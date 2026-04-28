# RAG Validation Workflow

**Audience:** users adapting A2MC to a new model (the "adapter kit" workflow), or A2MC maintainers shipping a new milestone wiki/RAG.

**Status:** Three validators are stable on `main` (`tools/codebase_wiki_validator.py`, `tools/yaml_wiki_validator.py`, `tools/rag_diff.py`). Workflow proven on the FATES api-31-0 → api-43-1 + ELM 60d9aad → d40b843 paired regen (see worked example at the bottom).

**Companion docs:**
- `codebase_wiki_generation_roadmap.md` — Step 1: produce the source-grounded wiki
- `rag_build_roadmap.md` — Step 2: wire wiki + parsers into the vector RAG
- `graphrag_curated_yaml_roadmap.md` — Step 3: overlay calibration intelligence via the curated YAML
- **This doc — Step 4: validate the chain before shipping**

---

## Why validate

The chain `source → wiki → curated YAML → RAG → AI calibration` has four hops. A hallucination at any hop propagates downstream silently. The classes of error that have actually bitten A2MC during model bumps:

| Hop | Failure mode | Impact |
|---|---|---|
| Source → wiki | Fabricated routine names, dead `(file:line)` citations, missing module references | AI cites code that doesn't exist; users land on 404 paths |
| Wiki → YAML | YAML mechanism `code_reference` strings drift; param shorthands stale after rename | YAML validator says "BOTH found" but pointer is wrong |
| YAML → RAG | Phantom parameter nodes (params in YAML not in param file); stale output references | RAG returns ghost results; graph traversal hits dead nodes |
| RAG ↔ RAG | Silent regression vs prior milestone | Hard to spot without a profile diff |

Without automated checks, drift accumulates with every model bump. The three validators close every edge in this chain.

## The validation triangle

```
                    ┌──────────────────────────┐
                    │  RAG Profile (build)     │
                    └────────────┬─────────────┘
                                 │
                          tools/rag_diff.py
                                 │
                    ┌────────────▼─────────────┐
                    │  RAG Profile (reference) │
                    └──────────────────────────┘

           ┌─────────────────────┐
           │  Curated YAML       │  rag/data/curated_relationships.yaml
           └─────────┬───────────┘
                     │
            tools/yaml_wiki_validator.py
                     │
           ┌─────────▼───────────┐
           │  Codebase wiki      │  docs/<model>-knowledge-base/<model>-codebase-wiki-<commit>/
           └─────────┬───────────┘
                     │
            tools/codebase_wiki_validator.py
                     │
           ┌─────────▼───────────┐
           │  Source code        │  pinned commit (E3SM checkout, etc.)
           └─────────────────────┘
```

Read bottom-up: the wiki claims things about the source. The YAML curates relationships from the wiki and parameter file. The RAG indexes both. **Every arrow is now a checked edge.**

The dependency goes bottom-up too: don't trust the YAML validator's "BOTH found" verdict if the wiki hasn't been validated against source first.

---

## When to run

Three triggers warrant a full validation pass:

1. **Before merging a new milestone wiki.** The wiki regen subagents (per `codebase_wiki_generation_roadmap.md`) can hallucinate. Validate before the wiki gets canonized.
2. **After a curated YAML edit.** Hand edits drift from the wiki and parameter file, especially if the model recently bumped.
3. **After a RAG rebuild at a new commit.** The diff vs the prior milestone catches regressions and confirms expected differences.

Single-file curation tweaks (one-line YAML fix) don't need the full sweep — re-run only the affected layer.

---

## Step-by-step playbook

Run the validators **in dependency order**. Fix any Red verdict at one tier before moving to the next.

### Step 1 — Wiki vs source

Question answered: "does the wiki cite real files, real line numbers, real routines, and real parameter names?"

```bash
# Example (FATES at e027a40)
python tools/codebase_wiki_validator.py \
    --wiki   docs/fates-knowledge-base/fates-codebase-wiki-e027a40 \
    --source ~/Desktop/Work/SourceCode/ELM_FATES/E3SM_FATES_api43-1/components/elm/src/external_models/fates \
    --param-file docs/fates-knowledge-base/fates_params_info_e027a40.json \
    --output docs/a2mc_reference/wiki_source_validation_fates_e027a40.md

# Example (ELM at d40b843)
python tools/codebase_wiki_validator.py \
    --wiki   docs/elm-knowledge-base/elm-codebase-wiki-d40b843 \
    --source ~/Desktop/Work/SourceCode/ELM_FATES/E3SM_FATES_api43-1/components/elm/src \
    --output docs/a2mc_reference/wiki_source_validation_elm_d40b843.md
```

