---
name: restart-failed-jobs
description: Restart SLURM jobs that failed in an A2MC ensemble or experiment. Use when failures appear mid-run (NODE_FAIL, PartitionDown, SIGKILL clusters) or at end-of-run (model failures like runaway recruitment, FATES mass-balance, PARTEH abort). Distinguishes infrastructure (restart-eligible) from model failures (NOT restart-eligible without parameter/model fix). Picks between `tools/diagnose_ensemble_status.py` (quiescent ensemble) and the `sacct`-based TSV pathway (in-flight ensemble). Generates audit TSV + flat case-list, handles two-wave zombie cleanup, and submits restart via `submit_phase0.py --cases-file`.
---

# Restart Failed Jobs — A2MC HPC Workflow

Use this skill when the user reports failed cases that need restarting, or when an audit surfaces a failure cluster. Always **diagnose mode first** before generating a restart script — a wrong-mode restart either wastes compute (re-running unrecoverable model failures) or skips recoverable cases.

## Step 0 — Always re-source configs

Each Bash invocation is a fresh shell on Perlmutter; env vars don't persist:

```bash
source /global/u1/j/jingtao/A2MC/a2mc_config.sh
source /global/u1/j/jingtao/A2MC/use_cases/Kougarok/config/kougarok_config_r5.sh  # adjust for round
```

## Step 1 — Pick the right entry point

```
┌─ Is the ensemble quiescent?
│  (no submit_phase0.py running, no sbatch waves landing, no extract_* processes,
│   queue ≤ ~50 stragglers, no orchestrator session active)
│
├─► YES → Use `tools/diagnose_ensemble_status.py` (canonical, filesystem-based)
│
└─► NO  → Use the sacct-based TSV pathway (this skill, Steps 2+)
```

When `diagnose_ensemble_status.py` applies, just run it — it writes `restart_incomplete_<TS>.sh` + companion txt files and auto-invokes `tools/validate_restart_script.py` (checks filesystem state, STOP_N math, finidat consistency, chain wiring). Then `bash restart_incomplete_<TS>.sh` to submit. Skip the rest of this skill.

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
ZL1=/global/homes/j/jingtao/A2MC/tmp/r5_zombie_jobids_${TS}.txt
squeue -u $USER -h --format="%i %r" 2>/dev/null \
  | awk '$2=="DependencyNeverSatisfied"{print $1}' > $ZL1
echo "Wave 1: $(wc -l < $ZL1) zombies"
[ -s $ZL1 ] && xargs -a $ZL1 scancel
sleep 5

# Wave 2 (cascade — TRANS children of cancelled RGSP zombies)
ZL2=/global/homes/j/jingtao/A2MC/tmp/r5_zombie_wave2_jobids_${TS}.txt
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

Per `memory/dev_logs/20260518b` §"4. Failed-jobs log files" — captures the audit trail so the cohort is reproducible even if the SLURM controller forgets the jobs later.

```bash
START="2026-05-21T11:00:00"      # cluster window start
END="2026-05-21T13:00:00"        # cluster window end
TS_LABEL=$(date -d "$START" +%Y%m%d)
MODE_LABEL="NODE_FAIL CLUSTER"   # or "MODEL FAILURE COHORT", etc.

TSV=/global/homes/j/jingtao/A2MC/tmp/r5_failed_jobs_${TS_LABEL}.tsv
TXT=/global/homes/j/jingtao/A2MC/tmp/r5_failed_cases_${TS_LABEL}.txt
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
LOG=/global/homes/j/jingtao/A2MC/tmp/r5_rerun_${TS}.log

nohup python3 -u /global/u1/j/jingtao/A2MC/phases/phase0_design/submit_phase0.py \
    --cases-file /global/homes/j/jingtao/A2MC/tmp/r5_failed_cases_${TS_LABEL}.txt \
    --build-case 1 --skip-build-case \
    --batch-size 10 \
    --submit --allow-existing-case-dirs \
    > $LOG 2>&1 &
echo "Restart submitter PID: $!"
echo "Log: $LOG"
```

`--allow-existing-case-dirs` is required — case dirs on `/pscratch/` are reused; per-case scripts regenerate and resubmit all three phases (ADSP → RGSP → TRANS) with fresh `--dependency=afterok` chaining.

Arm Claude Monitor on the restart submitter log:

```text
tail -F -n 0 <log_path> 2>/dev/null \
  | grep -E --line-buffered "Stage 3|submission summary|Phase 0|Pre-flight|ERROR|Traceback|FAILED|MaxJobsExceeded|sbatch:|Killed|batch (25|50|75|100)/"
```

### Recipe B — Model failure → archive, do NOT restart without a fix

Per `20260514a` §"Why NOT retry the failed cases with patched params?": the failures are deterministic given the parameters. Restart files exist as **archive only** until a model fix or parameter exclusion lands. Document in the manuscript's effective-sample-size reduction.

If the user wants per-mode splits (rare; useful when a fix targets one mode):

```bash
RUN_BASE=/pscratch/sd/j/jingtao
for case in $(cat $TXT); do
  LOG=$(find $RUN_BASE -maxdepth 6 -name "atm.log.*" -path "*PtCNPEn${case}PrescP*" 2>/dev/null | head -1)
  [ -z "$LOG" ] && continue
  if grep -q "EDMainMod.F90:1010" "$LOG"; then echo $case >> /tmp/rerun_mode1_runaway.txt
  elif grep -q "PRTAllometricCNPMod.F90:1757" "$LOG"; then echo $case >> /tmp/rerun_mode2_parteh.txt
  elif grep -q "FatesPlantRespPhotosynthMod.F90:910" "$LOG"; then echo $case >> /tmp/rerun_mode3_canopy.txt
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
2. **Do NOT** union failure cohorts of different modes into one restart submission. Restarting model-failure cases wastes compute and pollutes the auto-discovered knowledge stream (per the auto-learn hardening of `20260519b`).
3. **Do NOT** skip the two-wave zombie cleanup. Wave 1 alone leaves cascade children sitting in queue indefinitely.
4. **Do NOT** add the TSV/txt to git — they're gitignored per CLAUDE.md Rule #4 and regenerate cleanly.
5. **Do NOT** push `tools/diagnose_ensemble_status.py` as the answer mid-flight. The user pushed back on this exact suggestion on 2026-05-22 — it's the canonical tool but only for quiescent ensembles.

## Cross-references

- Forensic record + source recipes consolidated: `memory/dev_logs/20260522a_R5_Failed_Job_Restart_Workflow.md`
- Recipe B origin (model failure modes 1/2/3): `memory/dev_logs/20260514a_R5_Batch1_67_Failed_ADSPs_Runaway_Recruitment.md`
- Recipe A.1 + A.2 origin (zombie + TSV): `memory/dev_logs/20260518b_R5_Mid_Ensemble_Audit_And_Automation_Hardening.md`
- Companion monitoring workflow: `arm-hpc-monitoring` skill + `memory/dev_logs/20260514c_*.md`
- Today's worked example: `memory/dev_logs/20260521a` §"Open Items" §1 + `memory/dev_logs/20260522b` Part 2
- Auto-memory: `feedback_slurm_query_pitfalls.md` (sacct filter pitfall); `reference_failed_job_restart_workflow.md` (this skill's pointer)
