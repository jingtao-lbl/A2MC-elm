# Mode-Aware RAG Workflow

**Status:** Phase B complete (v2.92, 2026-04-29). Production-ready.

This is the comprehensive reference for A2MC's mode-aware RAG retrieval. It covers the schema, the env-var/site-config interface, common recipes, and troubleshooting. For implementation history, see `docs/20_Mode_Aware_RAG_Retrieval_Plan.md` (parent plan) and `docs/21_Mode_Aware_RAG_Phase_B_Implementation.md` (Phase B detail).

If you're new here, start at "What problem does this solve?" then jump to "Common recipes".

## What problem does this solve?

A2MC retrieves FATES + ELM documentation chunks for AI prompts during diagnosis (Phase 3) and hypothesis generation (Phase 4). Without mode awareness, every prompt sees content for every FATES capability — CNP allocation theory in carbon-only PARTEH=1 runs, fire mechanism details in runs with no SPITFIRE, plant hydraulics theory in runs with empirical BTRAN. The AI ends up reasoning over content that does not apply to the current simulation, recommending parameters that the model will silently ignore, or worse, citing mechanisms that aren't compiled in.

Mode-aware retrieval filters chunks at the ChromaDB layer based on a `ConfigMode` instance built from the user's env vars and `ELM_OPTIONS`. The result: the AI sees only mode-applicable content. Zero leakage from CNP theory into PARTEH=1 retrieval; zero leakage from fire docs when SPITFIRE is off; etc.

## Architecture (1-minute version)

```
                         ConfigMode (20 dimensions)
                           │
                           │ to_chroma_where()
                           ▼
                       {"$and": [...]} ───► ChromaDB
                                                │
                          chunk metadata        │
                          (applies_in_*)        ▼
                                            filtered top-K results
                                                │
                                                ▼
                                       AI prompt context
```

Three independent metadata sources tag chunks during the build:

1. **YAML curation**: `applies_in:` block on a parameter, mechanism, or output entry in `rag/data/curated_relationships_<profile>.yaml`. Inherited by the corresponding chunk and graph node.
2. **Path-prefix table**: hardcoded list in `rag/loader.py` mapping wiki source paths to mode tags (e.g., `fire/` → `fates_spitfire_mode: [1, 2]`).
3. **Default-permissive sweep**: any chunk/node not tagged by the above two ends up `applies_universal: True`.

A chunk is in **exactly one** of these states. A `ConfigMode.to_chroma_where()` builds a `$and` clause across all 20 axes; each branch is `$or [{applies_universal: True}, {applies_in_<axis>_<active>: True}]`. The chunk passes if it's universal OR matches the active value on every axis.

## The 20 dimensions

Defaults reflect ELM api-43-1's `namelist_defaults.xml` (a vanilla ELM run). Site configs override via env vars.

### Tier 1 — Primary (7)

| Field | Type | Values | ELM default | Source |
|---|---|---|---|---|
| `bgc_mode` | str | `sp`, `cn`, `bgc`, `fates` | `sp` | `namelist_defaults.xml:32` |
| `use_fates` | bool | derived from `bgc_mode == 'fates'` | False | derivation rule |
| `parteh_mode` | int | 1, 2 | 1 | `namelist_defaults.xml:2251` |
| `use_fates_nocomp` | bool | true / false | False | `namelist_defaults.xml:2278-2280` |
| `nutrient` | str | `''`, `c`, `cn`, `cnp` | `''` | only meaningful when bgc != sp |
| `nutrient_comp_pathway` | str | `rd`, `eca` | `rd` | `namelist_defaults.xml:67` |
| `soil_decomp` | str | `''`, `ctc`, `century` | `''` | activated only via `-soil_decomp` |

### Tier 2 — FATES feature flags (6, direct wiki impact)

