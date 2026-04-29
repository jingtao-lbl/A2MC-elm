---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# CNP State and Flux Types

ELM's biogeochemistry stores pools and fluxes for carbon, nitrogen, and
phosphorus (plus the `C12`, `C13`, `C14` isotopes for carbon) in six derived
types defined in `biogeochem/`. A separate container type (`cnstate_type`) in
`data_types/CNStateType.F90` carries diagnostic flags, crop state, phenology
state, and other per-column / per-patch scalars that do not fit the pure
state/flux split. Patch-level instances are `veg_cs`, `veg_ns`, `veg_ps`
(states) and `veg_cf`, `veg_nf`, `veg_pf` (fluxes); column-level instances are
`col_cs`, `col_ns`, `col_ps`, `col_cf`, `col_nf`, `col_pf`, declared in
`data_types/VegetationDataType.F90` and `data_types/ColumnDataType.F90`.
Gridcell aggregates follow the same naming (`grc_cs`, `grc_cf`, etc.).

The key flag controlling which pools are allocated is `use_fates` in
`main/elm_varctl.F90:227`. When FATES is active, patch-level living plant pools
are not allocated by ELM; only soil-column pools and a few summary variables
remain alive.

## carbonstate_type

Defined in `biogeochem/CNCarbonStateType.F90:37`. Single `species` integer
field (1=C12, 2=C13, 3=C14) and a large set of pointers.

### Living Vegetation Pools (patch, gC/m2)

Three-state structure per tissue: display pool (active biomass), storage pool
(reserve), and transfer pool (onset flush buffer). Allocated only when
`.not. use_fates` (`CNCarbonStateType.F90:195`).

| Field group | Pools |
|---|---|
| Leaf | `leafc_patch`, `leafc_storage_patch`, `leafc_xfer_patch`, `leafcmax_patch` |
| Fine root | `frootc_patch`, `frootc_storage_patch`, `frootc_xfer_patch` |
| Live stem | `livestemc_patch`, `livestemc_storage_patch`, `livestemc_xfer_patch` |
| Dead stem | `deadstemc_patch`, `deadstemc_storage_patch`, `deadstemc_xfer_patch` |
| Live coarse root | `livecrootc_patch`, `livecrootc_storage_patch`, `livecrootc_xfer_patch` |
| Dead coarse root | `deadcrootc_patch`, `deadcrootc_storage_patch`, `deadcrootc_xfer_patch` |
| Grain (crop) | `grainc_patch`, `grainc_storage_patch`, `grainc_xfer_patch` |
| Growth resp storage | `gresp_storage_patch`, `gresp_xfer_patch` |
| Photosynthate | `cpool_patch`, `xsmrpool_patch`, `ctrunc_patch` |
| Diagnostic | `woodc_patch`, `dispvegc_patch`, `storvegc_patch`, `totvegc_patch`, `totpftc_patch`, `totvegc_abg_patch` |

Column-aggregated counterparts: `leafc_col`, `deadstemc_col`, `frootc_col`,
`rootc_col`, `totvegc_col`, `totvegcc_col`, `totpftc_col`, `totvegc_abg_col`,
`fuelc_col`, `fuelc_crop_col`.

The patch-on-soil-column test inside `Summary` and elsewhere uses the
`veg_pp%is_on_soil_col(p)` helper at d40b8431 (replacing
`lun_pp%itype(l) == istsoil` patterns).

### Soil Decomposing Pools (column, gC/m3 vertically resolved)

`decomp_cpools_vr_col(begc:endc, 1:nlevdecomp_full, 1:ndecomp_pools)` holds the
vertically resolved litter/CWD/SOM pools defined by the decomposition cascade.
The cascade has 7 pools in the BGC/CENTURY configuration: `i_met_lit`,
`i_cel_lit`, `i_lig_lit`, `i_cwd`, `i_soil1`, `i_soil2`, `i_soil3` (indices set
in `DecompCascadeBGCMod.F90:413-538`). `ctrunc_vr_col` is the per-level C
truncation sink.

