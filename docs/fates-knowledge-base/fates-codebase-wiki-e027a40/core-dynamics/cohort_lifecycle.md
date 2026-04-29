# Cohort Lifecycle Management

---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

**Relevant source files:**
- `biogeochem/EDCohortDynamicsMod.F90`
- `biogeochem/EDPhysiologyMod.F90`
- `biogeochem/EDPatchDynamicsMod.F90`
- `biogeochem/FatesCohortMod.F90`
- `biogeochem/FatesPatchMod.F90`
- `biogeochem/FatesAllometryMod.F90`
- `main/EDTypesMod.F90`

## Purpose and Scope

This page documents the cohort lifecycle management system in FATES, covering how cohorts are created, recruited, fused, terminated, and organized within patches. Cohorts are the fundamental unit of vegetation organization in FATES, representing groups of similar-sized plants of the same PFT within a patch.

For information about patch-level dynamics and disturbances that create and destroy patches, see [Patch Dynamics and Disturbances](patch_dynamics.md). For details on the hierarchical data structures containing cohorts, see [Data Structures](data_structures.md). For allocation and growth processes that change cohort biomass, see [PARTEH: Plant Allocation System](../plant-physiology/parteh/index.md).

## Cohort Lifecycle Overview

Cohorts undergo a complete lifecycle from creation through growth, potential fusion with similar cohorts, and eventual termination. The lifecycle involves several key processes orchestrated during the daily dynamics loop.

- **Creation**: `create_cohort` at `(biogeochem/EDCohortDynamicsMod.F90:123)`
- **Termination (three levels)**: `terminate_cohorts` at `(biogeochem/EDCohortDynamicsMod.F90:283)`, `terminate_cohort` at `(biogeochem/EDCohortDynamicsMod.F90:413)`
- **Fusion**: `fuse_cohorts` at `(biogeochem/EDCohortDynamicsMod.F90:648)`

Sources: `(biogeochem/EDCohortDynamicsMod.F90:123-226)`, `(biogeochem/EDCohortDynamicsMod.F90:283-512)`, `(biogeochem/EDCohortDynamicsMod.F90:648-1232)`

## Cohort Data Structure and Organization

Cohorts are organized within patches using doubly-linked lists sorted by height. Each cohort points to its taller and shorter neighbors (`taller`, `shorter`). The patch holds head and tail pointers (`tallest`, `shortest`) that bound the list.

Sources: `(biogeochem/FatesCohortMod.F90:60-130)`, `(biogeochem/FatesPatchMod.F90:60-150)`, `(main/EDTypesMod.F90:325-435)`

## Cohort Creation Mechanisms

Cohorts are created through four distinct pathways. All four share the low-level allocation code path (`create_cohort`) but differ in which upstream routine constructs the initial state.

| Pathway | Entry function | When used | Initial conditions |
| --- | --- | --- | --- |
| Near-bare-ground | `create_cohort()` | Cold start | Minimal seedlings, PFT parameters |
| Inventory | `create_cohort()` | Inventory file read | Observed size, biomass from file |
| Recruitment | `create_cohort()` via `recruitment()` | Daily dynamics | Minimum size, seed germination |
| Restart | `create_cohort()` | Restart file read | Full state restoration |

Sources: `(biogeochem/EDCohortDynamicsMod.F90:123-226)`

## Recruitment Process

Recruitment creates new cohorts from germinated seeds. It is called once per patch from the reproduction/recruitment loop inside `ed_ecosystem_dynamics` (`main/EDMainMod.F90:259`).

Sources: `(biogeochem/EDPhysiologyMod.F90:2467-2798)`

### Recruitment Size and Biomass Initialization

New recruits start at minimum height and follow strict allometric relationships. Their biomass pools are initialized according to the PARTEH mode in force.

| Property | Initialization method | Key functions |
| --- | --- | --- |
| height | PFT minimum (`prt_params%hgt_min(ipft)`) | Direct from parameter |
| dbh | Inverted from height | `h2d_allom(h_min, ipft, dbh)` |
| bleaf | Allometry from dbh | `bleaf(dbh, ipft, ...)` |
| bfineroot | Proportional to leaf via `l2fr` | `bfineroot(dbh, ipft, l2fr, ...)` |
| bsapwood | Allometry from dbh | `bsap_allom(dbh, ipft, ...)` |
| bstore | Cushion fraction | `bstore_allom(dbh, ipft, ...)` |
| n | From seed germination, density dependence, hydraulic constraints | (local calc in `recruitment`) |