| Field | Type | Default | Wiki content gated |
|---|---|---|---|
| `fates_spitfire_mode` | int | 0 | `fire/` (5 docs) |
| `use_fates_planthydro` | bool | False | `biophysics/hydraulics/` (3 docs) |
| `use_fates_logging` | bool | False | `logging/` (3 docs) |
| `use_fates_sp` | bool | False | All FATES dynamics |
| `use_fates_ed_prescribed_phys` | bool | False | `biophysics/photosynthesis.md` |
| `use_fates_fixed_biogeog` | bool | False | Competition + dyn biogeography |

### Tier 3 — Secondary compset modifiers (7, scaffolding)

| Field | Type | Default | Compset suffix |
|---|---|---|---|
| `crop` | bool | False | `-crop` (CROP) |
| `dynamic_vegetation` | bool | False | `-dynamic_vegetation` |
| `methane` | bool | False (auto-derived: True iff `bgc_mode == 'bgc'`) | `-methane` |
| `hydrstress` | bool | False | `-hydrstress` (PHS) |
| `topounit` | bool | False | `-topounit` (TGU) |
| `irrig` | bool | False | `-irrig` (WFM) |
| `solar_rad_scheme` | str | `''` | `-solar_rad_scheme top` (TOP) |

## Configuration interface (v2.94+)

`ConfigMode.from_env()` resolves the active mode with **env vars as the primary source (user intent)**, enriched by the CIME case dir when available. **No silent default** — if no source produces `bgc_mode`, it raises with instructions.

### Resolution priority

```
For each field:
  1. User-provided env var (PRIMARY) — represents user INTENT
  2. CIME case dir (ENRICHMENT)      — fills in fields env vars didn't set
  3. Dataclass default               — last-resort baseline (ELM source default)
  4. Raise (if no bgc_mode anywhere)
```

This ordering reflects the principle that **user-set env vars are intent** (what they want A2MC to calibrate), while the case dir is **downstream truth** (their intent + ELM defaults applied by CIME). The two CAN disagree: a stale case from before the user updated env vars, or pre-build state when the case doesn't exist yet (Phase 0). When they conflict on a specific field, env vars win and a `RuntimeWarning` is emitted ("case dir may be stale; rebuild to refresh").

### Path 1 (PRIMARY): user-provided env vars

| Env var | Schema field | Notes |
|---|---|---|
| `A2MC_ELM_OPTIONS` | parsed | Tier 1 (`bgc`, `nutrient`, `nutrient_comp_pathway`, `soil_decomp`) and Tier 3 (`crop`, `methane`, `hydrstress`, `topounit`, `irrig`, `solar_rad_scheme`) parsed from this string |
| `A2MC_BGC_MODE` | `bgc_mode` | Override Tier 1 dimension if not in `A2MC_ELM_OPTIONS`; `use_fates` derives from this |
| `A2MC_USE_FATES` | `use_fates` | **Live input to case construction** — `tools/create_case.sh` writes `use_fates=${A2MC_USE_FATES}` into `user_nl_elm` (the namelist-override layer). On the **Python `ConfigMode`** side (RAG-mode selection) `use_fates` is *derived* from `bgc_mode` and this var is only a cross-check: set it consistently with `-bgc` (both FATES-on, e.g. `-bgc fates` + `.true.`; or both FATES-off, e.g. `-bgc bgc` + `.false.`), or `from_env()` raises. Not deprecated. See `memory/dev_logs/20260701a_A2MC_USE_FATES_Live_Input_Not_Deprecated.md`. |
| `A2MC_FATES_PARTEH_MODE` | `parteh_mode` | 1 = carbon-only; 2 = CNP |
| `A2MC_USE_FATES_NOCOMP` | `use_fates_nocomp` | bool string |
| `A2MC_FATES_SPITFIRE_MODE` | `fates_spitfire_mode` | int 0/1/2 |
| `A2MC_USE_FATES_PLANTHYDRO` | `use_fates_planthydro` | bool |
| `A2MC_USE_FATES_LOGGING` | `use_fates_logging` | bool |
| `A2MC_USE_FATES_SP` | `use_fates_sp` | bool |
| `A2MC_USE_FATES_ED_PRESCRIBED_PHYS` | `use_fates_ed_prescribed_phys` | bool |
| `A2MC_USE_FATES_FIXED_BIOGEOG` | `use_fates_fixed_biogeog` | bool |

