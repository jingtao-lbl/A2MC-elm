# Mode-Aware Retrieval: How to Use

**Audience:** A2MC users running ELM-FATES or ELM-only calibrations who want the RAG/GraphRAG retrieval to respect their simulation configuration (PARTEH mode, nutrient cycling, competition, etc.).

**Reading time:** ~5 minutes. For the comprehensive plan see `mode_aware_workflow.md`.

**What it does** (matured over v2.91 → v2.96):

1. **20-dimension `ConfigMode`** read from your env vars at orchestrator startup — covers FATES on/off, PARTEH=1 vs 2, ECA vs RD nutrient competition, SPITFIRE, plant hydraulics, logging, no-comp, plus seven secondary compset modifiers.
2. **Active-mode prompt block** — every Phase 3/4 AI prompt declares the run's mode at the top, letting the AI self-correct on any retrieved content that's mode-irrelevant.
3. **Chunk-level filtering** — ChromaDB `where` clauses gate chunks based on `ConfigMode` axes. PARTEH=1 retrieval does NOT surface CNP chunks; ELM-only retrieval excludes FATES content (the `kb_source` axis); NOCOMP excludes ECA/RD competition content; etc.
4. **Curated YAML `applies_in:` blocks** propagate to chunks + graph nodes via the build pipeline (see `mode_aware_workflow.md`).
5. **Path-prefix wiki tagging** — 11 patterns covering 22+ wiki docs gate fire/, hydraulics/, logging/, CNP theory, carbon-only theory, etc.
6. **Five-validator gate** (Tier 4 + snapshot + profile-completeness + cross-milestone + tier coverage) all Green against api-43-1.

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

Defaults match ELM `namelist_defaults.xml` (vanilla SP run, no FATES; per the April 30 design correction). To enable FATES + CNP + ECA (the Kougarok-style configuration), set the env vars above explicitly in your site config.

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
# or equivalently:  export A2MC_ELM_OPTIONS="-bgc bgc"
```

Retrieval applies `kb_source='elm'` filter — FATES content excluded from vector search results. Prompt block declares "FATES: DISABLED (ELM-only run; FATES parameters and mechanisms do NOT apply)". The AI agent will not recommend `fates_*` parameter tuning.

**v2.96+:** ELM-only runs are first-class. `scripts/extract_elm_outputs.py` indexes 1640 ELM core variables (extracted from `hist_addfld1d/2d` calls in `components/elm/src/**/*.F90`) into the api-43-1 RAG, so non-FATES configurations get full output coverage.

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

Prompt block declares "Nutrient cycling: CN ... P-cycle parameters (`fates_cnp_eca_*_ptase`, `FATES_PUPTAKE_*`) do NOT apply". The AI avoids recommending phosphorus-related parameter tuning.

---

## Verification

Run the harness after any setup change:

```bash
python scripts/verify_mode_aware.py
```

Healthy output (current main):

```
61/61 fixture tests pass
6/6 real-index smoke tests pass
Tier 4 mode-metadata validator: Green
Validator #1 (snapshot, api-43-1): Green (5/5 fixtures pass)
Validator #2 (profile completeness, api-43-1): Green
Validator #3 (cross-milestone consistency): Green (0 drift, 0 coverage warnings)
```

Detailed report drops at `docs/a2mc_reference/mode_aware_verification.md`. Failures point to specific assertions that broke. Same harness is used as the **post-rebuild gate** by the orchestrator's auto-rebuild path (v2.98) — a Red verdict triggers automatic rollback to the `<profile>.previous/` snapshot.

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

The user-facing entry points:

| Layer | File | What it gives you |
|---|---|---|
| Config | `tools/config.py` | `ConfigMode` dataclass (20 dims) read from env vars; `to_prompt_block()` for the AI block; `to_chroma_where()` for the retrieval filter |
| Retrieval | `rag/hybrid_retriever.py` | `get_targeted_context(config_mode=...)` is the primary call; threads mode through to ChromaDB `where` clause |
| Reasoning | `reasoning/base.py`, `reasoning/methods.py` | Auto-injects the mode block into every Phase 3/4 prompt; pulls `kb_source` filter from active `ConfigMode` |
| Validation | `tools/yaml_wiki_validator.py`, `tools/mode_metadata_validator.py`, `tools/snapshot_validator.py`, `tools/profile_completeness_validator.py`, `tools/cross_milestone_validator.py` | Five validators ensure YAML → chunk + graph propagation; harness via `scripts/verify_mode_aware.py` |
| Tests | `tests/test_mode_filters.py` | 61 fixtures across all dimensions |

For the full code map (every helper, every dispatch site) see `mode_aware_workflow.md` "Implementation reference" section.

For the original design rationale see `docs/20_Mode_Aware_RAG_Retrieval_Plan.md` (Phase A) and `docs/21_Mode_Aware_RAG_Phase_B_Implementation.md` (Phase B). For the audit that scoped this work see `memory/dev_logs/20260428e_Audit_Config_Aware_RAG_Retrieval.md`.

---

## Going deeper

- **`mode_aware_workflow.md`** — comprehensive reference. Full code map, the per-mode `applies_in:` schema, validator details, mode-block design rationale.
- **`version_association_howto.md`** — the parallel 5-min guide for version association (which RAG profile loads). Mode-awareness filters chunks WITHIN a profile; version association picks the profile.
- **`docs/22_Auto_Rebuild_Tier_Policy_Implementation.md`** — the v2.98 auto-rebuild design. Same `verify_mode_aware.py` harness gates rebuilds.
- **`rag_validation_workflow.md`** — adapter-kit Step 4: the four-tier validation triangle + three new validators (snapshot, profile-completeness, cross-milestone).
