---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Time Manager, Domain, and Decomposition

ELM runtime is built around three interlocking concepts: a **time manager** that tracks model time (driven by ESMF), a **domain decomposition** that splits the global land grid across MPI tasks and OpenMP threads (`decompMod`, `decompInitMod`), and an **SPMD communication layer** that initializes MPI and broadcasts/gathers data (`spmdMod`, `spmdGathScatMod`). A number of small utility modules (`domainMod`, `accumulMod`, `abortutils`, `fileutils`, `getdatetime`, `SimpleMathMod`, `quadraticMod`, `elm_varorb`, `seq_drydep_mod_elm`) round out the core infrastructure.

## 1. Time manager: `elm_time_manager` and `timeinfoMod`

### 1.1 ESMF-based clock

`elm_time_manager` (utils/elm_time_manager.F90, 1886 lines) wraps the ESMF clock and calendar API. Two calendars are supported (utils/elm_time_manager.F90:62-63):

```fortran
character(len=*), public, parameter :: NO_LEAP_C   = 'NO_LEAP'
character(len=*), public, parameter :: GREGORIAN_C = 'GREGORIAN'
```

The default is `NO_LEAP_C` (utils/elm_time_manager.F90:69-70), meaning **ELM uses a 365-day year by default with no leap days**. This is a critical detail for any day-of-year calculations: February always has 28 days, so `days_per_mon = (/31,28,31,30,31,30,31,31,30,31,30,31/)` in `timeinfoMod` (main/timeinfoMod.F90:14).

### 1.2 Key public entry points

The module's public interface is explicit (utils/elm_time_manager.F90:15-60). Most commonly used:

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
| `is_first_step()`, `is_first_restart_step()`, `is_end_curr_day()`, `is_end_curr_month()`, `is_end_curr_year()`, `is_last_step()` | Common time predicates. |
| `set_nextsw_cday(nextsw_cday_in)` | Tell time manager the next radiation calendar day (set by driver/coupler). |
| `update_rad_dtime(doalb)` | Tracking of radiation interval via `nstep`. |
| `timemgr_reset()` | Free ESMF objects and reset module state. |

Internal state lives in module-level `save` variables (utils/elm_time_manager.F90:69-113): the ESMF calendar `tm_cal`, the master clock `tm_clock`, the perpetual date, `dtime`, `dtime_rad`, `nstep_rad_prev`, start/stop/ref dates in `YYYYMMDD` integer form, the private data needed to round-trip the clock through a restart (`rst_start_ymd`, `rst_curr_ymd`, `rst_step_sec`, etc.), and `tm_first_restart_step` for one-shot first-restart logic.

### 1.3 `timemgr_init` sequence

`timemgr_init()` (utils/elm_time_manager.F90:209-321) runs in this order:

1. `timemgr_spmdbcast()` — broadcast namelist values from masterproc.
2. `init_calendar()` — create the ESMF calendar object (`NO_LEAP` by default).
3. Create `start_date` from `start_ymd`/`start_tod` via `TimeSetymd`.
4. Set `curr_date = start_date`.
5. Create `stop_date` from `stop_ymd`/`stop_tod` or from `nelapse` (must supply one; otherwise abort).
6. Validate `stop_date > start_date > curr_date`.
7. Create `ref_date` from `ref_ymd`/`ref_tod` (defaults to `start_date`).
8. Call `init_clock(start_date, ref_date, curr_date, stop_date)` to build `tm_clock` with `ESMF_ClockCreate` (utils/elm_time_manager.F90:347).
9. Print configuration via `timemgr_print()`.

### 1.4 `timeinfoMod`: GPU-friendly time state

