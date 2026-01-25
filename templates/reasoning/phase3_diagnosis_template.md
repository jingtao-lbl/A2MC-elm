# Phase 3: Diagnosis Reasoning Template

This template defines the structure for AI-driven root cause analysis in Phase 3.

---

## Overview

The diagnosis phase analyzes **why** calibration targets are not being met. The AI should:
1. Form multiple hypotheses before analysis
2. Systematically evaluate each hypothesis with quantitative evidence
3. Identify the root causes with mechanistic understanding
4. Produce actionable recommendations for Phase 4

---

## Required Sections

### 1. Executive Summary

Brief (2-3 sentences) summary of key findings. Example:
```
PFT#10 Arctic graminoid shows systematic underestimation across all biomass pools (leaf, froot, AGB).
The primary cause appears to be phosphorus limitation combined with light competition from PFT#9.
Confidence: 0.85
```

### 2. Failing Targets Analysis

Quantitative breakdown of each failing target:

| Target | Observed | Best Simulated | Error (%) | Severity |
|--------|----------|----------------|-----------|----------|
| froot_pft10 | 174.2 g/m² | 45.3 g/m² | -74% | CRITICAL |
| leaf_pft10 | 84.0 g/m² | 31.2 g/m² | -63% | HIGH |
| AGB_pft10 | 211.5 g/m² | 89.7 g/m² | -58% | HIGH |

**Severity definitions:**
- CRITICAL: >50% error, blocks progress
- HIGH: 30-50% error, significant impact
- MEDIUM: 20-30% error, needs attention
- LOW: <20% error, within acceptable range

### 3. Initial Hypotheses

List 4-6 hypotheses BEFORE deep analysis. Each hypothesis should:
- State a specific mechanism
- Predict which targets it affects
- Be testable

Example:
```yaml
hypotheses:
  - id: H1
    statement: "P starvation limits PFT#10 growth due to low soil P availability"
    mechanism: ECA_Competition
    affects: [froot_pft10, leaf_pft10, AGB_pft10]
    testable: true

  - id: H2
    statement: "Light competition from PFT#9 suppresses PFT#10 GPP"
    mechanism: Light_Competition
    affects: [leaf_pft10, AGB_pft10]
    testable: true

  - id: H3
    statement: "PID controller over-allocates to roots under stress"
    mechanism: PID_Controller
    affects: [froot_pft10, leaf_pft10]
    testable: true

  - id: H4
    statement: "Excessive mortality rate prevents biomass accumulation"
    mechanism: Carbon_Starvation
    affects: [AGB_pft10]
    testable: true
```

### 4. Diagnostic Evidence

For each hypothesis, present quantitative evidence:

#### H1: P Starvation
```
Evidence FOR:
- FATES_PUPTAKE_PFT10: 0.0012 vs PFT#9: 0.089 (PFT#10 is 1.3% of PFT#9)
- FATES_P_STRESS_PFT10: 0.92 (severe P stress)
- Soil labile P at PFT#10 root zone: 2.3 mg/kg (limiting)

Evidence AGAINST:
- Morris sensitivity shows fates_cnp_vmax_nh4 ranks higher than fates_cnp_vmax_p
- N uptake also very low, may be co-limiting
```

#### H2: Light Competition
```
Evidence FOR:
- FATES_GPP_PFT9: 485 g/m²/yr vs FATES_GPP_PFT10: 67 g/m²/yr
- PFT#9 LAI: 2.1, PFT#10 LAI: 0.3
- Canopy position analysis: PFT#10 in understory

Evidence AGAINST:
- Arctic graminoids naturally have lower LAI
- Some cases show PFT#10 can achieve higher biomass
```

### 5. Conceptual Model (ASCII Diagram)

