---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# ELM Subgrid Hierarchy

## 1. Overview

ELM represents a heterogeneous land surface with a five-level nested hierarchy. Each level owns its own derived type, defined in `components/elm/src/data_types/`. The types are declared `public, target` and exposed as **singleton module-level instances** (`grc_pp`, `top_pp`, `lun_pp`, `col_pp`, `veg_pp`). All numeric arrays inside these types are 1-D, allocated over processor-local bounds (`begg:endg`, `begt:endt`, `begl:endl`, `begc:endc`, `begp:endp`).

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
                    |  itype, active, snl, dz/z/zi, glc_topo, meangradz
                    |  hydrologically_active, is_fates, is_soil, is_crop, is_lake
                    |  wtgcell, wttopounit, wtlunit
                    |
                    +-- PATCH / VEGETATION  (veg_pp,
                          data_types/VegetationType.F90)
                          itype (0..24 PFT/CFT), mxy, active
                          is_fates, is_veg, is_bareground, wt_ed
                          is_on_soil_col, is_on_crop_col
                          wtgcell, wttopounit, wtlunit, wtcol, wtgcell_iac
```

`numpft` and `natpft_size`, `cft_size`, `maxpatch_glcmec` control how many entries exist at the patch / column level for each landunit type. PFT indexing at the `veg_pp%itype` level follows the header of `data_types/VegetationType.F90:9-34`.

**New fields at d40b843 vs 60d9aad:**
- **Column** (`col_pp`): `meangradz` (mean topographic gradient), and three logical class-flag pointers `is_soil`, `is_crop`, `is_lake` complementing the existing `is_fates` and `hydrologically_active`.
- **Vegetation** (`veg_pp`): `wtgcell_iac` (weight relative to gridcell-land, used for IAC data passing; allocated only when `iac_present`); `is_on_soil_col` and `is_on_crop_col` logical pointers.

## 2. Gridcell (`grc_pp`)

Source: `data_types/GridcellType.F90`.

The gridcell holds processor-global geographic metadata and **range pointers** into every subgrid level beneath it.

| Field | Units / type | Meaning |
|---|---|---|
| `gindex(:)` | integer | Global (unstructured) index |
| `area`, `lat`, `lon`, `latdeg`, `londeg` | km², radians, degrees | Geometry |
| `topi(:)`, `topf(:)`, `ntopounits(:)` | integer | Topounit range & count |
| `lndi(:)`, `lndf(:)`, `nlandunits(:)` | integer | Landunit range & count |
| `coli(:)`, `colf(:)`, `ncolumns(:)` | integer | Column range & count |
| `pfti(:)`, `pftf(:)`, `npfts(:)` | integer | Patch range & count |
| `landunit_indices(1:max_lunit, begg:endg)` | integer | Reverse map: for landunit type `l`, the index in `lun_pp` (or `ispval`). |
| `stdev_elev`, `sky_view`, `terrain_config`, `sinsl_cosas`, `sinsl_sinas` | real | Solar / topographic downscaling factors |
| `max_dayl`, `dayl`, `prev_dayl` | seconds | Daylength cache |
| `elevation`, `MaxElevation`, `froudenum` | m, dimensionless | Mean / max surface elevation (`MaxElevation` is used by precipitation downscaling) |

Allocation happens in `grc_pp_init`, which initializes every pointer to `ispval` / `spval` sentinels.

## 3. Topounit (`top_pp`)

Source: `data_types/TopounitType.F90`. Added in 2015 to give the gridcell-to-landunit edge a physical carrier for slope, aspect, and mean surface parameters. `max_topounits` is read from the surface dataset; by default it is 1.

| Field | Meaning |
|---|---|
| `gridcell(:)`, `topo_grc_ind(:)`, `wtgcell(:)` | Parent gridcell, ordinal within gridcell, weight |
| `lndi/lndf/nlandunits`, `coli/colf/ncolumns`, `pfti/pftf/npfts` | Child ranges & counts |
| `landunit_indices(1:max_lunit, begt:endt)` | Landunit reverse map |
| `active(:)` | True if this topounit participates in the time step |
| `area`, `lat`, `lon`, `elevation` | Mean geometry |
| `slope`, `aspect`, `emissivity` | Surface-scale physical properties |
| `surfalb_dir(:,:)`, `surfalb_dif(:,:)` | Mean surface albedo per radiation band |

The `landunit_varcon`-typed landunit counting and the `top_pp%landunit_indices` array are the mechanism by which `subgridWeightsMod.get_landunit_weight(t, ltype)` and `set_landunit_weight(t, ltype, w)` look up a landunit on a topounit without a linear search.

## 4. Landunit (`lun_pp`)

Source: `data_types/LandunitType.F90`.

| Field | Meaning |
|---|---|
| `gridcell(:)`, `topounit(:)` | Parent indices |
| `wtgcell`, `wttopounit` | Weight relative to gridcell / topounit |
| `coli/colf/ncolumns`, `pfti/pftf/npfts` | Column / patch ranges under this landunit |
| `itype(:)` | Landunit type code (`istsoil=1`, `istcrop=2`, `istice=3`, `istice_mec=4`, `istdlak=5`, `istwet=6`, `isturb_tbd=7`, `isturb_hd=8`, `isturb_md=9`; `max_lunit=9`) |
| `ifspecial`, `lakpoi`, `urbpoi`, `glcmecpoi` | Type-class flags |
| `active(:)` | True if this landunit participates in the time step |
| `canyon_hwr`, `wtroad_perv`, `wtlunit_roof`, `ht_roof`, `z_0_town`, `z_d_town` | Urban parameters |

`landunit_is_special(ltype)` returns `.false.` only for `istsoil` and `istcrop`, marking every other landunit as a "special" carrier.

## 5. Column (`col_pp`)

Source: `data_types/ColumnType.F90` (196 lines at d40b843).

| Field | Source | Meaning |
|---|---|---|
| `gridcell`, `topounit`, `landunit`, `wtgcell`, `wttopounit`, `wtlunit` | `:35-40` | Parent indices & weights |
| `pfti/pftf/npfts` | `:43-45` | Child patch range / count |
| `itype(:)` | `:48` | Column type: shares standard landunit codes (1..6) plus the urban-specific codes (`icol_roof=71`, `icol_sunwall=72`, `icol_shadewall=73`, `icol_road_imperv=74`, `icol_road_perv=75`); for ice-mec columns, `itype = istice_mec*100 + icemec_class` |
| `active(:)` | `:49` | Runtime active flag |
| `glc_topo`, `micro_sigma`, `n_melt`, `topo_slope`, `topo_std`, `hslp_p10`, `nlevbed`, `zibed` | `:52-59` | Microtopography, hillslope percentiles, bedrock depth |
| **`meangradz(:)`** | `:60` | **NEW.** Mean topographic gradient at the column level. |
| `snl`, `dz`, `z`, `zi`, `zii`, `dz_lake`, `z_lake`, `lakedepth` | `:63-70` | Snow-layer count and the `-nlevsno+1:nlevgrnd` vertical discretization; lake-specific levels |
| `hydrologically_active(:)` | `:73` | Pre-cached result of `is_hydrologically_active(col_itype, lun_itype)` |
| `is_fates(:)` | `:76` | True for columns under FATES control; default `.false.` at allocation time |
| **`is_soil(:)`** | `:80` | **NEW.** True if the column is a soil column. |
| **`is_crop(:)`** | `:81` | **NEW.** True if the column is a crop column. |
| **`is_lake(:)`** | `:82` | **NEW.** True if the column is a lake column. |

The new class-flag pointers (`is_soil`, `is_crop`, `is_lake`) complement the existing `is_fates` and `hydrologically_active`. They are populated in `col_pp_init` (along with their FreeMemory entries) so that downstream kernels can branch on column class without an `itype` lookup. `alm_fates%init` at api.43 uses **`col_pp%is_soil(c)`** as the FATES-site test (`main/elmfates_interfaceMod.F90:933`), replacing the older `lun_pp%itype(l) == istsoil` test in 60d9aad.

## 6. Patch / Vegetation (`veg_pp`)

Source: `data_types/VegetationType.F90` (180 lines at d40b843).

| Field | Source | Meaning |
|---|---|---|
| `gridcell`, `topounit`, `landunit`, `column` (+ matching weights) | `:57-66` | Parent indices and weights through every level |
| **`wtgcell_iac(:)`** | `:60` | **NEW.** Weight relative to gridcell-land, used for IAC data passing. Allocated only when `iac_present`. |
| `itype(:)` | `:69` | PFT / CFT index (0 = bare ground, 1..8 = trees, 9..11 = shrubs, 12..14 = grass, 15..24 = crops) |
| `mxy(:)` | `:70` | Index for 2-D history mapping |
| `active(:)` | `:71` | Runtime active flag |
| **`is_on_soil_col(:)`** | `:73` | **NEW.** True if this patch is on a soil column. |
| **`is_on_crop_col(:)`** | `:74` | **NEW.** True if this patch is on a crop-associated column. |
| `is_veg(:)`, `is_bareground(:)`, `wt_ed(:)`, `sp_pftorder_index(:)` | `:77-80` | Allocated only when `use_fates=.true.`; `wt_ed` is the weight FATES publishes back to ELM. |
| `is_fates(:)` | `:81` | Static flag — true for any patch slot reserved for FATES, even when not currently mapped to a live FATES cohort linked list |

## 7. Weight relationships

Four primitive weights are stored per level:

- `top_pp%wtgcell` — topounit share of a gridcell
- `lun_pp%wttopounit` — landunit share of a topounit
- `col_pp%wtlunit` — column share of a landunit
- `veg_pp%wtcol` — patch share of a column

Higher-order weights are **derived** by `compute_higher_order_weights` (`main/subgridWeightsMod.F90`):

```
lun%wtgcell(l)    = lun%wttopounit(l) * top%wtgcell(t)
col%wttopounit(c) = col%wtlunit(c)    * lun%wttopounit(l)
col%wtgcell(c)    = col%wtlunit(c)    * lun%wtgcell(l)
veg%wtlunit(p)    = veg%wtcol(p)      * col%wtlunit(c)
veg%wttopounit(p) = veg%wtcol(p)      * col%wttopounit(c)
veg%wtgcell(p)    = veg%wtcol(p)      * col%wtgcell(c)
```

The IAC weight `veg%wtgcell_iac` is computed and used separately (only when `iac_present`).

The invariants enforced by `check_weights`:

1. On every column, landunit, topounit, and gridcell, the sum of child weights equals 1.
2. On every **active** parent, the sum of weights over **active** children equals 1.
3. On every inactive parent, the sum over active children equals 0 **or** 1.

These rules allow the safe averaging pattern (loop over children, multiply by child weight, skip inactive / zero-weight children).

## 8. Active flags

`set_active` (in `subgridWeightsMod`) sets `active` at all four non-gridcell levels, enforcing the cascade:

- A landunit is active only if its parent topounit is active **and** `wttopounit > 0`, with exceptions for virtual `istice_mec` landunits inside `glcmask` and virtual `istsoil` landunits that keep bare-land SMB forcings alive.
- A column is active only if its landunit is active and `wtlunit > 0`, with exceptions for `istice_mec` columns inside the glcmask and all urban columns.
- A patch is active only if its column is active and `wtcol > 0`.
- Setting `all_active=.true.` (namelist) bypasses the cascade.

Errors in the cascade (active child under inactive parent) are fatal.

## 9. How the hierarchy is built

At startup, `initGridCells` (`main/initGridCellsMod.F90`) allocates all four non-gridcell vectors for each clump in a single pass, then for each gridcell iterates `add_topounit → add_landunit → add_column → add_patch` from `main/initSubgridMod.F90`. That pass sets parent indices and initial weights from the surface dataset (`elm_varsur%wt_lunit`, `wt_nat_patch`, `wt_glc_mec`). Vertical discretization of every soil / lake column is filled later in `main/initVerticalMod.F90`.

After initialization — and after every subsequent weight change — the sequence

```
compute_higher_order_weights → set_active → check_weights → setFilters
```

runs via `reweight_wrapup` (`main/reweightMod.F90`) to keep all derived arrays and processing filters consistent.

## 10. Accessing the hierarchy from code

Typical loop idioms:

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

! NEW at d40b843: branch on column class without itype lookup
if (col_pp%is_soil(c)) then
   ! soil-only logic
end if
```

These ranges and the reverse-lookup arrays are what let the rest of ELM and `dyn_subgrid` avoid searches and keep every averaging / conservation operation O(children).