`timeinfoMod` (main/timeinfoMod.F90, 76 lines) is a small GPU-visible mirror of the time manager. It holds scalar time state (`year_curr`, `mon_curr`, `day_curr`, `secs_curr`, `nstep_mod`, `jday_mod`, `thiscalday_mod`, `nextsw_cday_mod`, `end_cd_mod`, `doalb`) that an OpenACC kernel can read via the `!$acc declare copyin(...)` directive (main/timeinfoMod.F90:20-22). The `increment_time_vars()` routine (marked `!$acc routine seq`) advances the integer state by `dtime_mod` seconds on device, wrapping to the next day/month/year using the hard-coded 365-day year. This is only used in OpenACC code paths; CPU code uses `elm_time_manager` directly.

## 2. SPMD initialization: `spmdMod`

`spmdMod` (utils/spmdMod.F90, 107 lines) is a thin MPI wrapper that exposes module-level scalars used throughout ELM:

```fortran
logical, public :: masterproc   ! true on rank 0
integer, public :: iam          ! MPI rank
integer, public :: npes         ! number of MPI tasks
integer, public :: mpicom       ! ELM's MPI communicator
integer, public :: comp_id      ! driver component id
```

(utils/spmdMod.F90:29-33.) It also re-exports the common `MPI_*` constants from `mpif.h` (utils/spmdMod.F90:43-54) so other modules can `use spmdMod` without also including the mpif header.

The only public subroutine is `spmd_init(clm_mpicom, LNDID)` (utils/spmdMod.F90:64-105), called exactly once during driver initialization. It stores the communicator, calls `mpi_comm_rank` to set `iam` (and `masterproc = (iam == 0)`), and `mpi_comm_size` to set `npes`. From this point on, any module can consult `spmdMod::masterproc` to gate I/O and `spmdMod::iulog`-bound writes, and call `mpi_bcast`/`mpi_reduce` directly with `mpicom`.

## 3. `spmdGathScatMod`: gather/scatter

`spmdGathScatMod` (utils/spmdGathScatMod.F90, 536 lines) provides `scatter_data_from_master` and `gather_data_to_master` generic interfaces (utils/spmdGathScatMod.F90:27-35), each with four variants: `scatter_1darray_int`, `scatter_1darray_real`, `gather_1darray_int`, `gather_1darray_real`. These wrap MCT's gsmap-based gather/scatter for the registered ELM levels (`nameg`, `namet`, `namel`, `namec`, `namep`) via `get_elmlevel_gsmap` from `decompMod`. They are used primarily by surface-dataset readers (`surfrdMod`) and file-based I/O paths where masterproc holds the global array and needs to push it to each task's local slice.

## 4. Domain decomposition: `decompMod` / `decompInitMod`

### 4.1 The bounds structure

`decompMod` (main/decompMod.F90, 643 lines) defines the subgrid bounds structure that every physics routine uses. The core type (main/decompMod.F90:69-97) is:

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

The six integer constants `BOUNDS_SUBGRID_GRIDCELL .. BOUNDS_SUBGRID_COHORT` (main/decompMod.F90:21-26) identify subgrid levels for the generic `get_beg(bounds, subgrid_level)` / `get_end(bounds, subgrid_level)` accessors (main/decompMod.F90:190-273). The two integer constants `BOUNDS_LEVEL_PROC = 1`, `BOUNDS_LEVEL_CLUMP = 2` distinguish proc-wide vs clump-local bounds.

### 4.2 `procinfo` and `clumps`

The module-level `procinfo` (type `processor_type`, main/decompMod.F90:100-147) holds this rank's bounds at gridcell/topounit/landunit/column/patch/cohort level, its clump count `nclumps` and the clump indices it owns (`cid(:)`), plus ghost/halo bounds. The global array `clumps(:)` (type `clump_type`, main/decompMod.F90:151-167) is allocated during decomposition and records for each clump: owning PE, sizes at each subgrid level, and beg/end indices. Global totals `numg`, `numt`, `numl`, `numc`, `nump`, `numCohort` are also exported (main/decompMod.F90:62-67).

