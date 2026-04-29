---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# Photosynthesis and Respiration

## Purpose and Scope

This page documents the leaf-level photosynthesis and plant maintenance-respiration calculations in FATES. It covers the Farquhar-Collatz biochemical model, Ball-Berry and Medlyn stomatal conductance models, the nitrogen-decay scaling of photosynthetic capacity through the canopy, and the Ryan (1991) and Atkin (2017) maintenance-respiration options. For the radiative inputs, see [Radiation Transfer and Albedo](radiation.md). For soil-moisture stress, see [Transpiration and Soil Moisture Stress](transpiration.md). For carbon allocation of the assimilated carbon, see [PARTEH: Plant Allocation System](../plant-physiology/parteh/index.md).

Primary source files:

- `biogeophys/FatesPlantRespPhotosynthMod.F90` (1435 lines at e027a40) — public driver and maintenance-respiration calculations.
- `biogeophys/LeafBiophysicsMod.F90` (2299 lines, NEW) — inner Ci solver (`LeafLayerPhotosynthesis`, `CiFunc`, `CiBisection`), Ball-Berry/Medlyn quadratics, leaf biophysical-rate scaling, btran-application switches.
- `biogeophys/FatesLeafBiophysParamsMod.F90` (NEW) — declares `leafbiophys_params_type`/`lb_params` parameter struct.

## Main Entry Point

The public driver is `FatesPlantRespPhotosynthDrive` in `FatesPlantRespPhotosynthMod.F90`. It is invoked from the host land model by `alm_fates%wrap_photosynthesis(...)`, which is called from the ELM-side file `components/elm/src/biogeophys/CanopyFluxesMod.F90` (line 911 at d40b843) inside the sub-daily `CanopyFluxes` loop. It is **not** a daily call: photosynthesis runs on every host flux timestep (typically 30 min in ELM/CLM) together with the energy balance solver.

The driver walks `(site -> patch -> cohort)`, loops over canopy layers, PFTs, and vertical leaf layers, and for each leaf layer delegates the inner photosynthesis-stomatal solve to `LeafLayerPhotosynthesis` in `LeafBiophysicsMod.F90`.

## Photosynthetic Pathways: C3 and C4

FATES implements both the Farquhar et al. (1980) C3 biochemical model and the Collatz et al. (1992) C4 model, chosen per-PFT by `fates_leaf_c3psn` (1 = C3, 0 = C4). For C3, the gross photosynthesis rate is the smooth minimum of Rubisco-limited (`Ac`), RuBP-limited (`Aj`), and optional triose-phosphate-limited (`Ap`) rates. For C4, the rates are re-expressed with a light-limited term and a CO2-limited term based on `kp25top`. The smooth-min curvature parameters control how sharp the co-limitation blends.

At e027a40 the default 14-PFT array sets PFT 14 (`c4_grass`) to `c3psn = 0` and all others to `1` (`fates_params_default.json:843`).

## Biochemical Rates

Base rates are computed in `LeafLayerBiophysicalRates` (`LeafBiophysicsMod.F90`):

| Rate | Description | Base parameter | Temperature form |
| --- | --- | --- | --- |
| `vcmax` | Maximum carboxylation rate | `vcmax25 * N-scaling` | Arrhenius with high-T deactivation (`ft1_f` * `fth_f`) |
| `jmax` | Maximum electron transport rate | `jmax25 * N-scaling` | Arrhenius with high-T deactivation |
| `kp` | C4 initial slope | `kp25top * N-scaling * Q10` | Q10 |

Temperature sensitivity uses either:

- **Model 1 (non-acclimating):** Arrhenius with deactivation using `vcmaxha`, `vcmaxhd`, `vcmaxse`, `jmaxha`, `jmaxhd`, `jmaxse`. See `LeafBiophysicsMod.F90:1958-1969`.
- **Model 2 (Kumarathunge et al. 2019 acclimating):** Uses two exponential moving averages of canopy temperature.
  - Short-term EMA window: **30 days** by default (`fates_leaf_photo_temp_acclim_timescale = 30.0`, units = `days`, `fates_params_default.json:1958-1963`). This window is also used by the Atkin 2017 leaf maintenance-respiration model when `fates_maintresp_leaf_model = 2`.
  - Long-term EMA ("T_home"): **30 years** by default (`fates_leaf_photo_temp_acclim_thome_time = 30.0`, units = `years`, `fates_params_default.json:1951-1956`).

