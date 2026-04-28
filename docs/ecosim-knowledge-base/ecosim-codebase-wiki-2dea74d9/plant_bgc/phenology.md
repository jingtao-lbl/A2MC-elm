---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/{Plant_bgc, Prescribed_pheno}/`
**Last verified:** 2026-04-24
---

# Phenology and Disturbance

Phenology in EcoSIM is resolved **per branch** (not per PFT or per node). A PFT can have
up to `BranchNumMax` branches (5 for trees, 1 for graminoids/shrubs/bryophytes, declared
at `PlantPhenolMod.F90:29`), and each branch carries its own day-length, heat-sum,
cold-sum, water-potential-hour, and growth-stage-calendar accumulators. The dynamic
phenology module dispatches to one of four phenology types per PFT (evergreen, cold
deciduous, drought deciduous, cold+drought deciduous) and one of two growth habits
(annual, perennial).

A parallel **prescribed-phenology** mode (selected via `EcoSIMCtrlMod%ldo_sp_mode`)
supersedes the dynamic module and replaces dynamic LAI/SAI/height/root profiles with
interpolated monthly inputs.

## 1. Entry point and per-branch dispatch

The top-level routine is `PhenologyUpdate` (`PlantPhenolMod.F90:36-91`). Hourly, for
each active PFT it:

1. Accumulates the landscape population counter `PlantPopu_col`.
2. Calls `set_plant_flags` (`PlantPhenolMod.F90:160-244`) to flip planting, emergence,
   harvest, and death flags based on calendar rules from `PlantMgmtDataType`.
3. If the PFT is active (`IsPlantActive_pft == iTrue`):
   - `FindMainBranchNumber` (`PlantPhenolMod.F90:371-399`) — locates the main branch.
   - `StagePlantPhenology` (`PlantPhenolMod.F90:400-500`) — applies PFT-wide temperature
     offsets, computes acclimated maturity group `MatureGroup_pft`, and prepares
     per-branch state.
   - `TestPlantEmergence` (`PlantPhenolMod.F90:501-546`) — flips
     `iPlantCalendar_brch(ipltcal_Emerge,...)` from 0 to the current day-of-year `I`
     once both the shoot has penetrated the soil surface
     (`HypocotHeight_pft > SeedDepth_pft`) and the primary root has left the planting
     layer (`Root1stDepz_raxes(1,NZ) > SeedDepth_pft`).
   - `root_shoot_branching` (`PlantPhenolMod.F90:245-370`) — activates lateral branches
     and root axes as nodes accumulate.
   - If emerged or forced to initialize: `Emerged_plant_Phenology` (line 97), which
     iterates over all branches, calls `branch_specific_phenology`, updates node counts
     with `UpdateBranchNodeNumber`, and advances calendar stages.

## 2. Growth-stage calendar

The calendar flag `iPlantCalendar_brch(stage, NB, NZ)` stores the day-of-year on which
the branch first reached each stage; `0` means "not yet reached". The twelve stages are
declared in `f90src/Modelconfig/ElmIDMod.F90:127-139`:

| Id | Stage | Trigger (vegetative → reproductive) |
|---|---|---|
| `ipltcal_Planting` (0) | planted | Management calendar |
| `ipltcal_Emerge` (1) | emergence | Root+shoot penetration check (§1) |
| `ipltcal_InitFloral` (2) | floral initiation | `ShootNodeNum_brch > MatureGroup_pft + ShootNodeNumAtInitFloral_brch` (`PlantPhenolMod.F90:1180-1182`) |
| `ipltcal_Jointing` (3) | tillering | `NodeNumNormByMatgrp_brch > 0.25 * GrothStageNorm4VegetaPheno` |
| `ipltcal_Elongation` (4) | stem elongation | `NodeNumNormByMatgrp_brch > 0.50 * GrothStageNorm4VegetaPheno` |
| `ipltcal_heading` (5) | heading | `NodeNumNormByMatgrp_brch > 1.00 * GrothStageNorm4VegetaPheno` |
| `ipltcal_Anthesis` (6) | anthesis | `NumOfLeaves_brch > ShootNodeNumAtInitFloral_brch` |
| `ipltcal_BeginSeedFill` (7) | grain-fill start | `ReprodNodeNumNormByMatrgrp_brch > 0.50 * GrothStageNorm4ReprodPheno` |
| `ipltcal_SetSeedNumber` (8) | dough stage 1 | `ReprodNodeNumNormByMatrgrp_brch > 1.00 * GrothStageNorm4ReprodPheno` |
| `ipltcal_SetSeedMass` (9) | dough stage 2 | `ReprodNodeNumNormByMatrgrp_brch > 1.50 * GrothStageNorm4ReprodPheno` |
| `ipltcal_EndSeedFill` (10) | ripening | Grain-fill completed |

Stage checks live in `CheckBranchNodeState` (`PlantPhenolMod.F90:1149-1192`).
`GrothStageNorm4VegetaPheno=2.0`, `GrothStageNorm4ReprodPheno=0.667` are declared at
`PlantPhenolMod.F90:25-26`.

## 3. Environmental drivers

`CalcPhenolEnvfactor` (`PlantPhenolMod.F90:1009-1046`) builds the phenology-multiplier
triplet `(TFNP, WFNG, OFNG)` consumed by `UpdateBranchNodeNumber`:

```
TKCO = TKGroth_pft(NZ) + TempOffset_pft(NZ)            ! canopy growth temp + acclim offset
TFNP = calc_leave_grow_tempf(TKCO)                      ! Arrhenius with high/low-T inactivation, 25 °C = 1
if iPlantPhenolPattern_pft == iplt_annual:
    WFNG = exp(0.025 * max(PSICanopy_pft, -1000))       ! water-potential growth function
    OFNG = sqrt(PlantO2Stress_pft(NZ))                  ! O2-stress factor in [0,1]
