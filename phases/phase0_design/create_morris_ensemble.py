#!/usr/bin/env python3
"""
Create FATES Parameter Files from Sampling Ensemble

This script reads a sampling ensemble matrix and creates individual FATES
parameter NetCDF files for each parameter set.

Uses the existing modify_fates_parameters.py for parameter modifications.

Key features:
1. Handles PFT-specific parameters
2. Handles special 2D parameters (organ × PFT) for retrans and stoich
3. fates_cnp_nfix1 is ONLY for PFT#9 (ignored for PFT#7 and #10)
4. Ensures fates_leaf_slamax >= fates_leaf_slatop
5. Sets fates_cnp_prescribed_puptake and fates_cnp_prescribed_nuptake to 0

Configuration is loaded from environment variables (source a2mc_config.sh).

Reference:
    - Parameter list: A2MC_PARAM_LIST_FILE
    - Ensemble matrix: A2MC_ENSEMBLE_MATRIX_FILE

Created: December 30, 2025
"""

import numpy as np
import netCDF4 as nc
import shutil
from pathlib import Path
import sys
from datetime import datetime

# Import from shared tools
from tools.modify_fates_parameters import create_modified_parameter_file

# ============================================================================
# CONFIGURATION - Loaded from environment/config
# ============================================================================

import os

try:
    from tools.config import config
    ENSEMBLE_MATRIX_FILE = Path(config.ENSEMBLE_MATRIX_FILE)
    BASE_PARAM_FILE = Path(config.BASE_PARAM_FILE)
    OUTPUT_DIR = Path(config.PARAM_DIR)
    EXPECTED_N_PARAMS = config.N_PARAMS
    EXPECTED_N_SETS = config.TOTAL_ENSEMBLE
except ImportError:
    # Fallback to environment variables
    ENSEMBLE_MATRIX_FILE = Path(os.environ.get('A2MC_ENSEMBLE_MATRIX_FILE', ''))
    BASE_PARAM_FILE = Path(os.environ.get('A2MC_BASE_PARAM_FILE', ''))
    OUTPUT_DIR = Path(os.environ.get('A2MC_PARAM_DIR', ''))
    EXPECTED_N_PARAMS = int(os.environ.get('A2MC_N_PARAMS', '0'))
    EXPECTED_N_SETS = int(os.environ.get('A2MC_TOTAL_ENSEMBLE', '0'))

# Organ indices (1-based for modify_fates_parameters.py)
ORGAN_LEAF = 1
ORGAN_FINEROOT = 2

# ============================================================================
# PARAMETER MAPPING
# ============================================================================

