---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Surface Turbulent Fluxes and Photosynthesis

This document covers the five flux drivers that solve the surface energy budget for each ELM sub-grid patch type, the Monin-Obukhov aerodynamic machinery they share, and ELM's native Farquhar/Ball-Berry photosynthesis routine. This is the core physics loop of the biogeophysics subsystem and directly sets sensible heat (`H`), latent heat (`LE`), momentum flux (`τ`), and (for vegetated patches) gross primary production (GPP) and stomatal resistance.

Drivers by landunit:

| Driver | File | Called for |
|---|---|---|
| `CanopyFluxes` | `biogeophys/CanopyFluxesMod.F90:61` | Vegetated patches, non-lake non-urban (`filter_nolakeurbanp`) |
| `BareGroundFluxes` | `biogeophys/BareGroundFluxesMod.F90:35` | Non-vegetated patches on soil/crop columns |
| `UrbanFluxes` | `biogeophys/UrbanFluxesMod.F90:49` | Urban landunits (roof, walls, impervious road, pervious road) |
| `LakeFluxes` | `biogeophys/LakeFluxesMod.F90:39` | Deep-lake columns (see [lake.md](lake.md)) |
| `SoilFluxes` | `biogeophys/SoilFluxesMod.F90:38` | Final ground-T update and flux reconciliation after `SoilTemperature` |

Shared infrastructure:

| Module | Purpose |
|---|---|
| `FrictionVelocityMod` (`biogeophys/FrictionVelocityMod.F90`) | Zeng et al. (1998) Monin-Obukhov stability functions; `FrictionVelocity`, `MoninObukIni` |
| `FrictionVelocityType` (`biogeophys/FrictionVelocityType.F90`) | `frictionvel_type` container for `u10`, `va`, `fv`, `vds`, forcing heights |
| `PhotosynthesisMod` (`biogeophys/PhotosynthesisMod.F90`) | Farquhar-von Caemmerer-Berry + Ball-Berry leaf solution; ELM-native path |
| `PhotosynthesisType` (`biogeophys/PhotosynthesisType.F90`) | `photosyns_type` container for `vcmax_z`, `ac`, `aj`, `ap`, `ag`, `an`, `gs_mol`, `bbb`, `mbb`, `rssun`, `rssha` |
| `SurfaceResistanceMod` (`biogeophys/SurfaceResistanceMod.F90`) | Soil-evap resistance factor (`calc_beta_leepielke1992`), leaf boundary-layer coefficient `getlblcef` |
| `SoilMoistStressMod` (`biogeophys/SoilMoistStressMod.F90`) | `calc_root_moist_stress`, which produces `btran` (transpiration wetness factor 0-1) |
| `EnergyFluxType` (`biogeophys/EnergyFluxType.F90:19`) | `energyflux_type` with `btran`, `eflx_sh_veg`, `eflx_lh_tot`, `dlrad`, `ulrad`, ... |
| `WaterfluxType` (`biogeophys/WaterfluxType.F90:20`) | `waterflux_type` with `qflx_evap_veg`, `qflx_tran_veg`, `qflx_evap_soi`, ... |

## Public subroutines