else:
    WFNG = 1
    OFNG = 1
```

Annual plants are therefore water-stress- and O2-stress-responsive for node
initiation/leaf appearance; perennials are not (comment at
`PlantPhenolMod.F90:1097-1104`).

Canopy growth temperature `TKGroth_pft` (distinct from instantaneous `TKC_pft`) is the
time-integrated growth temperature updated elsewhere in `PlantPhenolMod.F90`;
`TempOffset_pft` shifts the Arrhenius curve to represent thermal acclimation.

### Node-initiation and leaf-appearance rates

`UpdateBranchNodeNumber` (`PlantPhenolMod.F90:1047-1148`):

```
NodeInitRate   = max(0, RefNodeInitRate_pft * TFNP)
LeafAppearRate = max(0, RateRefLeafAppearance_pft * TFNP)
```

For annuals only, rates are further modulated by `OFNG` (pre-floral initiation) and
`WFNG` (pre-anthesis):

```
if annual and not past floral init:
    NodeInitRate   *= OFNG
    LeafAppearRate *= OFNG
if annual and not past anthesis:
    NodeInitRate   *= WFNG
    LeafAppearRate *= WFNG
```

Rates accumulate into `ShootNodeNum_brch` and `NumOfLeaves_brch`, and into the
maturity-group normalized counters `NodeNumNormByMatgrp_brch` (vegetative) and
`ReprodNodeNumNormByMatrgrp_brch` (reproductive). These normalized counters drive the
stage transitions documented in §2.

## 4. Phenology type dispatch (per branch, per hour)

`branch_specific_phenology` (`PlantPhenolMod.F90:547-664`) switches on `iPlantPhenolType_pft`:

| Value | Name (ElmIDMod) | Branch routine |
|---|---|---|
| 0 | `iphenotyp_evgreen` | `CropEvergreenPhenology` (line 749) |
| 1 | `iphenotyp_coldecid` | `ColdDeciduousBranchPhenology` (line 805) |
| 2 | `iphenotyp_drouhtdecidu` | inline drought-deciduous block (lines 599-652) |
| 3 | `iphenotyp_coldroutdecid` | `ColdDroughtDeciduPhenology` (line 665) |
| 4, 5 | placeholder for subtropical/tropical evergreen | inline drought block with extra day-length cap |

Before dispatching, the routine updates the dual photoperiod accumulators
(`PlantPhenolMod.F90:578-585`):

```
if DayLenthCurrent >= DayLenthPrev:
    Hours4LenthenPhotoPeriod_brch += 1
    Hours4ShortenPhotoPeriod_brch  = 0
