# Daily Dynamics Loop

---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

**Relevant source files:**
- `main/EDMainMod.F90`
- `biogeochem/EDPhysiologyMod.F90`
- `biogeochem/EDCohortDynamicsMod.F90`
- `biogeochem/EDPatchDynamicsMod.F90`
- `biogeochem/EDMortalityFunctionsMod.F90`
- `biogeochem/EDLoggingMortalityMod.F90`
- `biogeochem/FatesAllometryMod.F90`
- `biogeochem/FatesPatchMod.F90`
- `biogeochem/FatesSoilBGCFluxMod.F90`
- `biogeochem/FatesLandUseChangeMod.F90`
- `fire/SFMainMod.F90`

This page describes the daily timestep orchestration in FATES, including the main sequence of operations executed each day, mass balance verification, and the coordination between different physiological and ecological processes.

For individual processes called during this loop (phenology, recruitment, mortality), see: [Phenology and Leaf Dynamics](../plant-physiology/phenology.md), [Recruitment](cohort_lifecycle.md), [Mortality Processes](../plant-physiology/mortality.md), [PARTEH Allocation](../plant-physiology/parteh/index.md), [Patch Dynamics](patch_dynamics.md). For the data structures traversed, see [Data Structures](data_structures.md).

## Overview and Entry Point

The daily dynamics loop is executed through the `ed_ecosystem_dynamics` subroutine in `main/EDMainMod.F90:148-332`. This routine is called once per day from the host land model and coordinates all vegetation dynamics, including growth, mortality, herbivory, disturbance, and biogeochemistry. It operates on a single site (`ed_site_type`) and exchanges information with the host model through boundary condition types (`bc_in_type`, `bc_out_type`).

### Key Design Principles

- Vegetation demography and disturbance are updated at a daily cadence; photosynthesis and respiration accumulate between calls and are consumed once per day.
- Mass balance is verified at six numbered checkpoints (`TotalBalanceCheck(0..5)`).
- Patch and cohort lists are maintained as age- and height-ordered doubly linked lists so that insertion, fusion, and termination are local operations.
- Maintenance, growth, and excess respiration are accounted in independent cohort fields (`resp_m_acc/_hold`, `resp_g_acc_hold`, `resp_excess_hold`) rather than a single combined `resp_acc`.

## Main Dynamics Sequence

The following table captures the full sequence of calls inside `ed_ecosystem_dynamics`. Line numbers refer to `main/EDMainMod.F90` at commit e027a40 and were verified against source.

| Step | Operation | Source line | Notes |
| --- | --- | --- | --- |
| 1 | Zero per-element `mass_balance%ZeroMassBalFlux()` and `flux_diags%ZeroFluxDiags()` | 171-174 | one per element (C, N, P) |
| 2 | `IsItLoggingTime`, `IsItDamageTime` | 179, 182 | global event flags |
| 3 | `ZeroAllocationRates(currentSite)` | 192 | clear per-day growth/turnover |
| 4 | `ZeroLitterFluxes(currentSite)` | 195 | clear litter input/output |
| 5 | `ZeroBCOutCarbonFluxes(bc_out)` | 198 | clear bc_out carbon flux diagnostics |
| 6 | `TotalBalanceCheck(currentSite, 0)` | 201 | record initial stocks |
| 7 | `phenology` or `satellite_phenology` | 208-210 | skipped in ST3 mode |
| 8 | `DailyFireModel(currentSite, bc_in)` | 224 | only if not ST3/SP and the youngest patch is not bareground |
| 9 | `disturbance_rates(currentSite, bc_in)` | 229 | only if not ST3/SP |
| 10 | `ed_integrate_state_variables(currentSite, bc_in, bc_out)` | 232 | daily cohort growth, allocation, post-cohort housekeeping |
| 11 | `bypass_dynamics(currentSite, bc_out)` (ST3/SP branch) | 246 | housekeeping-only path |
| 12 | `recruitment(currentSite, currentPatch, bc_in)` (per patch) | 259 | only if not ST3/SP |
| 13 | `TotalBalanceCheck(currentSite, 1)` | 266 | verify recruitment conservation |
| 14 | `currentPatch%SortCohorts()` (per patch) | 272 | type-bound method, reorder by height |
| 15 | `terminate_cohorts(..., level=1, ...)` | 275 | remove numerically unstable cohorts |
| 16 | `fuse_cohorts(currentSite, currentPatch, bc_in)` | 278 | merge similar cohorts |
| 17 | `terminate_cohorts(..., level=2, ...)` | 281 | remove small/depleted cohorts |
| 18 | `TotalBalanceCheck(currentSite, 2)` | 289 | verify cohort management |
| 19 | `spawn_patches(currentSite, bc_in)` | 305 | gated by `do_patch_dynamics` |
| 20 | `TotalBalanceCheck(currentSite, 3)` | 307 | verify disturbance transfers |
| 21 | `fuse_patches(currentSite, bc_in)` | 310 | merge similar patches |
| 22 | `UpdateSizeDepRhizHydProps(currentSite, bc_in)` | 317 | only if `hlm_use_planthydro` and `do_growthrecruiteffects` |
| 23 | `TotalBalanceCheck(currentSite, 4)` | 322 | verify patch fusion |
| 24 | `terminate_patches(currentSite, bc_in)` | 325 | remove small patches |
| 25 | `TotalBalanceCheck(currentSite, 5)` | 329 | final verification |