| Subroutine | Purpose |
|---|---|
| `CanopyFluxes(bounds, num_nolakeurbanp, filter_nolakeurbanp, ...)` (`biogeophys/CanopyFluxesMod.F90:61`) | Newton-Raphson solve of leaf temperature and all associated fluxes (H, LE, momentum) for vegetated patches; calls `Photosynthesis` (or FATES) each iteration |
| `BareGroundFluxes(bounds, num_nolakeurbanp, filter_nolakeurbanp, ...)` (`biogeophys/BareGroundFluxesMod.F90:35`) | Stability-iterated ground-to-atmosphere flux calculation using ground temperature from previous step |
| `UrbanFluxes(bounds, num_nourbanl, filter_nourbanl, ...)` (`biogeophys/UrbanFluxesMod.F90:49`) | Urban-canyon turbulent fluxes (roof, walls, road) |
| `LakeFluxes(bounds, num_lakec, filter_lakec, num_lakep, filter_lakep, ...)` (`biogeophys/LakeFluxesMod.F90:39`) | Lake-surface flux solve with unique roughness-length formulation |
| `SoilFluxes(bounds, num_urbanl, filter_urbanl, num_nolakec, filter_nolakec, ...)` (`biogeophys/SoilFluxesMod.F90:38`) | Updates surface fluxes with the new ground temperature from `SoilTemperature`; redistributes soil evaporation among top layers |
| `FrictionVelocity(lbn, ubn, fn, filtern, displa, z0m, z0h, z0q, obu, iter, ur, um, ugust, ustar, temp1, temp2, temp12m, temp22m, fm, frictionvel_vars)` (`biogeophys/FrictionVelocityMod.F90:38`) | Computes `u*`, `temp1`, `temp2` profile relations using Zeng et al. (1998) stability functions |
| `MoninObukIni(ur, thv, dthv, zldis, z0m, um, obu)` (`biogeophys/FrictionVelocityMod.F90:445`) | Initial guess for Monin-Obukhov length from bulk Richardson number |
| `Photosynthesis(bounds, fn, filterp, esat_tv, eair, oair, cair, rb, btran, dayl_factor, ..., phase)` (`biogeophys/PhotosynthesisMod.F90:212`) | Leaf-level Farquhar + Ball-Berry for one canopy stream (`phase = 'sun'` or `'sha'`) |
| `PhotosynthesisHydraulicStress(...)` (`biogeophys/PhotosynthesisMod.F90:1575`) | Plant hydraulic stress variant; solves sunlit + shaded jointly with xylem water potential |
| `PhotosynthesisTotal(fn, filterp, ...)` (`biogeophys/PhotosynthesisMod.F90:973`) | Vertical integration of per-layer `an_z` to patch-total `psn`, `psn_wc`, `psn_wj`, `psn_wp` |
| `Fractionation(bounds, fn, filterp, ..., c13flag)` (`biogeophys/PhotosynthesisMod.F90:1063`) | <sup>13</sup>C discrimination when `use_c13 = .true.` |
| `plc(x, ...)` (declared public at `PhotosynthesisMod.F90:56`) | Vulnerability curve used by hydraulic-stress photosynthesis |

Private helpers in `PhotosynthesisMod`: `hybrid` (`PhotosynthesisMod.F90:1139`), `brent` (`PhotosynthesisMod.F90:1257`), `ci_func` (`PhotosynthesisMod.F90:1448`), plus `_PHS` variants for the hydraulic-stress path. Private helpers in `FrictionVelocityMod`: `StabilityFunc1`, `StabilityFunc2` (Zeng integrated flux-gradient functions).

## The canopy flux Newton-Raphson solve

`CanopyFluxes` (`biogeophys/CanopyFluxesMod.F90:61`) is the longest single subroutine in the biogeophysics layer and follows the CLM4.5/CLM5 formulation described in the in-source comments at `CanopyFluxesMod.F90:65-90`. It solves for the leaf temperature `t_veg` that closes

```
f(T_veg) = R_net(T_veg) - H(T_veg) - LE(T_veg) = 0
```

using Newton-Raphson with analytical derivatives on the radiative and surface-humidity terms. The convergence criteria (`CanopyFluxesMod.F90:87-90`):

- Temperature change `|del|` and `|del2|` both under `dtmin = 0.01` K (`CanopyFluxesMod.F90:137`).
- Leaf energy-flux change `|dele|` under `dlemin = 0.1` W m<sup>-2</sup> (`CanopyFluxesMod.F90:136`).
- Hard cap at `itmax = 41` iterations (`CanopyFluxesMod.F90:139`), minimum `itmin = 3`.
- If `implicit_stress = .true.`, also require `|tau_diff| < dtaumin = 0.01` Pa (`CanopyFluxesMod.F90:138`).

