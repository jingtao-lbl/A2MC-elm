---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Initialization

ELM initialization is a three-stage pipeline driven from `cpl/lnd_comp_mct.F90::lnd_init_mct` (see [`driver_and_coupling.md`](driver_and_coupling.md)). Every stage lives in `main/elm_initializeMod.F90` (1286 lines) and is wrapped by `t_startf`/`t_stopf` timers.

| Stage | Source | Called from | Purpose |
|---|---|---|---|
| `initialize1` | `main/elm_initializeMod.F90:62` | `lnd_init_mct` (cpl/lnd_comp_mct.F90:297) | Namelist, global grid, decomposition, surface data, FATES globals phase 1 & 2, initial subgrid allocation. |
| `initialize2` | `main/elm_initializeMod.F90:503` | `lnd_init_mct` (cpl/lnd_comp_mct.F90:354) | Time manager, component instance allocation, FATES `init`/`Init2`/`InitAccBuffer`/`initAccVars`/restart/cold-start, deposition streams. |
| `initialize3` | `main/elm_initializeMod.F90:1146` | `lnd_init_mct` (cpl/lnd_comp_mct.F90:355) | MPP / PETSc bookkeeping for VSFM and petsc-thermal. |
| `elm_petsc_init` | `main/elm_initializeMod.F90:1229` | `initialize1` (line 158) | Boot PETSc when any of VSFM / lateral connectivity / petsc-thermal is active. |

All three stages run unconditionally at startup (`nsrest == nsrStartup`). Restart/branch runs still run all three; the divergence is inside each stage.

**Major change at d40b843 vs 60d9aad:** the FATES init flow lost the `FatesReadPFTs` step. The old three-step `ELMFatesGlobals1 → FatesReadPFTs → ELMFatesGlobals2` collapses to two steps `ELMFatesGlobals1 → ELMFatesGlobals2` because FATES api.43 reads its own parameter file inside `SetFatesGlobalElements1`. `alm_fates%init` also gained a third argument `flandusepftdat` (the FATES land-use × PFT input file path).

## Stage 1: `initialize1`

`initialize1` is where ELM learns the physical problem it is solving — the grid, the surface dataset, the land mask, and (for FATES runs) how many patches per column are needed.

Order of major calls (`main/elm_initializeMod.F90:62-499`):

1. **Run-control setup.** `control_init()` reads the `elm_inparm` namelist (`:143`). Then `elm_varpar_init()`, `elm_varcon_init()`, `landunit_varcon_init()`, `ncd_pio_init()` (`:144-147`).
2. **FATES globals phase 1** (`:148-156`). If `use_fates`:
   ```fortran
   call ELMFatesGlobals1()
   call update_pft_array_bounds()
   ```
   `ELMFatesGlobals1` (`main/elmfates_interfaceMod.F90:318`) hands FATES the parameter file path via `SetFatesGlobalElements1(use_fates, natpft_size, 0, fates_paramfile)` (line 397). FATES reads its own parameter file there (NetCDF or JSON via the api.43 JSON loader) and returns `fates_maxPatchesPerSite`. ELM then sets `natpft_size = fates_maxPatchesPerSite` and `max_patch_per_col = max(natpft_size, numcft, maxpatch_urb)`. **Note:** there is no separate `FatesReadPFTs()` step at api.43 — the wiki at 60d9aad showed this as a third step but it has been removed.
3. **PETSc / soil-temp.** `elm_petsc_init()` (`:158`), `init_soil_temperature()` (`:159`).
4. **Print control settings, dynamic-subgrid namelist.** `control_print()`; `dynSubgridControl_init(NLFilename)` (`:163`).
5. **Global land mask.** `surfrd_get_globmask(filename=fatmlndfrc, mask=amask, ni=ni, nj=nj)` (`:175`). If `amask` is all zero, set `noland=.true.` and return.
6. **Optional lateral connectivity** (`:189-197`).
7. **Gridcell decomposition.** Dispatch on `domain_decomp_type` (`:212-229`):
   - `"round_robin"` → `decompInit_lnd(ni, nj, amask)`
   - `"graph_partitioning"` → `decompInit_lnd_using_gp(...)`
   - `"simple"` → `decompInit_lnd_simple(...)`
   - (When `HAVE_MOAB`, `"moab"` → `decompInit_moab(...)`)
