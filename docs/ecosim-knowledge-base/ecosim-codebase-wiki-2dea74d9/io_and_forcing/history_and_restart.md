---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/IOutils/` output pipeline (`HistFileMod`, `HistDataType`, `bhistMod`, `ForcWriterMod`, `RestartMod`, `restUtilMod`)
**Last verified:** 2026-04-24
---

# History Tapes and Restart Files

EcoSIM has three independent output channels:

1. **Primary history tape system** (`HistFileMod` + `HistDataType`) — up to 6 tapes of CF-style NetCDF time-series output with per-field configurable averaging.
2. **Auxiliary `bhistMod` streams** — lightweight writer for side-channel diagnostics with mixed sub-daily/multi-annual cadences.
3. **Restart / checkpoint files** (`RestartMod` + `restUtilMod`) — full model-state snapshots for continuation.

A fourth, one-shot writer (`ForcWriterMod::WriteBBGCForc`) dumps a single-day NetCDF usable as initial conditions by a standalone batch soil-BGC model.

---

## 1. Primary history tape system

### 1.1 Architecture

`HistFileMod.F90` declares three derived types (`HistFileMod.F90:108-146`):

```fortran
type field_info          ! field identity: name, long_name, units, dims, indices
type history_entry       ! field + avgflag + hbuf(:,:) + nacs(:,:)
type history_tape        ! nflds, ntimes, mfilt, nhtfrq, ncprec, is_endhist, begtime, hlist(max_flds)
```

Globals:

- `tape(max_tapes)` (`HistFileMod.F90:159`) — the array of active tapes (`max_tapes = 6`, `HistFileMod.F90:24`).
- `masterlist(max_flds)` — the master field registry (`max_flds = 2500`, `HistFileMod.F90:25`).
- `esmptr_rs`, `esmptr_ra1`, `esmptr_ra2` (`HistFileMod.F90:105-106`, and 2D variant) — pointer wrappers holding the live-state source of each field (1D, 2D, 3D).
- `nfid(max_tapes)` / `ncid_hist(max_tapes)` (`HistFileMod.F90:168-169`) — file handles for primary and restart-history tapes.

### 1.2 Namelist controls

Set in `&ecosim` (example `examples/run_dir/blodgett/Blodget.ctrl.namelist:37-49`):

| Namelist var | Default | Meaning |
|---|---|---|
| `hist_mfilt(max_tapes)` | `(/ 1, 30, 30, 30, 30, 30 /)` (`HistFileMod.F90:47-48`) | Samples per file per tape. |
| `hist_nhtfrq(max_tapes)` | `(/ 0, -24, -24, -24, -24, -24 /)` (`HistFileMod.F90:50-51`) | Sample frequency. `0` = monthly; negative `-N` = every N hours (so `-24` = daily averaging); positive `N` = every N timesteps. |
| `hist_avgflag_pertape(max_tapes)` | blanks (`HistFileMod.F90:53-54`) | Per-tape override of the per-field averaging flag. |
| `hist_type1d_pertape(max_tapes)` | blanks | Per-tape override of the primary 1D coordinate. |
| `hist_fincl1..hist_fincl6` | blank arrays (`HistFileMod.F90:65-76`) | Inclusion list per tape (field names, optionally suffixed with averaging flag). |
| `hist_fexcl1..hist_fexcl6` | blank arrays (`HistFileMod.F90:78-89`) | Exclusion list per tape. |
| `hist_empty_htapes` | `.false.` (`HistFileMod.F90:41-42`) | If true, do not auto-populate tape 1 with default fields; include lists take full effect. |
| `hist_ndens(max_tapes)` | `2` (`HistFileMod.F90:44-45`) | NetCDF output precision code. |

### 1.3 Field registration

Fields are registered during initialization by `HistDataType::init_hist_data(this, bounds)` (`HistDataType.F90:640`). Each call to `hist_addfld1d` (`HistFileMod.F90:353`) or `hist_addfld2d` (`HistFileMod.F90:534`) does two things:

1. Acquires a pointer slot via `pointer_index()` (`HistFileMod.F90:512`), assigns the live-state Fortran pointer (`ptr_col=>…`, `ptr_gcell=>…`, `ptr_topo=>…`, or `ptr_patch=>…`, `HistFileMod.F90:378-398`).
2. Calls `masterlist_addfld` (`HistFileMod.F90:425`) to record name, units, long_name, dims, avgflag, and the 1D coordinate type (`gridcell`, `topounit`, `column`, or `pft`; `HistFileMod.F90:29-32`).

Representative field registrations in `HistDataType.F90` (first ~20 of hundreds):

```
HistDataType.F90:1256  hist_addfld1d('cumFIRE_CO2_col', 'gC m-2', 'I', ...)
HistDataType.F90:1260  hist_addfld1d('cumFIRE_CH4_col', 'gC d-2', 'I', ...)
HistDataType.F90:1264  hist_addfld1d('cNH4_LITR_col',   'gN NH4/g litter', 'A', ...)
HistDataType.F90:1272  hist_addfld1d('ECO_HVST_C_col',  'gC/m2', 'A', ...)
HistDataType.F90:1284  hist_addfld1d('NET_N_MIN_col',   'gN/m2', 'I', ...)
HistDataType.F90:1293  hist_addfld1d('RADN_col',        'MJ/m2/hr', 'A', ...)
HistDataType.F90:1301  hist_addfld1d('Root_AR_col',     'gC/m2/h', 'A', ...)
HistDataType.F90:1313  hist_addfld1d('HUMUS_C_col',     'gC/m2', 'A', ...)
```

Averaging flags (`avgflag`, fourth argument):
- `'A'` — time-average.
- `'I'` — instantaneous (value at tape-end).
- `'X'` — maximum over interval.
- `'M'` — minimum over interval.

### 1.4 Inclusion-list syntax

A name in `hist_fincl{N}` may carry a trailing averaging-flag suffix, parsed by `getname` (`HistFileMod.F90:1012`) and `getflag` (`HistFileMod.F90:1042`):

```
'TEMP_vr:A'   ← include TEMP_vr on tape N with time-averaging (overrides the master-list avgflag)
'AIR_TEMP'    ← include AIR_TEMP with its master-list default flag
```

### 1.5 Accumulation (`hist_update_hbuf`)

`hist_update_hbuf(bounds)` (`HistFileMod.F90:1235`) is called each timestep. It walks every tape, then every field on each tape, dispatches to `hist_update_hbuf_field_1d` (`HistFileMod.F90:1271`) or `hist_update_hbuf_field_2d` (`HistFileMod.F90:1449`), which updates `tape(t)%hlist(f)%hbuf(:, :)` and the counter `nacs(:, :)` according to the per-field averaging flag.

Upstream of the tape system, `HistDataType::hist_update(this, I, J, bounds)` (`HistDataType.F90:3793`) is the function that populates the `h1D_*` / `h2D_*` pointer fields (several hundred of them) from live state, with per-area normalization (e.g., `h1D_ECO_HVST_C_col(ncol) = EcoHavstElmnt_CumYr_col(ielmc, NY, NX) / AREA_3D(3, NU_col(NY,NX), NY, NX)`, `HistDataType.F90:3823`).

### 1.6 File creation and write (`hist_htapes_wrapup`)

`hist_htapes_wrapup(rstwr, nlend, bounds, lnyr)` (`HistFileMod.F90:1661`) executes every timestep at end-of-step:

1. For each active tape, decides whether this step ends a history interval (`tape(t)%is_endhist`).
2. If yes, increment `tape(t)%ntimes`, and if it is the first sample create a new file via `htape_create` (`HistFileMod.F90:182`) and define dims/variables.
3. Normalize time-averaged fields (`hfields_normalize`, `HistFileMod.F90:2904`).
4. Write time-constant metadata (`htape_timeconst`, `HistFileMod.F90:1892`) and field data (`hfields_write`, `HistFileMod.F90:1929`).
5. Reset counters and buffers (`hfields_zero`, `HistFileMod.F90:2955`).
6. Close and roll over when `tape(t)%ntimes == tape(t)%mfilt`.

### 1.7 File naming

`set_hist_filename(hist_freq, hist_mfilt, hist_file)` (`HistFileMod.F90:2147`):

```
./{case_name}.ecosim.h{N-1}.{YYYY-MM}.nc            when hist_freq == 0 (monthly)
./{case_name}.ecosim.h{N-1}.{YYYY-MM-DD-SSSSS}.nc   otherwise
```

Example with `case_name='Blodget.ctrl'`:
```
./Blodget.ctrl.ecosim.h0.2012-01-31-00000.nc
./Blodget.ctrl.ecosim.h1.2012-01-31-00000.nc
```

### 1.8 NetCDF dimensions

`htape_create` (`HistFileMod.F90:182`) defines the following dimensions on every primary tape (`HistFileMod.F90:242-262`):

| Dim | Size | Source |
|---|---|---|
| `gridcell` | `bounds%ngrid` | `get_grid_info` |
| `topounit` | `bounds%ntopou` | |
| `column` | `bounds%ncols` | |
| `pft` | `bounds%npfts` | |
| `node` | `MaxNodesPerBranch` | `GridConsts` |
| `levsoi` | `JZ` | `GridConsts` |
| `levsno` | `JS` | `GridConsts` |
| `levcan` | `NumCanopyLayers` | |
| `npfts` | `JP` | |
| `nbranches` | `MaxNumBranches` | |
| `ngrstages` | `NumGrowthStages` | |
| `elements` | `NumPlantChemElms` | `ElmIDMod` |
| `rootaxs` | `MaxNumRootAxes` | |
| `nkinecomp` | `jsken` | `EcoSIMConfig` |
| `nomcomplx` | `jcplx` | `EcoSIMConfig` |
| `pmorphunits` | `NumOfPlantMorphUnits` | |
| `hist_interval` | 2 (non-restart only) | |
| `time` | unlimited (non-restart only) | |

### 1.9 Global attributes

`htape_create` writes global attributes (`HistFileMod.F90:232-238`): `title`, `source`, `source_id` (git version), `product='model-output'`, `case`, `username`, `hostname`, `git_version`.

---

## 2. Auxiliary `bhistMod` streams

`bhistMod.F90` provides a lightweight multi-clock writer. Type `histf_type` (`bhistMod.F90:27`) holds:

- `varnames(:)`, `varnamesl(:)`, `units(:)`, `var_type(:)` (state-vs-flux flag from `fileUtil::var_flux_type`, `var_state_type`).
- `hrfreq(:)` — per-variable clock assignment. Accepted values: `'hour'`, `'day'`, `'week'`, `'month'`, `'year'`. Parsed in `init` (`bhistMod.F90:117`).
- `yvals(:, :)` — per-column buffer.
- Five integer counters (`nh_vars`, `nd_vars`, `nw_vars`, `nm_vars`, `ny_vars`) and per-clock `nX_varid(:)`.

Public procedures (`bhistMod.F90:51-60`): `init`, `hist_wrap`, `histrst` (read/write checkpoint), plus privates `initAlloc`, `hist_create`, `hist_write`, `hist_add_var`, `proc_counter`, `reset_counter`, `proc_record`.

`histrst(gfname, rwflag, yymmddhhss)` (`bhistMod.F90:66`) writes/reads a restart file named `{gfname}.hr.{yymmddhhss}.nc` with two variables (`counters`, `vars`) over dimensions (`clocks=5`, `column=ncols`, `numvar=unlimited`).

`hist_wrap(yval, timer)` (`bhistMod.F90:290`) is the per-timestep entry point. Typical use pattern is a module-local `type(histf_type) :: mystream` initialized once and fed each timestep.

This subsystem is auxiliary. The primary flux-and-state output goes through `HistFileMod` / `HistDataType`.

---

## 3. `HistDataType.F90` — the pointer container

`histdata_type` (`HistDataType.F90:47`) is a large record with ~500 pointer fields grouped by dimensionality and domain:
- `h1D_*_col(:)` — 1D (column-indexed) scalars.
- `h1D_*_ptc(:)` — 1D (PFT-column) scalars.
- `h2D_*_vr(:, :)` — 2D (column, soil-layer) vertical profiles.
- `h2D_*_pvr(:, :)` — 2D (PFT-column, soil-layer) plant vertical profiles.
- `h2D_*_snvr(:, :)` — 2D (column, snow-layer).
- `h2D_*_plyr(:, :)` — 2D (column, canopy-layer).

Type-bound procedures (`HistDataType.F90:632-634`):
- `init => init_hist_data` — allocate every buffer at `spval`, register each via `hist_addfld1d` / `hist_addfld2d`.
- `hist_update` — populate buffers from live state each timestep (`HistDataType.F90:3793`).
- `ZeroPlantHistVars` (private) — zero plant-specific buffers at planting / re-establishment.

Singleton: `hist_ecosim` (`HistDataType.F90:637`).

### 3.1 Sampling cadence

`hist_update(this, I, J, bounds)` is the single call site that loads every buffer. Typical assignments (`HistDataType.F90:3816-3869`):

```fortran
this%h1D_cumFIRE_CO2_col(ncol) = CO2byFire_CumYr_col(NY,NX) / AREA_3D(3, NU_col(NY,NX), NY, NX)
this%h1D_ECO_HVST_N_col(ncol) = EcoHavstElmnt_CumYr_col(ielmn, NY, NX) / AREA_3D(3, NU_col(NY,NX), NY, NX)
this%h1D_Qdrain_col(ncol)     = m2mm * QDrain_col(NY,NX) / AREA_3D(3, NU_col(NY,NX), NY, NX)
this%h1D_CanSWRad_col(ncol)   = MJ2W * RadSW_Canopy_col(NY,NX) / AREA_3D(3, NU_col(NY,NX), NY, NX)
```

Note the per-area normalization (divide by column footprint) and unit conversions (`MJ2W = 1e6/3600`, `m2mm = 1000`, `million = 1e6`, `secs1hour = 3600`, all defined at `HistDataType.F90:3803-3806`).

Once populated, the tape engine (`HistFileMod::hist_update_hbuf`) reads from these pointers into the time-averaging `hbuf` arrays.

---

## 4. `ForcWriterMod.F90` — batch-BGC forcing dump

`WriteBBGCForc(doy, year)` (`ForcWriterMod.F90:33`) writes a one-shot NetCDF file when `(year, doy) == (bgc_forc_conf%year, bgc_forc_conf%doy)`. The configuration type (`ForcWriterMod.F90:19-25`):

```fortran
type :: bgc_forc_config_type
  logical :: laddband
  integer :: year
  integer :: doy
  integer :: layer
  character(len=64) :: bgc_fname
