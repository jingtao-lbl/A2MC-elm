---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Atmosphere <-> Land Interface

The atmosphere–land exchange in ELM is organised around two derived types and their
associated driver routines, all under `components/elm/src/main/`:

- `atm2lndType.F90` / `atm2lndMod.F90` — atmosphere → land fields and their
  topographic downscaling
- `lnd2atmType.F90` / `lnd2atmMod.F90` — land → atmosphere fluxes and state, built
  via weighted averages up the subgrid hierarchy

All gridcell-level fields live in `atm2lnd_vars` / `lnd2atm_vars` instances; the
column-level downscaled versions live alongside them inside `atm2lnd_vars` so both
sets can be accessed from the same object.

## 1. `atm2lnd_type` — fields that arrive from the atmosphere

Source: `main/atm2lndType.F90:38-150+`.

### 1.1 Non-downscaled gridcell fields (`*_grc`)

These are copied directly from the coupler and used as the reference for
downscaling / conservation checks.

- Momentum / reference height: `forc_u_grc`, `forc_v_grc`, `forc_wind_grc`,
  `forc_hgt_grc`, `forc_hgt_u_grc`, `forc_hgt_t_grc`, `forc_hgt_q_grc`
- Thermodynamic state: `forc_t_not_downscaled_grc`,
  `forc_th_not_downscaled_grc`, `forc_q_not_downscaled_grc`,
  `forc_pbot_not_downscaled_grc`, `forc_rho_not_downscaled_grc`,
  `forc_vp_grc`, `forc_rh_grc`
- Precipitation: `forc_rain_not_downscaled_grc`,
  `forc_snow_not_downscaled_grc`
- Radiation: `forc_solad_grc(:,numrad)`, `forc_solai_grc(:,numrad)`,
  `forc_solar_grc`, `forc_lwrad_not_downscaled_grc`
- Chemistry / deposition: `forc_pco2_grc`, `forc_pc13o2_grc`, `forc_po2_grc`,
  `forc_pch4_grc`, `forc_aer_grc(:,:)`, `forc_ndep_grc`, `forc_pdep_grc`,
  and the FAN NH₃ / urea / nitrate / manure / soilpH streams when `use_fan`

The header comment at `main/atm2lndType.F90:28-37` warns that **downstream code must
not use the non-downscaled versions directly** — they exist only as raw inputs for
the downscaling routines and `lnd_import_export`. Everywhere else in ELM should
consume the `_col` (downscaled) variants.

### 1.2 Downscaled column fields (`*_col`)

Source: `main/atm2lndType.F90:105-113`.

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

- Runoff / flood fields from the river component (`forc_flood_grc`, `volr_grc`,
  `volrmch_grc`, `supply_grc`, `deficit_grc`, `h2orof_grc`, `frac_h2orof_grc`)
  arrive here and are consumed by hydrology.
- "Anomaly forcing" channels (`af_precip_grc` … `af_lwdn_grc`, `bc_precip_grc`)
  allow coupled experiments to add a small perturbation field on top of the
  standard forcing.
- Time-averaged diagnostics that BGC needs (`fsd24_patch`, `prec365_patch`,
  `t_mo_patch`, `t_mo_min_patch`, `wind24_patch`, etc.) are also cached on the
  `atm2lnd_type` instance so they can be restarted together with the forcing.
- The `CPL_BYPASS` block (`main/atm2lndType.F90:40-69`) lets the point-scale driver
  read compressed single-site drivers directly instead of going through the
  coupler.

## 2. `atm2lndMod` — topographic downscaling

Source: `main/atm2lndMod.F90`.

Public entry point: `downscale_forcings(bounds, num_do_smb_c, filter_do_smb_c,
atm2lnd_vars)` (`main/atm2lndMod.F90:41-189`).

### 2.1 Baseline: column = gridcell copy

For every active column, the eight gridcell fields are copied into their `_col`
counterparts (`main/atm2lndMod.F90:98-110`). This guarantees downstream code can
uniformly read `_col` without knowing whether the column was downscaled.

### 2.2 Elevation-based downscaling (glc_mec + optional bare-land)

The filter `filter_do_smb_c` selects columns where the surface mass balance is
computed. Historically this is only the `istice_mec` columns; with
`glcmec_downscale_rain_snow_convert` or when bare-land SMB is requested, `istsoil`
columns are added as well. For every column in the filter the routine computes
(`main/atm2lndMod.F90:115-181`):

1. `hsurf_g = ldomain%topo(g)`, `hsurf_c = col_pp%glc_topo(c)` — the gridcell and
   column surface elevations.
2. Temperature with `lapse_glcmec`:
   `tbot_c = tbot_g - lapse_glcmec * (hsurf_c - hsurf_g)`.
