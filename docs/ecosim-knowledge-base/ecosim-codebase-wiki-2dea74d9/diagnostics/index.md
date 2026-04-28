---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/ModelDiags/` — three modules for runtime mass-balance and state diagnostics
**Last verified:** 2026-04-24
---

# Model Diagnostics (`f90src/ModelDiags/`)

The `ModelDiags` subsystem contains three small modules that run inside the hourly time loop to (1) enforce water/heat/tracer-mass conservation, (2) diagnose the internal water-table depth, and (3) compute soil-gas partial pressures. Together they provide the closure checks and derived state that downstream history-output code consumes.

| File | Lines | Purpose | Public API |
|---|---|---|---|
| `BalancesMod.F90` | 516 | Hour-by-hour closure audit of water, heat, and tracer (gas-phase) mass budgets; plus storage and tracer-mass summarizers used both by the audit and by output. | `BegCheckBalances`, `EndCheckBalances`, `SummarizeTracerMass`, `SummarizeSnowMass`, `SummarizeTracers` (`BalancesMod.F90:30-34`) |
| `HydrologyDiagMod.F90` | 122 | Diagnose the internal water-table depth per soil column from air-filled porosity and matric potential. | `DiagWaterTBLDepz` (`HydrologyDiagMod.F90:18`) |
| `SoilDiagsMod.F90` | 70 | Convert dissolved-phase gas masses into per-layer gas pressures and mole-fraction composition. | `DiagSoilGasPressure` (`SoilDiagsMod.F90:28`) |

---

## 1. `BalancesMod.F90` — mass / energy closure

### 1.1 Bracket pattern

Every hour, the physics core is bracketed by two calls:

- `BegCheckBalances(I, J, NHW, NHE, NVN, NVS)` (`BalancesMod.F90:37`) — snapshot the state **before** the hour's fluxes are applied.
- `EndCheckBalances(I, J, NHW, NHE, NVN, NVS)` (`BalancesMod.F90:170`) — compute the closure errors **after** the hour's fluxes have updated state.

`BegCheckBalances` is invoked from `Hour1Mod::hour1` at `Hour1Mod.F90:151`, right before per-column hourly diagnostics. `EndCheckBalances` is invoked at end-of-hour from the main time loop after the physics/BGC core finishes.

### 1.2 What `BegCheckBalances` stores (`BalancesMod.F90:45-74`)

For every column:

| Snapshot variable | Source state |
|---|---|
| `WaterErr_col` | `WatMass_col` (total column water mass) |
| `HeatErr_col` | `HeatStore_col` (total column heat content) |
| `SnowEngyBeg_col` | `SnowEngyEnd_col` from previous step |
| `CanopyWaterMassBeg_col` | `CanopyWaterMassEnd_col` |
| `SnowMassBeg_col` | `SnowMassEnd_col` |
| `LitWatMassBeg_col` | `LitWatMassEnd_col` |
| `SoilWatMassBeg_col` | `SoilWatMassEnd_col` |
| `trcs_solml_dribBeg_col(ids)` | `trcs_solml_drib_vr(ids, 0, ...)` + sum over live soil layers |
| `trcg_TotalMass_beg_col(idg)` | `trcg_TotalMass_col(idg)` |
| `trcg_soilMass_beg_col(idg)` | `trcg_soilMass_col(idg)` |
| `trcg_rootMass_beg_col(idg)` | `trcg_rootMass_col(idg)` (for `idg` up to `idg_NH3`) |
| `trcg_snowMass_beg_col(idg)` | `trcg_snowMass_col(idg)` (same range) |

### 1.3 What `EndCheckBalances` checks (`BalancesMod.F90:170-424`)

For every column, compute closure residuals:

- **Soil water** (`BalancesMod.F90:201-206`):
  ```
  SoilWatErr_test = SoilWatMassBeg - SoilWatMassEnd
                  + Qinflx2Soil - QDrain - QDischarg2WTBL
                  + TPlantRootH2OUptake + QLaterFlow2Cell    (if !fixWaterLevel)
  ```
- **Precipitation partition** (`BalancesMod.F90:207-213`): `precipErr_test`, `prec2expSErr_test`, `prec2SnoErr_test`, `literH2Oerr_test`, `SnowMassErr_test`, `canopyH2Oerr_test`.
- **Column water** (`BalancesMod.F90:218-224`):
  ```
  WaterErr_test = WaterErr - WatMass
                + PrecAtm + Irrigation + QLaterFlow2Cell + RainLitr
                + VapXAir2GSurf + QVegET + QRunSurf
                - QDrain - QDischarg2WTBL + TPlantRootH2OUptake - QCanopyWat2Dist
  ```
- **Heat** (`BalancesMod.F90:225-228`):
  ```
  HeatErr_test = HeatErr - HeatStore
               + THeatRootRelease + HeatSource + Eco_NetRad
               + Eco_Heat_Latent + Eco_Heat_Sens + PrecHeat
               + THeatSoiThaw + THeatSnowThaw + HeatRunSurf
               - HeatDrain - HeatDischar - HeatCanopy2Dist
  ```
- **Gas-phase tracer mass** for each `idg` in `idg_beg..idg_NH3` (`BalancesMod.F90:288-305`):
  ```
  tracer_mass_err = trcg_TotalMass_beg - trcg_TotalMass
                  + SurfGasEmiss_all_flx + GasHydroLoss_flx
                  + trcs_solml_drib_col(idg) + RGasNetProd
                  - trcs_deadroot2soil
  ```
- **Root-internal gas mass** for the same range:
  ```
  tracer_rootmass_err = trcg_rootMass_beg - trcg_rootMass - trcs_deadroot2soil
                      + trcs_Soil2plant_uptake + trcg_air2root_flx + TRootGasLossDisturb
  ```
  with species-specific adjustments for O2 (`- RootO2_TotSink`) and CO2 (`+ RootCO2Ar2Root`) at `BalancesMod.F90:307-311`. `idg_NH3` also absorbs the band phase `idg_NH3B`.
- **Snow-phase tracer mass** per gas (`BalancesMod.F90:314-316`):
  ```
  tracer_snowmass_err = trcg_snowMass_beg - trcg_snowMass + Gas_WetDepo2Snow - Gas_Snowloss_flx
  ```
- Cumulative residual accumulation into `trcg_mass_cumerr_col(idg)` and `GasHydroLoss_cumflx_col(idg)` (`BalancesMod.F90:294`, `BalancesMod.F90:313`).

### 1.4 Thresholds and failure policy

- `err_h2o = 1.0e-4 kg` (`BalancesMod.F90:177`): water error tolerance.
- `err_engy = 1.0e-6 J` (`BalancesMod.F90:178`): heat error tolerance.
- Tracer error threshold: `1.0e-5` for `AMAX1(|mass_err|, |rootmass_err|)` (`BalancesMod.F90:317`).

On breach:
- If `iVerbLevel == 1` or `|SoilWatErr_test| > err_h2o`, a detailed diagnostic block is written to Fortran unit 110 (for water) or 111 (for tracers) listing every term of the budget (`BalancesMod.F90:230-269`).
- If `|SoilWatErr_test| > err_h2o`, `endrun` is called with `'H2O error test failure'` (`BalancesMod.F90:271`).
- Tracer mass errors trigger analogous reporting and abort.

The unit-110/unit-111 files are plain ASCII, opened once at startup.

### 1.5 Helper summarizers

- `SummarizeStorage(I, J, ...)` (`BalancesMod.F90:77`) aggregates `WatMassStore_lnd` and `HeatStore_lnd` across the landscape; calls `SumUpWaterStorage` and `SumUpHeatStorage` per column.
- `SumUpWaterStorage(NY, NX)` (`BalancesMod.F90:109`) computes `CanopyWaterMassEnd`, `SnowMassEnd`, `LitWatMassEnd`, and the soil-column water mass end-of-step.
- `SumUpHeatStorage(NY, NX)` (`BalancesMod.F90:144`) computes `HeatStore_col` and snow-phase heat at end-of-step.
- `SummarizeSnowMass(NY, NX)` (`BalancesMod.F90:97`) summates `VLDrySnoWE_snvr + VLWatSnow_snvr + VLIceSnow_snvr * DENSICE` across snow layers.
- `SummarizeTracers(I, J, ...)` (`BalancesMod.F90:428`) walks the snow (1..`nsnol_col`), root (idg_beg..idg_NH3), and soil (NU..NL) layers, and produces `trcg_snowMass_col`, `trcg_rootMass_col`, `trcg_soilMass_col`, and the sum `trcg_TotalMass_col`. The `idg_NH3B` (ammonium-band) phase feeds into the NH3 total for litter (`BalancesMod.F90:452`) and is kept separate for `trcg_TotalMass_col(idg_NH3B, ...)` (`BalancesMod.F90:488`).
- `SummarizeTracerMass(I, J, ...)` (`BalancesMod.F90:505`) is a thin wrapper that chains `SummarizeStorage` and `SummarizeTracers`. Called both from `Hour1Mod::hour1` (via `SummarizeTracerMass` at `Hour1Mod.F90:149`, conditional on `dosum`) and from the top of `EndCheckBalances` (`BalancesMod.F90:196`).

### 1.6 Consumption by history output

The quantities closed by the BalancesMod audit feed into the `HistDataType::hist_update` pointers (`HistDataType.F90:3793`). Examples tied back:

- `HydroIonFlx_CumYr_col`, `GasHydroLoss_cumflx_col` → history fields like `cumFIRE_CO2_col`, `tSALT_DISCHG_FLX_col`.
- `trcg_mass_cumerr_col(idg)` → can be surfaced as a diagnostic field (reported via unit 111 and optionally wrapped as a history variable).
- Mass-conserving column totals `trcg_soilMass_col`, `trcg_TotalMass_col` → basis for the per-tracer totals reported in the history tapes.

---

## 2. `HydrologyDiagMod.F90` — water-table depth diagnosis

### 2.1 Public API

```fortran
public :: DiagWaterTBLDepz
```
(`HydrologyDiagMod.F90:18`).

### 2.2 Call site

Invoked per column from within `Hour1Mod::hour1`:

```
Hour1Mod.F90:178        call DiagWaterTBLDepz(I, J, NY, NX)
```

So this runs once per column per hour, after the hourly flux arrays are reset and before the hydraulic properties are rebuilt.

### 2.3 Algorithm (`HydrologyDiagMod.F90:23-122`)

Inputs per layer: air-filled porosity (`THETPZ_vr`), matric potential (`PSISoilMatricP_vr`), bulk porosity (`POROS_vr`), pore-size distribution parameter (`PSD_vr`), logarithmic scaling constants (`LOGPSIAtSat`, `LOGPSIMXD_col`, `LOGPOROS_vr`), layer thickness `DLYR_3D(3, L, NY, NX)`, and the grid-specific `ExtWaterTable_col` (external water-table depth).

Internal thresholds:
- `THETPW = 0.01` — minimum air-filled porosity for a layer to be considered unsaturated (`HydrologyDiagMod.F90:43`).
- `THETWP = 1.0 - THETPW`.

Logic:

1. For each layer `L = NUI..NLI`, compute:
   - Volumetric water content `THETW_vr(L)` and ice content `THETI_vr(L)` (or set to `POROS` when `VLSoilMicP_vr <= ZEROS`).
   - Air-filled pore `THETPZ_vr(L) = max(0, POROS - THETW - THETI)`.

2. Scan top-down for the first saturated layer (`THETPZ < THETPW`) or the bottom boundary. Set `FoundWaterTable = true`.

3. If the current mid-depth is above the external water table, keep scanning downward looking for an unsaturated layer that would disqualify this as a water table (`HydrologyDiagMod.F90:74-83`).

4. If `FoundWaterTable`, compute the equilibrium matric potential `PSIEquil` at the interface with the layer above (or below), then solve for `THETW1` — the water content corresponding to `PSIEquil` — using the pore-size-distribution relationship:
   ```
   THETW1 = min(THETWM, exp((LOGPSIAtSat - log(-PSIEquil)) * PSD / LOGPSIMXD + LOGPOROS))
   ```
   Then interpolate the water-table depth inside the current layer:
   ```
   THETPX = min(1, max(0, (THETWM - THETW) / (THETWM - THETW1)))
   DepzIntWTBL_col = CumDepz2LayBottom_vr(L) - DLYR_3D(3, L) * (1 - THETPX)
   ```
   (`HydrologyDiagMod.F90:96-101`). Fallback: if `THETWM <= THETW1`, the water table is placed at the top of the layer.

5. Output: `DepzIntWTBL_col(NY, NX)` — the internal water-table depth (m, positive downward from the soil surface).

### 2.4 Consumption by history output

`DepzIntWTBL_col` is populated every hour and sampled into the history tapes (exposed through the `HistDataType` pointer family; see the many `hist_addfld1d` calls in `HistDataType.F90`).

---

## 3. `SoilDiagsMod.F90` — soil-gas pressure diagnosis

### 3.1 Public API

```fortran
public :: DiagSoilGasPressure
```
(`SoilDiagsMod.F90:28`).

### 3.2 Algorithm (`SoilDiagsMod.F90:31-69`)

For each column `(NY, NX)` and each soil layer `L = NU..NL`, when both micropore water volume `VLWatMicP_vr(L, NY, NX)` and dissolved CO2 `trcs_solml_vr(idg_CO2, L, NY, NX)` exceed `ZEROS(NY, NX)`:

1. Compute gas-mass solubility per tracer (g m3 per mol d-2) using molecular weight and per-layer Henry-like solubility:
   ```
   GasMassSolubility(idg) = MolecularWeight(idg) * GasSolbility_vr(idg, L, NY, NX) * VLWatMicP_vr(L, NY, NX)
   ```
   (`SoilDiagsMod.F90:46-48`). `GasMassSolubility(idg_NH3B)` is copied from `GasMassSolubility(idg_NH3)`.
2. Per-tracer partial pressure from the dissolved mass and temperature:
   ```
   GasPres(idg) = trcs_solml_vr(idg, L, NY, NX) * RGasC * TKS_vr(L, NY, NX) / GasMassSolubility(idg)
   ```
   where `RGasC` is the gas constant (`EcoSimConst`) and `TKS_vr` is layer temperature (K).
3. Sum across all gas tracers:
   ```
   Soil_Gas_pressure_vr(L, NY, NX) = sum(GasPres(idg_beg..idg_end))
   ```
4. Fractional composition in ppmv (`× 1e6`):
   ```
   Soil_Gas_Frac_vr(idg, L, NY, NX) = GasPres(idg) / Soil_Gas_pressure_vr(L, NY, NX) * 1e6
   ```
   for `idg = idg_beg..idg_NH3`, with `idg_NH3B` added into `Soil_Gas_Frac_vr(idg_NH3, ...)`.
5. Layers with insufficient water or dissolved CO2 are zeroed: `Soil_Gas_pressure_vr = 0`, `Soil_Gas_Frac_vr(idg_beg:idg_NH3) = 0`.

### 3.3 Call site and consumption

`DiagSoilGasPressure` is called inside the hourly physics path when gas composition is needed as a mole fraction (for example, for the `CO2_gas_ppmv_vr`, `O2_gas_ppmv_vr`, `CH4_gas_ppmv_vr`, `N2O_gas_ppmv_vr`, `N2_gas_ppmv_vr`, `H2_gas_ppmv_vr`, `NH3_gas_ppmv_vr`, `Ar_gas_ppmv_vr` history fields listed in the bare-soil namelist at `examples/run_dir/bare_soil/BareSoil.namelist:37-39`). The outputs (`Soil_Gas_pressure_vr`, `Soil_Gas_Frac_vr`) live in `AqueChemDatatype` and are sampled by `HistDataType::hist_update` into the history buffers.

---

## 4. Ordering in the hour loop

```
hour1(I, J, ...)                                 ← Modelforc/Hour1Mod.F90:85
    ResetLndscapeAccumlators
    SetAtmsTracerConc
    ResetFluxArrays
    [SummarizeTracerMass if dosum]               ← via BalancesMod
    BegCheckBalances                             ← ModelDiags/BalancesMod.F90:37
    SetSurfaceProp4SedErosion
    per column:
        SetHourlyDiagnostics
        ...
        DiagWaterTBLDepz                         ← ModelDiags/HydrologyDiagMod.F90:23
        ...
        [DiagSoilGasPressure]                    ← ModelDiags/SoilDiagsMod.F90:31 (called where gas ppmv is needed)
    CanopyInterceptPrecip
    ApplyFertilizerAtNoon
