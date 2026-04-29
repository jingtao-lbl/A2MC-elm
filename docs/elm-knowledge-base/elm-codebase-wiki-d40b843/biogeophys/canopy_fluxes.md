---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Surface Turbulent Fluxes and Photosynthesis

This document covers the five flux drivers that solve the surface energy budget for each ELM sub-grid patch type, the Monin-Obukhov aerodynamic machinery they share, and ELM's native Farquhar/Ball-Berry photosynthesis routine. This is the core physics loop of the biogeophysics subsystem and directly sets sensible heat (`H`), latent heat (`LE`), momentum flux (`τ`), and (for vegetated patches) gross primary production (GPP) and stomatal resistance.

Drivers by landunit:

| Driver | File | Called for |
|---|---|---|
| `CanopyFluxes` | `biogeophys/CanopyFluxesMod.F90:63` | Vegetated patches, non-lake non-urban (`filter_nolakeurbanp`) |
| `BareGroundFluxes` | `biogeophys/BareGroundFluxesMod.F90:35` | Non-vegetated patches on soil/crop columns |
| `UrbanFluxes` | `biogeophys/UrbanFluxesMod.F90:49` | Urban landunits (roof, walls, impervious road, pervious road) |
| `LakeFluxes` | `biogeophys/LakeFluxesMod.F90:39` | Deep-lake columns (see [lake.md](lake.md)) |
| `SoilFluxes` | `biogeophys/SoilFluxesMod.F90:39` | Final ground-T update and flux reconciliation after `SoilTemperature` |

Shared infrastructure:

| Module | Purpose |
|---|---|
| `FrictionVelocityMod` (`biogeophys/FrictionVelocityMod.F90`) | Zeng et al. (1998) Monin-Obukhov stability functions; `FrictionVelocity`, `MoninObukIni` |
| `FrictionVelocityType` (`biogeophys/FrictionVelocityType.F90`) | `frictionvel_type` container for `u10`, `va`, `fv`, `vds`, forcing heights, plus new history-output pointers (`num_iter_patch`, `rah_above_patch`, `rah_below_patch`, ...) |
| `PhotosynthesisMod` (`biogeophys/PhotosynthesisMod.F90`) | Farquhar-von Caemmerer-Berry + Ball-Berry leaf solution; ELM-native path |
| `PhotosynthesisType` (`biogeophys/PhotosynthesisType.F90`) | `photosyns_type` container for `vcmax_z`, `ac`, `aj`, `ap`, `ag`, `an`, `gs_mol`, `bbb`, `mbb`, `rssun`, `rssha`, `vcmax25_top_patch` |
| `SurfaceResistanceMod` (`biogeophys/SurfaceResistanceMod.F90`) | Soil-evap resistance factor (`calc_beta_leepielke1992`), leaf boundary-layer coefficient `getlblcef` |
| `SoilMoistStressMod` (`biogeophys/SoilMoistStressMod.F90`) | `calc_root_moist_stress`, which produces `btran` (transpiration wetness factor 0-1) |
| `EnergyFluxType` (`biogeophys/EnergyFluxType.F90:19`) | `energyflux_type` with `btran`, `eflx_sh_veg`, `eflx_lh_tot`, `dlrad`, `ulrad`, ..., plus daily-min `btran_min_patch`, `btran_min_inst_patch` (lines 92-93) |
| `WaterfluxType` (`biogeophys/WaterfluxType.F90:20`) | `waterflux_type` with `qflx_evap_veg`, `qflx_tran_veg`, `qflx_evap_soi`, ... |

## Public subroutines

