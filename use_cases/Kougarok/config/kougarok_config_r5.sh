#!/bin/bash
# =============================================================================
# Kougarok Round 5 Configuration — Full Morris ensemble with PRESCRIBED P UPTAKE
# =============================================================================
# Round 5 (designed 2026-05-12, motivated by the May 11-12 R4 attribution
# refresh + the May 11 correction of the old R4 subset_replay reading):
#
#   - Sampling: FULL Morris ensemble at 162 parameters, 4890 simulations
#     (same X matrix as R2/R3/R4 — no Morris regeneration needed).
#   - Parameter files: per-case NCs already encode the Morris draws (inherited
#     from R3/R4). R5 applies a SINGLE override on top: every case has
#     `fates_cnp_prescribed_puptake = 1.0` (all 12 PFTs). Combined with the
#     FATES `prescribed-puptake-fix` patch on `fates-cnp-eca-tj`, this
#     delivers P uptake at the plant's daily demand rate during all phases.
#   - Protocol: ALL supplementation OFF in every phase (ADSP / RGSP / TRANS).
#       ADSP_SUPLPHOS  = NONE   (NEW — overrides a2mc_config.sh default ALL)
#       ADSP_SUPLNITRO = NONE   (default, kept)
#       RGSP_SUPLPHOS  = NONE   (default, kept)
#       RGSP_SUPLNITRO = NONE   (default, kept)
#       TRANS_SUPLPHOS = NONE   (default, kept)
#       TRANS_SUPLNITRO= NONE   (default, kept)
#   - FATES build: jingtao-lbl/fates@fates-cnp-eca-tj (the same build as new R4).
#     Has TWO patches over base e85d997:
#       (a) gradual hydraulic mortality ramp (replaces binary threshold)
#       (b) prescribed-puptake-fix: FatesSoilBGCFluxMod.F90:202 reads
#           prescribed_puptake(pft) (instead of the buggy prescribed_nuptake(pft))
#           for the P-gain magnitude. CRITICAL: this patch is what makes
#           `fates_cnp_prescribed_puptake = 1.0` actually deliver "P at full
#           demand" — without it, the param value is ignored and the magnitude
#           is silently read from prescribed_nuptake (which is set to 0).
#
# Scientific motivation:
#
#   The May 11-12 R2-vs-R4 attribution refresh (memory/ana_logs/20260511a_*.md)
#   identified a fine-root re-allocation pathology under R4's ADSP_SUPLNITRO=ALL:
#   plants reduced fine-root investment during supplementation, then could not
#   recover the foraging structure once supplementation was removed. The
#   "fattening then starving" cycle confounds any nutrient-supplementation test.
#
#   R5 sidesteps this by removing ALL phase-level supplementation and instead
#   prescribing P uptake at full demand throughout. This decouples "is P
#   availability the bottleneck?" from "does supplementation distort
#   allocation?". If PFT10 still fails to establish under R5, then P
#   availability is not the bottleneck — the constraint is elsewhere
#   (allocation logic, light competition, fineroot turnover rate, etc.).
#
#   The May 11 correction (memory/ana_logs/20260511b_*.md) further established
#   that "fully prescribed P uptake" has never been cleanly tested in any
#   A2MC round:
#     - R2/R3: coupled P uptake via ECA (no prescription).
#     - Old R4 (subset_replay_PrescP, superseded): set
#       prescribed_puptake=1.0 but prescribed_nuptake=0 (the A2MC ensemble
#       generator's default). Combined with the unpatched FATES source quirk,
#       this delivered effective P uptake = ZERO during TRANS. Old R4 thus
#       tested P starvation, not prescribed P at full demand.
#     - R5 (new): prescribed_puptake=1.0 + the fates-cnp-eca-tj patch (which
#       decouples the P magnitude path from prescribed_nuptake). First time
#       the intended "full demand P" treatment actually runs.
#
# Relationship to other rounds:
#   - vs R2: same Morris design + same FATES *source code* pattern. R5
#     differs by (a) prescribed_puptake=1.0 override and (b) ADSP_SUPLPHOS=NONE.
#   - vs R3: R3 added RGSP_SUPLPHOS=ALL; R5 reverts that (to NONE, same as R2).
#   - vs R4 (new): R4 enabled ADSP_SUPLNITRO=ALL; R5 has NO supplementation
#     in any phase. R4's primary protocol is "N during ADSP only"; R5 is
#     "prescribed P throughout, otherwise coupled."
#   - vs old R4 (superseded): same intent (prescribed P throughout) but
#     correctly delivered. Case numbering also expanded to full 4890 (old R4
#     subset-replayed only top-200 R3 cases).
#
# Usage:
#   source a2mc_config.sh
#   source use_cases/Kougarok/config/kougarok_config_r5.sh
#   print_config  # Verify settings
# =============================================================================

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export A2MC_USE_CASE_DIR="$(dirname "$SCRIPT_DIR")"

