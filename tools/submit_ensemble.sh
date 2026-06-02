#!/bin/bash
# =======================================================================================
# A2MC Submit Ensemble Script
#
# DEPRECATED in favor of phases/phase0_design/submit_phase0.py (added in
# the 2026-05-11 Phase 0 refactor). The new orchestrator does the same
# work plus:
#   - Generates per-case scripts via `create_case.sh --write-script` so
#     each case's full configuration is auditable on disk
#   - Coordinates the build case (fresh build) vs reuse cases automatically
#     (no manual two-step --start 1 --end 1 / --start 2 --end N pattern)
#   - Runs a pre-flight validator (tools/validate_submission_plan.py) and
#     refuses to submit on errors
#   - Writes $A2MC_ENSEMBLE_OUTPUT/submission_manifest.json for audit
# See: docs/20_Phase_0_R5_Refactor_Plan.md
#      memory/dev_logs/20260511f_Phase0_P5_Submit_Phase0_Orchestrator.md
#
# This script is kept for backwards compatibility and as a fallback if
# the new path needs hardening. New ensembles should use:
#   python phases/phase0_design/submit_phase0.py --start N --end M --submit
#
# Submits multiple ensemble cases using create_case.sh as the template.
# Supports parallel submission with configurable batch sizes.
#
# Usage:
#   ./submit_ensemble.sh --start 1 --end 100 [options]
#   ./submit_ensemble.sh --cases-file r4_case_list.txt [options]
#
# Required (provide ONE of these two modes):
#   Range mode:    --start NUM --end NUM
#   Cases-file mode: --cases-file FILE   (one case number per line, # for comments)
#
#   --start NUM           Starting case number (range mode)
#   --end NUM             Ending case number (range mode)
#   --cases-file FILE     Text file with non-sequential case numbers (one per line).
#                         Used for subset_replay rounds where R4 case numbers
#                         match R3 source case numbers (e.g., 86, 2939, 1385, ...)
#
# Optional (defaults from a2mc_config.sh):
#   --param-dir DIR       Directory containing parameter files
#                         (default: $A2MC_PARAM_DIR from config)
#   --param-pattern PAT   Pattern for param files, {N} = case number
#                         (default: $A2MC_PARAM_PATTERN from config)
#   --output-root DIR     Override output directory
#   --case-prefix PREFIX  Override case name prefix
#   --case-suffix SUFFIX  Add suffix to case name
#   --batch-size NUM      Number of cases to submit in parallel (default: 10)
#   --delay SEC           Seconds between batch submissions (default: 5)
#   --phases PHASES       Which phases to run (default: "ADSP RGSP TRANS")
#   --submit              Actually submit (default: just build)
#   --skip-build          Skip building (use existing builds)
#   --reuse-build NUM     Reuse compiled build from case number NUM (e.g., "1").
#                         Forwarded to create_case.sh; sets EXEROOT and
#                         BUILD_COMPLETE=TRUE for each case in the loop.
#   --log-dir DIR         Directory for log files (default: ./logs)
#   --dry-run             Show what would be done
#   -h, --help            Show this help
#
# Examples:
#   # Submit Morris ensemble cases 1-100 (uses defaults from a2mc_config.sh)
#   ./submit_ensemble.sh --start 1 --end 100 --submit
#
#   # Submit full 4890-case ensemble with custom batch size
#   ./submit_ensemble.sh --start 1 --end 4890 --batch-size 50 --submit
#
#   # Submit with explicit parameter directory and pattern
#   ./submit_ensemble.sh --start 1 --end 100 \
#     --param-dir /path/to/fates_params \
#     --param-pattern "fates_params_api25.5.0_12pft_c230710__PtCNP162_En{N}.nc" \
#     --submit
#
#   # Only submit TRANS phase for cases that already have spinup complete
#   ./submit_ensemble.sh --start 1 --end 100 --phases TRANS --submit
#
#   # Dry run to see what would be submitted
#   ./submit_ensemble.sh --start 1 --end 10 --dry-run
#
# Author: A2MC Framework
# =======================================================================================

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load configuration (a2mc_config.sh is at the project root, one level up from tools/)
source "${SCRIPT_DIR}/../a2mc_config.sh"