Column summary variables (not in mass balance): `decomp_cpools_col`,
`decomp_cpools_1m_col`, `cwdc_col`, `ctrunc_col`, `totlitc_col`, `totsomc_col`,
`totlitc_1m_col`, `totsomc_1m_col`, `totecosysc_col`, `totcolc_col`,
`totabgc_col`, `totblgc_col`. The "is this column a soil column" test now uses
`col_pp%is_soil(c)` instead of landunit-type checks.

### Product and Seed Pools

`cropseedc_deficit_patch`, `seedc_grc`, `seedc_col`, `prod1c_col`,
`prod10c_col`, `prod100c_col`, `totprodc_col`, `dyn_cbal_adjustments_col`.

### Balance Check Book-keeping

`begcb_patch`, `begcb_col`, `begcb_grc`, `endcb_patch`, `endcb_col`, `endcb_grc`,
`errcb_patch`, `errcb_col`, `errcb_grc`. Plus `_beg_col`/`_end_col` arrays for
every major reservoir. Used by `EcosystemBalanceCheckMod.F90`.

### Procedures

`Init`, `SetValues`, `ZeroDWT`, `Restart`, `Summary`, plus private
`InitAllocate`, `InitHistory`, `InitCold`. The isotope-aware `Init` signature
takes a `carbon_type` string (`'c12'`, `'c13'`, `'c14'`) and an initial ratio,
and optionally a bulk c12 state to copy from.

## carbonflux_type

Defined in `biogeochem/CNCarbonFluxType.F90:36`. Contains over 200 pointers
covering every C flux in ELM. Several `iscft(ivt)` helper-based PFT tests have
replaced `ivt >= npcropmin` patterns inside the flux methods at d40b8431.

### Mortality Fluxes (patch, gC/m2/s)

Gap mortality `m_*_to_litter_patch` for each tissue and storage/xfer; harvest
mortality `hrv_*_to_litter_patch`, `hrv_deadstemc_to_prod10c_patch`,
`hrv_deadstemc_to_prod100c_patch`, `hrv_xsmrpool_to_atm_patch`,
`hrv_cpool_to_litter_patch`; crop harvest `hrv_leafc_to_prod1c_patch`,
`hrv_livestemc_to_prod1c_patch`, `hrv_grainc_to_prod1c_patch`,
`hrv_cropc_to_prod1c_patch`. Fire emissions `m_*_to_fire_patch` and
`m_*_to_litter_fire_patch` (uncombusted-fraction-to-CWD).

### Phenology Fluxes (patch)

`grainc_xfer_to_grainc_patch`, `leafc_xfer_to_leafc_patch`,
`frootc_xfer_to_frootc_patch`, `livestemc_xfer_to_livestemc_patch`, etc.
`leafc_to_litter_patch`, `frootc_to_litter_patch`, `livestemc_to_litter_patch`,
`grainc_to_food_patch`. `leafc_storage_to_xfer_patch`, etc.

### Respiration Fluxes (patch, gC/m2/s)

Maintenance: `leaf_mr_patch`, `froot_mr_patch`, `livestem_mr_patch`,
`livecroot_mr_patch`, `grain_mr_patch`. Decomposed into `_curmr_patch` (current
GPP) and `_xsmr_patch` (from storage). Excess C turnover: `xr_patch`.

Growth resp: `cpool_leaf_gr_patch`, `cpool_leaf_storage_gr_patch`,
`transfer_leaf_gr_patch` (and same for froot, livestem, deadstem, livecroot,
deadcroot, grain). Diagnostic: `mr_patch`, `gr_patch`, `current_gr_patch`,
`transfer_gr_patch`, `storage_gr_patch`, `ar_patch`, `rr_patch`. Photosynthesis:
`psnsun_to_cpool_patch`, `psnshade_to_cpool_patch`.

### Allocation Fluxes (patch, gC/m2/s)

`cpool_to_leafc_patch`, `cpool_to_leafc_storage_patch` for each of leaf, froot,
livestem, deadstem, livecroot, deadcroot, grain, plus `cpool_to_gresp_storage_patch`,
`cpool_to_xsmrpool_patch`. `plant_calloc_patch`, `excess_cflux_patch`,
`availc_patch`, `xsmrpool_recover_patch`, `xsmrpool_turnover_patch`.

