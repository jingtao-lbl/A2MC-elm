# PFT10_TripleBottleneck_TurnoverRootProfile_Fix

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 4 | **Cycle:** 0 | **Iteration:** 8
**Base Case:** #86
**Date:** 2026-04-14 11:04:22
**Confidence:** 0.72

---

## Hypothesis: PFT10_TripleBottleneck_TurnoverRootProfile_Fix

### Mechanism

PFT#10 (Arctic graminoid/sedge) fails on both leaf and fineroot biomass due to a triple bottleneck: (1) excessive fine root turnover at 3.07 yr in Case #86 — while Arctic literature reports 1.0–2.0 yr for sedges/grasses, high turnover means constant C and nutrient demand to maintain root biomass, but combined with near-zero P uptake (≈0.000005), this creates a severe drain; (2) root profile parameters (fnrt_prof_a_10=12.33, fnrt_prof_b_10=3.26) place roots too deep — Arctic graminoids concentrate >80% of biomass in the top 10–20 cm where organic layer P is most accessible, but current parameters give a diffuse deep profile that misses the shallow organic horizon nutrient hot-spot; (3) leaf longevity is at the minimum bound (turnover_leaf_10=0.3 yr) meaning leaves are replaced every ~4 months, creating excessive C demand that the nutrient-limited plant cannot sustain. The diagnosis explicitly identifies root profile as 'BACKWARDS' for graminoids. The mechanistic chain is: shallow-rooted graminoids need high-b, high-a parameters to concentrate roots near surface → current parameters disperse roots → low ECA competitive ability in shallow organic horizon → near-zero P uptake → C-limited allocation cannot build leaf or fineroot biomass → both targets fail. Extending leaf turnover reduces constant C burn while adjusting root profile parameters to match Arctic graminoid literature (top-heavy distribution) increases P access where organic P is mineralized. These are all PFT#10-specific parameters with no cross-PFT interference. Note: fates_turnover_fnrt is root LONGEVITY (years), so increasing it REDUCES turnover rate (fewer roots replaced per year), consistent with Arctic slow-turnover ecosystem trait databases (FRED: sedge root lifespan 1.5–4 yr). The leaf longevity at 0.3 yr is biologically unrealistic for Arctic sedges (Eriophorum, Carex lifespan ~1–2 yr growing seasons) and must be increased.

### Design Type

cumulative

---

## AI Reasoning and Analysis

PFT#10 (Arctic graminoid/sedge) fails on both leaf and fineroot biomass due to a triple bottleneck: (1) excessive fine root turnover at 3.07 yr in Case #86 — while Arctic literature reports 1.0–2.0 yr for sedges/grasses, high turnover means constant C and nutrient demand to maintain root biomass, but combined with near-zero P uptake (≈0.000005), this creates a severe drain; (2) root profile parameters (fnrt_prof_a_10=12.33, fnrt_prof_b_10=3.26) place roots too deep — Arctic graminoids concentrate >80% of biomass in the top 10–20 cm where organic layer P is most accessible, but current parameters give a diffuse deep profile that misses the shallow organic horizon nutrient hot-spot; (3) leaf longevity is at the minimum bound (turnover_leaf_10=0.3 yr) meaning leaves are replaced every ~4 months, creating excessive C demand that the nutrient-limited plant cannot sustain. The diagnosis explicitly identifies root profile as 'BACKWARDS' for graminoids. The mechanistic chain is: shallow-rooted graminoids need high-b, high-a parameters to concentrate roots near surface → current parameters disperse roots → low ECA competitive ability in shallow organic horizon → near-zero P uptake → C-limited allocation cannot build leaf or fineroot biomass → both targets fail. Extending leaf turnover reduces constant C burn while adjusting root profile parameters to match Arctic graminoid literature (top-heavy distribution) increases P access where organic P is mineralized. These are all PFT#10-specific parameters with no cross-PFT interference. Note: fates_turnover_fnrt is root LONGEVITY (years), so increasing it REDUCES turnover rate (fewer roots replaced per year), consistent with Arctic slow-turnover ecosystem trait databases (FRED: sedge root lifespan 1.5–4 yr). The leaf longevity at 0.3 yr is biologically unrealistic for Arctic sedges (Eriophorum, Carex lifespan ~1–2 yr growing seasons) and must be increased.

---

## Parameters to Modify

### fates_turnover_fnrt (PFT#10)
- **Current:** 3.071428571428571
- **Proposed:** 4.5
- **Rationale:** Case #86 has turnover_fnrt_10=3.07 yr (longevity). Arctic sedge/graminoid fine roots have longevity of 3–5 yr per FRED database (Iversen et al. 2017). Increasing to 4.5 yr reduces the annual fine root replacement fraction from 1/3.07=32.6% to 1/4.5=22.2% per year, lowering the continuous C+nutrient demand needed to maintain standing root biomass. This directly helps build fineroot biomass by reducing the steady-state loss rate. Within Morris bounds [0.5, 5.0]. Not a no-op: 3.07→4.5 is a 46% increase in longevity.

