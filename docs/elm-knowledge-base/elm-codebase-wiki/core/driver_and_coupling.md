---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Driver and coupling

This page documents how ELM enters from the CIME flux coupler and what ELM does in response. It covers the MCT component shim (`cpl/lnd_comp_mct.F90`), the coupler import/export surface (`cpl/lnd_import_export.F90`), and the main physics driver (`main/elm_driver.F90`). The CIME driver, MCT, and ESMF frameworks themselves are out of scope. For FATES-specific dispatch from `elm_drv`, see [`fates_interface.md`](fates_interface.md).

## Entry points from the coupler

`cpl/lnd_comp_mct.F90` publishes three CIME-visible entry points (cpl/lnd_comp_mct.F90:1):

| Entry point | Source | Purpose |
|---|---|---|
| `lnd_init_mct` | `cpl/lnd_comp_mct.F90:63` | One-time land component initialization. Reads namelists, builds grid, allocates state, performs the full three-stage ELM init, builds initial MCT attribute vectors. |
| `lnd_run_mct` | `cpl/lnd_comp_mct.F90:415` | Called once per CIME coupling interval. Imports the coupler-to-land vector, spins an internal ELM-timestep loop until the coupling alarm fires, then exports the land-to-coupler vector. |
| `lnd_final_mct` | `cpl/lnd_comp_mct.F90:670` | Calls `elm_finalizeMod::final()` and releases MOAB buffers if compiled with `HAVE_MOAB`. |

The module also provides MCT-internal helpers `lnd_setgsmap_mct` and `lnd_domain_mct` (cpl/lnd_comp_mct.F90:701, cpl/lnd_comp_mct.F90:747) used only during init to describe ELM's decomposition and domain back to the driver, and a `HAVE_MOAB`-gated set of `*_moab` paths for E3SM's mesh-oriented runtime. Those are parallel machinery and not covered here.

## `lnd_init_mct` – one-time startup

Key side effects of `lnd_init_mct`, in order (cpl/lnd_comp_mct.F90:63–411):

1. **Extract CIME handles.** `seq_cdata_setptrs` pulls `LNDID`, `mpicom_lnd`, the MCT `gsMap`/`gGrid`, and the shared `infodata` (cpl/lnd_comp_mct.F90:159). `elm_instance_init(LNDID)` stores the component ID into the `elm_instance` module (`main/elm_instance.F90:20`).
2. **Set coupler field indices.** `elm_cpl_indices_set` (from `cpl/elm_cpl_indices.F90`) populates the module-level `index_x2l_*` and `index_l2x_*` integers used by the import/export routines. Called at cpl/lnd_comp_mct.F90:172.
3. **SPMD bring-up and logging.** `spmd_init(mpicom_lnd, LNDID)` (cpl/lnd_comp_mct.F90:176) then `lnd_modelio.nml` attach (cpl/lnd_comp_mct.F90:191–201).
4. **Pull orbital parameters and clock state** from `infodata` and `EClock` (cpl/lnd_comp_mct.F90:238, 249).
5. **Set starttype → `nsrest`** (startup/continue/branch) via `elm_varctl_set` and classify via `seq_infodata_start_type_*` (cpl/lnd_comp_mct.F90:265–283).
6. **`control_setNL`** (from `main/controlMod.F90`) registers the `lnd_in{_NNNN}` namelist filename for this instance (cpl/lnd_comp_mct.F90:243).
7. **`initialize1()`** (cpl/lnd_comp_mct.F90:289) – see [`initialization.md`](initialization.md). On return, if no valid land points, set `lnd_present=.false.` and exit.
8. **gsMap, domain, attribute vectors.** `get_proc_bounds(bounds)`, then `lnd_setgsmap_mct` builds the global segment map, `lnd_domain_mct` fills the MCT grid, and `mct_aVect_init(x2l_l, ...)` / `mct_aVect_init(l2x_l, ...)` allocate the coupler attribute vectors with the field lists `seq_flds_x2l_fields` / `seq_flds_l2x_fields` (cpl/lnd_comp_mct.F90:310–330).
9. **`initialize2()` and `initialize3()`** (cpl/lnd_comp_mct.F90:347–348) – remaining allocation, time manager, FATES cold-start and restart read.
10. **Sanity check on timestep alignment.** `dtime_sync` from the EClock must be a multiple of `dtime_elm` or `endrun` (cpl/lnd_comp_mct.F90:352–362).
11. **Prime the export vector.** Calls `lnd_export(bounds, lnd2atm_vars, lnd2glc_vars, l2x_l%rattr)` so the first coupler send is valid even before any timestep runs (cpl/lnd_comp_mct.F90:366–367).
12. **Publish prognostic status.** `seq_infodata_PutData(infodata, lnd_prognostic=.true.)` and push `lnd_nx`/`lnd_ny`/`precip_downscaling_method` back to the driver (cpl/lnd_comp_mct.F90:376–377).
13. **`nextsw_cday` setup** for the first radiation step (cpl/lnd_comp_mct.F90:385, 393–394).

