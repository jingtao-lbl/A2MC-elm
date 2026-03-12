# Skip-Testing Synthesis Summary

**Site:** Kougarok
**Phase:** 4 - Hypothesis (Synthesis)
**Round:** 2 | **Cycle:** 0 | **Iteration:** 4
**Date:** 2026-03-11 21:29:38
**Skip-testing cycles:** 4
**Synthesized experiments:** 1

---

## Screening Baseline

- **Best case (targets):** #322 (RMSRE ?, 3 targets met)
- **Lowest cost case:** #1386 (RMSRE ?, 0 targets met)


---

## Diagnosis Evolution (4 cycles)

| Iter | Confidence | # Failing | Key Causes |
|------|-----------|-----------|------------|
| 1 | 0.88 | 5 | CATASTROPHIC P DEMAND EXPLOSION: Total P demand = 358,121 g/m²/yr vs. total supply = 0.86 g/m²/yr (ratio = 2.4×10⁻⁶ for PFT7). This is a mathematical artifact of the demand calculation (demand = fnrt_c × vmax_p) when fine root biomass is large. Even maximizing vmax_p to its upper bound (5×10⁻⁵ for PFT9) cannot close a 5-order-of-magnitude gap., PARAMETER SPACE EXHAUSTED FOR P UPTAKE: The test_morris_bounds_impact confirmed (confidence=0.95) that 9/9 key P-uptake parameters are at their bounds in the best-performing case. vmax_p_10 is at its lower bound (5×10⁻¹¹), vmax_p_9 at its upper bound (5×10⁻⁵), and the range still cannot satisfy targets. This is a parameter space design failure, not a value-tuning failure., L2FR OVER-ALLOCATION CARBON TRAP: PFT9's l2fr_ini_9 = 18.31 (at upper bound), which test_l2fr_carbon_limitation confirms reduces PFT9 leaf biomass by 63% in high-L2FR cases (confidence=0.60). The model is allocating excessive carbon to fine roots to pursue P, but the P is not accessible regardless, creating a futile carbon sink that collapses leaf biomass. (+2 more) |
| 2 | 0.87 | 5 | CONFIRMED PFT10 STRUCTURAL COLLAPSE VIA HYDRAULIC FAILURE: Mortality analysis reveals hydraulic failure dominates PFT10 mortality at 92% of all mortality. Key parameter in Case #322: vmax_p_10=5e-11 (at lower bound), leaf_slatop_10=0.00853 (at lower bound), mort_hf_sm_threshold_10=1e-8 (at lower bound). The graminoid is dying primarily of hydraulic stress, NOT carbon starvation — this is a fundamentally different mechanism than PFT9 failure. The hydraulic threshold being at its lower bound means even minimal soil moisture stress triggers mortality., CONFIRMED PFT9 C-STARVATION CASCADE FROM P LIMITATION: Carbon starvation accounts for 86% of PFT9 mortality. The causal chain: P demand (fnrt_c × vmax_p_9 = 165,550 g/m²/yr) >> P supply (0.86 g/m²/yr) → P uptake/demand ratio = 0.00 → PID controller maximizes root allocation → l2fr_ini_9=18.31 (at upper bound, 5× above the empirically identified collapse threshold of ~3.93) → excessive C diverted to roots → C starvation mortality. This is not a primary hydraulic problem for PFT9., CONFIRMED L2FR THRESHOLD VIOLATION: Ensemble analysis identifies the L2FR threshold for 50% leaf biomass drop at L2FR~3.93 for PFT9. Case #322 has l2fr_ini_9=18.31 (4.7× above threshold). Every single one of the 4890 cases has PFT9 leaf biomass far below target when L2FR is above this threshold. The current parameter range upper bound for l2fr_ini_9 (18.31) allows ecologically implausible configurations. (+3 more) |
| 3 | 0.88 | 5 | ROOT CAUSE 1 — L2FR BOUND VIOLATION (CONFIRMED, confidence=0.92): l2fr_ini_9=18.31 is 4.7× above the empirically confirmed collapse threshold of 3.93 (from test_vmax_l2fr_demand_interaction). l2fr_ini_10=9.88 is 3.3× above the PFT10 threshold of 2.99. 100% of ensemble cases for PFT10 have leaf < 10 gC/m² and froot < 20 gC/m² — confirmed structural failure from out-of-range L2FR bounds. The current parameter ranges [0.01, 18.31] for PFT9 and [1.115, 9.879] for PFT10 allow ecologically implausible configurations that guarantee failure., ROOT CAUSE 2 — P DEMAND EXPLOSION FROM vmax_p × L2FR INTERACTION (CONFIRMED, confidence=0.90): Total P demand = 358,121 g/m²/yr vs supply = 0.86 g/m²/yr. PFT7 alone demands 192,556 g P/m²/yr, PFT9 demands 165,550 g P/m²/yr. The mathematical relationship P_demand = fnrt_c × vmax_p creates an astronomically large demand when both fnrt_c (driven by L2FR) and vmax_p are large. Even setting vmax_p to its current maximum (5e-5) cannot bridge a 417,000:1 supply/demand gap. The ensemble shows vmax_p_9 at upper bound (5e-5) in Case #322 with ZERO improvement in P satisfaction., ROOT CAUSE 3 — PID CONTROLLER AMPLIFICATION TRAP (CONFIRMED, confidence=0.85): The PID controller (pid_kp_9=0.00357, pid_kp_10=0.00143 in Case #322) senses the P deficit and maximally redirects carbon to roots, which INCREASES fnrt_c, which INCREASES P demand, creating a positive feedback loop. This is not a tuning problem — it is a structural feedback that cannot be broken without constraining L2FR below the collapse threshold. (+3 more) |
| 4 | 0.88 | 5 | ROOT CAUSE 1 — GLOBAL PARAMETER SPACE COLLAPSE (CONFIRMED, confidence=0.95): ALL L2FR bins across ALL three PFTs show 100% biomass collapse fraction (from test_l2fr_collapse_thresholds Cycle 3). This is not a threshold issue — the ENTIRE current parameter space for PFT9 L2FR [0.01, 18.31] and PFT10 L2FR [1.115, 9.879] produces near-zero biomass. The empirical collapse thresholds (PFT9: ~1.27, PFT10: ~1.92 from Cycle 3 data) are LOWER than the minimum sampled values, meaning even the lowest ensemble cases exceed the biological feasibility limit. A Phase 0 redesign is mandatory., ROOT CAUSE 2 — P DEMAND EXPLOSION FROM fnrt_c × vmax_p INTERACTION (CONFIRMED, confidence=0.90): P_demand = 358,121 g/m²/yr vs supply = 0.86 g/m²/yr (417,000:1 ratio). PFT7 alone demands 192,555 g P/m²/yr, PFT9 demands 165,550 g P/m²/yr. The mathematical relationship P_demand = fnrt_c × vmax_p with upper bound vmax_p_9=5e-5 and large fnrt_c (driven by high L2FR) makes satisfying targets mathematically impossible within current bounds. This is confirmed by the edge analysis showing vmax_p_9 at upper bound (5e-5) in Case #322 with PFT9_leaf still only 26.6 gC/m²., ROOT CAUSE 3 — PID CONTROLLER AMPLIFICATION TRAP (CONFIRMED, confidence=0.85): The PID controller (pid_kp_9=0.00357, pid_kp_10=0.00143 in Case #322) detects the massive P deficit and maximally redirects carbon to roots, which increases fnrt_c, which increases P demand, creating a runaway positive feedback. pid_kd_9 and pid_kd_10 are both at their lower bounds (0.01) in Case #322, meaning the derivative term (which would dampen the oscillation) is minimized, worsening the feedback. (+3 more) |

