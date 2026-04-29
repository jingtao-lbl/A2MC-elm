---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Nitrogen Dynamics

Nitrogen biogeochemistry in ELM is split across several modules. External
inputs (atmospheric deposition, biological fixation, agricultural fertilization)
are in `biogeochem/NitrogenDynamicsMod.F90`; nitrification and denitrification
are in `biogeochem/NitrifDenitrifMod.F90`; staged state updates are in
`biogeochem/NitrogenStateUpdate1Mod.F90`, `NitrogenStateUpdate2Mod.F90`, and
`NitrogenStateUpdate3Mod.F90` (plus BeTR equivalents); agricultural nitrogen
cycling (FAN) is in `biogeochem/FanMod.F90` and `FanUpdateMod.F90`;
Michaelis-Menten plant-microbe kinetic parameters for ECA nutrient competition
are in `biogeochem/PlantMicKineticsMod.F90`. This page covers the entire
ELM-side nitrogen cycle (the FATES-side vegetation N is handled inside the
FATES library when `use_fates = .true.`).

## NitrogenDynamicsMod (signatures rewritten at d40b8431)

`biogeochem/NitrogenDynamicsMod.F90` (682 lines). Public entries (with the
exact arg lists at d40b8431):

```fortran
public :: NitrogenDynamicsInit
public :: NitrogenDeposition
public :: NitrogenFixation
public :: NitrogenLeaching
public :: NitrogenFert
public :: CNSoyfix
public :: readNitrogenDynamicsParams
public :: NitrogenFixation_balance
```

| Subroutine | Line | Signature |
|---|---|---|
| `NitrogenDynamicsInit` | `:64` | `()` (no args). Sets `nfix_timeconst = 10` if user did not override. |
| `readNitrogenDynamicsParams` | `:81` | `(ncid)`. Reads `sf_minn` and `sf_no3` into `CNNDynamicsParamsInst`. |
| `NitrogenDeposition` | `:117` | `(bounds, atm2lnd_vars)`. **2 args** (was 7 in 60d9aad). FAN dispatch was lifted out — see below. |
| `NitrogenFixation` | `:156` | `(bounds, num_soilc, filter_soilc, dayspyr)`. NPP-based; uses `alm_fates` data when `use_fates`. |
| `NitrogenLeaching` | `:251` | `(num_soilc, filter_soilc, dt)`. **`bounds` removed**. |
| `NitrogenFert` | `:390` | `(bounds, num_soilc, filter_soilc, num_pcropp, filter_pcropp, num_ppercropp, filter_ppercropp)`. **+2 perennial-crop args**. |
| `CNSoyfix` | `:463` | `(bounds, num_soilc, filter_soilc, num_soilp, filter_soilp, crop_vars, cnstate_vars)`. |
| `NitrogenFixation_balance` | `:596` | `(num_soilc, filter_soilc, cnstate_vars)`. ECA path. |

### `CNNDynamicsParamsInst%sf` and `sf_no3` are scalars, NOT pointers (d40b8431)

The type definition at `:49-52`:

```fortran
type, public :: CNNDynamicsParamsType
   real(r8) :: sf      ! soluble fraction of mineral N (unitless)
   real(r8) :: sf_no3  ! soluble fraction of NO3 (unitless)
end type CNNDynamicsParamsType
```

In 60d9aad these were declared as pointers initialized via `allocate(...%sf)`.
In d40b8431 they are plain scalars; `readNitrogenDynamicsParams` (`:107, 112`)
assigns them with `%sf = tempr`. Code that did `pointer => CNNDynamicsParamsInst%sf`
or tested `associated(...)` is no longer valid.

### NitrogenDeposition (2-arg) — FAN dispatch moved out

```fortran
subroutine NitrogenDeposition( bounds, atm2lnd_vars )
   type(bounds_type)  , intent(in)  :: bounds
   type(atm2lnd_type) , intent(in)  :: atm2lnd_vars
   ...
   do c = begc, endc
      g = col_pp%gridcell(c)
      ndep_to_sminn(c) = forc_ndep(g)
   end do
end subroutine NitrogenDeposition
```