Sources: `(biogeochem/EDPhysiologyMod.F90:2467-2798)`

## Cohort Fusion

Cohort fusion reduces the number of cohorts by merging similar individuals. This is necessary to keep computational costs manageable while maintaining ecological realism. Fusion walks the cohort list tallest-to-shortest and compares candidates by PFT, crown damage class, canopy layer, DBH, and (when enabled) cohort age.

Sources: `(biogeochem/EDCohortDynamicsMod.F90:648-1232)`

### Fusion Conservation Methods

FATES offers two methods for conserving properties during fusion. The choice affects how allometric consistency is maintained.

| Method (constant) | Conserved quantities | Adjusted quantities | Use case |
| --- | --- | --- | --- |
| `conserve_crownarea_and_number_not_dbh` (1) | Total crown area, plant number | Recalculated DBH from crown area allometry | Default; maintains spatial coverage |
| `conserve_dbh_and_number_not_crownarea` (2) | Average DBH, plant number | Recalculated crown area from DBH | Maintains size structure more strictly |

The constants are declared at `(biogeochem/EDCohortDynamicsMod.F90:112-113)`; the default (`cohort_fusion_conservation_method`) is set at `:115`. The two methods branch at `(biogeochem/EDCohortDynamicsMod.F90:852)` and `(:906)` inside `fuse_cohorts`.

### Fusion Tolerance

Fusion uses a tolerance on fractional DBH difference, with a relaxation loop that repeatedly widens the tolerance until the cohort count falls below target. The fractional DBH comparison is computed at `(biogeochem/EDCohortDynamicsMod.F90:742)` and the tolerance test at `(:746)`.

## Cohort Termination

Cohorts are terminated when they become too small or violate ecological constraints. `terminate_cohorts` accepts a `level` argument (1, 2, or 3) and applies a different termination criterion at each level. Levels 1 and 2 are called inside the daily loop (level 1 before `fuse_cohorts`, level 2 after); level 3 is invoked elsewhere (e.g., from canopy structure operations) to remove cohorts that have been pushed below the maximum canopy layer.

### Termination Criteria

| Level | Criterion | Threshold | Check location | Reason |
| --- | --- | --- | --- | --- |
| 1 | Number density (FPE prevention) | `n < min_n_safemath` (1.0E-12) | Before fusion | Prevent floating-point errors |
| 2 | Number density per m² | `n/area <= min_npm2` (1.0E-7) | After fusion | Too sparse |
| 2 | Absolute number | `n <= min_nppatch` (`min_npm2 * min_patch_area`) | After fusion | Too few individuals |
| 2 | DBH with negative storage | `dbh < 0.00001 AND store_c < 0` | After fusion | Unviable plant |
| 2 | Live biomass depleted | `sapw_c + leaf_c + fnrt_c < 1e-10` OR `store_c < 1e-10` | After fusion | No live tissue or no reserves |
| 2 | Total negative biomass | `struct_c + sapw_c + leaf_c + fnrt_c + store_c < 0` | After fusion | Mass balance violation |
| 3 | Canopy layer | `canopy_layer > nclmax` (`nclmax = 3` at e027a40) | Caller-driven (canopy structure) | Too deep in canopy |

Thresholds are defined at `(main/EDTypesMod.F90:110-128)`.

Sources: `(biogeochem/EDCohortDynamicsMod.F90:283-410)`

### SendCohortToLitter Process

When a cohort terminates, all its biomass is transferred to patch-level litter pools. The distribution depends on PFT properties and root profiles. `SendCohortToLitter` partitions aboveground biomass into CWD size classes and fine litter, and belowground biomass into fine root litter and belowground CWD, respecting the element (C, N, P) and organ layout of the PARTEH object.

Sources: `(biogeochem/EDCohortDynamicsMod.F90:516-644)`

## Cohort Sorting and Organization

