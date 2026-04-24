# History Variables and Dimensions

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

**Relevant source files:**
- `main/FatesHistoryInterfaceMod.F90`
- `main/FatesHistoryVariableType.F90`
- `main/FatesIODimensionsMod.F90`
- `main/FatesIOVariableKindMod.F90`
- `main/FatesInterfaceMod.F90`
- `main/FatesInterfaceTypesMod.F90`
- `main/FatesSizeAgeTypeIndicesMod.F90`

## Purpose and Scope

This page documents the actual FATES history variables registered in `e85d997` and the dimension system they use. It is the canonical reference for writing post-processing scripts against FATES history files: if you grep a history NetCDF for a name that is not in the table below, it does not exist.

For the mechanics of how these variables are accumulated and written, see [History Update Pipeline](pipeline.md). For the overall architecture, see [History Output System](index.md).

## Base Dimensions

Base dimensions are the fundamental axes along which variables can be indexed. Their sizes are determined by model configuration (parameter file, PFT count, etc.).

| Base dimension | Description | Typical size |
|---|---|---|
| `column` | Host model gridcell/column (FATES site) | `nsites` |
| `levsoil` | Vertical soil layer | `nlevsoil` |
| `levpft` | Plant functional type | `numpft` (12–18 typical) |
| `levscls` | Cohort diameter size class | `nlevsclass` (commonly 13) |
| `levage` | Patch age class | `nlevage` (4–7 typical) |
| `levcoage` | Cohort age class | `nlevcoage` |
| `levcan` | Canopy layer | `nclmax` (2: canopy, understory) |
| `levleaf` | Leaf layer within canopy | `nlevleaf` |
| `levcwdsc` | Coarse woody debris size class | `ncwd` (4) |
| `levfuel` | Fuel size class | `nfsc` (6) |
| `levheight` | Height bin | `nlevheight` |
| `levdamage` | Crown damage severity | `nlevdamage` |
| `levelem` | Chemical element (C, N, P) | `num_elements` |

Sources: `(main/FatesHistoryInterfaceMod.F90:763-1021)`

## Multiplexed Dimensions

Multiplexed dimensions flatten two or three base dimensions into one linear index so that variables can be written as 2-D (`site × multiplexed`) arrays in NetCDF, despite representing 3-D or 4-D information.

| Multiplexed dim | Components | Total size | Used for |
|---|---|---|---|
| `levscpf` | size × PFT | `nlevsclass × numpft` | Cohort quantities binned by size and PFT (most common) |
| `levscag` | size × patch age | `nlevsclass × nlevage` | Size-age distributions |
| `levscagpft` | size × age × PFT | `nlevsclass × nlevage × numpft` | Full size-age-PFT distributions |
| `levagepft` | age × PFT | `nlevage × numpft` | Patch age × PFT |
| `levcnlf` | canopy × leaf layer | `nclmax × nlevleaf` | Radiation profiles |
| `levcnlfpft` | canopy × leaf × PFT | `nclmax × nlevleaf × numpft` | PFT-specific radiation |
| `levagefuel` | age × fuel size | `nlevage × nfsc` | Fuel load by patch age |
| `levcdpf` | size × damage × PFT (3-D) | `nlevsclass × nlevdamage × numpft` | Crown damage × size × PFT |
| `levelcwd` | element × CWD size | `num_elements × ncwd` | CWD pools by element |
| `levelpft` | element × PFT | `num_elements × numpft` | Element pools by PFT |
| `levelage` | element × patch age | `num_elements × nlevage` | Element pools by age |
| `levclscpf` | canopy layer × size × PFT | `nclmax × nlevsclass × numpft` | Canopy-layer-stratified size × PFT |

Note: `levcdpf` is 3-D (`size × damage × PFT`), allocated as `nlevsclass × nlevdamage × numpft`. Source: `main/FatesInterfaceMod.F90:1168-1170`:

```fortran
allocate( fates_hdim_scmap_levcdpf(nlevsclass*nlevdamage * numpft))
allocate( fates_hdim_cdmap_levcdpf(nlevsclass*nlevdamage * numpft))
allocate( fates_hdim_pftmap_levcdpf(nlevsclass*nlevdamage * numpft))
```

Sources: `(main/FatesHistoryInterfaceMod.F90:134-152)`, `(main/FatesInterfaceMod.F90:1168-1286)`

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
| `cohort_r8` | `CO_R8` | 1-D: cohort (restart only) |
| `cohort_int` | `CO_INT` | 1-D: cohort (restart only) |

The `cohort_*` kinds exist for the restart system (not history output). History output variables are always at the site level or above.

Sources: `(main/FatesIOVariableKindMod.F90:19-49)`

## Output Variable Name Suffix Convention

FATES history variables follow a consistent naming convention in which a dimensionality suffix is appended to the base name. **These are the actual user-facing NetCDF variable names.** Internal Fortran index names (`ih_*`) use different, lowercase conventions (e.g., `ih_nplant_si_scpf`) but those strings never appear in the NetCDF output.

| Name suffix | Corresponds to | Meaning |
|---|---|---|
| (no suffix) | `site_r8` | Site-level scalar |
| `_PF` | `site_pft_r8` | Per PFT |
| `_SZ` | `site_size_r8` | Per size class |
| `_SZPF` | `site_size_pft_r8` | Per (size × PFT) |
| `_AP` | `site_age_r8` | Per patch age |
| `_APPF` | `site_agepft_r8` | Per (age × PFT) |
| `_AC` | `site_coage_r8` | Per cohort-age bin |
| `_ACPF` | `site_coage_pft_r8` | Per (cohort age × PFT) |
| `_SZAP` | `site_scag_r8` | Per (size × age) |
| `_SZAPPF` | `site_scagpft_r8` | Per (size × age × PFT) |
| `_CDPF` | `site_cdpf_r8` | Per (size × damage × PFT) |
| `_CL` | `site_can_r8` | Per canopy layer |
| `_CLLL` | `site_cnlf_r8` | Per (canopy × leaf layer) |
| `_CLLLPF` | `site_cnlfpft_r8` | Per (canopy × leaf × PFT) |
| `_SL` | `site_soil_r8` | Per soil layer |
| `_EL` | `site_elem_r8` | Per chemical element |
| `_ELDC` | `site_elcwd_r8` | Per (element × CWD) |
| `_FC` | `site_fuel_r8` | Per fuel class |
| `_DC` | `site_cwdsc_r8` | Per CWD size class |
| `_SE_SZ` | variant | Secondary-forest-only variant of a `_SZ` quantity |
| `_SE_PF` | variant | Secondary-forest-only variant of a `_PF` quantity |

### Important: `_SZPF`, not `_SCPF`

