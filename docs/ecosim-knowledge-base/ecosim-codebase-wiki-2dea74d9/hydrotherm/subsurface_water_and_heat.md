---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/HydroTherm/SoilPhys/`, `f90src/HydroTherm/PhysData/SoilPhysParaMod.F90`, `f90src/HydroTherm/PhysData/PhysPars.F90`
**Last verified:** 2026-04-24
---

# Subsurface Water and Heat Transport

This document covers the vertical and lateral soil-column physics in HydroTherm: the water-retention curve, hydraulic conductivity model, the 3D Darcy + macropore + vapor flow solver in `WatsubMod.F90`, the conductive + convective heat transport, and the explicit freeze-thaw scheme. See [index.md](index.md) for the overall hierarchy and [surface_energy_balance_and_snow.md](surface_energy_balance_and_snow.md) for upper-boundary handling.

## Water retention: Campbell-style log-log curve

EcoSIM uses a piecewise log-log water-retention model anchored to field capacity (FC) and wilting point (WP), not a direct van Genuchten or Brooks-Corey fit. The key routine is `ComputePsiMCM` (`f90src/HydroTherm/PhysData/SoilPhysParaMod.F90:253-277`):

```fortran
IF(THETWL < FieldCapacity_vr) THEN                                            ! dry branch
  PSISM1 = max(PSIHY,
               -exp(LOGPSIFLD_col
                    + ((LOGFldCapacity_vr - log(THETWL)) / FCD_vr) * LOGPSIMND_col))
ELSE IF(THETWL < POROS_vr - DTHETW) THEN                                      ! wet branch
  PSISM1 = -exp(LOGPSIAtSat
                + (((LOGPOROS_vr - log(THETWL)) / PSD_vr) ** SRP_vr) * LOGPSIMXD_col)
ELSE                                                                          ! saturated
  PSISM1 = PSISE_vr
END IF
```

Notation, from the subroutine docstring (SoilPhysParaMod.F90:50-54):

- `FieldCapacity_vr`, `WiltPoint_vr`: soil water contents at FC and WP.
- `LOGFldCapacity_vr = log(FieldCapacity_vr)`, `LOGWiltPoint_vr = log(WiltPoint_vr)` (SoilHydroParaMod.F90:159-162).
- `FCD_vr = log(FC) - log(WP)`, `PSD_vr = log(POROS) - log(FC)` (SoilHydroParaMod.F90:161-162).
- `LOGPSIAtSat`, `LOGPSIMND_col`, `LOGPSIMXD_col`: logs of matric potential at saturation, FC-WP potential difference, and FC-saturation potential difference, set in `SoilHydroParaMod::ComputeSoilHydroPars` from `PSIAtFldCapacity_col = -0.033 MPa` and `PSIAtWiltPoint_col = -1.5 MPa` (SoilHydroParaMod.F90:442,450).
- `SRP_vr`: non-linearity exponent, set to **0.25 for organic soil** (`CSoilOrgM_vr(ielmc,L,...) > FORGC`), **0.33 for semi-organic**, and **1.00 for mineral** (SoilHydroParaMod.F90:144-151). `SRP = 1.0` collapses the wet branch to a straight line in log-log.
- `DTHETW = ppmc` is a tiny buffer preventing saturation singularities (PhysPars.F90:47).
- `PSIHY` is the hygroscopic minimum (lowest allowed matric potential); it bounds the dry branch to prevent numerical divergence as theta -> 0.

The functional form is Campbell (1974) generalized with distinct exponents in the dry (below FC) and wet (above FC) branches. When the soil file does not supply FC or WP, `SoilHydroParaMod::SetColdRunSoilStates` (line 299-386) provides texture-based defaults:

```
mineral soil (C_org < FORGW):
  FC = 0.2576 - 0.20*sand + 0.36*clay + 0.60e-6*C_org                         (SoilHydroParaMod.F90:307-308)
  WP = 0.0260 + 0.50*clay + 0.32e-6*C_org                                      (line 323)

