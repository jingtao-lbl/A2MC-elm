#!/bin/bash
# =======================================================================================
# R4 (ADSPSupNP) FULL MORRIS BUNDLE SUBMISSION — cases 3 to 4890
# =======================================================================================
# Modeled on submit_subset_replay_PrescP.sh but adapted for the redesigned R4
# (full 4890-case Morris ensemble, ADSP_SUPLPHOS=ALL + ADSP_SUPLNITRO=ALL,
# RGSP/TRANS supplementation OFF, FATES rebuilt with gradual hydraulic
# mortality + prescribed_puptake correctness fix).
#
# Workflow assumption:
#   - En1_ADSPSupNP.sh was built fresh on the patched FATES (this is
#     the case that produces the compiled bld all subsequent cases
#     reuse via EXEROOT). It is currently running.
#   - En2_ADSPSupNP.sh has been tested independently and proved that
#     bld reuse from case 1 works correctly. It is the canonical
#     TEMPLATE for cases 3..4890 because it has the right "reuse
#     existing bld" structure, whereas En1 has the build-from-scratch
#     structure that is one-off.
#
# This script submits cases 3..4890 (or any range you specify) in PARALLEL
# BATCHES by copying the En2_ADSPSupNP.sh template, sed-replacing
# `casenumber=2` with each target case number, and running the resulting
# per-case scripts in batches.
#
# Usage:
#   ./submit_full_morris_ADSPSupNP.sh                          # default: 3..4890
#   ./submit_full_morris_ADSPSupNP.sh --start 3 --end 100      # subset
#   ./submit_full_morris_ADSPSupNP.sh --start 3 --end 4890 --batch-size 30
#   START_CASE=3 END_CASE=4890 BATCH_SIZE=20 ./submit_full_morris_ADSPSupNP.sh
#
# Tunable: BATCH_SIZE (default 20). Larger = more parallelism but more SLURM
# load.
#
# Notes:
#   - Cases 1 and 2 are DEFAULT-EXCLUDED from the start of the range because
#     the user has already submitted/tested them. To re-include them, pass
#     --start 1 explicitly.
#   - Each case script creates ADSP/RGSP/TRANS CIME cases with SLURM
#     afterok dependencies and submits all three to SLURM. So one
#     successful exit from the case script means the case is queued, not
#     finished.
# =======================================================================================

set -u

# -----------------------------------------------------------------------------
# Defaults (overridable via CLI or env)
# -----------------------------------------------------------------------------
BATCH_SIZE=${BATCH_SIZE:-20}
START_CASE=${START_CASE:-3}
END_CASE=${END_CASE:-4890}

# -----------------------------------------------------------------------------
# CLI parsing
# -----------------------------------------------------------------------------
while [ $# -gt 0 ]; do
    case "$1" in
        --start)      START_CASE="$2";  shift 2 ;;
        --end)        END_CASE="$2";    shift 2 ;;
        --batch-size) BATCH_SIZE="$2";  shift 2 ;;
        -h|--help)
            sed -n '2,40p' "$0"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run with -h for usage."
            exit 1
            ;;
    esac
done

# -----------------------------------------------------------------------------
# Per-round paths (matches kougarok_config_r4.sh and calibration_rounds.yaml)
# -----------------------------------------------------------------------------

# Where the per-case scripts live. The user has already placed
# Kougarok_ELM-FATES_PtCNP162_En1_ADSPSupNP.sh (build-from-scratch, running)
# and Kougarok_ELM-FATES_PtCNP162_En2_ADSPSupNP.sh (bld-reuse, tested) here.
CASE_SCRIPTS_DIR=/pscratch/sd/j/jingtao/CaseScripts/Kougarok_FATES/ReCalibration_PtCNP162_AllPhase_ADSPSupNP

# Use En2 as the canonical template — it has the bld-reuse structure that
# every case 3..4890 needs (each reuses the bld compiled by En1 via EXEROOT).
# We sed-replace `casenumber=2` with the target case number per case.
# (En1 is NOT a suitable template: it has the build-from-scratch structure
# that is one-off and would attempt a full recompile per case.)
TEMPLATE_SCRIPT="${CASE_SCRIPTS_DIR}/Kougarok_ELM-FATES_PtCNP162_En2_ADSPSupNP.sh"
TEMPLATE_CASENUM=2   # the literal value in `casenumber=2` inside the template

# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------
if [ ! -f "$TEMPLATE_SCRIPT" ]; then
    echo "ERROR: Template script not found: $TEMPLATE_SCRIPT"
    echo "Expected En2_ADSPSupNP.sh to exist (the bld-reuse template)."
    echo "If you have only En1_ADSPSupNP.sh, you need to create En2 first"
    echo "by adapting En1 for bld reuse from case 1."
    exit 1
fi
if [ ! -d "$CASE_SCRIPTS_DIR" ]; then
    echo "ERROR: Case scripts directory not found: $CASE_SCRIPTS_DIR"
    exit 1
fi
if [ "$START_CASE" -lt 1 ] || [ "$END_CASE" -gt 4890 ] || [ "$START_CASE" -gt "$END_CASE" ]; then
    echo "ERROR: invalid case range [$START_CASE, $END_CASE]"
    echo "       Expected 1 <= START_CASE <= END_CASE <= 4890"
    exit 1
