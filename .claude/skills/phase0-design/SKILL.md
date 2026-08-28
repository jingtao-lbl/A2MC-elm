---
name: phase0-design
visibility: public
category: phase
description: Run Phase 0 (DESIGN) of the A2MC calibration workflow as the offline agent — the human-in-the-loop analog of the orchestrator's `_run_design()`. Sample the parameter space (Morris/Sobol/LHS), materialize one FATES parameter file per case, generate + build + submit the ensemble, and arm monitoring. Use when the user says "design a new round", "set up the ensemble", "sample the parameters", "submit the Morris ensemble", "start a calibration round", "expand the parameter space (redesign)".
modes:
  requires_fates: false      # calibration-workflow phase skill; mode resolved at runtime via describe_mode
  nutrient_pathway: any
  scope: [calibration]
  summary: "Offline analog of online Phase 0 (design/sample/submit the ensemble). Applies in every calibration mode."
---

# Phase 0: Design & Submit (offline agent)

> **Driven by `calibration-goal`** — the run-to-convergence driver dispatches here when `WorkflowStateOffline.current_phase` routes to this phase; do the phase, then update + `save()` the state so the driver advances. Also runnable standalone (one phase).

The offline analog of the orchestrator's `_run_design()`. Online this is deterministic sampling +
submission; offline **you own the design decisions** the online loop takes from config — scheme,
trajectory count, which parameters vary, bounds, and whether this is a fresh round or a
redesign/replay. The underlying scripts are the same the online agent drives.

> **Floor, not ceiling.** This skill is the minimum to stand up a round the way the online agent
> would. As the offline agent you can do more: reconsider the parameter list itself, add or widen
> bounds a redesign implies, sanity-check the sampling against prior-round μ* before spending
> compute, or design a targeted sub-ensemble the fixed loop would never propose. Match the
> discipline (verify param existence, don't clobber the committed matrix, validate before submit),
> then exercise judgment about *what* to sample.

**Deliverable:** simulation jobs queued (ADSP→RGSP→TRANS dependency chains), `submission_manifest.json`
written, monitoring armed.

## Opening a NEW round (redesign, Phase 6 → 0, `calibration_round++`)

Arriving here from Phase 6 with the middle loop exhausted (or all candidates pinned at bounds) is the
**redesign** path — a whole new round on a corrected base, not another cycle. Stand it up in this order
**before** Step 1 (sampling); each round is a *superset* of the last, recorded, not an in-place edit:

0. **Gate first (authorization).** The redesign must be an explicit human-gated Phase-6 decision:
   `phase6_decision.decision == "redesign_6to0"` recorded on the **previous** round's
   `workflow_state_offline_r{RR}.json` and passing `validate_phase6_decision()`. Do NOT open a new round
   while the prior gate is still `null` (that is "closed at the gate, awaiting the PI", not "go"). The
   round's next-round plan (the round-summary report's plan section) is the design input.
