---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# History Update Pipeline

**Relevant source files:**
- `main/FatesHistoryInterfaceMod.F90` (9944 lines)
- `main/FatesHistoryVariableType.F90`
- `main/FatesSizeAgeTypeIndicesMod.F90`
- `biogeochem/EDCohortDynamicsMod.F90`
- `biogeochem/EDPhysiologyMod.F90`

## Purpose and Scope

This page explains how FATES actually populates its history output buffers each timestep at e027a40. It documents the four user-visible update routines, their internal sub-routine stacks, the hierarchical aggregation pattern (cohort → patch → site → history arrays), the index-calculation step for multiplexed dimensions, and the flush/reset cycle that runs at each host-model output interval.

For variable registration and the dimension kinds themselves, see [History Output System](index.md) and [History Variables and Dimensions](variables.md).

## Update Routines (User-Facing)

The HLM calls four FATES history update routines. At e027a40, two of those (`update_history_dyn` and `update_history_hifrq`) have been refactored into thin dispatchers that call a stack of focused sub-routines. The hydraulics and nutrient-flux routines remain monolithic.

| User-facing routine | Lines | Frequency | Called from | Updates |
|---|---|---|---|---|
| `update_history_dyn` | 2355-2392 | Daily | After `ed_ecosystem_dynamics` | Dispatcher (see below) |
| `update_history_hifrq` | 5152-5183 | Each photosynthesis timestep | During biophysics | Dispatcher (see below) |
| `update_history_hydraulics` | 6042-6422 | Each hydraulics timestep (when `hlm_use_planthydro == itrue`) | During hydraulics solve | Tissue water potential, sapflow, root/stem/leaf conductance fractions |
| `update_history_nutrflux` | 2132-2351 | Daily (when `hlm_parteh_mode == prt_cnp_flex_allom_hyp`) | After nutrient dynamics | NH4/NO3/P uptake by size × PFT, N demand, P demand, N fixation, nutrient efflux, L2FR dynamics |

Sources: `(main/FatesHistoryInterfaceMod.F90:2132, 2355, 5152, 6042)`

## `update_history_dyn` Dispatcher

This is the daily entry point. The dispatcher gates on `hlm_hist_level_dynam` and dispatches to a sitelevel/subsite/subsite_ageclass stack:

```fortran
subroutine update_history_dyn(this,nc,nsites,sites,bc_in)
   if (hlm_use_ed_st3.eq.itrue) return

   if(hlm_hist_level_dynam>0) then
      call update_history_dyn_sitelevel(this,nc,nsites,sites)
      if(hlm_hist_level_dynam>1) then
         call update_history_dyn_subsite(this,nc,nsites,sites,bc_in)
         call update_history_dyn_subsite_ageclass(this,nc,nsites,sites)
         call reset_history_dyn_subsite(this, nsites, sites)
      end if
   end if
end subroutine
```

| Sub-routine | Lines | Role |
|---|---|---|
| `update_history_dyn_sitelevel` | 2396-3105 | Site-aggregate updates (e.g., `FATES_VEGC`, `FATES_LEAFC`, `FATES_LAI`, `FATES_NPATCHES`, `FATES_NCOHORTS`, demographic and disturbance scalars, the new `FATES_GRAZING`, `FATES_INTERR_LIVEVEG_EL`, `FATES_INTERR_LITTER_EL`, `FATES_VIS_RAD_ERROR`, `FATES_NIR_RAD_ERROR`) |
| `update_history_dyn_subsite` | 3109-4791 | Patch and cohort loop. Aggregates per-(size × PFT), per-PFT, per-CDPF, per-CL/CLLL/CLLLPF outputs, including the disturbance-rate suite, the rxfire/wildfire mortality suite, and the per-PFT `FATES_MORT_CSTARV_CONT_CFLUX_PF`. |
| `update_history_dyn_subsite_ageclass` | 4795-5076 | Patch-age aggregations (e.g., `FATES_VEGC_AP`, `FATES_GPP_AP`, `FATES_PATCHAREA_AP`, `FATES_RXFIRE_BURNFRAC_AP`, `FATES_WILDFIRE_BURNFRAC_AP`) and age × PFT / age × fuel multiplexed outputs |
| `reset_history_dyn_subsite` | (in same source) | Clears per-cohort scratch state used inside the subsite loop after the day completes |

