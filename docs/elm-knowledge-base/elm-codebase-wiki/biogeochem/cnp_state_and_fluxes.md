---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# CNP State and Flux Types

ELM's biogeochemistry stores pools and fluxes for carbon, nitrogen, and phosphorus (plus the `C12`, `C13`, `C14` isotopes for carbon) in six derived types defined in `biogeochem/`. A separate container type (`cnstate_type`) in `data_types/CNStateType.F90` carries diagnostic flags, crop state, phenology state, and other per-column / per-patch scalars that do not fit the pure state/flux split. Patch-level instances are `veg_cs`, `veg_ns`, `veg_ps` (states) and `veg_cf`, `veg_nf`, `veg_pf` (fluxes); column-level instances are `col_cs`, `col_ns`, `col_ps`, `col_cf`, `col_nf`, `col_pf`, declared in `data_types/VegetationDataType.F90` and `data_types/ColumnDataType.F90`. Gridcell aggregates follow the same naming (`grc_cs`, `grc_cf`, etc).

The key flag controlling which pools are allocated is `use_fates` in `main/elm_varctl.F90:222`. When FATES is active, patch-level living plant pools are not allocated by ELM because FATES maintains its own cohort-level C/N/P state; only soil-column pools and a few summary variables remain alive.

## carbonstate_type

Defined in `biogeochem/CNCarbonStateType.F90:37`. Single `species` integer field (1=C12, 2=C13, 3=C14) and a large set of pointers.

### Living Vegetation Pools (patch, gC/m2)

Three-state structure per tissue: display pool (active biomass), storage pool (reserve), and transfer pool (onset flush buffer). Allocated only when `.not. use_fates` (`CNCarbonStateType.F90:195`).

| Field group | Pools |
|---|---|
| Leaf | `leafc_patch`, `leafc_storage_patch`, `leafc_xfer_patch`, `leafcmax_patch` (`:68`) |
| Fine root | `frootc_patch`, `frootc_storage_patch`, `frootc_xfer_patch` |
| Live stem | `livestemc_patch`, `livestemc_storage_patch`, `livestemc_xfer_patch` |
| Dead stem | `deadstemc_patch`, `deadstemc_storage_patch`, `deadstemc_xfer_patch` |
| Live coarse root | `livecrootc_patch`, `livecrootc_storage_patch`, `livecrootc_xfer_patch` |
| Dead coarse root | `deadcrootc_patch`, `deadcrootc_storage_patch`, `deadcrootc_xfer_patch` |
| Grain (crop) | `grainc_patch`, `grainc_storage_patch`, `grainc_xfer_patch` |
| Growth resp storage | `gresp_storage_patch`, `gresp_xfer_patch` |
| Photosynthate | `cpool_patch` (temporary photosynthate buffer), `xsmrpool_patch` (excess MR buffer), `ctrunc_patch` (truncation sink) |
| Diagnostic | `woodc_patch`, `dispvegc_patch`, `storvegc_patch`, `totvegc_patch`, `totpftc_patch`, `totvegc_abg_patch` |

Column-aggregated counterparts: `leafc_col`, `deadstemc_col`, `frootc_col`, `rootc_col`, `totvegc_col`, `totvegcc_col`, `totpftc_col`, `totvegc_abg_col`, `fuelc_col`, `fuelc_crop_col`.

### Soil Decomposing Pools (column, gC/m3 vertically resolved)

`decomp_cpools_vr_col(begc:endc, 1:nlevdecomp_full, 1:ndecomp_pools)` holds the vertically resolved litter/CWD/SOM pools defined by the decomposition cascade (`CNCarbonStateType.F90:77`). The cascade has 7 pools in the BGC/CENTURY configuration: `i_met_lit`, `i_cel_lit`, `i_lig_lit`, `i_cwd`, `i_soil1`, `i_soil2`, `i_soil3` (indices set in `DecompCascadeBGCMod.F90:413-539`). `ctrunc_vr_col` is the per-level C truncation sink.

Column summary variables (not in mass balance): `decomp_cpools_col`, `decomp_cpools_1m_col`, `cwdc_col`, `ctrunc_col`, `totlitc_col`, `totsomc_col`, `totlitc_1m_col`, `totsomc_1m_col`, `totecosysc_col`, `totcolc_col`, `totabgc_col`, `totblgc_col`.

### Product and Seed Pools

`cropseedc_deficit_patch` (crop seed deficit, negative), `seedc_grc` (gridcell seed pool for new PFTs via dynamic landcover), `seedc_col`, `prod1c_col` (1-year crop product), `prod10c_col` (10-year wood product), `prod100c_col` (100-year wood product), `totprodc_col`, `dyn_cbal_adjustments_col`.

