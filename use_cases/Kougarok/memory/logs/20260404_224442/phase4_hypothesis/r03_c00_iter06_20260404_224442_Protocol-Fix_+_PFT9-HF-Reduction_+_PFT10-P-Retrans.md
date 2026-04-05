# Protocol-Fix + PFT9-HF-Reduction + PFT10-P-Retrans Maximization: Post-TRANS_SUPLPHOS=ALL Re-Spinup with Confirmed Secondary Levers

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 3 | **Cycle:** 0 | **Iteration:** 6
**Date:** 2026-04-04 23:47:00
**Confidence:** 0.78

---

## Hypothesis: Protocol-Fix + PFT9-HF-Reduction + PFT10-P-Retrans Maximization: Post-TRANS_SUPLPHOS=ALL Re-Spinup with Confirmed Secondary Levers

### Mechanism

Six cycles of diagnosis have conclusively identified TRANS_SUPLPHOS=NONE as the root cause: LABILEP depleted from 13.90 to 0.00 g/m² during spinup, creating a 4-order-of-magnitude P supply/demand mismatch (1.51 vs 126,187 g/m²/yr). No parameter combination within the 162-parameter ensemble can overcome this physics — P cannot be created from nothing. The mandatory primary intervention is changing TRANS_SUPLPHOS=NONE→ALL to restore P supplementation during the transient calibration phase.

Once P supply is restored, two secondary levers with multi-cycle empirical support are applied simultaneously:

1. PFT9 hydraulic failure mortality reduction: mort_scalar_hydrfailure_9 reduced from 0.287 to 0.10. PFT9 currently suffers 100% HF mortality fraction. Five cycles confirm: r=-0.123 (Cycle 3), r=-0.097 (Cycle 4), r=-0.201 isolated (Cycle 5), 388.5% leaf improvement in PFT9-isolated quartile analysis (p<1e-14). PFT7 and PFT10 HF scalars MUST remain fixed at Case #86 values (0.164 and 0.770) — Cycle 3 confirmed that reducing these causes PFT7 leaf -83.4% and PFT10 leaf -64.6%.

2. PFT10 phosphorus retranslocation maximization: phos_retrans_10 increased from 0.871 to 0.90 (upper bound) for both leaf and fineroot organs. Confirmed across 3 cycles: raw r=+0.0397 (p=0.0055), partial r=+0.0429 (p=0.0027) after controlling for vmax_p_10. Under restored P conditions, maximizing P recycling per senescence event directly reduces net P demand on labile soil pools, amplifying available P for structural biomass growth.