1. **Per-round config wrapper `{site}_config_r{N}.sh`.** Rounds do NOT get a separate full config — they get
   a thin wrapper that **sources the base `{site}_config.sh` and overrides only the round-specific env**:
   `A2MC_ENSEMBLE_NAME` (→ `R{N}_...`), `A2MC_PARAM_LIST_FILE` (→ the R{N} list), **`A2MC_BASE_PARAM_FILE`
   (→ the round's corrected/best base, NOT the prior dead/stale base)**, and the output/param/case-scripts
   paths. Override AFTER sourcing. (Precedent: Kougarok `kougarok_config_r3.sh`/`_r4.sh`/`_r5.sh` — note
   those wrappers are **unpadded** `_r{N}`, while the offline state file below is **padded** `_r{RR}`.)
2. **The R{N} parameter artifacts** (the point of the redesign — the changed parameter set): a new
   param-list CSV implementing the plan (add dominant levers, drop insensitive ones, recenter/widen bounds)
   + its salib_problem. Step 1 then generates the design matrix from this CSV, using the round's sampling method (Morris / Sobol / LHS). Never reuse the prior round's
   committed matrix (Step-1 overwrite footgun).
3. **Add round N to `calibration_rounds.yaml`.** With the R{N} config sourced, run the FATES round-record
   generator `tools/generate_calibration_rounds.py --round N --write` (an adapter model on the adapter-kit
   branch has its own parallel generator) — it derives the block from the config + CSV + targets; then
   hand-fill the preserved narrative (`rationale`, `changes_from_previous`). Validate with the paired checker.
4. **New offline state `workflow_state_offline_r{RR}.json`.** A fresh per-round singleton
   (`tools/workflow_state_offline.py`) with `calibration_round = N`, `current_phase = "design"`. The driver
   then resolves the next action against the new round.
5. **Then proceed to Step 1** below on the new round (sample → materialize → validate → submit) with the
   R{N} config sourced — a **fresh** sensitivity screen on the corrected base (a prior round's μ* sampled
   around a stale/dead base is void). Log the redesign rationale in Step 5.

## Step 0.5 — design the parameter set (REQUIRED, every Phase 0)

**Do this before Step 1, every round — not only a redesign.** Step 1 samples whatever the parameter
list says, so this is the decision that determines everything after it. **Round 1 is not exempt:** it
must equally state what is deliberately *not* calibrated and where its bounds came from. Answer all
three **in the log**, not just in the round record.

**ADD — each new parameter, with the evidence for it.** Prior-round μ\*, a Phase-3 diagnosis, or a
mechanism the previous screen never varied. A lever nothing measured is a guess.

**DROP — each removed parameter, AND the fixed value it now takes, AND where that value comes from.**

> ⚠️ **A dropped parameter does NOT fall back to the parameter list's `default` column** — that column
> is documentation. `generate_parameter_files.py` copies `$A2MC_BASE_PARAM_FILE` and applies only the
> sampled-matrix edits, so **dropping a parameter transfers control of its value to the base file.**
> Verify the base carries the value you intend, and say so in the log.
>
> On this branch that base is a **site-tuned** file, not the FATES default — see
> [[feedback_port_tuned_base_param_file_across_versions]], whose sharp edge is exactly a
> non-calibrated parameter carrying a value nobody re-checked (grass `dbh_repro_threshold` 0.35 vs
> 3.0). A parameter dropped from the list inherits whatever that file says.

**BOUNDS — where each lower/upper came from.** Not "default ±50%": a literature range, a prior μ\*
sweep, or a physical limit, recorded per parameter
([[reference_param_bounds_sourcing_pipeline]]).

## Step 1 — sample the parameter space (parameter-file prep — no simulations)

`phases/phase0_design/create_parameter_sample.py --method {morris|sobol|lhs}` reads
`$A2MC_PARAM_LIST_FILE` (name + bounds) and writes the ensemble matrix (`$A2MC_ENSEMBLE_MATRIX_FILE`)
and SALib problem (`$A2MC_SALIB_PROBLEM_FILE`). Morris: `--trajectories T` (N = T×(P+1)).

> **Footgun — matrix overwrite.** `$A2MC_ENSEMBLE_MATRIX_FILE` for Kougarok points at the
> **committed, byte-stable 4890-set matrix the manuscript depends on**. To regenerate without
> clobbering it, write to a scratch path (`--output-matrix`) or repoint the env var to a fresh
> round file first.

**Redesign / replay** (reuse a prior round's NC dir instead of fresh sampling):
`apply_param_override.py` (global override, e.g. R5's `prescribed_puptake=1.0` onto R3's NCs) or
`create_subset_replay.py` (top-N replay preserving source case numbers).

## Step 2 — materialize per-case parameter files (parameter-file prep — no simulations)

`phases/phase0_design/generate_parameter_files.py` reads the X matrix + `$A2MC_BASE_PARAM_FILE` and
writes one parameter file per row into `$A2MC_PARAM_DIR` (pattern `$A2MC_PARAM_PATTERN`, `{N}`
placeholder). It is **method- and format-agnostic** (JSON at api-43+, NetCDF at api-31 and earlier)
and dispatches to `tools/modify_fates_parameters.py` for the per-parameter edits. Verify file
count = N_sets.

> **Footgun — column↔parameter mapping + file format.** The X-matrix column order must match the site
> parameter list; `build_param_lookup()` in `tools/modify_fates_parameters.py` maps each shorthand →
> FATES name + PFT + organ. Confirm `tools/describe_mode.py` shows the milestone you expect so the
> right parameter-file format (JSON vs NetCDF) is written. Never assume a column's meaning.

## Step 3 — generate scripts, build, submit the simulations

`phases/phase0_design/submit_phase0.py --start 1 --end N --dry-run` first (preview), then `--submit`.
It (3a) writes per-case scripts via `tools/create_case.sh --write-script`, (3b) auto-validates via
`tools/validate_submission_plan.py`, (3c.1) builds ONE case fresh (~30 min), (3c.2) runs the rest in
`--batch-size` parallel batches reusing the build's `bld/`. Non-sequential rounds: `--cases-file`.

> **Footgun — build-case reuse.** All cases share the build case's `bld/`. If the build case fails,
> every dependent case is orphaned — confirm it completed before the batch. Restart it separately,
> then `--skip-build-case --build-case N`.

## Step 4 — arm monitoring, don't idle-wait

Launch `tools/ensemble_auto_monitor.sh` (queue polling + auto extraction kick + **extraction-progress
ensemble plots** — it triggers `tools/regen_ensemble_milestone_plot.sh`, a thin wrapper over
`tools/plot_ensemble_cases.py`, each time the extracted-case count crosses a checkpoint →
`R{N}_{combined,TRANS}_{count}cases_ensemble.png`, [[reference_ensemble_combined_plot_pipeline]]; these are
in-flight progress snapshots of the running ensemble, not a graduated result),
then hand monitoring setup to `arm-hpc-monitoring` (CLAUDE.md Rule #6). Point-in-time completion:
`tools/diagnose_ensemble_status.py --cases 1-N` (writes completed/incomplete lists + a validated
restart script). Infrastructure failures → `restart-failed-jobs`; model failures need a fix first.

## Step 5 — log it and hand off

> **The log is a LIVING record — start it now, enrich as the phase runs.** Not an end-of-phase
> write-up: the operational detail (job/array IDs, which cases failed, what was restarted) is
> unrecoverable a week later. Full contract in `calibration-log`.
>
> **This phase's expected sections** — `PhaseLogger` names any you leave empty:
> Sampling Design · Cases Materialized · Submission · Simulation Status · Monitoring Armed · Failures and Restarts · Verification Plots.
>
> **Set the handshake before the `log_*` call**, so the chain is traceable:
> ```python
> logger.set_phase_handshake(
>     inherited_from="<predecessor log STEM> — what it concluded / asked of this phase",
>     handed_to="<what Phase 1 receives; mirror the reasoning/schemas.py field names>",
>     next_action="<the one concrete thing Phase 1 should do>")
> ```
> The log also carries `## Reasoning chain`, rebuilt from `workflow_state_offline` — so keep that
> state updated with the FINDING, not a label; the chain is only as good as what each phase wrote.


Log via `calibration-log` (phase log → `PhaseLogger.log_design`): scheme, N cases, param dir,
manifest hash, any redesign rationale. **Offline logging convention:** set **`A2MC_AGENT_MODE=offline`**
so the log lands FLAT at `use_cases/<site>/memory/logs/{YYYYMMDDx}_phase0_design_r{RR}_{descriptor}.md`
(docs/31) — NOT the online `{session_id}/phase0_design/` nested path. **Hand off** to `phase1-exploration`
once TRANS is >95% complete. **Advance the driver state:** `st.set_position(current_phase="exploration")`;
`st.save()` (`tools/workflow_state_offline.py` — the offline analog of the online phase transition, so
`resolve_next_action` picks up `exploration` next). (Arrived here from Phase 6 with all candidates pinned at
bounds? That's the 6→0 redesign — widen bounds / add parameters and start a new `calibration_round`.)

> **Design can be PREPARED but HELD.** If the base case doesn't even establish (e.g. a ported/calibrated
> base that N-starves and collapses over spin-up, with no viable ensemble to sample around), the round is
> designed (targets + params + bounds + extraction) but **not submittable** — do NOT force an ensemble.
> Record the hold: keep `st.set_position(current_phase="design")` and add a priority-1 open thread naming the
> precondition to clear (`st.add_thread("<blocker>", summary=..., next_action=<what unblocks submit>,
> priority=1)`); `save()`. The driver then surfaces that thread instead of a phantom "submit" step. (Worked
> FATES example: the api-43 `p2939uni` base collapses on nitrogen — `20260715c` — so an api-43 round stays
> designed-but-held pending a viable base.)

## Before you finish

**Discipline self-review (automatic).** Before advancing the state, re-check the [`calibration-discipline`](../calibration-discipline/SKILL.md) items that apply to this phase. This is unprompted and per-phase — the user does not have to ask (memory `feedback_schedule_periodic_reviews_with_a_real_mechanism`).

## Related skills / next phase

- **`plotting`** — load it **before your first `savefig`**, not after. Its rule 8 (*open the rendered PNG and LOOK at it*) is the only step that catches an overlapping legend, a stats box across the curve, or an unreadable axis, and it cannot catch them retroactively.

- **Monitoring the in-flight ensemble** → `arm-hpc-monitoring`. **Failed jobs** → `restart-failed-jobs`.
- **Rebuilding a new site/model's knowledge base first** → `build-rag-from-scratch`.
- **Next:** `phase1-exploration` (extract Y matrix + Morris sensitivity).

## Changelog

- 2026-08-23 — Added **Step 0.5 — design the parameter set (REQUIRED, every Phase 0)**, with the ADD / DROP / BOUNDS questions answered in the log. Adopted from `adapter-kit` (`659d0498`), re-authored. The load-bearing warning: a dropped parameter does NOT fall back to the list's `default` column — `generate_parameter_files.py` copies `$A2MC_BASE_PARAM_FILE` and applies only the matrix edits, so dropping a parameter transfers control of its value to the base file. On this branch that base is site-TUNED, which is the sharp edge in `feedback_port_tuned_base_param_file_across_versions`.

- 2026-08-03: Log step now states the **living-record** contract (start at phase start, enrich as it
  runs — the operational detail is unrecoverable later), names **this phase's expected sections** so an
  omission is visible in the log, and shows `set_phase_handshake()` so the reasoning chain is traceable.
  Added a **Before you finish** discipline self-review. Full contract: `calibration-log`.
- 2026-07-18: Added **"Opening a NEW round (redesign, Phase 6 → 0)"** — the explicit pre-Step-1 setup to
  stand up round N+1: the redesign gate (prior round's `phase6_decision == redesign_6to0`), the per-round
  config **wrapper** `{site}_config_r{N}.sh` (sources base + overrides ensemble/param-list/**base-param-file**),
  the R{N} param-list CSV + salib_problem, adding round N to `calibration_rounds.yaml`, and a fresh
  `workflow_state_offline_r{RR}.json` — then sample on the corrected base. Ported from adapter-kit `6aff7cd`
  (distilled from the demo Kougarok multi-round wrappers + the EcoSIM R1→R2 plan); Kougarok config precedent
  restored in the wrapper example.
- 2026-07-15: Two adapter-kit refinements ported from `b53ce21` (generic — surfaced in its EcoSIM R1
  dogfood): (1) the **offline logging convention** made explicit in Step 5 (`A2MC_AGENT_MODE=offline` → flat
  `memory/logs/{stem}.md`, not the online nested `{session_id}/phase0_design/`); (2) a **PREPARED-but-HELD**
  note — a round can be designed yet un-submittable when the base case doesn't establish (record via
  `current_phase="design"` + a priority-1 open thread), with the api-43 `p2939uni` N-collapse as the FATES
  worked example. **Not ported:** adapter-kit's non-FATES `ModelBackend` branch for Steps 2-3 (main is
  FATES-only; it references `backend.write_parameter_file`/`reduce_ecosystem` infra main lacks).
- 2026-07-15: Wired the explicit `set_position(current_phase="exploration")` state-advance in the handoff step (the offline program-counter advance main's generic banner lacked). Ported from demo `d3cbbf5` (offline-workflow enforcement sweep).
- 2026-07-15: Named the concrete progress-plot tool chain in Step 4 — `ensemble_auto_monitor.sh` → `regen_ensemble_milestone_plot.sh` → `plot_ensemble_cases.py` at each extracted-case checkpoint (was vague "milestone plots"); reworded to **extraction-progress ensemble plots** (in-flight snapshots, not a graduated result). Ported from demo `cd14d24`/`b85fc2c`, adapted — main has no promote-milestone layer to contrast against.
- 2026-07-02: Created — offline Phase 0 routine mirroring `_run_design()`; drives create_parameter_sample → generate_parameter_files → submit_phase0, delegates monitoring/restart, hands off to `phase1-exploration`.
