---
name: arm-hpc-monitoring
description: Set up real-time monitoring of an active A2MC HPC ensemble or experiment on Perlmutter at session start (CLAUDE.md Rule #6). Detects live long-running login-node processes (auto-monitor, submitter, extractor) via `ps -ef`, arms Claude `Monitor` tasks on each long-running log with the right event + error filter (silence ≠ success), and reminds Claude to react with proposals rather than just relaying events. Use whenever a session begins (or resumes after compaction) while an ensemble round is in flight. Also use immediately after launching a new submitter or restart job.
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
| Milestone-crossing extracted count (e.g., 2750, 3000) | The auto-monitor's `regen_milestone_plot.sh` should fire automatically. Confirm `REGEN_LAUNCHED` events follow. If not, manually invoke `bash use_cases/Kougarok/analysis/regen_milestone_plot.sh`. |
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

**Cancel surgically** — target only the provably-dead chain by name pattern or explicit IDs; **never** blanket-`scancel -u $USER` (that kills the live variants too):

```bash
ids=$(squeue -u $USER -h -o "%i %j" | grep -E "<dead-variant-name-pattern>" | awk '{print $1}')
echo "$ids"          # eyeball the list FIRST — confirm no live variants matched
scancel $ids
```

Safety: these are your own guaranteed-non-runnable jobs, and cancellation is reversible (resubmit the chain if a fix lands). This is routine housekeeping, not a destructive act — but the *targeting* is what must be exact. Re-list the queue after canceling to confirm only the live chains remain.

## Anti-patterns

1. **Do NOT** rely on the happy-path filter alone — if the process crashes, you'll never know.
2. **Do NOT** arm a Monitor without `persistent: true` for session-length watches — a 5-minute timeout means you stop receiving events 5 min after the harness fires.
3. **Do NOT** sleep/poll to wait for monitor events. The events arrive as notifications. If you need a one-shot "wait until ready," use Bash `run_in_background` with an `until` loop instead.
4. **Do NOT** narrate every event back to the user. Acknowledge with "Normal" or silence for routine, react with proposals for threshold crossings and errors.
5. **Do NOT** assume the auto-monitor survived the previous session — Claude Monitors are session-local. A nohup'd auto-monitor script itself survives, but the *tail process* armed by `Monitor` does not. Always re-arm at session start.
6. **Do NOT** count `PD|Dependency` jobs as "still runnable" in a completion/resolution watcher without first purging zombies (Step 7) — a crashed chain leaves un-propagated dependents in `PD|Dependency` that never run, so the watcher hangs forever on a finished batch.
7. **Do NOT** use blanket `scancel -u $USER` to clear zombies — it kills the live variants too. Cancel by name pattern / explicit IDs, and eyeball the ID list before firing.

## Cross-references

- Companion restart workflow: the `restart-failed-jobs` skill.
- The interactive-agent operating contract: `AGENTS.md`.
- A site's live auto-monitor script (if any) lives under `use_cases/<site>/analysis/`.

## Changelog

- 2026-07-06 — Added **Step 7 — Cancel zombie / dead-dependency jobs** + anti-patterns #6/#7 + two reaction-table rows (ported from demo `368cc31`, scrubbed of the Kougarok Fork-B worked example). A crashed phase in a chained (`afterok:`) case leaves un-propagated downstream zombies in `PD|Dependency` that hang any "wait-until-resolved" completion monitor.
- 2026-06-13 — Ported to `main` (v2.103, Phase 1): scrubbed for the generic public repo, added `modes:` frontmatter.
