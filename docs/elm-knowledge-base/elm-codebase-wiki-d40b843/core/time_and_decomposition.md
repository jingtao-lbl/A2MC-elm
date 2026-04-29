---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Time Manager, Domain, and Decomposition

ELM runtime is built around three interlocking concepts: a **time manager** that tracks model time (driven by ESMF), a **domain decomposition** that splits the global land grid across MPI tasks and OpenMP threads (`decompMod`, `decompInitMod`), and an **SPMD communication layer** that initializes MPI and broadcasts/gathers data (`spmdMod`, `spmdGathScatMod`). A number of small utility modules (`domainMod`, `accumulMod`, `abortutils`, `fileutils`, `getdatetime`, `SimpleMathMod`, `quadraticMod`, `elm_varorb`, `seq_drydep_mod_elm`) round out the core infrastructure.

**Status at d40b843 vs 60d9aad: VERIFIED UNCHANGED.** `utils/elm_time_manager.F90` (1886 lines), `main/decompMod.F90` (643 lines), and the surrounding utility modules are byte-for-byte identical between the two commits. All file/line citations below remain valid.

## 1. Time manager: `elm_time_manager` and `timeinfoMod`

### 1.1 ESMF-based clock

`elm_time_manager` (`utils/elm_time_manager.F90`, 1886 lines) wraps the ESMF clock and calendar API. Two calendars are supported (`utils/elm_time_manager.F90:62-63`):

```fortran
character(len=*), public, parameter :: NO_LEAP_C   = 'NO_LEAP'
character(len=*), public, parameter :: GREGORIAN_C = 'GREGORIAN'
```

The default is `NO_LEAP_C` (`utils/elm_time_manager.F90:69-70`), meaning **ELM uses a 365-day year by default with no leap days**. February always has 28 days, so `days_per_mon = (/31,28,31,30,31,30,31,31,30,31,30,31/)` in `timeinfoMod` (`main/timeinfoMod.F90:14`).

### 1.2 Key public entry points

| Routine | Purpose |
|---|---|
| `get_timemgr_defaults(...)` | Retrieve default calendar, start/stop/ref dates, `nelapse`. |
| `set_timemgr_init(...)` | Set startup values before `timemgr_init` runs. |
| `timemgr_init()` | Build the ESMF calendar, start/stop/ref/curr dates, and `tm_clock`. |
| `timemgr_restart_io(ncid, flag)` | Read/write time-manager state to restart file. |
| `timemgr_restart()` | Apply restart state after I/O. |
| `timemgr_datediff(ymd1, tod1, ymd2, tod2, days)` | Compute elapsed time between two ESMF dates. |
| `advance_timestep()` | Increment `tm_clock` one step. |
| `get_clock(clock)` | Retrieve a copy of `tm_clock`. |
| `get_curr_date(yr, mon, day, tod, offset)` | End-of-current-step date. |
| `get_prev_date(yr, mon, day, tod)` | Start-of-current-step date. |
| `get_curr_time(days, seconds)` | Elapsed time since reference date. |
| `get_start_date` / `get_ref_date` / `get_rest_date` | Read start, reference, restart dates. |
| `get_step_size()` | Timestep size in seconds (integer). |
| `get_nstep()` | Current step number. |
| `get_curr_calday()` / `get_calday()` | Fractional calendar day for radiation/phenology. |
| `get_days_per_year()` | Days per current year (365 for NO_LEAP). |
| `is_first_step()`, `is_first_restart_step()`, `is_end_curr_day()`, `is_end_curr_month()`, `is_end_curr_year()`, `is_last_step()`, `is_beg_curr_day()` | Common time predicates. |
| `set_nextsw_cday(nextsw_cday_in)` | Tell time manager the next radiation calendar day. |
| `update_rad_dtime(doalb)` | Tracking of radiation interval via `nstep`. |
| `timemgr_reset()` | Free ESMF objects and reset module state. |