`ldecomp` is a `decomp_type` (main/decompMod.F90:172-176) holding the `gdc2glo(:)` mapping from ELM-decomposed-compressed index to the 1D global sn-ordered index. Six MCT `gsMap` objects (main/decompMod.F90:178-184) map gridcells, topounits, landunits, columns, patches, and cohorts to the MCT global segment space used by the coupler and by `spmdGathScatMod`.

### 4.3 Accessors

The two flavors of `get_proc_bounds` and `get_clump_bounds` (main/decompMod.F90:44-54) support both "new style" (one `bounds_type` argument) and "old style" (many optional scalar arguments). The new form (main/decompMod.F90:379-447) simply copies `procinfo` into the caller's `bounds_type`. Physics loops typically look like:

```fortran
call get_proc_bounds(bounds)
do p = bounds%begp, bounds%endp
   ...
end do
```

Other accessors: `get_proc_total`, `get_proc_total_ghosts`, `get_proc_global`, `get_elmlevel_gsize`, `get_elmlevel_gsmap`, `get_proc_clumps` (main/decompMod.F90:36-42, 476-642).

### 4.4 Decomposition build: `decompInitMod`

`decompInitMod` (main/decompInitMod.F90, 2230 lines) contains the public initializers (main/decompInitMod.F90:31-36):

- `decompInit_lnd(lni, lnj, amask)` — Build gridcell-level decomposition from the global land mask. This is a **1D task layout with 2D optional segments**: clumps are allocated round-robin across PEs (`clump_pproc` clumps per task), and land gridcells are assigned to clumps either one-to-one (`seglen1 = .true.`) or in segments of length `numg / (nsegspc * nclumps)` (main/decompInitMod.F90:186-220+). The number of clumps per processor (`clump_pproc`) defaults to 1 in non-OpenMP builds and `omp_get_max_threads()` otherwise (main/controlMod.F90:346-350), so each OpenMP thread gets its own clump and can run physics loops with thread-private bounds.
- `decompInit_lnd_using_gp(...)` — Graph-partitioning variant (ParMETIS) for more balanced decomposition when lateral connectivity is active.
- `decompInit_lnd_simple(...)` — Simple `numg / nclumps` decomposition with no mask-aware optimization.
- `decompInit_clumps(...)` — Initialize clump structure once gridcell assignment is known.
- `decompInit_gtlcp(...)` — Populate the g/t/l/c/p (gridcell → topounit → landunit → column → patch) counts per clump after subgrid weights are known.
- `decompInit_ghosts(...)` — Initialize the ghost/halo bounds for lateral-flow simulations.

### 4.5 The 1D task layout and how bounds flow

`decompInit_lnd` first validates `nclumps = clump_pproc * npes >= npes`, allocates `procinfo%cid(clump_pproc)` and the global `clumps(nclumps)` array, initializes every subgrid begin to 1 and every end to 0 (main/decompInitMod.F90:95-146), then walks the global land grid:

1. Assigns each of the `nclumps` clumps to a PE via `pid = mod(n-1, npes)` (main/decompInitMod.F90:149-165).
2. Walks the mask and assigns each land point to a clump based on `nsegspc` (main/decompInitMod.F90:208-220+).
3. Builds the `ldecomp%gdc2glo` mapping and the MCT `gsMap_lnd_gdc2glo`.

After `decompInit_lnd` builds gridcell bounds, and after `surfrdMod::surfrd_get_data` populates subgrid weights, `decompInit_gtlcp` walks every clump and totals its topounits, landunits, columns, and patches to fill the `begt/endt`, `begl/endl`, `begc/endc`, `begp/endp` fields in each clump. These are then rolled up into `procinfo` so that `get_proc_bounds` returns sensible rank-wide limits.

## 5. The domain type: `domainMod`

