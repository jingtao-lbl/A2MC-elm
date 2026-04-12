---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

# Radiation Transfer and Albedo

## Purpose and Scope

This page documents the radiation transfer and albedo calculations in FATES. The model uses a Norman (1979) two-stream scheme to compute the absorption, transmission, and reflection of direct-beam and diffuse shortwave radiation through the multi-layered canopy. It supplies sunlit and shaded leaf area indices, the absorbed photosynthetically active radiation (PAR) profile, and the patch-level direct and diffuse albedos returned to the host land model.

For the consumption of radiation outputs by the leaf biochemistry, see [Photosynthesis and Respiration](photosynthesis.md). For canopy layering and competition that set up the geometry used by the radiation solver, see [Canopy Structure and Competition](../canopy-structure/index.md).

## Module Location

Primary source file: `biogeophys/EDSurfaceAlbedoMod.F90`. The first line of that file declares `module EDSurfaceRadiationMod`, so the file name and the module name differ. Fortran `use` statements and cross-references in other FATES modules refer to the module name (`EDSurfaceRadiationMod`); filesystem searches must use the file name (`EDSurfaceAlbedoMod.F90`).

The driver is called from the host land model via `alm_fates%wrap_albedo(...)`, which runs on the sub-daily radiation timestep.

## Key Subroutines

| Subroutine | File / lines | Purpose |
| --- | --- | --- |
| `ED_Norman_Radiation` | `EDSurfaceAlbedoMod.F90:68-173` | Top-level loop over sites and patches; dispatches per-patch calculations |
| `PatchNormanRadiation` | `EDSurfaceAlbedoMod.F90:178-1104` | Full Norman two-stream solve for one patch (all canopy layers × PFTs × leaf layers × wavebands) |
| `ED_SunShadeFracs` | `EDSurfaceAlbedoMod.F90:1108-1291` | Computes sunlit/shaded LAI and absorbed PAR profiles from the solved radiation state |

## Radiation Streams and Wavebands

The solver handles all four combinations of stream type × waveband:

- **Streams** — `idirect` (direct beam) and `idiffuse` (diffuse/scattered). Indices are declared at `EDSurfaceAlbedoMod.F90:27-29`.
- **Wavebands** — `ivis` / `ipar` (visible, PAR, 400-700 nm) and `inir` (near-infrared, 700-2500 nm). Declared at `EDSurfaceAlbedoMod.F90:30-32`.

Direct-PAR is used both for absorbed PAR in photosynthesis and as one component of the energy balance; direct-NIR and diffuse-NIR contribute only to the energy balance through the returned albedos.

## Direct Beam Extinction

The direct-beam extinction coefficient `k_dir` is computed from the solar zenith angle and the leaf angle distribution parameter `xl`:

```
k_dir = G(μ) * Ω / μ
```

where `μ = cos(θ_sun)`, `G(μ)` is the projection of unit leaf area in the sun direction (Ross-Goudriaan form using `xl`), and `Ω` is the PFT clumping index `clumping_index(ft)`. A minimum cosine `cosz = max(0.001, solar_zenith_angle)` is enforced at `EDSurfaceAlbedoMod.F90:353` to prevent division by zero near sunset.

The Ross-Goudriaan `G(μ)` formulation uses:

- `phi1 = 0.5 - 0.633 * xl - 0.330 * xl^2`
- `phi2 = 0.877 * (1 - 2 * phi1)`
- `G(μ) = phi1 + phi2 * μ`

See `EDSurfaceAlbedoMod.F90:353-361`.

## Diffuse Transmittance

Diffuse transmittance `tr_dif_z` is obtained by numerically integrating the direct-beam extinction over sky hemispheres, using **9 sky zenith angles from 5° to 85° in 10° increments**, weighted by `sin(angle)·cos(angle)` (`EDSurfaceAlbedoMod.F90:404-421`). This is the standard hemispherical-integration approximation used in CLM's Norman two-stream formulation.

