---
name: phase3-diagnosis
visibility: public
category: phase
description: Run Phase 3 (DIAGNOSIS) of the A2MC calibration workflow as the offline agent — the human-in-the-loop analog of the autonomous orchestrator's `_run_diagnosis()` / `reasoning.diagnose()`. Systematically root-cause WHY the screening round is missing its validation targets — gather diagnostic data with the phase3 tools, pull RAG + Adaptive Memory context, then reason to a structured diagnosis (failing targets, likely causes, ranked root causes, parameter recommendations, base cases, hypotheses) and hand off to Phase 4. Use when the user says "diagnose the failing targets", "run Phase 3", "why aren't the targets calibrating", "root-cause this round", "what's driving the PFTx miss", after screening (Phase 2) hands off a ranked ensemble.
modes:
  requires_fates: false      # calibration-workflow phase skill; mode resolved at runtime via describe_mode
  nutrient_pathway: any
  scope: [calibration]
  summary: "Offline analog of Phase 3 (root-cause the failing targets). Applies in every calibration mode."
---

# Phase 3: Diagnosis (offline agent)

> **Driven by `calibration-goal`** — the run-to-convergence driver dispatches here when `WorkflowStateOffline.current_phase` routes to this phase; do the phase, then update + `save()` the state so the driver advances. Also runnable standalone (one phase).

The offline analog of the orchestrator's `_run_diagnosis()`. Online, `reasoning.diagnose()`
makes this call automatically; **offline, YOU are the reasoning** — the `phases/phase3_diagnosis/`
tools are your instruments, RAG + Adaptive Memory are your evidence, and you produce the same
structured `Diagnosis` the online agent would. This is the **systematic** phase routine (diagnose
every failing target from the screening round), distinct from `diagnose-forensics` (reactive:
"is this one anomaly real?"). If you're chasing a single suspicious case, use `diagnose-forensics`
first; come here to diagnose the round.

> **Floor, not ceiling.** This skill captures what the online agent does in Phase 3 so you never
> do *less* — but the online loop is fenced into a fixed phase scope and you are not. Your value as
> the offline agent is doing *more*: pull extra data, run analyses no phase3 tool exists for, probe
> a mechanism deeper than the schema asks, cross into an adjacent phase when the evidence leads
> there, or question the round's framing outright. Match the discipline below (verify mechanisms,
> honor failed approaches, log it), then go past it — follow the surprising thread with
> `scientific-analysis` rather than forcing the finding back into the phase box.

**Inputs (handoff from Phase 2 `screen-ensemble`):** the ranked ensemble — `best_case`,
`lowest_cost_case`, per-target errors, which targets are met/missed, Morris μ* rankings from
Phase 1. **Deliverable:** a diagnosis (logged as a phase log) naming the ranked root causes and
the parameters/base-cases Phase 4 should act on.

## Step 1 — gather diagnostic data (reads existing outputs — no new simulations)

Drive the phase3 tools on the best / lowest-cost / most-targets cases. Run several at once via
`run_diagnostics_scripts.py`; dispatch AI-requested follow-ups via `dispatch.py`.

| Question | Tool |
|---|---|
| What params does this case have / how do top cases differ? | `read_case_parameters.py`, `compare_case_parameters.py` |
| Any parameter pinned at a Morris bound (redesign candidate)? | `check_edge_parameters.py` |
| Which targets, how far off, what direction? | `compare_targets.py` |
| Did a PFT collapse / crash? | `detect_collapse.py` |
| Why is a PFT not establishing / growing? | `diagnose_pft_limitations.py` |
| Carbon / mortality / nutrient mechanism | `analyze_carbon_balance.py`, `analyze_mortality.py`, `analyze_nutrient_balance.py`, `analyze_nutrient_pools.py` |
| Best vs lowest-cost case comparison | `comparative.py` |
| Structured hypothesis test with quantified metrics | `test_hypothesis_framework.py` |
| Diagnostic figures (6-panel PFT composite) | `plot_diagnostics.py` |

Any `test_*.py` in the folder exposing `test_hypothesis()` is **auto-discovered** (see root
`CLAUDE.md` §"Diagnostic tools") — you can run one to probe an ensemble-wide pattern without new simulations.

