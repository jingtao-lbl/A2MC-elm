---
name: arm-hpc-monitoring
visibility: public
category: calibration
description: Set up real-time monitoring of an active A2MC HPC ensemble or experiment on Perlmutter at session start (CLAUDE.md Rule #6). Detects live long-running login-node processes (auto-monitor, submitter, extractor) via `ps -ef`, arms Claude `Monitor` tasks on each long-running log with the right event + error filter (silence ≠ success), requires that layer 2 verify the watcher itself is still alive (a dead watcher is silent, and so is a healthy one), and reminds Claude to react with proposals rather than just relaying events. Use whenever a session begins (or resumes after compaction) while an ensemble round is in flight. Also use immediately after launching a new submitter or restart job.
modes:
  requires_fates: false      # session-start HPC monitoring; model-agnostic
  nutrient_pathway: any
  scope: [hpc]
  summary: "Monitors any in-flight A2MC ensemble/experiment; model-agnostic."
---

# Arm HPC Monitoring — Session-Start Runbook

Per **CLAUDE.md Rule #6**, when an HPC ensemble is in flight (R4/R5/...), the session must arm `Monitor` on every long-running log within the first few exchanges. Silence on a crashed process looks identical to silence on a still-running process — so coverage **must include error signatures**, not just happy-path events.

## Step 1 — Detect what's running

```bash
ps -ef | grep $USER | grep -E "r5_auto_monitor|submit_phase0|extract_ADSP_RGSP_slim|extract_monthly_variables_FATES|plot_all_extracted" | grep -v grep
```

Typical processes seen on this branch:

| Process | Typical PID lifetime | Log location (typical) |
|---|---|---|
| `r5_auto_monitor.sh` | 12+ hours (full round) | `tmp/r5_auto_monitor_<startTS>.log` |
| `submit_phase0.py --start N --end M` | ~9 h per 1000 cases | `tmp/r5_batch<N>_cases<A>-<B>_<TS>.log` |
| `submit_phase0.py --cases-file ...` (restart) | shorter, sized to cohort | `tmp/r5_rerun_<TS>.log` |
| `extract_ADSP_RGSP_slim.py` / `extract_monthly_variables_FATES.py` | minutes per batch | spawned by auto-monitor; no persistent log |
| `plot_all_extracted*.py` | minutes per milestone | `tmp/r5_plot_milestone<N>_<TS>.log` |

The active handoff log (typically the most recent `dev_logs/2026MMDDx_*.md`) names the live PIDs and exact log paths. **Read it first** to confirm what to arm.

> **Log location — ensemble scale goes to `tmp/`.** The auto-monitor / submitter / plot logs above live in the **repo-relative `tmp/`** (e.g. `~/A2MC-main/tmp/r5_auto_monitor_<TS>.log`) — **not** `~`, **not** a system `/tmp`. For a full ensemble this is the right home (many long-lived, high-volume, auto-generated logs; they don't belong beside the per-case scripts). This is deliberately **distinct from the `offline-testing-workflow` convention**, where a *small* experiment's launcher/submitter running log goes **in that experiment's `use_cases/{site}/memory/phase_results/{stem}/`** (repo-tracked, alongside the hand-authored case script(s), param files, figures, and captions — corrected 2026-08-12, was previously misdocumented as `$A2MC_SCRIPTS_DIR`/scratch). Rule of thumb: **ensemble monitoring → repo `tmp/`; a small offline experiment's run log → its `phase_results/{stem}/`.** Don't over-apply one skill's convention to the other.

### Choosing where to launch a NEW watcher

If you're arming monitoring for something you're about to launch yourself (not adopting an
already-running process), don't default the launch node to wherever an unrelated existing
process happens to already be — verify your own node and use it:

```bash
hostname                                    # this session's own node -- launch here by default

nohup bash watcher.sh >> watcher.events.log 2>> watcher.log &
disown                                      # layer 1

# layer 2: arm `Monitor` with a PLAIN LOCAL command, no ssh wrapper:
#   command = "bash monitor_feed.sh"
# never: command = 'ssh <node> "bash monitor_feed.sh"' -- that puts the checker on the
# same node as the thing being checked, defeating layer 2's independence (anti-pattern #11).
```

### Verify the actual SLURM job name before filtering by it

CIME's `case.submit` names every submitted job `run.<case_name>`, **not** the bare case name. A
`squeue -n`/`sacct --name` filter on the bare name matches nothing — and the failure is silent, not
an error, so it reads identically to "not yet submitted." Confirm the real name once before writing
the filter:

```bash
squeue -u $USER -h -o "%j" | grep <case_name_fragment>
# => run.Kougarok_ELM-FATES_PtCNPEn2939_p169v6rffix_ADSP
squeue -u "$USER" -h -n "run.$CASE_NAME" -o "%A %T %M"
sacct  -u "$USER" --name="run.$CASE_NAME" -o JobID,State --noheader --parsable2
```

## Step 2 — Arm Claude Monitor on the auto-monitor log (always, if present)

Broad event + error filter. This catches normal progress AND failure signatures:

```text
tail -F -n 0 <auto_monitor_log_path> 2>/dev/null \
  | grep -E --line-buffered "QUEUE_BELOW_1000|QUEUE_BELOW_500|QUEUE_ABOVE_500|TRANS_DONE|STARTING_EXTRACTION|EXTRACTION_FINISHED|EXTRACTED_CASES|MILESTONE|REGEN_LAUNCH|IDLE_TICK|R5_TERMINAL|ERROR|Traceback|FAILED|MaxJobsExceeded|Killed|OOM"
```

Always `persistent: true` and a long timeout. Reasoning: this monitor runs for the session lifetime; a short timeout silently drops you off the event stream.

## Step 3 — Arm Claude Monitor on each active submitter log (if any)

For a fresh launch, use the **tight** filter — per-batch progress (`batch [0-9]+/`) emits one event every ~5 min for hours, which is noisy. Limit to quarter-milestones + stage transitions + errors:

```text
tail -F -n 0 <submitter_log_path> 2>/dev/null \
  | grep -E --line-buffered "Stage 3|submission summary|Phase 0|Pre-flight|ERROR|Traceback|FAILED|MaxJobsExceeded|sbatch:|Killed|batch (25|50|75|100)/<TOTAL>"
```

Replace `<TOTAL>` with the actual batch count (e.g., `114` for 1140 cases at batch-size 10). If unknown, omit the batch alternation entirely — milestone monitoring is optional; error monitoring is not.

For a submitter that already finished (log ends with `submission summary: N OK, 0 FAILED`), DO NOT arm a Monitor on it — nothing more will be written. Confirm completion via `tail -5 <log>` first.

## Step 4 — React to events with proposals, not relay

The session-start runbook explicitly calls out (`CLAUDE.md` Rule #6, paraphrased):

> "react to events with proposals, not just relay: queue-threshold downcross → headroom math + propose next batch; extraction-milestone crossing → regenerate the ensemble plot per `feedback_plot_filename_convention`; ensemble-terminal signal → propose next phase (e.g. Phase 1 extraction + Morris sensitivity for an exploration round)."

Concrete reaction table:

| Event | Required reaction (not just "noted") |
|---|---|
| `QUEUE_BELOW_1000` / `QUEUE_BELOW_500` | Compute headroom: `current_queue + N_new_cases × 3 ≤ 5000`. Propose next batch (combined vs split). |
| `TRANS_DONE` + `STARTING_EXTRACTION` in normal cadence | Silent acknowledgment (use "Normal" or omit). These arrive every poll cycle. |
| Milestone-crossing extracted count (e.g., 2750, 3000) | The auto-monitor's `regen_milestone_plot.sh` should fire automatically. Confirm `REGEN_LAUNCHED` events follow. If not, manually invoke `bash use_cases/ELM-FATES_Kougarok/analysis/regen_milestone_plot.sh`. |
| `QUEUE_ABOVE_500` (after a submission launches) | Acknowledge as expected; sentinel re-arms for next downcross. |
| `R5_TERMINAL` / `EXTRACTION_FINISHED` (round complete) | Propose Phase 1 (extraction + Morris sensitivity analysis) per the round-completion runbook. |
| `FAILED` / `Traceback` / `MaxJobsExceeded` / `Killed` / `OOM` | **Stop. Investigate.** Pull recent log context, identify the source process, propose remediation (often: cancel the zombie/dead-dependency chain per **Step 7**, restart submitter, or invoke the `restart-failed-jobs` skill). |
| A chained phase (e.g. an AD-spinup → spinup → transient leg) crashes | Its downstream phases are now zombies. Cancel the dead chain (**Step 7**) so it doesn't linger in the queue or hang a completion watcher. |

If you find yourself replying with "Normal" or just relaying the event text three times in a row to a non-routine event, you are failing the proposals rule — re-read the table.

## Step 5 — Verify silence detection works

A monitor with only happy-path filters (e.g., `QUEUE_BELOW_500|TRANS_DONE|elapsed_steps`) will be **silent during a crash** — and silence reads identical to "still running." Before ending your arming, sanity-check that your filter alternation includes:

- At least one progress signal (`TRANS_DONE`, `Stage 3`, etc.)
- At least three failure signals (`ERROR`, `Traceback`, `FAILED`, ideally also `Killed`, `OOM`, `MaxJobsExceeded`)

If your filter doesn't satisfy this, widen it before arming. Some extra noise is far better than missing a crashloop.

### The same defect one level up: prove the WRITER is alive

The two bullets above make the *job's* failure visible. They do nothing about the **watcher's** failure.

Layer 1 (the nohup'd `ensemble_auto_monitor.sh` or a per-run watcher) is a single point of failure, and
**its failure mode is silence — which is also its healthy state between milestones.** A layer-2
`tail -F` cannot tell "watcher alive, nothing to report" from "watcher died an hour ago"; both are an
empty stream. So a monitor that only tails is trusting an unverified process to keep telling the truth.

**Requirement: layer 2 must verify layer 1 independently of what layer 1 says.** The log file's mtime is
the check — it is written by the poll loop itself, so it cannot be faked by a hung process:

```bash
age=$(( $(date +%s) - $(stat -c %Y "$POLL_LOG" 2>/dev/null || echo 0) ))
if [ "$age" -gt $(( 2 * POLL_INTERVAL_S )) ]; then
    echo "WATCHER STALL: poll log untouched ${age}s. Layer 1 may have died; the SLURM jobs are NOT
          necessarily affected — check squeue directly."
fi
```

Two properties that make the event actionable rather than alarming:

- **Edge-triggered, not level-triggered.** Emit once on entering the stalled state and once on recovery;
  re-emitting every tick trains you to ignore it (anti-pattern #4 in another form).
- **It says what it does *not* imply.** A dead watcher is not a dead run. Conflating them invites
  cancelling healthy jobs, which is the expensive direction of this mistake.

**Also emit a forced heartbeat** (last poll block, on a fixed wall-clock interval). Progress milestones
are keyed to *model* time, so at a slow rate they can be hours apart, and "no news for four hours" is
again ambiguous. A heartbeat on the cadence the human actually asked for removes the ambiguity without
touching the filter.

This is the same principle as anti-patterns #8 and #9 and as the allow-list rule in Step 7: **a read that
fails silently must never be indistinguishable from a clean result.** It has now been violated at three
levels in one workflow — a `grep` on a gzipped log, a `sacct` outage read as job completion, and a dead
watcher read as a quiet run — which is why it is stated as a general property here rather than as three
separate fixes.

## Step 6 — Volume-control: tighten filters on noisy submitter logs

If a Monitor produces > ~20 events in 10 minutes, it will likely auto-stop (the harness drops over-noisy monitors). Common culprit: per-batch `batch N/114` lines from `submit_phase0.py`. Tighten by:

1. `TaskStop <old_monitor_id>`
2. Re-arm with quarter-milestone alternation: `batch (25|50|75|100)/<TOTAL>` instead of `batch [0-9]+/`
3. Keep all error signals in the new filter

Document the tightening in the active dev_log so the next session uses the cleaner filter.

## Step 7 — Cancel zombie / dead-dependency jobs (unblocks completion monitors)

When one phase of a chained multi-phase case (`AD-spinup → spinup → transient`, submitted with `--dependency=afterok:`) **crashes**, every downstream phase becomes un-runnable. SLURM marks the *immediate* dependent `DependencyNeverSatisfied`, but it often does **not** propagate that state further down the chain: the grand-child phase keeps showing reason `Dependency` (as if it's just waiting) even though its parent is permanently dead. These are **zombie jobs** — they will never run, but they linger in the queue indefinitely (SLURM does not auto-purge them unless `kill_invalid_depend` is set cluster-wide, which it usually is not on Perlmutter).

**Why this matters for monitoring (the trap):** a "wait until the batch fully resolves" watcher that counts *runnable* jobs (`R` + PD with a satisfiable reason) will **never reach 0** — the un-propagated zombies sit in `PD|Dependency` forever, so the completion signal never fires. You wait on a run that finished hours ago.

**Detect** — a `DependencyNeverSatisfied` job is the head of a dead chain; everything downstream of it in the same case is a zombie:

```bash
# any never-satisfiable job = a crashed ancestor somewhere in its chain
squeue -u $USER -h -o "%.12i %r %j" | grep -E "DependencyNeverSatisfied"
```

**Confirm dead before canceling** (never cancel on suspicion): the ancestor phase must have actually failed, not just be slow. Check the crashed phase's `CaseStatus` (should show a non-`success` end, or the job is simply gone with no `case.run success`):

```bash
tail -4 ${A2MC_E3SM_ROOT}/cime/scripts/<case>_<PHASE>/CaseStatus   # look for a crash, not "case.run success"
```

**Read the crash cause by JOB ID — never a log glob.** CIME writes a *new*
`e3sm.log.<jobid>.<timestamp>` (plus `lnd.log.<jobid>.*`, `atm.log.<jobid>.*`) for **every** run
of a case and **never deletes the old ones**. So a case that crashed, was fixed, and resubmitted
has BOTH the stale crash log and the healthy new log in `run/` — and `grep <pattern> run/e3sm.log.*`
matches the *old* crash, reporting a **false "crashed again"** while the current run is fine.
**Capture the SLURM job id at submit** (`case.submit` prints `Submitted job id is <jobid>`) and
inspect only that run's logs:

```bash
JID=<jobid>                    # the id from THIS submission (e.g. 55824374)
RUNDIR=$(cd ${A2MC_E3SM_ROOT}/cime/scripts/<case>_<PHASE> && ./xmlquery -value RUNDIR)
grep -c "ERROR\|ENDRUN\|EDPftvarcon" "$RUNDIR"/e3sm.log.$JID.*   # THIS run only — NOT e3sm.log.*
tail -20 "$RUNDIR"/lnd.log.$JID.*                                # ELM-side detail, same run
```

Cross-check with elapsed time: a job still `RUNNING` far past the crash point (e.g. hours, when the
crash hit at ~2 min into init) cannot have crashed at init — trust `squeue` elapsed over a stale log.

**A COMPLETED run's logs are gzipped — plain `grep` on them silently finds nothing.** CIME compresses
`lnd.log.*` / `e3sm.log.*` to `.gz` when a run finishes. The glob still matches, so the file is found
and only the *grep* fails, returning a clean no-match. A sweep over a mixed set therefore reports
**zero crash signatures for exactly the runs that completed** — no error, no warning, a plausible
"clean" row. Pick the tool from the suffix, and take completion from the (never-compressed) restart
files rather than the log:

```bash
case "$f" in *.gz) G=zgrep;; *) G=grep;; esac
"$G" -c "ERROR\|ENDRUN" "$f"
ls "$RUNDIR"/*.elm.rh0.*.nc | tail -1     # how far it ACTUALLY got
```

See `<auto-memory>/feedback_run_logs_may_be_gzipped` (the 2026-08-08 near-miss that produced this).

**Cancel surgically** — target only the provably-dead chain by name pattern or explicit IDs; **never** blanket-`scancel -u $USER` (that kills the live variants too):

```bash
ids=$(squeue -u $USER -h -o "%i %j" | grep -E "<dead-variant-name-pattern>" | awk '{print $1}')
echo "$ids"          # eyeball the list FIRST — confirm no live variants matched
scancel $ids
```

Safety: these are your own guaranteed-non-runnable jobs, and cancellation is reversible (resubmit the chain if a fix lands). This is routine housekeeping, not a destructive act — but the *targeting* is what must be exact. Re-list the queue after canceling to confirm only the live chains remain.

## Step 8 — Arm an independent `DependencyNeverSatisfied` check

Steps 2-5's layer-1/layer-2 apparatus only sees what the *watcher script itself* decides to check
and write. Two gaps follow from that, both hit live on 2026-08-16 within the same few hours:

1. **Nothing watches for a dependency zombie unless the watcher script explicitly checks for one.**
   Step 7's `DependencyNeverSatisfied` recipe is a *manual* detection command — it only runs when
   someone remembers to run it. Restarting a phase whose downstream was already queued (a same-phase
   restart via `tools/restart_experiment_case.py`, or any other resubmit) can leave that downstream
   chained to the now-superseded old job ID; nothing here re-checks for that unless a human/agent
   re-invokes Step 7 by hand. See
   `memory/dev_logs/reflection/20260816a_Reflection_Restart_Tool_Left_A_Zombie_Its_Own_Docstring_Warned_About.md`
   — a zombie sat unnoticed for ~30 hours because no monitor filter, layer-1 watcher, or habit caught
   it; a routine PI status check did.
2. **The whole apparatus is watcher-dependent.** If the layer-1 script dies (Step 5 covers this) or was
   never armed for a *particular* case (e.g. a case restarted outside the watcher's original tracking
   list), layers 1-2 see nothing for it at all — Step 8 does not depend on any watcher script existing.

Arm a **third, independent** Monitor that queries `squeue` directly — no watcher script, no log file,
no dependency on anything else in this skill staying alive:

```bash
check_once() {
  ts=$(date '+%Y-%m-%d %H:%M:%S %Z')
  echo "=== squeue check $ts ==="
  squeue -u "$USER" -h -o "%.10i %.9M %.3t %j %r" 2>/dev/null
  zombies=$(squeue -u "$USER" -h -o "%i %r" 2>/dev/null | grep -c "DependencyNeverSatisfied")
  if [ "$zombies" -gt 0 ]; then
    echo "ZOMBIE ALERT: $zombies job(s) with DependencyNeverSatisfied -- needs chain repair"
    squeue -u "$USER" -h -o "%i %j %r" 2>/dev/null | grep "DependencyNeverSatisfied"
  fi
}
check_once
while true; do
  sleep <INTERVAL_SECONDS>
  check_once
done
```

**Choosing `<INTERVAL_SECONDS>` is a judgment call, not a fixed number — do not default to a
specific interval (e.g. always 3600) without thinking about the actual campaign.** Factors that
should move it:

- **How exposed is a fresh restart right now?** Right after restarting a phase with an
  already-queued downstream (exactly Step 8's trigger case), a *tighter* interval for the next
  hour or two buys faster confirmation that the cascade repair actually took; once several checks
  come back clean, widening is fine.
- **How long could a zombie sit before it matters?** A zombie is harmless *while it sits* (it is
  not consuming compute), but it hides a completion signal and a downstream phase that will never
  run. Weigh that against the walltime ceiling of the phases involved (this project's QOS ceiling
  is 47:59:00) — an interval a large fraction of that ceiling risks a zombie surviving an entire
  walltime window undetected.
- **How many chains, and how bursty?** A single quiet chain deep into a multi-day TRANS run does
  not need checking as often as a campaign mid-restart-storm with several phases changing job IDs
  in quick succession.
- **Session-scoped, not durable.** Like every `Monitor`, this dies with the session and is not
  written to disk anywhere — re-arm it at session start alongside Steps 2-3 whenever a chain is in
  flight, the same trigger condition as the rest of this skill.

When the alert fires, the fix is `tools/restart_experiment_case.py --rechain-downstream --case-dir
<the case whose job ID changed> --new-jobid <its current job ID>` (it walks the *entire* downstream
chain automatically, not just the one flagged job — see that tool's own docstring). If the zombie's
upstream is itself the one that needs restarting (not just re-chaining), a normal
`--execute` run already triggers this same cascade as its last step; Step 8 is what tells you a
cascade run is needed in the first place, for the case where nothing already noticed.

## Anti-patterns

1. **Do NOT** rely on the happy-path filter alone — if the process crashes, you'll never know.
2. **Do NOT** arm a Monitor without `persistent: true` for session-length watches — a 5-minute timeout means you stop receiving events 5 min after the harness fires.
3. **Do NOT** sleep/poll to wait for monitor events. The events arrive as notifications. If you need a one-shot "wait until ready," use Bash `run_in_background` with an `until` loop instead.
4. **Do NOT** narrate every event back to the user. Acknowledge with "Normal" or silence for routine, react with proposals for threshold crossings and errors.
5. **Do NOT** assume the auto-monitor survived the previous session — Claude Monitors are session-local. A nohup'd auto-monitor script itself survives, but the *tail process* armed by `Monitor` does not. Always re-arm at session start.
6. **Do NOT** count `PD|Dependency` jobs as "still runnable" in a completion/resolution watcher without first purging zombies (Step 7) — a crashed chain leaves un-propagated dependents in `PD|Dependency` that never run, so the watcher hangs forever on a finished batch.
7. **Do NOT** use blanket `scancel -u $USER` to clear zombies — it kills the live variants too. Cancel by name pattern / explicit IDs, and eyeball the ID list before firing.
8. **Do NOT** `grep e3sm.log.*` / `lnd.log.*` across a case's run dir to check for a crash — CIME keeps **every** prior run's logs, so a stale crashed-run log yields a false "crashed again." Scope to the current run's job id (`e3sm.log.<jobid>.*`), and cross-check elapsed `RUNNING` time (Step 7).
9. **Do NOT** plain-`grep` a **finished** run's log — CIME gzips it, so `grep` returns a silent clean no-match and every completed run reads as crash-free. Branch on the `.gz` suffix (`zgrep`), and read completion from `*.elm.rh0.*.nc` restart dates, not from the log (Step 7).
10. **Do NOT** arm layer 2 as a bare `tail -F` of layer 1's log and call the run monitored — if layer 1 dies, the stream goes quiet, and quiet is exactly what a healthy run looks like between milestones. Layer 2 must check layer 1's liveness (poll-log mtime) and emit a stall event (**Step 5**). Corollary: **do NOT report a stalled watcher as a stalled run** — they are independent, and only `squeue` settles which one it is.
11. **Do NOT default a watcher's launch node to wherever a pre-existing, unrelated process happens to already be running, and do NOT arm layer 2 (`Monitor`) via SSH to that same specific node.** There is no way to predict which login node will get drained for scheduled maintenance next — no status API, no advance notice observed in practice. Minimize exposure instead of guessing at "stability": launch layer 1 on the node your own session already executes on (its outage fails your next command visibly and immediately, so you never depend on a separate mechanism to notice), and arm layer 2 as a **local** `Monitor` command reading the shared-filesystem log — never `ssh <node> "bash monitor_feed.sh"` to the same node layer 1 runs on — concrete recipe in **Step 1**. Both mistakes were made together in one incident: a new watcher was launched on a node purely because an unrelated, pre-existing watcher happened to already be there, and layer 2 was armed over SSH to that same node — so when the node was drained for maintenance, both layers died together, and layer 2's own stall-detection (**Step 5**) never got the chance to fire, because the process meant to run it was dead too. The whole point of two layers is that they can't fail together. **This matters more, not less, at ensemble scale:** a multi-day 5000+-job campaign makes a mid-campaign login-node maintenance event near-certain rather than an unlucky coincidence, so the auto-monitor script driving that campaign (**Step 1**) and its `Monitor` both need this same discipline, not just a small offline-test watcher.
12. **Do NOT** assume a submitted job's SLURM name equals its case name when writing a `squeue -n`/`sacct --name` filter. CIME's `case.submit` names every job `run.<case_name>` (confirmed via `squeue -u $USER -h -o "%j"`), not the bare case name. A watcher filtered on the bare name matches nothing and silently logs `NOT_IN_QUEUE` on every poll — indistinguishable from "not yet submitted" or "terminal," while the job is actually running. Hit two independently-written watchers the same way in one session (2026-08-12) — one new, one armed a day earlier and silently non-functional the whole time — caught by a direct cross-check, not by the watcher itself. Verify the real name once via `squeue -o "%j"` before writing the filter (Step 1).
13. **Do NOT** rely on Step 7's `DependencyNeverSatisfied` recipe being re-run manually after every restart, and do NOT assume Steps 2-5's watcher-mediated monitoring will ever surface a dependency zombie — no watcher filter in this skill checks for one. Arm Step 8's independent check whenever a chain is in flight, the same trigger condition as the rest of this skill, not only when you already suspect a problem. Found live 2026-08-16: a zombie left by a restart sat undetected for ~30 hours until a routine PI status check caught it — see the reflection log Step 8 cites.

## Cross-references

- Companion restart workflow: the `restart-failed-jobs` skill.
- `tools/restart_experiment_case.py` — Step 8's fix command; its own docstring documents the automated multi-hop downstream cascade `--execute` triggers.
- **`calibration-goal`** — the run-to-convergence driver: when it hits a phase with an in-flight ensemble it takes a WAIT stop and relies on the `Monitor` events armed here as its **cross-wait re-invocation trigger** (the completion/milestone event resumes the driver loop).
- The interactive-agent operating contract: `AGENTS.md`.
- A site's live auto-monitor script (if any) lives under `use_cases/<site>/analysis/`.

## Changelog

- 2026-08-16 — Added **Step 8 — arm an independent `DependencyNeverSatisfied` check** + anti-pattern
  #13. Steps 2-5's watcher-mediated monitoring never surfaces a dependency zombie unless the watcher
  script explicitly checks for one, and Step 7's zombie-detection recipe is manual — nothing here
  re-runs it automatically after a restart. Found live: restarting a phase whose downstream was
  already queued left that downstream chained to the superseded old job ID for ~30 hours, undetected,
  until a routine PI status check caught it (`memory/dev_logs/reflection/20260816a_Reflection_Restart_Tool_Left_A_Zombie_Its_Own_Docstring_Warned_About.md`).
  Step 8 arms a third Monitor that queries `squeue` directly — independent of any watcher script,
  explicitly checking for `DependencyNeverSatisfied` on a self-chosen interval. **Deliberately does
  NOT hardcode a fixed interval** (e.g. "every hour") — the step instead states the factors that
  should set it (how recently a restart happened, the walltime ceiling in play, how many chains are
  active) per PI instruction, since a fixed number would just be trading one blind spot for another
  written in stone. Fix command references the automated cascade added the same day
  (`memory/dev_logs/20260816b_Restart_Tool_Automates_Downstream_Chain_Repair.md`). Placed as **Step
  8, appended** rather than inserted earlier and renumbering — many dev logs and two other skills
  (`offline-testing-workflow`, `restart-failed-jobs`) cite this skill's existing step numbers (1, 5,
  7) by number; renumbering would have silently broken every one of those citations.
- 2026-08-12 (b) — Added a **"Verify the actual SLURM job name before filtering by it"** subsection in
  Step 1 + **anti-pattern #12**: CIME's `case.submit` names every job `run.<case_name>`, not the bare
  case name, so a `squeue -n`/`sacct --name` filter on the bare name silently matches nothing. Two
  independently-written watchers (one new, one armed a day earlier) both filtered on the bare name and
  both logged `NOT_IN_QUEUE` on every poll for jobs that were actually `RUNNING` — caught by a direct
  `squeue -o "%j"` cross-check, not by either watcher. The older watcher had been silently non-functional
  for state-change/terminal detection for about a day. Companion cross-reference added to
  `offline-testing-workflow` Step 9d's hand-rolled-watcher requirements list (now three, was two). Full
  incident: `use_cases/ELM-FATES_Kougarok/memory/logs/20260812b_phase5_testing_r01_c01_rootfinesfrag_fix_suplphos_dose_experiment.md`.
  Signal: PI-requested `refine-skill` pass immediately after the incident and its live fix.
- 2026-08-12 (a) — Corrected the Step 1 log-location note's cross-reference: it pointed a small offline
  experiment's launcher/submitter running log at `$A2MC_SCRIPTS_DIR/<ExpName>_<date>/` (scratch),
  which was `offline-testing-workflow`'s Step 5 rule until the same-day fix there redirected it to
  `use_cases/{site}/memory/phase_results/{stem}/` (repo-tracked) — that skill's rule is authoritative
  here, this note just echoes it, so it needed updating in lockstep. See that skill's changelog for
  the full evidence (two worked examples never followed the scratch rule; a self-contradiction with
  its own restart-script placement).
- 2026-08-10 — Added **anti-pattern #11** + a **"Choosing where to launch a NEW watcher"**
  subsection in Step 1 with the concrete recipe (`hostname`, nohup layer 1 there, arm layer 2 as a
  plain local `Monitor` command, never `ssh <node> "..."` to layer 1's node): don't default a
  watcher's launch node to wherever a pre-existing process happens to already be, and don't arm
  layer 2 over SSH to that same node — both defeat the layer-1/layer-2 independence Step 5 depends
  on. Signal: PI correction — a new offline-experiment watcher was launched on `login23` purely
  because an unrelated watcher was already found running there, and layer 2 was armed via SSH to
  that same node; when NERSC drained it for maintenance, both layers died together and layer 2's
  own stall-detection never got the chance to fire. Framed around minimizing exposure (no way to
  predict node stability in advance) rather than "picking a trustworthy node" (unfalsifiable), per a
  direct follow-up correction on the first drafted wording; the Step 1 code block was added after a
  second follow-up asked whether the anti-pattern actually baked in the correct way, or only said
  what not to do — the other anti-patterns in this file either state the fix inline (this one
  originally did, in prose only) or point at a Step with a runnable recipe (Step 5's mtime check for
  #10); #11 now does the latter too. Also states explicitly that this matters *more* at ensemble
  scale (a multi-day 5000+-job campaign makes a mid-campaign maintenance event near-certain), since
  the next R1 launch batches ~5100 cases × 3 phases under the 5000-concurrent-job cap.
- 2026-08-09 — Added **watcher liveness** as a requirement of layer 2 (Step 5, new subsection + anti-pattern #10): layer 2 must verify layer 1 is alive via the poll log's mtime and emit an edge-triggered stall event, plus a forced wall-clock heartbeat, because **layer 1's failure mode is silence and silence is also its healthy state between milestones** — a bare `tail -F` cannot tell the two apart. Includes the corollary that a stalled watcher is not a stalled run (only `squeue` settles that), so the event does not invite cancelling healthy jobs. Signal: PI correction — three restarted TRANS chains ran ~25 h with a correctly nohup'd watcher whose events no `Monitor` was reading, and the recovery script's liveness check was left as one script's local good idea instead of a stated property. Framed as the general principle "a read that fails silently must never be indistinguishable from a clean result", now violated at three levels in this one workflow (gzipped log → anti-pattern #9; `sacct` outage read as completion → the Step 7 allow-list; dead watcher read as a quiet run → this entry). Companion mechanisms: `.claude/hooks/remind-arm-monitoring.py` (submission-time) and `session-start.py::hpc_jobs_in_flight()` (inherited-session); full analysis in `memory/dev_logs/reflection/20260809a_Reflection_Why_Reading_The_Skill_Was_Not_Enough.md`.
- 2026-08-08 — Added the **gzipped-completed-log rule** to Step 7 (+ anti-pattern #9), directly beside the 2026-07-12 job-id rule since it is the same operation's other failure mode: CIME gzips a run's logs when it **finishes**, so plain `grep` on them returns a silent clean no-match and every completed run reads as crash-free. Branch on the `.gz` suffix (`zgrep`); take completion from `*.elm.rh0.*.nc` restart dates, which are never compressed. Signal: a sweep of all 18 Kougarok api-43 TRANS runs reported "no lnd.log" for `p169v1/v2/v3` — the only three chains that ran to completion, and so the only ones with gzipped logs. Nearly concluded they had never run. Memory: `feedback_run_logs_may_be_gzipped`. Note `tools/diagnose_ensemble_status.py` is immune (it reads restart files, not logs).
- 2026-07-12 — Added the **job-id-scoped crash-log rule** to Step 7 (+ anti-pattern #8): inspect `e3sm.log.<jobid>.*` / `lnd.log.<jobid>.*` for a crash, **never** `grep e3sm.log.*` across the run dir — CIME keeps every prior run's logs, so a stale crashed-run log gives a false "crashed again." Cross-check `squeue` elapsed time. Signal: PI correction this session after I reported a false "CRASHED AGAIN" from a glob grep that matched the previous crash's log (the current run had passed).
- 2026-07-10 — Added an explicit **log-location note** after the Step 1 table: ensemble auto-monitor/submitter/plot logs live in the **repo-relative `tmp/`** (not `~`, not a system `/tmp`), deliberately distinct from `offline-testing-workflow` (a *small* experiment's run log goes with its case scripts). Signal: PI correction this session — ensemble-scale monitoring logs go to `tmp/`; don't over-apply the offline job-scripts convention to ensembles.
- 2026-07-06 — Added **Step 7 — Cancel zombie / dead-dependency jobs** + anti-patterns #6/#7 + two reaction-table rows (ported from demo `368cc31`, scrubbed of the Kougarok Fork-B worked example). A crashed phase in a chained (`afterok:`) case leaves un-propagated downstream zombies in `PD|Dependency` that hang any "wait-until-resolved" completion monitor.
- 2026-06-13 — Ported to `main` (v2.103, Phase 1): scrubbed for the generic public repo, added `modes:` frontmatter.
