---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Namelist, Control Flags, and Parameter File Reading

ELM runtime configuration flows from three sources: (1) the Fortran namelist file `lnd.stdin` (read by `controlMod`), (2) the CIME-generated PFT and BGC parameter NetCDF files (read by `readParamsMod` and `pftvarcon`), and (3) the surface dataset (`fsurdat`, read by `surfrdMod`). All runtime behavior ultimately traces back to flags stored in `elm_varctl`, size parameters in `elm_varpar`, physical constants in `elm_varcon`, and PFT/soil constants in `pftvarcon`/`soilorder_varcon`.

**Major change at d40b843 vs 60d9aad:** the FATES namelist surface roughly tripled in size, ten new flags appeared, and `use_fates_logging` was removed (its role taken over by `fates_harvest_mode`). The FATES parameter-reader module (`elmfates_paraminterfaceMod.F90`) is also gone, since FATES api.43 reads its own parameter file end-to-end. See §5 for the new FATES path.

## 1. The `elm_varctl` control flag module

`elm_varctl` (main/elm_varctl.F90, 701 lines) holds the master set of runtime logical, integer, and character flags. Selected non-FATES flags:

| Flag | Default | Source | Meaning |
|---|---|---|---|
| `use_cn` | `.false.` | `:388` | Carbon-nitrogen (CN/CNP) biogeochemistry active. |
| `use_crop` | `.false.` | `:390` | Prognostic crop module active. |
| `use_lch4` | `.false.` | `:383` | CH4 biogeochemistry active. |
| `use_century_decomp` | `.false.` | `:387` | CENTURY decomposition cascade instead of BGC. |
| `use_vertsoilc` | `.false.` | `:384` | Vertically-resolved soil C/N profile. |
| `use_cndv` | `.false.` | `:389` | CN-DV dynamic vegetation. |
| `use_nofire` | `.false.` | `:382` | Disable fire module. |
| `use_c13`, `use_c14` | `.false.` | `:220-221` | C isotope tracer models. |
| `use_betr` | `.false.` | `:279` | BeTR reactive transport. |
| `use_pflotran`, `use_elm_interface` | `.false.` | (later in file) | PFLOTRAN/ELM-BGC coupling path. |
| `use_vsfm` | `.false.` | (later in file) | Variably-saturated flow PETSc solver. |
| `use_top_solar_rad` | `.false.` | (later in file) | Sub-grid topographic solar. |
| `iac_present` | `.false.` | (later in file) | Integrated Assessment Coupling enabled (drives `iac2lndMod`/`lnd2iacMod`). |
| `use_ocn_lnd_one_way` | `.false.` | (later in file) | One-way ocean → land coupling (drives `ocn2lndType`). |

The `iulog` unit number (also in `elm_varctl`) is the logging unit used throughout via `write(iulog,*)`. Path/filename control variables (`paramfile`, `fsurdat`, `fatmlndfrc`, `finidat`, `fsoilordercon`, `fsnowoptics`, `fsnowaging`, `fates_paramfile`, `flandusepftdat`, `fluh_timeseries`) also live here.

### 1.1 FATES control block (greatly expanded at api.43)

Defined in `main/elm_varctl.F90:223-273`. Compared to 60d9aad, **ten new flags** appeared and `use_fates_logging` was **removed**.

#### Boolean switches

| Flag | Source | Default | Meaning |
|---|---|---|---|
| `use_fates` | `:227` | `.false.` | Master switch. |
| `use_fates_sp` | `:248` | `.false.` | Satellite phenology mode. |
| `use_fates_fixed_biogeog` | `:240` | `.false.` | Fixed biogeography. |
| `use_fates_nocomp` | `:247` | `.false.` | No-competition (per-PFT patches). |
| `use_fates_planthydro` | `:241` | `.false.` | Plant hydraulics. |
| `use_fates_cohort_age_tracking` | `:242` | `.false.` | Cohort age tracking. |
| `use_fates_tree_damage` | `:243` | `.false.` | Tree damage. |
| `use_fates_ed_st3` | `:244` | `.false.` | Static stand structure. |
| `use_fates_ed_prescribed_phys` | `:245` | `.false.` | Prescribed leaf physiology. |
| `use_fates_inventory_init` | `:246` | `.false.` | Initialize from inventory. |
| `use_fates_managed_fire` | `:229` | `.false.` | **NEW.** Managed-fire ignitions. |
| `use_fates_luh` | `:249` | `.false.` | **NEW.** LUH2 land-use transitions. |
| `use_fates_lupft` | `:250` | `.false.` | **NEW.** Land-use × PFT mode. |
| `use_fates_potentialveg` | `:251` | `.false.` | **NEW.** Potential vegetation only. |
| `use_fates_daylength_factor` | `:252` | `.false.` | **NEW.** Use HLM daylength factor. |
| ~~`use_fates_logging`~~ | — | — | **REMOVED.** Now derived from `fates_harvest_mode` at `main/elmfates_interfaceMod.F90:556-560`. |

