# Phase 1: Exploration (Sensitivity Analysis)

**Purpose:** Analyze completed simulations and rank parameter sensitivities
**Status:** Starts when HPC simulations from Phase 0 are complete
**Inputs:** Completed TRANS simulation outputs, X matrix (parameter samples)
**Outputs:** Y matrix (aggregated outputs), Morris sensitivity rankings

---

## Prerequisites

Before starting Phase 1, verify simulations are complete:
```bash
python tools/diagnose_ensemble_status.py --cases 1-4890
# Should show >95% cases with TRANS phase complete
```

---

## What This Phase Does

1. **Diagnose ensemble status** - Identify completed/failed cases
2. **Restart incomplete cases** (if needed)
3. **Extract Y matrix** - Aggregate outputs from completed simulations
4. **Run Morris sensitivity analysis** - Rank parameter importance by PFT
5. **AI analysis of results** [AI] - Interpret rankings, write to knowledge base

---

## Scripts in This Folder

| Script | Purpose |
|--------|---------|
| `analyze_ensemble.py` | High-level Phase 1 driver: extraction → Y matrix → Morris → summary (extracted from `orchestrator.py`) |
| `extract_sensitivity_outputs.py` | Extract Y matrix for Morris analysis |
| `morris_sensitivity_analysis.py` | Run Morris analysis, rank parameters |

---

## Key Inputs

| Input | Source | Description |
|-------|--------|-------------|
| X matrix | Phase 0 | Parameter samples (`FATES_*_Morris_*.txt`) |
| Completed simulations | HPC | TRANS phase history files (`*.elm.h0.*.nc`) |
| SALib problem file | `use_cases/{site}/parameters/` | Parameter names and bounds |

---

## Key Outputs

| Output | Location | Description |
|--------|----------|-------------|
| Y matrix files | `phases/phase1_exploration/` | `Morris{Var}_{N}cases.txt` |
| Sensitivity rankings | `phases/phase1_exploration/` | CSV with μ, μ*, σ by parameter |
| Sensitivity plots | `phases/phase1_exploration/` | PNG visualization of top parameters |

---

## Shared Tools Used (in `tools/`)

| Tool | Purpose |
|------|---------|
| `tools/diagnose_ensemble_status.py` | Check which cases completed |
| `tools/config.py` | Load configuration (paths, PFTs, etc.) |
| `tools/fates_utils.py` | SZPF index calculations, PFT data handling |

---

## Checking Ensemble Status

Before starting Phase 1, verify simulations are complete:

```bash
# Check ensemble status
python tools/diagnose_ensemble_status.py --cases 1-4890

# Outputs:
# - completed_cases_TIMESTAMP.txt    → Use for Y matrix extraction
# - incomplete_cases_TIMESTAMP.txt   → Cases needing restart
# - restart_incomplete_TIMESTAMP.sh  → Script to restart failed cases
```

If >95% cases complete, proceed with Y matrix extraction.

---

## Success Criteria

- [ ] >95% of cases have TRANS phase complete
- [ ] Y matrix extracted for all output variables (leaf, fineroot, AGB)
- [ ] Morris analysis completed for each PFT
- [ ] Sensitivity rankings exported to CSV
- [ ] Top parameters identified (highest μ* values)

---

## Sensitivity Analysis Workflow

After simulations complete, run sensitivity analysis:

### Step 1: Extract Y Matrix

```bash
# Extract leaf biomass for all cases (mean of 2010-2019)
python extract_sensitivity_outputs.py \
    --output-var leaf_biomass \
    --cases 1-4890 \
    --validation-period 2010 2019 \
    --output-dir ./sensitivity_results

# Extract other variables
python extract_sensitivity_outputs.py --output-var fineroot_biomass --cases 1-4890
python extract_sensitivity_outputs.py --output-var abg_biomass --cases 1-4890
```

### Step 2: Run Morris Analysis

```bash
# Analyze sensitivity using extracted Y matrix
python morris_sensitivity_analysis.py \
    --output-var leaf_biomass \
    --y-matrix ./sensitivity_results/MorrisLeafbiomass_4890cases_2010_2019.txt \
    --problem use_cases/Kougarok/parameters/salib_problem_162params.json \
    --x-matrix use_cases/Kougarok/parameters/FATES_CNPnPlantTraits_162param_Morris_4890sets.txt \
    --output-dir ./sensitivity_results
```