After `lnd_init_mct` returns, the coupler holds:
- A populated `gsMap_lnd` and MCT `dom_l` describing ELM's decomposition.
- An empty (but zeroed) `x2l_l` and a primed `l2x_l` with initial albedos and surface temperature.

## `lnd_run_mct` – one coupling interval

`lnd_run_mct` wraps one coupling interval and may run several ELM time steps inside it. The sequence (cpl/lnd_comp_mct.F90:415–666):

1. **Refresh `nextsw_cday`**. `seq_infodata_GetData(infodata, nextsw_cday=...)` then `set_nextsw_cday` (cpl/lnd_comp_mct.F90:517–519). If the atmosphere is absent, ELM derives its own shortwave calendar day from `nstep` (cpl/lnd_comp_mct.F90:522–529).
2. **Record restart/stop alarms** from the EClock (cpl/lnd_comp_mct.F90:532–533).
3. **Import coupler state.** `call lnd_import(bounds, x2l_l%rattr, atm2lnd_vars, glc2lnd_vars, lnd2atm_vars)` pulls the `x2l_l` attribute vector into ELM's internal `atm2lnd_vars` and `glc2lnd_vars` (cpl/lnd_comp_mct.F90:542). If compiled with MOAB, a parallel `lnd_import_moab` call overwrites those values from MOAB tags.
4. **Re-pull orbital parameters** (they can change mid-run, e.g. perpetual year runs) (cpl/lnd_comp_mct.F90:571).
5. **Internal ELM timestep loop**. Controlled by `dosend`, driven by `seq_timemgr_EClockDateInSync`:
   ```
   dosend = .false.
   do while (.not. dosend)
      get_curr_date → ymd, tod
      dosend = EClockDateInSync(EClock, ymd, tod)
      compute doalb from nextsw_cday vs calendar day
      rstwr = rstwr_sync .and. dosend
      nlend = nlend_sync .and. dosend
      shr_orb_decl(calday,     ...) → declin
      shr_orb_decl(nextsw_cday, ...) → declinp1
      call elm_drv(doalb, nextsw_cday, declinp1, declin, rstwr, nlend, rdate)
      call lnd_export(bounds, lnd2atm_vars, lnd2glc_vars, l2x_l%rattr)
      call advance_timestep()
   end do
   ```
   (cpl/lnd_comp_mct.F90:576–637). `doalb` is `true` only on the ELM step whose end lines up with the next radiation calculation; `rstwr` / `nlend` are only `.true.` on the final step of the coupling interval.
6. **Sync check.** After the loop, `get_curr_date(offset=-dtime)` must equal the EClock date or `endrun` (cpl/lnd_comp_mct.F90:641–649).

All actual physics happens inside `elm_drv`; this shim is purely a sync-and-dispatch layer.

## `lnd_final_mct`

Calls `elm_finalizeMod::final()` (cpl/lnd_comp_mct.F90:695). In the current tree, `final()` only finalizes PETSc when VSFM is on (`main/elm_finalizeMod.F90:21–48`).

## Import: `lnd_import`

`cpl/lnd_import_export.F90::lnd_import` (cpl/lnd_import_export.F90:22) maps the `x2l(:,:)` array from the coupler into ELM's internal `atm2lnd_vars` gridcell-level state. It also handles the several metdata-bypass paths used by single-point and offline runs (namelist group `light_streams` at cpl/lnd_import_export.F90:141 and related blocks).

The canonical coupled branch writes these scalar fields per gridcell (cpl/lnd_import_export.F90:1084–1094):

