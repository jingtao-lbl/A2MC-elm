---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# Canopy Structure and Competition

<details>
<summary>Relevant source files (FATES commit e027a40)</summary>

- `biogeochem/EDCanopyStructureMod.F90`
- `biogeochem/FatesAllometryMod.F90`
- `biogeochem/FatesCohortMod.F90`
- `biogeochem/FatesPatchMod.F90`
- `main/EDParamsMod.F90`
- `main/EDTypesMod.F90`
- `main/FatesConstantsMod.F90`

</details>

## Purpose and Scope

This page describes how FATES organises vegetation cohorts vertically into discrete canopy layers and manages competition for light among cohorts. The core mechanism is the Perfect Plasticity Approximation (PPA), which assumes that plants can plastically rearrange their crowns to fill available horizontal canopy space. This assignment determines which cohorts occupy the upper canopy (full light) and which are relegated to the understory, and therefore fundamentally shapes carbon gain, growth, and mortality.

For the mechanics of layer assignment (the unified promote-or-demote algorithm), see [Canopy Layering and Perfect Plasticity](ppa.md). For how leaf and stem area are distributed within those layers, see [LAI and SAI Profiles](lai_sai.md). For radiation transfer through the canopy, see `biophysics/radiation.md`.

The driver subroutine is `canopy_structure` (`EDCanopyStructureMod.F90:115`). It is called once per day per site.

## Canopy Layer System

FATES allocates cohorts among a small number of discrete vertical canopy layers:

- **Layer 1**: Upper canopy (overstory). Receives direct + diffuse sunlight.
- **Layer 2**: Understory. Receives only light transmitted through layer 1.
- **Layer 3**: Reserved transient bookkeeping layer (see note below).

The maximum number of layers is set by the Fortran compile-time constant `nclmax` (`EDParamsMod.F90:76`):

```fortran
integer, parameter, public :: nclmax = 3   ! Maximum number of canopy layers allowed
                                            ! We would make this even higher, but making this
                                            ! a little lower keeps the size down on some output arrays
```

Because `nclmax` is a Fortran `parameter`, its value (3) is baked in at compile time and cannot be changed through the parameter file or namelist. **Note**: although `nclmax = 3`, the in-source narrative comment at `EDCanopyStructureMod.F90:122-124` still describes the layering as "More than two layers is not permitted at the moment / Seeds germinating into the 3rd or higher layers are automatically removed." In practice the model still typically operates with at most two occupied layers in steady state. The third layer is transient: cohorts that end up in `canopy_layer = 3` after a rebalance pass are terminated by `terminate_cohorts(currentSite, currentPatch, 3, 17, bc_in)` at `EDCanopyStructureMod.F90:338`. The third layer slot exists so that the unified promote-or-demote routine can hold cohorts mid-rebalance without an array bounds error (see also the `carea_2pwr` comment at `FatesAllometryMod.F90:2633-2641`).

All per-canopy-layer arrays (`canopy_layer_tlai(nclmax)`, `nleaf(nclmax,maxpft)`, `nrad(nclmax,maxpft)`, etc.) are sized for 3 layers in e027a40. Diagnostic harnesses that hardcode "size 2" arrays will under-allocate.

The PPA's key assertion is that when the summed crown area of cohorts in a given layer exceeds `currentPatch%area`, some cohorts must be moved to the layer below. Symmetrically, after disturbance or mortality opens gaps, cohorts can be moved up from below to fill unused space in the upper layer. In e027a40 both directions are handled by a single unified subroutine (see next section).

## Control Flow

`canopy_structure` (`EDCanopyStructureMod.F90:115-381`) iterates the following loop per patch until every layer is balanced within tolerance, or the iteration cap `max_patch_iterations = nclmax + 7` is reached (`EDCanopyStructureMod.F90:182`, `:231-333`):

1. **Demotion phase** (`:243-247`). For each currently occupied layer `i_lyr` from 1 upward, call `CanopyLayerArea` to get the layer's current crown area sum, compute `target_area = max(0, arealayer - (1 - imperfect_fraction) * patch%area)`, and call `PromoteOrDemote(site, patch, i_lyr, demotion_phase, target_area)`.
2. Terminate near-zero-density cohorts and fuse cohorts (`:250-251`).
3. **Promotion phase** (`:262-267`). If at least two layers are occupied, for each layer `i_lyr` from 2 upward, compute the gap in the layer above (`target_area = max(0, (1 - imperfect_fraction) * patch%area - arealayer)`) and call `PromoteOrDemote(site, patch, i_lyr, promotion_phase, target_area)` to draw cohorts from `i_lyr` up into `i_lyr - 1`.
4. Terminate and fuse again (`:270-271`).
5. Recheck all layers (`:284-297`). For every layer except the bottom-most, the absolute deviation `|arealayer - patch%area|` must be below `area_check_precision = 1.0E-7`. For the bottom-most layer, only over-fill (`arealayer - patch%area > area_check_precision`) is flagged. If any layer fails, repeat from step 1.

