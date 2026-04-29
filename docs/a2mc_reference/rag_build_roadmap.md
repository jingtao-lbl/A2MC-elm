# A2MC RAG/GraphRAG Build Roadmap

**Purpose:** Reconstruction guide for the A2MC RAG/GraphRAG knowledge system. Read this when you need to (a) rebuild the index because the underlying wiki documentation changed (e.g. moved to a new commit-pinned tree like `fates-codebase-wiki-e85d997/`), (b) add a new model to A2MC (EcoSim, ReSOM, or any future ESM land model), or (c) refresh memory on how the system was built.

**Audience:** Future Jing + Claude. Self-contained — you should NOT need to read other docs to follow this roadmap.

**Companion docs:**
- `docs/a2mc_reference/rag_reference.md` — short overview of what the running system does (read first if you only want a 2-minute orientation)
- `docs/01_RAG_Implementation_Guide.md` — original Phase 1 implementation guide (historical)
- `docs/02_GraphRAG_Implementation_Plan.md` — original Phase 2 design (historical)
- `docs/11_RAG_Expansion_Full_Parameter_Output_Coverage.md` — Feb 2026 expansion to full CDL coverage (historical)
- `memory/dev_logs/20260111b_RAG_GraphRAG_Implementation_Complete.md`
- `memory/dev_logs/20260204b_RAG_ELM_Knowledge_Base_Extension.md`
- `memory/dev_logs/20260211b_RAG_Expansion_Full_Parameter_Output_Coverage.md`

---

## TL;DR — Just the commands

```bash
# Standard rebuild from current tree (FATES + ELM, both KBs):
cd /Users/jingtao/Desktop/Work/NGEE-Arctic/Kougarok/Program/A2MC
/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 \
    scripts/build_rag_index.py --rebuild --test

# Quick smoke test of an existing index (no rebuild):
/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -c "
from rag import HybridRetriever
r = HybridRetriever(auto_build=False)
print(r.get_stats())
print(r.get_targeted_context(
    param_names=['fates_cnp_pid_kp'],
    output_names=['FATES_LEAFC'],
    mechanisms=['PID_Controller'],
    pft=10)[:1500])
"
```

