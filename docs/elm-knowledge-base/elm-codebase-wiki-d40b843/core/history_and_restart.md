---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# History Output and Restart I/O

ELM writes two classes of NetCDF output: **history files** (time-averaged or instantaneous diagnostics on a user-selected subset of variables) and **restart files** (binary-identical snapshots of every prognostic state needed to resume or branch a run). The two systems are largely independent but share the PIO-based `ncdio_pio` I/O layer and the subgrid string-tag conventions defined in `elm_varcon` (`nameg`, `namet`, `namel`, `namec`, `namep`, `nameCohort`).

**Status at d40b843 vs 60d9aad: structurally unchanged narratives, with one important update for FATES.** The inner `alm_fates%restart` call inside `restFile_read`/`restFile_write` now passes three FATES-side keyword arguments. `histFileMod` grew slightly (5238 → 5269 lines) but the high-level architecture is intact. `restFileMod` grew slightly (1430 → 1444 lines).

## 1. The history module: `histFileMod`

`histFileMod` (`main/histFileMod.F90`, 5269 lines) implements a multi-tape, multi-field system where each model variable is added to a master list exactly once via `hist_addfld1d` or `hist_addfld2d`, and the runtime decides which tapes collect which fields, at which frequency, averaged which way.

### 1.1 Tapes, fields, and the master list

Key size parameters (`main/histFileMod.F90:48-50`):

```fortran
integer, public, parameter :: max_tapes  = 6          ! max number of history tapes
integer, public, parameter :: max_flds   = 2500       ! max fields on any one tape
integer, public, parameter :: max_namlen = 64         ! max characters in a field name
```

Plus `max_subs = 100` (max registered 2D subscripts, `:159`).

Fields are first added to the **master list** (`masterlist(max_flds)`) and then, per tape, **activated** into the per-tape `tape(t)%hlist(max_flds)` array. The two key derived types are:

- `field_info` — name, long_name, standard_name, units, type1d (e.g., `nameg`, `namep`), type2d (e.g., `levgrnd`, `numrad`), beg1d/end1d, num1d, num2d, beg1d_out/end1d_out, hpindex, p2c/c2l/l2g/t2g scale types, no_snow_behavior.
- `history_entry` — `field_info` + `avgflag` + `hbuf(:,:)` + `nacs(:,:)` accumulation counter.
- `history_tape` — nflds, ntimes, mfilt, nhtfrq, ncprec, dov2xy, is_endhist, begtime, hlist.

Data pointers for every field live in global arrays `elmptr_rs(max_mapflds)` (1D real) and `elmptr_ra(max_mapflds)` (2D real). When `hist_addfld1d`/`hist_addfld2d` is called with e.g. `ptr_patch=some_array`, the corresponding `elmptr_rs(hpindex)%ptr` is aimed at that array, and `hist_update_hbuf_field_1d`/`_2d` dereferences it each time step.

### 1.2 Namelist configuration

The history namelist variables wired into `elm_inparm` by `controlMod`:

| Variable | Type | Meaning |
|---|---|---|
| `hist_empty_htapes` | logical | If true, no default fields are populated. |
| `hist_nhtfrq(max_tapes)` | integer | Per-tape history write frequency. `0` = monthly. Negative = `-N hours`. Positive = steps. |
| `hist_mfilt(max_tapes)` | integer | Max time samples per file before rotation. Tape 1 default: 1; others default: 30. |
| `hist_ndens(max_tapes)` | integer | Output precision: 1 = double, 2 = float. |
| `hist_dov2xy(max_tapes)` | logical | Average from subgrid points to gridcell xy output. |
| `hist_avgflag_pertape(max_tapes)` | char(1) | `A`/`I`/`X`/`M`. |
| `hist_type1d_pertape(max_tapes)` | char(64) | Force a tape to use a particular subgrid 1D type. |
| `hist_fincl1..6(max_flds)` | char(66) | Fields to include. |
| `hist_fexcl1..6(max_flds)` | char(66) | Fields to exclude. |
| `hist_wrtch4diag` | logical | Also write CH4 diagnostic fields. |

### 1.3 The `hist_addfld` pattern

