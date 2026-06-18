---
name: generate-codebase-wiki
description: Produce a source-grounded codebase wiki for a model (FATES, ELM, EcoSim, ReSOM, or a new target) by fanning out parallel subagents that read actual source and cite (file:line) — the foundation every downstream A2MC artifact (RAG vector index, knowledge graph, calibration prompts) is built on. Use when the user asks to "generate/build a codebase wiki", "the deepwiki/cursor wiki is wrong — rewrite it", "audit the wiki against source", "bump the wiki to commit X", or "add model Y to A2MC" (wiki is step 1). Picks Workflow A (greenfield) vs B (audit-then-rewrite), enforces the fabrication/citation gates and commit-pinned output convention. Distilled from docs/a2mc_reference/codebase_wiki_generation_roadmap.md and the FATES/ELM/EcoSIM wiki dev logs.
modes:
  requires_fates: false
  nutrient_pathway: any
  scope: [rag]
  summary: "Generate a source-grounded codebase wiki for any model; model-agnostic."
---

# Generate a Source-Grounded Codebase Wiki

Full procedure, universal-context templates, and per-subagent prompts live in
**`docs/a2mc_reference/codebase_wiki_generation_roadmap.md`** — read it before dispatching.
This skill is the decision + dispatch + verification runbook.

> **Why this is the foundation.** The wiki feeds the ChromaDB vector index, the knowledge
> graph, milestone metadata, and ultimately the calibration agent's prompts. *Nothing built
> on top can be more correct than the wiki.* A fabricated routine name propagates silently
> all the way to a calibration recommendation. Treat every claim as suspect until cited.

## Step 1 — choose the workflow

| Situation | Workflow | Why |
|---|---|---|
| New model, no prior wiki | **A — greenfield** | nothing to audit; write from source |
| Auto-generated (deepwiki/cursor) wiki exists but is fabricated | **A — greenfield** (abandon the old one) | fabrications hide fabrications; don't patch incrementally |
| Source-grounded wiki exists, commit bumped **within** an api epoch | **skip** | milestone covers sci drift via param-file sha (`docs/18`) |
| Source-grounded wiki exists, commit bumped **across** api epochs (e.g. api-31-0 → api-43-1) | **B — audit then rewrite** | catch semantic drift (inverted units, fabricated defaults) before re-canonizing |

**A vs B litmus:** if the existing wiki makes *semantic/behavioral* claims that can be
silently wrong (GDD thresholds, MPa↔mm unit inversions, formula direction), audit first
(B). If errors are merely *structural* (wrong filenames, off-by-N line numbers, nonexistent
dirs), greenfield (A) catches them without a separate audit pass.

## Step 2 — stage inputs (read-only)

1. Clone or symlink the source checkout; **`git checkout` the exact commit** you're pinning.
2. Stage the parameter file (CDL/JSON/YAML) if the model has one.
3. Decide topics: **5–10, aligned to source subdirectories**, not editorial taxonomy — so
   "where is X implemented?" maps mechanically to a wiki file. A cross-cutting module goes
   in the topic where it conceptually lives (e.g. FATES `EDMainMod.F90` → core dynamics, not
   biogeochem). Promote a calibration-critical doc to its own topic (FATES
   `advanced/cnp_calibration_guide.md` is its own topic for this reason).

## Step 3 — pilot 2 before fanning out all N

Dispatch **2 subagents on the highest-stakes topics first**, spot-check their output, then
fan out the rest. Skipping this is how "dispatched 10 in parallel and they all produced thin
output" happens. For a coupled pair (ELM+FATES), the topic documenting the **coupling
boundary contract** (ELM `core/`) is the highest-stakes pilot.

## Step 4 — dispatch the subagents (single message, non-overlapping scope)

One subagent per topic, all in **one message** so they run concurrently. Each subagent's
prompt MUST carry the universal-context block (≤15 bold-ordered bullets — longer and they
skim it) and these hard constraints:

- Read **actual source** via Grep/Read; cite **every** claim as `(path/Module.F90:NNN)`
  relative to source root. Use **this commit's** line numbers, never the prior wiki's.
- Cite filenames **verbatim from `ls`** (casing trap: `ELMFatesInterfaceMod.F90` vs
  `elmfates_interfaceMod.F90`).
- Output **150–500 lines per doc**; start with the standard header:
  ```markdown
  **Source pin:** <model> commit <HASH>
  **Scope:** <subsystem>
  **Last verified:** <YYYY-MM-DD>
  ```
- **Workflow B only:** anchor everything to the NEW source; run an explicit **regression
  check** that previously-corrected items weren't quietly rolled back (roadmap step B.6),
  and emit an audit report per topic before the rewrite.

## Step 5 — output convention

Write to a **commit-pinned directory**, never overwriting the old one:

```
docs/<model>-knowledge-base/<model>-codebase-wiki-<COMMIT>/
```

A future bump creates a parallel `-<newhash>/` folder (traceability + rollback; the RAG
loader is later pointed at it via the `rebuild-rag` Recipe-1 symlink). Write a top-level
`index.md`; for a bump, give it a "What changed" section; for an abandoned deepwiki, state
explicitly that it was abandoned and why.

## Step 6 — verify before committing

- **Fabrication spot-check:** sample 3–5 claims per topic — parameter defaults against the
  param file, routine names as real `subroutine`/`function` declarations, cited line ranges
  in-range, and `find` for any directory the wiki names. (Real failures seen: FATES
  `phen_a` claimed `100/100/0.01` vs actual `-68/638/-0.01`; EcoSIM cited
  `build_EcoSIM.sh`/`docker/` files that don't exist upstream.)
- **Header completeness:** `grep -L 'Source pin' docs/<model>-knowledge-base/<…>/*.md`
  must be empty.
- Commit in two commits for Workflow B (audit reports, then rewrite).
- Then run the **`validate-rag-chain`** skill (Step 1, wiki↔source) — it automates the
  citation/line/routine/module checks across the whole wiki and is the real gate before the
  wiki gets canonized.

## Cost & footguns

~30–60 min for Workflow A, ~60–90 min for B, ~2–3 h for a coupled pair; **100K–400K tokens
per subagent** (this dominates the API budget — scope topics so no agent reads more than
~30–40 source files, split oversized subsystems into `_part1/_part2`). Other traps: stale
line numbers (subagent reads the prior wiki instead of new source), topic boundaries
cross-cutting a module so both under-document, over-long universal context. The roadmap's
"Common pitfalls" table is the full list.

## Notes

- Proven examples: `20260410e` (Workflow A, ELM), `20260410d` (Workflow B, FATES audit),
  `20260424g` (Workflow A, EcoSIM new-model). Recipes A1/A2/B1/B2/B3 in the roadmap.
- This is **step 1** of the adapter-kit pipeline → then `rebuild-rag` (Recipe 2 registers
  the model) → `inject-knowledge`/curated YAML → `validate-rag-chain`.
- Branch note: codebase-wiki work is forward-dev — its natural home is `main`/adapter-kit.
  The api-31-0 wikis (`fates-codebase-wiki-e85d997`, `elm-codebase-wiki-60d9aad`) on
  a version-pinned manuscript branch are the reproducibility anchor; regenerate them only
  with explicit reason.

## Changelog

- 2026-06-17: Initial version — distilled from docs/a2mc_reference/codebase_wiki_generation_roadmap.md (Workflow A/B; FATES/ELM/EcoSIM proven examples).
