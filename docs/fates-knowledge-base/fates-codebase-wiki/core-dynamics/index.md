# Core Ecosystem Dynamics

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

**Relevant source files:**
- `main/EDMainMod.F90`
- `biogeochem/EDPhysiologyMod.F90`
- `biogeochem/EDPatchDynamicsMod.F90`
- `biogeochem/EDCohortDynamicsMod.F90`
- `biogeochem/EDMortalityFunctionsMod.F90`
- `biogeochem/EDLoggingMortalityMod.F90`
- `main/EDTypesMod.F90`
- `biogeochem/FatesCohortMod.F90`
- `biogeochem/FatesPatchMod.F90`

## Purpose and Scope

This document describes the core ecosystem dynamics system in FATES, which orchestrates all vegetation processes on a daily timestep. The system manages the simulation of plant growth, mortality, disturbance, and succession through a coordinated sequence of operations that update cohort, patch, and site-level state variables while maintaining mass balance.

For detailed information about specific subsystems:

- [Daily Dynamics Loop](daily_loop.md) — daily timestep operations and call ordering
- [Patch Dynamics and Disturbances](patch_dynamics.md) — patch creation, fusion, termination
- [Cohort Lifecycle Management](cohort_lifecycle.md) — cohort creation, recruitment, fusion, termination
- [Data Structures: Sites, Patches, and Cohorts](data_structures.md) — memory organization and linked lists

## System Overview

The core dynamics system is centered around the `ed_ecosystem_dynamics` subroutine in `EDMainMod`, which serves as the main orchestrator for all daily ecosystem processes. This routine coordinates interactions between:

- **Physiological processes**: phenology, photosynthesis, allocation, respiration
- **Demographic processes**: recruitment, mortality, growth
- **Disturbance processes**: fire, logging, treefall mortality
- **Structural processes**: cohort fusion/termination, patch spawning/fusion

The system operates on a hierarchical data structure (`ed_site_type` → `fates_patch_type` → `fates_cohort_type`) and maintains strict mass balance through multiple checkpoints during the daily cycle.

Sources: `(main/EDMainMod.F90:1-140)`

## Main Orchestration Entry Point

### ed_ecosystem_dynamics Subroutine

The `ed_ecosystem_dynamics` subroutine in `EDMainMod` is called once per day from the host land model. It operates on a single site (`ed_site_type`) and exchanges information with the host model through boundary condition types (`bc_in_type` for inputs, `bc_out_type` for outputs).

Sources: `(main/EDMainMod.F90:141-317)`

## Core Dynamics Sequence

### Detailed Call Sequence

The following table summarizes the key subroutines called during the daily dynamics cycle, in the order they appear in `ed_ecosystem_dynamics`:

| Phase | Subroutine | Module | Purpose |
| --- | --- | --- | --- |
| Initialization | ZeroAllocationRates | EDPhysiologyMod | Zero out growth and turnover rates |
|  | ZeroLitterFluxes | EDPhysiologyMod | Zero out litter input/output fluxes |
|  | TotalBalanceCheck(0) | EDMainMod | Record initial mass stocks |
| Phenology | phenology or satellite_phenology | EDPhysiologyMod | Update leaf status (flush/abscise) |
| Disturbance | fire_model | SFMainMod | Calculate fire spread and effects |
|  | disturbance_rates | EDPatchDynamicsMod | Calculate mortality and disturbance rates |
| Growth | ed_integrate_state_variables | EDMainMod | Daily growth, allocation, mortality |
| Demographics | recruitment | EDPhysiologyMod | Add new recruits to patches |
| Balance Check | TotalBalanceCheck(1) | EDMainMod | Verify recruitment mass conservation |
| Demographics | sort_cohorts | EDCohortDynamicsMod | Sort cohorts by height |
|  | terminate_cohorts(level=1) | EDCohortDynamicsMod | Remove numerically unstable cohorts |
|  | fuse_cohorts | EDCohortDynamicsMod | Merge similar cohorts |
|  | terminate_cohorts(level=2) | EDCohortDynamicsMod | Remove small/depleted cohorts |
| Balance Check | TotalBalanceCheck(2) | EDMainMod | Verify cohort management conserved mass |
| Patch Dynamics | spawn_patches | EDPatchDynamicsMod | Create new patches from disturbance |
|  | TotalBalanceCheck(3) | EDMainMod | Verify disturbance transfers |
|  | fuse_patches | EDPatchDynamicsMod | Merge similar-age patches |
|  | TotalBalanceCheck(4) | EDMainMod | Verify patch fusion conserved mass |
|  | terminate_patches | EDPatchDynamicsMod | Remove small patches |
| Final Check | TotalBalanceCheck(5) | EDMainMod | Final verification of total mass |

