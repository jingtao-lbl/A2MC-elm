---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# FATES interface (ELM side)

This page documents **how ELM calls FATES**. It covers the host-side wrapper modules in `components/elm/src/main/` and the fire-factory modules in `components/elm/src/biogeochem/`. FATES internals (ecosystem dynamics, PARTEH allocation, photosynthesis formulation, hydraulics) are out of scope and documented in the separate FATES wiki at `docs/fates-knowledge-base/fates-codebase-wiki-e85d997/`. Here we only describe what ELM does to initialize FATES, hand it boundary conditions, trigger its dynamics, and consume its outputs.

For Kougarok calibration this is the single most important page in the ELM knowledge base: every parameter handoff, every timestep call, and the spitfire-mode dispatch all live in the modules below.

## Files

| File | Role |
|---|---|
| `main/elmfates_interfaceMod.F90` | Host-side interface module. Defines `hlm_fates_interface_type` and the global instance `alm_fates`. All HLM↔FATES communication goes through procedures on this type. |
| `main/elmfates_paraminterfaceMod.F90` | FATES parameter-file reader. Implements `fates_param_reader_ctsm_impl` and the public `FatesReadPFTs` routine. |
| `main/elm_instMod.F90` | Declares `type(hlm_fates_interface_type) :: alm_fates` (main/elm_instMod.F90:130) and calls `alm_fates%init(bounds_proc)` from `elm_inst_biogeochem` (main/elm_instMod.F90:247). |
| `main/elm_initializeMod.F90` | Calls `ELMFatesGlobals1`, `FatesReadPFTs`, `ELMFatesGlobals2`, `ELMFatesTimesteps`, `alm_fates%Init2`, `alm_fates%InitAccBuffer`, `alm_fates%initAccVars`, and `alm_fates%init_coldstart` in the right order. |
| `main/elm_driver.F90` | Per-timestep dispatch into FATES via `alm_fates%InterpFileInputs`, `%wrap_sunfrac`, `%WrapUpdateFatesRmean`, `%wrap_update_hifrq_hist`, `%dynamics_driv`, `%WrapGlobalSeedDispersal`, `%UpdateAccVars`. |
| `biogeophys/CanopyFluxesMod.F90` | Calls `alm_fates%prep_canopyfluxes`, `%wrap_btran`, `%wrap_photosynthesis`, `%wrap_accumulatefluxes`, `%wrap_hydraulics_drive` inside the leaf energy-balance solver. |
| `biogeophys/SurfaceAlbedoMod.F90` | Calls `alm_fates%wrap_canopy_radiation` for the FATES two-stream canopy radiation solver. |
| `biogeophys/HydrologyNoDrainageMod.F90` | Calls `alm_fates%ComputeRootSoilFlux` (biogeophys/HydrologyNoDrainageMod.F90:235). |
| `biogeochem/EcosystemDynMod.F90` | Calls `alm_fates%UpdateLitterFluxes(bounds)` after soil BGC leaching (biogeochem/EcosystemDynMod.F90:706). |
| `biogeochem/FATESFireBase.F90` | Abstract base `fates_fire_base_type` that both fire data paths inherit from. |
| `biogeochem/FATESFireDataMod.F90` | `fates_fire_data_type` – reads lightning/population-density streams. |
| `biogeochem/FATESFireNoDataMod.F90` | `fates_fire_no_data_type` – the constant-ignition or no-fire path. |
| `biogeochem/FATESFireFactoryMod.F90` | Factory `create_fates_fire_data_method` that picks the above based on `fates_spitfire_mode`. |

## The `hlm_fates_interface_type`

Defined in `main/elmfates_interfaceMod.F90:203`:

```fortran
type, public :: hlm_fates_interface_type
   type(fates_interface_type),        allocatable :: fates (:)      ! one per OpenMP clump
   type(f2hmap_type),                 allocatable :: f2hmap(:)      ! clump → (column ↔ FATES site)
   type(fates_restart_interface_type)             :: fates_restart
   class(fates_fire_base_type), allocatable       :: fates_fire_data_method
   type(dispersal_type)                           :: fates_seed     ! MPI seed dispersal buffers
 contains
   procedure, public :: init
   procedure, public :: check_hlm_active
   procedure, public :: restart
   procedure, public :: init_coldstart
   procedure, public :: dynamics_driv
   procedure, public :: wrap_sunfrac
   procedure, public :: wrap_btran
   procedure, public :: wrap_photosynthesis
   procedure, public :: wrap_accumulatefluxes
   procedure, public :: prep_canopyfluxes
   procedure, public :: wrap_canopy_radiation
   procedure, public :: wrap_WoodProducts
   procedure, public :: wrap_update_hifrq_hist
   procedure, public :: TransferZ0mDisp
   procedure, public :: InterpFileInputs
   procedure, public :: Init2
   procedure, public :: InitAccBuffer
   procedure, public :: InitAccVars
   procedure, public :: UpdateAccVars
   procedure, public :: UpdateLitterFluxes
   procedure, private :: init_history_io
   procedure, private :: wrap_update_hlmfates_dyn
   procedure, private :: init_soil_depths
   procedure, public  :: ComputeRootSoilFlux
   procedure, public  :: wrap_hydraulics_drive
   procedure, public  :: WrapUpdateFatesRmean
   procedure, public  :: WrapGlobalSeedDispersal
   procedure, public  :: WrapUpdateFatesSeedInOut
end type hlm_fates_interface_type
```

