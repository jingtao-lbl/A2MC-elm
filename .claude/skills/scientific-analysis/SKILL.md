---
name: scientific-analysis
description: Run a manuscript-supporting scientific investigation that ends in a figure + an ana_log — pose a question, pull ensemble/run data, compute the statistic/mechanism, make a figure, cite evidence, and write an ana_log. Use when the user asks to "investigate whether X", "is X correlated with Y", "analyze the mechanism of X", "make a manuscript figure for X", "P-pool / cross-regime / attribution analysis". For a standardized single-round report use summarize-calibration-round; for cross-round figures use compare-calibration-rounds.
modes:
  requires_fates: false
  nutrient_pathway: any
  scope: [analysis]
  summary: "Investigation -> figure -> ana_log workflow; model-agnostic (examples are FATES/Kougarok)."
---

# Scientific Analysis → Figure → ana_log

The interactive agent does the open-ended, manuscript-supporting science that the fixed
calibration loop can't: "is PFT10 P uptake growth-limited or stoichiometric?", "attribute
the R2→R4 change", cross-regime / P-pool investigations. This skill codifies that
workflow so the result is reproducible and properly recorded.

> Use this for *free-form investigation*. For the canned single-round report use
> `summarize-calibration-round`; for cross-round comparison figures use
> `compare-calibration-rounds`. Those are the standardized deliverables; this is the
> exploratory one.

## Step 1 — pose the question precisely + scope the data

State the question as something falsifiable ("P uptake tracks NPP, not leaf stoich"), and
identify exactly what data answers it: which round/ensemble, which variables, which
validation targets, which cases (top-N? all? a contrast pair?). If the question touches a
FATES mechanism, check RAG/GraphRAG / `docs/fates-knowledge-base/` first — don't assert mechanism
from names.

## Step 2 — pull + analyze

Reuse the analysis tooling rather than re-deriving:
- `use_cases/<site>/analysis/` scripts (attribution, contrast, forcing comparison) and
  `tools/plot_ensemble_cases.py` / `tools/extract_ADSP_RGSP_slim.py` for ensemble data.
- Compute the actual statistic (correlation r, attribution, regression) — quote the
  number, don't hand-wave. If a tiny/odd subset is involved, run `diagnose-forensics`
  triage first (is it real or an artifact?).

## Step 3 — make the figure (filename convention)

Save figures under `use_cases/<site>/analysis/` with the **round + axis-mode + case
count** embedded in the name (memory: plot filename convention) — e.g.
`R4_combined_519yr_top50_<topic>.png` — to avoid the `ensemble_biomass_all_cases.png`
ambiguity from past sessions. Figures are gitignored, so the filename is the only durable
pointer.

## Step 4 — write the ana_log (cite explicit evidence)

Write an `ana_log` via the `/log` skill (`/log ana <topic>` → `memory/ana_logs/`). The
load-bearing rule: **every quantitative claim names its figure / statistic / data file
inline**, and a section drawing on several artifacts gets an **"Artifacts this section is
based on"** table. A claim with no cited source is a red flag — find the source or soften
it. Render to PDF with the `markdown-to-pdf` skill if it's a shareable note.

## Step 5 — land the lesson (optional)

If the analysis yields a vetted, generalizable discovery, add it to the curated KB — but
Tier-3 is **interactive-only**, so author it deliberately (an `interactive`-mode
MemoryManager / by hand) or stage + promote via `curate-knowledge`. Do NOT inject an
unverified hunch.

## Notes
- ana_logs are manuscript working notes — tracked on this branch, excluded from public
  sync.
- Pairs with: `diagnose-forensics` (triage odd results), `compare-calibration-rounds` /
  `summarize-calibration-round` (standardized figures), `/log` (the ana_log + supersede
  protocol), `markdown-to-pdf` (render), `curate-knowledge` (land a lesson).

## Changelog

- 2026-06-17: `## Changelog` convention adopted (see .claude/skills/README.md). Earlier history: git log + memory/dev_logs/.
