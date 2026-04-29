---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# ELM Subgrid Utilities

Once the nested `grc_pp → top_pp → lun_pp → col_pp → veg_pp` hierarchy is in place (see [`subgrid_hierarchy.md`](subgrid_hierarchy.md)), a handful of utility modules in `components/elm/src/main/` are responsible for

- averaging fields up the hierarchy,
- collecting subsets of indices into **filters** so kernels can loop cheaply,
- validating that subgrid weights obey the invariants, and
- persisting and restoring weights across runs.

**Status at d40b843 vs 60d9aad: structurally unchanged.** `subgridAveMod`, `subgridWeightsMod`, `reweightMod`, `filterMod`, `subgridMod`, `subgridRestMod`, and `decompInitMod` retain the same public APIs and core algorithms. Line numbers may have shifted slightly with comment edits.

## 1. `subgridAveMod` — averaging kernels

Ten public entry points provide every up-averaging direction:

| Routine | Direction | Overloads |
|---|---|---|
| `p2c` | patch → column | 1-D, 2-D, filter, GPU |
| `p2l` | patch → landunit | 1-D, 2-D |
| `p2g` | patch → gridcell | 1-D, 2-D, GPU |
| `c2l` | column → landunit | 1-D, 2-D |
| `c2g` | column → gridcell | 1-D, 2-D, GPU |
| `l2g` | landunit → gridcell | 1-D, 2-D, GPU |
| `p2t` | patch → topounit | 1-D, 2-D |
| `c2t` | column → topounit | 1-D, 2-D |
| `l2t` | landunit → topounit | 1-D, 2-D |
| `t2g` | topounit → gridcell | 1-D, 2-D, GPU |

Every routine multiplies each child contribution by the **derived weight** (set by `compute_higher_order_weights`) and divides by the cumulative weight of valid children so points whose parent is inactive or whose children are entirely `spval` propagate sensibly.

Scaling modes are integer constants:

```
unity   = 0    ! straight weighted average
urbanf  = 1    ! scale urban landunits as "urban fluxes"
urbans  = 2    ! scale urban landunits as "urban states"
natveg  = 3    ! keep only natural-vegetation contribution
veg     = 4    ! keep only vegetated contribution
ice     = 5    ! keep only glacier contribution
nonurb  = 6    ! exclude urban
lake    = 7    ! keep only lake contribution
```

Private builders (`build_scale_l2g`, `create_scale_l2g_lookup`, `build_scale_l2t`, `create_scale_l2t_lookup`, and the `create_scale_c2l[_gpu]` interface) convert these modes into per-landunit scale coefficients. Callers therefore request behaviour symbolically — for example `lnd2atm_minimal` uses `c2l_scale_type=urbanf, l2g_scale_type=unity`.

The design philosophy and exact spval-handling logic is documented in the 70-line comment block at `main/subgridWeightsMod.F90:53-88`.

## 2. `subgridMod` — subgrid geometry queries

Two public helpers, both pure counters used during decomposition and case initialization:

- `subgrid_get_gcellinfo(gi, …)` — returns the number of topounits, landunits, columns, patches, cohorts, and per-landunit patches for a given global gridcell index. Inputs include `maxpatch_glcmec`, `create_crop_landunit`, and `fates_maxElementsPerSite` from `FatesInterfaceTypesMod`.
- `subgrid_get_topounitinfo` — analogous counter at topounit resolution.

These counters are how `decompInitMod` discovers how many entries each clump needs before allocating `lun_pp`, `col_pp`, and `veg_pp`.

## 3. `subgridWeightsMod` — weight arithmetic and invariants

This module centralises everything that touches subgrid weights at runtime. Public entry points:

- `init_subgrid_weights_mod(bounds)` — allocates the diagnostic arrays `pct_landunit`, `pct_nat_pft`, `pct_cft`, `pct_glc_mec` and registers history output for them.
- `compute_higher_order_weights(bounds)` — computes the five derived weights (`lun%wtgcell`, `col%wttopounit`, `col%wtgcell`, `veg%wtlunit`, `veg%wttopounit`, `veg%wtgcell`) from the four primitives (`top%wtgcell`, `lun%wttopounit`, `col%wtlunit`, `veg%wtcol`).
- `set_active(bounds)` — applies the active-flag cascade, aborting if it finds any active child under an inactive parent.
- `check_weights(bounds, active_only)` — walks the hierarchy and asserts the three invariants from [`subgrid_hierarchy.md`](subgrid_hierarchy.md) §7 using the internal helper `weights_okay`.
- `get_landunit_weight(t, ltype)` / `set_landunit_weight(t, ltype, w)` — O(1) accessors backed by `top_pp%landunit_indices`. `set_landunit_weight` aborts if asked to write a non-zero weight to a landunit type that does not exist on the topounit.
- `is_topo_all_ltypeX(t, ltype)` — fast check used by the glacier-mec virtual landunit bookkeeping in `is_active_l`.
- `set_subgrid_diagnostic_fields(bounds)` — fills `pct_landunit`, `pct_nat_pft`, `pct_cft`, `pct_glc_mec` history output from current weights.

### Active-flag cascade

`is_active_l` / `is_active_c` / `is_active_p` encode why a given landunit, column, or patch should be "alive" in a time step:

- The default rule for all three is "parent active and own weight > 0".
- `istice_mec` landunits (and their columns) are forced active on every gridcell whose `ldomain%glcmask(g) == 1`, so CISM always has somewhere to dump coupled output, even if the current ice weight is zero.
- `istsoil` landunits are forced active on every topounit that is not 100% `istice`, providing a bare-land SMB forcing target for glacier initialization.
- All urban columns are kept active even when they have zero weight so the urban loops do not need per-column `active` checks.
- Setting the namelist option `all_active` short-circuits each function to `.true.`.