The four-routine claim from the e85d997 wiki ("FATES has exactly four update routines") is now misleading: the user-facing call surface is still four entry points, but `_dyn` and `_hifrq` are dispatchers, and there are 11 distinct update sub-routines in total.

Sources: `(main/FatesHistoryInterfaceMod.F90:2355, 2396, 3109, 4795)`

## `update_history_hifrq` Dispatcher

Sub-daily entry point, called every photosynthesis timestep:

```fortran
subroutine update_history_hifrq(this,nc,nsites,sites,bc_in,bc_out,dt_tstep)
   if(hlm_hist_level_hifrq>0) then
      call update_history_hifrq_sitelevel(this,nc,nsites,sites,bc_in,dt_tstep)
      if(hlm_hist_level_hifrq>1) then
         call update_history_hifrq_subsite(this,nc,nsites,sites,bc_in,dt_tstep)
         call update_history_hifrq_subsite_ageclass(this,nsites,sites,dt_tstep)
         if (hlm_use_luh .eq. itrue) then
            call update_history_hifrq_landuse(this,nc,nsites,sites,bc_in,dt_tstep)
         end if
      end if
   end if
end subroutine
```

| Sub-routine | Lines | Role |
|---|---|---|
| `update_history_hifrq_sitelevel` | 5185-5407 | Site-aggregate sub-daily fluxes (`FATES_GPP`, `FATES_NPP`, `FATES_AUTORESP`, `FATES_AUTORESP_CANOPY`, `FATES_AUTORESP_USTORY`, `FATES_RDARK_*`, `FATES_TVEG`, `FATES_STOMATAL_COND`, `FATES_LBLAYER_COND`, `FATES_HARVEST_WOODPROD_C_FLUX`, `FATES_LUCHANGE_WOODPROD_C_FLUX`, the radiation-error scalars) |
| `update_history_hifrq_landuse` | 5412-5555 | NEW at e027a40: populates the `_LU`, `_LUPF`, `_LULU` family (`FATES_GPP_LU`, `FATES_NPP_LU`, `FATES_VEGC_LU`, `FATES_PATCHAREA_LU`, `FATES_NOCOMP_PATCHAREA_LUPF`, `FATES_LHFLUX_LU`, `FATES_SHFLUX_LU`, `FATES_TSA_LU`, `FATES_TVEG_LU`, `FATES_SWABS_LU`, `FATES_NETLW_LU`, `FATES_BURNEDAREA_LU`, `FATES_TRANSITION_MATRIX_LULU`, `FATES_DISTURBANCE_RATE_MATRIX_LULU`). Only called when `hlm_use_luh .eq. itrue`. |
| `update_history_hifrq_subsite` | 5559-5946 | Patch and cohort loop for sub-daily per-(size × PFT) and CL/CLLL/CLLLPF outputs (`FATES_GPP_SZPF`, `FATES_PARSUN_CLLL`, `FATES_LAISUN_CLLLPF`, `FATES_PARPROF_DIR_CLLL`, etc.). At e027a40 the `_Z` infix has been dropped from all radiation vnames here. |
| `update_history_hifrq_subsite_ageclass` | 5950-6038 | Sub-daily patch-age aggregates (`FATES_GPP_AP`, `FATES_LBLAYER_COND_AP`, `FATES_STOMATAL_COND_AP`) |

Sources: `(main/FatesHistoryInterfaceMod.F90:5152, 5185, 5412, 5559, 5950)`

## `update_history_hydraulics`