# Self-identification: expose this config's absolute path so A2MC tools can
# detect which round config is active without ambiguous filesystem globbing.
export A2MC_SITE_CONFIG="${SCRIPT_DIR}/$(basename "${BASH_SOURCE[0]}")"

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

# Calculate and export total ensemble size: 30 * (162+1) = 4890
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
# ELM Build/Namelist Options — R5 protocol
# -----------------------------------------------------------------------------
# All phases run with no nutrient supplementation. P is prescribed via the
# per-case NC override (fates_cnp_prescribed_puptake=1.0) — see the param
# file regeneration step (apply_param_override.py) that produces R5's NCs
# from R3's. With the fates-cnp-eca-tj prescribed-puptake-fix patch active,
# this delivers daily_p_gain = 1.0 × demand in all phases.
#
# Only one override vs a2mc_config.sh defaults: A2MC_ADSP_SUPLPHOS.
# Every other suplnitro/suplphos already defaults to NONE in a2mc_config.sh.
export A2MC_ADSP_SUPLPHOS="NONE"

# Explicit re-assertion of the other supplements for documentation. These
# are already NONE by default in a2mc_config.sh, but stating them here makes
# the R5 protocol obvious to anyone reading this file in isolation.
export A2MC_ADSP_SUPLNITRO="NONE"
export A2MC_RGSP_SUPLPHOS="NONE"
export A2MC_RGSP_SUPLNITRO="NONE"
export A2MC_TRANS_SUPLPHOS="NONE"
export A2MC_TRANS_SUPLNITRO="NONE"

export A2MC_ELM_OPTIONS="-nutrient cnp -nutrient_comp_pathway eca -soil_decomp century"

# -----------------------------------------------------------------------------
# Ensemble Paths (R5: prescribed P throughout, "PrescP" suffix)
# -----------------------------------------------------------------------------
# History of ensemble names for this site:
#   R2: Kougarok_PlantTraitsCNPEnsemble162_Morris
#   R3: Kougarok_PlantTraitsCNPEnsemble162_Morris_RGSPsuplP
#   Old R4 (subset_replay, superseded): Kougarok_PlantTraitsCNPEnsemble162_PrescribedP
#       (200 cases, intended prescribed P but actually delivered P starvation
#       due to FATES source quirk — see 20260511b correction log)
#   R4 (current — full Morris with ADSP N+P supplementation):
#       Kougarok_PlantTraitsCNPEnsemble162_Morris_ADSPSupNP
#   R5 (current design): Kougarok_PlantTraitsCNPEnsemble162_PrescribedP
#       Same ensemble name as old R4 (reusing the path) but now (a) full 4890
#       cases instead of top-200 subset, and (b) the FATES patch makes the
#       prescribed_puptake override actually work as intended.
export A2MC_ENSEMBLE_NAME="Kougarok_PlantTraitsCNPEnsemble162_PrescribedP"
export A2MC_ENSEMBLE_PREFIX="Kougarok_ELM-FATES"

