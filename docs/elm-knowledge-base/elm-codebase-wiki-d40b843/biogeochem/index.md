---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Biogeochemistry Subsystem Overview

The `components/elm/src/biogeochem/` directory implements ELM's terrestrial
biogeochemistry: living plant C/N/P pools, decomposition of litter and soil
organic matter, atmospheric and soil mineral nutrient dynamics, autotrophic and
heterotrophic respiration, phenology, gap and fire mortality, crop, wetland
methane, and BVOC/dust emission. This page is the top-level navigation; detailed
explanations live in the sibling `biogeochem/*.md` files.

All code referenced here is committed at `d40b8431`. Paths below are relative to
`components/elm/src/`.

## What is new in d40b8431 versus 60d9aad

The biogeochem tree saw structural drift between the two ELM snapshots that
A2MC tracks. Highlights surfaced repeatedly across the documents below:

1. **Three-step parameter handoff collapsed to two.** `elmfates_paraminterfaceMod.F90`
   and the `FatesReadPFTs` shim were deleted. FATES now does its own JSON
   parameter loading at the `api.43+` boundary. The remaining ELM-side wrapper
   is `main/elmfates_interfaceMod.F90` (lowercase filename — see PFT trait
   conventions section below).
2. **`alm_fates%init` is now a 3-arg call** (`elmfates_interfaceMod.F90:824`):
   `init(this, bounds_proc, flandusepftdat)`. Two-arg callsites will not compile.
3. **New per-radiation-step FATES callbacks**:
   `EcosystemDynLeaching` calls `alm_fates%wrap_FatesAtmosphericCarbonFluxes` and
   `alm_fates%wrap_FatesCarbonStocks` (`EcosystemDynMod.F90:267-270`).
   `EcosystemDynNoLeaching2` calls `col_cf%ZeroForFatesRR` and
   `alm_fates%UpdateLitterFluxes` (`EcosystemDynMod.F90:686-689`), and
   `alm_fates%wrap_WoodProducts` at `:811`.
4. **`AllocationMod.F90` was structurally refactored** (4557 lines, +631 over
   60d9aad). The single subroutine `Allocation3_PlantCNPAlloc` was deleted and
   split into `PlantCNPAlloc_RD` (`:2203`) and `PlantCNPAlloc_ECAMIC` (`:2113`),
   dispatched on `nu_com == 'RD'` from `SoilLittDecompAlloc2`. Most of the
   plant-N-and-P-demand math was lifted out of `Allocation1_PlantNPDemand`
   (now an 92-line wrapper at `:384-475`) into a new `TotalNPDemand`
   (`:477-1048`). Seven new helper subroutines were factored out:
   `NAllocationRD` (`:2914`), `NAllocationECAMIC` (`:2390`), `PAllocationRD`
   (`:3074`), `PAllocationECAMIC` (`:2710`), `DistributeN_RD` (`:3380`),
   `DistributeN_ECAMIC` (`:3794`), and `TotalNPDemand` (`:477`).
5. **Subroutine signatures changed** for the N and P input/output routines.
   `NitrogenDeposition(bounds, atm2lnd_vars)` is now 2-arg
   (`NitrogenDynamicsMod.F90:117`) — FAN dispatch was lifted to a sibling
   `fan_eval` call inside `EcosystemDynNoLeaching1:375-378`.
   `NitrogenLeaching(num_soilc, filter_soilc, dt)` (`:251`) and
   `PhosphorusLeaching(num_soilc, filter_soilc, dt)` (`:297`) lost their
   `bounds` argument. `NitrogenFert` (`:390`) gained
   `num_ppercropp, filter_ppercropp` for perennial crops.
   `RootDynamics` (`RootDynamicsMod.F90:40`) now takes `dt` as an explicit
   argument rather than computing it internally.
6. **`DecompCascadeBGCMod.F90:867,964`** reverts `minpsi` from `-1000.0_r8`
   (a debug override left in 60d9aad) back to `-10.0_r8` for both BGC and CN
   parameterizations. This is a scientific behavior change for the soil moisture
   limitation on heterotrophic respiration.
