# Patch Dynamics and Disturbances

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

**Relevant source files:**
- `biogeochem/EDPatchDynamicsMod.F90`
- `biogeochem/EDLoggingMortalityMod.F90`
- `biogeochem/EDMortalityFunctionsMod.F90`
- `main/EDMainMod.F90`
- `main/EDTypesMod.F90`

## Purpose and Scope

This page documents the patch dynamics system in FATES, which simulates disturbance-driven vegetation succession. Patches represent areas of land with a common disturbance history and age, organized within a site. This module controls patch creation from disturbance, fusion of similar-aged patches, and termination of negligibly small patches.

For information about the underlying data structures (sites, patches, cohorts), see [Data Structures](data_structures.md). For fire-specific processes, see [Fire Dynamics: SPITFIRE](../fire/index.md). For logging details, see [Logging and Land Use](../logging/index.md). For the daily dynamics orchestration that calls these routines, see [Daily Dynamics Loop](daily_loop.md).

## Disturbance Types

FATES simulates three types of disturbances, each represented by a distinct disturbance type index imported from `FatesConstantsMod` at `(biogeochem/EDPatchDynamicsMod.F90:35-37)`:

| Disturbance type | Constant name | Source | Description |
| --- | --- | --- | --- |
| Treefall | `dtype_ifall` | Background mortality | Natural tree mortality in canopy layer creates gaps |
| Logging | `dtype_ilog` | Harvest events | Anthropogenic logging operations remove trees |
| Fire | `dtype_ifire` | SPITFIRE model | Fire burns vegetation and creates new patches |

Each patch tracks disturbance rates for all three types via `currentPatch%disturbance_rates(1:N_DIST_TYPES)`. These rates represent the fraction of patch area disturbed per day.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:35-37)`, `(main/EDTypesMod.F90)`

## Disturbance Rate Calculation

### Overview

The `disturbance_rates` subroutine (`biogeochem/EDPatchDynamicsMod.F90:160`) calculates how much of each patch's area will be disturbed by each disturbance type during the current day. It runs after mortality rates have been computed but before patches are spawned.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:160-394)`

### Treefall Disturbance

Treefall disturbance is calculated from the mortality rate (`dmort`) of canopy-layer cohorts. Only woody plants in the canopy layer contribute to treefall disturbance, determined by `ExemptTreefallDist()`. The parameter `fates_mortality_disturbance_fraction` (typically less than 1.0) represents the fraction of mortality that generates new patches versus non-disturbance mortality.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:305-309)`, `(biogeochem/EDMortalityFunctionsMod.F90:327-351)`

### Logging Disturbance

Logging disturbance combines multiple mortality components. Each cohort's logging mortality is calculated by `LoggingMortality_frac()` based on:

- DBH thresholds (`logging_dbhmin`, `logging_dbhmax`)
- Harvest rates from the host land model or FATES parameters
- Canopy layer position
- Patch `anthro_disturbance_label` (primary vs. secondary forest)

For non-closed canopy patches, additional area is added to account for interstitial ground area.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:311-353)`, `(biogeochem/EDLoggingMortalityMod.F90:198-346)`

### Fire Disturbance

Fire disturbance is calculated by the SPITFIRE model and stored in `currentPatch%frac_burnt`. SPITFIRE determines burned area based on fire danger, fuel characteristics, and fire spread calculations. See [Fire Dynamics: SPITFIRE](../fire/index.md) for details.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:367-368)`

### Disturbance Rate Normalization

If the sum of all disturbance rates exceeds 1.0 (that is, more area would be disturbed than exists), all rates are proportionally reduced. This ensures mass balance and prevents mathematical inconsistencies.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:383-388)`

## Patch Lifecycle

### Overview

Patches progress through a lifecycle of creation, aging, fusion, and termination. The age-ordered doubly linked list structure allows FATES to efficiently track patches from youngest to oldest using the `younger` and `older` pointers.

### Patch Creation: spawn_patches

