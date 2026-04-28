---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/{Plant_bgc, Prescribed_pheno}/`
**Last verified:** 2026-04-24
---

# Photosynthesis and Respiration

EcoSIM uses a **Farquhar-type C3 / two-compartment C4** biochemical photosynthesis
model with a mechanistically prognosed leaf protein pool supplying Rubisco, PEP
carboxylase, and chlorophyll surface densities. Stomatal conductance is derived from
the CO2 diffusion equation rather than from a Ball-Berry or Medlyn empirical closure.
Respiration is split into maintenance (proportional to temperature × structural N) and
growth (proportional to non-structural C oxidation minus maintenance, multiplied by
turgor and N/P constraints).

The primary reference cited in the source is Grant (1989) — noted at
`f90src/Plant_bgc/StomatesMod.F90:438` ("Eq. (1) of Grant, 1989") and
`:968`. No Ball-Berry or Medlyn coupling is present; stomatal resistance is built
directly from the CO2 diffusion rate required to match the computed carboxylation rate.

## 1. Call sites

The photosynthesis solver is invoked from two call chains:

**Diagnostic chain** (prepares Vcmax25 / Jmax25 / leaf protein density, called
once per hour per PFT from `UptakesMod`):

```
RootUptakes                                  (UptakesMod.F90:41)
  PhotosynsDiag                              (StomatesMod.F90:23-192)      ! stoichiometric pools
  StomatalDynamics                           (StomatesMod.F90:194-272)     ! CanopyGasCO2, AirConc, min stomatal R
    PhotoActivePFT                           (StomatesMod.F90:975-...)     ! per-PFT gate on solar + LA
      PrepPhotosynthesis                     (StomatesMod.F90:890-974)     ! TFN_Carboxy/Oxygen/eTranspt, Km4RubOxy
      ... branch-level call paths
```

**Actual GPP/respiration chain** (during growth, per-hour per-branch):

```
GrowOneBranch                                (PlantBranchMod.F90:35)
  ComputeGPP                                 (PhotoSynsMod.F90:437-552)
    ComputeGPP_C3                            (PhotoSynsMod.F90:19-210)     ! if iPlantPhotosynsType_pft==ic3_photo
    ComputeGPP_C4                            (PhotoSynsMod.F90:213-434)    ! if iPlantPhotosynsType_pft==ic4_photo
  ComputRAutoAfEmergence                     (PlantBranchMod.F90:3047)     ! maintenance + growth resp
    [pre-emergence twin: ComputRAutoB4Emergence at 3243]
```

## 2. Photosynthesis types

Declared at `f90src/Modelconfig/ElmIDMod.F90:45-46`:

```
ic3_photo = 3
ic4_photo = 4
```

`iPlantPhotosynsType_pft(NZ)` selects the branch. C3 PFTs run Rubisco-only
carboxylation. C4 PFTs run the two-compartment model with PEP carboxylation in
mesophyll and C3/Rubisco re-fixation in bundle sheath.

## 3. Biochemical-pool diagnostic (PhotosynsDiag)

`PhotosynsDiag` (`f90src/Plant_bgc/StomatesMod.F90:23-192`) aggregates per-node leaf
protein into:

| Quantity (per branch, then per PFT) | Formula | Source line |
|---|---|---|
| `LeafProteinC_brch(NB,NZ)` | Σ over nodes: `LeafProteinC_node` | `StomatesMod.F90:119` |
| `MesophyllRubiscoC` (C3) | `LeafProteinC_node * LeafRubisco2Protein_pft` | `:147` |
| `MesophyllChlC` (C3) | `LeafProteinC_node * LeafProtein2Chl_pft / 3.5` | `:146` |
| `BundlSheathRubiscoC` (C4) | `LeafProteinC_node * LeafRubisco2Protein_pft` | `:127` |
| `MesophyllPEPC` (C4) | `LeafProteinC_node * LeafPEP2Protein_pft` | `:129` |
| `BundlSheathChlC` (C4) | `LeafProteinC_node * LeafProtein2Chl_pft * (1-fMesophyllChlProtein_pft) / 5.5` | `:128` |
| `MesophyllChlC` (C4) | `LeafProteinC_node * LeafProtein2Chl_pft * fMesophyllChlProtein_pft / 3.7` | `:130` |

The `3.5`, `3.7`, and `5.5` divisors are gC-protein-per-gC-chlorophyll conversion
factors (comments at `StomatesMod.F90:128-130, 146, 408`).

These are then multiplied by per-enzyme reference activities to get
temperature-independent capacities:

```
VcMaxRubiscoRef_brch += VmaxSpecRubCarboxyRef_pft * MesophyllRubiscoC  (C3)
                     or VmaxSpecRubCarboxyRef_pft * BundlSheathRubiscoC (C4)
