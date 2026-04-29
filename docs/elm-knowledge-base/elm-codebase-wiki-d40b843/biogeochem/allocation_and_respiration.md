---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Allocation and Respiration (non-FATES CN/CNP path)

The default ELM allocation, autotrophic respiration, and ecosystem dynamics
driver live in a small cluster of modules under `biogeochem/`. When
`use_fates = .true.` (`main/elm_varctl.F90:227`), FATES replaces the vegetation
allocation, phenology, gap mortality, and growth respiration entirely; the ELM
versions documented here run only when `.not. use_fates`. This doc covers
`AllocationMod.F90`, `CNAllocationBetrMod.F90`, `CNEcosystemDynBetrMod.F90`,
`AnnualUpdateMod.F90`, `GrowthRespMod.F90`, `MaintenanceRespMod.F90`,
`EcosystemDynMod.F90`, `EcosystemBalanceCheckMod.F90`, `CNBeTRIndicatorMod.F90`,
and the carbon state updaters.

## EcosystemDynMod (Driver)

`biogeochem/EcosystemDynMod.F90` is the master driver for per-timestep
biogeochemistry. Public entries:

- `EcosystemDynInit(bounds, elm_fates)` (`:79`) — initializes `AllocationInit`,
  then (if `.not. use_fates`) `PhenologyInit`, `FireInit`,
  `C14_init_BombSpike`, `InitPhenoFluxLimiter`, and `fanInit`. Returns early
  when `use_fates` (`:99`).
- `EcosystemDynLeaching` (`:121`) — final phase, called after the soil/hydrology
  solver has produced updated leaching drivers. Repeats the phosphorus inorganic
  cascade for leaching bookkeeping, calls `NitrogenLeaching` and
  `PhosphorusLeaching` (unless both `pf_cmode` and `pf_hmode` are true), runs
  stage-3 updates (`NitrogenStateUpdate3`, `PhosphorusStateUpdate3`), runs
  `PrecisionControl`, and then summary calls. **At d40b8431** the routine ends
  with a new FATES wrapper block (`:267-270`):

  ```fortran
  if (use_fates) then
     call alm_fates%wrap_FatesAtmosphericCarbonFluxes(bounds, num_soilc, filter_soilc)
     call alm_fates%wrap_FatesCarbonStocks(bounds, num_soilc, filter_soilc)
  endif
  ```

  When `use_fates`, the per-veg summaries are skipped and
  `col_*%ZeroForFates` is called for all six column types
  (`:248-253`). The new `wrap_*` calls then push FATES-side atmospheric C
  fluxes and FATES-side carbon stocks into the ELM column accumulators so the
  subsequent `col_cf_Summary`, `col_cs_Summary`, etc. (`:256-263`) include
  FATES contributions.
- `EcosystemDynNoLeaching1` (`:276`) — phase-1 of the core CN loop, called
  before soil BGC. Executes:
  - `NitrogenDeposition(bounds, atm2lnd_vars)` (`:374`).
  - If `use_fan`, sibling `fan_eval` (`:375-378`) — note this is a separate
    call now, not embedded inside `NitrogenDeposition`.
  - `NitrogenFixation` or `NitrogenFixation_balance` (`:381-390`).
  - If `.not. use_fates` and `crop_prog`, `NitrogenFert`, `PhosphorusFert`,
    `CNSoyfix`, then `MaintenanceResp` (`:392-408`).
  - If `nu_com /= 'RD'`, `PhosphorusWeathering` and either `PhosphorusBiochemMin`
    or `PhosphorusBiochemMin_balance` (`:411-430`).
  - `PhosphorusDeposition` (`:437`).
  - `decomp_rate_constants_bgc` or `_cn` (`:442-448`).
  - `decomp_vertprofiles` (`:453-455`).
  - `EvaluateSupplStatus` (`:462`).
  - If `.not. use_fates`, `Allocation1_PlantNPDemand` (`:467-478`).
