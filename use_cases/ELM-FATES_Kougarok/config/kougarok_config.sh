#!/bin/bash
# =============================================================================
# Kougarok Site-Specific Configuration
# =============================================================================
# This file contains ALL site-specific settings for Kougarok, Alaska.
# Source this AFTER sourcing the main a2mc_config.sh:
#
#   source a2mc_config.sh
#   source use_cases/ELM-FATES_Kougarok/config/kougarok_config.sh
#   print_config  # Verify settings
# =============================================================================

# ---------------------------------------------------------------------------
# IDENTITY + PATHS
#
# The case's identity is DECLARED, and its paths derive from it. Nothing here
# discovers where this file physically sits, so nothing depends on which shell
# sourced it (`BASH_SOURCE` is a bash builtin and is EMPTY under zsh, which
# silently collapsed these paths to $PWD's parent).
#
# It also makes the invariant true by construction rather than by convention:
# A2MC_USE_CASE_DIR can no longer disagree with A2MC_SITE_NAME.
# ---------------------------------------------------------------------------

# A2MC_ROOT comes from a2mc_config.sh, which is sourced FIRST (see
# feedback_source_config_order_and_round_selection). Fail loudly if it is not.
export A2MC_SITE_NAME="ELM-FATES_Kougarok"

: "${A2MC_ROOT:?A2MC_ROOT unset - source a2mc_config.sh BEFORE this site config}"

export A2MC_USE_CASE_DIR="${A2MC_ROOT}/use_cases/${A2MC_SITE_NAME}"

# A2MC_SITE_CONFIG is the ONE value that must still self-locate: it has to name
# the file ACTUALLY sourced, and a round wrapper (e.g. <site>_config_r4.sh)
# sources this base then overwrites it - last wins. A declared name cannot know
# which wrapper is in play. `:-$0` is the zsh fallback; it is unreachable under
# bash, which always sets BASH_SOURCE[0] when sourcing.
_A2MC_SC_SRC="${BASH_SOURCE[0]:-$0}"
export A2MC_SITE_CONFIG="$(cd "$(dirname "$_A2MC_SC_SRC")" && pwd)/$(basename "$_A2MC_SC_SRC")"
unset _A2MC_SC_SRC

# -----------------------------------------------------------------------------
# Model Source Path (Phase 4 RAG version association — required)
# -----------------------------------------------------------------------------
# Absolute path to the E3SM/ELM-FATES checkout used to RUN this case. The
# RAG infrastructure detects ELM + FATES commits from this path and selects
# the matching milestone profile. On this (main) branch the case runs against
# the canonical api-43-1 checkout (FATES e027a40 / ELM d40b843).
#
# On Perlmutter:
#   /global/cfs/cdirs/<your_project>/<your_user>/E3SM_FATES_api43   (api-43-1, canonical — this case)
#   /global/cfs/cdirs/<your_project>/<your_user>/E3SM_FATES         (api-31-0, Kougarok manuscript — demo branch)
#
# Precedence: a shell export of A2MC_MODEL_PATH before sourcing wins; otherwise
# this site value overrides a2mc_config.sh's machine-level default. To switch
# checkouts, edit the path below or shell-export A2MC_MODEL_PATH beforehand.
if [ -z "${A2MC_MODEL_PATH:-}" ] || [ "${_A2MC_MODEL_PATH_IS_DEFAULT:-}" = "1" ]; then
    export A2MC_MODEL_PATH="/global/cfs/cdirs/<your_project>/<your_user>/E3SM_FATES_api43"
    unset _A2MC_MODEL_PATH_IS_DEFAULT
fi

# -----------------------------------------------------------------------------
# Site Information
# -----------------------------------------------------------------------------
# A2MC_SITE_NAME is declared at the top, before the paths that derive from it.
export A2MC_SITE_DESCRIPTION="Arctic tundra, Seward Peninsula, Alaska (NGEE-Arctic)"
export A2MC_SITE_LAT=65.1
export A2MC_SITE_LON=-164.8