3. Scale height `Hbot = rair * 0.5*(tbot_g+tbot_c)/grav` and hydrostatic column
   pressure `pbot_c = pbot_g * exp(-(hsurf_c-hsurf_g)/Hbot)`.
4. Potential temperature via the derivation laid out at
   `main/atm2lndMod.F90:135-152`:
   `thbot_c = tbot_c * exp((zbot_c/Hbot)*(rair/cpair))`.
5. Specific humidity via `Qsat(tbot_g,pbot_g,…)` and `Qsat(tbot_c,pbot_c,…)` so
   that `qbot_c = qbot_g * qs_c / qs_g`, then density from the ideal gas law.
6. Optional rain ↔ snow conversion controlled by
   `glcmec_downscale_rain_snow_convert` and the threshold constant
   `glcmec_rain_snow_threshold`: warmer columns convert snow → rain, colder
   columns convert rain → snow (`main/atm2lndMod.F90:171-179`). The comment at
   `:168-170` flags that this conversion is **not energy-conserving** in its
   current form.

### 2.3 Longwave downscaling

`downscale_longwave` (`main/atm2lndMod.F90:192-314`) is invoked after temperature
downscaling because it uses the column-level temperature. It assumes
`dLW/dT = 4 * eps * sigma * T^3 = 4 * LW / T` from the Stefan–Boltzmann law, and
`dT/dz = lapse_glcmec`, giving (`main/atm2lndMod.F90:265-267`):

```
forc_lwrad_c(c) = forc_lwrad_g(g)
                - 4 * forc_lwrad_g(g) / (0.5*(forc_t_c(c)+forc_t_g(g)))
                * lapse_glcmec * (hsurf_c - hsurf_g)
```

### 2.4 Conservation via per-gridcell normalization

Because the downscaling filter generally does **not** cover 100% of a gridcell,
`build_normalization(orig_field, sum_field, sum_wts, norms)`
(`main/atm2lndMod.F90:316-375`) computes a scaling factor that, when applied to
every downscaled column, restores the weighted gridcell mean of the original
forcing field. The worked example at `main/atm2lndMod.F90:326-346` walks through
four glacier + vegetated columns with partial coverage. Special cases:

- `sum_wts == 0` → `norm = 1` (nothing to fix)
- `sum_field == 0` → `norm = 1` (gridcell mean was zero anyway)
- otherwise `norm = orig_field / (sum_field / sum_wts)`

`downscale_longwave` applies this normalization to `forc_lwrad_c`
(`main/atm2lndMod.F90:282-310`) and asserts that the new weighted mean matches the
original to `1.e-8` W/m² precision (`:297-308`).

### 2.5 Consistency checks

`check_downscale_consistency(bounds, atm2lnd_vars)`
(`main/atm2lndMod.F90:378-450`) operates over a superset of the downscaling filter
to catch cases where a non-filtered column still differs from the gridcell field,
which would indicate an uninitialized column or an incorrect filter.

## 3. `lnd2atm_type` — fields the land sends back

Source: `main/lnd2atmType.F90:28-89+`.

The coupler receives only gridcell-level fields. `lnd2atm_type` stores everything
flat and uses a `*_grc` suffix for clarity:

- Radiative / screen-level state: `t_rad_grc`, `t_ref2m_grc`, `q_ref2m_grc`,
  `u_ref10m_grc`, `u_ref10m_with_gusts_grc`
- Hydrology: `h2osno_grc`, `h2osoi_vol_grc(:,:)`, `wslake_grc`, `t_grnd_grc`,
  `zwt_grc`, `t_soisno_grc(:,:)`, `Tqsur_grc`, `Tqsub_grc`
- Radiation: `albd_grc(:,:)`, `albi_grc(:,:)`, `fsa_grc`,
  `eflx_lwrad_out_grc`
- Momentum / turbulent fluxes: `taux_grc`, `tauy_grc`, `ram1_grc`,
  `fv_grc`, `flxdst_grc(:,:)`, `flxvoc_grc(:,:)`, `ddvel_grc(:,:)`
- Mass / energy fluxes: `eflx_lh_tot_grc`, `eflx_sh_tot_grc`,
  `qflx_evap_tot_grc`, `nee_grc`, `nem_grc`, `flux_ch4_grc`, `flux_nh3_grc`
- lnd → rof (routing): `qflx_rofliq_grc`, `qflx_rofliq_qsur_grc`,
  `qflx_rofliq_qsub_grc`, `qflx_rofliq_qgwl_grc`, `qflx_rofliq_qsurp_grc`,
  `qflx_rofliq_qsubp_grc`, `qflx_rofice_grc`, `qflx_rofmud_grc`,
  `qflx_h2orof_drain_grc`, `qflx_irr_demand_grc`
