#!/bin/bash
# =======================================================================================
# A2MC Model Evolution — wait for both V0 jobs to finish, then compare
#
# Generalizes the phen_split #17 V0-check's wait_and_compare_v0.sh
# (use_cases/ELM-FATES_Kougarok/memory/phase_results/20260712_phen_split_v0_api43/wait_and_compare_v0.sh)
# into a site-agnostic tool. Polls squeue for BOTH case-name patterns; detects a crashed
# chain early via DependencyNeverSatisfied (a dead chain never resolves to "gone from
# queue" the way a healthy finish does — see arm-hpc-monitoring skill Step 7); once both
# are gone from the queue, hands off to compare_v0.py.
#
# Usage:
#   tools/model_evolution/wait_and_compare_v0.sh \
#       --case-a-pattern <squeue_name_substring> --run-dir-a <path> \
#       --case-b-pattern <squeue_name_substring> --run-dir-b <path> \
#       [--poll-interval SECONDS] [--mode auto|netcdf|log] [--key-vars v1,v2,...]
#
# Required:
#   --case-a-pattern PAT   Substring to grep in `squeue -o "%j"` for job A (the fix/off case).
#   --run-dir-a PATH       Run directory to pass to compare_v0.py as A once A finishes.
#   --case-b-pattern PAT   Substring for job B (the baseline case).
#   --run-dir-b PATH       Run directory to pass to compare_v0.py as B once B finishes.
#
# Optional:
#   --poll-interval SEC    Default 60 (a V0 check is normally short; the phen_split
#                          precedent used 300s for a full multi-year TRANS chain — raise
#                          this for a similarly long run to reduce polling overhead).
#   --mode / --key-vars    Passed through to compare_v0.py.
#
# Exit codes: 0 = V0-at-equality PASS, 1 = FAIL, 2 = a chain crashed
#             (DependencyNeverSatisfied), 3 = jobs left the queue without producing output.
#
# Author: Jing Tao with Claude on Perlmutter
# =======================================================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CASE_A_PATTERN=""
RUN_DIR_A=""
CASE_B_PATTERN=""
RUN_DIR_B=""
POLL_INTERVAL=60
MODE="auto"
KEY_VARS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --case-a-pattern) CASE_A_PATTERN="$2"; shift 2 ;;
        --run-dir-a) RUN_DIR_A="$2"; shift 2 ;;
        --case-b-pattern) CASE_B_PATTERN="$2"; shift 2 ;;
        --run-dir-b) RUN_DIR_B="$2"; shift 2 ;;
        --poll-interval) POLL_INTERVAL="$2"; shift 2 ;;
        --mode) MODE="$2"; shift 2 ;;
        --key-vars) KEY_VARS="$2"; shift 2 ;;
        -h|--help) head -30 "$0" | grep "^#" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

for req in CASE_A_PATTERN RUN_DIR_A CASE_B_PATTERN RUN_DIR_B; do
    if [ -z "${!req}" ]; then
        echo "ERROR: --$(echo "$req" | tr 'A-Z_' 'a-z-') is required" >&2
        exit 1
    fi
done

echo "watching V0 jobs; A pattern='$CASE_A_PATTERN' (-> $RUN_DIR_A)  B pattern='$CASE_B_PATTERN' (-> $RUN_DIR_B)"
while true; do
    q=$(squeue -u "$USER" -h -o "%j %T %r" 2>/dev/null)
    if echo "$q" | grep -E "$CASE_A_PATTERN|$CASE_B_PATTERN" | grep -q "DependencyNeverSatisfied"; then
        echo "=== V0 CHAIN CRASH: a phase died (DependencyNeverSatisfied). Investigate. ==="
        exit 2
    fi
    if ! echo "$q" | grep -qE "$CASE_A_PATTERN|$CASE_B_PATTERN"; then
        # Both gone from queue — confirm SOME output exists before declaring done. A run
        # too short for history output (a few-day segment) still writes lnd.log; only
        # a genuinely empty run dir means "crashed before producing anything."
        if [ -n "$(ls -A "$RUN_DIR_A" 2>/dev/null)" ] && [ -n "$(ls -A "$RUN_DIR_B" 2>/dev/null)" ]; then
            echo "=== BOTH V0 jobs done — comparing ==="
            break
        else
            echo "=== V0 jobs gone from queue but a run dir is empty — likely a crash before any output. Investigate. ==="
            exit 3
        fi
    fi
    sleep "$POLL_INTERVAL"
done

CMP_ARGS=("$RUN_DIR_A" "$RUN_DIR_B" "--mode" "$MODE")
[ -n "$KEY_VARS" ] && CMP_ARGS+=("--key-vars" "$KEY_VARS")

echo "===================== V0 COMPARE ====================="
PY="${A2MC_PYTHON:-python3}"
"$PY" "$SCRIPT_DIR/compare_v0.py" "${CMP_ARGS[@]}"
