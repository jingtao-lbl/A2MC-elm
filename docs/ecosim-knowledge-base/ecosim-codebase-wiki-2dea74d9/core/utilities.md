---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** core orchestration: `f90src/{Main, Ecosim_mods, Modelconfig, Modelpars, Mesh, Utils, Minimath, DebugTools}/`
**Last verified:** 2026-04-24
---

# Utilities, Math, and Debug Infrastructure

This doc covers three sibling directories of low-level plumbing. Everything here is called by higher-level physics/BGC/transport modules — nothing here knows about plants or soil processes.

| Directory | Files | Role |
|---|---|---|
| `f90src/Utils/` | 14 Fortran + 2 C + 1 header | Precision kinds, constants, time, I/O, logging, timing, units |
| `f90src/Minimath/` | 3 Fortran | Safe arithmetic, sparse linear algebra, small physical functions |
| `f90src/DebugTools/` | 1 Fortran | Verbose print helpers gated by `lverb` |

## 1. `Utils/` — grouped by function

### 1.1 Precision and physical constants (small foundational modules)

**`Utils/data_kind_mod.F90`** (26 lines). Precision kind parameters (f90src/Utils/data_kind_mod.F90:9-18): `DAT_KIND_R8` (8-byte real, `selected_real_kind(12)`), `DAT_KIND_R4`, `DAT_KIND_RN` (native real), `DAT_KIND_I8`, `DAT_KIND_I4`, `DAT_KIND_IN`, plus string-length parameters `DAT_KIND_CS=80`, `DAT_KIND_CL=256`, `DAT_KIND_CX=512`, `DAT_KIND_CXX=4096`. Every module in EcoSIM aliases `r8 => DAT_KIND_R8`. Also declares `type yearIJ_type` at :20-24 with fields `year`, `i`, `j` — used by `AdvanceModelOneYear` to bundle the triple (year, day-of-year, hour-of-day) into a single argument.

**`Utils/data_const_mod.F90`** (65 lines). Physical constants, CCSM `shr_const`-style (f90src/Utils/data_const_mod.F90:19-63). Earth geometry (`DAT_CONST_REARTH`, `DAT_CONST_OMEGA`, `DAT_CONST_G=9.80616`), thermodynamic constants (`DAT_CONST_BOLTZ`, `DAT_CONST_AVOGAD`, `DAT_CONST_RGAS`, `DAT_CONST_MWDAIR=28.966`, `DAT_CONST_MWWV=18.016`, derived `DAT_CONST_RDAIR`, `DAT_CONST_RWV`, `DAT_CONST_ZVIR`), reference T/P (`DAT_CONST_TKFRZ=273.15`, `DAT_CONST_TKTRIP=273.16`, `DAT_CONST_PSTD=101325`), phase densities and specific heats (`DAT_CONST_RHODAIR`, `DAT_CONST_RHOFW`, `DAT_CONST_RHOICE`, `DAT_CONST_CPDAIR`, `DAT_CONST_CPWV`, `DAT_CONST_CPFW`, `DAT_CONST_CPICE`), latent heats (`DAT_CONST_LATICE=3.337e5`, `DAT_CONST_LATVAP=2.501e6`, `DAT_CONST_LATSUB=LATICE+LATVAP`), Stefan-Boltzmann `DAT_CONST_STEBOL=5.67e-8`, von Karman `DAT_CONST_KARMAN=0.4`. Special values `DAT_CONST_SPVAL=1e30`, `DAT_CONST_ISPVAL=-999`.

