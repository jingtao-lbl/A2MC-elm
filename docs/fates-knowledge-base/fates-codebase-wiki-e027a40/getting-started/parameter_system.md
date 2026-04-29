---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# Parameter System

## Purpose and Scope

This document describes the FATES parameter system, which defines the configuration values that control model behavior. It covers the JSON parameter file structure, the one-shot loading mechanism, and the storage modules that manage parameters at runtime. For Python tooling, see [Parameter Management Tools](parameter_tools.md). For how parameters flow into specific processes, see [PARTEH](../plant-physiology/parteh/index.md) and [Fire Dynamics: SPITFIRE](../fire/index.md).

## Parameter File Structure

At api.43, FATES parameters are stored in **JSON** files. The canonical file is `parameter_files/fates_params_default.json`. Earlier API generations used CDL/NetCDF, those legacy snapshots are preserved under `parameter_files/archive/` (api24 through api41). The CDL workflow (`ncgen` / `ncdump`) is no longer applicable to the canonical file.

### File Organization

The default file declares the following dimensions `(parameter_files/fates_params_default.json:3-17)`:

| Dimension | Default | Purpose |
|-----------|---------|---------|
| `fates_pft` | **14** | number of plant functional types |
| `fates_leafage_class` | 1 | number of leaf age classes |
| `fates_hydr_organs` | 4 | hydraulic organs (leaf, stem, transporting root, absorbing root) |
| `fates_plant_organs` | 4 | allocation organs (leaf, fineroot, sapwood, structure) |
| `fates_history_size_bins` | 13 | DBH size class bin edges |
| `fates_history_age_bins` | 7 | patch age bin edges |
| `fates_history_height_bins` | 6 | height bin edges |
| `fates_history_coage_bins` | 2 | cohort age bin edges |
| `fates_history_damage_bins` | 2 | damage class bin edges |
| `fates_NCWD` | 4 | coarse woody debris size classes |
| `fates_litterclass` | 6 | litter decomposition classes |
| `fates_hlm_pftno` | 14 | number of HLM surface-dataset PFTs |
| `fates_landuseclass` | **5** | land-use classes (primaryland, secondaryland, rangeland, pastureland, cropland) — **new in api.43** |

There is no `fates_string_length` dimension, all character data are native JSON strings. The maximum allowable PFT count is `maxpft = 16` `(main/EDParamsMod.F90:91)`; the upper bound for canopy layers is `nclmax = 3` `(main/EDParamsMod.F90:76)`. The default PFT list at e027a40 is:

```
1  broadleaf_evergreen_tropical_tree
2  needleleaf_evergreen_extratrop_tree
3  needleleaf_colddecid_extratrop_tree
4  broadleaf_evergreen_extratrop_tree
5  broadleaf_hydrodecid_tropical_tree
6  broadleaf_colddecid_extratrop_tree
7  broadleaf_evergreen_extratrop_shrub
8  broadleaf_hydrodecid_extratrop_shrub
9  broadleaf_colddecid_extratrop_shrub
10 broadleaf_evergreen_arctic_shrub        (NEW at api.43)
11 broadleaf_colddecid_arctic_shrub        (NEW at api.43)
12 arctic_c3_grass                         (was index 10 at e85d997)
13 cool_c3_grass                           (NEW)
14 c4_grass                                (NEW)
```

Source: `parameter_files/fates_params_default.json:73`.

### Parameter Object Format

Each parameter is a JSON object with five fields. Example for `fates_leaf_vcmax25top` (`parameter_files/fates_params_default.json:915` and following):

```json
"fates_leaf_vcmax25top": {
  "dtype": "float",
  "dims": ["fates_leafage_class", "fates_pft"],
  "long_name": "maximum carboxylation rate of Rub. at 25C, canopy top",
  "units": "umol CO2/m^2/s",
  "data": [[ ... 14 values ... ]]
}
```

`dtype` must be `"float"`, `"integer"`, or `"string"` (`main/JSONParameterUtilsMod.F90:18`). Scalar parameters use `"dims": ["scalar"]`. Two-dimensional arrays use the convention that PFT is the **inner** (rightmost) JSON index but the **first** Fortran array dimension; transpose helpers `Transp2dInt` and `Transp2dReal` in `main/FatesParametersInterface.F90:25-73` perform the swap on read.

## Parameter Loading Architecture

At api.43 the two-phase Register/Receive loading flow has been replaced by a single read followed by a single transfer. The driver is `SetFatesGlobalElements1()` `(main/FatesInterfaceMod.F90:792-893)`:

```fortran
call JSONSetInvalid(fates_check_param_set+10._r8)   ! sentinel for nan/null entries
call JSONSetLogInit(fates_log())
call JSONRead(paramfile, pstruct)                   ! parse entire JSON, fill pstruct

if ( hlm_masterproc == itrue ) then
   write(fates_log(),*) '============= FATES Parameter Info ============'
   do i = 1, size(pstruct%parameters)
      call JSONDumpParameter(pstruct%parameters(i))
   end do
   write(fates_log(),*) '============ End FATES Parameter Info ========='
end if

call FatesTransferParameters()                      ! distribute to module storage
```

`pstruct` is a module-scoped `params_type` instance held by `main/FatesParametersInterface.F90`. `JSONRead` is implemented in `main/JSONParameterUtilsMod.F90:189-251`, with the parser doing a two-pass scan (`GetDimensions` then `GetParameters`) to populate `pstruct%dimensions(:)` and `pstruct%parameters(:)`.

`FatesTransferParameters()` `(main/FatesInterfaceMod.F90:2675-2694)` is a thin wrapper:

```fortran
call TransferParamsGeneric(pstruct)        ! main/EDParamsMod.F90:274
call TransferParamsSpitFire(pstruct)       ! fire/SFParamsMod.F90:169
call TransferParamsPRT(pstruct)            ! parteh/PRTParamsFATESMod.F90:62
call TransferParamsLeafBiophys(pstruct)    ! biogeophys/FatesLeafBiophysParamsMod.F90:26
call TransferParamsPFT(pstruct)            ! main/EDPftvarcon.F90:306
```

Each `TransferParams*` routine queries `pstruct%GetParamFromName("fates_<name>")` and copies the value into module-level storage in one pass. There are no separate `*RegisterParams` or `*ReceiveParams` routines; the module-level `FatesParametersInterface.F90` (76 lines) only holds `pstruct` and the two transpose helpers.

### Public API on `params_type`

The `params_type` (declared at `main/JSONParameterUtilsMod.F90:158-166`) exposes:

| Method | Purpose |
|--------|---------|
| `GetDimSizeFromName(dim_name)` | Return integer size for a named dimension |
| `GetParamFromName(param_name)` | Return pointer to a `param_type` record |
| `ReportAccessCounts()` | Print how many times each parameter has been read (debug) |
| `Destroy()` | Deallocate parameter and dimension arrays |

Each `param_type` (`main/JSONParameterUtilsMod.F90:129-156`) carries `name`, `units`, `long_name`, `dtype`, `dim_names(:)`, `ndims`, `access_count`, plus typed data slots (`r_data_scalar`, `r_data_1d`, `r_data_2d`, `i_data_scalar`, `i_data_1d`, `i_data_2d`, `c_data`, `c_data_1d`, `c_data_2d`). Only the slot matching the parameter's dtype/shape is populated.

## Parameter Storage Modules

FATES splits parameters across specialized modules by scope and usage.

### `EDParamsMod` — Global Parameters

`main/EDParamsMod.F90` stores scalar parameters that apply globally across the simulation. Key globals (declared at `main/EDParamsMod.F90:23-189` and populated in `TransferParamsGeneric()` at `:274-490`):

