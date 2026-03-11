# Skip-Testing Synthesis Summary

**Site:** Kougarok
**Phase:** 4 - Hypothesis (Synthesis)
**Round:** 2 | **Cycle:** 0 | **Iteration:** 4
**Date:** 2026-03-10 00:19:38
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
| 1 | 0.88 | 5 | Universal catastrophic P starvation: all three PFTs show P uptake/demand ratio of ~0.000, with total demand 358,121 g/m2/yr vs supply 0.67 g/m2/yr — a 530,000x imbalance that makes meaningful biomass accumulation impossible under ECA competition, PFT10 ECA competitive exclusion: PFT10 captures only 2.0% of total P uptake (0.013 g/m2/yr) while PFT7 dominates at 73.4%, leaving graminoid in a near-zero P state despite vmax_p_10 being sampled down to its minimum bound (5e-11), L2FR amplification feedback: extreme l2fr_ini values (9.88 for PFT10, 18.31 for PFT9, both at upper bounds in Case 322) generate enormous fine root C pools which ECA interprets as enormous P demand, deepening the starvation rather than relieving it — a positive feedback loop (+3 more) |
| 2 | 0.87 | 5 | PFT9 excessive leaf-to-fine-root ratio (l2fr_ini_9=18.31 at upper bound in Case #322) diverts almost all carbon to roots, starving leaf biomass — Case #3972 with l2fr_ini_9=5.24 achieves PFT9_leaf=85.2 vs Case #322's 26.6, proving l2fr is the dominant bottleneck for PFT9 leaf failure, PFT7 insufficient fine root investment (l2fr_ini_7=0.85 in Case #322 is leaf-biased) produces only 62 g C/m2 fineroot vs target 174 — the opposite problem from PFT9, requiring HIGHER l2fr to increase root biomass, PFT10 structural allometric collapse from triple lower-bound failure: allom_d2bl1_10=0.019, allom_dbh_maxheight_10=0.191, leaf_slatop_10=0.0085 all at sampling lower bounds, preventing graminoid canopy formation regardless of nutrient supply (+3 more) |
| 3 | 0.82 | 5 | PFT10 hydraulic failure mortality at 92% of total deaths (mean rate 12.58 events): mort_hf_sm_threshold_10=1e-08 (at absolute lower bound) triggers hydraulic failure at any soil moisture, making PFT10 effectively non-viable regardless of biomass production — this is the NEWLY IDENTIFIED primary cause of PFT10 collapse, distinct from the P starvation and allometric issues identified in previous cycles, Systemic P demand inflation from PFT7/9 ECA competition: total P demand = 358,121 g/m2/yr vs supply = 0.67 g/m2/yr (ratio 1.9e-6), with PFT7 alone demanding 192,556 g/m2/yr driven by vmax_nh4_7=0.00025 (upper bound) and microb_bio_7=600 (upper bound) and high root biomass investment. This systemic P starvation prevents ALL PFTs from acquiring meaningful nutrition, but PFT10 receives only 2% uptake share (0.013 g/m2/yr) vs demand of 15.5 g/m2/yr, PFT9 excessive leaf-to-fine-root ratio: l2fr_ini_9=18.31 at upper bound routes >95% of new carbon to fine roots, starving leaf carbon allocation. Cycle 2 test confirmed l2fr_ini_9 negative correlation with PFT9 leaf (r=-0.257), though all absolute values remain near-zero due to systemic P starvation masking the l2fr signal in the ensemble. The l2fr mechanism is directionally correct but insufficient alone without P demand correction (+3 more) |
| 4 | 0.82 | 5 | PRIMARY CAUSE — Astronomically inflated total P demand (358,121 g/m²/yr vs supply 0.67 g/m²/yr, ratio 534,509x) driven by extreme vmax_nh4_7=0.00025 (upper bound) and vmax_no3_9=0.00025 (upper bound) in Case #322. The ECA uptake demand formula is vmax × fnrt_C, so when vmax is at the upper bound for large-root PFTs, total system demand becomes physically impossible. Reducing PFT7 and PFT9 vmax by 10-100x is the UNTESTED primary intervention needed to bring total system P demand into a biologically realistic range that allows ECA to distribute P meaningfully., SECONDARY CAUSE — PFT9 over-investment in fine roots via l2fr_ini_9=18.31 (upper bound of range [0.01, 18.31]). This routes >95% of new carbon to fine roots, starving PFT9_leaf (26.6 vs target 124.7). Confirmed by Cycles 2 and 3: r=-0.257 negative correlation between l2fr_ini_9 and PFT9_leaf (p<1e-75). Cases with l2fr_ini_9<6 have 1.77x higher PFT9_leaf than ensemble mean. This is the STRONGEST statistically confirmed mechanism in the evidence ledger., TERTIARY CAUSE — PFT7 leaf-biased allocation from l2fr_ini_7=0.85 (leaf-biased, low ratio means high leaf per root allocation). PFT7_leaf=32.5 g/m² (overproducing vs target 24.6) while PFT7_froot=87.1 g/m² (-50% below target 174.2). Cycle 2 confirmed r=+0.015 positive correlation between l2fr_ini_7 and PFT7_froot — directionally correct but weak due to systemic P starvation masking the signal. (+2 more) |

---

## Hypothesis Evolution (4 cycles + synthesis)

| Iter | Name | # Params | Result |
|------|------|----------|--------|
| 1 | P-Starvation Root Cause: vmax_p_10 EC... | 5 | Not supported (0.90) |
| 2 | Dual L2FR Correction + PFT10 Allometr... | 7 | Not supported (0.62) |
| 3 | PFT10 Hydraulic Mortality Escape + Sy... | 6 | Not supported (0.70) |
| 4 | Systemic P Demand Reset via Dual vmax... | 7 | Not supported (0.69) |
| Synth | Systemic P Demand Reset via Dual vmax... | 7 | → HPC (0.72) |

---

## Evidence Ledger

### Active Parameters

| Parameter | Times Proposed | Times Supported | Status |
|-----------|---------------|-----------------|--------|
| fates_allom_l2fr | 6 | 0 | active |
| fates_cnp_pid_kd | 6 | 0 | active |
| fates_cnp_vmax_nh4 | 2 | 0 | active |
| fates_cnp_vmax_no3 | 1 | 0 | active |

### Dropped Parameters

| Parameter | Times Proposed | Times Supported | Status |
|-----------|---------------|-----------------|--------|
| fates_stoich_phos | 5 | 0 | dropped |
| fates_cnp_vmax_p | 1 | 0 | dropped |
| fates_cnp_eca_vmax_ptase | 1 | 0 | dropped |
| fates_allom_d2bl1 | 1 | 0 | dropped |
| fates_allom_dbh_maxheight | 1 | 0 | dropped |
| fates_mort_hf_sm_threshold | 1 | 0 | dropped |



---

## Synthesized Experiment Designs

### Experiment 1: Systemic P Demand Reset via Dual vmax Reduction + L2FR Rebalancing

- **Confidence:** 0.72
- **Design:** cumulative

| Parameter | Current | Proposed | Rationale |
|-----------|---------|----------|-----------|
| fates_cnp_vmax_nh4 | 0.00025 | 2.5e-06 | Case #322 has vmax_nh4_7 at absolute upper bound. PFT7 al... |
| fates_cnp_vmax_no3 | 0.00025 | 2.5e-06 | Case #322 has vmax_no3_9 at absolute upper bound — PFT9's... |
| fates_cnp_vmax_nh4 | 0.00021428575 | 2.14e-06 | Case #322 has vmax_nh4_9=0.000214 (near upper bound). Com... |
| fates_allom_l2fr | 18.31149756 | 5.2 | Case #322 has l2fr_ini_9 at absolute upper bound [0.01, 1... |
| fates_allom_l2fr | 0.8518917117142859 | 1.8 | Case #322 has l2fr_ini_7=0.852 (leaf-biased). PFT7_leaf=3... |
| fates_cnp_pid_kd | 0.01 | 0.35 | Case #322 has pid_kd_10=0.01 at lower bound [0.01, 0.5]. ... |
| fates_cnp_pid_kd | 0.01 | 0.2 | Case #322 has pid_kd_9=0.01 at lower bound. Without deriv... |

#### Cumulative Experiment Breakdown

Each experiment cumulatively adds one parameter change to isolate individual effects:

| Exp | # Params | Parameters Modified | Key Change |
|-----|----------|---------------------|------------|
| exp1 | 1 | fates_cnp_vmax_nh4 | fates_cnp_vmax_nh4: 0.00025 → 2.5e-06 |
| exp2 | 2 | fates_cnp_vmax_nh4, **+fates_cnp_vmax_no3** | fates_cnp_vmax_no3: 0.00025 → 2.5e-06 |
| exp3 | 3 | fates_cnp_vmax_nh4, fates_cnp_vmax_no3, **+fates_cnp_vmax_nh4** | fates_cnp_vmax_nh4: 0.00021428575 → 2.14e-06 |
| exp4 | 4 | fates_cnp_vmax_nh4, fates_cnp_vmax_no3, fates_cnp_vmax_nh4, **+fates_allom_l2fr** | fates_allom_l2fr: 18.31149756 → 5.2 |
| exp5 | 5 | fates_cnp_vmax_nh4, fates_cnp_vmax_no3, fates_cnp_vmax_nh4, fates_allom_l2fr, **+fates_allom_l2fr** | fates_allom_l2fr: 0.8518917117142859 → 1.8 |
| exp6 | 6 | fates_cnp_vmax_nh4, fates_cnp_vmax_no3, fates_cnp_vmax_nh4, fates_allom_l2fr, fates_allom_l2fr, **+fates_cnp_pid_kd** | fates_cnp_pid_kd: 0.01 → 0.35 |
| exp7 | 7 | fates_cnp_vmax_nh4, fates_cnp_vmax_no3, fates_cnp_vmax_nh4, fates_allom_l2fr, fates_allom_l2fr, fates_cnp_pid_kd, **+fates_cnp_pid_kd** | fates_cnp_pid_kd: 0.01 → 0.2 |




---

## Iteration Context

```json
{
  "calibration_round": 2,
  "iteration": 4,
  "phase": 4,
  "phase_name": "synthesis",
  "timestamp": "2026-03-10T00:19:38.213238",
  "site": "Kougarok",
  "session_id": "20260309_232001",
  "experiment_count": 0,
  "skip_testing_count": 3,
  "n_skip_testing_cycles": 4,
  "n_synthesized_experiments": 1,
  "n_evidence_ledger_params": 10
}
```
