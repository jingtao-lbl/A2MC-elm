# A2MC User Guide

Detailed companion to the top-level [`README.md`](../../README.md). The README is the front door (what A2MC is, how the two agents work, the 7-phase overview, a condensed quick start). This guide holds the full operational detail: configuration reference, per-phase behavior, module APIs, the knowledge system internals, and the operational concerns (state persistence, error handling, cost, reporting).

## Contents

1. [Installation and setup (NERSC Perlmutter)](#1-installation-and-setup-nersc-perlmutter)
2. [Configuration reference](#2-configuration-reference)
3. [Running the workflow](#3-running-the-workflow)
4. [The 7-phase workflow in detail](#4-the-7-phase-workflow-in-detail)
5. [Module reference](#5-module-reference)
6. [Knowledge system (RAG/GraphRAG, version- and configuration-aware retrieval)](#6-knowledge-system)
7. [Adaptive Memory system](#7-adaptive-memory-system)
8. [Experimental design strategies](#8-experimental-design-strategies)
9. [State persistence](#9-state-persistence)
10. [Integration with existing tools](#10-integration-with-existing-tools)
11. [Error handling](#11-error-handling)
12. [Cost management](#12-cost-management)
13. [Session reports and presentations](#13-session-reports-and-presentations)
14. [Directory structure](#14-directory-structure)

---

## 1. Installation and setup (NERSC Perlmutter)

```bash
# 1. Clone the repository
cd /global/homes/$USER
git clone https://github.com/jingtao-lbl/A2MC-elm.git
cd A2MC-elm

# 2. Set up Python environment (one-time setup)
module load python
python -m venv ~/a2mc_env
source ~/a2mc_env/bin/activate
# anthropic SDK for the Anthropic provider; openai SDK for OpenAI/CBorg providers
pip install anthropic openai numpy pandas xarray netCDF4 scipy SALib networkx chromadb sentence-transformers pyyaml Pillow

# 3. Set API key (add to ~/.bashrc for persistence)
# Use the env var matching your provider (see a2mc_config.sh -> A2MC_AI_PROVIDER):
#   anthropic -> ANTHROPIC_API_KEY, openai -> OPENAI_API_KEY, cborg -> CBORG_API_KEY
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.bashrc
source ~/.bashrc

# 4. Verify setup
python -c "import anthropic; print('Anthropic SDK OK')"
python -c "from orchestrator import CalibrationOrchestrator; print('Orchestrator OK')"
```

After initial setup, the virtual environment is auto-activated when you `source a2mc_config.sh`. Keep your API key visible only to yourself (e.g., `chmod 600 ~/.bashrc`).

---

## 2. Configuration reference

A2MC uses a two-level configuration hierarchy:

- `a2mc_config.sh` — machine-level defaults (HPC paths, COMPSET, Python env, simulation protocol, AI provider).
- `use_cases/{site}/config/{site}_config.sh` — site-specific overrides (PFTs, parameters, validation targets, protocol overrides).

Source **both** before every run.

### 2.1 Create a use case

```bash
# Copy the Kougarok example (recommended) or the minimal template
cp -r use_cases/Kougarok use_cases/YourSite
# OR
cp -r use_cases/TEMPLATE use_cases/YourSite
```

### 2.2 Site-specific settings

Edit `use_cases/YourSite/config/yoursite_config.sh`:

```bash
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

### 2.3 Parameters and validation targets

Create these files in your use case folder:

```bash
# Parameter list with bounds
vim use_cases/YourSite/parameters/your_param_list.txt

# SALib problem definition (optional, for sensitivity analysis)
vim use_cases/YourSite/parameters/salib_problem.txt

# Validation targets
vim use_cases/YourSite/validation/your_targets.txt
```

### 2.4 Machine settings

Only edit `a2mc_config.sh` if you need to change HPC-level settings:

```bash
export A2MC_PROJECT="your_project"        # HPC allocation
export A2MC_E3SM_ROOT="/path/to/E3SM"     # E3SM source code
export A2MC_OUTPUT_ROOT="/path/to/output" # Simulation output root

# REQUIRED for version-aware RAG (v2.90+): point at your E3SM/ELM-FATES checkout.
# A2MC reads the FATES + ELM commits and selects the matching RAG profile.
export A2MC_MODEL_PATH="/path/to/your/E3SM_FATES_checkout"

# Optional for configuration-aware retrieval (v2.92+): override mode env vars.
# Defaults match ELM namelist_defaults.xml (vanilla SP run, no FATES).
# Set in your site config to enable FATES with CNP + ECA, etc.
export A2MC_ELM_OPTIONS="-bgc fates -nutrient cnp -nutrient_comp_pathway eca"
export A2MC_FATES_PARTEH_MODE=2           # 1=carbon-only, 2=CNP
# Tier 2 FATES feature flags (default false):
#   A2MC_FATES_SPITFIRE_MODE, A2MC_USE_FATES_PLANTHYDRO,
#   A2MC_USE_FATES_LOGGING, A2MC_USE_FATES_SP, etc.
# See docs/a2mc_reference/mode_aware_workflow.md for the full 20-dim schema.

# Optional for auto-rebuild on drift (v2.98+):
# When the orchestrator detects your checkout has drifted off the matched
# milestone, this opts in to automatic rebuild for T2 / T3-near drift
# (subprocess + validator gate; rollback to <profile>.previous/ on failure).
# T3-distant drift always emits a prompt-pack and aborts regardless.
export A2MC_RAG_AUTO_REBUILD="false"      # default false (warn-and-continue)
export A2MC_RAG_T3_AUTO_DISTANCE=100      # default 100 = one major epoch step
# See docs/a2mc_reference/version_association_howto.md "Drift handling".
```

### 2.5 AI settings

AI reasoning is required for phases 2, 3, 4, and 6.

**Choose your provider** — edit `A2MC_AI_PROVIDER` in `a2mc_config.sh`:

```bash
export A2MC_AI_PROVIDER="anthropic"   # Direct Anthropic API (default)
# export A2MC_AI_PROVIDER="openai"    # Direct OpenAI API
# export A2MC_AI_PROVIDER="cborg"     # Berkeley Lab CBorg proxy
```

Each provider has a default model (set automatically when you source `a2mc_config.sh`); override with `A2MC_AI_MODEL`.

| Provider | Default Model | Other Models |
|----------|---------------|--------------|
| `anthropic` | `claude-opus-4-20250514` | `claude-sonnet-4-20250514`, `claude-haiku-3-20240307` |
| `openai` | `gpt-4o` | `gpt-4o-mini`, `o3-mini` |
| `cborg` | `anthropic/claude-sonnet` | `openai/gpt-4o`, `openai/gpt-4o-mini`, `lbl/llama` |

**Set the API key** matching your provider in `~/.bashrc` before sourcing `a2mc_config.sh`:

```bash
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.bashrc   # for anthropic
# echo 'export OPENAI_API_KEY="sk-..."' >> ~/.bashrc        # for openai
# echo 'export CBORG_API_KEY="sk-..."' >> ~/.bashrc         # for cborg
source ~/.bashrc
```

---

## 3. Running the workflow

```bash
# Source both configuration files (required before every run)
source a2mc_config.sh
source use_cases/YourSite/config/yoursite_config.sh
print_config  # Verify settings

# Start a new calibration run (with human review checkpoints between phases)
python orchestrator.py --run

# Run fully autonomous (no interactive prompts)
python orchestrator.py --run --no-review

# Start from a specific phase and calibration round
python orchestrator.py --run --start-phase 2 --start-round 2

# Resume from a saved checkpoint (state-file auto-detected from config)
python orchestrator.py --resume

# Resume Phase 5 after HPC experiments complete, continuing the same session
# (checks job status, extracts results, evaluates, then proceeds to Phase 6)
python orchestrator.py --resume --start-phase 5 --session-id 20260331_030000

# Re-run from Phase 2 using the same session's Phase 1 results
# (backs up state file and downstream phase_results, then re-runs Phase 2+)
python orchestrator.py --resume --start-phase 2 --session-id 20260405_145259
```

`--start-phase` accepts a number, `phaseN`, or the phase name (`exploration`). Use `screen` or `tmux` for long-running HPC sessions. All screen output is saved to `use_cases/{site}/a2mc_run_{timestamp}.log`:

```bash
tail -f use_cases/Kougarok/a2mc_run_*.log
```

---

## 4. The 7-phase workflow in detail

A2MC uses a 7-phase workflow with intelligent iteration paths to minimize HPC cost while maximizing learning.

### 4.1 Phase overview

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

**Phase 3 diagnostic tools:** `analyze_carbon_balance.py`, `analyze_mortality.py`, `analyze_nutrient_balance.py`, `analyze_nutrient_pools.py`, `check_edge_parameters.py`, `compare_case_parameters.py`, `compare_targets.py`, `detect_collapse.py`, `diagnose_pft_limitations.py`, `read_case_parameters.py`, `test_hypothesis_framework.py`.

**Self-improving diagnostic library.** When no existing tool can test a hypothesis, the agent writes a custom `test_*.py` (exposing `test_hypothesis()`) into `phases/phase3_diagnosis/generated/`, auto-discovered for the current run. A vetted, reusable one is then **promoted** into the permanent tool library with `tools/promote_diagnostic_script.py` (copies it to `phases/phase3_diagnosis/` and registers it in the diagnostic-tools inventory; human-gated).

**Phase 5 scripts:** `design_experiments.py`, `monitor_experiments.py`, `submit_experiments.py`.

### 4.2 Iteration paths

A2MC supports non-linear iteration to avoid unnecessary HPC computation:

```
Normal Flow:
  Phase 0 -> [HPC] -> Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 -> Phase 5 -> [HPC] -> Phase 6 -> Phase 7

Iteration Paths:
  Phase 4 -> Phase 3: Skip testing when existing data can test the hypothesis
  Phase 6 -> Phase 3: Rethink hypothesis when experiment results disprove it
  Phase 6 -> Phase 0: Redesign when parameter space needs expansion
```

- **Phase 4 -> Phase 3 (skip testing):** when a hypothesis can be tested using existing ensemble data (e.g., P mass balance analysis, comparing PFT responses), skip the HPC testing phase and return to diagnosis with new insights.
- **Phase 6 -> Phase 3 (rethink hypothesis):** when experiment results disprove the hypothesis, return to diagnosis to revise understanding and generate new hypotheses.
- **Phase 6 -> Phase 0 (redesign):** when all parameter candidates are at bounds and calibration fails, expand parameter ranges and run a new ensemble.

### 4.3 Three-level iteration structure

Three nested loops (outermost -> middle -> inner):

**Calibration Round (outermost):** full Phase 0 -> 7 cycle. Counter: `calibration_round`.
- Round 1: e.g., 138 parameters, 4170 simulations.
- Round 2: e.g., 162 parameters, 4890 simulations (expanded parameter space).
- Incremented when Phase 6 -> Phase 0 redesign is needed (experiment cycles reach max without meeting all targets).

**Middle Loop (experiment cycle):** Phase 3 -> 4 -> 5 -> 6 -> 3, max 10 cycles. Counter: `experiment_count`.
- Run full HPC experiments to test hypotheses.
- Exit when targets met (-> Phase 7 CONVERGED) OR experiment cycles reach max (-> Phase 0 redesign).

**Inner Loop (skip testing):** Phase 3 <-> 4, max 10 cycles. Counter: `skip_testing_count`.
- Test hypotheses with existing ensemble data (no HPC cost).
- Exit when confidence threshold met OR max cycles reached.
- Counter resets when entering Phase 5 (HPC).

```bash
# Control iteration limits
python orchestrator.py --run \
    --start-round 2 \              # Calibration round (outermost loop)
    --max-skip-testing 10 \        # Max Phase 3<->4 cycles (default: 10)
    --max-experiments 10 \         # Max full experiment cycles (default: 10)
    --confidence-threshold 0.95    # Exit skip testing threshold (default: 0.95)
```

### 4.4 Phase details

**Phase 0: DESIGN** — create the initial parameter sampling design and submit to HPC. Morris method: `n_trajectories × (n_params + 1)` simulations (e.g., 30 × 163 = 4890). Outputs: Morris ensemble matrix (X matrix) at `phases/phase0_design/FATES_*_Morris_*sets.txt`, modified parameter files per ensemble member, HPC jobs submitted.

**Phase 1: EXPLORATION** — extract the Y matrix (model outputs) from completed simulations, run Morris sensitivity analysis (SALib), rank parameters by μ* (mean absolute effect) and σ (interaction effect), generate plots and CSV rankings. Outputs: Y matrices (`MorrisLeafbiomass_*.txt`, etc.), per-PFT sensitivity rankings, sensitivity plots.

**Phase 2: SCREENING** — rank ensemble members against validation targets. Calculate cost metrics (RMSRE, NRMSE) across all targets, rank by multi-objective performance, identify met/failed targets per case, detect edge cases (parameters at bounds). Outputs: ranked case list with composite cost, per-target error statistics, edge parameter analysis.

**Phase 3: DIAGNOSIS** — root cause analysis of calibration failures. The AI analyzes which targets are failing and why, identifies mechanistic causes (e.g., P-limitation, allocation issues), finds cross-PFT parameter conflicts, compares best vs worst cases, and generates parameter adjustment recommendations. Output: diagnosis report with root causes, affected mechanisms, and priority rankings.

**Phase 4: HYPOTHESIS** — generate testable hypotheses. The AI creates named hypotheses (e.g., "PFT10 P-starvation hypothesis"), specifies parameters to modify and expected direction, defines expected outcomes and success criteria, and chooses an approach: run new experiments, or test with existing data. Output: hypothesis with modification plan or analysis plan.

**Phase 5: TESTING** — run designed experiments on HPC. Create modified parameter files, submit experiment simulations, extract and evaluate results, compare actual outcomes to expected.

**Phase 6: REFINEMENT** — evaluate results and extract lessons. Decision logic: hypothesis confirmed -> apply changes, check remaining targets; partially confirmed -> adjust hypothesis, return to Phase 4; rejected -> record failed approach, return to Phase 3; all targets met -> advance to CONVERGED; parameter bounds too restrictive -> return to Phase 0 (redesign). Adaptive Memory learning: extract lessons, store discoveries in `gained_knowledge/discoveries.json`, record failed approaches in `gained_knowledge/failed_approaches.json`, update parameter knowledge, check for equifinality.

**Phase 7: CONVERGED** — finalize calibration. Outputs: best parameter configuration, final calibration report, complete experiment history, extracted knowledge for future calibrations.

### 4.5 Validation targets

Validation targets are site-specific and defined in `use_cases/{site}/README.md`. Typical types: biomass (leaf, fine root, AGB by PFT, g C/m²), ecosystem fluxes (GPP, NPP, NEE, g C/m²/yr), structure (LAI, canopy height), phenology (leaf-on/off dates). See `use_cases/Kougarok/README.md` for a complete target specification.

---

## 5. Module reference

### 5.1 orchestrator.py

Main workflow controller with state persistence. Configuration is loaded from environment variables set by `a2mc_config.sh` and site config.

```python
from orchestrator import CalibrationOrchestrator, Config

# Config auto-detects paths from A2MC_USE_CASE_DIR environment variable
config = Config(
    use_memory=True,           # Enable Adaptive Memory
    use_reasoning=True,        # Enable Claude API reasoning
    max_iterations=10,
    max_skip_testing=10,       # Max Phase 3<->4 skip testing cycles
    max_experiments=10,        # Max Phase 3->4->5->6 experiment cycles
)
orch = CalibrationOrchestrator(config)
orch.run()
```

Key classes: `Config` (all settings), `Phase` (enum of 8 workflow phases), `WorkflowState` (persistent state with full history), `CalibrationOrchestrator` (main controller).

### 5.2 reasoning/ package

Claude API interface for intelligent reasoning (split into `schemas.py`, `prompts.py`, `base.py`, `methods.py`, `validation.py`).

```python
from reasoning import ReasoningModule, Diagnosis, Hypothesis

reasoning = ReasoningModule()

diagnosis = reasoning.diagnose(
    results={"leaf_pft10": 45.2, ...},
    targets={"leaf_pft10": {"mean": 82.7, "uncertainty": 0.20}, ...},
    sensitivity_rankings={"leaf_pft10": [{"param": "...", "mu_star": 0.45}]},
    iteration=1
)

hypothesis = reasoning.generate_hypothesis(
    diagnosis=diagnosis,
    sensitivity_data={...},
    previous_experiments=[]
)

experiments = reasoning.design_experiments(
    hypothesis=hypothesis,
    base_case={"case_id": 2678, "parameters": {...}}
)

interpretation = reasoning.interpret_results(
    experiment=experiments[0],
    actual_results={...},
    targets={...}
)
```

Output structures: `Diagnosis` (failing targets, causes, parameter/protocol recommendations, requested diagnostics), `Hypothesis` (name, mechanism, parameter modifications, test plan), `Experiment` (base case, modifications, expected results).

### 5.3 tools/hpc_utils.py

HPC-native interfaces for simulation management.

```python
from tools.hpc_utils import HPCConfig, HPCExecutor, ParameterManager

config = HPCConfig()  # reads from A2MC_* environment variables

param_mgr = ParameterManager(config)
new_param_file = param_mgr.create_modified_file(
    base_file="fates_params.nc",
    modifications=[
        {"parameter": "fates_alloc_storage_cushion", "pft": 10, "value": 3.0}
    ],
    output_file="fates_params_modified.nc"
)

executor = HPCExecutor(config)
job_id = executor.submit_case(case_name="PtCNPEn100_TRANS")
results = executor.wait_for_jobs([job_id], poll_interval=300)
```

Key classes: `HPCConfig` (HPC paths, project, QOS from env vars), `HPCExecutor` (direct sbatch/squeue execution), `ParameterManager` (wraps `modify_fates_parameters.py`).

---

## 6. Knowledge system

### 6.1 Three-tier FATES knowledge

Same knowledge encoded in three tiers so the AI can reach it via multiple retrieval paths:

| Tier | Location | Format | Purpose |
|------|----------|--------|---------|
| **Static Documentation** | `docs/fates-knowledge-base/` (per-commit subdirs) | Markdown | Human reference, RAG indexing |
| **RAG/GraphRAG** | `rag/{chroma_db,graphs,metadata}/<profile>/` | ChromaDB + JSON graph | AI semantic search, graph traversal — version-aware (per-milestone) and configuration-aware (per simulation mode) |
| **Adaptive Memory** | `memory/gained_knowledge/` | JSON | AI reasoning context, learned discoveries |

Key resources for CNP calibration:
- **START HERE:** `docs/fates-knowledge-base/fates-codebase-wiki/advanced/cnp_calibration_guide.md` (Knox 2026)
- PID controller: `docs/fates-knowledge-base/fates-codebase-wiki/plant-physiology/parteh/cnp_allocation.md`
- ECA/RD competition: `docs/fates-knowledge-base/fates-codebase-wiki/advanced/nutrient_competition.md`
- Nutrient uptake: `docs/fates-knowledge-base/fates-codebase-wiki/plant-physiology/parteh/soil_plant_interface.md`

The RAG/GraphRAG tier is **version-aware** (v2.90+), **configuration-aware** (v2.91 / v2.92), and **drift-aware** (v2.98). A2MC auto-detects the user's E3SM/ELM-FATES checkout and the active simulation mode, loads the right knowledge profile, filters out content that does not apply, and (with opt-in) auto-rebuilds the profile when the checkout drifts off the matched milestone.

### 6.2 Version association (v2.90)

A2MC reads the user's `A2MC_MODEL_PATH` (E3SM checkout root), detects the FATES + ELM commit hashes, and matches against the milestone registry at `rag/milestones.json`. Each milestone owns a self-contained profile: ChromaDB index, NetworkX graph, metadata, and a frozen per-milestone curated YAML.

| Milestone | FATES tag | FATES commit | ELM commit | Param file | Status |
|---|---|---|---|---|---|
| `api-43-1` | `sci.1.91.1_api.43.1.0` | `e027a40` | `d40b843` | JSON | Canonical (active development) |
| `api-31-0` | `sci.1.68.2_api.31.0.0` | `e85d997` | `60d9aad` | CDL | Legacy / Kougarok manuscript reproducibility |

```bash
# A2MC auto-detects on startup, picks the right RAG profile, and aligns or warns
export A2MC_MODEL_PATH="/path/to/your/E3SM_FATES_checkout"
source a2mc_config.sh
source use_cases/Kougarok/config/kougarok_config.sh
python orchestrator.py --run
```

Diagnostic CLIs:

```bash
python scripts/rag_list.py                                     # List registered milestones
python scripts/rag_match.py --model-path /path/to/E3SM_FATES   # Which milestone matches a checkout
python scripts/rag_bump.py --tier T2 --new-version sci.1.91.4_api.43.1.0 --mode prompt-pack
python scripts/verify_phase4.py                                # 24 content gates + 9 smoke tests
```

Per-milestone YAML reproducibility: each milestone owns `rag/data/curated_relationships_<profile>.yaml`. Rebuilding a milestone always uses its frozen YAML, preventing silent corruption when the canonical evolves. Full workflow: `docs/a2mc_reference/version_association_workflow.md`.

### 6.3 Configuration-aware retrieval (v2.91 / v2.92)

A2MC parses the user's `A2MC_ELM_OPTIONS` and Tier 2 env vars into a 20-dimension `ConfigMode`. The RAG retriever builds a ChromaDB `where` clause from this and filters every chunk: PARTEH=1 retrieval no longer surfaces CNP allocation theory, fire chunks are filtered when SPITFIRE is off, ELM-only runs see only ELM content.

**The 20 dimensions** (defaults match ELM `namelist_defaults.xml` — a vanilla SP run):

- **Tier 1 primary (7):** `bgc_mode` (sp/cn/bgc/fates), `use_fates` (derived), `parteh_mode` (1=carbon-only / 2=CNP), `use_fates_nocomp`, `nutrient` (c/cn/cnp), `nutrient_comp_pathway` (rd/eca), `soil_decomp` (ctc/century)
- **Tier 2 FATES feature flags (6):** `fates_spitfire_mode`, `use_fates_planthydro`, `use_fates_logging`, `use_fates_sp`, `use_fates_ed_prescribed_phys`, `use_fates_fixed_biogeog`
- **Tier 3 secondary compset modifiers (7):** `crop`, `dynamic_vegetation`, `methane`, `hydrstress`, `topounit`, `irrig`, `solar_rad_scheme`

Three independent metadata sources tag chunks during the build: (1) YAML curation via `applies_in:` blocks on parameters/mechanisms/outputs (17 mode-restricted parameters + 3 mechanisms tagged in the canonical YAML); (2) a path-prefix table of 11 patterns covering 22+ wiki docs in `rag/loader.py:_WIKI_PATH_PREFIX_TAGS` (including inverse-tagged docs, e.g., `biophysics/transpiration.md` applies when hydraulics is OFF); (3) a default-permissive sweep marking any untagged chunk/node `applies_universal: True`.

```bash
# Example config: Kougarok PARTEH=2 + ECA + CNP
export A2MC_ELM_OPTIONS="-bgc fates -nutrient cnp -nutrient_comp_pathway eca"
export A2MC_FATES_PARTEH_MODE=2
# Optional Tier 2 (default off):
# export A2MC_FATES_SPITFIRE_MODE=1
# export A2MC_USE_FATES_PLANTHYDRO=true
```

The reasoning module reads `ConfigMode.from_env()` once per Phase 3/4 retrieval call and threads the where clause through `HybridRetriever.get_targeted_context()`, `get_calibration_context()`, and `get_context()` to the ChromaDB layer.

### 6.4 Auto-rebuild on drift (v2.98)

When the orchestrator's startup hook detects that the checkout has drifted off the matched milestone, it dispatches via `tools/auto_rebuild.py:handle_drift()` per the tier policy:

| Tier | Condition | Action | Flag-gated? |
|---|---|---|---|
| **T1** | No drift, all SHAs match | In-process metadata refresh via `tools/rag_refresh.py` | No (always auto) |
| **T2** | Same epoch, FATES parameter file SHA differs | Subprocess `rag_bump.py --mode auto` + validator gate; rollback to `<profile>.previous/` on Red | Yes (`A2MC_RAG_AUTO_REBUILD=true`) |
| **T3-near** | `epoch_distance ≤ A2MC_RAG_T3_AUTO_DISTANCE` (default 100) | Same as T2 (full pipeline) | Yes |
| **T3-distant** | `epoch_distance > A2MC_RAG_T3_AUTO_DISTANCE` | Always emit prompt-pack at `Offline/bump_pack_<target>/` and abort startup | No (always manual) |

`epoch_distance` formula: `|major_a − major_b| × 100 + |minor_a − minor_b|`. So api-43-1 -> api-44-0 = 100 (auto-eligible); api-31-0 -> api-43-1 = 1201 (always manual). Concurrency is enforced by a file lock at `<rag_dir>/.bump.lock`. A Red verdict triggers automatic rollback to `<profile>.previous/`; the broken build is preserved at `<profile>.failed_<UTC-timestamp>/` for forensics. End-user how-to: `docs/a2mc_reference/version_association_howto.md` "Drift handling".

### 6.5 Validation — five layers

The knowledge-build validation started as a three-tier triangle (codebase_wiki + yaml_wiki + rag_diff), gained Tier 4 for mode-metadata propagation in v2.92, and added three more validators in v2.95:

| Layer | Validator | Asserts |
|---|---|---|
| **Tier 1** | `tools/codebase_wiki_validator.py` | Wiki claims match source (per-commit) |
| **Tier 2** | `tools/yaml_wiki_validator.py` (incl. Dim F for `applies_in:`) | Curated YAML entries present in wiki + parameter file; mode tags valid |
| **Tier 3** | `tools/rag_diff.py` | Diff between two RAG profiles (e.g., milestone bump) |
| **Tier 4** | `tools/mode_metadata_validator.py` (v2.92) | YAML `applies_in:` propagates correctly to chunks + graph nodes |
| **Snapshot** | `tools/snapshot_validator.py` (v2.95) | End-to-end integration test across 5 fixture ConfigModes |
| **Profile completeness** | `tools/profile_completeness_validator.py` (v2.95) | 5-category statistical coverage |
| **Cross-milestone** | `tools/cross_milestone_validator.py` (v2.95) | `applies_in:` drift between milestone YAMLs |

```bash
# Unified harness — runs all five layers + the orchestrator-side gate (v2.98)
python scripts/verify_mode_aware.py     # Verdict: GREEN

# Per-layer validators all have standalone CLI entry points; see
# docs/a2mc_reference/rag_validation_workflow.md for the full playbook.
```

The same `run_all_validators(profile)` function gates the v2.98 auto-rebuild path; a Red verdict triggers automatic rollback.

### 6.6 Reference docs

- **Comprehensive mode-aware workflow:** `docs/a2mc_reference/mode_aware_workflow.md`
- **Mode-aware quick how-to:** `docs/a2mc_reference/mode_aware_howto.md`
- **ELM compset reference:** `docs/a2mc_reference/elm_compset_reference.md`
- **Version association workflow / how-to:** `docs/a2mc_reference/version_association_workflow.md`, `version_association_howto.md`
- **Validation playbook:** `docs/a2mc_reference/rag_validation_workflow.md`
- **RAG system reference:** `docs/a2mc_reference/rag_reference.md`
- **RAG from-scratch reconstruction:** `docs/a2mc_reference/rag_build_roadmap.md`

---

## 7. Adaptive Memory system

Two-tier knowledge architecture enabling learning across sessions while keeping site-specific knowledge separate.

```
GENERIC KNOWLEDGE (memory/gained_knowledge/)
  General FATES mechanistic insights; applies to all sites

SITE-SPECIFIC KNOWLEDGE (use_cases/{site}/memory/)
  Site-specific discoveries and experiments; phase execution logs; lessons learned

KNOWLEDGE PROMOTION
  AI evaluates site-specific discoveries; generalizable lessons promoted to generic knowledge
```

### 7.1 Memory stores

**Generic** (`memory/gained_knowledge/`): `discoveries.json` (general FATES insights), `experiments.json` (generic patterns), `parameters.json` (parameter knowledge), `failed_approaches.json` (approaches to not repeat).

**Site-specific** (`use_cases/{site}/memory/gained_knowledge/`): `discoveries.json` (e.g., "Kougarok Allocation Paradox"), `experiments.json`, `failed_approaches.json`.

**Phase execution logs** (`use_cases/{site}/memory/logs/`): `phase2_screening/`, `phase3_diagnosis/`, `phase4_hypothesis/`, `phase6_refinement/` (Markdown, with AI reasoning).

### 7.2 MemoryManager API

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

### 7.3 Knowledge in AI prompts

When A2MC performs diagnosis or generates hypotheses, three knowledge sources are combined into the prompt:

| Source | Content | Role |
|--------|---------|------|
| **RAG/GraphRAG** | FATES + ELM source documentation (per-milestone profile; api-43-1 ≈ 6,300 chunks, api-31-0 ≈ 2,600) | General knowledge ("how does the PID controller work?") |
| **Adaptive Memory** | Discoveries, failed approaches, parameter insights | Learned knowledge ("what failed before? what worked?") |
| **Task Data** | Results, targets, sensitivity rankings | Current context ("what are we calibrating?") |

Prompt structure (in order): RAG/GraphRAG context -> Adaptive Memory context (failed approaches marked "DO NOT REPEAT") -> current data -> task instructions + response format. The sources are complementary, not strictly prioritized: RAG provides "textbook" knowledge, memory provides "experience," and both inform reasoning over the current task data.

### 7.4 Referencing knowledge from similar sites

| Your site type | Reference site | Transferable knowledge |
|----------------|----------------|------------------------|
| Arctic/tundra | `use_cases/Kougarok/` | Allocation Paradox, P-limitation dynamics, graminoid-shrub competition |
| CNP-enabled | `use_cases/Kougarok/` | PID controller behavior, ECA competition, vmax calibration strategies |

What transfers: mechanistic insights, diagnostic patterns, failed approaches. What does not: exact parameter values (site-specific).

```python
from memory import MemoryManager
kougarok_memory = MemoryManager("use_cases/Kougarok/memory/gained_knowledge")
discoveries = kougarok_memory.discoveries.get('discoveries', [])
failed = kougarok_memory.failed_approaches.get('failed_approaches', [])
```

### 7.5 Seeding memory

```bash
cp scripts/curated_knowledge_template.yaml scripts/curated_knowledge.yaml
# Edit with your discoveries, then:
python scripts/seed_memory_from_yaml.py --input scripts/curated_knowledge.yaml
```

---

## 8. Experimental design strategies

**Cumulative design** — test parameters sequentially, adding one at a time. Use when parameters act through sequential mechanisms (A -> B -> C).

```
Exp1: param_A only
Exp2: param_A + param_B
Exp3: param_A + param_B + param_C
```

**Factorial design** — test all combinations. Use when parameters may interact (synergistic or antagonistic effects).

```
Exp1: param_A=low,  param_B=low
Exp2: param_A=low,  param_B=high
Exp3: param_A=high, param_B=low
Exp4: param_A=high, param_B=high
```

---

## 9. State persistence

All workflow state is saved to JSON for resumability:

```json
{
  "phase": "DIAGNOSIS",
  "iteration": 3,
  "start_time": "2025-01-06T10:30:00",
  "config": {
    "work_dir": "~/A2MC",
    "param_file": "fates_params.nc",
    "output_root": "~/A2MC_runs"
  },
  "design": {
    "method": "morris",
    "n_params": 162,
    "n_trajectories": 30,
    "n_samples": 1000,
    "total_ensemble": 4890
  },
  "screening": {
    "top_cases": [2678, 845, 3930],
    "best_composite_nrmse": 0.493
  },
  "experiments": [
    {
      "name": "Exp1_storage_cushion",
      "base_case": 2678,
      "modifications": [],
      "results": {},
      "interpretation": {}
    }
  ],
  "phase_history": [
    {"phase": "DESIGN", "completed": "2025-01-06T11:00:00"},
    {"phase": "EXPLORATION", "completed": "2025-01-08T14:30:00"}
  ]
}
```

---

## 10. Integration with existing tools

A2MC wraps existing well-tested tools rather than reimplementing:

**Parameter modification** (`modify_fates_parameters.py`): `create_modified_parameter_file(input, output, modifications)`; handles 1D/2D parameters; supports absolute values or percent changes; verifies modifications after applying.

**Data extraction** (`extract_monthly_variables_FATES.py`): extracts site-, PFT-, and SZPF-level variables; outputs NetCDF (all vars) + CSV (site/PFT only); processes yearly files (12 months each); ~50-100× faster than daily extraction.

**Job submission** — direct SLURM commands: `sbatch case.submit`, `squeue -u $USER`, `scancel job_id`, `sacct -j job_id --format=...`.

---

## 11. Error handling

- **Job failures:** automatic retry with exponential backoff, max 3 retries per job, failed jobs logged for manual inspection.
- **API errors:** rate limiting with automatic backoff, fallback to rule-based reasoning if the API is unavailable, repeated queries cached to reduce cost.
- **Missing data:** verify expected files before proceeding, clear error messages with suggested fixes, option to skip incomplete cases.

---

## 12. Cost management

**Claude API usage** (per call): diagnosis ~2K in / ~1K out; hypothesis ~3K in / ~1K out; experiment design ~2K in / ~500 out; interpretation ~2K in / ~1K out. Estimated cost per iteration: ~$0.10-0.20 (Sonnet).

**HPC resources:** Morris ensemble (4890 sims) ~50K node-hours; single experiment ~10 node-hours; data extraction ~0.1 node-hours per case.

---

## 13. Session reports and presentations

A2MC includes offline tools for generating session reports, presentation slides, and narrated videos from calibration session logs. These are not part of the automated workflow and can run at any time (even while Phase 5 simulations are still running).

The orchestrator automatically generates a Markdown session report at the end of Phase 6 via `tools/session_report.py`, saved to `use_cases/{site}/memory/logs/{session_id}/session_report_{session_id}.md`.

`tools/reports/generate_presentation.py` provides a complete pipeline from session logs to narrated video:

```
Session logs + report + figures
  -> AI-generated manuscript-style technical report (.md)
  -> AI-generated Marp slides (.md)
  -> AI-generated narration script (.json)
  -> PDF + PPTX (marp-cli)
  -> Narrated MP4 video (TTS + ffmpeg)
```

Stages 1-4 (collect, report, slides, narration) run on Perlmutter (AI API only). Stages 5-6 (PDF, video) require marp-cli, ffmpeg, and poppler, available locally only. Use `--stop-after narration` on Perlmutter, then `--start-from pdf` on your local machine.

```bash
# On Perlmutter: generate report + slides + narration
python tools/reports/generate_presentation.py --session-id 20260330_135435 \
    --author "Dr. Jing Tao (Lawrence Berkeley National Laboratory)" \
    --stop-after narration

# On local machine: build PDF + video
source ~/a2mc_env/bin/activate  # for openai TTS
python tools/reports/generate_presentation.py --session-id 20260330_135435 \
    --start-from pdf
```

Local prerequisites: marp-cli (`npm install -g @marp-team/marp-cli`), poppler (`brew install poppler`), ffmpeg (`brew install ffmpeg`), openai Python package (in `~/a2mc_env`). Detailed workflow: `tools/reports/WORKFLOW.md`.

---

## 14. Directory structure

```
A2MC/
├── README.md              # Front-door overview
├── a2mc_config.sh         # Machine-level configuration (HPC paths, defaults)
├── orchestrator.py        # Main workflow controller
├── reasoning/             # Claude API interface (package)
│   ├── schemas.py         # Diagnosis, Hypothesis, Experiment dataclasses
│   ├── prompts.py         # DIAGNOSTIC_TOOLS_INVENTORY, CUSTOM_SCRIPT_TEMPLATE
│   ├── base.py            # ReasoningModule class core (init, query, RAG)
│   ├── methods.py         # Phase methods (diagnose, hypothesis, etc.)
│   └── validation.py      # Hypothesis validation and AI self-review
│
├── use_cases/             # Site-specific case studies
│   ├── TEMPLATE/          # Template for new sites
│   └── Kougarok/          # Kougarok, Alaska (NGEE-Arctic)
│       ├── config/        # ALL site-specific settings
│       ├── parameters/    # Parameter list + SALib problem
│       ├── validation/    # Validation targets
│       └── memory/        # SITE-SPECIFIC KNOWLEDGE
│           ├── logs/            # Phase execution logs (session-scoped)
│           │   └── {session_id}/phase{2..6}_*/
│           ├── phase_results/   # Phase outputs (session-scoped)
│           ├── extracted/       # Extracted lessons (YAML)
│           └── gained_knowledge/  # discoveries / experiments / failed_approaches (JSON)
│
├── phases/                # Phase-specific scripts (phase0_design … phase6_refinement)
│
├── tools/                 # Shared utilities (config, logging, cost functions,
│                          #   hpc_utils, modify_fates_parameters, extract_knowledge, …)
│
├── memory/                # GENERIC KNOWLEDGE (framework-level)
│   ├── manager.py         # MemoryManager class
│   ├── store.py           # JSON persistence utilities
│   └── gained_knowledge/  # Generic FATES knowledge (JSON)
│
├── rag/                   # RAG/GraphRAG system
│   ├── loader.py, vector_store.py, knowledge_graph.py, graph_builder.py, hybrid_retriever.py
│   ├── data/              # curated_relationships*.yaml (knowledge source of truth)
│   ├── chroma_db/<profile>/, graphs/<profile>.json, metadata/<profile>.json
│   └── milestones.json    # Version registry
│
├── docs/                  # Documentation
│   ├── a2mc_reference/    # Reference docs (this guide, mode-aware, version-association, validation, …)
│   └── fates-knowledge-base/  # FATES documentation (official + wiki)
│
├── scripts/               # Utility scripts (seed_memory, build_rag_index, rag_list/match/bump, …)
│
└── plot/                  # Visualization scripts
```
