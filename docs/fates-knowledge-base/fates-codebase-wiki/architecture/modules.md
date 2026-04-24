---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

# Module Organization

## Purpose and Scope

This document describes how FATES source code is organized into directories and modules at commit `e85d997`. It covers the top-level directory layout, the module naming conventions, the role of the core modules, and the basic dependency structure. For linked-list data structures, see [Linked List Data Structures](linked_lists.md). For the PARTEH extensibility framework, see [PARTEH Extensibility Framework](parteh_framework.md).

## Directory Structure

At the top level of the FATES source tree, the directories present at commit `e85d997` are:

| Directory | Role |
| --- | --- |
| `main/` | Primary interface to host land models (HLMs), top-level entry points, daily orchestration, initialization, I/O, parameters, and type definitions |
| `biogeochem/` | Plant and ecosystem biogeochemistry: cohort and patch dynamics, physiology, allometry, litter, mortality, damage, canopy structure, soil BGC fluxes, and the `fates_cohort_type` / `fates_patch_type` definitions themselves |
| `biogeophys/` | Canopy radiation and albedo, plant hydraulics, water-stress (Btran), photosynthesis, and flux accumulation |
| `fire/` | SPITFIRE fire model (main driver and fire-specific parameters) |
| `parteh/` | Plant Allocation and Reactive Transport Extensible Hypotheses framework (generic base, carbon-only and CNP hypotheses, loss fluxes, parameters) |
| `parameter_files/` | CDL/NetCDF parameter files and parameter file tooling |
| `functional_unit_testing/` | Standalone unit tests exercising FATES physics without a full HLM |
| `tools/` | Python utilities for parameter file manipulation (not Fortran modules) |

There is no `radiation/` directory — canopy radiative transfer lives in `biogeophys/EDSurfaceAlbedoMod.F90`. There is no `functional_unit/` directory — the closest match is `functional_unit_testing/`, which holds unit tests, and PFT parameter storage is in `main/EDPftvarcon.F90`. Sources: top-level listing of the FATES source tree at commit `e85d997`.

### Files currently in each source directory

- `main/`: `ChecksBalancesMod.F90`, `EDInitMod.F90`, `EDMainMod.F90`, `EDParamsMod.F90`, `EDPftvarcon.F90`, `EDTypesMod.F90`, `FatesConstantsMod.F90`, `FatesDispersalMod.F90`, `FatesGlobals.F90`, `FatesHistoryInterfaceMod.F90`, `FatesHistoryVariableType.F90`, `FatesHydraulicsMemMod.F90`, `FatesIODimensionsMod.F90`, `FatesIOVariableKindMod.F90`, `FatesIntegratorsMod.F90`, `FatesInterfaceMod.F90`, `FatesInterfaceTypesMod.F90`, `FatesInventoryInitMod.F90`, `FatesParameterDerivedMod.F90`, `FatesParametersInterface.F90`, `FatesRestartInterfaceMod.F90`, `FatesRestartVariableType.F90`, `FatesRunningMeanMod.F90`, `FatesSizeAgeTypeIndicesMod.F90`, `FatesSynchronizedParamsMod.F90`, `FatesUtilsMod.F90`.
- `biogeochem/`: `DamageMainMod.F90`, `EDCanopyStructureMod.F90`, `EDCohortDynamicsMod.F90`, `EDLoggingMortalityMod.F90`, `EDMortalityFunctionsMod.F90`, `EDPatchDynamicsMod.F90`, `EDPhysiologyMod.F90`, `FatesAllometryMod.F90`, `FatesCohortMod.F90`, `FatesLitterMod.F90`, `FatesPatchMod.F90`, `FatesSoilBGCFluxMod.F90`.
- `biogeophys/`: `EDAccumulateFluxesMod.F90`, `EDBtranMod.F90`, `EDSurfaceAlbedoMod.F90`, `FatesBstressMod.F90`, `FatesHydroWTFMod.F90`, `FatesPlantHydraulicsMod.F90`, `FatesPlantRespPhotosynthMod.F90`.
- `fire/`: `SFMainMod.F90`, `SFParamsMod.F90`.
- `parteh/`: `PRTAllometricCNPMod.F90`, `PRTAllometricCarbonMod.F90`, `PRTGenericMod.F90`, `PRTLossFluxesMod.F90`, `PRTParametersMod.F90`, `PRTParamsFATESMod.F90`.

