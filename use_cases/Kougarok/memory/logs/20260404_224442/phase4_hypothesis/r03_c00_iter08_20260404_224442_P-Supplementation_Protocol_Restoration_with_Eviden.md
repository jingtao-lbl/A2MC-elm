# P-Supplementation Protocol Restoration with Evidence-Based Parameter Trio (phos_retrans_10↑, HF_mort_9↓, agb3_10 fixed)

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 3 | **Cycle:** 0 | **Iteration:** 8
**Date:** 2026-04-04 23:59:23
**Confidence:** 0.85

---

## Hypothesis: P-Supplementation Protocol Restoration with Evidence-Based Parameter Trio (phos_retrans_10↑, HF_mort_9↓, agb3_10 fixed)

### Mechanism

Seven consecutive diagnostic cycles have conclusively identified TRANS_SUPLPHOS=NONE as a structural simulation protocol failure — not a parameter estimation problem. With LABILEP depleted from 13.90 to 0.00 g/m² and total P input (1.51 g/m²/yr) 4 orders of magnitude below demand (126,187 g/m²/yr), no combination of the 162 ensemble parameters can compensate. The ECA nutrient competition module allocates near-zero P to all three PFTs simultaneously (PFT7: uptake/demand = 3.53/69,667; PFT9: 0.31/39,944; PFT10: 1.75/16,576), driving the PID allocation controller into futile cycling, preventing structural C accumulation, inducing stomatal closure, and triggering hydraulic failure mortality cascades (PFT9: 100%, PFT7: 83%, PFT10: 73%). Restoring TRANS_SUPLPHOS=ALL eliminates the P supply constraint, allowing LABILEP to recover and all three PFTs to build stoichiometrically balanced organs. Three evidence-based parameter modifications are applied simultaneously from Case #86 baseline: (1) phos_retrans_10 → 0.90 for both leaf (organ=1) and fineroot (organ=2) — 5-cycle consistent positive correlation r=+0.040 to +0.0648 with PFT10 leaf and froot, partial r=+0.0429 p=0.0027 after controlling for vmax_p_10, maximizes P recycled per senescence event reducing net LABILEP demand per unit biomass turnover; (2) mort_scalar_hydrfailure_9 → 0.10 — 5-cycle consistent negative correlation r=-0.097 to -0.201 with PFT9 leaf, isolated quartile analysis shows 388.5% PFT9 leaf improvement p<1e-14, removes the dominant mortality pathway that has been killing PFT9 even when P is partially available; (3) allom_agb3_10 maintained at 0.986 (lower bound) — empirically confirmed superior over 2.881 (Case #4670), lower allometric exponent reduces above-ground structural C sink strength appropriate for the graminoid growth form of PFT10. The causal chain is: TRANS_SUPLPHOS=ALL → LABILEP recovery → P uptake/demand ratio >0 → PID builds balanced organs → structural C accumulates → stomatal conductance normalizes → HF mortality cascade ceases → all 6 biomass targets become achievable. The three parameter modifications address secondary bottlenecks that will emerge once the primary P starvation is resolved.

### Design Type

cumulative

---

## AI Reasoning and Analysis

Seven consecutive diagnostic cycles have conclusively identified TRANS_SUPLPHOS=NONE as a structural simulation protocol failure — not a parameter estimation problem. With LABILEP depleted from 13.90 to 0.00 g/m² and total P input (1.51 g/m²/yr) 4 orders of magnitude below demand (126,187 g/m²/yr), no combination of the 162 ensemble parameters can compensate. The ECA nutrient competition module allocates near-zero P to all three PFTs simultaneously (PFT7: uptake/demand = 3.53/69,667; PFT9: 0.31/39,944; PFT10: 1.75/16,576), driving the PID allocation controller into futile cycling, preventing structural C accumulation, inducing stomatal closure, and triggering hydraulic failure mortality cascades (PFT9: 100%, PFT7: 83%, PFT10: 73%). Restoring TRANS_SUPLPHOS=ALL eliminates the P supply constraint, allowing LABILEP to recover and all three PFTs to build stoichiometrically balanced organs. Three evidence-based parameter modifications are applied simultaneously from Case #86 baseline: (1) phos_retrans_10 → 0.90 for both leaf (organ=1) and fineroot (organ=2) — 5-cycle consistent positive correlation r=+0.040 to +0.0648 with PFT10 leaf and froot, partial r=+0.0429 p=0.0027 after controlling for vmax_p_10, maximizes P recycled per senescence event reducing net LABILEP demand per unit biomass turnover; (2) mort_scalar_hydrfailure_9 → 0.10 — 5-cycle consistent negative correlation r=-0.097 to -0.201 with PFT9 leaf, isolated quartile analysis shows 388.5% PFT9 leaf improvement p<1e-14, removes the dominant mortality pathway that has been killing PFT9 even when P is partially available; (3) allom_agb3_10 maintained at 0.986 (lower bound) — empirically confirmed superior over 2.881 (Case #4670), lower allometric exponent reduces above-ground structural C sink strength appropriate for the graminoid growth form of PFT10. The causal chain is: TRANS_SUPLPHOS=ALL → LABILEP recovery → P uptake/demand ratio >0 → PID builds balanced organs → structural C accumulates → stomatal conductance normalizes → HF mortality cascade ceases → all 6 biomass targets become achievable. The three parameter modifications address secondary bottlenecks that will emerge once the primary P starvation is resolved.

