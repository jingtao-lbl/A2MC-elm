# PFT10_TripleBottleneck_TurnoverRootProfile_Fix

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 4 | **Cycle:** 0 | **Iteration:** 5
**Base Case:** #86
**Date:** 2026-04-14 10:56:01
**Confidence:** 0.72

---

## Hypothesis: PFT10_TripleBottleneck_TurnoverRootProfile_Fix

### Mechanism

PFT#10 (arctic graminoid) fineroot and leaf biomass are severely underestimated due to three compounding deficits identified in Case #86: (1) Fine root turnover is too fast at turnover_fnrt_10=3.07 yr, meaning roots are being replaced too frequently relative to realistic Arctic tundra graminoid root longevity (literature: 3-7 yr for sedges/grasses); each replacement costs carbon and nutrients, depleting both C and P storage. (2) Root profile parameters are likely backwards for graminoids — fnrt_prof_a_10=12.33 and fnrt_prof_b_10=3.26 create a root distribution that concentrates roots in shallow, nutrient-poor horizons rather than accessing deeper, seasonally-thawed nutrient-rich layers. (3) P uptake capacity is near-zero (vmax_p_10=3.57e-5) despite PFT#10 being at high alpha_ptase (0.95), suggesting the ECA competition for P is still won by PFT#9 due to the latter's high microb_bio_9=468.6 creating strong microbial competition. The core mechanism is a positive feedback loop: slow P acquisition → insufficient P for root growth → fewer roots → even slower P acquisition → P starvation mortality. Extending root longevity (increasing turnover_fnrt_10 reduces the annual replacement cost, allowing the existing root stock to persist and accumulate. Simultaneously, modifying the root profile to be more surface-concentrated (lower a, lower b) reduces the vertical distance roots must grow to contact nutrient patches. These are sequential bottlenecks (turnover → root stock → P contact area) making a cumulative design appropriate. We deliberately avoid touching vmax_p or ECA parameters based on the ECA_decomp_cost_reduction_causes_systemic_nutrient_collapse and ptase_extreme_magnitude_crash discoveries.

### Design Type

cumulative

---

## AI Reasoning and Analysis

PFT#10 (arctic graminoid) fineroot and leaf biomass are severely underestimated due to three compounding deficits identified in Case #86: (1) Fine root turnover is too fast at turnover_fnrt_10=3.07 yr, meaning roots are being replaced too frequently relative to realistic Arctic tundra graminoid root longevity (literature: 3-7 yr for sedges/grasses); each replacement costs carbon and nutrients, depleting both C and P storage. (2) Root profile parameters are likely backwards for graminoids — fnrt_prof_a_10=12.33 and fnrt_prof_b_10=3.26 create a root distribution that concentrates roots in shallow, nutrient-poor horizons rather than accessing deeper, seasonally-thawed nutrient-rich layers. (3) P uptake capacity is near-zero (vmax_p_10=3.57e-5) despite PFT#10 being at high alpha_ptase (0.95), suggesting the ECA competition for P is still won by PFT#9 due to the latter's high microb_bio_9=468.6 creating strong microbial competition. The core mechanism is a positive feedback loop: slow P acquisition → insufficient P for root growth → fewer roots → even slower P acquisition → P starvation mortality. Extending root longevity (increasing turnover_fnrt_10 reduces the annual replacement cost, allowing the existing root stock to persist and accumulate. Simultaneously, modifying the root profile to be more surface-concentrated (lower a, lower b) reduces the vertical distance roots must grow to contact nutrient patches. These are sequential bottlenecks (turnover → root stock → P contact area) making a cumulative design appropriate. We deliberately avoid touching vmax_p or ECA parameters based on the ECA_decomp_cost_reduction_causes_systemic_nutrient_collapse and ptase_extreme_magnitude_crash discoveries.

---

## Parameters to Modify

### fates_turnover_fnrt (PFT#10)
- **Current:** 3.071428571428571
- **Proposed:** 5.0
- **Rationale:** Case #86 turnover_fnrt_10=3.07 yr is at mid-range of the Morris ensemble [0.5, 5.0]. Arctic graminoid fine root longevity is 3-7 yr in literature (Chapin 1987, Iversen et al. 2015). Increasing to 5.0 yr (upper Morris bound) reduces annual fineroot turnover flux by ~39% ((1/3.07 - 1/5.0)/(1/3.07)), directly reducing the carbon and nutrient cost of maintaining existing root biomass. This allows P-limited PFT#10 to retain more root tissue per unit of acquired P, breaking the turnover-starvation feedback. At 5.0 yr, standing fineroot C at steady state increases proportionally (SteadyState = Production × Longevity), so even at constant production rates, fineroot biomass should increase ~63%. This is within Morris bounds so no bound expansion needed.

