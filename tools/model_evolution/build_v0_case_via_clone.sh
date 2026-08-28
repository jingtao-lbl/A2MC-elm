#!/bin/bash
# =======================================================================================
# A2MC Model Evolution — build a V0 case via create_clone from an existing reference case
#
# Generalizes the guarded-branch-switch + create_clone recipe used for the
# PhosphorusBiochemMin_balance perf-fix V0 check (memory/model_logs/20260818a_*.md). Use
# this when the V0 case must MATCH AN EXISTING REFERENCE CASE's configuration exactly
# (or be built against a different commit); for a fresh chain configured from the site
# config instead, use build_v0_case_via_create_case.sh.
#
# Run length/start are set with --stop-n/--stop-option/--run-startdate. A SHORT segment
# resumes from a reference restart via --run-startdate + finidat -- the one resume
# mechanism A2MC uses. CONTINUE_RUN is deliberately NOT supported here: V0-at-equality is
# a DIFFERENCE test between two builds from identical state, so finidat's initialisation
# applies identically to both arms; and a change touching restart layout needs a fresh
# cold-start chain anyway. Keeping one mechanism makes CONTINUE_RUN an unambiguous
# wrong-answer marker repo-wide (feedback_restart_via_finidat_not_continue_run).
#
# `create_clone` has NO srcroot-override flag and CANNOT retarget an existing case's
# SRCROOT after creation (env_case.xml is locked) — the only way to build a clone of a
# case against a DIFFERENT commit is to guarded-switch the checkout ITSELF before cloning,
# so the clone inherits SRCROOT pointing at the (temporarily) switched tree. This also
# means the clone inherits the reference case's ENTIRE configuration in one step (PE
# layout, DATM streams, ELM_USRDAT_NAME, ELM_BLDNML_OPTS, ...) — the exact class of gap a
# hand-reconstructed `create_newcase` case silently drops. See
# feedback_replicate_full_case_config_on_create_newcase_fallback in the memory bucket.
#
# Usage:
#   tools/model_evolution/build_v0_case_via_clone.sh \
#       --e3sm-root <path> --target-ref <ref> --restore-ref <ref> \
#       --reference-case <case_name> --new-case-suffix <suffix> \
#       [--switch-repo-path <path>] [--verify-file <path> --verify-pattern <regex>] \
#       [--stop-n N] [--stop-option OPT] [--run-startdate DATE] \
#       [--queue Q] [--walltime HH:MM:SS] [--submit]
#
# Required:
#   --e3sm-root PATH       E3SM checkout root (where cime/scripts lives) — the build
#                          always runs from here regardless of which tree is switched.
#   --target-ref REF       Commit/branch to build FROM.
#   --restore-ref REF      Branch to restore to afterward.
#   --reference-case NAME  Case name (under <e3sm-root>/cime/scripts) to create_clone from.
#   --new-case-suffix S    Appended to the reference case's name for the new case.
#
# Optional:
#   --switch-repo-path PATH   Which checkout to guard-switch (default: --e3sm-root itself,
#                          i.e. an ELM-side change). Override to a submodule path (e.g. the
#                          FATES submodule) for a FATES-side change.
#   --verify-file / --verify-pattern   Sanity-check target_ref landed as expected.
#   --stop-n N / --stop-option OPT / --run-startdate DATE
#                          Override the cloned case's run-length settings for a short V0
#                          segment. Any omitted var is left at whatever the reference case
#                          already has (the clone inherits it) — do not pass one unless you
#                          actually want to change it.
#   --queue Q / --walltime HH:MM:SS   case.run job settings (defaults: leave inherited).
#   --submit               Actually submit after building (default: build only).
#
# Author: Jing Tao with Claude on Perlmutter
# =======================================================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib_guarded_switch.sh"