`domainMod` (utils/domainMod.F90, 355 lines) defines `type(domain_type)` (utils/domainMod.F90:23-63) and the module-level `ldomain` (utils/domainMod.F90:65). Fields: `ns` (global size), `ni`/`nj` (2D axis), `isgrid2d`, `nbeg`/`nend` (local beg/end), `elmlevel` tag, `mask(:)`, `frac(:)`, `topo(:)`, `latc(:)`/`lonc(:)` (1D), vertex arrays `latv(:,:)`/`lonv(:,:)` (for unstructured grids), `area(:)`, `pftm(:)` (pft mask), `glcmask(:)`, `num_tunits_per_grd(:)`, and (for the TOP solar parameterization) `stdev_elev`, `sky_view`, `terrain_config`, `sinsl_cosas`, `sinsl_sinas`. `domain_init` (utils/domainMod.F90:88) allocates and NaN-initializes a domain; `domain_clean` deallocates; `domain_check` prints summary. `ldomain` is the master handle for the currently-decomposed land domain, populated by `surfrdMod::surfrd_get_grid`.

## 6. Lateral connectivity: `domainLateralMod`

`domainLateralMod` (utils/domainLateralMod.F90, 613 lines, all gated by `#ifdef USE_PETSC_LIB`) provides a PETSc-based framework for inter-PE data exchange needed by lateral subsurface flow. It defines `type(domainlateral_type)` (utils/domainLateralMod.F90:37-44) wrapping an unstructured grid, a 1-DOF PETSc DM, and an `nlevgrnddof` DM. `domainlateral_init` (utils/domainLateralMod.F90:63) consumes the raw `cellsOnCell`, `edgesOnCell`, `dcEdge`, `dvEdge`, `areaCell` arrays read by `surfrdMod::surfrd_get_grid_conn` and builds an unstructured-grid object. `ExchangeColumnLevelGhostData` handles ghost-column data exchanges. Gated on the namelist flag `lateral_connectivity` from `controlMod` (main/controlMod.F90:300-301).

## 7. Accumulators: `accumulMod`

`accumulMod` (main/accumulMod.F90, 626 lines) provides generic time-accumulation of user-specified fields over user-defined periods. The internal type `accum_field` (main/accumulMod.F90:48-62) holds name, description, units, `acctype` (`timeavg`/`runmean`/`runaccum`), `type1d` (subgrid tag), `beg1d`/`end1d`, `numlev`, `initval`, `val(:,:)`, and `period` (steps between resets). The public API (main/accumulMod.F90:31-44) is:

- `init_accum_field(name, units, desc, accum_type, accum_period, numlev, subgrid_type, init_value, type2d)` — register a new accumulator (main/accumulMod.F90:75).
- `update_accum_field(name, field, nstep)` — add a new sample (generic interface over 1D and 2D, main/accumulMod.F90:41-44, 376).
- `extract_accum_field(name, field, nstep)` — read current accumulated value (generic over 1D/2D, main/accumulMod.F90:37-40).
- `print_accum_fields()` — debug print.
- `accumulRest(ncid, flag)` — restart I/O for all registered accumulators.

The constant `accumResetVal = -99999._r8` (main/accumulMod.F90:64) is a sentinel used in `runaccum` fields to trigger an annual reset. CN phenology uses `runmean` accumulators for 10-day temperature and 30-day soil moisture.

## 8. Error handling, timing, and I/O utilities

