# Phase 4: Hypothesis Generation Template

This template defines the structure for hypothesis generation and experiment design in Phase 4.

---

## Overview

Phase 4 transforms diagnosis results into testable hypotheses and specific experiment designs. The AI should:
1. Generate named, memorable hypotheses
2. Design experiments with clear expected outcomes
3. Identify potential discoveries (paradoxes, traps, etc.)
4. Specify what WON'T work and why

---

## Required Sections

### 1. Hypothesis Summary Table

Overview of all hypotheses being proposed:

| ID | Name | Mechanism | Key Parameter | Expected Improvement | Confidence |
|----|------|-----------|---------------|---------------------|------------|
| H1 | Root Ratio Correction | PID_Controller | fates_cnp_pid_kp | +30% froot | 0.75 |
| H2 | P Unlock | ECA_Competition | fates_cnp_vmax_p | +25% all pools | 0.70 |
| H3 | Storage Buffer | Storage_Allocation | fates_cnp_phos_store_ratio | +15% leaf | 0.60 |

### 2. Detailed Hypothesis Structure

For each hypothesis, provide full detail:

#### H1: Root Ratio Correction

**Statement:** "Reducing PID Kp from 0.5 to 0.3 for PFT#10 will allow the model to reach target L:FR ratio without overshooting"

**Mechanism (ASCII):**
```
Current Behavior (Kp=0.5):
┌─────────────────────────────────────────────────────────┐
│  P Stress Detected                                       │
│         │                                               │
│         ▼                                               │
│  PID Response: ↑ Root Allocation                        │
│         │                                               │
│         ▼  (Kp=0.5: aggressive response)                │
│  Massive root investment (70% of C)                     │
│         │                                               │
│         ▼                                               │
│  Leaf starved → GPP drops → LESS P uptake total         │
│         │                                               │
│         ▼                                               │
│  Even MORE P stress → Positive feedback loop            │
└─────────────────────────────────────────────────────────┘

Proposed Behavior (Kp=0.3):
┌─────────────────────────────────────────────────────────┐
│  P Stress Detected                                       │
│         │                                               │
│         ▼                                               │
│  PID Response: Moderate ↑ Root Allocation               │
│         │                                               │
│         ▼  (Kp=0.3: gentler response)                   │
│  Balanced allocation (50% root, 50% leaf)               │
│         │                                               │
│         ▼                                               │
│  Leaf maintained → GPP stable → P uptake improves       │
│         │                                               │
│         ▼                                               │
│  Gradual approach to equilibrium                        │
└─────────────────────────────────────────────────────────┘
```

**Parameters to Modify:**
```yaml
parameters:
  - name: fates_cnp_pid_kp
    pft: 10
    current: 0.5
    proposed: 0.3
    rationale: "Reduce PID aggressiveness to prevent allocation overshoot"
    bounds: [0.1, 1.0]
    sensitivity_rank: 3  # From Morris analysis
```

**Expected vs Test Strategy:**
```
┌─────────────────────────────────────────────────────────┐
│  EXPECTED OUTCOME                                        │
│  ────────────────                                        │
│  • froot_pft10: 45 → 80 g/m² (+77%)                    │
│  • leaf_pft10: 31 → 55 g/m² (+77%)                     │
│  • L:FR ratio: 0.69 → 0.69 (maintained)                │
│  • No degradation to PFT#7, PFT#9                       │
│                                                         │
│  TEST STRATEGY                                          │
│  ─────────────                                          │
│  Step 1: Run single experiment with Kp=0.3              │
│  Step 2: If successful, verify no cross-PFT impacts     │
│  Step 3: If partial, try Kp=0.2 and Kp=0.4             │
│                                                         │
│  SUCCESS CRITERIA                                       │
│  ────────────────                                       │
│  ✓ froot_pft10 error reduced by >25%                   │
│  ✓ No PFT#7 or PFT#9 degradation >5%                   │
│  ✓ L:FR ratio stays within 0.5-0.9 range               │
└─────────────────────────────────────────────────────────┘
```

**Risk Assessment:**
- LOW RISK: PFT-specific parameter, no cross-PFT effects
- MEDIUM RISK: May need to tune in conjunction with storage parameters
- KNOWN FAILURE: Kp > 0.7 causes oscillations (from memory)

### 3. Experiment Design

Specify exact experiments to run:

```yaml
experiments:
  - id: EXP_001
    name: "Kp Reduction Test"
    hypothesis_id: H1
    type: single_parameter
    base_case: 3930  # Best from Phase 2
    modifications:
      - parameter: fates_cnp_pid_kp
        pft: 10
        old_value: 0.5
        new_value: 0.3
    expected_results:
      froot_pft10: 80.0
      leaf_pft10: 55.0
      cost_reduction: 0.25
    success_threshold: 0.20
    priority: 1

  - id: EXP_002
    name: "P Uptake Enhancement"
    hypothesis_id: H2
    type: multi_parameter
    base_case: 3930
    modifications:
      - parameter: fates_cnp_vmax_p
        pft: 10
        old_value: 1.85e-9
        new_value: 3.7e-9  # 2x current
      - parameter: fates_cnp_eca_alpha_ptase
        pft: 10
        old_value: 0.5
        new_value: 0.7
    expected_results:
      froot_pft10: 90.0
      leaf_pft10: 60.0
      p_uptake_increase: 1.5  # 50% increase
    success_threshold: 0.25
    priority: 2
```

### 4. Potential Discoveries to Watch For

Name and describe potential discoveries:

#### Allocation Paradox
```
DEFINITION: When increasing nutrient uptake capacity DECREASES total uptake

MECHANISM:
↑ vmax_p → ↑ P uptake rate → ↓ P stress signal
         → PID reduces root allocation
         → Less root biomass → LESS total P uptake

SIGNATURE: Look for cases where:
- vmax_p increased but P uptake decreased
- Root allocation % dropped significantly
- P stress decreased but leaf/froot ratio changed

IF OBSERVED: Record as discovery, adjust strategy to include storage buffer
```

