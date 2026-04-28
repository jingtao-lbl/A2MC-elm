---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `drivers/ecosim/`
**Last verified:** 2026-04-24
---

# Main Standalone Driver (`ecosim.F90` / `EcoSIMAPI.F90`)

The standalone EcoSIM driver lives in `drivers/ecosim/` and consists of two
Fortran files.

| File | Role |
|---|---|
| `drivers/ecosim/ecosim.F90` (158 lines) | The `program main` — command-line handling, namelist load, mesh setup, three-level period / year loop |
| `drivers/ecosim/EcoSIMAPI.F90` (594 lines) | `module EcoSIMAPI` — four public subroutines that together form the single-year / single-timestep public API |

The CMake target `ecosim.f90.x` is built from both files
(`drivers/ecosim/CMakeLists.txt:1-6`).

## Program Entry (`ecosim.F90`)

The program is straight-line top-level code with no subroutines of its own.
The key phases of its execution, in the order they run, are:

### 1. Working directory and OS detection
`CALL GETCWD(BUF)` at `drivers/ecosim/ecosim.F90:53`. If the first character is
not `/` or `~` and the second is `:`, the driver assumes Windows / DOS, reads
the target directory from the second command-line argument, and `CHDIR`s into
it (`ecosim.F90:57-67`).

### 2. Namelist load
The first command-line argument is treated as the namelist file
(`ecosim.F90:69`). It is copied into an in-memory buffer by
`namelist_to_buffer` (`ecosim.F90:71`) and then passed to
`EcoSIMAPI::readnamelist`
(`ecosim.F90:74`, defined at `drivers/ecosim/EcoSIMAPI.F90:124-318`).

### 3. Output directory
The driver creates `<cwd>/<case_name>_outputs/` via `mkdir -p`
(`ecosim.F90:77-81`).

### 4. Mesh and module init
```
call SetMesh(NHW,NVN,NHE,NVS)    ! drivers/ecosim/ecosim.F90:87
call InitModules()               ! drivers/ecosim/ecosim.F90:89
CALL readi(NHW,NHE,NVN,NVS)      ! drivers/ecosim/ecosim.F90:92
```
`SetMesh` establishes the landscape horizontal-column range. `readi` loads
the site / soil / management input files.

### 5. Configuration summary
`write_modelconfig` (`EcoSIMAPI.F90:573-592`) writes `ecosim.setup` with the
active switches (`microbial_model`, `plant_model`, `salt_model`,
`erosion_model`, `grid_mode`).

### 6. Simulation-length calculation
```
nstopyr = get_sim_len(forc_periods, nperiods)     ! ecosim.F90:98
call etimer%update_sim_len(nstopyr)               ! ecosim.F90:100
```
`forc_periods` is a 15-element integer array laid out as (year_start, year_end,
repeat_count) triplets up to 5 periods. `get_sim_len` is defined at
`f90src/Modelconfig/EcoSIMCtrlMod.F90:112-129`.

### 7. Restart handling
```
if(is_restart())then
  call get_restart_date(curr_date)     ! ecosim.F90:107
  frectyp%ymdhs0 = curr_date
  read(curr_date,'(I4)')frectyp%yearrst
else
  frectyp%ymdhs0 = start_date          ! ecosim.F90:112
endif
```

### 8. History tapes and climate
```
call hist_htapes_build()               ! ecosim.F90:115
call get_clm_years()                   ! ecosim.F90:118
```

### 9. The three-level period / year loop

The main time loop occupies `ecosim.F90:124-151`:

```
DO nn1 = 1, nperiods                              ! outer: forcing period
  call set_ecosim_solver(NPXS(nn1), NPYS(nn1), NCYC_LITR, NCYC_SNOW)
  do nn2 = 1, forc_periods(nn1*3)                 ! repeats of this period
    nn3 = (nn1-1)*3
    idy = 1; if(forc_periods(nn3+1) > forc_periods(nn3+2)) idy = -1
    do nyr1 = forc_periods(nn3+1), forc_periods(nn3+2), idy  ! year in period
      frectyp%yearclm = nyr1
      frectyp%yearcur = etimer%get_curr_yearAD()
      nlend = .false.
      IGO = yeari - year_ini
      if(frectyp%yearcur == yeari)then
        call AdvanceModelOneYear(NHW,NHE,NVN,NVS,nlend)   ! ecosim.F90:140
      endif
      if(nlend) exit
      frectyp%yearacc = frectyp%yearacc + 1
      ...
    end do
  end do
end do
```

Three things to notice:

- `AdvanceModelOneYear` is called once per simulated calendar year. It is the
  *only* coupling point between the driver loop and the EcoSIM API.
