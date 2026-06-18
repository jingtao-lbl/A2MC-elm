---
name: build-rag-from-scratch
description: Construct the entire RAG/GraphRAG knowledge layer from scratch when the index AND/OR its inputs don't exist yet — either reconstructing an existing model's full layer from source (api-31-0 reproducibility / disaster recovery) or bootstrapping a brand-new model (EcoSim, ReSOM, …) into A2MC. This is the orchestrator that sequences the four step-skills (generate-codebase-wiki → build → inject-knowledge/curated-YAML → validate-rag-chain) plus the glue none of them own (loader registration, per-model parsers, separate persist dirs, milestone registration). Use when the user says "build the RAG/GraphRAG from scratch", "set up RAG for a new model", "add EcoSim/ReSOM to A2MC", "reconstruct the whole knowledge layer", "bootstrap the knowledge base from nothing". For reindexing inputs that already exist, use rebuild-rag instead. Distilled from rag_build_roadmap.md (Recipe 2) + codebase_wiki_generation_roadmap.md (Recipe B3).
modes:
  requires_fates: false
  nutrient_pathway: any
  scope: [rag]
  summary: "Construct the RAG/GraphRAG layer for any model; model-agnostic."
---

# Build the RAG/GraphRAG Knowledge Layer From Scratch

The **constructive** counterpart to `rebuild-rag` (which reindexes inputs that already
exist). This skill is an **orchestrator** — it produces the whole knowledge layer when the
ChromaDB index, the NetworkX graph, *or their upstream inputs* (wiki, CDLs, parsers, curated
YAML, loader registration) are missing. Canonical guide: **`docs/a2mc_reference/rag_build_roadmap.md`**
(the self-contained reconstruction guide; **Recipe 2** is the new-model path) +
`codebase_wiki_generation_roadmap.md` Recipe B3.

> **Use Python 3.10** for everything (`/Library/Frameworks/Python.framework/Versions/3.10/bin/python3`,
> called `$PY` below). Homebrew 3.12 fails on PEP-668.

## Step 0 — which from-scratch is this?

| Case | What already exists | Path |
|---|---|---|
| **Reconstruct an existing model's layer** (reproducibility, disaster recovery, fresh clone) | source + commit-pinned wiki + CDLs + curated YAML exist; only `chroma_db/` + graph JSON are gone | **Path R** |
| **Bootstrap a NEW model** (EcoSim, ReSOM, …) | only the model's source code; no wiki, CDLs, parser, YAML, or loader registration | **Path N** (Recipe 2, 12 steps) |

Path R is mostly mechanical (the inputs exist; rebuild the indexes from them). Path N is a
real project — the per-model parsers and curated YAML are days of work, not minutes.

## Path R — reconstruct an existing model's index from its inputs

The api-31-0 reproducibility contract: anyone with a fresh clone must be able to regenerate
the exact knowledge layer.

1. **Confirm the inputs are present:** the commit-pinned wiki dir(s), both CDLs, and
   `rag/data/curated_relationships.yaml`. If the wiki is missing or at the wrong commit →
   run **`generate-codebase-wiki`** first (Workflow A) before continuing.
2. **Point the loader at the right wiki tree.** The loader pattern-probe stops at the first
   match (`rag/loader.py:366-371`) — symlink the bare `…-codebase-wiki` name at the
   commit-pinned dir, or the build indexes the wrong tree. (Same footgun + fix as
   `rebuild-rag` Recipe 1.)
3. **Stage CDLs matching the wiki commit.** They're hand-managed, not auto-regenerated:
   `ncdump -h <model>_params_default.nc > docs/<model>-knowledge-base/<model>_params_info.cdl`.
4. **Build both layers:**
   ```bash
   $PY scripts/build_rag_index.py --rebuild --test
   ```
5. **Verify BOTH layers** — the vector index *and* the graph (Step V below). A build can
   produce a full vector index with an empty/broken graph.
6. **Validate the chain** — run **`validate-rag-chain`**.

## Path N — bootstrap a new model (Recipe 2, Path A: one graph per model)

Forward-dev / adapter-kit. The 12 steps from `rag_build_roadmap.md` Recipe 2:

1. **KB dir:** `mkdir -p docs/<model>-knowledge-base/<model>-codebase-wiki-<commit>` (stub
   dirs for `ecosim`/`resom` already exist).
2. **Wiki:** run **`generate-codebase-wiki`** (Workflow A greenfield) → commit-pinned dir.
3. **Param CDL + output CDL:** `ncdump -h …` for each. If the model's parameter file is an
   exotic format (XML/namelist/JSON), you'll write a parser instead.
