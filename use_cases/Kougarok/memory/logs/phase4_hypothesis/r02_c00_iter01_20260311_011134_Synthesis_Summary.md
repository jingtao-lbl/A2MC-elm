# Skip-Testing Synthesis Summary

**Site:** Kougarok
**Phase:** 4 - Hypothesis (Synthesis)
**Round:** 2 | **Cycle:** 0 | **Iteration:** 1
**Date:** 2026-03-11 01:35:16
**Skip-testing cycles:** 1
**Synthesized experiments:** 1

---

## Screening Baseline

- **Best case (targets):** #322 (RMSRE ?, 3 targets met)
- **Lowest cost case:** #1386 (RMSRE ?, 0 targets met)


---

## Diagnosis Evolution (1 cycles)

| Iter | Confidence | # Failing | Key Causes |
|------|-----------|-----------|------------|
| 1 | 0.88 | 5 | PRIMARY: Complete ecosystem P starvation — total P demand (358,121 g/m²/yr) exceeds supply (0.67 g/m²/yr) by factor of ~535,000, indicating the parameter space does not allow biologically realistic P uptake rates. The vmax_p parameters are the direct control: vmax_p_10 is at its lower bound (5e-11) in Case #322 while the ecosystem is P-starved., SECONDARY: Parameter space too narrow for vmax_p — the current upper bound for vmax_p (5e-05 for PFT9, 5e-11 for PFT10 at lower bound) allows a 6-order-of-magnitude range but the best case still uses extreme values, confirming the feasible region likely lies outside or at the edges of the sampled space. The test_morris_bounds_impact was confirmed with 95% confidence., TERTIARY: PID controller-driven maladaptive allocation — in response to P starvation, the PID controller redirects carbon allocation heavily toward roots (L2FR = 0.34 for PFT7, root-biased allocation), starving leaves of carbon even when GPP is adequate. This creates a positive feedback: P-starved plants invest in roots → leaves decline → GPP falls → C starvation. (+2 more) |

---

## Hypothesis Evolution (1 cycles + synthesis)

| Iter | Name | # Params | Result |
|------|------|----------|--------|
| 1 | P-Uptake Kinetics Expansion: vmax_p R... | 6 | Not supported (1.00) |
| Synth | P-Uptake Kinetics Expansion: vmax_p R... | 6 | → HPC (0.82) |

---

## Evidence Ledger

### Active Parameters

| Parameter | Times Proposed | Times Supported | Status |
|-----------|---------------|-----------------|--------|
| fates_cnp_vmax_p | 3 | 0 | active |
| fates_allom_l2fr | 1 | 0 | active |
| fates_cnp_eca_km_p | 1 | 0 | active |
| fates_cnp_phos_store_ratio | 1 | 0 | active |



---

## Synthesized Experiment Designs

### Experiment 1: P-Uptake Kinetics Expansion: vmax_p Range Ceiling Hypothesis

- **Confidence:** 0.82
- **Design:** cumulative

| Parameter | Current | Proposed | Rationale |
|-----------|---------|----------|-----------|
| fates_cnp_vmax_p | 5e-11 | RANGE EXPANSION REQUIRED: new bounds [5e-09, 5e-03], center 1e-06 | Current best case #322 has vmax_p_10 at its LOWER bound (... |
| fates_cnp_vmax_p | 5e-05 | RANGE EXPANSION REQUIRED: new bounds [5e-07, 5e-03], coordinated with l2fr_ini_9 reduction | PFT9 vmax_p is at its UPPER bound (5e-05) in Case #322 ye... |
| fates_cnp_vmax_p | 2.86e-05 | RANGE EXPANSION REQUIRED: new upper bound 5e-03, with caution on ECA competition | PFT7 vmax_p near upper bound (2.86e-05 vs max 2.86e-05) y... |
| fates_allom_l2fr | 18.31 | RANGE CONTRACTION: new bounds [1.0, 8.0], this is the root-demand inflation driver | l2fr_ini_9 = 18.3 (upper bound, Case #322) creates PFT9 r... |
| fates_cnp_eca_km_p | 0.064 | RANGE SHIFT LOWER: new bounds [0.005, 0.08] — arctic mycorrhizal adaptation | km_p_10 = 0.064 in Case #322. At Arctic soil P concentrat... |
| fates_cnp_phos_store_ratio | 1.0 | RANGE SHIFT: new bounds [2.0, 8.0] — arctic shrub P storage capacity | phos_store_ratio_9 = 1.0 (lower bound) in Case #322. Mini... |

#### Cumulative Experiment Breakdown

Each experiment cumulatively adds one parameter change to isolate individual effects:

| Exp | # Params | Parameters Modified | Key Change |
|-----|----------|---------------------|------------|
| exp1 | 1 | fates_cnp_vmax_p | fates_cnp_vmax_p: 5e-11 → RANGE EXPANSION REQUIRED: new bounds [5e-09, 5e-03], center 1e-06 |
| exp2 | 2 | fates_cnp_vmax_p, **+fates_cnp_vmax_p** | fates_cnp_vmax_p: 5e-05 → RANGE EXPANSION REQUIRED: new bounds [5e-07, 5e-03], coordinated with l2fr_ini_9 reduction |
| exp3 | 3 | fates_cnp_vmax_p, fates_cnp_vmax_p, **+fates_cnp_vmax_p** | fates_cnp_vmax_p: 2.86e-05 → RANGE EXPANSION REQUIRED: new upper bound 5e-03, with caution on ECA competition |
| exp4 | 4 | fates_cnp_vmax_p, fates_cnp_vmax_p, fates_cnp_vmax_p, **+fates_allom_l2fr** | fates_allom_l2fr: 18.31 → RANGE CONTRACTION: new bounds [1.0, 8.0], this is the root-demand inflation driver |
| exp5 | 5 | fates_cnp_vmax_p, fates_cnp_vmax_p, fates_cnp_vmax_p, fates_allom_l2fr, **+fates_cnp_eca_km_p** | fates_cnp_eca_km_p: 0.064 → RANGE SHIFT LOWER: new bounds [0.005, 0.08] — arctic mycorrhizal adaptation |
| exp6 | 6 | fates_cnp_vmax_p, fates_cnp_vmax_p, fates_cnp_vmax_p, fates_allom_l2fr, fates_cnp_eca_km_p, **+fates_cnp_phos_store_ratio** | fates_cnp_phos_store_ratio: 1.0 → RANGE SHIFT: new bounds [2.0, 8.0] — arctic shrub P storage capacity |




---

## Iteration Context

```json
{
  "calibration_round": 2,
  "iteration": 1,
  "phase": 4,
  "phase_name": "synthesis",
  "timestamp": "2026-03-11T01:35:16.444302",
  "site": "Kougarok",
  "session_id": "20260311_011134",
  "experiment_count": 0,
  "skip_testing_count": 0,
  "n_skip_testing_cycles": 1,
  "n_synthesized_experiments": 1,
  "n_evidence_ledger_params": 4
}
```