| Parameter | JSON name | Type | Description |
|-----------|-----------|------|-------------|
| `mortality_disturbance_fraction` | `fates_mort_disturb_frac` | `real(r8)` | Fraction of canopy mortality that causes disturbance |
| `comp_excln_exp` | `fates_comp_excln` | `real(r8)` | Weighting factor for canopy exclusion/promotion |
| `q10_mr` | `fates_q10_mr` | `real(r8)` | Q10 for maintenance respiration |
| `q10_froz` | `fates_q10_froz` | `real(r8)` | Q10 for frozen-soil respiration |
| `ED_val_phen_a/b/c` | `fates_phen_gddthresh_a/b/c` | `real(r8)` | GDD accumulation function coefficients |
| `ED_val_phen_chiltemp` | `fates_phen_chilltemp` | `real(r8)` | Chilling-day threshold |
| `ED_val_phen_coldtemp` | `fates_phen_coldtemp` | `real(r8)` | Cold-day threshold for leaf drop |
| `ED_val_phen_mindayson` | `fates_phen_mindayson` | `real(r8)` | Minimum days leaves must stay on |
| `ED_val_phen_ncolddayslim` | `fates_phen_ncolddayslim` | `real(r8)` | Cold-day count required to trigger leaf drop |
| `ED_val_cohort_size_fusion_tol` | `fates_cohort_size_fusion_tol` | `real(r8)` | DBH similarity threshold for cohort fusion |
| `ED_val_cohort_age_fusion_tol` | `fates_cohort_age_fusion_tol` | `real(r8)` | Age similarity threshold for cohort fusion |
| `ED_val_patch_fusion_tol` | `fates_patch_fusion_tol` | `real(r8)` | Profile similarity threshold for patch fusion |
| `ED_val_canopy_closure_thresh` | `fates_canopy_closure_thresh` | `real(r8)` | Canopy-closure threshold for crown allometry |
| `max_cohort_per_patch` | `fates_maxcohort` | integer | Max cohorts per patch |
| `maxpatches_by_landuse(:)` | `fates_maxpatches_by_landuse` | integer (n_landuse_cats) | Max patches per land-use class — replaces scalar `maxpatch_primary`/`maxpatch_secondary` |
| `max_nocomp_pfts_by_landuse(:)` | `fates_max_nocomp_pfts_by_landuse` | integer (n_landuse_cats) | Max nocomp PFTs per land-use class |
| `eca_plant_escalar` | `fates_cnp_eca_plant_escalar` | `real(r8)` | Plant fine-root scaling factor for ECA |
| `nclmax` | (parameter constant) | integer | **3** (was 2 in earlier API) — maximum canopy layers |

**Important renames and relocations vs. earlier API generations:**

- `fates_mortality_disturbance_fraction` → `fates_mort_disturb_frac` in the JSON file (the in-code variable name `mortality_disturbance_fraction` is unchanged at `main/EDParamsMod.F90:43`).
- `stomatal_model` and `photo_tempsens_model` are no longer in `EDParamsMod`. They are now members of `lb_params` in `biogeophys/LeafBiophysicsMod.F90` (`lb_params%stomatal_model`, `lb_params%photo_tempsens_model`). Set via `set_fates_ctrlparms()` `case` branches at `main/FatesInterfaceMod.F90:2103` (case `'photosynth_acclimation'`) and `:2119` (case `'stomatal_model'`).
- `maintresp_leaf_model` and `radiation_model` are no longer parameter-file driven. They are HLM-namelist-driven `hlm_*` flags declared at `main/FatesInterfaceTypesMod.F90:162` and `:169`, and set via `case('maintresp_leaf_model')` at `main/FatesInterfaceMod.F90:2140` and `case('radiation_model')` at `:2152`.
- `mort_cstarvation_model` is similarly namelist-driven `hlm_mort_cstarvation_model` at `main/FatesInterfaceTypesMod.F90:165`.
- `maxpatch_primary` and `maxpatch_secondary` no longer exist as separate scalars. They are replaced by `maxpatches_by_landuse(n_landuse_cats)` at `main/EDParamsMod.F90:152`, indexed by the land-use enumeration `(primaryland, secondaryland, rangeland, pastureland, cropland)`.
- `ED_val_comp_excln` is renamed to `comp_excln_exp` at `main/EDParamsMod.F90:44`.

Calibration recommendations using the old names will fail with a "missing parameter" error from `JSONRead`.

### `EDPftvarcon` — PFT-Specific Parameters

`EDPftvarcon_type` (instance `EDPftvarcon_inst`) stores parameters that vary by PFT. Most are `(numpft)` arrays; some have additional dimensions such as `(nleafage, numpft)` for `vcmax25top`, `(n_hydr_organs, numpft)` for `fates_hydro_*_node`, or `(numpft, num_swb)` for `rhol`, `rhos`, `taul`, `taus`. PFT-dimensioned parameters are distributed by `TransferParamsPFT()` `(main/EDPftvarcon.F90:306)`. Validation: `FatesCheckParams()` `(main/EDPftvarcon.F90:934)`. Reporting: `FatesReportPFTParams()` `(main/EDPftvarcon.F90:817)`.

### `PRTParamsFATESMod` — Allocation Parameters

Parameters for the PARTEH allocation system are stored in the `prt_params` global structure in `parteh/PRTParametersMod.F90`. Distribution from `pstruct` is performed by `TransferParamsPRT()` `(parteh/PRTParamsFATESMod.F90:62)`. Derived constants are computed by `PRTDerivedParams()` `(:490)`, and validation by `PRTCheckParams()` `(:515)`. Key groups:

| Group | Examples |
|-------|----------|
| Biomass | `wood_density`, `c2b` |
| Leaf | `slatop`, `leaf_long(:,:)` |
| Root | `root_long`, `root_rho` |
| Stoichiometry | `nitr_stoich_p1(:,:)`, `phos_stoich_p1(:,:)` |
| Growth | `grperc` (growth respiration fraction) |
| Turnover | `leaf_turnover`, `root_turnover` |

The structure supports both carbon-only and CNP flexible allocation modes through the appropriate subset of parameters.

### `SFParamsMod` — Fire Parameters

`fire/SFParamsMod.F90` manages fire parameters for the SPITFIRE fire model. Distribution: `TransferParamsSpitFire()` `(fire/SFParamsMod.F90:169)`. Validation: `SpitFireCheckParams()` `(:64)`. Categories include:

- **Ignition** — lightning and anthropogenic ignition rates
- **Fuel** — fuel moisture, bulk density, mineral damping
- **Spread** — rate of spread and wind effects
- **Effects** — crown scorch, cambial damage, mortality

### `LeafBiophysicsMod` / `FatesLeafBiophysParamsMod` — Leaf Biophysics

`biogeophys/LeafBiophysicsMod.F90` declares the type `leafbiophys_params_type` (line 184) and its singleton `lb_params`, which now own:

- `lb_params%stomatal_model` — 1=Ball-Berry, 2=Medlyn (line 211)
- `lb_params%photo_tempsens_model` — 1=non-acclimating, 2=Kumarathunge 2019 (line 206)
- FvCB1980 and other photosynthesis temperature-response constants

Distribution from `pstruct` to `lb_params` is performed by `TransferParamsLeafBiophys()` `(biogeophys/FatesLeafBiophysParamsMod.F90:26)`. Reporting is `LeafBiophysReportParams()` `(:111)`. The mode selectors are also written into `lb_params` from namelist `case` branches in `main/FatesInterfaceMod.F90:2103, 2119`.

## Parameter File Initialization Flow

Overall path from the HLM to the parameter storage modules at api.43:

```
HLM → SetFatesGlobalElements1     (main/FatesInterfaceMod.F90:792)
        → JSONRead(paramfile, pstruct)             ! main/JSONParameterUtilsMod.F90:189
        → FatesTransferParameters()                 ! main/FatesInterfaceMod.F90:2675
            ├─ TransferParamsGeneric(pstruct)       ! main/EDParamsMod.F90:274
            ├─ TransferParamsSpitFire(pstruct)      ! fire/SFParamsMod.F90:169
            ├─ TransferParamsPRT(pstruct)           ! parteh/PRTParamsFATESMod.F90:62
            ├─ TransferParamsLeafBiophys(pstruct)   ! biogeophys/FatesLeafBiophysParamsMod.F90:26
            └─ TransferParamsPFT(pstruct)           ! main/EDPftvarcon.F90:306
    → SetFatesGlobalElements2     (main/FatesInterfaceMod.F90:897)
        → numpft, nleafage, nlevsclass, n_uptake_mode, p_uptake_mode, max_comp_per_site
        → InitHydroGlobals(), InitPARTEHGlobals(), fates_history_maps()
        → FatesCheckParameters()  ! main/FatesInterfaceMod.F90:2697
            └─ TransferRadParams, FatesReportPFTParams, FatesReportParams,
               LeafBiophysReportParams, PRTDerivedParams, FatesCheckParams,
               PRTCheckParams, SpitFireCheckParams
```

`numpft` is determined from the parameter file via `size(prt_params%wood_density,dim=1)` `(main/FatesInterfaceMod.F90:911-913)`.

## Parameter Validation and Reporting

### Validation Functions

Each parameter module provides a checking routine, all invoked from `FatesCheckParameters()` at `main/FatesInterfaceMod.F90:2697-2720`:

- `FatesCheckParams()` — PFT and global parameters (`main/EDPftvarcon.F90:934`)
- `SpitFireCheckParams()` — fire parameters (`fire/SFParamsMod.F90:64`)
- `PRTCheckParams()` — allocation parameters (stoichiometry ratios, allometry modes) (`parteh/PRTParamsFATESMod.F90:515`)

Typical checks include ensuring fraction parameters are in `[0,1]`, required parameters are not at the unset sentinel `fates_check_param_set+10`, and related parameters are consistent.

### Parameter Reporting