organic soil (C_org >= FORGW):
  BulkDensity < 0.075: FC=0.27, WP=0.04
  BulkDensity < 0.195: FC=0.62, WP=0.15
  else:                FC=0.71, WP=0.22                                       (line 311-332)

both: FC = FC / (1 - SoilFracAsMacP),    FC = min(0.75*POROS, FC)             (line 319-320)
      WP = WP / (1 - SoilFracAsMacP),    WP = min(0.75*FC, WP)                (line 334-335)
```

`FORGW = 0.25e6` (gC/Mg soil, SoilHydroParaMod.F90:29), `FORGC` is a related threshold from `EcoSimConst`. The 0.2576, 0.20, 0.36, 0.60e-6 etc. coefficients are pedotransfer parameters; the source does not cite a literature reference, but the form is consistent with Rawls et al. (1982)-class equations.

For ponded (non-porous / bulk-density-zero) layers a simplified version is used in `ComputePSIPond` (SoilPhysParaMod.F90:82-115), where ice field capacity and wilting point (`FCI = 0.05`, `WPI = 0.025`, PhysPars.F90:29-30) modulate the effective liquid-water fractions.

Osmotic and gravity potentials are added in `GetSoilHydraulicVars` (`f90src/HydroTherm/SoilPhys/SoilHydroParaMod.F90:40-123`):

```
PSISoilOsmotic_vr          = -RGASC * TKS_vr * SolutesIonConc_vr * 1e-6       (line 88)
PSIGrav_vr                 = mGravAccelerat * (ALT_col - SoilDepthMidLay_vr)  (line 89)
ElvAdjstedSoilH2OPSIMPa_vr = min(PSISM + PSIO + PSIGrav, 0)                   (line 90)
```

## Hydraulic conductivity: Green-Corey integration of K(theta)

EcoSIM does **not** use van Genuchten's analytical K_r formula. Instead `SoilHydroProperty` (`f90src/HydroTherm/SoilPhys/SoilHydroParaMod.F90:128-296`) discretizes the retention curve into 100 bins and numerically integrates 1/psi^2 following Green and Corey (1971, Eq. 1 and Table 1 II) (source comment at line 228-229):

```fortran
SUM2 = sum_{K=1..100}  (2*K-1) / PSISK(K)^2                                   (line 231-238)

do K = 1, 100
  XK = (K-1)/100             ! air-filled relative pore fraction
  YK = (1 - XK)^1.33         ! relative water saturation factor                (line 247)
  SUM1 = sum_{M=K..100}  (2*(M-K)+1) / PSISK(M)^2                             (line 249-251)
  HydroCond_3D(3,K,L,NY,NX) = SatHydroCondVert_vr(L,NY,NX) * YK * SUM1/SUM2   (line 256)  ! vertical
  HydroCond_3D(1,K,L,NY,NX) = SatHydroCondHrzn_vr(L,NY,NX) * YK * SUM1/SUM2   (line 267)  ! horizontal
end do
```

The result is a per-layer lookup table `HydroCond_3D(direction, K_bin, L, NY, NX)` indexed by moisture-bin K. At runtime, `getMoistK` (SoilPhysParaMod.F90:280-287) maps the current water content to a K bin:

```fortran
K = max(1, min(100, 101 - int(100 * thetawl / pores)))
```

Saturated hydraulic conductivity `SatHydroCondVert_vr`, `SatHydroCondHrzn_vr` may be provided by the soil input file; otherwise `SoilHydroProperty` computes them from texture-based theta at -0.033 MPa (SoilHydroParaMod.F90:200-218):

```
mineral (C_org < FORGW):
  SatHydroCondVert = 1.54 * ((POROS - THETF) / THETF)^2                        (line 202)
organic (C_org >= FORGW):
  SatHydroCondVert = (0.10 + 75 * 1e-15^BulkDensity) * FracSoiAsMicP_vr        (line 204-205)
