---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

# FATES Model Overview

## Purpose and Scope

This document provides an architectural overview of the Functionally Assembled Terrestrial Ecosystem Simulator (FATES). It covers the core design principles, hierarchical data structures, execution flow, and major subsystems. It is intended for developers who need to understand how the components fit together before reading module-level source.

For more detail on individual subsystems see:

- [Host Model Interface](../getting-started/host_interface.md)
- [Initialization Modes](../getting-started/initialization.md)
- [Daily Dynamics Loop](../core-dynamics/daily_loop.md)
- [Data Structures: Sites, Patches, and Cohorts](../core-dynamics/data_structures.md)
- [Plant Growth and Physiology](../plant-physiology/index.md)
- [Canopy Structure and Competition](../canopy-structure/index.md)

## What is FATES?

FATES is a cohort-based vegetation demographic model that simulates ecosystem dynamics through coupled plant growth, mortality, recruitment, and disturbance. Vegetation is represented as a hierarchy of sites containing age-structured patches, each containing size-structured cohorts. FATES is designed as a module that couples to host land models (HLMs) such as E3SM Land Model (ELM) or Community Land Model (CLM) through a single boundary-condition interface `(main/FatesInterfaceMod.F90:125)`.

## Core Design Principles

### 1. Hierarchical Vegetation Structure

FATES organizes vegetation using a three-level hierarchy implemented through linked lists `(main/FatesInterfaceMod.F90:125)`:

```
fates_interface_type
  └── sites(:)                        (ed_site_type)
       ├── youngest_patch  ─ older ─► oldest_patch    (doubly-linked list, age order)
       │   └── tallest     ─ shorter ─► shortest      (doubly-linked list, height order)
       │        └── prt (PARTEH allocation object with biomass pools)
       ├── bc_in  (input boundary conditions from HLM)
       └── bc_out (output boundary conditions to HLM)
```

### 2. Cohort Representation

Cohorts aggregate individual plants with similar characteristics (PFT, size, age, canopy layer, damage class) to reduce computational cost while keeping demographic detail. A cohort is created in `create_cohort()` `(biogeochem/EDCohortDynamicsMod.F90:160)`. Each cohort tracks:

- `n` — number density (plants per patch)
- `dbh` — diameter at breast height (cm)
- `height` — height (m)
- `pft` — plant functional type
- `canopy_layer` — canopy layer index
- `prt` — biomass pools managed by PARTEH (leaf, fineroot, sapwood, structure, storage, reproduction)

### 3. Perfect Plasticity Approximation (PPA)

Cohorts are organized into discrete canopy layers. Upper canopy cohorts receive full light, understory cohorts receive reduced light. Layer assignment is based on cohort height and crown area. See [Canopy Layering and PPA](../canopy-structure/ppa.md).

### 4. Extensible Allocation Framework (PARTEH)

Plant carbon and nutrient allocation is handled through PARTEH (Plant Allocation and Reactive Transport Extensible Hypotheses), a polymorphic framework. Two hypotheses are currently available, selected via `hlm_parteh_mode`:

- `prt_carbon_allom_hyp` — carbon-only allometric allocation `(main/FatesInterfaceMod.F90:87)`
- `prt_cnp_flex_allom_hyp` — flexible CNP allocation with dynamic stoichiometry `(main/FatesInterfaceMod.F90:88)`

The PARTEH object is attached to each cohort as `currentCohort%prt` and allocated in `create_cohort()` `(biogeochem/EDCohortDynamicsMod.F90:160)`.

## Execution Flow: Daily Timestep

FATES is called once per day by the host land model. The daily sequence is orchestrated by `ed_ecosystem_dynamics()` `(main/EDMainMod.F90:141)`.

Major steps inside `ed_ecosystem_dynamics`:

```
  TotalBalanceCheck(0)                                   EDMainMod.F90:196
  phenology() / satellite_phenology()                    EDMainMod.F90:203, 205
  fire_model()                                           EDMainMod.F90:218
  disturbance_rates()                                    EDMainMod.F90:223
  ed_integrate_state_variables()                         EDMainMod.F90:226
  recruitment() (per patch)                              EDMainMod.F90:248
  TotalBalanceCheck(1)                                   EDMainMod.F90:255
  sort_cohorts / terminate_cohorts / fuse_cohorts        EDMainMod.F90:261-270
  TotalBalanceCheck(2)                                   EDMainMod.F90:277
  spawn_patches()                                        EDMainMod.F90:292
  TotalBalanceCheck(3)                                   EDMainMod.F90:294
  fuse_patches()                                         EDMainMod.F90:297
  TotalBalanceCheck(4)                                   EDMainMod.F90:309
  terminate_patches()                                    EDMainMod.F90:312
  TotalBalanceCheck(5)                                   EDMainMod.F90:315
```

