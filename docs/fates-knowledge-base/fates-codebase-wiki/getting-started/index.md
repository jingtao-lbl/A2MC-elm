---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

# Getting Started

## Purpose and Scope

This page describes how FATES initializes and prepares for simulation. It covers the fundamental concepts needed to understand FATES startup: the host land model interface, parameter loading, and initialization modes.

For detailed information on specific topics, see:

- [Host Model Interface](host_interface.md) — coupling and boundary conditions
- [Initialization Modes](initialization.md) — cold start, inventory, and restart
- [Parameter System](parameter_system.md) — parameter file structure and PFT parameters
- [Parameter Management Tools](parameter_tools.md) — Python tools for parameter manipulation

The core execution loop and daily dynamics are covered in [Core Ecosystem Dynamics](../core-dynamics/index.md).

## Initialization Sequence Overview

FATES initialization occurs through a fixed sequence of calls from the host land model (HLM). The process can be divided into three major phases: Setup, Parameter Loading, and State Initialization.

### Initialization Call Sequence

```
HLM calls:
  FatesInterfaceInit        (main/FatesInterfaceMod.F90:188)   FATES globals + logging
  SetFatesGlobalElements1   (main/FatesInterfaceMod.F90:737)   FatesReadParameters, numpft, maxpatch
  SetFatesGlobalElements2   (main/FatesInterfaceMod.F90:808)   nleafage, element sizing, n/p uptake modes
  allocate_bcpconst         (main/FatesInterfaceMod.F90:225)   one-shot parameter constants
  allocate_bcin             (main/FatesInterfaceMod.F90:412)   per-site input boundary conditions
  allocate_bcout            (main/FatesInterfaceMod.F90:569)   per-site output boundary conditions
  init_site_vars            (main/EDInitMod.F90:117)           allocate per-site arrays
  zero_site                 (main/EDInitMod.F90:222)           initialize to defaults
  set_site_properties       (main/EDInitMod.F90:354)           initial phenology, fire, biogeography
  init_patches              (main/EDInitMod.F90:534)           NBG, inventory, or restart path
```

## The FATES Interface Structure

The primary connection between FATES and the host land model is the `fates_interface_type` object `(main/FatesInterfaceMod.F90:125)`. It is the root of FATES data structures and manages boundary-condition exchange.

### Core Interface Components

| Component | Purpose | Allocation |
|-----------|---------|------------|
| `sites(:)` | Pointer array to FATES site structures containing patches and cohorts | Per site |
| `bc_in(:)` | Input boundary conditions from HLM (meteorology, soil state, etc.) | Per site |
| `bc_out(:)` | Output boundary conditions to HLM (fluxes, canopy properties, etc.) | Per site |
| `bc_pconst` | Parameter constants (nutrient uptake kinetics) | Once per interface |

Sources: `main/FatesInterfaceMod.F90:131-156`.

### Boundary Condition Allocation

The HLM allocates boundary-condition arrays via three routines before FATES site initialization:

| Subroutine | Source | Key Arrays Allocated |
|------------|--------|----------------------|
| `allocate_bcin()` | `main/FatesInterfaceMod.F90:412` | `lightning24`, `solad_parb`, `solai_parb`, `smp_sl`, `tempk_sl`, `h2o_liqvol_sl` |
| `allocate_bcout()` | `main/FatesInterfaceMod.F90:569` | `fsun_pa`, `laisun_pa`, `btran_pa`, `rootr_pasl`, `albd_parb`, `elai_pa` |
| `allocate_bcpconst()` | `main/FatesInterfaceMod.F90:225` | `vmax_nh4`, `vmax_no3`, `vmax_p`, `eca_km_nh4`, `eca_km_no3`, `eca_km_p`, `eca_km_ptase`, `eca_vmax_ptase`, `eca_alpha_ptase`, `eca_lambda_ptase`, `j_uptake` |

## Two-Phase Parameter Loading

FATES uses a two-phase system to load parameters from NetCDF files. This design lets the host model provide a parameter reader while FATES declares what it needs. The flow is implemented in `FatesReadParameters()` `(main/FatesInterfaceMod.F90:2399)`:

```
phase 1: Register      FatesRegisterParams            EDParamsMod
                       SpitFireRegisterParams         SFParamsMod
                       PRTRegisterParams              PRTInitParamsFATESMod
                       FatesSynchronizedParamsInst%RegisterParams

phase 2: Read          param_reader%Read(fates_params)   (HLM-supplied reader)

phase 3: Receive       FatesReceiveParams             EDParamsMod
                       SpitFireReceiveParams          SFParamsMod
                       PRTReceiveParams               PRTInitParamsFATESMod
                       FatesSynchronizedParamsInst%ReceiveParams
```

Call sites at `main/FatesInterfaceMod.F90:2413-2423`.

## Initialization Modes

FATES supports three distinct initialization modes, each appropriate for different simulation scenarios. The mode is selected by the `hlm_is_restart` and `hlm_use_inventory_init` flags, both declared in `main/FatesInterfaceTypesMod.F90` (lines 37, 175).

### Initialization Mode Decision Tree

```
hlm_is_restart == itrue              → Restart mode    (FatesRestartInterfaceMod)
hlm_use_inventory_init == itrue      → Inventory mode  (FatesInventoryInitMod)
otherwise                            → Near-Bare-Ground (EDInitMod::init_patches)
```

Entry at `main/EDInitMod.F90:534` (`init_patches`).

### Initialization Mode Comparison

| Mode | When Used | State Source | Key Modules |
|------|-----------|--------------|-------------|
| Restart | Continuing previous simulation | Restart file (NetCDF) | `main/FatesRestartInterfaceMod.F90` |
| Inventory | Initializing from field data | PSS/CSS inventory files | `main/FatesInventoryInitMod.F90` |
| Near-Bare-Ground | Cold start with minimal vegetation | Parameter defaults | `main/EDInitMod.F90:534` (`init_patches`) |

See [Initialization Modes](initialization.md) for details.

## Site Structure Initialization

After parameter loading, FATES initializes site-level data structures. Each site represents a geographic location and holds patches in an age-ordered linked list.

### Site Array Allocations

Arrays allocated during `init_site_vars()` `(main/EDInitMod.F90:117-219)`:

| Array | Dimensions | Purpose |
|-------|------------|---------|
| `term_nindivs_canopy` | `nlevsclass × numpft` | Terminated canopy individuals by size/PFT |
| `term_nindivs_ustory` | `nlevsclass × numpft` | Terminated understory individuals |
| `fmort_rate_canopy` | `nlevsclass × numpft` | Fire mortality rates (canopy) |
| `fmort_rate_ustory` | `nlevsclass × numpft` | Fire mortality rates (understory) |
| `imort_rate` | `nlevsclass × numpft` | Impact mortality rates |
| `growthflux_fusion` | `nlevsclass × numpft` | Cohort growth fusion flux |
| `mass_balance(:)` | `num_elements` | Track carbon/nutrient conservation |
| `flux_diags(:)` | `num_elements` | Element flux diagnostics |
| `area_pft` | `1:numpft` (or `0:numpft` for nocomp+fixed-biogeog) | PFT area fractions |
| `rec_l2fr` | `numpft × nclmax` | Mean L2FR of recruits for CNP dynamics |
| `sp_tlai`, `sp_tsai`, `sp_htop` | `numpft` | Satellite phenology inputs |
| `seed_in` | `1:numpft` | Incoming seed flux pool |
| `seed_out` | `1:numpft` | Outgoing seed flux pool (dispersal) |

**Note.** The drought-phenology water-memory field `liqvol_memory(numWaterMem, maxpft)` is a *fixed-size* member of `ed_site_type`, declared at `main/EDTypesMod.F90:316`, not an allocatable. Restart and history I/O expose differently named identifiers (e.g. `ir_liqvolmem_siwmft` in `FatesRestartInterfaceMod`, `ih_seed_bank_si` in `FatesHistoryInterfaceMod`); those are I/O labels, not site-struct field names.

## PFT Parameter Structure