#### Mode / model selectors (NEW at api.43)

Each character-string flag is mapped to an integer in `ELMFatesGlobals2` and pushed via `set_fates_ctrlparms`. Mapping tables at `main/elmfates_interfaceMod.F90:624-692`.

| Flag | Source | Default | Allowed values → integer |
|---|---|---|---|
| `fates_radiation_model` | `:238` | `''` | `'norman'` → 1, `'twostream'` → 2 |
| `fates_stomatal_model` | `:232` | `''` | `'ballberry1987'` → 1, `'medlyn2011'` → 2 |
| `fates_stomatal_assimilation` | `:233` | `''` | `'net'` → 1, `'gross'` → 2 |
| `fates_leafresp_model` | `:234` | `''` | `'ryan1991'` → 1, `'atkin2017'` → 2 |
| `fates_cstarvation_model` | `:235` | `''` | `'linear'` → 1, `'exponential'` → 2 |
| `fates_regeneration_model` | `:236` | `''` | `'default'` → 1, `'trs'` → 2, `'trs_no_seed_dyn'` → 3 |
| `fates_hydro_solver` | `:237` | `''` | `'1D_Taylor'` → 1, `'2D_Picard'` → 2, `'2D_Newton'` → 3 |
| `fates_electron_transport_model` | `:239` | `''` | `'FvCB1980'` → 1, `'JohnsonBerry2021'` → 2 |
| `fates_photosynth_acclimation` | `:231` | `''` | `'nonacclimating'` → 0, `'kumarathunge2019'` → 1 |
| `fates_harvest_mode` | `:230` | `''` | one of `fates_harvest_no_logging`, `fates_harvest_hlmlanduse`, `fates_harvest_luh_area`, `fates_harvest_luh_mass` (and a fifth catalog mode); strings defined in `dynFATESLandUseChangeMod`. |

The Kougarok-relevant defaults: when these character flags are blank, FATES uses its own internal defaults (typically Norman radiation, Ball-Berry stomatal, Ryan 1991 leaf respiration, linear C-starvation, default regeneration, 1D-Taylor hydraulics, FvCB1980 electron transport, no acclimation). Setting them explicitly is the new way to scan FATES sub-models in a sensitivity study.

#### Integer / character flags

| Flag | Source | Default | Meaning |
|---|---|---|---|
| `fates_spitfire_mode` | `:228` | `0` | 0=no fire, 1=scalar lightning, 2=lightning-from-data, 3=successful ignitions, 4=anthro ignitions, 5=anthro suppression. |
| `fates_parteh_mode` | `:256` | `-9` | 1=C-only, 2=C+N+P. |
| `fates_seeddisp_cadence` | `:259` | `iundef` | 0=none, 1=daily, 2=monthly, 3=yearly cross-gridcell seed dispersal. |
| `fates_inventory_ctrl_filename` | `:255` | `''` | Inventory control file. |
| `fates_paramfile` | `:376` | `' '` | Path to FATES parameter file (NetCDF or JSON). |
| `fluh_timeseries` | `:253` | `''` | **NEW.** LUH2 land-use harmonization data filename. |
| `flandusepftdat` | `:254` | `''` | **NEW.** FATES land-use × PFT data file (consumed inside `alm_fates%init`). |
| `fates_history_dimlevel` | `:273` | `(/2,2/)` | **NEW.** Two-element integer array. Element 1 = high-frequency history dim level; element 2 = dynamics (daily) dim level. 0=off, 1=column-level only, 2=include 4th (size/PFT) dim. |

## 2. Namelist read: `controlMod`

`controlMod` (main/controlMod.F90, 1402 lines) is the orchestrator that reads the `elm_inparm` and `elm_mosart` namelists from `lnd.stdin`. Key entry points:

- `control_setNL(NLFile)` — set the filename (default `'lnd.stdin'`).
- `control_init()` — read namelists, run consistency checks, broadcast flags to all ranks.
- `control_print()` — echo settings to `iulog`.

The `elm_inparm` namelist is built up via many Fortran `namelist /elm_inparm/ ...` declarations. The **FATES block** at `main/controlMod.F90:300-331` lists every FATES-related variable that can be set from the namelist:

```fortran
namelist /elm_inparm/ fates_paramfile, use_fates,   &
      fates_spitfire_mode,                          &
      fates_harvest_mode,                           &
      use_fates_planthydro,                         &
      use_fates_ed_st3,                             &
      use_fates_cohort_age_tracking,                &
      use_fates_ed_prescribed_phys,                 &
      use_fates_inventory_init,                     &
      fates_inventory_ctrl_filename,                &
      use_fates_fixed_biogeog,                      &
      use_fates_nocomp,                             &
      use_fates_sp,                                 &
      use_fates_luh,                                &
      use_fates_lupft,                              &
      use_fates_potentialveg,                       &
      use_fates_managed_fire,                       &
      fluh_timeseries,                              &
      flandusepftdat,                               &
      fates_parteh_mode,                            &
      fates_seeddisp_cadence,                       &
      use_fates_tree_damage,                        &
      use_fates_daylength_factor,                   &
      fates_photosynth_acclimation,                 &
      fates_stomatal_model,                         &
      fates_stomatal_assimilation,                  &
      fates_leafresp_model,                         &
      fates_cstarvation_model,                      &
      fates_regeneration_model,                     &
      fates_hydro_solver,                           &
      fates_radiation_model,                        &
      fates_electron_transport_model,               &
      fates_history_dimlevel
```

Compared to 60d9aad: `use_fates_logging` is no longer in the block; ten new entries appeared (the `use_fates_managed_fire`, `use_fates_luh`, `use_fates_lupft`, `use_fates_potentialveg`, `use_fates_daylength_factor`, `fluh_timeseries`, `flandusepftdat` switches plus the eight `fates_*_model`/`fates_*_solver`/`fates_*_acclimation`/`fates_history_dimlevel` selectors).

Other namelist groups in `elm_inparm` cover time step (`dtime`), file paths (`fsurdat`, `finidat`, `paramfile`, `fatmlndfrc`, `fsoilordercon`), history/restart options (`hist_*`), CN/CNP options (`suplnitro`, `suplphos`, `nu_com`, `spinup_state`, `nyears_ad_carbon_only`, `spinup_mortality_factor`), nitrification flags (`no_frozen_nitrif_denitrif`), experimental manipulations (`add_temperature`, `add_co2`, `startdate_add_*`), glacier_mec (`maxpatch_glcmec`, `glc_smb`, `glc_do_dynglacier`), decomposition parameters, and all `use_*` feature flags.

Only `masterproc` opens and reads the file via `find_nlgroup_name` (`utils/elm_nlUtilsMod.F90:41`). After reading, a large block of consistency checks runs — for example: `use_fates` is incompatible with `use_cn`, `use_crop`, `use_c13/c14`, `use_lai_streams`, and `use_var_soil_thick`; `use_crop` forces `create_crop_landunit=.true.`; `use_lch4 .and. use_vertsoilc` flips `anoxia` to true.

After consistency checks, every setting is broadcast to other MPI ranks with a long sequence of `mpi_bcast` calls. Separately-read namelists include `finidat_consistency_checks` (`main/restFileMod.F90`), `ndepdyn_nml` (`main/ndepStreamMod.F90`), `fan_nml` (`main/fanStreamMod.F90`), and the PFLOTRAN/BeTR namelists called via `elm_pf_readnl` and `betr_readNL`.

## 3. Size parameters: `elm_varpar`

`elm_varpar` (main/elm_varpar.F90) holds array-size and index parameters. Some are `parameter` constants; others are set dynamically in `elm_varpar_init()` based on `use_crop`, `use_vertsoilc`, `use_extralakelayers`, `use_century_decomp`, and `more_vertlayers`:

- `mxpft = 50`, `numveg = 16`, `nsoilorder = 15`.
- `nlevsoi`, `nlevgrnd`, `nlevurb`, `nlevlak`, `nlevsno`, `nlevdecomp`, `nlevdecomp_full` — all dynamic. Defaults: `nlevsoi=10`, `nlevgrnd=15`, `nlevsno=5`, `nlevurb=5`, `nlevlak=10`. `more_vertlayers = .true.` switches to `nlevsoi=23`, `nlevgrnd=30`.
- `use_vertsoilc`: `nlevdecomp = nlevsoi`, else `1`.
- `use_century_decomp`: `ndecomp_pools = 7`, `ndecomp_cascade_transitions = 10`; default BGC has `ndecomp_pools = 8`.
- `natpft_lb/ub/size`, `cft_lb/ub/size`, `surfpft_lb/ub/size` define patch-array bounds on each landunit. These can be **reset by FATES** in `ELMFatesGlobals1` (which sets `natpft_size = fates_maxPatchesPerSite`).

