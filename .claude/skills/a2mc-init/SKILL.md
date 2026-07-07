---
name: a2mc-init
description: First-run interactive setup for the offline agent — the official "getting started" flow the FIRST time someone uses A2MC in a repo/site. Interview the user (is a2mc_config.sh set up, where is the E3SM/ELM-FATES checkout, FATES on/off, carbon-only vs nutrient-enabled PARTEH, ECA vs RD, site name/location, PFTs, calibration targets), verify the checkout + RAG milestone, then create and populate the use case (site config + validation targets + parameter list) and hand off to phase0-design. Use when the user says "set up A2MC", "first time using A2MC", "help me get started / onboard me to A2MC", "initialize a new site / use case", "configure A2MC for my site", "I want to calibrate a new site". DISTINCT from onboard-session (which resumes an ALREADY-configured setup).
modes:
  requires_fates: false
  nutrient_pathway: any
  scope: [setup]
  summary: "First-run setup interview → create + populate a use case → hand off to phase0-design. Model-agnostic; resolves FATES/nutrient mode from the interview."
---

# a2mc-init — first-run setup (offline agent)

The **front door** for a new A2MC user. The offline agent (a coding-agent harness opened in the repo) runs this once to turn "I cloned A2MC" into "I have a configured, mode-resolved use case ready for Phase 0." It interviews the user, verifies their model checkout against the RAG milestone registry, writes the site config + validation targets, and hands off to `phase0-design`.

**This is not `onboard-session`.** `onboard-session` is the cold-start runbook for an **already-configured** setup (read the handoff, catch up, resume in-flight work). `a2mc-init` is for the **first run**, when there is no site config yet. Decision:

```
Is there a customized a2mc_config.sh AND a use_cases/<site>/ for this work?
  ├── No  → a2mc-init (this skill): set it up from scratch.
  └── Yes → onboard-session: resume the existing setup.
```

If the user is midway (config exists, site half-built), do the missing steps here, then route to `onboard-session`.

## Core discipline (read first)

This skill writes files and asserts model behavior, so the offline-agent operating discipline applies hard:

- **Never fabricate data.** Do not invent observation values, uncertainties, parameter bounds, or file paths the user did not give you. If a value is missing, ASK, or write a clearly-marked `TODO` placeholder and tell the user it must be filled before Phase 0. Fabricated targets silently corrupt the whole calibration.
- **Verify, don't assume.** Confirm the checkout's FATES/ELM commits and milestone with the tools below before telling the user which RAG profile applies. Never infer a parameter or mode's meaning from its name — check the RAG / knowledge base.
- **Confirm before writing.** Show the user what you will create (paths + key values) and get a yes before creating the use case dir and files. Creating a use case is reversible, but overwriting an existing one is not — never clobber an existing `use_cases/<site>/`.
- **Env vars = intent.** The site config's mode env vars represent what the user *intends* to calibrate (v2.94+); they are the source of truth, later enriched (not overridden) by the CIME case dir. See `feedback_env_vars_are_intent_case_dir_is_truth`.

## Step 1 — Interview