- DOC / DIC transfer to routing: `qflx_rofliq_qsur_doc_grc`,
  `qflx_rofliq_qsur_dic_grc`, `qflx_rofliq_qsub_doc_grc`,
  `qflx_rofliq_qsub_dic_grc`

Allocation happens in `InitAllocate` and history registration in `InitHistory`
(`main/lnd2atmType.F90:105-150+`).

## 4. `lnd2atmMod` — building the atm-bound state

Source: `main/lnd2atmMod.F90`.

The module uses the averaging primitives from `subgridAveMod` (see
`core/subgrid_utilities.md`) with hand-picked scale modes. At the top of the file
(`main/lnd2atmMod.F90:50-51`) it re-declares the scale constants so its `p2g` /
`c2g` calls are self-documenting.

Two public entry points:

- `lnd2atm_minimal(bounds, surfalb_vars, energyflux_vars, lnd2atm_vars)`
  (`main/lnd2atmMod.F90:57-120+`) — the minimal set of fields required to start
  the first coupled time step (snow water, soil moisture, direct/diffuse albedo,
  upwelling longwave). Every call is structured as, for example,
  `call c2g(bounds, h2osno, h2osno_grc, c2l_scale_type=urbanf,
  l2g_scale_type=unity)` so that urban column aggregation stays separate from
  gridcell aggregation.
- `lnd2atm(bounds, …)` — the full field set, pulling from `col_ws`, `col_wf`,
  `col_cf`, `col_es`, `col_nf`, `veg_es`, `veg_ef`, `veg_ws`, `veg_wf`,
  `grc_ef`, `grc_ws`, `grc_wf` (`main/lnd2atmMod.F90:32-37`). The routine uses
  whichever averaging target makes physical sense for the field: `p2t` for any
  quantity the atmosphere sees at the topounit level (relevant when
  `use_atm_downscaling_to_topunit` is true), and `p2g` / `c2g` otherwise.

### 4.1 Topounit-level radiative temperature

When `use_atm_downscaling_to_topunit` is enabled, `lnd2atm` also writes temperature
and flux state to `top_es` / `top_af`
(`main/lnd2atmMod.F90:32`) so the downscaling can be coordinated per topounit. This
is the forward path that pairs with the reverse path in `atm2lndMod`.

### 4.2 Chemistry, tracers, and MEGAN

Optional blocks driven by namelist flags `use_voc`, `use_lch4`, `use_c13`, `use_cn`,
`use_fan`, and `use_fates` populate the VOC flux, methane flux, and nitrogen-related
exchanges. `DUSTMod`, `DryDepVelocity`, `VocEmissionMod`, `FrictionVelocityType`, and
`CH4Mod` are imported (`main/lnd2atmMod.F90:23-28`) solely so `lnd2atm` can pull the
needed patch-level quantities before averaging.

## 5. Order of operations around the coupler

The typical order within a coupled time step is:

1. Coupler deposits `forc_*_not_downscaled_grc`, radiation, deposition, river
   forcing, etc. into `atm2lnd_vars`.
2. `downscale_forcings(bounds, num_do_smb_c, filter_do_smb_c, atm2lnd_vars)` runs.
   Every active column now has a correct `forc_*_downscaled_col`.
3. Physics / biogeophysics / biogeochemistry run on columns and patches, reading
   exclusively from `_col` forcings.
4. `lnd2atm_minimal` / `lnd2atm` averages the new state back up to gridcells and
   stages it in `lnd2atm_vars`.
5. Coupler pulls `lnd2atm_vars` and sends it out.

If dynamic landuse or GLC changes the subgrid weights during the step,
`reweight_wrapup` runs between (3) and (4) to keep the averages consistent
(`main/reweightMod.F90:28-56`; see `core/subgrid_utilities.md` §4).

## 6. Key design rules

- **Never read `forc_*_not_downscaled_grc` from physics code.** Use the `_col`
  variant, or the column will silently skip any elevation correction.
- **`check_downscale_consistency` is the final word** on whether the downscaling
  did the right thing for every active column — do not bypass it when wiring in a
  new forcing field.
- **Conservation is enforced at gridcell scale** via `build_normalization`, not at
  the column level. This means the column values for a given field may deviate
  individually from their "pure" downscaled value by a small factor, but their
  weighted mean equals the gridcell mean.
- **lnd2atm averaging is field-specific.** Do not re-use a `c2g` scale combination
  from one field blindly — check `lnd2atm_minimal` / `lnd2atm` for the right
  `c2l_scale_type` and `l2g_scale_type` combination for each output.