- `abortutils` (main/abortutils.F90, 81 lines) exposes an `endrun` generic interface (main/abortutils.F90:15-18). `endrun_vanilla(msg)` writes the message to `iulog` and calls `shr_sys_abort`. `endrun_globalindex(decomp_index, elmlevel, msg)` first calls `GetGlobalWrite` to dump gridcell/landunit/column/patch context before aborting. This is the standard ELM abort path — every module uses `call endrun(msg=...)` after a failed consistency check.
- `GetGlobalValuesMod` (main/GetGlobalValuesMod.F90, 219 lines) exposes `GetGlobalIndex(decomp_index, elmlevel)`, `GetGlobalIndexArray(...)`, and `GetGlobalWrite(decomp_index, elmlevel)`. These use `get_elmlevel_gsmap` and MCT's `mct_gsMap_orderedPoints` to map a local decomp index to the global index. `GetGlobalWrite` prints the full context (local index, global index, gridcell lat/lon, landunit/column/pft type) for the abort diagnostics emitted by `endrun_globalindex`.
- `perfMod_GPU` (main/perfMod_GPU.F90, 31 lines) provides `t_start_lnd(event)` and `t_stop_lnd(event)` that wrap `perf_mod::t_startf` and `t_stopf` but short-circuit the call under `_OPENACC` so that GPU kernels can include timing instrumentation without calling into the CPU-only timing library.
- `fileutils` (utils/fileutils.F90, 179 lines) exposes `get_filename(fulpath)` (strip directory), `opnfil`, `getfil` (fetch a local copy via `shr_file_get`), `getavu` (get an available Fortran unit number), `relavu` (release a unit). Used everywhere that opens a file.
- `getdatetime(cdate, ctime)` (utils/getdatetime.F90, 53 lines) — subroutine (not in a module) that wraps Fortran `date_and_time` on masterproc and broadcasts the formatted strings. Used by history/restart file metadata ("created on MM/DD/YY HH:MM:SS").

## 9. Math utilities

- `SimpleMathMod` (utils/SimpleMathMod.F90, 261 lines) provides small array routines: `array_normalization` (generic over 2D and 2D-with-filter, utils/SimpleMathMod.F90:12-14) normalizes an array along a specified dimension so each slice sums to 1. `array_div_vector` divides a 2D array by a 1D denominator column-wise, with or without a filter. All routines are marked `!$acc routine seq` for GPU use.
- `quadraticMod` (utils/quadraticMod.F90, 57 lines) — single routine `quadratic(a, b, c, r1, r2)` that solves `a*x^2 + b*x + c = 0` using the numerically-stable Press et al. (1986) formulation (utils/quadraticMod.F90:14-55). It calls `endrun` if `a == 0`. Widely used by the photosynthesis and stomatal-conductance solvers.

## 10. Small data modules

- `elm_varorb` (utils/elm_varorb.F90, 17 lines) holds four module-level scalars describing Earth orbital parameters: `eccen` (eccentricity), `obliqr` (obliquity, radians), `lambm0` (mean longitude of perihelion at vernal equinox), `mvelpp` (moving vernal equinox longitude of perihelion + pi). These are set by the driver's orbital-parameter routine and consumed by ELM's insolation calculation.
- `seq_drydep_mod_elm` (utils/seq_drydep_mod_elm.F90, 916 lines) is ELM's local copy of the shared `seq_drydep_mod` for dry-deposition of tracers. Public interface `seq_drydep_readnl` reads the `drydep_nml` namelist, `seq_drydep_init` sets up tables, and `seq_drydep_setHCoeff` computes Henry's-law coefficients. Key module-level state includes `drydep_method` (one of `DD_XATM = 'xactive_atm'`, `DD_XLND = 'xactive_lnd'`, `DD_TABL = 'table'`; default `DD_XLND`, utils/seq_drydep_mod_elm.F90:46-49), `n_drydep`, and the `drydep_list(maxspc)` array.

## 11. How a physics routine sees decomposition

Putting it together: a typical ELM physics routine uses the following pattern (seen e.g. in `PhotosynthesisMod`, `CNCarbonFluxType`, `SoilHydrologyMod`):

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

The caller (usually `elm_driver` or a clump loop in `elm_driver.F90`) obtained `bounds` either from `get_proc_bounds(bounds)` (full rank extent) or from `get_clump_bounds(nc, bounds_clump)` (one clump at a time, inside an `!$OMP PARALLEL DO` loop — see for example the `reweight_wrapup` loop at main/restFileMod.F90:525-531). Because each clump is a contiguous range of every subgrid level, loops like `do p = bounds%begp, bounds%endp` address a dense, thread-private slice of the column/patch/landunit arrays without any additional indexing machinery.
