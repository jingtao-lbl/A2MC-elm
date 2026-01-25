# [Descriptive Title]: Diagnostic Findings & Analysis

**Date:** [YYYY-MM-DD]
**Session:** [Brief description of what's being diagnosed]
**Cases Analyzed:** [List of cases/experiments analyzed]
**Working Directory:** [Path to relevant data/scripts]

---

## Executive Summary

**Problem:** [One-sentence description of the issue being diagnosed]

**Root Cause Identified:** [Named finding, e.g., "triple bottleneck", "allocation paradox"]

**Critical Discovery:** [Key unexpected finding with mechanistic explanation]

**Recommended Strategy:** [Actionable next steps]

---

## Background: The Journey to Diagnosis

### Initial Situation

**Status as of [date]:**
- [Number] total simulation cases
- Case [X] ranks #[N] overall (Metric = value)
- Satisfies [N]/[M] targets but [key failure description]
- Competing hypotheses:
  - [Hypothesis 1 with source]
  - [Hypothesis 2 with source]

### Critical Parameter Discovery

**Finding:** [Key parameter insight]

**Implication:**
- [Consequence 1]
- [Consequence 2]
- **Conclusion:** [Bottom line]

### User-Initiated Tests (if applicable)

**Test1 ([case name]):**
- Parameter changes: [list]
- **Result:** [metrics]
- **Interpretation:** [what it means]

**Test2 ([case name]):**
- Parameter changes: [list]
- **Result:** [metrics]
- **Interpretation:** [what it means]

---

## Diagnostic Script Development

### Script: `[script_name].py`

**Purpose:** [What the script tests/analyzes]

**Location:** `[path]`

**Data sources:**
- [Data file 1 with path]
- [Data file 2 with path]

**Key calculations:**
- [Calculation 1]
- [Calculation 2]

---

## Diagnostic Results

### Hypothesis 1: [Name] - **[CONFIRMED/REJECTED/PARTIAL]**

#### Key Findings:

**[Case/Scenario 1]:**
```
[Key metrics in formatted block]
```

**[Case/Scenario 2]:**
```
[Key metrics in formatted block]
```

**Interpretation:**
- [Bullet 1]
- [Bullet 2]
- **Conclusion:** [Bottom line for this hypothesis]

---

### Hypothesis 2: [Name] - **[CONFIRMED/REJECTED/PARTIAL]**

#### Quantitative Evidence:

| Variable | Case A | Case B | Δ | Interpretation |
|----------|--------|--------|---|----------------|
| [var1] | [val] | [val] | [%] | [meaning] |
| [var2] | [val] | [val] | [%] | [meaning] |

**Key insight:** [Main finding from this analysis]

---

### Hypothesis 3: [Name] - **[CONFIRMED/REJECTED/PARTIAL]**

[Continue pattern...]

---

## Conceptual Model

### [Named Mechanism, e.g., "Triple Bottleneck"]

```
[ASCII diagram showing causal chain]

         ┌─────────────┐
         │  Factor A   │
         └──────┬──────┘
                │
                ▼
         ┌─────────────┐
         │  Factor B   │
         └──────┬──────┘
                │
                ▼
         ┌─────────────┐
         │  OUTCOME    │
         └─────────────┘
```

**Explanation:**
1. [Step 1 of mechanism]
2. [Step 2 of mechanism]
3. [Step 3 of mechanism]

---

## Key Insights (Numbered)

1. **[Insight Name]:** [Description with evidence]

2. **[Insight Name]:** [Description with evidence]

3. **[Insight Name]:** [Description with evidence]

---

## Parameter Recommendations

| Parameter | Current | Proposed | Rationale | Priority |
|-----------|---------|----------|-----------|----------|
| [param1] | [val] | [val] | [why] | 1 |
| [param2] | [val] | [val] | [why] | 2 |

---

## Questions for Further Investigation

1. **[Question about mechanism]**
   - [Why this matters]

2. **[Question about parameters]**
   - [What needs to be tested]

3. **[Question about assumptions]**
   - [What might be wrong]

---

## Scripts Created

| Script | Purpose | Location |
|--------|---------|----------|
| `[script1].py` | [purpose] | [path] |
| `[script2].py` | [purpose] | [path] |

---

## Output Figures

```
[path to figures]/
├── [figure1].png  # [description]
├── [figure2].png  # [description]
└── [figure3].png  # [description]
```

---

## Related Memory Files

- `[date]_[topic].md` - [relationship]
- `[date]_[topic].md` - [relationship]

---

**Next Steps:** [Clear action items for the next session]