**`Utils/EcoSimConst.F90`** (60 lines). EcoSIM-specific constants, using hour/kJ/MJ units common in the BGC code (f90src/Utils/EcoSimConst.F90:8-58). Time: `secsphour=3600`, `secspday=86400`, `secspyear=86400*365` (365-day year, no leap). Volumetric heat capacities `cpw` (water), `cpi` (ice), `cpo` (consolidated organic matter), `cpsand`, `cpmins`, `cps` (fresh snow). Freezing and reference T (`TFice=TC2K=Tref=273.15`). Minimum heat capacities for solver stability: `VLHeatCapSnoMin`, `VLHeatCapLitRMin`, `VLHeatCapSoiMin`. Geometry: `PICON=3.14159...`, `PICON2h=PICON/2`, `TwoPiCON=2*PICON`, `RadianPerDegree=PICON/180`. Soil/water: `PSIPS=-0.5e-3` (saturated water pressure, MPa), `PSIHY=-2500` (hygroscopic water potential), `POROQ=0.66` (soil porosity ^(2/3)). Latent heats `LtHeatIceMelt=333.55 kJ/kg`, `EvapLHTC=2465 kJ/kg`, `SublmHTC=LtHeatIceMelt+EvapLHTC`. Gas and OM: `RGASC=8.3143`, `OMCMassFrac=0.55`, `DensitySolidOM=1.30`, `DensitySolidMineral=2.66`, `orgcden=OMCMassFrac*1e6`, `hpresc=8.4334e3` (elapsing height for atm pressure). Fire: `VolMaxSoilMoist4Fire=1.0`, `FrcAsCH4byFire=0.01`, `FORGC=1e5` (SOC threshold). Uptake kinetics: `OXKM=0.080` (Km for heterotrophic O2 uptake). Snow: `AirFillPore_Min=1e-3`, `THETPI=0.00`, `DENSICE=0.92-THETPI`, `ZW=0.01` (snowpack surface roughness). Atomic weights: `Catomw=12`, `Natomw=14`, `Patomw=31`. Solar: `TWILGT=0.06976` (sine of solar inclination at twilight). Unit conversions: `gC2MgOM=1e-6/OMCMassFrac`, `TKDif=EvapLHTC/cpw`, `ppmc=1e-6`. Stefan-Boltzmann re-expressed in model units: `stefboltz_const=5.670374419e-8*3600e-6` MJ/(hr m^2 K^4). Month-end correction table: `ICOR(12)=(/1,-1,0,0,1,1,2,3,3,4,4,5/)`. Gravitational acceleration rescaled: `mGravAccelerat=1e-3*GravAcceleration`.

**`Utils/UnitMod.F90`** (130 lines). Object-oriented unit-conversion singleton `units`, a `type(unit_type)` with scalar scale factors and bound elemental functions. Initialized once in `InitEcoSIM.F90:39` (`call units%Initailize()`; note the typo in the method name). Scalar fields (f90src/Utils/UnitMod.F90:12-31): `ppmv=1e-6`, `ppbv=1e-9`, `pptv=1e-12`, `gram2kg=1e-3`, `gram2Mg=1e-6`, `gram2Pg=1e-15`, `gram2Tg=1e-12`, `gram2ton=1e-6`, `cm3tom3=1e-6`, `Pa2kPa=1e-3`, `Pa2MPa=1e-3`, `Pa2Atmos=9.8692e-6`, `msq2hectare=1e-4`, `acre2hectare=0.404686`, `day2seconds=86400`, `hour2seconds=3600`, `molpm3tomolar=1e-3`, `km2mile=0.62137119223733`, `calorie2joule=4.184`. Bound methods (:34-39): `Initailize=>Init`, `Celcius2Kelvin`, `Kelvin2Celcius`, `Fahrenheit2Celcius`, `Celcius2Fahrenheit`, `get_SecondsPerDay`. All conversions are `elemental`, so they broadcast over arrays. The `Celcius2Kelvin`/`Kelvin2Celcius` functions passthrough `spval` sentinels unchanged (:76-80, :99-103).

### 1.2 Time

**`Utils/ecosim_time_mod.F90`** (1094 lines). Simulation clock, object-oriented. The public type is `ecosim_time_type` (f90src/Utils/ecosim_time_mod.F90:27+) with ~40 bound methods (listed at :55-94): lifecycle (`Init`, `setClock`, `update_sim_len`, `proc_initstep`); step control (`set_nstep`, `get_nstep`, `set_time_offset`, `update_time_stamp`); date queries (`get_prev_date`, `get_curr_date`, `get_curr_doy`, `get_curr_dom`, `get_days_per_year`, `get_step_size`, `get_prev_time`, `get_curr_time`, `get_curr_mon_days`, `getdatetime`, `get_curr_timeful`, `get_days_cur_year`, `get_ymdhs`, `get_curr_year`, `get_curr_yearAD`, `get_curr_day`, `get_curr_mon`, `get_calendar`, `print_curr_time`, `print_model_time_stamp`); boolean predicates (`its_time_to_write_restart`, `its_time_to_diag`, `its_time_to_exit`, `its_time_to_histflush`, `its_a_new_hour`, `its_a_new_day`, `its_a_new_week`, `its_a_new_month`, `its_a_new_year`, `is_first_step`); configuration (`config_restart`, `config_diag`).

