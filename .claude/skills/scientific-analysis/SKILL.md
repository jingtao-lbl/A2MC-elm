---
name: scientific-analysis
visibility: public
category: calibration
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

**Then resolve the run configuration, before reading any branched model source.** That check above guards against asserting a mechanism from a *name*; this one guards against a different failure — reading a real value correctly and applying it to a branch your run does not execute. ELM/FATES branches on FATES on/off, PARTEH 1 vs 2, CN vs CNP, ECA vs RD, NOCOMP, SPITFIRE, hydraulics and more, and each branch owns its own constants.

```bash
source use_cases/{Model}_{Case}/config/<case>_config.sh   # auto-sources the machine config
python tools/describe_mode.py                             # e.g. "Competition: ON (ECA pathway)"
CASE="$A2MC_E3SM_ROOT/cime/scripts/<case_name>"           # NOT co-located with the run dir
cd "$CASE" && ./xmlquery -value RUNDIR                    # also how you LOCATE the run dir
grep -nE "nu_com|use_fates|hlm_parteh_mode|suplphos" "$RUNDIR/lnd_in"   # ground truth
```

Namelist switches are not in the FATES parameter file (`nu_com` is one), so a parameter-file check returns empty for exactly the switch that selects the branch. Check the pinned wiki (`docs/elm-knowledge-base/elm-codebase-wiki-<elm-commit>/`) before the Fortran — it often states the per-branch split in prose already. **Name the branch whenever a constant reaches a figure, caption or ana_log.** Full rule: memory `feedback_resolve_run_config_before_reading_branched_source`.

## Step 2 — pull + analyze

Reuse the analysis tooling rather than re-deriving:
- `use_cases/<site>/scripts/` scripts (attribution, contrast, forcing comparison) and
  `tools/plot_ensemble_cases.py` / `tools/extract_ADSP_RGSP_slim.py` for ensemble data.
- **For any per-PFT / SZPF extraction in a custom script, use `tools/fates_utils`** — `get_szpf_range()`,
  `extract_pft_data()`, `aggregate_szpf_by_pft()`, `get_pft_index()`, `identify_dimension_level()`. Do
  **not** hand-roll the SZPF (`levscpf`) index: it is **PFT-major** `(pft-1)×nlevsclass`, where
  **`nlevsclass` is file-derived** (`get_n_size_classes(ds)` from `fates_levscls` — 13 in the common
  default but *configurable*, NOT a fixed constant), plus a 0-based/1-based PFT offset. (The FATES wiki's
  `(size_class-1)*numpft+pft` is a known **wiki error** — the source is PFT-major; `fates_utils` encodes
  the correct form.) `fates_utils` is the canonical helper the extract/plot tools use.
- Compute the actual statistic (correlation r, attribution, regression) — quote the
  number, don't hand-wave. If a tiny/odd subset is involved, run `diagnose-forensics`
  triage first (is it real or an artifact?).

## Step 3 — make the figure (conventions + filename)

**Load `plotting` BEFORE the first `savefig`.** This step is where a figure is actually made, and a filename convention says nothing about whether the figure is readable. `plotting` rule 8 (*open the rendered PNG and LOOK at it*) is the only check that catches an overlapping legend or a stats box drawn across the curve — and it cannot catch them once the figure is already in a report.

Save figures under `use_cases/<site>/scripts/` with the **round + axis-mode + case
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

- 2026-08-27: Step 1 (scope the data). Added a **resolve-the-run-configuration step** — a constant read correctly from the run's own input files can still belong to a branch the run never executes, so provenance discipline alone does not catch it. Carries the three-step chain (site config → CIME case dir under `cime/scripts/` → the run dir's `lnd_in`), the note that namelist switches like `nu_com` are absent from the FATES parameter file entirely, and the requirement to name the branch when quoting a constant. Signal: `memory/dev_logs/reflection/20260827a_Reflection_A_Real_Value_From_The_Wrong_Branch.md` — a figure normalised `LABILEP` by the RD-path `smax` in an ECA run, inverting the reading; `git grep -c describe_mode` confirmed both skills mentioned mode resolution zero times, while `tools/describe_mode.py` ran only in the two setup-time skills. Applied under `refine-skill` after PI approval.
- 2026-07-15: Step 2 names `tools/fates_utils` as the canonical per-PFT/SZPF extraction helper (`get_szpf_range`/`extract_pft_data`/`aggregate_szpf_by_pft`/`get_pft_index`) — don't hand-roll the `(pft-1)×13` index in a custom analysis script. Ported from demo `ac4c125`.
- 2026-06-17: `## Changelog` convention adopted (see .claude/skills/README.md). Earlier history: git log + memory/dev_logs/.
