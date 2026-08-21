# A2MC Tools Reference

**Purpose:** Detailed reference for A2MC tools and utilities.
**Summary:** Read this when working on specific tools (phase logger, workflow status, knowledge extraction, ensemble management, cost functions, AI config).
**Referenced from:** `CLAUDE.md` → various tool sections

---

## Cost Functions & Optimization

**Modules:** `tools/cost_functions.py`, `tools/optimize_function.py`

Generic error metrics (RE, RMSE, NRMSE, NSE, KGE) and ensemble optimization against validation targets.

**Quick usage:**
```python
from tools.cost_functions import CostFunction, aggregate_costs
from tools.optimize_function import Target, OptimizationConfig, optimize_ensemble

# Compute relative error
cost_fn = CostFunction(method='relative_error')
error = cost_fn.compute(simulated=150.0, observed=174.2)

# Run ensemble optimization
result = optimize_ensemble(simulated_data, targets, config)
```

**Details:** See `memory/logs/20260115a_CostFunction_OptimizeFunction_Implementation.md`

---

## Phase Logging (`tools/phase_logger.py`)

Detailed Markdown logging for each A2MC phase, capturing full AI reasoning for knowledge extraction.

### Log Filename Format

```
Phase 0-2:   r{RR}_{session_id}_Title.md
Phase 3-6:   r{RR}_c{EE}_iter{II}_{session_id}_Title.md
```

- `RR` = calibration_round (outermost Phase 0→7 loop)
- `EE` = experiment_count (outer loop: full 3→4→5→6 experiment cycles)
- `II` = iteration (Phase 3&4: skip_testing_count+1; Phase 5&6: overall iteration)
- `session_id` = `YYYYMMDD_HHMMSS` timestamp matching the run log (`a2mc_run_{session_id}.log`)

```
use_cases/{site}/memory/logs/
├── phase2_screening/
│   └── r02_20260210_143052_Ensemble_Screening.md
├── phase3_diagnosis/
│   ├── r02_c00_iter01_20260210_143052_PFT10_Root_Cause.md
│   └── r02_c00_iter03_20260210_143052_Revised_Diagnosis.md
├── phase4_hypothesis/
│   └── r02_c00_iter02_20260210_143052_P_Limitation.md
├── phase5_testing/
│   └── r02_c00_iter01_20260210_143052_Experiment_Design.md
└── phase6_refinement/
    └── r02_c00_iter01_20260210_143052_Lessons_Learned.md
```

### Usage

```python
from tools.phase_logger import PhaseLogger

# Initialize with full iteration context
logger = PhaseLogger(site_dir="use_cases/ELM-FATES_Kougarok", site_name="Kougarok",
                     calibration_round=2, iteration=2,
                     experiment_count=1, skip_testing_count=3)

# Update all counters (call before each phase log)
logger.set_iteration_context(calibration_round=2, iteration=3,
                             experiment_count=1, skip_testing_count=0)

# Find logs by iteration context
logs = logger.find_logs_by_iteration(3, calibration_round=2, experiment_count=0, iteration=1)
```

### Log Content

Each Markdown log contains:
- **Header:** Site, phase, round, experiment, iteration, date, confidence
- **AI Reasoning:** Full detailed analysis and thinking
- **Iteration Context block:** Machine-readable JSON with all counters (appended to every log)

### Orchestrator Integration

The orchestrator syncs all counters before each phase log via `set_iteration_context()`.

**Details:** See `memory/logs/20260210c_SkipTesting_UX_and_CumulativeInsights.md`

Logs are automatically written to `use_cases/{site}/memory/logs/{session_id}/phase{N}_{name}/` (falls back to flat `logs/phase{N}_{name}/` without session_id).

---

## Workflow Status Tracking (`tools/workflow_status.py`)

Master workflow status tracker that maintains `memory/workflow_log.json`. Enables quick status checks without parsing detailed state files.

### Quick Status Check

