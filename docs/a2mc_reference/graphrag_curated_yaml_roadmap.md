# GraphRAG Curated YAML Roadmap

**Audience:** users adapting A2MC to a new model (the "adapter kit" workflow), or A2MC maintainers extending the curated knowledge graph.

**Status:** the FATES curated YAML is the worked example (~1388 lines, hand-curated over months from Knox 2024/2026 CNP Guidebook + A2MC calibration experience). Pattern proven; adapter-kit workflow for new models is the open frontier.

**Companion docs:**
- `codebase_wiki_generation_roadmap.md` — Step 1: produce the source-grounded wiki
- `rag_build_roadmap.md` — Step 2: wire wiki + parsers into the vector RAG
- **This doc — Step 3: overlay calibration intelligence via the curated YAML (the GraphRAG layer)**

---

## What GraphRAG actually is

A2MC's knowledge layer is hybrid. The wiki and parameter file feed two parallel structures:

```
Wiki Markdown        ─────────►  ChromaDB vector index   (semantic search)
                                          │
Parameter file       ────┐               │
                         │               ▼
Curated YAML overlay ────┴────►  NetworkX knowledge graph (typed relationships)
                                          │
                                          ▼
                              HybridRetriever.get_targeted_context()
                                          │
                                          ▼
                                AI calibration agents
```

Vector RAG answers "what does the wiki say about X?". Graph RAG answers "what parameters affect FATES_LEAFC?", "what mechanism does fates_cnp_pid_kp control?", "what other parameters are usually tuned with this one?". They are different retrieval modes; A2MC's Phase 3/4/6 reasoning prompts use both.

The graph has two layers, and they have very different costs to produce:

| Layer | Source | Cost to produce | Calibration leverage |
|---|---|---|---|
| **Layer 1 — auto-extracted** | parameter file (CDL/JSON/YAML), output-variable file | ~1 day of parser work per format | Surface-level: name, category, dimension, default, units |
| **Layer 2 — curated overlay** | Hand-authored YAML capturing domain knowledge | Weeks to months of expert author time | **Deep:** mechanism→parameter→output relationships, calibration notes, "tune these together" advice |

**The curated YAML is the most A2MC-specific artifact in the whole stack.** It's where the AI calibration agents get their domain intuition. A vector RAG without it gives generic FATES information; a vector RAG WITH it can recommend specific parameter combinations to investigate when leaf carbon is low.

For adapter-kit users, Layer 2 is where the guidance is thinnest. This roadmap addresses that gap.

---

## Layer 1 — auto-extracted graph (parameter + output parsers)

Layer 1 is the model-specific code that reads a structured parameter or output-variable file and emits graph nodes. The pattern is in `rag/parameter_parser.py` and `rag/output_parser.py`. For adapter-kit users:

### What Layer 1 produces (for FATES)

- **Parameter nodes:** one per parameter, attributes include `category`, `dimension(s)`, `default value(s)`, `units`, `long_name`. ~324 nodes for FATES at e85d997, ~348 at e027a40.
- **Output-variable nodes:** one per registered history variable, attributes include `dimensions`, `units`, `long_name`, `cell_methods`. 495 at e027a40.
- **Dimension nodes:** `fates_pft`, `fates_levscls`, `fates_history_age_bins`, etc.
- **Category nodes:** `cnp`, `allocation`, `phenology`, `allometry`, `fire`, `hydraulics`, etc. — these come from the curated YAML, not the parameter file.

### What Layer 1 needs from the model

| Input | Format examples | Where the parser lives |
|---|---|---|
| Parameter file | NetCDF/CDL (FATES api≤31, ELM), JSON (FATES api43+), YAML (some models) | `rag/parameter_parser.py` |
| Output-variable file | CDL ncdump-h output, source-extracted JSON, YAML | `rag/output_parser.py` |

The existing FATES parser handles CDL. For JSON (api43+), an extension is needed (deferred to Phase 4 of the version-association branch). For an adapter-kit user with a different format, they extend the same modules with format-specific parsing.

