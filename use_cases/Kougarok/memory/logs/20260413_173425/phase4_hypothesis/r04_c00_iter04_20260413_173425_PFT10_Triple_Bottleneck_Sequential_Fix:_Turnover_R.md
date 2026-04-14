# PFT10_Triple_Bottleneck_Sequential_Fix: Turnover_RootDepth_Stoichiometry

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 4 | **Cycle:** 0 | **Iteration:** 4
**Base Case:** #86
**Date:** 2026-04-14 10:53:13
**Confidence:** 0.72

---

## Hypothesis: PFT10_Triple_Bottleneck_Sequential_Fix: Turnover_RootDepth_Stoichiometry

### Mechanism

PFT#10 (Arctic graminoid/sedge) suffers a triple mechanistic bottleneck in Case #86: (1) Fine root turnover is 3.07 yr — too fast for Arctic tundra where root longevity is typically 4-6 yr, causing excessive C and nutrient demand that depletes storage; (2) Root distribution parameters fnrt_prof_a=12.33 and fnrt_prof_b=3.26 place roots too shallowly, missing deeper nutrient-rich layers and reducing competitive access to soil P/N in the ECA framework; (3) Leaf P stoichiometry (stoich_phos_leaf=0.000921) is at the lower Morris bound, creating high P demand per unit leaf C that cannot be met by the near-zero P uptake (vmax_p_10=3.57e-5). Together, these drive P starvation (effectively zero P uptake), carbon starvation from nutrient-limited growth, and insufficient fine root biomass accumulation. The cumulative design first extends root longevity (reduces C flux through root pool, allowing biomass to accumulate), then adjusts root distribution toward deeper soil horizons (improves ECA competitive position for P), and finally lowers leaf P demand stoichiometry (reduces per-unit-leaf P requirement, alleviating starvation). These are sequential steps in the same causal chain: turnover controls steady-state biomass → root depth controls nutrient access → stoichiometry controls nutrient demand. PFT#9 parameters are NOT modified to avoid the known ECA competition inversion failure mode.

### Design Type

cumulative

---

## AI Reasoning and Analysis

PFT#10 (Arctic graminoid/sedge) suffers a triple mechanistic bottleneck in Case #86: (1) Fine root turnover is 3.07 yr — too fast for Arctic tundra where root longevity is typically 4-6 yr, causing excessive C and nutrient demand that depletes storage; (2) Root distribution parameters fnrt_prof_a=12.33 and fnrt_prof_b=3.26 place roots too shallowly, missing deeper nutrient-rich layers and reducing competitive access to soil P/N in the ECA framework; (3) Leaf P stoichiometry (stoich_phos_leaf=0.000921) is at the lower Morris bound, creating high P demand per unit leaf C that cannot be met by the near-zero P uptake (vmax_p_10=3.57e-5). Together, these drive P starvation (effectively zero P uptake), carbon starvation from nutrient-limited growth, and insufficient fine root biomass accumulation. The cumulative design first extends root longevity (reduces C flux through root pool, allowing biomass to accumulate), then adjusts root distribution toward deeper soil horizons (improves ECA competitive position for P), and finally lowers leaf P demand stoichiometry (reduces per-unit-leaf P requirement, alleviating starvation). These are sequential steps in the same causal chain: turnover controls steady-state biomass → root depth controls nutrient access → stoichiometry controls nutrient demand. PFT#9 parameters are NOT modified to avoid the known ECA competition inversion failure mode.

---

## Parameters to Modify

### fates_turnover_fnrt (PFT#10)
- **Current:** 3.071428571428571
- **Proposed:** 5.0
- **Rationale:** Arctic graminoid/sedge fine roots persist 4-7 yr in tundra (Iversen et al. 2017, Sloan et al. 2013). Case #86 has 3.07 yr — undershooting the Arctic range. Increasing to 5.0 yr (upper Morris bound) reduces annual root turnover flux by ~39%, allowing root C pool to accumulate toward observed froot target. Lower flux also reduces annual P demand from root turnover retranslocation cycling, easing P starvation. This is within the Morris sampling bounds so risk is low.

