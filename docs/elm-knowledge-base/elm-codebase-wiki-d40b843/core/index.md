---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Core subsystem

The ELM "core" subsystem covers the modules that wire everything else together: entry from the CIME driver, process-wide initialization, the main physics/BGC/FATES driver loop, the in-memory instance of ELM state, history and restart I/O, subgrid hierarchy setup, and runtime control flags. Almost everything in this directory lives under three source trees:

- `main/` – initialization, driver, instance/inst modules, subgrid data structures, control flags, history, restart, time manager wrappers.
- `cpl/` – MCT/ESMF component shims, import/export to the coupler, atmospheric forcing disaggregation and downscaling.
- `utils/` – low-level utilities used across the model (decomposition, logging, netCDF I/O helpers).

The entry point from the CIME flux coupler is `cpl/lnd_comp_mct.F90`, which calls into `main/elm_initializeMod.F90` at start-up and `main/elm_driver.F90` each coupling interval. When FATES is enabled, the same driver calls the host-side FATES shim `main/elmfates_interfaceMod.F90`, which owns the `alm_fates` instance that holds every FATES site, boundary-condition buffer, and the fire-data factory result.

**Note on filename casing.** The host-side FATES interface lives at `main/elmfates_interfaceMod.F90` (lowercase `elmfates_interfaceMod`, **not** any CamelCase form of that filename). The Fortran module name itself is `ELMFatesInterfaceMod`, but the file path is lowercase.

**Note on parameter reading (FATES api.43 change).** At d40b8431 the legacy `main/elmfates_paraminterfaceMod.F90` and the routine `FatesReadPFTs()` are **removed**. FATES api.43 reads its own parameter file (NetCDF or JSON) end-to-end on the FATES side via `JSONParameterUtilsMod`/`FatesReadParameters`, dispatched from inside `SetFatesGlobalElements1` at `main/elmfates_interfaceMod.F90:397`. ELM hands FATES only the file path (`fates_paramfile`). See [`fates_interface.md`](fates_interface.md) and [`initialization.md`](initialization.md) for details.

## What this subsystem owns

| Responsibility | Primary module(s) |
|---|---|
| Coupler entry / time stepping shell | `cpl/lnd_comp_mct.F90` |
| Import/export of coupler fields | `cpl/lnd_import_export.F90`, `cpl/elm_cpl_indices.F90` |
| Atm forcing disaggregation & topographic downscaling | `cpl/lnd_disagg_forc.F90`, `cpl/lnd_downscale_atm_forcing.F90` |
| Three-stage initialization | `main/elm_initializeMod.F90` (stages `initialize1/2/3`) |
| Instance (state vector) allocation | `main/elm_instMod.F90`, `main/elm_instance.F90` |
| Main driver loop (physics, BGC, FATES dispatch) | `main/elm_driver.F90` |
| FATES host-side interface | `main/elmfates_interfaceMod.F90` |
| Finalization | `main/elm_finalizeMod.F90` |
| Subgrid hierarchy (gridcell → topounit → landunit → column → patch) | `data_types/GridcellType.F90`, `data_types/TopounitType.F90`, `data_types/LandunitType.F90`, `data_types/ColumnType.F90`, `data_types/VegetationType.F90`, `main/initSubgridMod.F90` |
| Filters for active/inactive subgrid elements | `main/filterMod.F90` |
| History output | `main/histFileMod.F90`, `main/histGPUMod.F90` |
| Restart I/O | `main/restFileMod.F90`, `main/subgridRestMod.F90` |
| Time manager, decomposition, control vars | `utils/elm_time_manager.F90`, `main/decompMod.F90`, `main/controlMod.F90`, `main/elm_varctl.F90` |
| Glacier (CISM) coupling | `main/glc2lndMod.F90`, `main/lnd2glcMod.F90`, `main/glcDiagnosticsMod.F90` |
| IAC (Integrated Assessment Coupling) | `main/iac2lndMod.F90`, `main/lnd2iacMod.F90` |
| Ocean → land one-way | `main/ocn2lndType.F90` |
| Atmosphere-side exchange types | `main/atm2lndMod.F90`, `main/atm2lndType.F90`, `main/lnd2atmMod.F90`, `main/lnd2atmType.F90` |
| Runtime parameter and PFT input | `main/readParamsMod.F90`, `main/pftvarcon.F90`, `main/paramUtilMod.F90` |
| Runtime control variables and namelist flags | `main/elm_varctl.F90`, `main/controlMod.F90` |

## Page map

