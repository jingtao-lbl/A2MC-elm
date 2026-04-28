---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/{Plant_bgc, Prescribed_pheno}/`
**Last verified:** 2026-04-24
---

# Growth and C/N/P Allocation

Growth in EcoSIM is driven by non-structural C (and N, P) pools held in leaves, petiole-
sheath, stalk, stalk reserve, and roots. Partitioning among organs is determined by the
**current phenological stage** (stored in `iPlantCalendar_brch`) and is modulated by
turgor, temperature, stoichiometric feedbacks, and (for trees) sapwood-to-total-stalk
ratios. A growth "yield" converts non-structural C consumption into actual organ
biomass, with the balance appearing as growth respiration.

The model is **source-driven**: gross photosynthesis fills the non-structural C pool,
maintenance respiration is paid first, any surplus is multiplied by turgor and by
nutrient-ratio constraints before being partitioned to organs. When the maintenance bill
cannot be met, the difference drives remobilization and senescence (see §6).

## 1. Entry points and call order

The high-level entry is `GrowPlants` (`f90src/Plant_bgc/GrosubsMod.F90:51-109`). For each
active PFT it calls:

| Step | Routine | Purpose |
|---|---|---|
| 1 | `GrowOnePlant` (`GrosubsMod.F90:238-306`) | Per-PFT driver |
| 1a | `StagePlantForGrowth` (`GrosubsMod.F90:309-514`) | Compute wood fractions, temperature functions, water stress, turgor |
| 1b | `GrowOneBranch` (`PlantBranchMod.F90:35`) | Per-branch growth and respiration |
| 1c | `RootBGCModel` (`RootMod.F90:24`) | Per-plant root growth |
| 1d | `PlantNonstElmTransfer` (`PlantNonstElmDynMod.F90`) | Translocate non-structural pools shoot <-> root <-> seasonal storage |
| 2 | `RemoveBiomassByDisturbance` (`PlantDisturbsMod.F90:261`) | Apply harvest/grazing/tillage/fire |
| 3 | `ResetDeadPlant` (`LitterFallMod.F90:18`) | Reset dead-branch state |
| 4 | `AccumulateStates` (`GrosubsMod.F90:517-647`) | Sum into PFT and site accumulators |
| 5 | `LiveDeadTransformation` (`GrosubsMod.F90:112-235`) | Move senesced biomass to standing dead, decay standing dead to litter |

## 2. Organ pools: morphological units

Branch morph-unit ids (declared in `f90src/Modelconfig/ElmIDMod.F90`) are:

| Id | Name | Canonical organ |
|---|---|---|
| `ibrch_leaf` | leaf | lamina |
| `ibrch_petole` | petiole/sheath | petiole + sheath |
| `ibrch_stalk` | stalk | structural stem/woody stalk |
| `ibrch_resrv` | reserve | stalk reserve (fast in-branch non-structural pool) |
| `ibrch_husk` | husk | reproductive husk |
| `ibrch_ear` | ear | reproductive ear/cone |
| `ibrch_grain` | grain | seed/grain |

`NumOfPlantMorphUnits` (declared via `pltpar`) equals 7. Roots and mycorrhizae live
outside this enumeration in their own primary/secondary axes tree (see §7).

Element indices: `ielmc=1` (C), `ielmn=2` (N), `ielmp=3` (P). `NumPlantChemElms=3`.

## 3. Wood vs non-wood fractionation (pre-allocation)

Before allocation, `StagePlantForGrowth` (`GrosubsMod.F90:309-514`) computes for each PFT
the fraction of leaf, petiole-sheath, stalk, and root mass that behaves as "wood" vs
"fine litter". Key arrays in `plt_allom` (`GrosubsMod.F90:360-365`):

- `FracLeafShethElmAlloc2Litr(NE, k_fine_comp|k_woody_comp)` — leaf/sheath fraction to
  fine-litter vs coarse-woody litter complex on senescence.
- `FracWoodStalkElmAlloc2Litr(...)` — stalk fraction.
- `FracRootElmAllocm(...)` — root fraction.
- `FracPetolShethAlloc2Litr(...)` — petiole-sheath fraction (takes the same C pattern as
  leaf/sheath).

The **tree branch** of this logic reduces the wood fraction with the sapwood/stalk ratio
(`GrosubsMod.F90:398-407`):

```
FracWoodStalkElmAlloc2Litr(ielmc, k_fine_comp) = min(sqrt(CanopySapwoodC_pft / StalkStrutElms_pft), 1)
FracRootElmAllocm    (ielmc, k_fine_comp)      = min((CanopySapwoodC_pft / StalkStrutElms_pft)^(1/6), 1)
```

For non-tree or non-woody PFTs all fractions default to 1 (pure fine litter)
(`GrosubsMod.F90:393-397`).

The weighted N:C and P:C ratios of new growth are then

```
CNLFW = FracLeafShethElmAlloc2Litr(ielmc,woody)*rNCStalk + FracLeafShethElmAlloc2Litr(ielmc,fine)*rNCLeaf     (GrosubsMod.F90:422)
CPLFW = ... using rPCStalk and rPCLeaf                                                                       (GrosubsMod.F90:423)
CNSHW/CPSHW = similar for petiole-sheath using rNCSheath/rPCSheath                                           (GrosubsMod.F90:424-425)
CNRTW/CPRTW = ... for root using rNCRoot/rPCRootr                                                            (GrosubsMod.F90:426-427)
```

This means a woody PFT allocates new leaf C at a stoichiometry that blends **leaf N:C
and stalk N:C**, with the mixing fraction equal to the current wood fraction of the
leaf/sheath pool. Physically this represents the fact that leaves on trees accrete a
structural woody component (mid-rib, stipules, sapwood junction) that dilutes true leaf
stoichiometry.

## 4. Allocation logic inside a branch (CalcPartitionCoeff)

All growth-stage allocation is in `CalcPartitionCoeff`
(`f90src/Plant_bgc/PlantBranchMod.F90:538-788`). It fills the seven-element array
`PART(1:NumOfPlantMorphUnits)`.

The allocation scheme is **prescribed-by-stage, not sink-source**. Stages are recognized
via `iPlantCalendar_brch(ipltcal_*, NB, NZ)` which becomes non-zero on the day the stage
is reached.

### Stage A: before floral initiation (vegetative)
(`PlantBranchMod.F90:596-602`)

```
PART(ibrch_leaf)   = 0.725
PART(ibrch_petole) = 0.275
```

### Stage B: pre-anthesis (reproductive initiation)
(`PlantBranchMod.F90:606-614`)

```
PART(ibrch_leaf)   = max(PART2LEAF_MIN,   0.725 - FPART1 * TotalNodeNumNormByMatgrp_brch)
PART(ibrch_petole) = max(PART2PETOL_MIN,  0.275 - FPART2 * TotalNodeNumNormByMatgrp_brch)
remaining PARTS = 1 - PART(leaf) - PART(petiole):
  PART(ibrch_stalk) = 0.60 * PARTS
  PART(ibrch_resrv) = 0.30 * PARTS
  PART(ibrch_husk)  = 0.05 * PARTS   (0.5 of the 10% leftover)
  PART(ibrch_ear)   = 0.05 * PARTS