Related public type `ecosim_time_dat_type` at :21-25 is a plain record (`year0`, `nstep`, `tstep`) used for restart I/O. The `etimer` singleton of type `ecosim_time_type` is declared in `EcoSIMCtrlMod.F90:58`.

Month-day tables (f90src/Utils/ecosim_time_mod.F90:17-18): `daz(12)` (days in each month) and `cdaz(12)` (cumulative days). Both assume a 365-day non-leap year.

### 1.3 Error handling and logging

**`Utils/abortutils.F90`** (627 lines). The global error-exit interface `endrun` and mass destructors. Three forms of `endrun` (f90src/Utils/abortutils.F90:17-23): `endrun_vanilla(msg)` (:80), `endrun_line(msg, line)` (:104), `endrun_globalindex(decomp_index, elmlevel, msg)` (:124). All write to `iulog=6` (unit 6, stdout) and then `stop`. The line-number variant is the one most commonly seen in the codebase via `__LINE__`.

`check_bool(bool_expr, msg, lineno, modfile)` at :273-285: assertion helper.

`destroy` generic interface (:24-70) covers 50+ specific procedures for deallocating 1-D through 7-D arrays of REAL, INTEGER, LOGICAL, CHARACTER, and POINTER-to-REAL/INTEGER/CHARACTER/LOGICAL variants. Every `Destruct*` subroutine in the codebase calls `destroy(arr)` on its allocatables.

`print_info` generic (:72-76): `print_info_arr(msg, strarr, valarr)` (:237) for labelled arrays, `print_info_msg(msg, lineno)` (:261) for plain messages.

String-padding helpers `padl(str, width, symbol)` (:157) and `padr(str, width, symbol)` (:197). `iulog` integer constant at :16 is the log file unit number.

**`Utils/ModelStatusType.F90`** (86 lines). Lightweight `model_status_type` with fields `error` (integer) and `msg` (string up to `error_errmsg_len` from `fileUtil`). Methods `reset`, `set_msg(msg, err, c)` (optional column index), `check_status` (true iff `error<0`), `print_err`, `print_msg`. Factory function `create_model_status_type()` returns a pointer (f90src/Utils/ModelStatusType.F90:24-34). Used to pass soft errors (e.g., solver non-convergence) back through call chains without aborting.

**`Utils/ecosim_log_mod.F90`** (78 lines). CCSM-style logging: `shr_log_Level` (integer severity), `shr_log_Unit` (unit number, default 6), and helper `shr_log_errMsg(file, line)` (f90src/Utils/ecosim_log_mod.F90:62-76) that produces a standard "ERROR in &lt;file&gt; at line &lt;N&gt;" string. Used via `errMsg => shr_log_errMsg` aliases (e.g., `Minimath/LinearAlgebraMod.F90:9`).

### 1.4 File, string, and I/O helpers

**`Utils/fileUtil.F90`** (522 lines). Safe file-open and namelist utilities. Public (f90src/Utils/fileUtil.F90:10-26): `open_safe`, `check_read`, `remove_filename_extension`, `file_exists`, `getfil`, `getavu`, `int2str`, `strip_null`, `print_ichar`, `strip_space`, `namelist_to_buffer`, `opnfil`, `relavu`. Constants: `ecosim_filename_length=128`, `stdout=6`, `error_errmsg_len=256`, `ecosim_string_length_long=256`, `var_flux_type=1`, `var_state_type=2`, `ecosim_namelist_buffer_size=4096`, `datestrlen=14`. A unit-tracking table `UnitTag(0:file_maxUnit)` (file_maxUnit=99, minUnit=10) avoids reusing active Fortran unit numbers. `file_exists(filename)` at :35-45 is a wrapper over `INQUIRE`. `open_safe(lun, prefix, fname, status, location, lineno, lverb)` at :48-78 builds the full path via `getfilenamef`, verifies existence (except for `STATUS='UNKNOWN'`), opens the unit, and aborts via `endrun` if `OPEN` fails.