end type
```

Populated from the `&bbgcforc` namelist group (typically empty in the example runs, but present in every namelist: `examples/run_dir/blodgett/Blodget.ctrl.namelist:52-53`).

Output file (name given by `bgc_forc_conf%bgc_fname`) contains dimensions `jcplx`, `jsken`, `ndbiomcp`, `nlbiomcp`, `NumLiveAutoBioms`, `NumLiveHeterBioms`, `NumHetetr1MicCmplx`, `NumMicrobAutoTrophCmplx`, `element`, `ndoms` (`ForcWriterMod.F90:53-62`), and variables describing soil state (`pH`, `POROS`, `BKVL`, `FC`, `WP`, `CEC`, `AEC`, `XCEC`, `XAEC`, `CFE`, `CCA`, `CMG`, `CNA`, `CKA`, `CSO4`, `CCL`, `CAL`, `ZMG`, `ZNA`, `ZKA`, `CALPO`, etc.; see `ForcWriterMod.F90:63-120` for the first several and continuing through `ForcWriterMod.F90:284`).

Controlled by the public flag `do_bgcforc_write` (`ForcWriterMod.F90:28`).

---

## 5. Restart subsystem

### 5.1 Public interface

`RestartMod.F90` exposes (`RestartMod.F90:57-66`):

```fortran
character(len=8), public :: rest_opt = 'year'   ! 'never','ndays','nmonths','nyears'
integer,          public :: rest_frq = -999999999
public :: restFile           ! read or write a restart
public :: get_restart_date   ! parse stamp from a restart filename
```

Driven by the `&ecosim_time` namelist (`examples/run_dir/blodgett/Blodget.ctrl.namelist:56-64`):

```fortran
rest_opt='nyears'
rest_frq=1
delta_time=3600.
stop_n=82
stop_option='nyears'
diag_frq=1
diag_opt='nsteps'
```

### 5.2 Flow

`restFile(flag)` (`RestartMod.F90:70`) dispatches on `flag == 'read'` or `'write'`:

- **Write path**: `etimer%get_curr_date(yr, mon, day, tod)`, build stamp `YYYY-MM-DD-SSSSSS`, name the file via `restFile_filename(rdate)`, then call `restFile_write(bounds, filer, rdate)` (`RestartMod.F90:9476`).
- **Read path**: `restFile_getfile(fnamer, path)` (`RestartMod.F90:9133`) reads the persistent pointer file written by `restFile_write_pfile` (`RestartMod.F90:9265`), then `restFile_read(bounds, fnamer)` (`RestartMod.F90:9342`) restores state. `restFile_dimcheck` and `restFile_check_consistency` (`RestartMod.F90:9395`, `RestartMod.F90:9384`) validate grid consistency before reading.

### 5.3 What is checkpointed

`restFile_write` chains into numerous categorized sub-writers (the module has 9846 lines). The major per-category subroutine that reads or writes plant state is `restartnc_plant(ncid, flag)` (`RestartMod.F90:91`). Other major `restartnc`-family routines (per category, each calling `restartvar` hundreds of times) cover soil, snow, canopy, hydrology, microbial, chemistry, management, grid/topology, sediment, salt/ion, and time-manager state (`timemgr_restart_io`, `RestartMod.F90:9551`).

In addition, `hist_restart_ncd(bounds, ncid, flag, rdate)` (`HistFileMod.F90:2189`) checkpoints the history-tape accumulators so that tape sampling can resume mid-interval after a restart. `restFile_write` invokes this after state is written.

### 5.4 File naming

Naming is handled by `restFile_filename(rdate)` (not shown above, defined later in the file). The pattern, consistent with `set_hist_filename`, is:

```
./{case_name}.ecosim.r.{YYYY-MM-DD-SSSSSS}.nc            ← state restart
./{case_name}.ecosim.rh{N-1}.{YYYY-MM-DD-SSSSSS}.nc      ← history restart per tape (HistFileMod.F90:2329)
```

The "pointer file" written by `restFile_write_pfile(fnamer)` (`RestartMod.F90:9265`) and read by `restFile_read_pfile(pnamer)` (`RestartMod.F90:9298`) records the name of the most recent restart file, enabling transparent resume.

### 5.5 `restUtilMod` helpers

`restartvar` (`restUtilMod.F90:28`) is an overloaded interface. For each variable, a call such as

```fortran
call restartvar(ncid, flag, varname='TKS_vr', long_name='soil temperature', units='K', &
                interpinic_flag='interp', data=TKS_vr)
