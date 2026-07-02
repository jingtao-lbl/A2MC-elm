---
name: phase3-diagnosis
description: Run Phase 3 (DIAGNOSIS) of the A2MC calibration workflow as the offline agent — the human-in-the-loop analog of the autonomous orchestrator's `_run_diagnosis()` / `reasoning.diagnose()`. Systematically root-cause WHY the screening round is missing its validation targets: gather diagnostic data with the phase3 tools, pull RAG + Adaptive Memory context, then reason to a structured diagnosis (failing targets, likely causes, ranked root causes, parameter recommendations, base cases, hypotheses) and hand off to Phase 4. Use when the user says "diagnose the failing targets", "run Phase 3", "why aren't the targets calibrating", "root-cause this round", "what's driving the PFTx miss", after screening (Phase 2) hands off a ranked ensemble.
---

# Phase 3: Diagnosis (offline agent)

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

Structure follows `templates/reasoning/phase3_diagnosis_template.md`. Cross-check every mechanism
claim against RAG before writing it down.

## Step 4 — cheap test first? (skip-testing inner loop, Phase 3↔4)

If a hypothesis can be tested against the **existing** Morris ensemble (a correlation, a
high-vs-low group contrast, a threshold) — do that instead of queuing a new simulation. That is the Phase 3↔4
skip-testing inner loop: hand the hypothesis to `phase4-hypothesis`, which decides
`test_with_existing` vs a new simulation. Only real parameter values outside the ensemble range need Phase 5.

## Step 5 — log it and hand off

- **Log** via `calibration-log` (phase log → `PhaseLogger.log_diagnosis`, byte-identical to the
  autonomous agent so both modes' logs synthesize). Capture failing targets, ranked root causes,
  parameter recommendations, selected base cases, hypotheses, and the RAG/Memory evidence.
- **Hand off** to `phase4-hypothesis` with the base cases + hypotheses. (If you came here from
  Phase 6 to rethink a disproven hypothesis, that's the 6→3 experiment-cycle loop — same routine.)

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

## Related skills / next phase

- **Reactive anomaly** (one outlier, not the whole round) → `diagnose-forensics`.
- **Manuscript-grade investigation of a finding** → `scientific-analysis`.
- **Next:** `phase4-hypothesis` (turn the diagnosis into testable experiments).

## Changelog

- 2026-07-02: Created — offline Phase 3 routine mirroring `reasoning.diagnose()`; composes `diagnose-forensics` (triage), `calibration-log` (phase log), hands off to `phase4-hypothesis`.
