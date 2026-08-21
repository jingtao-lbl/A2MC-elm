# A2MC First-Run Interview — Sample Questionnaire

**A concrete, branching question script for the `a2mc-init` skill.** The skill (`.claude/skills/a2mc-init/SKILL.md`) is authoritative on the *logic*; this is an illustrative, ready-to-use set of questions the agent can adapt. It is **adaptive** in two ways:

- **Depth** — Q0 gauges the user's ELM/ELM-FATES experience and sets how much the agent explains vs simply captures (teach a novice; defer to an expert, don't impose defaults over an explicit choice).
- **Breadth** — skip logic: a question is asked only when a prior answer makes it relevant (e.g. PFT questions only for PFT-level targets; ECA/RD only when nutrient-enabled).

**Rules the agent follows while asking:** never fabricate a value the user didn't give (mark gaps `TODO`); never assert a FATES parameter/mode meaning from its name (verify against the knowledge base); confirm before writing any config. Each answer maps to the site config / `targets.yaml` / parameter list noted in `[→ ...]`.

Legend: **[novice]** = explain the concept when asking; **[expert]** = just capture the answer; **[skip if …]** = branch/skip logic.

---

## Section 0 — Greeting, experience & orientation (ask first; sets the depth for everything below)

**Q0.0 — Greeting + name (open here).**

> "Hi! I'm your A2MC agent — I'll work with you as your science assistant to calibrate your model. What's your name, and how should I address you?"

Record the answer as **`A2MC_USER_NAME`** (written to `a2mc_config.sh` in Step 3). Beyond personalizing the session, it sets the **Author field** for every log written during the user's work: **`{A2MC_USER_NAME} with {coding-agent name}`** — e.g. *"Jing Tao with Claude Code"*. The coding-agent name is whatever harness the offline agent runs in. If the user declines to give a name, fall back to a neutral author (`A2MC user with {coding-agent name}`). `[→ A2MC_USER_NAME]`

**Q0.1 — How would you describe your experience with ELM / ELM-FATES?**
- (a) New to it — please explain the concepts as we go
- (b) Some experience — I know the basics
- (c) Expert — I'll specify the configuration; keep it brief

> (a) → give the Step-0 orientation (below) and explain each mechanism as it comes up.
> (c) → skip the orientation, go straight to capture, and honor the user's explicit choices.
> (b) → orient lightly, check in as you go.

**Orientation to convey for (a)/(b) — four things:** (1) two-layer config — `a2mc_config.sh` (machine) + `<site>_config.sh` (site, **overrides** machine); (2) A2MC is mode-aware (FATES on/off, CNP, ECA/RD, milestone); (3) the goal sets *what you calibrate* (target granularity), spin-up is a *separate* decision; (4) **ELM PFTs (static surfdata) ≠ FATES PFTs (dynamic)** — targets use FATES PFT ids.

---

## Section 1.0 — Science goal & target granularity (asked of everyone)

**Q1.1 — In a sentence or two, what is your calibration goal / science question?**
`[→ research_plan.md: science goal]`

**Q1.2 — What does your observational data measure? (choose all that apply)**
- (a) **Ecosystem-level** fluxes/states — GPP, NEE, ET, ecosystem LAI, total aboveground biomass (aggregated over the gridcell/tower footprint)
- (b) **PFT- or species-level** — per-PFT leaf/fine-root/AGB biomass, per-PFT phenology, community composition
- (c) Not sure yet — let's inventory the data (→ Section 1.1)

> (a) only → **ecosystem-level goal**: skip Section 1.2 (no PFT enumeration needed). [novice: explain that PFT-level detail isn't required for aggregate fluxes.]
> (b) → **PFT-level goal**: go to Section 1.2.
> (c) → Section 1.1.
> `[→ target granularity]`

---

## Section 1.1 — Data inventory  *(skip if Q1.2 was clearly (a) or (b))*

**Q1.3 — For each observation you have, tell me:** source (MODIS / FLUXNET tower / field plot / literature), variable, spatial scale (gridcell / footprint / plot / individual), temporal (single snapshot vs time series), units, uncertainty, and the year/month measured.

> Map each: gridcell/tower-aggregate → ecosystem-level target; plot/species-resolved → PFT-level target (needs Section 1.2). The data decides the granularity.

**Q1.3b — For each dataset, is it a CALIBRATION goal or VALIDATION data?**
- **Calibration** — A2MC should score/optimize against it → goes into `targets.yaml` `[→ targets.yaml]`
- **Validation / diagnostic** — an independent cross-check you do NOT fit (evaluate the calibrated model against it) → kept in its native format, compared via a purpose-built script, **not** in `targets.yaml` and **not** scored

> Only calibration data enters `targets.yaml`. A long time-series calibration target references an external file rather than inlining. Calibration keys span four levels: `PFT<id>_<vartype>` (per-PFT), `ECO_<var>` (ecosystem scalar), `SNOW_<var>` (snow site scalar), `SOIL_<var>_<N>cm`/`_L<n>` (soil profile). *Validation* data you don't fit is separate — reader scripts, not `targets.yaml`.

---

## Section 1.2 — PFTs  *(skip unless Q1.2 established PFT-level targets)*

> [novice] **These are FATES PFTs** — the dynamic, competing PFTs in the base parameter file — **not** ELM's static surfdata PFTs (a separate system; surfdata fractions don't define the FATES target ids).

