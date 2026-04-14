# PFT10_Triple_Bottleneck_Sequential_Fix: Turnover→RootDepth→NutrientUptake

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 4 | **Cycle:** 0 | **Iteration:** 1
**Base Case:** #86
**Date:** 2026-04-14 10:44:45
**Confidence:** 0.72

---

## Hypothesis: PFT10_Triple_Bottleneck_Sequential_Fix: Turnover→RootDepth→NutrientUptake

### Mechanism

PFT#10 (Arctic graminoid) fails three sequential bottlenecks simultaneously: (1) fine root turnover is too fast at 3.07 yr in Case #86 — wait, actually 3.07 yr is already slow, but the diagnosis flags 'default 1.0 yr vs 5.0 yr realistic for Arctic', indicating the ensemble default was ~1 yr and Case #86 has drifted to 3.07 but not reached the Arctic-realistic 4-5 yr range; (2) root distribution parameters in Case #86 show fnrt_prof_a_10=12.33 and fnrt_prof_b_10=3.26 — the diagnosis flags these as 'BACKWARDS' for graminoids, which should concentrate roots in the shallow organic layer (high b, moderate a) rather than deep mineral soil; (3) P uptake capacity vmax_p_10=3.57e-05 may be insufficient relative to the competitive ECA equilibrium with PFT#9 (vmax_p_9=2.14e-05), and vmax_ptase_10=3.57e-04 is already at upper Morris bound, suggesting phosphatase is maximized but root contact area is insufficient due to wrong depth distribution. The mechanistic chain is: wrong root depth profile → roots accessing P-depleted deep mineral soil instead of P-rich shallow organic horizon → effectively zero plant-available P contact → P starvation → zero biomass allocation to both leaf and fineroot pools. Fixing root distribution to concentrate PFT#10 roots in shallow layers (increasing fnrt_prof_b_10 toward upper bound, adjusting fnrt_prof_a_10) combined with increasing turnover longevity to build steady-state root biomass stock should break the primary bottleneck. Crucially, fates_cnp_eca_decompmicc for PFT#10 is at 205.7 (below the 300 safety threshold identified in DISCOVERY ECA_decomp_cost_reduction_causes_systemic_nutrient_collapse), but since we are NOT modifying it, it remains a background risk.

### Design Type

cumulative

---

## AI Reasoning and Analysis

PFT#10 (Arctic graminoid) fails three sequential bottlenecks simultaneously: (1) fine root turnover is too fast at 3.07 yr in Case #86 — wait, actually 3.07 yr is already slow, but the diagnosis flags 'default 1.0 yr vs 5.0 yr realistic for Arctic', indicating the ensemble default was ~1 yr and Case #86 has drifted to 3.07 but not reached the Arctic-realistic 4-5 yr range; (2) root distribution parameters in Case #86 show fnrt_prof_a_10=12.33 and fnrt_prof_b_10=3.26 — the diagnosis flags these as 'BACKWARDS' for graminoids, which should concentrate roots in the shallow organic layer (high b, moderate a) rather than deep mineral soil; (3) P uptake capacity vmax_p_10=3.57e-05 may be insufficient relative to the competitive ECA equilibrium with PFT#9 (vmax_p_9=2.14e-05), and vmax_ptase_10=3.57e-04 is already at upper Morris bound, suggesting phosphatase is maximized but root contact area is insufficient due to wrong depth distribution. The mechanistic chain is: wrong root depth profile → roots accessing P-depleted deep mineral soil instead of P-rich shallow organic horizon → effectively zero plant-available P contact → P starvation → zero biomass allocation to both leaf and fineroot pools. Fixing root distribution to concentrate PFT#10 roots in shallow layers (increasing fnrt_prof_b_10 toward upper bound, adjusting fnrt_prof_a_10) combined with increasing turnover longevity to build steady-state root biomass stock should break the primary bottleneck. Crucially, fates_cnp_eca_decompmicc for PFT#10 is at 205.7 (below the 300 safety threshold identified in DISCOVERY ECA_decomp_cost_reduction_causes_systemic_nutrient_collapse), but since we are NOT modifying it, it remains a background risk.

---

## Parameters to Modify

### fates_turnover_fnrt (PFT#10)
- **Current:** 3.071428571428571
- **Proposed:** 4.8
- **Rationale:** Arctic graminoid fine roots have longevity of 4-6 yr in tundra literature (Iversen et al. 2015, Sloan et al. 2013). Case #86 at 3.07 yr builds insufficient steady-state root biomass pool. Increasing to 4.8 yr (within Morris bounds [0.5, 5.0]) increases equilibrium fineroot C = production_rate × longevity by ~56%, directly addressing the froot_pft10 target shortfall. This is the highest-priority fix per diagnosis.

### fates_allom_fnrt_prof_b (PFT#10)
- **Current:** 3.26
- **Proposed:** 8.5
- **Rationale:** fates_allom_fnrt_prof_b controls the steepness of root distribution decay with depth. Higher b concentrates roots in shallower layers. Arctic graminoids (sedges, grasses) are documented to concentrate >70% of root biomass in the top 10 cm organic horizon where P availability is highest. Case #86 has fnrt_prof_b_10=3.26 (near lower Morris bound of 3.26), meaning roots are distributed too deeply into P-depleted mineral soil. Increasing to 8.5 (within Morris bounds [3.26, 9.78]) corrects root depth profile to match Arctic graminoid ecology and places roots in contact with the organic P pool mineralized by phosphatase. This directly addresses the 'BACKWARDS' root distribution diagnosis.