### fates_allom_fnrt_prof_a (PFT#10)
- **Current:** 12.332857142857142
- **Proposed:** 5.75
- **Rationale:** Case #86 fnrt_prof_a_10=12.33 is at the lower end of the Morris range [5.75, 17.27] but still creates a relatively steep root concentration gradient. The parameter 'a' in the fine root profile exponential function controls depth-weighting: lower 'a' spreads roots more broadly across the soil profile. For arctic tundra graminoids (sedges, grasses), roots should be concentrated in the upper 10-30 cm of active layer where seasonal nutrient mineralization is highest and ECA competition for P occurs. Setting to the Morris lower bound 5.75 maximizes root contact with the shallow nutrient-rich horizon where ECA P competition takes place, increasing effective P uptake per unit root biomass without changing vmax_p. This avoids the risk of touching ECA competition parameters directly.

### fates_allom_fnrt_prof_b (PFT#10)
- **Current:** 3.26
- **Proposed:** 3.26
- **Rationale:** EXCLUDED — current value fnrt_prof_b_10=3.26 is already at the Morris lower bound [3.26, 9.78]. Proposing the same value would be a no-op. We omit this parameter from the experiment to avoid confounding. If the first two parameters prove insufficient, fnrt_prof_b could be explored outside Morris bounds (e.g., 1.5-2.5) in a subsequent Phase 0 redesign. FLAG: NOT a meaningful change at current bounds — recommend expanding lower bound to 1.5 in Phase 0 redesign based on root profile literature for shallow-rooted arctic plants.

### fates_turnover_leaf (PFT#10)
- **Current:** 0.3
- **Proposed:** 0.5
- **Rationale:** Case #86 turnover_leaf_10=0.3 yr is at the Morris lower bound [0.3, 2.0]. Arctic graminoids typically have leaf longevity of 0.5-1.5 yr (deciduous grasses ~1 yr, sedges can retain leaves through winter). At 0.3 yr, the leaf replacement cost is extremely high — effectively 3.3 full leaf replacements per year — creating a severe carbon demand that competes with root maintenance for P-limited carbohydrate allocation. Increasing to 0.5 yr (a modest 67% increase in leaf longevity) reduces the annual leaf replacement cost by 40% (1/0.3 vs 1/0.5 = 3.33 vs 2.0 replacements/yr), directly reducing the C and P demand for leaf maintenance and freeing more assimilated C to be allocated to roots. This addresses leaf_pft10 target failure directly by increasing leaf standing stock at steady state.


---

## Parameter Validation Report

| Parameter | Check | Status | Detail |
|-----------|-------|--------|--------|
| fates_allom_fnrt_prof_b | no-op | WARNING | proposed=3.26 is unchanged from current=3.26 (delta <0.1%) |

**Summary:** 0 auto-fixed, 1 warning(s), 0 error(s)

---

## Expected Outcomes

- **froot_pft10:** Increase by 50-80% from Case #86 baseline due to reduced annual turnover flux and improved root-nutrient contact geometry
- **leaf_pft10:** Increase by 30-50% from Case #86 baseline due to reduced leaf replacement cost freeing C for leaf accumulation
- **froot_pft9:** Minimal change expected — PFT#9-specific parameters unchanged, no ECA parameter modifications
- **leaf_pft9:** Minimal change expected — PFT#9 unaffected by PFT#10-specific modifications
- **agb_pft7:** Should remain stable — no PFT#7 parameters modified

---

## Metadata

```json
{
  "iteration": 5,
  "diagnosis_count": 5,
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
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_allom_fnrt_prof_b', check='no-op', severity='warning', detail='proposed=3.26 is unchanged from current=3.26 (delta <0.1%)', old_value=None, new_value=None)])"
}
```

---

## Iteration Context

```json
{
  "calibration_round": 4,
  "iteration": 5,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-04-14T10:56:01.426692",
  "site": "Kougarok",
  "session_id": "20260413_173425",
  "experiment_count": 0,
  "skip_testing_count": 4,
  "diagnosis_count": 5,
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
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_allom_fnrt_prof_b', check='no-op', severity='warning', detail='proposed=3.26 is unchanged from current=3.26 (delta <0.1%)', old_value=None, new_value=None)])"
}
```
