# Patch Dynamics and Disturbances

---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

**Relevant source files:**
- `biogeochem/EDPatchDynamicsMod.F90`
- `biogeochem/EDLoggingMortalityMod.F90`
- `biogeochem/EDMortalityFunctionsMod.F90`
- `biogeochem/FatesLandUseChangeMod.F90`
- `main/EDMainMod.F90`
- `main/EDTypesMod.F90`
- `main/FatesConstantsMod.F90`

## Purpose and Scope

This page documents the patch dynamics system in FATES, which simulates disturbance-driven vegetation succession. Patches represent areas of land with a common disturbance history and age, organized within a site. This module controls patch creation from disturbance, fusion of similar-aged patches, and termination of negligibly small patches.

For information about the underlying data structures (sites, patches, cohorts), see [Data Structures](data_structures.md). For fire-specific processes, see [Fire Dynamics: SPITFIRE](../fire/index.md). For logging details, see [Logging and Land Use](../logging/index.md). For the daily dynamics orchestration that calls these routines, see [Daily Dynamics Loop](daily_loop.md).

## Disturbance Types

FATES simulates four types of disturbances at e027a40 (the prior 3-type set was extended with a fourth land-use change type). The disturbance type indices are imported from `FatesConstantsMod` at `(biogeochem/EDPatchDynamicsMod.F90:34-37)`:

| Disturbance type | Constant name | Index | Source | Description |
| --- | --- | --- | --- | --- |
| Treefall | `dtype_ifall` | 1 | Background mortality | Natural tree mortality in canopy layer creates gaps |
| Fire | `dtype_ifire` | 2 | SPITFIRE / `DailyFireModel` | Fire burns vegetation and creates new patches |
| Logging | `dtype_ilog` | 3 | Harvest events | Anthropogenic logging operations remove trees |
| Land-use change | `dtype_ilandusechange` | 4 | LUH state/transition data | Land-use transitions among primaryland, secondaryland, pastureland, rangeland, cropland |

The constant `N_DIST_TYPES = 4` is defined at `(main/FatesConstantsMod.F90:44)`. The 1-2-3 ordering of treefall/fire/logging at e027a40 differs from the 1-2-3 (treefall/logging/fire) ordering used in earlier versions; downstream code accesses by name, not by integer literal.

Each patch tracks disturbance rates for all four types via `currentPatch%disturbance_rates(1:N_DIST_TYPES)`. These rates represent the fraction of patch area disturbed per day.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:34-42)`, `(main/FatesConstantsMod.F90:44-47)`, `(biogeochem/FatesPatchMod.F90:203)`

## Disturbance Rate Calculation

### Overview

The `disturbance_rates` subroutine (`biogeochem/EDPatchDynamicsMod.F90:164`) calculates how much of each patch's area will be disturbed by each disturbance type during the current day. It runs after mortality rates have been computed but before patches are spawned.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:164-484)`

### Treefall Disturbance

Treefall disturbance is calculated from the mortality rate (`dmort`) of canopy-layer cohorts. Only woody plants in the canopy layer contribute to treefall disturbance, determined by `ExemptTreefallDist()`. The parameter `mortality_disturbance_fraction` (typically less than 1.0) represents the fraction of mortality that generates new patches versus non-disturbance mortality. The contribution per cohort is added at `(biogeochem/EDPatchDynamicsMod.F90:366-368)`.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:362-369)`, `(biogeochem/EDMortalityFunctionsMod.F90)`

### Logging Disturbance

Logging disturbance combines multiple mortality components. Each cohort's logging mortality is calculated by `LoggingMortality_frac()` based on:

- DBH thresholds (`logging_dbhmin`, `logging_dbhmax`)
- Harvest rates from the host land model or FATES parameters
- Canopy layer position
- Patch `land_use_label` (primaryland, secondaryland, pastureland, rangeland, cropland)

For non-closed canopy patches, additional area is added to account for interstitial ground area subject to logging. The cohort-level contribution is added at `(biogeochem/EDPatchDynamicsMod.F90:372-377)`; the interstitial-area branch begins near `(:394)`.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:372-432)`, `(biogeochem/EDLoggingMortalityMod.F90)`

