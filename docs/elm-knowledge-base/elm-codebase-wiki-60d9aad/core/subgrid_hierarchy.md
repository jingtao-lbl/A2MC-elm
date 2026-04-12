---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# ELM Subgrid Hierarchy

## 1. Overview

ELM represents a heterogeneous land surface with a five-level nested hierarchy. Each
level owns its own derived type, defined in `components/elm/src/data_types/`. The
types are declared `public, target` and exposed as **singleton module-level
instances** (`grc_pp`, `top_pp`, `lun_pp`, `col_pp`, `veg_pp`). All numeric arrays
inside these types are 1-D, allocated over processor-local bounds
(`begg:endg`, `begt:endt`, `begl:endl`, `begc:endc`, `begp:endp`), so traversing the
hierarchy is done by index lookups, not pointer walks.

```
GRIDCELL  (grc_pp, data_types/GridcellType.F90)
  |  topi/topf, lndi/lndf, coli/colf, pfti/pftf
  |  landunit_indices(1:max_lunit, begg:endg)
  |
  +-- TOPOUNIT  (top_pp, data_types/TopounitType.F90)    [PET 2015: new level]
        |  lndi/lndf, coli/colf, pfti/pftf
        |  landunit_indices(1:max_lunit, begt:endt)
        |  wtgcell, active, area, lat, lon, elevation, slope, aspect
        |
        +-- LANDUNIT  (lun_pp, data_types/LandunitType.F90)
              |  coli/colf, pfti/pftf
              |  itype (istsoil..isturb_md), ifspecial, lakpoi, urbpoi, glcmecpoi
              |  wtgcell, wttopounit, active
              |
              +-- COLUMN  (col_pp, data_types/ColumnType.F90)
                    |  pfti/pftf
                    |  itype, active, snl, dz/z/zi, glc_topo
                    |  hydrologically_active, is_fates
                    |  wtgcell, wttopounit, wtlunit
                    |
                    +-- PATCH / VEGETATION  (veg_pp,
                          data_types/VegetationType.F90)
                          itype (0..24 PFT/CFT), mxy, active
                          is_fates, is_veg, is_bareground, wt_ed
                          wtgcell, wttopounit, wtlunit, wtcol
```

`numpft` and `natpft_size`, `cft_size`, `maxpatch_glcmec` control how many entries
exist at the patch / column level for each landunit type. PFT indexing at the
`veg_pp%itype` level follows the header of `VegetationType.F90:9-34`.

## 2. Gridcell (`grc_pp`)

Source: `data_types/GridcellType.F90:24-79`.

The gridcell holds processor-global geographic metadata and **range pointers** into
every subgrid level beneath it, so kernels that need "all children of gridcell `g`"
can walk with contiguous slices.

| Field | Units / type | Meaning |
|---|---|---|
| `gindex(:)` | integer | Global (unstructured) index |
| `area`, `lat`, `lon`, `latdeg`, `londeg` | km², radians, degrees | Geometry |
| `topi(:)`, `topf(:)`, `ntopounits(:)` | integer | Topounit range & count (`data_types/GridcellType.F90:35-37`) |
| `lndi(:)`, `lndf(:)`, `nlandunits(:)` | integer | Landunit range & count |
| `coli(:)`, `colf(:)`, `ncolumns(:)` | integer | Column range & count |
| `pfti(:)`, `pftf(:)`, `npfts(:)` | integer | Patch range & count |
| `landunit_indices(1:max_lunit, begg:endg)` | integer | Reverse map: for landunit type `l`, the index in `lun_pp` (or `ispval`). Note the transposed layout with space in the trailing dimension, called out at `data_types/GridcellType.F90:64-68`. |
| `stdev_elev`, `sky_view`, `terrain_config`, `sinsl_cosas`, `sinsl_sinas` | real | Solar / topographic downscaling factors |
| `max_dayl`, `dayl`, `prev_dayl` | seconds | Daylength cache |
| `elevation`, `MaxElevation`, `froudenum` | m, dimensionless | Mean / max surface elevation (`MaxElevation` is used by precipitation downscaling) |

Allocation happens in `grc_pp_init` (`data_types/GridcellType.F90:84-131`), which
initializes every pointer to `ispval` / `spval` sentinels.

## 3. Topounit (`top_pp`)

Source: `data_types/TopounitType.F90:22-60`. Added in 2015 to give the
grid-cell-to-landunit edge a physical carrier for slope, aspect, and mean surface
parameters. `max_topounits` is read from the surface dataset in
`main/topounit_varcon.F90:40-127`; by default it is 1 (a degenerate topounit equal to
the gridcell).

