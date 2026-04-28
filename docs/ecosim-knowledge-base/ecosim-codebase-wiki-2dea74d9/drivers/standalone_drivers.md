---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `drivers/mockbatch/`, `drivers/plantbgc/`, `drivers/tools/`
**Last verified:** 2026-04-24
---

# Standalone Drivers — Mock, Plant, Tools

This document covers the smaller drivers in the EcoSIM tree. None of
them exercise real EcoSIM physics at the scale of `ecosim.x`,
`boxsbgc.x`, or `aquachem.x`. They are either scaffolding templates for
developers, deliberately stubbed placeholders reserved for future work,
or standalone command-line utilities for I/O / time / history files.

## `drivers/mockbatch/` — The Scaffolding Template

| File | Lines | Role |
|---|---|---|
| `drivers/mockbatch/mockdriver.F90` | 167 | `program main` + `RunModel` — the template loop |
| `drivers/mockbatch/MockMod.F90` | 96 | `getvarllen`, `getvarlist`, `initmodel`, `runmock` — a no-op BGC implementation |

Build target: `mock.x` (`drivers/mockbatch/CMakeLists.txt:1-7`).

### What it does

Nothing, by design. The entire "BGC" routine is copy-through:

```fortran
! drivers/mockbatch/MockMod.F90:57-75
subroutine runmock(nvars, ystates0l, ystatesfl, err_status)
  ...
  call err_status%reset()
  do jj = 1, 5
    ystatesfl(jj)   = ystates0l(jj)      ! 5 state variables, identity
    ystatesfl(jj+5) = ystates0l(jj+5)    ! 5 flux variables, identity
  enddo
end subroutine runmock
```

### Why it exists

`mockdriver.F90` is the canonical *template* used to bootstrap new batch
drivers. Its `program main` and `RunModel` (lines 1-166) are structurally
identical to `aquachem.F90` and `batchsbgc.F90`:

```
program main
  ...
  call namelist_to_buffer(namelist_filename, namelist_buffer)
  call RunModel(namelist_buffer)
end program main

subroutine RunModel(namelist_buffer)
  ...
  namelist /driver_nml/ model_name, case_id, hist_freq
  ...
  nvars = getvarllen()
  ...
  call initmodel(nvars, ystates0l, err_status)
  ...
  do
    call timer%update_time_stamp()
    call runmock(nvars, ystates0l, ystatesfl, err_status)
    ...
    call hist%hist_wrap(ystatesf, timer)
    if(timer%its_time_to_exit()) exit
  enddo
  call hist%histrst('mockmodel', 'write', yymmddhhss)
end subroutine RunModel
```

A developer adding a new box model typically copies
`drivers/mockbatch/` to a new folder, renames the `program` / `module`,
replaces the body of `runmock` and the state-variable counts, and
updates `drivers/CMakeLists.txt` to include the new folder.

### Variable list

`MockMod::getvarlist` (lines 30-52) declares ten generic slots:
`var1_con ... var5_con` (state variables, units `mol m-3`) and
`flx1_con ... flx5_con` (fluxes, units `mol m-2 s-1`). The long names
are deliberately uninformative (`"flx1"` is hard-coded even for
`flx2`-`flx5`), because the list is never meant to be consumed by
anything real.

### Namelist

`namelist /driver_nml/ model_name, case_id, hist_freq` — exactly the
same minimum three-field namelist used by `aquachem.x` (minus `salton`).

## `drivers/plantbgc/` — Single-Plant Skeleton (Reserved)

| File | Lines | Role |
|---|---|---|
| `drivers/plantbgc/plantdriver.F90` | 166 | `program main` + `RunModel` |
| `drivers/plantbgc/PlantMod.F90` | 96 | Same template body as `MockMod` |

Build target: `plant.x` (`drivers/plantbgc/CMakeLists.txt:1-19`). This
target is built as a library (`add_ecosim_library(plant_driver ...)`) in
addition to an executable, so that other targets could link against it
if needed.

### Status

**As of commit `2dea74d9`, `PlantMod.F90` is byte-for-byte the same
template as `MockMod.F90` except for symbol names.** The `runplant`
routine (`PlantMod.F90:57-75`) is the same identity-copy-through pattern
as `runmock`, and `initmodel` (lines 80-91) seeds the same
`ystatesfl(1:5)=0.01` / `ystatesfl(6:10)=1e-5` pattern. The two files
differ only in:

- `module MockMod` vs `module PlantMod`
- `public :: runmock` vs `public :: runplant`
- The `Description` strings in `usage()`

### Intent

The folder exists to reserve the slot for a real single-plant driver
that would exercise EcoSIM's plant module (`f90src/Plant_bgc/PlantMod`)
in isolation — the plant analog of what `boxsbgc.x` does for microbial
BGC. Until that lands, `plant.x` is a placeholder. Treat it as the
template for a future doc, not as a functioning driver.

## `drivers/tools/` — Utility Executables

Twelve F90 files, of which eight build into CLI executables listed in
`drivers/tools/CMakeLists.txt:14-24`. These are developer utilities for
I/O testing, file format verification, climate-file transformation, and
timer / history / restart round-trips.

### Inventory

| Source file | Executable | Built? | Purpose |
|---|---|---|---|
| `ClimTransformer.F90` | `ClimTransformer.x` | yes | Reads a list of tabular climate files (daily or hourly) and writes a consolidated NetCDF climate-forcing file consumable by the full driver. Takes 3 CLI args: `inflist`, `ncfilename`, `hour|day` |
| `ClimReader.F90` | `ClimReader.x` | yes | Opens an existing climate NetCDF file and reads one record for one year / layer as a smoke test for `ClimReadMod::ReadClimNC`. CLI: `infile iyear` |
| `GridReader.F90` | — | **no** (source present, not in CMake) | Opens a grid NetCDF file and reads `NHW`, `NHE`, `NVN`, `NVS`. Source available at `drivers/tools/GridReader.F90:1-52` but no `add_ecosim_executable` line — it has to be added manually to the build list to use |
| `PlantManagementReader.F90` | `PlantManagementReader.x` | yes | Tests the plant-management file reader (`PlantInfoMod::ReadPlantInfo`) by invoking it with a namelist that specifies `pft_mgmt_in`, `year0`, `yearf`, `NHW..NVS`, `NPS`, `nyears` |
| `SoilManagementReader.F90` | `SoilManagementReader.x` | yes | Tests `ReadManagementMod::ReadManagementFiles` for soil fertilizer / management schedules. CLI: `soil_mgmt_in` file path |
| `SoilWarmReadTest.F90` | `SoilWarmReadTest.x` | yes | Tests the soil-warming forcing path. Hardcodes a `warming_exp` string (`'4K;1m;Blodget.ctrl.ecosim.h1.xxxx-01-00-00000.nc;2014/01/01:2018/12/31'`), calls `config_soil_warming`, and loops over years 2013-2020 verifying `check_warming_dates` |
| `etimerTest.F90` | `etimerTest.x` | yes | Tests the ecosim time module — day-of-week computations (`getdow`) across century boundaries, plus `get_steps_from_ymdhs`. CLI: namelist file |
| `NamelistTest.F90` | `NamelistTest.x` | yes | Round-trip test of the `etimer` namelist + associated time-arithmetic. CLI: namelist file |
| `HFileTest.F90` | `HFileTest.x` | yes | Tests the history-file machinery (`HistFileMod`) without running any physics. Writes synthetic data for `TSOI`, `VSM` across 24 hours × some number of days |
| `restartTest.F90` | `restartTest.x` | yes | Writes and reads a restart file through `RestartMod::restFile` to verify the round-trip |
| `EcoATSTest.F90` | — | no (commented out at CMakeLists.txt:23) | Minimal ATS-coupling smoke test (`program EcoATSTest`, 24 lines) — calls `SetBGCSizes` and `Init_EcoSIM` only. Superseded by `drivers/ATSEcoSIM/ATSEcoSIM_test.F90` |
| `EcoATSTest_old.F90` | — | no | Earlier, more elaborate ATS-coupling test kept for reference. Allocates every `state` / `props` member by hand, fills with sample values, then would call `ATS2EcoSIMData` / `Run_EcoSIM_one_step` / `EcoSIM2ATSData`. Also superseded |

Eight install targets are registered at
`drivers/tools/CMakeLists.txt:104-115`.

### Typical usage — `ClimTransformer.x`

