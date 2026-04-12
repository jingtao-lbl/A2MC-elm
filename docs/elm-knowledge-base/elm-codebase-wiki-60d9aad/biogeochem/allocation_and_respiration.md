---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Allocation and Respiration (non-FATES CN/CNP path)

The default ELM allocation, autotrophic respiration, and ecosystem dynamics driver live in a small cluster of modules under `biogeochem/`. When `use_fates = .true.` (`main/elm_varctl.F90:222`), FATES replaces these routines entirely. The ELM versions documented here run only when `.not. use_fates`. This doc covers `AllocationMod.F90`, `CNAllocationBetrMod.F90`, `CNEcosystemDynBetrMod.F90`, `AnnualUpdateMod.F90`, `GrowthRespMod.F90`, `MaintenanceRespMod.F90`, `EcosystemDynMod.F90`, `EcosystemBalanceCheckMod.F90`, `CNBeTRIndicatorMod.F90`, and the carbon state updaters.

## EcosystemDynMod (Driver)

`biogeochem/EcosystemDynMod.F90` is the master driver for per-timestep biogeochemistry. It provides four public entry points:

- `EcosystemDynInit(bounds, elm_fates)` (`:79`): initializes `AllocationInit`, then (if `.not. use_fates`) `PhenologyInit`, `FireInit`, `C14_init_BombSpike`, `InitPhenoFluxLimiter`, and `fanInit`.
- `EcosystemDynNoLeaching1` (`:280`): phase-1 of the core CN loop, called before soil BGC. Executes deposition (N, P), fixation, maintenance respiration, phosphorus weathering and biochemical mineralization, decomposition rate constants (via `decomp_rate_constants_bgc` or `_cn`), vertical profiles (`decomp_vertprofiles`), supplement-status evaluation, and `Allocation1_PlantNPDemand`.
- `EcosystemDynNoLeaching2` (`:488`): phase-2 of the core CN loop, called after soil BGC. Executes `SoilLittDecompAlloc` (including `Allocation2_ResolveNPLimit`), `SoilLittDecompAlloc2` (including `Allocation3_PlantCNPAlloc`), `Phenology`, `CNLitterToColumn`, `GrowthResp`, `CarbonStateUpdate0/1`, `NitrogenStateUpdate1`, `PhosphorusStateUpdate1`, `GapMortality`, stage-2 updates, `FireArea`, `FireFluxes`, `ErosionFluxes`, `CarbonIsoFlux*`, `C14Decay`, `WoodProducts`, `CropHarvestPools`, `SoilLittVertTransp`, and `RootDynamics`.
- `EcosystemDynLeaching` (`:121`): final phase, called after the soil/hydrology solver has produced updated leaching drivers. Repeats the phosphorus inorganic cascade updates for leaching bookkeeping, calls `NitrogenLeaching` and `PhosphorusLeaching` (unless both `pf_cmode` and `pf_hmode` are true, in which case PFLOTRAN handles N leaching), runs stage-3 updates (`NitrogenStateUpdate3`, `PhosphorusStateUpdate3`), runs `PrecisionControl`, and then calls the pool summary routines (`col_cf_Summary`, `col_nf_Summary`, `col_pf_Summary`, plus the vegetation summary routines). When `use_fates = .true.`, the veg summaries are skipped and `col_{cs,ns,ps,cf,nf,pf}%ZeroForFates` is called instead so the ELM-side veg pools remain zero (FATES supplies its own summary flow). See `EcosystemDynMod.F90:253`.

## AllocationMod: Three-Phase Plant C/N/P Allocation

`biogeochem/AllocationMod.F90` (3926 lines) implements the default non-FATES CN/CNP allocation. Header comment at `:56`:

> Allocation is divided into 3 subroutines/phases:
>   `Allocation1_PlantNPDemand`     !Plant N/P Demand;       called in EcosystemDynNoLeaching1
>   `Allocation2_ResolveNPLimit`    !Resolve N/P Limitation; called in SoilLittDecompAlloc
>   `Allocation3_PlantCNPAlloc`     !Plant C/N/P Allocation; called in SoilLittDecompAlloc2

### AllocParamsType (instance `AllocParamsInst`)

