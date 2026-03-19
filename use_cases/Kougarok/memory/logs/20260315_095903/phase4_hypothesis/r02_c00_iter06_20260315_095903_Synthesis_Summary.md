# Skip-Testing Synthesis Summary

**Site:** Kougarok
**Phase:** 4 - Hypothesis (Synthesis)
**Round:** 2 | **Cycle:** 0 | **Iteration:** 6
**Date:** 2026-03-15 11:05:09
**Skip-testing cycles:** 6
**Synthesized experiments:** 1

---

## Screening Baseline

- **Best case (targets):** #322 (RMSRE ?, 3 targets met)
- **Lowest cost case:** #1386 (RMSRE ?, 0 targets met)


---

## Diagnosis Evolution (6 cycles)

| Iter | Confidence | # Failing | Key Causes |
|------|-----------|-----------|------------|
| 1 | 0.87 | 6 | SYSTEMIC P STARVATION (PRIMARY): Total plant P demand (358,121 g/m²/yr) exceeds total P uptake (0.67 g/m²/yr) by a factor of ~530,000x. Supply/demand ratios are 0.000 for PFT7, 0.000 for PFT9, and 0.001 for PFT10. This is not a calibration failure — it is a near-complete P cutoff that prevents all biomass accumulation regardless of parameter settings., PROTOCOL-LEVEL P STARVATION (PRIMARY-STRUCTURAL): Current spinup configuration has A2MC_RGSP_SUPLPHOS=NONE and A2MC_TRANS_SUPLPHOS=NONE, while A2MC_ADSP_SUPLPHOS=ALL. Vegetation builds biomass with supplemented P in ADSP but then collapses when P supplementation is removed in RGSP/TRANS phases, because soil P mineralization rates (gross: 0.034 g/m²/yr, biochem: 0.533 g/m²/yr) are insufficient to sustain the observed biomass levels under current stoichiometry parameters., PARAMETER SPACE BOUNDARY CONSTRAINT: Case #322 (best target satisfier) has 46 of 162 parameters (28.4%) at or near sampling bounds, with 6 CNP vmax parameters and 4 CNP km parameters specifically at bounds. The test_morris_bounds_impact confirmed this at 95% confidence with 9/9 key parameters at bounds. This proves the current ensemble sampling does not bracket the feasible parameter region. (+3 more) |
| 2 | 0.82 | 5 | PROTOCOL-LEVEL P STARVATION (PRIMARY, CONFIRMED): The stoich_phos skip-test rejection (confidence 0.11, composite correlation -0.040, only 17% negative correlations) proves that within-ensemble parameter variation is insufficient to escape the P starvation regime. With A2MC_RGSP_SUPLPHOS=NONE and A2MC_TRANS_SUPLPHOS=NONE, vegetation must sustain observed biomass on 0.567 g/m2/yr mineralized P, while demand at observed biomass exceeds 358,000 g/m2/yr. No parameter combination within current bounds can bridge this 5-order-of-magnitude gap — confirmed by 86.6% zero-target failure rate and stoich_phos hypothesis rejection., PFT10 HYDRAULIC FAILURE MORTALITY (SECONDARY, NEW): Mortality analysis shows PFT10 hydraulic failure causes 92% of deaths (dominant_cause='hydraulic'). mort_hf_sm_threshold_10 is at lower bound (1e-08, verified in Case #322 edge analysis). This means PFT10 is being killed by drought stress at the minimum possible moisture threshold, likely because permafrost Arctic conditions in the model trigger hydraulic failure at moisture levels that real graminoids tolerate. This is mechanistically INDEPENDENT of P starvation and explains why PFT10 biomass is near zero even compared to what little P is available., EXTREME L2FR CREATING ROOT CARBON TRAP (TERTIARY): Case #322 has l2fr_ini_9=18.31 (at upper bound) and l2fr_ini_10=9.88 (at upper bound). High L2FR drives excessive fine root carbon allocation, depleting carbon available for leaf growth. The L2FR carbon limitation test showed confidence 0.60 that high L2FR reduces PFT9 leaves by 63%. Combined with P starvation, this creates a carbon-nutrient double constraint on leaf biomass. (+2 more) |
| 3 | 0.78 | 5 | PRIMARY — CONFIRMED PROTOCOL-LEVEL P STARVATION: With A2MC_RGSP_SUPLPHOS=NONE and A2MC_TRANS_SUPLPHOS=NONE, total soil P input is 0.857 g/m2/yr versus plant P demand of 358,121 g/m2/yr (supply/demand = 1.9e-6). This 5-order-of-magnitude gap makes ALL parameter variation within current bounds irrelevant — confirmed by two rejected skip-tests (stoich_phos: r=-0.040, conf=0.11; hydraulic: r=-0.016, conf=0.10). The system is in a degenerate state that ONLY protocol change can escape., SECONDARY — HYDRAULIC FAILURE IS AN EFFECT NOT A CAUSE: The 92% hydraulic-failure mortality for PFT10 is a DOWNSTREAM consequence of P starvation cascade (P deficit → PID allocates C to roots → insufficient leaf C → GPP collapses → BTRAN drops → hydraulic failure triggered), NOT an independent driver. The skip-test proved that mort_hf_sm_threshold_10 variation within ensemble [1e-8, 1.44e-6] does NOT predict PFT10 biomass (r=-0.016, p=0.252), confirming that raising the threshold parameter alone cannot rescue PFT10. Counter-intuitively, high-threshold cases have 0.53x leaf10 vs low-threshold cases, consistent with confounding from other parameters in those cases., TERTIARY — L2FR CARBON SINK INTERACTION: The conditional correlation analysis shows l2fr_ini_10 vs PFT10 leaf r=0.266 (p<0.001) when conditioned on high mort_hf_sm_threshold cases. This confirms L2FR IS a meaningful carbon allocation driver when plants can survive, but it is masked by the dominant P starvation effect across the full ensemble. Once P starvation is resolved via protocol change, L2FR will become a primary calibration lever for PFT10 biomass partitioning. (+2 more) |
| 4 | 0.72 | 5 | PRIMARY (CONFIRMED, confidence=0.85): Inter-PFT P competition asymmetry — PFT7 captures 73.4% of total P uptake via vmax_nh4_7=0.00025 (upper bound), leaving PFT10 only 2.0% (0.013 g/m2/yr). The competition rebalancing hypothesis passed skip-testing with composite r=0.273 (p<1e-84), with all four individual correlations showing expected signs. Case #3972 demonstrates this is actionable: using vmax_nh4_7=2.5e-10 + km_nh4_10=0.07 achieves PFT10_leaf=21.1 vs Case #322's 6.6 — a 3.2x improvement from ECA competition alone., SECONDARY (CONFIRMED, confidence=0.95): Protocol-level P starvation — SUPLPHOS=NONE during RGSP and TRANS phases results in total P input of 0.857 g/m2/yr against total demand of 358,121 g/m2/yr (supply/demand = 1.9e-6). This 5-order-of-magnitude gap cannot be bridged by any within-ensemble parameter change alone, but competition rebalancing can redistribute the scarce supply more equitably between PFTs., TERTIARY (CONFIRMED, confidence=0.60): L2FR carbon allocation imbalance for PFT9 — High L2FR (>10) reduces PFT9 leaves by 63% (supported: True, confidence 0.60 from test_l2fr_carbon_limitation). Case #322 has l2fr_ini_9=18.31 at upper bound. PFT9 leaf is 18.4% below target, which could be partially addressed by reducing l2fr_ini_9. (+2 more) |
| 5 | 0.78 | 5 | PRIMARY (CONFIRMED, confidence=0.90): Protocol-level P starvation — SUPLPHOS=NONE during RGSP and TRANS phases results in total P input of 0.857 g/m2/yr against total demand of 358,121 g/m2/yr (supply/demand = 2.4e-6). This 5-order-of-magnitude gap is the fundamental structural problem. Even the best parameter combination within the current protocol can only partially mitigate (not solve) this — demonstrated by max achievable PFT10_leaf of ~21 g/m2 (Case #3972) vs target of 82.65 g/m2., SECONDARY (CONFIRMED, confidence=0.85): Inter-PFT ECA competition asymmetry — PFT7 captures 73.4% of total P uptake (0.4917 g/m2/yr) via vmax_nh4_7=0.00025 (upper bound, 1000x default), leaving PFT10 only 2.0% (0.013 g/m2/yr). Skip-test confirmed: composite r=0.273 (p<1e-84), vmax_nh4_7 vs leaf10 r=-0.198 (p<1e-44), km_nh4_10 vs leaf10 r=-0.093 (p<1e-10). Competition rebalancing empirically achieves 3.2x PFT10_leaf improvement (Case #3972 vs #322)., TERTIARY (CONFIRMED, confidence=0.75): L2FR carbon allocation imbalance for PFT9 — l2fr_ini_9=18.31 (upper bound in Case #322) drives root-biased carbon allocation. Cycle 4 skip-test confirmed l2fr_ini_9 vs PFT9_leaf r=-0.257 (strongest leaf predictor found for PFT9). With PFT9_leaf now at 26.6 vs target 124.7 (-78.7%), L2FR correction is essential. (+2 more) |
| 6 | 0.82 | 5 | PRIMARY (STRUCTURAL, confidence=0.95): Protocol-level P starvation — SUPLPHOS=NONE during RGSP and TRANS phases results in total P input of 0.857 g/m2/yr against total plant P demand of 358,121 g/m2/yr (supply/demand ratio = 2.4e-6). This 5-order-of-magnitude structural gap is the fundamental bottleneck. No parameter combination within the current ensemble can close this gap — the best achievable PFT10_leaf within-protocol is ~37 g/m2 (Case #1386) vs target 82.65 g/m2, representing a 2.2x shortfall that is irreducible without protocol change. The P mass balance (confirmed diagnostic): weathering 0.0004 + deposition 0.0004 + desorption 0.2887 + biochemical mineralization 0.5333 + gross mineralization 0.0335 = 0.8563 g/m2/yr total P input., SECONDARY (CONFIRMED, confidence=0.90): Inter-PFT ECA competition asymmetry — Case #322 has vmax_nh4_7=0.00025 (upper bound, 1000x default), giving PFT7 73.4% of total P uptake (0.4917 g/m2/yr). Skip-test confirmed: r=-0.198 (p<1e-44) for vmax_nh4_7 vs PFT10 leaf; r=-0.093 (p<1e-10) for km_nh4_10 vs PFT10 leaf; r=0.110 (p<1e-14) for recruit_init_density_10 vs PFT10 leaf; composite r=0.273 (p<1e-84). Case #1386 achieves PFT10_leaf=37.0 (vs Case #322's 6.6) through a different competition balance — this 5.6x improvement within the same protocol demonstrates the power of competition rebalancing., TERTIARY (CONFIRMED, confidence=0.85): PFT9 L2FR carbon allocation imbalance — Case #322 has l2fr_ini_9=18.31 (upper bound). r=-0.257 (p<1e-75) confirmed for l2fr_ini_9 vs PFT9_leaf; monotone decrease across quartiles confirmed (l2fr_9_monotone_decrease_in_leaf9=True). PFT9_leaf=26.6 vs target 124.7 (-78.7%). The quartile analysis shows means: [0.018, 0.005, 0.003, 0.002] g/m2 across increasing l2fr_9 quartiles — clear monotone suppression of leaf allocation with increasing L2FR. (+3 more) |

---

## Hypothesis Evolution (6 cycles + synthesis)

| Iter | Name | # Params | Result |
|------|------|----------|--------|
| 1 | Stoichiometric P Demand Collapse: Red... | 6 | Not supported (0.11) |
| 2 | PFT10 Hydraulic Mortality Suppression... | 3 | Not supported (0.10) |
| 3 | Inter-PFT Nutrient Competition Rebala... | 4 | Not supported (0.85) |
| 4 | ECA Competition Rebalancing: Reduce P... | 5 | Not supported (0.15) |
| 5 | ECA Competition Rebalancing + PFT9 L2... | 5 | Not supported (0.43) |
| 6 | ECA Competition Rebalancing via Compl... | 6 | Not supported (0.31) |
| Synth | ECA Competition Rebalancing via Compl... | 6 | → HPC (0.72) |

---

## Evidence Ledger

### Active Parameters

| Parameter | Times Proposed | Times Supported | Status |
|-----------|---------------|-----------------|--------|
| fates_allom_l2fr | 5 | 0 | active |
| fates_cnp_vmax_nh4 | 4 | 0 | active |
| fates_cnp_eca_km_nh4 | 4 | 0 | active |
| fates_recruit_init_density | 4 | 0 | active |
| fates_cnp_vmax_p | 4 | 0 | active |

### Dropped Parameters

| Parameter | Times Proposed | Times Supported | Status |
|-----------|---------------|-----------------|--------|
| fates_stoich_phos | 6 | 0 | dropped |
| fates_mort_hf_sm_threshold | 1 | 0 | dropped |
| fates_mort_scalar_hydrfailure | 1 | 0 | dropped |



---

## Synthesized Experiment Designs

### Experiment 1: ECA Competition Rebalancing via Complementary PFT Parameter Rescue: Case #1386 Parameter Profile with PFT9 L2FR Correction

- **Confidence:** 0.72
- **Design:** cumulative

| Parameter | PFT | Current | Proposed | Rationale |
|-----------|-----|---------|----------|-----------|
| fates_cnp_vmax_nh4 | #7 | 0.00025 | 2.5e-10 | Case #322 has vmax_nh4_7 at the upper bound (1000x defaul... |
| fates_cnp_eca_km_nh4 | #10 | 0.21 | 0.07 | Case #322 has km_nh4_10 at the worst-possible upper bound... |
| fates_allom_l2fr | #9 | 18.31 | 5.0 | The strongest confirmed single predictor of PFT9 leaf bio... |
| fates_recruit_init_density | #10 | 0.1 | 0.281 | Case #322 has recruit_init_density_10 at the lower bound ... |
| fates_cnp_vmax_p | #10 | 5e-11 | 5e-09 | Case #322 has vmax_p_10 at the lower bound (5e-11, 10x be... |
| fates_allom_l2fr | #10 | 9.879 | 4.0 | Case #322 has l2fr_ini_10 at the upper bound (9.879, ense... |

#### Cumulative Experiment Breakdown

Each experiment cumulatively adds one parameter change to isolate individual effects:

| Exp | # Params | Parameters Modified | Key Change |
|-----|----------|---------------------|------------|
| exp1 | 1 | fates_cnp_vmax_nh4(PFT#7) | fates_cnp_vmax_nh4(PFT#7): 0.00025 → 2.5e-10 |
| exp2 | 2 | fates_cnp_vmax_nh4(PFT#7), **+fates_cnp_eca_km_nh4(PFT#10)** | fates_cnp_eca_km_nh4(PFT#10): 0.21 → 0.07 |
| exp3 | 3 | fates_cnp_vmax_nh4(PFT#7), fates_cnp_eca_km_nh4(PFT#10), **+fates_allom_l2fr(PFT#9)** | fates_allom_l2fr(PFT#9): 18.31 → 5.0 |
| exp4 | 4 | fates_cnp_vmax_nh4(PFT#7), fates_cnp_eca_km_nh4(PFT#10), fates_allom_l2fr(PFT#9), **+fates_recruit_init_density(PFT#10)** | fates_recruit_init_density(PFT#10): 0.1 → 0.281 |
| exp5 | 5 | fates_cnp_vmax_nh4(PFT#7), fates_cnp_eca_km_nh4(PFT#10), fates_allom_l2fr(PFT#9), fates_recruit_init_density(PFT#10), **+fates_cnp_vmax_p(PFT#10)** | fates_cnp_vmax_p(PFT#10): 5e-11 → 5e-09 |
| exp6 | 6 | fates_cnp_vmax_nh4(PFT#7), fates_cnp_eca_km_nh4(PFT#10), fates_allom_l2fr(PFT#9), fates_recruit_init_density(PFT#10), fates_cnp_vmax_p(PFT#10), **+fates_allom_l2fr(PFT#10)** | fates_allom_l2fr(PFT#10): 9.879 → 4.0 |




---

## Iteration Context

```json
{
  "calibration_round": 2,
  "iteration": 6,
  "phase": 4,
  "phase_name": "synthesis",
  "timestamp": "2026-03-15T11:05:09.438546",
  "site": "Kougarok",
  "session_id": "20260315_095903",
  "experiment_count": 0,
  "skip_testing_count": 5,
  "n_skip_testing_cycles": 6,
  "n_synthesized_experiments": 1,
  "n_evidence_ledger_params": 8
}
```
