#!/bin/bash
# =======================================================================================
# A2MC Configuration File - GENERIC SETTINGS
#
# This file contains MACHINE-LEVEL settings that apply to ALL sites/use cases.
# Site-specific settings (parameters, validation, PFTs) go in:
#   use_cases/{site}/config/{site}_config.sh
#
# Usage:
#   source a2mc_config.sh
#   source use_cases/YourSite/config/yoursite_config.sh
# =======================================================================================

# ========================
# PROJECT CONFIGURATION
# ========================
export A2MC_PROJECT="m2467"
export A2MC_USER="${USER:-jingtao}"

# ========================
# MACHINE CONFIGURATION
# ========================
export A2MC_MACHINE="pm-cpu"
export A2MC_COMPILER="intel"

# ========================
# PYTHON ENVIRONMENT
# ========================
# Load Python module on HPC (provides base Python with scientific packages)
# NOTE: Must happen BEFORE venv activation since module load can change PATH
if command -v module &> /dev/null; then
    module load python 2>/dev/null
fi

# Activate a2mc_env if it exists
# Always re-activate (module load python above may have altered PATH)
export A2MC_VENV="${HOME}/a2mc_env"
if [ -d "${A2MC_VENV}" ]; then
    source "${A2MC_VENV}/bin/activate"
fi

# ========================
# DIRECTORY PATHS (HPC)
# ========================
# E3SM/FATES source code
export A2MC_E3SM_ROOT="/global/cfs/cdirs/m2467/jingtao/E3SM_FATES"

# ========================
# RAG / VERSION ASSOCIATION (Phase 4 — see docs/18)
# ========================
# A2MC_MODEL_PATH: absolute path to the user's E3SM/ELM-FATES checkout root.
# Required by the RAG version-association infrastructure to detect ELM + FATES
# commits and select the matching milestone profile. Set in your SITE config
# (e.g., use_cases/<site>/config/<site>_config.sh), NOT here, because the
# checkout location is per-user/per-site, not per-machine.
#
# A2MC_RAG_DIR: root of the RAG storage tree. Default: ${A2MC_ROOT}/rag.
export A2MC_RAG_DIR="${A2MC_ROOT}/rag"
#
# A2MC_RAG_ACTIVE: active milestone profile name (e.g., 'api-43-1', 'api-31-0').
# Set automatically by the orchestrator's alignment-check hook based on
# A2MC_MODEL_PATH; do not set manually except for ad-hoc tooling.
#
# A2MC_RAG_AUTO_REBUILD: if 'true', orchestrator silently rebuilds the RAG
# when drift is detected. Default 'false' (drift causes WARN+abort).
export A2MC_RAG_AUTO_REBUILD="false"

# Output root for simulation results
export A2MC_OUTPUT_ROOT="/global/cfs/cdirs/m2467/jingtao"

# Scripts directory (where case scripts are generated)
export A2MC_SCRIPTS_DIR="pscratch/sd/j/jingtao/CaseScripts/Kougarok_FATES"

# Input data paths
export A2MC_DIN_LOC_ROOT="/dvs_ro/cfs/cdirs/e3sm/inputdata"
export A2MC_DIN_LOC_ROOT_CLMFORC="${A2MC_DIN_LOC_ROOT}/atm/datm7"

# ========================
# DEFAULT JOB SETTINGS
# ========================
export A2MC_QUEUE="shared"
export A2MC_WALLTIME="47:59:00"
export A2MC_MEMORY="16G"
export A2MC_NTASKS=1

# Email notifications (optional)
export A2MC_EMAIL="${A2MC_EMAIL:-tjmuse@gmail.com}"

# Additional ELM build/namelist options (optional)
export A2MC_ELM_OPTIONS="${A2MC_ELM_OPTIONS:-}"

# ========================
# MODEL DEFAULTS
# ========================
export A2MC_RES="ELM_USRDAT"
export A2MC_USE_FATES=".true."
export A2MC_FATES_PARTEH_MODE=2
export A2MC_USE_FATES_NOCOMP=".false."

# COMPSET configuration by phase
export A2MC_COMPSET_SPINUP="1850_DATM%QIA_ELM%BGC-FATES_SICE_SOCN_SROF_SGLC_SWAV"
export A2MC_COMPSET_TRANS="2000_DATM%QIA_ELM%BGC-FATES_SICE_SOCN_SROF_SGLC_SWAV"