fi

# Build the case-number list (range mode — full Morris is sequential 1..4890)
CASE_LIST=()
for ((n=START_CASE; n<=END_CASE; n++)); do
    CASE_LIST+=("$n")
done

TOTAL_CASES=${#CASE_LIST[@]}
NUM_BATCHES=$(( (TOTAL_CASES + BATCH_SIZE - 1) / BATCH_SIZE ))

echo "========================================"
echo "R4 ADSPSupNP Full Morris Bundle Submission"
echo "========================================"
echo "Template:          $TEMPLATE_SCRIPT"
echo "Case scripts dir:  $CASE_SCRIPTS_DIR"
echo "Range:             ${START_CASE}..${END_CASE}  (${TOTAL_CASES} cases)"
echo "Batch size:        $BATCH_SIZE (parallel within each batch)"
echo "Number of batches: $NUM_BATCHES"
echo "First 5 cases:     ${CASE_LIST[@]:0:5}"
echo "Last 5 cases:      ${CASE_LIST[@]: -5}"
echo "========================================"
echo ""

# -----------------------------------------------------------------------------
# Submission helper — runs one case
# -----------------------------------------------------------------------------
SUBMIT_ONE_CASE() {
    local n=$1
    local script="${CASE_SCRIPTS_DIR}/Kougarok_ELM-FATES_PtCNP162_En${n}_ADSPSupNP.sh"
    local logfile="${CASE_SCRIPTS_DIR}/Kougarok_ELM-FATES_PtCNP162_En${n}_ADSPSupNP.log"

    # Skip the template's own case number — En2 was the case used as the
    # template, don't overwrite/relaunch it. (Default --start is 3, so this
    # only fires if the user explicitly widens the range to include 2.)
    if [ "$n" -eq "$TEMPLATE_CASENUM" ]; then
        echo "  [case $n] SKIPPED (this is the template case, already tested)"
        return 0
    fi

    # If a per-case script already exists (e.g. En2 the user tested), reuse it
    # rather than overwrite. This avoids clobbering a script that may have
    # been hand-edited or already submitted.
    if [ ! -f "$script" ]; then
        cp "$TEMPLATE_SCRIPT" "$script"
        sed -i "s/casenumber=${TEMPLATE_CASENUM}/casenumber=${n}/g" "$script"
        chmod +x "$script"
    fi

    # Run the case script (creates + submits all 3 phases via SLURM afterok)
    "$script" > "$logfile" 2>&1
    local rc=$?
    if [ $rc -eq 0 ]; then
        echo "  [case $n] OK"
    else
        echo "  [case $n] FAILED (exit $rc) — see $logfile"
    fi
    return $rc
}

# -----------------------------------------------------------------------------
# Submission loop (parallel bundles)
# -----------------------------------------------------------------------------
n_success=0
n_failed=0
n_skipped=0

for ((batch=0; batch<NUM_BATCHES; batch++)); do
    BATCH_IDX_START=$((batch * BATCH_SIZE))
    BATCH_IDX_END=$((BATCH_IDX_START + BATCH_SIZE - 1))
    if [ $BATCH_IDX_END -ge $TOTAL_CASES ]; then
        BATCH_IDX_END=$((TOTAL_CASES - 1))
    fi

    BATCH_FIRST=${CASE_LIST[$BATCH_IDX_START]}
    BATCH_LAST=${CASE_LIST[$BATCH_IDX_END]}
    BATCH_SIZE_THIS=$((BATCH_IDX_END - BATCH_IDX_START + 1))

    echo "----------------------------------------"
    echo "Batch $((batch + 1))/${NUM_BATCHES}: cases ${BATCH_FIRST}..${BATCH_LAST} (${BATCH_SIZE_THIS} parallel)"
    echo "----------------------------------------"

    # Launch all cases in this batch in parallel
    PIDS=()
    for ((idx=BATCH_IDX_START; idx<=BATCH_IDX_END; idx++)); do
        n=${CASE_LIST[$idx]}
        SUBMIT_ONE_CASE "$n" &
        PIDS+=($!)
        sleep 0.2
    done

    # Wait for all in this batch to finish (case scripts return after SLURM
    # accepts the jobs; actual simulation continues asynchronously on the
    # SLURM queue)
    for pid in "${PIDS[@]}"; do
        if wait "$pid"; then
            n_success=$((n_success + 1))
        else
            n_failed=$((n_failed + 1))
        fi
    done

    echo ""
done

# Adjust counts: SUBMIT_ONE_CASE returns 0 for skips too, so distinguish them
# by looking at the output log (best effort — for accurate counts use the
# per-case logs).
echo "========================================"
echo "SUMMARY: ${n_success}/${TOTAL_CASES} returned success, ${n_failed} failed"
echo "(Note: returned-success includes skipped template case $TEMPLATE_CASENUM if in range.)"
echo "========================================"
echo "Monitor SLURM queue:    squeue -u \$USER"
echo "Check ensemble status:  python tools/diagnose_ensemble_status.py"
echo "Per-case logs:          ${CASE_SCRIPTS_DIR}/Kougarok_*_ADSPSupNP.log"

exit $((n_failed > 0 ? 1 : 0))