VcMaxPEPCarboxyRef_brch += VmaxPEPCarboxyRef_pft * MesophyllPEPC       (C4)
VoMaxRubiscoRef_brch += VmaxRubOxyRef_pft * (Mesophyll or BundlSheath Rubisco)
ElectronTransptJmaxRef_brch += SpecLeafChlAct_pft * MesophyllChlC      (+ BundlSheathChlC for C4)
```

Per-PFT totals are normalized by total leaf area to yield
`CanopyVcMaxRubisco25C_pft`, `CanopyVoMaxRubisco25C_pft`,
`CanopyVcMaxPEP25C_pft`, `ElectronTransptJmax25C_pft`, and the specific leaf area
`SpecificLeafArea_pft = tLeafArea / tLeafC` (`StomatesMod.F90:170-188`).

`PhotosynsDiag` also gates by phenology (`StomatesMod.F90:103-107`): Vcmax25 is only
non-zero when the branch is evergreen, past spring leafout, or before autumn leafoff.

## 4. Stomatal resistance (StomatalDynamics)

`StomatalDynamics` (`f90src/Plant_bgc/StomatesMod.F90:194-272`) operates at the PFT
level (no layer discrimination yet). Steps:

1. **Canopy boundary-layer resistance** from Richardson-number correction
   (`StomatesMod.F90:237-239`):

   ```
   RI = RichardsonNumber(RIB, TairK, TKCanopy_pft)
   CanopyCO2BndlResist_pft = 1.34 * max(5.56e-3, RawIsoTCanopy2Atm_pft / (1 - 10*RI))
   AirConc_pft = GetMolAirPerm3(TKCanopy_pft)   ! at 1 atm
   ```

   The factor 1.34 is the ratio of CO2-to-heat diffusivity (i.e.  Sc/Pr ~ 1.34).

2. **Canopy CO2 concentration** from mass balance on the canopy air
   (`StomatesMod.F90:250-252`):

   ```
   CanopyGasCO2_pft(NZ) = CO2E - 8.33e4 * NetCO2Flx2Canopy_col
                                 * CanopyCO2BndlResist_pft / AirConc_pft
   ```

   Clamped to `[CO2E-200, CO2E+200]` ppm. The prefactor `8.33e4` is a unit conversion
   (comment: "how 8.33E+04 is determined" -- not further annotated; from dimensional
   analysis it converts g CO2 d^-2 h^-1 through molar mass and h-per-s to umol/mol).

3. **Intercellular CO2** (`StomatesMod.F90:260`):

   ```
   LeafIntracellularCO2_pft(NZ) = CanopyCi2CaRatio_pft * CanopyGasCO2_pft(NZ)
   ```

   where `CanopyCi2CaRatio_pft` is read from the PFT file. There is **no Ball-Berry
   iteration** at this stage — Ci is simply a fixed fraction of Ca for the purpose of
   obtaining the daylight stomatal-resistance target.

4. **Minimum stomatal resistance** via `PhotoActivePFT` (`StomatesMod.F90:975-...`),
   only when the sun is up and leaf area exists. Otherwise
   `CanopyMinStomaResistH2O_pft = H2OCuticleResist_pft`. The minimum is the
   steady-state value when turgor is maximal; actual realized stomatal resistance is
   increased by turgor stress `Stomata_Stress` in `ComputeGPP_*`.

## 5. C3 photosynthesis (C3Photosynthesis + ComputeGPP_C3)

The biochemical equations live in `C3Photosynthesis`
(`StomatesMod.F90:368-474`). Per node (K), per branch (NB), per PFT (NZ):

### CO2-limited (Rubisco) carboxylation

```
MesophyllRubiscoSurfDensity = LeafRubisco2Protein_pft * ProteinCLeafAreaDensity        ! g Rubisco m^-2 LA
MesophyllChlDensity         = LeafProtein2Chl_pft * ProteinCLeafAreaDensity / 3.5      ! g Chl m^-2 LA

