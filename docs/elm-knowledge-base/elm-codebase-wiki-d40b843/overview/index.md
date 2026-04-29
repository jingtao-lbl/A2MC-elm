---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Overview of the ELM Source Tree

## What ELM is

The **E3SM Land Model (ELM)** is the land-surface component of the U.S. Department of Energy's Energy Exascale Earth System Model (E3SM). In this working tree it lives under `components/elm/src/`. ELM is a direct descendant of CLM (the Community Land Model) and shares much of CLM's heritage, but it is now maintained as an independent code base with additions such as the `topounit` subgrid level, the PFLOTRAN reactive-transport interface, the FAN agricultural-nitrogen module, the LUH2 land-use change front end for FATES, the iac (integrated assessment component) coupling, optional MOAB unstructured-mesh support, and first-class support for the FATES vegetation demography library.

This wiki describes only what lives in `components/elm/src/`. It does **not** describe the atmosphere, ocean, sea ice, river, or glacier components of E3SM, nor the CIME case infrastructure, nor the FATES internals. ELM's interfaces to FATES, PFLOTRAN, and BeTR are described in terms of the ELM-side glue code only.

## Top-level calling sequence

ELM's run is driven from an external coupler. At commit `d40b8431` only the MCT-style entry point exists in `cpl/`; the historical separate ESMF entry-point file (`cpl/lnd_comp_esmf.F90`) has been removed, although the MCT module still imports `ESMF_Clock` from the ESMF Fortran types for clock handling (`cpl/lnd_comp_mct.F90:16,99,463`).

- **MCT entry**: `subroutine lnd_init_mct` (`cpl/lnd_comp_mct.F90:58`), `lnd_run_mct` (`cpl/lnd_comp_mct.F90:437`), `lnd_final_mct` (`cpl/lnd_comp_mct.F90:684`).

During initialization, the coupler calls `initialize1` (`main/elm_initializeMod.F90:62`), `initialize2` (`main/elm_initializeMod.F90:503`), and now also `initialize3` (`main/elm_initializeMod.F90:1146`). Phase one reads namelists, constructs the subgrid structure, and sets up decomposition. Phase two reads parameters, initializes FATES if enabled (`ELMFatesGlobals1`/`ELMFatesGlobals2`), and brings in restart/surface data. Phase three is a new third-stage initializer that wires up the multi-physics process (MPP) framework: it sets up VSFM (variably saturated flow) and the PETSc thermal model when those external models are enabled, calling `EMI_Init_EM(EM_ID_VSFM)` and `EMI_Init_EM(EM_ID_PTM)` as required (`main/elm_initializeMod.F90:1146-1226`). Phase three is a no-op when neither `use_vsfm` nor `use_petsc_thermal_model` is set.

Each timestep, the coupler calls `elm_drv` (`main/elm_driver.F90:207`). `elm_drv` owns the within-timestep physics calling sequence — canopy temperature and fluxes, soil temperature and hydrology, snow, lake, urban, biogeochemistry, dynamic subgrid updates, FATES coupling, balance checks, and history-tape updates. It parallelizes across "clumps" of gridcells using OpenMP (`main/elm_driver.F90:4-8`).

## The seven source subsystems

The 242 `.F90` files under `components/elm/src/` are partitioned into seven subdirectories. Each has a distinct role:

1. **`main/` (65 files)** — top-level driver, initialization/finalization, global control flags and constants, subgrid bookkeeping, history/restart I/O, and the glue modules for FATES, PFLOTRAN, BeTR, and iac coupling. This is where you find `elm_driver.F90`, `elm_initializeMod.F90`, `elm_varctl.F90`, `elm_varcon.F90`, `controlMod.F90`, `histFileMod.F90`, `restFileMod.F90`, the subgrid index/accessor modules, and the new `iac2lndMod.F90`/`lnd2iacMod.F90`/`ocn2lndType.F90` coupling-buffer modules.

2. **`biogeophys/` (54 files)** — energy balance, radiation, aerodynamic resistance, canopy and soil temperature, snow hydrology, soil hydrology (Richards-equation solver), lake thermodynamics, and urban energy/moisture. Key entry points include `CanopyTemperatureMod`, `SoilTemperatureMod`, `BareGroundFluxesMod`, `CanopyFluxesMod`, `SoilFluxesMod`, `CanopyHydrologyMod`, `SnowHydrologyMod`, `SoilHydrologyMod`, `SurfaceAlbedoMod`, and `SurfaceRadiationMod`.

