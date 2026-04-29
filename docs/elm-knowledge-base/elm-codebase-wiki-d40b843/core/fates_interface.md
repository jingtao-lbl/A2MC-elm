---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# FATES interface (ELM side)

This page documents **how ELM calls FATES at api.43**. It covers the host-side wrapper module in `components/elm/src/main/elmfates_interfaceMod.F90` and the fire-factory modules under `components/elm/src/biogeochem/`. FATES internals (ecosystem dynamics, PARTEH allocation, photosynthesis, hydraulics, the new two-stream radiation solver, the JSON parameter loader) are out of scope; they live in the FATES wiki.

For Kougarok calibration this is the single most important page in the ELM knowledge base: every parameter handoff, every per-timestep call, every fire/harvest/landuse switch, and the complete `bc_in`/`bc_out` boundary contract live in the modules below.

## What changed at FATES api.43 (since 60d9aad)

Five host-coupling changes are load-bearing and would break code if you wrote against the old API:

1. **`elmfates_paraminterfaceMod.F90` and `FatesReadPFTs` are gone.** FATES now reads its own parameter file. ELM's parameter-handoff path collapses from three steps to two.
2. **`alm_fates%init` takes a third argument**, `flandusepftdat` (the FATES land-use × PFT input file path).
3. **Two new public TBPs** carry per-timestep FATES carbon fluxes/stocks back to ELM column state: `wrap_FatesAtmosphericCarbonFluxes` and `wrap_FatesCarbonStocks`.
4. **Three existing wrappers gained arguments**: `wrap_canopy_radiation` (now `+ surfalb_inst, nextsw_cday, declinp1`), `wrap_update_hifrq_hist` (now `+ solarabs_inst`), and `restart` (now `+ canopystate_inst, frictionvel_inst, soilstate_inst` keyword arguments).
5. **The FATES namelist surface roughly tripled.** Ten new flags including the physics-mode selectors (`fates_radiation_model`, `fates_stomatal_model`, `fates_leafresp_model`, `fates_cstarvation_model`, `fates_regeneration_model`, `fates_hydro_solver`, `fates_electron_transport_model`, `fates_photosynth_acclimation`, `fates_stomatal_assimilation`, `fates_history_dimlevel`); LUH2/LUPFT/managed-fire/daylength-factor switches; and `fates_harvest_mode` (which replaces `use_fates_logging`, **removed**).

The fire-factory deferred-name fix is also worth noting: the per-timestep dispatch routine on `fates_fire_data_method` is `FireInterp` (from the parent `fire_base_type`), not `Interp`.

## Files

| File | Role |
|---|---|
| `main/elmfates_interfaceMod.F90` (3993 lines) | Host-side interface module. Defines `hlm_fates_interface_type` and the global instance `alm_fates`. All HLM↔FATES communication goes through procedures on this type. |
| `main/elm_instMod.F90` | Declares `type(hlm_fates_interface_type) :: alm_fates` (`elm_instMod.F90:137`) and calls `alm_fates%init(bounds_proc, flandusepftdat)` from `elm_inst_biogeochem` (`elm_instMod.F90:257`). |
| `main/elm_initializeMod.F90` | Calls `ELMFatesGlobals1`, `ELMFatesGlobals2`, `ELMFatesTimesteps`, `alm_fates%InitAccBuffer`, `alm_fates%Init2`, `alm_fates%initAccVars`, and `alm_fates%init_coldstart` in the right order. |
| `main/elm_driver.F90` | Per-timestep dispatch into FATES via `alm_fates%InterpFileInputs`, `%wrap_sunfrac`, `%WrapUpdateFatesRmean`, `%wrap_update_hifrq_hist`, `%dynamics_driv`, `%wrap_canopy_radiation`, `%WrapGlobalSeedDispersal`, `%UpdateAccVars`. |
| `biogeophys/CanopyFluxesMod.F90` | Calls `alm_fates%prep_canopyfluxes`, `%wrap_btran`, `%wrap_photosynthesis`, `%wrap_accumulatefluxes`, `%wrap_hydraulics_drive` inside the leaf energy-balance solver. |
| `biogeophys/SurfaceAlbedoMod.F90` | Calls `alm_fates%wrap_canopy_radiation` for the FATES canopy radiation solver (Norman or two-stream). |
| `biogeophys/HydrologyNoDrainageMod.F90` | Calls `alm_fates%ComputeRootSoilFlux`. |
| `biogeochem/EcosystemDynMod.F90` | Calls `alm_fates%UpdateLitterFluxes`, `%wrap_WoodProducts`, **`%wrap_FatesAtmosphericCarbonFluxes`** and **`%wrap_FatesCarbonStocks`** (lines 268-269, NEW) inside `EcosystemDynLeaching`. |
| `biogeochem/FATESFireBase.F90` | Abstract class `fates_fire_base_type`, extends `fire_base_type`. |
| `biogeochem/FATESFireDataMod.F90` | `fates_fire_data_type` – reads lightning/population-density streams. |
| `biogeochem/FATESFireNoDataMod.F90` | `fates_fire_no_data_type` – constant-ignition / no-fire path. |
| `biogeochem/FATESFireFactoryMod.F90` | Factory `create_fates_fire_data_method` that picks the above based on `fates_spitfire_mode`. |

## The `hlm_fates_interface_type`

Defined at `main/elmfates_interfaceMod.F90:233`:

