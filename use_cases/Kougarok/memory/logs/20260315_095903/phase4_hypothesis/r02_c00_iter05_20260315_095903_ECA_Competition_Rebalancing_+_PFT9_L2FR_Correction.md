# ECA Competition Rebalancing + PFT9 L2FR Correction: Empirically-Validated Multi-Lever Intervention

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 2 | **Cycle:** 0 | **Iteration:** 5
**Date:** 2026-03-15 10:55:43
**Confidence:** 0.72

---

## Hypothesis: ECA Competition Rebalancing + PFT9 L2FR Correction: Empirically-Validated Multi-Lever Intervention

### Mechanism

Two confirmed mechanistic bottlenecks are preventing biomass targets from being met simultaneously: (1) Inter-PFT ECA competition asymmetry — PFT7's vmax_nh4 at upper bound (0.00025, 1000× default) gives it monopolistic control over NH4 uptake (73.4% of total P uptake), starving PFT10 of nutrients needed for growth. Skip-test confirmed r=-0.198 (p<1e-44) between vmax_nh4_7 and PFT10 leaf. Simultaneously, PFT10's km_nh4 at upper bound (0.21) means its NH4 transporters have the WORST possible affinity at Arctic soil NH4 concentrations. (2) PFT9 L2FR allocation imbalance — l2fr_ini_9 at upper bound (18.31) forces root-biased carbon partitioning, confirmed by r=-0.257 (p significant) between l2fr_ini_9 and PFT9 leaf — the strongest single predictor found for PFT9 leaf. Additionally, PFT10's vmax_p at lower bound (5e-11) nearly eliminates direct P acquisition. Case #3972 empirically demonstrated that competition rebalancing alone achieves 3.2× PFT10_leaf improvement (21.1 vs 6.6 g/m2). This hypothesis combines ALL confirmed levers into a single cumulative experiment starting from Case #3972's foundation, adding the L2FR correction for PFT9 and the vmax_p correction for PFT10.

### Design Type

cumulative

---

## AI Reasoning and Analysis

Two confirmed mechanistic bottlenecks are preventing biomass targets from being met simultaneously: (1) Inter-PFT ECA competition asymmetry — PFT7's vmax_nh4 at upper bound (0.00025, 1000× default) gives it monopolistic control over NH4 uptake (73.4% of total P uptake), starving PFT10 of nutrients needed for growth. Skip-test confirmed r=-0.198 (p<1e-44) between vmax_nh4_7 and PFT10 leaf. Simultaneously, PFT10's km_nh4 at upper bound (0.21) means its NH4 transporters have the WORST possible affinity at Arctic soil NH4 concentrations. (2) PFT9 L2FR allocation imbalance — l2fr_ini_9 at upper bound (18.31) forces root-biased carbon partitioning, confirmed by r=-0.257 (p significant) between l2fr_ini_9 and PFT9 leaf — the strongest single predictor found for PFT9 leaf. Additionally, PFT10's vmax_p at lower bound (5e-11) nearly eliminates direct P acquisition. Case #3972 empirically demonstrated that competition rebalancing alone achieves 3.2× PFT10_leaf improvement (21.1 vs 6.6 g/m2). This hypothesis combines ALL confirmed levers into a single cumulative experiment starting from Case #3972's foundation, adding the L2FR correction for PFT9 and the vmax_p correction for PFT10.

---

## Parameters to Modify

### fates_cnp_vmax_nh4 (PFT#7)
- **Current:** 0.00025
- **Proposed:** 2.5e-10
- **Rationale:** Reduce PFT7 NH4 uptake dominance from upper bound (1000× default) to lower bound. Confirmed via skip-test: r=-0.198 (p<1e-44) — higher vmax_nh4_7 suppresses PFT10 leaf through ECA competition. PFT7 leaf is also over-predicted (+32.2%), so this reduction corrects TWO errors simultaneously. Case #3972 uses this exact value and achieves 3.2× PFT10_leaf improvement.

### fates_cnp_eca_km_nh4 (PFT#10)
- **Current:** 0.21
- **Proposed:** 0.07
- **Rationale:** Reduce PFT10 Michaelis-Menten constant for NH4 from worst-affinity (0.21, upper bound) to highest-affinity (0.07, lower bound). At Arctic NH4 concentrations << 0.21 mM, PFT10 is biologically non-competitive. Lower Km is ecologically appropriate for Arctic tundra graminoids which express high-affinity NH4 transporters. Skip-test: r=-0.093 (p<1e-10). Case #3972 uses this exact value.

### fates_recruit_init_density (PFT#10)
- **Current:** 0.1
- **Proposed:** 0.281
- **Rationale:** Increase PFT10 initial seedling density from lower bound to near-upper bound (Case #3972 value: 0.2807). Skip-test: r=0.110 (p<1e-14). Higher density increases collective P acquisition probability and improves cohort representation in ECA competition. This is a within-ensemble value empirically verified in Case #3972.

### fates_cnp_vmax_p (PFT#10)
- **Current:** 5e-11
- **Proposed:** 5e-09
- **Rationale:** Increase PFT10 direct P uptake capacity from lower bound (5e-11, 10× below default) to default value (5e-10, then conservative 5e-09 = 10× default). Skip-test: log(vmax_p_10) vs leaf10 r=0.145 (p<1e-24). Previous cycle confirmed allocation_paradox_signal=False for vmax_p_10 vs froot10 (r>0), so this conservative increase should not trigger the PID allocation paradox. Avoids values >1e-06 that risk paradox.

### fates_allom_l2fr (PFT#9)
- **Current:** 18.31
- **Proposed:** 6.0
- **Rationale:** Reduce PFT9 leaf-to-fineroot ratio from upper bound (18.31) to mid-range (6.0). Confirmed strongest PFT9 leaf predictor: r=-0.257 (skip-test). With PFT9_leaf at 26.6 vs target 124.7 (-78.7%), this lever is critical. A moderate reduction to 6.0 (not minimum) preserves PFT9_fineroot which currently PASSES (191.8 vs 187.35, +2.4%). Reduction from 18.31 to 6.0 is a 3× decrease — should shift substantial C from roots to leaves without collapsing fineroot below target.


---

## Parameter Validation Report

| Parameter | Check | Status | Detail |
|-----------|-------|--------|--------|
| fates_cnp_vmax_nh4 | magnitude | INFO | 0.00025 → 2.5e-10 (0.0x change, >1000x) |

**Summary:** 0 auto-fixed, 0 warning(s), 0 error(s)

---

## Expected Outcomes

- **PFT10_leaf:** 25.0
- **PFT10_froot:** 15.0
- **PFT9_leaf:** 80.0
- **PFT9_froot:** 170.0
- **PFT7_leaf:** 22.0
- **PFT7_froot:** 90.0
- **composite_rmsre_improvement:** 0.15
- **targets_met_increase:** 2

---

## Metadata

```json
{
  "iteration": 5,
  "diagnosis_count": 5,
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
  "iteration": 5,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-03-15T10:55:43.615747",
  "site": "Kougarok",
  "session_id": "20260315_095903",
  "experiment_count": 0,
  "skip_testing_count": 4,
  "diagnosis_count": 5,
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