### Summary Diagnostic Fluxes

`gpp_patch`, `gpp_before_downreg_patch`, `npp_patch`, `agnpp_patch`,
`bgnpp_patch`, `litfall_patch`, `wood_harvestc_patch`, `cinputs_patch`,
`coutputs_patch`, `fire_closs_patch`, `annavg_agnpp_patch`, `annavg_bgnpp_patch`,
`tempavg_agnpp_patch`, `tempavg_bgnpp_patch`, `agwdnpp_patch`, `frootc_alloc_patch`,
`leafc_alloc_patch`, `woodc_alloc_patch`, `frootc_loss_patch`, `leafc_loss_patch`,
`woodc_loss_patch`.

### Column-level Decomposition Fluxes (gC/m3/s vertically resolved)

`decomp_cascade_hr_vr_col`, `decomp_cascade_ctransfer_vr_col`, `decomp_k_col`,
`hr_vr_col`, `t_scalar_col`, `w_scalar_col`, `o_scalar_col`, `phr_vr_col`,
`fphr_col`, `decomp_cpools_sourcesink_col`, `m_decomp_cpools_to_fire_vr_col`,
`m_c_to_litr_met_fire_col`, `m_c_to_litr_cel_fire_col`,
`m_c_to_litr_lig_fire_col`, `somc_fire_col`, `decomp_cpools_leached_col`,
`decomp_cpools_transport_tendency_col`, `som_c_leached_col`.

### Column-level Aggregated Fluxes

`hr_col`, `lithr_col`, `somhr_col`, `sr_col`, `er_col`, `ar_col`, `rr_col`,
`npp_col`, `gpp_col`, `nep_col`, `nbp_col`, `nee_col`, `fire_closs_col`,
`fire_decomp_closs_col`, `cwdc_hr_col`, `cwdc_loss_col`, `litterc_loss_col`.

### Dynamic Land Use Fluxes

`dwt_seedc_to_leaf_patch`, `dwt_seedc_to_deadstem_patch`, `dwt_conv_cflux_patch`,
`dwt_prod10c_gain_patch`, `dwt_prod100c_gain_patch`,
`dwt_crop_productc_gain_patch`, `dwt_slash_cflux_col`,
`dwt_frootc_to_litr_met_c_col`, `dwt_livecrootc_to_cwdc_col`, `dwt_closs_col`,
`landuseflux_col`, `landuptake_col`. Grid-level totals `dwt_*_grc`.

### Product Pool Losses

`prod1c_loss_col`, `prod10c_loss_col`, `prod100c_loss_col`, `product_closs_col`,
`hrv_xsmrpool_to_atm_col`.

### PFLOTRAN / Annual Dribbler Interface

`externalc_to_decomp_cpools_col`, `externalc_to_decomp_delta_col`,
`f_co2_soil_vr_col`, `f_co2_soil_col`. `dwt_conv_cflux_dribbler` and
`hrv_xsmrpool_to_atm_dribbler` are `annual_flux_dribbler_type` instances.

### Procedures

`Init`, `SetValues`, `ZeroDWT`, `Restart`, `Summary`,
`summary_cflux_for_ch4`, `summary_rr`, **plus** `ZeroForFates` and (new at
d40b8431) `ZeroForFatesRR`. `ZeroForFates` is bound to all six column types
(`col_cs`, `col_cf`, `col_ns`, `col_nf`, `col_ps`, `col_pf` —
`ColumnDataType.F90:244, 339, 415, 692, 917, 1055`). `ZeroForFatesRR` is bound
ONLY to `col_cf` (`ColumnDataType.F90:693`, implementation at `:8059-8085`).
The "RR" stands for the radiation-step reset: it zeros the column-level carbon
flux fields that need to be cleared once per radiation step before
`alm_fates%UpdateLitterFluxes` writes new values.

## nitrogenstate_type

Defined in `biogeochem/CNNitrogenStateType.F90:35`. Module-level parameter
`npool_seed_param = 0.1_r8`.