Anything you DO set is treated as explicit user intent. Anything you don't set falls through to Path 2.

### Path 2 (ENRICHMENT): CIME case directory

If `A2MC_CASE_DIR` is set (or `A2MC_E3SM_ROOT` + `A2MC_CASE_NAME` together resolve to an existing case at `$A2MC_E3SM_ROOT/cime/scripts/$A2MC_CASE_NAME`), A2MC parses three artifacts:

| Artifact | What it provides |
|---|---|
| `env_run.xml` | `ELM_BLDNML_OPTS` (compset + xmlchange append): `-bgc`, `-nutrient`, `-nutrient_comp_pathway`, `-soil_decomp`, Tier 3 flags |
| `user_nl_elm` | User namelist overrides (Tier 2 `use_fates_*` flags, `fates_parteh_mode`) |
| `CaseDocs/lnd_in` (or `Buildconf/elmconf/lnd_in`) | Post-build fully-resolved namelist |

This serves two purposes:
1. **Fills in fields env vars don't specify** — most users don't set every Tier 2 flag in env vars; the case dir's `lnd_in` provides them.
2. **Verification** — if env vars and case dir disagree, the warning surfaces a stale build state.

The example case at `Offline/CIME_case_example/Kougarok_ELM-FATES_PtCNPEn86_TRANS/` ships in the repo as a reference for the layout.

```bash
# In your site config:
export A2MC_CASE_DIR="/path/to/your/CIME/case"

# OR rely on auto-detection from existing A2MC settings:
export A2MC_E3SM_ROOT="/path/to/E3SM_FATES_checkout"
export A2MC_CASE_NAME="Kougarok_ELM-FATES_PtCNPEn86_TRANS"
```

### Path 3: dataclass defaults

If neither env vars nor case dir provide a value for a non-required field, A2MC uses the dataclass default. These mirror ELM source defaults from `namelist_defaults.xml`:

- `parteh_mode = 1` (carbon-only; line 2251)
- `nutrient_comp_pathway = 'rd'` (line 67: `<nu_com>RD</nu_com>`)
- `fates_spitfire_mode = 0`, all `use_fates_*` and Tier 3 flags `false`

### Path 4: raise

If `bgc_mode` is missing from ALL sources (no env var, no case dir), `from_env()` raises a `ValueError` listing the four ways to fix it. The `bgc_mode` is the irreducible minimum because `use_fates` derives from it and the kb_source filter depends on it.

### Why env vars are primary (and why this changed in v2.94)

v2.93 had case-dir-first priority, but that's wrong: in Phase 0 (pre-build), no case dir exists yet — A2MC has to BUILD the case from user intent (just like Phase 5 testing does). Env vars are the only source. Reversing the priority in v2.94 makes the same code path work for both Phase 0 (no case yet) and post-build runs (case exists). User intent always wins; case dir is a useful enrichment layer.

See `memory/feedback_env_vars_are_intent_case_dir_is_truth.md` for the principle.

## Common recipes

### Recipe 1: Default Kougarok run (FATES + PARTEH=2 + ECA + CNP)

```bash
# In use_cases/Kougarok/config/kougarok_config.sh:
export A2MC_ELM_OPTIONS="-bgc fates -nutrient cnp -nutrient_comp_pathway eca"
export A2MC_FATES_PARTEH_MODE=2
```

Runtime: every chunk that mentions PARTEH=1 carbon-only theory is filtered. Every chunk in `fire/`, `biophysics/hydraulics/`, `logging/` is filtered. Default Kougarok retrieval contains: universal FATES wiki, CNP-mode parameters, ECA-pathway parameters, parteh-2 theory.

