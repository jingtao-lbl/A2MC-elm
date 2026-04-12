---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# History Output and Restart I/O

ELM writes two classes of NetCDF output: **history files** (time-averaged or instantaneous state/flux diagnostics written onto a user-selected subset of the model variables) and **restart files** (binary-identical snapshots of every prognostic state variable needed to resume or branch a run). The two systems are largely independent but share the PIO-based `ncdio_pio` I/O layer and the subgrid string-tag conventions defined in `elm_varcon` (`nameg`, `namet`, `namel`, `namec`, `namep`, `nameCohort`).

## 1. The history module: `histFileMod`

`histFileMod` (main/histFileMod.F90, 5238 lines) is the heart of history output. It implements a multi-tape, multi-field system where each model variable is added to a master list exactly once via `hist_addfld1d` or `hist_addfld2d`, and the runtime decides which tapes collect which fields, at which frequency, averaged which way.

### 1.1 Tapes, fields, and the master list

Key size parameters (main/histFileMod.F90:47-49):

```fortran
integer, public, parameter :: max_tapes  = 6          ! max number of history tapes
integer, public, parameter :: max_flds   = 2500       ! max fields on any one tape
integer, public, parameter :: max_namlen = 64         ! max characters in a field name
```

Fields are first added to the **master list** (`masterlist(max_flds)`, main/histFileMod.F90:229) and then, per tape, **activated** into the per-tape `tape(t)%hlist(max_flds)` array (main/histFileMod.F90:233). The two key `derived types` (main/histFileMod.F90:164-213) are:

- `field_info` — name, long_name, standard_name, units, type1d (e.g., `nameg`, `namep`), type2d (e.g., `levgrnd`, `numrad`), beg1d/end1d, num1d, num2d, beg1d_out/end1d_out, hpindex, p2c/c2l/l2g/t2g scale types, no_snow_behavior.
- `history_entry` — field_info + `avgflag` + `hbuf(:,:)` + `nacs(:,:)` accumulation counter.
- `history_tape` — nflds, ntimes, mfilt, nhtfrq, ncprec, dov2xy, is_endhist, begtime, hlist.

Data pointers for every field live in global arrays `elmptr_rs(max_mapflds)` (1D real) and `elmptr_ra(max_mapflds)` (2D real) (main/histFileMod.F90:224-225). When `hist_addfld1d`/`hist_addfld2d` is called with e.g. `ptr_patch=some_array`, the corresponding `elmptr_rs(hpindex)%ptr` is aimed at that array, and `hist_update_hbuf_field_1d`/`_2d` (main/histFileMod.F90:1021, 1271) dereferences it each time step to accumulate into `hbuf`.

### 1.2 Namelist configuration

The history-file namelist variables declared in `histFileMod` (main/histFileMod.F90:69-114) and wired into `elm_inparm` by `controlMod` are:

| Variable | Type | Meaning |
|---|---|---|
| `hist_empty_htapes` | logical | If true, no default fields are populated; users must list everything via `hist_fincl*`. |
| `hist_nhtfrq(max_tapes)` | integer | Per-tape history write frequency. `0` = monthly. Negative values are treated as `-N hours` (converted to steps in `controlMod.F90:404`). Positive values are in steps. |
| `hist_mfilt(max_tapes)` | integer | Max time samples per file before rotation. Tape 1 default: 1 sample per file (monthly). Other tapes default: 30. |
| `hist_ndens(max_tapes)` | integer | Output precision: 1 = double (`ncd_double`), 2 = float (`ncd_float`). See tape init at main/histFileMod.F90:489-492. |
| `hist_dov2xy(max_tapes)` | logical | If true, average from subgrid points to gridcell xy output. |
| `hist_avgflag_pertape(max_tapes)` | char(1) | `A` (average), `I` (instantaneous), `X` (max), `M` (min), or blank for per-field default. Validated at main/histFileMod.F90:538-541. |
| `hist_type1d_pertape(max_tapes)` | char(64) | Force a tape to use a particular subgrid 1D type. |
| `hist_fincl1..6(max_flds)` | char(66) | List of field names to include on each tape. Format `name` or `name:avgflag`. |
| `hist_fexcl1..6(max_flds)` | char(66) | List of field names to exclude. |
| `hist_wrtch4diag` | logical | Also write CH4 diagnostic fields (only meaningful with `use_lch4`). |

### 1.3 The `hist_addfld` pattern