There are 25 numbered steps above; counting `IsItDamageTime` separately from `IsItLoggingTime` brings the routine to 26 distinct action calls (from 25 in e85d997). The main structural additions versus e85d997 are step 5 (`ZeroBCOutCarbonFluxes`), the rename of `fire_model` to `DailyFireModel`, and the conversion of `sort_cohorts` from a free subroutine call to the type-bound method `currentPatch%SortCohorts()`.

Sources: `(main/EDMainMod.F90:148-332)`

## State Integration: The Core Growth Loop

The `ed_integrate_state_variables` subroutine (`main/EDMainMod.F90:335-810`) contains the cohort-level loop where state variables are updated, plus a substantial sequence of post-cohort-loop housekeeping. The cohort loop is nested inside an outer loop that walks patches from `oldest_patch` to `youngest_patch`; within each patch, cohorts are visited from `shortest` up to `taller`.

Above the patch loop, `UpdateRecruitStoich(currentSite)` is called (`:442`) to set new-recruit stoichiometry before the growth sequence. `currentPatch%age` is advanced by `hlm_freq_day` (`:447`); the secondary-forest age clock `age_since_anthro_disturbance` is advanced for non-primary patches (`:456-458`); and the patch age class is reassigned (`:462`).

### Cohort State Update Sequence

Within each cohort iteration, the following state updates occur (line numbers verified against source):