8. **Processor bounds (gridcell only)** via `get_proc_bounds(begg, endg)` (`:242`).
9. **Domain read.** `surfrd_get_grid(...)` populates `ldomain` (`:252-256`). `domain_check(ldomain)` runs on masterproc. If `flndtopo` is non-blank, `surfrd_get_topo` pulls topography. **If `use_top_solar_rad` is on, `surfrd_get_topo_for_solar_rad(ldomain, fsurdat)` reads slope/aspect** (`:273-280`).
10. **Topounit bookkeeping.** `topounit_varcon_init(begg, endg, fsurdat, ldomain)` (`:285`). If `iac_present`, enforce `max_topounits == 1` (`:287-293`).
11. **Urban input.** `UrbanInput(begg, endg, mode='initialize')` (`:302`).
12. **Surface weight arrays.** Allocate `wt_lunit`, `urban_valid`, `wt_glc_mec`/`topo_glc_mec` (when glacier-mec is on), `wt_polygon`, `wt_tunit`, `elv_tunit`, `slp_tunit`, `asp_tunit`, `num_tunit_per_grd`, `firrig`, `f_surf`, `f_grd` (`:306-331`). **Note:** the `wt_nat_patch`, `wt_cft`, `fert_cft`, `fert_p_cft` allocations are deferred until **after** `pftconrd` (see next step).
13. **PFT physiology table.** `pftconrd()` (`:336`). If a user-defined PFT file is in use, `numpft`/`mxpft_nc` may be reset.
14. **Patch-table-dependent allocations.** `wt_nat_patch (begg:endg, 1:max_topounits, surfpft_lb:surfpft_ub)`, `wt_cft`, `fert_cft`, `fert_p_cft` (`:340-343`). This is reorganized vs 60d9aad: `pftconrd` happens **before** `wt_nat_patch` is allocated, so the patch table can finalize bounds first.
15. **Soil-order tables.** `soilorder_conrd()` (`:345`).
16. **Surface dataset.** `surfrd_get_data(begg, endg, ldomain, fsurdat)` (`:348`).
17. **FATES globals phase 2** (`:350-358`). `ELMFatesGlobals2()` pushes the full set of control flags into FATES via `set_fates_ctrlparms`, including the new physics-mode selectors (`fates_radiation_model`, `fates_stomatal_model`, etc.) and the LUH2/harvest/managed-fire flags. Then calls `SetFatesGlobalElements2(use_fates)` to size `fates_maxElementsPerPatch`, `num_elements`, `fates_maxElementsPerSite`. After this, FATES knows the element (C, N, P) shapes it will need.
18. **Subgrid decomposition.** `decompInit_clumps`/`decompInit_ghosts` give each MPI rank its thread-parallel clumps and ghost cells (`:365-371`). Then `get_proc_bounds(bounds_proc)` pulls the full landunit/column/patch ranges.
19. **Allocate the subgrid types** (`:383-404`):
    ```fortran
    call grc_pp%Init(bounds_proc%begg_all, bounds_proc%endg_all)
    call top_pp%Init(...);  call top_as%Init(...);  call top_af%Init(...);
    call top_es%Init(...);  call top_ws%Init(...)
    call lun_pp%Init(bounds_proc%begl_all, bounds_proc%endl_all)
    call col_pp%Init(bounds_proc%begc_all, bounds_proc%endc_all)
    call veg_pp%Init(bounds_proc%begp_all, bounds_proc%endp_all)
    ```
    If `has_topounit`, `surfrd_topounit_data(begg, endg, fsurdat)` fills topounit elevation/slope/aspect.