3. PFT10 AGB allometry constraint: allom_agb3_10 maintained at 0.986 (Case #86 lower bound), confirmed as discriminating parameter between the two 3-target cases (#86: 0.986 vs #4670: 2.881 — 100% range difference). Lower exponent reduces above-ground C sink strength, allowing more C to flow toward fineroot accumulation under the graminoid growth form.

Causal chain: TRANS_SUPLPHOS=ALL → LABILEP recovers from 0.00 → P uptake/demand ratio rises from 0.00 → PID controller receives non-zero P signal → stoichiometrically balanced organ construction resumes → stomatal conductance recovers → HF mortality signal drops across all PFTs → PFT9-specific HF reduction (0.10) further lowers remaining PFT9 mortality → PFT10 P retranslocation at 0.90 reduces marginal P demand per leaf/root cycle → net biomass accumulation becomes positive across all 6 targets simultaneously.

### Design Type

cumulative

---

## AI Reasoning and Analysis

Six cycles of diagnosis have conclusively identified TRANS_SUPLPHOS=NONE as the root cause: LABILEP depleted from 13.90 to 0.00 g/m² during spinup, creating a 4-order-of-magnitude P supply/demand mismatch (1.51 vs 126,187 g/m²/yr). No parameter combination within the 162-parameter ensemble can overcome this physics — P cannot be created from nothing. The mandatory primary intervention is changing TRANS_SUPLPHOS=NONE→ALL to restore P supplementation during the transient calibration phase.

Once P supply is restored, two secondary levers with multi-cycle empirical support are applied simultaneously:

1. PFT9 hydraulic failure mortality reduction: mort_scalar_hydrfailure_9 reduced from 0.287 to 0.10. PFT9 currently suffers 100% HF mortality fraction. Five cycles confirm: r=-0.123 (Cycle 3), r=-0.097 (Cycle 4), r=-0.201 isolated (Cycle 5), 388.5% leaf improvement in PFT9-isolated quartile analysis (p<1e-14). PFT7 and PFT10 HF scalars MUST remain fixed at Case #86 values (0.164 and 0.770) — Cycle 3 confirmed that reducing these causes PFT7 leaf -83.4% and PFT10 leaf -64.6%.

2. PFT10 phosphorus retranslocation maximization: phos_retrans_10 increased from 0.871 to 0.90 (upper bound) for both leaf and fineroot organs. Confirmed across 3 cycles: raw r=+0.0397 (p=0.0055), partial r=+0.0429 (p=0.0027) after controlling for vmax_p_10. Under restored P conditions, maximizing P recycling per senescence event directly reduces net P demand on labile soil pools, amplifying available P for structural biomass growth.

3. PFT10 AGB allometry constraint: allom_agb3_10 maintained at 0.986 (Case #86 lower bound), confirmed as discriminating parameter between the two 3-target cases (#86: 0.986 vs #4670: 2.881 — 100% range difference). Lower exponent reduces above-ground C sink strength, allowing more C to flow toward fineroot accumulation under the graminoid growth form.

Causal chain: TRANS_SUPLPHOS=ALL → LABILEP recovers from 0.00 → P uptake/demand ratio rises from 0.00 → PID controller receives non-zero P signal → stoichiometrically balanced organ construction resumes → stomatal conductance recovers → HF mortality signal drops across all PFTs → PFT9-specific HF reduction (0.10) further lowers remaining PFT9 mortality → PFT10 P retranslocation at 0.90 reduces marginal P demand per leaf/root cycle → net biomass accumulation becomes positive across all 6 targets simultaneously.

---

## Parameters to Modify

### fates_mort_scalar_hydrfailure (PFT#9)
- **Current:** 0.287
- **Proposed:** 0.1
- **Rationale:** PFT9 suffers 100% hydraulic failure mortality fraction under P starvation. Five cycles confirm negative relationship: r=-0.123 (Cycle 3), r=-0.097 (Cycle 4), r=-0.201 isolated with PFT7/10 fixed (Cycle 5). PFT9-isolated quartile analysis shows 388.5% leaf improvement at low HF9 values (p<1e-14). After P restoration, HF mortality will decrease ecosystem-wide, but PFT9's remaining HF vulnerability (likely driven by structural water-use parameters distinct from PFT7/10) requires targeted scalar reduction. Value of 0.10 is within ensemble bounds [0.05, 0.881] and well above lower bound to avoid overcorrection.

### fates_cnp_turnover_phos_retrans (PFT#10) [leaf]
- **Current:** 0.871
- **Proposed:** 0.9
- **Rationale:** Leaf phosphorus retranslocation for PFT10. Moving to upper bound (0.90) maximizes P recovery per leaf senescence event. Confirmed across 3 cycles: raw r=+0.0397 (p=0.0055), partial r=+0.0429 (p=0.0027) after controlling for vmax_p_10. Independent of P uptake capacity — effect persists even after removing vmax_p_10 variance. Under restored P conditions this becomes the critical marginal lever for PFT10 leaf biomass maintenance.

### fates_cnp_turnover_phos_retrans (PFT#10) [fineroot]
- **Current:** 0.871
- **Proposed:** 0.9
- **Rationale:** Fineroot phosphorus retranslocation for PFT10. Same value as leaf organ (Category B parameter — same fraction applies to both senescing tissue types). Reduces net P lost per fineroot senescence event, directly reducing the incremental P demand required to maintain fineroot biomass pools. Critical for PFT10 FATES_FROOTC target given that fineroot turnover is the dominant P sink for graminoid PFTs with high root allocation.


---

## Expected Outcomes

- **PFT7_leaf_gCm2:** 180.0
- **PFT7_froot_gCm2:** 170.0
- **PFT9_leaf_gCm2:** 120.0
- **PFT9_froot_gCm2:** 185.0
- **PFT10_leaf_gCm2:** 65.0
- **PFT10_froot_gCm2:** 120.0
- **targets_within_20pct:** 4
- **note:** Targets are approximate post-P-restoration estimates. PFT7 and PFT9 should reach ±20% first given lower P:C demand ratios. PFT10 fineroot (target 187.35 g/m²) most sensitive to phos_retrans_10 lever. PFT10 leaf (target 82.65 g/m²) hardest target requiring full P restoration plus both secondary levers. Current Case #86 PFT10 leaf = 4.68 g/m² — improvement of >10× expected from P restoration alone.

---

## Metadata

```json
{
  "iteration": 6,
  "diagnosis_count": 6,
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
  "iteration": 6,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-04-04T23:47:00.453373",
  "site": "Kougarok",
  "session_id": "20260404_224442",
  "experiment_count": 0,
  "skip_testing_count": 5,
  "diagnosis_count": 6,
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
