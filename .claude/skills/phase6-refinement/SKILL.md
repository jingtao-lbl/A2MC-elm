---
name: phase6-refinement
description: Run Phase 6 (REFINEMENT) of the A2MC calibration workflow as the offline agent — the human-in-the-loop analog of the orchestrator's `_run_refinement()` / `reasoning.interpret_results()` + `extract_lesson()`. Evaluate the experiment results vs baseline + expected outcomes, extract lessons (discoveries / failed approaches), update Adaptive Memory, and decide convergence: converged, rethink (6→3), or redesign (6→0). Use when the user says "evaluate the results", "did the experiment work", "extract the lessons", "run Phase 6", "should we converge or iterate", "what did we learn", after Phase 5 testing.
---

# Phase 6: Refinement (offline agent)

The offline analog of `_run_refinement()`. Online, `reasoning.interpret_results()` +
`extract_lesson()` evaluate and learn automatically; **offline, YOU do both** — judge the experiment
honestly against expectation, name the mechanism you learned, and decide where the loop goes next.

> **Floor, not ceiling.** The online agent classifies confirmed/partial/rejected and picks the next
> phase. As the offline agent you can do the deeper work the loop can't: a full equifinality /
> cross-regime analysis (`scientific-analysis`), a manuscript figure, reconciling this result with
> prior rounds (`compare-calibration-rounds`), or deciding a finding is worth curating into the KB.
> Evaluate at least as rigorously as the online agent, then reason past it.

**Critical mode difference — the memory write gate.** The online agent runs Memory in **propose**
mode (stages to `auto_discovered_pending.json`, cannot write curated knowledge). **You, the offline
agent, are the disposer** — you write curated knowledge directly (interactive mode) and you promote
the online agent's staged proposals. "Online proposes, offline disposes." This is *the* thing Phase 6
does differently offline.

**Inputs (from Phase 5):** experiment results (per-target metrics, extraction status) + the Phase 4
expected outcomes. **Deliverable:** honest per-hypothesis verdict, lessons written to Memory, a
convergence decision.

## Step 1 — evaluate the results (reads existing experiment results — no new simulations)

`phases/phase6_refinement/evaluate_results.py` compares each experiment to expected outcomes and to
the Phase 2 baseline → outcome class (SUCCESS / PARTIAL / MARGINAL / FAILED), best experiment,
targets met.

> **Footgun — data-reliability gate.** A *silent* extraction failure (no error, empty metrics) reads
> as 0/6 targets and looks like a real FAILED result. Confirm `extraction_status == "extracted"` AND
> non-empty metrics AND no `error` before trusting any outcome — otherwise you contaminate the KB
> with a phantom failure.

## Step 2 — interpret + extract lessons (you are the reasoning)

Mirror `interpret_results` (targets improved/degraded, hypothesis_status **honestly** — partial is
PARTIAL, not SUCCESS; cross-PFT impact) and `extract_lesson` (is it a **discovery**? a **failed
approach**? a named pattern — Allocation Paradox, Perfect Storm, Mortality Trap?). Verify any
mechanism against RAG before asserting it.

## Step 3 — update Adaptive Memory (offline = curated, direct)

- **Vetted new discovery / failed approach you originated** → write it via `inject-knowledge`
  (interactive mode writes the curated JSON directly through `memory/manager.py`).
- **The online agent's staged proposals** (`auto_discovered_pending.json`) → review + promote/discard
  via `curate-knowledge` (`tools/review_pending_knowledge.py`). This is the Tier-3 write gate.

## Step 4 — decide where the loop goes

- **All targets met** → converged (Phase 7); write the final config + round summary.
- **Not met, hypothesis disproven / more to try, cycles remain** → **6→3 rethink**: back to
  `phase3-diagnosis` for the next experiment cycle.
- **Not met, candidates pinned at bounds / space too narrow** → **6→0 redesign**: back to
  `phase0-design` with widened bounds (a new `calibration_round`).

## Step 5 — log, report, hand off

Log via `calibration-log` (phase log → `PhaseLogger.log_refinement`). Standardized reporting:
`summarize-calibration-round` (this round) / `compare-calibration-rounds` (vs prior). Then route per
Step 4.

## Related skills / next phase

- **Curate staged proposals** → `curate-knowledge`. **Inject a vetted finding** → `inject-knowledge`.
- **Deeper investigation / figure** → `scientific-analysis`. **Round reports** →
  `summarize-calibration-round`, `compare-calibration-rounds`.
- **Next:** converged (Phase 7), or loop to `phase3-diagnosis` (rethink) / `phase0-design` (redesign).

## Changelog

- 2026-07-02: Created — offline Phase 6 routine mirroring `interpret_results()` + `extract_lesson()`; encodes the offline "disposer" write gate (direct curated writes + promote staged proposals), delegates memory to curate-/inject-knowledge, reporting to summarize-/compare-calibration-round.
