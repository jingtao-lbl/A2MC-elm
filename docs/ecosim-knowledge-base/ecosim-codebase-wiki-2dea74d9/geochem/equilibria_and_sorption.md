---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/{Microbial_bgc, Geochem}/`
**Last verified:** 2026-04-24
---

# Equilibria and Sorption

This document details the rate laws, equilibrium constants, and activity coefficient treatments in EcoSIM's geochemistry. All citations are to `f90src/` paths relative to the EcoSIM repository root.

## Solver style

EcoSIM does not solve a closed algebraic equilibrium system. Instead, it applies **pseudo-transient relaxation**: every reaction has a characteristic time-scale `T*` (`TPD` for precipitation-dissolution, `TADA` for anion adsorption, `TADC` for cation adsorption, `TSL` for dissociation), and each time step drives the system toward equilibrium at a bounded rate. Over multiple time steps this converges to equilibrium for stable systems while avoiding stiffness and mass-balance violations.

Base rate constants (all 1/h; defined in `f90src/ModelPars/SoluteParMod.F90:143-152`):

| Constant | Value | Used for |
|---|---|---|
| `TPD` | `2.5e-3` | Mineral dissolution/precipitation |
| `TADA` | `5.0e-2` | Anion adsorption on AEC |
| `TADC` | `5.0e-2` | Cation adsorption on CEC |
| `TSL`  | `5.0e-1` | Aqueous dissociation reactions |

These are divided by `MRXN = 1` to yield the per-iteration `TPDX`, `TADAX`, `TADCX`, `TSLX`. `MRXN` can in principle be increased to sub-iterate within a time step.

## Aqueous chemistry

### pH and H/OH

In the full salt model, `H_1p_aque_mole_conc` is a state variable (tracked via `trcSalt_solml_vr(idsalt_Hp, ...)`, mapped to `ZHY`). The diagnostic pH is derived from the iterated H+ activity. In the reduced `NoSaltChemEquilibria`, the input pH determines H+ and OH- activities (`chemvar%PH`), and the rest of the system is solved against those.

Water self-ionization constant: `DPH2O = 6.5e-9 mol^2 m^-6` (`SoluteParMod.F90:11`). Note: this is a concentration-based constant in `mol^2 m^-6`, not the standard `Kw = 10^-14 mol^2 L^-2`; the unit system uses `mol m^-3`.

### Carbonate system

EcoSIM tracks aqueous CO2 as `H2CO3_aque_mole_conc` and solves the open carbonate system via two equilibria (`SoluteParMod.F90:25-26`):

- `CO2(aq) + H2O <-> HCO3(-) + H(+)`, `DPCO2 = 4.2e-4 mol m^-3`.
- `HCO3(-) <-> CO3(2-) + H(+)`, `DPHCO = 5.6e-8 mol m^-3`.

Combined `DPCO3 = DPCO2 * DPHCO` is the overall constant for `H2CO3 <-> CO3(2-) + 2H(+)`.

These are applied in `SoluteDissociation` (`SaltChemEquilibriaMod.F90:2178-2469`) using the quadratic reaction formulation from `GeoChemMathMod.F90`. CO2 also couples to soil respiration via `CO2S` input and `TRChem_CO2_gchem_soil` output.

### Ion activity corrections

`IonStrengthActivity` (`SaltChemEquilibriaMod.F90:1548-1655`) computes ionic strength from aqueous concentrations weighted by charge squared (`SaltChemEquilibriaMod.F90:1571-1572`):

```
CSTR1 = 0.5e-3 * (9 * (C3+ + A3-) + 4 * (C2+ + A2-) + (C1+ + A1-))
```

where the `0.5e-3` factor converts from `mol m^-3` to `mol L^-1`.

Activity coefficients for mono-, di-, and trivalent ions use the Davies approximation (`SaltChemEquilibriaMod.F90:1579-1581`):

```
A1 = min(1, 10^(-0.509 * 1 * FSTR2 + 0.20 * CSTR2))   ! monovalent
A2 = min(1, 10^(-0.509 * 4 * FSTR2 + 0.20 * CSTR2))   ! divalent
A3 = min(1, 10^(-0.509 * 9 * FSTR2 + 0.20 * CSTR2))   ! trivalent
```

with `FSTR2 = sqrt(CSTR1)/(1 + sqrt(CSTR1))` and `CSTR2 = sqrt(CSTR1)`. Neutral species take A0 = 1.0 (`SoluteParMod.F90:129`).

These coefficients multiply each aqueous concentration to produce activities (`SaltChemEquilibriaMod.F90:1597-1653`), which are the quantities used in the solubility and exchange expressions.

### NH4/NH3

Ammonium-ammonia equilibrium: `NH4(+) <-> NH3 + H(+)`, `DPN4 = 5.7e-7 mol m^-3` (`SoluteParMod.F90:27`). Solved in `SoluteDissociation`.

## Cation exchange (Gapon formulation)

`CationExchange` (`SaltChemEquilibriaMod.F90:2087-2175` for salt mode; `ChemEquilibriaMod.F90:558-770` for reduced mode) applies Gapon-selectivity exchange with the reference cation being Ca^2+. The exchange reactions are of the form:

```
X-Ca(1/2) + H(+)     <-> X-H      + (1/2) Ca(2+)           GKCH
X-Ca(1/2) + NH4(+)   <-> X-NH4    + (1/2) Ca(2+)           GKC4
X-Ca(1/2) + (1/3)Al(3+) <-> X-Al(1/3) + (1/2) Ca(2+)       GKCA
X-Ca(1/2) + (1/3)Fe(3+) <-> X-Fe(1/3) + (1/2) Ca(2+)       GKCA  (same)
X-Ca(1/2) + (1/2)Mg(2+) <-> X-Mg(1/2) + (1/2) Ca(2+)       GKCM
X-Ca(1/2) + Na(+)    <-> X-Na     + (1/2) Ca(2+)           GKCN
X-Ca(1/2) + K(+)     <-> X-K      + (1/2) Ca(2+)           GKCK
```

All cations are raised to the inverse of their charge (e.g., `AALX = Al_activity^0.333`, `ACAX = Ca_activity^0.5`), a hallmark of Gapon (as opposed to Vanselow) selectivity. The equilibrium exchangeable pool of Ca per unit CEC is computed as (`SaltChemEquilibriaMod.F90:2111-2115`):

```
XCAX = CEC / (1 + GKC4 * NH4_activity    * VLNH4 / ACAX
                 + GKC4 * NH4B_activity   * VLNHB / ACAX
                 + GKCH * H_activity      / ACAX
                 + GKCA * AALX            / ACAX
                 + GKCA * AFEX            / ACAX
                 + GKCM * AMGX            / ACAX
                 + GKCN * Na_activity     / ACAX
                 + GKCK * K_activity      / ACAX)
