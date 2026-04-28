---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/IOutils/` input readers
**Last verified:** 2026-04-24
---

# Input Readers

This document describes each reader module in `f90src/IOutils/`, the namelist variables driving them, the NetCDF variables they consume, and the model arrays they populate.

All readers use the `ncdio_pio` wrapper layer (`ncd_pio_openfile`, `ncd_getvar`, `ncd_pio_closefile`, `check_var`, `check_ret`). Namelist paths are set in the `&ecosim` block of the run namelist (example: `examples/run_dir/blodgett/Blodget.ctrl.namelist:5-15`).

---

## 1. Namelist structure

The namelist that orchestrates all reading is a Fortran `&ecosim` group. The canonical structure (from `examples/run_dir/blodgett/Blodget.ctrl.namelist:5-50`):

```fortran
&ecosim
 case_name='Blodget.ctrl'
 do_regression_test=.false.
 pft_file_in='../../inputs/blodgett/blodgett_pftpar_20241010.nc'
 grid_file_in='../../inputs/blodgett/Blodget_grid_20251115.nc'
 pft_mgmt_in='../../inputs/blodgett/Blodget_pft_20240622.ENF.nc'
 clm_hour_file_in='../../inputs/blodgett/Blodget.clim.2012-2022.nc'
 clm_factor_in='NO'
 soil_mgmt_in='NO'
 atm_ghg_in='../../../input_data/fatm_hist_GHGs_1750-2023.nc'
 lverbose=.false.
 plantOM4Heat=.true.
 disp_planttrait=.true.
 plant_model=.true.
 microbial_model=.true.
 soichem_model=.true.
 start_date  = '19410101000000'
 grid_mode=1
 continue_run=.false.
 forc_periods=2012,2015,18,2012,2022,1,2012,2022,0
 NPXS=30,30,30
 NPYS=10,10,10
 NCYC_LITR=30
 NCYC_SNOW=20
 hist_mfilt=7300, 240
 hist_fincl1='ECO_RA_col','ECO_RH_col','ECO_NPP_col', ...
 hist_nhtfrq=-24