After convergence, `currentPatch%NCL_p` is set to `min(nclmax, z)` where `z = NumCanopyLayers(currentPatch)` (`:340-353`). Under strict PPA (`comp_excln_exp < 0`), `currentPatch%zstar` is updated to the height of the shortest layer-1 cohort whose next-shorter neighbour is in layer 2 (`:362-375`). In stochastic PPA mode (`comp_excln_exp >= 0`), `zstar` is not updated by `canopy_structure` and should not be interpreted as a dynamic threshold.

Module-level constants (`EDCanopyStructureMod.F90:78-105`):

| Constant | Value | Purpose |
| --- | --- | --- |
| `co_area_target_precision` | `1.0E-9` | Cohort-level precision for partial promote/demote decisions. The new looser value (was `1.0E-11` in e85d997) reflects that with cohort areas up to ~1e4 m² and r8 precision (~1e-15), two orders of margin yield ~1e-9 absolute tolerance |
| `area_check_precision` | `1.0E-7` | Absolute tolerance for post-rebalance layer-area checks |
| `similar_height_tol` | `1.0E-3` m | Heights within 1 mm are treated as tied |
| `imperfect_fraction` | `0.0` | Hook for allowing some imperfection in canopy closure; currently zero so behaviour is unchanged, but appears throughout the rebalancing arithmetic |
| `demotion_phase` | `1` | Integer flag passed to `PromoteOrDemote` for demotion |
| `promotion_phase` | `2` | Integer flag passed to `PromoteOrDemote` for promotion |
| `preserve_b4b` | `.true.` | Toggle for the b4b-preserving leaf area profile branch in `leaf_area_profile` |
| `max_patch_iterations` | `nclmax + 7` (= 10 with `nclmax = 3`) | Outer iteration cap (`:182`); a function of `nclmax`, not a hard-coded literal |

Note: e85d997's `area_check_rel_precision = 1.0E-4` (relative tolerance) is **gone** at e027a40. Only the absolute tolerance `area_check_precision` is enforced.

## The Unified `PromoteOrDemote` Algorithm

In e85d997 demotion and promotion lived in two separate subroutines (`DemoteFromLayer` and `PromoteIntoLayer`). At e027a40 they have been merged into a single subroutine:

```fortran
subroutine PromoteOrDemote(site, patch, target_layer, phase, target_area)
   ! EDCanopyStructureMod.F90:385-715
   integer,intent(in)      :: target_layer ! Canopy layer we draw from
   integer,intent(in)      :: phase        ! promotion or demotion?
   real(r8),intent(in)     :: target_area  ! Area we want to move [m2/ha]
```

The behaviour is dispatched by the `phase` argument (`demotion_phase = 1`, `promotion_phase = 2`). The two phases share the same scratch vector, the same trivial / non-trivial split for the stochastic path, and the same rank-ordered logic for the deterministic path; only the cohort traversal direction and the height-weighting sign differ.

**Direction of traversal** (`:442-448`):

- For `phase = demotion_phase`: walk from `patch%shortest` upward (so shortest cohorts are processed first), and `ilyr_change = +1` (demoted cohorts move from `i_lyr` to `i_lyr + 1`).
- For `phase = promotion_phase`: walk from `patch%tallest` downward, and `ilyr_change = -1` (promoted cohorts move from `i_lyr` to `i_lyr - 1`).

**Stochastic path** (`comp_excln_exp >= 0`, `:477-557`).

- *Trivial branch* (`:483-497`): if `target_area >= group_area` (the requested transfer is at least as large as the entire layer), every cohort in `target_layer` is fully transferred. This is the e027a40 unification of what e85d997 documented as a separate "promote-all short-circuit" branch in `PromoteIntoLayer`. The trivial branch now applies symmetrically to both phases.
- *Non-trivial branch* (`:498-557`): each cohort is assigned a per-cohort transfer quantum
  - demotion: `pd_area_i = c_area_i / (height_i ** comp_excln_exp)` (shorter favoured)
  - promotion: `pd_area_i = c_area_i * (height_i ** comp_excln_exp)` (taller favoured)
  These per-cohort values are summed, and each cohort's actual transfer is `attempt_area = promdem_area * pd_area_i / sumpd_area`. If `attempt_area > c_area`, the cohort is capped at its own `c_area` and the excess is redistributed across cohorts that still have remaining capacity in proportion to that remaining capacity (`:531-556`).