### Detailed Integration Sequence

Inside `ed_integrate_state_variables()` `(main/EDMainMod.F90:320)`, the following operations occur once per cohort. Note that `LoggingMortality_frac()` is not invoked directly here; it is called from inside `Mortality_Derivative()` `(biogeochem/EDMortalityFunctionsMod.F90:284)` and also from `disturbance_rates()` (patch-level) in `EDPatchDynamicsMod`.

| Step | Operation | Source | Purpose |
|------|-----------|--------|---------|
| 1 | `Mortality_Derivative()` | `biogeochem/EDMortalityFunctionsMod.F90:234` (call at `main/EDMainMod.F90:473`) | Compute background, hydraulic, C-starvation, freezing, senescence and damage mortality; internally also computes logging mortality via `LoggingMortality_frac()` |
| 2 | `PRTMaintTurnover()` | `main/EDMainMod.F90:535` | Maintenance turnover of tissues |
| 3 | `prt%AgeLeaves()` | `main/EDMainMod.F90:543` | Move leaf mass through age classes |
| 4 | `prt%DailyPRT(phase=1)` | `main/EDMainMod.F90:582` | Phase-1 allocation (non-stature, priority pools) |
| 5 | `prt%DailyPRT(phase=2)` | `main/EDMainMod.F90:585` | Phase-2 allocation (non-stature, iterative) |
| 6 | `DamageRecovery()` (if tree damage on) | `main/EDMainMod.F90:595` | Recover damaged cohorts |
| 7 | `prt%DailyPRT(phase=3)` | `main/EDMainMod.F90:601` | Phase-3 allocation (stature growth) |
| 8 | `EffluxIntoLitterPools()` | `main/EDMainMod.F90:608` | Efflux of excess/turnover mass to litter |
| 9 | `h_allom()` | `main/EDMainMod.F90:647` | Update plant height from new DBH |

Hydraulic property updates (`UpdateSizeDepPlantHydProps`) occur per cohort later in the same routine when `hlm_use_planthydro` is active. Cohort sort / fuse / terminate run in the enclosing `ed_ecosystem_dynamics()` after integration.

## Data Structure Details

### Site-Patch-Cohort Hierarchy

Key implementation details:

- Patches form a doubly-linked list ordered by age (youngest to oldest). `ed_site_type` holds `youngest_patch` and `oldest_patch` pointers; each patch has `younger` / `older` pointers.
- Cohorts form a doubly-linked list ordered by height (tallest to shortest). `fates_patch_type` holds `tallest` and `shortest` pointers; each cohort has `taller` / `shorter` pointers.
- PARTEH objects (`prt`) store all biomass pools (leaf, fineroot, sapwood, structural, storage, reproduction) and handle allocation.

Sources: `biogeochem/EDCohortDynamicsMod.F90:160` (`create_cohort`), `biogeochem/EDCohortDynamicsMod.F90:347` (`terminate_cohorts`), `biogeochem/EDCohortDynamicsMod.F90:694` (`fuse_cohorts`), `biogeochem/EDCohortDynamicsMod.F90:1271` (`sort_cohorts`).

## Key Process Modules

Subroutine line numbers below point to the subroutine *body* (the `subroutine <name>(...)` line), not to public declaration lists.

### 1. Phenology and Recruitment — `biogeochem/EDPhysiologyMod.F90`

- `trim_canopy()` — optimizes leaf area based on carbon balance `(biogeochem/EDPhysiologyMod.F90:597)`
- `phenology()` — controls leaf flushing and abscission for deciduous PFTs `(biogeochem/EDPhysiologyMod.F90:909)`
- `recruitment()` — creates new seedlings from germinated seeds `(biogeochem/EDPhysiologyMod.F90:2440)`

### 2. Mortality — `biogeochem/EDMortalityFunctionsMod.F90`

