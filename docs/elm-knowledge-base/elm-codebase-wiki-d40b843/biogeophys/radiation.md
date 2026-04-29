---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Surface Albedo and Radiation

This document covers ELM's solar (shortwave) radiation pathway for one non-urban, non-lake time step. The pathway splits into **(1) albedo staging** (done one step ahead for the atmosphere's next downwelling call) and **(2) absorbed-radiation bookkeeping** (done when the downwelling fluxes actually arrive). Urban and lake albedo live in `UrbanAlbedoMod` and `SurfaceAlbedoMod::SoilAlbedo` (the lake branch), respectively.

Five modules implement the non-urban path:

| Module | Role |
|---|---|
| `SurfaceAlbedoMod` (`biogeophys/SurfaceAlbedoMod.F90`) | Top-level driver; calls soil albedo, SNICAR, and two-stream canopy transfer |
| `SurfaceAlbedoType` (`biogeophys/SurfaceAlbedoType.F90:59`) | `surfalb_type` container holding albedos, canopy transfer coefficients, SNICAR per-layer absorption factors |
| `SurfaceRadiationMod` (`biogeophys/SurfaceRadiationMod.F90`) | Multiplies absorbed/reflected/transmitted fractions by incoming `forc_solad`/`forc_solai` to get W m<sup>-2</sup> |
| `SnowSnicarMod` (`biogeophys/SnowSnicarMod.F90`) | SNICAR radiative transfer for snow with aerosols; snow grain aging |
| `SolarAbsorbedType` (`biogeophys/SolarAbsorbedType.F90:16`) | `solarabs_type` container for absorbed SW fluxes (`sabv`, `sabg`, `sabg_lyr`, etc.) |

## Public subroutines

| Subroutine | Purpose |
|---|---|
| `SurfaceAlbedo(bounds, ..., nextsw_cday, declinp1, ...)` (`biogeophys/SurfaceAlbedoMod.F90:59`) | Driver for the next radiation time step's albedo; calls `SoilAlbedo`, `SNICAR_RT` (or `SNICAR_AD_RT`) for direct and diffuse, then `TwoStream` |
| `SurfaceRadiation(bounds, ..., atm2lnd_vars, ...)` (`biogeophys/SurfaceRadiationMod.F90:305`) | Applies the stored transfer coefficients to the incoming `forc_solad/forc_solai`, computes `sabv`, `sabg`, `sabg_lyr`, reflected flux `fsr`, NIR/VIS reflectance splits for history |
| `CanopySunShadeFractions(...)` (`biogeophys/SurfaceRadiationMod.F90:854`) | Sun/shade area-index fractions used by the photosynthesis scaling |
| `SNICAR_RT(flg_snw_ice, bounds, ..., snw_rds, mss_cnc_aer_in, albsfc, albout, flx_abs)` (`biogeophys/SnowSnicarMod.F90:283`) | Two-stream snow radiative transfer (Toon et al. 1989 multi-scattering, Flanner et al. 2007 SNICAR) returning snow albedo and per-layer absorbed fraction, given grain radius and aerosol concentration |
| `SNICAR_AD_RT(...)` (`biogeophys/SnowSnicarMod.F90:1784`) | Adding-doubling variant of `SNICAR_RT`; selected when `use_snicar_ad = .true.` |
| `SnowAge_grain(bounds, num_snowc, filter_snowc, ...)` (`biogeophys/SnowSnicarMod.F90:1211`) | Updates effective snow grain radius from dry-snow vapor redistribution, wet-snow growth, and refreezing (Flanner & Zender 2006; Brun 1989) |
| `SnowOptics_init()` (`biogeophys/SnowSnicarMod.F90:1510`) / `SnowAge_init()` (`SnowSnicarMod.F90:1741`) | One-time reads of the SNICAR optics and aging lookup tables from NetCDF |

Private to `SurfaceAlbedoMod`: `SoilAlbedo` (`biogeophys/SurfaceAlbedoMod.F90:1015`), `TwoStream` (`SurfaceAlbedoMod.F90:1147`), `Albedo_TOP_Adjustment` (`SurfaceAlbedoMod.F90:1720`).