Plant Functional Type (PFT) parameters control vegetation physiology, allometry, and life history traits. They are loaded during initialization and accessed through the `EDPftvarcon_inst` singleton `(main/EDPftvarcon.F90:45-289)`. The `Register` and `Receive` entry points are at `main/EDPftvarcon.F90:315` and `main/EDPftvarcon.F90:332`, dispatching to subgroup routines for plain PFT, numrad-dimensioned, hydr_organs-dimensioned, and leafage-dimensioned parameters.

### Key PFT Parameter Categories

| Category | Example Parameters | Notes |
|----------|--------------------|-------|
| Allometry | `fates_allom_d2h1`, `fates_allom_d2h2`, `fates_allom_d2bl1`, `fates_allom_l2fr` | Mode flags: `fates_allom_hmode`, `fates_allom_lmode`, `fates_allom_smode`, `fates_allom_amode` |
| Photosynthesis | `fates_leaf_vcmax25top`, `fates_leaf_slatop`, `fates_leaf_stomatal_slope_ballberry`, `fates_leaf_stomatal_slope_medlyn`, `fates_leaf_stomatal_intercept`, `fates_leaf_c3psn` | |
| Mortality | `fates_mort_bmort`, `fates_mort_scalar_cstarvation`, `fates_mort_scalar_hydrfailure`, `fates_mort_freezetol`, `fates_mort_scalar_coldstress` | |
| Hydraulics | `fates_hydro_p50_node`, `fates_hydro_avuln_node`, `fates_hydro_kmax_node`, `fates_hydro_p50_gs`, `fates_hydro_avuln_gs` | Only active when `hlm_use_planthydro==itrue` |
| Phenology | `fates_phen_evergreen`, `fates_phen_stress_decid`, `fates_phen_flush_fraction` | |
| Fire | `fates_fire_alpha_SH`, `fates_fire_bark_scaler`, `fates_fire_crown_kill` | |

Source declarations: `parameter_files/fates_params_default.cdl:32-500`, `main/EDPftvarcon.F90:45-275`.

## Global Configuration Flags

FATES behavior is controlled by global flags set by the host model during initialization. These flags live in `main/FatesInterfaceTypesMod.F90` and remain constant throughout the simulation.

### Critical Global Flags

| Flag | Type | Purpose | Source |
|------|------|---------|--------|
| `hlm_use_planthydro` | integer | Enable plant hydraulics | `main/FatesInterfaceTypesMod.F90:143` |
| `hlm_parteh_mode` | integer | PARTEH allocation hypothesis (1=C-only, 2=CNP) | `main/FatesInterfaceTypesMod.F90:94` |
| `hlm_use_sp` | integer | Satellite phenology mode | `main/FatesInterfaceTypesMod.F90:194` |
| `hlm_use_nocomp` | integer | No-competition mode | `main/FatesInterfaceTypesMod.F90:191` |
| `hlm_use_fixed_biogeog` | integer | Fixed biogeography | `main/FatesInterfaceTypesMod.F90:188` |
| `hlm_use_lu_harvest` | integer | Use HLM land-use harvest data | `main/FatesInterfaceTypesMod.F90:114` |
| `hlm_use_inventory_init` | integer | Initialize from inventory files | `main/FatesInterfaceTypesMod.F90:175` |
| `hlm_is_restart` | integer | Restart vs. cold start | `main/FatesInterfaceTypesMod.F90:37` |
| `hlm_use_tree_damage` | integer | Enable tree damage module | `main/FatesInterfaceTypesMod.F90:152` |
| `hlm_use_ed_st3` | integer | Static stand structure (ST3) | `main/FatesInterfaceTypesMod.F90:155` |
| `hlm_spitfire_mode` | integer | Fire model configuration | `main/FatesInterfaceTypesMod.F90:110` |

All integer flags use `0=off / 1=on` semantics via `ifalse`/`itrue` constants, except `hlm_spitfire_mode` which selects a fire configuration.

## Summary: From Initialization to First Timestep

The complete sequence prepares FATES for its first call to `ed_ecosystem_dynamics()`. After initialization, control passes to the daily dynamics loop described in [Core Ecosystem Dynamics](../core-dynamics/index.md).