Key design points:

- **Thread-parallel.** `fates(nc)` is one `fates_interface_type` per OpenMP clump. Each clump owns its own sites, `bc_in`, and `bc_out` vectors, so FATES can run under `!$OMP PARALLEL DO` without locking.
- **Column → site mapping.** `f2hmap(nc)%hsites(c)` returns the FATES site index for column `c` (0 if the column is not a FATES site). `f2hmap(nc)%fcolumn(s)` returns the HLM column index for FATES site `s`. This is the only way ELM and FATES state are linked.
- **Boundary conditions are static arrays.** `bc_in(s)` and `bc_out(s)` are FATES-native types (from `FatesInterfaceTypesMod`) but ELM owns the allocation (`allocate_bcin` / `allocate_bcout` from `FatesInterfaceMod`). They are filled from ELM state on the way in and read back into ELM state on the way out. There are no direct references from ELM code into FATES cohort or patch internals; everything goes through `bc_in` / `bc_out`.
- **Fire data is a polymorphic member.** `fates_fire_data_method` is an `allocatable` of the abstract class `fates_fire_base_type` (see the "Fire factory" section below).

A module-level instance `alm_fates` is declared in `main/elm_instMod.F90:130`:

```fortran
type(hlm_fates_interface_type) :: alm_fates
public :: alm_fates
```

Every FATES call in ELM goes through this single object.

## Runtime flags

Defined in `main/elm_varctl.F90:215–239` (FATES block):

| Flag | Type | Default | Meaning |
|---|---|---|---|
| `use_fates` | logical | `.false.` | Master switch. When `.true.`, CN allocation/phenology/fire are replaced by FATES equivalents. |
| `use_fates_sp` | logical | `.false.` | FATES satellite phenology. Canopy structure prescribed from an LAI stream. |
| `use_fates_fixed_biogeog` | logical | `.false.` | Fixed biogeography mode. PFT distribution is prescribed from the surface dataset. |
| `use_fates_nocomp` | logical | `.false.` | No-competition mode – PFTs placed into separate patches, no inter-PFT competition. |
| `use_fates_logging` | logical | `.false.` | FATES logging module. |
| `use_fates_planthydro` | logical | `.false.` | FATES plant hydraulics. When on, ELM also populates soil hydraulic properties in `bc_in`. |
| `use_fates_cohort_age_tracking` | logical | `.false.` | Cohort age tracking. |
| `use_fates_tree_damage` | logical | `.false.` | Tree damage module. |
| `use_fates_ed_st3` | logical | `.false.` | Static stand structure. |
| `use_fates_ed_prescribed_phys` | logical | `.false.` | Prescribed leaf physiology (bypasses the FATES photosynthesis solver). |
| `use_fates_inventory_init` | logical | `.false.` | Initialize FATES from inventory data instead of cold-start. |
| `fates_spitfire_mode` | integer | `0` | 0=no fire, 1=scalar lightning, 2=lightning-from-data, 3=successful ignitions, 4=anthro ignitions, 5=anthro suppression. Defined as parameters in `FATESFireFactoryMod` and re-declared in `ELMFatesGlobals2`. |
| `fates_parteh_mode` | integer | `-9` | PARTEH mode: 1=C-only, 2=C+N+P (`prt_cnp_flex_allom_hyp`). |
| `fates_seeddisp_cadence` | integer | `iundef` | 0=none, 1=daily, 2=monthly, 3=yearly cross-gridcell seed dispersal. |
| `fates_inventory_ctrl_filename` | char(256) | `''` | Inventory control file. |
| `fates_paramfile` | char(fname_len) | `' '` | Path to the FATES parameter NetCDF file (main/elm_varctl.F90:342). |

These flags flow through `control_init` → `elm_varctl` → the `ELMFatesGlobals*` calls below, which push each one to the FATES side via `set_fates_ctrlparms`.

## Parameter file read path