The default build reads from `docs/fates-knowledge-base/` and `docs/elm-knowledge-base/`, parses CDLs from `docs/fates-knowledge-base/fates_params_info.cdl` and `elm_fates_output_info.cdl`, overlays `rag/data/curated_relationships.yaml`, and writes to `rag/chroma_db/` and `rag/fates_knowledge_graph.json`. **It does NOT pick up the commit-pinned wikis** (`fates-codebase-wiki-e85d997/`, `elm-codebase-wiki-60d9aad/`) without intervention — see [Recipe 1](#recipe-1-bumping-the-wiki-to-a-new-commit-pinned-tree).

---

## 1. Architecture

Three storage layers, one retriever surface:

```
┌─────────────────────────────────────────────────────────────────────┐
│  VECTOR STORE (ChromaDB)                  KNOWLEDGE GRAPH (NetworkX)│
│  ─────────────────────────                ─────────────────────────│
│  Single collection: "fates_knowledge"    Single DiGraph instance    │
│  Persisted at: rag/chroma_db/            Persisted at:              │
│  Embedding model: all-MiniLM-L6-v2       rag/fates_knowledge_graph  │
│                                          .json (node-link format)   │
│  Chunks (~2,707 in current build):                                  │
│  - Wiki Markdown chunks (~2,147)         Nodes (~1,299):            │
│  - CDL parameter definitions (286)       - Parameter (897)          │
│  - CDL output definitions (274)          - Output (291)             │
│                                          - Dimension (58)           │
│                                          - Category (39)            │
│                                          - Mechanism (7)            │
│                                          - Module (4)               │
│                                          - PFT (3)                  │
│                                          Edges (~2,200): controls,  │
│                                          affects, related_to,       │
│                                          contains, belongs_to,      │
│                                          has_dimension, etc.        │
└─────────────────────┬─────────────────────────┬─────────────────────┘
                      │                         │
                      └────────────┬────────────┘
                                   ▼
                  ┌─────────────────────────────────┐
                  │   HybridRetriever               │
                  │   (rag/hybrid_retriever.py)     │
                  │                                 │
                  │   - get_targeted_context()      │  ← primary API
                  │   - get_calibration_context()   │
                  │   - get_parameter_info()        │
                  │   - get_mechanism_info()        │
                  │   - find_parameters_for_output()│
                  └─────────────────┬───────────────┘
                                    │
                                    ▼
                  ┌─────────────────────────────────┐
                  │   ReasoningModule               │
                  │   (reasoning/base.py)           │
                  │                                 │
                  │   Auto-injects RAG context      │
                  │   into every Claude API call    │
                  └─────────────────────────────────┘
```

The graph is built in **two layers**:

- **Layer 1 (auto-extracted)** parses CDL parameter and output files and produces nodes for every parameter, output, dimension, and category. This gives 100% structural coverage of FATES parameters and outputs.
- **Layer 2 (curated overlay)** reads `rag/data/curated_relationships.yaml` and adds the mechanistic edges that humans encode by hand: `parameter → mechanism → output` causal chains, related-to links, and calibration notes. The overlay also adds 7 mechanism nodes (PID_Controller, ECA_Competition, etc.) that aren't in any CDL.

Layer 2 enriches Layer 1 nodes with richer descriptions and notes. It does NOT replace them.

---

## 2. Inputs you need before building

| Input | Path | Source | Required? |
|---|---|---|---|
| Wiki Markdown root | `docs/fates-knowledge-base/` and `docs/elm-knowledge-base/` | Hand-written or auto-generated wiki | **Yes** |
| Parameter CDL | `docs/fates-knowledge-base/fates_params_info.cdl` | `ncdump -h` of `fates_params_default.nc` from a FATES build, or curated equivalent | Yes for full param coverage |
| Output variable CDL | `docs/fates-knowledge-base/elm_fates_output_info.cdl` | `ncdump -h` of an ELM-FATES output file (`*.elm.h0.*.nc`) | Yes for full output coverage |
| Curated relationships YAML | `rag/data/curated_relationships.yaml` | Hand-curated, ~1387 lines | Yes for mechanistic edges |
| Python 3.10 | `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3` | `python.org` installer | **Yes** (NOT Homebrew Python) |
| Required packages | `chromadb`, `sentence-transformers`, `networkx`, `pyyaml`, `numpy` | Pre-installed in the Python 3.10 env | **Yes** |
| Optional package | `netCDF4` | For parsing `.nc` parameter files directly (instead of `.cdl`) | Optional |

**Why Python 3.10 and not Homebrew Python 3.12?** macOS Homebrew Python 3.12 is externally-managed and blocks pip installs. Python 3.10 from `python.org` has all RAG dependencies pre-installed. See `memory/dev_logs/20260202b_RAG_Python_Environment_Fix.md` for the history.

---

## 3. File inventory: what does what

### Source code (`rag/`)

| File | Lines | Role | Hardcoded "FATES"-isms? |
|---|---|---|---|
| `__init__.py` | ~62 | Package exports — `HybridRetriever`, `FATESRetriever`, etc. | Yes (class names) |
| `loader.py` | ~620 | Walks wiki tree, cleans Markdown/RST, chunks with structure-aware splitter, also loads CDL "definition chunks" via `load_parameter_descriptions()` | Yes — wiki dir patterns, `kb_name` inference |
| `vector_store.py` | ~200 | ChromaDB wrapper. Single collection `"fates_knowledge"`. Embedding model `all-MiniLM-L6-v2`. Has `query()`, `query_parameters()`, `query_outputs()` filtered methods | Yes — collection name, class name |
| `retriever.py` | ~360 | Vector-only retriever (`FATESRetriever`). Wraps `vector_store` with index-build logic, `add_documents()`, smoke tests | Yes — class name |
| `knowledge_graph.py` | ~620 | NetworkX `DiGraph` schema. Node types (Parameter/Output/Mechanism/PFT/Module/Category/Dimension), edge types (controls/affects/contains/belongs_to/has_dimension/...), graph queries, save/load JSON | Yes — class name, PFT-centric API |
| `graph_builder.py` | ~570 | Two-layer graph construction: `_add_auto_extracted_parameters()`, `_add_auto_extracted_outputs()`, `_overlay_curated_relationships()`. Environment-variable resolution for PFT list and CDL paths | Yes — `build_fates_graph()`, default paths |
| `parameter_parser.py` | ~480 | Parses FATES CDL/JSON/NC parameter files. `FATESParameterParser` class. CATEGORIES table (alloc, cnp, allom, phen, ...) | **Heavily** — `fates_\w+` regex prefix |
| `output_parser.py` | ~430 | Parses ELM-FATES output CDL. `FATESOutputParser` class. KEY_ELM_VARIABLES allowlist, OUTPUT_CATEGORIES table, DIMENSION_LEVEL_MAP | **Heavily** — `FATES_` prefix discriminator |
| `hybrid_retriever.py` | ~750 | Combined vector+graph retrieval. **`get_targeted_context()` is the primary API used by ReasoningModule**. Also `get_calibration_context()`, `get_parameter_info()`, etc. | Yes — class name, mechanism keyword map |
| `data/curated_relationships.yaml` | ~1387 | Layer 2 overlay: 7 mechanisms + ~65 parameters + ~100 outputs + 6 category groups, all with `controls`/`affects`/`related_to`/`controlled_by`/`key_parameters` edges and calibration notes | **Entirely** FATES-specific content (schema is model-agnostic) |

### Build entry point

| File | Role |
|---|---|
| `scripts/build_rag_index.py` | The CLI driver. Two-phase build: vector index then knowledge graph. CLI flags: `--rebuild`, `--test`, `--graph-only`, `--vector-only`, `--no-definitions`, `--kb-path`, `--persist-dir`, `--graph-path`, `--param-cdl`, `--output-cdl` |

### Persistent state (output of build)

| Path | Contents | Format |
|---|---|---|
| `rag/chroma_db/` | Vector index + embeddings cache | ChromaDB sqlite + segment files |
| `rag/fates_knowledge_graph.json` | Knowledge graph state | JSON via `nx.node_link_data(edges="links")` |

### Reference data (input)

| Path | Contents | Updated when... |
|---|---|---|
| `docs/fates-knowledge-base/fates_params_info.cdl` | All FATES parameter definitions (~290) | FATES adds/removes parameters or you bump to a new FATES commit |
| `docs/fates-knowledge-base/elm_fates_output_info.cdl` | All ELM-FATES output variables (~679 = 250 FATES + 429 ELM) | ELM/FATES adds/removes history variables |
| `docs/fates-knowledge-base/fates-codebase-wiki/**/*.md` | FATES codebase wiki | Wiki regenerated against a new commit (already done at `e85d997`) |
| `docs/elm-knowledge-base/elm-codebase-wiki-60d9aad/**/*.md` | ELM codebase wiki (commit-pinned) | ELM source updated, wiki regenerated (already done at `60d9aad`) |
| `rag/data/curated_relationships.yaml` | Mechanistic relationships | When a new mechanism is discovered, parameter is added, or relationship needs updating |

---

## 4. End-to-end build pipeline

What happens when you run `scripts/build_rag_index.py --rebuild`:

```
SCRIPT START
│
├─ Parse CLI args, auto-detect CDL paths from docs/fates-knowledge-base/
│
├─ PHASE 1: VECTOR INDEX  (only if not --graph-only)
│  │
│  ├─ create_retriever(rebuild=True)
│  │  └─ wipe rag/chroma_db/, instantiate fresh PersistentClient
│  │
│  ├─ load_multiple_knowledge_bases([
│  │     "docs/fates-knowledge-base",
│  │     "docs/elm-knowledge-base"
│  │  ])
│  │  └─ for each KB, infer kb_name from directory name suffix,
│  │     probe for "{kb}-codebase-wiki" / "codebase-wiki" / "wiki"
│  │     subdir (FIRST MATCH WINS), then rglob *.md inside it
│  │  └─ also load any "official-docs/docs/source/**/*.rst"
│  │  → returns list of {content, source, type, title, format, kb_source}
│  │
│  ├─ chunk_documents(docs, chunk_size=1000, overlap=200)
│  │  └─ recursive_split with separator preference:
│  │     ["\n## ", "\n### ", "\n#### ", "\n\n", "\n", ". ", " "]
│  │  └─ clean_text() FIRST: strips images, SVGs, HTML comments,
│  │     and triple-backtick code fences (CAVEAT — see Gotchas)
│  │  → returns chunks with chunk_id = "{rel_path}::chunk_{i}"
│  │
│  ├─ vector_store.add_documents(chunks)
│  │  └─ batch insert into Chroma collection "fates_knowledge"
│  │  └─ DEDUPES BY chunk_id (skips existing — see Gotchas)
│  │
│  └─ Index CDL parameter/output definitions (if --no-definitions not set):
│     load_parameter_descriptions(param_cdl, output_cdl)
│     → 286 parameter chunks + 274 output chunks with metadata tags
│     → vector_store.add_documents(definition_chunks)
│
├─ PHASE 2: KNOWLEDGE GRAPH  (only if not --vector-only)
│  │
│  ├─ build_fates_graph(kb_path, include_pft_specific=True,
│  │                    param_cdl_path=..., output_cdl_path=...)
│  │  │
│  │  ├─ Resolve PFT list: arg → A2MC_PFTS env var → [7,9,10] default
│  │  │
│  │  ├─ LAYER 1: Auto-extract from CDLs
│  │  │  ├─ _add_auto_extracted_parameters()
│  │  │  │   FATESParameterParser.parse(param_cdl)
│  │  │  │   For each param: add Parameter node + Category node +
│  │  │  │     Dimension nodes + has_dimension/contains edges
│  │  │  │   For PFT-dimensioned params: clone as :pft{N} replicas +
│  │  │  │     belongs_to edges
│  │  │  │
│  │  │  └─ _add_auto_extracted_outputs()
│  │  │      FATESOutputParser.parse(output_cdl)
│  │  │      Add all FATES_* outputs + 24 KEY_ELM_VARIABLES
│  │  │      Add Dimension nodes + has_dimension edges
│  │  │
│  │  ├─ LAYER 2: Overlay curated YAML
│  │  │  load_curated_relationships(rag/data/curated_relationships.yaml)
│  │  │  ├─ Add Mechanism nodes (7) + Module nodes
│  │  │  ├─ Enrich existing Parameter/Output nodes with notes/category
│  │  │  ├─ Add controls/affects/related_to edges
│  │  │  │   (only if both endpoints exist — defensive check)
│  │  │  ├─ Clone edges onto :pft{N} parameter replicas
│  │  │  └─ Add curated-only parameters/outputs (5+17) as fallback
│  │  │
│  │  └─ Add competes_with edges between all PFT pairs
│  │
│  └─ save_graph(kg, "rag/fates_knowledge_graph.json")
│
├─ Run --test queries if requested (vector + graph + targeted context)
│
└─ Print stats and usage instructions
```

**Key fact:** Vector and graph builds are independent. You can rebuild just one with `--vector-only` or `--graph-only`. Both share the same CDL inputs.

---

## 5. Verification

After a build, run these to confirm:

```bash
PY=/Library/Frameworks/Python.framework/Versions/3.10/bin/python3

# 1. Stats
$PY -c "
from rag import HybridRetriever
r = HybridRetriever(auto_build=False)
import json
print(json.dumps(r.get_stats(), indent=2))
"
# Expected (current build): vector ~2,707 docs, graph ~1,299 nodes / ~2,200 edges

# 2. Vector smoke test
$PY scripts/build_rag_index.py --test
# Runs the canned test queries: PID Controller / Phenology / Nutrient Competition,
# parameter+output filtered queries, and a targeted-context dump

# 3. Targeted retrieval (the API ReasoningModule uses)
$PY -c "
from rag import HybridRetriever
r = HybridRetriever(auto_build=False)
ctx = r.get_targeted_context(
    param_names=['fates_cnp_pid_kp', 'fates_alloc_storage_cushion'],
    output_names=['FATES_LEAFC', 'FATES_FROOTC'],
    mechanisms=['PID_Controller'],
    pft=10,
    include_docs=True)
print(ctx[:2000])
"
# Should print parameter definitions, output definitions, mechanism description,
# PFT 10 parameter list, and 3 documentation snippets — all in ~5–12K chars
```

If the build succeeded but the vector store is empty, the most likely cause is the wiki path-pattern issue documented in Recipe 1 below.

---

## Recipe 1: Bumping the wiki to a new commit-pinned tree

> **SUPERSEDED 2026-04-28 by the milestone tier (v2.90).** When the milestone tier landed (Phases 1–4 of `docs/18_ELM_FATES_Version_Association_Plan.md`), symlinks `docs/{fates,elm}-knowledge-base/*-codebase-wiki` were removed and loaders now read the explicit `wiki_subdir` from `rag/milestones.json` per profile. The symlink-based wiki bump described below is obsolete. **For new wiki commits, use `scripts/rag_bump.py --target-milestone <name>` instead** — see `docs/a2mc_reference/version_association_workflow.md` Workflow 4 ("Bump to a new milestone"). The text below is preserved for historical reference (Apr–early-Apr 2026 era).

**The situation:** We just regenerated FATES wiki at `docs/fates-knowledge-base/fates-codebase-wiki-e85d997/` and ELM wiki at `docs/elm-knowledge-base/elm-codebase-wiki-60d9aad/`. The original `fates-codebase-wiki/` and `elm-codebase-wiki/` are still in place. We want the RAG to use the new commit-pinned content.

**Why naive `--rebuild` does not "just work":** The loader walks the KB root with a fixed list of subdirectory name probes (`loader.py:366-371`):

```python
patterns = [
    f"{kb_name}-codebase-wiki",
    f"{kb_name}_codebase_wiki",
    "codebase-wiki",
    "wiki",
]
# First match wins; loop breaks
```

So when given `docs/fates-knowledge-base/`, it finds `fates-codebase-wiki/` (the original) and stops. The new `fates-codebase-wiki-e85d997/` is **never seen**, even though it sits as a sibling.

You have **four options**, in order of cleanness:

### Option A — Symlink (least invasive, RECOMMENDED)

```bash
cd docs/fates-knowledge-base
mv fates-codebase-wiki fates-codebase-wiki-original   # archive old
ln -s fates-codebase-wiki-e85d997 fates-codebase-wiki

cd ../elm-knowledge-base
mv elm-codebase-wiki elm-codebase-wiki-original
ln -s elm-codebase-wiki-60d9aad elm-codebase-wiki
```

Then run a normal `--rebuild`. The loader sees `fates-codebase-wiki/` (which now points at the e85d997 tree) and indexes the new content. To bump again later, just update the symlink target.

**Pros:** No code changes. Reversible. The old wiki is preserved with a clear name.

**Cons:** Symlinks don't survive `git add` cleanly on every platform. Git tracks the symlink, not the target. Since the target is in the same repo, this is fine, but `git mv` is preferable to `mv` for the rename step.

### Option B — Update the loader to glob

Edit `rag/loader.py:366-371` to accept a glob pattern:

```python
patterns = [
    f"{kb_name}-codebase-wiki",
    f"{kb_name}-codebase-wiki-*",   # NEW: matches commit-pinned variants
    f"{kb_name}_codebase_wiki",
    "codebase-wiki",
    "codebase-wiki-*",              # NEW
    "wiki",
]
```

If the glob has multiple matches, you need to decide whether to take the newest (by mtime) or all of them. Taking the newest is the cleanest semantic for a commit-bump workflow.

**Pros:** Permanent fix. Old and new wikis can coexist; the loader picks the newest commit automatically.

**Cons:** Code change. Requires understanding (and not breaking) the existing pattern logic. If multiple commit-pinned trees coexist, you may double-index unless you take the newest.

### Option C — Add a `--wiki-subdir` CLI flag

Add an explicit override path so the user can pass `--wiki-subdir fates-codebase-wiki-e85d997` to `build_rag_index.py`. Plumb it through `loader.load_knowledge_base()`. More code, but most explicit.

### Option D — Move CDLs and rebuild from scratch

If you also have new CDL files matching the new commit (regenerated from `ncdump -h fates_params_default.nc` against the new FATES build), drop them in place of `fates_params_info.cdl` / `elm_fates_output_info.cdl` and use either Option A or Option B. CDLs are referenced by the build script via fixed paths (`build_rag_index.py:40-41`); you can also override with `--param-cdl` and `--output-cdl`.

### Critical: Always use `--rebuild` for a wiki bump

`vector_store.add_documents()` (`vector_store.py:110-127`) **dedupes by chunk_id** and SKIPS existing entries. Chunk IDs encode the source path: `{rel_path}::chunk_{i}`. If you change the wiki content under the same path, old chunks are NOT removed; new chunks with new offsets are simply added on top. The vector store will be polluted with stale content.

The graph JSON is similarly only regenerated when `--rebuild` is set or the file is missing.

```bash
# Always for a wiki bump:
$PY scripts/build_rag_index.py --rebuild --test
```

This wipes `rag/chroma_db/` (`retriever.py:355-359`), wipes the graph JSON, and rebuilds both from scratch.

### Caches that get invalidated

- ✅ `rag/chroma_db/` — wiped and regenerated
- ✅ `rag/fates_knowledge_graph.json` — wiped and regenerated
- ❌ Sentence-transformers model weights at `~/.cache/huggingface/` — kept (don't need to clear)

### Verification for a wiki bump

```bash
$PY -c "
from rag import HybridRetriever
r = HybridRetriever(auto_build=False)
# Search for content that ONLY exists in the new wiki
results = r.vector_retriever.vector_store.query(
    'phenology GDD threshold default values', n_results=3)
for hit in results:
    print(hit['source'], '|', hit['relevance'])
"
# Should return chunks from .../fates-codebase-wiki/plant-physiology/phenology.md
# (which is now symlinked to the e85d997 version with the corrected -68/638/-0.01 defaults).
# Open one of the matched .md files and confirm it's the new content.
```

---

## Recipe 2: Adding a new model to A2MC (e.g., EcoSim, ReSOM)

**The situation:** You want to use A2MC's calibration framework with a different land/ecosystem model. The framework code (orchestrator, reasoning, phases) is mostly model-agnostic, but the RAG/GraphRAG layer is heavily FATES-shaped.

**Two architectural paths:**

### Path A — Coexisting RAG (one knowledge graph per model)

Build a separate RAG/GraphRAG for the new model. A2MC instantiates the right one based on which model the run targets. This is the cleanest approach if you keep both A2MC-FATES and A2MC-EcoSim runnable from the same checkout.

Steps:

1. **Create a new knowledge base directory:**
   ```bash
   mkdir -p docs/ecosim-knowledge-base/ecosim-codebase-wiki
   mkdir -p docs/ecosim-knowledge-base/ecosim-official-docs   # if any
   ```
   Place the wiki Markdown there. (Note: stub directories `docs/ecosim-knowledge-base/` and `docs/resom-knowledge-base/` already exist in the repo.)

2. **Generate Markdown wiki for the new model.** If the model has an auto-generated wiki (like the original FATES one was via DeepWiki), use that. Otherwise hand-write or use the same parallel-subagent rewrite approach we used for ELM (see `memory/dev_logs/20260410e_ELM_Wiki_vs_60d9aad_Rewrite.md` for the recipe). Pin to a model commit hash for traceability — name the directory `<model>-codebase-wiki-<commit>/`.

3. **Generate the parameter CDL.** Run `ncdump -h <model>_params_default.nc > docs/<model>-knowledge-base/<model>_params_info.cdl`. If the model uses a different parameter file format (XML, namelist, JSON), you will need to write a new parser.

4. **Generate the output variable CDL.** Run `ncdump -h <one-output-file>.nc > docs/<model>-knowledge-base/<model>_output_info.cdl`.

5. **Write a model-specific parameter parser.** Copy `rag/parameter_parser.py` → `rag/<model>_parameter_parser.py`. Replace:
   - The `fates_\w+` regex (`parameter_parser.py:270`) with the new model's parameter naming convention.
   - The `CATEGORIES` table (`parameter_parser.py:27-58`) with categories appropriate to the new model.
   - The PFT-detection logic (`is_pft_specific` via `'fates_pft' in dimensions`) with the new model's "group" axis if it has one (could be PFTs, plant types, soil orders, cohorts, etc.).
   - Class name `FATESParameterParser` → `<Model>ParameterParser`.

6. **Write a model-specific output parser.** Copy `rag/output_parser.py` → `rag/<model>_output_parser.py`. Replace:
   - The `FATES_` prefix discriminator (`output_parser.py:170-171`) with the new model's variable prefix.
   - The `KEY_ELM_VARIABLES` allowlist with calibration-relevant variables for the new model.
   - The `OUTPUT_CATEGORIES` and `DIMENSION_LEVEL_MAP` tables.

7. **Write a curated relationships YAML for the new model.**
   Copy `rag/data/curated_relationships.yaml` → `rag/data/<model>_relationships.yaml`. Keep the schema (`categories`/`mechanisms`/`outputs`/`parameters` with `controls`/`affects`/`related_to`/`controlled_by`/`key_parameters` edges) — it is **model-agnostic**. Replace all the content:
   - List the new model's mechanistic processes (analogous to PID_Controller, ECA_Competition, Cold_Phenology, etc.). Aim for 5–10 mechanisms initially.
   - For each mechanism, list its controlling parameters (must match names in the parameter CDL) and the output variables it affects (must match names in the output CDL).
   - Document calibration notes for each parameter — what changes when you tune it, what NOT to do, known interactions.
   - 60–100 parameter entries is enough for a first usable build.

8. **Add a model adapter or refactor the graph builder.** The simplest path: copy `rag/graph_builder.py` → `rag/<model>_graph_builder.py` and edit to use your new parsers. The cleaner path: refactor `graph_builder.py` to take parser objects as parameters (dependency injection) and reuse the existing module for any model. The cleaner path is more work but pays back if you want to maintain multiple models long-term.

9. **Update `rag/loader.py` to register the new KB:**
   ```python
   DEFAULT_KNOWLEDGE_BASES = [
       "docs/fates-knowledge-base",
       "docs/elm-knowledge-base",
       "docs/ecosim-knowledge-base",   # NEW
   ]
   ```
   Or — better for true multi-model support — make `DEFAULT_KNOWLEDGE_BASES` a function that selects the right list based on a `A2MC_TARGET_MODEL` env var.

10. **Build the new index in a separate persist dir to avoid clobbering FATES:**
    ```bash
    $PY scripts/build_rag_index.py --rebuild --test \
        --kb-path docs/ecosim-knowledge-base \
        --persist-dir rag/chroma_db_ecosim \
        --graph-path rag/ecosim_knowledge_graph.json \
        --param-cdl docs/ecosim-knowledge-base/ecosim_params_info.cdl \
        --output-cdl docs/ecosim-knowledge-base/ecosim_output_info.cdl
    ```

11. **Teach `HybridRetriever` to load the new model.** Either pass the new persist dir / graph path explicitly when instantiating, or add a `model="ecosim"` constructor argument that switches paths internally.

12. **Validate.** Spot-check that:
    - A natural-language query like `"how does <model> handle nitrogen uptake"` returns relevant chunks from the new wiki.
    - `get_targeted_context(param_names=[...], output_names=[...])` returns parameter definitions from the new CDL.
    - Graph traversal finds the curated mechanism→output paths you encoded in the YAML.

### Path B — Single multi-model RAG

Index multiple models into one Chroma collection and one graph, distinguished only by metadata tags (`kb_source`, `model`). This is what the existing FATES+ELM RAG already does at the vector layer (`kb_source` field). The graph layer would need namespacing on node IDs to avoid collisions (e.g., `parameter:fates:fates_cnp_pid_kp` vs `parameter:ecosim:N_uptake_vmax`).

**Pros:** A single retrieval call can pull from any model. Cross-model comparisons become possible.

**Cons:** Larger index, slower queries, harder to reason about. Mixing models in graph traversal can produce surprising paths. Not recommended unless you actively want cross-model knowledge fusion.

**Recommendation:** Path A for the first new model. Migrate to Path B only if multi-model fusion becomes a real need.

### What survives for free

- Build script structure (`build_rag_index.py`) — only the default paths and class names need to change.
- Loader chunking strategy — model-agnostic, structure-aware, works for any Markdown wiki.
- Vector store (`vector_store.py`) — model-agnostic ChromaDB wrapper. Just rename the collection.
- Knowledge graph schema (`knowledge_graph.py`) — Parameter/Output/Mechanism/Module/Category/Dimension is generic enough for almost any process-based model. PFT may need to be replaced with a different "group" type.
- Curated YAML schema — fully model-agnostic.
- HybridRetriever API surface — model-agnostic, but the entity-extraction regex (`hybrid_retriever.py:316-322`) and the keyword→mechanism map (`hybrid_retriever.py:332-341`) need to be rewritten per model.
- ReasoningModule integration in `reasoning/base.py` — model-agnostic; just point at a different retriever instance.

### What needs to be rewritten

- All the `fates_\w+` and `FATES_*` regex patterns (parameter_parser, output_parser, hybrid_retriever, graph_builder).
- The CATEGORIES, OUTPUT_CATEGORIES, DIMENSION_LEVEL_MAP, KEY_ELM_VARIABLES tables.
- The curated YAML content (schema is reusable, content is not).
- The keyword→mechanism map in `_extract_entities_from_query()`.
- The `DEFAULT_PFT_NAMES` Arctic-specific labels.
- Class names with "FATES" prefix (cosmetic but pervasive — find/replace works).

---

## 6. Common pitfalls and gotchas

| # | Pitfall | Cause | Fix |
|---|---|---|---|
| 1 | Vector index stays empty after rebuild | Wiki dir name doesn't match `loader.py:366-371` patterns (e.g., commit-pinned `fates-codebase-wiki-e85d997/`) | See [Recipe 1](#recipe-1-bumping-the-wiki-to-a-new-commit-pinned-tree) — symlink, glob, or explicit override |
| 2 | Old chunks linger after content change | `add_documents()` dedupes by `chunk_id` and SKIPS existing entries (`vector_store.py:110-127`) | Always use `--rebuild` for content updates, not incremental adds |
| 3 | Code blocks get split mid-content | `clean_text()` strips triple-backtick fences (`loader.py:111-138`), so the recursive splitter no longer sees them as boundaries | Currently not fixed. If you need code fidelity, add a separator for ```` ``` ```` to the splitter and skip the fence-strip. Affects rare technical queries that want exact code |
| 4 | `pip install` fails with externally-managed env | Homebrew Python 3.12 blocks pip | Use `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3` (the `python.org` install) for everything RAG-related. Documented in `memory/dev_logs/20260202b_RAG_Python_Environment_Fix.md` |
| 5 | Curated edge silently dropped during build | Curated YAML references a parameter or output that doesn't exist in the CDL — graph builder defensively checks both endpoints (`graph_builder.py:414`) | Either add the parameter to the CDL, or list it under the YAML's curated-only fallback (`graph_builder.py:521-554`). Watch the build log for "skipped edge: endpoint not found" |
| 6 | PFT count wrong | `_resolve_pft_list()` checks `A2MC_PFTS` env var first, then falls back to `[7, 9, 10]` | Set `A2MC_PFTS=1,2,3,4,5,6,7,8,9,10,11,12` for a non-Kougarok site |
| 7 | RAG returns FATES-only results when running ELM | Loader only walks `DEFAULT_KNOWLEDGE_BASES = [fates, elm]`; no model-aware filtering at query time | Either filter via `kb_source` metadata in the Chroma query, or instantiate per-model retrievers (Path A in Recipe 2) |
| 8 | New parameter CDL doesn't pick up new params | `fates_params_info.cdl` is hand-managed, NOT auto-regenerated from FATES source | Run `ncdump -h fates_params_default.nc > fates_params_info.cdl` against the FATES build matching your wiki commit. The roadmap should be: bump wiki + bump CDL together |
| 9 | Graph has 168 nodes instead of 1,299 | You're running an old build from before the Feb 2026 expansion | Re-run `--rebuild`. The expansion is documented in `memory/dev_logs/20260211b_RAG_Expansion_Full_Parameter_Output_Coverage.md` |
| 10 | Wiki path mismatch between FATES (`fates-codebase-wiki-e85d997`) and ELM (`elm-codebase-wiki-60d9aad`) | The two models are at different commits in the same E3SM_FATES tree (FATES is a submodule pinned to e85d997; ELM parent at 60d9aad) | Document this in any ChromaDB metadata as separate `kb_source` tags. Don't try to force them to a single commit |

---

## 7. Cost and time estimates

For the current build (FATES + ELM, ~106 wiki docs + 560 CDL definitions, 1,299 graph nodes):

| Step | Wall time | Notes |
|---|---|---|
| Document loading + chunking | ~10 s | Single-threaded Markdown parsing |
| Sentence-transformers embedding (~3,000 chunks) | ~60–90 s | First run downloads model (~80 MB); subsequent runs are faster |
| Chroma write | ~10 s | Sqlite-backed |
| CDL parsing (~290 params + ~679 outputs) | <5 s | Pure-Python regex |
| Graph build (Layer 1 + Layer 2) | <5 s | NetworkX in-memory |
| Save graph JSON | <1 s | |
| **Total `--rebuild` from scratch** | **~2 min** | On a 2025 MacBook Pro |

Disk footprint:
- `rag/chroma_db/` — ~50–80 MB (vectors + sqlite)
- `rag/fates_knowledge_graph.json` — ~1–2 MB
- HuggingFace model cache — ~80 MB (one-time, shared across projects)

API cost: **$0**. The build is local. Embedding is done by sentence-transformers locally, not via OpenAI/Anthropic.

---

## 8. Reference: Where things live in the code

A grep cheat-sheet for finding the relevant lines fast:

```bash
# Default paths and KB list
grep -n "DEFAULT_KNOWLEDGE_BASES\|DEFAULT_PARAM_CDL\|DEFAULT_OUTPUT_CDL" rag/loader.py scripts/build_rag_index.py

# Embedding model and collection name
grep -n "all-MiniLM-L6-v2\|fates_knowledge" rag/vector_store.py

# Wiki subdir patterns (the Recipe 1 pain point)
grep -n "codebase-wiki\|kb_name" rag/loader.py

# Chunk ID format and dedup logic
grep -n "chunk_id\|add_documents" rag/vector_store.py rag/loader.py

# PFT list resolution
grep -n "A2MC_PFTS\|_resolve_pft_list\|DEFAULT_PFT_NAMES" rag/graph_builder.py

# Parameter regex (the FATES-specific assumption)
grep -n "fates_" rag/parameter_parser.py rag/output_parser.py rag/hybrid_retriever.py rag/graph_builder.py

# CDL parser entry points
grep -n "FATESParameterParser\|FATESOutputParser" rag/

# Curated YAML loading
grep -n "load_curated_relationships\|extract_.*_from_yaml\|_overlay_curated_relationships" rag/graph_builder.py

# HybridRetriever public API
grep -n "def get_\|def find_" rag/hybrid_retriever.py

# ReasoningModule integration point
grep -n "rag_retriever\|HybridRetriever" reasoning/base.py
```

---

## 9. Open questions / known limitations

These are NOT bugs but design choices worth flagging when planning extensions:

1. **No re-ranking between vector and graph results.** `get_targeted_context()` formats them as separate Markdown sections; the LLM does the integration. A learned re-ranker (cross-encoder, ColBERT) would help precision, especially for ambiguous queries.

2. **No temporal versioning.** The graph and vector index are point-in-time snapshots. There's no way to query "what did the FATES wiki say at commit X" without rebuilding. The commit-pinned wiki directories solve this for the source content but not for the index.

3. **Curated YAML is single-tenant.** All curated relationships live in one file. As the curated set grows beyond a few hundred entries, splitting by mechanism or category might help.

4. **No quantitative store.** The original GraphRAG plan included a SQLite "Phase 2C" structured data store for Morris rankings, validation targets, and experiment results. It was deferred (`memory/dev_logs/20260111b_RAG_GraphRAG_Implementation_Complete.md` "Phase 2C: DEFERRED"). Ranking-based queries currently happen in `phases/phase2_screening/` with Pandas, not via RAG.

5. **Dedup on ID, not on content.** Chunk dedup uses `chunk_id`, not content hash. So a wiki edit that preserves chunk count but changes content (without `--rebuild`) would be silently ignored.

6. **Code-fence stripping** in `clean_text()` (`loader.py:111-138`) loses syntax markers. Trade-off between cleaner text-vector embeddings and code fidelity. Acceptable for current usage but document-aware indexing (e.g., one chunk per code block) might be better.

7. **The two CDL files are hand-maintained.** They are NOT auto-regenerated from FATES source on commit bump. A wiki bump should be paired with a CDL refresh.

---

## Quick decision tree

```
Is this a new model entirely?  ──→  Recipe 2 (Adding a new model)

Is this a wiki content update at a new FATES/ELM commit?  ──→  Recipe 1 (Wiki bump)

Did you just edit curated_relationships.yaml?  ──→  
    $PY scripts/build_rag_index.py --rebuild --graph-only --test
    (no need to rebuild the vector index)

Did you just add CDL definitions?  ──→  
    $PY scripts/build_rag_index.py --rebuild --test
    (full rebuild)

Did the existing index just stop working?  ──→  
    1. Check Python version (3.10 from python.org)
    2. Check rag/chroma_db/ exists and is non-empty
    3. Check rag/fates_knowledge_graph.json exists
    4. Run --test on the existing index
    5. If still broken, --rebuild
```