The body simply copies `atm2lnd_vars%forc_ndep_grc(g)` to
`col_nf%ndep_to_sminn(c)`. The `if (use_fan) call fan_eval(...)` branch that
lived inside `NitrogenDeposition` in 60d9aad was lifted to a sibling call in
`EcosystemDynNoLeaching1:375-378`:

```fortran
call NitrogenDeposition(bounds, atm2lnd_vars)
if (use_fan) then
  call fan_eval(bounds, num_soilc, filter_soilc, &
       atm2lnd_vars, soilstate_vars, frictionvel_vars)
end if
```

### NitrogenLeaching algorithm

`NitrogenLeaching(num_soilc, filter_soilc, dt)` (`:251`) uses
`sf_no3 = CNNDynamicsParamsInst%sf_no3`. Outline:

1. Compute `tot_water(c) = sum_j h2osoi_liq(c,j)` over the active soil column,
   and `surface_water(c)` for the top `depth_runoff_Nloss` meters.
2. For each level `j`:
   - `disn_conc = (sf_no3 * smin_no3_vr(c,j) * dz(c,j)) / h2osoi_liq(c,j)`
     (gN/kg water).
   - `smin_no3_leached_vr(c,j) = disn_conc * drain_tot(c) * h2osoi_liq(c,j) /
     (tot_water(c) * dz(c,j))`.
   - Cap: `<= smin_no3_vr(c,j) / dt` and `<= sf_no3 * smin_no3_vr(c,j) / dt`.
3. Surface runoff loss `smin_no3_runoff_vr(c,j)` for layers with `zisoi(j) <=
   depth_runoff_Nloss`.
4. When `use_vertsoilc = .false.`, the simpler formulation
   `smin_no3_leached_vr(c,j) = disn_conc * drain_tot(c)` is used.

Only NO3 is leached in the nitrification/denitrification mode. In the legacy
(non-nitrif_denitrif) mode, total `sminn` is leached through
`sminn_leached_vr_col` using `sf_minn` instead of `sf_no3`.

### NitrogenFert (perennial-crop aware)

The `:390` signature now branches on `fan_to_bgc_crop`:

- If `fan_to_bgc_crop = .false.`: `synthfert` and the default-CLM `manure` are
  averaged to the column via `p2c_1d_filter` and added to `fert_to_sminn`. Both
  `num_pcropp` and `num_ppercropp` patch loops accumulate `totalfert(p) =
  synthfert(p) + manure(p)` (`:445-453`).
- If `fan_to_bgc_crop = .true.`: FAN handles crop fertilizer; the call
  `fan_to_sminn(bounds, filter_soilc, num_soilc, totalfert)` (`:458`) merges
  the FAN output into `fert_to_sminn` regardless.

The 2-extra perennial-crop arguments are required because the bioenergy
perennials (`nmiscanthus`, `nswitchgrass`, irrigated variants) have their own
patch filter `filter_ppercropp`.

## NitrifDenitrifMod

`biogeochem/NitrifDenitrifMod.F90` computes nitrification (NH4 -> NO3) and
denitrification (NO3 -> N2 + N2O) rates per soil level. Parameters in
`NitrifDenitrifParamsInst` (type `NitrifDenitrifParamsType`):

- `k_nitr_max` (1/s): maximum nitrification rate constant.
- `surface_tension_water` (J/m^2): Arah and Vinten 1995 parameter.
- `rij_kro_a`, `rij_kro_alpha`, `rij_kro_beta`, `rij_kro_gamma`,
  `rij_kro_delta`: Arah and Vinten 1995 anoxic-fraction parameters.

Namelist flag `no_frozen_nitrif_denitrif = .false.` (default) allows
nitrification/denitrification in frozen soils.

### nitrif_denitrif algorithm

For each soil level and each column:

1. Nitrification rate from NH4 availability, modified by temperature, moisture,
   pH, and oxygen:
   ```
   k_nitr = k_nitr_max * k_nitr_t * k_nitr_ph * k_nitr_h2o
   f_nit_vr(c,j) = smin_nh4_vr(c,j) * k_nitr
   ```
   where `k_nitr_t = Q10_hr^((T - 25)/10)`, `k_nitr_h2o` decreases under high
   wfps and very dry conditions, and `k_nitr_ph` follows DAYCENT (Parton et al.).