### Fire Disturbance

Fire disturbance is calculated by the SPITFIRE model (now invoked from EDMainMod via `DailyFireModel`) and stored in `currentPatch%frac_burnt`. SPITFIRE determines burned area based on fire danger, fuel characteristics, and fire spread calculations. See [Fire Dynamics: SPITFIRE](../fire/index.md) for details. The fire contribution to `disturbance_rates(dtype_ifire)` is set inside `disturbance_rates`.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:436-442)` (verified within `disturbance_rates`), `(fire/SFMainMod.F90:46-69)`

### Land-Use Change Disturbance

When `hlm_use_luh == itrue`, land-use change rates are read from LUH state and transition data via `GetLUHStatedata` and `GetLanduseTransitionRates`. Rates are stored on the patch as `landuse_transition_rates(1:n_landuse_cats)` and contribute to `disturbance_rates(dtype_ilandusechange)`. The state-vector to per-patch conversion happens at `(biogeochem/EDPatchDynamicsMod.F90:350-357)`.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:325-357)`, `(biogeochem/FatesLandUseChangeMod.F90)`

### Disturbance Rate Normalization

If the sum of all disturbance rates exceeds 1.0 (that is, more area would be disturbed than exists), all rates are proportionally reduced. This ensures mass balance and prevents mathematical inconsistencies. Logging rates are individually clamped to a per-cohort cap of 1.0 at `(biogeochem/EDPatchDynamicsMod.F90:373)`; the per-patch normalization happens later inside `disturbance_rates` before patch spawning.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:164-484)`

## Patch Lifecycle

### Overview

Patches progress through a lifecycle of creation, aging, fusion, and termination. The age-ordered doubly linked list structure allows FATES to efficiently track patches from youngest to oldest using the `younger` and `older` pointers.

### Patch Creation: spawn_patches

The `spawn_patches()` subroutine creates new patches from disturbed area. It is called once per day for each disturbance type in sequence.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:488-1708)`

#### Primary vs. Secondary Forest Designation

When a new patch is created, its `land_use_label` is determined from the disturbance type and the donor patch's label. Secondary patches track `age_since_anthro_disturbance`, which resets when logging or land-use change occurs but continues to accumulate for natural disturbances. The `land_use_label` field replaced the prior `anthro_disturbance_label` field as part of the LUH integration. Recognized labels are `primaryland`, `secondaryland`, `pastureland`, `rangeland`, `cropland`, plus the special `nocomp_bareground_land` (`main/FatesConstantsMod.F90`).

Sources: `(biogeochem/EDPatchDynamicsMod.F90:488-1708)`, `(biogeochem/FatesPatchMod.F90:92-93)`

#### Litter Localization

When patches spawn, existing litter and litter from newly dead plants must be distributed between the new patch and the remaining donor patch. FATES uses "localization" parameters to control this distribution. A localization of 1.0 means all litter goes to the new patch. A localization of 0.0 means litter is distributed proportionally by the areas of the new and remaining donor patches.

| Source | Parameter | Value | Meaning | Definition |
| --- | --- | --- | --- | --- |
| Pre-existing litter | `existing_litt_localization` | 1.0 | All stays with new patch | `(biogeochem/EDPatchDynamicsMod.F90:149)` |
| Treefall mortality | `treefall_localization` | 0.0 | Distributed by area | `(biogeochem/EDPatchDynamicsMod.F90:150)` |
| Fire mortality | `burn_localization` | 0.0 | Distributed by area | `(biogeochem/EDPatchDynamicsMod.F90:151)` |
| Logging mortality | `harvest_litter_localization` | 0.0 | Distributed by area | `(biogeochem/EDLoggingMortalityMod.F90:99)` |

