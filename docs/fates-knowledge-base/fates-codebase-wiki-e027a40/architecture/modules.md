---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# Module Organization

## Purpose and Scope

This document describes how FATES source code is organized into directories and modules at commit `e027a40` (tag `sci.1.91.1_api.43.1.0`). It covers the top-level directory layout, the module naming conventions, the role of the core modules, and the basic dependency structure. For linked-list data structures, see [Linked List Data Structures](linked_lists.md). For the PARTEH extensibility framework, see [PARTEH Extensibility Framework](parteh_framework.md).

## Directory Structure

At the top level of the FATES source tree, the directories present at commit `e027a40` are:

| Directory | Role |
| --- | --- |
| `main/` | Primary interface to host land models (HLMs), top-level entry points, daily orchestration, initialization, I/O, parameters, and type definitions |
| `biogeochem/` | Plant and ecosystem biogeochemistry: cohort and patch dynamics, physiology, allometry, litter, mortality, damage, canopy structure, soil BGC fluxes, land use change, and the `fates_cohort_type` / `fates_patch_type` definitions themselves |
| `biogeophys/` | Plant hydraulics, water-stress (Btran), photosynthesis, leaf biophysics, and flux accumulation |
| `radiation/` | Canopy radiative transfer (Norman scheme, two-stream solver, MLPE multi-layer two-stream) |
| `fire/` | SPITFIRE fire model (main driver, fire weather, fuels, prescribed fire, fire equations, and Nesterov index) |
| `parteh/` | Plant Allocation and Reactive Transport Extensible Hypotheses framework (generic base, carbon-only and CNP hypotheses, loss fluxes, parameters) |
| `parameter_files/` | JSON/CDL parameter files and parameter file tooling |
| `functional_unit_testing/` | Standalone unit tests exercising FATES physics without a full HLM |
| `testing/` | Newer FATES unit-test scaffolding (`run_functional_tests.py`, `run_unit_tests.py`, `framework/`, `tests/`, `templates/`) |
| `tools/` | Python utilities for parameter file manipulation (not Fortran modules) |

Two directories present in earlier FATES versions are no longer the locus of certain functionality. Canopy radiative transfer no longer lives in the legacy `biogeophys/EDSurfaceAlbedo` module from earlier tags — that module has been removed and replaced by the new `radiation/` directory (`FatesNormanRadMod.F90`, `FatesRadiationDriveMod.F90`, `FatesRadiationMemMod.F90`, `FatesTwoStreamUtilsMod.F90`, `TwoStreamMLPEMod.F90`). The legacy synchronized-parameters module under `main/` has also been removed and replaced by `main/JSONParameterUtilsMod.F90`. Sources: top-level listing of the FATES source tree at commit `e027a40`.

### Files currently in each source directory

