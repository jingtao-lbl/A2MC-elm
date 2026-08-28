---
name: phase6-refinement
visibility: public
category: phase
description: Run Phase 6 (REFINEMENT) of the A2MC calibration workflow as the offline agent — the human-in-the-loop analog of the orchestrator's `_run_refinement()` / `reasoning.interpret_results()` + `extract_lesson()`. Evaluate the experiment results vs baseline + expected outcomes, extract lessons (discoveries / failed approaches), update Adaptive Memory, and decide convergence — converged, rethink (6→3), or redesign (6→0). Use when the user says "evaluate the results", "did the experiment work", "extract the lessons", "run Phase 6", "should we converge or iterate", "what did we learn", after Phase 5 testing.
modes:
  requires_fates: false      # calibration-workflow phase skill; mode resolved at runtime via describe_mode
  nutrient_pathway: any
  scope: [calibration]
  summary: "Offline analog of Phase 6 (evaluate, learn, converge/iterate). Applies in every calibration mode."
---

# Phase 6: Refinement (offline agent)

> **Driven by `calibration-goal`** — the run-to-convergence driver dispatches here for the **convergence fork**: this phase's converge/redesign/stop decision (`validate_phase6_decision`) is the driver's branch point AND a human gate (the driver auto-takes a `rethink_6to3`, pauses for converge/redesign/stop). Also runnable standalone.

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

## Step 1b — extract the FULL results + comparison plots (experiment Phase 6; esp. TIME SERIES)

### The requirement — what the figure must cover, before the verdict is written

**Produce a sim-vs-obs TIME-SERIES overlay covering EVERY SCORED TARGET, before writing the verdict,
and include it in the cycle report.** Concretely:

- **One panel per scored target**, not one panel for the target the experiment aimed at. An
  intervention that moves its own target while pushing two others out of band has **failed**, and a
  single-target figure cannot show that. This branch scores six targets (leaf + fine root × three
  PFTs), so a one-panel verdict is showing one sixth of the result.
