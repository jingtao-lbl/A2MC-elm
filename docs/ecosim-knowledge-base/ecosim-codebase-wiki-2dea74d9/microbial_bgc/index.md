---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/{Microbial_bgc, Geochem}/`
**Last verified:** 2026-04-24
---

# Microbial Biogeochemistry Subsystem

EcoSIM's microbial subsystem implements explicit-pool decomposition with multiple microbial functional groups ("guilds") that compete for substrates, oxygen, and nutrients. Unlike lumped first-order decomposition models (CENTURY-style), the living microbial biomass is an explicit state variable driving decomposition kinetics through mass-action and transport-based Michaelis-Menten formulations.

Source code lives in two sub-directories under `f90src/Microbial_bgc/`:

- `Box_Micmodel/` is the per-layer ("box") biogeochemistry, operating on a single soil layer at a time.
- `Layers_Micmodel/` handles multi-layer coordination, initial condition setup, and vertical mixing.

## Source files

### `f90src/Microbial_bgc/Box_Micmodel/`

| File | Role |
|---|---|
| `MicBGCFGMod.F90` | Main per-layer heterotroph biogeochemistry. Contains `SoilBGCOneLayer`, `SolidOMDecomposition`, `StageBGCEnvironCondition`, priming, sorption, and the aerobic/anaerobic/fermentation/denitrification catabolism routines. |
| `MicAutoCplxFGMod.F90` | Per-layer autotroph biogeochemistry: ammonia oxidizers, nitrite oxidizers, aerobic methanotrophs, hydrogenotrophic methanogens, and the anaerobic methane oxidizers AMO-ANME2D and AMO-NC10. |
| `MicStateTraitTypeMod.F90` | Derived type `micsttype` holding per-layer microbial and substrate state (DOM, SolidOM, OMBioResdu, mBiomeHeter, mBiomeAutor, mineral nutrient pools). |
| `MicFluxTypeMod.F90` | Derived type `micfluxtype` holding per-layer flux arrays (uptake demands, mineralization, hydrolysis rates, N2 fixation). |
| `MicForcTypeMod.F90` | Derived type `micforctype` holding per-layer forcing input (soil water potential, temperature, mass volumes, previous-step demand arrays). |
| `MicrobeDiagTypes.F90` | Derived types for per-guild and per-complex diagnostic and intermediate state: `Microbe_State_type`, `Microbe_Flux_type`, `OMCplx_State_type`, `OMCplx_Flux_type`, `Microbe_Diag_type`, `Cumlate_Flux_Diag_type`. |
| `MicrobMathFuncMod.F90` | Two reusable kinetic helpers: `MicrobPhysTempFun` (growth + maintenance temperature sensitivity) and `TranspBasedsubstrateUptake` (diffusion-limited Michaelis-Menten). |

### `f90src/Microbial_bgc/Layers_Micmodel/`

| File | Role |
|---|---|
| `SoilBGCNLayMod.F90` | Cross-layer utilities: vertical litter mixing (`DownwardMixOM`) plus per-layer OM/DOM/biomass summation routines used by the API layer and diagnostics. |
| `InitSOMBGCMod.F90` | Initial condition setup: partitions site-level SOC into kinetic components (protein, carbohydrate, cellulose, lignin), seeds microbial biomass and sorbed/dissolved OM at each layer, and applies litterfall-derived microbial additions. |

## Entry point

The calling sequence is driven from `f90src/APIs/MicBGCAPI.F90`.

- Public routine `MicrobeModel(I,J,NHW,NHE,NVN,NVS)` is the external entry used by the time-stepper (`f90src/APIs/MicBGCAPI.F90:78`). It loops over grid columns and layers, and for each valid-water layer either dispatches to `MicBGC1Layer` (litter layer or the top active soil layer) or zeros out layer-level microbial uptake arrays.
- `MicBGC1Layer(I,J,L,NY,NX)` packs grid-state into the `micfor`, `micstt`, `micflx` transfer types via `MicAPISend`, calls the core solver `SoilBGCOneLayer` (from `MicBGCFGMod`), and unpacks results via `MicAPIRecv` (`MicBGCAPI.F90:139-152`).
- Downward litter mixing and disturbance-driven SOC removal are applied after the layer loop (`MicBGCAPI.F90:121-128`).

The reverse call order is:

```
Driver -> MicrobeModel -> MicBGC1Layer -> SoilBGCOneLayer -> {
    StageBGCEnvironCondition,
    ActiveMicrobes -> ActiveHeterotrophsK -> {AerobicHeteroBactCatabolism,
                                              AerobicFungiCatabolism,
                                              AcetogFermentCatabolism,
                                              HeteroDenitrificCatabolism,
                                              AcetoMethanogenCatabolism},
    ActiveMicrobes -> ActiveAutotrophs -> {AmmoniaOxidizerCatabolism,
                                            NitriteOxidizerCatabolism,
                                            AeroMethanotrophCatabolism,
                                            H2MethanogensCatabolism,
                                            AMOANME2dCatabolism,
                                            AMONC10Catabolism},
    ChemoDenitrification,
    OMTransferForPriming,
    SolidOMDecomposition,
    RedistDecompProduct,
    RDOMSorption,
    AutotrophAnabolicUpdate,
    HeterotrophAnabolicUpdate,
    MicrobialLitterColonization,
    AggregateTransfOMBioResdue
}
```

See `f90src/Microbial_bgc/Box_Micmodel/MicBGCFGMod.F90:67-153` for the top-level orchestration.

## Microbial functional groups

Functional groups are split into a heterotroph family (one instance per organic-matter complex `K`) and an autotroph family (one global instance per layer). Group IDs (`mid_*`) are assigned in `f90src/ModelPars/MicBGCPars.F90:186-200`.

Heterotrophs (`NumMicbFunGrupsPerCmplx = 7`, `MicBGCPars.F90:186-192`, `Modelconfig/EcoSIMConfig.F90:23`):

| ID | `mid_*` symbol | Short name (`hmicname`) | Physiology |
|---|---|---|---|
| 1 | `mid_HeterAerobBacter` | `aerohetrob` | Obligate aerobic heterotrophic bacteria (DOC+O2 -> biomass+CO2) |
| 2 | `mid_Facult_DenitBacter` | `faculdenit` | Facultative denitrifier bacteria (DOC+O2 aerobic; DOC+NO3/NO2/N2O anaerobic) |
| 3 | `mid_Aerob_Fungi` | `aerofungi` | Aerobic fungi (DOC+O2; separate N:C and P:C stoichiometry from bacteria) |
| 4 | `mid_fermentor` | `aneroferm` | Anaerobic fermenters (DOC -> acetate + H2) |
| 5 | `mid_HeterAcetoCH4GenArchea` | `acetmethg` | Acetoclastic methanogens (acetate -> CH4 + CO2) |
| 6 | `mid_HeterAerobN2Fixer` | `aeron2fix` | Aerobic free-living N2-fixing heterotrophs |
| 7 | `mid_HeterAnaerobN2Fixer` | `aneron2fix` | Anaerobic free-living N2-fixing heterotrophs |

`is_aerobic_hetr`, `is_anaerobic_hetr` flags (`MicBGCPars.F90:220-226`) drive dispatch in `ActiveHeterotrophsK`.

Autotrophs (shared slot count `NumMicbFunGrupsPerCmplx = 7`, but only 6 occupied, `MicBGCPars.F90:195-200`):

| ID | `mid_*` symbol | Short name (`amicname`) | Physiology |
|---|---|---|---|
| 1 | `mid_AutoAmmoniaOxidBacter` | `amoniaoxib` | Aerobic NH3 -> NO2 (nitrification step 1) |
| 2 | `mid_AutoNitriteOxidBacter` | `nititeoxib` | Aerobic NO2 -> NO3 (nitrification step 2) |
| 3 | `mid_AutoAeroCH4OxiBacter` | `aeromethtp` | Aerobic CH4 -> CO2 methanotrophs |
| 4 | `mid_AutoAMOANME2D` | (none) | Anaerobic methanotroph ANME-2d (NO3/NO2 coupled CH4 oxidation) |
| 5 | `mid_AutoH2GenoCH4GenArchea` | `hydromethg` | Hydrogenotrophic methanogens (CO2 + H2 -> CH4) |
| 6 | `mid_AutoAMONC10` | (none) | Anaerobic methanotroph NC10 (NO2-driven CH4 oxidation) |

The four `is_CO2_autotroph` groups (`MicBGCPars.F90:247-250`) that fix inorganic C for biomass are the two nitrifiers, the hydrogenotrophic methanogen, and AMO-NC10; aerobic and ANME-2d methanotrophs use CH4 as carbon source.

Per-guild count within each functional group is set by `NumGuild_*` module parameters (`MicBGCPars.F90:14-26`), defaulting to 1 each. Each layer therefore holds `NumHetetr1MicCmplx = sum(FG_guilds_heter) = 7` heterotroph guilds replicated over `jcplx = 5` OM complexes, plus `NumMicrobAutoTrophCmplx = sum(FG_guilds_autor) = 6` autotroph guilds.

## SOM pool structure

EcoSIM carries five organic matter "complexes" (`jcplxc = 5`, `EcoSIMConfig.F90:21`), indexed by `K`, defined in `MicBGCPars.F90:139-153` and named via `cplxname`:

| K | Symbol | `cplxname` | Meaning |
|---|---|---|---|
| 1 | `k_woody_comp` | `woodylitr` | Woody plant litter |
| 2 | `k_fine_comp` | `folialitr` | Fine (non-woody) plant litter |
| 3 | `k_manure` | `manure` | Animal manure and other applied organic residues |
| 4 | `k_POM` | `pom` | Particulate organic matter |
| 5 | `k_humus` | `humus` | Humified organic matter |

The first three (`NumOfLitrCmplxs = k_manure = 3`) are litter and are colonized from litterfall; the last two are post-humification mineral-associated pools that do not receive direct litterfall but accept decomposition products from litter.

Each complex is further resolved into `jskenc = 4` kinetic components (`EcoSIMConfig.F90:20`, `MicBGCPars.F90:146-158`, `kiname`):

| M | Symbol | Meaning |
|---|---|---|
| 1 | `iprotein` | Protein (fastest-cycling) |
| 2 | `icarbhyro` | Carbohydrates and other soluble C |
| 3 | `icellulos` | Cellulose |
| 4 | `ilignin` | Lignin (slowest-cycling) |

Solid SOM is stored as `SolidOM(NE,M,K,L,...)` where `NE` runs over the plant chemical elements (C, N, P) through `NumPlantChemElms` (`MicStateTraitTypeMod.F90:76-80`). Additional per-layer state carried in `micsttype`:

- `OMBioResdu(NE, 1:ndbiomcp, 1:K)` for microbial necromass, with `ndbiomcp = NumDeadMicrbCompts = 2` components (`MicBGCPars.F90:178-179`, `micresb = {'kinetic','recalcitrant'}`).
- `SorbedOM(idom_beg:idom_end, K)` for mineral-sorbed dissolved OM.
- `DOM(idom, K)` for dissolved OM (DOC, DON, DOP, acetate; indexed by `idom_*` from `TracerIDMod`).
- `mBiomeHeter(NE, 1:NumLiveHeterBioms, K)` for heterotroph living biomass, with `NumLiveMicrbCompts = 3` components per guild (`kinetic`, `recalcitrant`/structural, `reserve`; see `ibiom_kinetic=1`, `ibiom_struct=2`, `ibiom_reserve=3` in `Modelconfig/ElmIDMod.F90:13-15`).
- `mBiomeAutor(NE, 1:NumLiveAutoBioms)` for autotroph living biomass.
- `SolidOMAct(M, K)` tracks the colonized (enzymatically accessible) fraction of `SolidOM`, which is what enters the decomposition rate law.

## Pool transitions at a glance

Litter layer (K in 1..3):
- Each kinetic fraction `SolidOM(:,M,K)` is hydrolyzed by heterotroph activity into DOM via `SolidOMDecomposition` (`MicBGCFGMod.F90:1388-1507`).
- A fraction `EPOC` of each hydrolysis flux is diverted into `k_POM` humification via `RHumifySolidOM` using the N:C and P:C ratios `CNRH(k_POM)`, `CPRH(k_POM)` as gates (`MicBGCFGMod.F90:1470-1497`). The lignin flux sets the cap, and protein/carbohydrate/cellulose are co-humified up to 10 percent of the lignin humification flux.
- The rest becomes DOM (`RDecmpProdDOM`, `MicBGCFGMod.F90:1486-1487`).

Non-litter complexes (K = `k_POM`, `k_humus`):
- Hydrolysis runs identically, but no humification step applies; all hydrolysis flux goes straight to DOM (`MicBGCFGMod.F90:1490-1497`).
- Priming transfer (`OMTransferForPriming`, `MicBGCFGMod.F90:1096-1215`) moves DOM between litter and non-litter K via rate constants `FPRIM` (nonstructural) and `FPRIMM` (microbial biomass) defined in `NitroPars.F90:27-28`.

Sorbed OM:
- `RDOMSorption` (`MicBGCFGMod.F90:1218-1305`) exchanges DOM with `SorbedOM` using sorption constants `TSORP` (rate, h^-1) and `HSORP` (capacity) from `NitroPars.F90:110-111`.
- `RHydlysSorptOM` desorbs back to DOM at rate `SPOHC` (C), `SPOHA` (acetate) from `NitroPars.F90:112-113`.

## Where to go next

- `decomposition_and_som.md` in this directory has the kinetic rate laws, Q10-like temperature function, water potential stress function, C:N:P stoichiometry handling, and citations to line numbers.
- `f90src/ModelPars/NitroPars.F90` and `f90src/ModelPars/MicBGCPars.F90` are the authoritative sources for calibratable parameters (rate constants, half-saturation Km, microbial N:C/P:C ratios, SPOSC decomposition rate constants).
- `f90src/APIs/MicBGCAPI.F90` is the only coupling surface to the rest of EcoSIM; look there first when tracing how plant or hydrology state reaches the microbial model.
