---
name: summarize-calibration-round
description: Produce a one-round calibration summary — whole-ensemble biomass graphs (combined 519-yr axis + TRANS), an evaluation report (best case, #targets met, per-target biomass vs ±20%/±SD bands), and a Morris μ* sensitivity report — ending in a markdown + PDF report. Use when the user asks to "summarize round N", "make a report for R5", "round N summary/report", "how did R3 do", or wants the combined+TRANS ensemble figures plus evaluation+sensitivity for a SINGLE round. (For comparing rounds against each other, use compare-calibration-rounds instead.)
modes:
  requires_fates: true
  nutrient_pathway: any
  scope: [analysis]
  summary: "FATES Morris-ensemble round summary (figures + evaluation + sensitivity); requires a FATES calibration ensemble. Drives targets from the case targets.yaml."
---

# Summarize a Calibration Round

Single-round deliverable: ensemble graphs + evaluation + sensitivity, tied into a markdown/PDF
report. The cross-round analog is `compare-calibration-rounds`; this is its per-round complement and
shares the same footguns + tooling.

## When to use

- "Summarize round N", "make a report for R{N}", "how did R{N} do".
- After a round's ensemble (largely) completes, or after relaunched/added cases land.
- NOT for round-vs-round comparison (→ `compare-calibration-rounds`).

## Inputs (source the round's config first)

```bash
source a2mc_config.sh
source use_cases/<site>/config/<site>_config_r<N>.sh   # sets ENSEMBLE_OUTPUT, EXTRACTED_DATA,
                                                        # A2MC_CASE_NAME_PATTERN, targets
```
Round run dir = `$A2MC_ENSEMBLE_OUTPUT`; extract dir = `$A2MC_EXTRACTED_DATA`.

## Three deliverables

### 1. Whole-ensemble graphs (combined + TRANS)
`tools/plot_ensemble_cases.py` (`--combined` for the 519-yr ADSP+RGSP+TRANS axis; default for the
TRANS-only zoom) — or the round wrapper `regen_ensemble_milestone_plot.sh` /
`use_cases/<site>/analysis/regen_milestone_plot.sh`. Combined needs ADSP(1-200)+RGSP(201-400)+TRANS
NCs per case (extract all 3 phases). Output: `R{N}_{combined,TRANS}_{count}cases_ensemble.png`.
- **Per-round graphs are UNCAPPED**: include the round's own legitimate extra cases (e.g. R3 + its
  51 model-swap reruns = 4941, merged via offset case numbers). Do NOT pass a case cap here.

