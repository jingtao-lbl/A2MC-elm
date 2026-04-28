---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/{Microbial_bgc, Geochem}/`
**Last verified:** 2026-04-24
---

# Geochemistry Subsystem

The EcoSIM geochemistry subsystem computes abiotic solute equilibria, surface sorption/exchange, mineral precipitation/dissolution, and fertilizer band dynamics at each soil layer at each time step. It runs *after* microbial biogeochemistry within a time step and feeds the chemical reaction sources `trcn_RprodChem_soil_vr`, `trcx_TRSoilChem_vr`, `trcp_RChem_soil_vr`, and `trcSalt_RGeoChem_flx_vr` that the transport module then diffuses and advects.

Source code lives in two sub-directories under `f90src/Geochem/`:

- `Box_chem/` is the per-layer ("box") equilibrium solver and initial condition setup.
- `Layers_chem/` handles multi-layer fertilizer band tracking, urea hydrolysis, and the layer-loop driver.

## Source files

### `f90src/Geochem/Box_chem/`

| File | Role |
|---|---|
| `ChemEquilibriaMod.F90` | Reduced-chemistry solver `NoSaltChemEquilibria` used when `salt_model = .false.`. Solves only the phosphorus and co-reactant subset (P precipitation-dissolution, P anion exchange, H2PO4-HPO4 dissociation, simplified cation exchange) with prescribed pH. Reference: Grant and Heaney (1997). |
| `SaltChemEquilibriaMod.F90` | Full salt-chemistry solver `SaltChemEquilibria` used when `salt_model = .true.`. Solves gibbsite/Fe(OH)3/calcite/gypsum precipitation, complete P mineral set, cation exchange (Gapon), anion exchange, solute dissociations, and ion activity corrections in a fixed-point iteration (`MRXN` passes). |
| `InitSoluteMod.F90` | Initial-condition setup: partitions bulk soil ion pools into aqueous/sorbed/precipitated phases, initial equilibrium solve (`InitEquilibria`, `SolubilityEquilibiriaSalt`, `SolubilityEquilibriaNoSalt`), and fixes `trcSaltIonNumber` for ion counting. |
| `SoluteChemDataType.F90` | Derived types `chem_var_type` (input state) and `solute_flx_type` (output fluxes). All per-layer chemistry is carried on these two bags rather than on grid arrays, enabling the loop-body to be grid-independent. |
| `GeoChemMathMod.F90` | Two reusable helpers for chemical reaction flux calculation: `A2BC_ChemReact_Quad` (exact quadratic solution for A <-> B + C) and `A2BC_ChemReact_Grad` (linearized gradient form). |

### `f90src/Geochem/Layers_chem/`

| File | Role |
|---|---|
| `SoluteMod.F90` | Multi-layer driver and fertilizer band state management. `GeoChemEquilibria` dispatches to salt or no-salt branch. `UpdateSoilFertlizer` applies dissolution of broadcast and banded NH4/NH3/urea/NO3/PO4 fertilizer. `UpdateFertilizerBand` diffuses band widths and depths. `UreaHydrolysis` handles microbe-catalyzed urea -> NH3 conversion. `UpdateSurfResidueSolute` applies the surface residue (litter) chemistry. |

## Entry point

The calling sequence is driven from `f90src/APIs/GeochemAPI.F90`.

- Public routine `soluteModel(I,J,NHW,NHE,NVN,NVS)` is the external entry used by the time-stepper (`f90src/APIs/GeochemAPI.F90:23`). It zeros the `chemvar` bag (`GeochemAPI.F90:40-91`), then loops over grid columns and layers.
- Per-layer within the loop (`GeochemAPI.F90:97-141`):
  1. `UpdateSoilFertlizer(I,J,L,NY,NX,chemvar)` applies fertilizer dissolution and populates fertilizer-driven mineral pool changes.
  2. `GeochemAPISend(L,NY,NX,chemvar,solflx)` packs grid state into `chemvar` (`GeochemAPI.F90:154-256`), including CEC, AEC, Gapon selectivity coefficients, ion masses, precipitate masses, and the salt-model ion pool if active.
  3. `GeoChemEquilibria(I,J,L,NY,NX,chemvar,solflx)` dispatches to `SaltChemEquilibria` or `NoSaltChemEquilibria` based on the `salt_model` flag (`SoluteMod.F90:50-54`).
  4. `GeochemAPIRecv(L,NY,NX,solflx)` unpacks computed fluxes back to the grid arrays in moles, then applies `catomw`/`natomw`/`patomw` mass conversion (`GeochemAPI.F90:260-369`).
  5. `UpdateFertilizerBand(L,NY,NX)` updates band widths/depths for NH4, NO3, PO4 fertilizer.
- After the layer loop, `UpdateSurfResidueSolute(NX,NY)` applies surface-residue chemistry (`GeochemAPI.F90:146`).

The conditional entry at `GeochemAPI.F90:98` gates chemistry on both pore-water and micropore volume being above a minimum, i.e., fully dry layers do not evolve chemistry.

The reverse call order for the salt branch is:

```
Driver -> soluteModel -> per layer:
  UpdateSoilFertlizer -> {UreaHydrolysis, per-species fertilizer dissolution}
  GeochemAPISend
  GeoChemEquilibria
    -> SaltChemEquilibria:
         PrepIonConcentrations
         repeat MRXN times:
           SolveChemEquilibria:
             GetSoluteConcentrations
             IonStrengthActivity
             PhospPrecipDissolNonBand
             PhospPrecipDissolBand
             PhospAnionExchNoBand
             PhospAnionExchBand
             CationExchange
             SoluteDissociation
             UpdateIonFluxCurentIter
             UpdateIonConcCurrentIter
             AccumulateIonFlux
         SummarizeIonFluxes
    -> NoSaltChemEquilibria (reduced-form alternative)
  GeochemAPIRecv
  UpdateFertilizerBand
    -> {UpdateNH3FertilizerBandinfo,
        UpdateNO3FertilizerBandinfo,
        UpdatePO4FertilizerBandinfo}