### Balance Check Book-keeping

`begcb_patch`, `begcb_col`, `begcb_grc` (pool totals at begin of time step); `endcb_patch`, `endcb_col`, `endcb_grc` (at end); `errcb_patch`, `errcb_col`, `errcb_grc` (difference). Also `totpftc_beg_col`, `cwdc_beg_col`, `totlitc_beg_col`, `totsomc_beg_col`, and their `end` counterparts plus `decomp_som2c_vr_col` for per-level monitoring. Used by `EcosystemBalanceCheckMod.F90` (`BeginColCBalance`, `ColCBalanceCheck`, `BeginGridCBalance`, `GridCBalanceCheck`).

### Procedures

`Init`, `SetValues`, `ZeroDWT`, `Restart`, `Summary`, and private `InitAllocate`, `InitHistory`, `InitCold`. The isotope-aware `Init` signature takes a `carbon_type` string (`'c12'`, `'c13'`, `'c14'`) and an initial ratio, and optionally a bulk c12 state to copy from (for C13 and C14 initialization).

## carbonflux_type

Defined in `biogeochem/CNCarbonFluxType.F90:36`. Contains over 200 pointers covering every C flux in ELM; they group into:

### Mortality Fluxes (patch, gC/m2/s)

Gap mortality `m_*_to_litter_patch` for each tissue and storage/xfer (`:39-59`); harvest mortality `hrv_*_to_litter_patch`, `hrv_deadstemc_to_prod10c_patch`, `hrv_deadstemc_to_prod100c_patch`, `hrv_xsmrpool_to_atm_patch`, `hrv_cpool_to_litter_patch`; crop harvest `hrv_leafc_to_prod1c_patch`, `hrv_livestemc_to_prod1c_patch`, `hrv_grainc_to_prod1c_patch`, `hrv_cropc_to_prod1c_patch`. Fire emissions `m_*_to_fire_patch` for each tissue and `m_*_to_litter_fire_patch` (wood uncombusted fraction going to CWD/litter; `:92-136`).

### Phenology Fluxes (patch)

`grainc_xfer_to_grainc_patch`, `leafc_xfer_to_leafc_patch`, `frootc_xfer_to_frootc_patch`, `livestemc_xfer_to_livestemc_patch`, etc. (transfer pool -> display pool during onset). `leafc_to_litter_patch`, `frootc_to_litter_patch`, `livestemc_to_litter_patch`, `grainc_to_food_patch` (offset litterfall fluxes). `leafc_storage_to_xfer_patch`, etc. (annual storage -> xfer shift at dormancy end).

### Respiration Fluxes (patch, gC/m2/s)

Maintenance: `leaf_mr_patch`, `froot_mr_patch`, `livestem_mr_patch`, `livecroot_mr_patch`, `grain_mr_patch`. Decomposed into "current GPP" (`*_curmr_patch`) and "from storage" (`*_xsmr_patch`). Excess C turnover: `xr_patch`.

Growth resp: `cpool_leaf_gr_patch`, `cpool_leaf_storage_gr_patch`, `transfer_leaf_gr_patch` (and same for froot, livestem, deadstem, livecroot, deadcroot, grain). Diagnostic: `mr_patch`, `gr_patch`, `current_gr_patch`, `transfer_gr_patch`, `storage_gr_patch`, `ar_patch` (autotrophic = MR+GR), `rr_patch` (root resp). Photosynthesis: `psnsun_to_cpool_patch`, `psnshade_to_cpool_patch`.

### Allocation Fluxes (patch, gC/m2/s)

`cpool_to_leafc_patch`, `cpool_to_leafc_storage_patch` (display vs storage allocation) for each of leaf, froot, livestem, deadstem, livecroot, deadcroot, grain, `cpool_to_gresp_storage_patch`, `cpool_to_xsmrpool_patch`. `plant_calloc_patch` (total allocated), `excess_cflux_patch` (downregulation loss), `availc_patch` (C available for allocation), `xsmrpool_recover_patch` (C redirected to recover negative cpool), `xsmrpool_turnover_patch`.

### Summary Diagnostic Fluxes

`gpp_patch`, `gpp_before_downreg_patch`, `npp_patch`, `agnpp_patch`, `bgnpp_patch`, `litfall_patch`, `wood_harvestc_patch`, `cinputs_patch`, `coutputs_patch`, `fire_closs_patch`, `annavg_agnpp_patch`, `annavg_bgnpp_patch`, `tempavg_agnpp_patch`, `tempavg_bgnpp_patch`, `agwdnpp_patch`, `frootc_alloc_patch`, `leafc_alloc_patch`, `woodc_alloc_patch`, `frootc_loss_patch`, `leafc_loss_patch`, `woodc_loss_patch`.