## Calling sequence inside `SurfaceAlbedo`

Documented in-source at `SurfaceAlbedoMod.F90:78-86`:

```
SurfaceAlbedo (stages albedo for NEXT sw step)
 ├── SoilAlbedo                 -> albsod, albsoi (soil/lake/ice/wetland underneath snow)
 ├── SNICAR_RT   (direct beam)  -> albsnd, flx_abs(direct)
 │     or SNICAR_AD_RT          (if use_snicar_ad)
 ├── SNICAR_RT   (diffuse)      -> albsni, flx_abs(diffuse)
 │     or SNICAR_AD_RT
 └── TwoStream                  -> albd, albi, fabd, fabi, ftdd, ftid, ftii,
                                  fabd_sun, fabd_sha, fabi_sun, fabi_sha, fabd_*_z
```

`nextsw_cday` (the next shortwave calendar day) is passed in so that the two-stream canopy solution corresponds to the cosine zenith angle at which the atmosphere will next call ELM for downwelling shortwave.

### Slope-corrected cosine of incidence (`use_finetop_rad`)

When `use_finetop_rad = .true.`, the routine no longer passes the geometric cosine of solar zenith angle (`coszen_col`) directly to `SoilAlbedo`/`SNICAR_RT`/`TwoStream`. Instead, a per-gridcell **cosine of solar incidence angle** `cosinc_gcell(g)` is computed using the gridcell's slope and aspect and the solar azimuth (`SurfaceAlbedoMod.F90:244-265`):

```fortran
deg2rad = SHR_CONST_PI/180._r8
if (.not. use_finetop_rad) then
   cosinc_gcell(g) = coszen_gcell(g)
else
   sza        = acos(coszen_gcell(g))
   saa        = shr_orb_azimuth(nextsw_cday, lat, lon, declinp1, sza)
   slope_rad  = grc_pp%slope_deg(g)  * deg2rad
   aspect_rad = grc_pp%aspect_deg(g) * deg2rad
   cosinc_gcell(g) = cos(slope_rad) * coszen_gcell(g) &
                   + sin(slope_rad) * sin(sza) * cos(aspect_rad - saa)
   cosinc_gcell(g) = max(-1._r8, min(cosinc_gcell(g), 1._r8))
   if (cosinc_gcell(g) <= 0._r8) cosinc_gcell(g) = 0.1_r8  ! still need diffuse albedo
endif
```

The result is stored on `surfalb_type::cosinc_col(:)` (`SurfaceAlbedoType.F90:62`, allocated at line 259, restart-wired at line 464) and threaded into all subsequent radiative-transfer calls via the `cosinc_col` slot at `SurfaceAlbedoMod.F90:335, 403, 414, 429, 440, ...`. Default behavior (flag off) is identical to the prior version.

## Soil albedo

`SoilAlbedo` (`biogeophys/SurfaceAlbedoMod.F90:1015`) computes the underlying ground albedo before snow overlay, branching by landunit type:

- **Vegetated soil / crop** — dry-vs-wet lookup based on `isoicol` and top-layer volumetric water:

  ```
  inc = max(0.11 - 0.40 * h2osoi_vol(c,1), 0)
  albsod = min(albsat(soilcol,ib) + inc, albdry(soilcol,ib))
  ```

  `albsat` and `albdry` are read at initialization into `SurfaceAlbedoType`. A larger `inc` from drier soils darkens when clamped to `albdry`.

- **Ice / glacier** — uses the constant `albice` for both VIS and NIR.

- **Open-water lake / wetland** — BATS-style cosine-zenith dependence, using `cosinc_col(c)`:

  ```
  albsod = 0.05 / (max(0.001, cosinc_col(c)) + 0.15)
  ```

- **Frozen lake** — uses `alblak`, with an optional ice-fraction parameterization from Mironov (2010) when `lakepuddling` is on. The `calb = 95.6` coefficient comes from Mironov's formula.

## SNICAR snow optics

