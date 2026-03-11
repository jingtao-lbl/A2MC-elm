# PFT10 Hydraulic Mortality Escape + Systemic P Demand Relief via Stoichiometry Correction

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 2 | **Cycle:** 0 | **Iteration:** 3
**Date:** 2026-03-10 00:09:48
**Confidence:** 0.72

---

## Hypothesis: PFT10 Hydraulic Mortality Escape + Systemic P Demand Relief via Stoichiometry Correction

### Mechanism

Three-layer mechanistic failure chain identified in Cycle 3 diagnosis: (1) PRIMARY: mort_hf_sm_threshold_10=1e-08 at absolute lower bound means any non-zero soil moisture triggers hydraulic failure mortality in PFT10, causing 92% of all PFT10 deaths (mean rate 12.58 events). No biomass accumulation is possible when cohorts are continuously erased by hydraulic failure at ecologically unrealistic thresholds. (2) SECONDARY: Systemic P demand inflation from PFT7 (stoich_phos × high root biomass driving 54% of total 358,121 g/m²/yr demand) starves all PFTs of phosphorus via ECA competition, with PFT10 receiving only 2% of soil P supply (0.013 g/m²/yr vs demand 15.5 g/m²/yr). Reducing PFT7 leaf and fineroot P stoichiometry toward literature-supported lower bounds provides proportional P demand relief without disrupting currently-passing PFT7_leaf target. (3) TERTIARY: PFT9 allocation paradox from l2fr_ini_9=18.31 (upper bound) routes >95% of new carbon to fine roots, starving PFT9_leaf (Cycle 2 confirmed r=-0.257 negative correlation). Correcting l2fr_ini_9 restores balanced allocation once P relief allows leaf growth to proceed. The causal sequence: [extreme mort_hf_sm_threshold_10→92% PFT10 death] + [inflated PFT7 stoich_phos→ECA exclusion of PFT10] + [extreme l2fr_ini_9→PFT9 leaf starvation]. This hypothesis addresses all three layers simultaneously in a cumulative design, starting with the highest-priority bottleneck. The derivative gain increases (pid_kd_10, pid_kd_9) add allocation stabilization that prevents PID oscillations from undermining the corrected l2fr and stoichiometry parameters — supported by Case #1391 evidence (pid_kd_10=0.43 achieving highest ensemble PFT10_froot=205 g/m²).

### Design Type

cumulative

---

## AI Reasoning and Analysis

Three-layer mechanistic failure chain identified in Cycle 3 diagnosis: (1) PRIMARY: mort_hf_sm_threshold_10=1e-08 at absolute lower bound means any non-zero soil moisture triggers hydraulic failure mortality in PFT10, causing 92% of all PFT10 deaths (mean rate 12.58 events). No biomass accumulation is possible when cohorts are continuously erased by hydraulic failure at ecologically unrealistic thresholds. (2) SECONDARY: Systemic P demand inflation from PFT7 (stoich_phos × high root biomass driving 54% of total 358,121 g/m²/yr demand) starves all PFTs of phosphorus via ECA competition, with PFT10 receiving only 2% of soil P supply (0.013 g/m²/yr vs demand 15.5 g/m²/yr). Reducing PFT7 leaf and fineroot P stoichiometry toward literature-supported lower bounds provides proportional P demand relief without disrupting currently-passing PFT7_leaf target. (3) TERTIARY: PFT9 allocation paradox from l2fr_ini_9=18.31 (upper bound) routes >95% of new carbon to fine roots, starving PFT9_leaf (Cycle 2 confirmed r=-0.257 negative correlation). Correcting l2fr_ini_9 restores balanced allocation once P relief allows leaf growth to proceed. The causal sequence: [extreme mort_hf_sm_threshold_10→92% PFT10 death] + [inflated PFT7 stoich_phos→ECA exclusion of PFT10] + [extreme l2fr_ini_9→PFT9 leaf starvation]. This hypothesis addresses all three layers simultaneously in a cumulative design, starting with the highest-priority bottleneck. The derivative gain increases (pid_kd_10, pid_kd_9) add allocation stabilization that prevents PID oscillations from undermining the corrected l2fr and stoichiometry parameters — supported by Case #1391 evidence (pid_kd_10=0.43 achieving highest ensemble PFT10_froot=205 g/m²).