2. Denitrification rate from the "anoxic fraction" `f_a` based on soil air
   diffusivity and CO2 production rate (Arah & Vinten 1995).
   ```
   f_denit_vr(c,j) = f_a * min(fmax_denit_nitrate, fmax_denit_carbonsubstrate)
   ```
3. Compute N2:N2O ratio.
4. Populate `f_nit_vr_col`, `f_denit_vr_col`, `pot_f_nit_vr_col`,
   `pot_f_denit_vr_col`, `n2_n2o_ratio_denit_vr_col`, `f_n2o_denit_vr_col`,
   `f_n2o_nit_vr_col`, plus kinetic diagnostics
   (`k_nitr_t_vr_col`, `k_nitr_ph_vr_col`, `k_nitr_h2o_vr_col`,
   `k_nitr_vr_col`, `wfps_vr_col`, `fmax_denit_carbonsubstrate_vr_col`,
   `fmax_denit_nitrate_vr_col`, `f_denit_base_vr_col`, `diffus_col`,
   `anaerobic_frac_col`).

The N2O flux from nitrification is `f_n2o_nit_vr_col = nitrif_n2o_loss_frac *
f_nit_vr_col`. `nitrif_denitrif` is called from within `SoilLittDecompAlloc`
during the decomposition phase.

## NitrogenStateUpdate1Mod

`biogeochem/NitrogenStateUpdate1Mod.F90` contains two public routines:

### NitrogenStateUpdateDynPatch (`:45`)

Called once per time step from `dynSubgridControlMod`. Handles N state changes
driven by dynamic subgrid weight adjustments. When `.not. use_fates`:

- `grc_ns%seedn(g) -= (dwt_seedn_to_leaf + dwt_seedn_to_deadstem +
  dwt_seedn_to_npool) * dt`.
- Column product pools `prod10n`, `prod100n`, `prod1n` get the `dwt_*_gain`
  additions.
- Column decomposing N pools gain fine root and coarse root transfers from
  landcover change.

### NitrogenStateUpdate1 (`:101`, stage 1: post-allocation)

Called from `EcosystemDynNoLeaching2:706`. Updates patch-level N pools from
phenology and allocation fluxes:

- `veg_ns%leafn -= leafn_to_litter + leafn_to_retransn`
- `veg_ns%leafn += leafn_xfer_to_leafn`
- `veg_ns%leafn_storage += npool_to_leafn_storage`
- `veg_ns%leafn_xfer += leafn_storage_to_xfer - leafn_xfer_to_leafn`
- `veg_ns%npool += sminn_to_npool + retransn_to_npool + nfix_to_plantn`
- `veg_ns%npool -= npool_to_leafn - npool_to_leafn_storage - npool_to_frootn - ...`
- `veg_ns%retransn += leafn_to_retransn + frootn_to_retransn + livestemn_to_retransn`
- Column decomposing pools: `col_ns%decomp_npools_vr(c,j,l) +=
  decomp_cascade_ntransfer * dt`.
- Column mineral N: `col_ns%sminn_vr(c,j) += (ndep_to_sminn * ndep_prof + ...)
  * dt`.
- Column `smin_no3_vr`, `smin_nh4_vr` updated separately under nitrif_denitrif.

Same structure for wood, grain, storage, and xfer pools. Guarded by
`is_active_betr_bgc` (BeTR override) and `use_pflotran .and. pf_cmode`
(PFLOTRAN override).

Semantic meaning: **stage 1 = post-photosynthesis, post-allocation,
post-decomposition (including deposition/fixation inputs and immobilization)**.

## NitrogenStateUpdate2Mod

`biogeochem/NitrogenStateUpdate2Mod.F90` has public routines
`NitrogenStateUpdate2` (`:33`) and `NitrogenStateUpdate2h` (`:112`). Called from
`EcosystemDynNoLeaching2` after `GapMortality` (and after `CNHarvest` for the
harvest flavor).

### NitrogenStateUpdate2 (stage 2, post-gap-mortality)

Updates column-level decomposing N pools for gap-phase mortality:

```fortran
col_ns%decomp_npools_vr(c,j,i_met_lit) += gap_mortality_n_to_litr_met_n(c,j) * dt
col_ns%decomp_npools_vr(c,j,i_cel_lit) += gap_mortality_n_to_litr_cel_n(c,j) * dt
col_ns%decomp_npools_vr(c,j,i_lig_lit) += gap_mortality_n_to_litr_lig_n(c,j) * dt
col_ns%decomp_npools_vr(c,j,i_cwd)     += gap_mortality_n_to_cwdn(c,j)       * dt
```

Then for each patch, subtract tissue mortality from `leafn_patch`,
`frootn_patch`, etc. and from storage and xfer pools.

### NitrogenStateUpdate2h

Harvest variant. Applies `hrv_*_to_litter_patch`, `hrv_*_to_prod1n_patch`,
`hrv_deadstemn_to_prod10n_patch`, `hrv_deadstemn_to_prod100n_patch` to patches.
Product pools `col_ns%prod10n`, `prod100n`, `prod1n` are incremented here.

Semantic meaning: **stage 2 = post-gap-mortality, post-harvest**.

## NitrogenStateUpdate3Mod

`biogeochem/NitrogenStateUpdate3Mod.F90`. Public routine
`NitrogenStateUpdate3(num_soilc, filter_soilc, num_soilp, filter_soilp, dt)`
(`:31`) called from `EcosystemDynLeaching`.

### NitrogenStateUpdate3 (stage 3, post-leaching and post-fire)

```fortran
col_ns%smin_no3_vr(c,j) = max( col_ns%smin_no3_vr(c,j) - &
                               (smin_no3_leached_vr(c,j) + smin_no3_runoff_vr(c,j)) * dt, 0 )
col_ns%sminn_vr(c,j) = smin_no3_vr(c,j) + smin_nh4_vr(c,j)
( + smin_nh4sorb_vr if use_pflotran .and. pf_cmode )
```

Then fire losses: `col_ns%decomp_npools_vr(c,j,l) -=
m_decomp_npools_to_fire_vr(c,j,l) * dt`. Uncombusted wood flows back to
litter/CWD: `col_ns%decomp_npools_vr(c,j,i_cwd) += fire_mortality_n_to_cwdn *
dt`, etc.

If `ero_ccycle`, SOM erosion losses.

Patch-level fire losses: `veg_ns%leafn -= m_leafn_to_fire * dt`,
`veg_ns%retransn -= m_retransn_to_fire * dt`, etc.

Semantic meaning: **stage 3 = post-NO3 leaching, post-fire, post-SOM erosion**.

## BeTR N State Updates

Three BeTR-specific updater modules:

- `biogeochem/CNNStateUpdate1BeTRMod.F90` (`NStateUpdate1` for BeTR)
- `biogeochem/CNNStateUpdate2BeTRMod.F90` (`NStateUpdate2` for BeTR)
- `biogeochem/CNNStateUpdate3BeTRMod.F90` (`NStateUpdate3` for BeTR)

Additionally `biogeochem/CNGapMortalityBeTRMod.F90` provides `CNGapMortality`
with `readCNGapMortBeTRParams`. The BeTR gap mortality respects the
flux-indicator arrays from `CNBeTRIndicatorMod.F90` (currently all 1, no
effect).

## FanMod (Flow of Agricultural Nitrogen)

`biogeochem/FanMod.F90` implements the FANv2 process model. Driver in
`biogeochem/FanUpdateMod.F90`. FAN tracks manure and fertilizer N through
age-structured TAN, NH3, and slurry pools, computing volatilization, leaching,
and surface runoff losses.

### Pool structure (FanUpdateMod.F90:65)

- 4 slurry age classes `S0, S1, S2, S3` (`num_cls_slr = 4`)
- 3 grazing manure age classes `G1, G2, G3` (`num_cls_grz = 3`)
- 2 urea age classes `U1, U2` before hydrolysis (`num_cls_urea = 2`)
- 3 TAN age classes from urea hydrolysis `F1, F2, F3` (`num_cls_fert = 3`)
- 1 NH4 fertilizer class `F4` (`num_cls_otherfert = 1`)