Internal state lives in module-level `save` variables (`utils/elm_time_manager.F90:69-113`): the ESMF calendar `tm_cal`, master clock `tm_clock`, perpetual date, `dtime`, `dtime_rad`, `nstep_rad_prev`, start/stop/ref dates in `YYYYMMDD` integer form, restart state, and `tm_first_restart_step`.

### 1.3 `timemgr_init` sequence

`timemgr_init()` (`utils/elm_time_manager.F90:209-321`) runs in this order:

1. `timemgr_spmdbcast()` — broadcast namelist values from masterproc.
2. `init_calendar()` — create the ESMF calendar object (`NO_LEAP` by default).
3. Create `start_date` from `start_ymd`/`start_tod` via `TimeSetymd`.
4. Set `curr_date = start_date`.
5. Create `stop_date` from `stop_ymd`/`stop_tod` or from `nelapse` (must supply one; otherwise abort).
6. Validate `stop_date > start_date > curr_date`.
7. Create `ref_date` from `ref_ymd`/`ref_tod` (defaults to `start_date`).
8. Call `init_clock(start_date, ref_date, curr_date, stop_date)` to build `tm_clock` with `ESMF_ClockCreate` (`utils/elm_time_manager.F90:347`).
9. Print configuration via `timemgr_print()`.

### 1.4 `timeinfoMod`: GPU-friendly time state

`timeinfoMod` (`main/timeinfoMod.F90`, 76 lines) is a small GPU-visible mirror of the time manager. It holds scalar time state (`year_curr`, `mon_curr`, `day_curr`, `secs_curr`, `nstep_mod`, `jday_mod`, `thiscalday_mod`, `nextsw_cday_mod`, `end_cd_mod`, `doalb`) that an OpenACC kernel can read via the `!$acc declare copyin(...)` directive (`main/timeinfoMod.F90:20-22`). The `increment_time_vars()` routine (marked `!$acc routine seq`) advances the integer state by `dtime_mod` seconds on device, wrapping using the hard-coded 365-day year.

## 2. SPMD initialization: `spmdMod`

`spmdMod` (`utils/spmdMod.F90`, 107 lines) is a thin MPI wrapper exposing module-level scalars used throughout ELM:

```fortran
logical, public :: masterproc   ! true on rank 0
integer, public :: iam          ! MPI rank
integer, public :: npes         ! number of MPI tasks
integer, public :: mpicom       ! ELM's MPI communicator
integer, public :: comp_id      ! driver component id
```

(`utils/spmdMod.F90:29-33`.) The only public subroutine is `spmd_init(clm_mpicom, LNDID)` (`utils/spmdMod.F90:64-105`), called once during driver init.

## 3. `spmdGathScatMod`: gather/scatter

`spmdGathScatMod` (`utils/spmdGathScatMod.F90`, 536 lines) provides `scatter_data_from_master` and `gather_data_to_master` generic interfaces (`utils/spmdGathScatMod.F90:27-35`), each with four variants (1D-int, 1D-real). They wrap MCT's gsmap-based gather/scatter for the registered ELM levels (`nameg`, `namet`, `namel`, `namec`, `namep`).

## 4. Domain decomposition: `decompMod` / `decompInitMod`

### 4.1 The bounds structure

`decompMod` (`main/decompMod.F90`, 643 lines) defines the subgrid bounds structure that every physics routine uses (`main/decompMod.F90:69-97`):

```fortran
type bounds_type
   integer :: begg, endg     ! gridcell
   integer :: begt, endt     ! topographic unit
   integer :: begl, endl     ! landunit
   integer :: begc, endc     ! column
   integer :: begp, endp     ! patch (pft)
   integer :: begCohort, endCohort

   integer :: begg_ghost, endg_ghost    ! ghost/halo bounds
   integer :: begt_ghost, endt_ghost
   ...

   integer :: begg_all, endg_all        ! local + ghost
   ...

   integer :: level          ! BOUNDS_LEVEL_PROC or BOUNDS_LEVEL_CLUMP
   integer :: clump_index
end type bounds_type
```