Visualize the causal chain:
```
                     ┌─────────────────────────┐
                     │   Low Soil P Available   │
                     └───────────┬─────────────┘
                                 │
                                 ▼
            ┌────────────────────────────────────────┐
            │  ECA Competition: PFT#9 outcompetes    │
            │  PFT#10 for limited P (higher vmax_p)  │
            └────────────────┬───────────────────────┘
                             │
               ┌─────────────┴─────────────┐
               │                           │
               ▼                           ▼
    ┌──────────────────┐        ┌──────────────────┐
    │ PFT#10 P Stress  │        │ PFT#9 Thrives    │
    │   (stress=0.92)  │        │  (high GPP/LAI)  │
    └────────┬─────────┘        └────────┬─────────┘
             │                           │
             ▼                           ▼
    ┌──────────────────┐        ┌──────────────────┐
    │ PID: ↑ Root Alloc│        │ Light Shading    │
    │ (try to get P)   │        │ of PFT#10        │
    └────────┬─────────┘        └────────┬─────────┘
             │                           │
             └───────────┬───────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  PFT#10 Stuck in     │
              │  Low-Growth Trap     │
              │  (all pools low)     │
              └──────────────────────┘
```

### 5b. "Perfect Storm" Diagrams (Multi-Factor Interactions)

When multiple stressors interact, use this pattern:
```
          External Driver (e.g., 1963-1968 Drought)
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────┐
│ Plant Water     │ │ Soil Moist  │ │ Temperature │
│ Stress          │ │ (w_scalar↓) │ │ (t_scalar)  │
│ • btran drops   │ │             │ │             │
└────────┬────────┘ └──────┬──────┘ └──────┬──────┘
         │                 │               │
         ▼                 ▼               │
┌─────────────────┐ ┌─────────────┐        │
│ Hydraulic Mort↑ │ │ Decomp ↓    │        │
│ C Starvation ↑  │ │ Litter pile │        │
│ → Veg dies      │ │ up          │        │
└────────┬────────┘ └──────┬──────┘        │
         │                 │               │
         └────────┬────────┘               │
                  ▼                        │
         ┌──────────────────┐              │
         │ LITTER P TRAPPING│◄─────────────┘
         │ (input >> decomp)│
         └──────────────────┘
```

### 5c. Mortality Component Analysis

When vegetation crash is involved, decompose mortality:

| Year | Total Mort | Hydraulic | C Starvation | Fire | Dominant |
|------|------------|-----------|--------------|------|----------|
| 1960 | 128.0 | 0.0 | 0.0 | 0.0 | Background |
| 1963 | 511.8 | 426.3 | 0.03 | 0.0 | **HYDRAULIC** |
| 1965 | 429.0 | 237.0 | 71.0 | 0.0 | Hydraulic + C Starv |
| 1970 | 16.8 | 5.0 | 10.9 | 0.0 | Recovery |

**Key parameters controlling mortality:**
- `fates_mort_hf_sm_threshold` - btran threshold for hydraulic mortality
- `fates_mort_scalar_hydrfailure` - Max hydraulic mortality rate
- `fates_mort_scalar_cstarvation` - Max carbon starvation mortality rate

**Phenology-Nutrient Uptake Interaction (explains PFT differential mortality):**
- **Evergreen PFTs**: Persistent but LOW nutrient uptake rates year-round → cannot build reserves during favorable periods → vulnerable to chronic stress
- **Deciduous PFTs & Graminoids**: HIGH uptake rates during spring flushing → can build nutrient reserves quickly → more resilient to drought
- This explains why PFT#7 (evergreen shrub) died while PFT#9 and PFT#10 survived the 1963-1968 drought

### 6. Root Cause Identification

Rank root causes by importance:

| Rank | Root Cause | Confidence | Affected Targets | Evidence Strength |
|------|------------|------------|------------------|-------------------|
| 1 | P Starvation | 0.85 | all PFT#10 pools | Strong |
| 2 | Light Competition | 0.70 | leaf, AGB | Moderate |
| 3 | PID Overshoot | 0.55 | froot/leaf ratio | Weak |

### 7. Key Insights

Numbered list of critical findings:

1. **Triple Bottleneck Pattern**: PFT#10 suffers from P limitation → light competition → allocation imbalance simultaneously
2. **Allocation Paradox Risk**: Simply increasing vmax_p may trigger PID response that reduces root allocation
3. **Cross-PFT Competition**: Cannot fix PFT#10 without addressing PFT#9 competitive advantage

### 7b. Pool Tracking Analysis (for P/N/C investigations)

When diagnosing nutrient cycling issues, track pool changes:

| Pool | Initial | End ADSP | End RGSP | Final | Δ Total |
|------|---------|----------|----------|-------|---------|
| Labile P | 0.0 | 442.9 | 164.7 | 87.9 | - |
| SMINP | 0.0 | 262.6 | 83.6 | 43.7 | - |
| SECONDP | 0.0 | 146.0 | 78.3 | 43.7 | - |
| **LITRP** | 0.3 | 67.9 | 31.5 | **471.2** | +470.9 |
| SOILP | 0.8 | 74.7 | 144.2 | 1.5 | -143 |
| VEGP | 0.2 | 2.3 | 1.5 | 1.5 | +1.3 |
| **Total** | 1.3 | 589.2 | 342.9 | **563.0** | +561.7 |

**Key insight:** P is NOT lost from the system - it's trapped in litter!

### 7c. Questions for Discussion

End diagnosis with open questions to address:

1. **Should we reduce `mort_scalar_hydrfailure` for Arctic PFTs?**
   - Evergreen shrubs may be more drought-tolerant than defaults suggest

2. **Should we adjust litter decomposition for Arctic conditions?**
   - Current parameters may allow too much litter accumulation

3. **Is PID response appropriate during combined stress?**
   - Massive root allocation during water stress depletes carbon reserves

4. **What about nutrient demand calculation?**
   - Uptake/demand < 1% suggests demand may be unrealistically high

---

### 8. Recommendations for Phase 4

Actionable next steps:

```yaml
recommendations:
  - priority: 1
    action: "Test P availability hypothesis"
    parameters: [fates_cnp_vmax_p, fates_cnp_eca_alpha_ptase]
    expected_effect: "Increase PFT#10 P uptake without triggering PID reallocation"

  - priority: 2
    action: "Test reduced PFT#9 competitive advantage"
    parameters: [fates_leaf_slatop_9, fates_cnp_vmax_p_9]
    expected_effect: "Level playing field for P competition"

  - priority: 3
    action: "Test storage buffer hypothesis"
    parameters: [fates_cnp_phos_store_ratio_10]
    expected_effect: "Build P reserves to buffer stress periods"
```

---

## JSON Output Schema

The `reasoning.diagnose()` method should return:

```json
{
    "iteration": 1,
    "failing_targets": ["froot_pft10", "leaf_pft10", "AGB_pft10"],
    "severity_breakdown": {
        "critical": ["froot_pft10"],
        "high": ["leaf_pft10", "AGB_pft10"],
        "medium": [],
        "low": []
    },
    "hypotheses": [
        {
            "id": "H1",
            "statement": "P starvation limits PFT#10 growth",
            "mechanism": "ECA_Competition",
            "evidence_for": ["Low P uptake (1.3% of PFT#9)", "High P stress (0.92)"],
            "evidence_against": ["N may be co-limiting"],
            "confidence": 0.85
        }
    ],
    "root_causes": [
        {
            "rank": 1,
            "cause": "Phosphorus starvation",
            "mechanism": "ECA_Competition",
            "confidence": 0.85,
            "affected_targets": ["froot_pft10", "leaf_pft10", "AGB_pft10"]
        }
    ],
    "conceptual_model": "ASCII diagram string",
    "key_insights": [
        "Triple Bottleneck Pattern: P + light + allocation",
        "Allocation Paradox Risk: vmax_p alone may backfire"
    ],
    "cross_pft_conflicts": [
        "PFT#9 vs PFT#10 P competition"
    ],
    "parameter_recommendations": [
        {
            "parameter": "fates_cnp_vmax_p",
            "pft": 10,
            "current_issue": "Low P uptake capacity",
            "suggested_direction": "increase",
            "priority": 1,
            "caution": "May trigger PID reallocation"
        }
    ],
    "confidence": 0.85,
    "reasoning": "Summary of diagnosis logic"
}
```

---

## Quality Checklist

Before finalizing diagnosis:
- [ ] All failing targets quantified with observed vs simulated
- [ ] At least 4 hypotheses proposed before analysis
- [ ] Each hypothesis has evidence for AND against
- [ ] Conceptual model shows causal chain
- [ ] Root causes ranked by confidence and evidence
- [ ] Key insights are numbered and actionable
- [ ] Recommendations include specific parameters
- [ ] Cross-PFT conflicts identified if present
- [ ] JSON output is valid and parseable