FATES has its own parameter file (typically `fates_params.nc`) separate from the ELM CN parameter file. The read path is:

1. **`ELMFatesGlobals1`** (`main/elmfates_interfaceMod.F90:283`) is called from `initialize1` before any subgrid allocation:
   - `FatesInterfaceInit(iulog, verbose_output)` – hand FATES a log unit.
   - `set_fates_ctrlparms('flush_to_unset')` – put all "receive-type" FATES control parameters in the unset state.
   - Push `use_fates_fixed_biogeog`, `use_fates_nocomp`, `use_fates_sp`, `masterproc` into FATES via `set_fates_ctrlparms`.
   - **`SetFatesGlobalElements1(use_fates, natpft_size, 0, var_reader)`** – this call has FATES read its parameter file (via the `var_reader :: fates_param_reader_ctsm_impl`) and compute `fates_maxPatchesPerSite`. ELM then assigns `natpft_size = fates_maxPatchesPerSite` so the subgrid allocator knows how many per-column patches to reserve.

2. **`FatesReadPFTs`** (`main/elmfates_paraminterfaceMod.F90:37`) is called next from `initialize1`:
   ```fortran
   allocate(fates_params)
   call fates_params%Init()
   call EDPftvarcon_inst%Init()
   call EDPftvarcon_inst%Register(fates_params)

   is_host_file = .false.
   call ParametersFromNetCDF(fates_paramfile, is_host_file, fates_params)

   is_host_file = .true.
   call ParametersFromNetCDF(paramfile, is_host_file, fates_params)

   call EDPftvarcon_inst%Receive(fates_params)
   call fates_params%Destroy()
   deallocate(fates_params)
   ```
   The two `ParametersFromNetCDF` calls are the dual-file design: FATES parameters that FATES itself defines come from `fates_paramfile` (`is_host_file=.false.`); FATES parameters that depend on HLM constants come from the ELM `paramfile` (`is_host_file=.true.`). `ParametersFromNetCDF` (`main/elmfates_paraminterfaceMod.F90:138`) walks the parameter metadata and only reads entries whose `is_host_param` flag matches the current pass.

3. **`ELMFatesGlobals2`** (`main/elmfates_interfaceMod.F90:361`) runs later in `initialize1`, after `surfrd_get_data` (and therefore after `FatesReadPFTs`). It pushes every remaining control flag into FATES via `set_fates_ctrlparms`:
   - `num_sw_bbands`, `vis_sw_index`, `nir_sw_index`, `num_lev_soil`, `hlm_name='ELM'`, `hio_ignore_val=spval`, `soilwater_ipedof`.
   - `parteh_mode = fates_parteh_mode`, `seeddisp_cadence = fates_seeddisp_cadence`.
   - `use_tree_damage`, `nu_com` (ECA/RD), `decomp_method` (CENTURY/CTC).
   - `nitrogen_spec=1`, `phosphorus_spec=1` (ELM always allocates N and P, even in supplement mode).
   - `is_restart`, `use_ch4`, `use_vertsoilc`.
   - `spitfire_mode` and the four mode constants `sf_nofire_def=0`, `sf_scalar_lightning_def=1`, `sf_successful_ignitions_def=3`, `sf_anthro_ignitions_def=4`.
   - `use_logging` (which `get_do_harvest` can override), `use_lu_harvest`, `num_lu_harvest_cats`.
   - `use_ed_st3`, `use_ed_prescribed_phys`, `use_planthydro`, `use_cohort_age_tracking`, `use_inventory_init`, `inventory_ctrl_file`.
   - Final `set_fates_ctrlparms('check_allset')` makes sure no receive-type parameter was left unset.
   - Then `SetFatesGlobalElements2(use_fates)` finalizes `fates_maxElementsPerPatch`, `num_elements`, `fates_maxElementsPerSite`.

4. **`Read` method** on `fates_param_reader_ctsm_impl` (`main/elmfates_paraminterfaceMod.F90:206`) is the callback FATES uses during `SetFatesGlobalElements1` to actually pull parameters out of `fates_paramfile`. It is a thin wrapper around `ParametersFromNetCDF(fates_paramfile, is_host_file=.false., fates_params)`.

After stage 1 returns, every FATES parameter is inside `EDPftvarcon_inst` (and FATES-internal globals) and ELM knows how many patches to allocate per column.

## Initialization sequence

Ordered calls into `alm_fates` from `main/elm_initializeMod.F90`:

| Order | Call | Source | Purpose |
|---|---|---|---|
| 1 | `ELMFatesGlobals1()` | `initialize1` at `main/elm_initializeMod.F90:140` | Read param file, set patch count. |
| 2 | `FatesReadPFTs()` | `initialize1` at `main/elm_initializeMod.F90:303` | Populate `EDPftvarcon_inst`. |
| 3 | `ELMFatesGlobals2()` | `initialize1` at `main/elm_initializeMod.F90:315` | Push remaining control flags, size element dimension. |
| 4 | `ELMFatesTimesteps()` | `initialize2` at `main/elm_initializeMod.F90:588` | Set `hlm_stepsize`, call `InitTimeAveragingGlobals`. |
| 5 | `alm_fates%init(bounds_proc)` | `elm_inst_biogeochem` → `main/elm_instMod.F90:247` (called from `initialize2`) | Build per-clump site lists, allocate `bc_in` / `bc_out`, populate `f2hmap`, initialize hydraulic sites, register FATES history variables, **create fire data method object** via `create_fates_fire_data_method`. |
| 6 | `alm_fates%InitAccBuffer(bounds_proc)` | `initialize2` at `main/elm_initializeMod.F90:719` | FATES fire accumulator buffer. |
| 7 | `alm_fates%Init2(bounds_proc, NLFilename)` | `initialize2` at `main/elm_initializeMod.F90:754` | **Only if** `fates_spitfire_mode > scalar_lightning`. Calls `fates_fire_data_method%FireInit(bounds, NLFilename)` to attach the lightning/population-density streams. |
| 8 | `alm_fates%initAccVars(bounds_proc)` | `initialize2` at `main/elm_initializeMod.F90:942` | FATES fire accumulator variables. |
| 9 | `restFile_read(..., alm_fates, ...)` | `initialize2` at `main/elm_initializeMod.F90:798, 816, 860` | Reads FATES state from the ELM restart file by routing into `alm_fates%restart(...)` (main/elmfates_interfaceMod.F90:1433). |
| 10 | `alm_fates%init_coldstart(canopystate_vars, soilstate_vars, frictionvel_vars)` | `initialize2` at `main/elm_initializeMod.F90:1020` | **Only on cold start** (`nsrest==startup .and. finidat==' ' .and. .not. is_restart()`). Runs `init_site_vars`, `zero_site`, `set_site_properties`, optional `HydrSiteColdStart`, `init_patches`, `ed_update_site`, `FluxIntoLitterPools`, and a first `wrap_update_hlmfates_dyn` so LAI/hbot/htop/displa/z0m are populated before the first radiation call. |

`alm_fates%init` (main/elmfates_interfaceMod.F90:586–829) is worth calling out. It allocates one `fates_interface_type` and one `f2hmap_type` per clump, then for each clump loops over columns and marks columns whose landunit is `istsoil` and is active as FATES sites. For each site it:

- Stores `h_gid = c` and `lat`/`lon` from the gridcell.
- Calls `allocate_bcpconst` and `set_bcpconst` to fill the constant boundary conditions (soil depths, decomposition levels, etc.).
- Calls `allocate_bcin(..., col_pp%nlevbed(c), ndecomp, num_harvest_vars, surfpft_lb, surfpft_ub)` and `allocate_bcout(..., col_pp%nlevbed(c), ndecomp)` to size the dynamic boundary buffers.
- Copies surface PFT fractions from `wt_nat_patch(g,t,:)` into `bc_in(s)%pft_areafrac(:)` (main/elmfates_interfaceMod.F90:778–787) and checks that they sum to 1 ± 1e-9.
- Calls `init_soil_depths(nc)` to populate `bc_in(s)%zi_sisl`, `dz_sisl`, etc.
- For `use_fates_planthydro`, `InitHydrSites`.

After the per-clump loop, `init_history_io(bounds_proc)` registers FATES history variables with the ELM `histFileMod`, `FatesReportParameters(masterproc)` dumps the parameter set, and `create_fates_fire_data_method(this%fates_fire_data_method)` instantiates the fire object.

## Per-timestep call sequence

FATES is touched at several points in one ELM timestep. The order follows the structure of `main/elm_driver.F90::elm_drv`.

### Outside the clump loop (processor-wide)

1. **Fire data interpolation.** `main/elm_driver.F90:635–641`:
   ```fortran
   elseif (use_fates) then
      if (fates_spitfire_mode > scalar_lightning) then
         call alm_fates%InterpFileInputs(bounds_proc)
      end if
   end if
   ```
   `InterpFileInputs` (main/elmfates_interfaceMod.F90:2763) calls `fates_fire_data_method%Interp(bounds)` when the fire data object is a `fates_fire_data_type`. For `no_fire` and `scalar_lightning` this branch is skipped entirely.

2. **P deposition interpolation.** `pdep_interp(bounds_proc, atm2lnd_vars)` runs under `use_cn .or. use_fates` (main/elm_driver.F90:651–653).

