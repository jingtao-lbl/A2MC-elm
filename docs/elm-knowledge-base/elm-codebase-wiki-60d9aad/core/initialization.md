---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Initialization

ELM initialization is a three-stage pipeline driven from `cpl/lnd_comp_mct.F90::lnd_init_mct` (see [`driver_and_coupling.md`](driver_and_coupling.md)). Every stage lives in `main/elm_initializeMod.F90` and is wrapped by `call t_startf(...)` / `t_stopf(...)` timers so the cost of each block shows up in the `cam_timing` output.

| Stage | Source | Called from | Purpose |
|---|---|---|---|
| `initialize1` | `main/elm_initializeMod.F90:54` | `lnd_init_mct` (before `mct_aVect_init`) | Namelist, global grid, decomposition, surface data, FATES globals phase 1, initial subgrid allocation. |
| `initialize2` | `main/elm_initializeMod.F90:452` | `lnd_init_mct` (after gsMap/domain set) | Time manager, component instance allocation, FATES globals phase 2, restart read, FATES cold-start, deposition streams. |
| `initialize3` | `main/elm_initializeMod.F90:1074` | `lnd_init_mct` | MPP / PETSc bookkeeping for VSFM and petsc-thermal. |
| `elm_petsc_init` | `main/elm_initializeMod.F90:1157` | `initialize1` | Boot PETSc when any of VSFM / lateral connectivity / petsc-thermal is active. |

All three stages run unconditionally at startup (`nsrest == nsrStartup`). Restart / branch runs still run all three; the divergence is inside each stage, typically in how the time manager and component state are reloaded.

## Stage 1: `initialize1`

`initialize1` is where ELM learns the physical problem it is solving – the grid, the surface dataset, the land mask, and (for FATES runs) how many patches per column are needed. It does not yet read restart data or allocate component state instances.

Order of major calls (main/elm_initializeMod.F90:115–447):

1. **Run-control setup.**
   - `control_init()` – read the `elm_inparm` namelist (main/elm_initializeMod.F90:129). Lives in `main/controlMod.F90`.
   - `elm_varpar_init()`, `elm_varcon_init()`, `landunit_varcon_init()`, `ncd_pio_init()` – initialize constants and the parallel netCDF layer.
2. **FATES globals phase 1** (main/elm_initializeMod.F90:134–142). If `use_fates`, call `ELMFatesGlobals1()` (from `main/elmfates_interfaceMod.F90:283`) and then `update_pft_array_bounds()`. Phase 1 reads the FATES parameter file, determines how many per-column patches FATES will need, and overwrites `natpft_size` / `natpft_ub`. See [`fates_interface.md`](fates_interface.md) for the details.
3. **PETSc / soil-temp subsystems.** `elm_petsc_init()` (main/elm_initializeMod.F90:144), `init_soil_temperature()` (in `biogeophys/SoilTemperatureMod.F90`).
4. **Dynamic subgrid control.** `dynSubgridControl_init(NLFilename)` – reads the transient-land-use namelist block (`main/dynSubgridControlMod.F90`).
5. **Global land mask.** `surfrd_get_globmask(filename=fatmlndfrc, mask=amask, ni=ni, nj=nj)` reads the atmosphere/land fraction file (main/elm_initializeMod.F90:161). If `amask` is all zero, sets `noland = .true.` and returns immediately so `lnd_init_mct` can tell the coupler to disable land.
6. **Optional lateral connectivity** between gridcells (MPAS-style graph) via `surfrd_get_grid_conn` (main/elm_initializeMod.F90:175–183).
7. **Gridcell decomposition.** Dispatches on `domain_decomp_type`:
   - `"round_robin"` → `decompInit_lnd(ni, nj, amask)`
   - `"graph_partitioning"` → `decompInit_lnd_using_gp(...)`
   - `"simple"` → `decompInit_lnd_simple(...)`
   Source: `main/decompInitMod.F90`, called at main/elm_initializeMod.F90:189–201.