7. **PFT identification refactored to trait flags.** The `woody` flag is now
   ternary (`0 = non-woody, 1 = tree, 2 = shrub`); see
   `MaintenanceRespMod.F90:110` and the `>= 1.0_r8` test at `:185`. New helper
   PFT-trait predicates `iscft`, `climatezone`, `needleleaf`, `evergreen`,
   `crop`, `graminoid` replace named-constant tests like `nbrdlf_evr_trp_tree`
   and `npcropmin`. Helper methods `col_pp%is_soil(c)` / `veg_pp%is_on_soil_col(p)`
   replace `lun_pp%itype(l) == istsoil` patterns.
8. **CN/CNP allocation namelist control** drives the RD vs ECA-MIC dispatch.
   The driver routine `PlantCNPAlloc_RD` is selected when `nu_com == 'RD'`;
   otherwise `PlantCNPAlloc_ECAMIC` runs.

`use_fates_logging` was removed; the FATES management/harvest control now lives
in `fates_harvest_mode` (`elm_varctl.F90:230`) and `use_fates_managed_fire`
(`:229`). About ten new FATES-related ELM namelist flags are documented in
`docs/a2mc_reference/` and recapped at the bottom of `phenology.md`.

## Top-level Organization

ELM biogeochemistry is built around three kinds of modules:

1. **State and flux derived types** that allocate and initialize the prognostic
   pool/flux arrays for each element. Carbon uses
   `biogeochem/CNCarbonStateType.F90` and `biogeochem/CNCarbonFluxType.F90`,
   nitrogen uses `biogeochem/CNNitrogenStateType.F90` and
   `biogeochem/CNNitrogenFluxType.F90`, phosphorus uses
   `biogeochem/PhosphorusStateType.F90` and `biogeochem/PhosphorusFluxType.F90`.
2. **Process modules** that compute fluxes (allocation, respiration,
   decomposition, mineralization, nitrification, denitrification, phosphatase,
   weathering, phenology, mortality, fire).
3. **State update modules** that step the pools forward in three staged sweeps
   per radiation time step (stage 1 after photosynthesis/allocation, stage 2
   after gap mortality and harvest, stage 3 after leaching, fire, and erosion).

The container type `cnstate_type` in `data_types/CNStateType.F90` is a
per-column structure that carries diagnostic flags, crop indices, vertical
profiles (`ndep_prof_col`, `pdep_prof_col`, `nfixation_prof_col`,
`leaf_prof_patch`, `froot_prof_patch`, `stem_prof_patch`, `croot_prof_patch`),
decomposition pool parameters (`rf_decomp_cascade_col`,
`pathfrac_decomp_cascade_col`), and phenology state (`dormant_flag_patch`,
`onset_flag_patch`, `days_active_patch`). See
`biogeochem/cnp_state_and_fluxes.md` for full field inventories.

## CN vs CNP

ELM supports three nutrient coupling configurations controlled by `elm_varctl`
flags:

| Flag | Meaning |
|---|---|
| `carbon_only`  | Carbon cycle only; N and P demand always satisfied, no downregulation |
| `carbonnitrogen_only` | CN mode; N limits GPP/growth, P always satisfied |
| `carbonphosphorus_only` | CP mode; P limits GPP/growth, N always satisfied |
| (default CNP) | Both N and P demand must be met; most restrictive limits growth |

Phosphorus is an ELM extension over the CESM/CLM ancestor. The `PhosphorusStateType`
and `PhosphorusFluxType` modules, the inorganic cascade
(`solutionp -> labilep -> secondp -> occlp` plus a `primp` weathering source) in
`biogeochem/PhosphorusDynamicsMod.F90`, and the three staged updaters
`biogeochem/PhosphorusStateUpdate{1,2,3}Mod.F90` are ELM-specific. The CNP code
path is engaged when `use_cn = .true.` and the CP / CNP configurations are
compiled in.