# Default phase durations (years) - can be overridden by site config
export A2MC_ADSP_YEARS=200
export A2MC_ADSP_REST=10
export A2MC_RGSP_YEARS=200
export A2MC_RGSP_REST=10
export A2MC_TRANS_YEARS=119 # consistent with the forcing data A2MC_DATM_MODE 
export A2MC_TRANS_REST=1

# Forcing data years
export A2MC_SPINUP_START_YEAR=1901
export A2MC_SPINUP_END_YEAR=1920
export A2MC_TRANS_START_YEAR=1901
export A2MC_TRANS_END_YEAR=2019
export A2MC_DATM_MODE="CLMGSWP3v1"

# ========================
# PHASE-SPECIFIC ELM/NAMELIST SETTINGS
# ========================
# These control the ELM configuration for each simulation phase.
# Override in site config if needed (e.g., different nutrient supplement strategy).

# --- ADSP (Accelerated Decomposition Spinup) ---
export A2MC_ADSP_BGC_SPINUP="on"           # "-bgc_spinup on" for accelerated decomp
export A2MC_ADSP_START_DATE="0001-01-01"
export A2MC_ADSP_SUPLPHOS="ALL"             # Prescribe all P during AD spinup
export A2MC_ADSP_SUPLNITRO="NONE"           # No prescribed N
export A2MC_ADSP_NYEARS_AD_CARBON_ONLY=30   # Carbon-only years before nutrient cycling
export A2MC_ADSP_FINIDAT=""                 # Empty = cold start

# --- RGSP (Regular Spinup) ---
export A2MC_RGSP_START_DATE="0201-01-01"
export A2MC_RGSP_SUPLPHOS="NONE"
export A2MC_RGSP_SUPLNITRO="NONE"
# Restart file date: when ADSP ends (ADSP_START + ADSP_YEARS)
export A2MC_RGSP_RESTART_DATE="0201-01-01-00000"

# --- TRANS (Transient Run) ---
export A2MC_TRANS_START_DATE="1901-01-01"
export A2MC_TRANS_SUPLPHOS="NONE"
export A2MC_TRANS_SUPLNITRO="NONE"
# Restart file date: when RGSP ends (RGSP_START + RGSP_YEARS)
export A2MC_TRANS_RESTART_DATE="0401-01-01-00000"

# --- History output settings ---
export A2MC_HIST_MFILT=12                   # Number of time samples per history file
export A2MC_HIST_NHTFRQ=0                   # 0 = monthly averages

# ========================
# ITERATION CONTROL
# ========================
# Max skip-testing cycles (Phase 3↔4 inner loop, no HPC testing runs)
export A2MC_MAX_SKIP_TESTING=10
# Max full experiment cycles (Phase 3→4→5→6 outer loop, with HPC runs)
export A2MC_MAX_EXPERIMENTS=10
# Confidence threshold to exit skip-testing early (0.0–1.0)
export A2MC_CONFIDENCE_THRESHOLD=0.95

# ========================
# SAMPLING DEFAULTS
# ========================
# Sampling scheme: "morris", "lhs" (Latin Hypercube), "sobol", or "custom"
export A2MC_SAMPLING_SCHEME="morris"

# Default sampling settings (override in site config)
export A2MC_N_PARAMS=${A2MC_N_PARAMS:-100}
export A2MC_N_TRAJECTORIES=${A2MC_N_TRAJECTORIES:-30}
export A2MC_N_SAMPLES=${A2MC_N_SAMPLES:-1000}

# Function to calculate total ensemble size based on sampling scheme
calculate_ensemble_size() {
    local scheme="${1:-$A2MC_SAMPLING_SCHEME}"
    local n_params="${2:-$A2MC_N_PARAMS}"
    local n_traj="${3:-$A2MC_N_TRAJECTORIES}"
    local n_samp="${4:-$A2MC_N_SAMPLES}"

    case "$scheme" in
        morris)
            echo $((n_traj * (n_params + 1)))
            ;;
        lhs)
            echo "$n_samp"
            ;;
        sobol)
            echo $((n_samp * (2 * n_params + 2)))
            ;;
        custom)
            echo "${A2MC_TOTAL_ENSEMBLE:-0}"
            ;;
        *)
            echo "ERROR: Unknown sampling scheme: $scheme" >&2
            echo 0
            ;;
    esac
}

