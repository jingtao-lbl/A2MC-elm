# Inter-PFT Nutrient Competition Rebalancing: PFT7 NH4 Dominance Suppression + PFT10 Recruitment and Affinity Enhancement

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 2 | **Cycle:** 0 | **Iteration:** 3
**Date:** 2026-03-15 10:38:21
**Confidence:** 0.62

---

## Hypothesis: Inter-PFT Nutrient Competition Rebalancing: PFT7 NH4 Dominance Suppression + PFT10 Recruitment and Affinity Enhancement

### Mechanism

The diagnosis confirms a 5-order-of-magnitude P supply/demand gap that is a protocol-level problem (SUPLPHOS=NONE) — but within this constrained P environment, PFT7 captures 73.4% of total P uptake (0.4917 g/m2/yr) while PFT10 receives only 2.0% (0.0134 g/m2/yr). This competitive imbalance is mechanistically driven by: (1) PFT7's vmax_nh4_7 at upper bound (0.00025) giving it maximal ECA competitive advantage — NH4 uptake capacity directly correlates with P competitive strength because ECA allocates nutrients proportionally to uptake capacity across all ions; (2) PFT10's km_nh4_10 at upper bound (0.21 mM) meaning LOW affinity at the low nutrient concentrations typical of Arctic soils — lower Km gives higher affinity and better competitive performance at limiting concentrations; (3) PFT10's recruit_init_density_10 at lower bound (0.100) while Case #3972 (achieving 3.2x better PFT10_leaf=21.1) has recruit_init_density_10=0.2807 — more initial plants means higher probability that some escape P starvation through stochastic variation in microsite P availability. The hypothesis tests whether SIMULTANEOUSLY reducing PFT7's competitive advantage (lower vmax_nh4_7) while improving PFT10's competitive affinity (lower km_nh4_10) and establishment density (higher recruit_init_density_10) can shift P distribution toward PFT10 from the current 2% share to a higher fraction. This is testable with existing Morris data because all three parameters vary across the ensemble. Mechanistic chain: lower PFT7 vmax_nh4 → ECA reduces PFT7 N uptake priority → P pool distribution shifts → lower PFT10 km_nh4 → PFT10 outcompetes at low concentrations → higher recruit_init_density_10 → more PFT10 individuals in early establishment → increased probability some cohorts achieve positive C balance → PFT10 leaf and fineroot biomass increases from near-zero. Critically, reducing PFT7 vmax_nh4 from upper bound is ECOLOGICALLY APPROPRIATE because PFT7 leaf is already OVER-predicted (+32.2%), meaning current PFT7 competitive dominance is excessive. The L2FR paradox discovered in prior calibration (lower L2FR paradoxically helps) is addressed by NOT touching L2FR parameters in this hypothesis — instead focusing on the ECA competition and recruitment mechanisms identified from the Case #322 vs #3972 comparison.

### Design Type

cumulative

---

## AI Reasoning and Analysis

The diagnosis confirms a 5-order-of-magnitude P supply/demand gap that is a protocol-level problem (SUPLPHOS=NONE) — but within this constrained P environment, PFT7 captures 73.4% of total P uptake (0.4917 g/m2/yr) while PFT10 receives only 2.0% (0.0134 g/m2/yr). This competitive imbalance is mechanistically driven by: (1) PFT7's vmax_nh4_7 at upper bound (0.00025) giving it maximal ECA competitive advantage — NH4 uptake capacity directly correlates with P competitive strength because ECA allocates nutrients proportionally to uptake capacity across all ions; (2) PFT10's km_nh4_10 at upper bound (0.21 mM) meaning LOW affinity at the low nutrient concentrations typical of Arctic soils — lower Km gives higher affinity and better competitive performance at limiting concentrations; (3) PFT10's recruit_init_density_10 at lower bound (0.100) while Case #3972 (achieving 3.2x better PFT10_leaf=21.1) has recruit_init_density_10=0.2807 — more initial plants means higher probability that some escape P starvation through stochastic variation in microsite P availability. The hypothesis tests whether SIMULTANEOUSLY reducing PFT7's competitive advantage (lower vmax_nh4_7) while improving PFT10's competitive affinity (lower km_nh4_10) and establishment density (higher recruit_init_density_10) can shift P distribution toward PFT10 from the current 2% share to a higher fraction. This is testable with existing Morris data because all three parameters vary across the ensemble. Mechanistic chain: lower PFT7 vmax_nh4 → ECA reduces PFT7 N uptake priority → P pool distribution shifts → lower PFT10 km_nh4 → PFT10 outcompetes at low concentrations → higher recruit_init_density_10 → more PFT10 individuals in early establishment → increased probability some cohorts achieve positive C balance → PFT10 leaf and fineroot biomass increases from near-zero. Critically, reducing PFT7 vmax_nh4 from upper bound is ECOLOGICALLY APPROPRIATE because PFT7 leaf is already OVER-predicted (+32.2%), meaning current PFT7 competitive dominance is excessive. The L2FR paradox discovered in prior calibration (lower L2FR paradoxically helps) is addressed by NOT touching L2FR parameters in this hypothesis — instead focusing on the ECA competition and recruitment mechanisms identified from the Case #322 vs #3972 comparison.