The `retain_frac = (1.0 - localization)` formula is applied at `(biogeochem/EDPatchDynamicsMod.F90:2035)` for existing litter, `(:2241)` for fire mortality, `(:2453)` for treefall mortality, and `(biogeochem/EDLoggingMortalityMod.F90:870)` for harvest litter.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:149-151)`, `(biogeochem/EDLoggingMortalityMod.F90:99)`

#### Cohort Survivorship

During patch spawning, cohorts from the donor patch are copied to the new patch with modified number densities based on the disturbance type:

- **Treefall**: canopy-layer cohorts set `nc%n = 0` (all die — they created the disturbance); understory cohorts survive into the new patch.
- **Logging**: apply `lmort_direct`, `lmort_collateral`, and `lmort_infra` to reduce `n`; woody understory experiences `logging_coll_under_frac`.
- **Fire**: apply `fire_mort` calculated from cambial and crown scorch damage to both canopy and understory.
- **Land-use change**: cohort survivorship follows the per-transition rules in `FatesLandUseChangeMod`.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:488-1708)`

### Patch Fusion: fuse_patches

The `fuse_patches()` subroutine merges patches that have become similar in age and size structure. This prevents the proliferation of many small patches and improves computational efficiency. Patch similarity is computed from the `patch_pft_size_profile` (binned biomass across PFT × size-class bins).

Sources: `(biogeochem/EDPatchDynamicsMod.F90:2882-3193)`

#### Fusion Criteria

Two patches can fuse if their PFT × size-class biomass profiles differ by less than a tolerance, and if they belong to the same `land_use_label`. The tolerance is progressively relaxed until the patch count is below the target.

#### Forced Fusion

Fusion is forced (tolerance effectively set to 0) when the oldest patch's age exceeds `max_age_of_second_oldest_patch = 200 years` (see `main/EDTypesMod.F90:112`), or when patch biomass drops below `force_patchfuse_min_biomass = 0.005 kg/m²` (`main/EDTypesMod.F90:110`).

Sources: `(biogeochem/EDPatchDynamicsMod.F90:2882-3193)`, `(main/EDTypesMod.F90:108-128)`

#### Fusion Mechanics

When two patches fuse via `fuse_2_patches()` (`biogeochem/EDPatchDynamicsMod.F90:3197`), litter pools, seed pools, and running means are area-weighted; cohort lists are concatenated and re-sorted; and the fused patch inherits the older of the two ages. Localization parameters above are not re-applied at fusion time; they only govern the spawn-time distribution.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:3197-3365)`

### Patch Termination: terminate_patches

The `terminate_patches()` subroutine removes patches whose area has become too small to meaningfully track. This prevents numerical issues and computational waste.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:3369-3633)`

#### Termination Criteria

A patch is terminated when its area drops below `min_patch_area = 0.01 m²` (or `min_patch_area_forced = 0.0001 m²` for the protected youngest-patch case). The youngest patch receives special protection to ensure at least some representation of recent disturbances, unless its area is extremely small.

Thresholds are defined at `(main/EDTypesMod.F90:110-128)`.

#### Transfer of Mass and Cohorts

