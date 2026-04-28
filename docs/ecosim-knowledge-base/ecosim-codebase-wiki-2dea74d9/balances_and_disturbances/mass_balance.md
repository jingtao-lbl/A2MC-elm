---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/Balances/`
**Last verified:** 2026-04-24
---

# Mass balance and state redistribution (`Balances/`)

The Balances subsystem has seven F90 modules. Four are direct bookkeeping (redistribution, lateral inter-grid flow, runoff, erosion accounting), two are soil-geometry updates (layer dynamics, tillage mixing), and one is a thin data module for shared arrays.

## Source files

| File | Key public subroutines | Role |
|------|------------------------|------|
| `RedistDataMod.F90` | (data-only module, no subroutines) | Allocatable arrays used across the Balances modules: `trcs_TransptMicP_vr`, `trcs_TransptMacP_vr`, `trcSalt_Flo2MicP_vr`, `trcg_SurfRunoff_flx`, `Gas_AdvDif_Flx_vr`, sediment-loss trackers (`TSandErosed_col`, etc.), DOM transport buffers (`DOM_Transp2Micp_vr`, `DOM_SurfRunoff_flx`) and layer freeze-thaw deltas (`WatIceThawMicP_vr`, `DVLiceMicP_vr`). |
| `RedistMod.F90` | `redist` (line 75), `InitRedist` (line 62), `UpdateOutputVars` (line 159), `SoilErosion` (line 559), `UpdateChemInSoilLays` (line 894), `SumMicBGCFluxes` (line 1453), `AddFlux2SurfaceResidue` (line 1304), `UpdateTSoilVSMProfile` (line 774), `LitterLayerSummary` (line 667) | End-of-step state update: takes all sub-hourly fluxes accumulated by transport and biology, applies them to the canonical state arrays, and drives erosion accounting and tillage mixing. |
| `LateralTranspMod.F90` | `XGridTranspt` (line 39), `FlowXGrids` (line 372), `SumSedmentTranspFlux` (line 149) | Sums the directional (W-E, N-S, vertical, mirrored) flux components into a single per-cell net flux for water, heat, solutes and sediments. Also sums freeze-thaw rates into net phase-change arrays. |
| `RunoffBalMod.F90` | `XGridBoundSolutesRunoff` (line 31), `XBoundarySurfRunoffs` (line 121), `XBoundarySubSurfRunoffs` (line 406), `WaterHeatSoluteBySnowDrift` (line 628) | Diagnoses solute losses across the landscape boundary (N/W/S/E and bottom drainage). Provides backstop accounting for solutes leaving the modeled domain, now largely integrated into the transport code. Currently disabled at the call site (`RedistMod.F90:118`, comment "will be removed in the future"). |
| `ErosionBalMod.F90` | `SinkSediments` (line 28), `ZeroErosionArray` (line 207) | Sediment pond-sinking dynamics: moves dissolved and solid C/N/P and microbial residues from a pond/water column down into the sediment layer at rate `VLS_col / DLYR`. |
| `TillageMixMod.F90` | `ApplyTillageMixing` (line 36), `MixSoluteMacpore` (line 361), `Mix1D`/`Mix2D`/`Mix3D`/`Mix4D` (lines 381-596), `DeriveTillageProf` (line 597) | Implements tillage mixing: homogenizes SOM, litter, solutes, minerals, heat and water within a tillage depth, weighted by the tillage intensity `DCORP`. |
| `SoilLayerDynMod.F90` | `UpdateSoilGrids` (line 63), `UpdateLayerEdges` (line 607), `FreezeThawSoilEdgeChange` (line 462), `ErosionSoilEdgeChange` (line 419), `SOMBGCSoilEdgeChange` (line 359), `ComputePondEdgeChange` (line 534), `UpdateLayerMaterials` (line 1056), `MoveSOM` (line 1456), `MoveHeatWat` (line 2003), `MoveBandSolute` (line 1714), `MoveFertMinerals` (line 1857) | Dynamic re-layering of the soil profile. Handles layer growth/shrinkage from freeze-thaw, erosion, and SOM buildup or decomposition; moves mass and heat between the redefined layers; manages pond emergence and submergence. |

## What gets balance-checked

The Balances subsystem does not itself run the end-of-step conservation check, but it produces the state values that the check reads. The per-step mass-conservation *checks* live in two places:

1. **Inside transport**, per-substep: `EnterMassCheck`/`ExitMassCheck` pairs in `TranspNoSaltMod.F90:65-293`, `TranspNoSaltSlowMod.F90:165-466`, `TranspNoSaltFastMod.F90:133-247`. These check gas and solute conservation for each hydrology substep and for the whole column, tracer by tracer.

2. **Hourly global**, in `f90src/ModelDiags/BalancesMod.F90`:
   - `BegCheckBalances` (line 37) -- called at the start of each hour from `Modelforc/Hour1Mod.F90:151`; snapshots: `WatMass_col`, `HeatStore_col`, `SnowEngyEnd_col`, `CanopyWaterMassEnd_col`, `SnowMassEnd_col`, `LitWatMassEnd_col`, `SoilWatMassEnd_col`, and per-tracer `trcg_TotalMass_col`, `trcg_soilMass_col`, `trcg_snowMass_col`, `trcg_rootMass_col`, `trcs_solml_dribBeg_col`.
   - `EndCheckBalances` (line 170) -- called at the end of each hour from `drivers/ecosim/EcoSIMAPI.F90:119`; recomputes the same quantities and compares them against the snapshot plus the hourly-aggregated inbound/outbound fluxes.

### Variables checked

Per column `(NY, NX)`, every hour:

| Category | Variables |
|----------|-----------|
| Water | `WatMass_col` (total column), `SnowMassEnd_col`, `LitWatMassEnd_col`, `SoilWatMassEnd_col`, `CanopyWaterMassEnd_col` |
| Heat / energy | `HeatStore_col`, `SnowEngyEnd_col` |
| Gas (per `idg`) | `trcg_TotalMass_col`, `trcg_soilMass_col`, `trcg_snowMass_col`, `trcg_rootMass_col` |
| Solutes (per `ids`) | `trcs_solml_drib_vr` dribble (numerical-clipping buffer, summed from `L=0` litter plus `NU_col..NL_col`) |
| Ebullition cumulative error | `trcg_mass_cumerr_col` |

No dedicated mass-balance check for soil-phase (solid) C, N, P exists at the hour-end global level; these are checked inside transport's ExitMassCheck for the dissolved phases, and the Balances path (specifically `RedistMod.F90:894-1133`, `UpdateChemInSoilLays`) is the single writer that updates solid-phase SOM/CNP arrays. Conservation there is enforced by construction (e.g., `sumORGMLayL` summed before and after in `TillageMixMod` mixing routines).

### Per-cell vs per-domain granularity

Per-cell: gas and solute mass-balance checks are cell-by-cell (`ExitMassCheck` loops `NX=NHW,NHE`, `NY=NVN,NVS` and reports per-`(NY,NX)`). Water and heat balance are also per-column. Tracer "dribble" buffers are per-cell, per-layer, so a conservation miss can be attributed to a specific column and layer.

Per-domain: lateral boundary fluxes (`trcs_SubsurTransp_flx_2DH`, runoff losses) are accumulated at boundary cells but summed into landscape totals in `EcoSimSumDataType` (e.g., `SurfGas_lnd(idg)` in `RedistMod.F90:213`).

## Tolerances and failure behavior

From `TranspNoSaltMod.F90:198, 286-288` for gas and solute per-substep checks:

```
if ( |errmass| > 1.e-4 .and. |safe_adb(errmass, delta_mass)| > 1.e-3 ) &
  call endrun(trim(mod_filename)//' at line', __LINE__)
```

Both conditions must fail -- an absolute miss above 1e-4 g d-2 AND a relative miss above 1e-3 of the change in mass. The routine writes a full decomposition of the miss across litter, snow, and soil sub-balances to file unit 121 before aborting. The decomposition separates each inbound and outbound flux pathway (wet deposition, snow-to-litter, surface runoff, lateral subsurface loss, drainage, BGC net production, plant uptake) so the offending physics module can be isolated.

`EndCheckBalances` in `ModelDiags/BalancesMod.F90` has more lenient default tolerances and can be configured via `iVerbLevel`. Its failures typically print diagnostics but do not abort by default.

## Where in the time loop

The hourly call sequence in `drivers/ecosim/EcoSIMAPI.F90:35-122` (each line prefixed by its file position):

```
Hour1Mod.F90:151         BegCheckBalances         (start-of-hour snapshot)
EcoSIMAPI.F90:47         HOUR1                    (surface energy/water)
EcoSIMAPI.F90:54         WATSUB                   (soil H & W flux rates)
EcoSIMAPI.F90:61         MicrobeModel             (BGC rates)
EcoSIMAPI.F90:69         PlantModel               (plant physiology, uptake)
EcoSIMAPI.F90:78         soluteModel              (aqueous equilibria)
EcoSIMAPI.F90:87         TranspNoSalt             (transport, Enter/ExitMassCheck per substep)
EcoSIMAPI.F90:96         TranspSalt               (salt transport, conditional)
EcoSIMAPI.F90:106        EROSION                  (sediment detachment/transport)
EcoSIMAPI.F90:113        REDIST                   (end-of-hour state update)
EcoSIMAPI.F90:119        EndCheckBalances         (end-of-hour global check)
```

`redist` (`RedistMod.F90:75-155`) itself calls, in order, per column: `AddFlux2SurfaceResidue`, `SinkSediments`, `ModifyExWTBLByDisturbance`, `XGridTranspt` (from `LateralTranspMod`), `SnowMassUpdate`, `HandleSurfaceBoundary`, `SoilErosion`, `DiagSnowChemMass`, `LitterLayerSummary`, `UpdateTSoilVSMProfile`, `UpdateChemInSoilLays`, `SnowpackLayering`, `UpdateSoilGrids` (from `SoilLayerDynMod`), and `UpdateOutputVars` (which invokes `ApplyTillageMixing` from `TillageMixMod`). This fixed sequence is the canonical end-of-hour state-update order.

## Redistribution mechanics

`redist` accepts no fluxes explicitly -- all sources are the per-substep accumulators written by the preceding transport and biology calls (e.g., `Gas_AdvDif_Flx_vr`, `trcs_TransptMicP_vr`, `RGasNetProd_col`, `DOM_Transp2Micp_vr`, `trcg_root_vr`). For each column it:

1. Sums sub-hour surface fluxes onto the surface residue inventory (`AddFlux2SurfaceResidue`, `RedistMod.F90:1304-1367`).
2. Sinks suspended sediment into the underlying sediment layer when a pond layer exists (`SinkSediments`, `ErosionBalMod.F90:28-206`; rate `FSINK = min(1, VLS_col/DLYR)`).
3. Applies adjustments for disturbance-modified water-table depth (`ModifyExWTBLByDisturbance`, `RedistMod.F90:277-341`).
4. Runs `XGridTranspt` (`LateralTranspMod.F90:39-105`), which loops over each layer and direction (West-East, North-South, vertical) and sums contributing directional fluxes into net water, heat, solute and sediment cell rates.
5. Applies snow-pack updates.
6. Handles surface boundary (precipitation inputs, evaporation losses not already reconciled by HydroTherm).
7. Does `SoilErosion` (`RedistMod.F90:559-666`): erosion sediment transport accounting, analogous to `SinkSediments` but for the mineral column.
8. Computes litter layer summaries and profile averages.
9. `UpdateChemInSoilLays` (`RedistMod.F90:894-1133`): the big per-layer update that applies net transport + BGC + disturbance deltas to `trcs_solml_vr`, `trcg_gasml_vr`, `trcs_soHml_vr`, DOM arrays, and solid SOM.
10. Runs snow layering and soil layering dynamics.
11. `UpdateOutputVars` aggregates diagnostics for output and -- the key line -- calls `ApplyTillageMixing` (`RedistMod.F90:251`, inside `UpdateOutputVars`) when the management stream triggers tillage.

## Soil-layer dynamics

`SoilLayerDynMod.F90` exists because the soil profile is not static. Five change modes are tracked via flags `IFLGL(:,ich_*)`:

| Mode | Constant | Trigger |
|------|----------|---------|
| Water-level change | `ich_watlev = 1` | External water table rises or falls past a layer edge |
| Top layer shrinkage | `iTopLayShrink = 2` | Erosion or combustion removes surface material |
| Top layer growth | `iTopLayGrow = 3` | Sedimentation, litter buildup |
| Freeze-thaw | `ich_frzthaw = 4` | Phase change at a layer boundary |
| Erosion | `ich_erosion = 5` | Overland flow + bank erosion |
| SOM BGC | `ich_sombgc = 6` | Net C loss or gain from microbial decomposition |

`UpdateSoilGrids` (`SoilLayerDynMod.F90:63-248`) sets these flags, updates layer edges (`UpdateLayerEdges`), moves SOM (`MoveSOM`), macropore solutes (`MoveMacPoreSolute`), banded solutes (`MoveBandSolute`), fertilizer salts (`MoveFertSalt`), fertilizer minerals (`MoveFertMinerals`), and heat + water (`MoveHeatWat`) between the redefined layers. The whole pathway early-returns if `erosion_model` is false (line 99).

## Tillage mixing

`ApplyTillageMixing` (`TillageMixMod.F90:36-360`) is triggered by `iSoilDisturbType_col(I,NY,NX) <= 20` (see `SoilDisturbMod.F90:43` which defines 1-20 as tillage, 21 = litter removal, 22 = fire, 23-24 = drainage). Implementation:

1. Compute per-layer mixing fraction `FI(L)` and cumulative depth `TI(L)` from the tillage depth profile (`DeriveTillageProf`, line 597).
2. Apply the mixing to a series of state variables by dimensionality:
   - `Mix1D` -- layer-only arrays: water content, heat capacity, etc.
   - `Mix2D` -- arrays with one extra index (SOM element `NumPlantChemElms`, tracer `ids`, etc.)
   - `Mix3D`, `Mix4D` -- higher-dimensional (e.g., microbial biomass per guild × component × layer).
3. Mixing preserves the domain sum within each call (by construction: `out = FI*layer_mean + (1-FI)*layer_self`, with `sum_layer(FI*(layer_mean - layer_self)) == 0`).

The `XCORP0` factor (retained fraction) lets the mixing be partial. Called from `RedistMod.F90:251`, once per column per hour.

## Erosion sediment bookkeeping

`SinkSediments` (`ErosionBalMod.F90:28-206`) moves suspended C, N, P and microbial residues from a pond/water cell down to the underlying sediment cell at rate `FSINK = min(1, VLS_col/DLYR)`. Applies to every solid-phase pool:
soil minerals (sand, silt, clay, CEC, AEC), SOM (by element, microbial complex, and guild: OMC, OMN, OMP, ORC, ORN, ORP, OHC, OHN, OHP, OHA, OSC, OSA, OSN, OSP), and living microbial biomass. `LateralTranspMod::SumSedmentTranspFlux` (line 149) sums the directional erosion fluxes into the net per-cell sediment flux that `SoilErosion` later integrates.

## What is NOT here

- The *rates* of erosion, tillage, fire, etc. are computed in `Disturbances/`, not Balances. Balances receives them as flux arrays and applies them.
- The end-of-hour global balance check lives in `ModelDiags/BalancesMod.F90`, outside this subsystem, because it synthesizes results from transport, HydroTherm, plant, and soil-BGC subsystems together.
- Water flux *computation* lives in `HydroTherm/`; Balances only redistributes the transported mass.
