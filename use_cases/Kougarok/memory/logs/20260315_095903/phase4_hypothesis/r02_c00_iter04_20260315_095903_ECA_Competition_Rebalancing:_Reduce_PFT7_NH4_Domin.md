# ECA Competition Rebalancing: Reduce PFT7 NH4 Dominance to Redistribute P toward PFT10

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 2 | **Cycle:** 0 | **Iteration:** 4
**Date:** 2026-03-15 10:46:08
**Confidence:** 0.72

---

## Hypothesis: ECA Competition Rebalancing: Reduce PFT7 NH4 Dominance to Redistribute P toward PFT10

### Mechanism

In ECA (Enzyme Competition Approach) mode, PFT7's vmax_nh4=0.00025 (upper bound, 1000x default) gives it maximal competitive dominance for soil NH4 and — through coupled ECA competition — for P. Case #322 shows PFT7 captures 73.4% of total P uptake, leaving PFT10 only 2.0% (0.013 g/m2/yr). Case #3972 demonstrates that setting vmax_nh4_7=2.5e-10 (lower bound) + km_nh4_10=0.07 (lower bound) achieves PFT10_leaf=21.1 vs Case #322's 6.6 — a 3.2x improvement from ECA redistribution alone. The mechanism is: lower PFT7 vmax_nh4 reduces PFT7 competitive ECA 'enzyme investment', freeing substrate for PFT10; simultaneously, lower PFT10 km_nh4 increases PFT10 affinity at low Arctic NH4 concentrations (NH4 << 0.21 mM), enabling PFT10 to compete more effectively for scarce substrate. Secondary intervention: increasing recruit_init_density_10 from lower bound (0.100) to 0.281 increases PFT10 cohort representation, raising collective P acquisition probability. Tertiary: reducing l2fr_ini_9 from upper bound (18.31) to mid-range (6.0) corrects PFT9 leaf underestimation by rebalancing carbon allocation toward leaves from overinvested fine roots. The cumulative design ensures each change adds mechanistic benefit sequentially without cross-parameter conflicts.

### Design Type

cumulative

---

## AI Reasoning and Analysis

In ECA (Enzyme Competition Approach) mode, PFT7's vmax_nh4=0.00025 (upper bound, 1000x default) gives it maximal competitive dominance for soil NH4 and — through coupled ECA competition — for P. Case #322 shows PFT7 captures 73.4% of total P uptake, leaving PFT10 only 2.0% (0.013 g/m2/yr). Case #3972 demonstrates that setting vmax_nh4_7=2.5e-10 (lower bound) + km_nh4_10=0.07 (lower bound) achieves PFT10_leaf=21.1 vs Case #322's 6.6 — a 3.2x improvement from ECA redistribution alone. The mechanism is: lower PFT7 vmax_nh4 reduces PFT7 competitive ECA 'enzyme investment', freeing substrate for PFT10; simultaneously, lower PFT10 km_nh4 increases PFT10 affinity at low Arctic NH4 concentrations (NH4 << 0.21 mM), enabling PFT10 to compete more effectively for scarce substrate. Secondary intervention: increasing recruit_init_density_10 from lower bound (0.100) to 0.281 increases PFT10 cohort representation, raising collective P acquisition probability. Tertiary: reducing l2fr_ini_9 from upper bound (18.31) to mid-range (6.0) corrects PFT9 leaf underestimation by rebalancing carbon allocation toward leaves from overinvested fine roots. The cumulative design ensures each change adds mechanistic benefit sequentially without cross-parameter conflicts.

---

## Parameters to Modify

### fates_cnp_vmax_nh4 (PFT#7)
- **Current:** 0.00025
- **Proposed:** 2.5e-10
- **Rationale:** Case #322 has vmax_nh4_7 at upper bound (1000x default), giving PFT7 maximal ECA competitive dominance and capturing 73.4% of total P uptake. Case #3972 uses vmax_nh4_7=2.5e-10 (lower bound) and achieves PFT10_leaf=21.1 vs 6.6 — the largest within-ensemble improvement. Skip-test confirmed: r=-0.198 (p<1e-44) between vmax_nh4_7 and PFT10 leaf biomass. Reducing to default/lower bound is ecologically appropriate as PFT7 (shrubs) with vmax 1000x above default is biologically implausible for Arctic conditions.

