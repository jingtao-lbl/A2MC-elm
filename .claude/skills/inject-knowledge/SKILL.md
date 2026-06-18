---
name: inject-knowledge
description: Inject a human-originated domain fact (a discovery, a parameter insight, a mechanism/relationship) into A2MC's curated knowledge so the calibration agent surfaces it — placing it correctly across the up-to-three channels (site discoveries.json, generic parameters.json, curated_relationships.yaml), validating, and rebuilding the graph. Use when the user says "add this finding/parameter knowledge to A2MC's AI", "inject the X discovery into the KB", "make the agent aware of X", "author a curated relationship for X", or wants a manuscript/literature insight to reach the reasoning pipeline. This is the HUMAN-originated counterpart to curate-knowledge (which promotes run-originated proposals); both are Tier-3 curated writes and you (the human-in-the-loop) own the truth call. Distilled from graphrag_curated_yaml_roadmap.md + dev log 20260519d (the clumping_index injection).
modes:
  requires_fates: false
  nutrient_pathway: any
  scope: [rag]
  summary: "Inject curated domain knowledge via the YAML overlay; model-agnostic."
---

# Inject Domain Knowledge into the Curated KB

This is **step 3** of the knowledge-base pipeline and a Tier-3 **curated write** — the same
class the v2.90 write gate protects (`20260612d`). It is **judgment-scaffolding, not
automation**: the skill does not decide whether a fact is true or belongs in the KB. **You
do.** It makes sure that *once you've decided*, the fact lands in the right channels, clears
the validation gates, and reaches every trigger path — the mechanics that fail silently.

> **Why the discipline matters.** The curated KB shapes the AI's diagnoses. The May 2026
> contamination (`20260519a`) was 70 unvetted entries — including `do_not_repeat` rules that
> forbade the AI's own best fixes. A wrong injection here is worse than no injection. Hold a
> human-originated fact to the **same bar** `curate-knowledge` holds a run-originated one.

## Step 0 — the truth call (human, before any file edit)

Before injecting, satisfy yourself — and state the basis in the entry's `references`:

- **Is it actually true / supported?** A site finding needs the run+figure+ana_log it came
  from; a mechanism claim needs RAG / `docs/fates-knowledge-base/` or primary literature.
  Do **not** inject a plausible-sounding guess — that is the exact contamination failure mode.
- **Is it already in the KB?** Grep `discoveries.json` / `parameters.json` / the YAML. Don't
  duplicate or let a weaker entry shadow a better-established one.
- **Scrutinize any `do_not_repeat`.** Highest-risk field — inject "never do X" only if X is a
  demonstrated dead end, not one failed attempt.
- **Set `verified` honestly.** Default **`verified: false`** unless the fact is independently
  confirmed; flip to `true` only on real evidence. Pick a `confidence` you can defend.

If you can't clear Step 0, stop — the right outcome may be "don't inject yet."

## Step 1 — pick the channels (not every fact needs all three)

A single fact reaches the agent through up-to-three independent trigger paths. Inject into
each channel the fact actually belongs in; **missing an applicable channel means that
trigger path never surfaces it** (the `20260519d` clumping_index fact needed all three).

| Channel | File | Inject when the fact is… | Trigger path it feeds |
|---|---|---|---|
| **Site discovery** | `use_cases/<site>/memory/gained_knowledge/discoveries.json` | a site-specific finding / mechanism observed in runs | `MemoryManager.get_relevant_context()` matches its `affects` against `failing_targets` (Phase 3/4/6) |
| **Generic parameter** | `memory/gained_knowledge/parameters.json` (under the `"parameters"` key) | knowledge about a specific parameter — bounds, interpretation, asymmetry, what it's a calibration lever for | `ReasoningModule.query()` when that parameter is in the call's `parameters` arg |
| **Curated relationship** | `rag/data/curated_relationships.yaml` | a mechanism or parameter→output relationship the RAG/graph should surface semantically | ChromaDB semantic search + graph traversal (after a rebuild) |

## Step 2 — channel A: site discovery JSON

Add one entry keyed by a descriptive `snake_case` name (schema matches existing entries):

```json
"clumping_index_overstory_radiation_anomaly": {
  "source": "curated",
  "confidence": 0.85,
  "verified": false,
  "date_added": "2026-06-17T00:00:00",
  "description": "...",
  "mechanism": "...",
  "affects": ["FATES_GPP_PF", "FATES_LEAFC_PF", "FATES_MORTALITY_CSTARV_CFLUX_PF"],
  "affects_pfts": [9],
  "implications": ["..."],
  "parameters_involved": ["fates_rad_leaf_clumping_index"],
  "do_not_repeat": [],
  "references": ["memory/ana_logs/<the log>", "<source.F90 or paper>"]
}
```

