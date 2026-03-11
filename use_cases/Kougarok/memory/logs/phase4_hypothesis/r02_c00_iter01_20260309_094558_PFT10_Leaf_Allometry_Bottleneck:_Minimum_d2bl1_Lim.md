# PFT10 Leaf Allometry Bottleneck: Minimum d2bl1 Limits Carbon Investment in Leaves

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 2 | **Cycle:** 0 | **Iteration:** 1
**Date:** 2026-03-09 09:52:41
**Confidence:** 0.72

---

## Hypothesis: PFT10 Leaf Allometry Bottleneck: Minimum d2bl1 Limits Carbon Investment in Leaves

### Mechanism

Previous experiments (c0_exp1 through c0_exp5) addressed the P uptake bottleneck by increasing vmax_p and vmax_ptase, combined with turnover and root profile adjustments. However, Case #322 has allom_d2bl1_10 = 0.019 — the MINIMUM of its ensemble range [0.019, 0.15]. This parameter controls the intercept of the diameter-to-leaf-biomass allometry (leaf_biomass = d2bl1 * dbh^d2bl2). At such an extremely low value, even if P limitation is fully relieved and carbon is available, the allometric target for leaf biomass is severely constrained — the plant simply cannot allocate sufficient carbon to leaves because the allometric blueprint says a plant of that diameter should have very few leaves. With minimal leaf area, photosynthetic carbon gain is suppressed, creating a positive feedback loop: low leaves → low GPP → low carbon available → low growth → low fineroot biomass. This is a DIFFERENT mechanism from P uptake (addressed in exp1-5) — it targets the structural allometric constraint on leaf carbon allocation. Additionally, leaf_slatop_10 = 0.00853 is also at the minimum of its range [0.00853, 0.02896], meaning that what little leaf biomass exists produces minimal leaf area (low SLA = thick, expensive leaves). Together, these two parameters at their minimums create a 'leaf starvation' trap independent of nutrient availability.

### Design Type

cumulative

---

## AI Reasoning and Analysis

Previous experiments (c0_exp1 through c0_exp5) addressed the P uptake bottleneck by increasing vmax_p and vmax_ptase, combined with turnover and root profile adjustments. However, Case #322 has allom_d2bl1_10 = 0.019 — the MINIMUM of its ensemble range [0.019, 0.15]. This parameter controls the intercept of the diameter-to-leaf-biomass allometry (leaf_biomass = d2bl1 * dbh^d2bl2). At such an extremely low value, even if P limitation is fully relieved and carbon is available, the allometric target for leaf biomass is severely constrained — the plant simply cannot allocate sufficient carbon to leaves because the allometric blueprint says a plant of that diameter should have very few leaves. With minimal leaf area, photosynthetic carbon gain is suppressed, creating a positive feedback loop: low leaves → low GPP → low carbon available → low growth → low fineroot biomass. This is a DIFFERENT mechanism from P uptake (addressed in exp1-5) — it targets the structural allometric constraint on leaf carbon allocation. Additionally, leaf_slatop_10 = 0.00853 is also at the minimum of its range [0.00853, 0.02896], meaning that what little leaf biomass exists produces minimal leaf area (low SLA = thick, expensive leaves). Together, these two parameters at their minimums create a 'leaf starvation' trap independent of nutrient availability.

---

## Parameters to Modify

### fates_allom_d2bl1
- **Current:** 0.019
- **Proposed:** 0.085
- **Rationale:** Currently at absolute minimum of range [0.019, 0.15]. At 0.019, the allometric leaf target for PFT#10 is ~4.5x lower than a mid-range value. Increasing to 0.085 (near default 0.07, mid-range) allows the plant to allocate more carbon to leaves per unit diameter growth, increasing LAI and photosynthetic capacity. This directly addresses the leaf_pft10 failing target.

### fates_leaf_slatop
- **Current:** 0.00853
- **Proposed:** 0.02
- **Rationale:** Currently at minimum of range [0.00853, 0.02896]. Low SLA means each gram of leaf carbon produces very little leaf area. Arctic graminoids typically have moderate-to-high SLA (~0.02-0.03 m²/gC). Increasing to 0.020 roughly doubles the leaf area per unit leaf biomass, dramatically improving light capture and GPP for the same carbon investment in leaves.


---

## Expected Outcomes

- **leaf_pft10:** Increase from near-zero toward 5-15 g C/m² as allometric leaf target increases and each gram of leaf produces more area
- **froot_pft10:** Increase from near-zero toward 15-30 g C/m² as higher GPP from increased leaf area provides more carbon for root allocation
- **leaf_pft9:** No significant change (PFT-specific parameters only)
- **froot_pft9:** No significant change
- **agb_pft7:** No significant change

---

## Metadata

```json
{
  "iteration": 9,
  "diagnosis_count": 9,
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
  "iteration": 9,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-03-09T09:52:41.151512",
  "site": "Kougarok",
  "session_id": "20260309_094558",
  "experiment_count": 0,
  "skip_testing_count": 0,
  "diagnosis_count": 9,
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
