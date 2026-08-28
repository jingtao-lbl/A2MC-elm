---
name: phase5-testing
visibility: public
category: phase
description: Run Phase 5 (TESTING) of the A2MC calibration workflow as the offline agent — the human-in-the-loop analog of the orchestrator's `_run_testing()`. Execute the hypothesis experiments as new simulation runs — modify parameter files, create + submit cases (ADSP→RGSP→TRANS), monitor, and extract results against targets. This is a thin phase-router — the end-to-end offline procedure lives in `offline-testing-workflow`. Use when the user says "run the experiment", "submit the test cases", "run Phase 5", "test this hypothesis with new simulations", after Phase 4 hands off a hypothesis that needs new simulations.
modes:
  requires_fates: false      # calibration-workflow phase skill; mode resolved at runtime via describe_mode
  nutrient_pathway: any
  scope: [calibration]
  summary: "Offline analog of Phase 5 (HPC experiment execution; routes to offline-testing-workflow). Applies in every calibration mode."
---

# Phase 5: Testing (offline agent) — router

> **Driven by `calibration-goal`** — the run-to-convergence driver dispatches here when `WorkflowStateOffline.current_phase` routes to this phase; on an HPC submit, arm monitors + take the WAIT stop (the Monitor event resumes the driver). Also runnable standalone (one phase).

The offline analog of `_run_testing()`. **The full offline procedure is `offline-testing-workflow`**
— this phase skill exists so the Phase 0–6 set is complete and to route you there with the phase
framing intact. Do not reimplement experiment execution here.

> **Floor, not ceiling.** The online Phase 5 runs exactly the experiments Phase 4 designed. As the
> offline agent you can add variants, a wider sweep, an extra control, or a second base case the
> fixed loop wouldn't — `offline-testing-workflow` is built for exactly that latitude (N variants,
> V0 gate, decision tree). Run at least the designed experiment; design more when it's warranted.

**Inputs (from Phase 4):** the hypothesis / experiment design + selected base case.
**Deliverable:** experiment results (per-target metrics vs baseline) → handed to Phase 6.

## Do this

0. **On Phase-5 entry, reset `skip_testing_count = 0`** in `workflow_state_offline_r{RR}.json`. Entering
   Phase 5 commits this experiment cycle to an HPC test and closes the inner (skip-test) loop, which counts
   within one cycle only. (`experiment_count` is unchanged here — it advances on the Phase 6→3 route.) The
   online orchestrator does this reset in code; offline, do it by hand.
1. **Invoke `offline-testing-workflow`** — it owns the whole path end-to-end: variant design,
   parameter-file generation via `tools/modify_fates_parameters.py` (+ `verify_modifications()`),
   case creation via `tools/create_case.sh --case-suffix` (the `_exp` convention — NEVER invent
   out-of-Morris case numbers), submission, the **V0 reproducibility gate** (validate the first
   completed variant before trusting V1+), extraction, and analysis. The corresponding phase
   scripts are `phases/phase5_testing/design_experiments.py`, `submit_experiments.py`,
   `monitor_experiments.py`.
2. **Monitor** the in-flight experiment → `arm-hpc-monitoring`. **Failed jobs** → distinguish
   infrastructure (restart-eligible) from model failures via `restart-failed-jobs`.
2b. **ARCHIVE THIS PHASE'S JOB SCRIPTS** into `phase_results/{stem}/` (a `submit_scripts/`
   subfolder once there are more than a couple), and **record which BINARY each run was bound to**.
   **Copy, never move** — the scheduler reads the operative copy from the run directory. Do it as
   soon as the scripts are final, not at Phase 6.

   **Why this is a step, not housekeeping.** The run directory is untracked scratch that gets
   cleaned, and the submit script is the only durable record of what actually ran. A case's
   `EXEROOT` lives in its `env_build.xml` under `CIME_OUTPUT_ROOT` — also scratch — so a log stating
   "V0 gate PASS" with no archived script and no binary identity **cannot show which executable
   produced the number**. Record the `md5sum` of each `e3sm.exe`, not just its path: the path is the
   part that disappears.

   Worked example on this branch: `phase_results/20260820a_*/BINARY_PROVENANCE.md`, written for the
   `PhosphorusBiochemMin_balance` perf pairs. That whole result rests on `v0base`/`v0fix` being
   different builds; `cmp` confirmed it at submission, but the confirmation lived only in a session
   transcript until the md5s were written down.

   > **Phase 0 is deliberately EXEMPT.** Its job scripts are generated from the machine + round
   > config by the materializer, and an ensemble is thousands of cases — archiving them would be
   > enormous and redundant, since the config plus the generator reproduces them exactly. Phase 5
   > differs in kind, not degree: its handful of variants are hand-designed and hand-repointed onto
   > a specific binary, so nothing else records what ran.

