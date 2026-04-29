---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
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

FATES is a cohort-based vegetation demographic model that simulates ecosystem dynamics through coupled plant growth, mortality, recruitment, and disturbance. Vegetation is represented as a hierarchy of sites containing age-structured patches, each containing size-structured cohorts. FATES is designed as a module that couples to host land models (HLMs) such as E3SM Land Model (ELM) or Community Land Model (CLM) through a single boundary-condition interface `(main/FatesInterfaceMod.F90:138)`.

## Core Design Principles

### 1. Hierarchical Vegetation Structure

FATES organizes vegetation using a three-level hierarchy implemented through linked lists `(main/FatesInterfaceMod.F90:138-172)`:

```
fates_interface_type
  └── sites(:)                        (ed_site_type)
       ├── youngest_patch  ─ older ─► oldest_patch    (doubly-linked list, age order)
       │   └── tallest     ─ shorter ─► shortest      (doubly-linked list, height order)
       │        └── prt (PARTEH allocation object with biomass pools)
       ├── bc_in  (input boundary conditions from HLM)
       └── bc_out (output boundary conditions to HLM)
```

Patches and cohorts now have dedicated home modules `biogeochem/FatesPatchMod.F90` (`fates_patch_type`) and `biogeochem/FatesCohortMod.F90` (`fates_cohort_type`); demography routines such as `create_cohort`, `terminate_cohorts`, and `fuse_cohorts` live in `biogeochem/EDCohortDynamicsMod.F90`, while patch-level routines such as `SortCohorts` are now type-bound methods on `fates_patch_type` (`biogeochem/FatesPatchMod.F90:264, :1172`).

### 2. Cohort Representation

Cohorts aggregate individual plants with similar characteristics (PFT, size, age, canopy layer, damage class) to reduce computational cost while keeping demographic detail. A cohort is created in `create_cohort()` `(biogeochem/EDCohortDynamicsMod.F90:123)`. Each cohort tracks:

- `n` — number density (plants per patch)
- `dbh` — diameter at breast height (cm)
- `height` — height (m)
- `pft` — plant functional type
- `canopy_layer` — canopy layer index
- `prt` — biomass pools managed by PARTEH (leaf, fineroot, sapwood, structure, storage, reproduction)

### 3. Perfect Plasticity Approximation (PPA)

Cohorts are organized into discrete canopy layers. Upper canopy cohorts receive full light, understory cohorts receive reduced light. Layer assignment is based on cohort height and crown area. The maximum number of canopy layers is `nclmax = 3` `(main/EDParamsMod.F90:76)`. See [Canopy Layering and PPA](../canopy-structure/ppa.md).

### 4. Extensible Allocation Framework (PARTEH)

Plant carbon and nutrient allocation is handled through PARTEH (Plant Allocation and Reactive Transport Extensible Hypotheses), a polymorphic framework. Two hypotheses are currently available, selected via `hlm_parteh_mode` (declared at `main/FatesInterfaceTypesMod.F90:85`):

- `prt_carbon_allom_hyp` — carbon-only allometric allocation
- `prt_cnp_flex_allom_hyp` — flexible CNP allocation with dynamic stoichiometry

Constants are defined in `parteh/PRTGenericMod.F90`. The PARTEH object is attached to each cohort as `currentCohort%prt` and allocated in `create_cohort()` `(biogeochem/EDCohortDynamicsMod.F90:123)`.

## Execution Flow: Daily Timestep

FATES is called once per day by the host land model. The daily sequence is orchestrated by `ed_ecosystem_dynamics()` `(main/EDMainMod.F90:148)`.

Major steps inside `ed_ecosystem_dynamics`:

```
  TotalBalanceCheck(0)                                   EDMainMod.F90:201
  phenology() / satellite_phenology()                    EDMainMod.F90:208, 210
  DailyFireModel()                                       EDMainMod.F90:224
  disturbance_rates()                                    EDMainMod.F90:229
  ed_integrate_state_variables()                         EDMainMod.F90:232
  recruitment() (per patch)                              EDMainMod.F90:259
  TotalBalanceCheck(1)                                   EDMainMod.F90:266
  SortCohorts / terminate_cohorts / fuse_cohorts         EDMainMod.F90:272-281
  TotalBalanceCheck(2)                                   EDMainMod.F90:289
  spawn_patches()                                        EDMainMod.F90:305
  TotalBalanceCheck(3)                                   EDMainMod.F90:307
  fuse_patches()                                         EDMainMod.F90:310
  TotalBalanceCheck(4)                                   EDMainMod.F90:322
  terminate_patches()                                    EDMainMod.F90:325
  TotalBalanceCheck(5)                                   EDMainMod.F90:329
```

A separate routine `ed_update_site()` `(main/EDMainMod.F90:813)` issues two additional balance checks at `:855` (`TotalBalanceCheck(6)`) and `:861` (`TotalBalanceCheck(final_check_id)`). These supplement the six numbered checkpoints above and are invoked during cold-start, restart, and every dynamics call.

### Detailed Integration Sequence

Inside `ed_integrate_state_variables()` `(main/EDMainMod.F90:335)`, the following operations occur once per cohort. Note that `LoggingMortality_frac()` is not invoked directly here; it is called from inside `Mortality_Derivative()` and also from `disturbance_rates()` (patch-level) in `EDPatchDynamicsMod`.

| Step | Operation | Source | Purpose |
|------|-----------|--------|---------|
| 1 | `Mortality_Derivative()` | call at `main/EDMainMod.F90:488`; body at `biogeochem/EDMortalityFunctionsMod.F90:289` | Compute background, hydraulic, C-starvation, freezing, senescence and damage mortality; internally also computes logging mortality via `LoggingMortality_frac()` |
| 2 | `PRTMaintTurnover()` | `main/EDMainMod.F90:568` | Maintenance turnover of tissues |
| 3 | `prt%AgeLeaves()` | `main/EDMainMod.F90:576` | Move leaf mass through age classes |
| 4 | `prt%DailyPRT(phase=1)` | `main/EDMainMod.F90:615` | Phase-1 allocation (non-stature, priority pools) |
| 5 | `prt%DailyPRT(phase=2)` | `main/EDMainMod.F90:618` | Phase-2 allocation (non-stature, iterative) |
| 6 | `DamageRecovery()` (if tree damage on) | `main/EDMainMod.F90:628` | Recover damaged cohorts |
| 7 | `prt%DailyPRT(phase=3)` | `main/EDMainMod.F90:634` | Phase-3 allocation (stature growth) |
| 8 | `EffluxIntoLitterPools()` | `main/EDMainMod.F90:651` | Efflux of excess/turnover mass to litter |
| 9 | `h_allom()` | `main/EDMainMod.F90:692` | Update plant height from new DBH |

Hydraulic property updates (`UpdateSizeDepPlantHydProps`) occur per cohort later in the same routine (call at `main/EDMainMod.F90:708`) when `hlm_use_planthydro` is active. Cohort sort / fuse / terminate run in the enclosing `ed_ecosystem_dynamics()` after integration.

## Data Structure Details

### Site-Patch-Cohort Hierarchy

Key implementation details:

- Patches form a doubly-linked list ordered by age (youngest to oldest). `ed_site_type` (`main/EDTypesMod.F90`) holds `youngest_patch` and `oldest_patch` pointers; each patch has `younger` / `older` pointers.
- Cohorts form a doubly-linked list ordered by height (tallest to shortest). `fates_patch_type` (`biogeochem/FatesPatchMod.F90`) holds `tallest` and `shortest` pointers; each cohort has `taller` / `shorter` pointers.
- PARTEH objects (`prt`) store all biomass pools (leaf, fineroot, sapwood, structural, storage, reproduction) and handle allocation.

Sources: `biogeochem/EDCohortDynamicsMod.F90:123` (`create_cohort`), `:283` (`terminate_cohorts`), `:648` (`fuse_cohorts`); `biogeochem/FatesPatchMod.F90:1172` (`SortCohorts` type-bound method).