Read from the parameters NetCDF by `readCNAllocParams` (`AllocationMod.F90:140`):
- `bdnr` (1/s): bulk denitrification rate
- `dayscrecover`: number of days to recover a negative `cpool`
- `compet_plant_no3`, `compet_plant_nh4`: plant relative competitiveness for NO3 / NH4
- `compet_decomp_no3`, `compet_decomp_nh4`: immobilizer competitiveness
- `compet_denit`, `compet_nit`: denitrifier / nitrifier competitiveness

Supplemental N/P modes `suplnitro` (default `NONE`), `suplphos` (default `ALL`). ECA competition options: `nu_com_leaf_physiology`, `nu_com_root_kinetics`, `nu_com_phosphatase`, `nu_com_nfix` (all false by default). ECA scaling factors: `e_plant_scalar = 1.25e-5`, `e_decomp_scalar = 0.05` (plant and decomposer enzyme abundance per fine-root biomass; `:125-129`).

### Allocation1_PlantNPDemand (`:378`)

Computes plant N and P demand. Takes GPP (post maintenance respiration) and target C:N, C:P ratios for each tissue, computes an allometric flux partition using PFT parameters `froot_leaf`, `stem_leaf`, `croot_stem`, `flivewd` (fraction of new wood that is live), `grperc`, `grpnow`, plus flux parameters from `veg_vp`. The demand is expressed as a required rate of `sminn_to_npool` and `sminp_to_ppool`. Crop-specific allocation parameters (`declfact`, `bfact`, `aleaff`, `arootf`, `astemf`, `arooti`, `fleafi`, `allconsl`, `allconss`) are used for prognostic crops when `ivt >= npcropmin`. Outputs include `plant_calloc_patch`, `availc_patch`, `plant_ndemand`, `plant_pdemand`, `fnc` (retranslocation N fraction), and column-level profiles `plant_nh4_vmax_vr_patch` via `calc_plantN_kineticpar`.

### Allocation2_ResolveNPLimit (`:928`)

Called from inside `SoilLittDecompAlloc` (`biogeochem/SoilLittDecompMod.F90`). Given the decomposer potential immobilization (`potential_immob_vr_col`, `potential_immob_p_vr_col`) computed from the cascade, and given plant demand from Phase 1, it resolves the N and P competition. Outputs:

- `fpi_vr_col`, `fpi_col` (fraction of potential immobilization for N, 0..1)
- `fpi_p_vr_col`, `fpi_p_col` (for P)
- `fpg_col` (fraction of potential GPP, N-limited)
- `fpg_p_col` (fraction of potential GPP, P-limited)
- `actual_immob_vr_col`, `sminn_to_plant_vr_col` (realized immobilization and plant uptake)
- `supplement_to_sminn_vr_col`, `supplement_to_sminp_vr_col` (when `suplnitro`/`suplphos` is active)

Depending on `nu_com` (`'RD'` for relative demand, default; `'ECA'` for enzyme-competition), the resolution algorithm is different. Under RD mode, plant and decomposer shares are set by their relative demand weighted by the `compet_*` parameters. Under ECA mode, per-level Michaelis-Menten uptake rates on NH4, NO3 and PO4 are computed from `plant_nh4_vmax_vr_patch`, `plant_nh4_km_vr_patch` etc. in `PlantMicKineticsMod.F90`, with enzyme abundance proportional to fine-root biomass via `calc_nuptake_prof` and `calc_puptake_prof` (private helpers inside AllocationMod). The ECA path is engaged when `nu_com /= 'RD'`.

### Allocation3_PlantCNPAlloc (`:1851`)

Called from `SoilLittDecompAlloc2`. Takes the resolved `fpg_col`, `fpg_p_col` and computes the actual allocation fluxes, writing `cpool_to_leafc_patch`, `cpool_to_leafc_storage_patch`, and the analogous fluxes for fine root, live stem, dead stem, live coarse root, dead coarse root, grain, and growth respiration storage. Same for `npool_to_*_patch` and `ppool_to_*_patch`. The split between display (`_patch` suffix) and storage (`_storage_patch`) is controlled by `alloc_pnow_patch` (set in `PhenologyMod`): during active growing season most C goes to display, during dormancy to storage.

`excess_cflux_patch` records C that was not allocated due to N/P downregulation; it feeds `xr_patch` (excess respiration). If `cpool` goes negative (common when `MR > GPP` under cold stress), `xsmrpool_recover_patch` schedules recovery from the `xsmrpool` over `dayscrecover` days.

