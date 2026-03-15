# A2MC: Agentic Adaptive Multi-target Calibration

**Status:** Implementation Complete
**Version:** 2.73
**Purpose:** Fully autonomous multi-target calibration of ELM-FATES using Claude API + HPC + Adaptive Memory

---

## Quick Start for New Users

### Step 1: Create Your Use Case

```bash
# Copy the Kougarok example (recommended) or the minimal template
cp -r use_cases/Kougarok use_cases/YourSite
# OR
cp -r use_cases/TEMPLATE use_cases/YourSite
```

### Step 2: Configure Site-Specific Settings

Edit your site configuration file with ALL site-specific settings:

```bash
vim use_cases/YourSite/config/yoursite_config.sh

# Key settings to modify:
# ========================
# SITE INFORMATION
export A2MC_SITE_NAME="YourSite"
export A2MC_SITE_LAT=45.0
export A2MC_SITE_LON=-120.0

# PFT CONFIGURATION
export A2MC_PFTS="1,2,3"                  # Your target PFTs
export A2MC_PFT_NAMES="PFT1,PFT2,PFT3"

# DOMAIN AND SURFACE DATA
export A2MC_DOMAIN_FILE="domain_yoursite.nc"
export A2MC_SURFACE_FILE="surfdata_yoursite.nc"

# PARAMETER CONFIGURATION
export A2MC_N_PARAMS=100                  # Number of parameters
export A2MC_N_TRAJECTORIES=30             # For Morris method
export A2MC_PARAM_LIST_FILE="${A2MC_USE_CASE_DIR}/parameters/your_param_list.txt"

# VALIDATION
export A2MC_VALIDATION_FILE="${A2MC_USE_CASE_DIR}/validation/your_targets.txt"

# HPC PATHS (ensemble output, parameter files)
export A2MC_PARAM_DIR="/path/to/fates_param_files"
export A2MC_ENSEMBLE_OUTPUT="${A2MC_OUTPUT_ROOT}/YourEnsemble"
```

### Step 3: Define Parameters and Validation Targets

Create these files in your use case folder:

```bash
# Parameter list with bounds
vim use_cases/YourSite/parameters/your_param_list.txt

# SALib problem definition (optional, for sensitivity analysis)
vim use_cases/YourSite/parameters/salib_problem.txt

# Validation targets
vim use_cases/YourSite/validation/your_targets.txt
```

### Step 4: Modify Machine Settings

Only edit `a2mc_config.sh` if you need to change HPC-level settings:

```bash
vim a2mc_config.sh

# Settings that might need changing:
export A2MC_PROJECT="your_project"        # HPC allocation
export A2MC_E3SM_ROOT="/path/to/E3SM"     # E3SM source code
export A2MC_OUTPUT_ROOT="/path/to/output" # Simulation output root
```

### Step 5: Configure AI Settings

AI reasoning is required for phases 2, 3, 4, and 6. Two things to configure:

**5a. Choose your AI provider** — edit `A2MC_AI_PROVIDER` in `a2mc_config.sh` (one-time):

```bash
# In a2mc_config.sh, set ONE of these (default is anthropic):
export A2MC_AI_PROVIDER="anthropic"   # Direct Anthropic API (default)
# export A2MC_AI_PROVIDER="openai"    # Direct OpenAI API
# export A2MC_AI_PROVIDER="cborg"     # Berkeley Lab CBorg proxy
```

Each provider has a default model (set automatically when you source `a2mc_config.sh`):

| Provider | Default Model | Other Models |
|----------|---------------|--------------|
| `anthropic` | `claude-opus-4-20250514` | `claude-sonnet-4-20250514`, `claude-haiku-3-20240307` |
| `openai` | `gpt-4o` | `gpt-4o-mini`, `o3-mini` |
| `cborg` | `anthropic/claude-sonnet` | `openai/gpt-4o`, `openai/gpt-4o-mini`, `lbl/llama` |

To override the model, set `A2MC_AI_MODEL` in `a2mc_config.sh`.

**5b. Set your API key** — add to `~/.bashrc` (one-time, must be done before sourcing `a2mc_config.sh`):

```bash
# Add the API key for your chosen provider to ~/.bashrc:
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.bashrc   # for anthropic
# echo 'export OPENAI_API_KEY="sk-..."' >> ~/.bashrc        # for openai
# echo 'export CBORG_API_KEY="sk-..."' >> ~/.bashrc         # for cborg

# Then reload:
source ~/.bashrc
```

**Note:** Keep your API key visible only to yourself (e.g., `chmod 600 ~/.bashrc`).

### Step 6: Run A2MC

```bash
# Source BOTH configuration files
source a2mc_config.sh
source use_cases/YourSite/config/yoursite_config.sh
print_config  # Verify settings

# Run calibration
python orchestrator.py --run
```

**Configuration hierarchy:**
- `a2mc_config.sh` - Machine-level defaults (HPC paths, COMPSET, Python env, simulation protocol, AI provider)
- `use_cases/{site}/config/{site}_config.sh` - Site-specific overrides (PFTs, parameters, validation targets, protocol overrides)

See "Running the Workflow" section below for more options.

---

## Overview