```

### Macropore hydraulic conductivity

Macropores are treated as idealized cylindrical pipes with Poiseuille flow (`SoilHydroParaMod.F90:272-293`):

```
MacPoreRadius_vr  = 0.5e-3                                 ! 0.5 mm, line 282
MacPoreNumbers_vr = int(VLMacP_vr / (PI * MacPoreRadius^2 * VGeomLayert0_vr))  (line 283)
PathLenMacPore_vr = 1 / sqrt(PI * MacPoreNumbers_vr)                           (line 286)
VISCWL            = Viscosity_H2O(TCS_vr)                                      (line 291)  [temperature-dependent]
HydroCondMacP_vr  = 3.6e3 * PI * MacPoreNumbers * MacPoreRadius^4 / (8 * VISCWL)  (line 293)
```

"Eq.(3.3)-(3.4) from Dimitrov et al. (2010)" is cited at line 280. The 3.6e3 prefactor converts Poiseuille Q in SI to EcoSIM's per-hour volume units.

### Hourly root-uptake conductivity

`HYCDMicP4RootUptake_vr` is the conductivity actually consumed by the plant root water uptake routine (`Plant_bgc/NutUptakeMod.F90`). It is computed in `GetSoilHydraulicVars` (`SoilHydroParaMod.F90:118-119`) as the arithmetic mean of the two horizontal-direction lookup entries at the current moisture bin:

```
K = getMoistK(THETW_vr, POROS_vr)
HYCDMicP4RootUptake_vr = 0.5 * (HydroCond_3D(1,K,L,NY,NX) + HydroCond_3D(3,K,L,NY,NX))
```

## Soil thermal conductivity: de Vries with convection

`CalcSoilThermConductivity` (`f90src/HydroTherm/PhysData/SoilPhysParaMod.F90:200-233`) computes the bulk thermal conductivity of each layer using a de Vries (1963)-style weighted average, with a Rayleigh-number-dependent Nusselt correction for convective enhancement when water- or air-filled porosity is high:

```
HeatDiffusByWat  = max(0, theta_wat - TRBW)^3      ! TRBW = 0.375, PhysPars.F90:28
HeatDiffusByAir  = max(0, theta_air - TRBA)^3      ! TRBA = 0.000, PhysPars.F90:27
RYLXW1  = dT * HeatDiffusByWat * 1e-6              ! Rayleigh-like scale        (line 217)
RYLXA1  = dT * HeatDiffusByAir * 1e-6
RYLNW1  = min(1e4, RYLXW * RYLXW1)                                               (line 219)
XNUSW1  = max(1, 0.68 + 0.67 * RYLNW1^0.25 / DNUSW)  ! Churchill-Chu Nusselt    (line 221)
TCNDW   = 2.067e-3 * XNUSW1                          ! water k, MJ/m/K/h
TCNDA   = 9.050e-5 * XNUSA1                          ! air k
WTHET1  = 1.467 - 0.467 * FracSoilAsAirt                                        (line 225)
TCND    = (SolidTCND_Numer + theta_wat*TCNDW + 0.611*theta_ice*7.844e-3
           + WTHET1 * theta_air * TCNDA)
          / (SolidTCND_Denom + theta_wat + 0.611*theta_ice + WTHET1*theta_air)  (line 226-229)