**Effort estimate per format:** ~50–150 lines of Python per format type. The parser is mechanical: read structured file, emit graph nodes with the model's parameter/output schema. No AI involvement needed.

### Worked example: where to add JSON dispatch

```python
# rag/parameter_parser.py (sketch)
def parse_parameter_file(path: Path):
    if path.suffix == ".cdl":
        return _parse_cdl(path)
    elif path.suffix == ".json":
        return _parse_json(path)            # NEW for FATES api43+
    elif path.suffix in (".yaml", ".yml"):
        return _parse_yaml(path)            # NEW for hypothetical YAML model
    else:
        raise ValueError(f"Unsupported parameter file format: {path}")
```

Each branch returns the same internal `Parameter` dataclass so the rest of the pipeline doesn't care which format produced it. The schema mapping (parameter file fields → `Parameter` fields) IS model-specific and must be authored per format.

---

## Layer 2 — curated YAML (the calibration intelligence)

This is where adapter-kit guidance is currently weakest. The remainder of this roadmap focuses on Layer 2.

### YAML schema (proven from FATES)

`rag/data/curated_relationships.yaml` has four top-level sections:

```yaml
categories:                        # Parameter groupings + their mechanisms + key outputs
  cnp:
    full_name: "Carbon-Nitrogen-Phosphorus"
    description: "..."
    mechanisms: [PID_Controller, Nutrient_Uptake, ECA_Competition, ...]
    key_outputs: [FATES_LEAFC, FATES_FROOTC, ...]

mechanisms:                        # Named processes + their controlling parameters + affected outputs
  PID_Controller:
    description: "Proportional-Integral-Derivative controller for C:N:P allocation"
    code_reference: "FATESPartehMod.F90::CNPAllocate"
    doc_reference: "Knox et al. 2024 CNP Guidebook"
    parameters: [fates_cnp_pid_kp, fates_cnp_pid_ki, fates_cnp_pid_kd]
    affects: [FATES_L2FR, FATES_LEAFC, FATES_FROOTC]
    notes: |
      The PID controller adjusts leaf-to-fine-root ratio based on
      C:nutrient stoichiometry in storage pool. Higher Kp = more responsive.
      KNOX 2024 RECOMMENDATION: If FATES_L2FR shows strange behavior...

outputs:                           # Output variables → which parameters affect them
  FATES_LEAFC:
    description: "Leaf carbon mass"
    direct_drivers: [...]
    indirect_drivers: [...]
    diagnostic_value: "..."

parameters:                        # Per-parameter relationships
  fates_cnp_pid_kp:
    category: cnp
    controls: [PID_Controller]
    affects: [FATES_L2FR, FATES_LEAFC, FATES_FROOTC]
    related_to: [fates_cnp_pid_ki, fates_cnp_pid_kd]
    calibration_notes: |
      Proportional gain for PID allocation controller.
      Higher values = more responsive to nutrient stress.
      Typical range: 1e-6 to 0.01
```

### Relationship types

Four relationship types proven sufficient on FATES:

| Type | Direction | Example | When to use |
|---|---|---|---|
| `controls` | parameter → mechanism | `fates_cnp_pid_kp controls PID_Controller` | Parameter directly governs a mechanism's behavior |
| `affects` | parameter → output (or mechanism → output) | `fates_cnp_pid_kp affects FATES_LEAFC` | Parameter influences the output, possibly indirectly |
| `related_to` | parameter ↔ parameter (bidirectional) | `fates_cnp_pid_kp related_to fates_cnp_pid_ki` | Parameters that should be tuned together |
| `modifies` | parameter → parameter | `fates_phenflush_fraction modifies fates_storage_cushion` | One parameter changes another's effective behavior |

Most curated relationships are `controls` and `affects`. `related_to` is the sleeper; it's how A2MC produces "consider tuning these N parameters together" recommendations.