8. **Processor bounds (gridcell only)** via `get_proc_bounds(begg, endg)` (main/elm_initializeMod.F90:214). Remaining bounds are filled in after subgrid decomposition below.
9. **Domain read.** `surfrd_get_grid(begg, endg, ldomain, fatmlndfrc[, fglcmask])` populates `ldomain` (main/elm_initializeMod.F90:225–228). `domain_check(ldomain)` runs on masterproc. If `flndtopo` is non-blank, `surfrd_get_topo` pulls the topography raster. If `use_top_solar_rad` is on, `surfrd_get_topo_for_solar_rad(ldomain, fsurdat)` reads slope/aspect parameters.
10. **Topounit bookkeeping.** `topounit_varcon_init(begg, endg, fsurdat, ldomain)` (main/elm_initializeMod.F90:257).
11. **Urban input.** `UrbanInput(begg, endg, mode='initialize')` (main/elm_initializeMod.F90:265) – populates the urban parameter tables.
12. **Surface weight arrays.** Allocate `wt_lunit`, `urban_valid`, `wt_nat_patch`, `wt_cft`, `fert_cft`, `fert_p_cft`, `wt_glc_mec`/`topo_glc_mec` (if glacier-mec landunits are on), plus the topounit arrays `wt_tunit`, `elv_tunit`, `slp_tunit`, `asp_tunit`, `num_tunit_per_grd`, and irrigation / surface / ground fraction helpers. All allocated at main/elm_initializeMod.F90:269–290.
13. **Patch and soil-order tables.** `pftconrd()` reads the PFT physiological parameter file, `soilorder_conrd()` reads the soil-order table (main/elm_initializeMod.F90:295–296).
14. **FATES PFT parameter read** (main/elm_initializeMod.F90:302–304). When `use_fates`, `FatesReadPFTs()` (from `main/elmfates_paraminterfaceMod.F90:37`) opens `fates_paramfile` and `paramfile`, calls `EDPftvarcon_inst%Init()`, then registers and receives the parameter set into FATES. This must run before `surfrd_get_data` because the FATES PFT file dictates the number of natural PFTs.
15. **Surface dataset.** `surfrd_get_data(begg, endg, ldomain, fsurdat)` populates the subgrid weights (main/elm_initializeMod.F90:307).
16. **FATES globals phase 2** (main/elm_initializeMod.F90:309–317). Calls `ELMFatesGlobals2()` to push the full set of control flags into FATES and run `SetFatesGlobalElements2`. After this, FATES knows the element (C, N, P) shapes it will need.
17. **Subgrid decomposition.** `decompInit_clumps` / `decompInit_ghosts` give each MPI rank its thread-parallel clumps and ghost cells. Then `get_proc_bounds(bounds_proc)` pulls the full landunit/column/patch ranges.
18. **Allocate the subgrid types** on this proc (main/elm_initializeMod.F90:342–362):
    ```fortran
    call grc_pp%Init(bounds_proc%begg_all, bounds_proc%endg_all)
    call top_pp%Init(bounds_proc%begt_all, bounds_proc%endt_all)
    call top_as%Init(...);  call top_af%Init(...);  call top_es%Init(...)
    call lun_pp%Init(bounds_proc%begl_all, bounds_proc%endl_all)
    call col_pp%Init(bounds_proc%begc_all, bounds_proc%endc_all)
    call veg_pp%Init(bounds_proc%begp_all, bounds_proc%endp_all)
    ```
    If `has_topounit` is on, `surfrd_topounit_data(begg, endg, fsurdat)` fills topounit elevation/slope/aspect.
19. **EMI external-model registry.** `EMI_Determine_Active_EMs()` (main/elm_initializeMod.F90:368).
20. **Build hierarchy.** `initGridCells()` wires gridcells to their children (`main/initGridCellsMod.F90`).
21. **Finish decomposition.** `decompInit_gtlcp(ns, ni, nj[, ldomain%glcmask])` builds the segment maps for all levels of the hierarchy (main/elm_initializeMod.F90:383–388).
22. **Filters.** `allocFilters()` allocates the per-clump filter structures from `main/filterMod.F90` (main/elm_initializeMod.F90:393).
23. **Reweighting.** `reweight_wrapup` runs per clump to apply the initial weights.
24. **CH4 parameters.** If `use_lch4`, `CH4conrd()` from `main/CH4varcon.F90` (main/elm_initializeMod.F90:413).
25. **Free scratch arrays.** Deallocate `wt_cft`, `wt_glc_mec`, `wt_tunit`, etc. Keep `wt_lunit`, `wt_nat_patch`, `topo_glc_mec` for use in `initialize2`.
26. **Initial `glc_topo`.** Loop over columns and set `col_pp%glc_topo(c)` to zero for non-ice-mec columns and to the surface dataset value for ice-mec columns; will be overwritten by CISM during the run (main/elm_initializeMod.F90:428–446).