The `spawn_patches()` subroutine creates new patches from disturbed area. It is called once per day for each disturbance type in sequence.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:398-1270)`

#### Primary vs. Secondary Forest Designation

When a new patch is created, its `anthro_disturbance_label` is determined from the disturbance type and the donor patch's label. Secondary patches track `age_since_anthro_disturbance`, which resets when logging occurs but continues to accumulate for natural disturbances.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:507-532)`

#### Litter Localization

When patches spawn, existing litter and litter from newly dead plants must be distributed between the new patch and the remaining donor patch. FATES uses "localization" parameters to control this distribution. A localization of 1.0 means all litter goes to the new patch. A localization of 0.0 means litter is distributed proportionally by the areas of the new and remaining donor patches.

| Source | Parameter | Value | Meaning |
| --- | --- | --- | --- |
| Pre-existing litter | `existing_litt_localization` | 1.0 | All stays with new patch |
| Treefall mortality | `treefall_localization` | 0.0 | Distributed by area |
| Fire mortality | `burn_localization` | 0.0 | Distributed by area |
| Logging mortality | `harvest_litter_localization` | 0.0 | Distributed by area |

Sources: `(biogeochem/EDPatchDynamicsMod.F90:146-148)`, `(biogeochem/EDLoggingMortalityMod.F90:79-89)`

#### Cohort Survivorship

During patch spawning, cohorts from the donor patch are copied to the new patch with modified number densities based on the disturbance type:

- **Treefall**: canopy-layer cohorts set `nc%n = 0` (all die — they created the disturbance); understory cohorts survive into the new patch.
- **Logging**: apply `lmort_direct`, `lmort_collateral`, and `lmort_infra` to reduce `n`; woody understory experiences `logging_coll_under_frac`.
- **Fire**: apply `fire_mort` calculated from cambial and crown scorch damage to both canopy and understory.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:726-848)`

### Patch Fusion: fuse_patches

The `fuse_patches()` subroutine merges patches that have become similar in age and size structure. This prevents the proliferation of many small patches and improves computational efficiency. Patch similarity is computed from the `patch_pft_size_profile` (binned biomass across PFT × size-class bins).

Sources: `(biogeochem/EDPatchDynamicsMod.F90:2103-2412)`

#### Fusion Criteria

Two patches can fuse if their PFT × size-class biomass profiles differ by less than a tolerance, and if they belong to the same `anthro_disturbance_label`. The tolerance is progressively relaxed until the patch count is below the target.

#### Forced Fusion

Fusion is forced (tolerance effectively set to 0) when the oldest patch's age exceeds `max_age_of_second_oldest_patch = 200 years` (see `main/EDTypesMod.F90:107`), or when patch biomass drops below `force_patchfuse_min_biomass = 0.005 kg/m²` (`main/EDTypesMod.F90:105`).

Sources: `(biogeochem/EDPatchDynamicsMod.F90:2103-2412)`, `(main/EDTypesMod.F90:104-110)`

#### Fusion Mechanics

When two patches fuse via `fuse_2_patches()` (`biogeochem/EDPatchDynamicsMod.F90:2413`), litter pools, seed pools, and running means are area-weighted; cohort lists are concatenated and re-sorted; and the fused patch inherits the older of the two ages. Localization parameters above are not re-applied at fusion time; they only govern the spawn-time distribution.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:2413-2609)`

### Patch Termination: terminate_patches

The `terminate_patches()` subroutine removes patches whose area has become too small to meaningfully track. This prevents numerical issues and computational waste.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:2610-2779)`

#### Termination Criteria

A patch is terminated when its area drops below `min_patch_area = 0.01 m²` (or `min_patch_area_forced = 0.0001 m²` for the protected youngest-patch case). The youngest patch receives special protection to ensure at least some representation of recent disturbances, unless its area is extremely small.

Sources: `(main/EDTypesMod.F90:115-123)`

#### Transfer of Mass and Cohorts

When a patch is terminated, its cohorts are moved to a neighboring patch (the next-older patch in most cases). Litter, seed bank, and other pool-level state are area-weighted and added to the receiving patch so that the total site mass balance is preserved.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:2610-2779)`

## Integration with Daily Dynamics