The model selector is `fates_leaf_photo_tempsens_model` (per HLM namelist `photo_tempsens_model`); only when this is `2` are the EMA windows consulted.

## Nitrogen Scaling Through the Canopy

Photosynthetic capacity declines with cumulative LAI from the canopy top via an exponential nitrogen decay. At e027a40 the decay-coefficient API is **`DecayCoeffVcmax`** (renamed from the earlier `decay_coeff_kn`), and its slope/intercept are now PFT-level parameters rather than hard-coded Lloyd-2010 fits:

```fortran
kn = DecayCoeffVcmax(currentCohort%vcmax25top, &
                     prt_params%leafn_vert_scaler_coeff1(ft), &
                     prt_params%leafn_vert_scaler_coeff2(ft))
nscaler = exp(-kn * cumulative_lai)
```

(`FatesPlantRespPhotosynthMod.F90:551-556`; function definition at `LeafBiophysicsMod.F90:2040`). The two coefficients come from `fates_leafn_vert_scaler_coeff1` (default 0.00963) and `fates_leafn_vert_scaler_coeff2` (`fates_params_default.json:943-957`).

`cumulative_lai` includes all canopy layers above the current leaf layer plus the portion of the current layer above its midpoint (`FatesPlantRespPhotosynthMod.F90:518-537`). `nscaler` multiplies `vcmax25top`, `jmax25top`, and `kp25top`.

Atkin 2017 leaf-respiration vertical scaling uses an analogous parameter pair `fates_maintresp_leaf_vert_scaler_coeff1/2` (`fates_params_default.json:971-983`).

## Stomatal Conductance: Ball-Berry and Medlyn

FATES supports two stomatal models. Selection is now via the **HLM namelist** key `stomatal_model` (1 = Ball-Berry, 2 = Medlyn), dispatched at `FatesInterfaceMod.F90:2116-2122` and stored in `lb_params%stomatal_model` (`LeafBiophysicsMod.F90:211`). The companion namelist key `stomatal_assim_model` selects net vs gross assimilation in the gs equation. **`fates_leaf_stomatal_model` is no longer a parameter-file entry.**

Ball-Berry (Ball et al. 1987):
```
gs = g0 + m * (A * hs / cs)
```
Medlyn et al. (2011):
```
gs = g0 + (1 + g1 / sqrt(D)) * (A / cs)
```

Both models are coupled to photosynthesis through an iterative solution for the intercellular CO2 partial pressure `ci` inside `LeafLayerPhotosynthesis` (`LeafBiophysicsMod.F90:1232-1411`; outer iteration loop at `:1354-1399`). The actual quadratic Ball-Berry / Medlyn solves live inside `CiFunc` (`:901-1079`) and the dedicated `StomatalCondMedlyn` (`:257-357`) / `StomatalCondBallBerry` (`:361-419`) helpers.

### Per-PFT btran-application switches (NEW at e027a40)

Two PFT-level integer parameters control where soil-water stress (`btran`) is applied inside the leaf solve. Constants are declared at `LeafBiophysicsMod.F90:165-178`:

**`fates_leaf_stomatal_btran_model`** (`fates_params_default.json:887-892`, default `1` for all 14 PFTs) — applied to gs0/gs1 in `LeafBiophysicsMod.F90:1997-2030`:

| Value | Constant | Effect |
| --- | --- | --- |
| 0 | `btran_on_gs_none` | Do not scale gs0 or gs1 |
| 1 | `btran_on_gs_gs0` | Scale only the intercept gs0 (API 36 default) |
| 2 | `btran_on_gs_gs1` | Scale only the slope gs1 |
| 3 | `btran_on_gs_gs01` | Scale both intercept and slope |
| 4 | `btran_on_gs_gs2` | Scale the whole non-intercept term (Medlyn-specific; equivalent to `gs_gs1` for Ball-Berry) |
| 5 | `btran_on_gs_gs02` | As 4, but also scale the intercept |

**`fates_leaf_agross_btran_model`** (`fates_params_default.json:831-836`, default `1` for all 14 PFTs) — applied to vcmax/jmax in `LeafBiophysicsMod.F90:1974-1982`:

| Value | Constant | Effect |
| --- | --- | --- |
| 0 | `btran_on_ag_none` | Do not scale vcmax or jmax |
| 1 | `btran_on_ag_vcmax` | Scale only vcmax (API 36 default) |
| 2 | `btran_on_ag_vcmax_jmax` | Scale both vcmax and jmax |

Under defaults, e027a40 reproduces the API-36 behavior (gs0 scaled by `btran`, vcmax scaled by `btran`, jmax untouched). Calibration that changes either switch can drastically alter how soil-water stress propagates through the leaf solve.

### Iteration convergence (REWRITTEN at e027a40)

The `(ci, an, gs)` iteration in `LeafLayerPhotosynthesis` is now a Newton-style root-finder on the residual `fval = ci_input - ci_predicted` returned by `CiFunc`, with a bisection fallback. The outer iteration applies a residual-based update `ci = ci0 - fval` (line 1375), which is functionally a fixed-point step using the residual rather than a strict Newton-secant; either way it is bracketed by the bisection fallback. Source-of-truth at `LeafBiophysicsMod.F90:1325-1399`:

- Outer loop max iterations: `max_iters = 10` (`LeafBiophysicsMod.F90:1330`).
- Convergence tolerance: `ci_tol = 0.5_r8` Pa, declared at `FatesPlantRespPhotosynthMod.F90:295` and passed in via `CiBisection`'s argument list. The tolerance is on the residual `fval` (Pa), **not** on `ci` and **not** on a ppm mole fraction.
- Convergence test (`LeafBiophysicsMod.F90:1380-1383`):

```fortran
if (abs(fval) <= ci_tol ) then
   loop_continue = .false.
   exit iter_loop
end if
```

- When `solve_iter == max_iters` (or the developer flag `force_bisection = .true.` at line 1327), control passes to `CiBisection` (`LeafBiophysicsMod.F90:1085-1224`), a bracketing bisection with its own `max_iters = 200` (line 1129) and the same `ci_tol` test.

The pre-e85d997 fixed-point loop with `niter == 5` cutoff and `2e-6 ppm` tolerance no longer exists at e027a40. The change matters: e027a40's algorithm is provably-convergent (bisection guarantees a bracketed root), where the older fixed-point loop simply quit after five iterations whether it had converged or not.

## Water Stress Multiplier: `btran_eff`

The PFT-level `btran` factor is selected based on whether plant hydraulics is active:

- **Hydraulic mode** (`hlm_use_planthydro == itrue`): `btran_eff = currentCohort%co_hydr%btran`, assigned at `FatesPlantRespPhotosynthMod.F90:512`. The cohort-level `btran` is computed in `FatesPlantHydraulicsMod` from the leaf water potential through the stomatal vulnerability curve.
- **Non-hydraulic mode** (`hlm_use_planthydro == ifalse`): `btran_eff = currentPatch%btran_ft(ft)`, assigned at `FatesPlantRespPhotosynthMod.F90:530`. This is the patch-PFT empirical BTRAN from `EDBtranMod`. See [Transpiration and Soil Moisture Stress](transpiration.md).

After this assignment, `btran_eff` is multiplied by `bstress_sal_ft(ft)` if salinity is active (see below), then handed to `LeafLayerBiophysicalRates` and `LeafLayerPhotosynthesis` as the `btran` argument. The two btran-application switches above then determine where it actually multiplies inside the leaf solve.

### Salinity overlay

When the salinity module is active (`do_fates_salinity == .true.`), an additional multiplicative factor `bstress_sal_ft(ft)` is applied immediately after the BTRAN assignment (`FatesPlantRespPhotosynthMod.F90:543-545`):

```fortran
if (do_fates_salinity) then
   btran_eff = btran_eff * currentPatch%bstress_sal_ft(ft)
endif
```

`bstress_sal_ft` is computed in `FatesBstressMod.F90` (`btran_sal_stress_fates`, lines 31-99). It is independent of soil moisture. Users comparing model output to an observed BTRAN diagnostic should remember that the salinity factor is **not** reflected in the patch-level `btran_pa` output, only in the gs multiplier that photosynthesis sees.

### Form of the stomatal vulnerability curve

In hydraulic mode, `cohort%co_hydr%btran` is generated by the TFS/sigmoidal form at `FatesHydroWTFMod.F90:1885-1912`:

```
ftc = max(min_ftc, 1 / (1 + (psi_eff / p50)^avuln))
```