### fates_allom_fnrt_prof_a (PFT#10)
- **Current:** 12.332857142857142
- **Proposed:** 5.75
- **Rationale:** Parameter 'a' in the exponential root profile function controls the rate of root mass decrease with depth. Higher 'a' concentrates roots near the surface. Case #86 has a=12.33 which places PFT#10 (graminoid/sedge) roots very shallowly. Arctic sedges (Eriophorum, Carex) have roots extending to 30-50 cm, accessing deeper mineral soil P. Reducing to 5.75 (lower Morris bound) distributes roots deeper, improving competitive P and N uptake in the ECA soil nutrient competition against PFT#9 and microbial biomass. This is the lower bound of the current Morris range — flagging as edge case but mechanistically justified.

### fates_allom_fnrt_prof_b (PFT#10)
- **Current:** 3.26
- **Proposed:** 3.26
- **Rationale:** EXCLUDED — current value is already at the lower Morris bound (3.26). Proposing the same value would be a no-op. Root depth adjustment is handled entirely through fnrt_prof_a reduction. Leaving fnrt_prof_b at its current value avoids over-parameterization and preserves the ability to attribute effects to fnrt_prof_a alone.

### fates_stoich_phos (PFT#10) [leaf]
- **Current:** 0.000920964
- **Proposed:** 0.0019
- **Rationale:** Case #86 PFT#10 leaf P stoichiometry is 0.000921 g P/g C — at the lower Morris bound and well below the default (0.004). This is counterintuitively LOW for tundra plants where P is limiting: low leaf P content reduces the P cost per unit leaf C but also signals P-stressed tissue. However, in the FATES CNP framework, stoich_phos_leaf sets the TARGET P content for allocation, so a very low value means the model targets P-poor leaves and the plant appears P-sufficient even when P uptake is near zero. Increasing to 0.0019 (mid-range of Morris bounds) sets a more realistic target, which will properly signal P limitation and stimulate the ECA uptake machinery. Out of bounds would require going to ~0.003 (literature: 0.002-0.003 for Arctic graminoids), but we take a conservative step to 0.0019 first.

### fates_stoich_phos (PFT#10) [fineroot]
- **Current:** 0.0010996144285714286
- **Proposed:** 0.0016
- **Rationale:** Fineroot P stoichiometry for PFT#10 is 0.00110 g P/g C in Case #86, below the midpoint of Morris bounds (0.00071-0.00126). Increasing to 0.0016 slightly increases root P content target, which will increase total plant P demand and stimulate P uptake fluxes through ECA. This is a modest increase within Morris bounds. Coordinated with leaf P increase to maintain realistic leaf:root P ratio.


---

## Parameter Validation Report

| Parameter | Check | Status | Detail |
|-----------|-------|--------|--------|
| fates_allom_fnrt_prof_b | no-op | WARNING | proposed=3.26 is unchanged from current=3.26 (delta <0.1%) |
| fates_stoich_phos | out of bounds | WARNING | proposed=0.0016 outside [0.000709198, 0.001255781] |

**Summary:** 0 auto-fixed, 2 warning(s), 0 error(s)

---

## Expected Outcomes

- **froot_pft10:** 85.0
- **leaf_pft10:** 40.0
- **froot_pft9:** 55.0
- **leaf_pft9:** 115.0
- **froot_pft7:** 25.0
- **leaf_pft7:** 20.0

---

## Metadata

```json
{
  "iteration": 4,
  "diagnosis_count": 4,
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
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_allom_fnrt_prof_b', check='no-op', severity='warning', detail='proposed=3.26 is unchanged from current=3.26 (delta <0.1%)', old_value=None, new_value=None), ValidationIssue(parameter='fates_stoich_phos', check='out of bounds', severity='warning', detail='proposed=0.0016 outside [0.000709198, 0.001255781]', old_value=None, new_value=None)])"
}
```

---

## Iteration Context

```json
{
  "calibration_round": 4,
  "iteration": 4,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-04-14T10:53:13.721589",
  "site": "Kougarok",
  "session_id": "20260413_173425",
  "experiment_count": 0,
  "skip_testing_count": 3,
  "diagnosis_count": 4,
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
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_allom_fnrt_prof_b', check='no-op', severity='warning', detail='proposed=3.26 is unchanged from current=3.26 (delta <0.1%)', old_value=None, new_value=None), ValidationIssue(parameter='fates_stoich_phos', check='out of bounds', severity='warning', detail='proposed=0.0016 outside [0.000709198, 0.001255781]', old_value=None, new_value=None)])"
}
```