```fortran
type, public :: hlm_fates_interface_type
   type(fates_interface_type), allocatable :: fates (:)        ! one per OpenMP clump
   type(f2hmap_type),          allocatable :: f2hmap(:)        ! clump → (column ↔ FATES site)
   type(fates_restart_interface_type)      :: fates_restart
   class(fates_fire_base_type), allocatable :: fates_fire_data_method
   type(dispersal_type)                    :: fates_seed       ! MPI seed dispersal buffers
 contains
   procedure, public  :: init                          ! :260
   procedure, public  :: check_hlm_active              ! :261
   procedure, public  :: restart                       ! :262
   procedure, public  :: init_coldstart                ! :263
   procedure, public  :: dynamics_driv                 ! :264
   procedure, public  :: wrap_sunfrac                  ! :265
   procedure, public  :: wrap_btran                    ! :266
   procedure, public  :: wrap_photosynthesis           ! :267
   procedure, public  :: wrap_accumulatefluxes         ! :268
   procedure, public  :: prep_canopyfluxes             ! :269
   procedure, public  :: wrap_canopy_radiation         ! :270
   procedure, public  :: wrap_WoodProducts             ! :271
   procedure, public  :: wrap_FatesAtmosphericCarbonFluxes  ! :272 NEW
   procedure, public  :: wrap_FatesCarbonStocks             ! :273 NEW
   procedure, public  :: wrap_update_hifrq_hist        ! :274
   procedure, public  :: TransferZ0mDisp               ! :275
   procedure, public  :: InterpFileInputs              ! :276
   procedure, public  :: Init2                         ! :277
   procedure, public  :: InitAccBuffer                 ! :278
   procedure, public  :: InitAccVars                   ! :279
   procedure, public  :: UpdateAccVars                 ! :280
   procedure, public  :: UpdateLitterFluxes            ! :281
   procedure, private :: init_history_io               ! :282
   procedure, private :: wrap_update_hlmfates_dyn      ! :283
   procedure, private :: init_soil_depths              ! :284
   procedure, public  :: ComputeRootSoilFlux           ! :285
   procedure, public  :: wrap_hydraulics_drive         ! :286
   procedure, public  :: WrapUpdateFatesRmean          ! :287
   procedure, public  :: WrapGlobalSeedDispersal       ! :288
   procedure, public  :: WrapUpdateFatesSeedInOut      ! :289
end type hlm_fates_interface_type
```

Key design points:

- **Thread-parallel.** `fates(nc)` is one `fates_interface_type` per OpenMP clump. Each clump owns its own sites, `bc_in`, and `bc_out` vectors, so FATES can run under `!$OMP PARALLEL DO` without locking.
- **Column → site mapping.** `f2hmap(nc)%hsites(c)` returns the FATES site index for column `c` (0 if the column is not a FATES site). `f2hmap(nc)%fcolumn(s)` returns the HLM column index for FATES site `s`. This is the only way ELM and FATES state are linked.
- **Boundary conditions live in the FATES sub-object.** `bc_in(s)` and `bc_out(s)` are FATES-native types declared in `external_models/fates/main/FatesInterfaceTypesMod.F90` and stored as `this%fates(nc)%bc_in(s)` / `bc_out(s)` (i.e., two levels into the wrapper). ELM owns the allocation through `allocate_bcin` / `allocate_bcout` / `allocate_bcpconst` from `FatesInterfaceMod`. There are no direct references from ELM into FATES cohort/patch internals; everything goes through `bc_in` / `bc_out`.
- **Fire data is a polymorphic member.** `fates_fire_data_method` is an `allocatable` of the abstract class `fates_fire_base_type` (see "Fire factory" below).

The module-level instance `alm_fates` is declared at `main/elm_instMod.F90:137`:

```fortran
type(hlm_fates_interface_type) :: alm_fates
public :: alm_fates
```

Every FATES call in ELM goes through this single object.

## Runtime flags (greatly expanded at api.43)

Defined in `main/elm_varctl.F90:223–273` (FATES block).

### Boolean switches

| Flag | Source | Default | Meaning |
|---|---|---|---|
| `use_fates` | `:227` | `.false.` | Master switch. When `.true.`, CN allocation/phenology/fire are replaced by FATES equivalents. |
| `use_fates_sp` | `:248` | `.false.` | FATES satellite phenology. Canopy structure prescribed from an LAI stream. |
| `use_fates_fixed_biogeog` | `:240` | `.false.` | Fixed biogeography mode. PFT distribution is prescribed from the surface dataset. |
| `use_fates_nocomp` | `:247` | `.false.` | No-competition mode – PFTs placed into separate patches, no inter-PFT competition. |
| `use_fates_planthydro` | `:241` | `.false.` | FATES plant hydraulics. ELM also populates soil hydraulic properties in `bc_in`. |
| `use_fates_cohort_age_tracking` | `:242` | `.false.` | Cohort age tracking. |
| `use_fates_tree_damage` | `:243` | `.false.` | Tree damage module. |
| `use_fates_ed_st3` | `:244` | `.false.` | Static stand structure. |
| `use_fates_ed_prescribed_phys` | `:245` | `.false.` | Prescribed leaf physiology (bypasses FATES photosynthesis). |
| `use_fates_inventory_init` | `:246` | `.false.` | Initialize FATES from inventory data. |
| `use_fates_managed_fire` | `:229` | `.false.` | **NEW.** Turn on managed-fire ignitions. |
| `use_fates_luh` | `:249` | `.false.` | **NEW.** Enable LUH2-based land-use transitions. |
| `use_fates_lupft` | `:250` | `.false.` | **NEW.** Enable land-use × PFT mode (paired with `flandusepftdat`). |
| `use_fates_potentialveg` | `:251` | `.false.` | **NEW.** Potential-vegetation-only mode (no LU). |
| `use_fates_daylength_factor` | `:252` | `.false.` | **NEW.** Let FATES use the host land model's daylength factor. |

**REMOVED at api.43:** `use_fates_logging` is no longer a namelist flag. Its role is taken over by `fates_harvest_mode` — `pass_logging` is derived from harvest mode at `main/elmfates_interfaceMod.F90:556-560` (any non-`no_logging` mode sets `use_logging=1` on the FATES side).

### Mode / model selectors (NEW at api.43)

These character flags pick FATES sub-models. Each is mapped to an integer code in `ELMFatesGlobals2` and pushed via `set_fates_ctrlparms`. Source: `main/elm_varctl.F90:228-239`, mapping at `main/elmfates_interfaceMod.F90:624-692`.

| Flag | Allowed values → FATES integer |
|---|---|
| `fates_radiation_model` | `'norman'` → 1, `'twostream'` → 2 |
| `fates_stomatal_model` | `'ballberry1987'` → 1, `'medlyn2011'` → 2 |
| `fates_stomatal_assimilation` | `'net'` → 1, `'gross'` → 2 |
| `fates_leafresp_model` | `'ryan1991'` → 1, `'atkin2017'` → 2 |
| `fates_cstarvation_model` | `'linear'` → 1, `'exponential'` → 2 |
| `fates_regeneration_model` | `'default'` → 1, `'trs'` → 2, `'trs_no_seed_dyn'` → 3 |
| `fates_hydro_solver` | `'1D_Taylor'` → 1, `'2D_Picard'` → 2, `'2D_Newton'` → 3 |
| `fates_electron_transport_model` | `'FvCB1980'` → 1, `'JohnsonBerry2021'` → 2 |
| `fates_photosynth_acclimation` | `'nonacclimating'` → 0, `'kumarathunge2019'` → 1 |
| `fates_harvest_mode` | five modes (see below) |

