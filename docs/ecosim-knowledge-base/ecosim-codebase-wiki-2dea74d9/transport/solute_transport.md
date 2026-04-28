---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/Transport/Nonsalt/` (solute portion) and `f90src/Transport/Salt/`
**Last verified:** 2026-04-24
---

# Solute transport

Aqueous (solute) transport handles dissolved nutrients, DOM, dissolved gases, and -- when `salt_model=.true.` -- aqueous salt ions and ion complexes. It is driven at the hydrology substep cadence (`M=1..NPH`) from two parallel solvers that share most numerical structure:

- Non-salt solutes and DOM: `Transport/Nonsalt/TranspNoSaltSlowMod.F90`, driven by `TransptSlowNoSaltM` (line 42).
- Salt ions: `Transport/Salt/IngridTranspMod.F90`, driven by `GetSaltTranspFlxM` (line 28) from `TranspSaltMod.F90`.

Within each substep the solvers run a Picard-style iteration (up to 3 passes for non-salt; unbounded for salt) that re-scales fluxes that would drive a concentration negative.

## Files

### Non-salt (solutes + DOM)

| File | Key subroutines | Purpose |
|------|-----------------|---------|
| `Transport/Nonsalt/TranspNoSaltSlowMod.F90` | `TransptSlowNoSaltM` (line 42), `MicroporeSoluteAdvectionM` (line 2487), `MicroporeSoluteDiffusionM` (line 1960), `MacroporeSoluteAdvectionM` (line 2169), `MacroporeSoluteDispersionM` (line 2280), `MicMacPoresSoluteAdvExchM` (line 2579), `MicMacPoresSoluteDifExchM` (line 2667), `SnowSoluteVertDrainM` (line 1820), `SurfaceSoluteFluxM` (line 1185), `TracerXBoundariesM` (line 3165), `ApplySlowSourceSink` (line 104) | Core solver: advection, diffusion, dispersion, and mac-micro exchange in micropore and macropore |
| `Transport/Nonsalt/InitNoSaltTransportMod.F90` | `InitTranspNoSaltModel`, `SoluteWetDeposition`, `TracerFall2Snowpack`, `TracerFall2Grnd` | Wet-deposition BC, per-step staging |

### Salt

| File | Key subroutines | Purpose |
|------|-----------------|---------|
| `Transport/Salt/IngridTranspMod.F90` | `GetSaltTranspFlxM` (line 28), `SoluteAdvMicroporeM` (line 1051), `SoluteDifsMicroporeM` (line 1108), `SoluteAdvMacroporeM` (line 1237), `SoluteDifsMacroporeM` (line 1328), `MicPoreSaltAdvExM` (line 812), `MacPoreSaltAdvExM` (line 775), `MacMicPoreSaltDifusExM` (line 850), `SnowSaltTranptM` (line 524), `SurfaceSaltFluxM` (line 50), `SaltSurfRofM` (line 920), `SaltXGridBoundTransptM` (line 136) | Salt-specific variants of the above kernels |
| `Transport/Salt/TranspSaltMod.F90` | `TranspSalt` (line 41), `UpdateSaltTranspM`, `AccumSaltFluxesM` | Top-level driver |

## Tracers

### Non-salt solutes (`ids_beg:ids_end`)

Declared in `f90src/Modelconfig/TracerIDMod.F90:178-204`. Indices are assigned at init time (`addone` pattern), so names rather than numeric IDs are load-bearing:

| Name | Purpose | Banded counterpart |
|------|---------|--------------------|
| `idg_CO2` / `idg_CH4` / `idg_O2` / `idg_N2` / `idg_N2O` / `idg_H2` / `idg_AR` | Dissolved gases (aqueous phase of the same species that `gas_transport.md` transports in air) | -- |
| `idg_NH3` / `idg_NH3B` | Aqueous ammonia / banded-zone aqueous ammonia | pair |
| `ids_NH4` / `ids_NH4B` | Ammonium | banded |
| `ids_NO3` / `ids_NO3B` | Nitrate | banded |
| `ids_NO2` / `ids_NO2B` | Nitrite | banded |
| `ids_H1PO4` / `ids_H1PO4B` | HPO4-2 | banded |
| `ids_H2PO4` / `ids_H2PO4B` | H2PO4- | banded |

The banded/non-banded split reflects fertilizer banding: volumes `trcs_VLN_vr(ids,L,NY,NX)` partition the soil layer between the band and the bulk, and every advection/diffusion kernel operates on the banded and bulk pore volumes separately (e.g., `VLWatMicPMA_vr` vs `VLWatMicPMB_vr`, set in `TranspNoSaltMod.F90:411-416`).

### DOM (`idom_beg:idom_end`)

From `TracerIDMod.F90:229-233`:

| Name | Species |
|------|---------|
| `idom_DOC` | Dissolved organic carbon |
| `idom_DON` | Dissolved organic nitrogen |
| `idom_DOP` | Dissolved organic phosphorus |
| `idom_acetate` | Acetate |

DOM is also indexed over litter/SOM complexes (`K=1..jcplx`) so the full state shape is `DOM_MicP2_vr(idom,K,L,NY,NX)`.

### Salt (`idsalt_beg:idsaltb_end`)

From `TracerIDMod.F90:41-80`. Free ions: Al, Fe, H+, Ca, Mg, Na, K, OH, SO4, Cl. Complexes: AlOH, AlOH2, AlOH3, AlOH4, AlSO4, FeOH, FeOH2, FeOH3, FeOH4, FeSO4, CaOH, CaCO3, CaHCO3, CaSO4, MgOH2, MgCO3, MgHCO3, MgSO4, NaCO3, etc. Banded (`idsalt_*B` or indexed ranges `idsalt_pband_beg:idsalt_pband_end`) and non-banded (`idsalt_psoil_beg:idsalt_psoil_end`) phosphate salts are tracked separately.

## Numerical scheme

### Upstream (upwind) advection in micropore

`MicroporeSoluteAdvectionM` (`TranspNoSaltSlowMod.F90:2487-2548`) and its salt analog `SoluteAdvMicroporeM` (`IngridTranspMod.F90:1051-1106`) are textbook first-order upwind:

```
if WaterFlow2MicPM_3D(M,N,dest) > 0          ! water from src -> dest
  VFLW = max(0, min( VFLWX, FLQW / V_w(src) ))
  flux = VFLW * max(0, C_src)                 ! upstream concentration