## Key Process Modules

Subroutine line numbers below point to the subroutine *body* (the `subroutine <name>(...)` line), not to public declaration lists.

### 1. Phenology and Recruitment — `biogeochem/EDPhysiologyMod.F90`

- `trim_canopy()` — optimizes leaf area based on carbon balance `(biogeochem/EDPhysiologyMod.F90:598)`
- `phenology()` — controls leaf flushing and abscission for deciduous PFTs `(biogeochem/EDPhysiologyMod.F90:900)`
- `phenology_leafonoff()` — drives leaf-on/leaf-off state transitions `(biogeochem/EDPhysiologyMod.F90:1534)`
- `recruitment()` — creates new seedlings from germinated seeds `(biogeochem/EDPhysiologyMod.F90:2467)`

### 2. Mortality — `biogeochem/EDMortalityFunctionsMod.F90`

`Mortality_Derivative()` `(biogeochem/EDMortalityFunctionsMod.F90:289)` combines multiple mortality mechanisms into per-cohort rates:

- `bmort` — background mortality
- `cmort` — carbon starvation mortality (linear or exponential, controlled by `hlm_mort_cstarvation_model` at `main/FatesInterfaceTypesMod.F90:165`)
- `hmort` — hydraulic failure mortality
- `frmort` — freezing mortality
- `smort` — size-dependent senescence
- `asmort` — age-dependent senescence
- `dgmort` — damage-dependent mortality
- Logging mortality via internal call to `LoggingMortality_frac()` at `biogeochem/EDLoggingMortalityMod.F90:208`

### 3. Allometry — `biogeochem/FatesAllometryMod.F90`

All allometry routines are dispatched based on per-PFT mode switches (`fates_allom_hmode`, `fates_allom_lmode`, `fates_allom_smode`, `fates_allom_amode`). Subroutine-body line numbers:

- `h_allom()` — DBH to height `(biogeochem/FatesAllometryMod.F90:336)`
- `bagw_allom()` — aboveground woody biomass `(biogeochem/FatesAllometryMod.F90:375)`
- `blmax_allom()` — maximum (target) leaf biomass `(biogeochem/FatesAllometryMod.F90:449)`
- `carea_allom()` — crown area `(biogeochem/FatesAllometryMod.F90:495)`
- `bleaf()` — current leaf biomass (accounts for crown damage and canopy trim) `(biogeochem/FatesAllometryMod.F90:580)`
- `bsap_allom()` — sapwood biomass / sapwood area `(biogeochem/FatesAllometryMod.F90:990)`
- `bbgw_allom()` — coarse (belowground) woody biomass `(biogeochem/FatesAllometryMod.F90:1114)`

### 4. Cohort Dynamics — `biogeochem/EDCohortDynamicsMod.F90`

- `create_cohort()` — initialize a new cohort and its PARTEH object `(biogeochem/EDCohortDynamicsMod.F90:123)`
- `terminate_cohorts()` — remove cohorts below thresholds `(biogeochem/EDCohortDynamicsMod.F90:283)`
- `fuse_cohorts()` — merge similar cohorts to bound per-patch cohort count `(biogeochem/EDCohortDynamicsMod.F90:648)`
- `SortCohorts` type-bound method on `fates_patch_type` — maintain the height-ordered list `(biogeochem/FatesPatchMod.F90:1172)`

### 5. Logging and Harvest — `biogeochem/EDLoggingMortalityMod.F90`

- `LoggingMortality_frac()` — computes direct-logging, collateral and infrastructure mortality fractions `(biogeochem/EDLoggingMortalityMod.F90:208)`
- `get_harvest_rate_area()` — area-based harvest rates `(biogeochem/EDLoggingMortalityMod.F90:426)`
- `get_harvest_rate_carbon()` — carbon-based harvest rates `(biogeochem/EDLoggingMortalityMod.F90:632)`

## Boundary Conditions: Host Model Interface

FATES exchanges information with the host land model through boundary-condition structures declared in `main/FatesInterfaceTypesMod.F90`.