Invoked only when plant hydraulics is enabled. It accumulates tissue-scale water variables used for hydraulic diagnostics: `FATES_SAPFLOW`, `FATES_SAPFLOW_SZPF`, `FATES_LEAF_H2O_SZPF`, `FATES_LEAF_H2OPOT_SZPF`, `FATES_LEAF_CONDFRAC_SZPF`, `FATES_STEM_H2O_SZPF`, `FATES_STEM_H2OPOT_SZPF`, `FATES_STEM_CONDFRAC_SZPF`, `FATES_TRANSROOT_H2O_SZPF`, `FATES_ABSROOT_H2O_SZPF`, `FATES_ROOTUPTAKE`, `FATES_ROOTUPTAKE_SL`, plus `FATES_BTRAN_SZPF` and `FATES_TRAN_SZPF`.

Sources: `(main/FatesHistoryInterfaceMod.F90:6042-6422)`

## `update_history_nutrflux`

Invoked once per day after nutrient dynamics, only when PARTEH is in flexible CNP mode. It updates uptake, demand, and efflux diagnostics: `FATES_NH4UPTAKE`, `FATES_NH4UPTAKE_SZPF`, `FATES_NO3UPTAKE`, `FATES_NO3UPTAKE_SZPF`, `FATES_PUPTAKE`, `FATES_PUPTAKE_SZPF`, `FATES_NDEMAND`, `FATES_NDEMAND_SZPF`, `FATES_PDEMAND`, `FATES_PDEMAND_SZPF`, `FATES_NFIX_SYM`, `FATES_NFIX_SYM_SZPF`, `FATES_NEFFLUX`, `FATES_NEFFLUX_SZPF`, `FATES_PEFFLUX`, `FATES_PEFFLUX_SZPF`, plus L2FR (leaf-to-fine-root) ratio diagnostics including the new `FATES_L2FR_CANOPY_REC_PF` and `FATES_L2FR_USTORY_REC_PF`.

Sources: `(main/FatesHistoryInterfaceMod.F90:2132-2351)`

## Data Aggregation Pattern

The typical accumulation pattern for a cohort-level variable (size × PFT output) is:

```
for each site:
   for each patch in site:
      for each cohort in patch:
         isc, iscpf = size_class_indices(cohort%dbh, cohort%pft)
         buf(ih_leafc_si_scpf, iscpf) += cohort%leaf_c * cohort%n * patch%area / AREA
```

Three principles underlie this pattern:

1. **Mass-conservative weighting.** Intensive per-plant variables (like `cohort%leaf_c`, which is kgC per plant) are multiplied by `cohort%n` (plants per unit patch area) and `patch%area / AREA` before summing, so the result is in `kgC / site` (or equivalently `kgC / m²` when the site is normalized to 1 ha = 10000 m²).
2. **Emit numerators and denominators separately.** When a variable is really a ratio (e.g., average biomass per plant), the source code advises emitting the numerator and denominator as separate variables so that post-processing can compute the correct weighted mean even when cohort numbers change between output intervals. This is explicitly documented in the header comments of `FatesHistoryInterfaceMod.F90`.
3. **Size/age class bin membership is recomputed on the fly.** Because cohorts are continuous in DBH and patches in age, the index-mapping functions (below) are called every step during accumulation — they are not cached on the cohort or patch.

## Dimension Index Calculation

Continuous attributes are mapped to discrete bins using helper functions in `main/FatesSizeAgeTypeIndicesMod.F90`:

| Function | Input | Output |
|---|---|---|
| `sizetype_class_index` | `dbh, pft` | `size_class`, `size_by_pft_class` |
| `get_sizeage_class_index` | `dbh, age` | `iscag` |
| `get_sizeagepft_class_index` | `dbh, age, pft` | `iscagpft` |
| `get_agepft_class_index` | `age, pft` | `iagepft` |
| `get_age_class_index` | `age` | `iage` |
| `get_layersizetype_class_index` | `canopy_layer, dbh, pft` | `iclscpf` |

For a multiplexed dimension like `levscpf` (size class × PFT), the linear index is computed as a row-major flattening:

```
iscpf = (size_class - 1) * numpft + pft
```

