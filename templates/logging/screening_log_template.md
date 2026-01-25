# [Site Name] Ensemble Screening: Analysis & Findings

**Date:** [YYYY-MM-DD]
**Session:** Screening of [N]-member Morris/Sobol ensemble
**Ensemble Size:** [Total cases] | **Completed:** [N completed]
**Working Directory:** [Path to analysis scripts]

---

## Executive Summary

**Ensemble Status:** [N]/[M] cases completed ([X]% success rate)

**Best-Performing Set:** Case #[ID] with RMSRE = [value]

**Overall Simulation Quality:**
| PFT | Quality | Median Error | Cases Within Uncertainty |
|-----|---------|--------------|-------------------------|
| [PFT7] | [POOR/GOOD/etc] | [±X%] | [N] ([%]) |
| [PFT9] | [POOR/GOOD/etc] | [±X%] | [N] ([%]) |
| [PFT10] | [POOR/GOOD/etc] | [±X%] | [N] ([%]) |

**Key Finding:** [One-sentence summary of most important pattern]

**Recommended Focus for Diagnosis:** [Which PFT/targets need investigation]

---

## Ensemble Completion Status

### Summary Statistics

| Metric | Value |
|--------|-------|
| Total ensemble size | [N] |
| Successfully completed | [N] |
| Completion rate | [X]% |
| Cases with errors | [N] |
| Extraction quality | [Good/Issues] |

### Data Quality Notes

- [Any extraction issues]
- [Missing variables or timesteps]
- [Cases excluded from analysis and why]

---

## PFT-by-PFT Performance Analysis

### PFT#[7]: [Evergreen shrub]

**Overall Quality:** [POOR/MODERATE/GOOD/EXCELLENT]

| Target | Observed | Ensemble Mean | Median Error | Bias |
|--------|----------|---------------|--------------|------|
| Leaf | [X] g/m² | [Y] g/m² | [±Z%] | [UNDER/OVER] |
| Froot | [X] g/m² | [Y] g/m² | [±Z%] | [UNDER/OVER] |
| AGB | [X] g/m² | [Y] g/m² | [±Z%] | [UNDER/OVER] |

**Pattern:** [Consistently low/high/variable]

**Initial Hypothesis:** [What might explain this pattern]

---

### PFT#[9]: [Deciduous shrub]

**Overall Quality:** [POOR/MODERATE/GOOD/EXCELLENT]

| Target | Observed | Ensemble Mean | Median Error | Bias |
|--------|----------|---------------|--------------|------|
| Leaf | [X] g/m² | [Y] g/m² | [±Z%] | [UNDER/OVER] |
| Froot | [X] g/m² | [Y] g/m² | [±Z%] | [UNDER/OVER] |
| AGB | [X] g/m² | [Y] g/m² | [±Z%] | [UNDER/OVER] |

**Pattern:** [Consistently low/high/variable]

**Initial Hypothesis:** [What might explain this pattern]

---

### PFT#[10]: [Arctic graminoid]

**Overall Quality:** [POOR/MODERATE/GOOD/EXCELLENT]

| Target | Observed | Ensemble Mean | Median Error | Bias |
|--------|----------|---------------|--------------|------|
| Leaf | [X] g/m² | [Y] g/m² | [±Z%] | [UNDER/OVER] |
| Froot | [X] g/m² | [Y] g/m² | [±Z%] | [UNDER/OVER] |
| AGB | [X] g/m² | [Y] g/m² | [±Z%] | [UNDER/OVER] |

**Pattern:** [Consistently low/high/variable]

**Initial Hypothesis:** [What might explain this pattern]

---

## Bias Pattern Visualization

```
                        SIMULATION BIAS BY TARGET

                    Underest    Target    Overest
                    <-50%  -25%  0%  +25%  +50%>
                       |     |     |     |     |
leaf_pft7:        ████████░░░░░░░░░░░░░░░░░░░░░  [-X%]
leaf_pft9:        ░░░░░░░░░░░░░░░█████░░░░░░░░░░  [+X%]
leaf_pft10:       ██████████████░░░░░░░░░░░░░░░░  [-X%]
froot_pft7:       █████████░░░░░░░░░░░░░░░░░░░░░  [-X%]
froot_pft9:       ░░░░░░░░░░░░░░█░░░░░░░░░░░░░░░  [-X%]
froot_pft10:      ████████████████░░░░░░░░░░░░░░  [-X%] **WORST**
AGB_pft7:         ███████░░░░░░░░░░░░░░░░░░░░░░░  [-X%]
AGB_pft9:         ░░░░░░░░░░░░░░█░░░░░░░░░░░░░░░  [+X%]
AGB_pft10:        ██████████████░░░░░░░░░░░░░░░░  [-X%]

█ = Underestimation  ░ = On target/Overestimation
```

---

## Error Pattern Summary

### By PFT

| PFT | All Targets Pattern | Most Affected Pool | Primary Issue |
|-----|--------------------|--------------------|---------------|
| 7 | [Consistent under] | [Which] | [Hypothesis] |
| 9 | [Well simulated] | [N/A] | [None major] |
| 10 | [Severe under] | [Froot] | [Hypothesis] |

### By Biomass Pool

