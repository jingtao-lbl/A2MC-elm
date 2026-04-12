# History Update Pipeline

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

**Relevant source files:**
- `main/FatesHistoryInterfaceMod.F90`
- `main/FatesHistoryVariableType.F90`
- `main/FatesSizeAgeTypeIndicesMod.F90`
- `biogeochem/EDCohortDynamicsMod.F90`
- `biogeochem/EDPhysiologyMod.F90`

## Purpose and Scope

This page explains how FATES actually populates its history output buffers each timestep. It documents the four update routines, their call frequencies, the hierarchical aggregation pattern (cohort → patch → site → history arrays), the index-calculation step for multiplexed dimensions, and the flush/reset cycle that runs at each host-model output interval.

For variable registration and the dimension kinds themselves, see [History Output System](index.md) and [History Variables and Dimensions](variables.md).

## Update Routines

FATES has exactly four update routines. Their line ranges below are verified against `e85d997`.

| Routine | Lines | Frequency | Called from | Updates |
|---|---|---|---|---|
| `update_history_dyn` | 2108–4387 | Daily | After `ed_ecosystem_dynamics` | Biomass state, demographic pools (nplant, basal area), growth, mortality, disturbance rates, litter/CWD pools, per-size-class and per-size-PFT aggregations, fire diagnostics |
| `update_history_hifrq` | 4389–4857 | Each photosynthesis timestep | During biophysics | GPP, autotrophic respiration, sunlit/shaded LAI, absorbed PAR by canopy and leaf layer, canopy temperature, stomatal conductance |
| `update_history_hydraulics` | 4861–5207 | Each hydraulics timestep (when `hlm_use_planthydro == itrue`) | During hydraulics solve | Tissue water potential, sapflow, root/stem/leaf conductance fractions |
| `update_history_nutrflux` | 1917–2104 | Daily (when `hlm_parteh_mode == prt_cnp_flex_allom_hyp`) | After nutrient dynamics | NH4/NO3/P uptake rates by size × PFT, N demand, P demand, N fixation, nutrient efflux, L2FR dynamics |

Sources: `(main/FatesHistoryInterfaceMod.F90:1917-5207)`

## `update_history_dyn`

This is the primary daily routine. It loops over all sites, all patches in each site, and all cohorts in each patch, extracting per-cohort state and flux variables and accumulating them into the registered history buffers. The registered variables touched here fall into several categories:

**Cohort-level variables aggregated by size × PFT (`site_size_pft_r8` / `_SZPF`).** Number density (`FATES_NPLANT_SZPF`), biomass pools (`FATES_LEAFC_SZPF`, `FATES_SAPWOODC_SZPF`, `FATES_FROOTC_SZPF`, `FATES_STOREC_SZPF`, etc.), fluxes (`FATES_GPP_SZPF`, `FATES_NPP_SZPF`), growth (`FATES_DDBH_SZPF`, `FATES_GROWTHFLUX_SZPF`), and mortality partitioned by mechanism (`FATES_MORTALITY_CANOPY_SZPF`, `FATES_MORTALITY_USTORY_SZPF`, `FATES_MORTALITY_HYDRAULIC_SZPF`, `FATES_MORTALITY_CSTARV_SZPF`, `FATES_MORTALITY_FIRE_SZPF`, `FATES_MORTALITY_LOGGING_SZPF`, etc.).

**Patch-level variables aggregated by age (`site_age_r8` / `_AP`).** Patch area by age class, LAI by age, GPP by age, canopy crown area by age.

**Site-level variables (`site_r8`).** Totals like `FATES_VEGC`, `FATES_LEAFC`, `FATES_LAI`, `FATES_AR`, `FATES_NPATCHES`, `FATES_NCOHORTS`.

**Disturbance rates by process.** `FATES_DISTURBANCE_RATE_FIRE`, `FATES_DISTURBANCE_RATE_LOGGING`, `FATES_DISTURBANCE_RATE_TREEFALL`, `FATES_DISTURBANCE_RATE_P2P`, `FATES_DISTURBANCE_RATE_P2S`, `FATES_DISTURBANCE_RATE_S2S` (primary-to-primary, primary-to-secondary, secondary-to-secondary transitions).

Sources: `(main/FatesHistoryInterfaceMod.F90:2108-4387)`

## `update_history_hifrq`

This routine handles variables with sub-daily dynamics. Called once per photosynthesis timestep (so multiple times per simulation day), it updates the radiation/photosynthesis diagnostics that cannot be meaningfully averaged across a full day from a single daily call.

Primary variables: `FATES_GPP`, `FATES_GPP_PF`, `FATES_GPP_SZPF`, `FATES_AR`, `FATES_AR_CANOPY`, `FATES_AR_UNDERSTORY`, `FATES_RDARK_SZPF`, `FATES_MAINT_RESP`, `FATES_GROWTH_RESP`, `FATES_LBLAYER_COND`, `FATES_STOMATAL_COND`, `FATES_TVEG`, `FATES_FABD_SHA_CLLL`, `FATES_FABD_SUN_CLLL`, `FATES_PARSUN_Z_CLLL`, `FATES_PARSHA_Z_CLLL`, and the PFT-stratified canopy/leaf-layer variants with suffix `_CLLLPF`. Because `avgflag='A'` applies, these accumulate during the day and are divided by the sample count at flush time to produce the reported time-mean.

Sources: `(main/FatesHistoryInterfaceMod.F90:4389-4857)`

## `update_history_hydraulics`

