# PFT10_TripleBottleneck_FineRoot_Biomass_Recovery

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 4 | **Cycle:** 0 | **Iteration:** 10
**Base Case:** #86
**Date:** 2026-04-14 11:10:52
**Confidence:** 0.72

---

## Hypothesis: PFT10_TripleBottleneck_FineRoot_Biomass_Recovery

### Mechanism

PFT#10 (Arctic graminoid/sedge) fineroot and leaf biomass are severely underestimated due to three compounding deficiencies operating in sequence: (1) Excessive fine root turnover — at turnover_fnrt_10=3.07 yr the standing stock is maintained at chronic deficit because the high turnover rate demands proportionally high P/N flux just to maintain existing roots, creating a negative feedback where P limitation prevents root growth which prevents P acquisition; (2) Root profile parameters are ecologically inverted — fnrt_prof_b_10=3.26 (lower bound) concentrates roots in shallow layers while Arctic graminoids/sedges have functionally deep root systems relative to their size to access nutrients in deeper thawed active layer; (3) The l2fr_ini_10=3.62 (high leaf-to-root ratio) forces the plant to allocate more C to leaves than roots during initialization, which starves the root system of C precisely when roots are needed to acquire P. The mechanistic chain: high l2fr_ini → insufficient fineroot C target → low root biomass → low P acquisition → P starvation → allocation shifts worsen → leaf biomass also collapses. Importantly, turnover_fnrt_10 is the PRIMARY bottleneck: increasing it from 3.07 to 4.5 yr reduces daily C turnover cost by ~32%, immediately freeing C for pool expansion. Simultaneously reducing l2fr_ini_10 from 3.62 to 1.5 rebalances initial organ targets toward roots. Root profile adjustment (increasing fnrt_prof_b_10 from 3.26 toward 7.0) redistributes roots to deeper soil layers where mineral P is less microbially competed. These three changes are cumulative (sequential bottleneck removal) and all PFT#10-specific, preventing cross-PFT degradation.

### Design Type

cumulative

---

## AI Reasoning and Analysis

PFT#10 (Arctic graminoid/sedge) fineroot and leaf biomass are severely underestimated due to three compounding deficiencies operating in sequence: (1) Excessive fine root turnover — at turnover_fnrt_10=3.07 yr the standing stock is maintained at chronic deficit because the high turnover rate demands proportionally high P/N flux just to maintain existing roots, creating a negative feedback where P limitation prevents root growth which prevents P acquisition; (2) Root profile parameters are ecologically inverted — fnrt_prof_b_10=3.26 (lower bound) concentrates roots in shallow layers while Arctic graminoids/sedges have functionally deep root systems relative to their size to access nutrients in deeper thawed active layer; (3) The l2fr_ini_10=3.62 (high leaf-to-root ratio) forces the plant to allocate more C to leaves than roots during initialization, which starves the root system of C precisely when roots are needed to acquire P. The mechanistic chain: high l2fr_ini → insufficient fineroot C target → low root biomass → low P acquisition → P starvation → allocation shifts worsen → leaf biomass also collapses. Importantly, turnover_fnrt_10 is the PRIMARY bottleneck: increasing it from 3.07 to 4.5 yr reduces daily C turnover cost by ~32%, immediately freeing C for pool expansion. Simultaneously reducing l2fr_ini_10 from 3.62 to 1.5 rebalances initial organ targets toward roots. Root profile adjustment (increasing fnrt_prof_b_10 from 3.26 toward 7.0) redistributes roots to deeper soil layers where mineral P is less microbially competed. These three changes are cumulative (sequential bottleneck removal) and all PFT#10-specific, preventing cross-PFT degradation.

---

## Parameters to Modify

### fates_turnover_fnrt (PFT#10)
- **Current:** 3.071428571428571
- **Proposed:** 4.5
- **Rationale:** Increasing fine root longevity from 3.07 to 4.5 yr reduces daily turnover cost by ~32%, directly increasing steady-state fineroot biomass. Arctic graminoids (e.g., Eriophorum, Carex) have measured root lifespans of 3-6 yr in tundra, and current value is already high but the upper Morris bound of 5.0 is justified. At 4.5 yr, the C required to maintain root pool declines, allowing net root C accumulation. This is the highest-priority bottleneck as it directly sets the equilibrium fineroot pool size via biomass = production_rate × longevity.

### fates_allom_l2fr (PFT#10)
- **Current:** 3.6191324047142857
- **Proposed:** 1.3
- **Rationale:** The current l2fr_ini_10=3.62 sets an initial leaf:fineroot C ratio target 3.62x higher than roots, meaning at initialization the plant targets far more leaf C than fineroot C. Arctic graminoids are known to invest heavily in roots relative to leaves (measured l2fr typically 0.8-2.0 in tundra). Reducing to 1.3 shifts initial allocation toward roots, increasing fineroot target biomass from the start of simulation. This directly addresses the 'root starvation at initialization' bottleneck. Value 1.3 is within Morris bounds [1.115, 9.879] and represents the lower-bound region appropriate for a root-heavy tundra PFT.

### fates_allom_fnrt_prof_b (PFT#10)
- **Current:** 3.26
- **Proposed:** 7.0
- **Rationale:** fnrt_prof_b controls the depth distribution shape of fine roots. Current value of 3.26 (at the Morris lower bound) concentrates roots very shallowly. In the ECA framework, shallow roots compete intensely with microbes in the organic horizon where microbial P immobilization is highest. Arctic graminoids/sedges root into the mineral active layer (15-40cm depth) where inorganic P availability is relatively higher and microbial competition lower. Increasing from 3.26 to 7.0 (midpoint of Morris range [3.26, 9.78]) redistributes roots deeper, reducing direct competition with microbes for P and improving per-root P acquisition efficiency. This is flagged as 'parameters BACKWARDS' in the diagnosis.


---

## Expected Outcomes

- **froot_pft10:** 35.0
- **leaf_pft10:** 18.0
- **froot_pft9:** 55.0
- **leaf_pft9:** 110.0
- **froot_pft7:** 40.0
- **leaf_pft7:** 85.0

---

## Metadata

```json
{
  "iteration": 10,
  "diagnosis_count": 10,
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
  "iteration": 10,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-04-14T11:10:52.818671",
  "site": "Kougarok",
  "session_id": "20260413_173425",
  "experiment_count": 0,
  "skip_testing_count": 9,
  "diagnosis_count": 10,
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
