# Phase 2: Screening Reasoning Template

This template defines the structure for AI-driven screening analysis in Phase 2.

---

## Overview

The screening phase analyzes ensemble results to understand **current model behavior** before diagnosis. The AI should:
1. Quantify how well each PFT/target is simulated
2. Identify systematic biases (underestimation vs overestimation)
3. Recognize error patterns across targets
4. Correlate errors with parameter values
5. Formulate initial questions for Phase 3 diagnosis

---

## Required Sections

### 1. Executive Summary

Brief (3-5 sentences) summary of screening results. Example:
```
Ensemble screening of 4890 Morris cases reveals systematic differences in simulation quality across PFTs.
PFT#9 (deciduous shrub) is best simulated with 45% of cases within observational uncertainty.
PFT#10 (graminoid) shows consistent underestimation across all biomass pools, with fineroot being most severe (-74%).
Top 10 parameter sets achieve average RMSRE of 0.38, but no single set satisfies all 9 targets simultaneously.
```

### 2. PFT-by-PFT Performance Summary

Quantify simulation quality for each PFT:

| PFT | Description | Cases Within Uncertainty | Median Error | Best Case Error | Worst Case Error | Simulation Quality |
|-----|-------------|--------------------------|--------------|-----------------|------------------|-------------------|
| 7 | Evergreen shrub | 123/4890 (2.5%) | -45% | -12% | -89% | POOR |
| 9 | Deciduous shrub | 2205/4890 (45%) | +8% | -3% | +67% | **GOOD** |
| 10 | Arctic graminoid | 0/4890 (0%) | -68% | -42% | -95% | CRITICAL |

**Quality definitions:**
- EXCELLENT: >60% cases within uncertainty, median error <15%
- GOOD: 30-60% within uncertainty, median error <30%
- MODERATE: 10-30% within uncertainty, median error <50%
- POOR: 2-10% within uncertainty, median error <70%
- CRITICAL: <2% within uncertainty, requires major parameter adjustment

### 3. Target-by-Target Bias Analysis

For each validation target, characterize the bias:

| Target | Observed (mean ± std) | Ensemble Mean | Ensemble Range | Bias | Bias Type | Consistency |
|--------|----------------------|---------------|----------------|------|-----------|-------------|
| leaf_pft7 | 52.0 ± 15.0 | 28.3 | [5.2, 67.1] | -46% | **UNDEREST** | High (92%) |
| leaf_pft9 | 89.0 ± 20.0 | 96.5 | [34.2, 245.0] | +8% | Slight over | Medium (65%) |
| leaf_pft10 | 84.0 ± 18.0 | 31.2 | [8.1, 78.9] | -63% | **UNDEREST** | High (98%) |
| froot_pft7 | 156.0 ± 40.0 | 89.4 | [12.3, 189.0] | -43% | **UNDEREST** | High (85%) |
| froot_pft9 | 201.0 ± 50.0 | 187.3 | [56.7, 412.0] | -7% | Near target | Low (45%) |
| froot_pft10 | 174.2 ± 35.0 | 45.3 | [5.8, 98.2] | -74% | **UNDEREST** | Very High (99%) |
| AGB_pft7 | 185.0 ± 45.0 | 112.8 | [18.9, 267.0] | -39% | **UNDEREST** | Medium (72%) |
| AGB_pft9 | 298.0 ± 60.0 | 312.5 | [89.4, 678.0] | +5% | Near target | Medium (58%) |
| AGB_pft10 | 211.5 ± 42.0 | 89.7 | [12.1, 156.0] | -58% | **UNDEREST** | High (95%) |

**Bias Type definitions:**
- **UNDEREST**: Systematic underestimation (>80% of cases below observation)
- **OVEREST**: Systematic overestimation (>80% of cases above observation)
- Slight under/over: 60-80% cases biased in one direction
- Near target: Within 15% of observed, good spread
- Variable: No clear bias pattern

**Consistency:** Percentage of cases showing same bias direction

### 4. Biomass Component Comparison (ASCII Visualization)

