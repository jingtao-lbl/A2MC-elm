#!/usr/bin/env python3
"""
Extract All Variables from Monthly ELM-FATES Output (Comprehensive)
Based on extract_monthly_variables_comprehensive_case.py

Purpose: Extract all variable types from monthly output files (one script for all dimensions)
  - 1D: Site-level time series (time, lndgrid)
  - 2D-PFT: PFT-level time series (time, fates_levpft, lndgrid)
  - 2D-SZPF: Size×PFT time series (time, fates_levscpf, lndgrid)

File Structure:
  - Input: Yearly files with 12 monthly timesteps (e.g., 2000-2019)
  - Output: NetCDF with all variables (CSV for 1D/PFT only, NetCDF for all including SZPF)

Usage:
cd /global/homes/j/jingtao/Program/PythonScripts
module load python

# Extract specific cases
python extract_monthly_variables_FATES.py --cases 845 2678 2675

# Or from case file
python extract_monthly_variables_FATES.py --case-file case_numbers.txt
python extract_monthly_variables_FATES.py --cases 845_exp1 845_exp2 845_exp3 845_exp4 845_exp5

python extract_monthly_variables_FATES.py --cases 2678_phen2675stc3pidfix 
python extract_monthly_variables_FATES.py --cases 2678_phen2675stc3pidfix_turnover5 

Author: Jing Tao
Date: December 12, 2025
Updated: December 14, 2025 - Added --cases argument for specific case numbers
"""

import numpy as np
import pandas as pd
import xarray as xr
from pathlib import Path
from datetime import datetime
import argparse
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION - loaded from a2mc_config.sh via environment variables
# Source a2mc_config.sh before running: source a2mc_config.sh
# ============================================================================
import os

try:
    from config import config
    BASE_INPUT_DIR = Path(config.ENSEMBLE_OUTPUT) if config.ENSEMBLE_OUTPUT else None
    OUTPUT_DIR = Path(config.EXTRACTED_DATA) if config.EXTRACTED_DATA else None
except ImportError:
    # Fallback to environment variables (no hardcoded defaults)
    _ensemble_output = os.environ.get('A2MC_ENSEMBLE_OUTPUT', '')
    _extracted_data = os.environ.get('A2MC_EXTRACTED_DATA', '')
    BASE_INPUT_DIR = Path(_ensemble_output) if _ensemble_output else None
    OUTPUT_DIR = Path(_extracted_data) if _extracted_data else None

# Validate configuration
if not BASE_INPUT_DIR or not OUTPUT_DIR:
    print("WARNING: A2MC_ENSEMBLE_OUTPUT or A2MC_EXTRACTED_DATA not set.")
    print("         Source a2mc_config.sh and site config before running.")
else:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Years to process
#START_YEAR = 1
#END_YEAR = 200
#CASE_SUFFIX = 'ADSP'

#START_YEAR = 201
#END_YEAR = 400
#CASE_SUFFIX = 'RGSP'

START_YEAR = 1901
##START_YEAR = 2000
END_YEAR = 2019
CASE_SUFFIX = 'TRANS'

# Suffix for modified cases
#CASE_SUFFIX = 'mod_phen_stc3_TRANS'
#CASE_SUFFIX = 'mod_phen_stc3pid_TRANS'
#CASE_SUFFIX = 'TRANS'

# PFT indices of interest (0-indexed in arrays)
PFT_INDICES = {
    'PFT7': 6,   # Evergreen Shrub
    'PFT9': 8,   # Arctic Deciduous Shrub
    'PFT10': 9   # Arctic Graminoid
}

# ============================================================================
# VARIABLE DEFINITIONS
# ============================================================================