A2MC is an autonomous calibration framework that combines:
- **Morris/Sobol sensitivity analysis** for parameter space exploration
- **Claude API reasoning** for diagnosis and hypothesis generation
- **HPC-native execution** for efficient simulation management
- **Multi-objective optimization** for simultaneous PFT calibration
- **Adaptive Memory System** for learning from experiments and avoiding repeated failures

The framework runs entirely on NERSC HPC (no SSH tunneling) and uses the Anthropic Claude API for intelligent decision-making. The Adaptive Memory System enables the AI agent to persistently store and retrieve knowledge across sessions.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            A2MC FRAMEWORK                                   │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    ORCHESTRATOR (orchestrator.py)                      │ │
│  │                                                                        │ │
│  │   7-Phase State Machine with Iteration Paths:                          │ │
│  │                                                                        │ │
│  │   ┌─────────┐    ┌─────────────┐    ┌───────────┐    ┌───────────┐     │ │
│  │   │ Phase 0 │───►│   Phase 1   │───►│  Phase 2  │───►│  Phase 3  │     │ │
│  │   │ DESIGN  │    │ EXPLORATION │    │ SCREENING │    │ DIAGNOSIS │     │ │
│  │   └────▲────┘    └─────────────┘    └───────────┘    └─────┬─────┘     │ │
│  │        │                                                   │           │ │
│  │        │ Redesign:                       ┌─────────────────┤           │ │
│  │        │ Expand params                   │                 │           │ │
│  │        │                                 │           ┌─────▼─────┐     │ │
│  │   ┌────┴────┐    ┌──────────────┐    ┌───────────┐    │  Phase 4  │     │ │
│  │   │ Phase 7 │◄───│   Phase 6    │◄───│  Phase 5  │◄───│HYPOTHESIS │     │ │
│  │   │CONVERGED│    │  REFINEMENT  │    │  TESTING  │    └─────┬─────┘     │ │
│  │   └─────────┘    └──────┬───────┘    └───────────┘          │           │ │
│  │                         │                                   │           │ │
│  │                Rethink: │                      Skip test:   │           │ │
│  │                Hypothesis                      Use existing │           │ │
│  │                proven wrong                                 │           │ │
│  │                         └───────────────────────┬───────────┘           │ │
│  │                                                 │                      │ │
│  │                                                 ▼                      │ │
│  │                                         Back to Phase 3                │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                      │
│            ┌─────────────────────────┼─────────────────────────┐            │
│            ▼                         ▼                         ▼            │
│  ┌──────────────────┐    ┌───────────────────┐    ┌──────────────────┐      │
│  │    REASONING     │    │    INTEGRATION    │    │  EXISTING TOOLS  │      │
│  │  (reasoning/)    │    │  (integration.py) │    │                  │      │
│  │                  │    │                   │    │ modify_fates_    │      │
│  │ • diagnose()     │    │ • ParameterManager│◄──►│   parameters.py  │      │
│  │ • hypothesize()  │    │ • HPCExecutor     │    │                  │      │
│  │ • design_exp()   │    │ • DataPipeline    │◄──►│ extract_monthly_ │      │
│  │ • interpret()    │    │ • ExperimentRunner│    │   variables.py   │      │
│  │                  │    │                   │    │                  │      │
│  │  Claude API      │    │  Direct sbatch/   │    │ NetCDF handling  │      │
│  │  (configurable)  │    │  squeue calls     │    │                  │      │
│  └──────────────────┘    └───────────────────┘    └──────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Tech Notes

### Install Anthropic and OpenAI on NERSC Perlmutter

```bash
# Load Python module
module load python

# Create a virtual environment (one-time setup)
python -m venv ~/a2mc_env
source ~/a2mc_env/bin/activate

# Install A2MC dependencies (including RAG)
# anthropic SDK for Anthropic provider; openai SDK for OpenAI/CBorg providers
pip install anthropic openai numpy pandas xarray netCDF4 scipy SALib networkx chromadb sentence-transformers pyyaml Pillow

# Set your API key (add to ~/.bashrc for persistence)
# Use the env var matching your provider: ANTHROPIC_API_KEY, OPENAI_API_KEY, or CBORG_API_KEY
export ANTHROPIC_API_KEY="your-api-key-here"

# Verify installation
python -c "import anthropic; print('anthropic', anthropic.__version__)"
python -c "import openai; print('openai', openai.__version__)"
```

**Note:** The virtual environment is auto-activated when you `source a2mc_config.sh`.

---

## 7-Phase Workflow

A2MC uses a 7-phase workflow with intelligent iteration paths to minimize HPC costs while maximizing learning.

### Phase Overview

| Phase | Name | Purpose | AI-Driven? | Scripts |
|-------|------|---------|------------|---------|
| 0 | DESIGN | Morris/Sobol sampling, create cases, submit to HPC | No | `create_morris_ensemble.py` |
| 1 | EXPLORATION | Extract Y matrix, run sensitivity analysis | **Yes** | `extract_sensitivity_outputs.py`, `morris_sensitivity_analysis.py` |
| 2 | SCREENING | Rank ensemble by validation targets | Yes | `screen_ensemble.py` |
| 3 | DIAGNOSIS | Root cause analysis, edge case detection | Yes | `run_diagnosis.py` (+ 11 diagnostic tools) |
| 4 | HYPOTHESIS | Generate experiments OR test with existing data | Yes | `reasoning/`, `phases/phase4_hypothesis/` |
| 5 | TESTING | Run designed experiments on HPC | No | `submit_experiments.py` (+ design, monitor) |
| 6 | REFINEMENT | Evaluate results, extract lessons, check equifinality | Yes | `reasoning/`, `phases/phase6_refinement/` |
| 7 | CONVERGED | Final optimal configuration | - | - |

