---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Biogeochemistry Subsystem Overview

The `components/elm/src/biogeochem/` directory (74 Fortran modules, plus `data_types/CNStateType.F90`) implements ELM's terrestrial biogeochemistry: living plant C/N/P pools, decomposition of litter and soil organic matter, atmospheric and soil mineral nutrient dynamics, autotrophic and heterotrophic respiration, phenology, gap and fire mortality, crop, wetland methane, and BVOC/dust emission. This page is the top-level navigation for the biogeochem docs; detailed explanations live in the sibling `biogeochem/*.md` files.

All code referenced here is committed at `60d9aad`. Paths below are relative to `components/elm/src/`.

## Top-level Organization

ELM biogeochemistry is built around three kinds of modules:

1. **State and flux derived types** that allocate and initialize the prognostic pool/flux arrays for each element. Carbon uses `biogeochem/CNCarbonStateType.F90` and `biogeochem/CNCarbonFluxType.F90`, nitrogen uses `biogeochem/CNNitrogenStateType.F90` and `biogeochem/CNNitrogenFluxType.F90`, phosphorus uses `biogeochem/PhosphorusStateType.F90` and `biogeochem/PhosphorusFluxType.F90`. Process modules read fluxes from, and write fluxes into, these types.
2. **Process modules** that compute fluxes (allocation, respiration, decomposition, mineralization, nitrification, denitrification, phosphatase, weathering, phenology, mortality, fire).
3. **State update modules** that step the pools forward in time in three staged sweeps per radiation time step (stage 1 after photosynthesis/allocation, stage 2 after gap mortality, stage 3 after leaching and fire).

The container type `cnstate_type` in `data_types/CNStateType.F90` is a per-column structure that carries diagnostic flags, crop indices, vertical profiles (`ndep_prof_col`, `pdep_prof_col`, `nfixation_prof_col`, `leaf_prof_patch`, `froot_prof_patch`, `stem_prof_patch`, `croot_prof_patch`), decomposition pool parameters (`rf_decomp_cascade_col`, `pathfrac_decomp_cascade_col`), and phenology state (`dormant_flag_patch`, `onset_flag_patch`, `days_active_patch`). See `biogeochem/cnp_state_and_fluxes.md` for full field inventories.

## CN vs CNP

ELM supports three nutrient coupling configurations controlled by `elm_varctl` flags:

| Flag | Meaning |
|---|---|
| `carbon_only`  | Carbon cycle only; N and P demand always satisfied, no downregulation |
| `carbonnitrogen_only` | CN mode; N limits GPP/growth, P always satisfied |
| `carbonphosphorus_only` | CP mode; P limits GPP/growth, N always satisfied |
| (default CNP) | Both N and P demand must be met; most restrictive limits growth |

Phosphorus is an ELM extension over the CESM/CLM ancestor: the `PhosphorusStateType` and `PhosphorusFluxType` modules, the inorganic cascade (`solutionp -> labilep -> secondp -> occlp`, plus `primp` weathering source) in `biogeochem/PhosphorusDynamicsMod.F90`, and the three staged updaters `biogeochem/PhosphorusStateUpdate1Mod.F90`, `biogeochem/PhosphorusStateUpdate2Mod.F90`, `biogeochem/PhosphorusStateUpdate3Mod.F90` are ELM-specific. The CNP code path is engaged when `use_cn = .true.` and the CP and CNP configurations are compiled in.

Details: `cnp_state_and_fluxes.md`, `phosphorus.md`.

## Decomposition Cascade and Vertical Soil BGC

Soil decomposition is structured as a cascade of donor/receiver transitions among pools (litter 1 metabolic, litter 2 cellulose, litter 3 lignin, CWD, SOM 1, SOM 2, SOM 3). The cascade definition sits in `biogeochem/CNDecompCascadeConType.F90` (`decomp_cascade_con`), and two alternative initializers populate the transitions: `biogeochem/DecompCascadeBGCMod.F90` (CENTURY/BGC parameterization, `use_century_decomp = .true.`, default) and `biogeochem/DecompCascadeCNMod.F90` (original CN parameterization).