## Sunlit / Shaded Leaf Fractions

For canopy layer `L`, PFT `ft`, and vertical layer `iv`, the sunlit leaf fraction is:

```
f_sun(L,ft,iv) = ftweight(L,ft,iv) * exp(-k_dir * LAI_cumulative)
```

where `LAI_cumulative` runs from the canopy top to the center of `(L,ft,iv)` and `ftweight` is the canopy area profile weight. The shaded fraction is `1 - f_sun`. See `EDSurfaceAlbedoMod.F90:485-528`.

`ED_SunShadeFracs` subsequently integrates these sunlit/shaded profiles together with the solved diffuse and direct radiation fields to produce the per-leaf-layer absorbed PAR arrays `ed_parsun_z` and `ed_parsha_z` consumed by `FatesPlantRespPhotosynthMod`.

## Iterative Diffuse Flux Solution

Because upward and downward diffuse radiation are coupled through multiple scattering, the solver uses an iterative scheme (`EDSurfaceAlbedoMod.F90:603-820`):

1. **Initialization phase** (`lines 603-697`): first-pass top-down and bottom-up sweeps seed the upward and downward diffuse fields.
2. **Iteration phase** (`lines 698-820`): successive sweeps update fluxes until convergence.

Convergence tolerance is `1e-9` (line 247) and the iteration cap is 50 (around line 707). The exit test checks that the maximum per-layer change in diffuse flux is below the tolerance.

## Canopy Inputs from `EDCanopyStructureMod`

The radiation solver relies on geometry computed by `EDCanopyStructureMod`:

| Field | Description |
| --- | --- |
| `elai_profile(L,ft,iv)` | Exposed leaf area index profile |
| `esai_profile(L,ft,iv)` | Exposed stem area index profile |
| `canopy_area_profile(L,ft,iv)` | Crown area weight per leaf layer |
| `NCL_p` | Number of canopy layers in the patch |
| `nrad(L,ft)` | Number of vertical radiation layers per canopy layer and PFT |

The per-layer absorption coefficient is constructed from leaf and stem optical properties at `EDSurfaceAlbedoMod.F90:315-343`.

## Optical Parameters (PFT-specific)

| Parameter | Dimensions | Description | Typical range |
| --- | --- | --- | --- |
| `rhol(ft,ib)` | (numpft, maxSWb) | Leaf reflectance | 0.07-0.35 (vis), 0.35-0.58 (NIR) |
| `taul(ft,ib)` | (numpft, maxSWb) | Leaf transmittance | 0.05-0.10 (vis), 0.10-0.25 (NIR) |
| `rhos(ft,ib)` | (numpft, maxSWb) | Stem reflectance | 0.16-0.39 (vis), 0.39-0.58 (NIR) |
| `taus(ft,ib)` | (numpft, maxSWb) | Stem transmittance | ~0.001 both bands |
| `xl(ft)` | (numpft) | Leaf angle distribution | -0.4 to 0.6 (0 = spherical) |
| `clumping_index(ft)` | (numpft) | Foliage clumping (Ω) | 0.75-0.85 for trees |

Parameter sources:

- `rhol`, `rhos`, `taul`, `taus` — `fates_rad_leaf_rhovis`, `fates_rad_leaf_rhonir`, `fates_rad_leaf_tauvis`, `fates_rad_leaf_taunir` and the corresponding `stem_rho*`, `stem_tau*` variants in `fates_params_default.cdl:479-508`.
- `xl` — `fates_rad_leaf_xl`.
- `clumping_index` — `fates_rad_clumping` (or equivalent).

## Outputs to the Host Land Model

Passed back through `bc_out`:

| Field | Description |
| --- | --- |
| `albd_parb(ifp, ib)` | Direct-beam albedo by patch and waveband |
| `albi_parb(ifp, ib)` | Diffuse albedo by patch and waveband |
| `fabd_parb(ifp, ib)` | Fraction of direct radiation absorbed by vegetation |
| `fabi_parb(ifp, ib)` | Fraction of diffuse radiation absorbed by vegetation |
| `ftdd_parb(ifp, ib)` | Direct-to-direct transmission to soil |
| `ftid_parb(ifp, ib)` | Direct-to-diffuse transmission to soil |
| `ftii_parb(ifp, ib)` | Diffuse-to-diffuse transmission to soil |
| `fsun_pa(ifp)` | Canopy-integrated sunlit leaf fraction |
| `laisun_pa(ifp)` | Sunlit LAI |
| `laisha_pa(ifp)` | Shaded LAI |

These feed both the host energy-balance solver (NIR and visible albedos) and the FATES photosynthesis driver (sun/shade PAR profiles).

## Edge Cases

- **Canopy snow** — when `fcansno > 0`, leaf and stem optical properties are blended with snow values (`ρ_snow ≈ 0.8` vis, `≈ 0.55` NIR; `τ_snow ≈ 0`). See `EDSurfaceAlbedoMod.F90:60-65, 330-334`.
- **Canopy gaps** — when the understory is incomplete (`sum(ftweight(L,:,1)) < 1`), radiation passes directly through to lower layers or soil (`lines 647-651, 687-695, 812-818`).
- **Bare patch** — if `maxval(nrad(1,:)) == 0`, the Norman solver is skipped: absorbed = 0, patch albedo = ground albedo, transmittance = 1.0 (lines 136-150).
- **Night / low sun** — when `solar_zenith_flag` is false the whole routine is bypassed; the host passes that flag via `bc_in(s)%filter_vegzen_pa(ifp)` (lines 120-126).

## Energy Conservation

After the iteration, `PatchNormanRadiation` verifies energy balance at `lines 1002-1008`:

- Direct: `fabd + albd + ftdd + ftid = 1`
- Diffuse: `fabi + albi + ftii = 1`

Residuals above the tolerance trigger a tiered correction (`lines 1032-1096`) that proportionally redistributes the imbalance among absorbed, reflected, and transmitted fractions to preserve global conservation. The normalized residual is stored in `currentPatch%radiation_error` for diagnostic output.

## Linking to Photosynthesis

Absorbed PAR fractions are combined with the incoming direct and diffuse PAR from `bc_in(s)%solad_parb(ifp, ipar)` and `bc_in(s)%solai_parb(ifp, ipar)` in `ED_SunShadeFracs` to produce the sunlit/shaded leaf-layer absorbed PAR fields that drive leaf photosynthesis. See [Photosynthesis and Respiration](photosynthesis.md).

## Source References

- `biogeophys/EDSurfaceAlbedoMod.F90:1` — `module EDSurfaceRadiationMod` statement
- `biogeophys/EDSurfaceAlbedoMod.F90:27-32` — stream and waveband indices
- `biogeophys/EDSurfaceAlbedoMod.F90:68-173` — `ED_Norman_Radiation` driver
- `biogeophys/EDSurfaceAlbedoMod.F90:178-1104` — `PatchNormanRadiation`
- `biogeophys/EDSurfaceAlbedoMod.F90:247, 703-820` — diffuse iteration tolerance and limits
- `biogeophys/EDSurfaceAlbedoMod.F90:353-361` — direct beam extinction
- `biogeophys/EDSurfaceAlbedoMod.F90:404-421` — 9-angle diffuse integration
- `biogeophys/EDSurfaceAlbedoMod.F90:485-528` — sunlit/shaded fraction
- `biogeophys/EDSurfaceAlbedoMod.F90:1002-1096` — energy conservation and correction
- `biogeophys/EDSurfaceAlbedoMod.F90:1108-1291` — `ED_SunShadeFracs`
- `parameter_files/fates_params_default.cdl:479-508` — default optical parameters