| Step | Function/Operation | Purpose | Code reference |
| --- | --- | --- | --- |
| 1 | `Mortality_Derivative(...)` | Calculate mortality rates (background, hydraulic, carbon starvation, logging, fire, freezing, senescence, age senescence, damage) | `(main/EDMainMod.F90:488)`, subroutine at `(biogeochem/EDMortalityFunctionsMod.F90:289)` |
| 2 | Store NPP/GPP/maintenance respiration into `_acc_hold`; compute `resp_g_acc_hold` from `prt_params%grperc(ft)` and recompute `npp_acc`/`npp_acc_hold` | Save accumulated photosynthesis values for diagnostics; account growth respiration as a tax on (GPP - maintenance respiration) | `(main/EDMainMod.F90:533-554)` |
| 3 | `FatesGrazing(currentCohort%prt, ft, currentPatch%land_use_label, currentCohort%height)` | Apply herbivore grazing to PARTEH organs (per-cohort, every day) | `(main/EDMainMod.F90:558)` |
| 4 | `PRTMaintTurnover(currentCohort%prt, ft, currentCohort%canopy_layer, is_drought)` | Apply maintenance turnover to all organs; gained `canopy_layer` argument | `(main/EDMainMod.F90:568)` |
| 5 | `currentCohort%prt%AgeLeaves(ft, currentCohort%canopy_layer, sec_per_day)` | Advance leaf age classes; gained `canopy_layer` argument | `(main/EDMainMod.F90:576)` |
| 6 | Compute `daily_n_gain = daily_nh4_uptake + daily_no3_uptake + sym_nfix_daily`; zero `resp_excess_hold` | Aggregate daily N inputs; reset excess-respiration accumulator | `(main/EDMainMod.F90:583-586)` |
| 7 | `EvaluateAndCorrectDBH(currentCohort, delta_dbh, delta_height)` | Ensure DBH is consistent with structural biomass | `(main/EDMainMod.F90:593)` |
| 8 | `currentCohort%prt%DailyPRT(phase=1)` | Prioritized allocation (turnover replacement, storage replenishment); skipped for newly recovered cohorts | `(main/EDMainMod.F90:615)` |
| 9 | `currentCohort%prt%DailyPRT(phase=2)` | Non-stature allocation for all cohorts (updated targets after damage recovery) | `(main/EDMainMod.F90:618)` |
| 10 | `DamageRecovery(currentSite, currentPatch, currentCohort, newly_recovered)` | Create recovered cohort clone if crown damage recovery applies | `(main/EDMainMod.F90:628)` |
| 11 | `currentCohort%prt%DailyPRT(phase=3)` | Stature growth using remaining carbon | `(main/EDMainMod.F90:634)` |
| 12 | Subtract `resp_excess_hold * days_per_year` from `npp_acc_hold` | Account excess respiration from nutrient limitation | `(main/EDMainMod.F90:644-645)` |
| 13 | `EffluxIntoLitterPools(currentSite, currentPatch, currentCohort, bc_in)` | Transfer nutrient efflux to litter | `(main/EDMainMod.F90:651)`; subroutine at `(biogeochem/FatesSoilBGCFluxMod.F90:544)` |
| 14 | Add per-cohort N/P/C uptake terms to `currentSite%mass_balance(...)%net_root_uptake`; add cohort GPP and total respiration to site `gpp_acc`/`aresp_acc` | Mass balance accounting | `(main/EDMainMod.F90:653-678)` |
| 15 | `currentCohort%UpdateCohortBioPhysRates()` | Recalculate vcmax25top, jmax25top from leaf age distribution | `(main/EDMainMod.F90:686)` |
| 16 | `h_allom(currentCohort%dbh, ft, currentCohort%height)` | Update height from new DBH via allometry | `(main/EDMainMod.F90:692)` |
| 17 | Compute `dhdt` and `ddbhdt` | Growth rate diagnostics | `(main/EDMainMod.F90:694-695)` |
| 18 | Zero `npp_acc`, `gpp_acc`, `resp_m_acc` | Reset accumulators for next dynamics step | `(main/EDMainMod.F90:700-702)` |
| 19 | `UpdateSizeDepPlantHydProps` and `UpdateSizeDepPlantHydStates` | Update hydraulic geometry (if `hlm_use_planthydro`) | `(main/EDMainMod.F90:707-710)` |
| 20 | Increment `coage`, recalculate cohort age class (if `hlm_use_cohort_age_tracking`) | Cohort age tracking | `(main/EDMainMod.F90:713-724)` |

Note the API changes vs e85d997: `PRTMaintTurnover` (step 4) and `AgeLeaves` (step 5) both gained a `canopy_layer` argument, and the per-cohort respiration was split into separate `resp_m_*` and `resp_g_acc_hold` accumulators. The single-field `resp_acc`/`resp_acc_hold` from earlier versions no longer exists.

### Post-Cohort-Loop Housekeeping

After all cohorts in all patches have been visited, `ed_integrate_state_variables` performs additional work that is not part of the cohort growth loop. The wiki at e85d997 omitted these blocks; they exist at e027a40 and update site-level state required for litter, seed, and mass-balance accounting:

| Block | Source line | Purpose |
| --- | --- | --- |
| `UpdateRecruitL2FR(currentSite)` | 737 | Update site-level running mean L2FR for new recruits, by PFT and canopy layer |
| CNP nutrient flux history (when `hlm_parteh_mode == prt_cnp_flex_allom_hyp`) | 741-744 | `fates_hist%update_history_nutrflux(currentSite)` |
| `AccumulateMortalityWaterStorage` (per cohort, when `hlm_use_planthydro == itrue`) | 750-761 | Walk all cohorts and accumulate water lost via `dndt`-driven mortality |
| `SeedUpdate(currentSite)` | 768 | Cross-patch seed-rain mixing |
| Per-patch litter loop: `GenerateDamageAndLitterFluxes`, `PreDisturbanceLitterFluxes`, `PreDisturbanceIntegrateLitter` | 773-783 | Build pre-disturbance litter inputs from each patch |
| `FluxIntoLitterPools(currentSite, bc_in, bc_out)` | 790 | Push patch-level litter into the BGC interface |
| Final cohort number update: `currentCohort%n = max(0, n + dndt * hlm_freq_day)`, then `sym_nfix_daily = 0` | 797-806 | Integrate cohort number from mortality rate; zero daily symbiotic N fixation |

