# Data Structures: Sites, Patches, and Cohorts

---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

**Relevant source files:**
- `main/EDTypesMod.F90`
- `biogeochem/FatesPatchMod.F90`
- `biogeochem/FatesCohortMod.F90`
- `biogeochem/EDPatchDynamicsMod.F90`
- `biogeochem/EDCohortDynamicsMod.F90`
- `main/EDInitMod.F90`
- `main/FatesInventoryInitMod.F90`
- `main/FatesRestartInterfaceMod.F90`

## Purpose and Scope

This page documents the core data structures that represent vegetation in FATES: sites, patches, and cohorts. These structures form a three-level hierarchy that enables FATES to simulate forest dynamics across spatial and size scales. Sites represent gridcells or land units, patches represent disturbance-age elements within a site, and cohorts represent groups of individual plants with similar size and functional type within a patch.

For information on how these structures are populated during initialization, see [Initialization Modes](../getting-started/initialization.md). For details on PARTEH plant allocation objects stored within cohorts, see [PARTEH: Plant Allocation System](../plant-physiology/parteh/index.md). For how cohorts are created, fused, and terminated during the simulation, see [Cohort Lifecycle Management](cohort_lifecycle.md) and [Patch Dynamics and Disturbances](patch_dynamics.md).

## Hierarchical Organization

FATES organizes vegetation in a strict three-level hierarchy with linked-list organization at the patch and cohort levels:

```
ed_site_type (gridcell/land unit)
  └─ fates_patch_type   (age-ordered doubly linked list: oldest_patch .. youngest_patch)
       └─ fates_cohort_type (height-ordered doubly linked list: tallest .. shortest)
```

At e027a40, FATES uses 14 PFTs by default (was 12 in earlier defaults): two new Arctic shrubs at PFT positions 10 and 11, and arctic_c3_grass at position 12.

Sources: `(main/EDTypesMod.F90:325-435)`, `(biogeochem/FatesPatchMod.F90)`, `(biogeochem/FatesCohortMod.F90)`

## Site Data Structure

The `ed_site_type` is the top-level container representing a gridcell or land unit. Each site maintains pointers to its patch linked list and stores site-level state variables, diagnostics, and environmental drivers.

### Core Site Components

| Component | Type | Description |
| --- | --- | --- |
| `oldest_patch` | pointer (`fates_patch_type`) | Head of patch linked list (oldest patch) |
| `youngest_patch` | pointer (`fates_patch_type`) | Tail of patch linked list (youngest patch) |
| `lat`, `lon` | real(r8) | Geographic coordinates (degrees) |
| `spread` | real(r8) | Dynamic canopy crown area spread factor [0-1] |
| `nlevsoil` | integer | Number of soil layers |

### Phenology State Variables

The site stores phenology status for cold and drought deciduous dynamics:

| Variable | Type | Description |
| --- | --- | --- |
| `cstatus` | integer | Cold deciduous status (0 = never experienced cold over ~400 days, 1 = cold-state/leaves dropped, 2 = warm-state/leaves flushed) |
| `dstatus(maxpft)` | integer array | Drought deciduous status per PFT (0 = off/time, 1 = off/moisture, 2 = on/moisture, 3 = on/time, 4 = partial) |
| `grow_deg_days` | real(r8) | Accumulated growing degree days |
| `vegtemp_memory(num_vegtemp_mem)` | real(r8) array | 10-day temperature memory for senescence |
| `cleafondate`, `cleafoffdate` | integer | Model dates of cold-deciduous leaf on/off |
| `dleafondate(maxpft)`, `dleafoffdate(maxpft)` | integer arrays | Drought-deciduous leaf dates per PFT |
| `elong_factor(maxpft)` | real(r8) array | Leaf elongation factor [0-1] for partial leaf flush |

Sources: `(main/EDTypesMod.F90:325-440)` (linked-list pointers and core fields at `:328-329, 343-344`; phenology state at `:412-437`)

## Patch Data Structure and Linked List

Patches represent landscape elements of similar disturbance age. They are organized as a doubly linked list ordered by age (youngest to oldest through `younger`/`older` pointers). Each patch occupies a fraction of the site area.

