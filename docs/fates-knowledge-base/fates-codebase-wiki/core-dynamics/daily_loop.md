# Daily Dynamics Loop

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

**Relevant source files:**
- `main/EDMainMod.F90`
- `biogeochem/EDPhysiologyMod.F90`
- `biogeochem/EDCohortDynamicsMod.F90`
- `biogeochem/EDPatchDynamicsMod.F90`
- `biogeochem/EDMortalityFunctionsMod.F90`
- `biogeochem/EDLoggingMortalityMod.F90`
- `biogeochem/FatesAllometryMod.F90`

This page describes the daily timestep orchestration in FATES, including the main sequence of operations executed each day, mass balance verification, and the coordination between different physiological and ecological processes.

For individual processes called during this loop (phenology, recruitment, mortality), see: [Phenology and Leaf Dynamics](../plant-physiology/phenology.md), [Recruitment](cohort_lifecycle.md), [Mortality Processes](../plant-physiology/mortality.md), [PARTEH Allocation](../plant-physiology/parteh/index.md), [Patch Dynamics](patch_dynamics.md). For the data structures traversed, see [Data Structures](data_structures.md).

## Overview and Entry Point

The daily dynamics loop is executed through the `ed_ecosystem_dynamics` subroutine in `main/EDMainMod.F90:141-317`. This routine is called once per day from the host land model and coordinates all vegetation dynamics, including growth, mortality, disturbance, and biogeochemistry. It operates on a single site (`ed_site_type`) and exchanges information with the host model through boundary condition types (`bc_in_type`, `bc_out_type`).

### Key Design Principles

- Vegetation demography and disturbance are updated at a daily cadence; photosynthesis and respiration accumulate between calls and are consumed once per day.
- Mass balance is verified at six numbered checkpoints (`TotalBalanceCheck(0..5)`).
- Patch and cohort lists are maintained as age- and height-ordered doubly linked lists so that insertion, fusion, and termination are local operations.

## Main Dynamics Sequence

The following table captures the full sequence of calls inside `ed_ecosystem_dynamics`. Line numbers refer to `main/EDMainMod.F90` at commit `e85d997` and were verified against source.

| Step | Operation | Source line | Notes |
| --- | --- | --- | --- |
| 1 | Zero per-element `mass_balance%ZeroMassBalFlux()` and `flux_diags%ZeroFluxDiags()` | 164-167 | one per element (C, N, P) |
| 2 | Zero dynamics-frequency history variables | 170, 173 | `upfreq_in=1`, `upfreq_in=5` |
| 3 | `IsItLoggingTime`, `IsItDamageTime` | 177, 180 | global event flags |
| 4 | `ZeroAllocationRates(currentSite)` | 190 | clear per-day growth/turnover |
| 5 | `ZeroLitterFluxes(currentSite)` | 193 | clear litter input/output |
| 6 | `TotalBalanceCheck(currentSite, 0)` | 196 | record initial stocks |
| 7 | `phenology` or `satellite_phenology` | 203-205 | skipped in ST3 mode |
| 8 | `fire_model` | 218 | only if not ST3/SP and not bareground-only |
| 9 | `disturbance_rates` | 223 | only if not ST3/SP |
| 10 | `ed_integrate_state_variables` | 226 | daily cohort growth & allocation |
| 11 | `bypass_dynamics` (ST3 branch) | 235 | housekeeping-only path |
| 12 | `recruitment` (per patch) | 248 | only if not ST3/SP |
| 13 | `TotalBalanceCheck(currentSite, 1)` | 255 | verify recruitment conservation |
| 14 | `sort_cohorts` (per patch) | 261 | re-order by height |
| 15 | `terminate_cohorts(..., level=1, ...)` | 264 | remove numerically unstable cohorts |
| 16 | `fuse_cohorts` | 267 | merge similar cohorts |
| 17 | `terminate_cohorts(..., level=2, ...)` | 270 | remove small/depleted cohorts |
| 18 | `TotalBalanceCheck(currentSite, 2)` | 277 | verify cohort management |
| 19 | `spawn_patches(currentSite, bc_in)` | 292 | gated by `do_patch_dynamics` |
| 20 | `TotalBalanceCheck(currentSite, 3)` | 294 | verify disturbance transfers |
| 21 | `fuse_patches(currentSite, bc_in)` | 297 | merge similar patches |
| 22 | `UpdateSizeDepRhizHydProps` | 304 | only if `hlm_use_planthydro` |
| 23 | `TotalBalanceCheck(currentSite, 4)` | 309 | verify patch fusion |
| 24 | `terminate_patches(currentSite)` | 312 | remove small patches |
| 25 | `TotalBalanceCheck(currentSite, 5)` | 315 | final verification |

Sources: `(main/EDMainMod.F90:141-317)`

## State Integration: The Core Growth Loop