### Column-level Decomposition Fluxes (gC/m3/s vertically resolved)

`decomp_cascade_hr_vr_col(begc:endc, 1:nlevdecomp, 1:ndecomp_cascade_transitions)` (het. resp. per transition), `decomp_cascade_ctransfer_vr_col` (C transferred along cascade), `decomp_k_col` (rate constants, 1/s), `hr_vr_col`, `t_scalar_col`, `w_scalar_col`, `o_scalar_col`, `phr_vr_col` (potential HR not N-limited), `fphr_col` (fraction of potential HR), `decomp_cpools_sourcesink_col` (change in decomposing pools used to update concentrations concurrently with vertical transport), `m_decomp_cpools_to_fire_vr_col`, `m_c_to_litr_met_fire_col`, `m_c_to_litr_cel_fire_col`, `m_c_to_litr_lig_fire_col`, `somc_fire_col` (peat burn), `decomp_cpools_leached_col`, `decomp_cpools_transport_tendency_col`, `som_c_leached_col`.

### Column-level Aggregated Fluxes

`hr_col`, `lithr_col` (litter HR), `somhr_col` (SOM HR), `sr_col` (soil resp = HR + root resp), `er_col` (ecosystem resp), `ar_col`, `rr_col`, `npp_col`, `gpp_col`, `nep_col`, `nbp_col`, `nee_col` (fluxes aggregated to column, `_p2c` suffix variants exist for patch->column averaged), `fire_closs_col`, `fire_decomp_closs_col`, `cwdc_hr_col`, `cwdc_loss_col`, `litterc_loss_col`.

### Dynamic Land Use Fluxes

`dwt_seedc_to_leaf_patch`, `dwt_seedc_to_deadstem_patch`, `dwt_conv_cflux_patch`, `dwt_prod10c_gain_patch`, `dwt_prod100c_gain_patch`, `dwt_crop_productc_gain_patch`, `dwt_slash_cflux_col`, `dwt_frootc_to_litr_met_c_col`, `dwt_livecrootc_to_cwdc_col`, `dwt_closs_col`, `landuseflux_col`, `landuptake_col`. Grid-level totals `dwt_*_grc`.

### Product Pool Losses

`prod1c_loss_col`, `prod10c_loss_col`, `prod100c_loss_col`, `product_closs_col`, `hrv_xsmrpool_to_atm_col`.

### PFLOTRAN / Annual Dribbler Interface

`externalc_to_decomp_cpools_col` (net external C input/removal to decomposing pools), `externalc_to_decomp_delta_col`, `f_co2_soil_vr_col`, `f_co2_soil_col`. `dwt_conv_cflux_dribbler` and `hrv_xsmrpool_to_atm_dribbler` are `annual_flux_dribbler_type` instances that spread once-per-year land-use fluxes evenly throughout the year.

Procedures: `Init`, `SetValues`, `ZeroDWT`, `Restart`, `Summary`, `summary_cflux_for_ch4`, `summary_rr`.

## nitrogenstate_type

Defined in `biogeochem/CNNitrogenStateType.F90:35`. Module-level parameter `npool_seed_param = 0.1_r8` (seed N for new crop growth).

### Vegetation N Pools (patch, gN/m2)

Same tissue structure as carbon: `leafn_patch`, `leafn_storage_patch`, `leafn_xfer_patch`, plus `frootn_*`, `livestemn_*`, `deadstemn_*`, `livecrootn_*`, `deadcrootn_*`, `grainn_*`. Plant-level N reserves: `retransn_patch` (retranslocated N during senescence), `npool_patch` (temporary plant N pool, analogous to `cpool`), `ntrunc_patch` (N truncation sink), `plant_n_buffer_patch` (abstract N storage buffer), `plant_n_buffer_col`.

### Soil Mineral N (column, gN/m3 and gN/m2)

`sminn_vr_col` (total soil mineral N, vertically resolved), `sminn_col` (depth integrated). With the default nitrification/denitrification turned on, `sminn_vr_col = smin_no3_vr_col + smin_nh4_vr_col` (nitrogen state update 3 recomputes this at `:65`). Separate vertical and column pools: `smin_no3_vr_col`, `smin_no3_col`, `smin_nh4_vr_col`, `smin_nh4_col`. Under PFLOTRAN coupling, an extra sorbed NH4 pool `smin_nh4sorb_vr_col`, `smin_nh4sorb_col` contributes to `sminn_vr`.

### Decomposing N Pools