Each transition has a respiration fraction `rf_decomp_cascade`, a path fraction `pathfrac_decomp_cascade`, and a rate constant `decomp_k`. At each time step, `biogeochem/SoilLittDecompMod.F90` (`SoilLittDecompAlloc`, `SoilLittDecompAlloc2`) computes potential C loss per transition, computes immobilization N/P demand, resolves competition between plants and decomposers via `AllocationMod`, and emits actual C/N/P transfers along the cascade. Vertical mixing is computed in `biogeochem/SoilLittVertTranspMod.F90` using a Patankar advection-diffusion tridiagonal solver on the `nlevdecomp` grid, parameterized by `som_diffus` and `cryoturb_diffusion_k` (the latter enables cryoturbation enhanced mixing in permafrost columns). Vertical profiles for incoming C/N/P come from `biogeochem/VerticalProfileMod.F90` (`decomp_vertprofiles`), which uses either PFT-specific Jackson beta root distributions or an exponential profile.

Details: `decomposition.md`.

## Allocation and Respiration

The non-FATES C/N/P allocation for vegetation is in `biogeochem/AllocationMod.F90`, split into three phases called at different points in the time step:

1. `Allocation1_PlantNPDemand` (called from `EcosystemDynNoLeaching1`) computes plant N and P demand from GPP and stoichiometry.
2. `Allocation2_ResolveNPLimit` (called from `SoilLittDecompAlloc`) resolves competition between plant and decomposer demand for soil mineral N/P given the decomposition-derived immobilization fluxes, and sets `fpg_col`, `fpg_p_col`, `fpi_col`, `fpi_p_col` (fractions of potential GPP and potential immobilization).
3. `Allocation3_PlantCNPAlloc` (called from `SoilLittDecompAlloc2`) applies the limitation-adjusted allocation to leaf, fine root, stem, coarse root, grain, and storage pools through the `cpool_to_*`, `npool_to_*`, `ppool_to_*` fluxes in `CNCarbonFluxType`, `CNNitrogenFluxType`, `PhosphorusFluxType`.

`biogeochem/GrowthRespMod.F90` assigns growth respiration based on each allocation flux times the PFT parameter `grperc` (split between now vs. storage via `grpnow`). `biogeochem/MaintenanceRespMod.F90` computes leaf, fine-root, live-stem, live-coarse-root, and grain MR using a base rate `br_mr` applied to N content of each pool with Q10 temperature response, plus an "excess respiration" term proportional to `cpool * br_xr(ivt)`.

`biogeochem/EcosystemDynMod.F90` is the main driver; `EcosystemDynNoLeaching1`, `EcosystemDynNoLeaching2`, and `EcosystemDynLeaching` structure the time-step sequence around soil BGC and leaching. `biogeochem/EcosystemBalanceCheckMod.F90` and `biogeochem/CNPBudgetMod.F90` perform mass-balance accounting at column and grid level. `biogeochem/AnnualUpdateMod.F90` rolls annual accumulators (`annsum_npp`, `annmax_retransn_patch`, `annavg_t2m_patch`). A parallel BeTR-flavored allocation path is in `biogeochem/CNAllocationBetrMod.F90` and its driver `biogeochem/CNEcosystemDynBetrMod.F90`.

Details: `allocation_and_respiration.md`.

## Nitrogen Dynamics

N inputs, internal fluxes, and losses are computed in several modules. `biogeochem/NitrogenDynamicsMod.F90` (`NitrogenDeposition`, `NitrogenFixation`, `NitrogenLeaching`, `NitrogenFert`, `CNSoyfix`, `NitrogenFixation_balance`) handles atmospheric deposition, symbiotic/asymbiotic fixation, leaching, and fertilizer application. `biogeochem/NitrifDenitrifMod.F90` computes nitrification and denitrification rates at each decomposition level using temperature, moisture, and anoxic-fraction parameterizations (Arah and Vinten 1995). Three staged update modules (`biogeochem/NitrogenStateUpdate1Mod.F90`, `NitrogenStateUpdate2Mod.F90`, `NitrogenStateUpdate3Mod.F90`) step `col_ns` and `veg_ns` pools. `biogeochem/PlantMicKineticsMod.F90` carries per-level Michaelis-Menten kinetic parameters (`plant_nh4_vmax_vr_patch`, `plant_no3_vmax_vr_patch`, `plant_p_vmax_vr_patch`, Km values) used by ECA nutrient competition.