## 4. Physical constants: `elm_varcon`

`elm_varcon` (main/elm_varcon.F90) exposes physical and tuning constants. Most are aliased from `shr_const_mod`: `grav`, `sb` (Stefan-Boltzmann), `vkc` (von Karman), `rwat`/`rair`, `cpliq`, `hvap`/`hsub`/`hfus`, `denh2o`/`denice`, `tfrz = SHR_CONST_TKFRZ`. ELM-specific tuning constants include `zlnd = 0.01`, `zsno = 0.0024`, `csoilc = 0.004`, `cnfac = 0.5`, `pondmx`, `thk_bedrock = 3.0`, and isotope ratios `c13ratio`, `c14ratio`. The public parameter `spval = 1.e36_r8` is the float-missing sentinel; `ispval = -9999` is the integer equivalent. Subgrid-type string names `grlnd`, `nameg`, `namet`, `namel`, `namec`, `namep`, `nameCohort` are declared here and used as tags throughout history/restart and gsmap lookups.

## 5. Parameter file read path

ELM reads its own parameter values from NetCDF files separately from FATES.

### 5.1 ELM parameter files (unchanged)

- `paramfile` — main ELM parameter file (PFT-physiology + shared/BGC). Read by `pftvarcon::pftconrd` and by `readParamsMod`.
- `fsoilordercon` — soil-order constants. Read by `soilorder_varcon::soilorder_conrd`.

```
controlMod reads namelist (paramfile, fsoilordercon, fates_paramfile, ...)
        |
        v
readParamsMod::readSharedParameters  -> CNParamsSharedReadFile
        |
        v
readParamsMod::readPrivateParameters -> opens paramfile and dispatches to:
        |   AllocationMod::readCNAllocParams
        |   SoilLittDecompMod::readSoilLittDecompParams
        |   DecompCascadeBGCMod::readDecompBGCParams       (if use_century_decomp)
        |   DecompCascadeCNMod::readDecompCNParams         (else)
        |   NitrifDenitrifMod::readNitrifDenitrifParams
        |   SoilLittVertTranspMod::readSoilLittVertTranspParams
        |   CH4Mod::readCH4Params                          (if use_lch4)
        |   NitrogenDynamicsMod::readNitrogenDynamicsParams
        |   PhenologyMod::readPhenolParams                 (if use_cn)
        |   MaintenanceRespMod::readMaintenanceRespParams  (if use_cn)
        |   GapMortalityMod::readGapMortParams             (if use_cn)
        v
pftvarcon::pftconrd          (PFT physiology: dleaf, slatop, leafcn, etc.)
        |
        v
soilorder_varcon::soilorder_conrd   (smax, ks_sorption, r_weather, ...)
```

`pftconrd` defines an `expected_pftnames(0:mxpft)` list and compares the file's `pftname` index-by-index; a mismatch is fatal. After matching, it assigns short integer aliases (`ndllf_evr_tmp_tree`, `nbrdlf_evr_shrub`, `nc3_arctic_grass`, etc.) for use elsewhere.

`soilorder_conrd` reads the soil-order parameter file. The expected soil-order list is: Water, Andisols, Gelisols, Histosols, Entisols, Inceptisols, Aridsols, Vertisols, Mollisols, Alfisols, Spodosols, Ultisols, Oxisols, Shifting_sand, rock_land, Ice_Glacier. Allocated arrays include `smax`, `ks_sorption`, `r_weather`, `r_adsorp`, `r_desorp`, `r_occlude`, and four biochemistry rate constants — these drive the ECA phosphorus cycle in CNP mode.

### 5.2 FATES parameter file (NEW path at api.43)

At api.43 **FATES reads its own parameter file**. The host's role is just to pass the file path and call the two FATES "globals" routines.

Old (60d9aad, no longer present):
- `main/elmfates_paraminterfaceMod.F90` (the `fates_param_reader_ctsm_impl` class, `FatesReadPFTs`, `ParametersFromNetCDF` with the dual-file `is_host_file=.true./.false.` pattern).
- A separate `FatesReadPFTs()` call from `initialize1`.

