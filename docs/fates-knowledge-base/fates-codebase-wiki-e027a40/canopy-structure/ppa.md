---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# Canopy Layering and Perfect Plasticity

<details>
<summary>Relevant source files (FATES commit e027a40)</summary>

- `biogeochem/EDCanopyStructureMod.F90`
- `biogeochem/FatesAllometryMod.F90`
- `biogeochem/FatesCohortMod.F90`
- `biogeochem/FatesPatchMod.F90`
- `main/EDParamsMod.F90`
- `main/EDTypesMod.F90`

</details>

## Purpose and Scope

This page documents how FATES organises cohorts into discrete canopy layers using the Perfect Plasticity Approximation (PPA), and how the layer assignment is updated daily via the unified `PromoteOrDemote` subroutine. For the overall system context and the crown-area allometry, see the [Canopy Structure and Competition overview](index.md). For how leaf and stem area are then distributed within a layer, see [LAI and SAI Profiles](lai_sai.md).

## Perfect Plasticity Approximation

The PPA (Purves et al. 2008; extended in Fisher et al. 2010) assumes that plants can fully adjust their canopy position, size, shape, and depth to fill available horizontal space. The layer assignment therefore reduces to a bookkeeping operation: if the sum of cohort crown areas in canopy layer `i` exceeds the patch area, some cohort or fraction of a cohort must be moved to layer `i+1`.

FATES's implementation extends the original PPA with:

- **Stochastic competition** controlled by the parameter `comp_excln_exp` (named `ED_val_comp_excln` in earlier source), so that tall cohorts are not guaranteed a canopy slot.
- **Dynamic crown spread** via `currentSite%spread`, which rescales the crown-area allometry daily in response to site-level canopy closure.
- **Multiple canopy layers up to `nclmax = 3`**, a Fortran compile-time `parameter` (`EDParamsMod.F90:76`). In practice the model still typically operates with at most two occupied layers, but the third slot is allowed during rebalance bookkeeping; cohorts that end up in layer 3 after a rebalance pass are terminated by `terminate_cohorts(currentSite, currentPatch, 3, 17, bc_in)` at `EDCanopyStructureMod.F90:338`.

## `canopy_structure` Driver Loop

The entry point `canopy_structure` (`EDCanopyStructureMod.F90:115-381`) walks each patch and, for each patch, iterates a demotion + promotion + recheck cycle until the layers balance within tolerance:

1. **Demotion phase** (`:243-247`): for layers 1 through `z = NumCanopyLayers(currentPatch)`, compute the layer's crown-area sum via `CanopyLayerArea`, then call
   ```fortran
   target_area = max(0._r8, arealayer - (1._r8 - imperfect_fraction)*currentPatch%area)
   call PromoteOrDemote(currentSite, currentPatch, i_lyr, demotion_phase, target_area)
   ```
   `target_area` is the excess area to push down. The trivial case `target_area < nearzero` short-circuits inside `PromoteOrDemote`.
2. Terminate near-zero-density cohorts and fuse cohorts (`:250-251`).
3. **Promotion phase** (`:262-267`): for layers 2 through `z`, compute the gap in the layer above, then call `PromoteOrDemote` with `phase = promotion_phase` to draw cohorts from `i_lyr` up into `i_lyr - 1`.
4. Terminate and fuse again (`:270-271`).
5. **Recheck** (`:284-297`): for every layer except the bottom-most, the absolute deviation `|arealayer - patch%area|` must lie below `area_check_precision`. For the bottom-most layer, only over-fill is flagged.
6. Repeat from step 1 until all layers are balanced or `max_patch_iterations = nclmax + 7` (= 10 with `nclmax = 3`) iterations are exhausted (`:182`, `:303-331`); failure to converge calls `endrun`.

After convergence, `currentPatch%NCL_p` is set to `min(nclmax, z)` (`:340-353`). Under **strict PPA** (`comp_excln_exp < 0`), `currentPatch%zstar` is updated to the height of the shortest layer-1 cohort whose next-shorter neighbour is in layer 2 (`:362-375`). In **stochastic mode** (`comp_excln_exp >= 0`), `zstar` is not assigned here and carries whatever value it previously held; it is not a meaningful dynamic threshold in that regime.