20. **EMI external-model registry.** `EMI_Determine_Active_EMs()` (`:410`).
21. **Build hierarchy.** `initGridCells()` (`:415`).
22. **Optional fineTOP solar parameters.** When `fsurdat /= " " .and. use_finetop_rad`, `surfrd_finetop_data(ldomain, fsurdat)` (`:417-423`).
23. **Finish decomposition.** `decompInit_gtlcp(ns, ni, nj[, ldomain%glcmask])` (`:433-437`).
24. **Filters.** `allocFilters()` (`:443`).
25. **Reweighting.** `reweight_wrapup` runs per clump.
26. **CH4 parameters.** If `use_lch4`, `CH4conrd()` (`:463-465`).
27. **Free scratch arrays.** Deallocate `wt_cft`, `wt_glc_mec`, `wt_tunit`, etc. Keep `wt_lunit`, `wt_nat_patch`, `topo_glc_mec` for use in `initialize2`.
28. **Initial `glc_topo`.** Loop over columns and set `col_pp%glc_topo(c)` for ice-mec columns (`:479-497`).

After `initialize1` returns, ELM knows the subgrid shape and has fully allocated the `*_pp` types, but no physical state is set yet.

## Stage 2: `initialize2`

`initialize2` (`main/elm_initializeMod.F90:503-1143`) owns the time manager, component-state allocation, FATES boundary-condition allocation, restart read, FATES cold-start, and deposition streams.

1. **Budget reset.** `WaterBudget_Reset('all')`; if CN, `CNPBudget_Reset('all')` (`:604-609`).
2. **Shared parameters.** `readSharedParameters()` (`:622`).
3. **Time manager.** Two paths (`:627-635`):
   - `nsrest == nsrStartup` → `timemgr_init()`.
   - Else (continue/branch) → `restFile_getfile` → `restFile_open(flag='read')` → `timemgr_restart_io(ncid, flag='read')` → `restFile_close` → `timemgr_restart`.
4. **FATES timestep handoff.** `ELMFatesTimesteps()` (`main/elmfates_interfaceMod.F90:813`, called from `:641`) sets `hlm_stepsize` and calls `InitTimeAveragingGlobals()`.
5. **Daylength bootstrap.** `shr_orb_decl` for current and previous step, then `InitDaylength` (`:648-659`). Compute `grc_pp%max_dayl` from latitude and max declination.
6. **History field registration for CN-specific fields** (`DAYL`, `PREV_DAYL`) (`:673-681`).
7. **Biogeophys instance allocation.** `hist_addfld2d`/`1d` for `SNO_Z`/`ZII`, then `elm_inst_biogeophys(bounds_proc)` (`:704`) allocates every biogeophysics state instance (`atm2lnd_vars`, `lnd2atm_vars`, `glc2lnd_vars`, `iac2lnd_vars`, `ocn2lnd_vars`, `canopystate_vars`, `temperature_vars`, water/energy/flux vars, `photosyns_vars`, `surfalb_vars`, …).
8. **BeTR subsystem.** Allocates `ep_betr` via `create_betr_simulation_elm()` (`:706-715`).
9. **SNICAR parameter tables.** `SnowOptics_init()`, `SnowAge_init()` (`:717-719`).
10. **Private parameters.** If `use_cn .or. use_fates`, `init_decomp_cascade_constants()`. Then `readPrivateParameters()` (`:725-729`).
11. **Decomposition cascade.** For `use_cn .or. use_fates` and not active BeTR BGC: either `init_decompcascade_bgc(...)` (CENTURY) or `init_decompcascade_cn(...)` (`:731-741`).
12. **Biogeochem instance allocation + FATES instance.** `elm_inst_biogeochem(bounds_proc)` (`:744`) allocates CN/P state types and, when `use_fates` is true, calls **`alm_fates%init(bounds_proc, flandusepftdat)`** (`main/elm_instMod.F90:257`). This is where per-clump FATES sites, `f2hmap`, `bc_in`/`bc_out` buffers, and the fire-data method object are built. The `flandusepftdat` argument is the FATES land-use × PFT input file path; consumed inside `init` only when `use_fates_fixed_biogeog .and. use_fates_luh`, but always required syntactically. See [`fates_interface.md`](fates_interface.md) for the full body.
13. **Accumulator buffers** for `atm2lnd_vars`, `top_as`, `top_af`, `veg_es`, `energyflux_vars`, `canopystate_vars`, `crop_vars` (if `crop_prog`), `cnstate_vars`, and (if `use_fates`) `alm_fates%InitAccBuffer(bounds_proc)` (`:755-779`).
14. **Dynamic subgrid init.** `init_subgrid_weights_mod(bounds_proc)` then `dynSubgrid_init(bounds_proc, glc2lnd_vars, crop_vars)` (`:788-789`).
15. **FATES LUH2 init (NEW at api.43).** If `use_fates_luh`, `dynFatesLandUseInit(bounds_proc, fluh_timeseries)` (`:793-795`). Sets up the LUH2 land-use stream.
16. **Ecosystem dynamics init.**
    - `use_cn .or. use_fates` → `EcosystemDynInit(bounds_proc, alm_fates)` (`biogeochem/EcosystemDynMod.F90:79`). Internally always calls `AllocationInit(bounds, elm_fates)`; if **not** `use_fates`, also `PhenologyInit`, `FireInit`, optional C14 spike init, optional `InitPhenoFluxLimiter`, optional `fanInit`. Under FATES, phenology and fire live on the FATES side.
    - Otherwise → `SatellitePhenologyInit(bounds_proc)`.