VcMaxRubiscoRef_node = VmaxSpecRubCarboxyRef_pft(NZ) * MesophyllRubiscoSurfDensity     ! umol m^-2 s^-1 at 25 °C
VoMaxRubiscoRef_node = VmaxRubOxyRef_pft(NZ)         * MesophyllRubiscoSurfDensity

Vmax4RubiscoCarboxy_node(K,NB,NZ) = VcMaxRubiscoRef_node * TFN_Carboxy                 ! T-corrected Vcmax
VOGRO                              = VoMaxRubiscoRef_node * TFN_Oxygen                  ! T-corrected Vomax

CO2CompenPoint_node(K,NB,NZ) = 0.5 * O2L_pft * VOGRO * Km4LeafaqCO2_pft                ! Γ* (uM)
                             / (Vmax4RubiscoCarboxy_node * Km4RubOxy)

! Eq. (1) of Grant, 1989 -- comment at line 438
CO2lmtRubiscoCarboxyRate_node(K,NB,NZ) = max(0, Vmax4RubiscoCarboxy_node
                                              * (aquCO2Intraleaf_pft - CO2CompenPoint_node)
                                              / (aquCO2Intraleaf_pft + Km4RubiscoCarboxy_pft))
```

`aquCO2Intraleaf_pft` is the leaf aqueous CO2 concentration (uM) corresponding to
`LeafIntracellularCO2_pft` through the CO2 solubility `CO2Solubility_pft`. `O2L_pft` is
the leaf aqueous O2 concentration. `Km4LeafaqCO2_pft` and `Km4RubiscoCarboxy_pft` are
the Km for Rubisco carboxylation without and with O2 competition.

### Light-limited carboxylation and the CURV-shape e-transport

```
ElectronTransptJmaxRef_node    = SpecLeafChlAct_pft * MesophyllChlDensity
LigthSatCarboxyRate_node       = ElectronTransptJmaxRef_node * TFN_eTranspt

! Smoothed (CURV-shape) electron transport, used inside ComputeGPP_C3:
PARX = QNTM * PAR_zsec
PARJ = PARX + LigthSatCarboxyRate_node
ETLF = (PARJ - sqrt(PARJ^2 - 4*CURV*PARX*LigthSatCarboxyRate_node)) / (2*CURV)
EGRO = ETLF * RubiscoCarboxyEff_node
VL   = min(CO2lmtRubiscoCarboxyRate_node, EGRO) * RubiscoActivity_brch
```

(`PhotoSynsMod.F90:114-119`). `QNTM=0.45` is quantum efficiency
(`PlantBGCPars.F90:233`), `CURV=0.70` is the shape parameter
(`PlantBGCPars.F90:234`). `RubiscoCarboxyEff_node` captures the CBX-vs-oxygenation ratio:

```
RubiscoCarboxyEff_node = max(0, (aquCO2Intraleaf_pft - CO2CompenPoint_node)
                                / (ELEC3*aquCO2Intraleaf_pft + 10.5*CO2CompenPoint_node))
```

with `ELEC3=4.5` (electrons per CO2 fixed by Rubisco, `PlantBGCPars.F90:237`) and the
10.5 coefficient representing oxygenation overhead.

### Stomatal conductance and Ci iteration (ComputeGPP_C3)

Within `ComputeGPP_C3` (`PhotoSynsMod.F90:130-198`) the model **solves for Ci**
such that carboxylation equals CO2 diffusion through stomata + boundary layer:

```
! Without water stress
RS  = min(CO2CuticleResist_pft, max(RCMN, DiffCO2Atmos2Intracel_pft / VL))
RSL = RS + (CO2CuticleResist_pft - RS) * Stomata_Stress              ! turgor-degraded
GSL = 1.0 / RSL * AirConc_pft                                         ! mol m^-2 s^-1

