---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# History Variables and Dimensions

**Relevant source files:**
- `main/FatesHistoryInterfaceMod.F90` (9944 lines)
- `main/FatesHistoryVariableType.F90`
- `main/FatesIODimensionsMod.F90`
- `main/FatesIOVariableKindMod.F90`
- `main/FatesInterfaceMod.F90`
- `main/FatesInterfaceTypesMod.F90`
- `main/FatesSizeAgeTypeIndicesMod.F90`

**Canonical inventory:** `docs/fates-knowledge-base/elm_fates_output_info_e027a40.cdl`

## Purpose and Scope

This page documents the actual FATES history variables registered at e027a40 and the dimension system they use. It is the canonical reference for writing post-processing scripts against FATES history files: if you grep a history NetCDF for a name that is not in the table below, it does not exist.

The variable inventory has been **regenerated from the canonical CDL** (`elm_fates_output_info_e027a40.cdl`), which has 493 unique `FATES_*` variables. The Fortran source registers 494 `set_history_var(vname='FATES_*')` calls (the extra is `FATES_L2FR_CLSZPF`, conditional on a build flag).

For the mechanics of how these variables are accumulated and written, see [History Update Pipeline](pipeline.md). For the overall architecture, see [History Output System](index.md).

## Base Dimensions

Base dimensions are the fundamental axes along which variables can be indexed. Their sizes are determined by model configuration (parameter file, PFT count, etc.).

| Base dimension | Description | CDL size at e027a40 |
|---|---|---|
| `lndgrid` (= column) | Host model gridcell/column (FATES site) | 1 (single-site test) |
| `levsoi` | Vertical soil layer | varies (commonly 10-20) |
| `fates_levpft` | Plant functional type | 14 (was 12 at e85d997) |
| `fates_levscls` | Cohort diameter size class | 13 |
| `fates_levage` | Patch age class | 7 |
| `fates_levcoage` | Cohort age class | varies |
| `fates_levcan` | Canopy layer | 2 (canopy, understory) |
| `fates_levleaf` | Leaf layer within canopy | varies (e.g., 30) |
| `fates_levcwdsc` | Coarse woody debris size class | 4 |
| `fates_levfuel` | Fuel size class | 6 |
| `fates_levheight` | Height bin | varies |
| `fates_levdamage` | Crown damage severity | varies |
| `fates_levelem` | Chemical element (C, N, P) | up to 3 |
| `fates_levlanduse` | Land-use category (NEW at e027a40) | 5 (primary, secondary, pasture, rangeland, crop) |

Note that `fates_levpft = 14` at e027a40 reflects the addition of two Arctic shrubs at PFT positions 10-11 and `arctic_c3_grass` at position 12 (the wider FATES drift from e85d997). The `fates_levlupft = 60` value (5 × 12) and `fates_levlulu = 25` (5 × 5) confirm the LU multiplexed sizes.

## Multiplexed Dimensions

Multiplexed dimensions flatten two or three base dimensions into one linear index so that variables can be written as 2-D (`site × multiplexed`) arrays in NetCDF, despite representing 3-D or 4-D information.

| Multiplexed dim | Components | CDL total size | Used for |
|---|---|---|---|
| `fates_levscpf` | size × PFT | `nlevsclass × numpft` (commonly 13 × 14 = 182) | Cohort quantities binned by size and PFT (most common) |
| `fates_levscag` | size × patch age | `nlevsclass × nlevage` | Size-age distributions |
| `fates_levscagpft` | size × age × PFT | `nlevsclass × nlevage × numpft` | Full size-age-PFT distributions |
| `fates_levagepft` | age × PFT | `nlevage × numpft` | Patch age × PFT |
| `fates_levcnlf` | canopy × leaf layer | `nclmax × nlevleaf` (e.g., 60) | Radiation profiles |
| `fates_levcnlfpft` | canopy × leaf × PFT | `nclmax × nlevleaf × numpft` | PFT-specific radiation |
| `fates_levagefuel` | age × fuel size | `nlevage × nfsc` | Fuel load by patch age |
| `fates_levcdpf` | size × damage × PFT (3-D) | `nlevsclass × nlevdamage × numpft` | Crown damage × size × PFT |
| `fates_levelcwd` | element × CWD size | `num_elements × ncwd` | CWD pools by element |
| `fates_levelpft` | element × PFT | `num_elements × numpft` | Element pools by PFT |
| `fates_levelage` | element × patch age | `num_elements × nlevage` | Element pools by age |
| `fates_levclscpf` | canopy layer × size × PFT | `nclmax × nlevsclass × numpft` | Canopy-layer-stratified size × PFT |
| `fates_levlupft` | land-use × PFT (NEW) | `n_landuse × numpft` (60 in CDL) | Per (land-use × PFT) outputs |
| `fates_levlulu` | land-use × land-use (NEW) | `n_landuse × n_landuse` (25 in CDL) | Land-use transition / disturbance matrix |

Note: `fates_levcdpf` is 3-D (`size × damage × PFT`).

## Dimension Kinds (Variable Types)

Each `set_history_var` call specifies a `vtype` that maps the variable to one of the named dimension kinds defined in `main/FatesIOVariableKindMod.F90`:

| `vtype` constant | Internal `name` string | Dimensionality |
|---|---|---|
| `site_r8` | `SI_R8` | 1-D: site |
| `site_int` | `SI_INT` | 1-D: site (integer) |
| `site_pft_r8` | `SI_PFT_R8` | 2-D: site × PFT |
| `site_size_r8` | `SI_SCLS_R8` | 2-D: site × size class |
| `site_size_pft_r8` | `SI_SCPF_R8` | 2-D: site × (size × PFT) |
| `site_age_r8` | `SI_AGE_R8` | 2-D: site × patch age |
| `site_coage_r8` | `SI_CACLS_R8` | 2-D: site × cohort age |
| `site_coage_pft_r8` | `SI_CAPF_R8` | 2-D: site × (cohort age × PFT) |
| `site_can_r8` | `SI_CAN_R8` | 2-D: site × canopy layer |
| `site_cnlf_r8` | `SI_CNLF_R8` | 2-D: site × (canopy layer × leaf layer) |
| `site_cnlfpft_r8` | `SI_CNLFPFT_R8` | 2-D: site × (canopy × leaf × PFT) |
| `site_cdpf_r8` | `SI_CDPF_R8` | 2-D: site × (size × damage × PFT) |
| `site_cdsc_r8` | `SI_CDSC_R8` | 2-D: site × (damage × size) |
| `site_cdam_r8` | `SI_CDAM_R8` | 2-D: site × damage class |
| `site_scag_r8` | `SI_SCAG_R8` | 2-D: site × (size × age) |
| `site_scagpft_r8` | `SI_SCAGPFT_R8` | 2-D: site × (size × age × PFT) |
| `site_agepft_r8` | `SI_AGEPFT_R8` | 2-D: site × (age × PFT) |
| `site_agefuel_r8` | `SI_AGEFUEL_R8` | 2-D: site × (age × fuel) |
| `site_clscpf_r8` | `SI_CLSCPF_R8` | 2-D: site × (canopy × size × PFT) |
| `site_soil_r8` | `SI_SOIL_R8` | 2-D: site × soil level |
| `site_height_r8` | `SI_HEIGHT_R8` | 2-D: site × height bin |
| `site_fuel_r8` | `SI_FUEL_R8` | 2-D: site × fuel class |
| `site_cwdsc_r8` | `SI_CWDSC_R8` | 2-D: site × CWD size class |
| `site_elem_r8` | `SI_ELEM_R8` | 2-D: site × element |
| `site_elpft_r8` | `SI_ELEMPFT_R8` | 2-D: site × (element × PFT) |
| `site_elcwd_r8` | `SI_ELEMCWD_R8` | 2-D: site × (element × CWD) |
| `site_elage_r8` | `SI_ELEMAGE_R8` | 2-D: site × (element × age) |
| `site_landuse_r8` | (LU) | 2-D: site × land-use (NEW) |
| `site_landuse_pft_r8` | (LUPF) | 2-D: site × (land-use × PFT) (NEW) |
| `site_landuse_landuse_r8` | (LULU) | 2-D: site × (land-use × land-use) (NEW) |
| `cohort_r8` | `CO_R8` | 1-D: cohort (restart only) |
| `cohort_int` | `CO_INT` | 1-D: cohort (restart only) |