## 4. `reweightMod` — high-level "weights changed" wrapper

`reweight_wrapup(bounds, icemask_grc)` is the one-line entry point that must be called after any code changes the subgrid weights. It runs

```
call set_active(bounds)
call check_weights(bounds, active_only=.false.)
call check_weights(bounds, active_only=.true.)
call setFilters(bounds, icemask_grc)
```

in that exact order. The module's only reason to exist is to keep `subgridWeightsMod` free of a dependency on `filterMod`. Everything in `dyn_subgrid/` ultimately goes through `reweight_wrapup` via `dynSubgrid_wrapup_weight_changes`.

## 5. `filterMod` — per-clump index filters

Filters are arrays of integer indices — one filter per thread clump — that a kernel consumes with `do fc = 1, num_XX; c = filter(nc)%XX(fc)`. The `clumpfilter` derived type holds roughly thirty filters grouped into:

- Natural-vegetation patches (`natvegp`, `num_natvegp`)
- Prognostic crop patches (`pcropp`, `ppercropp`)
- Soil columns (with and without progressive crops) and soil patches
- Lake / non-lake columns and patches
- Hydrology-active columns (`hydrologyc`, `hydrononsoic`)
- Urban landunits / columns / patches (`urbanl`, `nourbanl`, `urbanc`, `nourbanc`, `urbanp`, `nourbanp`)
- Glacier-mec columns (`icemecc`) and "do SMB" columns (`do_smb_c`)
- Snow / non-snow column filters (`snowc`, `nosnowc`)

Two parallel copies of the filter structure are maintained:

- `filter(:)` — the default, containing **active points only**
- `filter_inactive_and_active(:)` — a second group that includes inactive points, used for book-keeping operations that must visit points that just became inactive (for example the `dyn_cnbal_patch` mass-balance routine in `dyn_subgrid/dynConsBiogeochemMod.F90`)

`allocFilters` / `allocFiltersOneGroup` allocate both groups once per decomposition; `setFilters` / `setFiltersOneGroup` rebuild them whenever weights change. The per-clump inner loops skip columns and patches whose parent topounit is inactive so that inactive topounits fall out of every filter naturally.

## 6. `subgridRestMod` — weight restart I/O

`subgridRest(bounds, ncid, flag)` is the entry called from the restart driver. `flag` is one of `define`, `read`, or `write`; on `write` it delegates to `subgridRest_write_only`, and for reads it uses `subgridRest_write_and_read`. The module is also responsible for:

- `save_old_weights(bounds)` — snapshots the weight vectors read off the restart file so `subgridRest_check_consistency` can compare them to the surface-dataset weights.
- `subgridRest_read_cleanup` — releases temporary arrays allocated during the read / consistency phase.

Restart files therefore capture the exact `top%wtgcell`, `lun%wttopounit`, `col%wtlunit`, and `veg%wtcol` vectors present at the checkpoint step. On restart the model recomputes all derived weights, `active` flags, filters, and BGC state via the same `reweight_wrapup` path used during normal operation.

## 7. `decompInitMod` — domain decomposition helpers

`decompInitMod` wires the hierarchy to the processor layout via four steps:

- `decompInit_lnd` / `decompInit_lnd_simple` / `decompInit_lnd_using_gp` (and `decompInit_moab` when `HAVE_MOAB`) — decompose the land `(lni, lnj)` mesh into clumps and assign gridcells.
- `decompInit_clumps(glcmask)` — once clumps exist, compute per-clump counts of gridcells, landunits, columns, and patches, using `subgrid_get_gcellinfo` / `subgrid_get_topounitinfo` to size everything ahead of allocation.
- `decompInit_gtlcp(lns, lni, lnj, glcmask)` — allocate the procinfo arrays for `(g, t, l, c, p)` index ranges that back the `bounds_type` structure consumed by all callers in this document.
- `decompInit_ghosts(glcmask)` — wire up ghost-cell indices (`begg_ghost`/`endg_ghost`, etc.) for halo access, needed by routing and unstructured-mesh configurations.

Every `bounds_type` argument you see in `filterMod`, `subgridAveMod`, and all `dyn_subgrid/*` routines is populated by this module; its `BOUNDS_LEVEL_PROC` and `BOUNDS_LEVEL_CLUMP` sentinels are asserted at every entry point to make sure processor-level and clump-level bounds never get mixed up.

## 8. Putting the utilities together

A complete "weights changed" sequence — whether from dynamic land use, GLC coupling, or FATES — executes, in order:

1. **Write new primitive weights.** Some code writes directly into `top_pp%wtgcell`, `lun_pp%wttopounit`, `col_pp%wtlunit`, or `veg_pp%wtcol`.
2. **`compute_higher_order_weights`** — update all derived `wtXX` fields.
3. **`set_active`** — refresh active flags top-to-bottom.
4. **`check_weights(active_only=.false.)` + `check_weights(active_only=.true.)`** — verify invariants (1), (2), (3) of `subgridWeightsMod`.
5. **`setFilters`** — rebuild both filter groups for every clump.
6. **`set_subgrid_diagnostic_fields`** — refresh the `PCT_*` history diagnostics.

Steps 2-5 are combined inside `reweight_wrapup`. Writers wrap everything with the driver in `dyn_subgrid/dynSubgridDriverMod.F90`; callers that merely need to consume averaged data invoke `subgridAveMod` routines with the scale modes that best fit their semantics.
