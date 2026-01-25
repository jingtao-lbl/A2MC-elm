# Phase 6: Refinement Template

This template defines the structure for experiment evaluation and knowledge extraction in Phase 6.

---

## Overview

Phase 6 evaluates experiment results, extracts lessons, and decides on next steps. The AI should:
1. Compare expected vs actual outcomes honestly
2. Categorize results by mechanism and parameter type
3. Extract generalizable discoveries
4. Determine convergence status

---

## Required Sections

### 1. Experiment Results Summary

High-level overview of all experiments:

| Exp ID | Hypothesis | Expected | Actual | Status | Key Finding |
|--------|------------|----------|--------|--------|-------------|
| EXP_001 | H1 (Kp Reduction) | +77% froot | +52% froot | PARTIAL | Helps but insufficient alone |
| EXP_002 | H2 (P Unlock) | +100% froot | -12% froot | REJECTED | Allocation Paradox confirmed |
| EXP_003 | H3 (Storage) | +15% leaf | +23% leaf | CONFIRMED | Buffers stress effectively |

### 2. Detailed Experiment Analysis

For each experiment:

#### EXP_001: Kp Reduction Test

**Hypothesis:** "Reducing PID Kp from 0.5 to 0.3 will improve froot by +77%"

**Expected vs Actual:**
```
┌─────────────────────────────────────────────────────────┐
│  EXPECTED                    │  ACTUAL                  │
│  ────────                    │  ──────                  │
│  froot_pft10: 45 → 80 (+77%) │  froot_pft10: 45 → 68    │
│  leaf_pft10:  31 → 55 (+77%) │  leaf_pft10:  31 → 46    │
│  cost:       0.342 → 0.257   │  cost:       0.342 → 0.285│
│                              │                          │
│  STATUS: PARTIAL SUCCESS (52% vs 77% expected)         │
└─────────────────────────────────────────────────────────┘
```

**Why Partial?**
- Hypothesis mechanism was correct (PID overshoot was a problem)
- But magnitude was overestimated
- Additional limiting factors remain (P still limiting)

**Cross-PFT Impact:**
| PFT | leaf Δ | froot Δ | Status |
|-----|--------|---------|--------|
| 7 | +2% | +1% | OK |
| 9 | -1% | -2% | OK |
| 10 | +48% | +52% | IMPROVED |

---

#### EXP_002: P Uptake Enhancement

**Hypothesis:** "Doubling vmax_p will increase froot by +100%"

**Expected vs Actual:**
```
┌─────────────────────────────────────────────────────────┐
│  EXPECTED                    │  ACTUAL                  │
│  ────────                    │  ──────                  │
│  froot_pft10: 45 → 90 (+100%)│  froot_pft10: 45 → 40 ↓ │
│  P_uptake:   +50%            │  P_uptake:   +8% only    │
│                              │                          │
│  STATUS: REJECTED - ALLOCATION PARADOX CONFIRMED       │
│                                                         │
│  ⚠️  CRITICAL DISCOVERY                                │
│  Higher vmax_p → Lower P stress signal                 │
│            → PID reduced root allocation               │
│            → Less root biomass → Less total P uptake   │
└─────────────────────────────────────────────────────────┘
```

**Discovery Name:** **ALLOCATION PARADOX**

**Mechanism Diagram:**
```
Traditional Expectation:
↑ vmax_p → ↑ P uptake rate → ↑ Total P → ↑ Growth
                              (Wrong!)

Actual FATES Behavior:
↑ vmax_p → ↑ P uptake RATE per root
        → P stress signal DECREASES (less stress)
        → PID controller: "Less stress? Reduce root investment"
        → ↓ Root allocation %
        → ↓ Total root biomass
        → Net effect: ↓ Total P uptake capacity
        → ↓ Growth despite higher vmax_p

The paradox: Improving uptake EFFICIENCY reduces uptake CAPACITY
```

---

### 2b. Multi-Phase Time Series Analysis

When analyzing long simulations, track variables across phases:

| Phase | Years | P Uptake/Demand | VEGC (g/m²) | Key Event |
|-------|-------|-----------------|-------------|-----------|
| ADSP | 1-200 | 23% | Building | Accelerated decomp |
| RGSP | 201-400 | 0.85% | Stable | Nutrient stress develops |
| TRANS | 1901-1960 | 0.08% | 3,104 | Chronic limitation |
| **Drought** | 1963-1968 | 0.08% | **226** | Vegetation collapse |
| Recovery | 1970-2019 | varies | 622 | Gradual recovery |

**Pattern: "Perfect Storm" identification:**
```
1. Identify the crash point (e.g., 1963-1968)
2. Look for multiple simultaneous stressors
3. Track which stressor dominated (mortality components)
4. Follow the cascade effects (litter accumulation, etc.)
```

### 2c. Cross-PFT Comparison During Events

When one PFT crashes while others survive:

| PFT | Pre-Event GPP | Event GPP | Post-Event | Outcome |
|-----|---------------|-----------|------------|---------|
| PFT7 (Evergreen) | 959 | **19** | 45 | 98% died |
| PFT9 (Deciduous) | 359 | 423 | 380 | Survived |
| PFT10 (Graminoid) | 28 | 174 | 210 | Thrived |

**Differential response analysis:**
- Why did PFT7 die while PFT9 survived?
- What parameter differences explain the outcomes?
- Are there trait-based explanations?

**Key insight: Phenology-Nutrient Uptake Interaction**
- **PFT7 (Evergreen)**: Persistent but LOW nutrient uptake rates year-round → cannot build reserves during favorable periods → vulnerable to chronic stress
- **PFT9 (Deciduous) & PFT10 (Graminoid)**: HIGH uptake rates during spring flushing → can build nutrient reserves quickly → more resilient to drought

This phenology-mediated nutrient acquisition strategy explains why evergreen shrubs are most vulnerable to combined nutrient + water stress.

---

### 3. Parameter Category Analysis

Group results by parameter type:

#### Allocation Parameters
| Parameter | Experiments | Direction | Outcome | Generalizable? |
|-----------|-------------|-----------|---------|----------------|
| fates_cnp_pid_kp | EXP_001 | ↓ | Helps | YES - reduces overshoot |
| fates_cnp_pid_ki | EXP_007 | ↓ | No effect | No - already low |

**Key Insight:** PID Kp reduction is a reliable strategy but not sufficient alone.

#### Nutrient Uptake Parameters
| Parameter | Experiments | Direction | Outcome | Generalizable? |
|-----------|-------------|-----------|---------|----------------|
| fates_cnp_vmax_p | EXP_002 | ↑ | BACKFIRES | YES - Allocation Paradox |
| fates_cnp_vmax_nh4 | EXP_004 | ↑ | Minor help | Depends on N availability |

**Key Insight:** Cannot simply increase uptake capacity due to feedback with allocation.

#### Storage Parameters
| Parameter | Experiments | Direction | Outcome | Generalizable? |
|-----------|-------------|-----------|---------|----------------|
| fates_cnp_phos_store_ratio | EXP_003 | ↑ | Works | YES - buffers stress |
| fates_cnp_nitr_store_ratio | EXP_005 | ↑ | Minor | Only if N limiting |

**Key Insight:** Storage parameters are underutilized - can buffer stress without triggering PID.

#### Mortality Parameters
| Parameter | Experiments | Direction | Outcome | Generalizable? |
|-----------|-------------|-----------|---------|----------------|
| fates_mort_scalar_cstarvation | EXP_008 | ↓ | Helps short-term | NO - masks real problem |

**Key Insight:** Mortality tuning is a band-aid, not a solution.

---

### 4. Mechanism-Based Synthesis

#### What We Learned About PID Controller
```
BEFORE this iteration:
- Assumed PID Kp simply controls allocation speed
- Didn't understand feedback with stress signals

AFTER this iteration:
- PID creates feedback loop with stress signals
- High Kp + high uptake capacity = instability
- Need to tune Kp AND uptake together, not separately

RECOMMENDATION:
- Always test PID parameters in combination with uptake parameters
- Lower Kp (0.2-0.4) works better than high Kp for stressed PFTs
```

