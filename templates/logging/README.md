# Logging Templates

These templates define how the AI should document its reasoning process in persistent Markdown files. These logs serve as:

1. **Human-readable documentation** of the calibration process
2. **Memory for future iterations** - AI can learn from past analyses
3. **Audit trail** for understanding decisions made

## Templates

| Template | Purpose | When to Use |
|----------|---------|-------------|
| `screening_log_template.md` | Document ensemble screening analysis | Phase 2 bias analysis, PFT comparison |
| `diagnostic_log_template.md` | Document root cause analysis | Phase 3 deep dives |
| `experiment_log_template.md` | Document hypothesis testing | Phase 4-5 experiments |
| `discovery_log_template.md` | Document key discoveries | When finding unexpected results |
| `analysis_log_template.md` | General analysis documentation | Multi-phase investigations |

## Naming Convention

```
YYYYMMDD{letter}_{Topic_Description}.md
```

Examples:
- `20251222a_PFT10_Diagnostic_Findings_Triple_Bottleneck.md`
- `20251223a_PUptake_Tests_Allocation_Paradox.md`
- `20251231a_P_Desorption_Drought_Analysis.md`

The letter (a, b, c...) indicates sequence within a day.

## Storage Locations

**IMPORTANT:** There are two distinct logging locations:

### 1. A2MC Runtime Logs (AI Reasoning Documentation)

These templates are for **A2MC runtime reasoning logs** - documentation of the AI's reasoning during actual calibration runs. Stored per use case:

```
use_cases/{site}/memory/logs/
├── phase0_design/
├── phase1_exploration/
├── phase2_screening/
├── phase3_diagnosis/
├── phase4_hypothesis/
├── phase5_testing/
├── phase6_refinement/
├── phase7_converged/
└── {date}_*.md  (general logs)
```

Example: `use_cases/Kougarok/memory/logs/phase3_diagnosis/20260120a_Triple_Bottleneck.md`

### 2. Development Session Logs (Framework Development)

Development/debugging session logs for A2MC framework development go to:

```
A2MC/memory/logs/
└── {date}_{topic}.md
```

Example: `memory/logs/20260119d_Reasoning_Templates.md`

**Key distinction:**
- **Runtime logs** = AI documenting its reasoning during calibration (use these templates)
- **Development logs** = Human+AI documenting framework development work

## Key Principles

### 1. Start with Executive Summary
Every log should begin with a brief summary that captures:
- The problem being addressed
- Key findings/discoveries
- Recommended next steps

### 2. Document the Journey
Include "how we got here" context:
- What prompted this analysis
- Previous attempts and their outcomes
- User feedback that shaped the investigation

### 3. Name Your Discoveries
Give memorable names to unexpected findings:
- "Triple Bottleneck" - Multiple simultaneous constraints
- "Allocation Paradox" - Counter-intuitive allocation behavior
- "Perfect Storm" - Cascading multi-factor failures

### 4. Include Quantitative Evidence
Use tables for data presentation:
- Before/after comparisons
- Cross-case analysis
- Time series at key points

### 5. End with Questions
Close with open questions for future investigation:
- What remains unexplained?
- What parameters might need adjustment?
- What assumptions should be questioned?

## Relationship to Other Templates

| Template Type | Purpose | Format |
|---------------|---------|--------|
| `reasoning/` | Structure of AI thinking | JSON schemas + sections |
| `logging/` | Documentation of process | Markdown narratives |

Reasoning templates define WHAT to think about.
Logging templates define HOW to document it.

## Source Files

These templates are based on patterns from the first (offline) calibration iteration:
- `/Users/jingtao/Desktop/Work/SourceCode/ELM_FATES/fates_knowledge_base/memory/`
- See `A2MC/Backup/curated_list.txt` for the full list
