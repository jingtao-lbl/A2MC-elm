# Phase 5: Testing

**Purpose:** Run designed experiments on HPC
**Status:** Compute phase (runs on NERSC Perlmutter)
**Inputs:** Experiment designs from Phase 4, parameter files
**Outputs:** Experiment results, simulation outputs

---

## What This Phase Does

1. Receive handoff from Phase 4 (experiment designs)
2. Create modified parameter files for each experiment
3. Create and configure ELM-FATES cases
4. Submit experiments to HPC queue
5. Monitor completion
6. Extract results for analysis

---

## Scripts in This Folder

| Script | Purpose |
|--------|---------|
| `design_experiments.py` | Create parameter files from experiment specs |
| `submit_experiments.py` | Create cases and submit to HPC |
| `monitor_experiments.py` | Track experiment job status |

---

## Key Inputs

| Input | Source | Description |
|-------|--------|-------------|
| Hypothesis report | Phase 4 | Experiment designs, parameter changes |
| Base parameter file | Phase 0 | Template for modifications |
| Control case | Phase 2 | Best baseline for comparison |

---

## Key Outputs

| Output | Location | Description |
|--------|----------|-------------|
| Experiment param files | `{ENSEMBLE_OUTPUT}/experiments/` | Modified NetCDF files |
| Case directories | `{ENSEMBLE_OUTPUT}/exp_*/` | CIME cases |
| Simulation output | Case run directories | History files |
| Testing report | `memory/phase_results/{session_id}/phase5_testing/` | Status and results |

---

## Shared Tools Used

```python
from tools.modify_fates_parameters import modify_parameter_file
from tools.verify_parameter_file import verify_parameters
from tools.extract_monthly_variables_FATES import extract_variables
from tools.cost_functions import CostFunction
```

---

## Experiment Execution

```python
# Create experiment parameter file
for exp in experiments:
    base_file = get_control_param_file()

    for param in exp['parameters']:
        modify_parameter_file(
            base_file,
            param['name'],
            param['test_value'],
            pft=param.get('pft')
        )

    save_experiment_file(exp['id'])
```

---

## Success Criteria

- [ ] All experiment parameter files created
- [ ] Cases submitted and completed
- [ ] Output files extracted
- [ ] Results compared to control
- [ ] Testing report generated

---

## Next Phase

After Phase 5 completes → **Phase 6 (Refinement)**: Evaluate results

**Handoff includes:**
- Experiment results (cost metrics)
- Comparison to control case
- Observed vs expected outcomes
- Any unexpected behaviors

---

## Common Issues

1. **Experiment diverges:** Parameter change too extreme
2. **No improvement:** Hypothesis may be incorrect
3. **Unexpected degradation:** Parameter interaction
4. **Job failure:** Check FATES logs for errors

---

## When AI Works in This Phase

This guidance applies to **both** modes — the autonomous orchestrator traversing Phase 5, and the interactive (offline) agent navigating here. Offline skills for this phase: `phase5-testing` (primary — a thin router to `offline-testing-workflow`, which owns the execution), `arm-hpc-monitoring`, `restart-failed-jobs` (see `docs/a2mc_reference/skills_catalog.md`). The phase skill is a floor, not a ceiling — explore beyond the phase scope when the task warrants.

**Focus on:**
- Ensuring parameter files match experiment specs
- Monitoring job completion
- Initial result extraction
- Identifying any experiment failures

**Do NOT:**
- Modify experiment designs without returning to Phase 4
- Skip the control case comparison
- Interpret results (that's Phase 6)
- Delete simulation outputs

---

## Experiment Naming Convention

The real convention (from `tools/create_case.sh --case-suffix` + `design_experiments.py`):

```
# Modified parameter file (design_experiments.py:169): <base param stem>_<suffix>.nc
    e.g.  fates_params_..._En2678_exp1.nc

# Case name (create_case.sh:228-235): resolve A2MC_CASE_NAME_PATTERN for case N, then
# append _<suffix>; ADSP → RGSP → TRANS chained per phase.
    e.g.  ..._En2678_exp1_ADSP
          ..._En2678_exp1_RGSP
          ..._En2678_exp1_TRANS
```

(The `_<suffix>` / `_exp` convention keeps experiment cases out of the Morris case-number space —
see root `CLAUDE.md` Rule 7. `offline-testing-workflow` uses the same mechanism, e.g. `_clump02`.)

---

## Result Extraction

```python
# Extract key variables for each experiment
for exp_id in completed_experiments:
    results = extract_variables(
        case_dir=f"exp_{exp_id}",
        variables=['FATES_LEAFC_PF', 'FATES_FROOTC_SZPF', ...],
        time_range=('2015-01-01', '2019-12-31')
    )

    # Compute cost against targets
    cost = optimize_ensemble(
        simulated=results,
        targets=validation_targets
    )

    save_experiment_results(exp_id, cost)
```

---

## Comparison to Control

Each experiment is compared to the control case (best set from Phase 2):

```yaml
experiment_results:
  - exp_id: "EXP_001"
    hypothesis_id: "H1"
    control_cost: 0.342
    experiment_cost: 0.285
    improvement: 16.7%
    expected_improvement: ">20%"
    outcome: "partial_success"
```