### fates_allom_fnrt_prof_a (PFT#10)
- **Current:** 12.332857142857142
- **Proposed:** 8.0
- **Rationale:** fates_allom_fnrt_prof_a controls the overall root profile shape parameter a. In combination with the b parameter increase above, reducing a from 12.33 toward mid-range (8.0, within Morris bounds [5.75, 17.27]) prevents overly extreme root concentration in the very surface layer while still correcting the depth distribution toward shallow organic horizon. The a-b combination jointly determines the root density profile — adjusting both together (rather than one alone) produces a physically realistic shallow-concentrated but not surface-only distribution appropriate for tundra graminoids.

### fates_cnp_vmax_p (PFT#10)
- **Current:** 3.5714300000000005e-05
- **Proposed:** 0.00012
- **Rationale:** P uptake capacity vmax_p_10=3.57e-05 is insufficient relative to the ECA competitive equilibrium. In Case #86, PFT#9 (vmax_p_9=2.14e-05) and PFT#7 (vmax_p_7=2.86e-05) both have lower vmax_p than PFT#10, yet PFT#10 still shows near-zero P uptake, suggesting the root depth correction must be paired with sufficient uptake kinetics. Increasing vmax_p_10 to 1.2e-04 (within Morris bounds [5e-11, 5e-05] — NOTE: this value of 1.2e-04 exceeds the current Morris upper bound of 5e-05; flagged as out-of-Morris-bounds) places PFT#10 uptake capacity at ~3.4× its current value, compensating for the low root biomass during the transient period before the turnover increase takes full effect. The diagnosis explicitly identifies 'P STARVATION: PFT#10 P uptake/demand ≈ 0.000005 (essentially zero)' as primary cause. IMPORTANT: This value (1.2e-04) exceeds the Morris upper bound of 5e-05 — recommend Morris bound expansion to [5e-11, 2.5e-04] in Phase 0 redesign to cover Arctic graminoid literature values.


---

## Parameter Validation Report

| Parameter | Check | Status | Detail |
|-----------|-------|--------|--------|
| fates_cnp_vmax_p | out of bounds | WARNING | proposed=0.00012 outside [5e-11, 5e-05] |

**Summary:** 0 auto-fixed, 1 warning(s), 0 error(s)

---

## Expected Outcomes

- **froot_pft10:** Increase from near-zero to 30-60 g C/m² (target range estimated ~40-80 g C/m² for Arctic graminoid fineroot). Steady-state fineroot biomass scales as production_rate × turnover_time; 56% increase in turnover time combined with corrected root-soil contact area should produce 2-4× improvement.
- **leaf_pft10:** Increase from near-zero to 20-50 g C/m². Leaf biomass recovery is contingent on fineroot recovery (nutrient supply pathway). Once P uptake normalizes, allocation to leaf should recover through PID controller response. Expected 1.5-3× improvement.
- **froot_pft9:** Minimal change expected (<10% variation). PFT#9 parameters are unchanged; slight reduction possible if PFT#10 competes more effectively for shallow P, but PFT#9 roots are distributed differently (fnrt_prof_b_9=24.8, very shallow already).
- **leaf_pft9:** Minimal change expected (<10% variation). PFT#9 leaf biomass should be unaffected as only PFT#10-specific parameters are modified.
- **froot_pft7:** Minimal change expected. PFT#7 has distinct soil niche and high vmax_nh4_7=2.5e-04 providing N advantage independent of P competition changes.
- **agb_pft10:** Modest increase (20-50%) as recovered C allocation supports aboveground structural growth, but AGB response is secondary to root recovery.

---

## Metadata

```json
{
  "iteration": 1,
  "diagnosis_count": 1,
  "base_case": {
    "case_id": 86,
    "composite_rmsre": 0.5530835421160863,
    "targets_met": 2
  },
  "lowest_cost_case": {
    "case_id": 86,
    "composite_rmsre": 0.5530835421160863,
    "targets_met": 2
  },
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_cnp_vmax_p', check='out of bounds', severity='warning', detail='proposed=0.00012 outside [5e-11, 5e-05]', old_value=None, new_value=None)])"
}
```

---

## Iteration Context

```json
{
  "calibration_round": 4,
  "iteration": 1,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-04-14T10:44:45.729480",
  "site": "Kougarok",
  "session_id": "20260413_173425",
  "experiment_count": 0,
  "skip_testing_count": 0,
  "diagnosis_count": 1,
  "base_case": {
    "case_id": 86,
    "composite_rmsre": 0.5530835421160863,
    "targets_met": 2
  },
  "lowest_cost_case": {
    "case_id": 86,
    "composite_rmsre": 0.5530835421160863,
    "targets_met": 2
  },
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_cnp_vmax_p', check='out of bounds', severity='warning', detail='proposed=0.00012 outside [5e-11, 5e-05]', old_value=None, new_value=None)])"
}
```
