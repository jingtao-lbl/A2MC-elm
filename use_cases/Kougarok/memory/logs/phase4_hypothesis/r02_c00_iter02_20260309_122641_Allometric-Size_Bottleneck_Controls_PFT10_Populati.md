# Allometric-Size Bottleneck Controls PFT10 Population Viability

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 2 | **Cycle:** 0 | **Iteration:** 2
**Date:** 2026-03-09 12:56:23
**Confidence:** 0.85

---

## Hypothesis: Allometric-Size Bottleneck Controls PFT10 Population Viability

### Mechanism

PFT#10 (arctic graminoid) is functionally extinct across virtually all ensemble members because multiple allometric parameters in Case #322 are simultaneously at their lower bounds, creating a cascading size constraint: (1) allom_d2bl1_10=0.019 (lower bound) means leaf biomass per unit DBH is minimized; (2) allom_dbh_maxheight_10=0.192 (lower bound) caps maximum plant size at the smallest possible value; (3) leaf_slatop_10=0.00853 (lower bound) means extremely low leaf area per unit carbon, minimizing light capture; (4) allom_d2h1_10=0.370 (lower bound) constrains height growth. Together, these create plants too small and with too little leaf area to generate positive carbon balance. Carbon starvation mortality then eliminates the population. With near-zero population, there are no fine roots to take up nutrients, making P uptake parameters irrelevant (confirmed by Cycle 1: r=-0.109 for vmax_p_10 vs PFT10 froot). The critical test is whether cases where these allometric parameters take HIGHER values within the existing ensemble show viable PFT#10 populations. If the allometric bottleneck hypothesis is correct, we should see a strong positive correlation between these size-determining parameters and PFT#10 biomass, and cases in the upper quartiles of these parameters should show dramatically higher PFT#10 leaf and froot biomass than cases at the lower bounds. Additionally, Case #1386 (which achieves PFT10 leaf=37.0, froot=186.6) likely has these allometric parameters at much higher values than Case #322, providing direct evidence.

### Design Type

cumulative

---

## AI Reasoning and Analysis

PFT#10 (arctic graminoid) is functionally extinct across virtually all ensemble members because multiple allometric parameters in Case #322 are simultaneously at their lower bounds, creating a cascading size constraint: (1) allom_d2bl1_10=0.019 (lower bound) means leaf biomass per unit DBH is minimized; (2) allom_dbh_maxheight_10=0.192 (lower bound) caps maximum plant size at the smallest possible value; (3) leaf_slatop_10=0.00853 (lower bound) means extremely low leaf area per unit carbon, minimizing light capture; (4) allom_d2h1_10=0.370 (lower bound) constrains height growth. Together, these create plants too small and with too little leaf area to generate positive carbon balance. Carbon starvation mortality then eliminates the population. With near-zero population, there are no fine roots to take up nutrients, making P uptake parameters irrelevant (confirmed by Cycle 1: r=-0.109 for vmax_p_10 vs PFT10 froot). The critical test is whether cases where these allometric parameters take HIGHER values within the existing ensemble show viable PFT#10 populations. If the allometric bottleneck hypothesis is correct, we should see a strong positive correlation between these size-determining parameters and PFT#10 biomass, and cases in the upper quartiles of these parameters should show dramatically higher PFT#10 leaf and froot biomass than cases at the lower bounds. Additionally, Case #1386 (which achieves PFT10 leaf=37.0, froot=186.6) likely has these allometric parameters at much higher values than Case #322, providing direct evidence.

---

## Parameters to Modify

### fates_allom_d2bl1
- **Current:** 0.019
- **Proposed:** 0.08
- **Rationale:** Currently at lower bound in Case #322. Controls leaf biomass = d2bl1 * DBH^d2bl2. At 0.019, leaf biomass per diameter is 4× lower than default (0.07). Arctic graminoids need sufficient leaf area to photosynthesize during short growing season. Value of 0.08 is near default and within ensemble range [0.019, 0.15].

### fates_allom_dbh_maxheight
- **Current:** 0.192
- **Proposed:** 0.4
- **Rationale:** Currently at lower bound in Case #322. Caps maximum DBH and thus maximum plant size. At 0.192 cm, graminoids are constrained to extremely small individuals that cannot accumulate enough biomass. Value of 0.40 is above default (0.35) and within ensemble range [0.192, 0.520].

### fates_leaf_slatop
- **Current:** 0.00853
- **Proposed:** 0.025
- **Rationale:** Currently at lower bound in Case #322. SLA of 0.00853 m²/gC is unrealistically low for a graminoid (typical values 0.02-0.03). Low SLA means very little leaf area per unit carbon invested, severely limiting light interception and GPP. Value of 0.025 is within the graminoid literature range and ensemble bounds [0.0085, 0.029].

### fates_allom_d2h1
- **Current:** 0.37
- **Proposed:** 0.65
- **Rationale:** Currently at lower bound in Case #322. Controls height per unit diameter. At 0.370, plants are shorter than they should be for a given diameter, reducing competitive ability. Value of 0.65 is near default (0.64) and within ensemble range [0.370, 0.950].


---

## Expected Outcomes

- **PFT10_leaf_increase_from_near_zero:** Cases with allometric parameters in upper quartiles should show PFT#10 leaf biomass >10 gC/m² (vs ~0.1 in Case #322)
- **PFT10_froot_increase_from_near_zero:** Cases with allometric parameters in upper quartiles should show PFT#10 froot biomass >50 gC/m² (vs ~0.3 in Case #322)
- **Case_1386_confirmation:** Case #1386 (PFT10 leaf=37.0, froot=186.6) should have allometric parameters significantly above Case #322's lower-bound values
- **allometric_params_explain_variance:** Combined allometric parameters should explain >30% of PFT#10 biomass variance across ensemble

---

## Metadata

```json
{
  "iteration": 2,
  "diagnosis_count": 2,
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
  "iteration": 2,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-03-09T12:56:23.854562",
  "site": "Kougarok",
  "session_id": "20260309_122641",
  "experiment_count": 0,
  "skip_testing_count": 1,
  "diagnosis_count": 2,
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