### Module-level constants (`EDCanopyStructureMod.F90:78-105`, `:182`)

| Name | Value | Role |
| --- | --- | --- |
| `co_area_target_precision` | `1.0E-9` | Cohort-level precision for partial-vs-whole promote/demote decisions (was `area_target_precision = 1.0E-11` in e85d997; loosened by two orders of magnitude to reflect r8 precision relative to typical cohort areas of ~1e4 m²) |
| `area_check_precision` | `1.0E-7` | Absolute tolerance for post-rebalance layer-area checks |
| `similar_height_tol` | `1.0E-3` m | Tied-height threshold |
| `imperfect_fraction` | `0.0` | Hook for allowing some imperfection in canopy closure; currently zero so behaviour is unchanged |
| `demotion_phase` | `1` | Integer flag passed to `PromoteOrDemote` |
| `promotion_phase` | `2` | Integer flag passed to `PromoteOrDemote` |
| `max_patch_iterations` | `nclmax + 7` (= 10) | Outer iteration cap, derived from `nclmax` rather than hard-coded |

Note: e85d997's `area_check_rel_precision = 1.0E-4` (relative tolerance) is **gone** in e027a40. Only the absolute tolerance is enforced.

## Crown Area and Canopy Spread

Each cohort's crown area is computed by `carea_allom` (`FatesAllometryMod.F90:495-576`), which dispatches on `allom_lmode` and calls `carea_2pwr` (`FatesAllometryMod.F90:2606-2663`) for cases 1, 2, 3, and 5, or `carea_3pwr` for case 4. `carea_2pwr` is a **subroutine**, not a function; it writes the per-plant crown area back through its `intent(inout)` argument `c_area`, and `carea_allom` then multiplies by `nplant` at `FatesAllometryMod.F90:572` to produce the cohort-level value in m².

### The spread interpolation formula

The per-plant calculation in `carea_2pwr` is (`FatesAllometryMod.F90:2631-2648`):

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

**Direction**. `spread` is the interpolation weight on `d2ca_max`. When `spread = 1`, `spreadterm = d2ca_max` and crowns are at their widest. When `spread = 0`, `spreadterm = d2ca_min` and crowns are at their most compact. The daily `canopy_spread` update (next section) drives `spread` downward when site-level layer-1 woody canopy area approaches closure and upward when the canopy is open, so crowns contract as the canopy closes and expand as it opens. Trees become "narrower and taller" in crowded conditions and "wider" in open conditions.

### `canopy_spread` daily update

The site-level `spread` factor is updated once per day by `canopy_spread` (`EDCanopyStructureMod.F90:719-773`). The logic:

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

with `AREA = 10000.0` m² (`EDTypesMod.F90:82`). Interpretation: when the woody-cohort layer-1 canopy area exceeds `ED_val_canopy_closure_thresh * AREA`, `spread` is decremented by 0.05 (crowns contract next day). Otherwise `spread` is incremented by 0.05 (crowns expand). The result is then clamped to `[0, 1]`.

`spread` is initialised at site setup from one of two compile-time constants in `EDTypesMod.F90:76-77`: `init_spread_near_bare_ground = 1.0` (cold-start) or `init_spread_inventory = 0.0` (inventory-initialised).

## The Unified `PromoteOrDemote` Algorithm

In e85d997 demotion and promotion lived in two separate subroutines. At e027a40 they have been merged into a single subroutine that takes a `phase` argument:

```fortran
subroutine PromoteOrDemote(site, patch, target_layer, phase, target_area)
   ! EDCanopyStructureMod.F90:385-715
   integer,intent(in)      :: target_layer ! Canopy layer we draw from
   integer,intent(in)      :: phase        ! demotion_phase (1) or promotion_phase (2)
   real(r8),intent(in)     :: target_area  ! Area we want to move [m2/ha]
```

The two phases share scratch space, the trivial / non-trivial split, and the rank-ordered logic; only the cohort traversal direction and the height-weighting sign differ.

### Step 1: Build the layer's cohort list (`:431-470`)

A scratch vector `patch%co_scr` is filled with pointers to every cohort whose `canopy_layer == target_layer`. Each cohort's `c_area` is refreshed with `carea_allom`. The traversal direction depends on `phase`:

- `demotion_phase`: walk from `patch%shortest` upward (so shorter cohorts are processed first), `ilyr_change = +1`.
- `promotion_phase`: walk from `patch%tallest` downward, `ilyr_change = -1`.

The summed crown area in the layer is `group_area`, and the actual amount to move is `promdem_area = min(target_area, group_area)`.

### Step 2: Compute per-cohort transfer areas

#### Stochastic mode (`comp_excln_exp >= 0`, `:477-557`)

There are two sub-branches:

**Trivial branch** (`:483-497`). If `target_area >= group_area`, the requested transfer is at least as large as the entire layer. Every cohort in the layer is fully transferred:

```fortran
if_not_trivial: if(target_area >= group_area)then
   do ic = 1,n_layer
      layer_co(ic)%pd_area = layer_co(ic)%p%c_area
   end do
else
   ! ... weighted distribution ...
end if if_not_trivial
```

This trivial branch unifies what e85d997 documented as a separate "promote-all short-circuit" (only on the promotion side). At e027a40 it applies symmetrically to both phases. It is the path triggered immediately after large disturbance events (fire, canopy-opening mortality, logging) that wipe out most of the layer above and leave small understory populations to be promoted in full.

**Non-trivial weighted branch** (`:498-557`). Each cohort gets a per-cohort transfer quantum `pd_area_i`:

- demotion: `pd_area_i = c_area_i / (height_i ** comp_excln_exp)` (shorter favoured)
- promotion: `pd_area_i = c_area_i * (height_i ** comp_excln_exp)` (taller favoured)

The quantum is normalised so that `attempt_area = promdem_area * pd_area_i / sumpd_area`. If a cohort's `attempt_area` exceeds its `c_area`, the cohort is capped at its own `c_area` and the excess is redistributed across cohorts that still have remaining capacity, proportionally to the remaining capacity (`:531-556`):

```fortran
do ic = 1,n_layer
   cohort => layer_co(ic)%p
   if (abs(layer_co(ic)%pd_area-cohort%c_area) > nearzero) then
      layer_co(ic)%pd_area = layer_co(ic)%pd_area + &
           (excess_area/remainder_area) * &
           (cohort%c_area - layer_co(ic)%pd_area)
   end if
end do
```

#### Rank-ordered (deterministic) mode (`comp_excln_exp < 0`, `:565-593`)

The loop iterates from the shortest cohort (demotion) or tallest cohort (promotion):

```fortran
do while( ic<=n_layer .and. (promdem_area-sumpd_area)>co_area_target_precision)
   ! Group with later cohorts of similar height
   group_area = cohort%c_area
   ic_n       = ic
   check_next:do while(ic_n<n_layer)
      if( abs(cohort%height-layer_co(ic_n+1)%p%height) > similar_height_tol ) then
         exit check_next
      else
         ic_n = ic_n + 1
         group_area = group_area+layer_co(ic_n)%p%c_area
      end if
   end do check_next

   remainder_area = min(promdem_area-sumpd_area,group_area)
   do ic_nn = ic,ic_n
      layer_co(ic_nn)%pd_area = remainder_area*layer_co(ic_nn)%p%c_area/group_area
      sumpd_area = sumpd_area + layer_co(ic_nn)%pd_area
   end do
   ic = ic_n + 1
end do
```

The `min(promdem_area - sumpd_area, group_area)` truncation automatically handles the trivial case (when the requested transfer exceeds the available area) without needing a separate branch. Tied-height cohorts (within `similar_height_tol = 1 mm`) are grouped and split in proportion to their crown areas, to avoid arbitrary preferential treatment within numerically-tied groups.

### Step 3: Apply the transfer (`:601-711`)

For each cohort in the scratch vector:

```fortran
whole_or_part: if( ((pd_area - c_area) > co_area_target_precision) .or. (pd_area < 0._r8) ) then
   ! Negative or larger-than-cohort: error and abort.
   call endrun(...)

elseif ( abs(pd_area - c_area) < co_area_target_precision ) then
   ! Whole cohort: just bump its layer index.
   cohort%canopy_layer = cohort%canopy_layer + ilyr_change

elseif( pd_area > 0._r8 ) then
   ! Partial cohort: split.
   ...
end if whole_or_part
```

