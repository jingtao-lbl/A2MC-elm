---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# LAI and SAI Profiles

<details>
<summary>Relevant source files (FATES commit e027a40)</summary>

- `biogeochem/EDCanopyStructureMod.F90`
- `biogeochem/FatesAllometryMod.F90`
- `biogeochem/FatesPatchMod.F90`
- `radiation/FatesNormanRadMod.F90`
- `radiation/FatesRadiationDriveMod.F90`
- `main/EDParamsMod.F90`

</details>

## Purpose and Scope

LAI (Leaf Area Index) and SAI (Stem Area Index) profiles describe the vertical distribution of leaf and stem area within the canopy. They are the direct inputs to the Norman two-stream radiation transfer model and therefore shape photosynthesis, transpiration, and surface albedo. This page documents how FATES stores these profiles, how they are calculated from cohort state, and how they are aggregated to patch-level totals.

For layer assignment and the Perfect Plasticity Approximation, see [Canopy Layering and Perfect Plasticity](ppa.md). For the radiation solver that consumes these profiles, see `biophysics/radiation.md`.

## Profile Data Structure

Profile variables live in `fates_patch_type` and are three-dimensional arrays indexed by `(canopy layer, PFT, vertical sub-layer)`:

| Dimension | Size | Description |
| --- | --- | --- |
| Canopy layer | runtime size = `NCL_p` (allocated up to `nclmax = 3`) | `nclmax` is a compile-time constant in `EDParamsMod.F90:76` |
| PFT | runtime size = `numpft` (allocated up to `maxpft = 16`) | `numpft` is the run-time count of active PFTs |
| Vertical sub-layer | runtime size = `nveg` (a few above `maxval(nleaf(:,:))`) | bounded by `nlevleaf = 30` (`EDParamsMod.F90:82`) |

### Profile variables (`FatesPatchMod.F90:132-148`)

In e027a40 the profile arrays are **`allocatable`** rather than fixed-size:

```fortran
! exposed leaf area in each canopy layer, pft, and leaf layer [m2 leaf/m2 contributing crown area]
real(r8), allocatable :: elai_profile(:,:,:)  ! nclmax,maxpft,nlevleaf)
real(r8), allocatable :: esai_profile(:,:,:)  ! nclmax,maxpft,nlevleaf)
real(r8), allocatable :: tlai_profile(:,:,:)  ! nclmax,maxpft,nlevleaf)
real(r8), allocatable :: tsai_profile(:,:,:)  ! nclmax,maxpft,nlevleaf)
real(r8), allocatable :: canopy_area_profile(:,:,:) ! nclmax,maxpft,nlevleaf)
integer  :: canopy_mask(nclmax,maxpft)
integer  :: nrad(nclmax,maxpft)              ! number of exposed vegetation layers
integer  :: nleaf(nclmax,maxpft)             ! number of total leaf layers
```

The bound order `(canopy_layer, PFT, vertical_sub_layer)` is unchanged from e85d997. What is new is that the arrays are dynamically reshaped by `cpatch%ReAllocateDynamics()` (`FatesPatchMod.F90:310-411`), called at the start of `leaf_area_profile` (`EDCanopyStructureMod.F90:1038`). The actual shape used for allocation is `(NCL_p, numpft, nveg + 1)`, where `nveg = maxval(nleaf(:,:))` (so allocation is keyed off the *current* canopy structure rather than the compile-time maxima). Reallocation is skipped when the shape has not changed; deallocation+reallocation is triggered when the canopy gains or loses a layer, when `nveg` exceeds the previous bound, or when `nveg` is more than two layers smaller than previously allocated (to avoid thrash, `FatesPatchMod.F90:341-377`).

`nleaf(cl,ft)` records the number of vertical bins actually filled for each canopy layer × PFT, and `nrad(cl,ft)` records the number of exposed (above-snow) layers used by the radiation solver. In the current source `nrad` is set equal to `nleaf` (`EDCanopyStructureMod.F90:1050`), with a TODO comment noting that the snow-occlusion subset is no longer separately tracked.