### Vegetation N Pools (patch, gN/m2)

Same tissue structure as carbon: `leafn_patch`, `leafn_storage_patch`,
`leafn_xfer_patch`, plus `frootn_*`, `livestemn_*`, `deadstemn_*`,
`livecrootn_*`, `deadcrootn_*`, `grainn_*`. Plant-level N reserves:
`retransn_patch` (retranslocated N), `npool_patch`, `ntrunc_patch`,
`plant_n_buffer_patch`, `plant_n_buffer_col`.

### Soil Mineral N (column, gN/m3 and gN/m2)

`sminn_vr_col`, `sminn_col`. With nitrification/denitrification active,
`sminn_vr_col = smin_no3_vr_col + smin_nh4_vr_col` (rebuilt by stage-3 update).
Separate vertical and column pools: `smin_no3_vr_col`, `smin_no3_col`,
`smin_nh4_vr_col`, `smin_nh4_col`. Under PFLOTRAN coupling, an extra sorbed NH4
pool `smin_nh4sorb_vr_col`, `smin_nh4sorb_col` contributes to `sminn_vr`.

### Decomposing N Pools

`decomp_npools_vr_col`, `ntrunc_vr_col`. Diagnostic `decomp_npools_col`,
`decomp_npools_1m_col`, `cwdn_col`, `ntrunc_col`, `totlitn_col`, `totsomn_col`,
`totlitn_1m_col`, `totsomn_1m_col`, `totecosysn_col`, `totcoln_col`,
`totabgn_col`, `totblgn_col`, `totvegn_col`, `totpftn_col`. The
`iscft(veg_pp%itype(p))` predicate replaces `ivt >= npcropmin` in patch-loop
tests inside this module at d40b8431 (`CNNitrogenStateType.F90:1010`).

### Seed and Product Pools

`cropseedn_deficit_patch`, `seedn_grc`, `seedn_col`, `prod1n_col`, `prod10n_col`,
`prod100n_col`, `totprodn_col`, `dyn_nbal_adjustments_col`.

### Cost-Benefit and Physiological Sensitivities (NFIX_PTASE)

`npimbalance_patch`, `pnup_pfrootc_patch`, `ppup_pfrootc_patch`,
`ptlai_pleafc_patch`, `ppsnsun_ptlai_patch`, `ppsnsun_pleafn_patch`,
`ppsnsun_pleafp_patch`, `plmrsun_ptlai_patch`, `plmrsun_pleafn_patch`,
`benefit_pgpp_pleafc_patch`, `benefit_pgpp_pleafn_patch`,
`benefit_pgpp_pleafp_patch`, `cost_pgpp_pfrootc_patch`,
`cost_plmr_pleafc_patch`, `cost_plmr_pleafn_patch`, plus per-layer counterparts.

### FAN Pools (gN/m2)

Age-structured ammoniacal N pools: `tan_g1_col`, `tan_g2_col`, `tan_g3_col`
(grazing); `tan_s0_col`, `tan_s1_col`, `tan_s2_col`, `tan_s3_col` (slurry).
Active only when `use_fan = .true.`.

### Balance Check

`begnb_patch`, `endnb_patch`, `errnb_patch`, plus the col / grid counterparts
and `_beg_col`/`_end_col` arrays.

## nitrogenflux_type

Defined in `biogeochem/CNNitrogenFluxType.F90:24`. Mirrors `carbonflux_type`
mortality, harvest, phenology, allocation, decomposition, and dynamic-landuse
fluxes for N. Distinct N fluxes:

### External Inputs

`ndep_to_sminn_col` (atm N deposition), `nfix_to_sminn_col` (symbiotic +
asymbiotic fixation), `nfix_to_plantn_patch` (NFIX_PTASE plant-direct
fixation), `nfix_to_ecosysn_col`, `fert_to_sminn_col`, `soyfixn_to_sminn_col`,
`synthfert_patch`, `manure_patch`, `fert_counter_patch`, `soyfixn_patch`.

### Decomposition / Immobilization Fluxes