else
  VFLW = min(0, max(-VFLWX, FLQW / V_w(dest) ))
  flux = VFLW * max(0, C_dest)
endif
```

The Courant-like cap `VFLWX = 0.5` (`TranspNoSaltDataMod.F90:11`, `TranspSaltDataMod.F90:12`) limits per-step transported mass to half the source-cell inventory; a negative concentration is clipped to zero via `AZMAX1`, so the scheme is strictly non-negative and monotonic per substep.

For banded phosphate tracers, the advective flux is additionally multiplied by `trcs_VLN_vr(ids_H1PO4,L,NY,NX)` (or `ids_H1PO4B`) so that mass is carried in the appropriate pore subvolume (`IngridTranspMod.F90:1075-1080`).

### Diffusion + dispersion

Diffusion in micropores (`MicroporeSoluteDiffusionM`, `TranspNoSaltSlowMod.F90:1960`; `SoluteDifsMicroporeM`, `IngridTranspMod.F90:1108`) uses a Fickian form scaled by a tortuosity factor:

```
DISPN = DISP_3D(N,dest) * min( VFLWX, |q| / A )                     (line 2118)
SDifc(ids) = ( SoluteDifusivitytscaledM_vr(ids,dest) * TORTL + DISPN ) * XDPTH_3D(N,dest)
flux = SDifc(ids) * ( C_src - C_dest )                              (line 2125)
```

The `DISPN` term is a flow-velocity-dependent longitudinal dispersion term (linear in the interstitial velocity, standard Bear formulation). The combined coefficient `SoluteDifusivitytscaledM * TORTL + DISPN` has units consistent with a dispersion coefficient [m2 h-1]; `TORTL` is the Millington-style tortuosity reduction from aqueous to bulk diffusivity. The same structure is used for macropore dispersion (`MacroporeSoluteDispersionM`, `TranspNoSaltSlowMod.F90:2280-2485`; `SoluteDifsMacroporeM`, `IngridTranspMod.F90:1328`), differing only in which pore volume and water flux carry the signal.

### Operator splitting

Within each hydrology substep `M`, the solve is sequenced (`TransptSlowNoSaltM`, `TranspNoSaltSlowMod.F90:61-97`):

1. `StageSlowTranspIterationM` -- snapshot pre-step state.
2. `ZeroFluxesM` -- zero per-iteration flux accumulators.
3. `SnowSoluteVertDrainM` -- top-of-column snow drainage.
4. `SurfaceSoluteFluxM` -- wet deposition, litter-to-topsoil, runoff losses.
5. `TracerXBoundariesM` -- lateral external boundary fluxes (runoff out of landscape edges).
6. `TracerXInterGridsM` -- in-grid pair transport (combines advection + diffusion + mac-mic exchange).
7. `GatherTranspFluxM` -- sum 3-D directional fluxes into a single per-cell net flux.
8. `SlowUpdateStateVarsM` -- apply net flux to `trcs_solml2_vr` with per-tracer `pscal(ids)` limiter.
9. `AccumSlowFluxesM` -- accumulate substep fluxes into hourly totals, also tracking `pscal1_dom` for DOM.

The Picard loop at line 63 repeats steps 2-9 up to 3 times with shrinking `dpscal(ids) *= (1 - pscal(ids))` until `dpscal_max <= 1e-2`. Step 6 in turn calls `MicroporeSoluteAdvectionM`, `MicroporeSoluteDiffusionM`, `MacroporeSoluteAdvectionM`, `MacroporeSoluteDispersionM`, `MicMacPoresSoluteAdvExchM`, and `MicMacPoresSoluteDifExchM` in sequence (advection then diffusion then mac-mic exchange), a first-order operator-splitting pattern.

The salt solver uses the same structure but with a `do-while` Picard loop that iterates until convergence (`TranspSaltMod.F90:70-87`).

## Macropore-micropore exchange

Separate from vertical/lateral transport, each soil layer has both micropore and macropore solute inventories (`trcs_solml_vr` vs `trcs_soHml_vr`). Exchange between them occurs via two mechanisms:

- Advective (`MicMacPoresSoluteAdvExchM`, `TranspNoSaltSlowMod.F90:2579-2666`): driven by `FWatExMacP2MicPM_vr` computed in `HydroTherm/SoilPhys/WatsubMod.F90`.
- Diffusive (`MicMacPoresSoluteDifExchM`, `TranspNoSaltSlowMod.F90:2667-2723`): equilibration of concentrations between the two pore classes within a layer.

Salt analogs: `MicPoreSaltAdvExM`, `MacPoreSaltAdvExM`, `MacMicPoreSaltDifusExM` in `IngridTranspMod.F90:775-891`.

## BGC source/sink coupling

### Applied inside `TransptSlowNoSaltM`

`ApplySlowSourceSink` (`TranspNoSaltSlowMod.F90:104-163`) applies non-gas solute and DOM net BGC rates after transport:

- `RBGCSrcSoluteM_vr(ids,L)` -- production rate (mineralization, nitrification, dissolution).
- `RBGCSinkSoluteM_vr(ids,L)` -- consumption rate (plant uptake from `Plant_bgc`, microbial immobilization from `Microbial_bgc`, precipitation to solid).
- `RBGCSink_DOM_micpM_vr(idom,K,L)` -- DOM sinks (decomposition by microbes).
- The difference `source - sink` accumulates into `trcs_NetProd_slow_flxM_col` and `trcs_netProd_lit_col` for the slow mass check.

The "dribble" arrays (`trcs_solml_drib_vr`, `DOM_MicP_drib_vr`) are numerical buffers for tiny-mass clipping: when `SubstrateDribbling` (`MiniMathMod`) detects that applying a sink would drive a concentration below a tolerance, the residual is stored here and repaid to the balance equation on the next substep.

### Couplings

| Process | Source variables | Set in |
|---------|-----------------|--------|
| Plant uptake of NH4, NO3, H1PO4, H2PO4 | `trcs_Soil2plant_uptake_col` | `Plant_bgc/` (root uptake) |
| Microbial mineralization of DON/DOP | `RBGCSrcSoluteM_vr` for `ids_NH4`, `ids_H1PO4` | `Microbial_bgc/` |
| Nitrification | `RBGCSrcSoluteM_vr` for `ids_NO3`, sink for `ids_NH4` | `Microbial_bgc/` |
| Denitrification | Sink for `ids_NO3`, source for aqueous `idg_N2O`, `idg_N2` | `Microbial_bgc/` |
| Geochemistry (sorption, precipitation, speciation) | `trcSalt_RGeoChem_flxM_vr` for salt tracers; equivalent aqueous-equilibrium rates for non-salt | `Geochem/` (`soluteModel`, called in `EcoSIMAPI.F90:76-80` before `TranspNoSalt`) |

The call order in the hourly time step matters: `MicrobeModel` and `PlantModel` set source/sink terms first, `soluteModel` enforces aqueous-phase equilibria (salt tracer form, for example), and then `TranspNoSalt` (followed by `TranspSalt`) moves mass between cells. After transport, `redist` (see [balances_and_disturbances/mass_balance.md](../balances_and_disturbances/mass_balance.md)) writes the final state and diagnostic summaries.

## Boundary conditions

- **Surface (atmosphere → top soil)**: wet deposition through `SoluteWetDeposition`/`TracerFall2Snowpack`/`TracerFall2Grnd` (`InitNoSaltTransportMod.F90:88-120`). Dry deposition is routed through gas transport; dissolved-phase inputs enter the top soil micropore.
- **Litter layer (`L=0`)**: a pseudo-layer with its own `trcs_solml_vr(ids,0,NY,NX)` inventory. Coupled to layer 1 (`NU_col`) via `Lit2SoilTracerAdvectM` and `LitterSoilTracerDiffusionM` (`TranspNoSaltSlowMod.F90:1383, 1457`).
- **Lateral boundaries**: `TracerXBoundariesM` (`TranspNoSaltSlowMod.F90:3165`) and `SaltXGridBoundTransptM` (`IngridTranspMod.F90:136`) export tracers out of the landscape edge to runoff or an external boundary reservoir, conditional on `FlowDirIndicator_col` and user-specified boundary modes `RCHQF`.
- **Bottom drainage**: accumulated into `trcs_drainage_flx_col` (tracked in `ExitMassCheck`). The deepest layer's downward water flux times its solute concentration is written out to the mass balance as `soil2drainage`.
- **Snow column**: solutes in snow are handled in `TranspNoSaltSlowMod.F90:1742-1930` (`TracerFlowThruSnowRedist`, `SnowSoluteVertDrainM`) and in `IngridTranspMod.F90:524-607` (`SnowSaltTranptM`).

## Mass balance

The non-salt slow-loop balance is checked per `M` in `ExitMassCheck` (`TranspNoSaltSlowMod.F90:263-466`). The overall check wraps all `NPH` substeps in the outer `TranspNoSalt` routine's `EnterMassCheck`/`ExitMassCheck` pair (see `gas_transport.md` for the gas-phase statement; the solute statement adds `trcs_drainage_flx_col`, `trcs_SubsurTransp_flx_2DH` for lateral loss, and `trcs_irrig_flx_col` for irrigation inputs). Tolerance is the same 1e-4 absolute / 1e-3 relative threshold.

DOM has its own `TranspNetDOM_flx_col` accumulators and its own miss decomposition in the same routine, isolating DOM transport errors from mineral-solute errors.

## References

- Upstream/upwind advection: Patankar (1980) *Numerical Heat Transfer and Fluid Flow*, Ch. 5.
- Hydrodynamic dispersion form `D_eff = D_m * tau + alpha * v`: Bear (1972) *Dynamics of Fluids in Porous Media*, Eq. 10.5.15.
- Millington-Quirk tortuosity: Millington (1959) *Science* 130:100-102, as used for `POROQ = 2/3` effective exponent.
