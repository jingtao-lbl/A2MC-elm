# Canopy Layering and Perfect Plasticity

<details>
<summary>Relevant source files (FATES commit e85d997)</summary>

- `biogeochem/EDCanopyStructureMod.F90`
- `biogeochem/FatesAllometryMod.F90`
- `biogeochem/FatesCohortMod.F90`
- `biogeochem/FatesPatchMod.F90`
- `main/EDParamsMod.F90`
- `main/EDTypesMod.F90`

</details>

## Purpose and Scope

This page documents how FATES organises cohorts into discrete canopy layers using the Perfect Plasticity Approximation (PPA) and how the layer assignment is updated daily via the `DemoteFromLayer` and `PromoteIntoLayer` subroutines. For the overall system context and the crown-area allometry, see the [Canopy Structure and Competition overview](index.md). For how leaf and stem area are then distributed within a layer, see [LAI and SAI Profiles](lai_sai.md).

## Perfect Plasticity Approximation

The PPA (Purves et al. 2008; extended in Fisher et al. 2010) assumes that plants can fully adjust their canopy position, size, shape, and depth to fill available horizontal space. The layer assignment therefore reduces to a bookkeeping operation: if the sum of cohort crown areas in canopy layer `i` exceeds the patch area, some cohort or fraction of a cohort must be demoted to layer `i+1`.

FATES's implementation extends the original PPA with:

- **Stochastic competition** controlled by `ED_val_comp_excln`, so that tall cohorts are not guaranteed a canopy slot.
- **Dynamic crown spread** via `currentSite%spread`, which rescales the crown-area allometry daily in response to site-level canopy closure.
- **Multiple canopy layers up to `nclmax`**, which is a **Fortran compile-time parameter** equal to 2 in the current source (`EDParamsMod.F90:98`).

## `canopy_structure` Driver Loop

The entry point `canopy_structure` (`EDCanopyStructureMod.F90:90-332`) walks each patch and, for each patch, iterates:

1. For layers 1 through `nclmax`, call `CanopyLayerArea` to compute the crown-area sum.
2. If the layer has `arealayer > currentPatch%area + area_target_precision`, call `DemoteFromLayer`.
3. If the layer has `arealayer < currentPatch%area - area_target_precision` and a lower layer exists, call `PromoteIntoLayer`.
4. Recheck all layers; if any is out of balance beyond `area_check_precision` (absolute) or `area_check_rel_precision` (relative), repeat. Abort after `max_patch_iterations = 10` failed outer iterations.

After convergence, `currentPatch%NCL_p` is set to `min(nclmax, z)` where `z` is the highest occupied layer index. Under **strict PPA** (`ED_val_comp_excln < 0`), `currentPatch%zstar` is updated to the height of the shortest layer-1 cohort whose next-shorter neighbour is in layer 2 (`EDCanopyStructureMod.F90:313-326`). In **stochastic mode** (`ED_val_comp_excln >= 0`), `zstar` is not assigned here and carries whatever value it previously held; it is not a meaningful dynamic threshold in that regime.

### Tolerance Constants (`EDCanopyStructureMod.F90:70-79`, `:155`)

| Name | Value | Role |
| --- | --- | --- |
| `area_target_precision` | `1.0E-11` | Target for area balancing |
| `area_check_precision` | `1.0E-7` | Absolute tolerance for post-demote/post-promote layer checks |
| `area_check_rel_precision` | `1.0E-4` | Relative tolerance for the same checks |
| `similar_height_tol` | `1.0E-3` m | Heights within 1 mm are treated as tied |
| `max_patch_iterations` | `10` | Outer iteration cap |

## Crown Area and Canopy Spread

Each cohort's crown area is computed by `carea_allom` (`FatesAllometryMod.F90:476-550`), which dispatches on `allom_lmode` and calls `carea_2pwr` (`FatesAllometryMod.F90:2118-2175`) for the standard allometry branches. `carea_2pwr` is a **subroutine**, not a function — it writes the per-plant crown area back through its `intent(inout)` argument `c_area`, and `carea_allom` then multiplies by `nplant` at `FatesAllometryMod.F90:546` to produce the cohort-level value in m².

### The spread interpolation formula

The per-plant calculation in `carea_2pwr` is (`FatesAllometryMod.F90:2143-2160`):

```fortran
crown_area_to_dbh_exponent = d2bl_p2 + d2bl_ediff
spreadterm                 = spread * d2ca_max + (1._r8 - spread) * d2ca_min
c_area                     = spreadterm * dbh ** crown_area_to_dbh_exponent
```

where:

- `spread` is `currentSite%spread`, a dimensionless site-level variable constrained to `[0, 1]`.
- `d2ca_min = prt_params%allom_d2ca_coefficient_min(pft)` is the minimum (crowded-canopy) crown-area coefficient.
- `d2ca_max = prt_params%allom_d2ca_coefficient_max(pft)` is the maximum (open-canopy) crown-area coefficient.
- `d2bl_p2 = prt_params%allom_d2bl2(pft)`.
- `d2bl_ediff = prt_params%allom_blca_expnt_diff(pft)` (default 0).
- `crown_area_to_dbh_exponent` defaults to the diameter-to-leaf-biomass exponent, so that per-plant crown depth remains invariant with growth when `d2bl_ediff = 0`.

**Direction**. `spread` is the interpolation weight on `d2ca_max`. When `spread = 1`, `spreadterm = d2ca_max` and crowns are at their widest. When `spread = 0`, `spreadterm = d2ca_min` and crowns are at their most compact. The daily `canopy_spread` update (see next section) drives `spread` downward when site-level canopy area approaches closure and upward when the canopy is open, so crowns contract as the canopy closes and expand as it opens. Trees become "narrower and taller" in crowded conditions and "wider" in open conditions.

### `canopy_spread` daily update

The site-level `spread` factor is updated once per day by `canopy_spread` (`EDCanopyStructureMod.F90:1233-1287`). The logic:

```fortran
inc = 0.05_r8

! Sum layer-1 crown area over all woody cohorts at the site
sitelevel_canopyarea = sum over patches of c_area for woody, layer-1 cohorts

if ( sitelevel_canopyarea / AREA > ED_val_canopy_closure_thresh ) then
   currentSite%spread = currentSite%spread - inc
else
   currentSite%spread = currentSite%spread + inc
end if

currentSite%spread = max( min(currentSite%spread, 1._r8), 0._r8 )
```

with `AREA = 10000.0 m²` (`EDTypesMod.F90`). Interpretation: when the woody-cohort layer-1 canopy area exceeds `ED_val_canopy_closure_thresh * AREA`, `spread` is decremented by 0.05 (crowns contract next day). Otherwise `spread` is incremented by 0.05 (crowns expand). The result is then clamped to `[0, 1]`.

## Demotion Mechanism

When `arealayer(i_lyr) > currentPatch%area`, `DemoteFromLayer` (`EDCanopyStructureMod.F90:338-783`) moves crown area down. The total to remove is `demote_area = arealayer - currentPatch%area`.

### Stochastic mode (`ED_val_comp_excln >= 0`)

Cohorts in layer `i_lyr` are assigned exclusion weights inversely proportional to a power of height (`EDCanopyStructureMod.F90:410-411`):

```
w_i = 1 / h_i ** beta       where beta = ED_val_comp_excln
```

Shorter cohorts receive larger weights and therefore demote a larger fraction of their crown. The weights are then normalised and scaled so that the cohort-wise demoted areas sum to `demote_area`. Even tall cohorts retain a non-zero probability of being demoted, which is the hallmark of the stochastic PPA extension.

### Deterministic mode (`ED_val_comp_excln < 0`)

The loop runs from the shortest cohort upward (`EDCanopyStructureMod.F90:413` onward) and fully demotes cohorts in rank order until `demote_area` is exhausted. Cohorts whose heights agree within `similar_height_tol` are **grouped as a single tied unit** and demoted in proportion to their crown areas, to avoid arbitrary preferential treatment within a group of identical-sized cohorts (`EDCanopyStructureMod.F90:418-485`).

### Cohort splitting

When the weight `cc_loss` assigned to a cohort is less than its full `c_area` (but greater than `area_target_precision`), the cohort must be split between layers. The split preserves total plant number and biomass (`EDCanopyStructureMod.F90:654-717`):

```fortran
newarea = currentCohort%c_area - cc_loss           ! area kept in upper layer
copyc%n = currentCohort%n * newarea / currentCohort%c_area
currentCohort%n = currentCohort%n - copyc%n        ! = n * cc_loss / c_area
copyc%canopy_layer         = i_lyr                 ! copy stays in upper layer
currentCohort%canopy_layer = i_lyr + 1             ! original is demoted
```

After the split, `carea_allom` is re-invoked on both the copy and the (now smaller) original to refresh `c_area`. The copy is allocated with its own `prt` PARTEH object (via `InitPRTObject` and `Copy`) and its own plant-hydraulics workspace (via `InitHydrCohort` if `hlm_use_planthydro`). It is then inserted into the height-ordered linked list adjacent to the original (`EDCanopyStructureMod.F90:708-717`).

| Property | Original cohort (→ `i_lyr+1`) | Copy (stays in `i_lyr`) |
| --- | --- | --- |
| `canopy_layer` | `i_lyr + 1` | `i_lyr` |
| `n` | `n * cc_loss / c_area` | `n * (c_area - cc_loss) / c_area` |
| `c_area` | Recomputed from new `n` | Recomputed from new `n` |
| Height, DBH, biomass per plant | Unchanged | Unchanged |