#### What We Learned About ECA Competition
```
BEFORE:
- Assumed higher vmax always wins competition

AFTER:
- Competition is indirect via allocation changes
- PFT with higher vmax may LOSE if PID reduces its roots
- Non-linear dynamics make simple predictions fail

RECOMMENDATION:
- Test vmax changes with storage buffer
- Consider relative vmax ratios between PFTs, not absolute values
```

---

### 5. Critical Insights (Numbered)

1. **Allocation Paradox is REAL**: Higher uptake efficiency → lower uptake capacity via PID feedback. This fundamentally changes calibration strategy.

2. **Storage Parameters are KEY**: They buffer stress signals without triggering PID, providing a "safe" way to improve nutrient status.

3. **PID Kp is Necessary but Insufficient**: Reducing Kp helps (~50% improvement) but cannot reach targets alone.

4. **Cross-PFT Effects are Minimal**: PFT-specific parameters can be tuned independently (good news for calibration).

5. **Combination Strategy Required**: No single parameter fix is sufficient. Need: Lower Kp + Higher storage + Moderate vmax increase.

---

### 6. Fundamental Constraints Identified

```
┌─────────────────────────────────────────────────────────┐
│           FUNDAMENTAL CONSTRAINTS FOR PFT#10            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. ALLOCATION PARADOX CONSTRAINT                       │
│     Cannot increase vmax_p > 2x without storage buffer  │
│                                                         │
│  2. PID STABILITY CONSTRAINT                            │
│     Kp must be < 0.4 for PFT#10 under P stress         │
│                                                         │
│  3. COMPETITION CONSTRAINT                              │
│     Cannot reduce PFT#9 parameters (also need targets)  │
│                                                         │
│  4. MORTALITY THRESHOLD CONSTRAINT                      │
│     Cannot let storage drop below 5% (triggers death)   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

### 7. Knowledge Updates

#### Discoveries to Add
```yaml
discoveries:
  - name: "Allocation Paradox"
    description: "Higher uptake efficiency can reduce total uptake via PID feedback"
    mechanism: "vmax_p ↑ → stress ↓ → PID ↓ root alloc → total uptake ↓"
    affects: ["froot_pft10", "leaf_pft10", "P_uptake"]
    confidence: 0.95
    evidence: "EXP_002 showed +8% uptake rate but -12% biomass"

  - name: "Storage Buffer Strategy"
    description: "Increasing storage ratios buffers stress without PID response"
    mechanism: "Higher storage target → gradual stress reduction → stable allocation"
    affects: ["leaf", "storage", "stress_signals"]
    confidence: 0.85
    evidence: "EXP_003 showed +23% leaf with minimal side effects"
```

#### Failed Approaches to Record
```yaml
failed_approaches:
  - approach: "Doubling vmax_p alone"
    experiment_id: "EXP_002"
    why_failed: "Triggers Allocation Paradox"
    severity: "high"
    alternatives: ["Combine with storage buffer", "Reduce PID Kp first"]

  - approach: "High PID Kp (>0.5) for stressed PFTs"
    experiment_id: "EXP_001 baseline"
    why_failed: "Causes allocation oscillations under stress"
    severity: "medium"
    alternatives: ["Use Kp 0.2-0.4 for stressed PFTs"]
```

#### Parameter Insights to Record
```yaml
parameter_insights:
  - parameter: "fates_cnp_pid_kp"
    pft: 10
    optimal_range: [0.2, 0.4]
    sensitivity: "high"
    interactions: ["Must tune with vmax_p, storage_ratio"]
    notes: "Lower values prevent overshoot under nutrient stress"

  - parameter: "fates_cnp_phos_store_ratio"
    pft: 10
    optimal_range: [1.5, 3.0]
    sensitivity: "medium"
    interactions: ["Works independently of other parameters"]
    notes: "Safe parameter to increase - no negative feedbacks observed"
```

---

### 8. Convergence Assessment

```
Current Status: IMPROVING

Progress:
- Best cost: 0.342 → 0.285 (17% improvement)
- Targets in tolerance: 4/9 → 5/9
- Critical target (froot_pft10): -74% error → -48% error

