---
name: phase2-screening
description: Run Phase 2 (SCREENING) of the A2MC calibration workflow as the offline agent — the human-in-the-loop analog of the orchestrator's `_run_screening()` / `reasoning.analyze_screening_results()`. Rank the ensemble against the validation targets (RMSRE, targets-satisfied), find the best / lowest-cost / most-targets cases, read the error/bias patterns, and route the round into Phase 3 diagnosis. Use when the user says "screen the ensemble", "rank against targets", "which case is best", "run Phase 2", "how many targets are met", after Phase 1 sensitivity.
---

# Phase 2: Screening (offline agent)

The offline analog of `_run_screening()`. Online, `reasoning.analyze_screening_results()` reads the
ranked ensemble automatically; **offline, YOU read it** — identify best / lowest-cost / most-targets
cases, the per-target bias (over/under-estimate), edge parameters in the top cases, and PFT
trade-offs, then set up what Phase 3 must explain.

> **Floor, not ceiling.** Ranking + best-case is the online floor. As the offline agent, go further:
> inspect the whole cost distribution (not just top-N), test whether a "best" case is real or a
> contamination artifact before trusting it, look for equifinality (different parameter sets, same
> cost), or compare this round's frontier against a prior round. Produce the online ranking, then
> interrogate it.

**Inputs (from Phase 1):** extracted per-case data + Morris rankings. **Deliverable:** ranked cases
(RMSRE + targets satisfied), the best/lowest-cost/most-targets cases, error-pattern read → routed to
`phase3-diagnosis`.

## Step 1 — rank the ensemble (reads existing extracted outputs — no new simulations)

`phases/phase2_screening/screen_ensemble.py --data-dir $A2MC_EXTRACTED_DATA --top-n 100`. Per-target
relative error → composite RMSRE via `tools/optimize_function.py` / `tools/cost_functions.py`
(shared `tools/evaluate_case.py`); counts targets within tolerance (default ±20%). Outputs ranked
indices, composite cost, per-target errors, `n_satisfied`.

> **Footgun — `--max-case-num` contamination guard.** When experiment cases (e.g. `_exp` / #5001+)
> share the extract dir with the Morris ensemble, pass `--max-case-num 4890` so screening ranks
> only the ensemble. Without it, foreign cases inflate the top-N. (Same guard the
> `compare-calibration-rounds` cap enforces.)

> **Footgun — index vs case number.** Screening `Set_ID`/indices can be *position+1*, not the real
> case number. Use the JSON `best_case_num` + the `_results.txt` `Sim_` columns, not the indices
> file, before quoting a "best case" (see `diagnose-forensics`).

## Step 2 — read the patterns (you are the reasoning)

Mirror `analyze_screening_results`: **pft_performance** (cases within uncertainty, quality),
**target_bias** (UNDEREST/OVEREST + consistency), **edge_parameters** (top cases pinned at bounds),
**pft_tradeoffs** (shared-parameter conflicts), **priority_targets** for diagnosis. Optional QA:
`phases/phase2_screening/compare_biomass_topcases.py --top-n 50` (top-N biomass vs targets panel).

## Step 3 — log and route

Log via `calibration-log` (phase log → `PhaseLogger.log_screening`): best/lowest-cost/most-targets
cases, targets met, bias patterns, priority targets. **Route** to `phase3-diagnosis` with the
priority targets + candidate base cases.

## Related skills / next phase

- **Canned single-round report (graphs + eval + μ*)** → `summarize-calibration-round`.
  **Cross-round frontier** → `compare-calibration-rounds`. This skill *decides + routes*; those
  *render*.
- **A "best" case looks too good** → `diagnose-forensics` (triage before trusting).
- **Next:** `phase3-diagnosis`.

## Changelog

- 2026-07-02: Created — offline Phase 2 routine mirroring `reasoning.analyze_screening_results()`; drives screen_ensemble, delegates figures to summarize-/compare-calibration-round, routes to `phase3-diagnosis`.