---

## Parameters to Modify

### fates_mort_hf_sm_threshold
- **Current:** 1e-08
- **Proposed:** 5e-07
- **Rationale:** PRIORITY 1: mort_hf_sm_threshold_10=1e-08 is at the absolute lower bound of the sampling range [1e-08, 1.44e-06], causing hydraulic failure mortality at any soil moisture condition. This accounts for 92% of all PFT10 deaths (mean mortality rate 12.58). Increasing to 5e-07 (~35% of log-scale range, well within ensemble bounds) means hydraulic failure is only triggered under severe drought — ecologically appropriate for arctic graminoids which tolerate moderate water stress but not constant hydraulic failure. Default value is 1e-06; proposed 5e-07 is a conservative intermediate that prevents unrealistic continuous hydraulic failure while acknowledging arctic graminoids are less drought-tolerant than default temperate PFTs. Without this fix, all other parameter corrections are irrelevant — PFT10 cohorts cannot accumulate biomass when 92% die from hydraulic failure.

### fates_stoich_phos
- **Current:** 0.0018116108571428573
- **Proposed:** 0.0012
- **Rationale:** PRIORITY 2a: PFT7 leaf P stoichiometry reduction to relieve systemic ECA P competition. PFT7 drives 54% of total system P demand (192,556 g/m²/yr of 358,121 g/m²/yr total vs soil supply of 0.67 g/m²/yr). Current stoich_phos_leaf_7=0.00181 is in lower half of ensemble range [0.00103, 0.00285]. Reducing to 0.0012 (near lower bound but within range) reduces per-unit-leaf P requirement by ~34%, reducing PFT7's leaf P demand proportionally. This is a PFT-specific parameter — changing PFT7 leaf stoichiometry does not directly alter PFT9 or PFT10 stoichiometry. PFT7_leaf is currently near-passing (21.1 vs target 24.6 g C/m²) — stoichiometry reduction shifts less P to PFT7 leaves, potentially allowing more P to reach PFT9 and PFT10 via ECA. Risk: lower leaf P content may reduce photosynthetic capacity but this is partially offset by the reduced demand signal to the PID controller.

### fates_stoich_phos
- **Current:** 0.0010900005714285714
- **Proposed:** 0.00085
- **Rationale:** PRIORITY 2b: PFT7 fineroot P stoichiometry reduction. The fineroot component is the primary driver of PFT7 P demand given high root biomass investment — fineroot stoich × large root biomass pool × vmax at upper bounds creates the astronomically inflated P demand. Current stoich_phos_fineroot_7=0.00109 is near lower bound of range [0.000804, 0.00147]. Reducing to 0.00085 (within but below range lower bound — NOTE: 0.00085 is slightly below the ensemble lower bound of 0.000804. Adjusting to 0.000820 to remain within ensemble bounds) — actually setting to 0.000850 as it is within physical plausibility for arctic shrubs with low P tissue concentrations. This reduces per-unit-fineroot P requirement by ~22%. Combined with leaf reduction, total PFT7 P demand reduction is approximately 25-30%, potentially reducing total system P demand from 358,121 to ~250,000 g/m²/yr. Still extreme, but directionally correct.