`fates_harvest_mode` (`:230`) accepts one of five strings, defined as parameters in `dynFATESLandUseChangeMod`:
`fates_harvest_no_logging`, `fates_harvest_hlmlanduse`, `fates_harvest_luh_area`, `fates_harvest_luh_mass`, plus a fifth catalog mode. The mode determines (1) whether logging is on, (2) which `bc_in` harvest fields are populated, and (3) how many harvest categories are passed. Logic at `main/elmfates_interfaceMod.F90:556-575`.

### Integer / character flags

| Flag | Source | Default | Meaning |
|---|---|---|---|
| `fates_spitfire_mode` | `:228` | `0` | 0=no fire, 1=scalar lightning, 2=lightning-from-data, 3=successful ignitions, 4=anthro ignitions, 5=anthro suppression. Mode constants are in `FATESFireFactoryMod`. |
| `fates_parteh_mode` | `:256` | `-9` | 1=C-only, 2=C+N+P (`prt_cnp_flex_allom_hyp`). |
| `fates_seeddisp_cadence` | `:259` | `iundef` | 0=none, 1=daily, 2=monthly, 3=yearly cross-gridcell seed dispersal. |
| `fates_inventory_ctrl_filename` | `:255` | `''` | Inventory control file. |
| `fates_paramfile` | `:376` | `' '` | Path to the FATES parameter NetCDF file (or JSON at api.43). |
| `fluh_timeseries` | `:253` | `''` | **NEW.** Filename for LUH2 land-use harmonization data. |
| `flandusepftdat` | `:254` | `''` | **NEW.** Filename for FATES land-use × PFT data (read inside `alm_fates%init`). |
| `fates_history_dimlevel` | `:273` | `(/2,2/)` | **NEW.** Two-element integer array. Element 1 is high-frequency history dim level; element 2 is dynamics (daily) dim level. 0=off, 1=column-level only, 2=include the 4th (size/PFT) dimension. |

These flags flow through `control_init` → `elm_varctl` → the `ELMFatesGlobals1`/`ELMFatesGlobals2` calls below, which push each one to the FATES side via `set_fates_ctrlparms`.

## Parameter file read path (api.43, two-step)

FATES has its own parameter file (`fates_paramfile`, NetCDF or JSON) separate from the ELM CN parameter file. **The host's role at api.43 is to pass the file path to FATES** and let FATES read the file itself. The dual-file `ParametersFromNetCDF(host_file)` pattern from before api.43 is gone; so are `elmfates_paraminterfaceMod.F90` and `FatesReadPFTs()`.

The new flow has two FATES "globals" calls and no separate parameter-reader step:

1. **`ELMFatesGlobals1`** (`main/elmfates_interfaceMod.F90:318`) — called from `initialize1` (`main/elm_initializeMod.F90:154`) before any subgrid allocation. It:
   - Calls `FatesInterfaceInit(iulog, verbose_output)` to hand FATES a log unit.
   - Calls `set_fates_ctrlparms('flush_to_unset')` to put all "receive-type" FATES control parameters in the unset state.
   - Pushes the **early-flag set** to FATES via `set_fates_ctrlparms`: `use_fixed_biogeog`, `use_nocomp`, `use_sp`, `use_luh2`, `masterproc`, and `parteh_mode`. (Source: `:343-379`.)
   - Calls **`SetFatesGlobalElements1(use_fates, natpft_size, 0, fates_paramfile)`** at `:397`. This is the call that hands FATES the parameter file path. FATES reads the file end-to-end on its side (via `JSONParameterUtilsMod`/`FatesReadParameters`, see FATES wiki) and computes `fates_maxPatchesPerSite`.
   - On return, ELM sets `natpft_size = fates_maxPatchesPerSite` and `max_patch_per_col = max(natpft_size, numcft, maxpatch_urb)` so the subgrid allocator knows how many per-column patches to reserve.
   - The third positional argument (number of crop PFTs) is always 0 here. The comment at `:391-396` explains: if `use_crop` is off then `natpft_size` already includes the crop PFTs tacked on; if `use_crop` is true, FATES does not handle crops anyway. Either way FATES gets 0.

2. **`ELMFatesGlobals2`** (`main/elmfates_interfaceMod.F90:407`) — called from `initialize1` at `:356`, after `surfrd_get_data`. It pushes every remaining control flag into FATES via `set_fates_ctrlparms`:
   - `num_sw_bbands=numrad`, `vis_sw_index=ivis`, `nir_sw_index=inir`, `num_lev_soil=nlevsoi`, `hlm_name='ELM'`, `hio_ignore_val=spval`, `soilwater_ipedof`, `seeddisp_cadence`.
   - `hist_hifrq_dimlevel=fates_history_dimlevel(1)`, `hist_dynam_dimlevel=fates_history_dimlevel(2)` (NEW at api.43).
   - `use_tree_damage`, `nu_com` (`'ECA'` for ECA/MIC, else `'RD'`), `decomp_method` (`'CENTURY'`/`'CTC'`).
   - `is_restart`, `use_ch4`, `use_vertsoilc`.
   - `spitfire_mode` and the four mode constants (`sf_nofire_def=0`, `sf_scalar_lightning_def=1`, `sf_successful_ignitions_def=3`, `sf_anthro_ignitions_def=4`).
   - **`use_managed_fire`** (NEW), **`use_fates_potentialveg`** (NEW), **`num_luh2_states`/`num_luh2_transitions`** (NEW from `dynFATESLandUseChangeMod` when `use_fates_luh`).
   - Harvest-mode plumbing (NEW at api.43, replaces the old `use_fates_logging`): `pass_logging` is set to 1 if `fates_harvest_mode /= fates_harvest_no_logging`; `pass_lu_harvest` and `pass_num_lu_harvest_cats` are derived from whether the mode is `fates_harvest_hlmlanduse` or one of the two `fates_harvest_luh_*` modes. Pushed as `use_lu_harvest`, `num_lu_harvest_cats`, `use_logging`. Source: `:556-576`.
   - **The new physics-mode selectors** (NEW): `radiation_model`, `electron_transport_model`, `hydr_solver`, `regeneration_model`, `mort_cstarvation_model`, `maintresp_leaf_model`, `stomatal_assim_model`, `stomatal_model`, `photosynth_acclimation`, `use_daylength_factor_switch`. Each character namelist is translated to an integer (see "Mode / model selectors" above) and pushed. Source: `:624-699`.
   - `use_ed_st3`, `use_ed_prescribed_phys`, `use_planthydro`, `use_cohort_age_tracking`, `use_inventory_init`, `inventory_ctrl_file`.
   - Final `set_fates_ctrlparms('check_allset')` to ensure no receive-type parameter was left unset.
   - Then `SetFatesGlobalElements2(use_fates)` finalizes `fates_maxElementsPerPatch`, `num_elements`, `fates_maxElementsPerSite`.