`SNICAR_RT` implements the Flanner-Zender-Randerson-Rasch (2007) Single Layer Snow and Ice Aerosol Radiation model, solved with the Toon et al. (1989) multi-layer multiple-scattering method (references in `biogeophys/SnowSnicarMod.F90:291-303`).

Arguments (`biogeophys/SnowSnicarMod.F90:283-324`):

| Argument | Meaning |
|---|---|
| `flg_snw_ice` | 1 when called from CLM/ELM, 2 when called from CSIM sea ice |
| `coszen` | Cosine of solar zenith angle (or `cosinc_col` when `use_finetop_rad`) at next SW step |
| `flg_slr_in` | 1 = direct beam, 2 = diffuse — selects which downwelling spectrum to use |
| `h2osno_liq`, `h2osno_ice` | Layer liquid and ice mass (kg m<sup>-2</sup>) |
| `snw_rds` | Effective snow grain radius per layer (micron) |
| `mss_cnc_aer_in` | Mass concentration of each aerosol species (`sno_nbr_aer` of them) in each layer (kg/kg) |
| `albsfc` | Albedo of surface below the snow (from `SoilAlbedo`) |
| `albout` | Snow-surface albedo integrated into the two ELM radiation bands |
| `flx_abs` | Per-layer per-band absorbed flux fraction |

`SNICAR_RT` internally uses `numrad_snw` spectral sub-bands (finer than the 2 ELM bands) to capture the strong wavelength dependence of ice absorption and aerosol scattering, then integrates back to `numrad = 2` before returning.

The absorbed fraction `flx_abs` is carried into `SurfaceRadiation` as `flx_absdv` (VIS direct), `flx_absdn` (NIR direct), `flx_absiv` (VIS diffuse), `flx_absin` (NIR diffuse) through the `surfalb_type` container.

### Slope-corrected SWE for SNICAR (`use_finetop_rad`)

When `use_finetop_rad = .true.`, the per-layer snow water (`h2osno_liq_lcl`, `h2osno_ice_lcl`) and column-total `h2osno_lcl` are scaled by `cos(slope_rad)` before being passed into the SNICAR radiative-transfer kernel (`SnowSnicarMod.F90:2271-2283`):

```fortran
if (use_finetop_rad) then
   slope_rad = grc_pp%slope_deg(g_idx) * deg2rad
   if ((flg_snw_ice == 1) .and. (snl(c_idx) > -1)) then
      h2osno_liq_lcl(0) = h2osno_liq_lcl(0) * cos(slope_rad)
      h2osno_ice_lcl(0) = h2osno_ice_lcl(0) * cos(slope_rad)
   else
      h2osno_liq_lcl(:) = h2osno_liq_lcl(:) * cos(slope_rad)
      h2osno_ice_lcl(:) = h2osno_ice_lcl(:) * cos(slope_rad)
   endif
   h2osno_lcl = h2osno_lcl * cos(slope_rad)
endif
```

Default off; default behavior matches the unscaled SWE inputs.

### Snow grain aging

`SnowAge_grain` (`biogeophys/SnowSnicarMod.F90:1211`) updates the effective radius `snw_rds` each step from three processes:

1. **Dry-snow vapor redistribution (Flanner & Zender 2006)** — lookup table of (τ, κ, dr/dt<sub>0</sub>) as functions of snow T, dT/dz, density; applied as

   `dr/dt = drdt0 * (τ / (dr_fresh + τ))^(1/κ)`

2. **Wet-snow growth (Brun 1989)** — LWC-dependent incremental radius `dr_wet`.
3. **Refreezing** — refrozen liquid clumps into an effective grain size `snw_rds_refrz`.

`snw_rds_refrz` is a **module variable** at `d40b8431` (no longer a parameter), declared at `SnowSnicarMod.F90:83`:

```fortran
real(r8) :: snw_rds_refrz = 1000._r8   ! microns (default; pre-firn behavior)
```

It is **reset each call** depending on the firn flag (`SnowSnicarMod.F90:1444-1447`):

```fortran
if (use_firn_percolation_and_compaction) then
   snw_rds_refrz = 1500._r8       ! larger refreeze radius in firn mode
else
   snw_rds_refrz = 1000._r8       ! original value
endif
```

