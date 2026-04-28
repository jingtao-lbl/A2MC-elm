---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** core orchestration: `f90src/{Main, Ecosim_mods, Modelconfig, Modelpars, Mesh, Utils, Minimath, DebugTools}/`
**Last verified:** 2026-04-24
---

# Grid and Mesh

This doc covers the two files in `f90src/Mesh/`. They set up EcoSIM's spatial discretization — a 2-D rectangular arrangement of soil columns, each divided into vertical soil layers, with up to `JP` plant functional types per column.

## Mental model

EcoSIM's world is a landscape rectangle whose horizontal extent is specified by four corner indices:

```
  (NHW, NVN)  ──────────────  horizontal (X, east-west)
    o──────────────────────x
    │                      │
    │    landscape         │  vertical-in-plan (Y, north-south)
    │    columns           │
    │                      │
    x──────────────────────o
                          (NHE, NVS)
```

`(NHW, NVN)` is the upper-northwest corner; `(NHE, NVS)` is the lower-southeast corner (f90src/Mesh/GridMod.F90:22-29). Every column in the rectangle gets a vertical soil-layer stack with `JZ=20` layers (f90src/Mesh/GridMod.F90:88, 119), and up to `JP=5` PFT slots (from `GridConsts.JP`).

Each column is indexed by `(NY, NX)` where `NY` runs `NVN..NVS` and `NX` runs `NHW..NHE`. Each PFT slot is indexed by `(NZ, NY, NX)` where `NZ` runs `1..JP`. Linearized "column" and "pft" IDs used in flat state arrays are produced by `get_col(NY,NX)` and `get_pft(NZ,NY,NX)` (see §3 below).

## 1. `f90src/Mesh/GridConsts.F90` (57 lines) — shared grid constants and bounds

Module `GridConsts` declares the global grid dimensions and the landscape-wide `bounds` object. All public (f90src/Mesh/GridConsts.F90:4).

Dimension integers (f90src/Mesh/GridConsts.F90:9-15):

| Name | Meaning |
|---|---|
| `JX` | number of columns in X direction (set at runtime, may include halo) |
| `JY` | number of columns in Y direction (set at runtime, may include halo) |
| `JX0`, `JY0` | non-halo horizontal extents (used by `get_col`, `get_pft`) |
| `JZ` | number of soil layers per column (hard-set to 20 in `SetMesh`) |
| `JH` | horizontal halo count (`JX + nextra_grid`) |
| `JV` | vertical halo count (`JY + nextra_grid`) |
| `JD` | `JZ + 1` (one extra for below-bottom flux faces) |

Plant/canopy constants (f90src/Mesh/GridConsts.F90:16-29):

| Name | Value | Purpose |
|---|---|---|
| `JP` | 5 (parameter) | max PFTs per column |
| `NumCanopyLayers` | 10 (parameter) | canopy layers |
| `JS` | 5 (parameter) | snow layers |
| `jroots` | 2 (parameter) | plant-root + mycorrhiza group count |
| `NumLeafZenithSectors` | 4 (parameter) | leaf-zenith sectors `[0, π/2]` |
| `NumOfLeafAzimuthSectors` | 4 (parameter) | leaf-azimuth sectors `[0, π]` |
| `NumOfSkyAzimuthSects` | 4 (parameter) | sky-azimuth sectors `[0, 2π]` |
| `MaxNodesPerBranch` | 25 (parameter) | canopy-branch node count |

Runtime-set plant dimensions (f90src/Mesh/GridConsts.F90:16-21): `NMaxRootSegs`, `MaxNumBranches` (default 10), `NumGrowthStages` (default 10), `NumOfPlantMorphUnits`, `MaxNumRootAxes`, `NumLitterGroups`. These are populated by `InitPlantMorphSize` in `Ecosim_mods/InitAllocMod.F90:152-187` (see `main_orchestration.md` §3).

