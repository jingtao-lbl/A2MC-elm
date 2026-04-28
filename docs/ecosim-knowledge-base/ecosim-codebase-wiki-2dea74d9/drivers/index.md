---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `drivers/` + `f90src/ATSUtils/`
**Last verified:** 2026-04-24
---

# Drivers Overview

EcoSIM ships several *drivers* under `drivers/` rather than a single monolithic
entry point. Each driver is a Fortran `program` (plus a small support module)
that links a different subset of the EcoSIM component libraries. The drivers
exist because different users want different things out of the same code base
(full column simulation, one-layer batch experiments, API coupling to an
external flow solver, simple regression harnesses).

The top-level CMake file pulls them all in via
`drivers/CMakeLists.txt:1-8`, which simply does
`add_subdirectory(...)` for each of: `ecosim`, `mockbatch`, `boxshared`,
`aquachem`, `boxsbgc`, `plantbgc`, `tools`, and `ATSEcoSIM`.

## Driver Summary

| Driver | Executable | Program file | Purpose |
|---|---|---|---|
| `drivers/ecosim/` | `ecosim.f90.x` | `ecosim.F90` | Full standalone EcoSIM column/landscape simulation (default for most users) |
| `drivers/ATSEcoSIM/` | `ATSEcoSIM_test.x` | `ATSEcoSIM_test.F90` | Standalone exerciser for the ATS coupling layer (runs the ATS-side surface-balance path without an actual ATS instance) |
| `drivers/aquachem/` | `aquachem.x` | `aquachem.F90` | Batch driver for the aqueous-phase chemical equilibria solver (with/without salt chemistry) |
| `drivers/boxsbgc/` | `boxsbgc.x` | `batchsbgc.F90` | Single-layer "box" soil BGC driver for microbial / BGC testing using NetCDF forcing |
| `drivers/boxshared/` | `boxshared` (library) | `ChemIDMod.F90` | Shared chemistry state-ID tables consumed by `aquachem` and `boxsbgc` |
| `drivers/mockbatch/` | `mock.x` | `mockdriver.F90` | Minimal "does-nothing" driver used as a scaffolding template for new batch drivers |
| `drivers/plantbgc/` | `plant.x` | `plantdriver.F90` | Single-plant skeleton driver (currently a copy of the mock template, reserved for future plant-only testing) |
| `drivers/tools/` | several `.x` exes | 12 `.F90` files | Utility executables for climate/grid/management I/O, restart, history, and timer testing |
| `f90src/ATSUtils/` | `ATSUtils_mods` (library) | 8 `.F90` files | Bridge library consumed by both `ATSEcoSIM_test.x` and the external ATS executable for state translation between ATS and EcoSIM |

## Full vs Box Drivers

There are two broad classes of driver in the tree.

1. **Full-column driver (`drivers/ecosim/`).** Reads the site namelist, sets up
   the full 2-D landscape mesh, runs surface energy / water, soil
   energy / water, microbial BGC, plant BGC, aqueous chemistry, transport, and
   erosion through the public `AdvanceModelOneYear` / `Run_EcoSIM_one_step`
   entry points in `EcoSIMAPI`. This is the driver that most end users build
   and run.

2. **Box drivers (`aquachem`, `boxsbgc`, `plantbgc`, `mockbatch`).** These all
   share the same "batch" scaffolding: read a namelist, build a variable list,
   allocate a flat `ystates0l` / `ystatesfl` state vector, initialize a history
   file, then loop over time calling one `Run*` routine per step and writing
   history. They are designed for unit-style testing of individual model
   components and use the same `bhistMod` / `ecosim_Time_Mod` / `fileUtil`
   infrastructure as the full driver but deliberately avoid the 2-D mesh and
   the full physics orchestration.

## Coupled Mode (ATS)

`drivers/ATSEcoSIM/` and `f90src/ATSUtils/` together implement the ATS-EcoSIM
coupling. `ATSEcoSIM_test.F90` is a *Fortran* test harness that fakes ATS
inputs and exercises the coupler in-process. In a true coupled run, the ATS
executable is the main program; it dlopens the EcoSIM library and calls the
C-bindable wrappers in `f90src/ATSUtils/ecosim_wrappers.F90`
(`EcoSIM_Setup`, `EcoSIM_Advance`, `EcoSIM_Shutdown`), which in turn delegate
to `ATSCPLMod`. The CMake option `ATS_ECOSIM` (see
`CMakeLists.txt:172-229`) toggles extra compiler flags (`-fPIC`, NetCDF paths,
etc.) needed to produce a shared library linkable into ATS, but the `ATSUtils`
library itself is always compiled.

## Where to Go Next

- Main standalone driver: [`ecosim_main.md`](ecosim_main.md) — `ecosim.F90`
  and `EcoSIMAPI.F90` internals.
- ATS coupling layer: [`ats_coupling.md`](ats_coupling.md) — `ATSCPLMod`,
  `ATSEcoSIMInitMod`, `ATSEcoSIMAdvanceMod`, shared data module, C interface,
  and the `ATS_ECOSIM` build flag.
- Aqueous chemistry batch driver: [`aquachem.md`](aquachem.md) — what it tests
  and how it differs from the full driver.
- Soil BGC batch driver: [`boxsbgc.md`](boxsbgc.md) — one-layer microbial
  biogeochemistry harness and its supporting modules.
- Mock, plant, and tools drivers: [`standalone_drivers.md`](standalone_drivers.md)
  — developer scaffolding plus the `tools/` utility executables.

## What is *not* in this scope

This document set covers only the *driver* layer — the programs, their
namelists, and their top-level call graphs. The physics subroutines they call
(HOUR1, WATSUB, MicrobeModel, PlantModel, SoluteModel, TranspNoSalt,
TranspSalt, EROSION, REDIST) are documented elsewhere in this wiki under
`hydrotherm/`, `microbial_bgc/`, `plant_bgc/`, `geochem/`, and `transport/`.
The FATES, ELM, and ATS internals are documented by those projects and are
not duplicated here — the coupling doc only covers the EcoSIM side of the
bridge.
