---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/HydroTherm/`
**Last verified:** 2026-04-24
---

# HydroTherm Subsystem

The `HydroTherm/` tree holds EcoSIM's water and energy balance for the atmosphere-canopy-snow-litter-soil column. It diagnoses vertical and lateral fluxes of liquid water, water vapor, ice, and heat, partitions radiation and turbulent fluxes at the surface, tracks snowpack evolution, and handles soil freeze/thaw. Other subsystems read the water contents, soil temperatures, and fluxes it produces (they are pulled through `Ecosim_datatype` modules, not via a formal API layer).

## Source inventory (15 F90 files in 5 subdirectories)

```
HydroTherm/
  CanopyPhys/    1 file   canopy precipitation interception
  PhysData/      3 files  module-wide state arrays and physical parameters
  SnowPhys/      4 files  layered snowpack physics, transport, balance
  SoilPhys/      3 files  subsurface water/heat, hydraulic property curves, full watsub driver
  SurfPhys/      4 files  surface energy balance, litter exchange, runoff partitioning
```

| File | One-line purpose |
|---|---|
| `CanopyPhys/CanopyHydroMod.F90` | Canopy interception of rain and irrigation before throughfall reaches the ground (`CanopyInterceptPrecip`). Called from `Modelforc/Hour1Mod.F90:238`. |
| `PhysData/HydroThermData.F90` | Allocatable module-wide state arrays: iteration-level soil water/ice/air volumes, snowpack-overlying radiation and conductance terms, 3D water and heat flow arrays (`WaterFlow2Micpt_3D`, `HeatFlow2Soili_3D`, etc.), and the `HeatAdv_scal` scalar that turns advective heat transport on/off for fixed-water-level lake cases. |
| `PhysData/PhysPars.F90` | Compile-time physics parameters: minimum boundary-layer resistances (`RAM`, `RZ`), ice field capacity / wilting point (`FCI`, `WPI`), `MinSnowDepth=0.075 m`, water and air viscosity and diffusivity, and Rayleigh/Prandtl/Nusselt prefactors (`RYLXW`, `RYLXA`, `DNUSW`, `DNUSA`) used by the convective thermal-conductivity model. |
| `PhysData/SoilPhysParaMod.F90` | Soil matric potential `ComputePsiMCM` (Campbell-style log-log retention) and pond variant `ComputePSIPond`; `CalcSoilThermConductivity` (de Vries style with air/water convection); `get_Tfrez` (Clausius-Clapeyron freezing-point depression); `getMoistK` (100-bin moisture index); deep-layer property extension (`SetDeepSoil`). |
| `SnowPhys/SnowBalanceMod.F90` | Hourly snow-mass bookkeeping and safety nets after the fast-loop surface model finishes: `SnowMassUpdate`, `SnowpackDisapper`, `DealHighTempSnow`, `DealNegativeSnowMass`, `UpdateSnowLayerL`, `SnowpackLayering`. Called from `Balances/RedistMod.F90:126,144`. |
| `SnowPhys/SnowPhysData.F90` | Iteration-scratch snow arrays (temperatures, layer heat capacities, per-iteration phase-change and redistribution fluxes) allocated by `InitSnowPhysData`. |
| `SnowPhys/SnowPhysMod.F90` | The snow model core (~1900 lines): 5-layer initialization (`InitSnowLayers`, reference depths 0.05/0.15/0.30/0.60/1.00 m at line 66), snow-atmosphere energy balance (`SnowAtmosExchangeMM`), inner NPS-loop snowpack solver (`SolveSnowpackM`, `SnowPackIterationMM`), snow-litter and snow-soil exchange (`SnowSurLitterExch`, `SnowTopSoilExch`), snow redistribution (`SnowRedistributionM`), and boundary-layer resistance (`CalcSnowBNDResistance`). |
| `SnowPhys/SnowTransportMod.F90` | Solute and salt transport through the snowpack coupled to the water flow: `SoluteTransportThruSnow`, `SaltPercolThruSnow`, `ChemicalBySnowRedistribution`, `DiagSnowChemMass`. |
| `SoilPhys/SoilHydroParaMod.F90` | Soil hydraulic property setup at the start of each hour: `GetSoilHydraulicVars` (computes matric/osmotic/gravimetric/total potential per layer and hourly `HYCDMicP4RootUptake_vr`); `SoilHydroProperty` and `LitterHydroproperty` build the 100-bin K(theta) lookup via Green & Corey (1971) integration; `SetColdRunSoilStates` provides first-run defaults for field capacity, wilting point, and K_sat when the soil file leaves them unset; geotechnical helpers for root penetration (`estimate_friction_natural`, `estimate_root_stiffness`, `estimate_mineral_cohesion`). |
| `SoilPhys/WatsubDataMod.F90` | Allocate/destroy support arrays used only inside `watsub`: temporary 3D flow buffers, per-iteration soil-water and soil-heat copies. Entry `InitWatSubData` / `DestructWatSubData`. |
| `SoilPhys/WatsubMod.F90` | Full 3D water-and-heat driver (~2600 lines, 30 subroutines): Darcy micropore flow (`MicropXGridDarcyFlow`), gravity-driven macropore flow (`MacropXgridFLow`), vapor diffusion (`WaterVaporXgridFlow`), conduction + convection heat (`SolveXgridHeatConduction`), water-table discharge/recharge (`DischargeOverWaterTBL`, `RechargeFromExtWaterTBL`), tile drainage (`Config4TileDrainage`), explicit freeze-thaw (`FreezeThawIterateM`), and the main `watsub` subroutine (line 82) that iterates NPH times. Entries `InitWatsub` and `DestroyWatsub` are called from `Main/InitEcoSIM.F90:19` and `Ecosim_mods/InitAllocMod.F90:94`. |
| `SurfPhys/SurfPhysAPI.F90` | Empty stub module (13 lines). The duplicate stub at `f90src/APIs/SurfPhysAPI.F90` is also empty; no code exposes a formal API. Callers `use SurfPhysMod` directly. |
| `SurfPhys/SurfLitterPhysMod.F90` | Surface litter (residue) physics: `SurfLitREnergyBalanceM` (litter energy balance within the surface iteration), `CalcLitRThermConductivity` (Clapp-Hornberger-style weighted K with organic-matter term), `UpdateLitRPhys` (daily-summary updater called from `Balances/RedistMod.F90:1361`), and the overland runoff grid exchange `XGridsSurfRunoffM`. |
| `SurfPhys/SurfPhysData.F90` | Working scratch arrays shared across the surface-physics sequence (e.g., `ResistBndlSurf0`), allocated/destroyed via `InitSurfPhysData` / `DestructSurfPhysData` from inside `InitWatsub`. |
| `SurfPhys/SurfPhysMod.F90` | Surface physics core (~1900 lines, 28 subroutines): staging routine `StageSurfacePhysModel` (sets snow/litter/soil cover fractions, computes aerodynamic resistances, partitions precipitation and radiation), the inner-iteration driver `RunSurfacePhysModelM` (surface energy balance -> snow solver -> litter-soil water exchange -> infiltration/runoff partitioning -> canopy-air latent/sensible bookkeeping), and the hourly-end update `UpdateSurfaceAtM`. |

## Architecture

The subsystem is structured as a three-level time-step hierarchy, chosen because the snow surface and litter-soil interface need very short steps while the deeper soil column is solved on a longer step.

```
HOUR (driven by atmospheric forcing, Modelforc/Hour1Mod.F90)
  -> canopy interception (CanopyInterceptPrecip)
  -> SoilHydroParaMod::GetSoilHydraulicVars  (per-hour K(theta), psi, psi_gravity)

