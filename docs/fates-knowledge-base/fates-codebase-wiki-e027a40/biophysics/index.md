---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# Biophysical Processes

## Purpose and Scope

This page is the overview for FATES biophysical processes: the physical exchange of energy, water, and CO2 between vegetation and the atmosphere. These calculations drive photosynthesis, transpiration, and the energy balance seen by the host land model. For interactions with growth and allocation, see [Plant Growth and Physiology](../plant-physiology/index.md).

Four tightly coupled processes are covered in this section:

- [Radiation Transfer and Albedo](radiation.md) — Norman two-stream solver and the alternative Two-Stream MLPE solver, dispatched from a new `radiation/` subdirectory.
- [Photosynthesis and Respiration](photosynthesis.md) — Farquhar/Collatz photosynthesis with Ball-Berry or Medlyn stomatal coupling; inner Ci solver lives in the new `LeafBiophysicsMod`.
- [Transpiration and Soil Moisture Stress](transpiration.md) — empirical BTRAN pathway in `EDBtranMod`.
- [Plant Hydraulics](hydraulics/index.md) — mechanistic soil-plant-atmosphere water transport.

## Sub-daily Timing

All four processes run on the **sub-daily flux loop** of the host land model (typically a 30-minute ELM/CLM flux timestep), not on the FATES daily dynamics loop. Host-side dispatch:

- Radiation (per radiation timestep): `alm_fates%wrap_canopy_radiation(...)` from ELM-side `components/elm/src/biogeophys/SurfaceAlbedoMod.F90` (line 967 at d40b843) calls `FatesNormalizedCanopyRadiation` in `radiation/FatesRadiationDriveMod.F90:61`.
- BTRAN: `alm_fates%wrap_btran(...)` from ELM-side `components/elm/src/biogeophys/CanopyFluxesMod.F90` (line 591 at d40b843).
- Photosynthesis: `alm_fates%wrap_photosynthesis(...)` from the same ELM file (line 911) calls `FatesPlantRespPhotosynthDrive`.
- Hydraulics: `alm_fates%wrap_hydraulics_drive(...)` from the same ELM file (line 1322) calls `hydraulics_drive`.

`FatesSunShadeFracs` (`FatesRadiationDriveMod.F90:235`) is also invoked sub-daily to compute the absorbed PAR profiles consumed by photosynthesis.

## Module Organization

| Module | File | Primary functions | Key outputs |
| --- | --- | --- | --- |
| `FatesRadiationDriveMod` | `radiation/FatesRadiationDriveMod.F90` | Driver dispatch (Norman vs MLPE), sun/shade partitioning | `albd_parb`, `albi_parb`, `fabd`, `fabi`, `f_sun`, `ed_parsun_z`, `ed_parsha_z` |
| `FatesNormanRadMod` | `radiation/FatesNormanRadMod.F90` | Norman per-patch two-stream solve | per-layer absorbed/transmitted/reflected fluxes |
| `TwoStreamMLPEMod` | `radiation/TwoStreamMLPEMod.F90` | Multi-Layer Perimeter-Element two-stream alternative | same fields, alternative solver |
| `FatesPlantRespPhotosynthMod` | `biogeophys/FatesPlantRespPhotosynthMod.F90` | Public driver `FatesPlantRespPhotosynthDrive`, maintenance respiration | `gpp_tstep`, `resp_tstep`, `psn_z` |
| `LeafBiophysicsMod` | `biogeophys/LeafBiophysicsMod.F90` | Inner Ci solver (`LeafLayerPhotosynthesis`, `CiFunc`, `CiBisection`), Ball-Berry/Medlyn, biophysical-rate scaling | `anet`, `agross`, `gs`, `vcmax`, `jmax` |
| `FatesLeafBiophysParamsMod` | `biogeophys/FatesLeafBiophysParamsMod.F90` | Holds `lb_params` leaf biophysics parameter struct | - |
| `EDBtranMod` | `biogeophys/EDBtranMod.F90` | Empirical soil moisture stress factor and root uptake profile | `btran_ft`, `btran_pa`, `rootr_pasl` |
| `FatesPlantHydraulicsMod` | `biogeophys/FatesPlantHydraulicsMod.F90` | Soil-plant-atmosphere water transport, cohort `btran` | `psi_ag`, `th_ag`, `ftc_ag`, cohort `btran`, `qtop` |
| `FatesBstressMod` | `biogeophys/FatesBstressMod.F90` | Salinity stress factor | `bstress_sal_ft` |
| `FatesHydroWTFMod` | `biogeophys/FatesHydroWTFMod.F90` | Water retention (`wrf_*`) and conductivity (`wkf_*`) functions | `th_from_psi`, `psi_from_th`, `ftc_from_psi` |