4. **Per-model parameter parser:** copy `rag/parameter_parser.py` → `rag/<model>_parameter_parser.py`;
   replace the `fates_\w+` regex (`:270`), the `CATEGORIES` table (`:27-58`), the
   PFT-detection (`'fates_pft' in dimensions` → the model's group axis), and the class name.
5. **Per-model output parser:** copy `rag/output_parser.py` → `rag/<model>_output_parser.py`;
   replace the `FATES_` prefix discriminator (`:170-171`), `KEY_ELM_VARIABLES`,
   `OUTPUT_CATEGORIES`, `DIMENSION_LEVEL_MAP`.
6. **Curated YAML:** copy `rag/data/curated_relationships.yaml` → `rag/data/<model>_relationships.yaml`;
   **keep the schema (model-agnostic), replace all content** — 5–10 mechanisms, 60–100
   parameter entries for a first usable build. Parameter/output names **must match the new
   CDLs** (this is the `inject-knowledge` authoring discipline at scale — same dropped-edge
   footgun if a name doesn't resolve).
7. **Graph-builder adapter:** copy `rag/graph_builder.py` → `rag/<model>_graph_builder.py`
   (quick) or refactor it to take parser objects via dependency injection (cleaner for
   long-term multi-model).
8. **Register the KB** in `rag/loader.py` `DEFAULT_KNOWLEDGE_BASES` (or make it a function
   keyed on an `A2MC_TARGET_MODEL` env var for true multi-model).
9. **Build into a SEPARATE persist dir** so you don't clobber FATES:
   ```bash
   $PY scripts/build_rag_index.py --rebuild --test \
       --kb-path docs/<model>-knowledge-base \
       --persist-dir rag/chroma_db_<model> \
       --graph-path rag/<model>_knowledge_graph.json \
       --param-cdl docs/<model>-knowledge-base/<model>_params_info.cdl \
       --output-cdl docs/<model>-knowledge-base/<model>_output_info.cdl
   ```
10. **Teach `HybridRetriever`** to load the new model (a `model=` constructor arg, or pass
    the persist/graph paths explicitly); rewrite the entity-extraction regex
    (`hybrid_retriever.py:316-322`) and the keyword→mechanism map (`:332-341`).
11. **Verify both layers** (Step V) + **`validate-rag-chain`**.
12. **Register a milestone** in the version-association layer if applicable
    (`docs/18_ELM_FATES_Version_Association_Plan.md`).

**Path B (single multi-model index)** exists (metadata-tagged, node-ID namespacing) but is
not recommended for a first new model — see the roadmap. Use Path A.

**What survives for free:** build-script structure, loader chunking, vector store wrapper,
graph schema (Parameter/Output/Mechanism/Module/Category/Dimension), curated-YAML schema,
ReasoningModule integration. **What must be rewritten:** every `fates_\w+`/`FATES_*` regex,
the category/dimension/variable tables, the curated-YAML *content*, the keyword→mechanism
map, `DEFAULT_PFT_NAMES`, and the `FATES`-prefixed class names.

## Step V — verification gate (prove the GRAPH built, not just the vector index)

A full vector index with an empty or malformed graph is a silent half-build. Check **both**:

```bash
$PY -c "
from rag import HybridRetriever
r = HybridRetriever(auto_build=False)          # or model='<model>' / explicit paths for Path N
s = r.get_stats()
print('vector docs:', s['vector_store']['total_documents'])
print('graph nodes/edges:', s['knowledge_graph']['total_nodes'], s['knowledge_graph']['total_edges'])
print('edge types:', s['knowledge_graph']['edges_by_type'])
# GraphRAG traversal must actually return typed relationships:
res = r.find_parameters_for_output('<a real output var, e.g. FATES_LEAFC>')
print('params-for-output:', len(res))
"
```

Pass criteria: vector docs > 0 **and** graph nodes/edges > 0 **and** `edges_by_type`
includes the typed relations (`controls`/`affects`/`related_to`) **and**
`find_parameters_for_output(...)` returns a non-empty list. For reference, the api-31-0 FATES
build is ~2,581 docs / ~1,295 nodes / ~2,197 edges. If vector docs > 0 but nodes/edges are
0, the curated YAML or CDL parse failed — the graph half didn't build. (Verified gate: this
exact `get_stats` + `find_parameters_for_output` check distinguishes a real GraphRAG build
from a vector-only one.)

## Notes

- **Orchestrator, not a replacement:** this skill calls **`generate-codebase-wiki`** (wiki),
  the **`rebuild-rag`** build mechanics (the `build_rag_index.py` invocation + footguns),
  **`inject-knowledge`** (the curated-YAML authoring discipline), and **`validate-rag-chain`**
  (the gate) as sub-steps. It owns the glue: loader registration, per-model parsers, separate
  persist dirs, milestone registration.
- **Cost:** the index build itself is ~2 min / $0 (local embeddings). The real time sink is
  upstream — wiki generation (~30–90 min, token-heavy) and, for Path N, the per-model parsers
  + curated YAML (days). Budget accordingly; this is not a one-command skill.
- **Branch fit:** Path N (new model) is forward-dev — natural home `main`/adapter-kit. **Path
  R is the one relevant here** — reconstructing the api-31-0 FATES knowledge layer from source
  is this branch's reproducibility contract; keep it regenerable.

## Changelog

- 2026-06-17: Initial version — orchestrator over the four KB-build skills (rag_build_roadmap.md Recipe 2 + codebase_wiki_generation_roadmap.md Recipe B3); Step V graph-built gate baked in.
