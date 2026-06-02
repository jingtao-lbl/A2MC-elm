# RAG/GraphRAG System Reference

**Purpose:** Detailed reference for the RAG/GraphRAG hybrid retrieval system.
**Summary:** Read this when working on RAG code, knowledge graph, or vector store.
**Referenced from:** `CLAUDE.md` → "RAG/GraphRAG System" section
**Last verified against current index:** 2026-05-28 (post-2026-04-22 rebuild per `memory/dev_logs/20260422a_RAG_Rebuild_Against_New_Wikis_And_Curated_YAML_Fix.md`).

To check current index size yourself:
```bash
ls -lh rag/chroma_db rag/fates_knowledge_graph.json
python3 -c "from rag import HybridRetriever; r = HybridRetriever(); print(r.get_stats())"
```

Recipe for rebuilding from scratch (e.g., when bumping the wiki commit pin): see `docs/a2mc_reference/rag_build_roadmap.md` Recipe 1.

---

## System Overview

Hybrid retrieval system for FATES documentation and knowledge:

| Component | Technology | Stats |
|-----------|------------|-------|
| Vector Store | ChromaDB | 2,581 document chunks (post-2026-04-22 rebuild against `fates-codebase-wiki-e85d997/` and `elm-codebase-wiki-60d9aad/`) |
| Knowledge Graph | NetworkX | 1,295 nodes, 2,197 edges |
| Embedding Model | all-MiniLM-L6-v2 | sentence-transformers |
| Knowledge Bases | FATES | 65 documents |

**Default Knowledge Bases for ELM-FATES Calibration:**
```python
# rag/loader.py
DEFAULT_KNOWLEDGE_BASES = [
    "docs/fates-knowledge-base",
    "docs/elm-knowledge-base",
]
```

Other knowledge bases in `docs/` (ecosim-knowledge-base, resom-knowledge-base) are **not searched** during ELM-FATES calibration - they exist for future model support.

---

## Knowledge Graph Schema

**Node Breakdown:**
| Node Type | Count | Description |
|-----------|-------|-------------|
| Parameter | 897 | 286 base + 606 PFT-specific + 5 curated-only |
| Output | 291 | 250 FATES + 24 key ELM + 17 curated-only |
| Dimension | 58 | NetCDF dimensions (fates_pft, fates_levscpf, levgrnd, etc.) |
| Category | 39 | Parameter categories (from name prefixes) |
| Mechanism | 7 | Key processes (PID, ECA, RD, Storage, etc.) |
| Module | 4 | Code modules |
| PFT | 3 | Site-specific PFTs (configured per use case) |

**Edge Types:**
| Relation | Count | Description |
|----------|-------|-------------|
| contains | 897 | Category contains parameter |
| belongs_to | 606 | PFT-specific parameter belongs to PFT |
| has_dimension | 360 | Parameter/output has NetCDF dimension |
| affects | 165 | Parameter/mechanism affects output |
| related_to | 85 | Parameter-parameter relationships |
| controls | 77 | Parameter controls mechanism |
| implemented_in | 7 | Mechanism implemented in module |
| competes_with | 3 | PFT competition relationships |

---

## Key Files

```
rag/
├── loader.py           # Document loading, chunking, CDL definition indexing
├── vector_store.py     # ChromaDB wrapper (filtered queries: query_parameters, query_outputs)
├── knowledge_graph.py  # Graph schema (Parameter, Output, Mechanism, PFT, Module, Dimension)
├── graph_builder.py    # Two-layer construction: auto-extract CDL + curated YAML overlay
├── retriever.py        # Vector retriever
├── hybrid_retriever.py # Combined vector + graph retrieval (get_targeted_context)
├── parameter_parser.py # Parse FATES parameter CDL files
├── output_parser.py    # Parse ELM-FATES output CDL files
├── data/
│   └── curated_relationships.yaml  # Curated mechanistic relationships (Layer 2)
├── chroma_db/          # Persistent vector index
└── fates_knowledge_graph.json  # Serialized graph
```

---

## Usage

