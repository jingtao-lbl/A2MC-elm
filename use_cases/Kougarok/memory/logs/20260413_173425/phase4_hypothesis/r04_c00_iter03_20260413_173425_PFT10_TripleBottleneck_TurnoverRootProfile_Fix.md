# PFT10_TripleBottleneck_TurnoverRootProfile_Fix

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 4 | **Cycle:** 0 | **Iteration:** 3
**Base Case:** #86
**Date:** 2026-04-14 10:50:27
**Confidence:** 0.72

---

## Hypothesis: PFT10_TripleBottleneck_TurnoverRootProfile_Fix

### Mechanism

PFT#10 (Arctic graminoid) exhibits three compounding mechanistic failures: (1) Excessive fine root turnover at 3.07 yr (Case #86) — while this is already elevated within the Morris range [0.5–5.0], the diagnosis identifies P starvation as the primary driver meaning faster turnover may actually help by reducing the standing root P demand and allowing the existing P supply to maintain a smaller but adequate root pool; however the current value may be too high causing excessive C/N/P flux through the root pool. (2) Root profile parameters appear backwards for a graminoid: fnrt_prof_a_10=12.33 and fnrt_prof_b_10=3.26 in Case #86 — Arctic graminoids (sedges/grasses) concentrate roots in the shallow organic horizon (top 10–20 cm) where nutrient mineralization is highest; high 'a' values concentrate roots at depth, which is wrong for PFT#10 and reduces access to shallow P. Reducing both 'a' and 'b' shifts the root distribution shallower. (3) The P starvation (≈zero P uptake) is the primary bottleneck: vmax_p_10=3.57e-5 in Case #86 is already at the upper portion of the Morris range [5e-11, 5e-5], suggesting the ECA competition framework has PFT#10 losing to PFT#9 for soil P. The mechanistic chain is: wrong root depth profile → roots not co-located with shallow P mineralization hotspots → ECA uptake depressed despite adequate vmax → P starvation → allocation failure → both leaf and fineroot biomass collapse. The fix targets: (a) reduce fnrt_prof_a_10 to shallow the root distribution, (b) reduce fnrt_prof_b_10 to broaden shallow root access, (c) modestly reduce turnover_fnrt_10 to reduce P demand flux through the root pool. This is a cumulative design targeting sequential mechanisms: root placement → nutrient access → biomass recovery.

### Design Type

cumulative

---

## AI Reasoning and Analysis

PFT#10 (Arctic graminoid) exhibits three compounding mechanistic failures: (1) Excessive fine root turnover at 3.07 yr (Case #86) — while this is already elevated within the Morris range [0.5–5.0], the diagnosis identifies P starvation as the primary driver meaning faster turnover may actually help by reducing the standing root P demand and allowing the existing P supply to maintain a smaller but adequate root pool; however the current value may be too high causing excessive C/N/P flux through the root pool. (2) Root profile parameters appear backwards for a graminoid: fnrt_prof_a_10=12.33 and fnrt_prof_b_10=3.26 in Case #86 — Arctic graminoids (sedges/grasses) concentrate roots in the shallow organic horizon (top 10–20 cm) where nutrient mineralization is highest; high 'a' values concentrate roots at depth, which is wrong for PFT#10 and reduces access to shallow P. Reducing both 'a' and 'b' shifts the root distribution shallower. (3) The P starvation (≈zero P uptake) is the primary bottleneck: vmax_p_10=3.57e-5 in Case #86 is already at the upper portion of the Morris range [5e-11, 5e-5], suggesting the ECA competition framework has PFT#10 losing to PFT#9 for soil P. The mechanistic chain is: wrong root depth profile → roots not co-located with shallow P mineralization hotspots → ECA uptake depressed despite adequate vmax → P starvation → allocation failure → both leaf and fineroot biomass collapse. The fix targets: (a) reduce fnrt_prof_a_10 to shallow the root distribution, (b) reduce fnrt_prof_b_10 to broaden shallow root access, (c) modestly reduce turnover_fnrt_10 to reduce P demand flux through the root pool. This is a cumulative design targeting sequential mechanisms: root placement → nutrient access → biomass recovery.

---

## Parameters to Modify

