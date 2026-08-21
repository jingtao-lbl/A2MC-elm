---
name: validate-rag-chain
visibility: public
category: kb-build
description: Validate the source→wiki→curated-YAML→RAG chain before shipping, using the three A2MC validators in dependency order. Use when the user asks to "validate the wiki/RAG", "check the wiki against source", "did the rebuild regress", "check for hallucinations before merging the wiki", "validate the curated YAML", or after generating a wiki / editing curated_relationships.yaml / rebuilding the RAG at a new commit. Runs codebase_wiki_validator (wiki↔source) → yaml_wiki_validator (YAML↔wiki+param+output) → rag_diff (profile vs reference), applies the Green/Yellow/Red banding and the fabrication-vs-false-positive triage. Distilled from docs/a2mc_reference/rag_validation_workflow.md.
modes:
  requires_fates: false
  nutrient_pathway: any
  scope: [rag]
  summary: "Validate the RAG chain (3 validators); model-agnostic."
---

# Validate the RAG Chain (3 validators, in order)

Full playbook, dimension tables, and the worked api-31-0→api-43-1 example are in
**`docs/a2mc_reference/rag_validation_workflow.md`**. This skill is the run-order +
triage runbook.

> **Why.** The chain `source → wiki → curated YAML → RAG → AI calibration` has four hops; a
> hallucination at any hop propagates downstream silently. The three validators close every
> edge. Run them **in dependency order and fix any Red before the next tier** — a Step-2
> "BOTH found" verdict is meaningless if the Step-1 wiki claim it rests on was fabricated.

## When to run

1. **Before canonizing a new/regenerated wiki** (the `generate-codebase-wiki` subagents can
   hallucinate — validate before it becomes the source of truth).
2. **After a curated-YAML edit** (hand edits drift from the wiki + param file).
3. **After a RAG rebuild at a new commit** (diff vs the prior milestone catches regressions).

A one-line YAML tweak doesn't need the full sweep — re-run only the affected layer.

## Step 1 — wiki vs source  (`codebase_wiki_validator.py`)

"Does the wiki cite real files, real line numbers, real routines, real parameter names?"

```bash
python tools/codebase_wiki_validator.py \
    --wiki   docs/fates-knowledge-base/fates-codebase-wiki-<HASH> \
    --source <path-to-source-checkout-at-that-commit> \
    --param-file docs/fates-knowledge-base/fates_params_info_<HASH>.json \
    --output docs/a2mc_reference/wiki_source_validation_fates_<HASH>.md
```

Five dimensions: (1) file-citation existence, (2) line-bound validity, (3) routine
declaration presence, (4) parameter-name validity, (5) module-file presence.

**Triage Dim 4 carefully** — it has a known false-positive rate because the wiki uses the
param prefix (`fates_*`) for derived-type names, namelist flags, and filenames. Read the
report's "wiki-only parameter names" table before calling them fabrications. **Dim 5 is the
strongest signal** — a `PRTMyHypothesisMod.F90`-style placeholder module is unambiguously
fake. Get to Yellow/Green here before Step 2.

## Step 2 — YAML vs wiki + param + output  (`yaml_wiki_validator.py`)

"Are the curated relationships consistent with the wiki + param file + output CDL at this
commit?" **Skip if Step 1 is Red.**

```bash
python tools/yaml_wiki_validator.py \
    --yaml rag/data/curated_relationships.yaml \
    --wiki docs/fates-knowledge-base/fates-codebase-wiki-<HASH> \
    --param-file docs/fates-knowledge-base/fates_params_info_<HASH>.json \
    --output-cdl docs/fates-knowledge-base/elm_fates_output_info_<HASH>.cdl \
    --output docs/a2mc_reference/yaml_wiki_validation_<HASH>.md
```