**`Utils/StrToolsMod.F90`** (345 lines). String parsing. Public: `parse_var_val_string` (:9, body :16), `are_strings_equal_icase` (:10), `extract_number_and_unit` (:11, :197), `is_substring_present` (:12), `to_lower_string` (:13, :288). The `extract_number_and_unit` helper parses strings like `"3.14 MPa"` into a REAL and a unit token — used by the regression-test reader and ad-hoc namelist parsing.

**`Utils/ncdio_pio.F90`** (3244 lines). NetCDF-PIO wrapper — the single I/O layer for every gridded read/write. 40+ public entries (f90src/Utils/ncdio_pio.F90:31-58): file lifecycle (`ncd_pio_openfile`, `ncd_pio_openfile_for_write`, `ncd_pio_createfile`, `ncd_pio_closefile`, `ncd_enddef`), attributes (`ncd_putatt`, `ncd_getatt`, `check_att`, `check_ret`), dimensions (`ncd_defdim`, `ncd_inqdid`, `ncd_inqdname`, `ncd_inqdlen`, `ncd_inqfdims`, `check_dim`, `get_dim_len`), variable metadata (`ncd_defvar`, `ncd_inqvid`, `ncd_inqvname`, `check_var`, `ncd_inq_varid`), I/O (`ncd_putvar`, `ncd_getvar`, `ncd_io`, `ncd_getvint`, `ncd_getvar_str1d`), and init (`ncd_init`). The `file_desc_t` type used in `EcoSIMCtrlMod%pft_nfid` comes from this module, as does `Var_desc_t` used throughout `Mesh/GridMod.F90`. Generic interfaces resolve to per-type procedures (integer vs. real single/double, 1-D through N-D).

**`Utils/shr_infnan_mod.F90`** (1843 lines). Auto-generated (from `genf90.pl`) IEEE NaN/Inf test and signal helpers. Provides `shr_infnan_isnan(x)`, `shr_infnan_isinf`, and constructors for signaling/quiet NaNs. Used whenever the model needs to defensively check for bad floating-point values. Do not hand-edit — regenerate via the genf90.pl tooling if the type set changes.

### 1.5 Timing and regression tests

**`Utils/timings.F90`** (127 lines). Simple stopwatch. Public (f90src/Utils/timings.F90:21-24): `init_timer(outdir)` (:27-42) opens `<outdir>/timing/time.txt` on unit 3001; `start_timer(t1)` (:45) stamps a start time via `system_clock`; `end_timer(name, t1)` (:59) computes elapsed, pushes onto `timer_array` / `name_array` (up to `maxprocs=200`); `end_timer_loop()` (:81) writes a CSV row per iteration. Internal helper `timer(start, time)` (:110-125) wraps `system_clock`. Enabled when `do_timing` (declared elsewhere) is true.

**`Utils/TestMod.F90`** (340 lines). Regression testing. Exports `type error_status_type` (mirror of `ModelStatusType`), `type ecosys_regression_type` (holds filename, num_cells, output unit), and the singleton `regression` (f90src/Utils/TestMod.F90:55). Methods on `ecosys_regression_type` (:46-52): `Init(namelist_file, case_name)` (:60), `OpenOutput` (:166), `CloseOutput` (:184), `WriteData(category, name, data)` (:198), plus private `ReadNamelist` and `CheckInput`. Public `create_error_status_type()` (:259) factory and `errMsg(file, line)` (:324) helper. The run invokes `regressiontest(...)` from `drivers/ecosim/EcoSIMAPI.F90:154` when `do_rgres=.true.`.

### 1.6 C companion code

