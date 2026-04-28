---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/{IOutils, Modelforc, ModelDiags}/`
**Last verified:** 2026-04-24
---

# I/O and Forcing Subsystem Overview

The EcoSIM I/O and forcing subsystem comprises two top-level source directories:

- `f90src/IOutils/` (12 Fortran modules) handles all persistent reading and writing. It covers boundary-condition input (site/topography, soil, climate, plants, management, atmospheric GHGs), the history tape system for model output, the restart/checkpoint subsystem, and an auxiliary BGC-forcing writer used to seed batch soil-BGC spin-ups.
- `f90src/Modelforc/` (4 Fortran modules) converts the already-loaded forcing arrays into per-timestep quantities (annual resets, daily bookkeeping, hourly disaggregation of daily forcing or direct use of hourly forcing, radiation partitioning, and hourly atmospheric/flux-array resets).

This document summarizes every source file in both directories. Detailed reader, tape, restart, and forcing internals are broken out into the subsidiary pages listed at the end.

---

## Source files at a glance

### `f90src/IOutils/`

| File | Lines | One-line purpose |
|---|---|---|
| `readimod.F90` | 1035 | Reads site and topographic data from the NetCDF grid file (`grid_file_in`); sets geometry, water-table regime, lateral-flow boundary conditions, atmospheric trace-gas initial concentrations (`readimod.F90:62`, `readimod.F90:181`). |
| `readsmod.F90` | 377 | Wraps annual climate + soil-management reading. Entry point `ReadClimSoilForcing` either installs a constant climate (`SetConstClimeForcing`, `readsmod.F90:47`) or dispatches to `ReadClimateForc` (`readsmod.F90:307`), then calls `ReadManagementFiles` and `GetAtmGts`. |
| `ClimReadMod.F90` | 1071 | Core climate reader: ASCII weather files (`ReadClim`, `ClimReadMod.F90:583`), NetCDF daily/hourly weather (`ReadClimNC`, `ClimReadMod.F90:696`), 3-hourly to hourly interpolation (`interp3hourweather`, `ClimReadMod.F90:53`), atmospheric GHG record (`GetAtmGts`, `ClimReadMod.F90:900`), climate-correction overlay, and soil-warming reference temperatures. |
| `PlantInfoMod.F90` | 1806 | Reads the PFT parameter NetCDF (`pft_file_in`) and the per-PFT planting / management NetCDF (`pft_mgmt_in`). Populates planting dates, management events, harvest and cutting prescriptions. Entry points `ReadPlantInfo` and `ReadPlantTraitTable` (`PlantInfoMod.F90:39`, `PlantInfoMod.F90:35`). |
| `ReadManagementMod.F90` | 675 | Reads tillage, irrigation, and fertilizer subfiles referenced by the soil-management NetCDF; also reads fire events. Public entry points `ReadManagementFiles` (`ReadManagementMod.F90:409`) and `ReadFire` (`ReadManagementMod.F90:516`). |
| `HistFileMod.F90` | 2976 | History tape engine (up to 6 tapes). Manages the master field list, field addition (`hist_addfld1d`/`hist_addfld2d`), time-averaging flags, tape construction, buffer accumulation (`hist_update_hbuf`), file creation (`htape_create`), and write/closeout (`hist_htapes_wrapup`). Also owns history-restart I/O (`hist_restart_ncd`). |
| `HistDataType.F90` | 4867 | Declares `histdata_type`, a large container of column- and PFT-level pointers for every history field, plus `init_hist_data` (allocates and registers fields via `hist_addfld1d`/`hist_addfld2d`) and `hist_update` (populates the buffers each timestep from live state). |
| `bhistMod.F90` | 468 | Lightweight multi-frequency (hour/day/week/month/year) NetCDF writer used by optional auxiliary diagnostic streams. Defines `histf_type` with procedures `init`, `hist_wrap`, `histrst` (`bhistMod.F90:27`, `bhistMod.F90:66`, `bhistMod.F90:117`). |
| `ForcWriterMod.F90` | 286 | Writes an initial-condition NetCDF for a standalone batch soil-BGC model (`WriteBBGCForc`, `ForcWriterMod.F90:33`). Config type `bgc_forc_config_type` names the year/day/layer/filename to dump. |
| `RestartMod.F90` | 9846 | EcoSIM restart/checkpoint driver. Public `restFile(flag)` (`RestartMod.F90:70`) reads or writes a NetCDF restart covering every model state category (plants, soils, snow, canopy, hydrology, BGC, chemistry, management). Also owns restart pointer-file bookkeeping (`restFile_write_pfile`, `restFile_read_pfile`). |
| `restUtilMod.F90` | 1935 | Generic `restartvar` / `cppft` / `cpcol` utilities with explicit `module procedure` overloads for int/real 1D-5D fields (`restUtilMod.F90:28`). Defines `iflag_interp`, `iflag_copy`, `iflag_skip` semantics used when reading old restarts. |
| `MicrobeInfoMod.F90` | 19 | Stub module (empty subroutine `WriteMicrobeTraits`). Placeholder for future microbial-trait output. |

### `f90src/Modelforc/`

| File | Lines | One-line purpose |
|---|---|---|
| `YearMod.F90` | 138 | `SetAnnualAccumlators` (`YearMod.F90:38`) zeroes all annual cumulative flux arrays (GPP/NPP/NEP, fire emissions, harvest, runoff, mineralization, root uptake) at the start of each year and rolls over per-PFT cumulative element fluxes. |
| `DayMod.F90` | 305 | `day` (`DayMod.F90:45`) refreshes daily diagnostics: equation-of-time solar-noon correction, daily accumulator reset (`UpdateDailyAccumulators`), tillage + automatic irrigation decisions (`TillageandIrrigationEvents`), prescribed phenology interpolation. |
| `Hour1Mod.F90` | 1738 | Hourly "state-reset" step. `hour1` (`Hour1Mod.F90:85`) resets landscape/flux/salt arrays, applies soil-property updates after disturbance, triggers `BegCheckBalances`, diagnoses water table depth, computes hourly diagnostics, runs canopy radiation, and applies fertilizer at solar noon. |
| `WthrMod.F90` | 575 | `PrepHourlyWeather` (`WthrMod.F90:51`) is the forcing-to-state bridge. Dispatches to `DailyWeather` (disaggregation) or `HourlyWeather` (direct read), applies optional OTC/IR warming, partitions radiation (direct vs diffuse SW, direct vs diffuse PAR, longwave from sky emissivity), and accumulates climate summaries (`SummaryClimateForc`). |

---

## Input pipeline

At model initialization and at each forcing-year boundary, the following files are read (all paths are namelist items, examples from `examples/run_dir/blodgett/Blodget.ctrl.namelist:8-15`):

| Namelist variable | Contents | Reader |
|---|---|---|
| `grid_file_in` | Site latitude/altitude/MAT, water-table mode, boundary conditions, grid geometry, soil profile, hydraulic properties | `readimod.F90:84` opens; `readsiteNC`, `readTopoNC` populate. |
| `pft_file_in` | PFT parameter NetCDF (default `input_data/ecosim_pftpar_*.nc`) | `PlantInfoMod::ReadPlantTraitTable`. |
| `pft_mgmt_in` | Per-PFT planting date, population, harvest/cutting schedule | `PlantInfoMod::ReadPlantManagementNC`. Set to `'NO'` to disable. |
| `clm_hour_file_in` / `clm_day_file_in` | Hourly or daily weather NetCDF (TMPX/TMPN/TMPH, WIND/WINDH, DWPT/DWPTH, RAIN/RAINH, SRAD/SRADH, PATM, XRADH, plus scalars like site windspeed height `Z0G`, solar-noon offset `ZNOONG`, precip chemistry `PHRG/CN4RIG/...`) | `ClimReadMod::ReadClimNC` (`ClimReadMod.F90:696`). Year-indexed; call `get_clm_years` to discover the covered span. |
| `clm_factor_in` | Optional annual multiplicative/additive climate-change overlay (`DRAD`, `DTMPX/N`, `DPREC`, etc.) | `readsmod::ReadClimateCorrections` (`readsmod.F90:252`). `'NO'` disables. |
| `soil_mgmt_in` | Tillage, fertilizer, and irrigation subfiles referenced by year + topounit | `ReadManagementMod::ReadManagementFiles` (`ReadManagementMod.F90:409`). `'NO'` disables. |
| `atm_ghg_in` | Historical monthly atmospheric CO2 (ppm), CH4 and N2O (ppb) | `ClimReadMod::GetAtmGts` (`ClimReadMod.F90:900`). |

An ASCII fallback weather path exists via `ClimReadMod::ReadClim` (`ClimReadMod.F90:583`), which parses a text file whose first line encodes time-step type (`D`/`H`/`3` for daily/hourly/3-hourly) and calendar type (`J` for Julian day), followed by variable codes (`R/T/D/P` for radiation/temperature/dewpoint/precipitation) and unit codes (e.g., `M` for mm/d, `C` for cm/d, `I` for inch/d). The NetCDF path is the one used by all packaged example runs.

See `input_readers.md` for per-reader detail.

---

## Output pipeline

Two independent output mechanisms coexist:

1. **Primary history tape system** (`HistFileMod` + `HistDataType`). Up to 6 named tapes (`h0.nc` through `h5.nc`), each configured via `hist_nhtfrq` (sample frequency), `hist_mfilt` (samples per file), and inclusion lists (`hist_fincl1`..`hist_fincl6`) declared in `&ecosim`. Field names are those registered through `hist_addfld1d` / `hist_addfld2d` in `HistDataType.F90` (hundreds of entries, for example `call hist_addfld1d(fname='ECO_HVST_C_col', ...)` at `HistDataType.F90:1272`). The tape filename pattern is `./{case_name}.ecosim.h{N}.{YYYY-MM-DD-SSSSS}.nc` (`HistFileMod.F90:2183`).

2. **Auxiliary `bhistMod` streams** with per-variable clock assignment (`hour`, `day`, `week`, `month`, `year`), used for specialized side-channel diagnostic outputs.

3. **Restart / checkpoint files** written by `RestartMod::restFile` (`RestartMod.F90:70`). Filename pattern is `./{case_name}.ecosim.r.{YYYY-MM-DD-SSSSSS}.nc`; cadence is controlled by `rest_opt` (`ndays`/`nmonths`/`nyears`/`never`) and `rest_frq` in the `&ecosim_time` namelist.

4. **`ForcWriterMod::WriteBBGCForc`** dumps a one-shot NetCDF of soil-column state (pH, porosity, SOM stocks, CEC/AEC, ion content, microbial pools) on a chosen `(year, doy, layer)`, for use as initial conditions by a standalone batch soil-BGC model (`ForcWriterMod.F90:33`).

See `history_and_restart.md` for tape internals, field registration, restart flow, and file-naming details.

---

## File formats

- **Primary inputs** (site grid, PFT, PFT-management, weather, climate-correction, soil-management, atmospheric GHG): NetCDF, opened via `ncdio_pio::ncd_pio_openfile` (see the `use ncdio_pio` statements in every reader module, e.g., `readimod.F90:15`). All operational example runs (`examples/run_dir/blodgett/`, `examples/run_dir/bare_soil/`) use `.nc` files exclusively.
- **Legacy ASCII weather** remains supported through `ClimReadMod::ReadClim` (`ClimReadMod.F90:583`) but is not used by any in-tree example.
- **Namelist driver** is Fortran namelist. Structured as four groups in every example file: `&regression_test`, `&ecosim` (paths, flags, output inclusion lists), `&bbgcforc` (batch BGC forcing-writer config; often empty), and `&ecosim_time` (timestep, stop condition, restart and diagnostic cadence). Example in full: `examples/run_dir/blodgett/Blodget.ctrl.namelist:1-64`.
- **Primary history tapes** and **restart files**: NetCDF, written via the same `ncdio_pio` wrappers.
- **Model logs** (`logfile1`, `logfile2`, `logfile3`) are plain ASCII, opened unconditionally in `readimod::readi` (`readimod.F90:77-79`).

---

## Forcing pipeline (summary)

`f90src/Modelforc/` contains the forcing-to-state translator. Ordering within one simulated year:

1. **Year boundary**: `YearMod::SetAnnualAccumlators` zeroes annual cumulative fluxes (`YearMod.F90:38`).
2. **Day boundary**: `DayMod::day` computes daily solar geometry, resets daily max/min accumulators, handles tillage events, and performs automatic-irrigation decisions (`DayMod.F90:45`).
3. **Hour boundary, first phase**: `Hour1Mod::hour1` resets flux arrays, recomputes soil/litter properties after disturbance, begins mass-balance bookkeeping, diagnoses water-table depth, computes hourly diagnostics, runs canopy radiation, and applies solar-noon fertilizer events (`Hour1Mod.F90:85`).
4. **Hour boundary, second phase**: `WthrMod::PrepHourlyWeather` (`WthrMod.F90:51`) converts the 24-slot daily or hourly forcing arrays into current-hour column fields (`TCA_col`, `TairK_col`, `VPK_col`, `WindSpeedAtm_col`, `PBOT_col`, `PrecAsRain_col`, `PrecAsSnow_col`, `RADN_col`), splits radiation into direct/diffuse SW+PAR and sky longwave, adds irrigation, and accumulates climate summaries.

See `forcing.md` for the step-by-step pipeline, variable lists, and the disaggregation math.

---

## Diagnostics

The diagnostics subsystem (`f90src/ModelDiags/`, 3 modules) is documented separately at `../diagnostics/index.md`. Key connections:

- `BalancesMod::BegCheckBalances` and `EndCheckBalances` bracket every hour inside the Hour1 path to enforce water, heat, and tracer mass conservation (`Hour1Mod.F90:151`, called from within `hour1`).
- `HydrologyDiagMod::DiagWaterTBLDepz` is invoked per column inside `hour1` to update internal water-table depth (`Hour1Mod.F90:178`).
- `SoilDiagsMod::DiagSoilGasPressure` computes per-layer gas pressures and fractional composition (CO2/CH4/O2/N2/N2O/NH3) for use by diagnostic outputs.

---

## Navigation

- `input_readers.md` — per-reader details for IOutils readers (what each reads, variables populated, file format expected, namelist structure).
- `history_and_restart.md` — primary tape mechanics (`HistFileMod`/`HistDataType`), the `bhistMod` auxiliary stream, restart flow through `RestartMod` and `restUtilMod`, and file-naming conventions.
- `forcing.md` — `f90src/Modelforc/` per-file pipeline with forcing-variable list, unit conversions, disaggregation rules, and radiation partitioning.
- `../diagnostics/index.md` — `f90src/ModelDiags/` diagnostics accumulator subsystem.
