# Skip-Testing Synthesis Summary

**Site:** Kougarok
**Phase:** 4 - Hypothesis (Synthesis)
**Round:** 4 | **Cycle:** 0 | **Iteration:** 10
**Date:** 2026-04-14 11:11:18
**Skip-testing cycles:** 10
**Synthesized experiments:** 1

---

## Screening Baseline

- **Best case (targets):** #86 (RMSRE ?, 2 targets met)
- **Lowest cost case:** #86 (RMSRE ?, 2 targets met)


---

## Diagnosis Evolution (10 cycles)

| Iter | Confidence | # Failing | Key Causes |
|------|-----------|-----------|------------|
| 1 | 0.85 | 2 | P STARVATION; Light competition; Excessive turnover; Root distribution |
| 2 | 0.85 | 2 | P STARVATION; Light competition; Excessive turnover; Root distribution |
| 3 | 0.85 | 2 | P STARVATION; Light competition; Excessive turnover; Root distribution |
| 4 | 0.85 | 2 | P STARVATION; Light competition; Excessive turnover; Root distribution |
| 5 | 0.85 | 2 | P STARVATION; Light competition; Excessive turnover; Root distribution |
| 6 | 0.85 | 2 | P STARVATION; Light competition; Excessive turnover; Root distribution |
| 7 | 0.85 | 2 | P STARVATION; Light competition; Excessive turnover; Root distribution |
| 8 | 0.85 | 2 | P STARVATION; Light competition; Excessive turnover; Root distribution |
| 9 | 0.85 | 2 | P STARVATION; Light competition; Excessive turnover; Root distribution |
| 10 | 0.85 | 2 | P STARVATION; Light competition; Excessive turnover; Root distribution |

---

## Hypothesis Evolution (10 cycles + synthesis)

| Iter | Name | # Params | Result |
|------|------|----------|--------|
| 1 | PFT10_Triple_Bottleneck_Sequential_Fi... | 4 | Not supported (0.10) |
| 2 | PFT10_Fineroot_Biomass_Triple_Bottlen... | 4 | Not supported (0.10) |
| 3 | PFT10_TripleBottleneck_TurnoverRootPr... | 4 | Not supported (0.10) |
| 4 | PFT10_Triple_Bottleneck_Sequential_Fi... | 5 | Not supported (0.31) |
| 5 | PFT10_TripleBottleneck_TurnoverRootPr... | 4 | Not supported (0.00) |
| 6 | PFT10 Fine Root Longevity and Depth P... | 3 | Not supported (0.66) |
| 7 | PFT10_TripleBottleneck_TurnoverRootPr... | 3 | Not supported (0.15) |
| 8 | PFT10_TripleBottleneck_TurnoverRootPr... | 5 | Not supported (0.74) |
| 9 | PFT10 Triple Bottleneck: Fine Root Lo... | 9 | Not supported (0.00) |
| 10 | PFT10_TripleBottleneck_FineRoot_Bioma... | 3 | Not supported (0.10) |
| Synth | PFT10 Triple Bottleneck: Fine Root Lo... | 9 | → HPC (0.72) |

---

## Evidence Ledger

### Active Parameters

| Parameter | Times Proposed | Times Supported | Status |
|-----------|---------------|-----------------|--------|
| fates_turnover_fnrt | 10 | 0 | active |
| fates_allom_fnrt_prof_b | 10 | 0 | active |
| fates_allom_l2fr | 2 | 0 | active |

### Dropped Parameters

| Parameter | Times Proposed | Times Supported | Status |
|-----------|---------------|-----------------|--------|
| fates_allom_fnrt_prof_a | 9 | 0 | dropped |
| fates_stoich_phos | 4 | 0 | dropped |
| fates_cnp_vmax_p | 3 | 0 | dropped |
| fates_turnover_leaf | 2 | 0 | dropped |
| fates_cnp_turnover_phos_retrans | 2 | 0 | dropped |
| fates_cnp_eca_km_ptase | 1 | 0 | dropped |
| fates_cnp_eca_alpha_ptase | 1 | 0 | dropped |



---

## Synthesized Experiment Designs

### Experiment 1: PFT10 Triple Bottleneck: Fine Root Longevity × Root Distribution × P Starvation Sequenced Fix

- **Confidence:** 0.72
- **Design:** cumulative