```bash
# From command line
python tools/workflow_status.py

# Detailed with log file paths
python tools/workflow_status.py --detailed

# JSON output for scripts
python tools/workflow_status.py --json
```

### Console Output Example

```
==================================================
A2MC Workflow Status
==================================================
Status:     > RUNNING
Phase:      3 - DIAGNOSIS
Iteration:  2
Running:    2h 30m 15s

Phase History:
  [OK] Phase 0 (design) (2.0m)
  [OK] Phase 1 (exploration) (45.3m)
  --> Phase 3 (diagnosis) (15m in progress)
  [ ] Phase 4 (hypothesis)

Check results: memory/phase_results/{session_id}/phase3_diagnosis/
==================================================
```

### Python API

```python
from tools.workflow_status import WorkflowStatus, show_status, get_status

# Quick status check
show_status()

# Get status as dict
status = get_status()
print(f"Current phase: {status['current_phase_name']}")
print(f"Check logs at: {status['check_logs_at']}")

# Full programmatic access
ws = WorkflowStatus()
ws.start_phase(3, "diagnosis", iteration=2)
ws.complete_phase(3, "diagnosis", log_file="20260115_diagnosis.json")
```

### Integration with Orchestrator

The orchestrator automatically updates workflow status at:
- Workflow start: `start_workflow()`
- Phase entry: `start_phase()`
- Phase completion: `complete_phase()`
- Phase/workflow failure: `fail_phase()`, `fail_workflow()`
- Convergence: `complete_workflow()`

---

## AI Knowledge Extraction (`tools/extract_knowledge.py`)

Reads phase logs and extracts knowledge to `memory/data/` using AI reasoning.

### Purpose

After each A2MC iteration, the knowledge extractor:
1. Reads JSON logs from completed phases
2. Uses Claude API to identify discoveries, parameter insights, and failed approaches
3. Updates `memory/data/` (discoveries.json, parameters.json, failed_approaches.json)
4. Generates iteration summaries

### Usage

```python
from tools.extract_knowledge import KnowledgeExtractor
from reasoning import ReasoningEngine

# Initialize with reasoning engine for AI extraction
reasoning = ReasoningEngine(api_key="...")
extractor = KnowledgeExtractor(
    log_dir="memory/logs",
    memory_dir="memory/data",
    reasoning=reasoning,
    auto_save=True  # Automatically update memory files
)

# Extract from all recent logs (last 24 hours)
knowledge = extractor.extract_all(since_hours=24)
# Returns: {'discoveries': [...], 'parameters': [...], 'failed_approaches': [...]}

# Extract from specific phase
phase_knowledge = extractor.extract_from_phase(phase=6)  # Refinement

# Extract and summarize an entire iteration
iteration_knowledge = extractor.extract_iteration(iteration=1)
```

### Extraction Methods

| Method | Input | Output |
|--------|-------|--------|
| `extract_all()` | Recent logs (configurable hours) | Combined knowledge |
| `extract_from_phase()` | Single phase logs | Phase-specific knowledge |
| `extract_iteration()` | All phases for iteration | Iteration summary + knowledge |

### Knowledge Types Extracted

| Type | Description | Destination |
|------|-------------|-------------|
| Discoveries | Mechanistic insights (e.g., "Allocation Paradox") | `discoveries.json` |
| Parameter insights | Bounds, sensitivities, interactions | `parameters.json` |
| Failed approaches | What NOT to try again | `failed_approaches.json` |

### Integration with A2MC Workflow

```
Phase 6 (REFINEMENT)
    ↓
PhaseLogger.log_refinement()
    ↓
extract_knowledge.py reads logs
    ↓
AI analyzes results → extracts knowledge
    ↓
Updates memory/data/*.json
    ↓
Phase 0 (next iteration) uses updated memory
```

---

## AI Analysis in Screening Phase (`reasoning/methods.py`)

The `analyze_screening_results()` method provides AI analysis BEFORE diagnosis.

### Purpose