After stage 1 returns, FATES has its parameter set internally and ELM knows how many patches to allocate per column. **There is no separate `FatesReadPFTs` call anywhere in the new tree.**

## Initialization sequence (two-step, no `FatesReadPFTs`)

Ordered calls into the FATES side from `main/elm_initializeMod.F90`:

| Order | Call | Source | Purpose |
|---|---|---|---|
| 1 | `ELMFatesGlobals1()` | `initialize1` at `main/elm_initializeMod.F90:154` | Push early flags; hand FATES the parameter file path; receive `fates_maxPatchesPerSite` and set `natpft_size`. |
| 2 | `surfrd_get_data(...)` | `initialize1` at `:348` | Read surface dataset (now after `pftconrd` and the FATES parameter path handoff). |
| 3 | `ELMFatesGlobals2()` | `initialize1` at `:356` | Push the remaining control flags; size element dimension. |
| 4 | `ELMFatesTimesteps()` | `initialize2` at `:641` | Set `hlm_stepsize`, call `InitTimeAveragingGlobals`. |
| 5 | `alm_fates%init(bounds_proc, flandusepftdat)` | `elm_inst_biogeochem` → `main/elm_instMod.F90:257` (called from `initialize2` via `elm_inst_biogeochem`) | Build per-clump site lists, allocate `bc_in`/`bc_out`, populate `f2hmap`, initialize hydraulic sites, register FATES history variables, **create fire data method**. **Three-arg signature** at api.43. |
| 6 | `alm_fates%InitAccBuffer(bounds_proc)` | `initialize2` at `:774` | FATES fire accumulator buffer. |
| 7 | `alm_fates%Init2(bounds_proc, NLFilename)` | `initialize2` at `:814` | **Only if** `fates_spitfire_mode > scalar_lightning`. Calls `fates_fire_data_method%FireInit(bounds, NLFilename)` to attach the lightning/population-density streams. |
| 8 | `alm_fates%initAccVars(bounds_proc)` | `initialize2` at `:1008` | FATES fire accumulator variables. |
| 9 | `restFile_read(..., alm_fates, ...)` | `initialize2` at `:863, 881, 925` | Reads FATES state from the ELM restart file by routing into `alm_fates%restart(...)`. **NEW at api.43:** the call inside `restFile_read` passes three FATES-side keyword arguments (see "Restart" below). |
| 10 | `alm_fates%init_coldstart(canopystate_vars, soilstate_vars, frictionvel_vars)` | `initialize2` at `:1092` | **Only on cold start** (`use_fates .and. .not.is_restart() .and. finidat==' ' .and. nsrest /= nsrBranch`). Body at `main/elmfates_interfaceMod.F90:2085-2261`. Runs `init_site_vars`, `zero_site`, `set_site_properties`, optional `HydrSiteColdStart`, `init_patches`, `ed_update_site`, and a first `wrap_update_hlmfates_dyn` so LAI/hbot/htop/displa/z0m are populated before the first radiation call. |

### `alm_fates%init` (3-argument signature)

`main/elmfates_interfaceMod.F90:824`:

```fortran
subroutine init(this, bounds_proc, flandusepftdat)
   class(hlm_fates_interface_type), intent(inout) :: this
   type(bounds_type),               intent(in)    :: bounds_proc
   character(len=*),                intent(in)    :: flandusepftdat
```

Calling `alm_fates%init(bounds_proc)` with two arguments **will not compile**. The `flandusepftdat` argument carries the FATES land-use × PFT input file path; it is consumed inside `init` only when `use_fates_fixed_biogeog .and. use_fates_luh`, but it is always required syntactically.

`init` (`:824-1089`) does:

1. `param_derived%Init(numpft_fates)` (FATES parameter-derived inits).
2. If `fates_seeddisp_cadence /= fates_dispersal_cadence_none`, allocate the global seed dispersal buffer and call `DetermineGridCellNeighbors(lneighbors, this%fates_seed, numg)`.
3. Allocate `this%fates(nclumps)` and `this%f2hmap(nclumps)`.
4. If `use_fates_fixed_biogeog .and. use_fates_luh`, call `GetLandusePFTData(bounds_proc, flandusepftdat, landuse_pft_map, landuse_bareground)` to load the land-use × PFT map.
5. Per-clump (`!$OMP PARALLEL DO`):
   - Iterate columns with `(col_pp%is_soil(c) .and. col_pp%active(c))` to flag FATES sites and set `col_pp%is_fates(c) = .true.`. **Note:** at api.43 this uses the new `col_pp%is_soil(c)` flag instead of an `lun_pp%itype(l) == istsoil` test.
   - Allocate `this%fates(nc)%sites(nsites)`, `bc_in(nsites)`, `bc_out(nsites)`.
   - Call `allocate_bcpconst(bc_pconst, nlevdecomp)` and `set_bcpconst`.
   - For each site: call `allocate_bcin(bc_in(s), col_pp%nlevbed(c), ndecomp, num_harvest_vars, num_landuse_state_vars, num_landuse_transition_vars, surfpft_lb, surfpft_ub)` and `allocate_bcout(bc_out(s), col_pp%nlevbed(c), ndecomp)`. Then `zero_bcs(this%fates(nc), s)`.
   - Set `sites(s)%h_gid = c`, `sites(s)%lat`, `sites(s)%lon`.
   - If `use_fates_fixed_biogeog`: copy land-use × PFT map (when LUH on) or `wt_nat_patch(g,t,:)` into `bc_in(s)%pft_areafrac(:)`. Assert sum == 1 ± 1e-9.
   - Call `init_soil_depths(nc)` to populate `bc_in(s)%zi_sisl`, `dz_sisl`, etc.
   - For `use_fates_planthydro`, call `InitHydrSites`.
   - Set `veg_pp%is_fates(pi:pf) = .true.` for the patch slots reserved for FATES.