`decomp_cascade_ntransfer_vr_col`, `decomp_cascade_sminn_flux_vr_col`,
`potential_immob_vr_col`, `actual_immob_vr_col`, `sminn_to_plant_vr_col`,
`supplement_to_sminn_vr_col`, `gross_nmin_vr_col`, `net_nmin_vr_col`, plus
column totals.

### Nitrification / Denitrification

`f_nit_vr_col`, `f_nit_col`, `f_denit_vr_col`, `f_denit_col`, `pot_f_nit_vr_col`,
`pot_f_denit_vr_col`, `n2_n2o_ratio_denit_vr_col`, `f_n2o_denit_vr_col`,
`f_n2o_denit_col`, `f_n2o_nit_vr_col`, `f_n2o_nit_col`. Kinetic diagnostics:
`k_nitr_t_vr_col`, `k_nitr_ph_vr_col`, `k_nitr_h2o_vr_col`, `k_nitr_vr_col`,
`wfps_vr_col`, `fmax_denit_carbonsubstrate_vr_col`, `fmax_denit_nitrate_vr_col`,
`f_denit_base_vr_col`, `diffus_col`, `anaerobic_frac_col`.

### Immobilization / Uptake by N Form

`actual_immob_no3_vr_col`, `actual_immob_nh4_vr_col`,
`smin_no3_to_plant_vr_col`, `smin_nh4_to_plant_vr_col`, plus col totals.

### Leaching Fluxes

`smin_no3_leached_vr_col`, `smin_no3_leached_col`, `smin_no3_runoff_vr_col`,
`smin_no3_runoff_col`, `sminn_leached_vr_col`, `sminn_leached_col`.

### Legacy CN (non-nitrif_denitrif) Denitrification

`sminn_to_denit_decomp_cascade_vr_col`, `sminn_to_denit_decomp_cascade_col`,
`sminn_to_denit_excess_vr_col`, `sminn_to_denit_excess_col`.

### Turnover of Livewood to Deadwood

`livestemn_to_deadstemn_patch`, `livecrootn_to_deadcrootn_patch`,
`livestemn_storage_to_xfer_patch`, etc.

## phosphorusstate_type

Defined in `biogeochem/PhosphorusStateType.F90:37`. Module-level parameter
`ppool_seed_param = 0.01_r8`.

### Vegetation P Pools (patch, gP/m2)

Same tissue structure as N: `leafp_patch`, `leafp_storage_patch`,
`leafp_xfer_patch`, and for `frootp`, `livestemp`, `deadstemp`, `livecrootp`,
`deadcrootp`, `grainp`. Plant P reserves: `retransp_patch`, `ppool_patch`,
`ptrunc_patch`, `plant_p_buffer_patch`.

### Soil Inorganic P Cascade (column)

Four mineral reservoirs arranged in a cascade, vertically resolved on
`nlevdecomp_full`:

| Pool | Vertical field | Col total | Meaning |
|---|---|---|---|
| solution P | `solutionp_vr_col` | `solutionp_col` | Bio-available P in soil solution |
| labile P | `labilep_vr_col` | `labilep_col` | Exchangeable adsorbed P |
| secondary mineral P | `secondp_vr_col` | `secondp_col` | Slow-exchange adsorbed/precipitated P |
| occluded P | `occlp_vr_col` | `occlp_col` | Chemically occluded P |
| primary mineral P | `primp_vr_col` | - | Parent-material P, weathering source |

`sminp_vr_col` and `sminp_col` summarize total mineral P. `ptrunc_vr_col`,
`ptrunc_col` are the truncation sinks. Decomposing pools: `decomp_ppools_vr_col`,
`decomp_ppools_col`, `decomp_ppools_1m_col`. Diagnostics: `cwdp_col`,
`totlitp_col`, `totsomp_col`, `totlitp_1m_col`, `totsomp_1m_col`, `totecosysp_col`,
`totcolp_col`, `totvegp_col`, `totpftp_col`.

### Tracking Current vs Previous Time Step