UpdateSurfResidueSolute
```

See `f90src/Geochem/Box_chem/SaltChemEquilibriaMod.F90:299-535` for the orchestration and `SolveChemEquilibria` at `:733`.

## High-level architecture

### Two solver paths

The `salt_model` flag in the site input controls the chemistry fidelity:

- **Reduced mode (`salt_model = .false.`)**: only P and co-reactants are solved. The pH is prescribed (from user input or a constant), which sets H+ and OH- activities; the solver then computes P precipitation-dissolution, P anion exchange, and H2PO4 <-> HPO4 dissociation. Simplified cation exchange with NH4 is still done via Gapon coefficients. See `ChemEquilibriaMod.F90:22-770`. This is the default mode for non-saline systems where only NPK fertility chemistry matters.
- **Full salt mode (`salt_model = .true.`)**: full aqueous chemistry with Al3+, Fe3+, Ca2+, Mg2+, Na+, K+, SO4, Cl, CO3, HCO3, OH, H+ and their complexes (AlOH, AlOH2, AlOH3, AlOH4, AlSO4, FeOH through FeOH4, FeSO4, CaOH, CaCO3, CaHCO3, CaSO4, MgOH2, MgCO3, MgHCO3, MgSO4, NaCO3, NaSO4, KSO4). pH is iterated from ion balance. Activity coefficients are from the ionic-strength-dependent Debye-Huckel-like formulation in `IonStrengthActivity` (`SaltChemEquilibriaMod.F90:1548`). Used for saline, acid-sulfate, and calcareous soils.

### Fixed-point iteration

`SaltChemEquilibria` runs `MRXN = 1` passes through `SolveChemEquilibria` (`f90src/ModelPars/SoluteParMod.F90:143`). Each pass solves all the sub-problems (mineral dissolution, anion exchange, cation exchange, dissociation) using activity-based quadratic formulations like

```
(A) <-> B + C,    K = [B][C]/[A]
x^2 + (B + C + K) x + (BC - A*K) = 0
```

with `A2BC_ChemReact_Quad` in `GeoChemMathMod.F90:13-41`. Time-scale rate constants `TPDX = TPD/MRXN = 2.5e-3/MRXN h^-1` for dissolution, `TADAX = TADA/MRXN h^-1` for anion adsorption, `TADCX = TADC/MRXN h^-1` for cation adsorption, and `TSLX = TSL/MRXN h^-1` for dissociation are scaled to keep the per-iteration flux stable (`SoluteParMod.F90:144-152`).

The fluxes from each iteration are accumulated in `AccumulateIonFlux` and handed back at `SummarizeIonFluxes` (`SaltChemEquilibriaMod.F90:2680-...`, `:1342-...`).

### Band vs. non-band partitioning

Every species is tracked in two soil zones:
- "Non-band" (the bulk soil matrix between fertilizer bands).
- "Band" (a spatially limited stripe where fertilizer was applied).

Fraction-of-volume arrays `trcs_VLN_vr(ids_*, L, NY, NX)` for NH4/NO3/H1PO4 partition the layer volume, with `trcs_VLN_vr(ids_*B, L, NY, NX)` being the band complement. Band width and depth evolve in time via `UpdateFertilizerBand` in `SoluteMod.F90:61-135`, driven by:

- Diffusive widening, `DWPO4 = 0.5 * sqrt(SoluteDifusvtyT_vr(ids_H1PO4,L,NY,NX)) * TortMicPM_vr(NPH,L,NY,NX)` (`SoluteMod.F90:639`).
- Vertical advective movement, `FLWD = 0.5 * (WaterFlowSoiMicP_3D(3,L) + WaterFlowSoiMicP_3D(3,L+1)) / AREA_3D(3,L)` (`SoluteMod.F90:78`).
- Redistribution of solute, adsorbed, and precipitated species from non-band to band in proportion to the band growth (`SoluteMod.F90:688-735`).

All equilibrium reactions (P dissolution, P exchange, etc.) are computed separately in the non-band and band zones, with the relevant zone water volume (`VLWatMicPPO` vs. `VLWatMicPPB`) and soil mass (`BKVLPO` vs. `BKVLPB`) gating the calculation.

### Sorption framework

EcoSIM uses three sorption classes, each with its own equilibrium formulation:

1. **Cation exchange** (`CationExchange`, `SaltChemEquilibriaMod.F90:2087-2175` or `ChemEquilibriaMod.F90:558`): Gapon-selectivity formulation on `XCEC` (cation exchange capacity). Selectivity coefficients `GKC4` (Ca-NH4), `GKCH` (Ca-H), `GKCA` (Ca-Al, also used for Ca-Fe), `GKCM` (Ca-Mg), `GKCN` (Ca-Na), `GKCK` (Ca-K) are read per-layer from site input via `GKC*_vr`. All cations are expressed as equivalent fractions raised to their charge reciprocal (e.g., `Ca^0.5`, `Al^0.333`).
2. **P anion exchange** (`PhospAnionExchNoBand`, `PhospAnionExchBand`, `SaltChemEquilibriaMod.F90:1981-2084`): Langmuir-style linear exchange between aqueous H2PO4/HPO4 and the protonated/non-protonated surface hydroxyl pair (`X-OH2`, `X-OH`) on `XAEC` (anion exchange capacity). Equilibrium constants `SXH2P`, `SXH1P`, and `SXOH2`, `SXOH1` from `f90src/ModelPars/SoluteParMod.F90:23-24` for the P species and surface-proton pair, respectively.
3. **DOC/DOM sorption** is handled by the microbial subsystem (`RDOMSorption` in `MicBGCFGMod.F90`), not here.

NH4 sorption on CEC is also implemented, with `RXN4` (non-band) and `RXNB` (band) fluxes (`SaltChemEquilibriaMod.F90:2146-2147`).

### Mineral precipitation/dissolution

For each precipitated mineral, the flux is `TPDX * (activity_product - K_sp)` with a floor at `-precipitate_mass` so dissolution cannot exceed what is present. The activity-based formulation handles protonation/deprotonation state of the involved species automatically by picking the dominant species (`PX = AMAX1(...)`, e.g., `SaltChemEquilibriaMod.F90:993` for AlPO4). Minerals modeled:

Aqueous chemistry side:
- **Gibbsite** `Al(OH)3(s)` with `SPALO = 6.5e-22 mol^3 m^-9` (`SoluteParMod.F90:12`).
- **Ferric hydroxide** `Fe(OH)3(s)` with `SPFEO` (`SoluteParMod.F90`).
- **Calcite** `CaCO3(s)` (`SaltChemEquilibriaMod.F90` within `SolveChemEquilibria`).
- **Gypsum** `CaSO4(s)` (same).

Phosphate side (in both band and non-band):
- **Variscite** `AlPO4(s)` with `SPALP = 1.0e-15 mol m^-3` (`SoluteParMod.F90:16`).
- **Strengite** `FePO4(s)` with `SPFEP = 1.0e-20 mol m^-3` (`SoluteParMod.F90:17`).
- **Brushite/Dicalcium phosphate** `CaHPO4(s)` with `SPCAD` (derived; see `SoluteParMod.F90:120`).
- **Hydroxyapatite** `Ca5(PO4)3OH(s)` with `SPCAH` through `SHCAH2` (`SoluteParMod.F90:122-125`).
- **Monocalcium phosphate** `Ca(H2PO4)2(s)` with `SPCAM = 7.0e+7 mol^3 m^-9` (`SoluteParMod.F90:18`).

### Fertilizer band dynamics

Banded applications of NH4, NH3, urea, and NO3/PO4 fertilizers are tracked by separate mass pools (`ZNH4FB`, `ZNH3FB`, `ZNHUFB`, `ZNO3FB`) and a pair of band-geometry vectors (`BandWidthPO4_vr(L,NY,NX)`, `BandThicknessPO4_vr(L,NY,NX)`, etc. in `FertilizerDataType`). Dissolution is driven by:

- **Urea hydrolysis** (`SoluteMod.F90:139-215`): microbe-catalyzed, Monod form on urea concentration with `DUKM` / `DUKI` Km and inhibition constants, driven by microbial activity (`TMicHeterActivity_vr`), temperature (`TSens4MicbGrwoth_vr`), and an inhibitor decay (`ZNHUI_vr`). Specific rate `RFertUreaSpecHydrol` comes from the fertilizer type table.
- **Non-urea fertilizer dissolution**: first-order decay at rates specific to each fertilizer type, summed into `REcoReleaz_NH4`, `REcoReleaz_NH3`, `REcoReleaz_H1PO4`, `REcoReleaz_H2PO4`, `RFertReleaz_NO3`, which then enter the appropriate mineral pool (band or non-band) per `SoluteMod.F90:UpdateSoilFertlizer` (`:218-511`).

## Ion mass balance and output

`SummarizeIonFluxes` (`SaltChemEquilibriaMod.F90:1342`) rolls up per-iteration fluxes into the salt-model output bag `solflx`. `AccumulateIonFlux` (`:2680`) maintains the running total. The `solflx` bag is handed to `GeochemAPIRecv` which stores per-species results in:

- `trcn_RprodChem_soil_vr(ids_*, L, NY, NX)` for dissolved N and P species production.
- `trcn_RProdChem_band_soil_vr(ids_*B, L, NY, NX)` for banded equivalents.
- `trcx_TRSoilChem_vr(idx_*, L, NY, NX)` for exchangeable ion fluxes.
- `trcp_RChem_soil_vr(idsp_*, L, NY, NX)` for precipitate mass changes (AlPO4, FePO4, CaHPO4, apatite, CaH4P2O8, AlOH3, FeOH3, CaCO3, CaSO4).
- `trcSalt_RGeoChem_flx_vr(idsalt_*, L, NY, NX)` for all salt-model aqueous species (only when `salt_model=.true.`).

Net ion balance (`TBION`) and water mass balance (`TRH2O`) are also accumulated for sanity-checking (`GeochemAPI.F90:364-365`).

## Where to go next

- `equilibria_and_sorption.md` has the rate laws, Gapon formula, Langmuir-style anion exchange, mineral solubility products, and ion activity corrections with line-number citations.
- `f90src/ModelPars/SoluteParMod.F90` is the authoritative source for equilibrium constants and rate constants.
- `f90src/Modules/AqueChemDatatype.F90` and `f90src/Modules/TracerIDMod.F90` hold the salt tracer indices (`idsalt_*`) and sorbed-species indices (`idx_*`, `idsp_*`).