```

Here `FPART1=1.00`, `FPART2=0.40` (local parameters at
`PlantBranchMod.F90:555-556`) and `TotalNodeNumNormByMatgrp_brch` is the
maturity-group-normalized vegetative node count, so higher-maturity PFTs keep more C in
leaves for longer.

### Stage C: pre-grain-fill (post-anthesis)
(`PlantBranchMod.F90:620-635`)

Determinate PFTs set `PART(leaf)=PART(petiole)=0` (no more vegetative growth).
Indeterminate PFTs keep a residual leaf/petiole fraction scaled by
`1-TotReproNodeNumNormByMatrgrp_brch`, then allocate the same stalk/reserve/husk/ear
split as Stage B.

### Stage D: during grain filling
(`PlantBranchMod.F90:639-660`)

```
if determinate:
  PART(ibrch_grain) = 1.0
elif annual:
  PART(leaf)=PART2LEAF_MIN, PART(petiole)=PART2PETOL_MIN
  PARTS = 1 - PART(leaf) - PART(petiole)
  PART(stalk)=0.125*PARTS, PART(husk)=0.125*PARTS, PART(ear)=0.125*PARTS, PART(grain)=0.625*PARTS
else (perennial):
  PART(stalk)=0.75*PARTS, PART(grain)=0.25*PARTS
