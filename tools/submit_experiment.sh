#!/bin/bash
# =======================================================================================
# A2MC Submit Experiment Script
#
# Lightweight script for submitting a single A2MC experiment.
# Designed for hypothesis testing in the iterative calibration loop.
#
# Unlike submit_ensemble.sh (for thousands of Morris cases), this script:
# - Handles a single experiment at a time
# - Can use existing restart files from a base case
# - Provides quick feedback for calibration iteration
#
# Usage:
#   ./submit_experiment.sh --name exp1 --param-file /path/to/params.nc [options]
#
# Required:
#   --name NAME           Experiment name (e.g., "exp1", "test_turnover")
#   --param-file PATH     Path to modified FATES parameter file
#
# Optional:
#   --base-case NAME      Base case to start from (uses its restart file)
#   --output-root DIR     Override output directory
#   --phases PHASES       Which phases to run (default: "TRANS" for experiments)
#   --restart-file PATH   Explicit path to restart file
#   --submit              Submit after building
#   --wait                Wait for job completion and report results
#   --timeout SEC         Max wait time in seconds (default: 86400 = 24h)
#   --config FILE         Custom configuration file
#   --dry-run             Show what would be done
#   -h, --help            Show this help
#
# Examples:
#   # Quick experiment using existing base case spinup (TRANS only)
#   ./submit_experiment.sh --name test_stc3 \
#     --param-file /path/to/fates_params_modified.nc \
#     --base-case En2678 --submit
#
#   # Use parameter from Morris ensemble with modification
#   ./submit_experiment.sh --name test_turnover5 \
#     --param-file ${A2MC_PARAM_DIR}/fates_params_api25.5.0_12pft_c230710__PtCNP162_En2678_modified.nc \
#     --base-case En2678 --submit
#
#   # Full 3-phase experiment (new spinup from scratch)
#   ./submit_experiment.sh --name full_test \
#     --param-file params.nc \
#     --phases "ADSP RGSP TRANS" --submit
#
#   # Wait for completion and check results
#   ./submit_experiment.sh --name exp1 \
#     --param-file params.nc \
#     --base-case En2678 --submit --wait
#
#   # Dry run to preview experiment setup
#   ./submit_experiment.sh --name test1 \
#     --param-file params.nc \
#     --base-case En2678 --dry-run
#
# Note: For submitting multiple ensemble cases, use submit_ensemble.sh instead:
#   ./submit_ensemble.sh --start 1 --end 4890 --submit
#
# Author: Jing Tao
# =======================================================================================

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load configuration (a2mc_config.sh is at the project root, one level up from tools/)
source "${SCRIPT_DIR}/../a2mc_config.sh"

# ========================
# ARGUMENT PARSING
# ========================

EXP_NAME=""
PARAM_FILE=""
BASE_CASE=""
OUTPUT_ROOT="${A2MC_OUTPUT_ROOT}"
RUN_PHASES="ADSP RGSP TRANS"  # Default: full spinup required for modified params
REUSE_BUILD="En1"             # Default: reuse En1's build (first Morris case)
RESTART_FILE=""
DO_SUBMIT=false
DO_WAIT=false
TIMEOUT=86400
DRY_RUN=false

print_usage() {
    head -50 "$0" | grep -A 100 "^# Usage:" | grep "^#" | sed 's/^# //'
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --name)
            EXP_NAME="$2"
            shift 2
            ;;
        --param-file)
            PARAM_FILE="$2"
            shift 2
            ;;
        --base-case)
            BASE_CASE="$2"
            shift 2
            ;;
        --output-root)
            OUTPUT_ROOT="$2"
            shift 2
            ;;
        --phases)
            RUN_PHASES="$2"
            shift 2
            ;;
        --restart-file)
            RESTART_FILE="$2"
            shift 2
            ;;
        --reuse-build)
            REUSE_BUILD="$2"
            shift 2
            ;;
        --no-reuse-build)
            REUSE_BUILD=""
            shift
            ;;
        --submit)
            DO_SUBMIT=true
            shift
            ;;
        --wait)
            DO_WAIT=true
            shift
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
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
if [ -z "$EXP_NAME" ]; then
    echo "ERROR: --name is required"
    print_usage
    exit 1
fi

if [ -z "$PARAM_FILE" ]; then
    echo "ERROR: --param-file is required"
    print_usage
    exit 1
fi

# ========================
# DETERMINE RESTART FILE
# ========================

# If TRANS-only and no restart file specified, try to find from base case
if [[ "$RUN_PHASES" == "TRANS" ]] && [ -z "$RESTART_FILE" ]; then
    if [ -n "$BASE_CASE" ]; then
        # Look for base case restart file
        POSSIBLE_RESTART="${OUTPUT_ROOT}/${A2MC_ENSEMBLE_PREFIX}_${BASE_CASE}_RGSP/run/${A2MC_ENSEMBLE_PREFIX}_${BASE_CASE}_RGSP.elm.r.0401-01-01-00000.nc"

        if [ -f "$POSSIBLE_RESTART" ]; then
            RESTART_FILE="$POSSIBLE_RESTART"
            echo "Using restart file from base case: ${BASE_CASE}"
        else
            # Try alternate path patterns
            for pattern in \
                "${OUTPUT_ROOT}/*${BASE_CASE}*_RGSP/run/*.elm.r.0401-01-01-00000.nc" \
                "${OUTPUT_ROOT}/*${BASE_CASE}*/run/*RGSP*.elm.r.0401-01-01-00000.nc"
            do
                files=($pattern)
                if [ -f "${files[0]}" ]; then
                    RESTART_FILE="${files[0]}"
                    echo "Found restart file: ${RESTART_FILE}"
                    break
                fi
            done
        fi

        if [ -z "$RESTART_FILE" ]; then
            echo "WARNING: Could not find restart file for base case ${BASE_CASE}"
            echo "Either provide --restart-file or run with --phases 'ADSP RGSP TRANS'"
        fi
    fi