Important in-source design notes:

- **Ground temperature is frozen** at the previous step's `t_grnd(c)` while solving for `t_veg`. This is why `SurfaceAlbedo` is staged one step ahead (see [radiation.md](radiation.md)).
- **Aerodynamic-resistance derivatives** with respect to `T_veg` are ignored in the Jacobian (`CanopyFluxesMod.F90:79-80`), because `ra` depends on `T_veg` only through the Monin-Obukhov length, which is updated between iterations rather than differentiated.
- **Sunlit/shaded resistances** are combined via area-weighted harmonic mean for the canopy-scale `rs` (`CanopyFluxesMod.F90:81`).

### Iteration outline

The iteration begins at `CanopyFluxesMod.F90:764`:

```fortran
ITERATION : do while (itlef <= itmax .and. fn > 0)

   ! 1. Surface layer similarity -> ustar, temp1, temp2
   call FrictionVelocity (begp, endp, fn, filterp, &
        displa, z0mv, z0hv, z0qv, obu, itlef, ur, um, ugust_total, ustar, &
        temp1, temp2, temp12m, temp22m, fm, frictionvel_vars)

   ! 2. Aerodynamic resistances + leaf boundary layer + under-canopy
   !    (see CanopyFluxesMod.F90:784-855 for the algebra)

   ! 3. Photosynthesis / stomatal conductance
   if (use_fates) then
      call alm_fates%wrap_photosynthesis(...)     ! FATES path
   else if (use_hydrstress) then
      call PhotosynthesisHydraulicStress(...)     ! couples sunlit+shaded+xylem
   else
      call Photosynthesis(..., 'sun')             ! sunlit stream
      ! ...
      call Photosynthesis(..., 'sha')             ! shaded stream
   end if

   ! 4. Conductance composition and flux closure (CanopyFluxesMod.F90:937-1064)

   ! 5. Update M-O length from new (theta_v, q_v) gradients
   !    and repeat. See CanopyFluxesMod.F90:1108-1141.
end do ITERATION
```

### Aerodynamic resistance composition

Inside the iteration (`CanopyFluxesMod.F90:784-855`):

- `ram1 = 1 / (u*^2/u_m)` — aerodynamic resistance for momentum from reference height to canopy.
- `rah(p,1) = 1 / (temp1*u*)` — thermal resistance, atmosphere to canopy top.
- `raw(p,1) = 1 / (temp2*u*)` — moisture resistance, atmosphere to canopy top.
- `rah(p,2) = raw(p,2) = 1 / (csoilcn * uaf)` — under-canopy resistance from canopy air space to ground. `csoilcn` is itself a Sakaguchi & Zeng (2008) canopy-density and stability-weighted blend of bare-soil and dense-canopy coefficients (`CanopyFluxesMod.F90:816-843`).
- `rb = 1 / (cf * uaf)` — leaf boundary-layer resistance, with `cf = 0.01 / sqrt(uaf * dleaf)` (`CanopyFluxesMod.F90:812-814`). `dleaf` is PFT-dependent (pulled from `veg_vp%dleaf` or from FATES during dynamics).

The iteration-internal stability parameter is rebuilt each pass from the updated (`tstar`, `qstar`, `thvstar`) and a Businger-form non-dimensional height `zeta` (`CanopyFluxesMod.F90:1118-1137`); sign-flip safeguards prevent flip-flopping between stable and unstable branches (`nmozsgn`).

### Leaf energy-balance closure

After `Photosynthesis` returns `rssun`, `rssha` (and writes `gs_mol`, `an`, `ci_z` into `photosyns_vars`), the module assembles heat and moisture conductances `wta`, `wtl`, `wtg`, `wtaq`, `wtlq`, `wtgq`, updates the potential evaporation `efpot`, and splits it between transpiration `qflx_tran_veg` and interception loss `qflx_evap_veg` (`CanopyFluxesMod.F90:1071-1093`):

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