### Recipe 2: Carbon-only PARTEH=1 calibration (no nutrient cycling)

```bash
export A2MC_ELM_OPTIONS="-bgc fates -nutrient c"
export A2MC_FATES_PARTEH_MODE=1
```

Runtime: every chunk tagged with `parteh_mode: [2]` is filtered (CNP allocation theory, PID controller params, ECA km parameters, etc.). Carbon-only allocation theory passes (its tag is `parteh_mode: [1]`). Universal content (allometry, phenology, mortality) passes.

### Recipe 3: Fire-active calibration

```bash
export A2MC_ELM_OPTIONS="-bgc fates -nutrient cnp -nutrient_comp_pathway eca"
export A2MC_FATES_PARTEH_MODE=2
export A2MC_FATES_SPITFIRE_MODE=1
```

Adds `fire/` chunks to the retrieval set. Without `A2MC_FATES_SPITFIRE_MODE=1`, those chunks would be filtered (default `0`).

### Recipe 4: Plant hydraulics on

```bash
export A2MC_ELM_OPTIONS="-bgc fates -nutrient cnp -nutrient_comp_pathway eca"
export A2MC_FATES_PARTEH_MODE=2
export A2MC_USE_FATES_PLANTHYDRO=true
```

Adds `biophysics/hydraulics/` chunks. The inverse-tagged `biophysics/transpiration.md` (BTRAN empirical pathway) is filtered when planthydro is on.

### Recipe 5: ELM-only run (no FATES)

```bash
export A2MC_ELM_OPTIONS="-bgc bgc -nutrient cnp -nutrient_comp_pathway eca -soil_decomp ctc"
```

`use_fates` derives to `False` because `bgc_mode='bgc'`. Phase A's `kb_source='elm'` filter activates, removing all FATES content structurally. Phase B per-axis filters apply additionally to the surviving ELM chunks.

## Curating new mode-restricted entries

### Adding `applies_in:` to a YAML entry

`rag/data/curated_relationships.yaml` (the canonical) and `rag/data/curated_relationships_<profile>.yaml` (per-milestone). Add the block under the entry, before existing fields:

```yaml
parameters:
  fates_my_new_param:
    applies_in:
      use_fates: [true]
      parteh_mode: [2]
      nutrient: [cnp]
      nutrient_comp_pathway: [eca]
    category: cnp
    controls: ...
    affects: ...
```

Always include `use_fates: [true]` for FATES-side params; the validator (Dim F) will warn otherwise.

### Adding a wiki path-prefix entry

In `rag/loader.py`, append to `_WIKI_PATH_PREFIX_TAGS`:

```python
("my-new-section/", {
    "use_fates": [True],
    "fates_my_flag": [True],
}),
```

Three matching modes:
- `dir/` (trailing slash) — directory prefix
- `dir/file.md` (.md or .rst) — exact filename
- `dir/prefix_` (no extension) — filename-prefix substring

### Adding a new mode dimension

Four-line change in `tools/config.py`:

1. Add the field to `ConfigMode` dataclass with default
2. Add the parsing in `ConfigMode.from_env()` (and any constraint)
3. Add the entry to `ALL_AXIS_VALUES`
4. Optionally, add to `FATES_SPECIFIC_AXES` if it implies use_fates: [true]

`to_chroma_where()` and `build_applies_in_flags()` iterate over `ALL_AXIS_VALUES`, so they pick up new dimensions automatically.

## Validating after curation

The complete validation suite has 7 layers (4 tiers + 3 new validators in v2.95+) plus the unit-test fixtures and live smoke tests. The single-button command is `verify_mode_aware.py`:

```bash
# All 6 verification layers in sequence (~20 sec)
python scripts/verify_mode_aware.py
# Look for: Phase A+B status: GREEN
```

If you want to run individual layers (e.g., during development to focus on one):

