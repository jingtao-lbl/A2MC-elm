---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
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
| `CanopySunShadeFractions(...)` (`biogeophys/SurfaceRadiationMod.F90:840`) | Sun/shade area-index fractions used by the photosynthesis scaling |
| `SNICAR_RT(flg_snw_ice, bounds, ..., snw_rds, mss_cnc_aer_in, albsfc, albout, flx_abs)` (`biogeophys/SnowSnicarMod.F90:283`) | Two-stream snow radiative transfer (Toon et al. 1989 multi-scattering, Flanner et al. 2007 SNICAR) returning snow albedo and per-layer absorbed fraction, given grain radius and aerosol concentration |
| `SNICAR_AD_RT(...)` (`biogeophys/SnowSnicarMod.F90:1778`) | Adding-doubling variant of `SNICAR_RT`; selected when `use_snicar_ad = .true.` |
| `SnowAge_grain(bounds, num_snowc, filter_snowc, ...)` (`biogeophys/SnowSnicarMod.F90:1211`) | Updates effective snow grain radius from dry-snow vapor redistribution, wet-snow growth, and refreezing (Flanner & Zender 2006; Brun 1989) |
| `SnowOptics_init()` (`biogeophys/SnowSnicarMod.F90:1504`) / `SnowAge_init()` (`SnowSnicarMod.F90:1735`) | One-time reads of the SNICAR optics and aging lookup tables from NetCDF |

Private to `SurfaceAlbedoMod`: `SoilAlbedo` (`biogeophys/SurfaceAlbedoMod.F90:987`), `TwoStream` (`SurfaceAlbedoMod.F90:1119`), `Albedo_TOP_Adjustment` (`SurfaceAlbedoMod.F90:1676`).

## Calling sequence inside `SurfaceAlbedo`

Documented in-source at `SurfaceAlbedoMod.F90:76-86`:

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

## Soil albedo

`SoilAlbedo` (`biogeophys/SurfaceAlbedoMod.F90:987`) computes the underlying ground albedo before snow overlay, branching by landunit type:

- **Vegetated soil / crop** — dry-vs-wet lookup based on `isoicol` and top-layer volumetric water (`biogeophys/SurfaceAlbedoMod.F90:1054`):

  ```
  inc = max(0.11 - 0.40 * h2osoi_vol(c,1), 0)
  albsod = min(albsat(soilcol,ib) + inc, albdry(soilcol,ib))
  ```

  `albsat` and `albdry` are read at initialization into `SurfaceAlbedoType`. A larger `inc` from drier soils darkens when clamped to `albdry`.

- **Ice / glacier** — uses the constant `albice` for both VIS and NIR (`biogeophys/SurfaceAlbedoMod.F90:1065`).

- **Open-water lake / wetland** — BATS-style cosine-zenith dependence (`SurfaceAlbedoMod.F90:1071`):

  ```
  albsod = 0.05 / (max(0.001, coszen) + 0.15)
  ```

- **Frozen lake** — uses `alblak`, with an optional ice-fraction parameterization from Mironov (2010) when `lakepuddling` is on (`SurfaceAlbedoMod.F90:1092-1106`). The `calb = 95.6` coefficient at `SurfaceAlbedoMod.F90:52` comes from Mironov's formula.

## SNICAR snow optics

`SNICAR_RT` implements the Flanner-Zender-Randerson-Rasch (2007) Single Layer Snow and Ice Aerosol Radiation model, solved with the Toon et al. (1989) multi-layer multiple-scattering method (references at `biogeophys/SnowSnicarMod.F90:291-303`).

Arguments (`biogeophys/SnowSnicarMod.F90:283-324`):

| Argument | Meaning |
|---|---|
| `flg_snw_ice` | 1 when called from CLM/ELM, 2 when called from CSIM sea ice |
| `coszen` | Cosine of solar zenith angle at next SW step |
| `flg_slr_in` | 1 = direct beam, 2 = diffuse — selects which downwelling spectrum to use |
| `h2osno_liq`, `h2osno_ice` | Layer liquid and ice mass (kg m<sup>-2</sup>) |
| `snw_rds` | Effective snow grain radius per layer (micron) |
| `mss_cnc_aer_in` | Mass concentration of each aerosol species (`sno_nbr_aer` of them) in each layer (kg/kg) |
| `albsfc` | Albedo of surface below the snow (from `SoilAlbedo`) |
| `albout` | Snow-surface albedo integrated into the two ELM radiation bands |
| `flx_abs` | Per-layer per-band absorbed flux fraction |

`SNICAR_RT` internally uses `numrad_snw` spectral sub-bands (finer than the 2 ELM bands) to capture the strong wavelength dependence of ice absorption and aerosol scattering, then integrates back to `numrad = 2` before returning.