| Pool | Best Simulated PFT | Worst Simulated PFT | Pool-Specific Issue |
|------|-------------------|---------------------|---------------------|
| Leaf | [PFT#] | [PFT#] | [Issue or None] |
| Froot | [PFT#] | [PFT#] | [Issue or None] |
| AGB | [PFT#] | [PFT#] | [Issue or None] |

---

## Cross-PFT Trade-off Analysis

### Trade-off Identified: PFT#[X] vs PFT#[Y]

```
                    Trade-off Visualization

Case #XXXX:  PFT9 ●─────────────────○────────→ Good
             PFT10 ●──────○─────────────────→ Poor

Case #YYYY:  PFT9 ●────────────────────○───→ Excellent (overshoots)
             PFT10 ●────○─────────────────→ Worse

Case #ZZZZ:  PFT9 ●────────────○───────────→ Moderate
             PFT10 ●─────────○────────────→ Moderate (best balance)
```

**Trade-off Type:** [Competition-based / Allocation-based / Structural]

**Implication for Calibration:** [Can both be satisfied? Need multi-objective approach?]

---

## Edge Parameter Analysis

### Parameters at Upper Bound

| Parameter | PFT | Range | Top-10 Mean | % at Edge | Implication |
|-----------|-----|-------|-------------|-----------|-------------|
| [param1] | [N] | [min, max] | [value] | [X%] | [Wants higher values] |
| [param2] | [N] | [min, max] | [value] | [X%] | [Wants higher values] |

### Parameters at Lower Bound

| Parameter | PFT | Range | Top-10 Mean | % at Edge | Implication |
|-----------|-----|-------|-------------|-----------|-------------|
| [param3] | [N] | [min, max] | [value] | [X%] | [Default too high?] |

### Recommendation

- **Expand bounds:** [List parameters]
- **Keep current bounds:** [List parameters]

---

## Top Parameter Sets

### Top 10 by RMSRE

| Rank | Set ID | RMSRE | Targets Met | PFT7 Error | PFT9 Error | PFT10 Error |
|------|--------|-------|-------------|------------|------------|-------------|
| 1 | [ID] | [X] | [N]/9 | [±X%] | [±X%] | [±X%] |
| 2 | [ID] | [X] | [N]/9 | [±X%] | [±X%] | [±X%] |
| ... | | | | | | |
| 10 | [ID] | [X] | [N]/9 | [±X%] | [±X%] | [±X%] |

### Best Balanced Set: Case #[ID]

**Why selected:** [Lowest trade-off, best balance across PFTs]

**Key parameters:**
| Parameter | Value | Compared to Default |
|-----------|-------|---------------------|
| [key_param_1] | [X] | [Higher/Lower by Y%] |
| [key_param_2] | [X] | [Higher/Lower by Y%] |

---

## Initial Hypotheses for Diagnosis

### S1: [Hypothesis Name]

**Statement:** [PFT#10 is nutrient-limited due to ECA competition]

**Supporting Evidence from Screening:**
- [vmax_p at upper bound in top cases]
- [Consistent underestimation regardless of other parameters]
- [Trade-off with PFT#9 suggests shared resource]

**Priority:** HIGH

---

### S2: [Hypothesis Name]

**Statement:** [Description]

**Supporting Evidence from Screening:**
- [Evidence 1]
- [Evidence 2]

**Priority:** [HIGH/MEDIUM/LOW]

---

## Questions for Diagnosis Phase

1. **[Question about most critical issue]**
   - Why? [Brief justification]
   - What to check: [Variables, mechanisms]

2. **[Question about second issue]**
   - Why? [Brief justification]
   - What to check: [Variables, mechanisms]

3. **[Question about trade-offs]**
   - Why? [Brief justification]
   - What to check: [Variables, mechanisms]

---

## Scripts and Outputs

### Analysis Scripts

| Script | Purpose | Location |
|--------|---------|----------|
| [script1.py] | [Purpose] | [Path] |
| [script2.py] | [Purpose] | [Path] |

### Output Figures

| Figure | Description | Location |
|--------|-------------|----------|
| [fig1.png] | [What it shows] | [Path] |
| [fig2.png] | [What it shows] | [Path] |

### Data Files

| File | Description | Location |
|------|-------------|----------|
| [ranking.csv] | Ranked ensemble results | [Path] |
| [edge_params.csv] | Edge parameter analysis | [Path] |

---

## Handoff to Phase 3

### Priority Targets for Diagnosis

| Priority | Target | Issue | Recommended Focus |
|----------|--------|-------|-------------------|
| 1 | [froot_pft10] | -74% underest | Nutrient uptake, root allocation |
| 2 | [leaf_pft10] | -63% underest | GPP, light competition |
| 3 | [leaf_pft7] | -46% underest | Evergreen physiology |

### Key Questions Requiring Root Cause Analysis

1. Why does PFT#[10] show consistent underestimation?
2. Is there a fundamental trade-off between PFT#[9] and PFT#[10]?
3. Should parameter bounds be expanded for PFT#[10]?

### Preliminary Parameter Recommendations

| Parameter | PFT | Direction | Reason |
|-----------|-----|-----------|--------|
| [param1] | 10 | Increase | At upper bound in top cases |
| [param2] | 10 | Explore | May affect [mechanism] |

---

## Related Files

- **Ensemble design:** [Path to Morris/Sobol configuration]
- **Extraction outputs:** [Path to extracted data]
- **Previous screening:** [Path to prior screening if exists]
- **Validation targets:** [Path to targets file]