# ======= 1D VARIABLES (time, lndgrid) =======
SITE_LEVEL_VARS = [
    # === PHENOLOGY ===
    'FATES_TVEG24',           # 24-hour mean vegetation temperature
    'TV',                     # Instantaneous vegetation temperature
    'FATES_GDD',             # Growing degree days
    'FATES_COLD_STATUS',     # Cold status indicator
    'FATES_NCHILLDAYS',      # Number of chill days
    'FATES_NCOLDDAYS',       # Number of cold days
    'FATES_DAYSINCE_COLDLEAFON',   # Days since cold leaf flush
    'FATES_DAYSINCE_COLDLEAFOFF',  # Days since cold leaf drop

    # === BIOMASS POOLS ===
    'FATES_LAI',             # Leaf area index
    'FATES_VEGC',            # Total vegetation carbon
    'FATES_VEGN',            # Total vegetation nitrogen
    'FATES_VEGP',            # Total vegetation phosphorus
    'FATES_LEAFC',           # Leaf carbon
    'FATES_FROOTC',          # Fine root carbon
    'FATES_STOREC',          # Storage carbon
    'FATES_STOREN',          # Storage nitrogen
    'FATES_STOREP',          # Storage phosphorus
    'FATES_SAPWOODC',
    'FATES_SAPWOODN',
    'FATES_SAPWOODP',
    'FATES_NFIX_SYM',        # Symbiotic N fixation

    # === CARBON FLUXES ===
    'FATES_GPP',             # Gross primary production
    'FATES_NPP',             # Net primary production
    'FATES_AUTORESP',        # Autotrophic respiration
    'FATES_MAINT_RESP',      # Maintenance respiration
    'FATES_GROWTH_RESP',     # Growth respiration

    # === ALLOCATION FLUXES ===
    'FATES_LEAF_ALLOC',      # Allocation to leaves
    'FATES_FROOT_ALLOC',     # Allocation to fine-roots
    'FATES_STORE_ALLOC',     # Allocation to storage
    'FATES_SEED_ALLOC',      # Allocation to seeds
    'FATES_STEM_ALLOC',      # Allocation to stem
    'FATES_CROOT_ALLOC',     # Allocation to coarse roots

    # === DYNAMIC ALLOCATION STATE ===
    'FATES_L2FR',            # Leaf-to-fineroot ratio (kg/kg)

    # === OTHER FATES ===
    'FATES_NPLANT',          # Number of plants per m2 by cohort age class

    # === ELM CLIMATE ===
    'TSA',                   # 2m air temperature
    'TBOT',                  # Atmospheric forcing temperature
    'TSOI_10CM',             # Soil temperature in top 10cm of soil (K)
    'SOILWATER_10CM',        # Soil liquid water + ice in top 10cm of soil (veg landunits only) (kg/m²)
    'H2OSNO',                # Snow water equivalent
    'SNOW_DEPTH',            # Snow depth
    'FSNO',                  # Snow cover fraction
    'FSNO_EFF',              # Effective snow cover fraction
    'FPSN',                  # Photosynthesis
    'FSH',                   # Sensible heat flux
    'EFLX_LH_TOT',           # Latent heat flux
    'FSR',                   # Solar radiation
    'FSDS',                  # Downward solar radiation
    'QBOT',                  # Atmospheric humidity
    'WIND',                  # Wind speed
    'RAIN',                  # Rainfall
    'SNOW',                  # Snowfall
    # === P POOLS (site-level) ===
    'SMINP',              # Soil mineral P (total inorganic P)
    'LABILEP',            # Labile P (plant-available inorganic P)
    'SECONDP',            # Secondary mineral P (aged, sorbed)
    'PRIMP',              # Primary mineral P (freshly weathered)
    'OCCLP',              # Occluded P (strongly sorbed, unavailable)

    # === P FLUXES (site-level) ===
    'FATES_PUPTAKE',      # Plant P uptake (FATES, kg/m2/s)
    'FATES_PEFFLUX',      # Plant P efflux (FATES, kg/m2/s)
    'SMINP_LEACHED',      # P leaching loss
    'BIOCHEM_PMIN',       # Biochemical P mineralization
    'GROSS_PMIN',         # Gross P mineralization
    'SMINP_TO_PLANT',     # Mineral P to plant
    'PRIMP_TO_LABILEP',   # Primary P weathering → labile
    'PDEP_TO_SMINP',      # Atmospheric P deposition → soil mineral
    'SECONDP_TO_LABILEP', # Secondary P desorption → labile
    'LABILEP_TO_SECONDP', # Labile P sorption → secondary
    'SECONDP_TO_OCCLP',   # Secondary P occlusion → occluded

    # === N FLUXES (site-level) ===
    'NDEP_TO_SMINN',      # N deposition → soil mineral
    'NFIX_TO_SMINN',      # Free-living N fixation → soil mineral
    'GROSS_NMIN',         # Gross N mineralization
    'SMIN_NO3_LEACHED',   # NO3 leaching loss
    'SMIN_NO3_RUNOFF',    # NO3 runoff loss
    'SMINN',              # Total soil mineral N
    'SMIN_NH4',           # Soil ammonium
    'SMIN_NO3',           # Soil nitrate
    'FATES_NH4UPTAKE',    # Plant NH4 uptake (FATES)
    'FATES_NO3UPTAKE',    # Plant NO3 uptake (FATES)
    'FATES_NEFFLUX',      # Plant N efflux (FATES)
]

# ======= SOIL LAYER VARIABLES (time, levgrnd=15, lndgrid) =======
LEVGRND_VARS = [
    'H2OSOI',                # Total soil moisture (liquid + ice) by layer
    'SOILICE',               # Soil ice content by layer
    'SOILICE_ICE',           # Soil ice content (ice landunits only) by layer
    'SOILLIQ',               # Soil liquid water content by layer
    'SOILLIQ_ICE',           # Soil liquid water (ice landunits only) by layer
    'SOILPSI',               # Soil water potential by layer
    'TSOI',                  # Soil temperature by layer
    'TSOI_ICE',              # Soil temperature (ice landunits only) by layer
]

# ======= SOIL PROFILE VARIABLES (time, levsoi=10, lndgrid) =======
# FATES root distribution by soil layer (10 layers, different from levgrnd=15)
LEVSOI_VARS = [
    'FATES_FROOTC_SL',       # Fine root carbon by soil layer (kg m-3, volumetric)
]