- `idy` allows a period to count years backward (`year_end < year_start`),
  which is how cyclic / reverse forcing is expressed in `forc_periods`.
- `nlend` is the end-of-simulation flag returned by `AdvanceModelOneYear` via
  `intent(out)`. When set, the driver falls through all three loops.

### 10. Regression and cleanup
```
if(do_rgres) call regressiontest(trim(nmlfile), trim(case_name), NHW, NVN)   ! ecosim.F90:154
call DestructEcoSIM                                                          ! ecosim.F90:156
```

## Public API (`EcoSIMAPI.F90`)

The module is declared at `EcoSIMAPI.F90:1` and publishes four public
subroutines at `EcoSIMAPI.F90:29-31`:

```fortran
public :: AdvanceModelOneYear
public :: readnamelist
public :: regressiontest, write_modelconfig
```

`Run_EcoSIM_one_step` (`EcoSIMAPI.F90:35-122`) is internal to the module — it
is not exported and is called only from inside `AdvanceModelOneYear`.

### `readnamelist(nml_buffer, case_name, prefix, LYRG, nmicbguilds)`

Defined at `EcoSIMAPI.F90:124-318`.

Reads three namelist groups from the in-memory buffer:

| Namelist | Source lines | Purpose |
|---|---|---|
| `ecosim` | `EcoSIMAPI.F90:154-165` | Master run configuration — case name, paths, sub-model switches, time-step parameters, forcing periods, model-mode flags, history output settings |
| `bbgcforc` | `EcoSIMAPI.F90:168-169` | Bounds for writing a BGC-forcing NetCDF (year, DOY, layer, filename) |
| `FixClimForc` | `EcoSIMAPI.F90:171` | Fixed-climate values (airT_C, Wind_ms, vap_Kpa, Rain_mmhr, SRAD_Wm2, Atm_kPa) — read only when `fixClime=.true.` |

Important side effects set inside this routine:

- Defaults: `NPXS=30`, `NPYS=10`, `NCYC_LITR=NCYC_SNOW=20`
  (`EcoSIMAPI.F90:180-187`).
- `erosion_model = iErosionMode >= 0` (`EcoSIMAPI.F90:266`).
- If `ldo_radiation_test`, force `ldo_sp_mode = .true.`
  (`EcoSIMAPI.F90:284`).
- If `ldo_sp_mode`, force `plant_model=.true.`, `soichem_model=.false.`,
  `microbial_model=.false.` (`EcoSIMAPI.F90:285-290`). In site-prescribed
  (SP) mode the plant model is run only to allocate arrays — phenology is
  prescribed externally.
- Calls `config_soil_warming(warming_exp)` when a warming string is provided
  (`EcoSIMAPI.F90:293`), `config_fire(FireEvents)` (`EcoSIMAPI.F90:294`),
  and `ReadMicrobeNamelist(nml_buffer)` (`EcoSIMAPI.F90:316`).

### `AdvanceModelOneYear(NHW, NHE, NVN, NVS, nlend)`

Defined at `EcoSIMAPI.F90:321-497`. This is the single-year outer routine
orchestrating all physics for one calendar year on the `NHW..NHE` by
`NVN..NVS` column grid. It returns `nlend=.true.` (`intent(out)`) when
`etimer` says the simulation is done.

Execution outline, grouped in source order:

1. **Annual initialization (`EcoSIMAPI.F90:370-417`).**
   - `is_first_year = frectyp%yearacc == 0`.
   - Call `ReadClimSoilForcing(yearcur, yearclm, NHW, NHE, NVN, NVS)`.
   - On the first year only (`ymdhs(1:4) == frectyp%ymdhs0(1:4)`):
     - `STARTS(NHW,NHE,NVN,NVS)` — soil state initialization
       (`EcoSIMAPI.F90:383`).
     - If plants active, `ReadPlantInfo(yearcur, yearclm, ...)`
       (`EcoSIMAPI.F90:392`).
     - If plants active, `STARTQ(NHW,NHE,NVN,NVS, 1, JP)` — plant state
       initialization (`EcoSIMAPI.F90:399`).
     - If soil chemistry active, `STARTE(NHW,NHE,NVN,NVS)` — annual soil
       chemistry refresh (`EcoSIMAPI.F90:408`). Note the inline comment:
       this runs every year because rainfall tracer concentrations vary
       year-to-year.
   - Check and load soil-warming reference temperatures when warming is
     scheduled for this year (`EcoSIMAPI.F90:413-415`).

