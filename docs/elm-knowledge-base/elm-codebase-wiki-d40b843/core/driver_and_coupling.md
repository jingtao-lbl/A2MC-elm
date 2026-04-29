---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Driver and coupling

This page documents how ELM enters from the CIME flux coupler and what ELM does in response. It covers the MCT component shim (`cpl/lnd_comp_mct.F90`, 1040 lines), the coupler import/export surface (`cpl/lnd_import_export.F90`, 1630 lines), and the main physics driver (`main/elm_driver.F90`, 1985 lines). The CIME driver, MCT, and ESMF frameworks are out of scope. For FATES-specific dispatch from `elm_drv`, see [`fates_interface.md`](fates_interface.md).

**Major change at d40b843 vs 60d9aad:** the import/export signatures gained the **IAC (Integrated Assessment Coupling)** and **ocean** channels, and a number of file-level line numbers shifted because both `lnd_comp_mct.F90` and `elm_driver.F90` grew.

## Entry points from the coupler

`cpl/lnd_comp_mct.F90` publishes three CIME-visible entry points:

| Entry point | Source | Purpose |
|---|---|---|
| `lnd_init_mct` | `cpl/lnd_comp_mct.F90:58` | One-time land component initialization. Reads namelists, builds grid, allocates state, performs the full three-stage ELM init, builds initial MCT attribute vectors. |
| `lnd_run_mct` | `cpl/lnd_comp_mct.F90:437` | Called once per CIME coupling interval. Imports the coupler-to-land vector, spins an internal ELM-timestep loop until the coupling alarm fires, then exports the land-to-coupler vector. |
| `lnd_final_mct` | `cpl/lnd_comp_mct.F90:684` | Calls `elm_finalizeMod::final()` and releases MOAB buffers if compiled with `HAVE_MOAB`. |

The module also provides MCT-internal helpers `lnd_setgsmap_mct` (`cpl/lnd_comp_mct.F90:716`) and `lnd_domain_mct` (`cpl/lnd_comp_mct.F90:762`) used only during init, and a `HAVE_MOAB`-gated set of `*_moab` paths for E3SM's mesh-oriented runtime.

## `lnd_init_mct` – one-time startup

Key side effects of `lnd_init_mct`, in order (`cpl/lnd_comp_mct.F90:58-433`):

1. **Extract CIME handles.** `seq_cdata_setptrs` pulls `LNDID`, `mpicom_lnd`, MCT `gsMap`/`gGrid`, and `infodata`. `elm_instance_init(LNDID)` stores the component ID into `elm_instance` (`main/elm_instance.F90`).
2. **Set coupler field indices.** `elm_cpl_indices_set` populates the module-level `index_x2l_*` and `index_l2x_*` integers.
3. **SPMD bring-up and logging.** `spmd_init(mpicom_lnd, LNDID)`, then `lnd_modelio.nml` attach.
4. **Pull orbital parameters and clock state** from `infodata` and `EClock`.
5. **Set starttype → `nsrest`** (startup/continue/branch) via `elm_varctl_set`.
6. **`control_setNL`** registers the `lnd_in{_NNNN}` namelist filename for this instance.
7. **Set `use_lnd_rof_two_way` and `use_ocn_lnd_one_way`** (`cpl/lnd_comp_mct.F90:291-293`).
8. **`initialize1()`** (`cpl/lnd_comp_mct.F90:297`). On return, if no valid land points, set `lnd_present=.false.` and exit.
9. **gsMap, domain, attribute vectors.** `get_proc_bounds(bounds)`, `lnd_setgsmap_mct`, `lnd_domain_mct`, `mct_aVect_init(x2l_l, ...)` / `mct_aVect_init(l2x_l, ...)`.
10. **`initialize2()` and `initialize3()`** (`cpl/lnd_comp_mct.F90:354-355`).
11. **Sanity check on timestep alignment.** `dtime_sync` from the EClock must be a multiple of `dtime_elm` or `endrun` (`cpl/lnd_comp_mct.F90:359-368`).
12. **Prime the export vector.** First `lnd_export(...)` call so the first coupler send is valid even before any timestep runs.
13. **Publish prognostic status.** `seq_infodata_PutData(infodata, lnd_prognostic=.true.)`.
14. **`nextsw_cday` setup** for the first radiation step.