Note that `main/CMakeLists.txt` does not enumerate the entire `main/` module set; it only lists the subset compiled for unit tests. The authoritative inventory is the directory listing itself.

## Module Naming Conventions

FATES uses consistent prefix conventions to indicate a module's domain:

| Prefix | Purpose | Examples |
| --- | --- | --- |
| `Fates*Mod` | Core FATES-specific modules (newer naming) | `FatesInterfaceMod`, `FatesAllometryMod`, `FatesCohortMod`, `FatesPatchMod`, `FatesHistoryInterfaceMod`, `FatesPlantHydraulicsMod` |
| `ED*Mod` | Ecosystem Demography (legacy naming, still heavily used) | `EDPhysiologyMod`, `EDMainMod`, `EDCohortDynamicsMod`, `EDPatchDynamicsMod`, `EDCanopyStructureMod` |
| `PRT*Mod` | PARTEH allocation system | `PRTGenericMod`, `PRTAllometricCarbonMod`, `PRTAllometricCNPMod`, `PRTLossFluxesMod`, `PRTParametersMod` |
| `SF*Mod` | SPITFIRE fire model | `SFMainMod`, `SFParamsMod` |
| `*TypesMod` | Type definitions, no procedures of note | `EDTypesMod`, `FatesInterfaceTypesMod` |
| `*ParamsMod` | Parameter storage and I/O | `EDParamsMod`, `PRTParametersMod`, `SFParamsMod` |

## Key Modules by Role

### Interface Module (`main/FatesInterfaceMod.F90`)

`FatesInterfaceMod` defines the public API that host land models call. Its key public entities include:

- `fates_interface_type` at `main/FatesInterfaceMod.F90:125-159` — the root object (nsites, sites(:), bc_in(:), bc_out(:), bc_pconst).
- `FatesInterfaceInit` at `main/FatesInterfaceMod.F90:188` — one-time interface initialization.
- `SetFatesGlobalElements1` (`:737`) and `SetFatesGlobalElements2` (`:808`) — two-phase global element setup.
- `allocate_bcin` (`:412`) and `allocate_bcout` (`:569`) — per-site boundary-condition allocation.
- `FatesReadParameters` (`:2399`, private) — driver for parameter file reads.
- `FatesReportParameters` (`:1964`) — logs active parameter values after load.

### Type Definition Modules

`main/EDTypesMod.F90` declares `ed_site_type` at line 231. The site type holds the `oldest_patch` / `youngest_patch` pointers at lines 234-235, along with site-level diagnostic and state arrays (see the file for the full field list).

`main/FatesInterfaceTypesMod.F90` declares the boundary-condition types used on the HLM interface:

- `bc_in_type` — inputs from the host model (radiation, soil properties, meteorology).
- `bc_out_type` — outputs to the host model (albedo, fluxes, canopy structure).
- `bc_pconst_type` — parameter constants passed to the host once at startup.

Global configuration flags such as `hlm_use_planthydro` and `hlm_parteh_mode` also live here (consulted by `biogeochem/FatesCohortMod.F90:22-24` and many other sites).

Note that the `fates_patch_type` and `fates_cohort_type` definitions do NOT live in `EDTypesMod.F90`. They are declared in dedicated modules under `biogeochem/`:

- `biogeochem/FatesPatchMod.F90:35-41` (`fates_patch_type`)
- `biogeochem/FatesCohortMod.F90:60-64` (`fates_cohort_type`)