else:
    Hours4LenthenPhotoPeriod_brch  = 0
    Hours4ShortenPhotoPeriod_brch += 1
```

### 4.1 Evergreen (`CropEvergreenPhenology`)
(`PlantPhenolMod.F90:749-804`)

Evergreen PFTs key their activity to photoperiod. During lengthening days
(`DayLenthCurrent >= DayLenthPrev`) they accumulate `Hours4Leafout_brch`; when it
exceeds `HourReq4LeafOut_brch`, or on day-of-year 173 (N hemisphere) / 355 (S
hemisphere), they reset `Hours4LeafOff_brch=0` and flip `doPlantLeaveOff_brch=iTrue`.
During shortening days they accumulate `Hours4LeafOff_brch`; when it exceeds
`HourReq4LeafOff_brch`, or on DOY 355 (N) / 173 (S), they reset `Hours4Leafout_brch=0`
and re-enable leafout. This effectively builds a solstice-anchored seasonal cycle for
evergreen growth-rate modulation (leaves remain present, but activity waxes and wanes).

### 4.2 Cold deciduous (`ColdDeciduousBranchPhenology`)
(`PlantPhenolMod.F90:805-888`)

Accumulates leafout hours when `TCGroth_pft >= TC4LeafOut_pft` during lengthening-or-
resumed photoperiods. Chilling temperature `TCChill4Seed_pft` subtracts accumulated
hours. Once `Hours4Leafout_brch >= HourReq4LeafOut_brch` (or on the solstice-fallback
day), cold hours are reset to 0 (leafout).

On shortening days, after floral initiation has occurred (`iPlantCalendar_brch(ipltcal_InitFloral) != 0`),
or when day length drops below 12 h and is still shortening, `doPlantLeaveOff_brch` is
set. Then every hour below `TC4LeafOff_pft` increments `Hours4LeafOff_brch`; when it
exceeds `HourReq4LeafOff_brch`, `Hours4Leafout_brch` is reset and the branch
re-enables leafout for next spring (`PlantPhenolMod.F90:869-884`).

### 4.3 Drought deciduous
(`PlantPhenolMod.F90:599-652`)

Keyed to `PSICanopy_pft` rather than temperature:

```
if PSICanopy_pft >= PSIMin4LeafOut(iEmbryophyteType_pft):
    Hours4Leafout_brch += 1

if PSICanopy_pft < PSIMin4LeafOff(iEmbryophyteType_pft):
    Hours4LeafOff_brch += 1        ! during dormancy
    Hours4Leafout_brch -= 12       ! if still below leafout threshold, penalty