When `use_fan = .true.`, the agricultural N model FAN is active, implemented in `biogeochem/FanMod.F90` (numerical core) and `biogeochem/FanUpdateMod.F90` (driver). FAN tracks manure and fertilizer N through age-structured TAN, NH3, and slurry pools and produces volatilization, surface runoff, and soil NH4 deposition fluxes.

Details: `nitrogen.md`.

## Phosphorus Dynamics

The inorganic P cascade is in `biogeochem/PhosphorusDynamicsMod.F90`: `PhosphorusWeathering` (primp -> labilep from soil order weathering rate), `PhosphorusAdsportion` (labilep -> secondp), `PhosphorusDesoprtion` (secondp -> labilep), `PhosphorusOcclusion` (secondp -> occlp), `PhosphorusBiochemMin`/`PhosphorusBiochemMin_balance` (biochemical mineralization / phosphatase), `PhosphorusLeaching`, `PhosphorusDeposition`, `PhosphorusFert`. Three staged updaters (`PhosphorusStateUpdate1Mod.F90`, `PhosphorusStateUpdate2Mod.F90`, `PhosphorusStateUpdate3Mod.F90`) mirror the N update stages.

Details: `phosphorus.md`.

## BeTR / PFLOTRAN Interface

ELM can route soil BGC through the external PFLOTRAN reactive-transport model or through the BeTR soil column abstraction. The master switches in `main/elm_varctl.F90` are `use_elm_interface`, `use_pflotran`, `pf_cmode`, `pf_hmode`. The connectors live in `main/elm_interface_bgcType.F90`, `main/elm_interface_funcsMod.F90`, and `main/elm_interface_pflotranMod.F90`. When `use_pflotran .and. pf_cmode` is true, the default ELM decomposition cascade is bypassed for soil organic C/N and the `decomp_cpools_sourcesink_col` / `bgc_cpool_ext_inputs_vr_col` channels feed PFLOTRAN. The three BeTR-flavored update modules `biogeochem/CNNStateUpdate1BeTRMod.F90`, `CNNStateUpdate2BeTRMod.F90`, `CNNStateUpdate3BeTRMod.F90` provide BeTR-specific state updates, and `biogeochem/CNGapMortalityBeTRMod.F90` handles gap mortality in BeTR mode. A small indicator module `biogeochem/CNBeTRIndicatorMod.F90` defines per-flux switches used to zero out fluxes that should be handled by the external tracer transport code. The BeTR allocation driver is `biogeochem/CNEcosystemDynBetrMod.F90` and its allocation backend is `biogeochem/CNAllocationBetrMod.F90`.

## Relationship to FATES

When `use_fates = .true.` is set in `main/elm_varctl.F90:222`, FATES replaces most of the ELM vegetation biogeochemistry. The ELM side handles soil water and temperature, atmospheric forcing, soil BGC (litter/SOM decomposition, N/P mineralization, nitrification/denitrification, phosphorus inorganic cascade, leaching, deposition), and passes these to FATES via `main/ELMFatesInterfaceMod.F90` (`alm_fates`).

Specifically, inside `EcosystemDynMod` the `EcosystemDynNoLeaching1` and `EcosystemDynNoLeaching2` drivers guard the default CN allocation and phenology calls with `if (.not. use_fates)`. In `AllocationMod.F90` the patch-level CN allocation is skipped when FATES is active. In `CNCarbonStateType%InitAllocate` the patch-level leaf/root/stem pools are only allocated when `.not. use_fates`. Summaries in `EcosystemDynLeaching` call `col_cs%ZeroForFates` / `col_ns%ZeroForFates` / `col_ps%ZeroForFates` so that the default vegetation pool summaries are zeroed out (FATES maintains its own cohort-level pools). FATES-handled gap mortality and phenology are managed inside the FATES library; ELM's `GapMortalityMod.F90` and `PhenologyMod.F90` are inactive. The FATES-side coarse woody debris pool is its own internal bookkeeping; already-fragmented litter is delivered to ELM's litter pools, so the ELM CWD pool (`i_cwd`) stays at zero under FATES (see comments in `DecompCascadeBGCMod.F90:464`).

