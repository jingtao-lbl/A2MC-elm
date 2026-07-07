---
name: phase5-testing
description: Run Phase 5 (TESTING) of the A2MC calibration workflow as the offline agent — the human-in-the-loop analog of the orchestrator's `_run_testing()`. Execute the hypothesis experiments as new simulation runs — modify parameter files, create + submit cases (ADSP→RGSP→TRANS), monitor, and extract results against targets. This is a thin phase-router — the end-to-end offline procedure lives in `offline-testing-workflow`. Use when the user says "run the experiment", "submit the test cases", "run Phase 5", "test this hypothesis with new simulations", after Phase 4 hands off a hypothesis that needs new simulations.
modes:
  requires_fates: false      # calibration-workflow phase skill; mode resolved at runtime via describe_mode
  nutrient_pathway: any
  scope: [calibration]
  summary: "Offline analog of Phase 5 (HPC experiment execution; routes to offline-testing-workflow). Applies in every calibration mode."
---

# Phase 5: Testing (offline agent) — router

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
3. **Log** via `calibration-log` (phase log → `PhaseLogger.log_testing` /
   `log_experiment_design`).

## Footguns (the load-bearing ones; full set in `offline-testing-workflow`)

- **Case-suffix, not new case numbers.** Experiments use `--case-suffix exp_<id>`; inventing a
  case number collides with / leaks into the Morris ensemble extract dir.
- **V0 gate before trust.** Reproduce V0 (baseline params) before reading V1+ as signal — catches
  build / param-file errors early.

## Related skills / next phase

- **The actual execution** → `offline-testing-workflow`. **Monitor** → `arm-hpc-monitoring`.
  **Restart** → `restart-failed-jobs`.
- **Next:** `phase6-refinement` (evaluate results, extract lessons, decide convergence).

## Changelog

- 2026-07-06: Added Step 0 — reset `skip_testing_count = 0` on Phase-5 entry (closes the inner loop for the
  cycle). Pairs with the Phase-6 middle-loop gate + Phase-4 inner-loop counter. Ported from demo `2d3f4b0`.
- 2026-07-02: Created — thin Phase 5 router mirroring `_run_testing()`; delegates execution to `offline-testing-workflow`, hands off to `phase6-refinement`.