# v2.88: layer the active round-specific config on top of a2mc_config.sh
# defaults if A2MC_SITE_CONFIG was set in the parent shell (e.g., by sourcing
# kougarok_config_r4.sh). The unconditional `source a2mc_config.sh` above
# clobbers any round-specific overrides (A2MC_ADSP_SUPLNITRO,
# A2MC_RGSP_SUPLPHOS, A2MC_ENSEMBLE_NAME, etc.) the user established in their
# parent shell, silently producing ensemble submissions that use the wrong
# protocol or the wrong output paths. Re-sourcing the round config here
# restores them.
if [ -n "${A2MC_SITE_CONFIG:-}" ] && [ -f "$A2MC_SITE_CONFIG" ] && \
   [ "$A2MC_SITE_CONFIG" != "${SCRIPT_DIR}/../a2mc_config.sh" ]; then
    source "$A2MC_SITE_CONFIG"
fi

# ========================
# ARGUMENT PARSING
# ========================

START_NUM=""
END_NUM=""
CASES_FILE=""                              # Alternative to --start/--end: list of case numbers
PARAM_DIR="${A2MC_PARAM_DIR:-}"           # Default from config
# Note: bash parameter expansion ${VAR:-default} misparses `}` inside the default
# when the default contains `{N}` (the inner `}` closes the expansion early).
# Use a separate variable to avoid the bug.
_DEFAULT_PARAM_PATTERN='fates_params_*_En{N}.nc'
PARAM_PATTERN="${A2MC_PARAM_PATTERN:-$_DEFAULT_PARAM_PATTERN}"  # Default from config
OUTPUT_ROOT="${A2MC_OUTPUT_ROOT}"
CASE_PREFIX="${A2MC_ENSEMBLE_PREFIX}"
CASE_SUFFIX=""
BATCH_SIZE=10
DELAY=5
RUN_PHASES="ADSP RGSP TRANS"
DO_SUBMIT=false
SKIP_BUILD=false
REUSE_BUILD=""             # Forward to create_case.sh's --reuse-build NUM
LOG_DIR="./logs"
DRY_RUN=false

print_usage() {
    head -50 "$0" | grep -A 100 "^# Usage:" | grep "^#" | sed 's/^# //'
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --start)
            START_NUM="$2"
            shift 2
            ;;
        --end)
            END_NUM="$2"
            shift 2
            ;;
        --cases-file)
            CASES_FILE="$2"
            shift 2
            ;;
        --param-dir)
            PARAM_DIR="$2"
            shift 2
            ;;
        --param-pattern)
            PARAM_PATTERN="$2"
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
        --batch-size)
            BATCH_SIZE="$2"
            shift 2
            ;;
        --delay)
            DELAY="$2"
            shift 2
            ;;
        --phases)
            RUN_PHASES="$2"
            shift 2
            ;;
        --submit)
            DO_SUBMIT=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --reuse-build)
            REUSE_BUILD="$2"
            shift 2
            ;;
        --log-dir)
            LOG_DIR="$2"
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