Invoked only when plant hydraulics is enabled. It accumulates tissue-scale water variables used for hydraulic diagnostics: `FATES_SAPFLOW`, `FATES_SAPFLOW_SZPF`, `FATES_LEAF_H2O_SZPF`, `FATES_LEAF_H2OPOT_SZPF`, `FATES_LEAF_CONDFRAC_SZPF`, `FATES_STEM_H2O_SZPF`, `FATES_STEM_H2OPOT_SZPF`, `FATES_STEM_CONDFRAC_SZPF`, `FATES_TRANSROOT_H2O_SZPF`, `FATES_ABSROOT_H2O_SZPF`, `FATES_ROOTUPTAKE`, `FATES_ROOTUPTAKE_SL`, plus `FATES_BTRAN_SZPF` and `FATES_TRAN_SZPF`.

Sources: `(main/FatesHistoryInterfaceMod.F90:4861-5207)`

## `update_history_nutrflux`

Invoked once per day after nutrient dynamics, only when PARTEH is in flexible CNP mode. It updates uptake, demand, and efflux diagnostics: `FATES_NH4UPTAKE`, `FATES_NH4UPTAKE_SZPF`, `FATES_NO3UPTAKE`, `FATES_NO3UPTAKE_SZPF`, `FATES_PUPTAKE`, `FATES_PUPTAKE_SZPF`, `FATES_NDEMAND`, `FATES_NDEMAND_SZPF`, `FATES_PDEMAND`, `FATES_PDEMAND_SZPF`, `FATES_NFIX_SYM`, `FATES_NFIX_SYM_SZPF`, `FATES_NEFFLUX`, `FATES_NEFFLUX_SZPF`, `FATES_PEFFLUX`, `FATES_PEFFLUX_SZPF`, plus L2FR (leaf-to-fine-root) ratio diagnostics.

Sources: `(main/FatesHistoryInterfaceMod.F90:1917-2104)`

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

Sources: `(main/FatesHistoryInterfaceMod.F90:100-132, 272-286)`

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

The reverse maps `fates_hdim_pfmap_levscpf(:)` and `fates_hdim_scmap_levscpf(:)` (in `FatesInterfaceTypesMod.F90`) recover the PFT and size class from a linear index, e.g., for post-processing or when emitting per-bin metadata.

Sources: `(main/FatesSizeAgeTypeIndicesMod.F90)`, `(main/FatesInterfaceTypesMod.F90:252-293)`

## Weighting Strategy Table

| Variable type | Weight factor | Example |
|---|---|---|
| Per-plant intensive (biomass kgC/plant) | `cohort%n * patch%area / AREA` | `hio_leafc_si_scpf += leaf_c * n * pa / AREA` |
| Plant density (m-2) | `cohort%n * patch%area / AREA` | `hio_nplant_si_scpf += n * pa / AREA` |
| Patch area fraction | `patch%area / AREA` | `hio_area_si_age += pa / AREA` |
| Site-level total (already kg/site) | Direct | `hio_npp_si += npp_acc` |
| Crown area | `cohort%c_area` | `hio_crown_area_pf += c_area` |

The `patch%area / AREA` factor normalizes patch fractional area to the site unit of 1 ha (`AREA = 10000 m²`). `n` is typically already in units of plants per m², so no further division is needed.

Sources: `(main/FatesHistoryInterfaceMod.F90:100-132)`

## Flush and Reset

At the end of each host-model history interval (controlled by the HLM's `hist_mfilt`/`hist_nhtfrq` settings, not by FATES), the host calls `flush_hvars` and `zero_site_hvars` in that order.

`flush_hvars` walks each registered variable and, based on its `avgflag`, produces the final time-mean value to hand to the host. Because **every FATES history variable in `e85d997` uses `avgflag='A'`**, the flush step divides each accumulator by its sample count and returns the average. `'I'` (instantaneous), `'M'` (minimum), and `'X'` (maximum) are not currently used by any FATES variable, though the machinery supports them. The semantics follow the CLM/ALM `histFileMod` convention exactly.

`zero_site_hvars` then resets each variable's data buffer to its `flushval` (`flushzero`, `flushone`, or `flushinvalid`), clearing the accumulator for the next interval.

Sources: `(main/FatesHistoryInterfaceMod.F90:850-851)`, `(main/FatesHistoryVariableType.F90:42-90)`

## Threading and Boundary Management

History accumulation is threaded: each thread runs its own copies of the update routines over its own subset of sites/patches/cohorts, writing into thread-specific regions of the shared history arrays. Thread bounds are maintained in `dim_bounds` and initialized by `SetThreadBoundsEach` during FATES interface setup. This means all accumulator writes inside an update routine are into thread-local array slices, and no locking is required.

Sources: `(main/FatesHistoryInterfaceMod.F90:1024-1260)`

## End-to-End Data Path

```
cohort%leaf_c, n, dbh, pft
   ↓
size_class, pft_class = sizetype_class_index(dbh, pft)
iscpf = (size_class - 1) * numpft + pft_class
   ↓
buf(ih_leafc_si_scpf, iscpf) += leaf_c * n * patch%area / AREA
   ↓  [daily, inside update_history_dyn]
accumulator builds up over history interval
   ↓  [end of interval, host calls flush_hvars]
final value = accumulator / sample_count    (because avgflag='A')
   ↓
written to NetCDF as FATES_LEAFC_SZPF[site, iscpf]
   ↓  [host calls zero_site_hvars]
buffer reset to flushval; next interval begins
```

This pipeline runs every timestep (high-frequency variables) or every day (daily variables), continuously building the output dataset that represents the ecosystem's evolution.

Sources: `(main/FatesHistoryInterfaceMod.F90:1-5207)`