`FatesReportParams()` `(main/EDParamsMod.F90:495)` writes generic parameter values, `FatesReportPFTParams()` `(main/EDPftvarcon.F90:817)` writes PFT-dimensioned parameters, and `LeafBiophysReportParams()` `(biogeophys/FatesLeafBiophysParamsMod.F90:111)` writes leaf biophysics parameters. All three are gated on a debug flag and dump to `fates_log()` at initialization, creating a permanent record of the exact parameter values used by each run. `JSONDumpParameter()` `(main/JSONParameterUtilsMod.F90:1215)` provides a per-parameter dump of the raw `pstruct` contents.

## Default Coupled Mode (api.43 change)

At api.43 the defaults of `fates_cnp_prescribed_nuptake` and `fates_cnp_prescribed_puptake` have been **flipped from 1.0 to 0.0** for all PFTs (`parameter_files/fates_params_default.json:495-507`). This means the default behavior is now **fully coupled** N and P uptake (the HLM provides plant nutrient uptake fluxes through `bc_in%plant_nh4_uptake_flux`, `plant_no3_uptake_flux`, `plant_p_uptake_flux`). The mode is selected automatically in `SetFatesGlobalElements2()` `(main/FatesInterfaceMod.F90:962-972)`:

```fortran
if (any(abs(EDPftvarcon_inst%prescribed_nuptake(:)) > nearzero )) then
   n_uptake_mode = prescribed_n_uptake
else
   n_uptake_mode = coupled_n_uptake
end if
```

The PARTEH PID controller for adaptive fine-root allocation is gated on `(coupled_*_uptake .and. .not. hlm_*_suppl)`, see `parteh/PRTAllometricCNPMod.F90:1910-1911`:

```fortran
limiting_p = ((p_uptake_mode .eq. coupled_p_uptake) .and. (hlm_phosphorus_suppl .eq. ifalse))
limiting_n = ((n_uptake_mode .eq. coupled_n_uptake) .and. (hlm_nitrogen_suppl .eq. ifalse))
```

## Key Parameter Categories

### Allometry Parameters

Allometry parameters define size relationships between DBH and height, leaf area, biomass, and crown area. Most are stored in `prt_params` and accessed through allometry functions in `biogeochem/FatesAllometryMod.F90`. Major relationships:

- DBH → height: `fates_allom_d2h1`, `fates_allom_d2h2`, `fates_allom_d2h3`
- DBH → leaf biomass: `fates_allom_d2bl1`, `fates_allom_d2bl2`, `fates_allom_d2bl3`
- DBH → crown area: `fates_allom_d2ca_coefficient_min`, `fates_allom_d2ca_coefficient_max`
- Leaf area → sapwood area: `fates_allom_la_per_sa_int`, `fates_allom_la_per_sa_slp`
- AGB allometry: `fates_allom_agb1`..`fates_allom_agb4`

Mode switches pick the functional form:

- `fates_allom_hmode` — height function index
- `fates_allom_lmode` — leaf biomass function index
- `fates_allom_smode` — sapwood function index
- `fates_allom_amode` — AGB function index

### Photosynthesis Parameters

Key photosynthesis parameters:

- `fates_leaf_vcmax25top` — maximum carboxylation rate at 25 °C, canopy top (`fates_leafage_class × fates_pft`); JSON entry at `parameter_files/fates_params_default.json:915`
- `fates_leaf_slatop` — specific leaf area at canopy top (`:880`)
- `fates_leaf_stomatal_slope_ballberry` — Ball-Berry stomatal slope (`:901`)
- `fates_leaf_stomatal_slope_medlyn` — Medlyn stomatal slope (`:908`)
- `fates_leaf_stomatal_intercept` — minimum stomatal conductance (`:894`)
- `fates_leaf_c3psn` — photosynthetic pathway flag (1=C3, 0=C4) (`:838`)

Kumarathunge temperature-sensitivity parameters: `fates_leaf_vcmaxha`, `fates_leaf_vcmaxhd`, `fates_leaf_vcmaxse`, and the corresponding `_jmax*` set.

### Mortality Parameters

Mortality parameters control death processes:

| Parameter | Purpose | JSON entry |
|-----------|---------|------------|
| `fates_mort_bmort` | Background mortality rate (1/yr) | `:1006` |
| `fates_mort_scalar_cstarvation` | Max mortality rate from carbon starvation (1/yr) | `:1083` |
| `fates_mort_upthresh_cstarvation` | Storage threshold above which starvation mortality is zero | `:1097` |
| `fates_mort_scalar_hydrfailure` | Max mortality rate from hydraulic failure (1/yr) | `:1090` |
| `fates_mort_hf_sm_threshold` | Soil moisture threshold (non-hydraulic model) | `:1027` |
| `fates_mort_hf_flc_threshold` | Fractional loss of conductivity threshold (hydraulic model) | `:1020` |
| `fates_mort_ip_size_senescence` | DBH inflection point for size-dependent senescence | `:1041` |
| `fates_mort_freezetol` | Minimum temperature tolerance (°C) | `:1013` |
| `fates_mort_scalar_coldstress` | Max mortality from cold stress (1/yr) | `:1076` |

