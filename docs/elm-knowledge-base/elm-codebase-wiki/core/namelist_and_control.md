---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Namelist, Control Flags, and Parameter File Reading

ELM runtime configuration flows from three sources: (1) the Fortran namelist file `lnd.stdin` (read by `controlMod`), (2) the CIME-generated PFT and BGC parameter NetCDF files (read by `readParamsMod` and `pftvarcon`), and (3) the surface dataset (`fsurdat`, read by `surfrdMod`). All runtime behavior ultimately traces back to flags stored in `elm_varctl`, size parameters in `elm_varpar`, physical constants in `elm_varcon`, and PFT/soil constants in `pftvarcon`/`soilorder_varcon`.

## 1. The `elm_varctl` control flag module

`elm_varctl` (main/elm_varctl.F90) holds the master set of runtime logical, integer, and character flags used throughout ELM. Flags are declared with sensible defaults and later overridden by the namelist read in `controlMod`. Selected flags (file:line references):

| Flag | Default | Meaning |
|---|---|---|
| `use_cn` | `.false.` | Carbon-nitrogen (CN/CNP) biogeochemistry active (main/elm_varctl.F90:354). |
| `use_fates` | `.false.` | FATES vegetation demography active (main/elm_varctl.F90:222). |
| `use_crop` | `.false.` | Prognostic crop module active (main/elm_varctl.F90:356). |
| `use_lch4` | `.false.` | CH4 biogeochemistry active (main/elm_varctl.F90:349). |
| `use_century_decomp` | `.false.` | CENTURY decomposition cascade instead of BGC (main/elm_varctl.F90:353). |
| `use_vertsoilc` | `.false.` | Vertically-resolved soil C/N profile (main/elm_varctl.F90:350). |
| `use_cndv` | `.false.` | CN-DV dynamic vegetation (main/elm_varctl.F90:355). |
| `use_nofire` | `.false.` | Disable fire module (main/elm_varctl.F90:348). |
| `use_c13`, `use_c14` | `.false.` | C isotope tracer models (main/elm_varctl.F90:215-216). |
| `use_fan` | `.false.` | FAN manure-N model (main/elm_varctl.F90:372). |
| `use_snicar_ad`, `use_snicar_frc` | `.false.` | SNICAR snow aerosol/radiation (main/elm_varctl.F90:357-358). |
| `use_hydrstress` | `.false.` | Plant hydraulic stress (main/elm_varctl.F90:257). |
| `use_dynroot` | `.false.` | Dynamic rooting depth (main/elm_varctl.F90:265). |
| `use_betr` | `.false.` | BeTR reactive transport (main/elm_varctl.F90:245). |
| `use_pflotran`, `use_elm_interface`, `use_elm_bgc` | `.false.` | PFLOTRAN/ELM-BGC coupling path (main/elm_varctl.F90:452-454). |
| `use_fates_sp` | `.false.` | FATES satellite phenology mode (main/elm_varctl.F90:233). |
| `use_fates_nocomp` | `.false.` | FATES no-competition (per-PFT patches) mode (main/elm_varctl.F90:232). |
| `use_vsfm` | `.false.` | Variably-saturated flow PETSc solver (main/elm_varctl.F90:382). |
| `use_top_solar_rad` | `.false.` | Sub-grid topographic solar (main/elm_varctl.F90:367). |

The `iulog` unit number (also in `elm_varctl`) is the logging file unit used by every module via `write(iulog,*)`. Path/filename control variables (`paramfile`, `fsurdat`, `fatmlndfrc`, `finidat`, `fsoilordercon`, `fsnowoptics`, `fsnowaging`, `fates_paramfile`) also live here and are populated from namelist.

`use_nitrif_denitrif` appears in OpenACC `copyin` directives (main/elm_varctl.F90:490) but is not declared in `elm_varctl` itself — its declaration lives in the BGC code path that the directive imports. It is not a user-facing namelist flag; nitrification/denitrification activation follows `use_cn` and the decomposition cascade choice.

## 2. Namelist read: `controlMod`

`controlMod` (main/controlMod.F90) is the orchestrator that reads the `elm_inparm` and `elm_mosart` namelists from `lnd.stdin`. Key entry points:

- `control_setNL(NLFile)` — set the filename (default `'lnd.stdin'`; main/controlMod.F90:81-110).
- `control_init()` — read namelists, run consistency checks, broadcast flags to all ranks (main/controlMod.F90:113).
- `control_print()` — echo settings to `iulog`.