# -----------------------------------------------------------------------------
# PFT Configuration
# -----------------------------------------------------------------------------
# A2MC_PFTS = the **1-based FATES PFT ids** (positions in the base file's `fates_pftname`)
# of the PFTs this study calibrates. This is A2MC's own knob (A2MC_ prefix per CLAUDE.md
# Rule 8); it is NOT a FATES-native variable — it *selects* which FATES PFTs are targets.
# Mapping to FATES: id N here == fates_pftname[N] in $A2MC_BASE_PARAM_FILE (verify with
# `python -c "from tools.fates_utils import get_pft_names_from_file as g; print(g('<base>'))"`).
# The TOTAL PFT count is NOT set here — it is read from the base file at runtime
# (get_n_pft_from_file), so it tracks the model (api-43 default = 14 PFTs; arctic shrubs
# sit at 10/11/12). The api-31 study used 7/9/10 on a 12-PFT file, remapped by functional type.
export A2MC_PFTS="10,11,12"
export A2MC_PFT_NAMES="Evergreen_Arctic_Shrub,Colddecid_Arctic_Shrub,Arctic_C3_Grass"

# PFT indices (0-based for array access)
export A2MC_PFT10_INDEX=9   # broadleaf_evergreen_arctic_shrub  (was PFT#7 on api-31)
export A2MC_PFT11_INDEX=10  # broadleaf_colddecid_arctic_shrub  (was PFT#9 on api-31)
export A2MC_PFT12_INDEX=11  # arctic_c3_grass                   (was PFT#10 on api-31)

# -----------------------------------------------------------------------------
# Domain and Surface Data
# -----------------------------------------------------------------------------
export A2MC_DOMAIN_DIR="/dvs_ro/u1/<x>/<your_user>/CaseScripts/Kougarok_FATES"
export A2MC_DOMAIN_FILE="domain_Kougarok_from0.125x0.125_simyr1850_c240309.nc"
export A2MC_SURFACE_FILE="surfdata_Kougarok_from0.125x0.125_simyr1850_c240309_ModPval.nc"

# CNP soil parameters
export A2MC_SOILORDER_DIR="/global/homes/<x>/<your_user>/E3SM_Aid/clm_params"
export A2MC_SOILORDER_FILE="CNP_parameters_c180312.nc"

# Forcing data redirects
export A2MC_FORCING_DIR="${HOME}/E3SM_Aid/RedirectForcing/atm_forcing.datm7.GSWP3-w5e5.c211106"

# -----------------------------------------------------------------------------
# Parameter Configuration (api-43, 14-PFT, docs/37 explicit-column CSV) (override a2mc_config.sh)
# -----------------------------------------------------------------------------
# N_PARAMS is DERIVED from the param list (never hardcoded) so it stays in sync as the list changes;
# the ensemble SIZE is then computed by scheme in calculate_ensemble_size() (Morris trajectories vs
# Sobol vs LHS all differ — see a2mc_config.sh). Change the scheme/trajectories, not a hardcoded count.
# Sampling scheme: "morris", "lhs" (Latin Hypercube), "sobol", or "custom"
export A2MC_SAMPLING_SCHEME="morris"
export A2MC_N_TRAJECTORIES=30

# Parameter list. This filename is the ONLY place the parameter count appears as a literal
# ("para168"); every downstream name/count derives from $A2MC_N_PARAMS below — never hardcode
# the number anywhere else (feedback_derive_pft_count_never_hardcode).
export A2MC_PARAM_LIST_FILE="${A2MC_USE_CASE_DIR}/parameters/FATES_Parameter_List_api43_para169.csv"

