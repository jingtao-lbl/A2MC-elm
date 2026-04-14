# PFT10_TripleBottleneck_TurnoverRootProfile_Correction

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 4 | **Cycle:** 0 | **Iteration:** 7
**Base Case:** #86
**Date:** 2026-04-14 11:01:20
**Confidence:** 0.68

---

## Hypothesis: PFT10_TripleBottleneck_TurnoverRootProfile_Correction

### Mechanism

PFT#10 (Arctic graminoid/sedge) fails to build fineroot and leaf biomass due to a triple bottleneck: (1) Fine root turnover at 3.07 yr (Case #86) is near the upper Morris bound of 5.0 yr, but the DIAGNOSIS identifies excessive turnover as a cause — this is likely already compensated. The real issue is that froot_prof_b_10 = 3.26 (at its LOWER Morris bound) forces roots into shallow soil layers where frozen/nutrient-poor conditions dominate, limiting P and N uptake. Meanwhile froot_prof_a_10 = 12.33 concentrates the root profile too sharply. For Arctic graminoids/sedges, shallow roots in the active layer are ecologically correct, BUT the ECA competition framework requires roots to be co-located with nutrient-rich microsites — in tundra, the top 10-15 cm organic horizon is P-rich from slow decomposition. A LARGER fnrt_prof_b_10 (steeper exponential falloff with depth) combined with LOWER fnrt_prof_a_10 (shallower centroid) would concentrate PFT#10 roots in the nutrient-rich organic horizon, increasing P/N uptake efficiency without changing vmax values. This is PFT-specific (no cross-PFT conflict) and tests the root architecture hypothesis independent of nutrient kinetics. Additionally, turnover_fnrt_10 at 3.07 yr creates a high continuous carbon demand for root replacement — reducing it toward 4.5 yr would lower the standing root maintenance cost, allowing carbon to accumulate in the fineroot pool. The existing ensemble contains cases spanning the full Morris bounds for all three parameters (fnrt_prof_a_10: 5.75–17.27, fnrt_prof_b_10: 3.26–9.78, turnover_fnrt_10: 0.5–5.0), enabling correlation analysis BEFORE committing to an HPC run.

### Design Type

cumulative

---

## AI Reasoning and Analysis

PFT#10 (Arctic graminoid/sedge) fails to build fineroot and leaf biomass due to a triple bottleneck: (1) Fine root turnover at 3.07 yr (Case #86) is near the upper Morris bound of 5.0 yr, but the DIAGNOSIS identifies excessive turnover as a cause — this is likely already compensated. The real issue is that froot_prof_b_10 = 3.26 (at its LOWER Morris bound) forces roots into shallow soil layers where frozen/nutrient-poor conditions dominate, limiting P and N uptake. Meanwhile froot_prof_a_10 = 12.33 concentrates the root profile too sharply. For Arctic graminoids/sedges, shallow roots in the active layer are ecologically correct, BUT the ECA competition framework requires roots to be co-located with nutrient-rich microsites — in tundra, the top 10-15 cm organic horizon is P-rich from slow decomposition. A LARGER fnrt_prof_b_10 (steeper exponential falloff with depth) combined with LOWER fnrt_prof_a_10 (shallower centroid) would concentrate PFT#10 roots in the nutrient-rich organic horizon, increasing P/N uptake efficiency without changing vmax values. This is PFT-specific (no cross-PFT conflict) and tests the root architecture hypothesis independent of nutrient kinetics. Additionally, turnover_fnrt_10 at 3.07 yr creates a high continuous carbon demand for root replacement — reducing it toward 4.5 yr would lower the standing root maintenance cost, allowing carbon to accumulate in the fineroot pool. The existing ensemble contains cases spanning the full Morris bounds for all three parameters (fnrt_prof_a_10: 5.75–17.27, fnrt_prof_b_10: 3.26–9.78, turnover_fnrt_10: 0.5–5.0), enabling correlation analysis BEFORE committing to an HPC run.

---

## Parameters to Modify

### fates_allom_fnrt_prof_a (PFT#10)
- **Current:** 12.332857142857142
- **Proposed:** 7.5
- **Rationale:** Reducing fnrt_prof_a_10 from 12.33 toward 7.5 shifts the root centroid shallower into the organic horizon (top 5-10 cm) where P and N are concentrated in tundra soils. Default=11, lower bound=5.75 — proposed value of 7.5 is within Morris bounds and represents the ecologically correct shallow root architecture for sedges/graminoids in the active layer.

### fates_allom_fnrt_prof_b (PFT#10)
- **Current:** 3.26
- **Proposed:** 7.5
- **Rationale:** Increasing fnrt_prof_b_10 from 3.26 (lower Morris bound) to 7.5 steepens the root profile decay with depth, concentrating a larger fraction of roots in the shallow organic horizon. This is the OPPOSITE of the diagnosis claim that parameters are 'backwards' — for Arctic graminoids, we want SHALLOW concentration, and higher b achieves this by making the exponential decay faster. Current value 3.26 is at the extreme lower bound, causing an unrealistically flat/deep root distribution.

### fates_turnover_fnrt (PFT#10)
- **Current:** 3.071428571428571
- **Proposed:** 4.5
- **Rationale:** Increasing fine root longevity from 3.07 yr to 4.5 yr reduces the annual carbon cost of root maintenance and replacement. Arctic tundra graminoids maintain fine roots for 3-6 years (Chapin et al. 1988, Jonasson & Chapin 1985). At 3.07 yr, PFT#10 spends excessive assimilated carbon on root turnover, preventing biomass accumulation. At 4.5 yr, the standing fineroot pool grows larger for the same carbon input. This is within the Morris sampling range [0.5, 5.0] and is physiologically realistic for cold-limited Arctic sedges.


---

## Expected Outcomes

- **froot_pft10:** Increase from near-zero toward 30-50 g C/m² as (a) root turnover cost decreases and (b) roots are better positioned in nutrient-rich horizon, increasing P/N uptake and reducing nutrient starvation
- **leaf_pft10:** Secondary improvement of 15-30% as reduced P starvation allows leaf allocation to proceed
- **froot_pft9:** Minimal change — PFT#9 fnrt_prof parameters unchanged; slight benefit if soil nutrient competition from PFT#10 decreases
- **froot_pft7:** No expected change — PFT#7 parameters unchanged

---

## Metadata

```json
{
  "iteration": 7,
  "diagnosis_count": 7,
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
  "validation": "ValidationResult(issues=[])"
}
```

---

## Iteration Context

```json
{
  "calibration_round": 4,
  "iteration": 7,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-04-14T11:01:20.798008",
  "site": "Kougarok",
  "session_id": "20260413_173425",
  "experiment_count": 0,
  "skip_testing_count": 6,
  "diagnosis_count": 7,
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
  "validation": "ValidationResult(issues=[])"
}
```
