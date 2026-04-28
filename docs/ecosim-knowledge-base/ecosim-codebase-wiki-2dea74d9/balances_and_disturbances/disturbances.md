---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/Disturbances/`
**Last verified:** 2026-04-24
---

# Disturbances subsystem (`Disturbances/`)

Six F90 modules implement discrete or continuous ecosystem disturbances. Each encapsulates the decision logic (trigger, depth, magnitude) and the state-variable modification for its particular disturbance type. Continuous disturbances (erosion, soil warming) run at sub-hourly or hourly cadence. Event disturbances (fertilizer, tillage, fire, grazing) trigger on time-of-day or management-file conditions.

## Source files

| File | Key public subroutines | Disturbance type |
|------|------------------------|------------------|
| `EcosysWarmingMod.F90` | `config_soil_warming` (line 167), `InitSoilWarming` (line 55), `destructSoilWarming` (line 69), `check_warming_dates` (line 84), `get_warming_fname`, `apply_soil_cable_warming` (line 508), `apply_IR_warming` (line 545), `apply_OTC_warming` (line 473), `is_warming_layerL` | Soil warming (buried cable), infrared lamp heating, open-top chamber (OTC) |
| `ErosionMod.F90` | `erosion` (line 62), `SedimentDetachmentM` (line 93), `SedimentTransportM` (line 258), `OverLandFlowSedTransp` (line 182), `LateralXGridSedmentFlux` (line 399), `XBoundErosionFlux` (line 744), `InitErosion` (line 47), `DestructErosion` (line 973), `XBoundSedTranspM` (line 300) | Surface sediment detachment and overland transport |
| `FertilizerMod.F90` | `ApplyFertilizerAtNoon` (line 34), `ApplyMineralFertilizer` (line 416), `ApplyManure` (line 120), `ApplyUreaNitrifierInhibitor` (line 66) | Mineral and organic fertilizer, manure, urea, nitrification inhibitors |
| `FireMod.F90` | `config_fire` (line 24), `check_fire` (line 100) | Fire (configuration and annual activation; actual combustion runs in `SoilDisturbMod`) |
| `PlantDisturbMod.F90` | `PrepLandscapeGrazing` (line 35) | Landscape-level staging of grazing and herbivory pressure (actual biomass removal is in `Plant_bgc/PlantDisturbByGrazingMod.F90`) |
| `SoilDisturbMod.F90` | `SOMRemovalByDisturbance` (line 39) | Fire combustion, litter removal, and other soil-profile SOM removal (`iSoilDisturbType_col` codes 1-24) |

## Disturbance types and triggers

### Fertilizer (mineral, manure, urea inhibitors)

`ApplyFertilizerAtNoon` (`FertilizerMod.F90:34-63`) is called every hour from `f90src/Modelforc/Hour1Mod.F90:247`. It enforces a single-trigger condition: `J .EQ. INT(SolarNoonHour_col(NY,NX))` (line 46), so fertilizer is applied once per day at solar noon.

Three sub-routines run in sequence when the trigger fires:

1. `ApplyMineralFertilizer` (line 416): applies N (NH4, NH3, NO3, urea -- all in both broadcast and banded form), P (Ca(H2PO4)2 broadcast and banded, apatite), Ca (lime, gypsum) according to the `FERT(ifert_*, I, NY, NX)` input array. Fertilizer types and IDs are in `Modelconfig/ElmIDMod.F90:53-69` (`ifert_N_nh4` through `ifert_Ca_gypsum`).
2. `ApplyManure` (line 120): applies plant residues and manure C/N/P to layer `LFDPTH`. Supports residue classes `iPlantRes_maize`, `iPlantRes_wheat`, `iPlantRes_soybean`, `iPlantRes_oldStraw`, `iPlantRes_Straw`, `iPlantRes_compost`, `iPlantRes_GreeManure`, `iPlantRes_simple` (`ElmIDMod.F90:79-86`). Partitions residue carbon across protein, CH2O/carbohydrate, cellulose, lignin fractions (`CFOSC_vr`) using literature-based defaults per residue type (e.g., maize: protein 0.080, carbohydrate 0.245, cellulose 0.613, lignin 0.062 at `FertilizerMod.F90:172-176`).
3. `ApplyUreaNitrifierInhibitor` (line 66): if urea fertilizer is present and `IYTYP(iamendtyp_fert) == 1` or `3`, activates urea hydrolysis inhibitor `ZNHUI_vr(LFDPTH)=1.0`; if `IYTYP == 3` or `4`, activates nitrification inhibitor `ZNFNI_vr(LFDPTH)=1.0`.

State variables modified: `trcs_solml_vr(ids_NH4,...)`, `trcs_solml_vr(ids_NO3,...)`, `trcs_solml_vr(ids_H1PO4,...)` and banded counterparts, urea pool, `CSoilOrgM_vr`, `CFOSC_vr`, `ZNHU0/I_vr`, `ZNFN0/I_vr`.

Management inputs come from the fertilizer input stream `FERT` and the amendment type array `IYTYP`, both read in `f90src/IOutils/` (see `io_and_forcing/`).

### Fire

Fire has a two-stage implementation in the Disturbances tree plus an execution stage in `SoilDisturbMod`:

- **Stage 1: Configuration** (`FireMod.F90:24-98`). `config_fire` parses a fire-event specification string of the form `year1/file1;year2/file2;...` into `fire_years(:)` and `fire_files(:)`. Requires `soil_mgmt_in` to be defined (`FireMod.F90:91-93`). Setting `use_fire=.true.` at line 89.

- **Stage 2: Annual activation** (`f90src/IOutils/readsmod.F90:235-239`). Each simulation year, if `use_fire` and `check_fire(yearc, fire_event_entry)` returns true, `ReadFire` is invoked to load that year's fire specification (which sets `iSoilDisturbType_col(I,NY,NX) = itill_fire = 22`, see `ElmIDMod.F90:170`).

- **Stage 3: Execution** (`SoilDisturbMod.F90:39-393`). `SOMRemovalByDisturbance` is called once per hour from `f90src/APIs/MicBGCAPI.F90:128`. It triggers when `J == INT(SolarNoonHour_col)` AND `iSoilDisturbType_col` equals `itill_rmlitr` (21) or `itill_fire` (22). For fire:
  1. Set `iResetSoilProf_col = itrue`.
  2. Sweep downward from `L=0` (litter) to find burning depth `NLL`, stopping at the first layer failing combustion criteria (moisture `THETW_vr > VolMaxSoilMoist4Fire` or too little organic matter `CSoilOrgM_vr(ielmc) <= FORGC`) (`SoilDisturbMod.F90:79-93`).
  3. For layers `L=0..NLL`, remove organic C, N, P using per-disturbance combustion factor `DCORPC` scaled by `DepzCorp_col(I,NY,NX)` from the management file (`SoilDisturbMod.F90:104-108`).
  4. Emit combustion products using emission factors `EFIRE(1:2, iSoilDisturbType_col)` -- separate N and P factors per disturbance code (`SoilDisturbMod.F90:131-264`). Distinguishes solid SOM, DOM, microbial biomass, and litter.

### Soil warming (cable / IR / OTC)

`EcosysWarmingMod.F90` supports three warming modalities plus combined experiments:

- Type 1: `ir_heating` -- overhead infrared lamp. Power specified in `W m-2`; converted internally to `MJ m-2 h-1` (`set_IR_heating`, line 259). Applied in `apply_IR_warming` (line 545).
- Type 2: `cable_heating` -- buried heating cable with target temperature delta `dT` below surface down to `Depth`. Applied in `apply_soil_cable_warming` (line 508); requires a reference soil-temperature history file (`hist_ctrl`) set with `fname_warming_Tref`.
- Type 3: `open_top_chamber` -- OTC modifies wind speed, longwave emissivity, and shortwave transmissivity. Applied in `apply_OTC_warming` (line 473).
- Combined: `21 = IR + cable`, `23 = OTC + cable` (`EcosysWarmingMod.F90:213, 219`).

Configuration string format (line 10 comment in source):
```
warming_exp = 'loc[NY,NX];type[Cable_heating];dT[4K];Depth[1m];hist_ctrl[Blodget.ctrl.ecosim.h1.xxxx-01-00-00000.nc];beg_time[2014/01/01];end_time[2018/12/31]'
```

Time-window and season gating comes via `warm_yearb/yeare`, `warm_doyb/doye`, `seas_doyb/doye`, `ihtime` (0=all day, 1=day, 2=night), `igrowth` (0=whole year, 1=growing season only). Entry points are called from `f90src/Modelforc/WthrMod.F90:105-106` (OTC, IR) and `f90src/HydroTherm/SoilPhys/WatsubMod.F90:117` (cable).

State variables modified: `TKS_vr(L,NY,NX)` (soil temperature), canopy energy balance (OTC), radiation-balance forcing `AtmGasCgperm3_col` only indirectly through `WATSUB`.

### Erosion

`erosion` (`ErosionMod.F90:62-90`) is called every hour from `drivers/ecosim/EcoSIMAPI.F90:106`. Gating:

```
IF(iErosionMode == ieros_frzthaweros OR iErosionMode == ieros_frzthawsomeros) ...
```

where `iErosionMode` is set per run via namelist. The four modes (`Modelconfig/ElmIDMod.F90:18-22`): `ieros_noaction=-1`, `ieros_frzthawelv=0`, `ieros_frzthaweros=1`, `ieros_frzthawsom=2`, `ieros_frzthawsomeros=3`. Modes 1 and 3 enable the erosion block; modes 0 and 2 only track freeze-thaw elevation changes.

When enabled, the sequence is (`ErosionMod.F90:75-89`):

1. Loop `M=1..NPH` inside the hour:
   - `SedimentDetachmentM` (line 93): rainfall kinetic-energy detachment (`DETW = SoilDetachability4Erosion1 * (1 + 2*theta_W/V_mic)`) plus overland flow detachment. Includes pond-water attenuation.
   - `SedimentTransportM` (line 258): `XBoundSedTranspM` at domain edges, then within-domain transport.
2. `LateralXGridSedmentFlux` (line 399): the non-boundary grid-to-grid sediment fluxes.
3. `XBoundErosionFlux` (line 744): landscape-edge sediment losses (skipped if `column_mode=.true.`).

State variables modified: `SED_col`, `TSandErosed_col`, `TSiltErosed_col`, `TCLAYErosed_col`, `TNH4Erosed_molN_col`, `TNO3Erosed_molN_col`, `TPO4Erosed_molP_col`, `trcx_TER_col`, `trcp_TER_col`, and microbial/SOM erosion arrays (`TOMEERhetr_col`, `TORMER_col`, `TOHMER_col`, `TOSMER_col`). The mass moved is then redistributed by `RedistMod::SoilErosion`.

Energy for detachment (`EnergyImpact4Erosion_colM`) is computed in HydroTherm. Erosion-induced layer-edge changes are applied in `SoilLayerDynMod::ErosionSoilEdgeChange`.

### Grazing and herbivory (preparation stage only)

`PrepLandscapeGrazing` (`PlantDisturbMod.F90:35-76`) runs once per hour from `f90src/APIs/PlantMod.F90:47`, before the plant biogeochemistry step. For each PFT whose `iHarvstType_pft(NZ,I,NY,NX)` is either `iharvtyp_grazing=4` or `iharvtyp_herbivo=6` (`ElmIDMod.F90:112-114`), it aggregates total shoot biomass across all grid cells sharing the same landscape-grazing section `LSG_pft(NZ,NY,NX)` and writes the average into `AvgCanopyBiomC2Graze_pft(NZ,NY,NX)`.

The actual biomass removal and transfer to microbial substrate is NOT in this file. It lives in `f90src/Plant_bgc/PlantDisturbByGrazingMod.F90` and `PlantDisturbsMod.F90`, both of which consume `AvgCanopyBiomC2Graze_pft` and `iHarvstType_pft` to compute per-PFT uptake rates proportional to biomass (`PlantDisturbByGrazingMod.F90:233`). Fire as a harvest type (`iharvtyp_fire=5`) is also handled there -- distinct from soil-profile fire (`itill_fire=22`) which combusts SOM via `SoilDisturbMod`.

### Tillage and litter removal (soil-SOM side)

`SOMRemovalByDisturbance` (`SoilDisturbMod.F90:39-393`) covers both fire (`itill_fire=22`) and litter removal (`itill_rmlitr=21`). Despite living in `Disturbances/`, tillage-style mixing (`iSoilDisturbType_col <= 20`) is NOT handled here -- it is handled in `TillageMixMod::ApplyTillageMixing` (in `Balances/`). `SOMRemovalByDisturbance` only runs at solar noon AND when `iSoilDisturbType_col(I,NY,NX)` is 21 or 22 (`SoilDisturbMod.F90:71`). For litter removal, it strips the `L=0` litter layer only (`NLL=0`); for fire it burns downward through combustion-eligible layers.

## Coupling with management input streams

Fertilizer, tillage, fire, and warming all read from forcing streams maintained by `f90src/IOutils/` (documented in `io_and_forcing/`). A high-level pointer:

| Input | Stream | Read by |
|-------|--------|---------|
| Fertilizer rates (`FERT`, `IYTYP`) | Per-day fertilizer input file | `ReadManagementFiles` in `readsmod.F90:242` |
| Tillage depth (`DepzCorp_col`), type (`iSoilDisturbType_col`) | Per-day tillage input file | `ReadManagementFiles` |
| Fire year/file pairs | Namelist string to `config_fire` | Parsed at startup |
| Fire-year specifics (depth, combustion factors) | Fire spec file for that year | `ReadFire` (called from `readsmod.F90:237`) |
| Warming experiment config | Namelist string to `config_soil_warming` | Parsed at startup |
| Warming reference soil-T history | NetCDF file `fname_warming_Tref` | `EcosysWarmingMod::get_warming_fname` |

The soil-management namelist is controlled by `soil_mgmt_in` in the EcoSIM control namelist. Setting `soil_mgmt_in='NO'` disables all daily management-file reads and is incompatible with `use_fire=.true.` (`FireMod.F90:91-93` enforces that combination).

## Summary of state modifications

| Disturbance | `TKS_vr` | `trcs_solml_vr` | `SOM*` | `VLWatMicP*` | Sediment | Canopy |
|-------------|:------:|:-----:|:-----:|:-----:|:---:|:----:|
| Fertilizer (mineral) |   | x (NH4, NO3, H2PO4) | (inhibitor activity) |   |   |   |
| Fertilizer (manure) |   | x (via residues) | x (CFOSC, OM pools) |   |   |   |
| Fire (SOMRemoval) |   | x (mineralization products) | x (combustion) |   |   |   |
| Litter removal |   |   | x (L=0 only) |   |   |   |
| Tillage mixing (Balances) |   | x (mixed) | x (mixed) | x (mixed) |   |   |
| Soil warming, cable | x |   |   |   |   |   |
| Soil warming, IR (forcing-side) | indirect |   |   |   |   | x (longwave) |
| Soil warming, OTC (forcing-side) | indirect |   |   |   |   | x (wind, SW, LW) |
| Erosion | (via layer dynamics) | x (eroded) | x (eroded) |   | x |   |
| Grazing/herbivory (prep only) |   |   |   |   |   | (staging, no modification) |

See [`mass_balance.md`](mass_balance.md) for how these modifications are reconciled with the end-of-hour conservation checks.