`decomp_npools_vr_col(begc:endc, 1:nlevdecomp_full, 1:ndecomp_pools)`, `ntrunc_vr_col`. Diagnostic `decomp_npools_col`, `decomp_npools_1m_col`, `cwdn_col`, `ntrunc_col`, `totlitn_col`, `totsomn_col`, `totlitn_1m_col`, `totsomn_1m_col`, `totecosysn_col`, `totcoln_col`, `totabgn_col`, `totblgn_col`, `totvegn_col`, `totpftn_col`.

### Seed and Product Pools

`cropseedn_deficit_patch`, `seedn_grc`, `seedn_col`, `prod1n_col`, `prod10n_col`, `prod100n_col`, `totprodn_col`, `dyn_nbal_adjustments_col`.

### Cost-Benefit and Physiological Sensitivities

Used by the NFIX_PTASE dynamic allocation scheme and the FUN-style cost/benefit analysis (`:145-192`): `npimbalance_patch`, `pnup_pfrootc_patch`, `ppup_pfrootc_patch`, `ptlai_pleafc_patch`, `ppsnsun_ptlai_patch`, `ppsnsun_pleafn_patch`, `ppsnsun_pleafp_patch`, `plmrsun_ptlai_patch`, `plmrsun_pleafn_patch`, `benefit_pgpp_pleafc_patch`, `benefit_pgpp_pleafn_patch`, `benefit_pgpp_pleafp_patch`, `cost_pgpp_pfrootc_patch`, `cost_plmr_pleafc_patch`, `cost_plmr_pleafn_patch`, plus their per-layer counterparts (`_z` and per-Vcmax/Jmax/TPU component). These partial derivatives feed the `dynamic_plant_alloc` routine in `AllocationMod.F90`.

### FAN Pools (gN/m2)

Ammoniacal nitrogen age-structured pools for the FAN agricultural model (`:194-200`): `tan_g1_col`, `tan_g2_col`, `tan_g3_col` (grazing), `tan_s0_col`, `tan_s1_col`, `tan_s2_col`, `tan_s3_col` (slurry). Only active when `use_fan = .true.`.

### Balance Check

`begnb_patch`, `endnb_patch`, `errnb_patch`, and the col / grid counterparts. Plus `_beg_col` / `_end_col` arrays for every major reservoir (`totpftn_beg_col`, `cwdn_beg_col`, `totlitn_beg_col`, `totsomn_beg_col`, `sminn_beg_col`, `smin_no3_beg_col`, `smin_nh4_beg_col`, `totprodn_beg_col`, `seedn_beg_col`, `ntrunc_beg_col`).

## nitrogenflux_type

Defined in `biogeochem/CNNitrogenFluxType.F90:24`.

### Mortality and Harvest

Complete mirrors of carbon flux mortality (gap, harvest, fire), plus `hrv_retransn_to_litter_patch`, `m_retransn_to_litter_patch`, `m_npool_to_litter_patch`. `m_npool_to_fire_patch`, `m_retransn_to_fire_patch`. Column-level `fire_mortality_n_to_cwdn_col`, `harvest_n_to_*_col`.

### Phenology Fluxes

`leafn_xfer_to_leafn_patch`, `frootn_xfer_to_frootn_patch`, `livestemn_xfer_to_livestemn_patch`, etc.; `leafn_to_litter_patch`, `frootn_to_litter_patch`, `livestemn_to_litter_patch`; `leafn_to_retransn_patch`, `frootn_to_retransn_patch`, `livestemn_to_retransn_patch`, `livecrootn_to_retransn_patch` (N retranslocated out of senescing tissue).

### Allocation Fluxes

`sminn_to_npool_patch` (soil mineral N uptake to plant pool), `retransn_to_npool_patch` (retranslocated N deployed), `npool_to_leafn_patch`, `npool_to_leafn_storage_patch`, and same for froot, livestem, deadstem, livecroot, deadcroot, grain. `wood_harvestn_patch`. Diagnostic `ndeploy_patch`, `ninputs_patch`, `noutputs_patch`.

### External Inputs

`ndep_to_sminn_col` (atm N deposition), `nfix_to_sminn_col` (symbiotic + asymbiotic fixation), `nfix_to_plantn_patch` (NFIX_PTASE plant-direct fixation), `nfix_to_ecosysn_col`, `fert_to_sminn_col`, `soyfixn_to_sminn_col`, `synthfert_patch`, `manure_patch`, `fert_counter_patch`, `soyfixn_patch`.

### Decomposition / Immobilization Fluxes

