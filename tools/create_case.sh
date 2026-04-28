#!/bin/bash
# =======================================================================================
# A2MC Create Case Script
#
# Creates and optionally submits an ELM-FATES case with all three phases (ADSP/RGSP/TRANS)
# Uses SLURM dependencies to run phases automatically in sequence.
#
# Usage:
#   ./create_case.sh --case-num 1 --param-file /path/to/fates_params.nc [options]
#
# Required:
#   --case-num NUM        Case number (e.g., 1, 2, ... 4890)
#   --param-file PATH     Path to FATES parameter file
#
# Optional:
#   --output-root DIR     Override output directory
#   --case-prefix PREFIX  Override case name prefix (default: from config)
#   --case-suffix SUFFIX  Add suffix to case name (e.g., "exp1")
#   --phases PHASES       Which phases to run (default: "ADSP RGSP TRANS")
#   --submit              Submit jobs after creating cases
#   --build-only          Only build, don't submit
#   --skip-build          Skip building (use existing build)
#   --reuse-build NUM     Reuse compiled build from case number NUM (e.g., "1")
#                         Uses A2MC_CASE_NAME_PATTERN to resolve the full case name
#                         Sets EXEROOT and BUILD_COMPLETE=TRUE (implies --skip-build)
#   --config FILE         Path to custom config file
#   --write-script PATH   Write a self-contained reviewable script to PATH
#                         instead of executing (all env vars resolved to literals)
#   --dry-run             Show what would be done without doing it
#   -h, --help            Show this help message
#
# Examples:
#   # Create and submit case 1 with default parameters
#   ./create_case.sh --case-num 1 --param-file params.nc --submit
#
#   # Create case with custom suffix (for experiments)
#   ./create_case.sh --case-num 2678 --param-file params_exp1.nc --case-suffix exp1 --submit
#
#   # Only create TRANS phase (assuming ADSP/RGSP already done)
#   ./create_case.sh --case-num 1 --param-file params.nc --phases TRANS --submit
#
# Author: Jing Tao
# =======================================================================================

set -e  # Exit on error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load configuration (a2mc_config.sh is at the project root, one level up from tools/)
CONFIG_FILE="${SCRIPT_DIR}/../a2mc_config.sh"
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
else
    echo "ERROR: Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# v2.88: layer the active round-specific config on top of a2mc_config.sh
# defaults if A2MC_SITE_CONFIG was set in the parent shell (e.g., by sourcing
# kougarok_config_r4.sh). Without this, sourcing a2mc_config.sh above clobbers
# any round-specific overrides (A2MC_ADSP_SUPLNITRO, A2MC_RGSP_SUPLPHOS, etc.)
# the user established in their parent shell, silently producing simulations
# with the wrong protocol. The --config CLI flag still takes precedence (it
# is processed in the arg loop below); this only fires when --config is NOT
# given AND a round config is identifiable via A2MC_SITE_CONFIG.
if [ -n "${A2MC_SITE_CONFIG:-}" ] && [ -f "$A2MC_SITE_CONFIG" ] && \
   [ "$A2MC_SITE_CONFIG" != "$CONFIG_FILE" ]; then
    source "$A2MC_SITE_CONFIG"
fi

# ========================
# ARGUMENT PARSING
# ========================

CASE_NUM=""
PARAM_FILE=""
OUTPUT_ROOT="${A2MC_OUTPUT_ROOT}"
CASE_PREFIX="${A2MC_ENSEMBLE_PREFIX}"
CASE_SUFFIX=""
RUN_PHASES=("ADSP" "RGSP" "TRANS")
DO_SUBMIT=false
BUILD_ONLY=false
SKIP_BUILD=false
REUSE_BUILD=""  # Case number whose compiled build to reuse (e.g., "1")
DRY_RUN=false
WRITE_SCRIPT=""  # Path to write self-contained script instead of executing

print_usage() {
    head -50 "$0" | grep -A 100 "^# Usage:" | grep "^#" | sed 's/^# //'
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --case-num)
            CASE_NUM="$2"
            shift 2
            ;;
        --param-file)
            PARAM_FILE="$2"
            shift 2
            ;;
        --output-root)
            OUTPUT_ROOT="$2"
            shift 2
            ;;
        --case-prefix)
            CASE_PREFIX="$2"
            shift 2
            ;;
        --case-suffix)
            CASE_SUFFIX="$2"
            shift 2
            ;;
        --phases)
            IFS=' ' read -r -a RUN_PHASES <<< "$2"
            shift 2
            ;;
        --submit)
            DO_SUBMIT=true
            shift
            ;;
        --build-only)
            BUILD_ONLY=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --reuse-build)
            REUSE_BUILD="$2"
            SKIP_BUILD=true
            shift 2
            ;;
        --config)
            source "$2"
            shift 2
            ;;
        --write-script)
            WRITE_SCRIPT="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

