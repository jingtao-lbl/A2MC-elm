---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/{Microbial_bgc, Geochem}/`
**Last verified:** 2026-04-24
---

# Decomposition and SOM Dynamics

This document walks through the kinetic machinery behind EcoSIM's SOM decomposition and microbial biogeochemistry. All citations are to `f90src/` paths relative to the EcoSIM repository root.

EcoSIM uses **explicit microbial biomass** (heterotrophs and autotrophs, multiple guilds per layer per OM complex) as the engine driving hydrolysis and catabolism. It is therefore a second-generation microbial-explicit model, not a CENTURY-style first-order cascade. Each decomposition rate law multiplies:

1. A specific rate constant (per-guild, per-substrate).
2. Active microbial biomass (state variable that grows/shrinks).
3. A substrate-saturation term (Michaelis-Menten / Monod).
4. An environment scalar combining temperature and water stress.
5. A stoichiometry scalar combining N and P sufficiency.

## Environmental scalars

### Temperature sensitivity

`MicrobPhysTempFun` (`f90src/Microbial_bgc/Box_Micmodel/MicrobMathFuncMod.F90:14-31`) computes separate scalars for growth and maintenance respiration, based on an Arrhenius form with low-T and high-T inactivation branches:

```
RTK   = R * T                       (R = gas constant)
STK   = 710 * T
ACTV  = 1 + exp((197500 - STK)/RTK) + exp((STK - 222500)/RTK)
TSensGrowth = exp(25.229 - 62500/RTK) / ACTV
ACTVM = 1 + exp((195000 - STK)/RTK) + exp((STK - 232500)/RTK)
TSensMaintR = exp(25.214 - 62500/RTK) / ACTVM
```

Parameters: activation energy 62500 J mol^-1, low-T inactivation enthalpy 197500 (growth) or 195000 (maintenance), high-T inactivation 222500 / 232500, entropy 710. This is explicitly NOT a Q10 form; it is the Johnson-Lewin-Eyring piecewise Arrhenius / thermal-inactivation formulation, with different half-lives for growth and maintenance.

Call site in the layer solver is `MicBGCFGMod.F90:410`. An adaptive acclimation offset `TempOffset` (site mean annual temperature in `starts.f`) shifts input temperature before the function is evaluated (`MicBGCFGMod.F90:408`).

### Water stress

The water potential (matric potential, MPa) scalar is an exponential decay applied per guild within `StageFuncGuild`. It caps the water potential floor at -500 MPa (`MicBGCFGMod.F90:781-786`):

```
if (N == mid_Aerob_Fungi) then
  WatStressMicb = exp(0.1 * max(PSISoilMatricP, -500))
else
  WatStressMicb = exp(0.2 * max(PSISoilMatricP, -500))
endif
WSensGroHeter(NGL,K) = real_truncate(WatStressMicb, 1.e-3)
```

Fungi are set to be twice as water-stress-tolerant as bacteria (exponent 0.1 vs. 0.2 per MPa). Each catabolism routine (`AerobicHeteroBactCatabolism`, `AerobicFungiCatabolism`, `AcetoMethanogenCatabolism`, etc.) re-computes an equivalent scalar locally and multiplies it with `TSensGrowth` to produce the combined growth environment scalar `GrowthEnvScalHeter(NGL,K)` used in the Monod catabolism formulas (`MicBGCFGMod.F90:2593`, `2888`, `3010`).

When soil is frozen (`TKS < Tref`), `PSISoilMatricP` is overridden with the Clausius-Clapeyron expression `LtHeatIceMelt * (TKS - Tref)/TKS`, so freezing appears as a strong matric-potential drop (`f90src/APIs/MicBGCAPI.F90:222-224`).

### Oxygen limitation

Heterotrophs request O2 following a Monod form with `OXKM = 0.080 g O m-3` (`f90src/Utils/EcoSimConst.F90:43`). The O2 uptake rate is solved diffusion-limited via the quadratic formulation `TranspBasedsubstrateUptake` in `MicrobMathFuncMod.F90:35-66`, which balances:

```
q = V_max * S / (KM + S) = D * (S_ext - S)
```

giving `q = (-B - sqrt(B^2 - 4C))/2` with `B = -V_max - D*KM - D*S_ext`, `C = D*S_ext*V_max`. The caller is `AerobicHeterO2Uptake` (`MicBGCFGMod.F90:3438-3606`). The fraction of unconstrained respiration actually realized becomes `OxyLimterHeter(NGL,K)`, multiplied onto the unlimited demand to give gross heterotroph respiration.

## SOM hydrolysis rate law

`SolidOMDecomposition` (`MicBGCFGMod.F90:1308-1595`) is the core hydrolysis routine. For each OM complex `K` and kinetic component `M`:

```
RHydrolysisScalCmpK(K) = max(ROQC4HeterMicActCmpK(K), 0)
                       * DFNS * OQCI / BulkSOMC(K)            (MicBGCFGMod.F90:1438)