The most user-visible tool. It reads a list-of-files (one path per line,
each path pointing to a plain-text climate table) and writes them into
a single NetCDF with dimensions `year` (unlimited), `day` (366),
`hour` (24, for hourly data), and `ngrid` (1). Variables written for
the hourly case include `TMPH` (air temperature at 2 m),
`WINDH` (wind speed at 10 m), `RAINH`, and others (see
`ClimTransformer.F90:67-80` for the full variable definitions).

Usage:

```
./ClimTransformer.x  file_list.txt  my_site_climate.nc  hour
./ClimTransformer.x  file_list.txt  my_site_climate.nc  day
```

The daily branch (not shown above) writes a simpler record set.

### Typical usage — `ClimReader.x`

Smoke-tests the format produced by `ClimTransformer.x` (or any
compatible NetCDF climate file) by reading one record:

```
./ClimReader.x  my_site_climate.nc  2012
```

Internally sets `lverb=.true.`, `irec=1`, `L=2`, then calls
`ReadClimNC(iyear, irec, L, atmf)` from `ClimReadMod`. It is the
simplest integration-test for the climate-input path.

### Typical usage — management readers

```
./SoilManagementReader.x  path/to/soil_mgmt_file
./PlantManagementReader.x  path/to/pft_mgmt_namelist
```

Both exist to exercise the management-file readers outside the context
of a full EcoSIM run, which is useful when debugging new file formats
or regression-testing a change to the reader code.

### Typical usage — I/O / timer tests

These are developer tools rather than user tools:

- `HFileTest.x <namelist>` — write a handful of synthetic history
  records and close the tape.
- `restartTest.x <namelist>` — round-trip a restart file.
- `etimerTest.x <namelist>` / `NamelistTest.x <namelist>` — timer
  arithmetic and namelist parsing.
- `SoilWarmReadTest.x` — takes no arguments; its test input is
  hardcoded. Exists as a self-contained reproducer for a specific past
  bug in the warming-forcing reader.

### A note on CMake layout

All eight tools share the same include-directory recipe (`Utils`,
`Mesh`, `Modelconfig`, `Minimath`, `Ecosim_datatype`, `IOutils`). The
`SoilWarmReadTest.x` target additionally pulls in `Disturbances`
(`drivers/tools/CMakeLists.txt:94-101`). Adding a new tool is a
matter of:

1. Drop a new `.F90` file under `drivers/tools/`.
2. Add `add_ecosim_executable(<name>.x <name>.F90)`.
3. Add a `target_include_directories` block.
4. If installing, add to the `install(TARGETS ...)` list at the bottom.

`GridReader.F90` is already present but none of steps 2-4 have been
done for it, which is why it does not appear in the built-outputs list.

## How Do These Fit Into the Wider Driver Story?

Of the eight driver subdirectories, the two in this doc and the `tools`
directory are the *non-physics* half of the tree:

- `ecosim/` — full physics. Production driver.
- `ATSEcoSIM/` — ATS coupling test harness.
- `aquachem/`, `boxsbgc/` — physics-subset box drivers for chemistry
  and microbial BGC.
- **`mockbatch/` — template for new box drivers, no physics.**
- **`plantbgc/` — reserved for a future single-plant driver, currently
  a copy of `mockbatch/`.**
- **`tools/` — CLI utilities for climate-file transformation, grid /
  management / restart / history / timer round-trips.**

All of them share the same `bhistMod` / `ecosim_Time_Mod` / `fileUtil`
/ `abortutils` infrastructure. Changes to those shared libraries will
affect every driver in this document.

## Cross-References

- Template-sibling drivers with real bodies:
  [`aquachem.md`](aquachem.md), [`boxsbgc.md`](boxsbgc.md).
- Full driver: [`ecosim_main.md`](ecosim_main.md).
- ATS coupling and the superseded `EcoATSTest*.F90` prototypes:
  [`ats_coupling.md`](ats_coupling.md).
- Climate I/O: `f90src/Modelforc/ClimReadMod.F90` (the library behind
  `ClimReader.x` and `ClimTransformer.x`).
- Restart: `f90src/IOutils/RestartMod.F90`.
- History: `f90src/IOutils/HistFileMod.F90`, `f90src/IOutils/bhistMod.F90`.
- Timer: `f90src/Utils/ecosim_Time_Mod.F90`.