Details: `cnp_state_and_fluxes.md`, `phosphorus.md`.

## Decomposition Cascade and Vertical Soil BGC

Soil decomposition is structured as a cascade of donor/receiver transitions
among pools (litter 1 metabolic, litter 2 cellulose, litter 3 lignin, CWD, SOM 1,
SOM 2, SOM 3). The cascade definition sits in
`biogeochem/CNDecompCascadeConType.F90` (`decomp_cascade_con`), and two
alternative initializers populate the transitions:
`biogeochem/DecompCascadeBGCMod.F90` (CENTURY/BGC parameterization,
`use_century_decomp = .true.`, default) and
`biogeochem/DecompCascadeCNMod.F90` (original CN parameterization).

Each transition has a respiration fraction `rf_decomp_cascade`, a path fraction
`pathfrac_decomp_cascade`, and a rate constant `decomp_k`. At each time step,
`biogeochem/SoilLittDecompMod.F90` (`SoilLittDecompAlloc` at `:92`,
`SoilLittDecompAlloc2` at `:566`) computes potential C loss per transition,
computes immobilization N/P demand, resolves competition between plants and
decomposers via `AllocationMod`, and emits actual C/N/P transfers along the
cascade. Vertical mixing is computed in `biogeochem/SoilLittVertTranspMod.F90`
using a Patankar advection-diffusion tridiagonal solver, parameterized by
`som_diffus` and `cryoturb_diffusion_k`. The d40b8431 source promotes
`SoilLittVertTranspParamsType` to `public` and adds a
`type, public :: ConcTransportType` plus `transport_ptr_list(:)` that lets
callers register additional tracers via `createLitterTransportList` rather than
hand-coding a sequence of pool transports. Vertical profiles for incoming
C/N/P come from `biogeochem/VerticalProfileMod.F90` (`decomp_vertprofiles`).

The `minpsi` value used in the moisture scalar `w_scalar(c,j)` for both BGC
(`:867`) and CN (`:964`) initializers is `-10.0_r8` at d40b8431 (was an erroneous
`-1000.0_r8` in 60d9aad). This makes heterotrophic respiration much more
sensitive to soil dryness than the prior wiki described.

Details: `decomposition.md`.

## Allocation and Respiration

The non-FATES C/N/P allocation for vegetation is in
`biogeochem/AllocationMod.F90` (4557 lines), now organized as:

1. `Allocation1_PlantNPDemand` (`:384`, called from `EcosystemDynNoLeaching1`)
   is a thin wrapper that calls `TotalNPDemand` (`:477-1048`) and then
   `p2c_1d_filter` to aggregate to column. `TotalNPDemand` holds the
   per-PFT allometric demand math that previously lived inside
   `Allocation1_PlantNPDemand`.
2. `Allocation2_ResolveNPLimit` (`:1052`, called from inside
   `SoilLittDecompAlloc`) resolves competition between plant and decomposer
   demand for soil mineral N/P, sets `fpg_col`, `fpg_p_col`, `fpi_col`,
   `fpi_p_col`.
3. **Two final allocation entry points**, dispatched in
   `SoilLittDecompMod.F90:759-771` on `nu_com`:
   - `PlantCNPAlloc_RD(...)` (`AllocationMod.F90:2203`, when `nu_com == 'RD'`),
   - `PlantCNPAlloc_ECAMIC(...)` (`:2113`, otherwise).
   Each uses a matching pair of helpers `NAllocationRD`/`PAllocationRD` (or
   `NAllocationECAMIC`/`PAllocationECAMIC`) and a tissue distributor
   `DistributeN_RD`/`DistributeN_ECAMIC` to write the final
   `cpool_to_*`, `npool_to_*`, `ppool_to_*` fluxes in `CNCarbonFluxType`,
   `CNNitrogenFluxType`, `PhosphorusFluxType`.

