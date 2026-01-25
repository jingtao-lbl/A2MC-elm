# Reasoning Templates

This directory contains templates for AI reasoning in each A2MC phase. These templates define the structure and content expected from the ReasoningModule for diagnosis, hypothesis generation, and refinement.

## Templates

| Template | Phase | Purpose |
|----------|-------|---------|
| `phase2_screening_template.md` | 2 | Ensemble screening, bias analysis, PFT comparison |
| `phase3_diagnosis_template.md` | 3 | Root cause analysis structure |
| `phase4_hypothesis_template.md` | 4 | Hypothesis and experiment design |
| `phase6_refinement_template.md` | 6 | Evaluation and lesson extraction |

## How Templates Are Used

1. **In `reasoning.py`**: The prompt strings in each method follow these template structures
2. **In Phase CLAUDE.md**: Referenced for AI context when working in that phase
3. **For logging**: PhaseLogger outputs follow these structures for knowledge extraction

## Template Design Principles

These templates were derived from patterns observed in the first (offline) calibration iteration documented in `Backup/` memory files:

### Key Sources

- `20251222a_PFT10_Diagnostic_Findings_Triple_Bottleneck.md` - Diagnosis pattern
- `20251223a_PUptake_Tests_Allocation_Paradox.md` - Hypothesis testing pattern
- `20251214a_Case2678vs845_ParameterTradeoff.md` - Refinement pattern
- `20251231a_P_Desorption_Drought_Analysis.md` - Multi-phase time series, "Perfect Storm" mechanism, mortality component analysis, pool tracking

### Patterns Identified

1. **Screening**: Quantify PFT-by-PFT performance, identify bias patterns, formulate initial questions
2. **Diagnosis**: Start with hypotheses, then systematically test each with quantitative evidence
3. **Hypothesis Testing**: Clear expected vs actual structure with named discoveries
4. **Refinement**: Category-based analysis with mechanism ASCII diagrams

## Template Sections

Each template contains:
- **Required sections**: Must be present in every output
- **Optional sections**: Include when relevant
- **JSON schema**: Structured output for programmatic parsing
- **ASCII diagram examples**: Visual aids for mechanism explanation

## Updating Templates

When updating templates:
1. Preserve the JSON schema structure for compatibility
2. Add new optional sections rather than removing existing ones
3. Update the corresponding phase CLAUDE.md file
4. Test with a sample reasoning call

## Related Files

- `reasoning.py` - ReasoningModule that uses these patterns
- `tools/phase_logger.py` - Logs structured output from reasoning
- `phases/phase{N}_{name}/CLAUDE.md` - Phase-specific context