Earlier versions of this wiki used `_SCPF` as the output suffix for size × PFT variables (e.g., `FATES_NPLANT_SCPF`, `FATES_MORTALITY_SCPF`, `FATES_DDBH_SCPF`). **These strings do not exist anywhere in `set_history_var` calls.** The actual suffix is `_SZPF`, and the correct names are `FATES_NPLANT_SZPF`, `FATES_MORTALITY_CANOPY_SZPF` / `FATES_MORTALITY_USTORY_SZPF`, and `FATES_DDBH_SZPF`. Similarly, `FATES_PARSUN_Z_CNLF` does not exist — the correct names are `FATES_PARSUN_Z_CLLL` (canopy × leaf layer) and `FATES_PARSUN_Z_CLLLPF` (canopy × leaf × PFT). `FATES_FIRE_AREA` does not exist either — fractional burned area is `FATES_BURNFRAC`.

## Verified Variable Inventory (`e85d997`)

The following 475 variable names are registered via `call this%set_history_var(vname='FATES_...', ...)` in `main/FatesHistoryInterfaceMod.F90`. They are grouped by subject area for navigation; a complete alphabetical listing is at the end. All are registered with `avgflag='A'` (time-mean over the history interval).

### Site-scale scalars (`site_r8`)

`FATES_GPP`, `FATES_NPP`, `FATES_AR`, `FATES_AR_CANOPY`, `FATES_AR_UNDERSTORY`, `FATES_AUTORESP`, `FATES_AUTORESP_CANOPY`, `FATES_AUTORESP_USTORY`, `FATES_AUTORESP_SECONDARY`, `FATES_HET_RESP`, `FATES_MAINT_RESP`, `FATES_MAINT_RESP_SECONDARY`, `FATES_MAINT_RESP_UNREDUCED`, `FATES_GROWTH_RESP`, `FATES_GROWTH_RESP_SECONDARY`, `FATES_NEP`, `FATES_EXCESS_RESP`, `FATES_LEAFMAINTAR`, `FATES_FROOTMAINTAR`, `FATES_LSTEMMAINTAR`, `FATES_CROOTMAINTAR`, `FATES_NPP_SECONDARY`, `FATES_GPP_SECONDARY`, `FATES_LAI`, `FATES_LAI_SECONDARY`, `FATES_VEGC`, `FATES_VEGC_ABOVEGROUND`, `FATES_CANOPY_VEGC`, `FATES_USTORY_VEGC`, `FATES_SECONDARY_FOREST_VEGC`, `FATES_SECONDARY_FOREST_FRACTION`, `FATES_LEAFC`, `FATES_FROOTC`, `FATES_SAPWOODC`, `FATES_STRUCTC`, `FATES_STOREC`, `FATES_STOREC_TF`, `FATES_STOREN`, `FATES_STOREN_TF`, `FATES_STOREP`, `FATES_STOREP_TF`, `FATES_LEAFN`, `FATES_LEAFP`, `FATES_FROOTN`, `FATES_FROOTP`, `FATES_SAPWOODN`, `FATES_SAPWOODP`, `FATES_VEGN`, `FATES_VEGP`, `FATES_NONSTRUCTC`, `FATES_REPROC`, `FATES_REPRON`, `FATES_REPROP`, `FATES_NPATCHES`, `FATES_NCOHORTS`, `FATES_NPATCHES_SECONDARY`, `FATES_NCOHORTS_SECONDARY`, `FATES_TRIMMING`, `FATES_CANOPY_SPREAD`, `FATES_BA_WEIGHTED_HEIGHT`, `FATES_CA_WEIGHTED_HEIGHT`, `FATES_AREA_PLANTS`, `FATES_AREA_TREES`, `FATES_FRACTION`, `FATES_COLD_STATUS`, `FATES_GDD`, `FATES_NCHILLDAYS`, `FATES_NCOLDDAYS`, `FATES_DAYSINCE_COLDLEAFOFF`, `FATES_DAYSINCE_COLDLEAFON`, `FATES_L2FR`, `FATES_BURNFRAC`, `FATES_FDI`, `FATES_IGNITIONS`, `FATES_NESTEROV_INDEX`, `FATES_EFFECT_WSPEED`, `FATES_FUELCONSUMED`, `FATES_ROS`, `FATES_FIRE_INTENSITY`, `FATES_FIRE_INTENSITY_BURNFRAC`, `FATES_FIRE_CLOSS`, `FATES_FUEL_AMOUNT`, `FATES_FUEL_BULKD`, `FATES_FUEL_EFF_MOIST`, `FATES_FUEL_MEF`, `FATES_FUEL_SAV`, `FATES_DISTURBANCE_RATE_FIRE`, `FATES_DISTURBANCE_RATE_LOGGING`, `FATES_DISTURBANCE_RATE_P2P`, `FATES_DISTURBANCE_RATE_P2S`, `FATES_DISTURBANCE_RATE_POTENTIAL`, `FATES_DISTURBANCE_RATE_S2S`, `FATES_DISTURBANCE_RATE_TREEFALL`, `FATES_HARVEST_CARBON_FLUX`, `FATES_HARVEST_DEBT`, `FATES_HARVEST_DEBT_SEC`, `FATES_WOOD_PRODUCT`, `FATES_LITTER_IN`, `FATES_LITTER_OUT`, `FATES_FRAGMENTATION_SCALER_SL`, `FATES_SEEDS_IN`, `FATES_SEEDS_IN_LOCAL`, `FATES_SEEDLING_POOL`, `FATES_SEED_BANK`, `FATES_UNGERM_SEED_BANK`, `FATES_NDEMAND`, `FATES_PDEMAND`, `FATES_NH4UPTAKE`, `FATES_NO3UPTAKE`, `FATES_PUPTAKE`, `FATES_NEFFLUX`, `FATES_PEFFLUX`, `FATES_NFIX_SYM`, `FATES_ROOTUPTAKE`, `FATES_ROOTWGT_SOILMATPOT`, `FATES_ROOTWGT_SOILVWC`, `FATES_ROOTWGT_SOILVWCSAT`, `FATES_STOMATAL_COND`, `FATES_LBLAYER_COND`, `FATES_TVEG`, `FATES_TVEG24`, `FATES_TGROWTH`, `FATES_TLONGTERM`, `FATES_VEGH2O`, `FATES_VEGH2O_DEAD`, `FATES_VEGH2O_RECRUIT`, `FATES_VEGH2O_GROWTURN_ERR`, `FATES_VEGH2O_HYDRO_ERR`, `FATES_SAPFLOW`, `FATES_DEMOTION_CARBONFLUX`, `FATES_PROMOTION_CARBONFLUX`, `FATES_PRIMARY_PATCHFUSION_ERR`, `FATES_CBALANCE_ERROR`, `FATES_ERROR_EL`, `FATES_RAD_ERROR`, `FATES_CROOT_ALLOC`, `FATES_FROOT_ALLOC`, `FATES_LEAF_ALLOC`, `FATES_SEED_ALLOC`, `FATES_STEM_ALLOC`, `FATES_STORE_ALLOC`.