`biogeochem/GrowthRespMod.F90` assigns growth respiration based on each
allocation flux times the PFT parameter `grperc` (split between now vs storage
via `grpnow`). `biogeochem/MaintenanceRespMod.F90` (`:79-223`) computes leaf,
fine-root, live-stem, live-coarse-root, and grain MR using a base rate `br_mr`
applied to N content of each pool with Q10 temperature response, plus an
"excess respiration" term proportional to `cpool * br_xr(ivt)`.
The new ternary `woody` test (`:185`, `>= 1.0_r8`) lets shrubs (woody==2)
also receive live-stem and live-coarse-root MR.

`biogeochem/EcosystemDynMod.F90` is the main driver. `EcosystemDynNoLeaching1`
(`:276`), `EcosystemDynNoLeaching2` (`:481`), and `EcosystemDynLeaching`
(`:121`) structure the time-step sequence around soil BGC and leaching.
`biogeochem/EcosystemBalanceCheckMod.F90` and `biogeochem/CNPBudgetMod.F90`
perform mass-balance accounting at column and grid level.
`biogeochem/AnnualUpdateMod.F90` rolls annual accumulators (`annsum_npp`,
`annmax_retransn_patch`, `annavg_t2m_patch`). A parallel BeTR-flavored
allocation path is in `biogeochem/CNAllocationBetrMod.F90` and its driver
`biogeochem/CNEcosystemDynBetrMod.F90`.

Details: `allocation_and_respiration.md`.

## Nitrogen Dynamics

`biogeochem/NitrogenDynamicsMod.F90` (682 lines) handles atmospheric deposition,
fixation, leaching, and fertilizer. Key entries (with d40b8431 line numbers):

- `NitrogenDeposition(bounds, atm2lnd_vars)` (`:117`) — copy `forc_ndep_grc`
  to `ndep_to_sminn_col`. The legacy in-routine FAN call has been REMOVED;
  `fan_eval` is now a sibling call from `EcosystemDynNoLeaching1:375-378`.
- `NitrogenFixation(bounds, num_soilc, filter_soilc, dayspyr)` (`:156`) —
  Cleveland 1999 NPP-based fixation (CN mode); FATES path is selected by the
  caller when `use_fates`.
- `NitrogenLeaching(num_soilc, filter_soilc, dt)` (`:251`) — NO3 loss to
  drainage and runoff (`bounds` removed in d40b8431).
- `NitrogenFert(bounds, num_soilc, filter_soilc, num_pcropp, filter_pcropp,
  num_ppercropp, filter_ppercropp)` (`:390`) — synthetic fert + manure;
  perennial-crop arguments added.
- `CNSoyfix` (`:463`), `NitrogenFixation_balance` (`:596`).

`biogeochem/NitrifDenitrifMod.F90` computes nitrification and denitrification
rates per soil level (Arah & Vinten 1995). Three staged update modules
(`NitrogenStateUpdate1Mod.F90:101`, `NitrogenStateUpdate2Mod.F90:33`,
`NitrogenStateUpdate3Mod.F90:31`) step `col_ns` and `veg_ns` pools.
`biogeochem/PlantMicKineticsMod.F90` carries per-level Michaelis-Menten
parameters used by ECA. `biogeochem/FanMod.F90` and `FanUpdateMod.F90`
implement the FANv2 agricultural N model when `use_fan = .true.`.

The ParamsInst `sf` and `sf_no3` fields in `CNNDynamicsParamsType`
(`NitrogenDynamicsMod.F90:50-51`) are now plain `real(r8)` scalars (in 60d9aad
they were pointers). Code that did `pointer => CNNDynamicsParamsInst%sf` is
no longer valid.

Details: `nitrogen.md`.

## Phosphorus Dynamics

The inorganic P cascade is in `biogeochem/PhosphorusDynamicsMod.F90` (757 lines).
Public entries at d40b8431:

- `PhosphorusDeposition(bounds, atm2lnd_vars)` (`:51`) — 2-arg.
- `PhosphorusWeathering(num_soilc, filter_soilc, cnstate_vars, dt)` (`:88`).
- `PhosphorusAdsportion(num_soilc, filter_soilc, cnstate_vars, dt)` (`:136`).
- `PhosphorusDesoprtion(num_soilc, filter_soilc, cnstate_vars, dt)` (`:190`).
- `PhosphorusOcclusion(num_soilc, filter_soilc, cnstate_vars, dt)` (`:243`).
- `PhosphorusBiochemMin(num_soilc, filter_soilc, cnstate_vars, dt)` (`:389`)
  and `PhosphorusBiochemMin_balance(bounds, ..., dt)` (`:477`, used when
  `nu_com_phosphatase = .true.`).
- `PhosphorusLeaching(num_soilc, filter_soilc, dt)` (`:297`) — `bounds` removed.
- `PhosphorusFert(bounds, num_soilc, filter_soilc)` (`:729`).

Three staged updaters (`PhosphorusStateUpdate1Mod.F90:99`,
`PhosphorusStateUpdate2Mod.F90:34`, `PhosphorusStateUpdate3Mod.F90:40`) mirror
the N stages.

Details: `phosphorus.md`.

## BeTR / PFLOTRAN Interface

ELM can route soil BGC through the external PFLOTRAN reactive-transport model or
through the BeTR soil column abstraction. Master switches in
`main/elm_varctl.F90` are `use_elm_interface`, `use_pflotran`, `pf_cmode`,
`pf_hmode`. The BeTR-flavored update modules
`biogeochem/CNNStateUpdate1BeTRMod.F90`, `CNNStateUpdate2BeTRMod.F90`,
`CNNStateUpdate3BeTRMod.F90` provide BeTR-specific state updates;
`biogeochem/CNGapMortalityBeTRMod.F90` handles gap mortality in BeTR mode;
`biogeochem/CNBeTRIndicatorMod.F90` defines per-flux switches; the BeTR
allocation driver is `biogeochem/CNEcosystemDynBetrMod.F90` and its allocation
backend is `biogeochem/CNAllocationBetrMod.F90`.

## Relationship to FATES (d40b8431)

When `use_fates = .true.` (`main/elm_varctl.F90:227`), FATES replaces most of
ELM's vegetation biogeochemistry. The ELM side handles soil water and
temperature, atmospheric forcing, soil BGC (litter/SOM decomposition,
N/P mineralization, nitrification/denitrification, phosphorus inorganic cascade,
leaching, deposition), and exchanges with FATES via
`main/elmfates_interfaceMod.F90` (the `alm_fates` instance, declared at
`elm_instMod`). The filename is lowercase `elmfates_interfaceMod.F90`; the
older `elmfates_paraminterfaceMod.F90` was DELETED.

Specifically, inside `EcosystemDynMod.F90`:

- `EcosystemDynLeaching` (`:121-272`): when `.not. use_fates` runs the standard
  veg summaries (`veg_cf_Summary`, etc.); when `use_fates` skips them and zeros
  the column-level upscaled veg arrays via `col_*%ZeroForFates`
  (`:248-253`). After the column summary block, two new FATES wrappers run
  unconditionally on every soil column:
  `alm_fates%wrap_FatesAtmosphericCarbonFluxes(bounds, num_soilc, filter_soilc)`
  (`:268`) and `alm_fates%wrap_FatesCarbonStocks(...)` (`:269`).
- `EcosystemDynNoLeaching2` (`:481-878`): the `.not. use_fates` block runs
  `Phenology`, `GrowthResp`, `RootDynamics`, and the standard staged updates;
  the `use_fates` block (`:682-690`) calls
  `col_cf%ZeroForFatesRR(bounds, num_soilc, filter_soilc)` (a
  radiation-step-only variant defined at `ColumnDataType.F90:693, 8059`) and
  `alm_fates%UpdateLitterFluxes(bounds)` (defined at
  `elmfates_interfaceMod.F90:1423`). Then `CarbonStateUpdate1`,
  `NitrogenStateUpdate1`, `PhosphorusStateUpdate1`, and `SoilLittVertTransp`
  run unconditionally for both modes. At `:811`, when FATES is active,
  `alm_fates%wrap_WoodProducts(bounds, num_soilc, filter_soilc)` runs to feed
  harvested wood from the FATES side back into the ELM product pools.