The integrate-state-variables routine therefore handles the recruit L2FR feedback, CNP nutrient diagnostics, plant-hydraulics water-mortality bookkeeping, seed mixing, all pre-disturbance litter generation, and the actual integration of cohort number from mortality rates, in addition to the per-cohort growth loop.

Sources: `(main/EDMainMod.F90:442-810)`

## Mass Balance Verification

`TotalBalanceCheck` (`main/EDMainMod.F90:928-1127`) compares stock changes against the sum of tracked input and output fluxes for each element. The comparison uses a site-level tolerance, and failures abort the simulation. The routine signature gained an optional `is_restarting` argument so that the restart-init path can suppress flux accounting:

```fortran
subroutine TotalBalanceCheck(currentSite, call_index, is_restarting)
```

### Balance Check Components

The mass balance verification tracks the following pools and fluxes at the site level (carbon always; nitrogen and phosphorus when CNP is active):

- **Standing stocks**: vegetation biomass (leaf, root, sapwood, structure, storage, reproductive), litter pools (CWD, fine litter), seed bank
- **Input fluxes**: GPP, external seed rain
- **Output fluxes**: autotrophic respiration, fragmentation to soil, seed decay/germination
- **Lateral fluxes**: root uptake (for CNP mode, includes N and P tracking)

The six numbered checkpoints frame the loop: checkpoint 0 records the initial state, 1 confirms recruitment conservation, 2 confirms cohort fusion/termination, 3 confirms patch spawning, 4 confirms patch fusion and hydraulic updates, and 5 is the final closing check.

Sources: `(main/EDMainMod.F90:201-329)`, `(main/EDMainMod.F90:928-1127)`

## Bypass Mode for Non-Dynamic Simulations

When operating in ST3 (static stand structure) mode or SP (satellite phenology) mode, many of the steps above are skipped. In ST3 mode `bypass_dynamics` is called in lieu of `ed_integrate_state_variables`; it does the minimum required housekeeping. For each cohort it marks `isnew=.false.`, derives `resp_g_acc_hold` from `prt_params%grperc * max(0, gpp_acc - resp_m_acc) * days_per_year`, copies the `_acc` accumulators into their `_acc_hold` siblings, zeros `resp_excess_hold`, zeros all mortality components (`bmort/hmort/cmort/frmort/smort/asmort/dgmort`) and the rate diagnostics (`dndt/dhdt/ddbhdt`), and resets `npp_acc/gpp_acc/resp_m_acc` to zero. Site-level `bc_out%gpp_site` and `bc_out%ar_site` are set to zero before the patch walk.

Sources: `(main/EDMainMod.F90:215-248)`, `(main/EDMainMod.F90:1131-1196)`

## PARTEH Three-Phase Allocation

The daily allocation within `ed_integrate_state_variables` uses a three-phase approach to prioritize different allocation targets.

### Phase 1: Prioritized Allocation

- **Purpose**: essential maintenance and deficit correction
- **Operations**: replacement of turnover losses, replenishment of depleted storage
- **Executed**: once per day, only for non-recovered cohorts
- **Code**: `currentCohort%prt%DailyPRT(phase=1)` at `(main/EDMainMod.F90:615)`

### Phase 2: Non-Stature Allocation

- **Purpose**: update allocation targets without growing stature
- **Operations**: adjust leaf/root targets after damage recovery, maintain allometric ratios
- **Executed**: for all cohorts including newly recovered clones created in `DamageRecovery`
- **Code**: `currentCohort%prt%DailyPRT(phase=2)` at `(main/EDMainMod.F90:618)`

### Phase 3: Stature Growth