| Field | Meaning |
|---|---|
| `gridcell(:)`, `topo_grc_ind(:)`, `wtgcell(:)` | Parent gridcell, its ordinal within the gridcell, and the topounit weight relative to that gridcell |
| `lndi/lndf/nlandunits`, `coli/colf/ncolumns`, `pfti/pftf/npfts` | Child ranges & counts |
| `landunit_indices(1:max_lunit, begt:endt)` | Landunit reverse map (analogous to `grc_pp`) |
| `active(:)` | True if this topounit participates in the time step |
| `area`, `lat`, `lon`, `elevation` | Mean geometry |
| `slope`, `aspect`, `emissivity` | Surface-scale physical properties |
| `surfalb_dir(:,:)`, `surfalb_dif(:,:)` | Mean surface albedo per radiation band |

The `landunit_varcon`-typed landunit counting and the `top_pp%landunit_indices`
array are the mechanism by which
`subgridWeightsMod.get_landunit_weight(t, ltype)` and `set_landunit_weight(t, ltype,
w)` look up a landunit on a topounit without a linear search
(`main/subgridWeightsMod.F90:483-540`).

## 4. Landunit (`lun_pp`)

Source: `data_types/LandunitType.F90:27-64`.

| Field | Meaning |
|---|---|
| `gridcell(:)`, `topounit(:)` | Parent indices |
| `wtgcell`, `wttopounit` | Weight relative to gridcell / topounit (the two are related via `compute_higher_order_weights`) |
| `coli/colf/ncolumns`, `pfti/pftf/npfts` | Column / patch ranges under this landunit |
| `itype(:)` | Landunit type code, values enumerated in `main/landunit_varcon.F90:20-33`: `istsoil=1`, `istcrop=2`, `istice=3`, `istice_mec=4`, `istdlak=5`, `istwet=6`, `isturb_tbd=7`, `isturb_hd=8`, `isturb_md=9`, with `max_lunit=9` |
| `ifspecial`, `lakpoi`, `urbpoi`, `glcmecpoi` | Type-class flags (filled by `landunit_is_special` semantics, see `main/landunit_varcon.F90:74-99`) |
| `active(:)` | True if this landunit participates in the time step (set by `set_active` in `subgridWeightsMod`) |
| `canyon_hwr`, `wtroad_perv`, `wtlunit_roof`, `ht_roof`, `z_0_town`, `z_d_town` | Urban parameters (populated by `UrbanParamsMod`) |

`landunit_is_special(ltype)` returns `.false.` only for `istsoil` and `istcrop`,
marking every other landunit as a "special" carrier that does not hold most
biogeochemistry state (`main/landunit_varcon.F90:74-99`).

## 5. Column (`col_pp`)

Source: `data_types/ColumnType.F90:33-82`.

| Field | Meaning |
|---|---|
| `gridcell`, `topounit`, `landunit`, `wtgcell`, `wttopounit`, `wtlunit` | Parent indices & weights |
| `pfti/pftf/npfts` | Child patch range / count |
| `itype(:)` | Column type: shares standard landunit codes (1..6) plus the urban-specific codes defined in `main/column_varcon.F90:23-27` (`icol_roof=71`, `icol_sunwall=72`, `icol_shadewall=73`, `icol_road_imperv=74`, `icol_road_perv=75`); for ice-mec columns, `itype = istice_mec*100 + icemec_class` via `icemec_class_to_col_itype` (`main/column_varcon.F90:76-98`) |
| `active(:)` | Runtime active flag |
| `snl`, `dz`, `z`, `zi`, `zii`, `dz_lake`, `z_lake`, `lakedepth` | Snow-layer count and the `-nlevsno+1:nlevgrnd` vertical discretization; lake-specific levels |
| `glc_topo`, `micro_sigma`, `n_melt`, `topo_slope`, `topo_std`, `hslp_p10`, `nlevbed`, `zibed` | Microtopography, hillslope percentiles, and bedrock depth |
| `hydrologically_active(:)` | Pre-cached result of `is_hydrologically_active(col_itype, lun_itype)` (`main/column_varcon.F90:37-73`) so loops can branch in O(1) |
| `is_fates(:)` | True for columns under FATES control; default `.false.` at allocation time (`data_types/ColumnType.F90:138`) |

## 6. Patch / Vegetation (`veg_pp`)

Source: `data_types/VegetationType.F90:49-82`.