- `EcosystemDynNoLeaching1` (`:276-478`): `NitrogenDeposition`,
  `NitrogenFixation` or `_balance`, optional `NitrogenFert`/`PhosphorusFert`/
  `CNSoyfix`/`MaintenanceResp` (only when `.not. use_fates`),
  P inorganic-cascade pre-step (only when `nu_com /= 'RD'`),
  `PhosphorusDeposition`, `decomp_rate_constants_bgc` or `_cn`,
  `decomp_vertprofiles`, `EvaluateSupplStatus`, and (only when
  `.not. use_fates`) `Allocation1_PlantNPDemand`.

Soil biogeochemistry (decomposition, nitrification/denitrification, P cascade,
vertical mixing) runs the same way whether or not FATES is active. FATES calls
into ELM soil BGC for mineralization/immobilization and competes with
decomposers for mineral N and P through the ECA/RD machinery in
`AllocationMod.F90`.

## Navigation

| Document | Covers |
|---|---|
| `cnp_state_and_fluxes.md` | State/flux derived types: `carbonstate_type`, `carbonflux_type`, `nitrogenstate_type`, `nitrogenflux_type`, `phosphorusstate_type`, `phosphorusflux_type`, `cnstate_type`, `chemstate_type`; pool inventories; `CNPBudgetMod.F90`, `EcosystemBalanceCheckMod.F90`; `ZeroForFates` and `ZeroForFatesRR` helpers |
| `allocation_and_respiration.md` | `AllocationMod.F90` (RD/ECA-MIC dispatch, `TotalNPDemand`), `CNAllocationBetrMod.F90`, `CNEcosystemDynBetrMod.F90`, `AnnualUpdateMod.F90`, `GrowthRespMod.F90`, `MaintenanceRespMod.F90`, `EcosystemDynMod.F90` (with new FATES wrap_* hooks), `EcosystemBalanceCheckMod.F90`, `CNBeTRIndicatorMod.F90`, carbon state updaters |
| `decomposition.md` | `CNDecompCascadeConType.F90`, `DecompCascadeBGCMod.F90` (minpsi reverted), `DecompCascadeCNMod.F90`, `SoilLittDecompMod.F90`, `SoilLittVertTranspMod.F90` (new `ConcTransportType` infrastructure), `VerticalProfileMod.F90` |
| `nitrogen.md` | `NitrogenDynamicsMod.F90` (signatures rewritten), `NitrifDenitrifMod.F90`, `NitrogenStateUpdate1Mod.F90`, `NitrogenStateUpdate2Mod.F90`, `NitrogenStateUpdate3Mod.F90`, `CNGapMortalityBeTRMod.F90`, `CNNStateUpdate1BeTRMod.F90`, `CNNStateUpdate2BeTRMod.F90`, `CNNStateUpdate3BeTRMod.F90`, `FanMod.F90`, `FanUpdateMod.F90`, `PlantMicKineticsMod.F90` |
| `phosphorus.md` | `PhosphorusDynamicsMod.F90` (signatures rewritten), `PhosphorusStateUpdate{1,2,3}Mod.F90`, inorganic P cascade, weathering, phosphatase |
| `phenology.md` | `PhenologyMod.F90` (3754 lines, new `coldtolerance` subroutine, shifted line numbers), `CNPhenologyBeTRMod.F90`, `PhenologyFluxLimitMod.F90`, `SatellitePhenologyMod.F90`, `VegStructUpdateMod.F90` |
| `mortality.md` | `GapMortalityMod.F90` (trait-based PFT identification), `RootDynamicsMod.F90` (now takes explicit `dt`), `WoodProductsMod.F90`, `CropHarvestPoolsMod.F90` |
| `fire.md` | `FireMod.F90` (trait-based PFT predicates), `FireDataBaseType.F90`, `FireMethodType.F90`, `FATESFireBase.F90`, `FATESFireDataMod.F90`, `FATESFireFactoryMod.F90`, `FATESFireNoDataMod.F90` |
| `methane.md` | `CH4Mod.F90`, `CH4varcon.F90` |
| `crops.md` | `CropMod.F90`, `CropType.F90` (winter-wheat survival fields), `CropHarvestPoolsMod.F90` |
| `emissions.md` | `VOCEmissionMod.F90`, `MEGANFactorsMod.F90`, `DUSTMod.F90`, `DryDepVelocity.F90`, `ErosionMod.F90` |

