# P-Retranslocation Maximization + PFT9-Specific HF Mortality Reduction + PFT10 Allometric Constraint: Multi-Lever Post-Starvation Recovery

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 3 | **Cycle:** 0 | **Iteration:** 5
**Date:** 2026-04-04 23:38:55
**Confidence:** 0.72

---

## Hypothesis: P-Retranslocation Maximization + PFT9-Specific HF Mortality Reduction + PFT10 Allometric Constraint: Multi-Lever Post-Starvation Recovery

### Mechanism

The diagnosis has conclusively established across 5 cycles that TRANS_SUPLPHOS=NONE is the root cause of all 6 target failures, with LABILEP depleted to 0.00 g/m² creating a 4-order-of-magnitude P supply/demand mismatch. However, three secondary parameters have shown consistent directional support across multiple cycles that will become critical once P supplementation is restored: (1) fates_cnp_turnover_phos_retrans for PFT10 (r=+0.057, +0.046, +0.040 across Cycles 2-4) — the only parameter with consistent multi-cycle directional support, maximizing P recycling per senescence event minimizes net P loss from plant P pools; (2) fates_mort_scalar_hydrfailure for PFT9 ONLY (r=-0.123 Cycle 3, r=-0.097 Cycle 4) with confirmed +563.4% PFT9 leaf improvement in all-low-HF analysis — PFT9 suffers 100% HF mortality fraction and PFT9-specific reduction is mechanistically isolated from the harmful effects on PFT7 (-83.4%) and PFT10 (-64.6%); (3) fates_allom_agb3 for PFT10 at lower bound confirmed as the discriminating parameter between the two 3-target cases (#86 vs #4670: 0.986 vs 2.881). The current hypothesis tests whether the existing ensemble already contains sufficient evidence to quantify each lever's independent contribution and their interactions, before proposing a new HPC experiment requiring TRANS_SUPLPHOS=ALL re-spinup. The custom script will perform three sub-analyses: (A) partial correlation of phos_retrans_10 with PFT10 leaf after controlling for vmax_p_10 — to determine whether retranslocation effect is independent of P uptake capacity; (B) PFT9-isolated HF mortality quartile analysis with PFT7 and PFT10 HF fixed at their Case #86 values (0.164 and 0.770) — to quantify the PFT9 HF effect size without cross-PFT contamination; (C) allom_agb3_10 decile analysis conditioned on cases where PFT10 froot > 1.0 g/m² — to detect whether the allometric constraint is active even under marginal P availability.

### Design Type

cumulative

---

## AI Reasoning and Analysis

The diagnosis has conclusively established across 5 cycles that TRANS_SUPLPHOS=NONE is the root cause of all 6 target failures, with LABILEP depleted to 0.00 g/m² creating a 4-order-of-magnitude P supply/demand mismatch. However, three secondary parameters have shown consistent directional support across multiple cycles that will become critical once P supplementation is restored: (1) fates_cnp_turnover_phos_retrans for PFT10 (r=+0.057, +0.046, +0.040 across Cycles 2-4) — the only parameter with consistent multi-cycle directional support, maximizing P recycling per senescence event minimizes net P loss from plant P pools; (2) fates_mort_scalar_hydrfailure for PFT9 ONLY (r=-0.123 Cycle 3, r=-0.097 Cycle 4) with confirmed +563.4% PFT9 leaf improvement in all-low-HF analysis — PFT9 suffers 100% HF mortality fraction and PFT9-specific reduction is mechanistically isolated from the harmful effects on PFT7 (-83.4%) and PFT10 (-64.6%); (3) fates_allom_agb3 for PFT10 at lower bound confirmed as the discriminating parameter between the two 3-target cases (#86 vs #4670: 0.986 vs 2.881). The current hypothesis tests whether the existing ensemble already contains sufficient evidence to quantify each lever's independent contribution and their interactions, before proposing a new HPC experiment requiring TRANS_SUPLPHOS=ALL re-spinup. The custom script will perform three sub-analyses: (A) partial correlation of phos_retrans_10 with PFT10 leaf after controlling for vmax_p_10 — to determine whether retranslocation effect is independent of P uptake capacity; (B) PFT9-isolated HF mortality quartile analysis with PFT7 and PFT10 HF fixed at their Case #86 values (0.164 and 0.770) — to quantify the PFT9 HF effect size without cross-PFT contamination; (C) allom_agb3_10 decile analysis conditioned on cases where PFT10 froot > 1.0 g/m² — to detect whether the allometric constraint is active even under marginal P availability.

---

## Parameters to Modify

### fates_cnp_turnover_phos_retrans (PFT#10) [leaf]
- **Current:** 0.87
- **Proposed:** 0.9
- **Rationale:** Three-cycle consistent positive correlation with PFT10 leaf (r=+0.057, +0.046, +0.040, all p<0.02). At upper bound of Morris range [0.7, 0.9]. Maximizes P retention per leaf senescence cycle — under P-limited conditions, each unit of P retranslocated from senescing leaf avoids one unit of P demand on soil uptake. The marginal benefit is highest when soil P is scarce. Push to absolute upper bound of ensemble range.

### fates_cnp_turnover_phos_retrans (PFT#10) [fineroot]
- **Current:** 0.87
- **Proposed:** 0.9
- **Rationale:** Same retranslocation logic as organ=1 (leaf). Fineroot P retranslocation during senescence recycles P that would otherwise be lost to litter. With LABILEP near zero, every gram of P recycled from senescing fine roots reduces net P demand on the depleted soil pool. Consistent multi-cycle support justifies maximizing both organ values simultaneously.

### fates_mort_scalar_hydrfailure (PFT#9)
- **Current:** 0.287
- **Proposed:** 0.1
- **Rationale:** PFT9-specific reduction ONLY. Consistent negative correlation with PFT9 leaf (r=-0.123 Cycle 3, r=-0.097 Cycle 4, both p<1e-9). All-low-HF analysis confirmed +563.4% PFT9 leaf improvement. PFT9 suffers 100% hydraulic failure mortality fraction — this is a secondary symptom of P starvation (stomatal closure → water stress cascade) but can be partially alleviated by reducing the mortality scalar. The 0.10 target is within the Morris range [0.05, 0.881] and represents a 65% reduction from current Case #86 value. Cycle 3 definitively confirmed PFT7 (0.164, fixed) and PFT10 (0.770, fixed) must NOT be changed simultaneously.

### fates_allom_agb3 (PFT#10)
- **Current:** 0.986
- **Proposed:** 0.986
- **Rationale:** MAINTAIN at current lower-bound value. Confirmed as discriminating parameter between the two 3-target cases (#86: 0.986 vs #4670: 2.881 — 100% range difference). Lower allom_agb3_10 is empirically superior for PFT10 graminoid biomass scaling. The proposed value is unchanged — this entry documents the HOLD decision to prevent accidental modification in next iteration. Do not increase above 1.2 under any circumstances until post-TRANS_SUPLPHOS=ALL validation.


---

## Expected Outcomes

- **pft10_leaf_improvement_pct:** 5-10% improvement from phos_retrans_10 alone under current P starvation; 40-80% improvement expected after TRANS_SUPLPHOS=ALL re-spinup with these parameters held at proposed values
- **pft9_leaf_improvement_pct:** 30-60% improvement from mort_scalar_hydrfailure_9 reduction from 0.287 to 0.10, consistent with +563.4% observed in all-low-HF quadrant scaled by PFT9-isolation factor
- **pft7_leaf_change_pct:** < ±5% — PFT7 HF scalar maintained at 0.164 (fixed), no cross-PFT contamination expected
- **pft10_froot_improvement_pct:** < 10% under current P starvation; primary improvement deferred to post-protocol-fix phase
- **targets_met_current_regime:** 3-4 (up from 3 in Case #86, with PFT9 leaf likely to improve beyond current 123.16 g/m²)
- **targets_met_post_protocol_fix:** 5-6 expected when combined with TRANS_SUPLPHOS=ALL re-spinup

---

## Metadata

```json
{
  "iteration": 5,
  "diagnosis_count": 5,
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
  "iteration": 5,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-04-04T23:38:55.135401",
  "site": "Kougarok",
  "session_id": "20260404_224442",
  "experiment_count": 0,
  "skip_testing_count": 4,
  "diagnosis_count": 5,
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