**Deterministic / rank-ordered path** (`comp_excln_exp < 0`, `:559-594`). The loop iterates from the shortest cohort (demotion) or tallest cohort (promotion) and transfers either the cohort's full area or, if the running total would exceed `promdem_area`, only the residual `remainder_area = min(promdem_area - sumpd_area, group_area)`. This `min` automatically truncates without needing a separate trivial-case branch. Cohorts whose heights agree within `similar_height_tol` are grouped as a tied unit and their area is split in proportion to their crown areas (`:576-589`).

**Apply the transfer** (`:601-711`). For each cohort in the layer:

- If `|pd_area - c_area| < co_area_target_precision`, the whole cohort moves: `cohort%canopy_layer += ilyr_change` (`:623-626`).
- Otherwise (partial), allocate a copy of the cohort, partition number density by area fraction (`copyc%n = cohort%n * remainder_area / cohort%c_area`), keep the copy in `target_layer`, send the original to the adjacent layer, recompute both cohorts' `c_area` via `carea_allom`, and splice the copy into the height-sorted linked list (`:628-686`).
- Update the corresponding `demotion_rate` / `promotion_rate` and `demotion_carbonflux` / `promotion_carbonflux` site-level diagnostics (`:691-708`).

See [Canopy Layering and Perfect Plasticity](ppa.md) for full pseudocode, the cohort-splitting table, and edge-case discussion.

## Crown Area Allometry

Crown area is the horizontal ground footprint of a cohort and is the quantity compared to `patch%area` during canopy structure. It is computed by `carea_allom` (`FatesAllometryMod.F90:495-576`) and, for `allom_lmode` cases 1, 2, 3, and 5, by the helper subroutine `carea_2pwr` (`FatesAllometryMod.F90:2606-2663`). `allom_lmode = 4` instead dispatches to `carea_3pwr` (`FatesAllometryMod.F90:2669-` onward), which uses height in addition to dbh.

`carea_2pwr` is a **subroutine**, not a function: per-plant crown area is written back through the `intent(inout)` argument `c_area`. The per-plant value is multiplied by `nplant` at `FatesAllometryMod.F90:572` to yield cohort-level crown area (m²).

The per-plant calculation is (`FatesAllometryMod.F90:2631-2648`):

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

The site-level `spread` factor is a dynamic interpolation weight on `d2ca_max`. When `spread = 1`, `spreadterm = d2ca_max` (crowns expand to their maximum coefficient). When `spread = 0`, `spreadterm = d2ca_min` (crowns are at their minimum). The daily update in `canopy_spread` (`EDCanopyStructureMod.F90:719-773`) drives `spread` toward smaller values (more compact crowns) as site-level woody-cohort layer-1 canopy area approaches `ED_val_canopy_closure_thresh * AREA`. See the [PPA page](ppa.md) for details.

`spread` is initialised from one of two compile-time constants at site setup: `init_spread_near_bare_ground = 1.0` or `init_spread_inventory = 0.0` (`EDTypesMod.F90:76-77`).

### Crown Damage

If `crowndamage > 1`, `carea_2pwr` retrieves a `crown_reduction` factor via `GetCrownReduction` and multiplies per-plant crown area by `(1 - crown_reduction)` (`FatesAllometryMod.F90:2650-2653`). Damaged crowns therefore occupy less horizontal space and are correspondingly less likely to hold a layer-1 slot.

### Crown Depth

In e027a40, crown depth is computed by `CrownDepth` (`FatesAllometryMod.F90:2546-2594`) and is dispatched on the per-PFT integer parameter `allom_dmode`:

```fortran
case (1) ! Default, linear relationship with height
   crown_depth = p1 * height                              ! p1 = allom_h2cd1; plays the old crown_depth_frac role
case (2) ! Power law, akin to Poorter et al. (2006).
   crown_depth = min(height, p1 * height ** p2)           ! p2 = allom_h2cd2
```

The legacy parameter `crown_depth_frac` is **no longer used**. It has been replaced by the triplet:

- `fates_allom_dmode` (integer, `1` = linear, `2` = Poorter power-law),
- `fates_allom_h2cd1` (linear coefficient, equivalent to former `crown_depth_frac` when `allom_dmode = 1`),
- `fates_allom_h2cd2` (Poorter power-law exponent, used only when `allom_dmode = 2`).

## LAI and SAI