# Case names: append "PrescP" suffix after the case number so R5 case folders
# don't collide with R2/R3/new-R4 case folders on the shared CIME scripts
# directory. (Note: old R4 subset_replay also used "PrescP" — its case dirs
# are still on /global/cfs/cdirs/m2467/jingtao/... and will need cleanup
# before R5 launch, or R5 can pick a different suffix to keep both viewable.)
export A2MC_CASE_NAME_PATTERN="${A2MC_ENSEMBLE_PREFIX}_PtCNPEn{N}PrescP_{PHASE}"

export A2MC_ENSEMBLE_OUTPUT="${A2MC_OUTPUT_ROOT}/${A2MC_ENSEMBLE_NAME}"
# Extracted monthly data (NetCDF files from extract_monthly_variables_FATES.py)
export A2MC_EXTRACTED_DATA="${A2MC_OUTPUT_ROOT}/${A2MC_ENSEMBLE_NAME}_Extract"

# Case scripts directory
export A2MC_CASE_SCRIPTS="${A2MC_SCRIPTS_DIR}/Kougarok_FATES/ReCalibration_PtCNP162_AllPhase_PrescribedP"
export A2MC_LOG_DIR="${A2MC_CASE_SCRIPTS}"

# -----------------------------------------------------------------------------
# HPC Paths (NERSC Perlmutter)
# -----------------------------------------------------------------------------
# Base FATES parameter file (template — same for all rounds)
export A2MC_BASE_PARAM_FILE="/global/homes/j/jingtao/E3SM_Aid/FATES-ParameterFiles/fates_params_api25.5.0_12pft_c230710.nc"

# Directory containing FATES parameter files for the R5 ensemble.
# Built by apply_param_override.py: copies R3's 4890 NCs (each encoding the
# Morris draws) and applies fates_cnp_prescribed_puptake=1.0 to every PFT.
export A2MC_PARAM_DIR="/global/homes/j/jingtao/E3SM_Aid/FATES-ParameterFiles/fates_params_PrescribedP_EnPlantTraitsCNPparam162"

# Parameter file naming pattern ({N} = case number 1-4890)
export A2MC_PARAM_PATTERN="fates_params_api25.5.0_12pft_c230710__PtCNP162_En{N}.nc"

# Morris ensemble matrix (4890 x 162) - site-specific data, reused from R2/R3/R4
export A2MC_ROOT="$(dirname "$(dirname "$A2MC_USE_CASE_DIR")")"
export A2MC_ENSEMBLE_MATRIX_FILE="${A2MC_USE_CASE_DIR}/parameters/FATES_CNPnPlantTraits_162param_Morris_4890sets.txt"

# -----------------------------------------------------------------------------
# Cross-ensemble bld reuse — R5 COULD reuse R4's case-1 FATES binary
# -----------------------------------------------------------------------------
# R5 runs on the same FATES build as R4-current (fates-cnp-eca-tj branch with
# both patches over base e85d997). The FATES binary is identical — only the
# parameter values + protocol settings differ. In principle every R5 case
# (INCLUDING case 1) can point EXEROOT directly at R4 case 1's bld dir,
# skipping the ~30 min FATES compile entirely.
#
# COMMENTED OUT FOR R5 PILOT (2026-05-12). Two reasons:
#   1. The cross-ensemble reuse code path (create_case.sh + commit c7414c6)
#      is brand new and has never run end-to-end against CIME. Better to
#      test the well-trodden --reuse-build N pattern first (the same path
#      R3 and R4-current used in production).
#   2. Building R5's own case-1 bld makes R5 "self-owned" — independent of
#      R4 case-dir cleanup policy. If R4 case dirs ever get archived, R5's
#      reuse won't break.
#
# Pilot plan: R5 case 1 builds fresh (~30 min FATES compile), then cases
# 2..4890 use --reuse-build 1 to share R5 case 1's bld. The env var below
# stays commented out unless the orchestrator explicitly switches to
# zero-build mode.
#
# To enable zero-build R5 (skip even case 1's compile), uncomment the
# line below. The {PHASE} placeholder is substituted at create_case.sh
# runtime so the same template covers ADSP, RGSP, and TRANS.
#
# R4 bld dirs verified to exist as of 2026-05-12 13:38:
#   /global/cfs/cdirs/m2467/jingtao/Kougarok_PlantTraitsCNPEnsemble162_Morris_ADSPSupNP/
#     Kougarok_ELM-FATES_PtCNPEn1ADSPSupNP_{ADSP,RGSP,TRANS}/bld   (each has e3sm.exe)
#
#export A2MC_REUSE_BUILD_EXEROOT_TEMPLATE="${A2MC_OUTPUT_ROOT}/Kougarok_PlantTraitsCNPEnsemble162_Morris_ADSPSupNP/Kougarok_ELM-FATES_PtCNPEn1ADSPSupNP_{PHASE}/bld"