3. **Log** via `calibration-log` (phase log → `PhaseLogger.log_testing` /
   `log_experiment_design`).
4. **Advance the driver state** once results are extracted: `st.set_position(current_phase="refinement")`;
   `st.save()` (`tools/workflow_state_offline.py`) so `resolve_next_action` resolves Phase 6.

## Log it as a LIVING record

`offline-testing-workflow` owns the mechanics; **the log is still yours**, and it starts when the
variants are submitted, not when the results land. The operational detail — job/array IDs, which
variants failed when the scheduler hiccupped, what was restarted — is unrecoverable a week later.
Full contract in `calibration-log`.

**Phase 5's expected sections** — `PhaseLogger` names any you leave empty:
Experiments Designed · Submission · Simulation Status · Monitoring Armed · Failures and Restarts · V0 Reproducibility Gate · Results Preview · Results Summary.

**Results Preview** is the load-bearing one: before trusting any result, show that each new test came
out sane. It pairs with the **V0 reproducibility gate** — V0 proves the variant reproduces its base,
the preview proves the variant itself is not nonsense.

```python
logger.set_phase_handshake(
    inherited_from="<phase4 log STEM> — the hypothesis + its success_criteria bar",
    handed_to="experiment results vs the bar (Phase 6 rules CONFIRMED/REFUTED against it)",
    next_action="<the one concrete thing Phase 6 should evaluate>")
```

## Footguns (the load-bearing ones; full set in `offline-testing-workflow`)

- **Case-suffix, not new case numbers.** Experiments use `--case-suffix exp_<id>`; inventing a
  case number collides with / leaks into the Morris ensemble extract dir.
- **V0 gate before trust.** Reproduce V0 (baseline params) before reading V1+ as signal — catches
  build / param-file errors early.

## Before you finish

**Discipline self-review (automatic).** Before advancing the state, re-check the [`calibration-discipline`](../calibration-discipline/SKILL.md) items that apply to this phase. This is unprompted and per-phase — the user does not have to ask (memory `feedback_schedule_periodic_reviews_with_a_real_mechanism`).

## Related skills / next phase

- **The actual execution** → `offline-testing-workflow`. **Monitor** → `arm-hpc-monitoring`.
  **Restart** → `restart-failed-jobs`.
- **Next:** `phase6-refinement` (evaluate results, extract lessons, decide convergence).

## Changelog

- 2026-08-23 — Added **Step 2b: archive this phase's job scripts, and record which BINARY each run was bound to**. Adopted from `adapter-kit` (`74e81e88` as corrected by `d77950da`), re-authored. Taken at the corrected state: the rule first covered Phase 0 too and was withdrawn for it within the hour, because an ensemble's scripts are config-generated and number in the tens of thousands. Main already archived its `run_*.sh` by habit but had no rule and, more importantly, **no record of binary identity** — `EXEROOT` lives in scratch, so the `PhosphorusBiochemMin` perf verdict rested on a `cmp` that existed only in a session transcript. Fixed retroactively in `phase_results/20260820a_*/BINARY_PROVENANCE.md`.

- 2026-08-03: Log step now states the **living-record** contract (start at phase start, enrich as it
  runs — the operational detail is unrecoverable later), names **this phase's expected sections** so an
  omission is visible in the log, and shows `set_phase_handshake()` so the reasoning chain is traceable.
  Added a **Before you finish** discipline self-review. Full contract: `calibration-log`.
- 2026-07-15: Wired the Step-4 `set_position(current_phase="refinement")` state-advance (once results are extracted, so `resolve_next_action` resolves Phase 6). Ported from demo `d3cbbf5` (offline-workflow enforcement sweep).
- 2026-07-06: Added Step 0 — reset `skip_testing_count = 0` on Phase-5 entry (closes the inner loop for the
  cycle). Pairs with the Phase-6 middle-loop gate + Phase-4 inner-loop counter. Ported from demo `2d3f4b0`.
- 2026-07-02: Created — thin Phase 5 router mirroring `_run_testing()`; delegates execution to `offline-testing-workflow`, hands off to `phase6-refinement`.