| Subroutine | Purpose |
|---|---|
| `CanopyFluxes(bounds, num_nolakeurbanp, filter_nolakeurbanp, ...)` (`biogeophys/CanopyFluxesMod.F90:63`) | Newton-Raphson solve of leaf temperature and all associated fluxes (H, LE, momentum) for vegetated patches; calls `Photosynthesis` (or FATES) each iteration |
| `BareGroundFluxes(bounds, num_nolakeurbanp, filter_nolakeurbanp, ...)` (`biogeophys/BareGroundFluxesMod.F90:35`) | Stability-iterated ground-to-atmosphere flux calculation using ground temperature from previous step |
| `UrbanFluxes(bounds, num_nourbanl, filter_nourbanl, ...)` (`biogeophys/UrbanFluxesMod.F90:49`) | Urban-canyon turbulent fluxes (roof, walls, road) |
| `LakeFluxes(bounds, num_lakec, filter_lakec, num_lakep, filter_lakep, ...)` (`biogeophys/LakeFluxesMod.F90:39`) | Lake-surface flux solve with unique roughness-length formulation |
| `SoilFluxes(bounds, num_urbanl, filter_urbanl, num_nolakec, filter_nolakec, ...)` (`biogeophys/SoilFluxesMod.F90:39`) | Updates surface fluxes with the new ground temperature from `SoilTemperature`; redistributes soil evaporation among top layers |
| `FrictionVelocity(lbn, ubn, fn, filtern, displa, z0m, z0h, z0q, obu, iter, ur, um, ugust, ustar, temp1, temp2, temp12m, temp22m, fm, frictionvel_vars)` (`biogeophys/FrictionVelocityMod.F90:38`) | Computes `u*`, `temp1`, `temp2` profile relations using Zeng et al. (1998) stability functions |
| `MoninObukIni(ur, thv, dthv, zldis, z0m, um, obu)` (`biogeophys/FrictionVelocityMod.F90:445`) | Initial guess for Monin-Obukhov length from bulk Richardson number |
| `Photosynthesis(bounds, fn, filterp, esat_tv, eair, oair, cair, rb, btran, dayl_factor, ..., phase)` (`biogeophys/PhotosynthesisMod.F90:212`) | Leaf-level Farquhar + Ball-Berry for one canopy stream (`phase = 'sun'` or `'sha'`) |
| `PhotosynthesisHydraulicStress(...)` | Plant hydraulic stress variant; solves sunlit + shaded jointly with xylem water potential |
| `PhotosynthesisTotal(fn, filterp, ...)` | Vertical integration of per-layer `an_z` to patch-total `psn`, `psn_wc`, `psn_wj`, `psn_wp` |
| `Fractionation(bounds, fn, filterp, ..., c13flag)` | <sup>13</sup>C discrimination when `use_c13 = .true.` |
| `plc(x, ...)` (declared public in `PhotosynthesisMod`) | Vulnerability curve used by hydraulic-stress photosynthesis |

Private helpers in `PhotosynthesisMod`: `hybrid`, `brent`, `ci_func`, plus `_PHS` variants for the hydraulic-stress path. Private helpers in `FrictionVelocityMod`: `StabilityFunc1`, `StabilityFunc2` (Zeng integrated flux-gradient functions).

## The canopy flux Newton-Raphson solve

`CanopyFluxes` (`biogeophys/CanopyFluxesMod.F90:63`) is the longest single subroutine in the biogeophysics layer (1355 lines at `d40b8431`, up from 1312 at `60d9aad`) and follows the CLM4.5/CLM5 formulation. It solves for the leaf temperature `t_veg` that closes

```
f(T_veg) = R_net(T_veg) - H(T_veg) - LE(T_veg) = 0
```

using Newton-Raphson with analytical derivatives on the radiative and surface-humidity terms. The convergence criteria:

- Temperature change `|del|` and `|del2|` both under `dtmin = 0.01` K.
- Leaf energy-flux change `|dele|` under `dlemin = 0.1` W m<sup>-2</sup>.
- Hard cap at `itmax = 41` iterations, minimum `itmin = 3`.
- If `implicit_stress = .true.`, also require `|tau_diff| < dtaumin = 0.01` Pa.

Important in-source design notes:

- **Ground temperature is frozen** at the previous step's `t_grnd(c)` while solving for `t_veg`. This is why `SurfaceAlbedo` is staged one step ahead (see [radiation.md](radiation.md)).
- **Aerodynamic-resistance derivatives** with respect to `T_veg` are ignored in the Jacobian, because `ra` depends on `T_veg` only through the Monin-Obukhov length, which is updated between iterations rather than differentiated.
- **Sunlit/shaded resistances** are combined via area-weighted harmonic mean for the canopy-scale `rs`.

### Iteration outline

The iteration includes a slope-corrected longwave term when `use_finetop_rad = .true.`. At `CanopyFluxesMod.F90:705-708`, the longwave coefficients `bir`, `cir` are divided by `cos(slope_rad)`:

```fortran
if (use_finetop_rad) then
   slope_rad = slope_deg(g) * deg2rad
   bir(p) = bir(p) / cos(slope_rad)
   cir(p) = cir(p) / cos(slope_rad)
endif
```

