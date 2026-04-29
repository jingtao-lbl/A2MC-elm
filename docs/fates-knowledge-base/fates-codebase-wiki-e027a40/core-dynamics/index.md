# Core Ecosystem Dynamics

---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

**Relevant source files:**
- `main/EDMainMod.F90`
- `biogeochem/EDPhysiologyMod.F90`
- `biogeochem/EDPatchDynamicsMod.F90`
- `biogeochem/EDCohortDynamicsMod.F90`
- `biogeochem/EDMortalityFunctionsMod.F90`
- `biogeochem/EDLoggingMortalityMod.F90`
- `biogeochem/FatesSoilBGCFluxMod.F90`
- `main/EDTypesMod.F90`
- `biogeochem/FatesCohortMod.F90`
- `biogeochem/FatesPatchMod.F90`
- `fire/SFMainMod.F90`

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
- **Demographic processes**: recruitment, mortality, growth, herbivory
- **Disturbance processes**: fire, logging, treefall mortality, land-use change
- **Structural processes**: cohort fusion/termination, patch spawning/fusion

The system operates on a hierarchical data structure (`ed_site_type` → `fates_patch_type` → `fates_cohort_type`) and maintains strict mass balance through six numbered checkpoints during the daily cycle.

Sources: `(main/EDMainMod.F90:1-145)`

## Main Orchestration Entry Point

### ed_ecosystem_dynamics Subroutine

The `ed_ecosystem_dynamics` subroutine in `EDMainMod` is called once per day from the host land model. It operates on a single site (`ed_site_type`) and exchanges information with the host model through boundary condition types (`bc_in_type` for inputs, `bc_out_type` for outputs).

Sources: `(main/EDMainMod.F90:148-332)`

## Core Dynamics Sequence

### Detailed Call Sequence

The following table summarizes the 26 key subroutines called during the daily dynamics cycle, in the order they appear in `ed_ecosystem_dynamics`:

| Phase | Subroutine | Module | Purpose |
| --- | --- | --- | --- |
| Initialization | ZeroMassBalFlux / ZeroFluxDiags | EDTypesMod | Zero per-element mass balance flux accumulators |
|  | IsItLoggingTime / IsItDamageTime | EDLoggingMortalityMod / DamageMainMod | Set global event flags |
|  | ZeroAllocationRates | EDPhysiologyMod | Zero out growth and turnover rates |
|  | ZeroLitterFluxes | EDPhysiologyMod | Zero out litter input/output fluxes |
|  | ZeroBCOutCarbonFluxes | FatesInterfaceTypesMod | Zero diagnostic boundary condition C fluxes |
|  | TotalBalanceCheck(0) | EDMainMod | Record initial mass stocks |
| Phenology | phenology or satellite_phenology | EDPhysiologyMod | Update leaf status (flush/abscise) |
| Disturbance | DailyFireModel | SFMainMod | Calculate fire spread and effects |
|  | disturbance_rates | EDPatchDynamicsMod | Calculate mortality and disturbance rates |
| Growth | ed_integrate_state_variables | EDMainMod | Daily growth, allocation, mortality, post-cohort housekeeping |
| Bypass | bypass_dynamics (ST3 only) | EDMainMod | ST3-mode cohort housekeeping path |
| Demographics | recruitment | EDPhysiologyMod | Add new recruits to patches |
| Balance Check | TotalBalanceCheck(1) | EDMainMod | Verify recruitment mass conservation |
| Demographics | currentPatch%SortCohorts() | FatesPatchMod | Sort cohorts by height (type-bound method) |
|  | terminate_cohorts(level=1) | EDCohortDynamicsMod | Remove numerically unstable cohorts |
|  | fuse_cohorts | EDCohortDynamicsMod | Merge similar cohorts |
|  | terminate_cohorts(level=2) | EDCohortDynamicsMod | Remove small/depleted cohorts |
| Balance Check | TotalBalanceCheck(2) | EDMainMod | Verify cohort management conserved mass |
| Patch Dynamics | spawn_patches | EDPatchDynamicsMod | Create new patches from disturbance |
|  | TotalBalanceCheck(3) | EDMainMod | Verify disturbance transfers |
|  | fuse_patches | EDPatchDynamicsMod | Merge similar-age patches |
|  | UpdateSizeDepRhizHydProps | FatesPlantHydraulicsMod | Update rhizosphere geometry (if `hlm_use_planthydro`) |
|  | TotalBalanceCheck(4) | EDMainMod | Verify patch fusion conserved mass |
|  | terminate_patches | EDPatchDynamicsMod | Remove small patches |
| Final Check | TotalBalanceCheck(5) | EDMainMod | Final verification of total mass |