The capping correction inside `SnowAge_grain` is also gated by the firn flag (`SnowSnicarMod.F90:1438`): `if (do_capsnow(c_idx) .and. .not. use_firn_percolation_and_compaction)`. The wiki at `60d9aad` described `snw_rds_refrz` as a "fixed constant" — that is no longer accurate.

The updated `snw_rds` feeds back into the next `SNICAR_RT` call via a lookup over single-scatter albedo and asymmetry parameter at each layer's grain size.

## Two-stream canopy radiative transfer

`TwoStream` (`biogeophys/SurfaceAlbedoMod.F90:1147`) solves the Dickinson (1983) / Sellers (1985) two-stream approximation for a leaf-stem canopy overlying a surface of known albedo (`albgrd`, `albgri` from `SoilAlbedo`). The implementation is the multi-layer extension of Bonan et al. (2011), capturing the sunlit-vs-shaded profile of absorbed PAR needed by the per-layer photosynthesis.

### Geometry terms

For each vegetated sunlit patch (`filter_vegsol`), leaf angle parameter `xl` (PFT-dependent, pulled from `veg_vp%xl`) is clamped and used to compute the leaf-projection in the beam direction:

```
chil   = clamp(xl, -0.4, 0.6)
phi1   = 0.5 - 0.633 * chil - 0.330 * chil^2
phi2   = 0.877 * (1 - 2*phi1)
G(mu)  = gdir = phi1 + phi2 * cosz          ! Ross G-function
K_b    = twostext = gdir / cosz             ! direct-beam extinction
avmu   = [1 - phi1/phi2 * ln((phi1+phi2)/phi1)] / phi2   ! avg inverse diffuse optical depth
```

When `use_finetop_rad = .true.`, the `cosz` argument is `cosinc_col(c)`; otherwise it is `coszen_col(c)`.

### Per-band solution

Inside `do ib = 1, numrad`, for each band:

```
omegal = rho(p,ib) + tau(p,ib)              ! leaf scatter albedo
asu    = 0.5*omegal*gdir/temp0(p)*temp2(p)  ! single-scatter albedo
betadl = (1 + avmu*K_b) / (omegal*avmu*K_b) * asu
betail = 0.5 * [(rho+tau) + (rho-tau)*((1+chil)/2)^2] / omegal
```

If leaves are cold (`t_veg <= tfrz`), the wet fraction `fwet` is taken as snow-cover fraction and blended with bulk-snow `omegas`, `betads`, `betais` constants.

The coupled two-stream ODEs for upward (`I↑`) and downward (`I↓`) diffuse fluxes, with source terms from the direct beam, reduce to a linear system in four unknowns (`h2, h3, h5, h6`) solved analytically. Key intermediates:

```
b = 1 - omega + omega*betai
c1 = omega*betai
h  = sqrt(b^2 - c1^2) / avmu       ! decay rate of diffuse fluxes
sigma = (avmu*K_b)^2 - (b^2 - c1^2)
s1 = exp(-h*(LAI+SAI))
s2 = exp(-K_b*(LAI+SAI))
```

Outputs per patch/band:

| Output | Meaning |
|---|---|
| `albd(p,ib)`, `albi(p,ib)` | Canopy albedo above canopy for direct/diffuse beam |
| `ftdd(p,ib)` | Transmitted direct beam below canopy (= `s2`) |
| `ftid(p,ib)` | Downward scattered diffuse below canopy, per unit incident direct |
| `ftii(p,ib)` | Downward diffuse below canopy, per unit incident diffuse |
| `fabd(p,ib)`, `fabi(p,ib)` | Total absorbed by canopy, per unit direct / diffuse incident |
| `fabd_sun(p,ib)`, `fabd_sha(p,ib)` | Sunlit/shaded splits of `fabd` |
| `fabd_sun_z(p,iv)`, `fabd_sha_z(p,iv)` | Per canopy-layer absorbed PAR (sunlit/shaded) — drives per-layer photosynthesis |
| `fsun_z(p,iv)` | Sunlit fraction of canopy layer `iv` |
| `vcmaxcintsun_patch`, `vcmaxcintsha_patch` | Leaf-to-canopy scaling coefficients for sunlit/shaded Vcmax (saved on `surfalb_type`) |