```

The thresholds are hard-coded at `PlantPhenolMod.F90:23-28`:
- `PSIMin4LeafExpansion = 0.1 MPa` (positive turgor for leaf expansion)
- `PSIMin4LeafOut(2:4) = (-0.5, -1.5, -0.5) MPa` keyed on embryophyte type
- `PSIMin4LeafOff(0:4) = (-200, -2, -8, -5, -3) MPa`

The 200 MPa entry applies to bryophytes (embryophyte type 0) and effectively disables
drought leaf-off for bryophytes (they desiccate and recover).

### 4.4 Cold + drought deciduous (`ColdDroughtDeciduPhenology`)
(`PlantPhenolMod.F90:665-748`)

Combines the cold and drought rules: both temperature and water-potential hours must
satisfy their respective thresholds for leafout or leafoff.

## 5. Growth-habit (annual vs perennial)

Declared at `ElmIDMod.F90:116-117`:

```
iplt_annual    = 0
iplt_perennial = 1
```

Used throughout allocation and phenology:

- `CalcPartitionCoeff` (`PlantBranchMod.F90:645-660`) — annuals push 62.5% to grain,
  perennials 25%; perennials roll stalk allocation into reserve at senescence.
- `CalcPhenolEnvfactor` (above) — only annuals feel water/O2 stress in phenology.
- `ResetNonAnnualBranch` (`PlantBranchMod.F90:2294-2511`) — resets perennial branches
  for the next growing season without killing them.
- `ResetBranchPhenology` (`PlantBranchMod.F90:2512-2699`) — common reset of calendar
  stages for both habits.

## 6. Annual death and false breaks

`Hours2KillAnuals(0:5) = (336, 672, 672, 672, 672, 672)` at
`StomatesMod.F90:16-17` specifies the number of grain-fill-free hours required to
terminate an annual. `eval_annual_false_break_death` (`PlantDisturbsMod.F90:183-208`) is
called from `set_plant_flags` to detect annuals that failed to initiate floral growth
and triggers termination.

## 7. PFT-wide life-form and growth-type discriminators

Declared at `ElmIDMod.F90:119-121`:

```
iplt_bryophyte = 0
iplt_grasslike = 1
iplt_treelike  = 2
```

`iPlantRootProfile_pft` stores one of these and gates:
- Whether canopy has turgor (`is_root_bryophyte` → no turgor; `Stomata_Stress=1`;
  water-stress uses total water potential, `GrosubsMod.F90:497-503`).
- Whether litter fractions to wood-vs-fine complexes are applied
  (`GrosubsMod.F90:393-407` — non-vascular always fine).
- Whether fine/woody litter group is used for disturbance litterfall
  (`GrosubsMod.F90:221-230`).
- Primary-root axis allometry exponent (`GrosubsMod.F90:482-487`).
- Whether cold deciduous / evergreen evergreen-only paths apply
  (`PlantPhenolMod.F90:549-570`).

## 8. Disturbance integration

Disturbance routines interact with phenology through two mechanisms:

1. **Stage/flag changes.** Harvest or fire can force `iPlantCalendar_brch` back to `0`
   for stages after the cut, reset `EnablePlantLeafOut_brch`, and (for annuals) flip
   `IsPlantActive_pft` to 0 via `RemoveDeadAnnual`
   (`PlantDisturbsMod.F90:98-182`).
2. **Partial biomass removal.** `RemoveBiomassByDisturbance`
   (`PlantDisturbsMod.F90:261-302`) is called **inside** `GrowOnePlant` so that fresh
   growth is allocated before disturbance removal, ensuring the disturbance fluxes for
   the hour are consistent with the allocated state.

### Dispatch layer
`PlantDisturbsMod.F90:261-302` — `RemoveBiomassByDisturbance` wraps harvest, tillage,
thinning, grazing, and fire into a single call.

### Sub-modules

| File | Public routines | Role |
|---|---|---|
| `PlantDisturbByFireMod.F90` | `StageRootRemovalByFire`, `RemoveRootByFire`, `AbvGrndLiterFallByFire`, `AbvgBiomRemovalByFire`, `ApplyBiomRemovalByFire`, `InitPlantFireMod` | Fire-specific C/N/P partitioning between atmosphere (gaseous loss), litter, and standing dead |
| `PlantDisturbByGrazingMod.F90` | `AbvgBiomRemovalByGrazing`, `RemoveStandDeadByGrazing`, `ApplyBiomRemovalByGrazing`, `CutBranchNonstalByGrazing`, `GrazingPlant` | Fractional removal of leaves, petioles, and grain; non-structural pools typically left intact to fuel regrowth |
| `PlantDisturbByTillageMod.F90` | `RemoveBiomByTillage` | Soil-cultivation impact on roots and surface residues |

### Harvest

`RemoveBiomByHarvest` (`PlantDisturbsMod.F90:669-895`) handles crop harvest. It
distinguishes harvest types (leaf, fine-nonleaf, stalk, standing-dead) declared at
`ElmIDMod.F90:40-43` and moves harvested biomass to `HarvestElmnt2Litr` if the harvest
type leaves residue on-site, or to site-level cumulative harvest totals
(`EcoHavstElmntCum_pft`) if removed. The `HarvestCanopy` routine
(`PlantDisturbsMod.F90:1555-1711`) applies node-by-node canopy cutting.

### Self-thinning and mortality

Self-thinning is not a discrete routine; it emerges from two mechanisms:

1. **Excess maintenance respiration** (`RMxess_brch` > available reserves) drives
   `SenescenceBranch` (`PlantBranchMod.F90:3878-4096`), which kills lowest nodes.
2. **`isPlantShootAlive_pft`/`isPlantRootAlive_pft` flags** (`plt_pheno`) are flipped
   by `set_plant_flags` (`PlantPhenolMod.F90:160-244`) based on branch state checks.
   A PFT with both flags false is skipped by `GrowOnePlant`
   (`GrosubsMod.F90:280-282`).

Branch-level senescence and stand-level standing-dead decay into litter
(at rate `StandingDeadKd = 1.5814e-5 h^-1`, `GrosubsMod.F90:117`) are both tracked
under `LiveDeadTransformation` (`GrosubsMod.F90:112-235`).

## 9. Prescribed-phenology mode

File: `f90src/Prescribed_pheno/PrescribePhenolMod.F90` (364 lines).

Used when `ldo_sp_mode=.true.` (or `ats_cpl_mode=.true.` for ATS coupling). In this
mode:

- `PhenologyUpdate`, `GrowPlants`, and `RootBGCModel` are **not called**
  (see `APIs/PlantMod.F90:51-61`).
- `CanopyConditionModel` internally calls `SetCanopyProfile`
  (`PrescribePhenolMod.F90:132-180`) instead of `DivideCanopyAreaByHeight` +
  `SummaryCanopyAREA` (`SurfaceRadiationMod.F90:43-50`).
- Nutrient/gas uptake still runs through `RootUptakes`; it consumes the prescribed LAI,
  SAI, and root profiles as if they were dynamically computed.

### Public interface

```fortran
public :: GetRootProfile            ! 2-exponential root-depth profile (Jackson et al. 1996 style)
public :: SetCanopyProfile          ! uniform LAI/SAI distribution through canopy layers and zenith sectors
public :: PrescribePhenologyInterp  ! interpolate monthly LAI/SAI/height to current day
```

### Monthly interpolation (`PrescribePhenologyInterp`)
(`PrescribePhenolMod.F90:196-313`)

Fraction-of-month weight:

```
t        = (day_of_month - 0.5) / days_in_month
timwt(1) = (it(1)+0.5) - t     ! weight on current month
timwt(2) = 1 - timwt(1)         ! weight on next month
```

For each PFT:

```
tlai_day_pft = timwt(1)*tlai_mon_pft(month_current) + timwt(2)*tlai_mon_pft(month_next)
tsai_day_pft = same for stem-area index
CanopyHeight_pft = same for height
```

LAI and SAI are then uniformly subdivided across `NumCanopyLayers` layers. Currently the
monthly LAI/SAI/height arrays have **hard-coded test values**
(`PrescribePhenolMod.F90:200-201`, `219-221`):

```
lai(12) = [1.18, 1.18, 1.16, 1.24, 1.29, 1.33, 1.23, 1.41, 1.43, 1.39, 1.27, 1.22]
sai(12) = [0.32, 0.31, 0.31, 0.30, 0.31, 0.31, 0.34, 0.30, 0.31, 0.33, 0.37, 0.32]
height  = 17 m
LeafAngleClass(:,NZ) = uniform 1/NumLeafZenithSectors
```

A coupled ATS driver is expected to overwrite these with real input values before the
routine is invoked.

### Root profile (`SetRootProfileZ`)
(`PrescribePhenolMod.F90:315-363`)

Uses the beta-function CDF-of-depth of Jackson et al. (1997), tabulated for 10 biome
types:

```
CumRootFrac_vr(L) = 1 - beta(irootType)^(cum_depth_cm(L))
RootFrac_vr(L)    = CumRootFrac_vr(L) - CumRootFrac_vr(L-1)
tmp_rootc(L)      = frac * totfrootC(irootType) / PltPopDef(irootType)
tmp_rootl(L)      = frac * frootLen(irootType)  / PltPopDef(irootType)
```

Biome-indexed parameters (`PrescribePhenolMod.F90:346-349`):

| irootType | Biome | beta | totFrootC (g/m2) | frootLen (km/m2) | PltPopDef (1/m2) |
|---|---|---|---|---|---|
| 1 | Boreal forest | 0.943 | 293 | 2.6 | 0.6 |
| 2 | Desert bushes | 0.970 | 132 | 4.0 | 1.0 |
| 3 | Sclerophyllous shrubs/trees | 0.950 | 254 | 8.4 | 1.0 |
| 4 | Temperate coniferous forest | 0.980 | 400 | 6.1 | 0.6 |
| 5 | Temperate deciduous forest | 0.967 | 381 | 5.4 | 0.6 |
| 6 | Temperate grassland | 0.943 | 737 | 112 | 40 |
| 7 | Tropical deciduous forest | 0.982 | 278 | 3.5 | 0.6 |
| 8 | Tropical evergreen forest | 0.972 | 278 | 4.1 | 0.6 |
| 9 | Tropical grassland/savanna | 0.972 | 483 | 60.4 | 40 |
| 10 | Tundra | 0.909 | 469 | 7.4 | 40 |

totFrootC values shown above are in gC/m² after the 0.488 C-fraction conversion. Source
comment: "Jackson et al. (1997), *A global budget for fine root biomass, surface area,
and nutrient contents*, PNAS" (`PrescribePhenolMod.F90:322`).

### Canopy profile (`SetCanopyProfile`)
(`PrescribePhenolMod.F90:132-180`)

For each PFT, LAI and SAI are divided uniformly across:

```
LeafAreaZsec_lpft(N,L,NZ) = LeafAngleClass_pft(N,NZ) * CanopyLeafAreaZ_pft(L,NZ) / NumOfLeafAzimuthSectors
```

All stem area is assigned to the steepest zenith sector
(`PrescribePhenolMod.F90:159-160`).

### Unused helpers

`get_LAI_profile` and `get_StemArea_profile` are declared but empty
(`PrescribePhenolMod.F90:78-96`), reserved for future non-uniform profiles.

`TreeStem_diameter_taperEq` (`PrescribePhenolMod.F90:100-127`) implements a Larsen-2017
three-segment diameter taper equation; not currently called, retained for derivation of
stem area when DBH and height are prescribed.

## 10. Phenology parameters (per-PFT input)

Read from the PFT parameter file and stored in `plt_pheno`:

| Field | Purpose |
|---|---|
| `iPlantPhenolType_pft` | 0=evergreen, 1=cold decid, 2=drought decid, 3=cold+drought |
| `iPlantPhenolPattern_pft` | 0=annual, 1=perennial |
| `iPlantRootProfile_pft` | 0=bryophyte, 1=grass-like, 2=tree-like |
| `iPlantTurnoverPattern_pft` | 0=all abvg, 1=leaf+petiole, 2=none, 3=mixed |
| `iPlantDevelopPattern_pft` | 0=determinate, 1=indeterminate |
| `iEmbryophyteType_pft` | 0=Bryophytes, 1=Pteridophytes, 2=Gymnosperms, 3=Monocots, 4=Eudicots |
| `iPlantPhotosynsType_pft` | 3=C3, 4=C4 |
| `MatureGroup_pft` | Maturity group (node number at floral init) |
| `HourReq4LeafOut_brch` | Heat-sum hours for leafout |
| `HourReq4LeafOff_brch` | Cold-sum hours for leafoff |
| `TC4LeafOut_pft`, `TC4LeafOff_pft` | Threshold temperatures for leafout/leafoff |
| `TCChill4Seed_pft` | Chilling temperature threshold |
| `TempOffset_pft` | Arrhenius-curve shift for thermal acclimation |
| `RefNodeInitRate_pft` | Reference node initiation rate (h^-1 at 25 °C) |
| `RateRefLeafAppearance_pft` | Reference leaf appearance rate (h^-1 at 25 °C) |
| `MatureGroup_brch` | Per-branch maturity group |
| `MainBranchNum_pft` | ID of main branch |

These fields are all accessed through `plt_pheno` `associate` blocks; none have
fabricated or undocumented values.