### dynamic_plant_alloc and EvaluateSupplStatus

`dynamic_plant_alloc` implements a cost-benefit allocation variant using the partial derivatives stored in `nitrogenstate_type` (`benefit_pgpp_pleafc_patch`, `cost_pgpp_pfrootc_patch`, etc.). Active when `NFIX_PTASE_plant` is enabled. `EvaluateSupplStatus` toggles `suplnitro` / `suplphos` off when spinup criteria are met.

### AllocationInit

`AllocationInit(bounds, elm_fates)` reads PFT allocation coefficients `arepr` and `aroot` from `pftvarcon`, allocates module-scope arrays (`veg_rootc_bigleaf`, `ft_index_bigleaf`), and reads `AllocParamsInst` from the parameter file. If `use_fates` is true, most of the per-PFT arrays are not allocated because FATES owns allocation.

## AnnualUpdateMod

`biogeochem/AnnualUpdateMod.F90` has a single public routine `AnnualUpdate` that rolls temporal accumulators. At the end of each simulated year (detected via `annsum_counter_col >= dayspyr_mod * secspday`), it:

1. Copies `tempsum_potential_gpp_patch -> annsum_potential_gpp_patch` and zeros the temp.
2. Copies `tempmax_retransn_patch -> annmax_retransn_patch` and zeros the temp.
3. Copies `tempmax_retransp_patch -> annmax_retransp_patch` and zeros the temp.
4. Copies `tempavg_t2m_patch -> annavg_t2m_patch`, zeros the temp.
5. Multiplies `tempsum_npp * dt -> annsum_npp` (converts rate to annual total).
6. Aggregates `annsum_npp` and `annavg_t2m_patch` to column-level via `p2c`.

`annsum_npp_col` and `annavg_t2m_col` are used by `NitrogenFixation` (annual NPP-based fixation) and by temperature-driven processes respectively.

## MaintenanceRespMod

`biogeochem/MaintenanceRespMod.F90` computes autotrophic maintenance respiration (MR). The single public routine is `MaintenanceResp` (`:79`). Base rate `br_mr_Inst` is read from the parameters file by `readMaintenanceRespParams`.

Per Peter Thornton's comment (`:139`): base rate originally from Ryan 1991, 0.0106 molC/(molN h) converted to 2.525e-6 gC/(gN s). Q10 is pulled from `ParamsShareInst%Q10_mr` (shared with heterotrophic respiration Q10 `ParamsShareInst%Q10_hr`); originally Q10 was 2.0 but was reduced to 1.5 as part of tuning the atmospheric CO2 seasonal cycle.

For each soil patch:

```
tc = Q10^((t_ref2m - 273.15 - 20) / 10)   ! 2m temperature correction
if (frac_veg_nosno == 1):
    leaf_mr = lmrsun * laisun * 12.011e-6  +  lmrsha * laisha * 12.011e-6   ! from photosynthesis leaf MR
else:
    leaf_mr = 0                                                              ! snow-covered

if woody:
    livestem_mr   = livestemn * br_mr * tc
    livecroot_mr  = livecrootn * br_mr * tc
else if crop (ivt >= npcropmin and livestemn > 0):
    livestem_mr   = livestemn * br_mr * tc
    grain_mr      = grainn    * br_mr * tc

if br_xr(ivt) > 1e-9:
    xr = cpool * br_xr(ivt) * tc    ! excess carbon respiration
else:
    xr = 0
```

Fine root MR uses a depth-resolved soil temperature correction `tcsoi(c,j) = Q10^((t_soisno(c,j) - 273.15 - 20)/10)` weighted by the rooting fraction `rootfr_patch(p,j)`:

```
froot_mr(p) = sum_j ( frootn(p) * br_mr * tcsoi(c,j) * rootfr(p,j) )
```

Note the leaf MR is sourced from `lmrsun` / `lmrsha` which are computed by the photosynthesis module (`PhotosynthesisType`), so leaf MR is tied to leaf stoichiometry via the Photosynthesis-Respiration coupling in the canopy, not via `leafn` directly. `FIX(SPM,032414)` note at `:77` indicates that `MaintenanceResp` should not be called under FATES; the guard is in `EcosystemDynNoLeaching1` (`:396`).

