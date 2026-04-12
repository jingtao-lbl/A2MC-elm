---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Nitrogen Dynamics

Nitrogen biogeochemistry in ELM is split across several modules. External inputs (atmospheric deposition, biological fixation, agricultural fertilization) are in `biogeochem/NitrogenDynamicsMod.F90`; nitrification and denitrification are in `biogeochem/NitrifDenitrifMod.F90`; staged state updates are in `biogeochem/NitrogenStateUpdate1Mod.F90`, `NitrogenStateUpdate2Mod.F90`, and `NitrogenStateUpdate3Mod.F90` (plus BeTR equivalents); agricultural nitrogen cycling (FAN) is in `biogeochem/FanMod.F90` and `FanUpdateMod.F90`; Michaelis-Menten plant-microbe kinetic parameters for ECA nutrient competition are in `biogeochem/PlantMicKineticsMod.F90`. This page covers the entire ELM-side nitrogen cycle (the FATES-side vegetation N is handled inside the FATES library when `use_fates = .true.`).

## NitrogenDynamicsMod

`biogeochem/NitrogenDynamicsMod.F90` (686 lines) implements N inputs, losses, and fertilizer application. Public entry points:

- `NitrogenDynamicsInit` - set `nfix_timeconst` default of 10 days when not specified by namelist (`:65`).
- `readNitrogenDynamicsParams` - read `sf_minn` (soluble fraction of mineral N) and `sf_no3` (soluble fraction of NO3) into `CNNDynamicsParamsInst`.
- `NitrogenDeposition` - copy gridcell-level `forc_ndep_grc` to column `ndep_to_sminn_col` (`:120`). If `use_fan = .true.`, also call `fan_eval` to update agricultural N pools.
- `NitrogenFixation` - compute symbiotic + asymbiotic N fixation as a function of annual NPP (`:166`). In the CN mode the rate is computed per column from `annsum_npp_col` using an empirical relation calibrated to Cleveland et al. 1999; in the FATES mode the fixation rate is instead computed per FATES site using `alm_fates` data. The running mean is exponentially relaxed to NPP with time constant `nfix_timeconst` (default 10 days).
- `NitrogenFixation_balance` - alternative fixation routine used with the ECA nutrient competition path (`nu_com_nfix = .true.`), which balances plant demand against soil labile N.
- `NitrogenLeaching` - compute NO3 loss to subsurface drainage and surface runoff (`:279-403`).
- `NitrogenFert` - apply crop fertilizer and manure to the soil mineral N pool (`:406`). Crop synthetic fertilizer `synthfert` and the default-CLM `manure` are averaged to the column via `p2c` and added to `fert_to_sminn`. If `fan_to_bgc_crop = .true.`, FAN handles crop fertilizer instead. The FAN output is merged via `fan_to_sminn` at the end.
- `CNSoyfix` - soybean-specific fixation based on EPICPHASE (Cabelguenne et al. 1999), uses soil moisture, plant growth phase, and mineral N availability.

### NitrogenLeaching algorithm

`NitrogenLeaching` (`NitrogenDynamicsMod.F90:279`) uses `sf_no3 = CNNDynamicsParamsInst%sf_no3` (fraction of soil NO3 considered soluble, typically 1.0). Summary at `:279-403`:

1. Compute `tot_water(c) = sum_j h2osoi_liq(c,j)` over the active soil column, and `surface_water(c)` for the top `depth_runoff_Nloss` meters (for runoff loss).
2. For each level `j`:
   - Compute dissolved NO3 concentration `disn_conc = (sf_no3 * smin_no3_vr(c,j) * dz(c,j)) / h2osoi_liq(c,j)` (gN/kg water).
   - Leaching flux: `smin_no3_leached_vr(c,j) = disn_conc * drain_tot(c) * h2osoi_liq(c,j) / (tot_water(c) * dz(c,j))`.
   - Cap: `smin_no3_leached_vr(c,j) <= smin_no3_vr(c,j) / dt` (don't leach more than exists).
   - Cap: `smin_no3_leached_vr(c,j) <= sf_no3 * smin_no3_vr(c,j) / dt` (only the soluble fraction can leave per step).
3. Compute surface runoff loss `smin_no3_runoff_vr(c,j)` for layers with `zisoi(j) <= depth_runoff_Nloss`, using `qflx_surf` and the layer-weighted surface water content. Remaining NO3 after leaching is further depleted by runoff.
4. When `use_vertsoilc = .false.` (single layer decomposition), the simpler formulation `smin_no3_leached_vr(c,j) = disn_conc * drain_tot(c)` is used.

Only NO3 is leached in the nitrification/denitrification mode. In the legacy (non-nitrif_denitrif) mode, the total `sminn` is leached through `sminn_leached_vr_col` using `sf_minn` instead of `sf_no3`.

## NitrifDenitrifMod

`biogeochem/NitrifDenitrifMod.F90` computes nitrification (NH4 -> NO3) and denitrification (NO3 -> N2 + N2O) rates per soil level. Parameters in `NitrifDenitrifParamsInst` (type `NitrifDenitrifParamsType`, `:28`), read from the NetCDF parameter file by `readNitrifDenitrifParams`:

- `k_nitr_max` (1/s): maximum nitrification rate constant.
- `surface_tension_water` (J/m^2): Arah and Vinten 1995 parameter.
- `rij_kro_a`, `rij_kro_alpha`, `rij_kro_beta`, `rij_kro_gamma`, `rij_kro_delta`: Arah and Vinten 1995 anoxic-fraction parameters.

Namelist flag `no_frozen_nitrif_denitrif = .false.` (default) allows nitrification/denitrification in frozen soils.

### nitrif_denitrif algorithm (`:112`)

For each soil level and each column:

1. Compute nitrification rate from NH4 availability, modified by temperature, moisture, pH, and oxygen:
   ```
   k_nitr = k_nitr_max * k_nitr_t * k_nitr_ph * k_nitr_h2o
   f_nit_vr(c,j) = smin_nh4_vr(c,j) * k_nitr
   ```
   where `k_nitr_t = Q10_hr^((T - 25)/10)`, and `k_nitr_h2o` decreases under high water-filled pore space (`wfps`) and under very dry conditions. pH dependence `k_nitr_ph` follows the Parton et al. DAYCENT parameterization.
2. Compute denitrification rate from the "anoxic fraction" `f_a` based on soil air diffusivity and rate of CO2 production, following Arah and Vinten (1995). The anoxic fraction depends on `diffus`, `r_max` (max anoxic radius), and the parameters `rij_kro_*`.
   ```
   f_denit_vr(c,j) = f_a * min(fmax_denit_nitrate, fmax_denit_carbonsubstrate)
   ```
   where `fmax_denit_nitrate` is limited by substrate NO3 and `fmax_denit_carbonsubstrate` is limited by C substrate (soil HR).
3. Compute N2:N2O ratio from the denitrification-limiting factor.
4. Populate the flux arrays: `f_nit_vr_col`, `f_denit_vr_col`, `pot_f_nit_vr_col`, `pot_f_denit_vr_col`, `n2_n2o_ratio_denit_vr_col`, `f_n2o_denit_vr_col`, `f_n2o_nit_vr_col`, and kinetic diagnostics `k_nitr_t_vr_col`, `k_nitr_ph_vr_col`, `k_nitr_h2o_vr_col`, `k_nitr_vr_col`, `wfps_vr_col`, `fmax_denit_carbonsubstrate_vr_col`, `fmax_denit_nitrate_vr_col`, `f_denit_base_vr_col`, `diffus_col`, `anaerobic_frac_col`.

The N2O flux from nitrification is set to `f_n2o_nit_vr_col = nitrif_n2o_loss_frac * f_nit_vr_col` where `nitrif_n2o_loss_frac` is a module-level parameter in `elm_varcon` (default ~0.0006). The denitrification N2O flux is computed from the N2:N2O ratio.

`nitrif_denitrif` is called from within `SoilLittDecompAlloc` (`biogeochem/SoilLittDecompMod.F90`) during the decomposition phase.

## NitrogenStateUpdate1Mod

`biogeochem/NitrogenStateUpdate1Mod.F90` contains two public routines:

### NitrogenStateUpdateDynPatch (`:45`)

Called once per time step outside the three main stages, from `dynSubgridControlMod`. Handles N state changes driven by dynamic subgrid weight adjustments. When `.not. use_fates`:

- Gridcell `grc_ns%seedn(g) -= (dwt_seedn_to_leaf + dwt_seedn_to_deadstem + dwt_seedn_to_npool) * dt`.
- Column product pools `prod10n`, `prod100n`, `prod1n` get the `dwt_*_gain` additions.
- Column decomposing N pools gain fine root and coarse root transfers from landcover change: `col_ns%decomp_npools_vr(c,j,i_met_lit) += dwt_frootn_to_litr_met_n * dt` etc.

### NitrogenStateUpdate1 (stage 1, post-allocation)

Called from `EcosystemDynNoLeaching2` (not shown in snippet but parallel to `CarbonStateUpdate1`). Updates patch-level N pools from phenology and allocation fluxes:

- `veg_ns%leafn -= leafn_to_litter + leafn_to_retransn` (litterfall + retranslocation)
- `veg_ns%leafn += leafn_xfer_to_leafn` (transfer pool -> display pool)
- `veg_ns%leafn_storage += npool_to_leafn_storage` (allocation to storage)
- `veg_ns%leafn_xfer += leafn_storage_to_xfer - leafn_xfer_to_leafn` (storage -> xfer annual shift, xfer -> leaf flush)
- `veg_ns%npool += sminn_to_npool + retransn_to_npool + nfix_to_plantn`
- `veg_ns%npool -= npool_to_leafn - npool_to_leafn_storage - npool_to_frootn - ...`
- `veg_ns%retransn += leafn_to_retransn + frootn_to_retransn + livestemn_to_retransn`
- Column decomposing pools: `col_ns%decomp_npools_vr(c,j,l) += decomp_cascade_ntransfer` (net N transfer along cascade), plus litterfall from phenology.
- Column mineral N: `col_ns%sminn_vr(c,j) += ndep_to_sminn * ndep_prof(c,j) * dt + nfix_to_sminn * nfixation_prof(c,j) * dt + fert_to_sminn * ... * dt - (f_nit_vr + sminn_to_plant_vr + actual_immob_vr - gross_nmin_vr - supplement_to_sminn_vr) * dt`
- Column `smin_no3_vr`, `smin_nh4_vr` updated separately in the nitrif_denitrif mode.

Same structure for wood, grain, storage, and xfer pools for each tissue. The update is guarded by `is_active_betr_bgc` check so that under BeTR, the BeTR-flavored updater in `CNNStateUpdate1BeTRMod.F90` is used instead, and under `use_pflotran .and. pf_cmode`, PFLOTRAN handles the soil mineral N update.

Semantic meaning: **stage 1 = post-photosynthesis, post-allocation, post-decomposition (including deposition/fixation inputs and immobilization)**.

## NitrogenStateUpdate2Mod

`biogeochem/NitrogenStateUpdate2Mod.F90` has public routines `NitrogenStateUpdate2` and `NitrogenStateUpdate2h`. Called from `EcosystemDynNoLeaching2` after `GapMortality` (and after `CNHarvest` for the harvest flavor).

### NitrogenStateUpdate2 (stage 2, post-gap-mortality)

Updates column-level decomposing N pools for gap-phase mortality (`:59`):

```
col_ns%decomp_npools_vr(c,j,i_met_lit) += gap_mortality_n_to_litr_met_n(c,j) * dt
col_ns%decomp_npools_vr(c,j,i_cel_lit) += gap_mortality_n_to_litr_cel_n(c,j) * dt
col_ns%decomp_npools_vr(c,j,i_lig_lit) += gap_mortality_n_to_litr_lig_n(c,j) * dt
col_ns%decomp_npools_vr(c,j,i_cwd)     += gap_mortality_n_to_cwdn(c,j)       * dt
```

Then for each patch, subtract the tissue-level mortality fluxes from `leafn_patch`, `frootn_patch`, `livestemn_patch`, etc. and from their storage and xfer pools. Guarded by `.not. is_active_betr_bgc .and. .not. (use_pflotran .and. pf_cmode)`.

### NitrogenStateUpdate2h

The "harvest" variant: applies harvest fluxes (`hrv_*_to_litter_patch`, `hrv_*_to_prod1n_patch`, `hrv_deadstemn_to_prod10n_patch`, `hrv_deadstemn_to_prod100n_patch`) to patches. Separate from `NitrogenStateUpdate2` because in some configurations harvest is applied before gap mortality and needs its own update pass. Product pools `col_ns%prod10n`, `prod100n`, `prod1n` are incremented here.

Semantic meaning: **stage 2 = post-gap-mortality, post-harvest**.

## NitrogenStateUpdate3Mod

`biogeochem/NitrogenStateUpdate3Mod.F90`. Public routine `NitrogenStateUpdate3` called from `EcosystemDynLeaching`.

### NitrogenStateUpdate3 (stage 3, post-leaching and post-fire)

Updates (`:55-84`):

```
col_ns%smin_no3_vr(c,j) = max( col_ns%smin_no3_vr(c,j) - (smin_no3_leached_vr(c,j) + smin_no3_runoff_vr(c,j)) * dt, 0 )
col_ns%sminn_vr(c,j) = smin_no3_vr(c,j) + smin_nh4_vr(c,j)
( + smin_nh4sorb_vr if use_pflotran .and. pf_cmode )
```

Then fire losses: for each decomp pool `l`, `col_ns%decomp_npools_vr(c,j,l) -= m_decomp_npools_to_fire_vr(c,j,l) * dt`. Uncombusted wood (gap-mortality fire) flows back to litter/CWD: `col_ns%decomp_npools_vr(c,j,i_cwd) += fire_mortality_n_to_cwdn * dt`, `col_ns%decomp_npools_vr(c,j,i_met_lit) += m_n_to_litr_met_fire * dt`, etc.

Also (if `ero_ccycle`) SOM erosion losses.

Patch-level pools get their fire losses: `veg_ns%leafn -= m_leafn_to_fire * dt`, `veg_ns%retransn -= m_retransn_to_fire * dt`, etc. Plus litter fire fluxes from uncombusted portions of dead tissue.

Semantic meaning: **stage 3 = post-NO3 leaching, post-fire, post-SOM erosion**.

## BeTR N State Updates

Three BeTR-specific updater modules are in the biogeochem directory:

- `biogeochem/CNNStateUpdate1BeTRMod.F90`: `NStateUpdate1` for BeTR, called from `CNEcosystemDynBeTR`. Updates patch-level vegetation N pools from phenology and allocation, and delegates column-level decomposing and mineral N updates to the BeTR tracer-transport layer (so ELM does not update `col_ns%decomp_npools_vr` or `col_ns%sminn_vr` directly; BeTR carries those as tracers).
- `biogeochem/CNNStateUpdate2BeTRMod.F90`: `NStateUpdate2` for BeTR, stage 2 gap mortality.
- `biogeochem/CNNStateUpdate3BeTRMod.F90`: `NStateUpdate3` for BeTR, stage 3 fire and leaching.

Additionally `biogeochem/CNGapMortalityBeTRMod.F90` provides `CNGapMortality` (with `readCNGapMortBeTRParams`) and its `CNGapMortParamsType` has two parameters `am` (mortality rate, 1/yr) and `k_mort` (coefficient of growth efficiency in the mortality equation). The BeTR gap mortality additionally respects the flux-indicator arrays from `CNBeTRIndicatorMod.F90` (which in the current codebase set all indicators to 1, i.e. all fluxes are enabled).

## FanMod (Flow of Agricultural Nitrogen)

`biogeochem/FanMod.F90` (1255 lines) implements the FANv2 process model. The driver is in `biogeochem/FanUpdateMod.F90`. FAN tracks manure and fertilizer N through age-structured TAN (total ammoniacal nitrogen), NH3, and slurry pools, computing volatilization, leaching, and surface runoff losses.

### Pool structure (FanUpdateMod.F90:65)

- 4 slurry age classes `S0, S1, S2, S3` (`num_cls_slr = 4`)
- 3 grazing manure age classes `G1, G2, G3` (`num_cls_grz = 3`)
- 2 urea age classes `U1, U2` before hydrolysis (`num_cls_urea = 2`)
- 3 TAN age classes from urea hydrolysis `F1, F2, F3` (`num_cls_fert = 3`)
- 1 NH4 fertilizer class `F4` (`num_cls_otherfert = 1`)

The column-level state variables `tan_g1_col`, ..., `tan_s3_col` in `nitrogenstate_type` (`CNNitrogenStateType.F90:194`) hold the ammoniacal N content of each age class.

pH is age-class-specific: the youngest classes have pH 8.5 (fresh urea, alkaline) transitioning toward soil pH as the manure ages. Hconc (hydrogen concentration, mol/L) values at `FanUpdateMod.F90:77`:

```fortran
Hconc_grz_def = 10^(/ -8.5, -8.0 /)    ! grazing G1, G2
Hconc_slr_def = 10^(/ -8.0, -8.0, -8.0 /)  ! slurry S0, S1, S2
Hconc_fert    = 10^(/ -7.0, -8.5, -8.0 /)  ! F1, F2, F3
```

### Key subroutines

FanMod.F90 public interface (`:51-57`):
- `update_org_n`: decompose organic N, release TAN to soil.
- `eval_fluxes_storage`: compute N volatilization in animal housings and storage pools before manure is applied to the field.
- `update_npool`: evaluate fluxes and update the TAN n-pool model.
- `update_4pool`: evaluate fluxes and update the 4-pool slurry model.
- `update_urea`: update the urea-based pools (no NO3 or volatilization pathway).

Flux indices (`:60-73`): `iflx_air` (volatilization to atmosphere), `iflx_soild` (diffusion to soil), `iflx_no3` (nitrification), `iflx_soilq` (percolation), `iflx_roff` (surface runoff), `iflx_to_tan` (urea hydrolysis to TAN). Storage flux indices: `iflx_air_barns`, `iflx_air_stores`, `iflx_appl` (applied to field), `iflx_to_store` (transferred to storage).

Error flags: `err_bad_theta`, `err_negative_tan`, `err_negative_flux`, `err_balance_tan`, `err_balance_nitr`, `err_nan`, `err_bad_subst`, `err_bad_type`, `err_bad_arg`.

### FanUpdateMod driver

`fan_eval` (the main driver) is called from `NitrogenDeposition` when `use_fan = .true.` (`NitrogenDynamicsMod.F90:158`). It orchestrates:

1. `handle_storage` - update losses from in-storage manure before it is applied.
2. For each fertilizer type and each column, call `update_org_n`, `update_npool`, `update_4pool`, or `update_urea` as appropriate.
3. Compute total TAN and NO3 pools at the column level, deposit NH4 and NO3 into `col_ns%smin_nh4_vr_col` and `col_ns%smin_no3_vr_col` via the vertical profile `ndep_prof_col`.
4. `fan_to_sminn` collects the total FAN flux into `col_nf%fert_to_sminn`, which is then added to the soil mineral N pool during `NitrogenStateUpdate1`.

`fanInit` reads the FAN namelist parameters and sets up the TAN pools. The FAN stream module `fanStreamMod` (in the `main/` tree) provides the annual manure and fertilizer input forcing at gridcell resolution.

## PlantMicKineticsMod

`biogeochem/PlantMicKineticsMod.F90` defines `PlantMicKinetics_type` (`:12`) that carries per-level Michaelis-Menten parameters used for ECA-style nutrient competition between plants and decomposers. Fields:

- Plant uptake Vmax and Km (per-patch, per-level) for NH4, NO3, and P: `plant_nh4_vmax_vr_patch`, `plant_no3_vmax_vr_patch`, `plant_p_vmax_vr_patch`, `plant_nh4_km_vr_patch`, `plant_no3_km_vr_patch`, `plant_p_km_vr_patch`.
- `plant_eff_frootc_vr_patch`: effective fine-root C per level (weights plant enzyme abundance).
- `dsolutionp_dt_vr_col`: tendency of solution P, used by the P ECA path.
- `dlabp_dt_vr_col`: tendency of labile P.
- Decomposer efficiencies per level: `decomp_eff_ncompet_b_vr_col`, `decomp_eff_pcompet_b_vr_col`.
- Nitrification/denitrification efficiencies: `nit_eff_ncompet_b_vr_col`, `den_eff_ncompet_b_vr_col`.
- Plant efficiencies: `plant_eff_ncompet_b_vr_patch`, `plant_eff_pcompet_b_vr_patch`.
- Mineral surface competitiveness: `minsurf_p_compet_vr_col`, `minsurf_nh4_compet_vr_col`, `vmax_minsurf_p_vr_col`, `km_minsurf_p_vr_col`, `km_minsurf_nh4_vr_col`.
- Km values for decomposer uptake: `km_decomp_nh4_vr_col`, `km_decomp_no3_vr_col`, `km_decomp_p_vr_col`, `km_nit_nh4_vr_col`, `km_den_no3_vr_col`.

`PlantMicKinetics_type%Init`, `InitAllocate`, and `InitCold` allocate the arrays over `(begp:endp, 1:nlevdecomp_full)` or `(begc:endc, 1:nlevdecomp_full)` and initialize to NaN. The populated values come from `AllocationMod%calc_plantN_kineticpar` (for plants) and from per-level reaction rate calculations in `AllocationMod` (for decomposers).

The ECA scheme uses these parameters to compute the fraction of each nutrient form (NH4, NO3, P) that is taken up by plants, immobilized by decomposers, consumed by nitrifiers, or consumed by denitrifiers at each level. The resolved fractions feed into `Allocation2_ResolveNPLimit`.

## Related Flags and Parameters

- `elm_varctl%use_fan = .false.` (default): if true, run the FAN agricultural N model.
- `elm_varctl%fan_to_bgc_crop = .false.`: if true, let FAN handle crop fertilizer; otherwise `NitrogenFert` adds synthfert directly.
- `elm_varctl%fan_to_bgc_veg = .false.`: if true, let FAN manure apply to non-crop vegetated columns.
- `elm_varctl%fan_nh3_to_atm`: channel for NH3 volatilization output.
- `elm_varctl%use_fates = .false.`: when true, vegetation N dynamics (`NitrogenStateUpdate1` patch-level fluxes, gap mortality, phenology) are bypassed for vegetation and handled by FATES instead. Soil mineral N updates (`sminn_vr`, `smin_no3_vr`, `smin_nh4_vr`), nitrification/denitrification, decomposition, and leaching still run as described above regardless of FATES.
- `CNNDynamicsParamsInst%sf = sf_minn`: soluble fraction of mineral N (used in the non-nitrif_denitrif legacy path).
- `CNNDynamicsParamsInst%sf_no3`: soluble fraction of NO3 (typically 1.0).
- `nfix_timeconst`: exponential time constant (days) for the NPP-based running mean of fixation, default 10 days, defined in `CNCarbonFluxType.F90:34`.
- `no_frozen_nitrif_denitrif = .false.`: when true, disable nitrification/denitrification in frozen soils. Default false.

## Summary Flow

1. **Deposition + fixation + fertilization** (once per timestep, called from `EcosystemDynNoLeaching1`):
   `NitrogenDeposition` (+ FAN `fan_eval`) -> `col_nf%ndep_to_sminn`
   `NitrogenFixation` (or `NitrogenFixation_balance` under ECA) -> `col_nf%nfix_to_sminn`
   `NitrogenFert` -> `col_nf%fert_to_sminn`
2. **Nitrification + denitrification**: `nitrif_denitrif` (called from `SoilLittDecompAlloc`) -> `col_nf%f_nit_vr`, `f_denit_vr`, `f_n2o_nit_vr`, `f_n2o_denit_vr`.
3. **Decomposition + immobilization**: handled inside `SoilLittDecompAlloc` / `SoilLittDecompAlloc2` via `potential_immob_vr_col`, `actual_immob_vr_col`, `gross_nmin_vr_col`, `net_nmin_vr_col`, `sminn_to_plant_vr_col`.
4. **Stage 1 state update** `NitrogenStateUpdate1` (post-allocation).
5. **Gap mortality and harvest**: `CNHarvest`, then stage 2 `NitrogenStateUpdate2` and `NitrogenStateUpdate2h`.
6. **Fire** (`FireFluxes`): stage 3 fire fluxes prepared.
7. **Leaching**: `NitrogenLeaching` called from `EcosystemDynLeaching`.
8. **Stage 3 state update** `NitrogenStateUpdate3` (post-leaching, post-fire).

Under `use_fates = .true.`, steps 4-6 at the **vegetation** level are bypassed (FATES does its own plant N); soil mineral N updates in stages 1 and 3 still execute, and FATES communicates uptake demand to ELM via the BGC interface in `main/ELMFatesInterfaceMod.F90` so that plants in FATES still compete with decomposers, nitrifiers, and denitrifiers through `Allocation2_ResolveNPLimit` (run on behalf of FATES plants).
