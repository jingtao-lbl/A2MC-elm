---
name: phase4-hypothesis
description: Run Phase 4 (HYPOTHESIS) of the A2MC calibration workflow as the offline agent — the human-in-the-loop analog of the orchestrator's `_run_hypothesis()` / `reasoning.generate_hypothesis()`. Turn a Phase 3 diagnosis into specific, testable hypotheses with parameter changes + expected outcomes, and FIRST try to test them against the existing Morris ensemble (skip-testing — reads existing data, no new simulations) before committing to a Phase 5 experiment. Use when the user says "generate a hypothesis", "what should we test next", "design the experiment", "can we test this with existing data", "run Phase 4", after Phase 3 diagnosis.
modes:
  requires_fates: false      # calibration-workflow phase skill; mode resolved at runtime via describe_mode
  nutrient_pathway: any
  scope: [calibration]
  summary: "Offline analog of Phase 4 (hypotheses + skip-test on existing data). Applies in every calibration mode."
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

- **confidence ≥ `--confidence-threshold` (default 0.95)** (or the pattern is clear) → conclude without
  new simulations; or
- **feed the insight back to `phase3-diagnosis`** and refine the next hypothesis (loop).

**Inner-loop counter (enforce it — the online agent does so in code).** This is the `skip_testing_count`
loop, capped at `--max-skip-testing` (default 10). On each skip-test, **increment `skip_testing_count`** in
`workflow_state_offline_r{RR}.json`. Exit the inner loop when **confidence ≥ 0.95**, OR `skip_testing_count`
= `--max-skip-testing`, OR the hypothesis needs values outside the Morris range (`test_with_existing=false`
→ Phase 5). `skip_testing_count` **counts within the current experiment cycle only — it resets to 0 when
Phase 5 begins.**

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

**Evidence gate (docs/33).** A skip-test log must cite the skip-test **script + output** produced this session
(`test_with_existing_data.py` result in `phase_results/{stem}/`), not just an assertion. Run
`python tools/check_offline_log_evidence.py <log.md>` (exit 0). Note: a hypothesis is a hypothesis until a
Phase-5 test confirms it — do not promote it to the curated KB from here (that's the `docs/33` §3b KB gate).

## Working discipline (offline agent — applies across Phase 3↔4)

1. **Log the integrated story, not a snapshot.** A diagnosis/hypothesis log must carry the *whole
   reasoning chain*: what has already been tested and learned, the logic that led here, why each
   candidate was kept or ruled out, and **why the next step is the correct direction**. Credit the
   canonical prior log instead of re-deriving it; when a new finding overturns an earlier one, supersede
   it. A well-formed log lets a cold reader reconstruct the *argument*, not just the conclusion.

2. **Read your checked-out model source FIRST, then upstream git.** To verify how a parameter / line /
   mechanism behaves, read the **actual checked-out source** (`$A2MC_E3SM_ROOT/...`) and the **param file
   in use** BEFORE querying the upstream model repo. Your local tree may be a custom branch that diverges
   from upstream; ask upstream "has this been fixed since" *after* you know the local truth.

3. **Keep the inner loop turning while sims run.** Phase-5 simulations take hours — do NOT idle waiting.
   Continue diagnosis / hypothesis / skip-test work (the 3↔4 inner loop) in parallel with the in-flight
   experiment. Idle waiting is an online-agent limitation you don't share
   ([[feedback_offline_agent_drives_the_workflow]]).

4. **Stem invariant: the log stem is canonical.** Every `phase_results/{stem}/` folder MUST have a
   matching `logs/{stem}.md`. Decide the stem when you write the log and reuse that exact stem for
   `phase_results/` — never mint a separate letter for the artifacts (`docs/31`; via `PhaseLogger`
   offline mode). (Mirrored in `phase3-diagnosis`.)

## Related skills / next phase

- **Experiment execution (the new-simulation path)** → `offline-testing-workflow` / `phase5-testing`.
- **Literature / satellite grounding for a hypothesis** → `offline-testing-workflow` (Steps 1–4),
  `scientific-analysis`.
- **Next:** `phase5-testing` (new simulations) or `phase3-diagnosis` (skip-test loop).

## Changelog

- 2026-07-06: Made the **inner-loop counter explicit** in Step 2 — named `skip_testing_count`,
  `--max-skip-testing` (10), `--confidence-threshold` (0.95), the increment-per-skip-test, and the
  reset-to-0-on-Phase-5. Pairs with the Phase-6 middle-loop gate. Ported from demo `2d3f4b0`.
- 2026-07-06: Added the mirrored "Working discipline (Phase 3↔4)" block (integrated-story logs, source-before-upstream-git, keep the inner loop turning, log-stem-is-canonical). Kept in sync with `phase3-diagnosis`. Ported from demo, scrubbed of Kougarok specifics.
- 2026-07-02: Created — offline Phase 4 routine mirroring `reasoning.generate_hypothesis()` + skip-testing (`test_with_existing_data.py`); hands the new-simulation path to `offline-testing-workflow` / `phase5-testing`.