After all weights have been applied, `DemoteFromLayer` calls `CanopyLayerArea` on `i_lyr` and errors out if the post-demotion balance check fails beyond `area_check_precision`/`area_check_rel_precision` (`EDCanopyStructureMod.F90:767-777`).

Cohorts whose new `canopy_layer` exceeds `nclmax` are terminated via `terminate_cohort` (`EDCanopyStructureMod.F90:736-744`), and their biomass is routed to the fragmenting litter pools.

### Site-level diagnostics

Each demotion increments (`EDCanopyStructureMod.F90:649-652`, `:698-701`):

- `currentSite%demotion_rate(size_class) += currentCohort%n`
- `currentSite%demotion_carbonflux += (leaf_c + store_c + fnrt_c + sapw_c + struct_c) * currentCohort%n`

## Promotion Mechanism

When `arealayer(i_lyr) < currentPatch%area`, `PromoteIntoLayer` (`EDCanopyStructureMod.F90:787-1236`) fills the gap from layer `i_lyr+1`. The gap size is:

```fortran
promote_area = currentPatch%area - arealayer_current
```

and the lower-layer area is `arealayer_below`. The routine has **two branches**, and it is critical that users of the wiki understand both.

### Branch 1: Promote-all short-circuit (`EDCanopyStructureMod.F90:839-868`)

```fortran
if ( arealayer_below <= promote_area ) then
   ! Promote ALL cohorts from layer i_lyr+1 unconditionally.
   currentCohort => currentPatch%tallest
   do while (associated(currentCohort))
      if (currentCohort%canopy_layer == i_lyr + 1) then
         currentCohort%canopy_layer = i_lyr
         call carea_allom(..., currentCohort%c_area)
         ! update demotion / promotion site diagnostics
      end if
      currentCohort => currentCohort%shorter
   end do
```

When the entire lower layer fits into the gap, **every cohort in `i_lyr+1` is promoted in full, regardless of height and regardless of `ED_val_comp_excln`**. No weighting and no cohort splitting take place in this branch. This short-circuit is routinely triggered immediately after large disturbance events (fire, canopy-opening mortality, logging) that wipe out most of layer 1 while leaving small understory populations intact, and it is the reason why a post-disturbance patch often shows layer 1 populated by the full set of surviving understory cohorts rather than by a height-weighted subset.

### Branch 2: Weighted promotion (`EDCanopyStructureMod.F90:870-1236`)

Only when `arealayer_below > promote_area` does the weighted logic apply. The weighting is the mirror image of demotion:

- **Stochastic mode** (`ED_val_comp_excln >= 0`, `EDCanopyStructureMod.F90:894`): `prom_weight = height ** ED_val_comp_excln`. Taller cohorts in the lower layer get higher weights — the reverse of the demotion formula.
- **Deterministic mode** (`ED_val_comp_excln < 0`): the loop promotes from the tallest downward, with tied-height cohorts (within `similar_height_tol`) grouped and promoted proportionally.

As in demotion, when a selected cohort's `prom_weight` is less than its full `c_area`, the cohort is split into two: one part retains the lower layer, one part is promoted. The splitting mechanics mirror demotion but in the opposite direction, and the site-level `promotion_rate` and `promotion_carbonflux` diagnostics are updated accordingly.

## Layer Area Calculation

`CanopyLayerArea` (`EDCanopyStructureMod.F90:2090-2118`) sums `c_area` over all cohorts whose `canopy_layer` matches the requested index, after refreshing each cohort's `c_area` via `carea_allom`. It is called from multiple points in `canopy_structure`, `DemoteFromLayer`, and `PromoteIntoLayer` to check that the iterative rebalancing is converging.

## Key Data Structures

### Cohort-level (`FatesCohortMod.F90`)

| Field | Type | Purpose |
| --- | --- | --- |
| `canopy_layer` | integer | Current layer index (1 = overstory, 2 = understory) |
| `canopy_layer_yesterday` | real(r8) | Previous day's layer index (weighted average, for transition tracking) |
| `c_area` | real(r8) | Crown area footprint [m²] |
| `excl_weight` | real(r8) | Temporary demotion weight |
| `prom_weight` | real(r8) | Temporary promotion weight |
| `n` | real(r8) | Number density [individuals/patch] |
| `dbh` | real(r8) | Diameter at breast height [cm] |
| `height` | real(r8) | Plant height [m] |
| `pft` | integer | PFT index |
| `crowndamage` | integer | Crown damage class (1 = undamaged) |

### Patch-level (`FatesPatchMod.F90`)