**Phase 3 Diagnostic Tools:** `analyze_carbon_balance.py`, `analyze_mortality.py`, `analyze_nutrient_balance.py`, `analyze_nutrient_pools.py`, `check_edge_parameters.py`, `compare_case_parameters.py`, `compare_targets.py`, `detect_collapse.py`, `diagnose_pft_limitations.py`, `read_case_parameters.py`, `test_hypothesis_framework.py`

**Phase 5 Scripts:** `design_experiments.py`, `monitor_experiments.py`, `submit_experiments.py`

### Iteration Paths

A2MC supports non-linear iteration to avoid unnecessary HPC computation:

```
Normal Flow:
  Phase 0 → [HPC] → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → [HPC] → Phase 6 → Phase 7

Iteration Paths:
  Phase 4 → Phase 3: Skip testing when existing data can test hypothesis
  Phase 6 → Phase 3: Rethink hypothesis when experiment results disprove it
  Phase 6 → Phase 0: Redesign when parameter space needs expansion
```

**Phase 4 → Phase 3 (Skip Testing):**
When a hypothesis can be tested using existing ensemble data (e.g., P mass balance analysis, comparing PFT responses), skip the HPC testing phase and return to diagnosis with new insights.

**Phase 6 → Phase 3 (Rethink Hypothesis):**
When experiment results disprove the hypothesis, return to diagnosis to revise understanding and generate new hypotheses.

**Phase 6 → Phase 0 (Redesign):**
When all parameter candidates are at bounds and calibration fails, expand parameter ranges and run a new ensemble.

### Three-Level Iteration Structure

A2MC uses three nested loops:

**Calibration Round (Outermost):** Full Phase 0 → 7 cycle
- Round 1: e.g., 138 parameters, 4170 simulations
- Round 2: e.g., 162 parameters, 4890 simulations (expanded parameter space)
- Incremented when Phase 6 → Phase 0 redesign is needed

**Inner Loop (Skip Testing):** Phase 3 ↔ 4, max 10 cycles
- Test hypotheses with existing ensemble data (no HPC cost)
- Exit when confidence threshold met OR max cycles reached
- Counter resets when entering Phase 5 (HPC)

**Outer Loop (Experiments):** Phase 3 → 4 → 5 → 6, max 10 cycles
- Run full HPC experiments
- Exit when targets met OR max experiments reached

```bash
# Control iteration limits
python orchestrator.py --run \
    --start-iteration 2 \          # Calibration round (outermost loop)
    --max-skip-testing 10 \        # Max Phase 3↔4 cycles (default: 10)
    --max-experiments 10 \         # Max full experiment cycles (default: 10)
    --confidence-threshold 0.95    # Exit skip testing threshold (default: 0.95)
```

### Phase Details

#### Phase 0: DESIGN
**Purpose:** Create initial parameter sampling design and submit to HPC

```bash
# Morris method: n_trajectories × (n_params + 1) simulations
# Example: 30 trajectories × 163 params = 4890 simulations
python orchestrator.py --run --start-phase 0
```

**Outputs:**
- Morris ensemble matrix (X matrix): `phases/phase0_design/FATES_*_Morris_*sets.txt`
- Modified parameter files for each ensemble member
- HPC jobs submitted to queue

#### Phase 1: EXPLORATION
**Purpose:** Extract results and run Morris sensitivity analysis

**Key operations:**
1. Extract Y matrix (model outputs) from completed simulations
2. Run Morris sensitivity analysis using SALib
3. Rank parameters by μ* (mean absolute effect) and σ (interaction effect)
4. Generate sensitivity plots and CSV rankings

**Outputs:**
- Y matrices: `MorrisLeafbiomass_*.txt`, `MorrisFineroootbiomass_*.txt`, `MorrisAbgbiomass_*.txt`
- Sensitivity rankings by PFT (top parameters with μ*, σ values)
- Sensitivity plots (PNG)

**Command-line usage:**
```bash
python orchestrator.py --run --start-phase 1 --start-iteration 2
# Or equivalently:
python orchestrator.py --run --start-phase phase1 --start-iteration 2
python orchestrator.py --run --start-phase exploration --start-iteration 2
```

#### Phase 2: SCREENING
**Purpose:** Rank ensemble members against validation targets

**Analysis:**
- Calculate cost metrics (RMSRE, NRMSE) across all targets
- Rank all simulations by multi-objective performance
- Identify which targets are met/failed for each case
- Detect edge cases (parameters at bounds)

**Outputs:**
- Ranked case list with composite cost
- Per-target error statistics
- Edge parameter analysis

#### Phase 3: DIAGNOSIS
**Purpose:** Root cause analysis of calibration failures