## GrowthRespMod

`biogeochem/GrowthRespMod.F90` assigns growth respiration (GR). Single public routine `GrowthResp` (`:33`). Per-PFT parameter `grperc(ivt)` is the fraction of allocated C that goes to growth respiration (typically 0.3, i.e. 30% of newly fixed biomass is respired during construction). `grpnow(ivt)` is the fraction of GR that happens at the time of allocation versus later when the transfer pool releases its contents.

For each flux, GR is apportioned across three paths: "now" from current allocation, "storage" from allocation into storage pools (to be respired later), and "transfer" from `xfer` pool release during phenology flush:

```
cpool_leaf_gr          = cpool_to_leafc * grperc(ivt)
cpool_leaf_storage_gr  = cpool_to_leafc_storage * grperc(ivt) * grpnow(ivt)
transfer_leaf_gr       = leafc_xfer_to_leafc  * grperc(ivt) * (1 - grpnow(ivt))
```

Same structure for fine root, live stem, dead stem, live coarse root, dead coarse root (woody only), and grain (crops only). Wood pools are only computed if `woody(ivt) == 1`. Crop pools require `ivt >= npcropmin` (skip the two generic crops). The sum of all GR terms is later aggregated into `gr_patch` and `current_gr_patch` in `veg_cf_Summary`.

## EcosystemBalanceCheckMod

`biogeochem/EcosystemBalanceCheckMod.F90` implements mass conservation checks at column and grid levels for C, N, and P. Tolerance `balance_check_tolerance = 1e-8_r8`. Public routines:

- `BeginColCBalance`, `BeginColNBalance`, `BeginColPBalance`: save `totcolc` / `totcoln` / `totcolp` into `col_cs%begcb` / `col_ns%begnb` / `col_ps%begpb` at start of time step.
- `ColCBalanceCheck`, `ColNBalanceCheck`, `ColPBalanceCheck`: at end of time step, compute `endcb - begcb - net_input_flux * dt` and abort if `|err| > tolerance`. The column-level CBalance equation includes GPP, HR (col), land use flux, fire loss, and crop / wood product losses.
- `BeginGridCBalance`, `GridCBalanceCheck`: grid-level equivalents, which account for the `dyn_cbal_adjustments_col` term from dynamic landcover weight changes.
- `EndGrid{C,N,P}BalanceAfterDynSubgridDriver`: a second grid check after the dynamic subgrid driver has finished shifting weights between columns/patches.

## CarbonStateUpdate Mod 1/2/3

ELM updates carbon (and N, and P) pools in three stages per radiation time step, matching the three-phase structure of allocation, gap mortality, and leaching.

### CarbonStateUpdate1 (`biogeochem/CarbonStateUpdate1Mod.F90:170`)

Called from `EcosystemDynNoLeaching2` after allocation. Updates all prognostic carbon state variables except for gap-phase mortality and fire. The smaller helper `CarbonStateUpdate0` (`:140`) updates only `cpool` by adding `psnsun_to_cpool * dt + psnshade_to_cpool * dt` (fresh photosynthate). `CarbonStateUpdate1` then steps:

- `cpool` <- minus MR, minus GR, minus allocation to each tissue (plus transfer in).
- `leafc` <- plus display allocation, plus xfer -> leafc flux, minus leaf litterfall.
- `leafc_storage` <- plus storage allocation, minus storage -> xfer (annual).
- `leafc_xfer` <- plus storage -> xfer, minus xfer -> leafc.
- Same three updates per tissue (froot, livestem, deadstem, livecroot, deadcroot, grain).
- `livestemc` <- plus allocation, minus livewood-to-deadwood turnover.
- `deadstemc` <- plus allocation, plus livewood-to-deadwood turnover.
- `xsmrpool` <- plus excess MR diversion.
- `ctrunc_patch` unchanged at this stage.
- Column `decomp_cpools_vr(c,j,l)` <- plus decomposition cascade transfers (litter input from phenology, SOM source-sink from `decomp_cpools_sourcesink_col`).

The semantic meaning of this stage is "post-photosynthesis and post-allocation, before gap mortality": all the non-mortality fluxes computed during the current time step (phenology, allocation, maintenance/growth respiration, decomposition) have been applied.