`decomp_cascade_ntransfer_vr_col`, `decomp_cascade_sminn_flux_vr_col` (mineral N flux for the transition), `potential_immob_vr_col`, `actual_immob_vr_col`, `sminn_to_plant_vr_col` (plant uptake per level), `supplement_to_sminn_vr_col` (when plant N supplementation is active, e.g. spinup), `gross_nmin_vr_col`, `net_nmin_vr_col`, plus vertically integrated `_col` counterparts. `sminn_no3_input_vr_col`, `sminn_nh4_input_vr_col`, `bgc_npool_ext_inputs_vr_col`, `bgc_npool_ext_loss_vr_col`, `bgc_npool_inputs_col`.

### Nitrification / Denitrification

`f_nit_vr_col`, `f_nit_col`, `f_denit_vr_col`, `f_denit_col`, `pot_f_nit_vr_col`, `pot_f_denit_vr_col`, `pot_f_nit_col`, `pot_f_denit_col`, `n2_n2o_ratio_denit_vr_col`, `f_n2o_denit_vr_col`, `f_n2o_denit_col`, `f_n2o_nit_vr_col`, `f_n2o_nit_col`. Nitrification kinetic diagnostics: `k_nitr_t_vr_col`, `k_nitr_ph_vr_col`, `k_nitr_h2o_vr_col`, `k_nitr_vr_col`, `wfps_vr_col`, `fmax_denit_carbonsubstrate_vr_col`, `fmax_denit_nitrate_vr_col`, `f_denit_base_vr_col`, `diffus_col`, `anaerobic_frac_col`.

### Immobilization / Uptake (by N form)

`actual_immob_no3_vr_col`, `actual_immob_nh4_vr_col`, `smin_no3_to_plant_vr_col`, `smin_nh4_to_plant_vr_col`, plus col totals.

### Leaching Fluxes

`smin_no3_leached_vr_col`, `smin_no3_leached_col`, `smin_no3_runoff_vr_col`, `smin_no3_runoff_col`, `sminn_leached_vr_col`, `sminn_leached_col` (non-nitrif_denitrif path).

### Legacy CN (non-nitrif_denitrif) Denitrification

`sminn_to_denit_decomp_cascade_vr_col`, `sminn_to_denit_decomp_cascade_col`, `sminn_to_denit_excess_vr_col`, `sminn_to_denit_excess_col`.

### Dynamic Land Use

`dwt_seedn_to_leaf_patch`, `dwt_seedn_to_deadstem_patch`, `dwt_conv_nflux_patch`, `dwt_prod10n_gain_patch`, `dwt_prod100n_gain_patch`, `dwt_crop_productn_gain_patch`, `dwt_slash_nflux_col`, `dwt_frootn_to_litr_met_n_col`, `dwt_livecrootn_to_cwdn_col`, etc., plus grid totals.

### Turnover of Livewood to Deadwood

`livestemn_to_deadstemn_patch`, `livecrootn_to_deadcrootn_patch`, `livestemn_storage_to_xfer_patch`, etc.

## phosphorusstate_type

Defined in `biogeochem/PhosphorusStateType.F90:37`. Module-level parameter `ppool_seed_param = 0.01_r8`.

### Vegetation P Pools (patch, gP/m2)

Same tissue structure as N: `leafp_patch`, `leafp_storage_patch`, `leafp_xfer_patch`, and for `frootp`, `livestemp`, `deadstemp`, `livecrootp`, `deadcrootp`, `grainp`. Plant P reserves: `retransp_patch`, `ppool_patch`, `ptrunc_patch`, `plant_p_buffer_patch`.

### Soil Inorganic P Cascade (column)

Four mineral reservoirs arranged in a cascade (`:64-71`), each vertically resolved on `nlevdecomp_full`:

| Pool | Vertical field | Col total | Meaning |
|---|---|---|---|
| solution P | `solutionp_vr_col` | `solutionp_col` | Bio-available P in soil solution |
| labile P | `labilep_vr_col` | `labilep_col` | Exchangeable adsorbed P (in equilibrium with solution) |
| secondary mineral P | `secondp_vr_col` | `secondp_col` | Slow-exchange adsorbed/precipitated P |
| occluded P | `occlp_vr_col` | `occlp_col` | Chemically occluded P, essentially not available |
| primary mineral P | `primp_vr_col` | - | Parent-material P (apatite, feldspar), source via weathering |

`sminp_vr_col` and `sminp_col` are the total soil mineral P pool summary. `ptrunc_vr_col`, `ptrunc_col` are the P truncation sinks. Decomposing pools: `decomp_ppools_vr_col`, `decomp_ppools_col`, `decomp_ppools_1m_col`. Diagnostics: `cwdp_col`, `totlitp_col`, `totsomp_col`, `totlitp_1m_col`, `totsomp_1m_col`, `totecosysp_col`, `totcolp_col`, `totvegp_col`, `totpftp_col`.

### Tracking Current vs Previous Time Step

