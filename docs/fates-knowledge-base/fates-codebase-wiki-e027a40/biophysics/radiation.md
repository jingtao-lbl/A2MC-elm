---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# Radiation Transfer and Albedo

## Purpose and Scope

This page documents the radiation transfer and albedo calculations in FATES. At e027a40 FATES ships **two** alternative canopy-radiation solvers:

- **Norman (1979) two-stream**, the historical default. Implemented in `radiation/FatesNormanRadMod.F90`.
- **Two-Stream Multi-Layer Perimeter-Element (MLPE)**, NEW. Implemented in `radiation/TwoStreamMLPEMod.F90` (1783 lines).

Both solvers compute the absorption, transmission, and reflection of direct-beam and diffuse shortwave radiation through the multi-layered canopy, and supply sunlit and shaded leaf area indices, the absorbed photosynthetically active radiation (PAR) profile, and the patch-level direct and diffuse albedos returned to the host land model.

For the consumption of radiation outputs by the leaf biochemistry, see [Photosynthesis and Respiration](photosynthesis.md). For canopy layering and competition that set up the geometry used by the radiation solver, see [Canopy Structure and Competition](../canopy-structure/index.md).

## Module Reorganization at e027a40

The legacy `biogeophys/EDSurfaceAlbedo` module from earlier tags (which declared `module EDSurfaceRadiationMod`) **no longer exists**. Radiation now lives in a dedicated `radiation/` subdirectory with separate driver, solver, and memory modules:

| Module | File | Purpose |
| --- | --- | --- |
| `FatesRadiationDriveMod` | `radiation/FatesRadiationDriveMod.F90` (450 lines) | Driver dispatching to the chosen solver, plus sun/shade fraction post-processing |
| `FatesNormanRadMod` | `radiation/FatesNormanRadMod.F90` (987 lines) | Norman per-patch two-stream solve |
| `TwoStreamMLPEMod` | `radiation/TwoStreamMLPEMod.F90` (1783 lines) | Multi-Layer Perimeter-Element two-stream alternative |
| `FatesRadiationMemMod` | `radiation/FatesRadiationMemMod.F90` (61 lines) | Solver constants, waveband indices, snow optical defaults |
| `FatesTwoStreamUtilsMod` | `radiation/FatesTwoStreamUtilsMod.F90` (627 lines) | Utility routines for the MLPE solver |

Public driver entry points (`FatesRadiationDriveMod.F90:52-53`):

- `FatesNormalizedCanopyRadiation(sites, bc_in, bc_out)` — top-level driver, lines 61-231. Replaces the older `ED_Norman_Radiation`.
- `FatesSunShadeFracs(nsites, sites, bc_in, bc_out)` — sun/shade integration, lines 235-448. Replaces the older `ED_SunShadeFracs`.

The host-side wrap call has changed accordingly. ELM now calls `alm_fates%wrap_canopy_radiation(...)` from ELM-side `components/elm/src/biogeophys/SurfaceAlbedoMod.F90` (line 967 at d40b843), replacing the older `wrap_albedo` path.

## Solver Selection

Solver dispatch is via the **HLM namelist** key `radiation_model`, NOT a parameter-file entry. The host-side dispatch is in `FatesInterfaceMod.F90:2152-2154`, which stores the selected value in module-scope `hlm_radiation_model` (declared at `FatesInterfaceTypesMod.F90:169`). FATES aborts at startup with "radiation model is unset" if the namelist is not set (`FatesInterfaceMod.F90:1882-1884`).

Solver constants in `radiation/FatesRadiationMemMod.F90:16-17`:

```fortran
integer, parameter, public :: norman_solver = 1
integer, parameter, public :: twostr_solver = 2
```

Per-patch dispatch in `FatesRadiationDriveMod.F90:145-223`:

```fortran
select case(hlm_radiation_model)
case(norman_solver)
   call PatchNormanRadiation(currentPatch, ...)
case(twostr_solver)
   associate( twostr => currentPatch%twostr )
     call twostr%CanopyPrep(currentPatch%fcansno)
     call twostr%ZenithPrep(sites(s)%coszen)
     do ib = 1,num_swb
        call twostr%Solve(ib, normalized_upper_boundary, ...)
     end do
   end associate
end select
```

`FatesSunShadeFracs` similarly branches on `hlm_radiation_model` (`FatesRadiationDriveMod.F90:283`) — Norman uses `cpatch%f_sun` already populated by the radiation solve; the MLPE path calls `FatesPatchFSun` to compute the sunlit/shaded split per scattering element.

## Radiation Streams and Wavebands

Both solvers use the same stream and waveband indices, declared in `FatesRadiationMemMod.F90:21-45`:

- **Streams** — `idirect = 1` (direct beam) and `idiffuse = 2` (diffuse). `num_rad_stream_types = 2`.
- **Wavebands** — `ivis = 1` / `ipar = ivis` (visible/PAR, 400-700 nm) and `inir = 2` (near-infrared, 700-2500 nm). `num_swb = 2`.