The `elm_inparm` namelist is built up via many Fortran `namelist /elm_inparm/ ...` declarations (main/controlMod.F90:142-329) covering: time step (`dtime`), file paths (`fsurdat`, `finidat`, `paramfile`, `fatmlndfrc`, `fsoilordercon`), history/restart options (`hist_*`), CN/CNP options (`suplnitro`, `suplphos`, `nu_com`, `spinup_state`, `nyears_ad_carbon_only`, `spinup_mortality_factor`), FATES options (`use_fates`, `fates_parteh_mode`, `fates_spitfire_mode`, `fates_inventory_ctrl_filename`, etc.), nitrification flags (`no_frozen_nitrif_denitrif`), experimental manipulations (`add_temperature`, `add_co2`, `startdate_add_*`), glacier_mec (`maxpatch_glcmec`, `glc_smb`, `glc_do_dynglacier`), decomposition parameters (`som_adv_flux`, `max_depth_cryoturb`, `exponential_rooting_profile`), and all `use_*` feature flags.

Only `masterproc` opens and reads the file (main/controlMod.F90:354-388) via `shr_nl_find_group_name` (wrapper around `find_nlgroup_name` in `utils/elm_nlUtilsMod.F90:41`). After reading, a large block of consistency checks runs (main/controlMod.F90:390-550) — for example: `use_fates` is incompatible with `use_cn`, `use_crop`, `use_c13/c14`, `use_lai_streams`, and `use_var_soil_thick`; `use_crop` forces `create_crop_landunit=.true.`; and `use_lch4 .and. use_vertsoilc` flips `anoxia` to true.

After the consistency checks, every setting is broadcast to the other MPI ranks with a long sequence of `mpi_bcast` calls (main/controlMod.F90:740-940). Separately-read namelists include `finidat_consistency_checks` (main/restFileMod.F90:1252), `ndepdyn_nml` (main/ndepStreamMod.F90:73), `fan_nml` (main/fanStreamMod.F90:76), and the PFLOTRAN/BeTR namelists called via `elm_pf_readnl` and `betr_readNL` (main/controlMod.F90:122-123).

`find_nlgroup_name` (utils/elm_nlUtilsMod.F90:41-112) reads the file line by line, looks for a leading `&<groupname>`, and on match backspaces the unit so the caller can `read(unit, nml=groupname)`. It returns status `-1` on miss.

## 3. Size parameters: `elm_varpar`

`elm_varpar` (main/elm_varpar.F90) holds array-size and index parameters. Parameters are either `parameter` constants or are set dynamically in `elm_varpar_init()` (main/elm_varpar.F90:128) based on `use_crop`, `use_vertsoilc`, `use_extralakelayers`, `use_century_decomp`, and `more_vertlayers`:

- `mxpft = 50`, `numveg = 16`, `nsoilorder = 15` (main/elm_varpar.F90:51-66).
- `nlevsoi`, `nlevgrnd`, `nlevurb`, `nlevlak`, `nlevsno`, `nlevdecomp`, `nlevdecomp_full` — all dynamic (main/elm_varpar.F90:190-245).
- Default: `nlevsoi=10`, `nlevgrnd=15`, `nlevsno=5`, `nlevurb=5`, `nlevlak=10`.
- `more_vertlayers = .true.` changes them to `nlevsoi=23`, `nlevgrnd=30` (main/elm_varpar.F90:192-197).
- `use_vertsoilc`: `nlevdecomp = nlevsoi`, else `1` (main/elm_varpar.F90:212).
- `use_century_decomp`: `ndecomp_pools = 7`, `ndecomp_cascade_transitions = 10`; default BGC has `ndecomp_pools = 8` (main/elm_varpar.F90:231-244).
- `natpft_lb/ub/size`, `cft_lb/ub/size`, `surfpft_lb/ub/size` define patch-array bounds on each landunit (main/elm_varpar.F90:82-95). These are reset by `update_pft_array_bounds()` (main/elm_varpar.F90:111) and potentially overwritten by FATES after the base init.

## 4. Physical constants: `elm_varcon`

