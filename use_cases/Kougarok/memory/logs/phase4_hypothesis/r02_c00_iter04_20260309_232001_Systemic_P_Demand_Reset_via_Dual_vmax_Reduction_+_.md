# Systemic P Demand Reset via Dual vmax Reduction + L2FR Rebalancing

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 2 | **Cycle:** 0 | **Iteration:** 4
**Date:** 2026-03-10 00:19:01
**Confidence:** 0.72

---

## Hypothesis: Systemic P Demand Reset via Dual vmax Reduction + L2FR Rebalancing

### Mechanism

Case #322 operates in a regime of catastrophic systemic P starvation (total demand 358,121 g/m²/yr vs supply 0.67 g/m²/yr, ratio 534,509×). The root cause is that vmax_nh4_7=0.00025 and vmax_no3_9=0.00025 are both at their absolute upper sampling bounds, creating astronomically inflated ECA uptake demand (demand = vmax × fnrt_C). In ECA competition, total P is divided proportionally to each competitor's demand-weighted uptake capacity — when PFT7 and PFT9 each generate ~160,000+ g/m²/yr of P demand, PFT10 receives essentially 0% of available P regardless of its own vmax. This is a structural regime failure, not a gradual optimization problem. Simultaneously, l2fr_ini_9=18.31 (upper bound) routes >95% of PFT9 carbon to fine roots, starving PFT9 leaves (26.6 g/m² vs target 124.7). The proposed intervention is a SIMULTANEOUS reset of: (1) vmax_nh4_7 reduced 100× to bring PFT7 N demand to biologically plausible range; (2) vmax_no3_9 and vmax_nh4_9 reduced 100× to reduce PFT9 N/P demand by ~100×; (3) l2fr_ini_9 decreased from 18.31 to ~5.0 based on Case #3972 evidence (PFT9_leaf improved from 26.6 to 85.2 at l2fr_ini_9=5.24); (4) l2fr_ini_7 increased from 0.852 to 1.8 to redirect C toward PFT7 fine roots; (5) pid_kd stabilization for PFT9/10 to prevent allocation oscillation after rebalancing. This is the FIRST time vmax reduction for PFT7/PFT9 is being directly proposed — all prior cycles focused on stoichiometry, threshold, and PFT10-specific parameters while leaving the primary vmax bottleneck untouched. The mechanism predicts that reducing total system P demand by ~100× (from 358,121 to ~3,500 g/m²/yr) will allow ECA to distribute P meaningfully across all three PFTs, breaking the competitive exclusion of PFT10.

### Design Type

cumulative

---

## AI Reasoning and Analysis

Case #322 operates in a regime of catastrophic systemic P starvation (total demand 358,121 g/m²/yr vs supply 0.67 g/m²/yr, ratio 534,509×). The root cause is that vmax_nh4_7=0.00025 and vmax_no3_9=0.00025 are both at their absolute upper sampling bounds, creating astronomically inflated ECA uptake demand (demand = vmax × fnrt_C). In ECA competition, total P is divided proportionally to each competitor's demand-weighted uptake capacity — when PFT7 and PFT9 each generate ~160,000+ g/m²/yr of P demand, PFT10 receives essentially 0% of available P regardless of its own vmax. This is a structural regime failure, not a gradual optimization problem. Simultaneously, l2fr_ini_9=18.31 (upper bound) routes >95% of PFT9 carbon to fine roots, starving PFT9 leaves (26.6 g/m² vs target 124.7). The proposed intervention is a SIMULTANEOUS reset of: (1) vmax_nh4_7 reduced 100× to bring PFT7 N demand to biologically plausible range; (2) vmax_no3_9 and vmax_nh4_9 reduced 100× to reduce PFT9 N/P demand by ~100×; (3) l2fr_ini_9 decreased from 18.31 to ~5.0 based on Case #3972 evidence (PFT9_leaf improved from 26.6 to 85.2 at l2fr_ini_9=5.24); (4) l2fr_ini_7 increased from 0.852 to 1.8 to redirect C toward PFT7 fine roots; (5) pid_kd stabilization for PFT9/10 to prevent allocation oscillation after rebalancing. This is the FIRST time vmax reduction for PFT7/PFT9 is being directly proposed — all prior cycles focused on stoichiometry, threshold, and PFT10-specific parameters while leaving the primary vmax bottleneck untouched. The mechanism predicts that reducing total system P demand by ~100× (from 358,121 to ~3,500 g/m²/yr) will allow ECA to distribute P meaningfully across all three PFTs, breaking the competitive exclusion of PFT10.

---

## Parameters to Modify

### fates_cnp_vmax_nh4
- **Current:** 0.00025
- **Proposed:** 2.5e-06
- **Rationale:** Case #322 has vmax_nh4_7 at absolute upper bound. PFT7 alone drives ~192,556 g/m²/yr of total P demand. A 100× reduction to 2.5e-06 reduces PFT7 demand to ~1,926 g/m²/yr — still high but within 3 orders of magnitude of supply. Case #3972 achieves better PFT7_froot=102.5 (vs Case #322's 62.3) with vmax_nh4_7=3.57e-05 (7× lower), confirming that reduction does not harm PFT7 biomass. Primary intervention targeting the #1 diagnosed cause.