The `cohort_*` kinds exist for the restart system, not history output. History output variables are always at the site level or above.

## Output Variable Name Suffix Convention

FATES history variables follow a consistent naming convention in which a dimensionality suffix is appended to the base name. **These are the actual user-facing NetCDF variable names.** Internal Fortran index names (`ih_*`) use different, lowercase conventions but those strings never appear in the NetCDF output.

| Name suffix | Corresponds to | Meaning |
|---|---|---|
| (no suffix) | `site_r8` | Site-level scalar |
| `_PF` | `site_pft_r8` | Per PFT |
| `_SZ` | `site_size_r8` | Per size class |
| `_SZPF` | `site_size_pft_r8` | Per (size × PFT) |
| `_AP` | `site_age_r8` | Per patch age |
| `_APPF` | `site_agepft_r8` | Per (age × PFT) |
| `_APFC` | `site_agefuel_r8` | Per (age × fuel) |
| `_AC` | `site_coage_r8` | Per cohort-age bin |
| `_ACPF` | `site_coage_pft_r8` | Per (cohort age × PFT) |
| `_SZAP` | `site_scag_r8` | Per (size × age) |
| `_SZAPPF` | `site_scagpft_r8` | Per (size × age × PFT) |
| `_CD` | `site_cdam_r8` | Per crown-damage class |
| `_CDPF` | `site_cdpf_r8` | Per (size × damage × PFT) |
| `_CL` | `site_can_r8` | Per canopy layer |
| `_CLLL` | `site_cnlf_r8` | Per (canopy × leaf layer) |
| `_CLLLPF` | `site_cnlfpft_r8` | Per (canopy × leaf × PFT) |
| `_CLSZPF` | `site_clscpf_r8` | Per (canopy × size × PFT) (conditional) |
| `_SL` | `site_soil_r8` | Per soil layer |
| `_HT` | `site_height_r8` | Per height bin |
| `_EL` | `site_elem_r8` | Per chemical element |
| `_ELDC` | `site_elcwd_r8` | Per (element × CWD) |
| `_FC` | `site_fuel_r8` | Per fuel class |
| `_DC` | `site_cwdsc_r8` | Per CWD size class |
| `_LU` | `site_landuse_r8` | Per land-use category (NEW) |
| `_LUPF` | `site_landuse_pft_r8` | Per (land-use × PFT) (NEW) |
| `_LULU` | `site_landuse_landuse_r8` | Per (land-use × land-use) (NEW) |
| `_SE_SZ` | (variant) | Secondary-forest-only variant of a `_SZ` quantity (only one survivor at e027a40: `FATES_MORTALITY_CANOPY_SE_SZ`) |

### Important: `_SZPF`, not `_SCPF`

`_SCPF` is an internal-source-only suffix (e.g., `ih_nplant_si_scpf`). The actual NetCDF output suffix for size × PFT is `_SZPF`. Use `FATES_NPLANT_SZPF`, `FATES_MORTALITY_CANOPY_SZPF`, `FATES_DDBH_SZPF`. Similarly, the `_Z` infix in `FATES_PARSUN_Z_*` and `FATES_LAISUN_Z_*` (e85d997) **has been dropped at e027a40**: the correct names are `FATES_PARSUN_CLLL`, `FATES_PARSUN_CLLLPF`, `FATES_PARSUN_CL`, `FATES_LAISUN_CLLL`, `FATES_LAISUN_CLLLPF`, `FATES_LAISUN_CL`. `FATES_FIRE_AREA` does not exist; fractional burned area is `FATES_BURNFRAC` (and the new wildfire/rxfire-specific `FATES_WILDFIRE_BURNFRAC` / `FATES_RXFIRE_BURNFRAC`).

## Variable Inventory by Suffix Family (e027a40)

The 493 CDL-registered variables grouped by suffix. A complete alphabetical listing follows at the end.

### Site-scale scalars (`site_r8`, no suffix or special)

(146 variables in CDL)

`FATES_AREA_PLANTS`, `FATES_AREA_TREES`, `FATES_AUTORESP`, `FATES_AUTORESP_CANOPY`, `FATES_AUTORESP_USTORY`, `FATES_BA_WEIGHTED_HEIGHT`, `FATES_BURNFRAC`, `FATES_CANOPYAREA`, `FATES_CANOPY_SPREAD`, `FATES_CANOPY_VEGC`, `FATES_CA_WEIGHTED_HEIGHT`, `FATES_CBALANCE_ERROR`, `FATES_COLD_STATUS`, `FATES_CROOTMAINTAR`, `FATES_CROOT_ALLOC`, `FATES_DAYSINCE_COLDLEAFOFF`, `FATES_DAYSINCE_COLDLEAFON`, `FATES_DEMOTION_CARBONFLUX`, `FATES_DISTURBANCE_RATE_FIRE`, `FATES_DISTURBANCE_RATE_LOGGING`, `FATES_DISTURBANCE_RATE_TREEFALL`, `FATES_EFFECT_WSPEED`, `FATES_ELAI`, `FATES_EXCESS_RESP`, `FATES_FDI`, `FATES_FIRE_CLOSS`, `FATES_FIRE_CLOSS_LANDUSECHANGE`, `FATES_FIRE_CLOSS_LIVEFUELS`, `FATES_FIRE_INTENSITY`, `FATES_FIRE_INTENSITY_BURNFRAC`, `FATES_FRACTION`, `FATES_FROOTC`, `FATES_FROOTMAINTAR`, `FATES_FROOTN`, `FATES_FROOTP`, `FATES_FROOT_ALLOC`, `FATES_FUELCONSUMED`, `FATES_FUEL_AMOUNT`, `FATES_FUEL_BULKD`, `FATES_FUEL_EFF_MOIST`, `FATES_FUEL_MEF`, `FATES_FUEL_SAV`, `FATES_GDD`, `FATES_GPP`, `FATES_GPP_CANOPY`, `FATES_GPP_USTORY`, `FATES_GRAZING`, `FATES_GROWTH_RESP`, `FATES_HARVEST_DEBT`, `FATES_HARVEST_DEBT_SEC`, `FATES_HARVEST_WOODPROD_C_FLUX`, `FATES_HET_RESP`, `FATES_IGNITIONS`, `FATES_L2FR`, `FATES_LAI`, `FATES_LBLAYER_COND`, `FATES_LEAFC`, `FATES_LEAFMAINTAR`, `FATES_LEAFN`, `FATES_LEAFP`, `FATES_LEAF_ALLOC`, `FATES_LITTER_IN`, `FATES_LITTER_OUT`, `FATES_LSTEMMAINTAR`, `FATES_LUCHANGE_WOODPROD_C_FLUX`, `FATES_MAINT_RESP`, `FATES_MAINT_RESP_UNREDUCED`, `FATES_MEAN_95PCTILE_HEIGHT`, `FATES_MORTALITY_CFLUX_CANOPY`, `FATES_MORTALITY_CFLUX_USTORY`, `FATES_NCHILLDAYS`, `FATES_NCL`, `FATES_NCOHORTS`, `FATES_NCOLDDAYS`, `FATES_NDEMAND`, `FATES_NEFFLUX`, `FATES_NEP`, `FATES_NESTEROV_INDEX`, `FATES_NFIX_SYM`, `FATES_NH4UPTAKE`, `FATES_NIR_RAD_ERROR`, `FATES_NO3UPTAKE`, `FATES_NONSTRUCTC`, `FATES_NPATCHES`, `FATES_NPP`, `FATES_PATCHAREA`, `FATES_PDEMAND`, `FATES_PEFFLUX`, `FATES_PRIMARY_PATCHFUSION_ERR`, `FATES_PROMOTION_CARBONFLUX`, `FATES_PUPTAKE`, `FATES_REPROC`, `FATES_REPRON`, `FATES_REPROP`, `FATES_ROOTUPTAKE`, `FATES_ROOTWGT_SOILMATPOT`, `FATES_ROOTWGT_SOILVWC`, `FATES_ROOTWGT_SOILVWCSAT`, `FATES_ROS`, `FATES_RXFIRE_BURNABLE_FI`, `FATES_RXFIRE_BURNABLE_FINAL`, `FATES_RXFIRE_BURNABLE_FUEL`, `FATES_RXFIRE_BURNFRAC`, `FATES_RXFIRE_INTENSITY`, `FATES_RXFIRE_INTENSITY_BURNFRAC`, `FATES_RX_BURN_WINDOW`, `FATES_SAPFLOW`, `FATES_SAPWOODC`, `FATES_SAPWOODN`, `FATES_SAPWOODP`, `FATES_SEEDLING_POOL`, `FATES_SEEDS_IN`, `FATES_SEEDS_IN_LOCAL`, `FATES_SEED_ALLOC`, `FATES_SEED_BANK`, `FATES_STEM_ALLOC`, `FATES_STOMATAL_COND`, `FATES_STOREC`, `FATES_STOREC_TF`, `FATES_STOREN`, `FATES_STOREN_TF`, `FATES_STOREP`, `FATES_STOREP_TF`, `FATES_STORE_ALLOC`, `FATES_STRUCTC`, `FATES_TGROWTH`, `FATES_TLONGTERM`, `FATES_TRIMMING`, `FATES_TVEG`, `FATES_TVEG24`, `FATES_UNGERM_SEED_BANK`, `FATES_USTORY_VEGC`, `FATES_VEGC`, `FATES_VEGC_ABOVEGROUND`, `FATES_VEGH2O`, `FATES_VEGH2O_DEAD`, `FATES_VEGH2O_GROWTURN_ERR`, `FATES_VEGH2O_HYDRO_ERR`, `FATES_VEGH2O_RECRUIT`, `FATES_VEGN`, `FATES_VEGP`, `FATES_VIS_RAD_ERROR`, `FATES_WILDFIRE_BURNFRAC`, `FATES_WILDFIRE_INTENSITY`, `FATES_WILDFIRE_INTENSITY_BURNFRAC`, `FATES_ZSTAR`.