After `initialize1` returns, ELM knows the subgrid shape and has fully allocated the `*_pp` types, but no physical state (temperatures, water, carbon pools) is set yet.

## Stage 2: `initialize2`

`initialize2` is the big stage. It owns the time manager, component-state allocation, FATES boundary-condition allocation, restart read, and deposition streams. Key blocks (main/elm_initializeMod.F90:452–1071):

1. **Budget reset.** `WaterBudget_Reset('all')` and, if CN, `CNPBudget_Reset('all')` (main/elm_initializeMod.F90:551–556).
2. **Shared parameters.** `readSharedParameters()` reads the shared physconst / BGC parameter file (from `main/readParamsMod.F90`) (main/elm_initializeMod.F90:569).
3. **Time manager.** Two paths (main/elm_initializeMod.F90:574–582):
   - `nsrest == nsrStartup` → `timemgr_init()`.
   - Else (continue / branch) → `restFile_getfile` → `restFile_open` → `timemgr_restart_io(ncid, flag='read')` → `timemgr_restart`.
4. **FATES timestep handoff.** `ELMFatesTimesteps()` (main/elmfates_interfaceMod.F90:575) sets `hlm_stepsize` and calls `InitTimeAveragingGlobals()` so FATES's running-mean machinery knows the ELM step size (main/elm_initializeMod.F90:587–589).
5. **Daylength bootstrap.** Compute the solar declination for the current and previous step using `shr_orb_decl`, then `InitDaylength` so `prev_dayl` is populated for day-length-sensitive processes (main/elm_initializeMod.F90:595–615). Also fills `grc_pp%max_dayl` using the latitude and max declination.
6. **History field registration for CN-specific fields** (`DAYL`, `PREV_DAYL`) (main/elm_initializeMod.F90:621–628).
7. **Biogeophys instance allocation.** Two `hist_addfld*` calls register `SNO_Z` and `ZII`, then `elm_inst_biogeophys(bounds_proc)` (from `main/elm_instMod.F90`) allocates every biogeophysics state instance (`atm2lnd_vars`, `lnd2atm_vars`, `glc2lnd_vars`, `canopystate_vars`, `temperature_vars`, water/energy/flux vars, `photosyns_vars`, `surfalb_vars`, …) (main/elm_initializeMod.F90:640–651).
8. **BeTR subsystem.** Allocates `ep_betr` via `create_betr_simulation_elm()`. If `use_betr`, initializes online (main/elm_initializeMod.F90:653–662).
9. **SNICAR parameter tables.** `SnowOptics_init()` and `SnowAge_init()`.
10. **Private parameters.** If `use_cn .or. use_fates`, call `init_decomp_cascade_constants()`. Then `readPrivateParameters()` (main/elm_initializeMod.F90:672–676).
11. **Decomposition cascade.** For `use_cn .or. use_fates` and not active BeTR BGC: either `init_decompcascade_bgc(bounds_proc, cnstate_vars, soilstate_vars)` (CENTURY) or `init_decompcascade_cn(bounds_proc, cnstate_vars)` (CTC) (main/elm_initializeMod.F90:678–688).
12. **Biogeochem instance allocation + FATES instance.** `elm_inst_biogeochem(bounds_proc)` allocates CN/P state types and, when `use_fates` is true, calls `alm_fates%init(bounds_proc)` (`main/elm_instMod.F90:247`). This is where per-clump FATES sites, f2hmap, bc_in/bc_out buffers, and the fire-data method object are built. Comment in source: "FATES is instantiated in the following call" (main/elm_initializeMod.F90:690–691). See [`fates_interface.md`](fates_interface.md).
13. **Accumulator buffers** for `atm2lnd_vars`, `top_as`, `top_af`, `veg_es`, `canopystate_vars`, `crop_vars`, `cnstate_vars`, and (if `use_fates`) `alm_fates%InitAccBuffer` (main/elm_initializeMod.F90:702–720).
14. **Dynamic subgrid init.** `init_subgrid_weights_mod(bounds_proc)` then `dynSubgrid_init(bounds_proc, glc2lnd_vars, crop_vars)` (main/elm_initializeMod.F90:733–734).
15. **Ecosystem dynamics init.**
    - `use_cn .or. use_fates` → `EcosystemDynInit(bounds_proc, alm_fates)` (from `biogeochem/EcosystemDynMod.F90:79`). Internally it always calls `AllocationInit(bounds, elm_fates)`; then if **not** `use_fates` it also calls `PhenologyInit`, `FireInit`, C14 spike init, and (if active) `InitPhenoFluxLimiter` and `fanInit`. Under FATES, phenology and fire live on the FATES side.
    - Otherwise → `SatellitePhenologyInit(bounds_proc)` (prescribed-vegetation mode).
