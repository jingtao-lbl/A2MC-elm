---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# Getting Started

## Purpose and Scope

This page describes how FATES initializes and prepares for simulation. It covers the fundamental concepts needed to understand FATES startup: the host land model interface, parameter loading, and initialization modes.

For detailed information on specific topics, see:

- [Host Model Interface](host_interface.md) — coupling and boundary conditions
- [Initialization Modes](initialization.md) — cold start, inventory, and restart
- [Parameter System](parameter_system.md) — JSON parameter file structure and PFT parameters
- [Parameter Management Tools](parameter_tools.md) — Python tools for JSON parameter manipulation

The core execution loop and daily dynamics are covered in [Core Ecosystem Dynamics](../core-dynamics/index.md).

## Initialization Sequence Overview

FATES initialization occurs through a fixed sequence of calls from the host land model (HLM). The process can be divided into three major phases: Setup, Parameter Loading, and State Initialization.

### Initialization Call Sequence

```
HLM calls:
  FatesInterfaceInit        (main/FatesInterfaceMod.F90:199)   FATES globals + logging
  SetFatesGlobalElements1   (main/FatesInterfaceMod.F90:792)   JSONRead, FatesTransferParameters,
                                                               numpft, maxpatches_by_landuse
  SetFatesGlobalElements2   (main/FatesInterfaceMod.F90:897)   nleafage, element sizing, n/p uptake modes
  allocate_bcpconst         (main/FatesInterfaceMod.F90:236)   one-shot parameter constants
  allocate_bcin             (main/FatesInterfaceMod.F90:443)   per-site input boundary conditions
  allocate_bcout            (main/FatesInterfaceMod.F90:623)   per-site output boundary conditions
  init_site_vars            (main/EDInitMod.F90:131)           allocate per-site arrays
  zero_site                 (main/EDInitMod.F90:278)           initialize to defaults
  set_site_properties       (main/EDInitMod.F90:439)           initial phenology, fire, biogeography
  init_patches              (main/EDInitMod.F90:690)           NBG, inventory, or restart path
```

## The FATES Interface Structure

The primary connection between FATES and the host land model is the `fates_interface_type` object `(main/FatesInterfaceMod.F90:138)`. It is the root of FATES data structures and manages boundary-condition exchange.

### Core Interface Components

| Component | Purpose | Allocation |
|-----------|---------|------------|
| `sites(:)` | Pointer array to FATES site structures containing patches and cohorts | Per site |
| `bc_in(:)` | Input boundary conditions from HLM (meteorology, soil state, etc.) | Per site |
| `bc_out(:)` | Output boundary conditions to HLM (fluxes, canopy properties, etc.) | Per site |
| `bc_pconst` | Parameter constants (nutrient uptake kinetics) | Once per interface |

Sources: `main/FatesInterfaceMod.F90:138-172`.

### Boundary Condition Allocation

The HLM allocates boundary-condition arrays via three routines before FATES site initialization:

| Subroutine | Source | Key Arrays Allocated |
|------------|--------|----------------------|
| `allocate_bcin()` | `main/FatesInterfaceMod.F90:443` | `lightning24`, `solad_parb`, `solai_parb`, `smp_sl`, `tempk_sl`, `h2o_liqvol_sl`, `eff_porosity_sl`, `t_scalar_sisl`, `w_scalar_sisl` |
| `allocate_bcout()` | `main/FatesInterfaceMod.F90:623` | `fsun_pa`, `laisun_pa`, `btran_pa`, `rootr_pasl`, `albd_parb`, `elai_pa`, `ftdd_parb`, `ftid_parb`, `ftii_parb` |
| `allocate_bcpconst()` | `main/FatesInterfaceMod.F90:236` | `vmax_nh4`, `vmax_no3`, `vmax_p`, `eca_km_nh4`, `eca_km_no3`, `eca_km_p`, `eca_km_ptase`, `eca_vmax_ptase`, `eca_alpha_ptase`, `eca_lambda_ptase`, `j_uptake`. `eca_plant_escalar` is set as a scalar field within `set_bcpconst()` `(main/FatesInterfaceMod.F90:275)`. |