`btran` is computed **before** the canopy iteration inside `CanopyFluxes` (roughly `CanopyFluxesMod.F90:460-520`), by calling into `SoilMoistStressMod::calc_root_moist_stress`. The default (non-hydrstress) implementation is `calc_root_moist_stress_clm45default` (`biogeophys/SoilMoistStressMod.F90:306`):

```
s_node   = max(h2osoi_liqvol(c,j) / eff_porosity(c,j), 0.01)
smp_node = -sucsat(c,j) * s_node^{-bsw(c,j)}         ! Clapp-Hornberger
smp_node = max(smpsc, smp_node)
rresis(p,j) = min( (eff_porosity/watsat) *
                  (smp_node - smpsc) / (smpso - smpsc), 1)
rootr(p,j)  = rootfr(p,j) * rresis(p,j)
btran(p)    = Sum_j rootr(p,j)                       ! 0 <= btran <= 1
```

`smpso` (soil water potential at full stomatal opening) and `smpsc` (at full closure) are PFT parameters. If `t_soisno(c,j) <= tfrz + tc_stress`, that layer contributes zero. `btran` then scales the Ball-Berry slope and intercept inside `Photosynthesis` (see below), and `rootr` is used to distribute the column-total transpiration sink among soil layers during Richards' equation.

## Monin-Obukhov similarity — `FrictionVelocityMod`

The scheme implements Zeng et al. (1998, *J. Climate* 11, 2628–2644). `FrictionVelocity` is called each iteration of the canopy or bare-ground loop with the current Monin-Obukhov length estimate.

Key algebra (`biogeophys/FrictionVelocityMod.F90:128-143`):

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

### Monin-Obukhov initialization

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

The initial friction-velocity guess is hardcoded `u* = 0.06` m s<sup>-1</sup> and convective velocity `wc = 0.5` m s<sup>-1</sup> (`FrictionVelocityMod.F90:476-477`).

## ELM-native photosynthesis (`PhotosynthesisMod`)

`Photosynthesis` (`biogeophys/PhotosynthesisMod.F90:212`) is the Farquhar-von Caemmerer-Berry biochemical model coupled to Ball-Berry stomatal conductance, as described in the in-source header (`PhotosynthesisMod.F90:217-220`, citing Bonan et al. 2011). It is called **once per canopy stream** (sunlit = `phase='sun'` or shaded = `phase='sha'`) from `CanopyFluxes`.

**This subroutine is bypassed when `use_fates = .true.`** — FATES has its own Farquhar/Ball-Berry implementation called through `alm_fates%wrap_photosynthesis` (see `CanopyFluxesMod.F90:880` and the header note at `PhotosynthesisMod.F90:222`: *"This subroutine is not called via FATES (RGK)"*).

### Rubisco-, RuBP-, and product-limited rates

Inside `ci_func` (`biogeophys/PhotosynthesisMod.F90:1448`), for each canopy layer and each iteration of the `ci` hybrid Newton-Secant solver, three potential photosynthesis rates are computed (`PhotosynthesisMod.F90:1511-1532`):

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
- `je` — photosynthetic electron transport rate, from a quadratic co-limitation involving `jmax_z`, absorbed PAR `par_z`, and empirical curvature `theta_psii = 0.7` (`PhotosynthesisMod.F90:1508`).
- `cp`, `kc`, `ko` — CO<sub>2</sub> compensation point and Michaelis-Menten constants for CO<sub>2</sub> and O<sub>2</sub>, each Arrhenius-scaled with activation energies `vcmaxha`, `kcha`, `koha`, `cpha`, etc.
- `tpu_z`, `kp_z` — triose-phosphate utilization (C3) and PEP-carboxylase slope (C4).

### Co-limitation

The three rates are merged via two quadratic co-limitations (`PhotosynthesisMod.F90:1534-1546`):