# Validate required arguments
if [ -z "$CASE_NUM" ]; then
    echo "ERROR: --case-num is required"
    print_usage
    exit 1
fi

if [ -z "$PARAM_FILE" ]; then
    echo "ERROR: --param-file is required"
    print_usage
    exit 1
fi

# ========================
# CASE NAME GENERATION
# ========================

# Derive BASE_CASE_NAME from A2MC_CASE_NAME_PATTERN for naming consistency.
# Pattern example: "Kougarok_ELM-FATES_PtCNPEn{N}_{PHASE}"
# Strip _{PHASE} to get the base, replace {N} with CASE_NUM.
if [ -n "${A2MC_CASE_NAME_PATTERN:-}" ]; then
    # Derive from pattern: strip {PHASE} placeholder, substitute {N}
    BASE_CASE_NAME=$(echo "${A2MC_CASE_NAME_PATTERN}" | sed 's/_{PHASE}//' | sed "s/{N}/${CASE_NUM}/")
else
    # Fallback when pattern is not set
    BASE_CASE_NAME="${CASE_PREFIX}_En${CASE_NUM}"
fi

if [ -n "$CASE_SUFFIX" ]; then
    BASE_CASE_NAME="${BASE_CASE_NAME}_${CASE_SUFFIX}"
fi

if [ -z "${A2MC_ENSEMBLE_OUTPUT:-}" ]; then
    echo "ERROR: A2MC_ENSEMBLE_OUTPUT is not set. Source your site config first."
    exit 1
fi
CIME_OUTPUT_ROOT="${A2MC_ENSEMBLE_OUTPUT}/"

echo "========================================"
echo "A2MC Create Case"
echo "========================================"
echo "Case Number: ${CASE_NUM}"
echo "Parameter File: ${PARAM_FILE}"
echo "Base Case Name: ${BASE_CASE_NAME}"
echo "Output Root: ${CIME_OUTPUT_ROOT}"
echo "Phases: ${RUN_PHASES[*]}"
echo "Submit: ${DO_SUBMIT}"
echo "========================================"

if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN] Would create case with above settings"
    exit 0
fi

# ========================
# WRITE SELF-CONTAINED SCRIPT (--write-script mode)
# ========================

if [ -n "$WRITE_SCRIPT" ]; then
    # Resolve all A2MC_* variables to their current literal values
    # and write a self-contained script that can be reviewed and run standalone

    # Build phase-specific blocks
    _ws_phases_str="${RUN_PHASES[*]}"
    _ws_reuse_build="${REUSE_BUILD}"
    _ws_skip_build="${SKIP_BUILD}"

    cat > "$WRITE_SCRIPT" <<'SCRIPT_HEADER'
#!/bin/bash
# =======================================================================================
# A2MC Experiment Script (Auto-generated, self-contained)
#
# This script was generated by create_case.sh --write-script.
# All environment variables have been resolved to literal values.
# Review this script, then run it on HPC:
#   bash THIS_SCRIPT.sh
#
# Author: Jing Tao
# =======================================================================================

set -e

SCRIPT_HEADER

    # Write resolved configuration as literal variables
    cat >> "$WRITE_SCRIPT" <<EOF
# ========================
# RESOLVED CONFIGURATION
# ========================
# Generated: $(date '+%Y-%m-%d %H:%M:%S')
# Source: create_case.sh --write-script

CASE_NUM="${CASE_NUM}"
PARAM_FILE="${PARAM_FILE}"
BASE_CASE_NAME="${BASE_CASE_NAME}"
CASE_PREFIX="${CASE_PREFIX}"
CIME_OUTPUT_ROOT="${CIME_OUTPUT_ROOT}"
RUN_PHASES=(${_ws_phases_str})

# E3SM/ELM paths
E3SM_ROOT="${A2MC_E3SM_ROOT}"
CREATE_NEWCASE_CMD="$(get_create_newcase_cmd)"

