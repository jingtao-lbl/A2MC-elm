#!/bin/bash
# =======================================================================================
# A2MC Model Evolution — build a V0-baseline case via tools/create_case.sh
#
# Generalizes the phen_split #17 V0-check scripts (build_baseline_api43.sh +
# run_baseline_chain_api43.sh, use_cases/ELM-FATES_Kougarok/memory/phase_results/20260712_phen_split_v0_api43/)
# into a site-agnostic, parameterized tool: guarded-switch a checkout to a PARENT ref,
# build a fresh case there via the canonical tools/create_case.sh (so ALL of compset/res/
# domain/DATM_MODE/ELM_USRDAT_NAME/ELM_BLDNML_OPTS come from the site config, not a
# hand-reconstruction), then restore the checkout.
#
# Use this for a FRESH cold-start chain (ADSP[/RGSP/TRANS]) baseline — the case-num /
# case-suffix pattern from tools/create_case.sh. For a V0 check that continues an EXISTING
# reference case's configuration exactly (or a different commit), use
# build_v0_case_via_clone.sh instead — it inherits a reference case's full config via
# create_clone rather than building a fresh case from scratch.
#
# Usage:
#   tools/model_evolution/build_v0_case_via_create_case.sh \
#       --repo-path <path> --target-ref <ref> --restore-ref <ref> \
#       --site-config <path> --case-num N --param-file <path> \
#       [--verify-file <path> --verify-pattern <regex>] \
#       [--case-suffix SUFFIX] [--phases "ADSP RGSP TRANS"] [--submit|--build-only]
#
# Required:
#   --repo-path PATH      Git checkout to switch (E3SM root or a submodule, e.g. the FATES
#                          submodule path) — must be clean and committed.
#   --target-ref REF      Commit/branch to build FROM (the baseline/parent).
#   --restore-ref REF     Branch to restore to afterward (normally the branch checked out
#                          before running this script — capture it yourself and pass it in).
#   --site-config PATH    Site config to source (e.g. use_cases/ELM-FATES_Kougarok/config/kougarok_config.sh).
#   --case-num N           Passed through to tools/create_case.sh.
#   --param-file PATH      Passed through to tools/create_case.sh.
#
# Optional:
#   --verify-file PATH / --verify-pattern REGEX   Sanity-check the target_ref actually
#                          landed (e.g. confirm a since-refactored symbol is present/absent).
#   --case-suffix SUFFIX   Passed through to tools/create_case.sh (default: "v0base").
#   --phases "P1 P2 ..."   Passed through (default: "ADSP").
#   --submit / --build-only  Passed through (default: --build-only).
#
# Author: Jing Tao with Claude on Perlmutter
# =======================================================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
A2MC_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/lib_guarded_switch.sh"

REPO_PATH=""
TARGET_REF=""
RESTORE_REF=""
VERIFY_FILE=""
VERIFY_PATTERN=""
SITE_CONFIG=""
CASE_NUM=""
PARAM_FILE=""
CASE_SUFFIX="v0base"
PHASES="ADSP"
SUBMIT_FLAG="--build-only"

while [[ $# -gt 0 ]]; do
    case $1 in
        --repo-path) REPO_PATH="$2"; shift 2 ;;
        --target-ref) TARGET_REF="$2"; shift 2 ;;
        --restore-ref) RESTORE_REF="$2"; shift 2 ;;
        --verify-file) VERIFY_FILE="$2"; shift 2 ;;
        --verify-pattern) VERIFY_PATTERN="$2"; shift 2 ;;
        --site-config) SITE_CONFIG="$2"; shift 2 ;;
        --case-num) CASE_NUM="$2"; shift 2 ;;
        --param-file) PARAM_FILE="$2"; shift 2 ;;
        --case-suffix) CASE_SUFFIX="$2"; shift 2 ;;
        --phases) PHASES="$2"; shift 2 ;;
        --submit) SUBMIT_FLAG="--submit"; shift ;;
        --build-only) SUBMIT_FLAG="--build-only"; shift ;;
        -h|--help) head -40 "$0" | grep "^#" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

for req in REPO_PATH TARGET_REF RESTORE_REF SITE_CONFIG CASE_NUM PARAM_FILE; do
    if [ -z "${!req}" ]; then
        echo "ERROR: --$(echo "$req" | tr 'A-Z_' 'a-z-') is required" >&2
        exit 1
    fi
done

cd "$A2MC_ROOT"
source a2mc_config.sh
source "$SITE_CONFIG"

echo "=== V0 baseline build via tools/create_case.sh ==="
echo "repo_path=$REPO_PATH target_ref=$TARGET_REF restore_ref=$RESTORE_REF"
echo "case_num=$CASE_NUM case_suffix=$CASE_SUFFIX phases=$PHASES ($SUBMIT_FLAG)"

guarded_switch_and_run "$REPO_PATH" "$TARGET_REF" "$RESTORE_REF" "$VERIFY_FILE" "$VERIFY_PATTERN" -- \
    ./tools/create_case.sh --case-num "$CASE_NUM" --case-suffix "$CASE_SUFFIX" \
        --param-file "$PARAM_FILE" --phases "$PHASES" "$SUBMIT_FLAG"

echo "=== V0 BASELINE BUILD DONE ==="
