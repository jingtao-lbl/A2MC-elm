# Skip-Testing Synthesis Summary

**Site:** Kougarok
**Phase:** 4 - Hypothesis (Synthesis)
**Round:** 2 | **Cycle:** 0 | **Iteration:** 7
**Date:** 2026-03-09 13:27:36
**Skip-testing cycles:** 7
**Synthesized experiments:** 1

---

## Screening Baseline

- **Best case (targets):** #322 (RMSRE ?, 3 targets met)
- **Lowest cost case:** #1386 (RMSRE ?, 0 targets met)


---

## Diagnosis Evolution (7 cycles)

| Iter | Confidence | # Failing | Key Causes |
|------|-----------|-----------|------------|
| 1 | 0.78 | 5 | SYSTEMIC P STARVATION: All PFTs have P uptake/demand ≈ 0.00 throughout the 120-year simulation. Total ecosystem P demand (358,121 g/m²/yr) exceeds P uptake (0.67 g/m²/yr) by 5 orders of magnitude, indicating the ECA P uptake parameterization is fundamentally miscalibrated for this arctic system., LITTER P TRAP: P accumulates massively in litter pools (Case #322: ~1100 g P/m²; Case #1386: ~3200 g P/m²) instead of being mineralized to plant-available forms. Biochemical mineralization (0.53 g/m²/yr) and gross mineralization (0.035 g/m²/yr) are insufficient to recycle this trapped P., PFT#10 COMPETITIVE EXCLUSION: PFT#10 receives only 2% of total P uptake (0.013 g/m²/yr) despite having the largest biomass targets. In Case #322, vmax_p_10 is at its lower bound (5e-11), while PFT#7 captures 73.4% of P uptake. This competitive asymmetry drives PFT#10 to near-extinction. (+2 more) |
| 2 | 0.80 | 5 | PFT#10 ALLOMETRIC BOTTLENECK: allom_d2bl1_10 (0.019, at lower bound), allom_dbh_maxheight_10 (0.192, at lower bound), leaf_slatop_10 (0.00853, at lower bound), and allom_d2h1_10 (0.370, at lower bound) collectively constrain PFT#10 plants to be too small with too little leaf area to sustain positive carbon balance. This prevents population establishment regardless of nutrient parameters., PFT#10 POPULATION COLLAPSE FEEDBACK: With near-zero population (max ensemble froot=0.3 gC/m²), there are essentially no fine roots to take up ANY nutrients. P uptake parameters are irrelevant when the plant population is functionally extinct. This is confirmed by the Cycle 1 hypothesis test showing zero correlation between vmax_p_10 and PFT#10 biomass., PFT#9 P-MEDIATED LEAF SUPPRESSION: PFT#9 maintains a viable population (froot=191.8 near target) but leaf biomass is severely suppressed (26.6 vs 124.7 target, -78.6% error). The PID controller is shifting allocation heavily to roots (l2fr_ini_9 at upper bound 18.3), starving leaf pools. This suggests P limitation triggers an over-aggressive root allocation response that is self-defeating. (+2 more) |
| 3 | 0.75 | 0 |  |
| 4 | 0.78 | 0 |  |
| 5 | 0.82 | 0 |  |
| 6 | 0.78 | 0 |  |
| 7 | 0.82 | 0 |  |

---

## Hypothesis Evolution (7 cycles + synthesis)

| Iter | Name | # Params | Result |
|------|------|----------|--------|
| 1 | P Supply Bottleneck Relief via Coordi... | 3 | Not supported (0.00) |
| 2 | Allometric-Size Bottleneck Controls P... | 4 | Not supported (0.10) |
| 3 | P-Uptake × Allometry Interaction Gate... | 3 | Not supported (0.30) |
| 4 | Phenology-Recruitment-Nutrient Recycl... | 5 | Not supported (0.46) |
| 5 | Case #1386 Parameter Constellation An... | 0 | Not supported (0.00) |
| 6 | PFT10 P Uptake Bottleneck: Sequential... | 5 | Not supported (0.00) |
| 7 | PFT9-PFT10 Coexistence via Coordinate... | 0 | Not supported (0.30) |
| Synth | PFT10 P Uptake Bottleneck: Sequential... | 5 | → HPC (0.65) |

---

## Evidence Ledger

### Dropped Parameters

| Parameter | Times Proposed | Times Supported | Status |
|-----------|---------------|-----------------|--------|
| fates_cnp_eca_vmax_ptase | 4 | 0 | dropped |
| fates_cnp_vmax_p | 3 | 0 | dropped |
| fates_allom_d2bl1 | 3 | 0 | dropped |
| fates_stoich_phos | 2 | 0 | dropped |
| fates_allom_dbh_maxheight | 1 | 0 | dropped |
| fates_leaf_slatop | 1 | 0 | dropped |
| fates_allom_d2h1 | 1 | 0 | dropped |
| fates_phen_gddthresh_c | 1 | 0 | dropped |
| fates_frag_seed_decay_rate | 1 | 0 | dropped |
| fates_cnp_turnover_nitr_retrans | 1 | 0 | dropped |
| fates_recruit_seed_supplement | 1 | 0 | dropped |
| fates_leaf_vcmax25top | 1 | 0 | dropped |



---

## Synthesized Experiment Designs

### Experiment 1: PFT10 P Uptake Bottleneck: Sequential vmax Escalation with Allometric Support

- **Confidence:** 0.65
- **Design:** cumulative

| Parameter | Current | Proposed | Rationale |
|-----------|---------|----------|-----------|
| fates_cnp_vmax_p | 5e-11 | 5e-08 | Increase P uptake capacity by 1000x from lower bound. Cas... |
| fates_cnp_eca_vmax_ptase | 5e-10 | 5e-07 | Increase phosphatase production rate by 1000x from lower ... |
| fates_allom_d2bl1 | 0.019 | 0.07 | Restore from lower bound to default value. Case #322 has ... |
| fates_stoich_phos | 0.002995 | 0.0015 | Reduce leaf P stoichiometry from upper bound (0.002995) t... |
| fates_stoich_phos | 0.000943 | 0.000709 | Reduce fineroot P stoichiometry toward lower bound. This ... |

#### Cumulative Experiment Breakdown

Each experiment cumulatively adds one parameter change to isolate individual effects:

| Exp | # Params | Parameters Modified | Key Change |
|-----|----------|---------------------|------------|
| exp1 | 1 | fates_cnp_vmax_p | fates_cnp_vmax_p: 5e-11 → 5e-08 |
| exp2 | 2 | fates_cnp_vmax_p, **+fates_cnp_eca_vmax_ptase** | fates_cnp_eca_vmax_ptase: 5e-10 → 5e-07 |
| exp3 | 3 | fates_cnp_vmax_p, fates_cnp_eca_vmax_ptase, **+fates_allom_d2bl1** | fates_allom_d2bl1: 0.019 → 0.07 |
| exp4 | 4 | fates_cnp_vmax_p, fates_cnp_eca_vmax_ptase, fates_allom_d2bl1, **+fates_stoich_phos** | fates_stoich_phos: 0.002995 → 0.0015 |
| exp5 | 5 | fates_cnp_vmax_p, fates_cnp_eca_vmax_ptase, fates_allom_d2bl1, fates_stoich_phos, **+fates_stoich_phos** | fates_stoich_phos: 0.000943 → 0.000709 |




---

## Iteration Context

```json
{
  "calibration_round": 2,
  "iteration": 7,
  "phase": 4,
  "phase_name": "synthesis",
  "timestamp": "2026-03-09T13:27:36.791376",
  "site": "Kougarok",
  "session_id": "20260309_122641",
  "experiment_count": 0,
  "skip_testing_count": 6,
  "n_skip_testing_cycles": 7,
  "n_synthesized_experiments": 1,
  "n_evidence_ledger_params": 12
}
```