! Non-stomatal water stress on Rubisco
if not bryophyte:
    WFNB = sqrt(RS / RSL)
else:
    WFNB = PsiCan4Photosyns                                           ! water-potential scalar

! Ci fixed-point iteration (max 100 iterations, tolerance 0.005)
CO2X = LeafIntracellularCO2_pft
for NN = 1..100:
    CO2C  = CO2X * CO2Solubility_pft                                  ! ppmv -> uM
    CO2Y  = max(0, CO2C - CO2CompenPoint_node)
    CBXNX = CO2Y / (ELEC3*CO2C + 10.5*CO2CompenPoint_node)
    VGROX = Vmax4RubiscoCarboxy_node * CO2Y / (CO2C + Km4RubiscoCarboxy_pft)
    EGROX = ETLF * CBXNX
    VL    = min(VGROX, EGROX) * WFNB * RubiscoActivity_brch
    VG    = (CanopyGasCO2_pft - CO2X) * GSL
    DIFF  = (VL - VG) / (VL + VG)
    if abs(DIFF) < 0.005: break
    VA    = 0.95*VG + 0.05*VL
    CO2X  = CanopyGasCO2_pft - VA / GSL
```

(`PhotoSynsMod.F90:158-181`). The fixed-point iteration uses a 95/5 convex combination
to damp oscillations. On convergence:

```
clscal = LeafAreaSunlit_zsec * TAU_Rad             ! sunlit area fraction × transmittance
CH2OClmt += VGROX * WFNB * RubiscoActivity_brch * clscal
CH2OLlmt += EGROX * WFNB * RubiscoActivity_brch * clscal
CH2O3K   += VL * clscal
```

Sunlit-vs-shaded attribution is tracked in `CH2OSunlit_pft` and `CH2OSunsha_pft`
(`PhotoSynsMod.F90:192-197`) based on the `LP` flag (leaf population: sunlit = 1,
shaded = other).

`RCMN=15.6 s m^-1` (`PlantBGCPars.F90:229`) is the minimum CO2 stomatal resistance.
`CO2CuticleResist_pft` is the cuticle resistance read from the PFT file (effectively
the max stomatal resistance).

### C3 GPP sum

`ComputeGPP_C3` iterates over all `NumCanopyLayers1` layers (top-to-bottom),
`NumLeafZenithSectors1` sectors, `NumOfSkyAzimuthSects1` azimuths, and both
sunlit/shaded populations. The result is unit-converted to gC d^-2 h^-1 at
`ComputeGPP:519-527` via `umol2gC_hr = 3600 * 12e-6 = 0.0432`
(`PhotoSynsMod.F90:13`).

## 6. C4 photosynthesis (C4Photosynthesis + ComputeGPP_C4)

C4 uses a two-compartment model where the mesophyll concentrates CO2 via PEP
carboxylase, and the bundle sheath decarboxylates + re-fixes via Rubisco. Both
compartments run simultaneously.

### Mesophyll PEP carboxylation
(`StomatesMod.F90:547-561`)

```
MesophyllPEPSurfDensity = ProteinCLeafAreaDensity * LeafPEP2Protein_pft
MesophyllChlDensity     = ProteinCLeafAreaDensity * LeafProtein2Chl_pft * fMesophyllChlProtein_pft / 3.7

VcMaxPEPCarboxyRef_node       = VmaxPEPCarboxyRef_pft(NZ) * MesophyllPEPSurfDensity
Vmax4PEPCarboxy_node(K,NB,NZ) = VcMaxPEPCarboxyRef_node * TFN_Carboxy
CO2lmtPEPCarboxyRate_node     = max(0, Vmax4PEPCarboxy_node
                                        * (aquCO2Intraleaf_pft - COMP4)
                                        / (aquCO2Intraleaf_pft + Km4PEPCarboxy_pft))