# ========================
# AI CONFIGURATION
# ========================
# AI provider: "anthropic" (direct), "openai" (direct), or "cborg" (LBL proxy)
#   anthropic - Uses Anthropic SDK, hits api.anthropic.com; this is the default.
#   openai    - Uses OpenAI SDK, hits api.openai.com
#   cborg     - Uses OpenAI SDK, hits api.cborg.lbl.gov (Berkeley Lab proxy)
#export A2MC_AI_PROVIDER="anthropic"
export A2MC_AI_PROVIDER="cborg"

# AI model — auto-derived from provider unless explicitly overridden AFTER this block.
# To override: export A2MC_AI_MODEL="your-model" AFTER sourcing this file.
# Available models per provider:
#   anthropic: claude-opus-4-20250514 (default), claude-sonnet-4-20250514, claude-haiku-3-20240307
#   openai:    gpt-4o (default), gpt-4o-mini, o3-mini
#   cborg:     anthropic/claude-sonnet(default), anthropic/claude-opus, openai/gpt-4o, openai/gpt-4o-mini, lbl/llama
case "${A2MC_AI_PROVIDER}" in
    anthropic) export A2MC_AI_MODEL="claude-opus-4-20250514" ;;
    openai)    export A2MC_AI_MODEL="gpt-4o" ;;
    cborg)     export A2MC_AI_MODEL="anthropic/claude-sonnet" ;;
    *)         export A2MC_AI_MODEL="claude-opus-4-20250514" ;;
esac

# API base URL override (only needed for custom endpoints)
# CBorg auto-sets to https://api.cborg.lbl.gov when empty
export A2MC_AI_BASE_URL="${A2MC_AI_BASE_URL:-}"

# Maximum tokens for AI responses (default for most calls)
export A2MC_AI_MAX_TOKENS="${A2MC_AI_MAX_TOKENS:-4096}"

# Maximum tokens for diagnosis responses (Phase 3)
# Diagnosis JSON is large: hypotheses with evidence, root causes, severity,
# comparative analysis, visual observations, etc. Needs more than default.
export A2MC_AI_DIAG_MAX_TOKENS="${A2MC_AI_DIAG_MAX_TOKENS:-32768}"

# API key env var name (auto-derived from provider if empty):
#   anthropic → ANTHROPIC_API_KEY
#   openai    → OPENAI_API_KEY
#   cborg     → CBORG_API_KEY
export A2MC_AI_API_KEY_ENV="${A2MC_AI_API_KEY_ENV:-}"

# ========================
# USE CASE DIRECTORY
# ========================
# Set this to point to the active use case (set by site config)
export A2MC_USE_CASE_DIR="${A2MC_USE_CASE_DIR:-}"

# ========================
# HELPER FUNCTIONS
# ========================

# Get create_newcase command with proper path handling
get_create_newcase_cmd() {
    local pwd=$(pwd)
    local rpwd=$(readlink -f $pwd)
    echo $(sed "s/\/global\//\/dvs_ro\//g" <<< "${A2MC_E3SM_ROOT}/cime/scripts")/create_newcase
}

# Generate case name from components
make_case_name() {
    local prefix=$1
    local case_num=$2
    local suffix=${3:-}
    local phase=$4

    if [ -n "$suffix" ]; then
        echo "${prefix}_${case_num}_${suffix}_${phase}"
    else
        echo "${prefix}_${case_num}_${phase}"
    fi
}