```

Perennials thus reinvest a majority of late-season C in structural stalk instead of
grain.

### Stage E: post-grain-fill (senescence)
(`PlantBranchMod.F90:665-678`)

If all above-ground biomass turns over (`iPlantTurnoverPattern_pft==0`) and seed fill
has ended, annuals zero out reserve/stalk/grain allocation; perennials fold the stalk
allocation into reserve (`PART(resrv) += PART(stalk); PART(stalk) = 0`). This is the
mechanism by which perennials refill their overwintering reserve.

### Reserve buffer
(`PlantBranchMod.F90:680-710`)

After the stage logic, allocation is rebalanced against the reserve/sapwood ratio:
when `StalkRsrvElms_brch(ielmc) < XFRX * SapwoodBiomassC_brch`, 10% of every other
organ's allocation is diverted to reserve; conversely if reserve exceeds sapwood mass,
the excess is pushed back to stalk. This keeps the reserve pool proportional to
structural sapwood and serves as a slow-turnover buffer against short-term C deficits.

## 5. Non-structural C consumed in growth (BranchBiomAllocate)

`BranchBiomAllocate` (`PlantBranchMod.F90:313-421`) executes the computed partitioning.
The central equations (`PlantBranchMod.F90:361-369`) are:

```
Growth_brch(ielmc, ibrch_leaf)   = RNonstC4Groth_brch * PART(ibrch_leaf)   * DMLFB
Growth_brch(ielmc, ibrch_petole) = RNonstC4Groth_brch * PART(ibrch_petole) * DMSHB
Growth_brch(ielmc, ibrch_stalk)  = RNonstC4Groth_brch * PART(ibrch_stalk)  * StalkBiomGrowthYld_pft
Growth_brch(ielmc, ibrch_resrv)  = RNonstC4Groth_brch * PART(ibrch_resrv)  * ReserveBiomGrowthYld_pft
Growth_brch(ielmc, ibrch_husk)   = RNonstC4Groth_brch * PART(ibrch_husk)   * HuskBiomGrowthYld_pft
Growth_brch(ielmc, ibrch_ear)    = RNonstC4Groth_brch * PART(ibrch_ear)    * EarBiomGrowthYld_pft
Growth_brch(ielmc, ibrch_grain)  = RNonstC4Groth_brch * PART(ibrch_grain)  * GrainBiomGrowthYld_pft
```

`RNonstC4Groth_brch` is the total non-structural C used in growth respiration + growth
for the branch (computed in `ComputRAutoAfEmergence`, see §6). The `*BiomGrowthYld_pft`
coefficients are the **growth yields** read from the PFT file (non-structural C used per
unit structural C produced; values are < 1 and the shortfall is growth respiration).
`DMLFB` and `DMSHB` are locally computed leaf/petiole yield coefficients that depend on
etoliation and node development.

N and P growth follows the same `PART`-weighted partition but scaled by the computed
N:C and P:C ratios `fNCLFW_brch`, `CNSHB`, `rNCStalk_pft`, `rNCReserve_pft`, etc.
(`PlantBranchMod.F90:372-391`):

```
Growth_brch(ielmn, ibrch_leaf) = Growth_brch(ielmc, ibrch_leaf) * fNCLFW_brch(NB,NZ)
Growth_brch(ielmn, ibrch_stalk)= Growth_brch(ielmc, ibrch_stalk)* rNCStalk_pft(NZ)
... etc.
```

`fNCLFW_brch` (`PlantBranchMod.F90:371`) uses the leaf-specific N:C as modulated by
`ZPLFM` and `ZPLFD*CNPG` (internal non-structural N availability and the combined
N,P-status coefficient `CNPG`), so leaves can be constructed N-rich or N-poor depending
on branch nutrient status. Stalk/reserve/husk/ear/grain N and P are calculated against
**fixed** PFT-level stoichiometric ratios from the parameter file.

Each new-growth element flux is added to the running pool
(`PlantBranchMod.F90:394-400`):

```
LeafStrutElms_brch(NE, NB, NZ)       += Growth_brch(NE, ibrch_leaf)
PetolShethStrutElms_brch(NE, NB, NZ) += Growth_brch(NE, ibrch_petole)
StalkStrutElms_brch(NE, NB, NZ)      += Growth_brch(NE, ibrch_stalk)
StalkRsrvElms_brch(NE, NB, NZ)       += Growth_brch(NE, ibrch_resrv)
... etc.
```

## 6. Maintenance + growth respiration (ComputRAutoAfEmergence)

`ComputRAutoAfEmergence` (`PlantBranchMod.F90:3047-3242`) and its pre-emergence twin
`ComputRAutoB4Emergence` (`PlantBranchMod.F90:3243-3445`) convert the non-structural C
pool into respiration + growth.

### N/P constraint on respiration
(`PlantBranchMod.F90:3116-3126`)

```
CNG  = CZPOL / (CZPOL + CCPOL * CNKI)
CPG  = CPPOL / (CPPOL + CCPOL * CPKI)
CNPG = min(CNG, CPG)
```

where `CZPOL`, `CCPOL`, `CPPOL` are the branch non-structural N, C, P concentrations
(`LeafPetoNonstElmConc_brch(ielmn|ielmc|ielmp, NB, NZ)`) and `CNKI`, `CPKI` are the
N and P inhibition constants. `CNPG` enters the respiration rate as a linear
multiplier: low non-structural N:C or P:C depresses oxidation of non-structural C.

### Respiration from non-structural C
(`PlantBranchMod.F90:3131-3133`)

```
RCO2NonstC_brch = VMXC * CanopyNonstElms_brch(ielmc, NB, NZ)
                  * fTCanopyGroth_pft(NZ) * CNPG
                  * GrainFillDowreg_brch(NB, NZ) * WaterStress4Groth
