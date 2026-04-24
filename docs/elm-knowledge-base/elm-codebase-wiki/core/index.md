---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Core subsystem

The ELM "core" subsystem covers the modules that wire everything else together: entry from the CIME driver, process-wide initialization, the main physics/BGC/FATES driver loop, the in-memory instance of ELM state, history and restart I/O, subgrid hierarchy setup, and runtime control flags. Almost everything in this directory lives under three source trees:

- `main/` – initialization, driver, instance/inst modules, subgrid data structures, control flags, history, restart, time manager wrappers.
- `cpl/` – MCT/ESMF component shims, import/export to the coupler, atmospheric forcing disaggregation and downscaling.
- `utils/` – low-level utilities used across the model (decomposition, logging, netCDF I/O helpers).

The entry point from the CIME flux coupler is `cpl/lnd_comp_mct.F90`, which calls into `main/elm_initializeMod.F90` at start-up and `main/elm_driver.F90` each coupling interval. When FATES is enabled, the same driver calls the host-side FATES shim `main/elmfates_interfaceMod.F90`, which owns the `alm_fates` instance that holds every FATES site, boundary-condition buffer, and the fire-data factory result.

## What this subsystem owns

| Responsibility | Primary module(s) |
|---|---|
| Coupler entry / time stepping shell | `cpl/lnd_comp_mct.F90` |
| Import/export of coupler fields | `cpl/lnd_import_export.F90`, `cpl/elm_cpl_indices.F90` |
| Atm forcing disaggregation & topographic downscaling | `cpl/lnd_disagg_forc.F90`, `cpl/lnd_downscale_atm_forcing.F90` |
| Three-stage initialization | `main/elm_initializeMod.F90` (stages `initialize1/2/3`) |
| Instance (state vector) allocation | `main/elm_instMod.F90`, `main/elm_instance.F90` |
| Main driver loop (physics, BGC, FATES dispatch) | `main/elm_driver.F90` |
| FATES host-side interface | `main/elmfates_interfaceMod.F90`, `main/elmfates_paraminterfaceMod.F90` |
| Finalization | `main/elm_finalizeMod.F90` |
| Subgrid hierarchy (grid → topounit → landunit → column → patch) | `main/GridcellType.F90`, `main/TopounitType.F90`, `main/LandunitType.F90`, `main/ColumnType.F90`, `main/VegetationType.F90`, `main/subgridMod.F90`, `main/initSubgridMod.F90` |
| Filters for active/inactive subgrid elements | `main/filterMod.F90` |
| History output | `main/histFileMod.F90`, `main/histGPUMod.F90` |
| Restart I/O | `main/restFileMod.F90`, `main/subgridRestMod.F90` |
| Time manager, decomposition, control vars | `main/timeinfoMod.F90`, `main/decompMod.F90`, `main/controlMod.F90`, `main/elm_varctl.F90` |
| Glacier (CISM) coupling | `main/glc2lndMod.F90`, `main/lnd2glcMod.F90`, `main/glcDiagnosticsMod.F90` |
| Atmosphere-side exchange types | `main/atm2lndMod.F90`, `main/atm2lndType.F90`, `main/lnd2atmMod.F90`, `main/lnd2atmType.F90` |
| Runtime parameter and PFT input | `main/readParamsMod.F90`, `main/pftvarcon.F90`, `main/paramUtilMod.F90` |
| Runtime control variables and namelist flags | `main/elm_varctl.F90`, `main/controlMod.F90` |

## Page map

The core subsystem is documented across the following pages. This index only sketches the boundaries between them; detail lives in each target.

| Page | Scope |
|---|---|
| [`driver_and_coupling.md`](driver_and_coupling.md) | How ELM enters from CIME: `lnd_init_mct`, `lnd_run_mct`, `lnd_final_mct`; the main physics loop `elm_drv`; the import/export surface in `lnd_import_export.F90`. |
| [`initialization.md`](initialization.md) | Three-stage init: `initialize1` (namelist, grid, surface, FATES globals 1), `initialize2` (time manager, instances, FATES globals 2, restart read, FATES cold-start), `initialize3` (PETSc/MPP/VSFM subsystems). |
| `subgrid_hierarchy.md` | Grid → topounit → landunit → column → patch data types, allocation order, index relationships. *(produced by another agent)* |
| `subgrid_utilities.md` | `initGridCellsMod`, `initSubgridMod`, `subgridAveMod`, `subgridWeightsMod`, `reweightMod`, `filterMod`. *(produced by another agent)* |
| `atmosphere_interface.md` | `atm2lndMod`, `lnd2atmMod`, `lnd_disagg_forc`, `lnd_downscale_atm_forcing`, how forcings are disaggregated and downscaled inside a coupling interval. *(produced by another agent)* |
| `glacier_interface.md` | `glc2lndMod`, `lnd2glcMod`, ice-sheet coupling fields and glc_mec landunits. *(produced by another agent)* |
| [`fates_interface.md`](fates_interface.md) | **Kougarok-critical.** The host-side FATES interface: `alm_fates` instance, parameter file read, per-timestep call sequence from the driver, how ELM hands boundary conditions to FATES and consumes FATES outputs, and the FATES fire factory. |
| `namelist_and_control.md` | `controlMod`, `elm_varctl`, major namelist groups and how runtime flags propagate. *(produced by another agent)* |
| `history_and_restart.md` | `histFileMod`, `restFileMod`, `subgridRestMod`, history tape build, restart read/write pattern. *(produced by another agent)* |
| `time_and_decomposition.md` | `timeinfoMod`, `elm_time_manager` (in `utils/`), `decompMod`, `decompInitMod`, clump bounds, OpenMP strategy. *(produced by another agent)* |

## High-level call flow

```
  CIME driver (not documented here)
        │
        ▼
  lnd_init_mct   ──► initialize1  ──► initialize2  ──► initialize3       (startup)
        │                │                │
        │                │                └─ FATES cold-start or restart read
        │                └─ instance allocation, EcosystemDynInit, FATES globals 2
        └─ namelist/grid read, FATES globals 1, FATES parameter file
        
  lnd_run_mct (each coupling interval)
        │
        ├─ lnd_import (x2l coupler array → atm2lnd_vars, glc2lnd_vars)
        │
        └─ while (not in sync with EClock):
              elm_drv(doalb, nextsw_cday, declinp1, declin, rstwr, nlend, rdate)
                 │
                 ├─ dynSubgrid_driver, decomp vertical profiles, balance begin
                 ├─ FATES fire data interpolation (if use_fates)
                 ├─ Canopy hydrology, surface radiation (FATES sunfrac path)
                 ├─ Canopy temperature, CanopyFluxes (→ FATES photosynthesis wrapper)
                 ├─ Soil temperature, hydrology, drainage
                 ├─ CN ecosystem dynamics OR FATES dynamics (daily only)
                 ├─ Balance checks, albedo update, history accumulate
                 └─ lnd2atm → lnd2atm_vars
           advance_timestep
        lnd_export (lnd2atm_vars → l2x coupler array)

  lnd_final_mct → elm_finalizeMod::final()
```

For the physics/BGC details, see the subsystem-specific pages under `biogeophys/`, `biogeochem/`, `hydrology/`, `soilbgc/`. For FATES the page to read is [`fates_interface.md`](fates_interface.md) because almost everything FATES-related is routed through a single `alm_fates` procedure call from `elm_driver.F90`.