16. **FATES satellite phenology / Init2.** If `use_fates`:
    - If `use_fates_sp`, run `SatellitePhenologyInit` so FATES-SP has the LAI streams.
    - If `fates_spitfire_mode > scalar_lightning`, call `alm_fates%Init2(bounds_proc, NLFilename)`, which in turn calls `fates_fire_data_method%FireInit(bounds, NLFilename)` to attach the lightning/population-density streams (main/elm_initializeMod.F90:747–756).
17. **CN dry-dep SP initialization.** If CN is on and dry-dep is `DD_XLND`, also run `SatellitePhenologyInit` to get monthly LAI estimates (main/elm_initializeMod.F90:758–762).
18. **Restart history namelist.** If `nsrest == nsrContinue`, call `htapes_fieldlist()` so history tapes read the stored namelist rather than the new one.
19. **Restart or initial-conditions read.** Three paths (main/elm_initializeMod.F90:780–823):
    - **Cold start** (`nsrest=startup, finidat==' ', finidat_interp_source==' '`) – nothing is read; state is left at its default cold-start values.
    - **Restart from file** (`finidat /= ' '`) – `getfil(finidat, fnamer, 0)`, then `restFile_read(bounds_proc, fnamer, atm2lnd_vars, aerosol_vars, canopystate_vars, cnstate_vars, ch4_vars, energyflux_vars, frictionvel_vars, lakestate_vars, photosyns_vars, soilhydrology_vars, soilstate_vars, solarabs_vars, surfalb_vars, sedflux_vars, ep_betr, alm_fates, glc2lnd_vars, crop_vars)`. The `alm_fates` argument routes into `hlm_fates_interface_type%restart` (main/elmfates_interfaceMod.F90:1433) so FATES state is restored.
    - **Continue / branch** (`nsrest == nsrContinue .or. nsrBranch`) – same `restFile_read` call but from the checkpoint file.