| Field | Meaning |
|---|---|
| `gridcell`, `topounit`, `landunit`, `column` (+ matching weights) | Parent indices and weights through every level |
| `itype(:)` | PFT / CFT index (0 = bare ground, 1..8 = trees, 9..11 = shrubs, 12..14 = grass, 15..24 = crops) per the header comment at `data_types/VegetationType.F90:9-34` |
| `mxy(:)` | Index for 2-D history mapping |
| `active(:)` | Runtime active flag |
| `is_fates(:)` | Static flag — true for any patch slot reserved for FATES, even when not currently mapped to a live FATES cohort linked list (`data_types/VegetationType.F90:70-75`) |
| `is_veg(:)`, `is_bareground(:)`, `wt_ed(:)`, `sp_pftorder_index(:)` | Allocated only when `use_fates=.true.` (`data_types/VegetationType.F90:118-123`); `wt_ed` is the weight FATES publishes back to ELM and is copied into `wtcol` by `dynEDMod`. |

## 7. Weight relationships

Four primitive weights are stored per level:

- `top_pp%wtgcell` — topounit share of a gridcell
- `lun_pp%wttopounit` — landunit share of a topounit
- `col_pp%wtlunit` — column share of a landunit
- `veg_pp%wtcol` — patch share of a column

Higher-order weights are **derived** by `compute_higher_order_weights`
(`main/subgridWeightsMod.F90:217-253`):

```
lun%wtgcell(l)    = lun%wttopounit(l) * top%wtgcell(t)
col%wttopounit(c) = col%wtlunit(c)    * lun%wttopounit(l)
col%wtgcell(c)    = col%wtlunit(c)    * lun%wtgcell(l)
veg%wtlunit(p)    = veg%wtcol(p)      * col%wtlunit(c)
veg%wttopounit(p) = veg%wtcol(p)      * col%wttopounit(c)
veg%wtgcell(p)    = veg%wtcol(p)      * col%wtgcell(c)
```

The invariants enforced by `check_weights` and described in the header of
`main/subgridWeightsMod.F90:9-50` are:

1. On every column, landunit, topounit, and gridcell, the sum of child weights equals 1.
2. On every **active** parent, the sum of weights over **active** children equals 1.
3. On every inactive parent, the sum over active children equals 0 **or** 1.

These rules allow the safe averaging pattern documented at
`main/subgridWeightsMod.F90:53-88` (loop over children, multiply by child weight,
skip inactive / zero-weight children).

## 8. Active flags

`set_active` (`main/subgridWeightsMod.F90:256-310`) sets `active` at all four non-
gridcell levels, enforcing the cascade:

- A landunit is active only if its parent topounit is active **and** `wttopounit > 0`,
  with exceptions for virtual `istice_mec` landunits inside `glcmask` and virtual
  `istsoil` landunits that keep bare-land SMB forcings alive
  (`main/subgridWeightsMod.F90:313-386`).
- A column is active only if its landunit is active and `wtlunit > 0`, with
  exceptions for `istice_mec` columns inside the glcmask and all urban columns so
  the urban loop structure stays clean (`main/subgridWeightsMod.F90:389-446`).
- A patch is active only if its column is active and `wtcol > 0`
  (`main/subgridWeightsMod.F90:449-480`).
- Setting `all_active=.true.` (namelist) bypasses the cascade and forces every
  child to be active.

Errors in the cascade (active child under inactive parent) are fatal
(`main/subgridWeightsMod.F90:280-308`).

## 9. How the hierarchy is built

At startup, `initGridCells` (`main/initGridCellsMod.F90:47-100+`) allocates all four
non-gridcell vectors for each clump in a single pass, then for each gridcell iterates
`add_topounit → add_landunit → add_column → add_patch` from
`main/initSubgridMod.F90`. That pass sets parent indices and initial weights from the
surface dataset (`elm_varsur%wt_lunit`, `wt_nat_patch`, `wt_glc_mec`). Counts on the
gridcell-level range pointers (`topi/topf`, `lndi/lndf`, `coli/colf`, `pfti/pftf`) are
the accumulated totals. Vertical discretization of every soil / lake column is filled
later in `main/initVerticalMod.F90`.

After initialization — and after every subsequent weight change — the sequence

```
compute_higher_order_weights → set_active → check_weights → setFilters
```

runs via `reweight_wrapup` (`main/reweightMod.F90:28-56`) to keep all derived arrays
and processing filters consistent.

## 10. Accessing the hierarchy from code

Typical loop idioms (they rely on the contiguous index ranges documented above):

```fortran
! Walk every column in a gridcell
do c = grc_pp%coli(g), grc_pp%colf(g)
   ...
end do

! Walk every patch in a landunit
do p = lun_pp%pfti(l), lun_pp%pftf(l)
   ...
end do

! Lookup: get the column index of the first glacier-mec column of gridcell g
l = grc_pp%landunit_indices(istice_mec, g)
if (l /= ispval) then
   do c = lun_pp%coli(l), lun_pp%colf(l)
      ...
   end do
end if
```

These ranges and the reverse-lookup arrays are what let the rest of ELM and
`dyn_subgrid` avoid searches and keep every averaging / conservation operation
O(children).
