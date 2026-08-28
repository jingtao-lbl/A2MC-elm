---
name: phase4-hypothesis
visibility: public
category: phase
description: Run Phase 4 (HYPOTHESIS) of the A2MC calibration workflow as the offline agent — the human-in-the-loop analog of the orchestrator's `_run_hypothesis()` / `reasoning.generate_hypothesis()`. Turn a Phase 3 diagnosis into specific, testable hypotheses with parameter changes + expected outcomes, and FIRST try to test them against the existing Morris ensemble (skip-testing — reads existing data, no new simulations) before committing to a Phase 5 experiment. Use when the user says "generate a hypothesis", "what should we test next", "design the experiment", "can we test this with existing data", "run Phase 4", after Phase 3 diagnosis.
modes:
  requires_fates: false      # calibration-workflow phase skill; mode resolved at runtime via describe_mode
  nutrient_pathway: any
  scope: [calibration]
  summary: "Offline analog of Phase 4 (hypotheses + skip-test on existing data). Applies in every calibration mode."
---

# Phase 4: Hypothesis (offline agent)

> **Driven by `calibration-goal`** — the run-to-convergence driver dispatches here when `WorkflowStateOffline.current_phase` routes to this phase; do the phase, then update + `save()` the state so the driver advances. Also runnable standalone (one phase).

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
/ diagnostic / custom_script). **Visualize the skip-test result** — the high-vs-low group contrast, the
scatter + fit, or the threshold split — as a figure (via the `plotting` skill); a skip-test verdict rides
on a distribution/relationship that a table of numbers flattens ([[feedback_figures_over_tables_over_words]]).
This is the 3↔4 inner loop: accumulate the evidence, and either

- **confidence ≥ `--confidence-threshold` (default 0.95)** (or the pattern is clear) → conclude without
  new simulations; or
- **feed the insight back to `phase3-diagnosis`** and refine the next hypothesis (loop).

**Inner-loop counter (enforce it — the online agent does so in code).** This is the `skip_testing_count`
loop, capped at `--max-skip-testing` (default 10). On each skip-test, **increment `skip_testing_count`** in
`workflow_state_offline_r{RR}.json`. Exit the inner loop when **confidence ≥ 0.95**, OR `skip_testing_count`
= `--max-skip-testing`, OR the hypothesis needs values outside the Morris range (`test_with_existing=false`
→ Phase 5). `skip_testing_count` **counts within the current experiment cycle only — it resets to 0 when
Phase 5 begins.**

### THE EXIT IS PER-HYPOTHESIS, NOT PER-CYCLE — and that is how this loop dies

`test_with_existing=false` is a property of **one hypothesis**, not a verdict on the cycle. Taking it
as the cycle's exit means: frame one hypothesis, skip-test it, discover its *experiment* needs new
simulations, and leave — spending the **expensive** loop while the **free** one still had questions.

**So before routing to Phase 5, ask explicitly and answer in the log:**

> *Is there another question about this cycle's mechanism that the EXISTING ensemble can answer?*

If yes, that is the next iteration — increment `skip_testing_count` and run it. Only when the honest
answer is no does the cycle route to Phase 5. The asymmetry is the argument: a skip-test is minutes
of arithmetic over data already on disk; a Phase-5 cycle is hours of compute plus scoring and
analysis.

**And keep asking while Phase 5 RUNS.** An in-flight experiment is not a reason to idle — the
existing ensemble is still there, and a skip-test run during those hours costs nothing and can
redirect the next cycle before this one even lands.

> **Where this branch actually stands** (measured 2026-08-23, so the rule is calibrated rather than
> assumed): main's Phase-3/4 logs span `iter01`–`iter04` against `A2MC_MAX_SKIP_TESTING`=10. Main
> **does** enter the free loop — unlike the branch this rule came from, where 46 logs sat at `iter01`
> and 4 at `iter02`. The rule is therefore a guard here, not a correction: four iterations is real
> use, and still four of ten.

### A conditioned claim must be checked for the cost it conditions AWAY