For solving stoichiometric balances over a time step, ELM stores `_cur` and `_prev` copies: `solutionp_vr_col_cur`, `solutionp_vr_col_prev`, `labilep_vr_col_cur`, `labilep_vr_col_prev`, `secondp_vr_col_cur`, `secondp_vr_col_prev`, `occlp_vr_col_cur`, `occlp_vr_col_prev`, `primp_vr_col_cur`, `primp_vr_col_prev`.

### Seed and Product Pools

`cropseedp_deficit_patch`, `seedp_grc`, `seedp_col`, `prod1p_col`, `prod10p_col`, `prod100p_col`, `totprodp_col`, `dyn_pbal_adjustments_col`.

### Balance Check

`begpb_patch`, `endpb_patch`, `errpb_patch` plus col and grid. `totpftp_beg_col`, `solutionp_beg_col`, `labilep_beg_col`, `secondp_beg_col`, `totlitp_beg_col`, `cwdp_beg_col`, `totsomp_beg_col`, and `_end_col` counterparts.

`Init` signature takes initial leaf, froot, deadstem C and the C decomposing pools to seed initial P pools from C:P ratios (`PhosphorusStateType.F90:165`).

## phosphorusflux_type

Defined in `biogeochem/PhosphorusFluxType.F90:24`. Structure mirrors `nitrogenflux_type` but with additional inorganic cascade fluxes.

### Vegetation / Mortality / Phenology / Allocation

All parallel to nitrogen: `m_leafp_to_litter_patch`, `hrv_*`, `leafp_xfer_to_leafp_patch`, `ppool_to_leafp_patch`, `ppool_to_leafp_storage_patch`, etc. `sminp_to_ppool_patch`, `retransp_to_ppool_patch`. Fire: `m_leafp_to_fire_patch`, `m_decomp_ppools_to_fire_vr_col`. Dynamic landuse `dwt_*_p*` fields.

### Decomposition / Immobilization

`decomp_cascade_ptransfer_vr_col`, `decomp_cascade_sminp_flux_vr_col`, `potential_immob_p_vr_col`, `actual_immob_p_vr_col`, `sminp_to_plant_vr_col`, `supplement_to_sminp_vr_col`, `gross_pmin_vr_col`, `net_pmin_vr_col`, col totals. `soil_p_immob_flux`, `soil_p_immob_flux_vr`, `soil_p_grossmin_flux`, `pmpf_decomp_cascade`.

### Inorganic Mineral Cycle (column, gP/m3/s vertically resolved)

- `pdep_to_sminp` (atm P deposition, col)
- `primp_to_labilep_vr`, `primp_to_labilep` (weathering, from `PhosphorusWeathering`)
- `labilep_to_secondp_vr`, `labilep_to_secondp` (adsorption, from `PhosphorusAdsportion`)
- `secondp_to_labilep_vr`, `secondp_to_labilep` (desorption, from `PhosphorusDesoprtion`)
- `secondp_to_occlp_vr`, `secondp_to_occlp` (occlusion, from `PhosphorusOcclusion`)
- `biochem_pmin_vr`, `biochem_pmin` (biochemical mineralization / phosphatase, from `PhosphorusBiochemMin` or `_balance`)
- `pf_flx_input_vr_col` (external P input), `sminp_leached_vr_col`, `sminp_leached_col`
- `fert_p_to_sminp_col`, `fire_ploss_col`, `fire_decomp_ploss_col`

## cnstate_type

Defined in `data_types/CNStateType.F90:37`. Per-column and per-patch container for diagnostic flags and auxiliary state that is shared across process modules.

### Crop State

`burndate_patch`, `lfpftd_patch`, `hdidx_patch`, `cumvd_patch`, `gddmaturity_patch`, `huileaf_patch`, `huigrain_patch`, `aleafi_patch`, `astemi_patch`, `aleaf_patch`, `astem_patch`, `htmx_patch`, `peaklai_patch`, `idop_patch`, `isoilorder`.

### Vertical Profiles (1/m)

`leaf_prof_patch`, `froot_prof_patch`, `croot_prof_patch`, `stem_prof_patch` (patch-level fractional profiles, `nlevdecomp_full`). `nfixation_prof_col`, `ndep_prof_col`, `pdep_prof_col` (column-level profiles). `som_adv_coef_col`, `som_diffus_coef_col`. Computed in `biogeochem/VerticalProfileMod.F90`.

### Fire-related

`gdp_lf_col`, `peatf_lf_col`, `abm_lf_col`, `lgdp_col`, `lgdp1_col`, `lpop_col`, `nfire_col`, `fsr_col`, `fd_col`, `lfc_col`, `lfc2_col`, `dtrotr_col`, `trotr1_col`, `trotr2_col`, `cropf_col`, `baf_crop_col`, `baf_peatf_col`, `fbac_col`, `fbac1_col`, `wtlf_col`, `lfwt_col`, `farea_burned_col`.