- `EcosystemDynNoLeaching2` (`:481`) — phase-2 of the core CN loop, called after
  soil BGC. Executes `SoilLittDecompAlloc` and `SoilLittDecompAlloc2`
  (which dispatches `Allocation2_ResolveNPLimit` then either `PlantCNPAlloc_RD`
  or `PlantCNPAlloc_ECAMIC` based on `nu_com`); when `.not. use_fates` runs
  `Phenology`, `GrowthResp`, `veg_cf_summary_rr`, optional `RootDynamics`,
  `CarbonStateUpdate0`, optional `phenology_flux_limiter`, `CNLitterToColumn`,
  optional `CarbonIsoFlux1`. **At d40b8431**, when `use_fates` (`:682-690`):

  ```fortran
  if(use_fates) then
     call col_cf%ZeroForFatesRR(bounds,num_soilc, filter_soilc)
     call alm_fates%UpdateLitterFluxes(bounds)
  end if
  ```

  Then `CarbonStateUpdate1`, `NitrogenStateUpdate1`, `PhosphorusStateUpdate1`,
  and `SoilLittVertTransp` run unconditionally for both modes
  (`:692-718`).

  When `.not. use_fates`, the routine continues with `GapMortality`, optional
  isotope flux 2, `CarbonStateUpdate2`, `NitrogenStateUpdate2`,
  `PhosphorusStateUpdate2`, optional `CNHarvest` and the 2h-suffixed updates,
  `WoodProducts`, `CropHarvestPools`, `FireArea`, `FireFluxes` (`:720-808`).

  When `use_fates` (`:810-817`), `alm_fates%wrap_WoodProducts` runs first
  (`:811`), then `WoodProducts` and `CropHarvestPools` still run (so harvested
  product accounting is centralized on the ELM side).

  Then `ErosionFluxes` (if `ero_ccycle`), and stage-3 updates are run only when
  `.not. use_fates` (`:829-872`).

## AllocationMod: Refactored Three-Phase Plant C/N/P Allocation

`biogeochem/AllocationMod.F90` (4557 lines, +631 over 60d9aad) implements the
default non-FATES CN/CNP allocation. The header at `:64` declares the public
entry points:

```
public :: PlantCNPAlloc_RD, PlantCNPAlloc_ECAMIC     !Plant C/N/P Allocation; called in SoilLittDecompAlloc2
```

The legacy `Allocation3_PlantCNPAlloc` no longer exists. Instead the dispatcher
in `SoilLittDecompMod.F90:758-771` selects between the two:

```fortran
if(.not.use_fates)then
  call t_startf('CNAllocation - phase-3')
  if(nu_com .eq. 'RD') then
     call PlantCNPAlloc_RD(bounds, num_soilc, filter_soilc, num_soilp, &
                           filter_soilp, canopystate_vars, cnstate_vars, &
                           crop_vars, dt)
  else
     call PlantCNPAlloc_ECAMIC(bounds, num_soilc, filter_soilc, num_soilp, &
                               filter_soilp, canopystate_vars, cnstate_vars, &
                               crop_vars, dt)
  endif
  call t_stopf('CNAllocation - phase-3')
end if
```

### AllocParamsType (instance `AllocParamsInst`)

Read from the parameters NetCDF by `readCNAllocParams` (`AllocationMod.F90:146`):

- `bdnr` (1/s): bulk denitrification rate
- `dayscrecover`: number of days to recover a negative `cpool`
- `compet_plant_no3`, `compet_plant_nh4`: plant relative competitiveness for
  NO3 / NH4
- `compet_decomp_no3`, `compet_decomp_nh4`: immobilizer competitiveness
- `compet_denit`, `compet_nit`: denitrifier / nitrifier competitiveness

Supplemental N/P modes `suplnitro` (default `NONE`), `suplphos` (default `ALL`).
ECA competition options: `nu_com_leaf_physiology`, `nu_com_root_kinetics`,
`nu_com_phosphatase`, `nu_com_nfix`. ECA scaling factors (module-level parameters
at `:132` and `:135`):

```fortran
real(r8), parameter :: e_plant_scalar  = 0.0000125_r8
real(r8), parameter :: e_decomp_scalar = 0.05_r8
```

### Allocation1_PlantNPDemand (`:384`)

In d40b8431 this is now a thin wrapper (~92 lines, `:384-475`). Its body calls
`TotalNPDemand` at `:412` and then `p2c_1d_filter` to aggregate to column.
**The old per-PFT allometric demand math is now in `TotalNPDemand`.** Anything
grepping for `Allocation1_PlantNPDemand` and expecting to see allometric flux
partitioning (`froot_leaf`, `stem_leaf`, `croot_stem`, `flivewd`, `grperc`,
`grpnow`) will not find it here.