PrepHourlyWeather(I, J, ...)                     ← Modelforc/WthrMod.F90:51
<physics + BGC>
EndCheckBalances(I, J, ...)                      ← ModelDiags/BalancesMod.F90:170
<history sampling and tape write>
```

---

## 5. Diagnostic-file outputs (side channels)

Plain ASCII reports written on budget failure:

| Unit | Written by | Content |
|---|---|---|
| 110 | `EndCheckBalances` water-budget branch | Per-column water budget dump with every term (`BalancesMod.F90:230-269`) |
| 111 | `EndCheckBalances` tracer-budget branch | Per-tracer mass balance dump (opened later in the module) |
| 115 | `SummarizeTracers` (disabled by `if(.false.)` guard, `BalancesMod.F90:490-497`) | Per-layer tracer dump for debugging |
| 18, 19, 20 | `readimod::readi` (`readimod.F90:77-79`) | `logfile1`, `logfile2`, `logfile3` — general model logs |

Units 110 and 111 are opened by the driver at model init; they contain only failure-time audits rather than a continuous stream.

---

## 6. Navigation

- Tape-based outputs that expose these diagnostics: `../io_and_forcing/history_and_restart.md` (see `HistDataType::hist_update` for the sampling step).
- Hour-loop structure and radiation/meteorology partitioning: `../io_and_forcing/forcing.md`.
- Reader side of the loop: `../io_and_forcing/input_readers.md`.