# ======= DECOMPOSITION LAYER VARIABLES (time, levdcmp=15, lndgrid) =======
# Nutrient pools and fluxes by decomposition layer
LEVDCMP_VARS = [
    # === INORGANIC NITROGEN POOLS ===
    'SMIN_NH4_vr',           # Soil mineral NH4 by layer (ammonium, plant-available)
    'SMIN_NO3_vr',           # Soil mineral NO3 by layer (nitrate, plant-available)

    # === ORGANIC NITROGEN POOLS (Litter) ===
    'LITR1N_vr',             # Litter 1 N by layer (metabolic litter)
    'LITR2N_vr',             # Litter 2 N by layer (cellulose litter)
    'LITR3N_vr',             # Litter 3 N by layer (lignin litter)

    # === ORGANIC NITROGEN POOLS (Soil Organic Matter) ===
    'SOIL1N_vr',             # Soil organic matter 1 N by layer (fast turnover)
    'SOIL2N_vr',             # Soil organic matter 2 N by layer (medium turnover)
    'SOIL3N_vr',             # Soil organic matter 3 N by layer (slow turnover, passive)

    # === NITROGEN TRANSFORMATION FLUXES ===
    'F_NIT_vr',              # Nitrification flux by layer (NH4 → NO3)
    'F_DENIT_vr',            # Denitrification flux by layer (NO3 → N2/N2O)

    # === INORGANIC PHOSPHORUS POOLS ===
    'PRIMP_vr',              # Primary mineral P by layer (inorganic, freshly weathered)
    'SECONDP_vr',            # Secondary mineral P by layer (aged, occluded)
    'OCCLP_vr',              # Occluded P by layer (strongly sorbed, unavailable)
    'LABILEP_vr',            # Labile P by layer (plant-available inorganic P)
    'SMINP_vr',              # Soil mineral P by layer (total inorganic P)

    # === ORGANIC PHOSPHORUS POOLS (Litter) ===
    'LITR1P_vr',             # Litter 1 P by layer (metabolic litter)
    'LITR2P_vr',             # Litter 2 P by layer (cellulose litter)
    'LITR3P_vr',             # Litter 3 P by layer (lignin litter)

    # === ORGANIC PHOSPHORUS POOLS (Soil Organic Matter) ===
    'SOIL1P_vr',             # Soil organic matter 1 P by layer (fast turnover)
    'SOIL2P_vr',             # Soil organic matter 2 P by layer (medium turnover)
    'SOIL3P_vr',             # Soil organic matter 3 P by layer (slow turnover, passive)
]

# ======= 2D-PFT VARIABLES (time, fates_levpft, lndgrid) =======
PFT_LEVEL_VARS = [
    # === BIOMASS POOLS BY PFT ===
    'FATES_LEAFC_PF',                # Leaf C by PFT
    'FATES_FROOTC_PF',               # Fine root C by PFT
    'FATES_STOREC_PF',               # Storage C by PFT

    # === CARBON FLUXES BY PFT ===
    'FATES_GPP_PF',                  # GPP by PFT
    'FATES_NPP_PF',                  # NPP by PFT

    'FATES_MORTALITY_CFLUX_PF',
    'FATES_MORTALITY_FIRE_CFLUX_PF',
    'FATES_MORTALITY_HYDRO_CFLUX_PF',
    'FATES_MORTALITY_CSTARV_CFLUX_PF',

    # === DYNAMIC L2FR BY PFT (for recruits) ===
    'FATES_L2FR_CANOPY_REC_PF',      # Canopy recruit l2fr by PFT
    'FATES_L2FR_USTORY_REC_PF'      # Understory recruit l2fr by PFT

]

# ======= ELEMENT-LEVEL VARIABLES (time, fates_levelem=3, lndgrid) =======
# fates_levelem = 3 (Carbon, Nitrogen, Phosphorus)
# Element index: 0=Carbon, 1=Nitrogen, 2=Phosphorus
LEVELEM_VARS = [
    'FATES_SEED_BANK_EL',     # Seed bank mass by element (kg element/m2)
    'FATES_SEED_DECAY_EL',    # Seed decay flux by element (kg element/m2/s)
    'FATES_SEED_GERM_EL',     # Seed germination by element (kg element/m2)
    'FATES_SEEDS_IN_EXTERN_EL',  # External seed influx by element
    'FATES_SEEDS_IN_LOCAL_EL',   # Local seed production by element
]

# ======= 2D-SZPF VARIABLES (time, fates_levscpf, lndgrid) =======
# fates_levscpf = 156 (13 size classes × 12 PFTs)
SZPF_VARS = [
    #'FATES_BASALAREA_SZPF',           # Basal area
    #'FATES_DDBH_CANOPY_SZPF',         # DBH growth rate (canopy)
    #'FATES_DDBH_SZPF',                # DBH growth rate (total)
    #'FATES_DDBH_USTORY_SZPF',         # DBH growth rate (understory)
    'FATES_FROOTC_SZPF',              # Fine root carbon
    'FATES_FROOTN_SZPF',              # Fine root nitrogen
    'FATES_FROOTP_SZPF',              # Fine root phosphorus
    'FATES_FROOT_ALLOC_SZPF',         # Fine root allocation
    'FATES_LEAFC_SZPF',               # Leaf carbon
    'FATES_LEAFN_SZPF',               # Leaf nitrogen
    'FATES_LEAFP_SZPF',               # Leaf phosphorus
    'FATES_LEAF_ALLOC_SZPF',          # Leaf allocation
    'FATES_NDEMAND_SZPF',             # Nitrogen demand
    'FATES_NEFFLUX_SZPF',             # Nitrogen efflux
    'FATES_NFIX_SYM_SZPF',            # Symbiotic N fixation
    'FATES_NH4UPTAKE_SZPF',           # NH4 uptake
    'FATES_NO3UPTAKE_SZPF',           # NO3 uptake
    'FATES_NPP_SZPF',                 # Net primary production
    'FATES_PDEMAND_SZPF',             # Phosphorus demand
    'FATES_PEFFLUX_SZPF',             # Phosphorus efflux
    'FATES_PUPTAKE_SZPF',             # Phosphorus uptake
    'FATES_REPROC_SZPF',              # Reproductive carbon
    'FATES_REPRON_SZPF',              # Reproductive nitrogen
    'FATES_REPROP_SZPF',              # Reproductive phosphorus
    'FATES_SEED_ALLOC_SZPF',          # Seed allocation
    #'FATES_STOREC_TF_CANOPY_SZPF',    # Storage C (canopy, target fraction)
    #'FATES_STOREC_TF_USTORY_SZPF',    # Storage C (understory, target fraction)
    #'FATES_STOREN_TF_CANOPY_SZPF',    # Storage N (canopy, target fraction)
    #'FATES_STOREN_TF_USTORY_SZPF',    # Storage N (understory, target fraction)
    #'FATES_STOREP_TF_CANOPY_SZPF',    # Storage P (canopy, target fraction)
    #'FATES_STOREP_TF_USTORY_SZPF',    # Storage P (understory, target fraction)
    'FATES_VEGC_ABOVEGROUND_SZPF',    # Aboveground biomass by pft/size in kg carbon per m2
    'FATES_VEGC_SZPF',                # Total vegetation carbon by size-class x pft in kg C per m2
    'FATES_VEGN_SZPF',                # Total (live) vegetation nitrogen mass by size-class x pft in kg N per m2
    'FATES_VEGP_SZPF'                # Total (live) vegetation phosphorus mass by size-class x pft in kg P per m2
]