### Inputs from HLM (`bc_in_type`)

| Category | Key Variables | Purpose |
|----------|---------------|---------|
| Radiation | `solad_parb`, `solai_parb` | Direct/diffuse PAR and NIR |
| Hydrology | `smp_sl`, `h2o_liqvol_sl`, `watsat_sl`, `eff_porosity_sl` | Soil moisture state |
| Temperature | `tempk_sl`, `t_veg_pa`, `t_soisno_sl` | Soil and vegetation temperature drivers |
| Decomposition controls | `w_scalar_sisl`, `t_scalar_sisl` | Moisture/temperature scalars for litter and SOM decomp |
| BGC accounting | `tot_het_resp`, `tot_somc`, `tot_litc` | Site-level pool diagnostics from HLM |
| Snow | `snow_depth_si`, `frac_sno_eff_si`, `fcansno_pa` | Snow state for radiation/phenology |
| Fire weather | `lightning24`, `pop_density`, `wind24_pa`, `relhumid24_pa`, `precip24_pa` | Ignition sources and SPITFIRE drivers |
| BGC nutrients | `plant_nh4_uptake_flux`, `plant_no3_uptake_flux`, `plant_p_uptake_flux` | Nutrient uptake when CNP is coupled to HLM BGC |
| Land use | `hlm_harvest_rates`, `hlm_harvest_catnames`, `hlm_luh_states`, `hlm_luh_transitions` | Harvest prescriptions and LUH2 states/transitions |

`bc_in_type` is declared at `main/FatesInterfaceTypesMod.F90:383-606`. Allocations are in `allocate_bcin()` `(main/FatesInterfaceMod.F90:443-619)`.

### Outputs to HLM (`bc_out_type`)

| Category | Key Variables | Purpose |
|----------|---------------|---------|
| Radiation | `albd_parb`, `albi_parb`, `fabd_parb`, `fabi_parb`, `ftdd_parb`, `ftid_parb`, `ftii_parb`, `fsun_pa`, `laisun_pa`, `laisha_pa` | Albedo, sunlit fraction, two-stream transmittance |
| Hydrology | `rootr_pasl`, `btran_pa`, `active_suction_sl` | Root uptake profile, transpiration stress |
| Stomatal conductance | `rssun_pa`, `rssha_pa` | Sun/shade canopy resistance |
| Structure | `elai_pa`, `esai_pa`, `tlai_pa`, `tsai_pa`, `htop_pa`, `hbot_pa`, `dleaf_pa`, `displa_pa`, `z0m_pa`, `canopy_fraction_pa` | Exposed/total LAI/SAI, canopy height/geometry |
| Litter fluxes | `litt_flux_cel_c_si`, `litt_flux_lig_c_si`, `litt_flux_lab_c_si`, plus N/P analogues | Litter fragmentation to soil BGC |
| Nutrient competition | `veg_rootc`, `decompmicc`, `ft_index`, `cn_scalar`, `cp_scalar` | Competitor state for soil BGC |
| BGC source terms | `source_nh4`, `source_p` | FATES-generated source to mineralized N and P pools |
| LULCC | `hrv_deadstemc_to_prod10c`, `hrv_deadstemc_to_prod100c` | Harvested wood-product fluxes |

`bc_out_type` is declared at `main/FatesInterfaceTypesMod.F90:609-807`. Allocations are in `allocate_bcout()` `(main/FatesInterfaceMod.F90:623-759)`.

### Parameter Constants (`bc_pconst_type`)

Parameters set once during initialization and held constant throughout the simulation, mostly ECA uptake kinetics. Allocated in `allocate_bcpconst()` `(main/FatesInterfaceMod.F90:236-254)` and populated in `set_bcpconst()` `(main/FatesInterfaceMod.F90:258-278)`:

```
vmax_nh4, vmax_no3, vmax_p          ! uptake rate constants per PFT
eca_km_nh4, eca_km_no3, eca_km_p    ! half-saturation constants
eca_km_ptase, eca_vmax_ptase
eca_alpha_ptase, eca_lambda_ptase
eca_plant_escalar                    ! site-wide scalar
j_uptake                             ! per soil decomp layer
```