### Per-PFT (`site_pft_r8`, `_PF` suffix)

(35 variables) `FATES_CANOPYCROWNAREA_PF`, `FATES_CROWNAREA_PF`, `FATES_DAYSINCE_DROUGHTLEAFOFF_PF`, `FATES_DAYSINCE_DROUGHTLEAFON_PF`, `FATES_DROUGHT_STATUS_PF`, `FATES_ELONG_FACTOR_PF`, `FATES_GPP_PF`, `FATES_L2FR_CANOPY_REC_PF`, `FATES_L2FR_USTORY_REC_PF`, `FATES_LEAFC_PF`, `FATES_MEANLIQVOL_DROUGHTPHEN_PF`, `FATES_MEANSMP_DROUGHTPHEN_PF`, `FATES_MORTALITY_CFLUX_PF`, `FATES_MORTALITY_CSTARV_CFLUX_PF`, `FATES_MORTALITY_FIRE_CFLUX_PF`, `FATES_MORTALITY_HYDRO_CFLUX_PF`, `FATES_MORTALITY_PF`, `FATES_MORT_CSTARV_CONT_CFLUX_PF`, `FATES_NOCOMP_BURNEDAREA_PF`, `FATES_NOCOMP_NPATCHES_PF`, `FATES_NOCOMP_PATCHAREA_PF`, `FATES_NPLANT_PF`, `FATES_NPP_PF`, `FATES_RECRUITMENT_CFLUX_PF`, `FATES_RECRUITMENT_PF`, `FATES_SCORCH_HEIGHT_PF`, `FATES_SEEDLING_POOL_PF`, `FATES_SEEDS_IN_GRIDCELL_PF`, `FATES_SEEDS_IN_LOCAL_PF`, `FATES_SEEDS_IN_PF`, `FATES_SEEDS_OUT_GRIDCELL_PF`, `FATES_SEED_BANK_PF`, `FATES_STOREC_PF`, `FATES_UNGERM_SEED_BANK_PF`, `FATES_VEGC_PF`.

### Per-patch-age (`site_age_r8`, `_AP` suffix)

(22 variables) `FATES_BURNFRAC_AP`, `FATES_CANOPYAREA_AP`, `FATES_FIRE_INTENSITY_BURNFRAC_AP`, `FATES_FUEL_AMOUNT_AP`, `FATES_GPP_AP`, `FATES_LAI_AP`, `FATES_LBLAYER_COND_AP`, `FATES_NCL_AP`, `FATES_NPATCH_AP`, `FATES_NPP_AP`, `FATES_PATCHAREA_AP`, `FATES_PRIMARY_AREA_AP`, `FATES_RXFIRE_BURNFRAC_AP`, `FATES_RXFIRE_INTENSITY_BURNFRAC_AP`, `FATES_SECONDARY_AGB_ANTHROAGE_AP`, `FATES_SECONDARY_AREA_ANTHRO_AP`, `FATES_SECONDARY_AREA_AP`, `FATES_STOMATAL_COND_AP`, `FATES_VEGC_AP`, `FATES_WILDFIRE_BURNFRAC_AP`, `FATES_WILDFIRE_INTENSITY_BURNFRAC_AP`, `FATES_ZSTAR_AP`.

Per (age × PFT) (`_APPF`, 3 vars): `FATES_NPP_APPF`, `FATES_SCORCH_HEIGHT_APPF`, `FATES_VEGC_APPF`. Per (age × fuel class) (`_APFC`, 1 var): `FATES_FUEL_AMOUNT_APFC`.

### Per-size × PFT (`site_size_pft_r8`, `_SZPF` suffix)