---

## Parameters to Modify

### fates_cnp_turnover_phos_retrans (PFT#10) [leaf]
- **Current:** 0.871
- **Proposed:** 0.9
- **Rationale:** Five-cycle consistent positive correlation with PFT10 leaf biomass (r=+0.040 to +0.0648, all p<0.006). Partial correlation r=+0.0429 (p=0.0027) after controlling for vmax_p_10 confirms independent effect beyond P uptake capacity. At 0.90 (upper ensemble bound), maximizes P recycled per leaf senescence event — under restored P conditions this directly reduces net demand on LABILEP pool per unit leaf turnover, allowing PFT10 to maintain larger standing leaf biomass with lower gross P uptake requirement.

### fates_cnp_turnover_phos_retrans (PFT#10) [fineroot]
- **Current:** 0.871
- **Proposed:** 0.9
- **Rationale:** Category B parameter — must match leaf organ (organ=1) value. Fine root senescence also returns P to litter; maximizing retranslocation fraction reduces net P loss per fineroot turnover event. Cycle 6 confirmed r=+0.0648 (p<0.0001) vs PFT10 froot biomass. With fine root longevity (turnover_fnrt_10) in the ensemble at 0.5–5.0 yr range, high retranslocation fraction is especially impactful when turnover is fast.

### fates_mort_scalar_hydrfailure (PFT#9)
- **Current:** 0.287
- **Proposed:** 0.1
- **Rationale:** PFT9 suffers 100% hydraulic failure mortality fraction under current protocol. Five-cycle consistent negative correlation with PFT9 leaf: r=-0.123 (Cycle 3), r=-0.097 (Cycle 4), r=-0.201 isolated (Cycle 5), r=-0.1218 constrained (Cycle 6). Isolated quartile analysis shows 388.5% PFT9 leaf improvement (p<1e-14) when this parameter is reduced. Even with TRANS_SUPLPHOS=ALL, residual HF mortality at 0.287 will suppress PFT9 recovery. Reducing to 0.10 (within ensemble bounds [0.05, 0.881]) removes dominant mortality pathway. STRICTLY PFT9-SPECIFIC: PFT7 (r=+0.060) and PFT10 (r=+0.103) show POSITIVE correlations — reducing their HF scalars causes PFT7 leaf -83.4% and PFT10 leaf -64.6%. Do NOT modify PFT7 (current: 0.164) or PFT10 (current: 0.770) HF scalars.

### fates_allom_agb3 (PFT#10)
- **Current:** 0.986
- **Proposed:** 0.986
- **Rationale:** MAINTAIN at lower bound — do not change. Empirically confirmed superior to Case #4670 value of 2.881. Both achieve 3/6 targets under current protocol but lower allom_agb3_10 provides better PFT10 biomass scaling consistent with graminoid growth form where above-ground structural C demand scales sub-linearly with diameter. Must be explicitly documented to prevent reversion to default 1.94 during re-spinup parameter file preparation.


---

## Expected Outcomes

- **PFT10_leaf_gCm2:** 65.0
- **PFT10_froot_gCm2:** 200.0
- **PFT7_leaf_gCm2:** 22.0
- **PFT7_froot_gCm2:** 160.0
- **PFT9_leaf_gCm2:** 115.0
- **PFT9_froot_gCm2:** 195.0
- **targets_met_expected:** 5
- **targets_met_minimum_success:** 4
- **LABILEP_recovery_gCm2:** 8.0
- **P_uptake_demand_ratio_minimum:** 0.05
- **PFT9_HF_mortality_fraction_maximum:** 0.3

---

## Metadata

```json
{
  "iteration": 8,
  "diagnosis_count": 8,
  "base_case": {
    "case_id": 86,
    "composite_rmsre": 0.562969471091657,
    "targets_met": 3
  },
  "lowest_cost_case": {
    "case_id": 2939,
    "composite_rmsre": 0.4690570693488718,
    "targets_met": 2
  },
  "validation": "ValidationResult(issues=[])"
}
```

---

## Iteration Context

```json
{
  "calibration_round": 3,
  "iteration": 8,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-04-04T23:59:23.090093",
  "site": "Kougarok",
  "session_id": "20260404_224442",
  "experiment_count": 0,
  "skip_testing_count": 7,
  "diagnosis_count": 8,
  "base_case": {
    "case_id": 86,
    "composite_rmsre": 0.562969471091657,
    "targets_met": 3
  },
  "lowest_cost_case": {
    "case_id": 2939,
    "composite_rmsre": 0.4690570693488718,
    "targets_met": 2
  },
  "validation": "ValidationResult(issues=[])"
}
```