### Outputs

| File | Description |
|------|-------------|
| `morris_{var}_{PFT}_*.csv` | Full Morris results by PFT |
| `morris_{var}_combined_rankings_*.csv` | Cross-PFT parameter rankings |
| `morris_{var}_sensitivity_*.png` | Visualization (top 10 by |μ|) |

---

## AI Analysis of Sensitivity Results [AI]

After Morris analysis, AI interprets the results:

### What AI Analyzes

1. **Parameter Importance (μ*)**
   - High μ* = parameter strongly affects output
   - Compare rankings across PFTs: which parameters matter for all vs specific PFTs?

2. **Parameter Interactions (σ)**
   - High σ/μ* ratio = parameter effect depends on other parameters
   - Indicates non-linear behavior, potential for optimization

3. **Cross-PFT Patterns**
   - Parameters that rank high for all PFTs → generic importance
   - Parameters that rank high for one PFT only → PFT-specific tuning needed

4. **Edge Effects**
   - Parameters at sampling bounds with high sensitivity → may need expanded ranges

### Knowledge Base Updates

| Discovery Type | Destination | Example |
|----------------|-------------|---------|
| Generic FATES mechanism | `memory/data/discoveries.json` | "PID controller (pid_kp) dominates allocation for all PFTs" |
| Site-specific pattern | `use_cases/{site}/memory/discoveries.json` | "At Kougarok, P-uptake parameters matter more than N-uptake" |
| Parameter insight | `memory/data/parameters.json` | "leaf_slatop has high μ* but also high σ - interacts with vcmax" |

### AI Analysis Command

```python
from reasoning import ReasoningModule

reasoning = ReasoningModule(use_rag=True)

# morris_rankings should be a dict with PFT keys, each containing
# a list of dicts: [{parameter, mu, mu_star, sigma, rank}, ...]
analysis = reasoning.analyze_sensitivity_results(
    morris_rankings={
        'PFT7': [{'parameter': 'fates_cnp_pid_kp_7', 'mu_star': 0.45, 'sigma': 0.12, ...}, ...],
        'PFT9': [...],
        'PFT10': [...]
    },
    pfts=['PFT7', 'PFT9', 'PFT10'],
    output_var='leaf_biomass',
    problem=salib_problem  # Optional: SALib problem dict with bounds
)

# Returns dict with:
# - key_parameters: Top parameters with mechanisms and priority
# - interactions: Parameters with high σ/μ* ratio
# - cross_pft_patterns: Generic vs PFT-specific parameters
# - edge_effects: Parameters needing expanded ranges
# - knowledge_entries: Auto-saved to memory/data/
# - recommendations: For diagnosis phase
# - summary: One-paragraph summary
```

---

## Next Phase

After Phase 1 completes → **Phase 2 (Screening)**: Rank ensemble by validation targets

---

## Common Issues

1. **Many NaN values in Y matrix:** Check which cases failed using `diagnose_ensemble_status.py`
2. **Memory error during extraction:** Process cases in batches, use `--resume`
3. **Missing history files:** Case may not have reached TRANS phase - restart from checkpoint
4. **Morris analysis fails:** Ensure X matrix rows match Y matrix rows (filter failed cases)

---

## When AI Works in This Phase

This guidance applies to **both** modes — the autonomous orchestrator traversing Phase 1, and the interactive (offline) agent navigating here. Offline skills for this phase: `summarize-calibration-round`, `compare-calibration-rounds` (see `docs/a2mc_reference/skills_catalog.md`).

**Focus on:**
- Diagnosing which cases completed vs failed
- Extracting Y matrices with appropriate aggregation periods
- Running Morris analysis and interpreting results
- Identifying most sensitive parameters for each PFT

**Do NOT:**
- Delete simulation output files
- Modify completed simulation results
- Skip cases without documenting why

---

## HPC-Specific Notes

- **Y matrix extraction** runs on login node (reads NetCDF, no heavy compute)
- **Morris analysis** runs on login node (SALib is fast)
- For large ensembles, use `--resume` flag if extraction is interrupted
