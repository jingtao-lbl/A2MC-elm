---
name: diagnose-forensics
description: Investigate an anomaly or suspicious result in an ensemble — an outlier, a too-good "best" case, a failure cluster, a target that won't move — to determine FIRST whether it's real or an artifact (contamination, infra-timing, mislabeled index, NaN), then root-cause it with the phase3 diagnosis tools. Use when the user asks "why is case X an outlier", "is this result real or contamination", "investigate this anomaly / failure cluster", "edge-case / collapse detection", "root cause of this PFT not calibrating".
---

# Ensemble Forensics (artifact triage, then root cause)

When a result looks surprising — a case that scores far better/worse than its
neighbours, a cluster of failures, a "most-targets" winner that seems too good, a target
that never moves — **triage for artifacts BEFORE reading it as scientific signal.** Most
"interesting" tiny patterns turn out to be contamination or infrastructure timing. Only
after a result survives triage do you root-cause it.

> Worked example this skill generalizes: the bogus R3 "most-targets" case #100317 — an
> experiment NC leaking into the Morris extract dir and matching the glob, not a real
> champion. See `memory/dev_logs/20260610g_R3_Ensemble_Plot_Contamination_Fix_100317.md`.

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

Use the `phases/phase3_diagnosis/` tools (drive several via `run_diagnostics_scripts.py`
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

- 2026-06-17: `## Changelog` convention adopted (see .claude/skills/README.md). Earlier history: git log + memory/dev_logs/.