def build_modifications_list(param_values):
    """
    Build a list of modifications for create_modified_parameter_file().

    Parameters:
    -----------
    param_values : array
        1D array of 162 parameter values from Morris ensemble

    Returns:
    --------
    modifications : list of dict
        List of modifications in format expected by create_modified_parameter_file()
    """
    modifications = []

    # =========================================================================
    # Columns 1-18: PFT#7 CNP parameters (0-based: 0-17)
    # =========================================================================
    modifications.extend([
        {'param': 'fates_cnp_eca_alpha_ptase', 'pft': 7, 'value': param_values[0]},
        {'param': 'fates_cnp_eca_decompmicc', 'pft': 7, 'value': param_values[1]},
        {'param': 'fates_cnp_eca_km_nh4', 'pft': 7, 'value': param_values[2]},
        {'param': 'fates_cnp_eca_km_no3', 'pft': 7, 'value': param_values[3]},
        {'param': 'fates_cnp_eca_km_p', 'pft': 7, 'value': param_values[4]},
        {'param': 'fates_cnp_eca_km_ptase', 'pft': 7, 'value': param_values[5]},
        {'param': 'fates_cnp_vmax_nh4', 'pft': 7, 'value': param_values[6]},
        {'param': 'fates_cnp_vmax_no3', 'pft': 7, 'value': param_values[7]},
        {'param': 'fates_cnp_vmax_p', 'pft': 7, 'value': param_values[8]},
        {'param': 'fates_cnp_eca_vmax_ptase', 'pft': 7, 'value': param_values[9]},
        {'param': 'fates_cnp_pid_kp', 'pft': 7, 'value': param_values[10]},
        {'param': 'fates_allom_l2fr', 'pft': 7, 'value': param_values[11]},
        # nitr_retrans: both organs
        {'param': 'fates_cnp_turnover_nitr_retrans', 'pft': 7, 'organ': ORGAN_LEAF, 'value': param_values[12]},
        {'param': 'fates_cnp_turnover_nitr_retrans', 'pft': 7, 'organ': ORGAN_FINEROOT, 'value': param_values[12]},
        # phos_retrans: both organs
        {'param': 'fates_cnp_turnover_phos_retrans', 'pft': 7, 'organ': ORGAN_LEAF, 'value': param_values[13]},
        {'param': 'fates_cnp_turnover_phos_retrans', 'pft': 7, 'organ': ORGAN_FINEROOT, 'value': param_values[13]},
        # stoich: separate leaf and fineroot
        {'param': 'fates_stoich_nitr', 'pft': 7, 'organ': ORGAN_LEAF, 'value': param_values[14]},
        {'param': 'fates_stoich_phos', 'pft': 7, 'organ': ORGAN_LEAF, 'value': param_values[15]},
        {'param': 'fates_stoich_nitr', 'pft': 7, 'organ': ORGAN_FINEROOT, 'value': param_values[16]},
        {'param': 'fates_stoich_phos', 'pft': 7, 'organ': ORGAN_FINEROOT, 'value': param_values[17]},
    ])

    # =========================================================================
    # Columns 19-37: PFT#9 CNP parameters (0-based: 18-36)
    # =========================================================================
    modifications.extend([
        {'param': 'fates_cnp_eca_alpha_ptase', 'pft': 9, 'value': param_values[18]},
        {'param': 'fates_cnp_eca_decompmicc', 'pft': 9, 'value': param_values[19]},
        {'param': 'fates_cnp_eca_km_nh4', 'pft': 9, 'value': param_values[20]},
        {'param': 'fates_cnp_eca_km_no3', 'pft': 9, 'value': param_values[21]},
        {'param': 'fates_cnp_eca_km_p', 'pft': 9, 'value': param_values[22]},
        {'param': 'fates_cnp_eca_km_ptase', 'pft': 9, 'value': param_values[23]},
        {'param': 'fates_cnp_vmax_nh4', 'pft': 9, 'value': param_values[24]},
        {'param': 'fates_cnp_vmax_no3', 'pft': 9, 'value': param_values[25]},
        {'param': 'fates_cnp_vmax_p', 'pft': 9, 'value': param_values[26]},
        {'param': 'fates_cnp_eca_vmax_ptase', 'pft': 9, 'value': param_values[27]},
        {'param': 'fates_cnp_pid_kp', 'pft': 9, 'value': param_values[28]},
        {'param': 'fates_allom_l2fr', 'pft': 9, 'value': param_values[29]},
        # nfix1: ONLY for PFT#9!
        {'param': 'fates_cnp_nfix1', 'pft': 9, 'value': param_values[30]},
        # nitr_retrans: both organs
        {'param': 'fates_cnp_turnover_nitr_retrans', 'pft': 9, 'organ': ORGAN_LEAF, 'value': param_values[31]},
        {'param': 'fates_cnp_turnover_nitr_retrans', 'pft': 9, 'organ': ORGAN_FINEROOT, 'value': param_values[31]},
        # phos_retrans: both organs
        {'param': 'fates_cnp_turnover_phos_retrans', 'pft': 9, 'organ': ORGAN_LEAF, 'value': param_values[32]},
        {'param': 'fates_cnp_turnover_phos_retrans', 'pft': 9, 'organ': ORGAN_FINEROOT, 'value': param_values[32]},
        # stoich: separate leaf and fineroot
        {'param': 'fates_stoich_nitr', 'pft': 9, 'organ': ORGAN_LEAF, 'value': param_values[33]},
        {'param': 'fates_stoich_phos', 'pft': 9, 'organ': ORGAN_LEAF, 'value': param_values[34]},
        {'param': 'fates_stoich_nitr', 'pft': 9, 'organ': ORGAN_FINEROOT, 'value': param_values[35]},
        {'param': 'fates_stoich_phos', 'pft': 9, 'organ': ORGAN_FINEROOT, 'value': param_values[36]},
    ])

    # =========================================================================
    # Columns 38-55: PFT#10 CNP parameters (0-based: 37-54)
    # =========================================================================
    modifications.extend([
        {'param': 'fates_cnp_eca_alpha_ptase', 'pft': 10, 'value': param_values[37]},
        {'param': 'fates_cnp_eca_decompmicc', 'pft': 10, 'value': param_values[38]},
        {'param': 'fates_cnp_eca_km_nh4', 'pft': 10, 'value': param_values[39]},
        {'param': 'fates_cnp_eca_km_no3', 'pft': 10, 'value': param_values[40]},
        {'param': 'fates_cnp_eca_km_p', 'pft': 10, 'value': param_values[41]},
        {'param': 'fates_cnp_eca_km_ptase', 'pft': 10, 'value': param_values[42]},
        {'param': 'fates_cnp_vmax_nh4', 'pft': 10, 'value': param_values[43]},
        {'param': 'fates_cnp_vmax_no3', 'pft': 10, 'value': param_values[44]},
        {'param': 'fates_cnp_vmax_p', 'pft': 10, 'value': param_values[45]},
        {'param': 'fates_cnp_eca_vmax_ptase', 'pft': 10, 'value': param_values[46]},
        {'param': 'fates_cnp_pid_kp', 'pft': 10, 'value': param_values[47]},
        {'param': 'fates_allom_l2fr', 'pft': 10, 'value': param_values[48]},
        # nitr_retrans: both organs
        {'param': 'fates_cnp_turnover_nitr_retrans', 'pft': 10, 'organ': ORGAN_LEAF, 'value': param_values[49]},
        {'param': 'fates_cnp_turnover_nitr_retrans', 'pft': 10, 'organ': ORGAN_FINEROOT, 'value': param_values[49]},
        # phos_retrans: both organs
        {'param': 'fates_cnp_turnover_phos_retrans', 'pft': 10, 'organ': ORGAN_LEAF, 'value': param_values[50]},
        {'param': 'fates_cnp_turnover_phos_retrans', 'pft': 10, 'organ': ORGAN_FINEROOT, 'value': param_values[50]},
        # stoich: separate leaf and fineroot
        {'param': 'fates_stoich_nitr', 'pft': 10, 'organ': ORGAN_LEAF, 'value': param_values[51]},
        {'param': 'fates_stoich_phos', 'pft': 10, 'organ': ORGAN_LEAF, 'value': param_values[52]},
        {'param': 'fates_stoich_nitr', 'pft': 10, 'organ': ORGAN_FINEROOT, 'value': param_values[53]},
        {'param': 'fates_stoich_phos', 'pft': 10, 'organ': ORGAN_FINEROOT, 'value': param_values[54]},
    ])

    # =========================================================================
    # Columns 56-81: PFT#7 Plant Trait parameters (0-based: 55-80)
    # =========================================================================
    modifications.extend([
        {'param': 'fates_allom_d2bl1', 'pft': 7, 'value': param_values[55]},
        {'param': 'fates_allom_d2bl2', 'pft': 7, 'value': param_values[56]},
        {'param': 'fates_allom_agb2', 'pft': 7, 'value': param_values[57]},
        {'param': 'fates_allom_agb3', 'pft': 7, 'value': param_values[58]},
        {'param': 'fates_allom_d2h1', 'pft': 7, 'value': param_values[59]},
        {'param': 'fates_allom_d2h2', 'pft': 7, 'value': param_values[60]},
        {'param': 'fates_recruit_height_min', 'pft': 7, 'value': param_values[61]},
        {'param': 'fates_allom_dbh_maxheight', 'pft': 7, 'value': param_values[62]},
        {'param': 'fates_allom_d2ca_coefficient_min', 'pft': 7, 'value': param_values[63]},
        {'param': 'fates_alloc_store_priority_frac', 'pft': 7, 'value': param_values[64]},
        {'param': 'fates_alloc_storage_cushion', 'pft': 7, 'value': param_values[65]},
        {'param': 'fates_leaf_slatop', 'pft': 7, 'value': param_values[66]},
        {'param': 'fates_leaf_vcmax25top', 'pft': 7, 'value': param_values[67]},
        {'param': 'fates_grperc', 'pft': 7, 'value': param_values[68]},
        {'param': 'fates_mort_scalar_hydrfailure', 'pft': 7, 'value': param_values[69]},
        {'param': 'fates_mort_scalar_cstarvation', 'pft': 7, 'value': param_values[70]},
        {'param': 'fates_mort_scalar_coldstress', 'pft': 7, 'value': param_values[71]},
        {'param': 'fates_mort_bmort', 'pft': 7, 'value': param_values[72]},
        {'param': 'fates_mort_hf_sm_threshold', 'pft': 7, 'value': param_values[73]},
        {'param': 'fates_mort_freezetol', 'pft': 7, 'value': param_values[74]},
        {'param': 'fates_recruit_seed_alloc', 'pft': 7, 'value': param_values[75]},
        {'param': 'fates_frag_seed_decay_rate', 'pft': 7, 'value': param_values[76]},
        {'param': 'fates_recruit_seed_germination_rate', 'pft': 7, 'value': param_values[77]},
        {'param': 'fates_recruit_seed_supplement', 'pft': 7, 'value': param_values[78]},
        {'param': 'fates_recruit_init_density', 'pft': 7, 'value': param_values[79]},
        {'param': 'fates_phen_mindaysoff', 'pft': 7, 'value': param_values[80]},
    ])

    # =========================================================================
    # Columns 82-107: PFT#9 Plant Trait parameters (0-based: 81-106)
    # =========================================================================
    modifications.extend([
        {'param': 'fates_allom_d2bl1', 'pft': 9, 'value': param_values[81]},
        {'param': 'fates_allom_d2bl2', 'pft': 9, 'value': param_values[82]},
        {'param': 'fates_allom_agb2', 'pft': 9, 'value': param_values[83]},
        {'param': 'fates_allom_agb3', 'pft': 9, 'value': param_values[84]},
        {'param': 'fates_allom_d2h1', 'pft': 9, 'value': param_values[85]},
        {'param': 'fates_allom_d2h2', 'pft': 9, 'value': param_values[86]},
        {'param': 'fates_recruit_height_min', 'pft': 9, 'value': param_values[87]},
        {'param': 'fates_allom_dbh_maxheight', 'pft': 9, 'value': param_values[88]},
        {'param': 'fates_allom_d2ca_coefficient_min', 'pft': 9, 'value': param_values[89]},
        {'param': 'fates_alloc_store_priority_frac', 'pft': 9, 'value': param_values[90]},
        {'param': 'fates_alloc_storage_cushion', 'pft': 9, 'value': param_values[91]},
        {'param': 'fates_leaf_slatop', 'pft': 9, 'value': param_values[92]},
        {'param': 'fates_leaf_vcmax25top', 'pft': 9, 'value': param_values[93]},
        {'param': 'fates_grperc', 'pft': 9, 'value': param_values[94]},
        {'param': 'fates_mort_scalar_hydrfailure', 'pft': 9, 'value': param_values[95]},
        {'param': 'fates_mort_scalar_cstarvation', 'pft': 9, 'value': param_values[96]},
        {'param': 'fates_mort_scalar_coldstress', 'pft': 9, 'value': param_values[97]},
        {'param': 'fates_mort_bmort', 'pft': 9, 'value': param_values[98]},
        {'param': 'fates_mort_hf_sm_threshold', 'pft': 9, 'value': param_values[99]},
        {'param': 'fates_mort_freezetol', 'pft': 9, 'value': param_values[100]},
        {'param': 'fates_recruit_seed_alloc', 'pft': 9, 'value': param_values[101]},
        {'param': 'fates_frag_seed_decay_rate', 'pft': 9, 'value': param_values[102]},
        {'param': 'fates_recruit_seed_germination_rate', 'pft': 9, 'value': param_values[103]},
        {'param': 'fates_recruit_seed_supplement', 'pft': 9, 'value': param_values[104]},
        {'param': 'fates_recruit_init_density', 'pft': 9, 'value': param_values[105]},
        {'param': 'fates_phen_mindaysoff', 'pft': 9, 'value': param_values[106]},
    ])

    # =========================================================================
    # Columns 108-133: PFT#10 Plant Trait parameters (0-based: 107-132)
    # =========================================================================
    modifications.extend([
        {'param': 'fates_allom_d2bl1', 'pft': 10, 'value': param_values[107]},
        {'param': 'fates_allom_d2bl2', 'pft': 10, 'value': param_values[108]},
        {'param': 'fates_allom_agb2', 'pft': 10, 'value': param_values[109]},
        {'param': 'fates_allom_agb3', 'pft': 10, 'value': param_values[110]},
        {'param': 'fates_allom_d2h1', 'pft': 10, 'value': param_values[111]},
        {'param': 'fates_allom_d2h2', 'pft': 10, 'value': param_values[112]},
        {'param': 'fates_recruit_height_min', 'pft': 10, 'value': param_values[113]},
        {'param': 'fates_allom_dbh_maxheight', 'pft': 10, 'value': param_values[114]},
        {'param': 'fates_allom_d2ca_coefficient_min', 'pft': 10, 'value': param_values[115]},
        {'param': 'fates_alloc_store_priority_frac', 'pft': 10, 'value': param_values[116]},
        {'param': 'fates_alloc_storage_cushion', 'pft': 10, 'value': param_values[117]},
        {'param': 'fates_leaf_slatop', 'pft': 10, 'value': param_values[118]},
        {'param': 'fates_leaf_vcmax25top', 'pft': 10, 'value': param_values[119]},
        {'param': 'fates_grperc', 'pft': 10, 'value': param_values[120]},
        {'param': 'fates_mort_scalar_hydrfailure', 'pft': 10, 'value': param_values[121]},
        {'param': 'fates_mort_scalar_cstarvation', 'pft': 10, 'value': param_values[122]},
        {'param': 'fates_mort_scalar_coldstress', 'pft': 10, 'value': param_values[123]},
        {'param': 'fates_mort_bmort', 'pft': 10, 'value': param_values[124]},
        {'param': 'fates_mort_hf_sm_threshold', 'pft': 10, 'value': param_values[125]},
        {'param': 'fates_mort_freezetol', 'pft': 10, 'value': param_values[126]},
        {'param': 'fates_recruit_seed_alloc', 'pft': 10, 'value': param_values[127]},
        {'param': 'fates_frag_seed_decay_rate', 'pft': 10, 'value': param_values[128]},
        {'param': 'fates_recruit_seed_germination_rate', 'pft': 10, 'value': param_values[129]},
        {'param': 'fates_recruit_seed_supplement', 'pft': 10, 'value': param_values[130]},
        {'param': 'fates_recruit_init_density', 'pft': 10, 'value': param_values[131]},
        {'param': 'fates_phen_mindaysoff', 'pft': 10, 'value': param_values[132]},
    ])

    # =========================================================================
    # Columns 134-138: Shared parameters (0-based: 133-137)
    # Apply to ALL PFTs for PFT-dependent ones, or as scalar for scalar params
    # =========================================================================
    # maintresp_nonleaf_baserate: apply to all 12 PFTs
    for pft in range(1, 13):
        modifications.append({'param': 'fates_maintresp_nonleaf_baserate', 'pft': pft, 'value': param_values[133]})

    # Phenology parameters: scalars (applied to all PFTs in MATLAB, here as pft=0)
    # Note: These may be scalar in NetCDF, need to check. For safety, apply to all PFTs if PFT-dependent
    modifications.extend([
        {'param': 'fates_phen_chilltemp', 'pft': 0, 'value': param_values[134]},
        {'param': 'fates_phen_coldtemp', 'pft': 0, 'value': param_values[135]},
        {'param': 'fates_phen_ncolddayslim', 'pft': 0, 'value': param_values[136]},
        {'param': 'fates_phen_gddthresh_c', 'pft': 0, 'value': param_values[137]},
    ])

    # =========================================================================
    # Columns 139-162: NEW parameters (0-based: 138-161)
    # =========================================================================
    # Turnover parameters
    modifications.extend([
        {'param': 'fates_turnover_fnrt', 'pft': 7, 'value': param_values[138]},
        {'param': 'fates_turnover_fnrt', 'pft': 9, 'value': param_values[139]},
        {'param': 'fates_turnover_fnrt', 'pft': 10, 'value': param_values[140]},
        {'param': 'fates_turnover_leaf', 'pft': 7, 'value': param_values[141]},
        {'param': 'fates_turnover_leaf', 'pft': 9, 'value': param_values[142]},
        {'param': 'fates_turnover_leaf', 'pft': 10, 'value': param_values[143]},
    ])

    # Root distribution parameters
    modifications.extend([
        {'param': 'fates_allom_fnrt_prof_a', 'pft': 7, 'value': param_values[144]},
        {'param': 'fates_allom_fnrt_prof_a', 'pft': 9, 'value': param_values[145]},
        {'param': 'fates_allom_fnrt_prof_a', 'pft': 10, 'value': param_values[146]},
        {'param': 'fates_allom_fnrt_prof_b', 'pft': 7, 'value': param_values[147]},
        {'param': 'fates_allom_fnrt_prof_b', 'pft': 9, 'value': param_values[148]},
        {'param': 'fates_allom_fnrt_prof_b', 'pft': 10, 'value': param_values[149]},
    ])

    # PID gains
    modifications.extend([
        {'param': 'fates_cnp_pid_ki', 'pft': 7, 'value': param_values[150]},
        {'param': 'fates_cnp_pid_ki', 'pft': 9, 'value': param_values[151]},
        {'param': 'fates_cnp_pid_ki', 'pft': 10, 'value': param_values[152]},
        {'param': 'fates_cnp_pid_kd', 'pft': 7, 'value': param_values[153]},
        {'param': 'fates_cnp_pid_kd', 'pft': 9, 'value': param_values[154]},
        {'param': 'fates_cnp_pid_kd', 'pft': 10, 'value': param_values[155]},
    ])

    # Storage ratios
    modifications.extend([
        {'param': 'fates_cnp_phos_store_ratio', 'pft': 7, 'value': param_values[156]},
        {'param': 'fates_cnp_phos_store_ratio', 'pft': 9, 'value': param_values[157]},
        {'param': 'fates_cnp_phos_store_ratio', 'pft': 10, 'value': param_values[158]},
        {'param': 'fates_cnp_nitr_store_ratio', 'pft': 7, 'value': param_values[159]},
        {'param': 'fates_cnp_nitr_store_ratio', 'pft': 9, 'value': param_values[160]},
        {'param': 'fates_cnp_nitr_store_ratio', 'pft': 10, 'value': param_values[161]},
    ])

    return modifications