After `lnd_init_mct` returns, the coupler holds a populated `gsMap_lnd` and MCT `dom_l`, an empty (zeroed) `x2l_l`, and a primed `l2x_l` with initial albedos and surface temperature.

## `lnd_run_mct` – one coupling interval

`lnd_run_mct` wraps one coupling interval and may run several ELM time steps inside it. The sequence (`cpl/lnd_comp_mct.F90:437-680`):

1. **Refresh `nextsw_cday`.** `seq_infodata_GetData(infodata, nextsw_cday=...)` then `set_nextsw_cday`. If atmosphere is absent, ELM derives its own shortwave calendar day from `nstep`.
2. **Record restart/stop alarms** from the EClock.
3. **Import coupler state.** `cpl/lnd_comp_mct.F90:571-573`:
   ```fortran
   call lnd_import(bounds, x2l_l%rattr, atm2lnd_vars, glc2lnd_vars, &
                   ocn2lnd_vars, lnd2atm_vars, iac2lnd_vars)
   ```
   **NEW signature at d40b843** — the import call now takes `ocn2lnd_vars` and `iac2lnd_vars`.
4. **Re-pull orbital parameters** (they can change mid-run).
5. **Internal ELM timestep loop.** Driven by `seq_timemgr_EClockDateInSync`:
   ```fortran
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
      call lnd_export(bounds, lnd2atm_vars, lnd2glc_vars, lnd2iac_vars, l2x_l%rattr)
      call advance_timestep()
   end do
   ```
   (`cpl/lnd_comp_mct.F90:584-654`.) `doalb` is `.true.` only on the ELM step whose end lines up with the next radiation calculation; `rstwr` / `nlend` are only `.true.` on the final step of the coupling interval. **The `lnd_export` call has a NEW 5-argument signature** at d40b843 — `lnd2iac_vars` is the new one.
6. **Sync check.** After the loop, `get_curr_date(offset=-dtime)` must equal the EClock date or `endrun`.

## `lnd_final_mct`

Calls `elm_finalizeMod::final()`. In the current tree, `final()` only finalizes PETSc when VSFM is on.

## Import: `lnd_import` (NEW 7-arg signature)

`cpl/lnd_import_export.F90:27`:

```fortran
subroutine lnd_import( bounds, x2l, atm2lnd_vars, glc2lnd_vars, &
                       ocn2lnd_vars, lnd2atm_vars, iac2lnd_vars)
   type(bounds_type),  intent(in)    :: bounds
   real(r8),           intent(in)    :: x2l(:,:)
   type(atm2lnd_type), intent(inout) :: atm2lnd_vars
   type(glc2lnd_type), intent(inout) :: glc2lnd_vars
   type(ocn2lnd_type), intent(inout) :: ocn2lnd_vars      ! NEW
   type(lnd2atm_type), intent(in)    :: lnd2atm_vars
   type(iac2lnd_type), intent(inout) :: iac2lnd_vars      ! NEW
```

**Two new arguments:** `ocn2lnd_vars` (defined in `main/ocn2lndType.F90`) carries one-way ocean → land state when `use_ocn_lnd_one_way = .true.`; `iac2lnd_vars` (defined in `main/iac2lndMod.F90`) carries IAC (Integrated Assessment Coupling) state when `iac_present = .true.`. Both fields gate their writes on the corresponding namelist switch — for typical coupled runs without an IAM, the IAC and ocean code paths are dead but the argument still has to be passed.

The canonical coupled branch writes these scalar fields per gridcell (selected highlights from `cpl/lnd_import_export.F90:1084-1100`+ — exact line numbers may shift with cpl_bypass and metdata-bypass paths):

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

River coupling fields (`index_x2l_Flrr_*`) are also ingested. CO₂, aerosol deposition, and N/P deposition fields follow similar patterns; there are separate code paths for `co2_type='prognostic'` vs `'diagnostic'`.

When `iac_present` is true, the IAC fields are unpacked at `cpl/lnd_import_export.F90:1383-1396`:

```fortran
do num = 0, numpft
   iac2lnd_vars%frac_pft(g,num)      = x2l(index_x2l_Sz_pct_pft(num),i)
   iac2lnd_vars%frac_pft_prev(g,num) = x2l(index_x2l_Sz_pct_pft_prev(num),i)
   if (num < numharvest) then
      iac2lnd_vars%harvest_frac(g,num) = x2l(index_x2l_Sz_harvest_frac(num),i)
   end if
end do
```

