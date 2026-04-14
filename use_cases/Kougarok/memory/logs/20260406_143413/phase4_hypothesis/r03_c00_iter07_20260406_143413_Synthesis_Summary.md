# Skip-Testing Synthesis Summary

**Site:** Kougarok
**Phase:** 4 - Hypothesis (Synthesis)
**Round:** 3 | **Cycle:** 0 | **Iteration:** 7
**Date:** 2026-04-07 12:35:16
**Skip-testing cycles:** 7
**Synthesized experiments:** 1

---

## Screening Baseline

- **Best case (targets):** #86 (RMSRE ?, 3 targets met)
- **Lowest cost case:** #2939 (RMSRE ?, 2 targets met)


---

## Diagnosis Evolution (7 cycles)

| Iter | Confidence | # Failing | Key Causes |
|------|-----------|-----------|------------|
| 1 | 0.87 | 6 | CONFIRMED; CONFIRMED; CONFIRMED; CONFIRMED; LIKELY; LIKELY |
| 2 | 0.88 | 6 | CONFIRMED (Cycle 1+2); CONFIRMED; NEW (Cycle 2); CONFIRMED; LIKELY; LIKELY; LIKELY; CONFIRMED |
| 3 | 0.82 | 6 | CONFIRMED (Cycles 1-3); CONFIRMED; NEW (Cycle 3, Case #1385 fingerprint); CONFIRMED; CONFIRMED; LIKELY; LIKELY |
| 4 | 0.83 | 6 | CONFIRMED (Cycles 1-4); CONFIRMED (Cycle 3 NEW); CONFIRMED (Cycles 2-3); CONFIRMED (Cycles 1-3); NEW (Cycle 4); CONFIRMED (Case #86); CONFIRMED (Case #86 vs Case #4670 comparison) |
| 5 | 0.82 | 6 | CONFIRMED (Cycles 1-4, PRIMARY); CONFIRMED (Cycles 2-4); CONFIRMED (Cycle 4); CONFIRMED (Cycles 3-4); NOT CONFIRMED (Cycle 4); CONFIRMED (Cycles 2-4); INFERRED (Case #1385 reference) |
| 6 | 0.82 | 6 | CONFIRMED (Cycles 1-5, PRIMARY STRUCTURAL); CONFIRMED (Cycles 3-5); CONFIRMED (Cycles 4-5); CONFIRMED (Cycles 3-5); NOT CONFIRMED but UNTESTED; CONFIRMED (Cycles 2-5) |
| 7 | 0.82 | 6 | CONFIRMED PRIMARY STRUCTURAL (Cycles 1-7); CONFIRMED (Cycles 3-5); CONFIRMED (Cycles 4-5); CONFIRMED (Cycles 3-5); NEWLY CRITICAL (Cycle 7, was Cycle 6 failed test); CONFIRMED (Cycles 2-5) |

---

## Hypothesis Evolution (7 cycles + synthesis)

| Iter | Name | # Params | Result |
|------|------|----------|--------|
| 1 | P-Starvation Triage: PFT10 Nutrient U... | 6 | Not supported (0.00) |
| 2 | PFT10-P-Access-Enabler: Stoichiometri... | 7 | Not supported (0.70) |
| 3 | Cross-PFT P Competition Rescue via Du... | 9 | Not supported (0.75) |
| 4 | nfix1_9 Compensation + Dual Cross-PFT... | 8 | Not supported (0.80) |
| 5 | Balanced Cross-PFT P Redistribution v... | 10 | Not supported (0.75) |
| 6 | Cycle6_N-Stoichiometry_P-Demand_Combi... | 12 | Not supported (0.00) |
| 7 | Cycle 7 Synthesis: Simultaneous Multi... | 9 | Not supported (0.75) |
| Synth | Cycle6_N-Stoichiometry_P-Demand_Combi... | 12 | → HPC (0.62) |

---

## Evidence Ledger

### Active Parameters

| Parameter | Times Proposed | Times Supported | Status |
|-----------|---------------|-----------------|--------|
| fates_stoich_phos | 13 | 0 | active |
| fates_cnp_eca_decompmicc | 11 | 0 | active |
| fates_cnp_phos_store_ratio | 8 | 0 | active |
| fates_turnover_leaf | 5 | 0 | active |
| fates_cnp_nitr_store_ratio | 5 | 0 | active |
| fates_cnp_nfix1 | 4 | 0 | active |
| fates_stoich_nitr | 4 | 0 | active |

### Dropped Parameters

| Parameter | Times Proposed | Times Supported | Status |
|-----------|---------------|-----------------|--------|
| fates_cnp_turnover_phos_retrans | 10 | 0 | dropped |
| fates_cnp_vmax_p | 1 | 0 | dropped |



---

## Synthesized Experiment Designs

### Experiment 1: Cycle6_N-Stoichiometry_P-Demand_Combined_Demand_Reduction_for_PFT10_with_PFT9_Compensation

- **Confidence:** 0.62
- **Design:** cumulative

| Parameter | PFT | Current | Proposed | Rationale |
|-----------|-----|---------|----------|-----------|
| fates_stoich_phos | #9 | 0.00428 | 0.0021 | Confirmed cross-PFT P demand lever (Cycles 3-5): reducing... |
| fates_cnp_eca_decompmicc | #9 | 468.571 | 150.0 | Confirmed strongest single correlation with PFT10 leaf re... |
| fates_cnp_nfix1 | #9 | 0.5714 | 0.9 | Morris rank #2 for PFT9 abg biomass (μ*=0.282), confirmed... |
| fates_stoich_nitr | #10 | 0.015246 | 0.0128 | NEW CYCLE 6 — Morris rank #2 for PFT10 fineroot (μ*=0.040... |
| fates_stoich_nitr | #10 | 0.020071 | 0.01663 | Morris rank #5 for PFT10 abg biomass (μ*=0.029). Reducing... |
| fates_cnp_phos_store_ratio | #10 | 5.0 | 1.5 | Morris rank #3 for PFT10 fineroot (μ*=0.041). Case #86 ha... |
| fates_cnp_nitr_store_ratio | #10 | 5.0 | 1.5 | Morris rank #6 for PFT10 fineroot (μ*=0.037, nitr_store_r... |
| fates_turnover_leaf | #7 | 2.0 | 1.5 | Morris rank #2 for PFT7 leaf (μ*=0.060) and rank #2 for P... |
| fates_cnp_phos_store_ratio | #7 | 3.2857 | 1.5 | Morris rank #3 for PFT7 abg biomass (μ*=0.262) and rank #... |
| fates_cnp_turnover_phos_retrans | #7 | 0.6 | 0.78 | Category B parameter. Case #86: phos_retrans_7=0.60 (at L... |
| fates_cnp_turnover_phos_retrans | #7 | 0.6 | 0.78 | Category B parameter (same value as organ=1). Retransloca... |
| fates_stoich_phos | #9 | 0.002069 | 0.0009 | Case #86 has stoich_phos_fineroot_9 at UPPER Morris bound... |

#### Cumulative Experiment Breakdown

Each experiment cumulatively adds one parameter change to isolate individual effects:

| Exp | # Params | Parameters Modified | Key Change |
|-----|----------|---------------------|------------|
| exp1 | 1 | fates_stoich_phos(PFT#9) | fates_stoich_phos(PFT#9): 0.00428 → 0.0021 |
| exp2 | 2 | fates_stoich_phos(PFT#9), **+fates_cnp_eca_decompmicc(PFT#9)** | fates_cnp_eca_decompmicc(PFT#9): 468.571 → 150.0 |
| exp3 | 3 | fates_stoich_phos(PFT#9), fates_cnp_eca_decompmicc(PFT#9), **+fates_cnp_nfix1(PFT#9)** | fates_cnp_nfix1(PFT#9): 0.5714 → 0.9 |
| exp4 | 4 | fates_stoich_phos(PFT#9), fates_cnp_eca_decompmicc(PFT#9), fates_cnp_nfix1(PFT#9), **+fates_stoich_nitr(PFT#10)** | fates_stoich_nitr(PFT#10): 0.015246 → 0.0128 |
| exp5 | 5 | fates_stoich_phos(PFT#9), fates_cnp_eca_decompmicc(PFT#9), fates_cnp_nfix1(PFT#9), fates_stoich_nitr(PFT#10), **+fates_stoich_nitr(PFT#10)** | fates_stoich_nitr(PFT#10): 0.020071 → 0.01663 |
| exp6 | 6 | fates_stoich_phos(PFT#9), fates_cnp_eca_decompmicc(PFT#9), fates_cnp_nfix1(PFT#9), fates_stoich_nitr(PFT#10), fates_stoich_nitr(PFT#10), **+fates_cnp_phos_store_ratio(PFT#10)** | fates_cnp_phos_store_ratio(PFT#10): 5.0 → 1.5 |
| exp7 | 7 | fates_stoich_phos(PFT#9), fates_cnp_eca_decompmicc(PFT#9), fates_cnp_nfix1(PFT#9), fates_stoich_nitr(PFT#10), fates_stoich_nitr(PFT#10), fates_cnp_phos_store_ratio(PFT#10), **+fates_cnp_nitr_store_ratio(PFT#10)** | fates_cnp_nitr_store_ratio(PFT#10): 5.0 → 1.5 |
| exp8 | 8 | fates_stoich_phos(PFT#9), fates_cnp_eca_decompmicc(PFT#9), fates_cnp_nfix1(PFT#9), fates_stoich_nitr(PFT#10), fates_stoich_nitr(PFT#10), fates_cnp_phos_store_ratio(PFT#10), fates_cnp_nitr_store_ratio(PFT#10), **+fates_turnover_leaf(PFT#7)** | fates_turnover_leaf(PFT#7): 2.0 → 1.5 |
| exp9 | 9 | fates_stoich_phos(PFT#9), fates_cnp_eca_decompmicc(PFT#9), fates_cnp_nfix1(PFT#9), fates_stoich_nitr(PFT#10), fates_stoich_nitr(PFT#10), fates_cnp_phos_store_ratio(PFT#10), fates_cnp_nitr_store_ratio(PFT#10), fates_turnover_leaf(PFT#7), **+fates_cnp_phos_store_ratio(PFT#7)** | fates_cnp_phos_store_ratio(PFT#7): 3.2857 → 1.5 |
| exp10 | 10 | fates_stoich_phos(PFT#9), fates_cnp_eca_decompmicc(PFT#9), fates_cnp_nfix1(PFT#9), fates_stoich_nitr(PFT#10), fates_stoich_nitr(PFT#10), fates_cnp_phos_store_ratio(PFT#10), fates_cnp_nitr_store_ratio(PFT#10), fates_turnover_leaf(PFT#7), fates_cnp_phos_store_ratio(PFT#7), **+fates_cnp_turnover_phos_retrans(PFT#7)** | fates_cnp_turnover_phos_retrans(PFT#7): 0.6 → 0.78 |
| exp11 | 11 | fates_stoich_phos(PFT#9), fates_cnp_eca_decompmicc(PFT#9), fates_cnp_nfix1(PFT#9), fates_stoich_nitr(PFT#10), fates_stoich_nitr(PFT#10), fates_cnp_phos_store_ratio(PFT#10), fates_cnp_nitr_store_ratio(PFT#10), fates_turnover_leaf(PFT#7), fates_cnp_phos_store_ratio(PFT#7), fates_cnp_turnover_phos_retrans(PFT#7), **+fates_cnp_turnover_phos_retrans(PFT#7)** | fates_cnp_turnover_phos_retrans(PFT#7): 0.6 → 0.78 |
| exp12 | 12 | fates_stoich_phos(PFT#9), fates_cnp_eca_decompmicc(PFT#9), fates_cnp_nfix1(PFT#9), fates_stoich_nitr(PFT#10), fates_stoich_nitr(PFT#10), fates_cnp_phos_store_ratio(PFT#10), fates_cnp_nitr_store_ratio(PFT#10), fates_turnover_leaf(PFT#7), fates_cnp_phos_store_ratio(PFT#7), fates_cnp_turnover_phos_retrans(PFT#7), fates_cnp_turnover_phos_retrans(PFT#7), **+fates_stoich_phos(PFT#9)** | fates_stoich_phos(PFT#9): 0.002069 → 0.0009 |




---

## Iteration Context

```json
{
  "calibration_round": 3,
  "iteration": 7,
  "phase": 4,
  "phase_name": "synthesis",
  "timestamp": "2026-04-07T12:35:16.758288",
  "site": "Kougarok",
  "session_id": "20260406_143413",
  "experiment_count": 0,
  "skip_testing_count": 6,
  "n_skip_testing_cycles": 7,
  "n_synthesized_experiments": 1,
  "n_evidence_ledger_params": 9
}
```