- **The observation drawn as it was measured.** If the record is a series, plot the series — per-year
  points with their spread, and **gaps left as gaps**. A flat line at the multi-year mean is a
  *summary* of the observation, not the observation, and it hides both the spread and the years
  nobody measured. (Relevant here: the Kougarok targets carry field standard deviations *larger than
  the mean* for PFT#10 — 29.1 vs 24.6 — which a flat line erases.)
- **The control on top**, so V0-tracks-its-base is visually confirmed rather than asserted.

Pairs with [[feedback_timeseries_plots_during_diagnosis]] (trajectory shape often IS the diagnosis)
and [[feedback_figures_over_tables_over_words]].

For an **experiment** (N variants on a base case), Step 1's `evaluate_results.py` gives the per-target
*numbers at the observation month*, but Phase 6 also needs the **full extracted series and the visual
comparison vs observations** to judge honestly and to report. Use the generic tool
**`tools/extract_and_plot_selected_cases.py`** — the promoted successor to the retired
`use_cases/{site}/scripts/` one-off overlay scripts; **do NOT resurrect those**, and do not edit the
`_exp`-gated production extractor ([[feedback_do_not_change_extractor_case_naming]]):

- **`extract`** — pull the full monthly target variables (e.g. `FATES_LEAFC_SZPF` / `FATES_FROOTC_SZPF`)
  for every variant into the extract dir. It reuses the production `process_case()` and handles the
  **non-`_exp`** experiment suffixes this driver is for.
- **`v0check`** — confirm each V0 control reproduces its base within tolerance BEFORE interpreting any
  variant (the Step-10 gate).
- **`plot`** — the **time-series overlay**: one colored line per variant over the transient years, in a
  PFT × (target) panel grid, with the observation tolerance band (`axhspan`) + obs marker. This follows the
  **A2MC ensemble figure template** (`plotting` skill) — same obs-diamond / ±20%-band / units convention as
  the whole-ensemble plot, but with **solid opaque colored variant lines** (few lines, not a cloud) and the
  control **black-dashed on top**. Pass **`--baseline <ctrl case id or suffix>`** to dash-highlight the
  control so `split − ctrl`-style comparisons read at a glance — the others stay colored solid.

**The time series is REQUIRED, not optional.** A single endpoint metric hides the trajectory — did the
variant equilibrate, collapse late, overshoot-then-crash, or oscillate? The time-series overlay is what
reveals the mechanism (and is how the V0 controls are visually confirmed to track their base). Produce it
before writing the verdict and include it in the report ([[feedback_figures_over_tables_over_words]]).
Every figure gets a caption + a plain-finding explanation in the log.

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

## Step 3b — promote reusable scripts into the shared library (round close)

Knowledge is not the only reusable output — a **diagnostic/analysis script** that proved reusable this
round should graduate out of its scratch home so future rounds/sites auto-discover it (the tooling analog
of "online proposes, offline disposes"). Human-gated; promote only genuinely reusable scripts, not one-offs.

- **Online agent's generated scripts** — `phases/phase3_diagnosis/generated/*.py` →
  `phases/phase3_diagnosis/` via `tools/promote_diagnostic_script.py` (`--list` → `--script <n> --dry-run`
  → promote; it copies the file and registers the tool in `DIAGNOSTIC_TOOLS_INVENTORY` so future runs
  auto-discover it). Full contract: `phases/phase3_diagnosis/generated/README.md`.
- **Your (offline) scripts** — the reusable ones you wrote into `use_cases/{site}/memory/phase_results/{stem}/`
  → `tools/` (a generic analysis utility) or `phases/phase3_diagnosis/` (a reusable `test_hypothesis`), via
  `tools/promote_diagnostic_script.py --source <path> --dest tools|phase3_diagnosis` (`--dry-run` first;
  `--dest tools` just copies, `--dest phase3_diagnosis` also registers it in `DIAGNOSTIC_TOOLS_INVENTORY`).
  Leave one-off figure scripts in `phase_results/{stem}/` — they are the log's evidence, not library code.
- **Generalize the promoted copy before committing** — promotion is copy-**then-generalize**. A
  `phase_results/{stem}/` script hardcodes its output path, stem, and case IDs; the library copy must be
  site/run-agnostic, so edit it to strip hardcoded paths/stems/case/site names and parameterize inputs
  (argparse or `tools/config.py`) — CLAUDE.md rules 5 + 8. The tool prints this reminder after copying.

## Step 4 — decide where the loop goes (GATE on the middle-loop counter)

The online orchestrator enforces this fork in **code** (`orchestrator.py` state machine: `experiment_count`
vs `max_experiments`), so it physically cannot skip a cycle. **Offline you must enforce the SAME gate by
hand** — the offline agent matches or exceeds the online loop discipline, it never rushes past it. **Read
`experiment_count` / `skip_testing_count` from `workflow_state_offline_r{RR}.json` before deciding.**

### A rethink is a SYNTHESIS, not a routing decision

`rethink_6to3` is the default route and — everywhere else in this skill — only a counter increment.
**A cycle that re-enters Phase 3 carrying the previous cycle's base, binding target and lever class
forward unexamined is not a new cycle; it is the same cycle with one parameter changed.**

Answer all six **in the log** before recording the decision. Every one is settled by existing data
at zero compute.

1. **Synthesize THIS cycle, Phases 3–6.** What was hypothesized and on what mechanism; what each
   inner-loop iteration asked and returned, *including the ones that refuted the cycle's own earlier
   iterations*; what was run and what it scored per target; the verdict against the pre-registered
   bar. State what the cycle **ESTABLISHED** separately from what it merely tried — a refuted
   hypothesis that localized a cost is a finding, and carrying only "it failed" forward loses it.
   **Write this once**: it is the same synthesis the CYCLE report needs (`write-report`), so produce
   it here and let the report draw on it rather than deriving it twice from raw logs.
2. **Re-read Phase 1 and Phase 2 AGAINST that synthesis, not for citation.** The μ\* ranking and the
   screening leaders were computed before the round learned what it now knows; the question is what
   they say that this cycle's result makes newly relevant. Check the artifacts' own caveats too — a
   ranking computed over a population containing runaway cases ranks levers by their behaviour in a
   regime the calibration never occupies.
3. **Is the BASE still right for the question now being asked?** A base is chosen to fix one target;
   the binding target moves. Check whether it still has headroom on the targets it already holds. A
   base sitting at a band edge on the target the next experiment would move is the wrong base,
   however good its overall score.
4. **Has the BINDING TARGET moved?** Re-derive it from the current best configuration rather than
   inheriting the previous cycle's framing.
5. **What CLASS of lever has the round exhausted, and what class is untried?** Group refuted cycles
   by **mechanism class, not by parameter**. Three cycles refuting three parameters in one class is
   *one* refutation, and the next cycle should leave the class.
6. **For each refuted lever: which DIRECTION was moved, from a base with which SIGN of miss, and
   does that still apply?** A refutation is a property of a **(parameter, direction, base)** triple,
   not of a parameter — and question 5 does not catch this, because it groups by mechanism rather
   than by direction. A lever refuted for failing to *lower* a target at a base where it was too
   *high* has never been tested for *raising* it at a base where it is too *low*; a dose response
   that moved monotonically the wrong way is **positive evidence for the opposite direction**, not a
   closed door. Tabulate: parameter, direction moved, the base's miss sign at the time, and whether
   the opposite direction has ever been run. Then check the only two ways "no, and it still cannot
   be" holds — the opposite direction is **out of bounds or past a physical ceiling** (extrapolate
   the dose against both the calibrated bound and any structural limit, e.g. a fraction that cannot
   exceed 1), or the base has **no headroom left** in that parameter. Where neither holds, the
   opposite direction is an untested experiment the round has been treating as refuted.