17. **FATES Init2.** If `use_fates`:
    - If `use_fates_sp`, `SatellitePhenologyInit(bounds_proc)` (so SP has the LAI streams).
    - If `fates_spitfire_mode > scalar_lightning`, **`alm_fates%Init2(bounds_proc, NLFilename)`** (`:814`) attaches the lightning/population-density streams via `fates_fire_data_method%FireInit(bounds, NLFilename)`.
18. **CN dry-dep SP initialization.** If CN is on and dry-dep is `DD_XLND`, also `SatellitePhenologyInit` (`:818-822`).
19. **Decomp pool pointers.** If `use_cn .or. use_fates`, `CreateLitterTransportList()` (`:824-827`).
20. **Restart history namelist.** If `nsrest == nsrContinue`, `htapes_fieldlist()` (`:837-839`).
21. **Restart or initial-conditions read.** Three paths (`:845-888`):
    - **Cold start** (`nsrest == nsrStartup, finidat == ' ', finidat_interp_source == ' '`) — nothing read; state is left at default cold-start values.
    - **Restart from file** (`finidat /= ' '`) — `getfil(finidat, fnamer, 0)`, then:
      ```fortran
      call restFile_read(bounds_proc, fnamer, &
           atm2lnd_vars, aerosol_vars, canopystate_vars, cnstate_vars, &
           ch4_vars, energyflux_vars, frictionvel_vars, lakestate_vars, &
           photosyns_vars, soilhydrology_vars,                          &
           soilstate_vars, solarabs_vars, surfalb_vars,                 &
           sedflux_vars, ep_betr, alm_fates, glc2lnd_vars, crop_vars)
      ```
      The `alm_fates` argument routes into `hlm_fates_interface_type%restart` (`main/elmfates_interfaceMod.F90:1726`), which **at api.43 takes three FATES-side keyword arguments** (`canopystate_inst`, `frictionvel_inst`, `soilstate_inst`) — see [`fates_interface.md`](fates_interface.md).
    - **Continue / branch** (`nsrest == nsrContinue .or. nsrBranch`) — same `restFile_read` call (`:881-886`).