The `_not_downscaled_grc` suffix is important. The raw gridcell forcing is later disaggregated to topounits and optionally downscaled by elevation (`cpl/lnd_disagg_forc.F90`, `cpl/lnd_downscale_atm_forcing.F90`). After disaggregation, `top_as` (topounit atmospheric state) and `top_af` (topounit atmospheric flux) carry the values that the physics actually consumes.

## Export: `lnd_export` (NEW 5-arg signature)

`cpl/lnd_import_export.F90:1407`:

```fortran
subroutine lnd_export( bounds, lnd2atm_vars, lnd2glc_vars, lnd2iac_vars, l2x)
   type(bounds_type),  intent(in)    :: bounds
   type(lnd2atm_type), intent(inout) :: lnd2atm_vars
   type(lnd2glc_type), intent(inout) :: lnd2glc_vars
   type(lnd2iac_type), intent(inout) :: lnd2iac_vars     ! NEW
   real(r8),           intent(out)   :: l2x(:,:)
```

The new `lnd2iac_vars` argument carries land → IAC state. When `iac_present` is true (`cpl/lnd_import_export.F90:1547-1553`):

```fortran
if (iac_present) then
   do p = 0, numpft
      l2x(index_l2x_Sl_hr(p),i)     = lnd2iac_vars%hr(g,p)
      l2x(index_l2x_Sl_npp(p),i)    = lnd2iac_vars%npp(g,p)
      l2x(index_l2x_Sl_pftwgt(p),i) = lnd2iac_vars%pftwgt(g,p)
   end do
end if
```

The core fields per gridcell are still (`cpl/lnd_import_export.F90:1447-1474`):

| Coupler field index | ELM source | Notes |
|---|---|---|
| `index_l2x_Sl_t` | `lnd2atm_vars%t_rad_grc(g)` | Effective radiative surface temp |
| `index_l2x_Sl_snowh` | `lnd2atm_vars%h2osno_grc(g)` | Snow water equivalent [mm] |
| `index_l2x_Sl_avsdr`, `_anidr` | `lnd2atm_vars%albd_grc(g,1:2)` (or `apparent_albd_grc` if `use_finetop_rad`) | Direct-beam albedo (VIS, NIR) |
| `index_l2x_Sl_avsdf`, `_anidf` | `lnd2atm_vars%albi_grc(g,1:2)` (or `apparent_albi_grc`) | Diffuse albedo (VIS, NIR) |
| `index_l2x_Sl_tref`, `_qref` | `lnd2atm_vars%t_ref2m_grc`, `q_ref2m_grc` | 2 m screen-level state |
| `index_l2x_Sl_u10`, `_u10withgusts` | `lnd2atm_vars%u_ref10m_grc`, `u_ref10m_with_gusts_grc` | 10 m wind |
| `index_l2x_Fall_taux`, `_tauy` | `-lnd2atm_vars%taux_grc`, `-tauy_grc` | Momentum flux (sign flipped) |
| `index_l2x_Fall_lat`, `_sen` | `-eflx_lh_tot_grc`, `-eflx_sh_tot_grc` | Latent, sensible heat |
| `index_l2x_Fall_lwup` | `-eflx_lwrad_out_grc` | Upward longwave |
| `index_l2x_Fall_evap` | `-qflx_evap_tot_grc` | Evaporation |
| `index_l2x_Fall_swnet` | `fsa_grc` | Net absorbed shortwave |
| `index_l2x_Fall_fco2_lnd` | `-nee_grc` (if coupled-carbon) | Land→atm CO₂ flux |
| `index_l2x_coszen_str` | `lnd2atm_vars%coszen_str(g)` | Solar zenith angle |

Optional fields gated on nonzero indices include dust fluxes, MEGAN VOC emissions, dry-deposition velocities, methane, FAN NH₃. River fields (`index_l2x_Flrl_*`) carry liquid/ice/surface/subsurface runoff to MOSART. Glacier coupling fields (`index_l2x_Sl_tsrf`, `_topo`, `index_l2x_Flgl_qice`) are written only when `create_glacier_mec_landunit` is true. `index_l2x_Flrl_inundinf` (inundation infiltration) is gated on its index being nonzero.