## Supporting Utilities

- `biogeochem/PrecisionControlMod.F90`: catches small negative pool values and
  moves them into a per-pool truncation sink (`ctrunc_patch`, `ntrunc_patch`,
  `ptrunc_patch`).
- `biogeochem/SharedParamsMod.F90`: shared parameter instance `ParamsShareInst`
  carrying `Q10_mr`, `Q10_hr`, `minpsi`, `cwd_fcel`, `cwd_flig`, `froz_q10`,
  `decomp_depth_efolding`, `mino2lim`, `organic_max`. Note `minpsi` here is the
  netCDF-loaded value; the in-source override in `DecompCascadeBGCMod.F90` was
  reverted to `-10.0_r8`.
- `biogeochem/SpeciesMod.F90`: integer IDs for carbon isotopes (`CN_SPECIES_C12=1`,
  `CN_SPECIES_C13=2`, `CN_SPECIES_C14=3`) and N/P species (`CN_SPECIES_N=4`,
  `CN_SPECIES_P=5`), plus `species_from_string`.
- `biogeochem/LSparseMatMod.F90`: sparse matrix utilities used by the vertical
  transport solver.
- `biogeochem/ComputeSeedMod.F90`: computes initial seed C/N/P for newly opened
  patches during dynamic land cover change.
- `biogeochem/CarbonIsoFluxMod.F90`: routes C13 and C14 fluxes alongside bulk C.
- `biogeochem/C14DecayMod.F90`: C14 radioactive decay and bomb-spike atmospheric
  history.

## PFT Trait Conventions (d40b8431)

Across the biogeochem tree, name-based PFT tests (`nbrdlf_evr_trp_tree`,
`nc4_grass`, `npcropmin`, `nc3_arctic_grass`, etc.) have been replaced by a
small set of trait predicates loaded from the parameter file via `pftvarcon`:

| Predicate | Type | Meaning |
|---|---|---|
| `woody(ivt)` | `real(r8)` | 0 = non-woody, 1 = tree, 2 = shrub. Test "any woody" with `>= 1.0_r8` (e.g. `MaintenanceRespMod.F90:185`). |
| `needleleaf(ivt)` | integer | 1 = needleleaf, 0 = broadleaf |
| `evergreen(ivt)` | integer | 1 = evergreen, 0 = deciduous |
| `climatezone(ivt)` | integer | 1 = tropical, 2 = temperate, 3 = boreal (used in `FireMod.F90:386-406`, `GapMortalityMod.F90:589-591`) |
| `iscft(ivt)` | logical helper | true for prognostic crops; replaces `ivt >= npcropmin` (e.g. `MaintenanceRespMod.F90:188`) |
| `crop(ivt)`, `graminoid(ivt)` | numeric flags | trait-based ag and grass identification (`FireMod.F90:130`) |
| `col_pp%is_soil(c)` | logical method | replaces `lun_pp%itype(l) == istsoil` |
| `veg_pp%is_on_soil_col(p)` | logical method | replaces patch-on-soil-landunit checks |

These predicates are documented locally in each consumer module. Any wiki snippet
that hard-codes `woody(ivt) == 1` will now miss shrubs.

## Driver Ordering (non-FATES CNP)

Inside `EcosystemDynNoLeaching1` (`EcosystemDynMod.F90:276`, called once per
radiation time step, before soil BGC):