| Parameter | PFT | Current | Proposed | Rationale |
|-----------|-----|---------|----------|-----------|
| fates_stoich_phos | #10 | 0.000920964 | 0.00065 | Reduce leaf P stoichiometric demand for PFT#10. Current v... |
| fates_stoich_phos | #10 | 0.0010996144285714286 | 0.00078 | Reduce fineroot P stoichiometric demand for PFT#10. Curre... |
| fates_cnp_eca_km_ptase | #10 | 1.3571428571428572 | 0.5 | Reduce Michaelis-Menten constant for phosphatase activity... |
| fates_cnp_eca_alpha_ptase | #10 | 0.95 | 0.95 | HOLD: alpha_ptase_10 is already at Morris upper bound (0.... |
| fates_turnover_fnrt | #10 | 3.071428571428571 | 4.5 | Increase fine root longevity for PFT#10 from 3.07 yr to 4... |
| fates_allom_fnrt_prof_b | #10 | 3.26 | 7.5 | Increase fnrt_prof_b_10 from 3.26 (Morris lower bound) to... |
| fates_allom_fnrt_prof_a | #10 | 12.332857142857142 | 9.0 | Decrease fnrt_prof_a_10 from 12.3 toward lower Morris bou... |
| fates_cnp_turnover_phos_retrans | #10 | 0.8714285714285714 | 0.9 | Slightly increase P retranslocation from leaves for PFT#1... |
| fates_cnp_turnover_phos_retrans | #10 | 0.8714285714285714 | 0.9 | Same as leaf: increase P retranslocation from fineroots t... |

#### Cumulative Experiment Breakdown

Each experiment cumulatively adds one parameter change to isolate individual effects:

| Exp | # Params | Parameters Modified | Key Change |
|-----|----------|---------------------|------------|
| exp1 | 1 | fates_stoich_phos(PFT#10) | fates_stoich_phos(PFT#10): 0.000920964 → 0.00065 |
| exp2 | 2 | fates_stoich_phos(PFT#10), **+fates_stoich_phos(PFT#10)** | fates_stoich_phos(PFT#10): 0.0010996144285714286 → 0.00078 |
| exp3 | 3 | fates_stoich_phos(PFT#10), fates_stoich_phos(PFT#10), **+fates_cnp_eca_km_ptase(PFT#10)** | fates_cnp_eca_km_ptase(PFT#10): 1.3571428571428572 → 0.5 |
| exp4 | 4 | fates_stoich_phos(PFT#10), fates_stoich_phos(PFT#10), fates_cnp_eca_km_ptase(PFT#10), **+fates_cnp_eca_alpha_ptase(PFT#10)** | fates_cnp_eca_alpha_ptase(PFT#10): 0.95 → 0.95 |
| exp5 | 5 | fates_stoich_phos(PFT#10), fates_stoich_phos(PFT#10), fates_cnp_eca_km_ptase(PFT#10), fates_cnp_eca_alpha_ptase(PFT#10), **+fates_turnover_fnrt(PFT#10)** | fates_turnover_fnrt(PFT#10): 3.071428571428571 → 4.5 |
| exp6 | 6 | fates_stoich_phos(PFT#10), fates_stoich_phos(PFT#10), fates_cnp_eca_km_ptase(PFT#10), fates_cnp_eca_alpha_ptase(PFT#10), fates_turnover_fnrt(PFT#10), **+fates_allom_fnrt_prof_b(PFT#10)** | fates_allom_fnrt_prof_b(PFT#10): 3.26 → 7.5 |
| exp7 | 7 | fates_stoich_phos(PFT#10), fates_stoich_phos(PFT#10), fates_cnp_eca_km_ptase(PFT#10), fates_cnp_eca_alpha_ptase(PFT#10), fates_turnover_fnrt(PFT#10), fates_allom_fnrt_prof_b(PFT#10), **+fates_allom_fnrt_prof_a(PFT#10)** | fates_allom_fnrt_prof_a(PFT#10): 12.332857142857142 → 9.0 |
| exp8 | 8 | fates_stoich_phos(PFT#10), fates_stoich_phos(PFT#10), fates_cnp_eca_km_ptase(PFT#10), fates_cnp_eca_alpha_ptase(PFT#10), fates_turnover_fnrt(PFT#10), fates_allom_fnrt_prof_b(PFT#10), fates_allom_fnrt_prof_a(PFT#10), **+fates_cnp_turnover_phos_retrans(PFT#10)** | fates_cnp_turnover_phos_retrans(PFT#10): 0.8714285714285714 → 0.9 |
| exp9 | 9 | fates_stoich_phos(PFT#10), fates_stoich_phos(PFT#10), fates_cnp_eca_km_ptase(PFT#10), fates_cnp_eca_alpha_ptase(PFT#10), fates_turnover_fnrt(PFT#10), fates_allom_fnrt_prof_b(PFT#10), fates_allom_fnrt_prof_a(PFT#10), fates_cnp_turnover_phos_retrans(PFT#10), **+fates_cnp_turnover_phos_retrans(PFT#10)** | fates_cnp_turnover_phos_retrans(PFT#10): 0.8714285714285714 → 0.9 |




---

## Iteration Context

```json
{
  "calibration_round": 4,
  "iteration": 10,
  "phase": 4,
  "phase_name": "synthesis",
  "timestamp": "2026-04-14T11:11:18.112857",
  "site": "Kougarok",
  "session_id": "20260413_173425",
  "experiment_count": 0,
  "skip_testing_count": 9,
  "n_skip_testing_cycles": 10,
  "n_synthesized_experiments": 1,
  "n_evidence_ledger_params": 10
}
```