Cohorts must remain sorted by height to maintain the linked list invariant. At e027a40 sorting is invoked via the type-bound method `currentPatch%SortCohorts()` once per patch inside the daily loop (after recruitment, before fusion) to repair ordering after any operation that changed height. The method body lives on `fates_patch_type` and uses an index sort to build a new ordering, then re-threads the doubly-linked list.

Sources: `(biogeochem/FatesPatchMod.F90:264)` (procedure binding), `(biogeochem/FatesPatchMod.F90:1172-1237)` (method body), `(main/EDMainMod.F90:272)` (call site)

## Integration with Daily Dynamics

Cohort lifecycle functions are called at specific points in the daily dynamics loop to maintain consistency. The order (see `main/EDMainMod.F90:259-281`) is:

1. `recruitment` — per patch, adds new seedling-size cohorts to the shortest end of each list
2. `TotalBalanceCheck(1)` — verify recruitment mass conservation
3. `currentPatch%SortCohorts()` — repair height ordering (type-bound method)
4. `terminate_cohorts(level=1)` — remove numerically unstable cohorts
5. `fuse_cohorts` — merge similar cohorts
6. `terminate_cohorts(level=2)` — clean up post-fusion artifacts
7. `TotalBalanceCheck(2)` — verify cohort management conserved mass

This sequence ensures:

- new recruits are sorted and integrated before fusion sees them;
- level-1 termination prevents numerical issues inside fusion;
- level-2 termination cleans up cohorts that became unviable from fusion.

Sources: `(main/EDMainMod.F90:259-289)`, `(biogeochem/EDPhysiologyMod.F90:2467-2798)`

## Key Module Functions Reference

| Function | Module | Purpose | Source |
| --- | --- | --- | --- |
| `create_cohort()` | EDCohortDynamicsMod | Allocate and initialize new cohort | `(biogeochem/EDCohortDynamicsMod.F90:123)` |
| `InitPRTObject()` | EDCohortDynamicsMod | Allocate PARTEH object by hypothesis | `(biogeochem/EDCohortDynamicsMod.F90:230)` |
| `recruitment()` | EDPhysiologyMod | Create new cohorts from seeds | `(biogeochem/EDPhysiologyMod.F90:2467)` |
| `terminate_cohorts()` | EDCohortDynamicsMod | Remove invalid cohorts (level 1, 2, or 3) | `(biogeochem/EDCohortDynamicsMod.F90:283)` |
| `terminate_cohort()` | EDCohortDynamicsMod | Remove a single cohort | `(biogeochem/EDCohortDynamicsMod.F90:413)` |
| `SendCohortToLitter()` | EDCohortDynamicsMod | Transfer biomass to litter pools | `(biogeochem/EDCohortDynamicsMod.F90:516)` |
| `fuse_cohorts()` | EDCohortDynamicsMod | Merge similar cohorts | `(biogeochem/EDCohortDynamicsMod.F90:648)` |
| `SortCohorts` (type-bound on `fates_patch_type`) | FatesPatchMod | Reorder cohorts by height | `(biogeochem/FatesPatchMod.F90:1172)` |
| `InsertCohort` (type-bound on `fates_patch_type`) | FatesPatchMod | Insert cohort into sorted list | `(biogeochem/FatesPatchMod.F90:977)` |
| `CountCohorts` (type-bound on `fates_patch_type`) | FatesPatchMod | Count cohorts in a patch | `(biogeochem/FatesPatchMod.F90:1145)` |
| `EvaluateAndCorrectDBH()` | EDCohortDynamicsMod | Ensure DBH consistent with structural C | `(biogeochem/EDCohortDynamicsMod.F90:1236)` |
| `DamageRecovery()` | EDCohortDynamicsMod | Create recovered cohort clone | `(biogeochem/EDCohortDynamicsMod.F90:1335)` |

At e027a40, the previous free-subroutine `sort_cohorts`, `insert_cohort`, and `count_cohorts` in `EDCohortDynamicsMod.F90` no longer exist; they have all been migrated to type-bound procedures on `fates_patch_type` in `FatesPatchMod.F90` (see procedure bindings near `:261-264`).

Sources: `(biogeochem/EDCohortDynamicsMod.F90:1-1597)`, `(biogeochem/EDPhysiologyMod.F90:2467-2798)`, `(biogeochem/FatesPatchMod.F90:977-1237)`