6. After the per-clump loop: `init_history_io(bounds_proc)` registers FATES history variables, then `create_fates_fire_data_method(this%fates_fire_data_method)` instantiates the fire object.

## Per-timestep call sequence

FATES is touched at several points in one ELM timestep. The order follows the structure of `main/elm_driver.F90::elm_drv` (entry at `:207`).

### Outside the clump loop (processor-wide)

1. **Fire data interpolation.** `main/elm_driver.F90:645-651`:
   ```fortran
   elseif (use_fates) then
      if (fates_spitfire_mode > scalar_lightning) then
         call alm_fates%InterpFileInputs(bounds_proc)
      end if
   end if
   ```
   `InterpFileInputs` (`main/elmfates_interfaceMod.F90:3180`) calls `this%fates_fire_data_method%FireInterp(bounds)` (line 3212). The deferred name on `fates_fire_base_type` is **`FireInterp`** (inherited from `fire_base_type` in `biogeochem/FireDataBaseType.F90`), not `Interp`. For `no_fire` and `scalar_lightning` this branch is skipped entirely.

2. **P deposition interpolation.** `pdep_interp(bounds_proc, atm2lnd_vars)` runs under `use_cn .or. use_fates` (`main/elm_driver.F90:660-663`).

### Inside the clump loop (per OpenMP thread)

3. **Sunlit/shaded canopy fractions.** `main/elm_driver.F90:737-743`:
   ```fortran
   if (use_fates) then
      call alm_fates%wrap_sunfrac(bounds_clump, top_af, canopystate_vars)
   else
      call CanopySunShadeFractions(...)
   end if
   ```
   `wrap_sunfrac` (`main/elmfates_interfaceMod.F90:2265`) hands incident direct/diffuse shortwave from `top_af` into `bc_in(s)%solad_parb` / `solai_parb` and calls `FatesSunShadeFracs` to compute per-patch sunlit/shaded fractions, then writes `fsun_pa`, `laisun_pa`, `laisha_pa` back into `canopystate_vars`.