# Print configuration summary
print_config() {
    echo "========================================"
    echo "A2MC Configuration"
    echo "========================================"
    echo "Project: ${A2MC_PROJECT}"
    echo "User: ${A2MC_USER}"
    echo "Machine: ${A2MC_MACHINE}"
    echo "E3SM Root: ${A2MC_E3SM_ROOT}"
    echo "Output Root: ${A2MC_OUTPUT_ROOT}"
    echo ""
    echo "COMPSET Configuration:"
    echo "  Spinup (ADSP/RGSP): ${A2MC_COMPSET_SPINUP}"
    echo "  Transient (TRANS):  ${A2MC_COMPSET_TRANS}"
    echo ""
    echo "Simulation Protocol:"
    echo "  ADSP: ${A2MC_ADSP_YEARS}yr, start=${A2MC_ADSP_START_DATE}, suplphos=${A2MC_ADSP_SUPLPHOS}, suplnitro=${A2MC_ADSP_SUPLNITRO}, ad_C_only=${A2MC_ADSP_NYEARS_AD_CARBON_ONLY}yr"
    echo "  RGSP: ${A2MC_RGSP_YEARS}yr, start=${A2MC_RGSP_START_DATE}, suplphos=${A2MC_RGSP_SUPLPHOS}, suplnitro=${A2MC_RGSP_SUPLNITRO}"
    echo "  TRANS: ${A2MC_TRANS_YEARS}yr, start=${A2MC_TRANS_START_DATE}, suplphos=${A2MC_TRANS_SUPLPHOS}, suplnitro=${A2MC_TRANS_SUPLNITRO}"
    echo ""
    if [ -n "${A2MC_SITE_NAME:-}" ]; then
        echo "Site: ${A2MC_SITE_NAME}"
        echo "Use Case Dir: ${A2MC_USE_CASE_DIR}"
        echo ""
        echo "Ensemble Configuration:"
        echo "  Sampling scheme: ${A2MC_SAMPLING_SCHEME}"
        echo "  Number of parameters: ${A2MC_N_PARAMS}"
        if [ "$A2MC_SAMPLING_SCHEME" = "morris" ]; then
            echo "  Trajectories: ${A2MC_N_TRAJECTORIES}"
        elif [ "$A2MC_SAMPLING_SCHEME" = "subset_replay" ]; then
            echo "  Source round: R${A2MC_REPLAY_SOURCE_ROUND:-?}"
            echo "  Top N cases: ${A2MC_REPLAY_TOP_N:-?}"
        else
            echo "  Samples: ${A2MC_N_SAMPLES}"
        fi
        echo "  Total ensemble size: ${A2MC_TOTAL_ENSEMBLE:-$(calculate_ensemble_size)}"
    else
        echo "No site loaded. Source a site config:"
        echo "  source use_cases/{site}/config/{site}_config.sh"
    fi
    echo ""
    echo "AI Configuration:"
    echo "  Provider: ${A2MC_AI_PROVIDER}"
    echo "  Model: ${A2MC_AI_MODEL}"
    echo "  Max tokens: ${A2MC_AI_MAX_TOKENS}"
    if [ -n "${A2MC_AI_BASE_URL}" ]; then
        echo "  Base URL: ${A2MC_AI_BASE_URL}"
    elif [ "${A2MC_AI_PROVIDER}" = "cborg" ]; then
        echo "  Base URL: https://api.cborg.lbl.gov (auto)"
    fi
    # Derive API key env var name if not explicitly set
    local _key_env="${A2MC_AI_API_KEY_ENV}"
    if [ -z "${_key_env}" ]; then
        case "${A2MC_AI_PROVIDER}" in
            anthropic) _key_env="ANTHROPIC_API_KEY" ;;
            openai)    _key_env="OPENAI_API_KEY" ;;
            cborg)     _key_env="CBORG_API_KEY" ;;
            *)         _key_env="AI_API_KEY" ;;
        esac
    fi
    echo "  API key env: ${_key_env}"
    if [ -n "${!_key_env:-}" ]; then
        echo "  API key set: Yes"
    else
        echo "  API key set: No (set ${_key_env})"
    fi
    echo "========================================"
}

# Validate configuration
validate_config() {
    local errors=0

    if [ ! -d "${A2MC_E3SM_ROOT}" ]; then
        echo "ERROR: E3SM root not found: ${A2MC_E3SM_ROOT}"
        errors=$((errors + 1))
    fi

    if [ -z "${A2MC_SITE_NAME:-}" ]; then
        echo "WARNING: No site configuration loaded"
        echo "  Run: source use_cases/<site>/config/<site>_config.sh"
    fi

    return $errors
}

# Discover available site configs
_A2MC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_A2MC_SITES=()
for _cfg in "${_A2MC_DIR}"/use_cases/*/config/*_config.sh; do
    [ -f "$_cfg" ] && _A2MC_SITES+=("$_cfg")
done

echo "A2MC base configuration loaded."
if [ ${#_A2MC_SITES[@]} -gt 0 ]; then
    echo "Available site configs:"
    for _cfg in "${_A2MC_SITES[@]}"; do
        _rel="${_cfg#${_A2MC_DIR}/}"
        echo "  source ${_rel}"
    done
else
    echo "Next: source use_cases/{site}/config/{site}_config.sh"
fi
unset _A2MC_DIR _A2MC_SITES _cfg _rel