**Critical unit convention.** `tlai_profile`, `elai_profile`, `tsai_profile`, and `esai_profile` are all expressed **per unit contributing crown area**, not per unit ground area. The source header comment is explicit (`FatesPatchMod.F90:132-139`): `[m2 leaf/m2 contributing crown area]`. To obtain patch-level totals expressed per unit ground area, these profiles must be multiplied by `canopy_area_profile` (which carries the crown-area-to-ground-area weighting) and summed. This is exactly what `calc_areaindex` does (see below).

The `e` prefix (`elai_profile`, `esai_profile`) denotes the **exposed** fraction — the portion of leaf/stem area that is not occluded by snow. The `t` prefix denotes the **total** area including snow-occluded material.

## Calculation Workflow

The relevant subroutines all live in `EDCanopyStructureMod.F90`:

| Routine | Location | Responsibility |
| --- | --- | --- |
| `UpdateCohortLAI` | `:1700-1729` | For one cohort, call `tree_lai_sai` to set `currentCohort%treelai` and `currentCohort%treesai` (both per crown area), and set `currentCohort%nv` (number of filled vertical sub-layers in that cohort's crown) via `GetNVegLayers(treelai + treesai)` |
| `UpdatePatchLAI` | `:1651-1697` | Walk all cohorts from top layer downward (outer loop over `cl = 1, nclmax`). Call `UpdateCohortLAI` on each and accumulate `canopy_layer_tlai(cl)` as an average weighted by `c_area / total_canopy_area` |
| `leaf_area_profile` | `:955-1327` | Build the full `tlai_profile`, `elai_profile`, `tsai_profile`, `esai_profile`, `canopy_area_profile` arrays from cohort state, distributing each cohort's LAI/SAI across `nv` vertical bins. Two implementation branches are gated by the module-local `preserve_b4b` constant: a legacy direct-distribution branch and a branch that delegates to `VegAreaLayer` |
| `calc_areaindex` | `:1553-1615` | Integrate a given profile (`elai`, `tlai`, `esai`, or `tsai`) to a single patch-level scalar (per unit ground area) |

In e027a40, `tree_lai` and `tree_sai` are no longer the public entry points. The single public wrapper is now `tree_lai_sai`:

```fortran
public :: tree_lai_sai       ! LAI and SAI calculations must work together, thus they
                              ! should never be called separately
                              ! (FatesAllometryMod.F90:129)
```

The wrapper is defined at `FatesAllometryMod.F90:839-885` and calls the (now private) functions `tree_lai` (`FatesAllometryMod.F90:667-796`) and `tree_sai` (`FatesAllometryMod.F90:800-835`) internally, then applies a **VAI-capping pass** (`:868-882`):

```fortran
treelai = tree_lai( leaf_c, pft, c_area, nplant, cl, canopy_lai, vcmax25top)

treesai = tree_sai( pft, dbh, crowndamage, canopy_trim, elongf_stem, c_area, nplant, &
                          cl, canopy_lai, treelai, vcmax25top, call_id )

! Don't allow lai+sai to exceed the vertical discretization bounds
if( do_vai_capping ) then
   if( (treelai + treesai) > (sum(dinc_vai)) )then
      treelai = sum(dinc_vai) * (1._r8 - prt_params%allom_sai_scaler(pft)) - nearzero
      treesai = sum(dinc_vai) * prt_params%allom_sai_scaler(pft) - nearzero
   end if
end if
```

`do_vai_capping` is a module-local `logical, parameter :: do_vai_capping = .true.` (`:868`), so the cap is always applied through the public path. `dinc_vai` is the per-bin VAI thickness array of length `nlevleaf` (`EDParamsMod.F90:84`); `sum(dinc_vai)` is the maximum per-cohort VAI the discretisation can represent. When the cap fires, the cohort's leaf area and stem area are reset to fill the discretisation exactly, partitioned by `allom_sai_scaler(pft)` (the SAI:total-VAI ratio).

`tree_lai` (`FatesAllometryMod.F90:667-796`) is the workhorse for individual-cohort LAI. It takes `leaf_c`, `c_area`, `nplant`, and cohort context, computes `leafc_per_unitarea = leaf_c / (c_area/nplant)` (kgC per m² of cohort crown), then integrates an exponential-in-depth SLA profile. The return value is in units of `m² leaf / m² crown`.

`tree_sai` (`FatesAllometryMod.F90:800-835`) scales SAI as:

```fortran
target_lai = tree_lai(target_bleaf, pft, c_area, nplant, cl, canopy_lai, vcmax25top)
tree_sai   = elongf_stem * prt_params%allom_sai_scaler(pft) * target_lai
```

where `target_lai` is `tree_lai` recomputed with `target_bleaf` from `bleaf(dbh, pft, crowndamage, canopy_trim, 1.0_r8, target_bleaf)` (i.e. fully-flushed allometric leaf biomass rather than current leaf biomass). SAI therefore tracks the stable allometric target rather than the current leaf phenology state, but can still be modulated down by stem phenology (`elongf_stem`) for grasses. Note the new arguments compared to e85d997: `crowndamage`, `treelai` (passed in for self-consistency checks), and `call_id` (a tag identifying the calling site for diagnostics).

`UpdateCohortLAI` (`EDCanopyStructureMod.F90:1700-1729`) calls the wrapper:

```fortran
call tree_lai_sai(leaf_c, currentCohort%pft, currentCohort%c_area, currentCohort%n,           &
       currentCohort%canopy_layer, canopy_layer_tlai, currentCohort%vcmax25top, currentCohort%dbh, currentCohort%crowndamage,          &
       currentCohort%canopy_trim, currentCohort%efstem_coh, 4, currentCohort%treelai, treesai )

if (hlm_use_sp .eq. ifalse) then
   currentCohort%treesai = treesai
end if

currentCohort%nv = GetNVegLayers(currentCohort%treelai+currentCohort%treesai)
```

In SP (satellite phenology) mode, the SAI returned by the wrapper is discarded and the cohort's `treesai` is left at whatever was prescribed externally; cohort LAI is also not rebuilt from leaf carbon in SP mode.

## Integrating to Patch Totals: `calc_areaindex`

The function that turns the 3-D profiles into scalar patch totals is `calc_areaindex` (`EDCanopyStructureMod.F90:1553-1615`). Its header comment states the conversion explicitly: *"this is the square meters of leaf per square meter of ground area. It does so by integrating over the depth and functional type profile of leaf area which are per area of crown. This value has to be scaled by crown area to convert to ground area."*

For `ai_type = 'elai'`:

```fortran
ai = 0._r8
do cl = 1, cpatch%NCL_p
   do ft = 1, numpft
      ai = ai + sum( cpatch%canopy_area_profile(cl,ft,1:cpatch%nrad(cl,ft)) * &
                     cpatch%elai_profile(cl,ft,1:cpatch%nrad(cl,ft)) )
   enddo
enddo
ai = max(ai_min, ai)
```

(`EDCanopyStructureMod.F90:1576-1582, :1611`). Three things to note:

1. The profile values (`elai_profile`, in m² leaf / m² crown area) are multiplied by `canopy_area_profile` (the fraction of ground the element covers) to yield the per-ground-area contribution.
2. The sum runs over both PFT and the filled vertical sub-layers up to `nrad(cl, ft)`.
3. A legacy minimum floor `ai = max(ai_min, ai)` with `ai_min = 0.1` (`:1571`) is applied at the end (`:1611`). The source flags this as an artifact from old testing that has been retained to preserve bitwise reproducibility, with a TODO to remove it.

The same function is called for `'tlai'`, `'esai'`, and `'tsai'`, substituting the appropriate profile (`:1583-1604`). These calls produce the four patch-level diagnostics that are exported to the host land model:

| Diagnostic | Profile integrated | Description |
| --- | --- | --- |
| `elai_pa` | `elai_profile` | Exposed LAI per patch (per unit ground area) |
| `tlai_pa` | `tlai_profile` | Total LAI per patch (including snow-occluded) |
| `esai_pa` | `esai_profile` | Exposed SAI per patch |
| `tsai_pa` | `tsai_profile` | Total SAI per patch |

These are accumulated and exported to the HLM in `update_hlm_dynamics` (`EDCanopyStructureMod.F90:1331-1549`).

## `canopy_layer_tlai`: a Different Aggregation

`UpdatePatchLAI` also maintains `currentPatch%canopy_layer_tlai(cl)`, which is a coarser per-layer total (`FatesPatchMod.F90:124-126`, units `m² veg / m² canopy area`). It is accumulated as:

```fortran
currentPatch%canopy_layer_tlai(cl) = currentPatch%canopy_layer_tlai(cl) +  &
     currentCohort%treelai * currentCohort%c_area / currentPatch%total_canopy_area
```

(`EDCanopyStructureMod.F90:1688-1689`). This is the average cohort `treelai` weighted by crown-area fraction of the patch's total canopy area. Its primary use is inside `tree_lai` itself, which takes the `canopy_layer_tlai` of the layer above as `canopy_lai_above` to offset the exponential SLA profile. It is **not** the same quantity as `tlai_pa` from `calc_areaindex`; the two normalise by different areas (canopy area vs ground area).

## Sunlit / Shaded Partitioning

In e85d997 the sun/shade partitioning lived in `biogeophys/EDSurfaceAlbedoMod.F90`. **That file no longer exists at e027a40.** The radiation routines have been reorganised into a top-level `radiation/` directory:

- `radiation/FatesNormanRadMod.F90` — Norman scheme; contains the cumulative-LAI sun-fraction calculation
- `radiation/FatesRadiationDriveMod.F90` — driver that selects between Norman and the two-stream scheme
- `radiation/FatesTwoStreamUtilsMod.F90`, `radiation/TwoStreamMLPEMod.F90` — two-stream solver path
- `radiation/FatesRadiationMemMod.F90` — shared types and constants

LAI is partitioned into sunlit and shaded fractions inside `PatchNormanRadiation` (`FatesNormanRadMod.F90`). The sunlit fraction of each sub-layer is computed from the direct-beam extinction coefficient and cumulative LAI from the top of the canopy (`FatesNormanRadMod.F90:387-405`):

```fortran
if (L == 1)then !top canopy layer
   currentPatch%f_sun(L,ft,iv) = exp(-k_dir(ft) * laisum)* &
        (ftweight(L,ft,iv)/ftweight(L,ft,1))
else
   currentPatch%f_sun(L,ft,iv) = weighted_fsun(L-1)* exp(-k_dir(ft) * laisum)* &
        (ftweight(L,ft,iv)/ftweight(L,ft,1))
endif
```

with `laisum` being the cumulative LAI to the middle of layer `iv` (`FatesNormanRadMod.F90:380-383`). The patch's `f_sun(:,:,:)` array is itself an allocatable 3-D field on the patch (`FatesPatchMod.F90:171`).

Note: the legacy snow-blending operation that was in `biogeophys/EDSurfaceAlbedoMod` (around line 331-334) in e85d997 is now at `FatesNormanRadMod.F90:217-220`:

```fortran
rho_layer(L,ft,iv,ib) = rho_layer(L,ft,iv,ib)*(1.0_r8 - currentPatch%fcansno) &
                      + rho_snow(ib) * currentPatch%fcansno
tau_layer(L,ft,iv,ib) = tau_layer(L,ft,iv,ib)*(1.0_r8 - currentPatch%fcansno) &
                      + tau_snow(ib) * currentPatch%fcansno
```

with `rho_snow = (0.80, 0.55)` (vis, NIR) and `tau_snow = (0.01, 0.01)` declared as module-public arrays at `FatesNormanRadMod.F90:54-58`. `currentPatch%fcansno` is the canopy-snow fraction set in the radiation driver (`FatesRadiationDriveMod.F90:140`).

## Snow Occlusion

The difference between `tlai`/`tsai` and `elai`/`esai` comes from canopy-snow occlusion, computed inside `leaf_area_profile`'s `preserve_b4b = .true.` branch (`EDCanopyStructureMod.F90:1127-1158`):

```fortran
fraction_exposed = 1.0_r8
if(currentSite%snow_depth  > layer_top_height)then
   fraction_exposed = 0._r8
endif
if(currentSite%snow_depth < layer_bottom_height)then
   fraction_exposed = 1._r8
endif
if(currentSite%snow_depth >= layer_bottom_height .and. &
     currentSite%snow_depth <= layer_top_height) then !only partly hidden...
   fraction_exposed = 1._r8 - max(0._r8, (min(1.0_r8, &
        (currentSite%snow_depth - layer_bottom_height)/(layer_top_height-layer_bottom_height))))
endif
...
cpatch%elai_profile(cl,ft,iv) = cpatch%elai_profile(cl,ft,iv) + &
     remainder * fleaf * currentCohort%c_area/cpatch%total_canopy_area * fraction_exposed
```

So the `e`-prefixed profiles are scaled by `fraction_exposed`, while the `t`-prefixed profiles are not. The exposed-area profiles therefore already account for the snow-occluded fraction having been excluded from the photosynthetically active area. The Norman radiation solver's `fcansno` blending (above) operates on top of these exposed profiles to further reduce reflectance/transmittance for the snow-covered fraction of canopy elements.

## Update Timing

Profiles are rebuilt whenever cohort state changes or cohorts cross canopy layers:

| Trigger | Routine invoked | Source |
| --- | --- | --- |
| Daily dynamics, after canopy structure rebalances and `canopy_summarization` updates `total_canopy_area` | `leaf_area_profile` (called from the bottom of `canopy_summarization`) | `EDCanopyStructureMod.F90:921` |
| Per-cohort update inside `leaf_area_profile`'s patch loop | `UpdatePatchLAI` → `UpdateCohortLAI` → `tree_lai_sai` | `EDCanopyStructureMod.F90:1032`, `:1681-1683` |

`leaf_area_profile` first calls `cpatch%ReAllocateDynamics()` (`:1038`) to resize the allocatable profile arrays if needed, then `cpatch%NanDynamics()` and `cpatch%ZeroDynamics()` (`:1041-1042`) to clear them.

## Key Profile Variables Reference

| Variable | Where defined | Units | Meaning |
| --- | --- | --- | --- |
| `elai_profile(cl,ft,iv)` | `FatesPatchMod.F90:133` | m² leaf / m² crown area | Exposed LAI in sub-layer `iv` of `(cl,ft)`. Allocatable. |
| `esai_profile(cl,ft,iv)` | `FatesPatchMod.F90:135` | m² stem / m² crown area | Exposed SAI in sub-layer `iv`. Allocatable. |
| `tlai_profile(cl,ft,iv)` | `FatesPatchMod.F90:137` | m² leaf / m² crown area | Total LAI (incl. snow-occluded). Allocatable. |
| `tsai_profile(cl,ft,iv)` | `FatesPatchMod.F90:139` | m² stem / m² crown area | Total SAI (incl. snow-occluded). Allocatable. |
| `canopy_area_profile(cl,ft,iv)` | `FatesPatchMod.F90:141` | fraction [0, 1] | Fraction of patch ground area covered by this (cl,ft,iv) element. Allocatable. Used as the crown→ground weight in `calc_areaindex`. |
| `canopy_layer_tlai(cl)` | `FatesPatchMod.F90:124` | m² leaf / m² canopy area | Per-layer mean LAI, used internally by `tree_lai` |
| `nleaf(cl,ft)` | `FatesPatchMod.F90:148` | - | Number of filled vertical bins for layer `cl`, PFT `ft` |
| `nrad(cl,ft)` | `FatesPatchMod.F90:147` | - | Number of bins used by radiation; currently equal to `nleaf` |
| `currentCohort%treelai` | `FatesCohortMod.F90:106` | m² leaf / m² crown area | Cohort LAI, per the cohort's own crown footprint |
| `currentCohort%treesai` | `FatesCohortMod.F90:107` | m² stem / m² crown area | Cohort SAI |
| `currentCohort%nv` | `FatesCohortMod.F90:98` | - | Number of vertical bins occupied by this cohort's crown |