E3SM_ROOT=""
SWITCH_REPO_PATH=""
TARGET_REF=""
RESTORE_REF=""
VERIFY_FILE=""
VERIFY_PATTERN=""
REFERENCE_CASE=""
NEW_CASE_SUFFIX=""
STOP_N=""
STOP_OPTION=""
RUN_STARTDATE=""
QUEUE=""
WALLTIME=""
DO_SUBMIT=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --e3sm-root) E3SM_ROOT="$2"; shift 2 ;;
        --switch-repo-path) SWITCH_REPO_PATH="$2"; shift 2 ;;
        --target-ref) TARGET_REF="$2"; shift 2 ;;
        --restore-ref) RESTORE_REF="$2"; shift 2 ;;
        --verify-file) VERIFY_FILE="$2"; shift 2 ;;
        --verify-pattern) VERIFY_PATTERN="$2"; shift 2 ;;
        --reference-case) REFERENCE_CASE="$2"; shift 2 ;;
        --new-case-suffix) NEW_CASE_SUFFIX="$2"; shift 2 ;;
        --stop-n) STOP_N="$2"; shift 2 ;;
        --stop-option) STOP_OPTION="$2"; shift 2 ;;
        --run-startdate) RUN_STARTDATE="$2"; shift 2 ;;
        --queue) QUEUE="$2"; shift 2 ;;
        --walltime) WALLTIME="$2"; shift 2 ;;
        --submit) DO_SUBMIT=true; shift ;;
        -h|--help) head -50 "$0" | grep "^#" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

for req in E3SM_ROOT TARGET_REF RESTORE_REF REFERENCE_CASE NEW_CASE_SUFFIX; do
    if [ -z "${!req}" ]; then
        echo "ERROR: --$(echo "$req" | tr 'A-Z_' 'a-z-') is required" >&2
        exit 1
    fi
done
[ -z "$SWITCH_REPO_PATH" ] && SWITCH_REPO_PATH="$E3SM_ROOT"

NEW_CASE_NAME="${REFERENCE_CASE}_${NEW_CASE_SUFFIX}"
CIME_SCRIPTS="$E3SM_ROOT/cime/scripts"

_build_clone() {
    cd "$CIME_SCRIPTS"
    echo "=== create_clone: $NEW_CASE_NAME <- $REFERENCE_CASE ==="
    ./create_clone --case "$NEW_CASE_NAME" --clone "$REFERENCE_CASE"

    cd "$CIME_SCRIPTS/$NEW_CASE_NAME"
    [ -n "$STOP_N" ]         && ./xmlchange STOP_N="$STOP_N"
    [ -n "$STOP_OPTION" ]    && ./xmlchange STOP_OPTION="$STOP_OPTION"
    [ -n "$RUN_STARTDATE" ]  && ./xmlchange RUN_STARTDATE="$RUN_STARTDATE"
    [ -n "$QUEUE" ]          && ./xmlchange JOB_QUEUE="$QUEUE" --subgroup case.run
    [ -n "$WALLTIME" ]       && ./xmlchange JOB_WALLCLOCK_TIME="$WALLTIME" --subgroup case.run

    echo "=== case.setup ==="
    ./case.setup
    echo "=== case.build ==="
    ./case.build

    if [ "$DO_SUBMIT" = true ]; then
        echo "=== case.submit ==="
        ./case.submit
    else
        echo "=== BUILD ONLY (pass --submit to also submit) ==="
    fi
}

echo "=== V0 case build via create_clone ==="
echo "e3sm_root=$E3SM_ROOT switch_repo_path=$SWITCH_REPO_PATH target_ref=$TARGET_REF restore_ref=$RESTORE_REF"
echo "reference_case=$REFERENCE_CASE new_case=$NEW_CASE_NAME"

guarded_switch_and_run "$SWITCH_REPO_PATH" "$TARGET_REF" "$RESTORE_REF" "$VERIFY_FILE" "$VERIFY_PATTERN" -- \
    _build_clone

echo "=== V0 CASE BUILD DONE: $NEW_CASE_NAME ==="