```

Constants:

- `TRBW = 0.375` and `TRBA = 0.000` are the threshold water-filled and air-filled porosities for the convective correction (PhysPars.F90:27-28). When `theta_wat < TRBW` the water convection term is exactly zero, i.e. the model is pure conduction at drier states.
- `VISCW`, `VISCA`, `DIFFW`, `DIFFA`, `EXPNW`, `EXPNA` are the water/air viscosities, thermal diffusivities, and thermal expansion coefficients (PhysPars.F90:35-41); they combine into the Rayleigh-similarity groups `RYLXW`, `RYLXA`.
- `DNUSW`, `DNUSA` are Prandtl-number Churchill-Chu prefactors (PhysPars.F90:44-45).
- `2.067e-3`, `9.050e-5`, `7.844e-3` are the base thermal conductivities of water, air, and ice in MJ/(m K h), converted from SI.

The solid-soil numerator and denominator `NumerSolidThermCond_vr`, `DenomSolidThermCond_vr` are precomputed elsewhere (not in HydroTherm) and encode the per-grain thermal conductivities (quartz, clay, organic matter) with shape factors.

## Freezing point depression

`get_Tfrez` (`f90src/HydroTherm/PhysData/SoilPhysParaMod.F90:236-249`) applies the Clausius-Clapeyron relation with "Cary and Mayland (1972)" explicitly cited in the docstring (line 239):

```fortran
TFREEZ = -9.0959e4 / (max(PSI, -5.5) - LtHeatIceMelt)
```

`9.0959e4 ~= 273.15 * LtHeatIceMelt` (line 240 comment). The `max(PSI, -5.5)` clamp is documented as "used for numerical stability" (line 246). The effective freezing temperature is used by the micropore freeze-thaw routine to determine whether ice or liquid water is the equilibrium phase for given matric + osmotic potential.

## The watsub driver: overall structure

`watsub` (`f90src/HydroTherm/SoilPhys/WatsubMod.F90:82-199`) is the main entry point for the subsurface water and heat solver. In the ATS-coupled build the equivalent sequence (surface staging + `RunSurfacePhysModelM` + subsurface 3D flow) is assembled inside `ATSUtils/ATSEcoSIMAdvanceMod.F90`; `watsub` itself remains in the tree as the single-box driver.

```
watsub:
  if fixWaterLevel: HeatAdv_scal = 0                                           (WatsubMod.F90:112)
  apply soil-cable warming if active                                            (line 114-118)
  LocalCopySoilVars                                                             (line 120)
  BeginMassCheck                                                                (line 122)
  StageSurfacePhysModel                                                         (line 125)
  InitSoilHydrauics                                                             (line 127)
  DO M = 1, NPH:                                                                (line 132)
    PrepHydroThermIterM                                                         (line 136)
    RunSurfacePhysModelM        (surface energy + snow + litter + infiltration) (line 138)
    CopySoilWatVolIterateM                                                      (line 141)
    Subsurface3DInternalFlowM   (internal grid fluxes: Darcy + macropore + vapor)(line 144)
    XBoundaryFlowM              (boundary fluxes)                                (line 146)
    Summarize3DFlowM            (net fluxes per cell)                            (line 148)
    AccumulateSnowRedisFluxM    (if snowRedist_model)                            (line 150)
    UpdateSoilMoistTempM        (explicit update VLWatMicP1, TKSoil1 + FreezeThaw)(line 152)
    AggregateSurfRunoffFluxM                                                     (line 154)
    UpdateSurfaceAtM                                                             (line 156)
    UpdateStateFluxAtM   (M<NPH) or UpdateFluxAtExit (M=NPH)                     (line 158-162)
    ExitMassBalanceM                                                             (line 164)
  ENDDO
  diagnose surface ice: set NLF_col to the highest layer with ThetaICEZ > 0.9   (line 170-197)
```

Time steps: `dts_HeatWatTP = 1 / NPH` (hour) for soil heat-water iterations, `dts_sno = dts_HeatWatTP * XNPS` for snow, `dts_wat` for water-flux unit conversion (all provided by `EcoSIMSolverPar`). `NPH`, `NPS`, `NPR` are compile-time or runtime-configured.

## 3D internal flow

`Subsurface3DInternalFlowM` (`f90src/HydroTherm/SoilPhys/WatsubMod.F90:614-779`) sweeps every internal grid-cell interface exactly once per iteration. The sweep pattern traverses west-to-east, north-to-south, top-to-bottom:

```fortran
DO NX = NHW, NHE
  DO NY = NVN, NVS
    DO L = 1, NL_col(NY,NX)
      DO N = FlowDirIndicator_col(NY,NX), 3
        if N == 1 (west-east):   destination = (NX+1, NY, L)
        if N == 2 (north-south): destination = (NX,   NY+1, L)
        if N == 3 (vertical):    destination = (NX,   NY,   L+1)
      ENDDO
    ENDDO
  ENDDO