Sources: `(main/EDMainMod.F90:148-332)`, `(biogeochem/EDPhysiologyMod.F90:1-200)`, `(biogeochem/EDPatchDynamicsMod.F90:160-484)`

### Key API-Level Changes Since e85d997

- `fire_model` was renamed to `DailyFireModel` and is now imported from `SFMainMod` (`main/EDMainMod.F90:61`, called at `:224`).
- A new step `ZeroBCOutCarbonFluxes(bc_out)` was inserted at `main/EDMainMod.F90:198` between `ZeroLitterFluxes` and `TotalBalanceCheck(0)`. The daily loop now contains 26 numbered steps (was 25).
- `sort_cohorts` is no longer a free subroutine. Sorting is now invoked via the type-bound method `currentPatch%SortCohorts()` (`main/EDMainMod.F90:272`; method body at `biogeochem/FatesPatchMod.F90:1172-1237`).

## State Integration: ed_integrate_state_variables

The `ed_integrate_state_variables` subroutine performs the daily update of all cohort-level state variables and substantial post-cohort-loop housekeeping. This is where plant growth, allocation, turnover, herbivory, recruit feedback, plant-hydraulics water mortality bookkeeping, seed mixing, pre-disturbance litter generation, and the final integration of cohort number from mortality rates occur.

### Key State Updates

Within the cohort loop, the following state variables are updated:

| Variable | Update Mechanism | Purpose |
| --- | --- | --- |
| cohort%n | Integrated from cohort%dndt at end of routine | Number density (/m²) |
| cohort%dbh | Growth from PARTEH allocation | Diameter at breast height [cm] |
| cohort%height | Allometry from DBH (`h_allom`) | Plant height [m] |
| cohort%prt | DailyPRT() (3-phase call) | All biomass pools (leaf, root, sapwood, etc.) |
| cohort%co_hydr | UpdateSizeDepPlantHydProps() | Hydraulic compartment properties |
| cohort%npp_acc_hold | Accumulation during growth | Net primary production (held for I/O) |
| cohort%gpp_acc_hold | Accumulation during photosynthesis | Gross primary production (held for I/O) |
| cohort%resp_m_acc_hold | Maintenance respiration accumulation (held for I/O) | Maintenance respiration |
| cohort%resp_g_acc_hold | Growth respiration accumulation (held for I/O) | Growth respiration |
| cohort%resp_excess_hold | Excess respiration from nutrient limitation | Excess respiration |

Note: the prior single `resp_acc`/`resp_acc_hold` cohort field has been split into the three independent accumulators above (`resp_m_acc/_hold`, `resp_g_acc_hold`, `resp_excess_hold`). See [Data Structures](data_structures.md).

Sources: `(main/EDMainMod.F90:335-810)`

## Module Coordination

`EDMainMod` is the top-level orchestrator. It directly imports and calls routines from:

- `EDPhysiologyMod` (phenology, satellite_phenology, recruitment, ZeroAllocationRates, ZeroLitterFluxes, SeedUpdate, GenerateDamageAndLitterFluxes, PreDisturbanceLitterFluxes, PreDisturbanceIntegrateLitter, UpdateRecruitL2FR, UpdateRecruitStoich)
- `EDPatchDynamicsMod` (disturbance_rates, spawn_patches, fuse_patches, terminate_patches)
- `EDCohortDynamicsMod` (fuse_cohorts, terminate_cohorts, EvaluateAndCorrectDBH, DamageRecovery)
- `EDMortalityFunctionsMod` (Mortality_Derivative)
- `SFMainMod` (DailyFireModel)
- `FatesSoilBGCFluxMod` (EffluxIntoLitterPools, FluxIntoLitterPools, PrepNutrientAquisitionBCs, PrepCH4BCs)
- `FatesPlantHydraulicsMod` (UpdateSizeDepRhizHydProps, UpdateSizeDepPlantHydProps, UpdateSizeDepPlantHydStates, AccumulateMortalityWaterStorage)
- `FatesLandUseChangeMod` (FatesGrazing — called once per cohort per day inside `ed_integrate_state_variables`)