**Claude API tasks:**
- Analyze which targets are failing and why
- Identify mechanistic causes (e.g., P-limitation, allocation issues)
- Find cross-PFT parameter conflicts
- Compare best vs worst cases to identify key differences
- Generate parameter adjustment recommendations

**Output:** Diagnosis report with root causes, affected mechanisms, and priority rankings

#### Phase 4: HYPOTHESIS
**Purpose:** Generate testable hypotheses

**Claude API tasks:**
- Create named hypotheses (e.g., "PFT10 P-starvation hypothesis")
- Specify parameters to modify and expected direction
- Define expected outcomes and success criteria
- Choose approach:
  - **Run experiments:** Submit new simulations to test hypothesis
  - **Use existing data:** Test hypothesis with existing ensemble (e.g., mass balance analysis)

**Output:** Hypothesis with modification plan or analysis plan

#### Phase 5: TESTING
**Purpose:** Run designed experiments on HPC

**Key operations:**
- Create modified parameter files based on hypothesis
- Submit experiment simulations to HPC
- Extract and evaluate results
- Compare actual outcomes to expected outcomes

#### Phase 6: REFINEMENT
**Purpose:** Evaluate results and extract lessons

**Decision logic:**
- If hypothesis confirmed → apply changes, check if more targets remain
- If partially confirmed → adjust hypothesis, return to Phase 4
- If rejected → record failed approach, return to Phase 3
- If all targets met → advance to CONVERGED
- If parameter bounds too restrictive → return to Phase 0 (redesign)

**Adaptive Memory Learning:**
- Extract lessons from experiment outcomes
- Store successful discoveries in `gained_knowledge/discoveries.json`
- Record failed approaches in `gained_knowledge/failed_approaches.json`
- Update parameter knowledge for future reasoning
- Check for equifinality (multiple parameter sets achieving same targets)

#### Phase 7: CONVERGED
**Purpose:** Finalize calibration

**Outputs:**
- Best parameter configuration
- Final calibration report
- Complete experiment history
- Extracted knowledge for future calibrations

---

## Validation Targets

Validation targets are site-specific and defined in `use_cases/{site}/README.md`.

**Typical target types:**
- **Biomass:** Leaf, fine root, AGB by PFT (g C/m²)
- **Ecosystem fluxes:** GPP, NPP, NEE (g C/m²/yr)
- **Structure:** LAI, canopy height
- **Phenology:** Leaf-on/off dates

**See example:** `use_cases/Kougarok/README.md` for a complete target specification.

---

## Module Reference

### orchestrator.py

Main workflow controller with state persistence. Configuration is loaded from environment variables set by `a2mc_config.sh` and site config.

```python
from orchestrator import CalibrationOrchestrator, Config

# Config auto-detects paths from A2MC_USE_CASE_DIR environment variable
config = Config(
    use_memory=True,           # Enable Adaptive Memory
    use_reasoning=True,        # Enable Claude API reasoning
    max_iterations=10,
    max_skip_testing=10,       # Max Phase 3↔4 skip testing cycles
    max_experiments=10,        # Max Phase 3→4→5→6 experiment cycles
)
orch = CalibrationOrchestrator(config)
orch.run()
```

**Key Classes:**
- `Config` - All settings (paths, HPC, sampling, AI, iteration limits)
- `Phase` - Enum of 8 workflow phases
- `WorkflowState` - Persistent state with full history
- `CalibrationOrchestrator` - Main controller

### reasoning/ package

Claude API interface for intelligent reasoning (split into `schemas.py`, `prompts.py`, `base.py`, `methods.py`).

```python
from reasoning import ReasoningModule, Diagnosis, Hypothesis

# Initialize (uses provider-specific API key env var and A2MC_AI_MODEL config)
reasoning = ReasoningModule()

# Diagnose calibration failure
diagnosis = reasoning.diagnose(
    results={"leaf_pft10": 45.2, ...},
    targets={"leaf_pft10": {"mean": 82.7, "uncertainty": 0.20}, ...},
    sensitivity_rankings={"leaf_pft10": [{"param": "...", "mu_star": 0.45}]},
    iteration=1
)

# Generate hypothesis
hypothesis = reasoning.generate_hypothesis(
    diagnosis=diagnosis,
    sensitivity_data={...},
    previous_experiments=[]
)

# Design experiment
experiments = reasoning.design_experiments(
    hypothesis=hypothesis,
    base_case={"case_id": 2678, "parameters": {...}}
)

# Interpret results
interpretation = reasoning.interpret_results(
    experiment=experiments[0],
    actual_results={...},
    targets={...}
)
```

**Output Structures:**
- `Diagnosis` - Failing targets, causes, parameter/protocol recommendations, requested diagnostics
- `Hypothesis` - Name, mechanism, parameter modifications, test plan
- `Experiment` - Base case, modifications, expected results

### integration.py / tools/hpc_utils.py

HPC-native interfaces for simulation management. Core classes (`HPCConfig`, `HPCExecutor`, `ParameterManager`) are in `tools/hpc_utils.py`; `integration.py` provides backward-compatible imports and the `DataPipeline`/`ExperimentRunner` classes.

