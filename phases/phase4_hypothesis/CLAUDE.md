# Phase 4: Hypothesis Generation

**Purpose:** Generate testable hypotheses and design experiments
**Status:** AI reasoning phase (uses Claude API)
**Inputs:** Diagnosis results, parameter bounds, experimental constraints
**Outputs:** Hypotheses, experiment designs, testing plan

---

## What This Phase Does

1. Receive handoff from Phase 3 (root causes, implicated parameters)
2. Generate specific, testable hypotheses
3. Design experiments to test each hypothesis
4. Specify parameter modifications for each experiment
5. Define expected outcomes and success criteria
6. Generate hypothesis report for Phase 5

---

## Scripts in This Folder

| Script | Purpose |
|--------|---------|
| `generate_hypothesis.py` | Main hypothesis generation workflow |
| `test_with_existing_data.py` | Skip-testing — test hypotheses with existing ensemble data |
| `synthesis.py` | Synthesize skip-testing insights into experiment designs |

---

## Key Inputs

| Input | Source | Description |
|-------|--------|-------------|
| Diagnosis report | Phase 3 | Root causes, implicated parameters |
| Parameter bounds | Site config | Valid ranges for modifications |
| Memory context | `memory/data/` | Failed approaches to avoid |
| Baseline results | Phase 2 | Reference performance |

---

## Key Outputs

| Output | Location | Description |
|--------|----------|-------------|
| Hypotheses | Report | Testable statements with IDs |
| Experiments | Report | Parameter modifications |
| Expected outcomes | Report | Predicted improvements |
| Hypothesis report | `memory/phase_results/{session_id}/phase4_hypothesis/` | Full JSON |

---

## Hypothesis Structure

```yaml
hypotheses:
  - id: "H1"
    statement: "Reducing fates_cnp_pid_kp from 0.5 to 0.3 will reduce FROOT_PFT10 error by >20%"
    mechanism: "PID_Controller"
    testable: true
    experiment_id: "EXP_001"
    rationale: "Lower Kp reduces overshoot in allocation response"
    confidence: 0.75

  - id: "H2"
    statement: "Increasing fates_cnp_nitr_store_ratio will improve PFT#10 nitrogen status"
    mechanism: "Storage_Allocation"
    testable: true
    experiment_id: "EXP_002"
    rationale: "More N storage provides buffer against competition"
    confidence: 0.6
```

---

## Experiment Design

```yaml
experiments:
  - id: "EXP_001"
    hypothesis_id: "H1"
    type: "single_parameter"
    parameters:
      - name: "fates_cnp_pid_kp"
        baseline: 0.5
        test_value: 0.3
        pft: 10
    expected_outcome:
      target: "FROOT_PFT10"
      direction: "decrease_error"
      magnitude: ">20%"
    control: "baseline_set_3930"  # Best set from Phase 2

  - id: "EXP_002"
    hypothesis_id: "H2"
    type: "multi_parameter"
    parameters:
      - name: "fates_cnp_nitr_store_ratio"
        baseline: 1.5
        test_value: 2.0
        pft: 10
      - name: "fates_cnp_phos_store_ratio"
        baseline: 1.5
        test_value: 2.0
        pft: 10
    expected_outcome:
      target: "LEAF_PFT10"
      direction: "increase"
      magnitude: "10-20%"
```

---

## Success Criteria

- [ ] Each hypothesis is testable (clear prediction)
- [ ] Experiments specify exact parameter changes
- [ ] Expected outcomes are quantifiable
- [ ] No experiments repeat known failed approaches
- [ ] Hypothesis report generated with next steps

---

## Next Phase

After Phase 4 completes → **Phase 5 (Testing)**: Run experiments

**Handoff includes:**
- Experiment IDs and configurations
- Parameter files to create
- Success criteria for each experiment
- Control case reference

---

## Common Issues

1. **Vague hypotheses:** Make predictions specific and quantifiable
2. **Too many experiments:** Prioritize by confidence and impact
3. **Conflicting experiments:** May need factorial design
4. **Untestable hypothesis:** Reformulate with measurable outcome

---

## When AI Works in This Phase

**Focus on:**
- Generating falsifiable hypotheses
- Designing efficient experiments
- Specifying clear success criteria
- Avoiding repetition of failed approaches

**Do NOT:**
- Generate hypotheses without mechanistic basis
- Design experiments outside parameter bounds
- Ignore constraints from Phase 3 diagnosis
- Skip checking Memory for failed approaches

---

## Hypothesis Quality Checklist

A good hypothesis should:
- [ ] State a specific, testable prediction
- [ ] Identify the mechanism being tested
- [ ] Specify which parameters to change
- [ ] Define expected outcome quantitatively
- [ ] Be connected to a root cause from Phase 3

---

## Reasoning Template

**See:** `templates/reasoning/phase4_hypothesis_template.md`

The hypothesis generation should follow a structured approach:

1. **Hypothesis Summary Table** - Overview with names, mechanisms, confidence
2. **Detailed Hypothesis Structure** - Each hypothesis with ASCII mechanism diagram
3. **Experiment Design** - YAML specification with base case and modifications
4. **Potential Discoveries** - Named patterns to watch for (Paradoxes, Traps)
5. **What WON'T Work** - Failed approaches from memory with alternatives
6. **What MIGHT Work** - Lower-confidence speculative approaches

### Key Patterns from Iteration #1

**Discovery Naming:** Give memorable names to unexpected findings:
- "Allocation Paradox" - When ↑ uptake efficiency → ↓ total uptake
- "Mortality Trap" - When ↑ allocation → ↑ mortality
- "Triple Bottleneck" - Multiple simultaneous constraints

**ASCII Diagrams:** Always include mechanism diagrams:
```
Current:  A → B → C (problem)
Proposed: A → B' → C (solution)
```

---

## AI Reasoning Process

```python
from reasoning import ReasoningModule

reasoning = ReasoningModule(use_rag=True)

hypotheses = reasoning.generate_hypothesis(
    diagnosis=diagnosis_report,
    constraints={
        'max_experiments': 5,
        'parameter_bounds': param_bounds,
        'excluded_approaches': memory.get_failed_approaches()
    },
    iteration=1
)
```
