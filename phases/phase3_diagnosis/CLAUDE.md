# Phase 3: Diagnosis

**Purpose:** AI-driven root cause analysis of model-data mismatch
**Status:** AI reasoning phase (uses Claude API)
**Inputs:** Screening results, Morris sensitivity rankings, RAG context
**Outputs:** Root causes, implicated parameters, diagnosis report

---

## What This Phase Does

1. Receive handoff from Phase 2 (next steps, error patterns)
2. Query RAG/GraphRAG for mechanistic knowledge
3. Query Adaptive Memory for past discoveries and failed approaches
4. Reason about root causes of model-data mismatch
5. Identify parameters and mechanisms responsible
6. Generate diagnosis report with hypotheses to test

---

## Scripts in This Folder

### High-Level API (for orchestrator)

| Script | Purpose |
|--------|---------|
| `run_diagnosis.py` | Main diagnosis workflow - orchestrates all diagnostic scripts |
| `ai_diagnosis.py` | Claude API + rule-based diagnosis (extracted from orchestrator) |
| `dispatch.py` | Execute AI-requested diagnostics — dispatches the diagnostic tools |
| `run_diagnostics_scripts.py` | Gather data for diagnosis — edge-param checks, PFT diagnostics, figures |

### Low-Level Diagnostic Scripts

| Script | Purpose |
|--------|---------|
| `read_case_parameters.py` | Read parameter values from Morris ensemble file |
| `check_edge_parameters.py` | Identify parameters at sampling bounds |
| `compare_case_parameters.py` | Compare parameters between Morris cases |
| `diagnose_pft_limitations.py` | Analyze allocation, nutrient, competition limits |
| `analyze_mortality.py` | Extract and analyze mortality by component |
| `analyze_nutrient_pools.py` | P/N pool dynamics, uptake vs demand |
| `detect_collapse.py` | Vegetation collapse detection ("Perfect Storm") |
| `compare_targets.py` | Compare simulated vs observed targets |
| `test_hypothesis_framework.py` | Structured hypothesis testing with quantified metrics |
| `analyze_carbon_balance.py` | Detect carbon deficit (GPP vs MR bottleneck) |
| `analyze_nutrient_balance.py` | Full N/P mass balance, budget closure, PFT competition |
| `comparative.py` | Evaluate best_case vs lowest_cost_case (pure function) |
| `plot_diagnostics.py` | Diagnostic figures for PFT diagnosis |

### Auto-discovered hypothesis tests + promotion

Additional `test_*.py` scripts in this folder are **auto-discovered** hypothesis tests — any
`test_*.py` exposing `test_hypothesis()` is picked up automatically (see root `CLAUDE.md`
§"Diagnostic tools"), so they are not enumerated in the table above. AI-generated custom scripts
land in `generated/`; a vetted, reusable one is promoted into this permanent library with
`tools/promote_diagnostic_script.py` (copies it here + registers it in the diagnostic-tools
inventory; human-gated).

---

## Key Inputs

| Input | Source | Description |
|-------|--------|-------------|
| Screening report | Phase 2 | Top sets, error patterns, next steps |
| Morris rankings | Phase 0/2 | Parameter sensitivity (μ*, σ) |
| RAG context | `rag/` | FATES documentation, mechanisms |
| Memory context | `memory/data/` | Past discoveries, failed approaches |

---

## Key Outputs

| Output | Location | Description |
|--------|----------|-------------|
| Root causes | Diagnosis report | Mechanisms explaining errors |
| Implicated parameters | Report | Parameters to modify |
| Hypotheses | Report | Testable statements |
| Diagnosis report | `memory/phase_results/{session_id}/phase3_diagnosis/` | Full JSON report |

---

## High-Level API Usage

The orchestrator uses the high-level API to run all diagnostic scripts:

```python
from phases.phase3_diagnosis import run_diagnosis_for_orchestrator

# Run all diagnostic scripts
result = run_diagnosis_for_orchestrator(
    screening_data=screening_results,
    morris_file="/path/to/morris_params.txt",
    param_names_file="/path/to/param_names.txt",
    param_bounds_file="/path/to/param_bounds.txt",
    nc_file="/path/to/simulation.nc",  # Optional
    targets={'PFT7': {'leaf': 24.6}, ...},
    pft_ids=[7, 9, 10]
)

# Access diagnostic results
print(result.edge_summary)      # Parameters at bounds
print(result.target_summary)    # Simulated vs observed
print(result.get_ai_context())  # Combined context for AI
```

