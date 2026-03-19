# ECA Competition Rebalancing via Complementary PFT Parameter Rescue: Case #1386 Parameter Profile with PFT9 L2FR Correction

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 2 | **Cycle:** 0 | **Iteration:** 6
**Date:** 2026-03-15 11:04:39
**Confidence:** 0.72

---

## Hypothesis: ECA Competition Rebalancing via Complementary PFT Parameter Rescue: Case #1386 Parameter Profile with PFT9 L2FR Correction

### Mechanism

The diagnosis identifies a fundamental competitive asymmetry in the ECA nutrient uptake system: Case #322 has vmax_nh4_7=0.00025 (1000x default, upper bound), causing PFT7 to monopolize 73.4% of total P uptake (0.4917 g/m2/yr), while PFT10 receives only 2% and PFT9 receives 24.6%. Simultaneously, Case #1386 achieves PFT10_leaf=37.0 g/m2 (vs #322's 6.6) through a different competition balance, but suffers PFT9_leaf collapse (5.67 g/m2). This hypothesis proposes that the optimal parameter configuration exists in the intersection of #1386's PFT10-favorable competition dynamics (low vmax_nh4_7, low km_nh4_10, high recruit_init_density_10, elevated vmax_p_10) combined with the confirmed PFT9 leaf rescue mechanism (l2fr_ini_9 reduction from 18.31 to mid-range ~5.0, exploiting the confirmed r=-0.257 monotone relationship). The mechanistic chain is: [reduce PFT7 NH4 competitive dominance] → [release P to PFT9 and PFT10] → [increase PFT10 P uptake capacity via vmax_p_10 and recruit_init_density_10] → [shift PFT9 C allocation from roots to leaves via l2fr_ini_9 reduction] → [simultaneous improvement in PFT10_leaf, PFT10_froot, PFT9_leaf while keeping PFT7_leaf near its 24.55 target and preserving PFT9_froot near its 187.35 target]. The hypothesis is testable within the existing ensemble by identifying cases that jointly satisfy: low vmax_nh4_7 (<1e-8), low km_nh4_10 (<0.10), moderate l2fr_ini_9 (2.0-8.0), and elevated recruit_init_density_10 (>0.20).

### Design Type

cumulative

---

## AI Reasoning and Analysis

The diagnosis identifies a fundamental competitive asymmetry in the ECA nutrient uptake system: Case #322 has vmax_nh4_7=0.00025 (1000x default, upper bound), causing PFT7 to monopolize 73.4% of total P uptake (0.4917 g/m2/yr), while PFT10 receives only 2% and PFT9 receives 24.6%. Simultaneously, Case #1386 achieves PFT10_leaf=37.0 g/m2 (vs #322's 6.6) through a different competition balance, but suffers PFT9_leaf collapse (5.67 g/m2). This hypothesis proposes that the optimal parameter configuration exists in the intersection of #1386's PFT10-favorable competition dynamics (low vmax_nh4_7, low km_nh4_10, high recruit_init_density_10, elevated vmax_p_10) combined with the confirmed PFT9 leaf rescue mechanism (l2fr_ini_9 reduction from 18.31 to mid-range ~5.0, exploiting the confirmed r=-0.257 monotone relationship). The mechanistic chain is: [reduce PFT7 NH4 competitive dominance] → [release P to PFT9 and PFT10] → [increase PFT10 P uptake capacity via vmax_p_10 and recruit_init_density_10] → [shift PFT9 C allocation from roots to leaves via l2fr_ini_9 reduction] → [simultaneous improvement in PFT10_leaf, PFT10_froot, PFT9_leaf while keeping PFT7_leaf near its 24.55 target and preserving PFT9_froot near its 187.35 target]. The hypothesis is testable within the existing ensemble by identifying cases that jointly satisfy: low vmax_nh4_7 (<1e-8), low km_nh4_10 (<0.10), moderate l2fr_ini_9 (2.0-8.0), and elevated recruit_init_density_10 (>0.20).

---

## Parameters to Modify

### fates_cnp_vmax_nh4 (PFT#7)
- **Current:** 0.00025
- **Proposed:** 2.5e-10
- **Rationale:** Case #322 has vmax_nh4_7 at the upper bound (1000x default), conferring PFT7 monopolistic P capture (73.4% of 0.67 g/m2/yr total P uptake). Reducing to lower bound (1000x reduction) matches Case #1386's competitive balance and is doubly justified: (1) PFT7_leaf is OVER-predicted (+32.2%, 32.5 vs 24.55 target), so reducing PFT7's competitive advantage will help correct this overprediction; (2) Released P will flow to PFT9 and PFT10 via ECA. Skip-test confirmed r=-0.198 (p<1e-44) for this parameter vs PFT10 leaf biomass.

### fates_cnp_eca_km_nh4 (PFT#10)
- **Current:** 0.21
- **Proposed:** 0.07
- **Rationale:** Case #322 has km_nh4_10 at the worst-possible upper bound (0.21 mM), making PFT10 nearly non-competitive for NH4 at Arctic soil concentrations. Lower km means higher substrate affinity at low concentrations, which is critical in P-scarce Arctic tundra. Skip-test confirmed r=-0.093 (p<1e-10). Case #3972 (lower bound km_nh4_10=0.07) achieves 3.2x PFT10_leaf improvement. Must be combined with vmax_nh4_7 reduction for full effect; composite r=0.273 (p<1e-84).