| ELM field (gridcell) | Coupler field index | Meaning |
|---|---|---|
| `atm2lnd_vars%forc_hgt_grc(g)` | `index_x2l_Sa_z` | Atm reference height [m] |
| `atm2lnd_vars%forc_u_grc(g)` | `index_x2l_Sa_u` | Zonal wind [m s⁻¹] |
| `atm2lnd_vars%forc_v_grc(g)` | `index_x2l_Sa_v` | Meridional wind [m s⁻¹] |
| `atm2lnd_vars%forc_solad_grc(g,2)` | `index_x2l_Faxa_swndr` | Direct near-IR shortwave [W m⁻²] |
| `atm2lnd_vars%forc_solad_grc(g,1)` | `index_x2l_Faxa_swvdr` | Direct visible shortwave [W m⁻²] |
| `atm2lnd_vars%forc_solai_grc(g,2)` | `index_x2l_Faxa_swndf` | Diffuse near-IR shortwave [W m⁻²] |
| `atm2lnd_vars%forc_solai_grc(g,1)` | `index_x2l_Faxa_swvdf` | Diffuse visible shortwave [W m⁻²] |
| `atm2lnd_vars%forc_th_not_downscaled_grc(g)` | `index_x2l_Sa_ptem` | Potential temperature [K] |
| `atm2lnd_vars%forc_q_not_downscaled_grc(g)` | `index_x2l_Sa_shum` | Specific humidity [kg kg⁻¹] |

River coupling fields (`index_x2l_Flrr_*`) are also ingested here (cpl/lnd_import_export.F90:191–200). CO₂, aerosol deposition, and N/P deposition fields follow similar patterns; there are separate code paths for `co2_type='prognostic'` vs `'diagnostic'` (cpl/lnd_import_export.F90:171–174).

The `_not_downscaled_grc` suffix is important. The raw gridcell forcing is later disaggregated to topounits and optionally downscaled by elevation in `cpl/lnd_disagg_forc.F90` and `cpl/lnd_downscale_atm_forcing.F90`. After disaggregation, `top_as` (topounit atmospheric state) and `top_af` (topounit atmospheric flux) carry the values that the physics actually consumes:

```fortran
top_as%tbot(topo)    = atm2lnd_vars%forc_t_not_downscaled_grc(g)   ! cpl/lnd_import_export.F90:1036
top_as%thbot(topo)   = atm2lnd_vars%forc_th_not_downscaled_grc(g)  ! :1037
top_as%pbot(topo)    = atm2lnd_vars%forc_pbot_not_downscaled_grc(g)! :1038
top_as%qbot(topo)    = atm2lnd_vars%forc_q_not_downscaled_grc(g)   ! :1039
top_af%rain(topo)    = forc_rainc + forc_rainl                     ! :1069
top_af%snow(topo)    = forc_snowc + forc_snowl                     ! :1070
top_af%solad(topo,:) = atm2lnd_vars%forc_solad_grc(g,:)            ! :1071-1072
```

## Export: `lnd_export`

`lnd_export` (cpl/lnd_import_export.F90:1347) fills `l2x(:,:)` from `lnd2atm_vars` and `lnd2glc_vars`. The core fields per gridcell are (cpl/lnd_import_export.F90:1385–1404):

| Coupler field index | ELM source | Notes |
|---|---|---|
| `index_l2x_Sl_t` | `lnd2atm_vars%t_rad_grc(g)` | Effective radiative surface temp |
| `index_l2x_Sl_snowh` | `lnd2atm_vars%h2osno_grc(g)` | Snow water equivalent [mm] |
| `index_l2x_Sl_avsdr`, `_anidr` | `lnd2atm_vars%albd_grc(g,1:2)` | Direct-beam albedo (VIS, NIR) |
| `index_l2x_Sl_avsdf`, `_anidf` | `lnd2atm_vars%albi_grc(g,1:2)` | Diffuse albedo (VIS, NIR) |
| `index_l2x_Sl_tref`, `_qref` | `lnd2atm_vars%t_ref2m_grc`, `q_ref2m_grc` | 2 m screen-level state |
| `index_l2x_Sl_u10`, `_u10withgusts` | `lnd2atm_vars%u_ref10m_grc`, `u_ref10m_with_gusts_grc` | 10 m wind, with/without gusts |
| `index_l2x_Fall_taux`, `_tauy` | `-lnd2atm_vars%taux_grc`, `-tauy_grc` | Momentum flux (sign flipped to coupler convention) |
| `index_l2x_Fall_lat`, `_sen` | `-eflx_lh_tot_grc`, `-eflx_sh_tot_grc` | Latent, sensible heat |
| `index_l2x_Fall_lwup` | `-eflx_lwrad_out_grc` | Upward longwave |
| `index_l2x_Fall_evap` | `-qflx_evap_tot_grc` | Evaporation |
| `index_l2x_Fall_swnet` | `fsa_grc` | Net absorbed shortwave |
| `index_l2x_Fall_fco2_lnd` | `-nee_grc` (if coupled-carbon) | Land→atm CO₂ flux |