### Per-PFT (`site_pft_r8`, `_PF` suffix)

`FATES_VEGC_PF`, `FATES_VEGC_SE_PF`, `FATES_LEAFC_PF`, `FATES_STOREC_PF`, `FATES_GPP_PF`, `FATES_GPP_SE_PF`, `FATES_NPP_PF`, `FATES_NPP_SE_PF`, `FATES_CROWNAREA_PF`, `FATES_CANOPYCROWNAREA_PF`, `FATES_DAYSINCE_DROUGHTLEAFOFF_PF`, `FATES_DAYSINCE_DROUGHTLEAFON_PF`, `FATES_DROUGHT_STATUS_PF`, `FATES_ELONG_FACTOR_PF`, `FATES_L2FR_CANOPY_REC_PF`, `FATES_L2FR_USTORY_REC_PF`, `FATES_MEANLIQVOL_DROUGHTPHEN_PF`, `FATES_MEANSMP_DROUGHTPHEN_PF`, `FATES_MORTALITY_PF`, `FATES_MORTALITY_CFLUX_PF`, `FATES_MORTALITY_CSTARV_CFLUX_PF`, `FATES_MORTALITY_FIRE_CFLUX_PF`, `FATES_MORTALITY_HYDRO_CFLUX_PF`, `FATES_NPLANT_PF`, `FATES_NPLANT_SEC_PF`, `FATES_NOCOMP_BURNEDAREA_PF`, `FATES_NOCOMP_NPATCHES_PF`, `FATES_NOCOMP_PATCHAREA_PF`, `FATES_RECRUITMENT_PF`, `FATES_SEEDS_IN_GRIDCELL_PF`, `FATES_SEEDS_OUT_GRIDCELL_PF`.

### Per-patch-age (`site_age_r8`, `_AP` suffix)

`FATES_BURNFRAC_AP`, `FATES_CANOPYAREA_AP`, `FATES_FIRE_INTENSITY_BURNFRAC_AP`, `FATES_FUEL_AMOUNT_AP`, `FATES_GPP_AP`, `FATES_LAI_AP`, `FATES_LBLAYER_COND_AP`, `FATES_NCL_AP`, `FATES_NPATCH_AP`, `FATES_NPP_AP`, `FATES_PATCHAREA_AP`, `FATES_SECONDAREA_ANTHRODIST_AP`, `FATES_SECONDAREA_DIST_AP`, `FATES_STOMATAL_COND_AP`, `FATES_VEGC_AP`, `FATES_ZSTAR_AP`.

Per (age × PFT) (`_APPF`): `FATES_NPP_APPF`, `FATES_SCORCH_HEIGHT_APPF`, `FATES_VEGC_APPF`.

Per (age × fuel class): `FATES_FUEL_AMOUNT_APFC`.

### Per-size × PFT (`site_size_pft_r8`, `_SZPF` suffix)

The `_SZPF` suffix is the most common multi-PFT dimension — approximately 100 variables use it. Examples:

`FATES_NPLANT_SZPF`, `FATES_NPLANT_CANOPY_SZPF`, `FATES_NPLANT_USTORY_SZPF`, `FATES_BASALAREA_SZPF`, `FATES_GROWTHFLUX_SZPF`, `FATES_GROWTHFLUX_FUSION_SZPF`, `FATES_DDBH_SZPF`, `FATES_DDBH_CANOPY_SZPF`, `FATES_DDBH_USTORY_SZPF`, `FATES_LEAFC_SZPF`, `FATES_LEAFC_CANOPY_SZPF`, `FATES_LEAFC_USTORY_SZPF`, `FATES_LEAFN_SZPF`, `FATES_LEAFP_SZPF`, `FATES_FROOTC_SZPF`, `FATES_FROOTN_SZPF`, `FATES_FROOTP_SZPF`, `FATES_SAPWOODC_SZPF`, `FATES_SAPWOODN_SZPF`, `FATES_SAPWOODP_SZPF`, `FATES_STOREC_SZPF`, `FATES_STOREC_CANOPY_SZPF`, `FATES_STOREC_USTORY_SZPF`, `FATES_STOREC_TF_CANOPY_SZPF`, `FATES_STOREC_TF_USTORY_SZPF`, `FATES_STOREN_SZPF`, `FATES_STOREN_TF_CANOPY_SZPF`, `FATES_STOREN_TF_USTORY_SZPF`, `FATES_STOREP_SZPF`, `FATES_STOREP_TF_CANOPY_SZPF`, `FATES_STOREP_TF_USTORY_SZPF`, `FATES_REPROC_SZPF`, `FATES_REPRON_SZPF`, `FATES_REPROP_SZPF`, `FATES_VEGC_SZPF`, `FATES_VEGC_ABOVEGROUND_SZPF`, `FATES_VEGN_SZPF`, `FATES_VEGP_SZPF`, `FATES_LAI_CANOPY_SZPF`, `FATES_LAI_USTORY_SZPF`, `FATES_GPP_SZPF`, `FATES_GPP_CANOPY_SZPF`, `FATES_GPP_USTORY_SZPF`, `FATES_NPP_SZPF`, `FATES_ABOVEGROUND_MORT_SZPF`, `FATES_ABOVEGROUND_PROD_SZPF`, `FATES_AGSAPMAINTAR_SZPF`, `FATES_AGSAPWOOD_ALLOC_SZPF`, `FATES_BGSAPMAINTAR_SZPF`, `FATES_BGSAPWOOD_ALLOC_SZPF`, `FATES_BGSTRUCT_ALLOC_SZPF`, `FATES_AUTORESP_CANOPY_SZPF`, `FATES_AUTORESP_USTORY_SZPF`, `FATES_AUTORESP_SZPF`, `FATES_FROOTMAINTAR_SZPF`, `FATES_FROOT_ALLOC_SZPF`, `FATES_LEAF_ALLOC_SZPF`, `FATES_SEED_ALLOC_SZPF`, `FATES_GROWAR_SZPF`, `FATES_MAINTAR_SZPF`, `FATES_RDARK_SZPF`, `FATES_C13DISC_SZPF`, `FATES_MORTALITY_AGESCEN_SZPF`, `FATES_MORTALITY_BACKGROUND_SZPF`, `FATES_MORTALITY_CAMBIALBURN_SZPF`, `FATES_MORTALITY_CANOPY_SZPF`, `FATES_MORTALITY_USTORY_SZPF`, `FATES_MORTALITY_CROWNSCORCH_SZPF`, `FATES_MORTALITY_CSTARV_SZPF`, `FATES_MORTALITY_FIRE_SZPF`, `FATES_MORTALITY_FREEZING_SZPF`, `FATES_MORTALITY_HYDRAULIC_SZPF`, `FATES_MORTALITY_IMPACT_SZPF`, `FATES_MORTALITY_LOGGING_SZPF`, `FATES_MORTALITY_SENESCENCE_SZPF`, `FATES_MORTALITY_TERMINATION_SZPF`, `FATES_M3_MORTALITY_CANOPY_SZPF`, `FATES_M3_MORTALITY_USTORY_SZPF`, `FATES_NH4UPTAKE_SZPF`, `FATES_NO3UPTAKE_SZPF`, `FATES_PUPTAKE_SZPF`, `FATES_NDEMAND_SZPF`, `FATES_PDEMAND_SZPF`, `FATES_NEFFLUX_SZPF`, `FATES_PEFFLUX_SZPF`, `FATES_NFIX_SYM_SZPF`, `FATES_BTRAN_SZPF`, `FATES_TRAN_SZPF`, `FATES_ERRH2O_SZPF`, `FATES_LEAF_H2O_SZPF`, `FATES_LEAF_H2OPOT_SZPF`, `FATES_LEAF_CONDFRAC_SZPF`, `FATES_STEM_H2O_SZPF`, `FATES_STEM_H2OPOT_SZPF`, `FATES_STEM_CONDFRAC_SZPF`, `FATES_ABSROOT_H2O_SZPF`, `FATES_ABSROOT_H2OPOT_SZPF`, `FATES_ABSROOT_CONDFRAC_SZPF`, `FATES_TRANSROOT_H2O_SZPF`, `FATES_TRANSROOT_H2OPOT_SZPF`, `FATES_TRANSROOT_CONDFRAC_SZPF`, `FATES_SAPFLOW_SZPF`, `FATES_ITERH1_SZPF`, `FATES_ITERH2_SZPF`, `FATES_ROOTUPTAKE0_SZPF`, `FATES_ROOTUPTAKE10_SZPF`, `FATES_ROOTUPTAKE50_SZPF`, `FATES_ROOTUPTAKE100_SZPF`, `FATES_L2FR_CLSZPF`.