# Domain and forcing
RES="${A2MC_RES}"
MACHINE="${A2MC_MACHINE}"
PROJECT="${A2MC_PROJECT}"
COMPILER="${A2MC_COMPILER}"
COMPSET_SPINUP="${A2MC_COMPSET_SPINUP}"
COMPSET_TRANS="${A2MC_COMPSET_TRANS}"
DIN_LOC_ROOT="${A2MC_DIN_LOC_ROOT}"
DIN_LOC_ROOT_CLMFORC="${A2MC_DIN_LOC_ROOT_CLMFORC}"
DOMAIN_DIR="${A2MC_DOMAIN_DIR}"
DOMAIN_FILE="${A2MC_DOMAIN_FILE}"
SURFACE_FILE="${A2MC_SURFACE_FILE}"
DATM_MODE="${A2MC_DATM_MODE}"
SITE_NAME="${A2MC_SITE_NAME}"
FORCING_DIR="${A2MC_FORCING_DIR}"

# Job settings
NTASKS="${A2MC_NTASKS}"
WALLTIME="${A2MC_WALLTIME}"
QUEUE="${A2MC_QUEUE}"
MEMORY="${A2MC_MEMORY}"
EMAIL="${A2MC_EMAIL:-}"
ELM_OPTIONS="${A2MC_ELM_OPTIONS}"

# FATES settings
USE_FATES="${A2MC_USE_FATES}"
FATES_PARTEH_MODE="${A2MC_FATES_PARTEH_MODE}"
USE_FATES_NOCOMP="${A2MC_USE_FATES_NOCOMP}"
SOILORDER_DIR="${A2MC_SOILORDER_DIR}"
SOILORDER_FILE="${A2MC_SOILORDER_FILE}"
HIST_SZPF_VARS="${A2MC_HIST_SZPF_VARS}"

# Simulation years
ADSP_YEARS="${A2MC_ADSP_YEARS}"
ADSP_REST="${A2MC_ADSP_REST}"
RGSP_YEARS="${A2MC_RGSP_YEARS}"
RGSP_REST="${A2MC_RGSP_REST}"
TRANS_YEARS="${A2MC_TRANS_YEARS}"
TRANS_REST="${A2MC_TRANS_REST}"
SPINUP_START_YEAR="${A2MC_SPINUP_START_YEAR}"
SPINUP_END_YEAR="${A2MC_SPINUP_END_YEAR}"
TRANS_START_YEAR="${A2MC_TRANS_START_YEAR}"
TRANS_END_YEAR="${A2MC_TRANS_END_YEAR}"

# Phase-specific ELM settings
ADSP_BGC_SPINUP="${A2MC_ADSP_BGC_SPINUP}"
ADSP_START_DATE="${A2MC_ADSP_START_DATE}"
ADSP_SUPLPHOS="${A2MC_ADSP_SUPLPHOS}"
ADSP_SUPLNITRO="${A2MC_ADSP_SUPLNITRO}"
ADSP_NYEARS_AD_CARBON_ONLY="${A2MC_ADSP_NYEARS_AD_CARBON_ONLY}"
ADSP_FINIDAT="${A2MC_ADSP_FINIDAT}"
RGSP_START_DATE="${A2MC_RGSP_START_DATE}"
RGSP_SUPLPHOS="${A2MC_RGSP_SUPLPHOS}"
RGSP_SUPLNITRO="${A2MC_RGSP_SUPLNITRO}"
RGSP_RESTART_DATE="${A2MC_RGSP_RESTART_DATE}"
TRANS_START_DATE="${A2MC_TRANS_START_DATE}"
TRANS_SUPLPHOS="${A2MC_TRANS_SUPLPHOS}"
TRANS_SUPLNITRO="${A2MC_TRANS_SUPLNITRO}"
TRANS_RESTART_DATE="${A2MC_TRANS_RESTART_DATE}"
HIST_MFILT="${A2MC_HIST_MFILT}"
HIST_NHTFRQ="${A2MC_HIST_NHTFRQ}"

# Ensemble settings
ENSEMBLE_PREFIX="${A2MC_ENSEMBLE_PREFIX}"
CASE_NAME_PATTERN="${A2MC_CASE_NAME_PATTERN}"

# Build reuse
REUSE_BUILD="${_ws_reuse_build}"
SKIP_BUILD=${_ws_skip_build}
EOF

    # Write the functions and main loop as literal script (no variable expansion)
    cat >> "$WRITE_SCRIPT" <<'SCRIPT_BODY'

# ========================
# CREATE PHASE CASE
# ========================