```python
from tools.hpc_utils import HPCConfig, HPCExecutor, ParameterManager

# HPCConfig reads from A2MC_* environment variables
config = HPCConfig()

# Modify parameters
param_mgr = ParameterManager(config)
new_param_file = param_mgr.create_modified_file(
    base_file="fates_params.nc",
    modifications=[
        {"parameter": "fates_alloc_storage_cushion", "pft": 10, "value": 3.0}
    ],
    output_file="fates_params_modified.nc"
)

# Submit jobs
executor = HPCExecutor(config)
job_id = executor.submit_case(case_name="PtCNPEn100_TRANS")

# Wait for completion
results = executor.wait_for_jobs([job_id], poll_interval=300)
```

**Key Classes:**
- `HPCConfig` - HPC paths, project, QOS (from env vars)
- `HPCExecutor` - Direct sbatch/squeue execution
- `ParameterManager` - Wraps modify_fates_parameters.py
- `DataPipeline` - Wraps extract_monthly_variables_FATES.py
- `ExperimentRunner` - High-level experiment coordinator

---

## Three-Tier FATES Knowledge System

A2MC uses a three-tier architecture for FATES knowledge, ensuring the AI has access via multiple retrieval paths:

| Tier | Location | Format | Purpose |
|------|----------|--------|---------|
| **Static Documentation** | `docs/fates-knowledge-base/` | Markdown | Human reference, RAG indexing |
| **RAG/GraphRAG** | `rag/` | ChromaDB + JSON graph | AI semantic search, graph traversal |
| **Adaptive Memory** | `memory/gained_knowledge/` | JSON | AI reasoning context, learned discoveries |

**Key resources for CNP calibration:**
- **START HERE:** `docs/fates-knowledge-base/fates-codebase-wiki/advanced/cnp_calibration_guide.md` (Knox 2026)
- PID controller: `docs/fates-knowledge-base/fates-codebase-wiki/plant-physiology/parteh/cnp_allocation.md`
- ECA/RD competition: `docs/fates-knowledge-base/fates-codebase-wiki/advanced/nutrient_competition.md`
- Nutrient uptake: `docs/fates-knowledge-base/fates-codebase-wiki/plant-physiology/parteh/soil_plant_interface.md`

---

## Adaptive Memory System

Two-tier knowledge architecture enabling learning across sessions while keeping site-specific knowledge separate.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   A2MC Knowledge System                          │
├─────────────────────────────────────────────────────────────────┤
│  GENERIC KNOWLEDGE (memory/gained_knowledge/)                   │
│  ─────────────────────────────────────────────                  │
│  • General FATES mechanistic insights                           │
│  • Applies to all sites                                         │
│                                                                  │
│  SITE-SPECIFIC KNOWLEDGE (use_cases/{site}/memory/)             │
│  ─────────────────────────────────────────────                  │
│  • Site-specific discoveries and experiments                    │
│  • Phase execution logs with AI reasoning                       │
│  • Lessons learned from site calibration                        │
│                                                                  │
│  KNOWLEDGE PROMOTION                                            │
│  ─────────────────────────────────────────────                  │
│  • AI evaluates site-specific discoveries                       │
│  • Generalizable lessons promoted to generic knowledge          │
└─────────────────────────────────────────────────────────────────┘
```

### Memory Stores

**Generic Knowledge** (`memory/gained_knowledge/`):

| Store | Purpose |
|-------|---------|
| `discoveries.json` | General FATES mechanistic insights |
| `experiments.json` | Generic experiment patterns |
| `parameters.json` | Parameter knowledge (not site-specific) |
| `failed_approaches.json` | Generic approaches to NOT repeat |

**Site-Specific Knowledge** (`use_cases/{site}/memory/gained_knowledge/`):

| Store | Purpose |
|-------|---------|
| `discoveries.json` | Site-specific insights (e.g., "Kougarok Allocation Paradox") |
| `experiments.json` | Site experiments with outcomes |
| `failed_approaches.json` | Site-specific approaches to NOT repeat |

**Phase Execution Logs** (`use_cases/{site}/memory/logs/`):

| Directory | Purpose |
|-----------|---------|
| `phase2_screening/` | Screening analysis logs (Markdown) |
| `phase3_diagnosis/` | Root cause analysis with AI reasoning |
| `phase4_hypothesis/` | Hypothesis generation logs |
| `phase6_refinement/` | Lessons learned and knowledge extraction |

### MemoryManager API

```python
from memory import MemoryManager

# Generic knowledge
memory = MemoryManager("memory/gained_knowledge")

# Site-specific knowledge
memory = MemoryManager("use_cases/Kougarok/memory/gained_knowledge")

# Query methods
context = memory.get_relevant_context(targets, parameters, phase)
failed = memory.get_failed_experiments(parameters)
knowledge = memory.get_parameter_knowledge("fates_alloc_storage_cushion")
stats = memory.stats()

