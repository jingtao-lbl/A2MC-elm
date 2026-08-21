---
name: a2mc-init
visibility: public
category: meta
description: First-run interactive setup for the offline agent — the official "getting started" flow the FIRST time someone uses A2MC in a repo/site. Interview the user (is a2mc_config.sh set up, where is the E3SM/ELM-FATES checkout, FATES on/off, carbon-only vs nutrient-enabled PARTEH, ECA vs RD, site name/location, PFTs, calibration targets), verify the checkout + RAG milestone, then create and populate the use case (site config + validation targets + parameter list) and hand off to phase0-design. Use when the user says "set up A2MC", "first time using A2MC", "help me get started / onboard me to A2MC", "initialize a new site / use case", "configure A2MC for my site", "I want to calibrate a new site". DISTINCT from onboard-session (which resumes an ALREADY-configured setup).
modes:
  requires_fates: false
  nutrient_pathway: any
  scope: [setup]
  summary: "First-run setup interview → create + populate a use case → hand off to phase0-design. Model-agnostic; resolves FATES/nutrient mode from the interview."
---

<!-- ───────────────────────── At a glance ───────────────────────── -->
```text
Step 0  greet + gauge experience + orient
Step 1  interview (goal → granularity → PFTs/targets/params)
Step 2  verify checkout + milestone + PFT inventory
Step 3  machine config
Step 4  draft research_plan.md ──► ★ GATE 1 (iterate until approved): plan ◄──
          then: record memory + write site config + targets.yaml
Step 4b parameter list + ensemble design (scheme/size/cost — show trade-offs)
          ──► ★ GATE 2 (iterate until agreed) ◄── then: round record
Step 5  check_setup_ready.py  (goal-conditional; all ✗ resolved)
Step 6  hand off to phase0-design
```

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

This skill writes files and asserts model behavior, so the offline-agent operating discipline applies hard
— the four failure modes + the gate enforcing each are in `AGENTS.md` §"Offline-Agent Operating Discipline"
(lead memory `feedback_offline_agent_operating_discipline`). In this skill that means especially:

- **Anchor every write to the A2MC repo root — never a bare relative path.** This skill's paths
  (`use_cases/…`, `a2mc_config.sh`, `tools/…`, `scripts/…`) are relative to the **repo root**; if the agent's
  cwd is elsewhere, a bare `use_cases/$SITE` write lands in the wrong place. `A2MC_ROOT` is **not** set on a
  first run (a site config sets it, and none exists yet) — so **derive it** and prefix all writes with it:
  ```bash
  A2MC_ROOT="${A2MC_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
  test -f "$A2MC_ROOT/a2mc_config.sh" || { echo "not in an A2MC clone — cd into it first"; exit 1; }
  ```
  Then write under `"$A2MC_ROOT/use_cases/$SITE/…"`. **Never** `$A2MC_ROOT/…` while `A2MC_ROOT` is unset — an
  empty prefix expands to `/use_cases/$SITE`, i.e. the filesystem root.
- **Never fabricate data.** Do not invent observation values, uncertainties, parameter bounds, or file paths the user did not give you. If a value is missing, ASK, or write a clearly-marked `TODO` placeholder and tell the user it must be filled before Phase 0. Fabricated targets silently corrupt the whole calibration.
- **Verify, don't assume.** Confirm the checkout's FATES/ELM commits and milestone with the tools below before telling the user which RAG profile applies. Never infer a parameter or mode's meaning from its name — check the RAG / knowledge base.
- **Confirm before writing.** Show the user what you will create (paths + key values) and get a yes before creating the use case dir and files. Creating a use case is reversible, but overwriting an existing one is not — never clobber an existing `use_cases/<site>/`.
- **Env vars = intent.** The site config's mode env vars represent what the user *intends* to calibrate (v2.94+); they are the source of truth, later enriched (not overridden) by the CIME case dir. See `feedback_env_vars_are_intent_case_dir_is_truth`.

## Step 0 — Greet + name the user, gauge experience, then orient (adapt the depth to them)