This is the **Pammenter and Vanderwilligen (1998) sigmoidal form**, **not a Weibull**. A Weibull would be `exp(-(psi/b)^c)`. The distinction matters when tuning `hydr_avuln_gs`: sigmoidal `avuln` controls steepness around `p50`, whereas Weibull shape parameters have different scale/shape interactions. See [Hydraulic Architecture](hydraulics/architecture.md) for the full functional form.

## Maintenance Respiration

### Leaf respiration

FATES offers two leaf dark-respiration models, selected by the HLM namelist `maintresp_leaf_model` (dispatched at `FatesInterfaceMod.F90:2139-2143`).

**Model 1: Ryan (1991).** Base rate `fates_maintresp_leaf_ryan1991_baserate` at 20 C in gC gN-1 s-1. Scaled by top-of-canopy leaf nitrogen density `lnc_top` and the canopy `nscaler`, with a Q10 temperature function using `q10_mr`.

**Model 2: Atkin et al. (2017).** Base rate `fates_maintresp_leaf_atkin2017_baserate` at 25 C in umol CO2 m-2 s-1. Uses the **30-day** exponential moving average of vegetation temperature (`fates_leaf_photo_temp_acclim_timescale`) for acclimation and is parameterized directly per unit leaf area.

The wrapper functions are `LeafLayerMaintenanceRespiration_Ryan_1991` and `LeafLayerMaintenanceRespiration_Atkin_etal_2017`.

### Non-leaf respiration

Live sapwood (stem and coarse root) and fine-root respiration use the common base rate `fates_maintresp_nonleaf_baserate` (default 2.525e-6 gC gN-1 s-1, `fates_params_default.json:1965-1971`) multiplied by a Q10 function (`q10_mr` for live tissue; `q10_froz` for fine roots in frozen soil):

| Tissue | Biomass | Nitrogen | Temperature |
| --- | --- | --- | --- |
| Live stem (sapwood) | `sapw_c_agw` | `sapw_n_agw` | Air temperature |
| Live coarse roots | `sapw_c_bgw` | `sapw_n_bgw` | Soil temperature |
| Fine roots | `fnrt_c` | `fnrt_n` | Soil temperature (weighted by root profile) |

Fine-root respiration is computed layer by layer using the root-fraction distribution and layer-specific soil temperatures.

### Carbon-storage throttling

When the storage pool is depleted, maintenance respiration is throttled to delay C-starvation mortality. The reduction is a function of `frac = storage_c / storage_c_target` and is parameterised by:

- `fates_maintresp_reduction_curvature` — shape of the reduction curve (0 = very curved, 1 = linear)
- `fates_maintresp_reduction_intercept` — maximum throttling at zero storage
- `fates_maintresp_reduction_upthresh` — storage fraction above which no reduction occurs

## Sunlit / Shaded Integration

Photosynthesis is evaluated separately for sunlit and shaded leaves within every `(canopy_layer, PFT, vertical_layer)` triple. The sunlit fraction `f_sun(cl,ft,iv)` comes from the direct-beam transmittance computed in the radiation solver (Norman or two-stream MLPE) and stored on the patch by `FatesSunShadeFracs` (`radiation/FatesRadiationDriveMod.F90:235-448`). The absorbed-PAR profiles `cpatch%ed_parsun_z` and `cpatch%ed_parsha_z` are then constructed at lines 334-339 from `bc_in(s)%solad_parb(ifp,ipar)` and `solai_parb(ifp,ipar)`.

The layer-averaged net assimilation is `an = f_sun * an_sun + (1 - f_sun) * an_sha`. See [Radiation Transfer and Albedo](radiation.md) for the radiation solvers.

## Key Parameters

PFT-indexed arrays at e027a40 are length 14 (was 12 at e85d997).