The conservation check is:

```
fabd = 1 - albd - (1 - albgrd)*ftdd - (1 - albgri)*ftid
```

(absorbed = incident minus reflected-above minus transmitted-through to the ground, which is in turn reflected by the ground per-its-albedo).

### TOP solar adjustment

When `use_top_solar_rad = .true.`, `Albedo_TOP_Adjustment` (`SurfaceAlbedoMod.F90:1720`) applies a Terrain-Over-the-Pole topographic correction via factors `f_dir`, `f_rdir`, `f_dif`, `f_rdif` stored on `surfalb_type` (`biogeophys/SurfaceAlbedoType.F90:80-85`). This rescales both the canopy-top albedo and the below-canopy downward fluxes to account for subgrid slope/aspect effects on vegetated patches.

**Note:** at `d40b8431`, only `cosinc_col` (`SurfaceAlbedoType.F90:62`) is restart-wired (`SurfaceAlbedoType.F90:464`). The `fd_top_adjust`, `f_dir`, `f_rdir`, `f_dif`, `f_rdif` pointers still exist as type members (allocated at lines 277-282, initialized to `1.0` for `fd_top_adjust` and `0.0` for the four others), but they are **not** persisted across runs — they are derived per-step from `cosinc_col` and the slope/aspect inputs. The wiki at `60d9aad` listed these four as restart fields; that is no longer accurate.

`use_top_solar_rad` and `use_finetop_rad` are independent flags. Both apply slope/aspect-related corrections, but `use_top_solar_rad` operates inside `Albedo_TOP_Adjustment` (the older formulation), while `use_finetop_rad` adds the `cosinc_col` substitution directly into `SoilAlbedo`/`SNICAR_RT`/`TwoStream` upstream.

## Absorbed radiation accounting — `SurfaceRadiation`

`SurfaceRadiation` (`biogeophys/SurfaceRadiationMod.F90:305`) runs when incoming `forc_solad` (direct) and `forc_solai` (diffuse) become available. It uses the fractional transfer coefficients stored in `surfalb_type` to compute actual watts per square meter.

When `use_finetop_rad = .true.`, the routine reads forcing from `top_af%solad_pp` / `top_af%solai_pp` (the per-patch radiation under the topographic-correction scheme), and falls back to plain `top_af%solad`/`top_af%solai` only when the flag is off (`SurfaceRadiationMod.F90:480-485` style):

```fortran
if (.not. use_finetop_rad) then
   forc_solad_pp(:,:) = forc_solad(:,:)
   forc_solai_pp(:,:) = forc_solai(:,:)
end if
```

Outputs (driven by `forc_solad_pp`, `forc_solai_pp` internally):

- Canopy direct absorbed: `cad(p,ib) = fabd(p,ib) * forc_solad_pp(t,ib)`
- Canopy diffuse absorbed: `cai(p,ib) = fabi(p,ib) * forc_solai_pp(t,ib)`
- `sabv_patch` — total SW absorbed by vegetation (`solarabs_type`).
- `sabg_patch` — total SW absorbed by ground.
- `sabg_lyr_patch(p,j)` — per-layer (snow and top soil) absorbed flux, built from `flx_absdv/flx_absdn/flx_absiv/flx_absin` multiplied by the direct/diffuse contributions that actually reach the ground (`trd`, `tri`).

Reflected fluxes for history output:

- `fsa_patch` — total absorbed = `sabv + sabg`
- `fsr_patch` — total reflected = `(forc_solad+forc_solai) - fsa`
- `fsr_vis_d_patch`, `fsr_vis_i_patch` — patch-level reflected VIS direct/diffuse (**new** at `d40b8431`, declared on `solarabs_type` at `SolarAbsorbedType.F90:57-58`, allocated at lines 136-137; initialized to zero at lines 281-282)
- `fsr_nir_d`, `fsr_nir_i` — per-band direct/diffuse components (NIR)
- `fsr_sno_vd`, `fsr_sno_nd`, `fsr_sno_vi`, `fsr_sno_ni` — snow-only splits (when snow is present)

