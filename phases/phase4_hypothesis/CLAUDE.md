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
6. Generate hypothesis report
7. (Skip-testing inner loop, Phase 3↔4) If a hypothesis is testable against existing Morris data (`test_with_existing`), test it now — conclude, or loop back to Phase 3; only hypotheses needing new simulations proceed to Phase 5

---

## Scripts in This Folder

| Script | Purpose |
|--------|---------|
| `generate_hypothesis.py` | Main hypothesis generation workflow (Claude API or rule-based fallback) |
| `test_with_existing_data.py` | Skip-testing: test hypotheses against existing Morris data (comparison / correlation / threshold) |
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

Fields match the `Hypothesis` dataclass in `reasoning/schemas.py`.

```yaml
hypotheses:
  - name: "PID Overshoot Reduction"
    mechanism: "PID_Controller — lower kp reduces C-allocation overshoot for PFT#10"
    parameters:                       # list of {name, current, proposed, rationale} (+ pft/organ/bounds)
      - name: "fates_cnp_pid_kp"
        pft: 10
        current: 0.5
        proposed: 0.3
        rationale: "Lower Kp reduces overshoot in the allocation response"
    design_type: "cumulative"         # or "factorial"
    expected_outcomes: {FROOT_PFT10: 123.0}
    success_criteria: {FROOT_PFT10: 0.20}     # per-target tolerance
    confidence: 0.75
    test_with_existing: false         # true → test with the existing ensemble (skip-testing), no new sims
    base_case_id: 3930                # from Phase 2 screening (stamped by the orchestrator)
```

---

## Experiment Design

Fields match the `Experiment` dataclass in `reasoning/schemas.py`. A `cumulative` design adds one
parameter per experiment (Exp2 = Exp1's change + the next parameter).

```yaml
experiments:
  - name: "Exp1"
    base_case: "case_3930"            # best set from Phase 2 screening
    modifications:                    # list of {parameter, old_value, new_value}
      - parameter: "fates_cnp_pid_kp"
        old_value: 0.5
        new_value: 0.3
    expected_results: {FROOT_PFT10: 123.0}
    success_threshold: 0.20

  - name: "Exp2"
    base_case: "case_3930"
    modifications:
      - parameter: "fates_cnp_pid_kp"
        old_value: 0.5
        new_value: 0.3
      - parameter: "fates_cnp_nitr_store_ratio"
        old_value: 1.5
        new_value: 2.0
    expected_results: {LEAF_PFT10: 95.0}
    success_threshold: 0.20
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

This guidance applies to **both** modes — the autonomous orchestrator traversing Phase 4, and the interactive (offline) agent navigating here. Offline skills for this phase: `phase4-hypothesis` (primary — the offline analog of `reasoning.generate_hypothesis()` + skip-testing), then `offline-testing-workflow` (the HPC path), `scientific-analysis` (see `docs/a2mc_reference/skills_catalog.md`). The phase skill is a floor, not a ceiling — explore beyond the phase scope when the task warrants.

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