### fates_cnp_vmax_no3
- **Current:** 0.00025
- **Proposed:** 2.5e-06
- **Rationale:** Case #322 has vmax_no3_9 at absolute upper bound — PFT9's second largest N demand driver. PFT9 drives ~165,550 g/m²/yr of total P demand. A 100× reduction to 2.5e-06 reduces PFT9 NO3-driven demand by 100×. Must be reduced simultaneously with vmax_nh4_9 to avoid asymmetric NH4/NO3 preference shift. Confirmed by diagnosis as 46% of total system P demand.

### fates_cnp_vmax_nh4
- **Current:** 0.00021428575
- **Proposed:** 2.14e-06
- **Rationale:** Case #322 has vmax_nh4_9=0.000214 (near upper bound). Compound with vmax_no3_9=0.00025 this creates excessive PFT9 N demand. Reduce 100× in concert with vmax_no3_9 to maintain NH4/NO3 preference ratio while eliminating the demand explosion. Symmetric reduction preserves competitive niche structure while reducing magnitude.

### fates_allom_l2fr
- **Current:** 18.31149756
- **Proposed:** 5.2
- **Rationale:** Case #322 has l2fr_ini_9 at absolute upper bound [0.01, 18.31], routing >95% of C to fine roots and starving PFT9_leaf (26.6 vs target 124.7). Three cycles confirm r=-0.257 negative correlation with PFT9_leaf (p<1e-75). Case #3972 with l2fr_ini_9=5.24 achieves PFT9_leaf=85.2 g/m² — the strongest empirical evidence in the ensemble. Proposed value 5.2 matches Case #3972's successful parameter. NOTE: PFT9_froot=191.8 currently passes; reducing l2fr will reduce froot. Estimated reduction from 191.8 to ~90-100 g/m² — monitor against lower bound 149.9 g/m².

### fates_allom_l2fr
- **Current:** 0.8518917117142859
- **Proposed:** 1.8
- **Rationale:** Case #322 has l2fr_ini_7=0.852 (leaf-biased). PFT7_leaf=32.5 g/m² overproduces (+32% above target 24.6) while PFT7_froot=87.1 g/m² underproduces (-50% below target 174.2). Increasing l2fr_ini_7 redirects C toward roots. A 2× increase from 0.852 to 1.8 estimated to reduce PFT7_leaf by ~30-40% (from 32.5 to ~20-23 g/m²) while improving PFT7_froot. Risk: PFT7_leaf lower bound is 19.6 g/m² (0.8×24.6); stay below l2fr_ini_7=2.5 to avoid overshooting.

### fates_cnp_pid_kd
- **Current:** 0.01
- **Proposed:** 0.35
- **Rationale:** Case #322 has pid_kd_10=0.01 at lower bound [0.01, 0.5]. Case #1391 (highest ensemble PFT10_froot=205 g/m²) has pid_kd_10=0.43. Derivative gain provides allocation stability damping — at minimum value, PID allocation oscillates without restraint. After vmax reduction removes P starvation regime, stable allocation is critical to allow PFT10 to accumulate biomass. Value 0.35 is within Case #1391's successful range without going to the extreme.

### fates_cnp_pid_kd
- **Current:** 0.01
- **Proposed:** 0.2
- **Rationale:** Case #322 has pid_kd_9=0.01 at lower bound. Without derivative damping, the l2fr_ini_9 correction (from 18.31 to 5.2) may dynamically re-diverge as PID responds to the new allocation regime. More conservative than PFT10 correction (0.35) since PFT9 does not have the same catastrophic failure pattern. Stabilizes allocation rebalancing after l2fr correction.


---

## Parameter Validation Report

| Parameter | Check | Status | Detail |
|-----------|-------|--------|--------|
| fates_cnp_vmax_nh4 | magnitude | WARNING | 0.00021428575 → 2.14e-06 (0.0x change, 100-1000x) |

**Summary:** 0 auto-fixed, 1 warning(s), 0 error(s)

---

## Expected Outcomes

- **leaf_pft7:** 20.0
- **froot_pft7:** 130.0
- **leaf_pft9:** 80.0
- **froot_pft9:** 120.0
- **leaf_pft10:** 15.0
- **froot_pft10:** 50.0
- **total_system_P_demand_reduction:** from 358121 to ~3500 g/m²/yr (100× reduction)
- **ECA_P_allocation_to_pft10:** from ~2% to ~10-15% of total supply

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
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_cnp_vmax_nh4', check='magnitude', severity='warning', detail='0.00021428575 \u2192 2.14e-06 (0.0x change, 100-1000x)', old_value=None, new_value=None)])"
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
  "timestamp": "2026-03-10T00:19:01.693523",
  "site": "Kougarok",
  "session_id": "20260309_232001",
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
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_cnp_vmax_nh4', check='magnitude', severity='warning', detail='0.00021428575 \u2192 2.14e-06 (0.0x change, 100-1000x)', old_value=None, new_value=None)])"
}
```
