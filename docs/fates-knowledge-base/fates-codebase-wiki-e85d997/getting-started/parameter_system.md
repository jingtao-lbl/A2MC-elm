---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

# Parameter System

## Purpose and Scope

This document describes the FATES parameter system, which defines the configuration values that control model behavior. It covers the parameter file structure, the two-phase loading mechanism, and the storage modules that manage parameters at runtime. For Python tooling, see [Parameter Management Tools](parameter_tools.md). For how parameters flow into specific processes, see [PARTEH](../plant-physiology/parteh/index.md) and [Fire Dynamics: SPITFIRE](../fire/index.md).

## Parameter File Structure

FATES parameters are stored in NetCDF files. The canonical definition is human-readable CDL (Common Data Language) at `parameter_files/fates_params_default.cdl`.

### File Organization

The default file declares the following dimensions `(parameter_files/fates_params_default.cdl:1-16)`:

- `fates_pft` — number of plant functional types (default 12)
- `fates_leafage_class` — number of leaf age classes (default 1)
- `fates_hydr_organs` — hydraulic organs (default 4 — leaf, stem, transporting root, absorbing root)
- `fates_plant_organs` — allocation organs (default 4 — leaf, fineroot, sapwood, store)
- `fates_history_size_bins`, `fates_history_age_bins`, `fates_history_height_bins`, `fates_history_coage_bins`, `fates_history_damage_bins` — history bin edges
- `fates_NCWD` — coarse woody debris size classes (default 4)
- `fates_litterclass` — litter decomposition classes (default 6)
- `fates_hlm_pftno` — number of HLM surface-dataset PFTs (default 14)
- `fates_string_length` — character string length (default 60)

Each variable has `units` and `long_name` attributes. Variables may be scalar or multi-dimensional, and character arrays store names (PFT names, organ names). Example:

```
double fates_leaf_vcmax25top(fates_leafage_class, fates_pft) ;
    fates_leaf_vcmax25top:units = "umol CO2/m^2/s" ;
    fates_leaf_vcmax25top:long_name = "maximum carboxylation rate of Rub. at 25C, canopy top" ;
```

Source: `parameter_files/fates_params_default.cdl:368-370`.

## Parameter Loading Architecture

FATES uses a two-phase parameter loading system that separates parameter declaration from parameter population. This design lets the host land model (HLM) manage file I/O while FATES declares its requirements.

### Two-Phase Loading System

`FatesReadParameters()` `(main/FatesInterfaceMod.F90:2399)` drives the full flow:

```fortran
allocate(fates_params)
call fates_params%Init()               ! FatesParametersInterface.F90

call FatesRegisterParams(fates_params)                         ! main/EDParamsMod.F90
call SpitFireRegisterParams(fates_params)                      ! fire/SFParamsMod.F90
call PRTRegisterParams(fates_params)                           ! parteh/PRTInitParamsFATESMod.F90
call FatesSynchronizedParamsInst%RegisterParams(fates_params)  ! main/FatesSynchronizedParamsMod.F90

call param_reader%Read(fates_params)   ! HLM-supplied NetCDF reader

call FatesReceiveParams(fates_params)                          ! pulls values into module storage
call SpitFireReceiveParams(fates_params)
call PRTReceiveParams(fates_params)
call FatesSynchronizedParamsInst%ReceiveParams(fates_params)
```

Call sites: `main/FatesInterfaceMod.F90:2413-2423`.

### Parameter Interface Classes

`FatesParametersInterface.F90` defines `fates_parameters_type` and the reader interface `fates_param_reader_type`. Key methods:

- `RegisterParameter(name, dimension_shape, dimension_names, lower_bounds)` `(main/FatesParametersInterface.F90:143)`
- `RetrieveParameter` — scalar / 1D / 2D variants `(main/FatesParametersInterface.F90:185, 202, 229)`
- `RetrieveParameterAllocate` — 1D and 2D allocatable variants `(main/FatesParametersInterface.F90:260)`

### Registration Phase Details

During registration, each module declares what it needs by calling `RegisterParameter`. The call specifies:

- **name** — matches the NetCDF variable name (e.g. `fates_mort_freezetol`)
- **dimension_shape** — scalar, 1D, or 2D
- **dimension_names** — e.g. `fates_pft`, `fates_hydr_organs`, `fates_leafage_class`
- **lower_bounds** — typically 1