`elm_varcon` (main/elm_varcon.F90) exposes physical and tuning constants. Most are aliased from `shr_const_mod`: gravity `grav`, Stefan-Boltzmann `sb`, von Karman `vkc`, gas constants `rwat`/`rair`, water specific heat `cpliq`, latent heats `hvap`/`hsub`/`hfus`, densities `denh2o`/`denice`, freezing point `tfrz = SHR_CONST_TKFRZ` (main/elm_varcon.F90:46-64). It also holds ELM tuning constants such as `zlnd = 0.01` (soil roughness), `zsno = 0.0024` (snow roughness), `csoilc = 0.004`, `cnfac = 0.5` (Crank-Nicholson factor), `pondmx`, `thk_bedrock = 3.0`, and the isotope ratios `c13ratio`, `c14ratio` (main/elm_varcon.F90:85-124). The public parameter `spval = 1.e36_r8` is the float-missing sentinel used throughout history output, and `ispval = -9999` is the integer equivalent (main/elm_varcon.F90:79-80). Subgrid-type string names `grlnd`, `nameg`, `namet`, `namel`, `namec`, `namep`, `nameCohort` are declared here and used as tags throughout history/restart and gsmap lookups. `elm_varcon_init()` fills in level-arrays (e.g., `dzsoi_decomp`) once `nlevgrnd` is known.

## 5. Parameter file read path

ELM reads parameter values from NetCDF CDL files. Two separate files are used:

- `paramfile` — the main ELM parameter file (PFT-physiology + shared/BGC parameters). Read by `pftconrd` in `pftvarcon.F90:320` and by `readParamsMod.F90`.
- `fsoilordercon` — soil-order-dependent constants, read by `soilorder_conrd` in `soilorder_varcon.F90:66`.

### Overall flow

```
controlMod reads namelist (paramfile, fsoilordercon, ...)
        |
        v
readParamsMod::readSharedParameters  -> CNParamsSharedReadFile
        |                                  (opens paramfile, calls
        v                                   SharedParamsMod::ParamsReadShared)
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
        |   PhotosynthesisMod::params_inst%readParams      (if use_hydrstress)
        v
pftvarcon::pftconrd    (PFT physiology: dleaf, slatop, leafcn, etc.)
        |
        v
soilorder_varcon::soilorder_conrd   (smax, ks_sorption, r_weather, ...)
```

(See `main/readParamsMod.F90:22-152` for the dispatcher.) Every downstream reader re-opens the NetCDF file through `ncdio_pio::ncd_pio_openfile`, reads its fields via `ncd_io(...)`, and closes it at the end of `readPrivateParameters` (main/readParamsMod.F90:176).

### `paramUtilMod` read primitives

`paramUtilMod` (main/paramUtilMod.F90) provides a generic `readNcdio` interface that wraps `ncdio_pio::ncd_io` for scalar, 1D, and 2D reads, with optional dimension-checking variants (main/paramUtilMod.F90:10-26). Every `read*Params` routine across the BGC modules uses these helpers to fetch tables and trap missing variables via `endrun`.

### `pftvarcon::pftconrd`

`pftconrd` (main/pftvarcon.F90:320) is the PFT-physiology reader. It first defines an `expected_pftnames(0:mxpft)` list (main/pftvarcon.F90:361-411) that encodes the exact order of PFTs in the file: index 0 is `not_vegetated`, 1-8 are tree PFTs, 9-11 are shrubs, 12-14 are grasses, and 15-50 are crops. The file's `pftname` variable is read and compared index-by-index; a mismatch is a fatal error (`pftconrd: bad name for pft on paramfile dataset`, main/pftvarcon.F90:1037-1040). After matching, `pftconrd` assigns short integer aliases (`ndllf_evr_tmp_tree`, `nbrdlf_evr_shrub`, `nc3_arctic_grass`, `ncorn`, etc.; main/pftvarcon.F90:1043-1100+) that are used elsewhere in the model to look up per-PFT parameters. It allocates arrays of size `(0:mxpft)` or `(0:mxpft, nsoilorder)` or `(0:mxpft, nlevdecomp_full)` depending on dimensionality, for hundreds of fields (main/pftvarcon.F90:413-600+).

### `soilorder_varcon::soilorder_conrd`

`soilorder_conrd` (main/soilorder_varcon.F90:66) reads the soil-order parameter file identified by `fsoilordercon`. The expected soil-order list (main/soilorder_varcon.F90:99+) is: Water, Andisols, Gelisols, Histosols, Entisols, Inceptisols, Aridsols, Vertisols, Mollisols, Alfisols, Spodosols, Ultisols, Oxisols, Shifting_sand, rock_land, Ice_Glacier. The allocated arrays include `smax`, `ks_sorption`, `r_weather`, `r_adsorp`, `r_desorp`, `r_occlude`, and four biochemistry rate constants `k_s1_biochem`-`k_s4_biochem` (main/soilorder_varcon.F90:40-49) — these drive the ECA phosphorus cycle in CNP mode.

## 6. Surface dataset: `surfrdMod`