`solutionp_vr_col_cur`, `solutionp_vr_col_prev`, `labilep_vr_col_cur`,
`labilep_vr_col_prev`, `secondp_vr_col_cur`, `secondp_vr_col_prev`,
`occlp_vr_col_cur`, `occlp_vr_col_prev`, `primp_vr_col_cur`,
`primp_vr_col_prev`.

### Seed and Product Pools

`cropseedp_deficit_patch`, `seedp_grc`, `seedp_col`, `prod1p_col`,
`prod10p_col`, `prod100p_col`, `totprodp_col`, `dyn_pbal_adjustments_col`.

### Balance Check

`begpb_patch`, `endpb_patch`, `errpb_patch` plus col and grid arrays.

`Init` signature takes initial leaf, froot, deadstem C and the C decomposing
pools to seed initial P pools from C:P ratios.

## phosphorusflux_type

Defined in `biogeochem/PhosphorusFluxType.F90:24`. Structure mirrors
`nitrogenflux_type` but with additional inorganic cascade fluxes.

### Inorganic Mineral Cycle (column, gP/m3/s vertically resolved)

- `pdep_to_sminp` (atm P deposition, col)
- `primp_to_labilep_vr`, `primp_to_labilep` (weathering, from
  `PhosphorusWeathering`)
- `labilep_to_secondp_vr`, `labilep_to_secondp` (adsorption, from
  `PhosphorusAdsportion`)
- `secondp_to_labilep_vr`, `secondp_to_labilep` (desorption, from
  `PhosphorusDesoprtion`)
- `secondp_to_occlp_vr`, `secondp_to_occlp` (occlusion, from
  `PhosphorusOcclusion`)
- `biochem_pmin_vr`, `biochem_pmin` (phosphatase, from `PhosphorusBiochemMin`
  or `_balance`)
- `pf_flx_input_vr_col` (external P input), `sminp_leached_vr_col`,
  `sminp_leached_col`
- `fert_p_to_sminp_col`, `fire_ploss_col`, `fire_decomp_ploss_col`

## cnstate_type

Defined in `data_types/CNStateType.F90:37`. Per-column and per-patch container
for diagnostic flags and auxiliary state shared across process modules.

### Crop State

`burndate_patch`, `lfpftd_patch`, `hdidx_patch`, `cumvd_patch`,
`gddmaturity_patch`, `huileaf_patch`, `huigrain_patch`, `aleafi_patch`,
`astemi_patch`, `aleaf_patch`, `astem_patch`, `htmx_patch`, `peaklai_patch`,
`idop_patch`, `isoilorder`.

### Vertical Profiles (1/m)

`leaf_prof_patch`, `froot_prof_patch`, `croot_prof_patch`, `stem_prof_patch`,
`nfixation_prof_col`, `ndep_prof_col`, `pdep_prof_col`, `som_adv_coef_col`,
`som_diffus_coef_col`. Computed in `biogeochem/VerticalProfileMod.F90`.

### Fire-related

`gdp_lf_col`, `peatf_lf_col`, `abm_lf_col`, `lgdp_col`, `lgdp1_col`, `lpop_col`,
`nfire_col`, `fsr_col`, `fd_col`, `lfc_col`, `lfc2_col`, `dtrotr_col`,
`trotr1_col`, `trotr2_col`, `cropf_col`, `baf_crop_col`, `baf_peatf_col`,
`fbac_col`, `fbac1_col`, `wtlf_col`, `lfwt_col`, `farea_burned_col`.

### N/P Limitation State

`fpi_vr_col`, `fpi_col`, `fpg_col`, `fpi_p_vr_col`, `fpi_p_col`, `fpg_p_col`,
`fpg_nh4_vr_col`, `fpg_no3_vr_col`, `frootc_nfix_scalar_col`,
`decomp_litpool_rcn_col`.

### Decomposition Cascade Coefficients (per-column)

`rf_decomp_cascade_col(begc:endc, 1:nlevdecomp, 1:ndecomp_cascade_transitions)`,
`pathfrac_decomp_cascade_col`.

### Annual / Temporary Accumulators