# Update methods
memory.record_experiment(experiment_id, base_case, modifications, results, outcome)
memory.add_discovery(name, description, mechanism, affects, confidence)
memory.add_failed_approach(approach, experiment_id, why_failed, severity, alternatives)
memory.update_parameter_knowledge(param_name, knowledge)
```

### Integration with Reasoning

The `ReasoningModule` automatically queries memory during:
- **Diagnosis:** Retrieves relevant discoveries and parameter knowledge
- **Hypothesis Generation:** Checks failed approaches to avoid repetition
- **Refinement:** Extracts lessons and updates memory with new discoveries

### Knowledge Integration in AI Prompts

When A2MC performs diagnosis or generates hypotheses, three knowledge sources are combined into the Claude API prompt:

| Source | Content | Role |
|--------|---------|------|
| **RAG/GraphRAG** | FATES + ELM documentation (2,707 doc chunks + 560 CDL definitions) | General knowledge - "how does the PID controller work?" |
| **Adaptive Memory** | Discoveries, failed approaches, parameter insights | Learned knowledge - "what failed before? what worked?" |
| **Task Data** | Results, targets, sensitivity rankings | Current context - "what are we trying to calibrate?" |

**Prompt Structure (in order):**

```
┌─────────────────────────────────────────────────────────────┐
│  ## FATES Knowledge Base Context (RAG/GraphRAG)             │
│  [Vector search results from docs + Graph traversal]        │
│                                                             │
│  ## Adaptive Memory Context                                 │
│  [Relevant discoveries, FAILED APPROACHES - DO NOT REPEAT]  │
│                                                             │
│  ## Current Data                                            │
│  [Simulation results, validation targets, sensitivity]      │
│                                                             │
│  ## Task Instructions + Response Format                     │
└─────────────────────────────────────────────────────────────┘
```

**Key Safeguard:** The system explicitly marks failed approaches with "DO NOT REPEAT" and instructs Claude to avoid proposing them unless there's strong justification.

**No strict priority** - the sources serve complementary roles:
- RAG provides the "textbook" knowledge (how FATES mechanisms work)
- Memory provides the "experience" (what we learned from previous iterations)
- Both inform the AI's reasoning about the current task data

### Referencing Knowledge from Similar Sites

When calibrating a new site, you can reference knowledge from existing sites with similar characteristics:

| Your Site Type | Reference Site | Transferable Knowledge |
|----------------|----------------|------------------------|
| Arctic/tundra | `use_cases/Kougarok/` | Allocation Paradox, P-limitation dynamics, graminoid-shrub competition |
| CNP-enabled | `use_cases/Kougarok/` | PID controller behavior, ECA competition, vmax calibration strategies |

**What transfers:** Mechanistic insights, diagnostic patterns, failed approaches to avoid
**What doesn't transfer:** Exact parameter values (these are site-specific)

```python
# Reference another site's knowledge
from memory import MemoryManager

# Load Kougarok knowledge for reference
kougarok_memory = MemoryManager("use_cases/Kougarok/memory/gained_knowledge")

# Check discoveries relevant to your calibration
discoveries = kougarok_memory.discoveries.get('discoveries', [])
for d in discoveries:
    print(f"- {d['name']}: {d['description'][:80]}...")

# Check failed approaches to avoid
failed = kougarok_memory.failed_approaches.get('failed_approaches', [])
for f in failed:
    print(f"AVOID: {f['approach']}")
```

**See also:** `use_cases/Kougarok/README.md` → "Reference for Similar Sites" section for detailed applicability guidance.

### Seeding Memory

To seed memory with curated knowledge:

```bash
# Create curated_knowledge.yaml from template
cp scripts/curated_knowledge_template.yaml scripts/curated_knowledge.yaml
# Edit with your discoveries...

# Run seeding script
python scripts/seed_memory_from_yaml.py --input scripts/curated_knowledge.yaml
```

### Configuration

Enable memory in the orchestrator (paths auto-detected from environment):

```python
from orchestrator import CalibrationOrchestrator, Config

config = Config(
    use_memory=True,           # Enable Adaptive Memory (site + generic)
    use_reasoning=True,        # Enable Claude API reasoning
    max_skip_testing=10,       # Max Phase 3↔4 skip testing cycles
    max_experiments=10,        # Max full experiment cycles
)
orch = CalibrationOrchestrator(config)
orch.run()
```

---

## Installation & Setup

### On NERSC Perlmutter

```bash
# 1. Clone the repository
cd /global/homes/$USER
git clone https://github.com/jingtao-lbl/A2MC.git
cd A2MC

# 2. Set up Python environment (one-time setup)
module load python
python -m venv ~/a2mc_env
source ~/a2mc_env/bin/activate
pip install anthropic openai netCDF4 numpy scipy SALib pandas networkx chromadb sentence-transformers pyyaml Pillow

# 3. Set API key (add to ~/.bashrc for persistence)
# Use the env var matching your provider (see a2mc_config.sh → A2MC_AI_PROVIDER):
#   anthropic → ANTHROPIC_API_KEY, openai → OPENAI_API_KEY, cborg → CBORG_API_KEY
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.bashrc
source ~/.bashrc

# 4. Verify setup
python -c "import anthropic; print('Anthropic SDK OK')"
python -c "from orchestrator import CalibrationOrchestrator; print('Orchestrator OK')"
```

**Note:** After initial setup, the virtual environment is auto-activated when you `source a2mc_config.sh`.

### Running the Workflow

Before running, modify the two configuration files for your setup:

1. **`a2mc_config.sh`** — Machine-level settings (HPC project, E3SM path, output root, Python env, **AI provider**)
2. **`use_cases/{site}/config/{site}_config.sh`** — Site-specific settings (PFTs, parameters, validation targets, case naming)

```bash
# Source both configuration files (required before every run)
source a2mc_config.sh
source use_cases/Kougarok/config/kougarok_config.sh

