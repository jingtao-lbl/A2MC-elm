---
name: phase1-exploration
description: Run Phase 1 (EXPLORATION) of the A2MC calibration workflow as the offline agent — the human-in-the-loop analog of the orchestrator's `_run_exploration()` / `reasoning.analyze_sensitivity_results()`. Extract the Y matrix from completed simulations, run Morris sensitivity analysis, and interpret μ* to decide what parameters matter for each target/PFT. Use when the user says "run the sensitivity analysis", "extract the Y matrix", "which parameters matter", "run Phase 1", "Morris rankings", after the Phase 0 ensemble finishes.
modes:
  requires_fates: false      # calibration-workflow phase skill; mode resolved at runtime via describe_mode
  nutrient_pathway: any
  scope: [calibration]
  summary: "Offline analog of Phase 1 (extract Y matrix, Morris sensitivity). Applies in every calibration mode."
---

# Phase 1: Exploration (offline agent)

The offline analog of `_run_exploration()`. Online, `reasoning.analyze_sensitivity_results()`
interprets the Morris output automatically; **offline, YOU interpret it** — attribute each ranked
parameter to a FATES mechanism, spot cross-PFT vs PFT-specific importance, and decide what's worth
tuning. The extraction + Morris scripts are the same the online agent uses.

> **Floor, not ceiling.** Morris μ* is the online agent's one lens. As the offline agent, reach for
> more when the round warrants it: check σ/μ* for interaction-heavy parameters, look for edge
> effects (params pinned near bounds → a Phase 0 redesign signal), compute a second output variable
> the loop didn't rank, or run a targeted correlation `scientific-analysis` the fixed pipeline has
> no step for. Produce the ranking the online agent would, then go past it.

**Inputs (from Phase 0):** completed TRANS outputs, the X matrix (`$A2MC_ENSEMBLE_MATRIX_FILE`), the
SALib problem (`$A2MC_SALIB_PROBLEM_FILE`). **Deliverable:** Morris rankings (μ, μ*, σ per parameter
per PFT) as CSV + plots, plus your interpretation of what to tune (captured in the phase log), handed to Phase 2.

## Step 0 — completion gate

`tools/diagnose_ensemble_status.py --cases 1-N` — proceed when >95% of cases have TRANS complete.
Failed cases become NaN rows downstream.

## Step 1 — extract the Y matrix (reads existing outputs — no new simulations)

`phases/phase1_exploration/extract_sensitivity_outputs.py --output-var leaf_biomass --cases 1-N
--validation-period 2010 2019` → `Morris{Var}_{N}cases.txt` (cases × PFTs). Runs on the login node;
large ensembles can be memory-heavy — extract in `--cases` ranges, and use `--resume` to continue an
interrupted run.

> **Footgun — row-order alignment.** The X-matrix row order MUST match the Y-matrix row order (same
> cases, same order) or SALib Morris is meaningless. If you filter failed cases, filter both sides
> with `completed_cases_<TS>.txt`. Audit for NaN rows — >5% NaN, investigate failures first.

## Step 2 — run Morris (analysis of the extracted matrices — no new simulations)

`phases/phase1_exploration/morris_sensitivity_analysis.py --output-var leaf_biomass --y-matrix <Y>
--x-matrix <X> --problem <salib_problem>` → per-PFT `morris_*.csv` (parameter, μ, μ*, σ, rank) +
color-coded `*.png`. `analyze_ensemble.py` is the higher-level driver that chains extract → Morris.

## Step 3 — interpret (you are the reasoning)

Produce the same shape as the online `analyze_sensitivity_results` output: **key_parameters**
(each attributed to a FATES mechanism — verify against RAG, never from the name), **interactions**
(high σ/μ*), **cross_pft_patterns** (generic-to-all vs PFT-specific), **edge_effects** (near-bound →
redesign candidates), and a **calibration strategy** (tune order, PFT-by-PFT vs global).

## Step 4 — log and hand off

Log via `calibration-log` (phase log → `PhaseLogger.log_exploration`): top parameters per PFT, the
mechanism attributions, edge effects, and the tuning recommendation. **Hand off** to
`phase2-screening`.

## Related skills / next phase

- **Standardized single-round / cross-round figures** → `summarize-calibration-round`,
  `compare-calibration-rounds` (they invoke the same Morris pipeline).
- **A one-off sensitivity question with a figure + ana_log** → `scientific-analysis`.
- **Next:** `phase2-screening` (rank the ensemble against targets).

## Changelog

- 2026-07-02: Created — offline Phase 1 routine mirroring `reasoning.analyze_sensitivity_results()`; drives extract_sensitivity_outputs → morris_sensitivity_analysis, hands off to `phase2-screening`.