3. **`biogeochem/` (74 files)** — carbon-nitrogen-phosphorus cycling, allocation, phenology, decomposition cascade, fire, crop model, methane (`CH4Mod`), VOC emissions, dust, dry deposition, satellite phenology, and erosion. The CN/CNP code has three state-update stages per cycle (non-mortality, mortality, harvest/prod) visible in the `*StateUpdate{1,2,3}Mod.F90` naming. BeTR variants live alongside for tracer-transport-coupled runs, and FATES-fire glue lives here as `FATESFire*Mod.F90`.

4. **`dyn_subgrid/` (18 files)** — transient land-cover machinery. Reads time-varying datasets (`dynpftFileMod`, `dyncropFileMod`, `dynHarvestMod`), adjusts subgrid weights (`dynLandunitAreaMod`, `dynSubgridDriverMod`), updates state variables to conserve mass and energy when column and patch weights change (`dynConsBiogeochemMod`, `dynConsBiogeophysMod`, `dynColumnStateUpdaterMod`, `dynPatchStateUpdaterMod`), and couples dynamic behavior into FATES (`dynEDMod`). New at `d40b8431`: `dynFATESLandUseChangeMod.F90` reads the LUH2 land-use harmonization dataset (108 transition variables, 12 state variables, 5 harvest variables) and feeds land-use change forcing into FATES.

5. **`data_types/` (13 files)** — pure derived-type definitions for the five subgrid levels. Each level has a `*Type.F90` for the structure and a `*DataType.F90` for allocation/initialization of its variable instances (e.g., `GridcellType.F90` and `GridcellDataType.F90`). This directory is the single source of truth for ELM's subgrid memory layout. New at `d40b8431`: `MOABGridType.F90` (756 lines, guarded by `#ifdef HAVE_MOAB`) provides Mesh-Oriented dAtaBase support for unstructured-mesh grids; it is built only when MOAB is enabled and sits outside the five-level subgrid hierarchy.

6. **`utils/` (13 files)** — time manager (`elm_time_manager.F90`), SPMD helpers (`spmdMod.F90`, `spmdGathScatMod.F90`), domain and orbital information, namelist helpers, and a handful of small math utilities (`quadraticMod.F90`, `SimpleMathMod.F90`, `AnnualFluxDribbler.F90`).

7. **`cpl/` (5 files)** — the coupler-facing interface. The MCT entry point, import/export of coupler fields (`lnd_import_export.F90`), topounit-aware disaggregation/downscaling of atmospheric forcing (`lnd_disagg_forc.F90`, `lnd_downscale_atm_forcing.F90`), and the field-index table (`elm_cpl_indices.F90`).

See [`source_tree.md`](source_tree.md) for a directory diagram and [`../reference/module_inventory.md`](../reference/module_inventory.md) for the full per-file table.

## The subgrid hierarchy

ELM represents heterogeneity on the land surface through a nested hierarchy of five subgrid levels:

```
gridcell
  └── topounit        (ELM-specific; see below)
        └── landunit  (e.g., natural vegetation, crop, urban TBD/HD/MD, lake, wetland, glacier, glacier_mec)
              └── column       (soil column with its own vertical discretization)
                    └── patch  (individual PFT or crop functional type)
```

The structure is declared and allocated in the `data_types/` subdirectory and instantiated in `main/elm_initializeMod.F90:383-405`:

```fortran
call grc_pp%Init (bounds_proc%begg_all, bounds_proc%endg_all)
call top_pp%Init (bounds_proc%begt_all, bounds_proc%endt_all) ! topology and physical properties
call top_as%Init (bounds_proc%begt_all, bounds_proc%endt_all) ! atmospheric state variables (forcings)
call top_af%Init (bounds_proc%begt_all, bounds_proc%endt_all) ! atmospheric flux variables (forcings)
call top_es%Init (bounds_proc%begt_all, bounds_proc%endt_all) ! energy state
call top_ws%Init (bounds_proc%begt_all, bounds_proc%endt_all) ! water state
call lun_pp%Init (bounds_proc%begl_all, bounds_proc%endl_all)
call col_pp%Init (bounds_proc%begc_all, bounds_proc%endc_all)
call veg_pp%Init (bounds_proc%begp_all, bounds_proc%endp_all)
```

