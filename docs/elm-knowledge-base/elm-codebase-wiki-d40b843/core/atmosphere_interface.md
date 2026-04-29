---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Atmosphere <-> Land Interface

The atmosphere–land exchange in ELM is organised around two derived types and their associated driver routines, all under `components/elm/src/main/`:

- `atm2lndType.F90` / `atm2lndMod.F90` — atmosphere → land fields and their topographic downscaling
- `lnd2atmType.F90` / `lnd2atmMod.F90` — land → atmosphere fluxes and state, built via weighted averages up the subgrid hierarchy

All gridcell-level fields live in `atm2lnd_vars` / `lnd2atm_vars` instances; the column-level downscaled versions live alongside them inside `atm2lnd_vars`.

**Major change at d40b843 vs 60d9aad:** `atm2lndMod` gained a new public entry point `topographic_effects_on_radiation`, paired with the `use_top_solar_rad`/`use_finetop_rad` namelist switches. `atm2lndMod` grew from 450 → 619 lines (`main/atm2lndMod.F90`). The other narratives (downscale_forcings, downscale_longwave, build_normalization, check_downscale_consistency) are intact.

## 1. `atm2lnd_type` — fields that arrive from the atmosphere

Source: `main/atm2lndType.F90`.

### 1.1 Non-downscaled gridcell fields (`*_grc`)

These are copied directly from the coupler and used as the reference for downscaling / conservation checks.

- Momentum / reference height: `forc_u_grc`, `forc_v_grc`, `forc_wind_grc`, `forc_hgt_grc`, `forc_hgt_u_grc`, `forc_hgt_t_grc`, `forc_hgt_q_grc`
- Thermodynamic state: `forc_t_not_downscaled_grc`, `forc_th_not_downscaled_grc`, `forc_q_not_downscaled_grc`, `forc_pbot_not_downscaled_grc`, `forc_rho_not_downscaled_grc`, `forc_vp_grc`, `forc_rh_grc`
- Precipitation: `forc_rain_not_downscaled_grc`, `forc_snow_not_downscaled_grc`
- Radiation: `forc_solad_grc(:,numrad)`, `forc_solai_grc(:,numrad)`, `forc_solar_grc`, `forc_lwrad_not_downscaled_grc`
- Chemistry / deposition: `forc_pco2_grc`, `forc_pc13o2_grc`, `forc_po2_grc`, `forc_pch4_grc`, `forc_aer_grc(:,:)`, `forc_ndep_grc`, `forc_pdep_grc`, plus the FAN streams when `use_fan`

The header comment warns that **downstream code must not use the non-downscaled versions directly** — they exist only as raw inputs for the downscaling routines and `lnd_import_export`. Everywhere else in ELM should consume the `_col` (downscaled) variants.

### 1.2 Downscaled column fields (`*_col`)

```
forc_t_downscaled_col       ! K
forc_th_downscaled_col      ! K
forc_q_downscaled_col       ! kg/kg
forc_pbot_downscaled_col    ! Pa
forc_rho_downscaled_col     ! kg/m^3
forc_rain_downscaled_col    ! mm/s
forc_snow_downscaled_col    ! mm/s
forc_lwrad_downscaled_col   ! W/m^2
```

### 1.3 Other inputs routed through `atm2lnd_type`

- Runoff / flood fields from the river component (`forc_flood_grc`, `volr_grc`, `volrmch_grc`, `supply_grc`, `deficit_grc`, `h2orof_grc`, `frac_h2orof_grc`).
- "Anomaly forcing" channels (`af_precip_grc`, `af_lwdn_grc`, `bc_precip_grc`).
- Time-averaged diagnostics that BGC needs (`fsd24_patch`, `prec365_patch`, `t_mo_patch`, `t_mo_min_patch`, `wind24_patch`, etc.).
- The `CPL_BYPASS` block lets the point-scale driver read compressed single-site drivers directly.

## 2. `atm2lndMod` — topographic downscaling

Source: `main/atm2lndMod.F90` (619 lines).

**Public entry points** (`main/atm2lndMod.F90:33-34`):

- `downscale_forcings(bounds, num_do_smb_c, filter_do_smb_c, atm2lnd_vars)` (`:45`).
- **`topographic_effects_on_radiation(bounds, atm2lnd_vars, nextsw_cday, declin, lnd2atm_vars)`** (`:455`). **NEW at d40b843** — paired with `use_top_solar_rad` and the fineTOP solar parameterization (and `use_finetop_rad`).

Internal helpers (`main/atm2lndMod.F90`):
- `downscale_longwave(bounds, num_do_smb_c, filter_do_smb_c, atm2lnd_vars)` (`:196`).
- `build_normalization(orig_field, sum_field, sum_wts, norms)` (`:321`).
- `check_downscale_consistency(bounds, atm2lnd_vars)` (`:383`).