The absorbed fraction `flx_abs` is carried into `SurfaceRadiation` as `flx_absdv` (VIS direct), `flx_absdn` (NIR direct), `flx_absiv` (VIS diffuse), `flx_absin` (NIR diffuse) through the `surfalb_type` container (see `biogeophys/SurfaceAlbedoType.F90:99-102`).

### Snow grain aging

`SnowAge_grain` (`biogeophys/SnowSnicarMod.F90:1211`) updates the effective radius `snw_rds` each step from three processes:

1. **Dry-snow vapor redistribution (Flanner & Zender 2006)** — lookup table of (τ, κ, dr/dt<sub>0</sub>) as functions of snow T, dT/dz, density; applied as

   `dr/dt = drdt0 * (τ / (dr_fresh + τ))^(1/κ)`

   (`biogeophys/SnowSnicarMod.F90:1226-1231`).
2. **Wet-snow growth (Brun 1989)** — LWC-dependent incremental radius `dr_wet`.
3. **Refreezing** — refrozen liquid clumps into an arbitrarily large `snw_rds_refrz` (fixed constant).

The updated `snw_rds` feeds back into the next `SNICAR_RT` call via a lookup over single-scatter albedo and asymmetry parameter at each layer's grain size.

## Two-stream canopy radiative transfer

`TwoStream` (`biogeophys/SurfaceAlbedoMod.F90:1119`) solves the Dickinson (1983) / Sellers (1985) two-stream approximation for a leaf-stem canopy overlying a surface of known albedo (`albgrd`, `albgri` from `SoilAlbedo`). The implementation is the multi-layer extension of Bonan et al. (2011), capturing the sunlit-vs-shaded profile of absorbed PAR needed by the per-layer photosynthesis (`SurfaceAlbedoMod.F90:1132-1133`).

### Geometry terms

For each vegetated sunlit patch (`filter_vegsol`), leaf angle parameter `xl` (PFT-dependent, pulled from `veg_vp%xl`) is clamped and used to compute the leaf-projection in the beam direction (`SurfaceAlbedoMod.F90:1247-1256`):

```
chil   = clamp(xl, -0.4, 0.6)
phi1   = 0.5 - 0.633 * chil - 0.330 * chil^2
phi2   = 0.877 * (1 - 2*phi1)
G(mu)  = gdir = phi1 + phi2 * cosz          ! Ross G-function
K_b    = twostext = gdir / cosz             ! direct-beam extinction
avmu   = [1 - phi1/phi2 * ln((phi1+phi2)/phi1)] / phi2   ! average inverse diffuse optical depth
```

### Per-band solution

Inside `do ib = 1, numrad`, for each band (`biogeophys/SurfaceAlbedoMod.F90:1287-1375`):

```
omegal = rho(p,ib) + tau(p,ib)              ! leaf scatter albedo
asu    = 0.5*omegal*gdir/temp0(p)*temp2(p)  ! single-scatter albedo
betadl = (1 + avmu*K_b) / (omegal*avmu*K_b) * asu
betail = 0.5 * [(rho+tau) + (rho-tau)*((1+chil)/2)^2] / omegal
```

If leaves are cold (`t_veg <= tfrz`), the wet fraction `fwet` is taken as snow-cover fraction and blended with bulk-snow `omegas`, `betads`, `betais` constants (`SurfaceAlbedoMod.F90:1314-1322`).

The coupled two-stream ODEs for upward (`I↑`) and downward (`I↓`) diffuse fluxes, with source terms from the direct beam, reduce to a linear system in four unknowns (`h2, h3, h5, h6`) solved analytically at `SurfaceAlbedoMod.F90:1352-1370`. Key intermediates:

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

The conservation check is (`SurfaceAlbedoMod.F90:1375`):

```
fabd = 1 - albd - (1 - albgrd)*ftdd - (1 - albgri)*ftid
```

(absorbed = incident minus reflected-above minus transmitted-through to the ground, which is in turn reflected by the ground per-its-albedo).

### TOP solar adjustment

When `use_top_solar_rad = .true.`, `Albedo_TOP_Adjustment` (`SurfaceAlbedoMod.F90:1676`) applies a Terrain-Over-the-Pole / topographic correction via factors `f_dir`, `f_rdir`, `f_dif`, `f_rdif` stored on `surfalb_type` (`biogeophys/SurfaceAlbedoType.F90:79-84`). This rescales both the canopy-top albedo and the below-canopy downward fluxes to account for subgrid slope/aspect effects on vegetated patches.

## Absorbed radiation accounting — `SurfaceRadiation`

`SurfaceRadiation` (`biogeophys/SurfaceRadiationMod.F90:305`) runs when incoming `forc_solad` (direct) and `forc_solai` (diffuse) become available (`biogeophys/SurfaceRadiationMod.F90:389-390`). It uses the fractional transfer coefficients stored in `surfalb_type` to compute actual watts per square meter:

- Canopy direct absorbed: `cad(p,ib) = fabd(p,ib) * forc_solad(t,ib)`
- Canopy diffuse absorbed: `cai(p,ib) = fabi(p,ib) * forc_solai(t,ib)`
- Transmitted to ground, direct: `trd(p,ib) = ftdd(p,ib)*forc_solad + ftid(p,ib)*forc_solad`-style contributions (full algebra at `SurfaceRadiationMod.F90` in the per-band `do ib` loop, values accumulated into `sabv` and `sabg`).
- `sabv_patch` — total SW absorbed by vegetation (`solarabs_type`).
- `sabg_patch` — total SW absorbed by ground.
- `sabg_lyr_patch(p,j)` — per-layer (snow and top soil) absorbed flux, built from `flx_absdv/flx_absdn/flx_absiv/flx_absin` multiplied by the direct/diffuse contributions that actually reach the ground (`trd`, `tri`).

Reflected fluxes for history output:

- `fsa_patch` — total absorbed = `sabv + sabg`
- `fsr_patch` — total reflected = `(forc_solad+forc_solai) - fsa`
- `fsr_vis_d`, `fsr_nir_d`, `fsr_vis_i`, `fsr_nir_i` — per-band direct/diffuse components
- `fsr_sno_vd`, `fsr_sno_nd`, `fsr_sno_vi`, `fsr_sno_ni` — snow-only splits (when snow is present)

SNICAR aerosol "no-X" albedos (`albgrd_oc`, `albgrd_bc`, `albgrd_dst`, `albgrd_pur`) are used to re-compute `sabg_pur`, `sabg_bc`, `sabg_oc`, `sabg_dst` inside the same loop, yielding the aerosol surface-forcing fields `sfc_frc_bc_patch`, `sfc_frc_oc_patch`, `sfc_frc_dst_patch`, `sfc_frc_aer_patch` (see declarations at `SurfaceRadiationMod.F90:458-468`). These are the main SNICAR radiative-forcing diagnostics.

## The `surfalb_type` container

`SurfaceAlbedoType::surfalb_type` (`biogeophys/SurfaceAlbedoType.F90:59-121`) stores everything the radiation path needs to carry between `SurfaceAlbedo` (step *n*+1 staging) and `SurfaceRadiation` (step *n*+1 application), plus sunlit/shaded canopy scaling used by photosynthesis:

- `coszen_col`, `albd_patch`, `albi_patch`, `albgrd_col`, `albgri_col`, `albsod_col`, `albsoi_col`, `albsnd_hst_col`, `albsni_hst_col`, plus pure-snow / no-aerosol variants `albgrd_pur_col`, `albgrd_bc_col`, `albgrd_oc_col`, `albgrd_dst_col` and their `albgri_*_col` diffuse counterparts.
- Two-stream outputs `ftdd_patch`, `ftid_patch`, `ftii_patch`, `fabd_patch`, `fabd_sun_patch`, `fabd_sha_patch`, `fabi_patch`, `fabi_sun_patch`, `fabi_sha_patch`.
- Per-layer outputs `fabd_sun_z_patch`, `fabd_sha_z_patch`, `fabi_sun_z_patch`, `fabi_sha_z_patch`, `fsun_z_patch`, `tlai_z_patch`, `tsai_z_patch`, `nrad_patch`, `ncan_patch`.
- Sunlit/shaded Vcmax scaling `vcmaxcintsun_patch`, `vcmaxcintsha_patch`.
- SNICAR per-layer absorption `flx_absdv_col`, `flx_absdn_col`, `flx_absiv_col`, `flx_absin_col`.
- TOP adjustment factors `fd_top_adjust`, `fi_top_adjust`, `f_dir`, `f_rdir`, `f_dif`, `f_rdif`.

Together with `solarabs_type` (`biogeophys/SolarAbsorbedType.F90:16`), which owns the *W m<sup>-2</sup>* outputs (`sabv`, `sabg`, `sabg_lyr`, `fsa`, `fsr`, `parveg_ln`), these are the two data types linking radiation to the canopy energy-balance solver in [canopy_fluxes.md](canopy_fluxes.md).

## Cross-links

- Sunlit/shaded PAR profiles (`fabd_sun_z`, `fabi_sha_z`) drive the per-layer photosynthesis in [canopy_fluxes.md](canopy_fluxes.md).
- Per-layer absorbed shortwave (`sabg_lyr` built from `flx_abs`) enters the snow and soil energy solve in [snow.md](snow.md) and `soil_temperature.md`.
- Snow grain radius `snw_rds` is mass-weighted during snow layer compaction and division in [snow.md](snow.md); the updates shown here apply only to the optics-relevant part.
- Under FATES, the FATES-native canopy RT path overrides `TwoStream`. See the note in the header of [index.md](index.md) about FATES vs native paths.