### Inside the clump loop (per OpenMP thread / chunk)

3. **Sunlit/shaded canopy fractions.** `main/elm_driver.F90:721–727`:
   ```fortran
   if (use_fates) then
      call alm_fates%wrap_sunfrac(bounds_clump, top_af, canopystate_vars)
   else
      call CanopySunShadeFractions(...)
   end if
   ```
   `wrap_sunfrac` (main/elmfates_interfaceMod.F90:1950) hands incident direct/diffuse shortwave from `top_af` into `bc_in` and calls `ED_SunShadeFracs` to compute per-patch sunlit/shaded canopy fractions that the rest of the radiation solver consumes.

4. **Canopy energy-balance solve.** `CanopyFluxes` (main/elm_driver.F90:782–786) drives the iterative leaf temperature / stomatal conductance solve. Inside `CanopyFluxes`:
   - `alm_fates%prep_canopyfluxes(bounds)` (biogeophys/CanopyFluxesMod.F90:498) flushes per-patch `filter_photo_pa` to `1` (meaning "not yet run") and zeros `qflx_transp_pa` when plant hydraulics is on.
   - `alm_fates%wrap_btran(bounds, fn, filterc_tmp(1:fn), soilstate_vars, energyflux_vars, soil_water_retention_curve)` (biogeophys/CanopyFluxesMod.F90:573) fills `bc_in(s)%smp_sl(:)` with soil matric potential for layers FATES flags as active, then calls `btran_ed` which returns per-patch `btran`, `btran2`, `rresis`, and `rootr` to ELM's `energyflux_vars` / `soilstate_vars`.
   - Inside the iterative solver, `alm_fates%wrap_photosynthesis(bounds, fn, filterp(1:fn), esat_tv, eair, oair, cair, rb, dayl_factor, atm2lnd_vars, canopystate_vars, photosyns_vars)` (biogeophys/CanopyFluxesMod.F90:880) pushes leaf-side inputs (`esat_tv`, `eair`, `oair`, `cair`, `rb`, `dayl_factor`, `t_veg`, `tgcm`, `forc_pbot`, `t_soisno_sl`) into `bc_in`, marks the patch filter as active, and calls `FatesPlantRespPhotosynthDrive`. On return, ELM writes `rssun`, `rssha` back out from `bc_out` and flags `psnsun_patch` / `psnsha_patch` as `spval` because FATES owns those now. See `main/elmfates_interfaceMod.F90:2253–2376`.
   - After the solver converges, `alm_fates%wrap_accumulatefluxes(bounds, fn, filterp(1:fn))` (biogeophys/CanopyFluxesMod.F90:1278) calls `AccumulateFluxes_ED` to accumulate photosynthetic and respiration fluxes into the cohort structures.
   - If plant hydraulics is on, `alm_fates%wrap_hydraulics_drive(bounds, fn, filterp(1:fn), soilstate_vars, ...)` (biogeophys/CanopyFluxesMod.F90:1279, wrapper at main/elmfates_interfaceMod.F90:3189) calls `hydraulics_drive`.

5. **Canopy radiation two-stream.** From `biogeophys/SurfaceAlbedoMod.F90:936`, inside the albedo calculation:
   ```fortran
   call alm_fates%wrap_canopy_radiation(bounds, ...)
   ```
   `wrap_canopy_radiation` (main/elmfates_interfaceMod.F90:2462) calls `ED_Norman_Radiation` to produce the per-patch albedo, absorbed SW, and related diagnostics that SurfaceAlbedoMod writes into `surfalb_vars`.

6. **Root-zone water flux.** `HydrologyNoDrainageMod.F90:235`:
   ```fortran
   if (use_fates) call alm_fates%ComputeRootSoilFlux(bounds, num_hydrologyc, filter_hydrologyc, ...)
   ```
   `ComputeRootSoilFlux` (main/elmfates_interfaceMod.F90:3120) diagnoses root-zone water uptake from FATES's plant-hydraulic state and writes it back into ELM's column water flux arrays.

7. **Litter fluxes.** `biogeochem/EcosystemDynMod.F90:706`:
   ```fortran
   call alm_fates%UpdateLitterFluxes(bounds)
   ```
   `UpdateLitterFluxes` (main/elmfates_interfaceMod.F90:1134) takes per-layer litter fluxes (`litt_flux_lab_c_si`, `litt_flux_cel_c_si`, `litt_flux_lig_c_si` and their N and P equivalents) out of `bc_out` and adds them to `col_cf%decomp_cpools_sourcesink`, `col_nf%decomp_npools_sourcesink`, `col_pf%decomp_ppools_sourcesink`. The N and P transfers are gated on `fates_parteh_mode == prt_cnp_flex_allom_hyp`.

