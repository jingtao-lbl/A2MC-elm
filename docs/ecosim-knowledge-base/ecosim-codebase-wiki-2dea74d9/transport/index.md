---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/Transport/`
**Last verified:** 2026-04-24
---

# Transport subsystem overview

The `f90src/Transport/` tree handles 3-D fluxes of gases, non-salt solutes (including DOM and nutrients) and salt species through the soil-snow-litter column and across lateral grid boundaries. It consumes water and air-volume fields produced by `HydroTherm/` (see `WaterFlow2MicPM_3D`, `VLsoiAirPM_vr`, `VLWatMicPM_vr`), couples to biogeochemical source/sink terms produced by `Microbial_bgc/` and `Plant_bgc/`, and delivers column-level emissions, drainage and runoff fluxes that the Balances subsystem reconciles.

Transport is split into two sibling packages that share a common numerical style (upstream advection, concentration-gradient diffusion, macropore-micropore exchange, per-substep mass-balance checks) but differ in tracer set:

- `Nonsalt/` -- gases plus nutrient solutes and dissolved organic matter. Always active.
- `Salt/` -- aqueous salt ions and ion complexes (Al, Fe, H, Ca, Mg, Na, K, OH, SO4, Cl, plus AlOH_n, CaCO3, etc.). Active only when `salt_model` is true; see the driver sequence in `drivers/ecosim/EcoSIMAPI.F90:86-98`.

`TranspNoSalt` is invoked unconditionally once per hourly outer step; `TranspSalt` is called immediately afterward when salt chemistry is enabled (`drivers/ecosim/EcoSIMAPI.F90:94`).

## Source files

### `Nonsalt/` (5 files)

| File | Purpose |
|------|---------|
| `InitNoSaltTransportMod.F90` | Stages inputs at the start of each call: copies state into per-iteration buffers, zeros flux arrays, applies wet deposition to snow/litter (`SoluteWetDeposition`), pre-computes surface and soil flux terms (`StageSurfaceFluxes`, `StageSoilFluxes`) and copies results back at the end (`BackCopyStateVars`). |
| `TranspNoSaltDataMod.F90` | Module-level allocatable storage for the transport solver: per-iteration solute/gas/DOM copies (`trcs_solml2_vr`, `trcg_gasml2_vr`, `DOM_MicP2_vr`), transport-flux accumulators (`Gas_AdvDif_FlxMM_3D`, `trcs_MicpTranspFlxM_3D`), and BGC source/sink buffers (`RBGCSrcSoluteM_vr`, `RBGCSinkSoluteM_vr`). Also defines the solver constants `VFLWX=0.5` and `XFRS=0.05`. |
| `TranspNoSaltSlowMod.F90` | The "slow" loop at water-flux sub-hour cadence (`M=1..NPH`). Does the advection/dispersion of dissolved species in micropores and macropores, macropore-micropore exchange, snow-to-soil/litter drainage, surface runoff, lateral boundaries, and bubbling (`BubbleEffluxM`). |
| `TranspNoSaltFastMod.F90` | The "fast" loop inside each `M` step (`MM=1..NPT`). Does gas-phase diffusion + advection in soil air, gas dissolution/volatilization between air and water, and atmosphere-topsoil gas exchange. |
| `TranspNoSaltMod.F90` | Top-level driver `TranspNoSalt`: orchestrates initialization, the `NPH`-by-`NPT` nested loops, bubbling, back-copy, flux summaries, and wraps the whole call in an `EnterMassCheck`/`ExitMassCheck` pair that verifies per-column gas and solute conservation to ~1e-4 g d-2 absolute and 1e-3 relative tolerance. |

### `Salt/` (3 files, plus `TranspSaltDataMod`)

| File | Purpose |
|------|---------|
| `TranspSaltDataMod.F90` | Allocatable storage for salt transport: per-iteration salt copies (`trcSalt_solml2_vr`, `trcSalt_soHml2_vr`, `trcSalt_ml2_snvr`), 3-D mac/micro fluxes, snow-drift and runoff buffers, and geochemistry coupling term `trcSalt_RGeoChem_flxM_vr`. |
| `IngridTranspMod.F90` | The in-grid (micropore/macropore) and across-grid salt transport kernels. Provides both advection (upstream) and diffusion/dispersion in micropores and macropores, litter-to-soil exchange, snow-column drainage, snow drift, surface runoff and lateral boundary fluxes. |
| `TranspSaltMod.F90` | Top-level driver `TranspSalt`: `NPH` outer iterations with a Picard-style inner loop that reduces the step until `dpscal_max` drops below 1e-2, each pass re-calling `GetSaltTranspFlxM` (in `IngridTranspMod`) and re-updating concentrations. |

## Soil column vs lateral structure

Every inner kernel is parameterized on a pair of neighboring grid cells `(N3,N2,N1)` (source) and `(N6,N5,N4)` (destination) plus a direction index `N`:

- `N=1` (`iWestEastDirection`), `N=2` (`iNorthSouthDirection`) -- lateral flow.
- `N=3` (`iVerticalDirection`) -- vertical flow between adjacent soil layers.

Whether a direction is exercised depends on `FlowDirIndicator_col(NY,NX)`; column-mode runs (`column_mode=.true.`) suppress the lateral directions. This pattern is shared by both gas transport (`GasTransportMM`, `TranspNoSaltFastMod.F90:513`), micropore solute transport (`MicroporeSoluteAdvectionM`, `TranspNoSaltSlowMod.F90:2487`), macropore dispersion (`MacroporeSoluteDispersionM`, `TranspNoSaltSlowMod.F90:2280`), and salt transport (`SoluteAdvMicroporeM`, `Transport/Salt/IngridTranspMod.F90:1051`).

## Gas vs solute differences

| Aspect | Gas phase (`TranspNoSaltFast*`) | Aqueous phase (`TranspNoSaltSlow*`, `Salt`) |
|---|---|---|
| Substep | `MM=1..NPT` inside each `M` | `M=1..NPH` |
| Carrier | Soil air volume `VLsoiAirPM_vr` | Soil water volume `VLWatMicPM_vr`, `VLWatMacPM_vr` |
| Diffusion scaling | `POROQ * theta_a^2 / porosity` (air-filled), `GasDifctScaledMM_vr` | Tortuosity-reduced aqueous diffusivity + velocity-dependent dispersion `DISPN = DISP_3D * min(VFLWX, |q|/A)` |
| Surface BC | Atmospheric concentration + boundary-layer conductance `PARGas_CefMM` | Wet deposition (`TracerFall2Grnd`, `TracerFall2Snowpack`), runoff, drainage |
| Phase coupling | `GasDissolutionMM` (`TranspNoSaltFastMod.F90:545`) | Same routine, but in reverse (gas out of water) |

`NPH` and `NPT` are the number of hydrology and gas sub-iterations per hour (from `EcoSIMSolverPar`); the hourly time step is split into `NPH` water/solute steps, and each of those is split into `NPT` gas steps. The time fraction for gas-phase work is `dt_GasCyc=1/NPT` (`TranspNoSaltMod.F90:320`).

## Coupling with HydroTherm

Transport never computes water fluxes. It consumes fields written by `Watsub` in `HydroTherm/SoilPhys/WatsubMod.F90`:

- `WaterFlow2MicPM_3D(M,N,L,NY,NX)` -- net micropore water flux in direction `N`, used as carrier for advection.
- `WaterFlow2MacPM_3D(M,N,L,NY,NX)` -- corresponding macropore water flux.
- `VLWatMicPM_vr`, `VLWatMacPM_vr`, `VLsoiAirPM_vr` -- time-resolved pore volumes for concentration calculations.
- `CondGasXSnowM_col(M,NY,NX)` -- atmospheric boundary-layer gas conductance, scaled per tracer in `TranspNoSaltMod.F90:395-403`.

For each gas tracer, the per-tracer diffusion coefficient is obtained by multiplying `PARGM` by a molecular-diffusivity ratio relative to a reference (CO2: 0.74, CH4: 1.04, O2: 0.83, N2: 0.86, N2O: 0.74, NH3: 1.02, H2: 2.08, Ar: 0.72, see `TranspNoSaltMod.F90:396-403`). These ratios reflect molecular-mass differences in free-air diffusion.

## Mass balance, non-negativity, and limiter passes

Both drivers run an internal Picard-style limiter loop (`while dpscal_max > 1e-2 ...`, `TranspNoSaltSlowMod.F90:63`, `TranspSaltMod.F90:70`) that shrinks computed fluxes when they would otherwise drive a concentration negative. Helper function `flux_mass_limiter` (from `MiniMathMod`) is applied per-tracer.

Bubble efflux (`BubbleEffluxM`, `TranspNoSaltSlowMod.F90:2725`) is optional (`ldo_transpt_bubbling`) and runs once per `M` step. It sweeps upward from the first unfrozen layer (`NLF_col`), releases total aqueous gas that exceeds the saturation pressure `P_atm + rho*g*h_pond`, and either emits to atmosphere (surface layer / below water table) or deposits in the next overlying gas-phase layer for further vertical transport.

## Navigation

- [`gas_transport.md`](gas_transport.md) -- Gas-phase transport: diffusion form, tracer list, surface exchange, bubbling, and coupling with microbial/plant sources.
- [`solute_transport.md`](solute_transport.md) -- Aqueous transport: advection-dispersion, tracers, numerical scheme, macropore-micropore exchange, and BGC source/sink coupling.