```
                        LEAF BIOMASS SIMULATION QUALITY

Observed:    ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
             PFT7: 52g    PFT9: 89g    PFT10: 84g

Ensemble:
PFT7:        ▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
             [-46%] Systematic UNDERESTIMATION

PFT9:        ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
             [+8%]  ✓ Well simulated

PFT10:       ▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
             [-63%] Systematic UNDERESTIMATION

─────────────────────────────────────────────────────────────────────────────

                        FINEROOT BIOMASS SIMULATION QUALITY

Observed:    ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
             PFT7: 156g   PFT9: 201g   PFT10: 174g

Ensemble:
PFT7:        ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
             [-43%] UNDERESTIMATION

PFT9:        ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
             [-7%]  ✓ Well simulated

PFT10:       ▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
             [-74%] **SEVERE** UNDERESTIMATION

─────────────────────────────────────────────────────────────────────────────

                        ABOVEGROUND BIOMASS SIMULATION QUALITY

Observed:    ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
             PFT7: 185g   PFT9: 298g   PFT10: 212g

Ensemble:
PFT7:        ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
             [-39%] UNDERESTIMATION

PFT9:        ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
             [+5%]  ✓ Well simulated

PFT10:       ▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
             [-58%] **SEVERE** UNDERESTIMATION
```

### 5. Error Pattern Recognition

Identify systematic patterns across targets:

#### 5a. By PFT
```
┌─────────────────────────────────────────────────────────────────────────┐
│                           ERROR PATTERN BY PFT                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  PFT#7 (Evergreen shrub):                                              │
│  ├── Leaf:  ▼▼▼▼ (-46%) Underestimated                                │
│  ├── Froot: ▼▼▼  (-43%) Underestimated                                │
│  └── AGB:   ▼▼▼  (-39%) Underestimated                                │
│  Pattern: CONSISTENTLY LOW across all pools                            │
│  → Suggests: Overall growth limitation (GPP? nutrients?)               │
│                                                                         │
│  PFT#9 (Deciduous shrub):                                              │
│  ├── Leaf:  ▲    (+8%)  Slight overestimation                         │
│  ├── Froot: ≈    (-7%)  Near target                                   │
│  └── AGB:   ≈    (+5%)  Near target                                   │
│  Pattern: WELL SIMULATED, slight positive bias                         │
│  → Suggests: Model captures deciduous shrub dynamics well              │
│                                                                         │
│  PFT#10 (Arctic graminoid):                                            │
│  ├── Leaf:  ▼▼▼▼▼ (-63%) Severe underestimation                       │
│  ├── Froot: ▼▼▼▼▼▼ (-74%) **MOST SEVERE**                             │
│  └── AGB:   ▼▼▼▼▼ (-58%) Severe underestimation                       │
│  Pattern: CRITICAL UNDERESTIMATION across all pools                    │
│  → Suggests: Fundamental growth constraint on graminoids               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 5b. By Biomass Pool
```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ERROR PATTERN BY POOL                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  FINEROOT:                                                              │
│  • PFT#10 worst: -74% (critical)                                       │
│  • PFT#7 poor:   -43%                                                  │
│  • PFT#9 good:   -7%                                                   │
│  → Root allocation may favor deciduous over evergreen/graminoid        │
│                                                                         │
│  LEAF:                                                                  │
│  • PFT#10 worst: -63%                                                  │
│  • PFT#7 poor:   -46%                                                  │
│  • PFT#9 good:   +8%                                                   │
│  → Same pattern as fineroot - deciduous PFT dominates                  │
│                                                                         │
│  AGB:                                                                   │
│  • PFT#10 worst: -58%                                                  │
│  • PFT#7 poor:   -39%                                                  │
│  • PFT#9 good:   +5%                                                   │
│  → Consistent with leaf/froot - structural biomass follows             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 5c. Cross-PFT Trade-off Analysis

Identify if improving one PFT degrades another:

| Set ID | PFT7 Error | PFT9 Error | PFT10 Error | Trade-off Pattern |
|--------|------------|------------|-------------|-------------------|
| 3930 | -25% | +12% | -42% | PFT9↑ comes at PFT10↓ cost |
| 2451 | -18% | +35% | -55% | **Strong trade-off**: PFT9 overshoots |
| 1287 | -42% | -5% | -38% | All underestimated, less trade-off |
| 4102 | -15% | +8% | -65% | PFT7↑ worsens PFT10↓↓ |