8. **FATES ecosystem dynamics (daily).** `main/elm_driver.F90:1285–1300`:
   ```fortran
   if (use_fates) then
      call alm_fates%WrapUpdateFatesRmean(nc)
      call alm_fates%wrap_update_hifrq_hist(bounds_clump)
      if (is_beg_curr_day()) then
         call alm_fates%dynamics_driv(bounds_clump, top_as, top_af,    &
              atm2lnd_vars, soilstate_vars, canopystate_vars,          &
              frictionvel_vars, soil_water_retention_curve)
      end if
   end if
   ```
   `WrapUpdateFatesRmean` (main/elmfates_interfaceMod.F90:2913) pushes current canopy-air temperature into `bc_in%t_veg_pa` and updates FATES running means. `wrap_update_hifrq_hist` refreshes the FATES high-frequency history buffer every timestep. **`dynamics_driv`** (main/elmfates_interfaceMod.F90:869) runs once per ELM day and is where FATES actually advances its ecosystem state.

   Inside `dynamics_driv`:
   - Call `GetAndSetTime` so FATES's global time variables (`hlm_current_day`, etc.) match ELM's time manager.
   - For spitfire modes > `scalar_lightning`, copy 24-hour lightning density (`lnfm24`) and population density into `bc_in(s)%lightning24`, `pop_density`.
   - Per site, fill `bc_in(s)` with soil-BGC decomposition scalars (`w_scalar_sisl`, `t_scalar_sisl`), soil water (`h2o_liqvol_sl`), rooting depth, soil temperatures (`tempk_sl`), soil matric potentials (`smp_sl` using the `soil_water_retention_curve` type), 24-hour precipitation / RH / wind from `top_as`/`top_af`, harvest rates from `dynHarvestMod`, and the total site area.
   - For `use_fates_sp`, copy `hlm_sp_tlai`, `hlm_sp_tsai`, `hlm_sp_htop` from `canopystate_vars%tlai_patch`, `tsai_patch`, `htop_patch` into `bc_in`.
   - For `use_fates_planthydro`, copy soil hydraulic properties (`hksat`, `watsat`, `watres`, `sucsat`, `bsw`, `h2o_liq`).
   - Call `UnPackNutrientAquisitionBCs(this%fates(nc)%sites, this%fates(nc)%bc_in)` to transfer accumulated ELM nutrient uptake into the cohort structures.
   - If seed dispersal is enabled, `WrapUpdateFatesSeedInOut(bounds_clump)` distributes incoming seeds from neighboring gridcells.
   - Flush `fates_hist` buffers for upfreq 1 and upfreq 5.
   - **Run FATES.** For each site: `ed_ecosystem_dynamics(sites(s), bc_in(s), bc_out(s))` then `ed_update_site(sites(s), bc_in(s), bc_out(s), is_restarting=.false.)`.
   - Call `wrap_update_hlmfates_dyn(nc, bounds_clump, canopystate_vars, frictionvel_vars, .false.)` – the private method that writes FATES diagnostics back into ELM state (see below).
   - Call `fates_hist%update_history_dyn(nc, nsites, sites, bc_in)` to populate the per-day FATES history fields.

   `wrap_update_hlmfates_dyn` (main/elmfates_interfaceMod.F90:1221) is the **primary output consumer**. It reads `bc_out(s)%elai_pa`, `esai_pa`, `hbot_pa`, `tlai_pa`, `tsai_pa`, `htop_pa`, `z0m_pa`, `displa_pa`, `dleaf_pa`, `frac_veg_nosno_alb_pa`, and `canopy_fraction_pa`, and writes them into `canopystate_vars%elai_patch`, `esai_patch`, `hbot_patch`, `tlai_patch`, `tsai_patch`, `htop_patch`, `frac_veg_nosno_alb_patch`, and `frictionvel_vars%z0m_patch`, `canopystate_vars%displa_patch`, `dleaf_patch`. It also sets `veg_pp%is_veg`, `veg_pp%is_bareground`, and `veg_pp%wt_ed` to tell the rest of ELM which patches are FATES canopy cells and which is the bareground patch. Finally it updates `col_ws%total_plant_stored_h2o` when plant hydraulics is on, and an assertion `abs(areacheck - 1.0) < 1e-9` enforces that patch areas sum to 1.

9. **Global seed dispersal.** `main/elm_driver.F90:1399–1401`:
   ```fortran
   if (use_fates) then
      if (fates_seeddisp_cadence /= fates_dispersal_cadence_none) &
           call alm_fates%WrapGlobalSeedDispersal()
   end if
   ```
   MPI-reduces incoming and outgoing seeds across ranks.