### Why Layer 2 matters more than it looks

Layer 1 alone produces a flat list of parameters with surface attributes. The graph it makes is shallow. Specifically:

- **No mechanism nodes.** Without curated YAML, the graph has parameter nodes but no `PID_Controller` node, no `Nutrient_Uptake` node, no `Cold_Deciduous` node. Mechanisms are conceptual constructs not extractable from parameter file metadata.
- **No parameter-to-output edges.** Layer 1 knows `FATES_LEAFC` exists and `fates_cnp_pid_kp` exists, but cannot connect them.
- **No tuning-together hints.** Three PID gains (`kp`, `ki`, `kd`) are obviously related to a human, but Layer 1 sees them as three isolated parameters with no edges between them.
- **No calibration narrative.** Layer 1 has no place to record "if FATES_L2FR is misbehaving, reduce kp by 10×." That's what `calibration_notes` is for.

When the AI calibration agent retrieves "what affects FATES_LEAFC," Layer 1 alone returns the dimension and units of FATES_LEAFC. Layer 1 + Layer 2 returns the parameter-mechanism chain that drives leaf carbon, with calibration warnings for each. The difference is whether the agent's recommendation is informed.

---

## Authoring a curated YAML for a new model

This is the hard part. The FATES YAML took months to author and continues to be refined. For an adapter-kit user, the goal is a **defensible v0.1** in days, not perfection on day one.

### Phase 0 — collect source material

Before writing any YAML, gather:

1. **The model's primary calibration / user guide** (e.g., Knox 2024 CNP Guidebook for FATES). This is the single most leveraged source.
2. **The newly-generated codebase wiki** (Step 1 from `codebase_wiki_generation_roadmap.md`).
3. **The auto-extracted parameter file** (Layer 1 input).
4. **2–3 published model-application papers** that discuss parameter sensitivities for your sites of interest.
5. **Any prior calibration runs / lessons-learned docs** if they exist.

Without (1), authoring Layer 2 from scratch is mostly guessing. If your model has no equivalent of the Knox guidebook, Layer 2 starts thinner and grows organically as calibration runs surface relationships.

### Phase 1 — categorize

Partition the model's parameters into **5–15 categories**. These become top-level entries under `categories:`. Each category should:

- Group parameters that participate in similar physical processes
- Have ≤30 parameters (otherwise it's too coarse — split it)
- Have ≥3 parameters (otherwise it's too fine — merge it)

For FATES the categories are: `cnp`, `allocation`, `allometry`, `phenology`, `mortality`, `fire`, `hydraulics`, `radiation`, `respiration`, `recruitment`. Most ecosystem-model categories will look similar.

### Phase 2 — name the mechanisms

For each category, identify the **named processes** the parameters control. These become entries under `mechanisms:`. Heuristic:

- A mechanism is a **named process** in the literature, not just a parameter group.
- A mechanism should have a `code_reference` (the source file/routine that implements it) — if you can't cite source code, the mechanism is probably too vague.
- A mechanism should have a `doc_reference` (the user guide / paper section that describes it).
- Each mechanism is governed by 1–10 parameters (typically 3–6).
- Each mechanism affects 1–10 outputs (typically 2–5).

Worked FATES example mechanisms: `PID_Controller`, `ECA_Competition`, `RD_Competition`, `Cold_Deciduous`, `Drought_Deciduous`, `Storage_Allocation`, `DBH_Height`, `Crown_Allometry`, `Hydraulic_Failure`, `Fire_Mortality`, `Decomposition`, `N_Fixation`. ~30 mechanisms total.

The mechanism layer is the **conceptual skeleton** of the graph. Spending time here pays back later.

### Phase 3 — fill in `parameters:` entries

For each parameter in the parameter file, write an entry with:

- `category`: which category it belongs to (1 only)
- `controls`: which mechanisms it controls (0–3)
- `affects`: which outputs it affects (0–10)
- `related_to`: which other parameters tune together (0–10, common: 1–3)
- `calibration_notes`: free-form Markdown — typical range, sign conventions, gotchas

Not every parameter needs every field. Skip empty lists.

**Heuristic for `affects`:** if the wiki cites the parameter as appearing in a formula that computes an output, list that output. If the parameter modulates a mechanism that affects an output, list it indirectly. Two hops max — beyond that, the relationship is too diffuse to be useful.

**Heuristic for `related_to`:** parameters appear together in user-guide tuning advice, or share a category and have correlated effects. The PID gains are the canonical example.

### Phase 4 — fill in `outputs:` entries (optional but valuable)

For each high-priority output variable (typically 10–30 of them):

- `description`: one line
- `direct_drivers`: parameters that appear in the formula
- `indirect_drivers`: parameters that affect inputs to the formula
- `diagnostic_value`: how to interpret unusual values during calibration

The `outputs:` section is a reverse index of `parameters:`, useful when the calibration agent starts from "FATES_LEAFC is too low" rather than "what does fates_cnp_pid_kp do?".

### Phase 5 — sanity check

Before declaring v0.1 complete:

- Every parameter in the parameter file appears under `parameters:` (or is explicitly skipped in a `_skip:` list with rationale).
- Every mechanism listed under any `parameters[name].controls` appears under `mechanisms:`.
- Every output listed under any `parameters[name].affects` appears in the parameter file's output-variable list.
- Every category listed under any `parameters[name].category` appears under `categories:`.
- No fabricated parameter/mechanism/output names. Cross-check against the wiki + parameter file.

Run the graph builder to confirm the YAML loads cleanly:

```bash
/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -c "
from rag.graph_builder import load_curated_relationships
data = load_curated_relationships()
print('categories:', len(data.get('categories', {})))
print('mechanisms:', len(data.get('mechanisms', {})))
print('parameters:', len(data.get('parameters', {})))
print('outputs:', len(data.get('outputs', {})))
"
```

For FATES the counts should be roughly: 10 categories, ~30 mechanisms, ~150–300 parameters with non-empty entries, ~20–50 outputs.

---

## Bootstrapping with AI assistance (faster than from scratch)

For adapter-kit users, authoring 1000+ lines of YAML by hand is daunting. Use the wiki you already have (Step 1) as the primary input to a bootstrapping subagent.

### Recipe: AI-assisted v0.1 from wiki + parameter file

1. **Decompose by category** (Phase 1, manual). A human picks the 5–15 categories.
2. **Per-category subagent dispatch.** For each category, send a subagent with:
   - The relevant wiki sections (the ones that document mechanisms in this category)
   - The parameter file (filtered to parameters in this category)
   - The category's mechanism list (from Phase 2, manual)
   - A YAML schema example from FATES
   - Instructions to author the `parameters:` entries for this category
3. **Each subagent produces a YAML fragment** with parameters, controls, affects, related_to, calibration_notes. Citations to wiki paths and source files.
4. **Merge fragments** into the master YAML.
5. **Human review pass** (Phase 5 sanity check, plus a careful read of `calibration_notes` since this is where AI hallucinations are most likely).

Subagent prompt template (per category):

```text
Author the YAML `parameters:` entries for the {category_name} category of
the {model} curated relationships file.

## Inputs (read-only)

1. Wiki sections: {list of wiki paths covering this category's mechanisms}
2. Parameter file (filtered): {param_file_path}
   Parameters in this category: {comma-separated list}
3. Mechanism inventory for this category: {list of mechanism names from Phase 2}
4. Schema example: rag/data/curated_relationships.yaml (FATES — read for format)

## Output

For each parameter in the input list, produce an entry:

```yaml
{parameter_name}:
  category: {category_name}
  controls:    # 0-3 mechanism names
    - ...
  affects:     # 0-10 output variable names
    - ...
  related_to:  # 0-10 other parameter names
    - ...
  calibration_notes: |
    Free-form Markdown. Typical range. Sign conventions. Gotchas.
    Cite wiki sections (path:line) for any non-trivial claim.
```

## Constraints

- Do NOT invent mechanisms not in the input mechanism inventory.
- Do NOT invent output variables not in the parameter/output file.
- Do NOT invent `related_to` parameters not in the parameter file.
- For `calibration_notes`, cite the wiki when making non-trivial claims.
- If a parameter has no defensible content for a field, omit the field
  rather than fabricate.

Output to: rag/data/curated_relationships_{category_name}.yaml
```

Wall-clock estimate: ~10–20 min per category subagent. For a model with 10 categories: ~30 min if dispatched in parallel.

**Quality bar for v0.1:** the YAML loads cleanly into the graph builder, and a manual spot-check of 5 random parameters per category confirms the entries match wiki content. Calibration runs will surface the rest of the gaps.

---

## Validating a curated YAML before shipping

Beyond Phase 5 sanity checks, run these before treating the YAML as production:

### Static validation

```python
# Pseudocode
yaml_data = load_yaml(...)
param_file = load_parameter_file(...)

# 1. Every parameter in YAML exists in parameter file
yaml_params = set(yaml_data['parameters'].keys())
file_params = set(param_file.parameters.keys())
assert yaml_params <= file_params, f"YAML has fabricated params: {yaml_params - file_params}"

# 2. Every mechanism referenced is defined
defined_mechs = set(yaml_data['mechanisms'].keys())
referenced_mechs = {m for p in yaml_data['parameters'].values() for m in p.get('controls', [])}
assert referenced_mechs <= defined_mechs

# 3. Every output referenced exists
defined_outputs = set(load_output_variables())
referenced_outputs = {o for p in yaml_data['parameters'].values() for o in p.get('affects', [])}
assert referenced_outputs <= defined_outputs

# 4. Every related_to reference is bidirectional
for p_name, p in yaml_data['parameters'].items():
    for related in p.get('related_to', []):
        assert p_name in yaml_data['parameters'].get(related, {}).get('related_to', []), \
            f"{p_name} → {related} is one-way; should be bidirectional"
```

### Retrieval validation

After building the graph, run the standard A2MC test queries:

```python
from rag.hybrid_retriever import HybridRetriever
r = HybridRetriever(auto_build=False)

# Probe questions a calibration user might ask
test_queries = [
    ("What parameters affect <key output 1>?", expected: at least 3 hits),
    ("What controls <key mechanism 1>?", expected: 1-5 parameter hits),
    ("What is typically tuned with <key parameter 1>?", expected: 1-5 related_to hits),
]

for q, expectation in test_queries:
    ctx = r.get_targeted_context(...)
    # Manual review: does the response include relevant parameters?
```

For FATES, the test queries are codified in `tools/rag_diff_queries.yaml` (Phase 3 verification deliverable, see `docs/18_ELM_FATES_Version_Association_Plan.md`).

### Regression validation

When the YAML is updated (e.g., when a model bumps and the parameter file changes):

1. Diff the YAML before/after.
2. For removed parameters, confirm they are also gone from the new parameter file (otherwise the YAML lost real content).
3. For added parameters, confirm they exist in the new parameter file (otherwise the YAML invented content).
4. For changed `calibration_notes`, manually review.

The FATES YAML had a phantom `fates_cnp_nfix` entry through Feb 2026 that referenced a parameter that never existed in source. The Apr 22 rebuild fixed it (`memory/dev_logs/20260422a_*`). Adapter-kit users should expect to find similar drift on every model bump.

---

## Worked example: FATES YAML

The full file is at `rag/data/curated_relationships.yaml` (1388 lines). Key statistics:

- **10 categories:** cnp, allocation, allometry, phenology, mortality, fire, hydraulics, radiation, respiration, recruitment.
- **~30 mechanisms:** the conceptual skeleton.
- **~150 parameters with curated entries** (out of ~324 total in the parameter file at e85d997). Coverage gaps are mostly in lower-priority categories like fuel-moisture-class fire parameters.
- **20+ output entries** for the most calibration-relevant variables.
- **~150 `related_to` edges,** clustered around PID gains, ECA half-saturations, allometry coefficients.
- **~600 `affects` edges.**

The YAML grew incrementally over Jan–April 2026 as Knox guidebook content was distilled and as A2MC calibration runs surfaced new relationships (e.g., the "Allocation Paradox" discovery at Kougarok added new `related_to` edges between storage and allocation parameters).

For an adapter-kit user, **the FATES YAML is the most concrete example of what a defensible Layer 2 looks like.** Read 100 lines of it before starting your own.

---

## Common pitfalls

| Pitfall | Mitigation |
|---|---|
| Subagent invents parameters not in the parameter file | Phase 5 / static validation step 1. |
| Subagent invents mechanism names not in the curated inventory | Per-category subagent prompts include the inventory; static validation step 2. |
| `affects` edges are too loose (every parameter "affects" every output) | Cap `affects` at 10 per parameter; force the subagent to choose. |
| `related_to` is one-way (A → B but not B → A) | Static validation step 4. |
| Calibration notes are wishy-washy and don't help users | Require citation: "every non-trivial claim cites a wiki path or source file." Subagent prompts enforce this. |
| YAML grows to 5000+ lines with diminishing returns | Track coverage as a percentage of the parameter file; once you hit 60–80% of parameters with curated entries, the marginal value of adding more is low. Spend time on calibration_notes quality instead. |
| YAML and parameter file drift apart on model bumps | Regression validation pass on every bump. The Apr 22 FATES rebuild caught one phantom (`fates_cnp_nfix`). |
| Categories evolve and YAML doesn't catch up | When a category split happens (e.g., a future split of `cnp` into `cnp_uptake` and `cnp_allocation`), update categories first, then propagate to all parameters in the affected categories. |

---

## Recipes

### Recipe G1 — New model, no curated YAML at all

Adapter-kit user adopting a model A2MC has never targeted (e.g., a new vegetation model after FATES, ELM, EcoSIM, ReSOM, BeTR).

1. **Have wiki + parameter file ready.** Steps 1–2 from the prerequisite roadmaps must be done first.
2. **Categorize manually** (Phase 1, ~1 hour for a typical ecosystem model).
3. **Name mechanisms manually** (Phase 2, ~2–4 hours, cross-referencing the user guide).
4. **Bootstrap parameter entries via AI** (Phase 3, AI-assisted recipe above).
5. **Author outputs entries manually** for top 10–20 calibration-relevant outputs (~2 hours).
6. **Sanity check + retrieval test** (Phase 5 + validation section above).
7. **Commit v0.1.** Plan to iterate.

Estimated total: ~1–2 working days for v0.1 given a decent user guide.

### Recipe G2 — Existing curated YAML, model bumps to a new commit

Example: FATES YAML when migrating from e85d997 to e027a40 (the current branch's scope).

1. **Diff the parameter files** between commits. Identify added / removed / renamed parameters.
2. **For removed parameters:** delete entries from `parameters:`. Update any `related_to` lists that reference them.
3. **For renamed parameters:** rename keys + propagate to all `related_to` references. Update `calibration_notes` if the rename reflects a semantic change.
4. **For added parameters:** dispatch one subagent to author entries for the new parameters, with the existing YAML as schema reference.
5. **Audit existing entries for stale claims:** any `calibration_notes` referencing source-line or specific code paths needs to re-anchor against the new commit.
6. **Run validation passes.**
7. **Commit.** Document the changes in the metadata header (`Last updated: ...`).

Estimated total: ~half day for typical model bumps.

### Recipe G3 — Curated YAML for a model component A2MC partially supports

Example: A2MC supports FATES; adapter-kit user wants to add CN-only ELM (not FATES-coupled). They need a curated YAML for ELM CN parameters.

1. **Decide scope overlap with FATES YAML.** ELM-CN has overlap with FATES (allocation, phenology, decomposition) but distinct parameters.
2. **Author a separate YAML** at `rag/data/curated_relationships_elm_cn.yaml`.
3. **Categories may overlap** — that's fine; the graph builder merges them by name.
4. **Mechanisms named differently** — `CN_Allocation` vs FATES's `PARTEH_Allocation`. Don't try to unify; let them be distinct nodes.
5. **Cross-references** in `calibration_notes` are valuable — "this parameter is the ELM-CN analog of FATES `fates_cnp_pid_kp`."

Estimated total: ~1 day given existing FATES YAML as schema reference.

### Recipe G4 — Iteratively grow curated YAML during real calibration

Most curated YAML knowledge is **discovered during use**, not authored upfront. After v0.1 is built:

1. Run a calibration pass on a real site.
2. When the AI agent makes a poor recommendation, trace back: which RAG retrieval was insufficient?
3. The retrieval gap usually maps to a missing or thin curated YAML entry.
4. Update the YAML to fill the gap. Add a calibration_notes line. Add a `related_to` edge.
5. Rebuild the graph.
6. Re-run.

This is how the FATES YAML grew. The "Allocation Paradox" `related_to` edges were authored AFTER a Kougarok calibration run surfaced the unexpected coupling between storage and allocation parameters. The Knox 2026 PID guidance was added AFTER R3 calibration runs showed unstable PID behavior. **Iteration is the methodology.**

---

## Connection to wiki and RAG roadmaps

The three reference docs work as a sequence:

1. `codebase_wiki_generation_roadmap.md` — Step 1: wiki (the source-grounded text foundation)
2. `rag_build_roadmap.md` — Step 2: vector RAG (auto-built from wiki + parsers)
3. **This doc — Step 3: GraphRAG curated YAML** (the calibration intelligence)

For adapter-kit users, all three are required for a defensible A2MC instance. Cutting corners on Step 3 produces a calibration framework that confidently retrieves wiki text but cannot reason about parameter-mechanism-output relationships. Cutting corners on Step 1 or 2 produces an A2MC that confidently retrieves wrong content.

The curated YAML is the longest-lived artifact of the three. Wiki gets regenerated on every model bump (~half day per bump). Vector RAG gets rebuilt automatically from the wiki. Curated YAML evolves slowly over months and is the genuine institutional knowledge of A2MC's domain expertise.

---

## When to update the curated YAML

| Trigger | Recipe |
|---|---|
| New model adoption | G1 |
| Model commit bump (within api epoch) | G2 (lightweight: usually just a few entry additions/removals) |
| Model api-level bump | G2 (heavier: review all `calibration_notes` for source-anchored claims) |
| Calibration run surfaces unexpected coupling | G4 (add `related_to` edges) |
| User guide / paper publishes new mechanism explanation | G4 (add or update `mechanisms:` entry) |
| AI calibration agent makes a poor recommendation traceable to thin curation | G4 |

---

## Companion docs

- `codebase_wiki_generation_roadmap.md` — Step 1: wiki generation. Prerequisite to this roadmap.
- `rag_build_roadmap.md` — Step 2: RAG/GraphRAG building, including parser registration. Recipe 2 covers adding a new model (the Layer 1 work).
- `docs/02_GraphRAG_Implementation_Plan.md` — original GraphRAG design. Useful for understanding the auto-extraction layer.
- `memory/dev_logs/20260113b_GraphRAG_YAML_Integration_Update.md` — historical context on how the curated YAML was integrated with the auto-extracted graph.
- `memory/dev_logs/20260111b_RAG_GraphRAG_Implementation_Complete.md` — initial GraphRAG implementation; useful for the schema choices.
- `rag/data/curated_relationships.yaml` — the FATES curated YAML itself; the canonical worked example.
- `rag/graph_builder.py` — `load_curated_relationships()` and the overlay logic.