Direct-PAR is used both for absorbed PAR in photosynthesis and as one component of the energy balance; direct-NIR and diffuse-NIR contribute only to the energy balance through the returned albedos.

## Norman Solver Internals

`PatchNormanRadiation` (`FatesNormanRadMod.F90:62-984`) is the per-patch solve. Convergence tolerance for the iterative diffuse flux loop is hard-coded at line 133:

```fortran
real(r8),parameter :: tolerance = 0.000000001_r8
```

### Direct beam extinction

The direct-beam extinction coefficient `k_dir` is computed from the solar zenith angle and the leaf angle distribution parameter `xl`:

```
k_dir(ft) = clumping_index(ft) * gdir / sin(sb)
```

with `gdir = phi1b(ft) + phi2b(ft) * sin(sb)` (Ross-Goudriaan G-function), and `phi1b`, `phi2b` derived from `xl(ft)`:

```fortran
phi1b(ft) = 0.5_r8 - 0.633_r8*xl(ft) - 0.330_r8*xl(ft)*xl(ft)
phi2b(ft) = 0.877_r8 * (1._r8 - 2._r8*phi1b(ft))
gdir      = phi1b(ft) + phi2b(ft) * sin(sb)
k_dir(ft) = clumping_index(ft) * gdir / sin(sb)
```

(`FatesNormanRadMod.F90:242-247`). A minimum cosine `cosz = max(0.001_r8, coszen)` is enforced at line 239 to prevent division by zero near sunset.

### Diffuse transmittance

Diffuse transmittance `tr_dif_z` is obtained by numerically integrating the direct-beam extinction over sky hemispheres, using **9 sky zenith angles from 5 deg to 85 deg in 10 deg increments**, weighted by `sin(angle) * cos(angle)` (`FatesNormanRadMod.F90:295-305`). This is the standard hemispherical-integration approximation used in CLM's Norman two-stream formulation.

### Iterative diffuse flux solution

Because upward and downward diffuse radiation are coupled through multiple scattering, the solver uses an iterative scheme (`FatesNormanRadMod.F90:589-706`):

1. **Initialization** (lines 589 onward): first-pass top-down and bottom-up sweeps seed the upward and downward diffuse fields.
2. **Iteration**: `do while(irep == 1 .and. iter < 50)` loop at line 593, with the exit flag `irep` set whenever any per-layer flux change exceeds `tolerance` (lines 642-644 and 688-690).

Iteration cap is **50**. The exit test checks that the maximum per-layer change in diffuse flux is below `1e-9`.

### Energy conservation correction

After convergence, the routine verifies energy balance per waveband (`FatesNormanRadMod.F90:881-887`):

- Direct: `forc_dir = fabd + albd + sabs_dir`
- Diffuse: `forc_dif = fabi + albi + sabs_dif`

When the residual `error` exceeds `1e-9` but is below `0.15`, it is folded back into the patch albedo (`:914-922` for direct, `:939-941` for diffuse). When `|error| > 0.15` the residual is logged (debug only) and still added back to the albedo (`:924-936`). The normalized residual is stored in `currentPatch%rad_error(ib)` for diagnostic output (`:893-894`).

## Two-Stream MLPE Solver Internals

The MLPE solver (`radiation/TwoStreamMLPEMod.F90`, 1783 lines) is an alternative implementation that organizes scattering elements into per-layer "perimeter-element" columns. Its public entry on the patch-attached `twostr` object includes:

- `CanopyPrep(fcansno)` — pre-solve geometry update.
- `ZenithPrep(coszen)` — zenith-dependent setup.
- `Solve(ib, normalized_upper_boundary, ...)` — per-waveband solve.
- `GetRb(cl, icol, ib, vai_top)`, `GetRdDn(...)`, `GetRdUp(...)` — diagnostic profile getters used by `FatesNormalizedCanopyRadiation` to populate `currentPatch%nrmlzd_parprof_pft_dir_z` and `nrmlzd_parprof_pft_dif_z` (lines 202-220).

The MLPE solver call returns the same `albd_parb`, `albi_parb`, `fabd_parb`, `fabi_parb`, `ftdd_parb`, `ftid_parb`, `ftii_parb` outputs as the Norman path. Its internal layering, scattering-element model, and validation are documented in the MLPE module header.

`FatesSunShadeFracs` handles the MLPE branch separately (`FatesRadiationDriveMod.F90:368-440`), calling `FatesPatchFSun` (in `FatesTwoStreamUtilsMod`) to compute the sunlit fraction per layer/PFT/leaf-layer.

## Sunlit / Shaded Leaf Fractions

After the radiation solve, `FatesSunShadeFracs` (`FatesRadiationDriveMod.F90:235-448`) integrates the solved sun/shade absorption fields with the incoming direct and diffuse PAR forcing to produce the per-leaf-layer absorbed PAR consumed by photosynthesis (`:334-339`):

```fortran
cpatch%ed_parsun_z(cl,ft,iv) = bc_in(s)%solad_parb(ifp,ipar)*cpatch%fabd_sun_z(cl,ft,iv) + ...
cpatch%ed_parsha_z(cl,ft,iv) = ...
```