Likewise the leaf-emitted and ground-reflected longwave inside the iteration (`CanopyFluxesMod.F90:1277-1290`) is divided by `cos(slope_rad)` when the flag is on. Default behavior (flag off) is unchanged.

The iteration structure:

```fortran
ITERATION : do while (itlef <= itmax .and. fn > 0)

   ! 1. Surface layer similarity -> ustar, temp1, temp2
   call FrictionVelocity (begp, endp, fn, filterp, &
        displa, z0mv, z0hv, z0qv, obu, itlef, ur, um, ugust_total, ustar, &
        temp1, temp2, temp12m, temp22m, fm, frictionvel_vars)

   ! 2. Aerodynamic resistances + leaf boundary layer + under-canopy

   ! 3. Photosynthesis / stomatal conductance
   if (use_fates) then
      call alm_fates%wrap_photosynthesis(...)     ! FATES path (CanopyFluxesMod.F90:911)
   else if (use_hydrstress) then
      call PhotosynthesisHydraulicStress(...)     ! couples sunlit+shaded+xylem
   else
      call Photosynthesis(..., 'sun')             ! sunlit stream
      call Photosynthesis(..., 'sha')             ! shaded stream
   end if

   ! 4. Conductance composition and flux closure

   ! 5. Update M-O length from new (theta_v, q_v) gradients
   !    and repeat.
end do ITERATION
```