SOIL-HEAT ITERATION m = 1 .. NPH (dts_HeatWatTP = 1/NPH of an hour)
  watsub (SoilPhys/WatsubMod.F90:82)  OR  ATS coupler path
    -> StageSurfacePhysModel            (once per hour; SurfPhys/SurfPhysMod.F90:114)
    -> RunSurfacePhysModelM (each m)     (SurfPhys/SurfPhysMod.F90:1626)
         -> SurfaceEnergyModelM
              -> InitSurfModelM
              -> AtmLandSurfExchangeM  (energy budgets over snow, bare soil, litter)
                   -> SnowAtmosExchangeMM
                   -> SolveSnowpackM -> SnowPackIterationMM  (inner NPS subloop)
                   -> SoilSRFEnerbyBalanceM  (bare-soil Penman-style closure)
                   -> SurfLitREnergyBalanceM (litter Penman-style closure)
              -> UpdateSnowPack1M
         -> SurfLitrSoilWaterExchangeM
         -> InfilSRFRoffPartitionM
         -> XGridsSurfRunoffM         (overland flow between columns)
         -> AccumWaterVaporHeatFluxesM
    -> Subsurface3DInternalFlowM  (3D Darcy + gravity-drained macropore + vapor diffusion)
    -> XBoundaryFlowM             (lateral/base boundary fluxes, water table)
    -> Summarize3DFlowM           (per-cell net fluxes)
    -> UpdateSoilMoistTempM       (explicit update of VLWatMicP1, VLiceMicP1, TKSoil1)
         -> FreezeThawIterateM    (latent-heat-constrained phase change)
    -> UpdateSurfaceAtM / UpdateStateFluxAtM

