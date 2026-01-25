# [Experiment Name]: [Brief Description]

**Date:** [YYYY-MM-DD]
**Hypothesis Tested:** [H1/H2/etc. from Phase 4]
**Base Case:** [Case number/name]
**Experiment Type:** [Cumulative/Factorial/Single Parameter]

---

## Executive Summary

**Hypothesis:** "[Testable statement from Phase 4]"

**Expected Outcome:** [What we predicted would happen]

**Actual Outcome:** [What actually happened]

**Status:** [CONFIRMED / PARTIAL / REJECTED]

**Key Discovery:** [Named finding if unexpected, e.g., "Allocation Paradox"]

---

## Experiment Design

### Parameters Modified

| Parameter | Base Value | Test Value | Rationale |
|-----------|------------|------------|-----------|
| [param1] | [val] | [val] | [why] |
| [param2] | [val] | [val] | [why] |

### Experiment Sequence (for Cumulative design)

| Exp | Parameters Changed | Building On |
|-----|-------------------|-------------|
| Exp1 | param1 only | Base case |
| Exp2 | param1 + param2 | Exp1 |
| Exp3 | param1 + param2 + param3 | Exp2 |

### Simulation Details

- **Spinup:** [Duration, e.g., "200-year ADSP + 200-year RGSP"]
- **Transient:** [Duration, e.g., "1901-2019 with historical forcing"]
- **Output variables:** [Key variables extracted]

---

## Expected vs Actual Results

### Target Comparison

| Target | Observed | Base Case | Experiment | Expected | Δ vs Expected |
|--------|----------|-----------|------------|----------|---------------|
| froot_pft10 | 174.2 | 45.3 | [val] | [val] | [%] |
| leaf_pft10 | 84.0 | 31.2 | [val] | [val] | [%] |

### EXPECTED:
```
┌─────────────────────────────────────────────────────────┐
│  Target        Base      Expected    Change             │
│  ──────        ────      ────────    ──────             │
│  froot_pft10   45.3      90.0        +99% (2×)          │
│  leaf_pft10    31.2      55.0        +76%               │
│  cost          0.342     0.200       -42%               │
└─────────────────────────────────────────────────────────┘
```

### ACTUAL:
```
┌─────────────────────────────────────────────────────────┐
│  Target        Base      Actual      Change             │
│  ──────        ────      ──────      ──────             │
│  froot_pft10   45.3      40.1        -12% ⚠️ OPPOSITE   │
│  leaf_pft10    31.2      28.5        -9%  ⚠️ OPPOSITE   │
│  cost          0.342     0.385       +13% ⚠️ WORSE      │
└─────────────────────────────────────────────────────────┘
```

---

## Discovery: [Named Finding]

### The "[Discovery Name]"

**Definition:** [What this phenomenon is]

**Mechanism:**
```
Traditional Expectation:
↑ [parameter] → ↑ [intermediate] → ↑ [outcome]
                    (WRONG!)

Actual Behavior:
↑ [parameter] → ↑ [intermediate A]
             → ↓ [intermediate B] (feedback)
             → Net: ↓ [outcome]
```

### Why This Happens

1. [Step 1 with mechanism]
2. [Step 2 with mechanism]
3. [Step 3 with mechanism]

**ASCII Diagram:**
```
┌─────────────────────────────────────────────────────────┐
│  [Parameter] Increase                                    │
│         │                                               │
│         ▼                                               │
│  [Direct Effect]                                        │
│         │                                               │
│         ├──────────────────┐                            │
│         │                  │                            │
│         ▼                  ▼                            │
│  [Expected Path]    [Feedback Path]                     │
│         │                  │                            │
│         ▼                  ▼                            │
│  [Intermediate]     [Counter-Effect]                    │
│         │                  │                            │
│         └────────┬─────────┘                            │
│                  │                                      │
│                  ▼                                      │
│         [Net Outcome: Opposite of Expected]             │
└─────────────────────────────────────────────────────────┘
```

---

## Cross-Validation

### Evidence Supporting This Discovery

| Source | Finding | Supports? |
|--------|---------|-----------|
| [Case X] | [observation] | Yes/No |
| [Literature] | [citation] | Yes/No |
| [Theory] | [prediction] | Yes/No |

### Conditions Under Which This Occurs

- **Necessary condition 1:** [e.g., "Nutrient stress must be present"]
- **Necessary condition 2:** [e.g., "PID must be responsive (Kp > 0.001)"]
- **Triggering condition:** [e.g., "Parameter increase > 2×"]

---

## What This Means

### What WON'T Work

| Approach | Why It Fails |
|----------|--------------|
| Simply increasing [param] | Triggers [feedback mechanism] |
| [Approach 2] | [Reason] |

### What MIGHT Work

| Approach | Mechanism | Confidence |
|----------|-----------|------------|
| Combine [param] with [buffer param] | [Why this avoids the feedback] | 0.7 |
| [Approach 2] | [Mechanism] | 0.5 |

---

## Implications for Calibration Strategy

1. **[Parameter] cannot be increased in isolation** - must be combined with [other parameter]

2. **The [feedback mechanism] creates a constraint** - any modification to [X] must account for [Y]

3. **[PFT type] may be fundamentally limited by [mechanism]** - consider structural model changes

---

## Questions Raised

1. **Does this [discovery] occur under all conditions?**
   - Need to test with [different scenario]

2. **Is this a FATES-specific behavior or physically realistic?**
   - Compare with observations/literature

3. **Can the feedback be avoided by [alternative approach]?**

---

## Data Files

### Input
```
[path]/
├── [input_file1.nc]  # Base case output
└── [input_file2.nc]  # Experiment output
```

### Output
```
[path]/
├── [analysis_figure.png]  # Comparison plot
└── [results_table.csv]    # Quantitative comparison
```

---

## Related Memory Files

- `[date]_[diagnosis].md` - Diagnosis that led to this hypothesis
- `[date]_[previous_test].md` - Related experiment

---

**Next Steps:**
1. [Action 1]
2. [Action 2]
3. [Action 3]