ENDDO
```

For each (source, destination) pair that contains valid soil (lines 707-712), the routine calls in turn:

1. `CalcSoilWatPotential` on both cells (psi_m, osmotic, gravity).
2. `MicropXGridDarcyFlow` (line 730-732) - Darcy micropore flow.
3. `MacropXgridFLow` (line 734) - gravity-driven macropore flow.
4. `WaterVaporXgridFlow` (line 736) - binary vapor diffusion in the air-filled pore space.
5. `SolveXgridHeatConduction` (line 749) - conduction plus convective heat.

Results are accumulated into `WaterFlow2Micpt_3D(direction, L_dst, NY_dst, NX_dst)`, `WaterFlow2Macpt_3D`, `HeatFlow2Soili_3D`, and propagated into the longer-step sums `WaterFlowSoiMicP_3D`, `HeatFlow2Soil_3D` (line 758-766) that the transport and plant modules read.

### Micropore Darcy flow

`MicropXGridDarcyFlow` (`f90src/HydroTherm/SoilPhys/WatsubMod.F90:1784-1988`) handles the pressure-driven water flow. It distinguishes four saturation regimes at the source-destination boundary (line 1818-1880):

- both cells saturated,
- source saturated, destination unsaturated: Green-Ampt style,
- source unsaturated, destination saturated: Green-Ampt style,
- both unsaturated: standard Richards flow,

and selects the matric potential and moisture-bin K for each case. The interface conductance is the harmonic mean weighted by layer thickness (Arrhenius mixing rule for serial layers):

```fortran
AVE_CONDUCTANCE = 2 * HydCondSrc * HydCondDest
                  / (HydCondSrc * DLYR_3D(N,N_dst,...) + HydCondDest * DLYR_3D(N,N_src,...))   (line 1918)