`tempavg_t2m_patch`, `annavg_t2m_patch`, `annavg_t2m_col`, `scalaravg_col`,
`annsum_counter_col`, `tempsum_potential_gpp_patch`,
`annsum_potential_gpp_patch`, `tempmax_retransn_patch`,
`annmax_retransn_patch`, `tempmax_retransp_patch`, `annmax_retransp_patch`,
`downreg_patch`, `rc14_atm_patch`, `c_allometry_patch`, `n_allometry_patch`,
`p_allometry_patch`.

### Phenology State

`dormant_flag_patch`, `days_active_patch`, `onset_flag_patch`,
`onset_counter_patch`, `onset_gddflag_patch`, `onset_fdd_patch`,
`onset_gdd_patch`, `onset_swi_patch`, `offset_flag_patch`,
`offset_counter_patch`, `offset_fdd_patch`, `offset_swi_patch`,
`grain_flag_patch`, `lgsf_patch`, `bglfr_patch`, `bglfr_leaf_patch`,
`bglfr_froot_patch`, `bgtr_patch`, `alloc_pnow_patch`.

Module-level (not inside the type): `fert_type(:)`, `fert_continue(:)`,
`fert_dose(:,:)`, `fert_start(:)`, `fert_end(:)` for forest fertilization
experiments.

## chemstate_type

Defined in `biogeochem/ChemStateType.F90:17`. Minimal type carrying
`soil_pH(:,:)` on `(begc:endc, 1:nlevsoi)`. Used by `NitrifDenitrifMod` for
pH-dependent nitrification rate.

## CNPBudgetMod

`biogeochem/CNPBudgetMod.F90` implements global mass-balance bookkeeping for
C, N, P. It defines integer indexes for every flux and state in the C, N, P
budgets and runs `CNPBudget_Reset`, `CNPBudget_Run`, `CNPBudget_Accum`,
`CNPBudget_Print`, `CNPBudget_Restart`, `CNPBudget_SetBeginningMonthlyStates`,
`CNPBudget_SetEndingMonthlyStates`. Tracked flux groups: C inputs/outputs and
balance terms (~12 fluxes), N inputs/outputs (~20 fluxes), P inputs/outputs
(~16 fluxes). Tracked states (`s_*_beg` / `s_*_end`) cover every reservoir;
errors `s_c_error`, `s_n_error`, `s_p_error` close each budget. Five temporal
periods (`p_inst`, `p_day`, `p_mon`, `p_ann`, `p_inf`) accumulate via the
`c_budg_fluxL/G`, `n_budg_fluxL/G`, `p_budg_fluxL/G` arrays.

## EcosystemBalanceCheckMod

`biogeochem/EcosystemBalanceCheckMod.F90` performs column- and grid-level
conservation checks with `balance_check_tolerance = 1e-8_r8`. Public routines:

- `BeginColCBalance`, `BeginColNBalance`, `BeginColPBalance` — save begin-of-step
  totals into `begcb`, `begnb`, `begpb`.
- `ColCBalanceCheck`, `ColNBalanceCheck`, `ColPBalanceCheck` — compute
  end-of-step totals, abort if `|err| > tolerance`.
- `BeginGridCBalance`, `GridCBalanceCheck`, `BeginGridNBalance`,
  `BeginGridPBalance`, `EndGrid{C,N,P}BalanceAfterDynSubgridDriver` — grid-level
  with `dyn_cbal_adjustments_col` accounting.

## Supporting Utilities

- `biogeochem/PrecisionControlMod.F90` (`PrecisionControl`): scans each living
  pool and each soil decomposition pool for values below a precision threshold,
  moves the residual into `ctrunc_patch` / `ntrunc_patch` / `ptrunc_patch`
  (or vertically resolved `ctrunc_vr_col` / `ntrunc_vr_col` / `ptrunc_vr_col`).
- `biogeochem/SpeciesMod.F90`: species IDs `CN_SPECIES_C12=1`, `CN_SPECIES_C13=2`,
  `CN_SPECIES_C14=3`, `CN_SPECIES_N=4`, `CN_SPECIES_P=5`. Set via
  `species_from_string`.
