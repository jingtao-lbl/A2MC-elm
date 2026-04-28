---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/` + `drivers/` (full repo)
**Last verified:** 2026-04-24
---

# EcoSIM Codebase Wiki

This wiki documents the EcoSIM biogeochemical model source tree, pinned to commit [`2dea74d9`](https://github.com/jinyun1tang/EcoSIM/commit/2dea74d992bb821269d0a755e8cb3074c6cc453e) (internal version `0.1.0`, see `CMakeLists.txt:6-9`). Every section is grounded in the actual source, and line-number citations refer to files under `f90src/` and `drivers/`.

EcoSIM is a biogeochemical modeling library spun off from the ecosys model (`README.md:3`). It offers three usage modes, all built from the same `f90src/` core library:

1. A standalone 1-D/multi-column Fortran executable (`drivers/ecosim/`).
2. An ATS-coupled library for subsurface reactive-transport integration (`drivers/ATSEcoSIM/` + `f90src/ATSUtils/`).
3. A family of specialized batch drivers that exercise individual subsystems in isolation (`drivers/aquachem/`, `drivers/boxsbgc/`, `drivers/mockbatch/`, `drivers/plantbgc/`).

## Navigation

| Section | Path | What it covers |
|---|---|---|
| **Overview** | [`overview/`](overview/index.md) | What EcoSIM is, how it runs, build system, high-level subsystem map |
| &nbsp;&nbsp;Source tree | [`overview/source_tree.md`](overview/source_tree.md) | Directory layout with file counts and one-liner purposes |
| **Reference** | [`reference/`](reference/index.md) | Authoritative lookup tables |
| &nbsp;&nbsp;Module inventory | [`reference/module_inventory.md`](reference/module_inventory.md) | Every F90 module under `f90src/` and `drivers/`, one line each |
| **Drivers** | [`drivers/`](drivers/index.md) | Executable entry points (standalone, ATS-coupled, batch harnesses) |
| **Core** | [`core/`](core/index.md) | Initialization, time stepping, grid/mesh, control flow (`f90src/Main`, `Ecosim_mods`, `Mesh`, `Modelconfig`, `Modelpars`) |
| **Data types** | [`data_types/`](data_types/index.md) | The `Ecosim_datatype/` allocatable-field modules (state + auxiliary arrays) |
| **APIs** | [`apis/`](apis/index.md) | The `f90src/APIs/` layer that wraps subsystems for drivers and coupling |
| **Plant BGC** | [`plant_bgc/`](plant_bgc/index.md) | Photosynthesis, stomata, allocation, root/canopy BGC, phenology, litterfall (`f90src/Plant_bgc/`) |
| **Microbial BGC** | [`microbial_bgc/`](microbial_bgc/index.md) | Heterotroph/autotroph dynamics, SOM turnover, layered soil microbial BGC (`f90src/Microbial_bgc/`) |
| **Geochem** | [`geochem/`](geochem/index.md) | Solute equilibria (pH-prescribed and full-salt), urea hydrolysis, fertilizer chemistry (`f90src/Geochem/`) |
| **HydroTherm** | [`hydrotherm/`](hydrotherm/index.md) | Soil water/heat (WATSUB), snow physics, surface-litter energy balance, canopy interception (`f90src/HydroTherm/`) |
| **Transport** | [`transport/`](transport/index.md) | Gas/solute transport, non-salt and salt paths (`f90src/Transport/`) |
| **Balances and disturbances** | [`balances_and_disturbances/`](balances_and_disturbances/index.md) | Redistribution, runoff/erosion balances, tillage mixing, fire, fertilizer, soil warming (`f90src/Balances/`, `f90src/Disturbances/`) |
| **I/O and forcing** | [`io_and_forcing/`](io_and_forcing/index.md) | Namelist, climate/management readers, restart, history output, weather preparation (`f90src/IOutils/`, `f90src/Modelforc/`) |
| **Diagnostics** | [`diagnostics/`](diagnostics/index.md) | Balance checks, hydrology and soil-gas diagnostics, debug print helpers (`f90src/ModelDiags/`, `f90src/DebugTools/`) |

## What this wiki is (and is not)

- **Is:** an overlay on the source tree at commit `2dea74d9`. Every technical claim cites a concrete file and line number that was verified at the time of writing (`Last verified: 2026-04-24`).
- **Is not:** a science manual. It does not reproduce the equations or describe the theoretical framework. For that, consult the published ecosys / EcoSIM literature and the developer notes in individual modules.
- **Is not:** a user guide. See `README.md` in the repo root for build/run instructions and the example cases under `examples/`.

## How to read citations

Citations appear as `(path/from/repo/root.F90:NNN)`. Paths are relative to the EcoSIM repository root (the directory containing `CMakeLists.txt`, `f90src/`, and `drivers/`). A line number NNN points at the specific declaration, subroutine header, or call site being referenced. When a range is needed, we write `file.F90:NNN-MMM`.

## Third-party libraries

Four third-party libraries are vendored as git submodules under `3rd-partylibs/` and built by the CMake top-level when `ATS_ECOSIM` is not set (`CMakeLists.txt:234`): `hdf5`, `netcdf-c`, `netcdf-fortran`, and `zlib`. This wiki does not document those libraries, only how EcoSIM uses them via `f90src/Utils/ncdio_pio.F90`, `f90src/IOutils/HistFileMod.F90`, and `f90src/IOutils/RestartMod.F90`.