### Per-size class only (`site_size_r8`, `_SZ` suffix)

`FATES_BASALAREA_SZ`, `FATES_DDBH_CANOPY_SZ`, `FATES_DDBH_USTORY_SZ`, `FATES_NPLANT_SZ`, `FATES_NPLANT_CANOPY_SZ`, `FATES_NPLANT_USTORY_SZ`, `FATES_NPLANT_SZAP`, `FATES_NPLANT_SZAPPF`, `FATES_CROWNAREA_CANOPY_SZ`, `FATES_CROWNAREA_USTORY_SZ`, `FATES_LAI_CANOPY_SZ`, `FATES_LAI_USTORY_SZ`, `FATES_SAI_CANOPY_SZ`, `FATES_SAI_USTORY_SZ`, `FATES_VEGC_SZ`, `FATES_VEGC_ABOVEGROUND_SZ`, `FATES_GPP_CANOPY_SZ`, `FATES_NPP_CANOPY_SZ`, `FATES_NPP_USTORY_SZ`, `FATES_CROOTMAINTAR_CANOPY_SZ`, `FATES_CROOTMAINTAR_USTORY_SZ`, `FATES_FROOTCTURN_CANOPY_SZ`, `FATES_FROOTCTURN_USTORY_SZ`, `FATES_FROOTMAINTAR_CANOPY_SZ`, `FATES_FROOTMAINTAR_USTORY_SZ`, `FATES_FROOT_ALLOC_CANOPY_SZ`, `FATES_FROOT_ALLOC_USTORY_SZ`, `FATES_LEAFCTURN_CANOPY_SZ`, `FATES_LEAFCTURN_USTORY_SZ`, `FATES_LEAF_ALLOC_CANOPY_SZ`, `FATES_LEAF_ALLOC_USTORY_SZ`, `FATES_LSTEMMAINTAR_CANOPY_SZ`, `FATES_LSTEMMAINTAR_USTORY_SZ`, `FATES_STRUCTCTURN_CANOPY_SZ`, `FATES_STRUCTCTURN_USTORY_SZ`, `FATES_STRUCT_ALLOC_CANOPY_SZ`, `FATES_STRUCT_ALLOC_USTORY_SZ`, `FATES_SAPWOODCTURN_CANOPY_SZ`, `FATES_SAPWOODCTURN_USTORY_SZ`, `FATES_SAPWOOD_ALLOC_CANOPY_SZ`, `FATES_SAPWOOD_ALLOC_USTORY_SZ`, `FATES_STOREC_TF` (site-level, not _SZ), `FATES_STORECTURN_CANOPY_SZ`, `FATES_STORECTURN_USTORY_SZ`, `FATES_STORE_ALLOC_CANOPY_SZ`, `FATES_STORE_ALLOC_USTORY_SZ`, `FATES_SEED_PROD_CANOPY_SZ`, `FATES_SEED_PROD_USTORY_SZ`, `FATES_GROWAR_CANOPY_SZ`, `FATES_GROWAR_USTORY_SZ`, `FATES_MAINTAR_CANOPY_SZ`, `FATES_MAINTAR_USTORY_SZ`, `FATES_TRIMMING_CANOPY_SZ`, `FATES_TRIMMING_USTORY_SZ`, `FATES_RDARK_CANOPY_SZ`, `FATES_RDARK_USTORY_SZ`, `FATES_YESTCANLEV_CANOPY_SZ`, `FATES_YESTCANLEV_USTORY_SZ`, `FATES_DEMOTION_RATE_SZ`, `FATES_PROMOTION_RATE_SZ`, `FATES_M3_MORTALITY_CANOPY_SZ`, `FATES_M3_MORTALITY_USTORY_SZ`, `FATES_MORTALITY_AGESCEN_SZ`, `FATES_MORTALITY_BACKGROUND_SZ`, `FATES_MORTALITY_CANOPY_SZ`, `FATES_MORTALITY_USTORY_SZ`, `FATES_MORTALITY_CSTARV_SZ`, `FATES_MORTALITY_FIRE_SZ`, `FATES_MORTALITY_FREEZING_SZ`, `FATES_MORTALITY_HYDRAULIC_SZ`, `FATES_MORTALITY_IMPACT_SZ`, `FATES_MORTALITY_LOGGING_SZ`, `FATES_MORTALITY_SENESCENCE_SZ`, `FATES_MORTALITY_TERMINATION_SZ`, `FATES_MORTALITY_AGESCEN_SE_SZ`, `FATES_MORTALITY_BACKGROUND_SE_SZ`, `FATES_MORTALITY_CANOPY_SE_SZ`, `FATES_MORTALITY_CSTARV_SE_SZ`, `FATES_MORTALITY_FREEZING_SE_SZ`, `FATES_MORTALITY_HYDRAULIC_SE_SZ`, `FATES_MORTALITY_LOGGING_SE_SZ`, `FATES_MORTALITY_SENESCENCE_SE_SZ`.

### Crown-damage dimensions (`_CDPF` suffix)