create_phase_case() {
    local PHASE=$1

    echo ""
    echo "========================================"
    echo "Creating phase: $PHASE"
    echo "========================================"

    CASE_NAME="${BASE_CASE_NAME}_${PHASE}"

    # Set COMPSET based on phase
    if [ "$PHASE" = "ADSP" ] || [ "$PHASE" = "RGSP" ]; then
        COMPSET="${COMPSET_SPINUP}"
    elif [ "$PHASE" = "TRANS" ]; then
        COMPSET="${COMPSET_TRANS}"
    fi

    # Return to scripts directory
    cd "${E3SM_ROOT}/cime/scripts"

    # Clean up existing case
    rm -rf "$CASE_NAME"
    rm -rf "${CIME_OUTPUT_ROOT}${CASE_NAME}"

    # Create the case
    echo "Running: $CREATE_NEWCASE_CMD -case $CASE_NAME ..."
    $CREATE_NEWCASE_CMD -case "$CASE_NAME" \
        -res "${RES}" \
        -compset "$COMPSET" \
        -mach "${MACHINE}" \
        -project "${PROJECT}" \
        -compiler "${COMPILER}"

    cd "${CASE_NAME}"

    # Set paths
    ./xmlchange CIME_OUTPUT_ROOT="${CIME_OUTPUT_ROOT}"
    ./xmlchange DIN_LOC_ROOT="${DIN_LOC_ROOT}"
    ./xmlchange DIN_LOC_ROOT_CLMFORC="${DIN_LOC_ROOT_CLMFORC}"

    ./xmlchange ATM_DOMAIN_FILE="${DOMAIN_FILE}"
    ./xmlchange ATM_DOMAIN_PATH="${DOMAIN_DIR}"
    ./xmlchange LND_DOMAIN_FILE="${DOMAIN_FILE}"
    ./xmlchange LND_DOMAIN_PATH="${DOMAIN_DIR}"
    ./xmlchange DATM_MODE="${DATM_MODE}"
    ./xmlchange ELM_USRDAT_NAME="${SITE_NAME}"

    ./xmlchange NTASKS="${NTASKS}"
    ./xmlchange ATM_GRID="${RES}"
    ./xmlchange LND_GRID="${RES}"

    ./xmlchange --append ELM_BLDNML_OPTS="${ELM_OPTIONS}"
    ./xmlchange DEBUG=FALSE
    ./xmlchange STOP_OPTION=nyears
    ./xmlchange REST_OPTION=nyears
    ./xmlchange JOB_WALLCLOCK_TIME="${WALLTIME}"
    ./xmlchange GMAKE=make

    # Phase-specific settings (all from resolved config variables)
    if [ "$PHASE" = "ADSP" ]; then
        ./xmlchange --append ELM_BLDNML_OPTS="-bgc_spinup ${ADSP_BGC_SPINUP}"
        ./xmlchange STOP_N="${ADSP_YEARS}"
        ./xmlchange REST_N="${ADSP_REST}"
        ./xmlchange RUN_STARTDATE="${ADSP_START_DATE}"
        ./xmlchange DATM_CLMNCEP_YR_START="${SPINUP_START_YEAR}"
        ./xmlchange DATM_CLMNCEP_YR_END="${SPINUP_END_YEAR}"
        RESTART_FILE=""
    elif [ "$PHASE" = "RGSP" ]; then
        ./xmlchange STOP_N="${RGSP_YEARS}"
        ./xmlchange REST_N="${RGSP_REST}"
        ./xmlchange RUN_STARTDATE="${RGSP_START_DATE}"
        ./xmlchange DATM_CLMNCEP_YR_START="${SPINUP_START_YEAR}"
        ./xmlchange DATM_CLMNCEP_YR_END="${SPINUP_END_YEAR}"
        RESTART_FILE="${CIME_OUTPUT_ROOT}${BASE_CASE_NAME}_ADSP/run/${BASE_CASE_NAME}_ADSP.elm.r.${RGSP_RESTART_DATE}.nc"
    elif [ "$PHASE" = "TRANS" ]; then
        ./xmlchange STOP_N="${TRANS_YEARS}"
        ./xmlchange REST_N="${TRANS_REST}"
        ./xmlchange RUN_STARTDATE="${TRANS_START_DATE}"
        ./xmlchange DATM_CLMNCEP_YR_START="${TRANS_START_YEAR}"
        ./xmlchange DATM_CLMNCEP_YR_END="${TRANS_END_YEAR}"
        RESTART_FILE="${CIME_OUTPUT_ROOT}${BASE_CASE_NAME}_RGSP/run/${BASE_CASE_NAME}_RGSP.elm.r.${TRANS_RESTART_DATE}.nc"
    fi

    # Create ELM namelist
    cat >> user_nl_elm <<NLEOF
hist_mfilt = ${HIST_MFILT}
hist_nhtfrq = ${HIST_NHTFRQ}
fsurdat = '${DOMAIN_DIR}/${SURFACE_FILE}'

use_fates=${USE_FATES}
fates_parteh_mode = ${FATES_PARTEH_MODE}
use_fates_nocomp = ${USE_FATES_NOCOMP}
fates_paramfile = '${PARAM_FILE}'
fsoilordercon = '${SOILORDER_DIR}/${SOILORDER_FILE}'
hist_fincl1=${HIST_SZPF_VARS}
NLEOF

    # Phase-specific namelist additions
    if [ "$PHASE" = "ADSP" ]; then
        echo "suplphos = '${ADSP_SUPLPHOS}'" >> user_nl_elm
        echo "suplnitro = '${ADSP_SUPLNITRO}'" >> user_nl_elm
        echo "finidat = '${ADSP_FINIDAT}'" >> user_nl_elm
        echo "nyears_ad_carbon_only = ${ADSP_NYEARS_AD_CARBON_ONLY}" >> user_nl_elm
    elif [ "$PHASE" = "RGSP" ]; then
        echo "suplphos = '${RGSP_SUPLPHOS}'" >> user_nl_elm
        echo "suplnitro = '${RGSP_SUPLNITRO}'" >> user_nl_elm
        echo "finidat = '${RESTART_FILE}'" >> user_nl_elm
    elif [ "$PHASE" = "TRANS" ]; then
        echo "suplphos = '${TRANS_SUPLPHOS}'" >> user_nl_elm
        echo "suplnitro = '${TRANS_SUPLNITRO}'" >> user_nl_elm
        echo "finidat = '${RESTART_FILE}'" >> user_nl_elm
    fi

    # MOSART namelist
    cat > user_nl_mosart <<NLEOF
do_rtm = .false.
NLEOF

    # DATM namelist
    cat >> user_nl_datm <<NLEOF
taxmode = "cycle", "cycle", "cycle","extend"
NLEOF

    # Copy forcing redirects
    if [ -d "${FORCING_DIR}" ]; then
        cp "${FORCING_DIR}"/user_datm.streams.txt* ./ 2>/dev/null || true
    fi

    # Build or reuse existing build
    if [ -n "$REUSE_BUILD" ]; then
        if [ -z "${CASE_NAME_PATTERN:-}" ]; then
            echo "ERROR: CASE_NAME_PATTERN is not set. Source your site config first."
            exit 1
        fi
        REUSE_CASE=$(echo "${CASE_NAME_PATTERN}" | sed "s/{N}/${REUSE_BUILD}/" | sed "s/{PHASE}/${PHASE}/")
        REUSE_EXEROOT="${CIME_OUTPUT_ROOT}${REUSE_CASE}/bld"
        echo "Reusing build from: ${REUSE_CASE}"
        ./xmlchange EXEROOT="${REUSE_EXEROOT}"
        ./xmlchange BUILD_COMPLETE=TRUE

        # Setup and preview after EXEROOT is set
        ./case.setup
        ./preview_namelists
    else
        # Setup and preview before building
        ./case.setup
        ./preview_namelists

        if [ "$SKIP_BUILD" = false ]; then
            echo "Building case..."
            ./case.build
        fi
    fi

    # Create placeholder restart file for RGSP/TRANS
    if [ -n "$RESTART_FILE" ]; then
        mkdir -p "$(dirname "$RESTART_FILE")"
        touch "$RESTART_FILE"
    fi

    echo "Phase $PHASE created successfully: $CASE_NAME"
}