- `biogeochem/ComputeSeedMod.F90`: computes initial seed C/N/P for newly opened
  patches during dynamic land cover change.

## Instances

- Patch state: `veg_cs`, `c13_veg_cs`, `c14_veg_cs`, `veg_ns`, `veg_ps`
  (in `data_types/VegetationDataType.F90`).
- Patch flux: `veg_cf`, `c13_veg_cf`, `c14_veg_cf`, `veg_nf`, `veg_pf`.
- Column state: `col_cs`, `c13_col_cs`, `c14_col_cs`, `col_ns`, `col_ps`
  (in `data_types/ColumnDataType.F90`).
- Column flux: `col_cf`, `c13_col_cf`, `c14_col_cf`, `col_nf`, `col_pf`.
- Gridcell: `grc_cs`, `grc_cf`, `grc_ns`, `grc_nf`, `grc_ps`, `grc_pf`.
- CN container: `cnstate_vars` (passed as argument between modules, held in
  `elm_instMod`).

## ZeroForFates and ZeroForFatesRR (FATES Coupling)

When `use_fates = .true.`, the `InitAllocate` routines skip the patch-level
vegetation pool allocations (`CNCarbonStateType.F90:195`). At runtime two
distinct zeroing pathways are used:

1. **Once per leaching pass** (`EcosystemDynLeaching`, after the column-summary
   block where the veg-summary was skipped): `col_*%ZeroForFates(bounds,
   num_soilc, filter_soilc)` is called for ALL six column types
   (`EcosystemDynMod.F90:248-253`):

   ```fortran
   call col_cs%ZeroForFates(bounds,num_soilc, filter_soilc)
   call col_ns%ZeroForFates(bounds,num_soilc, filter_soilc)
   call col_ps%ZeroForFates(bounds,num_soilc, filter_soilc)
   call col_cf%ZeroForFates(bounds,num_soilc, filter_soilc)
   call col_nf%ZeroForFates(bounds,num_soilc, filter_soilc)
   call col_pf%ZeroForFates(bounds,num_soilc, filter_soilc)
   ```

   This zeros the column-level upscaled veg arrays so the subsequent column
   summaries do not double-count anything FATES will report through the
   `wrap_*` callbacks.

2. **Once per radiation step**, only on `col_cf` and only when `use_fates`
   (`EcosystemDynNoLeaching2:686`):

   ```fortran
   call col_cf%ZeroForFatesRR(bounds,num_soilc, filter_soilc)
   call alm_fates%UpdateLitterFluxes(bounds)
   ```

   `ZeroForFatesRR` (`ColumnDataType.F90:693`, implementation at `:8059-8085`)
   clears the carbon-flux fields that need a clean state immediately before
   FATES writes new litter fluxes via `UpdateLitterFluxes`. The "RR" suffix
   denotes the radiation-step reset.

After the staged updates, two more FATES wrappers complete the leaching pass
(`EcosystemDynMod.F90:267-270`):

```fortran
if (use_fates) then
   call alm_fates%wrap_FatesAtmosphericCarbonFluxes(bounds, num_soilc, filter_soilc)
   call alm_fates%wrap_FatesCarbonStocks(bounds, num_soilc, filter_soilc)
endif
```

`wrap_FatesAtmosphericCarbonFluxes` (`elmfates_interfaceMod.F90:2771-2816`)
copies FATES-side atmospheric C exchange fluxes into the ELM gridcell totals so
NEE / NBP closures account for FATES-managed C; `wrap_FatesCarbonStocks`
(`:2820-2858`) copies FATES cohort biomass into the ELM column-level summary
arrays. Combined with `wrap_WoodProducts` (called at
`EcosystemDynNoLeaching2:811`), these three wrappers replace the per-patch
veg summary that runs only when `.not. use_fates`.

Column-level soil BGC pools (`decomp_cpools_vr_col`, `sminn_vr_col`,
`solutionp_vr_col`, etc.) remain alive in both modes and are fed
mineralization/immobilization fluxes through FATES's call into ELM soil BGC via
`main/elmfates_interfaceMod.F90` (the canonical filename — note the lowercase
`elmfates_interface`).
