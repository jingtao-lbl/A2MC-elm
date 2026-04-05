# P-Supplementation Protocol Unlock + Allometric-Turnover Structural Fix for PFT10 Graminoid

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 3 | **Cycle:** 0 | **Iteration:** 4
**Date:** 2026-04-04 23:29:50
**Confidence:** 0.72

---

## Hypothesis: P-Supplementation Protocol Unlock + Allometric-Turnover Structural Fix for PFT10 Graminoid

### Mechanism

The diagnosis conclusively identifies a single root cause: TRANS_SUPLPHOS=NONE creates a cold-turkey P cutoff at calibration phase start, leaving LABILEP=0.00 g/m² and P uptake/demand ratio=0.00 for all three PFTs. No parameter combination within the current 162-parameter Morris ensemble can create P from nothing — the 4-order-of-magnitude supply/demand mismatch (1.51 vs 126,187 g/m²/yr) is mechanistically irreducible by parameter tuning alone. The primary intervention is a protocol-level change: A2MC_TRANS_SUPLPHOS from NONE→ALL, which will restore P supplementation during the transient calibration phase and allow LABILEP to recover from zero.

Secondary structural constraints compound PFT10 underperformance under any P regime:
1. fates_turnover_fnrt for PFT10 (discovered absent from prior 138-parameter Morris, now confirmed at default=1 yr in the current 162-parameter ensemble) — literature values for Arctic graminoid fine roots exceed 5 years, meaning current turnover is 5× too fast, systematically depleting PFT10 fineroot biomass pool
2. allom_agb3_10 at lower bound (0.986 in Case #86) is confirmed as the primary discriminating allometric parameter between the two 3-target cases (#86 vs #4670), and the lower bound is empirically better for PFT10 under P-depleted AND likely under P-supplemented conditions for this graminoid PFT
3. fates_mort_scalar_hydrfailure for PFT9 (NOT PFT7 or PFT10 — Cycle 3 confirmed reducing HF scalar for PFT7/PFT10 HURTS them by -83.4% and -64.6% respectively) — reducing PFT9 HF scalar exploits the confirmed negative correlation (r=-0.123) and the Cycle 3 all-low-HF result showing PFT9 leaf +563.4%

The causal chain being addressed: TRANS_SUPLPHOS=NONE → LABILEP=0 → P_uptake=0 → PID futile allocation → no structural C accumulation → hydraulic failure cascade → all 6 targets fail. Enabling TRANS_SUPLPHOS=ALL breaks the first link. The secondary parameter adjustments (turnover_fnrt_10 lengthening, mort_scalar_hydrfailure_9 reduction) address confirmed structural constraints that will become rate-limiting once the P supply bottleneck is removed.

### Design Type

cumulative

---

## AI Reasoning and Analysis

The diagnosis conclusively identifies a single root cause: TRANS_SUPLPHOS=NONE creates a cold-turkey P cutoff at calibration phase start, leaving LABILEP=0.00 g/m² and P uptake/demand ratio=0.00 for all three PFTs. No parameter combination within the current 162-parameter Morris ensemble can create P from nothing — the 4-order-of-magnitude supply/demand mismatch (1.51 vs 126,187 g/m²/yr) is mechanistically irreducible by parameter tuning alone. The primary intervention is a protocol-level change: A2MC_TRANS_SUPLPHOS from NONE→ALL, which will restore P supplementation during the transient calibration phase and allow LABILEP to recover from zero.

Secondary structural constraints compound PFT10 underperformance under any P regime:
1. fates_turnover_fnrt for PFT10 (discovered absent from prior 138-parameter Morris, now confirmed at default=1 yr in the current 162-parameter ensemble) — literature values for Arctic graminoid fine roots exceed 5 years, meaning current turnover is 5× too fast, systematically depleting PFT10 fineroot biomass pool
2. allom_agb3_10 at lower bound (0.986 in Case #86) is confirmed as the primary discriminating allometric parameter between the two 3-target cases (#86 vs #4670), and the lower bound is empirically better for PFT10 under P-depleted AND likely under P-supplemented conditions for this graminoid PFT
3. fates_mort_scalar_hydrfailure for PFT9 (NOT PFT7 or PFT10 — Cycle 3 confirmed reducing HF scalar for PFT7/PFT10 HURTS them by -83.4% and -64.6% respectively) — reducing PFT9 HF scalar exploits the confirmed negative correlation (r=-0.123) and the Cycle 3 all-low-HF result showing PFT9 leaf +563.4%

The causal chain being addressed: TRANS_SUPLPHOS=NONE → LABILEP=0 → P_uptake=0 → PID futile allocation → no structural C accumulation → hydraulic failure cascade → all 6 targets fail. Enabling TRANS_SUPLPHOS=ALL breaks the first link. The secondary parameter adjustments (turnover_fnrt_10 lengthening, mort_scalar_hydrfailure_9 reduction) address confirmed structural constraints that will become rate-limiting once the P supply bottleneck is removed.

---

## Parameters to Modify

### fates_turnover_fnrt (PFT#10)
- **Current:** 1.0
- **Proposed:** 4.5
- **Rationale:** Discovery 'morris_missing_critical_parameters' (confidence=1.0) confirmed PFT10 turnover_fnrt was absent from the 138-parameter ensemble at 1.0 yr — 5× faster than Arctic literature values (>5 yr). Now included in 162-parameter ensemble as turnover_fnrt_10 with range [0.5, 5.0]. Increasing to 4.5 yr reduces the fineroot turnover flux by 4.5×, allowing fineroot biomass to accumulate toward target (187.35 g/m²). This is the most mechanistically grounded secondary intervention: fineroot steady-state biomass = GPP_allocation / turnover_rate, so 4.5× slower turnover → proportionally higher steady-state froot pool. Value 4.5 yr chosen near but not at the upper bound (5.0) to avoid potential carbon storage feedback anomalies at extreme longevity.

### fates_mort_scalar_hydrfailure (PFT#9)
- **Current:** 0.6
- **Proposed:** 0.12
- **Rationale:** PFT9-SPECIFIC only. Cycle 3 confirmed negative correlation (r=-0.123, p<0.0001) for PFT9 — the ONLY PFT where reducing HF scalar is beneficial. PFT9 shows 100% hydraulic failure mortality fraction. All-low-HF analysis showed PFT9 leaf +563.4% when HF scalar is reduced. Reducing from default 0.6 to 0.12 (80% reduction) is within ensemble bounds [0.05, 0.880957031]. This directly reduces the dominant mortality pathway for PFT9. CRITICAL: PFT7 and PFT10 mort_scalar_hydrfailure are NOT modified — Cycle 3 proved reducing those causes PFT7 leaf -83.4% and PFT10 leaf -64.6%. The positive correlation of mort_scalar_hydrfailure_10 with PFT10 biomass (r=+0.103) is confounded but must be respected.

### fates_cnp_turnover_phos_retrans (PFT#10) [leaf]
- **Current:** 0.871
- **Proposed:** 0.89
- **Rationale:** Maintaining near upper bound (0.9) as consistently supported by Cycle 2 (r=+0.057, p=0.019) and Cycle 3 (r=+0.046, p=0.019) positive correlations with PFT10 leaf biomass. Once TRANS_SUPLPHOS=ALL enables P uptake, maximizing P retranslocation from senescing leaves reduces gross P demand per unit leaf production. The marginal gain from 0.871→0.89 is small but consistently positive and within bounds [0.7, 0.9]. This is priority 2 — cannot rescue PFT10 alone but is the most consistently evidenced secondary CNP lever for PFT10 across both previous cycles.

### fates_cnp_turnover_phos_retrans (PFT#10) [fineroot]
- **Current:** 0.871
- **Proposed:** 0.89
- **Rationale:** Fineroot organ pair for retranslocation parameter — Category B organ-dependent parameter requiring leaf (organ=1) and fineroot (organ=2) entries with matching values. Same rationale: maximize P recovery from senescing fine roots to reduce net P demand. Under Arctic conditions where P is scarce even with supplementation, maximizing P internal cycling is mechanistically sound.

### fates_turnover_fnrt (PFT#9)
- **Current:** 1.0
- **Proposed:** 2.5
- **Rationale:** PFT9 fineroot target is 187.35 g/m² and Case #86 achieves 224.26 g/m² — a 19.7% overestimate. Current turnover_fnrt_9 default=1.0 yr in ensemble range [0.5, 5.0]. Moderate increase to 2.5 yr will slightly increase fineroot steady-state biomass, maintaining PFT9 froot within target range while allowing rebalancing. CAUTION: PFT9 froot is already above target in Case #86, so this should not push it further up — however the increase is secondary to the P-supply fix which may change the steady-state. Set conservatively at 2.5 yr rather than maximum.


---

## Expected Outcomes

- **PFT7_leaf_gCm2:** 95.0
- **PFT7_froot_gCm2:** 170.0
- **PFT9_leaf_gCm2:** 125.0
- **PFT9_froot_gCm2:** 195.0
- **PFT10_leaf_gCm2:** 55.0
- **PFT10_froot_gCm2:** 150.0
- **targets_met_within_20pct:** 4
- **rationale:** TRANS_SUPLPHOS=ALL is expected to rescue PFT7 and PFT9 leaf/froot from zero P starvation. PFT10 froot improvement driven primarily by turnover_fnrt_10 4.5× increase (1.0→4.5 yr), which should raise steady-state froot pool by ~3-4× from current near-zero. PFT9 HF mortality reduction expected to increase PFT9 leaf by +100-500% (Cycle 3 showed +563% under all-low-HF, but PFT9-specific reduction will have smaller effect). PFT10 leaf improvement depends entirely on P availability restoration — conservative estimate given remaining structural constraints. Allometric allom_agb3_10 maintained at lower bound (0.986) as confirmed better for PFT10.

---

## Metadata

```json
{
  "iteration": 4,
  "diagnosis_count": 4,
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
  "iteration": 4,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-04-04T23:29:50.098198",
  "site": "Kougarok",
  "session_id": "20260404_224442",
  "experiment_count": 0,
  "skip_testing_count": 3,
  "diagnosis_count": 4,
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