## One-Shot JSON Parameter Loading

Earlier API generations used a two-phase Register/Receive flow with NetCDF parameter files. At api.43, this has been replaced by a one-shot JSON loader. The flow is implemented inside `SetFatesGlobalElements1()` `(main/FatesInterfaceMod.F90:792)`:

```
call JSONSetInvalid(fates_check_param_set+10._r8)   ! sentinel for nan/null
call JSONSetLogInit(fates_log())
call JSONRead(paramfile, pstruct)                   ! read entire JSON into pstruct
...
call FatesTransferParameters()                      ! distribute pstruct → modules
```

`pstruct` is a module-level `params_type` instance held by `FatesParametersInterface.F90` and populated by `JSONRead` (defined at `main/JSONParameterUtilsMod.F90:189`). `FatesTransferParameters()` `(main/FatesInterfaceMod.F90:2675-2694)` is a thin dispatcher:

```
call TransferParamsGeneric(pstruct)        ! main/EDParamsMod.F90:274
call TransferParamsSpitFire(pstruct)       ! fire/SFParamsMod.F90
call TransferParamsPRT(pstruct)            ! parteh/PRTParamsFATESMod.F90 (declares module PRTInitParamsFatesMod)
call TransferParamsLeafBiophys(pstruct)    ! biogeophys/LeafBiophysicsMod.F90
call TransferParamsPFT(pstruct)            ! main/EDPftvarcon.F90:306
```

There are no separate `*RegisterParams` and `*ReceiveParams` calls. Each `TransferParams*` routine queries `pstruct%GetParamFromName("fates_<name>")` and copies the value into module storage in one pass.

## Initialization Modes

FATES supports three distinct initialization modes, each appropriate for different simulation scenarios. The mode is selected by the `hlm_is_restart` and `hlm_use_inventory_init` flags, both declared in `main/FatesInterfaceTypesMod.F90` (lines 37 and 197).

### Initialization Mode Decision Tree

```
hlm_is_restart == itrue              → Restart mode    (FatesRestartInterfaceMod)
hlm_use_inventory_init == itrue      → Inventory mode  (FatesInventoryInitMod)
otherwise                            → Near-Bare-Ground (EDInitMod::init_patches)
```

Entry at `main/EDInitMod.F90:690` (`init_patches`); the inventory dispatch is at `:756-765` and forwards to `initialize_sites_by_inventory()` `(main/FatesInventoryInitMod.F90:121)`.

### Initialization Mode Comparison

| Mode | When Used | State Source | Key Modules |
|------|-----------|--------------|-------------|
| Restart | Continuing previous simulation | Restart file (NetCDF) | `main/FatesRestartInterfaceMod.F90` |
| Inventory | Initializing from field data | PSS/CSS inventory files | `main/FatesInventoryInitMod.F90` |
| Near-Bare-Ground | Cold start with minimal vegetation | Parameter defaults | `main/EDInitMod.F90:690` (`init_patches`) |

See [Initialization Modes](initialization.md) for details.

## Site Structure Initialization

After parameter loading, FATES initializes site-level data structures. Each site represents a geographic location and holds patches in an age-ordered linked list.

### Site Array Allocations

Arrays allocated during `init_site_vars()` `(main/EDInitMod.F90:131-275)`:

| Array | Dimensions | Purpose |
|-------|------------|---------|
| `term_nindivs_canopy` | `n_term_mort_types × nlevsclass × numpft` | Terminated canopy individuals by mortality type / size / PFT |
| `term_nindivs_ustory` | `n_term_mort_types × nlevsclass × numpft` | Terminated understory individuals |
| `fmort_rate_canopy` | `nlevsclass × numpft` | Fire mortality rates (canopy) |
| `fmort_rate_ustory` | `nlevsclass × numpft` | Fire mortality rates (understory) |
| `imort_rate` | `nlevsclass × numpft` | Impact mortality rates |
| `growthflux_fusion` | `nlevsclass × numpft` | Cohort growth fusion flux |
| `mass_balance(:)` | `num_elements` | Track carbon/nutrient conservation |
| `iflux_balance(:)` | `num_elements` | Integrated element flux diagnostics |
| `area_pft` | `numpft × n_landuse_cats` | PFT area fractions by land-use class |
| `landuse_vector_gt_min` | `n_landuse_cats` | Active land-use categories |
| `area_by_age` | `nlevage` | Patch area by age class |
| `rec_l2fr` | `numpft × nclmax` | Mean L2FR of recruits for CNP dynamics |
| `sp_tlai`, `sp_tsai`, `sp_htop` | `numpft` | Satellite phenology inputs |
| `seed_in` | `numpft` | Incoming seed flux pool |
| `seed_out` | `numpft` | Outgoing seed flux pool (dispersal) |
| `flux_diags%nh4_uptake_scpf` etc. | `numpft × nlevsclass` (flattened) | Per-PFT × size-class flux diagnostics |