Cohort state updates dispatch into `PRTGenericMod` (via `cohort%prt%DailyPRT`) and into `FatesAllometryMod` (via `h_allom`). `PRTLossFluxesMod` provides `PRTMaintTurnover`. When plant hydraulics is enabled, updates also dispatch to `FatesPlantHydraulicsMod` through `UpdateSizeDepPlantHydProps`/`UpdateSizeDepPlantHydStates` and `AccumulateMortalityWaterStorage`.

Sources: `(main/EDMainMod.F90:1-145)`, `(main/EDMainMod.F90:335-810)`

## Mass Balance and Quality Control

### TotalBalanceCheck System

The `TotalBalanceCheck` subroutine is called at six numbered checkpoints during the daily cycle to verify mass conservation. The signature gained an optional `is_restarting` argument so that restart initialisation can suppress flux accounting:

```fortran
subroutine TotalBalanceCheck(currentSite, call_index, is_restarting)
```

Each checkpoint has a specific purpose:

| Checkpoint | Call Location | Purpose |
| --- | --- | --- |
| 0 | Before dynamics (`:201`) | Record initial stocks; zero flux accumulators |
| 1 | After recruitment (`:266`) | Verify recruitment mass conservation |
| 2 | After cohort fusion/termination (`:289`) | Verify cohort management conserved mass |
| 3 | After patch spawning (`:307`) | Verify disturbance transfers |
| 4 | After patch fusion / hydraulics update (`:322`) | Verify patch fusion conserved mass |
| 5 | End of dynamics (`:329`) | Final verification of total mass conservation |

The balance check compares standing stocks, input fluxes, output fluxes, and stock changes across elements (carbon, nitrogen, phosphorus when enabled):

- **Inputs**: GPP, seed rain, root uptake, prescribed inputs
- **Outputs**: Autotrophic respiration, wood products, fragmentation, fire emissions
- **Stock changes**: Biomass in plants and litter pools

If the imbalance exceeds tolerance (`calloc_abs_error`), the run aborts with a diagnostic message.

Sources: `(main/EDMainMod.F90:928-1127)`

## Bypass Modes

### Special Simulation Modes

FATES supports several runtime flags that bypass or modify standard dynamics:

| Mode Flag | Description | Impact on Dynamics |
| --- | --- | --- |
| `hlm_use_ed_st3` | Ecosystem state (ST3) mode | Bypasses phenology, disturbance, patch dynamics |
| `hlm_use_sp` | Satellite phenology mode | Uses prescribed LAI/SAI instead of prognostic phenology |
| `hlm_use_ed_prescribed_phys` | Prescribed physiology | Uses prescribed NPP instead of prognostic GPP |
| `hlm_use_nocomp` | No competition mode | Patches carry a `nocomp_pft_label`; PFTs are simulated side-by-side without inter-PFT competition |

The `bypass_dynamics` subroutine is called when ST3 mode is active to ensure proper initialization of cohort flags without executing full dynamics. It zeros mortality components, computes hold-style respiration accumulators (including the new `resp_g_acc_hold` from `prt_params%grperc`), and resets growth-rate diagnostics so that biophysics-only runs keep mass balance.

Sources: `(main/EDMainMod.F90:215-248)`, `(main/EDMainMod.F90:1131-1196)`

## Summary of Key Functions

### Primary Orchestration Functions

