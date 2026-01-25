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
#   --config FILE         Path to custom config file
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

# Load configuration
CONFIG_FILE="${SCRIPT_DIR}/a2mc_config.sh"
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
else
    echo "ERROR: Configuration file not found: $CONFIG_FILE"
    exit 1
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
DRY_RUN=false

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
        --config)
            source "$2"
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

if [ -n "$CASE_SUFFIX" ]; then
    BASE_CASE_NAME="${CASE_PREFIX}_En${CASE_NUM}_${CASE_SUFFIX}"
else
    BASE_CASE_NAME="${CASE_PREFIX}_En${CASE_NUM}"
fi

CIME_OUTPUT_ROOT="${OUTPUT_ROOT}/${CASE_PREFIX}_${A2MC_TOTAL_ENSEMBLE}Ensemble/"

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

    # Phase-specific settings
    if [ "$PHASE" = "ADSP" ]; then
        ./xmlchange --append ELM_BLDNML_OPTS="-bgc_spinup on"
        ./xmlchange STOP_N="${A2MC_ADSP_YEARS}"
        ./xmlchange REST_N="${A2MC_ADSP_REST}"
        ./xmlchange RUN_STARTDATE='0001-01-01'
        ./xmlchange DATM_CLMNCEP_YR_START="${A2MC_SPINUP_START_YEAR}"
        ./xmlchange DATM_CLMNCEP_YR_END="${A2MC_SPINUP_END_YEAR}"
        RESTART_FILE=""
    elif [ "$PHASE" = "RGSP" ]; then
        ./xmlchange STOP_N="${A2MC_RGSP_YEARS}"
        ./xmlchange REST_N="${A2MC_RGSP_REST}"
        ./xmlchange RUN_STARTDATE='0201-01-01'
        ./xmlchange DATM_CLMNCEP_YR_START="${A2MC_SPINUP_START_YEAR}"
        ./xmlchange DATM_CLMNCEP_YR_END="${A2MC_SPINUP_END_YEAR}"
        RESTART_FILE="${CIME_OUTPUT_ROOT}${BASE_CASE_NAME}_ADSP/run/${BASE_CASE_NAME}_ADSP.elm.r.0201-01-01-00000.nc"
    elif [ "$PHASE" = "TRANS" ]; then
        ./xmlchange STOP_N="${A2MC_TRANS_YEARS}"
        ./xmlchange REST_N="${A2MC_TRANS_REST}"
        ./xmlchange RUN_STARTDATE='1901-01-01'
        ./xmlchange DATM_CLMNCEP_YR_START="${A2MC_TRANS_START_YEAR}"
        ./xmlchange DATM_CLMNCEP_YR_END="${A2MC_TRANS_END_YEAR}"
        RESTART_FILE="${CIME_OUTPUT_ROOT}${BASE_CASE_NAME}_RGSP/run/${BASE_CASE_NAME}_RGSP.elm.r.0401-01-01-00000.nc"
    fi

    # Create ELM namelist
    cat >> user_nl_elm <<EOF
hist_mfilt = 12
hist_nhtfrq = 0
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
        echo "suplphos = 'ALL'" >> user_nl_elm
        echo "suplnitro = 'NONE'" >> user_nl_elm
        echo "finidat = ''" >> user_nl_elm
        echo "nyears_ad_carbon_only = 30" >> user_nl_elm
    else
        echo "suplphos = 'NONE'" >> user_nl_elm
        echo "suplnitro = 'NONE'" >> user_nl_elm
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

    # Setup case
    ./case.setup

    # Preview namelists
    ./preview_namelists

    # Build (unless skipped)
    if [ "$SKIP_BUILD" = false ]; then
        echo "Building case..."
        ./case.build
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