Example from `EDPftvarcon::Register_PFT()` `(main/EDPftvarcon.F90:372-374)`:

```fortran
name = 'fates_mort_freezetol'
call fates_params%RegisterParameter(name=name, dimension_shape=dimension_shape_1d, &
     dimension_names=dim_names, lower_bounds=dim_lower_bound)
```

### Receive Phase Details

During `Receive`, modules pull values from the parameter object into their storage. For PFT-dimensioned parameters, `EDPftvarcon::Receive` dispatches to `Receive_PFT`, `Receive_PFT_numrad`, `Receive_PFT_hydr_organs`, and `Receive_PFT_leafage` `(main/EDPftvarcon.F90:332-346)`. Array sizes are determined from the parameter file itself: `numpft` is set in `SetFatesGlobalElements2()` from `size(prt_params%wood_density,dim=1)` `(main/FatesInterfaceMod.F90:823-831)`.

## Parameter Storage Modules

FATES splits parameters across specialized modules by scope and usage.

### `EDParamsMod` — Global Parameters

`main/EDParamsMod.F90` stores scalar parameters that apply globally across the simulation. Key globals:

| Parameter | Type | Description |
|-----------|------|-------------|
| `fates_mortality_disturbance_fraction` | `real(r8)` | Fraction of canopy mortality that causes disturbance |
| `ED_val_comp_excln` | `real(r8)` | Weighting factor for canopy exclusion/promotion |
| `stomatal_model` | integer | 1=Ball-Berry, 2=Medlyn `(main/EDParamsMod.F90:73)` |
| `regeneration_model` | integer | 1=default, 2=TRS (Hanbury-Brown et al. 2022), 3=TRS without seedling dynamics `(main/EDParamsMod.F90:74-77)` |
| `photo_tempsens_model` | integer | 1=non-acclimating, 2=Kumarathunge 2019 `(main/EDParamsMod.F90:47-49)` |
| `maintresp_leaf_model` | integer | 1=Ryan 1991, 2=Atkin 2017 `(main/EDParamsMod.F90:35)` |
| `radiation_model` | integer | 1=Norman, 2=Two-stream `(main/EDParamsMod.F90:51)` |
| `q10_mr` | `real(r8)` | Q10 for maintenance respiration `(main/EDParamsMod.F90:134)` |
| `maxpatch_primary` | integer | Max primary patches per site `(main/EDParamsMod.F90:251)` |
| `maxpatch_secondary` | integer | Max secondary patches per site `(main/EDParamsMod.F90:254)` |
| `max_cohort_per_patch` | integer | Max cohorts per patch `(main/EDParamsMod.F90:260)` |

Phenology parameters `(main/EDParamsMod.F90:62-68)`:

- `ED_val_phen_a`, `ED_val_phen_b`, `ED_val_phen_c` — GDD accumulation function coefficients (`gdd_thresh = a + b·exp(c·ncd)`)
- `ED_val_phen_chiltemp` — chilling day counting threshold
- `ED_val_phen_coldtemp` — cold-day threshold for leaf drop
- `ED_val_phen_mindayson` — minimum days leaves must stay on
- `ED_val_phen_ncolddayslim` — cold-day count required to trigger leaf drop

Cohort and patch fusion tolerances `(main/EDParamsMod.F90:69-71)`:

- `ED_val_cohort_size_fusion_tol` — DBH similarity threshold for cohort fusion
- `ED_val_cohort_age_fusion_tol` — age similarity threshold for cohort fusion
- `ED_val_patch_fusion_tol` — profile similarity threshold for patch fusion

### `EDPftvarcon` — PFT-Specific Parameters

`EDPftvarcon_type` (instance `EDPftvarcon_inst`) stores parameters that vary by PFT. Most are `(numpft)` arrays; some have additional dimensions such as `(nleafage, numpft)` for `vcmax25top`, `(n_hydr_organs, numpft)` for `fates_hydro_*_node`, or `(numpft, nSWbands)` for `rhol`, `rhos`, `taul`, `taus`.

Source: `main/EDPftvarcon.F90:45-289`.

### `PRTInitParamsFATESMod` — Allocation Parameters

Parameters for the PARTEH allocation system are stored in the `prt_params` global structure in `parteh/PRTParametersMod.F90`. Key groups:

| Group | Examples |
|-------|----------|
| Biomass | `wood_density`, `c2b` |
| Leaf | `slatop`, `leaf_long(:,:)` |
| Root | `root_long`, `root_rho` |
| Stoichiometry | `nitr_stoich_p1(:,:)`, `phos_stoich_p1(:,:)` |
| Growth | `grperc` (growth respiration fraction) |
| Turnover | `leaf_turnover`, `root_turnover` |

The structure supports both carbon-only and CNP flexible allocation modes through the appropriate subset of parameters. Registration and receive are in `PRTInitParamsFATESMod::PRTRegisterParams` / `PRTReceiveParams`, used at `main/FatesInterfaceMod.F90:71`.

### `SFParamsMod` — Fire Parameters

`fire/SFParamsMod.F90` manages fire parameters for the SPITFIRE fire model. Categories include:

- **Ignition** — lightning and anthropogenic ignition rates
- **Fuel** — fuel moisture, bulk density, mineral damping
- **Spread** — rate of spread and wind effects
- **Effects** — crown scorch, cambial damage, mortality

Used at `main/FatesInterfaceMod.F90:53, 70`.

## Parameter File Initialization Flow

Overall path from the HLM to the parameter storage modules:

```
HLM → SetFatesGlobalElements1     (main/FatesInterfaceMod.F90:737)
        → FatesReadParameters     (main/FatesInterfaceMod.F90:2399)
            ├─ *RegisterParams    (EDParamsMod, SFParamsMod, PRTInitParamsFATESMod, FatesSynchronizedParamsMod)
            ├─ param_reader%Read  (HLM-supplied)
            └─ *ReceiveParams     (same four modules)
    → SetFatesGlobalElements2     (main/FatesInterfaceMod.F90:808)
        → numpft, nleafage, nlevsclass, n_uptake_mode, p_uptake_mode, max_comp_per_site
```

## Parameter Validation and Reporting

### Validation Functions

Each parameter module provides a checking routine:

- `FatesCheckParams()` — global parameters `(main/FatesInterfaceMod.F90:51-52)`
- `SpitFireCheckParams()` — fire parameters
- `PRTCheckParams()` — allocation parameters (stoichiometry ratios, allometry modes) `(main/FatesInterfaceMod.F90:96)`

Typical checks include ensuring fraction parameters are in `[0,1]`, required parameters are not at the unset sentinel, and related parameters are consistent.

### Parameter Reporting

`FatesReportParameters()` `(main/FatesInterfaceMod.F90:1964)` writes all parameter values to the log at initialization, creating a permanent record of the exact parameter values used by each run.

## Key Parameter Categories

### Allometry Parameters

Allometry parameters define size relationships between DBH and height, leaf area, biomass, and crown area. Most are stored in `prt_params` and accessed through allometry functions `(biogeochem/FatesAllometryMod.F90)`. Major relationships:

- DBH → height: `fates_allom_d2h1`, `fates_allom_d2h2`, `fates_allom_d2h3`
- DBH → leaf biomass: `fates_allom_d2bl1`, `fates_allom_d2bl2`, `fates_allom_d2bl3`
- DBH → crown area: `fates_allom_d2ca_coefficient_min`, `fates_allom_d2ca_coefficient_max`
- Leaf area → sapwood area: `fates_allom_la_per_sa_int`, `fates_allom_la_per_sa_slp`
- AGB allometry: `fates_allom_agb1`..`fates_allom_agb4`

Mode switches pick the functional form `(parameter_files/fates_params_default.cdl:74-148)`:

- `fates_allom_hmode` — height function index
- `fates_allom_lmode` — leaf biomass function index
- `fates_allom_smode` — sapwood function index
- `fates_allom_amode` — AGB function index

### Photosynthesis Parameters

Key photosynthesis parameters `(parameter_files/fates_params_default.cdl:341-370)`:

- `fates_leaf_vcmax25top` — maximum carboxylation rate at 25 °C, canopy top (`fates_leafage_class × fates_pft`)
- `fates_leaf_slatop` — specific leaf area at canopy top
- `fates_leaf_stomatal_slope_ballberry` — Ball-Berry stomatal slope
- `fates_leaf_stomatal_slope_medlyn` — Medlyn stomatal slope
- `fates_leaf_stomatal_intercept` — minimum stomatal conductance
- `fates_leaf_c3psn` — photosynthetic pathway flag (1=C3, 0=C4) — confirmed at `parameter_files/fates_params_default.cdl:341-343`