`affects` must be **real output variable names** (the matching key) — check the output CDL.

## Step 3 — channel B: generic parameter JSON

Add under `["parameters"]["<fates_name>"]`:

```json
"fates_rad_leaf_clumping_index": {
  "type": "...", "fates_name": "fates_rad_leaf_clumping_index",
  "official_dimension": "fates_pft",
  "physically_meaningful_range": [..],
  "biological_interpretation": "...",
  "mechanism": "Canopy_Radiation_Extinction",
  "calibration_lever_for": ["FATES_GPP_PF", ...],
  "asymmetry_warning": "understory PFT's own clumping is inert; only canopy-PFT clumping matters",
  "added": "2026-06-17", "added_from": "memory/ana_logs/<log>"
}
```

The `asymmetry_warning`-style caveat is the highest-value field — it's what stops the agent
tuning a parameter that can't move the target.

## Step 4 — channel C: curated YAML (up to three subsections)

A relationship fact often needs entries under **all three** YAML sections so both retrieval
modes find it:

- **`categories:`** — add the parameter under its category (create the category if new).
- **`mechanisms:`** — `description`, `code_reference` (`Module.F90::routine (FATES api-31)`),
  `doc_reference`, `parameters: [...]`, `affects: [...]`, multiline `notes: |` (formula,
  caveats, the site finding with an ana_log cross-ref).
- **`parameters:`** — `category`, `controls: [...]`, `affects: [...]`, `related_to: [...]`,
  multiline `calibration_notes: |`.

**Two YAML footguns:** (1) `related_to` is **not** auto-bidirectional — add the reverse
entry too, or graph traversal misses it. (2) Every parameter/output you reference must exist
in the param file / output CDL, or the graph builder **silently drops that edge**
(`graph_builder.py:414`, watch for `skipped edge: endpoint not found`).

## Step 5 — validate every file you touched (before commit, before rebuild)

```bash
PY=/Library/Frameworks/Python.framework/Versions/3.10/bin/python3
$PY -c "import json; json.load(open('use_cases/Kougarok/memory/gained_knowledge/discoveries.json'))"
$PY -c "import json; json.load(open('memory/gained_knowledge/parameters.json'))"
$PY -c "import yaml; yaml.safe_load(open('rag/data/curated_relationships.yaml'))"
# Memory smoke test — the new discovery surfaces for its targets:
$PY -c "from memory import MemoryManager; m=MemoryManager('use_cases/Kougarok/memory/gained_knowledge'); print(m.get_relevant_context(failing_targets=['FATES_GPP_PF']))"
```

## Step 6 — rebuild the graph + validate the chain

YAML edits don't reach the agent until the graph is rebuilt. This is a graph-only rebuild
(vector index unchanged) — see the **`rebuild-rag`** skill:

```bash
$PY scripts/build_rag_index.py --rebuild --graph-only --test
# then confirm the new node is retrievable:
$PY -c "from rag import HybridRetriever; r=HybridRetriever(auto_build=False); print(r.get_targeted_context(param_names=['fates_rad_leaf_clumping_index'])[:1200])"
```

If you added or renamed YAML relationships, run **`validate-rag-chain`** Step 2
(`yaml_wiki_validator`) — it catches phantom params (in YAML, not in the param file) and
unresolved `code_reference`s.

## Step 7 — record it

Note what you injected, into which channels, and the evidence basis — a dev log if
substantial (the `log` skill), a one-line note otherwise. The curated JSONs are hand-vetted
manuscript knowledge (CLAUDE.md Rule 3); the audit trail matters as much as for
`curate-knowledge`.

## Notes

- **Pairs with `curate-knowledge`:** that skill promotes *run-originated* proposals the
  autonomous agent staged; this skill injects *human-originated* facts. Same curated stores,
  same judgment bar, opposite origin.
- **Branch fit:** unlike the other KB-build skills, this one **is** routinely useful on
  a version-pinned manuscript branch (e.g. a Kougarok-facing clumping-index injection). The
  api-31-0 RAG is the manuscript-reproducibility anchor, so keep injections additive and
  evidence-backed.
- Authoring/validation recipes (G1–G4): `docs/a2mc_reference/graphrag_curated_yaml_roadmap.md`.

## Changelog

- 2026-06-17: Initial version — distilled from graphrag_curated_yaml_roadmap.md + dev log 20260519d (clumping_index injection).
- 2026-06-17: Verify-pass fix — removed invalid `phase=` kwarg from the Step 5 memory smoke-test command (TypeError on copy-paste).