(115 variables — most-populated suffix) Examples: `FATES_NPLANT_SZPF`, `FATES_NPLANT_CANOPY_SZPF`, `FATES_NPLANT_USTORY_SZPF`, `FATES_BASALAREA_SZPF`, `FATES_GROWTHFLUX_SZPF`, `FATES_GROWTHFLUX_FUSION_SZPF`, `FATES_DDBH_SZPF`, `FATES_DDBH_CANOPY_SZPF`, `FATES_DDBH_USTORY_SZPF`, `FATES_LEAFC_SZPF`, `FATES_LEAFC_CANOPY_SZPF`, `FATES_LEAFC_USTORY_SZPF`, `FATES_LEAFN_SZPF`, `FATES_LEAFP_SZPF`, `FATES_FROOTC_SZPF`, `FATES_FROOTN_SZPF`, `FATES_FROOTP_SZPF`, `FATES_SAPWOODC_SZPF`, `FATES_SAPWOODN_SZPF`, `FATES_SAPWOODP_SZPF`, `FATES_SAPWOOD_AREA_SZPF` (NEW), `FATES_STOREC_SZPF`, `FATES_STOREC_CANOPY_SZPF`, `FATES_STOREC_USTORY_SZPF`, `FATES_VEGC_SZPF`, `FATES_VEGC_ABOVEGROUND_SZPF`, `FATES_GPP_SZPF`, `FATES_NPP_SZPF`, `FATES_AUTORESP_SZPF`, `FATES_AUTORESP_CANOPY_SZPF`, `FATES_AUTORESP_USTORY_SZPF`, `FATES_RDARK_SZPF`, `FATES_C13DISC_SZPF`, the full mortality suite `FATES_MORTALITY_{AGESCEN,BACKGROUND,CANOPY,USTORY,CSTARV,FREEZING,HYDRAULIC,IMPACT,LOGGING,SENESCENCE,TERMINATION}_SZPF`, and the new fire-mortality split `FATES_MORTALITY_WILDFIRE_SZPF`, `FATES_MORTALITY_WILDFIRE_CAMBIAL_SZPF`, `FATES_MORTALITY_WILDFIRE_CROWN_SZPF`, `FATES_MORTALITY_RXFIRE_SZPF`, `FATES_MORTALITY_RXCAMBIAL_SZPF`, `FATES_MORTALITY_RXCROWN_SZPF`. Plus the new crown-area split `FATES_CROWNAREA_CANOPY_SZPF`, `FATES_CROWNAREA_USTORY_SZPF`. Also `FATES_NH4UPTAKE_SZPF`, `FATES_NO3UPTAKE_SZPF`, `FATES_PUPTAKE_SZPF`, `FATES_NDEMAND_SZPF`, `FATES_PDEMAND_SZPF`, `FATES_NEFFLUX_SZPF`, `FATES_PEFFLUX_SZPF`, `FATES_NFIX_SYM_SZPF`, `FATES_BTRAN_SZPF`, `FATES_TRAN_SZPF`, `FATES_ERRH2O_SZPF`, the hydraulics block `FATES_LEAF_H2O_SZPF`, `FATES_LEAF_H2OPOT_SZPF`, `FATES_LEAF_CONDFRAC_SZPF`, `FATES_STEM_*_SZPF`, `FATES_ABSROOT_*_SZPF`, `FATES_TRANSROOT_*_SZPF`, `FATES_SAPFLOW_SZPF`, `FATES_ITERH1_SZPF`, `FATES_ITERH2_SZPF`, `FATES_ROOTUPTAKE0_SZPF`, `FATES_ROOTUPTAKE10_SZPF`, `FATES_ROOTUPTAKE50_SZPF`, `FATES_ROOTUPTAKE100_SZPF`. (Conditional: `FATES_L2FR_CLSZPF` not in the standard CDL.)

### Per-size class only (`site_size_r8`, `_SZ` suffix)

(74 variables) Includes `FATES_BASALAREA_SZ`, `FATES_NPLANT_SZ`, `FATES_NPLANT_CANOPY_SZ`, `FATES_NPLANT_USTORY_SZ`, `FATES_VEGC_SZ`, `FATES_VEGC_ABOVEGROUND_SZ`, `FATES_LAI_CANOPY_SZ`, `FATES_LAI_USTORY_SZ`, `FATES_SAI_CANOPY_SZ`, `FATES_SAI_USTORY_SZ`, the canopy/understory growth-and-allocation blocks `FATES_*_CANOPY_SZ` / `FATES_*_USTORY_SZ` (CROOTMAINTAR, CROWNAREA, DDBH, FROOTCTURN, FROOTMAINTAR, FROOT_ALLOC, GROWAR, LEAFCTURN, LEAF_ALLOC, LSTEMMAINTAR, MAINTAR, RDARK, SAPWOODCTURN, SAPWOOD_ALLOC, SEED_ALLOC, SEED_PROD, STORECTURN, STORE_ALLOC, STRUCTCTURN, STRUCT_ALLOC, TRIMMING, YESTCANLEV), the per-size mortality block `FATES_MORTALITY_{AGESCEN,BACKGROUND,CANOPY,USTORY,CSTARV,FIRE,FREEZING,HYDRAULIC,IMPACT,LOGGING,SENESCENCE,TERMINATION,RXFIRE}_SZ`, plus `FATES_M3_MORTALITY_CANOPY_SZ`, `FATES_M3_MORTALITY_USTORY_SZ`, `FATES_DEMOTION_RATE_SZ`, `FATES_PROMOTION_RATE_SZ`, and the single `_SE_SZ` survivor `FATES_MORTALITY_CANOPY_SE_SZ`. (NPP_CANOPY_SZ and NPP_USTORY_SZ are also present.)

### Crown-damage dimensions (`_CD`, `_CDPF`)

(2 + 15 variables) `_CD`: `FATES_CROWNAREA_CANOPY_CD`, `FATES_CROWNAREA_USTORY_CD`. `_CDPF`: `FATES_DDBH_CDPF`, `FATES_DDBH_CANOPY_CDPF`, `FATES_DDBH_USTORY_CDPF`, `FATES_NPLANT_CDPF`, `FATES_NPLANT_CANOPY_CDPF`, `FATES_NPLANT_USTORY_CDPF`, `FATES_M11_CDPF`, `FATES_M11_MORTALITY_CANOPY_CDPF`, `FATES_M11_MORTALITY_USTORY_CDPF`, `FATES_M3_CDPF`, `FATES_M3_MORTALITY_CANOPY_CDPF`, `FATES_M3_MORTALITY_USTORY_CDPF`, `FATES_MORTALITY_CDPF`, `FATES_MORTALITY_CANOPY_CDPF`, `FATES_MORTALITY_USTORY_CDPF`.

### Cohort-age dimensions (`_AC`, `_ACPF`)

(2 + 2 variables) `FATES_MORTALITY_AGESCEN_AC`, `FATES_NPLANT_AC`, `FATES_MORTALITY_AGESCEN_ACPF`, `FATES_NPLANT_ACPF`.

### Size × Age (`_SZAP`, `_SZAPPF`)

(7 + 1 variables) `_SZAP`: `FATES_DDBH_CANOPY_SZAP`, `FATES_DDBH_USTORY_SZAP`, `FATES_MORTALITY_CANOPY_SZAP`, `FATES_MORTALITY_USTORY_SZAP`, `FATES_NPLANT_CANOPY_SZAP`, `FATES_NPLANT_SZAP`, `FATES_NPLANT_USTORY_SZAP`. `_SZAPPF`: `FATES_NPLANT_SZAPPF`.

### Canopy-layer × leaf-layer (`_CL`, `_CLLL`, `_CLLLPF`)

(5 + 8 + 7 variables; **no `_Z` infix at e027a40**)

`_CL`: `FATES_CROWNAREA_CL`, `FATES_LAISHA_CL`, `FATES_LAISUN_CL`, `FATES_PARSHA_CL`, `FATES_PARSUN_CL`.

`_CLLL`: `FATES_CROWNAREA_CLLL`, `FATES_LAISHA_CLLL`, `FATES_LAISUN_CLLL`, `FATES_NET_C_UPTAKE_CLLL`, `FATES_PARPROF_DIF_CLLL`, `FATES_PARPROF_DIR_CLLL`, `FATES_PARSHA_CLLL`, `FATES_PARSUN_CLLL`.

`_CLLLPF`: `FATES_CROWNFRAC_CLLLPF` (NEW), `FATES_LAISHA_CLLLPF`, `FATES_LAISUN_CLLLPF`, `FATES_PARPROF_DIF_CLLLPF`, `FATES_PARPROF_DIR_CLLLPF`, `FATES_PARSHA_CLLLPF`, `FATES_PARSUN_CLLLPF`.

The `FATES_FABD_*` and `FATES_FABI_*` (12 vars at e85d997) **no longer exist**.

### Per-element (`_EL`, `_ELDC`)

