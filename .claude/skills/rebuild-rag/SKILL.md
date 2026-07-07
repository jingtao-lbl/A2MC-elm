---
name: rebuild-rag
description: Rebuild or repair the A2MC RAG/GraphRAG index (ChromaDB vector store + NetworkX knowledge graph) that the ReasoningModule queries before every Claude API call. Use when the user asks to "rebuild the RAG", "reindex", "bump the wiki to a new commit", "the RAG/index stopped working / returns nothing / returns stale content", "I edited the curated YAML — refresh the graph", "add a model to the RAG", or after any edit to a wiki / CDL / curated_relationships.yaml. Codifies the build pipeline + the footguns (the loader pattern-probe symlink trap, --rebuild vs --graph-only, Python 3.10, dropped curated edges, PFT-count env var) distilled from docs/a2mc_reference/rag_build_roadmap.md and the RAG dev logs.
modes:
  requires_fates: false
  nutrient_pathway: any
  scope: [rag]
  summary: "Rebuild/refresh the RAG index; model-agnostic."
---

# Rebuild the RAG/GraphRAG Index

The full reconstruction guide is **`docs/a2mc_reference/rag_build_roadmap.md`** — read it for
the architecture, file inventory, and Recipe 1/2 detail. This skill is the operational
runbook: pick the right rebuild mode, avoid the footguns, verify the result.

> **Always use Python 3.10** for anything RAG-related:
> `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3` (the python.org install).
> Homebrew 3.12 fails on PEP-668. Call it `$PY` below.

## Step 0 — classify the task (decision tree)

| What changed | Mode | Command |
|---|---|---|
| Edited `rag/data/curated_relationships.yaml` only | graph-only | `$PY scripts/build_rag_index.py --rebuild --graph-only --test` |
| Added/changed CDL definitions (`fates_params_info.cdl`, output CDL) | full rebuild | `$PY scripts/build_rag_index.py --rebuild --test` |
| Wiki content at a **new commit** (e.g. e85d997 → e027a40) | **Recipe 1** (below) | symlink first, then full rebuild |
| A **new model** entirely (EcoSim, ReSOM, …), or a full from-nothing build | use **`build-rag-from-scratch`** | that orchestrator owns wiki-gen + parser/loader registration; this skill is only the (re)index step it calls |
| Index "just stopped working" | diagnose first (Step 4) | usually Python version or empty `chroma_db/` |

**Never** rely on an incremental add for a content change: `add_documents()` dedupes by
`chunk_id` and silently SKIPS existing entries (`vector_store.py:110-127`). A wiki edit
that preserves chunk count but changes text is ignored unless you `--rebuild`.

## Step 1 — standard rebuild (current tree, no commit bump)

```bash
$PY scripts/build_rag_index.py --rebuild --test
```

Reads `docs/fates-knowledge-base/` + `docs/elm-knowledge-base/`, parses the two CDLs,
overlays `rag/data/curated_relationships.yaml`, writes `rag/chroma_db/<profile>/` +
`rag/graphs/<profile>.json`. Local, ~2 min, $0 (embeddings are local
sentence-transformers, not an API call).

## Step 1b — Recipe 1: bumping the wiki to a new commit-pinned tree

The **#1 footgun.** The loader probes wiki dir names and **stops at the first match**
(`rag/loader.py:366-371`), so a bare `--rebuild` keeps indexing the *legacy* tree even
though a commit-pinned `fates-codebase-wiki-e85d997/` exists. The build looks like it
succeeded but indexes the wrong content. Redirect with a symlink, archive the old
artifacts for rollback, then rebuild:

```bash
cd docs/fates-knowledge-base
git mv fates-codebase-wiki fates-codebase-wiki-legacy        # if a bare dir is in the way
ln -s fates-codebase-wiki-e85d997 fates-codebase-wiki        # point the probe at the new tree
cd -
mv rag/chroma_db rag/chroma_db.legacy_$(date +%Y%m%d)        # rollback safety
mv rag/fates_knowledge_graph.json rag/fates_knowledge_graph.json.legacy_$(date +%Y%m%d)
$PY scripts/build_rag_index.py --rebuild --test
```

