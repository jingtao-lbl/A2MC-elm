---
name: arm-hpc-monitoring
description: Set up real-time monitoring of an active A2MC HPC ensemble or experiment on Perlmutter at session start (CLAUDE.md Rule #6). Detects live long-running login-node processes (auto-monitor, submitter, extractor) via `ps -ef`, arms Claude `Monitor` tasks on each long-running log with the right event + error filter (silence ≠ success), and reminds Claude to react with proposals rather than just relaying events. Use whenever a session begins (or resumes after compaction) while an ensemble round is in flight. Also use immediately after launching a new submitter or restart job.
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
| `FAILED` / `Traceback` / `MaxJobsExceeded` / `Killed` / `OOM` | **Stop. Investigate.** Pull recent log context, identify the source process, propose remediation (often: scancel zombies, restart submitter, or invoke the `restart-failed-jobs` skill). |

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

## Anti-patterns

1. **Do NOT** rely on the happy-path filter alone — if the process crashes, you'll never know.
2. **Do NOT** arm a Monitor without `persistent: true` for session-length watches — a 5-minute timeout means you stop receiving events 5 min after the harness fires.
3. **Do NOT** sleep/poll to wait for monitor events. The events arrive as notifications. If you need a one-shot "wait until ready," use Bash `run_in_background` with an `until` loop instead.
4. **Do NOT** narrate every event back to the user. Acknowledge with "Normal" or silence for routine, react with proposals for threshold crossings and errors.
5. **Do NOT** assume the auto-monitor survived the previous session — Claude Monitors are session-local. The Perlmutter `r5_auto_monitor.sh` itself is nohup'd and survives, but the *tail process* armed by `Monitor` does not. Always re-arm at session start.

## Cross-references

- CLAUDE.md branch operating rule #6 (this skill's source)
- Canonical workflow: `memory/dev_logs/20260514c_Monitoring_Workflow_Pattern_For_HPC_Ensembles.md`
- Companion restart workflow: `restart-failed-jobs` skill
- Auto-memory: `feedback_arm_monitor_at_session_start.md`, `feedback_plot_filename_convention.md`
- Today's worked example of filter-tightening: `memory/dev_logs/20260522b_*.md` Part 3
- Live auto-monitor source: `use_cases/Kougarok/analysis/r5_auto_monitor.sh`

## Changelog

- 2026-06-17: `## Changelog` convention adopted (see .claude/skills/README.md). Earlier history: git log + memory/dev_logs/.
