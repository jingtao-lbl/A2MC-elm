#!/bin/bash
# =======================================================================================
# PFT10 Establishment Experiment — Single-Call Submitter for 6 Variants
#
# Submits the 6 PFT10-allocation variants (estab00 .. estab05) on base case #488 per
# memory/dev_logs/20260531c_Offline_Experiment_Plan_PFT10_Establishment.md
# (grounded in memory/ana_logs/20260531b donor analysis).
#
# Convention (per feedback_phase5_case_naming_convention auto-memory):
# - --case-num 488 (preserves base case lineage)
# - --case-suffix estab0X (differentiates from R5 Morris case 488)
# - Case names: Kougarok_ELM-FATES_PtCNPEn488PrescP_estab0X_{PHASE}
#   (suffix sits between PrescP and _{PHASE} -> excluded from the Morris *PrescP_TRANS_* glob)
# - Param files (already generated + verified): fates_params_..._En488_estab0X.nc
#
# Dedicated dirs (per offline-testing-workflow Step 5):
#   Output:       ~/Kougarok_Estab_Exp_20260604/
#   Case scripts: ~/CaseScripts/Kougarok_FATES/EstabExp_20260604/
#   Extract:      ~/Kougarok_Estab_Exp_20260604_Extract/
#
# Author: Jing Tao with Claude on Perlmutter
# Created: 2026-06-04
# =======================================================================================

set -e
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
A2MC_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

source "$A2MC_ROOT/a2mc_config.sh" > /dev/null 2>&1
source "$A2MC_ROOT/use_cases/Kougarok/config/kougarok_config_r5.sh" > /dev/null 2>&1

# Dedicated dirs (keep this experiment OFF the R5 Morris paths)
export A2MC_ENSEMBLE_OUTPUT="~/Kougarok_Estab_Exp_20260604"
export A2MC_CASE_SCRIPTS="~/CaseScripts/Kougarok_FATES/EstabExp_20260604"
export A2MC_EXTRACTED_DATA="~/Kougarok_Estab_Exp_20260604_Extract"

# Reuse R5 case 1's FATES bld (param changes are runtime; no recompile). {PHASE} -> ADSP/RGSP/TRANS.
export A2MC_REUSE_BUILD_EXEROOT_TEMPLATE="~/Kougarok_PlantTraitsCNPEnsemble162_PrescribedP/Kougarok_ELM-FATES_PtCNPEn1PrescP_{PHASE}/bld"

mkdir -p "$A2MC_ENSEMBLE_OUTPUT" "$A2MC_CASE_SCRIPTS" "$A2MC_EXTRACTED_DATA"

PARAM_DIR="~/E3SM_Aid/FATES-ParameterFiles/fates_params_estab_exp_20260604"
BASE_CASE=488

DRY_RUN=""
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN="--dry-run"; shift ;;
        -h|--help) sed -n '4,25p' "$0"; echo "Usage: $0 [--dry-run]"; exit 0 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

VARIANTS=(estab00 estab01 estab02 estab03 estab04 estab05)

echo "======================================================================"
echo "PFT10 Establishment Experiment — 6 variants on base case #${BASE_CASE}"
echo "======================================================================"
echo "  Param dir:        $PARAM_DIR"
echo "  Ensemble output:  $A2MC_ENSEMBLE_OUTPUT"
echo "  Case scripts:     $A2MC_CASE_SCRIPTS"
echo "  Extracted data:   $A2MC_EXTRACTED_DATA"
echo "  Build reuse:      $A2MC_REUSE_BUILD_EXEROOT_TEMPLATE"
echo "  Variants:         ${VARIANTS[*]}"
echo "  Dry-run:          ${DRY_RUN:-no}"
echo ""

CREATE_CASE="$A2MC_ROOT/tools/create_case.sh"

for i in "${!VARIANTS[@]}"; do
    variant="${VARIANTS[$i]}"
    PARAM_FILE="$PARAM_DIR/fates_params_api25.5.0_12pft_c230710__PtCNP162_En${BASE_CASE}_${variant}.nc"
    if [ ! -f "$PARAM_FILE" ]; then
        echo "ERROR: param file missing: $PARAM_FILE"
        exit 1
    fi

    echo "----------------------------------------------------------------------"
    echo "[$((i+1))/${#VARIANTS[@]}] Submitting variant: $variant"
    echo "  param file: $(basename "$PARAM_FILE")"

    CMD=("$CREATE_CASE"
         --case-num "$BASE_CASE"
         --case-suffix "$variant"
         --param-file "$PARAM_FILE"
         --phases "ADSP RGSP TRANS"
         --output-root "$A2MC_ENSEMBLE_OUTPUT"
         --submit)

    if [ -n "$DRY_RUN" ]; then
        echo "[dry-run] would run: ${CMD[*]}"
    else
        echo "Running: ${CMD[*]}"
        "${CMD[@]}"
    fi
done

echo ""
echo "======================================================================"
echo "Submission complete. Monitor with:"
echo "  squeue -u \$USER -h --format='%i %j %T' | grep estab"
echo "======================================================================"