The soil biogeochemistry (nitrification/denitrification, P cascade, decomposition, vertical mixing) runs the same way whether or not FATES is active, because FATES calls into ELM soil BGC for mineralization/immobilization and competes with decomposers for mineral N and P through the ECA/RD machinery in `AllocationMod.F90`.

## Navigation

| Document | Covers |
|---|---|
| `cnp_state_and_fluxes.md` | State/flux derived types: `carbonstate_type`, `carbonflux_type`, `nitrogenstate_type`, `nitrogenflux_type`, `phosphorusstate_type`, `phosphorusflux_type`, `cnstate_type`, `chemstate_type`; pool inventories and budget bookkeeping (`CNPBudgetMod.F90`, `EcosystemBalanceCheckMod.F90`) |
| `allocation_and_respiration.md` | `AllocationMod.F90`, `CNAllocationBetrMod.F90`, `CNEcosystemDynBetrMod.F90`, `AnnualUpdateMod.F90`, `GrowthRespMod.F90`, `MaintenanceRespMod.F90`, `EcosystemDynMod.F90`, `EcosystemBalanceCheckMod.F90`, `CNBeTRIndicatorMod.F90`, carbon state updaters |
| `decomposition.md` | `CNDecompCascadeConType.F90`, `DecompCascadeBGCMod.F90`, `DecompCascadeCNMod.F90`, `SoilLittDecompMod.F90`, `SoilLittVertTranspMod.F90`, `VerticalProfileMod.F90`, cascade topology, rate constants |
| `nitrogen.md` | `NitrogenDynamicsMod.F90`, `NitrifDenitrifMod.F90`, `NitrogenStateUpdate{1,2,3}Mod.F90`, `CNGapMortalityBeTRMod.F90`, `CNNStateUpdate{1,2,3}BeTRMod.F90`, `FanMod.F90`, `FanUpdateMod.F90`, `PlantMicKineticsMod.F90` |
| `phosphorus.md` | `PhosphorusDynamicsMod.F90`, `PhosphorusStateUpdate{1,2,3}Mod.F90`, inorganic P cascade, weathering, phosphatase |
| `phenology.md` (agent 8) | `PhenologyMod.F90`, `CNPhenologyBeTRMod.F90`, `PhenologyFluxLimitMod.F90`, `SatellitePhenologyMod.F90`, `VegStructUpdateMod.F90` |
| `mortality.md` (agent 8) | `GapMortalityMod.F90`, `CNGapMortalityBeTRMod.F90`, `WoodProductsMod.F90`, `RootDynamicsMod.F90` |
| `fire.md` (agent 8) | `FireMod.F90`, `FireDataBaseType.F90`, `FireMethodType.F90`, `FATESFireBase.F90`, `FATESFireDataMod.F90`, `FATESFireFactoryMod.F90`, `FATESFireNoDataMod.F90` |
| `methane.md` (agent 8) | `CH4Mod.F90`, `CH4varcon.F90` |
| `crops.md` (agent 8) | `CropMod.F90`, `CropType.F90`, `CropHarvestPoolsMod.F90` |
| `emissions.md` (agent 8) | `VOCEmissionMod.F90`, `MEGANFactorsMod.F90`, `DUSTMod.F90`, `DryDepVelocity.F90`, `ErosionMod.F90` |

## Supporting Utilities

