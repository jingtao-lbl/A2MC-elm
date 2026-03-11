# PFT10 Leaf Allometry Bottleneck: Minimum d2bl1 Limits Carbon Display Despite P Relief

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 2 | **Cycle:** 0 | **Iteration:** 2
**Date:** 2026-03-09 09:56:48
**Confidence:** 0.65

---

## Hypothesis: PFT10 Leaf Allometry Bottleneck: Minimum d2bl1 Limits Carbon Display Despite P Relief

### Mechanism

Previous experiments (c0_exp1 through c0_exp5) all target the P uptake bottleneck via vmax_p, vmax_ptase, turnover_fnrt, and root profile parameters. However, Case #322 has fates_allom_d2bl1 for PFT#10 at 0.019 — the absolute MINIMUM of its bounds [0.019, 0.15]. This parameter controls the scaling coefficient in the diameter-to-leaf-biomass allometry (leaf_biomass = d2bl1 * dbh^d2bl2). With d2bl1 at minimum, even if P limitation is relieved, the allometric target for leaf biomass is extremely small for any given diameter, meaning the plant allocates very little carbon to leaves. This creates a secondary bottleneck: low leaf area → low GPP → low carbon gain → low fineroot investment → continued P starvation feedback. Additionally, leaf_slatop_10 = 0.00853 (near minimum of [0.0085, 0.029]) means the specific leaf area is very low, so what little leaf biomass exists translates to minimal leaf area for light capture. The combination of minimum d2bl1 AND minimum SLA creates a 'double leaf bottleneck' that may persist even after P uptake is enhanced. This hypothesis is mechanistically DISTINCT from the P uptake experiments: it targets the carbon display side rather than the nutrient acquisition side.

### Design Type

factorial

---

## AI Reasoning and Analysis

Previous experiments (c0_exp1 through c0_exp5) all target the P uptake bottleneck via vmax_p, vmax_ptase, turnover_fnrt, and root profile parameters. However, Case #322 has fates_allom_d2bl1 for PFT#10 at 0.019 — the absolute MINIMUM of its bounds [0.019, 0.15]. This parameter controls the scaling coefficient in the diameter-to-leaf-biomass allometry (leaf_biomass = d2bl1 * dbh^d2bl2). With d2bl1 at minimum, even if P limitation is relieved, the allometric target for leaf biomass is extremely small for any given diameter, meaning the plant allocates very little carbon to leaves. This creates a secondary bottleneck: low leaf area → low GPP → low carbon gain → low fineroot investment → continued P starvation feedback. Additionally, leaf_slatop_10 = 0.00853 (near minimum of [0.0085, 0.029]) means the specific leaf area is very low, so what little leaf biomass exists translates to minimal leaf area for light capture. The combination of minimum d2bl1 AND minimum SLA creates a 'double leaf bottleneck' that may persist even after P uptake is enhanced. This hypothesis is mechanistically DISTINCT from the P uptake experiments: it targets the carbon display side rather than the nutrient acquisition side.

---

## Parameters to Modify

### fates_allom_d2bl1
- **Current:** 0.019
- **Proposed:** 0.085
- **Rationale:** Case #322 has this at absolute minimum bound (0.019). Increasing to mid-range (0.085) would increase allometric leaf biomass target by ~4.5× for any given diameter, enabling more carbon display and GPP. This is the geometric mean of the bounds [0.019, 0.15].

### fates_leaf_slatop
- **Current:** 0.00853
- **Proposed:** 0.02
- **Rationale:** Case #322 has SLA near minimum (0.00853 vs bounds [0.0085, 0.029]). Arctic graminoids typically have high SLA (~0.02-0.03 m²/g C). Increasing to 0.020 converts leaf biomass to ~2.3× more leaf area, boosting light capture and GPP. Combined with d2bl1 increase, this could break the leaf carbon display bottleneck.


---

## Expected Outcomes

- **leaf_pft10:** Increase from near-zero toward 5-15 g C/m² (partial improvement; full correction likely requires P fix from c0_exp experiments too)
- **froot_pft10:** Modest increase as higher GPP provides more carbon for root allocation
- **leaf_pft9:** No change (PFT-specific parameters only)
- **froot_pft9:** No change
- **agb_pft7:** No change

---

## Metadata

```json
{
  "iteration": 10,
  "diagnosis_count": 10,
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
  "iteration": 10,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-03-09T09:56:48.921506",
  "site": "Kougarok",
  "session_id": "20260309_094558",
  "experiment_count": 0,
  "skip_testing_count": 1,
  "diagnosis_count": 10,
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