### Key Patch Fields

| Field | Type | Description |
| --- | --- | --- |
| `patchno` | integer | Patch index number |
| `age` | real(r8) | Time since disturbance created this patch [years] |
| `age_class` | integer | Age class index for binning |
| `area` | real(r8) | Patch area [m²] |
| `younger`, `older` | pointers | Links in age-ordered doubly linked list |
| `tallest`, `shortest` | pointers | Head and tail of cohort linked list |
| `land_use_label` | integer | Land-use category label (`primaryland`, `secondaryland`, `pastureland`, `rangeland`, `cropland`, `nocomp_bareground_land`); replaces the prior `anthro_disturbance_label` |
| `age_since_anthro_disturbance` | real(r8) | Time since last logging or land-use change [years] |
| `nocomp_pft_label` | integer | PFT label in no-competition mode |

Sources: `(biogeochem/FatesPatchMod.F90:67-93)`

### Patch Disturbance and Fire State

| Field | Type | Description |
| --- | --- | --- |
| `disturbance_rates(N_DIST_TYPES)` | real(r8) array (N_DIST_TYPES = 4) | Daily disturbance rates [fraction/day] for treefall, fire, logging, land-use change |
| `landuse_transition_rates(n_landuse_cats)` | real(r8) array | Per-category land-use transition rates from LUH driver |
| `frac_burnt` | real(r8) | Fraction of patch burned by fire this timestep |
| `burnt_frac_litter(num_elements)` | real(r8) array | Fraction of litter consumed by fire per element |
| `scorch_ht(maxpft)` | real(r8) array | Scorch height per PFT [m] |

Sources: `(biogeochem/FatesPatchMod.F90:203-243)`, `(main/FatesConstantsMod.F90:44)` (`N_DIST_TYPES = 4`)

### Patch Litter Pools

Each patch contains a `litter_type` array indexed by element (carbon, nitrogen, phosphorus). Each element's `litter_type` contains pools for:

- Above-ground coarse woody debris (CWD) in size classes
- Below-ground CWD
- Leaf litter (fine litter)
- Fine root litter
- Seed pools (non-germinated and germinated)

### Patch Canopy Structure

| Field | Type | Description |
| --- | --- | --- |
| `ncl_p` | integer | Number of occupied canopy layers |
| `canopy_layer_tlai(nclmax)` | real(r8) array | Total LAI per canopy layer [m²/m²] (`nclmax = 3` at e027a40) |
| `total_canopy_area` | real(r8) | Sum of crown areas of canopy trees [m²] |
| `tlai_profile(nclmax, maxpft, nlevleaf)` | real(r8), allocatable 3D array | Vertical total LAI profile per canopy layer, PFT, leaf level [m²/m²] |
| `elai_profile(nclmax, maxpft, nlevleaf)` | real(r8), allocatable 3D array | Exposed LAI profile (snow-adjusted) |
| `tsai_profile(nclmax, maxpft, nlevleaf)` | real(r8), allocatable 3D array | Total stem area index profile |
| `esai_profile(nclmax, maxpft, nlevleaf)` | real(r8), allocatable 3D array | Exposed stem area index profile |

`nclmax` was raised from 2 to 3 at e027a40 (declared `integer, parameter, public :: nclmax = 3` in `main/EDParamsMod.F90:76`). The four canopy profile arrays are declared `allocatable :: (:,:,:)` at `(biogeochem/FatesPatchMod.F90:133-139)` and allocated with shape `(ncan, numpft, nveg)` during patch initialisation.

Sources: `(biogeochem/FatesPatchMod.F90:91-150)`, `(main/EDParamsMod.F90:76)`

## Cohort Data Structure and Linked List

Cohorts represent groups of individual plants with similar size, PFT, and age within a patch. They are organized in a height-ordered doubly linked list (tallest to shortest through `taller`/`shorter` pointers).

### Core Cohort State Variables