### 2. Evaluation report (screening)
`phases/phase2_screening/screen_ensemble.py --data-dir $A2MC_EXTRACTED_DATA --top-n 100
--output-dir <out>` → best case #, composite NRMSE, # targets met, per-target best-case sim vs obs.
- **Cap foreign contamination:** pass `--max-case-num <Morris size>` (e.g. 4890) so out-of-Morris
  experiment cases that happen to share the extract dir (e.g. H1 clumping #5001) don't rank as
  "best". This is distinct from #1: the round's *own* reruns are a separate model-swap view, not part
  of its Morris screening.
- Read `_results.txt` Sim_ columns + `screening_result.json` `best_case_num`, NOT the indices file.

### 3. Sensitivity report (Morris μ*)
Per target (PFT×organ): `build_Y_from_monthly.py` (builds Y, auto-excludes case# > ensemble size)
→ `phases/phase1_exploration/morris_sensitivity_analysis.py --output-var {leaf,fineroot}_biomass
--x-matrix <Morris X> --y-matrix <Y> --problem <salib_problem> --output-dir <out>` → per-PFT μ* CSVs.
- **Partial-ensemble caveat:** Morris μ* needs reasonably complete trajectories; with many missing
  cases (NaN rows) SALib drops incomplete trajectories. Report how many trajectories survived and
  flag μ* as provisional if the round is far from complete (e.g. R5 at 92.6% with deterministic
  model-failure dropouts — μ* usable but caveated).

## Report writing standard (the report is for a HUMAN with NO project context)

A round summary is read by a PI, a collaborator, or a manuscript reviewer who has **never seen the
codebase, the logs, or any internal name.** Internal logs may use project shorthand because writer and
reader share context; a *report* may not. Write to that reader:

1. **Executive summary first.** Open with 3–5 plain-language sentences a reader can understand alone: what
   the round tested, what it found, and what happens next.
2. **Define-or-avoid every internal term.** Expand each experiment codename / model-internal / A2MC term to
   plain language on FIRST use, or don't use it. Banned-unless-defined includes: any run-specific experiment
   codename, FATES internals (`PARTEH`, `ADSP/RGSP/TRANS`, `cohort_n`, `l2fr`, `prescribed_puptake`,
   `EDMainMod.F90:1010`), and A2MC terms (`V0`, `Morris μ*`, `skip-test`). e.g. write "the plant
   carbon–nutrient allocation solver (called PARTEH in FATES)", not "PARTEH".
3. **Every claim is a complete sentence: plain finding → mechanism → evidence.** No isolated jargon
   phrases. Template: *"[what happened, in physical/biological terms]; [why — the mechanism]; [the number
   or figure that shows it]."* **Bad:** "72 solver failures are restart-eligible." **Good:** "72 of the
   simulations stopped when the plant carbon–nutrient allocation solver failed to converge numerically;
   re-running five identical copies of one such case reproduced none of the failures (0 of 5), so these are
   numerical round-off artifacts that mostly succeed on resubmission — not model errors a parameter change
   could fix."
4. **Physically grounded, code as a footnote.** Lead with the biology (plant establishment, biomass,
   leaf-out timing) and the physical quantity; cite the source-file location as supporting detail, not the
   headline.
5. **Every figure and statistic carries its interpretation inline** — the `feedback_figures_over_tables_over_words`
   caption discipline, applied to the report body: name the figure, quote the key number, say what it means.
6. **The stranger test.** Each sentence must stand alone and be correct + clear to a stranger. If a
   sentence needs the reader to already know an internal term, rewrite it.
7. **A valid round outcome is "stop → improve the model."** A round can conclude that the *parameter*
   approach is exhausted and the next step is a model-code change — state that plainly with its evidence,
   not just "the next round changes X".

## The report (markdown → PDF)

Write `R{N}_summary_<date>.md` (a git-tracked home such as `reports/R{N}_summary_{date}/` keeps the report +
its figures together), then render with the **`markdown-to-pdf`** skill. Structure (apply the writing
standard above throughout):
0. **Executive summary** — 3–5 plain sentences (see standard #1).
1. **Header** — round N, protocol (suppl-N/P, prescribed vs coupled, FATES build), ensemble size +
   completion % (+ what the incomplete cases are: infra vs deterministic model failures, each explained).
2. **Evaluation** — best case # + composite NRMSE; per-target table (best-case sim vs obs, with ±20%
   and ±1 SD); # of 6 targets met; embed the combined + TRANS figures.
3. **Sensitivity** — top-N μ* params per target (table) + embed the per-round sensitivity figure;
   note trajectory count / provisional flag.
4. **Caveats + next steps** — bounds at edges, model-failure modes, what a next round should change.

## Footguns (shared with compare-calibration-rounds)

- Screening evaluation: **cap with `--max-case-num`** to drop foreign experiment cases; per-round
  **graphs stay uncapped** for the round's own reruns.
- Morris CSV `rank` is by `mu`; rank by **`mu_star`** for importance.
- Sensitivity file prefix is always `morris_leafbiomass_*` — organ is set by the **directory**.
- Use `_results.txt` + JSON, not the (partial-ensemble-buggy) `screening_top50_indices.txt`.
- Extraction conventions: `extract_monthly_variables_FATES.py` (production, `_exp`-gated) vs
  `extract_and_plot_selected_cases.py` (any phase/suffix via CLI) — see `offline-testing-workflow`.
- NERSC: scratch under `$HOME`/repo `tmp/` only.

## Cross-references

- `compare-calibration-rounds` (cross-round), `markdown-to-pdf` (report rendering),
  `offline-testing-workflow` (extraction conventions).
- Tools: `tools/plot_ensemble_cases.py`, `phases/phase2_screening/screen_ensemble.py`,
  `phases/phase1_exploration/morris_sensitivity_analysis.py`, `tools/regen_ensemble_milestone_plot.sh`.
- Worked references: `the originating dev/ana log,b` (R5/R3 graphs), the originating dev/ana log.

## Changelog

- 2026-07-06: Added the **Report writing standard** (report is for a human with no project context:
  executive summary, define-or-avoid jargon, complete plain-finding→mechanism→evidence sentences, the
  stranger test, "stop→improve-model" as a valid outcome) + a git-tracked report-location note. Ported from
  demo (`d788bd1`/`2cb3056`/`3519a61`), scrubbed of Kougarok run-specific codenames. See memory
  `feedback_report_writing_self_contained`.
- 2026-06-17: `## Changelog` convention adopted (see .claude/skills/README.md). Earlier history: git log + memory/dev_logs/.