The `ed_integrate_state_variables` subroutine (`main/EDMainMod.F90:320-766`) contains the innermost loop where cohort-level state variables are updated. The outer loop walks patches from `oldest_patch` to `youngest_patch`; within each patch, cohorts are visited from `shortest` up to `taller`.

### Cohort State Update Sequence

Within each cohort iteration, the following state updates occur (line numbers verified against source):

| Step | Function/Operation | Purpose | Code reference |
| --- | --- | --- | --- |
| 1 | `Mortality_Derivative(...)` | Calculate mortality rates (background, hydraulic, carbon starvation, logging, fire, freezing, senescence, damage) | `(main/EDMainMod.F90:473)`, subroutine at `(biogeochem/EDMortalityFunctionsMod.F90:234)` |
| 2 | Store NPP/GPP/Resp into `_acc_hold` and push to `bc_out` | Save accumulated photosynthesis values for diagnostics | `(main/EDMainMod.F90:517-526)` |
| 3 | `PRTMaintTurnover(cohort%prt, ft, is_drought)` | Apply maintenance turnover to all organs | `(main/EDMainMod.F90:535)` |
| 4 | `cohort%prt%AgeLeaves(ft, sec_per_day)` | Advance leaf age classes | `(main/EDMainMod.F90:543)` |
| 5 | `EvaluateAndCorrectDBH(cohort, delta_dbh, delta_height)` | Ensure DBH is consistent with structural biomass | `(main/EDMainMod.F90:560)` |
| 6 | `cohort%prt%DailyPRT(phase=1)` | Prioritized allocation (turnover replacement, storage replenishment); skipped for newly recovered cohorts | `(main/EDMainMod.F90:582)` |
| 7 | `cohort%prt%DailyPRT(phase=2)` | Non-stature allocation for all cohorts (updated targets after damage recovery) | `(main/EDMainMod.F90:585)` |
| 8 | `DamageRecovery(csite, cpatch, cohort, newly_recovered)` | Create recovered cohort clone if crown damage recovery applies | `(main/EDMainMod.F90:595)` |
| 9 | `cohort%prt%DailyPRT(phase=3)` | Stature growth using remaining carbon | `(main/EDMainMod.F90:601)` |
| 10 | `EffluxIntoLitterPools(...)` | Transfer nutrient efflux to litter | `(main/EDMainMod.F90:608)` |
| 11 | `cohort%UpdateCohortBioPhysRates()` | Recalculate vcmax25top, jmax25top from leaf age distribution | `(main/EDMainMod.F90:641)` |
| 12 | `h_allom(cohort%dbh, ft, cohort%height)` | Update height from new DBH via allometry | `(main/EDMainMod.F90:647)` |
| 13 | Compute `dhdt` and `ddbhdt` | Growth rate diagnostics | `(main/EDMainMod.F90:649-650)` |
| 14 | Zero `npp_acc`, `gpp_acc`, `resp_acc` | Reset accumulators for next dynamics step | `(main/EDMainMod.F90:655-657)` |
| 15 | `UpdateSizeDepPlantHydProps` and `UpdateSizeDepPlantHydStates` | Update hydraulic geometry (if `hlm_use_planthydro`) | `(main/EDMainMod.F90:663-664)` |
| 16 | Increment `coage`, recalculate cohort age class (if `hlm_use_cohort_age_tracking`) | Cohort age tracking | `(main/EDMainMod.F90:669-678)` |

Outside the cohort loop, the subroutine also updates recruit stoichiometry (`UpdateRecruitStoich`, `:428`) and advances `currentPatch%age` by `hlm_freq_day` (`:433`), including the secondary-forest age clock (`:442-444`) and age class (`:448`).

Sources: `(main/EDMainMod.F90:458-685)`

## Mass Balance Verification

`TotalBalanceCheck` (`main/EDMainMod.F90:847-1024`) compares stock changes against the sum of tracked input and output fluxes for each element. The comparison uses a site-level tolerance, and failures abort the simulation.

### Balance Check Components

The mass balance verification tracks the following pools and fluxes at the site level (carbon always; nitrogen and phosphorus when CNP is active):

- **Standing stocks**: vegetation biomass (leaf, root, sapwood, structure, storage, reproductive), litter pools (CWD, fine litter), seed bank
- **Input fluxes**: GPP, external seed rain
- **Output fluxes**: autotrophic respiration, fragmentation to soil, seed decay/germination
- **Lateral fluxes**: root uptake (for CNP mode, includes N and P tracking)

The six numbered checkpoints frame the loop: checkpoint 0 records the initial state, 1 confirms recruitment conservation, 2 confirms cohort fusion/termination, 3 confirms patch spawning, 4 confirms patch fusion and hydraulic updates, and 5 is the final closing check.

Sources: `(main/EDMainMod.F90:196-315)`, `(main/EDMainMod.F90:847-1024)`

## Bypass Mode for Non-Dynamic Simulations

