# Canopy Structure and Competition

<details>
<summary>Relevant source files (FATES commit e85d997)</summary>

- `biogeochem/EDCanopyStructureMod.F90`
- `biogeochem/FatesAllometryMod.F90`
- `biogeochem/FatesCohortMod.F90`
- `biogeochem/FatesPatchMod.F90`
- `main/EDParamsMod.F90`
- `main/FatesConstantsMod.F90`

</details>

## Purpose and Scope

This page describes how FATES organises vegetation cohorts vertically into discrete canopy layers and manages competition for light among cohorts. The core mechanism is the Perfect Plasticity Approximation (PPA), which assumes that plants can plastically rearrange their crowns to fill available horizontal canopy space. This assignment determines which cohorts occupy the upper canopy (full light) and which are relegated to the understory, and therefore fundamentally shapes carbon gain, growth, and mortality.

For the mechanics of layer assignment (demotion and promotion), see [Canopy Layering and Perfect Plasticity](ppa.md). For how leaf and stem area are distributed within those layers, see [LAI and SAI Profiles](lai_sai.md). For radiation transfer through the canopy, see `biophysics/radiation.md`.

The driver subroutine is `canopy_structure` (`EDCanopyStructureMod.F90:90`). It is called once per day per site.

## Canopy Layer System

FATES uses a small, fixed number of discrete vertical canopy layers:

- **Layer 1**: Upper canopy (overstory). Receives direct + diffuse sunlight.
- **Layer 2**: Understory. Receives only light transmitted through layer 1.

The maximum number of layers is set by the Fortran compile-time constant `nclmax` (`EDParamsMod.F90:98`):

```fortran
integer, parameter, public :: nclmax = 2
```

Because `nclmax` is a Fortran `parameter`, its value (2) is baked in at compile time and cannot be changed through the parameter file or namelist. Cohorts whose assignment would exceed `nclmax` after demotion are terminated (`EDCanopyStructureMod.F90:736-744`).

The PPA's key assertion is that when the summed crown area of cohorts in a given layer exceeds `currentPatch%area`, some cohorts must be "demoted" to the layer below. Symmetrically, after disturbance or mortality opens gaps, cohorts can be "promoted" from below to fill unused space in the upper layer.

## Control Flow

`canopy_structure` iterates the following loop per patch until every layer is balanced within tolerance or `max_patch_iterations = 10` iterations are reached (`EDCanopyStructureMod.F90:155`, `EDCanopyStructureMod.F90:255-298`):

1. For each active layer `i_lyr` from 1 upward, call `CanopyLayerArea` to get its current crown area sum.
2. If `arealayer(i_lyr) > currentPatch%area + area_target_precision`, call `DemoteFromLayer(currentSite, currentPatch, i_lyr, bc_in)`.
3. If `arealayer(i_lyr) < currentPatch%area - area_target_precision` and a lower layer exists, call `PromoteIntoLayer(currentSite, currentPatch, i_lyr)`.
4. Recheck with `CanopyLayerArea`. If balance has not been achieved within `area_check_precision` (absolute) and `area_check_rel_precision` (relative), iterate.

After the loop converges, `currentPatch%NCL_p` is set to `min(nclmax, z)`. Under strict PPA (`ED_val_comp_excln < 0`), `currentPatch%zstar` is updated to the height of the shortest cohort that is still in layer 1 and whose next-shorter neighbour is in layer 2 (`EDCanopyStructureMod.F90:313-326`). In stochastic PPA mode (`ED_val_comp_excln >= 0`), `zstar` is not updated by `canopy_structure` and should not be interpreted as a dynamic threshold.

Tolerance constants (`EDCanopyStructureMod.F90:70-79`):

| Constant | Value | Purpose |
| --- | --- | --- |
| `area_target_precision` | `1.0E-11` | Target for iterative area balancing |
| `area_check_precision` | `1.0E-7` | Absolute tolerance for layer-area checks |
| `area_check_rel_precision` | `1.0E-4` | Relative tolerance for layer-area checks |
| `similar_height_tol` | `1.0E-3` m | Heights within 1 mm are treated as tied |
| `max_patch_iterations` | `10` | Maximum outer iterations before abort |

## Cohort Demotion

When `arealayer(i_lyr) > currentPatch%area`, `DemoteFromLayer` (`EDCanopyStructureMod.F90:338-783`) selects cohorts or cohort fractions to move down:

- **Stochastic mode** (`ED_val_comp_excln >= 0`, `EDCanopyStructureMod.F90:410-411`): each cohort in layer `i_lyr` is assigned `excl_weight = 1 / height**ED_val_comp_excln`. Shorter cohorts receive larger weights, but all cohorts in the layer retain a non-zero probability of being pushed down. Weights are normalised and scaled so the total demoted area matches the excess.
- **Deterministic mode** (`ED_val_comp_excln < 0`, from `EDCanopyStructureMod.F90:413` onward): the loop runs from shortest to tallest and demotes in strict rank order until `demote_area` is exhausted. Cohorts whose heights agree within `similar_height_tol` are grouped and demoted in proportion to their crown areas.

