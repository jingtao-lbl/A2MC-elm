# Hydraulic Failure Mortality Reduction + PFT10 P-Retranslocation Maximization

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 3 | **Cycle:** 0 | **Iteration:** 3
**Date:** 2026-04-04 23:22:20
**Confidence:** 0.62

---

## Hypothesis: Hydraulic Failure Mortality Reduction + PFT10 P-Retranslocation Maximization

### Mechanism

Diagnosis confirms ecologically anomalous hydraulic failure dominates all three PFTs (PFT7: 83%, PFT9: 100%, PFT10: 73% hydraulic cause fraction) in a moisture-sufficient arctic tundra system. The mechanistic pathway is: P starvation → reduced GPP → reduced turgor maintenance capacity → stomatal closure → altered soil moisture dynamics → hydraulic failure threshold triggered. This is a proxy-hydraulic mortality cascade driven by P limitation, NOT genuine soil moisture deficit. Two intervention levers exist: (1) Reducing mort_scalar_hydrfailure for all PFTs will reduce the per-day mortality fraction when soil moisture falls below the threshold, directly reducing the mortality rate. For arctic tundra, hydraulic failure mortality scalars of 0.05-0.15 are more ecologically appropriate than current values (PFT10: 0.770 in Case #86). (2) Simultaneously maximizing phos_retrans_10 (leaf+fineroot, organ=1 and 2) toward the upper bound of 0.90 recycles more P within PFT10's limited P budget per senescence cycle — the only parameter showing a positive correlation with PFT10 leaf in Cycle 2 (r=0.057, p<0.0001). For PFT7 and PFT9, phos_retrans is also at suboptimal values relative to ecological expectation under P depletion. The combined effect: reduced mortality allows more PFT10 cohorts to survive and accumulate biomass even under P limitation, while higher retranslocation reduces per-cycle P loss, allowing the small P uptake (31.3% of 5.59 g/m²/yr = 1.75 g/m²/yr) to maintain higher steady-state biomass. This is a cumulative design because the mortality reduction must precede meaningful biomass accumulation before retranslocation efficiency can compound its benefit.

### Design Type

cumulative

---

## AI Reasoning and Analysis

Diagnosis confirms ecologically anomalous hydraulic failure dominates all three PFTs (PFT7: 83%, PFT9: 100%, PFT10: 73% hydraulic cause fraction) in a moisture-sufficient arctic tundra system. The mechanistic pathway is: P starvation → reduced GPP → reduced turgor maintenance capacity → stomatal closure → altered soil moisture dynamics → hydraulic failure threshold triggered. This is a proxy-hydraulic mortality cascade driven by P limitation, NOT genuine soil moisture deficit. Two intervention levers exist: (1) Reducing mort_scalar_hydrfailure for all PFTs will reduce the per-day mortality fraction when soil moisture falls below the threshold, directly reducing the mortality rate. For arctic tundra, hydraulic failure mortality scalars of 0.05-0.15 are more ecologically appropriate than current values (PFT10: 0.770 in Case #86). (2) Simultaneously maximizing phos_retrans_10 (leaf+fineroot, organ=1 and 2) toward the upper bound of 0.90 recycles more P within PFT10's limited P budget per senescence cycle — the only parameter showing a positive correlation with PFT10 leaf in Cycle 2 (r=0.057, p<0.0001). For PFT7 and PFT9, phos_retrans is also at suboptimal values relative to ecological expectation under P depletion. The combined effect: reduced mortality allows more PFT10 cohorts to survive and accumulate biomass even under P limitation, while higher retranslocation reduces per-cycle P loss, allowing the small P uptake (31.3% of 5.59 g/m²/yr = 1.75 g/m²/yr) to maintain higher steady-state biomass. This is a cumulative design because the mortality reduction must precede meaningful biomass accumulation before retranslocation efficiency can compound its benefit.

---

## Parameters to Modify

### fates_mort_scalar_hydrfailure (PFT#7)
- **Current:** 0.164
- **Proposed:** 0.05
- **Rationale:** PFT7 shows 83% hydraulic failure mortality fraction despite being the best-performing PFT. For arctic shrubs (PFT7), hydraulic failure should be rare. Reducing to ensemble lower bound (0.05) eliminates the proxy-P-starvation hydraulic mortality cascade for PFT7 while preserving true drought response capacity. Current value 0.164 already low but still contributes to 83% mortality cause fraction — must reduce to minimum.

### fates_mort_scalar_hydrfailure (PFT#9)
- **Current:** 0.287
- **Proposed:** 0.05
- **Rationale:** PFT9 shows 100% hydraulic failure mortality fraction — the most extreme pathology. Despite mort_scalar_hydrfailure_9=0.287 being relatively low, the 100% hydraulic cause fraction indicates the mort_hf_sm_threshold_9 (at upper bound 1.4209e-06 in Case #86) is triggering mortality on nearly every timestep. Reducing the scalar to 0.05 will drastically reduce per-event mortality rate. Note: mort_hf_sm_threshold_9 is NOT in the Morris ensemble parameter list and cannot be changed here — addressing the scalar is the only available lever for PFT9.

### fates_mort_scalar_hydrfailure (PFT#10)
- **Current:** 0.77
- **Proposed:** 0.05
- **Rationale:** PFT10 (graminoid) has mort_scalar_hydrfailure_10=0.770 — nearly at upper bound — while exhibiting 73% hydraulic failure mortality. Arctic graminoids have shallow roots in consistently moist organic soils and experience very low hydraulic failure rates empirically. The 0.770 value is ecologically inappropriate. Reducing to 0.05 (ensemble lower bound) removes the dominant PFT10 mortality pathway, allowing surviving cohorts to accumulate biomass. This is the highest-priority single parameter change for PFT10 biomass recovery.

### fates_cnp_turnover_phos_retrans (PFT#10) [leaf]
- **Current:** 0.871
- **Proposed:** 0.9
- **Rationale:** Cycle 2 confirmed positive correlation with PFT10 leaf (r=0.057, p<0.0001). Current value 0.871 is near but not at the upper bound of 0.90. Pushing to maximum reduces per-cycle P loss from leaf senescence. PFT10's short leaf longevity (lower bound ~0.3 yr) means high turnover frequency — every senescence event without retranslocation permanently removes P from the plant P budget. At 0.90 retranslocation, 90% of senesced leaf P is recycled, maximizing the P retention per unit of leaf turnover. Small absolute improvement but consistent with ecological theory for P-stressed arctic vegetation.

### fates_cnp_turnover_phos_retrans (PFT#10) [fineroot]
- **Current:** 0.871
- **Proposed:** 0.9
- **Rationale:** Fineroot retranslocation (organ=2) must match leaf retranslocation (organ=1) — both senescing tissue types contribute to P cycling. PFT10 fineroot biomass is severely underperforming (22.6 vs target in Case #86). Higher fineroot P retranslocation means each fine root cohort death returns more P to the plant storage pool, reducing the net P demand for new fineroot construction. Same value as organ=1 per Category B parameter convention.

### fates_cnp_turnover_phos_retrans (PFT#7) [leaf]
- **Current:** 0.6
- **Proposed:** 0.8
- **Rationale:** PFT7 phos_retrans is at lower bound (0.6) in Case #86 — ecologically anomalous under P depletion where retranslocation should be maximized. Cycle 2 showed positive correlation with PFT7 froot (r=+0.097, p≈0). Increasing from 0.6 to 0.80 (midpoint of range) captures the positive signal without over-correcting. PFT7 froot is already within 20% target in Case #86 (150.6 vs 174.25) — conservative increase prevents disrupting the working PFT7 performance balance.

### fates_cnp_turnover_phos_retrans (PFT#7) [fineroot]
- **Current:** 0.6
- **Proposed:** 0.8
- **Rationale:** Same rationale as organ=1 for PFT7. Fineroot retranslocation must be set consistently with leaf retranslocation per Category B parameter structure. PFT7 fineroot P recycling at 0.6 means 40% of fineroot P is lost per turnover event — increasing to 0.80 reduces this loss by 50% under the same turnover rate.

### fates_cnp_turnover_phos_retrans (PFT#9) [leaf]
- **Current:** 0.72
- **Proposed:** 0.8
- **Rationale:** PFT9 phos_retrans is at intermediate value (0.72, within [0.6, 0.8] range for PFT9). The Cycle 2 stoichiometry tests showed that interventions that reduce PFT9 P demand destroy PFT9 leaf performance (leaf=0.0 g/m²). Increasing P retranslocation does NOT reduce stoichiometric demand — it reduces net P loss per turnover cycle, a safer mechanism. PFT9 leaf is within 20% target in Case #86 (123.16 vs 124.7) — conservative increase to 0.80 maintains current performance while marginally improving P efficiency. This is the upper bound for PFT9.

### fates_cnp_turnover_phos_retrans (PFT#9) [fineroot]
- **Current:** 0.72
- **Proposed:** 0.8
- **Rationale:** Same rationale as organ=1 for PFT9. Fineroot retranslocation to upper bound (0.80) for PFT9. PFT9 froot is within 20% target in Case #86 (224.26 vs 187.35 — slight overestimate). Conservative increase consistent with Category B parameter structure.


---

## Expected Outcomes

- **PFT7_leaf:** 25-35 g/m² (target: 24.55, within 20% = [19.6, 29.5])
- **PFT7_froot:** 160-185 g/m² (target: 174.25, maintain current 150.6 or improve)
- **PFT9_leaf:** 115-130 g/m² (target: 124.7, maintain current 123.16)
- **PFT9_froot:** 185-230 g/m² (target: 187.35, maintain current 224.26)
- **PFT10_leaf:** 10-40 g/m² (target: 82.3, partial improvement from near-zero, mortality reduction alone cannot achieve target without TRANS_SUPLPHOS=ALL)
- **PFT10_froot:** 30-80 g/m² (target: 300+, partial improvement from 22.6, mortality reduction allows cohort survival and biomass accumulation)

---

## Metadata

```json
{
  "iteration": 3,
  "diagnosis_count": 3,
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
  "iteration": 3,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-04-04T23:22:20.100156",
  "site": "Kougarok",
  "session_id": "20260404_224442",
  "experiment_count": 0,
  "skip_testing_count": 2,
  "diagnosis_count": 3,
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