#### Mortality Trap
```
DEFINITION: When improved allocation triggers increased mortality

MECHANISM:
Better allocation → Higher biomass → Exceeds carbon balance threshold
                 → Carbon starvation mortality activated
                 → Biomass drops despite "better" parameters

SIGNATURE:
- Biomass initially increases then crashes
- FATES_MORTALITY_CANOPY spikes
- Maintenance respiration > GPP

IF OBSERVED: Need to adjust mortality thresholds or growth rate limits
```

### 5. What WON'T Work (and Why)

Critical section based on memory and reasoning:

```yaml
failed_approaches:
  - approach: "Simply increasing vmax_p without other changes"
    why_fails: "Triggers Allocation Paradox - PID reduces root allocation"
    evidence: "Observed in Cases 2145, 3892 (from Phase 2)"
    alternative: "Combine with storage buffer or PID reduction"

  - approach: "Reducing PFT#9 parameters to reduce competition"
    why_fails: "PFT#9 validation targets also need to be met"
    evidence: "Cross-PFT conflict documented in diagnosis"
    alternative: "Focus on PFT#10-specific parameters only"

  - approach: "Increasing turnover rate to boost fine root"
    why_fails: "Higher turnover means more C cost, worsens C balance"
    evidence: "Known FATES behavior from knowledge base"
    alternative: "Reduce turnover if anything, not increase"
```

### 6. What MIGHT Work (Speculative)

Lower-confidence ideas for backup:

```yaml
speculative_approaches:
  - approach: "Modify phosphatase production rate"
    mechanism: "Organic P mineralization in rhizosphere"
    confidence: 0.4
    rationale: "May bypass direct P competition with PFT#9"
    risk: "Less well understood in FATES, may have unintended effects"

  - approach: "Seasonal phenology adjustment"
    mechanism: "Shift PFT#10 growth timing relative to PFT#9"
    confidence: 0.3
    rationale: "Temporal niche separation could reduce competition"
    risk: "Phenology parameters affect many outputs"
```

---

## JSON Output Schema

The `reasoning.generate_hypothesis()` method should return:

```json
{
    "hypotheses": [
        {
            "id": "H1",
            "name": "Root Ratio Correction",
            "statement": "Reducing PID Kp will allow equilibrium approach",
            "mechanism": "PID_Controller",
            "mechanism_diagram": "ASCII diagram string",
            "parameters": [
                {
                    "name": "fates_cnp_pid_kp",
                    "pft": 10,
                    "current": 0.5,
                    "proposed": 0.3,
                    "rationale": "Reduce overshoot",
                    "bounds": [0.1, 1.0],
                    "sensitivity_rank": 3
                }
            ],
            "expected_outcomes": {
                "froot_pft10": 80.0,
                "leaf_pft10": 55.0
            },
            "success_criteria": {
                "froot_error_reduction": ">25%",
                "no_cross_pft_degradation": true
            },
            "confidence": 0.75,
            "risk_level": "low"
        }
    ],
    "experiments": [
        {
            "id": "EXP_001",
            "hypothesis_id": "H1",
            "name": "Kp Reduction Test",
            "type": "single_parameter",
            "base_case": 3930,
            "modifications": [...],
            "expected_results": {...},
            "success_threshold": 0.20,
            "priority": 1
        }
    ],
    "potential_discoveries": [
        {
            "name": "Allocation Paradox",
            "definition": "Increasing uptake capacity decreases total uptake",
            "signature": "vmax_p up but P uptake down",
            "action_if_observed": "Add storage buffer"
        }
    ],
    "wont_work": [
        {
            "approach": "Simply increasing vmax_p",
            "why_fails": "Allocation Paradox",
            "alternative": "Combine with storage buffer"
        }
    ],
    "might_work": [
        {
            "approach": "Phosphatase production adjustment",
            "confidence": 0.4,
            "risk": "Less understood"
        }
    ],
    "design_type": "cumulative",
    "overall_confidence": 0.70
}
```

---

## Experiment Design Guidelines

### Cumulative vs Factorial Design

**Use CUMULATIVE when:**
- Mechanisms are sequential (A → B → C)
- You want to identify which parameter has most impact
- Limited computational budget

```
Cumulative Design:
EXP1: Parameter A only
EXP2: A + B
EXP3: A + B + C
→ Can identify: A contribution, B additional contribution, C additional
```

**Use FACTORIAL when:**
- Parameters may interact (P × N synergy)
- Non-linear effects suspected
- Need to understand interaction effects

```
Factorial Design (2 parameters, 2 levels):
EXP1: A_low, B_low (baseline)
EXP2: A_high, B_low
EXP3: A_low, B_high
EXP4: A_high, B_high
→ Can identify: A main effect, B main effect, A×B interaction
```

### Parameter Selection Priority

1. **High Morris rank** - Most influential on target
2. **PFT-specific** - Avoid cross-PFT conflicts
3. **Mechanistically linked** - Based on diagnosis causal chain
4. **Not previously failed** - Check memory for failed approaches

---

## Quality Checklist

Before finalizing hypotheses:
- [ ] Each hypothesis has a memorable name
- [ ] Mechanism explained with ASCII diagram
- [ ] Parameters include current/proposed/rationale/bounds
- [ ] Expected outcomes are quantitative
- [ ] Success criteria are measurable
- [ ] Risk assessment included
- [ ] Potential discoveries named and described
- [ ] "Won't work" section populated from memory
- [ ] Design type (cumulative/factorial) justified
- [ ] JSON output is valid and parseable
