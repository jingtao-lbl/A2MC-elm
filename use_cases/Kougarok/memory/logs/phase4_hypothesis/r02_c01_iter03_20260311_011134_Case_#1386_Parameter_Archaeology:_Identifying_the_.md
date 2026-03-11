# Case #1386 Parameter Archaeology: Identifying the PFT10-Enabling Parameter Regime

**Site:** Kougarok
**Phase:** 4 - Hypothesis
**Round:** 2 | **Cycle:** 1 | **Iteration:** 3
**Date:** 2026-03-11 02:09:05
**Confidence:** 0.87

---

## Hypothesis: Case #1386 Parameter Archaeology: Identifying the PFT10-Enabling Parameter Regime

### Mechanism

The diagnosis reveals a critical dichotomy: Case #322 achieves PFT9 viability (PFT9_leaf=101.8) but PFT10 collapses (leaf=6.6 g C/m²), while Case #1386 achieves PFT10 partial viability (leaf=37.0 g C/m², within std-range 82.65±56.3) but PFT9 collapses (leaf=5.67). This mutual exclusivity suggests that specific parameters — most likely vmax_p_10, l2fr_ini_10, km_p_10, and vmax_ptase_10 — take qualitatively different values in Case #1386 vs Case #322. By systematically comparing all 162 parameters between these two cases in the existing Morris ensemble data, we can identify the exact parameter constellation that enables PFT10 viability, determine whether the PFT9-PFT10 conflict is an ECA competition artifact (reducible by parameter redistribution) or a fundamental model structure issue, and extract the PFT10-enabling parameter values to anchor the Phase 0 ensemble redesign. The hypothesis is: Case #1386 achieves PFT10 leaf biomass within std-range through a combination of (1) higher vmax_p_10 relative to Case #322 (higher per-root P uptake capacity), (2) lower l2fr_ini_10 (reducing PFT10 root P demand to feasible levels), and (3) possibly lower vmax_p_9 or l2fr_ini_9 (reducing PFT9's ECA competition pressure on PFT10). These parameter differences represent the intersection region that a redesigned ensemble must explore. This is NOT a new HPC experiment — it is a custom analysis of already-computed ensemble data to extract the parameter values that accidentally enabled PFT10 viability in one case.

### Design Type

cumulative

---

## AI Reasoning and Analysis

The diagnosis reveals a critical dichotomy: Case #322 achieves PFT9 viability (PFT9_leaf=101.8) but PFT10 collapses (leaf=6.6 g C/m²), while Case #1386 achieves PFT10 partial viability (leaf=37.0 g C/m², within std-range 82.65±56.3) but PFT9 collapses (leaf=5.67). This mutual exclusivity suggests that specific parameters — most likely vmax_p_10, l2fr_ini_10, km_p_10, and vmax_ptase_10 — take qualitatively different values in Case #1386 vs Case #322. By systematically comparing all 162 parameters between these two cases in the existing Morris ensemble data, we can identify the exact parameter constellation that enables PFT10 viability, determine whether the PFT9-PFT10 conflict is an ECA competition artifact (reducible by parameter redistribution) or a fundamental model structure issue, and extract the PFT10-enabling parameter values to anchor the Phase 0 ensemble redesign. The hypothesis is: Case #1386 achieves PFT10 leaf biomass within std-range through a combination of (1) higher vmax_p_10 relative to Case #322 (higher per-root P uptake capacity), (2) lower l2fr_ini_10 (reducing PFT10 root P demand to feasible levels), and (3) possibly lower vmax_p_9 or l2fr_ini_9 (reducing PFT9's ECA competition pressure on PFT10). These parameter differences represent the intersection region that a redesigned ensemble must explore. This is NOT a new HPC experiment — it is a custom analysis of already-computed ensemble data to extract the parameter values that accidentally enabled PFT10 viability in one case.

---

## Parameters to Modify

### fates_cnp_vmax_p
- **Current:** 5e-11
- **Proposed:** DIAGNOSTIC ONLY — extract Case #1386 value to determine new ensemble center
- **Rationale:** Case #1386 is the ONLY case in 4890 simulations showing PFT10_leaf within std-range. Its vmax_p_10 value is the empirical proof-of-concept for what P uptake capacity enables PFT10 viability. This value will anchor the Phase 0 redesign upper bound recommendation.