| Parameter | Units | Description | Source |
| --- | --- | --- | --- |
| `fates_leaf_vcmax25top` | umol CO2 m-2 s-1 | Vcmax at 25 C, canopy top | `fates_params_default.json:915-921` |
| `fates_leaf_jmaxha` | J mol-1 | Jmax activation energy | `:852-858` (43540 all PFTs) |
| `fates_leaf_jmaxhd` | J mol-1 | Jmax deactivation energy | `:859-865` (152040 all PFTs) |
| `fates_leaf_vcmaxha` | J mol-1 | Vcmax activation energy | `:922-928` (65330 all PFTs) |
| `fates_leaf_vcmaxhd` | J mol-1 | Vcmax deactivation energy | `:929-935` (149250 all PFTs) |
| `fates_leaf_stomatal_intercept` | umol H2O m-2 s-1 | g0 | `:894-900` (10000 default; 40000 for C4) |
| `fates_leaf_stomatal_slope_ballberry` | unitless | Ball-Berry slope `m` | `:901-907` (8.0 all PFTs) |
| `fates_leaf_stomatal_slope_medlyn` | kPa^0.5 | Medlyn `g1` | `:908-914` (1.6 to 5.3) |
| `fates_leaf_stomatal_btran_model` | flag (per PFT) | btran-on-gs switch | `:887-892` (default 1) |
| `fates_leaf_agross_btran_model` | flag (per PFT) | btran-on-vcmax/jmax switch | `:831-836` (default 1) |
| `fates_leaf_c3psn` | flag | 1 = C3, 0 = C4 | `:838-844` |
| `fates_leafn_vert_scaler_coeff1/2` | unitless | DecayCoeffVcmax slope/intercept | `:943-957` |
| `fates_maintresp_leaf_ryan1991_baserate` | gC gN-1 s-1 | Leaf MR base (Ryan) | parameter file (per PFT) |
| `fates_maintresp_leaf_atkin2017_baserate` | umol CO2 m-2 s-1 | Leaf MR base (Atkin) | parameter file (per PFT) |
| `fates_maintresp_nonleaf_baserate` | gC gN-1 s-1 | Non-leaf MR base rate | `:1965-1971` (2.525e-6) |
| `fates_leaf_photo_temp_acclim_timescale` | days | Short EMA window (Kumarathunge / Atkin) | `:1958-1963` (30) |
| `fates_leaf_photo_temp_acclim_thome_time` | years | Long EMA window (T_home) | `:1951-1956` (30) |
| `fates_nonhydro_smpso` | **mm** | Soil potential at full stomatal opening | `:1111-1116` (-66000) |
| `fates_nonhydro_smpsc` | **mm** | Soil potential at full stomatal closure | `:1104-1109` (-255000) |
| `fates_hydro_p50_gs` | MPa | Leaf potential at 50% stomatal closure | `:705-711` (-1.5) |
| `fates_hydro_avuln_gs` | unitless | Sigmoidal shape parameter for stomatal vulnerability | `:663-668` (2.5) |

## Source References

- `biogeophys/FatesPlantRespPhotosynthMod.F90:295` — `ci_tol = 0.5_r8` Pa
- `biogeophys/FatesPlantRespPhotosynthMod.F90:510-545` — `btran_eff` assignment (hydraulic and non-hydraulic branches) and salinity overlay
- `biogeophys/FatesPlantRespPhotosynthMod.F90:551-556` — `DecayCoeffVcmax` call and canopy nitrogen scaling
- `biogeophys/LeafBiophysicsMod.F90:165-178` — btran-application integer constants
- `biogeophys/LeafBiophysicsMod.F90:1232-1411` — `LeafLayerPhotosynthesis` (outer iteration loop at `:1354-1399`)
- `biogeophys/LeafBiophysicsMod.F90:1083-1228` — `CiBisection` 200-iteration bracketing fallback (`max_iters` at `:1129`)
- `biogeophys/LeafBiophysicsMod.F90:901-1079` — `CiFunc` residual evaluator
- `biogeophys/LeafBiophysicsMod.F90:1974-2030` — Vcmax/Jmax/gs0/gs1 btran application
- `biogeophys/LeafBiophysicsMod.F90:2040` — `DecayCoeffVcmax` function definition
- `biogeophys/FatesHydroWTFMod.F90:1885-1912` — sigmoidal `ftc_from_psi_tfs` used for stomatal vulnerability
- `main/FatesInterfaceMod.F90:2116-2122, 2139-2143` — HLM namelist dispatch for `stomatal_model` and `maintresp_leaf_model`
- ELM-side `components/elm/src/biogeophys/CanopyFluxesMod.F90` (line 911 at d40b843) — sub-daily invocation of the photosynthesis driver
- `parameter_files/fates_params_default.json:831-836, 887-892, 943-957, 1951-1963` — new/changed parameter defaults at e027a40