Every field that ELM writes starts its life with a call to `hist_addfld1d` or `hist_addfld2d`. Signature of `hist_addfld1d` (main/histFileMod.F90:4433-4473):

```fortran
call hist_addfld1d (fname, units, avgflag, long_name, type1d_out, standard_name, &
                    ptr_gcell, ptr_topo, ptr_lunit, ptr_col, ptr_patch, ptr_lnd, &
                    ptr_atm, p2c_scale_type, c2l_scale_type, &
                    l2g_scale_type, t2g_scale_type, set_lake, set_nolake, set_urb, &
                    set_nourb, set_noglcmec, set_spec, default)
```

The caller passes exactly one of `ptr_gcell`, `ptr_topo`, `ptr_lunit`, `ptr_col`, `ptr_patch`, `ptr_lnd`, `ptr_atm` — that choice determines `type1d` (e.g., `ptr_patch` → `namep`) and which `elmptr_rs(hpindex)%ptr` pointer is aimed at the data array (main/histFileMod.F90:4498-4550+). Optional `set_*` arguments let the caller zero out the pointer on special landunits (lakes, urban, etc.) before registration.

`hist_addfld2d` (main/histFileMod.F90:4671) adds an extra `type2d` argument (`levgrnd`, `levsoi`, `levsno`, `levlak`, `numrad`, `natpft`, `cft`, `month`, etc.) and takes 2D pointers. The allowed 2D dimensions are registered via `hist_add_subscript(name, dim)` (main/histFileMod.F90:5144); the library keeps at most 100 (`max_subs = 100`, main/histFileMod.F90:159).

The `default='inactive'` optional argument flags a field as registered-but-off-by-default, so it only appears on a tape if the user names it in `hist_fincl*`.

### 1.4 Tape lifecycle: `hist_htapes_build` / `hist_update_hbuf` / `hist_htapes_wrapup`

Once all `hist_addfld*` calls have run during model init, `hist_htapes_build()` (main/histFileMod.F90:432) is called to:

1. Parse `hist_fincl*` and `hist_fexcl*` lists via `htapes_fieldlist()` (main/histFileMod.F90:605) and push chosen fields into each tape's `hlist`.
2. Copy `hist_dov2xy(t)`, `hist_nhtfrq(t)`, `hist_mfilt(t)`, and `hist_ndens(t)` into the `tape(t)%` struct (main/histFileMod.F90:484-494).
3. Set `tape(t)%begtime` from `get_prev_time()` (main/histFileMod.F90:499-502).

During run, `hist_update_hbuf(bounds)` (main/histFileMod.F90:987) is called every time step. For each active field on each tape, it increments `nacs` (number of accumulations) and adds the current value into `hbuf`, following the field's avgflag:
- `A` — running sum, later divided by `nacs` in `hfields_normalize` (main/histFileMod.F90:1665).
- `I` — overwrite with latest value.
- `X` / `M` — running max / min.

`hist_htapes_wrapup(rstwr, nlend, bounds, watsat_col, sucsat_col, bsw_col, hksat_col)` (main/histFileMod.F90:3310) is called each step after accumulation. For each tape it checks whether the end-of-interval is reached:

```fortran
if (tape(t)%nhtfrq == 0) then       ! monthly average
   if (mon /= monm1) tape(t)%is_endhist = .true.
else
   if (mod(nstep,tape(t)%nhtfrq) == 0) tape(t)%is_endhist = .true.
end if
```

(main/histFileMod.F90:3399-3403.) When the interval ends it: normalizes averaged fields, increments `ntimes`, opens a new file on the first sample (`set_hist_filename` + `htape_create`; main/histFileMod.F90:3425-3432), writes the sample via `hfields_write`, and zeroes the buffers via `hfields_zero` for the next interval.

### 1.5 History filename convention

`set_hist_filename(hist_freq, hist_mfilt, hist_file)` (main/histFileMod.F90:4394-4430) builds the path:

```
./<caseid>.elm<inst_suffix>.h<N>.<date>.nc
```

where `N` = `hist_file - 1` (so tape 1 → `h0`, tape 2 → `h1`, ...) and `<date>` is `YYYY-MM` for monthly output (`hist_freq == 0 .and. hist_mfilt == 1`, using `get_prev_date`) or `YYYY-MM-DD-SSSSS` otherwise (using `get_curr_date`). Source lines main/histFileMod.F90:4419-4428.