**Deliverable: NEW PATHWAYS, plural, handed to Phase 3.** Each names **what kind of move it is** and
what would falsify it, rather than continuing the refuted hypothesis. The kind is usually a lever
class (Q5), but Q6 makes two others first-class: a **DIRECTION** on a lever the round believes it
refuted, and a **BASE CHANGE**, which is not a lever at all. A pathway that only says "change the
base" is weak — say what to rank by, since a criterion is actionable and "look again" is not. And a
**diagnostic pathway that costs no compute outranks an experiment** when its outcome would decide
which experiment to run. Record them with `st.add_decision(...)` and name them in
`set_phase_handshake(handed_to=...)` so Phase 3 receives them instead of re-deriving them.

> **Preventive on this branch.** Main is at `experiment_count=1` with `phase6_decision=None` — no
> rethink has run here yet. The protocol is adopted before the first one, not after a round spent
> three cycles on one base. (Adopted from `adapter-kit` `2849b4d2` + `924b7b56`.)

**Structural objective gate (docs/34) — fill it, don't skip it.** Before recording a decision, populate the
`phase6_decision` block and run the validator; a failing check **blocks** the escalation (it cannot be the
path of least resistance):

```python
from tools.workflow_state_offline import WorkflowStateOffline
st = WorkflowStateOffline.load(calibration_round=RR)
st.set_phase6_decision(decision="rethink_6to3",           # converge | rethink_6to3 | redesign_6to0 | stop_model_dev
    objective="6 targets", best_so_far="3/6", binding_target="<the specific failing target>",
    next_targeted_experiment="<named, in-range, target-aimed experiment aimed at binding_target> | NONE",
    exhaustion_justification="<why no in-range experiment remains> | ''", max_experiments=10)
violations = st.validate_phase6_decision()   # MUST be [] before you act
```
`stop_model_dev` / `redesign_6to0` are rejected while `experiment_count < max_experiments` and a named
`next_targeted_experiment` remains (that is a `rethink_6to3`); `stop_model_dev` also requires
`next_targeted_experiment == NONE` + a non-empty `exhaustion_justification`. On `rethink_6to3`, advance the
counter via `st.set_position(experiment_count=experiment_count+1)` and `st.save()`.