When operating in ST3 (static stand structure) mode or SP (satellite phenology) mode, many of the steps above are skipped. In ST3 mode `bypass_dynamics` is called in lieu of `ed_integrate_state_variables`; it does the minimum required housekeeping — marking cohorts as not-new, moving `*_acc` into `*_acc_hold`, and zeroing mortality and growth rates — so that biophysics-only runs can reuse the same data structures without violating mass balance.

Sources: `(main/EDMainMod.F90:198-237)`, `(main/EDMainMod.F90:1028-1087)`

## PARTEH Three-Phase Allocation

The daily allocation within `ed_integrate_state_variables` uses a three-phase approach to prioritize different allocation targets.

### Phase 1: Prioritized Allocation

- **Purpose**: essential maintenance and deficit correction
- **Operations**: replacement of turnover losses, replenishment of depleted storage
- **Executed**: once per day, only for non-recovered cohorts
- **Code**: `cohort%prt%DailyPRT(phase=1)` at `(main/EDMainMod.F90:582)`

### Phase 2: Non-Stature Allocation

- **Purpose**: update allocation targets without growing stature
- **Operations**: adjust leaf/root targets after damage recovery, maintain allometric ratios
- **Executed**: for all cohorts including newly recovered clones created in `DamageRecovery`
- **Code**: `cohort%prt%DailyPRT(phase=2)` at `(main/EDMainMod.F90:585)`

### Phase 3: Stature Growth

- **Purpose**: diameter and height growth using surplus carbon
- **Operations**: integrate DBH forward, grow structural tissues, update height via `h_allom`
- **Executed**: after all non-growth allocation is complete
- **Code**: `cohort%prt%DailyPRT(phase=3)` at `(main/EDMainMod.F90:601)`

This phased approach guarantees that storage is topped up before stature growth, and that a cohort recovered from crown damage has its target biomass pools updated before it attempts to grow. For the allocation hypotheses themselves, see [PARTEH: Plant Allocation System](../plant-physiology/parteh/index.md).

Sources: `(main/EDMainMod.F90:566-601)`

## Litter Flux Coordination

Litter fluxes are generated from several sources during the daily loop and must be coordinated so that each source is attributed to the correct (donor or spawned) patch.

- **Pre-disturbance litter**: maintenance turnover, leaf aging, and phase 1-3 allocation efflux are handled inside `ed_integrate_state_variables` via `EffluxIntoLitterPools` (`:608`).
- **Disturbance litter**: `spawn_patches` delegates distribution of existing and mortality-sourced litter to `TransLitterNewPatch` (`biogeochem/EDPatchDynamicsMod.F90:1387`), `mortality_litter_fluxes` (`:1870`), and `fire_litter_fluxes` (`:1631`), each using a localization parameter (see [Patch Dynamics](patch_dynamics.md)).
- **Logging litter**: handled in `EDLoggingMortalityMod` via `logging_litter_fluxes`.

Sources: `(biogeochem/EDPhysiologyMod.F90)`, `(main/EDMainMod.F90:190-194)`

## Configuration Flags Affecting Dynamics

Several runtime flags modify the daily dynamics sequence:

| Flag | Effect on Daily Loop | Reference |
| --- | --- | --- |
| `hlm_use_ed_st3` | Skip phenology, fire, disturbance, recruitment, patch dynamics; use `bypass_dynamics` | `(main/EDMainMod.F90:201-237)` |
| `hlm_use_sp` | Use satellite phenology instead of prognostic; skip fire, disturbance, patch dynamics | `(main/EDMainMod.F90:202-207)` |
| `hlm_use_ed_prescribed_phys` | Use prescribed NPP instead of calculated | `(main/EDMainMod.F90:489-503)` |
| `hlm_use_planthydro` | Enable hydraulic state updates | `(main/EDMainMod.F90:662-665)`, `(main/EDMainMod.F90:303-306)` |
| `hlm_use_cohort_age_tracking` | Track cohort age for age-dependent processes | `(main/EDMainMod.F90:668-678)` |
| `hlm_use_tree_damage` | Enable crown damage and `DamageRecovery` | `(main/EDMainMod.F90:587-599)` |

Sources: `(main/EDMainMod.F90:201-678)`

## Key Data Flow Summary

The daily dynamics loop orchestrates data flow through the model hierarchy:

- sub-daily GPP, respiration, and nutrient uptake accumulate into `cohort%gpp_acc`, `cohort%resp_acc`, `cohort%daily_n_gain`, etc.;
- `ed_integrate_state_variables` consumes those accumulators to drive PARTEH allocation, produces new DBH/height/n, and pushes site-level GPP and autotrophic respiration into `bc_out`;
- cohort management and patch dynamics reshape the linked lists;
- `TotalBalanceCheck` verifies that every daily flux landed in a bookkeeping slot.

Sources: `(main/EDMainMod.F90:141-766)`