**Trade-off diagnosis:**
- [ ] **Competition-based**: Improving PFT#9 suppresses PFT#10 (shared resource)
- [ ] **Allocation-based**: Parameters that increase one pool decrease another
- [ ] **Structural**: Model cannot simulate both PFT types well simultaneously

### 6. Edge Parameter Analysis

Parameters at or near bounds in top cases:

| Parameter | PFT | Min | Max | Top 10 Mean | At Edge? | Direction | Implication |
|-----------|-----|-----|-----|-------------|----------|-----------|-------------|
| fates_cnp_vmax_p | 10 | 1e-10 | 1e-7 | 9.8e-8 | **YES** | Upper | Wants MORE P uptake |
| fates_leaf_slatop | 10 | 0.006 | 0.04 | 0.038 | **YES** | Upper | Wants thinner leaves |
| fates_alloc_storage_cushion | 10 | 0.5 | 2.5 | 2.4 | **YES** | Upper | Wants larger buffer |
| fates_cnp_pid_kp | 10 | 0.01 | 0.5 | 0.12 | No | - | - |
| fates_leaf_vcmax25top | 9 | 30 | 100 | 78 | No | - | - |

**Edge parameter insights:**
- Parameters hitting upper bound: Model wants values beyond Morris range
- Parameters hitting lower bound: Current range may be too high
- Recommendation: Consider expanding bounds for Phase 4 experiments

### 7. Potential Causes for Phase 3

Initial hypotheses based on screening patterns:

| Hypothesis ID | Statement | Supported By | Affects | Priority |
|---------------|-----------|--------------|---------|----------|
| S1 | PFT#10 is nutrient-limited | vmax_p at upper bound, consistent underestimation | All PFT#10 targets | HIGH |
| S2 | Competition favors PFT#9 over PFT#10 | Trade-off in top cases, PFT#9 well simulated | PFT#10 targets | HIGH |
| S3 | Evergreen PFTs (PFT#7) have wrong allocation | Consistent 40% underestimation all pools | PFT#7 targets | MEDIUM |
| S4 | Root allocation parameters need recalibration | Froot most underestimated pool | froot_pft7, froot_pft10 | MEDIUM |
| S5 | SLA or Vcmax limits graminoid productivity | slatop at edge, no leaf accumulation | leaf_pft10, AGB_pft10 | LOW |

### 8. Questions for Diagnosis Phase

Open questions to guide Phase 3 analysis:

1. **Why is PFT#10 systematically underestimated while PFT#9 is well simulated?**
   - Is it nutrient competition (ECA)?
   - Light competition (canopy position)?
   - Intrinsic growth parameters?

2. **Why does fineroot show the largest bias for PFT#10 (-74%)?**
   - Is root allocation responding to stress (PID controller)?
   - Are root turnover rates too high?
   - Is belowground competition limiting root growth?

3. **What causes the trade-off between PFT#9 and PFT#10 performance?**
   - Shared nutrient pool (P or N)?
   - Shared light resource (canopy competition)?
   - Model structural limitation?

4. **Should we expand parameter bounds for PFT#10?**
   - vmax_p hitting upper bound suggests higher values needed
   - But is this compensating for other errors?

### 9. Recommendations for Phase 3

Prioritized next steps for diagnosis:

```yaml
recommendations:
  - priority: 1
    action: "Investigate PFT#10 nutrient limitation"
    focus: ["FATES_PUPTAKE_SZPF", "FATES_NUPTAKE_SZPF", "P_STRESS", "N_STRESS"]
    reason: "vmax_p at edge, consistent underestimation suggests nutrient bottleneck"

  - priority: 2
    action: "Analyze PFT competition dynamics"
    focus: ["FATES_GPP_PF", "FATES_NPP_PF", "canopy_area_by_pft"]
    reason: "Trade-off between PFT#9 and PFT#10 suggests competitive exclusion"

  - priority: 3
    action: "Examine root allocation and turnover"
    focus: ["FATES_L2FR", "FATES_FROOT_ALLOC", "fates_turnover_fnrt"]
    reason: "Fineroot most severely underestimated, PID may be over-allocating"

  - priority: 4
    action: "Check phenology timing for graminoids"
    focus: ["FATES_GDD", "FATES_COLD_STATUS", "FATES_DAYSINCE_COLDLEAFON"]
    reason: "Arctic graminoid phenology may not match observations"
```

---

## JSON Output Schema

The `reasoning.analyze_screening_results()` method should return:

```json
{
    "ensemble_size": 4890,
    "completed_cases": 4850,
    "best_cost": 0.342,
    "best_set_id": 3930,

    "pft_performance": {
        "7": {
            "name": "Evergreen shrub",
            "cases_within_uncertainty": 123,
            "median_error": -0.45,
            "quality": "POOR"
        },
        "9": {
            "name": "Deciduous shrub",
            "cases_within_uncertainty": 2205,
            "median_error": 0.08,
            "quality": "GOOD"
        },
        "10": {
            "name": "Arctic graminoid",
            "cases_within_uncertainty": 0,
            "median_error": -0.68,
            "quality": "CRITICAL"
        }
    },

    "target_bias": {
        "leaf_pft7": {"bias": -0.46, "type": "UNDEREST", "consistency": 0.92},
        "leaf_pft9": {"bias": 0.08, "type": "near_target", "consistency": 0.65},
        "leaf_pft10": {"bias": -0.63, "type": "UNDEREST", "consistency": 0.98},
        "froot_pft7": {"bias": -0.43, "type": "UNDEREST", "consistency": 0.85},
        "froot_pft9": {"bias": -0.07, "type": "near_target", "consistency": 0.45},
        "froot_pft10": {"bias": -0.74, "type": "UNDEREST", "consistency": 0.99},
        "AGB_pft7": {"bias": -0.39, "type": "UNDEREST", "consistency": 0.72},
        "AGB_pft9": {"bias": 0.05, "type": "near_target", "consistency": 0.58},
        "AGB_pft10": {"bias": -0.58, "type": "UNDEREST", "consistency": 0.95}
    },

    "error_patterns": {
        "by_pft": {
            "7": "Consistently low across all pools",
            "9": "Well simulated, slight positive bias",
            "10": "Critical underestimation across all pools"
        },
        "by_pool": {
            "leaf": "Deciduous >> Evergreen > Graminoid",
            "froot": "Graminoid most underestimated (-74%)",
            "AGB": "Follows leaf/froot pattern"
        }
    },

    "trade_offs": [
        {
            "pft_pair": ["9", "10"],
            "type": "competition",
            "description": "Improving PFT#9 often degrades PFT#10"
        }
    ],

    "edge_parameters": [
        {
            "parameter": "fates_cnp_vmax_p",
            "pft": 10,
            "at_bound": "upper",
            "implication": "Model wants higher P uptake capacity"
        }
    ],

    "screening_hypotheses": [
        {
            "id": "S1",
            "statement": "PFT#10 is nutrient-limited",
            "evidence": "vmax_p at upper bound",
            "priority": "HIGH"
        }
    ],

    "questions_for_diagnosis": [
        "Why is PFT#10 systematically underestimated?",
        "What causes the PFT#9 vs PFT#10 trade-off?",
        "Should parameter bounds be expanded?"
    ],

    "recommendations": [
        {
            "priority": 1,
            "action": "Investigate PFT#10 nutrient limitation",
            "target_phase": 3
        }
    ]
}
```

---

## Quality Checklist

Before finalizing screening analysis:
- [ ] All completed cases analyzed and ranked
- [ ] PFT performance quantified (cases within uncertainty, median error)
- [ ] Bias direction identified for each target (UNDEREST/OVEREST/near_target)
- [ ] ASCII visualizations show clear patterns
- [ ] Error patterns identified by PFT and by biomass pool
- [ ] Trade-offs between PFTs documented
- [ ] Edge parameters flagged with implications
- [ ] Initial hypotheses formulated for Phase 3
- [ ] Open questions listed to guide diagnosis
- [ ] JSON output is valid and parseable
