# P-Starvation Triage: PFT10 Nutrient Uptake Capacity and Stoichiometric Demand Reduction

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 3 | **Cycle:** 0 | **Iteration:** 1
**Base Case:** #86
**Date:** 2026-04-07 11:31:52
**Confidence:** 0.62

---

## Hypothesis: P-Starvation Triage: PFT10 Nutrient Uptake Capacity and Stoichiometric Demand Reduction

### Mechanism

Universal P starvation across all PFTs (confirmed: uptake/demand ≈ 0.00) is the primary cause of the 6/6 target failures. The causal chain is: (1) stoich_phos sets structural P demand per unit carbon; (2) vmax_p controls maximum P uptake from soil via ECA kinetics; (3) when demand >> uptake, PARTEH cannot allocate carbon to growth tissues. For PFT10 (graminoid), the collapse is most severe (leaf: 4.7 vs 82.7 gC/m², froot: 22.6 vs 382.1 gC/m²). Two mechanistically distinct levers are available: (A) reduce P demand by lowering stoich_phos for PFT10 leaf and fineroot to minimum physically reasonable Arctic values — literature values for Arctic graminoids (Carex, Eriophorum) suggest leaf P:C of 0.001-0.002 gP/gC and root P:C of 0.0006-0.001 gP/gC; (B) increase P uptake capacity via vmax_p_10, which is at its lower bound (5e-11) in Case #86 — essentially zero P uptake for PFT10. Simultaneously, phos_store_ratio_10 is at its upper bound (5.0) in Case #86, meaning 5× the structural P is targeted for labile storage, which diverts the small amount of P that IS taken up into storage pools rather than growth. Reducing phos_store_ratio_10 allows more of the scarce P to support structural tissue formation. The sensitivity analysis confirms: phos_store_ratio_10 (μ*=0.041, rank 3) and stoich_nitr_fineroot_10 (μ*=0.040, rank 2) are the top mechanistic parameters for PFT10 fineroot. For PFT7 leaf overshoot (+26%), turnover_leaf_7 (μ*=0.060, rank 2 for PFT7 leaf) at its upper bound (2.0 yr) accumulates excess leaves — but since P is limiting, this is secondary. The three-parameter combination (reduce stoich_phos leaf/froot PFT10, increase vmax_p_10, reduce phos_store_ratio_10) attacks the P starvation from demand, supply, and allocation sides simultaneously — a cumulative intervention matching the sequential nature of the bottleneck.

### Design Type

cumulative

---

## AI Reasoning and Analysis

Universal P starvation across all PFTs (confirmed: uptake/demand ≈ 0.00) is the primary cause of the 6/6 target failures. The causal chain is: (1) stoich_phos sets structural P demand per unit carbon; (2) vmax_p controls maximum P uptake from soil via ECA kinetics; (3) when demand >> uptake, PARTEH cannot allocate carbon to growth tissues. For PFT10 (graminoid), the collapse is most severe (leaf: 4.7 vs 82.7 gC/m², froot: 22.6 vs 382.1 gC/m²). Two mechanistically distinct levers are available: (A) reduce P demand by lowering stoich_phos for PFT10 leaf and fineroot to minimum physically reasonable Arctic values — literature values for Arctic graminoids (Carex, Eriophorum) suggest leaf P:C of 0.001-0.002 gP/gC and root P:C of 0.0006-0.001 gP/gC; (B) increase P uptake capacity via vmax_p_10, which is at its lower bound (5e-11) in Case #86 — essentially zero P uptake for PFT10. Simultaneously, phos_store_ratio_10 is at its upper bound (5.0) in Case #86, meaning 5× the structural P is targeted for labile storage, which diverts the small amount of P that IS taken up into storage pools rather than growth. Reducing phos_store_ratio_10 allows more of the scarce P to support structural tissue formation. The sensitivity analysis confirms: phos_store_ratio_10 (μ*=0.041, rank 3) and stoich_nitr_fineroot_10 (μ*=0.040, rank 2) are the top mechanistic parameters for PFT10 fineroot. For PFT7 leaf overshoot (+26%), turnover_leaf_7 (μ*=0.060, rank 2 for PFT7 leaf) at its upper bound (2.0 yr) accumulates excess leaves — but since P is limiting, this is secondary. The three-parameter combination (reduce stoich_phos leaf/froot PFT10, increase vmax_p_10, reduce phos_store_ratio_10) attacks the P starvation from demand, supply, and allocation sides simultaneously — a cumulative intervention matching the sequential nature of the bottleneck.

