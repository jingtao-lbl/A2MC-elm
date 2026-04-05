# Protocol Fix: TRANS_SUPLPHOS=ALL Restoration with Case #86 Optimized Parameter Set

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 3 | **Cycle:** 0 | **Iteration:** 7
**Date:** 2026-04-04 23:51:46
**Confidence:** 0.78

---

## Hypothesis: Protocol Fix: TRANS_SUPLPHOS=ALL Restoration with Case #86 Optimized Parameter Set

### Mechanism

Seven consecutive diagnostic cycles have conclusively established that TRANS_SUPLPHOS=NONE creates a catastrophic P starvation cascade that no parameter combination within the 162-parameter ensemble can overcome. The mechanism is: (1) LABILEP depleted from 13.90 to 0.00 g/m² during spinup under NONE setting; (2) P uptake/demand ratio = 0.00 for all PFTs (PFT7: 3.53 vs 69,667 g/m²/yr demanded; PFT9: 0.31 vs 39,944; PFT10: 1.75 vs 16,576); (3) Total P input 1.51 g/m²/yr vs demand 126,187 g/m²/yr = 4-order-of-magnitude mismatch; (4) PID controller drives futile C allocation cycles because stoichiometrically balanced organs cannot be constructed without P; (5) No net structural C accumulation leads to stomatal closure cascade; (6) Hydraulic failure mortality dominates as secondary symptom (PFT7: 83%, PFT9: 100%, PFT10: 73%); (7) All 6 biomass targets fail. Post-protocol-fix, the simulation must start from Case #86 parameter configuration (best case, 3/6 targets met under P starvation) with three evidence-based modifications: (a) phos_retrans_10 increased to 0.90 (five-cycle consistent positive correlation r=+0.040 to +0.0648, partial r=+0.0429 p=0.0027 controlling for vmax_p_10); (b) mort_scalar_hydrfailure_9 decreased to 0.10 (five-cycle consistent negative correlation r=-0.097 to -0.201, PFT9-isolated quartile 388.5% leaf improvement p<1e-14); (c) allom_agb3_10 maintained at 0.986 lower bound (empirically confirmed superior to 2.881 in Case #4670). Under P-replete conditions, these modifications target the three confirmed secondary bottlenecks that are currently masked by P starvation but will emerge as rate-limiting once P is restored.

### Design Type

cumulative

---

## AI Reasoning and Analysis

Seven consecutive diagnostic cycles have conclusively established that TRANS_SUPLPHOS=NONE creates a catastrophic P starvation cascade that no parameter combination within the 162-parameter ensemble can overcome. The mechanism is: (1) LABILEP depleted from 13.90 to 0.00 g/m² during spinup under NONE setting; (2) P uptake/demand ratio = 0.00 for all PFTs (PFT7: 3.53 vs 69,667 g/m²/yr demanded; PFT9: 0.31 vs 39,944; PFT10: 1.75 vs 16,576); (3) Total P input 1.51 g/m²/yr vs demand 126,187 g/m²/yr = 4-order-of-magnitude mismatch; (4) PID controller drives futile C allocation cycles because stoichiometrically balanced organs cannot be constructed without P; (5) No net structural C accumulation leads to stomatal closure cascade; (6) Hydraulic failure mortality dominates as secondary symptom (PFT7: 83%, PFT9: 100%, PFT10: 73%); (7) All 6 biomass targets fail. Post-protocol-fix, the simulation must start from Case #86 parameter configuration (best case, 3/6 targets met under P starvation) with three evidence-based modifications: (a) phos_retrans_10 increased to 0.90 (five-cycle consistent positive correlation r=+0.040 to +0.0648, partial r=+0.0429 p=0.0027 controlling for vmax_p_10); (b) mort_scalar_hydrfailure_9 decreased to 0.10 (five-cycle consistent negative correlation r=-0.097 to -0.201, PFT9-isolated quartile 388.5% leaf improvement p<1e-14); (c) allom_agb3_10 maintained at 0.986 lower bound (empirically confirmed superior to 2.881 in Case #4670). Under P-replete conditions, these modifications target the three confirmed secondary bottlenecks that are currently masked by P starvation but will emerge as rate-limiting once P is restored.

---