```bash
# Tier 2 (YAML schema): catches typos in applies_in: blocks
python tools/yaml_wiki_validator.py \
    --yaml rag/data/curated_relationships.yaml \
    --wiki docs/fates-knowledge-base/fates-codebase-wiki-e027a40 \
    --param-file docs/fates-knowledge-base/fates_params_info_e027a40.json \
    --output-cdl docs/fates-knowledge-base/elm_fates_output_info_e027a40.cdl \
    --output /tmp/yaml_validation.md

# Rebuild the index after curation (passes both FATES and ELM CDLs)
python scripts/build_rag_index.py --rebuild --profile api-43-1

# Tier 4 (mode-metadata propagation): YAML applies_in: → chunk metadata + graph nodes
python tools/mode_metadata_validator.py --profile api-43-1 \
    --output docs/a2mc_reference/mode_metadata_validation_api-43-1.md

# Validator #1 (snapshot): end-to-end integration test (5 fixture ConfigModes)
python tools/snapshot_validator.py --profile api-43-1 \
    --output docs/a2mc_reference/snapshot_validation_api-43-1.md

# Validator #2 (profile completeness): statistical coverage (5 categories)
python tools/profile_completeness_validator.py --profile api-43-1 \
    --output docs/a2mc_reference/profile_completeness_api-43-1.md

# Validator #3 (cross-milestone consistency): drift across milestone YAMLs
python tools/cross_milestone_validator.py \
    --output docs/a2mc_reference/cross_milestone_validation.md
```

Full validation playbook + when-to-run guidance: `docs/a2mc_reference/rag_validation_workflow.md`.

## ELM output coverage (v2.96+)

The build process now uses two source-grounded output CDLs:

- `docs/fates-knowledge-base/elm_fates_output_info_e027a40.cdl` — FATES-only registry, source-pinned to FATES commit `e027a40`
- `docs/fates-knowledge-base/elm_output_info_d40b843.cdl` — ELM-only registry, source-pinned to ELM commit `d40b843` (NEW v2.96)

The ELM CDL covers ~1640 ELM core history-output variables (TOTSOMC, TOTLITC, NFIX_TO_SMINN, TSA, hydrology vars, energy budget vars, etc.) that the FATES CDL deliberately excludes. Generated by `scripts/extract_elm_outputs.py` walking `components/elm/src/**/*.F90` for `hist_addfld1d/2d` registrations.

When the loader sees both CDLs, FATES wins on duplicate names (rare). Each chunk's `kb_source` correctly tags it (`fates` for FATES CDL, `elm` for ELM CDL); `source` field shows which CDL it came from.

Both CDLs auto-detected at build time from the milestone's commit short SHAs. Override via `--output-cdl` and `--elm-output-cdl` if needed.

**For adapter-kit users:** if you're adopting a new model (EcoSIM, ReSOM, etc.), generate YOUR model's output registry the same way — extract `set_history_var()`-style registrations from your source. See `extract_elm_outputs.py` as a template.

## Troubleshooting

### "ConfigMode.from_env() failed: ... is inconsistent with bgc_mode"

Your env has `A2MC_USE_FATES` set explicitly AND `A2MC_BGC_MODE` set, and the two contradict. Drop `A2MC_USE_FATES`; let it derive.

### "valueError: nutrient_comp_pathway='..' invalid"

Only `rd` and `eca` are accepted. Check ELM compset name; the third token after `-bgc` (e.g., `CNPRDCTCBC` is RD, `CNPECACTCBC` is ECA).

### Tier 4 reports "no chunks matched pattern" for a path-prefix entry

The wiki tree changed; the table entry is stale. Either remove the entry or update it to match the current path. Use `find docs/.../<wiki>/ -name '*.md' | grep <pattern>` to confirm.

### Filter clause produces empty retrieval