**Open with a greeting and capture the user's name:** *"Hi! I'm your A2MC agent — I'll work with you as
your science assistant to calibrate your model. What's your name, and how should I address you?"* Record
it as **`A2MC_USER_NAME`** (written to `a2mc_config.sh` in Step 3). Beyond personalizing the session, it
sets the **Author field** for every log the user's work produces — `{A2MC_USER_NAME} with {coding-agent
name}` (e.g. *"Jing Tao with Claude Code"*); see the `calibration-log` skill. If the user declines,
fall back to `A2MC user with {coding-agent name}`.

**Then gauge how familiar the user is with ELM / ELM-FATES** — ask directly, or infer from how they
answer Step 1. This sets how much you explain vs defer **for the whole session**:

- **New to the models** → be a teacher: orient them (the points below) and explain the relevant
  mechanism as each decision comes up (what a PFT is, what spin-up does, carbon-only vs CNP, ECA vs RD).
  Offer sensible defaults *with* the reasoning.
- **Experienced** → rely on their decisions: confirm their intent, don't lecture, and **do not impose a
  default over an explicit choice**. Skip the orientation they don't need and go straight to capturing
  their configuration.
- **Mixed / unsure** → orient lightly and check in as you go.

**Orientation for a user new to the modeling system — convey these plainly (skip/abbreviate for an expert):**

1. **Two-layer configuration.** `a2mc_config.sh` holds *machine* settings (HPC allocation, output root, model checkout `A2MC_MODEL_PATH`, Python env, AI provider). `use_cases/<site>/config/<site>_config.sh` holds *site* settings **and overrides** the machine defaults for this site (spin-up protocol, PFTs, ensemble name, parameter/target files). You always `source a2mc_config.sh` **then** `source <site>_config.sh` — the site config wins on any overlap, so nothing site-specific belongs in `a2mc_config.sh`.
2. **A2MC is mode-aware.** What it retrieves and how it runs depend on the *configuration* — ELM with or without FATES, carbon-only vs nutrient-enabled (CNP), ECA vs RD, and the FATES **milestone** matched from the checkout's commits (Step 2). Resolve this early so the right knowledge profile loads.
3. **The goal sets *what you calibrate*, not by itself the *run protocol*.** Your science question + data set the **target granularity** — ecosystem-level fluxes/states (tower/MODIS GPP, ET, NEE) vs per-PFT quantities (per-PFT biomass, phenology). That decides whether you must enumerate PFTs (Step 1.2). It does **not** decide spin-up: **spin-up is a separate decision** (Step 1B) — even a GPP-only run often needs spin-up to equilibrate carbon/soil pools. Ask; never infer "no spin-up" from an ecosystem goal.
4. **PFTs — ELM vs FATES are different systems.** ELM's surface-dataset PFTs are **static** (prescribed fractional cover, fixed in time); FATES's PFTs are **dynamic** (they compete and evolve demographically). They have separate id mappings — a calibration target's PFT id refers to the **FATES** PFT list (read from the base parameter file, Step 2), *not* the ELM surfdata PFTs. Confirm which system the user means when they say "PFT."
5. **The 7-phase loop.** Setup (this skill) → Phase 0 design/submit → 1 explore → 2 screen → 3 diagnose → 4 hypothesize → 5 test → 6 refine → 7 converge. Setup ends only when the Step 5 preparation gate is green.

## Step 1 — Interview (start from the science goal, not the model internals)

**Do not assume the user knows FATES internals.** A new user often does not know which PFTs dominate their
site, what a parameter does, or even whether they need PFT-level detail at all. Start from what they *do*
know — their **science question and their data** — and derive the model configuration from it. Ask in grouped
rounds (use the harness's structured-question UI where available); never ask what you can read from the
repo/env — check first, then confirm.

**Offer the user a path first (a structured choice, each with a different next action):**

- **Path A — "I know my configuration and site"** (FATES/nutrient mode, PFTs, and targets are clear). → Go
  straight to the detail rounds **1A–1D** and **capture the setup** (site config + a session log; the
  "record the decisions" block below). This is the fast path.
- **Path B — "I'm new to this / not sure what I need."** → **Do not** start by asking for PFT ids or a
  parameter list. Start with **1.0 (goal + data)** — it decides which later questions even apply, so the user
  never has to answer a FATES-internals question they cannot.

### 1.0 — What are you calibrating? (this sets the *target granularity* — ask it first)

The granularity of the target decides everything downstream, **including whether the user needs to know their
PFTs at all.** Offer these options:

- **Ecosystem-level fluxes/states** — e.g. MODIS or eddy-covariance **GPP**, NEE, ET, ecosystem LAI, total
  aboveground biomass — aggregated over the whole gridcell / tower footprint. → **You do NOT need to
  enumerate dominant PFTs or per-PFT biomass.** The targets are ecosystem totals; the PFT composition is
  secondary (a reasonable default/mixed PFT set is fine, and a simpler FATES config — even ELM-SP for pure
  GPP — may suffice). **Skip 1.2.**
- **PFT- or species-level** — per-PFT leaf / fine-root / AGB biomass, per-PFT phenology, community
  composition. → The PFT set now matters; go to **1.2** to identify it.
- **Both / not sure yet** — go to **1.1** (data inventory) and let the data decide.

### 1.1 — Data inventory (for users unsure what they can calibrate)

Ask what observations they actually have, and for each: **source** (MODIS, a FLUXNET tower, a field plot,
literature…), **variable** (GPP, biomass, LAI, phenology…), **spatial scale** (gridcell / tower footprint /
plot / individual), **temporal** (single snapshot vs time series), **units**, **uncertainty**, and the
**year/month** measured. Then map each observation to a granularity:

- gridcell- or tower-aggregate flux/state → an **ecosystem-level** target (no PFT breakdown needed);
- plot- or species-resolved biomass/trait → a **PFT-level** target (needs the PFT mapping, 1.2).

The data they have **is** the answer to "what should I calibrate" — the observations determine the targets,
which determine how much model detail (PFT-level or not) they actually need.

**Then classify each dataset by ROLE — calibration vs validation (ask explicitly):**
- **Calibration data** = a goal A2MC should *score and optimize against* → it goes into `targets.yaml`
  and drives the objective.
- **Validation / diagnostic data** = an independent cross-check of ecosystem/soil behavior you do **not**
  fit (you *evaluate* the calibrated model against it) → kept in its **native format**, compared via a
  purpose-built reader/plot script, and **never placed in `targets.yaml`** (it is not scored).

Only calibration data enters `targets.yaml`. A long **time-series** calibration target does not fit the
inline `observations:` list — reference an external data file instead. Calibration targets span four
levels, each with its own key form + extractor: `PFT<id>_<vartype>` (per-PFT SZPF, e.g. `PFT10_leaf`),
`ECO_<var>` (FATES site scalar — `ECO_gpp`/`ECO_lai`), `SNOW_<var>` (snow site scalar —
`SNOW_snowdp`/`SNOW_h2osno`/`SNOW_fsno`), and `SOIL_<var>_<N>cm` or `_L<n>` (soil profile at a
depth/layer — `SOIL_tsoi_10cm`, `SOIL_h2osoi_L3`). *(Snow-**layer** vars await confirmed ELM `levsno`
output names + extractor support.)* **Validation** data you don't fit is separate — reader scripts, not
`targets.yaml` — it is **calibration-only**, and everything in it is scored. Raw observations of either role live in `use_cases/<Case>/validation/data/`; see that folder's `README.md` (convention in `use_cases/TEMPLATE/validation/data/README.md`).

### 1.2 — Identify the PFTs (ONLY if you have PFT-level targets)

Reach here only when 1.0/1.1 established PFT-level targets. **These are FATES PFTs** — the dynamic,
competing PFTs defined in the base parameter file — **not** ELM's static surfdata PFTs (a separate
system with its own mapping; the surface dataset's PFT fractions don't define the FATES target ids).
Don't ask "which FATES PFT ids" cold — a new user won't know. Ask in **plain ecological terms**: the
dominant vegetation (trees / shrubs / grasses / sedges),
leaf habit (evergreen / deciduous), leaf form (needleleaf / broadleaf), and biome (arctic / boreal /
temperate / tropical). Then **map** those to FATES PFT ids by reading the actual PFT list from the base
parameter file — `get_pft_names_from_file()` (the Step-2 PFT-inventory command prints every `PFT#id = name`);
never assert the mapping from a name (Calibration Rule #2). These 1-based ids are exactly what `A2MC_PFTS`
holds (each target is then keyed `PFT<id>_<vartype>`, and that id drives the SZPF extraction slice). Confirm
the mapping with the user, and offer to **seed from a similar reference site** (e.g.
`use_cases/ELM-FATES_Kougarok/` for an arctic 3-PFT config). If the user genuinely doesn't know their site's
vegetation, that is a data-collection gap — flag it, don't invent a composition.

### 1A–1D — Detail rounds (ask what the chosen path still needs)

**1A. Machine / HPC (`a2mc_config.sh`).**
- Have you already set up `a2mc_config.sh` (HPC project, output root, Python env)? If not, we do it in Step 3.
- Where is your E3SM / ELM-FATES checkout root? → `A2MC_MODEL_PATH` (**required**; the orchestrator hard-fails without it).
- Which AI provider — `anthropic` (default), `openai`, or `cborg`? Is the matching API key set? (Only needed for the online agent; the offline agent reasons in the harness.)

**1B. Model configuration (drives mode-aware retrieval) — resolve from the science goal, not a default.**
- Are you running **FATES**, or ELM without FATES? (`-bgc fates` vs ELM-only.) *For an ecosystem-only GPP goal, PFT competition may not be needed — a `nocomp` or simpler config (or ELM-SP) can be the right, cheaper choice; don't default to full competition.*
- If FATES: **carbon-only or nutrient-enabled?** → PARTEH mode 1 vs 2 (CNP). `A2MC_FATES_PARTEH_MODE`.
- If nutrient-enabled: **ECA or RD**? (`-nutrient_comp_pathway eca|rd`.) Soil decomposition (CENTURY vs CTC)?
- Any Tier-2 FATES features on (SPITFIRE fire, plant hydraulics, logging, no-comp)? Default off.
- **Spin-up protocol** — accelerated-decomposition (ADSP) + regular spin-up (RGSP) years before the transient run, and the supplement-N/P flags per phase (`A2MC_{ADSP,RGSP,TRANS}_{SUPLPHOS,SUPLNITRO}`, defaults in `a2mc_config.sh`). **This is independent of the target granularity** — even an ecosystem-level GPP goal usually needs spin-up to equilibrate C/N/P and soil pools; ask the user how much (or whether) to spin up rather than inferring it from the goal. An expert may prescribe the exact protocol; a novice gets the default + why it matters.

**1C. Site.**
- Site name (used in case names + paths), latitude, longitude; surface + domain data files (NetCDF paths).
- **PFTs — only if 1.0/1.1 established PFT-level targets** (the mapping from 1.2). Ecosystem-only goals skip this.

**1D. Calibration targets + parameters.** (Mostly captured by 1.0/1.1 already; formalize here.)
- Each target as either a **`PFT<id>_<vartype>`** key (PFT-level) or an **ecosystem-level** target — with value, units, uncertainty, and the measurement year/month. Only values the user gave you.
- **Target variant — classify each (from the 1.1 data inventory), it decides the `targets.yaml` shape + a sensible metric:**
  - **Snapshot** (one value at one time) → scalar `observed` + `uncertainty` at `time_year`/`time_month`; metric `relative_error` (default).
  - **Time series / several time snapshots** (a variable at N times) → **one** target with an `observations:` list (one point per time, each with its own value/uncertainty/window); metric a series metric (`nrmse` / `nse` / `kge` — skill scores need ≥2 points). Both scoring paths score it on ALL points.
  - **Several stocks / variables** (leaf, fine-root, AGB, GPP…) → **separate** targets, one per variable; do not merge them.
- **Cost function** (the calibration objective — built from these targets; most users take the defaults). Ask, or default: the **error metric** per target (per the variant above), how targets **aggregate** into one composite (`rmsre` default; `weighted_mean` if some targets matter more), any per-target **weight**, and the **satisfied tolerance** (±20% default). Mixing very different stocks under one composite? use a **comparable-scale metric** per target (relative / normalized / a skill score) + weights so no single target dominates — `validate_targets_config.py` WARNs when `rmsre` mixes relative + absolute metrics. These become a `cost_config` block + per-target `cost_method`/`weight` in `targets.yaml` (Step 4); screening (`optimize_function.py`) and single-case eval (`evaluate_case.py`, with `year_start`) both honor them.
- **Do you have an initial list of parameters to calibrate** (a `FATES_Parameter_List*.txt` + SALib problem file), with bounds? Three cases: **(a)** vetted list → use it (still coverage-check it in Step 4b); **(b)** rough/partial → we vet + complete it; **(c)** none → **the agent builds one from the mechanisms** in Step 4b. Never default to copying the Kougarok 162-parameter set — its *values* and its parameter *set* are Kougarok-specific.

> **Arctic/tundra site?** Offer to seed from `use_cases/ELM-FATES_Kougarok/` instead of the bare `TEMPLATE/` — a working 3-PFT arctic config, a 162-parameter list, and transferable knowledge (Allocation Paradox, P-limitation). Exact parameter *values* never transfer; the structure does.

### Synthesize before you build — do not write config yet

The interview answers (both paths) feed a single **research plan**, not the config files directly. After you
verify the milestone (Step 2), you draft that plan into the use case and get the user to **confirm** it
(Step 4) — that confirmation is the gate before you create the case memory and propagate answers into config.
Do **not** populate `a2mc_config.sh` / the site config / `targets.yaml` until the plan is confirmed.

## Step 2 — Verify the checkout and RAG milestone

Before writing config, confirm the model version so the right knowledge profile loads.

```bash
export A2MC_MODEL_PATH="<user's E3SM/ELM-FATES checkout root>"
python scripts/rag_list.py                                 # registered milestones (api-43-1, api-31-0)
python scripts/rag_match.py --model-path "$A2MC_MODEL_PATH" # detect FATES+ELM commits → matched milestone
```

Report the detected FATES + ELM commits and the matched milestone to the user. If the checkout does not match a registered milestone (drift), say so and point to `docs/a2mc_reference/version_association_workflow.md` "Drift handling" — do not silently proceed on a mismatched profile. `api-31-0` is the frozen Kougarok-manuscript milestone; `api-43-1` is canonical.

**Also read the PFT inventory from the checkout's base parameter file** — the same gate that reads commits should read the PFTs, so the total count and id↔name mapping come from the model the user actually runs (NEVER hardcode a PFT count; FATES can change its PFT system):

```bash
python -c "from tools.fates_utils import get_pft_names_from_file as g; \
  d=g('$A2MC_MODEL_PATH/components/elm/src/external_models/fates/parameter_files/fates_params_default.json'); \
  print(f'{len(d)} PFTs total'); [print(f'  PFT#{i} = {n}') for i,n in d.items()]"
```

Report the **total PFT count** and the full `PFT#id = name` list to the user. This count is authoritative: A2MC reads it at runtime (`get_n_pft_from_file`) and the SZPF extraction derives its level total (= count × 13 size classes) from the file, so nothing assumes 12/14/etc. Use this exact list to (a) do the target→PFT-id mapping in Step 1.2 and (b) fill `A2MC_PFTS` in Step 3 with the **1-based FATES ids** of the calibrated PFTs. If the user's targets name a PFT not in this list, stop — the checkout and the target set disagree.

## Step 2b — Offer fork-safe remotes on the model checkout (guard against pushing to upstream)

A freshly-cloned E3SM/ELM-FATES checkout has `origin` pointing at the **upstream** repo (usually
`E3SM-Project/E3SM` for E3SM and `NGEET/fates` for the FATES submodule) with **push enabled** — so a stray
`git push origin …` targets upstream. **Check it, and offer to make it fork-safe** (especially if the user
plans model-*development* — editing ELM/FATES source; pure calibration users never push to the model repo,
but the guard is harmless and worth offering):

```bash
git -C "$A2MC_MODEL_PATH" remote -v
git -C "$A2MC_MODEL_PATH/components/elm/src/external_models/fates" remote -v   # FATES submodule
```

If `origin` is an upstream URL with push enabled, **ask the user**: (1) do they have their own fork of
E3SM and of FATES (give the fork URLs), and (2) may you set the remotes so pushes can only go to their fork?
If yes, for **each** repo (E3SM root + the FATES submodule) set it up for them:

```bash
git -C "$REPO" remote add fork "<user's fork URL for this repo>"     # e.g. git@github.com:<user>/E3SM.git
git -C "$REPO" remote set-url --push origin DISABLED_no_push_to_upstream   # `git push origin` now fails loudly
# thereafter: git push fork <branch>
```

Prefer **SSH** fork URLs — an HTTPS token without the `workflow` scope is refused when the history touches
`.github/workflows/`. This is **per-clone git config (not committed)** — re-apply on any re-clone. Model-dev
then happens on **experiment branches** off the pinned anchor, default-off + V0-at-equality; see the
`add-fates-parameter` skill and the memory [[feedback_model_source_push_fork_only]] for the full contract.
Record the user's fork URLs + intended experiment branch in their case memory if they opt in.

## Step 3 — Set up machine config (if needed)

If `a2mc_config.sh` is not yet customized, walk the user through the minimal set:

```bash
# In a2mc_config.sh:
export A2MC_USER_NAME="<how the user asked to be addressed>"  # from the Step-0 greeting; author field
export A2MC_PROJECT="<HPC allocation>"
export A2MC_E3SM_ROOT="<E3SM source>"
export A2MC_OUTPUT_ROOT="<simulation output root>"
export A2MC_MODEL_PATH="<E3SM/ELM-FATES checkout root>"   # REQUIRED
export A2MC_AI_PROVIDER="anthropic"                       # or openai / cborg
```

API key (online agent only): `echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.bashrc && source ~/.bashrc`. Full field reference: `docs/a2mc_reference/user_guide.md` §2. Do not paste real keys into tracked files.

## Step 4 — Draft the research plan, confirm, then create + populate the use case

**Draft the research plan first — it is the build gate.** Synthesize the interview (Step 1) + the matched
milestone (Step 2) into a single **research plan**, write it into the use case, and get the user to confirm
*before* writing any config. Create the dir from the appropriate seed so the plan has a home (never overwrite
an existing dir):

**Name the case `{Model}_{Site}`** — `ELM-FATES_Kougarok`, not `Kougarok`. The same site gets calibrated under different model configurations (`ELM_Kougarok` for ELM-only), and those are different cases with different parameters, targets and results; a bare site name collides the moment the second one appears. Hyphens belong to the model half, underscore separates the halves (matches `adapter-kit`'s `<Model>_<Case>`). **`A2MC_SITE_NAME` must equal the directory name**, since `A2MC_USE_CASE_DIR` derives from it.

```bash
A2MC_ROOT="${A2MC_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"   # anchor writes to the repo root
test -f "$A2MC_ROOT/a2mc_config.sh" || { echo "not in an A2MC clone — cd into it first"; exit 1; }
SITE="<YourSite>"
DEST="$A2MC_ROOT/use_cases/$SITE"
test -e "$DEST" && { echo "$DEST exists — stop, do not clobber"; exit 1; }
cp -r "$A2MC_ROOT/use_cases/TEMPLATE" "$DEST"     # or: cp -r "$A2MC_ROOT/use_cases/ELM-FATES_Kougarok" "$DEST" (arctic seed)
mv "$DEST/config/template_config.sh"               "$DEST/config/${SITE,,}_config.sh"
mv "$DEST/config/template_calibration_rounds.yaml" "$DEST/config/calibration_rounds.yaml"
```

**Both renames are required.** The site config is sourced by an explicit `<site>_config.sh` path, so a leftover prefix just means nothing sources it. `calibration_rounds.yaml` is worse: **43 call sites read that exact fixed name**, so a case keeping the prefix has no round record as far as the framework is concerned — and `generate_calibration_rounds.py --write` then creates a *second*, empty one beside the prefixed copy, leaving two files where the stale one carries an authoritative-looking instructional header. TEMPLATE's own file states the rule in its first lines.

**Also set `A2MC_SITE_NAME` in the renamed config before anything else** — `A2MC_USE_CASE_DIR` now derives from it (`${A2MC_ROOT}/use_cases/${A2MC_SITE_NAME}`), so it must match the case directory name.

Write `$DEST/research_plan.md` (i.e. `$A2MC_ROOT/use_cases/$SITE/research_plan.md`) — a plain-language
synthesis a domain reader can confirm without project context (the report discipline,
`feedback_report_writing_self_contained`):

- **Science goal + question** and the **target granularity** (ecosystem-level vs PFT-level) with the reason;
- **Calibration + validation targets** — each as its `PFT<id>_<vartype>` or ecosystem-level key, with value,
  units, uncertainty, source, year/month, **and its variant** (snapshot / time-series / several-snapshots —
  the latter two as an `observations:` list; several stocks = several targets) (only values the user gave you — mark gaps `TODO`);
- **Cost function** — the error metric per target (matched to the variant) + how they aggregate into the
  composite + any weights + the satisfied tolerance (the calibration objective; defaults: `relative_error` + `rmsre` + ±20%);
- **Model configuration** — FATES/ELM, PARTEH mode, ECA/RD, soil decomp, Tier-2 flags, and the **matched
  milestone** (Step 2);
- **Site** — name, lat/lon, data files; **PFTs** (mapping from 1.2) or "ecosystem-only — PFTs not required";
- **Parameter approach** — bring the user's list / vet-and-complete / build from mechanisms (Step 4b), with
  the candidate mechanisms per target if known;
- **Ensemble design + compute cost** — the intended **sampling scheme** (Morris / Sobol / LHS), the
  resulting **ensemble size**, and a **core-hour + wall-clock estimate**, with the trade-off stated up
  front (full detail + the agreement gate are in Step 4b). Even at plan stage, flag if the chosen scheme
  implies a very large, expensive ensemble;
- **Seed** (`TEMPLATE` vs `Kougarok`) and the **open questions / data gaps** to resolve before Phase 0.

**Present it and ask the user to confirm or correct — this is GATE 1, and it is ITERATIVE.** Answer every
question the user raises and fold in every requested change, then **re-present the revised plan**. **Do
not advance past this gate (to config, or to the Step-4b parameter list) while any question or request is
unresolved** — keep looping until the user *explicitly approves* the plan. Only then build config.

**On confirmation — (a) record the case memory, then (b) propagate the plan into config.**

**(a) Persist the intent** so the next session + the calibration agent inherit *why* the setup looks as it
does, not just the files:
- the **site config** mode env vars — the structural record (env vars = intent, `feedback_env_vars_are_intent_case_dir_is_truth`);
- a **`calibration-log`** session log under `use_cases/$SITE/memory/logs/` (science goal, target granularity,
  data sources, PFT mapping or skip decision, seed) — anchored to the confirmed `research_plan.md`;
- optionally seed initial **site knowledge** via `inject-knowledge` — only *verified* facts the user gave you
  (a measured target value, a known site trait), never a guess (the evidence gate, `docs/33`).

**(b) Propagate the confirmed plan into the config files** (all under `$DEST = $A2MC_ROOT/use_cases/$SITE`):

1. **Site config** `use_cases/$SITE/config/<site>_config.sh` — fill Section 1 (name, lat/lon, surface/domain data), Section 2 (`A2MC_PFTS` — the 1-based **FATES** PFT ids of the calibrated PFTs), Section 5 mode env vars (`A2MC_ELM_OPTIONS`, `A2MC_FATES_PARTEH_MODE`, Tier-2 flags). These mode vars are what makes retrieval configuration-aware — set them to the user's actual run, not the template defaults.
2. **Validation targets + cost function** `use_cases/$SITE/validation/targets.yaml` — one entry per target. **Key must be `PFT<id>_<vartype>`** (e.g. `PFT10_leaf`, `PFT9_fineroot`); a non-matching key is silently dropped at runtime. Snapshot targets carry a scalar `observed` + `uncertainty` matched at `time_year`/`time_month`; **time-series / several-snapshot** targets use an `observations:` list (one point per time). Several stocks → several targets. Only enter values the user gave you. **The cost function lives here too:** a top-level `cost_config:` block (`error_method`, `aggregation_method`) + optional per-target `cost_method` / `weight` (defaults: `relative_error` + `rmsre` + weight 1.0) — **match each `cost_method` to the variant** (a series may use `nse`/`kge`/`nrmse`; a snapshot cannot — skill scores need ≥2 points). Validate with `tools/validate_targets_config.py` (it checks the keys, the `cost_config` metrics against the valid sets, and warns on mixing relative + absolute metrics under `rmsre`). Format + examples: the seed `targets.yaml` header and `docs/a2mc_reference/user_guide.md` §4.5.
3. **Parameters** `use_cases/$SITE/parameters/` — drop in the user's list, or build one in **Step 4b** (below). The list defines the entire Morris search space, so it is the highest-leverage design choice here — do not shortcut it by copying Kougarok's set.
3b. **Round record** `use_cases/$SITE/config/calibration_rounds.yaml` — **generate this LAST, after the parameter list exists (Step 4b)**: it derives `A2MC_N_PARAMS` / ensemble size / the SALib-problem path from the parameter list, so generating it before Step 4b reads an incomplete config (and Step 5's `check_calibration_rounds` then fails). **Do NOT hand-author it** (it duplicates the configs and silently drifts). Once the param list is built: source the configs, then `python tools/generate_calibration_rounds.py --round 1 --write` (fills params/ensemble/paths/targets/protocol/milestone/commits from the environment; leaves `rationale`/`changes_from_previous`/`patches` as `TODO`). Fill those by hand, then `python tools/check_calibration_rounds.py`.

## Step 4b — Build (or vet) the parameter list from the mechanisms

The parameter list is the single most consequential decision in setup: it *is* the sampling design's search space — whichever method you choose (Morris, Sobol, LHS), every one of them samples exactly the parameters on this list and nothing else. A list that omits the parameters that actually drive a target guarantees that target can never calibrate; a list padded with irrelevant parameters wastes the ensemble. So when the user has no list (interview D case c), or a rough one (case b), **build/complete it by studying the mechanisms — never by guessing from parameter names** (Calibration Rule #2). When the user has a vetted list (case a), still run the coverage check at the end.

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
1b. **Verify load-bearing candidates in the SOURCE, not only the knowledge layers.** The wiki, the
   curated overlay and RAG are *leads*; the Fortran is the authority. A parameter's `long_name`, units
   or documented range can be wrong, and a parameter can be **inert** in your configuration — read by
   nothing, guarded to zero, or superseded by a mode switch — while still reading as a plausible lever.
   Escalate to source when the parameter is load-bearing for a target, when the knowledge layers are
   ambiguous or disagree, or when a bound would be set from a description alone. Trace
   **read → internal variable → equation** in `${A2MC_MODEL_PATH}`; a name lookup is not a trace. Two
   instances from this branch: `fates_cnp_prescribed_puptake` reads as a fraction and is a binary mode
   flag ([[reference_fates_prescribed_puptake_fixed_on_fork]]), and `eca_alpha_ptase`/`lambda_ptase` are
   hard-guarded to zero in api-43 ([[reference_fates_eca_ptase_disabled_api43]]). See
   [[feedback_param_description_can_lie_verify_in_source]]. **A parameter that cannot be traced to an
   equation does not belong on the list** — it costs a column and samples nothing.

2. **Pull prior experience** from Adaptive Memory: generic `memory/gained_knowledge/parameters.json` (known bounds/sensitivities) and, for a similar site, the reference site's `use_cases/<ref>/memory/gained_knowledge/{parameters,discoveries,failed_approaches}.json` (which parameters were sensitive, which pitfalls to avoid). Mechanistic insight transfers across sites; exact values do not.
3. **Assemble each entry** with: FATES parameter name, the PFT(s) it applies to (Morris shorthand `{param}_{pft}`, e.g. `alloc_storage_cushion_10`; official FATES names carry no PFT suffix — see `docs/a2mc_reference/fates_data_reference.md`), the target/mechanism it addresses, and **bounds**. Anchor each bound to the FATES default parameter-file value plus a defensible ± range from the knowledge base / literature / the reference list. **Never invent a bound** — an unfounded range silently distorts the whole sensitivity analysis. If a bound is genuinely unknown, mark it `TODO` and flag it to the user.
4. **Right-size, don't pad.** Morris cost = `n_trajectories × (n_params + 1)`; a broad list is affordable *because Phase 1 sensitivity prunes it* — but every parameter must trace to a target through a named mechanism. No "might as well include it." Flag targets with no driving parameter (a coverage gap) and parameters with no target link (drop them).
5. **Present the proposed list for review before writing — this is GATE 2, and it is ITERATIVE.** Per parameter: the target it serves, the mechanism, the source citation, and the bound rationale. Answer every question and fold in every requested add / drop / bound change, **re-presenting until the user agrees** (like curated-knowledge writes — do not write while a request is open). On agreement, write both files to `use_cases/$SITE/parameters/` matching the Kougarok examples' format — the parameter list (names + bounds) and the SALib problem file (`num_vars`, names, bounds) — and point `A2MC_PARAM_LIST_FILE` / `A2MC_SALIB_PROBLEM_FILE` at them.

6. **Agree on the ensemble-simulation design (still GATE 2) — surface the trade-offs, then follow the user's choice.** With the parameter count now fixed, confirm the **sampling scheme** (`A2MC_SAMPLING_SCHEME`) + resulting **ensemble size** and **compute cost** with the user *before* writing the config / round record. Compute and **SHOW the numbers per option** so the choice is informed (A2MC's `calculate_ensemble_size()` in `a2mc_config.sh` gives the exact count per scheme):
   - **Morris** (default) — `n_traj × (n_params+1)` sims: a cheap sensitivity **screening** (μ*). e.g. `30×(171+1) = 5160`.
   - **Sobol** — `N × (2·n_params+2)` sims (SALib Saltelli, `N`≈500–1024): rigorous first + total-order variance sensitivity, but **often 10–100× more simulations** → far more core-hours, much longer wall-clock, heavier queue pressure. e.g. `512×(2·171+2) = 176,128`.
   - **LHS** — `N` space-filling samples (user-set `N`): cheaper than Sobol, no sensitivity indices.
   Multiply the ensemble size by the per-case core-hours (ADSP + RGSP + TRANS) for a **core-hour + wall-clock estimate**, and state it plainly (queue/walltime reality too). **Recommend** — Morris for screening; Sobol only when full variance decomposition is the goal and the compute budget genuinely allows it. **But if the user chooses the expensive path (e.g. Sobol), FOLLOW it — inform of the trade-off, never override an explicit choice** (the defer-to-the-user rule from Step 0). Iterate until the user agrees; only then set `A2MC_SAMPLING_SCHEME` / `A2MC_N_TRAJECTORIES` and generate the round record.

**If the user brought a list (case a/b):** run steps 1–2 as a *coverage check* — confirm every target has ≥1 driving parameter in the list and flag any parameter with no mechanistic tie to a target. Report gaps; do not silently rewrite their list.

**Now the parameter list exists → generate the round record (Step 4 item 3b):** `generate_calibration_rounds.py --round 1 --write` (it derives from the param count/salib you just wrote) → fill the TODO narrative → `check_calibration_rounds.py`. That is the last prep artifact; then run the Step 5 gate.

## Step 5 — Preflight: is the setup ready for Phase 0? (goal-conditional gate)

```bash
source a2mc_config.sh
source use_cases/$SITE/config/<site>_config.sh
print_config                        # confirm paths/PFTs/mode resolved
python tools/describe_mode.py       # confirm the mode A2MC will actually use
python tools/check_setup_ready.py   # the aggregate, goal-conditional readiness gate
```

`check_setup_ready.py` is the single **goal-conditional** readiness gate. It runs the *universal*
checks — model path + matched milestone, **site config overrides the machine config**, `targets.yaml`
valid **AND every target mapped to a model output variable with a cost function established**,
parameter list present, `calibration_rounds.yaml` present + consistent with the config — and reports
**`N/A` (never `✗`) for checks that don't apply to this user's goal**: PFT inventory only for
PFT-level targets (an ecosystem/flux goal skips it), FATES base file + RAG milestone only when FATES
is on, and the spin-up **protocol is reported, not required** (spin-up is the user's decision, set in
config — independent of the target granularity). It
wraps `validate_targets_config.py` + `check_calibration_rounds.py`, so a green run means those pass
too. Exit 0 = ready for Phase 0; every `✗` must be resolved first. Matching the checkout to a milestone
uses `scripts/rag_match.py` — full how-to in `docs/a2mc_reference/version_association_howto.md`.

## Step 5b — Log the setup ★ (the case's origin record)

**Do this before handing off, not "if there is time".** First-run setup makes the decisions that are
hardest to reconstruct later and least visible in the files they produce: the run configuration, the
PFT identity mapping, and why each parameter is on the list. The configs record *what* was chosen;
only a log records *why*.

Invoke **`calibration-log`** and write a **free-form session log** under
`use_cases/$SITE/memory/logs/` (offline mode gives the flat `logs/{stem}.md` layout,
`stem = YYYYMMDDx_<descriptor>`). It sits beside the autonomous agent's own logs, so both modes'
records synthesize together later.

Capture the reasoning, not the file list:

- **the run configuration** and why — FATES on/off, PARTEH mode, nutrient pathway, competition;
- **the PFTs**: which functional types this case calibrates, **their ids in THIS model version**, and
  how they were verified against the base parameter file's `fates_pftname` — ids are **not stable**
  across versions ([[feedback_verify_pft_identity_across_versions]]);
- **each parameter**: full model name, the target it serves, the mechanism, and where the bound came
  from — including any candidate **rejected** and why (inert, mode-switched, derived by a transform);
- **the targets**, their sources, uncertainties, and anything left `TODO`;
- **which observations are calibration vs validation**, since only the first are scored;
- **the sampling method** chosen and the cost that justified it.

The parameter list and the PFT-id mapping are the two things most likely to be questioned months
later. A case whose origin log names them **with their evidence** can be re-derived; one without it
cannot, and its values quietly become unfalsifiable
([[feedback_bind_derived_facts_to_their_source]]).

Curated *findings* are a different lane — they belong in
`use_cases/$SITE/memory/gained_knowledge/` through the human-gated review path, never hand-written
([[feedback_no_case_state_in_memory]]).

## Step 6 — Hand off to Phase 0

Setup is done. Route to **`phase0-design`** to sample the parameter space and submit the ensemble. From here on the standard cold-start flow applies: `onboard-session` on the next session, `arm-hpc-monitoring` once the ensemble is in flight.

> **Or start a driven run.** To go straight from setup-complete into a run that drives itself to the calibration goal (rather than a bare Phase-0 hand-off), invoke **`calibration-goal`** — the run-to-convergence driver loops the 7-phase workflow to CONVERGED, pausing only at the human gates.

The setup log is **Step 5b above**, and it is written before this hand-off — not offered afterwards.

## Footguns

- **A2MC_MODEL_PATH unset** — the orchestrator hard-fails at startup. Set it in Step 3, verify in Step 2.
- **Template mode defaults left in place** — the seed config ships a FATES+CNP+ECA default; if the user runs carbon-only or ELM-only, retrieval will surface the wrong content until you fix Section 5.
- **Bad target keys** — anything not matching `PFT<id>_<vartype>` is dropped silently; always run `validate_targets_config.py`.
- **Fabricated targets/paths** — the single most damaging first-run error. Placeholders marked `TODO`, never invented numbers.
- **Clobbering an existing site** — check `use_cases/<site>/` before `cp`; if it exists, this is probably an `onboard-session` case, not `a2mc-init`.
- **Asserting a milestone without verifying** — always run `rag_match.py`; never name the profile from the folder name or an assumption.
- **Parameter list guessed from names** — the list defines the entire search space for whichever sampling method is used; build it from the knowledge system (curated relationships + RAG + CNP guide + Adaptive Memory), not from what a parameter is called (Calibration Rule #2). Fabricated bounds distort the sensitivity analysis — mark unknown bounds `TODO`. Do not reflexively copy the Kougarok 162-parameter set; it is Kougarok-specific.
- **Putting validation data in `targets.yaml`** — `targets.yaml` is **calibration-only** (everything in it is scored/optimized against). Data the user wants as an *independent cross-check* (not fit) — e.g. MODIS GPP/LAI, soil T/moisture profiles for a biomass calibration — is **validation data**: keep it in its native format and compare via a purpose-built script; never add it to `targets.yaml`. Classify calibration vs validation in the 1.1 interview.
- **Over-asking a new user for detail they don't need** — do NOT demand dominant PFTs, per-PFT biomass, or a parameter list when the goal is **ecosystem-level** (e.g. MODIS/tower GPP). Let 1.0 set the granularity first; PFT-level questions (1.2, 1C PFTs) apply *only* to PFT-level targets. Forcing FATES internals on someone who only has an ecosystem flux is the fastest way to stall a first run.
- **Bare relative path from the wrong cwd** — always derive `A2MC_ROOT="$(git rev-parse --show-toplevel)"` and prefix writes (`"$A2MC_ROOT/use_cases/$SITE/…"`). `A2MC_ROOT` is unset on a first run (a site config sets it, none exists yet), so `$A2MC_ROOT/use_cases/$SITE` with an *empty* prefix expands to `/use_cases/$SITE` — the filesystem root. Verify `$A2MC_ROOT/a2mc_config.sh` exists before writing.
- **Building config before the plan is confirmed** — write `use_cases/$SITE/research_plan.md` and get the user's confirmation BEFORE populating `a2mc_config.sh` / the site config / `targets.yaml` / the parameter list. The plan is the single human-review artifact; skipping it means the user first sees your interpretation as already-written files, which is far harder to correct. Record the case memory only after the plan is confirmed.
- **Hand-authoring `calibration_rounds.yaml`** — it duplicates values already in the two configs (param count, ensemble size, artifact paths, targets file, protocol, milestone), so a hand-typed round record drifts. Generate it from the sourced config (`tools/generate_calibration_rounds.py --round N --write`) and verify with `tools/check_calibration_rounds.py`; never trust a hand-typed one.
- **Naming a milestone without matching the checkout** — to associate the user's ELM + FATES commits with a registered RAG milestone, run `scripts/rag_match.py` (never assert the profile from a folder name). Auto-detection, drift tiers T1/T2/T3, and the five scripts are documented in `docs/a2mc_reference/version_association_howto.md`.
- **Treating a leftover check as a hard failure** — `check_setup_ready.py` is goal-conditional: `N/A` on PFT inventory (ecosystem goal), FATES base file (ELM-only), or an as-yet-ungenerated SALib file is expected, not a blocker. Only `✗` blocks Phase 0.

## Cross-references

- `onboard-session` — the resume-an-existing-setup counterpart (route there once configured).
- `phase0-design` — the immediate hand-off (design + submit the ensemble); consumes the parameter list built in Step 4b.
- `phase1-exploration` — Morris sensitivity that prunes the Step-4b list (why a broad-but-grounded list is safe).
- `calibration-log` — record the setup session.
- `docs/a2mc_reference/user_guide.md` §1–§3 (install/config/run), §4.5 (targets), §6 (knowledge system); `fates_data_reference.md` (parameter naming / Morris shorthand); `rag_reference.md` (RAG query how-to + Python-3.10 binary).
- `docs/a2mc_reference/version_association_howto.md` — **match ELM + FATES commits to a registered RAG milestone** (the Step-2 milestone step: `rag_match.py`, drift tiers, the five scripts); `version_association_workflow.md`, `mode_aware_workflow.md` — deeper milestone + mode detail.
- `tools/generate_calibration_rounds.py` / `check_calibration_rounds.py` — generate the round record from config + validate it; `tools/check_setup_ready.py` — the Step-5 goal-conditional readiness gate.

## Changelog

- 2026-07-11: **Step 0 (gauge experience + orient) + `calibration_rounds.yaml` in the flow + goal-conditional Step-5 gate.**
  Added **Step 0**: first **gauge the user's ELM/ELM-FATES experience** and adapt session-wide depth
  (teach + orient novices; defer to experts, don't impose defaults over an explicit choice), then orient
  (two-layer config where the site config *overrides* the machine config, mode-awareness, the 7-phase
  loop). Two model-fidelity corrections folded in (PI): **spin-up is a separate decision from target
  granularity** (even a GPP goal may need spin-up — interviewed in 1B, not inferred), and **ELM's static
  surfdata PFTs are distinct from FATES's dynamic PFTs** (a target's PFT id is a FATES id from the base
  file — noted in Step 0 + interview 1.2). Fixed a stale var name (`A2MC_PFT_LIST` → `A2MC_PFTS`). Step 4 (b) now generates the **round
  record** from the sourced config (`tools/generate_calibration_rounds.py --write` → fill TODO
  narrative → `check_calibration_rounds.py`) instead of hand-authoring it. **Step 5** replaced with
  `tools/check_setup_ready.py`, a single **goal-conditional** readiness gate (universal checks +
  `N/A` for PFT inventory on ecosystem goals, FATES/RAG when FATES off, spin-up reported-not-required;
  wraps `validate_targets_config.py` + `check_calibration_rounds.py`). New footguns (hand-authoring
  the round record; naming a milestone without `rag_match.py`; treating `N/A` as a blocker) + cross-ref
  to `version_association_howto.md`. Distilled from the api-31→api-43 Kougarok migration (dev_logs
  20260710o–y, 20260711a) — that migration IS the new-site/new-user prep path. Requested by the PI.
- 2026-07-09: **Step 2b — offer fork-safe model-checkout remotes.** After verifying the checkout, the agent
  now checks the model repo's git remotes (E3SM root + FATES submodule); if `origin` is an upstream URL with
  push enabled, it asks the user for their fork URLs and (with consent) adds a `fork` remote + disables push
  to `origin`, so a stray `git push origin` can't reach upstream. Generic (no host assumptions); prefers SSH
  (HTTPS PAT without `workflow` scope is refused on `.github/workflows/`). Pairs with the model-dev track
  (`add-fates-parameter`, `feedback_model_source_push_fork_only`). Requested by the PI.
- 2026-07-09: **Variant-aware targets.** Interview 1D + research plan + Step-4 `targets.yaml` now classify each
  target's variant — snapshot / time-series / several-snapshots (an `observations:` list, scored on all points)
  / several stocks (separate targets) — and match the per-target `cost_method` to it (skill scores like
  `nse`/`kge` need ≥2 points). Pairs with the `evaluate_case.py` time-series upgrade (`year_start` +
  `extract_case_series`). Requested by the PI.
- 2026-07-08: **Cost function folded into setup.** The targets the user gives now also specify the cost
  function — interview 1D + the research plan + Step-4 `targets.yaml` capture a `cost_config` (error_method,
  aggregation_method, tolerance) + optional per-target `cost_method`/`weight` (defaults `relative_error` +
  `rmsre` + ±20%), validated by `validate_targets_config.py`. Paired with the `evaluate_case.py`
  reconciliation so both scoring paths honor it. Requested by the PI.
- 2026-07-08: **Research-plan confirmation gate before building (Step 4).** After the interview + milestone,
  the agent now drafts `$A2MC_ROOT/use_cases/$SITE/research_plan.md` (goal, granularity, targets, mode,
  milestone, PFTs or ecosystem-only, parameter approach, seed, open gaps), presents it, and gets the user to
  **confirm** before any config is written; only on confirmation does it record the case memory + propagate
  the plan into the config files. **Path-safety:** all writes are anchored to `A2MC_ROOT` (derived via
  `git rev-parse --show-toplevel` — it is unset on a first run, and a bare `$A2MC_ROOT/use_cases/$SITE` with
  an empty prefix would write to the filesystem root). New footguns (building before confirmation; bare
  relative path from the wrong cwd). Requested by the PI.
- 2026-07-08: **Goal-and-data-first interview + guided path for users new to FATES.** Restructured Step 1 to
  lead with the science goal + **target granularity** (1.0) and a data-inventory helper (1.1): an
  **ecosystem-level** goal (e.g. MODIS/tower GPP) does NOT require enumerating dominant PFTs or per-PFT
  biomass, so PFT identification (1.2) + the 1C PFT questions are now conditional on PFT-level targets. Added
  a **path choice** (know-your-setup vs guided). New footgun (over-asking a new user for detail they don't
  need). Cross-linked the operating-discipline stance (`AGENTS.md` §Offline-Agent Operating Discipline +
  `feedback_offline_agent_operating_discipline`). Requested by the PI.
- 2026-07-07: **Parameter-list building (Step 4b).** Interview D reworded to "do you have an initial list of parameters to be calibrated?" with a 3-case branch (vetted / rough / none). Added **Step 4b** — when the user has no list (or a rough one), the agent studies the mechanisms via `HybridRetriever.get_calibration_context()` + curated `curated_relationships_<profile>.yaml` + the CNP calibration guide + Adaptive Memory to build a target-driven list with source-anchored bounds (no fabricated values), presented for review before writing; a vetted list gets a coverage check instead. New footgun (list-from-names / fabricated bounds). Requested by the PI.
- 2026-07-07: Initial version — official first-run setup flow for the offline agent (interview → verify checkout/milestone → create + populate use case → hand off to phase0-design). Fills the gap between "cloned the repo" and `phase0-design`; complements `onboard-session` (which assumes an existing setup). Requested by the PI.