```
! First co-limit ac (Rubisco) and aj (RuBP) with curvature theta_cj(p):
theta_cj * ai^2 - (ac + aj)*ai + ac*aj = 0     ->  ai = min(r1, r2)

! Then co-limit ai with ap (product) with curvature theta_ip = 0.95:
theta_ip * ag^2 - (ai + ap)*ag + ai*ap = 0     ->  ag = min(r1, r2)

an(p,iv) = ag(p,iv) - lmr_z    ! subtract leaf maintenance respiration
```

`theta_cj` is PFT-dependent (stored on `photosyns_type`), `theta_ip = 0.95` is a constant (`PhotosynthesisMod.F90:1509`).

### Ball-Berry stomatal conductance

Still inside `ci_func`, once net photosynthesis `an` is known, stomatal conductance `gs_mol` is obtained from the quadratic Ball-Berry equation (`PhotosynthesisMod.F90:1558-1564`):

```
cs = cair - (1.4 / gb_mol) * an * forc_pbot           ! CO2 at leaf surface
cs * gs^2 + [cs*(gb - bbb) - mbb*an*forc_pbot] * gs
         - gb*(cs*bbb + mbb*an*forc_pbot*rh_can) = 0
```

whose physically-meaningful root `gs_mol = max(r1, r2)` is then used to compute the next `ci`:

```
ci_new = cair - an * forc_pbot * (1.4/gs + 1.6/gb) / (gs * gb / (gs + gb))
```

(rearranged to the residual form `fval = ci - ci_new` in `PhotosynthesisMod.F90:1568`). The outer `hybrid` / `brent` solver (`PhotosynthesisMod.F90:1139-1256`) iterates `ci` until `fval = 0`.

Ball-Berry parameters:
- `bbb` = `bbbopt * btran` — minimum leaf conductance, scaled by soil water stress.
- `mbb` = `mbbopt` — slope; `mbbopt` is PFT-dependent (`veg_vp%mbbopt`, e.g. ~9 for C3 and ~4 for C4, `PhotosynthesisMod.F90:511-516`).
- `rh_can` — canopy air relative humidity passed in by `CanopyFluxes`.

A consistency check after the solve (`PhotosynthesisMod.F90:909-920`) computes `gs_mol_err = mbb*max(an,0)*hs/cs*forc_pbot + bbb` and prints a warning if it differs from the quadratic root by more than 0.1 μmol H<sub>2</sub>O m<sup>-2</sup> s<sup>-1</sup>.

### Canopy integration

After `Photosynthesis` has written `an(p,iv)` and `gs_mol(p,iv)` for every canopy layer `iv = 1..nrad(p)` and every sunlit/shaded stream, `PhotosynthesisTotal` (`biogeophys/PhotosynthesisMod.F90:973`) vertically integrates using the sunlit-fraction profile `fsun_z(p,iv)` that came out of `TwoStream` (see [radiation.md](radiation.md)). This sets:

- `psnsun_patch`, `psnsha_patch` — patch-scale sunlit and shaded gross photosynthesis
- `psn_patch = psnsun + psnsha`
- `psn_wc_patch`, `psn_wj_patch`, `psn_wp_patch` — C3 co-limitation diagnostics
- `rssun_patch`, `rssha_patch` — canopy-scale stomatal resistances (s m<sup>-1</sup>)

These canopy-integrated rates flow onward into the CN/CNP BGC (`psn_to_cpool`) and into the latent-heat split inside `CanopyFluxes` for the next iteration.

## Bare-ground fluxes — `BareGroundFluxes`

`BareGroundFluxes` (`biogeophys/BareGroundFluxesMod.F90:35`) runs for non-vegetated patches. It shares the stability-iteration structure of `CanopyFluxes` but without a canopy Newton-Raphson on `t_veg`:

- `itmin = 3`, `itmax = 30` (`BareGroundFluxesMod.F90:69-70`).
- Uses the same `FrictionVelocity` / `MoninObukIni` machinery.
- Uses `shr_flux_update_stress` (from `shr_flux_mod`) to iteratively relax the surface stress when `implicit_stress = .true.`.
- Calls `do_soilevap_beta` from `SurfaceResistanceMod` to check whether the Lee-Pielke 1992 evaporation-efficiency factor is active.
- Uses `QSat` (see [canopy_hydrology.md](canopy_hydrology.md)) to rebuild `qsatg`, `dqsatg/dT` at the ground surface each iteration.
- Writes `eflx_sh_grnd`, `qflx_evap_soi`, `taux`, `tauy` straight into `energyflux_vars` / `waterflux_vars`, plus `u10`, `va` diagnostics for dust emission.

## Urban fluxes — `UrbanFluxes`

`UrbanFluxes` (`biogeophys/UrbanFluxesMod.F90:49`) solves turbulent fluxes for urban canyons. Unlike the single-patch vegetated and bare-ground cases, urban landunits have multiple column types (sunwall, shadewall, roof, impervious road, pervious road), each with its own roughness and temperature. The routine shares `FrictionVelocity` with the other drivers but applies it separately for each urban column and then aggregates the urban-landunit-average fluxes. See [urban.md](urban.md) for the column layout and anthropogenic heat handling.

## Lake fluxes — `LakeFluxes`

`LakeFluxes` (`biogeophys/LakeFluxesMod.F90:39`) assumes one PFT per lake column (`LakeFluxesMod.F90:47`). It has a distinctive roughness-length formulation specific to open water, using `minz0lake`, `fcrit`, `cur0`, `cus`, `curm` from `LakeCon`, and the frozen-lake roughness `z0frzlake`. It runs an **explicit-then-implicit** stress iteration with different `itmax` bounds (`itmax_expl = 4`, `itmax_impl = 30`, `LakeFluxesMod.F90:81-82`). Heat transfer through the lake column and freezing/thawing are handled by `LakeTemperatureMod` and `LakeHydrologyMod` — see [lake.md](lake.md) for the full lake physics.

## Ground-flux reconciliation — `SoilFluxes`

`SoilFluxes` (`biogeophys/SoilFluxesMod.F90:38`) runs **after** `SoilTemperature` and applies a single linear correction so that the surface fluxes reported for the time step are consistent with the *new* ground temperature. Key operations:

- Compute the temperature increment `tinc(c) = t_grnd(c) - t_grnd0(c)`.
- Update longwave emission `eflx_lwrad_del` using the new `t_grnd`.
- Redistribute column-total soil evaporation `topsoil_evap_tot` among patches and among the top soil/snow layers, respecting `egsmax` (max allowable supply) and `frac_sno_eff`, `frac_h2osfc` (`SoilFluxesMod.F90:72-97`).
- Recompute `eflx_sh_grnd`, `eflx_lh_grnd`, `qflx_evap_soi`, `qflx_evap_tot`.
- Assemble patch-total `eflx_sh_tot = eflx_sh_veg + eflx_sh_grnd`, `eflx_lh_tot`, and `qflx_evap_veg` at the end of the step.

After `SoilFluxes`, the fluxes seen by the atmosphere coupler for the ending time step are final.

## State containers

### `energyflux_type` (`biogeophys/EnergyFluxType.F90:19`)

Stores (partial list):
- `btran_patch`, `btran2_patch`, `rresis_patch` — transpiration wetness factor and layer resistance (from `SoilMoistStressMod`).
- `eflx_sh_tot`, `eflx_sh_veg`, `eflx_sh_grnd`, `eflx_sh_snow`, `eflx_sh_h2osfc`, `eflx_sh_soil` — sensible heat components.
- `eflx_lh_tot`, `eflx_lh_vege`, `eflx_lh_vegt`, `eflx_lh_grnd` — latent heat components.
- `eflx_lwrad_net`, `eflx_lwrad_out`, `ulrad`, `dlrad` — longwave energy fluxes.
- `taux_patch`, `tauy_patch` — momentum stress components.
- `eflx_dynbal_dribbler` — annual flux dribbler for dynamic subgrid balancing (`EnergyFluxType.F90:121`).

