---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

# Photosynthesis and Respiration

## Purpose and Scope

This page documents the leaf-level photosynthesis and plant maintenance-respiration calculations in FATES. It covers the Farquhar-Collatz biochemical model, Ball-Berry and Medlyn stomatal conductance models, the nitrogen-decay scaling of photosynthetic capacity through the canopy, and the Ryan (1991) and Atkin (2017) maintenance-respiration options. For the radiative inputs, see [Radiation Transfer and Albedo](radiation.md). For soil-moisture stress, see [Transpiration and Soil Moisture Stress](transpiration.md). For carbon allocation of the assimilated carbon, see [PARTEH: Plant Allocation System](../plant-physiology/parteh/index.md).

Primary source file: `biogeophys/FatesPlantRespPhotosynthMod.F90`.

## Main Entry Point

The public driver is `FatesPlantRespPhotosynthDrive` (`FatesPlantRespPhotosynthMod.F90:118-960`). It is invoked from the host land model by `alm_fates%wrap_photosynthesis(...)`, which is called from `elm/src/biogeophys/CanopyFluxesMod.F90:880` inside the sub-daily `CanopyFluxes` loop. It is **not** a daily call: photosynthesis runs on every host flux timestep (typically 30 min in ELM/CLM) together with the energy balance solver.

The driver walks `(site → patch → cohort)`, loops over canopy layers, PFTs, and vertical leaf layers, and for each leaf layer solves for sunlit and shaded fluxes.

## Photosynthetic Pathways: C3 and C4

FATES implements both the Farquhar et al. (1980) C3 biochemical model and the Collatz et al. (1992) C4 model, chosen per-PFT by `fates_leaf_c3psn` (1 = C3, 0 = C4). For C3, the gross photosynthesis rate is the smooth minimum of Rubisco-limited (`Ac`), RuBP-limited (`Aj`), and optional triose-phosphate-limited (`Ap`) rates. For C4, the rates are re-expressed with a light-limited term and a CO₂-limited term based on `kp25top`. The smooth-min curvature parameters `theta_cj_c3` and `theta_cj_c4` (in `EDParamsMod.F90`) control how sharp the co-limitation blends.

## Biochemical Rates

Base rates are computed in `LeafLayerBiophysicalRates`:

| Rate | Description | Base parameter | Temperature form |
| --- | --- | --- | --- |
| `vcmax_z` | Maximum carboxylation rate | `vcmax25top × N-scaling` | Arrhenius with high-T deactivation |
| `jmax_z` | Maximum electron transport rate | `jmax25top × N-scaling` | Arrhenius with high-T deactivation |
| `kp_z` | C4 initial slope | `kp25top × N-scaling` | Arrhenius |

Temperature sensitivity uses either:

- **Model 1 (non-acclimating):** Arrhenius with deactivation using `vcmaxha`, `vcmaxhd`, `vcmaxse`, `jmaxha`, `jmaxhd`, `jmaxse`.
- **Model 2 (Kumarathunge et al. 2019 acclimating):** uses a 10-day and a multi-year exponential moving average of canopy temperature to acclimate the activation/deactivation parameters.

Selection is via `photo_tempsens_model`. Michaelis-Menten constants and the CO₂ compensation point are evaluated once per patch and timestep in `GetCanopyGasParameters` from Bernacchi et al. (2001, 2003).

## Nitrogen Scaling Through the Canopy

Photosynthetic capacity declines with cumulative LAI from the canopy top via an exponential nitrogen decay. The decay coefficient is derived from `vcmax25top` through `decay_coeff_kn` (Lloyd et al. 2010):

```fortran
kn = decay_coeff_kn(ft, currentCohort%vcmax25top)
nscaler = exp(-kn * cumulative_lai)
```
(`FatesPlantRespPhotosynthMod.F90:492-500`).

`cumulative_lai` includes all canopy layers above the current leaf layer plus the portion of the current layer above its midpoint (lines 480-482). `nscaler` multiplies `vcmax25top`, `jmax25top`, and `kp25top`.

## Stomatal Conductance: Ball-Berry and Medlyn

FATES supports two stomatal models, chosen by the integer parameter `fates_leaf_stomatal_model` (1 = Ball-Berry, 2 = Medlyn). Both models are coupled to photosynthesis through an iterative solution for the intercellular CO₂ mole fraction `co2_inter_c`.

Ball-Berry (Ball et al. 1987):
```
gs = g0 + m * (A * hs / cs)
```
Medlyn et al. (2011):
```
gs = g0 + (1 + g1 / sqrt(D)) * (A / cs)
```
Here `g0 = stomatal_intercept_btran` is the stress-scaled intercept (`g0 = fates_leaf_stomatal_intercept × btran_eff`), `m = bb_slope(ft)`, `g1 = medlyn_slope(ft)`, `hs` is leaf-surface relative humidity, and `D` is leaf-to-air vapor pressure deficit. The implementations are at `FatesPlantRespPhotosynthMod.F90:1337-1355`.

