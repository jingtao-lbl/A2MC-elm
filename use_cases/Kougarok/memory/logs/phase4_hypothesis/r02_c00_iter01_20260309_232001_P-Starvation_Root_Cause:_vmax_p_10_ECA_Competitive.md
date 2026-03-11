# P-Starvation Root Cause: vmax_p_10 ECA Competitive Exclusion + Stoichiometric Demand Reduction

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 2 | **Cycle:** 0 | **Iteration:** 1
**Date:** 2026-03-09 23:45:57
**Confidence:** 0.62

---

## Hypothesis: P-Starvation Root Cause: vmax_p_10 ECA Competitive Exclusion + Stoichiometric Demand Reduction

### Mechanism

Case #322 shows PFT#10 (Arctic graminoid) capturing only 2.0% of total P uptake (0.013 g/m2/yr) while its vmax_p_10 sits at the absolute lower bound (5e-11 kg_nutrient/kg_fineroot_C/s). In the ECA competition framework, P uptake share is proportional to vmax × root_biomass / (km_p + total_competitive_demand). With vmax_p_10 at 5e-11 and PFT7's vmax_p_7 at 2.86e-05 (570,000x higher), PFT#10 is mathematically excluded from P acquisition regardless of root investment. Simultaneously, stoich_phos_leaf_10 = 0.00299 defines the P requirement per unit leaf C — at arctic-adapted lower stoichiometry (0.0015), the same P supply could sustain twice the leaf biomass. The hypothesis is: a moderate 100x increase in vmax_p_10 (from 5e-11 to 5e-9, within the ensemble sampling range) combined with reduced leaf P stoichiometry for PFT#10 will shift ECA P allocation toward PFT#10 and reduce its per-unit P demand, enabling leaf and fineroot biomass recovery. This tests whether the ECA competitive exclusion is the primary bottleneck for PFT#10 failure, or whether systemic P starvation across all PFTs prevents any single-PFT vmax change from helping.

### Design Type

cumulative

---

## AI Reasoning and Analysis

Case #322 shows PFT#10 (Arctic graminoid) capturing only 2.0% of total P uptake (0.013 g/m2/yr) while its vmax_p_10 sits at the absolute lower bound (5e-11 kg_nutrient/kg_fineroot_C/s). In the ECA competition framework, P uptake share is proportional to vmax × root_biomass / (km_p + total_competitive_demand). With vmax_p_10 at 5e-11 and PFT7's vmax_p_7 at 2.86e-05 (570,000x higher), PFT#10 is mathematically excluded from P acquisition regardless of root investment. Simultaneously, stoich_phos_leaf_10 = 0.00299 defines the P requirement per unit leaf C — at arctic-adapted lower stoichiometry (0.0015), the same P supply could sustain twice the leaf biomass. The hypothesis is: a moderate 100x increase in vmax_p_10 (from 5e-11 to 5e-9, within the ensemble sampling range) combined with reduced leaf P stoichiometry for PFT#10 will shift ECA P allocation toward PFT#10 and reduce its per-unit P demand, enabling leaf and fineroot biomass recovery. This tests whether the ECA competitive exclusion is the primary bottleneck for PFT#10 failure, or whether systemic P starvation across all PFTs prevents any single-PFT vmax change from helping.

---

## Parameters to Modify

### fates_cnp_vmax_p
- **Current:** 5e-11
- **Proposed:** 5e-09
- **Rationale:** Case #322 has vmax_p_10 at absolute lower bound (5e-11), giving PFT#10 near-zero competitive ability in ECA. A 100x increase to 5e-9 is within the ensemble sampling range [5e-11, 5e-5] and moves vmax_p_10 closer to the midpoint of the log-scale range. This should shift ECA P allocation from 2% toward 5-15% for PFT#10, enabling meaningful P acquisition without creating a massive demand amplification (100x vmax increase on minimal root biomass yields modest total demand change).

### fates_stoich_phos
- **Current:** 0.002994719
- **Proposed:** 0.0015
- **Rationale:** Leaf P stoichiometry for PFT#10 (stoich_phos_leaf_10 = 0.00299) is near the upper bound of the arctic-adapted range. Arctic graminoids (sedges, grasses) typically have leaf P concentrations of 0.8-1.5 mg P/g DM, corresponding to stoich_phos of 0.001-0.0015. Reducing from 0.00299 to 0.0015 halves the per-unit leaf P requirement, directly reducing the P demand that drives ECA competition, and potentially reducing the PID controller's allocation-to-roots signal, allowing more C to flow to leaves.

### fates_stoich_phos
- **Current:** 0.0009434478571428572
- **Proposed:** 0.00075
- **Rationale:** Fineroot P stoichiometry for PFT#10 (stoich_phos_fineroot_10 = 0.000943) is also above arctic literature values for graminoid fine roots (~0.5-0.8 mg P/g DM). Reducing to 0.00075 reduces P demand from root biomass investment, breaking the positive feedback loop where large root investment generates impossible P demand. This is a modest 20% reduction within the ensemble range [0.000709198, 0.001255781].

### fates_cnp_eca_vmax_ptase
- **Current:** 5e-10
- **Proposed:** 5e-08
- **Rationale:** Case #322 has vmax_ptase_10 at lower bound (5e-10), minimizing biochemical P mineralization driven by PFT#10. The P mass balance shows BIOCHEM_PMIN = 0.533 g/m2/yr is a significant P source. A 100x increase to 5e-8 (within ensemble range [5e-10, 5e-4]) gives PFT#10 access to organic P mineralization via phosphatase, supplementing direct P uptake. Note: phosphatase evidence was weak (confidence 0.04 from prior test) but the biochemical P pathway is mechanistically important when direct uptake is ECA-limited.

### fates_allom_l2fr
- **Current:** 9.879038859
- **Proposed:** 3.0
- **Rationale:** Case #322 has l2fr_ini_10 = 9.88 (at upper bound), generating an extremely large fine root C pool that amplifies P demand in ECA (demand = fnrt_c × vmax). From the diagnosis, this creates a positive feedback: PID controller increases l2fr to acquire more P, but more roots means more P demand, deepening starvation. Reducing l2fr_ini_10 from 9.88 to 3.0 (within ensemble range [1.115, 9.879]) reduces initial root investment, lowering total P demand while maintaining capacity for P uptake. Ecologically appropriate for arctic graminoids.


---

## Expected Outcomes

- **leaf_pft10:** 25.0
- **froot_pft10:** 50.0
- **leaf_pft9:** 120.0
- **froot_pft9:** 180.0
- **leaf_pft7:** 85.0
- **froot_pft7:** 180.0

---

## Metadata

```json
{
  "iteration": 1,
  "diagnosis_count": 1,
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
  "iteration": 1,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-03-09T23:45:57.240212",
  "site": "Kougarok",
  "session_id": "20260309_232001",
  "experiment_count": 0,
  "skip_testing_count": 0,
  "diagnosis_count": 1,
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