Ask in grouped rounds (use the harness's structured-question UI where available). Do not ask questions whose answers you can already read from the repo/env — check first, then confirm. Capture the answers before writing anything.

**A. Machine / HPC (a2mc_config.sh).**
- Have you already set up `a2mc_config.sh` (HPC project, output root, Python env)? If not, we do it in Step 3.
- Where is your E3SM / ELM-FATES checkout root? → `A2MC_MODEL_PATH` (**required**; the orchestrator hard-fails without it).
- Which AI provider — `anthropic` (default), `openai`, or `cborg`? Is the matching API key set (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `CBORG_API_KEY`)? (Only needed for the online agent; the offline agent reasons in the harness.)

**B. Model configuration (drives mode-aware retrieval).**
- Are you running **FATES**, or ELM without FATES? (`-bgc fates` vs ELM-only.)
- If FATES: **carbon-only or nutrient-enabled?** → PARTEH mode 1 (carbon-only) vs 2 (CNP). `A2MC_FATES_PARTEH_MODE`.
- If nutrient-enabled: nutrient scheme **ECA or RD**? (`-nutrient_comp_pathway eca|rd`.) Soil decomposition (CENTURY vs CTC)?
- Any Tier-2 FATES features on (SPITFIRE fire, plant hydraulics, logging, no-comp)? Default off.

**C. Site.**
- Site name (used in case names + paths), latitude, longitude.
- Surface + domain data files (NetCDF paths).
- Which PFTs are you calibrating? (1-based FATES PFT ids, e.g. `7 9 10`.)

**D. Calibration targets + parameters.**
- What observations are you calibrating against, per PFT? (e.g. leaf / fine-root / AGB biomass, fluxes, LAI, phenology — value, units, uncertainty, and the measurement year/month.)
- Do you already have a parameter list + bounds (a `FATES_Parameter_List*.txt` / SALib problem file), or should we start from the Kougarok example's list?

> **Arctic/tundra site?** Offer to seed from `use_cases/Kougarok/` instead of the bare `TEMPLATE/` — it carries a working 3-PFT arctic config, a 162-parameter list, and transferable knowledge (Allocation Paradox, P-limitation). Exact parameter *values* never transfer; the structure does.

## Step 2 — Verify the checkout and RAG milestone

Before writing config, confirm the model version so the right knowledge profile loads.

```bash
export A2MC_MODEL_PATH="<user's E3SM/ELM-FATES checkout root>"
python scripts/rag_list.py                                 # registered milestones (api-43-1, api-31-0)
python scripts/rag_match.py --model-path "$A2MC_MODEL_PATH" # detect FATES+ELM commits → matched milestone
```

Report the detected FATES + ELM commits and the matched milestone to the user. If the checkout does not match a registered milestone (drift), say so and point to `docs/a2mc_reference/version_association_workflow.md` "Drift handling" — do not silently proceed on a mismatched profile. `api-31-0` is the frozen Kougarok-manuscript milestone; `api-43-1` is canonical.

## Step 3 — Set up machine config (if needed)

If `a2mc_config.sh` is not yet customized, walk the user through the minimal set:

```bash
# In a2mc_config.sh:
export A2MC_PROJECT="<HPC allocation>"
export A2MC_E3SM_ROOT="<E3SM source>"
export A2MC_OUTPUT_ROOT="<simulation output root>"
export A2MC_MODEL_PATH="<E3SM/ELM-FATES checkout root>"   # REQUIRED
export A2MC_AI_PROVIDER="anthropic"                       # or openai / cborg
```

API key (online agent only): `echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.bashrc && source ~/.bashrc`. Full field reference: `docs/a2mc_reference/user_guide.md` §2. Do not paste real keys into tracked files.

## Step 4 — Create and populate the use case

Confirm the plan with the user, then create the site from the appropriate seed (never overwrite an existing dir):

```bash
SITE="<YourSite>"
test -e "use_cases/$SITE" && { echo "use_cases/$SITE exists — stop, do not clobber"; }
cp -r use_cases/TEMPLATE "use_cases/$SITE"        # or: cp -r use_cases/Kougarok "use_cases/$SITE"
mv "use_cases/$SITE/config/template_config.sh" "use_cases/$SITE/config/${SITE,,}_config.sh"
```

Populate from the interview answers:

1. **Site config** `use_cases/$SITE/config/<site>_config.sh` — fill Section 1 (name, lat/lon, surface/domain data), Section 2 (`A2MC_PFT_LIST`), Section 5 mode env vars (`A2MC_ELM_OPTIONS`, `A2MC_FATES_PARTEH_MODE`, Tier-2 flags). These mode vars are what makes retrieval configuration-aware — set them to the user's actual run, not the template defaults.
2. **Validation targets** `use_cases/$SITE/validation/targets.yaml` — one entry per target. **Key must be `PFT<id>_<vartype>`** (e.g. `PFT10_leaf`, `PFT9_fineroot`); a non-matching key is silently dropped at runtime. Snapshot targets carry a scalar `observed` + `uncertainty` matched at `time_year`/`time_month`; time-series targets use an `observations:` list. Only enter values the user gave you. Format + examples: the seed `targets.yaml` header and `docs/a2mc_reference/user_guide.md` §4.5.
3. **Parameters** `use_cases/$SITE/parameters/` — use the user's parameter-list + SALib problem file, or the Kougarok list as a starting point (tell the user it is a starting point to prune, not a site-specific truth).

## Step 5 — Validate the setup

```bash
source a2mc_config.sh
source use_cases/$SITE/config/<site>_config.sh
print_config                                   # confirm paths/PFTs/mode resolved
python tools/describe_mode.py                  # confirm the mode A2MC will actually use
python tools/validate_targets_config.py        # targets.yaml pre-flight (flags bad keys/vartypes)
```

Resolve every warning before moving on. A green `describe_mode.py` + a clean `validate_targets_config.py` + a matched milestone (Step 2) means the setup is calibration-ready.

## Step 6 — Hand off to Phase 0

Setup is done. Route to **`phase0-design`** to sample the parameter space and submit the ensemble. From here on the standard cold-start flow applies: `onboard-session` on the next session, `arm-hpc-monitoring` once the ensemble is in flight.

Offer to log the setup with `calibration-log` (a free-form session log under `use_cases/$SITE/memory/logs/`) so the choices (mode, PFTs, targets, seed) are recorded for the next session.

## Footguns

- **A2MC_MODEL_PATH unset** — the orchestrator hard-fails at startup. Set it in Step 3, verify in Step 2.
- **Template mode defaults left in place** — the seed config ships a FATES+CNP+ECA default; if the user runs carbon-only or ELM-only, retrieval will surface the wrong content until you fix Section 5.
- **Bad target keys** — anything not matching `PFT<id>_<vartype>` is dropped silently; always run `validate_targets_config.py`.
- **Fabricated targets/paths** — the single most damaging first-run error. Placeholders marked `TODO`, never invented numbers.
- **Clobbering an existing site** — check `use_cases/<site>/` before `cp`; if it exists, this is probably an `onboard-session` case, not `a2mc-init`.
- **Asserting a milestone without verifying** — always run `rag_match.py`; never name the profile from the folder name or an assumption.

## Cross-references

- `onboard-session` — the resume-an-existing-setup counterpart (route there once configured).
- `phase0-design` — the immediate hand-off (design + submit the ensemble).
- `calibration-log` — record the setup session.
- `docs/a2mc_reference/user_guide.md` §1–§3 (install/config/run), §4.5 (targets), §6 (knowledge system).
- `docs/a2mc_reference/version_association_workflow.md`, `mode_aware_workflow.md` — milestone + mode detail.

## Changelog

- 2026-07-07: Initial version — official first-run setup flow for the offline agent (interview → verify checkout/milestone → create + populate use case → hand off to phase0-design). Fills the gap between "cloned the repo" and `phase0-design`; complements `onboard-session` (which assumes an existing setup). Requested by the PI.