LigthSatC4CarboxyRate_node    = SpecLeafChlAct_pft * TFN_eTranspt * MesophyllChlDensity
C4CarboxyEff_node             = max(0, (aquCO2Intraleaf_pft - COMP4) / (ELEC4*aquCO2Intraleaf_pft + 10.5*COMP4))
```

`COMP4 = 0.5 uM` is the C4 CO2 compensation point (`PlantBGCPars.F90:242`), and
`ELEC4 = 3.0` is electrons per CO2 fixed by PEP (`PlantBGCPars.F90:238`).

### Non-structural feedback on C4 carboxylation
(`StomatesMod.F90:538-543`)

Mesophyll C4 non-structural C (`CPOOL4_node`) and bundle sheath non-structural C
(`CMassCO2BundleSheath_node`) feedback-inhibit PEP carboxylation through a
Michaelis-type factor:

```
CC4M = 0.021e9 * CPOOL4_node / (LeafElmntNode_brch(ielmc) * FWCMesophyll)
CCBS = 0.083e9 * CMassCO2BundleSheath_node / (LeafElmntNode_brch(ielmc) * FWCBundlSheath)
NutrientCtrlonC4Carboxy_node(K,NB,NZ) = 1 / (1 + CC4M / C4KI_pepcarboxy)
                                       * GrainFillDowreg_brch(NB,NZ)
```

with `C4KI_pepcarboxy = 5.0e6` (`PlantBGCPars.F90:257`), `FWCMesophyll = 0.8*FWCLeaf = 4.8`,
`FWCBundlSheath = 0.2*FWCLeaf = 1.2` (`PlantBGCPars.F90:244-246`). Leaf water volume
fractions `FWCLeaf=6.0` (g water per g C).

### Bundle sheath C3 re-fixation
(`StomatesMod.F90:619-655`)

Identical Grant-1989 Rubisco kinetics as in C3, but with CO2 supply `CCBS` (from
bundle-sheath pool) instead of `aquCO2Intraleaf_pft`:

```
BundlSheathRubiscoSurfDensity = ProteinCLeafAreaDensity * LeafRubisco2Protein_pft
BundlSheathChlDensity         = ProteinCLeafAreaDensity * LeafProtein2Chl_pft * (1-fMesophyllChlProtein_pft) / 5.5

Vmax4RubiscoCarboxy_node      = VcMaxRubiscoRef_node * TFN_Carboxy
CO2CompenPoint_node           = 0.5 * O2L_pft * (VmaxRubOxyRef_pft * BundlSheathRubiscoSurfDensity * TFN_Oxygen)
                                * Km4LeafaqCO2_pft / (Vmax4RubiscoCarboxy_node * Km4RubOxy)
CO2lmtRubiscoCarboxyRate_node = max(0, Vmax4RubiscoCarboxy_node * (CCBS - CO2CompenPoint_node)
                                                                / (CCBS + Km4RubiscoCarboxy_pft))
LigthSatCarboxyRate_node      = SpecLeafChlAct_pft * TFN_eTranspt * BundlSheathChlDensity
RubiscoCarboxyEff_node        = max(0, (CCBS - CO2CompenPoint_node) / (ELEC3*CCBS + 10.5*CO2CompenPoint_node))
```

The C4 Ci iteration and canopy-layer sums in `ComputeGPP_C4`
(`PhotoSynsMod.F90:213-434`) mirror the C3 path but track four quantities — PEP
carboxylation (`CH2O4`), Rubisco re-fixation in bundle sheath (`CH2O3`),
carbon-limited and light-limited totals (`CH2OClm`, `CH2OLlm`).

## 7. Temperature functions

Four temperature functions come from `PrepPhotosynthesis` (`StomatesMod.F90:890-974`):
`TFN_Carboxy`, `TFN_Oxygen`, `TFN_eTranspt`, and `Km4RubOxy`. They each follow the
same Arrhenius-with-high-low-T-inactivation functional form as maintenance respiration
(§8), with enzyme-specific activation energies and inactivation enthalpies.

Two utilities in `PlantMathFuncMod.F90` implement these:

- `calc_plant_maint_tempf(TKCM)` (`PlantMathFuncMod.F90:163-174`) — maintenance
  respiration:
  ```
  TFN5 = exp(25.214 - 62500/RTK) / ACTVM
  ACTVM = 1 + exp((195000 - 710*TK)/RTK) + exp((710*TK - 232500)/RTK)
  ```
  62500 J/mol activation, 195000 J/mol low-T inactivation, 232500 J/mol high-T
  inactivation. Normalized to 1 at 298.15 K.
- `calc_leave_grow_tempf(TKCO)` — used by phenology (node-initiation rates);
  documented in the phenology sub-doc, §3.

Comments at `GrosubsMod.F90:458-461`: "8.3143, 710.0 = gas constant, enthalpy;
62500, 195000, 232500 = energy of activn, high, low temp inactivn (KJ mol-1)".

## 8. Maintenance respiration

From `ComputRAutoAfEmergence` (`PlantBranchMod.F90:3145-3150`):

```
RCO2Maint_brch = max(0, RmSpecPlant * TFN5 * ShootStructN_brch)

