# Mode-Aware Retrieval: How to Use

**Audience:** A2MC users running ELM-FATES or ELM-only calibrations who want the RAG/GraphRAG retrieval to respect their simulation configuration (PARTEH mode, nutrient cycling, competition, etc.).

**Reading time:** ~5 minutes. For the comprehensive plan see `docs/20_Mode_Aware_RAG_Retrieval_Plan.md`.

**What ships in Phase A (v2.91):**
1. Active-mode prompt block — every Phase 3/4 prompt now declares the run's mode at the top, letting the AI self-correct on retrieved content.
2. `kb_source` filter — ELM-only runs (`A2MC_USE_FATES=false`) exclude FATES content from retrieval entirely.
3. Python config plumbing — four new env vars become accessible to the orchestrator and reasoning module.

**What's deferred to Phase B:** per-mode chunk-level filtering for within-FATES modes (PARTEH=1 vs 2, NOCOMP, CN-only). Phase A relies on the prompt block to nudge the AI; Phase B will hard-filter content from retrieval.

---

## Setup

Mode-awareness requires four environment variables, all already standard in A2MC site configs. No new setup needed if your `kougarok_config.sh` (or equivalent) is up to date.

```bash
# In your site config:
export A2MC_USE_FATES=true              # or false for ELM-only
export A2MC_FATES_PARTEH_MODE=2         # 1 = carbon-only, 2 = CNP
export A2MC_USE_FATES_NOCOMP=false      # true = PFTs in separate patches
export A2MC_ELM_OPTIONS="-bgc fates -nutrient cnp -nutrient_comp_pathway eca"
```

Defaults are conservative (FATES on, PARTEH=2, nutrient=cnp, ECA pathway) so legacy configs continue to work unchanged.

---

## What you'll see at orchestrator startup

The alignment hook logs the active mode:

```
[Mode] {'use_fates': True, 'parteh_mode': 2, 'nutrient': 'cnp', ...}
[Mode] ## Active Run Configuration
[Mode] - FATES: enabled (PARTEH=2, CNP allocation (nutrient cycling ON))
[Mode] - Nutrient cycling: CNP
[Mode] - Competition: ON (ECA pathway)
```

The same block appears at the top of every Phase 3 / Phase 4 AI prompt under the heading `## Active Run Configuration`. The AI uses this to correctly interpret retrieved content.

---

## Mode combinations and what changes

### Default (PARTEH=2 CNP)

```bash
export A2MC_USE_FATES=true
export A2MC_FATES_PARTEH_MODE=2
export A2MC_ELM_OPTIONS="-bgc fates -nutrient cnp -nutrient_comp_pathway eca"
```

No retrieval filtering applied. Prompt block declares "FATES: enabled (PARTEH=2, CNP allocation), Nutrient cycling: CNP, Competition: ON (ECA pathway)". Same content as pre-v2.91 retrieval, plus the explanatory mode block.

### ELM-only (no FATES)

```bash
export A2MC_USE_FATES=false
```

Retrieval applies `kb_source='elm'` filter — FATES content excluded from vector search results. Prompt block declares "FATES: DISABLED (ELM-only run; FATES parameters and mechanisms do NOT apply)". The AI agent will not recommend `fates_*` parameter tuning.

### PARTEH=1 carbon-only

```bash
export A2MC_USE_FATES=true
export A2MC_FATES_PARTEH_MODE=1
```

No `kb_source` filter (FATES is still on). Prompt block declares "FATES: enabled (PARTEH=1, carbon-only allocation) - CNP mechanisms (PID controller, nutrient uptake, stoichiometry) do NOT apply to this run". The AI sees this block and avoids recommending CNP-specific parameters even if retrieved content discusses them.

### NOCOMP (no inter-PFT competition)

```bash
export A2MC_USE_FATES=true
export A2MC_USE_FATES_NOCOMP=true
```

Prompt block declares "Competition: OFF (PFTs in separate patches; ECA/RD do NOT apply)". The AI avoids recommending competition-pathway parameter tuning.

### CN-only nutrient mode

```bash
export A2MC_USE_FATES=true
export A2MC_ELM_OPTIONS="-bgc fates -nutrient cn -nutrient_comp_pathway eca"
```

Prompt block declares "Nutrient cycling: CN ... P-cycle parameters (fates_cnp_*ptase, FATES_PUPTAKE_*) do NOT apply". The AI avoids recommending phosphorus-related parameter tuning.

---

## Verification

Run the verification harness after any setup change:

```bash
python scripts/verify_mode_aware.py
```

Healthy output (Phase A):

```
17/20 fixture tests pass (3 Phase B skipped, 0 fail, 0 error)
6/6 real-index smoke tests pass
```

Detailed report drops at `docs/a2mc_reference/mode_aware_verification.md`. Failures point to specific assertions that broke.

---

## Phase B (v2.92, 2026-04-29) — now active

Phase B shipped, replacing the "deferred" status of within-FATES chunk filtering. Active features:

- **20-dim ConfigMode** — schema covers Tier 1 (primary), Tier 2 (FATES feature flags), Tier 3 (compset modifiers). Defaults match ELM `namelist_defaults.xml`. See `mode_aware_workflow.md`.
- **Curated-YAML `applies_in:` blocks** — 17 mode-restricted parameters + 3 mechanisms tagged in canonical YAML.
- **Path-prefix wiki tagging** — 11 patterns covering 22+ wiki docs gate fire/, hydraulics/, logging/, CNP theory, carbon-only theory, inverse-tagged BTRAN/photosynthesis docs.
- **Tier 4 validator** — `tools/mode_metadata_validator.py` confirms YAML → chunk + graph propagation chain is intact.
- **End-to-end verification GREEN** on api-43-1: 50/50 fixtures, 6/6 smoke, 79/79 Tier 4 assertions.

For comprehensive details on Phase B: `docs/a2mc_reference/mode_aware_workflow.md`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Mode block missing from AI prompt | `tools.config` not importable from orchestrator | Source `a2mc_config.sh` and your site config before launching |
| ELM-only run still sees `fates_*` content | `A2MC_USE_FATES=false` not set or not exported | Confirm: `echo $A2MC_USE_FATES` returns "false" |
| `verify_mode_aware.py` reports `kb_source` MISSING/empty | Index built before v2.91 (pre-kb_source-fix) | Rebuild: `python scripts/build_rag_index.py --rebuild --vector-only --profile <name>` |
| Mode block shows wrong values | Env vars from a stale shell | Re-source site config |

---

## Implementation reference

| File | Role |
|---|---|
| `tools/config.py` | `ConfigMode` dataclass (20 dims), `ALL_AXIS_VALUES`, `to_chroma_where()`, `build_applies_in_flags()`, `parse_elm_options()`, `to_prompt_block()`, `kb_source_filter()` |
| `rag/loader.py` | `_WIKI_PATH_PREFIX_TAGS` table + `path_prefix_tags()` matcher; `chunk_documents()` + `load_parameter_descriptions()` write applies_in flags |
| `rag/graph_builder.py` | `_overlay_curated_relationships()` writes flags onto graph nodes; default-permissive sweep at end of `build_fates_graph()` |
| `rag/vector_store.py` | `add_documents()` passes through `applies_*`/`inactive` metadata; `query()` family accepts `mode_where` kwarg |
| `rag/hybrid_retriever.py` | 3 top-level methods accept `config_mode`; threads `mode_where` to inner queries |
| `reasoning/base.py` | `_get_active_config_mode()`; threads `config_mode` through Phase 3/4 RAG calls |
| `tools/yaml_wiki_validator.py` | Dim F validates `applies_in:` schema |
| `tools/mode_metadata_validator.py` | Tier 4 validator: end-to-end propagation chain |
| `orchestrator.py:_detect_config_mode()` | Startup hook: log active mode |
| `reasoning/methods.py:_build_active_mode_block()` | Inject mode block into Phase 3/4 prompts |
| `reasoning/base.py:_mode_kb_source_filter()` | Pull kb_source filter from ConfigMode for retrieval calls |
| `rag/vector_store.py:query()` | Accepts `kb_source` keyword; builds ChromaDB `where` clause |
| `rag/hybrid_retriever.py:get_targeted_context() / get_context()` | Pass `kb_source` to underlying vector_store calls |
| `rag/loader.py:chunk_documents()` | Propagates `kb_source` from doc to chunk; prefixes `chunk_id` to avoid FATES/ELM file-name collisions |
| `tests/test_mode_filters.py` | 20 fixtures (17 Phase A + 3 Phase B placeholders) |
| `scripts/verify_mode_aware.py` | Runs fixtures + real-index smoke; writes Markdown report |

For the design rationale see `docs/20_Mode_Aware_RAG_Retrieval_Plan.md`. For the audit that scoped this work see `memory/dev_logs/20260428e_Audit_Config_Aware_RAG_Retrieval.md`.