### fates_allom_fnrt_prof_a (PFT#10)
- **Current:** 12.332857142857142
- **Proposed:** 5.75
- **Rationale:** fnrt_prof_a controls the exponential decay rate of root distribution with depth. Higher values concentrate roots deeper. Arctic graminoids (Eriophorum, Carex) concentrate 80–90% of root biomass in the top 15 cm organic horizon where P mineralization is active. Reducing from 12.33 to 5.75 (lower Morris bound) shifts root centroid shallower, improving co-location with P availability. This is the lower Morris bound — scientifically justified by tundra root ecology literature showing graminoids are among the shallowest-rooted PFTs in Arctic systems.

### fates_allom_fnrt_prof_b (PFT#10)
- **Current:** 3.26
- **Proposed:** 3.26
- **Rationale:** fnrt_prof_b_10 in Case #86 is already at the lower Morris bound [3.26, 9.78]. No change proposed — this is already at the minimum allowed value. Including here to confirm it is correctly at its lower bound and should not be reduced further without bound expansion. OMITTING from proposed changes — value equals current, would be a no-op.

### fates_turnover_fnrt (PFT#10)
- **Current:** 3.071428571428571
- **Proposed:** 1.5
- **Rationale:** Reducing fine root turnover from 3.07 yr to 1.5 yr for PFT#10 reduces the standing demand for P to maintain the root pool. With P starvation, a lower turnover RATE (fewer roots dying and needing replacement) means less P demand flux per unit time, allowing the limited P supply to maintain existing roots rather than continuously recycling. Arctic sedge graminoids have measured root longevity of 1–2 years (Iversen et al. 2015, New Phytologist). The current 3.07 yr is ecologically too long for graminoids and paradoxically creates higher P demand by requiring more replacement. At 1.5 yr, turnover is faster but C/P cycling is more consistent with observations.

### fates_cnp_vmax_p (PFT#10)
- **Current:** 3.5714300000000005e-05
- **Proposed:** 5e-05
- **Rationale:** Modestly increase P uptake Vmax for PFT#10 beyond the current Morris upper bound to break the ECA competitive deadlock with PFT#9. PFT#9 currently has vmax_p_9=2.14e-5 while PFT#10 has 3.57e-5 but still shows near-zero P uptake, suggesting the ECA competition is nonlinear and PFT#10 needs a larger advantage in uptake affinity to overcome PFT#9's larger root biomass. The proposed 5e-5 is 40% above the current Morris upper bound [5e-11, 5e-5] — flagged as OUT OF MORRIS BOUNDS. This is scientifically justified: graminoids with high root surface area per unit biomass (aerenchyma-rich roots) have higher specific uptake rates than shrubs. Recommend expanding Morris upper bound to 1e-4 in Phase 0 redesign.


---

## Parameter Validation Report

| Parameter | Check | Status | Detail |
|-----------|-------|--------|--------|
| fates_allom_fnrt_prof_b | no-op | WARNING | proposed=3.26 is unchanged from current=3.26 (delta <0.1%) |

**Summary:** 0 auto-fixed, 1 warning(s), 0 error(s)

---

## Expected Outcomes

- **froot_pft10:** 45.0
- **leaf_pft10:** 25.0
- **froot_pft9:** 60.0
- **leaf_pft9:** 115.0
- **froot_pft7:** 30.0
- **leaf_pft7:** 80.0

---

## Metadata

```json
{
  "iteration": 3,
  "diagnosis_count": 3,
  "base_case": {
    "case_id": 86,
    "composite_rmsre": 0.5530835421160863,
    "targets_met": 2
  },
  "lowest_cost_case": {
    "case_id": 86,
    "composite_rmsre": 0.5530835421160863,
    "targets_met": 2
  },
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_allom_fnrt_prof_b', check='no-op', severity='warning', detail='proposed=3.26 is unchanged from current=3.26 (delta <0.1%)', old_value=None, new_value=None)])"
}
```

---

## Iteration Context

```json
{
  "calibration_round": 4,
  "iteration": 3,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-04-14T10:50:27.899469",
  "site": "Kougarok",
  "session_id": "20260413_173425",
  "experiment_count": 0,
  "skip_testing_count": 2,
  "diagnosis_count": 3,
  "base_case": {
    "case_id": 86,
    "composite_rmsre": 0.5530835421160863,
    "targets_met": 2
  },
  "lowest_cost_case": {
    "case_id": 86,
    "composite_rmsre": 0.5530835421160863,
    "targets_met": 2
  },
  "validation": "ValidationResult(issues=[ValidationIssue(parameter='fates_allom_fnrt_prof_b', check='no-op', severity='warning', detail='proposed=3.26 is unchanged from current=3.26 (delta <0.1%)', old_value=None, new_value=None)])"
}
```