### N/P Limitation State

`fpi_vr_col`, `fpi_col` (fraction of potential immobilization for N), `fpg_col` (fraction of potential GPP), `fpi_p_vr_col`, `fpi_p_col`, `fpg_p_col`, `fpg_nh4_vr_col`, `fpg_no3_vr_col`, `frootc_nfix_scalar_col`, `decomp_litpool_rcn_col`.

### Decomposition Cascade Coefficients (per-column)

`rf_decomp_cascade_col(begc:endc, 1:nlevdecomp, 1:ndecomp_cascade_transitions)`, `pathfrac_decomp_cascade_col`.

### Annual / Temporary Accumulators

`tempavg_t2m_patch`, `annavg_t2m_patch`, `annavg_t2m_col`, `scalaravg_col`, `annsum_counter_col`, `tempsum_potential_gpp_patch`, `annsum_potential_gpp_patch`, `tempmax_retransn_patch`, `annmax_retransn_patch`, `tempmax_retransp_patch`, `annmax_retransp_patch`, `downreg_patch`, `rc14_atm_patch`, `c_allometry_patch`, `n_allometry_patch`, `p_allometry_patch`.

### Phenology State

`dormant_flag_patch`, `days_active_patch`, `onset_flag_patch`, `onset_counter_patch`, `onset_gddflag_patch`, `onset_fdd_patch`, `onset_gdd_patch`, `onset_swi_patch`, `offset_flag_patch`, `offset_counter_patch`, `offset_fdd_patch`, `offset_swi_patch`, `grain_flag_patch`, `lgsf_patch` (long growing season factor), `bglfr_patch` (background litterfall rate), `bglfr_leaf_patch`, `bglfr_froot_patch`, `bgtr_patch`, `alloc_pnow_patch`.

Module-level (not inside the type) targets: `fert_type(:)`, `fert_continue(:)`, `fert_dose(:,:)`, `fert_start(:)`, `fert_end(:)` carry forest fertilization experiment state.

## chemstate_type

Defined in `biogeochem/ChemStateType.F90:17`. Minimal type carrying `soil_pH(:,:)` on `(begc:endc, 1:nlevsoi)`. Used by `NitrifDenitrifMod` via `ph` column input for pH-dependent nitrification rate.

## CNPBudgetMod

`biogeochem/CNPBudgetMod.F90` implements mass-balance bookkeeping for C, N, P at the global level. It defines integer indexes for every flux and state in the C, N, P budgets and runs `CNPBudget_Reset`, `CNPBudget_Run`, `CNPBudget_Accum`, `CNPBudget_Print`, `CNPBudget_Restart`, `CNPBudget_SetBeginningMonthlyStates`, `CNPBudget_SetEndingMonthlyStates`.

Flux inputs tracked (C, `:41-55`): `f_gpp`, `f_er`, `f_fire_closs`, `f_hrv_xsmrpool_to_atm`, `f_prod1c_loss`, `f_prod10c_loss`, `f_prod100c_loss`, `f_som_c_leached`, `f_som_c_yield`, `f_dwt_conv_cflux`, `f_dwt_seedc_to_leaf`, `f_dwt_seedc_to_deadstem`.

Flux inputs tracked (N, `:76-97`): `f_ndep_to_sminn`, `f_nfix_to_ecosysn`, `f_nfix_to_sminn`, `f_supplement_to_sminn`, `f_fert_to_sminn`, `f_soyfixn_to_sminn`, `f_supplement_to_plantn`, `f_nfert_dose`, `f_denit`, `f_fire_ploss`, `f_n2o_nit`, `f_smin_no3_leached`, `f_smin_no3_runoff`, `f_sminn_leached`, `f_col_prod1n_loss`, `f_col_prod10n_loss`, `f_col_prod100n_loss`, `f_som_n_leached`, `f_som_n_yield`.

Flux inputs tracked (P, `:124-145`): `f_primp_to_labilep`, `f_supplement_to_sminp`, `f_supplement_to_plantp`, `f_pfert_dose`, `f_secondp_to_occlp`, `f_sminp_leached`, `f_col_fire_ploss`, `f_solutionp`, `f_labilep`, `f_secondp`, `f_col_prod1p_loss`, `f_col_prod10p_loss`, `f_col_prod100p_loss`, `f_som_p_yield`, `f_labilep_yield`, `f_secondp_yield`.