22. **Interpolated initial conditions** (`finidat_interp_source`). If set, write a template via `restFile_write`, then `initInterp(filei, fileo, bounds_proc)`, then `restFile_read` the interpolated result (`:894-936`).
23. **Reweight wrapup** per clump using the ice-sheet mask (`:938-944`).
24. **Nitrogen / phosphorus deposition streams.** `ndep_init`, `ndep_interp` (`:953-957`); `pdep_init`, `pdep_interp` (`:970-974`); FAN ammonia stream (`use_fan`).
25. **History tape build.** `hist_htapes_build()` unless `nsrest == nsrContinue` (`:987-989`).
26. **Accumulator-variable init.** `atm2lnd_vars%initAccVars`, `top_as/top_af/veg_es/canopystate_vars%InitAccVars`, crop, FATES (`alm_fates%initAccVars(bounds_proc)` at `:1007-1009`), CN state.
27. **Monthly vegetation read.** If dry-dep XLND or `use_fates_sp`, `readAnnualVegetation` / `interpMonthlyVeg` (`:1019-1030`).
28. **Initial `lnd2atm`.** For `nsrest == nsrStartup`, `lnd2atm_minimal(...)` sets initial export state (`:1036-1044`).
29. **Initial `lnd2glc`.** For glacier-mec runs (`:1052-1064`).
30. **Deallocate `wt_nat_patch`** (`:1073`).
31. **FATES cold-start.** If `use_fates .and. .not.is_restart() .and. finidat == ' ' .and. nsrest /= nsrBranch` (`:1079-1093`):
    - If `use_fates_sp`, run `SatellitePhenology` per clump first.
    - `alm_fates%init_coldstart(canopystate_vars, soilstate_vars, frictionvel_vars)` — body at `main/elmfates_interfaceMod.F90:2085-2261`. Per clump: `init_site_vars`, `zero_site`, `set_site_properties`; if `use_fates_planthydro`, fill hydraulic `bc_in` from `soilstate_vars` and call `HydrSiteColdStart`; if `use_fates_luh`, copy `landuse_states`/`landuse_transitions` and the appropriate harvest fields; `init_patches`; per-site `ed_update_site(..., is_restarting=.false.)`; `wrap_update_hlmfates_dyn(..., .false.)`; flush and zero history buffers; `fates_hist%update_history_dyn`.
32. **`topo_glc_mec` deallocation** (`:1105`).
33. **ELM-interface / PFLOTRAN init.** If `use_elm_interface`, `elm_interface_data%Init(bounds_proc)`; if also `use_pflotran`, `elm_pf_interface_init(bounds_proc)` (`:1109-1117`).
34. **End-of-init log message** (`:1124-1138`).

## Stage 3: `initialize3`

`initialize3` (`main/elm_initializeMod.F90:1146-1226`) is a thin wrapper that gives the multi-physics framework (`components/elm/src/utils/mpp`) its view of the ELM decomposition:

1. Decide `restart_vsfm` based on `nsrest` / `finidat`.
2. `mpp_varpar_init(nlevsoi, nlevgrnd, nlevsno, max_patch_per_col)` (`:1193`).
3. `mpp_varcon_init_landunit(istsoil, istcrop, istice, istice_mec, istdlak, istwet, max_lunit)` and `mpp_varcon_init_column(...)`.
4. `mpp_varctl_init_vsfm(use_vsfm, vsfm_use_dynamic_linesearch, vsfm_include_seepage_bc, lateral_connectivity, restart_vsfm, vsfm_satfunc_type, vsfm_lateral_model_type)` (`:1201-1203`).
5. `mpp_varctl_init_petsc_thermal(use_petsc_thermal_model)`.
6. `mpp_bounds_init_proc_bounds(...)` and `mpp_bounds_init_clump(get_proc_clumps())` (`:1208-1213`).
7. **External model attach.** If `use_vsfm`, `EMI_Init_EM(EM_ID_VSFM)`. If `use_petsc_thermal_model`, `EMI_Init_EM(EM_ID_PTM)` (`:1215-1221`).

If neither VSFM nor PETSc-thermal nor lateral connectivity is active, `elm_petsc_init` returns without calling `PetscInitialize`, so stage 3 is effectively a no-op for most Kougarok-style point runs.

## Start type branching

`lnd_init_mct` translates the coupler `starttype` into `nsrest` before calling `initialize1`:

| `starttype` | `nsrest` | Restart path | Initial-conditions source |
|---|---|---|---|
| `seq_infodata_start_type_start` | `nsrStartup = 0` | Cold start or interpolation from `finidat_interp_source` | `finidat`, or cold values if blank |
| `seq_infodata_start_type_cont` | `nsrContinue = 1` | Standard continue | Restart pointer file written by previous run |
| `seq_infodata_start_type_brnch` | `nsrBranch = 2` | Branch off another case | Explicit `finidat` from another case, but time manager continues |