### TotalNPDemand (`:477`, NEW at d40b8431)

`TotalNPDemand(num_soilp, filter_soilp, photosyns_vars, canopystate_vars,
crop_vars, cnstate_vars, dt)` (`:477-1048`) holds the per-PFT allometric demand
math:

- Computes plant N and P demand from GPP (post maintenance respiration) and
  target C:N, C:P ratios for each tissue.
- Applies the allometric flux partition using PFT parameters `froot_leaf`,
  `stem_leaf`, `croot_stem`, `flivewd`, `grperc`, `grpnow`, plus flux
  parameters from `veg_vp`.
- Crop-specific allocation parameters (`declfact`, `bfact`, `aleaff`, `arootf`,
  `astemf`, `arooti`, `fleafi`, `allconsl`, `allconss`) for prognostic crops
  selected via the `iscft(ivt)` predicate (replacing `ivt >= npcropmin`).
- Outputs `plant_calloc_patch`, `availc_patch`, `plant_ndemand`,
  `plant_pdemand`, `fnc` (retranslocation N fraction), and column-level
  profiles `plant_nh4_vmax_vr_patch` via `calc_plantN_kineticpar`.

### Allocation2_ResolveNPLimit (`:1052`)

Called from inside `SoilLittDecompAlloc` (`biogeochem/SoilLittDecompMod.F90`).
Given the decomposer potential immobilization (`potential_immob_vr_col`,
`potential_immob_p_vr_col`) computed from the cascade and plant demand from
phase 1, it resolves the N and P competition. Outputs:

- `fpi_vr_col`, `fpi_col` (fraction of potential immobilization for N, 0..1)
- `fpi_p_vr_col`, `fpi_p_col` (for P)
- `fpg_col` (fraction of potential GPP, N-limited)
- `fpg_p_col` (fraction of potential GPP, P-limited)
- `actual_immob_vr_col`, `sminn_to_plant_vr_col`
- `supplement_to_sminn_vr_col`, `supplement_to_sminp_vr_col` (when
  `suplnitro`/`suplphos` is active)

Under RD mode (`nu_com == 'RD'`), plant and decomposer shares are set by their
relative demand weighted by `compet_*` parameters. Under ECA mode, per-level
Michaelis-Menten uptake rates on NH4, NO3 and PO4 are computed from
`plant_nh4_vmax_vr_patch`, `plant_nh4_km_vr_patch` etc. in
`PlantMicKineticsMod.F90`, with enzyme abundance proportional to fine-root
biomass via `calc_nuptake_prof` (`:3150`) and `calc_puptake_prof` (`:3238`).

### PlantCNPAlloc_ECAMIC (`:2113`)

`PlantCNPAlloc_ECAMIC(bounds, num_soilc, filter_soilc, num_soilp,
filter_soilp, canopystate_vars, cnstate_vars, crop_vars, dt)` is the
non-RD final-allocation entry point. At `:2113-2201` it orchestrates
`NAllocationECAMIC` (`:2390`) and `PAllocationECAMIC` (`:2710`) followed by
`DistributeN_ECAMIC` (`:3794`) and the analogous P distribution. The output
fluxes are `cpool_to_leafc_patch`, `cpool_to_leafc_storage_patch` and the
analogous fluxes for fine root, live stem, dead stem, live coarse root, dead
coarse root, grain, and growth respiration storage; same for `npool_to_*_patch`
and `ppool_to_*_patch`.

### PlantCNPAlloc_RD (`:2203`)

`PlantCNPAlloc_RD` is the relative-demand variant, structurally analogous but
calling `NAllocationRD` (`:2914`), `PAllocationRD` (`:3074`), and
`DistributeN_RD` (`:3380`). The display (`_patch`) versus storage
(`_storage_patch`) split is controlled by `alloc_pnow_patch` (set in
`PhenologyMod`): during active growing season most C goes to display, during
dormancy to storage.

`excess_cflux_patch` records C that was not allocated due to N/P
downregulation; it feeds `xr_patch` (excess respiration). If `cpool` goes
negative, `xsmrpool_recover_patch` schedules recovery from the `xsmrpool` over
`dayscrecover` days.

### dynamic_plant_alloc and EvaluateSupplStatus

