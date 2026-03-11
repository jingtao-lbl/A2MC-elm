# Skip-Testing Synthesis Summary

**Site:** Kougarok
**Phase:** 4 - Hypothesis (Synthesis)
**Round:** 2 | **Cycle:** 2 | **Iteration:** 1
**Date:** 2026-03-11 02:26:10
**Skip-testing cycles:** 5
**Synthesized experiments:** 1

---

## Screening Baseline

- **Best case (targets):** #322 (RMSRE ?, 3 targets met)
- **Lowest cost case:** #1386 (RMSRE ?, 0 targets met)


---

## Diagnosis Evolution (5 cycles)

| Iter | Confidence | # Failing | Key Causes |
|------|-----------|-----------|------------|
| 1 | 0.88 | 5 | PRIMARY: Complete ecosystem P starvation — total P demand (358,121 g/m²/yr) exceeds supply (0.67 g/m²/yr) by factor of ~535,000, indicating the parameter space does not allow biologically realistic P uptake rates. The vmax_p parameters are the direct control: vmax_p_10 is at its lower bound (5e-11) in Case #322 while the ecosystem is P-starved., SECONDARY: Parameter space too narrow for vmax_p — the current upper bound for vmax_p (5e-05 for PFT9, 5e-11 for PFT10 at lower bound) allows a 6-order-of-magnitude range but the best case still uses extreme values, confirming the feasible region likely lies outside or at the edges of the sampled space. The test_morris_bounds_impact was confirmed with 95% confidence., TERTIARY: PID controller-driven maladaptive allocation — in response to P starvation, the PID controller redirects carbon allocation heavily toward roots (L2FR = 0.34 for PFT7, root-biased allocation), starving leaves of carbon even when GPP is adequate. This creates a positive feedback: P-starved plants invest in roots → leaves decline → GPP falls → C starvation. (+2 more) |
| 2 | 0.88 | 5 | ROOT CAUSE 1: Catastrophic cross-PFT phosphorus starvation — total ecosystem P demand (358,121 g/m²/yr) exceeds total P uptake (0.67 g/m²/yr) by >500,000x, driven by l2fr_ini_9=18.3 creating biologically impossible root biomass that inflates calculated nutrient demand, ROOT CAUSE 2: vmax_p_10 at lower bound (5e-11) in Case #322, providing only 0.013 g P/m²/yr to PFT10 against a demand of 15.5 g/m²/yr — a 1,200x deficit even in the 'best' case, ROOT CAUSE 3: PFT7 competitive dominance in ECA nutrient competition (73.4% of total P uptake) due to high microb_bio_7=600 (upper bound) suppressing PFT9 and PFT10 via the Equilibrium Chemistry Approximation mechanism (+3 more) |
| 3 | 0.82 | 5 | ROOT CAUSE 1 [CONFIRMED]: vmax_p_10 at lower ensemble bound (5e-11) provides only 0.013 g P/m2/yr to PFT10 against demand of 15.5 g/m2/yr (1,200x deficit). Skip-testing PROVED zero valid PFT10 biomass cases exist anywhere in the 4890-case ensemble (0 cases with leaf10 > 0.1 g C/m2), confirming ensemble boundary collapse. The lower bound is too low AND the upper bound (5e-05) is still insufficient for arctic graminoid P uptake at Kougarok soil P levels., ROOT CAUSE 2 [CONFIRMED]: l2fr_ini_9 at upper bound (18.31) and l2fr_ini_10 at upper bound (9.88) create biologically impossible root-to-leaf ratios, inflating P demand for PFT9 from realistic ~10,000 g/m2/yr to 165,550 g/m2/yr (l2fr_corr_with_leaf9=-0.257, l2fr_reduction_beneficial=True confirmed by skip-testing)., ROOT CAUSE 3 [CONFIRMED]: ECA cross-PFT suppression — microb_bio_7=600 (upper bound) and vmax_nh4_7=0.00025 (upper bound) cause PFT7 to capture 73.4% of total P uptake, suppressing PFT9 and PFT10 (ECA suppression confirmed: vmax7/vmax10 ratio corr with pft10_leaf=-0.113). (+4 more) |
| 4 | 0.88 | 5 | ROOT CAUSE 1 [STRUCTURALLY CONFIRMED — 3 cycles]: Ensemble boundary collapse for vmax_p_10. The parameter range [5e-11, 5e-05] is insufficient for arctic graminoid P uptake — 0/4890 cases produce viable PFT10 biomass (>0.1 g C/m²). Even at ensemble ceiling, joint favorable cases show leaf10=0.002 g C/m². The mechanistic explanation: at Kougarok soil P concentrations, P uptake = vmax_p × fineroot_C / (km_p + [P]). With vmax_p_10 ceiling at 5e-05 and soil [P] ~0.05 mg/L, maximum PFT10 P uptake is ~0.013 g/m²/yr against biological demand of 15.5 g/m²/yr — a structural 1,200x supply gap that CANNOT be resolved within the current ensemble bounds., ROOT CAUSE 2 [CONFIRMED — 3 cycles]: l2fr_ini_9 at upper bound (18.31 in Case #322) creates biologically impossible root-to-leaf ratio for Betula nana, inflating PFT9 P demand from realistic ~10,000 g/m²/yr to 165,550 g/m²/yr. Correlation evidence: l2fr_corr_with_leaf9 = -0.257 (negative = reduction beneficial, 3-cycle support). This is a structural mismatch — arctic deciduous shrubs have observed L2FR of 1-4, not 18., ROOT CAUSE 3 [CONFIRMED — 3 cycles]: Cross-PFT ECA suppression. microb_bio_7=600 (upper bound in Case #322) + vmax_nh4_7=0.00025 (upper bound) causes PFT7 to capture 73.4% of total P uptake (0.49/0.67 g/m²/yr), leaving PFT9 with 24.6% (0.165 g/m²/yr) and PFT10 with only 2.0% (0.013 g/m²/yr). ECA suppression confirmed: vmax7/vmax10 ratio corr with PFT10 leaf = -0.113. (+3 more) |
| 5 | 0.92 | 5 | PRIMARY: vmax_p_10 ensemble ceiling constraint — the current upper bound (5e-05) is biologically insufficient for arctic graminoids. Case #1386 at 1.43e-05 achieves only partial PFT10 viability (leaf=37 gC/m²). Literature values for arctic graminoid P uptake kinetics are 1e-07 to 1e-04 gP/gC/s. Zero viable PFT10 cases (leaf>5) exist in 4890 simulations even at ensemble maximum., PRIMARY: vmax_ptase_10 phosphatase bypass mechanism — Case #1386 has vmax_ptase_10 at 4.28e-05 (428,571x higher than Case #322's 5e-10). High phosphatase capacity enables PFT10 to access organic P pools bypassing ECA inorganic P competition, the key mechanism enabling partial PFT10 viability., SECONDARY: ECA competition lock-in — PFT7 captures 73.4% of all P uptake due to high vmax_p_7 (at upper bound) and microb_bio_7=600 (upper bound). This leaves PFT10 (2.0% uptake share) chronically P-starved regardless of its own vmax_p settings within current bounds. (+3 more) |

---

## Hypothesis Evolution (5 cycles + synthesis)

| Iter | Name | # Params | Result |
|------|------|----------|--------|
| 1 | P-Uptake Kinetics Expansion: vmax_p R... | 6 | Not supported (1.00) |
| 2 | Coordinated P-Kinetics and Leaf-Root ... | 4 | Not supported (0.14) |
| 3 | P-Uptake Bottleneck: Direct vmax_p Ce... | 4 | Not supported (0.50) |
| 4 | Case #1386 Parameter Archaeology: Ide... | 6 | Not supported (0.90) |
| 5 | Case-1386-Anchored Multi-Parameter P-... | 7 | Not supported (0.20) |
| Synth | Case-1386-Anchored Multi-Parameter P-... | 7 | → HPC (0.65) |

---

## Evidence Ledger

### Active Parameters

| Parameter | Times Proposed | Times Supported | Status |
|-----------|---------------|-----------------|--------|
| fates_allom_l2fr | 8 | 0 | active |
| fates_cnp_vmax_p | 6 | 0 | active |
| fates_cnp_eca_km_p | 4 | 0 | active |
| fates_cnp_eca_decompmicc | 4 | 0 | active |
| fates_cnp_eca_vmax_ptase | 3 | 0 | active |

### Dropped Parameters

| Parameter | Times Proposed | Times Supported | Status |
|-----------|---------------|-----------------|--------|
| fates_cnp_phos_store_ratio | 1 | 0 | dropped |
| fates_mort_scalar_hydrfailure | 1 | 0 | dropped |



---

## Synthesized Experiment Designs

### Experiment 1: Case-1386-Anchored Multi-Parameter P-Rescue: Coordinated ECA Rebalancing with Realistic Step Changes

- **Confidence:** 0.65
- **Design:** cumulative

| Parameter | Current | Proposed | Rationale |
|-----------|---------|----------|-----------|
| fates_cnp_vmax_p | 5e-11 | 5e-09 | Case #322 has vmax_p_10 at ensemble lower bound (5e-11). ... |
| fates_cnp_eca_vmax_ptase | 5e-10 | 5e-08 | Case #322 has vmax_ptase_10 at ensemble lower bound (5e-1... |
| fates_cnp_eca_vmax_ptase | 5e-09 | 1e-07 | PFT9 vmax_ptase is at ensemble default (5e-09). Modest in... |
| fates_allom_l2fr | 18.31 | 5.24 | Case #322 has l2fr_ini_9 at upper bound (18.31), creating... |
| fates_cnp_eca_decompmicc | 600 | 402 | Case #322 has microb_bio_7 at upper bound (600), giving m... |
| fates_allom_l2fr | 9.88 | 5.5 | Case #322 has l2fr_ini_10 at upper bound (9.88). Reductio... |
| fates_cnp_eca_km_p | 0.064 | 0.02 | Reducing km_p_10 from 0.064 to 0.02 (3.2x reduction) incr... |

#### Cumulative Experiment Breakdown

Each experiment cumulatively adds one parameter change to isolate individual effects:

| Exp | # Params | Parameters Modified | Key Change |
|-----|----------|---------------------|------------|
| exp1 | 1 | fates_cnp_vmax_p | fates_cnp_vmax_p: 5e-11 → 5e-09 |
| exp2 | 2 | fates_cnp_vmax_p, **+fates_cnp_eca_vmax_ptase** | fates_cnp_eca_vmax_ptase: 5e-10 → 5e-08 |
| exp3 | 3 | fates_cnp_vmax_p, fates_cnp_eca_vmax_ptase, **+fates_cnp_eca_vmax_ptase** | fates_cnp_eca_vmax_ptase: 5e-09 → 1e-07 |
| exp4 | 4 | fates_cnp_vmax_p, fates_cnp_eca_vmax_ptase, fates_cnp_eca_vmax_ptase, **+fates_allom_l2fr** | fates_allom_l2fr: 18.31 → 5.24 |
| exp5 | 5 | fates_cnp_vmax_p, fates_cnp_eca_vmax_ptase, fates_cnp_eca_vmax_ptase, fates_allom_l2fr, **+fates_cnp_eca_decompmicc** | fates_cnp_eca_decompmicc: 600 → 402 |
| exp6 | 6 | fates_cnp_vmax_p, fates_cnp_eca_vmax_ptase, fates_cnp_eca_vmax_ptase, fates_allom_l2fr, fates_cnp_eca_decompmicc, **+fates_allom_l2fr** | fates_allom_l2fr: 9.88 → 5.5 |
| exp7 | 7 | fates_cnp_vmax_p, fates_cnp_eca_vmax_ptase, fates_cnp_eca_vmax_ptase, fates_allom_l2fr, fates_cnp_eca_decompmicc, fates_allom_l2fr, **+fates_cnp_eca_km_p** | fates_cnp_eca_km_p: 0.064 → 0.02 |




---

## Iteration Context

```json
{
  "calibration_round": 2,
  "iteration": 7,
  "phase": 4,
  "phase_name": "synthesis",
  "timestamp": "2026-03-11T02:26:10.255525",
  "site": "Kougarok",
  "session_id": "20260311_011134",
  "experiment_count": 2,
  "skip_testing_count": 0,
  "n_skip_testing_cycles": 5,
  "n_synthesized_experiments": 1,
  "n_evidence_ledger_params": 7
}
```
