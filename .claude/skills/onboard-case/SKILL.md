---
name: onboard-case
visibility: public
category: calibration
description: Create a NEW calibration case (a site or project) in a clone where A2MC is ALREADY configured — the repeatable half of getting started. Interview from the science goal, resolve the case SCALE, draft the research plan, scaffold use_cases/<Case>/ from the site-agnostic TEMPLATE, build or vet the parameter list, run the readiness preflight, hand off to Phase 0. Use when the user says "set up a new case", "add a site", "calibrate a second site", "start another case", "onboard my site". NOT first-run machine setup in a fresh clone (use a2mc-init) and NOT resuming an existing setup (use onboard-session).
modes:
  requires_fates: false
  nutrient_pathway: any
  scope: [setup]
  summary: "Repeatable per-case onboarding in an already-configured clone — interview, resolve case scale, research plan, scaffold from TEMPLATE, param list, preflight, Phase 0. Single-point only today; transect/regional is a HARD STOP."
---

# Onboard a Case (a new site or project)

The repeatable half of getting started. `a2mc-init` is the **first-run** flow for a fresh clone and does the once-per-machine work — verify the model checkout, offer fork-safe remotes, set up `a2mc_config.sh`. Once that is done it never needs doing again, and dragging a user back through it to add their second site is noise.

This skill is everything after that: **one case, start to Phase 0.**

| Skill | When |
|---|---|
| `a2mc-init` | first time in this clone — machine config, checkout, remotes, then the first case |
| **`onboard-case`** (this) | every case after that |
| `onboard-session` | resuming a case that already exists |

> **`a2mc-init` remains authoritative for the interview and scaffolding substance.** This skill does not fork that content — Steps 1, 3, 3b, 4 below are the same procedure, and where they differ `a2mc-init` wins. What is genuinely new here is **Step 2, the scale gate**, and the removal of the machine-setup steps.

## Step 0 — Confirm the clone is already configured

```bash
git branch --show-current
source a2mc_config.sh && echo "A2MC_ROOT=$A2MC_ROOT  MODEL_PATH=$A2MC_MODEL_PATH"
ls use_cases/                       # what already exists — do not collide with it
```

If `a2mc_config.sh` is missing or `A2MC_MODEL_PATH` is unset, **stop and route to `a2mc-init`** — this skill assumes the machine layer is done. If the clone has no `use_cases/` entries at all, this is a first run: also route to `a2mc-init`.

## Step 1 — Interview, starting from the science goal

Follow `a2mc-init` Step 1 and `docs/a2mc_reference/a2mc_init_interview_questionnaire.md`. The order matters: **goal → target granularity → PFTs/targets/parameters**, never model internals first. Do not re-ask what the machine config already answers (HPC project, output root, Python env, model checkout).

## Step 2 — Resolve the case SCALE ★ (ask, never assume)

**Ask explicitly. Do not infer it from the site name or from a lat/lon the user happens to mention.**

> *"Is this one location, a set of locations, or an area?"*

| Answer | Meaning | Status |
|---|---|---|
| **Single point** | one lat/lon, one CIME case per ensemble member | **supported — continue to Step 3** |
| **Transect / multi-site** | an ordered or unordered series of points calibrated together | **HARD STOP — not supported today** |
| **Regional / gridded** | an area, a domain, a set of gridcells | **HARD STOP — not supported today** |

**On a HARD STOP, say so plainly and do not scaffold anything.** A2MC is single-point end to end today, and a case scaffolded as if it were single-point will silently calibrate one location while the user believes it covers many — the worst available failure, because every downstream artifact looks correct.

What is actually single-point, verified rather than assumed:

- **the targets schema has no spatial axis at all** — an observation is a scalar or a *time* series, with no way to say which point it belongs to (`evaluate_case.py`'s `n_points` is the **temporal** axis: `SNAPSHOT if n_points == 1 else TIME_SERIES`)
- **scoring collapses the grid** — `np.squeeze` in `evaluate_case.py`, then a scalar cost per member; there is no per-point cost and no rule for combining points
- extraction is **not** the blocker: `tools/extract_monthly_variables_FATES.py` explicitly preserves the grid axis (*"`time` and `lndgrid` are NEVER stripped"*)
- `A2MC_SITE_LAT` / `A2MC_SITE_LON` are **decorative** — exported by the configs but consumed by nothing; the real spatial definition is `A2MC_DOMAIN_FILE` / `A2MC_SURFACE_FILE` / `ELM_USRDAT_NAME`. Do not treat editing them as changing the run's extent.

**Do not work around it** by scaffolding N separate cases and calling that a transect. That produces N independent calibrations with no shared parameter set and no joint objective, which is not what a transect calibration means. If the user wants that, it is a deliberate choice to state in the research plan, not a default to slide into.

Route a HARD STOP to the multi-point scoping work rather than improvising (see Cross-references). **A gridcell- or tower-aggregate *observation* is still a single-point case** — that is about the footprint of the measurement, not the extent of the run, and `a2mc-init` Step 1 already covers mapping it to an ecosystem-level target.

## Step 3 — Draft the research plan, confirm, then scaffold ★ GATE 1

Write `use_cases/<Case>/research_plan.md` and **get explicit confirmation before creating any config**. Building config before the plan is confirmed is the footgun `a2mc-init` calls out, and it is worse here: a second case invites copying the first one's answers.

**Name the case `{Model}_{Site}`** — `ELM-FATES_Kougarok`, not `Kougarok`. The same site gets calibrated under different model configurations (`ELM_Kougarok` for ELM-only), and those are different cases with different parameters, targets and results; a bare site name collides the moment the second one appears. Hyphens belong to the model half, underscore separates the halves (matches `adapter-kit`'s `<Model>_<Case>`). **`A2MC_SITE_NAME` must equal the directory name**, since `A2MC_USE_CASE_DIR` derives from it.

```bash
DEST="$A2MC_ROOT/use_cases/<Case>"
cp -r "$A2MC_ROOT/use_cases/TEMPLATE" "$DEST"
# Arctic/tundra? offer use_cases/ELM-FATES_Kougarok as a working 3-PFT seed instead of the bare TEMPLATE

# ★ DROP THE `template_` PREFIX — both files, or the case is broken:
mv "$DEST/config/template_config.sh"             "$DEST/config/${CASE,,}_config.sh"
mv "$DEST/config/template_calibration_rounds.yaml" "$DEST/config/calibration_rounds.yaml"
```

**Both renames are required, for different reasons.** The site config is sourced by an explicit `<case>_config.sh` path, so leaving it prefixed just means nothing sources it. `calibration_rounds.yaml` is worse: **43 call sites look it up by that exact fixed name**, so a case that keeps the prefix has no round record as far as the framework is concerned — and `tools/generate_calibration_rounds.py --write` will then create a *second*, empty one beside the prefixed copy, leaving two files where the stale one carries an authoritative-looking instructional header. TEMPLATE's own file states the rule in its first lines; follow it.

**Check the run configuration before editing anything else.** `template_config.sh` is written for **FATES + CNP + ECA** and hardcodes that in at least five places — `A2MC_ELM_OPTIONS` (line 141), `A2MC_FATES_PARTEH_MODE=2` (142), the FATES-tree `A2MC_BASE_PARAM_FILE` (158), the `fates_params_*` `A2MC_PARAM_PATTERN` (165), and `A2MC_ENSEMBLE_NAME` (172). A2MC supports ELM **with or without** FATES, and carbon-only as well as CNP, so **a case that is not FATES+CNP+ECA must correct all five**. None of them errors when wrong — the config sources cleanly and the FATES paths are simply meaningless.

Naming: `use_cases/<Case>/` — a short, unambiguous case name. Check `ls use_cases/` from Step 0 first; a collision silently merges two projects' state.

Populate from the interview, never by hand-copying values that live in config ([[feedback_case_template_should_source_config]]). **Never invent a target value or a data path** — placeholders marked `TODO` are correct, fabricated numbers are not.

## Step 3b — Build or vet the parameter list ★ GATE 2

Follow `a2mc-init` Step 4b. Bounds come from the sourcing pipeline, not from a default ±50% ([[reference_param_bounds_sourcing_pipeline]]). Verify PFT identity against the base parameter file rather than trusting ids from another case ([[feedback_verify_pft_identity_across_versions]]) — **a second case is exactly where a copied PFT id goes wrong**, since the ids are not stable across model versions and the new case may not share the first one's.

Do not hand-author `calibration_rounds.yaml`; generate it (`tools/generate_calibration_rounds.py`).

## Step 4 — Preflight, then hand off to Phase 0

```bash
python tools/check_setup_ready.py        # goal-conditional readiness gate
python tools/validate_param_list.py
```

Both must pass. Then hand off to `phase0-design`.

## Step 5 — Log the setup ★ (this is the case's origin record)

Invoke **`calibration-log`** and write a **free-form session log** under
`use_cases/<Case>/memory/logs/` — offline mode gives the flat `logs/{stem}.md` layout,
`stem = YYYYMMDDx_<descriptor>`. It sits alongside the autonomous agent's own logs, so both
modes' records synthesize together later.

**Log the decisions, not the file list** — the reasoning is what nothing else preserves:

- **the run configuration** and why (FATES on/off, PARTEH mode, nutrient pathway);
- **the PFTs**: which functional types this case calibrates, **their ids in THIS model version**,
  and how they were verified against the base parameter file's `fates_pftname` — ids are not stable
  across versions ([[feedback_verify_pft_identity_across_versions]]);
- **each parameter**: the full model name, the target it serves, the mechanism, and where the bound
  came from — including any candidate **rejected** and why (an inert parameter, a mode switch, a
  transform);
- **the targets**, their sources and uncertainties, and anything left `TODO`;
- **the sampling method** chosen and the cost that justified it.

**Why this matters more than it looks.** Config files record *what* was chosen; only the log records
*why*, and the why is what a later session needs when a bound looks wrong or a PFT id stops matching.
The parameter list and the PFT-id mapping are the two things most likely to be questioned months
later — a case whose origin log names them, with their evidence, can be re-derived; one without it
cannot, and the values become unfalsifiable ([[feedback_bind_derived_facts_to_their_source]]).

Curated *findings* are a different lane: they belong in `use_cases/<Case>/memory/gained_knowledge/`
through the human-gated review path, never hand-written ([[feedback_no_case_state_in_memory]]).

## Footguns

- **Assuming the scale.** Step 2 exists because the assumption is invisible once made and every artifact downstream still looks right.
- **Copying the previous case's answers.** PFT ids, targets, bounds, and paths are per-case. A second case is where copied values look plausible and are wrong.
- **Re-running the machine setup.** If you find yourself asking where the E3SM checkout is, you are in `a2mc-init`'s territory, not this skill's.
- **Fabricated targets or paths** — the single most damaging onboarding error. `TODO` placeholders, never invented numbers.
- **Validation data in `targets.yaml` — it gets SCORED.** `targets.yaml` is **calibration-only**: every entry in it is scored and drives parameter optimization. Diagnostic observations you only want to *compare against* do not belong there — put them in **`use_cases/<Case>/validation/data/`** — which holds **all** raw observation files, both roles — and read them with a purpose-built script (`diagnose-forensics` / `scientific-analysis` / `plotting`), producing model-vs-obs figures and an ana_log. Nothing errors if you get this wrong; the round simply starts optimizing toward data you meant as a cross-check. **The folder name is the trap**: `use_cases/<Case>/validation/` holds *calibration* targets. The split is now explicit — `validation/targets.yaml` is the **spec** (what is scored), `validation/data/` is the **data** (every raw file, whatever its role). What makes an observation a calibration target is that `targets.yaml` names it, nothing else. Decide the role of every observation before writing it anywhere: *must the model MATCH this, or am I only checking it?* Worked split — Kougarok's PFT leaf/fineroot biomass are calibration; its MODIS GPP/LAI and soil T/moisture are validation and are deliberately **not** wired into `evaluate_case`/`cost_config`.
- **Bad target keys — dropped SILENTLY.** A target name that does not resolve to an NC variable is discarded at runtime with no error: the round then optimizes against fewer targets than the research plan claims, and every artifact still looks correct. Valid shapes are `PFT<id>_<vartype>` (`PFT10_leaf`), `ECO_<var>` (`ECO_gpp`), `SNOW_<var>` (`SNOW_snowdp`). **Run `python tools/validate_targets_config.py`** — its R1 check exists for exactly this. Note this key is *not* the retired parameter shorthand: a parameter carries `pft`/`organ` as CSV columns, while a target embeds the PFT id because the target itself is per-PFT and has nowhere else to put it.
- **Over-asking a new user.** Do not demand dominant PFTs, per-PFT biomass, or a parameter list when the goal is **ecosystem-level** — those are PFT-level requirements. Ask for what the stated goal needs and no more; an interview that demands unavailable detail stalls onboarding for no gain.
- **Treating a leftover check as a hard failure.** `check_setup_ready.py` is **goal-conditional**: `N/A` on the PFT inventory is the correct result for an ecosystem-level goal, not something to satisfy. Read what each check is conditioned on before chasing it.
- **Skipping GATE 1.** Config written before the plan is confirmed gets defended rather than revised.

## Cross-references

- `a2mc-init` — first-run setup; authoritative for the interview and scaffolding substance this skill reuses.
- `onboard-session` — resuming an existing case.
- `phase0-design` — the hand-off target.
- `calibration-goal` — drives the full loop once Phase 0 is designed.
- `docs/a2mc_reference/a2mc_init_interview_questionnaire.md` — the question bank.
- Memory: [[feedback_case_template_should_source_config]], [[reference_param_bounds_sourcing_pipeline]], [[feedback_verify_pft_identity_across_versions]], [[reference_a2mc_init_flow_order]].
- **Multi-point and regional scoping** — `docs/39_MultiPoint_And_Regional_Case_Scoping.md` is the scoping behind Step 2's HARD STOP — what blocks it, what does not, and the four open questions. Until those are answered, transect and regional cases have no supported path.

## Changelog

- 2026-08-19: Initial version. Split out of `a2mc-init` once the PI confirmed `main` will host many cases — additional sites, transect-scale, and regional. Reuses `a2mc-init`'s interview and scaffolding rather than forking them, drops the once-per-clone machine setup, and adds **Step 2, the scale gate**, which is new to both branches: `main` is single-point end to end (scalar `A2MC_SITE_LAT`/`LON`, one `observed` per target, single-location extraction and scoring), so transect and regional are a hard stop rather than an unstated assumption. Structure follows `adapter-kit`'s `onboard-case`; the model axis (`<Model>_<Case>` naming, per-model templates) is deliberately dropped, since this branch is FATES-family only.