`dynamic_plant_alloc` implements a cost-benefit allocation variant using
partial derivatives stored in `nitrogenstate_type` (`benefit_pgpp_pleafc_patch`,
`cost_pgpp_pfrootc_patch`, etc.). Active when `NFIX_PTASE_plant` is enabled.
`EvaluateSupplStatus` (`:282`) toggles `suplnitro` / `suplphos` off when spinup
criteria are met.

### AllocationInit (`:213`)

`AllocationInit(bounds, elm_fates)` reads PFT allocation coefficients `arepr`
and `aroot` from `pftvarcon`, allocates module-scope arrays
(`veg_rootc_bigleaf`, `ft_index_bigleaf`), and reads `AllocParamsInst` from the
parameter file. If `use_fates` is true, most of the per-PFT arrays are not
allocated because FATES owns allocation.

## AnnualUpdateMod

`biogeochem/AnnualUpdateMod.F90` has a single public routine `AnnualUpdate`
that rolls temporal accumulators. At the end of each simulated year (detected
via `annsum_counter_col >= dayspyr_mod * secspday`), it:

1. Copies `tempsum_potential_gpp_patch -> annsum_potential_gpp_patch` and
   zeros the temp.
2. Copies `tempmax_retransn_patch -> annmax_retransn_patch` and zeros the temp.
3. Copies `tempmax_retransp_patch -> annmax_retransp_patch` and zeros the temp.
4. Copies `tempavg_t2m_patch -> annavg_t2m_patch`, zeros the temp.
5. Multiplies `tempsum_npp * dt -> annsum_npp` (rate to annual total).
6. Aggregates `annsum_npp` and `annavg_t2m_patch` to column-level via `p2c`.

`annsum_npp_col` and `annavg_t2m_col` are used by `NitrogenFixation` and by
temperature-driven processes respectively.

## MaintenanceRespMod

`biogeochem/MaintenanceRespMod.F90` (223 lines) computes autotrophic
maintenance respiration (MR). Single public routine `MaintenanceResp` (`:79`).
Base rate `br_mr_Inst` is read from the parameters file.

The `woody` flag is now ternary: `0 = non-woody, 1 = tree, 2 = shrub`
(comment at `:110`). The "any woody" test at `:185` is `>= 1.0_r8`:

```fortran
woody          =>    veg_vp%woody                      , & ! Input:  [real(r8) (:)   ]  woody lifeform flag (0 = non-woody, 1 = tree, 2 = shrub)
...
if (woody(ivt(p)) >= 1.0_r8) then
   livestem_mr   = livestemn * br_mr * tc
   livecroot_mr  = livecrootn * br_mr * tc
else if (iscft(ivt(p)) .and. livestemn(p) .gt. 0._r8) then
   livestem_mr   = livestemn * br_mr * tc
   grain_mr      = grainn    * br_mr * tc
end if
```