History restart files (needed because history buffers accumulate between writes) follow the pattern `./<caseid>.elm<inst_suffix>.rh<N>.<date>.nc` — built at main/histFileMod.F90:3678.

### 1.6 Per-tape restart of the accumulators

`hist_restart_ncd(bounds, ncid, flag, rdate)` (main/histFileMod.F90:3529) is the history-restart handler. It is called by `restFileMod::restFile_write` and `restFileMod::restFile_read` with `flag = 'define' | 'write' | 'read'` and is responsible for preserving the partially-accumulated `hbuf`, `nacs`, `begtime`, and `ntimes` counters across restart boundaries so that monthly averages spanning a restart are reconstructed correctly.

### 1.7 `histGPUMod`: GPU mirror

`histGPUMod` (main/histGPUMod.F90, 871 lines) provides a `history_tape_gpu` derived type and `htape_gpu_init` routine that copies the active tape list into structures declared with `!$acc declare create(tape_gpu)` (main/histGPUMod.F90:68) so that GPU kernels can update `hbuf` directly. It mirrors `histFileMod` internal types in a flattened, pointer-heavy form suitable for OpenACC transfer. The CPU-side truth still lives in `histFileMod::tape`; the GPU tape is populated from it and map arrays (`map_tapes`, `map_fields`) let the CPU find the GPU-updated values at the end of each step (main/histGPUMod.F90:24-26).

## 2. The restart module: `restFileMod`

`restFileMod` (main/restFileMod.F90, 1430 lines) writes/reads a single NetCDF restart file that holds the full ELM prognostic state. Public entry points (main/restFileMod.F90:73-79):

- `restFile_write` — write the restart file.
- `restFile_read` — read a restart file during a restart or branch run.
- `restFile_open` / `restFile_close` — low-level file handling.
- `restFile_getfile` — fetch a restart file from disk/storage.
- `restFile_filename(rdate)` — compose the restart filename (see below).

### 2.1 The variable-restart pattern

`restFile_read` (main/restFileMod.F90:455) and `restFile_write` follow a uniform dispatch pattern: each major `*_type` derived type has a type-bound procedure `restart(bounds, ncid, flag)` (e.g., `atm2lnd_vars%restart`, `canopystate_vars%restart`, `soilhydrology_vars%restart`). The module simply calls every such procedure in sequence (main/restFileMod.F90:535-574+). Each `restart` routine internally uses `restUtilMod::restartvar` helpers (from `utils/restUtilMod.F90.in`) to register each field: provide the NetCDF varname, optionally a `readvar` flag, and the local data pointer. The first call with `flag='define'` defines all variables in the NetCDF header; `flag='write'` actually writes them; `flag='read'` reads them back on restart.

### 2.2 Restart filename

`restFile_filename(rdate)` (main/restFileMod.F90:886-903):

```fortran
restFile_filename = "./"//trim(caseid)//".elm"//trim(inst_suffix)// &
                    ".r."//trim(rdate)//".nc"
```

All ELM restart files end in `.r.` followed by the model date, which is usually provided in `YYYY-MM-DD-SSSSS` format by the driver. There is exactly one primary restart file per restart point; auxiliary history-restart files use the `.rh<N>.` prefix from `histFileMod` (see §1.5).

### 2.3 Dimension definitions: `restFile_dimset`

`restFile_dimset(ncid)` (main/restFileMod.F90:906) is called during `flag='define'` and registers every NetCDF dimension used by restart variables: the subgrid dimensions (`nameg`, `namet`, `namel`, `namec`, `namep`, and `nameCohort` when `use_fates`); the soil/snow/lake/urban level dimensions (`levgrnd`, `levsoi` via `nlevtrc_full`, `levurb`, `levlak`, `levsno`, `levsno1`, `levtot`); radiation (`numrad`), canopy (`levcan`), vegetation water stress (`vegwcs` when `use_hydrstress`), crop (`glc_nec` for `maxpatch_glcmec`), and the `budg_flux` / `budg_state` dimensions for C/N/P budget restart arrays when `do_budgets` is on (main/restFileMod.F90:946-984). Global attributes are then written (`Conventions`, `history`, `username`, `host`, `version`, `source`, `case_title`, `case_id`, `surface_dataset`, `flanduse_timeseries`, `title`; main/restFileMod.F90:988-1007). Finally, metadata helpers `restFile_add_ilun_metadata`, `restFile_add_icol_metadata`, and `restFile_add_ipft_metadata` are called to write enumerated-type decoder rings into the global attributes (main/restFileMod.F90:1009-1011, 1016-1112).