The legacy `biogeophys/EDSurfaceAlbedoMod.F90` (declaring `module EDSurfaceRadiationMod`) no longer exists at e027a40. The radiation code has been moved to a dedicated `radiation/` subdirectory with new module names, and the host call has changed from `wrap_albedo` to `wrap_canopy_radiation`.

## Execution Sequence within a Sub-daily Step

For a given patch on a given timestep:

1. `FatesNormalizedCanopyRadiation` is called from the surface-albedo path. It dispatches per-patch on `hlm_radiation_model` (`FatesRadiationDriveMod.F90:145`) to either `PatchNormanRadiation` (`norman_solver = 1`) or the two-stream MLPE `Solve` routine (`twostr_solver = 2`). See [Radiation Transfer and Albedo](radiation.md).
2. `FatesSunShadeFracs` (`FatesRadiationDriveMod.F90:235`) integrates the solved fields with incoming `solad_parb` / `solai_parb` to populate `cpatch%ed_parsun_z` and `cpatch%ed_parsha_z` (lines 334-339).
3. `wrap_btran` triggers `btran_ed` (or, when hydraulics is active, `BTranForHLMDiagnosticsFromCohortHydr`), updating `btran_ft` and `rootr_pasl`.
4. `FatesPlantRespPhotosynthDrive` solves the leaf-level photosynthesis-stomatal-conductance system using `btran_eff` (multiplied by `bstress_sal_ft` when salinity is on) and the absorbed-PAR profile.
5. `hydraulics_drive` (if `hlm_use_planthydro == itrue`) updates plant and rhizosphere water potentials and refreshes the cohort `btran` for the next iteration of the canopy-flux loop.

## Environmental Boundary Conditions

Biophysics uses these host-supplied fields on the `bc_in_type` structure (declared in `main/FatesInterfaceTypesMod.F90`):

- `bc_in(s)%solad_parb(ifp,ib)` — direct beam irradiance by patch and waveband
- `bc_in(s)%solai_parb(ifp,ib)` — diffuse irradiance by patch and waveband
- `bc_in(s)%smp_sl(j)` — soil matric potential by layer, **in mm**
- `bc_in(s)%h2o_liqvol_sl(j)` — volumetric soil moisture by layer
- `bc_in(s)%watsat_sl(j)` — saturated porosity by layer
- `bc_in(s)%eff_porosity_sl(j)` — unfrozen porosity by layer
- `bc_in(s)%t_veg_pa(ifp)` — canopy temperature [K]
- `bc_in(s)%eair_pa(ifp)` — vapour pressure of air [Pa]
- `bc_in(s)%tempk_sl(j)` — soil temperature by layer [K]

## Water Transport Modes

FATES supports two water-stress modes selected at HLM compile/startup time.

### Non-hydraulic mode (empirical BTRAN)

Active when `hlm_use_planthydro == ifalse`. Uses the piecewise-linear ramp in `EDBtranMod.btran_ed` controlled by:

- `fates_nonhydro_smpso(ft)` — soil water potential at full stomatal opening [mm] (default −66000 mm, all 14 PFTs)
- `fates_nonhydro_smpsc(ft)` — soil water potential at full stomatal closure [mm] (default −255000 mm, all 14 PFTs)

Both parameters are in **millimetres**, consistent with the host `smp_sl` units, and `smpsc` is more negative than `smpso`. Verified at `parameter_files/fates_params_default.json:1104-1116`. See [Transpiration and Soil Moisture Stress](transpiration.md) for the exact formula and a common unit-swap pitfall.

### Hydraulic mode

Active when `hlm_use_planthydro == itrue`. Solves the compartmentalized water-transport equations via one of three solvers selected at the **HLM namelist** (NOT the FATES parameter file at e027a40):

| `hlm_hydr_solver` | Constant name | Method |
| --- | --- | --- |
| 1 | `hydr_solver_1DTaylor` | Sequential layer-by-layer implicit Taylor |
| 2 | `hydr_solver_2DPicard` | Fixed-point iteration over full plant-soil system |
| 3 | `hydr_solver_2DNewton` | Newton-Raphson on full plant-soil system |

Constants are declared in `main/FatesHydraulicsMemMod.F90:19-21`. The HLM passes the namelist key `hydr_solver` through `FatesInterfaceMod.F90:2133-2137`, which stores it in `hlm_hydr_solver` (declared in `FatesInterfaceTypesMod.F90:154`). Default is `unset_int`; FATES aborts at startup with "FATES hydro solver is unset" if the namelist is not set (`FatesInterfaceMod.F90:1867-1869`). Solver dispatch at `FatesPlantHydraulicsMod.F90:2582-2622`. All three solvers are actively dispatched; **`fates_hydro_solver` is no longer a parameter-file entry** (verified absent in `fates_params_default.json`). See [Plant Hydraulics](hydraulics/index.md).

## Water Transfer Functions (WTFs)

Plant compartments and rhizosphere shells are characterized by water retention (WRF) and water conductivity (WKF) functions implemented in `FatesHydroWTFMod`. For plant tissues, `InitHydroGlobals` (`FatesPlantHydraulicsMod.F90:6248-6376`) only instantiates two forms:

- TFS (`tfs_type = 1`) — default, used for all four plant media in the shipped parameter file (`fates_hydro_htftype_node = [1,1,1,1]` at `fates_params_default.json:61-67`).
- Van Genuchten (`van_genuchten_type = 2`) — available but not the default.

Any other value of `hydr_htftype_node` for a plant medium triggers `endrun` (`case default` at `FatesPlantHydraulicsMod.F90:6323-6325`). **Campbell is not a valid plant WTF option** despite a legacy source comment (`FatesPlantHydraulicsMod.F90:200-206`) saying it "could technically be used". The soil rhizosphere, by contrast, is hard-coded to Campbell (`soil_wrf_type = campbell_type` at `FatesPlantHydraulicsMod.F90:214-215`).

Each plant organ has its own WTF parameters defined in the PFT file:

| Organ | `p50` | `avuln` | `kmax` | `thetas`/`resid` | `pinot`/`epsil` (TFS) |
| --- | --- | --- | --- | --- | --- |
| Leaf (`leaf_p_media = 1`) | `hydr_p50_node(ft,1)` | `hydr_avuln_node(ft,1)` | `hydr_kmax_node(ft,1)` | yes | yes |
| Stem (`stem_p_media = 2`) | `hydr_p50_node(ft,2)` | `hydr_avuln_node(ft,2)` | `hydr_kmax_node(ft,2)` | yes | yes |
| Transporting root (`troot_p_media = 3`) | `hydr_p50_node(ft,3)` | `hydr_avuln_node(ft,3)` | `hydr_kmax_node(ft,3)` | yes | yes |
| Absorbing root (`aroot_p_media = 4`) | `hydr_p50_node(ft,4)` | `hydr_avuln_node(ft,4)` | `hydr_kmax_node(ft,4)` | yes | yes |