10. **Accumulators.** `main/elm_driver.F90:1472–1474`:
    ```fortran
    if (use_fates) then
       call alm_fates%UpdateAccVars(bounds_proc)
    end if
    ```
    Calls `fates_fire_data_method%UpdateAccVars(bounds_proc)` to advance the fire accumulator state.

11. **Wood products.** `biogeochem/EcosystemDynMod.F90:833` calls `alm_fates%wrap_WoodProducts(bounds, num_soilc, filter_soilc)`. The wrapper (main/elmfates_interfaceMod.F90:2420) writes `col_cf%hrv_deadstemc_to_prod10c`, `hrv_deadstemc_to_prod100c`, `gpp(c)`, and `ar(c)` back into ELM column-level carbon flux state from `bc_out(s)%gpp_site * g_per_kg` and `bc_out(s)%ar_site * g_per_kg`.

12. **Restart write.** When `rstwr` is true the driver's `restFile_write` call (main/elm_driver.F90:1534) includes `alm_fates` in the argument list, routing into `alm_fates%restart(bounds_proc, ncid, flag='write', ...)`.

### Quick reference: what crosses the ELM↔FATES boundary

**Into `bc_in(s)` (ELM → FATES):**

- Soil state: `t_soisno_sl`, `h2o_liqvol_sl`, `h2osoi_liqvol` (via btran), `smp_sl`, `tempk_sl`, `w_scalar_sisl`, `t_scalar_sisl`.
- Atmosphere (per patch): `forc_pbot`, `t_veg_pa`, `tgcm_pa`, `esat_tv_pa`, `eair_pa`, `oair_pa`, `cair_pa`, `rb_pa`, `dayl_factor_pa`, `precip24_pa`, `relhumid24_pa`, `wind24_pa`.
- Fire (per patch, only in data modes): `lightning24`, `pop_density`.
- Hydraulics (when on): `hksat_sisl`, `watsat_sisl`, `watres_sisl`, `sucsat_sisl`, `bsw_sisl`, `h2o_liq_sisl`, `eff_porosity_sl`.
- Harvest (when on): `hlm_harvest_rates`, `hlm_harvest_catnames`, `hlm_harvest_units`.
- Snow state: `snow_depth_si`, `frac_sno_eff_si`.
- Site-level scalars: `site_area`, `pft_areafrac`, `max_rooting_depth_index_col`.
- Filter state for photosynthesis: `filter_photo_pa`.

**Out of `bc_out(s)` (FATES → ELM):**

- Canopy structure: `tlai_pa`, `tsai_pa`, `elai_pa`, `esai_pa`, `htop_pa`, `hbot_pa`, `canopy_fraction_pa`, `frac_veg_nosno_alb_pa`, `z0m_pa`, `displa_pa`, `dleaf_pa`.
- Photosynthesis/ET: `rssun_pa`, `rssha_pa`, `qflx_transp_pa` (through CanopyFluxes), `gpp_site`, `ar_site`.
- Litter: `litt_flux_lab_c_si`, `litt_flux_cel_c_si`, `litt_flux_lig_c_si`, and `_n_si`, `_p_si` variants (when CNP is on).
- Hydraulics: `plant_stored_h2o_si`.
- Harvest products: `hrv_deadstemc_to_prod10c`, `hrv_deadstemc_to_prod100c`.
- Soil suction activation flags: `active_suction_sl`.

The set of fields is fixed by the FATES API; anything you need to pass from ELM to FATES (or back) must already have a slot in `bc_in` / `bc_out` as defined in `external_models/fates/main/FatesInterfaceTypesMod.F90`.

## Fire factory (`biogeochem/FATESFire*`)

FATES fire integration is implemented with a strategy pattern so that the data-driven and no-data ignition models are interchangeable at runtime.

**`FATESFireBase.F90:17`** declares the abstract class:

```fortran
type, abstract, extends(fire_base_type) :: fates_fire_base_type
   contains
      procedure(GetLight24_interface),    public, deferred :: GetLight24
      procedure(GetGDP_interface),        public, deferred :: GetGDP
      procedure(InitAccBuffer_interface), public, deferred :: InitAccBuffer
      procedure(InitAccVars_interface),   public, deferred :: InitAccVars
      procedure(UpdateAccVars_interface), public, deferred :: UpdateAccVars
      procedure(need_lightning_and_popdens_interface), public, deferred :: &
                                                            need_lightning_and_popdens
end type fates_fire_base_type
```

It extends `fire_base_type` from `biogeochem/FireDataBaseType.F90`, which is the non-FATES fire base used by `FireMod.F90` for CN.