After optimization ranking (Phase 2), this method analyzes patterns in screening results
to inform the diagnosis phase:
- Error distribution patterns across targets
- Edge cases (parameters at bounds)
- Success patterns (what worked)
- PFT trade-offs (multi-objective conflicts)

### Usage

```python
from reasoning import ReasoningEngine

reasoning = ReasoningEngine(api_key="...")

analysis = reasoning.analyze_screening_results(
    screening_results=result,           # From optimize_ensemble()
    targets=targets,                    # Target definitions
    parameter_sets=parameter_values,    # Parameter values for top sets
    morris_rankings=morris_sensitivity  # Optional: Morris μ* rankings
)

# Returns:
# {
#     'error_patterns': {...},       # By-target error distributions
#     'edge_cases': [...],           # Parameters at bounds
#     'success_patterns': {...},     # What correlates with low cost
#     'pft_tradeoffs': {...},        # Multi-objective conflicts
#     'recommendations': [...],      # Suggested next steps
#     'knowledge_entries': [...]     # For memory persistence
# }
```

---

## Ensemble Management Tools

### Two-Level Configuration

**Configuration hierarchy:**
1. `a2mc_config.sh` - Machine-level defaults (HPC paths, COMPSET, Python env)
2. `use_cases/{site}/config/{site}_config.sh` - ALL site-specific settings

### Central Configuration (`a2mc_config.sh`)

**Machine-level configuration.** Includes auto-activation of Python environment.

**Key settings:**
```bash
# Auto-activates ~/a2mc_env Python environment when sourced

# Sampling scheme and dynamic ensemble size
export A2MC_SAMPLING_SCHEME="morris"  # morris, lhs, sobol, custom
export A2MC_N_PARAMS=162
export A2MC_N_TRAJECTORIES=30    # For Morris
export A2MC_N_SAMPLES=1000       # For LHS/Sobol
export A2MC_TOTAL_ENSEMBLE=$(calculate_ensemble_size)  # Auto-calculated

# COMPSET configuration by phase
export A2MC_COMPSET_SPINUP="1850_DATM%QIA_ELM%BGC-FATES_SICE_SOCN_SROF_SGLC_SWAV"
export A2MC_COMPSET_TRANS="2000_DATM%QIA_ELM%BGC-FATES_SICE_SOCN_SROF_SGLC_SWAV"

# HPC settings
export A2MC_PROJECT="m2467"
export A2MC_E3SM_ROOT="/path/to/E3SM"
export A2MC_OUTPUT_ROOT="/path/to/output"
```

### Site Configuration (`use_cases/{site}/config/{site}_config.sh`)

**All site-specific settings:**
```bash
export A2MC_SITE_NAME="YourSite"
export A2MC_PFTS="7,9,10"
export A2MC_PARAM_LIST_FILE="${A2MC_USE_CASE_DIR}/parameters/param_list.txt"
export A2MC_VALIDATION_FILE="${A2MC_USE_CASE_DIR}/validation/targets.txt"

# Case naming pattern (uses {N} for case number, {PHASE} for simulation phase)
export A2MC_CASE_NAME_PATTERN="${A2MC_ENSEMBLE_PREFIX}_PtCNPEn{N}_{PHASE}"
# Default (if not set): "${A2MC_ENSEMBLE_PREFIX}{N}_{PHASE}"
```

### Case Name Pattern (`A2MC_CASE_NAME_PATTERN`)

All scripts that reference case directories or output files use this configurable pattern instead of hardcoded names. The pattern uses `{N}` for case number and `{PHASE}` for simulation phase (ADSP, RGSP, TRANS).

**Python API (`tools/config.py`):**
```python
from tools.config import config

# Get pattern string
pattern = config.CASE_NAME_PATTERN  # e.g., "Kougarok_ELM-FATES_PtCNPEn{N}_{PHASE}"

# Build case name
case_name = config.make_case_name(case_num=322, phase='TRANS')
# → "Kougarok_ELM-FATES_PtCNPEn322_TRANS"
```