### `waterflux_type` (`biogeophys/WaterfluxType.F90:20`)

Stores (partial list):
- `qflx_evap_tot_patch`, `qflx_evap_veg_patch`, `qflx_evap_soi_patch`, `qflx_evap_can_patch` — evaporation components.
- `qflx_tran_veg_patch` — transpiration.
- `qflx_rain_grnd_patch`, `qflx_snow_grnd_patch`, `qflx_snwcp_ice_patch`, `qflx_snwcp_liq_patch` — precipitation onto the ground.
- `qflx_sub_snow_patch`, `qflx_dew_snow_patch`, `qflx_dew_grnd_patch` — sublimation/dew.
- `qflx_surf_col`, `qflx_drain_col`, `qflx_qrgwl_col` — runoff and drainage (used by `HydrologyDrainageMod`).

### `frictionvel_type` (`biogeophys/FrictionVelocityType.F90`)

Stores:
- `forc_hgt_u_patch`, `forc_hgt_t_patch`, `forc_hgt_q_patch` — atmospheric forcing heights used in similarity theory.
- `u10_patch`, `u10_elm_patch`, `u10_with_gusts_elm_patch`, `va_patch` — 10-m wind diagnostics for dust/sea-salt.
- `fv_patch` — friction velocity (`u*`) for dust.
- `vds_patch` — dry-deposition velocity term.

### `photosyns_type` (`biogeophys/PhotosynthesisType.F90`)

Stores per canopy layer:
- `ac_patch`, `aj_patch`, `ap_patch`, `ag_patch`, `an_patch` — Rubisco, RuBP, product, co-limited, and net CO<sub>2</sub> assimilation rates.
- `vcmax_z_patch`, `tpu_z_patch`, `kp_z_patch` — temperature- and canopy-depth-scaled kinetic parameters.
- `gs_mol_patch`, `rssun_patch`, `rssha_patch` — stomatal conductance and sunlit/shaded resistances.
- `bbb_patch`, `mbb_patch` — Ball-Berry parameters after `btran` scaling.
- `cp_patch`, `kc_patch`, `ko_patch`, `qe_patch`, `theta_cj_patch` — Farquhar kinetic constants.
- `psnsun_patch`, `psnsha_patch`, `psn_patch`, `psn_wc_patch`, `psn_wj_patch`, `psn_wp_patch` — integrated GPP and limitation diagnostics.
- `c3flag_patch` — true for C3, false for C4.

`photosyns_vars_TimeStepInit` (`PhotosynthesisType.F90`; called from `CanopyFluxesMod.F90:110`) resets the time-step-scoped fields at the start of each canopy-flux call.

## Cross-links

- The `btran` factor and root-weighted transpiration sink feed into `SoilHydrology` (Richards' equation) in the soil hydrology doc.
- `wind_speed0`, `va`, `u10` from `frictionvel_type` drive the dust emission in `AerosolMod` (see `aerosol_and_erosion.md`) and sea-salt in the atmosphere coupler.
- The FATES path replaces `Photosynthesis` / `PhotosynthesisHydraulicStress`, but still uses `FrictionVelocity`, the Newton-Raphson `t_veg` solve, and `SoilFluxes` — i.e. the entire turbulent-flux machinery in this document applies to FATES runs.
- `sabv`, `sabg`, `sabg_lyr` from [radiation.md](radiation.md) enter `CanopyFluxes` and `BareGroundFluxes` as the driving `R_net` terms.
- Canopy interception `h2ocan` referenced here (and set by [canopy_hydrology.md](canopy_hydrology.md)) caps the interception-evaporation flux in `CanopyFluxesMod.F90:1081-1092`.