# Mapping variables (to interpret the size-class × PFT dimension)
MAPPING_VARS = [
    'levgrnd',             # Ground level index (15 layers)
    'levsoi',              # Soil profile index (10 layers, for FATES root distribution)
    'levdcmp',             # Decomposition level index (15 layers)
    'fates_levscls',        # Size class boundaries
    'fates_levpft',         # PFT indices
    'fates_levelem',        # Element indices (3: C, N, P)
    'fates_pftmap_levscpf', # PFT index for each size-class × PFT combo
    'fates_scmap_levscpf',  # Size class index for each size-class × PFT combo
]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

# Read case numbers from file or command-line arguments
def load_case_numbers(case_list=None, case_file=None):
    """
    Load case numbers from command-line list or file.

    Parameters:
    -----------
    case_list : list of int or None
        List of case numbers from --cases argument
    case_file : str or None
        Path to file containing case numbers (one per line)

    Returns:
    --------
    cases : list of int
        List of case numbers to process
    """
    # Priority 1: Use case_list if provided
    if case_list:
        return case_list

    # Priority 2: Use case_file if provided and exists
    if case_file and Path(case_file).exists():
        with open(case_file, 'r') as f:
            cases = [int(line.strip()) for line in f if line.strip().isdigit()]
        return cases

    # No cases specified
    raise ValueError("No cases specified. Use --cases [list] or --case-file [file]")

def get_history_files(case_name, start_year, end_year):
    """
    Find all monthly history files for a case.

    Pattern: {case_name}.elm.h0.YYYY-MM-01-00000.nc
    where each file contains 12 monthly timesteps for that year.
    """
    case_dir = BASE_INPUT_DIR / case_name / 'run'

    if not case_dir.exists():
        print(f"  ⚠ Warning: Case directory not found: {case_dir}")
        return []

    # Find all .elm.h0.*.nc files for the year range
    files = []
    for year in range(start_year, end_year + 1):
        # Pattern: case.elm.h0.YYYY-*-00000.nc
        year_files = sorted(case_dir.glob(f'{case_name}.elm.h0.{year:04d}-??-??-00000.nc'))
        files.extend(year_files)

    return sorted(files)