```

This is the gross oxidation of non-structural C. `VMXC` is a specific rate constant
(h^-1), `fTCanopyGroth_pft` is a 25-degC-normalized canopy-temperature growth function
(see `PlantMathFuncMod.F90`), `GrainFillDowreg_brch` is a down-regulation on C4
photosynthesis that also feeds back into respiration, and `WaterStress4Groth` is the
canopy-water-potential growth function.

### Maintenance respiration
(`PlantBranchMod.F90:3145-3150`)

```
RCO2Maint_brch = max(0, RmSpecPlant * TFN5 * ShootStructN_brch)
if bryophyte or drought-deciduous:
    RCO2Maint_brch *= WaterStress4Groth
```

`RmSpecPlant` is a species-level maintenance-respiration coefficient (units: gC per gN
structural per h at 25 degC). `TFN5` is the Arrhenius-with-inactivation temperature
function from `calc_plant_maint_tempf` (`PlantMathFuncMod.F90:163-174`):

```
RTK   = R_gas * TKCM                 ! R=8.3143 J/mol/K
STK   = 710.0 * TKCM
ACTVM = 1 + exp((195000 - STK)/RTK) + exp((STK - 232500)/RTK)
TFN5  = exp(25.214 - 62500/RTK) / ACTVM
```

with 62,500 J/mol activation energy and 195,000 / 232,500 J/mol low- and high-T
inactivation enthalpies; commented header "8.3143, 710.0 = gas constant, enthalpy" at
`GrosubsMod.F90:458-461`. `ShootStructN_brch` is the **branch-total structural N mass**,
reflecting the convention that maintenance respiration scales with N content rather than
C content.

### Growth respiration
(`PlantBranchMod.F90:3158-3170`)

```
RCO2X       = RCO2NonstC_brch - RCO2Maint_brch
RCO2Y       = max(0, RCO2X) * TurgEff4CanopyResp
RMxess_brch = max(0, -RCO2X)                 ! drives remobilization/senescence
```

`TurgEff4CanopyResp` comes from `fRespWatSens` (`PlantMathFuncMod.F90`) which maps
leaf-petiole turgor (`PSICanopyTurg_pft - TurgPSIMin4OrganExtens`) into a
[0,1] growth-respiration multiplier. Growth respiration that cannot be supported by
available non-structural N/P is further trimmed:

```
RFN1 = ZPOOLB * YCO2Gro_brch / (CNSHX + CNLFM + CNLFX * CNPG)
RFP1 = PPOOLB * YCO2Gro_brch / (CPSHX + CPLFM + CPLFX * CNPG)
RgroCO2_ltd = min(RCO2Y, min(RFN1, RFP1))
```

The key quantity used in §5 is then derived from the limited growth respiration
(`PlantBranchMod.F90:3202-3208`):

```
RNonstC4Groth_brch         = RgroCO2_ltd / YCO2Gro_brch
CanopyNonstElm4Gros(ielmn) = min(CanopyNonstElms_brch(ielmn,NB,NZ),
                                 RNonstC4Groth_brch * (CNSHX + CNLFM + CNLFX*CNPG))
CanopyNonstElm4Gros(ielmp) = min(CanopyNonstElms_brch(ielmp,NB,NZ),
                                 RNonstC4Groth_brch * (CPSHX + CPLFM + CPLFX*CNPG))