`Mortality_Derivative()` `(biogeochem/EDMortalityFunctionsMod.F90:234)` combines multiple mortality mechanisms into per-cohort rates:

- `bmort` — background mortality
- `cmort` — carbon starvation mortality
- `hmort` — hydraulic failure mortality
- `frmort` — freezing mortality
- `smort` — size-dependent senescence
- `asmort` — age-dependent senescence
- `dgmort` — damage-dependent mortality
- Logging mortality via internal call to `LoggingMortality_frac()` at `EDMortalityFunctionsMod.F90:284`

### 3. Allometry — `biogeochem/FatesAllometryMod.F90`

All allometry routines are dispatched based on per-PFT mode switches (`fates_allom_hmode`, `fates_allom_lmode`, `fates_allom_smode`, `fates_allom_amode`). Subroutine-body line numbers:

- `h_allom()` — DBH to height `(biogeochem/FatesAllometryMod.F90:333)`
- `bagw_allom()` — aboveground woody biomass `(biogeochem/FatesAllometryMod.F90:372)`
- `blmax_allom()` — maximum (target) leaf biomass `(biogeochem/FatesAllometryMod.F90:440)`
- `carea_allom()` — crown area `(biogeochem/FatesAllometryMod.F90:476)`
- `bleaf()` — current leaf biomass (accounts for crown damage and canopy trim) `(biogeochem/FatesAllometryMod.F90:554)`
- `bsap_allom()` — sapwood biomass / sapwood area `(biogeochem/FatesAllometryMod.F90:922)`
- `bbgw_allom()` — coarse (belowground) woody biomass `(biogeochem/FatesAllometryMod.F90:1025)`

### 4. Cohort Dynamics — `biogeochem/EDCohortDynamicsMod.F90`

- `create_cohort()` — initialize a new cohort and its PARTEH object `(biogeochem/EDCohortDynamicsMod.F90:160)`
- `terminate_cohorts()` — remove cohorts below thresholds `(biogeochem/EDCohortDynamicsMod.F90:347)`
- `fuse_cohorts()` — merge similar cohorts to bound per-patch cohort count `(biogeochem/EDCohortDynamicsMod.F90:694)`
- `sort_cohorts()` — maintain the height-ordered list `(biogeochem/EDCohortDynamicsMod.F90:1271)`

### 5. Logging and Harvest — `biogeochem/EDLoggingMortalityMod.F90`

- `LoggingMortality_frac()` — computes direct-logging, collateral and infrastructure mortality fractions `(biogeochem/EDLoggingMortalityMod.F90:198)`
- `get_harvest_rate_area()` — area-based harvest rates `(biogeochem/EDLoggingMortalityMod.F90:351)`
- `get_harvest_rate_carbon()` — carbon-based harvest rates `(biogeochem/EDLoggingMortalityMod.F90:540)`

## Boundary Conditions: Host Model Interface

FATES exchanges information with the host land model through boundary-condition structures declared in `main/FatesInterfaceTypesMod.F90`.

### Inputs from HLM (`bc_in_type`)

| Category | Key Variables | Purpose |
|----------|---------------|---------|
| Radiation | `solad_parb`, `solai_parb` | Direct/diffuse PAR and NIR |
| Hydrology | `smp_sl`, `h2o_liqvol_sl`, `watsat_sl` | Soil moisture state |
| Temperature | `tempk_sl`, `t_veg_pa` | Soil and vegetation temperature drivers |
| Fire weather | `lightning24`, `pop_density` | Ignition sources |
| BGC | `plant_nh4_uptake_flux`, `plant_no3_uptake_flux`, `plant_p_uptake_flux` | Nutrient uptake in CNP coupled mode |
| Land use | `hlm_harvest_rates`, `hlm_harvest_catnames` | Harvest prescriptions |

Sources: `main/FatesInterfaceTypesMod.F90:348-562`.

### Outputs to HLM (`bc_out_type`)

| Category | Key Variables | Purpose |
|----------|---------------|---------|
| Radiation | `albd_parb`, `albi_parb`, `fsun_pa` | Albedo, sunlit fraction |
| Hydrology | `rootr_pasl`, `btran_pa` | Root uptake profile, transpiration stress |
| Structure | `elai_pa`, `esai_pa`, `htop_pa` | Exposed LAI/SAI, canopy height |
| Litter fluxes | `litt_flux_cel_c_si`, `litt_flux_lig_c_si`, `litt_flux_lab_c_si` | Litter fragmentation to soil BGC |
| Nutrient fluxes | `veg_rootc`, `cn_scalar`, `cp_scalar` | Competitor state for soil BGC |