Every field that ELM writes starts its life with a call to `hist_addfld1d` or `hist_addfld2d`. Signature of `hist_addfld1d`:

```fortran
call hist_addfld1d (fname, units, avgflag, long_name, type1d_out, standard_name, &
                    ptr_gcell, ptr_topo, ptr_lunit, ptr_col, ptr_patch, ptr_lnd, &
                    ptr_atm, p2c_scale_type, c2l_scale_type, &
                    l2g_scale_type, t2g_scale_type, set_lake, set_nolake, set_urb, &
                    set_nourb, set_noglcmec, set_spec, default)
```

The caller passes exactly one of `ptr_gcell`, `ptr_topo`, `ptr_lunit`, `ptr_col`, `ptr_patch`, `ptr_lnd`, `ptr_atm` — that choice determines `type1d` and which `elmptr_rs(hpindex)%ptr` pointer is aimed at the data array.

`hist_addfld2d` adds an extra `type2d` argument (`levgrnd`, `levsoi`, `levsno`, `levlak`, `numrad`, `natpft`, `cft`, `month`, etc.).

### 1.4 Tape lifecycle

Once all `hist_addfld*` calls have run during model init, `hist_htapes_build()` parses `hist_fincl*` / `hist_fexcl*`, copies tape config into `tape(t)%`, and sets `tape(t)%begtime`.

During run, `hist_update_hbuf(bounds)` is called every time step. For each active field on each tape, it increments `nacs` and adds the current value into `hbuf`:
- `A` — running sum (later divided in `hfields_normalize`).
- `I` — overwrite with latest value.
- `X` / `M` — running max / min.

`hist_htapes_wrapup(rstwr, nlend, bounds, watsat_col, sucsat_col, bsw_col, hksat_col)` is called each step after accumulation. For each tape it checks whether the end-of-interval is reached:

```fortran
if (tape(t)%nhtfrq == 0) then       ! monthly average
   if (mon /= monm1) tape(t)%is_endhist = .true.
else
   if (mod(nstep,tape(t)%nhtfrq) == 0) tape(t)%is_endhist = .true.
end if
```

When the interval ends: normalize averaged fields, increment `ntimes`, open a new file on the first sample, write the sample, zero the buffers.

### 1.5 History filename convention

`set_hist_filename(hist_freq, hist_mfilt, hist_file)` builds:

```
./<caseid>.elm<inst_suffix>.h<N>.<date>.nc
```

where `N = hist_file - 1` (so tape 1 → `h0`, tape 2 → `h1`, ...) and `<date>` is `YYYY-MM` for monthly output or `YYYY-MM-DD-SSSSS` otherwise.

History restart files (needed because history buffers accumulate between writes) follow the pattern `./<caseid>.elm<inst_suffix>.rh<N>.<date>.nc`.

### 1.6 Per-tape restart of the accumulators

`hist_restart_ncd(bounds, ncid, flag, rdate)` is the history-restart handler. It is called by `restFileMod::restFile_write` and `restFileMod::restFile_read` with `flag = 'define' | 'write' | 'read'` and is responsible for preserving the partially-accumulated `hbuf`, `nacs`, `begtime`, and `ntimes` counters across restart boundaries.

### 1.7 `histGPUMod`: GPU mirror

`histGPUMod` (`main/histGPUMod.F90`, 871 lines) provides a `history_tape_gpu` derived type and `htape_gpu_init` routine that copies the active tape list into structures declared with `!$acc declare create(tape_gpu)` so that GPU kernels can update `hbuf` directly.

## 2. The restart module: `restFileMod`

`restFileMod` (`main/restFileMod.F90`, 1444 lines) writes/reads a single NetCDF restart file holding the full ELM prognostic state. Public entry points:

- `restFile_write` (`main/restFileMod.F90:103`) — write the restart file.
- `restFile_read` (`main/restFileMod.F90:459`) — read a restart file during a restart or branch run.
- `restFile_open` (`:854`) / `restFile_close` (`:1182`) — low-level file handling.
- `restFile_getfile` (`:683`) — fetch a restart file from disk/storage.
- `restFile_filename(rdate)` — compose the restart filename.

### 2.1 The variable-restart pattern