Five dimensions:

| Dim | Check |
|---|---|
| 1 | File-citation existence — every `(path/File.F90:NNN)` resolves |
| 2 | Line-bound validity — cited line is in-range for the file |
| 3 | Routine declaration presence — top backtick identifiers appear as `subroutine`/`function` declarations |
| 4 | Parameter-name validity — `<prefix>_*` mentions match the parameter file |
| 5 | Module-file presence — every `*Mod.F90` mentioned in narrative exists somewhere under source root |

**Triage discipline (important).** Dim 4 has a known false-positive rate because the wiki uses the parameter prefix (e.g., `fates_*`) for derived-type names, namelist flags, and filenames. Read the report's "wiki-only parameter names" table before assuming all are fabrications. The strongest signal is usually Dim 5 (`PRTMyHypothesisMod.F90`-style placeholders are unambiguous).

### Step 2 — YAML vs wiki + param + output

Question answered: "are the curated relationships consistent with the wiki + parameter file + output CDL at this commit?"

```bash
# Example (api-43-1 milestone)
python tools/yaml_wiki_validator.py \
    --yaml rag/data/curated_relationships.yaml \
    --wiki docs/fates-knowledge-base/fates-codebase-wiki-e027a40 \
    --param-file docs/fates-knowledge-base/fates_params_info_e027a40.json \
    --output-cdl docs/fates-knowledge-base/elm_fates_output_info_e027a40.cdl \
    --output docs/a2mc_reference/yaml_wiki_validation_e027a40.md
```

Five dimensions:

| Dim | Check |
|---|---|
| A | Parameter coverage in wiki — every YAML parameter has a wiki page |
| B | Mechanism coverage in wiki — every YAML mechanism has a wiki section matching its name |
| C | Output reference validity — every `affects:` output appears in the CDL |
| D | Code-reference resolution — every `code_reference` (`File::routine`) resolves at source |
| E | Citation freshness sample — spot-check `calibration_notes` citations |

**Don't run Step 2 if Step 1 is Red.** A Step-2 "BOTH found" verdict is meaningless when the underlying wiki claim was hallucinated.

### Step 3 (optional) — RAG profile diff

Question answered: "how does this milestone's RAG compare to a reference (e.g., the previous milestone)?"

```bash
# Example (api-31-0 vs api-43-1)
python tools/rag_diff.py \
    --profile-a-graph rag/data/<reference-graph>.json \
    --profile-a-wiki  docs/fates-knowledge-base/fates-codebase-wiki-e85d997 \
    --profile-a-param docs/fates-knowledge-base/fates_params_info.cdl \
    --profile-a-name  api-31-0 \
    --profile-b-graph rag/fates_knowledge_graph.json \
    --profile-b-wiki  docs/fates-knowledge-base/fates-codebase-wiki-e027a40 \
    --profile-b-param docs/fates-knowledge-base/fates_params_info_e027a40.json \
    --profile-b-name  api-43-1 \
    --output docs/a2mc_reference/rag_diff_api-31-0_vs_api-43-1.md
```

Four dimensions: nodes, edges, params, mechanisms. Adapter-kit users skip this step on a first build (no reference profile yet).

---

## Verdict scheme

All three validators use the same banding:

- **Green** — every dimension ≥ 90% pass
- **Yellow** — any dimension 70–90%
- **Red** — any dimension < 70%

Reports are Markdown tables with side-by-side dimension scores. Stack-readable when run in order.

### Triage discipline

Don't chase every line item. Categorize findings before fixing:

| Category | Action |
|---|---|
| Real fabrication (e.g., `PRTMyHypothesisMod.F90`, dead routines) | Fix immediately — wiki rewrite or YAML refinement |
| Validator false positive (regex hit on derived-type, namelist flag, filename) | Note in the report's "false-positive classes" section; queue validator improvement |
| By-design scope mismatch (e.g., FATES wiki cites ELM-side file) | Either repath the citation or move the section to the other model's wiki |
| Renamed at this commit | Cross-reference upstream commit log; update the wiki/YAML to the new name |

The Phase 3.5 / 3.6 / 3.7 dev logs on `elm-fates_version_association` show this triage in practice. Worth reading once.

---

## Common recipes

Patterns that recur during a milestone bump.

### Recipe V1 — Wiki regen, validate, patch fabrications

When wiki regen subagents produce hallucinated content. Workflow:

1. Run Step 1 (`codebase_wiki_validator`).
2. Open the report; sort findings by Dim 5 (module-file presence) — most damning class.
3. For each missing module file, decide: rename in wiki, or escalate to wiki-rewrite subagent.
4. For Dim 1 dead citations, repath or remove.
5. Re-run Step 1; aim for Yellow or Green before proceeding to Step 2.

### Recipe V2 — Curated YAML drift after model bump

When YAML still references prior-commit parameter names or routines. Workflow:

1. Run Step 2 (`yaml_wiki_validator`).
2. Cross-reference Dim A "wiki-absent parameters" against the new param file — these are usually renames (e.g., `fates_cnp_km_nh4` → `fates_cnp_eca_km_nh4`).
3. Cross-reference Dim D "code-reference resolution" failures — usually module renames.
4. Apply Recipe G2 from `graphrag_curated_yaml_roadmap.md` for the YAML edits.
5. Re-run Step 2; Dim D should improve from "FILE_ONLY" to "BOTH_FOUND" for routines that exist.

### Recipe V3 — Suspected RAG regression

When a milestone build feels off compared to a known-good prior build. Workflow:

1. Run Step 3 (`rag_diff`).
2. Look at the "removed nodes" / "removed edges" tables — unexpectedly large = something dropped.
3. Look at the "added nodes" / "added edges" tables — unexpectedly large = something duplicated or mis-categorized.
4. The expected diff for a clean version bump is "small reorder, a handful of renames." Anything larger needs a Step-1 / Step-2 root-cause check.

---

## What's not covered (deferred)

Two checks worth keeping on the roadmap but not yet built:

| Gap | Why deferred |
|---|---|
| Param-file ↔ source consistency | Lower hit rate — only matters when source registers parameters that aren't in the JSON, or vice versa. Build when a future bump shows this drift. |
| End-to-end RAG retrieval smoke tests (canned query → expected-chunk assertions) | Requires curating an expected-answers fixture. High up-front effort; better as a per-model test suite than a generic tool. |

If you build either, follow the same `tools/<name>_validator.py` naming convention and add a section here.

---

## Worked example: api-31-0 → api-43-1 milestone bump

The first end-to-end run of this workflow happened on `elm-fates_version_association` during the FATES api-31-0 → api-43-1 + ELM 60d9aad → d40b843 paired regen. Outcome:

| Step | Tool | Verdict | Patch pass | Final state |
|---|---|---|---|---|
| 1a | `codebase_wiki_validator` (FATES) | Red (Dim 4 false positives) | Triaged; queued validator improvements | Yellow after triage |
| 1b | `codebase_wiki_validator` (ELM) | Yellow (routine heuristic) | Triaged; queued validator improvements | Yellow |
| 2 | `yaml_wiki_validator` (FATES) | Red → Yellow → Yellow | Phase 3.5 (rename phantoms) + Phase 3.6 (refactor code_references) | Yellow (3 mechanisms FILE_ONLY by design) |
| 3 | `rag_diff` (api-31-0 vs api-43-1) | Within expected drift | n/a | Documented in `rag_diff_api-31-0_vs_api-43-1.md` |

Reports: `docs/a2mc_reference/wiki_source_validation_*_e027a40.md`, `yaml_wiki_validation_e027a40.md`, `rag_diff_api-31-0_vs_api-43-1.md`. Session logs: `memory/dev_logs_fatesversionassociation/20260427[a-c]_*.md`.

The whole pass took about half a working day for two paired wikis (FATES + ELM) plus YAML refinement. Re-runs after fixes are seconds each. Budget similarly for an adapter-kit first build.