(15 + 1 variables) `_EL`: `FATES_ERROR_EL`, `FATES_FIRE_FLUX_EL`, `FATES_INTERR_LITTER_EL` (NEW), `FATES_INTERR_LIVEVEG_EL` (NEW), `FATES_LITTER_AG_CWD_EL`, `FATES_LITTER_AG_FINE_EL`, `FATES_LITTER_BG_CWD_EL`, `FATES_LITTER_BG_FINE_EL`, `FATES_LITTER_IN_EL`, `FATES_LITTER_OUT_EL`, `FATES_SEEDS_IN_EXTERN_EL`, `FATES_SEEDS_IN_LOCAL_EL`, `FATES_SEED_BANK_EL`, `FATES_SEED_DECAY_EL`, `FATES_SEED_GERM_EL`. `_ELDC`: `FATES_LITTER_CWD_ELDC`.

### Fuel and CWD (`_FC`, `_DC`)

(3 + 6 variables) `_FC`: `FATES_FUEL_AMOUNT_FC`, `FATES_FUEL_BURNT_BURNFRAC_FC`, `FATES_FUEL_MOISTURE_FC`. `_DC`: `FATES_CWD_ABOVEGROUND_DC`, `FATES_CWD_ABOVEGROUND_IN_DC`, `FATES_CWD_ABOVEGROUND_OUT_DC`, `FATES_CWD_BELOWGROUND_DC`, `FATES_CWD_BELOWGROUND_IN_DC`, `FATES_CWD_BELOWGROUND_OUT_DC`.

### Soil and height (`_SL`, `_HT`)

(6 + 2 variables) `_SL`: `FATES_FRAGMENTATION_SCALER_SL`, `FATES_FROOTC_SL`, `FATES_ROOTUPTAKE_SL`, `FATES_SOILMATPOT_SL`, `FATES_SOILVWC_SL`, `FATES_SOILVWCSAT_SL`. `_HT`: `FATES_CANOPYAREA_HT`, `FATES_LEAFAREA_HT`.

### Land Use (`_LU`, `_LUPF`, `_LULU`) — NEW at e027a40

(11 + 2 + 2 variables)

`_LU`: `FATES_BURNEDAREA_LU`, `FATES_GPP_LU`, `FATES_LHFLUX_LU`, `FATES_NETLW_LU`, `FATES_NPP_LU`, `FATES_PATCHAREA_LU`, `FATES_SHFLUX_LU`, `FATES_SWABS_LU`, `FATES_TSA_LU`, `FATES_TVEG_LU`, `FATES_VEGC_LU`.

`_LUPF`: `FATES_NOCOMP_PATCHAREA_LUPF`, `FATES_VEGC_LUPF`.

`_LULU`: `FATES_DISTURBANCE_RATE_MATRIX_LULU`, `FATES_TRANSITION_MATRIX_LULU`.

These collectively replace the e85d997 `*_SECONDARY` and `*_SE_PF` suffix families. To get "secondary forest GPP" at e027a40, take `FATES_GPP_LU` and slice the `fates_levlanduse` axis at the secondary index.

### Removed at e027a40 (relative to e85d997)

The wiki at e85d997 listed these names that no longer exist at e027a40 (do not query a history file for them):

- All 12 `FATES_FABD_*` / `FATES_FABI_*` absorbed-radiation vars.
- All 12 `FATES_PARSUN_Z_*` / `FATES_LAISUN_Z_*` / `FATES_PARSHA_Z_*` / `FATES_LAISHA_Z_*` (drop the `_Z` to get the e027a40 names).
- `FATES_AR`, `FATES_AR_CANOPY`, `FATES_AR_UNDERSTORY` (renamed `FATES_AUTORESP*`).
- All `FATES_*_SECONDARY` scalars (`FATES_AUTORESP_SECONDARY`, `FATES_GPP_SECONDARY`, `FATES_NPP_SECONDARY`, `FATES_LAI_SECONDARY`, `FATES_MAINT_RESP_SECONDARY`, `FATES_GROWTH_RESP_SECONDARY`, `FATES_NCOHORTS_SECONDARY`, `FATES_NPATCHES_SECONDARY`, `FATES_SECONDARY_FOREST_FRACTION`, `FATES_SECONDARY_FOREST_VEGC`).
- All `FATES_*_SE_PF` per-PFT secondary vars (`FATES_VEGC_SE_PF`, `FATES_GPP_SE_PF`, `FATES_NPP_SE_PF`, `FATES_NPLANT_SEC_PF`).
- All `FATES_MORTALITY_*_SE_SZ` except `FATES_MORTALITY_CANOPY_SE_SZ`.
- `FATES_MORTALITY_FIRE_SZPF`, `FATES_MORTALITY_CAMBIALBURN_SZPF`, `FATES_MORTALITY_CROWNSCORCH_SZPF` (replaced by the WILDFIRE/RXFIRE pair).
- `FATES_HARVEST_CARBON_FLUX`, `FATES_WOOD_PRODUCT` (replaced by `FATES_HARVEST_WOODPROD_C_FLUX` and `FATES_LUCHANGE_WOODPROD_C_FLUX`).
- `FATES_FIRE_AREA` (does not exist; use `FATES_BURNFRAC`).

### Added at e027a40 (relative to e85d997)

Beyond the LU and WILDFIRE/RXFIRE families and `FATES_AUTORESP*` already noted: `FATES_GRAZING`, `FATES_NCL`, `FATES_ELAI`, `FATES_CANOPYAREA`, `FATES_PATCHAREA`, `FATES_ZSTAR`, `FATES_MEAN_95PCTILE_HEIGHT`, `FATES_PRIMARY_AREA_AP`, `FATES_SCORCH_HEIGHT_PF`, `FATES_SAPWOOD_AREA_SZPF`, `FATES_CROWNAREA_CANOPY_SZPF`, `FATES_CROWNAREA_USTORY_SZPF`, `FATES_CROWNFRAC_CLLLPF`, `FATES_VIS_RAD_ERROR`, `FATES_NIR_RAD_ERROR`, `FATES_INTERR_LIVEVEG_EL`, `FATES_INTERR_LITTER_EL`, `FATES_MORT_CSTARV_CONT_CFLUX_PF`, `FATES_RECRUITMENT_CFLUX_PF`, `FATES_SEEDS_IN_PF`, `FATES_SEEDS_IN_LOCAL_PF`, `FATES_SEED_BANK_PF`, `FATES_UNGERM_SEED_BANK_PF`, `FATES_SEEDLING_POOL_PF`, `FATES_FIRE_CLOSS_LIVEFUELS`, `FATES_FIRE_CLOSS_LANDUSECHANGE`, `FATES_RX_BURN_WINDOW`, `FATES_SECONDARY_AGB_ANTHROAGE_AP`, `FATES_SECONDARY_AREA_AP`, `FATES_SECONDARY_AREA_ANTHRO_AP`, `FATES_PRIMARY_AREA_AP`.

## Complete alphabetical inventory (e027a40, regenerated from CDL)

The 493 unique `FATES_*` names registered in the standard CDL. If a name does not appear here, it is not in the standard build. (`FATES_L2FR_CLSZPF` is conditionally registered in the source but absent from the standard CDL.)