Column-level state variables `tan_g1_col`, ..., `tan_s3_col` in
`nitrogenstate_type` hold the ammoniacal N content of each age class.

pH is age-class-specific:
```fortran
Hconc_grz_def = 10^(/ -8.5, -8.0 /)    ! grazing G1, G2
Hconc_slr_def = 10^(/ -8.0, -8.0, -8.0 /)  ! slurry S0, S1, S2
Hconc_fert    = 10^(/ -7.0, -8.5, -8.0 /)  ! F1, F2, F3
```

### Key subroutines

FanMod.F90 public interface:
- `update_org_n`: decompose organic N, release TAN to soil.
- `eval_fluxes_storage`: in-storage volatilization before manure is applied.
- `update_npool`: TAN n-pool model.
- `update_4pool`: 4-pool slurry model.
- `update_urea`: urea-based pools.

Flux indices: `iflx_air`, `iflx_soild`, `iflx_no3`, `iflx_soilq`, `iflx_roff`,
`iflx_to_tan`. Storage indices: `iflx_air_barns`, `iflx_air_stores`,
`iflx_appl`, `iflx_to_store`. Error flags `err_bad_theta`, `err_negative_tan`,
`err_negative_flux`, `err_balance_tan`, `err_balance_nitr`, `err_nan`,
`err_bad_subst`, `err_bad_type`, `err_bad_arg`.

### FanUpdateMod driver

`fan_eval(bounds, num_soilc, filter_soilc, atm2lnd_vars, soilstate_vars,
frictionvel_vars)` is called from `EcosystemDynNoLeaching1:375-378`
(separately from `NitrogenDeposition` in d40b8431). It orchestrates:

1. `handle_storage` — losses from in-storage manure.
2. For each fertilizer type and each column, `update_org_n`, `update_npool`,
   `update_4pool`, or `update_urea`.
3. Deposit NH4 and NO3 into `col_ns%smin_nh4_vr_col` and
   `col_ns%smin_no3_vr_col` via `ndep_prof_col`.
4. `fan_to_sminn` collects the total FAN flux into `col_nf%fert_to_sminn`.

`fanInit` reads the FAN namelist and sets up the TAN pools. The FAN stream
module `fanStreamMod` provides annual manure and fertilizer input forcing.

## PlantMicKineticsMod

`biogeochem/PlantMicKineticsMod.F90` defines `PlantMicKinetics_type` carrying
per-level Michaelis-Menten parameters used for ECA-style nutrient competition:

- Plant uptake Vmax and Km per-patch per-level for NH4, NO3, and P:
  `plant_nh4_vmax_vr_patch`, `plant_no3_vmax_vr_patch`, `plant_p_vmax_vr_patch`,
  `plant_nh4_km_vr_patch`, `plant_no3_km_vr_patch`, `plant_p_km_vr_patch`.
- `plant_eff_frootc_vr_patch`: effective fine-root C per level.
- `dsolutionp_dt_vr_col`, `dlabp_dt_vr_col`: solution-P and labile-P
  tendencies for the P ECA path.
- Decomposer efficiencies: `decomp_eff_ncompet_b_vr_col`,
  `decomp_eff_pcompet_b_vr_col`.
- Nitrif/denit efficiencies: `nit_eff_ncompet_b_vr_col`,
  `den_eff_ncompet_b_vr_col`.
- Plant efficiencies: `plant_eff_ncompet_b_vr_patch`,
  `plant_eff_pcompet_b_vr_patch`.
- Mineral surface competitiveness: `minsurf_p_compet_vr_col`,
  `minsurf_nh4_compet_vr_col`, `vmax_minsurf_p_vr_col`, `km_minsurf_p_vr_col`,
  `km_minsurf_nh4_vr_col`.
- Decomposer Km values: `km_decomp_nh4_vr_col`, `km_decomp_no3_vr_col`,
  `km_decomp_p_vr_col`, `km_nit_nh4_vr_col`, `km_den_no3_vr_col`.

`PlantMicKinetics_type%Init`, `InitAllocate`, `InitCold` allocate over
`(begp:endp, 1:nlevdecomp_full)` or `(begc:endc, 1:nlevdecomp_full)`.

