---
name: plotting
visibility: public
category: authoring
description: Produce a clean, readable, report/manuscript/slide-grade matplotlib figure — right fonts, no legend/annotation overlap, log scale + units, a finding-stating title — and VERIFY it by viewing the saved PNG before shipping. Use when making or fixing any figure — "plot X", "make a figure/chart", "the legend overlaps", "clean up this plot", "make this publication-quality", "the fonts are too small", "the labels are clipped". The HOW-to-make-it-look-right complement to figures>tables>words.
allowed-tools: [Read, Glob, Grep, Write, Edit, Bash]
modes:
  requires_fates: false
  nutrient_pathway: any
  scope: [analysis]
  summary: "Clean, readable, overlap-free matplotlib figures; verify by viewing the PNG. Model-agnostic."
---

# plotting — clean, readable, overlap-free matplotlib figures

A2MC makes claims with figures (figures > tables > words — `<auto-memory>/feedback_figures_over_tables_over_words`).
A figure that overlaps its own legend, uses matplotlib's tiny default fonts, or clips a label **undercuts
the claim it's meant to make**. This skill is the checklist for a report/manuscript/slide-grade figure —
and the one step that actually catches the problems: **look at the rendered PNG.**

## THE LOAD-BEARING RULE — verify by viewing

**After `savefig`, open the PNG and LOOK at it (Read the image file) before you embed it in a report,
ship it, or move on.** Overlaps, clipped labels, unreadable fonts, a legend sitting on the data — **none
of these show up in the code; they show up in the picture.** This is the step that is easy to skip and
the reason figures ship broken. (2026-07-09: an envelope figure's legend sat squarely on top of its own
annotation — the code read fine; only viewing the PNG revealed it. The fix took one look.)

Everything below reduces how often the view-check fails; the view-check is what guarantees it.

## Setup (headless — Perlmutter has no display)

```python
import matplotlib
matplotlib.use("Agg")                     # or export MPLBACKEND=Agg — NEVER plt.show() on a login node
import matplotlib.pyplot as plt
plt.rcParams.update({
    "savefig.dpi": 135,                    # 130–150 is crisp without bloating; >200 rarely needed
    "figure.constrained_layout.use": True, # auto-fits labels/legend — kills most clipping
    "font.size": 11, "axes.titlesize": 13, "axes.labelsize": 12,
    "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.fontsize": 9,
})
# For a SLIDE, scale the four size lines ~1.4× (titlesize 18, labelsize 16, ticks 14, legend 12).
```

## Checklist (each item is a common way the view-check fails)

1. **Readable fonts.** matplotlib's defaults are too small for a report page. Set the sizes above
   explicitly (rcParams, or per-element `fontsize=`). If in doubt, bigger.
2. **No overlap — place the legend in the empty region, not on the data.**
   - Find the empty quadrant first. A **monotonic rising** curve leaves the **upper-left** and
     **lower-right** empty; a **falling** curve leaves upper-right / lower-left; a scatter — the
     sparsest corner. `ax.legend(loc="upper left", framealpha=0.95)`.
   - If nothing inside is clear, put it **outside** the axes and let constrained_layout make room:
     `ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5))`.
3. **No overlap — annotations sit in empty space and POINT to the data.** Never drop text on the curve.
   `ax.annotate("what this point means", xy=(x_pt, y_pt), xytext=(x_clear, y_clear),
   arrowprops=dict(arrowstyle="->"))`. Put the text where there's whitespace; the arrow does the linking.
4. **Log scale when the data spans ≥ ~2 orders of magnitude** (`ax.set_yscale("log")`), and **always put
   units in the axis label** — `"standing plant density (plants/m², log)"`, not `"density"`.
5. **Title states the FINDING, not the axes.** "Option C bounds density ~3 orders lower" beats
   "nplant vs option". The reader should get the point from the title.
6. **Semantic, colorblind-safe colors, used consistently.** red = fail/crash/bad, green = good/fixed/healthy,
   grey = baseline/reference. Avoid red↔green as the *only* distinction; add markers/linestyles too.
   **For A2MC biomass-vs-targets time-series specifically, the colors are FIXED semantic roles — use the
   ensemble figure template below, not free choices.**
7. **Layout + save.** `constrained_layout=True` (set above) or `fig.tight_layout()` before `savefig`;
   both prevent clipped tick labels and titles. Save PNG at the rcParams DPI.
8. **VERIFY BY VIEWING** (the load-bearing rule) — Read the PNG and eyeball it. Fix and re-render until
   it's clean. Only then embed/ship.
9. **Regenerable.** Read data from a durable file (CSV/NetCDF), not hardcoded numbers where avoidable, and
   **ship the plotting script next to the figure** so it can be regenerated. Name the file per
   `<auto-memory>/feedback_plot_filename_convention` (round + axis-mode + case count).

## The A2MC ensemble figure template (biomass vs targets)

Every biomass-vs-targets **time-series** figure in A2MC — the whole-ensemble screening/round plot
(`tools/plot_ensemble_cases.py`), the per-round and cross-round summaries, and the Phase-6 variant-comparison
overlays (`tools/extract_and_plot_selected_cases.py plot`) — shares **one visual language**, so a reader
learns it once and every figure reads the same way. **`tools/plot_ensemble_cases.py` is the reference
implementation: reuse it when you can; when you must hand-roll a related figure, match this scheme rather
than inventing colors.**