2. **Day loop (`EcoSIMAPI.F90:419-494`).** `DazCurrYear` days.
   - `CALL DAY(I, NHW, NHE, NVN, NVS)` — daily management inputs
     (`EcoSIMAPI.F90:431`).
   - `call SetAnnualAccumlators(I, NHW, NHE, NVN, NVS)` — reset/advance
     annual accumulator buffers (`EcoSIMAPI.F90:433`).
   - **Hour loop (`EcoSIMAPI.F90:435-483`).** `J = 1..24`.
     - On the restart timestamp, call `restFile(flag='read')` and replay the
       accumulators (`EcoSIMAPI.F90:440-448`).
     - `call PrepHourlyWeather(I,J,...)` — hourly weather forcing
       (`EcoSIMAPI.F90:458`).
     - `call Run_EcoSIM_one_step(yearIJ, NHW,NHE,NVN,NVS)` — the hourly
       physics orchestrator (`EcoSIMAPI.F90:461`).
     - `call hist_ecosim%hist_update(...)` and `hist_update_hbuf(bounds)`
       — push state into the history buffer (`EcoSIMAPI.F90:465-467`).
     - `call etimer%update_time_stamp()` — advance the clock one hour.
     - `nlend = etimer%its_time_to_exit()`,
       `rstwr = etimer%its_time_to_write_restart(nlend)`,
       `lnyr = etimer%its_a_new_year()` — end / restart / year-end flags.
     - `call hist_htapes_wrapup(rstwr, nlend, bounds, lnyr)` to finalize
       tapes, and `call restFile(flag='write')` when `rstwr`.
   - If `do_bgcforc_write`, `call WriteBBGCFORC(I, IYRR)`
     (`EcoSIMAPI.F90:490-492`).
   - Regression-mode early-out: when `do_rgres .and. I == LYRG`, return
     (`EcoSIMAPI.F90:427`).

3. **Return.** No annual cleanup here — the `DestructEcoSIM` call happens in
   the driver program after all years finish.

### `Run_EcoSIM_one_step(yearIJ, NHW, NHE, NVN, NVS)` (internal)

Defined at `EcoSIMAPI.F90:35-122`. This is the hourly physics orchestrator.
It is **not public** — callers outside the module must go through
`AdvanceModelOneYear`. The call order, with the flag that gates each step, is:

| Order | Call | Gating flag | Source line |
|---|---|---|---|
| 1 | `HOUR1` (surface energy/water hourly) | always | `EcoSIMAPI.F90:47` |
| 2 | `WATSUB` (soil water/heat, subhourly) | always | `EcoSIMAPI.F90:54` |
| 3 | `MicrobeModel` (soil BGC) | `microbial_model` | `EcoSIMAPI.F90:61` |
| 4 | `PlantModel` | `plant_model .and. .not.ldo_radiation_test` | `EcoSIMAPI.F90:69` |
| 5 | `soluteModel` (aqueous chemistry) | `soichem_model` | `EcoSIMAPI.F90:78` |
| 6 | `TranspNoSalt` (non-salt transport) | always | `EcoSIMAPI.F90:87` |
| 7 | `TranspSalt` (salt transport) | `salt_model` | `EcoSIMAPI.F90:96` |
| 8 | `EROSION` | always (see note) | `EcoSIMAPI.F90:106` |
| 9 | `REDIST` (update state after fluxes) | always | `EcoSIMAPI.F90:113` |
| 10 | `DiagSoilGasPressure` | always | `EcoSIMAPI.F90:117` |
| 11 | `EndCheckBalances` | always | `EcoSIMAPI.F90:119` |

Note: `EROSION` is always *called*, but it reads `iErosionMode` internally and
no-ops when erosion is disabled. All calls are wrapped in optional `start_timer`
/ `end_timer` pairs controlled by the `do_timing` flag (default `.false.`,
enabled via the `ecosim` namelist).

The routine also emits `PrintInfo` breadcrumbs at its entry and exit
(`EcoSIMAPI.F90:43,121`) for the `DebugToolMod`-driven debug trace.

> **Note on naming.** The name `Run_EcoSIM_one_step` is reused inside the ATS
> coupling layer (`f90src/ATSUtils/ATSCPLMod.F90:312`) but refers to a
> *different* subroutine there — one that only runs surface-balance physics
> for a single subcycled surface time step. The two are kept distinct by
> being module-private to their respective modules.

### `regressiontest(nmfile, case_name, NX, NY)`

Defined at `EcoSIMAPI.F90:500-570`. Called from the driver when `do_rgres` is
true (set via the `ecosim` namelist `do_regression_test` switch). It opens a
regression-output file (via `regression%Init` / `regression%OpenOutput`,
`EcoSIMAPI.F90:529-533`) and writes four diagnostic arrays for the first
active plant in column `(NY,NX)`:

1. `'flux' / 'NH4_UPTK (g m^-3 h^-1)'` — per-layer NH4 root uptake (summed over
   band / non-band) for the first active PFT (`EcoSIMAPI.F90:538-548`).