These modules carry the type declarations together with their type-bound procedures (patch TBPs at `biogeochem/FatesPatchMod.F90:222-230`; cohort TBPs at `biogeochem/FatesCohortMod.F90:275-284`).

### Physiology and Dynamics Modules

`biogeochem/EDPhysiologyMod.F90` is the central physiology orchestrator. Its public subroutines include `trim_canopy` (`:597`), `phenology` (`:909`), `phenology_leafonoff` (`:1529`), and `recruitment` (`:2440`), among others. It coordinates litter flux management and daily allocation calls.

`biogeochem/EDCohortDynamicsMod.F90` manages the cohort lifecycle. Its public subroutines include `create_cohort` (`:160`), `terminate_cohorts` (`:347`), `terminate_cohort` (`:464`), `fuse_cohorts` (`:694`), `InitPRTObject` (`:293`), `sort_cohorts` (`:1271`), `insert_cohort` (`:1322`), and `count_cohorts` (`:1433`).

`biogeochem/EDPatchDynamicsMod.F90` owns patch creation, fusion, and termination, and most disturbance mechanics, including `spawn_patches` at `:398`.

`main/EDMainMod.F90` holds the daily dynamics entry point `ed_ecosystem_dynamics` at `:141`, which the HLM calls once per dynamics timestep.

### Allometry Module (`biogeochem/FatesAllometryMod.F90`)

`FatesAllometryMod` provides a library of allometric functions with consistent interfaces. Many functions return both a value and a derivative (for example `dhdd` for the height derivative with respect to diameter). The module supports multiple allometry modes via PFT parameters such as `allom_hmode` and `allom_amode`, and integrates with the damage module via the `crowndamage` argument.

## PARTEH (Plant Allocation) Module Structure

The PARTEH framework uses object-oriented polymorphism. The base class `prt_vartypes` is declared in `parteh/PRTGenericMod.F90:233-277`, and the two concrete hypothesis modules extend it:

- `parteh/PRTAllometricCarbonMod.F90:136-143` — `callom_prt_vartypes` extends `prt_vartypes`, overrides `DailyPRT` and `FastPRT`.
- `parteh/PRTAllometricCNPMod.F90:250-266` — `cnp_allom_prt_vartypes` extends `prt_vartypes`, overrides `DailyPRT`, `FastPRT`, and `GetNutrientTarget`, and adds CNP-specific procedures.

Module selection happens at cohort initialization through `InitPRTObject` in `biogeochem/EDCohortDynamicsMod.F90:293`, driven by the `hlm_parteh_mode` flag. The active hypothesis also assigns a module-level singleton pointer `prt_global` (declared at `parteh/PRTGenericMod.F90:395`) to its own `prt_global_ac` / `prt_global_acnp` instance. See [PARTEH Extensibility Framework](parteh_framework.md) for the registration pattern and mass-balance bookkeeping.

## Parameter Management Architecture

Parameter management is distributed across several specialized modules:

| Module | Role |
| --- | --- |
| `main/EDParamsMod.F90` | Global scalar parameters (e.g., `nclmax`, `nlevleaf`, `maxpft`, `maxSWb`) |
| `main/EDPftvarcon.F90` | PFT-scale parameters, exposed as the singleton `EDPftvarcon_inst` (`main/EDPftvarcon.F90:290`) |
| `parteh/PRTParametersMod.F90` | PARTEH-specific parameters, exposed as `prt_params` (`parteh/PRTParametersMod.F90:188`) |
| `parteh/PRTParamsFATESMod.F90` | Binds PARTEH parameters to the FATES parameter file reader |
| `fire/SFParamsMod.F90` | SPITFIRE fire parameters |
| `main/FatesParametersInterface.F90` | Generic read interface used by the HLM parameter reader |

Two-phase parameter loading is coordinated from `main/FatesInterfaceMod.F90`. The private subroutine `FatesReadParameters` (`:2399-2428`) is invoked from `SetFatesGlobalElements1` (`:758`) and pulls parameters into each of the singleton containers. Once loaded, the parameter objects are effectively read-only for the remainder of the run; `FatesReportParameters` (`:1964`) logs the active values.