```python
from rag import HybridRetriever

retriever = HybridRetriever(auto_build=True)
context = retriever.get_calibration_context(
    parameters=['fates_cnp_pid_kp'],
    outputs=['FATES_LEAFC', 'FATES_FROOTC'],
    mechanisms=['PID_Controller'],
    pft=10
)

# Targeted context (replaces raw text injection, ~9K token savings per call)
context = retriever.get_targeted_context(
    param_names=['fates_cnp_pid_kp', 'fates_alloc_storage_cushion'],
    output_names=['FATES_LEAFC', 'FATES_FROOTC'],
    mechanisms=['PID_Controller']
)
```

---

## Two-Layer Graph Construction

The knowledge graph uses a two-layer architecture:
- **Layer 1 (Auto-extracted):** ALL parameters (286) and outputs (274) parsed from CDL files with dimensions, units, categories
- **Layer 2 (Curated overlay):** Hand-curated mechanistic relationships from `curated_relationships.yaml` — controls, affects, related_to edges, calibration notes

**CDL Source Files:**
- `docs/fates-knowledge-base/fates_params_info.cdl` — 290 FATES parameter definitions
- `docs/fates-knowledge-base/elm_fates_output_info.cdl` — 679 output variables (~250 FATES + ~429 ELM)

**Curated Relationships (`rag/data/curated_relationships.yaml`):**

Curated mechanistic knowledge overlaid onto auto-extracted graph (Layer 2):
- **7 mechanisms** (PID_Controller, ECA_Competition, RD_Competition, Storage_Allocation, Root_Distribution, Cold_Deciduous, Carbon_Starvation)
- **~65 parameters** with calibration notes, controls, affects, related_to edges
- **~100 outputs** with controlled_by and key_parameters relationships
- Curated metadata enriches (not replaces) auto-extracted node attributes

**To rebuild the knowledge graph and vector index:**

Set `$PYTHON310` to whatever Python 3.10+ environment has the RAG dependencies installed (see "Python Environment" below for the Mac vs. Perlmutter split):

```bash
# Full rebuild (graph + vector store + CDL definitions)
$PYTHON310 scripts/build_rag_index.py --rebuild --test

# Graph only
$PYTHON310 scripts/build_rag_index.py --rebuild --graph-only --test
```

**To update curated relationships only:**
1. Edit `rag/data/curated_relationships.yaml`
2. Run the rebuild command above

Output variable categories (auto-inferred from names):
- Phenology: FATES_GDD, FATES_DAYSINCE_COLDLEAFON, etc.
- Biomass: FATES_LEAFC, FATES_FROOTC, FATES_STOREC, etc.
- Carbon fluxes: FATES_GPP, FATES_NPP, FATES_AUTORESP, etc.
- Allocation: FATES_L2FR, FATES_LEAF_ALLOC, FATES_FROOT_ALLOC, etc.
- Nutrient cycling: FATES_PUPTAKE_SZPF, FATES_NH4UPTAKE_SZPF, etc.
- Soil nutrients: LABILEP, SECONDP, SMIN_NH4_vr, etc.

**Filtered Vector Queries (CDL definitions in ChromaDB):**

Parameter and output definitions from CDL files are indexed in ChromaDB with metadata tags for filtered queries:
```python
# Query parameter definitions only
results = retriever.vector_retriever.query_parameters("PID controller gain", n_results=5)

# Query output definitions only
results = retriever.vector_retriever.query_outputs("leaf carbon biomass", n_results=5)
```

Details: `memory/logs/20260211b_RAG_Expansion_Full_Parameter_Output_Coverage.md`

---

## Python Environment

**IMPORTANT:** The RAG system requires Python 3.10+ with specific packages installed:

```
networkx (knowledge graph)
chromadb (vector store)
sentence-transformers (embeddings)
pyyaml (config loading)
```

### Mac (local dev clone)

Homebrew Python 3.12 is externally-managed and blocks pip installs, so use the Python 3.10 framework install:

```bash
PYTHON310=/Library/Frameworks/Python.framework/Versions/3.10/bin/python3
# Or alias for convenience: alias python310='/Library/Frameworks/Python.framework/Versions/3.10/bin/python3'
```