Optional fields only written if their index is nonzero include dust fluxes (`index_l2x_Fall_flxdst1..4`), MEGAN VOC emissions (`index_l2x_Fall_flxvoc`), dry-deposition velocities (`index_l2x_Sl_ddvel`), methane (`index_l2x_Fall_methane`), and FAN NH₃ (`index_l2x_Fall_flxnh3`). River fields (`index_l2x_Flrl_*`) carry liquid/ice/surface/subsurface runoff to MOSART. Glacier coupling fields (`index_l2x_Sl_tsrf`, `_topo`, `index_l2x_Flgl_qice`) are written only when `create_glacier_mec_landunit` is true.

Everything in `l2x_l` is populated at gridcell resolution; ELM's subgrid hierarchy is collapsed in `main/lnd2atmMod::lnd2atm`, which is called inside `elm_drv` before `lnd_export` sees the data.

## `elm_drv` – the main driver loop

`main/elm_driver.F90` exposes `elm_drv(doalb, nextsw_cday, declinp1, declin, rstwr, nlend, rdate)` (main/elm_driver.F90:197) plus three private helpers: `elm_drv_init` (main/elm_driver.F90:1557), `elm_drv_patch2col` (main/elm_driver.F90:1670), and `write_diagnostic` (main/elm_driver.F90:1870). `elm_drv` parallelizes over OpenMP "clumps" obtained from `get_proc_clumps` / `get_clump_bounds` (`main/decompMod.F90`).

The high-level shape of one call, with FATES-relevant branches called out, is:

1. **Dynamic subgrid adjustment.** `dynSubgrid_driver` is the first call (not shown in the file header excerpt but visible in the imports at main/elm_driver.F90:29). After this, subgrid weights for transient land-cover changes are up to date.
2. **Balance-check opening entries.** `BeginColWaterBalance`, `BeginGridWaterBalance`, then `BeginColCBalance` / `BeginColNBalance` / `BeginColPBalance` when `use_cn` or `use_fates` (main/elm_driver.F90:393–443).
3. **Phenology interpolation.** CN uses `interpMonthlyVeg` conditionally; FATES in satellite-phenology mode (`use_fates_sp`) also calls `interpMonthlyVeg`; otherwise the prescribed-biogeography path reads monthly LAI (main/elm_driver.F90:280–313).
4. **Decomposition vertical profile update** for CN or FATES (main/elm_driver.F90:339–347).
5. **Fire/deposition interpolation.** `FireInterp` for CN, `alm_fates%InterpFileInputs` for FATES when `fates_spitfire_mode > scalar_lightning`; `pdep_interp` runs for both (main/elm_driver.F90:631–654). `pdep_interp` updates dynamic P deposition.
6. **Per-clump physics loop** (`!$OMP PARALLEL DO PRIVATE (nc,bounds_clump,...)`, main/elm_driver.F90:670). Inside each clump:
   - `UpdateDaylength` and `elm_drv_init` zero per-timestep accumulators.
   - `downscale_forcings` (from `atm2lndMod`) pushes the gridcell/topounit state down to column/patch arrays.
   - `CanopyHydrology` handles canopy interception and fresh snow initialization.
   - **Surface radiation.** If `use_fates`, `alm_fates%wrap_sunfrac(bounds_clump, top_af, canopystate_vars)` replaces `CanopySunShadeFractions`; otherwise the non-FATES path runs (main/elm_driver.F90:721–727). `SurfaceRadiation` and `UrbanRadiation` run next.
   - **Canopy/flux solver.** `CanopyTemperature` sets leaf-temperature boundary conditions; then `CanopyFluxes` does the iterative leaf energy-balance solve (main/elm_driver.F90:754–786). `CanopyFluxes` is where FATES photosynthesis is actually invoked – see [`fates_interface.md`](fates_interface.md) for `prep_canopyfluxes`, `wrap_btran`, `wrap_photosynthesis`, `wrap_accumulatefluxes`, and `wrap_hydraulics_drive`.
   - `SoilFluxes`, `LakeFluxes`, `UrbanFluxes`, `LakeTemperature`, `SoilTemperature` follow.
   - `LakeHydrology`, `HydrologyNoDrainage`, `HydrologyDrainage` complete the column water budget. `HydrologyNoDrainage` calls `alm_fates%ComputeRootSoilFlux` when FATES is active (see `biogeophys/HydrologyNoDrainageMod.F90:235`).
   - `EcosystemDynNoLeaching1`, the `elm_interface`/PFLOTRAN bridge (when `use_elm_interface .and. use_pflotran`), then `EcosystemDynNoLeaching2` run the column-level soil BGC decomposition (main/elm_driver.F90:1030–1132). When `use_fates_sp` is true, `SatellitePhenology` is called here instead of the CN phenology routines. `AnnualUpdate` runs only when CN is active, not under FATES.
   - **Vegetation update.** For `use_cn`: `VegStructUpdate` runs on albedo timesteps. For `use_fates`: `alm_fates%WrapUpdateFatesRmean`, `alm_fates%wrap_update_hifrq_hist`, and once per simulation day `alm_fates%dynamics_driv(...)` (main/elm_driver.F90:1285–1300).
   - **Balance checks.** Column-level water, carbon, nitrogen, phosphorus, and gridcell carbon balance checks run under `use_cn .or. use_fates` (main/elm_driver.F90:1335–1353).
   - **Albedo update** (`SurfaceAlbedo`, `UrbanAlbedo`) when `doalb` is true (main/elm_driver.F90:1361–1393).