A skip-test that computes its statistic over a **filtered** population — cases where one target is
already in band, cases that are "alive", the top-N — is making a claim about that population, and is
**silent about whether the lever takes cases out of it**.

**Conditioning on a variable the intervention itself moves hides exactly the cost that matters.** So
whenever a screen is conditioned, pair it with the membership check:

> *Does this lever preserve membership in the set I conditioned on, over the range I intend to move
> it?*

Same error class as reading a group contrast on a *downstream* variable as a mechanism. Both produce
a result that is true as computed and wrong as used.

> **Footgun — untestable in range.** If the hypothesis needs parameter values *outside* the Morris
> sampled range, existing data can't test it — go straight to Phase 5. Don't force a skip-test that
> the ensemble can't actually answer.

`phases/phase4_hypothesis/synthesis.py` consolidates multi-cycle skip-testing insights into
experiment designs when you exit the loop toward Phase 5.

## Step 2b — EVERY hypothesis carries its own test plan and falsification bar

Online, `design_experiments(hypothesis, base_case)` returns a `List[Experiment]` — so each
hypothesis mechanically gets concrete experiments, each with `modifications`,
`expected_results` and a **`success_threshold`**. Offline nothing forced that, and the gap is
**worse here**, because this skill invites you to weigh *several* hypotheses where the online
agent proposes one.

For **each** hypothesis you carry forward, state:

| | |
|---|---|
| **How it is examined** | skip-test on existing data (which cases, which reduction) **or** the Phase-5 variants that test it |
| **Expected outcome** | the direction and magnitude per target |
| **Success criteria** | the **quantified bar** that would confirm it |
| **What would refute it** | the observation that kills it — if nothing could, it is not a hypothesis |

Log the bar via `success_criteria=` on `log_hypothesis` (it emits `## Success Criteria`).
`expected_outcomes` says what you think will happen; `success_criteria` says what settles it.
Phase 6 rules CONFIRMED/REFUTED against this bar, so a hypothesis logged without one leaves
that verdict unanchored.

If you carry N hypotheses, log N of them (`log_hypothesis` is per-hypothesis) rather than one
merged entry — Phase 6 evaluates them individually and the reasoning chain tracks each.

## Step 3 — needs new simulations? design the experiment → Phase 5

If it can't be answered with existing data, the hypothesis becomes a parameter-sweep experiment.
**Hand off to `offline-testing-workflow`** (the offline Phase 5) — it owns variant design, param-file
generation + verification, the V0 reproducibility gate, submission, and analysis. Invoke
`phase5-testing` for the phase-level routing.

## Step 4 — log and hand off

> **The log is a LIVING record — start it now, enrich as the phase runs.** Not an end-of-phase
> write-up. Full contract in `calibration-log`.
>
> **This phase's expected sections** — `PhaseLogger` names any you leave empty:
> Mechanism · Parameters to Modify · AI Reasoning and Deep Analysis · Expected Outcomes · Success Criteria · Experiments Planned.
>
> **`Success Criteria` is the one that decides Phase 6.** Pass it explicitly — `log_hypothesis`
> now takes `success_criteria=` — or Phase 6 rules CONFIRMED/REFUTED against a bar no log holds.
>
> **Set the handshake before the `log_*` call**, so the chain is traceable:
> ```python
> logger.set_phase_handshake(
>     inherited_from="<phase3 log STEM> — root causes, implicated params, base cases",
>     handed_to="the hypothesis + its success_criteria bar + the planned experiments",
>     next_action="<skip-test to run, or the Phase 5 experiment to launch>")
> ```
> The log also carries `## Reasoning chain`, rebuilt from `workflow_state_offline` — so keep that
> state updated with the FINDING, not a label; the chain is only as good as what each phase wrote.


Log via `calibration-log` (phase log → `PhaseLogger.log_hypothesis`): the hypothesis, parameter
moves, skip-test evidence + verdict, and the routing decision. **Hand off** to `phase5-testing` (new simulations)
or back to `phase3-diagnosis` (another skip-test cycle). **Advance the driver state:** on route to Phase 5
`st.set_position(current_phase="testing")`; on a skip-test loop-back
`st.set_position(current_phase="diagnosis", skip_testing_count=<n+1>)`; `st.save()` either way
(`tools/workflow_state_offline.py`).