### Iteration convergence

The `(ci, an, gs)` iteration in `LeafLayerPhotosynthesis` runs in the `iter_loop` at lines 1098-1370 and exits using the following test (lines 1366-1369):

```fortran
if ((abs(co2_inter_c - co2_inter_c_old)/can_press*1.e06_r8 <=  2.e-06_r8) &
     .or. niter == 5) then
   loop_continue = .false.
end if
```

The tolerance is **`2 × 10⁻⁶` mole fraction (ppm), not `0.01 Pa`**. The maximum iteration count is **`niter == 5`, not 10**. A stale comment just above the exit test still reads "at least ten iterations (niter=10) are completed"; disregard the comment — the enforced limit is 5. If the solver has not converged after five iterations, the final estimates of `gs`, `co2_inter_c`, and `leaf_co2_ppress` are taken as-is (lines 1375-1383).

## Water Stress Multiplier: `btran_eff`

The stomatal intercept is scaled by a soil moisture stress factor `btran_eff` before the iteration starts:

- **Non-hydraulic mode** (`hlm_use_planthydro == ifalse`): `btran_eff = cpatch%btran_ft(ft)`, assigned at `FatesPlantRespPhotosynthMod.F90:475`. This is the patch-PFT empirical BTRAN from `EDBtranMod`. See [Transpiration and Soil Moisture Stress](transpiration.md).
- **Hydraulic mode** (`hlm_use_planthydro == itrue`): `btran_eff = cohort%co_hydr%btran`, where `co_hydr%btran = wkf_plant(stomata_p_media,ft)%p%ftc_from_psi(psi_ag(1))` is computed in `FatesPlantHydraulicsMod` from the cohort leaf water potential. See [Plant Hydraulics](hydraulics/index.md).

### Salinity overlay

When the salinity module is active (`do_fates_salinity == .true.`), an additional multiplicative factor `bstress_sal_ft(ft)` is applied immediately after the BTRAN assignment (`FatesPlantRespPhotosynthMod.F90:488-490`):

```fortran
if (do_fates_salinity) then
   btran_eff = btran_eff * currentPatch%bstress_sal_ft(ft)
endif
```

`bstress_sal_ft` is computed in `FatesBstressMod.F90`. It is independent of soil moisture. Users comparing model output to an observed BTRAN diagnostic should remember that the salinity factor is **not** reflected in the patch-level `btran_pa` output, only in the gs multiplier that photosynthesis sees.

### Form of the stomatal vulnerability curve

In hydraulic mode, `cohort%co_hydr%btran` is generated by the TFS/sigmoidal form at `FatesHydroWTFMod.F90:1727-1738`:

```
ftc = max(min_ftc, 1 / (1 + (ψ_eff / p50)^avuln))
```

This is the **Pammenter-Vanderwilligen (1998) sigmoidal form**, **not a Weibull**. A Weibull would be `exp(-(ψ/b)^c)`. The distinction matters when tuning `hydr_avuln_gs`: sigmoidal `avuln` controls steepness around `p50`, whereas Weibull shape parameters have different scale/shape interactions. See [Hydraulic Architecture](hydraulics/architecture.md) for the full functional form.

## Maintenance Respiration

### Leaf respiration

FATES offers two leaf dark-respiration models, selected by `fates_maintresp_leaf_model`.

**Model 1: Ryan (1991).** Base rate `fates_maintresp_leaf_ryan1991_baserate` at 20 °C in gC gN⁻¹ s⁻¹. Scaled by top-of-canopy leaf nitrogen density `lnc_top` and the canopy `nscaler`, with a Q10 temperature function using `q10_mr`.

**Model 2: Atkin et al. (2017).** Base rate `fates_maintresp_leaf_atkin2017_baserate` at 25 °C in μmol CO₂ m⁻² s⁻¹. Uses the 10-day exponential moving average of vegetation temperature for acclimation and is parameterized directly per unit leaf area.

The wrapper functions are `LeafLayerMaintenanceRespiration_Ryan_1991` and `LeafLayerMaintenanceRespiration_Atkin_etal_2017`.

### Non-leaf respiration

Live sapwood (stem and coarse root) and fine-root respiration use the common base rate `fates_maintresp_nonleaf_baserate` multiplied by a Q10 function (`q10_mr` for live tissue; `q10_froz` for fine roots in frozen soil):

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

Implementation: `FatesPlantRespPhotosynthMod.F90:413-424`.

## Sunlit / Shaded Integration