RHydlysSolidOM(C,M,K) = SolidOMAct(M,K)
                      * min(0.5, SPOSC(M,K) * RHydrolysisScalCmpK(K))   (MicBGCFGMod.F90:1442)
```

Symbol definitions:

| Symbol | Source | Meaning |
|---|---|---|
| `SolidOMAct(M,K)` | state | Colonized (enzymatically accessible) fraction of `SolidOM(C,M,K)` |
| `SPOSC(M,K)` | `MicBGCPars.F90:319-325` | Specific decomposition rate constant, h^-1, kinetic component x complex |
| `ROQC4HeterMicActCmpK(K)` | from ActiveMicrobes | Aggregated heterotroph respiration as activity proxy |
| `DFNS = COSC/(COSC + DCKD)` | `MicBGCFGMod.F90:1420` | Monod saturation on bulk SOC concentration |
| `DCKD = DCKM0 * (1 + COQCK/DCKI)` | `MicBGCFGMod.F90:1409/1411` | DOC-inhibited Km (`DCKM0 = DCKML = 1.0e+3 g C g^-1 soil`, `DCKI = 2.5 g C m^-3`; `NitroPars.F90:132,148-149`) |
| `OQCI = 1/(1 + CDOM_doc/OQKI)` | `MicBGCFGMod.F90:1421` | DOC product inhibition (`OQKI = 1200 g C m^-3`, `NitroPars.F90:140`) |
| `BulkSOMC(K)` | state | Total SOC in complex K |
| `COSC` | state | Concentration of BulkSOMC per unit soil mass or pore volume |

`SPOSC` initial values (`MicBGCPars.F90:319-325`; h^-1 per kinetic component, per complex; litter complexes are further multiplied by 1.5 at line 325):

| Kinetic component (M) | woody (K=1) | fine (K=2) | manure (K=3) | POM (K=4) | humus (K=5) |
|---|---|---|---|---|---|
| 1 protein | 7.5 x 1.5 | 7.5 x 1.5 | 7.5 x 1.5 | 0.05 | 0.05 |
| 2 carbohydrate | 7.5 x 1.5 | 7.5 x 1.5 | 7.5 x 1.5 | 0.0 | 0.0167 |
| 3 cellulose | 1.5 x 1.5 | 1.5 x 1.5 | 1.5 x 1.5 | 0.0 | 0.0 |
| 4 lignin | 0.5 x 1.5 | 0.5 x 1.5 | 0.5 x 1.5 | 0.0 | 0.0 |

Thus humus is decomposed through its colonized protein (0.05 h^-1) and residual carbohydrate (0.0167 h^-1) fractions only; cellulose and lignin in POM and humus are effectively permanent in this parameterization.

The `min(0.5, ...)` cap ensures no more than half of a colonized SolidOM pool is hydrolyzed per time step, providing stability without implicit solution.

### Microbial necromass hydrolysis

`OMBioResdu(ielmc, M, K)` (M in 1..2, kinetic vs. recalcitrant) is hydrolyzed at rates `SPORC = (7.5, 1.5) g C g^-1 N h^-1` (`NitroPars.F90:210`) through the same `RHydrolysisScalCmpK` scalar (`MicBGCFGMod.F90:1528-1531`).

### Sorbed OM hydrolysis

`SorbedOM(idom, K)` is desorbed at rates `SPOHC = 0.25` (C) and `SPOHA = 0.25` (acetate) from `NitroPars.F90:207-208`, gated by the same activity scalar (`MicBGCFGMod.F90:1571-1575`).

## C:N:P stoichiometry and mineralization

Each microbial guild has pre-set maximum mass-based biomass N:C and P:C ratios, stored in `rNCOMC(ibiom, NGL, K)` and `rPCOMC(ibiom, NGL, K)` (`MicBGCPars.F90:329-366`). Defaults:

| Guild class | kinetic N:C | struct N:C | reserve N:C | kinetic P:C | struct P:C |
|---|---|---|---|---|---|
| Fungi (N = `mid_Aerob_Fungi`) | 0.15 | 0.09 | wt.avg. via `FL=(0.55,0.45)` | 0.015 | 0.009 |
| All other heterotrophs (bacteria, archaea) | 0.225 | 0.135 | wt.avg. | 0.0225 | 0.0135 |
| Autotrophs | 0.225 | 0.135 | wt.avg. | 0.0225 | 0.0135 |

The reserve N:C/P:C is computed by `DOT_PRODUCT(FL, rNCOMC(1:2,NGL,K))` (`MicBGCPars.F90:360-363`).

Biomass-level stoichiometry scalars (`MicBGCFGMod.F90:485-518`):

```
rCNBiomeActHeter(N,NGL,K) = max(mBiomeHeter(N,MID1,K)/mBiomeHeter(C,MID1,K), 0)
FCN(NGL,K) = min(1, max(0.5, sqrt(rCNBiomeActHeter(N)/rNCOMC(kin,NGL,K))))
FCP(NGL,K) = min(1, max(0.5, sqrt(rCNBiomeActHeter(P)/rPCOMC(kin,NGL,K))))
FBiomStoiScalarHeter(NGL,K) = min(FCN(NGL,K), FCP(NGL,K))
```

This "demand-side" scalar (floored at 0.5, capped at 1) multiplies the catabolic rate in every catabolism routine (e.g., `MicBGCFGMod.F90:2764`).

A "supply-side" scalar is then computed per substrate complex:

```
CNOMX = TOMEK(N,K) / tMaxNActMicrbK(K)
CPOMX = TOMEK(P,K) / tMaxPActMicrbK(K)
FCNK(K) = min(1, max(0.5, CNOMX))
FCPK(K) = min(1, max(0.5, CPOMX))
```

(`MicBGCFGMod.F90:1391-1398`). `FCNK` and `FCPK` relax the N:C/P:C requirement of the hydrolysis N and P fluxes (`MicBGCFGMod.F90:1444-1445`), allowing immobilization/mineralization consistent with the substrate's and microbe's stoichiometric state:

```
RHydlysSolidOM(N,M,K) = AZERO(SolidOM(N,M,K)) * dHyd / FCNK(K)
RHydlysSolidOM(P,M,K) = AZERO(SolidOM(P,M,K)) * dHyd / FCPK(K)
```

This produces the standard "immobilization when N/P limited, mineralization when N/P rich" behavior, since `1/FCNK >= 1` pulls in N when the substrate is N-poor, and vice versa after flux caps via `min(flux, pool)` at line 1448. The downstream aggregation in `AggregateTransfOMBioResdue` (`MicBGCFGMod.F90:2009-2377`) splits the net N/P flow between microbial biomass uptake and net release to mineral pools (`RNH4MicbReliz2Soil`, `RH2PO4MicbReliz2Soil`, `RNH4MicbReliz2Band`, etc., `MicBGCFGMod.F90:488-497` in `MicBGCAPI.F90` for the output packing).

Net mineralization diagnostics `NetNH4Mineralize` and `NetPO4Mineralize` from `micflx` are accumulated into annual totals at `MicBGCAPI.F90:504-505`.

## Catabolic pathways (per guild)

For each active heterotroph guild `N` in OM complex `K`, `ActiveHeterotrophsK` (`MicBGCFGMod.F90:917-1005`) dispatches to a pathway routine depending on the group's flags:

- `is_aerobic_hetr(N)` true: dispatches to `AerobicHeteroBactCatabolism` (N = `mid_HeterAerobBacter`, `mid_Facult_DenitBacter` in aerobic conditions, `mid_HeterAerobN2Fixer`) or `AerobicFungiCatabolism` (N = `mid_Aerob_Fungi`). Facultative denitrifiers also call `HeteroDenitrificCatabolism` when non-litter (`MicBGCFGMod.F90:971-974`).
- `is_anaerobic_hetr(N)` true and N = `mid_fermentor` or `mid_HeterAnaerobN2Fixer`: dispatches to `AcetogFermentCatabolism`.
- N = `mid_HeterAcetoCH4GenArchea`: dispatches to `AcetoMethanogenCatabolism`.

Each routine uses the Monod form on its specific substrate. For aerobic heterotrophs (`AerobicHeteroBactCatabolism`, `MicBGCFGMod.F90:2648-2816`):

```
FSBSTC = CDOC     / (CDOC     + OQKM)     ! OQKM = 12 g C m-3
FSBSTA = CAcetate / (CAcetate + OQKA)     ! OQKA = 12 g C m-3
RGOCY  = AZMAX1(FBiomStoiScalarHeter(NGL,K) * OMActHeter(NGL,K)) * VMXO * GrowthEnvScalHeter(NGL,K)
RGOCZ  = RGOCY * FSBSTC * FOCA(K)         ! FOCA = DOC fraction in DOC+Acet pool
RGOAZ  = RGOCY * FSBSTA * FOAA(K)
```

with `VMXO = 0.125 g C g^-1 C h^-1` (`NitroPars.F90:152`). The final uptake is `min(RGOCZ, RGOCX)` where `RGOCX = AZMAX1(DOM_doc * FOQC(NGL,K) * EO2Q)` is a kinetic cap (`MicBGCFGMod.F90:2769-2775`). `O2` demand is stoichiometric: `RO2Dmnd4RespHeter = 2.667 * RGOMP` corresponding to `CH2O + O2 -> CO2 + H2O` (`MicBGCFGMod.F90:2796`).

Growth respiration efficiencies (fraction of C uptake lost as CO2) are derived from empirical free-energy yields (`NitroPars.F90:214-220`):

```
EO2X = 1/(1 + GO2X/EOMC)    ! aerobic bacteria on DOC, EOMC = 25 kJ g-1 C, GO2X = 37.5 kJ g-1 C
EH4X = 1/(1 + GH4X/EOMC)    ! methanotrophs
EO2G = 1/(1 + GO2X/EOMG)    ! fungi,     EOMG = 37.5
EO2D = 1/(1 + GO2X/EOMD)    ! denitrif., EOMD = 37.5
```

The denitrifier catabolism (`HeteroDenitrificCatabolism`, `MicBGCFGMod.F90:3096-3435`) uses sequential Monod uptake on NO3, NO2, and N2O, with product-inhibition constants `VMKI = 0.25 g N m^-3` (`NitroPars.F90:187`). Methanogens (`AcetoMethanogenCatabolism`, `MicBGCFGMod.F90:2536-2645`) operate on acetate with `OQKAM = 12 g C m^-3` and specific rate `VMXCH4gAcet = 0.125^2 g C g^-1 C h^-1` (`NitroPars.F90:154,161`).

## Nitrification and chemodenitrification

Autotroph catabolism routines live in `MicAutoCplxFGMod.F90`:

- `AmmoniaOxidizerCatabolism` (`MicAutoCplxFGMod.F90:1256-1447`): NH3 -> NO2 by `mid_AutoAmmoniaOxidBacter`. Substrate Km = `ZHKM = 1.4 g N m^-3`, specific rate `VMXNH3Oxi = 0.375 h^-1`, efficiency `ECNH = 0.30` (`NitroPars.F90:156,164,183`).
- `NitriteOxidizerCatabolism` (`MicAutoCplxFGMod.F90:1447-1599`): NO2 -> NO3 by `mid_AutoNitriteOxidBacter`. Substrate Km = `ZNKM = 1.4 g N m^-3`, specific rate `VMXNO2Oxi = 0.25 h^-1`, efficiency `ECNO = 0.10`.
- `AeroMethanotrophCatabolism` (`MicAutoCplxFGMod.F90:1714-1905`): CH4 + O2 -> CO2, efficiency `ECHO = 0.75`, `VMXCH4OxiAero = 0.375`.
- `H2MethanogensCatabolism` (`MicAutoCplxFGMod.F90:1599-1714`): CO2 + H2 -> CH4.
- `AMOANME2dCatabolism`, `AMONC10Catabolism` (`MicAutoCplxFGMod.F90:1100-1447`): anaerobic methane oxidation coupled to NO3/NO2.

Nitrification inhibition uses `RNFNI = 2.0e-4`, decay of inhibitor field `ZNFNI_vr`, and NH3 product-inhibition `ZHKI = 7000 g N m^-3` (`NitroPars.F90:186`).

Non-biological (chemical) denitrification is handled in `ChemoDenitrification` (`MicBGCFGMod.F90:1009-1093`): a purely abiotic path reducing NO2 to N2O in both band and non-band zones as a function of Fe and pH, with rates summed into `RN2OChemoProd_vr` and `RNO2ReduxSoilChemo`.

## Microbial growth, maintenance, and turnover

- **Maintenance respiration** uses `RMOM = 0.010 g C g^-1 N h^-1` (`NitroPars.F90:209`), multiplied by biomass N and `TSensMaintR` in `CalcRespMaint` (`MicAutoCplxFGMod.F90:2371-2415` for autotrophs, and aggregated by each heterotroph catabolism routine via `RMOMK`).
- **Basal mortality / turnover** uses `SPOMC = (1.0e-2, 1.0e-3) h^-1` (`NitroPars.F90:211`), applied per biomass component (kinetic vs. structural). Dead biomass is routed into `OMBioResdu(C,1..ndbiomcp,K)`.
- **Growth allocation** between kinetic, structural, and reserve pools uses `FL = (0.55, 0.45)` for kinetic:structural, with reserves computed from the weighted mean; transfer from reserve/nonstructural to structural is rate-limited by `OMGR = 0.25 h^-1` (`NitroPars.F90:29,139`).
- **N2 fixation** by diazotroph heterotrophs (`mid_HeterAerobN2Fixer`, `mid_HeterAnaerobN2Fixer`): yield from C oxidation `EN2F(1:7)` with default `EN2X = GO2X/GN2X` (`NitroPars.F90:215`), `GN2X = 187.5 kJ g^-1 N`. Fixation flux feeds `Micb_N2Fixation_vr` (`MicBGCAPI.F90:501`).

## Priming and OM transfer between complexes

`OMTransferForPriming` (`MicBGCFGMod.F90:1096-1215`) moves DOM and microbial biomass between litter and non-litter complexes at rates:

- `FPRIM = 5.0e-2` for DOC/DON/DOP (`NitroPars.F90:27`, `NitroPars.F90:137`).
- `FPRIMM = 1.0e-6` for microbial biomass (`NitroPars.F90:28`, `NitroPars.F90:138`).

The direction (litter -> non-litter vs. reverse) is driven by concentration gradients and the substrate stoichiometric status.

## DOM sorption

`RDOMSorption` (`MicBGCFGMod.F90:1218-1305`) models linear sorption-desorption exchange between `DOM(idom, K)` and `SorbedOM(idom, K)`:

```
RDOMSorption ~ TSORP * (DOM / VLWatMicP - HSORP * SorbedOM / BulkSOMC)
```

with `TSORP = 0.5 h^-1` rate constant and `HSORP = 1.0` linear partition coefficient (`NitroPars.F90:110-111`, `205-206`). Sorbed OM is then subject to its own slow hydrolysis at `SPOHC = 0.25` (see SOM hydrolysis rate law above). This is a linear (Henry-type) isotherm, not Langmuir or Freundlich.

## Vertical mixing and disturbance

`DownwardMixOM` (`f90src/Microbial_bgc/Layers_Micmodel/SoilBGCNLayMod.F90:63-145`) applies `FracLitrMix` to mix litter C, N, P between adjacent layers L and L+1. Mixing rates depend on `FOSCZ0 = 2.0e-2 h^-1` at the surface and `FOSCZL = 2.0e-6 h^-1` in the subsurface (`NitroPars.F90:146-147`), invoked after the per-layer biogeochemistry finishes (`MicBGCAPI.F90:121-124`).

`SOMRemovalByDisturbance` (from `SoilDisturbMod`, called at `MicBGCAPI.F90:128`) applies instantaneous SOM removal events specified in the disturbance input file (fire, harvest). Combustion partitioning for N and P loss is set by `EFIRE(2, 21:22)` (`NitroPars.F90:118`).

## Calibration entry points

If tuning decomposition rates:

1. `SPOSC(jsken, jcplx)` (`MicBGCPars.F90:319-325`) for solid SOM specific hydrolysis rates.
2. `SPORC(1:2)` and `SPOMC(1:2)` (`NitroPars.F90:210-211`) for necromass and live-biomass turnover.
3. `SPOHC`, `SPOHA` (`NitroPars.F90:207-208`) for sorbed OM and acetate.
4. `DCKM0`, `DCKML`, `DCKI`, `OQKI` (`NitroPars.F90:132,140,148-149`) for the DOC-inhibited Monod on SOC.
5. `rNCOMC`, `rPCOMC`, `rNCOMCAutor`, `rPCOMCAutor` (`MicBGCPars.F90:334-386`) for microbial stoichiometry.
6. `VMXO`, `VMXF`, `VMXCH4gAcet`, `VMXNH3Oxi`, `VMXNO2Oxi`, `VMXCH4OxiAero`, `VMXCH4gH2` (`NitroPars.F90:152-158`) for per-pathway specific uptake rates.
7. `EOMC`, `EOMG`, `EOMD`, `EOMF`, `EOMH`, `EOMN` (`NitroPars.F90:190-195`) for growth-efficiency energetics.
8. `CNRH`, `CPRH` (`MicBGCPars.F90:299-300`) for SOC-complex default N:C and P:C ratios (5-element arrays indexed by complex K).

The `initNitroPars` routine (`NitroPars.F90:121-212`) first attempts `ReadPars()` from a NetCDF file (`micpar_file_in`) before falling back to the hard-coded defaults shown above, so a calibration driver should supply an override NetCDF rather than editing the source.

## Explicit-microbe vs. implicit-decomposition distinction

EcoSIM is unambiguously microbial-explicit. The living biomass `mBiomeHeter` and `mBiomeAutor` are prognostic state variables per layer per complex per guild. The SOM decomposition rate depends linearly on the active colonized biomass through `RHydrolysisScalCmpK = ROQC4HeterMicActCmpK/BulkSOMC`, so decomposition will stall if the microbial biomass collapses (e.g., after a disturbance) and rebuild as biomass recolonizes via `MicrobialLitterColonization` (`MicBGCFGMod.F90:1955-2006`). There is no first-order decay term that acts independent of microbes.

Initial microbial biomass is set up in `InitSOMBGCMod.F90:InitSOMVars` (`f90src/Microbial_bgc/Layers_Micmodel/InitSOMBGCMod.F90:66-411`) using `OMCK = 0.01 (fraction of init SOC as living biomass)` and per-guild allocations `OMCF`, `OMCA` (`MicBGCPars.F90:283-302`).