DAILY CLOSURE (Balances/RedistMod.F90)
  -> SnowMassUpdate, SnowpackLayering
  -> UpdateLitRPhys
```

Inside the snow solver, `SolveSnowpackM` runs its own `D3000: DO MM = 1, NPS` loop (SnowPhys/SnowPhysMod.F90:565), and `SnowSurfLitRIteration` runs yet another `D4000: DO NN = 1, NPR` loop over the snow-litter vapor/heat exchange (SnowPhys/SnowPhysMod.F90:1475). `NPH`, `NPS`, `NPR` and their inverses `XNPS`, `XNPR` are provided by `EcoSIMSolverPar`; `dts_HeatWatTP` is the soil-heat iteration step, `dts_sno = dts_HeatWatTP*XNPS` the snow step, and `dts_wat` the (per-hour) water step used to convert fluxes between per-second and per-step units.

## Subsystem components

### Surface energy balance + snow

Implemented in `SurfPhys/SurfPhysMod.F90`, `SurfPhys/SurfLitterPhysMod.F90`, and the `SnowPhys/` directory. Handles shortwave/longwave partitioning between snow, bare soil, and litter; aerodynamic resistances with Richardson-number stability correction; Penman-style energy closures for `HeatSensAir2Grnd`, `LatentHeatEvapAir2Grnd`, and storage `HeatFluxAir2Soi`; five-layer snowpack with dry-snow-equivalent, liquid, and ice partitions; albedo weighted by dry/ice/water volumes; vapor exchange between snow, litter, and the top soil layer.

See **[surface_energy_balance_and_snow.md](surface_energy_balance_and_snow.md)** for equations and file:line citations.

### Subsurface water and heat

Implemented in `SoilPhys/WatsubMod.F90`, `SoilPhys/SoilHydroParaMod.F90`, and `PhysData/SoilPhysParaMod.F90`. Handles Darcy flow in micropores using harmonic-mean K, gravity-driven macropore flow (Poiseuille-derived K from macropore radius/number), binary water-vapor diffusion, 3D conductive + convective heat transport with de Vries thermal conductivity, Clausius-Clapeyron freezing-point depression for unfrozen water in frozen soil, explicit phase-change iteration with per-layer latent-heat budget, and water-table discharge/recharge with slope-aware gravity adjustment.

See **[subsurface_water_and_heat.md](subsurface_water_and_heat.md)** for equations and file:line citations.

## Coupling with other EcoSIM subsystems

HydroTherm is invoked once per model hour; the timings and module dependencies below were verified by grep over the full `f90src/` tree.

- **Entry / driver.** In the ATS-coupled build the driver is `ATSUtils/ATSEcoSIMAdvanceMod.F90:303,322,336` (calls `StageSurfacePhysModel`, `RunSurfacePhysModelM`, then `UpdateSurfaceAtM`). The standalone `watsub(I,J,NHW,NHE,NVN,NVS)` driver in `SoilPhys/WatsubMod.F90:82` bundles the same sequence plus the full 3D flow loop but is not called by any file under commit `2dea74d9`; the ATS coupler is the active path, and the subsurface 3D flow is invoked separately. Note that the top-level `f90src/APIs/SurfPhysAPI.F90` and the `HydroTherm/SurfPhys/SurfPhysAPI.F90` are empty stubs, so callers `use SurfPhysMod` directly.
- **Precipitation and atmospheric forcing.** `Modelforc/Hour1Mod.F90:238` calls `CanopyInterceptPrecip` to reduce precipitation reaching the ground. Radiation, air temperature, humidity, wind, and precipitation enter through `ClimForcDataType` (`TairK_col`, `VPA_col`, `WindSpeedAtm_col`, `RadSWGrnd_col`, `LWRadSky_col`, `PrecRainAndIrrig_col`). These modules are the responsibility of `f90src/Modelforc/`.
- **Plant transpiration and root water.** `SoilHydroParaMod::GetSoilHydraulicVars` computes `HYCDMicP4RootUptake_vr` used by the root solver in `Plant_bgc/NutUptakeMod.F90`. Plant-to-soil return flows `TWaterPlantRoot2SoilPrev_vr` and `THeatPlantRoot2SoilPrev_vr` are consumed in `WatsubMod.F90:15` (`use PlantDataRateType`). Canopy air vapor-pressure and temperature `VPQ_col`, `TKQ_col` are maintained here (`SurfPhysMod::SetCanopyProperty`, line 275-276) and are the state on which canopy energy balance and stomatal conductance are built.
- **Geochemistry.** Soil matric and osmotic potentials, pore volumes, and per-layer temperatures (`PSISoilMatricP_vr`, `PSISoilOsmotic_vr`, `VLWatMicP_vr`, `TKS_vr`) are inputs to `f90src/Geochem/`; solute advection comes from water fluxes in `WaterFlow2MicPM_3D` (set here and consumed in `Transport/Nonsalt/TranspNoSaltSlowMod.F90:2179,2183`).
- **Microbial biogeochemistry.** Water/air filled porosity (`FracSoiPAsWat_vr`, `FracAirFilledSoilPore_vr`) and soil temperature drive microbial kinetics in `f90src/Microbial_bgc/`; the comment blocks in `Microbial_bgc/Box_Micmodel/MicAutoCplxFGMod.F90:713` and `MicBGCFGMod.F90:3533` trace these inputs back to watsub.
- **Balances / day-end closure.** `Balances/RedistMod.F90:126,144,1361` calls `SnowMassUpdate`, `SnowpackLayering`, and `UpdateLitRPhys` at the end of the day to close the mass and energy budgets and adjust snow layering.
- **Warming experiments.** `WatsubMod.F90:14,114-118` checks `check_warming_dates` and applies `apply_soil_cable_warming` when soil cable warming dates are active. Handled in `EcosysWarmingMod` (`f90src/Modelforc/`, not in HydroTherm).

## Navigation

- [surface_energy_balance_and_snow.md](surface_energy_balance_and_snow.md) - surface radiation, sensible/latent/ground heat partitioning, litter, snowpack.
- [subsurface_water_and_heat.md](subsurface_water_and_heat.md) - soil Richards flow, macropores, vapor, thermal conductivity, freeze/thaw, water table.