| Page | Scope |
|---|---|
| [`driver_and_coupling.md`](driver_and_coupling.md) | How ELM enters from CIME: `lnd_init_mct`, `lnd_run_mct`, `lnd_final_mct`; the main physics loop `elm_drv`; the import/export surface (now with IAC and ocean channels) in `lnd_import_export.F90`. |
| [`initialization.md`](initialization.md) | Three-stage init: `initialize1` (namelist, grid, surface, FATES globals 1), `initialize2` (time manager, instances, FATES globals 2, restart read, FATES cold-start), `initialize3` (PETSc/MPP/VSFM). |
| [`subgrid_hierarchy.md`](subgrid_hierarchy.md) | Gridcell → topounit → landunit → column → patch data types, allocation order, index relationships, and the new column/vegetation flag fields. |
| [`subgrid_utilities.md`](subgrid_utilities.md) | `initGridCellsMod`, `initSubgridMod`, `subgridAveMod`, `subgridWeightsMod`, `reweightMod`, `filterMod`. |
| [`atmosphere_interface.md`](atmosphere_interface.md) | `atm2lndMod`, `lnd2atmMod`, `lnd_disagg_forc`, `lnd_downscale_atm_forcing`, plus the new `topographic_effects_on_radiation` entry. |
| [`glacier_interface.md`](glacier_interface.md) | `glc2lndMod`, `lnd2glcMod`, ice-sheet coupling fields and glc_mec landunits. |
| [`fates_interface.md`](fates_interface.md) | **Kougarok-critical.** The host-side FATES interface at FATES api.43: `alm_fates` instance, parameter file handoff, per-timestep call sequence, two new C-flux/stock wrappers, FATES fire factory. |
| [`namelist_and_control.md`](namelist_and_control.md) | `controlMod`, `elm_varctl`, FATES namelist (greatly expanded at api.43), and how runtime flags propagate. |
| [`history_and_restart.md`](history_and_restart.md) | `histFileMod`, `restFileMod`, `subgridRestMod`, history tape build, restart read/write pattern (FATES `restart` now takes three keyword arguments). |
| [`time_and_decomposition.md`](time_and_decomposition.md) | `elm_time_manager`, `decompMod`, `decompInitMod`, clump bounds, OpenMP strategy. (Unchanged at d40b843.) |

## High-level call flow

```
  CIME driver (not documented here)
        │
        ▼
  lnd_init_mct   ──► initialize1  ──► initialize2  ──► initialize3       (startup)
        │                │                │
        │                │                └─ FATES cold-start or restart read
        │                └─ instance allocation (incl. alm_fates%init), EcosystemDynInit, FATES globals 2
        └─ namelist/grid read, FATES globals 1 (with FATES-side parameter file read)
        
  lnd_run_mct (each coupling interval)
        │
        ├─ lnd_import (x2l → atm2lnd_vars, glc2lnd_vars, ocn2lnd_vars, iac2lnd_vars)
        │
        └─ while (not in sync with EClock):
              elm_drv(doalb, nextsw_cday, declinp1, declin, rstwr, nlend, rdate)
                 │
                 ├─ dynSubgrid_driver, decomp vertical profiles, balance begin
                 ├─ FATES fire data interpolation (if use_fates)
                 ├─ Canopy hydrology, surface radiation (FATES sunfrac path)
                 ├─ Canopy temperature, CanopyFluxes (→ FATES photosynthesis wrapper)
                 ├─ Soil temperature, hydrology, drainage
                 ├─ CN ecosystem dynamics OR FATES dynamics
                 │   └─ EcosystemDynLeaching → wrap_FatesAtmosphericCarbonFluxes,
                 │                              wrap_FatesCarbonStocks (NEW per-step)
                 ├─ Per-step FATES updates: WrapUpdateFatesRmean, wrap_update_hifrq_hist;
                 │   once per day: dynamics_driv
                 ├─ Balance checks, albedo update (wrap_canopy_radiation), history accumulate
                 └─ lnd2atm → lnd2atm_vars
           advance_timestep
        lnd_export (lnd2atm_vars, lnd2glc_vars, lnd2iac_vars → l2x)

  lnd_final_mct → elm_finalizeMod::final()
```

For the physics/BGC details, see the subsystem-specific pages under `biogeophys/`, `biogeochem/`, `hydrology/`, `soilbgc/`. For FATES the page to read is [`fates_interface.md`](fates_interface.md) because almost every FATES touch is routed through a single `alm_fates%*` procedure call.