### fates_allom_l2fr
- **Current:** 9.88
- **Proposed:** DIAGNOSTIC ONLY — extract Case #1386 value
- **Rationale:** The paradoxical behavior (higher L:FR=9.88 matched better than lower L:FR=2.37 in prior tests) suggests the optimal l2fr_ini_10 is constrained by P supply. Case #1386 likely has a different l2fr_ini_10 that reduces PFT10 root P demand to achievable levels while maintaining adequate root biomass target of 382 g C/m².

### fates_allom_l2fr
- **Current:** 18.31
- **Proposed:** DIAGNOSTIC ONLY — extract Case #1386 value
- **Rationale:** Case #1386 shows PFT9 collapse (leaf=5.67 vs 124.7 target), suggesting its l2fr_ini_9 may be very low (reducing PFT9 root demand and ECA competition) OR very high (P-starving PFT9 while allowing PFT10 to acquire more P). This distinction is mechanistically critical for understanding the conflict.

### fates_cnp_vmax_p
- **Current:** 5e-05
- **Proposed:** DIAGNOSTIC ONLY — extract Case #1386 value
- **Rationale:** If Case #1386 achieves PFT10 viability by reducing PFT9 ECA competition (lower vmax_p_9), this confirms the cross-PFT conflict mechanism. If Case #1386 has HIGHER vmax_p_9 but PFT9 still collapses, it suggests PFT9 collapse has a different cause (e.g., mortality parameters).

### fates_cnp_eca_vmax_ptase
- **Current:** 5e-10
- **Proposed:** DIAGNOSTIC ONLY — extract Case #1386 value
- **Rationale:** The diagnosis notes Case #1386 may have vmax_ptase_10=0.0005 (upper bound), giving much higher phosphatase capacity. This would enable PFT10 to access organic P pools unavailable to competitors, potentially explaining how it achieves positive leaf biomass despite ECA competition pressure.

### fates_cnp_eca_decompmicc
- **Current:** 600
- **Proposed:** DIAGNOSTIC ONLY — extract Case #1386 value
- **Rationale:** In Case #322, microb_bio_7=600 gives PFT7 maximum ECA advantage (73.4% of P uptake). If Case #1386 has lower microb_bio_7, this confirms the ECA dominance hypothesis. If Case #1386 has SAME microb_bio_7=600 but PFT10 still achieves viability, then a different mechanism enables PFT10 survival (e.g., high vmax_ptase_10 bypasses ECA competition via organic P).


---

## Expected Outcomes

- **case_1386_vmax_p_10_expected_range:** 1e-06 to 5e-05 — must be significantly above Case #322's 5e-11 to explain PFT10 viability
- **case_1386_l2fr_ini_10_expected_range:** 2.0 to 6.0 — reduced from Case #322's 9.88 to lower root P demand
- **case_1386_vmax_p_9_direction:** Either significantly lower (ECA redistribution hypothesis) or unchanged (phosphatase bypass hypothesis)
- **case_1386_microb_bio_7_direction:** Either lower than 600 (ECA dominance hypothesis) or unchanged (confirming phosphatase access as primary mechanism)
- **conflict_resolution_insight:** If Case #1386 achieves PFT10 viability through ECA redistribution (lower PFT7/9 parameters), then ensemble redesign must target coordinated parameter ratios. If through phosphatase bypass (high vmax_ptase_10), then organic P access is the key lever.
- **phase0_design_anchors:** Case #1386 parameter values for vmax_p_10, l2fr_ini_10, vmax_ptase_10 will define new ensemble centers; Case #322 parameter values for PFT7 and PFT9 shrub parameters will anchor those PFTs

---

## Metadata

```json
{
  "iteration": 5,
  "diagnosis_count": 4,
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
  "iteration": 5,
  "phase": 4,
  "phase_name": "hypothesis",
  "timestamp": "2026-03-11T02:09:05.751633",
  "site": "Kougarok",
  "session_id": "20260311_011134",
  "experiment_count": 1,
  "skip_testing_count": 2,
  "diagnosis_count": 4,
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