if bryophyte or drought-deciduous:
    RCO2Maint_brch *= WaterStress4Groth
```

- `RmSpecPlant = 0.010` gC per gN h^-1 (`PlantBGCPars.F90:227`). Species-level
  maintenance-respiration rate constant at 25 °C, per unit **structural N** of the
  shoot.
- `TFN5` is the canopy temperature function (§7 above, via `calc_plant_maint_tempf`).
- `ShootStructN_brch` is the **structural** N mass of the branch, excluding
  non-structural pools — so reserves don't pay maintenance respiration.

The root-side twin is `ComputRAutoB4Emergence` (`PlantBranchMod.F90:3185-3188`) and
uses `TFN6_vr(NGTopRootLayer_pft)` (per-layer temperature function) in place of `TFN5`.

### Excess-maintenance feedback

When `RCO2NonstC_brch < RCO2Maint_brch`, the deficit is stored as `RMxess_brch`
(`PlantBranchMod.F90:3160`) and propagated to:
- `RemobilizeBranch` (`PlantBranchMod.F90:3706-3877`) — withdraws non-structural C/N/P
  from leaves, petiole-sheath, stalk, and stalk reserve to pay the deficit.
- `SenescenceBranch` (`PlantBranchMod.F90:3878-4096`) — if remobilization fails,
  advances leaf senescence and moves residual mass to litter.

This makes maintenance respiration the mechanistic trigger for seasonal leaf drop in
stress-deciduous PFTs, not an explicit day-length or temperature threshold in the
deciduous path.

## 9. Growth respiration

`ComputRAutoAfEmergence` (`PlantBranchMod.F90:3156-3224`):

```
RCO2NonstC_brch = VMXC * CanopyNonstElms_brch(ielmc) * fTCanopyGroth_pft
                  * CNPG * GrainFillDowreg_brch * WaterStress4Groth

CNPG = min( ZPOL/(ZPOL + CPOL*CNKI), PPOL/(PPOL + CPOL*CPKI) )     ! N,P constraint

RCO2X = RCO2NonstC_brch - RCO2Maint_brch
RCO2Y = max(0, RCO2X) * TurgEff4CanopyResp                           ! growth resp ceiling
RgroCO2_ltd = min(RCO2Y, ZPOOL * YCO2Gro_brch / (CNSHX + CNLFM + CNLFX*CNPG),
                         PPOOL * YCO2Gro_brch / (CPSHX + CPLFM + CPLFX*CNPG))
