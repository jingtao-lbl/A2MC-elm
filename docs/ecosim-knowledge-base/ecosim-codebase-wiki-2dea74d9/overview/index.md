---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/` + `drivers/` (full repo)
**Last verified:** 2026-04-24
---

# Overview

## What EcoSIM is

EcoSIM is "a biogeochemical modeling library spins off the ecosys model" (`README.md:3`). The repository builds a reusable Fortran library (the `f90src/` tree, organized by subsystem) and a set of executables under `drivers/` that link against it. Internal version is `ECOSIM_VERSION = 0.1.0` (assembled from the three numeric fields at `CMakeLists.txt:6-9`).

At its core the code integrates a coupled terrestrial ecosystem: soil/canopy/snow energy and water fluxes, soil/aqueous geochemistry, microbial transformations of organic matter, plant biogeochemistry (canopy radiation, photosynthesis, allocation, root BGC, phenology), gas and solute transport, disturbances (fire, erosion, tillage, fertilization, soil warming), and column-scale balance diagnostics.

The standalone driver entry point is the program `main` in `drivers/ecosim/ecosim.F90` (`drivers/ecosim/ecosim.F90:1`). Its own comment header describes it as "THIS SUBROUTINE READS THE RUNSCRIPT AND ENTERS FILENAMES INTO DATA ARRAYS FOR USE IN 'READS' AND 'READQ'. WHEN FINISHED THIS SUBROUTINE CALLS 'SOIL' WHICH IS THE MAIN SUBROUTINE FROM WHICH ALL OTHERS ARE CALLED" (`drivers/ecosim/ecosim.F90:3-6`), a lineage comment inherited from the ecosys code base.

## Execution modes

EcoSIM ships five driver programs plus one ATS-coupling harness and a cluster of standalone test tools. All of them share the same `f90src/` library.

### 1. Standalone — `drivers/ecosim/`

`drivers/ecosim/ecosim.F90` is the production driver. Its control flow, reading the source top-to-bottom:

1. Parse the namelist file from `argv[1]` via `call namelist_to_buffer(...)` (`drivers/ecosim/ecosim.F90:71`) and `call readnamelist(...)` (`drivers/ecosim/ecosim.F90:74`, implemented at `drivers/ecosim/EcoSIMAPI.F90:124`).
2. Lay out the 2-D/3-D horizontal mesh via `call SetMesh(NHW,NVN,NHE,NVS)` (`drivers/ecosim/ecosim.F90:87`, implemented in `f90src/Mesh/GridMod.F90`).
3. Allocate every `Ecosim_datatype/*DataType.F90` state array through `call InitModules()` (`drivers/ecosim/ecosim.F90:89`, implemented in `f90src/Main/InitEcoSIM.F90:15`). `InitModules` chains `InitAlloc`, optional plant-trait-table reading, `units%Initailize`, `InitPlantDisturbance`, `InitUptake`, `initNitro`, `InitRedist`, `InitErosion`, `InitHour1`, `InitTranspNoSalt`, `hist_ecosim%Init`, and `MicAPI_Init` (`f90src/Main/InitEcoSIM.F90:34-57`).
4. Build the history tape configuration (`call hist_htapes_build`, `drivers/ecosim/ecosim.F90:115`) and configure the solver (`call set_ecosim_solver(...)`, `drivers/ecosim/ecosim.F90:125`).
5. Loop over climate years, calling `call AdvanceModelOneYear(NHW,NHE,NVN,NVS,nlend)` (`drivers/ecosim/ecosim.F90:140`, implemented at `drivers/ecosim/EcoSIMAPI.F90:321`).

`AdvanceModelOneYear` itself drives each sub-daily step through the subsystem sequence encoded in `Run_EcoSIM_one_step` (`drivers/ecosim/EcoSIMAPI.F90:35`), in this order:

| Step | Call site | Subsystem |
|---|---|---|
| 1 | `CALL HOUR1(...)` (`drivers/ecosim/EcoSIMAPI.F90:47`) | Sub-daily surface energy/water update and forcing staging |
| 2 | `CALL WATSUB(...)` (`drivers/ecosim/EcoSIMAPI.F90:54`) | Soil water/heat fluxes and energy balance |
| 3 | `CALL MicrobeModel(...)` (`drivers/ecosim/EcoSIMAPI.F90:61`) | Soil microbial biogeochemistry (guarded by `microbial_model`) |
| 4 | `call PlantModel(...)` (`drivers/ecosim/EcoSIMAPI.F90:69`) | Plant BGC (guarded by `plant_model .and. .not.ldo_radiation_test`) |
| 5 | `CALL soluteModel(...)` (`drivers/ecosim/EcoSIMAPI.F90:78`) | Aqueous equilibrium chemistry (guarded by `soichem_model`) |
| 6 | `CALL TranspNoSalt(...)` (`drivers/ecosim/EcoSIMAPI.F90:87`) | Gas and non-salt solute transport |
| 7 | `CALL TranspSalt(...)` (`drivers/ecosim/EcoSIMAPI.F90:96`) | Salt ion transport (guarded by `salt_model`) |
| 8 | `CALL EROSION(...)` (`drivers/ecosim/EcoSIMAPI.F90:106`) | Sediment detachment/deposition |
| 9 | `CALL REDIST(...)` (`drivers/ecosim/EcoSIMAPI.F90:113`) | Redistribute fluxes into state updates |
| 10 | `call DiagSoilGasPressure(...)` + `EndCheckBalances(...)` (`drivers/ecosim/EcoSIMAPI.F90:117-119`) | Diagnostics and closure checks |

After the last year, the run is cleaned up with `call DestructEcoSIM` (`drivers/ecosim/ecosim.F90:156`, implemented in `f90src/Main/EcoSIMDesctruct.F90`).

### 2. ATS-coupled — `drivers/ATSEcoSIM/` + `f90src/ATSUtils/`

The test harness `drivers/ATSEcoSIM/ATSEcoSIM_test.F90` (program `EcoATSTest`, `drivers/ATSEcoSIM/ATSEcoSIM_test.F90:1`) exercises the coupling path used by the Advanced Terrestrial Simulator (ATS). The coupling layer lives in `f90src/ATSUtils/`:

- `ATSCPLMod.F90` — coupling state holders.
- `ATSEcoSIMInitMod.F90` — initialization (`Init_EcoSIM_Soil`, `THETRX`).
- `ATSEcoSIMAdvanceMod.F90` — per-step advance (`RunEcoSIMSurfaceBalance`).
- `BGC_containers.F90` — `BGCState`, `BGCProperties`, `BGCSizes` derived types adapted from Alquimia (`f90src/ATSUtils/BGC_containers.F90:2-5`).
- `c_f_interface_module.F90` — C/Fortran interop, also adapted from Alquimia.
- `SharedDataMod.F90` — scratch data holders and grid bookkeeping for ATS hand-off (`f90src/ATSUtils/SharedDataMod.F90:14-20`).
- `ecosim_wrappers.F90` — compiler-neutral wrappers around the EcoSIM F90 driver entry points (`f90src/ATSUtils/ecosim_wrappers.F90:1`).

The ATS path is activated at build time by setting `ATS_ECOSIM=TRUE` in the CMake configuration (`CMakeLists.txt:172`), which changes TPL handling and linker flags (`CMakeLists.txt:179-232`).

### 3. Specialized batch drivers

Four batch drivers exercise individual subsystems against prescribed forcing, which is helpful for unit testing, parameter sensitivity, and integration with external solvers:

| Driver | Program | Purpose |
|---|---|---|
| `drivers/aquachem/` | `drivers/aquachem/aquachem.F90` (program `main`) | Standalone aqueous-chemistry solver (module `AquachemMod`, plus `AquaSaltChemMod` for salt mode). Exposes `initmodel`, `runchem`, `getvarlist`/`getvarllen`. |
| `drivers/boxsbgc/` | `drivers/boxsbgc/batchsbgc.F90` (program `main`; "Single layer model", `drivers/boxsbgc/batchsbgc.F90:1`) | Single-layer box run of the soil-BGC pipeline; uses `batchmod` (`drivers/boxsbgc/batchmod.F90`: "configure the batch mode of the soil bgc", `drivers/boxsbgc/batchmod.F90`) and `ChemMod`/`ForcTypeMod`/`MicIDMod` helpers. |
| `drivers/mockbatch/` | `drivers/mockbatch/mockdriver.F90` (program `main`) | Minimal-dependency mock driver (`MockMod` exposes `initmodel`, `getvarlist`, `getvarllen`). |
| `drivers/plantbgc/` | `drivers/plantbgc/plantdriver.F90` (program `main`) | Standalone plant-BGC driver (`PlantMod` exposes `initmodel`, `getvarlist`, `getvarllen`). |

A shared ID module lives in `drivers/boxshared/ChemIDMod.F90` and is reused by the chemistry and plant box drivers (`public :: getvarlist_nosalt`, `drivers/boxshared/ChemIDMod.F90`).

### 4. Standalone test tools — `drivers/tools/`

Twelve small programs live under `drivers/tools/`, each a `program` that exercises a narrow piece of the code base. They are not meant to be production drivers. They are built by `drivers/tools/CMakeLists.txt` alongside the main executables. Examples: `ClimReader` (reads and echoes climate forcing via `ClimReadMod`), `ClimTransformer` (reshapes climate arrays), `GridReader` (reads the grid NetCDF via `ncdio_pio`), `HFileTest` (smoke-tests `HistFileMod`), `NamelistTest` (namelist parsing with `etimer`), `PlantManagementReader` / `SoilManagementReader` (management-file parsing), `SoilWarmReadTest` (reads `read_soil_warming_Tref`), `etimerTest` (walks the time manager), `restartTest` (restart round-trip), and `EcoATSTest` / `EcoATSTest_old` (ATS coupling smoke test). See [`reference/module_inventory.md`](../reference/module_inventory.md) for the one-line description of each.

## High-level subsystem map

The `f90src/` tree is organized by subsystem. Each folder has its own `CMakeLists.txt` and is added in the top-level `f90src/CMakeLists.txt`. A driver program depends only on the subset of `f90src/` subdirectories it actually needs (the standalone driver uses essentially all of them).

| Subsystem folder | Role | Dedicated wiki section |
|---|---|---|
| `f90src/Main/` | `InitModules` orchestration and `DestructEcoSIM` teardown | [core](../core/index.md) |
| `f90src/Ecosim_mods/` | Historical ecosys-derived initialization routines: `StartsMod`, `StartqMod`, `StarteMod`, `InitAllocMod` | [core](../core/index.md) |
| `f90src/Mesh/` | Horizontal/vertical grid setup (`GridConsts`, `GridMod`) | [core](../core/index.md) |
| `f90src/Modelconfig/` | Run-level config and namelist state (`EcoSIMCtrlMod`, `EcoSIMConfig`), solver parameters (`EcoSIMSolverPar`), tracer and element IDs (`TracerIDMod`, `ElmIDMod`) | [core](../core/index.md) |
| `f90src/Modelpars/` | Scientific parameters, not run-time options: plant, microbial, solute, tracer transport, and shared parameter data | [core](../core/index.md) |
| `f90src/Ecosim_datatype/` | 33 files of `allocatable, target` field modules that hold the per-column, per-layer, per-PFT state (see [data types](../data_types/index.md)) | [data_types](../data_types/index.md) |
| `f90src/APIs/` | Thin wrappers (`PlantMod`, `MicBGCAPI`, `GeochemAPI`, `PlantAPI*`, `SurfPhysAPI`) exposed to `EcoSIMAPI` and external drivers | [apis](../apis/index.md) |
| `f90src/Plant_bgc/` | Plant biogeochemistry: photosynthesis, stomata, uptake, allocation, phenology, litterfall, disturbance effects | [plant_bgc](../plant_bgc/index.md) |
| `f90src/Microbial_bgc/` | Soil microbial dynamics, split between `Box_Micmodel/` (single-layer box) and `Layers_Micmodel/` (layered profile) | [microbial_bgc](../microbial_bgc/index.md) |
| `f90src/Geochem/` | Aqueous chemistry, equilibrium solvers, split between `Box_chem/` and `Layers_chem/` | [geochem](../geochem/index.md) |
| `f90src/HydroTherm/` | Water/energy physics, split into `CanopyPhys/`, `SnowPhys/`, `SoilPhys/`, `SurfPhys/`, and shared `PhysData/` | [hydrotherm](../hydrotherm/index.md) |
| `f90src/Transport/` | Non-salt and salt advection/diffusion/dissolution (`Nonsalt/`, `Salt/`) | [transport](../transport/index.md) |
| `f90src/Balances/` | Column-scale redistribution and balance accounting (`RedistMod`, `RunoffBalMod`, `ErosionBalMod`, `LateralTranspMod`, `SoilLayerDynMod`, `TillageMixMod`) | [balances_and_disturbances](../balances_and_disturbances/index.md) |
| `f90src/Disturbances/` | Fire (`FireMod`), erosion (`ErosionMod`), fertilizer (`FertilizerMod`), soil disturbance (`SoilDisturbMod`), plant disturbance (`PlantDisturbMod`), soil/atmospheric warming (`EcosysWarmingMod`) | [balances_and_disturbances](../balances_and_disturbances/index.md) |
| `f90src/IOutils/` | Namelist reading, climate/management reading, restart, history file writing | [io_and_forcing](../io_and_forcing/index.md) |
| `f90src/Modelforc/` | In-simulation forcing orchestration (`hour1`, `day`, `PrepHourlyWeather`, annual accumulators) | [io_and_forcing](../io_and_forcing/index.md) |
| `f90src/ModelDiags/` | `BalancesMod` (begin/end balance checks), `HydrologyDiagMod` (water-table depth), `SoilDiagsMod` (gas pressure) | [diagnostics](../diagnostics/index.md) |
| `f90src/DebugTools/` | `DebugToolMod` print/trace helpers | [diagnostics](../diagnostics/index.md) |
| `f90src/Utils/` | Kind/constant modules, string/file/time/logging utilities, NetCDF PIO shim (`ncdio_pio`), regression harness (`TestMod`), infinity/NaN checks (`shr_infnan_mod`) | cross-cutting, see [module inventory](../reference/module_inventory.md) |
| `f90src/Minimath/` | Small numerical utilities: `LinearAlgebraMod`, `MiniFuncMod`, `MiniMathMod` | cross-cutting, see [module inventory](../reference/module_inventory.md) |
| `f90src/Prescribed_pheno/` | `PrescribePhenolMod` — prescribed phenology mode (`GetRootProfile`, `SetCanopyProfile`) | [plant_bgc](../plant_bgc/index.md) |
| `f90src/APIData/` | `PlantAPIData` — data types exchanged through the plant API | [apis](../apis/index.md) |
| `f90src/ATSUtils/` | ATS coupling layer (see above) | [drivers](../drivers/index.md) |

## Build system

EcoSIM uses CMake as the primary build system. The top-level script `build_EcoSIM.sh` is a convenience wrapper that configures the CMake tree, builds the third-party libraries under `3rd-partylibs/`, and then configures and builds EcoSIM (`README.md:11-19`). The resulting executable lives at `./build/bin/ecosim.f90.x` (`README.md:21`).

Key CMake entry points:

- `CMakeLists.txt` (top level). Declares the `ecosim` project (`CMakeLists.txt:96`), enables C/C++/Fortran (`CMakeLists.txt:90-92`), handles APPLE SDK detection (`CMakeLists.txt:11-25`), adds `3rd-partylibs/` when `ATS_ECOSIM` is not set (`CMakeLists.txt:234`), and finally descends into `f90src/` and `drivers/` (`CMakeLists.txt:273-274`).
- `f90src/CMakeLists.txt` and per-subsystem `f90src/<subsystem>/CMakeLists.txt` files enumerate the F90 sources compiled into the library.
- `drivers/CMakeLists.txt` and per-driver `drivers/<driver>/CMakeLists.txt` files link each executable against the library.
- `cmake/Modules/` and `cmake/Templates/` hold helper modules (`set_up_platform`, `set_up_compilers`) and `ecosim.cmake.in`, the CMake package config consumers import.

Optional build flags documented in `README.md:29-43`: `debug`, `mpi`, `shared`, `verbose`, `sanitize`, `regression_test`, `precision`, plus compiler overrides `CC`, `CXX`, `FC`. A `--help` flag to `build_EcoSIM.sh` lists everything.

For reproducible environments, `docker/ubuntu-compiler.dockerfile` provides a compiled Ubuntu image, and the repository is known to be CI-tested with GCC via `.github/workflow/ecosim-ci.yml` (`README.md:23`).

## What comes next

- [`overview/source_tree.md`](source_tree.md) — the directory-by-directory tour with file counts.
- [`reference/module_inventory.md`](../reference/module_inventory.md) — every F90 module, one line each, for quick lookup.
- Subsystem sections linked from the [top-level index](../index.md).