```
FATES_ABOVEGROUND_MORT_SZPF                  FATES_MORTALITY_RXCROWN_SZPF
FATES_ABOVEGROUND_PROD_SZPF                  FATES_MORTALITY_RXFIRE_SZ
FATES_ABSROOT_CONDFRAC_SZPF                  FATES_MORTALITY_RXFIRE_SZPF
FATES_ABSROOT_H2OPOT_SZPF                    FATES_MORTALITY_SENESCENCE_SZ
FATES_ABSROOT_H2O_SZPF                       FATES_MORTALITY_SENESCENCE_SZPF
FATES_AGSAPMAINTAR_SZPF                      FATES_MORTALITY_TERMINATION_SZ
FATES_AGSAPWOOD_ALLOC_SZPF                   FATES_MORTALITY_TERMINATION_SZPF
FATES_AREA_PLANTS                            FATES_MORTALITY_USTORY_CDPF
FATES_AREA_TREES                             FATES_MORTALITY_USTORY_SZ
FATES_AUTORESP                               FATES_MORTALITY_USTORY_SZAP
FATES_AUTORESP_CANOPY                        FATES_MORTALITY_USTORY_SZPF
FATES_AUTORESP_CANOPY_SZPF                   FATES_MORTALITY_WILDFIRE_CAMBIAL_SZPF
FATES_AUTORESP_SZPF                          FATES_MORTALITY_WILDFIRE_CROWN_SZPF
FATES_AUTORESP_USTORY                        FATES_MORTALITY_WILDFIRE_SZPF
FATES_AUTORESP_USTORY_SZPF                   FATES_MORT_CSTARV_CONT_CFLUX_PF
FATES_BASALAREA_SZ                           FATES_NCHILLDAYS
FATES_BASALAREA_SZPF                         FATES_NCL
FATES_BA_WEIGHTED_HEIGHT                     FATES_NCL_AP
FATES_BGSAPMAINTAR_SZPF                      FATES_NCOHORTS
FATES_BGSAPWOOD_ALLOC_SZPF                   FATES_NCOLDDAYS
FATES_BGSTRUCT_ALLOC_SZPF                    FATES_NDEMAND
FATES_BTRAN_SZPF                             FATES_NDEMAND_SZPF
FATES_BURNEDAREA_LU                          FATES_NEFFLUX
FATES_BURNFRAC                               FATES_NEFFLUX_SZPF
FATES_BURNFRAC_AP                            FATES_NEP
FATES_C13DISC_SZPF                           FATES_NESTEROV_INDEX
FATES_CANOPYAREA                             FATES_NETLW_LU
FATES_CANOPYAREA_AP                          FATES_NET_C_UPTAKE_CLLL
FATES_CANOPYAREA_HT                          FATES_NFIX_SYM
FATES_CANOPYCROWNAREA_PF                     FATES_NFIX_SYM_SZPF
FATES_CANOPY_SPREAD                          FATES_NH4UPTAKE
FATES_CANOPY_VEGC                            FATES_NH4UPTAKE_SZPF
FATES_CA_WEIGHTED_HEIGHT                     FATES_NIR_RAD_ERROR
FATES_CBALANCE_ERROR                         FATES_NO3UPTAKE
FATES_COLD_STATUS                            FATES_NO3UPTAKE_SZPF
FATES_CROOTMAINTAR                           FATES_NOCOMP_BURNEDAREA_PF
FATES_CROOTMAINTAR_CANOPY_SZ                 FATES_NOCOMP_NPATCHES_PF
FATES_CROOTMAINTAR_USTORY_SZ                 FATES_NOCOMP_PATCHAREA_LUPF
FATES_CROOT_ALLOC                            FATES_NOCOMP_PATCHAREA_PF
FATES_CROWNAREA_CANOPY_CD                    FATES_NONSTRUCTC
FATES_CROWNAREA_CANOPY_SZ                    FATES_NPATCHES
FATES_CROWNAREA_CANOPY_SZPF                  FATES_NPATCH_AP
FATES_CROWNAREA_CL                           FATES_NPLANT_AC
FATES_CROWNAREA_CLLL                         FATES_NPLANT_ACPF
FATES_CROWNAREA_PF                           FATES_NPLANT_CANOPY_CDPF
FATES_CROWNAREA_USTORY_CD                    FATES_NPLANT_CANOPY_SZ
FATES_CROWNAREA_USTORY_SZ                    FATES_NPLANT_CANOPY_SZAP
FATES_CROWNAREA_USTORY_SZPF                  FATES_NPLANT_CANOPY_SZPF
FATES_CROWNFRAC_CLLLPF                       FATES_NPLANT_CDPF
FATES_CWD_ABOVEGROUND_DC                     FATES_NPLANT_PF
FATES_CWD_ABOVEGROUND_IN_DC                  FATES_NPLANT_SZ
FATES_CWD_ABOVEGROUND_OUT_DC                 FATES_NPLANT_SZAP
FATES_CWD_BELOWGROUND_DC                     FATES_NPLANT_SZAPPF
FATES_CWD_BELOWGROUND_IN_DC                  FATES_NPLANT_SZPF
FATES_CWD_BELOWGROUND_OUT_DC                 FATES_NPLANT_USTORY_CDPF
FATES_DAYSINCE_COLDLEAFOFF                   FATES_NPLANT_USTORY_SZ
FATES_DAYSINCE_COLDLEAFON                    FATES_NPLANT_USTORY_SZAP
FATES_DAYSINCE_DROUGHTLEAFOFF_PF             FATES_NPLANT_USTORY_SZPF
FATES_DAYSINCE_DROUGHTLEAFON_PF              FATES_NPP
FATES_DDBH_CANOPY_CDPF                       FATES_NPP_AP
FATES_DDBH_CANOPY_SZ                         FATES_NPP_APPF
FATES_DDBH_CANOPY_SZAP                       FATES_NPP_CANOPY_SZ
FATES_DDBH_CANOPY_SZPF                       FATES_NPP_LU
FATES_DDBH_CDPF                              FATES_NPP_PF
FATES_DDBH_SZPF                              FATES_NPP_SZPF
FATES_DDBH_USTORY_CDPF                       FATES_NPP_USTORY_SZ
FATES_DDBH_USTORY_SZ                         FATES_PARPROF_DIF_CLLL
FATES_DDBH_USTORY_SZAP                       FATES_PARPROF_DIF_CLLLPF
FATES_DDBH_USTORY_SZPF                       FATES_PARPROF_DIR_CLLL
FATES_DEMOTION_CARBONFLUX                    FATES_PARPROF_DIR_CLLLPF
FATES_DEMOTION_RATE_SZ                       FATES_PARSHA_CL
FATES_DISTURBANCE_RATE_FIRE                  FATES_PARSHA_CLLL
FATES_DISTURBANCE_RATE_LOGGING               FATES_PARSHA_CLLLPF
FATES_DISTURBANCE_RATE_MATRIX_LULU           FATES_PARSUN_CL
FATES_DISTURBANCE_RATE_TREEFALL              FATES_PARSUN_CLLL
FATES_DROUGHT_STATUS_PF                      FATES_PARSUN_CLLLPF
FATES_EFFECT_WSPEED                          FATES_PATCHAREA
FATES_ELAI                                   FATES_PATCHAREA_AP
FATES_ELONG_FACTOR_PF                        FATES_PATCHAREA_LU
FATES_ERRH2O_SZPF                            FATES_PDEMAND
FATES_ERROR_EL                               FATES_PDEMAND_SZPF
FATES_EXCESS_RESP                            FATES_PEFFLUX
FATES_FDI                                    FATES_PEFFLUX_SZPF
FATES_FIRE_CLOSS                             FATES_PRIMARY_AREA_AP
FATES_FIRE_CLOSS_LANDUSECHANGE               FATES_PRIMARY_PATCHFUSION_ERR
FATES_FIRE_CLOSS_LIVEFUELS                   FATES_PROMOTION_CARBONFLUX
FATES_FIRE_FLUX_EL                           FATES_PROMOTION_RATE_SZ
FATES_FIRE_INTENSITY                         FATES_PUPTAKE
FATES_FIRE_INTENSITY_BURNFRAC                FATES_PUPTAKE_SZPF
FATES_FIRE_INTENSITY_BURNFRAC_AP             FATES_RDARK_CANOPY_SZ
FATES_FRACTION                               FATES_RDARK_SZPF
FATES_FRAGMENTATION_SCALER_SL                FATES_RDARK_USTORY_SZ
FATES_FROOTC                                 FATES_RECRUITMENT_CFLUX_PF
FATES_FROOTCTURN_CANOPY_SZ                   FATES_RECRUITMENT_PF
FATES_FROOTCTURN_USTORY_SZ                   FATES_REPROC
FATES_FROOTC_SL                              FATES_REPROC_SZPF
FATES_FROOTC_SZPF                            FATES_REPRON
FATES_FROOTMAINTAR                           FATES_REPRON_SZPF
FATES_FROOTMAINTAR_CANOPY_SZ                 FATES_REPROP
FATES_FROOTMAINTAR_SZPF                      FATES_REPROP_SZPF
FATES_FROOTMAINTAR_USTORY_SZ                 FATES_ROOTUPTAKE
FATES_FROOTN                                 FATES_ROOTUPTAKE0_SZPF
FATES_FROOTN_SZPF                            FATES_ROOTUPTAKE100_SZPF
FATES_FROOTP                                 FATES_ROOTUPTAKE10_SZPF
FATES_FROOTP_SZPF                            FATES_ROOTUPTAKE50_SZPF
FATES_FROOT_ALLOC                            FATES_ROOTUPTAKE_SL
FATES_FROOT_ALLOC_CANOPY_SZ                  FATES_ROOTWGT_SOILMATPOT
FATES_FROOT_ALLOC_SZPF                       FATES_ROOTWGT_SOILVWC
FATES_FROOT_ALLOC_USTORY_SZ                  FATES_ROOTWGT_SOILVWCSAT
FATES_FUELCONSUMED                           FATES_ROS
FATES_FUEL_AMOUNT                            FATES_RXFIRE_BURNABLE_FI
FATES_FUEL_AMOUNT_AP                         FATES_RXFIRE_BURNABLE_FINAL
FATES_FUEL_AMOUNT_APFC                       FATES_RXFIRE_BURNABLE_FUEL
FATES_FUEL_AMOUNT_FC                         FATES_RXFIRE_BURNFRAC
FATES_FUEL_BULKD                             FATES_RXFIRE_BURNFRAC_AP
FATES_FUEL_BURNT_BURNFRAC_FC                 FATES_RXFIRE_INTENSITY
FATES_FUEL_EFF_MOIST                         FATES_RXFIRE_INTENSITY_BURNFRAC
FATES_FUEL_MEF                               FATES_RXFIRE_INTENSITY_BURNFRAC_AP
FATES_FUEL_MOISTURE_FC                       FATES_RX_BURN_WINDOW
FATES_FUEL_SAV                               FATES_SAI_CANOPY_SZ
FATES_GDD                                    FATES_SAI_USTORY_SZ
FATES_GPP                                    FATES_SAPFLOW
FATES_GPP_AP                                 FATES_SAPFLOW_SZPF
FATES_GPP_CANOPY                             FATES_SAPWOODC
FATES_GPP_CANOPY_SZPF                        FATES_SAPWOODCTURN_CANOPY_SZ
FATES_GPP_LU                                 FATES_SAPWOODCTURN_USTORY_SZ
FATES_GPP_PF                                 FATES_SAPWOODC_SZPF
FATES_GPP_SZPF                               FATES_SAPWOODN
FATES_GPP_USTORY                             FATES_SAPWOODN_SZPF
FATES_GPP_USTORY_SZPF                        FATES_SAPWOODP
FATES_GRAZING                                FATES_SAPWOODP_SZPF
FATES_GROWAR_CANOPY_SZ                       FATES_SAPWOOD_ALLOC_CANOPY_SZ
FATES_GROWAR_SZPF                            FATES_SAPWOOD_ALLOC_USTORY_SZ
FATES_GROWAR_USTORY_SZ                       FATES_SAPWOOD_AREA_SZPF
FATES_GROWTHFLUX_FUSION_SZPF                 FATES_SCORCH_HEIGHT_APPF
FATES_GROWTHFLUX_SZPF                        FATES_SCORCH_HEIGHT_PF
FATES_GROWTH_RESP                            FATES_SECONDARY_AGB_ANTHROAGE_AP
FATES_HARVEST_DEBT                           FATES_SECONDARY_AREA_ANTHRO_AP
FATES_HARVEST_DEBT_SEC                       FATES_SECONDARY_AREA_AP
FATES_HARVEST_WOODPROD_C_FLUX                FATES_SEEDLING_POOL
FATES_HET_RESP                               FATES_SEEDLING_POOL_PF
FATES_IGNITIONS                              FATES_SEEDS_IN
FATES_INTERR_LITTER_EL                       FATES_SEEDS_IN_EXTERN_EL
FATES_INTERR_LIVEVEG_EL                      FATES_SEEDS_IN_GRIDCELL_PF
FATES_ITERH1_SZPF                            FATES_SEEDS_IN_LOCAL
FATES_ITERH2_SZPF                            FATES_SEEDS_IN_LOCAL_EL
FATES_L2FR                                   FATES_SEEDS_IN_LOCAL_PF
FATES_L2FR_CANOPY_REC_PF                     FATES_SEEDS_IN_PF
FATES_L2FR_USTORY_REC_PF                     FATES_SEEDS_OUT_GRIDCELL_PF
FATES_LAI                                    FATES_SEED_ALLOC
FATES_LAISHA_CL                              FATES_SEED_ALLOC_CANOPY_SZ
FATES_LAISHA_CLLL                            FATES_SEED_ALLOC_SZPF
FATES_LAISHA_CLLLPF                          FATES_SEED_ALLOC_USTORY_SZ
FATES_LAISUN_CL                              FATES_SEED_BANK
FATES_LAISUN_CLLL                            FATES_SEED_BANK_EL
FATES_LAISUN_CLLLPF                          FATES_SEED_BANK_PF
FATES_LAI_AP                                 FATES_SEED_DECAY_EL
FATES_LAI_CANOPY_SZ                          FATES_SEED_GERM_EL
FATES_LAI_CANOPY_SZPF                        FATES_SEED_PROD_CANOPY_SZ
FATES_LAI_USTORY_SZ                          FATES_SEED_PROD_USTORY_SZ
FATES_LAI_USTORY_SZPF                        FATES_SHFLUX_LU
FATES_LBLAYER_COND                           FATES_SOILMATPOT_SL
FATES_LBLAYER_COND_AP                        FATES_SOILVWCSAT_SL
FATES_LEAFAREA_HT                            FATES_SOILVWC_SL
FATES_LEAFC                                  FATES_STEM_ALLOC
FATES_LEAFCTURN_CANOPY_SZ                    FATES_STEM_CONDFRAC_SZPF
FATES_LEAFCTURN_USTORY_SZ                    FATES_STEM_H2OPOT_SZPF
FATES_LEAFC_CANOPY_SZPF                      FATES_STEM_H2O_SZPF
FATES_LEAFC_PF                               FATES_STOMATAL_COND
FATES_LEAFC_SZPF                             FATES_STOMATAL_COND_AP
FATES_LEAFC_USTORY_SZPF                      FATES_STOREC
FATES_LEAFMAINTAR                            FATES_STORECTURN_CANOPY_SZ
FATES_LEAFN                                  FATES_STORECTURN_USTORY_SZ
FATES_LEAFN_SZPF                             FATES_STOREC_CANOPY_SZPF
FATES_LEAFP                                  FATES_STOREC_PF
FATES_LEAFP_SZPF                             FATES_STOREC_SZPF
FATES_LEAF_ALLOC                             FATES_STOREC_TF
FATES_LEAF_ALLOC_CANOPY_SZ                   FATES_STOREC_TF_CANOPY_SZPF
FATES_LEAF_ALLOC_SZPF                        FATES_STOREC_TF_USTORY_SZPF
FATES_LEAF_ALLOC_USTORY_SZ                   FATES_STOREC_USTORY_SZPF
FATES_LEAF_CONDFRAC_SZPF                     FATES_STOREN
FATES_LEAF_H2OPOT_SZPF                       FATES_STOREN_SZPF
FATES_LEAF_H2O_SZPF                          FATES_STOREN_TF
FATES_LHFLUX_LU                              FATES_STOREN_TF_CANOPY_SZPF
FATES_LITTER_AG_CWD_EL                       FATES_STOREN_TF_USTORY_SZPF
FATES_LITTER_AG_FINE_EL                      FATES_STOREP
FATES_LITTER_BG_CWD_EL                       FATES_STOREP_SZPF
FATES_LITTER_BG_FINE_EL                      FATES_STOREP_TF
FATES_LITTER_CWD_ELDC                        FATES_STOREP_TF_CANOPY_SZPF
FATES_LITTER_IN                              FATES_STOREP_TF_USTORY_SZPF
FATES_LITTER_IN_EL                           FATES_STORE_ALLOC
FATES_LITTER_OUT                             FATES_STORE_ALLOC_CANOPY_SZ
FATES_LITTER_OUT_EL                          FATES_STORE_ALLOC_USTORY_SZ
FATES_LSTEMMAINTAR                           FATES_STRUCTC
FATES_LSTEMMAINTAR_CANOPY_SZ                 FATES_STRUCTCTURN_CANOPY_SZ
FATES_LSTEMMAINTAR_USTORY_SZ                 FATES_STRUCTCTURN_USTORY_SZ
FATES_LUCHANGE_WOODPROD_C_FLUX               FATES_STRUCT_ALLOC_CANOPY_SZ
FATES_M11_CDPF                               FATES_STRUCT_ALLOC_USTORY_SZ
FATES_M11_MORTALITY_CANOPY_CDPF              FATES_SWABS_LU
FATES_M11_MORTALITY_USTORY_CDPF              FATES_TGROWTH
FATES_M11_SZPF                               FATES_TLONGTERM
FATES_M3_CDPF                                FATES_TRANSITION_MATRIX_LULU
FATES_M3_MORTALITY_CANOPY_CDPF               FATES_TRANSROOT_CONDFRAC_SZPF
FATES_M3_MORTALITY_CANOPY_SZ                 FATES_TRANSROOT_H2OPOT_SZPF
FATES_M3_MORTALITY_CANOPY_SZPF               FATES_TRANSROOT_H2O_SZPF
FATES_M3_MORTALITY_USTORY_CDPF               FATES_TRAN_SZPF
FATES_M3_MORTALITY_USTORY_SZ                 FATES_TRIMMING
FATES_M3_MORTALITY_USTORY_SZPF               FATES_TRIMMING_CANOPY_SZ
FATES_MAINTAR_CANOPY_SZ                      FATES_TRIMMING_USTORY_SZ
FATES_MAINTAR_SZPF                           FATES_TSA_LU
FATES_MAINTAR_USTORY_SZ                      FATES_TVEG
FATES_MAINT_RESP                             FATES_TVEG24
FATES_MAINT_RESP_UNREDUCED                   FATES_TVEG_LU
FATES_MEANLIQVOL_DROUGHTPHEN_PF              FATES_UNGERM_SEED_BANK
FATES_MEANSMP_DROUGHTPHEN_PF                 FATES_UNGERM_SEED_BANK_PF
FATES_MEAN_95PCTILE_HEIGHT                   FATES_USTORY_VEGC
FATES_MORTALITY_AGESCEN_AC                   FATES_VEGC
FATES_MORTALITY_AGESCEN_ACPF                 FATES_VEGC_ABOVEGROUND
FATES_MORTALITY_AGESCEN_SZ                   FATES_VEGC_ABOVEGROUND_SZ
FATES_MORTALITY_AGESCEN_SZPF                 FATES_VEGC_ABOVEGROUND_SZPF
FATES_MORTALITY_BACKGROUND_SZ                FATES_VEGC_AP
FATES_MORTALITY_BACKGROUND_SZPF              FATES_VEGC_APPF
FATES_MORTALITY_CANOPY_CDPF                  FATES_VEGC_LU
FATES_MORTALITY_CANOPY_SE_SZ                 FATES_VEGC_LUPF
FATES_MORTALITY_CANOPY_SZ                    FATES_VEGC_PF
FATES_MORTALITY_CANOPY_SZAP                  FATES_VEGC_SZ
FATES_MORTALITY_CANOPY_SZPF                  FATES_VEGC_SZPF
FATES_MORTALITY_CDPF                         FATES_VEGH2O
FATES_MORTALITY_CFLUX_CANOPY                 FATES_VEGH2O_DEAD
FATES_MORTALITY_CFLUX_PF                     FATES_VEGH2O_GROWTURN_ERR
FATES_MORTALITY_CFLUX_USTORY                 FATES_VEGH2O_HYDRO_ERR
FATES_MORTALITY_CSTARV_CFLUX_PF              FATES_VEGH2O_RECRUIT
FATES_MORTALITY_CSTARV_SZ                    FATES_VEGN
FATES_MORTALITY_CSTARV_SZPF                  FATES_VEGN_SZPF
FATES_MORTALITY_FIRE_CFLUX_PF                FATES_VEGP
FATES_MORTALITY_FIRE_SZ                      FATES_VEGP_SZPF
FATES_MORTALITY_FREEZING_SZ                  FATES_VIS_RAD_ERROR
FATES_MORTALITY_FREEZING_SZPF                FATES_WILDFIRE_BURNFRAC
FATES_MORTALITY_HYDRAULIC_SZ                 FATES_WILDFIRE_BURNFRAC_AP
FATES_MORTALITY_HYDRAULIC_SZPF               FATES_WILDFIRE_INTENSITY
FATES_MORTALITY_HYDRO_CFLUX_PF               FATES_WILDFIRE_INTENSITY_BURNFRAC
FATES_MORTALITY_IMPACT_SZ                    FATES_WILDFIRE_INTENSITY_BURNFRAC_AP
FATES_MORTALITY_IMPACT_SZPF                  FATES_YESTCANLEV_CANOPY_SZ
FATES_MORTALITY_LOGGING_SZ                   FATES_YESTCANLEV_USTORY_SZ
FATES_MORTALITY_LOGGING_SZPF                 FATES_ZSTAR
FATES_MORTALITY_PF                           FATES_ZSTAR_AP
FATES_MORTALITY_RXCAMBIAL_SZPF
```