- **All targets met** → converged (Phase 7); write the final config + round summary.
- **NOT met, `experiment_count` < `--max-experiments` (default 10)** → **6→3 rethink is the DEFAULT.** Do NOT
  escalate while the cycle budget remains. Before choosing anything other than rethink, confirm there is **no
  named, in-range, target-aimed parameter experiment left to run** ([[feedback_performance_experiment_is_the_objective]]);
  if one remains — including a lead flagged in a prior log — that **is** the next rethink cycle, run it.
  **On routing 6→3: increment `experiment_count` in the state file.**
- **NOT met, `experiment_count` = `--max-experiments`** (middle loop exhausted) → **6→0 redesign**: back to
  `phase0-design` with widened bounds; increment `calibration_round`. Redesign earlier is justified ONLY if
  every remaining candidate is a Morris-bound **edge** parameter (a redesign signal, not a Phase-4 knob) AND
  no in-range experiment remains — the exception, not the default.

> **"Stop → improve the model" is NOT a loop branch.** Modifying model source is *outside* the A2MC
> calibration loop; it is justified only after the loop is **provably exhausted** (rethink cycles to the cap,
> then redesign) OR a structural impossibility is **proven by exhausting the targeted experiments**, not
> asserted from one result. Jumping there with `experiment_count` cycles still on the clock is the rush this
> gate prevents.

## Step 5 — log, report, hand off

> **The log is a LIVING record — start it now, enrich as the phase runs.** Not an end-of-phase
> write-up: the operational detail (job/array IDs, which cases failed, what was restarted) is
> unrecoverable a week later. Full contract in `calibration-log`.
>
> **This phase's expected sections** — `PhaseLogger` names any you leave empty:
> Target Changes · AI Reasoning and Deep Analysis · Lessons Learned · Discoveries (for gained_knowledge) · Failed Approaches (DO NOT REPEAT) · Experiment Results Summary.
>
> **Set the handshake before the `log_*` call**, so the chain is traceable:
> ```python
> logger.set_phase_handshake(
>     inherited_from="<predecessor log STEM> — what it concluded / asked of this phase",
>     handed_to="<what Phase 3 / 0 / 7 receives; mirror the reasoning/schemas.py field names>",
>     next_action="<the one concrete thing Phase 3 / 0 / 7 should do>")
> ```
> The log also carries `## Reasoning chain`, rebuilt from `workflow_state_offline` — so keep that
> state updated with the FINDING, not a label; the chain is only as good as what each phase wrote.


Log via `calibration-log` (phase log → `PhaseLogger.log_refinement`). Standardized reporting:
`summarize-calibration-round` (this round) / `compare-calibration-rounds` (vs prior). Then route per
Step 4. **Evidence gate (docs/33):** the refinement log must cite the evaluation artifact produced this
session (the biomass/target extraction + figure in `phase_results/{stem}/`); run
`python tools/check_offline_log_evidence.py <log.md>` (exit 0) before curating any lesson.

## Before you finish

**Discipline self-review (automatic).** Before advancing the state, re-check the [`calibration-discipline`](../calibration-discipline/SKILL.md) items that apply to this phase. This is unprompted and per-phase — the user does not have to ask (memory `feedback_schedule_periodic_reviews_with_a_real_mechanism`).

## Related skills / next phase

- **Curate staged proposals** → `curate-knowledge`. **Inject a vetted finding** → `inject-knowledge`.
- **Deeper investigation / figure** → `scientific-analysis`. **Round reports** →
  `summarize-calibration-round`, `compare-calibration-rounds`; an **integrated, cross-cutting write-up**
  for a human reader (an investigation synthesis beyond the standardized round summary) → `write-report`.