- `main/`: `ChecksBalancesMod.F90`, `EDInitMod.F90`, `EDMainMod.F90`, `EDParamsMod.F90`, `EDPftvarcon.F90`, `EDTypesMod.F90`, `FatesConstantsMod.F90`, `FatesDispersalMod.F90`, `FatesGlobals.F90`, `FatesHistoryInterfaceMod.F90`, `FatesHistoryVariableType.F90`, `FatesHydraulicsMemMod.F90`, `FatesIODimensionsMod.F90`, `FatesIOVariableKindMod.F90`, `FatesIntegratorsMod.F90`, `FatesInterfaceMod.F90`, `FatesInterfaceTypesMod.F90`, `FatesInventoryInitMod.F90`, `FatesParameterDerivedMod.F90`, `FatesParametersInterface.F90`, `FatesRestartInterfaceMod.F90`, `FatesRestartVariableType.F90`, `FatesRunningMeanMod.F90`, `FatesSizeAgeTypeIndicesMod.F90`, `FatesUtilsMod.F90`, `JSONParameterUtilsMod.F90`.
- `biogeochem/`: `DamageMainMod.F90`, `EDCanopyStructureMod.F90`, `EDCohortDynamicsMod.F90`, `EDLoggingMortalityMod.F90`, `EDMortalityFunctionsMod.F90`, `EDPatchDynamicsMod.F90`, `EDPhysiologyMod.F90`, `FatesAllometryMod.F90`, `FatesCohortMod.F90`, `FatesLandUseChangeMod.F90`, `FatesLitterMod.F90`, `FatesPatchMod.F90`, `FatesSoilBGCFluxMod.F90`.
- `biogeophys/`: `EDAccumulateFluxesMod.F90`, `EDBtranMod.F90`, `FatesBstressMod.F90`, `FatesHydroWTFMod.F90`, `FatesLeafBiophysParamsMod.F90`, `FatesPlantHydraulicsMod.F90`, `FatesPlantRespPhotosynthMod.F90`, `LeafBiophysicsMod.F90`.
- `radiation/`: `FatesNormanRadMod.F90`, `FatesRadiationDriveMod.F90`, `FatesRadiationMemMod.F90`, `FatesTwoStreamUtilsMod.F90`, `TwoStreamMLPEMod.F90`.
- `fire/`: `FatesFuelClassesMod.F90`, `FatesFuelMod.F90`, `FatesRxFireMod.F90`, `SFEquationsMod.F90`, `SFFireWeatherMod.F90`, `SFMainMod.F90`, `SFNesterovMod.F90`, `SFParamsMod.F90`.
- `parteh/`: `PRTAllometricCNPMod.F90`, `PRTAllometricCarbonMod.F90`, `PRTGenericMod.F90`, `PRTLossFluxesMod.F90`, `PRTParametersMod.F90`, `PRTParamsFATESMod.F90`.

Note that `main/CMakeLists.txt` does not enumerate the entire `main/` module set; it only lists the subset compiled for unit tests. The authoritative inventory is the directory listing itself.

## Module Naming Conventions

FATES uses consistent prefix conventions to indicate a module's domain:

| Prefix | Purpose | Examples |
| --- | --- | --- |
| `Fates*Mod` | Core FATES-specific modules (newer naming) | `FatesInterfaceMod`, `FatesAllometryMod`, `FatesCohortMod`, `FatesPatchMod`, `FatesHistoryInterfaceMod`, `FatesPlantHydraulicsMod`, `FatesNormanRadMod`, `FatesRadiationDriveMod`, `FatesLandUseChangeMod`, `FatesRxFireMod` |
| `ED*Mod` | Ecosystem Demography (legacy naming, still heavily used) | `EDPhysiologyMod`, `EDMainMod`, `EDCohortDynamicsMod`, `EDPatchDynamicsMod`, `EDCanopyStructureMod` |
| `PRT*Mod` | PARTEH allocation system | `PRTGenericMod`, `PRTAllometricCarbonMod`, `PRTAllometricCNPMod`, `PRTLossFluxesMod`, `PRTParametersMod` |
| `SF*Mod` | SPITFIRE fire model | `SFMainMod`, `SFParamsMod`, `SFEquationsMod`, `SFFireWeatherMod`, `SFNesterovMod` |
| `*TypesMod` | Type definitions, no procedures of note | `EDTypesMod`, `FatesInterfaceTypesMod` |
| `*ParamsMod` | Parameter storage and I/O | `EDParamsMod`, `PRTParametersMod`, `SFParamsMod`, `FatesLeafBiophysParamsMod` |

## Key Modules by Role

### Interface Module (`main/FatesInterfaceMod.F90`)

`FatesInterfaceMod` defines the public API that host land models call. Its public surface (declared at `main/FatesInterfaceMod.F90:178-192`) is `FatesInterfaceInit`, `set_fates_ctrlparms`, `SetFatesTime`, `SetFatesGlobalElements1`, `SetFatesGlobalElements2`, `allocate_bcin`, `allocate_bcout`, `allocate_bcpconst`, `set_bcpconst`, `zero_bcs`, `set_bcs`, `UpdateFatesRMeansTStep`, `InitTimeAveragingGlobals`, `DetermineGridCellNeighbors`. Key entities include:

- `fates_interface_type` at `main/FatesInterfaceMod.F90:138-172` — the root object (`nsites`, `sites(:)`, `bc_in(:)`, `bc_out(:)`, `bc_pconst`).
- `FatesInterfaceInit` at `main/FatesInterfaceMod.F90:199-210` — one-time interface initialization.
- `set_fates_ctrlparms` at `main/FatesInterfaceMod.F90:1489-2258` — accepts namelist control parameters from the HLM.
- `SetFatesGlobalElements1` (`:792-893`) and `SetFatesGlobalElements2` (`:897-1115`) — two-phase global element setup.
- `allocate_bcin` (`:443-619`) and `allocate_bcout` (`:623-759`) — per-site boundary-condition allocation.
- `allocate_bcpconst` (`:236-254`) and `set_bcpconst` (`:258-278`) — single-instance parameter-constant boundary condition.
- `FatesTransferParameters` (`:2675-2694`, private) — copies parameters from the JSON-parsed `pstruct` into typed singleton arrays. Called from `SetFatesGlobalElements1:841` after `JSONRead` populates `pstruct` at `:827`.

The legacy `FatesReadParameters` and `FatesReportParameters` subroutines have been removed at e027a40; parameter loading now goes through `JSONParameterUtilsMod` (see Parameter Management Architecture below).

### Type Definition Modules

`main/EDTypesMod.F90` declares `ed_site_type` at `:325-... `. The site type holds the `oldest_patch` / `youngest_patch` pointers at `:328-329`, along with site-level diagnostic and state arrays (see the file for the full field list).

`main/FatesInterfaceTypesMod.F90` declares the boundary-condition types used on the HLM interface:

- `bc_in_type` — inputs from the host model (radiation, soil properties, meteorology).
- `bc_out_type` — outputs to the host model (albedo, fluxes, canopy structure).
- `bc_pconst_type` — parameter constants passed to the host once at startup.

Global configuration flags such as `hlm_use_planthydro` and `hlm_parteh_mode` also live here (consulted by `biogeochem/FatesCohortMod.F90:23-25` and many other sites).

The `fates_patch_type` and `fates_cohort_type` definitions do NOT live in `EDTypesMod.F90`. They are declared in dedicated modules under `biogeochem/`:

- `biogeochem/FatesPatchMod.F90:64-271` (`fates_patch_type`)
- `biogeochem/FatesCohortMod.F90:61-301` (`fates_cohort_type`)

These modules carry the type declarations together with their type-bound procedures (patch TBPs at `biogeochem/FatesPatchMod.F90:250-269`; cohort TBPs at `biogeochem/FatesCohortMod.F90:287-299`). The patch TBP set has been substantially extended at e027a40 to include cohort-list maintenance (`CountCohorts`, `InsertCohort`, `SortCohorts`, `ValidateCohorts`), dynamic-array (re)allocation (`NanDynamics`, `ZeroDynamics`, `ReAllocateDynamics`), and canopy bookkeeping (`UpdateTreeGrassArea`, `UpdateLiveGrass`). The cohort gains `SumMortForHistory` (`biogeochem/FatesCohortMod.F90:296`) for history aggregation of mortality components.

### Physiology and Dynamics Modules

`biogeochem/EDPhysiologyMod.F90` is the central physiology orchestrator. Its public subroutines include `trim_canopy` (`:598`), `phenology` (`:900`), `phenology_leafonoff` (`:1534`), and `recruitment` (`:2467`), among others. It coordinates litter flux management and daily allocation calls.

`biogeochem/EDCohortDynamicsMod.F90` manages the cohort lifecycle. Its public subroutines include `create_cohort` (`:123-226`), `InitPRTObject` (`:230-279`), `terminate_cohorts` (`:283-410`), `terminate_cohort` (`:413-512`), and `fuse_cohorts` (`:648-1232`). The list-maintenance routines `sort_cohorts`, `insert_cohort`, and `count_cohorts` are no longer module-level subroutines here; they are now type-bound on `fates_patch_type` (see [Linked List Data Structures](linked_lists.md)).

`biogeochem/EDPatchDynamicsMod.F90` owns patch creation, fusion, and termination, and most disturbance mechanics, including `spawn_patches` at `:488-1708`. Many sites in this module dispatch to the new patch TBPs, e.g. `currentPatch%SortCohorts()` and `currentPatch%ValidateCohorts()` at `:1335-1336`, `:1395-1396`, `:1800-1801`, `:3094-3095`.