Patch dynamics are integrated into the daily timestep inside `ed_ecosystem_dynamics()` in the order: `spawn_patches` (`:292`) → `TotalBalanceCheck(3)` (`:294`) → `fuse_patches` (`:297`) → optional rhizosphere update → `TotalBalanceCheck(4)` (`:309`) → `terminate_patches` (`:312`) → `TotalBalanceCheck(5)` (`:315`).

Sources: `(main/EDMainMod.F90:279-315)`

### Patch Dynamics Control Flag

The local variable `do_patch_dynamics` (set at `main/EDMainMod.F90:284-288`) controls whether patch spawning, fusion, and termination occur. Patch dynamics are disabled in:

- **ST3 mode** (`hlm_use_ed_st3 == itrue`): ecosystem structure is prescribed from inventory
- **SP mode** (`hlm_use_sp == itrue`): satellite phenology mode with prescribed vegetation

Sources: `(main/EDMainMod.F90:283-288)`

## No-Competition Mode Considerations

When operating in no-competition mode (`hlm_use_nocomp == itrue`), each patch has a PFT identity (`nocomp_pft_label`). Patches are not shared across PFTs, and the fusion machinery keeps distinct PFT labels separate. This allows FATES to simulate multiple PFTs at the same location without inter-PFT competition, similar to running separate big-leaf models side by side.

Sources: `(biogeochem/EDPatchDynamicsMod.F90)`

## Diagnostic Outputs

Patch dynamics produce several site-level diagnostic outputs tracked for history files:

| Variable | Description | Units |
| --- | --- | --- |
| `disturbance_rates_primary_to_primary` | Natural disturbance creating new primary forest | m²/m²/day |
| `disturbance_rates_primary_to_secondary` | Logging or disturbance from primary to secondary | m²/m²/day |
| `disturbance_rates_secondary_to_secondary` | Disturbance within secondary forest | m²/m²/day |
| `potential_disturbance_rates` | Pre-normalized disturbance rates by type | m²/m²/day |
| `area_by_age` | Total patch area by age class | m² |

These diagnostics are populated during `disturbance_rates()` and `spawn_patches()`.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:160-530)`, `(main/EDTypesMod.F90)`

## Key Module Functions and Entry Points

| Function | File | Description |
| --- | --- | --- |
| `disturbance_rates()` | `biogeochem/EDPatchDynamicsMod.F90:160` | Calculate disturbance rates for all patches |
| `spawn_patches()` | `biogeochem/EDPatchDynamicsMod.F90:398` | Create new patches from disturbed area |
| `check_patch_area()` | `biogeochem/EDPatchDynamicsMod.F90:1272` | Validate site-level patch area closure |
| `set_patchno()` | `biogeochem/EDPatchDynamicsMod.F90:1344` | Assign sequential patch numbers |
| `TransLitterNewPatch()` | `biogeochem/EDPatchDynamicsMod.F90:1387` | Transfer existing litter during spawn |
| `fire_litter_fluxes()` | `biogeochem/EDPatchDynamicsMod.F90:1631` | Add litter from fire mortality |
| `mortality_litter_fluxes()` | `biogeochem/EDPatchDynamicsMod.F90:1870` | Add litter from treefall mortality |
| `fuse_patches()` | `biogeochem/EDPatchDynamicsMod.F90:2103` | Merge similar patches |
| `fuse_2_patches()` | `biogeochem/EDPatchDynamicsMod.F90:2413` | Merge two specific patches |
| `terminate_patches()` | `biogeochem/EDPatchDynamicsMod.F90:2610` | Remove patches with negligible area |
| `DistributeSeeds()` | `biogeochem/EDPatchDynamicsMod.F90:2780` | Apportion seed rain across patches |
| `patch_pft_size_profile()` | `biogeochem/EDPatchDynamicsMod.F90:2811` | Calculate patch similarity metric |
| `get_frac_site_primary()` | `biogeochem/EDPatchDynamicsMod.F90:2898` | Compute primary-forest area fraction |
| `logging_litter_fluxes()` | `biogeochem/EDLoggingMortalityMod.F90` | Add litter from logging mortality |

Sources: `(biogeochem/EDPatchDynamicsMod.F90:116-160)`