# -----------------------------------------------------------------------------
# Phenology Calibration (placeholder, not active in R5)
# -----------------------------------------------------------------------------
#export A2MC_PHEN_GDDTHRESH_C=-0.00991
#export A2MC_PHEN_CHILLTEMP=2.262

# -----------------------------------------------------------------------------
# History Output Variables
# -----------------------------------------------------------------------------
export A2MC_HIST_SZPF_VARS="'FATES_VEGC_ABOVEGROUND_SZPF','FATES_VEGC_SZPF','FATES_VEGN_SZPF','FATES_VEGP_SZPF','FATES_STOREN_TF_CANOPY_SZPF','FATES_STOREN_TF_USTORY_SZPF','FATES_STOREP_TF_CANOPY_SZPF','FATES_STOREP_TF_USTORY_SZPF','FATES_NH4UPTAKE_SZPF','FATES_NO3UPTAKE_SZPF','FATES_PUPTAKE_SZPF','FATES_NEFFLUX_SZPF','FATES_DDBH_CANOPY_SZPF','FATES_DDBH_USTORY_SZPF','FATES_PEFFLUX_SZPF','FATES_NFIX_SYM_SZPF','FATES_NPP_SZPF','FATES_STOREC_TF_CANOPY_SZPF','FATES_STOREC_TF_USTORY_SZPF','FATES_FROOTCTURN_USTORY_SZ','FATES_FROOTCTURN_CANOPY_SZ','FATES_NDEMAND_SZPF','FATES_PDEMAND_SZPF','FATES_LEAFC_SZPF','FATES_LEAFN_SZPF','FATES_LEAFP_SZPF','FATES_FROOTC_SZPF','FATES_FROOTN_SZPF','FATES_FROOTP_SZPF','FATES_REPROC_SZPF','FATES_REPRON_SZPF','FATES_REPROP_SZPF','FATES_SAPWOODC_SZPF','FATES_SAPWOODN_SZPF','FATES_SAPWOODP_SZPF','FATES_STOREC_SZPF','FATES_STOREN_SZPF','FATES_STOREP_SZPF','FATES_LEAF_ALLOC_SZPF','FATES_SEED_ALLOC_SZPF','FATES_STEM_ALLOC','FATES_FROOT_ALLOC_SZPF','FATES_CROOT_ALLOC','FATES_STORE_ALLOC','FATES_DDBH_SZPF','FATES_BASALAREA_SZPF'"

echo ""
echo "Loaded Kougarok R5 site configuration (PrescribedP, full Morris 4890)"
echo "  Site: ${A2MC_SITE_NAME}"
echo "  PFTs: ${A2MC_PFTS}"
echo "  Parameters: ${A2MC_N_PARAMS}"
echo "  Ensemble size: ${A2MC_TOTAL_ENSEMBLE}"
echo "  Protocol: all supplementation OFF in all 3 phases"
echo "  Param dir: ${A2MC_PARAM_DIR}"
echo "  Use case dir: ${A2MC_USE_CASE_DIR}"