`cpatch%f_sun(cl,ft,iv)` is populated upstream — by `PatchNormanRadiation` for the Norman path, by `FatesPatchFSun` for the MLPE path. The shaded fraction is `1 - f_sun`.

## Optical Parameters (PFT-specific, length 14 at e027a40)

| Parameter | Dimensions | Description | Typical range |
| --- | --- | --- | --- |
| `rhol(ft,ib)` | (numpft, num_swb) | Leaf reflectance | 0.07-0.35 (vis), 0.35-0.58 (NIR) |
| `taul(ft,ib)` | (numpft, num_swb) | Leaf transmittance | 0.05-0.10 (vis), 0.10-0.25 (NIR) |
| `rhos(ft,ib)` | (numpft, num_swb) | Stem reflectance | 0.16-0.39 (vis), 0.39-0.58 (NIR) |
| `taus(ft,ib)` | (numpft, num_swb) | Stem transmittance | ~0.001 both bands |
| `xl(ft)` | (numpft) | Leaf angle distribution | -0.4 to 0.6 (0 = spherical) |
| `clumping_index(ft)` | (numpft) | Foliage clumping (Omega) | 0.75-0.85 for trees |

Snow blending uses constants from `FatesRadiationMemMod.F90:49-55`:

```fortran
real(r8), public :: rho_snow(num_swb) = (/ 0.80_r8, 0.55_r8 /)
real(r8), public :: tau_snow(num_swb) = (/ 0.01_r8, 0.01_r8 /)
real(r8), public :: alb_ice(num_swb)  = (/ 0.80_r8, 0.55_r8 /)
```

## Canopy Inputs from `EDCanopyStructureMod`

The radiation solvers rely on geometry computed by `EDCanopyStructureMod`:

| Field | Description |
| --- | --- |
| `elai_profile(L,ft,iv)` | Exposed leaf area index profile |
| `esai_profile(L,ft,iv)` | Exposed stem area index profile |
| `canopy_area_profile(L,ft,iv)` | Crown area weight per leaf layer |
| `NCL_p` | Number of canopy layers in the patch |
| `nrad(L,ft)` | Number of vertical radiation layers per canopy layer and PFT |

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

- **Bare patch** — when the patch has `nocomp_pft_label == nocomp_bareground`, the entire solve is skipped and trivial outputs (albedo = 1, absorbed = 0) are written (`FatesRadiationDriveMod.F90:115-126`).
- **Night / low sun** — when `bc_in(s)%coszen <= 0`, the dispatch block at `:143` is bypassed entirely.
- **Canopy snow** — when `fcansno > 0` is passed in via the patch state, leaf and stem optical properties are blended with snow values inside `PatchNormanRadiation` (`FatesNormanRadMod.F90:217-220`).
- **Canopy gaps** — when the understory is incomplete (`sum(ftweight(L,:,1)) < 1`), radiation passes directly through to lower layers or soil (handled inside the iterative loop in `PatchNormanRadiation`).

## Linking to Photosynthesis

Absorbed PAR fractions are combined with the incoming direct and diffuse PAR from `bc_in(s)%solad_parb(ifp, ipar)` and `bc_in(s)%solai_parb(ifp, ipar)` in `FatesSunShadeFracs` to produce the sunlit/shaded leaf-layer absorbed PAR fields that drive leaf photosynthesis (`FatesRadiationDriveMod.F90:334-339`). See [Photosynthesis and Respiration](photosynthesis.md).

## Source References

- `radiation/FatesRadiationDriveMod.F90:52-53` — public entry points
- `radiation/FatesRadiationDriveMod.F90:61-231` — `FatesNormalizedCanopyRadiation`
- `radiation/FatesRadiationDriveMod.F90:145-223` — Norman/MLPE dispatch
- `radiation/FatesRadiationDriveMod.F90:235-448` — `FatesSunShadeFracs`
- `radiation/FatesNormanRadMod.F90:62-984` — `PatchNormanRadiation`
- `radiation/FatesNormanRadMod.F90:133` — Norman tolerance `1e-9`
- `radiation/FatesNormanRadMod.F90:242-247` — direct beam extinction (Ross-Goudriaan)
- `radiation/FatesNormanRadMod.F90:295-305` — 9-angle diffuse integration
- `radiation/FatesNormanRadMod.F90:589-706` — iterative diffuse flux loop (cap 50)
- `radiation/FatesNormanRadMod.F90:881-984` — energy conservation and correction
- `radiation/TwoStreamMLPEMod.F90` — MLPE solver (1783 lines)
- `radiation/FatesRadiationMemMod.F90:16-17` — `norman_solver`, `twostr_solver` constants
- `main/FatesInterfaceMod.F90:1882-1884, 2152-2154` — namelist dispatch and unset-check
- `main/FatesInterfaceTypesMod.F90:169` — `hlm_radiation_model`
- ELM-side `components/elm/src/biogeophys/SurfaceAlbedoMod.F90` (line 967 at d40b843) — host `wrap_canopy_radiation` call
