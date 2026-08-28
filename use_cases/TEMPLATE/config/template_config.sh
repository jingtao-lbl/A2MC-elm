#!/bin/bash
# =============================================================================
# A2MC Site Configuration Template
# =============================================================================
#
# Copy this file to your site's config directory and rename:
#   cp use_cases/TEMPLATE/config/template_config.sh \
#      use_cases/{Model}_{Case}/config/<case>_config.sh
#
# Then edit the values below. Source it AFTER the machine config, always in
# this order (feedback_source_config_order_and_round_selection):
#   source a2mc_config.sh                                   # machine-level
#   source use_cases/{Model}_{Case}/config/<case>_config.sh # this file
#
# WHAT BELONGS HERE vs ELSEWHERE
#   a2mc_config.sh ......... machine-level: A2MC_ROOT, A2MC_OUTPUT_ROOT,
#                            A2MC_SCRIPTS_DIR, A2MC_RAG_DIR, A2MC_MODEL_PATH,
#                            calculate_ensemble_size(). Do NOT restate them here.
#   this file .............. everything site- and round-specific.
#   validation/targets.yaml  the targets AND the scoring config (see §5).
#   config/calibration_rounds.yaml
#                            the per-round record. Do NOT hand-type it — derive
#                            it from this file:
#                              python tools/generate_calibration_rounds.py --round N --write
#                              python tools/check_calibration_rounds.py
#
# THE ONE RULE: derive, never hardcode. The parameter count, ensemble size and
# every name built from them come from the parameter list. Change the list (or
# the scheme), not a literal (feedback_derive_pft_count_never_hardcode).
#
# Every variable below is consumed by A2MC code. Verify with:
#   grep -rl A2MC_<VAR> --include='*.py' --include='*.sh' .
# =============================================================================

# ---------------------------------------------------------------------------
# IDENTITY + PATHS  —  set A2MC_SITE_NAME and the rest follows
#
# The case's identity is DECLARED here; its paths derive from it. Nothing below
# discovers where this file physically sits, so nothing depends on which shell
# sourced it. (`BASH_SOURCE` is a bash builtin and is EMPTY under zsh, which
# used to collapse these paths to $PWD's parent — silently, with no error.)
#
# ★ A2MC_SITE_NAME MUST match this case's directory name under use_cases/.
#   Deriving one from the other makes them impossible to disagree; a mismatch
#   now fails loudly (the path will not exist) instead of quietly.
# ---------------------------------------------------------------------------
# ★ NAMING: `{Model}_{Site}` — the model is part of the identity.
#   Use `ELM-FATES_Kougarok`, not `Kougarok`, because the SAME site is calibrated
#   under different model configurations (`ELM_Kougarok` for ELM-only) and they are
#   different cases with different parameters, targets and results. A bare site name
#   silently collides the moment the second configuration appears.
#   Hyphens belong to the MODEL half (`ELM-FATES`), underscore separates the halves.
#   This matches the adapter-kit branch's `<Model>_<Case>` convention.
#
#   MUST equal this case's directory name under `use_cases/` — `A2MC_USE_CASE_DIR`
#   derives from it, so a mismatch fails loudly rather than quietly.
#
#   Renaming an EXISTING case: rename the directory and this value together. What
#   it touches — the case dir, `ELM_USRDAT_NAME` (a CIME label; the datasets come
#   from explicit `A2MC_DOMAIN_FILE`/`A2MC_SURFACE_FILE`, so this is low-risk but
#   worth confirming on the first run), log headers, and the offline workflow state.
#   What it does NOT touch: `A2MC_ENSEMBLE_NAME` and `A2MC_CASE_NAME_PATTERN` are
#   set independently, so existing case names and outputs on disk keep their names.
export A2MC_SITE_NAME="ELM-FATES_MySite"   # ← {Model}_{Case}; must equal the use_cases/ dir name