# Start a new calibration run
python orchestrator.py --run

# Start from a specific phase and calibration round
python orchestrator.py --run --start-phase 2 --start-iteration 2

# Resume from a saved checkpoint (state-file auto-detected from config)
python orchestrator.py --resume
```

**Tip:** Use `screen` or `tmux` for long-running sessions on HPC.

```bash
# Monitor progress (main log file saved to use_cases/{site}/)
tail -f use_cases/Kougarok/a2mc_run_*.log
```

All screen output is automatically saved to `use_cases/{site}/a2mc_run_{timestamp}.log`.

---

## Experimental Design Strategies

### Cumulative Design
Test parameters sequentially, adding one at a time:

```
Exp1: param_A only
Exp2: param_A + param_B
Exp3: param_A + param_B + param_C
```

**Use when:** Parameters act through sequential mechanisms (A → B → C)

### Factorial Design
Test all combinations of parameters:

```
Exp1: param_A=low,  param_B=low
Exp2: param_A=low,  param_B=high
Exp3: param_A=high, param_B=low
Exp4: param_A=high, param_B=high
```

**Use when:** Parameters may interact (synergistic or antagonistic effects)

---

## State Persistence

All workflow state is saved to JSON for resumability:

```json
{
  "phase": "DIAGNOSIS",
  "iteration": 3,
  "start_time": "2025-01-06T10:30:00",
  "config": {
    "work_dir": "/pscratch/sd/j/jingtao/A2MC",
    "param_file": "fates_params.nc",
    "output_root": "/global/cfs/cdirs/m2467/jingtao/A2MC_runs"
  },
  "design": {
    "method": "morris",           // or "lhs", "sobol", "custom"
    "n_params": 162,
    "n_trajectories": 30,         // Morris: total = traj × (params+1)
    "n_samples": 1000,            // LHS/Sobol
    "total_ensemble": 4890        // Auto-calculated from scheme
  },
  "screening": {
    "top_cases": [2678, 845, 3930],
    "best_composite_nrmse": 0.493
  },
  "experiments": [
    {
      "name": "Exp1_storage_cushion",
      "base_case": 2678,
      "modifications": [...],
      "results": {...},
      "interpretation": {...}
    }
  ],
  "phase_history": [
    {"phase": "DESIGN", "completed": "2025-01-06T11:00:00"},
    {"phase": "EXPLORATION", "completed": "2025-01-08T14:30:00"}
  ]
}
```

---

## Integration with Existing Tools

A2MC wraps existing well-tested tools rather than reimplementing:

### Parameter Modification
```
modify_fates_parameters.py
├── create_modified_parameter_file(input, output, modifications)
├── Handles 1D/2D parameters
├── Supports absolute values or percent changes
└── Verifies modifications after applying
```

### Data Extraction
```
extract_monthly_variables_FATES.py
├── Extracts site-level, PFT-level, SZPF-level variables
├── Outputs NetCDF (all vars) + CSV (site/PFT only)
├── Processes yearly files (12 months each)
└── ~50-100× faster than daily extraction
```

### Job Submission
```
Direct SLURM commands:
├── sbatch case.submit
├── squeue -u $USER
├── scancel job_id
└── sacct -j job_id --format=...
```

---

## Error Handling

### Job Failures
- Automatic retry with exponential backoff
- Maximum 3 retries per job
- Log failed jobs for manual inspection

### API Errors
- Rate limiting with automatic backoff
- Fallback to rule-based reasoning if API unavailable
- Cache repeated queries to reduce costs

### Missing Data
- Verify expected files before proceeding
- Clear error messages with suggested fixes
- Option to skip incomplete cases

---

## Cost Management

### Claude API Usage
- **Diagnosis:** ~2K tokens input, ~1K output
- **Hypothesis:** ~3K tokens input, ~1K output
- **Experiment design:** ~2K tokens input, ~500 output
- **Interpretation:** ~2K tokens input, ~1K output

**Estimated cost per iteration:** ~$0.10-0.20 (Sonnet)

### HPC Resources
- **Morris ensemble (4890 sims):** ~50K node-hours
- **Single experiment:** ~10 node-hours
- **Data extraction:** ~0.1 node-hours per case

---

## Directory Structure

```
A2MC/
├── README.md              # This file
├── a2mc_config.sh         # Machine-level configuration (HPC paths, defaults)
├── orchestrator.py        # Main workflow controller
├── reasoning/             # Claude API interface (package)
│   ├── __init__.py        # Backward-compatible re-exports
│   ├── schemas.py         # Diagnosis, Hypothesis, Experiment dataclasses
│   ├── prompts.py         # DIAGNOSTIC_TOOLS_INVENTORY, CUSTOM_SCRIPT_TEMPLATE
│   ├── base.py            # ReasoningModule class core (init, query, RAG)
│   ├── methods.py         # Phase methods (diagnose, hypothesis, etc.)
│   └── validation.py      # Hypothesis validation and AI self-review
├── integration.py         # HPC integration layer
│
├── use_cases/             # Site-specific case studies
│   ├── README.md          # Overview and instructions
│   ├── TEMPLATE/          # Template for new sites
│   └── Kougarok/          # Kougarok, Alaska (NGEE-Arctic)
│       ├── README.md      # Site description and discoveries
│       ├── config/
│       │   └── kougarok_config.sh  # ALL site-specific settings
│       ├── parameters/
│       │   ├── FATES_Parameter_List_Full_162_Finalized.txt
│       │   └── salib_problem_162params.txt
│       ├── validation/
│       │   └── validation_targets_leafroot.txt
│       └── memory/        # SITE-SPECIFIC KNOWLEDGE
│           ├── logs/      # Phase execution logs (session-scoped)
│           │   └── {session_id}/          # e.g., 20260310_143052/
│           │       ├── phase2_screening/
│           │       ├── phase3_diagnosis/
│           │       ├── phase4_hypothesis/
│           │       ├── phase5_testing/
│           │       └── phase6_refinement/
│           ├── phase_results/  # Phase outputs (session-scoped)
│           │   └── {session_id}/
│           │       ├── phase1_exploration/  # Sensitivity analysis results
│           │       ├── phase2_screening/    # Ranking plots, CSVs
│           │       ├── phase3_diagnosis/    # Diagnostic figures
│           │       ├── phase5_testing/      # Experiment scripts, params
│           │       └── phase6_refinement/   # Comparison plots
│           ├── extracted/ # Extracted lessons (YAML)
│           └── gained_knowledge/  # Site-specific knowledge (JSON)
│               ├── discoveries.json
│               ├── experiments.json
│               └── failed_approaches.json
│
├── phases/                # Phase-specific scripts
│   ├── CLAUDE.md          # Phase overview for AI assistants
│   ├── phase0_design/     # Morris sampling, case creation
│   ├── phase1_exploration/# Sensitivity analysis
│   ├── phase2_screening/  # Ensemble ranking
│   ├── phase3_diagnosis/  # Root cause analysis
│   ├── phase4_hypothesis/ # Hypothesis generation
│   ├── phase5_testing/    # Run experiments
│   └── phase6_refinement/ # Learn from results
│
├── tools/                 # Shared utilities
│   ├── config.py          # Python config loader (reads a2mc_config.sh)
│   ├── phase_logger.py    # Site-specific Markdown logging (session-scoped)
│   ├── workflow_status.py # Master workflow status
│   ├── cost_functions.py  # Error metrics (RE, RMSE, NSE, KGE)
│   ├── evaluate_case.py   # Case evaluation against validation targets
│   ├── optimize_function.py  # Ensemble ranking
│   ├── fates_utils.py     # FATES data utilities
│   ├── fates_output_variables.py  # FATES output variable registry
│   ├── hpc_utils.py       # HPCConfig, HPCExecutor, ParameterManager
│   ├── modify_fates_parameters.py
│   ├── diagnose_ensemble_status.py
│   ├── populate_experiments.py  # Phase 6 resume tool
│   ├── submit_experiment.sh    # Submit single experiment to HPC
│   ├── create_case.sh          # Create CIME case (sources config vars)
│   └── extract_knowledge.py    # Knowledge extraction from logs
│
├── memory/                # GENERIC KNOWLEDGE (framework-level)
│   ├── __init__.py        # Package exports
│   ├── store.py           # JSON persistence utilities
│   ├── manager.py         # MemoryManager class
│   ├── gained_knowledge/  # Generic FATES knowledge (JSON)
│   │   ├── discoveries.json
│   │   ├── experiments.json
│   │   ├── parameters.json
│   │   └── failed_approaches.json
│   ├── logs/              # A2MC DEVELOPMENT session logs (Markdown)
│   ├── extracted/         # Generic extracted lessons (YAML)
│   └── workflow_log.json  # Master workflow status
│
├── rag/                   # RAG/GraphRAG System (generic FATES knowledge)
│   ├── loader.py          # Document loading
│   ├── vector_store.py    # ChromaDB wrapper
│   ├── knowledge_graph.py # NetworkX graph
│   ├── graph_builder.py   # Build from YAML
│   ├── hybrid_retriever.py# Combined retrieval
│   ├── data/
│   │   └── curated_relationships.yaml  # Knowledge source of truth
│   └── chroma_db/         # Vector index
│
├── docs/                  # Documentation
│   └── fates-knowledge-base/  # FATES documentation (official + wiki)
│
├── scripts/               # Utility scripts
│   ├── seed_memory_from_yaml.py
│   ├── build_rag_index.py
│   └── curated_knowledge_template.yaml
│
└── plot/                  # Visualization scripts
    └── visualize_a2mc_horizontal.py
```

---

## References

- [Anthropic Claude API](https://docs.anthropic.com/)
- [NERSC SLURM Documentation](https://docs.nersc.gov/jobs/)
- [ELM-FATES Technical Reference](https://fates-users-guide.readthedocs.io/)
- [SALib Morris Sensitivity](https://salib.readthedocs.io/)



---

## Contact

**Author:** Jing Tao
**Email:** jingtao@lbl.gov
**Project:** NGEE-Arctic ELM-FATES calibration
**GitHub:** https://github.com/jingtao-lbl/A2MC-elm