The reverse maps `fates_hdim_pfmap_levscpf(:)` and `fates_hdim_scmap_levscpf(:)` (in `FatesInterfaceTypesMod.F90`) recover the PFT and size class from a linear index, e.g., for post-processing or when emitting per-bin metadata. Analogous maps exist for `levscagpft`, `levcdpf`, `levlupft`, and `levlulu`.

Sources: `(main/FatesSizeAgeTypeIndicesMod.F90)`, `(main/FatesInterfaceTypesMod.F90)`

## Weighting Strategy Table

| Variable type | Weight factor | Example |
|---|---|---|
| Per-plant intensive (biomass kgC/plant) | `cohort%n * patch%area / AREA` | `hio_leafc_si_scpf += leaf_c * n * pa / AREA` |
| Plant density (m-2) | `cohort%n * patch%area / AREA` | `hio_nplant_si_scpf += n * pa / AREA` |
| Patch area fraction | `patch%area / AREA` | `hio_area_si_age += pa / AREA` |
| Site-level total (already kg/site) | Direct | `hio_npp_si += npp_acc` |
| Crown area | `cohort%c_area` | `hio_crown_area_pf += c_area` |
| Per land-use category | Aggregate within `update_history_hifrq_landuse` over patches whose `land_use_label` matches the LU index | `hio_gpp_lu(ilu) += sum_over_patches(...)` |

The `patch%area / AREA` factor normalizes patch fractional area to the site unit of 1 ha (`AREA = 10000 m²`). `n` is typically already in units of plants per m², so no further division is needed.

## Flush and Reset

At the end of each host-model history interval (controlled by the HLM's `hist_mfilt`/`hist_nhtfrq` settings, not by FATES), the host calls `flush_hvars` and `zero_site_hvars` in that order.

`flush_hvars` walks each registered variable and, based on its `avgflag`, produces the final time-mean value to hand to the host. Because **every FATES history variable in e027a40 uses `avgflag='A'`**, the flush step divides each accumulator by its sample count and returns the average. `'I'` (instantaneous), `'M'` (minimum), and `'X'` (maximum) are not currently used by any FATES variable, though the machinery supports them. The semantics follow the CLM/ALM `histFileMod` convention exactly.

`zero_site_hvars` then resets each variable's data buffer to its `flushval` (`flushzero`, `flushone`, or `flushinvalid`), clearing the accumulator for the next interval.

Sources: `(main/FatesHistoryVariableType.F90)`, `(main/FatesHistoryInterfaceMod.F90)`

## Threading and Boundary Management

History accumulation is threaded: each thread runs its own copies of the update routines over its own subset of sites/patches/cohorts, writing into thread-specific regions of the shared history arrays. Thread bounds are maintained in `dim_bounds` and initialized by `SetThreadBoundsEach` during FATES interface setup. This means all accumulator writes inside an update routine are into thread-local array slices, and no locking is required.

## End-to-End Data Path

```
cohort%leaf_c, n, dbh, pft
   ↓
size_class, pft_class = sizetype_class_index(dbh, pft)
iscpf = (size_class - 1) * numpft + pft_class
   ↓
buf(ih_leafc_si_scpf, iscpf) += leaf_c * n * patch%area / AREA
   ↓  [daily, inside update_history_dyn_subsite]
accumulator builds up over history interval
   ↓  [end of interval, host calls flush_hvars]
final value = accumulator / sample_count    (because avgflag='A')
   ↓
written to NetCDF as FATES_LEAFC_SZPF[site, iscpf]
   ↓  [host calls zero_site_hvars]
buffer reset to flushval; next interval begins
```

The same template applies to the new `_LU`/`_LUPF`/`_LULU` family, but the per-cohort or per-patch sum is restricted to patches whose `land_use_label` matches the bin's land-use index, and the work happens inside `update_history_hifrq_landuse` rather than `update_history_dyn_subsite`.

This pipeline runs every timestep (high-frequency variables) or every day (daily variables), continuously building the output dataset that represents the ecosystem's evolution.

Sources: `(main/FatesHistoryInterfaceMod.F90:1-9944)`
