#!/usr/bin/env python3
"""
Reasoning Module Prompt Constants

Constants used in AI reasoning prompts:
- DIAGNOSTIC_TOOLS_INVENTORY: Available diagnostic scripts for Claude to request
- CUSTOM_SCRIPT_TEMPLATE: Template for custom hypothesis testing scripts

Author: Jing Tao with Claude
"""

# =============================================================================
# DIAGNOSTIC TOOLS INVENTORY
# =============================================================================
# This inventory is included in AI prompts so Claude knows what scripts are
# available and can request specific diagnostics for deeper analysis.
#
# The Ensemble-Level Analysis section is auto-generated at runtime from
# discover_ensemble_tests() in phases/phase3_diagnosis/__init__.py.
# When new test_*.py scripts with test_hypothesis() are added to that
# directory, they appear here automatically — no manual editing needed.

_DIAGNOSTIC_TOOLS_INVENTORY_TEMPLATE = """
## Available Diagnostic Tools

You can request specific diagnostic analyses by including them in your response.
The orchestrator will run these scripts and provide results in follow-up calls.

### Parameter Analysis

| Tool | Function | Use When |
|------|----------|----------|
| `check_edge_parameters` | Find parameters at Morris sampling bounds | Suspect parameter space is too narrow |
| `compare_case_parameters` | Compare parameters between good/bad cases | Want to find what makes best cases different |
| `read_case_parameters` | Get exact parameter values for a case | Need specific values for diagnosis |

### PFT Limitation Analysis

| Tool | Function | Use When |
|------|----------|----------|
| `diagnose_pft_limitations` | Full PFT diagnosis (allocation, nutrients, competition) | PFT underperforming targets |
| `analyze_allocation_dynamics` | Check L2FR and allocation responses | Suspect allocation imbalance |
| `analyze_nutrient_limitation` | Test N/P starvation hypotheses | Suspect nutrient limits growth |
| `analyze_light_competition` | Check inter-PFT shading effects | Suspect competition for light |

### Mortality & Collapse Analysis

| Tool | Function | Use When |
|------|----------|----------|
| `analyze_mortality` | Decompose mortality by cause (hydraulic, carbon starvation, fire) | Vegetation declining unexpectedly |
| `detect_collapse` | Find "Perfect Storm" patterns (rapid vegetation loss) | Suspect cascading failures |
| `detect_perfect_storm_pattern` | Check for multi-factor collapse signature | Multiple stressors combining |

### Nutrient Pool Analysis

| Tool | Function | Use When |
|------|----------|----------|
| `analyze_nutrient_pools` | P and N pool time series | Suspect nutrient depletion |
| `compare_uptake_vs_demand` | Check if uptake meets plant demand | Suspect uptake limitation |
| `extract_p_pools` / `extract_n_pools` | Get specific nutrient pool data | Need detailed nutrient dynamics |

### Nutrient Mass Balance

| Tool | Function | Use When |
|------|----------|----------|
| `extract_nutrient_budget` | Full N/P budget (all inputs, outputs, pools) | Need complete nutrient accounting |
| `calculate_budget_closure` | Check dPool/dt = Inputs - Outputs | Suspect mass imbalance or missing fluxes |
| `analyze_pft_competition` | PFT-level uptake shares and supply/demand | Suspect inter-PFT nutrient competition |
| `identify_nutrient_sinks` | Rank output pathways by magnitude | Need to find dominant nutrient loss paths |

### Target Comparison

| Tool | Function | Use When |
|------|----------|----------|
| `compare_biomass_targets` | Compare simulated vs observed values | Initial target assessment |
| `calculate_target_metrics` | Compute RE, RMSE, bias for targets | Quantify error patterns |

### Hypothesis Testing

| Tool | Function | Use When |
|------|----------|----------|
| `test_hypotheses` | Test multiple competing hypotheses with quantified metrics | Evaluating multiple explanations for a pattern |
| `test_single_hypothesis` | Test one specific hypothesis | Targeted hypothesis testing |
| `get_default_hypotheses` | Get common hypotheses for CNP allocation issues | Starting point for hypothesis testing |

### Carbon Balance Analysis

| Tool | Function | Use When |
|------|----------|----------|
| `analyze_carbon_balance` | Detect carbon deficit (cumulative GPP vs MR) | Suspecting carbon starvation or growth constraints |
| `detect_carbon_bottleneck` | Quick check for carbon bottleneck | Fast screening for C limitation |

### Ensemble-Level Analysis

{ensemble_tools_placeholder}

### Ensemble Visualization

| Tool | Function | Use When |
|------|----------|----------|
| `plot_ensemble_biomass` | Plot top-N ensemble timeseries with best cases highlighted (red=best NRMSE, blue=most targets) | Want to visualize ensemble spread and best cases against observations |

### How to Request Diagnostics

In your JSON response, include:
```json
"requested_diagnostics": [
    {
        "tool": "check_edge_parameters",
        "reason": "Best case has extreme values, need to verify bounds",
        "priority": "high"
    },
    {
        "tool": "analyze_mortality",
        "reason": "PFT#10 biomass too low, suspect mortality issues",
        "priority": "medium",
        "args": {"pft_ids": [10]}
    }
]
```

The orchestrator will run requested diagnostics and include results in the next call.
"""