`initialize2` switches on `nsrest` at several points:

- **Time manager.** Startup → `timemgr_init()`. Continue/branch → `restFile_open` + `timemgr_restart_io` + `timemgr_restart`.
- **History namelist.** `htapes_fieldlist()` only on `nsrContinue`.
- **State read.** Startup with non-blank `finidat`, and both continue and branch, call `restFile_read`.
- **Interpolated IC.** Only on `nsrStartup .and. finidat_interp_source /= ' '`.
- **FATES cold-start.** Only on `use_fates .and. .not. is_restart() .and. finidat == ' ' .and. nsrest /= nsrBranch`. Any non-cold path relies on `restFile_read` to rehydrate FATES state.

## Subsystems touched during init

| Subsystem | Init call(s) | Stage | Source |
|---|---|---|---|
| Namelist / run control | `control_init`, `control_setNL`, `elm_varctl_set`, `dynSubgridControl_init` | 1 | `main/controlMod.F90`, `main/elm_varctl.F90`, `dyn_subgrid/dynSubgridControlMod.F90` |
| Time manager | `timemgr_init` / `timemgr_restart` | 2 | `utils/elm_time_manager.F90` |
| Decomposition | `decompInit_lnd*`, `decompInit_clumps`, `decompInit_ghosts`, `decompInit_gtlcp` | 1 | `main/decompInitMod.F90`, `main/decompMod.F90` |
| Surface data | `surfrd_get_globmask`, `surfrd_get_grid`, `surfrd_get_topo`, `surfrd_get_topo_for_solar_rad`, `surfrd_get_data`, `surfrd_finetop_data` | 1 | `main/surfrdMod.F90`, `main/surfrdUtilsMod.F90` |
| Subgrid types | `grc_pp%Init`, `top_pp%Init`, `lun_pp%Init`, `col_pp%Init`, `veg_pp%Init`, `initGridCells` | 1 | `data_types/*Type.F90`, `main/initGridCellsMod.F90` |
| Filters | `allocFilters` | 1 | `main/filterMod.F90` |
| Biogeophysics instances | `elm_inst_biogeophys` | 2 | `main/elm_instMod.F90` |
| Biogeochem instances (CN / FATES) | `elm_inst_biogeochem` (allocates `cnstate_vars`, `carbonstate_vars`, ..., and calls `alm_fates%init`) | 2 | `main/elm_instMod.F90` |
| Decomposition cascade | `init_decomp_cascade_constants`, `init_decompcascade_bgc` / `_cn` | 2 | `biogeochem/DecompCascadeBGCMod.F90`, `biogeochem/DecompCascadeCNMod.F90` |
| ELM parameters | `pftconrd`, `soilorder_conrd`, `readSharedParameters`, `readPrivateParameters` | 1/2 | `main/pftvarcon.F90`, `main/readParamsMod.F90` |
| FATES (NEW: 2-step parameter handoff) | `ELMFatesGlobals1`, `ELMFatesGlobals2`, `ELMFatesTimesteps`, `alm_fates%init`, `alm_fates%InitAccBuffer`, `alm_fates%Init2`, `alm_fates%init_coldstart`, `alm_fates%initAccVars` | 1/2 | `main/elmfates_interfaceMod.F90` |
| FATES LUH2 | `dynFatesLandUseInit` | 2 | `main/dynFATESLandUseChangeMod.F90` |
| Hydrology | `init_hydrology` (called from `elm_inst_biogeophys`) | 2 | `main/init_hydrology.F90` |
| SNICAR | `SnowOptics_init`, `SnowAge_init` | 2 | `biogeophys/SnowSnicarMod.F90` |
| Deposition streams | `ndep_init`, `ndep_interp`, `pdep_init`, `pdep_interp`, `fanstream_init` | 2 | `main/ndepStreamMod.F90`, `main/pdepStreamMod.F90`, `main/fanStreamMod.F90` |
| History tapes | `hist_htapes_build`, `hist_addfld1d/2d`, accumulator registration | 2 | `main/histFileMod.F90` |
| Restart | `restFile_getfile`, `restFile_open`, `restFile_read`, `restFile_write` | 2 | `main/restFileMod.F90`, `main/subgridRestMod.F90` |
| Ecosystem dynamics | `EcosystemDynInit` (→ `AllocationInit`, `PhenologyInit`, `FireInit`, `C14_init_BombSpike`, `fanInit`) | 2 | `biogeochem/EcosystemDynMod.F90` |
| Dynamic subgrid | `init_subgrid_weights_mod`, `dynSubgrid_init` | 2 | `main/subgridWeightsMod.F90`, `dyn_subgrid/dynSubgridDriverMod.F90` |
| MPP / PETSc | `mpp_varpar_init`, `mpp_varcon_init_*`, `mpp_varctl_init_*`, `mpp_bounds_init_*`, `EMI_Init_EM` | 3 | `utils/mpp/...`, `main/ExternalModelInterfaceMod.F90` |