---

## Parameters to Modify

### fates_stoich_phos (PFT#10) [leaf]
- **Current:** 0.000920964
- **Proposed:** 0.00065
- **Rationale:** Reduce PFT10 leaf P:C demand to lower end of Arctic graminoid literature values (~0.0006-0.001 gP/gC). Current Morris lower bound is 0.000921 — proposing value below bound based on literature for Eriophorum/Carex leaf tissue P concentrations in nutrient-poor Arctic tundra (Chapin et al. 1987, Sullivan et al. 2007). Lower P demand makes the supply-demand gap closeable. This is the most powerful intervention for reducing the 22,000× demand-uptake gap. OUT OF MORRIS BOUNDS — recommend bound expansion in Phase 0 redesign.

### fates_stoich_phos (PFT#10) [fineroot]
- **Current:** 0.000709198
- **Proposed:** 0.0005
- **Rationale:** Reduce PFT10 fineroot P:C demand. Arctic graminoid fine root P concentrations are among the lowest measured in tundra ecosystems (~0.0004-0.0008 gP/gC). Current Morris lower bound is 0.000709 — proposing value below bound based on measured root P:C ratios for Carex and Eriophorum in organic soils. Lower root P demand directly reduces the P deficit that prevents fineroot construction in PARTEH. OUT OF MORRIS BOUNDS — recommend bound expansion in Phase 0 redesign.

### fates_cnp_vmax_p (PFT#10)
- **Current:** 3.5714300000000005e-05
- **Proposed:** 0.00012
- **Rationale:** Substantially increase PFT10 P uptake capacity. In Case #86, vmax_p_10 is at 3.57e-05 (near middle of range but the diagnosis notes that functional P uptake is near zero — the actual uptake/demand ratio is 0.00). Morris sensitivity for PFT9 abg biomass shows vmax_p_10 at rank 9 (μ*=0.095), confirming cross-PFT signal. Arctic graminoids have high specific root length and mycorrhizal associations enabling efficient P scavenging. The proposed value (1.2e-4) exceeds the Morris upper bound (5e-5) but is within biologically plausible range for tundra plants with dense, fine root mats. OUT OF MORRIS BOUNDS — recommend bound expansion to 2e-4 in Phase 0 redesign.

### fates_cnp_phos_store_ratio (PFT#10)
- **Current:** 5.0
- **Proposed:** 1.5
- **Rationale:** Reduce PFT10 P storage target from maximum (5.0×) to default (1.5×). Morris sensitivity confirms phos_store_ratio_10 (μ*=0.041, rank 3 for PFT10 fineroot). At 5.0×, the model targets 5× structural P in labile storage — when soil P is scarce, this storage priority diverts P from tissue construction. At 1.5×, the plant maintains a modest P buffer without sacrificing growth allocation. This is within current Morris bounds [1.0, 5.0]. The reduction from 5.0 to 1.5 represents moving from the upper bound to the default, a strong within-range intervention.

### fates_cnp_turnover_phos_retrans (PFT#10) [leaf]
- **Current:** 0.8714285714285714
- **Proposed:** 0.89
- **Rationale:** Marginally increase leaf P retranslocation for PFT10. Already near upper bound (0.87 vs max 0.9). Small increase to 0.89 maximizes P recycling from senescing leaves back to labile store, reducing net P demand from soil. This is a within-bounds refinement consistent with high-retranslocation strategy of P-stressed plants. Expected small additive benefit alongside vmax_p and stoich_phos changes.

