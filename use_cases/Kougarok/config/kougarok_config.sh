#!/bin/bash
# =============================================================================
# Kougarok Site-Specific Configuration
# =============================================================================
# This file contains ALL site-specific settings for Kougarok, Alaska.
# Source this AFTER sourcing the main a2mc_config.sh:
#
#   source a2mc_config.sh
#   source use_cases/Kougarok/config/kougarok_config.sh
#   print_config  # Verify settings
# =============================================================================

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export A2MC_USE_CASE_DIR="$(dirname "$SCRIPT_DIR")"

# Self-identification: expose this config's absolute path so A2MC tools can
# detect which round config is active without ambiguous filesystem globbing.
# When a round-specific wrapper (e.g., kougarok_config_r4.sh) sources this
# file, its own export at the bottom overwrites this value — last wins.
export A2MC_SITE_CONFIG="${SCRIPT_DIR}/$(basename "${BASH_SOURCE[0]}")"

# -----------------------------------------------------------------------------
# Model Source Path (Phase 4 RAG version association — required)
# -----------------------------------------------------------------------------
# Absolute path to the E3SM/ELM-FATES checkout used to RUN this case. The
# RAG infrastructure detects ELM + FATES commits from this path and selects
# the matching milestone profile (api-31-0 for the Kougarok manuscript;
# api-43-1 for E3SM-master-pinned work).
#
# On Perlmutter:
#   /global/cfs/cdirs/m2467/jingtao/E3SM_FATES   (api-31, Kougarok manuscript)
# Locally (override per developer):
#   $HOME/Desktop/Work/SourceCode/ELM_FATES/E3SM_FATES   (api-31)
#
# If you maintain multiple checkouts, switch between them by editing this line
# OR by exporting A2MC_MODEL_PATH in your shell BEFORE sourcing this file.
if [ -z "${A2MC_MODEL_PATH:-}" ]; then
    if [ -d "$HOME/Desktop/Work/SourceCode/ELM_FATES/E3SM_FATES" ]; then
        export A2MC_MODEL_PATH="$HOME/Desktop/Work/SourceCode/ELM_FATES/E3SM_FATES"
    else
        export A2MC_MODEL_PATH="${A2MC_E3SM_ROOT}"
    fi
fi

# -----------------------------------------------------------------------------
# Site Information
# -----------------------------------------------------------------------------
export A2MC_SITE_NAME="Kougarok"
export A2MC_SITE_DESCRIPTION="Arctic tundra, Seward Peninsula, Alaska (NGEE-Arctic)"
export A2MC_SITE_LAT=65.1
export A2MC_SITE_LON=-164.8

# -----------------------------------------------------------------------------
# PFT Configuration
# -----------------------------------------------------------------------------
# Arctic PFTs used in this study
export A2MC_PFTS="7,9,10"
export A2MC_PFT_NAMES="Evergreen_Shrub,Deciduous_Shrub,Arctic_Graminoid"

# PFT indices (0-based for array access)
export A2MC_PFT7_INDEX=6   # Evergreen shrub
export A2MC_PFT9_INDEX=8   # Deciduous shrub
export A2MC_PFT10_INDEX=9  # Arctic graminoid

# -----------------------------------------------------------------------------
# Domain and Surface Data
# -----------------------------------------------------------------------------
export A2MC_DOMAIN_DIR="/dvs_ro/u1/j/jingtao/CaseScripts/Kougarok_FATES"
export A2MC_DOMAIN_FILE="domain_Kougarok_from0.125x0.125_simyr1850_c240309.nc"
export A2MC_SURFACE_FILE="surfdata_Kougarok_from0.125x0.125_simyr1850_c240309_ModPval.nc"

# CNP soil parameters
export A2MC_SOILORDER_DIR="/global/homes/j/jingtao/E3SM_Aid/clm_params"
export A2MC_SOILORDER_FILE="CNP_parameters_c180312.nc"

# Forcing data redirects
export A2MC_FORCING_DIR="${HOME}/E3SM_Aid/RedirectForcing/atm_forcing.datm7.GSWP3-w5e5.c211106"

# -----------------------------------------------------------------------------
# Parameter Configuration (162-parameter ensemble)
# -----------------------------------------------------------------------------
export A2MC_N_PARAMS=162
export A2MC_N_TRAJECTORIES=30

# Calculate and export total ensemble size
export A2MC_TOTAL_ENSEMBLE=$(calculate_ensemble_size)