```

Then each exchangeable pool is `X*Q = XCAX * activity_* * GK*` and re-normalized by `FX = CEC / XTLQ` to force the sum of equivalents to equal the CEC (`:2127`). Per-cation adsorption rate is (`:2146-2159`):

```
RXN4 = TADCX * max(min((XN4Q - XNH4_sorbed) * NH4_activity / XN4Q,  NH4_aqueous), -XNH4_sorbed)
```

The Gapon selectivity coefficients `GKC4`, `GKCH`, `GKCA`, `GKCM`, `GKCN`, `GKCK` are layer-level inputs (`GKCA_vr`, etc.) and come from site soil input.

Note: The Ca-Al and Ca-Fe use the same coefficient `GKCA` in code (line 2114); there is no separate `GKCF`.

NH4 is exchanged separately in the band (`RXNB`) and non-band (`RXN4`) zones, since the band has higher NH4 concentration locally.

## Anion exchange for phosphate (Langmuir-style)

`PhospAnionExchNoBand` and `PhospAnionExchBand` (`SaltChemEquilibriaMod.F90:1981-2084`; `ChemEquilibriaMod.F90:377-410`) implement a four-site surface model with two protonation states of the hydroxyl (`X-OH` vs. `X-OH2(+)`) and two phosphate states (`X-HPO4(-)` vs. `X-H2PO4`).

The surface protonation reactions (`SoluteParMod.F90:21-22`):

- `X-OH2(+) <-> X-OH + H(+)`, `SXOH2 = 4.5e-5 mol m^-3`.
- `X-OH <-> X-O(-) + H(+)`, `SXOH1 = 1.1e-6 mol m^-3`.

The P exchange reactions (`SoluteParMod.F90:23-24`):

- `X-H2PO4 + H2O <-> X-OH2(+) + H2PO4(-)`, `SXH2P = 2.0e7 mol m^-3` (this form sells that `SPH2P = SXH2P * DPH2O`).
- `X-H1PO4(-) + H2O <-> X-OH + H2PO4(-)`, (via `SXH1P` for the HPO4-to-OH pairing).

The rate equations have Langmuir form (since both sides of the exchange contribute to the denominator). For H2PO4 exchange with X-OH2 in the non-band (`SaltChemEquilibriaMod.F90:2015`):

```
H2PO4_1e_to_XH2PO4_ROH2_flx = TADAX
  * (XROH2 * H2PO4_1e_activity - SPH2P * XH2PO4_mole_conc)
  / (XROH2 + SPH2P) * VLWatMicPBK