Everything in `l2x_l` is populated at gridcell resolution; ELM's subgrid hierarchy is collapsed in `main/lnd2atmMod::lnd2atm`, which is called inside `elm_drv` before `lnd_export` sees the data.

## `elm_drv` – the main driver loop

`main/elm_driver.F90` exposes `elm_drv(doalb, nextsw_cday, declinp1, declin, rstwr, nlend, rdate)` (`main/elm_driver.F90:207`) plus three private helpers: `elm_drv_init` (`:1600`), `elm_drv_patch2col`, and `write_diagnostic` (`:1916`). `elm_drv` parallelizes over OpenMP "clumps" obtained from `get_proc_clumps` / `get_clump_bounds` (`main/decompMod.F90`).

The high-level shape of one call, with FATES-relevant branches called out:

1. **Setup.** `get_proc_bounds`, `get_proc_clumps`, `get_nstep`, `get_step_size`, `get_curr_date`. Optional `MPI_Barrier` if `mpi_sync_nstep_freq > 0`.
2. **Phenology interpolation.** CN uses `interpMonthlyVeg` conditionally; FATES in satellite-phenology mode (`use_fates_sp`) also calls `interpMonthlyVeg`; otherwise the prescribed-biogeography path reads monthly LAI (`:286-323`).
3. **Decomposition vertical profile update** for CN or FATES (`:333-360`).
4. **Balance opening / zero-DWT entries.** `BeginGridWaterBalance`, then for `use_cn .or. use_fates`: `col_cs/ns/ps%Summary`, `BeginGridCBalance` / `BeginGridNBalance` / `BeginGridPBalance` (`:436-449`). Under FATES, `col_cs/ns/ps%ZeroForFates` runs instead of the CN summary path (`:430-432`).
5. **Fire/deposition interpolation.** `FireInterp` for CN; `alm_fates%InterpFileInputs(bounds_proc)` for FATES when `fates_spitfire_mode > scalar_lightning` (`:641-651`); `pdep_interp` runs for both (`:660-663`); FAN stream interp when `use_fan` (`:668-670`).
6. **Per-clump physics loop** (`!$OMP PARALLEL DO PRIVATE (nc,bounds_clump,...)`, `:680`). Inside each clump:
   - `UpdateDaylength` and `elm_drv_init` zero per-timestep accumulators.
   - **Optional topographic radiation effect** when `use_finetop_rad`: `topographic_effects_on_radiation(bounds_clump, atm2lnd_vars, nextsw_cday, declinp1, lnd2atm_vars)` (`:695-699`). NEW public entry on `atm2lndMod` at d40b843 — see [`atmosphere_interface.md`](atmosphere_interface.md).
   - `downscale_forcings(bounds_clump, num_do_smb_c, do_smb_c, atm2lnd_vars)` (`:701-703`).
   - `CanopyHydrology` (`:716`).
   - **Surface radiation.** If `use_fates`, `alm_fates%wrap_sunfrac(bounds_clump, top_af, canopystate_vars)` replaces `CanopySunShadeFractions` (`:737-743`). Then `SurfaceRadiation`, `UrbanRadiation`.
   - `CanopyTemperature` (`:770-774`); then `CanopyFluxes` (`:798`) does the iterative leaf energy-balance solve. `CanopyFluxes` is where FATES photosynthesis is invoked — see [`fates_interface.md`](fates_interface.md) for `prep_canopyfluxes`, `wrap_btran`, `wrap_photosynthesis`, `wrap_accumulatefluxes`, and `wrap_hydraulics_drive`.
   - `SoilFluxes`, `LakeFluxes`, `UrbanFluxes`, `LakeTemperature`, `SoilTemperature` follow.
   - `LakeHydrology`, `HydrologyNoDrainage` (`:913`), `HydrologyDrainage` complete the column water budget. `HydrologyNoDrainage` calls `alm_fates%ComputeRootSoilFlux` when FATES is active.
   - `EcosystemDynNoLeaching1` (`:1060`), the `elm_interface`/PFLOTRAN bridge (when `use_elm_interface .and. use_pflotran`) at `:1216`, then `EcosystemDynNoLeaching2` (`:1138`). Inside `EcosystemDynLeaching` (called later in this chain), the new per-step FATES carbon dispatch runs:
     ```fortran
     if (use_fates) then
        call alm_fates%wrap_FatesAtmosphericCarbonFluxes(bounds, num_soilc, filter_soilc)
        call alm_fates%wrap_FatesCarbonStocks(bounds, num_soilc, filter_soilc)
     endif
     ```
     (`biogeochem/EcosystemDynMod.F90:267-270`). NEW at api.43.
   - **Vegetation update.** For `use_cn`: `VegStructUpdate` runs on albedo timesteps. For `use_fates` (`:1304-1318`):
     ```fortran
     call alm_fates%WrapUpdateFatesRmean(nc)
     call alm_fates%wrap_update_hifrq_hist(bounds_clump, solarabs_vars)
     if (is_beg_curr_day()) then
        call alm_fates%dynamics_driv(bounds_clump, top_as, top_af, atm2lnd_vars, &
             soilstate_vars, canopystate_vars, frictionvel_vars, soil_water_retention_curve)
     end if
     ```
     **`wrap_update_hifrq_hist` now takes `solarabs_vars`** (NEW at api.43).
   - **Balance checks.** Column-level water, C, N, P, and gridcell C balance checks under `use_cn .or. use_fates` (`:1354-1373`).
   - **Albedo update.** On the first step (cold start or `fates_radiation_model='twostream'`), seed FATES with valid solar zenith data via `alm_fates%wrap_canopy_radiation(bounds_clump, surfalb_vars, nextsw_cday, declinp1)` (`:1382-1386`). Then `SurfaceAlbedo` / `UrbanAlbedo` when `doalb` (`:1388-1420`). The internal call from `SurfaceAlbedo` to `wrap_canopy_radiation` is at `biogeophys/SurfaceAlbedoMod.F90:967`. **`wrap_canopy_radiation` has a NEW 4-argument signature** at api.43.
