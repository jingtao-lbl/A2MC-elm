---
name: phase1-exploration
visibility: public
category: phase
description: Run Phase 1 (EXPLORATION) of the A2MC calibration workflow as the offline agent — the human-in-the-loop analog of the orchestrator's `_run_exploration()` / `reasoning.analyze_sensitivity_results()`. Extract the Y matrix from completed simulations, run Morris sensitivity analysis, and interpret μ* to decide what parameters matter for each target/PFT. Use when the user says "run the sensitivity analysis", "extract the Y matrix", "which parameters matter", "run Phase 1", "Morris rankings", after the Phase 0 ensemble finishes.
modes:
  requires_fates: false      # calibration-workflow phase skill; mode resolved at runtime via describe_mode
  nutrient_pathway: any
  scope: [calibration]
  summary: "Offline analog of Phase 1 (extract Y matrix, Morris sensitivity). Applies in every calibration mode."
---

# Phase 1: Exploration (offline agent)

> **Driven by `calibration-goal`** — the run-to-convergence driver dispatches here when `WorkflowStateOffline.current_phase` routes to this phase; do the phase, then update + `save()` the state so the driver advances. Also runnable standalone (one phase).

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

> **The per-PFT μ* ranking plot is a REQUIRED deliverable, not a byproduct** — include it in the phase
> log with a caption naming the top parameters ([[feedback_figures_over_tables_over_words]]). For the
> cross-target μ* overlay (one panel per validation target) use `summarize-calibration-round`; for a
> per-target μ* comparison across rounds use `compare-calibration-rounds`.

## Step 3 — interpret (you are the reasoning)

Produce the same shape as the online `analyze_sensitivity_results` output: **key_parameters**
(each attributed to a FATES mechanism — verify against RAG, never from the name), **interactions**
(high σ/μ*), **cross_pft_patterns** (generic-to-all vs PFT-specific), **edge_effects** (near-bound →
redesign candidates), and a **calibration strategy** (tune order, PFT-by-PFT vs global).

## Step 4 — log and hand off

> **The log is a LIVING record — start it now, enrich as the phase runs.** Not an end-of-phase
> write-up: the operational detail (job/array IDs, which cases failed, what was restarted) is
> unrecoverable a week later. Full contract in `calibration-log`.
>
> **This phase's expected sections** — `PhaseLogger` names any you leave empty:
> Extraction Status · Y Matrix · Morris Results · Interpretation.
>
> **Set the handshake before the `log_*` call**, so the chain is traceable:
> ```python
> logger.set_phase_handshake(
>     inherited_from="<predecessor log STEM> — what it concluded / asked of this phase",
>     handed_to="<what Phase 2 receives; mirror the reasoning/schemas.py field names>",
>     next_action="<the one concrete thing Phase 2 should do>")
> ```
> The log also carries `## Reasoning chain`, rebuilt from `workflow_state_offline` — so keep that
> state updated with the FINDING, not a label; the chain is only as good as what each phase wrote.


Log via `calibration-log` (phase log → `PhaseLogger.log_exploration`): top parameters per PFT, the
mechanism attributions, edge effects, and the tuning recommendation. **Hand off** to
`phase2-screening`. **Advance the driver state:** `st.set_position(current_phase="screening")`;
`st.save()` (`tools/workflow_state_offline.py`).

## Before you finish

**Discipline self-review (automatic).** Before advancing the state, re-check the [`calibration-discipline`](../calibration-discipline/SKILL.md) items that apply to this phase. This is unprompted and per-phase — the user does not have to ask (memory `feedback_schedule_periodic_reviews_with_a_real_mechanism`).

## Related skills / next phase

- **Standardized single-round / cross-round figures** → `summarize-calibration-round`,
  `compare-calibration-rounds` (they invoke the same Morris pipeline).
- **A one-off sensitivity question with a figure + ana_log** → `scientific-analysis`.
- **Next:** `phase2-screening` (rank the ensemble against targets).

## Changelog

- 2026-08-03: Log step now states the **living-record** contract (start at phase start, enrich as it
  runs — the operational detail is unrecoverable later), names **this phase's expected sections** so an
  omission is visible in the log, and shows `set_phase_handshake()` so the reasoning chain is traceable.
  Added a **Before you finish** discipline self-review. Full contract: `calibration-log`.
- 2026-07-15: Wired the explicit `set_position(current_phase="screening")` state-advance in the handoff step. Ported from demo `d3cbbf5` (offline-workflow enforcement sweep).
- 2026-07-15: Made the **per-PFT μ* ranking plot a named REQUIRED deliverable** (not a byproduct) in Step 2, with cross-target/cross-round μ* overlays pointed at `summarize-`/`compare-calibration-rounds`. Ported from demo `cd14d24`.
- 2026-07-02: Created — offline Phase 1 routine mirroring `reasoning.analyze_sensitivity_results()`; drives extract_sensitivity_outputs → morris_sensitivity_analysis, hands off to `phase2-screening`.