Convergence Criteria:
┌─────────────────────────────────────────────────┐
│ Criterion              │ Target  │ Current │ Met │
├────────────────────────┼─────────┼─────────┼─────┤
│ Overall cost           │ < 0.20  │ 0.285   │ ✗   │
│ All targets < 30% err  │ 9/9     │ 6/9     │ ✗   │
│ No critical failures   │ 0       │ 1       │ ✗   │
│ Stable across iter     │ yes     │ N/A     │ -   │
└─────────────────────────────────────────────────┘

RECOMMENDATION: Continue to next iteration with combined strategy
```

---

### 9. Next Iteration Strategy

```yaml
next_iteration:
  focus: "Combined Kp + Storage + Moderate vmax approach"

  priority_experiments:
    - id: "EXP_COMBO_001"
      description: "Kp=0.3 + storage_ratio=2.0 + vmax_p=1.5x"
      expected_improvement: "+40% froot (to reach ~63 g/m²)"
      confidence: 0.75

    - id: "EXP_COMBO_002"
      description: "Kp=0.25 + storage_ratio=2.5 (no vmax change)"
      expected_improvement: "+30% froot (safer approach)"
      confidence: 0.70

  parameters_to_hold_fixed:
    - "fates_turnover_leaf" (already optimized in Phase 2)
    - "fates_mort_scalar_cstarvation" (band-aid, not solution)

  new_hypotheses_to_explore:
    - "Phenology timing adjustment for temporal niche"
    - "Root distribution parameter effects on P access"
```

---

## JSON Output Schema

The `reasoning.interpret_results()` and `extract_lesson()` methods should return:

```json
{
    "experiment_results": [
        {
            "id": "EXP_001",
            "hypothesis_id": "H1",
            "status": "partial",
            "expected": {"froot_pft10": 80.0},
            "actual": {"froot_pft10": 68.0},
            "improvement_pct": 52,
            "cross_pft_ok": true,
            "key_finding": "Helps but insufficient alone"
        }
    ],
    "discoveries": [
        {
            "name": "Allocation Paradox",
            "description": "Higher uptake efficiency reduces total uptake via PID",
            "mechanism": "vmax_p ↑ → stress ↓ → PID ↓ root → uptake ↓",
            "affects": ["froot_pft10", "P_uptake"],
            "confidence": 0.95,
            "evidence": "EXP_002"
        }
    ],
    "failed_approaches": [
        {
            "approach": "Doubling vmax_p alone",
            "experiment_id": "EXP_002",
            "why_failed": "Allocation Paradox",
            "severity": "high",
            "alternatives": ["Combine with storage buffer"]
        }
    ],
    "parameter_insights": [
        {
            "parameter": "fates_cnp_pid_kp",
            "pft": 10,
            "optimal_range": [0.2, 0.4],
            "interactions": ["vmax_p", "storage_ratio"],
            "notes": "Lower prevents overshoot"
        }
    ],
    "fundamental_constraints": [
        "Cannot increase vmax_p > 2x without storage buffer",
        "Kp must be < 0.4 for stressed PFTs"
    ],
    "convergence": {
        "status": "improving",
        "cost_improvement_pct": 17,
        "targets_met": "5/9",
        "recommendation": "continue"
    },
    "next_iteration": {
        "focus": "Combined Kp + Storage + vmax approach",
        "priority_experiments": ["EXP_COMBO_001", "EXP_COMBO_002"],
        "parameters_to_hold": ["turnover_leaf"]
    }
}
```

---

## Quality Checklist

Before finalizing refinement:
- [ ] All experiments evaluated with expected vs actual
- [ ] Status (confirmed/partial/rejected) assigned to each
- [ ] Parameter categories analyzed systematically
- [ ] Mechanism understanding updated (before/after)
- [ ] Critical insights numbered and actionable
- [ ] Fundamental constraints identified
- [ ] Discoveries named with memorable names
- [ ] Failed approaches recorded with alternatives
- [ ] Convergence status determined
- [ ] Next iteration strategy specified
- [ ] JSON output is valid and parseable