7. **Global seed dispersal** across MPI tasks if FATES seed dispersal is active (`:1426-1428`).
8. **`lnd2atm`** (`:1438-1443`) builds the gridcell-averaged export state.
9. **`lnd2glc` update** for glacier_mec runs (`:1450-1461`).
10. **`lnd2iac` update** when `iac_present` (`:1467-1476`). NEW at d40b843 — calls `lnd2iac_vars%update_lnd2iac(bounds_clump)` per clump.
11. **Diagnostics** via `write_diagnostic` (`:1485`).
12. **Accumulators, history.** `hist_update_hbuf` then per-component `UpdateAccVars` calls. If FATES is active, `alm_fates%UpdateAccVars(bounds_proc)` runs here (`:1516-1518`).
13. **Restart write.** On the final step (`rstwr=.true.`), `restFile_write(bounds_proc, filer, ..., alm_fates, crop_vars, rdate=rdate)` (`:1573-1578`).

The driver is deliberately data-flow-oriented: everything the physics cares about is reached through a small set of module-level instances (`atm2lnd_vars`, `lnd2atm_vars`, `col_cs`/`col_cf`/..., `veg_cs`/..., `alm_fates`, `iac2lnd_vars`, `lnd2iac_vars`, `ocn2lnd_vars`) imported from `elm_instMod`. There is no dependency injection.

## What `elm_drv` does not do

- It does **not** touch the coupler attribute vectors. Those are marshalled only in `lnd_import` and `lnd_export`.
- It does **not** advance the time manager. That happens in `lnd_run_mct` after `elm_drv` returns.
- It does **not** decide when to write restart or stop; it only honors the `rstwr` / `nlend` flags passed from the coupler loop.
- It does **not** call FATES internals directly. Every FATES call is routed through a procedure on `alm_fates`.
- It does **not** re-read namelists or surface data. Those are one-shot in `initialize1` / `initialize2`.

## Key driver arguments

`elm_drv(doalb, nextsw_cday, declinp1, declin, rstwr, nlend, rdate)`:

| Argument | Type | Meaning |
|---|---|---|
| `doalb` | logical | `.true.` only on the timestep whose end aligns with the atmosphere's next radiation calculation. Controls whether surface albedo is updated. |
| `nextsw_cday` | real(r8) | Calendar day of the next shortwave calculation. Used for solar declination and (now also) passed into `alm_fates%wrap_canopy_radiation` for the FATES two-stream solver. |
| `declinp1`, `declin` | real(r8) | Solar declinations at next and current timestep. |
| `rstwr` | logical | `.true.` means "write restart before returning". |
| `nlend` | logical | `.true.` means "last step of the run". |
| `rdate` | character(32) | `YYYY-MM-DD-SSSSS` date string used for restart filenames. |