**Two concrete implementations:**

- **`FATESFireNoDataMod.F90:23`** – `fates_fire_no_data_type`. Its `need_lightning_and_popdens` returns `.false.` (`FATESFireNoDataMod.F90:55`) and both `GetLight24` and `GetGDP` call `endrun` because they should never be invoked. Used for `fates_spitfire_mode ∈ {0, 1}` (no fire / scalar lightning).

- **`FATESFireDataMod.F90:23`** – `fates_fire_data_type`. Its `need_lightning_and_popdens` returns `.true.` (`FATESFireDataMod.F90:53`), and `GetLight24` returns a pointer to an internal `lnfm24(:)` array populated from the lightning stream. `InitAccBuffer`/`InitAccVars`/`UpdateAccVars` manage the accumulator state for the lightning and population-density streams. Used for `fates_spitfire_mode ∈ {2, 3, 4, 5}`.

**`FATESFireFactoryMod.F90:38`** – `create_fates_fire_data_method` picks the right concrete class:

```fortran
subroutine create_fates_fire_data_method(fates_fire_data_method)
   ...
   current_case = fates_spitfire_mode
   select case (current_case)
   case (no_fire:scalar_lightning)
      allocate(fates_fire_no_data_type :: fates_fire_data_method)
   case (lightning_from_data:anthro_suppression)
      allocate(fates_fire_data_type :: fates_fire_data_method)
   case default
      call endrun(msg=errMsg(sourcefile, __LINE__))
   end select
end subroutine create_fates_fire_data_method
```

`FATESFireFactoryMod` also publishes the integer parameters `no_fire=0`, `scalar_lightning=1`, `lightning_from_data=2`, `successful_ignitions=3`, `anthro_ignitions=4`, `anthro_suppression=5` (`FATESFireFactoryMod.F90:25–30`), which are imported by `ELMFatesInterfaceMod` and `elm_initializeMod` so both sides agree on the mode numbering. The factory is called exactly once from `alm_fates%init` at main/elmfates_interfaceMod.F90:827:

```fortran
call create_fates_fire_data_method(this%fates_fire_data_method)
```

At runtime, `alm_fates%dynamics_driv` calls `this%fates_fire_data_method%GetLight24()` (main/elmfates_interfaceMod.F90:936) only when `fates_spitfire_mode > scalar_lightning` – so the no-data object's `endrun` branch is genuinely unreachable in practice. Similarly, `alm_fates%Init2` (main/elmfates_interfaceMod.F90:2803) only runs `fates_fire_data_method%FireInit(bounds, NLFilename)` under the same condition.

For Kougarok runs, `fates_spitfire_mode` is typically left at `0` (no fire) because arctic tundra has very low fire incidence in the validation period. The factory then instantiates `fates_fire_no_data_type` and the lightning-stream code path is effectively dead.

## How ELM and CN fire coexist

`main/elm_driver.F90:631–641` shows the dispatch:

```fortran
if (use_cn) then
   call t_startf('fireinterp')
   call FireInterp(bounds_proc)
   call t_stopf('fireinterp')
elseif (use_fates) then
   if (fates_spitfire_mode > scalar_lightning) then
      call alm_fates%InterpFileInputs(bounds_proc)
   end if
end if
```

`FireInterp` comes from `biogeochem/FireMod.F90` and drives the CN fire model through `fire_base_type` (the abstract class in `biogeochem/FireDataBaseType.F90`). When FATES is on, CN fire is bypassed entirely and FATES-spitfire is used instead. The two paths never run simultaneously – `use_cn` and `use_fates` are mutually exclusive in practice, and `EcosystemDynInit` explicitly early-returns after `AllocationInit` when FATES is on, so `FireInit` (CN) is never called in FATES runs (`biogeochem/EcosystemDynMod.F90:97–116`).

## Where to look next

- **FATES internals** – `docs/fates-knowledge-base/fates-codebase-wiki-e85d997/` (not this wiki). The FATES wiki covers `ed_ecosystem_dynamics`, `FatesPlantRespPhotosynthDrive`, `ED_Norman_Radiation`, `hydraulics_drive`, PARTEH allocation, and the cohort / patch data structures.
- **Initialization order** – [`initialization.md`](initialization.md) for the surrounding `initialize1` / `initialize2` context.
- **Driver context** – [`driver_and_coupling.md`](driver_and_coupling.md) for where in `elm_drv` each `alm_fates%*` call sits.
- **CN path** – `biogeochem/FireMod.F90`, `biogeochem/FireDataBaseType.F90`, `biogeochem/FireMethodType.F90` for the non-FATES fire model that the factory replaces.