`restFile_read` and `restFile_write` follow a uniform dispatch pattern: each major `*_type` derived type has a type-bound procedure `restart(bounds, ncid, flag)` (e.g., `atm2lnd_vars%restart`, `canopystate_vars%restart`, `soilhydrology_vars%restart`). The module calls every such procedure in sequence. Each `restart` routine internally uses `restUtilMod::restartvar` helpers.

### 2.2 Restart filename

`restFile_filename(rdate)`:

```fortran
restFile_filename = "./"//trim(caseid)//".elm"//trim(inst_suffix)// &
                    ".r."//trim(rdate)//".nc"
```

All ELM restart files end in `.r.` followed by the model date (`YYYY-MM-DD-SSSSS`). Auxiliary history-restart files use the `.rh<N>.` prefix.

### 2.3 Dimension definitions: `restFile_dimset`

`restFile_dimset(ncid)` (`main/restFileMod.F90:912`) is called during `flag='define'` and registers every NetCDF dimension used by restart variables: subgrid dimensions (`nameg`, `namet`, `namel`, `namec`, `namep`, and `nameCohort` when `use_fates`); soil/snow/lake/urban level dimensions (`levgrnd`, `levsoi` via `nlevtrc_full`, `levurb`, `levlak`, `levsno`, `levsno1`, `levtot`); radiation (`numrad`), canopy (`levcan`), vegetation water stress (`vegwcs` when `use_hydrstress`), crop (`glc_nec` for `maxpatch_glcmec`), and `budg_flux` / `budg_state` for C/N/P budget arrays when `do_budgets` is on. Global attributes are then written.

### 2.4 Consistency checks

After opening a restart file for reading, `restFile_dimcheck(ncid)` verifies that the file's subgrid dimensions match the current run's. The `finidat_consistency_checks` namelist controls how strict the consistency checks are:

```fortran
namelist /finidat_consistency_checks/ &
     check_finidat_fsurdat_consistency, &
     check_finidat_year_consistency, &
     check_finidat_pct_consistency
```

All three default to `.true.`. The group is read via `elm_nlUtilsMod::find_nlgroup_name`.

### 2.5 The FATES restart call (NEW signature at api.43)

The full `restFile_read` argument list (`main/restFileMod.F90:459-465`):

```fortran
subroutine restFile_read( bounds, file,                           &
     atm2lnd_vars, aerosol_vars, canopystate_vars, cnstate_vars,  &
     ch4_vars, energyflux_vars, frictionvel_vars, lakestate_vars, &
     photosyns_vars, soilhydrology_vars,                          &
     soilstate_vars, solarabs_vars, surfalb_vars,                 &
     sedflux_vars, ep_betr,                                       &
     alm_fates, glc2lnd_vars, crop_vars)
```

The argument list itself is unchanged from 60d9aad. **What changed at api.43 is the inner `alm_fates%restart` call** at `main/restFileMod.F90:642-647`:

```fortran
if (use_fates) then
   call alm_fates%restart(bounds, ncid, flag='read',  &
         canopystate_inst=canopystate_vars, &
         frictionvel_inst=frictionvel_vars, &
         soilstate_inst=soilstate_vars)
end if
```

Three new keyword arguments (`canopystate_inst`, `frictionvel_inst`, `soilstate_inst`) carry the host state that the FATES read-side post-processing needs. After reading restart vectors, the FATES-side `restart` routine rebuilds the cohort linked-list state, calls `ed_update_site(..., is_restarting=.true.)` per site, repopulates hydraulic `bc_in` from `soilstate_inst`, and rebuilds canopy diagnostics in `canopystate_inst` / `frictionvel_inst` via `wrap_update_hlmfates_dyn(..., .true.)`. See [`fates_interface.md`](fates_interface.md) for the body.

The dispatch order (subgridRest → reweight_wrapup loop → accumulRest → vars → FATES → hist_restart_ncd → WaterBudget_Restart → CNPBudget_Restart) is unchanged.

### 2.6 Subgrid restart: `subgridRestMod`

`subgridRestMod::subgridRest(bounds, ncid, flag)` is called by `restFile_read`/`restFile_write` and handles restart I/O of the subgrid-structure arrays themselves: `grc_pp`, `top_pp`, `lun_pp`, `col_pp`, `veg_pp`. It is split into:

- `subgridRest_write_only` — write-only variables (e.g., pre-computed `active` flags, time-constant metadata). On read, these are recomputed.
- `subgridRest_write_and_read` — variables that round-trip (weights such as `veg_pp%wtlunit`, indices, `itype`, etc.).

`subgridRest_check_consistency` and `subgridRest_read_cleanup` are called after the read to validate and free the scratch `pft_wtlunit_before_rest_read` array. `subgridRest_write_only` stores `pft_wtlunit_before_rest_read` before subgrid weights are overwritten so the outer `reweight_wrapup` call in `restFile_read` can detect weight changes and recompute subgrid filters.

## 3. Cross-module interactions

- `restFile_read` opens the file, calls `restFile_dimcheck`, then `subgridRest(...,'read')`, then `accumulRest`, then each `*_vars%restart(...,'read')` in sequence, then the FATES restart call (with the three new keyword args at api.43), then `hist_restart_ncd`, and finally `WaterBudget_Restart` / `CNPBudget_Restart`.
- The order matters: subgrid structure must be read first so that later variable-level restarts can use the correct `bounds` and filter arrays.
- `hist_restart_ncd` is called with the same `ncid` as the main restart file, so history-accumulator state lives inside the main restart file rather than as a separate sidecar.
- `accumulMod::accumulRest` handles the time-averaging accumulators (those registered via `init_accum_field` — e.g., 10-day running means used by CN phenology).

## 4. Summary table

| Component | File | Frequency | Purpose |
|---|---|---|---|
| History tapes (h0-h5) | `main/histFileMod.F90` | per `hist_nhtfrq` step | Diagnostic output, averaged or instantaneous, user-selectable fields. |
| History restart (`rh*`) | `main/histFileMod.F90` | per restart point | Round-trip history buffers and counters. |
| Restart (`.r.`) | `main/restFileMod.F90` | per restart point | Full prognostic state. |
| Subgrid restart | `main/subgridRestMod.F90` | embedded in `.r.` | Subgrid hierarchy + weights. |
| Accumulator restart | `main/accumulMod.F90` | embedded in `.r.` | Running-mean accumulators (e.g., CN phenology). |
| GPU tape mirror | `main/histGPUMod.F90` | per step | OpenACC-accessible copy of active history buffers. |

## 5. FATES-relevant restart flow

For Kougarok-style runs with `use_fates`, the full restart sequence is:

1. **Define phase** (during `restFile_dimset`): the `nameCohort` dimension is registered.
2. **Subgrid restart** rebuilds `wtlunit`, `wtcol`, `is_fates`, `is_soil` etc. on `col_pp`/`veg_pp`.
3. **`alm_fates%restart(bounds, ncid, flag='read', canopystate_inst=..., frictionvel_inst=..., soilstate_inst=...)`** runs the FATES-side `restart` body which:
   - Allocates restart I/O structures on first call (`fates_restart%Init` → `assemble_restart_output_types` → `initialize_restart_vars`).
   - Reads cohort_r8 / site_r8 / cohort_int / site_int variables via `restartvar`.
   - Calls `create_patchcohort_structure` and `get_restart_vectors` to rebuild the cohort linked-list state.
   - Per site, calls `ed_update_site(..., is_restarting=.true.)`.
   - For `use_fates_sp`, copies host LAI/TSAI/HTOP from `canopystate_inst` into `bc_in%hlm_sp_*`.
   - For `use_fates_planthydro`, repopulates hydraulic `bc_in` from `soilstate_inst` and calls `RestartHydrStates`.
   - Calls `wrap_update_hlmfates_dyn(..., .true.)` to rebuild ELM-side canopy diagnostics from the just-restored FATES state.
   - Calls `fates_restart%update_3dpatch_radiation` and `fates_hist%update_history_dyn`.
   - If `fates_seeddisp_cadence /= fates_dispersal_cadence_none`, calls `WrapGlobalSeedDispersal(is_restart_flag=.true.)`.

The three new keyword args are load-bearing: dropping them (or passing the wrong instance) will not compile.