Microbial complex pointers (f90src/Mesh/GridConsts.F90:30-37): `JGniH`, `JGnfH`, `JGniA`, `JGnfA`, plus counts `NumMicrobAutoTrophCmplx`, `NumHetetr1MicCmplx`, `NumLiveHeterBioms`, `NumLiveAutoBioms` (all populated downstream from `micpar` during `InitAlloc`).

### The `bounds_type` and the singleton `bounds`

`bounds_type` (f90src/Mesh/GridConsts.F90:38-53) carries the landscape extents plus linearized index bookends used by every module that iterates over grids, topo-units, columns, or PFTs:

```fortran
type, public :: bounds_type
 integer :: NHW, NVN, NHE, NVS              ! landscape corner indices
 integer :: begg, endg                       ! grid range
 integer :: begt, endt                       ! topo-unit range
 integer :: begc, endc                       ! column range
 integer :: begp, endp                       ! pft range
 integer :: ngrid, ntopou                    ! totals
 integer :: ncols, npfts                     ! totals
 integer, pointer :: icol(:,:)   => null()   ! column id, shape (JY, JX)
 integer, pointer :: ipft(:,:,:) => null()   ! pft id,    shape (JP, JY, JX)
end type bounds_type
type(bounds_type) :: bounds
```

`bounds%icol(NY, NX)` and `bounds%ipft(NZ, NY, NX)` are populated by `SetMesh`/`SetMeshATS` (see next section). They are NOT the same as `get_col`/`get_pft` return values (see §3 — the former are filled by a dense counter, the latter are closed-form formulas on `NX`, `NY`, `NZ`, `JX0`, `JY0`, `JP`).

## 2. `f90src/Mesh/GridMod.F90` (229 lines)

Module `GridMod`; four public entries (f90src/Mesh/GridMod.F90:7-8): `SetMesh`, `SetMeshATS`, `get_col`, `get_pft`.

### `SetMesh(NHW, NVN, NHE, NVS)` — standalone driver path (:13-125)

Called once by the driver at `drivers/ecosim/ecosim.F90:87`, before `InitModules`. Inputs are `intent(out)` — the routine reads them from the grid netCDF file named in `EcoSIMCtrlMod%grid_file_in`. Steps:

1. Open the grid netCDF file (`ncd_pio_openfile`, :42) and read `ngrid` and `ntopou` dimensions (:44-46).
2. Read `NHW`, `NHE`, `NVN`, `NVS` as scalar variables (:49-71). Abort with `endrun` if any is missing.
3. Close the file (:73).
4. Copy corners into `bounds%NHW/NVN/NHE/NVS` (:76-79).
5. If `first_topou=.true.` (from `EcoSIMCtrlMod`), collapse everything to 1×1 at `(1,1)` (:80-87). This is the "run only the first topo-unit" debug mode.
6. Hard-set `JZ=20` (:88) — the number of soil layers is NOT read from the grid file.
7. Compute `bounds%begg=1; bounds%endg=ngrid`, `bounds%begt=1; bounds%endt=ntopou` (:89-90).
8. Compute extents `JX=(NHE-NHW)+1`, `JY=(NVS-NVN)+1`, and stash non-halo copies `JX0=JX`, `JY0=JY` (:92-93).
9. Set column/pft totals: `bounds%ncols=JX*JY`, `bounds%npfts=ncols*JP`, with `begc=1; endc=ncols`, `begp=1; endp=npfts` (:95-98).
10. Allocate `bounds%icol(JY,JX)` and `bounds%ipft(JP,JY,JX)` (:100-101).
11. If `column_mode=.true.` (from `EcoSIMConfig`), `nextra_grid=0`; else `nextra_grid=1`. Add the halo to `JX`, `JY` (:103-105).
12. Populate `bounds%icol(NY,NX) = ic` and `bounds%ipft(NZ,NY,NX) = ip` with dense sequential counters (:107-117).
13. Set derived halo constants `JH=JX+nextra_grid`, `JV=JY+nextra_grid`, `JD=JZ+1` (:119-123). Note `JZ` is re-set to 20 again at :119 — a redundant belt-and-suspenders reset.