def _build_ensemble_tools_section():
    """Auto-generate the Ensemble-Level Analysis table from discovered tests."""
    try:
        from phases.phase3_diagnosis import discover_ensemble_tests
        tools = discover_ensemble_tests()
    except Exception:
        tools = {}

    if not tools:
        return "| Tool | Function | Use When |\n|------|----------|----------|\n| (none discovered) | — | — |"

    lines = ["| Tool | Function | Use When |",
             "|------|----------|----------|"]
    for name, meta in sorted(tools.items()):
        desc = meta.get('description', name)
        hypothesis = meta.get('hypothesis', '')
        use_when = hypothesis if hypothesis else f"Test: {desc}"
        lines.append(f"| `{name}` | {desc} | {use_when} |")
    return "\n".join(lines)


def get_diagnostic_tools_inventory():
    """Return the full diagnostic tools inventory with auto-discovered ensemble tests."""
    ensemble_section = _build_ensemble_tools_section()
    return _DIAGNOSTIC_TOOLS_INVENTORY_TEMPLATE.replace(
        "{ensemble_tools_placeholder}", ensemble_section)


# Backward-compatible: callers that read DIAGNOSTIC_TOOLS_INVENTORY directly
# still get the auto-populated version (evaluated once at import time).
DIAGNOSTIC_TOOLS_INVENTORY = get_diagnostic_tools_inventory()