#### Cohort splitting (partial branch, `:628-686`)

When the assigned `pd_area` is strictly between `co_area_target_precision` and `c_area`, the cohort must be split between layers. The split preserves total plant number:

```fortran
allocate(copyc)
copyc%prt => null()
call InitPRTObject(copyc%prt)
if( hlm_use_planthydro.eq.itrue ) then
   call InitHydrCohort(site, copyc)
endif
call cohort%Copy(copyc)
call copyc%InitPRTBoundaryConditions()

remainder_area = cohort%c_area - layer_co(ic)%pd_area
copyc%n = cohort%n * min(1._r8, max(0._r8, remainder_area/cohort%c_area))
cohort%n = cohort%n - copyc%n

! The copy stays in the source layer
copyc%canopy_layer = cohort%canopy_layer
! The original moves
cohort%canopy_layer = cohort%canopy_layer + ilyr_change

call carea_allom(copyc%dbh, copyc%n, site%spread, copyc%pft, copyc%crowndamage, copyc%c_area)
call carea_allom(cohort%dbh, cohort%n, site%spread, cohort%pft, cohort%crowndamage, cohort%c_area)
```

The copy is then spliced into the height-sorted linked list adjacent to the original (`:673-685`).

| Property | Original cohort (→ adjacent layer) | Copy (stays in source layer) |
| --- | --- | --- |
| `canopy_layer` | `target_layer + ilyr_change` | `target_layer` |
| `n` | `n_orig * pd_area / c_area_orig` | `n_orig * (c_area_orig - pd_area) / c_area_orig` |
| `c_area` | Recomputed from new `n` via `carea_allom` | Recomputed from new `n` via `carea_allom` |
| `dbh`, `height`, biomass per plant | Unchanged | Unchanged |
| PARTEH / hydraulics | Existing state | Freshly allocated (`InitPRTObject`, `InitHydrCohort`) and copied from original (`cohort%Copy(copyc)`) |

### Step 4: Site-level diagnostics (`:691-708`)

Each transferred cohort increments either the demotion or promotion site-level counters:

```fortran
if(phase==demotion_phase) then
   site%demotion_rate(cohort%size_class) = site%demotion_rate(cohort%size_class) + cohort%n
   site%demotion_carbonflux = site%demotion_carbonflux + &
        (leaf_c + store_c + fnrt_c + sapw_c + struct_c) * cohort%n
else
   site%promotion_rate(cohort%size_class) = site%promotion_rate(cohort%size_class) + cohort%n
   site%promotion_carbonflux = site%promotion_carbonflux + &
        (leaf_c + store_c + fnrt_c + sapw_c + struct_c) * cohort%n
end if
```

After all cohorts have been processed, control returns to `canopy_structure`, which performs the next phase or rechecks balance. There is no longer a per-routine balance check inside `PromoteOrDemote`; the outer loop's recheck step (`canopy_structure:284-297`) is the single point of failure.

### Cohort termination outside `nclmax`

Cohorts whose `canopy_layer` exceeds `nclmax` after the rebalance loop are terminated by `terminate_cohorts(currentSite, currentPatch, 3, 17, bc_in)` (`EDCanopyStructureMod.F90:338`). Their biomass is routed to the fragmenting litter pools.

## Layer Area Calculation

`CanopyLayerArea` (`EDCanopyStructureMod.F90:1619-1647`) sums `c_area` over all cohorts whose `canopy_layer` matches the requested index, after refreshing each cohort's `c_area` via `carea_allom`. The signature is:

```fortran
subroutine CanopyLayerArea(currentPatch, site_spread, layer_index, layer_area)
   type(fates_patch_type),intent(inout), target :: currentPatch
   real(r8),intent(in)                          :: site_spread
   integer,intent(in)                           :: layer_index
   real(r8),intent(inout)                       :: layer_area
```

Both `site_spread` and `layer_index` are `intent(in)`; `layer_area` is `intent(inout)`. (In e85d997 this was a function returning a value; the e027a40 version is a subroutine that takes `site_spread` as an explicit argument and returns through `layer_area`.) It is called from `canopy_structure` to check whether each layer is balanced against the patch area.