| Field | Type | Description |
| --- | --- | --- |
| `pft` | integer | Plant functional type index |
| `n` | real(r8) | Number of individuals per patch area [plants/m²] |
| `dbh` | real(r8) | Diameter at breast height [cm] |
| `height` | real(r8) | Plant height [m] |
| `coage` | real(r8) | Cohort age [years since recruitment] |
| `canopy_layer` | integer | Canopy position (1 = top canopy, 2+ = understory) |
| `canopy_layer_yesterday` | real(r8) | Previous timestep canopy layer (kept real for conservative fusion) |
| `crowndamage` | integer | Crown damage class (1 = undamaged, 2+ = damaged) |
| `canopy_trim` | real(r8) | Fraction of maximum leaf biomass [0-1] |
| `c_area` | real(r8) | Crown area per individual [m²] |
| `isnew` | logical | True until the cohort has experienced its first daily integration |
| `coage_class`, `coage_by_pft_class` | integer | Cohort age binning indices (when `hlm_use_cohort_age_tracking`) |

Sources: `(biogeochem/FatesCohortMod.F90:82-120)`

### Cohort Biomass via PARTEH

Each cohort contains a pointer `prt` to a PARTEH (Plant Allocation and Reactive Transport Extensible Hypotheses) object that tracks biomass pools:

- **Leaf biomass** (`leaf_organ`)
- **Fine root biomass** (`fnrt_organ`)
- **Sapwood biomass** (`sapw_organ`)
- **Structural biomass** (`struct_organ`)
- **Storage biomass** (`store_organ`)
- **Reproductive tissue biomass** (`repro_organ`)

For each element tracked (C, N, P), PARTEH stores mass in each organ. See [PARTEH: Plant Allocation System](../plant-physiology/parteh/index.md) for details.

### Cohort Physiology and Fluxes

| Field | Type | Description |
| --- | --- | --- |
| `gpp_acc`, `gpp_acc_hold` | real(r8) | Accumulated gross primary production [kgC/indiv/day or /year] |
| `npp_acc`, `npp_acc_hold` | real(r8) | Accumulated net primary production [kgC/indiv/day or /year] |
| `resp_m_acc`, `resp_m_acc_hold` | real(r8) | Accumulated maintenance respiration [kgC/indiv/day or /year] |
| `resp_g_acc_hold` | real(r8) | Growth respiration held for I/O [kgC/indiv/year] (computed from `prt_params%grperc * max(0, gpp_acc - resp_m_acc) * days_per_year`) |
| `resp_excess_hold` | real(r8) | Excess respiration from nutrient limitation [kgC/indiv/day] |
| `resp_m_unreduced` | real(r8) | Diagnostic-only unreduced maintenance respiration [kgC/indiv/timestep] |
| `treelai` | real(r8) | Leaf area index per individual [m²/m²] |
| `treesai` | real(r8) | Stem area index per individual [m²/m²] |

The single-field `resp_acc` / `resp_acc_hold` from earlier versions has been split into the four independent accumulators above. Code that read `cohort%resp_acc` or `cohort%resp_acc_hold` will not compile against e027a40.

The `_acc` variables are zeroed at the end of the dynamics call and accumulated over the next dynamics interval; `_acc_hold` retains the last completed day's value (converted to per-year for I/O).

Sources: `(biogeochem/FatesCohortMod.F90:145-217)`

### Cohort Mortality Rates

Each cohort tracks multiple mortality rate components calculated daily in `Mortality_Derivative`:

| Field | Type | Description |
| --- | --- | --- |
| `dmort` | real(r8) | Total proportional mortality rate [/year] |
| `cmort` | real(r8) | Carbon starvation mortality [indiv/year] |
| `bmort` | real(r8) | Background mortality [indiv/year] |
| `hmort` | real(r8) | Hydraulic failure mortality [indiv/year] |
| `frmort` | real(r8) | Freezing mortality [indiv/year] |
| `smort` | real(r8) | Senescence mortality [indiv/year] |
| `asmort` | real(r8) | Age senescence mortality [indiv/year] |
| `dgmort` | real(r8) | Damage mortality [indiv/year] |
| `lmort_direct` | real(r8) | Direct logging rate [fraction/logging activity] |
| `lmort_collateral` | real(r8) | Collateral logging damage [fraction/logging activity] |
| `lmort_infra` | real(r8) | Mechanical logging damage [fraction/logging activity] |
| `fire_mort` | real(r8) | Post-fire mortality from cambial and crown damage [0-1] |
| `nonrx_cambial_mort` | real(r8) | Cambial kill mortality due to wildfire |
| `nonrx_crown_mort` | real(r8) | Crown fire mortality due to wildfire |
| `nonrx_fire_mort` | real(r8) | Post-fire mortality due to wildfire |