7. **Global seed dispersal** across MPI tasks if FATES seed dispersal is active (main/elm_driver.F90:1399–1401).
8. **`lnd2atm`** (main/elm_driver.F90:1411–1417) builds the gridcell-averaged export state from the subgrid pools.
9. **Accumulators, history, budgets, and restart.** `hist_update_hbuf` then per-component `UpdateAccVars` calls. If FATES is active, `alm_fates%UpdateAccVars(bounds_proc)` runs here (main/elm_driver.F90:1473). On the final step (`rstwr=.true.`), `restFile_write` is called with the FATES object in the argument list so FATES restart data is written atomically with ELM's own restart.
10. **Diagnostics** via `write_diagnostic`.

The driver is deliberately data-flow-oriented: everything the physics cares about is reached through a small set of module-level instances (`atm2lnd_vars`, `lnd2atm_vars`, `col_cs`/`col_cf`/..., `veg_cs`/..., `alm_fates`) imported from `elm_instMod`. There is no dependency injection; `elm_drv` is effectively the entire mid-level physics schedule.

## What `elm_drv` does not do

- It does **not** touch the coupler attribute vectors. Those are marshalled only in `lnd_import` and `lnd_export`.
- It does **not** advance the time manager. That happens in `lnd_run_mct` after `elm_drv` returns (`advance_timestep()` at cpl/lnd_comp_mct.F90:634).
- It does **not** decide when to write restart or stop; it only honors the `rstwr` / `nlend` flags passed from the coupler loop.
- It does **not** call FATES internals directly. Every FATES call is routed through a procedure on `alm_fates` (see [`fates_interface.md`](fates_interface.md)).
- It does **not** re-read namelists or surface data. Those are one-shot in `initialize1` / `initialize2`.

## Key driver arguments

`elm_drv(doalb, nextsw_cday, declinp1, declin, rstwr, nlend, rdate)` uses these arguments to route flow inside one timestep:

| Argument | Type | Meaning |
|---|---|---|
| `doalb` | logical | `.true.` only on the timestep whose end aligns with the atmosphere's next radiation calculation. Controls whether surface albedo is updated and whether CN runs its albedo-coupled path (`if (use_cn .and. doalb) call VegStructUpdate`). |
| `nextsw_cday` | real(r8) | Calendar day of the next shortwave calculation. Used for solar declination (`shr_orb_decl`) and for deciding on the very first step (`nstep == 1`) whether `doalb` is satisfied. |
| `declinp1`, `declin` | real(r8) | Solar declinations at next and current timestep, precomputed in `lnd_run_mct` (cpl/lnd_comp_mct.F90:614–615) and passed in because `elm_drv` is entered with them baked into `rdate`. |
| `rstwr` | logical | `.true.` means "write restart before returning" – only set on the final ELM step of the current coupling interval and only if the EClock restart alarm is on. |
| `nlend` | logical | `.true.` means "last step of the run" – set from the EClock stop alarm. |
| `rdate` | character(32) | `YYYY-MM-DD-SSSSS` date string used for restart filenames. |

`doalb` is checked at main/elm_driver.F90:594–598 – the first timestep's `doalb` is decided by comparing `nextsw_cday` to the next calendar day; subsequent steps use `(nextsw_cday >= -0.5)` as the gate. The first step after init skips albedo (`doalb = .false.` at line 593) to avoid a stale cosine-of-zenith problem.

## Coupler field sources (lnd2atm / atm2lnd lineage)

The `x2l_l` / `l2x_l` attribute vectors touched by `lnd_import` / `lnd_export` come from and go to ELM state through two intermediate types:

- **`atm2lnd_vars` / `glc2lnd_vars`** (`main/atm2lndMod.F90`, `main/glc2lndMod.F90`) – populated by `lnd_import` from `x2l_l`, then consumed by `downscale_forcings` which pushes the values into `top_as` / `top_af` / `col_*` state inside the clump loop. `downscale_forcings` is where elevation lapse-rate downscaling and topographic aspect corrections happen.
- **`lnd2atm_vars` / `lnd2glc_vars`** (`main/lnd2atmMod.F90`, `main/lnd2glcMod.F90`) – populated by `lnd2atm` at the end of `elm_drv` from column / patch state, then consumed by `lnd_export` to fill `l2x_l`.

Because `lnd_import` runs before the ELM timestep loop but `lnd_export` runs inside it, the import fields are effectively frozen for all ELM steps inside one coupling interval, while the export fields are refreshed every ELM step (but only the last one actually reaches the coupler since the MCT attribute vector is overwritten each time).

## Per-instance and per-rank state

`elm_instance_init(LNDID)` stores `lnd_id`, `inst_name`, `inst_suffix`, `inst_index` in the `elm_instance` module (`main/elm_instance.F90:20`). These are used to:

- Construct `lnd_modelio.nml` filenames (e.g. `lnd_modelio.nml_0001`).
- Construct per-instance namelist filenames via `control_setNL("lnd_in"//trim(inst_suffix))`.
- Tag restart and history file names (`main/restFileMod.F90`, `main/histFileMod.F90`).

The coupler can run multiple ELM instances at once (e.g. for ensembles). `inst_index` distinguishes them; the module-level `alm_fates` and every other instance variable are **per-rank per-instance**, not global. MPI rank-level parallelism is provided by the `mpicom_lnd` communicator passed through `spmd_init`; OpenMP parallelism inside one rank is by clumps, all of which inherit the same `alm_fates` object (but different clump indices).

## Forcing processing between coupler and physics

`lnd_import` only populates the **gridcell-level** fields of `atm2lnd_vars`. The physics operates on column- or patch-level quantities, so there are several rewriting steps inside each ELM step:

1. **Disaggregation to topounit.** `cpl/lnd_disagg_forc.F90` holds helpers that spread the gridcell forcing across the topounits that make up that gridcell. Each gridcell may contain multiple topounits (different elevations or slope bands).
2. **Downscaling by elevation, slope, and aspect.** `cpl/lnd_downscale_atm_forcing.F90` and `main/atm2lndMod.F90::downscale_forcings` apply lapse-rate corrections to temperature, saturation vapor pressure, longwave, and (optionally) precipitation, and `surfrdMod`'s topo-solar parameters to shortwave. `downscale_forcings` is called from inside the clump loop in `elm_drv` (main/elm_driver.F90:685–687) so it runs per clump and sees both the raw `atm2lnd_vars` and the topographic state in `top_pp`.
3. **Copy into `top_as` / `top_af`.** The topounit-scoped atmospheric state (`top_as` – atmospheric state, `top_af` – atmospheric flux) is the interface that every downstream module actually reads. This happens inside `lnd_import_export.F90:1036–1072` for the coupler path and inside `downscale_forcings` for the topographic-downscaling path.

