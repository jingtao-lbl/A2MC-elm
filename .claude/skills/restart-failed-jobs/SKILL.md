---
name: restart-failed-jobs
visibility: public
category: calibration
description: Restart SLURM jobs or a single case that failed/TIMED OUT in an A2MC ensemble OR an ad-hoc offline-testing experiment. Use on any restart/resume — mid-run failures (NODE_FAIL, PartitionDown, SIGKILL clusters), end-of-run model failures (runaway recruitment, FATES mass-balance, PARTEH abort), or a TIMEOUT that must resume where it stopped. Routes THREE ways — a single suffixed experiment case → `tools/restart_experiment_case.py` (self-contained; also auto-repairs the downstream chain), a quiescent ensemble → `tools/diagnose_ensemble_status.py`, an in-flight ensemble → the `sacct`-based TSV pathway. This project resumes via `finidat` + `RUN_STARTDATE` + `STOP_N`, NEVER `CONTINUE_RUN`. Distinguishes infrastructure (restart-eligible) from model failures (NOT restart-eligible without parameter/model fix).
modes:
  requires_fates: false      # the SLURM restart workflow is model-agnostic
  nutrient_pathway: any
  scope: [hpc]
  summary: "Scheduler-level restart workflow; applies to any A2MC ensemble on a SLURM HPC. The model-failure fingerprints in Step 2 are FATES examples — a different model has different abort signatures."
---

# Restart Failed Jobs — A2MC HPC Workflow

Use this skill when the user reports failed cases that need restarting, or when an audit surfaces a failure cluster. Always **diagnose mode first** before generating a restart script — a wrong-mode restart either wastes compute (re-running unrecoverable model failures) or skips recoverable cases.

## Step 0 — Always re-source configs

Each Bash invocation is a fresh shell on the HPC login node; env vars don't persist. From the repo root:

```bash
source a2mc_config.sh
source use_cases/<site>/config/<site>_config.sh   # your site (and round) config
ROUND=r1                          # label for this round's audit files (adjust)
STEM="$(date +%Y%m%d)_restart_audit_${ROUND}"
TMP="$A2MC_USE_CASE_DIR/memory/phase_results/$STEM"; mkdir -p "$TMP"
# ^ durable, repo-tracked audit record (the TSV/txt/zombie-lists, Steps 3-4, Recipe B) -- NOT
#   $A2MC_ROOT/tmp. One folder per round per day; multiple invocations the same day share it since
#   every filename below already carries its own $TS/$TS_LABEL timestamp, so nothing collides.
TMPLOG="$A2MC_ROOT/tmp"; mkdir -p "$TMPLOG"
# ^ separate, deliberately scratch -- the restart SUBMITTER's live process log (Recipe A's $LOG)
#   is the ensemble-scale operational log arm-hpc-monitoring already documents at this exact path
#   (its own Step 1 table names the pattern tmp/r5_rerun_<TS>.log), not the durable forensic
#   record $TMP holds. Don't move it to $TMP -- these are two different artifact classes.
```

## Step 1 — Pick the right entry point

**Ask this FIRST — is this an ensemble at all?** The two branches below both assume the numbered Morris
ensemble. A single ad-hoc **offline-testing-workflow** case (a suffixed name like
`..._p169v6rffixRGnone_RGSP`, not a bare `{N}_{PHASE}`) is NOT one, and the ensemble machinery cannot
address it: `diagnose_ensemble_status.py` derives case names from `A2MC_CASE_NAME_PATTERN` and output
root from `A2MC_ENSEMBLE_OUTPUT`, neither of which matches a suffixed experiment case.

```
┌─ One ad-hoc / suffixed experiment case (offline-testing-workflow)?
│
└─► YES → `tools/restart_experiment_case.py --case-dir <case>`  (preview; add --execute)
          Skip the rest of this skill.
```

It is self-contained — case name, phase, output root, forcing-cycle length and last-completed year all
come from the case's own files — and `--execute` additionally walks the ENTIRE downstream chain and
re-chains it, which is what stops a restart from stranding a queued phase on
`DependencyNeverSatisfied`. Save the plan durably with `--output-script
use_cases/<site>/memory/phase_results/{stem}/restart_<case>_<YYYYMMDD>.sh`, and check that folder for
prior `restart_*.sh` from the same experiment — they are the authoritative precedent for its convention.