### CarbonStateUpdate2 / CarbonStateUpdate2h (`biogeochem/CarbonStateUpdate2Mod.F90`)

Called from `EcosystemDynNoLeaching2` after `GapMortality`. Updates pools for gap-phase mortality fluxes (`m_*_to_litter_patch`) and harvest mortality fluxes (`hrv_*_to_litter_patch`). `CarbonStateUpdate2h` is a second form that handles only the harvest update path when a separate hrv-only pass is needed (used in some crop/harvest configurations). The column-level decomposing pools also receive the gap-mortality litter inputs (`gap_mortality_c_to_litr_met_c_col`, `gap_mortality_c_to_cwdc_col`).

Semantic meaning: "post-gap-mortality and post-harvest".

### CarbonStateUpdate3 (`biogeochem/CarbonStateUpdate3Mod.F90:32`)

Called from `EcosystemDynLeaching` (for N/P) and from `EcosystemDynNoLeaching2` after fire for C. Applies fire loss fluxes (`m_*_to_fire_patch`, `m_decomp_cpools_to_fire_vr_col`), the `m_*_to_litter_fire_patch` uncombusted wood -> CWD transfers, and SOM erosion losses (if `ero_ccycle`). Semantic meaning: "post-fire, post-erosion, post-leaching".

The N and P equivalents have the same three-stage structure and the same semantics:

- Stage 1 = after photosynthesis / allocation / decomposition-cascade transfers.
- Stage 2 = after gap mortality / harvest.
- Stage 3 = after fire / erosion / leaching.

`biogeochem/NitrogenStateUpdate1Mod.F90`, `NitrogenStateUpdate2Mod.F90`, `NitrogenStateUpdate3Mod.F90` mirror this for N. `biogeochem/PhosphorusStateUpdate1Mod.F90`, `PhosphorusStateUpdate2Mod.F90`, `PhosphorusStateUpdate3Mod.F90` mirror it for P.

Additionally each stage has a `StateUpdateDynPatch` variant (e.g. `NitrogenStateUpdateDynPatch` in `NitrogenStateUpdate1Mod.F90:45`) that handles state changes driven by dynamic subgrid weight adjustments (seed transfers, land-use flux to product pools, fine root CWD reallocation). These are called once per time step outside the three main stages, from `dynSubgridControlMod`.

## BeTR Allocation Path

`biogeochem/CNAllocationBetrMod.F90` and `biogeochem/CNEcosystemDynBetrMod.F90` provide a parallel allocation/ecosystem-dynamics path for the BeTR (Benchmarking Ecosystem Tracer Responses) soil-column abstraction, which is used when ELM is coupled to PFLOTRAN for reactive transport.

### CNAllocationBetrMod

Mirrors `AllocationMod.F90` but fetches nutrient availability from the BeTR-side tracer state rather than from the default `col_ns%sminn_vr_col` / `col_ps%solutionp_vr_col` pools. Public entries:

- `CNAllocationBeTRInit` (initialization).
- `SetPlantMicNPDemand` (compute per-level plant N and P Vmax/Km parameters in `PlantMicKinetics_type`).
- `Allocation3_PlantCNPAlloc` (public) and private `Allocation1_PlantNPDemand`, `dynamic_plant_alloc`.

ECA scaling factors `E_plant_scalar = 1.25e-5`, `E_decomp_scalar = 0.05` at `CNAllocationBetrMod.F90:85`. Summary variables `e_km_nh4`, `e_km_no3`, `e_km_p`, `e_km_n` are temporary competition variables used inside the ECA resolver.

### CNEcosystemDynBetrMod

`CNEcosystemDynBeTR` is the BeTR driver, called instead of `EcosystemDynNoLeaching{1,2}` when `is_active_betr_bgc` is set. It orchestrates: `NitrogenDeposition`, `NitrogenFixation(_balance)`, `MaintenanceResp`, `SoilLittDecompAlloc`, `CNPhenology` (from `CNPhenologyBeTRMod`, a BeTR-flavored phenology), `GrowthResp`, `CarbonStateUpdate0/1`, `NStateUpdate1` (from `CNNStateUpdate1BeTRMod`), `CNGapMortality` (from `CNGapMortalityBeTRMod`), `CarbonStateUpdate2/2h`, `NStateUpdate2/2h`, `FireArea/FireFluxes`, `CarbonStateUpdate3`, `CarbonIsoFlux*`, `C14Decay`, `WoodProducts`, `decomp_rate_constants_bgc/_cn`, `CropHarvestPools`, `SetPlantMicNPDemand`, `Allocation3_PlantCNPAlloc`, `NStateUpdate3`, `NitrogenFixation_balance`, `PhosphorusStateUpdate{1,2,2h}`, `PhosphorusBiochemMin_balance`, `PhosphorusDeposition`, `PhosphorusWeathering`, `decomp_vertprofiles`, `RootDynamics`, and `CNFluxStateBetrSummary`.

