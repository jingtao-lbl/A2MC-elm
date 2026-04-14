# PFT10 Fine Root Longevity and Depth Profile Correction for Arctic Graminoid Biomass Recovery

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 4 | **Cycle:** 0 | **Iteration:** 6
**Base Case:** #86
**Date:** 2026-04-14 10:58:52
**Confidence:** 0.72

---

## Hypothesis: PFT10 Fine Root Longevity and Depth Profile Correction for Arctic Graminoid Biomass Recovery

### Mechanism

PFT#10 (Arctic graminoid) fineroot biomass is severely underestimated due to two compounding structural errors: (1) fates_turnover_fnrt_10 = 3.07 yr is already elevated but the diagnosis indicates excessive turnover relative to observed Arctic graminoid root longevity (~3-5 yr is realistic, so this may already be near-appropriate — the key question is whether the root profile parameters are the primary bottleneck); (2) fates_allom_fnrt_prof_a_10 = 12.33 and fates_allom_fnrt_prof_b_10 = 3.26 define the vertical root distribution shape. High values of parameter 'a' concentrate roots near the surface, which is correct for shrubs (PFT#9) but WRONG for graminoids that exploit deeper soil horizons for nutrient access in Arctic tundra. With P uptake near zero for PFT#10 (P starvation diagnosis), the root distribution determines WHERE roots compete for ECA-mediated soil P. If PFT#10 roots are concentrated in the same shallow horizon as PFT#9 (shrubs), PFT#9 (with much higher GPP = 5-10× higher) will dominate ECA competition and starve PFT#10 of P. Shifting PFT#10 root profile deeper (lower 'a', lower 'b') would: (a) reduce direct ECA competition with PFT#9 for shallow P pools, (b) access deeper unfrozen mineral soil P, and (c) modestly reduce the total fineroot C demand if combined with slightly longer turnover. The Morris ensemble already includes fnrt_prof_a_10 in [5.75, 17.27] and fnrt_prof_b_10 in [3.26, 9.78], so we can test the hypothesis that LOWER values of both (deeper root profile) correlate with higher PFT#10 fineroot biomass. Current base case #86 has fnrt_prof_a_10 = 12.33 (mid-to-upper range) and fnrt_prof_b_10 = 3.26 (at lower bound). The testable prediction: cases with fnrt_prof_a_10 < 9.0 should show higher PFT#10 fineroot biomass because they compete in deeper soil layers where PFT#9 root density is lower, reducing ECA competition and allowing non-zero P uptake. Simultaneously, turnover_fnrt_10 = 3.07 yr should be examined — cases with higher turnover (shorter longevity) correlate with lower steady-state fineroot biomass since biomass = production × longevity.

### Design Type

cumulative

---

## AI Reasoning and Analysis

PFT#10 (Arctic graminoid) fineroot biomass is severely underestimated due to two compounding structural errors: (1) fates_turnover_fnrt_10 = 3.07 yr is already elevated but the diagnosis indicates excessive turnover relative to observed Arctic graminoid root longevity (~3-5 yr is realistic, so this may already be near-appropriate — the key question is whether the root profile parameters are the primary bottleneck); (2) fates_allom_fnrt_prof_a_10 = 12.33 and fates_allom_fnrt_prof_b_10 = 3.26 define the vertical root distribution shape. High values of parameter 'a' concentrate roots near the surface, which is correct for shrubs (PFT#9) but WRONG for graminoids that exploit deeper soil horizons for nutrient access in Arctic tundra. With P uptake near zero for PFT#10 (P starvation diagnosis), the root distribution determines WHERE roots compete for ECA-mediated soil P. If PFT#10 roots are concentrated in the same shallow horizon as PFT#9 (shrubs), PFT#9 (with much higher GPP = 5-10× higher) will dominate ECA competition and starve PFT#10 of P. Shifting PFT#10 root profile deeper (lower 'a', lower 'b') would: (a) reduce direct ECA competition with PFT#9 for shallow P pools, (b) access deeper unfrozen mineral soil P, and (c) modestly reduce the total fineroot C demand if combined with slightly longer turnover. The Morris ensemble already includes fnrt_prof_a_10 in [5.75, 17.27] and fnrt_prof_b_10 in [3.26, 9.78], so we can test the hypothesis that LOWER values of both (deeper root profile) correlate with higher PFT#10 fineroot biomass. Current base case #86 has fnrt_prof_a_10 = 12.33 (mid-to-upper range) and fnrt_prof_b_10 = 3.26 (at lower bound). The testable prediction: cases with fnrt_prof_a_10 < 9.0 should show higher PFT#10 fineroot biomass because they compete in deeper soil layers where PFT#9 root density is lower, reducing ECA competition and allowing non-zero P uptake. Simultaneously, turnover_fnrt_10 = 3.07 yr should be examined — cases with higher turnover (shorter longevity) correlate with lower steady-state fineroot biomass since biomass = production × longevity.