# Parameter list and SALib problem definition (in use_cases folder)
export A2MC_PARAM_LIST_FILE="${A2MC_USE_CASE_DIR}/parameters/FATES_Parameter_List_Full_162_Finalized.txt"
export A2MC_SALIB_PROBLEM_FILE="${A2MC_USE_CASE_DIR}/parameters/salib_problem_162params.txt"

# -----------------------------------------------------------------------------
# Validation Targets
# -----------------------------------------------------------------------------
export A2MC_VALIDATION_FILE="${A2MC_USE_CASE_DIR}/validation/validation_targets_leafroot.txt"

# Validation period (growing season)
export A2MC_VALIDATION_START_YEAR=2000
export A2MC_VALIDATION_END_YEAR=2019
export A2MC_VALIDATION_MONTHS="6,7,8"  # June-August peak season

# Calibration settings
export A2MC_ERROR_METHOD="relative_error"
export A2MC_AGGREGATION_METHOD="rmsre"
export A2MC_TOLERANCE=0.20  # 20% tolerance
export A2MC_TOP_N=50

# -----------------------------------------------------------------------------
# ELM Build/Namelist Options
# -----------------------------------------------------------------------------
# Override RGSP suplphos for Round 3: extend supplementary P through regular spinup
# to prevent chronic P-limitation (see calibration_rounds.yaml Round 3 rationale)
export A2MC_RGSP_SUPLPHOS="ALL"

export A2MC_ELM_OPTIONS="-nutrient cnp -nutrient_comp_pathway eca -soil_decomp century"

# -----------------------------------------------------------------------------
# Ensemble Paths
# -----------------------------------------------------------------------------
#export A2MC_ENSEMBLE_NAME="Kougarok_PlantTraitsCNPEnsemble162_Morris"
export A2MC_ENSEMBLE_NAME="Kougarok_PlantTraitsCNPEnsemble162_Morris_RGSPsuplP" #3rd round of calibration
export A2MC_ENSEMBLE_PREFIX="Kougarok_ELM-FATES"
export A2MC_CASE_NAME_PATTERN="${A2MC_ENSEMBLE_PREFIX}_PtCNPEn{N}_{PHASE}"
export A2MC_ENSEMBLE_OUTPUT="${A2MC_OUTPUT_ROOT}/${A2MC_ENSEMBLE_NAME}"

# -----------------------------------------------------------------------------
# CASE DIR (v2.93+ — for case-dir-enrichment of mode-aware retrieval)
# -----------------------------------------------------------------------------
# A2MC's ConfigMode.from_env() reads env vars first (user intent), then enriches
# from a CIME case dir if available. The case dir provides Tier 2 use_fates_*
# flags from user_nl_elm/lnd_in plus ELM defaults that env vars don't specify.
#
# Set A2MC_CASE_DIR to ANY representative ensemble member's case directory.
# All ensemble members share the same compset / ELM_BLDNML_OPTS / user_nl_elm
# (only the FATES parameter file differs), so any one works as the reference.
#
# Default: pick En86 TRANS phase (matches the committed example case).
#export A2MC_CASE_DIR="${A2MC_E3SM_ROOT}/cime/scripts/${A2MC_ENSEMBLE_PREFIX}_PtCNPEn86_TRANS"
#
# OR, if A2MC_E3SM_ROOT + A2MC_CASE_NAME are set, A2MC auto-detects:
#export A2MC_CASE_NAME="${A2MC_ENSEMBLE_PREFIX}_PtCNPEn86_TRANS"
#
# If neither is set, ConfigMode uses env-vars-only path (still works; just no
# case-dir enrichment). See docs/a2mc_reference/mode_aware_workflow.md.

# -----------------------------------------------------------------------------
# MODE-AWARE RETRIEVAL ENV VARS (v2.94+ — primary source = USER INTENT)
# -----------------------------------------------------------------------------
# ConfigMode resolves: env vars (here) > case dir (above, if set) > defaults.
# These reflect Kougarok's actual run config (FATES + PARTEH=2 + CNP + ECA +
# CENTURY soil decomp), overriding ELM source defaults (which would be SP).
export A2MC_ELM_OPTIONS="-bgc fates -nutrient cnp -nutrient_comp_pathway eca -soil_decomp century"
export A2MC_FATES_PARTEH_MODE=2
# All other Tier 2 / Tier 3 flags default off (no fire, no hydraulics, etc.)
# -----------------------------------------------------------------------------
# Extracted monthly data (NetCDF files from extract_monthly_variables_FATES.py)
export A2MC_EXTRACTED_DATA="${A2MC_OUTPUT_ROOT}/${A2MC_ENSEMBLE_NAME}_Extract"