```

either defines the NetCDF variable and writes it (when `flag=='write'`), or reads and assigns (when `flag=='read'`), optionally routing through an interpolation helper if the stored grid differs from the current one (`iflag_interp` / `iflag_copy` / `iflag_skip` at `restUtilMod.F90:42-44`).

`cpcol` (column-by-column copy, `restUtilMod.F90:18-21`) and `cppft` (PFT-by-PFT copy, `restUtilMod.F90:23-26`) are overloaded for ranks 1-5, used when a stored variable's shape must be remapped onto the current run's decomposition.

---

## 6. Output-file summary

| Channel | Driver | Filename pattern | Cadence control |
|---|---|---|---|
| Primary history tape 0-5 | `HistFileMod::hist_htapes_wrapup` | `./{case}.ecosim.h{N-1}.{stamp}.nc` | `hist_nhtfrq`, `hist_mfilt`, `hist_fincl{N}`, `hist_fexcl{N}` |
| History restart per tape | `HistFileMod::hist_restart_ncd` | `./{case}.ecosim.rh{N-1}.{stamp}.nc` | Written alongside state restarts |
| State restart | `RestartMod::restFile('write')` | `./{case}.ecosim.r.{stamp}.nc` | `rest_opt`, `rest_frq` in `&ecosim_time` |
| Restart pointer | `RestartMod::restFile_write_pfile` | `rpointer.ecosim` (typical) | Updated on every restart write |
| Auxiliary `bhistMod` stream | `histf_type::hist_wrap` | `{gfname}.{clock}.nc` and `{gfname}.hr.{stamp}.nc` | Per-variable `hrfreq` |
| Batch BGC forcing | `ForcWriterMod::WriteBBGCForc` | `bgc_forc_conf%bgc_fname` | Triggered on `(year, doy, layer)` match |
| Text logs | `readimod::readi` | `{outdir}/logfile1`, `logfile2`, `logfile3` | Opened at init, appended throughout |