Sources: `main/FatesInterfaceTypesMod.F90:565-751`.

### Parameter Constants (`bc_pconst_type`)

Parameters set once during initialization and held constant throughout the simulation, mostly ECA uptake kinetics. Allocated in `allocate_bcpconst()` `(main/FatesInterfaceMod.F90:225)`:

```
vmax_nh4, vmax_no3, vmax_p          ! uptake rate constants per PFT
eca_km_nh4, eca_km_no3, eca_km_p    ! half-saturation constants
eca_km_ptase, eca_vmax_ptase
eca_alpha_ptase, eca_lambda_ptase
j_uptake                             ! per soil decomp layer
```

## Mass Balance and Diagnostics

FATES performs rigorous mass-balance checking at six checkpoints during the daily timestep. `TotalBalanceCheck(currentSite, N)` is called at:

- N=0: initial state before dynamics `(main/EDMainMod.F90:196)`
- N=1: after recruitment `(main/EDMainMod.F90:255)`
- N=2: after cohort dynamics `(main/EDMainMod.F90:277)`
- N=3: after patch spawning `(main/EDMainMod.F90:294)`
- N=4: after patch fusion `(main/EDMainMod.F90:309)`
- N=5: final check `(main/EDMainMod.F90:315)`

`SiteMassStock()` calculates total carbon (or nutrient) across all live vegetation, litter, and seed pools to verify conservation.

## Parameter System

FATES loads parameters from a NetCDF file (`fates_params.nc`), generated from a canonical CDL definition at `parameter_files/fates_params_default.cdl`. Parameters include:

- PFT-specific traits (wood density, leaf lifespan, allometric coefficients, stoichiometry)
- Global scalars (mortality disturbance fraction, canopy exclusion weight, phenology thresholds, fusion tolerances)
- Mode switches (`fates_allom_hmode`, `fates_allom_lmode`, `fates_maintresp_leaf_model`, `fates_rad_model`, etc.)

Parameter loading is two-phase, driven by `FatesReadParameters()` `(main/FatesInterfaceMod.F90:2399)`:

1. Register phase — each module declares parameters via `FatesRegisterParams`, `SpitFireRegisterParams`, `PRTRegisterParams`, `FatesSynchronizedParamsInst%RegisterParams` `(main/FatesInterfaceMod.F90:2413-2416)`
2. Read phase — `param_reader%Read(fates_params)` `(main/FatesInterfaceMod.F90:2418)`
3. Receive phase — `FatesReceiveParams`, `SpitFireReceiveParams`, `PRTReceiveParams`, `FatesSynchronizedParamsInst%ReceiveParams` `(main/FatesInterfaceMod.F90:2420-2423)`

See [Parameter System](../getting-started/parameter_system.md) for details.

## Operational Modes

FATES supports several operational modes set by the HLM during initialization. All flags are declared in `main/FatesInterfaceTypesMod.F90`.

| Mode | Flag | Source | Description |
|------|------|--------|-------------|
| Standard | (default) | — | Full demographic dynamics |
| Satellite Phenology | `hlm_use_sp` | `main/FatesInterfaceTypesMod.F90:194` | Prescribed LAI from surface dataset |
| No Competition | `hlm_use_nocomp` | `main/FatesInterfaceTypesMod.F90:191` | One patch per PFT, no inter-PFT competition (does not fix area) |
| Fixed Biogeography | `hlm_use_fixed_biogeog` | `main/FatesInterfaceTypesMod.F90:188` | PFT area fractions from surface dataset |
| Static Stand Structure | `hlm_use_ed_st3` | `main/FatesInterfaceTypesMod.F90:155` | No growth, recruitment, or mortality — experimental |

## Summary

FATES implements ecosystem demography through a clean separation of site/patch/cohort data structures, a two-phase parameter system, and a daily execution pipeline that integrates mortality, allocation, disturbance and recruitment. The modular design (PARTEH, SPITFIRE, plant hydraulics, tree damage, logging) allows components to be swapped while the site-patch-cohort backbone is maintained. For subsystem details, follow the links at the top of this document.