`main/EDMainMod.F90` holds the daily dynamics entry point `ed_ecosystem_dynamics` at `:148-332`, which the HLM calls once per dynamics timestep. This routine also calls `currentPatch%SortCohorts()` (`:272`) and `currentPatch%CountCohorts()` (`:877`).

### Allometry Module (`biogeochem/FatesAllometryMod.F90`)

`FatesAllometryMod` provides a library of allometric functions with consistent interfaces. Many functions return both a value and a derivative (for example `dhdd` for the height derivative with respect to diameter). The module supports multiple allometry modes via PFT parameters such as `allom_hmode` and `allom_amode`, and integrates with the damage module via the `crowndamage` argument.

### Radiation Modules (`radiation/`)

At e027a40, canopy radiative transfer is its own top-level directory. The active drivers are:

- `radiation/FatesRadiationDriveMod.F90:1-450` — top-level dispatcher, exposes `FatesNormalizedCanopyRadiation` and `FatesSunShadeFracs`. Internally calls `PatchNormanRadiation` from `FatesNormanRadMod` (`:44`).
- `radiation/FatesNormanRadMod.F90:1-987` — Norman radiative-transfer scheme.
- `radiation/FatesRadiationMemMod.F90` — radiation memory and constants (`num_swb`, `ivis`, `inir`, `ipar`, `norman_solver`, `twostr_solver`, `num_rad_stream_types`).
- `radiation/FatesTwoStreamUtilsMod.F90` — two-stream utilities (`FatesConstructRadElements`, `FatesPatchFSun`, `CheckPatchRadiationBalance`).
- `radiation/TwoStreamMLPEMod.F90` — multi-layer two-stream solver and the `twostream_type` derived type embedded in `fates_patch_type` (field `twostr` at `biogeochem/FatesPatchMod.F90:185`).

The `radiation/` modules are consumed widely (`use FatesRadiationMemMod` appears in `EDPatchDynamicsMod`, `FatesPatchMod`, `EDInitMod`, `EDPftvarcon`, `FatesHistoryInterfaceMod`; `use FatesNormanRadMod` is also imported in `main/FatesRestartInterfaceMod.F90:4126`).

## PARTEH (Plant Allocation) Module Structure

The PARTEH framework uses object-oriented polymorphism. The base class `prt_vartypes` is declared at `parteh/PRTGenericMod.F90:232-278`, and the two concrete hypothesis modules extend it:

- `parteh/PRTAllometricCarbonMod.F90:136-143` — `callom_prt_vartypes` extends `prt_vartypes`, overrides `DailyPRT` and `FastPRT`.
- `parteh/PRTAllometricCNPMod.F90:254-270` — `cnp_allom_prt_vartypes` extends `prt_vartypes`, overrides `DailyPRT`, `FastPRT`, and `GetNutrientTarget`, and adds CNP-specific procedures.

Module selection happens at cohort initialization through `InitPRTObject` in `biogeochem/EDCohortDynamicsMod.F90:230-279`, driven by the `hlm_parteh_mode` flag (selected via `select case` at `:253`). The active hypothesis also assigns a module-level singleton pointer `prt_global` (declared at `parteh/PRTGenericMod.F90:396`) to its own `prt_global_ac` / `prt_global_acnp` instance. See [PARTEH Extensibility Framework](parteh_framework.md) for the registration pattern and mass-balance bookkeeping.

## Parameter Management Architecture

Parameter management is distributed across several specialized modules:

| Module | Role |
| --- | --- |
| `main/EDParamsMod.F90` | Global scalar parameters (e.g., `nclmax = 3` at `:76`, `maxpft = 16` at `:91`, `nlevleaf`, `maxSWb`) |
| `main/EDPftvarcon.F90` | PFT-scale parameters, exposed as the singleton `EDPftvarcon_inst` at `main/EDPftvarcon.F90:291` |
| `parteh/PRTParametersMod.F90` | PARTEH-specific parameters, exposed as `prt_params` at `parteh/PRTParametersMod.F90:195` |
| `parteh/PRTParamsFATESMod.F90` | Binds PARTEH parameters to the FATES parameter file reader |
| `fire/SFParamsMod.F90` | SPITFIRE fire parameters |
| `biogeophys/FatesLeafBiophysParamsMod.F90` | Leaf biophysics parameters (factored out at e027a40) |
| `main/FatesParametersInterface.F90` | Generic read interface used by the HLM parameter reader |
| `main/JSONParameterUtilsMod.F90` | New at e027a40. Parses the JSON parameter file into a `params_type` data structure |

