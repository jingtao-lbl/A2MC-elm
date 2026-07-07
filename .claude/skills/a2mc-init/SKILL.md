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
- **Do you have an initial list of parameters to be calibrated** (a `FATES_Parameter_List*.txt` + SALib problem file), and if so does it have bounds? Three cases: **(a)** you have a vetted list → use it (still vet it against the targets in Step 4b); **(b)** you have a rough/partial list → we vet + complete it; **(c)** no list → **the agent builds one from the mechanisms** in Step 4b. Do not just default to copying the Kougarok 162-parameter list — its *values* and its parameter *set* are Kougarok-specific.

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
3. **Parameters** `use_cases/$SITE/parameters/` — drop in the user's list, or build one in **Step 4b** (below). The list defines the entire Morris search space, so it is the highest-leverage design choice here — do not shortcut it by copying Kougarok's set.

## Step 4b — Build (or vet) the parameter list from the mechanisms

The parameter list is the single most consequential decision in setup: it *is* the Morris search space. A list that omits the parameters that actually drive a target guarantees that target can never calibrate; a list padded with irrelevant parameters wastes the ensemble. So when the user has no list (interview D case c), or a rough one (case b), **build/complete it by studying the mechanisms — never by guessing from parameter names** (Calibration Rule #2). When the user has a vetted list (case a), still run the coverage check at the end.

**Work target-by-target.** For each calibration target (a `PFT<id>_<vartype>`, e.g. `PFT10_leaf`), ask: which FATES mechanisms produce this output, and which parameters drive those mechanisms? Answer from the knowledge system, not intuition. RAG ops need the Python-3.10 interpreter (see `docs/a2mc_reference/user_guide.md` §6 / the RAG reference for the exact binary).

1. **Query the knowledge system** for each target output + PFT, filtered to the active mode:
   ```python
   from rag import HybridRetriever
   r = HybridRetriever(auto_build=False)
   ctx = r.get_calibration_context(
       outputs=["FATES_LEAFC_SZPF"], pft=10, config_mode=None)  # params/mechanisms/docs for this target
   info = r.get_parameter_info("fates_leaf_slatop")             # confirm a candidate's effect + direction
   mech = r.get_mechanism_info("carbon_allocation")             # mechanism → parameters it exposes
   ```
   Cross-read the **curated overlay** `rag/data/curated_relationships_<profile>.yaml` (the human-vetted parameter→mechanism→output map for the matched milestone) — it is the source of truth for which parameters matter. For **nutrient-enabled** runs, START at the CNP calibration guide in the active milestone's wiki (`docs/fates-knowledge-base/fates-codebase-wiki-<commit>/advanced/cnp_calibration_guide.md`) for PID gains, `vmax`, stoichiometry, and retranslocation parameters.
2. **Pull prior experience** from Adaptive Memory: generic `memory/gained_knowledge/parameters.json` (known bounds/sensitivities) and, for a similar site, the reference site's `use_cases/<ref>/memory/gained_knowledge/{parameters,discoveries,failed_approaches}.json` (which parameters were sensitive, which pitfalls to avoid). Mechanistic insight transfers across sites; exact values do not.
3. **Assemble each entry** with: FATES parameter name, the PFT(s) it applies to (Morris shorthand `{param}_{pft}`, e.g. `alloc_storage_cushion_10`; official FATES names carry no PFT suffix — see `docs/a2mc_reference/fates_data_reference.md`), the target/mechanism it addresses, and **bounds**. Anchor each bound to the FATES default parameter-file value plus a defensible ± range from the knowledge base / literature / the reference list. **Never invent a bound** — an unfounded range silently distorts the whole sensitivity analysis. If a bound is genuinely unknown, mark it `TODO` and flag it to the user.
4. **Right-size, don't pad.** Morris cost = `n_trajectories × (n_params + 1)`; a broad list is affordable *because Phase 1 sensitivity prunes it* — but every parameter must trace to a target through a named mechanism. No "might as well include it." Flag targets with no driving parameter (a coverage gap) and parameters with no target link (drop them).
5. **Present the proposed list for review before writing** — per parameter: the target it serves, the mechanism, the source citation, and the bound rationale. This is a human-gated design decision, like curated-knowledge writes. On approval, write both files to `use_cases/$SITE/parameters/` matching the Kougarok examples' format — the parameter list (names + bounds) and the SALib problem file (`num_vars`, names, bounds) — and point `A2MC_PARAM_LIST_FILE` / `A2MC_SALIB_PROBLEM_FILE` at them.

**If the user brought a list (case a/b):** run steps 1–2 as a *coverage check* — confirm every target has ≥1 driving parameter in the list and flag any parameter with no mechanistic tie to a target. Report gaps; do not silently rewrite their list.

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
- **Parameter list guessed from names** — the list defines the entire Morris search space; build it from the knowledge system (curated relationships + RAG + CNP guide + Adaptive Memory), not from what a parameter is called (Calibration Rule #2). Fabricated bounds distort the sensitivity analysis — mark unknown bounds `TODO`. Do not reflexively copy the Kougarok 162-parameter set; it is Kougarok-specific.

## Cross-references

- `onboard-session` — the resume-an-existing-setup counterpart (route there once configured).
- `phase0-design` — the immediate hand-off (design + submit the ensemble); consumes the parameter list built in Step 4b.
- `phase1-exploration` — Morris sensitivity that prunes the Step-4b list (why a broad-but-grounded list is safe).
- `calibration-log` — record the setup session.
- `docs/a2mc_reference/user_guide.md` §1–§3 (install/config/run), §4.5 (targets), §6 (knowledge system); `fates_data_reference.md` (parameter naming / Morris shorthand); `rag_reference.md` (RAG query how-to + Python-3.10 binary).
- `docs/a2mc_reference/version_association_workflow.md`, `mode_aware_workflow.md` — milestone + mode detail.

## Changelog

- 2026-07-07: **Parameter-list building (Step 4b).** Interview D reworded to "do you have an initial list of parameters to be calibrated?" with a 3-case branch (vetted / rough / none). Added **Step 4b** — when the user has no list (or a rough one), the agent studies the mechanisms via `HybridRetriever.get_calibration_context()` + curated `curated_relationships_<profile>.yaml` + the CNP calibration guide + Adaptive Memory to build a target-driven list with source-anchored bounds (no fabricated values), presented for review before writing; a vetted list gets a coverage check instead. New footgun (list-from-names / fabricated bounds). Requested by the PI.
- 2026-07-07: Initial version — official first-run setup flow for the offline agent (interview → verify checkout/milestone → create + populate use case → hand off to phase0-design). Fills the gap between "cloned the repo" and `phase0-design`; complements `onboard-session` (which assumes an existing setup). Requested by the PI.