The stomatal conductance vulnerability curve is always sigmoidal/TFS using `hydr_p50_gs(ft)` and `hydr_avuln_gs(ft)`, not tied to `hydr_htftype_node` (see `FatesPlantHydraulicsMod.F90:6371-6376`).

## Representative Parameters

### Photosynthesis (PFT-indexed; arrays now length 14)

| Parameter | Description | Units | Default(s) |
| --- | --- | --- | --- |
| `fates_leaf_vcmax25top` | Maximum carboxylation rate at 25C, canopy top | umol CO2 m-2 s-1 | 38 to 86 across 14 PFTs |
| `fates_leaf_jmaxha` | Jmax activation energy | J mol-1 | 43540 (all PFTs) |
| `fates_leaf_jmaxhd` | Jmax deactivation energy | J mol-1 | 152040 (all PFTs) |
| `fates_leaf_stomatal_slope_medlyn` | Medlyn g1 | kPa^0.5 | 1.6 to 5.3 |
| `fates_leaf_stomatal_slope_ballberry` | Ball-Berry slope | unitless | 8 (all PFTs) |
| `fates_leaf_stomatal_intercept` | Minimum stomatal conductance (g0) | umol H2O m-2 s-1 | 10000 (40000 for C4) |
| `fates_leaf_stomatal_btran_model` | btran-application switch on stomatal terms (per PFT) | index | 1 (apply to gs0 only) |
| `fates_leaf_agross_btran_model` | btran-application switch on Vcmax/Jmax (per PFT) | index | 1 (apply to vcmax only) |

### Hydraulics

| Parameter | Description | Units |
| --- | --- | --- |
| `fates_hydro_p50_node` | psi at 50% conductivity loss | MPa |
| `fates_hydro_avuln_node` | Vulnerability curve shape | unitless |
| `fates_hydro_kmax_node` | Maximum xylem conductivity | kg m-1 MPa-1 s-1 |
| `fates_hydro_epsil_node` | Bulk elastic modulus (TFS) | MPa |
| `fates_hydro_psi0` | Capillary reference potential (TFS) | MPa |
| `fates_hydro_psicap` | Capillary exhaustion potential (TFS) | MPa |
| `fates_hydro_pitlp_node` | Turgor loss point (TFS) | MPa |
| `fates_hydro_fcap_node` | Capillary fraction of non-residual water (TFS) | unitless |
| `fates_hydro_k_lwp` | Inner-leaf-humidity scaling for stomata | unitless |
| `fates_hydro_htftype_node` | Plant WTF selector (1=TFS, 2=VG only) | - |

`fates_hydro_solver` does not exist in the parameter file at e027a40. Solver selection is HLM-side via the namelist key `hydr_solver`.

### Radiation

| Parameter | Description | Units |
| --- | --- | --- |
| `fates_rad_leaf_rhovis` / `rhonir` | Leaf reflectance (vis/NIR) | fraction |
| `fates_rad_leaf_tauvis` / `taunir` | Leaf transmittance (vis/NIR) | fraction |
| `fates_rad_leaf_xl` | Leaf angle distribution | unitless |
| `fates_rad_clumping` | Foliage clumping index | unitless |

Radiation solver selection is HLM-side via the namelist key `radiation_model` (`FatesInterfaceMod.F90:2152-2154`), stored in `hlm_radiation_model` (`FatesInterfaceTypesMod.F90:169`).

### Transpiration (BTRAN)

| Parameter | Description | Units | Default |
| --- | --- | --- | --- |
| `fates_nonhydro_smpso` | Soil potential at full stomatal opening | **mm** | -66000 |
| `fates_nonhydro_smpsc` | Soil potential at full stomatal closure | **mm** | -255000 |

## Numerical Considerations

### Photosynthesis inner loop

