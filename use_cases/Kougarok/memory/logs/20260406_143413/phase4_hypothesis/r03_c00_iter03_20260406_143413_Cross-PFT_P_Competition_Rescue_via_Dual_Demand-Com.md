# Cross-PFT P Competition Rescue via Dual Demand-Competition Reduction

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 3 | **Cycle:** 0 | **Iteration:** 3
**Base Case:** #86
**Date:** 2026-04-07 11:52:01
**Confidence:** 0.72

---

## Hypothesis: Cross-PFT P Competition Rescue via Dual Demand-Competition Reduction

### Mechanism

Universal P starvation across PFT7, PFT9, and PFT10 is driven by catastrophic ECA soil P depletion (LABILEP 13.90→0.00 gP/m²; SMINP -37.7%). The Case #1385 fingerprint reveals that PFT10 recovery (leaf=69.5 gC/m² vs 4.7 in Case #86) is achieved NOT by PFT10-specific parameters but via cross-PFT mechanisms: (1) reducing PFT9 leaf P stoichiometry from 0.00428 to 0.00210 gP/gC (51% reduction in PFT9 leaf P demand) and (2) reducing PFT9 microbial biomass from 468.6 to 140.0 gC/m³ (ECA competition relief). Together these free shared soil P for PFT10 acquisition. This hypothesis tests whether COMBINING Case #1385's PFT10-enabling cross-PFT parameters WITH Case #86's PFT7/PFT9-enabling parameters (turnover_leaf_7 reduction to fix PFT7_leaf overshoot; phos_retrans_7 increase to reduce PFT7 net P demand; phos_store_ratio_10 and nitr_store_ratio_10 reduction to eliminate the storage trap in PFT10) can simultaneously satisfy all 6 targets. The mechanism is: lower PFT9 leaf P demand + lower PFT9 microbial competition → more soil P available → ECA solver allocates P to PFT10 roots → PARTEH exits P-starvation mode for PFT10 → structural biomass construction resumes. Simultaneously, turnover_leaf_7 reduction corrects the PFT7_leaf +26% overshoot, and phos_retrans_7 increase reduces PFT7 net P soil demand, preserving PFT7_fineroot satisfaction.

### Design Type

cumulative

---

## AI Reasoning and Analysis

Universal P starvation across PFT7, PFT9, and PFT10 is driven by catastrophic ECA soil P depletion (LABILEP 13.90→0.00 gP/m²; SMINP -37.7%). The Case #1385 fingerprint reveals that PFT10 recovery (leaf=69.5 gC/m² vs 4.7 in Case #86) is achieved NOT by PFT10-specific parameters but via cross-PFT mechanisms: (1) reducing PFT9 leaf P stoichiometry from 0.00428 to 0.00210 gP/gC (51% reduction in PFT9 leaf P demand) and (2) reducing PFT9 microbial biomass from 468.6 to 140.0 gC/m³ (ECA competition relief). Together these free shared soil P for PFT10 acquisition. This hypothesis tests whether COMBINING Case #1385's PFT10-enabling cross-PFT parameters WITH Case #86's PFT7/PFT9-enabling parameters (turnover_leaf_7 reduction to fix PFT7_leaf overshoot; phos_retrans_7 increase to reduce PFT7 net P demand; phos_store_ratio_10 and nitr_store_ratio_10 reduction to eliminate the storage trap in PFT10) can simultaneously satisfy all 6 targets. The mechanism is: lower PFT9 leaf P demand + lower PFT9 microbial competition → more soil P available → ECA solver allocates P to PFT10 roots → PARTEH exits P-starvation mode for PFT10 → structural biomass construction resumes. Simultaneously, turnover_leaf_7 reduction corrects the PFT7_leaf +26% overshoot, and phos_retrans_7 increase reduces PFT7 net P soil demand, preserving PFT7_fineroot satisfaction.

---

## Parameters to Modify