## I/O Module Organization

### History Output System

History output is managed by `main/FatesHistoryInterfaceMod.F90` (module declared at line 1). It allocates and populates the multiplexed history dimensions used for size/PFT and canopy/leaf/PFT outputs, with supporting utilities in `FatesHistoryVariableType.F90`, `FatesIODimensionsMod.F90`, and `FatesIOVariableKindMod.F90`.

### Restart System

Restart I/O is managed by `main/FatesRestartInterfaceMod.F90`, with variable metadata helpers in `FatesRestartVariableType.F90`. Restart serializes the linked-list vegetation hierarchy (see [Linked List Data Structures](linked_lists.md)) to flat arrays and rebuilds it on read.

## Module Compilation and Linking

FATES is built as a library and linked into the host land model. The `main/CMakeLists.txt` file lists only the subset of sources compiled for FATES-internal unit tests (`FatesGlobals.F90`, `EDTypesMod.F90`, `EDPftvarcon.F90`, `FatesConstantsMod.F90`, `FatesHydraulicsMemMod.F90`, `FatesParametersInterface.F90`, `FatesUtilsMod.F90`). The full FATES build is driven by the host model's own build system, which compiles every `.F90` file under `main/`, `biogeochem/`, `biogeophys/`, `fire/`, and `parteh/`.

Key linkage points with the host land model:

- `FatesInterfaceInit()` — called once during HLM initialization.
- `SetFatesGlobalElements1()` / `SetFatesGlobalElements2()` — two-phase setup of element lists and parameter reads.
- `ed_ecosystem_dynamics()` (`main/EDMainMod.F90:141`) — called once per dynamics step.
- Boundary condition exchange via `bc_in(:)` and `bc_out(:)` arrays on the `fates_interface_type`.

## Module Documentation Conventions

FATES modules follow consistent coding conventions:

- Module declaration followed by `use` statements (grouped by source module).
- `implicit none` followed by `private`, with explicit `public ::` declarations for each exported entity.
- A module-level `character(len=*), parameter :: sourcefile = __FILE__` string used in error-reporting macros.
- Subroutine headers with `!DESCRIPTION:`, `!ARGUMENTS:`, and `!LOCAL VARIABLES:` sections, matching the conventions used by ELM and CTSM.

## Summary of Key Modules by Importance

| Module | Primary Role |
| --- | --- |
| `EDPhysiologyMod` | Phenology, recruitment, litter production, canopy trimming |
| `EDPatchDynamicsMod` | Disturbance, patch creation / fusion / termination |
| `FatesHistoryInterfaceMod` | History output variable management |
| `FatesInterfaceMod` | Public API and host land model coupling |
| `FatesPlantHydraulicsMod` | Plant water transport and hydraulic failure |
| `EDMainMod` | Daily dynamics orchestration (`ed_ecosystem_dynamics`) |
| `EDCohortDynamicsMod` | Cohort lifecycle (create, terminate, fuse, sort) |
| `PARTEH` modules | Plant allocation and reactive transport |
| `FatesAllometryMod` | Allometric relationships and size calculations |

Sources: directory listings at commit `e85d997` for `main/`, `biogeochem/`, `biogeophys/`, `fire/`, and `parteh/`; `main/FatesInterfaceMod.F90`; `main/EDMainMod.F90`; `biogeochem/FatesCohortMod.F90`; `biogeochem/FatesPatchMod.F90`; `biogeochem/EDCohortDynamicsMod.F90`; `biogeochem/EDPatchDynamicsMod.F90`; `biogeochem/EDPhysiologyMod.F90`; `parteh/PRTGenericMod.F90`; `parteh/PRTAllometricCarbonMod.F90`; `parteh/PRTAllometricCNPMod.F90`; `parteh/PRTParametersMod.F90`; `main/EDPftvarcon.F90`.