# ========================
# SUBMIT PHASE CASE
# ========================

submit_phase_case() {
    local PHASE=$1
    local DEPEND_JOBID=$2

    CASE_NAME="${BASE_CASE_NAME}_${PHASE}"
    cd "${E3SM_ROOT}/cime/scripts/${CASE_NAME}"

    # Build batch args
    BATCH_ARGS="-q ${QUEUE} --mem=${MEMORY}"
    if [ -n "${EMAIL}" ]; then
        BATCH_ARGS="${BATCH_ARGS} --mail-type=ALL --mail-user=${EMAIL}"
    fi
    if [ -n "$DEPEND_JOBID" ]; then
        BATCH_ARGS="${BATCH_ARGS} --dependency=afterok:${DEPEND_JOBID}"
    fi

    # Submit
    SUBMIT_OUTPUT=$(./case.submit --batch-args="$BATCH_ARGS" 2>&1)
    echo "$SUBMIT_OUTPUT" >&2

    # Extract job ID
    JOBID=$(echo "$SUBMIT_OUTPUT" | grep -oP '(?:Submitted job id is |with id )\K[0-9]+' | head -1 || echo "")
    if [ -z "$JOBID" ]; then
        sleep 2
        JOBID=$(squeue -u "$USER" -n "$CASE_NAME" -h -o "%i" | head -1)
    fi

    if [ -n "$JOBID" ]; then
        echo "Phase $PHASE submitted: Job ID $JOBID" >&2
    else
        echo "Warning: Could not extract job ID for $PHASE" >&2
    fi

    echo "$JOBID"
}