```

Here `YCO2Gro_brch` is the canopy respiration quotient (total biomass per unit
respiration); `CNSHX`, `CNLFM`, `CNLFX`, `CPSHX`, `CPLFM`, `CPLFX` are leaf/non-leaf
min/range N:C and P:C boundaries used to cap stoichiometric cost (set in
`UpdateBranchAllometry`, `PlantBranchMod.F90:422-537`).

### Excess maintenance respiration

When `RCO2NonstC_brch < RCO2Maint_brch`, `RMxess_brch` records the deficit. It is later
consumed by:
- `RemobilizeBranch` (`PlantBranchMod.F90:3706-3877`) — withdraws C, N, P from leaves,
  petiole-sheath, stalk-reserve, and stalk to pay the deficit,
- `SenescenceBranch` (`PlantBranchMod.F90:3878-4096`) — if remobilization is
  insufficient, kills lowest leaf/petiole nodes, moves their un-remobilized fraction
  to fine or woody litter complexes at stoichiometry-matched fractions.

Non-structural C, N, P used by these processes are accumulated into
`LitrFallElms_brch` and `LitrfallElms_pvr` (the per-soil-layer flux sent to
`LitterFallMod`).

## 7. Root-side allocation (RootBGCModel)

Root growth is structurally parallel to branch growth but uses a different topology.
`RootBGCModel` (`RootMod.F90:24-142`) receives:

- `TFN6_vr(L)` — soil-layer temperature function for root maintenance respiration.
- `CNRTW`, `CPRTW` — wood-weighted N:C, P:C for root structural growth
  (from `StagePlantForGrowth`, `GrosubsMod.F90:426-427`).
- `RootSinkC_vr`, `RootSinkC` — output sink-strength arrays used by
  `PlantNonstElmTransfer` to send non-structural C downward.

Internally it calls `RootBiochemistry` (`RootMod.F90:143-249`), which computes
respiration and growth for each primary axis (`NumAxesPerPrimRoot_pft`) and each soil
layer `L`. The **number of primary root axes per plant** is set in
`StagePlantForGrowth` (`GrosubsMod.F90:478-487`) using a size-dependent allometric rule
akin to Shinozaki et al. (1964) pipe-model theory (explicit comment in the code,
`GrosubsMod.F90:475-477`):

```
RootBiomCPerPlant_pft(NZ) = max(0.99999 * RootBiomCPerPlant_pft(NZ),
                                 RootElms_pft(ielmc,NZ) / PlantPopulation_pft(NZ))
if annual:
    NumAxesPerPrimRoot_pft = max(1, RootBiomCPerPlant_pft^0.833) * PlantPopulation_pft
elif woody vascular:
    NumAxesPerPrimRoot_pft = max(1, RootBiomCPerPlant_pft^0.7143) * PlantPopulation_pft  ! 1/1.4
else (herbaceous perennial):
    NumAxesPerPrimRoot_pft = max(1, RootBiomCPerPlant_pft^1.053)  * PlantPopulation_pft  ! 1/0.95