/
```

Key conventions:

- **Path placeholders**: a string of `'NO'` disables that input stream (see `soil_mgmt_in`, `clm_factor_in`, `pft_mgmt_in` in the Blodgett namelist and bare-soil namelist `examples/run_dir/bare_soil/BareSoil.namelist:11-14`).
- **`forc_periods`** is a 9-tuple encoding (spin-up begin, spin-up end, cycles, regular begin, regular end, cycles, ...). The last `stop_n` / `stop_option` pair in `&ecosim_time` ultimately overrides.
- **`grid_mode`** — `1` enables lateral runoff; see `readimod::GridConectionMode` (`readimod.F90:136`) for semantics (1=3D, 2=2D N-S only, 3=1D vertical column).

---

## 2. `readimod.F90` — site and topography

**Entry point**: `readi(NHW,NHE,NVN,NVS)` (`readimod.F90:62`). Called once at model initialization.

**Input file**: `grid_file_in` (NetCDF). Opened at `readimod.F90:84`.

**What it reads** (all via `ncd_getvar`, `readimod.F90:215-240`):

| NetCDF variable | Semantics | Populated module variable |
|---|---|---|
| `ALATG` | Site latitude (deg, +N) | `ALAT_col` |
| `ALTIG` | Altitude (m) | `ALTI_col` |
| `ATCAG` | Mean annual air temperature (C) | `ATCAI_col` |
| `IDTBLG` | Water-table mode (0=none, 1-2 natural, 3-4 artificial) | `IDWaterTable_col` |
| `IETYPG` | Koppen climate zone (-2 = phytotron) | `KoppenClimZone_col` |
| `DTBLIG` | Depth of natural water table (m) | `NatWtblDepz_col` |
| `DTBLDIG` | Depth of artificial (tile) water table (m) | `WtblDepzTile_col` |
| `DTBLGG` | Slope of natural water table vs land surface | `WaterTBLSlope_col` |
| `RCHQNG`/`RCHQEG`/`RCHQSG`/`RCHQWG` | N/E/S/W surface runoff boundary conditions | `RechargNorth/East/South/WestSurf_col` |
| `RCHGNUG`/`RCHGEUG`/`RCHGSUG`/`RCHGWUG` | N/E/S/W subsurface flow boundary conditions | `RechargRateNorth/East/South/WestWTBL_col` |
| `RCHGNTG`/`RCHGETG`/`RCHGSTG`/`RCHGWTG` | N/E/S/W distance to water table (m) | `RechrgDistNorth/East/South/WestSubSurf_col` |
| `RCHGDG` | Lower (bottom) boundary condition for water flow | `RechargBottom_col` |
| `DHI` | W-E landscape column widths | `DH_col` |
| `DVI` | N-S landscape row widths | `DV_col` |

`readsiteNC` also initializes atmospheric trace-gas column fields (`OXYE_col`, `CO2EI_col`, `CH4E_col`, `Z2OE_col`, `ARGE_col`, `ZNH3E_col`, `H2GE_col`) from hard-coded ppm constants (`readimod.F90:284-317`).

Before `readsiteNC`, `readi` opens three ASCII model-wide logfiles (`logfile1`, `logfile2`, `logfile3`) at `readimod.F90:77-79`.

After site data, `readTopoNC` (`readimod.F90:337`) reads per-column soil-profile data (horizons, textures, bulk density, pH, CEC/AEC, field capacity, wilting point, etc.) from the same `grid_nfid` file.

The module also provides three look-up helpers:
- `erosion_model_status(flag)` (`readimod.F90:107`) — decodes the erosion mode flag into a human string.
- `GridConectionMode(NCNG)` (`readimod.F90:136`).
- `WaterTableStatus(iWaterTabelMode)` (`readimod.F90:156`).

---

## 3. `readsmod.F90` — annual climate + soil-management dispatch

**Entry point**: `ReadClimSoilForcing(yearc, yeari, NHW, NHE, NVN, NVS)` (`readsmod.F90:83`). Called at each forcing-year boundary. `yearc` is the current model year; `yeari` is the forcing-data year (they differ during spin-up cycling).

**Flow** (`readsmod.F90:107-247`):

1. Call `ReadClimateCorrections(yeari)` (`readsmod.F90:252`) to overlay annual perturbations (`DRAD`, `DTMPX`, `DTMPN`, `DHUM`, `DPREC`, `DIRRI`, `DWIND`, `DCN4R`, `DCNOR`, `ICLM`) from `clm_factor_in`. Skipped when that file is `'NO'`.
2. If the global flag `fixClime` is set, invoke `SetConstClimeForcing()` (`readsmod.F90:47`) to broadcast the scalar `clim_var` (`clime_type` struct with `airT_C`, `vap_Kpa`, `Wind_ms`, `Atm_kPa`, `Rain_mmhr`, `SRAD_Wm2`) to every hour of `TMP_hrly`, `WINDH`, `DWPTH`, `RAINH`, `SWRad_hrly`, `PBOT_hrly` and zero out precipitation chemistry. Used for constant-forcing regression tests (see `examples/run_dir/climeConst/`).
3. Otherwise, call `ReadClimateForc(yearc, yeari, L, NHW, NHE, NVN, NVS)` (`readsmod.F90:307`), which delegates to `ClimReadMod::ReadClimNC`.
4. Zero out per-day management arrays (`iSoilDisturbType_col`, `DepzCorp_col`, `FERT`, `IYTYP`, `FDPTH`, `RRIG`, `PHQ`, `NH4_irrig_mole_conc`, `NO3_irrig_mole_conc`, `H2PO4_irrig_mole_conc`, `WDPTH`, `ROWI`, and if `salt_model` the salt tracer concentrations) for the new year (`readsmod.F90:185-229`).
5. If `use_fire` is on and `check_fire(yearc, fire_event_entry)` matches, call `ReadManagementMod::ReadFire` (`readsmod.F90:236-238`).
6. If `soil_mgmt_in /= 'NO'`, call `ReadManagementFiles(yeari)` (`readsmod.F90:241`).
7. Call `ClimReadMod::GetAtmGts(yearc, NHW, NHE, NVN, NVS)` (`readsmod.F90:246`) for the year's atmospheric CO2/CH4/N2O.

The module-level `yearhi` guard (`readsmod.F90:31`, `readsmod.F90:178`) prevents re-reading the same forcing year within one outer iteration.

---

## 4. `ClimReadMod.F90` — climate/weather, GHGs, soil warming

Public API (`ClimReadMod.F90:44-48`):
- `ReadClim` — legacy ASCII weather reader.
- `ReadClimNC` — NetCDF weather reader (daily + hourly).
- `GetAtmGts` — atmospheric GHG record.
- `get_clm_years` — probe the span covered by the climate files.
- `read_soil_warming_Tref` — read an external reference temperature grid for prescribed soil warming.

### 4.1 `ReadClimNC(yearc, yeari, L, atmf)` — the primary path

Called from `readsmod::ReadClimateForc`. Behavior depends on `IWTHR = get_forc_step_type(yeari)`:

- `IWTHR == 1` (daily): open `clm_day_file_in` (`ClimReadMod.F90:725`). Variables read (`ClimReadMod.F90:741-762`): `TMPX`, `TMPN`, `WIND`, `RAIN`, `SRAD`, `DWPT`, plus site scalars `Z0G` (anemometer height), `ZNOONG` (solar-noon offset), precip chemistry (`PHRG`, `CN4RIG`, `CNORIG`, `CPORG`, `CALRG`, `CFERG`, `CCARG`, `CMGRG`, `CNARG`, `CKARG`, `CSORG`, `CCLRG`), and vegetation-flag `IFLGW` (`iFlagRaiseZ0GbyVeg`). Populates the arrays defined in `ClimForcDataType`. Pads day 366 when the year is not a leap year.
- `IWTHR == 2` (hourly): open `clm_hour_file_in` (`ClimReadMod.F90:781`). Variables read (`ClimReadMod.F90:799-830`): `TMPH` → `TMP_hrly`, `WINDH`, `DWPTH`, `RAINH`, `SRADH` → `SWRad_hrly`, optional `PATM` → `PBOT_hrly` (defaulted to 101.325 kPa if absent), optional `XRADH` → `RadLWClm` (longwave, zeroed if absent), plus the same site scalars as daily.

Unit conversions (`ClimReadMod.F90:849-855`): `SWRad_hrly` from W m-2 to MJ m-2 hr-1 via `*3600e-6`, `WINDH` from m s-1 to m hr-1 via `*3600`, `RAINH` from mm hr-1 to m hr-1 via `*1e-3`.

### 4.2 `ReadClim(iyear, clmfile, NTX, NFX, I, IX, TTYPE, atmf)` — ASCII path (`ClimReadMod.F90:583`)

Reads a plain-text weather file with a structured header. Line 1 encodes time-step type (`D`, `H`, or `3`) and calendar type (`J` for Julian day or otherwise month-day-year); line 2 gives unit codes; line 3 contains `Z0G`, `IFLGW`, `ZNOONG`; line 4 contains 12 precipitation-chemistry scalars (pH and ion concentrations, `ClimReadMod.F90:613-617`). Daily path in `readdayweather`, hourly path in `readhourweather` (`ClimReadMod.F90:103`). Supports 3-hourly data via `interp3hourweather` (`ClimReadMod.F90:53`), which linearly interpolates between 3-hour stamps. Not used by any packaged example run but retained for backward compatibility.

### 4.3 `GetAtmGts(yeari, NHW, NHE, NVN, NVS)` (`ClimReadMod.F90:900`)

Opens `atm_ghg_in`, locates the month index for `yeari`, and reads 12 monthly values of `CO2` (ppm), `CH4` (ppb), `N2O` (ppb) into `atm_co2_mon`, `atm_ch4_mon`, `atm_n2o_mon`. Values can be overridden by the scalars `atm_co2_fix`, `atm_ch4_fix`, `atm_n2o_fix` (set to a positive value to pin). The January value is broadcast to all columns as the initial `CO2EI_col`, `CH4E_col`, `Z2OE_col`.

### 4.4 `read_soil_warming_Tref(year, NHW, NHE, NVN, NVS)` (`ClimReadMod.F90:1023`)

Optional. Reads a time-varying `TEMP_vr(time, levsoi, column)` field from a prescribed-warming NetCDF identified by `EcosysWarmingMod::get_warming_fname`. Populates `TKS_ref_vr(time, level, NY, NX)` in Kelvin. Used by the OTC/IR warming path in `WthrMod::PrepHourlyWeather`.

---

## 5. `PlantInfoMod.F90` — plant parameters and management

**Entry point**: `ReadPlantInfo(yearc, yeari, NHW, NHE, NVN, NVS)` (`PlantInfoMod.F90:39`).

Two-phase flow:

1. `ReadPlantInfoNC(yeari, ...)` — reads the per-PFT, per-year trait and distribution NetCDF. Sources: `pft_file_in` (the reusable parameter NetCDF, e.g., `input_data/ecosim_pftpar_20251018.nc`) and `pft_mgmt_in` (the site-specific planting/harvest NetCDF).
2. `READQ(yearc, yeari, NHW, NHE, NVN, NVS)` (`PlantInfoMod.F90:63`) — opens `pft_mgmt_in` and calls `ReadPlantManagementNC` (`PlantInfoMod.F90:80`), which in turn dispatches to:
   - `readplantinginfo` (`PlantInfoMod.F90:109`) — reads `pft_pltinfo(JP, ntopou, year)` (a character-encoded `(DD, MM, YYYY, population, depth)` string per PFT), parses the day/month/year, converts to ordinal day, and sets `iDayPlanting_pft`, `iYearPlanting_pft`, `iPlantingDay_pft`, `iPlantingYear_pft`, `PPatSeeding_pft`, `PlantinDepz_pft`.
   - `readplantmgmtinfo` (`PlantInfoMod.F90:219`) — reads up to 24 management events per PFT per year from `pft_mgmt(24, JP, ntopou, year)` and `nmgnts(JP, ntopou, year)`. Each event is an ASCII-encoded string interpreted as tillage / cut / harvest parameters (`ECUT1*`, `ECUT2*`, `HCUT`, `PCUT`, `JCUT`). Populates `iHarvstType_pft`, `jHarvstType_pft`, `CanopyCutProxy_pft`, `THIN_pft`, `FracBiomHarvsted(...)`.

A ledger file `plant_trait.{year}.desc` is optionally opened when `disp_planttrait` is true, listing each PFT's traits for verification (`PlantInfoMod.F90:82-86`).

`InitPlantMgmnt(NHW,NHE,NVN,NVS)` (`PlantInfoMod.F90:190`) initializes the management arrays before reading, setting default harvest fractions to 1.0 and disturbance types to -1.

---

## 6. `ReadManagementMod.F90` — soil management

**Entry point**: `ReadManagementFiles(yeari)` (`ReadManagementMod.F90:409`). Skipped when `soil_mgmt_in == 'NO'`.

**Structure**: `soil_mgmt_in` is a single NetCDF file holding, per (topounit, year), the subfile identifiers `fertf`, `tillf`, `irrigf`. For each topounit, `ReadManagementFiles`:

1. Reads `NH1`, `NV1`, `NH2`, `NV2` (the corner indices of the topounit).
2. Reads the three subfile-identifier strings (`fertf`, `tillf`, `irrigf`) and calls the appropriate sub-reader, skipping any whose identifier is `'NO'`:
   - `ReadTillageFile` (`ReadManagementMod.F90:36`) reads a `tillf` variable holding per-day entries of the form `DDMMYYYY` + intensity/depth (e.g., tillage types 1-20, litter removal=21, fire=22, drainage=23-24). Populates `iSoilDisturbType_col(I, NY, NX)` and `DepzCorp_col(I, NY, NX)`.
   - `ReadIrrigationFile` (`ReadManagementMod.F90:101`). Populates `RRIG(J, I, NY, NX)`, `WDPTH(I, NY, NX)`, `ROWI(I, NY, NX)`, and precipitation chemistry arrays.
   - `ReadFertlizerFile` (`ReadManagementMod.F90:277`). Populates `FERT(N, I, NY, NX)` for N=1..20 fertilizer tracers (urea, NH4, NO3, PO4, etc.), plus the event type arrays `IYTYP(iAmendtyp_*, I, NY, NX)` for inorganic amendments, plant residues, and manure.

**Automatic irrigation**: If `irrigf(1:4) == 'auto'`, the flag `Lirri_auto` is set and the irrigation file is interpreted as automatic-irrigation triggers (`IIRRA(1:4, NY, NX)` = start/end dates + start/end hours; `DIRRA(1:2, NY, NX)` = depletion/refill depths; `CIRRA_col` = fraction-of-field-capacity target; `FIRRA_col` = depletion threshold). The actual daily decision is made in `DayMod::TillageandIrrigationEvents` (`DayMod.F90:265-300`).

**Fire**: `ReadFire(yearc, fire_event_entry, NHW, NHE, NVN, NVS)` (`ReadManagementMod.F90:516`). Called from `readsmod` when a fire-event entry matches the current year. Reads fire intensity, footprint (`iSoilDisturbType_col = 22`), and cascades to `ReadPlantFireMgmt` (`ReadManagementMod.F90:592`) for the per-PFT effect.

---

## 7. `restUtilMod.F90` — restart-variable helpers

**Role**: Provides `restartvar(ncid, flag, varname, ...)` overloaded across types (`int`, `real_sp`) and ranks (0D through 5D), plus `cpcol` and `cppft` overloads for rank-preserving column-by-column and PFT-by-PFT copying. Declarations at `restUtilMod.F90:28-40`.

**Interpolation flags** (`restUtilMod.F90:42-44`):
- `iflag_interp = 1` — if the restart's grid differs from the run's grid, interpolate.
- `iflag_copy   = 2` — copy verbatim.
- `iflag_skip   = 3` — do not restore this variable.

**Use**: `RestartMod.F90` calls `restartvar(...)` hundreds of times to read/write every checkpointed state field; see `history_and_restart.md` for restart flow.

---

## 8. `MicrobeInfoMod.F90`

Stub module (19 lines). Contains a single empty subroutine `WriteMicrobeTraits()` (`MicrobeInfoMod.F90:15`). Placeholder for future microbial-trait output. No readers.

---

## Cross-reference: what populates what

| Namelist path | Reader chain | Populates |
|---|---|---|
| `grid_file_in` | `readimod::readi` | Site geometry, water table, boundary conditions, soil profile |
| `pft_file_in` | `PlantInfoMod::ReadPlantTraitTable` | PFT parameter tables (`PlantTraitTableMod`) |
| `pft_mgmt_in` | `PlantInfoMod::ReadPlantInfo` → `readplantinginfo`, `readplantmgmtinfo` | Planting dates, PFT management events |
| `clm_day_file_in` / `clm_hour_file_in` | `ClimReadMod::ReadClimNC` (via `readsmod::ReadClimateForc`) | Daily/hourly weather arrays, precipitation chemistry, `Z0G`, `ZNOONG` |
| `clm_factor_in` | `readsmod::ReadClimateCorrections` | Annual climate-change overlays |
| `soil_mgmt_in` | `ReadManagementMod::ReadManagementFiles` | Tillage, fertilizer, irrigation schedules |
| `atm_ghg_in` | `ClimReadMod::GetAtmGts` | Atmospheric CO2/CH4/N2O monthly series |
| (fire event, keyed on `yearc`) | `ReadManagementMod::ReadFire` | Fire disturbance event |
| (soil warming, `EcosysWarmingMod` path) | `ClimReadMod::read_soil_warming_Tref` | `TKS_ref_vr(time, level, col)` |