# ========================
# MAIN EXECUTION
# ========================

# Array to store job IDs
declare -A JOB_IDS

# Create all phase cases
for PHASE in "${RUN_PHASES[@]}"; do
    create_phase_case "$PHASE"
done

# Submit jobs
echo ""
echo "========================================"
echo "Submitting jobs..."
echo "========================================"

PREV_JOBID=""
for PHASE in "${RUN_PHASES[@]}"; do
    JOBID=$(submit_phase_case "$PHASE" "$PREV_JOBID")
    PREV_JOBID="$JOBID"
    JOB_IDS[$PHASE]="$JOBID"
done

echo ""
echo "========================================"
echo "All phases submitted!"
echo "========================================"
for PHASE in "${RUN_PHASES[@]}"; do
    if [ -n "${JOB_IDS[$PHASE]}" ]; then
        echo "$PHASE: Job ID ${JOB_IDS[$PHASE]}"
    fi
done

echo ""
echo "========================================"
echo "Case creation complete: ${BASE_CASE_NAME}"
echo "========================================"
echo "Monitor with: squeue -u $USER"
SCRIPT_BODY

    chmod +x "$WRITE_SCRIPT"
    echo "Self-contained script written to: $WRITE_SCRIPT"
    exit 0
fi

# Get create_newcase command
cd "${A2MC_E3SM_ROOT}/cime/scripts"
CREATE_NEWCASE_CMD=$(get_create_newcase_cmd)

# Array to store job IDs
declare -A JOB_IDS

# ========================
# CREATE PHASE CASE
# ========================