```

Key quantities:

- `VMXC = 0.015 h^-1` — specific oxidation rate of non-structural C at 25 °C
  (`PlantBGCPars.F90:216`).
- `CNKI = 0.10`, `CPKI = 0.01` (gN or gP / gC) — N and P inhibition constants on
  respiration from non-structural C:N:P (`PlantBGCPars.F90:225-226`). Values differ
  from `CNKI_rubisco = 0.01` and `CPKI_rubisco = 0.001` (`PlantBGCPars.F90:255-256`)
  used for Rubisco feedback in `PhenoActiveBranch` (`StomatesMod.F90:834-841`).
- `fTCanopyGroth_pft` — canopy growth-temperature function, distinct from `TFN5`
  (maintenance).
- `YCO2Gro_brch` — respiration quotient (gC respired per gC biomass produced; 0<Y<1).
- `TurgEff4CanopyResp` — from `fRespWatSens(TurgEff4LeafPetolExpansion, iPlantRootProfile_pft)`
  in `GrosubsMod.F90:505`.

### Net C balance per branch

```
Rauto_brch           = min(RCO2Maint_brch, RCO2NonstC_brch) + RgroCO2_ltd + RCO2NonstC4Nassim_brch
RCO2NonstC4Nassim_brch = max(0, 1.70 * CanopyNonstElm4Gros(ielmn) - 0.025 * CH2O)
```

(`PlantBranchMod.F90:3210-3215`). The N-assimilation term represents the respiratory
cost of assimilating non-structural N into structural protein (1.70 gC respired per
gN fixed into protein, minus a 0.025 gC/gCH2O offset representing newly fixed C also
used for N assimilation — comment at `PlantBranchMod.F90:3206-3207`: "1/4 newly fixed
C is used for N-assimilation").

### Site-level carbon flux accumulation
(`PlantBranchMod.F90:3218-3224`)

```
GrossCO2Fix_pft    += CO2F                                ! gross photosynthesis accumulator
CanopyGrosRCO2_pft -= Rauto_brch                          ! autotrophic respiration
CO2NetFix_pft      += CO2F - Rauto_brch                   ! NPP equivalent (per-hour, per-PFT)
ECO_ER_col         -= Rauto_brch                          ! ecosystem respiration
Eco_AutoR_CumYr_col -= Rauto_brch
RCanMaintDef_CO2_pft -= RMxess_brch                       ! residual maintenance deficit
```

## 10. Per-branch RubiscoActivity (nutrient down-regulation)

`PhenoActiveBranch` (`StomatesMod.F90:803-889`) applies two feedbacks to each branch
before its photosynthesis call:

1. **Nutrient feedback on Rubisco** (`StomatesMod.F90:828-841`):
   ```
   if LeafPetoNonstElmConc_brch(ielmc) > 0:
       CNS = CZPOL / (CZPOL + CCPOL * CNKI_rubisco)
       CPS = CPPOL / (CPPOL + CCPOL * CPKI_rubisco)
       RubiscoActivity_brch = min(CNS, CPS)
   else:
       RubiscoActivity_brch = 1
   ```
   with `CNKI_rubisco = 0.01`, `CPKI_rubisco = 0.001` (`PlantBGCPars.F90:255-256`).

2. **Conifer spring dehardening** (`StomatesMod.F90:859-861`):
   ```
   if not evergreen and iPlantTurnoverPattern_pft >= 2:
       RubiscoActivity_brch *= min(1, Hours2LeafOut_brch / (0.9 * Hours4ConiferSpringDeharden))
   ```
   with `Hours4ConiferSpringDeharden = 276.9 h` (`PlantBGCPars.F90:258`).

3. **Annual termination** (`StomatesMod.F90:867-872`):
   ```
   if annual and HourFailGrainFill_brch > 0:
       GrainFillDowreg_brch = max(0, 1 - HourFailGrainFill_brch / Hours2KillAnuals(iPlantPhenolType_pft))
   ```
   with `Hours2KillAnuals(0:5) = (336, 672, 672, 672, 672, 672)` for the six
   phenology types (`StomatesMod.F90:16`).

## 11. Root respiration

Root respiration is computed identically to canopy respiration but with:

- `TFN6_vr(L)` (per-soil-layer maintenance temp function, `GrosubsMod.F90:467`) in
  place of `TFN5`.
- `fTgrowRootP_vr(L)` in place of `fTCanopyGroth_pft` for non-structural C oxidation.
- `RAutoRootO2Limter_rpvr(ipltroot, L, NZ)` — O2-availability multiplier for root
  non-structural C oxidation (0-1). Reflects hypoxic soils and explains much of the
  seasonal variation in soil CO2 flux in flooded/saturated sites.
- `fRootGrowPSISense` — root water-potential sensitivity function replacing
  `WaterStress4Groth`.

Root growth respiration and maintenance respiration are summed across primary axes
and soil layers and accumulated in `PlantExudElm_CumYr_pft` (net C exchange) and
`Eco_AutoR_CumYr_col` in the root-BGC driver (`RootMod.F90`).

## 12. Parameter provenance

All dimensionless biochemical constants are declared in `PlantBGCPars.F90:216-258`:

| Parameter | Value | Meaning |
|---|---|---|
| `QNTM` | 0.45 | Quantum efficiency, umol e-/umol PAR |
| `CURV` | 0.70 | Shape parameter for e-transport response to PAR |
| `ELEC3` | 4.5 | Electrons per CO2 fixed by Rubisco |
| `ELEC4` | 3.0 | Electrons per CO2 fixed by PEP carboxylase |
| `COMP4` | 0.5 uM | C4 CO2 compensation point |
| `CO2KI` | 1.0e3 | CO2 inhibition constant |
| `FCMassCO2BundleSheath_node` | 0.02 | C4 bundle-sheath CO2 pool fraction |
| `FWCLeaf` | 6.0 | Leaf water content ratio (g water / g C) |
| `FWCBundlSheath` | 0.2*FWCLeaf = 1.2 | Bundle-sheath water content |
| `FWCMesophyll` | 0.8*FWCLeaf = 4.8 | Mesophyll water content |
| `VMXC` | 0.015 h^-1 | Non-structural C oxidation rate at 25 °C |
| `RmSpecPlant` | 0.010 gC/gN/h | Specific maintenance respiration at 25 °C |
| `CNKI` | 0.10 gN/gC | N inhibition on non-structural C oxidation |
| `CPKI` | 0.01 gP/gC | P inhibition on non-structural C oxidation |
| `CNKI_rubisco` | 0.01 gN/gC | N inhibition on Rubisco activity |
| `CPKI_rubisco` | 0.001 gP/gC | P inhibition on Rubisco activity |
| `C4KI_pepcarboxy` | 5.0e6 | PEP carboxylase feedback inhibition constant |
| `RCMN` | 15.6 s/m | Min stomatal resistance to CO2 |
| `Hours4ConiferSpringDeharden` | 276.9 h | Hours to conifer spring dehardening |
| `ZPLFM`, `ZPLFD` | 0.33, 0.67 | Leaf protein partitioning to metabolic/storage |
| `resp_downreg` | 0.05 | Respiration down-regulation coefficient |

PFT-level parameters (`plt_photo`, `plt_allom`): `VmaxSpecRubCarboxyRef_pft`,
`VmaxRubOxyRef_pft`, `VmaxPEPCarboxyRef_pft`, `SpecLeafChlAct_pft`, `Km4RubiscoCarboxy_pft`,
`Km4LeafaqCO2_pft`, `Km4PEPCarboxy_pft`, `LeafRubisco2Protein_pft`,
`LeafPEP2Protein_pft`, `LeafProtein2Chl_pft`, `fMesophyllChlProtein_pft`,
`CanopyCi2CaRatio_pft`, `CO2Solubility_pft`, `O2L_pft`, `RCS_pft` (e-folding turgor
for stomatal resistance), `iPlantPhotosynsType_pft`. All are read from the PFT
parameter file through `InitPlantMod`.

## 13. Literature cited in source

- **Grant 1989** — "Eq. (1) of Grant, 1989" in `StomatesMod.F90:438` and `:968`.
  Refers to R.F. Grant's Rubisco kinetic formulation. This is the only explicit
  literature citation in the photosynthesis code.
- **Shinozaki et al. 1964** — cited in `GrosubsMod.F90:475-477` for the pipe-model
  root-axis scaling (used in allocation, not photosynthesis).
- **Jackson et al. 1997** — cited in `PrescribePhenolMod.F90:322` for the beta-function
  root-depth profile (prescribed phenology mode).

No Farquhar/von Caemmerer/Berry, Ball-Berry, or Medlyn citations appear in source
comments. The model is thus best described as "Grant (1989) C3/C4 biochemical model
with mechanistically prognosed enzyme pools and diffusion-based stomatal closure".
