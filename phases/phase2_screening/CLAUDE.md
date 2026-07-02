# Phase 2: Screening

**Purpose:** Rank ensemble members against validation targets, identify promising parameter sets
**Status:** AI-assisted analysis phase
**Inputs:** Simulation outputs, validation targets
**Outputs:** Ranked parameter sets, error analysis, screening report

---

## What This Phase Does

1. Read the variables extracted in Phase 1 (Phase 2 does not re-extract; it reads existing outputs)
2. Compute cost/error metrics against validation targets
3. Rank ensemble members by aggregate cost
4. Analyze error patterns across targets
5. Identify parameters at edge of their ranges
6. Generate screening report with recommendations

---

## Scripts in This Folder

| Script | Purpose |
|--------|---------|
| `screen_ensemble.py` | Main screening: load ensemble outputs, rank against validation targets, hand off to Phase 3 |
| `screening_helpers.py` | Load / perform / analyze screening results (extracted from `orchestrator.py`) |
| `plot_screening.py` | Ensemble biomass-vs-targets panel figure (top-N purple, best-NRMSE red, most-targets blue) |
| `compare_biomass_topcases.py` | Compare top cases against observations |

---

## Key Inputs

| Input | Source | Description |
|-------|--------|-------------|
| Extracted data | Phase 1 | `{EXTRACTED_DATA}/*.csv` or `.nc` |
| Validation targets | Site config | `use_cases/{site}/validation/targets.txt` |
| Parameter matrix | Phase 0 | Ensemble parameter values |

---

## Key Outputs

| Output | Location | Description |
|--------|----------|-------------|
| Ranked results | `memory/phase_results/{session_id}/phase2_screening/` | JSON with rankings |
| Top N sets | Report | Best parameter sets by cost |
| Error distribution | Report | Per-target error statistics |
| Next steps | Report handoff | Recommendations for Phase 3 |

---

## Shared Tools Used

```python
from tools.cost_functions import CostFunction, aggregate_costs
from tools.optimize_function import Target, optimize_ensemble
from tools.fates_utils import get_szpf_range, aggregate_szpf_by_pft
```

---

## Cost Function Options

| Method | Description | Use When |
|--------|-------------|----------|
| `relative_error` | `\|sim - obs\| / obs` | Default, scale-independent |
| `rmse` | Root mean square error | Absolute accuracy matters |
| `nrmse` | Normalized RMSE | Compare across variables |
| `nse` | Nash-Sutcliffe efficiency | Time series evaluation |
| `kge` | Kling-Gupta efficiency | Hydrological applications |

**Aggregation:** `rmsre` (root mean square of relative errors) across targets

---

## AI Analysis Tasks

The `reasoning.analyze_screening_results()` method:
- Identifies error patterns across targets
- Finds parameters consistently at bounds
- Detects PFT trade-offs (improving one degrades another)
- Generates recommendations for diagnosis

---

## Success Criteria

- [ ] All completed cases analyzed
- [ ] Ranked list of top N parameter sets
- [ ] Error distribution computed for each target
- [ ] Edge parameters identified
- [ ] Screening report generated with next steps

---

## Next Phase

After Phase 2 completes → **Phase 3 (Diagnosis)**: Root cause analysis

**Handoff includes:**
- Top parameter sets to investigate
- Targets with highest errors
- Parameters at edge of range
- Suspected mechanisms

---

## Common Issues

1. **Missing output variables:** Check extraction script configuration
2. **All costs high:** Possible structural model problem
3. **PFT trade-offs:** May need multi-objective approach
4. **Edge parameters:** Consider expanding bounds

---

## When AI Works in This Phase

This guidance applies to **both** modes — the autonomous orchestrator traversing Phase 2, and the interactive (offline) agent navigating here. Offline skills for this phase: `phase2-screening` (primary — the offline analog of `reasoning.analyze_screening_results()`), then `summarize-calibration-round`, `compare-calibration-rounds` (see `docs/a2mc_reference/skills_catalog.md`). The phase skill is a floor, not a ceiling — explore beyond the phase scope when the task warrants.

**Focus on:**
- Pattern recognition in error distributions
- Identifying correlations between parameters and errors
- Generating actionable recommendations for diagnosis
- Documenting discoveries and insights

**Do NOT:**
- Modify simulation outputs
- Change validation targets without user approval
- Skip edge parameter analysis

---

## Example Screening Output

```json
{
  "phase": 2,
  "status": "completed",
  "ensemble_size": 4890,
  "completed_cases": 4850,
  "best_cost": 0.342,
  "best_set_id": 3930,
  "next_steps": [
    {
      "priority": 1,
      "action": "Diagnose PFT#10 fineroot underestimation",
      "target_phase": 3
    }
  ]
}
```