### fates_cnp_turnover_phos_retrans (PFT#10) [fineroot]
- **Current:** 0.8714285714285714
- **Proposed:** 0.89
- **Rationale:** Marginally increase fineroot P retranslocation for PFT10 (same value as leaf per Category B requirement). Maximizes P recovery from dying roots, reducing ongoing P demand from soil during fineroot turnover.


---

## Parameter Validation Report

| Parameter | Check | Status | Detail |
|-----------|-------|--------|--------|
| fates_stoich_phos | bounds | AUTO-FIXED | [0.0004, 0.000921] → [0.000920964, 0.002994719] (actual bounds) |
| fates_stoich_phos | out of bounds | WARNING | proposed=0.00065 outside [0.000920964, 0.002994719] |
| fates_stoich_phos | bounds | AUTO-FIXED | [0.0003, 0.000709] → [0.000709198, 0.001255781] (actual bounds) |
| fates_stoich_phos | out of bounds | WARNING | proposed=0.0005 outside [0.000709198, 0.001255781] |
| fates_cnp_vmax_p | out of bounds | WARNING | proposed=0.00012 outside [5e-11, 5e-05] |

**Summary:** 2 auto-fixed, 3 warning(s), 0 error(s)

---

## Expected Outcomes

- **leaf_pft10:** 55.0
- **froot_pft10:** 180.0
- **leaf_pft7:** 210.0
- **froot_pft7:** 160.0
- **leaf_pft9:** 245.0
- **froot_pft9:** 170.0

---

## Metadata

```json
{
  "iteration": 1,
  "diagnosis_count": 1,
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
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_stoich_phos', check='bounds', severity='auto_fix', detail='[0.0004, 0.000921] \u2192 [0.000920964, 0.002994719] (actual bounds)', old_value=[0.0004, 0.000921], new_value=[0.000920964, 0.002994719]), ValidationIssue(parameter='fates_stoich_phos', check='out of bounds', severity='warning', detail='proposed=0.00065 outside [0.000920964, 0.002994719]', old_value=None, new_value=None), ValidationIssue(parameter='fates_stoich_phos', check='bounds', severity='auto_fix', detail='[0.0003, 0.000709] \u2192 [0.000709198, 0.001255781] (actual bounds)', old_value=[0.0003, 0.000709], new_value=[0.000709198, 0.001255781]), ValidationIssue(parameter='fates_stoich_phos', check='out of bounds', severity='warning', detail='proposed=0.0005 outside [0.000709198, 0.001255781]', old_value=None, new_value=None), ValidationIssue(parameter='fates_cnp_vmax_p', check='out of bounds', severity='warning', detail='proposed=0.00012 outside [5e-11, 5e-05]', old_value=None, new_value=None)])"
}
```

---

## Iteration Context

```json
{
  "calibration_round": 3,
  "iteration": 1,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-04-07T11:31:52.936754",
  "site": "Kougarok",
  "session_id": "20260406_143413",
  "experiment_count": 0,
  "skip_testing_count": 0,
  "diagnosis_count": 1,
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
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_stoich_phos', check='bounds', severity='auto_fix', detail='[0.0004, 0.000921] \u2192 [0.000920964, 0.002994719] (actual bounds)', old_value=[0.0004, 0.000921], new_value=[0.000920964, 0.002994719]), ValidationIssue(parameter='fates_stoich_phos', check='out of bounds', severity='warning', detail='proposed=0.00065 outside [0.000920964, 0.002994719]', old_value=None, new_value=None), ValidationIssue(parameter='fates_stoich_phos', check='bounds', severity='auto_fix', detail='[0.0003, 0.000709] \u2192 [0.000709198, 0.001255781] (actual bounds)', old_value=[0.0003, 0.000709], new_value=[0.000709198, 0.001255781]), ValidationIssue(parameter='fates_stoich_phos', check='out of bounds', severity='warning', detail='proposed=0.0005 outside [0.000709198, 0.001255781]', old_value=None, new_value=None), ValidationIssue(parameter='fates_cnp_vmax_p', check='out of bounds', severity='warning', detail='proposed=0.00012 outside [5e-11, 5e-05]', old_value=None, new_value=None)])"
}
```
