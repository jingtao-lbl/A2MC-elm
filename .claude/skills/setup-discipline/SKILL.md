---
name: setup-discipline
visibility: public
category: calibration
description: The per-STAGE definition-of-done checklist for the setup arc — is a2mc-init or onboard-case actually finished, or does it only look finished? Use when a setup stage is ending, when picking up a clone someone else configured, when a session says "setup is done" and you want that verified, or when onboarding stalled and you need to know what is missing. Collects the gates each setup skill names inline so a stage can be CLOSED, not just performed. Does not re-teach the stages.
modes:
  requires_fates: false
  nutrient_pathway: any
  scope: [setup]
  summary: "Per-stage definition-of-done checklists for the setup arc (a2mc-init / onboard-case), each item pointing at the step or tool that owns it. A checked box means the check was RUN."
---

```text
Which stage am I in?  ─┬─ clone NOT configured ................ Stage 1  a2mc-init
                       ├─ configured, need another case ....... Stage 2  onboard-case
                       └─ configured + a case in flight ....... (not setup) onboard-session

A stage is DONE only when every [ ] is checked, or explicitly N/A with a reason.
```

# setup-discipline — is this setup stage actually finished?

`a2mc-init` and `onboard-case` name their gates **inline, inside their steps**. That makes each stage easy to *perform* and hard to *finish*: nothing collects "what does done mean here", so a stage gets abandoned mid-way and the next session inherits a clone that **looks** configured and is not.

This skill is the collector. It does not re-teach the stages — each item points at the step or tool that owns it.

**Why a half-done stage is worse than one not started: the failure is silent.** A missing fork-guard is invisible until someone pushes to upstream. An unmatched RAG milestone is invisible until the reasoning agent answers from the wrong model version. A `targets.yaml` whose keys never resolved is invisible until Phase 2 scores nothing. Each is cheap to check now and expensive to discover later.

## Step 0 — establish which stage you are in (always first)

**Do not infer the stage from what the user says they want — it is checkable on disk.**

```bash
ls use_cases/                      # only TEMPLATE/ = no real case yet
ls a2mc_config.sh 2>/dev/null      # machine layer written?
echo "${A2MC_MODEL_PATH:-<unset>}" # required; the orchestrator hard-fails without it
python3 scripts/rag_match.py       # does THIS checkout match a registered milestone?
python3 tools/describe_mode.py     # resolved run configuration
```

| what you find | stage | skill |
|---|---|---|
| no `a2mc_config.sh`, or `A2MC_MODEL_PATH` unset, or `use_cases/` holds only `TEMPLATE/` | **1** | `a2mc-init` |
| machine layer done, ≥1 real case exists, user wants **another** | **2** | `onboard-case` |
| a case exists and work is in flight | — | `onboard-session` |

> **Main has no `onboard-model` stage.** This branch is the ELM family (ELM with or without FATES), configured through `A2MC_ELM_OPTIONS` rather than by adapting a new model. Adding a *model* is `adapter-kit`'s line of work, and its `setup-discipline` carries that third stage.

## Stage 1 — `a2mc-init` is DONE when

The per-CLONE half. Owns the machine, the checkout and the routing — **not** the case.

- [ ] **Checkout verified and milestone MATCHED** — `python3 scripts/rag_match.py`. Report the detected ELM + FATES commits **and** the matched profile to the user; do not silently accept a near-match. A drifted checkout still answers from *some* profile, in another version's vocabulary.
- [ ] **Fork-safe remotes offered** on the model checkout (Step 2b) — `origin` push disabled, `fork` set. Verify **both** directions, not just that a `fork` remote exists ([[feedback_model_source_push_fork_only]]).
- [ ] **Machine config written** (Step 3) — `a2mc_config.sh`, with the HPC project, output root and Python env.
- [ ] **`A2MC_MODEL_PATH` set**, pointing at the checkout just verified. The orchestrator hard-fails on startup without it, so an unset value is not a soft warning.
- [ ] **Run configuration resolved and stated** — `python3 tools/describe_mode.py`. FATES on/off, PARTEH mode, nutrient pathway. TEMPLATE ships FATES+CNP+ECA; anything else must be corrected in five places, and none of them errors when wrong.
- [ ] **Routed onward explicitly** (Step 6) — say which stage comes next and why. Setup ends by handing off, never by trailing off.
- [ ] **Setup captured in a `calibration-log` session log** under `use_cases/<Case>/memory/logs/` (Step 5b) — mode, checkout, milestone, and the decisions behind them.

> **N/A rules.** Fork-safe remotes are N/A when the user has no write access to the upstream at all. Nothing else here is optional.

## Stage 2 — `onboard-case` is DONE when

The per-CASE half, repeatable for every new site or project.