Photosynthesis is evaluated separately for sunlit and shaded leaves within every `(canopy_layer, PFT, vertical_layer)` triple. The sunlit fraction `f_sun(cl,ft,iv)` comes from the direct-beam extinction coefficient computed in the Norman radiation solver (see [Radiation Transfer and Albedo](radiation.md)):

- **Sunlit leaves** absorb both direct and diffuse PAR (`ed_parsun_z`).
- **Shaded leaves** absorb only diffuse PAR (`ed_parsha_z`).

The layer-averaged net assimilation is `an = f_sun * an_sun + (1 - f_sun) * an_sha`. The vertical structure of these profiles is stored on the patch.

## Key Parameters

| Parameter | Units | Description | Source line(s) |
| --- | --- | --- | --- |
| `fates_leaf_vcmax25top` | μmol CO₂ m⁻² s⁻¹ | Maximum carboxylation rate at 25 °C, canopy top | `fates_params_default.cdl:368-370` |
| `fates_leaf_jmaxha` | J mol⁻¹ | Activation energy for Jmax | `fates_params_default.cdl:344-346` |
| `fates_leaf_jmaxhd` | J mol⁻¹ | Deactivation energy for Jmax | `fates_params_default.cdl:347-349` |
| `fates_leaf_vcmaxha` | J mol⁻¹ | Activation energy for Vcmax | `fates_params_default.cdl:371-373` |
| `fates_leaf_vcmaxhd` | J mol⁻¹ | Deactivation energy for Vcmax | `fates_params_default.cdl:374-376` |
| `fates_leaf_stomatal_intercept` | μmol H₂O m⁻² s⁻¹ | `g0` | `fates_params_default.cdl:359-361` |
| `fates_leaf_stomatal_slope_ballberry` | unitless | Ball-Berry slope `m` | `fates_params_default.cdl:362-364` |
| `fates_leaf_stomatal_slope_medlyn` | kPa^0.5 | Medlyn `g1` | `fates_params_default.cdl:365-367` |
| `fates_leaf_stomatal_model` | flag | 1 = Ball-Berry, 2 = Medlyn | `EDParamsMod.F90:185` |
| `fates_leaf_c3psn` | flag | 1 = C3, 0 = C4 | `fates_params_default.cdl:341-343` |
| `fates_maintresp_leaf_ryan1991_baserate` | gC gN⁻¹ s⁻¹ | Leaf MR base (Ryan) | `fates_params_default.cdl:383-385` |
| `fates_maintresp_leaf_atkin2017_baserate` | μmol CO₂ m⁻² s⁻¹ | Leaf MR base (Atkin) | `fates_params_default.cdl:380-382` |
| `fates_maintresp_nonleaf_baserate` | gC gN⁻¹ s⁻¹ | Non-leaf MR base rate | `EDParamsMod.F90:61` |
| `fates_q10_mr` | unitless | Q10 for maintenance respiration | `EDParamsMod.F90:134` |
| `fates_nonhydro_smpso` | **mm** | Soil potential at full stomatal opening | `fates_params_default.cdl:440-442` |
| `fates_nonhydro_smpsc` | **mm** | Soil potential at full stomatal closure | `fates_params_default.cdl:437-439` |
| `fates_hydro_p50_gs` | MPa | Leaf potential at 50% stomatal closure | `fates_params_default.cdl:284-304` |
| `fates_hydro_avuln_gs` | unitless | Sigmoidal shape parameter for stomatal vulnerability | `fates_params_default.cdl:284-304` |

## Source References

- `biogeophys/FatesPlantRespPhotosynthMod.F90:76, 118-155, 960` — public driver
- `biogeophys/FatesPlantRespPhotosynthMod.F90:475, 488-490` — `btran_eff` assignment and salinity overlay
- `biogeophys/FatesPlantRespPhotosynthMod.F90:492-500` — canopy nitrogen scaling
- `biogeophys/FatesPlantRespPhotosynthMod.F90:1098-1370` — inner photosynthesis-stomatal iteration
- `biogeophys/FatesPlantRespPhotosynthMod.F90:1337-1355` — Ball-Berry and Medlyn quadratic solves
- `biogeophys/FatesPlantRespPhotosynthMod.F90:1366-1370` — iteration exit test (tolerance `2e-6 ppm`, `niter == 5`)
- `biogeophys/FatesHydroWTFMod.F90:1727-1738` — sigmoidal `ftc_from_psi` used for stomatal vulnerability
- `elm/src/biogeophys/CanopyFluxesMod.F90:880` — sub-daily invocation of the photosynthesis driver
- `parameter_files/fates_params_default.cdl:341-442`, `main/EDParamsMod.F90:61-186` — parameter declarations
