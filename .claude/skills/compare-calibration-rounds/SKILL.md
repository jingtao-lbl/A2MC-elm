---
name: compare-calibration-rounds
description: Compare A2MC calibration rounds (R1, R2, …) against each other and the validation targets — top-N best-achievable biomass per round, per-target Morris μ* sensitivity, P-pool / cross-regime overlays. Use when the user asks to "compare rounds", "update the multi-round figure", "refresh the R1-RN comparison", "which round is best", "top sensitive parameters per round", or to regenerate any `multiround_*` / cross-round figure after new cases complete. Codifies the multiround bundle pipeline + the footguns (screening contamination, case-name patterns, μ* ranking, param-set mismatch, partial-ensemble caveats).
---

# Compare Calibration Rounds

Cross-round comparison of A2MC calibration rounds: best-achievable biomass per round vs the
validation targets, and Morris μ* sensitivity per round. The canonical bundle lives at
`use_cases/Kougarok/analysis/multiround_top50_sensitivity_20260606/` (self-locating scripts; figures
versioned beside them). Read `README.md` there + `memory/ana_logs/20260606b` (findings) and
`memory/dev_logs/20260606c` (procedure) first.

## When to use

- "Compare the rounds", "which round is best", "update/refresh the multi-round figure".
- "Top sensitive parameters per round" / cross-round sensitivity.
- Regenerating a `multiround_*` figure after new cases complete (e.g. a round's relaunched/added cases).
- P-pool or cross-regime cross-round overlays (same bundle conventions).

## The bundle

```
multiround_top50_sensitivity_20260606/
├── scripts/
│   ├── plot_multiround_top50_overlay.py        # biomass top-50 vs 6 targets (6 panels)
│   ├── plot_multiround_sensitivity_overlay.py  # Morris μ* top params per round (grouped bars)
│   ├── build_Y_from_monthly.py                 # R2..R5 Morris Y matrices from monthly NCs
│   └── build_Y_R1.py                           # R1 (138-param)
├── screening_top50/{R1..RN}/                   # screen_ensemble.py outputs per round
├── sensitivity/{R1..RN}_{leaf,fineroot}/       # morris μ* CSVs + per-round png
├── Y_matrices/                                 # Morris inputs (for sensitivity only)
└── multiround_*.png                            # the comparison figures
```
Also: `tools/compare_rounds.py` for quantitative round-vs-round deltas.

## Pipeline (to refresh a figure after new cases)

1. **Extract** the new cases (all 3 phases if the combined/sensitivity figures are needed):
   production `tools/extract_monthly_variables_FATES.py` (TRANS) or `tools/extract_and_plot_selected_cases.py`
   (`extract`, any phase via `--phase/--year-start/--year-end`, reuses `process_case`).
2. **Re-screen** the round: `phases/phase2_screening/screen_ensemble.py --data-dir <round extract dir>
   --top-n 100 --output-dir screening_top50/<RN>` (source that round's config so
   `A2MC_CASE_NAME_PATTERN` is right). **⚠️ see footgun #1 — filter out-of-range cases first.**
3. **Biomass figure:** `python scripts/plot_multiround_top50_overlay.py` (reads `screening_top50/*/`).
4. **Sensitivity** (only if refreshing μ*): rebuild Y (`build_Y_from_monthly.py`) → Morris
   (`phases/phase1_exploration/morris_sensitivity_analysis.py`) → `plot_multiround_sensitivity_overlay.py`.

## Footguns (the load-bearing part)

| # | Footgun | Guard |
|---|---|---|
| 1 | **CROSS-round screening must cap the case number.** `screen_ensemble.py` matches `PtCNPEn(\d+)<suffix>_TRANS` for any digits, so out-of-Morris-range experiment cases (e.g. H1 clumping #5001/5005/5006) sitting in a shared extract dir get swept in and can rank as "best". (This made the R5 biomass figure briefly show best **#5001** instead of **#1304**, 2026-06-10.) | Pass **`screen_ensemble.py --max-case-num <ensemble max>`** (e.g. `4890`) for cross-round comparison — it drops out-of-range cases and prints how many. Verify `# Sets:` in `_results.txt` = expected. **NOTE:** leave `--max-case-num` UNSET for a single round's own whole-ensemble summary graph — those legitimately exceed the Morris size (e.g. R3 + reruns = 4941). |
| 2 | **Read `_results.txt` Sim_ columns + `screening_result.json` `best_case_num`, NOT `screening_top50_indices.txt`.** The indices file mislabels case numbers on partial ensembles and isn't always rewritten (can be stale). | The overlay scripts already do this; don't "trust" the indices file. |
| 3 | **Morris CSV `rank` column is by `mu`, not `mu_star`.** | Re-sort by `mu_star` (Morris importance) for selecting/ranking top params. |
| 4 | **Sensitivity file prefix is unreliable.** Older runs (R1–R4, 6/6) named *both* organs `morris_leafbiomass_*` (the `--output-var` quirk); newer runs (R5, 6/10) correctly use `morris_finerootbiomass_*` for fineroot. So a dir can hold either prefix. The **directory** `{Rn}_{organ}` is the source of truth for the organ; content is correct per dir. | Map organ by directory, never by filename prefix. Glob `morris_*PFT{X}_2*.csv` (matches both); ensure one file per PFT so `sorted()[-1]` is unambiguous. |
| 5 | **Param-set mismatch across rounds.** R1 used 138 params; R2+ used 162. | Align on shared names; show "no bar"/blank for params absent in a round; note it in the caption. |
| 6 | **Partial-ensemble rounds.** Screening/ranking is valid on a partial ensemble (dead cases get finite high cost), but **Morris μ* is NOT reliable** until the ensemble is reasonably complete. | Include a partial round in the biomass top-N figure (label it), but **exclude it from the sensitivity overlay** until a full Y-rebuild + Morris re-run. |

## Conventions

- **Filenames** embed round + axis-mode + case count: `R{N}_{TRANS,combined}_{count}cases_ensemble.png`,
  `multiround_top50_biomass_vs_6targets_R1-RN.png`, `multiround_top_sensitive_params_bars_R1-RN.png`
  (per `feedback_plot_filename_convention`).
- **Biomass overlay bands:** grey ±20% acceptance band + light-blue ±1 SD observation band (SD often
  exceeds the mean → floor the lower SD edge at 0). SD values from `validation_targets_leafroot.txt`.
- **Whole-ensemble** (not top-N) cross-round plots use `tools/plot_ensemble_cases.py` +
  `regen_ensemble_milestone_plot.sh` (different from this bundle's top-50 overlay).
- NERSC: scratch (symlink dirs, filtered sets) under `$HOME`/repo `tmp/` only — never `/tmp`,`/scratch`.

## Cross-references

- Worked examples: `memory/dev_logs/20260606c` (procedure), `20260610b` (refresh + H1 catch),
  `memory/ana_logs/20260606b` (findings).
- Tools: `phases/phase2_screening/screen_ensemble.py`, `phases/phase1_exploration/morris_sensitivity_analysis.py`,
  `tools/{compare_rounds,extract_and_plot_selected_cases,plot_ensemble_cases}.py`.