def apply_post_modifications(output_file, param_values):
    """
    Apply post-processing modifications:
    1. Ensure fates_leaf_slamax >= fates_leaf_slatop for each PFT
    2. Set fates_cnp_prescribed_puptake and fates_cnp_prescribed_nuptake to 0

    Parameters:
    -----------
    output_file : Path
        Path to the output NetCDF file
    param_values : array
        Original parameter values (to get slatop values)
    """
    with nc.Dataset(output_file, 'r+') as ncfile:
        # slatop column indices (0-based): 66 for PFT7, 92 for PFT9, 118 for PFT10
        slatop_cols = {7: 66, 9: 92, 10: 118}
        pft_indices = {7: 6, 9: 8, 10: 9}  # 0-based indices

        for pft, col in slatop_cols.items():
            pft_idx = pft_indices[pft]
            slatop_val = param_values[col]
            slamax_val = float(ncfile.variables['fates_leaf_slamax'][pft_idx])

            if slamax_val < slatop_val:
                ncfile.variables['fates_leaf_slamax'][pft_idx] = slatop_val

        # Set prescribed uptake to 0
        ncfile.variables['fates_cnp_prescribed_puptake'][:] = 0.0
        ncfile.variables['fates_cnp_prescribed_nuptake'][:] = 0.0


