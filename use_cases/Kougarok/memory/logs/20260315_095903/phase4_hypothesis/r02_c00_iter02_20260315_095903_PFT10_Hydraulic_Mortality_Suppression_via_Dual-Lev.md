# PFT10 Hydraulic Mortality Suppression via Dual-Lever Threshold Elevation

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 2 | **Cycle:** 0 | **Iteration:** 2
**Date:** 2026-03-15 10:29:41
**Confidence:** 0.68

---

## Hypothesis: PFT10 Hydraulic Mortality Suppression via Dual-Lever Threshold Elevation

### Mechanism

Diagnosis confirms that 92% of PFT10 mortality is driven by hydraulic failure, with mort_hf_sm_threshold_10 at its lower bound (1e-08) in Case #322. Arctic graminoids (PFT10) naturally grow in waterlogged, saturated soils and have high physiological tolerance for low soil water potentials — yet the current parameterization kills them at extremely low moisture thresholds that would not trigger death in real tundra conditions. This creates a mortality trap where PFT10 is eliminated before P starvation can even become the binding constraint (GPP=0 in year 1901). Two mechanistically independent levers control hydraulic failure mortality rate: (1) mort_hf_sm_threshold_10 determines the BTRAN moisture level that triggers hydraulic failure events — raising it from 1e-08 to 1e-05 (within the ensemble range upper bound of 1.44e-06 extended) means the threshold is met less often in Arctic permafrost soils that maintain moderate moisture; (2) mort_scalar_hydrfailure_10 at 0.410 determines the RATE of mortality once threshold is exceeded — reducing to 0.10 slows the kill rate even when threshold is crossed. Together, these two changes represent a cumulative suppression of hydraulic mortality that should allow PFT10 to persist long enough for P uptake (vmax_p_10) and carbon assimilation to accumulate meaningful biomass. The mechanism is completely independent of P stoichiometry (stoich_phos hypothesis was rejected), root turnover (r=-0.008, rejected), and PID allocation (PID responds to light not P stress). This is the ONLY mechanistic pathway that addresses PFT10's 92% hydraulic-mortality-driven collapse without modifying cross-PFT parameters.

### Design Type

cumulative

---

## AI Reasoning and Analysis

Diagnosis confirms that 92% of PFT10 mortality is driven by hydraulic failure, with mort_hf_sm_threshold_10 at its lower bound (1e-08) in Case #322. Arctic graminoids (PFT10) naturally grow in waterlogged, saturated soils and have high physiological tolerance for low soil water potentials — yet the current parameterization kills them at extremely low moisture thresholds that would not trigger death in real tundra conditions. This creates a mortality trap where PFT10 is eliminated before P starvation can even become the binding constraint (GPP=0 in year 1901). Two mechanistically independent levers control hydraulic failure mortality rate: (1) mort_hf_sm_threshold_10 determines the BTRAN moisture level that triggers hydraulic failure events — raising it from 1e-08 to 1e-05 (within the ensemble range upper bound of 1.44e-06 extended) means the threshold is met less often in Arctic permafrost soils that maintain moderate moisture; (2) mort_scalar_hydrfailure_10 at 0.410 determines the RATE of mortality once threshold is exceeded — reducing to 0.10 slows the kill rate even when threshold is crossed. Together, these two changes represent a cumulative suppression of hydraulic mortality that should allow PFT10 to persist long enough for P uptake (vmax_p_10) and carbon assimilation to accumulate meaningful biomass. The mechanism is completely independent of P stoichiometry (stoich_phos hypothesis was rejected), root turnover (r=-0.008, rejected), and PID allocation (PID responds to light not P stress). This is the ONLY mechanistic pathway that addresses PFT10's 92% hydraulic-mortality-driven collapse without modifying cross-PFT parameters.

---

## Parameters to Modify