create_phase_case() {
    local PHASE=$1

    echo ""
    echo "========================================"
    echo "Creating phase: $PHASE"
    echo "========================================"

    CASE_NAME="${BASE_CASE_NAME}_${PHASE}"

    # Set COMPSET based on phase (from a2mc_config.sh)
    if [ "$PHASE" = "ADSP" ] || [ "$PHASE" = "RGSP" ]; then
        COMPSET="${A2MC_COMPSET_SPINUP}"
    elif [ "$PHASE" = "TRANS" ]; then
        COMPSET="${A2MC_COMPSET_TRANS}"
    fi

    # Return to scripts directory
    cd "${A2MC_E3SM_ROOT}/cime/scripts"

    # Clean up existing case
    rm -rf "$CASE_NAME"
    rm -rf "${CIME_OUTPUT_ROOT}${CASE_NAME}"

    # Create the case
    echo "Running: $CREATE_NEWCASE_CMD -case $CASE_NAME ..."
    $CREATE_NEWCASE_CMD -case "$CASE_NAME" \
        -res "${A2MC_RES}" \
        -compset "$COMPSET" \
        -mach "${A2MC_MACHINE}" \
        -project "${A2MC_PROJECT}" \
        -compiler "${A2MC_COMPILER}"

    cd "${CASE_NAME}"

    # Set paths
    ./xmlchange CIME_OUTPUT_ROOT="${CIME_OUTPUT_ROOT}"
    ./xmlchange DIN_LOC_ROOT="${A2MC_DIN_LOC_ROOT}"
    ./xmlchange DIN_LOC_ROOT_CLMFORC="${A2MC_DIN_LOC_ROOT_CLMFORC}"

    ./xmlchange ATM_DOMAIN_FILE="${A2MC_DOMAIN_FILE}"
    ./xmlchange ATM_DOMAIN_PATH="${A2MC_DOMAIN_DIR}"
    ./xmlchange LND_DOMAIN_FILE="${A2MC_DOMAIN_FILE}"
    ./xmlchange LND_DOMAIN_PATH="${A2MC_DOMAIN_DIR}"
    ./xmlchange DATM_MODE="${A2MC_DATM_MODE}"
    ./xmlchange ELM_USRDAT_NAME="${A2MC_SITE_NAME}"

    ./xmlchange NTASKS="${A2MC_NTASKS}"
    ./xmlchange ATM_GRID="${A2MC_RES}"
    ./xmlchange LND_GRID="${A2MC_RES}"

    ./xmlchange --append ELM_BLDNML_OPTS="${A2MC_ELM_OPTIONS}"
    ./xmlchange DEBUG=FALSE
    ./xmlchange STOP_OPTION=nyears
    ./xmlchange REST_OPTION=nyears
    ./xmlchange JOB_WALLCLOCK_TIME="${A2MC_WALLTIME}"
    ./xmlchange GMAKE=make

    # Phase-specific settings (all from a2mc_config.sh / site config)
    if [ "$PHASE" = "ADSP" ]; then
        ./xmlchange --append ELM_BLDNML_OPTS="-bgc_spinup ${A2MC_ADSP_BGC_SPINUP}"
        ./xmlchange STOP_N="${A2MC_ADSP_YEARS}"
        ./xmlchange REST_N="${A2MC_ADSP_REST}"
        ./xmlchange RUN_STARTDATE="${A2MC_ADSP_START_DATE}"
        ./xmlchange DATM_CLMNCEP_YR_START="${A2MC_SPINUP_START_YEAR}"
        ./xmlchange DATM_CLMNCEP_YR_END="${A2MC_SPINUP_END_YEAR}"
        RESTART_FILE=""
    elif [ "$PHASE" = "RGSP" ]; then
        ./xmlchange STOP_N="${A2MC_RGSP_YEARS}"
        ./xmlchange REST_N="${A2MC_RGSP_REST}"
        ./xmlchange RUN_STARTDATE="${A2MC_RGSP_START_DATE}"
        ./xmlchange DATM_CLMNCEP_YR_START="${A2MC_SPINUP_START_YEAR}"
        ./xmlchange DATM_CLMNCEP_YR_END="${A2MC_SPINUP_END_YEAR}"
        RESTART_FILE="${CIME_OUTPUT_ROOT}${BASE_CASE_NAME}_ADSP/run/${BASE_CASE_NAME}_ADSP.elm.r.${A2MC_RGSP_RESTART_DATE}.nc"
    elif [ "$PHASE" = "TRANS" ]; then
        ./xmlchange STOP_N="${A2MC_TRANS_YEARS}"
        ./xmlchange REST_N="${A2MC_TRANS_REST}"
        ./xmlchange RUN_STARTDATE="${A2MC_TRANS_START_DATE}"
        ./xmlchange DATM_CLMNCEP_YR_START="${A2MC_TRANS_START_YEAR}"
        ./xmlchange DATM_CLMNCEP_YR_END="${A2MC_TRANS_END_YEAR}"
        RESTART_FILE="${CIME_OUTPUT_ROOT}${BASE_CASE_NAME}_RGSP/run/${BASE_CASE_NAME}_RGSP.elm.r.${A2MC_TRANS_RESTART_DATE}.nc"
    fi

    # Create ELM namelist
    cat >> user_nl_elm <<EOF
hist_mfilt = ${A2MC_HIST_MFILT}
hist_nhtfrq = ${A2MC_HIST_NHTFRQ}
fsurdat = '${A2MC_DOMAIN_DIR}/${A2MC_SURFACE_FILE}'

use_fates=${A2MC_USE_FATES}
fates_parteh_mode = ${A2MC_FATES_PARTEH_MODE}
use_fates_nocomp = ${A2MC_USE_FATES_NOCOMP}
fates_paramfile = '${PARAM_FILE}'
fsoilordercon = '${A2MC_SOILORDER_DIR}/${A2MC_SOILORDER_FILE}'
hist_fincl1=${A2MC_HIST_SZPF_VARS}
EOF

    # Phase-specific namelist additions
    if [ "$PHASE" = "ADSP" ]; then
        echo "suplphos = '${A2MC_ADSP_SUPLPHOS}'" >> user_nl_elm
        echo "suplnitro = '${A2MC_ADSP_SUPLNITRO}'" >> user_nl_elm
        echo "finidat = '${A2MC_ADSP_FINIDAT}'" >> user_nl_elm
        echo "nyears_ad_carbon_only = ${A2MC_ADSP_NYEARS_AD_CARBON_ONLY}" >> user_nl_elm
    elif [ "$PHASE" = "RGSP" ]; then
        echo "suplphos = '${A2MC_RGSP_SUPLPHOS}'" >> user_nl_elm
        echo "suplnitro = '${A2MC_RGSP_SUPLNITRO}'" >> user_nl_elm
        echo "finidat = '${RESTART_FILE}'" >> user_nl_elm
    elif [ "$PHASE" = "TRANS" ]; then
        echo "suplphos = '${A2MC_TRANS_SUPLPHOS}'" >> user_nl_elm
        echo "suplnitro = '${A2MC_TRANS_SUPLNITRO}'" >> user_nl_elm
        echo "finidat = '${RESTART_FILE}'" >> user_nl_elm
    fi

    # MOSART namelist
    cat > user_nl_mosart <<EOF
do_rtm = .false.
EOF

    # DATM namelist
    cat >> user_nl_datm <<EOF
taxmode = "cycle", "cycle", "cycle","extend"
EOF

    # Copy forcing redirects
    if [ -d "${A2MC_FORCING_DIR}" ]; then
        cp "${A2MC_FORCING_DIR}"/user_datm.streams.txt* ./ 2>/dev/null || true
    fi

    # Build or reuse existing build
    if [ -n "$REUSE_BUILD" ]; then
        # Reuse compiled binary from another case
        # Use CASE_NAME_PATTERN to resolve the full case name (consistent with --write-script)
        if [ -n "${A2MC_CASE_NAME_PATTERN:-}" ]; then
            REUSE_CASE=$(echo "${A2MC_CASE_NAME_PATTERN}" | sed "s/{N}/${REUSE_BUILD}/" | sed "s/{PHASE}/${PHASE}/")
        else
            echo "ERROR: A2MC_CASE_NAME_PATTERN is not set. Source your site config first."
            exit 1
        fi
        REUSE_EXEROOT="${CIME_OUTPUT_ROOT}${REUSE_CASE}/bld"
        echo "Reusing build from: ${REUSE_CASE}"
        ./xmlchange EXEROOT="${REUSE_EXEROOT}"
        ./xmlchange BUILD_COMPLETE=TRUE

        # Setup and preview after EXEROOT is set
        ./case.setup
        ./preview_namelists
    else
        # Setup and preview before building
        ./case.setup
        ./preview_namelists

        if [ "$SKIP_BUILD" = false ]; then
            echo "Building case..."
            ./case.build
        fi
    fi

    # Create placeholder restart file for RGSP/TRANS
    if [ -n "$RESTART_FILE" ]; then
        mkdir -p "$(dirname "$RESTART_FILE")"
        touch "$RESTART_FILE"
    fi

    echo "Phase $PHASE created successfully: $CASE_NAME"
}