# A2MC_ROOT comes from a2mc_config.sh, which is sourced FIRST. Fail loudly if not.
# Since 2026-08-26 this file AUTO-SOURCES the machine config when it has not been sourced yet,
# so one command is enough:  source use_cases/{Model}_{Case}/config/<case>_config.sh
# Sourcing a2mc_config.sh first still works and makes this block a no-op.
#
# The bootstrap path locates a2mc_config.sh ONLY -- it never becomes A2MC_ROOT, which still comes
# from a2mc_config.sh itself. BASH_SOURCE is a bash builtin and is EMPTY under zsh, so the
# walk-up-from-$PWD branch is what runs there; if neither branch finds the file the `:?` guard
# below still fails loudly rather than half-configuring the shell.
if [ -z "${A2MC_ROOT:-}" ]; then
    _a2mc_boot=""
    if [ -n "${BASH_SOURCE:-}" ]; then
        _a2mc_boot="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." 2>/dev/null && pwd)"
    fi
    if [ -z "$_a2mc_boot" ] || [ ! -f "$_a2mc_boot/a2mc_config.sh" ]; then
        _a2mc_boot="$PWD"
        while [ "$_a2mc_boot" != "/" ] && [ ! -f "$_a2mc_boot/a2mc_config.sh" ]; do
            _a2mc_boot="$(dirname "$_a2mc_boot")"
        done
    fi
    [ -f "$_a2mc_boot/a2mc_config.sh" ] && . "$_a2mc_boot/a2mc_config.sh"
    unset _a2mc_boot
fi

: "${A2MC_ROOT:?A2MC_ROOT unset and a2mc_config.sh could not be located automatically - source a2mc_config.sh first}"

export A2MC_USE_CASE_DIR="${A2MC_ROOT}/use_cases/${A2MC_SITE_NAME}"

# A2MC_SITE_CONFIG is the ONE value that must still self-locate: it has to name
# the file ACTUALLY sourced, and a round wrapper (<site>_config_r4.sh) sources
# this base then overwrites it — last wins. A declared name cannot know which
# wrapper is in play. `:-$0` is the zsh fallback, unreachable under bash.
_A2MC_SC_SRC="${BASH_SOURCE[0]:-$0}"
export A2MC_SITE_CONFIG="$(cd "$(dirname "$_A2MC_SC_SRC")" && pwd)/$(basename "$_A2MC_SC_SRC")"
unset _A2MC_SC_SRC

# -----------------------------------------------------------------------------
# 1. SITE IDENTITY
# -----------------------------------------------------------------------------
# A2MC_SITE_NAME is declared at the top, before the paths that derive from it.
export A2MC_SITE_DESCRIPTION="One line describing the site"
export A2MC_SITE_LAT="64.86"             # decimal degrees
export A2MC_SITE_LON="-164.83"           # decimal degrees

# -----------------------------------------------------------------------------
# 2. DOMAIN / SURFACE / FORCING DATA  (read by tools/create_case.sh)
# -----------------------------------------------------------------------------
# One shared directory plus bare FILENAMES — that split is what create_case.sh
# expects. (An older template used A2MC_DOMAIN_DATA / A2MC_SURFACE_DATA holding
# full paths; nothing reads those names. Use the DIR + FILE forms below.)
export A2MC_DOMAIN_DIR="/path/to/your/domain_and_surface_data"
export A2MC_DOMAIN_FILE="domain_${A2MC_SITE_NAME}.nc"
export A2MC_SURFACE_FILE="surfdata_${A2MC_SITE_NAME}.nc"
# Soil-order input (ELM CNP); may live in the same dir as above.
export A2MC_SOILORDER_DIR="/path/to/your/soilorder_data"
export A2MC_SOILORDER_FILE="soilorder_${A2MC_SITE_NAME}.nc"
# Atmospheric forcing directory.
export A2MC_FORCING_DIR="/path/to/your/atm_forcing"

# -----------------------------------------------------------------------------
# 3. PFT CONFIGURATION
# -----------------------------------------------------------------------------
# Comma-separated, 1-based FATES PFT ids A2MC will calibrate — the ids from the
# BASE PARAMETER FILE's fates_pftname list, NOT ELM's static surfdata PFTs.
# PFT ids are NOT stable across FATES API versions: map by functional type and
# verify against the base file (feedback_verify_pft_identity_across_versions).
# Set this only for PFT-level goals; an ecosystem-flux goal (tower/MODIS GPP)
# does not need it. Example = an arctic 3-PFT set on an api-43 parameter file.
export A2MC_PFTS="10,11,12"              # evergreen shrub, deciduous shrub, graminoid (api-43 ids)

