# L2FR Collapse Threshold Verification: Confirming Empirical Thresholds and Feasible Region Across All PFTs

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 2 | **Cycle:** 0 | **Iteration:** 3
**Date:** 2026-03-11 21:20:15
**Confidence:** 0.88

---

## Hypothesis: L2FR Collapse Threshold Verification: Confirming Empirical Thresholds and Feasible Region Across All PFTs

### Mechanism

The diagnosis identifies L2FR (leaf-to-fine-root ratio) bound violations as the PRIMARY root cause of PFT9 and PFT10 collapse. Specifically: (1) l2fr_ini_9=18.31 is 4.7× above the empirically confirmed collapse threshold of 3.93, and (2) l2fr_ini_10=9.88 is 3.3× above the PFT10 threshold of 2.99. The mechanism is: high L2FR → large fine root carbon allocation → P_demand = fnrt_c × stoich_phos × vmax_p explodes → PID controller detects P deficit → redirects all carbon to roots → zero leaf carbon → carbon starvation collapse. Before redesigning the Morris ensemble bounds (Phase 0 redesign), we must VERIFY these thresholds empirically using the existing ensemble data. Specifically: (A) Does a sharp threshold exist at L2FR~3.93 for PFT9 where biomass collapses? (B) Does a similar threshold exist at L2FR~2.99 for PFT10? (C) What is the feasible L2FR range that avoids collapse while achieving target biomass ratios (PFT9: root:leaf=1.5, PFT10: root:leaf=4.6, PFT7: root:leaf=7.1)? (D) Is the PFT7 undershoot in froot explained by l2fr_ini_7=0.85 being too LOW (leaf-biased)? This analysis will directly inform the bounds redesign for the next Morris ensemble.

### Design Type

cumulative

---

## AI Reasoning and Analysis

The diagnosis identifies L2FR (leaf-to-fine-root ratio) bound violations as the PRIMARY root cause of PFT9 and PFT10 collapse. Specifically: (1) l2fr_ini_9=18.31 is 4.7× above the empirically confirmed collapse threshold of 3.93, and (2) l2fr_ini_10=9.88 is 3.3× above the PFT10 threshold of 2.99. The mechanism is: high L2FR → large fine root carbon allocation → P_demand = fnrt_c × stoich_phos × vmax_p explodes → PID controller detects P deficit → redirects all carbon to roots → zero leaf carbon → carbon starvation collapse. Before redesigning the Morris ensemble bounds (Phase 0 redesign), we must VERIFY these thresholds empirically using the existing ensemble data. Specifically: (A) Does a sharp threshold exist at L2FR~3.93 for PFT9 where biomass collapses? (B) Does a similar threshold exist at L2FR~2.99 for PFT10? (C) What is the feasible L2FR range that avoids collapse while achieving target biomass ratios (PFT9: root:leaf=1.5, PFT10: root:leaf=4.6, PFT7: root:leaf=7.1)? (D) Is the PFT7 undershoot in froot explained by l2fr_ini_7=0.85 being too LOW (leaf-biased)? This analysis will directly inform the bounds redesign for the next Morris ensemble.

---

## Parameters to Modify


---

## Expected Outcomes

- **pft9_collapse_threshold_confirmed:** Sharp biomass drop at l2fr_ini_9 > 3.5-4.5 visible in scatter plot
- **pft10_collapse_threshold_confirmed:** Sharp biomass drop at l2fr_ini_10 > 2.5-3.5 visible in scatter plot
- **pft7_froot_underestimate_explained:** Cases with l2fr_ini_7 < 2.0 systematically underestimate PFT7 froot
- **feasible_l2fr_region_identified:** Quantitative bounds for next ensemble redesign

---

## Metadata

```json
{
  "iteration": 3,
  "diagnosis_count": 3,
  "base_case": {
    "case_id": 322,
    "composite_rmsre": 0.6144307532631226,
    "targets_met": 3
  },
  "lowest_cost_case": {
    "case_id": 1386,
    "composite_rmsre": 0.5864984646272866,
    "targets_met": 0
  },
  "validation": "ValidationResult(issues=[])"
}
```

---

## Iteration Context

```json
{
  "calibration_round": 2,
  "iteration": 3,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-03-11T21:20:15.529197",
  "site": "Kougarok",
  "session_id": "20260311_203934",
  "experiment_count": 0,
  "skip_testing_count": 2,
  "diagnosis_count": 3,
  "base_case": {
    "case_id": 322,
    "composite_rmsre": 0.6144307532631226,
    "targets_met": 3
  },
  "lowest_cost_case": {
    "case_id": 1386,
    "composite_rmsre": 0.5864984646272866,
    "targets_met": 0
  },
  "validation": "ValidationResult(issues=[])"
}
```