`FATES_DDBH_CDPF`, `FATES_DDBH_CANOPY_CDPF`, `FATES_DDBH_USTORY_CDPF`, `FATES_NPLANT_CDPF`, `FATES_NPLANT_CANOPY_CDPF`, `FATES_NPLANT_USTORY_CDPF`, `FATES_CROWNAREA_CANOPY_CD`, `FATES_CROWNAREA_USTORY_CD`, `FATES_M11_SZPF`, `FATES_M11_CDPF`, `FATES_M11_MORTALITY_CANOPY_CDPF`, `FATES_M11_MORTALITY_USTORY_CDPF`, `FATES_M3_CDPF`, `FATES_M3_MORTALITY_CANOPY_CDPF`, `FATES_M3_MORTALITY_USTORY_CDPF`, `FATES_MORTALITY_CDPF`, `FATES_MORTALITY_CANOPY_CDPF`, `FATES_MORTALITY_USTORY_CDPF`.

### Cohort-age dimensions (`_AC`, `_ACPF`)

`FATES_MORTALITY_AGESCEN_AC`, `FATES_MORTALITY_AGESCEN_ACPF`, `FATES_NPLANT_AC`, `FATES_NPLANT_ACPF`.

### Canopy-layer × leaf-layer (`_CL`, `_CLLL`, `_CLLLPF`)

`FATES_CROWNAREA_CL`, `FATES_CROWNAREA_CLLL`, `FATES_PARSUN_Z_CL`, `FATES_PARSUN_Z_CLLL`, `FATES_PARSUN_Z_CLLLPF`, `FATES_PARSHA_Z_CL`, `FATES_PARSHA_Z_CLLL`, `FATES_PARSHA_Z_CLLLPF`, `FATES_PARPROF_DIR_CLLL`, `FATES_PARPROF_DIR_CLLLPF`, `FATES_PARPROF_DIF_CLLL`, `FATES_PARPROF_DIF_CLLLPF`, `FATES_LAISUN_Z_CLLL`, `FATES_LAISUN_Z_CLLLPF`, `FATES_LAISUN_TOP_CL`, `FATES_LAISHA_Z_CLLL`, `FATES_LAISHA_Z_CLLLPF`, `FATES_LAISHA_TOP_CL`, `FATES_FABD_SHA_CLLL`, `FATES_FABD_SHA_CLLLPF`, `FATES_FABD_SHA_TOPLF_CL`, `FATES_FABD_SUN_CLLL`, `FATES_FABD_SUN_CLLLPF`, `FATES_FABD_SUN_TOPLF_CL`, `FATES_FABI_SHA_CLLL`, `FATES_FABI_SHA_CLLLPF`, `FATES_FABI_SHA_TOPLF_CL`, `FATES_FABI_SUN_CLLL`, `FATES_FABI_SUN_CLLLPF`, `FATES_FABI_SUN_TOPLF_CL`, `FATES_NET_C_UPTAKE_CLLL`.

### Per-element (`_EL`)

`FATES_FIRE_FLUX_EL`, `FATES_LITTER_IN_EL`, `FATES_LITTER_OUT_EL`, `FATES_LITTER_AG_CWD_EL`, `FATES_LITTER_AG_FINE_EL`, `FATES_LITTER_BG_CWD_EL`, `FATES_LITTER_BG_FINE_EL`, `FATES_LITTER_CWD_ELDC`, `FATES_SEED_BANK_EL`, `FATES_SEED_DECAY_EL`, `FATES_SEED_GERM_EL`, `FATES_SEEDS_IN_EXTERN_EL`, `FATES_SEEDS_IN_LOCAL_EL`.

### Fuel and CWD (`_FC`, `_DC`)

`FATES_FUEL_AMOUNT_FC`, `FATES_FUEL_BURNT_BURNFRAC_FC`, `FATES_FUEL_MOISTURE_FC`, `FATES_CWD_ABOVEGROUND_DC`, `FATES_CWD_ABOVEGROUND_IN_DC`, `FATES_CWD_ABOVEGROUND_OUT_DC`, `FATES_CWD_BELOWGROUND_DC`, `FATES_CWD_BELOWGROUND_IN_DC`, `FATES_CWD_BELOWGROUND_OUT_DC`.

### Soil and height (`_SL`, `_HT`)

`FATES_FROOTC_SL`, `FATES_ROOTUPTAKE_SL`, `FATES_SOILMATPOT_SL`, `FATES_SOILVWC_SL`, `FATES_SOILVWCSAT_SL`, `FATES_CANOPYAREA_HT`, `FATES_LEAFAREA_HT`.

### Complete alphabetical listing

For reference, all 475 verified `vname=` strings in `main/FatesHistoryInterfaceMod.F90` (commit `e85d997`), sorted:

```
FATES_ABOVEGROUND_MORT_SZPF                 FATES_ABOVEGROUND_PROD_SZPF
FATES_ABSROOT_CONDFRAC_SZPF                 FATES_ABSROOT_H2OPOT_SZPF
FATES_ABSROOT_H2O_SZPF                      FATES_AGSAPMAINTAR_SZPF
FATES_AGSAPWOOD_ALLOC_SZPF                  FATES_AR
FATES_AREA_PLANTS                           FATES_AREA_TREES
FATES_AR_CANOPY                             FATES_AR_UNDERSTORY
FATES_AUTORESP                              FATES_AUTORESP_CANOPY
FATES_AUTORESP_CANOPY_SZPF                  FATES_AUTORESP_SECONDARY
FATES_AUTORESP_SZPF                         FATES_AUTORESP_USTORY
FATES_AUTORESP_USTORY_SZPF                  FATES_BASALAREA_SZ
FATES_BASALAREA_SZPF                        FATES_BA_WEIGHTED_HEIGHT
FATES_BGSAPMAINTAR_SZPF                     FATES_BGSAPWOOD_ALLOC_SZPF
FATES_BGSTRUCT_ALLOC_SZPF                   FATES_BTRAN_SZPF
FATES_BURNFRAC                              FATES_BURNFRAC_AP
FATES_C13DISC_SZPF                          FATES_CANOPYAREA_AP
FATES_CANOPYAREA_HT                         FATES_CANOPYCROWNAREA_PF
FATES_CANOPY_SPREAD                         FATES_CANOPY_VEGC
FATES_CA_WEIGHTED_HEIGHT                    FATES_CBALANCE_ERROR
FATES_COLD_STATUS                           FATES_CROOTMAINTAR
FATES_CROOTMAINTAR_CANOPY_SZ                FATES_CROOTMAINTAR_USTORY_SZ
FATES_CROOT_ALLOC                           FATES_CROWNAREA_CANOPY_CD
FATES_CROWNAREA_CANOPY_SZ                   FATES_CROWNAREA_CL
FATES_CROWNAREA_CLLL                        FATES_CROWNAREA_PF
FATES_CROWNAREA_USTORY_CD                   FATES_CROWNAREA_USTORY_SZ
FATES_CWD_ABOVEGROUND_DC                    FATES_CWD_ABOVEGROUND_IN_DC
FATES_CWD_ABOVEGROUND_OUT_DC                FATES_CWD_BELOWGROUND_DC
FATES_CWD_BELOWGROUND_IN_DC                 FATES_CWD_BELOWGROUND_OUT_DC
FATES_DAYSINCE_COLDLEAFOFF                  FATES_DAYSINCE_COLDLEAFON
FATES_DAYSINCE_DROUGHTLEAFOFF_PF            FATES_DAYSINCE_DROUGHTLEAFON_PF
FATES_DDBH_CANOPY_CDPF                      FATES_DDBH_CANOPY_SZ
FATES_DDBH_CANOPY_SZAP                      FATES_DDBH_CANOPY_SZPF
FATES_DDBH_CDPF                             FATES_DDBH_SZPF
FATES_DDBH_USTORY_CDPF                      FATES_DDBH_USTORY_SZ
FATES_DDBH_USTORY_SZAP                      FATES_DDBH_USTORY_SZPF
FATES_DEMOTION_CARBONFLUX                   FATES_DEMOTION_RATE_SZ
FATES_DISTURBANCE_RATE_FIRE                 FATES_DISTURBANCE_RATE_LOGGING
FATES_DISTURBANCE_RATE_P2P                  FATES_DISTURBANCE_RATE_P2S
FATES_DISTURBANCE_RATE_POTENTIAL            FATES_DISTURBANCE_RATE_S2S
FATES_DISTURBANCE_RATE_TREEFALL             FATES_DROUGHT_STATUS_PF
FATES_EFFECT_WSPEED                         FATES_ELONG_FACTOR_PF
FATES_ERRH2O_SZPF                           FATES_ERROR_EL
FATES_EXCESS_RESP                           FATES_FABD_SHA_CLLL
FATES_FABD_SHA_CLLLPF                       FATES_FABD_SHA_TOPLF_CL
FATES_FABD_SUN_CLLL                         FATES_FABD_SUN_CLLLPF
FATES_FABD_SUN_TOPLF_CL                     FATES_FABI_SHA_CLLL
FATES_FABI_SHA_CLLLPF                       FATES_FABI_SHA_TOPLF_CL
FATES_FABI_SUN_CLLL                         FATES_FABI_SUN_CLLLPF
FATES_FABI_SUN_TOPLF_CL                     FATES_FDI
FATES_FIRE_CLOSS                            FATES_FIRE_FLUX_EL
FATES_FIRE_INTENSITY                        FATES_FIRE_INTENSITY_BURNFRAC
FATES_FIRE_INTENSITY_BURNFRAC_AP            FATES_FRACTION
FATES_FRAGMENTATION_SCALER_SL               FATES_FROOTC
FATES_FROOTCTURN_CANOPY_SZ                  FATES_FROOTCTURN_USTORY_SZ
FATES_FROOTC_SL                             FATES_FROOTC_SZPF
FATES_FROOTMAINTAR                          FATES_FROOTMAINTAR_CANOPY_SZ
FATES_FROOTMAINTAR_SZPF                     FATES_FROOTMAINTAR_USTORY_SZ
FATES_FROOTN                                FATES_FROOTN_SZPF
FATES_FROOTP                                FATES_FROOTP_SZPF
FATES_FROOT_ALLOC                           FATES_FROOT_ALLOC_CANOPY_SZ
FATES_FROOT_ALLOC_SZPF                      FATES_FROOT_ALLOC_USTORY_SZ
FATES_FUELCONSUMED                          FATES_FUEL_AMOUNT
FATES_FUEL_AMOUNT_AP                        FATES_FUEL_AMOUNT_APFC
FATES_FUEL_AMOUNT_FC                        FATES_FUEL_BULKD
FATES_FUEL_BURNT_BURNFRAC_FC                FATES_FUEL_EFF_MOIST
FATES_FUEL_MEF                              FATES_FUEL_MOISTURE_FC
FATES_FUEL_SAV                              FATES_GDD
FATES_GPP                                   FATES_GPP_AP
FATES_GPP_CANOPY                            FATES_GPP_CANOPY_SZPF
FATES_GPP_PF                                FATES_GPP_SECONDARY
FATES_GPP_SE_PF                             FATES_GPP_SZPF
FATES_GPP_USTORY                            FATES_GPP_USTORY_SZPF
FATES_GROWAR_CANOPY_SZ                      FATES_GROWAR_SZPF
FATES_GROWAR_USTORY_SZ                      FATES_GROWTHFLUX_FUSION_SZPF
FATES_GROWTHFLUX_SZPF                       FATES_GROWTH_RESP
FATES_GROWTH_RESP_SECONDARY                 FATES_HARVEST_CARBON_FLUX
FATES_HARVEST_DEBT                          FATES_HARVEST_DEBT_SEC
FATES_HET_RESP                              FATES_IGNITIONS
FATES_ITERH1_SZPF                           FATES_ITERH2_SZPF
FATES_L2FR                                  FATES_L2FR_CANOPY_REC_PF
FATES_L2FR_CLSZPF                           FATES_L2FR_USTORY_REC_PF
FATES_LAI                                   FATES_LAISHA_TOP_CL
FATES_LAISHA_Z_CLLL                         FATES_LAISHA_Z_CLLLPF
FATES_LAISUN_TOP_CL                         FATES_LAISUN_Z_CLLL
FATES_LAISUN_Z_CLLLPF                       FATES_LAI_AP
FATES_LAI_CANOPY_SZ                         FATES_LAI_CANOPY_SZPF
FATES_LAI_SECONDARY                         FATES_LAI_USTORY_SZ
FATES_LAI_USTORY_SZPF                       FATES_LBLAYER_COND
FATES_LBLAYER_COND_AP                       FATES_LEAFAREA_HT
FATES_LEAFC                                 FATES_LEAFCTURN_CANOPY_SZ
FATES_LEAFCTURN_USTORY_SZ                   FATES_LEAFC_CANOPY_SZPF
FATES_LEAFC_PF                              FATES_LEAFC_SZPF
FATES_LEAFC_USTORY_SZPF                     FATES_LEAFMAINTAR
FATES_LEAFN                                 FATES_LEAFN_SZPF
FATES_LEAFP                                 FATES_LEAFP_SZPF
FATES_LEAF_ALLOC                            FATES_LEAF_ALLOC_CANOPY_SZ
FATES_LEAF_ALLOC_SZPF                       FATES_LEAF_ALLOC_USTORY_SZ
FATES_LEAF_CONDFRAC_SZPF                    FATES_LEAF_H2OPOT_SZPF
FATES_LEAF_H2O_SZPF                         FATES_LITTER_AG_CWD_EL
FATES_LITTER_AG_FINE_EL                     FATES_LITTER_BG_CWD_EL
FATES_LITTER_BG_FINE_EL                     FATES_LITTER_CWD_ELDC
FATES_LITTER_IN                             FATES_LITTER_IN_EL
FATES_LITTER_OUT                            FATES_LITTER_OUT_EL
FATES_LSTEMMAINTAR                          FATES_LSTEMMAINTAR_CANOPY_SZ
FATES_LSTEMMAINTAR_USTORY_SZ                FATES_M11_CDPF
FATES_M11_MORTALITY_CANOPY_CDPF             FATES_M11_MORTALITY_USTORY_CDPF
FATES_M11_SZPF                              FATES_M3_CDPF
FATES_M3_MORTALITY_CANOPY_CDPF              FATES_M3_MORTALITY_CANOPY_SZ
FATES_M3_MORTALITY_CANOPY_SZPF              FATES_M3_MORTALITY_USTORY_CDPF
FATES_M3_MORTALITY_USTORY_SZ                FATES_M3_MORTALITY_USTORY_SZPF
FATES_MAINTAR_CANOPY_SZ                     FATES_MAINTAR_SZPF
FATES_MAINTAR_USTORY_SZ                     FATES_MAINT_RESP
FATES_MAINT_RESP_SECONDARY                  FATES_MAINT_RESP_UNREDUCED
FATES_MEANLIQVOL_DROUGHTPHEN_PF             FATES_MEANSMP_DROUGHTPHEN_PF
FATES_MORTALITY_AGESCEN_AC                  FATES_MORTALITY_AGESCEN_ACPF
FATES_MORTALITY_AGESCEN_SE_SZ               FATES_MORTALITY_AGESCEN_SZ
FATES_MORTALITY_AGESCEN_SZPF                FATES_MORTALITY_BACKGROUND_SE_SZ
FATES_MORTALITY_BACKGROUND_SZ               FATES_MORTALITY_BACKGROUND_SZPF
FATES_MORTALITY_CAMBIALBURN_SZPF            FATES_MORTALITY_CANOPY_CDPF
FATES_MORTALITY_CANOPY_SE_SZ                FATES_MORTALITY_CANOPY_SZ
FATES_MORTALITY_CANOPY_SZAP                 FATES_MORTALITY_CANOPY_SZPF
FATES_MORTALITY_CDPF                        FATES_MORTALITY_CFLUX_CANOPY
FATES_MORTALITY_CFLUX_PF                    FATES_MORTALITY_CFLUX_USTORY
FATES_MORTALITY_CROWNSCORCH_SZPF            FATES_MORTALITY_CSTARV_CFLUX_PF
FATES_MORTALITY_CSTARV_SE_SZ                FATES_MORTALITY_CSTARV_SZ
FATES_MORTALITY_CSTARV_SZPF                 FATES_MORTALITY_FIRE_CFLUX_PF
FATES_MORTALITY_FIRE_SZ                     FATES_MORTALITY_FIRE_SZPF
FATES_MORTALITY_FREEZING_SE_SZ              FATES_MORTALITY_FREEZING_SZ
FATES_MORTALITY_FREEZING_SZPF               FATES_MORTALITY_HYDRAULIC_SE_SZ
FATES_MORTALITY_HYDRAULIC_SZ                FATES_MORTALITY_HYDRAULIC_SZPF
FATES_MORTALITY_HYDRO_CFLUX_PF              FATES_MORTALITY_IMPACT_SZ
FATES_MORTALITY_IMPACT_SZPF                 FATES_MORTALITY_LOGGING_SE_SZ
FATES_MORTALITY_LOGGING_SZ                  FATES_MORTALITY_LOGGING_SZPF
FATES_MORTALITY_PF                          FATES_MORTALITY_SENESCENCE_SE_SZ
FATES_MORTALITY_SENESCENCE_SZ               FATES_MORTALITY_SENESCENCE_SZPF
FATES_MORTALITY_TERMINATION_SZ              FATES_MORTALITY_TERMINATION_SZPF
FATES_MORTALITY_USTORY_CDPF                 FATES_MORTALITY_USTORY_SZ
FATES_MORTALITY_USTORY_SZAP                 FATES_MORTALITY_USTORY_SZPF
FATES_NCHILLDAYS                            FATES_NCL_AP
FATES_NCOHORTS                              FATES_NCOHORTS_SECONDARY
FATES_NCOLDDAYS                             FATES_NDEMAND
FATES_NDEMAND_SZPF                          FATES_NEFFLUX
FATES_NEFFLUX_SZPF                          FATES_NEP
FATES_NESTEROV_INDEX                        FATES_NET_C_UPTAKE_CLLL
FATES_NFIX_SYM                              FATES_NFIX_SYM_SZPF
FATES_NH4UPTAKE                             FATES_NH4UPTAKE_SZPF
FATES_NO3UPTAKE                             FATES_NO3UPTAKE_SZPF
FATES_NOCOMP_BURNEDAREA_PF                  FATES_NOCOMP_NPATCHES_PF
FATES_NOCOMP_PATCHAREA_PF                   FATES_NONSTRUCTC
FATES_NPATCHES                              FATES_NPATCHES_SECONDARY
FATES_NPATCH_AP                             FATES_NPLANT_AC
FATES_NPLANT_ACPF                           FATES_NPLANT_CANOPY_CDPF
FATES_NPLANT_CANOPY_SZ                      FATES_NPLANT_CANOPY_SZAP
FATES_NPLANT_CANOPY_SZPF                    FATES_NPLANT_CDPF
FATES_NPLANT_PF                              FATES_NPLANT_SEC_PF
FATES_NPLANT_SZ                             FATES_NPLANT_SZAP
FATES_NPLANT_SZAPPF                         FATES_NPLANT_SZPF
FATES_NPLANT_USTORY_CDPF                    FATES_NPLANT_USTORY_SZ
FATES_NPLANT_USTORY_SZAP                    FATES_NPLANT_USTORY_SZPF
FATES_NPP                                   FATES_NPP_AP
FATES_NPP_APPF                              FATES_NPP_CANOPY_SZ
FATES_NPP_PF                                FATES_NPP_SECONDARY
FATES_NPP_SE_PF                             FATES_NPP_SZPF
FATES_NPP_USTORY_SZ                         FATES_PARPROF_DIF_CLLL
FATES_PARPROF_DIF_CLLLPF                    FATES_PARPROF_DIR_CLLL
FATES_PARPROF_DIR_CLLLPF                    FATES_PARSHA_Z_CL
FATES_PARSHA_Z_CLLL                         FATES_PARSHA_Z_CLLLPF
FATES_PARSUN_Z_CL                           FATES_PARSUN_Z_CLLL
FATES_PARSUN_Z_CLLLPF                       FATES_PATCHAREA_AP
FATES_PDEMAND                               FATES_PDEMAND_SZPF
FATES_PEFFLUX                               FATES_PEFFLUX_SZPF
FATES_PRIMARY_PATCHFUSION_ERR               FATES_PROMOTION_CARBONFLUX
FATES_PROMOTION_RATE_SZ                     FATES_PUPTAKE
FATES_PUPTAKE_SZPF                          FATES_RAD_ERROR
FATES_RDARK_CANOPY_SZ                       FATES_RDARK_SZPF
FATES_RDARK_USTORY_SZ                       FATES_RECRUITMENT_PF
FATES_REPROC                                FATES_REPROC_SZPF
FATES_REPRON                                FATES_REPRON_SZPF
FATES_REPROP                                FATES_REPROP_SZPF
FATES_ROOTUPTAKE                            FATES_ROOTUPTAKE0_SZPF
FATES_ROOTUPTAKE100_SZPF                    FATES_ROOTUPTAKE10_SZPF
FATES_ROOTUPTAKE50_SZPF                     FATES_ROOTUPTAKE_SL
FATES_ROOTWGT_SOILMATPOT                    FATES_ROOTWGT_SOILVWC
FATES_ROOTWGT_SOILVWCSAT                    FATES_ROS
FATES_SAI_CANOPY_SZ                         FATES_SAI_USTORY_SZ
FATES_SAPFLOW                               FATES_SAPFLOW_SZPF
FATES_SAPWOODC                              FATES_SAPWOODCTURN_CANOPY_SZ
FATES_SAPWOODCTURN_USTORY_SZ                FATES_SAPWOODC_SZPF
FATES_SAPWOODN                              FATES_SAPWOODN_SZPF
FATES_SAPWOODP                              FATES_SAPWOODP_SZPF
FATES_SAPWOOD_ALLOC_CANOPY_SZ               FATES_SAPWOOD_ALLOC_USTORY_SZ
FATES_SCORCH_HEIGHT_APPF                    FATES_SECONDAREA_ANTHRODIST_AP
FATES_SECONDAREA_DIST_AP                    FATES_SECONDARY_FOREST_FRACTION
FATES_SECONDARY_FOREST_VEGC                 FATES_SEEDLING_POOL
FATES_SEEDS_IN                              FATES_SEEDS_IN_EXTERN_EL
FATES_SEEDS_IN_GRIDCELL_PF                  FATES_SEEDS_IN_LOCAL
FATES_SEEDS_IN_LOCAL_EL                     FATES_SEEDS_OUT_GRIDCELL_PF
FATES_SEED_ALLOC                            FATES_SEED_ALLOC_CANOPY_SZ
FATES_SEED_ALLOC_SZPF                       FATES_SEED_ALLOC_USTORY_SZ
FATES_SEED_BANK                             FATES_SEED_BANK_EL
FATES_SEED_DECAY_EL                         FATES_SEED_GERM_EL
FATES_SEED_PROD_CANOPY_SZ                   FATES_SEED_PROD_USTORY_SZ
FATES_SOILMATPOT_SL                         FATES_SOILVWCSAT_SL
FATES_SOILVWC_SL                            FATES_STEM_ALLOC
FATES_STEM_CONDFRAC_SZPF                    FATES_STEM_H2OPOT_SZPF
FATES_STEM_H2O_SZPF                         FATES_STOMATAL_COND
FATES_STOMATAL_COND_AP                      FATES_STOREC
FATES_STORECTURN_CANOPY_SZ                  FATES_STORECTURN_USTORY_SZ
FATES_STOREC_CANOPY_SZPF                    FATES_STOREC_PF
FATES_STOREC_SZPF                           FATES_STOREC_TF
FATES_STOREC_TF_CANOPY_SZPF                 FATES_STOREC_TF_USTORY_SZPF
FATES_STOREC_USTORY_SZPF                    FATES_STOREN
FATES_STOREN_SZPF                           FATES_STOREN_TF
FATES_STOREN_TF_CANOPY_SZPF                 FATES_STOREN_TF_USTORY_SZPF
FATES_STOREP                                FATES_STOREP_SZPF
FATES_STOREP_TF                             FATES_STOREP_TF_CANOPY_SZPF
FATES_STOREP_TF_USTORY_SZPF                 FATES_STORE_ALLOC
FATES_STORE_ALLOC_CANOPY_SZ                 FATES_STORE_ALLOC_USTORY_SZ
FATES_STRUCTC                               FATES_STRUCTCTURN_CANOPY_SZ
FATES_STRUCTCTURN_USTORY_SZ                 FATES_STRUCT_ALLOC_CANOPY_SZ
FATES_STRUCT_ALLOC_USTORY_SZ                FATES_TGROWTH
FATES_TLONGTERM                             FATES_TRANSROOT_CONDFRAC_SZPF
FATES_TRANSROOT_H2OPOT_SZPF                 FATES_TRANSROOT_H2O_SZPF
FATES_TRAN_SZPF                             FATES_TRIMMING
FATES_TRIMMING_CANOPY_SZ                    FATES_TRIMMING_USTORY_SZ
FATES_TVEG                                  FATES_TVEG24
FATES_UNGERM_SEED_BANK                      FATES_USTORY_VEGC
FATES_VEGC                                  FATES_VEGC_ABOVEGROUND
FATES_VEGC_ABOVEGROUND_SZ                   FATES_VEGC_ABOVEGROUND_SZPF
FATES_VEGC_AP                               FATES_VEGC_APPF
FATES_VEGC_PF                               FATES_VEGC_SE_PF
FATES_VEGC_SZ                               FATES_VEGC_SZPF
FATES_VEGH2O                                FATES_VEGH2O_DEAD
FATES_VEGH2O_GROWTURN_ERR                   FATES_VEGH2O_HYDRO_ERR
FATES_VEGH2O_RECRUIT                        FATES_VEGN
FATES_VEGN_SZPF                             FATES_VEGP
FATES_VEGP_SZPF                             FATES_WOOD_PRODUCT
FATES_YESTCANLEV_CANOPY_SZ                  FATES_YESTCANLEV_USTORY_SZ
FATES_ZSTAR_AP
```

This list is the canonical authority — if a name does not appear here, it is not registered in `e85d997`.

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

These are called during history update (once per cohort per timestep) and during cohort initialization.

Sources: `(main/FatesSizeAgeTypeIndicesMod.F90)`, `(biogeochem/EDCanopyStructureMod.F90:1357-1365)`

## Summary

FATES's history variables use a two-pronged naming system: **internal** module-level integer indices (`ih_*`, with suffixes like `_si`, `_scpf`, `_cnlfpft`) that exist only in Fortran source, and **user-facing** NetCDF variable names (like `FATES_NPLANT_SZPF`, `FATES_PARSUN_Z_CLLL`) that are what you actually see in a history file. Confusing the two is the single most common source of "variable not found" errors in post-processing. Always use the actual `vname=` strings (which this page lists verbatim) when constructing xarray/Python or NCO queries against a FATES history file.