---

## Hypothesis Evolution (4 cycles + synthesis)

| Iter | Name | # Params | Result |
|------|------|----------|--------|
| 1 | P-Demand Explosion Quantification via... | 4 | Not supported (0.70) |
| 2 | PFT10_Hydraulic_Mortality_Threshold_R... | 4 | Not supported (0.40) |
| 3 | L2FR Collapse Threshold Verification:... | 0 | Not supported (0.29) |
| 4 | Phase 0 Redesign: L2FR-vmax_p Joint C... | 10 | Not supported (0.00) |
| Synth | Phase 0 Redesign: L2FR-vmax_p Joint C... | 10 | → HPC (0.88) |

---

## Evidence Ledger

### Active Parameters

| Parameter | Times Proposed | Times Supported | Status |
|-----------|---------------|-----------------|--------|
| fates_cnp_vmax_p | 6 | 0 | active |
| fates_allom_l2fr | 6 | 0 | active |
| fates_cnp_pid_kd | 2 | 0 | active |
| fates_cnp_phos_store_ratio | 1 | 0 | active |
| fates_leaf_slatop | 1 | 0 | active |

### Dropped Parameters

| Parameter | Times Proposed | Times Supported | Status |
|-----------|---------------|-----------------|--------|
| fates_mort_hf_sm_threshold | 1 | 0 | dropped |
| fates_mort_scalar_hydrfailure | 1 | 0 | dropped |



---

## Synthesized Experiment Designs

### Experiment 1: Phase 0 Redesign: L2FR-vmax_p Joint Constraint Verification via Ensemble Feasibility Analysis

- **Confidence:** 0.88
- **Design:** cumulative