This list is the canonical authority — if a name does not appear here (and is not the conditionally-built `FATES_L2FR_CLSZPF`), it is not registered in e027a40.

## Index-to-Bin Mapping Functions

The size and age class indexing functions live in `main/FatesSizeAgeTypeIndicesMod.F90` (not `biogeochem/`):

| Function | Inputs | Outputs |
|---|---|---|
| `sizetype_class_index(dbh, pft)` | cohort DBH, PFT | `size_class`, `size_by_pft_class` |
| `get_sizeage_class_index(dbh, age)` | cohort DBH, patch age | `iscag` (linear index into `levscag`) |
| `get_sizeagepft_class_index(dbh, age, pft)` | cohort DBH, age, PFT | `iscagpft` (linear index into `levscagpft`) |
| `get_agepft_class_index(age, pft)` | age, PFT | `iagepft` |
| `get_age_class_index(age)` | patch age | `iage` |
| `get_layersizetype_class_index(canopy_layer, dbh, pft)` | canopy layer, DBH, PFT | `iclscpf` |

These are called during history update (once per cohort per timestep) and during cohort initialization. The land-use × PFT and land-use × land-use multiplexing (for the new `_LUPF` and `_LULU` outputs) is row-major over (`n_landuse`, `numpft`) and (`n_landuse`, `n_landuse`) respectively.

## Summary

FATES's history variables use a two-pronged naming system: **internal** module-level integer indices (`ih_*`) that exist only in Fortran source, and **user-facing** NetCDF variable names (like `FATES_NPLANT_SZPF`, `FATES_PARSUN_CLLL`) that are what you actually see in a history file. Confusing the two is the single most common source of "variable not found" errors in post-processing. Always use the actual `vname=` strings (which this page lists verbatim) when constructing xarray/Python or NCO queries against a FATES history file pinned to e027a40.