## Mass Balance and Diagnostics

FATES performs rigorous mass-balance checking. Inside `ed_ecosystem_dynamics()`, six checkpoints are issued: `TotalBalanceCheck(currentSite, N)` for N=0..5 at lines `(main/EDMainMod.F90:201, 266, 289, 307, 322, 329)`. Two additional checks are issued by `ed_update_site()` at `:855` (call_index=6) and `:861` (`final_check_id`) to cover restart and post-update consistency. The `TotalBalanceCheck` body is at `main/EDMainMod.F90:928-1127`.

`SiteMassStock()` calculates total carbon (or nutrient) across all live vegetation, litter, and seed pools to verify conservation.

## Parameter System

FATES loads parameters from a JSON file (`parameter_files/fates_params_default.json`). The CDL file used in earlier API generations no longer exists in the canonical location; historical CDL snapshots are preserved under `parameter_files/archive/` (api24 through api41).

Parameters include:

- PFT-specific traits (wood density, leaf lifespan, allometric coefficients, stoichiometry)
- Global scalars (mortality disturbance fraction `fates_mort_disturb_frac`, canopy exclusion exponent `fates_comp_excln`, phenology thresholds, fusion tolerances)
- Mode switches (`fates_allom_hmode`, `fates_allom_lmode`, `fates_stomatal_model`, `fates_radiation_model`, etc.)

Loading is one-shot, driven from `SetFatesGlobalElements1()` `(main/FatesInterfaceMod.F90:792)`:

```fortran
call JSONSetInvalid(fates_check_param_set+10._r8)
call JSONSetLogInit(fates_log())
call JSONRead(paramfile,pstruct)
...
call FatesTransferParameters()
```

`JSONRead` is implemented in `main/JSONParameterUtilsMod.F90:189` (1272-line module); `FatesTransferParameters()` is a thin wrapper at `main/FatesInterfaceMod.F90:2675-2694` that calls five `TransferParams*` routines for generic, SPITFIRE, PRT, leaf-biophysics, and PFT parameter groups. The two-phase Register/Receive flow used in earlier API versions has been removed.

See [Parameter System](../getting-started/parameter_system.md) for details.

## Operational Modes

FATES supports several operational modes set by the HLM during initialization. All flags are declared in `main/FatesInterfaceTypesMod.F90`.

| Mode | Flag | Source | Description |
|------|------|--------|-------------|
| Standard | (default) | — | Full demographic dynamics |
| Satellite Phenology | `hlm_use_sp` | `main/FatesInterfaceTypesMod.F90:216` | Prescribed LAI from surface dataset |
| No Competition | `hlm_use_nocomp` | `main/FatesInterfaceTypesMod.F90:213` | One patch per PFT, no inter-PFT competition (does not by itself fix area) |
| Fixed Biogeography | `hlm_use_fixed_biogeog` | `main/FatesInterfaceTypesMod.F90:210` | PFT area fractions from surface dataset |
| Static Stand Structure | `hlm_use_ed_st3` | `main/FatesInterfaceTypesMod.F90:177` | No growth, recruitment, or mortality — experimental |
| LUH2 Land Use | `hlm_use_luh` | `main/FatesInterfaceTypesMod.F90:119` | Drive land-use transitions from LUH2 dataset |
| Tree Damage | `hlm_use_tree_damage` | `main/FatesInterfaceTypesMod.F90:151` | Enable crown-damage submodule |

## Summary

FATES implements ecosystem demography through a clean separation of site/patch/cohort data structures, a one-shot JSON-based parameter system, and a daily execution pipeline that integrates mortality, allocation, disturbance and recruitment. The modular design (PARTEH, SPITFIRE, plant hydraulics, tree damage, logging, LUH2 land use) allows components to be swapped while the site-patch-cohort backbone is maintained. For subsystem details, follow the links at the top of this document.