# -----------------------------------------------------------------------------
# 4. SAMPLING + PARAMETER LIST  (everything downstream derives from these)
# -----------------------------------------------------------------------------
# Scheme decides how the ensemble SIZE is computed from the parameter count —
# Morris trajectories, Sobol and LHS all differ. Change the scheme or the list,
# never a hardcoded ensemble count.
export A2MC_SAMPLING_SCHEME="morris"     # morris | lhs | sobol | custom
export A2MC_N_TRAJECTORIES=30            # Morris trajectories

# The parameter list. Its FILENAME is the only place a parameter count may appear
# as a literal (e.g. "para169"); everything below derives from the content.
#
# Ships pointing at the example list so a fresh TEMPLATE validates end to end. Replace the
# example rows with your parameters, rename it to something that identifies YOUR list
# (e.g. "${A2MC_SITE_NAME}_Parameter_List_para42.csv"), and repoint this line. The schema —
# including the ELM-only variant with no `organ` column — is documented in the file's header.
export A2MC_PARAM_LIST_FILE="${A2MC_USE_CASE_DIR}/parameters/parameter_list_template.csv"

# Parameter count, derived from the list CONTENT (authoritative, format-agnostic:
# handles the explicit-column CSV and the legacy shorthand .txt). Falls back to a
# "paraNNN" token in the filename only if the tool cannot run.
export A2MC_N_PARAMS=$(python "${A2MC_ROOT}/tools/count_param_list.py" "$A2MC_PARAM_LIST_FILE" 2>/dev/null \
    || { _p="${A2MC_PARAM_LIST_FILE##*para}"; echo "${_p%%[!0-9]*}"; })
# Fail LOUD rather than letting an empty count flow into every derived name below
# (an unnoticed empty yields an ensemble called "..._Para" and an ensemble size of 0).
if [[ -z "${A2MC_N_PARAMS}" || ! "${A2MC_N_PARAMS}" =~ ^[0-9]+$ ]]; then
    echo "WARNING: could not derive A2MC_N_PARAMS from '${A2MC_PARAM_LIST_FILE}'." >&2
    echo "         Create your parameter list first (a2mc-init / phase0-design), then re-source." >&2
    export A2MC_N_PARAMS=0
fi

# SALib problem file — regenerated by phases/phase0_design/create_parameter_sample.py.
export A2MC_SALIB_PROBLEM_FILE="${A2MC_USE_CASE_DIR}/parameters/salib_problem_para${A2MC_N_PARAMS}.txt"

# Total ensemble size — computed by scheme (Morris: N_TRAJECTORIES x (N_PARAMS+1)).
export A2MC_TOTAL_ENSEMBLE=$(calculate_ensemble_size)

# The sample matrix written by Phase 0 (rows = A2MC_TOTAL_ENSEMBLE, cols = A2MC_N_PARAMS).
export A2MC_ENSEMBLE_MATRIX_FILE="${A2MC_USE_CASE_DIR}/parameters/${A2MC_SITE_NAME}_Morris_matrix.txt"

# -----------------------------------------------------------------------------
# 5. VALIDATION TARGETS
# -----------------------------------------------------------------------------
# The LIVE target file, loaded via tools/targets_loader.py. It carries BOTH the
# targets and the scoring settings:
#   cost_config: {error_method, aggregation_method, tolerance, tolerance_type}
#   time_year / time_month: the observation window
# Those live in the YAML, NOT in env vars — older configs exported
# A2MC_ERROR_METHOD / A2MC_AGGREGATION_METHOD / A2MC_TOLERANCE /
# A2MC_VALIDATION_{START_YEAR,END_YEAR,MONTHS} / A2MC_TOP_N, and nothing reads
# them any more. Edit validation/targets.yaml instead, then:
#   python tools/validate_targets_config.py
export A2MC_VALIDATION_TARGETS="${A2MC_USE_CASE_DIR}/validation/targets.yaml"