**Scripts using this pattern:**
| Script | How It Uses Pattern |
|--------|---------------------|
| `tools/diagnose_ensemble_status.py` | Find case directories, build restart scripts |
| `tools/extract_monthly_variables_FATES.py` | Build case names for NetCDF extraction |
| `phases/phase1_exploration/extract_sensitivity_outputs.py` | Locate case output directories |
| `phases/phase2_screening/screen_ensemble.py` | Scan extracted files, load timeseries |
| `phases/phase2_screening/compare_biomass_topcases.py` | Scan extracted files, load timeseries |

**Dynamic ensemble size formulas:**
| Scheme | Formula | Example |
|--------|---------|---------|
| Morris | trajectories × (params + 1) | 30 × 163 = 4890 |
| LHS | n_samples | 1000 |
| Sobol | samples × (2×params + 2) | 1000 × 326 = 326,000 |

**Usage:**
```bash
source a2mc_config.sh
source use_cases/ELM-FATES_Kougarok/config/kougarok_config.sh
print_config  # Show current settings
```

### Diagnose Ensemble Status (`tools/diagnose_ensemble_status.py`)

Scans ensemble output directory to identify completed/incomplete cases and generate restart scripts.

**Usage:**
```bash
# Diagnose all cases (default: 2-4890)
python tools/diagnose_ensemble_status.py

# Diagnose specific range with more workers
python tools/diagnose_ensemble_status.py --cases 100-500 --parallel 32

# Specify output directory
python tools/diagnose_ensemble_status.py --output-dir /path/to/output
```

**Output files generated:**
- `ensemble_status_report_TIMESTAMP.txt` - CSV with all case statuses
- `completed_cases_TIMESTAMP.txt` - List of completed case numbers (for extraction)
- `incomplete_cases_TIMESTAMP.txt` - Cases needing restart with phase/year/type
- `restart_incomplete_TIMESTAMP.sh` - Executable restart script
- `error_cases_TIMESTAMP.txt` - Cases with errors (creation failures, missing files)
- `recreate_cases_TIMESTAMP.txt` - Cases needing recreation (disk quota, permission errors)
- `recreate_cases_TIMESTAMP.sh` - Script to recreate failed cases

**Phase definitions:**
| Phase | Duration | Years | Final Restart |
|-------|----------|-------|---------------|
| ADSP | 200 yr | 1-200 | 201 |
| RGSP | 200 yr | 201-400 | 401 |
| TRANS | 119 yr | 1901-2019 | 2020 |

**Key features:**
- Uses restart files (`*.elm.r.*.nc`), NOT history output (`*.elm.h0.*.nc`)
- **Restart file size validation** - Skips 0-byte placeholder files (min 1KB)
- **Case creation validation** - Checks for case.submit, user_nl_elm, .case.run
- **Log file scanning** - Detects "Disk quota exceeded", "Permission denied", etc.
- Correctly handles fresh starts vs continues
- ADSP restarts: removes 2 lines from user_nl_elm (finidat, nyears_ad_carbon_only)
- RGSP/TRANS restarts: removes 1 line (old finidat), adds new finidat
- STOP_N formula: `end_year - restart_year + 1`

**Phase Chain Feature (automatic subsequent phase submission):**

When restarting an incomplete case, the script automatically submits ALL subsequent phases with SLURM dependencies:

| If stuck at | Submits | Dependency chain |
|-------------|---------|------------------|
| ADSP | ADSP → RGSP → TRANS | RGSP waits for ADSP, TRANS waits for RGSP |
| RGSP | RGSP → TRANS | TRANS waits for RGSP |
| TRANS | TRANS only | No dependency |

- **Job ID capture**: Extracts job IDs from `case.submit` output to set up dependencies
- **Auto-create missing phases**: If RGSP/TRANS cases weren't created, runs the case script first
- **SLURM dependency**: Uses `--dependency=afterok:$JOBID` to chain phases