1. Zero patch and column flux accumulators (`col_cf_SetValues`, etc.).
2. `NitrogenDeposition`, then (if `use_fan`) `fan_eval`. `NitrogenFixation` or
   `NitrogenFixation_balance`.
3. (If `.not. use_fates` and `crop_prog`) `NitrogenFert`, `PhosphorusFert`,
   `CNSoyfix`. (If `.not. use_fates`) `MaintenanceResp`.
4. (If `nu_com /= 'RD'`) `PhosphorusWeathering`, then `PhosphorusBiochemMin` or
   `PhosphorusBiochemMin_balance`.
5. `PhosphorusDeposition`.
6. `decomp_rate_constants_bgc` or `_cn` (compute `decomp_k`, `t_scalar`,
   `w_scalar`, `o_scalar`).
7. `decomp_vertprofiles` (update `froot_prof`, `leaf_prof`, `ndep_prof`,
   `nfixation_prof`, `pdep_prof`).
8. `EvaluateSupplStatus`.
9. (If `.not. use_fates`) `Allocation1_PlantNPDemand` -> `TotalNPDemand`.

Inside `EcosystemDynNoLeaching2` (`:481`):

10. `SoilLittDecompAlloc` (decomposition + `Allocation2_ResolveNPLimit`).
11. `SoilLittDecompAlloc2` (calls either `PlantCNPAlloc_RD` or
    `PlantCNPAlloc_ECAMIC`).
12. (If `.not. use_fates`) `Phenology`, `GrowthResp`,
    `veg_cf_summary_rr`, optional `RootDynamics` (when `use_dynroot`),
    `CarbonStateUpdate0`, optional `phenology_flux_limiter`,
    `CNLitterToColumn`, optional `CarbonIsoFlux1` (when `use_c13`/`use_c14`).
13. (If `use_fates`) `col_cf%ZeroForFatesRR`, `alm_fates%UpdateLitterFluxes`.
14. `CarbonStateUpdate1`, `NitrogenStateUpdate1`, `PhosphorusStateUpdate1`
    (run for both modes).
15. `SoilLittVertTransp` (run for both modes).
16. (If `.not. use_fates`) `GapMortality`, optional `CarbonIsoFlux2`,
    `CarbonStateUpdate2`, `NitrogenStateUpdate2`, `PhosphorusStateUpdate2`,
    optional `CNHarvest` + `CarbonStateUpdate2h` family,
    `WoodProducts`, `CropHarvestPools`, `FireArea`, `FireFluxes`.
17. (If `use_fates`) `alm_fates%wrap_WoodProducts`, then `WoodProducts`,
    `CropHarvestPools`.
18. (If `ero_ccycle`) `ErosionFluxes`.
19. (If `.not. use_fates`) `CarbonIsoFlux3` (optional), `CarbonStateUpdate3`.

Inside `EcosystemDynLeaching` (`:121`):

20. `PhosphorusWeathering`, `Adsportion`, `Desoprtion`, `Occlusion`,
    `PhosphorusBiochemMin` (re-run for leaching-step bookkeeping).
21. `NitrogenLeaching`, `PhosphorusLeaching` (unless `pf_cmode .and. pf_hmode`).
22. `NitrogenStateUpdate3`, `PhosphorusStateUpdate3` (stage 3:
    post-leaching, post-fire, post-erosion).
23. `PrecisionControl` (move near-zero negatives to truncation sinks).
24. (If `.not. use_fates`) Veg summary calls (`veg_cf_Summary`, etc.).
25. (If `use_fates`) `col_*%ZeroForFates` for all six column types
    (`:248-253`).
26. Column summary calls (`col_cf_Summary`, `col_cs_Summary`, etc.) — run for
    both modes.
27. (If `use_fates`) `alm_fates%wrap_FatesAtmosphericCarbonFluxes`,
    `alm_fates%wrap_FatesCarbonStocks` (`:267-270`).

See `allocation_and_respiration.md` and `decomposition.md` for the
subroutine-level details of each step.