---

## Parameters to Modify

### fates_allom_fnrt_prof_a (PFT#10)
- **Current:** 12.332857142857142
- **Proposed:** 6.5
- **Rationale:** Reduce root profile concentration parameter 'a' to shift PFT#10 graminoid roots to deeper soil horizons. Arctic graminoids (sedges, grasses) have deeper root systems than shrubs, exploiting mineral soil nutrient pools. Lower 'a' spreads roots more uniformly with depth, reducing ECA competition with PFT#9 in the organic-rich surface layer where shrubs dominate. This is scientifically justified by Arctic root ecology literature showing Eriophorum and Carex species reaching 40-80 cm depth.

### fates_allom_fnrt_prof_b (PFT#10)
- **Current:** 3.26
- **Proposed:** 3.26
- **Rationale:** HOLD at current lower bound value (3.26). fnrt_prof_b_10 is already at its Morris lower bound. Reducing further would be out-of-bounds and scientifically uncertain. Focus the root profile correction on parameter 'a' only to isolate the mechanism. Flag: current value is AT THE LOWER BOUND — if the existing data test shows b should decrease further, recommend bound expansion in Phase 0 redesign.

### fates_turnover_fnrt (PFT#10)
- **Current:** 3.071428571428571
- **Proposed:** 4.5
- **Rationale:** Increase fine root longevity from 3.07 to 4.5 yr for PFT#10 Arctic graminoids. Steady-state fineroot biomass = production_rate × turnover_time. With P starvation limiting production, extending root longevity is the most direct lever to increase standing stock without requiring higher nutrient uptake. Arctic tundra graminoid fine root longevity measurements (Iversen et al. 2015, Sloan et al. 2013) range from 2-7 yr, with mean ~4-5 yr for sedges. Current value of 3.07 yr may be underestimating actual longevity. This is within the Morris sampling range [0.5, 5.0]. Note: from the failed approaches list, 4x turnover increase was part of a crashed experiment — but that crash was due to simultaneous extreme ptase change, NOT turnover alone. Modest increase from 3.07 to 4.5 (1.46×) is conservative and should be safe.


---

## Parameter Validation Report

| Parameter | Check | Status | Detail |
|-----------|-------|--------|--------|
| fates_allom_fnrt_prof_b | no-op | WARNING | proposed=3.26 is unchanged from current=3.26 (delta <0.1%) |

**Summary:** 0 auto-fixed, 1 warning(s), 0 error(s)

---

## Expected Outcomes

- **froot_pft10:** Increase from ~current underestimate toward observation target. Mechanistically: if root depth shift reduces ECA competition by 30-50%, P uptake should rise from near-zero to measurable levels, allowing fineroot biomass to accumulate. Combined with longer turnover (4.5 vs 3.07 yr, +46% longevity multiplier), expected froot increase of 40-80% relative to Case #86 baseline.
- **leaf_pft10:** Secondary benefit: if P starvation is partially relieved by reduced ECA competition, PID allocation controller should shift resources toward leaf growth. Expected modest improvement in leaf biomass (10-30%), but leaf_pft10 is secondary to froot_pft10 fix.
- **froot_pft9:** Should remain stable or slightly increase — PFT#9 roots are not being modified, and deeper PFT#10 roots reduce (not increase) competition at PFT#9's preferred shallow depth.
- **leaf_pft9:** Should remain stable — no direct modification to PFT#9 parameters.
- **agb_pft7:** Unaffected — PFT#7 is a different functional type with independent root zone.

---

## Metadata

```json
{
  "iteration": 6,
  "diagnosis_count": 6,
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
  "iteration": 6,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-04-14T10:58:52.580173",
  "site": "Kougarok",
  "session_id": "20260413_173425",
  "experiment_count": 0,
  "skip_testing_count": 5,
  "diagnosis_count": 6,
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
