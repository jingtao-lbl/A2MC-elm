# P-Demand Explosion Quantification via vmax_p × L2FR Interaction Test

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 2 | **Cycle:** 0 | **Iteration:** 1
**Date:** 2026-03-11 21:02:26
**Confidence:** 0.87

---

## Hypothesis: P-Demand Explosion Quantification via vmax_p × L2FR Interaction Test

### Mechanism

The diagnosis identifies a catastrophic P demand explosion (supply/demand ratio ~10⁻⁶) driven by the mathematical formulation: P_demand = fnrt_c × vmax_p. When fine root biomass is large (driven by high L2FR) AND vmax_p is at its upper bound, demand explodes by orders of magnitude beyond supply capacity. This creates a futile cycle: PID controller senses P deficit → increases root allocation → increases P demand arithmetically → widens the supply/demand gap further. The hypothesis is that cases with BOTH high vmax_p AND high L2FR simultaneously will show WORSE biomass outcomes than cases with either parameter at high values alone, because the interaction term (fnrt_c × vmax_p) creates a demand amplification effect that cannot be satisfied. Critically, cases with LOW L2FR and HIGH vmax_p should show the best P acquisition efficiency (fewer, more productive roots rather than many futile roots). This test will quantify: (1) whether the vmax_p × L2FR interaction is the dominant driver of failure, (2) whether any existing cases have found parameter combinations that escape the demand explosion trap, and (3) what the empirical L2FR threshold is above which biomass collapses regardless of vmax_p. This test uses ONLY existing Morris ensemble data and requires no new HPC runs.

### Design Type

factorial

---

## AI Reasoning and Analysis

The diagnosis identifies a catastrophic P demand explosion (supply/demand ratio ~10⁻⁶) driven by the mathematical formulation: P_demand = fnrt_c × vmax_p. When fine root biomass is large (driven by high L2FR) AND vmax_p is at its upper bound, demand explodes by orders of magnitude beyond supply capacity. This creates a futile cycle: PID controller senses P deficit → increases root allocation → increases P demand arithmetically → widens the supply/demand gap further. The hypothesis is that cases with BOTH high vmax_p AND high L2FR simultaneously will show WORSE biomass outcomes than cases with either parameter at high values alone, because the interaction term (fnrt_c × vmax_p) creates a demand amplification effect that cannot be satisfied. Critically, cases with LOW L2FR and HIGH vmax_p should show the best P acquisition efficiency (fewer, more productive roots rather than many futile roots). This test will quantify: (1) whether the vmax_p × L2FR interaction is the dominant driver of failure, (2) whether any existing cases have found parameter combinations that escape the demand explosion trap, and (3) what the empirical L2FR threshold is above which biomass collapses regardless of vmax_p. This test uses ONLY existing Morris ensemble data and requires no new HPC runs.

---

## Parameters to Modify

### fates_cnp_vmax_p
- **Current:** 5e-05
- **Proposed:** None
- **Rationale:** NOT modifying — analyzing existing variation in ensemble to quantify interaction with L2FR

### fates_allom_l2fr
- **Current:** 18.31
- **Proposed:** None
- **Rationale:** NOT modifying — analyzing existing variation in ensemble to identify L2FR threshold above which biomass collapses

### fates_cnp_vmax_p
- **Current:** 5e-11
- **Proposed:** None
- **Rationale:** NOT modifying — analyzing existing ensemble variation for PFT10

### fates_allom_l2fr
- **Current:** 9.88
- **Proposed:** None
- **Rationale:** NOT modifying — analyzing existing ensemble variation for PFT10


---

## Expected Outcomes

- **high_vmax_p_high_l2fr_pft9_leaf:** < 30 gC/m² (demand explosion, worse than average)
- **high_vmax_p_low_l2fr_pft9_leaf:** > 60 gC/m² (best P acquisition efficiency)
- **low_vmax_p_high_l2fr_pft9_leaf:** < 20 gC/m² (P starved AND carbon diverted to roots)
- **low_vmax_p_low_l2fr_pft9_leaf:** 15-40 gC/m² (P limited but carbon balanced)
- **pft10_froot_any_case:** < 50 gC/m² (structural failure regardless of quadrant)
- **l2fr_threshold_pft9:** L2FR > 8 causes > 50% reduction in leaf biomass
- **vmax_p_l2fr_interaction_correlation:** negative correlation between vmax_p×l2fr product and leaf biomass (r < -0.3)

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
  "timestamp": "2026-03-11T21:02:26.037714",
  "site": "Kougarok",
  "session_id": "20260311_203934",
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