Pair a wiki bump with a **CDL refresh** — the CDLs are hand-managed, not auto-regenerated
from source (`ncdump -h fates_params_default.nc > fates_params_info.cdl` against the FATES
build matching the wiki commit). See Recipe 1 in the roadmap for the full sequence.

## Step 2 — verify (don't trust a silent success)

```bash
$PY -c "
from rag import HybridRetriever
r = HybridRetriever(auto_build=False)
print(r.get_stats())
print(r.get_targeted_context(param_names=['fates_cnp_pid_kp'],
      output_names=['FATES_LEAFC'], mechanisms=['PID_Controller'], pft=10)[:1500])
"
```

- **Stats sanity:** current api-31-0 build is ~2,581 vector docs, ~1,295 graph nodes, ~2,197 edges (CLAUDE.md §RAG/GraphRAG).
  168 nodes means you ran a pre-Feb-2026 build — `--rebuild` again. 0 docs means the wiki
  path didn't match (the Step 1b footgun).
- **Content spot-check after a bump** (these are the claims that were wrong in the stale
  Feb-2026 index): phenology defaults `-68 / 638 / -0.01`, transpiration units in `mm`,
  and the phantom `fates_cnp_nfix` parameter **absent**. Open a matched `.md` and confirm
  it's the new commit's content, not legacy.
- **Coverage self-test (docs/33 §3c):** `$PY tools/check_rag_coverage.py --profile <profile>` —
  asserts every expected `kb_source` is present above a floor and canary wiki files appear.
  This catches the ELM-wiki-absent bug class (a whole KB silently dropped: `kb_source 'elm' = 0`).
  Update `rag/canary_queries.yaml` floors after a legitimate rebuild; the *presence* invariant should hold.

## Step 3 — graph-only rebuild after a curated-YAML edit

```bash
$PY scripts/build_rag_index.py --rebuild --graph-only --test
```

Skips re-embedding (the vector index is unchanged) — seconds, not minutes. Watch the
build log for `skipped edge: endpoint not found`: a curated edge whose parameter/output
isn't in the CDL is **silently dropped** (`graph_builder.py:414`). Either add the endpoint
to the CDL or use the YAML curated-only fallback. (To inject a *new fact* across all three
memory channels before rebuilding, that's the `inject-knowledge` skill — this skill only
re-indexes what's already authored.)

## Step 4 — when the index "just stopped working"

1. Wrong Python (must be 3.10 from python.org). 2. `rag/chroma_db/` exists and non-empty.
3. `rag/graphs/<profile>.json` exists. 4. `--test` the existing index. 5. Still
broken → `--rebuild`. Cross-CWD failures (Perlmutter) trace to path resolution
(`rag/hybrid_retriever.py` `_resolve_path`) and the NetworkX `edges="links"` JSON-key
compat fix (`20260204a`).

## Notes

- **Other knobs:** `A2MC_PFTS` sets the PFT list (defaults to Kougarok `[7,9,10]`) — set
  `A2MC_PFTS=1,2,...,12` for a non-Kougarok site or graph nodes come out wrong
  (`graph_builder.py` `_resolve_pft_list`).
- **After a commit bump or curated edit, validate the chain** before trusting it — the
  `validate-rag-chain` skill (wiki↔source, YAML↔wiki, profile diff).
- **Where it lives in code:** the roadmap §8 has a grep cheat-sheet for every default path,
  the wiki subdir patterns, the chunk-ID/dedup logic, and the curated-YAML loader.
- Branch note: wiki *bumps* and new-model adds are forward-dev (mostly `main`/adapter-kit);
  on a version-pinned manuscript branch the common use is a `--graph-only` refresh after a
  curated-YAML injection. A pinned (e.g. api-31-0) index is the manuscript-reproducibility anchor
  — don't bump its wiki commit here without reason.

## Changelog

- 2026-06-17: Initial version — distilled from docs/a2mc_reference/rag_build_roadmap.md.
- 2026-06-17: Verify-pass fix — corrected stats sanity figure (~2,700 → ~2,581 docs / ~1,295 nodes) to match the api-31-0 index.