## Key Data Structures

### Cohort-level (`FatesCohortMod.F90:82-107`)

| Field | Type | Purpose |
| --- | --- | --- |
| `canopy_layer` | integer | Current layer index (1 = overstory, 2 = understory, 3 = transient) |
| `canopy_layer_yesterday` | real(r8) | Previous day's layer index (real-valued for fusion stability) |
| `c_area` | real(r8) | Crown area footprint [m²] |
| `excl_weight` | real(r8) | Temporary demotion weight |
| `prom_weight` | real(r8) | Temporary promotion weight |
| `n` | real(r8) | Number density [individuals/area] |
| `dbh` | real(r8) | Diameter at breast height [cm] |
| `height` | real(r8) | Plant height [m] |
| `pft` | integer | PFT index |
| `crowndamage` | integer | Crown damage class (1 = undamaged, >1 = damaged) |

### Patch-level (`FatesPatchMod.F90:124-148`)

| Field | Purpose |
| --- | --- |
| `NCL_p` | Number of canopy layers currently occupied (`<= nclmax`) |
| `total_canopy_area` | Sum of layer-1 cohort crown areas (m²); the per-canopy-area normalisation |
| `total_tree_area` | Sum of layer-1 *woody* cohort crown areas (m²) |
| `total_grass_area` | Sum of layer-1 *non-woody* cohort crown areas (m²) |
| `area` | Total patch area (typically 10 000 m²) |
| `zstar` | Height of shortest cohort in layer 1. **Only updated under strict PPA (`comp_excln_exp < 0`)**; in stochastic mode it retains its previous value and should not be used as a dynamic threshold. |
| `canopy_layer_tlai(nclmax)` | Mean LAI per canopy layer, per canopy area |

### Site-level (`EDTypesMod.F90:531-586`)

| Field | Purpose |
| --- | --- |
| `spread` | Site-level crown spread, `[0, 1]`. Interpolation weight on `d2ca_max` in `carea_2pwr` |
| `demotion_rate(:)` | Allocatable, per-size-class individuals demoted per FATES timestep |
| `promotion_rate(:)` | Allocatable, per-size-class individuals promoted per FATES timestep |
| `demotion_carbonflux` | Biomass flux from demotion [kgC/ha/day] |
| `promotion_carbonflux` | Biomass flux from promotion [kgC/ha/day] |

## Key Parameters

### Canopy structure controls

| Name | Origin | Value / description |
| --- | --- | --- |
| `nclmax` | `EDParamsMod.F90:76` | **Compile-time Fortran `parameter` = 3**. Not adjustable via the parameter file or namelist. |
| `comp_excln_exp` | FATES parameter file (JSON key `fates_comp_excln`) | Competitive exclusion exponent. `>= 0` stochastic; `< 0` strict (deterministic rank-ordered) PPA. Renamed from `ED_val_comp_excln` in e85d997. |
| `ED_val_canopy_closure_thresh` | FATES parameter file | Site-level canopy closure threshold used in `canopy_spread` |

### Allometric parameters (PFT-specific, in `prt_params`)

| Name | Code symbol | Description |
| --- | --- | --- |
| `allom_d2ca_coefficient_min` | `d2ca_min` | Minimum crown-area coefficient (crowded canopies) |
| `allom_d2ca_coefficient_max` | `d2ca_max` | Maximum crown-area coefficient (open canopies) |
| `allom_d2bl2` | `d2bl_p2` | Diameter-to-leaf-biomass exponent, reused for crown area |
| `allom_blca_expnt_diff` | `d2bl_ediff` | Offset between crown-area and leaf-biomass exponents (default 0) |
| `allom_dmode` | - | Crown-depth dispatcher (1 = linear, 2 = Poorter power-law). Replaces former `crown_depth_frac` parameter. |
| `allom_h2cd1` | - | Linear coefficient (when `allom_dmode = 1`, plays the role of former `crown_depth_frac`); Poorter prefactor (when `allom_dmode = 2`) |
| `allom_h2cd2` | - | Poorter power-law exponent (used only when `allom_dmode = 2`) |
| `allom_sai_scaler` | - | SAI:LAI ratio used in `tree_sai` and the VAI cap |