The ECA scheme uses these to compute the fraction of each nutrient form taken
up by plants, immobilized by decomposers, consumed by nitrifiers, or consumed
by denitrifiers at each level. The resolved fractions feed
`Allocation2_ResolveNPLimit`.

## Related Flags and Parameters

- `elm_varctl%use_fan = .false.`: if true, run the FAN agricultural N model.
- `elm_varctl%fan_to_bgc_crop = .false.`: if true, FAN handles crop fertilizer.
- `elm_varctl%fan_to_bgc_veg = .false.`: if true, FAN manure to non-crop
  vegetated columns.
- `elm_varctl%fan_nh3_to_atm`: NH3 volatilization output channel.
- `elm_varctl%use_fates = .false.` (`elm_varctl.F90:227`): when true, vegetation
  N dynamics are bypassed for vegetation and handled by FATES. Soil mineral N
  updates, nitrification/denitrification, decomposition, and leaching still run
  regardless of FATES.
- `CNNDynamicsParamsInst%sf` (scalar): soluble fraction of mineral N (legacy
  path).
- `CNNDynamicsParamsInst%sf_no3` (scalar): soluble fraction of NO3 (typically
  1.0).
- `nfix_timeconst`: exponential time constant (days) for the NPP-based running
  mean of fixation, default 10 days.
- `no_frozen_nitrif_denitrif = .false.`: when true, disable
  nitrification/denitrification in frozen soils.

## Summary Flow

1. **Deposition + fixation + fertilization** (called from
   `EcosystemDynNoLeaching1`):
   - `NitrogenDeposition(bounds, atm2lnd_vars)` (`:117`) -> `col_nf%ndep_to_sminn`
   - (if `use_fan`) `fan_eval(...)` — separate sibling call
   - `NitrogenFixation(bounds, num_soilc, filter_soilc, dayspyr)` (`:156`)
     OR `NitrogenFixation_balance(num_soilc, filter_soilc, cnstate_vars)`
     (`:596`) under ECA -> `col_nf%nfix_to_sminn`
   - (if `crop_prog`) `NitrogenFert(bounds, num_soilc, filter_soilc,
     num_pcropp, filter_pcropp, num_ppercropp, filter_ppercropp)` (`:390`) ->
     `col_nf%fert_to_sminn`
   - (if `crop_prog`) `CNSoyfix` (`:463`)
2. **Nitrification + denitrification**: `nitrif_denitrif` (called from
   `SoilLittDecompAlloc`) -> `col_nf%f_nit_vr`, `f_denit_vr`, `f_n2o_nit_vr`,
   `f_n2o_denit_vr`.
3. **Decomposition + immobilization**: handled inside `SoilLittDecompAlloc` /
   `SoilLittDecompAlloc2` via `potential_immob_vr_col`, `actual_immob_vr_col`,
   `gross_nmin_vr_col`, `net_nmin_vr_col`, `sminn_to_plant_vr_col`.
4. **Stage 1 state update** `NitrogenStateUpdate1` (post-allocation, runs for
   both `use_fates` and `.not. use_fates` modes per
   `EcosystemDynMod.F90:706`).
5. **Gap mortality and harvest** (only when `.not. use_fates`): `CNHarvest`,
   then stage 2 `NitrogenStateUpdate2` and `NitrogenStateUpdate2h`.
6. **Fire** (`FireFluxes`): stage 3 fire fluxes prepared.
7. **Leaching**: `NitrogenLeaching(num_soilc, filter_soilc, dt)` (`:251`)
   called from `EcosystemDynLeaching`.
8. **Stage 3 state update** `NitrogenStateUpdate3` (post-leaching, post-fire).

Under `use_fates = .true.`, steps 4-6 at the **vegetation** level are
bypassed; soil mineral N updates in stages 1 and 3 still execute, and FATES
communicates uptake demand to ELM via the BGC interface in
`main/elmfates_interfaceMod.F90` (lowercase) so plants in FATES still compete
with decomposers, nitrifiers, and denitrifiers through
`Allocation2_ResolveNPLimit` (run on behalf of FATES plants).