The difference from the default path is that gap mortality, phenology, and state updates use the BeTR-flavored modules, and the plant-microbe kinetics (Vmax/Km) are set up through `SetPlantMicNPDemand` rather than being computed inside `Allocation1`. This lets the BeTR tracer-transport layer compute N and P uptake alongside the rest of the column BGC.

## CNBeTRIndicatorMod

`biogeochem/CNBeTRIndicatorMod.F90` defines per-flux indicator arrays `pheno_indicator(3)` and `gap_indicator(19)` used to selectively zero out certain phenology or gap-mortality fluxes when running under BeTR coupling. The routines `set_pheno_indicators` and `set_gap_indicators` currently set all indicators to 1 and then `return` immediately (so all fluxes are enabled); the dead code below the return is kept for future use, showing which fluxes could be disabled. Indexes defined:

- `pid_leafn_to_litter`, `pid_frootn_to_litter`, `pid_livestemn_to_litter` (phenology litterfall).
- `gid_m_leafn_to_litter`, ..., `gid_m_deadcrootn_xfer_to_litter` (19 gap mortality N fluxes for each tissue/storage/xfer combination).

This module is a stub that would allow a tracer-transport layer to take over specific fluxes without needing to modify the default CN code paths. Under current default settings, these indicators are all 1.0 and have no effect on the simulation.

## Summary Flow

The typical sequence within a single radiation time step for a non-FATES CNP run:

1. `EcosystemDynNoLeaching1`: zero fluxes, N/P deposition + fixation, MR, P weathering, P biochem min, decomposition rate constants, vertical profiles, supplement status, `Allocation1_PlantNPDemand`.
2. `SoilLittDecompAlloc` (called from `EcosystemDynNoLeaching2`): compute decomposition fluxes, call `Allocation2_ResolveNPLimit` to split N/P between plants and decomposers, write `fpi_vr_col`, `fpg_col`.
3. `SoilLittDecompAlloc2`: call `Allocation3_PlantCNPAlloc` to apply downregulation and produce the final `cpool_to_*`, `npool_to_*`, `ppool_to_*` fluxes; emit decomposition transfers along the cascade; vertically integrate mineralization fluxes.
4. `Phenology`, `CNLitterToColumn`, `GrowthResp`.
5. `CarbonStateUpdate0`, `CarbonStateUpdate1`, `NitrogenStateUpdate1`, `PhosphorusStateUpdate1` (stage 1).
6. `GapMortality`, `CarbonStateUpdate2`, `NitrogenStateUpdate2`, `PhosphorusStateUpdate2` (stage 2).
7. `FireArea`, `FireFluxes`, `ErosionFluxes`, `CarbonStateUpdate3` (for C only at this stage).
8. `CarbonIsoFlux*`, `C14Decay`, `C14BombSpike`.
9. `SoilLittVertTransp`, `WoodProducts`, `CropHarvestPools`, `RootDynamics`.
10. `EcosystemDynLeaching`: P inorganic cascade re-run, `NitrogenLeaching`, `PhosphorusLeaching`, `NitrogenStateUpdate3`, `PhosphorusStateUpdate3` (stage 3).
11. `PrecisionControl`, summary routines, balance check at end of time step.

When FATES is active, steps 4-9 are bypassed for vegetation (FATES runs its own cohort-level allocation, phenology, mortality, and growth). Steps involving soil BGC (decomposition, vertical transport, mineralization, leaching, deposition) still run, and FATES communicates plant C/N/P demand to ELM's soil BGC through `main/ELMFatesInterfaceMod.F90` so that the two-way coupling of nutrient limitation and vegetation dynamics is preserved.