4. **Canopy energy-balance solve.** `CanopyFluxes` (`main/elm_driver.F90:798`) drives the iterative leaf temperature / stomatal conductance solve. Inside `CanopyFluxes`:
   - `alm_fates%prep_canopyfluxes(bounds)` flushes per-patch `filter_photo_pa` to `1` and zeros `qflx_transp_pa` when plant hydraulics is on.
   - `alm_fates%wrap_btran(bounds, fn, filterc, soilstate_vars, energyflux_vars, soil_water_retention_curve)` (`:2388`) fills `bc_in(s)%smp_sl(:)` with soil matric potential for layers FATES flags as active, then calls `btran_ed` which returns per-patch `btran`, `rresis`, and `rootr` to ELM. (`btran2` and `rresis` are forced to `-999.9` because FATES doesn't compute them.)
   - Inside the iterative solver, `alm_fates%wrap_photosynthesis(bounds, fn, filterp, esat_tv, eair, oair, cair, rb, dayl_factor, atm2lnd_vars, canopystate_vars, photosyns_vars)` (`:2568`) pushes leaf-side inputs into `bc_in`, marks the patch filter as active, calls `FatesPlantRespPhotosynthDrive`. On return, ELM writes `rssun`, `rssha` back from `bc_out` and flags `psnsun_patch`/`psnsha_patch` as `spval` because FATES owns them.
   - After convergence, `alm_fates%wrap_accumulatefluxes(bounds, fn, filterp)` (`:2695`) calls `AccumulateFluxes_ED`.
   - If plant hydraulics is on, `alm_fates%wrap_hydraulics_drive(bounds, fn, filterp, soilstate_vars, solarabs_vars, energyflux_vars)` (`:3610`) calls `hydraulics_drive`.

5. **Per-step FATES carbon flux & stock dispatch (NEW at api.43).** Inside `EcosystemDynLeaching` (`biogeochem/EcosystemDynMod.F90:267-270`):
   ```fortran
   if (use_fates) then
      call alm_fates%wrap_FatesAtmosphericCarbonFluxes(bounds, num_soilc, filter_soilc)
      call alm_fates%wrap_FatesCarbonStocks(bounds, num_soilc, filter_soilc)
   endif
   ```
   These run **every timestep** under `use_fates`, not just on the daily FATES update. They are how per-step FATES carbon information is integrated with ELM column-level state.

   - **`wrap_FatesAtmosphericCarbonFluxes`** (body at `main/elmfates_interfaceMod.F90:2771-2816`): for each FATES column, compute `nep(c) = bc_out(s)%gpp_site*g_per_kg - bc_out(s)%ar_site*g_per_kg - hr(c)`; `nbp(c) = nep(c) - bc_out(s)%grazing_closs_to_atm_si*g_per_kg - bc_out(s)%fire_closs_to_atm_si*g_per_kg - product_closs(c)`; `nee(c) = -nbp(c)`. These are the column-level per-step C-balance components ELM exports to the atmosphere through `lnd2atm` and uses for budget checks.
   - **`wrap_FatesCarbonStocks`** (body at `:2820-2858`): `totecosysc(c) = totsomc(c) + totlitc(c) + totprodc(c) + bc_out(s)%veg_c_si + bc_out(s)%litter_cwd_c_si + bc_out(s)%seed_c_si`. This is the gridcell C inventory that ELM uses for total ecosystem carbon stock diagnostics.

6. **Canopy radiation (FATES Norman or two-stream).** From `biogeophys/SurfaceAlbedoMod.F90:967` (called from `main/elm_driver.F90:1384`):
   ```fortran
   call alm_fates%wrap_canopy_radiation(bounds_clump, surfalb_vars, nextsw_cday, declinp1)
   ```
   **NEW signature at api.43.** `wrap_canopy_radiation` (`main/elmfates_interfaceMod.F90:2862`):
   ```fortran
   subroutine wrap_canopy_radiation(this, bounds_clump, surfalb_inst, nextsw_cday, declinp1)
      type(surfalb_type), intent(inout) :: surfalb_inst
      real(r8), intent(in) :: nextsw_cday, declinp1
   ```
   Internally computes `coszen_col(c) = shr_orb_cosz(nextsw_cday, lat, lon, declinp1)` and assigns it into `bc_in(s)%coszen` (`:2894-2896`). Calls `FatesNormalizedCanopyRadiation` and writes per-patch `albd`, `albi`, `fabd`, `fabi`, `ftdd`, `ftid`, `ftii` back to `surfalb_inst`. This refactor is what supports the new `fates_radiation_model='twostream'` option.

   On the very first step of a non-restart run, `elm_drv` also calls `wrap_canopy_radiation` outside the `doalb` branch (`main/elm_driver.F90:1382-1386`) to seed FATES with valid solar zenith data, gated on either cold start or `fates_radiation_model='twostream'`.

7. **Root-zone water flux.** `biogeophys/HydrologyNoDrainageMod.F90:235`:
   ```fortran
   if (use_fates) call alm_fates%ComputeRootSoilFlux(bounds, num_hydrologyc, filter_hydrologyc, soilstate_vars)
   ```
   `ComputeRootSoilFlux` (`main/elmfates_interfaceMod.F90:3541`) writes `col_wf%qflx_rootsoi(c,1:nlevsoil) = bc_out(s)%qflx_soil2root_sisl(:)`. Skipped when `use_fates_planthydro = .false.`.

8. **Litter fluxes.** `biogeochem/EcosystemDynMod.F90:689`:
   ```fortran
   call alm_fates%UpdateLitterFluxes(bounds)
   ```
   `UpdateLitterFluxes` (`main/elmfates_interfaceMod.F90:1423`) takes per-layer litter fluxes from `bc_out` and adds them to `col_cf%decomp_cpools_sourcesink`, `col_nf%decomp_npools_sourcesink`, `col_pf%decomp_ppools_sourcesink`. The N and P transfers are gated on `fates_parteh_mode == prt_cnp_flex_allom_hyp`.

9. **FATES per-step running means and high-frequency history (every step).** `main/elm_driver.F90:1304-1313`:
   ```fortran
   if (use_fates) then
      call alm_fates%WrapUpdateFatesRmean(nc)
      call alm_fates%wrap_update_hifrq_hist(bounds_clump, solarabs_vars)
      ...
   end if
   ```
   - `WrapUpdateFatesRmean` (`:3330`) pushes current canopy-air temperature into `bc_in%t_veg_pa` and updates FATES running means (e.g., 24-hour Tveg, exponential moving averages for photosynthetic acclimation).
   - **`wrap_update_hifrq_hist`** (`:3077`) — **NEW signature at api.43.** Now takes `solarabs_inst` so it can pull `fsa_patch` directly:
     ```fortran
     subroutine wrap_update_hifrq_hist(this, bounds_clump, solarabs_inst)
        type(solarabs_type), intent(in) :: solarabs_inst
     ```
     It pushes `hr(c)`, `totsomc(c)`, `totlitc(c)` into `bc_in`; pushes per-patch `eflx_lh_tot`, `eflx_sh_tot`, `fsa_patch`, `eflx_lwrad_net`, `t_ref2m` into `bc_in%lhflux_pa`, `shflux_pa`, `swabs_pa`, `netlw_pa`, `t2m_pa`; then calls `fates_hist%update_history_hifrq` to refresh the FATES high-frequency history buffer.

10. **FATES daily ecosystem dynamics.** `main/elm_driver.F90:1314-1318`:
    ```fortran
    if (is_beg_curr_day()) then
       call alm_fates%dynamics_driv(bounds_clump, top_as, top_af, atm2lnd_vars, &
                                    soilstate_vars, canopystate_vars, &
                                    frictionvel_vars, soil_water_retention_curve)
    end if
    ```
    **`dynamics_driv`** (`main/elmfates_interfaceMod.F90:1129-1404`) runs once per ELM day and is where FATES actually advances its ecosystem state. Inside:
    - `GetAndSetTime` so FATES's `hlm_current_day` etc. match ELM.
    - For spitfire modes > `scalar_lightning`, copy 24-hour lightning density (`lnfm24`) and population density into `bc_in(s)%lightning24`, `pop_density`. For mode `anthro_suppression`, also copy GDP.
    - Per site, fill `bc_in(s)` with soil-BGC decomposition scalars (`w_scalar_sisl`, `t_scalar_sisl`), soil water (`h2o_liqvol_sl`), rooting depth, soil temperatures (`tempk_sl`), soil matric potentials (`smp_sl`), 24-hour precipitation/RH/wind from `top_as`/`top_af`.
    - For `use_fates_sp`, copy `hlm_sp_tlai`, `hlm_sp_tsai`, `hlm_sp_htop` from `canopystate_vars`.
    - For `use_fates_planthydro`, copy soil hydraulic properties.
    - **Harvest data routing** (NEW). For `fates_harvest_mode == fates_harvest_hlmlanduse`, copy `harvest_rates(:,g)` from `dynHarvestMod`. For LUH harvest modes (`fates_harvest_luh_area`, `fates_harvest_luh_mass`), copy `landuse_harvest(:,g)` from `dynFATESLandUseChangeMod`.
    - **LUH state/transition routing** (NEW). When `use_fates_luh`, copy `landuse_states(:,g)` and `landuse_transitions(:,g)` plus their varname arrays into `bc_in`.
    - Set `bc_in(s)%site_area = col_pp%wtgcell(c) * grc_pp%area(g) * m2_per_km2`.
    - Call `UnPackNutrientAquisitionBCs(sites, bc_in, nitr_suppl, phos_suppl)` to transfer accumulated ELM nutrient uptake into the cohort structures. `nitr_suppl` / `phos_suppl` are derived from `carbon_only`/`carbonnitrogen_only`/`carbonphosphorus_only`.
    - If seed dispersal is enabled, call `WrapUpdateFatesSeedInOut(bounds_clump)` to distribute incoming seeds.
    - Flush `fates_hist` buffers for `group_dyna_simple` and `group_dyna_complx`.
    - **Run FATES.** For each site: `ed_ecosystem_dynamics(sites(s), bc_in(s), bc_out(s))` then `ed_update_site(sites(s), bc_in(s), bc_out(s), is_restarting=.false.)`.
    - Call `wrap_update_hlmfates_dyn(nc, bounds_clump, canopystate_vars, frictionvel_vars, .false.)` — the private method that writes FATES diagnostics back into ELM canopy/friction state (LAI, htop, hbot, z0m, displa, dleaf, frac_veg_nosno_alb, plant_stored_h2o). Body at `:1514-1722`.
    - Call `fates_hist%update_history_dyn(nc, nsites, sites, bc_in)` to populate per-day FATES history fields.

11. **Global seed dispersal.** `main/elm_driver.F90:1426-1428`:
    ```fortran
    if (use_fates) then
       if (fates_seeddisp_cadence /= fates_dispersal_cadence_none) call alm_fates%WrapGlobalSeedDispersal()
    end if
    ```
    MPI-reduces incoming and outgoing seeds across ranks once per day.

12. **Accumulators.** `main/elm_driver.F90:1516-1518`:
    ```fortran
    if (use_fates) then
       call alm_fates%UpdateAccVars(bounds_proc)
    end if
    ```
    Calls `fates_fire_data_method%UpdateAccVars(bounds_proc)`.

13. **Wood products.** `biogeochem/EcosystemDynMod.F90:811`:
    ```fortran
    call alm_fates%wrap_WoodProducts(bounds, num_soilc, filter_soilc)
    ```
    `wrap_WoodProducts` (`main/elmfates_interfaceMod.F90:2735`) writes `col_cf%hrv_deadstemc_to_prod10c(c)` and `hrv_deadstemc_to_prod100c(c)` from `bc_out(s)%hrv_deadstemc_to_prod*c`. (Note: at api.43 this wrapper no longer also writes `gpp(c)`/`ar(c)`; those are now handled by `wrap_FatesAtmosphericCarbonFluxes`.)

14. **Restart write.** When `rstwr` is true the driver's `restFile_write` call (`main/elm_driver.F90:1573-1578`) includes `alm_fates` in the argument list, routing into `alm_fates%restart(bounds_proc, ncid, flag='write', canopystate_inst=canopystate_vars, frictionvel_inst=frictionvel_vars, soilstate_inst=soilstate_vars)`.

## Restart (3 keyword args at api.43)

`restart` (`main/elmfates_interfaceMod.F90:1726`):

```fortran
subroutine restart( this, bounds_proc, ncid, flag, &
                    canopystate_inst, frictionvel_inst, soilstate_inst )
   class(hlm_fates_interface_type), intent(inout) :: this
   type(bounds_type),               intent(in)    :: bounds_proc
   type(file_desc_t),               intent(inout) :: ncid
   character(len=*),                intent(in)    :: flag         ! 'define' | 'read' | 'write'
   type(canopystate_type),          intent(inout) :: canopystate_inst
   type(frictionvel_type),          intent(inout) :: frictionvel_inst
   type(soilstate_type),            intent(inout) :: soilstate_inst
```

The three new keyword arguments (NEW at api.43) carry the host state that the read-side post-processing needs. After the restart vectors are read in, `restart` calls:
1. `create_patchcohort_structure` and `get_restart_vectors` to rebuild the FATES linked-list state.
2. Per site, `ed_update_site(..., is_restarting=.true.)`.
3. For `use_fates_sp`, copy host LAI/TSAI/HTOP from `canopystate_inst` into `bc_in%hlm_sp_*`.
4. For `use_fates_planthydro`, repopulate hydraulic `bc_in` from `soilstate_inst` and call `RestartHydrStates`.
5. Call `wrap_update_hlmfates_dyn(nc, bounds_clump, canopystate_inst, frictionvel_inst, .true.)` to rebuild ELM-side canopy diagnostics from the just-restored FATES state.
6. Call `fates_restart%update_3dpatch_radiation` and `fates_hist%update_history_dyn`.
7. If seed dispersal is on, call `WrapGlobalSeedDispersal(is_restart_flag=.true.)`.

The call site at `main/restFileMod.F90:642-647`:

```fortran
if (use_fates) then
   call alm_fates%restart(bounds, ncid, flag='read',  &
         canopystate_inst=canopystate_vars, &
         frictionvel_inst=frictionvel_vars, &
         soilstate_inst=soilstate_vars)
end if
```

## Quick reference: what crosses the ELM↔FATES boundary

**Into `bc_in(s)` (ELM → FATES):**

- Soil state: `t_soisno_sl`, `h2o_liqvol_sl`, `h2osoi_liqvol`, `smp_sl`, `tempk_sl`, `w_scalar_sisl`, `t_scalar_sisl`, `eff_porosity_sl`, `watsat_sl`.
- Atmosphere (per patch): `forc_pbot`, `t_veg_pa`, `tgcm_pa`, `esat_tv_pa`, `eair_pa`, `oair_pa`, `cair_pa`, `rb_pa`, `dayl_factor_pa`, `precip24_pa`, `relhumid24_pa`, `wind24_pa`.
- Solar (per patch): `solad_parb`, `solai_parb`, `coszen`, `albgr_dir_rb`, `albgr_dif_rb`, `fcansno_pa`.
- High-frequency biophysics (per patch, NEW path via `wrap_update_hifrq_hist` with `solarabs_inst`): `lhflux_pa`, `shflux_pa`, `swabs_pa`, `netlw_pa`, `t2m_pa`. Site-level: `tot_het_resp`, `tot_somc`, `tot_litc`.
- Fire (per patch, only in data modes): `lightning24`, `pop_density`.
- Hydraulics (when on): `hksat_sisl`, `watsat_sisl`, `watres_sisl`, `sucsat_sisl`, `bsw_sisl`, `h2o_liq_sisl`, `eff_porosity_sl`.
- **Harvest** (NEW handling): `hlm_harvest_rates`, `hlm_harvest_catnames`, `hlm_harvest_units` — populated either from `harvest_rates` (HLM landuse mode) or `landuse_harvest` (LUH modes). Source at `:1306-1315`.
- **LUH2** (NEW): `hlm_luh_states`, `hlm_luh_state_names`, `hlm_luh_transitions`, `hlm_luh_transition_names`. Source at `:1318-1323`.
- Snow state: `snow_depth_si`, `frac_sno_eff_si`.
- Site-level scalars: `site_area`, `pft_areafrac` (or `pft_areafrac_lu` and `baregroundfrac` for LUH+fixed-biogeog), `max_rooting_depth_index_col`.
- Filter state for photosynthesis: `filter_photo_pa`.

**Out of `bc_out(s)` (FATES → ELM):**

- Canopy structure: `tlai_pa`, `tsai_pa`, `elai_pa`, `esai_pa`, `htop_pa`, `hbot_pa`, `canopy_fraction_pa`, `frac_veg_nosno_alb_pa`, `z0m_pa`, `displa_pa`, `dleaf_pa`.
- Photosynthesis/ET: `rssun_pa`, `rssha_pa`, `qflx_transp_pa` (through CanopyFluxes), `gpp_site`, `ar_site`.
- **Per-step C atmosphere fluxes** (consumed by `wrap_FatesAtmosphericCarbonFluxes` → `col_cf%nep`, `nbp`, `nee`): `gpp_site`, `ar_site`, `grazing_closs_to_atm_si`, `fire_closs_to_atm_si`.
- **Per-step C stocks** (consumed by `wrap_FatesCarbonStocks` → `col_cs%totecosysc`): `veg_c_si`, `litter_cwd_c_si`, `seed_c_si`.
- Litter: `litt_flux_lab_c_si`, `litt_flux_cel_c_si`, `litt_flux_lig_c_si`, and `_n_si`, `_p_si` variants (when CNP is on).
- Hydraulics: `plant_stored_h2o_si`, `qflx_soil2root_sisl`.
- Albedo / two-stream radiation outputs: `albd_parb`, `albi_parb`, `fabd_parb`, `fabi_parb`, `ftdd_parb`, `ftid_parb`, `ftii_parb`, `fsun_pa`, `laisun_pa`, `laisha_pa`.
- Btran: `btran_pa`, `rootr_pasl`.
- Harvest products: `hrv_deadstemc_to_prod10c`, `hrv_deadstemc_to_prod100c`.
- Soil suction activation flags: `active_suction_sl`.

The set of fields is fixed by the FATES API; anything new must already have a slot in `bc_in` / `bc_out` as defined in `external_models/fates/main/FatesInterfaceTypesMod.F90`.

## Fire factory (`biogeochem/FATESFire*`)

FATES fire integration uses a strategy pattern so the data-driven and no-data ignition models are interchangeable at runtime.

`biogeochem/FATESFireBase.F90` declares the abstract class `fates_fire_base_type` extending `fire_base_type` (from `biogeochem/FireDataBaseType.F90`). The deferred procedures are `GetLight24`, `GetGDP`, `InitAccBuffer`, `InitAccVars`, `UpdateAccVars`, and `need_lightning_and_popdens`. The base also inherits the deferred `FireInit` and `FireInterp` routines from `fire_base_type` — these are the names the `alm_fates` wrapper actually invokes.

**Two concrete implementations:**

- **`FATESFireNoDataMod.F90`** – `fates_fire_no_data_type`. `need_lightning_and_popdens` returns `.false.`. Used for `fates_spitfire_mode ∈ {0, 1}` (no fire / scalar lightning).
- **`FATESFireDataMod.F90`** – `fates_fire_data_type`. `need_lightning_and_popdens` returns `.true.`. `GetLight24` returns a pointer to the lightning-stream `lnfm24(:)` array; `GetGDP` returns the GDP / population stream. Used for `fates_spitfire_mode ∈ {2, 3, 4, 5}`.

**`FATESFireFactoryMod.F90`** – `create_fates_fire_data_method` picks the right concrete class based on `fates_spitfire_mode`. Mode constants `no_fire=0`, `scalar_lightning=1`, `lightning_from_data=2`, `successful_ignitions=3`, `anthro_ignitions=4`, `anthro_suppression=5` are exported by this module and re-imported by `ELMFatesInterfaceMod` so both sides agree on the integers.

The factory is called exactly once from `alm_fates%init` at `main/elmfates_interfaceMod.F90:1081`:

```fortran
call create_fates_fire_data_method(this%fates_fire_data_method)
```

At runtime, `alm_fates%dynamics_driv` calls `this%fates_fire_data_method%GetLight24()` and `GetGDP()` only when `fates_spitfire_mode > scalar_lightning`. `alm_fates%Init2` only runs `fates_fire_data_method%FireInit(bounds, NLFilename)` under the same condition. `alm_fates%InterpFileInputs` calls `fates_fire_data_method%FireInterp(bounds)` (note: **`FireInterp`**, not `Interp`) at `main/elmfates_interfaceMod.F90:3212`.

For Kougarok runs, `fates_spitfire_mode` is typically 0; the factory then instantiates `fates_fire_no_data_type` and the lightning-stream code path is effectively dead.

## How ELM and CN fire coexist

`main/elm_driver.F90:641-651` shows the dispatch:

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

`FireInterp` (CN) comes from `biogeochem/FireMod.F90`. When FATES is on, CN fire is bypassed and FATES-spitfire is used instead. The two paths never run simultaneously: `use_cn` and `use_fates` are mutually exclusive in practice, and `EcosystemDynInit` (`biogeochem/EcosystemDynMod.F90:79-116`) explicitly early-returns after `AllocationInit` when FATES is on, so the CN `PhenologyInit` / `FireInit` are never called in FATES runs.

## Where to look next

- **FATES internals** – `docs/fates-knowledge-base/fates-codebase-wiki-d40b843/` (sister wiki). Covers `ed_ecosystem_dynamics`, `FatesPlantRespPhotosynthDrive`, `FatesNormalizedCanopyRadiation`, `hydraulics_drive`, PARTEH allocation, the JSON parameter loader, and the cohort/patch data structures.
- **Initialization order** – [`initialization.md`](initialization.md) for the surrounding `initialize1` / `initialize2` context and the new two-step FATES init.
- **Driver context** – [`driver_and_coupling.md`](driver_and_coupling.md) for where in `elm_drv` each `alm_fates%*` call sits.
- **Namelist surface** – [`namelist_and_control.md`](namelist_and_control.md) for the full FATES namelist block and the api.43 additions.
- **CN path** – `biogeochem/FireMod.F90`, `biogeochem/FireDataBaseType.F90`, `biogeochem/FireMethodType.F90` for the non-FATES fire model that the factory replaces.