**Note.** The drought-phenology water-memory field `liqvol_memory(numWaterMem, maxpft)` is a *fixed-size* member of `ed_site_type`, declared at `main/EDTypesMod.F90:444`, not an allocatable. `numWaterMem = 10` and `maxpft = 16` are parameters from `EDTypesMod.F90:85` and `EDParamsMod.F90:91`. Restart and history I/O expose differently named identifiers (e.g. `ir_liqvolmem_siwmft` in `FatesRestartInterfaceMod`, `ih_seed_bank_si` in `FatesHistoryInterfaceMod`); those are I/O labels, not site-struct field names.

## PFT Parameter Structure

Plant Functional Type (PFT) parameters control vegetation physiology, allometry, and life history traits. They are loaded during initialization and accessed through the `EDPftvarcon_inst` singleton declared in `main/EDPftvarcon.F90`. PFT-dimensioned parameters are distributed from `pstruct` into `EDPftvarcon_inst` by `TransferParamsPFT()` `(main/EDPftvarcon.F90:306)`. Validation is performed by `FatesCheckParams()` `(main/EDPftvarcon.F90:934)`. Reporting is performed by `FatesReportPFTParams()` `(main/EDPftvarcon.F90:817)`. Most fields are `(numpft)` arrays; some have additional dimensions such as `(nleafage, numpft)` for `vcmax25top`, or `(num_swb, numpft)` for `rhol`, `rhos`, `taul`, `taus`.

### Number of PFTs