```

where `SPH2P = SXH2P * DPH2O = 2e7 * 6.5e-9 = 0.13 mol m^-3`. The form `(K_d * C - C_sorbed) / (K_d + C)` is the standard Langmuir-competitive rate expression. The `VLWatMicPBK` term (`SaltChemEquilibriaMod.F90:1998-2002`) converts between concentration per soil mass and per pore volume.

An analogous pair operates in the band zone (`SaltChemEquilibriaMod.F90:2037-2084`).

This is explicitly **not** a Freundlich isotherm. The model sits between linear (low P loading, `C_sorbed << K_d`) and saturated (high P loading, `C_sorbed -> max site density`).

### Summary of P sorbed species

| Sorbed species | State array | Equilibrium pair |
|---|---|---|
| `X-H2PO4` | `XH2PO4_mole_conc` (non-band), `XH2PO4_band_mole_conc` | with `X-OH2(+)` and with `X-OH` |
| `X-HPO4(-)` | `XHPO4_mole_conc`, `XHPO4_band_mole_conc` | with `X-OH` |
| `X-OH`, `X-OH2(+)`, `X-O(-)` | `XROH1_mole_conc`, `XROH2_mole_conc`, `XOH_mole_conc` | from surface protonation |

There is **no sorption model for NO3** in EcoSIM; nitrate is treated as a free aqueous anion. **NH4** sorption uses the CEC (see above), not the AEC.

## Mineral precipitation/dissolution

### General structure

All precipitation-dissolution fluxes take the form `TPDX * (activity_product - K_eq)` with a floor at `-precipitate_mass` to prevent unphysical negative precipitate. When multiple protonation states compete (e.g., H1PO4 vs. H2PO4; Al^3+ vs. AlOH^2+ vs. AlO2H2^+ vs. AlO3H3 vs. AlO4H4^-), the code picks the **dominant** (highest-activity) species and uses the associated equilibrium constant branch (`SaltChemEquilibriaMod.F90:993-1168` for AlPO4, `:1108-1217` for FePO4).

For AlPO4 the generic form solved is:

```
AlPO4(s) + nR1 * R1 <-> Al-species + P-species + nP3 * OH(-)
SPX = SP * R1^nR1 / P3^nP3
R_dissolve = TPDX * (P1 + P2 - sqrt((P1 + P2)^2 - 4*(P1*P2 - SPX)))
```

bounded below by `-Precp_AlPO4_mole_conc`.

### Phosphate minerals

Solubility products (`SoluteParMod.F90:16-20`; all given in `mol m^-3`):

| Mineral | Formula | K_sp | Source |
|---|---|---|---|
| Variscite | `AlPO4(s) <-> Al(3+) + PO4(3-)` | `SPALP = 1.0e-15` | `SoluteParMod.F90:16` |
| Strengite | `FePO4(s) <-> Fe(3+) + PO4(3-)` | `SPFEP = 1.0e-20` | `SoluteParMod.F90:17` |
| Brushite (DCP) | `CaHPO4(s) <-> Ca(2+) + HPO4(2-)` | `SPCAD = 1.0e-1` | `SoluteParMod.F90:19` |
| Hydroxyapatite | `Ca5(PO4)3OH(s) <-> 5Ca(2+) + 3PO4(3-) + OH(-)` | `SPCAH = 2.3e-31` | `SoluteParMod.F90:20` |
| Monocalcium phosphate (MCP) | `Ca(H2PO4)2(s) <-> Ca(2+) + 2H2PO4(-)` | `SPCAM = 7.0e+7` | `SoluteParMod.F90:18` |

Each of these is solved in both the non-band (`PhospPrecipDissolNonBand`, `SaltChemEquilibriaMod.F90:984-1342`) and band (`PhospPrecipDissolBand`, `:1658-1980`) zones.

### Non-phosphate minerals

In the full salt model `SolveChemEquilibria` (`SaltChemEquilibriaMod.F90:733-984`) also solves:

| Mineral | Formula | K_sp | Source |
|---|---|---|---|
| Gibbsite | `Al(OH)3(s) <-> Al(3+) + 3 OH(-)` | `SPALO = 6.5e-22` | `SoluteParMod.F90:12` |
| Ferric hydroxide | `Fe(OH)3(s) <-> Fe(3+) + 3 OH(-)` | `SPFEO = 6.5e-27` | `SoluteParMod.F90:13` |
| Calcite | `CaCO3(s) <-> Ca(2+) + CO3(2-)` | `SPCAC = 3.8e-3` | `SoluteParMod.F90:14` |
| Gypsum | `CaSO4(s) <-> Ca(2+) + SO4(2-)` | `SPCAS = 1.4e+1` | `SoluteParMod.F90:15` |

In the reduced `NoSaltChemEquilibria` only the P minerals are solved.

## Aqueous dissociation reactions

`SoluteDissociation` (`SaltChemEquilibriaMod.F90:2178-2468`) handles dissociation of the many aqueous complexes. Their equilibrium constants are all in `SoluteParMod.F90:28-57`. Selected entries:

- Aluminum hydrolysis: `AlOH(2+) <-> Al(3+) + OH(-)`, `DPAL1 = 4.6e-7`; `Al(OH)2(+) <-> AlOH(2+) + OH(-)`, `DPAL2 = 7.3e-7`; `Al(OH)3(aq) <-> Al(OH)2(+) + OH(-)`, `DPAL3 = 1.8e-5`; `Al(OH)4(-) <-> Al(OH)3(aq) + OH(-)`, `DPAL4 = 1.2e-5`.
- Iron hydrolysis: analogous set (`DPFE1-DPFE4`).
- Aluminum sulfate: `AlSO4(+) <-> Al(3+) + SO4(2-)`, `DPALS = 0.16`.
- Ca complexes: `CaOH(+), CaCO3(aq), CaHCO3(+), CaSO4(aq)` with `DPCAO = 12.5`, `DPCAC = 4.2e-2`, `DPCAH = 13.5`, `DPCAS = 1.2`.
- Mg complexes: analogous (`DPMGO`, `DPMGC`, `DPMGH`, `DPMGS`).
- P protonation steps: `HPO4(2-) <-> H(+) + PO4(3-)`, `DPH1P = 4.5e-10`; `H2PO4(-) <-> H(+) + HPO4(2-)`, `DPH2P = 6.3e-5`; `H3PO4 <-> H(+) + H2PO4(-)`, `DPH3P = 7.1`.
- FeHPO4, FeH2PO4, CaPO4, CaHPO4(aq), CaH4P2O8, MgHPO4 complex dissociation constants `DPF1P`, `DPF2P`, `DPC0P`, `DPC1P`, `DPC2P`, `DPM1P`.

Each dissociation flux uses `A2BC_ChemReact_Quad` or `A2BC_ChemReact_Grad` (`GeoChemMathMod.F90`) on the activities multiplied by `A1`, `A2`, or `A3`.

## Fertilizer band dynamics

`UpdateFertilizerBand` (`f90src/Geochem/Layers_chem/SoluteMod.F90:61-135`) coordinates the band evolution after each chemistry step:

- Calls `UpdateNH3FertilizerBandinfo`, `UpdateNO3FertilizerBandinfo`, `UpdatePO4FertilizerBandinfo`.
- Each of these updates the layer-specific `BandWidth*_vr` and `BandThickness*_vr`, then reallocates `trcs_VLN_vr(*, L, NY, NX)` between the band (indices `*B`) and non-band zones.
- When band geometry changes, solute, sorbed, and precipitated masses are redistributed in proportion to the volume-fraction change `FVLPO4 = (trcs_VLN_new - trcs_VLN_old)/trcs_VLN_old` (`SoluteMod.F90:680`).

### Band geometry evolution

For the PO4 band (`SoluteMod.F90:615-843`):

- Band width grows diffusively: `DWPO4 = 0.5 * sqrt(SoluteDifusvtyT_vr(ids_H1PO4,L,NY,NX)) * TortMicPM_vr(NPH,L,NY,NX)`. Capped at the row spacing `ROWSpacePO4_col(NY,NX)`.
- Band depth (`BandDepthPO4_col`) evolves with vertical water flow `FLWD = 0.5 * (WaterFlowSoiMicP_3D(3,L) + WaterFlowSoiMicP_3D(3,L+1))/AREA_3D(3,L)` plus the diffusive widening term `DWPO4`.
- Band thickness (`BandThicknessPO4_vr`) is integrated downward. If the band crosses a layer boundary, the excess is handed to `BandThicknessPO4_vr(L+1,NY,NX)`.
- Fraction-of-volume for the band: `trcs_VLN_vr(ids_H1PO4B,L) = BandWidth / ROWSpace * BandThickness / DLYR`, capped at 0.999 (`SoluteMod.F90:672-673`).

The analogous logic applies to NH3 and NO3 bands.

### Fertilizer dissolution rates

Specific first-order release rates (all h^-1; `SoluteParMod.F90:132-136`):

- NH4: `RFertNH4SpecReleaz = 1.0` h^-1.
- NH3: `RFertNH3SpecReleaz = 1.0` h^-1.
- Urea: `RFertUreaSpecHydrol = 0.1` h^-1 (Monod-modified by microbial activity; see below).
- NO3: `RFertNO3SpecReleaz = 1.0` h^-1.
- PO4: `SPPO4 = 5.0e-2` h^-1 (much slower, representing granule dissolution).

Urea hydrolysis (`SoluteMod.F90:139-215`) is microbial-catalyzed:

```
RFertReleaz_Urea = min(FertN_mole_soil,  RFertUreaSpecHydrol
                     * TMicHeterActivity_vr * DFNSA
                     * TSens4MicbGrwoth_vr)
                 * (1 - ZNHUI_vr)
