# [Discovery Name]: [Descriptive Subtitle]

**Date:** [YYYY-MM-DD]
**Status:** [Analysis complete / In progress / Solutions to be discussed]
**Related Case:** [Case or experiment that revealed this]

---

## 1. Initial Question

**Why does [observed phenomenon] occur instead of [expected behavior]?**

Original hypothesis: [What we thought would happen]

Observed result: [What actually happened]

---

## 2. Data Files Analyzed

```
[base_path]/
├── [file1.nc]   # (Description, e.g., "Years 1-200, ADSP")
├── [file2.nc]   # (Description, e.g., "Years 201-400, RGSP")
└── [file3.nc]   # (Description, e.g., "Years 1901-2019, TRANS")
```

**Simulation phases (if applicable):**
- **ADSP (years 1-200):** [Description of this phase]
- **RGSP (years 201-400):** [Description of this phase]
- **TRANS (years 401+):** [Description of this phase]

---

## 3. Key Discovery #1: [Name]

**Initial misconception:** [What we thought was happening]

**Reality:** [What is actually happening]

### Evidence Table

| Variable | Initial | Phase 1 | Phase 2 | Final | Δ Total |
|----------|---------|---------|---------|-------|---------|
| [var1] | [val] | [val] | [val] | [val] | [val] |
| [var2] | [val] | [val] | [val] | [val] | [val] |
| **[key var]** | [val] | [val] | [val] | **[val]** | **[val]** |

**Critical finding:**
- [Bullet 1 with quantitative evidence]
- [Bullet 2 with quantitative evidence]
- [Bullet 3 - the key insight]

---

## 4. Key Discovery #2: [Name]

### Time Series Analysis

| Year/Time | [Var1] | [Var2] | Event |
|-----------|--------|--------|-------|
| [t1] | [val] | [val] | [description] |
| [t2] | [val] | [val] | [description] |
| **[critical]** | **[val]** | **[val]** | **[CRASH/PEAK/etc.]** |
| [t4] | [val] | [val] | [recovery/continuation] |

**Key insight:** [What the time series reveals]

---

## 5. Key Discovery #3: [Mechanism Name]

### Mechanism Identified

1. Around [time]: [What happened first]
2. [Consequence]: [Second-order effect]
3. [Feedback]: [What this triggered]
4. [Outcome]: [Final result]

---

## 6. The "[Named Mechanism]" Pattern

**The "Perfect Storm" / "Cascade" / "[Custom Name]" Mechanism:**

```
[External Driver]
         │
         ├──────────────────────────┐
         ▼                          ▼
┌─────────────────────┐    ┌─────────────────────┐
│ [Effect Path A]     │    │ [Effect Path B]     │
│ • [detail 1]        │    │ • [detail 1]        │
│ • [detail 2]        │    │ • [detail 2]        │
└─────────┬───────────┘    └──────────┬──────────┘
          │                           │
          ▼                           ▼
    [Intermediate A]     +      [Intermediate B]
          │                           │
          └────────────┬────────────┘
                       ▼
              [COMBINED OUTCOME]
              ([description])
```

---

## 7. Code/Model Control (if applicable)

**Code location:** `[path/to/file.F90:line_numbers]`

```fortran
[relevant code snippet]
```

**Key controls:**
- `[variable1]` - [what it controls]
- `[variable2]` - [what it controls]

**During [event]:** [parameter] changed → [effect] → [outcome]

---

## 8. Quantitative Analysis

### [Analysis Type, e.g., "Nutrient Limitation"]

| Phase | [Metric1] | [Metric2] | [Ratio/Comparison] |
|-------|-----------|-----------|-------------------|
| [Phase1] | [val] | [val] | [val] |
| [Phase2] | [val] | [val] | **[critical val]** |
| [Phase3] | [val] | [val] | **[critical val]** |

**Critical finding:** [Key quantitative insight, e.g., "Plants getting <1% of nutrient demand"]

---

## 9. Cross-PFT / Cross-Case Comparison

### Differential Response

| Entity | Pre-Event | During Event | Post-Event | Outcome |
|--------|-----------|--------------|------------|---------|
| [PFT/Case 1] | [val] | **[val]** | [val] | [died/survived/thrived] |
| [PFT/Case 2] | [val] | [val] | [val] | [outcome] |
| [PFT/Case 3] | [val] | [val] | [val] | [outcome] |

**Why different outcomes?**
- [Entity 1]: [Mechanism explaining outcome]
- [Entity 2]: [Mechanism explaining outcome]

---

## 10. Why [Parameter/Action] Made Things Worse

**Hypothesis:**
1. [Step 1 of mechanism]
2. [Step 2 leading to vulnerability]
3. When [event] hit:
   - [Effect 1]
   - [Effect 2]
   - [Final outcome]

---

## 11. Scripts Created

**Location:** `[path to scripts]/`

| Script | Purpose |
|--------|---------|
| `[script1].py` | [Description] |
| `[script2].py` | [Description] |

**To run scripts:**
```bash
source [environment activation]
cd [directory]
python [script].py
```

---

## 12. Output Figures

```
[output_path]/
├── [figure1].png   # [description]
├── [figure2].png   # [description]
└── [figure3].png   # [description]
```

---

## 13. Summary: The Complete Story

1. **[Phase 1]:** [What happened]

2. **[Phase 2]:** [What happened]

3. **[Phase 3]:** [What happened]

4. **[Critical Event]:**
   - [Detail 1]
   - [Detail 2]
   - [Outcome]

5. **[Aftermath]:**
   - [Consequence 1]
   - [Consequence 2]
   - [Final state]

---

## 14. Questions for Discussion

1. **Should we [adjust parameter X]?**
   - [Context and implications]

2. **Should we [modify mechanism Y]?**
   - [Context and implications]

3. **Is [observed behavior] appropriate for [conditions]?**
   - [What needs to be validated]

4. **What about [alternative explanation]?**
   - [How to test it]

---

## 15. Related Memory Files

- `[date]_[topic].md` - [relationship]
- `[date]_[topic].md` - [relationship]

---

**Next Steps:** [Clear statement of what to discuss/test next]