### Hydraulics Parameters

Plant hydraulics parameters are active when `hlm_use_planthydro == itrue`:

Organ-level (dimensioned by `fates_hydr_organs × fates_pft`):

- `fates_hydro_p50_node` — water potential at 50% conductivity loss (MPa) (`:712`)
- `fates_hydro_avuln_node` — vulnerability curve shape parameter (`:670`)
- `fates_hydro_kmax_node` — maximum xylem conductivity (kg/MPa/m/s) (`:698`)
- `fates_hydro_epsil_node` — bulk elastic modulus (MPa)
- `fates_hydro_fcap_node` — fraction of non-residual water that is capillary

Stomatal control:

- `fates_hydro_p50_gs` — water potential at 50% stomatal closure (MPa)
- `fates_hydro_avuln_gs` — stomatal vulnerability shape parameter

### Nutrient Parameters (CNP Mode)

Nutrient acquisition parameters for nitrogen and phosphorus dynamics:

Uptake kinetics (per PFT):

- `fates_cnp_vmax_nh4` — maximum NH4 uptake rate (gN/gC/s) (`:530`)
- `fates_cnp_vmax_no3` — maximum NO3 uptake rate (gN/gC/s) (`:537`)
- `fates_cnp_vmax_p` — maximum P uptake rate (gP/gC/s) (`:544`)

ECA parameters:

- `fates_cnp_eca_km_nh4`, `fates_cnp_eca_km_no3`, `fates_cnp_eca_km_p` — half-saturation constants (`:411, :418, :425`)
- `fates_cnp_eca_vmax_ptase` — maximum phosphatase production (`:446`)
- `fates_cnp_eca_km_ptase` — half-saturation for biochemical P (`:432`)
- `fates_cnp_eca_alpha_ptase` — fraction of phosphatase-released P that flows to plant (`:397`)
- `fates_cnp_eca_decompmicc` — maximum microbial decomposer biomass (`:404`)
- `fates_cnp_eca_plant_escalar` — site-wide ECA scalar (set into `EDParamsMod::eca_plant_escalar`)

Storage and allocation:

- `fates_cnp_nitr_store_ratio` — storable N as ratio to structural N (`:460`)
- `fates_cnp_phos_store_ratio` — storable P as ratio to structural P (`:467`)
- `fates_cnp_store_ovrflw_frac` — overflow storage size (`:509`)

PID controller for adaptive fine-root allocation (gated on coupled-uptake; see "Default Coupled Mode" above):

- `fates_cnp_pid_kp` — proportional constant (`:488`)
- `fates_cnp_pid_ki` — integral constant (`:481`)
- `fates_cnp_pid_kd` — derivative constant (`:474`)

Coupling defaults (api.43 change):

- `fates_cnp_prescribed_nuptake` — default 0.0 for all 14 PFTs → coupled N uptake (`:495`)
- `fates_cnp_prescribed_puptake` — default 0.0 for all 14 PFTs → coupled P uptake (`:502`)

## Parameter Usage in Code

Parameters are accessed directly from their respective module singletons:

```fortran
! Global
use EDParamsMod, only : ED_val_phen_coldtemp, q10_mr, mortality_disturbance_fraction

! Leaf biophysics (NEW HOME for stomatal_model and photo_tempsens_model)
use LeafBiophysicsMod, only : lb_params
ist = lb_params%stomatal_model

! HLM-namelist-driven (NEW HOME for maintresp/radiation/cstarvation models)
use FatesInterfaceTypesMod, only : hlm_maintresp_leaf_model, hlm_radiation_model

! PFT-specific
use EDPftvarcon, only : EDPftvarcon_inst
vcmax25 = EDPftvarcon_inst%vcmax25top(1, ft)

! Allocation
use PRTParametersMod, only : prt_params
slatop  = prt_params%slatop(ft)
```

This direct-access pattern (rather than passing parameters through function arguments) is used throughout FATES for simplicity. The boundary-condition parameter constants in `bc_pconst` are the exception, those are copied into the interface structure so the HLM can use them during its own coupled BGC work.