### 2.1 Baseline: column = gridcell copy

For every active column, the eight gridcell fields are copied into their `_col` counterparts. This guarantees downstream code can uniformly read `_col` without knowing whether the column was downscaled.

### 2.2 Elevation-based downscaling (glc_mec + optional bare-land)

The filter `filter_do_smb_c` selects columns where the surface mass balance is computed. Historically this is only `istice_mec` columns; with `glcmec_downscale_rain_snow_convert` or when bare-land SMB is requested, `istsoil` columns are added. For every column in the filter the routine computes:

1. `hsurf_g = ldomain%topo(g)`, `hsurf_c = col_pp%glc_topo(c)`.
2. Temperature with `lapse_glcmec`: `tbot_c = tbot_g - lapse_glcmec * (hsurf_c - hsurf_g)`.
3. Scale height `Hbot = rair * 0.5*(tbot_g+tbot_c)/grav` and hydrostatic column pressure `pbot_c = pbot_g * exp(-(hsurf_c-hsurf_g)/Hbot)`.
4. Potential temperature: `thbot_c = tbot_c * exp((zbot_c/Hbot)*(rair/cpair))`.
5. Specific humidity via `Qsat(tbot_g,pbot_g,…)` and `Qsat(tbot_c,pbot_c,…)` so that `qbot_c = qbot_g * qs_c / qs_g`.
6. Optional rain ↔ snow conversion controlled by `glcmec_downscale_rain_snow_convert` and threshold constant `glcmec_rain_snow_threshold`.

### 2.3 Longwave downscaling

`downscale_longwave` is invoked after temperature downscaling. It assumes `dLW/dT = 4 * eps * sigma * T^3 = 4 * LW / T` from Stefan-Boltzmann, and `dT/dz = lapse_glcmec`:

```
forc_lwrad_c(c) = forc_lwrad_g(g)
                - 4 * forc_lwrad_g(g) / (0.5*(forc_t_c(c)+forc_t_g(g)))
                * lapse_glcmec * (hsurf_c - hsurf_g)
```

### 2.4 Conservation via per-gridcell normalization

`build_normalization` computes a scaling factor that, when applied to every downscaled column, restores the weighted gridcell mean of the original forcing field. Special cases: `sum_wts == 0` → `norm = 1`; `sum_field == 0` → `norm = 1`; otherwise `norm = orig_field / (sum_field / sum_wts)`. `downscale_longwave` applies this normalization and asserts the new weighted mean matches the original to `1.e-8` W/m² precision.

### 2.5 Consistency checks

`check_downscale_consistency` operates over a superset of the downscaling filter to catch cases where a non-filtered column still differs from the gridcell field, which would indicate an uninitialized column or an incorrect filter.

### 2.6 `topographic_effects_on_radiation` (NEW at d40b843)

`topographic_effects_on_radiation(bounds, atm2lnd_vars, nextsw_cday, declin, lnd2atm_vars)` (`main/atm2lndMod.F90:455-617`) is the new public entry. It is called from inside the per-clump physics loop (`main/elm_driver.F90:695-699`) when `use_finetop_rad` is true:

```fortran
if (use_finetop_rad) then
   call topographic_effects_on_radiation(bounds_clump, &
        atm2lnd_vars, nextsw_cday, declinp1, lnd2atm_vars)
endif
```

The routine applies sub-gridcell topographic corrections to direct- and diffuse-beam shortwave (using slope, aspect, sky view, and solar zenith / azimuth derived from `nextsw_cday` and `declin`) and writes corrected radiation fields back through `lnd2atm_vars` so they can flow into `lnd_export`. The `apparent_albd_grc` / `apparent_albi_grc` fields on `lnd2atm_vars` (used by `lnd_export` when `use_finetop_rad` is on) are populated here.

The companion namelist switch is `use_top_solar_rad` (which controls whether topo-aware solar parameters are read in `surfrd_get_topo_for_solar_rad` during `initialize1`). `use_finetop_rad` is a separate switch that gates this runtime entry; both flags can be active simultaneously.

## 3. `lnd2atm_type` — fields the land sends back

Source: `main/lnd2atmType.F90`.

The coupler receives only gridcell-level fields. `lnd2atm_type` stores everything flat with a `*_grc` suffix:

- Radiative / screen-level state: `t_rad_grc`, `t_ref2m_grc`, `q_ref2m_grc`, `u_ref10m_grc`, `u_ref10m_with_gusts_grc`, `coszen_str`.
- Hydrology: `h2osno_grc`, `h2osoi_vol_grc(:,:)`, `wslake_grc`, `t_grnd_grc`, `zwt_grc`, `t_soisno_grc(:,:)`, `Tqsur_grc`, `Tqsub_grc`.
- Radiation: `albd_grc(:,:)`, `albi_grc(:,:)`, `fsa_grc`, `eflx_lwrad_out_grc`. **NEW at d40b843:** `apparent_albd_grc(:,:)`, `apparent_albi_grc(:,:)` (the topographic-fineTOP-corrected albedos written by `topographic_effects_on_radiation` and consumed by `lnd_export` when `use_finetop_rad`).
- Momentum / turbulent fluxes: `taux_grc`, `tauy_grc`, `ram1_grc`, `fv_grc`, `flxdst_grc(:,:)`, `flxvoc_grc(:,:)`, `ddvel_grc(:,:)`.
- Mass / energy fluxes: `eflx_lh_tot_grc`, `eflx_sh_tot_grc`, `qflx_evap_tot_grc`, `nee_grc`, `nem_grc`, `flux_ch4_grc`, `flux_nh3_grc`.
- lnd → rof (routing): `qflx_rofliq_grc`, `qflx_rofliq_qsur_grc`, `qflx_rofliq_qsub_grc`, `qflx_rofliq_qgwl_grc`, `qflx_rofliq_qsurp_grc`, `qflx_rofliq_qsubp_grc`, `qflx_rofice_grc`, `qflx_rofmud_grc`, `qflx_h2orof_drain_grc`, `qflx_irr_demand_grc`.
- DOC / DIC transfer to routing: `qflx_rofliq_qsur_doc_grc`, `qflx_rofliq_qsur_dic_grc`, `qflx_rofliq_qsub_doc_grc`, `qflx_rofliq_qsub_dic_grc`.

## 4. `lnd2atmMod` — building the atm-bound state

Source: `main/lnd2atmMod.F90`.

The module uses the averaging primitives from `subgridAveMod` (see [`subgrid_utilities.md`](subgrid_utilities.md)) with hand-picked scale modes.

Two public entry points:

- `lnd2atm_minimal(bounds, surfalb_vars, solarabs_vars, energyflux_vars, atm2lnd_vars, lnd2atm_vars)` — the minimal set required for the first coupled time step. Every call uses `c2g`, `c2l_scale_type=urbanf`, `l2g_scale_type=unity` patterns.
- `lnd2atm(bounds, ...)` — the full field set, pulling from `col_ws`, `col_wf`, `col_cf`, `col_es`, `col_nf`, `veg_es`, `veg_ef`, `veg_ws`, `veg_wf`, `grc_ef`, `grc_ws`, `grc_wf`. Uses whichever averaging target makes physical sense for the field: `p2t` for any quantity the atmosphere sees at the topounit level, `p2g` / `c2g` otherwise.

### 4.1 Topounit-level radiative temperature

When `use_atm_downscaling_to_topunit` is enabled, `lnd2atm` also writes temperature and flux state to `top_es` / `top_af` so the downscaling can be coordinated per topounit.

### 4.2 Chemistry, tracers, and MEGAN

Optional blocks driven by `use_voc`, `use_lch4`, `use_c13`, `use_cn`, `use_fan`, and `use_fates` populate the VOC flux, methane flux, and nitrogen-related exchanges.

## 5. Order of operations around the coupler

The typical order within a coupled time step is:

1. Coupler deposits `forc_*_not_downscaled_grc`, radiation, deposition, river forcing into `atm2lnd_vars`. (For IAC and ocean coupling, `iac2lnd_vars` and `ocn2lnd_vars` are also populated — these are NEW at d40b843.)
2. **Optional: `topographic_effects_on_radiation`** when `use_finetop_rad`. NEW at d40b843.
3. `downscale_forcings(bounds, num_do_smb_c, filter_do_smb_c, atm2lnd_vars)` runs. Every active column now has a correct `forc_*_downscaled_col`.
4. Physics / biogeophysics / biogeochemistry run on columns and patches, reading exclusively from `_col` forcings.
5. `lnd2atm_minimal` / `lnd2atm` averages the new state back up to gridcells and stages it in `lnd2atm_vars`.
6. Coupler pulls `lnd2atm_vars` (and `lnd2glc_vars`, `lnd2iac_vars` when present) and sends it out.

If dynamic landuse or GLC changes the subgrid weights during the step, `reweight_wrapup` runs between steps (4) and (5) to keep the averages consistent.

## 6. Key design rules

- **Never read `forc_*_not_downscaled_grc` from physics code.** Use the `_col` variant, or the column will silently skip any elevation correction.
- **`check_downscale_consistency` is the final word** on whether the downscaling did the right thing for every active column.
- **Conservation is enforced at gridcell scale** via `build_normalization`, not at the column level.
- **lnd2atm averaging is field-specific.** Do not re-use a `c2g` scale combination from one field blindly.
- **`topographic_effects_on_radiation` is gated on `use_finetop_rad`**, not `use_top_solar_rad`. The two flags do related but different work: `use_top_solar_rad` reads the parameter file at startup; `use_finetop_rad` switches the runtime correction on.