### fates_allom_l2fr
- **Current:** 18.31149756
- **Proposed:** 5.0
- **Rationale:** PRIORITY 3: PFT9 leaf-to-fineroot ratio correction. l2fr_ini_9=18.31 is at the absolute upper bound of sampling range [0.01, 18.31], routing ~95% of new carbon to fine roots and starving PFT9_leaf. Cycle 2 confirmed negative correlation r=-0.257 between l2fr_ini_9 and PFT9_leaf — the strongest mechanistic signal observed for PFT9. Reducing to 5.0 (within range, ~27% of log-scale range from lower bound) redirects approximately 40-50% of new carbon to leaves. Caution: PFT9_fineroot is currently passing (223.8 vs target 187.4 g C/m²); reducing l2fr_ini_9 will reduce fine root investment. At l2fr_ini_9=5.0, estimated PFT9_froot reduction is ~50-60% (to ~90-110 g C/m²), which may push below tolerance (149.9 g C/m²). However, this is an acceptable risk given PFT9_leaf is severely failing (26.6 vs target 124.7 g C/m²) — the leaf failure is more severe than the potential froot over-correction. A value of 5.5-6.0 is more conservative but 5.0 provides stronger directional correction consistent with Case #3972 evidence (l2fr_ini_9≈5.24).

### fates_cnp_pid_kd
- **Current:** 0.01
- **Proposed:** 0.35
- **Rationale:** PRIORITY 4: PFT10 PID derivative gain stabilization. pid_kd_10=0.01 is at the lower bound of range [0.01, 0.5], removing stabilizing derivative action from PFT10 allocation dynamics. Case #1391, which achieves the highest PFT10_froot in the entire ensemble (205 g/m²), has pid_kd_10=0.43. Increasing from 0.01 to 0.35 adds damping that prevents allocation oscillations without changing the equilibrium allocation point. This is particularly important after mort_hf_sm_threshold correction — as PFT10 cohorts begin surviving, stable allocation dynamics are needed to build biomass progressively rather than oscillating between leaf-biased and root-biased states. The derivative gain change does not alter the equilibrium allocation direction, only the approach trajectory, making it a mechanistically safe improvement.

### fates_cnp_pid_kd
- **Current:** 0.01
- **Proposed:** 0.2
- **Rationale:** PRIORITY 5: PFT9 PID derivative gain stabilization. pid_kd_9=0.01 at lower bound removes derivative damping from PFT9 allocation. Without damping, the corrected l2fr_ini_9=5.0 may dynamically re-diverge toward root-biased allocation as the PID responds to nutrient limitation signals. Increasing to 0.20 provides moderate stabilization — more conservative than PFT10 (0.35) because PFT9 does not have the same catastrophic mortality bottleneck and its allocation dynamics are less urgently unstable. Value of 0.20 is within ensemble range [0.01, 0.5] and consistent with Cycle 2 recommendation (proposed 0.15, escalated slightly based on Case #1391 pattern).


---

## Expected Outcomes

- **leaf_pft7:** 22.0
- **froot_pft7:** 85.0
- **leaf_pft9:** 65.0
- **froot_pft9:** 105.0
- **leaf_pft10:** 25.0
- **froot_pft10:** 80.0
- **notes:** PFT10 biomass recovery is conditional on hydraulic mortality elimination (Priority 1). Expected PFT10_leaf improvement from ~1 to ~25 g C/m² (still below target 82.7 but order-of-magnitude improvement). PFT9_leaf expected to recover from ~26 to ~65 g C/m² once l2fr_ini_9 correction channels carbon to leaves AND P stoichiometry reduction partially relieves P starvation. PFT9_froot may decline from ~224 to ~105 g C/m² (below 20% tolerance of 149.9) — this is the primary tradeoff risk. PFT7_leaf expected to remain near-passing (~22 g C/m²); PFT7_froot may increase modestly via P relief effect but structural constraint from l2fr_ini_7=0.85 limits improvement to ~85 g C/m² (still below target 174 g C/m²). All estimates are conservative given the systemic P starvation remains extreme even after stoichiometry correction.

---

## Metadata

```json
{
  "iteration": 3,
  "diagnosis_count": 3,
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
  "iteration": 3,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-03-10T00:09:48.207757",
  "site": "Kougarok",
  "session_id": "20260309_232001",
  "experiment_count": 0,
  "skip_testing_count": 2,
  "diagnosis_count": 3,
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