Five dimensions: (A) every YAML parameter has a wiki page, (B) every YAML mechanism has a
matching wiki section, (C) every `affects:` output is in the CDL, (D) every `code_reference`
(`File::routine`) resolves at source, (E) `calibration_notes` citation freshness sample.
Dim A "wiki-absent parameters" and Dim D failures are usually **renames at the new commit**
(`fates_cnp_km_nh4` → `fates_cnp_eca_km_nh4`) — cross-reference the param file / upstream
commit log and fix the YAML (the `inject-knowledge` skill's edit conventions apply).

## Step 3 (optional) — RAG profile diff  (`rag_diff.py`)

"How does this milestone's RAG compare to a known-good reference?" Skip on a first build
(no reference profile yet).

```bash
python tools/rag_diff.py \
    --profile-a-graph <reference-graph>.json --profile-a-wiki <ref-wiki> \
    --profile-a-param <ref-param> --profile-a-name <ref-name> \
    --profile-b-graph rag/fates_knowledge_graph.json --profile-b-wiki <new-wiki> \
    --profile-b-param <new-param> --profile-b-name <new-name> \
    --output docs/a2mc_reference/rag_diff_<ref>_vs_<new>.md
```

Four dimensions: nodes, edges, params, mechanisms. **Expected diff for a clean version bump
is "small reorder + a handful of renames."** Unexpectedly large removed-nodes/edges =
something dropped; large added = something duplicated or mis-categorized → root-cause back
in Step 1/2.

## Step 4 (post-rebuild) — index coverage self-test  (`check_rag_coverage.py`)

The three validators above check the *source→wiki→YAML→graph* chain; they do **not** catch a whole
knowledge base silently missing from the **vector index** (the 2026-07-05/06 ELM-wiki-absent bug — the
retriever answered FATES-only with no error). After a rebuild, run:

```bash
python tools/check_rag_coverage.py --profile <profile>   # docs/33 §3c
```

It asserts every expected `kb_source` is present above a floor and canary wiki files appear (config:
`rag/canary_queries.yaml`). Metadata-only, no embedding model; ERRORs if a `kb_source` count is 0.

## Verdict scheme & triage

Banding (all three validators): **Green** ≥90% every dimension · **Yellow** any dim 70–90% ·
**Red** any dim <70%. Don't chase every line item — categorize first:

| Category | Action |
|---|---|
| Real fabrication (placeholder module, dead routine) | fix now — wiki rewrite or YAML refinement |
| Validator false positive (regex hit on derived-type / namelist / filename) | note in report's false-positive section; queue validator improvement |
| By-design scope mismatch (FATES wiki cites ELM-side file) | repath the citation or move the section to the other model's wiki |
| Renamed at this commit | cross-ref upstream commit log; update wiki/YAML to the new name |

A real first-pass outcome (api-31-0→api-43-1): Step 1 Red→Yellow after triaging Dim-4 false
positives; Step 2 Red→Yellow after fixing renamed phantoms; Step 3 within expected drift.
Whole pass ~half a working day for a coupled pair; re-runs after fixes are seconds.

## Notes

- Reports are Markdown tables, stack-readable when run in order; name them
  `tools/<name>_validator.py` → `docs/a2mc_reference/<check>_<HASH>.md`.
- This is **step 4** of the adapter-kit pipeline: `generate-codebase-wiki` →
  `rebuild-rag` → `inject-knowledge`/curated YAML → **validate**. Recipes V1 (patch wiki
  fabrications), V2 (curated-YAML drift after a bump), V3 (suspected regression) in the
  roadmap.
- Not yet covered (deferred): param-file↔source consistency, end-to-end retrieval smoke
  tests. If you build either, follow the `tools/<name>_validator.py` convention and add a
  section to the roadmap.
- Branch note: this is forward-dev tooling (milestone bumps live on `main`/adapter-kit);
  on a version-pinned manuscript branch its main use is a sanity pass after a curated-YAML
  injection + `--graph-only` rebuild.

## Changelog

- 2026-06-17: Initial version — distilled from docs/a2mc_reference/rag_validation_workflow.md.