Leaf area index (LAI) and stem area index (SAI) are computed at the cohort level by the public wrapper `tree_lai_sai` (`FatesAllometryMod.F90:839-885`), which calls the (now private) per-cohort routines `tree_lai` and `tree_sai` and applies a "VAI capping" pass that prevents `treelai + treesai` from exceeding `sum(dinc_vai)`:

```fortran
if( do_vai_capping ) then
   if( (treelai + treesai) > (sum(dinc_vai)) )then
      treelai = sum(dinc_vai) * (1._r8 - prt_params%allom_sai_scaler(pft)) - nearzero
      treesai = sum(dinc_vai) * prt_params%allom_sai_scaler(pft) - nearzero
   end if
end if
```

(`FatesAllometryMod.F90:868-882`). Because `do_vai_capping = .true.` by default, every call through the public path applies the cap.

Both the cohort-level `treelai` and `treesai` are returned in `m² leaf (or stem) area per m² of the cohort's own crown area`. The full vertical profiles (`tlai_profile`, `elai_profile`, `tsai_profile`, `esai_profile`) are built in `leaf_area_profile` (`EDCanopyStructureMod.F90:955-1327`). Aggregation back to patch-level totals is performed by `calc_areaindex` (`EDCanopyStructureMod.F90:1553-1615`), which weights the profile values by `canopy_area_profile` to convert from per-crown-area to per-ground-area. See the dedicated [LAI and SAI Profiles](lai_sai.md) page for details.

## Canopy Layer Area

`CanopyLayerArea` (`EDCanopyStructureMod.F90:1619-1647`) sums the current `c_area` of all cohorts whose `canopy_layer` matches the requested index, after refreshing `c_area` via `carea_allom`. The signature is:

```fortran
subroutine CanopyLayerArea(currentPatch, site_spread, layer_index, layer_area)
```

Both `site_spread` and `layer_index` are `intent(in)`; `layer_area` is `intent(inout)`. (In e85d997 this was a function returning a value; the e027a40 version is a subroutine returning via `inout` and takes `site_spread` as an explicit argument.) The result is in the same units as `currentPatch%area` (m²). `canopy_structure` and `PromoteOrDemote` both use it.

## Key Data Structures

### Cohort Fields (`FatesCohortMod.F90:82-107`)

| Field | Type | Units | Description |
| --- | --- | --- | --- |
| `pft` | integer | - | PFT index |
| `n` | real(r8) | individuals/area | Number density (default area = 10000 m²) |
| `dbh` | real(r8) | cm | Diameter at breast height |
| `height` | real(r8) | m | Plant height |
| `canopy_layer` | integer | - | Current layer (1 = overstory, 2 = understory, 3 = transient) |
| `canopy_layer_yesterday` | real(r8) | - | Previous day's layer index (real-valued for fusion stability) |
| `crowndamage` | integer | - | Crown damage class (1 = undamaged, >1 = damaged) |
| `excl_weight` | real(r8) | - | Temporary workspace for demotion weight |
| `prom_weight` | real(r8) | - | Temporary workspace for promotion weight |
| `c_area` | real(r8) | m² | Crown area of entire cohort |
| `treelai` | real(r8) | m² leaf / m² crown area | Cohort LAI, per unit crown area |
| `treesai` | real(r8) | m² stem / m² crown area | Cohort SAI, per unit crown area |
| `nv` | integer | - | Number of leaf layers in this cohort's crown |

### Patch Fields (`FatesPatchMod.F90:124-148`)

| Field | Type | Units | Description |
| --- | --- | --- | --- |
| `NCL_p` | integer | - | Number of currently occupied canopy layers (`<= nclmax`) |
| `canopy_layer_tlai(nclmax)` | real(r8) | m² leaf / m² canopy area | Total LAI in each canopy layer (per canopy area, not ground area) |
| `total_canopy_area` | real(r8) | m² | Sum of layer-1 cohort crown areas; the per-canopy-area normalisation |
| `total_tree_area` | real(r8) | m² | Sum of layer-1 *woody* cohort crown areas |
| `total_grass_area` | real(r8) | m² | Sum of layer-1 *non-woody* cohort crown areas |
| `zstar` | real(r8) | m | Height separating layer 1 from layer 2. Only updated under strict PPA (`comp_excln_exp < 0`) |
| `area` | real(r8) | m² | Total patch area |
| `elai_profile(:,:,:)` | real(r8), allocatable | m² leaf / m² crown area | Vertical profile, allocated dynamically by `ReAllocateDynamics` |
| `esai_profile(:,:,:)` | real(r8), allocatable | m² stem / m² crown area | Vertical profile |
| `tlai_profile(:,:,:)` | real(r8), allocatable | m² leaf / m² crown area | Vertical profile (incl. snow-occluded) |
| `tsai_profile(:,:,:)` | real(r8), allocatable | m² stem / m² crown area | Vertical profile (incl. snow-occluded) |
| `canopy_area_profile(:,:,:)` | real(r8), allocatable | fraction [0,1] | Crown-area fraction of patch ground covered by each (cl,ft,iv) bin |
| `nleaf(nclmax,maxpft)` | integer | - | Number of filled vertical bins per (cl,ft) |
| `nrad(nclmax,maxpft)` | integer | - | Same as `nleaf` (currently equal) |