## Coupler field sources (lnd2atm / atm2lnd lineage)

The `x2l_l` / `l2x_l` attribute vectors touched by `lnd_import` / `lnd_export` come from and go to ELM state through several intermediate types:

- **`atm2lnd_vars` / `glc2lnd_vars` / `ocn2lnd_vars` / `iac2lnd_vars`** — populated by `lnd_import` from `x2l_l`, then consumed by `downscale_forcings` (which pushes values into `top_as` / `top_af` / `col_*` state inside the clump loop). The IAC and ocean instances are NEW at d40b843 and are populated only when `iac_present` / `use_ocn_lnd_one_way` are true.
- **`lnd2atm_vars` / `lnd2glc_vars` / `lnd2iac_vars`** — populated by `lnd2atm` (and `lnd2glc_vars%update_lnd2glc` / `lnd2iac_vars%update_lnd2iac`) at the end of `elm_drv` from column / patch state, then consumed by `lnd_export` to fill `l2x_l`.

## Forcing processing between coupler and physics

`lnd_import` only populates the **gridcell-level** fields of `atm2lnd_vars`. The physics operates on column- or patch-level quantities, so there are several rewriting steps inside each ELM step:

1. **Disaggregation to topounit.** `cpl/lnd_disagg_forc.F90` spreads gridcell forcing across topounits.
2. **Downscaling by elevation, slope, and aspect.** `cpl/lnd_downscale_atm_forcing.F90` and `main/atm2lndMod.F90::downscale_forcings` apply lapse-rate corrections. The new `topographic_effects_on_radiation` entry in `atm2lndMod` (called when `use_finetop_rad`) handles the topographic shortwave/longwave correction on top of `downscale_forcings`.
3. **Copy into `top_as` / `top_af`.** This is the interface every downstream module reads.

The physics modules read from `top_as%tbot(topo)`, `top_as%pbot(topo)`, `top_as%qbot(topo)`, `top_af%rain(topo)`, `top_af%snow(topo)`, `top_af%solad(topo,:)` — not from `atm2lnd_vars`. FATES-side boundary conditions in `bc_in` are filled from `top_as` / `top_af`, not `atm2lnd_vars`.

## Common entry-point failure modes

A few runtime issues always originate in `lnd_comp_mct` or `elm_driver`:

- **`ERROR elm_initializeMod: Unsupported domain_decomp_type`** — `initialize1` was called with a `domain_decomp_type` namelist value not in `{round_robin, graph_partitioning, simple, moab}`.
- **`ERROR: atmosphere model MUST send aerosols to ELM`** — `lnd_init_mct` gate. Coupler reported `atm_present=.true.` but `atm_aero=.false.`.
- **`elm dtime ... never align`** — `lnd_init_mct` at `cpl/lnd_comp_mct.F90:365`. Coupling interval isn't a multiple of the ELM timestep.
- **`ERROR: EHC not supported with MOAB yet`** — when `iac_present` is true but `HAVE_MOAB` is also defined.
- **IAC/ocean argument-count mismatches** when calling `lnd_import` / `lnd_export` from non-CIME callers — both signatures changed at d40b843.

## Related pages

- [`initialization.md`](initialization.md) — what `initialize1/2/3` do before `elm_drv` can run.
- [`fates_interface.md`](fates_interface.md) — the entire host-side FATES interface called from `elm_drv` and `CanopyFluxes`. Several wrapper signatures changed at api.43.
- [`atmosphere_interface.md`](atmosphere_interface.md) — how raw coupler forcings become topounit-level `top_as`/`top_af`, the new `topographic_effects_on_radiation` entry, and how `lnd2atm` builds the export state.
- [`time_and_decomposition.md`](time_and_decomposition.md) — `get_step_size`, `get_curr_date`, `advance_timestep`, clump/omp parallelism.
- [`history_and_restart.md`](history_and_restart.md) — `restFile_write` and `hist_update_hbuf` as called from `elm_drv`.