Kumarathunge temperature-sensitivity parameters: `fates_leaf_vcmaxha`, `fates_leaf_vcmaxhd`, `fates_leaf_vcmaxse`, and the corresponding `_jmax*` set.

### Mortality Parameters

Mortality parameters control death processes `(parameter_files/fates_params_default.cdl:395-436)`:

| Parameter | Purpose |
|-----------|---------|
| `fates_mort_bmort` | Background mortality rate (1/yr) |
| `fates_mort_scalar_cstarvation` | Max mortality rate from carbon starvation (1/yr) |
| `fates_mort_upthresh_cstarvation` | Storage threshold above which starvation mortality is zero |
| `fates_mort_scalar_hydrfailure` | Max mortality rate from hydraulic failure (1/yr) |
| `fates_mort_hf_sm_threshold` | Soil moisture threshold (non-hydraulic model) |
| `fates_mort_hf_flc_threshold` | Fractional loss of conductivity threshold (hydraulic model) |
| `fates_mort_ip_size_senescence` | DBH inflection point for size-dependent senescence |
| `fates_mort_freezetol` | Minimum temperature tolerance (°C) |
| `fates_mort_scalar_coldstress` | Max mortality from cold stress (1/yr) |

### Hydraulics Parameters

Plant hydraulics parameters are active when `hlm_use_planthydro == itrue` `(parameter_files/fates_params_default.cdl:284-341)`:

Organ-level (dimensioned by `fates_hydr_organs × fates_pft`):

- `fates_hydro_p50_node` — water potential at 50% conductivity loss (MPa)
- `fates_hydro_avuln_node` — vulnerability curve shape parameter
- `fates_hydro_kmax_node` — maximum xylem conductivity (kg/MPa/m/s)
- `fates_hydro_epsil_node` — bulk elastic modulus (MPa)
- `fates_hydro_fcap_node` — fraction of non-residual water that is capillary

Stomatal control:

- `fates_hydro_p50_gs` — water potential at 50% stomatal closure (MPa)
- `fates_hydro_avuln_gs` — stomatal vulnerability shape parameter

### Nutrient Parameters (CNP Mode)

Nutrient acquisition parameters for nitrogen and phosphorus dynamics `(parameter_files/fates_params_default.cdl:170-236)`:

Uptake kinetics (per PFT):

- `fates_cnp_vmax_nh4` — maximum NH4 uptake rate (gN/gC/s)
- `fates_cnp_vmax_no3` — maximum NO3 uptake rate (gN/gC/s)
- `fates_cnp_vmax_p` — maximum P uptake rate (gP/gC/s)

ECA parameters:

- `fates_cnp_eca_km_nh4`, `fates_cnp_eca_km_no3`, `fates_cnp_eca_km_p` — half-saturation constants
- `fates_cnp_eca_vmax_ptase` — maximum phosphatase production
- `fates_cnp_eca_km_ptase` — half-saturation for biochemical P
- `fates_cnp_eca_alpha_ptase` — fraction of phosphatase-released P that flows to plant
- `fates_cnp_eca_decompmicc` — maximum microbial decomposer biomass

Storage and allocation:

- `fates_cnp_nitr_store_ratio` — storable N as ratio to structural N
- `fates_cnp_phos_store_ratio` — storable P as ratio to structural P
- `fates_cnp_store_ovrflw_frac` — overflow storage size

PID controller for adaptive fine-root allocation:

- `fates_cnp_pid_kp` — proportional constant
- `fates_cnp_pid_ki` — integral constant
- `fates_cnp_pid_kd` — derivative constant

## Parameter Usage in Code

Parameters are accessed directly from their respective module singletons:

```fortran
! Global
use EDParamsMod, only : ED_val_phen_coldtemp, stomatal_model, q10_mr

! PFT-specific
use EDPftvarcon, only : EDPftvarcon_inst
vcmax25 = EDPftvarcon_inst%vcmax25top(1, ft)

! Allocation
use PRTParametersMod, only : prt_params
slatop  = prt_params%slatop(ft)
```

This direct-access pattern (rather than passing parameters through function arguments) is used throughout FATES for simplicity. The boundary-condition parameter constants in `bc_pconst` are the exception: those are copied into the interface structure so the HLM can use them during its own coupled BGC work.