Sources: `(main/EDMainMod.F90:141-317)`, `(biogeochem/EDPhysiologyMod.F90:1-200)`, `(biogeochem/EDPatchDynamicsMod.F90:1-160)`

## State Integration: ed_integrate_state_variables

The `ed_integrate_state_variables` subroutine performs the daily update of all cohort-level state variables. This is where plant growth, allocation, and turnover actually occur.

### Key State Updates

Within the cohort loop, the following state variables are updated:

| Variable | Update Mechanism | Purpose |
| --- | --- | --- |
| cohort%n | Integrated from cohort%dndt | Number density (/m²) |
| cohort%dbh | Growth from PARTEH allocation | Diameter at breast height [cm] |
| cohort%height | Allometry from DBH (`h_allom`) | Plant height [m] |
| cohort%prt | DailyPRT() (3-phase call) | All biomass pools (leaf, root, sapwood, etc.) |
| cohort%co_hydr | UpdateSizeDepPlantHydProps() | Hydraulic compartment properties |
| cohort%npp_acc_hold | Accumulation during growth | Net primary production (held for I/O) |
| cohort%gpp_acc_hold | Accumulation during photosynthesis | Gross primary production (held for I/O) |
| cohort%resp_acc_hold | Accumulation during respiration | Total respiration (held for I/O) |

Sources: `(main/EDMainMod.F90:320-715)`

## Module Coordination

`EDMainMod` is the top-level orchestrator. It directly imports and calls routines from:

- `EDPhysiologyMod` (phenology, recruitment, ZeroAllocationRates, ZeroLitterFluxes, EvaluateAndCorrectDBH, EffluxIntoLitterPools)
- `EDPatchDynamicsMod` (disturbance_rates, spawn_patches, fuse_patches, terminate_patches)
- `EDCohortDynamicsMod` (sort_cohorts, fuse_cohorts, terminate_cohorts)
- `EDMortalityFunctionsMod` (Mortality_Derivative)
- `SFMainMod` (fire_model)

Cohort state updates dispatch into `PRTGenericMod` (via `cohort%prt%DailyPRT`) and into `FatesAllometryMod` (via `h_allom`). When plant hydraulics is enabled, updates also dispatch to `FatesHydroWTFMod`/`FatesPlantHydraulicsMod` through `UpdateSizeDepPlantHydProps`.

Sources: `(main/EDMainMod.F90:1-140)`, `(main/EDMainMod.F90:320-682)`

## Mass Balance and Quality Control

### TotalBalanceCheck System

The `TotalBalanceCheck` subroutine is called at multiple checkpoints during the daily cycle to verify mass conservation. Each checkpoint has a specific purpose:

| Checkpoint | Call Location | Purpose |
| --- | --- | --- |
| 0 | Before dynamics (`:196`) | Record initial stocks; zero flux accumulators |
| 1 | After recruitment (`:255`) | Verify recruitment mass conservation |
| 2 | After cohort fusion/termination (`:277`) | Verify cohort management conserved mass |
| 3 | After patch spawning (`:294`) | Verify disturbance transfers |
| 4 | After patch fusion / hydraulics update (`:309`) | Verify patch fusion conserved mass |
| 5 | End of dynamics (`:315`) | Final verification of total mass conservation |

The balance check compares standing stocks, input fluxes, output fluxes, and stock changes across elements (carbon, nitrogen, phosphorus when enabled):

- **Inputs**: GPP, seed rain, root uptake, prescribed inputs
- **Outputs**: Autotrophic respiration, wood products, fragmentation, fire emissions
- **Stock changes**: Biomass in plants and litter pools