# Custom script template for hypothesis testing
CUSTOM_SCRIPT_TEMPLATE = '''
## Writing Custom Test Scripts

IMPORTANT: Before writing a custom script, check the "Ensemble-Level Analysis" section
in the Diagnostic Tools Inventory above. If a promoted tool already exists that matches
your hypothesis (e.g., test_p_limitation_cascade, test_root_turnover_impact), set
method to "custom_script" with that tool's name as script_name. The system will
automatically use the promoted tool's verified code. You do NOT need to provide
script_code when a promoted tool exists — if you do, it will be ignored in favor
of the promoted version.

If NO existing diagnostic tool can test your hypothesis, you can write a custom Python script.
The script will be saved and executed by the orchestrator.

### Data Reference (MUST follow exactly)

#### Where the data comes from (file locations)

The orchestrator pre-loads data and passes it to your function. You do NOT open files yourself.

| Data | Source Files | Location |
|------|-------------|----------|
| `param_matrix` | Morris X matrix (`*Morris*.txt`) | `use_cases/{site}/parameters/` |
| `y_outputs["leaf_biomass"]` | `MorrisLeafbiomass_*cases*.txt` | `use_cases/{site}/memory/phase_results/phase1_exploration/` |
| `y_outputs["froot_biomass"]` | `MorrisFinerootbiomass_*cases*.txt` | same directory |
| `y_outputs["agb_biomass"]` | `MorrisAbgbiomass_*cases*.txt` | same directory |
| `screening_data` | Phase 2 screening results (dict) | passed from orchestrator state |

#### screening_data: dict (Phase 2 screening results)

| Key | Type | Description |
|-----|------|-------------|
| `"best_case"` | dict | Best case: `{"case_id": int, "composite_nrmse": float}` |
| `"best_cases"` | list[dict] | Top cases ranked by composite NRMSE, each with `case_id`, `composite_nrmse` |
| `"case_numbers"` | list[int] | All evaluated case numbers (maps array index → case number) |
| `"n_cases_evaluated"` | int | Total number of cases evaluated |

**NOTE:** Validation targets are NOT in `screening_data`. They are loaded separately
by the orchestrator. If your script needs to classify "good" vs "bad" cases, use
the biomass values in `y_outputs` and compare against known observed values from
the diagnosis context — or use `screening_data["best_cases"]` to get pre-ranked cases.

**Identifying good vs bad cases:**
```python
best_cases = screening_data.get("best_cases", [])
best_case_ids = {int(c["case_id"]) for c in best_cases[:10]}  # Top 10
case_numbers = screening_data.get("case_numbers", [])
```

Per-case NetCDF time series (NOT loaded into y_outputs — for reference only):
- Location: `$A2MC_EXTRACTED_DATA/` (the extracted data directory)
- Filename pattern: `{CASE_NAME_PATTERN}_all_variables_monthly_{startyr}_{endyr}.nc`
- Example: `Kougarok_ELM-FATES_PtCNPEn322_TRANS_all_variables_monthly_1901_2019.nc`
- These contain full monthly output for ALL variables (biomass, fluxes, phenology, nutrients)

#### param_matrix: np.ndarray, shape (n_cases, n_params)
Morris parameter values. Columns match `config["param_names"]` (shorthand names).

#### y_outputs: dict of np.ndarray, each shape (n_cases, n_pfts)
Biomass Y matrices from Phase 1 extraction (annual-mean values per case per PFT).

**Available keys and their meaning:**
| Key | Description | Shape |
|-----|-------------|-------|
| `"leaf_biomass"` | Leaf biomass (g C/m²) | (n_cases, n_pfts) |
| `"froot_biomass"` | Fineroot biomass (g C/m²) | (n_cases, n_pfts) |
| `"agb_biomass"` | Aboveground biomass (g C/m²) | (n_cases, n_pfts) |

**WRONG key names (do NOT use):** `"fineroot_biomass"`, `"leaf_biomass_pft10"`, `"froot_biomass_pft7"`

#### PFT column mapping in y_outputs arrays
Columns are ordered by the PFTs configured for this site. For a 3-PFT site with PFTs [7, 9, 10]:

| Column Index | PFT |
|---|---|
| 0 | PFT#7 |
| 1 | PFT#9 |
| 2 | PFT#10 |

**Build the mapping dynamically from config:**
```python
pft_ids = config.get("pft_ids", [7, 9, 10])
PFT_COL = {pft: i for i, pft in enumerate(pft_ids)}
# PFT_COL = {7: 0, 9: 1, 10: 2}

# Access PFT#10 fineroot biomass:
froot = y_outputs["froot_biomass"]
froot_pft10 = froot[:, PFT_COL[10]]   # Column 2
```

**WRONG indexing (do NOT use):**
- `froot[:, pft - 7]` — gives wrong indices (0, 2, 3) instead of (0, 1, 2)
- `froot[:, 2]` — hardcoded; use `PFT_COL[10]` instead

#### config: dict
| Key | Type | Description |
|-----|------|-------------|
| `"param_names"` | list[str] | Shorthand names matching param_matrix columns |
| `"pft_ids"` | list[int] | PFT IDs for this site, e.g. [7, 9, 10] |
| `"use_case_dir"` | str | Path to use case directory |

#### Parameter name convention
`config["param_names"]` contains **shorthand names** from the ensemble list.
Use the EXACT names from the "Parameters in Current Morris Ensemble" section above.

Example ensemble entries:
```
  9. vmax_p_7      46. vmax_p_10      139. turnover_fnrt_7
  11. pid_kp_7     48. pid_kp_10      147. fnrt_prof_a_10
```

**ALWAYS use safe lookup:**
```python
def _safe_index(param_names, name):
    try:
        return param_names.index(name)
    except ValueError:
        return None

param_names = config["param_names"]
idx = _safe_index(param_names, "vmax_p_10")
if idx is not None:
    values = param_matrix[:, idx]
```

**WRONG:** bare `param_names.index("vmax_p_10")` without try/except — crashes if not found.

### Script Requirements

Your script must define a `test_hypothesis` function:

```python
def test_hypothesis(param_matrix, y_outputs, screening_data, config):
    import numpy as np

    # Build PFT column mapping
    pft_ids = config.get("pft_ids", [7, 9, 10])
    PFT_COL = {pft: i for i, pft in enumerate(pft_ids)}
    param_names = config["param_names"]

    def _safe_index(names, name):
        try:
            return names.index(name)
        except ValueError:
            return None

    # Access parameter: use EXACT shorthand
    idx = _safe_index(param_names, "vmax_p_10")
    if idx is None:
        return {"supported": False, "confidence": 0.0,
                "evidence": {"error": "vmax_p_10 not found"}, "insights": []}
    vmax_p_values = param_matrix[:, idx]

    # Access biomass: use correct key and PFT_COL
    froot = y_outputs.get("froot_biomass")
    if froot is None:
        return {"supported": False, "confidence": 0.0,
                "evidence": {"error": "froot_biomass not in y_outputs"}, "insights": []}
    froot_pft10 = froot[:, PFT_COL[10]]

    # Your analysis here...
    corr = np.corrcoef(vmax_p_values, froot_pft10)[0, 1]

    return {
        "supported": corr > 0.3,
        "confidence": min(0.9, abs(corr)),
        "evidence": {"correlation": float(corr)},
        "insights": [f"vmax_p–froot correlation: {corr:.3f}"]
    }
```

### How to Specify a Custom Script

In `existing_data_test`, set method to "custom_script" and include the code:

```json
{
    "method": "custom_script",
    "description": "Test if P uptake scales with vmax_p across ensemble",
    "script_name": "test_p_uptake_scaling",
    "script_code": "def test_hypothesis(param_matrix, y_outputs, screening_data, config):\\n    ..."
}
```

### Naming Convention (IMPORTANT)

**script_name MUST start with `test_`** (e.g., `test_p_uptake_scaling`, `test_root_depth_impact`).

Scripts named `test_*.py` that define `test_hypothesis()` are auto-discovered by the orchestrator
and automatically appear in the diagnostic tools inventory. Scripts with other naming patterns
require manual wiring and will NOT be auto-discovered.

The function MUST be named `test_hypothesis` (not `run_test`, `analyze`, etc.).

### Guidelines for Custom Scripts

1. **Keep it focused** - Test ONE specific aspect of the hypothesis
2. **Use numpy/scipy** - Standard scientific Python libraries are available
3. **Return structured results** - Always return the required dict format
4. **Handle edge cases** - Check for empty arrays, missing data, None
5. **No side effects** - Don't modify files or state outside the function
6. **Use EXACT shorthand names** - From the "Parameters in Current Morris Ensemble" list
7. **ALWAYS use safe lookup** - Wrap param_names.index() in try/except; NEVER use bare .index()
8. **Use PFT_COL mapping** - Build from config["pft_ids"]; NEVER hardcode column indices
9. **Use correct y_outputs keys** - "leaf_biomass", "froot_biomass", "agb_biomass" (2D arrays)
10. **All evidence values must be JSON-serializable** - Use float(), int() to convert numpy scalars
11. **Name starts with test_** - e.g., `test_p_uptake_scaling` (enables auto-discovery when promoted)
'''
