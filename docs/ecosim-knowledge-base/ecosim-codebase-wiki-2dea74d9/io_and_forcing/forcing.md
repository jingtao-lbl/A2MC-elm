---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/Modelforc/` — four modules that drive the model from already-loaded forcing arrays
**Last verified:** 2026-04-24
---

# Forcing Pipeline (`f90src/Modelforc/`)

The `Modelforc` subsystem converts forcing arrays that have been loaded by `f90src/IOutils/` readers into the per-column, per-timestep state fields consumed by the physics/BGC core. It does not itself open NetCDF files; it transforms `ClimForcDataType` arrays (`TMPX`, `TMPN`, `WIND`, `RAIN`, `SRAD`, `DWPT` for daily; `TMP_hrly`, `WINDH`, `DWPTH`, `RAINH`, `SWRad_hrly`, `PBOT_hrly`, `RadLWClm` for hourly) into the working fields (`TCA_col`, `TairK_col`, `VPK_col`, `WindSpeedAtm_col`, `PBOT_col`, `RADN_col`, `RadSWDirect_col`, `RadSWDiffus_col`, `RadDirectPAR_col`, `RadPARDiffus_col`, `SkyLonwRad_col`, `PrecAsRain_col`, `PrecAsSnow_col`).

Four files organize this by temporal scope:

| File | Role | Public entry |
|---|---|---|
| `YearMod.F90` | Annual accumulator reset | `SetAnnualAccumlators` (`YearMod.F90:34`) |
| `DayMod.F90` | Daily reset + tillage/irrigation decisions | `day` (`DayMod.F90:42`) |
| `Hour1Mod.F90` | Hourly "phase 1" (state reset, disturbance, radiation, balance-check bracket) | `hour1`, `InitHour1` (`Hour1Mod.F90:63-64`) |
| `WthrMod.F90` | Weather-to-state translator with radiation partitioning | `PrepHourlyWeather` (`WthrMod.F90:48`) |

---

## 1. Forcing variables

### 1.1 Daily forcing (fields of `ClimForcDataType`, populated in `ClimReadMod::ReadClimNC` when `IWTHR==1`)

| Array | Dim | Units after read | Source NetCDF var |
|---|---|---|---|
| `TMPX(I)` | `(366)` | C | `TMPX` |
| `TMPN(I)` | `(366)` | C | `TMPN` |
| `WIND(I)` | `(366)` | m s-1 (converted to m hr-1 in `ReadClimNC`) | `WIND` |
| `RAIN(I)` | `(366)` | mm d-1 from file → m d-1 post-convert | `RAIN` |
| `SRAD(I)` | `(366)` | MJ m-2 d-1 | `SRAD` |
| `DWPT(1..2, I)` | `(2, 366)` | kPa | `DWPT` (single value, copied to both) |

### 1.2 Hourly forcing (`IWTHR==2`)

| Array | Dim | Units | Source NetCDF var |
|---|---|---|---|
| `TMP_hrly(J, I)` | `(24, 366)` | C | `TMPH` |
| `WINDH(J, I)` | `(24, 366)` | m hr-1 (converted from m s-1) | `WINDH` |
| `DWPTH(J, I)` | `(24, 366)` | kPa | `DWPTH` |
| `RAINH(J, I)` | `(24, 366)` | m hr-1 (converted from mm hr-1) | `RAINH` |
| `SWRad_hrly(J, I)` | `(24, 366)` | MJ m-2 hr-1 (converted from W m-2) | `SRADH` |
| `PBOT_hrly(J, I)` | `(24, 366)` | kPa | `PATM` (optional; defaults 101.325) |
| `RadLWClm(J, I)` | `(24, 366)` | MJ m-2 hr-1 | `XRADH` (optional; defaults 0) |

### 1.3 Precipitation chemistry and site scalars (loaded once per forcing year)

Structure `atm_forc_type` (`ClimReadMod.F90:28-43`): `Z0G` (anemometer height, m), `ZNOONG` (solar-noon offset, hours), `PHRG` (precip pH), ion concentrations in precipitation (`CN4RIG`=NH4, `CNORIG`=NO3, `CPORG`=H2PO4, `CALRG`=Al, `CFERG`=Fe, `CCARG`=Ca, `CMGRG`=Mg, `CNARG`=Na, `CKARG`=K, `CSORG`=SO4, `CCLRG`=Cl).

### 1.4 Atmospheric CO2/CH4/N2O (`GetAtmGts`, `ClimReadMod.F90:900`)

Monthly arrays `atm_co2_mon(1:12)` (ppm), `atm_ch4_mon(1:12)` (ppb), `atm_n2o_mon(1:12)` (ppb). Overridable by scalars `atm_co2_fix`, `atm_ch4_fix`, `atm_n2o_fix` when positive.

---

## 2. Annual entry: `YearMod::SetAnnualAccumlators`

**Call site**: start of each simulated year (in the main driver).

**Signature**: `SetAnnualAccumlators(I, NHW, NHE, NVN, NVS)` (`YearMod.F90:38`). `I` is day-of-year (called on day 1 by convention).

**Action** (`YearMod.F90:47-136`):

- Zero per-column annual cumulative flux arrays: `GasHydroLoss_cumflx_col`, `Gas_Prod_TP_cumRes_col`, `QdewCanopy_CumYr_pft`, `trcg_mass_cumerr_col`, `GDD_col`, `AmendC_CumYr_flx_col`, `LiterfalOrgM_col`, `RootResp_CumYr_col`, `Eco_NBP_CumYr_col`, `QRain_CumYr_col`, `QEvap_CumYr_col`, `Qrunoff_CumYr_col`, `SedmErossLoss_CumYr_col`, `H2OLoss_CumYr_col`, `HydroIonFlx_CumYr_col`, `FertN_Flx_CumYr_col`, `HydroSufDINFlx_CumYr_col`, `FerP_Flx_CumYr_col`, `HydroSufDIPFlx_CumYr_col`, and the fire-emission CumYr counters (CO2/CH4/O2/N2O/NH3/PO4).
- Zero the ecosystem flux CumYr counters (`Eco_HR_CumYr_col`, `Eco_GPP_CumYr_col`, `Eco_NPP_CumYr_col`, `Eco_AutoR_CumYr_col`, `EcoHavstElmnt_CumYr_col`).
- Zero the mineralization CumYr counters (`NetNH4Mineralize_CumYr_col`, `NetPO4Mineralize_CumYr_col`).
- Zero per-PFT `HoursTooLowPsiCan_pft`, `PlantElmBalCum_pft`, `QDrain_cum_col`.
- For each PFT: zero `cumNPP_pft`; update `NetCumElmntFlx2Plant_pft(ielmc, ...)`, `NetCumElmntFlx2Plant_pft(ielmn, ...)`, and `NetCumElmntFlx2Plant_pft(ielmp, ...)` by accumulating last year's net C/N/P fluxes (fix - respire - fire emissions ± uptake); zero per-PFT CumYr counters (`GrossCO2Fix_CumYr_pft`, `GrossRespC_CumYr_pft`, root uptake, N2 fixation, NH3 emission, fire emissions per PFT, `EcoHavstElmnt_CumYr_pft`, litterfall totals).
- If erosion mode is `ieros_frzthaweros` or `ieros_frzthawsomeros`, zero `TSED_col`.

The southern/northern-hemisphere branch at `YearMod.F90:53` is written as a stub (both branches zero at `I == 1`); this is a placeholder for GDD-based year start.

---

## 3. Daily entry: `DayMod::day`

**Signature**: `day(I, NHW, NHE, NVN, NVS)` (`DayMod.F90:45`).

**Action** (`DayMod.F90:45-86`):

1. Compute the equation-of-time solar-noon correction:
   ```
   eot = calculate_equation_of_time(I, leapday)
   SolarNoonHour_col(NY, NX) = SolarNoonHourYM_col(NY, NX) + eot
   ```
2. Call `UpdateDailyAccumulators(I, NHW, NHE, NVN, NVS)` (`DayMod.F90:89`).
3. Call `TillageandIrrigationEvents(I, NHW, NHE, NVN, NVS)` (`DayMod.F90:216`).
4. If `ldo_sp_mode`, call `PrescribePhenologyInterp(I, NHW, NHE, NVN, NVS)`.

### 3.1 `UpdateDailyAccumulators` (`DayMod.F90:89`)

Resets `HUDX_col=0`, `HUDN_col=100`, `TWIND_col=0`, per-PFT `SeasonalNonstCDayAve_pft=0`. Updates daylength: `DayLenthPrev_col = DayLensCurr_col`, then `DayLensCurr_col = GetDayLength(ALAT_col, I)`.

**Daily-to-hourly disaggregation setup** (`DayMod.F90:141-168`): if `IWTHR==1` (daily forcing), prepare bookends for hourly interpolation:
- Max hourly radiation: `RMAX = SRAD(I) / (DayLensCurr_col * 0.658)` (or `= SRAD(I)` for phytotron, `KoppenClimZone_col == -2`).
- `TAVG1`, `TAVG2`, `TAVG3` = averages of adjacent-day maxes and min (running mean across I-1, I, I+1).
- `AMP1`, `AMP2`, `AMP3` = amplitudes (TAVG-TMPN) for each bookend.
- `VAVG*`, `VMP*` — same pattern for vapor pressure.

**Climate-change overlays** (`DayMod.F90:180-209`): for each month N=1..12, applies `DTMPX(N)`, `DTMPN(N)`, `DRAD(N)`, `DWIND(N)`, `DHUM(N)`, `DPREC(N)`, `DIRRI(N)`, `DCN4R(N)`, `DCNOR(N)` as step changes (`ICLM==1`), as incremental annual additions (`ICLM==2`), into the `TDTPX`, `TDTPN`, `TDRAD`, `TDWND`, `TDHUM`, `TDPRC`, `TDIRI`, `TDCN4`, `TDCNO` accumulators. Applied later in `WthrMod::CorrectClimate`.

### 3.2 `TillageandIrrigationEvents` (`DayMod.F90:216`)

- Translates `iSoilDisturbType_col(I, NY, NX)` (from `ReadManagementMod::ReadTillageFile`) into a mixing fraction `CORP` and residual `XTillCorp_col = 1 - CORP` used by the soil redistribution path (`DayMod.F90:236-246`).
- Handles automatic irrigation when `Lirri_auto`: if today falls within `IIRRA(1, NY, NX) <= I <= IIRRA(2, NY, NX)`, compute depletion-weighted field capacity target and trigger hour-distributed irrigation during `IIRRA(3, NY, NX)` to `IIRRA(4, NY, NX)`, setting `RRIG(J, I, NY, NX)`. Trigger logic supports two modes (`DayMod.F90:284`):
  - `iIrrigOpt_col == iIrrig_swc`: soil-water-content criterion (`TVW < TWP + FIRRA_col * (TFZ - TWP)`).
  - `iIrrigOpt_col == iIrrig_cwp`: canopy-water-potential criterion (`PSICanPDailyMin_pft(1, ...) < FIRRA_col`).

---

## 4. Hourly entry: `Hour1Mod::hour1`

**Signature**: `hour1(I, J, NHW, NHE, NVN, NVS)` (`Hour1Mod.F90:85`). `I` is day-of-year, `J` is hour-of-day (1..24).

**Sequence** (`Hour1Mod.F90:102-250`):

1. `ResetLndscapeAccumlators()` — zero landscape-level hourly totals (water, heat, gas, solute; `Hour1Mod.F90:253`).
2. `SetAtmsTracerConc(I, J, NHW, NHE, NVN, NVS)` — apply monthly atmospheric CO2/CH4/N2O for the current month (`Hour1Mod.F90:275`).
3. `ResetFluxArrays(I, NHW, NHE, NVN, NVS)` — zero per-column hourly flux arrays (`Hour1Mod.F90:317`).
4. If `salt_model`, `ResetSaltModelArrays(NHW, NHE, NVN, NVS)` (`Hour1Mod.F90:426`).
5. If `J == 1`, zero `NumActivePlants_col` and `PSICanPDailyMin_pft` for the new day.
6. `UpdateLiterPropertz(NHW, NHE, NVN, NVS)` — refresh litter-layer hydrological properties.
7. `SetLiterSoilPropAftDisturb(I, J, NHW, NHE, NVN, NVS, dosum)` — apply post-disturbance litter/soil-property update (`Hour1Mod.F90:643`).
8. If `dosum`, `SummarizeTracerMass(I, J, NHW, NHE, NVN, NVS)` (from `BalancesMod`).
9. **`BegCheckBalances(I, J, NHW, NHE, NVN, NVS)`** — snapshot state for end-of-hour conservation check. See `../diagnostics/index.md`.
10. `SetSurfaceProp4SedErosion(NHW, NHE, NVN, NVS)` (`Hour1Mod.F90:873`).
11. Per-column loop: call (in order) `SetHourlyDiagnostics` (`Hour1Mod.F90:709`), `SetArrays4PlantSoilTransfer`, `UpdateTotalSOC` (if erosion mode requires), `ZeroHourlyArrays`, **`DiagWaterTBLDepz`** (`Hour1Mod.F90:178`, from `HydrologyDiagMod`), `GetChemicalConcsInSoil`, `GetSoluteConcentrations`, `Prep4PlantMicrobeUptake`, `CalGasSolubility`, `GetSoilHydraulicVars`, `DiagActiveLayerDepth`, `GetSurfResidualProperties`, `SetTracerPropertyInLiterAir`, optional `ForceGasAquaEquil` (if `do_instequil`), `PlantCanopyRadsModel` (canopy radiation), and update the hourly LW/NEE bookkeeping.
12. Zero the per-column hourly Eco_Heat_* and Eco_NEE bookkeeping fields (`Hour1Mod.F90:213-221`).
13. `CanopyInterceptPrecip` per column.
14. `ApplyFertilizerAtNoon(I, J, NHW, NHE, NVN, NVS)` (from `FertilizerMod`) — triggers scheduled fertilizer events at local solar noon.

**Init**: `InitHour1(NumOfLitrCmplxs)` (`Hour1Mod.F90:73`) allocates the module-private `THETRX(1:NumOfLitrCmplxs)` — litter water-retention capacity — with hard-coded defaults `(/4.0e-06, 8.0e-06, 8.0e-06/)`.

---

## 5. Weather translator: `WthrMod::PrepHourlyWeather`

**Signature**: `PrepHourlyWeather(I, J, NHW, NHE, NVN, NVS)` (`WthrMod.F90:51`).

**Flow** (`WthrMod.F90:72-128`):

1. Compute continuous `DOY = I - 1 + J/24` (`WthrMod.F90:74`).
2. Branch on `IWTHR`:
   - `ITYPE == 1` (daily forcing): `DailyWeather(I, J, ..., RADN_col, PrecAsRain_col, PrecAsSnow_col, VPS)` (`WthrMod.F90:132`). Disaggregates daily quantities into the current hour using the `TAVG*`, `AMP*`, `VAVG*`, `VMP*`, `RMAX` coefficients computed in `DayMod`.
   - `IWTHR == -999` (ATS coupled mode): uses `RMAX` directly for radiation; hour-of-day temperature/humidity/wind arrive from the coupler, not read here.
   - Otherwise (hourly forcing): `HourlyWeather(I, J, ..., RADN_col, PrecAsRain_col, PrecAsSnow_col, VPS)` (`WthrMod.F90:228`). Simply copies `SWRad_hrly(J, I)`, `TMP_hrly(J, I)`, `DWPTH(J, I)`, `WINDH(J, I)`, `PBOT_hrly(J, I)`, and partitions `RAINH(J, I)` into `PrecAsRain_col` or `PrecAsSnow_col` based on `TCA_col > TSNOW` (threshold `-0.25 C`, `WthrMod.F90:46`).
3. If `check_warming_dates(iYearCurrent, I, J)` (from `EcosysWarmingMod`):
   - `apply_OTC_warming(I, J, NHW, NHE, NVN, NVS)` — open-top-chamber warming.
   - `apply_IR_warming(I, J, NHW, NHE, NVN, NVS)` — infrared heating-lamp warming.
4. `CalcRadiation(I, J, NHW, NHE, NVN, NVS, RADN_col, PRECUI_col, PRECII_col)` (`WthrMod.F90:274`).
5. `SummaryClimateForc(I, J, ..., PRECUI_col, PrecAsRain_col, PRECII_col, PrecAsSnow_col)` (`WthrMod.F90:526`).

### 5.1 Daily disaggregation (`DailyWeather`, `WthrMod.F90:132-225`)

Computes the current hour's:

- **Shortwave radiation**: sine-of-hour-angle model,
  ```
  RADN_col = max(0, RMAX * sin((J - (SolarNoonHour - DayLen/2)) * π / DayLen))
  ```
  (`WthrMod.F90:155`). For phytotron (`KoppenClimZone == -2`), constant `RMAX/24`.
- **Air temperature**: piecewise-sinusoidal interpolation around solar noon using `TAVG1/2/3`, `AMP1/2/3`:
  - Pre-dawn: `TCA_col = TAVG1 + AMP1 * sin(...)`.
  - Post-noon: `TCA_col = TAVG3 + AMP3 * sin(...)`.
  - Mid-day: `TCA_col = TAVG2 + AMP2 * sin(...)`.
- **Vapor pressure**: analogous piecewise sinusoid using `VAVG*`, `VMP*`.
- **Wind**: flat (no diurnal cycle; uses daily `WIND(I)`).
- **Precipitation**: equal distribution over hours (daily `RAIN(I) / 24`).

### 5.2 Hourly copy (`HourlyWeather`, `WthrMod.F90:228-271`)

Direct assignments from hourly forcing with unit safety:
```fortran
RADN_col(NY,NX)  = SWRad_hrly(J,I)                    ! MJ/m2/hr
TCA_col(NY,NX)   = TMP_hrly(J,I)
TairK_col(NY,NX) = Celcius2Kelvin(TCA_col(NY,NX))
VPS(NY,NX)       = vapsat0(TairK_col) * exp(-ALTI_col/7272.0)   ! elevation-corrected saturation kPa
VPK_col(NY,NX)   = min(DWPTH(J,I), VPS(NY,NX))                  ! cap at saturation
WindSpeedAtm_col(NY,NX) = max(3600.0, WINDH(J,I))                ! floor at 3600 m/hr = 1 m/s
PBOT_col(NY,NX)  = PBOT_hrly(J,I)
```

Rain/snow partition (`WthrMod.F90:259-265`): if `TCA > TSNOW`, all precip is rain; else all snow.

### 5.3 Radiation partitioning (`CalcRadiation`, `WthrMod.F90:274-409`)

Per column per hour:

1. Compute sine of solar inclination using declination (`get_sun_declin(I)`) and latitude:
   ```
   AZI = sin(ALAT * rad) * sin(DECLIN * rad)
   DEC = cos(ALAT * rad) * cos(DECLIN * rad)
   SineSunInclAngle_col = max(0, AZI + DEC * cos(π/12 * (SolarNoonHour - (J - 0.5))))
   ```
   (`WthrMod.F90:305-315`). Matches Campbell & Norman (1998) eq. 11.1. `SineSunInclAnglNxtHour_col` evaluated at `J + 0.5` for the next hour.
2. Clip `RADN_col` to the theoretical top-of-atmosphere value: `RADX = SolConst * max(0, SineSunInclAngle_col)`, where `SolConst = 4.896 MJ/m2/hr` (≈ 1360 W/m2; `WthrMod.F90:41`).
3. Split into direct + diffuse:
   ```
   RADZ                   = min(RADN_col, 0.5 * (RADX - RADN_col))   ! diffuse
   RadSWDirect_col        = safe_adb(RADN_col - RADZ, SineSunInclAngle_col) * srad_scalar_col
                            clipped to 4.167 MJ/m2/hr ceiling
   RadSWDiffus_col        = RADZ / TotSineSkyAngles_grd * srad_scalar_col
   RadDirectPAR_col       = RadSWDirect_col * CDIR * PDIR             ! CDIR=0.42, PDIR=1269.4
   RadPARDiffus_col       = RadSWDiffus_col * CDIF * PDIF             ! CDIF=0.58, PDIF=1269.4
   ```
   Partition constants at `WthrMod.F90:42-45`.
4. Sky emissivity (longwave): `CLD = min(1, max(0.2, 2.33 - 3.33*RADN_col/RADX))`; `EMM = 0.625 * max(1, (1000*VPK/TairK)^0.131) * (1 + 0.242 * CLD^0.583)` (Duarte et al. 2006 form).
5. Longwave down:
   ```
   SkyLonwRad_col = EMM * stefboltz_const * TairK_col^4
   if RadLWClm(J, I) > 0:  SkyLonwRad_col = SkyLonwRad_col + RadLWClm(J, I)
   ```
   i.e., the optional prescribed-LW field is additive, not replacing.
6. Irrigation injection: `PRECII_col(NY, NX) = RRIG(J, I, NY, NX)` (surface irrigation); `PRECUI_col` reserved for subsurface irrigation (currently zero, `WthrMod.F90:401-402`).

### 5.4 Summary accumulators (`SummaryClimateForc`, `WthrMod.F90:526-573`)

Accumulates the hourly column-level climate quantities into the annual totals (`QRain_CumYr_col`, `Eco_NetRad_col`, etc.), which are later written to the history tapes by `HistDataType::hist_update`.

---

## 6. Temporal ordering (reference)

Inside the main time loop (conceptual, with the actual sequencing in `drivers/`):

```
for each year:
    SetAnnualAccumlators            (Modelforc/YearMod.F90)
    for each day:
        day                         (Modelforc/DayMod.F90)
        for each hour:
            hour1                   (Modelforc/Hour1Mod.F90)  ← BegCheckBalances here
            PrepHourlyWeather       (Modelforc/WthrMod.F90)
            <physics + BGC>
            EndCheckBalances        (ModelDiags/BalancesMod.F90)
            hist_update, hist_update_hbuf, hist_htapes_wrapup  (IOutils)