JSON-based parameter loading is coordinated from `main/FatesInterfaceMod.F90`. Inside `SetFatesGlobalElements1` (`:792-893`), the load sequence at `:825-841` is:

```fortran
call JSONSetInvalid(fates_check_param_set+10._r8)
call JSONSetLogInit(fates_log())
call JSONRead(paramfile,pstruct)
! ... optional dump of all parameters via JSONDumpParameter ...
call FatesTransferParameters()
```

`FatesTransferParameters` (`main/FatesInterfaceMod.F90:2675-2694`) is a thin wrapper that calls `TransferParamsGeneric`, `TransferParamsSpitFire`, `TransferParamsPRT`, `TransferParamsLeafBiophys`, and `TransferParamsPFT` to copy values from the generic `pstruct` into typed primitive arrays held by each parameter singleton. Once loaded, the parameter objects are effectively read-only for the remainder of the run. The legacy `FatesReadParameters` / `FatesReportParameters` pair has been removed.

## I/O Module Organization

### History Output System

History output is managed by `main/FatesHistoryInterfaceMod.F90` (module declared at line 1). It allocates and populates the multiplexed history dimensions used for size/PFT and canopy/leaf/PFT outputs, with supporting utilities in `FatesHistoryVariableType.F90`, `FatesIODimensionsMod.F90`, and `FatesIOVariableKindMod.F90`.

### Restart System

Restart I/O is managed by `main/FatesRestartInterfaceMod.F90`, with variable metadata helpers in `FatesRestartVariableType.F90`. Restart serializes the linked-list vegetation hierarchy (see [Linked List Data Structures](linked_lists.md)) to flat arrays and rebuilds it on read.

## Module Compilation and Linking

FATES is built as a library and linked into the host land model. The `main/CMakeLists.txt` file lists only the subset of sources compiled for FATES-internal unit tests. The full FATES build is driven by the host model's own build system, which compiles every `.F90` file under `main/`, `biogeochem/`, `biogeophys/`, `radiation/`, `fire/`, and `parteh/`.

Key linkage points with the host land model:

- `FatesInterfaceInit()` — called once during HLM initialization.
- `SetFatesGlobalElements1()` / `SetFatesGlobalElements2()` — two-phase setup of element lists and parameter reads.
- `ed_ecosystem_dynamics()` (`main/EDMainMod.F90:148`) — called once per dynamics step.
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
| `EDCohortDynamicsMod` | Cohort lifecycle (create, terminate, fuse) |
| `FatesPatchMod` | Patch type, cohort-list maintenance TBPs (`SortCohorts`, `InsertCohort`, etc.) |
| `PARTEH` modules | Plant allocation and reactive transport |
| `FatesAllometryMod` | Allometric relationships and size calculations |
| `FatesRadiationDriveMod` | Canopy radiative-transfer dispatch |
| `JSONParameterUtilsMod` | JSON parameter file parsing |

Sources: directory listings at commit `e027a40` for `main/`, `biogeochem/`, `biogeophys/`, `radiation/`, `fire/`, `parteh/`, and `testing/`; `main/FatesInterfaceMod.F90`; `main/EDMainMod.F90`; `main/JSONParameterUtilsMod.F90`; `biogeochem/FatesCohortMod.F90`; `biogeochem/FatesPatchMod.F90`; `biogeochem/EDCohortDynamicsMod.F90`; `biogeochem/EDPatchDynamicsMod.F90`; `biogeochem/EDPhysiologyMod.F90`; `parteh/PRTGenericMod.F90`; `parteh/PRTAllometricCarbonMod.F90`; `parteh/PRTAllometricCNPMod.F90`; `parteh/PRTParametersMod.F90`; `main/EDPftvarcon.F90`; `radiation/FatesRadiationDriveMod.F90`; `main/EDParamsMod.F90`.