Sources: `(biogeochem/FatesCohortMod.F90:230-277)`

### Cohort Phenology

| Field | Type | Description |
| --- | --- | --- |
| `status_coh` | integer | Phenology status (2 = leaves on, 1 = leaves off) |
| `efleaf_coh` | real(r8) | Leaf elongation factor [0-1] |
| `effnrt_coh` | real(r8) | Fine root elongation factor [0-1] |
| `efstem_coh` | real(r8) | Stem elongation factor [0-1] |

Sources: `(biogeochem/FatesCohortMod.F90:99-102)`

### Cohort Hydraulics

If plant hydraulics is enabled (`hlm_use_planthydro == itrue`), each cohort has an associated hydraulics object tracking water content, water potential, and hydraulic conductances across leaf, stem, and root compartments. Updates happen inside `UpdateSizeDepPlantHydProps`/`UpdateSizeDepPlantHydStates` during `ed_integrate_state_variables`, and post-cohort-loop bookkeeping calls `AccumulateMortalityWaterStorage` for water-conservation accounting.

Sources: `(biogeochem/FatesCohortMod.F90)`, `(main/EDMainMod.F90:707-761)`

## Memory Layout and Allocation

### Site Allocation

Sites are allocated as a fixed-size array by the host land model. Each site then allocates its own internal arrays during initialization (`EDInitMod`).

Sources: `(main/EDInitMod.F90)`

### Patch Allocation and Linking

Patches are dynamically allocated and inserted into the age-ordered linked list. The insertion algorithm maintains the age-ordering invariant:

- Traverse the list from youngest to oldest
- Find the position where `current_patch%age <= newpatch%age < older_patch%age`
- Update four pointers to insert between `current_patch` and `older_patch`

