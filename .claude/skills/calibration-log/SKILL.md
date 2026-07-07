---
name: calibration-log
description: Log interactive calibration work for a site under use_cases/{site}/memory/logs/. Two log types — a PHASE log (a diagnosis, screening, experiment design/result, refinement — recorded the same way the autonomous agent does, via PhaseLogger, so both modes' logs synthesize together) or a free-form SESSION log (exploratory work that does not map to a specific phase). Use when the user wants to record calibration or exploration work — "log this", "log this phase / diagnosis / experiment", "log this calibration session", "write a session log", "record what I explored".
modes:
  requires_fates: false      # logging convention; model-agnostic (PhaseLogger)
  nutrient_pathway: any
  scope: [logging]
  summary: "Site calibration/exploration logging via PhaseLogger; applies in every mode."
---

# Log Calibration Work (phase log or free-form session log)

Records the interactive agent's calibration/exploration work for a site under
`use_cases/{site}/memory/logs/`, so it lives alongside the autonomous agent's logs and
`tools/session_report.py` / synthesis reporting can process everything for a session together.

## Step 1 — pick the log type

| Type | When | How it is written |
|------|------|-------------------|
| **phase log** | The work maps to a Phase 0–7 activity (diagnosis, screening, experiment design/result, refinement, …) | `PhaseLogger` — identical format/naming to the autonomous agent |
| **session log** | Free-form / exploratory work that does **not** follow the phases exactly (an ad-hoc analysis, a data check, an idea) — which is fine | a plain dated note using the `YYYYMMDDx_Topic.md` convention |

Both land under the same session directory `use_cases/{site}/memory/logs/{stamp}/`, so synthesis
sees one session in one place. `{stamp}` = the orchestrator `session_id` (`YYYYMMDD_HHMMSS`) when a
run is active, otherwise a date stamp for the interactive session.

## Type A — phase log (via PhaseLogger)

Don't hand-roll the format; call `tools/phase_logger.py` so the output matches the autonomous
agent byte-for-byte.

```python
# source a2mc_config.sh + use_cases/{site}/config/{site}_config.sh first
from tools.phase_logger import create_logger

logger = create_logger()                 # resolves site dir from A2MC_USE_CASE_DIR
logger.set_iteration_context(            # the three-level counters (see CLAUDE.md)
    calibration_round=<round>,           # RR — outermost loop
    experiment_count=<exp_cycle>,        # EE — middle loop
    skip_testing_count=<skip>,           # inner loop (Phase 3/4 only)
)
logger.log_diagnosis(title="PFT10 Fineroot Root-Cause", content=<markdown>, ...)
```

Per-phase methods: `log_design` (0), `log_exploration` (1), `log_screening` (2),
`log_diagnosis` (3), `log_hypothesis` (4) / `log_experiment_design`, `log_testing` (5),
`log_refinement` (6). Each applies the right section template from `templates/logging/`.

Lands at:
```
use_cases/{site}/memory/logs/{stamp}/phase{N}_{name}/
    Phase 0–2 : r{RR}_{stamp}_Title.md
    Phase 3–6 : r{RR}_c{EE}_iter{II}_{stamp}_Title.md
```
`RR` = `calibration_round`, `EE` = `experiment_count`, `II` = `skip_testing_count + 1` (Phase 3/4).
Full convention: `CLAUDE.md` §"Session Logging Convention" and the `tools/phase_logger.py` header.

**Offline (interactive-agent) layout — optional (docs/31).** When there is no orchestrator run /
`session_id` and you're working continuously by *topic* rather than by run, set
`A2MC_AGENT_MODE=offline` (or `create_logger(...)` with `agent_mode='offline'`). `PhaseLogger` then
writes a **date-led flat topic-stem** instead — `logs/{stem}.md` with
`stem = YYYYMMDDx_phase{N}_{name}_r{RR}[_c{EE}[_iter{II}]]_{descriptor}` — and `topic_artifact_dir()`
gives the paired `phase_results/{stem}/` for figures/data. Track progress in the per-round
`workflow_state_offline_r{RR}.json` (`tools/workflow_state_offline.py`). The **online path is
unchanged**; this only switches on for the interactive agent. `session_report.collect_session_artifacts(include_offline=True)`
folds these flat logs into synthesis alongside session-scoped ones.

**Evidence gate for analysis-phase logs (docs/33).** A diagnosis/hypothesis/refinement (phase 3/4/6) log must
cite a **first-hand artifact produced this session** (a script/figure/data file in the paired
`phase_results/{stem}/` or `phases/*/generated/`), not just restate a prior log. After writing one, run
`python tools/check_offline_log_evidence.py <log.md>` — it must exit 0. See
`feedback_offline_logs_need_first_hand_analysis`.

## Type B — session log (free-form)

For exploratory work that doesn't fit a phase. Write a plain dated markdown note at the **session
root** (no `phase{N}` subdir):
```
use_cases/{site}/memory/logs/{stamp}/YYYYMMDDx_Topic.md
```
- `YYYYMMDDx` = date + a sequential letter (`a`, `b`, `c`, … for same-day notes — check existing
  files so you don't reuse a letter), `Topic` = Title_Case with underscores.
- Keep it light: a short header (**Date**, **Author**, **Type:** exploration/analysis) followed by
  free-form reasoning — what you looked at, what you found, evidence (cite specific cases/values),
  and any open question. No fixed section list; it is a working note, not a phase deliverable.

## Notes

- These are **run-state** logs (site-specific calibration data) — not synced to the public demo.
  The value is local synthesis across a session.
- Do **not** re-implement the phase naming/section logic here; it lives in `tools/phase_logger.py`
  and this skill follows it.

## Changelog

- 2026-07-06: Added the offline (interactive-agent) topic-stem layout note now that `PhaseLogger`
  offline mode landed on main (v2.115, docs/31): `A2MC_AGENT_MODE=offline` → flat `logs/{stem}.md` +
  `phase_results/{stem}/` + per-round `workflow_state_offline`. Generic; online path unchanged.
- 2026-07-01: Created — public skill so the interactive agent logs calibration work the same way
  the autonomous agent does (phase logs) plus a free-form session-log option for exploratory work.
