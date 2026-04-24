# LAI and SAI Profiles

<details>
<summary>Relevant source files (FATES commit e85d997)</summary>

- `biogeochem/EDCanopyStructureMod.F90`
- `biogeochem/FatesAllometryMod.F90`
- `biogeochem/FatesPatchMod.F90`
- `biogeophys/EDSurfaceAlbedoMod.F90`

</details>

## Purpose and Scope

LAI (Leaf Area Index) and SAI (Stem Area Index) profiles describe the vertical distribution of leaf and stem area within the canopy. They are the direct inputs to the Norman two-stream radiation transfer model and therefore shape photosynthesis, transpiration, and surface albedo. This page documents how FATES stores these profiles, how they are calculated from cohort state, and how they are aggregated to patch-level totals.

For layer assignment and the Perfect Plasticity Approximation, see [Canopy Layering and Perfect Plasticity](ppa.md). For the radiation solver that consumes these profiles, see `biophysics/radiation.md`.

## Profile Data Structure

Profile variables live in `fates_patch_type` and are three-dimensional arrays indexed by `(canopy layer, PFT, vertical sub-layer)`:

| Dimension | Size parameter | Description |
| --- | --- | --- |
| Canopy layer | `nclmax` | Compile-time constant = 2 (`EDParamsMod.F90:98`) |
| PFT | `maxpft` | Maximum PFTs compiled in |
| Vertical sub-layer | `nlevleaf` | Number of vertical discretisation bins within a canopy layer |

### Profile variables (`FatesPatchMod.F90:99-103`)

```fortran
real(r8) :: elai_profile(nclmax,maxpft,nlevleaf)
    ! exposed leaf area [m2 leaf / m2 contributing crown area]
real(r8) :: esai_profile(nclmax,maxpft,nlevleaf)
    ! exposed stem area [m2 stem / m2 contributing crown area]
real(r8) :: tlai_profile(nclmax,maxpft,nlevleaf)
    ! total (including snow-occluded) leaf area [m2 leaf / m2 contributing crown area]
real(r8) :: tsai_profile(nclmax,maxpft,nlevleaf)
    ! total stem area [m2 stem / m2 contributing crown area]
real(r8) :: canopy_area_profile(nclmax,maxpft,nlevleaf)
    ! fraction of patch ground area occupied by this (cl, ft, iv) element [0-1]
```

**Critical unit convention.** `tlai_profile`, `elai_profile`, `tsai_profile`, and `esai_profile` are all expressed **per unit contributing crown area**, not per unit ground area. The source header comment is explicit (`FatesPatchMod.F90:99-100`): `[m2 leaf/m2 contributing crown area]`. To obtain patch-level totals expressed per unit ground area, these profiles must be multiplied by `canopy_area_profile` (which carries the crown-area-to-ground-area weighting) and summed. This is exactly what `calc_areaindex` does (see below).

The `e` prefix (`elai_profile`, `esai_profile`) denotes the **exposed** fraction — the portion of leaf/stem area that is not occluded by snow. The `t` prefix denotes the **total** area including snow-occluded material.

## Calculation Workflow

The relevant subroutines all live in `EDCanopyStructureMod.F90`:

| Routine | Location | Responsibility |
| --- | --- | --- |
| `UpdateCohortLAI` | `:2171-2206` | For one cohort, call `tree_lai` and `tree_sai` to set `currentCohort%treelai` and `currentCohort%treesai` (both per crown area), and set `currentCohort%nv` (number of filled vertical sub-layers in that cohort's crown) |
| `UpdatePatchLAI` | `:2122-2168` | Walk all cohorts from top layer downward. Call `UpdateCohortLAI` on each and accumulate `canopy_layer_tlai(cl)` as an average weighted by `c_area / total_canopy_area` |
| `leaf_area_profile` | `:1467-1794` | Build the full `tlai_profile`, `elai_profile`, `tsai_profile`, `esai_profile`, `canopy_area_profile`, and `layer_height_profile` arrays from cohort state, distributing each cohort's LAI/SAI across `nlevleaf` vertical bins |
| `calc_areaindex` | `:2024-2086` | Integrate a given profile (`elai`, `tlai`, `esai`, or `tsai`) to a single patch-level scalar (per unit ground area) |

`tree_lai` (`FatesAllometryMod.F90:636-761`) is the workhorse for individual-cohort LAI. It takes `leaf_c`, `c_area`, `nplant`, and cohort context, computes `leafc_per_unitarea = leaf_c / (c_area/nplant)` (kgC per m² of cohort crown), then integrates an exponential-in-depth SLA profile. When the SLA floor (`slamax`) is reached, the remaining leaf carbon is added linearly (see the [index page](index.md) for the equation). The return value is in units of `m² leaf / m² crown`.

`tree_sai` (`FatesAllometryMod.F90:765-827`) scales SAI as:

```fortran
tree_sai = elongf_stem * allom_sai_scaler(pft) * target_lai
```

where `target_lai` is `tree_lai` recomputed with `elongf_leaf = 1.0` (i.e. using target, fully-flushed leaf biomass rather than current leaf biomass). SAI therefore tracks the stable allometric target rather than the current leaf phenology state, but can still be modulated down by stem phenology (`elongf_stem`) for grasses.

## Integrating to Patch Totals: `calc_areaindex`

The function that turns the 3-D profiles into scalar patch totals is `calc_areaindex` (`EDCanopyStructureMod.F90:2024-2086`). Its header comment states the conversion explicitly: *"this is the square meters of leaf per square meter of ground area. It does so by integrating over the depth and functional type profile of leaf area which are per area of crown. This value has to be scaled by crown area to convert to ground area."*

For `ai_type = 'elai'`:

```fortran
ai = 0._r8
do cl = 1, cpatch%NCL_p
   do ft = 1, numpft
      ai = ai + sum( cpatch%canopy_area_profile(cl,ft,1:cpatch%nrad(cl,ft)) * &
                     cpatch%elai_profile(cl,ft,1:cpatch%nrad(cl,ft)) )
   enddo
enddo
```

Three things to note:

1. The profile values (`elai_profile`, in m² leaf / m² crown area) are multiplied by `canopy_area_profile` (the fraction of ground the element covers) to yield the per-ground-area contribution.
2. The sum runs over both PFT and the filled vertical sub-layers up to `nrad(cl,ft)`.
3. A legacy minimum floor `ai = max(ai_min, ai)` with `ai_min = 0.1` is applied at the end (`EDCanopyStructureMod.F90:2082`). This is flagged in the source as an artifact from old testing that has been retained to preserve bitwise reproducibility, and is on the TODO list for removal.

The same function is called for `'tlai'`, `'esai'`, and `'tsai'`, substituting the appropriate profile. These calls produce the four patch-level diagnostics that are exported to the host land model:

| Diagnostic | Profile integrated | Description |
| --- | --- | --- |
| `elai_pa` | `elai_profile` | Exposed LAI per patch (per unit ground area) |
| `tlai_pa` | `tlai_profile` | Total LAI per patch (including snow-occluded) |
| `esai_pa` | `esai_profile` | Exposed SAI per patch |
| `tsai_pa` | `tsai_profile` | Total SAI per patch |

## `canopy_layer_tlai`: a Different Aggregation

`UpdatePatchLAI` also maintains `currentPatch%canopy_layer_tlai(cl)`, which is a coarser per-layer total (`FatesPatchMod.F90:93`, units `m2 veg / m2 canopy area`). It is accumulated as:

```fortran
currentPatch%canopy_layer_tlai(cl) = &
    currentPatch%canopy_layer_tlai(cl) + &
    currentCohort%treelai * currentCohort%c_area / currentPatch%total_canopy_area
```

(`EDCanopyStructureMod.F90:2159-2160`). This is the average cohort `treelai` weighted by crown-area fraction of the canopy. Its primary use is inside `tree_lai` itself, which takes `canopy_layer_tlai` of the layer above as `canopy_lai_above` to offset the exponential SLA profile (`FatesAllometryMod.F90:685-695`). It is not the same quantity as `tlai_pa` from `calc_areaindex`; the two normalise by different areas (canopy area vs ground area).

## Sunlit / Shaded Partitioning

LAI is further partitioned into sunlit and shaded fractions inside `EDSurfaceAlbedoMod.F90` for the photosynthesis calculation. The sunlit fraction of each sub-layer is computed from the direct-beam extinction coefficient and cumulative LAI from the top of the canopy:

```fortran
f_sun(L,ft,iv) = exp( -k_dir(ft) * laisum )
```

(`EDSurfaceAlbedoMod.F90:501-506`, where `laisum` is the cumulative LAI to the middle of layer `iv`). The resulting sunlit and shaded LAI profiles are then stored separately and exported as `laisun_pa` / `laisha_pa` (`EDSurfaceAlbedoMod.F90:1178-1213`).

## Snow Occlusion

The difference between `tlai`/`tsai` and `elai`/`esai` comes from canopy-snow occlusion. In the radiation solver, `fcansno` blends vegetation optical properties with snow properties (`EDSurfaceAlbedoMod.F90:331-334`):

```fortran
rho_blend = (1 - fcansno) * rho_veg + fcansno * rho_snow
tau_blend = (1 - fcansno) * tau_veg + fcansno * tau_snow
```

where `rho_snow` is typically 0.80 (visible) / 0.55 (NIR) and `tau_snow` is ~0.01 in both bands. The exposed-area profiles therefore already account for the snow-occluded fraction having been excluded from the photosynthetically active area.

## Update Timing

Profiles are rebuilt whenever cohort state changes or cohorts cross canopy layers:

| Trigger | Routine invoked | Source |
| --- | --- | --- |
| Daily dynamics (after growth, mortality, fusion) | `canopy_structure` → `leaf_area_profile` | `EDCanopyStructureMod.F90:1437` |
| Start of a radiation timestep | `leaf_area_profile` (via ED interface) | `EDCanopyStructureMod.F90:1467` |
| Per-cohort update inside the daily loop | `UpdateCohortLAI` → `UpdatePatchLAI` | `EDCanopyStructureMod.F90:2122-2206` |

## Key Profile Variables Reference

| Variable | Where defined | Units | Meaning |
| --- | --- | --- | --- |
| `elai_profile(cl,ft,iv)` | `FatesPatchMod.F90:99` | m² leaf / m² crown area | Exposed LAI in sub-layer `iv` of `(cl,ft)` |
| `esai_profile(cl,ft,iv)` | `FatesPatchMod.F90:100` | m² stem / m² crown area | Exposed SAI in sub-layer `iv` |
| `tlai_profile(cl,ft,iv)` | `FatesPatchMod.F90:101` | m² leaf / m² crown area | Total LAI (incl. snow-occluded) |
| `tsai_profile(cl,ft,iv)` | `FatesPatchMod.F90:102` | m² stem / m² crown area | Total SAI (incl. snow-occluded) |
| `canopy_area_profile(cl,ft,iv)` | `FatesPatchMod.F90:103` | fraction [0, 1] | Fraction of patch ground area covered by this (cl,ft,iv) element. Used as the crown→ground weight in `calc_areaindex`. |
| `canopy_layer_tlai(cl)` | `FatesPatchMod.F90:93` | m² leaf / m² canopy area | Per-layer mean LAI, used internally by `tree_lai` |
| `currentCohort%treelai` | `FatesCohortMod.F90` | m² leaf / m² crown area | Cohort LAI, per the cohort's own crown footprint |
| `currentCohort%treesai` | `FatesCohortMod.F90` | m² stem / m² crown area | Cohort SAI |
