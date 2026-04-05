# Skip-Testing Synthesis Summary

**Site:** Kougarok
**Phase:** 4 - Hypothesis (Synthesis)
**Round:** 3 | **Cycle:** 0 | **Iteration:** 8
**Date:** 2026-04-04 23:59:50
**Skip-testing cycles:** 8
**Synthesized experiments:** 1

---

## Screening Baseline

- **Best case (targets):** #86 (RMSRE ?, 3 targets met)
- **Lowest cost case:** #2939 (RMSRE ?, 2 targets met)


---

## Diagnosis Evolution (8 cycles)

| Iter | Confidence | # Failing | Key Causes |
|------|-----------|-----------|------------|
| 1 | 0.88 | 6 | Universal catastrophic P limitation; Complete labile P pool depletion; P mass balance failure (-507% residual); Parameter space truncation; Transient phase P supplementation disabled (TRANS_SUPLPHOS=NONE); PFT10 specific collapse |
| 2 | 0.82 | 6 | Universal catastrophic P limitation persists; Complete labile P pool depletion confirmed; P mass balance closure failure (-507% residual); PFT10 hydraulic failure mortality dominates (73% of mortality causes); TRANS_SUPLPHOS=NONE protocol forces cold-turkey P cutoff at calibration phase...; Previous hypothesis test failed due to Python syntax error (f-string at line ...; Case #86 has 39 parameters at bounds (17 lower, 22 upper, 24.1% of 162), conf...; PFT10 allometric collapse |
| 3 | 0.82 | 6 | PRIMARY CAUSE; CONFIRMED; CONFIRMED; NEW EVIDENCE; CONFIRMED; SECONDARY; CONFIRMED |
| 4 | 0.82 | 6 | PRIMARY (CONFIRMED); SECONDARY (CONFIRMED, PARADOXICAL); TERTIARY (CONFIRMED); QUATERNARY (CYCLE 2 CONFIRMED); QUINARY (CONFIRMED) |
| 5 | 0.87 | 6 | PRIMARY (CONFIRMED, 5 CYCLES); SECONDARY (CONFIRMED); TERTIARY (CONFIRMED, PARADOXICAL); QUATERNARY (CONFIRMED, CYCLE 4); QUINARY (CONFIRMED); SENARY (CONFIRMED, CONSISTENT) |
| 6 | 0.91 | 6 | PRIMARY (CONFIRMED, 6 CYCLES); SECONDARY (CONFIRMED); TERTIARY (CONFIRMED); QUATERNARY (CONFIRMED, CYCLE 4-5); QUINARY (CONFIRMED); SENARY (CONFIRMED, 3 CYCLES) |
| 7 | 0.93 | 6 | PRIMARY (CONFIRMED, 7 CYCLES); SECONDARY (CONFIRMED); TERTIARY (CONFIRMED); QUATERNARY (CONFIRMED); QUINARY (CONFIRMED); SENARY (CONFIRMED, 5 CYCLES); SEPTENARY (CONFIRMED, 5 CYCLES) |
| 8 | 0.95 | 6 | PRIMARY (CONFIRMED, 7 CYCLES, STRUCTURAL); SECONDARY (CONFIRMED, 5 CYCLES); TERTIARY (CONFIRMED, 5 CYCLES); QUATERNARY (CONFIRMED, 5 CYCLES); QUINARY (CONFIRMED, 2 CYCLES); SENARY |

---

## Hypothesis Evolution (8 cycles + synthesis)

| Iter | Name | # Params | Result |
|------|------|----------|--------|
| 1 | Stoichiometric Demand Reduction + Ret... | 10 | Not supported (0.00) |
| 2 | Stoichiometric Demand Reduction + Ret... | 6 | Not supported (0.47) |
| 3 | Hydraulic Failure Mortality Reduction... | 9 | Not supported (0.50) |
| 4 | P-Supplementation Protocol Unlock + A... | 5 | Not supported (0.70) |
| 5 | P-Retranslocation Maximization + PFT9... | 4 | Not supported (0.70) |
| 6 | Protocol-Fix + PFT9-HF-Reduction + PF... | 3 | Not supported (0.70) |
| 7 | Protocol Fix: TRANS_SUPLPHOS=ALL Rest... | 4 | Not supported (0.80) |
| 8 | P-Supplementation Protocol Restoratio... | 4 | Not supported (1.00) |
| Synth | Stoichiometric Demand Reduction + Ret... | 10 | → HPC (0.62) |

---

## Evidence Ledger

### Active Parameters

| Parameter | Times Proposed | Times Supported | Status |
|-----------|---------------|-----------------|--------|
| fates_cnp_turnover_phos_retrans | 26 | 0 | active |
| fates_mort_scalar_hydrfailure | 8 | 0 | active |
| fates_allom_agb3 | 3 | 0 | active |

### Dropped Parameters

| Parameter | Times Proposed | Times Supported | Status |
|-----------|---------------|-----------------|--------|
| fates_stoich_phos | 6 | 0 | dropped |
| fates_turnover_fnrt | 2 | 0 | dropped |



---

## Synthesized Experiment Designs

### Experiment 1: Stoichiometric Demand Reduction + Retranslocation Amplification to Break P Starvation Cycle

- **Confidence:** 0.62
- **Design:** cumulative

| Parameter | PFT | Current | Proposed | Rationale |
|-----------|-----|---------|----------|-----------|
| fates_stoich_phos | #9 | 0.00428 | 0.0021 | stoich_phos_leaf_9 is AT UPPER BOUND (0.00428) in Case #8... |
| fates_stoich_phos | #9 | 0.00207 | 0.00095 | stoich_phos_fineroot_9 is AT UPPER BOUND (~0.00207) in Ca... |
| fates_stoich_phos | #10 | 0.000921 | 0.000921 | stoich_phos_leaf_10 is ALREADY AT LOWER BOUND (0.000921) ... |
| fates_stoich_phos | #10 | 0.000709 | 0.000709 | stoich_phos_fineroot_10 is ALREADY AT LOWER BOUND (~0.000... |
| fates_cnp_turnover_phos_retrans | #10 | 0.7 | 0.9 | PFT#10 graminoid has the fastest leaf turnover (turnover_... |
| fates_cnp_turnover_phos_retrans | #10 | 0.7 | 0.9 | Same retranslocation increase applied to fineroot organ f... |
| fates_cnp_turnover_phos_retrans | #7 | 0.6 | 0.8 | phos_retrans_7 is AT LOWER BOUND (0.6) in Case #86 — the ... |
| fates_cnp_turnover_phos_retrans | #7 | 0.6 | 0.8 | Consistent Category B treatment — same value as organ=1 f... |
| fates_cnp_turnover_phos_retrans | #9 | 0.75 | 0.85 | Moderate increase for PFT#9 deciduous shrub. Combined wit... |
| fates_cnp_turnover_phos_retrans | #9 | 0.75 | 0.8 | Capped at upper bound 0.80 for PFT#9. Category B consiste... |

#### Cumulative Experiment Breakdown

Each experiment cumulatively adds one parameter change to isolate individual effects:

| Exp | # Params | Parameters Modified | Key Change |
|-----|----------|---------------------|------------|
| exp1 | 1 | fates_stoich_phos(PFT#9) | fates_stoich_phos(PFT#9): 0.00428 → 0.0021 |
| exp2 | 2 | fates_stoich_phos(PFT#9), **+fates_stoich_phos(PFT#9)** | fates_stoich_phos(PFT#9): 0.00207 → 0.00095 |
| exp3 | 3 | fates_stoich_phos(PFT#9), fates_stoich_phos(PFT#9), **+fates_stoich_phos(PFT#10)** | fates_stoich_phos(PFT#10): 0.000921 → 0.000921 |
| exp4 | 4 | fates_stoich_phos(PFT#9), fates_stoich_phos(PFT#9), fates_stoich_phos(PFT#10), **+fates_stoich_phos(PFT#10)** | fates_stoich_phos(PFT#10): 0.000709 → 0.000709 |
| exp5 | 5 | fates_stoich_phos(PFT#9), fates_stoich_phos(PFT#9), fates_stoich_phos(PFT#10), fates_stoich_phos(PFT#10), **+fates_cnp_turnover_phos_retrans(PFT#10)** | fates_cnp_turnover_phos_retrans(PFT#10): 0.7 → 0.9 |
| exp6 | 6 | fates_stoich_phos(PFT#9), fates_stoich_phos(PFT#9), fates_stoich_phos(PFT#10), fates_stoich_phos(PFT#10), fates_cnp_turnover_phos_retrans(PFT#10), **+fates_cnp_turnover_phos_retrans(PFT#10)** | fates_cnp_turnover_phos_retrans(PFT#10): 0.7 → 0.9 |
| exp7 | 7 | fates_stoich_phos(PFT#9), fates_stoich_phos(PFT#9), fates_stoich_phos(PFT#10), fates_stoich_phos(PFT#10), fates_cnp_turnover_phos_retrans(PFT#10), fates_cnp_turnover_phos_retrans(PFT#10), **+fates_cnp_turnover_phos_retrans(PFT#7)** | fates_cnp_turnover_phos_retrans(PFT#7): 0.6 → 0.8 |
| exp8 | 8 | fates_stoich_phos(PFT#9), fates_stoich_phos(PFT#9), fates_stoich_phos(PFT#10), fates_stoich_phos(PFT#10), fates_cnp_turnover_phos_retrans(PFT#10), fates_cnp_turnover_phos_retrans(PFT#10), fates_cnp_turnover_phos_retrans(PFT#7), **+fates_cnp_turnover_phos_retrans(PFT#7)** | fates_cnp_turnover_phos_retrans(PFT#7): 0.6 → 0.8 |
| exp9 | 9 | fates_stoich_phos(PFT#9), fates_stoich_phos(PFT#9), fates_stoich_phos(PFT#10), fates_stoich_phos(PFT#10), fates_cnp_turnover_phos_retrans(PFT#10), fates_cnp_turnover_phos_retrans(PFT#10), fates_cnp_turnover_phos_retrans(PFT#7), fates_cnp_turnover_phos_retrans(PFT#7), **+fates_cnp_turnover_phos_retrans(PFT#9)** | fates_cnp_turnover_phos_retrans(PFT#9): 0.75 → 0.85 |
| exp10 | 10 | fates_stoich_phos(PFT#9), fates_stoich_phos(PFT#9), fates_stoich_phos(PFT#10), fates_stoich_phos(PFT#10), fates_cnp_turnover_phos_retrans(PFT#10), fates_cnp_turnover_phos_retrans(PFT#10), fates_cnp_turnover_phos_retrans(PFT#7), fates_cnp_turnover_phos_retrans(PFT#7), fates_cnp_turnover_phos_retrans(PFT#9), **+fates_cnp_turnover_phos_retrans(PFT#9)** | fates_cnp_turnover_phos_retrans(PFT#9): 0.75 → 0.8 |




---

## Iteration Context

```json
{
  "calibration_round": 3,
  "iteration": 8,
  "phase": 4,
  "phase_name": "synthesis",
  "timestamp": "2026-04-04T23:59:50.949318",
  "site": "Kougarok",
  "session_id": "20260404_224442",
  "experiment_count": 0,
  "skip_testing_count": 7,
  "n_skip_testing_cycles": 8,
  "n_synthesized_experiments": 1,
  "n_evidence_ledger_params": 5
}
```