| Parameter | Current | Proposed | Rationale |
|-----------|---------|----------|-----------|
| fates_allom_l2fr | 18.31 | 1.0 | PFT9 observed root:leaf ratio = 187.35/124.7 = 1.50, impl... |
| fates_allom_l2fr | 9.879 | 0.22 | PFT10 observed root:leaf ratio = 382.05/82.65 = 4.62, imp... |
| fates_cnp_vmax_p | 5e-11 | 1.43e-05 | vmax_p_10 at absolute lower bound (5e-11) in Case #322 — ... |
| fates_cnp_vmax_p | 2.86e-05 | 5e-08 | PFT7 demands 192,555 g P/m²/yr due to high vmax_p × large... |
| fates_cnp_vmax_p | 5e-05 | 5e-08 | vmax_p_9 at upper bound (5e-5) in Case #322 — PFT9 demand... |
| fates_cnp_pid_kd | 0.01 | 0.2 | pid_kd_9 at lower bound (0.01) in Case #322 — derivative ... |
| fates_cnp_pid_kd | 0.01 | 0.2 | pid_kd_10 at lower bound (0.01) in Case #322. Same dampin... |
| fates_cnp_phos_store_ratio | 1.0 | 3.0 | phos_store_ratio_9=1.0 at lower bound in Case #322. FATES... |
| fates_leaf_slatop | 0.0172 | 0.012 | leaf_slatop_7 at upper bound (0.0172) in Case #322 produc... |
| fates_allom_l2fr | 0.85 | 1.5 | PFT7 observed root:leaf ratio = 174.2/24.6 = 7.08, sugges... |

#### Cumulative Experiment Breakdown

Each experiment cumulatively adds one parameter change to isolate individual effects:

| Exp | # Params | Parameters Modified | Key Change |
|-----|----------|---------------------|------------|
| exp1 | 1 | fates_allom_l2fr | fates_allom_l2fr: 18.31 → 1.0 |
| exp2 | 2 | fates_allom_l2fr, **+fates_allom_l2fr** | fates_allom_l2fr: 9.879 → 0.22 |
| exp3 | 3 | fates_allom_l2fr, fates_allom_l2fr, **+fates_cnp_vmax_p** | fates_cnp_vmax_p: 5e-11 → 1.43e-05 |
| exp4 | 4 | fates_allom_l2fr, fates_allom_l2fr, fates_cnp_vmax_p, **+fates_cnp_vmax_p** | fates_cnp_vmax_p: 2.86e-05 → 5e-08 |
| exp5 | 5 | fates_allom_l2fr, fates_allom_l2fr, fates_cnp_vmax_p, fates_cnp_vmax_p, **+fates_cnp_vmax_p** | fates_cnp_vmax_p: 5e-05 → 5e-08 |
| exp6 | 6 | fates_allom_l2fr, fates_allom_l2fr, fates_cnp_vmax_p, fates_cnp_vmax_p, fates_cnp_vmax_p, **+fates_cnp_pid_kd** | fates_cnp_pid_kd: 0.01 → 0.2 |
| exp7 | 7 | fates_allom_l2fr, fates_allom_l2fr, fates_cnp_vmax_p, fates_cnp_vmax_p, fates_cnp_vmax_p, fates_cnp_pid_kd, **+fates_cnp_pid_kd** | fates_cnp_pid_kd: 0.01 → 0.2 |
| exp8 | 8 | fates_allom_l2fr, fates_allom_l2fr, fates_cnp_vmax_p, fates_cnp_vmax_p, fates_cnp_vmax_p, fates_cnp_pid_kd, fates_cnp_pid_kd, **+fates_cnp_phos_store_ratio** | fates_cnp_phos_store_ratio: 1.0 → 3.0 |
| exp9 | 9 | fates_allom_l2fr, fates_allom_l2fr, fates_cnp_vmax_p, fates_cnp_vmax_p, fates_cnp_vmax_p, fates_cnp_pid_kd, fates_cnp_pid_kd, fates_cnp_phos_store_ratio, **+fates_leaf_slatop** | fates_leaf_slatop: 0.0172 → 0.012 |
| exp10 | 10 | fates_allom_l2fr, fates_allom_l2fr, fates_cnp_vmax_p, fates_cnp_vmax_p, fates_cnp_vmax_p, fates_cnp_pid_kd, fates_cnp_pid_kd, fates_cnp_phos_store_ratio, fates_leaf_slatop, **+fates_allom_l2fr** | fates_allom_l2fr: 0.85 → 1.5 |




---

## Iteration Context

```json
{
  "calibration_round": 2,
  "iteration": 4,
  "phase": 4,
  "phase_name": "synthesis",
  "timestamp": "2026-03-11T21:29:38.631272",
  "site": "Kougarok",
  "session_id": "20260311_203934",
  "experiment_count": 0,
  "skip_testing_count": 3,
  "n_skip_testing_cycles": 4,
  "n_synthesized_experiments": 1,
  "n_evidence_ledger_params": 7
}
```