The coupled `(ci, an, gs)` system is iterated inside `LeafLayerPhotosynthesis` in `LeafBiophysicsMod.F90:1232-1411` (outer iteration loop at `:1354-1399`). The outer iteration applies a residual-based update step `ci = ci0 - fval` on the residual `fval = ci_input - ci_predicted` (Pa) returned by `CiFunc`. Convergence test (`LeafBiophysicsMod.F90:1380-1383`):

```fortran
if (abs(fval) <= ci_tol ) then
   loop_continue = .false.
   exit iter_loop
end if
```

with `max_iters = 10` (`LeafBiophysicsMod.F90:1330`) and `ci_tol = 0.5_r8` Pa (declared at `FatesPlantRespPhotosynthMod.F90:295` and passed through). When the outer loop exhausts its iteration budget (or `force_bisection = .true.` is set for testing at line 1327), control passes to `CiBisection` (`LeafBiophysicsMod.F90:1083-1228`) with its own `max_iters = 200` (line 1129) and the same residual-on-Pa tolerance. The pre-e85d997 fixed-point loop with `niter == 5` cutoff and `2e-6 ppm` tolerance no longer exists.

### Hydraulic mass balance

`max_wb_step_err = 2.e-6_r8 kg` per plant per sub-step (`FatesPlantHydraulicsMod.F90:242`, with the inline comment "original is 1.e-7_r8, Junyan changed to 2.e-6_r8" intact). Three error pools in `ed_site_hydr_type` (`errh2o_hyd`, `h2oveg_growturn_err`, `h2oveg_hydro_err`) accumulate the residuals per site.

### Conservation checks in radiation

`PatchNormanRadiation` verifies energy balance after the iterative solve at `FatesNormanRadMod.F90:881-887`, with tiered correction at `:911-961` when residuals exceed `1.e-9` (small) or `0.15` (large). The patch diagnostic `currentPatch%rad_error` stores the normalized residual per waveband for offline checking.

## Source References

- `biogeophys/FatesPlantRespPhotosynthMod.F90:295, 510-545, 551-556` — driver, btran assignment, salinity overlay, DecayCoeffVcmax
- `biogeophys/LeafBiophysicsMod.F90:1276-1411, 1085-1224, 165-178` — Ci-solve outer/inner loops, btran-application constants
- `biogeophys/FatesPlantHydraulicsMod.F90:242, 2582-2622, 6248-6376, 214-215` — error tolerance, solver dispatch, WTF allocation, soil hard-coding
- `radiation/FatesRadiationDriveMod.F90:61-231, 145-223, 235-448` — driver, solver dispatch, sun/shade
- `radiation/FatesNormanRadMod.F90:62-984` — Norman per-patch solve
- `radiation/TwoStreamMLPEMod.F90` — alternative two-stream MLPE solver (1783 lines)
- `radiation/FatesRadiationMemMod.F90:16-17` — solver constants `norman_solver`, `twostr_solver`
- `biogeophys/EDBtranMod.F90:88-262` — `btran_ed`
- `main/FatesHydraulicsMemMod.F90:19-21, 35-39, 52-57` — solver constants, compartment counts, media indices
- `main/FatesInterfaceTypesMod.F90:154, 169` — `hlm_hydr_solver`, `hlm_radiation_model`
- `main/FatesInterfaceMod.F90:1867-1869, 1882-1884, 2116-2154` — namelist dispatch and unset-checks
- `parameter_files/fates_params_default.json:61-67, 887-892, 831-836, 1104-1116` — htftype, btran switches, smpsc/smpso defaults (all 14 PFTs)
- ELM-side `components/elm/src/biogeophys/CanopyFluxesMod.F90` (lines 591, 911, 1322 at d40b843) — host wrap calls
- ELM-side `components/elm/src/biogeophys/SurfaceAlbedoMod.F90` (line 967 at d40b843) — host `wrap_canopy_radiation` call
