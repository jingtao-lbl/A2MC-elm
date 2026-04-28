---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/HydroTherm/SurfPhys/`, `f90src/HydroTherm/SnowPhys/`, `f90src/HydroTherm/CanopyPhys/`
**Last verified:** 2026-04-24
---

# Surface Energy Balance and Snow

This document covers the surface-level components of the HydroTherm subsystem: canopy interception, radiation partitioning, aerodynamic resistances, the Penman-style energy closure over bare soil / litter / snow, and the 5-layer snowpack. See [index.md](index.md) for subsystem context and [subsurface_water_and_heat.md](subsurface_water_and_heat.md) for the soil column.

Atmospheric forcing variables used below (`TairK_col`, `VPA_col`, `WindSpeedAtm_col`, `PrecRainAndIrrig_col`, `RadSWGrnd_col`, `LWRadSky_col`, `VPQ_col`, `TKQ_col`) enter via `ClimForcDataType` from the `Modelforc/` subsystem, not from HydroTherm. Only the use of those fields is documented here.

## Canopy precipitation interception

`CanopyInterceptPrecip` (`f90src/HydroTherm/CanopyPhys/CanopyHydroMod.F90:23-56`) is the only canopy-physics routine in HydroTherm and is called once per hour from `Modelforc/Hour1Mod.F90:238`. For each plant functional type it computes a maximum retention capacity

```
CanopyWatHeldCap = FoliarWatRetcap(profile) * (CanopyLeafArea_pft + CanopyStemSurfArea_pft)
```

and intercepts the minimum of throughfall-weighted precipitation and the remaining capacity (CanopyPhys/CanopyHydroMod.F90:46-50). The retention capacity array `FoliarWatRetcap(0:3) = (/5.0e-4, 2.5e-4, 2.5e-4, 2.5e-4/)` (m3 H2O per m2 surface, CanopyPhys/CanopyHydroMod.F90:18) is keyed on `iPlantRootProfile_pft`; snowfall is not intercepted (comment at line 43: "Warning: No snofall intercepation is considered at the moment"). The un-intercepted fraction becomes `RainPrecThrufall_col` (line 54), which is then partitioned between snow/rain/ice on the snowpack and throughfall to the litter/ground in `SurfPhysMod::PartitionPrecip` (line 1376 of SurfPhysMod, not re-detailed here).

## Surface staging: fractions, resistances, radiation

`StageSurfacePhysModel` (`f90src/HydroTherm/SurfPhys/SurfPhysMod.F90:114-173`) is called once per soil-heat iteration (or once per hour by the ATS coupler at `ATSUtils/ATSEcoSIMAdvanceMod.F90:303`) and lays out the state every other sub-iteration depends on. Key steps:

1. `StageSnowModel` - initializes snow diagnostic arrays (SnowPhys/SnowPhysMod.F90:1631).
2. `CopySurfaceVars` - copies soil surface state into the iteration-scratch `*_vr` arrays and computes surface organic-matter volume `m3OM_col` and litter volumetric heat capacity `VHeatCapacity1_vr(0,...)` (SurfPhys/SurfPhysMod.F90:198: `cpo*m3OM_col + cpw*VLWatMicP_vr + cpi*VLiceMicP_vr`).
3. `PartionSurfaceFraction` (SurfPhysMod:241-257) sets the snow / snow-free partition:

   ```
   FracSurfAsSnow_col = min(1, sqrt(SnowDepth_col / MinSnowDepth))          (MinSnowDepth = 0.075 m, PhysPars.F90:31)
   FracSurfSnoFree_col = 1 - FracSurfAsSnow_col
   ```

   and then calls `PartLitSoilFractionM` (SurfLitterPhysMod:43-65) which uses the surface organic-matter mass (an exponential attenuation, `exp(-0.8e-2 * SoilOrgM_vr(ielmc,0,...)`) and the mobile-water ratio to set `FracSurfByLitR_col` and `FracSurfBareSoil_col`.
4. `PartitionPrecip` distributes rainfall, snowfall, and irrigation onto snow, rain-on-snow, litter, and top soil layer.
5. `SurfaceResistances` - aerodynamic resistances (next subsection).
6. `Radiation2Surface` - radiation partitioning (subsection after that).
7. `SetCanopyProperty` (SurfPhysMod:260-285) updates canopy-air state used by both the ground and the plant canopy:

   ```
   VPQ_col = VPA_col - TLEX_col / (EvapLHTC * AREA)                           (line 275)
   TKQ_col = TairK_col - TSHX_col / (SpecHeatCapAir * AREA)                   (line 276; SpecHeatCapAir = 1.25e-3 MJ/m3/K)
   ```

   A Richardson-number stability multiplier is applied to `RawTAtm2CanopySinkZ_col` (line 281), clamped to within 0.8x-1.2x its isothermal value and bounded below by `RAM = 1.39e-3 h/m` (PhysPars.F90:32).

### Aerodynamic resistances

`SurfaceResistances` (`f90src/HydroTherm/SurfPhys/SurfPhysMod.F90:355-443`) computes the ground-level aerodynamic resistances. If a plant canopy is present, the canopy-to-ground resistance follows Choudhury and Monteith (1988) using an attenuation coefficient `ALFZ = 2*(1 - FracSWRad2Grnd_col)`:

```
WindSpeedGrnd = WindSpeedAtm_col * exp(-ALFZ)                                 (SurfPhysMod.F90:383)
RawIsoTSurf2SinkZ_col = CanopyHeight*exp(ALFZ) / (ALFZ/RawIsoTSurf2CanopyHScal)
                        * [exp(-ALFZ*z0soil/h) - exp(-ALFZ*(d+z0)/h)]        (line 385-387)
```

clamped between `RACX = 0.0139 h/m` (canopy-boundary minimum, SurfPhysMod.F90:66) and 0.

Litter vapor-diffusion resistance is derived from a temperature-dependent diffusivity:

```
TFACR                      = TEFGASDIF(TKS_vr(0,...))
VaporDiffusivityLitR_col   = TFACR * 7.70e-2                                  (SurfPhysMod.F90:416-417)
VapDiffusResistanceLitR    = DLYRR_COL / VaporDiffusivityLitR_col             (line 418)
ResistanceLitRLay          = RawIsoTSoil2ATM_col + VapDiffusResistanceLitR/(theta_air^2 * POROQ/POROS)  (line 425-426)
```

Area-scaled conductances for latent and sensible heat fluxes are built from `PAREX = AREA*dts_HeatWatTP` (m2 h) and `PARSX = 1.25e-3 * AREA*dts_HeatWatTP` (MJ h / m / K) and split between snow, soil, and litter fractions (SurfPhysMod.F90:427-436). The snowpack-averaged boundary resistance is added through `CalcSnowBNDResistance` (SnowPhys/SnowPhysMod.F90:1386-1420): each snow layer contributes `RASL = (layer_thickness / H2OVapDifsc) / FracAsAirSno^2`; the sum is added to the litter resistance before conductance `PARR_col` is finalized (SurfPhysMod.F90:441).

### Radiation partitioning

`Radiation2Surface` (`f90src/HydroTherm/SurfPhys/SurfPhysMod.F90:288-329`) partitions the ground-level shortwave and longwave radiation between snow, bare soil, and litter weighted by `FracSurfAsSnow_col`, `FracSurfSnoFree_col`, `FracSurfBareSoil_col`, and `FracSurfByLitR_col`, with the snow and litter fractions further scaled by `XNPS = 1/NPS` and `XNPR = 1/NPR` so that each inner iteration gets the correct time-slice of incident radiation. Longwave emission is linearized via the Stefan-Boltzmann coefficient `stefboltz_const`:

```
RadSW2Sno_col = RadSWGrnd_col * dts_HeatWatTP * FracSurfAsSnow_col * XNPS                  (line 315)
LWRad2Snow_col = (LWRadSky_col*FracSWRad2Grnd_col + LWRadCanGPrev_col) * dts_HeatWatTP
                 * FracSurfAsSnow_col * XNPS                                                (line 317-318)
LWEmscefSnow_col = SnowEmisivity * stefboltz_const * AREA * FracSurfAsSnow_col
                   * dts_HeatWatTP * EMS_Modify_Scalar_col                                  (line 322-323)
```

Emissivities are compile-time constants `SoilEmisivity = SnowEmisivity = SurfLitREmisivity = 0.97` (`SurfPhysMod.F90:63-65`). `LiterSoilRadiationM` (SurfPhysMod.F90:332-352) is the sub-iteration variant that uses `XNPR` for litter and no XNPS scaling (since snow is already handled inside its own loop).

### Ground albedo

Ground albedo is dynamic and water-state-dependent:

```
AlbedoGrnd = (SoilAlbedo_col*VLSoilMicPMass_vr + 0.06*VLWatGrnd + 0.30*VLIceGrnd)
             / (VLSoilMicPMass_vr + VLWatGrnd + VLIceGrnd)
```

(`SurfPhysMod.F90:526-527`), with `VLWatGrnd` and `VLIceGrnd` summed over micropores and macropores of the top soil layer (line 519-520). When both water and ice are absent the bare soil albedo `SoilAlbedo_col` is used.

Snow albedo is computed inside `SnowAtmosExchangeMM` (`f90src/HydroTherm/SnowPhys/SnowPhysMod.F90:817-822`): if the runtime flag `mod_snow_albedo` is true the externally supplied `SnowAlbedo_col` is used; otherwise it is reconstructed each iteration from the dry-snow / ice / water fractions:

```
SnowAlbedo = (0.85*(VLDrySnoWE0M + SnoFall) + 0.30*(VLIceSnow0M + IceFall)
              + 0.06*(VLWatSnow0M + RainFall)) / SnowVolume                   (line 820-821)
```

The source comment at line 525 of SurfPhysMod ("ice albedo seems too low") flags the soil-surface ice albedo 0.30 as a known calibration concern.

## Penman-style energy closure over bare soil

`SoilSRFEnerbyBalanceM` (`f90src/HydroTherm/SurfPhys/SurfPhysMod.F90:447-616`) solves the bare-soil surface energy balance at the start of each sub-iteration. Its equations are worth quoting in full because they are the calibration target for surface fluxes.

**1. Soil matric + osmotic water potential at the surface**:

```
PSISV1 = PSISM1_vr(NUM_col) + PSISoilOsmotic_vr(NUM_col)                      (line 504-506)
```

computed by `SoilPhysParaMod::CalcSoilWatPotential`.

**2. Net radiation on the ground**:

```
RadSWbySoil  = (1 - AlbedoGrnd) * RadSW2Soil_col
tRadIncid    = RadSWbySoil + LWRad2Soil_col
LWRadGrnd    = LWEmscefSoil_col * TKSoil1_vr(NUM_col)^4
Radnet2Grnd  = tRadIncid - LWRadGrnd                                          (line 535-538)
```

**3. Richardson-number-corrected aerodynamic resistance** `RAa`:

```
RI           = RichardsonNumber(RIB_col, TKQ_col, TKSoil1_vr(NUM_col))        (line 558)
ResistBndlSurf_col clamped within 0.8x-1.2x of isothermal and bounded above
                    by ResistanceLitRLay / (1 - 10*RI)                         (line 560-565)
RAa          = ResistAreodynOverLitr_col + ResistBndlSurf_col                  (line 566)
```

**4. Latent and sensible heat fluxes** (Penman-form with Bishop-style separation of latent and convective-heat components):

```
CdSoiEvap    = AScaledCdWOverSoil_col / (RAa + RZ)         (RZ = 0.0139, PhysPars.F90:33)
CdSoiHSens   = AScaledCdHOverSoil_col / RAa                                   (line 581-582)
VaporSoi1    = vapsat(TKX1) * exp(18 * PSISV1 / (RGASC * TKX1))               (line 584)
VapXAir2TopLay = max(CdSoiEvap * (VPQ_col - VaporSoi1), -max(TopLayWatVol*dts_wat))  (line 588)
LatentHeatEvapAir2Grnd = VapXAir2TopLay * EvapLHTC                            (line 592)
HeatSensAir2Grnd       = CdSoiHSens * (TKQ_col - TKSoil1_vr(NUM_col))         (line 611)
HeatSensVapAir2Grnd = if(evap) cpw*TKsoi*VapXAir2TopLay * HeatAdv_scal
                     else     cpw*TKair*VapXAir2TopLay * HeatAdv_scal          (line 593-599)
tHeatAir2Grnd  = Radnet2Grnd + LatentHeatEvapAir2Grnd + HeatSensAir2Grnd      (line 612)
HeatFluxAir2Soi = tHeatAir2Grnd + HeatSensVapAir2Grnd                         (line 613)
```

`HeatFluxAir2Soi` is the storage/ground heat flux that becomes the upper boundary condition for `UpdateSoilMoistTempM` in `WatsubMod.F90:1252`. `HeatAdv_scal` is set to 0 when `fixWaterLevel` is true (WatsubMod.F90:112), disabling advective heat transport for fixed-water-level lake cases.

The soil surface vapor pressure in step 4 uses the thermodynamic equilibrium expression `p_sat*exp(M_w * psi / (RT))` (Kelvin equation), which follows Philip and de Vries (1957) and the treatment in earlier ecosys versions.

## Litter energy balance

`SurfLitREnergyBalanceM` (`f90src/HydroTherm/SurfPhys/SurfLitterPhysMod.F90:68-185`) solves a parallel Penman-style balance over the litter layer using the litter thermal conductivity from `CalcLitRThermConductivity` (SurfLitterPhysMod.F90:186-215). The weighted thermal conductivity has the Clapp-Hornberger / de Vries structure with dedicated weighting factors for organic, water, ice, and air components:

```
TCNDR = (0.779*THETRR*9.050e-4 + 0.622*theta_wat*TCNDW0
         + 0.380*theta_ice*7.844e-3 + WTHET0*theta_air*TCNDA0)
        / (0.779*THETRR + 0.622*theta_wat + 0.380*theta_ice + WTHET0*theta_air)
```

(`SurfLitterPhysMod.F90:212-214`) where `TCNDW0` and `TCNDA0` are temperature-dependent water and air thermal conductivities derived from Nusselt-number formulas (de Vries 1963-style convective correction; see PhysPars.F90:44-45 for the `DNUSW`, `DNUSA` prefactors), and `WTHET0 = 1.467 - 0.467*FracSoilAsAirt` (line 211). The 0.779 / 0.622 / 0.380 weights are characteristic shape factors for elongated organic grains, water films, and ice crystals.

The iterated litter inner loop (`SurfLitterIterationM`, line 219) uses `NPR` sub-steps, each of duration `dts_litrvapht = dt_SnoHeat/NPR`, to couple vapor, heat conduction, and liquid-water exchange with the snow above and the soil below.

## Snowpack initialization

`InitSnowLayers` (`f90src/HydroTherm/SnowPhys/SnowPhysMod.F90:56-149`) sets up up to 5 snow layers with reference cumulative depths

```
cumSnowDepzRef_col(1:5) = (/ 0.05, 0.15, 0.30, 0.60, 1.00 /)  [m]             (SnowPhysMod.F90:66)
```

so that layer thicknesses are 0.05 / 0.10 / 0.15 / 0.30 / 0.40 m when the snowpack is at or above 1 m. New-snow density `NewSnowDens_col` is initialized at 0.10 Mg/m3 (line 89). For each layer L the snow water equivalent `VLDrySnoWE_snvr`, liquid water `VLWatSnow_snvr`, and ice `VLIceSnow_snvr` are allocated; layer temperature is initialized to `min(Tref, TairKClimMean_col)` (line 125). Heat capacities use the specific heats `cps` (snow/ice), `cpw` (water), `cpi` (bulk ice) from `EcoSimConst`:

```
VLHeatCapSnow = cps*VLDrySnoWE + cpw*VLWatSnow + cpi*VLIceSnow                (SnowPhysMod.F90:127)
```

A minimum column-heat-capacity threshold `VLHeatCapSnowMin_col = VLHeatCapSnoMin * AREA` is precomputed (line 147) and is used downstream to decide whether snow-related fluxes should be computed for a given iteration.

## Snow energy balance and layer solver

`SnowAtmosExchangeMM` (`f90src/HydroTherm/SnowPhys/SnowPhysMod.F90:782-926`) is the snowpack equivalent of `SoilSRFEnerbyBalanceM`. It is invoked once per snow sub-step (`MM = 1 .. NPS`, `dts_sno = dts_HeatWatTP * XNPS`). The Richardson-number correction of `ResistAreodynOverSnow_col` is the same as for the soil (line 841-842). The key differences from the soil balance are:

- Vapor pressure at the snow surface assumes local saturation (no matric suction term): `VPSno0 = vapsat(TKSnow1_snvr(1))` (line 860).
- Losses are split into evaporation from held water `EVAPW2` and sublimation of dry snow `EvapSublimation2`, with latent-heat coefficient `EvapLHTC` for water and `SublmHTC` for sublimation:

  ```
  EVAPW2              = max(MaxVapXAir2Sno, -max(VLWatSnow0M * dts_sno))       (line 864)
  EvapSublimation2    = max(EVAPX2, -max(VLDrySnoWE0M * dts_sno))              (line 868)
  LatentHeatAir2Sno2  = EVAPW2*EvapLHTC + EvapSublimation2*SublmHTC            (line 869)
  ```

- Net heat flux into the snowpack:

  ```
  HeatNetFlx2Sno1 = RadNet2Sno2 + LatentHeatAir2Sno2 + HeatSensAir2Sno2        (line 892)
  HeatNetFlx2Sno2 = HeatNetFlx2Sno1 + HeatAdvAir2SnoByEvap2                    (line 894)
  ```

The snowpack layer solver `SolveSnowpackM` (SnowPhysMod.F90:499-780) then runs its own `DO MM = 1, NPS` (line 565). Inside, `SnowPackIterationMM` computes inter-layer snow/water/ice/heat transfers (drift, gravitational settling, melt percolation, refreezing), and the explicit freeze-thaw loop `D9860: DO L = 1, JS` (line 590) applies a latent-heat-constrained phase change at `TFice`:

```
TFLX1          = VLHeatCapSnowMX * (TFice - TKApp) / 2.7185 * dts_wat         (line 669)
if melt:   HeatByFrezThaw = max(-LtHeatIceMelt*TotSnowLMass, TFLX1)           (line 680)
if freeze: HeatByFrezThaw = min(LtHeatIceMelt*max(VOLW0X - tinyw1, 0), TFLX1) (line 687)
```

with `LtHeatIceMelt` the latent heat of fusion of water-ice. Updated layer volumes and temperatures are clamped to a tiny floor `tinyw0 = 1.e-16 m3` (line 528, 728-730) to avoid divide-by-zero downstream, and guarded against non-physical excursions of > 20 K/step or temperatures < 200 K (line 748-758) which trigger an `endrun('crazy snow temperature')`.

At the end of each hour `SnowMassUpdate` (`f90src/HydroTherm/SnowPhys/SnowBalanceMod.F90:57-169`) and `SnowpackLayering` (line 549-824) are called from `Balances/RedistMod.F90:126,144` to close the snow mass balance, coalesce thin layers, re-split thick layers, and advance the diagnostic `SnowDepth_col`.

## Snow-litter and snow-soil vapor/heat exchange

`SnowSurLitterExch` (`f90src/HydroTherm/SnowPhys/SnowPhysMod.F90:1719-1813`) couples a snow layer L directly to the litter below when litter fraction `FracSurfByLitR_col > ZEROL = 1.e-3` (PhysPars.F90:48). It computes harmonic-mean vapor and thermal conductances between snow and litter and between litter and soil (lines 1768-1797) and then calls `SnowSurfLitRIteration` for the actual inner loop over `NPR` steps. `SnowTopSoilExch` (SnowPhysMod.F90:1817-1925) is the analogous direct snow-to-soil interaction used when litter cover is absent; its thermal-conductivity expression for the top soil layer (line 1898-1904) is the de Vries form shared with the litter and subsurface code.

The snow-litter vapor flux follows

```
VapFlxSno2Litr  = CNVR(snow,litr) * (vapsat(TKSno) - vapsat_at_psi(TKLit))    (SnowPhysMod.F90:1475+)
```

with the Kelvin-equation correction for litter vapor pressure `vapsat_at_psi = vapsat(TK) * exp(18*PSISM1_litr/(RGASC*TK))`. Heat transport across each interface separates conduction (proportional to thermal conductivity and T gradient) and convection (cpw * T * vapor_flux) as in the subsurface code.

## Surface runoff and overland flow

After the surface energy balance and soil-litter water exchange, `InfilSRFRoffPartitionM` (SurfPhysMod.F90:955) decides what fraction of surface water infiltrates versus becomes runoff, and `XGridsSurfRunoffM` (SurfLitterPhysMod.F90:744) exchanges runoff between grid cells. Overland flow velocity uses the Gauckler-Manning formula:

```
CrossSectVelocity = HydraulicRadius^(2/3) * sqrt(slope)     [m/s]             (SurfPhysMod.F90:1725-1739)
```

documented in the source as "ref: https://en.wikipedia.org/wiki/Manning_formula V=k/n*Rh^(2/3)*S^(1/2)". Note: the roughness coefficient n is absorbed into an upstream scaling; the literal code returns unit-k velocity.

## Diagnostics after the energy balance

`SumAftEnergyBalanceM` (SurfPhysMod.F90:1530-1624) accumulates the sub-iteration fluxes into the hourly `LWRadBySurf_col`, `Eco_RadSW_col`, `TLatHeatFlx_col`, `TSenHeatFlux_col` etc. `UpdateSurfaceAtM` (line 1509) collects the final hourly bookkeeping. `writeSurfDiagnosis` (line 1743) is a debug-only printer that is turned on through `EcoSIMCtrlMod` flags.

## Literature references present in the source

- **Choudhury, B. J. and Monteith, J. L. (1988)** - used for canopy-air to ground resistance (`SurfPhysMod.F90:384` comment).
- **Gauckler-Manning formula** - overland flow velocity (`SurfPhysMod.F90:1729` reference in the docstring).
- **Dimitrov et al. (2010)** - macropore dimension closure used in `SoilHydroParaMod.F90:280` (see subsurface_water_and_heat.md).
- **Philip and de Vries (1957) / Clausius-Clapeyron** - Kelvin equation for soil-surface vapor pressure (`SurfPhysMod.F90:584`).
- **Stefan-Boltzmann** - longwave emission (`SurfPhysMod.F90:322-326`).

Other references (Choudhury-Monteith wind attenuation, de Vries 1963 thermal conductivity) are implied by the equation structure but not explicitly cited in the current source.