**Q1.4 — Describe the dominant vegetation in plain ecological terms:** growth form (trees / shrubs / grasses / sedges), leaf habit (evergreen / deciduous), leaf form (needleleaf / broadleaf), biome (arctic / boreal / temperate / tropical).

> The agent maps this to FATES PFT ids by reading the base parameter file's PFT list (Step 2), then **confirms the id↔name mapping with the user**. Offer to seed from a similar reference site (e.g. Kougarok for arctic 3-PFT).
> `[→ A2MC_PFTS = 1-based FATES ids of the calibrated PFTs]`

---

## Section 1A — Machine / HPC

**Q1.5 — Is `a2mc_config.sh` already set up** (HPC allocation, output root, Python env)? *(if no → do it in Step 3)*
**Q1.6 — Where is your E3SM / ELM-FATES checkout root?** `[→ A2MC_MODEL_PATH (required)]`
**Q1.7 — AI provider** — `anthropic` (default) / `openai` / `cborg`? Is the matching API key set? *(online agent only)*

---

## Section 1B — Model configuration  *(drives mode-aware retrieval)*

**Q1.8 — FATES, or ELM without FATES?** `[→ A2MC_ELM_OPTIONS: -bgc fates]`
> [novice] For an ecosystem-GPP-only goal, a simpler config (nocomp, or even ELM-SP) may be cheaper — don't default to full competition.

**Q1.9 — [if FATES] Carbon-only or nutrient-enabled (CNP)?** `[→ A2MC_FATES_PARTEH_MODE: 1 or 2]`
**Q1.10 — [if CNP] ECA or RD nutrient competition? Soil decomposition — CENTURY or CTC?** `[skip if Q1.9 = carbon-only]`
**Q1.11 — [if FATES] Any Tier-2 features on** (SPITFIRE fire, plant hydraulics, logging, no-comp)? *(default off)*
**Q1.12 — Spin-up protocol** — how many years of accelerated-decomposition (ADSP) + regular spin-up (RGSP) before the transient run, and the supplement-N/P flags per phase? `[→ A2MC_{ADSP,RGSP,TRANS}_{YEARS,SUPLPHOS,SUPLNITRO}]`
> **Ask this even for ecosystem/GPP goals** — spin-up is *independent* of target granularity; a GPP run usually still needs spin-up to equilibrate C/N/P + soil pools. [novice: explain what spin-up does + offer the default; expert: capture their prescribed protocol.]

---

## Section 1C — Site

**Q1.13 — Site name, latitude, longitude.** `[→ Section 1 of site config]`
**Q1.14 — Surface + domain data files** (NetCDF paths). *(ELM surfdata — static PFTs; distinct from the FATES PFT set)*
**Q1.15 — [PFT-level only] Confirm the FATES PFT mapping** from Q1.4. `[skip for ecosystem-level goal]`

---

## Section 1D — Calibration targets & parameters

**Q1.16 — For each target, give:** its key (**`PFT<id>_<vartype>`** for PFT-level, e.g. `PFT10_leaf`; or an ecosystem-level name), the observed value, units, uncertainty, and measurement year/month. *(only values you actually have; gaps → `TODO`)* `[→ targets.yaml]`

**Q1.17 — For each target, which variant is it?**
- Snapshot (one value, one time) → scalar `observed`+`uncertainty`
- Time series / several snapshots (a variable at N times) → an `observations:` list (metric like `nrmse`/`nse`/`kge`)
- Several stocks/variables (leaf, root, AGB, GPP…) → **separate** targets, one per variable

**Q1.18 — Cost function** (the objective; most users take defaults): error metric per target, how targets aggregate into one composite, per-target weights, satisfied tolerance. *(defaults: `relative_error` + `rmsre` + ±20%)* `[→ cost_config in targets.yaml]`
> Match the metric to the variant (a skill score needs ≥2 points). Mixing very different stocks → use comparable-scale metrics + weights.

**Q1.19 — Do you have a parameter list to calibrate** (with bounds + a SALib problem file)?
- (a) Vetted list → use it (coverage-check in Step 4b)
- (b) Rough/partial → we vet + complete it
- (c) None → the agent builds one from the mechanisms (Step 4b)
> Never default to copying Kougarok's set — its *values* and *parameter set* are site-specific. `[→ parameters/, A2MC_PARAM_LIST_FILE / A2MC_SALIB_PROBLEM_FILE]`

---

## After the interview

The answers feed a **`research_plan.md`** the user confirms (the build gate) — *not* the config files directly. On confirmation, the agent records the case memory and propagates the plan into the site config, `targets.yaml`, the parameter list, and the generated `calibration_rounds.yaml`, then runs the Step-5 gate (`tools/check_setup_ready.py`). See the `a2mc-init` skill for the full flow.