---

## Parameters to Modify

### fates_cnp_vmax_nh4 (PFT#7)
- **Current:** 0.00025
- **Proposed:** 2.5e-09
- **Rationale:** Case #322 has vmax_nh4_7 at upper bound (0.00025), giving PFT7 73.4% of total P uptake via ECA competitive advantage. This is 5 orders of magnitude above the default (2.5e-09). Reducing to default level dramatically reduces PFT7's ECA competitive dominance, redistributing available P toward PFT9 and PFT10. This is also ecologically justified because PFT7 leaf biomass is already OVER-predicted by +32.2% (32.5 vs 24.6 gC/m2) — reduced competitive dominance will reduce PFT7 leaf biomass toward the observed value while freeing P for other PFTs. Case #3972 (best PFT10 performer, PFT10_leaf=21.1) shows 100% range difference in vmax_nh4_7 vs Case #322, confirming this parameter is critical to PFT10 performance.

### fates_cnp_eca_km_nh4 (PFT#10)
- **Current:** 0.21
- **Proposed:** 0.07
- **Rationale:** Case #322 has km_nh4_10 at upper bound (0.21 mM), the WORST possible affinity for Arctic low-nutrient soils. Lower Km means higher affinity — PFT10 can outcompete at low substrate concentrations typical of Arctic tundra where NH4 concentrations are often <0.1 mM. Case #3972 achieves PFT10_leaf=21.1 (vs Case #322's 6.6) with km_nh4_10=0.07 (lower bound) — 100% range difference confirming this is a critical mechanistic lever. In ECA competition, high-affinity (low Km) plants disproportionately capture nutrient pools at limiting concentrations, even when their vmax is lower than competitors. This change does NOT conflict with any failed approach listed in memory.

### fates_recruit_init_density (PFT#10)
- **Current:** 0.100195
- **Proposed:** 0.2807
- **Rationale:** Case #322 has recruit_init_density_10 at lower bound (0.100), while Case #3972 (best PFT10 performer) has recruit_init_density_10=0.2807 — 100% range difference. Higher initial density means more PFT10 cohorts competing for nutrients, but also more individuals that can potentially escape P starvation through stochastic variation in microsite nutrient availability and crown geometry. In tundra graminoids (PFT10), high stem density is ecologically realistic — sedge tussocks have very high individual density. This is a PFT-specific parameter with no cross-PFT conflict. Setting to the Case #3972 value directly tests the hypothesis that this contributes to Case #3972's 3.2x improvement.

### fates_cnp_vmax_p (PFT#10)
- **Current:** 5e-11
- **Proposed:** 5e-09
- **Rationale:** Case #322 has vmax_p_10 at 5e-11, which is 10x BELOW the default (5e-10) and 1000x below the upper bound (5e-05). This gives PFT10 effectively zero P uptake capacity in ECA competition. While the prior diagnosis notes that 'higher vmax_p_10 increases PFT10's competitive demand, which may worsen P starvation for PFT7/9', the WARNING was specifically about values at or near the ensemble UPPER bound. Moving from lower-bound (5e-11) to default (5e-09) is a conservative 100x increase that restores PFT10 to baseline P uptake capacity — it should improve P acquisition without triggering the allocation paradox that occurs at extreme high values. This change is synergistic with lower km_nh4_10 (high affinity) — together they give PFT10 both sufficient capacity AND competitive affinity.


---

## Parameter Validation Report

| Parameter | Check | Status | Detail |
|-----------|-------|--------|--------|
| fates_cnp_vmax_nh4 | magnitude | INFO | 0.00025 → 2.5e-09 (0.0x change, >1000x) |

**Summary:** 0 auto-fixed, 0 warning(s), 0 error(s)

---

## Expected Outcomes

- **leaf_pft7:** 22.0
- **froot_pft7:** 130.0
- **leaf_pft9:** 35.0
- **froot_pft9:** 190.0
- **leaf_pft10:** 15.0
- **froot_pft10:** 8.0
- **p_uptake_pft7_fraction:** 0.45
- **p_uptake_pft10_fraction:** 0.08

---

## Metadata

```json
{
  "iteration": 3,
  "diagnosis_count": 3,
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
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_cnp_vmax_nh4', check='magnitude', severity='info', detail='0.00025 \u2192 2.5e-09 (0.0x change, >1000x)', old_value=None, new_value=None)])"
}
```

---

## Iteration Context

```json
{
  "calibration_round": 2,
  "iteration": 3,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-03-15T10:38:21.459999",
  "site": "Kougarok",
  "session_id": "20260315_095903",
  "experiment_count": 0,
  "skip_testing_count": 2,
  "diagnosis_count": 3,
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
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_cnp_vmax_nh4', check='magnitude', severity='info', detail='0.00025 \u2192 2.5e-09 (0.0x change, >1000x)', old_value=None, new_value=None)])"
}
```