If the imbalance exceeds tolerance (`calloc_abs_error`), the run aborts with a diagnostic message.

Sources: `(main/EDMainMod.F90:847-1024)`

## Bypass Modes

### Special Simulation Modes

FATES supports several runtime flags that bypass or modify standard dynamics:

| Mode Flag | Description | Impact on Dynamics |
| --- | --- | --- |
| `hlm_use_ed_st3` | Ecosystem state (ST3) mode | Bypasses phenology, disturbance, patch dynamics |
| `hlm_use_sp` | Satellite phenology mode | Uses prescribed LAI/SAI instead of prognostic phenology |
| `hlm_use_ed_prescribed_phys` | Prescribed physiology | Uses prescribed NPP instead of prognostic GPP |
| `hlm_use_nocomp` | No competition mode | Single-PFT patches, no inter-PFT competition |

The `bypass_dynamics` subroutine is called when ST3 mode is active to ensure proper initialization of cohort flags without executing full dynamics.

Sources: `(main/EDMainMod.F90:198-237)`, `(main/EDMainMod.F90:1028-1087)`

## Summary of Key Functions

### Primary Orchestration Functions

| Function | Module | File | Purpose |
| --- | --- | --- | --- |
| ed_ecosystem_dynamics | EDMainMod | `main/EDMainMod.F90:141-317` | Main daily orchestrator |
| ed_integrate_state_variables | EDMainMod | `main/EDMainMod.F90:320-766` | Daily growth integration |
| TotalBalanceCheck | EDMainMod | `main/EDMainMod.F90:847-1024` | Mass balance verification |
| bypass_dynamics | EDMainMod | `main/EDMainMod.F90:1028-1087` | ST3-mode cohort housekeeping |

### Supporting Process Functions

| Function | Module | File | Purpose |
| --- | --- | --- | --- |
| phenology | EDPhysiologyMod | `biogeochem/EDPhysiologyMod.F90` | Leaf phenology |
| recruitment | EDPhysiologyMod | `biogeochem/EDPhysiologyMod.F90:2440` | Add new cohorts |
| disturbance_rates | EDPatchDynamicsMod | `biogeochem/EDPatchDynamicsMod.F90:160` | Calculate disturbance |
| spawn_patches | EDPatchDynamicsMod | `biogeochem/EDPatchDynamicsMod.F90:398` | Create new patches |
| fuse_patches | EDPatchDynamicsMod | `biogeochem/EDPatchDynamicsMod.F90:2103` | Merge patches |
| terminate_patches | EDPatchDynamicsMod | `biogeochem/EDPatchDynamicsMod.F90:2610` | Remove small patches |
| fuse_cohorts | EDCohortDynamicsMod | `biogeochem/EDCohortDynamicsMod.F90:694` | Merge cohorts |
| terminate_cohorts | EDCohortDynamicsMod | `biogeochem/EDCohortDynamicsMod.F90:347` | Remove cohorts |
| Mortality_Derivative | EDMortalityFunctionsMod | `biogeochem/EDMortalityFunctionsMod.F90:234` | Calculate mortality |

Sources: `(main/EDMainMod.F90:1-317)`, `(biogeochem/EDPhysiologyMod.F90:2440)`, `(biogeochem/EDPatchDynamicsMod.F90:160-398)`, `(biogeochem/EDCohortDynamicsMod.F90:1-1500)`

## Design Principles

The core dynamics system follows several key design principles:

1. **Daily timestep for demography and disturbance**: sub-daily physiology (photosynthesis, respiration) is accumulated between dynamics calls and consumed once per day.
2. **Strict mass balance**: six balance checkpoints cover the full daily cycle, any imbalance beyond `calloc_abs_error` halts the simulation.
3. **Hierarchical linked lists**: site → patch (age-ordered) → cohort (height-ordered) enables efficient insertion and traversal without global re-sorting.
4. **Three-phase PARTEH allocation**: prioritized, non-stature, and stature phases allow deterministic handling of storage deficit correction, damage recovery, and residual growth.
5. **Explicit bypass paths**: ST3 and SP modes take short-circuit branches so biophysics-only configurations remain consistent.

Sources: `(main/EDMainMod.F90:141-317)`