- **Next:** converged (Phase 7), or loop to `phase3-diagnosis` (rethink) / `phase0-design` (redesign).

## Changelog

- 2026-08-23 — Added **the 6→3 RETHINK PROTOCOL**: six questions answered in the log before the decision is recorded, deliverable NEW PATHWAYS (plural) with lever class and falsifier. Adopted from `adapter-kit` (`2849b4d2` + `924b7b56`), re-authored. `rethink_6to3` was the default route and only a counter increment here too — a cycle could re-enter Phase 3 carrying the previous cycle's base, binding target and lever class forward unexamined. Q6 (a refutation is a (parameter, DIRECTION, base-miss-sign) triple, not a property of a parameter) is the one Q5 cannot catch. PREVENTIVE on main: `experiment_count=1`, `phase6_decision=None` — no rethink has run here yet.

- 2026-08-23 — Added **the figure requirement** to Step 1b: a sim-vs-obs time-series overlay covering EVERY scored target before the verdict is written. Adopted from `adapter-kit` (`518af9c8`), re-authored — its model-neutral half only, since main IS the FATES implementation that half was being separated from. One panel per scored target, the observation drawn as measured with gaps left as gaps, and the control on top. This branch scores six targets, so a one-panel verdict shows one sixth of the result.

- 2026-08-03: Log step now states the **living-record** contract (start at phase start, enrich as it
  runs — the operational detail is unrecoverable later), names **this phase's expected sections** so an
  omission is visible in the log, and shows `set_phase_handshake()` so the reasoning chain is traceable.
  Added a **Before you finish** discipline self-review. Full contract: `calibration-log`.
- 2026-07-18: Added **Step 3b — promote reusable scripts into the shared library** at round close (the
  tooling analog of the knowledge write-gate): online `phases/phase3_diagnosis/generated/` →
  `phases/phase3_diagnosis/` via `tools/promote_diagnostic_script.py`; offline `phase_results/{stem}/`
  scripts → `tools/` or `phases/phase3_diagnosis/` via the new `--source <path> --dest tools|phase3_diagnosis`
  flags (was manual). Promotion is copy-**then-generalize** (the tool prints the reminder). Mirrored in the
  `calibration-discipline` per-round checklist (item 12). Ported from adapter-kit `0eacaea`/`92e5c0e`/`9ac4d44`.
- 2026-07-15: Step 1b notes the new `extract_and_plot_selected_cases.py --baseline` flag (dash-highlight the control for split−ctrl reads). Ported from demo `db488cd`.
- 2026-07-09: **Added Step 1b — extract full results + time-series comparison plots** for an experiment's
  Phase 6, via the generic `tools/extract_and_plot_selected_cases.py` (`extract`/`v0check`/`plot`). Makes
  the **time-series overlay vs observations** a required Phase-6 figure — a single endpoint metric hides the
  trajectory (equilibrate / late-collapse / overshoot-crash / oscillate). Ported from demo `a2147ff`, scrubbed
  of Kougarok example filenames.
- 2026-07-06: **Wired the middle-loop gate into Step 4.** The decision fork now gates on `experiment_count`
  vs `--max-experiments` (rethink 6→3 is the DEFAULT while cycles remain; redesign 6→0 only at the cap), adds
  the "no in-range target-aimed experiment left" precondition before any escalation, the counter-increment
  step, and an explicit "'stop → improve the model' is NOT a loop branch" guard. Mirrors the online
  orchestrator's coded state machine so the offline agent can't rush past the loop. Ported from demo `2d3f4b0`
  (v3.12), scrubbed of the Kougarok worked example. See `feedback_performance_experiment_is_the_objective`.
- 2026-07-02: Created — offline Phase 6 routine mirroring `interpret_results()` + `extract_lesson()`; encodes the offline "disposer" write gate (direct curated writes + promote staged proposals), delegates memory to curate-/inject-knowledge, reporting to summarize-/compare-calibration-round.