New (d40b843):
- `ELMFatesGlobals1` (`main/elmfates_interfaceMod.F90:318`, called from `initialize1` at `:154`) calls `SetFatesGlobalElements1(use_fates, natpft_size, 0, fates_paramfile)` at `:397`. The fourth argument is the file path; FATES uses its own `JSONParameterUtilsMod`/`FatesReadParameters` to ingest the file, NetCDF or JSON.
- `ELMFatesGlobals2` (`main/elmfates_interfaceMod.F90:407`, called from `initialize1` at `:356`) does the rest of the control-flag handoff and finalizes the element dimension via `SetFatesGlobalElements2(use_fates)`.

The init-order collapse from three steps to two (the `FatesReadPFTs` step is gone) is the main user-visible effect. See [`fates_interface.md`](fates_interface.md) for the full sequence.

## 6. Surface dataset: `surfrdMod`

`surfrdMod` reads the surface dataset (`fsurdat`), which defines grid geometry, land mask, subgrid weights for landunits and patches, glacier elevation classes, and fertilizer amounts. Public entry points:

- `surfrd_get_globmask(filename, mask, ni, nj)` — reads the global land mask before decomposition.
- `surfrd_get_grid(begg, endg, ldomain, filename, glcfilename)` — reads grid/landfrac into `ldomain` after decomposition.
- `surfrd_get_topo(domain, filename)` — reads grid topography.
- `surfrd_get_topo_for_solar_rad(domain, filename)` — reads slope/aspect parameters when `use_top_solar_rad` is on.
- `surfrd_get_data(begg, endg, ldomain, lfsurdat)` — main subgrid-weight reader.
- `surfrd_topounit_data(begg, endg, lfsurdat)` — topounit physical properties.
- `surfrd_finetop_data(ldomain, fsurdat)` — fineTOP radiation parameters.
- `surfrd_get_grid_conn(...)` — grid connectivity (lateral flow).

`surfrd_get_data` opens the file, validates `PFTDATA_MASK`, detects whether the file is a domain-type (`xc`/`yc`) or LNDGRID-type (`LONGXY`/`LATIXY`) file, then dispatches `surfrd_special` (for ice/lake/wetland/urban/glacier_mec) and `surfrd_veg_all`/`surfrd_pftformat`/`surfrd_cftformat`/`surfrd_fates_nocropmod` (for the vegetated landunit).

Subgrid weights are stored in `elm_varsur` pointers: `wt_lunit(:,:,:)`, `wt_nat_patch(:,:,:)`, `wt_cft(:,:,:)`, `wt_glc_mec(:,:,:)`, `fert_cft(:,:,:)`, `fert_p_cft(:,:,:)`. Indexed by `(gridcell, topounit, patch_or_landunit)`.

## 7. Auxiliary file readers

- `organicFileMod::organicrd(organic)` reads the organic-matter density (`kg/m3`) field from `fsurdat`.
- `ndepStreamMod::ndep_init(bounds, NLFilename)` reads the `ndepdyn_nml` namelist and initializes a `shr_strdata_type` stream for interpolated N deposition. `ndep_interp` performs the temporal interpolation each time step.
- `pdepStreamMod` mirrors `ndepStreamMod` for phosphorus deposition.
- `fanStreamMod::fanstream_init(bounds, NLFilename)` reads `fan_nml` and sets up five streams (`sdat_past`, `sdat_mix`, `sdat_urea`, `sdat_nitr`, `sdat_soilph`) for the FAN manure-nitrogen pipeline.
- `dynFATESLandUseChangeMod::dynFatesLandUseInit(bounds, fluh_timeseries)` (NEW path at api.43) sets up the LUH2 land-use stream when `use_fates_luh = .true.`. Called from `initialize2` at `main/elm_initializeMod.F90:794`.

All stream modules use `shr_strdata_mod` from the share code.

## 8. Cross-references

- `controlMod` consistency checks rely on `elm_varpar` for `maxpatch_glcmec`, `nlevdecomp_full`, `nsoilorder`.
- `surfrdMod` consumes `nlevsoifl`, `numpft`, `numcft` from `elm_varpar` and `numurbl` from `landunit_varcon`.
- `histFileMod` imports `max_tapes`, `max_namlen`, and all `hist_*` namelist vars from `elm_varctl` via the `namelist /elm_inparm/` declarations in `controlMod`.
- `readParamsMod` is called from `elm_initializeMod` after `controlMod` runs and after `elm_varpar_init` has established dimensions.
- `dynFATESLandUseChangeMod` exports `landuse_states`, `landuse_transitions`, `landuse_harvest`, the matching varname arrays, and the `fates_harvest_no_logging`/`fates_harvest_hlmlanduse`/`fates_harvest_luh_area`/`fates_harvest_luh_mass` parameter strings used by `controlMod` and `elmfates_interfaceMod`.