Six integer constants `BOUNDS_SUBGRID_GRIDCELL .. BOUNDS_SUBGRID_COHORT` (`main/decompMod.F90:21-26`) identify subgrid levels for the generic `get_beg(bounds, subgrid_level)` / `get_end(bounds, subgrid_level)` accessors. Two integer constants `BOUNDS_LEVEL_PROC = 1`, `BOUNDS_LEVEL_CLUMP = 2` distinguish proc-wide vs clump-local bounds.

### 4.2 `procinfo` and `clumps`

The module-level `procinfo` (type `processor_type`, `main/decompMod.F90:100-147`) holds this rank's bounds at every subgrid level, its clump count `nclumps` and the clump indices (`cid(:)`), plus ghost/halo bounds. The global array `clumps(:)` (type `clump_type`) records owning PE, sizes, and beg/end indices for each clump. Global totals `numg`, `numt`, `numl`, `numc`, `nump`, `numCohort` are exported.

`ldecomp` is a `decomp_type` holding the `gdc2glo(:)` mapping. Six MCT `gsMap` objects map each subgrid level to MCT's global segment space.

### 4.3 Accessors

The two flavors of `get_proc_bounds` and `get_clump_bounds` support both "new style" (one `bounds_type` argument) and "old style" (many optional scalar arguments). Physics loops typically look like:

```fortran
call get_proc_bounds(bounds)
do p = bounds%begp, bounds%endp
   ...
end do
```

Other accessors: `get_proc_total`, `get_proc_total_ghosts`, `get_proc_global`, `get_elmlevel_gsize`, `get_elmlevel_gsmap`, `get_proc_clumps`.

### 4.4 Decomposition build: `decompInitMod`

`decompInitMod` (`main/decompInitMod.F90`, ~2230 lines) contains the public initializers:

- `decompInit_lnd(lni, lnj, amask)` — Build gridcell-level decomposition from the global land mask. Clumps are allocated round-robin across PEs (`clump_pproc` clumps per task; defaults to `omp_get_max_threads()` in OpenMP builds).
- `decompInit_lnd_using_gp(...)` — Graph-partitioning variant (ParMETIS).
- `decompInit_lnd_simple(...)` — Simple `numg / nclumps` decomposition.
- `decompInit_clumps(...)` — Initialize clump structure once gridcell assignment is known.
- `decompInit_gtlcp(...)` — Populate the g/t/l/c/p counts per clump after subgrid weights are known.
- `decompInit_ghosts(...)` — Initialize the ghost/halo bounds for lateral-flow simulations.
- `decompInit_moab(...)` — MOAB-mesh-based variant when compiled with `HAVE_MOAB`.

## 5. The domain type: `domainMod`

`domainMod` (`utils/domainMod.F90`, 355 lines) defines `type(domain_type)` and the module-level `ldomain`. Fields: `ns`, `ni`/`nj`, `isgrid2d`, `nbeg`/`nend`, `elmlevel`, `mask(:)`, `frac(:)`, `topo(:)`, `latc(:)`/`lonc(:)`, vertex arrays, `area(:)`, `pftm(:)`, `glcmask(:)`, `num_tunits_per_grd(:)`, and (for the TOP solar parameterization) `stdev_elev`, `sky_view`, `terrain_config`, `sinsl_cosas`, `sinsl_sinas`. `domain_init` allocates and NaN-initializes; `domain_clean` deallocates; `domain_check` prints summary. `ldomain` is populated by `surfrdMod::surfrd_get_grid`.

## 6. Lateral connectivity: `domainLateralMod`

`domainLateralMod` (`utils/domainLateralMod.F90`, 613 lines, all gated by `#ifdef USE_PETSC_LIB`) provides a PETSc-based framework for inter-PE data exchange needed by lateral subsurface flow. Defines `type(domainlateral_type)` wrapping an unstructured grid, a 1-DOF PETSc DM, and an `nlevgrnddof` DM. Gated on the namelist flag `lateral_connectivity` from `controlMod`.

## 7. Accumulators: `accumulMod`