- [ ] **Case SCALE resolved by asking** (Step 2) — one location, a set, or an area. Transect and regional are a **HARD STOP** on this branch (`docs/39`); a case scaffolded as single-point while the user believes otherwise produces artifacts that all look correct.
- [ ] **Target granularity established** — ecosystem-level vs per-PFT. This decides everything downstream. Valid target keys are `PFT<id>_<vartype>`, `ECO_<var>`, `SNOW_<var>`; **a key that does not resolve is dropped silently at runtime**. Run `python3 tools/validate_targets_config.py`.
- [ ] **PFT ids read from the base parameter file**, never carried over from another case or another API version ([[feedback_verify_pft_identity_across_versions]]). N/A for ecosystem-level targets.
- [ ] **Calibration vs validation separated** — only calibration data enters `targets.yaml`, where everything is scored. Raw observations of either role live in `use_cases/<Case>/validation/data/`; the role is decided by `targets.yaml` naming a file.
- [ ] **`research_plan.md` drafted and APPROVED** — ★ GATE 1. Nothing is written into the site config or `targets.yaml` before this.
- [ ] **Case scaffolded from `TEMPLATE`, and BOTH `template_` prefixes dropped** — `template_config.sh` → `<case>_config.sh`, `template_calibration_rounds.yaml` → `calibration_rounds.yaml`. The second is looked up by that **fixed name in 43 places**; keeping the prefix leaves the case with no round record.
- [ ] **Parameter list built or vetted from the mechanisms** (Step 3b) — ★ GATE 2. Full model names with explicit `pft`/`organ` columns, bounds from the sourcing pipeline rather than a default ±50% ([[reference_param_bounds_sourcing_pipeline]]). Verify with `python3 tools/validate_param_list.py`.
- [ ] **`calibration_rounds.yaml` present and consistent** — generated, not hand-authored (`tools/generate_calibration_rounds.py`). Check with `python3 tools/check_calibration_rounds.py`.
- [ ] **`python3 tools/check_setup_ready.py` exits 0** — the goal-conditional preflight. **`N/A` is a pass**; a `FAIL` is not. When it reports `✗`, run the specific validator directly, since the gate only reports pass/fail.
- [ ] **Handed off to `phase0-design`** with the sampling method and ensemble size agreed.
- [ ] **Setup logged** (Step 5) under `use_cases/<Case>/memory/logs/` — the PFT ids and how they were verified, each parameter's bound provenance including candidates **rejected** and why.
- [ ] **No auto-memory written about this case.** Case state belongs in the case's `gained_knowledge/`, `workflow_state_offline_r{NN}.json`, or `TODO.md` ([[feedback_no_case_state_in_memory]]).

## The rule that outranks the lists

**A checked box means you ran the check, not that you believe the item holds.**

Every line above naming a tool is executable. The ones without a tool are exactly the ones to state explicitly as done or N/A, **with the reason**, in the stage's log. An unrunnable claim recorded as "done" is how a half-built clone comes to look finished — and the next session trusts it.

## Cross-references

- `a2mc-init` — Stage 1; authoritative for how each item is done.
- `onboard-case` — Stage 2; likewise.
- `onboard-session` — resuming a case, not setting one up.
- `phase0-design` — the hand-off target for both stages.
- `docs/39_MultiPoint_And_Regional_Case_Scoping.md` — why transect/regional is a HARD STOP.
- `use_cases/TEMPLATE/validation/data/README.md` — the calibration-vs-validation split.
- Memory: [[feedback_model_source_push_fork_only]], [[feedback_verify_pft_identity_across_versions]], [[reference_param_bounds_sourcing_pipeline]], [[feedback_no_case_state_in_memory]].

## Changelog

- 2026-08-19: Initial version. Adopted from the `adapter-kit` branch (re-authored per `adopt-from-adapter-kit`, not copied). Adapted for this branch: **two stages, not three** — there is no `onboard-model`, since this is the ELM family configured through `A2MC_ELM_OPTIONS` rather than a set of adapted models; the non-CIME config choice and the model-registry checks are dropped; Stage 2 gains this branch's own gates (the **scale** HARD STOP, the **two template renames**, `validation/data/`). Upstream's executable half is **not** ported — `{adapter-kit branch}/tools/check_stage_ready.py` (316 lines, stdlib-only; read it with `git show origin/adapter-kit:tools/check_stage_ready.py`, no checkout needed). It auto-detects the stage and runs the mechanical half of the checklist without a sourced config, which is the point — `check_setup_ready.py` cannot run before a site exists. It is written around `models/<name>/register_model()`, per-model templates and a third stage, none of which exist here, so it needs a main-native rewrite rather than an adaptation. Recorded as a follow-up, not half-landed.