`iscft` (use'd from `pftvarcon` at `:15`) replaces the legacy
`ivt(p) >= npcropmin` test (`:188`).

For each soil patch:

```
tc = Q10^((t_ref2m - 273.15 - 20) / 10)
if frac_veg_nosno == 1:
    leaf_mr = lmrsun * laisun * 12.011e-6  +  lmrsha * laisha * 12.011e-6
else:
    leaf_mr = 0
if br_xr(ivt) > 1e-9:
    xr = cpool * br_xr(ivt) * tc
else:
    xr = 0
```

Fine root MR uses depth-resolved soil temperature
`tcsoi(c,j) = Q10^((t_soisno(c,j) - 273.15 - 20)/10)` weighted by `rootfr_patch`:

```
froot_mr(p) = sum_j ( frootn(p) * br_mr * tcsoi(c,j) * rootfr(p,j) )
```

Q10 is pulled from `ParamsShareInst%Q10_mr`. The `FIX(SPM,032414)` note at
`:77` indicates that `MaintenanceResp` should not be called under FATES; the
guard is enforced inside `EcosystemDynNoLeaching1` at `:392-408` (the
`if(.not.use_fates)then` block surrounding the `MaintenanceResp` call).

## GrowthRespMod

`biogeochem/GrowthRespMod.F90` assigns growth respiration (GR). Single public
routine `GrowthResp` (`:33`). Per-PFT parameter `grperc(ivt)` is the fraction
of allocated C that goes to growth respiration. `grpnow(ivt)` is the fraction
of GR that happens at the time of allocation versus later when the transfer
pool releases its contents.

```
cpool_leaf_gr          = cpool_to_leafc * grperc(ivt)
cpool_leaf_storage_gr  = cpool_to_leafc_storage * grperc(ivt) * grpnow(ivt)
transfer_leaf_gr       = leafc_xfer_to_leafc  * grperc(ivt) * (1 - grpnow(ivt))
```

Same structure for fine root, live stem, dead stem, live coarse root, dead
coarse root (woody only), and grain (crops only). Wood pools are computed
when `woody(ivt) >= 1.0_r8` (covers both trees and shrubs in d40b8431). Crop
pools require `iscft(ivt)` per the trait-flag refactor.

## EcosystemBalanceCheckMod

`biogeochem/EcosystemBalanceCheckMod.F90` implements mass conservation checks
at column and grid levels for C, N, and P. Tolerance
`balance_check_tolerance = 1e-8_r8`. Public routines:

- `BeginColCBalance`, `BeginColNBalance`, `BeginColPBalance`: save `totcolc` /
  `totcoln` / `totcolp` into `col_cs%begcb` / `col_ns%begnb` / `col_ps%begpb` at
  start of time step.
- `ColCBalanceCheck`, `ColNBalanceCheck`, `ColPBalanceCheck`: compute
  end-of-step `endcb - begcb - net_input_flux * dt`, abort if `|err| >
  tolerance`.
- `BeginGridCBalance`, `GridCBalanceCheck`: grid-level equivalents, account
  for `dyn_cbal_adjustments_col`.
- `EndGrid{C,N,P}BalanceAfterDynSubgridDriver`: a second grid check after the
  dynamic subgrid driver has finished shifting weights.

## CarbonStateUpdate Mod 1/2/3

ELM updates carbon (and N, and P) pools in three stages per radiation time
step, matching the three-phase structure of allocation, gap mortality, and
leaching.

### CarbonStateUpdate0 / CarbonStateUpdate1 (`biogeochem/CarbonStateUpdate1Mod.F90:140` / `:170`)

`CarbonStateUpdate0(num_soilp, filter_soilp, veg_cs, veg_cf, dt)` is called
from `EcosystemDynNoLeaching2` (`:638`) in the `.not. use_fates` block; it
adds fresh photosynthate `psnsun_to_cpool * dt + psnshade_to_cpool * dt` to
`cpool`. `CarbonStateUpdate1(bounds, num_soilc, filter_soilc, num_soilp,
filter_soilp, crop_vars, col_cs, veg_cs, col_cf, veg_cf, dt)` (`:170`) then
runs unconditionally (both `use_fates` and `.not. use_fates` paths) at
`EcosystemDynMod.F90:694`. It steps:

- `cpool` <- minus MR, minus GR, minus allocation (plus transfer in).
- `leafc` <- plus display allocation, plus xfer flux, minus litterfall.
- `leafc_storage` <- plus storage allocation, minus storage -> xfer.
- `leafc_xfer` <- plus storage -> xfer, minus xfer -> leafc.
- Same three updates per tissue (froot, livestem, deadstem, livecroot,
  deadcroot, grain).
- `livestemc` <- plus allocation, minus livewood-to-deadwood turnover.
- `deadstemc` <- plus allocation, plus livewood-to-deadwood turnover.
- `xsmrpool` <- plus excess MR diversion.
- Column `decomp_cpools_vr(c,j,l)` <- plus decomposition cascade transfers
  (litter input from phenology under `.not. use_fates`, or from
  `alm_fates%UpdateLitterFluxes` under `use_fates`).

The semantic meaning of this stage is "post-photosynthesis and post-allocation,
before gap mortality": all the non-mortality fluxes computed during the
current time step have been applied. Note `CarbonStateUpdate1` running for
both `use_fates` and `.not. use_fates` is by design at d40b8431 — the column
decomposing pools are managed by ELM regardless of mode.

### CarbonStateUpdate2 / CarbonStateUpdate2h (`biogeochem/CarbonStateUpdate2Mod.F90:32` / `:118`)

Called from `EcosystemDynNoLeaching2` after `GapMortality` (only when
`.not. use_fates`). Updates pools for gap-phase mortality fluxes
(`m_*_to_litter_patch`) and harvest mortality fluxes (`hrv_*_to_litter_patch`).
The column-level decomposing pools also receive gap-mortality litter inputs.

Semantic meaning: "post-gap-mortality and post-harvest".

### CarbonStateUpdate3 (`biogeochem/CarbonStateUpdate3Mod.F90:32`)

Called from `EcosystemDynNoLeaching2` only when `.not. use_fates`
(`EcosystemDynMod.F90:841`). Applies fire loss fluxes (`m_*_to_fire_patch`,
`m_decomp_cpools_to_fire_vr_col`), the `m_*_to_litter_fire_patch` uncombusted
wood -> CWD transfers, and SOM erosion losses (if `ero_ccycle`). Semantic
meaning: "post-fire, post-erosion, post-leaching".

The N and P equivalents have the same three-stage structure and the same
semantics:

- Stage 1 = after photosynthesis / allocation / decomposition-cascade transfers.
- Stage 2 = after gap mortality / harvest.
- Stage 3 = after fire / erosion / leaching.

`biogeochem/NitrogenStateUpdate1Mod.F90:101` (`NitrogenStateUpdate1`),
`NitrogenStateUpdate2Mod.F90:33` and `:112` (`NitrogenStateUpdate2`,
`NitrogenStateUpdate2h`), `NitrogenStateUpdate3Mod.F90:31`
(`NitrogenStateUpdate3`) mirror this for N.
`biogeochem/PhosphorusStateUpdate1Mod.F90:99` (`PhosphorusStateUpdate1`),
`PhosphorusStateUpdate2Mod.F90:34` and `:117` (`PhosphorusStateUpdate2`,
`PhosphorusStateUpdate2h`), `PhosphorusStateUpdate3Mod.F90:40`
(`PhosphorusStateUpdate3`) mirror it for P.

Additionally each stage has a `StateUpdateDynPatch` variant
(`NitrogenStateUpdate1Mod.F90:45`, `PhosphorusStateUpdate1Mod.F90:44`) that
handles state changes driven by dynamic subgrid weight adjustments. These are
called once per time step outside the three main stages, from
`dynSubgridControlMod`.

## BeTR Allocation Path

`biogeochem/CNAllocationBetrMod.F90` and `biogeochem/CNEcosystemDynBetrMod.F90`
provide a parallel allocation/ecosystem-dynamics path for the BeTR
(Benchmarking Ecosystem Tracer Responses) soil-column abstraction, used when
ELM is coupled to PFLOTRAN for reactive transport.

### CNAllocationBetrMod

Mirrors `AllocationMod.F90` but fetches nutrient availability from the BeTR-side
tracer state rather than from the default `col_ns%sminn_vr_col` /
`col_ps%solutionp_vr_col` pools. Public entries:

- `CNAllocationBeTRInit` (initialization).
- `SetPlantMicNPDemand`.
- `Allocation3_PlantCNPAlloc` (BeTR keeps the legacy single-entry name) and
  private `Allocation1_PlantNPDemand`, `dynamic_plant_alloc`.

NOTE: this is the BeTR sibling, not the default `AllocationMod` — the BeTR
module retained the old name `Allocation3_PlantCNPAlloc` because it was not
refactored alongside the default path. Code that grep-finds
`Allocation3_PlantCNPAlloc` in d40b8431 will land here, not in
`AllocationMod.F90`.

ECA scaling factors `E_plant_scalar = 1.25e-5`, `E_decomp_scalar = 0.05`.

### CNEcosystemDynBetrMod

`CNEcosystemDynBeTR` is the BeTR driver, called instead of
`EcosystemDynNoLeaching{1,2}` when `is_active_betr_bgc` is set. It orchestrates:
`NitrogenDeposition`, `NitrogenFixation(_balance)`, `MaintenanceResp`,
`SoilLittDecompAlloc`, `CNPhenology` (from `CNPhenologyBeTRMod`), `GrowthResp`,
`CarbonStateUpdate0/1`, `NStateUpdate1` (from `CNNStateUpdate1BeTRMod`),
`CNGapMortality` (from `CNGapMortalityBeTRMod`), `CarbonStateUpdate2/2h`,
`NStateUpdate2/2h`, `FireArea/FireFluxes`, `CarbonStateUpdate3`,
`CarbonIsoFlux*`, `C14Decay`, `WoodProducts`, `decomp_rate_constants_bgc/_cn`,
`CropHarvestPools`, `SetPlantMicNPDemand`, `Allocation3_PlantCNPAlloc`
(BeTR variant), `NStateUpdate3`, `NitrogenFixation_balance`,
`PhosphorusStateUpdate{1,2,2h}`, `PhosphorusBiochemMin_balance`,
`PhosphorusDeposition`, `PhosphorusWeathering`, `decomp_vertprofiles`,
`RootDynamics`, and `CNFluxStateBetrSummary`.

## CNBeTRIndicatorMod

`biogeochem/CNBeTRIndicatorMod.F90` defines per-flux indicator arrays
`pheno_indicator(3)` and `gap_indicator(19)` used to selectively zero out
phenology or gap-mortality fluxes when running under BeTR coupling. The
routines `set_pheno_indicators` and `set_gap_indicators` currently set all
indicators to 1 and then `return` immediately. This module is a stub for future
tracer-transport overrides.

## Summary Flow (d40b8431)

The typical sequence within a single radiation time step for a non-FATES CNP run:

1. `EcosystemDynNoLeaching1`: zero fluxes, N/P deposition + (optional) FAN +
   fixation, MR, P weathering, P biochem min, decomposition rate constants,
   vertical profiles, supplement status, `Allocation1_PlantNPDemand` (which
   delegates to `TotalNPDemand`).
2. `SoilLittDecompAlloc` (called from `EcosystemDynNoLeaching2`): compute
   decomposition fluxes, call `Allocation2_ResolveNPLimit`, write `fpi_vr_col`,
   `fpg_col`.
3. `SoilLittDecompAlloc2`: dispatch on `nu_com` to either `PlantCNPAlloc_RD`
   or `PlantCNPAlloc_ECAMIC` to apply downregulation and produce final
   `cpool_to_*`, `npool_to_*`, `ppool_to_*` fluxes.
4. `Phenology`, `GrowthResp`, optional `RootDynamics`, optional
   `phenology_flux_limiter`, `CNLitterToColumn`.
5. `CarbonStateUpdate0`, `CarbonStateUpdate1`, `NitrogenStateUpdate1`,
   `PhosphorusStateUpdate1` (stage 1).
6. `SoilLittVertTransp`.
7. `GapMortality`, `CarbonStateUpdate2`, `NitrogenStateUpdate2`,
   `PhosphorusStateUpdate2` (stage 2).
8. Optional `CNHarvest` and `*StateUpdate2h`.
9. `WoodProducts`, `CropHarvestPools`, `FireArea`, `FireFluxes`.
10. (If `ero_ccycle`) `ErosionFluxes`.
11. `CarbonIsoFlux*`, `C14Decay`, `C14BombSpike`. `CarbonStateUpdate3`
    for C only at this stage.
12. `EcosystemDynLeaching`: P inorganic cascade re-run, `NitrogenLeaching`,
    `PhosphorusLeaching`, `NitrogenStateUpdate3`, `PhosphorusStateUpdate3`
    (stage 3).
13. `PrecisionControl`, summary routines.

When FATES is active:

- Steps 4-9 (vegetation phenology, growth/maintenance respiration, gap
  mortality, harvest) are bypassed. FATES runs its own cohort-level allocation,
  phenology, mortality, and growth.
- New step 4.5: between `SoilLittDecompAlloc2` and `CarbonStateUpdate1`,
  `col_cf%ZeroForFatesRR` and `alm_fates%UpdateLitterFluxes` execute
  (`EcosystemDynNoLeaching2:686-689`). FATES delivers its litter into the ELM
  decomposing pools through `UpdateLitterFluxes`.
- `CarbonStateUpdate1`, `NitrogenStateUpdate1`, `PhosphorusStateUpdate1`, and
  `SoilLittVertTransp` run for both modes (`:692-718`).
- New step 9.5: `alm_fates%wrap_WoodProducts` fires before `WoodProducts` and
  `CropHarvestPools` (`:811`).
- New step 13.5: `alm_fates%wrap_FatesAtmosphericCarbonFluxes` and
  `alm_fates%wrap_FatesCarbonStocks` close the leaching pass
  (`EcosystemDynLeaching:267-270`), pushing FATES C pools and atmospheric
  exchange into the column summaries.