# Derive the parameter count from the list CONTENT (authoritative, format-agnostic). If the count
# tool fails, fall back to the number in the filename (parsed) — so no literal count lives here.
export A2MC_N_PARAMS=$(python "$(dirname "$(dirname "$A2MC_USE_CASE_DIR")")/tools/count_param_list.py" "$A2MC_PARAM_LIST_FILE" 2>/dev/null || { _p="${A2MC_PARAM_LIST_FILE##*para}"; echo "${_p%%[!0-9]*}"; })

# SALib problem file name derives from the count (the file itself is regenerated by create_parameter_sample.py)
export A2MC_SALIB_PROBLEM_FILE="${A2MC_USE_CASE_DIR}/parameters/salib_problem_api43_para${A2MC_N_PARAMS}.txt"

# Total ensemble size — computed by scheme, not hardcoded (Morris: N_TRAJ×(N_PARAMS+1))
export A2MC_TOTAL_ENSEMBLE=$(calculate_ensemble_size)

# -----------------------------------------------------------------------------
# Validation Targets
# -----------------------------------------------------------------------------
# A2MC_VALIDATION_TARGETS is the LIVE target file: the calibration pipeline loads it via
# tools.targets_loader.load_case_targets() -> resolve_targets_yaml() (screening, diagnosis,
# single-case eval). Set it explicitly here so there's no ambiguity (it otherwise defaults
# to $A2MC_USE_CASE_DIR/validation/targets.yaml). Keyed api-43 PFT10/11/12.
export A2MC_VALIDATION_TARGETS="${A2MC_USE_CASE_DIR}/validation/targets.yaml"

# Validation period (growing season)
export A2MC_VALIDATION_START_YEAR=2000
export A2MC_VALIDATION_END_YEAR=2019
export A2MC_VALIDATION_MONTHS="7,8"  # Measurements at the end of July

# Calibration settings
export A2MC_ERROR_METHOD="relative_error"
export A2MC_AGGREGATION_METHOD="rmsre"
export A2MC_TOLERANCE=0.20  # 20% tolerance
export A2MC_TOP_N=50

# -----------------------------------------------------------------------------
# ELM Build/Namelist Options
# -----------------------------------------------------------------------------
# Override ELM Options
export A2MC_RGSP_SUPLPHOS="ALL"
export A2MC_ELM_OPTIONS="-nutrient cnp -nutrient_comp_pathway eca -soil_decomp century"

# -----------------------------------------------------------------------------
# Ensemble Paths
# -----------------------------------------------------------------------------
#export A2MC_ENSEMBLE_NAME="Kougarok_PlantTraitsCNPEnsemble162_Morris"
#export A2MC_ENSEMBLE_NAME="Kougarok_PlantTraitsCNPEnsemble162_Morris_RGSPsuplP" #3rd round of calibration (api-31-0)
export A2MC_ENSEMBLE_NAME="Kougarok_FATESapi43_CNPECA_Para${A2MC_N_PARAMS}" # api-43-1 canonical run (FATES e027a40 / ELM d40b843); param count derives from the list, never hardcode it (api-31 had 162; api-43 went 171 -> 168 dropping the inactive eca_alpha_ptase rows -> 169 adding the per-PFT fates_phen_gddthresh_c #17 split)
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
# R1 (2026-08-17, PI decision): enable the CWDOut litter-flux fix for calibration. R1's
# Morris ensemble is still status=planned (calibration_rounds.yaml) -- no cases created yet
# under the old (fix-off) behavior, so this applies cleanly to the whole round. See
# memory/model_logs/20260817a_Root_Fines_Frag_Fix_Merged_To_Fork_Main.md for the merge, and
# use_cases/ELM-FATES_Kougarok/memory/phase_results/20260812a_.../leafroot_biomass_vs_obs_monthly.md
# for why single-parameterization biomass-vs-obs results don't settle whether the fix helps
# the calibrated ensemble -- that's exactly what R1's Morris sweep now gets to test.
export A2MC_USE_ROOTFINESFRAG_FIX=".true."
# All other Tier 2 / Tier 3 flags default off (no fire, no hydraulics, etc.)
# -----------------------------------------------------------------------------
# Extracted monthly data (NetCDF files from extract_monthly_variables_FATES.py)
export A2MC_EXTRACTED_DATA="${A2MC_OUTPUT_ROOT}/${A2MC_ENSEMBLE_NAME}_Extract"