def extract_all_variables(history_files, site_vars, levgrnd_vars, levsoi_vars, levdcmp_vars, levelem_vars, pft_vars, szpf_vars, case_name):
    """
    Extract all variables from monthly history files using xarray.

    Parameters:
    -----------
    history_files : list of Path
        List of NetCDF files (one per year, 12 months per file)
    site_vars : list
        Site-level variables (1D)
    levgrnd_vars : list
        Soil layer variables (2D-levgrnd)
    levsoi_vars : list
        Soil profile variables (2D-levsoi, FATES root distribution)
    levdcmp_vars : list
        Decomposition layer variables (2D-levdcmp)
    levelem_vars : list
        Element-level variables (2D-fates_levelem, C/N/P)
    pft_vars : list
        PFT-level variables (2D-PFT)
    szpf_vars : list
        SZPF-level variables (2D-SZPF)
    case_name : str
        Case name for metadata

    Returns:
    --------
    ds_combined : xarray.Dataset
        Combined dataset with all variables
    """

    print(f"  Loading {len(history_files)} yearly files (each with 12 months)...")

    # Open all files and concatenate
    ds_list = []

    for i, file in enumerate(history_files):
        print(f"    Loading file {i+1}/{len(history_files)}: {file.name}")

        try:
            # Open file
            ds = xr.open_dataset(file, decode_times=False)

            # Select only variables we need
            vars_to_extract = []

            # Add site-level vars
            vars_to_extract.extend([v for v in site_vars if v in ds.variables])

            # Add soil layer vars
            vars_to_extract.extend([v for v in levgrnd_vars if v in ds.variables])

            # Add soil profile vars (FATES root distribution)
            vars_to_extract.extend([v for v in levsoi_vars if v in ds.variables])

            # Add decomposition layer vars
            vars_to_extract.extend([v for v in levdcmp_vars if v in ds.variables])

            # Add element-level vars (fates_levelem dimension)
            vars_to_extract.extend([v for v in levelem_vars if v in ds.variables])

            # Add PFT-level vars
            vars_to_extract.extend([v for v in pft_vars if v in ds.variables])

            # Add SZPF-level vars
            vars_to_extract.extend([v for v in szpf_vars if v in ds.variables])

            # Also get mapping variables (only need from first file)
            if i == 0:
                mapping_vars = [v for v in MAPPING_VARS if v in ds.variables]
                vars_to_extract.extend(mapping_vars)

            # Extract subset
            ds_subset = ds[vars_to_extract]
            ds_list.append(ds_subset)
            ds.close()

        except Exception as e:
            print(f"  ⚠ Error reading {file.name}: {e}")
            continue

    if not ds_list:
        print(f"  ✗ No data extracted")
        return None

    print(f"    Concatenating {len(ds_list)} files...")
    # Concatenate along time dimension
    ds_combined = xr.concat(ds_list, dim='time')

    # Add metadata
    ds_combined.attrs['title'] = f'Monthly ELM-FATES Output - All Variables'
    ds_combined.attrs['case_name'] = case_name
    ds_combined.attrs['temporal_resolution'] = 'monthly'
    ds_combined.attrs['created'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ds_combined.attrs['calendar'] = 'noleap (365 days/year, no leap years)'
    ds_combined.attrs['note'] = 'Yearly files with 12 monthly timesteps, concatenated'

    return ds_combined


def create_csv_dataframe(ds_combined, site_vars, pft_vars):
    """
    Create CSV-friendly DataFrame from site-level and PFT-level variables.

    Note: Skips levgrnd, levsoi, and levdcmp variables - those are only in NetCDF output.

    Parameters:
    -----------
    ds_combined : xarray.Dataset
        Combined dataset
    site_vars : list
        Site-level variables (excludes levgrnd/levdcmp)
    pft_vars : list
        PFT-level variables

    Returns:
    --------
    df : pandas.DataFrame
        DataFrame with time, site-level, and PFT-level (for selected PFTs) columns
    """

    all_data = []
    n_times = len(ds_combined.time)

    print(f"  Creating CSV DataFrame ({n_times} timesteps)...")

    for t in range(n_times):
        row_data = {}

        # Extract time info (assuming time is in days since some epoch)
        # We'll use the file structure to infer year-month
        # Each file has 12 months, so:
        year = START_YEAR + t // 12
        month = (t % 12) + 1
        row_data['year'] = year
        row_data['month'] = month

        # Extract site-level variables
        for var in site_vars:
            if var in ds_combined.variables:
                # Skip levgrnd, levsoi, and levdcmp variables (only in NetCDF)
                if ('levgrnd' in ds_combined[var].dims or
                    'levsoi' in ds_combined[var].dims or
                    'levdcmp' in ds_combined[var].dims):
                    continue

                value = ds_combined[var].values

                # Handle dimensions
                if value.ndim == 2:  # (time, lndgrid)
                    value = value[t, 0]
                elif value.ndim == 1:  # (time,)
                    value = value[t]
                else:
                    # Other multi-dimensional variables - take mean
                    value = np.mean(value[t, ...])

                row_data[var] = float(value) if not np.isnan(value) else np.nan
            else:
                row_data[var] = np.nan

        # Extract PFT-level variables for selected PFTs
        for var in pft_vars:
            if var in ds_combined.variables:
                # Shape: (time, fates_levpft=12, lndgrid)
                pft_values = ds_combined[var].values[t, :, 0]  # Extract (12,) array

                # Extract specific PFTs
                for pft_name, pft_idx in PFT_INDICES.items():
                    col_name = f"{var}_{pft_name}"
                    row_data[col_name] = float(pft_values[pft_idx])
            else:
                # Variable not found - set all PFTs to NaN
                for pft_name in PFT_INDICES.keys():
                    col_name = f"{var}_{pft_name}"
                    row_data[col_name] = np.nan

        all_data.append(row_data)

    # Create DataFrame
    df = pd.DataFrame(all_data)

    # Convert temperatures from Kelvin to Celsius
    temp_vars = [var for var in df.columns if 'TVEG' in var or var in ['TV', 'TSA', 'TBOT', 'TSOI']]
    for var in temp_vars:
        if var in df.columns and df[var].max() > 100:
            df[var] = df[var] - 273.15

    # Convert fluxes from per-second to per-day (kg C/m²/s → g C/m²/day)
    flux_vars = [v for v in df.columns if any(x in v for x in ['GPP', 'NPP', 'RESP', 'ALLOC'])]
    seconds_per_day = 86400
    kg_to_g = 1000

    for var in flux_vars:
        if var in df.columns:
            df[var] = df[var] * seconds_per_day * kg_to_g

    # Convert biomass pools from kg to g
    biomass_vars = [v for v in df.columns if any(x in v for x in ['LEAFC', 'FROOTC', 'STOREC', 'STOREN', 'STOREP', 'VEGC'])]
    for var in biomass_vars:
        if var in df.columns and 'ALLOC' not in var:
            df[var] = df[var] * kg_to_g

    return df


def process_case(case_id, available_site, available_levgrnd, available_levsoi, available_levdcmp, available_levelem, available_pft, available_szpf):
    """
    Process a single case: extract all variables and save to NetCDF + CSV.

    Parameters:
    -----------
    case_id : int or str
        Case number (int) or case identifier (str like "845_exp1")
    available_site : list
        Available site-level variables
    available_levgrnd : list
        Available soil layer variables
    available_levsoi : list
        Available soil profile variables (FATES root distribution)
    available_levdcmp : list
        Available decomposition layer variables
    available_levelem : list
        Available element-level variables (fates_levelem)
    available_pft : list
        Available PFT-level variables
    available_szpf : list
        Available SZPF-level variables

    Returns:
    --------
    success : bool
        True if successful, False otherwise
    """

    # Handle both integer case numbers and string case IDs
    if isinstance(case_id, int):
        # Regular ensemble case: use CASE_SUFFIX
        case_name = f'Kougarok_ELM-FATES_PtCNPEn{case_id}_{CASE_SUFFIX}'
    else:
        # String case ID (e.g., "845_exp1")
        # Check if it's an experimental case
        if '_exp' in str(case_id):
            # Experimental case: case_id already contains "845_exp1", just append "_TRANS"
            # Result: Kougarok_ELM-FATES_PtCNPEn845_exp1_TRANS
            case_name = f'Kougarok_ELM-FATES_PtCNPEn{case_id}_TRANS'
        else:
            # Other string case ID: use CASE_SUFFIX
            case_name = f'Kougarok_ELM-FATES_PtCNPEn{case_id}_{CASE_SUFFIX}'

    print(f"\n  Processing case {case_id}: {case_name}")

    # Get history files
    history_files = get_history_files(case_name, START_YEAR, END_YEAR)

    if not history_files:
        print(f"  ✗ No history files found")
        return False

    expected_files = END_YEAR - START_YEAR + 1
    print(f"    Found {len(history_files)} yearly files (expected: {expected_files})")

    try:
        # Extract all variables
        ds_combined = extract_all_variables(
            history_files, available_site, available_levgrnd, available_levsoi, available_levdcmp, available_levelem, available_pft, available_szpf, case_name
        )

        if ds_combined is None:
            return False

        print(f"  Dataset shape:")
        print(f"    Time steps: {len(ds_combined.time)}")
        print(f"    Site-level variables: {len([v for v in available_site if v in ds_combined.variables])}")
        print(f"    Soil layer variables: {len([v for v in available_levgrnd if v in ds_combined.variables])}")
        print(f"    Soil profile variables: {len([v for v in available_levsoi if v in ds_combined.variables])}")
        print(f"    Decomposition layer variables: {len([v for v in available_levdcmp if v in ds_combined.variables])}")
        print(f"    Element-level variables: {len([v for v in available_levelem if v in ds_combined.variables])}")
        print(f"    PFT-level variables: {len([v for v in available_pft if v in ds_combined.variables])}")
        print(f"    SZPF-level variables: {len([v for v in available_szpf if v in ds_combined.variables])}")

        # Save NetCDF (all variables including SZPF)
        nc_file = OUTPUT_DIR / f'{case_name}_all_variables_monthly_{START_YEAR}_{END_YEAR}.nc'

        # Use compression for large SZPF dimension
        encoding = {}
        for var in ds_combined.data_vars:
            if var not in MAPPING_VARS:  # Don't compress mapping variables
                encoding[var] = {
                    'zlib': True,
                    'complevel': 4,
                    'shuffle': True,
                    'fletcher32': True
                }

        ds_combined.to_netcdf(nc_file, encoding=encoding, format='NETCDF4')
        size_mb = nc_file.stat().st_size / 1e6
        print(f"  ✓ Saved NetCDF: {nc_file.name} ({size_mb:.1f} MB)")

        # Create CSV DataFrame (site-level + PFT-level only, not SZPF)
        df = create_csv_dataframe(ds_combined, available_site, available_pft)

        # Save CSV
        csv_file = OUTPUT_DIR / f'{case_name}_site_pft_monthly_{START_YEAR}_{END_YEAR}.csv'
        df.to_csv(csv_file, index=False)
        size_mb_csv = csv_file.stat().st_size / 1e6
        print(f"  ✓ Saved CSV: {csv_file.name} ({size_mb_csv:.1f} MB)")

        # Close dataset
        ds_combined.close()

        print(f"  ✓ Complete!")
        return True

    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# CALLABLE API (for orchestrator integration)
# ============================================================================

def run_monthly_extraction(case_list=None, case_file=None, parallel=8):
    """
    Extract comprehensive monthly variables from ELM-FATES simulation output.

    Callable API wrapping the main() logic for use by the orchestrator.
    Uses module-level config (BASE_INPUT_DIR, OUTPUT_DIR, etc.).

    Parameters:
    -----------
    case_list : list of int, optional
        List of case numbers to extract. If None, uses case_file or config.
    case_file : str, optional
        Path to file containing case numbers (one per line).
    parallel : int, optional
        Number of parallel workers (default: 8). Set to 1 for sequential.

    Returns:
    --------
    dict with keys:
        'status': 'completed' | 'partial' | 'failed'
        'successful_cases': list of int
        'failed_cases': list of int
        'output_dir': str
    """
    if not BASE_INPUT_DIR or not OUTPUT_DIR:
        return {'status': 'failed', 'error': 'A2MC config not loaded (BASE_INPUT_DIR/OUTPUT_DIR not set)'}

    # Load case numbers
    try:
        case_numbers = load_case_numbers(case_list, case_file)
    except ValueError as e:
        # No cases specified — generate full range from config
        try:
            from tools.config import config as a2mc_config
            n_total = a2mc_config.TOTAL_ENSEMBLE
            case_numbers = list(range(1, n_total + 1))
        except (ImportError, AttributeError):
            return {'status': 'failed', 'error': str(e)}

    if not case_numbers:
        return {'status': 'failed', 'error': 'No case numbers to process'}

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Skip cases that already have extracted files
    cases_to_extract = []
    for case_id in case_numbers:
        if isinstance(case_id, int):
            case_name = f'Kougarok_ELM-FATES_PtCNPEn{case_id}_{CASE_SUFFIX}'
        elif '_exp' in str(case_id):
            case_name = f'Kougarok_ELM-FATES_PtCNPEn{case_id}_TRANS'
        else:
            case_name = f'Kougarok_ELM-FATES_PtCNPEn{case_id}_{CASE_SUFFIX}'
        nc_file = OUTPUT_DIR / f'{case_name}_all_variables_monthly_{START_YEAR}_{END_YEAR}.nc'
        if not nc_file.exists():
            cases_to_extract.append(case_id)

    if not cases_to_extract:
        print(f"All {len(case_numbers)} cases already extracted in {OUTPUT_DIR}")
        return {
            'status': 'completed',
            'successful_cases': case_numbers,
            'failed_cases': [],
            'output_dir': str(OUTPUT_DIR),
            'skipped': len(case_numbers)
        }

    print(f"\nExtracting {len(cases_to_extract)} cases ({len(case_numbers) - len(cases_to_extract)} already done)")

    # Detect available variables from first case
    first_case_id = cases_to_extract[0]
    if isinstance(first_case_id, int):
        first_case_name = f'Kougarok_ELM-FATES_PtCNPEn{first_case_id}_{CASE_SUFFIX}'
    elif '_exp' in str(first_case_id):
        first_case_name = f'Kougarok_ELM-FATES_PtCNPEn{first_case_id}_TRANS'
    else:
        first_case_name = f'Kougarok_ELM-FATES_PtCNPEn{first_case_id}_{CASE_SUFFIX}'

    first_history_files = get_history_files(first_case_name, START_YEAR, START_YEAR)
    if not first_history_files:
        return {'status': 'failed', 'error': f'No history files found for case {first_case_id}'}

    ds_test = xr.open_dataset(first_history_files[0], decode_times=False)
    all_vars = list(ds_test.variables.keys())
    available_site = [v for v in SITE_LEVEL_VARS if v in all_vars]
    available_levgrnd = [v for v in LEVGRND_VARS if v in all_vars]
    available_levsoi = [v for v in LEVSOI_VARS if v in all_vars]
    available_levdcmp = [v for v in LEVDCMP_VARS if v in all_vars]
    available_levelem = [v for v in LEVELEM_VARS if v in all_vars]
    available_pft = [v for v in PFT_LEVEL_VARS if v in all_vars]
    available_szpf = [v for v in SZPF_VARS if v in all_vars]
    ds_test.close()

    # Process cases (parallel or sequential)
    successful_cases = []
    failed_cases = []

    if parallel > 1 and len(cases_to_extract) > 1:
        from multiprocessing import Pool
        print(f"Using {parallel} parallel workers")

        # Worker function with all available vars bound
        def _extract_case(case_id):
            return (case_id, process_case(case_id, available_site, available_levgrnd,
                                          available_levsoi, available_levdcmp,
                                          available_levelem, available_pft, available_szpf))

        with Pool(processes=parallel) as pool:
            for i, (case_id, success) in enumerate(pool.imap_unordered(_extract_case, cases_to_extract), 1):
                if success:
                    successful_cases.append(case_id)
                else:
                    failed_cases.append(case_id)
                if i % 50 == 0 or i == len(cases_to_extract):
                    print(f"  Progress: {i}/{len(cases_to_extract)} "
                          f"({len(successful_cases)} OK, {len(failed_cases)} failed)")
    else:
        for idx, case_id in enumerate(cases_to_extract, 1):
            print(f"\n[{idx}/{len(cases_to_extract)}] Case {case_id}")
            success = process_case(case_id, available_site, available_levgrnd, available_levsoi,
                                   available_levdcmp, available_levelem, available_pft, available_szpf)
            if success:
                successful_cases.append(case_id)
            else:
                failed_cases.append(case_id)

    total_success = len(successful_cases) + (len(case_numbers) - len(cases_to_extract))
    status = 'completed' if not failed_cases else 'partial'

    print(f"\nExtraction {status}: {total_success}/{len(case_numbers)} cases")
    if failed_cases:
        print(f"Failed cases: {failed_cases}")

    return {
        'status': status,
        'successful_cases': successful_cases,
        'failed_cases': failed_cases,
        'output_dir': str(OUTPUT_DIR),
        'total_extracted': total_success
    }


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Extract all variables from monthly ELM-FATES output',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Extract specific cases
  python %(prog)s --cases 845 2678 2675

  # Extract cases from file
  python %(prog)s --case-file case_numbers.txt

  # Extract Case #845 experimental modifications
  python %(prog)s --cases 845_exp1 845_exp2 845_exp3 845_exp4 845_exp5
        '''
    )
    parser.add_argument('--cases', type=str, nargs='+', default=None,
                       help='List of case numbers or case IDs (e.g., 845 2678 or 845_exp1 845_exp2)')
    parser.add_argument('--case-file', type=str, default=None,
                       help='File containing case numbers (one per line)')
    parser.add_argument('--parallel', type=int, default=8,
                       help='Number of parallel workers (default: 8, use 1 for sequential)')
    args = parser.parse_args()

    # Load case numbers
    # Convert case strings to case identifiers (handle both integers and strings like "845_exp1")
    case_list = None
    if args.cases:
        case_list = []
        for case_str in args.cases:
            # Try to convert to int if it's a pure number
            try:
                case_list.append(int(case_str))
            except ValueError:
                # Keep as string (e.g., "845_exp1")
                case_list.append(case_str)

    CASE_NUMBERS = load_case_numbers(case_list, args.case_file)

    print("\n" + "=" * 80)
    print("EXTRACT ALL VARIABLES FROM MONTHLY ELM-FATES OUTPUT (COMPREHENSIVE)")
    print("=" * 80)
    print()
    print(f"Cases to process: {len(CASE_NUMBERS)}")
    if args.cases:
        print(f"Case IDs: {CASE_NUMBERS}")
    elif args.case_file:
        print(f"Case numbers loaded from: {args.case_file}")
    print(f"Year range: {START_YEAR}-{END_YEAR} (yearly files with 12 months each)")
    print(f"Case suffix: {CASE_SUFFIX}")
    print()
    print(f"Variables to extract:")
    print(f"  - Site-level (1D): {len(SITE_LEVEL_VARS)}")
    print(f"  - Soil layer (2D): {len(LEVGRND_VARS)} (dimension: 15 soil layers)")
    print(f"  - Soil profile (2D): {len(LEVSOI_VARS)} (dimension: 10 layers, FATES root distribution)")
    print(f"  - Decomposition layer (2D): {len(LEVDCMP_VARS)} (dimension: 15 decomp layers, N+P diagnostics)")
    print(f"  - Element-level (2D): {len(LEVELEM_VARS)} (dimension: 3 elements, C/N/P)")
    print(f"  - PFT-level (2D): {len(PFT_LEVEL_VARS)}")
    print(f"  - SZPF-level (2D): {len(SZPF_VARS)} (dimension: 156 = 13 size × 12 PFTs)")
    print()
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Estimated time: {len(CASE_NUMBERS) * 5}-{len(CASE_NUMBERS) * 10} minutes")
    print("=" * 80)

    # Check first case to detect available variables
    print("\nDetecting available variables from first case...")
    first_case_id = CASE_NUMBERS[0]

    # Build case name with appropriate suffix
    if isinstance(first_case_id, int):
        first_case_name = f'Kougarok_ELM-FATES_PtCNPEn{first_case_id}_{CASE_SUFFIX}'
    else:
        # String case ID
        if '_exp' in str(first_case_id):
            # Experimental case: just append "_TRANS"
            first_case_name = f'Kougarok_ELM-FATES_PtCNPEn{first_case_id}_TRANS'
        else:
            # Other string case ID: use CASE_SUFFIX
            first_case_name = f'Kougarok_ELM-FATES_PtCNPEn{first_case_id}_{CASE_SUFFIX}'

    first_history_files = get_history_files(first_case_name, START_YEAR, START_YEAR)

    if not first_history_files:
        print(f"ERROR: No history files found for first case: {first_case_name}")
        return

    first_file = first_history_files[0]
    ds_test = xr.open_dataset(first_file, decode_times=False)
    all_vars = list(ds_test.variables.keys())

    available_site = [v for v in SITE_LEVEL_VARS if v in all_vars]
    available_levgrnd = [v for v in LEVGRND_VARS if v in all_vars]
    available_levsoi = [v for v in LEVSOI_VARS if v in all_vars]
    available_levdcmp = [v for v in LEVDCMP_VARS if v in all_vars]
    available_levelem = [v for v in LEVELEM_VARS if v in all_vars]
    available_pft = [v for v in PFT_LEVEL_VARS if v in all_vars]
    available_szpf = [v for v in SZPF_VARS if v in all_vars]

    ds_test.close()

    print(f"  Site-level: {len(available_site)}/{len(SITE_LEVEL_VARS)}")
    print(f"  Soil layer: {len(available_levgrnd)}/{len(LEVGRND_VARS)}")
    print(f"  Soil profile: {len(available_levsoi)}/{len(LEVSOI_VARS)}")
    print(f"  Decomposition layer: {len(available_levdcmp)}/{len(LEVDCMP_VARS)}")
    print(f"  Element-level: {len(available_levelem)}/{len(LEVELEM_VARS)}")
    print(f"  PFT-level: {len(available_pft)}/{len(PFT_LEVEL_VARS)}")
    print(f"  SZPF-level: {len(available_szpf)}/{len(SZPF_VARS)}")

    # Process each case
    print("\n" + "=" * 80)
    print(f"PROCESSING CASES (parallel={args.parallel})")
    print("=" * 80)

    successful_cases = []
    failed_cases = []

    if args.parallel > 1 and len(CASE_NUMBERS) > 1:
        from multiprocessing import Pool

        def _extract_case(case_id):
            return (case_id, process_case(case_id, available_site, available_levgrnd,
                                          available_levsoi, available_levdcmp,
                                          available_levelem, available_pft, available_szpf))

        with Pool(processes=args.parallel) as pool:
            for i, (case_id, success) in enumerate(pool.imap_unordered(_extract_case, CASE_NUMBERS), 1):
                if success:
                    successful_cases.append(case_id)
                else:
                    failed_cases.append(case_id)
                if i % 50 == 0 or i == len(CASE_NUMBERS):
                    print(f"  Progress: {i}/{len(CASE_NUMBERS)} "
                          f"({len(successful_cases)} OK, {len(failed_cases)} failed)")
    else:
        for idx, case_id in enumerate(CASE_NUMBERS, 1):
            print(f"\n[{idx}/{len(CASE_NUMBERS)}] Case {case_id}")
            print("=" * 80)

            success = process_case(case_id, available_site, available_levgrnd, available_levsoi, available_levdcmp, available_levelem, available_pft, available_szpf)

            if success:
                successful_cases.append(case_id)
            else:
                failed_cases.append(case_id)

    # Final summary
    print("\n" + "=" * 80)
    print("BATCH PROCESSING COMPLETE")
    print("=" * 80)
    print(f"Successful: {len(successful_cases)}/{len(CASE_NUMBERS)} cases")
    print(f"Failed: {len(failed_cases)}/{len(CASE_NUMBERS)} cases")

    if failed_cases:
        print(f"\nFailed cases: {failed_cases}")

    print(f"\nOutput directory: {OUTPUT_DIR}")
    print("=" * 80)


if __name__ == "__main__":
    main()