**`Utils/clock.c`, `Utils/getfilename.c`, `Utils/dtypes.h`, `Utils/clock.o`.** Small C helpers used to paper over Fortran limitations — `clock.c` provides a portable wall-clock call linked into `timer`, and `getfilename.c` provides `getfilenamef(prefix, fname, pathfile)` (invoked from `fileUtil.open_safe:63`) to concatenate prefix + filename with proper C string handling. `dtypes.h` supplies type macros consumed by `shr_infnan_mod.F90`.

## 2. `f90src/Minimath/`

Three modules, entirely self-contained math helpers. No state.

### 2.1 `MiniMathMod.F90` (689 lines) — safe arithmetic and small scientific functions

The workhorse. ~40 public entries (f90src/Minimath/MiniMathMod.F90:15-54), all mostly `pure` or `elemental`:

Safe arithmetic:
- `safe_adb(a, b)` (:69-85), `p_adb(a, b)` (:88-98) — safe division (returns 0 or `spval` on zero-denominator).
- `AZMAX1`, `AZMIN1` — max/min with zero (`AZMAX1(x) = max(x, 0)`), overloaded for scalar (`_s`) and two-arg (`_d`) versions (:42-50, :303-351). Plus typed variants `AZMAX1t` (:206), `AZMAX1d` (:217), `AZMIN1d` (:251).
- `AZERO(val, tiny1)` (:266-285), `AZERO1(val, tiny2)` (:288-300) — snap-to-zero below threshold.
- `addone(itemp)` (:355-366) — atomic increment returning new value. Heavily used in `TracerIDMod.InitTracerIDs` to pack sequential IDs.
- `fixnegmass(val, refcon)` (:441-455), `fixEXConsumpFlux(mass, consum_flux, dsgn)` (:458-493) — clamp and fix-up for conservative variables.
- `flux_mass_limiter(flux, massa, massb)` (:529-546), `get_flux_scalar(x0, flux, x1, pscal)` (:549+), `real_truncate`, `pMod(a, b)` (:233-248).

Classification / interval:
- `isclose(a, b)` (:370-391) — two-value approximate equality.
- `isnan(a)` (:59-66) — wraps `shr_infnan_isnan`.
- `isAinsideBC`, `isABetweenBC`, `isALeftinBC`, `isARightinBC` (:113-143) — closed/open interval membership.
- `isletter(c)` (:518-525) — character is a-z/A-Z.

Physical helpers:
- `vapsat(tempK)` (:147-158), `vapsat0(tempK)` (:162-171) — saturation vapor pressure.
- `GetMolAirPerm3(TKair, Patm_Pa)` (:407-420) — mol air per m³ via ideal gas.
- `Viscosity_H2O`, `VapMass2KPa`.
- `RichardsonNumber(RIB, TK1, TK2)` (:395-405).
- `fSiLU(x, b)` (:422-439) — sigmoid-linear unit activation.
- `dssign(snow)` (:101-111).
- `SubstrateLimit`, `SubstrateDribbling` (scalar and vector overloads), `sfexp` — Monod/Michaelis kinetics helpers.

Calendar:
- `isLeap(year)` (:175-185), `iisLeap(year)` (:188-202) — Gregorian leap rules. Reminder: EcoSIM's `secspyear` in `EcosimConst` is 365*86400 — the model does not currently treat leap years as 366 days, but this helper is provided for I/O routines that must respect calendar years.
- `yearday(year, month, day)` (:497-515) — day-of-year from calendar date.

### 2.2 `MiniFuncMod.F90` (224 lines) — small pure functions for soil-water-gas physics

Ten pure functions (f90src/Minimath/MiniFuncMod.F90:13+):