### Perlmutter (HPC)

Activate the pre-built A2MC environment, which has Python 3.11 with all RAG dependencies installed:

```bash
source ~/a2mc_env/bin/activate
PYTHON310=python   # any 3.10+ works once env is activated
```

### Example invocations

```bash
# Run graph builder
$PYTHON310 rag/graph_builder.py

# Test hybrid retriever
$PYTHON310 -c "from rag import HybridRetriever; r = HybridRetriever(); print(r.get_stats())"
```

---

## RAG Integration with ReasoningModule

The `ReasoningModule` automatically queries RAG/GraphRAG before each Claude API call:

```
┌─────────────────────────────────────────────────────────────┐
│                    ReasoningModule                           │
├─────────────────────────────────────────────────────────────┤
│  1. Extract entities (params, outputs, mechanisms, PFTs)     │
│  2. Query HybridRetriever._get_rag_context()                │
│  3. Query MemoryManager.get_relevant_context()              │
│  4. Combine: RAG Context + Memory Context + Task Data        │
│  5. Send to Claude API                                       │
│  6. Parse structured JSON response                           │
└─────────────────────────────────────────────────────────────┘
```

**Methods with RAG integration:**
| Method | RAG Context Retrieved |
|--------|----------------------|
| `diagnose()` | Parameters from Morris rankings, output variables, mechanisms + targeted param/output definitions |
| `generate_hypothesis()` | Parameters from diagnosis, inferred mechanisms + targeted param/output definitions |
| `interpret_results()` | Modified parameters, affected outputs |
| `extract_lesson()` | Experiment parameters, result variables |
| `analyze_screening_results()` | Target outputs, sensitivity mechanisms |

**Usage:**
```python
from reasoning import ReasoningModule

# RAG enabled by default
reasoning = ReasoningModule(use_rag=True)

# Diagnose with automatic RAG context + targeted parameter definitions
diagnosis = reasoning.diagnose(results, targets, morris_rankings, iteration=1)
# Claude receives: RAG context + Memory context + targeted param context + results data
```

**Disable RAG (faster, less context):**
```python
reasoning = ReasoningModule(use_rag=False)
```

---

## Knowledge Integration in AI Prompts

When A2MC performs diagnosis or generates hypotheses, three knowledge sources are combined into the Claude API prompt:

| Source | Content | Role |
|--------|---------|------|
| **RAG/GraphRAG** | FATES + ELM documentation | General knowledge - "how does the PID controller work?" |
| **Adaptive Memory** | Discoveries, failed approaches, parameter insights | Learned knowledge - "what failed before? what worked?" |
| **Task Data** | Results, targets, sensitivity rankings | Current context - "what are we trying to calibrate?" |

**Prompt Structure (in order):**

```
┌─────────────────────────────────────────────────────────────┐
│  ## FATES Knowledge Base Context (RAG/GraphRAG)             │
│  [Vector search results from docs + Graph traversal]        │
│                                                             │
│  ## Adaptive Memory Context                                 │
│  [Relevant discoveries, FAILED APPROACHES - DO NOT REPEAT]  │
│                                                             │
│  ## FATES Parameter & Output Context (Targeted)             │
│  [Only relevant param/output definitions from CDL via RAG]  │
│  [Replaces previous ~53K char raw text injection]           │
│                                                             │
│  ## Parameters in Current Morris Ensemble                   │
│  [Ensemble parameter list with sampling bounds (~4K chars)]  │
│                                                             │
│  ## Current Data                                            │
│  [Simulation results, validation targets, sensitivity]      │
│                                                             │
│  ## Task Instructions + Response Format                     │
└─────────────────────────────────────────────────────────────┘
```

**Key Safeguard:** The system explicitly marks failed approaches with "DO NOT REPEAT" and instructs Claude to avoid proposing them unless there's strong justification.

**No strict priority** - the sources serve complementary roles:
- RAG provides the "textbook" knowledge (how FATES mechanisms work)
- Memory provides the "experience" (what we learned from previous iterations)
- Both inform the AI's reasoning about the current task data