20. **Interpolated initial conditions** (`finidat_interp_source`). If set, writes a template file via `restFile_write`, then `initInterp(filei, fileo, bounds_proc)` to interpolate the old file onto the new grid, then `restFile_read` the interpolated result back (main/elm_initializeMod.F90:829–871).
21. **Reweight wrapup** per clump using the ice-sheet mask.
22. **Nitrogen / phosphorus deposition streams.** `ndep_init`, `ndep_interp`; `pdep_init`, `pdep_interp`. FAN ammonia stream (`use_fan`) if enabled (main/elm_initializeMod.F90:888–910).
23. **History tape build.** `hist_htapes_build()` unless this is a continue run (which reads the list from the restart file) (main/elm_initializeMod.F90:922–924).
24. **Accumulator-variable init.** `atm2lnd_vars%initAccVars`, `top_as/top_af/veg_es/canopystate_vars%InitAccVars`, crop, FATES (`alm_fates%initAccVars`), CN state.
25. **Monthly vegetation read.** If dry-dep XLND is on or `use_fates_sp`, read the monthly LAI stream via `readAnnualVegetation` / `interpMonthlyVeg` so the first SP call has valid data (main/elm_initializeMod.F90:953–964).
26. **Initial `lnd2atm`.** For `nsrest == nsrStartup`, `lnd2atm_minimal(bounds_proc, surfalb_vars, energyflux_vars, lnd2atm_vars)` sets the initial export state (main/elm_initializeMod.F90:970–974).
27. **Initial `lnd2glc`.** For glacier-mec runs, fill `lnd2glc_vars` for the first coupling interval.
28. **Deallocate `wt_nat_patch`.** It was needed through `initialize2` but not afterwards (main/elm_initializeMod.F90:1001).
29. **FATES cold-start.** If `use_fates .and. .not. is_restart() .and. finidat == ' ' .and. nsrest /= nsrBranch`, call `alm_fates%init_coldstart(canopystate_vars, soilstate_vars, frictionvel_vars)` (main/elm_initializeMod.F90:1007–1021). This is the FATES-side bootstrap: `init_site_vars`, `zero_site`, `set_site_properties`, optional hydraulic-sites cold-start, `init_patches`, `ed_update_site`, and `FluxIntoLitterPools` for each FATES site. If `use_fates_sp`, `SatellitePhenology` is run first so `leaf_area_profile` has LAI to work with.
30. **`topo_glc_mec` deallocation** (main/elm_initializeMod.F90:1033).
31. **elm interface / PFLOTRAN init.** If `use_elm_interface`, `elm_interface_data%Init(bounds_proc)` and, if `use_pflotran`, `elm_pf_interface_init(bounds_proc)` (main/elm_initializeMod.F90:1038–1044).
32. **End-of-init log message** (main/elm_initializeMod.F90:1053–1066).

## Stage 3: `initialize3`

`initialize3` (main/elm_initializeMod.F90:1074–1154) is a thin wrapper that gives the multi-physics framework (`components/elm/src/utils/mpp`) its view of the ELM decomposition:

1. Decide `restart_vsfm` based on `nsrest` / `finidat`.
2. `mpp_varpar_init(nlevsoi, nlevgrnd, nlevsno, max_patch_per_col)` (main/elm_initializeMod.F90:1121) – fix the MPP layer's vertical dimensions.
3. `mpp_varcon_init_landunit(istsoil, istcrop, istice, istice_mec, istdlak, istwet, max_lunit)` and `mpp_varcon_init_column(...)` translate ELM's landunit/column type codes into MPP enums.
4. `mpp_varctl_init_vsfm(use_vsfm, ..., lateral_connectivity, restart_vsfm, vsfm_satfunc_type, vsfm_lateral_model_type)` – sets VSFM runtime options.
5. `mpp_varctl_init_petsc_thermal(use_petsc_thermal_model)`.
6. `mpp_bounds_init_proc_bounds(bounds_proc%begg, …)` and `mpp_bounds_init_clump(get_proc_clumps())` give MPP the bounds arrays.
7. **External model attach.** If `use_vsfm`, `EMI_Init_EM(EM_ID_VSFM)`. If `use_petsc_thermal_model`, `EMI_Init_EM(EM_ID_PTM)`. Both come from `main/ExternalModelInterfaceMod.F90`.

If neither VSFM nor PETSc-thermal nor lateral connectivity is active, `elm_petsc_init` returns without calling `PetscInitialize` (main/elm_initializeMod.F90:1181–1183), so stage 3 is effectively a no-op for most Kougarok-style point runs.

## Start type branching

`lnd_init_mct` translates the coupler `starttype` into `nsrest` before calling `initialize1` (`cpl/lnd_comp_mct.F90:265–273`):

| `starttype` | `nsrest` | Restart path | Initial-conditions source |
|---|---|---|---|
| `seq_infodata_start_type_start` | `nsrStartup = 0` | Cold start or interpolation from `finidat_interp_source` | `finidat`, or cold values if blank |
| `seq_infodata_start_type_cont` | `nsrContinue = 1` | Standard continue | Restart pointer file written by previous run |
| `seq_infodata_start_type_brnch` | `nsrBranch = 2` | Branch off another case | Explicit `finidat` from another case, but time manager continues |