- `biogeochem/PrecisionControlMod.F90`: catches small negative pool values and moves them into a per-pool truncation sink (`ctrunc_patch`, `ntrunc_patch`, `ptrunc_patch`), preserving mass balance while protecting downstream code from numerical underflow.
- `biogeochem/SharedParamsMod.F90`: shared parameter instance `ParamsShareInst` carrying `Q10_mr`, `Q10_hr`, `minpsi`, `cwd_fcel`, `cwd_flig`, `froz_q10`, `decomp_depth_efolding`, `mino2lim`, `organic_max`.
- `biogeochem/SpeciesMod.F90`: integer IDs for carbon isotopes (`CN_SPECIES_C12=1`, `CN_SPECIES_C13=2`, `CN_SPECIES_C14=3`) and N/P species (`CN_SPECIES_N=4`, `CN_SPECIES_P=5`), plus `species_from_string`.
- `biogeochem/LSparseMatMod.F90`: sparse matrix utilities used by the vertical transport solver.
- `biogeochem/ComputeSeedMod.F90`: computes initial seed C/N/P for newly opened patches during dynamic land cover change.
- `biogeochem/CarbonIsoFluxMod.F90`: routes C13 and C14 fluxes alongside bulk C.
- `biogeochem/C14DecayMod.F90`: C14 radioactive decay and bomb-spike atmospheric history.

## Driver Ordering (non-FATES CNP)

Inside `EcosystemDynNoLeaching1` (called once per radiation time step, before soil BGC):

1. Zero patch and column flux accumulators (`col_cf_SetValues`, `veg_cf_SetValues`, etc.).
2. `NitrogenDeposition` (+ `FanMod%fan_eval` if `use_fan`), `NitrogenFixation` or `NitrogenFixation_balance`, `PhosphorusDeposition`.
3. `MaintenanceResp` (leaf, froot, livestem, livecroot, grain; temperature-scaled).
4. `PhosphorusWeathering`, `PhosphorusBiochemMin` (or `_balance` if phosphatase enabled).
5. `decomp_rate_constants_bgc` or `_cn` (compute `decomp_k`, `t_scalar`, `w_scalar`, `o_scalar`).
6. `decomp_vertprofiles` (update `froot_prof`, `leaf_prof`, `ndep_prof`, `nfixation_prof`, `pdep_prof`).
7. `EvaluateSupplStatus` (check whether supplemental N/P is still active in the spinup stage).
8. `Allocation1_PlantNPDemand` (compute plant N and P demand from target stoichiometry).

Inside `EcosystemDynNoLeaching2`:

9. `SoilLittDecompAlloc` (decomposition + `Allocation2_ResolveNPLimit`).
10. `SoilLittDecompAlloc2` (`Allocation3_PlantCNPAlloc`, update decomposition fluxes in pools).
11. `Phenology`, `CNLitterToColumn` (convert patch-level litterfall to column litter pools).
12. `GrowthResp` (multiply each allocation flux by `grperc(ivt)`).
13. `CarbonStateUpdate0` + `CarbonStateUpdate1` + `NitrogenStateUpdate1` + `PhosphorusStateUpdate1` (stage 1: post-allocation, post-decomposition).
14. `GapMortality`, then `CarbonStateUpdate2` / `NitrogenStateUpdate2` / `PhosphorusStateUpdate2` (stage 2: post-gap-mortality).
15. `FireArea`, `FireFluxes`, `ErosionFluxes`.
16. `CarbonIsoFlux*`, `C14Decay`, `C14BombSpike`.
17. `SoilLittVertTransp` (vertical mixing of decomposing pools).
18. `WoodProducts`, `CropHarvestPools`.
19. `RootDynamics` (dynamic rooting updates if `use_dynroot`).

Inside `EcosystemDynLeaching`:

20. `PhosphorusWeathering`, `Adsportion`, `Desoprtion`, `Occlusion`, `PhosphorusBiochemMin` (re-run for leaching-step bookkeeping).
21. `NitrogenLeaching`, `PhosphorusLeaching` (unless `pf_cmode .and. pf_hmode`).
22. `NitrogenStateUpdate3`, `PhosphorusStateUpdate3` (stage 3: post-leaching, post-fire, post-erosion).
23. `PrecisionControl` (move near-zero negatives to truncation sinks).
24. Summary calls: `col_cf_Summary`, `col_nf_Summary`, `col_pf_Summary`, `col_cs_Summary`, `col_ns_Summary`, `col_ps_Summary`, `veg_*_Summary`.

See `allocation_and_respiration.md` and `decomposition.md` for the subroutine-level details of each step.