def create_single_parameter_file(base_file, output_file, param_values, verbose=False):
    """
    Create a single parameter file with the given parameter values.

    Parameters:
    -----------
    base_file : Path
        Path to base FATES parameter file
    output_file : Path
        Path to output file
    param_values : array
        1D array of 162 parameter values
    verbose : bool
        Print details
    """
    # Build modifications list
    modifications = build_modifications_list(param_values)

    # Create modified parameter file using existing function
    create_modified_parameter_file(base_file, output_file, modifications, verbose=verbose)

    # Apply post-processing
    apply_post_modifications(output_file, param_values)


def main():
    """Main function to create parameter files from ensemble matrix."""

    print("=" * 80)
    print("CREATE FATES PARAMETER FILES FROM SAMPLING ENSEMBLE")
    print("=" * 80)
    print(f"\nStart time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Verify configuration
    if not ENSEMBLE_MATRIX_FILE or not str(ENSEMBLE_MATRIX_FILE):
        print("ERROR: A2MC_ENSEMBLE_MATRIX_FILE not set. Source config first.")
        sys.exit(1)

    # Verify input files exist
    print(f"\n--- Input Files ---")
    print(f"Ensemble matrix: {ENSEMBLE_MATRIX_FILE}")
    print(f"Base param file: {BASE_PARAM_FILE}")

    if not ENSEMBLE_MATRIX_FILE.exists():
        print(f"ERROR: Ensemble matrix file not found!")
        sys.exit(1)
    if not BASE_PARAM_FILE.exists():
        print(f"ERROR: Base parameter file not found!")
        sys.exit(1)

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\nOutput directory: {OUTPUT_DIR}")

    # Load ensemble matrix
    print(f"\n--- Loading Ensemble Matrix ---")
    ensemble = np.loadtxt(ENSEMBLE_MATRIX_FILE)
    n_sets, n_params = ensemble.shape
    print(f"Loaded: {n_sets} parameter sets × {n_params} parameters")

    if EXPECTED_N_PARAMS > 0 and n_params != EXPECTED_N_PARAMS:
        print(f"ERROR: Expected {EXPECTED_N_PARAMS} parameters, got {n_params}")
        sys.exit(1)
    if EXPECTED_N_SETS > 0 and n_sets != EXPECTED_N_SETS:
        print(f"WARNING: Expected {EXPECTED_N_SETS} parameter sets, got {n_sets}")

    # Create parameter files
    print(f"\n--- Creating Parameter Files ---")
    print(f"Creating {n_sets} parameter files...")

    # Progress tracking
    progress_interval = max(1, n_sets // 20)  # Report every 5%

    for i in range(n_sets):
        # Parameter set ID (1-based)
        set_id = i + 1

        # Output filename
        output_file = OUTPUT_DIR / f"fates_params_api25.5.0_12pft_c230710__PtCNP162_En{set_id}.nc"

        # Create parameter file
        create_single_parameter_file(
            BASE_PARAM_FILE,
            output_file,
            ensemble[i, :],
            verbose=False
        )

        # Progress report
        if (i + 1) % progress_interval == 0 or i == 0 or i == n_sets - 1:
            pct = (i + 1) / n_sets * 100
            print(f"  Progress: {i+1}/{n_sets} ({pct:.1f}%) - {output_file.name}")

    # Verification
    print(f"\n--- Verification ---")
    n_files = len(list(OUTPUT_DIR.glob("*.nc")))
    print(f"Created {n_files} parameter files")

    if n_files == n_sets:
        print("SUCCESS: All parameter files created!")
    else:
        print(f"WARNING: Expected {n_sets} files, found {n_files}")

    # Sample verification: check first and last file
    print(f"\n--- Sample Verification (first and last files) ---")
    PFT7, PFT9, PFT10 = 6, 8, 9  # 0-based indices
    for check_id in [1, n_sets]:
        check_file = OUTPUT_DIR / f"fates_params_api25.5.0_12pft_c230710__PtCNP162_En{check_id}.nc"
        if check_file.exists():
            with nc.Dataset(check_file, 'r') as ncf:
                # Check a few parameter values
                val1 = float(ncf.variables['fates_cnp_eca_alpha_ptase'][PFT7])
                val2 = float(ncf.variables['fates_alloc_storage_cushion'][PFT10])
                val3 = float(ncf.variables['fates_cnp_prescribed_puptake'][0])
                print(f"  File {check_id}:")
                print(f"    alpha_ptase[PFT7] = {val1:.6g} (expected: {ensemble[check_id-1, 0]:.6g})")
                print(f"    storage_cushion[PFT10] = {val2:.6g} (expected: {ensemble[check_id-1, 117]:.6g})")
                print(f"    prescribed_puptake = {val3:.6g} (expected: 0.0)")

    print(f"\n--- Complete ---")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nOutput directory: {OUTPUT_DIR}")
    print(f"Total files: {n_files}")


if __name__ == '__main__':
    main()