The FATES `wrap_btran` call site is `CanopyFluxesMod.F90:591`, and `wrap_hydraulics_drive` is at line 1322. The number of iterations performed is now stored on `frictionvel_vars%num_iter_patch` and emitted as the history field `ITER_LND_EBAL_AVG` (see [Mi1](#new-history-output-fields-on-frictionvel_type)).

### Aerodynamic resistance composition

Inside the iteration:

- `ram1 = 1 / (u*^2/u_m)` — aerodynamic resistance for momentum from reference height to canopy.
- `rah(p,1) = 1 / (temp1*u*)` — thermal resistance, atmosphere to canopy top.
- `raw(p,1) = 1 / (temp2*u*)` — moisture resistance, atmosphere to canopy top.
- `rah(p,2) = raw(p,2) = 1 / (csoilcn * uaf)` — under-canopy resistance from canopy air space to ground. `csoilcn` is itself a Sakaguchi & Zeng (2008) canopy-density and stability-weighted blend of bare-soil and dense-canopy coefficients.
- `rb = 1 / (cf * uaf)` — leaf boundary-layer resistance, with `cf = 0.01 / sqrt(uaf * dleaf)`. `dleaf` is PFT-dependent (pulled from `veg_vp%dleaf` or from FATES during dynamics).

At `d40b8431`, several previously-local arrays in `CanopyFluxes` (`obu`, `um`, `uaf`, `ustar`, `taf`, `qaf`, `zeta`, plus the components of `rah`/`raw`) have been moved to module-level type pointers on `frictionvel_type` (`FrictionVelocityType.F90:44-58`), allowing them to be emitted as history. The algebra is unchanged.

The iteration-internal stability parameter is rebuilt each pass from the updated (`tstar`, `qstar`, `thvstar`) and a Businger-form non-dimensional height `zeta`; sign-flip safeguards prevent flip-flopping between stable and unstable branches (`nmozsgn`).

### Leaf energy-balance closure

After `Photosynthesis` returns `rssun`, `rssha` (and writes `gs_mol`, `an`, `ci_z` into `photosyns_vars`), the module assembles heat and moisture conductances `wta`, `wtl`, `wtg`, `wtaq`, `wtlq`, `wtgq`, updates the potential evaporation `efpot`, and splits it between transpiration `qflx_tran_veg` and interception loss `qflx_evap_veg`:

```
efpot = rho_air * wtl * (wtgaq*(qsat_l + dqsat/dT * dT_veg)
                         - wtgq0 * qg - wtaq0 * q_air)
qflx_evap_veg = rpp * efpot
qflx_tran_veg = rppdry * efpot     (when efpot > 0 and btran > 0)
ecidif         = max(0, qflx_evap_veg - qflx_tran_veg - h2ocan/dt)
eflx_sh_veg    = efsh + dc1*wtga*dT_veg + err + erre + hvap*ecidif
```

`ecidif` is the "excess energy" when demanded evaporation exceeds what's in the canopy water store; it is dropped into sensible heat.

### Transpiration wetness factor `btran`

`btran` is computed **before** the canopy iteration inside `CanopyFluxes`, by calling into `SoilMoistStressMod::calc_root_moist_stress`. The default (non-hydrstress) implementation `calc_root_moist_stress_clm45default` does:

```
s_node   = max(h2osoi_liqvol(c,j) / eff_porosity(c,j), 0.01)
smp_node = -sucsat(c,j) * s_node^{-bsw(c,j)}         ! Clapp-Hornberger
smp_node = max(smpsc, smp_node)
rresis(p,j) = min( (eff_porosity/watsat) *
                  (smp_node - smpsc) / (smpso - smpsc), 1)
rootr(p,j)  = rootfr(p,j) * rresis(p,j)
btran(p)    = Sum_j rootr(p,j)                       ! 0 <= btran <= 1
```

`smpso` (soil water potential at full stomatal opening) and `smpsc` (at full closure) are PFT parameters. If `t_soisno(c,j) <= tfrz + tc_stress`, that layer contributes zero. `btran` then scales the Ball-Berry slope and intercept inside `Photosynthesis`, and `rootr` is used to distribute the column-total transpiration sink among soil layers during Richards' equation.

A daily-minimum tracker `btran_min_inst_patch` accumulates the per-step minimum (`EnergyFluxType.F90:551-557`) and `UpdateAccVars` (line 497) snapshots it once per day to `btran_min_patch`, exposed as the history field `BTRAN_DAILY_MIN`. Useful for FATES drought analysis.

### Crop / N-fixer attribute API

At `d40b8431`, the soybean-vs-other dispatch inside `CanopyFluxes` uses the generic `crop()` and `nfixer()` functions instead of hard-coded PFT indices (`CanopyFluxesMod.F90:900-901, 941-942`):

```fortran
! 60d9aad style:
if (veg_pp%itype(p) == nsoybean .or. veg_pp%itype(p) == nsoybeanirrig) then ...

! d40b8431 style:
if (crop(veg_pp%itype(p)) >= 1 .and. nfixer(veg_pp%itype(p)) == 1) then ...
```

`crop()`, `nfixer()`, and `iscft()` live in `pftvarcon` and let any PFT self-identify as a crop / nitrogen fixer / managed crop without referring to specific integer indices. This matters when adding new crop PFTs (CMIP6 LUH2, FATES LUH2). Wiki text that names `nsoybean` indexing is now obsolete.

## Monin-Obukhov similarity — `FrictionVelocityMod`

The scheme implements Zeng et al. (1998, *J. Climate* 11, 2628–2644). `FrictionVelocity` is called each iteration of the canopy or bare-ground loop with the current Obukhov-length-scale estimate. (Comment text at `d40b8431` consistently refers to "Obukhov length scale" rather than "Monin-Obukhov length"; the mathematics is unchanged.)

Key algebra:

```
zeta = zldis / obu                           ! dimensionless height
zetam = 1.574,   zetat = 0.465               ! transition points

! Momentum friction velocity:
if (zeta < -zetam)       ! very unstable, convective-limit correction
   u* = vk * um / ( log(-zetam*obu/z0m)
                    - psi_1(-zetam)
                    + psi_1(z0m/obu)
                    + 1.14 * [(-zeta)^(1/3) - zetam^(1/3)] )

else if (zeta < 0)       ! unstable
   u* = vk * um / ( log(zldis/z0m) - psi_1(zeta) + psi_1(z0m/obu) )

else if (zeta <= 1)      ! stable (Businger)
   u* = vk * um / ( log(zldis/z0m) + 5*zeta - 5*z0m/obu )

else                     ! very stable
   u* = vk * um / ( log(obu/z0m) + 5 - 5*z0m/obu + 5*log(zeta) + zeta - 1 )
end if
```

`StabilityFunc1` and `StabilityFunc2` (private helpers in the same module) are the integrated Paulson (1970) forms for momentum and temperature/humidity. `temp1` and `temp2` returned from this subroutine are the inverses of the resistance kernel for potential temperature and specific humidity, used above to build `rah` and `raw`.

### Obukhov-length initialization

`MoninObukIni` (`biogeophys/FrictionVelocityMod.F90:445`) is called once before the iteration begins to get a first-guess `obu`:

```
rib  = grav * zldis * dthv / (thv * um^2)         ! bulk Richardson
if (rib >= 0)                                      ! stable/neutral
   zeta = rib * log(zldis/z0m) / (1 - 5*min(rib, 0.19))
   zeta = clamp(zeta, 0.01, 2)
else                                               ! unstable
   zeta = rib * log(zldis/z0m)
   zeta = clamp(zeta, -100, -0.01)
obu = zldis / zeta
```

The initial friction-velocity guess is hardcoded `u* = 0.06` m s<sup>-1</sup> and convective velocity `wc = 0.5` m s<sup>-1</sup>.

## ELM-native photosynthesis (`PhotosynthesisMod`)

`Photosynthesis` (`biogeophys/PhotosynthesisMod.F90:212`) is the Farquhar-von Caemmerer-Berry biochemical model coupled to Ball-Berry stomatal conductance, as described in the in-source header (citing Bonan et al. 2011). It is called **once per canopy stream** (sunlit = `phase='sun'` or shaded = `phase='sha'`) from `CanopyFluxes`.

**This subroutine is bypassed when `use_fates = .true.`** — FATES has its own Farquhar/Ball-Berry implementation called through `alm_fates%wrap_photosynthesis` (see `CanopyFluxesMod.F90:911`).

At `d40b8431`, the only material change to `PhotosynthesisMod` is the addition of the `vcmax25_top` write at `PhotosynthesisMod.F90:792-794`, exposed as history field `VCMAX25TOP` (default `inactive`) on `photosyns_type` (`PhotosynthesisType.F90:30, 148, 269-274`). Useful for cross-PFT photosynthesis-capacity diagnostics. Also the `pftvarcon` import list no longer includes `nsoybean`, `nsoybeanirrig`, `nbrdlf_dcd_tmp_shrub`, `npcropmin` (now using the generic crop accessors).

### Rubisco-, RuBP-, and product-limited rates

Inside `ci_func`, for each canopy layer and each iteration of the `ci` hybrid Newton-Secant solver, three potential photosynthesis rates are computed:

```
! C3 plants
ac(p,iv) = vcmax_z(p,iv) * max(ci - cp, 0) / (ci + kc * (1 + oair/ko))         ! Rubisco-limited
aj(p,iv) = je * max(ci - cp, 0) / (4*ci + 8*cp)                                ! RuBP-limited
ap(p,iv) = 3 * tpu_z(p,iv)                                                     ! triose-phosphate limited

! C4 plants
ac(p,iv) = vcmax_z(p,iv)
aj(p,iv) = qe * par_z * 4.6
ap(p,iv) = kp_z(p,iv) * max(ci, 0) / forc_pbot
```

where:
- `vcmax_z` — maximum Rubisco carboxylation rate (umol CO<sub>2</sub> m<sup>-2</sup> s<sup>-1</sup>), temperature-scaled and depth-scaled from canopy-top `vcmax25top`.
- `je` — photosynthetic electron transport rate, from a quadratic co-limitation involving `jmax_z`, absorbed PAR `par_z`, and empirical curvature `theta_psii = 0.7`.
- `cp`, `kc`, `ko` — CO<sub>2</sub> compensation point and Michaelis-Menten constants for CO<sub>2</sub> and O<sub>2</sub>, each Arrhenius-scaled with activation energies `vcmaxha`, `kcha`, `koha`, `cpha`, etc.
- `tpu_z`, `kp_z` — triose-phosphate utilization (C3) and PEP-carboxylase slope (C4).

### Co-limitation

The three rates are merged via two quadratic co-limitations:

```
! First co-limit ac (Rubisco) and aj (RuBP) with curvature theta_cj(p):
theta_cj * ai^2 - (ac + aj)*ai + ac*aj = 0     ->  ai = min(r1, r2)

! Then co-limit ai with ap (product) with curvature theta_ip = 0.95:
theta_ip * ag^2 - (ai + ap)*ag + ai*ap = 0     ->  ag = min(r1, r2)

an(p,iv) = ag(p,iv) - lmr_z    ! subtract leaf maintenance respiration
```

`theta_cj` is PFT-dependent (stored on `photosyns_type`), `theta_ip = 0.95` is a constant.

### Ball-Berry stomatal conductance

Still inside `ci_func`, once net photosynthesis `an` is known, stomatal conductance `gs_mol` is obtained from the quadratic Ball-Berry equation:

```
cs = cair - (1.4 / gb_mol) * an * forc_pbot           ! CO2 at leaf surface
cs * gs^2 + [cs*(gb - bbb) - mbb*an*forc_pbot] * gs
         - gb*(cs*bbb + mbb*an*forc_pbot*rh_can) = 0
```

whose physically-meaningful root `gs_mol = max(r1, r2)` is then used to compute the next `ci`:

```
ci_new = cair - an * forc_pbot * (1.4/gs + 1.6/gb) / (gs * gb / (gs + gb))
```

(rearranged to the residual form `fval = ci - ci_new`). The outer `hybrid` / `brent` solver iterates `ci` until `fval = 0`.

Ball-Berry parameters:
- `bbb` = `bbbopt * btran` — minimum leaf conductance, scaled by soil water stress.
- `mbb` = `mbbopt` — slope; `mbbopt` is PFT-dependent (`veg_vp%mbbopt`, e.g. ~9 for C3 and ~4 for C4).
- `rh_can` — canopy air relative humidity passed in by `CanopyFluxes`.

A consistency check after the solve computes `gs_mol_err = mbb*max(an,0)*hs/cs*forc_pbot + bbb` and prints a warning if it differs from the quadratic root by more than 0.1 μmol H<sub>2</sub>O m<sup>-2</sup> s<sup>-1</sup>.

### Canopy integration

After `Photosynthesis` has written `an(p,iv)` and `gs_mol(p,iv)` for every canopy layer `iv = 1..nrad(p)` and every sunlit/shaded stream, `PhotosynthesisTotal` vertically integrates using the sunlit-fraction profile `fsun_z(p,iv)` that came out of `TwoStream` (see [radiation.md](radiation.md)). This sets:

- `psnsun_patch`, `psnsha_patch` — patch-scale sunlit and shaded gross photosynthesis
- `psn_patch = psnsun + psnsha`
- `psn_wc_patch`, `psn_wj_patch`, `psn_wp_patch` — C3 co-limitation diagnostics
- `rssun_patch`, `rssha_patch` — canopy-scale stomatal resistances (s m<sup>-1</sup>)

These canopy-integrated rates flow onward into the CN/CNP BGC (`psn_to_cpool`) and into the latent-heat split inside `CanopyFluxes` for the next iteration.

## Bare-ground fluxes — `BareGroundFluxes`

`BareGroundFluxes` (`biogeophys/BareGroundFluxesMod.F90:35`) runs for non-vegetated patches on soil/crop columns (selected via the `veg_pp%is_on_soil_col(p)` accessor at `BareGroundFluxesMod.F90:417`, replacing the old `lun_pp%itype(l) == istsoil` style). It shares the stability-iteration structure of `CanopyFluxes` but without a canopy Newton-Raphson on `t_veg`:

- `itmin = 3`, `itmax = 30`.
- Uses the same `FrictionVelocity` / `MoninObukIni` machinery.
- Uses `shr_flux_update_stress` (from `shr_flux_mod`) to iteratively relax the surface stress when `implicit_stress = .true.`.
- Calls `do_soilevap_beta` from `SurfaceResistanceMod` to check whether the Lee-Pielke 1992 evaporation-efficiency factor is active.
- Uses `QSat` (see [canopy_hydrology.md](canopy_hydrology.md)) to rebuild `qsatg`, `dqsatg/dT` at the ground surface each iteration.
- Writes `eflx_sh_grnd`, `qflx_evap_soi`, `taux`, `tauy` straight into `energyflux_vars` / `waterflux_vars`, plus `u10`, `va` diagnostics for dust emission.

## Urban fluxes — `UrbanFluxes`

`UrbanFluxes` (`biogeophys/UrbanFluxesMod.F90:49`) solves turbulent fluxes for urban canyons. Unlike the single-patch vegetated and bare-ground cases, urban landunits have multiple column types (sunwall, shadewall, roof, impervious road, pervious road), each with its own roughness and temperature. The routine shares `FrictionVelocity` with the other drivers but applies it separately for each urban column and then aggregates the urban-landunit-average fluxes. See [urban.md](urban.md) for the column layout and anthropogenic heat handling.

## Lake fluxes — `LakeFluxes`

`LakeFluxes` (`biogeophys/LakeFluxesMod.F90:39`) assumes one PFT per lake column. It has a distinctive roughness-length formulation specific to open water, using `minz0lake`, `fcrit`, `cur0`, `cus`, `curm` from `LakeCon`, and the frozen-lake roughness `z0frzlake`. It runs an **explicit-then-implicit** stress iteration with different `itmax` bounds (`itmax_expl = 4`, `itmax_impl = 30`). Heat transfer through the lake column and freezing/thawing are handled by `LakeTemperatureMod` and `LakeHydrologyMod` — see [lake.md](lake.md) for the full lake physics.

## Ground-flux reconciliation — `SoilFluxes`

`SoilFluxes` (`biogeophys/SoilFluxesMod.F90:39`) runs **after** `SoilTemperature` and applies a single linear correction so that the surface fluxes reported for the time step are consistent with the *new* ground temperature. Key operations:

- Compute the temperature increment `tinc(c) = t_grnd(c) - t_grnd0(c)`.
- Update longwave emission `eflx_lwrad_del` using the new `t_grnd`.
- Redistribute column-total soil evaporation `topsoil_evap_tot` among patches and among the top soil/snow layers, respecting `egsmax` (max allowable supply) and `frac_sno_eff`, `frac_h2osfc`.
- Recompute `eflx_sh_grnd`, `eflx_lh_grnd`, `qflx_evap_soi`, `qflx_evap_tot`.
- Assemble patch-total `eflx_sh_tot = eflx_sh_veg + eflx_sh_grnd`, `eflx_lh_tot`, and `qflx_evap_veg` at the end of the step.

### Slope-corrected ground longwave (`use_finetop_rad`)

When `use_finetop_rad = .true.`, the bare-ground branch of `eflx_soil_grnd` divides the longwave terms by `cos(slope_rad)` (`SoilFluxesMod.F90:287-301`):

```fortran
if (use_finetop_rad) then
   slope_rad = slope_deg(g) * deg2rad
   eflx_soil_grnd(p) = ... &
        - emg(c)*sb*lw_grnd/cos(slope_rad) &
        - emg(c)*sb*t_grnd0(c)**3*(4._r8*tinc(c))/cos(slope_rad) &
        - ...
else
   eflx_soil_grnd(p) = ... &
        - emg(c)*sb*lw_grnd &
        - emg(c)*sb*t_grnd0(c)**3*(4._r8*tinc(c)) &
        - ...
endif
```

The same correction is applied to the vegetated-ground branch (`SoilFluxesMod.F90:437-444`). Default behavior matches the unscaled version.

After `SoilFluxes`, the fluxes seen by the atmosphere coupler for the ending time step are final.

## State containers

### `energyflux_type` (`biogeophys/EnergyFluxType.F90:19`)

Stores (partial list):
- `btran_patch`, `btran2_patch`, `rresis_patch` — transpiration wetness factor and layer resistance (from `SoilMoistStressMod`).
- `btran_min_patch`, `btran_min_inst_patch` — **new** at `d40b8431`: daily minimum transpiration wetness factor (lines 92-93). Accumulator procedures `InitAccBuffer`, `InitAccVars`, `UpdateAccVars` at lines 133-135. History field `BTRAN_DAILY_MIN`.
- `eflx_sh_tot`, `eflx_sh_veg`, `eflx_sh_grnd`, `eflx_sh_snow`, `eflx_sh_h2osfc`, `eflx_sh_soil` — sensible heat components.
- `eflx_lh_tot`, `eflx_lh_vege`, `eflx_lh_vegt`, `eflx_lh_grnd` — latent heat components.
- `eflx_lwrad_net`, `eflx_lwrad_out`, `ulrad`, `dlrad` — longwave energy fluxes.
- `taux_patch`, `tauy_patch` — momentum stress components.
- `eflx_dynbal_dribbler` — annual flux dribbler for dynamic subgrid balancing.

### `waterflux_type` (`biogeophys/WaterfluxType.F90:20`)

Stores (partial list):
- `qflx_evap_tot_patch`, `qflx_evap_veg_patch`, `qflx_evap_soi_patch`, `qflx_evap_can_patch` — evaporation components.
- `qflx_tran_veg_patch` — transpiration.
- `qflx_rain_grnd_patch`, `qflx_snow_grnd_patch`, `qflx_snwcp_ice_patch`, `qflx_snwcp_liq_patch` — precipitation onto the ground.
- `qflx_sub_snow_patch`, `qflx_dew_snow_patch`, `qflx_dew_grnd_patch` — sublimation/dew.
- `qflx_surf_col`, `qflx_drain_col`, `qflx_qrgwl_col` — runoff and drainage (used by `HydrologyDrainageMod`).
- **New at d40b8431** (used by the updated water-balance equation and the `Drainage_To_OCN` path): `qflx_lnd2ocn`, `qflx_h2oocn_drain`, `qflx_from_uphill`, `qflx_to_downhill`, `qflx_ice_runoff_xs`, `qflx_glcice_diag`, `qflx_glcice_frz_diag`.

### New history-output fields on `frictionvel_type`

Several previously-local arrays in `CanopyFluxes` and `BareGroundFluxes` have been moved to module-level type pointers on `frictionvel_type` (`FrictionVelocityType.F90:44-58`), allowing them to be emitted as history without changing computation:

```
real(r8), pointer :: num_iter_patch    (:)   ! number of iterations per CanopyFluxes solve
real(r8), pointer :: rah_above_patch   (:)
real(r8), pointer :: rah_below_patch   (:)
real(r8), pointer :: raw_above_patch   (:)
real(r8), pointer :: raw_below_patch   (:)
real(r8), pointer :: ustar_patch, um_patch, uaf_patch, taf_patch, qaf_patch (:)
real(r8), pointer :: obu_patch         (:)   ! Obukhov length scale [m]
real(r8), pointer :: zeta_patch        (:)   ! dimensionless stability parameter
real(r8), pointer :: vpd_patch         (:)   ! kPa
```

History fields (`FrictionVelocityType.F90:240-304`): `ITER_LND_EBAL_AVG`, `RAH_ABOVE`, `RAH_BELOW`, `RAW_ABOVE`, `RAW_BELOW`, plus the rest (most default `inactive`). Use sites in `CanopyFluxes` write through `frictionvel_vars%rah_above_patch(p)` etc. Function: pure history/diagnostic; no behavior change.

### `photosyns_type` (`biogeophys/PhotosynthesisType.F90`)

Stores per canopy layer:
- `ac_patch`, `aj_patch`, `ap_patch`, `ag_patch`, `an_patch` — Rubisco, RuBP, product, co-limited, and net CO<sub>2</sub> assimilation rates.
- `vcmax_z_patch`, `tpu_z_patch`, `kp_z_patch` — temperature- and canopy-depth-scaled kinetic parameters.
- `vcmax25_top_patch` — **new** at `d40b8431`: top-canopy aggregate, history field `VCMAX25TOP` (`PhotosynthesisType.F90:30, 148, 269-274`).
- `gs_mol_patch`, `rssun_patch`, `rssha_patch` — stomatal conductance and sunlit/shaded resistances.
- `bbb_patch`, `mbb_patch` — Ball-Berry parameters after `btran` scaling.
- `cp_patch`, `kc_patch`, `ko_patch`, `qe_patch`, `theta_cj_patch` — Farquhar kinetic constants.
- `psnsun_patch`, `psnsha_patch`, `psn_patch`, `psn_wc_patch`, `psn_wj_patch`, `psn_wp_patch` — integrated GPP and limitation diagnostics.
- `c3flag_patch` — true for C3, false for C4.

`photosyns_vars_TimeStepInit` resets the time-step-scoped fields at the start of each canopy-flux call. The `is_on_soil_col`/`is_on_crop_col` accessors are used to gate `vcmax25_top` initialization (`PhotosynthesisType.F90:458, 484`).

## Cross-links

- The `btran` factor and root-weighted transpiration sink feed into `SoilHydrology` (Richards' equation) in [soil_hydrology.md](soil_hydrology.md).
- `wind_speed0`, `va`, `u10` from `frictionvel_type` drive the dust emission in `AerosolMod` (see [aerosol_and_erosion.md](aerosol_and_erosion.md)) and sea-salt in the atmosphere coupler.
- The FATES path replaces `Photosynthesis` / `PhotosynthesisHydraulicStress`, but still uses `FrictionVelocity`, the Newton-Raphson `t_veg` solve, and `SoilFluxes` — i.e. the entire turbulent-flux machinery in this document applies to FATES runs.
- `sabv`, `sabg`, `sabg_lyr` from [radiation.md](radiation.md) enter `CanopyFluxes` and `BareGroundFluxes` as the driving `R_net` terms.
- Canopy interception `h2ocan` referenced here (and set by [canopy_hydrology.md](canopy_hydrology.md)) caps the interception-evaporation flux in `CanopyFluxes`.
- `BTRAN_DAILY_MIN` (from `EnergyFluxType%UpdateAccVars`) is a calibration-relevant drought diagnostic for the Kougarok use case (see `use_cases/Kougarok/`).