The default parameter file `parameter_files/fates_params_default.json` defines **14 PFTs** at e027a40 (was 12 in earlier API generations). The PFT list at indices 1-14 is:

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
10 broadleaf_evergreen_arctic_shrub        (NEW)
11 broadleaf_colddecid_arctic_shrub        (NEW)
12 arctic_c3_grass                         (was index 10)
13 cool_c3_grass                           (NEW)
14 c4_grass                                (NEW)
```

(`parameter_files/fates_params_default.json:73`). The maximum allowable number of PFTs is `maxpft = 16` `(main/EDParamsMod.F90:91)`; if the JSON file declares more, FATES aborts in `SetFatesGlobalElements2()` at `main/FatesInterfaceMod.F90:920-925`.

### Key PFT Parameter Categories

| Category | Example Parameters | Notes |
|----------|--------------------|-------|
| Allometry | `fates_allom_d2h1`, `fates_allom_d2h2`, `fates_allom_d2bl1`, `fates_allom_l2fr` | Mode flags: `fates_allom_hmode`, `fates_allom_lmode`, `fates_allom_smode`, `fates_allom_amode` |
| Photosynthesis | `fates_leaf_vcmax25top`, `fates_leaf_slatop`, `fates_leaf_stomatal_slope_ballberry`, `fates_leaf_stomatal_slope_medlyn`, `fates_leaf_stomatal_intercept`, `fates_leaf_c3psn` | C3/C4 path flag is per-PFT |
| Mortality | `fates_mort_bmort`, `fates_mort_scalar_cstarvation`, `fates_mort_scalar_hydrfailure`, `fates_mort_freezetol`, `fates_mort_scalar_coldstress` | |
| Hydraulics | `fates_hydro_p50_node`, `fates_hydro_avuln_node`, `fates_hydro_kmax_node`, `fates_hydro_p50_gs`, `fates_hydro_avuln_gs` | Only active when `hlm_use_planthydro==itrue` |
| Phenology | `fates_phen_evergreen`, `fates_phen_stress_decid`, `fates_phen_flush_fraction` | |
| Fire | `fates_fire_alpha_SH`, `fates_fire_bark_scaler`, `fates_fire_crown_kill` | |

## Global Configuration Flags

FATES behavior is controlled by global flags set by the host model during initialization. These flags live in `main/FatesInterfaceTypesMod.F90` and remain constant throughout the simulation.

### Critical Global Flags

| Flag | Type | Purpose | Source |
|------|------|---------|--------|
| `hlm_use_planthydro` | integer | Enable plant hydraulics | `main/FatesInterfaceTypesMod.F90:142` |
| `hlm_parteh_mode` | integer | PARTEH allocation hypothesis (1=C-only, 2=CNP) | `main/FatesInterfaceTypesMod.F90:85` |
| `hlm_use_sp` | integer | Satellite phenology mode | `main/FatesInterfaceTypesMod.F90:216` |
| `hlm_use_nocomp` | integer | No-competition mode | `main/FatesInterfaceTypesMod.F90:213` |
| `hlm_use_fixed_biogeog` | integer | Fixed biogeography | `main/FatesInterfaceTypesMod.F90:210` |
| `hlm_use_lu_harvest` | integer | Use HLM land-use harvest data | `main/FatesInterfaceTypesMod.F90:107` |
| `hlm_use_luh` | integer | Use LUH2 land-use drivers | `main/FatesInterfaceTypesMod.F90:119` |
| `hlm_use_inventory_init` | integer | Initialize from inventory files | `main/FatesInterfaceTypesMod.F90:197` |
| `hlm_is_restart` | integer | Restart vs. cold start | `main/FatesInterfaceTypesMod.F90:37` |
| `hlm_use_tree_damage` | integer | Enable tree damage module | `main/FatesInterfaceTypesMod.F90:151` |
| `hlm_use_ed_st3` | integer | Static stand structure (ST3) | `main/FatesInterfaceTypesMod.F90:177` |
| `hlm_spitfire_mode` | integer | Fire model configuration | `main/FatesInterfaceTypesMod.F90:101` |
| `hlm_maintresp_leaf_model` | integer | Leaf maintenance respiration model (1=Ryan 1991, 2=Atkin 2017) | `main/FatesInterfaceTypesMod.F90:162` |
| `hlm_radiation_model` | integer | Radiation model (1=Norman, 2=Two-stream) | `main/FatesInterfaceTypesMod.F90:169` |
| `hlm_mort_cstarvation_model` | integer | Carbon starvation mortality (1=Linear, 2=Exponential) | `main/FatesInterfaceTypesMod.F90:165` |
| `hlm_regeneration_model` | integer | Regeneration model (1=default, 2=TRS, 3=TRS-no-seedlings) | `main/FatesInterfaceTypesMod.F90:172` |

All integer flags use `0=off / 1=on` semantics via `ifalse`/`itrue` constants, except `hlm_spitfire_mode`, `hlm_maintresp_leaf_model`, `hlm_radiation_model`, `hlm_mort_cstarvation_model`, and `hlm_regeneration_model`, which select a configuration. **Note:** `maintresp_leaf_model` and `radiation_model` were previously stored as parameter-file-driven globals in `EDParamsMod`; at e027a40 they are HLM-namelist-driven and live in `FatesInterfaceTypesMod`. The stomatal model and the photosynthesis temperature-sensitivity model are now stored on `lb_params` in `biogeophys/LeafBiophysicsMod.F90` (`lb_params%stomatal_model`, `lb_params%photo_tempsens_model`), set via `set_fates_ctrlparms()` `case('stomatal_model')` at `main/FatesInterfaceMod.F90:2119` and `case('photosynth_acclimation')` at `:2103`.

## Summary: From Initialization to First Timestep

The complete sequence prepares FATES for its first call to `ed_ecosystem_dynamics()`. After initialization, control passes to the daily dynamics loop described in [Core Ecosystem Dynamics](../core-dynamics/index.md).