### Site Fields (`EDTypesMod.F90`)

| Field | Type | Units | Description |
| --- | --- | --- | --- |
| `spread` | real(r8) | - | Dynamic crown spread, [0, 1] (interpolation weight on `d2ca_max`) |
| `demotion_rate(:)` | real(r8), allocatable | individuals/timestep | Per-size-class demotion rate |
| `promotion_rate(:)` | real(r8), allocatable | individuals/timestep | Per-size-class promotion rate |
| `demotion_carbonflux` | real(r8) | kgC/ha/day | Biomass flux from demotion |
| `promotion_carbonflux` | real(r8) | kgC/ha/day | Biomass flux from promotion |

### Compile-time site-level constants (`EDTypesMod.F90:76-83`)

| Name | Value | Purpose |
| --- | --- | --- |
| `init_spread_near_bare_ground` | `1.0` | Initial `currentSite%spread` for cold-start sites |
| `init_spread_inventory` | `0.0` | Initial `currentSite%spread` for inventory-initialised sites |
| `area` | `10000.0` m² | Notional area of simulated forest (the `AREA` constant used in `canopy_spread` and elsewhere) |

## Parameter Controls

| Name | Origin | Description | Notes |
| --- | --- | --- | --- |
| `nclmax` | `EDParamsMod.F90:76` | Max number of canopy layers | **Compile-time Fortran `parameter` = 3.** Not runtime-adjustable. |
| `comp_excln_exp` | FATES parameter file (`fates_comp_excln`) | Competitive exclusion exponent | `>= 0` stochastic; `< 0` strict PPA. Was named `ED_val_comp_excln` in e85d997 |
| `ED_val_canopy_closure_thresh` | FATES parameter file | Canopy closure threshold for spread update | Used in `canopy_spread` |
| `allom_d2ca_coefficient_min` | PFT | Min crown-area coefficient | `d2ca_min` in code |
| `allom_d2ca_coefficient_max` | PFT | Max crown-area coefficient | `d2ca_max` in code |
| `allom_d2bl2` | PFT | Leaf-biomass allometry exponent | `d2bl_p2` in code (reused for crown area) |
| `allom_blca_expnt_diff` | PFT | Crown-area-vs-leaf-biomass exponent offset | `d2bl_ediff` in code (default 0) |
| `allom_sai_scaler` | PFT | SAI:LAI ratio | Used in `tree_sai` and in the VAI cap |
| `allom_dmode` | PFT (integer) | Crown-depth dispatcher (1 = linear, 2 = Poorter) | Replaces former `crown_depth_frac` parameter |
| `allom_h2cd1` | PFT | Linear coefficient or Poorter prefactor for crown depth | Plays role of former `crown_depth_frac` when `allom_dmode = 1` |
| `allom_h2cd2` | PFT | Poorter power-law exponent for crown depth | Used only when `allom_dmode = 2` |

## Integration with Other Systems

- **Radiation**: Layer assignment controls which cohorts are in the direct-beam path. The Norman two-stream radiation solver walks layer-wise through `elai_profile` / `esai_profile`. The legacy `EDSurfaceAlbedo` module from earlier tags has been removed at e027a40; the sun/shade machinery now lives in `radiation/FatesNormanRadMod.F90` (see `:387-405`). See `biophysics/radiation.md`.
- **Photosynthesis and allocation**: Upper-canopy cohorts experience high light and favourable growth; understory cohorts may exhibit prolonged negative carbon balance and trigger carbon-starvation mortality. See `plant-physiology/parteh/index.md` and `plant-physiology/mortality.md`.
- **Disturbance and recruitment**: New recruits enter the lowest available layer. Disturbance (fire, mortality, logging) can open gaps in layer 1 that are filled by promotion on the next daily call. See `core-dynamics/patches.md`.
- **Host land model handoff**: `update_hlm_dynamics` (`EDCanopyStructureMod.F90:1331-1549`) packages `htop_pa`, `hbot_pa`, `canopy_fraction_pa`, `dleaf_pa`, `z0m_pa`, `displa_pa`, etc. for export to the HLM.