Insertion is performed via the type-bound `InsertPatch` on `ed_site_type`-style helpers and via `InsertPatch` in `EDPatchDynamicsMod.F90:3751`.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:488-1708)`, `(biogeochem/EDPatchDynamicsMod.F90:3751-3839)`

### Cohort Allocation and Linking

Cohorts are allocated and inserted into the height-ordered linked list within their patch via the type-bound `InsertCohort` method on `fates_patch_type` (`biogeochem/FatesPatchMod.F90:977`). The insertion maintains height ordering:

- Traverse from tallest to shortest
- Insert where `taller_cohort%height >= nc%height > shorter_cohort%height`
- Update pointers in both directions

The previous free-subroutine `insert_cohort` in `EDCohortDynamicsMod.F90` no longer exists at e027a40; the type-bound `InsertCohort` method is the only insertion path. `CountCohorts` (also type-bound on `fates_patch_type` at `biogeochem/FatesPatchMod.F90:1145`) replaced the free `count_cohorts` subroutine.

Sources: `(biogeochem/FatesPatchMod.F90:977-1168)`, `(biogeochem/EDCohortDynamicsMod.F90:123-226)`

## Initialization Pathways

FATES supports three initialization modes, each populating the data structures differently. At e027a40 the FATES parameter file is read in JSON format via `JSONRead` plus `FatesTransferParameters()`, replacing the older NetCDF/CDL parameter loader.

### Near-Bare-Ground Initialization

In near-bare-ground mode, FATES creates one patch per site (or per PFT in no-competition mode) and seeds it with minimal cohorts at the PFT minimum height.

Sources: `(main/EDInitMod.F90)`

### Inventory Initialization

Inventory initialization reads PSS (Patch State) and CSS (Cohort State) files in ED2-compatible format:

- PSS contains one line per patch: time, patch_name, land_use_type, age, area, soil_carbon_pools
- CSS contains one line per cohort: time, patch_name, cohort_index, dbh, height, pft, n, bdead, balive
- Cohorts are matched to patches via the string identifier `patch_name`
- After reading, cohorts and patches are fused to reduce memory footprint

Sources: `(main/FatesInventoryInitMod.F90)`

### Restart Initialization

Restart initialization reads the complete model state from a restart file. The restart system uses flat arrays in the host land model's I/O format and reconstructs the linked lists:

- Patches are stored in age order in restart arrays
- Cohorts within each patch are stored in height order
- `fates_PatchesPerSite` and `fates_CohortsPerPatch` variables indicate array slicing
- PARTEH biomass pools are restored from separate arrays per organ and element
- Linked list pointers are reconstructed during restart reading

Sources: `(main/FatesRestartInterfaceMod.F90)`

## Linked List Traversal Patterns

### Forward Traversal of Patches (Oldest to Youngest)

Follow `%younger` pointers starting from `oldest_patch` until reaching `null`. This is the dominant traversal direction in `ed_ecosystem_dynamics` and in `ed_integrate_state_variables`.

### Reverse Traversal of Patches (Youngest to Oldest)

Follow `%older` pointers starting from `youngest_patch`. Used when the operation must touch the most-recent disturbance first (for example, post-cohort-loop water-mortality accumulation, seed mixing, and pre-disturbance litter generation).

### Forward Traversal of Cohorts (Shortest to Tallest)

Follow `%taller` pointers starting from `patch%shortest`. Used inside the growth loop in `ed_integrate_state_variables` so that newly recovered damage-clone cohorts (inserted "above" the donor) are skipped correctly on the same iteration.

### Reverse Traversal of Cohorts (Tallest to Shortest)

Follow `%shorter` pointers starting from `patch%tallest`. Used for light competition and canopy structure operations where canopy dominants must be processed first.

Sources: `(biogeochem/EDPatchDynamicsMod.F90)`, `(main/EDMainMod.F90)`, `(biogeochem/EDCohortDynamicsMod.F90)`

## Memory Management Considerations

### Dynamic Allocation

- **Sites**: allocated once at initialization, fixed for simulation duration
- **Patches**: dynamically created via `spawn_patches()` and destroyed via `terminate_patches()`
- **Cohorts**: dynamically created via `recruitment()` (and the other creation pathways) and destroyed via `terminate_cohorts()`

### Pointer Safety

All linked list traversals use `associated()` checks before dereferencing, preventing segmentation faults when reaching list ends where pointers are `null()`.

### Cohort and Patch Fusion

To limit memory usage, FATES fuses similar cohorts and patches:

- **Cohort fusion**: `fuse_cohorts()` merges cohorts with similar PFT, size, and canopy position
- **Patch fusion**: `fuse_patches()` merges patches with similar age and species composition

Fusion criteria use binned profiles (size × PFT) to assess similarity. See [Cohort Lifecycle Management](cohort_lifecycle.md) and [Patch Dynamics and Disturbances](patch_dynamics.md).

### Termination Thresholds

Small cohorts and patches are removed to prevent numerical instability. The thresholds are defined as public constants in `EDTypesMod`:

| Constant | Value | Source line | Purpose |
| --- | --- | --- | --- |
| `force_patchfuse_min_biomass` | `0.005` kg/m² | `:110` | Force-fuse patches below this biomass |
| `max_age_of_second_oldest_patch` | `200` years | `:112` | Force-fuse when oldest patch exceeds this age |
| `min_npm2` | `1.0E-7` plants/m² | `:120` | Minimum cohort number density before termination |
| `min_patch_area` | `0.01` m² | `:121` | Smallest allowable patch area before termination |
| `min_patch_area_forced` | `0.0001` m² | `:122` | Protected threshold for the youngest patch |
| `min_nppatch` | `min_npm2 * min_patch_area` | `:127` | Minimum plants per patch |
| `min_n_safemath` | `1.0E-12` | `:128` | Aggressive FPE-prevention threshold (level-1 termination) |

Sources: `(main/EDTypesMod.F90:110-128)`