# Case scripts directory
#export A2MC_CASE_SCRIPTS="${A2MC_SCRIPTS_DIR}/Kougarok_FATES/ReCalibration_PtCNP162_AllPhase"
export A2MC_CASE_SCRIPTS="${A2MC_SCRIPTS_DIR}/Kougarok_FATES/ReCalibration_PtCNP162_AllPhase_RGSPsuplP" #3rd round of calibration
export A2MC_LOG_DIR="${A2MC_CASE_SCRIPTS}"

# -----------------------------------------------------------------------------
# HPC Paths (NERSC Perlmutter)
# -----------------------------------------------------------------------------
# Base FATES parameter file (template)
export A2MC_BASE_PARAM_FILE="/global/homes/j/jingtao/E3SM_Aid/FATES-ParameterFiles/fates_params_api25.5.0_12pft_c230710.nc"

# Directory containing FATES parameter files for ensemble
export A2MC_PARAM_DIR="/global/homes/j/jingtao/E3SM_Aid/FATES-ParameterFiles/fates_params_NonPrescribed_EnPlantTraitsCNPparam162_Morris"

# Parameter file naming pattern ({N} = case number 1-4890)
export A2MC_PARAM_PATTERN="fates_params_api25.5.0_12pft_c230710__PtCNP162_En{N}.nc"

# Morris ensemble matrix (4890 x 162) - site-specific data
# Note: A2MC_ROOT is two levels up from use_cases/Kougarok/config/
export A2MC_ROOT="$(dirname "$(dirname "$A2MC_USE_CASE_DIR")")"
export A2MC_ENSEMBLE_MATRIX_FILE="${A2MC_USE_CASE_DIR}/parameters/FATES_CNPnPlantTraits_162param_Morris_4890sets.txt"

# -----------------------------------------------------------------------------
# Phenology Calibration (from Dec 2025 analysis)
# -----------------------------------------------------------------------------
# Calibrated phenology parameters (shared across cold-deciduous PFTs)
#export A2MC_PHEN_GDDTHRESH_C=-0.00991
#export A2MC_PHEN_CHILLTEMP=2.262

# -----------------------------------------------------------------------------
# History Output Variables
# -----------------------------------------------------------------------------
export A2MC_HIST_SZPF_VARS="'FATES_VEGC_ABOVEGROUND_SZPF','FATES_VEGC_SZPF','FATES_VEGN_SZPF','FATES_VEGP_SZPF','FATES_STOREN_TF_CANOPY_SZPF','FATES_STOREN_TF_USTORY_SZPF','FATES_STOREP_TF_CANOPY_SZPF','FATES_STOREP_TF_USTORY_SZPF','FATES_NH4UPTAKE_SZPF','FATES_NO3UPTAKE_SZPF','FATES_PUPTAKE_SZPF','FATES_NEFFLUX_SZPF','FATES_DDBH_CANOPY_SZPF','FATES_DDBH_USTORY_SZPF','FATES_PEFFLUX_SZPF','FATES_NFIX_SYM_SZPF','FATES_NPP_SZPF','FATES_STOREC_TF_CANOPY_SZPF','FATES_STOREC_TF_USTORY_SZPF','FATES_FROOTCTURN_USTORY_SZ','FATES_FROOTCTURN_CANOPY_SZ','FATES_NDEMAND_SZPF','FATES_PDEMAND_SZPF','FATES_LEAFC_SZPF','FATES_LEAFN_SZPF','FATES_LEAFP_SZPF','FATES_FROOTC_SZPF','FATES_FROOTN_SZPF','FATES_FROOTP_SZPF','FATES_REPROC_SZPF','FATES_REPRON_SZPF','FATES_REPROP_SZPF','FATES_SAPWOODC_SZPF','FATES_SAPWOODN_SZPF','FATES_SAPWOODP_SZPF','FATES_STOREC_SZPF','FATES_STOREN_SZPF','FATES_STOREP_SZPF','FATES_LEAF_ALLOC_SZPF','FATES_SEED_ALLOC_SZPF','FATES_STEM_ALLOC','FATES_FROOT_ALLOC_SZPF','FATES_CROOT_ALLOC','FATES_STORE_ALLOC','FATES_DDBH_SZPF','FATES_BASALAREA_SZPF'"

echo ""
echo "Loaded Kougarok site configuration"
echo "  Site: ${A2MC_SITE_NAME}"
echo "  PFTs: ${A2MC_PFTS}"
echo "  Parameters: ${A2MC_N_PARAMS}"
echo "  Ensemble size: ${A2MC_TOTAL_ENSEMBLE}"
echo "  Use case dir: ${A2MC_USE_CASE_DIR}"