### fates_mort_hf_sm_threshold (PFT#10)
- **Current:** 1e-08
- **Proposed:** 1e-05
- **Rationale:** Case #322 has mort_hf_sm_threshold_10 at the lower bound (1e-08). This means hydraulic failure triggers at near-zero BTRAN — an unrealistically sensitive threshold for Arctic graminoids that tolerate saturated soils. Raising to 1e-05 (well outside current ensemble upper bound of 1.44e-06, requiring a new HPC run) represents a 1000x increase that corresponds to BTRAN levels Arctic tundra plants can actually tolerate. The FATES tech note explicitly notes hydraulic failure mortality is set to 0 when any soil layer drops below -2°C, but summer thaw layer drying can still trigger events. The new value of 1e-05 is conservative compared to PFT9's known effective range (1e-06 improved PFT9 by 50-100%); PFT10 graminoids need an even higher threshold given their wetland adaptation.

### fates_mort_scalar_hydrfailure (PFT#10)
- **Current:** 0.41
- **Proposed:** 0.08
- **Rationale:** Case #322 has mort_scalar_hydrfailure_10=0.410 (mid-range, within ensemble bounds [0.05, 0.890]). This scalar controls the daily mortality rate fraction when soil moisture falls below the hydraulic failure threshold. With hydraulic failure accounting for 92% of PFT10 mortality, reducing from 0.410 to 0.08 (near the lower bound of 0.05) will substantially reduce the per-event kill rate even when threshold conditions are met. The combined effect of raising the threshold (fewer triggering events) AND reducing the scalar (slower kill rate per event) creates a multiplicative suppression: if threshold elevation reduces event frequency by 90% and scalar reduction reduces per-event rate by 80%, PFT10 hydraulic mortality could decrease by ~98%. This value is WITHIN the ensemble sampling range [0.05, 0.890] so can be validated against existing data, but combined with the out-of-bounds threshold change requires a new HPC run.

### fates_allom_l2fr (PFT#10)
- **Current:** 9.88
- **Proposed:** 3.5
- **Rationale:** Case #322 has l2fr_ini_10=9.88 (at upper bound of ensemble range [1.115, 9.879]). Even if hydraulic mortality is suppressed and PFT10 plants survive, the extreme L2FR=9.88 forces massive carbon allocation to fine roots at the expense of leaf C. Previous analysis showed high L2FR reduces PFT9 leaves by 63% (confidence 0.60). For PFT10 with FATES_LEAFC observed at 82.7 g/m2 but simulated at 6.6 g/m2, the carbon allocation imbalance is a secondary bottleneck. Reducing l2fr_ini_10 from 9.88 to 3.5 (mid-range, within bounds) reallocates C toward leaves. Note: this is WITHIN ensemble bounds and can be partially validated with existing data. The paradoxical behavior noted in parameter knowledge (lower L2FR sometimes underestimates fineroot) suggests we should monitor FATES_FROOTC alongside FATES_LEAFC after this change.


---

## Parameter Validation Report

| Parameter | Check | Status | Detail |
|-----------|-------|--------|--------|
| fates_mort_hf_sm_threshold | magnitude | INFO | 1e-08 → 1e-05 (1000.0x change, >1000x) |

**Summary:** 0 auto-fixed, 0 warning(s), 0 error(s)

---

## Expected Outcomes

- **leaf_pft10:** 35.0
- **froot_pft10:** 120.0
- **leaf_pft9:** 100.0
- **froot_pft9:** 210.0
- **leaf_pft7:** 22.0
- **froot_pft7:** 80.0
- **agb_pft10:** 15.0

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
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_mort_hf_sm_threshold', check='magnitude', severity='info', detail='1e-08 \u2192 1e-05 (1000.0x change, >1000x)', old_value=None, new_value=None)])"
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
  "timestamp": "2026-03-15T10:29:41.554436",
  "site": "Kougarok",
  "session_id": "20260315_095903",
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
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_mort_hf_sm_threshold', check='magnitude', severity='info', detail='1e-08 \u2192 1e-05 (1000.0x change, >1000x)', old_value=None, new_value=None)])"
}
```