SNICAR aerosol "no-X" albedos (`albgrd_oc`, `albgrd_bc`, `albgrd_dst`, `albgrd_pur`) are used to re-compute `sabg_pur`, `sabg_bc`, `sabg_oc`, `sabg_dst` inside the same loop, yielding the aerosol surface-forcing fields `sfc_frc_bc_patch`, `sfc_frc_oc_patch`, `sfc_frc_dst_patch`, `sfc_frc_aer_patch`. These are the main SNICAR radiative-forcing diagnostics.

## The `surfalb_type` container

`SurfaceAlbedoType::surfalb_type` (`biogeophys/SurfaceAlbedoType.F90:59-`) stores everything the radiation path needs to carry between `SurfaceAlbedo` (step *n*+1 staging) and `SurfaceRadiation` (step *n*+1 application), plus sunlit/shaded canopy scaling used by photosynthesis:

- `coszen_col`, `cosinc_col` (**new**, line 62), `albd_patch`, `albi_patch`, `albgrd_col`, `albgri_col`, `albsod_col`, `albsoi_col`, `albsnd_hst_col`, `albsni_hst_col`, plus pure-snow / no-aerosol variants `albgrd_pur_col`, `albgrd_bc_col`, `albgrd_oc_col`, `albgrd_dst_col` and their `albgri_*_col` diffuse counterparts.
- Two-stream outputs `ftdd_patch`, `ftid_patch`, `ftii_patch`, `fabd_patch`, `fabd_sun_patch`, `fabd_sha_patch`, `fabi_patch`, `fabi_sun_patch`, `fabi_sha_patch`.
- Per-layer outputs `fabd_sun_z_patch`, `fabd_sha_z_patch`, `fabi_sun_z_patch`, `fabi_sha_z_patch`, `fsun_z_patch`, `tlai_z_patch`, `tsai_z_patch`, `nrad_patch`, `ncan_patch`.
- Sunlit/shaded Vcmax scaling `vcmaxcintsun_patch`, `vcmaxcintsha_patch`.
- SNICAR per-layer absorption `flx_absdv_col`, `flx_absdn_col`, `flx_absiv_col`, `flx_absin_col`.
- TOP adjustment factors `fd_top_adjust`, `fi_top_adjust`, `f_dir`, `f_rdir`, `f_dif`, `f_rdif` (no longer restart-wired at `d40b8431`).

Together with `solarabs_type` (`biogeophys/SolarAbsorbedType.F90:16`), which owns the *W m<sup>-2</sup>* outputs (`sabv`, `sabg`, `sabg_lyr`, `fsa`, `fsr`, `fsr_vis_d`, `fsr_vis_i`, `parveg_ln`), these are the two data types linking radiation to the canopy energy-balance solver in [canopy_fluxes.md](canopy_fluxes.md).

## Cross-links

- Sunlit/shaded PAR profiles (`fabd_sun_z`, `fabi_sha_z`) drive the per-layer photosynthesis in [canopy_fluxes.md](canopy_fluxes.md).
- Per-layer absorbed shortwave (`sabg_lyr` built from `flx_abs`) enters the snow and soil energy solve in [snow.md](snow.md) and `soil_temperature.md`.
- Snow grain radius `snw_rds` is mass-weighted during snow layer compaction and division in [snow.md](snow.md); the updates shown here apply only to the optics-relevant part. `snw_rds_refrz` is now a variable that toggles between 1000 µm (default) and 1500 µm (firn mode) — see also `aerosol_and_erosion.md`.
- Slope-corrected longwave in `CanopyFluxesMod.F90:705-708, 1277-1290` and `SoilFluxesMod.F90:287-301, 437-444` consumes the same `slope_rad` geometry as the radiation path when `use_finetop_rad = .true.`.
- Under FATES, the FATES-native canopy RT path overrides `TwoStream`. See the note in the header of [index.md](index.md) about FATES vs native paths.