States tracked (begin and end of period, integer indices `s_*_beg` and `s_*_end`): `totc` / `totpftc` / `cwdc` / `totlitc` / `totsomc` / `totprodc` / `ctrunc` / `cropseedc_deficit` (carbon), `totpftn` / `cwdn` / `totlitn` / `totsomn` / `sminn` / `totprodn` / `plant_n_buffer` / `ntrunc` / `cropseedn_deficit` (nitrogen), `totpftp` / `cwdp` / `totlitp` / `totsomp` / `totprodp` / `ptrunc` / `solutionp` / `labilep` / `secondp` / `cropseedp_deficit` (phosphorus). A grid-level error term (`s_c_error`, `s_n_error`, `s_p_error`) closes each budget.

The budget accumulates at five temporal periods (`p_inst`, `p_day`, `p_mon`, `p_ann`, `p_inf`) via the local arrays `c_budg_fluxL/G`, `n_budg_fluxL/G`, `p_budg_fluxL/G` and `c/n/p_budg_stateL/G`. `Reset` is called at day/month/year boundaries; `Run` accumulates per timestep. `Print` emits formatted tables to the log.

## EcosystemBalanceCheckMod

`biogeochem/EcosystemBalanceCheckMod.F90` performs column and grid-level conservation checks with a tolerance of `balance_check_tolerance = 1e-8_r8`.

Public routines:
- `BeginColCBalance`, `BeginColNBalance`, `BeginColPBalance`: save pool totals at start of time step into `begcb`, `begnb`, `begpb`.
- `ColCBalanceCheck`, `ColNBalanceCheck`, `ColPBalanceCheck`: compute end-of-step totals, difference against input-output fluxes, abort if `|err| > tolerance`.
- `BeginGridCBalance`, `GridCBalanceCheck`, `BeginGridNBalance`, `BeginGridPBalance` and `EndGrid{C,N,P}BalanceAfterDynSubgridDriver`: grid-level equivalents, accounting for dynamic subgrid weight changes via `dyn_cbal_adjustments_col`.

The begin/end budget state arrays (`totpftc_beg_col`, `totpftc_end_col`, etc.) are written by `BeginColCBalance` and consumed by `ColCBalanceCheck` in combination with the flux arrays.

## Supporting Utilities

- `biogeochem/PrecisionControlMod.F90` (`PrecisionControl`) scans each living pool and each soil decomposition pool for values below a precision threshold and moves the residual into the per-species truncation sink (`ctrunc_patch`, `ntrunc_patch`, `ptrunc_patch`, and the vertically resolved `ctrunc_vr_col`, `ntrunc_vr_col`, `ptrunc_vr_col`). This protects downstream code from negative pools caused by round-off while preserving total mass via the truncation sinks.
- `biogeochem/SpeciesMod.F90` defines species IDs `CN_SPECIES_C12=1`, `CN_SPECIES_C13=2`, `CN_SPECIES_C14=3`, `CN_SPECIES_N=4`, `CN_SPECIES_P=5`. The `species` integer field inside `carbonstate_type` is set via `species_from_string`.
- `biogeochem/ComputeSeedMod.F90` computes initial seed C/N/P for newly opened patches during dynamic land cover change.

## Instances

- Patch state: `veg_cs` (bulk), `c13_veg_cs`, `c14_veg_cs`, `veg_ns`, `veg_ps` (in `data_types/VegetationDataType.F90`).
- Patch flux: `veg_cf`, `c13_veg_cf`, `c14_veg_cf`, `veg_nf`, `veg_pf`.
- Column state: `col_cs`, `c13_col_cs`, `c14_col_cs`, `col_ns`, `col_ps` (in `data_types/ColumnDataType.F90`).
- Column flux: `col_cf`, `c13_col_cf`, `c14_col_cf`, `col_nf`, `col_pf`.
- Gridcell: `grc_cs`, `grc_cf`, `grc_ns`, `grc_nf`, `grc_ps`, `grc_pf`.
- CN container: `cnstate_vars` (passed as argument between modules, held in `elm_instMod`).

When `use_fates = .true.`, the `InitAllocate` routines skip the patch-level vegetation pool allocations (`CNCarbonStateType.F90:195`), and the column summary routines are replaced by `col_cs%ZeroForFates`, `col_cf%ZeroForFates`, `col_ns%ZeroForFates`, `col_nf%ZeroForFates`, `col_ps%ZeroForFates`, `col_pf%ZeroForFates` called from `EcosystemDynLeaching` (`EcosystemDynMod.F90:257`). Column-level soil BGC pools (`decomp_cpools_vr_col`, `sminn_vr_col`, `solutionp_vr_col`, etc.) remain alive and are fed mineralization/immobilization fluxes through FATES's call into ELM soil BGC via `main/ELMFatesInterfaceMod.F90`.