### fates_stoich_phos (PFT#9) [leaf]
- **Current:** 0.00428
- **Proposed:** 0.0021
- **Rationale:** PRIMARY LEVER (Case #1385 fingerprint): Reducing PFT9 leaf P:C from upper bound (0.00428) to lower bound (0.00210) cuts PFT9 leaf P demand by 51%. This is the single largest differentiator between Case #86 (PFT10 leaf=4.7 gC/m²) and Case #1385 (PFT10 leaf=69.5 gC/m²). Arctic deciduous shrub (Betula nana, Salix) leaf P:C literature values of 0.0015-0.0030 gP/gC support this reduction. Lower PFT9 P demand frees shared soil P pool for PFT10 via ECA competition. PFT9_leaf is currently satisfied in Case #86 (123.2 vs 124.7 gC/m²) under carbon-based allometry — reducing leaf P:C changes nutrient stoichiometry but not carbon biomass directly, so PFT9_leaf target should be preserved.

### fates_stoich_phos (PFT#9) [fineroot]
- **Current:** 0.002068657
- **Proposed:** 0.0009
- **Rationale:** SECONDARY LEVER (Case #1385 fingerprint confirms stoich_phos_fineroot_9 at lower bound): Reducing PFT9 fineroot P:C reduces PFT9 root tissue P demand. In Case #86, stoich_phos_fineroot_9=0.002068657 (upper bound of Morris range [0.000693992, 0.002068657]). Case #1385 has this at lower bound. Arctic deciduous shrub fineroot P:C literature values (0.0006-0.0012 gP/gC) support reduction. Proposed value 0.000900 is within Morris bounds and will reduce the total PFT9 P sink strength, amplifying the cross-PFT P release. Note: proposed value 0.000900 is within Morris range [0.000693992, 0.002068657].

### fates_cnp_eca_decompmicc (PFT#9)
- **Current:** 468.57142857142856
- **Proposed:** 150.0
- **Rationale:** PRIMARY LEVER (Case #1385 fingerprint, Morris rank #2 for PFT7 fineroot μ*=0.124): Reducing PFT9 microbial biomass from 468.6 to 140.0 gC/m³ was identified as the second strongest differentiator between Case #86 and Case #1385. Microbial biomass in ECA framework directly competes with plant roots for soil P. Lower microb_bio_9 reduces microbial P sequestration, increasing the fraction of soil P available for plant uptake. Proposed value 150.0 gC/m³ is near the lower bound (140 gC/m³) but avoids the exact boundary to prevent numerical artifacts. This reduction benefits ALL three PFTs through the shared soil P pool.

### fates_cnp_eca_decompmicc (PFT#7)
- **Current:** 468.57142857142856
- **Proposed:** 270.0
- **Rationale:** MODERATE REDUCTION (Morris rank #2 for PFT7 fineroot μ*=0.124, rank #6 for PFT7 abg biomass μ*=0.221): Reducing PFT7 microbial biomass from 468.6 to 270.0 gC/m³ (moderate, mid-range) reduces microbial competition for PFT7 P uptake. Unlike PFT9 (aggressive reduction to ~150), PFT7 reduction is kept moderate because PFT7_fineroot is already satisfied (150.7 vs 174.3 gC/m²) and PFT7_leaf is currently overestimated (+26%). Too large a reduction in microb_bio_7 could increase PFT7 P access enough to worsen the leaf overshoot. Proposed 270.0 gC/m³ is conservative — enough to help PFT7 without destabilizing satisfied targets.

### fates_turnover_leaf (PFT#7)
- **Current:** 2.0
- **Proposed:** 1.5
- **Rationale:** CRITICAL FIX for PFT7_leaf overshoot (Morris rank #2 for PFT7 leaf biomass μ*=0.060, rank #2 for PFT7 abg biomass μ*=0.436): PFT7_leaf is currently +26% above target (31.0 vs 24.55 gC/m²) in Case #86. turnover_leaf_7=2.0 yr (at upper bound of [0.3, 2.0]). At steady state, leaf biomass ∝ leaf turnover time. Reducing from 2.0 to 1.5 yr (25% reduction) should reduce standing leaf biomass by approximately 20-25%, bringing PFT7_leaf from ~31.0 to ~23-25 gC/m² (within ±20% of 24.55 target: valid range 19.64-29.46 gC/m²). Arctic evergreen shrub leaf lifespan literature: 1.5-3.0 years, making 1.5 yr scientifically defensible. CAUTION: Also reduces litter input; monitor PFT7_fineroot.

### fates_cnp_turnover_phos_retrans (PFT#7) [leaf]
- **Current:** 0.6
- **Proposed:** 0.78
- **Rationale:** SUPPLEMENTARY LEVER (Case #1385 fingerprint: phos_retrans_7=0.857): Increasing P retranslocation efficiency from 0.60 (lower bound) to 0.78 (mid-range) recycles more P from senescing PFT7 leaves and fineroots back to labile storage, reducing net P demand from soil. Arctic evergreen shrub documented retranslocation: 0.70-0.85 (Aerts 1996, van Heerwaarden et al. 2003). This reduces PFT7 net P soil demand without changing carbon allocation, preserving PFT7_fineroot satisfaction. Proposed 0.78 is deliberately more conservative than Case #1385's 0.857 to avoid over-correcting. Category B parameter — same value for leaf and fineroot organs.

### fates_cnp_turnover_phos_retrans (PFT#7) [fineroot]
- **Current:** 0.6
- **Proposed:** 0.78
- **Rationale:** Category B organ-dependent parameter: same proposed value as organ=1 (leaf). Increases P recycling from senescing PFT7 fineroots, reducing net P soil demand and freeing more ECA-pool P for PFT10.

### fates_cnp_phos_store_ratio (PFT#10)
- **Current:** 5.0
- **Proposed:** 1.5
- **Rationale:** STORAGE TRAP ELIMINATION (Morris rank #3 for PFT10 fineroot μ*=0.041): phos_store_ratio_10=5.0 (upper bound) means PARTEH targets P storage at 5× structural P before allocating to tissue growth. When P uptake is near-zero, this 'storage trap' prevents biomass construction. Reducing to default value 1.5 gP/gP means structural tissue P allocation is prioritized earlier. NOTE: Cycle 2 showed weak positive correlation (r=+0.058) across full ensemble — this counter-intuitive sign is because P starvation dominates in the ensemble and the storage ratio signal is masked. This parameter is a secondary intervention that should amplify the effect of the primary cross-PFT demand reduction (stoich_phos_leaf_9, microb_bio_9).

### fates_cnp_nitr_store_ratio (PFT#10)
- **Current:** 5.0
- **Proposed:** 1.5
- **Rationale:** CO-REDUCTION with phos_store_ratio_10: nitr_store_ratio_10=5.0 (upper bound, not in Case #86 parameter list but confirmed at upper bound from diagnosis context). High N storage target (5× structural N) creates an N storage trap analogous to the P storage trap. Reducing to default 1.5 ensures N storage priority does not compete with structural tissue allocation when N supply is limiting. This is a coupled intervention — both nutrient storage ratios should be reduced simultaneously to prevent single-nutrient storage bottleneck replacing the other.


---

## Parameter Validation Report

| Parameter | Check | Status | Detail |
|-----------|-------|--------|--------|
| fates_stoich_phos | bounds | AUTO-FIXED | [0.0021, 0.00428] → [0.002095471, 0.004278889] (actual bounds) |

**Summary:** 1 auto-fixed, 0 warning(s), 0 error(s)

---

## Expected Outcomes

- **leaf_pft7:** 23.5
- **froot_pft7:** 170.0
- **leaf_pft9:** 120.0
- **froot_pft9:** 195.0
- **leaf_pft10:** 55.0
- **froot_pft10:** 45.0

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
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_stoich_phos', check='bounds', severity='auto_fix', detail='[0.0021, 0.00428] \u2192 [0.002095471, 0.004278889] (actual bounds)', old_value=[0.0021, 0.00428], new_value=[0.002095471, 0.004278889])])"
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
  "timestamp": "2026-04-07T11:52:01.134430",
  "site": "Kougarok",
  "session_id": "20260406_143413",
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
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_stoich_phos', check='bounds', severity='auto_fix', detail='[0.0021, 0.00428] \u2192 [0.002095471, 0.004278889] (actual bounds)', old_value=[0.0021, 0.00428], new_value=[0.002095471, 0.004278889])])"
}
```