- **Purpose**: diameter and height growth using surplus carbon
- **Operations**: integrate DBH forward, grow structural tissues, update height via `h_allom`
- **Executed**: after all non-growth allocation is complete
- **Code**: `currentCohort%prt%DailyPRT(phase=3)` at `(main/EDMainMod.F90:634)`

This phased approach guarantees that storage is topped up before stature growth, and that a cohort recovered from crown damage has its target biomass pools updated before it attempts to grow. For the allocation hypotheses themselves, see [PARTEH: Plant Allocation System](../plant-physiology/parteh/index.md).

Sources: `(main/EDMainMod.F90:599-645)`

## Litter Flux Coordination

Litter fluxes are generated from several sources during the daily loop and must be coordinated so that each source is attributed to the correct (donor or spawned) patch.

- **Per-cohort nutrient efflux** during the cohort loop: `EffluxIntoLitterPools` (`main/EDMainMod.F90:651`; subroutine at `biogeochem/FatesSoilBGCFluxMod.F90:544`).
- **Pre-disturbance litter generation** in the post-cohort loop: `GenerateDamageAndLitterFluxes`, `PreDisturbanceLitterFluxes`, and `PreDisturbanceIntegrateLitter` are called per patch at `main/EDMainMod.F90:776-780`, then `FluxIntoLitterPools` (`biogeochem/FatesSoilBGCFluxMod.F90:609`) pushes the patch-level totals into the BGC interface at `main/EDMainMod.F90:790`.
- **Disturbance litter**: `spawn_patches` delegates distribution of existing and mortality-sourced litter to `TransLitterNewPatch` (`biogeochem/EDPatchDynamicsMod.F90:1890`), `mortality_litter_fluxes` (`:2393`), `fire_litter_fluxes` (`:2154`), and `landusechange_litter_fluxes` (`:2626`), each using a localization parameter (see [Patch Dynamics](patch_dynamics.md)).
- **Logging litter**: handled in `EDLoggingMortalityMod` via `logging_litter_fluxes`.

Sources: `(main/EDMainMod.F90:651-790)`, `(biogeochem/FatesSoilBGCFluxMod.F90:544-947)`, `(biogeochem/EDPatchDynamicsMod.F90:1890-2878)`

## Configuration Flags Affecting Dynamics

Several runtime flags modify the daily dynamics sequence:

| Flag | Effect on Daily Loop | Reference |
| --- | --- | --- |
| `hlm_use_ed_st3` | Skip phenology, fire, disturbance, recruitment, patch dynamics; use `bypass_dynamics` | `(main/EDMainMod.F90:206-248)` |
| `hlm_use_sp` | Use satellite phenology instead of prognostic; skip fire, disturbance, patch dynamics | `(main/EDMainMod.F90:207-211)` |
| `hlm_use_ed_prescribed_phys` | Use prescribed NPP instead of calculated | `(main/EDMainMod.F90:505-519, 538-547)` |
| `hlm_use_planthydro` | Enable hydraulic state updates | `(main/EDMainMod.F90:316-319, 707-710, 750-761)` |
| `hlm_use_cohort_age_tracking` | Track cohort age for age-dependent processes | `(main/EDMainMod.F90:713-724)` |
| `hlm_use_tree_damage` | Enable crown damage and `DamageRecovery` | `(main/EDMainMod.F90:620-632)` |

Sources: `(main/EDMainMod.F90:206-724)`

## Key Data Flow Summary

The daily dynamics loop orchestrates data flow through the model hierarchy:

- sub-daily GPP, respiration, and nutrient uptake accumulate into `cohort%gpp_acc`, `cohort%resp_m_acc`, `cohort%daily_nh4_uptake`, `cohort%daily_no3_uptake`, `cohort%sym_nfix_daily`, etc.;
- `ed_integrate_state_variables` consumes those accumulators to drive PARTEH allocation, produces new DBH/height, and pushes site-level GPP and autotrophic respiration into the site mass-balance state;
- the post-cohort-loop housekeeping integrates cohort number from `dndt`, generates pre-disturbance litter, mixes seeds across patches, and pushes litter fluxes into `bc_out`;
- cohort management and patch dynamics reshape the linked lists;
- `TotalBalanceCheck` verifies that every daily flux landed in a bookkeeping slot.

Sources: `(main/EDMainMod.F90:148-810)`