- `FilmThickness(PSISM, is_top_layer)` (:13) — water-film thickness from matric potential.
- `TEFAQUDIF(TK)` (:31-45) — temperature enhancement factor for aqueous diffusivity.
- `TEFGASDIF(TK)` (:49-64) — temperature enhancement factor for gas diffusivity.
- `TortMicporeW(THETWT)` (:67-74), `TortMacporeW(THETWH)` (:76-84) — tortuosity factors for micro- and macro-pore water.
- `fDiffusivitySolutEff(tempscalar, THETWA, Z3SR, is_litter)` (:87-127) — effective solute diffusivity in soil/litter.
- `fOFFSET(atcs)` (:129-136) — temperature offset for microbial acclimation based on mean annual temperature.
- `GetDayLength(ALAT, I, DECLIN)` (:139-163) — day length in hours from latitude, DOY, declination.
- `get_sun_declin(I)` (:166-178) — solar declination from day-of-year.
- `gOC_to_m3_OM(gram_OC)` (:212-223) — organic-matter volume from organic-C mass using `OMCMassFrac` and `DensitySolidOM`.

All functions import from `EcosimConst` and `MiniMathMod`, making the module the canonical home for EcoSIM's hand-coded soil-physics scalar closures. None of these are Newton solvers or root-finders — they are closed-form expressions.

### 2.3 `LinearAlgebraMod.F90` (126 lines) — tiny custom BLAS

Two public entries (f90src/Minimath/LinearAlgebraMod.F90:15-19):

- `sparse_gemv(transp, nx, ny, a, nb, b, nz, dxdt)` (:23-62) — general matrix-vector product with sparsity tracking. The `transp` character argument ('N'/'T') selects orientation; `nb` is used for the compressed-form b length, `nz` is output stride. This exists instead of calling BLAS `dgemv` so the build does not require a LAPACK/BLAS library.
- `taxpy` generic (:17-19 interface) → `taxpy_v(N, DA, DX, INCX, DY, INCY)` (:65-105) for vectors, `taxpy_m(N, DA, DX, INCX, DY, INCY)` (:108-123) for matrices. Computes `y = a*x + y` with configurable strides, following the `daxpy` BLAS signature.

The filename's "Mini" prefix is literal — these replace a subset of BLAS with a dependency-free in-tree implementation.

## 3. `f90src/DebugTools/`

### `DebugToolMod.F90` (81 lines)

Two public entries (f90src/DebugTools/DebugToolMod.F90:10-18):

- `PrintInfo(message)` (:23-28) — writes `message` to `iulog` iff `lverb` (from `EcoSIMCtrlMod`) is true. Every start-of-subroutine trace in EcoSIM uses this pattern, e.g., `call PrintInfo('beg '//subname)` at `StartqMod.F90:56` and `StarteMod.F90:60`.
- `DebugPrint` generic (:13-18) dispatches to one of four specific procedures:
  - `DebugPrint_real_arr(vnames, vals)` (:32-46) — prints labelled REAL array in E14.6.
  - `DebugPrint_real_arrs(vals)` (:49-59) — bare REAL array dump.
  - `DebugPrint_real_sp(vname, val)` (:63-70) — single labelled REAL.
  - `DebugPrint_int(vname, val)` (:73-80) — single labelled integer.

All honor `lverb` and silently return when it is false. This means DebugPrint calls left in production code incur almost zero cost when `lverb=.false.`, which is the default.

## 4. Key takeaways

- **Aliasing pattern**: nearly every module starts with `use data_kind_mod, only: r8 => DAT_KIND_R8`. Treat `r8` as the project-wide "double precision" alias.
- **Error exit**: all fatal paths call `abortutils.endrun(msg, __LINE__)`. Never call `stop` directly; do call `endrun` with a descriptive message and `__LINE__`.
- **Singletons**: `units` (in `UnitMod`), `regression` (in `TestMod`), `bounds` (in `GridConsts`), `etimer` (in `EcoSIMCtrlMod`), `frectyp` (in `EcoSIMCtrlMod`), `micpar` / `pltpar` (in `EcoSiMParDataMod`). They are populated exactly once during `InitModules`; read freely thereafter.
- **Trace discipline**: routines of non-trivial length open with `call PrintInfo('beg '//subname)` so a run with `lverb=.true.` produces a nested call trace for free. Follow this convention when adding new orchestration routines.
- **No external LAPACK/BLAS**. Everything linear-algebraic of note is in `Minimath/LinearAlgebraMod.F90`. If a solver needs matrix ops beyond `gemv`/`axpy`, it must either add to this file or inline the math.
