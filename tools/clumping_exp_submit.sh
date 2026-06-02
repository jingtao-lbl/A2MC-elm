#!/bin/bash
# =======================================================================================
# Clumping_Index Experiment — Single-Call Submitter for 8 Variants
#
# Submits the 8 clumping_index variants (clump00 .. clump07) on base case #1304 per
# memory/dev_logs/20260519e_Phase4_Clumping_Index_Verification_Experiment_Plan.md.
#
# Convention (per memory/dev_logs/20260528b + feedback_phase5_case_naming_convention):
# - --case-num 1304 (preserves base case lineage)
# - --case-suffix clump0X (differentiates from R5 Morris case 1304)
# - Case names: Kougarok_ELM-FATES_PtCNPEn1304PrescP_clump0X_{PHASE}
# - Param files (already generated): fates_params_..._En1304_clump0X.nc
#
# Dedicated dirs (per 20260519e §"HPC submission details"):
#   Output: /global/cfs/cdirs/m2467/jingtao/Kougarok_Clumping_Exp_20260528/
#   Case scripts: /pscratch/sd/j/jingtao/CaseScripts/Kougarok_FATES/ClumpingExp_20260528/
#
# Author: Jing Tao with Claude on Perlmutter
# Created: 2026-05-28
# =======================================================================================

set -e
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
A2MC_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

source "$A2MC_ROOT/a2mc_config.sh" > /dev/null 2>&1
source "$A2MC_ROOT/use_cases/Kougarok/config/kougarok_config_r5.sh" > /dev/null 2>&1

# Override env vars for dedicated dirs (per 20260519e §"HPC submission details")
export A2MC_ENSEMBLE_OUTPUT="/global/cfs/cdirs/m2467/jingtao/Kougarok_Clumping_Exp_20260528"
export A2MC_CASE_SCRIPTS="/pscratch/sd/j/jingtao/CaseScripts/Kougarok_FATES/ClumpingExp_20260528"
export A2MC_EXTRACTED_DATA="/global/cfs/cdirs/m2467/jingtao/Kougarok_Clumping_Exp_20260528_Extract"

# Reuse R5 case 1's FATES bld (saves ~4h of compiles across 8 variants). Same FATES binary;
# param changes are runtime so no recompile is needed. Pattern format: {PHASE} → ADSP/RGSP/TRANS.
export A2MC_REUSE_BUILD_EXEROOT_TEMPLATE="/global/cfs/cdirs/m2467/jingtao/Kougarok_PlantTraitsCNPEnsemble162_PrescribedP/Kougarok_ELM-FATES_PtCNPEn1PrescP_{PHASE}/bld"

mkdir -p "$A2MC_ENSEMBLE_OUTPUT" "$A2MC_CASE_SCRIPTS" "$A2MC_EXTRACTED_DATA"

PARAM_DIR="/global/homes/j/jingtao/E3SM_Aid/FATES-ParameterFiles/fates_params_clumping_exp_20260528"

DRY_RUN=""
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN="--dry-run"; shift ;;
        -h|--help) sed -n '4,25p' "$0"; echo "Usage: $0 [--dry-run]"; exit 0 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

VARIANTS=(clump00 clump01 clump02 clump03 clump04 clump05 clump06 clump07)

echo "======================================================================"
echo "Clumping_Index Experiment — 8 variants on base case #1304"
echo "======================================================================"
echo "  Param dir:        $PARAM_DIR"
echo "  Ensemble output:  $A2MC_ENSEMBLE_OUTPUT"
echo "  Case scripts:     $A2MC_CASE_SCRIPTS"
echo "  Extracted data:   $A2MC_EXTRACTED_DATA"
echo "  Variants:         ${VARIANTS[*]}"
echo "  Dry-run:          ${DRY_RUN:-no}"
echo ""

# Use create_case.sh per variant. clump00 (first) does fresh FATES build (~30 min);
# subsequent variants reuse clump00's build via --reuse-build (case-num + suffix).
CREATE_CASE="$A2MC_ROOT/tools/create_case.sh"

for i in "${!VARIANTS[@]}"; do
    variant="${VARIANTS[$i]}"
    PARAM_FILE="$PARAM_DIR/fates_params_api25.5.0_12pft_c230710__PtCNP162_En1304_${variant}.nc"
    if [ ! -f "$PARAM_FILE" ]; then
        echo "ERROR: param file missing: $PARAM_FILE"
        exit 1
    fi

    echo "----------------------------------------------------------------------"
    echo "[$((i+1))/8] Submitting variant: $variant"
    echo "  param file: $(basename "$PARAM_FILE")"

    # No --reuse-build N flag: we use A2MC_REUSE_BUILD_EXEROOT_TEMPLATE (set above)
    # which short-circuits all 8 builds to R5 case 1's bld. Same FATES binary; param
    # changes are runtime so no recompile.
    CMD=("$CREATE_CASE"
         --case-num 1304
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
echo "  squeue -u \$USER -h --format='%i %j %T' | grep clump"
echo "======================================================================"