The physics modules then read from `top_as%tbot(topo)`, `top_as%pbot(topo)`, `top_as%qbot(topo)`, `top_af%rain(topo)`, `top_af%snow(topo)`, `top_af%solad(topo,:)` – not from `atm2lnd_vars`. FATES-side boundary conditions in `bc_in` are similarly filled from `top_as` / `top_af`, not from `atm2lnd_vars` directly (see `alm_fates%dynamics_driv` in [`fates_interface.md`](fates_interface.md)).

## Export assembly (`lnd2atm`)

`lnd2atm` (`main/lnd2atmMod.F90`) runs near the end of `elm_drv` (main/elm_driver.F90:1411–1416). Its job is to roll patch-level and column-level state up to gridcell averages, mass-weighted by `wt_lunit * wt_column * wt_patch`. Typical output fields:

- **Radiation and energy balance.** `lnd2atm_vars%t_rad_grc`, `albd_grc(g,1:2)`, `albi_grc(g,1:2)`, `eflx_lh_tot_grc`, `eflx_sh_tot_grc`, `eflx_lwrad_out_grc`, `fsa_grc`.
- **Mass fluxes.** `qflx_evap_tot_grc`, `nee_grc` (when coupled-carbon is active), `flux_ch4_grc`.
- **Near-surface diagnostics.** `t_ref2m_grc`, `q_ref2m_grc`, `u_ref10m_grc`, `u_ref10m_with_gusts_grc`.
- **Runoff.** `qflx_rofliq_*_grc`, `qflx_rofice_grc`.
- **Optional chemistry.** `ddvel_grc(:,:)`, `flxvoc_grc(:,:)`, `flxdst_grc(:,:)`, `flux_nh3_grc`.

`lnd_export` then writes those gridcell fields into `l2x_l` with appropriate sign conventions. The sign flip on fluxes (`Fall_lat`, `Fall_sen`, `Fall_evap`, `Fall_lwup`, `Fall_fco2_lnd`, `Fall_taux`, `Fall_tauy`) converts from the ELM "upward positive for fluxes leaving the land" convention to CIME's "positive downward" convention.

## Common entry-point failure modes

A few runtime issues always originate in `lnd_comp_mct` or `elm_driver` and show up here when you debug:

- **`ERROR elm_initializeMod: Unsupported domain_decomp_type`** – `initialize1` was called with a `domain_decomp_type` namelist value that isn't `round_robin`, `graph_partitioning`, or `simple`. See `main/elm_initializeMod.F90:189–201`.
- **`ERROR: atmosphere model MUST send aerosols to ELM`** – `lnd_init_mct` gate at cpl/lnd_comp_mct.F90:304. The coupler's `infodata` reported `atm_present=.true.` but `atm_aero=.false.`; fix the coupler setup, not ELM.
- **`ERROR: unknown starttype`** – `lnd_init_mct` at cpl/lnd_comp_mct.F90:272 rejected a `starttype` string that isn't one of the three defined in `seq_infodata_mod`.
- **`ELM clock not in sync with Master Sync clock`** – `lnd_run_mct` at cpl/lnd_comp_mct.F90:648. The internal ELM clock and the EClock disagree after the `do while` loop; almost always caused by a mismatched `dtime_elm` / `dtime_sync`.
- **`elm dtime ... never align`** – `lnd_init_mct` at cpl/lnd_comp_mct.F90:358. The coupling interval isn't a multiple of the ELM timestep.

Each of these aborts is the last chance ELM gets before physics runs. Nothing deeper in the codebase can recover from them.

## Related pages

- [`initialization.md`](initialization.md) – what `initialize1/2/3` do before `elm_drv` can run.
- [`fates_interface.md`](fates_interface.md) – the entire host-side FATES interface called from `elm_drv` and `CanopyFluxes`.
- `atmosphere_interface.md` – how raw coupler forcings become topounit-level `top_as`/`top_af`, and how `lnd2atm` builds the export state.
- `time_and_decomposition.md` – `get_step_size`, `get_curr_date`, `advance_timestep`, clump/omp parallelism.
- `history_and_restart.md` – `restFile_write` and `hist_update_hbuf` as called from `elm_drv`.