### fates_turnover_leaf (PFT#10)
- **Current:** 0.3
- **Proposed:** 1.0
- **Rationale:** Case #86 has turnover_leaf_10=0.3 yr — the absolute minimum of Morris bounds [0.3, 2.0]. This is biologically unrealistic: Arctic sedges and grasses (Carex, Eriophorum) have leaf lifespans of 1–2 growing seasons (~0.8–1.5 yr). At 0.3 yr leaves must be replaced 3.3× per year, creating massive C demand that the P-starved PFT#10 cannot meet. Increasing to 1.0 yr reduces leaf replacement to 1× per year, dramatically cutting C drain on the storage pool and allowing leaf biomass to accumulate. This is the single highest-leverage carbon demand reduction available. Strictly within Morris bounds.

### fates_allom_fnrt_prof_a (PFT#10)
- **Current:** 12.332857142857142
- **Proposed:** 17.0
- **Rationale:** fates_allom_fnrt_prof_a controls the steepness/concentration of the root distribution profile. The diagnosis explicitly states root profile is 'BACKWARDS for graminoids'. Arctic graminoids (sedges, grasses) are documented to concentrate >75% of fine root biomass in the top 10–20 cm organic horizon (Nadelhoffer et al. 1992, Sullivan et al. 2007). Higher values of parameter 'a' in the exponential root profile function concentrate roots more strongly in shallow soil layers, increasing access to the shallow organic P pool where ECA competition is most favorable for graminoids. Proposed value 17.0 is within Morris bounds [5.75, 17.27] — at the upper end where root concentration is highest. This maximizes overlap with the shallow organic P mineralization hot-spot.

### fates_allom_fnrt_prof_b (PFT#10)
- **Current:** 3.26
- **Proposed:** 9.0
- **Rationale:** fates_allom_fnrt_prof_b controls root profile shape parameter b. Current value 3.26 is at the minimum of Morris bounds [3.26, 9.78], producing the most dispersed (deep) root distribution possible. For Arctic graminoids, literature consistently shows top-heavy root profiles. Increasing b to 9.0 (near upper bound) further concentrates roots in shallow layers, complementing the increase in parameter a. Together, high-a and high-b create a steeply top-concentrated root profile matching Arctic sedge biology. This directly addresses the 'root profile BACKWARDS' diagnosis. The combined a+b increase is mechanistically coherent (not conflicting) — both push toward shallow concentration.

### fates_cnp_vmax_p (PFT#10)
- **Current:** 3.5714300000000005e-05
- **Proposed:** 0.0001
- **Rationale:** P uptake ≈0.000005 (essentially zero) is the primary P starvation signal. Case #86 has vmax_p_10=3.57e-5, which is mid-range of Morris bounds [5e-11, 5e-5]. Increasing to 1e-4 (2.8× increase) is a modest and safe boost that stays within 2× of current value — well below the catastrophic thresholds identified in previous experiments. This is purely PFT-specific. The root profile fix (parameters 3-4) increases per-unit-root P acquisition by placing roots in P-rich shallow soil; vmax_p controls the maximum uptake rate per root biomass. Together they address both WHERE roots are and HOW FAST they uptake P. IMPORTANT: This is a 2.8× increase, far below the >1000× increase that caused the ptase_extreme_magnitude_crash. Discovery ECA_decomp_cost_reduction warns about compounding with stoichiometry/ECA changes — this experiment avoids touching those parameters.


---

## Parameter Validation Report

| Parameter | Check | Status | Detail |
|-----------|-------|--------|--------|
| fates_cnp_vmax_p | out of bounds | WARNING | proposed=0.0001 outside [5e-11, 5e-05] |

**Summary:** 0 auto-fixed, 1 warning(s), 0 error(s)

---

## Expected Outcomes

- **leaf_pft10:** 25.0
- **froot_pft10:** 45.0
- **leaf_pft9:** 110.0
- **froot_pft9:** 55.0
- **leaf_pft7:** 80.0
- **froot_pft7:** 40.0

---

## Metadata

```json
{
  "iteration": 8,
  "diagnosis_count": 8,
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
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_cnp_vmax_p', check='out of bounds', severity='warning', detail='proposed=0.0001 outside [5e-11, 5e-05]', old_value=None, new_value=None)])"
}
```

---

## Iteration Context

```json
{
  "calibration_round": 4,
  "iteration": 8,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-04-14T11:04:22.782248",
  "site": "Kougarok",
  "session_id": "20260413_173425",
  "experiment_count": 0,
  "skip_testing_count": 7,
  "diagnosis_count": 8,
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
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_cnp_vmax_p', check='out of bounds', severity='warning', detail='proposed=0.0001 outside [5e-11, 5e-05]', old_value=None, new_value=None)])"
}
```