`accumulMod` (`main/accumulMod.F90`, 626 lines) provides generic time-accumulation of user-specified fields over user-defined periods. The internal `accum_field` type holds name, description, units, `acctype` (`timeavg`/`runmean`/`runaccum`), `type1d`, `beg1d`/`end1d`, `numlev`, `initval`, `val(:,:)`, and `period`. Public API:

- `init_accum_field(name, units, desc, accum_type, accum_period, numlev, subgrid_type, init_value, type2d)` — register a new accumulator.
- `update_accum_field(name, field, nstep)` — add a sample (1D and 2D).
- `extract_accum_field(name, field, nstep)` — read current accumulated value.
- `print_accum_fields()` — debug print.
- `accumulRest(ncid, flag)` — restart I/O.

`accumResetVal = -99999._r8` is a sentinel used in `runaccum` fields to trigger annual reset. CN phenology uses `runmean` accumulators for 10-day temperature and 30-day soil moisture.

## 8. Error handling, timing, and I/O utilities

- `abortutils` (`main/abortutils.F90`, 81 lines): `endrun_vanilla(msg)` writes to `iulog` and calls `shr_sys_abort`. `endrun_globalindex(decomp_index, elmlevel, msg)` first calls `GetGlobalWrite` to dump gridcell/landunit/column/patch context.
- `GetGlobalValuesMod` (`main/GetGlobalValuesMod.F90`, 219 lines): `GetGlobalIndex(decomp_index, elmlevel)`, `GetGlobalIndexArray(...)`, `GetGlobalWrite(decomp_index, elmlevel)`. Maps local decomp index to global via MCT's `mct_gsMap_orderedPoints`.
- `perfMod_GPU` (`main/perfMod_GPU.F90`, 31 lines): `t_start_lnd(event)` and `t_stop_lnd(event)` short-circuit under `_OPENACC`.
- `fileutils` (`utils/fileutils.F90`, 179 lines): `get_filename`, `opnfil`, `getfil`, `getavu`, `relavu`.
- `getdatetime(cdate, ctime)` (`utils/getdatetime.F90`): wraps Fortran `date_and_time` on masterproc and broadcasts.

## 9. Math utilities

- `SimpleMathMod` (`utils/SimpleMathMod.F90`, 261 lines): `array_normalization`, `array_div_vector`. All `!$acc routine seq`.
- `quadraticMod` (`utils/quadraticMod.F90`, 57 lines): `quadratic(a, b, c, r1, r2)` numerically-stable Press et al. (1986) formulation. Used by photosynthesis and stomatal-conductance solvers.

## 10. Small data modules

- `elm_varorb` (`utils/elm_varorb.F90`, 17 lines) holds Earth orbital parameters: `eccen`, `obliqr`, `lambm0`, `mvelpp`. Set by the driver, consumed by ELM's insolation calculation.
- `seq_drydep_mod_elm` (`utils/seq_drydep_mod_elm.F90`, 916 lines) is ELM's local copy of the shared `seq_drydep_mod`. `drydep_method` is one of `DD_XATM = 'xactive_atm'`, `DD_XLND = 'xactive_lnd'`, `DD_TABL = 'table'` (default `DD_XLND`).

## 11. How a physics routine sees decomposition

```fortran
subroutine mysub(bounds, ...)
  use decompMod, only: bounds_type
  type(bounds_type), intent(in) :: bounds
  integer :: p, c, g
  ...
  do p = bounds%begp, bounds%endp
    c = veg_pp%column(p)
    g = col_pp%gridcell(c)
    ! operate on veg_pp(p), col_pp(c), grc_pp(g)
  end do
end subroutine
```

The caller (`elm_driver` or a clump loop) obtains `bounds` from `get_proc_bounds(bounds)` (full rank extent) or `get_clump_bounds(nc, bounds_clump)` (one clump at a time, inside `!$OMP PARALLEL DO`). Each clump is a contiguous range of every subgrid level, so loops address dense, thread-private slices without extra indexing.