### Tolerance / precision constants (`EDCanopyStructureMod.F90:78-105`, `:182`)

| Name | Value | Role |
| --- | --- | --- |
| `co_area_target_precision` | `1.0E-9` | Cohort-level precision for partial promote/demote decisions (was `area_target_precision = 1.0E-11`) |
| `area_check_precision` | `1.0E-7` | Absolute tolerance for area checks |
| `similar_height_tol` | `1.0E-3` m | Tied-height threshold |
| `imperfect_fraction` | `0.0` | Hook for imperfect canopy closure |
| `max_patch_iterations` | `nclmax + 7` (= 10) | Outer iteration cap |

## Special Cases and Edge Conditions

### No-competition mode

When `hlm_use_nocomp = .true.`, each patch hosts a single PFT. Crown areas are still computed but each PFT occupies its own patch area, so inter-PFT layering is handled by the no-competition machinery rather than by `PromoteOrDemote`. See `fates-codebase-wiki/advanced/simulation_modes.md` for the details of no-competition mode; note that `use_fates_nocomp` separates PFTs into patches but does not fix areas.

### Satellite phenology mode

When `hlm_use_sp = .true.`, cohort LAI (and therefore crown-area contributions) is prescribed from an external product and much of the canopy-structure algorithm is shortcut. `canopy_summarization` (`EDCanopyStructureMod.F90:778-930`) enforces that there is exactly one cohort per SP patch and aborts if `total_canopy_area > patch%area` by more than `area_error_1`.

### Cohort termination

Cohorts that end up in `canopy_layer = 3` (i.e. above `nclmax = 3` minus the working ceiling of 2 active layers) after a rebalance pass are terminated via `terminate_cohorts(...,3,17,bc_in)` at `EDCanopyStructureMod.F90:338`. Biomass is transferred to the fragmenting litter pools. This prevents accumulation of phantom upper layers.

### Tied cohorts

When a run of cohorts has heights agreeing within `similar_height_tol = 1 mm`, the rank-ordered branch of `PromoteOrDemote` treats them as a group, summing their `c_area` and distributing the demoted/promoted area in proportion to each cohort's share. This avoids arbitrary preferential treatment within numerically-tied groups.

### Trivial transfer

The stochastic-mode "trivial branch" (where `target_area >= group_area`) and the rank-ordered `min(promdem_area - sumpd_area, group_area)` truncation both handle the case where the requested transfer is at least as large as the entire layer. In e85d997 this trivial case was an explicit `if(arealayer_below <= promote_area)` branch only on the promotion side; in e027a40 it is symmetric across both phases and lives within the unified routine.

## Call Sequence

`canopy_structure` is invoked once per day per site as part of the ED dynamics loop. A schematic sequence:

```
canopy_spread(site)              ! daily update of site%spread
  |
  v
canopy_structure(site, bc_in)    ! per-patch rebalancing
  |-- for each patch:
  |     |-- demotion phase: for each layer i_lyr:
  |     |     |-- CanopyLayerArea(patch, site%spread, i_lyr, arealayer)
  |     |     |-- PromoteOrDemote(site, patch, i_lyr, demotion_phase, target_area)
  |     |
  |     |-- terminate_cohorts + fuse_cohorts
  |     |
  |     |-- promotion phase (if z > 1): for each layer i_lyr from 2 upward:
  |     |     |-- CanopyLayerArea(patch, site%spread, i_lyr-1, arealayer)
  |     |     |-- PromoteOrDemote(site, patch, i_lyr, promotion_phase, target_area)
  |     |
  |     |-- terminate_cohorts + fuse_cohorts
  |     |
  |     |-- recheck all layers; iterate up to max_patch_iterations
  |     |-- terminate_cohorts(..., 3, 17, ...) on layer 3
  |     |-- set NCL_p, and (strict PPA only) zstar
  v
canopy_summarization(...)        ! sum total_canopy_area, total_tree_area, total_grass_area
  |
  v
leaf_area_profile(site)          ! builds elai/esai/tlai/tsai profiles
  |
  v
update_hlm_dynamics(...)         ! exports htop_pa, hbot_pa, canopy_fraction_pa, etc. to HLM
```