> **Writing a custom diagnostic script? Use `tools/fates_utils`** for any per-PFT / SZPF extraction
> (`get_szpf_range()`, `extract_pft_data()`, `aggregate_szpf_by_pft()`, `get_pft_index()`) — do NOT hand-roll
> the SZPF (`levscpf`) index: it is **PFT-major** `(pft-1)×nlevsclass` with `nlevsclass` **file-derived**
> (13 in the common default but *configurable*, not a fixed 13), plus the 0-based/1-based offset (a classic
> silent bug; the FATES wiki's size-major formula is wrong). It is the canonical helper the existing phase3
> tools already import.

> **Trajectory view for collapse/exclusion.** The per-case `plot_diagnostics.py` (6-panel PFT composite)
> shows *one* case; to see *where in the spin-up→transient a target diverges from the ensemble/observations*,
> also read the whole-ensemble time-series comparison from Phase 2 Step 1b
> (`tools/plot_ensemble_cases.py --combined`, [[reference_ensemble_combined_plot_pipeline]]). Late collapse,
> overshoot-then-crash, and competitive-exclusion frontiers show up there before the per-case mechanism tools
> name them.

## Step 2 — pull evidence (RAG + Memory), verify before asserting

- **RAG/GraphRAG + `docs/fates-knowledge-base/`:** confirm the mechanism behind any parameter
  BEFORE naming it. Never infer a FATES mechanism from a parameter name (root `CLAUDE.md` rule).
- **Adaptive Memory (`memory/manager.py`):** load site discoveries (e.g. the Allocation Paradox)
  and — load-bearing — the **failed approaches**. Do NOT propose a direction Memory already
  records as failed; if you must, say why this time differs.

## Step 3 — reason to a structured diagnosis

Produce the same shape the online `Diagnosis` schema carries (don't skip the discipline the
prompt enforces online):

1. **Mechanism inventory** — enumerate every plausible mechanism (nutrient limitation, carbon
   balance, allocation/PID, competition/ECA, mortality, phenology, sim protocol); rate each and
   name the confirming/refuting evidence from Step 1–2.
2. **Severity** — classify each failing target CRITICAL (>50% error) / HIGH (30–50) / MEDIUM
   (20–30) / LOW (<20).
3. **Ranked root causes** — `{cause, mechanism, affected_targets, confidence}`, most-confident
   first, each tied to evidence (not a statistical hunch).
4. **Parameter recommendations** — `{parameter, current_issue, suggested_direction, priority,
   caution}` (FATES names). Flag any that would need values outside Morris bounds as a Phase 0
   redesign candidate, not a Phase 4 knob.
5. **Comparative analysis** — recommend 1–2 `selected_base_cases` (`{case_id, rationale,
   targets_satisfied, targets_to_fix}`) for Phase 4 to build on.
6. **Hypotheses** — 1–N testable statements for Phase 4, each with an expected direction.

Structure follows `templates/reasoning/phase3_diagnosis_template.md`. **Verify every mechanism claim in
the checked-out model SOURCE (`file:line`), not just RAG or the parameter's `long_name`/`units`.**
RAG and `long_name` are the starting hypothesis; the Fortran is ground truth, and it has repeatedly
contradicted the description:

- `fates_allom_l2fr` reads as "leaf-to-fineroot" and is the **reverse** — fine-root C *per leaf* C
  (`FatesAllometryMod.F90`, `bfineroot`: `bfr = blmax * l2fr * canopy_trim`), so high `l2fr` means MORE
  fine root ([[reference_l2fr_is_fineroot_per_leaf]]);
- `fates_cnp_eca_alpha_ptase` / `lambda_ptase` are **inactive and hard-guarded to 0** in api-43 ECA
  despite live-looking descriptions — a nonzero value aborts init ([[reference_fates_eca_ptase_disabled_api43]]);
- `use_fates_nocomp` does **not** fix PFT areas, whatever the name suggests (CLAUDE.md's own worked example).

So before writing a root cause that rests on "parameter X does Y": grep the source for X, read the
equation it enters, and cite the `file:line`. A mechanism claim with a source citation is a different
quality of evidence from one with a plausible name.
[[feedback_param_description_can_lie_verify_in_source]] [[feedback_verify_before_acting_triangulate_sources]]

## Step 4 — cheap test first? (skip-testing inner loop, Phase 3↔4)

If a hypothesis can be tested against the **existing** Morris ensemble (a correlation, a
high-vs-low group contrast, a threshold) — do that instead of queuing a new simulation. That is the Phase 3↔4
skip-testing inner loop: hand the hypothesis to `phase4-hypothesis`, which decides
`test_with_existing` vs a new simulation. Only real parameter values outside the ensemble range need Phase 5.

## Step 5 — log it and hand off

> **The log is a LIVING record — start it now, enrich as the phase runs.** Not an end-of-phase
> write-up: the operational detail (job/array IDs, which cases failed, what was restarted) is
> unrecoverable a week later. Full contract in `calibration-log`.
>
> **This phase's expected sections** — `PhaseLogger` names any you leave empty:
> Failing Targets · Likely Causes · Root Causes (Ranked) · Key Insights · AI Reasoning and Deep Analysis · Parameter Recommendations · Cross-PFT Conflicts · Hypotheses Tested · Conceptual Model.
>
> **Set the handshake before the `log_*` call**, so the chain is traceable:
> ```python
> logger.set_phase_handshake(
>     inherited_from="<predecessor log STEM> — what it concluded / asked of this phase",
>     handed_to="<what Phase 4 receives; mirror the reasoning/schemas.py field names>",
>     next_action="<the one concrete thing Phase 4 should do>")
> ```
> The log also carries `## Reasoning chain`, rebuilt from `workflow_state_offline` — so keep that
> state updated with the FINDING, not a label; the chain is only as good as what each phase wrote.


- **Log** via `calibration-log` (phase log → `PhaseLogger.log_diagnosis`, byte-identical to the
  autonomous agent so both modes' logs synthesize). Capture failing targets, ranked root causes,
  parameter recommendations, selected base cases, hypotheses, and the RAG/Memory evidence.
- **Evidence gate (docs/33).** The log must cite a first-hand artifact produced **this session** — the
  diagnostic script + its output/figure in `phase_results/{stem}/` or `phases/phase3_diagnosis/generated/`
  (a "Scripts Created" / "Output Figures" / "Evidence" section) — not just restate a prior log. Run
  `python tools/check_offline_log_evidence.py <log.md>`; it must exit 0 (ERROR = no resolvable first-hand
  artifact). See `feedback_offline_logs_need_first_hand_analysis`.
  **Make `phase_results/{stem}/` SELF-DOCUMENTING** (`calibration-log` "different jobs" note): the
  `log/{stem}.md` carries the analysis/findings/discussion/conclusion/next-action; the folder ships, per
  figure, the **figure + a caption/NOTES `.md` (what it shows + how-to-read + provenance) + the generating
  `.py` script (saved, not an inline heredoc) + the data**. The gate now WARNs on a figure missing its
  caption/script/data — clear those warnings, don't stop at exit 0 (mirrors `write-report`). Phase 4/6 identical.
- **Hand off** to `phase4-hypothesis` with the base cases + hypotheses. (If you came here from
  Phase 6 to rethink a disproven hypothesis, that's the 6→3 experiment-cycle loop — same routine;
  `experiment_count` was incremented on the 6→3 route (Phase-6 Step 4), and this new cycle's inner-loop
  `skip_testing_count` starts fresh. Confirm both in `workflow_state_offline_r{RR}.json`.)

## Footguns

- **The `generated/` dir is staging, not truth.** AI-written custom tests land in
  `phases/phase3_diagnosis/generated/` (see its README). Review + V0-validate a generated
  script's first run before trusting it. If it's vetted and reusable, **promote** it into the
  permanent tool library with `tools/promote_diagnostic_script.py --script <name>` (`--list` →
  `--dry-run` → promote) — this copies it to `phases/phase3_diagnosis/` and registers it in
  `DIAGNOSTIC_TOOLS_INVENTORY` so future runs auto-discover it. Human-gated; review before committing.
- **Verified-only Memory gate.** Baseline auto-discovered entries are `verified=false`; know
  whether your Memory context is filtered before leaning on it.
- **Don't touch the extractor.** Phase 3 reads existing outputs; it never modifies the Phase 5
  extraction path.
- **Artifact before signal.** A too-good "best" case or a tidy failure cluster is often
  contamination / infra-timing, not science — if a result looks surprising, run
  `diagnose-forensics` triage before diagnosing it as mechanism.

## Working discipline (offline agent — applies across Phase 3↔4)

1. **Log the integrated story, not a snapshot.** A diagnosis/hypothesis log must carry the *whole
   reasoning chain*: what has already been tested and learned (across prior iterations/cycles), the
   logic that led here, why each candidate was kept or ruled out, and **why the next step is the correct
   direction**. Credit the canonical prior log instead of re-deriving it; when a new finding overturns an
   earlier one, supersede it (don't silently restate). A well-formed log lets a cold reader reconstruct
   the *argument*, not just the conclusion.

2. **Read your checked-out model source FIRST, then upstream git.** To verify how a specific parameter /
   line / mechanism behaves, read the **actual checked-out source** (`$A2MC_E3SM_ROOT/...`) and the
   **param file in use** BEFORE querying the upstream model repo or its commit history. Your local tree
   may be a custom branch that already carries fixes or diverges from upstream — an upstream read can
   mislead if you haven't pinned what YOUR code actually does. Upstream git answers "has this been fixed
   since / is there a known issue", asked *after* you know the local truth.

3. **Keep the inner loop turning while sims run.** Phase-5 simulations (the middle experiment loop) take
   hours — do NOT idle waiting. Continue diagnosis / hypothesis / skip-test work (the 3↔4 inner loop):
   analyze existing data, refute or refine other levers, read source, check upstream — in parallel with
   the in-flight experiment. Idle waiting is an online-agent limitation you don't share
   ([[feedback_offline_agent_drives_the_workflow]]).

4. **Stem invariant: the log stem is canonical.** Every `phase_results/{stem}/` folder MUST have a
   matching `logs/{stem}.md`; a log with no results folder is fine (analysis-only), a results folder with
   no log is not. So **decide the stem when you write the log, and reuse that exact stem for
   `phase_results/`** — never mint a separate letter for the artifacts (`docs/31`; via `PhaseLogger`
   offline mode `topic_stem`/`topic_artifact_dir`).

## Before you finish

**Discipline self-review (automatic).** Before advancing the state, re-check the [`calibration-discipline`](../calibration-discipline/SKILL.md) items that apply to this phase. This is unprompted and per-phase — the user does not have to ask (memory `feedback_schedule_periodic_reviews_with_a_real_mechanism`).

## Related skills / next phase

- **`plotting`** — load it **before your first `savefig`**, not after. Its rule 8 (*open the rendered PNG and LOOK at it*) is the only step that catches an overlapping legend, a stats box across the curve, or an unreadable axis, and it cannot catch them retroactively.

- **Reactive anomaly** (one outlier, not the whole round) → `diagnose-forensics`.
- **Manuscript-grade investigation of a finding** → `scientific-analysis`.
- **Next:** `phase4-hypothesis` (turn the diagnosis into testable experiments).

## Changelog

- 2026-08-03: Diagnosis-writing step now requires **verifying every mechanism claim in the model SOURCE**
  (`file:line`), not just RAG/`long_name`, with three FATES cases where the description misleads
  (`fates_allom_l2fr` reversed, `eca_alpha_ptase` inactive, `use_fates_nocomp` misread).
- 2026-08-03: Log step now states the **living-record** contract (start at phase start, enrich as it
  runs — the operational detail is unrecoverable later), names **this phase's expected sections** so an
  omission is visible in the log, and shows `set_phase_handshake()` so the reasoning chain is traceable.
  Added a **Before you finish** discipline self-review. Full contract: `calibration-log`.
- 2026-07-17: Evidence-gate bullet now requires a SELF-DOCUMENTING `phase_results/{stem}/` (figure + caption + saved generating .py + data), not just one artifact; the gate WARNs on a lone under-documented figure. Phase 4/6 mirror it. See `calibration-log` "different jobs" note. Ported from adapter-kit `3d187c3`.
- 2026-07-15: Named `tools/fates_utils` as the canonical per-PFT/SZPF helper for a custom diagnostic script (don't hand-roll `(pft-1)×13`), and added a trajectory-view cross-ref to the whole-ensemble time-series comparison (`plot_ensemble_cases.py --combined`, Phase 2 Step 1b) as a complement to the per-case `plot_diagnostics.py`. Ported from demo `ac4c125`+`b11162a`.
- 2026-07-06: Noted the middle-loop counter at the 6→3 re-entry (`experiment_count` incremented on the route;
  fresh `skip_testing_count`). Pairs with the Phase-6 middle-loop gate. Ported from demo `2d3f4b0`.
- 2026-07-06: Added "Working discipline (Phase 3↔4)" — integrated-story logs, read-your-source-before-upstream-git (generalized off demo's FATES-branch phrasing), keep the inner loop turning while sims run, and the log-stem-is-canonical invariant (now backed by `PhaseLogger` offline mode, v2.115). Ported from demo, scrubbed of Kougarok worked examples. Mirrored in `phase4-hypothesis`.
- 2026-07-02: Created — offline Phase 3 routine mirroring `reasoning.diagnose()`; composes `diagnose-forensics` (triage), `calibration-log` (phase log), hands off to `phase4-hypothesis`.
