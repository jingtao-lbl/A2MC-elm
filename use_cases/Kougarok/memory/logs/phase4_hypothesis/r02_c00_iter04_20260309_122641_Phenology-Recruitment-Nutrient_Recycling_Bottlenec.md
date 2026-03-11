# Phenology-Recruitment-Nutrient Recycling Bottleneck

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 2 | **Cycle:** 0 | **Iteration:** 4
**Date:** 2026-03-09 13:12:29
**Confidence:** 0.72

---

## Hypothesis: Phenology-Recruitment-Nutrient Recycling Bottleneck

### Mechanism

Three cycles of hypothesis testing have revealed that PFT#10 biomass is NOT primarily controlled by P uptake rates (vmax_p, vmax_ptase) or allometric parameters (d2bl1, dbh_maxheight), but rather by a cascade of phenology-recruitment-nutrient recycling parameters. The strongest correlation with PFT#10 total biomass is phen_gddthresh_c (r=-0.326), a shared phenology parameter controlling GDD threshold slope. More negative values delay leaf-on timing, shortening the growing season and reducing C assimilation. Combined with frag_seed_decay_rate_10 (r=-0.240, controlling seed bank persistence), nitr_retrans_10 (r=0.180, controlling N recycling efficiency), and recruit_seed_supplement_10 (r=0.159, controlling external seed input), these parameters form a bottleneck where PFT#10 graminoids: (1) have insufficient growing season length due to phenology thresholds, (2) lose seeds before germination due to high decay, (3) fail to recycle enough N to sustain growth, and (4) lack recruitment subsidies. Case #322 has phen_gddthresh_c=-0.0121 (middle of range), frag_seed_decay_rate_10=0.193, nitr_retrans_10=0.7 (at upper bound), and recruit_seed_supplement_10=0.0345. The hypothesis is that PFT#10 performance is primarily limited by this phenology-recruitment nexus, NOT nutrient uptake kinetics.

### Design Type

factorial

---

## AI Reasoning and Analysis

Three cycles of hypothesis testing have revealed that PFT#10 biomass is NOT primarily controlled by P uptake rates (vmax_p, vmax_ptase) or allometric parameters (d2bl1, dbh_maxheight), but rather by a cascade of phenology-recruitment-nutrient recycling parameters. The strongest correlation with PFT#10 total biomass is phen_gddthresh_c (r=-0.326), a shared phenology parameter controlling GDD threshold slope. More negative values delay leaf-on timing, shortening the growing season and reducing C assimilation. Combined with frag_seed_decay_rate_10 (r=-0.240, controlling seed bank persistence), nitr_retrans_10 (r=0.180, controlling N recycling efficiency), and recruit_seed_supplement_10 (r=0.159, controlling external seed input), these parameters form a bottleneck where PFT#10 graminoids: (1) have insufficient growing season length due to phenology thresholds, (2) lose seeds before germination due to high decay, (3) fail to recycle enough N to sustain growth, and (4) lack recruitment subsidies. Case #322 has phen_gddthresh_c=-0.0121 (middle of range), frag_seed_decay_rate_10=0.193, nitr_retrans_10=0.7 (at upper bound), and recruit_seed_supplement_10=0.0345. The hypothesis is that PFT#10 performance is primarily limited by this phenology-recruitment nexus, NOT nutrient uptake kinetics.

---

## Parameters to Modify

### fates_phen_gddthresh_c
- **Current:** -0.012130998857142857
- **Proposed:** varied in ensemble [-0.015, -0.005]
- **Rationale:** Strongest single correlate with PFT#10 biomass (r=-0.326). More negative = higher GDD threshold = later leaf-on = shorter growing season. SHARED parameter - need to verify effect on all PFTs.

### fates_frag_seed_decay_rate
- **Current:** 0.19297223771428573
- **Proposed:** varied in ensemble [0.10, 0.75]
- **Rationale:** Second strongest PFT#10-specific correlate (r=-0.240). Lower decay = more persistent seed bank = more recruitment = more biomass.

### fates_cnp_turnover_nitr_retrans
- **Current:** 0.7
- **Proposed:** varied in ensemble [0.6, 0.7]
- **Rationale:** Third strongest correlate (r=0.180). Higher retranslocation = more N recycled = less N limitation. Case #322 already at upper bound (0.7).

### fates_recruit_seed_supplement
- **Current:** 0.03450753385714286
- **Proposed:** varied in ensemble [0.001, 0.048]
- **Rationale:** Fourth correlate (r=0.159). External seed input subsidizes recruitment when internal seed production is low.

### fates_leaf_vcmax25top
- **Current:** 64.23293509428572
- **Proposed:** varied in ensemble [58.4, 99.4]
- **Rationale:** Sixth correlate (r=-0.135). Counterintuitively negative - higher Vcmax may increase C assimilation but trigger faster nutrient depletion or PID reallocation. Need to verify direction.


---

## Expected Outcomes

- **pft10_biomass_increase_with_less_negative_gddthresh:** Cases with phen_gddthresh_c closer to -0.005 should have higher PFT#10 biomass (longer growing season)
- **pft10_biomass_increase_with_low_seed_decay:** Cases with frag_seed_decay_rate_10 < 0.15 should have >30% more PFT#10 biomass than those >0.5
- **interaction_gddthresh_x_seed_decay:** Combined favorable phenology + low seed decay should show nonlinear positive interaction
- **cross_pft_phenology_tradeoff:** phen_gddthresh_c changes should affect PFT#7 and PFT#9 as well - need to quantify tradeoff

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
  "validation": "ValidationResult(issues=[])"
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
  "timestamp": "2026-03-09T13:12:29.311100",
  "site": "Kougarok",
  "session_id": "20260309_122641",
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
  "validation": "ValidationResult(issues=[])"
}
```