`surfrdMod` (main/surfrdMod.F90) reads the surface dataset (`fsurdat`), which defines grid geometry, land mask, subgrid weights for landunits and patches, glacier elevation classes, and fertilizer amounts. Public entry points (main/surfrdMod.F90:37-43):

- `surfrd_get_globmask(filename, mask, ni, nj)` — reads the global land mask before decomposition.
- `surfrd_get_grid(begg, endg, ldomain, filename, glcfilename)` — reads grid/landfrac into `ldomain` after decomposition.
- `surfrd_get_topo(domain, filename)` — reads grid topography.
- `surfrd_get_data(begg, endg, ldomain, lfsurdat)` — main subgrid-weight reader.
- `surfrd_get_grid_conn(...)` — grid connectivity (for lateral flow).
- `surfrd_topounit_data(begg, endg, lfsurdat)` — topounit physical properties.
- `surfrd_get_topo_for_solar_rad(domain, filename)` — TOP radiation inputs.

`surfrd_get_data` (main/surfrdMod.F90:601) opens the file, validates `PFTDATA_MASK`, detects whether the file is a domain-type (`xc`/`yc`) or LNDGRID-type (`LONGXY`/`LATIXY`) file (main/surfrdMod.F90:683-700), consistency-checks lat/lon against `fatmlndfrc`, then calls `surfrd_special` for ice/lake/wetland/urban/glacier_mec landunits and `surfrd_veg_all`/`surfrd_pftformat`/`surfrd_cftformat`/`surfrd_fates_nocropmod` for the vegetated landunit. Subgrid weights are stored in `elm_varsur` pointers: `wt_lunit(:,:,:)`, `wt_nat_patch(:,:,:)`, `wt_cft(:,:,:)`, `wt_glc_mec(:,:,:)`, `fert_cft(:,:,:)`, `fert_p_cft(:,:,:)` (main/elm_varsur.F90:17-40). These are indexed by `(gridcell, topounit, patch_or_landunit)` and are later distributed into the subgrid hierarchy by `initGridCellsMod`.

`surfrdUtilsMod` (main/surfrdUtilsMod.F90) provides shared utilities: `check_sums_equal_1_2d`/`check_sums_equal_1_3d` guard that weight arrays sum to 1, and `collapse_crop_types`/`collapse_crop_var` handle the crop-type collapsing logic when the paramfile and surfdat have different crop lists.

## 7. Auxiliary file readers

- `organicFileMod::organicrd(organic)` (main/organicFileMod.F90:44) reads the organic-matter density (`kg/m3`) field from `fsurdat`. It is separate from `surfrd_get_data` because it returns a `(begg:endg, ntopo, nlevsoi)` field into a caller-supplied pointer.
- `ndepStreamMod::ndep_init(bounds, NLFilename)` (main/ndepStreamMod.F90:45) reads the `ndepdyn_nml` namelist (`stream_year_first_ndep`, `stream_year_last_ndep`, `model_year_align_ndep`, `ndepmapalgo`, `stream_fldFileName_ndep`) and initializes a `shr_strdata_type` stream for interpolated N deposition. `ndep_interp` performs the temporal interpolation each time step. The companion `elm_domain_mct` sets up the MCT domain for the stream.
- `pdepStreamMod` (main/pdepStreamMod.F90) mirrors `ndepStreamMod` for phosphorus deposition. Same pattern: `pdep_init` reads a `pdepdyn_nml` namelist, `pdep_interp` updates values each time step.
- `fanStreamMod::fanstream_init(bounds, NLFilename)` (main/fanStreamMod.F90:48) reads `fan_nml` and sets up five data streams (`sdat_past`, `sdat_mix`, `sdat_urea`, `sdat_nitr`, `sdat_soilph`) for the FAN manure-nitrogen pipeline. `fanstream_interp` performs per-step interpolation. This is active only when `use_fan = .true.`.

All three stream modules ultimately use `shr_strdata_mod` from the share code to handle NetCDF input streams, time alignment, and horizontal remapping (`bilinear`, `nn`, etc.).

## 8. Cross-references

- `controlMod` consistency checks rely on `elm_varpar` for `maxpatch_glcmec`, `nlevdecomp_full`, `nsoilorder`.
- `surfrdMod` consumes `nlevsoifl`, `numpft`, `numcft` from `elm_varpar` and `numurbl` from `landunit_varcon`.
- `histFileMod` imports `max_tapes`, `max_namlen`, and all `hist_*` namelist vars from `elm_varctl` via the `namelist /elm_inparm/` declarations in `controlMod`.
- `readParamsMod` is called from `elm_initializeMod` after `controlMod` runs and after `elm_varpar_init` has established dimensions.