## Parameters to Modify

### fates_cnp_turnover_phos_retrans (PFT#10) [leaf]
- **Current:** 0.871
- **Proposed:** 0.9
- **Rationale:** Five-cycle consistent positive correlation with PFT10 leaf biomass (r=+0.040 to +0.0648, all p<0.006). Partial correlation r=+0.0429 (p=0.0027) controlling for vmax_p_10 confirms independence from P uptake capacity. At upper bound of ensemble range [0.70, 0.90]. Maximizes P recovery per leaf senescence event — critical under any residual P limitation after protocol fix. Category B parameter: must match organ=2 value.

### fates_cnp_turnover_phos_retrans (PFT#10) [fineroot]
- **Current:** 0.871
- **Proposed:** 0.9
- **Rationale:** Category B parameter (same value for leaf and fineroot organs). Cycle 6 confirmed r=+0.0648 (p<0.0001) vs PFT10 froot biomass. Maximizes P recovery from senescing fine roots, reducing net P loss per root turnover event. Must be set equal to organ=1 value per FATES CNP parameter structure.

### fates_mort_scalar_hydrfailure (PFT#9)
- **Current:** 0.287
- **Proposed:** 0.1
- **Rationale:** PFT9-SPECIFIC ONLY. Five-cycle consistent negative correlation with PFT9 leaf biomass: r=-0.123 (Cycle 3), r=-0.097 (Cycle 4), r=-0.201 isolated (Cycle 5), r=-0.1218 constrained (Cycle 6). PFT9-isolated HF quartile analysis shows 388.5% PFT9 leaf improvement (p<1e-14). PFT9 suffers 100% hydraulic failure mortality fraction under current parameter set. Reducing to lower-bound region (0.10) removes dominant mortality pathway for PFT9. DO NOT modify PFT7 (r=+0.060 positive, current 0.164) or PFT10 (r=+0.103 positive, current 0.770) — confirmed harmful in Cycles 3-6 (-83.4% and -64.6% respectively).

### fates_allom_agb3 (PFT#10)
- **Current:** 0.986
- **Proposed:** 0.986
- **Rationale:** MAINTAIN at lower bound — do not change. Empirically confirmed superior: Case #86 (allom_agb3_10=0.986) achieves 3/6 targets vs Case #4670 (allom_agb3_10=2.881) achieving different target profile. Lower AGB allometry exponent for PFT10 (herbaceous tundra) reduces above-ground structural biomass demand, allowing more C to flow to leaf and root pools under nutrient-limited conditions. Explicitly maintaining this value in the parameter file to prevent reversion to default (1.94).


---

## Expected Outcomes

- **PFT7_leaf:** 95-160 g C/m² (target: 124.6, valid range 99.7-149.5) — P restoration enables C fixation; PFT7 already captures 63.2% of P uptake so should recover well
- **PFT7_froot:** 140-210 g C/m² (target: 174.25, valid range 139.4-209.1) — Case #86 already within range under P starvation; P restoration should maintain or improve
- **PFT9_leaf:** 100-150 g C/m² (target: 124.7, valid range 99.8-149.6) — mort_scalar_hydrfailure_9 reduction to 0.10 removes dominant mortality; P restoration enables growth; 388.5% improvement expected from HF reduction alone
- **PFT9_froot:** 150-225 g C/m² (target: 187.35, valid range 149.9-224.8) — Case #86 currently 224.26 (passing); maintain within range post-protocol-fix
- **PFT10_leaf:** 20-60 g C/m² (target: 36.64, valid range 29.3-44.0) — phos_retrans_10=0.90 and allom_agb3_10=0.986 together should enable C accumulation once P available; highest uncertainty
- **PFT10_froot:** 30-80 g C/m² (target: 49.93, valid range 39.9-59.9) — zero correlation with turnover_fnrt_10 under P starvation means this will be the key test of whether P restoration unlocks froot accumulation

---

## Metadata

```json
{
  "iteration": 7,
  "diagnosis_count": 7,
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
  "iteration": 7,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-04-04T23:51:46.500939",
  "site": "Kougarok",
  "session_id": "20260404_224442",
  "experiment_count": 0,
  "skip_testing_count": 6,
  "diagnosis_count": 7,
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
