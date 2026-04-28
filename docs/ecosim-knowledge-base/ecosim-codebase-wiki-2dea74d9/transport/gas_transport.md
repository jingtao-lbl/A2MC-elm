---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/Transport/Nonsalt/` (gas-phase portion)
**Last verified:** 2026-04-24
---

# Gas transport

Gas-phase transport in EcoSIM is driven by the fast inner loop of `TranspNoSalt`. The solute-phase outer loop (see [`solute_transport.md`](solute_transport.md)) updates water-phase concentrations over `NPH` iterations per hour; inside each of those iterations, `NPT` gas-phase sub-iterations advance soil-air gas concentrations and couple them to the aqueous phase through dissolution.

## Files and entry points

| File | Main subroutines | Purpose |
|------|------------------|---------|
| `Transport/Nonsalt/TranspNoSaltFastMod.F90` | `TransptFastNoSaltMM` (line 35), `GasTransportMM` (line 513), `GasDiffusionMM` (line 779), `UpstreamGasAdvectionMM` (line 588), `GasDissolutionMM` (line 545), `Atm2TopSoilGasDifussionMM` (line 814), `Atm2TopSoilGasAdvectionMM` (line 476), `LitterGasVolatilDissolMM` (line 404), `SurfSoilFluxGasDifAdvMM` (line 443) | Per-substep gas kernels |
| `Transport/Nonsalt/TranspNoSaltSlowMod.F90` | `BubbleEffluxM` (line 2725) | Ebullition once per hydrology substep |
| `Transport/Nonsalt/TranspNoSaltMod.F90` | `TranspNoSalt` (line 296), `PassSlow2FastIterationM` (line 377) | Outer driver, boundary-layer setup |

## Tracers

Gas tracers are declared in `f90src/Modelconfig/TracerIDMod.F90` lines 13-24. EcoSIM defines 9 gaseous species (transport is over `idg_beg:idg_NH3` for the uniform gas-phase carriers, with `idg_NH3B` as a banded counterpart that mirrors NH3 transport in banded-fertilizer volumes):

| Index | Symbol | Name |
|------|--------|------|
| 1 | `idg_CO2` | Carbon dioxide |
| 2 | `idg_CH4` | Methane |
| 3 | `idg_O2` | Oxygen |
| 4 | `idg_N2` | Dinitrogen |
| 5 | `idg_N2O` | Nitrous oxide |
| 6 | `idg_H2` | Hydrogen |
| 7 | `idg_AR` | Argon |
| 8 | `idg_NH3` | Ammonia (non-banded) |
| -- | `idg_NH3B` | Ammonia in banded fertilizer strip (= `idg_NH3+1`) |

`idg_end = idg_NH3B` and `idg_beg = idg_CO2`. The loop idiom `DO idg=idg_beg,idg_NH3` covers the full gas set once; the banded-NH3 volume `VLsoiAirPMB_vr` is tracked separately (`TranspNoSaltMod.F90:412-416`) and treated via mirrored kernels throughout `TranspNoSaltFastMod`.

Solubility coefficients (`GasSolbility_vr`) are read from `AqueChemDatatype`; for bubbling the mass-basis solubility is `MolecularWeight(idg) * GasSolbility_vr(idg,L,NY,NX)` (`TranspNoSaltSlowMod.F90:2763`).

## Diffusion model

Soil-to-soil gas diffusion is computed in `GasDiffusionMM` (`TranspNoSaltFastMod.F90:779-812`):

```
DFLG2 = 2.0 * POROQ * theta_a(src)^2 / porosity(src) * A / DL                  (line 795)
DFLGL = 2.0 * POROQ * theta_a(dest)^2 / porosity(dest) * A / DL                (line 797)

CNDC1 = DFLG2 * GasDifctScaledMM_vr(idg,src)                                   (line 801)
CNDC2 = DFLGL * GasDifctScaledMM_vr(idg,dest)                                  (line 802)
GasDifuscoefMM_3D = CNDC1 * CNDC2 / (CNDC1 + CNDC2)                            (line 803)

