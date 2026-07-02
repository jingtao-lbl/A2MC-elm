---
name: phase4-hypothesis
description: Run Phase 4 (HYPOTHESIS) of the A2MC calibration workflow as the offline agent — the human-in-the-loop analog of the orchestrator's `_run_hypothesis()` / `reasoning.generate_hypothesis()`. Turn a Phase 3 diagnosis into specific, testable hypotheses with parameter changes + expected outcomes, and FIRST try to test them against the existing Morris ensemble (skip-testing — reads existing data, no new simulations) before committing to a Phase 5 experiment. Use when the user says "generate a hypothesis", "what should we test next", "design the experiment", "can we test this with existing data", "run Phase 4", after Phase 3 diagnosis.
---

# Phase 4: Hypothesis (offline agent)

The offline analog of `_run_hypothesis()`. Online, `reasoning.generate_hypothesis()` proposes the
hypothesis and decides `test_with_existing`; **offline, YOU do both** — frame a mechanistic,
falsifiable hypothesis with concrete parameter moves and expected target directions, then decide
whether the existing ensemble can already answer it.

> **Floor, not ceiling.** The online agent proposes one hypothesis per diagnosis, bounded by its
> prompt. As the offline agent you can generate + weigh several, bring in literature or satellite
> evidence (`offline-testing-workflow` Steps 1–4), design a sharper falsification test, or invent a
> skip-test the fixed loop has no method for. Match the discipline (diversity vs prior experiments,
> honor failed approaches, quantified success criteria), then reason more widely.

**Inputs (from Phase 3):** ranked root causes, implicated parameters, selected base cases.
**Deliverable:** a `Hypothesis` (name, mechanism, parameter moves with bounds, expected outcomes,
success criteria, confidence) + a routing decision: skip-test now, or queue a Phase 5 experiment.

## Step 1 — generate the hypothesis (you are the reasoning)

Mirror the `Hypothesis` schema (`reasoning/schemas.py`): **name**, **mechanism** (verify against RAG,
never from a param name), **parameters** (list of `{name, current, proposed, rationale}`, plus
`pft` / `organ` / `bounds` when relevant — FATES names; 2-organ params need dual leaf+fineroot
entries), **design_type** (`cumulative` or `factorial`), **expected_outcomes** + **success_criteria**
(quantified, e.g. "leaf_pft9 within 20%"), **confidence**. Must target a *different* mechanism
from previous experiments (check Memory failed approaches — do not re-propose a known failure).

## Step 2 — can existing data test it? (skip-testing inner loop, Phase 3↔4)

If the hypothesis is answerable from the **existing** Morris ensemble — a correlation, a high-vs-low
group contrast, a threshold, or a custom test — set `test_with_existing=true` and run it via
`phases/phase4_hypothesis/test_with_existing_data.py` (methods: comparison / correlation / threshold
/ diagnostic / custom_script). This is the 3↔4 inner loop: accumulate the evidence, and either

- **confidence ≥ threshold** (or the pattern is clear) → conclude without new simulations; or
- **feed the insight back to `phase3-diagnosis`** and refine the next hypothesis (loop), until
  confidence is high or the cycle cap is hit.

> **Footgun — untestable in range.** If the hypothesis needs parameter values *outside* the Morris
> sampled range, existing data can't test it — go straight to Phase 5. Don't force a skip-test that
> the ensemble can't actually answer.

`phases/phase4_hypothesis/synthesis.py` consolidates multi-cycle skip-testing insights into
experiment designs when you exit the loop toward Phase 5.

## Step 3 — needs new simulations? design the experiment → Phase 5

If it can't be answered with existing data, the hypothesis becomes a parameter-sweep experiment.
**Hand off to `offline-testing-workflow`** (the offline Phase 5) — it owns variant design, param-file
generation + verification, the V0 reproducibility gate, submission, and analysis. Invoke
`phase5-testing` for the phase-level routing.

## Step 4 — log and hand off

Log via `calibration-log` (phase log → `PhaseLogger.log_hypothesis`): the hypothesis, parameter
moves, skip-test evidence + verdict, and the routing decision. **Hand off** to `phase5-testing` (new simulations)
or back to `phase3-diagnosis` (another skip-test cycle).

## Related skills / next phase

- **Experiment execution (the new-simulation path)** → `offline-testing-workflow` / `phase5-testing`.
- **Literature / satellite grounding for a hypothesis** → `offline-testing-workflow` (Steps 1–4),
  `scientific-analysis`.
- **Next:** `phase5-testing` (new simulations) or `phase3-diagnosis` (skip-test loop).

## Changelog

- 2026-07-02: Created — offline Phase 4 routine mirroring `reasoning.generate_hypothesis()` + skip-testing (`test_with_existing_data.py`); hands the new-simulation path to `offline-testing-workflow` / `phase5-testing`.
