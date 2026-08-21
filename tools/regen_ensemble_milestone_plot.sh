#!/bin/bash
# regen_ensemble_milestone_plot.sh — A2MC generic milestone ensemble-plot regen.
#
# =============================================================================
# WHAT THIS IS
# =============================================================================
# Config-driven generalization of use_cases/ELM-FATES_Kougarok/analysis/regen_milestone_plot.sh.
# Counts fresh extracted TRANS NCs (mtime > launch), rounds down to the nearest
# case-count milestone, and (re)generates whichever ensemble-plot variants don't
# yet exist. Idempotent per variant: skips if the target file exists or a plot
# job for the same --output-path is already running.
#
# Reusable by BOTH the ONLINE Phase 0 monitor and an OFFLINE Phase-0-mimic run:
# called from tools/ensemble_auto_monitor.sh's poll loop, or stand-alone after a
# TRANS_DONE milestone.
#
# Produces two complementary plots per milestone (axis-mode encoded in filename,
# per feedback_plot_filename_convention):
#   1. TRANS-only zoom        → <PREFIX>_TRANS_<M>cases_ensemble.png
#   2. Combined-axis (ADSP+RGSP+TRANS) → <PREFIX>_combined_<M>cases_ensemble.png
#
# =============================================================================
# USAGE
# =============================================================================
#   source a2mc_config.sh
#   source use_cases/<site>/config/<site>_config_rN.sh
#   bash tools/regen_ensemble_milestone_plot.sh [milestone_step]
#
# Config (flags win over env vars; the positional arg sets the milestone step):
#   $1 / --milestone-step N  milestone granularity   [A2MC_MILESTONE_STEP, default 250]
#   --launch "YYYY-MM-DD HH:MM:SS"  fresh-file mtime cutoff   [A2MC_LAUNCH_TIME]
#   --prefix STR             output filename prefix (round id) [A2MC_PLOT_PREFIX, default $A2MC_CALIBRATION_ROUND-derived "R<N>" or "ENS"]
#   --output-dir DIR         where the PNGs land               [A2MC_PLOT_OUTPUT_DIR, default $A2MC_USE_CASE_DIR/analysis]
#   --plot-script-dir DIR    dir holding the two plot_*.py     [A2MC_PLOT_SCRIPT_DIR, default $A2MC_USE_CASE_DIR/analysis]
#
# The fresh-NC glob is derived from $A2MC_CASE_NAME_PATTERN (no hardcoded
# PrescP), the same substitution plot_all_extracted.py's _build_case_regex uses:
#   pattern{N=*,PHASE=TRANS}_all_variables_monthly_*.nc
#
# =============================================================================
# EVENTS EMITTED ON STDOUT (kept identical to the R5 vocabulary)
# =============================================================================
#   REGEN_SKIP: fresh=<n> < step=<s>
#   REGEN_SKIP[<variant>]: <reason>
#   REGEN_DEFER[<variant>]: <reason>
#   REGEN_LAUNCHED[<variant>]: pid=<P> milestone=<N> fresh=<N> out=<path> log=<path>
#
# NERSC rule: logs go under $A2MC_ROOT/tmp only — never /tmp, /scratch, etc.
# =============================================================================

set -u

# -----------------------------------------------------------------------------
# CLI parsing (flags + one positional milestone-step).
# -----------------------------------------------------------------------------
POS_STEP=""
while [ $# -gt 0 ]; do
    case "$1" in
        --milestone-step) A2MC_MILESTONE_STEP="$2";   shift 2 ;;
        --launch)         A2MC_LAUNCH_TIME="$2";       shift 2 ;;
        --prefix)         A2MC_PLOT_PREFIX="$2";       shift 2 ;;
        --output-dir)     A2MC_PLOT_OUTPUT_DIR="$2";   shift 2 ;;
        --plot-script-dir) A2MC_PLOT_SCRIPT_DIR="$2";  shift 2 ;;
        -h|--help)        sed -n '2,55p' "$0"; exit 0 ;;
        -*)               echo "ERROR: unknown flag: $1" >&2; exit 2 ;;
        *)                POS_STEP="$1";               shift   ;;
    esac
done

# -----------------------------------------------------------------------------
# Config validation.
# -----------------------------------------------------------------------------
required=(A2MC_ROOT A2MC_EXTRACTED_DATA A2MC_CASE_NAME_PATTERN A2MC_LAUNCH_TIME)
missing=0
for v in "${required[@]}"; do
    if [ -z "${!v:-}" ]; then
        echo "ERROR: required value \$$v is not set. Source a2mc_config.sh + the round config, or pass the matching flag." >&2
        missing=1
    fi