# -----------------------------------------------------------------------------
# 6. MODEL BUILD / NAMELIST OPTIONS
# -----------------------------------------------------------------------------
# Nutrient supplementation per spin-up phase (ADSP / RGSP / TRANS). Recorded in
# calibration_rounds.yaml `protocol`. "ALL" supplements, "NONE" runs prognostic.
export A2MC_RGSP_SUPLPHOS="ALL"
# =============================================================================
# ★ RUN CONFIGURATION — set this FIRST; the rest of the file assumes FATES+CNP+ECA
# =============================================================================
# This template ships the ELM-FATES / CNP / ECA configuration. A2MC also runs ELM
# WITHOUT FATES, and FATES carbon-only. If your case is not FATES+CNP+ECA, change
# the block below AND the FATES-specific paths further down (base param file,
# param pattern, ensemble name) — they are meaningless otherwise.
#
#   (a) NOT using FATES
#       Change the `-bgc` flag; do NOT just set A2MC_USE_FATES.
#       `use_fates` is DERIVED from `-bgc` (tools/config.py), and an inconsistent
#       A2MC_USE_FATES RAISES rather than silently disagreeing:
#           export A2MC_ELM_OPTIONS="-bgc sp ..."      # or bgc / cn — ELM's default is sp
#           export A2MC_USE_FATES=".false."            # optional, an assertion only
#
#   (b) FATES, carbon-only (no nutrient cycling)
#           export A2MC_FATES_PARTEH_MODE=1            # 1 = carbon-only, 2 = CNP
#           export A2MC_USE_FATES_NOCOMP=".true."      # see the caveat below
#
# NOTE on values: these are CIME-style `.true.` / `.false.` strings. The parser
# also accepts true/1/yes/on (tools/config.py::_truthy), but match the surrounding
# style so a reader can see at a glance that these are namelist-shaped.
#
# CAVEAT on NOCOMP, do not treat it as implied by carbon-only: `use_fates_nocomp`
# means no inter-PFT competition, with PFTs in separate patches. It does NOT fix
# PFT areas and it is NOT a nutrient switch — it is an independent axis that
# happens to pair well with carbon-only runs. Verify against the FATES knowledge
# base before assuming what it does (CLAUDE.md: never infer FATES behaviour from a
# parameter's name).
# -----------------------------------------------------------------------------
# ELM build options. Drives BOTH the build and the mode-aware RAG filter.
export A2MC_ELM_OPTIONS="-bgc fates -nutrient cnp -nutrient_comp_pathway eca -soil_decomp century"
export A2MC_FATES_PARTEH_MODE=2          # 1 = carbon-only; 2 = CNP

# Tier 2 FATES feature flags (default off; set only if enabled in user_nl_elm)
#export A2MC_FATES_SPITFIRE_MODE=1        # 0 = off, 1 = lightning, 2 = + managed
#export A2MC_USE_FATES_PLANTHYDRO=true    # plant hydraulics
#export A2MC_USE_FATES_LOGGING=true       # logging mortality
#export A2MC_USE_FATES_NOCOMP=true        # PFTs in separate patches (no competition)

# -----------------------------------------------------------------------------
# 7. PARAMETER FILES (base + per-case)
# -----------------------------------------------------------------------------
# The BASE parameter file: the template every per-case file is built from. A2MC
# reads the PFT count/names from it, and every NON-calibrated parameter flows
# from it unchanged into every case — so on an API migration prefer a site-TUNED
# prior over the generic default (feedback_port_tuned_base_param_file_across_versions).
# api-43+ is JSON; older FATES uses .nc/.cdl.
export A2MC_BASE_PARAM_FILE="${A2MC_MODEL_PATH}/components/elm/src/external_models/fates/parameter_files/fates_params_default.json"

# Where the per-case parameter files are written by Phase 0. Anchor it on
# ${A2MC_OUTPUT_ROOT} (machine-level) — never a literal /global/... or /home/...
# path, and include the round token so two rounds cannot overwrite each other.
export A2MC_PARAM_DIR="${A2MC_OUTPUT_ROOT}/ParameterFiles/${A2MC_SITE_NAME}_para${A2MC_N_PARAMS}_Morris"
# Per-case filename pattern; {N} = case number. Include the round token too.
export A2MC_PARAM_PATTERN="fates_params_${A2MC_SITE_NAME}_para${A2MC_N_PARAMS}_En{N}.json"