flux = GasDifuscoefMM_3D * ( C_src - C_dest )                                  (line 809)
```

with `POROQ = 0.66` (`Utils/EcoSimConst.F90:38`) and `theta_a = FracAirFilledSoilPoreM_vr`. The functional form `theta_a^2 / porosity` with `POROQ` as a porosity exponent corresponds to the Millington (1959) / Millington-Quirk family of tortuosity models rather than a Penman straight-line reduction. The harmonic average `CNDC1*CNDC2/(CNDC1+CNDC2)` across the interface applies the standard two-layer resistor composition.

The flux is gated on both cells having air-filled porosity above `AirFillPore_Min` and significant air volume (`TranspNoSaltFastMod.F90:529-533`).

## Upstream advection

Water-driven gas advection is computed in `UpstreamGasAdvectionMM` (`TranspNoSaltFastMod.F90:588-633`). Because of volume conservation in saturated/partially-saturated micropores, gas displaces in the opposite direction from water:

```
FLQW = WaterFlow2SoilMM_3D(N,dest)                                             (line 604)

if FLQW > 0  ! water INTO dest => gas OUT of dest
  VFLW = -min( VFLWX, FLQW / VLsoiAirPM(dest) )
  RGasAdv = VFLW * max(0, trcg_gasml2(idg,dest))
else         ! water OUT of dest => gas INTO dest
  VFLW = -min(-VFLWX, FLQW / VLsoiAirPM(src))
  RGasAdv = VFLW * max(0, trcg_gasml2(idg,src))
endif
```

The upwind source/destination selection and the cap `VFLWX=0.5` (`TranspNoSaltDataMod.F90:11`) together guarantee monotonicity and non-negativity for the advective component. The combined diffusion + advection tendency is accumulated into `Gas_AdvDif_FlxMM_3D(idg,N,dest)` (`TranspNoSaltFastMod.F90:618, 629`).

`GasTransportMM` (`TranspNoSaltFastMod.F90:513-542`) is the combined driver that calls `GasDiffusionMM` then `UpstreamGasAdvectionMM` when both cells qualify.

## Atmospheric boundary conditions

The top of the soil column exchanges gas with the atmosphere through two parallel pathways, both guarded by a boundary-layer conductance derived from above-canopy aerodynamics:

1. **Diffusion** (`Atm2TopSoilGasDifussionMM`, `TranspNoSaltFastMod.F90:814-851`): the soil-air diffusivity `GasDifuscoefMM_3D` and the atmospheric boundary-layer conductance `PARGas_CefMM` are combined in series,
   `DGQ_cef = GasDifuscoefMM_3D * PARGas_CefMM / (GasDifuscoefMM_3D + PARGas_CefMM)` (line 846),
   driving a flux proportional to `(AtmGasCgperm3_col - C_soil_surf)` (line 848). `AtmGasCgperm3_col` comes from `ClimForcDataType`.

2. **Advection with water flux into/out of the surface layer** (`Atm2TopSoilGasAdvectionMM`, `TranspNoSaltFastMod.F90:476`).

The per-tracer boundary-layer conductance is set in `PassSlow2FastIterationM` (`TranspNoSaltMod.F90:395-403`) by scaling the bulk conductance `CondGasXSnowM_col` with the molecular-diffusivity factors listed in the overview.

Litter volatilization is handled separately in `LitterGasVolatilDissolMM` (`TranspNoSaltFastMod.F90:404`), and the surface-soil combined diffusive + advective exchange is wrapped in `SurfSoilFluxGasDifAdvMM` (`TranspNoSaltFastMod.F90:443`).

Bottom boundary: gases leave the column through `trcs_drainage_flx_col(idg,NY,NX)` tied to the water drainage flux out of the deepest layer (`NL_col`). The ExitMassCheck (`TranspNoSaltMod.F90:233, 269`) reports both the drainage loss and the net `soil2drainage` term.

## Gas-aqueous coupling: dissolution and volatilization

`GasDissolutionMM` (`TranspNoSaltFastMod.F90:545-585`) computes the dissolution/volatilization flux between the gas and aqueous phases within a single soil layer:

```
RGas_Disol = DiffusivitySolutEffM_vr * ( C_gas * V_w*H(c) - C_sol * V_air )
                                          / ( V_w*H(c) + V_air )              (line 562-565)