### fates_allom_l2fr (PFT#9)
- **Current:** 18.31
- **Proposed:** 5.0
- **Rationale:** The strongest confirmed single predictor of PFT9 leaf biomass: r=-0.257 (p<1e-75) with monotone decrease verified across quartiles. Case #322 has l2fr_ini_9 at the extreme upper bound (18.31), forcing massive C allocation to fine roots at the expense of leaf growth. PFT9_leaf=26.6 vs target 124.7 (-78.7%). Reducing to 5.0 (mid-lower range) is calibrated to: (a) substantially improve leaf allocation; (b) preserve PFT9_froot near its passing target (187.35) — using 5.0 rather than minimum 0.01 as a conservative balance. This directly corrects Case #1386's PFT9 collapse (which has l2fr_ini_9 near the upper bound causing PFT9_leaf=5.67).

### fates_recruit_init_density (PFT#10)
- **Current:** 0.1
- **Proposed:** 0.281
- **Rationale:** Case #322 has recruit_init_density_10 at the lower bound (0.100 stems/m2). Skip-test r=0.110 (p<1e-14). Higher initial cohort density increases collective PFT10 fine root biomass and thus P acquisition surface in the ECA framework. Case #3972 (recruit_init_density_10=0.281, upper bound) achieves 3.2x PFT10_leaf improvement compared to lower-bound cases. Must be paired with vmax_nh4_7 reduction to ensure P is available to the increased PFT10 root biomass.

### fates_cnp_vmax_p (PFT#10)
- **Current:** 5e-11
- **Proposed:** 5e-09
- **Rationale:** Case #322 has vmax_p_10 at the lower bound (5e-11, 10x below default 5e-10), nearly eliminating PFT10 direct P acquisition via ECA. Increasing to 5e-09 (10x default, conservative within ensemble bounds [5e-11, 5e-05]) increases PFT10's maximum P uptake rate. Log-linear correlation confirmed: r=0.145 (p<1e-24) for log(vmax_p_10) vs PFT10 leaf. allocation_paradox_signal=False for conservative increases confirmed in previous diagnostics. Value of 5e-09 is well below the paradox-triggering zone (>1e-05).

### fates_allom_l2fr (PFT#10)
- **Current:** 9.879
- **Proposed:** 4.0
- **Rationale:** Case #322 has l2fr_ini_10 at the upper bound (9.879, ensemble range [1.115, 9.879]). Although the unconditional correlation is weak (r=0.021), the conditional correlation r=0.266 (p=0.000) when conditioned on high P availability cases suggests this parameter becomes critical once P starvation is partially relieved by the higher-priority changes above. Reducing from 9.879 to 4.0 (mid-range) allows more C to flow toward leaf allocation once P is available. Applied as a SECONDARY adjustment — its effect depends on successful P redistribution from Parameters 1-4.


---

## Parameter Validation Report

| Parameter | Check | Status | Detail |
|-----------|-------|--------|--------|
| fates_cnp_vmax_nh4 | magnitude | INFO | 0.00025 → 2.5e-10 (0.0x change, >1000x) |

**Summary:** 0 auto-fixed, 0 warning(s), 0 error(s)

---

## Expected Outcomes

- **PFT7_leaf_gCm2:** 20.0
- **PFT7_fineroot_gCm2:** 130.0
- **PFT9_leaf_gCm2:** 85.0
- **PFT9_fineroot_gCm2:** 175.0
- **PFT10_leaf_gCm2:** 35.0
- **PFT10_fineroot_gCm2:** 150.0
- **rationale:** Conservative estimates. PFT7_leaf expected to decrease from 32.5 toward target 24.55 as vmax_nh4_7 is reduced (currently over-predicted by 32%). PFT9_leaf expected to increase from 26.6 toward 85 (still short of 124.7 target but 3x improvement from l2fr correction). PFT10_leaf expected to increase from 6.6 toward 35 (matching Case #1386 pattern from competition rebalancing). PFT9_froot may decrease slightly from 191.8 toward 175 due to l2fr_ini_9 reallocation — still within ±20% of 187.35 target. PFT10_froot expected to increase substantially from 16.9 toward 150 (still short of 382.05 due to structural P deficit, but a 9x improvement). All estimates assume SUPLPHOS=NONE protocol constraint remains unchanged; structural P deficit (0.857 g/m2/yr supply vs demand) caps achievable PFT10 biomass at approximately 37-50 g/m2 leaf per Case #1386 evidence.

---

## Metadata

```json
{
  "iteration": 6,
  "diagnosis_count": 6,
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
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_cnp_vmax_nh4', check='magnitude', severity='info', detail='0.00025 \u2192 2.5e-10 (0.0x change, >1000x)', old_value=None, new_value=None)])"
}
```

---

## Iteration Context

```json
{
  "calibration_round": 2,
  "iteration": 6,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-03-15T11:04:39.579171",
  "site": "Kougarok",
  "session_id": "20260315_095903",
  "experiment_count": 0,
  "skip_testing_count": 5,
  "diagnosis_count": 6,
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
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_cnp_vmax_nh4', check='magnitude', severity='info', detail='0.00025 \u2192 2.5e-10 (0.0x change, >1000x)', old_value=None, new_value=None)])"
}
```