`initialize2` switches on `nsrest` at several points:

- **Time manager.** Startup calls `timemgr_init()`. Continue/branch opens the restart file with `restFile_open(flag='read')`, runs `timemgr_restart_io(ncid, flag='read')`, and finishes with `timemgr_restart()` (main/elm_initializeMod.F90:574–582).
- **History namelist.** `htapes_fieldlist()` is only called when `nsrest == nsrContinue` to pull the previous namelist (main/elm_initializeMod.F90:922–924).
- **State read.** Startup with a non-blank `finidat`, and both continue and branch, call `restFile_read(bounds_proc, fnamer, ...)`.
- **Interpolated IC.** Only reachable when `nsrest == nsrStartup .and. finidat_interp_source /= ' '`. Produces a new template via `restFile_write`, interpolates with `initInterp`, then reads the result back with `restFile_read`.
- **FATES cold-start.** Only reachable when `use_fates .and. .not. is_restart() .and. finidat == ' ' .and. nsrest /= nsrBranch`. Any non-cold path (continue, branch, `finidat` set, interp source set) relies on `restFile_read` to rehydrate FATES state.

## Subsystems touched during init

The table below collects the subsystem-level init calls that `initialize1` / `initialize2` dispatch into, so that you can find the right module without re-reading the long sequence.

| Subsystem | Init call(s) | Stage | Source |
|---|---|---|---|
| Namelist / run control | `control_init`, `control_setNL`, `elm_varctl_set`, `dynSubgridControl_init` | 1 | `main/controlMod.F90`, `main/elm_varctl.F90`, `dyn_subgrid/dynSubgridControlMod.F90` |
| Time manager | `set_timemgr_init` (init) then `timemgr_init` / `timemgr_restart` | 1/2 | `utils/elm_time_manager.F90` |
| Decomposition | `decompInit_lnd*`, `decompInit_clumps`, `decompInit_ghosts`, `decompInit_gtlcp` | 1 | `main/decompInitMod.F90`, `main/decompMod.F90` |
| Surface data | `surfrd_get_globmask`, `surfrd_get_grid`, `surfrd_get_topo`, `surfrd_get_data` | 1 | `main/surfrdMod.F90`, `main/surfrdUtilsMod.F90` |
| Subgrid types | `grc_pp%Init`, `top_pp%Init`, `lun_pp%Init`, `col_pp%Init`, `veg_pp%Init`, `initGridCells` | 1 | `main/GridcellType.F90`, `main/LandunitType.F90`, `main/ColumnType.F90`, `main/VegetationType.F90`, `main/initGridCellsMod.F90` |
| Filters | `allocFilters` | 1 | `main/filterMod.F90` |
| Biogeophysics instances | `elm_inst_biogeophys` (allocates `atm2lnd_vars`, `lnd2atm_vars`, `glc2lnd_vars`, `canopystate_vars`, `temperature_vars`, ...) | 2 | `main/elm_instMod.F90` |
| Biogeochem instances (CN / FATES) | `elm_inst_biogeochem` (allocates `cnstate_vars`, `carbonstate_vars`, ..., and `alm_fates`) | 2 | `main/elm_instMod.F90` |
| Decomposition cascade | `init_decomp_cascade_constants`, `init_decompcascade_bgc` / `_cn` | 2 | `biogeochem/DecompCascadeBGCMod.F90`, `biogeochem/DecompCascadeCNMod.F90` |
| Parameters | `pftconrd`, `soilorder_conrd`, `readSharedParameters`, `readPrivateParameters`, `FatesReadPFTs` | 1/2 | `main/pftvarcon.F90`, `main/readParamsMod.F90`, `main/elmfates_paraminterfaceMod.F90` |
| FATES | `ELMFatesGlobals1`, `ELMFatesGlobals2`, `ELMFatesTimesteps`, `alm_fates%init`, `alm_fates%InitAccBuffer`, `alm_fates%Init2`, `alm_fates%init_coldstart`, `alm_fates%initAccVars` | 1/2 | `main/elmfates_interfaceMod.F90` |
| Hydrology | `init_hydrology` (called from `elm_inst_biogeophys`) | 2 | `main/init_hydrology.F90` |
| SNICAR | `SnowOptics_init`, `SnowAge_init` | 2 | `biogeophys/SnowSnicarMod.F90` |
| Deposition streams | `ndep_init`, `ndep_interp`, `pdep_init`, `pdep_interp`, `fanstream_init` | 2 | `main/ndepStreamMod.F90`, `main/pdepStreamMod.F90`, `main/fanStreamMod.F90` |
| History tapes | `hist_htapes_build`, `hist_addfld1d/2d`, accumulator registration | 2 | `main/histFileMod.F90` |
| Restart | `restFile_getfile`, `restFile_open`, `restFile_read`, `restFile_write` | 2 | `main/restFileMod.F90`, `main/subgridRestMod.F90` |
| Ecosystem dynamics | `EcosystemDynInit` (→ `AllocationInit`, `PhenologyInit`, `FireInit`, `C14_init_BombSpike`, `fanInit`) | 2 | `biogeochem/EcosystemDynMod.F90` |
| Dynamic subgrid | `init_subgrid_weights_mod`, `dynSubgrid_init` | 2 | `main/subgridWeightsMod.F90`, `dyn_subgrid/dynSubgridDriverMod.F90` |
| MPP / PETSc | `mpp_varpar_init`, `mpp_varcon_init_*`, `mpp_varctl_init_*`, `mpp_bounds_init_*`, `EMI_Init_EM` | 3 | `utils/mpp/...`, `main/ExternalModelInterfaceMod.F90` |