Example generated script for ADSP restart:
```bash
# Case 123: Restart from ADSP (fresh)
# Phases to submit: ADSP → RGSP → TRANS

# --- ADSP Phase ---
cd /path/to/case_ADSP
SUBMIT_OUTPUT=$(./case.submit --batch-args="-q shared --mem=8G" 2>&1)
JOBID_ADSP_123=$(echo "$SUBMIT_OUTPUT" | grep -oP '(?:Submitted job id is |with id )\K[0-9]+')

# --- RGSP Phase ---
cd /path/to/case_RGSP
./case.submit --batch-args="-q shared --mem=8G --dependency=afterok:$JOBID_ADSP_123"
# ... captures JOBID_RGSP_123

# --- TRANS Phase ---
cd /path/to/case_TRANS
./case.submit --batch-args="-q shared --mem=8G --dependency=afterok:$JOBID_RGSP_123"
```

**Configuration:** Uses `A2MC_CASE_NAME_PATTERN` from site config (see "Case Name Pattern" section above). Other settings read from `a2mc_config.sh` and site config.

### Create Morris Ensemble Parameters (`tools/create_morris_ensemble_params.py`)

Generates FATES parameter files from Morris ensemble matrix.

### Extract Monthly Variables (`tools/extract_monthly_variables_FATES.py`)

Extracts monthly data from completed simulations for analysis.

**Usage:**
```bash
# Extract from list of completed cases
python tools/extract_monthly_variables_FATES.py --case-file completed_cases.txt
```

---

## AI Configuration

A2MC uses AI (Claude API by default) for reasoning in phases 2, 3, 4, and 6. Configuration is done via environment variables.

### Required: Set Your API Key

```bash
# Set your AI API key (required for AI-driven phases)
export AI_API_KEY="sk-ant-api03-..."
```

### Optional: Configure Model and Settings

```bash
# Choose AI model (default: claude-sonnet-4-20250514)
export A2MC_AI_MODEL="claude-sonnet-4-20250514"   # Balanced (default)
export A2MC_AI_MODEL="claude-opus-4-20250514"    # Most capable
export A2MC_AI_MODEL="claude-haiku-3-20240307"   # Fastest/cheapest

# Max tokens for AI responses (default: 4096)
export A2MC_AI_MAX_TOKENS=4096

# Use a different env var for API key (default: AI_API_KEY)
export A2MC_AI_API_KEY_ENV="MY_CUSTOM_KEY_VAR"
```

### Configuration in `a2mc_config.sh`

The AI settings are defined in `a2mc_config.sh`:

```bash
# AI CONFIGURATION
export A2MC_AI_MODEL="${A2MC_AI_MODEL:-claude-sonnet-4-20250514}"
export A2MC_AI_MAX_TOKENS="${A2MC_AI_MAX_TOKENS:-4096}"
export A2MC_AI_API_KEY_ENV="${A2MC_AI_API_KEY_ENV:-AI_API_KEY}"
```

### Verify Configuration

```bash
# Shell: source config and check settings
source a2mc_config.sh
print_config  # Shows AI settings including whether API key is set

# Python: check config
python -c "from tools.config import config; config.print_config()"
```

### Using in Python Code

```python
from reasoning import ReasoningModule

# Uses config automatically (AI_API_KEY env var, A2MC_AI_MODEL)
reasoning = ReasoningModule()

# Or override explicitly
reasoning = ReasoningModule(
    api_key="sk-ant-...",
    model="claude-opus-4-20250514"
)
```

### Resolution Order

| Setting | Resolution Order |
|---------|-----------------|
| API Key | 1. Explicit arg → 2. `config.get_ai_api_key()` → 3. `AI_API_KEY` env var |
| Model | 1. Explicit arg → 2. `A2MC_AI_MODEL` env var → 3. Default (sonnet) |
| Max Tokens | 1. Explicit arg → 2. `A2MC_AI_MAX_TOKENS` env var → 3. 4096 |