## Key initialization invariants

- The FATES init order at api.43 is `ELMFatesGlobals1` (stage 1, with FATES-side parameter file read) → subgrid decomposition → `ELMFatesGlobals2` (stage 1) → `alm_fates%init(bounds_proc, flandusepftdat)` (stage 2) → `alm_fates%init_coldstart` (stage 2, cold-start only). It cannot be reordered.
- **There is no `FatesReadPFTs` step at api.43.** Code that calls or imports it will not compile.
- `ELMFatesGlobals1` must run **before** `update_pft_array_bounds`, because phase 1 sets `natpft_size = fates_maxPatchesPerSite` and therefore determines how many patches per column will be allocated.
- `pftconrd` runs **before** `wt_nat_patch` is allocated (different from 60d9aad). The new order in stage 1 is: allocate the non-pft-dependent surface arrays → `pftconrd()` → allocate `wt_nat_patch`/`wt_cft`/`fert_cft`/`fert_p_cft` → `soilorder_conrd()` → `surfrd_get_data` → `ELMFatesGlobals2`.
- `surfrd_get_data` must run **after** `ELMFatesGlobals1` (which sets `natpft_size`) and **before** `ELMFatesGlobals2`.
- `readSharedParameters` runs in stage 2 because it needs the namelist switches.
- The restart read in stage 2 always passes `alm_fates` so FATES restart is atomic with ELM restart — FATES cannot be restarted independently. The `alm_fates%restart` call inside `restFile_read` (`main/restFileMod.F90:642-647`) **passes three FATES-side keyword arguments** (`canopystate_inst`, `frictionvel_inst`, `soilstate_inst`) at api.43.
- CN and FATES share the `EcosystemDynInit` / `EcosystemDyn*Leaching*` scaffolding, but FATES replaces CN's phenology, allocation, and fire with its own per-site state. `EcosystemDynInit` early-returns after `AllocationInit` when `use_fates` is true (`biogeochem/EcosystemDynMod.F90:97-116`).
- `initialize3` is not FATES-aware. Nothing in PETSc/VSFM/MPP interacts with FATES.
- The restart read must run **before** `alm_fates%init_coldstart`, so that `init_coldstart` is gated behind `.not. is_restart() .and. finidat == ' '`.
- `dynFatesLandUseInit` (NEW, called only when `use_fates_luh`) must run after `dynSubgrid_init` and before `EcosystemDynInit` so its varname tables are populated before FATES picks them up.

## Related pages

- [`driver_and_coupling.md`](driver_and_coupling.md) — caller context (`lnd_init_mct`) and the `elm_drv` loop that runs after init completes.
- [`fates_interface.md`](fates_interface.md) — what `ELMFatesGlobals1`, `ELMFatesGlobals2`, `alm_fates%init`, `alm_fates%init_coldstart`, and `alm_fates%Init2` do in detail at api.43.
- [`namelist_and_control.md`](namelist_and_control.md) — `control_init`, `elm_varctl` flags, the FATES namelist block.
- [`history_and_restart.md`](history_and_restart.md) — `restFile_read`/`restFile_write` argument list and the new FATES-side keyword arguments in the inner `alm_fates%restart` call.