**Semantic color scheme (fixed roles — memorize):**

| Element | Style | Meaning |
|---|---|---|
| ensemble cloud | light purple `[0.7, 0.6, 1.0]`, `alpha=0.05`, `lw=0.3` | every case — the achievable envelope |
| **best-fit case** | **red**, `lw=3` | lowest composite error (the figure calls it "Best NRMSE") |
| **most-targets case** | **blue**, `lw=3` | most targets within ±20% — drawn **only when ≠ the red case** |
| baseline / control | **black dashed**, drawn on top | the unchanged reference (variant plots: `--baseline`) |
| observation | black diamond `kd`, `markersize=12` | the field target value |
| ±20% acceptance band | yellow fill / darkorange edge, `alpha=0.4` | the "target met" tolerance |
| obs uncertainty | black `k-` bar, `lw=3` | ±1 SD, when available |
| phase boundaries | gray dashed `axvline` + gray `ADSP`/`RGSP`/`TRANS` labels | spin-up → transient segments |

**Layout + axes.** 3 PFT rows (the calibrated PFTs — Kougarok api-43: PFT10 evergreen shrub, PFT11 deciduous
shrub, PFT12 graminoid) × 2 organ columns (leaf, fineroot); y-unit `Leaf/Fineroot C (g C m$^{-2}$)`; x-label
`Simulation Year (ADSP, RGSP) / Calendar Year (TRANS)` for the `--combined` 519-yr axis, calendar years for
the TRANS-only view; `suptitle` states the best case + its NRMSE.

**zorder law (the observation must stay readable on top of everything).** cloud (50) < best/most-targets
(99–100) < ±20% band (200) < obs uncertainty bar (201) < obs diamond (202). Draw in that order or set
`zorder=` explicitly.

**Footgun — alpha scales with case count.** With ~2,700+ cases the cloud saturates to solid purple at
`alpha=0.5`; `plot_ensemble_cases.py` uses **`alpha=0.05`** so density gradients stay legible. Dial alpha
DOWN as the ensemble grows — but a small **selected-case comparison** (a handful of variant lines) wants the
opposite: solid, opaque colored lines (`alpha=1.0`), one distinct color per variant, control black-dashed.

This template **overrides generic rule 6** for these figures — red / blue / purple / black-dashed are fixed
semantic roles here (best-fit / most-targets / cloud / control), not free color choices.

## Footguns

- **Legend/annotation drawn last but placed by habit** (`loc="best"` or a fixed corner) lands on the data
  when the data shape changes. Re-check placement whenever the data changes — and view the PNG (rule above).
- **`plt.show()` / no Agg backend on Perlmutter** → hang or error on the login node. Always Agg + savefig.
- **`tight_layout` after adding an outside-axes legend** can still clip it; prefer `constrained_layout` +
  `bbox_to_anchor`, and view the result.
- **Tiny default fonts** look fine at the interactive size but are unreadable in an embedded report page —
  set sizes explicitly.
- **Not viewing the PNG** — the #1 footgun. The code compiling ≠ the figure being readable.

## Cross-references

- Why figures at all + captioning: `<auto-memory>/feedback_figures_over_tables_over_words`,
  `feedback_plot_filename_convention`.
- Skills that produce figures (apply these conventions; the biomass time-series ones follow the ensemble
  template above): `phase2-screening` + `phase0-design` + `phase3-diagnosis` + `phase6-refinement` (the
  in-loop ensemble/variant figures), `offline-testing-workflow` (variant comparison plots),
  `scientific-analysis`, `summarize-calibration-round`, `compare-calibration-rounds`. Reference
  implementation of the template: `tools/plot_ensemble_cases.py`. Rendering the doc that embeds them:
  `markdown-to-pdf`. The report that embeds them: `write-report`.

## Notes

- **Branch fit:** generic matplotlib conventions — applies on any branch and any model configuration.

- **Reciprocal skills:** `phase0-design`, `phase2-screening`, `phase3-diagnosis`, `phase6-refinement`, `scientific-analysis`, `summarize-calibration-round`, `compare-calibration-rounds`, `offline-testing-workflow`, `write-report`, `markdown-to-pdf`
  Each of these makes or embeds figures, so each must name `plotting` back. `tools/check_skill_registry.py::reciprocity_check` enforces it: a one-directional claim is invisible from the side that should load the skill, which is how six of these produced figures without rule 8 ever running.

## Changelog

- 2026-07-16: Added **"The A2MC ensemble figure template (biomass vs targets)"** — the fixed semantic color
  scheme (purple cloud / red best-fit / blue most-targets / black-dashed control / black obs diamond / yellow
  ±20% band / gray phase boundaries), the 3-PFT×2-organ layout + `g C m$^{-2}$` units, the zorder law (obs on
  top), and the alpha-scales-with-case-count footgun, with `tools/plot_ensemble_cases.py` as the reference
  implementation; rule 6 defers to it. Cross-refs name the ensemble-figure-producing skills. Ported from demo
  `e247330`; PFT layout labels adapted to api-43 (10/11/12) — main's `plot_ensemble_cases.py` carries the same
  style constants (verified).
- 2026-07-09: Ported to `main` from demo `5ef9cc7` (v3.13) — distilled from the R5 mass-balance report
  figures (demo branch), where a legend-on-annotation overlap was caught only by viewing the rendered PNG.
  The "verify by viewing" step is the load-bearing rule. Added main's `modes:` block.