```

with `DFNSA = Urea_mole_conc / (Urea_mole_conc + DUKD)`, `DUKD = DUKM * (1 + COMA/DUKI)`, `DUKM = 1.0 g m^-3`, `DUKI = 2.5 g m^-3` (`SoluteParMod.F90:127-128`).

`ZNHUI_vr` is an inhibitor activity field that decays at rate `RUreaInhibtorConst(0:2) = (0.10, 0.01, 0.005) h^-1` depending on `iUreaHydInhibitorType_col` (`SoluteParMod.F90:10`), representing commercial urease inhibitors like NBPT with different half-lives.

## Mass conversion at the coupling boundary

Internally the solver uses `mol d^-2` (moles per decimeter squared area in the ELM-style convention); the plant and transport modules use `g d^-2`. `GeochemAPIRecv` applies the conversion at output (`GeochemAPI.F90:297,364`):

```
TProd_CO2_geochem_soil_vr = solflx%TRChem_CO2_gchem_soil * catomw   ! g C per mole
```

and analogous `natomw` (N mass/mole), `patomw` (P mass/mole) conversions in `SoluteMod.F90:117-132`.

## Calibration entry points

If tuning geochemistry:

1. **Rate constants**: `TPD`, `TADA`, `TADC`, `TSL` (`SoluteParMod.F90:143-152`). Lower these for more inertial P sorption; raise for snappier equilibration. `MRXN` multiplier controls sub-iteration.
2. **P solubility**: `SPALP`, `SPFEP`, `SPCAD`, `SPCAH`, `SPCAM` (`SoluteParMod.F90:16-20`). These are the big levers for P-availability calibration in acid, neutral, and calcareous soils respectively.
3. **P sorption capacity**: `XAEC` input (site-level), and the surface protonation constants `SXOH2`, `SXOH1`, `SXH2P`, `SXH1P` (`SoluteParMod.F90:21-24`).
4. **CEC**: `XCEC` input and the six Gapon selectivities `GKC4`, `GKCH`, `GKCA`, `GKCM`, `GKCN`, `GKCK` (per-layer input).
5. **Calcite**: `SPCAC = 3.8e-3` (`SoluteParMod.F90:14`) and CO2-carbonate system `DPCO2`, `DPHCO`.
6. **Fertilizer release**: `RFertNH4SpecReleaz`, `RFertNH3SpecReleaz`, `RFertUreaSpecHydrol`, `RFertNO3SpecReleaz`, `SPPO4` (`SoluteParMod.F90:132-136`).
7. **Urea inhibitor decay**: `RUreaInhibtorConst(0:2)` by inhibitor type (`SoluteParMod.F90:10`).

All equilibrium constants in `SoluteParMod.F90` are `PARAMETER`s (compile-time constants). Changes therefore require recompilation, unlike the microbial NitroPars which support NetCDF override. The Gapon selectivities and CEC/AEC are runtime inputs per soil layer.

## Caveats noted in source

- `ChemEquilibriaMod.F90:7` flags that the reduced-chemistry model does not include H3PO4 and describes this as "problematic" (noted July 28, 2022 by the model authors).
- Multiple commented-out diagnostic WRITE blocks suggest the P precipitation/dissolution logic is a common debugging focus (`SaltChemEquilibriaMod.F90:1097-1103,1212-1219,1249-1253`).