### 2.4 Consistency checks

After opening a restart file for reading, `restFile_dimcheck(ncid)` (main/restFileMod.F90:1113) verifies that the file's subgrid dimensions match the current run's dimensions, aborting otherwise. Additional high-level consistency checks are governed by the `finidat_consistency_checks` namelist (see below): `restFile_check_fsurdat(ncid)` (main/restFileMod.F90:1291) compares the `surface_dataset` global attribute with the current `fsurdat`, and `restFile_check_year(ncid)` (main/restFileMod.F90:1349) checks that the restart file's year matches the expected initial date.

### 2.5 The `finidat_consistency_checks` namelist

`restFile_read_consistency_nl` (main/restFileMod.F90:1225-1288) reads a small Fortran namelist group, separate from `elm_inparm`, to control how strict the consistency checks are:

```fortran
namelist /finidat_consistency_checks/ &
     check_finidat_fsurdat_consistency, &
     check_finidat_year_consistency, &
     check_finidat_pct_consistency
```

All three default to `.true.` (main/restFileMod.F90:1258-1260). The group is read via `elm_nlUtilsMod::find_nlgroup_name` (utils/elm_nlUtilsMod.F90:41) from the same `lnd.stdin` that `controlMod` consumed, and then broadcast with `shr_mpi_bcast`. These flags let the user disable specific checks when, for example, intentionally starting a new run from a restart whose `fsurdat` or year differs.

### 2.6 Subgrid restart: `subgridRestMod`

`subgridRestMod::subgridRest(bounds, ncid, flag)` (main/subgridRestMod.F90:49) is called by `restFile_read`/`restFile_write` and handles restart I/O of the subgrid-structure arrays themselves: `grc_pp`, `top_pp`, `lun_pp`, `col_pp`, `veg_pp`. It is split into two private workers (main/subgridRestMod.F90:38-40):

- `subgridRest_write_only` — write-only variables (e.g., pre-computed `active` flags, time-constant metadata). On read, these are recomputed from the rest of the state.
- `subgridRest_write_and_read` — variables that truly round-trip (weights such as `veg_pp%wtlunit`, indices, `itype`, etc.).

`subgridRest_check_consistency` and `subgridRest_read_cleanup` are called after the read to validate and then free the scratch `pft_wtlunit_before_rest_read` array (main/subgridRestMod.F90:43). `subgridRest_write_only` stores the module-local `pft_wtlunit_before_rest_read` before the subgrid weights are overwritten so the outer `reweight_wrapup` call in `restFile_read` (main/restFileMod.F90:526-531) can detect weight changes and recompute subgrid filters accordingly.

## 3. Cross-module interactions

- `restFile_read` opens the file, calls `restFile_dimcheck`, then `subgridRest(...,'read')`, then `accumulRest` (main/accumulMod.F90:31), then each `*_vars%restart(...,'read')` in sequence, then the FATES restart call, then `hist_restart_ncd`, and finally `WaterBudget_Restart` / `CNPBudget_Restart` (main/restFileMod.F90:508-600+).
- The order matters: subgrid structure must be read first so that later variable-level restarts can use the correct `bounds` and filter arrays.
- `hist_restart_ncd` is called with the same `ncid` as the main restart file, so history-accumulator state lives inside the main restart file rather than as a separate sidecar.
- `accumulMod::accumulRest` handles the time-averaging accumulators (those registered via `init_accum_field` — e.g., 10-day running means used by CN phenology).

## 4. Summary table

| Component | File | Frequency | Purpose |
|---|---|---|---|
| History tapes (h0-h5) | main/histFileMod.F90 | per `hist_nhtfrq` step | Diagnostic output, averaged or instantaneous, user-selectable fields. |
| History restart (`rh*`) | main/histFileMod.F90 | per restart point | Round-trip history buffers and counters. |
| Restart (`.r.`) | main/restFileMod.F90 | per restart point | Full prognostic state. |
| Subgrid restart | main/subgridRestMod.F90 | embedded in `.r.` | Subgrid hierarchy + weights. |
| Accumulator restart | main/accumulMod.F90 | embedded in `.r.` | Running-mean accumulators (e.g., CN phenology). |
| GPU tape mirror | main/histGPUMod.F90 | per step | OpenACC-accessible copy of active history buffers. |