| Field | Purpose |
| --- | --- |
| `NCL_p` | Number of canopy layers currently occupied |
| `total_canopy_area` | Sum of cohort crown areas (m²) used in per-canopy-area aggregations |
| `area` | Total patch area (typically 10 000 m²) |
| `zstar` | Height of shortest cohort in layer 1. **Only updated under strict PPA (`ED_val_comp_excln < 0`)**; in stochastic mode it retains its previous value and should not be used as a dynamic threshold. |
| `canopy_layer_tlai(nclmax)` | Mean LAI per canopy layer, per canopy area |

### Site-level (`EDTypesMod.F90`)

| Field | Purpose |
| --- | --- |
| `spread` | Site-level crown spread, `[0, 1]`. Interpolation weight on `d2ca_max` in `carea_2pwr` |
| `demotion_rate(nlevsclass)` | Individuals demoted per size class [plants/day] |
| `promotion_rate(nlevsclass)` | Individuals promoted per size class [plants/day] |
| `demotion_carbonflux` | Biomass flux from demotion [kgC/day] |
| `promotion_carbonflux` | Biomass flux from promotion [kgC/day] |

## Key Parameters

### Canopy structure controls

| Name | Origin | Value / description |
| --- | --- | --- |
| `nclmax` | `EDParamsMod.F90:98` | **Compile-time Fortran `parameter` = 2**. Not adjustable via the parameter file or namelist. |
| `ED_val_comp_excln` | FATES parameter file | Competitive exclusion exponent. `>= 0` stochastic; `< 0` strict (deterministic rank-ordered) PPA |
| `ED_val_canopy_closure_thresh` | FATES parameter file | Site-level canopy closure threshold used in `canopy_spread` |

### Allometric parameters (PFT-specific, in `prt_params`)

| Name | Code symbol | Description |
| --- | --- | --- |
| `allom_d2ca_coefficient_min` | `d2ca_min` | Minimum crown-area coefficient (crowded canopies) |
| `allom_d2ca_coefficient_max` | `d2ca_max` | Maximum crown-area coefficient (open canopies) |
| `allom_d2bl2` | `d2bl_p2` | Diameter-to-leaf-biomass exponent, reused for crown area |
| `allom_blca_expnt_diff` | `d2bl_ediff` | Offset between crown-area and leaf-biomass exponents |
| `crown_depth_frac` | - | Fraction of tree height occupied by crown |

### Tolerance / precision constants (`EDCanopyStructureMod.F90:70-79`)

| Name | Value | Role |
| --- | --- | --- |
| `area_target_precision` | `1.0E-11` | Target precision for area balancing |
| `area_check_precision` | `1.0E-7` | Absolute tolerance for area checks |
| `area_check_rel_precision` | `1.0E-4` | Relative tolerance |
| `similar_height_tol` | `1.0E-3` m | Tied-height threshold |
| `max_patch_iterations` | `10` | Outer iteration cap |

## Special Cases and Edge Conditions

### No-competition mode

When `hlm_use_nocomp = .true.`, each patch hosts a single PFT. Crown areas are still computed but each PFT occupies its own patch area, so inter-PFT layering is handled by the no-competition machinery rather than by `DemoteFromLayer` / `PromoteIntoLayer`. See `fates-codebase-wiki/advanced/simulation_modes.md` for the details of no-competition mode; note that `use_fates_nocomp` separates PFTs into patches but does not fix areas.

### Satellite phenology mode

When `hlm_use_sp = .true.`, cohort LAI (and therefore crown-area contributions) is prescribed from an external product and much of the canopy-structure algorithm is shortcut.

### Cohort termination

Cohorts demoted into layer `> nclmax` are removed via `terminate_cohort`, with biomass transferred to the fragmenting litter pools. This prevents accumulation of a phantom third or lower layer.

### Tied cohorts

When a run of cohorts has heights agreeing within `similar_height_tol = 1 mm`, both `DemoteFromLayer` and `PromoteIntoLayer` treat them as a group, summing their `c_area` and distributing the demoted/promoted area in proportion to each cohort's share. This avoids arbitrary preferential treatment inside numerically-tied groups.

## Call Sequence

`canopy_structure` is invoked once per day per site as part of the ED dynamics loop. A schematic sequence:

```
canopy_spread(site)              ! daily update of site%spread
  |
  v
canopy_structure(site, bc_in)    ! per-patch rebalancing
  |-- for each patch:
  |     |-- for each layer i_lyr:
  |     |     |-- CanopyLayerArea(...)
  |     |     |-- if over-full: DemoteFromLayer(...)
  |     |     |-- if under-full (and lower layer exists): PromoteIntoLayer(...)
  |     |
  |     |-- recheck all layers; iterate up to max_patch_iterations
  |     |-- set NCL_p and (strict PPA only) zstar
  v
leaf_area_profile(site)          ! builds elai/esai/tlai/tsai profiles
  |
  v
UpdatePatchLAI / UpdateCohortLAI ! per-cohort and per-layer LAI updates
```