# Validate required arguments — accept either (--start and --end) OR --cases-file
if [ -n "$CASES_FILE" ]; then
    # Cases-file mode: read non-sequential case numbers from a file
    if [ ! -f "$CASES_FILE" ]; then
        echo "ERROR: Cases file not found: $CASES_FILE"
        exit 1
    fi
    # Build CASE_LIST array (skip blank lines and # comments)
    # Use while-read loop for bash 3.x compatibility (mapfile is bash 4+)
    CASE_LIST=()
    while IFS= read -r _line || [ -n "$_line" ]; do
        # Strip whitespace
        _line="${_line#"${_line%%[![:space:]]*}"}"
        _line="${_line%"${_line##*[![:space:]]}"}"
        # Skip blank lines and comments
        [ -z "$_line" ] && continue
        case "$_line" in '#'*) continue ;; esac
        CASE_LIST+=("$_line")
    done < "$CASES_FILE"
    if [ ${#CASE_LIST[@]} -eq 0 ]; then
        echo "ERROR: Cases file is empty (or only comments): $CASES_FILE"
        exit 1
    fi
    if [ -n "$START_NUM" ] || [ -n "$END_NUM" ]; then
        echo "ERROR: --cases-file cannot be combined with --start/--end"
        exit 1
    fi
    USE_CASES_FILE=true
elif [ -z "$START_NUM" ] || [ -z "$END_NUM" ]; then
    echo "ERROR: must provide either (--start and --end) OR --cases-file"
    print_usage
    exit 1
else
    # Range mode: build CASE_LIST from sequential range
    USE_CASES_FILE=false
    CASE_LIST=()
    for ((n=START_NUM; n<=END_NUM; n++)); do
        CASE_LIST+=("$n")
    done
fi

if [ -z "$PARAM_DIR" ]; then
    echo "ERROR: --param-dir is required (or set A2MC_PARAM_DIR in a2mc_config.sh)"
    print_usage
    exit 1
fi

if [ ! -d "$PARAM_DIR" ]; then
    echo "ERROR: Parameter directory not found: $PARAM_DIR"
    echo "Check A2MC_PARAM_DIR in a2mc_config.sh or use --param-dir"
    exit 1
fi

# Create log directory
mkdir -p "$LOG_DIR"

# ========================
# SUMMARY
# ========================

TOTAL_CASES=${#CASE_LIST[@]}
NUM_BATCHES=$(( (TOTAL_CASES + BATCH_SIZE - 1) / BATCH_SIZE ))

echo "========================================"
echo "A2MC Ensemble Submission"
echo "========================================"
if [ "$USE_CASES_FILE" = true ]; then
    echo "Cases file: ${CASES_FILE} (${TOTAL_CASES} cases, non-sequential)"
    echo "First 5 cases: ${CASE_LIST[@]:0:5}"
    echo "Last 5 cases:  ${CASE_LIST[@]: -5}"
else
    echo "Cases: ${START_NUM} to ${END_NUM} (${TOTAL_CASES} total)"
fi
echo "Parameter directory: ${PARAM_DIR}"
echo "Parameter pattern: ${PARAM_PATTERN}"
echo "Batch size: ${BATCH_SIZE}"
echo "Number of batches: ${NUM_BATCHES}"
echo "Phases: ${RUN_PHASES}"
echo "Submit: ${DO_SUBMIT}"
echo "Log directory: ${LOG_DIR}"
echo "========================================"

if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN] Would submit ${TOTAL_CASES} cases in ${NUM_BATCHES} batches"
    exit 0
fi

# ========================
# SUBMISSION FUNCTIONS
# ========================

# Find parameter file for a given case number
find_param_file() {
    local case_num=$1
    local pattern="${PARAM_PATTERN/\{N\}/${case_num}}"

    # Try direct pattern match
    local files=(${PARAM_DIR}/${pattern})
    if [ -f "${files[0]}" ]; then
        echo "${files[0]}"
        return 0
    fi

    # Try with wildcard
    local files=(${PARAM_DIR}/*En${case_num}*.nc ${PARAM_DIR}/*_${case_num}.nc ${PARAM_DIR}/*_${case_num}_*.nc)
    for f in "${files[@]}"; do
        if [ -f "$f" ]; then
            echo "$f"
            return 0
        fi
    done

    echo ""
    return 1
}

# Submit a single case
submit_case() {
    local case_num=$1
    local param_file=$2
    local log_file="${LOG_DIR}/case_${case_num}.log"

    # Build command
    local cmd="${SCRIPT_DIR}/create_case.sh"
    cmd="$cmd --case-num ${case_num}"
    cmd="$cmd --param-file ${param_file}"
    cmd="$cmd --output-root ${OUTPUT_ROOT}"
    cmd="$cmd --case-prefix ${CASE_PREFIX}"
    cmd="$cmd --phases \"${RUN_PHASES}\""

    # v2.88: forward the active round config to create_case.sh via --config so
    # the round-specific protocol overrides reach the per-case namelist.
    # Without this, create_case.sh would only see a2mc_config.sh defaults.
    if [ -n "${A2MC_SITE_CONFIG:-}" ] && [ -f "$A2MC_SITE_CONFIG" ]; then
        cmd="$cmd --config ${A2MC_SITE_CONFIG}"
    fi

    if [ -n "$CASE_SUFFIX" ]; then
        cmd="$cmd --case-suffix ${CASE_SUFFIX}"
    fi

    if [ "$DO_SUBMIT" = true ]; then
        cmd="$cmd --submit"
    fi

    if [ "$SKIP_BUILD" = true ]; then
        cmd="$cmd --skip-build"
    fi

    if [ -n "$REUSE_BUILD" ]; then
        cmd="$cmd --reuse-build ${REUSE_BUILD}"
    fi

    # Run in background with logging
    echo "Submitting case ${case_num}..."
    eval "$cmd" > "$log_file" 2>&1 &
    echo $!
}

# ========================
# MAIN SUBMISSION LOOP
# ========================

echo ""
echo "Starting ensemble submission..."
echo ""

TOTAL_SUBMITTED=0
TOTAL_FAILED=0
declare -a PIDS

for ((batch=0; batch<NUM_BATCHES; batch++)); do
    # Index range into CASE_LIST array
    BATCH_IDX_START=$((batch * BATCH_SIZE))
    BATCH_IDX_END=$((BATCH_IDX_START + BATCH_SIZE - 1))
    if [ $BATCH_IDX_END -ge $TOTAL_CASES ]; then
        BATCH_IDX_END=$((TOTAL_CASES - 1))
    fi

    BATCH_FIRST_CASE=${CASE_LIST[$BATCH_IDX_START]}
    BATCH_LAST_CASE=${CASE_LIST[$BATCH_IDX_END]}

    echo "========================================"
    echo "Batch $((batch + 1))/${NUM_BATCHES}: Cases ${BATCH_FIRST_CASE} ... ${BATCH_LAST_CASE} ($((BATCH_IDX_END - BATCH_IDX_START + 1)) cases)"
    echo "========================================"

    PIDS=()

    # Submit cases in this batch
    for ((idx=BATCH_IDX_START; idx<=BATCH_IDX_END; idx++)); do
        n=${CASE_LIST[$idx]}

        # Find parameter file
        PARAM_FILE=$(find_param_file $n)

        if [ -z "$PARAM_FILE" ]; then
            echo "WARNING: No parameter file found for case ${n}, skipping"
            TOTAL_FAILED=$((TOTAL_FAILED + 1))
            continue
        fi

        # Submit case
        PID=$(submit_case $n "$PARAM_FILE")
        PIDS+=($PID)
        TOTAL_SUBMITTED=$((TOTAL_SUBMITTED + 1))

        # Small delay between submissions within batch
        sleep 0.5
    done

    # Wait for batch to complete
    echo "Waiting for batch ${batch+1} to complete..."
    for pid in "${PIDS[@]}"; do
        wait $pid 2>/dev/null || true
    done

    # Delay between batches
    if [ $((batch + 1)) -lt $NUM_BATCHES ]; then
        echo "Pausing ${DELAY}s before next batch..."
        sleep $DELAY
    fi
done

# ========================
# SUMMARY
# ========================

echo ""
echo "========================================"
echo "Ensemble Submission Complete"
echo "========================================"
echo "Total cases submitted: ${TOTAL_SUBMITTED}"
echo "Total cases failed: ${TOTAL_FAILED}"
echo "Log directory: ${LOG_DIR}"
echo ""
echo "Monitor jobs with: squeue -u $USER"
echo "Check logs with: tail -f ${LOG_DIR}/case_*.log"
echo "========================================"