# ========================
# SUBMIT PHASE CASE
# ========================

submit_phase_case() {
    local PHASE=$1
    local DEPEND_JOBID=$2

    CASE_NAME="${BASE_CASE_NAME}_${PHASE}"
    cd "${A2MC_E3SM_ROOT}/cime/scripts/${CASE_NAME}"

    # Build batch args
    BATCH_ARGS="-q ${A2MC_QUEUE} --mem=${A2MC_MEMORY}"
    if [ -n "${A2MC_EMAIL}" ]; then
        BATCH_ARGS="${BATCH_ARGS} --mail-type=ALL --mail-user=${A2MC_EMAIL}"
    fi
    if [ -n "$DEPEND_JOBID" ]; then
        BATCH_ARGS="${BATCH_ARGS} --dependency=afterok:${DEPEND_JOBID}"
    fi

    # Submit
    SUBMIT_OUTPUT=$(./case.submit --batch-args="$BATCH_ARGS" 2>&1)
    echo "$SUBMIT_OUTPUT" >&2

    # Extract job ID
    JOBID=$(echo "$SUBMIT_OUTPUT" | grep -oP '(?:Submitted job id is |with id )\K[0-9]+' | head -1 || echo "")
    if [ -z "$JOBID" ]; then
        sleep 2
        JOBID=$(squeue -u "$USER" -n "$CASE_NAME" -h -o "%i" | head -1)
    fi

    if [ -n "$JOBID" ]; then
        echo "Phase $PHASE submitted: Job ID $JOBID" >&2
    else
        echo "Warning: Could not extract job ID for $PHASE" >&2
    fi

    echo "$JOBID"
}

# ========================
# MAIN EXECUTION
# ========================

# Create all phase cases
for PHASE in "${RUN_PHASES[@]}"; do
    create_phase_case "$PHASE"
done

# Submit if requested
if [ "$DO_SUBMIT" = true ] && [ "$BUILD_ONLY" = false ]; then
    echo ""
    echo "========================================"
    echo "Submitting jobs..."
    echo "========================================"

    PREV_JOBID=""
    for PHASE in "${RUN_PHASES[@]}"; do
        JOBID=$(submit_phase_case "$PHASE" "$PREV_JOBID")
        PREV_JOBID="$JOBID"
        JOB_IDS[$PHASE]="$JOBID"
    done

    echo ""
    echo "========================================"
    echo "All phases submitted!"
    echo "========================================"
    for PHASE in "${RUN_PHASES[@]}"; do
        if [ -n "${JOB_IDS[$PHASE]}" ]; then
            echo "$PHASE: Job ID ${JOB_IDS[$PHASE]}"
        fi
    done
fi

echo ""
echo "========================================"
echo "Case creation complete: ${BASE_CASE_NAME}"
echo "========================================"
echo "Monitor with: squeue -u $USER"