### Partial Cohort Demotion (Cohort Splitting)

When the demotion weight `cc_loss` assigned to a cohort is strictly less than `currentCohort%c_area` (and greater than `area_target_precision`), the cohort must be split between layers. The code at `EDCanopyStructureMod.F90:654-717` does this as follows:

```fortran
newarea = currentCohort%c_area - cc_loss          ! area kept in upper layer
copyc%n = currentCohort%n * newarea / currentCohort%c_area
currentCohort%n = currentCohort%n - copyc%n       ! = n * cc_loss / c_area
copyc%canopy_layer       = i_lyr                  ! copy stays in upper layer
currentCohort%canopy_layer = i_lyr + 1            ! original is demoted
```

| Property | Original cohort (demoted) | Copy (remains in upper) |
| --- | --- | --- |
| `canopy_layer` | `i_lyr + 1` | `i_lyr` |
| `n` (number density) | `n * cc_loss / c_area` | `n * (c_area - cc_loss) / c_area` |
| `c_area` | Recomputed via `carea_allom` after density drop | Recomputed via `carea_allom` |
| PARTEH / hydraulics | Existing state | Freshly allocated and copied from original |

Total plant number is conserved. The copy is linked into the height-sorted cohort list adjacent to the original (`EDCanopyStructureMod.F90:708-717`). After splitting, `DemoteFromLayer` calls `CanopyLayerArea` and aborts the run if the balance check still fails beyond `area_check_precision` / `area_check_rel_precision` (`EDCanopyStructureMod.F90:767-777`).

## Cohort Promotion

When `arealayer(i_lyr) < currentPatch%area`, `PromoteIntoLayer` (`EDCanopyStructureMod.F90:787-1236`) fills the gap from layer `i_lyr+1`. The mechanism mirrors demotion with two important asymmetries, both documented in detail on the [PPA page](ppa.md):

1. **Promote-all short-circuit**. If the entire lower layer's area fits into the gap (`arealayer_below <= promote_area`), every cohort in layer `i_lyr+1` is promoted unconditionally, regardless of height or of `ED_val_comp_excln` (`EDCanopyStructureMod.F90:839-868`).
2. **Weighted promotion** (only when the lower layer is larger than the gap). Stochastic mode uses `prom_weight = height**ED_val_comp_excln`, so taller cohorts are favoured. Deterministic mode promotes in rank order from tallest downward, with tied-height cohorts grouped by `similar_height_tol`.

## Crown Area Allometry

Crown area is the horizontal ground footprint of a cohort and is the quantity compared to `patch%area` during canopy structure. It is computed by `carea_allom` (`FatesAllometryMod.F90:476-550`) and, for the standard FATES allometry modes, by the helper subroutine `carea_2pwr` (`FatesAllometryMod.F90:2118-2175`).

`carea_2pwr` is a `subroutine`, not a function: per-plant crown area is written back through the `intent(inout)` argument `c_area`. The per-plant value is multiplied by `nplant` inside `carea_allom` at `FatesAllometryMod.F90:546` to yield cohort-level crown area (m²).

The per-plant calculation is:

```fortran
crown_area_to_dbh_exponent = d2bl_p2 + d2bl_ediff
spreadterm                 = spread * d2ca_max + (1._r8 - spread) * d2ca_min
c_area (per plant)         = spreadterm * dbh ** crown_area_to_dbh_exponent
```

where the symbols correspond to PFT parameters in `prt_params`:

| Code symbol | `prt_params` name | Role |
| --- | --- | --- |
| `d2bl_p2` | `allom_d2bl2(pft)` | Exponent in the diameter-to-leaf-biomass allometry, reused for crown area |
| `d2bl_ediff` | `allom_blca_expnt_diff(pft)` | Difference between crown-area and leaf-biomass exponents (default 0) |
| `d2ca_min` | `allom_d2ca_coefficient_min(pft)` | Minimum crown-area coefficient (crowded canopies) |
| `d2ca_max` | `allom_d2ca_coefficient_max(pft)` | Maximum crown-area coefficient (open canopies) |
| `spread` | `currentSite%spread` | Site-level spread factor, in [0, 1] |

The site-level `spread` factor is a dynamic interpolation weight on `d2ca_max`. When `spread = 1`, `spreadterm = d2ca_max` (crowns expand to their maximum coefficient). When `spread = 0`, `spreadterm = d2ca_min` (crowns are at their minimum). The daily update in `canopy_spread` (`EDCanopyStructureMod.F90:1233-1287`) drives `spread` toward smaller values (more compact crowns) as site-level canopy area approaches `ED_val_canopy_closure_thresh * AREA`. See the [PPA page](ppa.md) for details.

### Crown Damage

If `crowndamage > 1`, `carea_2pwr` retrieves a `crown_reduction` factor via `GetCrownReduction` and multiplies per-plant crown area by `(1 - crown_reduction)` (`FatesAllometryMod.F90:2162-2165`). Damaged crowns therefore occupy less horizontal space and are correspondingly less likely to hold a layer-1 slot.

## LAI and SAI