### `SetMeshATS(NHW, NVN, NHE, NVS)` — ATS-coupled path (:132-206)

Same idea, but inputs are `intent(in)` because ATS (the coupled hydrology engine) provides the mesh. No netCDF read. Otherwise the logic mirrors `SetMesh`: copy to `bounds`, compute `JX0/JY0/ncols/npfts`, allocate `icol/ipft`, apply the halo, populate `icol/ipft` with dense counters. `JZ` is NOT re-set here — it is assumed to have been set by the ATS coupling layer before `SetMeshATS` is called.

Called from `drivers/ATSEcoSIM/` and `f90src/ATSUtils/ATSEcoSIMInitMod.F90`.

### `get_col(NY, NX)` (:210-217)

Closed-form linear column index:

```fortran
get_col = (NX - 1) * JY0 + NY
```

Uses non-halo extents `JY0` from `GridConsts`. Note the ordering: X is the "outer" dimension, Y is the "inner" dimension (column-major in (NY,NX)). This matches the allocation pattern of `bounds%icol(JY,JX)`.

### `get_pft(NZ, NY, NX)` (:219-227)

Closed-form linear PFT index:

```fortran
get_pft = (NX - 1) * (JP * JY0) + (NY - 1) * JP + NZ
```

PFT is the innermost dimension, Y next, X outermost. Matches `bounds%ipft(JP,JY,JX)`.

## 3. Indexing conventions — quick reference

- **Horizontal iteration idiom** across a column grid (used everywhere):
  ```fortran
  DO NX = NHW, NHE
    DO NY = NVN, NVS
      ! column (NY, NX)
    ENDDO
  ENDDO
  ```
- **PFT iteration idiom** inside a column:
  ```fortran
  DO NZ = 1, JP            ! or a subrange like 1..NP_col(NY,NX)
    ! pft (NZ, NY, NX)
  ENDDO
  ```
- **Vertical iteration idiom** for soil layers:
  ```fortran
  DO L = NU_col(NY,NX), NL_col(NY,NX)
    ! soil layer L in column (NY, NX)
  ENDDO
  ```
  where `NU_col` / `NL_col` are the upper/lower active layer indices per column (declared in `Ecosim_datatype/GridDataType`).

- **JZ is fixed at 20 layers.** This is a hard-coded build-time assumption in `SetMesh` (:88, :119). Any change requires source modification, not a runtime input.

- **JP is fixed at 5 PFTs per column** (parameter in `GridConsts`, :22). Same story.

- **`bounds%icol(NY,NX)`** gives a 1-based dense column ID from `(NY,NX)` coordinates (populated by `SetMesh`). **`get_col(NY,NX)`** gives the same mapping via a closed-form formula, usable without the `bounds` object.

- **Halo behavior.** `JX`, `JY` are enlarged by `nextra_grid` (1 by default, 0 if `column_mode`) after `icol`/`ipft` are filled. That means halo cells have no `icol` entry but downstream code treats `JX`, `JY` as the iteration bound. Always distinguish `(JX0,JY0)` (true extent) from `(JX,JY)` (extent + halo) when writing loops over real columns vs. flux faces.

- **No horizontal transport across lateral neighbors by default?** No — lateral flux code IS present (see `Transport/` and `HydroTherm/`), but the mesh itself does not encode explicit neighbor pointers. Neighbors are addressed by `NX±1`, `NY±1` index arithmetic; the `iWestEastDirection`/`iNorthSouthDirection`/`iVerticalDirection` flux-direction integer codes from `Modelconfig/ElmIDMod.F90:27-29` disambiguate when needed.

- **`grid_mode=3`** (from `EcoSIMCtrlMod.F90:78`) means "vertical only" — a flag consumed by the transport solver to skip lateral terms. The default value makes sense for single-column / single-topounit runs; multi-column runs should set `grid_mode` accordingly.
