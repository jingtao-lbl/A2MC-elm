---
name: diagnose-forensics
visibility: public
category: calibration
description: Investigate an anomaly or suspicious result in an ensemble — an outlier, a too-good "best" case, a failure cluster, a target that won't move — to determine FIRST whether it's real or an artifact (contamination, infra-timing, mislabeled index, NaN), then root-cause it with the phase3 diagnosis tools. Use when the user asks "why is case X an outlier", "is this result real or contamination", "investigate this anomaly / failure cluster", "edge-case / collapse detection", "root cause of this PFT not calibrating".
modes:
  requires_fates: false
  nutrient_pathway: any
  scope: [analysis]
  summary: "Artifact-triage + root-cause workflow; model-agnostic (the worked examples are FATES/Morris)."
---

# Ensemble Forensics (artifact triage, then root cause)

When a result looks surprising — a case that scores far better/worse than its
neighbours, a cluster of failures, a "most-targets" winner that seems too good, a target
that never moves — **triage for artifacts BEFORE reading it as scientific signal.** Most
"interesting" tiny patterns turn out to be contamination or infrastructure timing. Only
after a result survives triage do you root-cause it.

> Worked example this skill generalizes: the bogus R3 "most-targets" case #100317 — an
> experiment NC leaking into the Morris extract dir and matching the glob, not a real
> champion.

## Step 1 — artifact triage (do this first)

Run the checks that apply; any hit means the "signal" is an artifact, not science:

- **Contamination (foreign case in the analysis set).** Is the case ID inside the round's
  Morris range? Does its name match the round's pattern, or is it an **experiment leak**
  (`_exp`, clump, or other suffix) that a glob picked up? List the extract dir and look
  for NCs that don't belong. (memory: Phase 5 case-naming; the extractor's `_exp` gating.)
- **Mislabeled index on a partial ensemble.** Screening `Set_ID`/indices can be
  *position+1*, not the real case number. Use the JSON `best_case_num` + the `_results.txt`
  `Sim_` columns, not the indices file. (memory: screening indices mislabel.)
- **Failure-signature, not science.** For a failure cluster, check **ExitCode +
  DerivedExitCode + End time + NodeList + `lnd.log` tail** before reading case-ID or
  param-vector clustering as meaningful. Tiny cohorts (3–10 jobs) are prone to
  infra-timing artifacts that look like signal. (memory: check failure signatures first.)
- **Garbage metrics.** NaN/Inf or schema-mismatched values that passed a non-empty check.
- **Stale run-state.** Re-derive counts from live `squeue` + disk NC counts + the newest
  dated log before quoting (memory: verify run-state before quoting).

If any triage check fires: it's a tooling/data bug, not a discovery. **Fix it and
supersede** the affected analysis/figure (the `/log` supersede protocol — new dated log +
banner on the old), don't quietly edit the old conclusion.

## Step 2 — root-cause (only after triage passes)

**First, resolve the run configuration — before running a diagnosis tool or opening model source.** ELM/FATES branches on many axes at once (FATES on/off, PARTEH 1 vs 2, CN vs CNP, ECA vs RD, NOCOMP, SPITFIRE, hydraulics, prescribed vs coupled uptake), and each branch owns constants, parameters and history variables that are inert or differently-defined under the others. A constant read correctly from the run's own input files can still belong to a branch the run never executes — every provenance check passes and the answer is still wrong.

```bash
source use_cases/{Model}_{Case}/config/<case>_config.sh   # auto-sources the machine config
python tools/describe_mode.py                             # e.g. "Competition: ON (ECA pathway)"
CASE="$A2MC_E3SM_ROOT/cime/scripts/<case_name>"           # NOT co-located with the run dir
cd "$CASE" && ./xmlquery -value RUNDIR                    # also how you LOCATE the run dir
grep -nE "nu_com|use_fates|hlm_parteh_mode|suplphos|nyears_ad_carbon_only" "$RUNDIR/lnd_in"
```

The run dir's `lnd_in` is ground truth and the FATES parameter file does not substitute for it: namelist switches are absent from that file entirely (`nu_com` is one), so a parameter-file-only check returns an empty result for exactly the switch that selects the branch — and empty reads as "nothing to see". **Name the branch whenever you quote what you found** ("`smax`, the RD-path capacity", never "the capacity"). The mode-aware RAG filtering in `docs/a2mc_reference/mode_aware_howto.md` does not cover you here — it gates what the *online* agent retrieves into a Phase 3/4 prompt; reading source directly bypasses it. Full rule + verification chain: memory `feedback_resolve_run_config_before_reading_branched_source`.

Then use the `phases/phase3_diagnosis/` tools (drive several via `run_diagnostics_scripts.py`
/ `dispatch.py`):

| Question | Tool |
|---|---|
| What parameters does this case have / differ by? | `read_case_parameters.py`, `compare_case_parameters.py` |
| Any parameter pinned at a bound? | `check_edge_parameters.py` |
| Which targets, how far off? | `compare_targets.py` |
| Did it collapse / crash? | `detect_collapse.py` |
| Why is a PFT not establishing/growing? | `diagnose_pft_limitations.py` |
| Carbon / mortality / nutrient mechanism | `analyze_carbon_balance.py`, `analyze_mortality.py`, `analyze_nutrient_balance.py`, `analyze_nutrient_pools.py` |
| Plot the diagnostics | `plot_diagnostics.py` |

Cross-check the mechanism against RAG/GraphRAG / `docs/fates-knowledge-base/` before asserting it
(never name a FATES mechanism from a parameter name).

## Step 3 — write it up

- **Scientific finding** → an `ana_log` (cite the figures/stats/data files; `/log ana`).
- **Tooling/contamination bug** → a `dev_log` documenting root cause + fix, and supersede
  any analysis it invalidated.
- If the finding is a vetted, generalizable lesson → propose it for the curated KB via
  `curate-knowledge` (Tier-3 is interactive-only).

## Notes
- The order is load-bearing: **triage → root-cause → write-up.** Reading a pattern as
  science before triage is how the contamination episodes happened.
- Related skills: `restart-failed-jobs` (after you confirm infra vs model failure),
  `curate-knowledge` (to land a confirmed lesson), `/log` (write-up + supersede).

## Changelog

- 2026-08-27: Step 2 (root-cause). Added a **resolve-the-run-configuration step** — a constant read correctly from the run's own input files can still belong to a branch the run never executes, so provenance discipline alone does not catch it. Carries the three-step chain (site config → CIME case dir under `cime/scripts/` → the run dir's `lnd_in`), the note that namelist switches like `nu_com` are absent from the FATES parameter file entirely, and the requirement to name the branch when quoting a constant. Signal: `memory/dev_logs/reflection/20260827a_Reflection_A_Real_Value_From_The_Wrong_Branch.md` — a figure normalised `LABILEP` by the RD-path `smax` in an ECA run, inverting the reading; `git grep -c describe_mode` confirmed both skills mentioned mode resolution zero times, while `tools/describe_mode.py` ran only in the two setup-time skills. Applied under `refine-skill` after PI approval.
- 2026-06-17: `## Changelog` convention adopted (see .claude/skills/README.md). Earlier history: git log + memory/dev_logs/.