You probably have an inconsistent `ConfigMode` (e.g., `bgc_mode='sp'` + `parteh_mode=2`). SP runs don't have PARTEH; the per-axis flags filter every chunk. Check `print(ConfigMode.from_env().to_dict())` and confirm the values match your intent.

### Path-prefix tag added but chunk still passes filter for inapplicable mode

Two checks:

1. Did you rebuild the index? Path-prefix changes apply only at build time.
2. Does the `vector_store.add_documents` allowlist forward the new flag? Per-axis flags are pass-through (`startswith('applies_')`); but if you add a non-namespaced flag, it gets stripped silently.

### Real run: AI still recommends mode-inapplicable params

The graph layer surfaces user-explicit-asked params regardless of mode (see Doc 21 §B.3 design). If the user explicitly asks for `fates_cnp_pid_kp`, retrieval returns it. The mode filter applies to **vector similarity search**, not to graph traversal of explicit names. Phase A's prompt block (the active mode declaration at the top of every prompt) is the LLM-side guardrail. If the AI still recommends inapplicable params, the prompt block may need clearer language for the active mode.

## Implementation summary

| Layer | Files | Result |
|-------|-------|--------|
| Schema | `tools/config.py` (ConfigMode, ALL_AXIS_VALUES, build_applies_in_flags, to_chroma_where) | 20-dim schema; constraint enforcement |
| Curation | `rag/data/curated_relationships*.yaml` | 17 mode-restricted params + 3 mechanisms tagged |
| Build (chunk metadata) | `rag/loader.py` (path-prefix table), `rag/graph_builder.py` (graph node attrs), `rag/vector_store.py` (metadata pass-through) | Every chunk + node tagged |
| Retrieval | `rag/hybrid_retriever.py` (3 methods accept `config_mode`), `rag/retriever.py` (VectorRetriever forwards), `reasoning/base.py` (reads ConfigMode per call) | Filter applied at ChromaDB layer |
| Validation | `tools/yaml_wiki_validator.py` (Dim F), `tools/mode_metadata_validator.py` (Tier 4) | YAML schema + propagation chain validated |

Test coverage: 50 unittest fixtures + 6 smoke tests + 79 Tier 4 assertions.

## Related docs

- **Doc 20** (`docs/20_Mode_Aware_RAG_Retrieval_Plan.md`) — original plan + strategic decisions
- **Doc 21** (`docs/21_Mode_Aware_RAG_Phase_B_Implementation.md`) — Phase B implementation detail
- **`mode_aware_howto.md`** — quick how-to for site config setup
- **`elm_compset_reference.md`** — ELM compset flag reference (Tier 1 + Tier 3 sources)
- **`rag_validation_workflow.md`** — full RAG validation triangle (now quadrilateral with Tier 4)
- **`version_association_workflow.md`** — milestone selection (orthogonal to mode filtering)

## Phase B dev logs

- `memory/dev_logs/20260429a_Mode_Aware_Phase_A.md` — Phase A (kb_source filter, prompt block)
- `memory/dev_logs/20260429b_Phase_B_Wiki_And_YAML_Audit.md` — audit
- `memory/dev_logs/20260429c_Phase_B_Plan_Mistakes_Reflection.md` — planning mistakes reflection
- `memory/dev_logs/20260429d_Phase_B_Chunk_B1_YAML_Curation_Validator.md` — B.1
- `memory/dev_logs/20260429e_Phase_B_Chunk_B2_Graph_Chunk_Metadata_Path_Prefix.md` — B.2
- `memory/dev_logs/20260429f_Phase_B_Chunk_B3_Retriever_And_Reasoning_Plumbing.md` — B.3
- `memory/dev_logs/20260429g_Phase_B_Chunk_B35_Tier4_Mode_Metadata_Validator.md` — B.3.5
- `memory/dev_logs/20260429h_Phase_B_Chunk_B4_Final_Verification.md` — B.4
- `memory/dev_logs/20260429i_Phase_B_Chunk_B5_Documentation.md` — B.5 (this chunk)