# Case scripts directory — where create_case.sh --write-script puts the generated per-case
# driver scripts (and their logs), consumed by phases/phase0_design/submit_phase0.py. NOT the
# CIME case dir: create_case.sh always creates those under ${A2MC_E3SM_ROOT}/cime/scripts/.
#
# Derived from A2MC_ENSEMBLE_NAME so each round gets its own tree and cannot overwrite the
# previous one. Do NOT re-append "Kougarok_FATES" here: A2MC_SCRIPTS_DIR already ends in it
# (it did not in the api-31 era, which is how the doubled
# .../CaseScripts/Kougarok_FATES/Kougarok_FATES/... path arose — fixed 2026-08-02).
export A2MC_CASE_SCRIPTS="${A2MC_SCRIPTS_DIR}/${A2MC_ENSEMBLE_NAME}"
export A2MC_LOG_DIR="${A2MC_CASE_SCRIPTS}"

# -----------------------------------------------------------------------------
# HPC Paths (NERSC Perlmutter)
# -----------------------------------------------------------------------------
# Base FATES parameter file (template) — the pristine api-43 14-PFT model default (FATES e027a40).
# api-43 uses JSON natively (FATES switched from NetCDF/CDL to JSON at api.43). This is the GENERIC
# upstream default; arctic-tuning of any remaining NON-calibrated params is a follow-up
# (feedback_port_tuned_base_param_file_across_versions) — the big one, dbh_repro_threshold, is now
# a calibrated list param so its base value no longer matters.
export A2MC_BASE_PARAM_FILE="${A2MC_MODEL_PATH}/components/elm/src/external_models/fates/parameter_files/fates_params_default.json"

# Directory holding the generated per-case FATES parameter files (written by Phase 0's
# generate_parameter_files.py). Anchored on ${A2MC_OUTPUT_ROOT} (the <your_project> CFS allocation that
# already holds the ensemble output + extract), NOT on NERSC home: 5,100 generated files do not
# belong under a home quota, and a literal path violates CLAUDE.md rule 8.
# The round token derives from A2MC_N_PARAMS, so a new parameter list yields a new directory and
# two rounds cannot overwrite each other.
# (Was /global/homes/<x>/<your_user>/E3SM_Aid/FATES-ParameterFiles/fates_params_api43_14pft_Morris —
#  the api-31 R1-R5 param sets still live under E3SM_Aid, but that api-43 subdir was never
#  populated: Phase 0 has not run, and no log, README or case template references it. PI
#  decision 2026-08-02 to move api-43 onto CFS.)
export A2MC_PARAM_DIR="${A2MC_OUTPUT_ROOT}/ParameterFiles/fates_params_api43_para${A2MC_N_PARAMS}_Morris"

# Parameter file naming pattern ({N} = case number). Carries the round token for the same reason.
export A2MC_PARAM_PATTERN="fates_params_api43.1.0_e027a40__PtCNP${A2MC_N_PARAMS}_En{N}.json"

# Morris ensemble matrix (rows = A2MC_TOTAL_ENSEMBLE, cols = A2MC_N_PARAMS) - site-specific data
# Note: A2MC_ROOT is two levels up from use_cases/ELM-FATES_Kougarok/config/
# A2MC_ROOT is set by a2mc_config.sh (sourced first); re-deriving it from
# A2MC_USE_CASE_DIR would now be circular, since that derives FROM A2MC_ROOT.
export A2MC_ENSEMBLE_MATRIX_FILE="${A2MC_USE_CASE_DIR}/parameters/FATES_api43_PlantTraitsCNP_Morris_matrix.txt"

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
