#!/bin/bash
# =======================================================================================
# R4 SUBSET REPLAY BUNDLE SUBMISSION
# =======================================================================================
# Reads the case list from create_subset_replay.py output, copies the R4 template
# (Kougarok_ELM-FATES_PtCNP162_En2939_PrescP.sh) for each case, sed-replaces the
# casenumber, and runs them in PARALLEL BUNDLES (not sequentially like the R3
# submit4890jobs_*.sh).
#
# All R4 cases reuse R3 case 1's bld via EXEROOT (set inside the template) — no
# rebuild needed.
#
# Usage:
#   ./submit_subset_replay_PrescP.sh
#
# Tunable: BATCH_SIZE (default 20). Larger = more parallelism but more SLURM load.
# =======================================================================================

set -u

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
BATCH_SIZE=${BATCH_SIZE:-20}

# Where the R4 case template lives (the En2939_PrescP.sh script in this directory)
TEMPLATE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_SCRIPT="${TEMPLATE_DIR}/Kougarok_ELM-FATES_PtCNP162_En2939_PrescP.sh"
TEMPLATE_CASENUM=2939   # the literal value in `casenumber=2939` inside the template

# Where to put the per-case scripts (mirrors R3 layout)
CASE_SCRIPTS_DIR=/pscratch/sd/j/jingtao/CaseScripts/Kougarok_FATES/ReCalibration_PtCNP162_AllPhase_PrescribedP

# Where to read the case list from (output of create_subset_replay.py)
CASE_LIST_FILE=${CASE_LIST_FILE:-/global/cfs/cdirs/m2467/jingtao/Kougarok_PlantTraitsCNPEnsemble162_PrescribedP/subset_replay_case_list.txt}

# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------
if [ ! -f "$TEMPLATE_SCRIPT" ]; then
    echo "ERROR: Template script not found: $TEMPLATE_SCRIPT"
    exit 1
fi
if [ ! -f "$CASE_LIST_FILE" ]; then
    echo "ERROR: Case list file not found: $CASE_LIST_FILE"
    echo "       Run phases/phase0_design/create_subset_replay.py first."
    exit 1
fi

mkdir -p "$CASE_SCRIPTS_DIR"

# Read case numbers (skip blank lines and # comments)
CASE_LIST=()
while IFS= read -r _line || [ -n "$_line" ]; do
    _line="${_line#"${_line%%[![:space:]]*}"}"
    _line="${_line%"${_line##*[![:space:]]}"}"
    [ -z "$_line" ] && continue
    case "$_line" in '#'*) continue ;; esac
    CASE_LIST+=("$_line")
done < "$CASE_LIST_FILE"

TOTAL_CASES=${#CASE_LIST[@]}
NUM_BATCHES=$(( (TOTAL_CASES + BATCH_SIZE - 1) / BATCH_SIZE ))

echo "========================================"
echo "R4 Subset Replay Bundle Submission"
echo "========================================"
echo "Template:        $TEMPLATE_SCRIPT"
echo "Case list:       $CASE_LIST_FILE"
echo "Total cases:     $TOTAL_CASES"
echo "Batch size:      $BATCH_SIZE (parallel)"
echo "Number of batches: $NUM_BATCHES"
echo "Case scripts dir:  $CASE_SCRIPTS_DIR"
echo "First 5 cases:   ${CASE_LIST[@]:0:5}"
echo "Last 5 cases:    ${CASE_LIST[@]: -5}"
echo "========================================"
echo ""

# -----------------------------------------------------------------------------
# Submission loop (parallel bundles)
# -----------------------------------------------------------------------------
SUBMIT_ONE_CASE() {
    local n=$1
    local script="${CASE_SCRIPTS_DIR}/Kougarok_ELM-FATES_PtCNP162_En${n}_PrescP.sh"
    local logfile="${CASE_SCRIPTS_DIR}/Kougarok_ELM-FATES_PtCNP162_En${n}_PrescP.log"

    # Copy template and substitute casenumber
    cp "$TEMPLATE_SCRIPT" "$script"
    sed -i "s/casenumber=${TEMPLATE_CASENUM}/casenumber=${n}/g" "$script"
    chmod +x "$script"

    # Run the case script (creates + submits all 3 phases)
    "$script" > "$logfile" 2>&1
    local rc=$?
    if [ $rc -eq 0 ]; then
        echo "  [case $n] OK"
    else
        echo "  [case $n] FAILED (exit $rc) — see $logfile"
    fi
    return $rc
}

n_success=0
n_failed=0

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

    # Wait for all in this batch to finish
    for pid in "${PIDS[@]}"; do
        if wait "$pid"; then
            n_success=$((n_success + 1))
        else
            n_failed=$((n_failed + 1))
        fi
    done

    echo ""
done

echo "========================================"
echo "SUMMARY: ${n_success}/${TOTAL_CASES} successful, ${n_failed} failed"
echo "========================================"
echo "Monitor SLURM jobs with: squeue -u $USER"
echo "Check ensemble status:   python tools/diagnose_ensemble_status.py"

exit $((n_failed > 0 ? 1 : 0))