Leaf area index (LAI) and stem area index (SAI) are computed at the cohort level by `tree_lai` (`FatesAllometryMod.F90:636-761`) and `tree_sai` (`FatesAllometryMod.F90:765-827`). Both functions return values in `m² leaf (or stem) area per m² of the cohort's own crown area`. The full vertical profiles (`tlai_profile`, `elai_profile`, `tsai_profile`, `esai_profile`) are built in `leaf_area_profile` (`EDCanopyStructureMod.F90:1467-1794`). Aggregation back to patch-level totals is performed by `calc_areaindex` (`EDCanopyStructureMod.F90:2024-2086`), which weights the profile values by `canopy_area_profile` to convert from per-crown-area to per-ground-area. See the dedicated [LAI and SAI Profiles](lai_sai.md) page for details.

## Canopy Layer Area

`CanopyLayerArea` (`EDCanopyStructureMod.F90:2090-2118`) sums the current `c_area` of all cohorts whose `canopy_layer` matches the requested index, after refreshing `c_area` via `carea_allom`. The result is in the same units as `currentPatch%area` (m²). `canopy_structure`, `DemoteFromLayer`, and `PromoteIntoLayer` all use it to check whether each layer is balanced against the patch area.

## Key Data Structures

### Cohort Fields (`FatesCohortMod.F90`)

| Field | Type | Units | Description |
| --- | --- | --- | --- |
| `canopy_layer` | integer | - | Current layer (1 = overstory, 2 = understory) |
| `canopy_layer_yesterday` | real(r8) | - | Previous day's layer index (weighted, for transition tracking) |
| `c_area` | real(r8) | m² | Crown area of entire cohort |
| `treelai` | real(r8) | m² leaf / m² crown area | Cohort LAI, per unit crown area |
| `treesai` | real(r8) | m² stem / m² crown area | Cohort SAI, per unit crown area |
| `height` | real(r8) | m | Height |
| `crowndamage` | integer | - | Crown damage class (1 = undamaged) |
| `excl_weight` | real(r8) | - | Temporary workspace for demotion weight |
| `prom_weight` | real(r8) | - | Temporary workspace for promotion weight |

### Patch Fields (`FatesPatchMod.F90`)

| Field | Type | Units | Description |
| --- | --- | --- | --- |
| `NCL_p` | integer | - | Number of currently occupied canopy layers |
| `canopy_layer_tlai(nclmax)` | real(r8) | m² leaf / m² canopy area | Total LAI in each canopy layer (per canopy area, not ground area) |
| `zstar` | real(r8) | m | Height separating layer 1 from layer 2. Only updated under strict PPA (`ED_val_comp_excln < 0`) |
| `area` | real(r8) | m² | Total patch area |

### Site Fields (`EDTypesMod.F90`)

| Field | Type | Units | Description |
| --- | --- | --- | --- |
| `spread` | real(r8) | - | Dynamic crown spread, [0, 1] (interpolation weight on `d2ca_max`) |
| `demotion_rate(nlevsclass)` | real(r8) | plants/day | Individuals demoted, by size class |
| `promotion_rate(nlevsclass)` | real(r8) | plants/day | Individuals promoted, by size class |
| `demotion_carbonflux` | real(r8) | kgC/day | Biomass flux from demotion |
| `promotion_carbonflux` | real(r8) | kgC/day | Biomass flux from promotion |

## Parameter Controls

| Name | Origin | Description | Notes |
| --- | --- | --- | --- |
| `nclmax` | `EDParamsMod.F90:98` | Max number of canopy layers | **Compile-time Fortran `parameter` = 2.** Not runtime-adjustable. |
| `ED_val_comp_excln` | FATES parameter file | Competitive exclusion exponent | `>= 0` stochastic; `< 0` strict PPA |
| `ED_val_canopy_closure_thresh` | FATES parameter file | Canopy closure threshold for spread update | Used in `canopy_spread` |
| `allom_d2ca_coefficient_min` | PFT | Min crown-area coefficient | `d2ca_min` in code |
| `allom_d2ca_coefficient_max` | PFT | Max crown-area coefficient | `d2ca_max` in code |
| `allom_d2bl2` | PFT | Leaf-biomass allometry exponent | `d2bl_p2` in code (reused for crown area) |
| `allom_blca_expnt_diff` | PFT | Crown-area-vs-leaf-biomass exponent offset | `d2bl_ediff` in code (default 0) |
| `allom_sai_scaler` | PFT | SAI:LAI ratio | Used in `tree_sai` |

## Integration with Other Systems

- **Radiation**: Layer assignment controls which cohorts are in the direct-beam path. The two-stream radiation solver walks layer-wise through `elai_profile` / `esai_profile`. See `biophysics/radiation.md`.
- **Photosynthesis and allocation**: Upper-canopy cohorts experience high light and favourable growth; understory cohorts may exhibit prolonged negative carbon balance and trigger carbon-starvation mortality. See `plant-physiology/parteh/index.md` and `plant-physiology/mortality.md`.
- **Disturbance and recruitment**: New recruits enter the lowest available layer. Disturbance (fire, mortality, logging) can open gaps in layer 1 that are filled by promotion on the next daily call. See `core-dynamics/patches.md`.