---

## AI Reasoning Process

The diagnostic data is passed to Claude for reasoning:

```python
from reasoning import ReasoningModule

reasoning = ReasoningModule(use_rag=True)

# Diagnostic scripts provide context
results = screening_results.copy()
results["diagnostic_context"] = {
    "parameters": diagnostic_result.parameters,
    "edge_summary": diagnostic_result.edge_summary,
    "redesign_candidates": diagnostic_result.redesign_candidates
}

diagnosis = reasoning.diagnose(
    results=results,
    targets=targets,
    morris_rankings=sensitivity_data,
    iteration=1
)
```

**RAG provides:**
- Parameter-mechanism relationships
- Output variable dependencies
- Known model behaviors

**Memory provides:**
- Past discoveries (e.g., "Allocation Paradox")
- Failed approaches to avoid
- Parameter-specific insights

---

## Example Root Cause Analysis

```yaml
root_causes:
  - cause: "PID Controller Overshoot"
    mechanism: "PID_Controller"
    affected_targets: ["FROOT_PFT10", "LEAF_PFT10"]
    explanation: "High pid_kp causes oscillation in C allocation"
    confidence: 0.85

  - cause: "Nutrient Competition Imbalance"
    mechanism: "ECA_Competition"
    affected_targets: ["LEAF_PFT7", "LEAF_PFT9"]
    explanation: "PFT#7 outcompetes PFT#9 for nitrogen"
    confidence: 0.7
```

---

## Success Criteria

- [ ] Root causes identified with evidence
- [ ] Parameters implicated with mechanistic justification
- [ ] Hypotheses are testable and specific
- [ ] No repetition of known failed approaches
- [ ] Diagnosis report generated with next steps

---

## Next Phase

After Phase 3 completes → **Phase 4 (Hypothesis)**: Design experiments

**Handoff includes:**
- Specific hypotheses to test
- Parameters to modify
- Expected outcomes
- Experiment design suggestions

---

## Common Issues

1. **Vague root causes:** Need more specific RAG context
2. **Conflicting mechanisms:** May indicate parameter interactions
3. **No clear root cause:** Consider structural model limitations

---

## When AI Works in This Phase

**Focus on:**
- Mechanistic reasoning (not just statistical patterns)
- Connecting symptoms to FATES processes
- Using RAG to verify assumptions about model behavior
- Checking Memory for relevant past discoveries

**Do NOT:**
- Assume behavior from parameter names (always check RAG)
- Ignore failed approaches from Memory
- Generate untestable hypotheses
- Skip the handoff from Phase 2

---

## Reasoning Template

**See:** `templates/reasoning/phase3_diagnosis_template.md`

The diagnosis reasoning should follow a structured approach:

1. **Executive Summary** - Brief key findings
2. **Failing Targets Analysis** - Quantitative breakdown with severity
3. **Initial Hypotheses** - 4-6 hypotheses BEFORE analysis
4. **Diagnostic Evidence** - For/against each hypothesis
5. **Conceptual Model** - ASCII diagram of causal chain
6. **Root Cause Identification** - Ranked by confidence
7. **Key Insights** - Numbered actionable findings
8. **Recommendations** - Specific parameters for Phase 4

---

## RAG Query Examples

```python
# Get context for diagnosis
context = retriever.get_calibration_context(
    parameters=['fates_cnp_pid_kp', 'fates_cnp_pid_kd'],
    outputs=['FATES_LEAFC', 'FATES_FROOTC'],
    mechanisms=['PID_Controller'],
    pft=10
)
```

---

## Memory Query Examples

```python
# Check for relevant past knowledge
memory_context = memory.get_relevant_context(
    targets=['FROOT_PFT10'],
    parameters=['fates_cnp_pid_kp'],
    phase=3
)

# Check failed approaches
failed = memory.get_failed_approaches(
    related_to=['pid_kp', 'allocation']
)
```