## Key initialization invariants

- The order of `FatesReadPFTs` (stage 1) → subgrid decomposition → `alm_fates%init` (stage 2) → `alm_fates%init_coldstart` (stage 2, cold-start only) cannot be reordered. FATES needs its PFT table to size the patches, then a decomposed HLM to know which columns are FATES sites, then cold-start/restart state before the first `dynamics_driv` call.
- `readSharedParameters` runs in stage 2 (after stage 1's `control_init`) because it needs the namelist-driven switches to decide which BGC fields to allocate.
- The restart read in stage 2 always passes `alm_fates` so FATES restart is atomic with ELM restart – FATES cannot be restarted independently of the host.
- CN and FATES share the `EcosystemDynInit` / `EcosystemDyn*Leaching*` scaffolding, but FATES replaces CN's phenology, allocation, and fire with its own per-site state. `EcosystemDynInit` explicitly early-returns after `AllocationInit` when `use_fates` is true.
- `initialize3` is not FATES-aware. Nothing in PETSc/VSFM/MPP interacts with FATES.
- `ELMFatesGlobals1` must run **before** `update_pft_array_bounds`, because phase 1 is the call that assigns `natpft_size = fates_maxPatchesPerSite` and therefore determines how many patches per column will be allocated.
- `surfrd_get_data` must run **after** `FatesReadPFTs` (stage 1) because the FATES PFT file can change `natpft_size`, which `surfrd_get_data` uses when building `wt_nat_patch`.
- `init_subgrid_weights_mod` and `dynSubgrid_init` must run **after** `elm_inst_biogeophys` / `elm_inst_biogeochem` because they write into the newly allocated `grc_pp`, `lun_pp`, `col_pp`, `veg_pp` instances.
- The restart read must run **before** `alm_fates%init_coldstart`, so that `init_coldstart` is gated behind `.not. is_restart() .and. finidat == ' '`.

## Related pages

- [`driver_and_coupling.md`](driver_and_coupling.md) – caller context (`lnd_init_mct`) and the `elm_drv` loop that runs after init completes.
- [`fates_interface.md`](fates_interface.md) – what `ELMFatesGlobals1`, `ELMFatesGlobals2`, `FatesReadPFTs`, `alm_fates%init`, `alm_fates%init_coldstart`, and `alm_fates%Init2` do in detail.
- `namelist_and_control.md` – `control_init`, `elm_varctl` flags, and which namelist groups each stage reads.