fi

# ========================
# CASE SETUP
# ========================

CASE_NAME="${A2MC_ENSEMBLE_PREFIX}_${EXP_NAME}"
CIME_OUTPUT_ROOT="${OUTPUT_ROOT}/${CASE_NAME}_experiment/"

echo "========================================"
echo "A2MC Experiment Submission"
echo "========================================"
echo "Experiment Name: ${EXP_NAME}"
echo "Case Name: ${CASE_NAME}"
echo "Parameter File: ${PARAM_FILE}"
echo "Output Root: ${CIME_OUTPUT_ROOT}"
echo "Phases: ${RUN_PHASES}"
if [ -n "$BASE_CASE" ]; then
    echo "Base Case: ${BASE_CASE}"
fi
if [ -n "$RESTART_FILE" ]; then
    echo "Restart File: ${RESTART_FILE}"
fi
echo "Submit: ${DO_SUBMIT}"
echo "Wait: ${DO_WAIT}"
echo "========================================"

if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN] Would create experiment with above settings"
    exit 0
fi

# ========================
# CREATE CASE
# ========================

# Use create_case.sh for actual case creation
CREATE_CASE_CMD="${SCRIPT_DIR}/create_case.sh"
CREATE_CASE_CMD="$CREATE_CASE_CMD --case-num ${EXP_NAME}"
CREATE_CASE_CMD="$CREATE_CASE_CMD --param-file ${PARAM_FILE}"
CREATE_CASE_CMD="$CREATE_CASE_CMD --output-root ${OUTPUT_ROOT}"
CREATE_CASE_CMD="$CREATE_CASE_CMD --phases \"${RUN_PHASES}\""

if [ -n "$REUSE_BUILD" ]; then
    CREATE_CASE_CMD="$CREATE_CASE_CMD --reuse-build ${REUSE_BUILD}"
fi

if [ "$DO_SUBMIT" = true ]; then
    CREATE_CASE_CMD="$CREATE_CASE_CMD --submit"
fi

echo ""
echo "Running: $CREATE_CASE_CMD"
echo ""

# Execute case creation
eval "$CREATE_CASE_CMD"

# ========================
# WAIT FOR COMPLETION
# ========================

if [ "$DO_WAIT" = true ] && [ "$DO_SUBMIT" = true ]; then
    echo ""
    echo "========================================"
    echo "Waiting for job completion..."
    echo "========================================"

    # Find the job ID
    PHASE=$(echo "$RUN_PHASES" | awk '{print $NF}')  # Last phase
    FULL_CASE_NAME="${CASE_NAME}_${PHASE}"

    START_TIME=$(date +%s)

    while true; do
        # Check if job is still in queue
        JOB_INFO=$(squeue -u "$USER" -n "$FULL_CASE_NAME" -h -o "%i %T" 2>/dev/null || true)

        if [ -z "$JOB_INFO" ]; then
            # Job not in queue - check if completed
            echo "Job not in queue - checking completion status..."

            # Look for completion indicators
            RUN_DIR="${CIME_OUTPUT_ROOT}${FULL_CASE_NAME}/run"
            if [ -d "$RUN_DIR" ]; then
                # Check for output files
                OUTPUT_FILES=$(ls "$RUN_DIR"/*.elm.h0.*.nc 2>/dev/null | wc -l || echo 0)
                if [ "$OUTPUT_FILES" -gt 0 ]; then
                    echo "SUCCESS: Found ${OUTPUT_FILES} output files"
                    echo "Output directory: ${RUN_DIR}"
                    break
                fi
            fi

            # Check for error logs
            if [ -d "$RUN_DIR" ]; then
                ERROR_LOG=$(ls -t "$RUN_DIR"/*.log.* 2>/dev/null | head -1)
                if [ -f "$ERROR_LOG" ]; then
                    echo "Checking log file: $ERROR_LOG"
                    if grep -qi "error\|fail\|abort" "$ERROR_LOG"; then
                        echo "WARNING: Possible errors in log file"
                        tail -20 "$ERROR_LOG"
                    fi
                fi
            fi

            break
        fi

        JOB_ID=$(echo "$JOB_INFO" | awk '{print $1}')
        JOB_STATUS=$(echo "$JOB_INFO" | awk '{print $2}')
        echo "Job ${JOB_ID}: ${JOB_STATUS}"

        # Check timeout
        ELAPSED=$(($(date +%s) - START_TIME))
        if [ $ELAPSED -gt $TIMEOUT ]; then
            echo "TIMEOUT: Job still running after ${TIMEOUT}s"
            break
        fi

        sleep 60
    done

    echo ""
    echo "========================================"
    echo "Experiment Complete"
    echo "========================================"
fi

echo ""
echo "Experiment ${EXP_NAME} processed."
echo "Output location: ${CIME_OUTPUT_ROOT}"