```

`DiagWaterTBLDepz` is called per-column inside `hour1` before hydraulics (`Hour1Mod.F90:178`). `DiagSoilGasPressure` is called elsewhere in the physics core when gas concentrations need to be expressed as mole-fraction equivalents.

---

## 7. Forcing-flag cheat sheet

| Flag | File / namelist | Effect |
|---|---|---|
| `IWTHR` | Set by `ClimReadMod::get_forc_step_type(yeari)` | 1=daily, 2=hourly, -999=ATS coupled |
| `fixClime` | `EcoSIMCtrlMod` (namelist) | Bypass all reading, broadcast `clim_var` everywhere |
| `atm_co2_fix`, `atm_ch4_fix`, `atm_n2o_fix` | namelist (positive values) | Pin atmospheric concentration, skip history read |
| `ICLM` | from `clm_factor_in` | 0=no change, 1=step, 2=incremental annual |
| `ats_cpl_mode` | namelist | Couple with ATS (sets `IWTHR=-999` path) |
| `srad_scalar_col`, `EMS_Modify_Scalar_col` | column-level scalars | Per-column SW / longwave emissivity modifier (default 1.0, `WthrMod.F90:266-267`) |
| `plantOM4Heat` | namelist | Plant OM contributes to soil heat balance |
| `Lirri_auto` | Set by `ReadManagementMod` when `irrigf(1:4)=='auto'` | Enables automatic-irrigation triggers in `DayMod::TillageandIrrigationEvents` |