```

Root primary elongation (`Grow1stRootAxes`, `RootMod.F90:1529-1700`), secondary axis
branching (`Grow2ndRootAxes`, `RootMod.F90:451-756`), and mycorrhizal-axis growth
(`GrowRootMycoAxes`, `RootMod.F90:925-1120`) all share the same non-structural-pool /
respiration / growth-yield pattern as branches, but the allocation fraction is
determined by per-layer sink strength (turgor, water availability, temperature, O2).
Root-layer respiration is further constrained by `RAutoRootO2Limter_rpvr` (O2
availability) and `fRootGrowPSISense` (root water-potential sensitivity).

Primary-root remobilization (`RemobilizePrimeRoots`, `RootMod.F90:2406-2609`) and
primary-root withdrawal (`PrimeRootsWithdraw`, `RootMod.F90:2763-2956`) are the root-side
analogs of branch remobilization and senescence.

## 8. Non-structural pools and translocation

Pools:

| Pool | Variable | Location |
|---|---|---|
| Leaf-petiole non-structural | `CanopyNonstElms_brch(NE, NB, NZ)` | In each branch |
| Stalk reserve | `StalkRsrvElms_brch(NE, NB, NZ)` | In each branch |
| Seasonal storage | `SeasonalNonstElms_pft(NE, NZ)` | Per PFT (overwintering) |
| Root non-structural | Embedded in primary/secondary root state | Per soil layer, per axis |

`PlantNonstElmTransfer` (`PlantNonstElmDynMod.F90`) moves material among these:

- **`SeasonStoreShootTransfer`** — seasonal storage → leaf/petiole at leafout, at rate
  `RateK4ShootSeaStoreNonstEXfer` per hour (parameter declared in `GrosubsMod.F90`
  header, commented).
- **`StalkRsrvShootNonstTransfer`** — stalk reserve ↔ leaf/petiole, at rate
  `FXFY`/`FXFZ`.
- **`StalkRsrvRootNonstTransfer`** — root-side analog.
- **`RepleteLowSeaStorByRoot`** — roots push non-structural C up into seasonal storage
  when seasonal storage is below threshold (supports perennial overwintering).
- **`RepleteSeaStoreByStalk`** — stalk reserve pushes into seasonal storage at
  end-of-season.

The reserve/storage buffering logic (§4) plus these transfers give EcoSIM a three-level
non-structural hierarchy: fast (leaf-petiole), medium (stalk reserve), slow (seasonal
storage). Empirically this matches observed tree NSC dynamics with leaves turning over
daily, sapwood reserves turning over seasonally, and root+heartwood storage turning
over annually.

## 9. Allometric parameters (PFT inputs)

These are ingested from the PFT parameter file through `InitPlantMod` into `plt_allom`
(`f90src/Ecosim_datatype/PlantTraitDataType.F90`). Key fields cited above:

| Field | Meaning | Used by |
|---|---|---|
| `rNCLeaf_pft`, `rPCLeaf_pft` | Max leaf N:C and P:C (gN/gC, gP/gC) | §3 |
| `rNCSheath_pft`, `rPCSheath_pft` | Sheath N:C, P:C | §3 |
| `rNCStalk_pft`, `rPCStalk_pft` | Stalk N:C, P:C | §3 |
| `rNCRoot_pft`, `rPCRootr_pft` | Root N:C, P:C | §3 |
| `rNCReserve_pft`, `rPCReserve_pft` | Reserve pool N:C, P:C | §5 |
| `rNCHusk_pft`, `rNCEar_pft` | Reproductive organ stoichiometry | §5 |
| `StalkBiomGrowthYld_pft`, `ReserveBiomGrowthYld_pft`, `HuskBiomGrowthYld_pft`, `EarBiomGrowthYld_pft`, `GrainBiomGrowthYld_pft` | Growth yields (gC structural / gC non-struct consumed) | §5 |
| `NodeLenPergC_pft` | Internode length per gC | Node-morphology updates |
| `rProteinC2LeafN_pft`, `rProteinC2LeafP_pft` | Protein C per leaf N, P | Photosynthesis |

Literature provenance: no explicit citations in comment headers beyond the Shinozaki
pipe-model reference at `GrosubsMod.F90:475-477` (root axis scaling) and the Grant 1989
note in `StomatesMod.F90:438` (Farquhar-style C3; used downstream of allocation by
`ComputeGPP`, see photosynthesis doc).

## 10. Parameters local to allocation code

These are **module-level or local constants** not exposed via PFT input:

| Constant | Value | Location | Meaning |
|---|---|---|---|
| `FPART1` | `1.00` | `PlantBranchMod.F90:555` | Pre-anthesis leaf-allocation slope |
| `FPART2` | `0.40` | `PlantBranchMod.F90:556` | Pre-anthesis petiole-allocation slope |
| `PART2LEAF_MIN` | in `PlantBGCPars` | module-level | Floor on leaf allocation during senescence |
| `PART2PETOL_MIN` | in `PlantBGCPars` | module-level | Floor on petiole allocation during senescence |
| `XFRX` | in `PlantBGCPars` | module-level | Max storage C ratio for remobilization from stalk/root reserves |
| `CNKI`, `CPKI` | in `PlantBGCPars` | module-level | N, P inhibition constants on growth/respiration |
| `StandingDeadKd` | `1.5814e-5` h^-1 | `GrosubsMod.F90:117` | First-order decay rate of standing dead to litter |

## 11. Mass balance

Every growth-timestep cycle is wrapped by `EnterPlantBalance` / `ExitPlantBalance`
(`PlantBalMod.F90`). `CheckPlantBalanceZ` is invoked during development/debug to verify
that

```
d/dt (live biomass + non-structural pools) ==
      (GPP) - (Rauto) - (Litterfall) - (Disturbance removal) + (N2 fixation) + (Uptake)
```

per element, per PFT. The routine `SumPlantBiome` (`PlantBalMod.F90:34`) emits the
tracked `vegE(NumPlantChemElms)` vector used by `CheckPlantBalanceZ`.