2. `'state' / 'aqueous soil O2 (g m^3)'` — layers 1..12 of
   `trc_solcl_vr(idg_O2,:)` (`EcoSIMAPI.F90:553-556`).
3. `'state' / 'liquid soil water (m^3 m^-3)'` — `ThetaH2OZ_vr(1:12,NY,NX)`
   (`EcoSIMAPI.F90:558-561`).
4. `'state' / 'soil temperature (oC)'` — `TCS_vr(1:12,NY,NX)`
   (`EcoSIMAPI.F90:563-566`).

The routine is a regression *writer*; the comparison against baseline is done
by the external test harness in `regression-tests/`.

### `write_modelconfig()`

Defined at `EcoSIMAPI.F90:573-592`. When `disp_modelconfig` is true (default
`.true.`, set in `readnamelist`), opens a file named `ecosim.setup` and writes
five key-value lines: the four sub-model switches (`microbial_model`,
`plant_model`, `salt_model`, `erosion_model_status(iErosionMode)`) and the
`grid_mode` descriptor (`GridConectionMode(grid_mode)`).

## Timestep Orchestrators — Which Subroutine Does What?

A common point of confusion is which routine owns which part of the timestep
structure. The division of labor is:

| Scope | Owned by | Source |
|---|---|---|
| Multi-year forcing-period loop | `program main` | `ecosim.F90:124-151` |
| Per-year setup and day/hour loop | `AdvanceModelOneYear` | `EcoSIMAPI.F90:321-497` |
| Per-hour physics call sequence | `Run_EcoSIM_one_step` (module-private) | `EcoSIMAPI.F90:35-122` |
| Subhourly (intra-hour) iteration | `WATSUB` + the individual physics modules | outside this file |

Deepwiki previously claimed `AdvanceModelOneYear` occupied
`EcoSIMAPI.F90:321-488`. The correct end line is 497; lines 321-367 are the
subroutine header and use-statements, not executable code. The actual
executable body starts at line 369 with `call PrintInfo('beg '//subname)`.

## Namelist Summary

The `ecosim` namelist is the master control interface. Key groups of flags,
with source lines in `EcoSIMAPI.F90:154-165`:

- **Case / I/O.** `case_name`, `prefix`, `pft_file_in`, `grid_file_in`,
  `pft_mgmt_in`, `soil_mgmt_in`, `clm_factor_in`, `clm_hour_file_in`,
  `clm_day_file_in`, `atm_ghg_in`, `micpar_file_in`.
- **Sub-model switches.** `plant_model`, `microbial_model`, `soichem_model`,
  `salt_model`, `snowRedist_model`, `iErosionMode`.
- **Mode flags.** `ldo_sp_mode` (prescribed phenology),
  `ldo_radiation_test`, `transport_on`, `column_mode`, `do_instequil`,
  `continue_run`, `restart_out`, `lsoilCompaction`, `plantOM4Heat`,
  `fixClime`, `fixWaterLevel`, `first_topou`, `first_pft`.
- **Time control.** `forc_periods(15)`, `num_of_simdays`, `start_date`,
  `ref_date`, `NPXS`, `NPYS`, `NCYC_LITR`, `NCYC_SNOW`.
- **Atmospheric composition.** `aco2_ppm`, `ao2_ppm`, `an2_ppm`, `ach4_ppm`,
  `anh3_ppm`, `arg_ppm`, plus fix overrides `atm_co2_fix`, `atm_n2o_fix`,
  `atm_ch4_fix`.
- **History / diagnostics.** `hist_nhtfrq`, `hist_mfilt`, `hist_fincl1`,
  `hist_fincl2`, `hist_yrclose`, `do_budgets`, `do_timing`, `iverblevel`,
  `idebug_day`, `idebug_year`.
- **Warming / fire.** `warming_exp`, `FireEvents`.
- **Regression.** `do_regression_test`, `oscal_test`.

Defaults are set at `EcoSIMAPI.F90:178-242` before the `read(nml_buffer, ...)`
call. Any value not present in the user's namelist keeps its default there.

## Cross-References

- Physics routine details are under `hydrotherm/`, `microbial_bgc/`,
  `plant_bgc/`, `geochem/`, and `transport/` in this wiki.
- Time-stepping / `etimer` / `frectyp`: `f90src/Modelconfig/EcoSIMCtrlMod.F90`.
- Mesh setup (`SetMesh`): `f90src/Mesh/GridMod.F90`.
- History tapes (`hist_*`): `f90src/IOutils/HistFileMod.F90` and
  `f90src/IOutils/EcoSIMHistMod.F90`.
- Restart: `f90src/IOutils/RestartMod.F90`.