`grc_pp` is the gridcell instance, `top_pp` the topounit instance, and so on. Each `*_pp` container holds the physical-properties side of its subgrid level; the state- and flux-side derived types are allocated in the `*DataType.F90` modules. The topounit level now also instantiates `top_as`/`top_af`/`top_es`/`top_ws` for atmospheric state, atmospheric flux, energy state, and water state respectively.

**The topounit level is ELM-specific.** `TopounitType.F90:1-7` describes topounits as sub-gridcell "topographic units" that sit between the gridcell and the landunit, so that atmospheric forcing and topographic modifiers can be applied below gridcell resolution without inflating the landunit count. The downscaling logic that splits gridcell forcing across topounits lives in `cpl/lnd_disagg_forc.F90` and `cpl/lnd_downscale_atm_forcing.F90`.

## Run-time control flags

ELM's run configuration is controlled through namelist variables declared in `main/elm_varctl.F90` and populated by `main/controlMod.F90`. Flags that select major run modes include:

- **`use_cn`** (`main/elm_varctl.F90:388`) — enable the CN (or CNP, depending on other flags) biogeochemistry pathway.
- **`use_lch4`** (`main/elm_varctl.F90:383`) — enable the `CH4Mod` methane module.
- **`use_fates`** (`main/elm_varctl.F90:227`) — use the FATES demographic vegetation library instead of the default CN phenology/allocation. When true, the ELM side uses `ELMFatesInterfaceMod` to drive the external FATES library; the FATES source itself is in `external_models/` and is not documented in this wiki.
- **`use_fates_sp`** (`main/elm_varctl.F90:248`) — FATES satellite-phenology mode.
- **`use_betr`** (`main/elm_varctl.F90:279`) — route nutrient and carbon tracers through the BeTR transport core (selects the `*BeTR*Mod.F90` variants under `biogeochem/`).
- **`use_pflotran`** (`main/elm_varctl.F90:501`) — couple ELM's subsurface thermal/hydrology/BGC to PFLOTRAN through `main/elm_interface_pflotranMod.F90`.
- **`use_fan`** (`main/elm_varctl.F90:409`) — activate the FAN (Flow of Agricultural Nitrogen) agricultural-nitrogen module (`biogeochem/FanMod.F90`).
- **`use_voc`** (`main/elm_varctl.F90:108`) — activate `VOCEmissionMod` for biogenic VOC emissions.
- **`use_erosion`** (`main/elm_varctl.F90:490`) — enable soil erosion and sediment/POC/PON/POP flux calculation (`biogeochem/ErosionMod.F90`, `biogeophys/SedYieldMod.F90`).

These flags are the primary axis along which the calling sequence in `elm_drv` branches. Most of them are loaded into the `elm_varctl` module as `public` logicals, then referenced throughout the rest of the code with `use elm_varctl, only : use_xxx`. Adding a new run mode almost always involves (a) declaring the flag in `elm_varctl.F90`, (b) wiring it through the namelist reader in `controlMod.F90`, and (c) branching in `elm_drv` and/or the affected physics modules.

## Parallelism and decomposition

ELM is parallelized two ways:

- **MPI (SPMD) across processes.** Each process owns a non-contiguous subset of gridcells. The decomposition is built in `main/decompInitMod.F90` and queried through `main/decompMod.F90`. SPMD gather/scatter primitives live in `utils/spmdGathScatMod.F90`.
- **OpenMP across "clumps" within a process.** The `main/elm_driver.F90` entry point loops over "clumps" of gridcells and allows OpenMP threading across that loop. The clumping is configured by the namelist variable `clump_pproc` (number of clumps per process) and queried via `get_proc_clumps` / `get_clump_bounds` in `main/decompMod.F90`. The header comment on `elm_driver` spells this out (`main/elm_driver.F90:4-8`).

History and restart I/O are **not** assumed thread-safe, so memory used for I/O is held in process-wide vectors that are pushed to and pulled from tape writers at clump boundaries.

## History and restart I/O

Output (history) and checkpoint (restart) are handled by `main/histFileMod.F90` and `main/restFileMod.F90`:

- `histFileMod.F90` defines the tape system. Multiple tapes are supported via the `hist_*` namelist arrays (`hist_nhtfrq`, `hist_mfilt`, `hist_fincl*`, `hist_fexcl*`) read by `main/controlMod.F90`.
- `restFileMod.F90` reads/writes the restart stream through the `restFile_write` and `restFile_filename` entry points that `elm_drv` calls at the end of each tick when a restart is due.
- GPU-specific buffers for history tapes are kept in `main/histGPUMod.F90`.
- The subgrid structure itself (i.e., which columns/patches exist) is written by `main/subgridRestMod.F90` so the restart can be rebuilt on a different decomposition.

## Optional engines

### FATES (vegetation demography)

When `use_fates` is true, the default CN phenology/allocation/vegetation-structure chain in `biogeochem/` is replaced by calls into the FATES library via `main/elmfates_interfaceMod.F90`. As of `d40b8431`, the historical wrapper module `main/elmfates_paraminterfaceMod.F90` no longer exists — its parameter-loading responsibilities have been folded into `elmfates_interfaceMod.F90` itself, which exposes `ELMFatesGlobals1` (`main/elmfates_interfaceMod.F90:318`) and `ELMFatesGlobals2` (`main/elmfates_interfaceMod.F90:407`) as the global FATES-init entry points. The interface module's head comment states that *all* connections between the two models must go through that file alone, and that FATES memory structures are not visible to the rest of ELM (`main/elmfates_interfaceMod.F90:1-15`). Dynamic subgrid updates relevant to FATES flow through `dyn_subgrid/dynEDMod.F90`, and LUH2-driven land-use change is delivered through `dyn_subgrid/dynFATESLandUseChangeMod.F90`. FATES-fire glue lives in `biogeochem/FATESFire*Mod.F90`.

### PFLOTRAN (reactive transport)

When `use_pflotran` is true, ELM uses `main/elm_interface_pflotranMod.F90` together with the `elm_interface_*Type.F90` coupling-buffer types to exchange thermal, hydrological, and BGC state with PFLOTRAN. The coupling is restricted to the interface modules; the rest of ELM is unaware of PFLOTRAN.

### BeTR (biogeochemistry transport engine)

When `use_betr` is true, the CN/CNP code paths switch to the BeTR-suffixed variants under `biogeochem/` (for example, `CNAllocationBetrMod.F90`, `CNPhenologyBeTRMod.F90`, `CNNStateUpdate1BeTRMod.F90`, `CNNStateUpdate2BeTRMod.F90`, `CNNStateUpdate3BeTRMod.F90`, `CNGapMortalityBeTRMod.F90`). These replace the corresponding default modules so that nutrient transport runs through BeTR's generic tracer framework.

### FAN (Flow of Agricultural Nitrogen)

When `use_fan` is true, `biogeochem/FanMod.F90` implements the FANv2 parameterizations and `biogeochem/FanUpdateMod.F90` interfaces the FAN module with ELM's nitrogen dynamics. Forcing comes in through `main/fanStreamMod.F90` (manure-nitrogen deposition).

### VSFM and PETSc thermal model (third-phase init)

When `use_vsfm` (variably saturated flow model) or `use_petsc_thermal_model` is true, the third-phase initializer `initialize3` (`main/elm_initializeMod.F90:1146`) wires those external models in through the External Model Interface (`EMI_Init_EM(EM_ID_VSFM)`, `EMI_Init_EM(EM_ID_PTM)`). Otherwise `initialize3` simply sets up the multi-physics process bookkeeping and returns. Lateral subsurface connectivity for VSFM is built through `utils/domainLateralMod.F90` (PETSc-based).

### iac (integrated assessment component)

The new `main/iac2lndMod.F90` and `main/lnd2iacMod.F90` modules define `iac2lnd_type` and `lnd2iac_type` derived types for exchanging per-PFT fields (PFT fractions in, heterotrophic respiration / NPP / PFT weight out) with an integrated assessment component on the ELM grid. These are passive plumbing types — coupler activation is controlled outside this directory.

## Where to go next

- **[`source_tree.md`](source_tree.md)** — directory map with per-subdir descriptions.
- **[`../reference/module_inventory.md`](../reference/module_inventory.md)** — one-line description of every `.F90` module.
- **Subsystem pages** (to be added): `core/index.md`, `biogeophys/index.md`, `biogeochem/index.md`, `dyn_subgrid/index.md`.