### fates_cnp_eca_km_nh4 (PFT#10)
- **Current:** 0.21
- **Proposed:** 0.07
- **Rationale:** Case #322 has km_nh4_10=0.21 (upper bound = lowest substrate affinity). In Arctic soils where NH4 concentrations are << 0.21 mM, high Km renders PFT10 non-competitive. Case #3972 uses km_nh4_10=0.07 (lower bound) and achieves the 3.2x PFT10 improvement. Skip-test: r=-0.093 (p<1e-10). Lower Km means PFT10 can extract NH4 at low concentrations typical of frozen/thawed Arctic mineral soils. Ecologically supported: tundra graminoids have high-affinity low-Km transporters for nutrient-scarce cold soils.

### fates_recruit_init_density (PFT#10)
- **Current:** 0.1
- **Proposed:** 0.281
- **Rationale:** Case #322 has recruit_init_density_10=0.100 (lower bound). Case #3972 uses 0.2807 and achieves the 3.2x PFT10_leaf improvement. Skip-test: r=0.110 (p<1e-14). More initial PFT10 cohorts increase probability of P acquisition in early establishment and raise collective fine root biomass for nutrient uptake. Value 0.281 is within ensemble bounds and has been empirically validated in Case #3972.

### fates_cnp_vmax_p (PFT#10)
- **Current:** 5e-11
- **Proposed:** 5e-09
- **Rationale:** Case #322 has vmax_p_10=5e-11 (lower bound, 10x below default 5e-10). This nearly eliminates PFT10 direct P acquisition capacity in ECA. Conservative increase to 5e-09 (2 orders of magnitude above lower bound) restores baseline P uptake capacity without reaching the high values (e.g., 2.14e-05 in Case #3972) that triggered allocation paradox in previous experiments. This is the minimum correction needed to allow any meaningful P uptake by PFT10 fineroots.

### fates_allom_l2fr (PFT#9)
- **Current:** 18.31
- **Proposed:** 6.0
- **Rationale:** Case #322 has l2fr_ini_9=18.31 (upper bound). test_l2fr_carbon_limitation confirmed: high L2FR (>10) reduces PFT9 leaves by 63% (confidence 0.60). PFT9_leaf is 18.4% below target (101.8 vs 124.7). Reducing to 6.0 (mid-range) corrects the carbon allocation imbalance toward leaves from overinvested fine roots. Applied last in cumulative design to avoid confounding with competition rebalancing effects. Value 6.0 is conservative (mid-range of [0.01, 18.31]) to avoid PFT9 shading PFT10.


---

## Parameter Validation Report

| Parameter | Check | Status | Detail |
|-----------|-------|--------|--------|
| fates_cnp_vmax_nh4 | magnitude | INFO | 0.00025 → 2.5e-10 (0.0x change, >1000x) |

**Summary:** 0 auto-fixed, 0 warning(s), 0 error(s)

---

## Expected Outcomes

- **PFT10_leaf:** 25.0
- **PFT10_fineroot:** 40.0
- **PFT9_leaf:** 115.0
- **PFT9_fineroot:** 195.0
- **PFT7_leaf:** 20.0
- **PFT7_fineroot:** 80.0
- **composite_rmsre_improvement:** 0.15

---

## Metadata

```json
{
  "iteration": 4,
  "diagnosis_count": 4,
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
  "iteration": 4,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-03-15T10:46:08.491264",
  "site": "Kougarok",
  "session_id": "20260315_095903",
  "experiment_count": 0,
  "skip_testing_count": 3,
  "diagnosis_count": 4,
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