```

where `trcg_VLWatMicP_vr(idg,L,NY,NX) = VLWatMicPM * GasSolbility_vr(idg,L)` is the Henry-law-weighted "effective" water volume for each gas. NH3 and its banded counterpart NH3B are treated with the banded / non-banded pore volumes `VLsoiAirPMA/B_vr`, `VLWatMicPXA/B_vr` (lines 568-580).

This is the single routine that couples gas-phase and aqueous-phase transport: aqueous CO2/CH4/O2/N2/N2O/H2/Ar/NH3 produced or consumed by `Microbial_bgc` is dissolved from gas or volatilized back, and the balance is accumulated into `RGas_Disol_FlxMM_vr`.

## Ebullition (bubbling)

`BubbleEffluxM` (`TranspNoSaltSlowMod.F90:2725-2850`) runs once per hydrology substep when `ldo_transpt_bubbling=.true.` (controlled by `EcoSIMCtrlMod`). Algorithm:

1. Sweep upward from the first unfrozen layer `NLF_col(N2,N1)` to the top of the column.
2. For each unfrozen, water-significant layer, convert all gas-equivalent (aqueous) masses to moles using `GasMassSolubility(idg) = MolecularWeight(idg) * GasSolbility_vr(idg,L)` (line 2763).
3. Compute `VTATM`, the moles of gas the layer's water could hold at atmospheric pressure plus ponded head (line 2778), and `VTGAS`, the current total moles in aqueous phase (line 2779).
4. If `VTGAS > VTATM`, remove `FracEbu * (VTATM - VTGAS)/VTGAS` of each aqueous gas (line 2786). Half-step damping (0.5 in line 2785) prevents oscillation.
5. If the layer is at the surface or below the water table, the removed gas emits as ebullition flux `trcg_ebu_flx_col`. Otherwise it is deposited into the gas phase `trcg_gasml2_vr` of the same layer and transported upward on the next gas substep.

O2 and CH4 ebullition are also summed into `RO2AquaSourcePrev_vr` and `RCH4PhysexchPrev_vr` for reporting (lines 2820-2821).

## BGC source/sink coupling

Transport consumes per-substep source and sink arrays produced by `Microbial_bgc` and `Plant_bgc`:

- `RBGCSrceGasMM_vr`, `RBGCSinkGasMM_vr` -- gas-phase BGC terms (production, uptake) applied in the fast loop.
- `RBGCSrcSoluteM_vr`, `RBGCSinkSoluteM_vr` -- aqueous BGC terms; NH3 and related are applied in `ApplySlowSourceSink` (`TranspNoSaltSlowMod.F90:104-163`).
- `trcs_Soil2plant_uptake_col(idg,NY,NX)` -- plant uptake (delivered from `Plant_bgc`). Subtracted from the gas mass balance via `RGasNetProd_col(idg) -= trcs_Soil2plant_uptake_col(idg)` (`TranspNoSaltMod.F90:191`).

The overall gas conservation equation checked in `ExitMassCheck` (`TranspNoSaltMod.F90:186-197`):

```
(mass_now - mass_beg) = - SurfGasEmiss_flx_col       (to atmosphere)
                        - GasHydroLoss_flx_col       (hydrologic loss: drainage + runoff)
                        + RGasNetProd_col            (BGC net production - plant uptake)
                        + trcs_solml_drib_col        (numerical "dribble" from tiny-mass clipping)
```

Tolerance: absolute `|errmass| > 1e-4` AND relative `|errmass/delta| > 1e-3` triggers `endrun` (`TranspNoSaltMod.F90:286-288`). The diagnostic diffing block at lines 198-285 decomposes the miss into litter, snow, and soil components and writes to unit 121 so the failing tracer and pathway can be traced.

## Surface-flux outputs comparable to eddy-covariance

`SurfGasEmiss_flx_col(idg,NY,NX)` is the net hourly column-to-atmosphere flux and is assembled in `ExitMassCheck` (`TranspNoSaltMod.F90:164-165`) as:

```
SurfGasEmiss_flx_col = trcg_ebu_flx_col        (ebullition)
                     + GasDiff2Surf_flx_col    (molecular diffusion at surface)
                     + Gas_WetDeposit_flx_col  (wet deposition, sign convention aggregated)
```

For evaluation against eddy-covariance observations the relevant tracers are typically `idg_CO2`, `idg_CH4`, `idg_H2O` (water vapor is handled in HydroTherm, not here), and `idg_N2O`. `SurfGasEmiss_all_flx_col` additionally includes root disturbance losses (`Balances/RedistMod.F90:172-213`).