```

The total water potential at each side includes matric, osmotic, and gravity components:

```
PSIST1 = PSISM1_vr(src) + PSIGrav_vr(src) + PSISoilOsmotic_vr(src)            (line 1902)
PSISTL = PSISM1_vr(dst) + PSIGrav_vr(dst) + PSISoilOsmotic_vr(dst)            (line 1906)
```

The unconstrained Darcy flux is

```
PtWatDarcyFlux = AVE_CONDUCTANCE * (PSIST1 - PSISTL) * AREA * dts_HeatWatTP   (line 1932)
```

The flux is then constrained by (a) the volumetric difference between current water and saturated water (to prevent over-saturating the destination, line 1939-1946 forward direction and line 1956-1962 reverse), and (b) the air-filled pore volume of the destination cell. Convective heat flux is computed as the upwind:

```fortran
if WatDarcyFlowMicP > 0:   HeatByDarcyFlow = cpw * TKSoil1(src) * Q * HeatAdv_scal       (line 1979)
else:                       HeatByDarcyFlow = cpw * TKSoil1(dst) * Q * HeatAdv_scal       (line 1982)
```

This is an **explicit, first-order upwind** scheme, not Crank-Nicolson or implicit. There is no tridiagonal solver. Numerical stability is achieved through the small sub-step `dts_HeatWatTP` (= 1/NPH hour) and the conservative flux limiters. The surface-layer K is attenuated by `KSatRedusByRainKinetEnergy` (line 1887-1891) to represent rainfall-induced surface sealing.

### Macropore flow

`MacropXgridFLow` (`f90src/HydroTherm/SoilPhys/WatsubMod.F90:1990-2062`) uses a simplified gravity-plus-fullness potential (line 2012-2015):

```
PSISH = PSIGrav_vr + mGravAccelerat * DLYR * (min(1, VLWatMacP / VLMacP) - 0.5)
```

and the `AVCNHL_3D` saturated macropore conductance precomputed in `SoilHydroParaMod`. Horizontal and vertical flows are handled separately, with the vertical flow being strictly gravity-driven once the source-destination pair is established (line 2034+).

### Vapor diffusion

`WaterVaporXgridFlow` (`f90src/HydroTherm/SoilPhys/WatsubMod.F90:2064-2129`) implements binary vapor diffusion through the air-filled pore space when both cells exceed `AirFillPore_Min` (line 2099):

```
VP1  = vapsat(TK_src) * exp(18 * PSISV_src / (RGASC * TK_src))                (line 2102)  ! Kelvin eqn
VPL  = vapsat(TK_dst) * exp(18 * PSISV_dst / (RGASC * TK_dst))                (line 2103)
CNV1 = WVapDifusvitySoil_vr(src) * theta_air_src^2 * POROQ / POROS_src        (line 2104)  ! Millington-Quirk tortuosity
CNVL = WVapDifusvitySoil_vr(dst) * theta_air_dst^2 * POROQ / POROS_dst        (line 2105)
ATCNVL = 2*CNV1*CNVL / (CNV1*DLYR_dst + CNVL*DLYR_src)                         (line 2106)
PotentialVaporFlux = ATCNVL * (VP1 - VPL) * AREA * dts_HeatWatTP              (line 2111)
ConvectVapFlux  = limited by (1) equilibrium VPY, (2) available water in source
```

Convective heat carried by the vapor flux is `HeatByConvectVapFlux = (cpw*TK_upwind + EvapLHTC) * ConvectVapFlux` (lines 2118, 2122), consistent with condensation releasing latent heat into the destination cell.

### Heat conduction

`SolveXgridHeatConduction` (`f90src/HydroTherm/SoilPhys/WatsubMod.F90:2132-2234`) solves the heat equation by separating conduction and convection with a Bishop-style (two-temperature) split. For each interface:

```
dCPv = cpw * ConvectVapFlux
DTKX = |TKSoil1(src) - TKSoil1(dst)|
call CalcSoilThermConductivity(src, DTKX, ThermCondSrc)                       (line 2161)
call CalcSoilThermConductivity(dst, DTKX, ThermCondDst)                       (line 2163)
ATCNDL = 2*ThermCondSrc*ThermCondDst / (ThermCondSrc*DLYR_dst + ThermCondDst*DLYR_src)   (line 2165)
HFLWC  = ATCNDL * (TK1X - TKLX) * AREA * dts_HeatWatTP                          (line 2223)  ! conductive
HFLWX  = (TK1X - TKY) * VHeatCapacity1(src) * dts_wat                           (line 2222)  ! storage-constrained
HeatCondSoi = sign-preserving min of HFLWC and HFLWX                            (line 2224-2230)
```

`TKY` is the interface-equilibrium temperature that would result if all heat transferred (line 2216-2220). The `HeatFluxAir2Soi` (ground heat flux) from the surface energy balance enters only for the top layer (line 2182-2184). Results feed `HeatFlow2Soili_3D(N, N_dst, N5, N4)` (line 2232), which downstream is integrated into total layer heat change in `UpdateSoilMoistTempM`.

## Water-table exchange

Two routines couple the model column to an external groundwater body:

- `DischargeOverWaterTBL` (`f90src/HydroTherm/SoilPhys/WatsubMod.F90:2236-2347`) handles upward/lateral loss to an external water table when the soil water potential exceeds the weighted external head, using the saturated K and a slope-aware driving head `PSISWD = XN * 0.5 * mGravAccelerat * SLOPE_col * DLYR * (1 - WaterTBLSlope_col)` (line 2279). Separate branches for micropore (line 2278) and macropore (line 2322) discharge.
- `RechargeFromExtWaterTBL` (`f90src/HydroTherm/SoilPhys/WatsubMod.F90:2350-2446`) handles downward/lateral gain from the external water table when the layer is below the active-layer depth and below the external water-table depth. The recharge is bounded by the available air-filled pore volume in the destination grid (line 2396-2401).

Both apply a scale factor `Recharg2WTBLScal` (set elsewhere) and respect the inverse distance `1 / (RechargDist2WTBL + 1)` to the external water table.

Tile drainage uses `Config4TileDrainage` (`WatsubMod.F90:1575-1649`). Vertical boundary drainage (free drainage at the base) is `VertBoundaryDrainM` (`WatsubMod.F90:1186-1250`).

## Freeze-thaw

`FreezeThawIterateM` (`f90src/HydroTherm/SoilPhys/WatsubMod.F90:2449-2585`) applies an **explicit, latent-heat-constrained phase change** to micropore and macropore water separately per layer. It is invoked from within `UpdateSoilMoistTempM` (line 1252-1426).

The apparent temperature `TK1App` reflects the layer's energy state if no phase change had occurred:

```
VLWatMicP1X  = VLWatMicP1 + WatNetFlow2MicP_3DM + FWatExMacP2MicPiM + FWatIrrigate2MicP1      (line 2501)
VLWatMacP1X  = VLWatMacP1 + WatNetFlow2Macpt_3DM - FWatExMacP2MicPiM                           (line 2502)
VLHeatCapacityX = VHeatCapSolidSoil + cpw*(VLWatMicP1X + VLWatMacP1X) + cpi*(VLiceMicP1 + VLiceMacP1)  (line 2504)
ENGY1        = VHeatCapacity1 * TKSoil1                                                        (line 2503)
TK1App       = (ENGY1 + THeatFlow2Soil_3DM + HeatIrrigation1) / VLHeatCapacityX               (line 2508)
```

With an optional root-heat-capacity addition `dcpo = cpo * gOC_to_m3_OM(rootC)` when `plantOM4Heat` is true (line 2491-2496).

### Macropore freeze-thaw (no depression)

Macropore water is assumed to have no freezing-point depression (`TFICE` from EcoSimConst, the bulk water freezing point). Condition for phase change (line 2515-2516):

```fortran
(TK1App < TFICE .and. VLWatMacP1 > threshold)  .or.  (TK1App > TFICE .and. VLiceMacP1 > threshold)
```

The potential latent heat release and its water-equivalent

```
MacPIceHeatFlxFrezPt = VLHeatCapacityBX * (TFICE - TK1App) / (1 + 6.2913e-3 * TFICE) * dts_wat   (line 2520)
if thaw:   MacPIceHeatFlxFrez = max(-LtHeatIceMelt * DENSICE * VLiceMacP1 * dts_wat, MacPIceHeatFlxFrezPt)  (line 2525)
if freeze: MacPIceHeatFlxFrez = min( LtHeatIceMelt * VLWatMacP1X * dts_wat,          MacPIceHeatFlxFrezPt)  (line 2528)
FIceThawedMacP = -MacPIceHeatFlxFrez / LtHeatIceMelt                                                (line 2530)
```

The `1 / (1 + 6.2913e-3 * TFICE)` factor originates in an apparent-heat-capacity formulation for the temperature-energy relationship across the phase boundary; the exact derivation is not documented in the comments (line 2519: "where is the following equation come from?"). This is a calibration-relevant sensitivity.

### Micropore freeze-thaw (with depression)

Micropore freezing temperature uses the Clausius-Clapeyron-based depression:

```
PSISMX  = PSISoilMatricPtmp_vr + PSISoilOsmotic_vr                                              (line 2497)
TFREEZ  = get_Tfrez(PSISMX)                                                                      (line 2499)
```

and the analogous condition and constraint are applied (lines 2538-2556). `SoilWatFrezHeatRelease_vr` is the total latent-heat release per layer, summing micropore and macropore contributions (line 2565). Accumulators `TLIceThawMicP_vr`, `TLIceThawMacP_vr`, `TLPhaseChangeHeat2Soi_vr` are updated for post-hour bookkeeping (line 2577-2582).

The scheme is explicit: the phase change applies at the end of the sub-iteration using the `TK1App` estimate, with flux-conserving bounds. When the available water or ice is small (below the per-grid `ZERO * VGeomLayer_vr` threshold) no phase change occurs.

## Unfrozen water in frozen soil

Unfrozen water content in a frozen layer is implicitly represented by the Clausius-Clapeyron freezing-temperature depression acting on the soil matric + osmotic potential (`get_Tfrez(PSISMX)`). A layer at temperature between `TFREEZ` and `TFICE` can contain both ice and liquid water in equilibrium, with the partition set by the energy balance iteration.

## Film-thickness diagnostic

For the vertical direction, the destination cell's `FILMM_vr` is updated with `FilmThickness(PSISoilMatricPtmp_vr(dst))` (`WatsubMod.F90:769`) each iteration; this is a diagnostic of liquid water film thickness on soil particles used by the root and microbial modules.

## Numerical scheme summary

| Aspect | EcoSIM HydroTherm choice |
|---|---|
| Water retention | Piecewise log-log (Campbell-style), branch exponent `SRP` = 1 mineral / 0.33 semi-organic / 0.25 organic |
| Unsaturated K(theta) | Green & Corey (1971) integration of 1/psi^2 over 100 pore-size bins, stored as lookup table |
| Saturated K | From soil file, or texture-based default (mineral: Campbell-like; organic: log-linear in bulk density) |
| Macropore K | Poiseuille, radius 0.5 mm, variable number, temperature-dependent viscosity |
| Richards solver | Explicit first-order upwind, NPH sub-steps per hour, volume-limited flux bounds |
| Vapor flow | Binary diffusion, Millington-Quirk tortuosity, Kelvin-equation surface vapor |
| Heat equation | Explicit conduction (de Vries with convective Nusselt correction) + upwind convection, Bishop-type T-split |
| Boundary conditions | Top: ground heat flux from surface energy balance. Base: free drainage + optional external water table. Lateral: Darcy + slope-aware gravity drop between columns |
| Phase change | Explicit, latent-heat-constrained, Clausius-Clapeyron depression for micropores, bulk TFICE for macropores |
| Tridiagonal / implicit solver | **None**. Stability is ensured by small sub-steps and conservative flux limiters. |

## Literature references present in the source

- **Campbell (1974)** (implied structure, not cited inline) - log-log water retention.
- **Cary and Mayland (1972)** - Clausius-Clapeyron freezing-point depression (`SoilPhysParaMod.F90:239`).
- **de Vries (1963)** (implied structure, not cited inline) - thermal conductivity of porous media.
- **Dimitrov et al. (2010)** - macropore geometry and Poiseuille conductance, cited as "Eq.(3.3)-(3.4)" (`SoilHydroParaMod.F90:280`).
- **Grant (1993)** - bulk modulus for root penetration, cited as "Eq.(8) in Grant (1993), Simulation model of soil compaction and root growth I. Model structure." (`SoilHydroParaMod.F90:95`).
- **Green and Corey (1971)** - numerical K(theta) integration, cited as "Eq.(1) and II in Table 1" (`SoilHydroParaMod.F90:228-229`).
- **Holtz and Kovacs (1981)** - baseline cohesion vs texture (`SoilHydroParaMod.F90:826`).
- **Rickman et al. (1992)** - fit data for bulk modulus (`SoilHydroParaMod.F90:96`).
- **Vucetic and Dobry (1991)** - reference strain for modulus degradation (`SoilHydroParaMod.F90:993`).
- **Zhang, Horn, and Hallett (2005)** - OM effect on clay cohesion (`SoilHydroParaMod.F90:850`).
- **Ekwue (1990)** - OM binding for sandy soils (`SoilHydroParaMod.F90:859`).

The last five references are specific to the geotechnical helpers (`estimate_friction_natural`, `estimate_mineral_cohesion`, `estimate_root_stiffness`) which are used for root-penetration mechanics, not for the mainline water/heat transport. They are included here for completeness since they live in `SoilHydroParaMod.F90` (lines 584-1006).