When a patch is terminated, its cohorts are moved to a neighboring patch (the next-older patch in most cases). Litter, seed bank, and other pool-level state are area-weighted and added to the receiving patch so that the total site mass balance is preserved.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:3369-3633)`

## Integration with Daily Dynamics

Patch dynamics are integrated into the daily timestep inside `ed_ecosystem_dynamics()` in the order: `spawn_patches` (`:305`) → `TotalBalanceCheck(3)` (`:307`) → `fuse_patches` (`:310`) → optional rhizosphere update `UpdateSizeDepRhizHydProps` (`:317`) → `TotalBalanceCheck(4)` (`:322`) → `terminate_patches` (`:325`) → `TotalBalanceCheck(5)` (`:329`).

Sources: `(main/EDMainMod.F90:291-329)`

### Patch Dynamics Control Flag

The local variable `do_patch_dynamics` (set at `main/EDMainMod.F90:296-300`) controls whether patch spawning, fusion, and termination occur. Patch dynamics are disabled in:

- **ST3 mode** (`hlm_use_ed_st3 == itrue`): ecosystem structure is prescribed from inventory
- **SP mode** (`hlm_use_sp == itrue`): satellite phenology mode with prescribed vegetation

Sources: `(main/EDMainMod.F90:296-300)`

## No-Competition Mode Considerations

When operating in no-competition mode (`hlm_use_nocomp == itrue`), each patch has a PFT identity (`nocomp_pft_label`). Patches are not shared across PFTs, and the fusion machinery keeps distinct PFT labels separate. This allows FATES to simulate multiple PFTs at the same location without inter-PFT competition. A dedicated bareground PFT label (`nocomp_bareground`) keeps a bareground patch present at all times so the fire model can be skipped if it is the only patch.

Sources: `(biogeochem/EDPatchDynamicsMod.F90)`, `(main/EDMainMod.F90:215-225)`

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

Sources: `(biogeochem/EDPatchDynamicsMod.F90:164-1708)`, `(main/EDTypesMod.F90)`

## Key Module Functions and Entry Points

| Function | File | Description |
| --- | --- | --- |
| `disturbance_rates()` | `biogeochem/EDPatchDynamicsMod.F90:164` | Calculate disturbance rates for all patches |
| `spawn_patches()` | `biogeochem/EDPatchDynamicsMod.F90:488` | Create new patches from disturbed area |
| `split_patch()` | `biogeochem/EDPatchDynamicsMod.F90:1712` | Helper that splits a donor patch and returns the new patch |
| `check_patch_area()` | `biogeochem/EDPatchDynamicsMod.F90:1810` | Validate site-level patch area closure |
| `set_patchno()` | `main/EDTypesMod.F90:617` | Assign sequential patch numbers (imported by EDPatchDynamicsMod at `:25`) |
| `TransLitterNewPatch()` | `biogeochem/EDPatchDynamicsMod.F90:1890` | Transfer existing litter during spawn |
| `fire_litter_fluxes()` | `biogeochem/EDPatchDynamicsMod.F90:2154` | Add litter from fire mortality |
| `mortality_litter_fluxes()` | `biogeochem/EDPatchDynamicsMod.F90:2393` | Add litter from treefall mortality |
| `landusechange_litter_fluxes()` | `biogeochem/EDPatchDynamicsMod.F90:2626` | Add litter from land-use change |
| `fuse_patches()` | `biogeochem/EDPatchDynamicsMod.F90:2882` | Merge similar patches |
| `fuse_2_patches()` | `biogeochem/EDPatchDynamicsMod.F90:3197` | Merge two specific patches |
| `terminate_patches()` | `biogeochem/EDPatchDynamicsMod.F90:3369` | Remove patches with negligible area |
| `DistributeSeeds()` | `biogeochem/EDPatchDynamicsMod.F90:3637` | Apportion seed rain across patches |
| `patch_pft_size_profile()` | `biogeochem/EDPatchDynamicsMod.F90:3664` | Calculate patch similarity metric |
| `countPatches()` | `biogeochem/EDPatchDynamicsMod.F90:3719` | Count patches per site |
| `InsertPatch()` | `biogeochem/EDPatchDynamicsMod.F90:3751` | Insert patch into age-ordered list |
| `GetPseudoPatchAge()` | `biogeochem/EDPatchDynamicsMod.F90:3843` | Compute pseudo-age for fusion comparisons |
| `logging_litter_fluxes()` | `biogeochem/EDLoggingMortalityMod.F90` | Add litter from logging mortality |

Note: `set_patchno` lives in `main/EDTypesMod.F90` (declared near `:617`) and is imported by `EDPatchDynamicsMod` at `:25`. Cite the EDTypesMod path when referring to its definition; cite EDPatchDynamicsMod call sites at `:1401` and `:3630` for typical usage.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:1-3895)`, `(main/EDTypesMod.F90:617)`
