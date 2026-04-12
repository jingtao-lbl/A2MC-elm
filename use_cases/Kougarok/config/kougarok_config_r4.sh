#!/bin/bash
# =============================================================================
# Kougarok Round 4 — Subset Replay with Prescribed P Uptake
# =============================================================================
#
# Replays the top 200 R3 cases with fates_cnp_prescribed_puptake=1.0 to test
# whether removing P limitation rescues PFT10. This is a controlled experiment
# isolating ONE variable from R3.
#
# Usage:
#   source a2mc_config.sh
#   source use_cases/Kougarok/config/kougarok_config_r4.sh
#   python phases/phase0_design/create_subset_replay.py
#   ./tools/submit_ensemble.sh --start 1 --end 200 --submit --reuse-build 1
#
# Then once HPC simulations complete:
#   python tools/diagnose_ensemble_status.py
#   python orchestrator.py --run --start-iteration 4 --start-phase 1 --no-review
#
# See: memory/dev_logs/20260410a_Subset_Replay_Sampling_Scheme.md
#      use_cases/Kougarok/config/calibration_rounds.yaml (Round 4 entry)
# =============================================================================

# Inherit ALL base R3 settings first
source "$(dirname "${BASH_SOURCE[0]}")/kougarok_config.sh"

echo ""
echo "=================================================================="
echo "Round 4 overrides: subset_replay with prescribed P uptake"
echo "=================================================================="

# -----------------------------------------------------------------------------
# Sampling scheme
# -----------------------------------------------------------------------------
export A2MC_SAMPLING_SCHEME="subset_replay"
export A2MC_TOTAL_ENSEMBLE=200
# Note: A2MC_N_TRAJECTORIES not relevant for subset_replay (no Morris design)

# -----------------------------------------------------------------------------
# Round 4 ensemble paths (NEW directories — separate from R3)
# -----------------------------------------------------------------------------
export A2MC_ENSEMBLE_NAME="Kougarok_PlantTraitsCNPEnsemble162_PrescribedP"
export A2MC_ENSEMBLE_OUTPUT="${A2MC_OUTPUT_ROOT}/${A2MC_ENSEMBLE_NAME}"
export A2MC_EXTRACTED_DATA="${A2MC_OUTPUT_ROOT}/${A2MC_ENSEMBLE_NAME}_Extract"

# Round 4 case scripts directory (separate from R3)
export A2MC_CASE_SCRIPTS="${A2MC_SCRIPTS_DIR}/Kougarok_FATES/ReCalibration_PtCNP162_AllPhase_PrescribedP"
export A2MC_LOG_DIR="${A2MC_CASE_SCRIPTS}"

# -----------------------------------------------------------------------------
# Round 4 case naming — MUST differ from R3 because all CIME case folders are
# built under one shared scripts directory (e.g., E3SM_FATES/cime/scripts/) and
# would collide if R3 and R4 used the same case name. We append "PrescP" AFTER
# the case number so the original "PtCNPEn{N}" substring is preserved — any
# regex or string search for "PtCNPEn86" still finds R4 case 86. Case NUMBERS
# are also preserved (R4 case 86 = R3 case 86 with override applied).
#
#   R3 case folder:  cime/scripts/Kougarok_ELM-FATES_PtCNPEn86_TRANS/
#   R4 case folder:  cime/scripts/Kougarok_ELM-FATES_PtCNPEn86PrescP_TRANS/
#
# Note: A2MC_PARAM_PATTERN (the NetCDF filename) stays the same as R3 because
# parameter files live in a separate per-round directory (A2MC_PARAM_DIR), so
# they don't collide.
export A2MC_CASE_NAME_PATTERN="${A2MC_ENSEMBLE_PREFIX}_PtCNPEn{N}PrescP_{PHASE}"

# -----------------------------------------------------------------------------
# Round 4 parameter file directory (NEW dir) — same filename pattern as R3
# -----------------------------------------------------------------------------
export A2MC_PARAM_DIR="/global/homes/j/jingtao/E3SM_Aid/FATES-ParameterFiles/fates_params_PrescribedP_EnPlantTraitsCNPparam162_R4"
# A2MC_PARAM_PATTERN is inherited from kougarok_config.sh (same as R3)

# -----------------------------------------------------------------------------
# Subset replay source (R3 inputs)
# -----------------------------------------------------------------------------
# Where to read the top-N case ranking from
export A2MC_REPLAY_SOURCE_STATE="${A2MC_USE_CASE_DIR}/memory/workflow_state_s0409h20m58.json"

# Where to read source NC parameter files (R3's PARAM_DIR)
export A2MC_REPLAY_SOURCE_PARAM_DIR="/global/homes/j/jingtao/E3SM_Aid/FATES-ParameterFiles/fates_params_NonPrescribed_EnPlantTraitsCNPparam162_Morris"

# Source filename pattern (R3's PARAM_PATTERN)
export A2MC_REPLAY_SOURCE_PARAM_PATTERN="fates_params_api25.5.0_12pft_c230710__PtCNP162_En{N}.nc"

# How many top cases to replay
export A2MC_REPLAY_TOP_N=200

# Override(s) applied to all replayed cases (comma-separated param=value)
# fates_cnp_prescribed_puptake=1.0 → P uptake forced at demand rate (no P limit)
export A2MC_REPLAY_OVERRIDES="fates_cnp_prescribed_puptake=1.0"

# Optional: ranking metric field name (default 'composite_nrmse')
# export A2MC_REPLAY_RANKING_METRIC="composite_nrmse"

echo "  Sampling scheme: subset_replay"
echo "  Source round:    R3 (state: workflow_state_s0409h20m58.json)"
echo "  Top N:           ${A2MC_REPLAY_TOP_N}"
echo "  Overrides:       ${A2MC_REPLAY_OVERRIDES}"
echo "  Param dir:       ${A2MC_PARAM_DIR}"
echo "  Ensemble output: ${A2MC_ENSEMBLE_OUTPUT}"
echo "=================================================================="
echo ""