**Evidence gate (docs/33).** A skip-test log must cite the skip-test **script + output + figure** produced this session
(`test_with_existing_data.py` result + the Step-2 visualization in `phase_results/{stem}/`), not just an assertion. Run
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

## Before you finish

**Discipline self-review (automatic).** Before advancing the state, re-check the [`calibration-discipline`](../calibration-discipline/SKILL.md) items that apply to this phase. This is unprompted and per-phase — the user does not have to ask (memory `feedback_schedule_periodic_reviews_with_a_real_mechanism`).

## Related skills / next phase

- **Experiment execution (the new-simulation path)** → `offline-testing-workflow` / `phase5-testing`.
- **Literature / satellite grounding for a hypothesis** → `offline-testing-workflow` (Steps 1–4),
  `scientific-analysis`.
- **Next:** `phase5-testing` (new simulations) or `phase3-diagnosis` (skip-test loop).

## Changelog

- 2026-08-23 — Added **a conditioned claim must be checked for the cost it conditions AWAY**. Adopted from `adapter-kit` (`94b2a784`), re-authored. A skip-test computed over a filtered population (already-in-band, alive, top-N) is silent about whether the lever takes cases OUT of that population; conditioning on a variable the intervention moves hides the cost that matters. Generic reasoning trap, not model-specific.
- 2026-08-23 — Added **THE EXIT IS PER-HYPOTHESIS, NOT PER-CYCLE**. Adopted from `adapter-kit` (`659d0498`), re-authored. `test_with_existing=false` is a property of one hypothesis, not the cycle's exit; taking it as the exit spends the expensive loop while the free one still had questions. Calibrated to this branch rather than inherited: main's Phase-3/4 logs span `iter01`–`iter04` against a cap of 10, so main DOES enter the inner loop — unlike the source branch (46 logs at `iter01`, 4 at `iter02`). Stated as a guard here, not a correction.

- 2026-08-03: New **Step 2b — every hypothesis carries its own test plan and falsification bar**.
  Online, `design_experiments()` mechanically gives each hypothesis a `success_threshold`; offline
  nothing forced it, and the gap is worse here because this skill weighs SEVERAL hypotheses. Log the
  bar via `success_criteria=` (v2.221 wired it end to end) — Phase 6 rules CONFIRMED/REFUTED against it.
- 2026-08-03: Log step now states the **living-record** contract (start at phase start, enrich as it
  runs — the operational detail is unrecoverable later), names **this phase's expected sections** so an
  omission is visible in the log, and shows `set_phase_handshake()` so the reasoning chain is traceable.
  Added a **Before you finish** discipline self-review. Full contract: `calibration-log`.
- 2026-07-15: Wired the conditional `set_position` state-advance in the handoff step (route to `testing` vs the 3↔4 skip-test loop-back to `diagnosis` with `skip_testing_count++`). Ported from demo `d3cbbf5` (offline-workflow enforcement sweep).
- 2026-07-15: **Skip-test result must be visualized** — Step 2 requires a figure of the contrast / scatter+fit / threshold split, and the evidence gate now cites script + output **+ figure**. Ported from demo `cd14d24`.
- 2026-07-06: Made the **inner-loop counter explicit** in Step 2 — named `skip_testing_count`,
  `--max-skip-testing` (10), `--confidence-threshold` (0.95), the increment-per-skip-test, and the
  reset-to-0-on-Phase-5. Pairs with the Phase-6 middle-loop gate. Ported from demo `2d3f4b0`.
- 2026-07-06: Added the mirrored "Working discipline (Phase 3↔4)" block (integrated-story logs, source-before-upstream-git, keep the inner loop turning, log-stem-is-canonical). Kept in sync with `phase3-diagnosis`. Ported from demo, scrubbed of Kougarok specifics.
- 2026-07-02: Created — offline Phase 4 routine mirroring `reasoning.generate_hypothesis()` + skip-testing (`test_with_existing_data.py`); hands the new-simulation path to `offline-testing-workflow` / `phase5-testing`.