**Do NOT hand-roll the restart from `xmlquery` output.** This project resumes by pointing `finidat` at
an explicit restart file plus `RUN_STARTDATE` + `STOP_N`; cases run with `CONTINUE_RUN=FALSE`, so the
generic-CIME instinct to set `CONTINUE_RUN=TRUE` is wrong here, and a plain resubmit without these edits
silently re-runs from the original `RUN_STARTDATE`. Cycle-snap-back of the resume year applies to
**ADSP/RGSP only, never TRANS** (TRANS writes a restart every year, so there is no partially-replayed
forcing cycle to snap back from). See [[feedback_restart_via_finidat_not_continue_run]].

Otherwise, for the numbered Morris ensemble:

```
┌─ Is the ensemble quiescent?
│  (no submit_phase0.py running, no sbatch waves landing, no extract_* processes,
│   queue ≤ ~50 stragglers, no orchestrator session active)
│
├─► YES → Use `tools/diagnose_ensemble_status.py` (canonical, filesystem-based)
│
└─► NO  → Use the sacct-based TSV pathway (this skill, Steps 2+)
```

When `diagnose_ensemble_status.py` applies, run it with `--output-dir "$TMP"` (Step 0) — it writes
`restart_incomplete_<TS>.sh` + companion txt files there, durably (see anti-pattern #4), and auto-invokes
`tools/validate_restart_script.py` (checks filesystem state, STOP_N math, finidat consistency, chain
wiring). Then `bash restart_incomplete_<TS>.sh` to submit. Skip the rest of this skill.

> **Special case — a `restart_*.sh` that hit the QOS submit limit *partway***. If an auto-generated
> `restart_incomplete_<TS>.sh` aborted mid-run on `QOSMaxSubmitJobPerUserLimit` (or any `sbatch` error),
> some cases are in a **prepped-but-not-submitted** state — the script already did the per-case edits
> (`xmlchange`, `user_nl_elm` sed, `finidat` append, `case.setup`) but `case.submit` never reached SLURM.
> **Do NOT re-run the original `restart_*.sh`** — it re-does that prep and can clobber the already-correct
> state. Instead run **`tools/diagnose_qos_failures.py --restart-script <the restart_*.sh> --start-time <T>
> --output-dir "$TMP"`**: it diffs what the script prepped vs what actually reached the queue, and emits a
> **resubmit-only** script for the un-submitted `(case, phase)` set (add `--verify-prep` to confirm each
> case's prep is intact first). `--output-dir "$TMP"` makes this diagnosis durable too, same as everything
> else this skill writes (Step 0) — without it, the tool defaults to scratch `<dir-of-restart-script>/tmp/`.
> Filesystem-state-based like `diagnose_ensemble_status.py` but keyed on *submission reach*, not
> *run output* — the two answer different questions.

## Step 2 — Diagnose failure mode (CRITICAL)

Pull sacct over the failure window:

```bash
sacct -u $USER --starttime <window_start> --endtime <window_end> --noheader -P -X \
      --format=JobID,JobName,State,ExitCode,DerivedExitCode,Reason,Elapsed,NodeList,End 2>/dev/null \
  | awk -F'|' '$3=="FAILED" || $3=="NODE_FAIL"' | head -30
```

Then read the signature:

| Signal | Infrastructure (Recipe A) | Model failure (Recipe B) |
|---|---|---|
| `DerivedExitCode` | `0:9` (SIGKILL) on most | typically `0:0` with FATES Fortran abort code in log |
| `Elapsed` distribution | wide spread (mid-run kills, often hours) | tight, very short for ADSP runaway recruitment (<6 min) |
| `End` timestamps | clustered in narrow window (~minutes/seconds) | spread along the natural run timeline |
| `Reason` field | at least one `PartitionDown` is the smoking gun | typically blank or `NonZeroExitCode` |
| NodeList | spread across many `nid*` nodes simultaneously | correlates with Morris trajectories, not nodes |
| Case log fingerprint | nothing — truncated mid-line | one of `EDMainMod.F90:1010` (runaway), `PRTAllometricCNPMod.F90:1757` (PARTEH), `FatesPlantRespPhotosynthMod.F90:910` (canopy resistance) |

If the signature is mixed (some infrastructure, some model in the same window), they are **separate cohorts** — generate one TSV + txt per cohort. NEVER union them.

## Step 3 — Two-wave zombie cleanup (applies to both modes)

If any `DependencyNeverSatisfied` jobs are in the queue, clean them up FIRST. Required because canceling a parent zombie cascades children into the same state — must re-query and cancel again.

```bash
TS=$(date +%Y%m%d_%H%M%S)

# Wave 1
ZL1=$TMP/${ROUND}_zombie_jobids_${TS}.txt
squeue -u $USER -h --format="%i %r" 2>/dev/null \
  | awk '$2=="DependencyNeverSatisfied"{print $1}' > $ZL1
echo "Wave 1: $(wc -l < $ZL1) zombies"
[ -s $ZL1 ] && xargs -a $ZL1 scancel
sleep 5

# Wave 2 (cascade — TRANS children of cancelled RGSP zombies)
ZL2=$TMP/${ROUND}_zombie_wave2_jobids_${TS}.txt
squeue -u $USER -h --format="%i %r" 2>/dev/null \
  | awk '$2=="DependencyNeverSatisfied"{print $1}' > $ZL2
echo "Wave 2: $(wc -l < $ZL2) zombies"
[ -s $ZL2 ] && xargs -a $ZL2 scancel
sleep 5

# Confirm 0
squeue -u $USER -h --format="%r" 2>/dev/null | grep -c "DependencyNeverSatisfied"
# Expect: 0. If non-zero, repeat the loop until 0.
```

**Always confirm with the user before running `xargs scancel`** — destructive action. Cite the count and a small sample of job names so they know what's being cancelled.

## Step 4 — Generate durable record (TSV + flat list)

Capture the audit trail so the cohort is reproducible even if the SLURM controller forgets the jobs later.

```bash
START="2026-05-21T11:00:00"      # cluster window start
END="2026-05-21T13:00:00"        # cluster window end
TS_LABEL=$(date -d "$START" +%Y%m%d)
MODE_LABEL="NODE_FAIL CLUSTER"   # or "MODEL FAILURE COHORT", etc.

TSV=$TMP/${ROUND}_failed_jobs_${TS_LABEL}.tsv
TXT=$TMP/${ROUND}_failed_cases_${TS_LABEL}.txt
BODY=$(mktemp)

# Body: parse sacct → tab-separated rows
sacct -u $USER --starttime $START --endtime $END --noheader -P -X \
      --format=JobID,JobName,State 2>/dev/null \
  | awk -F'|' '$3=="FAILED"' \
  | awk -F'|' 'BEGIN{OFS="\t"} {
      job=$1; name=$2; n=name; sub(/^run\./,"",n);
      if (n ~ /s[0-9]+h[0-9]+m[0-9]+/) {
        batch="R4_orchestrator"; case_num=0;  # parse from name if needed
      } else {
        match(n, /PtCNPEn[0-9]+/); case_num=substr(n,RSTART+7,RLENGTH-7)+0;
        if (case_num<=1500) batch="batch1"; else if (case_num<=2250) batch="batch2A";
        else if (case_num<=3000) batch="batch2B"; else if (case_num<=3750) batch="batch3A";
        else if (case_num<=4500) batch="batch3B"; else if (case_num<=4890) batch="batch4";
        else batch="other";
      }
      if (n ~ /_ADSP$/) phase="ADSP"; else if (n ~ /_RGSP$/) phase="RGSP";
      else if (n ~ /_TRANS$/) phase="TRANS"; else phase="?";
      print job, name, case_num, phase, batch
    }' | sort -t$'\t' -k5,5 -k4,4 -k3,3n > $BODY

# Header
{
  echo "# Ensemble failed-jobs log — ${TS_LABEL} ${MODE_LABEL}"
  echo "# Generated: $(date '+%Y-%m-%d %H:%M %Z') (Perlmutter)"
  echo "# Source:    sacct ... --starttime $START --endtime $END (filtered State==FAILED)"
  echo "# Cause:     (fill in: infrastructure | model)"
  echo "# Note:      --state=FAILED filter is broken in this sacct build — must post-filter awk"
  echo "# Phase breakdown: ADSP=$(awk '$4=="ADSP"' $BODY | wc -l), RGSP=$(awk '$4=="RGSP"' $BODY | wc -l), TRANS=$(awk '$4=="TRANS"' $BODY | wc -l)"
  echo "# Columns:"
  printf 'JobID\tJobName\tCaseNumber\tPhase\tBatch\n'
} > $TSV
cat $BODY >> $TSV

# Flat case list — ensemble-eligible cases only (R5 batches, NOT R4 orchestrator)
awk -F'\t' '$5 ~ /^batch/ {print $3}' $BODY | sort -un > $TXT

echo "Wrote $(wc -l < $TSV) rows → $TSV"
echo "Wrote $(wc -l < $TXT) cases → $TXT"
rm -f $BODY
```

## Step 5 — Restart submission (mode-specific)

### Recipe A — Infrastructure failure → restart immediately

Wait for any in-flight `submit_phase0.py` to finish (or pause it) to avoid hitting NERSC's 5000-job ceiling. Then:

```bash
TS=$(date +%Y%m%d_%H%M%S)
LOG=$TMPLOG/${ROUND}_rerun_${TS}.log

nohup python3 -u phases/phase0_design/submit_phase0.py \
    --cases-file $TMP/${ROUND}_failed_cases_${TS_LABEL}.txt \
    --build-case 1 --skip-build-case \
    --batch-size 10 \
    --submit --allow-existing-case-dirs \
    > $LOG 2>&1 &
echo "Restart submitter PID: $!"
echo "Log: $LOG"
```

`--allow-existing-case-dirs` is required — existing case dirs on scratch are reused; per-case scripts regenerate and resubmit all three phases (ADSP → RGSP → TRANS) with fresh `--dependency=afterok` chaining.

Arm Claude Monitor on the restart submitter log:

```text
tail -F -n 0 <log_path> 2>/dev/null \
  | grep -E --line-buffered "Stage 3|submission summary|Phase 0|Pre-flight|ERROR|Traceback|FAILED|MaxJobsExceeded|sbatch:|Killed|batch (25|50|75|100)/"
```

### Recipe B — Model failure → archive, do NOT restart without a fix

Model failures are deterministic given the parameters, so re-running them unchanged just reproduces the failure. Restart files exist as **archive only** until a model fix or parameter exclusion lands. Document the effective-sample-size reduction.

If the user wants per-mode splits (rare; useful when a fix targets one mode):

```bash
RUN_BASE=$SCRATCH        # ensemble run-dir base (NERSC: $SCRATCH)
for case in $(cat $TXT); do
  LOG=$(find $RUN_BASE -maxdepth 6 -name "atm.log.*" -path "*PtCNPEn${case}PrescP*" 2>/dev/null | head -1)
  [ -z "$LOG" ] && continue
  # Route through $TMP, not a raw /tmp/ -- writing outside $HOME on Perlmutter is a hard NERSC rule,
  # and these per-mode case lists are as much a durable audit record as the Step 4 TSV.
  if grep -q "EDMainMod.F90:1010" "$LOG"; then echo $case >> $TMP/${ROUND}_rerun_mode1_runaway_${TS_LABEL}.txt
  elif grep -q "PRTAllometricCNPMod.F90:1757" "$LOG"; then echo $case >> $TMP/${ROUND}_rerun_mode2_parteh_${TS_LABEL}.txt
  elif grep -q "FatesPlantRespPhotosynthMod.F90:910" "$LOG"; then echo $case >> $TMP/${ROUND}_rerun_mode3_canopy_${TS_LABEL}.txt
  fi
done
```

When a fix lands, restart only the relevant mode's case list via the same Recipe A.3 command.

### Recipe C — Mixed cohorts

If the failure window has both modes:

1. Generate one TSV + txt per cohort (separate timestamps, separate `MODE_LABEL`).
2. Verify disjoint: `comm -12 <(sort -u cohortA.txt) <(sort -u cohortB.txt)` should be empty.
3. Restart only the infrastructure cohort (Recipe A); archive the model-failure cohort (Recipe B).

## NODE_FAIL state — usually auto-handled

Jobs in `NODE_FAIL` state (distinct from `FAILED`) are typically auto-requeued by SLURM when `--requeue` is set in the batch script. Verify by checking whether they reappear in `squeue` within ~15 min of the event. If they don't, treat them as FAILED and include in Recipe A.

## Anti-patterns (do not do these)

1. **Do NOT** run `tools/diagnose_ensemble_status.py` while the ensemble is in flight — running cases look identical to incomplete cases on disk; you'll get spurious restart entries.
2. **Do NOT** union failure cohorts of different modes into one restart submission. Restarting model-failure cases wastes compute and pollutes the auto-discovered knowledge stream.
3. **Do NOT** skip the two-wave zombie cleanup. Wave 1 alone leaves cascade children sitting in queue indefinitely.
4. **Do NOT leave this skill's own audit TSV/txt/zombie-list files untracked in `$A2MC_ROOT/tmp`.**
   They live in `$A2MC_USE_CASE_DIR/memory/phase_results/{stem}/` (Step 0) and are the durable
   forensic record of a restart cohort — `git add` + commit them, the same as any other
   `phase_results/{stem}/` artifact. **Same rule now applies to `diagnose_ensemble_status.py`'s and
   `diagnose_qos_failures.py`'s own outputs** (`completed_cases_*.txt`, `restart_incomplete_*.sh`,
   `restart_qos_resubmit_*.sh`, etc.) — as of 2026-08-14 (CLAUDE.md Operating Rule #3) they're
   gitignored **only** at their scratch default (repo root / `<script-dir>/tmp/`); pass
   `--output-dir "$TMP"` (both tools support it, shown in Step 1 above) to make a given invocation's
   output durable instead. A quick ad-hoc status check with no `--output-dir` is still fine to leave
   as scratch — the point is that a restart decision's audit trail should not be, and now has a real
   way to not be.
5. **Do NOT** push `tools/diagnose_ensemble_status.py` as the answer mid-flight. The user pushed back on this exact suggestion on 2026-05-22 — it's the canonical tool but only for quiescent ensembles.

## Cross-references

- Companion monitoring workflow: the `arm-hpc-monitoring` skill.
- The canonical quiescent-ensemble tool: `tools/diagnose_ensemble_status.py` (+ `tools/validate_restart_script.py`).
- Restart submission entry point: `phases/phase0_design/submit_phase0.py --cases-file`.

> The detailed forensic records and worked examples that this workflow was distilled from
> live in the analysis dev-logs of the manuscript working branch, not on `main`.

## Changelog

- 2026-08-20 — **Added the ad-hoc-case fork as Step 1's FIRST question, and named it in the
  frontmatter description.** `restart_experiment_case.py` previously appeared in this skill ONLY
  inside a 2026-08-14 changelog entry — never as a routing step — while the description named just
  the two ensemble pathways. So for a single suffixed experiment case the routing layer pointed at
  machinery that structurally cannot address it (the tool exists precisely because
  `A2MC_CASE_NAME_PATTERN`/`A2MC_ENSEMBLE_OUTPUT` don't match a suffixed case), and the fallback was
  generic CIME knowledge — i.e. `CONTINUE_RUN`. Also states the finidat/RUN_STARTDATE/STOP_N
  mechanism and the ADSP/RGSP-only scope of cycle-snap-back inline. Signal: PI correction 2026-08-20
  — *"why when it comes to restarting a run, you always go to check CONTINUE_RUN and are going to
  hand-roll the restart? ... this actually happened many times already"*, plus a second correction
  that cycle-snap-back is spin-up-only. Companion memory:
  `feedback_restart_via_finidat_not_continue_run`. Remedy shape follows the 2026-08-16 precedent
  (`reflection/20260816a_*`): fix the mechanism/routing, don't just document harder.

- 2026-08-14 (b): **Extended the durable-artifact treatment to `diagnose_ensemble_status.py` and
  `diagnose_qos_failures.py`'s own outputs** (Step 1, anti-pattern #4). These were previously
  described as "genuinely gitignored" (the (a) entry below drew that as the contrast case) — now,
  per PI request, `--output-dir "$TMP"` makes a given invocation's `completed_cases_*.txt`,
  `restart_incomplete_*.sh`, `restart_qos_resubmit_*.sh`, etc. durable and git-trackable, same as
  this skill's own sacct TSVs. The scratch default (repo root / `<script-dir>/tmp/`) is unchanged
  for a quick ad-hoc status check with no `--output-dir`. Required a `.gitignore` fix beyond the
  obvious one: the existing `use_cases/ELM-FATES_Kougarok/memory/phase_results/**` negation (2026-07-21)
  already un-ignores that whole tree, but the broader filename-pattern block
  (`completed_cases_*.txt` etc.) is declared *after* it in the file, so under gitignore's
  last-match-wins rule it was silently re-ignoring anything with these names placed there — added a
  second, more specific negation after the filename block itself to win the tie-break; verified
  empirically with `git check-ignore` before committing (durable-location files un-ignored,
  repo-root/`tmp/` files still ignored). Also fixed a pre-existing citation error found while
  touching this text: anti-pattern #4 (and this file's own (a) entry below) cited "CLAUDE.md Rule
  #4" for the transient-outputs policy; the actual rule is **Rule #3** — Rule #4 in that numbered
  list is `A2MC_MODEL_PATH` being required, an unrelated rule. CLAUDE.md's own Rule #3 text updated
  in the same commit. Signal: PI request, direct follow-on to the same-day (a) fix below.
- 2026-08-14 (a): **This skill's own sacct-based audit TSV/txt/zombie-lists moved from scratch
  `$A2MC_ROOT/tmp` to durable `$A2MC_USE_CASE_DIR/memory/phase_results/{stem}/`** (`$TMP`, Step 0,
  Steps 3-4, Recipe B, anti-pattern #4). They are the forensic record of a restart cohort, not
  regenerable ensemble-scale scratch — conflating them with `diagnose_ensemble_status.py`'s own
  gitignored outputs (`completed_cases_*.txt`, `restart_incomplete_*.sh`, covered by CLAUDE.md Rule
  #4) was the error; those two mechanisms are different, and only one of them is meant to be thrown
  away. **Kept Recipe A's restart-submitter process log (`$LOG`) in scratch**, via a new separate
  `$TMPLOG="$A2MC_ROOT/tmp"` — that log is the ensemble-scale operational artifact
  `arm-hpc-monitoring` already documents at exactly this path (its own Step 1 table names the
  pattern `tmp/r5_rerun_<TS>.log`), a different class from the durable TSV/txt; an early draft of
  this fix pointed it at the new `$TMP` too, which would have contradicted that existing convention
  — caught on a full re-read before committing. Also fixed a genuine NERSC-rule violation found in
  the same pass: Recipe B's per-mode case-split loop wrote to a raw `/tmp/rerun_mode*.txt` (writing
  outside `$HOME` on Perlmutter), now routed through the durable `$TMP`. Signal: PI correction,
  prompted directly by the `offline-testing-workflow` Step 9d fix earlier the same session
  (`20260814j`) that gave `restart_experiment_case.py` an `--output-script` destination — the PI
  then asked for the same audit here.
- 2026-07-15: Named `tools/diagnose_qos_failures.py` (Step 1 special case) — for a `restart_*.sh` that hit `QOSMaxSubmitJobPerUserLimit` partway (cases prepped but `case.submit` never reached SLURM); emits a resubmit-only script without re-doing the prep. Ported from demo `ce7dc47` (tool copied from demo — it's generic, zero site hardcoding).
- 2026-06-13 — Ported to `main` (v2.103, Phase 1): scrubbed for the generic public repo, added `modes:` frontmatter.