# -----------------------------------------------------------------------------
# 8. ENSEMBLE NAMING + OUTPUT PATHS
# -----------------------------------------------------------------------------
# Name THIS round's ensemble so it identifies the config AND the round; the
# param count derives, so a new list automatically yields a new name.
export A2MC_ENSEMBLE_NAME="${A2MC_SITE_NAME}_FATESapi43_CNPECA_Para${A2MC_N_PARAMS}"
export A2MC_ENSEMBLE_PREFIX="${A2MC_SITE_NAME}_ELM-FATES"
# {N} = member index, {PHASE} = spin-up phase (ADSP/RGSP/TRANS).
export A2MC_CASE_NAME_PATTERN="${A2MC_ENSEMBLE_PREFIX}_PtCNPEn{N}_{PHASE}"
export A2MC_ENSEMBLE_OUTPUT="${A2MC_OUTPUT_ROOT}/${A2MC_ENSEMBLE_NAME}"
export A2MC_EXTRACTED_DATA="${A2MC_OUTPUT_ROOT}/${A2MC_ENSEMBLE_NAME}_Extract"
# CIME case scripts + run logs. Anchor on ${A2MC_SCRIPTS_DIR}; include the round
# token so a new round does not build into the previous round's tree.
export A2MC_CASE_SCRIPTS="${A2MC_SCRIPTS_DIR}/${A2MC_ENSEMBLE_NAME}"
export A2MC_LOG_DIR="${A2MC_CASE_SCRIPTS}"

# -----------------------------------------------------------------------------
# 9. HISTORY OUTPUT VARIABLES
# -----------------------------------------------------------------------------
# Size x PFT (SZPF) history fields written into user_nl_elm. Trim to what your
# targets and diagnostics actually need — every field costs disk on a large
# ensemble. This minimal set covers biomass + N/P pools per PFT.
export A2MC_HIST_SZPF_VARS="'FATES_VEGC_ABOVEGROUND_SZPF','FATES_LEAFC_SZPF','FATES_FROOTC_SZPF','FATES_STOREC_SZPF','FATES_NPP_SZPF'"

# -----------------------------------------------------------------------------
# 10. OPTIONAL — case-dir enrichment for mode-aware retrieval
# -----------------------------------------------------------------------------
# ConfigMode resolves: env vars (above, = user INTENT) > case dir > ELM defaults.
# A case dir adds Tier 2 use_fates_* flags from user_nl_elm/lnd_in. Any one
# ensemble member works as the reference (members differ only in param file).
#export A2MC_CASE_DIR="${A2MC_E3SM_ROOT}/cime/scripts/${A2MC_ENSEMBLE_PREFIX}_PtCNPEn1_TRANS"
#export A2MC_CASE_NAME="${A2MC_ENSEMBLE_PREFIX}_PtCNPEn1_TRANS"
# If neither is set, the env-vars-only path is used (still fully supported).
# See docs/a2mc_reference/mode_aware_workflow.md.

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo "=== A2MC site config: ${A2MC_SITE_NAME} ==="
echo "  Use case dir:  ${A2MC_USE_CASE_DIR}"
echo "  PFTs (FATES):  ${A2MC_PFTS:-(unset — ecosystem-level goal?)}"
echo "  Param list:    $(basename "${A2MC_PARAM_LIST_FILE}") (${A2MC_N_PARAMS} params)"
echo "  Sampling:      ${A2MC_SAMPLING_SCHEME}, ${A2MC_N_TRAJECTORIES} trajectories -> ${A2MC_TOTAL_ENSEMBLE} cases"
echo "  Ensemble:      ${A2MC_ENSEMBLE_NAME:-(unset)}"
echo "  ELM_OPTIONS:   ${A2MC_ELM_OPTIONS}"
echo "  PARTEH mode:   ${A2MC_FATES_PARTEH_MODE}"
echo "  Case dir:      ${A2MC_CASE_DIR:-(unset; using env-vars-only path)}"
