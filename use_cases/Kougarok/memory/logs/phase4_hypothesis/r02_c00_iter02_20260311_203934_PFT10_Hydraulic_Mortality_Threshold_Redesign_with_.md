# PFT10_Hydraulic_Mortality_Threshold_Redesign_with_L2FR_Constraint

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 2 | **Cycle:** 0 | **Iteration:** 2
**Date:** 2026-03-11 21:11:12
**Confidence:** 0.72

---

## Hypothesis: PFT10_Hydraulic_Mortality_Threshold_Redesign_with_L2FR_Constraint

### Mechanism

PFT10 (Arctic graminoid) is experiencing catastrophic collapse driven by hydraulic failure mortality (92% of all mortality in Case #322). Two compounding mechanisms are active: (1) mort_hf_sm_threshold_10 is at its lower bound (1e-8 in Case #322), meaning the hydraulic failure trigger activates at even the slightest soil moisture deficit — an ecologically implausible setting for Arctic graminoids adapted to waterlogged tundra soils; (2) l2fr_ini_10=9.88 (upper bound of range [1.115, 9.879]) is above the empirically identified L2FR threshold of ~2.99 for 50% PFT10 leaf biomass drop, creating a carbon starvation secondary pressure on top of hydraulic failure. Case #1386 (which uses different parameter values) achieves froot_pft10=186.6 vs Case #322's 16.9, confirming this parameter space has strong sensitivity. The fix requires simultaneously: (A) reducing mort_hf_sm_threshold_10 to near-zero (making hydraulic failure nearly impossible for this waterlogged-soil species), (B) reducing mort_scalar_hydrfailure_10 to dampen the mortality rate per stress day, and (C) constraining l2fr_ini_10 below the collapse threshold (~2.99) to prevent C-starvation secondary mortality. These three changes target the PRIMARY failure pathway (hydraulic) and SECONDARY failure pathway (C-starvation from excessive root allocation) simultaneously. This is a CUMULATIVE design because hydraulic failure must be reduced first before P limitation and C cycling can rescue biomass.

### Design Type

cumulative

---

## AI Reasoning and Analysis

PFT10 (Arctic graminoid) is experiencing catastrophic collapse driven by hydraulic failure mortality (92% of all mortality in Case #322). Two compounding mechanisms are active: (1) mort_hf_sm_threshold_10 is at its lower bound (1e-8 in Case #322), meaning the hydraulic failure trigger activates at even the slightest soil moisture deficit — an ecologically implausible setting for Arctic graminoids adapted to waterlogged tundra soils; (2) l2fr_ini_10=9.88 (upper bound of range [1.115, 9.879]) is above the empirically identified L2FR threshold of ~2.99 for 50% PFT10 leaf biomass drop, creating a carbon starvation secondary pressure on top of hydraulic failure. Case #1386 (which uses different parameter values) achieves froot_pft10=186.6 vs Case #322's 16.9, confirming this parameter space has strong sensitivity. The fix requires simultaneously: (A) reducing mort_hf_sm_threshold_10 to near-zero (making hydraulic failure nearly impossible for this waterlogged-soil species), (B) reducing mort_scalar_hydrfailure_10 to dampen the mortality rate per stress day, and (C) constraining l2fr_ini_10 below the collapse threshold (~2.99) to prevent C-starvation secondary mortality. These three changes target the PRIMARY failure pathway (hydraulic) and SECONDARY failure pathway (C-starvation from excessive root allocation) simultaneously. This is a CUMULATIVE design because hydraulic failure must be reduced first before P limitation and C cycling can rescue biomass.

---

## Parameters to Modify

### fates_mort_hf_sm_threshold
- **Current:** 1e-08
- **Proposed:** 1e-10
- **Rationale:** mort_hf_sm_threshold_10=1e-8 is at lower bound in Case #322, yet the parameter needs to go LOWER to reduce PFT10 sensitivity to hydraulic failure. Arctic graminoids grow in waterlogged tundra soils (Kougarok site) and rarely experience meaningful hydraulic failure — the threshold should be essentially non-operative. Reducing from 1e-8 to 1e-10 moves PFT10 to the extreme low end of hydraulic stress sensitivity, consistent with wetland-adapted graminoids. This directly targets the 92% hydraulic failure mortality observed in Case #322.

### fates_mort_scalar_hydrfailure
- **Current:** 0.41
- **Proposed:** 0.05
- **Rationale:** Even with threshold reduced, the scalar (0.41 in Case #322) amplifies each stress-day mortality too strongly. Reducing to 0.05 (lower bound of current range [0.05, 0.89]) minimizes the per-day hydraulic mortality rate for PFT10. Combined with the threshold reduction, this effectively disables hydraulic failure as a primary mortality pathway for this waterlogged-soil species. The combination of threshold + scalar reduction should eliminate the 92% hydraulic mortality dominance.

### fates_allom_l2fr
- **Current:** 9.88
- **Proposed:** 3.5
- **Rationale:** l2fr_ini_10=9.88 is at the upper bound of [1.115, 9.879] and is 3.3x above the empirically identified L2FR collapse threshold of ~2.99 for PFT10. The observed root:leaf biomass ratio for PFT10 (Arctic graminoid) is 382/83 ≈ 4.6, suggesting L2FR should be in the 3-6 range. Setting to 3.5 places it just above the collapse threshold (2.99) to allow adequate root investment without triggering C-starvation. This addresses the SECONDARY mortality pathway (C-starvation) after hydraulic failure is reduced. NOTE: Previous memory confirms paradoxical L2FR behavior for PFT10 — lower L2FR sometimes reduces froot biomass despite more leaf area. Setting at 3.5 (between threshold 2.99 and target ratio 4.6) balances this risk.

### fates_cnp_vmax_p
- **Current:** 5e-11
- **Proposed:** 5e-08
- **Rationale:** vmax_p_10=5e-11 is at the absolute lower bound, giving PFT10 essentially zero P uptake capacity. Once hydraulic failure mortality is reduced, PFT10 plants will survive long enough to face P limitation. Pre-emptively increasing vmax_p_10 by 3 orders of magnitude (5e-11 → 5e-8) ensures P uptake can support the surviving plant population. This is within the redesigned range (5e-9, 5e-3) recommended in the diagnosis. Note: this is a SECONDARY fix — hydraulic failure reduction is the primary lever, but vmax_p must be raised simultaneously or P starvation will cause C-starvation mortality to replace hydraulic mortality as the dominant killer.


---

## Parameter Validation Report

| Parameter | Check | Status | Detail |
|-----------|-------|--------|--------|
| fates_cnp_vmax_p | magnitude | INFO | 5e-11 → 5e-08 (1000.0x change, 100-1000x) |

**Summary:** 0 auto-fixed, 0 warning(s), 0 error(s)

---

## Expected Outcomes

- **leaf_pft10:** 50.0
- **froot_pft10:** 200.0
- **leaf_pft9:** 100.0
- **froot_pft9:** 120.0
- **leaf_pft7:** 22.0
- **froot_pft7:** 80.0
- **agb_pft10:** 30.0

---

## Metadata

```json
{
  "iteration": 2,
  "diagnosis_count": 2,
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
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_cnp_vmax_p', check='magnitude', severity='info', detail='5e-11 \u2192 5e-08 (1000.0x change, 100-1000x)', old_value=None, new_value=None)])"
}
```

---

## Iteration Context

```json
{
  "calibration_round": 2,
  "iteration": 2,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-03-11T21:11:12.106863",
  "site": "Kougarok",
  "session_id": "20260311_203934",
  "experiment_count": 0,
  "skip_testing_count": 1,
  "diagnosis_count": 2,
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
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_cnp_vmax_p', check='magnitude', severity='info', detail='5e-11 \u2192 5e-08 (1000.0x change, 100-1000x)', old_value=None, new_value=None)])"
}
```