| Function | Module | File | Purpose |
| --- | --- | --- | --- |
| ed_ecosystem_dynamics | EDMainMod | `main/EDMainMod.F90:148-332` | Main daily orchestrator |
| ed_integrate_state_variables | EDMainMod | `main/EDMainMod.F90:335-810` | Daily growth integration plus post-cohort housekeeping |
| TotalBalanceCheck | EDMainMod | `main/EDMainMod.F90:928-1127` | Mass balance verification |
| bypass_dynamics | EDMainMod | `main/EDMainMod.F90:1131-1196` | ST3-mode cohort housekeeping |

### Supporting Process Functions

| Function | Module | File | Purpose |
| --- | --- | --- | --- |
| phenology | EDPhysiologyMod | `biogeochem/EDPhysiologyMod.F90` | Leaf phenology |
| recruitment | EDPhysiologyMod | `biogeochem/EDPhysiologyMod.F90:2467` | Add new cohorts |
| disturbance_rates | EDPatchDynamicsMod | `biogeochem/EDPatchDynamicsMod.F90:164` | Calculate disturbance |
| spawn_patches | EDPatchDynamicsMod | `biogeochem/EDPatchDynamicsMod.F90:488` | Create new patches |
| fuse_patches | EDPatchDynamicsMod | `biogeochem/EDPatchDynamicsMod.F90:2882` | Merge patches |
| terminate_patches | EDPatchDynamicsMod | `biogeochem/EDPatchDynamicsMod.F90:3369` | Remove small patches |
| fuse_cohorts | EDCohortDynamicsMod | `biogeochem/EDCohortDynamicsMod.F90:648` | Merge cohorts |
| terminate_cohorts | EDCohortDynamicsMod | `biogeochem/EDCohortDynamicsMod.F90:283` | Remove cohorts |
| Mortality_Derivative | EDMortalityFunctionsMod | `biogeochem/EDMortalityFunctionsMod.F90:289` | Calculate mortality |
| EvaluateAndCorrectDBH | EDCohortDynamicsMod | `biogeochem/EDCohortDynamicsMod.F90:1236` | DBH-allometry consistency check |
| EffluxIntoLitterPools | FatesSoilBGCFluxMod | `biogeochem/FatesSoilBGCFluxMod.F90:544` | Per-cohort nutrient efflux into patch litter |
| FluxIntoLitterPools | FatesSoilBGCFluxMod | `biogeochem/FatesSoilBGCFluxMod.F90:609` | Push patch-level litter into BGC interface |
| DailyFireModel | SFMainMod | `fire/SFMainMod.F90:46` | Daily fire spread and consumption |
| SortCohorts (type-bound) | FatesPatchMod | `biogeochem/FatesPatchMod.F90:1172` | Reorder cohorts by height |
| set_patchno | EDTypesMod | `main/EDTypesMod.F90:617` | Renumber patches; imported by EDPatchDynamicsMod at `:25` |

Sources: `(main/EDMainMod.F90:1-332)`, `(biogeochem/EDPhysiologyMod.F90:2467)`, `(biogeochem/EDPatchDynamicsMod.F90:160-3700)`, `(biogeochem/EDCohortDynamicsMod.F90:1-1597)`, `(biogeochem/FatesSoilBGCFluxMod.F90:544-947)`, `(fire/SFMainMod.F90:46-69)`

## Design Principles

The core dynamics system follows several key design principles:

1. **Daily timestep for demography and disturbance**: sub-daily physiology (photosynthesis, respiration) is accumulated between dynamics calls and consumed once per day.
2. **Strict mass balance**: six balance checkpoints cover the full daily cycle; any imbalance beyond `calloc_abs_error` halts the simulation.
3. **Hierarchical linked lists**: site → patch (age-ordered) → cohort (height-ordered) enables efficient insertion and traversal without global re-sorting.
4. **Three-phase PARTEH allocation**: prioritized, non-stature, and stature phases allow deterministic handling of storage deficit correction, damage recovery, and residual growth.
5. **Explicit bypass paths**: ST3 and SP modes take short-circuit branches so biophysics-only configurations remain consistent.
6. **Decomposed daily respiration accounting**: maintenance, growth, and excess respiration are tracked in independent cohort accumulators so that PARTEH can adjust each component during the daily integrator.

Sources: `(main/EDMainMod.F90:148-332)`