done
[ "$missing" -eq 1 ] && exit 2

# -----------------------------------------------------------------------------
# Resolve config.
# -----------------------------------------------------------------------------
LAUNCH="$A2MC_LAUNCH_TIME"
MILESTONE_STEP="${POS_STEP:-${A2MC_MILESTONE_STEP:-250}}"
USE_CASE_DIR="${A2MC_USE_CASE_DIR:-$A2MC_ROOT/use_cases/ELM-FATES_Kougarok}"
OUTPUT_DIR="${A2MC_PLOT_OUTPUT_DIR:-${USE_CASE_DIR}/analysis}"
SCRIPT_DIR="${A2MC_PLOT_SCRIPT_DIR:-${USE_CASE_DIR}/analysis}"
LOG_DIR="${A2MC_AUTOMON_LOG_DIR:-${A2MC_ROOT}/tmp}"

# Output-filename prefix (round id). Prefer an explicit --prefix; else derive
# "R<N>" from $A2MC_CALIBRATION_ROUND; else fall back to "ENS".
if [ -n "${A2MC_PLOT_PREFIX:-}" ]; then
    PREFIX="$A2MC_PLOT_PREFIX"
elif [ -n "${A2MC_CALIBRATION_ROUND:-}" ]; then
    PREFIX="R${A2MC_CALIBRATION_ROUND}"
else
    PREFIX="ENS"
fi

# Derive the fresh-NC glob from the case-name pattern (no hardcoded PrescP).
glob_stem="${A2MC_CASE_NAME_PATTERN//\{N\}/*}"
glob_stem="${glob_stem//\{PHASE\}/TRANS}"
FRESH_GLOB="${A2MC_EXTRACTED_NC_GLOB:-${glob_stem}_all_variables_monthly_*.nc}"

n_fresh=$(find "$A2MC_EXTRACTED_DATA" -maxdepth 1 \
            -name "$FRESH_GLOB" \
            -newermt "$LAUNCH" 2>/dev/null | wc -l)

if [ "$n_fresh" -lt "$MILESTONE_STEP" ]; then
    echo "REGEN_SKIP: fresh=$n_fresh < step=$MILESTONE_STEP"
    exit 0
fi

milestone=$(( (n_fresh / MILESTONE_STEP) * MILESTONE_STEP ))

# Generate one plot variant; each has its own existence + active-job checks
# keyed off its target output path so the two operate independently.
try_regen() {
    local variant="$1"      # short tag for log messages (e.g. "TRANS", "combined")
    local script="$2"       # script filename under $SCRIPT_DIR
    local extra_args="$3"   # extra CLI flags (e.g. "--combined" or "")
    local out_basename="$4" # full basename including milestone + .png

    local out="${OUTPUT_DIR}/${out_basename}"

    if [ -f "$out" ]; then
        echo "REGEN_SKIP[$variant]: $out already exists (fresh=$n_fresh)"
        return 0
    fi

    # Per-output-path active check: match the exact --output-path argument in the
    # process command line so the two variants don't break each other's idempotency.
    local active
    active=$(ps -ef | grep -F -- "--output-path $out" | grep -v grep | wc -l)
    if [ "$active" -gt 0 ]; then
        echo "REGEN_DEFER[$variant]: plot for $out is already in flight"
        return 0
    fi

    local ts log
    ts=$(date +%Y%m%d_%H%M%S)
    log="${LOG_DIR}/ensemble_plot_milestone${milestone}_${variant}_${ts}.log"

    cd "$A2MC_ROOT" || return 1
    # $extra_args intentionally unquoted so "--combined" expands as a flag.
    nohup python3 -u "${SCRIPT_DIR}/$script" \
        --output-path "$out" \
        --mtime-after "$LAUNCH" \
        $extra_args \
        > "$log" 2>&1 &

    echo "REGEN_LAUNCHED[$variant]: pid=$! milestone=$milestone fresh=$n_fresh out=$out log=$log"
}

# Variant 1: TRANS-only zoom.
try_regen "TRANS" "plot_all_extracted_Trans.py" "" \
          "${PREFIX}_TRANS_${milestone}cases_ensemble.png"

# Variant 2: Combined-axis ADSP+RGSP+TRANS.
try_regen "combined" "plot_all_extracted.py" "--combined" \
          "${PREFIX}_combined_${milestone}cases_ensemble.png"
