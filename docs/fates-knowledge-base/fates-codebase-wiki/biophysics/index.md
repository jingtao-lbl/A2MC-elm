---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

# Biophysical Processes

## Purpose and Scope

This page is the overview for FATES biophysical processes: the physical exchange of energy, water, and CO₂ between vegetation and the atmosphere. These calculations drive photosynthesis, transpiration, and the energy balance seen by the host land model. For interactions with growth and allocation, see [Plant Growth and Physiology](../plant-physiology/index.md).

Four tightly coupled processes are covered in this section:

- [Radiation Transfer and Albedo](radiation.md) — Norman two-stream solver at the patch level.
- [Photosynthesis and Respiration](photosynthesis.md) — Farquhar-Collatz photosynthesis with Ball-Berry or Medlyn stomatal coupling.
- [Transpiration and Soil Moisture Stress](transpiration.md) — empirical BTRAN pathway in `EDBtranMod`.
- [Plant Hydraulics](hydraulics/index.md) — mechanistic soil-plant-atmosphere water transport.

## Sub-daily Timing

All four processes run on the **sub-daily flux loop** of the host land model (typically a 30-minute ELM/CLM flux timestep), not on the FATES daily dynamics loop. They are invoked from `elm/src/biogeophys/CanopyFluxesMod.F90`:

- `alm_fates%wrap_photosynthesis(...)` → `FatesPlantRespPhotosynthDrive` (around `CanopyFluxesMod.F90:880`)
- `alm_fates%wrap_hydraulics_drive(...)` → `hydraulics_drive` (at `CanopyFluxesMod.F90:1279`)

Radiation transfer runs once per radiation timestep (also sub-daily) through the `wrap_albedo` pathway that invokes `ED_Norman_Radiation` in `biogeophys/EDSurfaceAlbedoMod.F90`. `btran_ed` is driven as part of the photosynthesis coupling so that the stomatal multiplier is available on every iteration.

## Module Organization

| Module | File | Primary functions | Key outputs |
| --- | --- | --- | --- |
| `EDSurfaceRadiationMod` | `biogeophys/EDSurfaceAlbedoMod.F90` | Norman two-stream, albedo, sun/shade partitioning | `albd_parb`, `albi_parb`, `fabd`, `fabi`, `f_sun` |
| `FatesPlantRespPhotosynthMod` | `biogeophys/FatesPlantRespPhotosynthMod.F90` | Farquhar/Collatz photosynthesis, Ball-Berry/Medlyn, maintenance respiration | `gpp`, `rdark`, `rs_z`, cohort `gpp_tstep`/`resp_tstep` |
| `EDBtranMod` | `biogeophys/EDBtranMod.F90` | Empirical soil moisture stress factor and root uptake profile | `btran_ft`, `btran_pa`, `rootr_pasl` |
| `FatesPlantHydraulicsMod` | `biogeophys/FatesPlantHydraulicsMod.F90` | Soil-plant-atmosphere water transport, cohort `btran` | `psi_ag`, `th_ag`, `ftc_ag`, cohort `btran`, `qtop` |
| `FatesBstressMod` | `biogeophys/FatesBstressMod.F90` | Salinity stress factor | `bstress_sal_ft` |
| `FatesHydroWTFMod` | `biogeophys/FatesHydroWTFMod.F90` | Water retention (`wrf_*`) and conductivity (`wkf_*`) functions | `th_from_psi`, `psi_from_th`, `ftc_from_psi` |

Note that the file `biogeophys/EDSurfaceAlbedoMod.F90` actually declares `module EDSurfaceRadiationMod` on its first line. Code references and `use` statements use the module name (`EDSurfaceRadiationMod`), while filesystem searches need the file name.

## Execution Sequence within a Sub-daily Step

For a given patch on a given timestep:

1. `ED_Norman_Radiation` computes sunlit/shaded leaf fractions and absorbed PAR from the host radiation boundary (`solad_parb`, `solai_parb`). See [Radiation Transfer and Albedo](radiation.md).
2. `btran_ed` (or equivalently `BTranForHLMDiagnosticsFromCohortHydr` when hydraulics is active) computes `btran_ft` and the per-layer uptake profile `rootr_pasl`.
3. `FatesPlantRespPhotosynthDrive` solves the leaf-level photosynthesis-stomatal-conductance system using `btran_eff` (multiplied by `bstress_sal_ft` when salinity is on) and the absorbed-PAR profile.
4. `hydraulics_drive` (if `hlm_use_planthydro == itrue`) updates plant and rhizosphere water potentials and refreshes the cohort `btran` for the next iteration of the canopy-flux loop.

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

- `fates_nonhydro_smpso(ft)` — soil water potential at full stomatal opening [mm] (default −66000 mm)
- `fates_nonhydro_smpsc(ft)` — soil water potential at full stomatal closure [mm] (default −255000 mm)

Both parameters are in **millimetres**, consistent with the host `smp_sl` units, and `smpsc` is more negative than `smpso`. See [Transpiration and Soil Moisture Stress](transpiration.md) for the exact formula and a common unit-swap pitfall.

### Hydraulic mode

Active when `hlm_use_planthydro == itrue`. Solves the compartmentalized water-transport equations via one of three solvers set by the integer parameter `hydr_solver`:

| `hydr_solver` | Name | Notes |
| --- | --- | --- |
| 1 | `hydr_solver_1DTaylor` | Sequential layer-by-layer implicit Taylor |
| 2 | `hydr_solver_2DPicard` | Fixed-point iteration over full plant-soil system |
| 3 | `hydr_solver_2DNewton` | Newton-Raphson on full plant-soil system (active, not deprecated) |

All three are actively dispatched in `FatesPlantHydraulicsMod.F90:2567-2607`. See [Plant Hydraulics](hydraulics/index.md).

## Water Transfer Functions (WTFs)

Plant compartments and rhizosphere shells are characterized by water retention (WRF) and water conductivity (WKF) functions implemented in `FatesHydroWTFMod`. For plant tissues, `InitHydroGlobals` (`FatesPlantHydraulicsMod.F90:6198-6320`) only instantiates two forms:

- TFS (`tfs_type = 1`) — default, used for all four plant media in the shipped parameter file (`fates_params_default.cdl:905`).
- Van Genuchten (`van_genuchten_type = 2`) — available but not the default.

Any other value of `hydr_htftype_node` for a plant medium triggers `endrun` (`case default` in `InitHydroGlobals`). **Campbell is not a valid plant WTF option** despite a legacy source comment saying it "could technically be used". The soil rhizosphere, by contrast, is hard-coded to Campbell (`soil_wrf_type = campbell_type` at `FatesPlantHydraulicsMod.F90:214-215`).

Each plant organ has its own WTF parameters defined in the PFT file:

| Organ | `p50` | `avuln` | `kmax` | `thetas`/`resid` | `pinot`/`epsil` (TFS) |
| --- | --- | --- | --- | --- | --- |
| Leaf (`leaf_p_media = 1`) | `hydr_p50_node(ft,1)` | `hydr_avuln_node(ft,1)` | `hydr_kmax_node(ft,1)` | yes | yes |
| Stem (`stem_p_media = 2`) | `hydr_p50_node(ft,2)` | `hydr_avuln_node(ft,2)` | `hydr_kmax_node(ft,2)` | yes | yes |
| Transporting root (`troot_p_media = 3`) | `hydr_p50_node(ft,3)` | `hydr_avuln_node(ft,3)` | `hydr_kmax_node(ft,3)` | yes | yes |
| Absorbing root (`aroot_p_media = 4`) | `hydr_p50_node(ft,4)` | `hydr_avuln_node(ft,4)` | `hydr_kmax_node(ft,4)` | yes | yes |

The stomatal conductance vulnerability curve is always sigmoidal/TFS using `hydr_p50_gs(ft)` and `hydr_avuln_gs(ft)`, not tied to `hydr_htftype_node`.

## Representative Parameters

### Photosynthesis
| Parameter | Description | Units | Typical values |
| --- | --- | --- | --- |
| `fates_leaf_vcmax25top` | Maximum carboxylation rate at 25°C, canopy top | μmol CO₂ m⁻² s⁻¹ | 30-110 |
| `fates_leaf_jmaxha` | Jmax activation energy | J mol⁻¹ | ~43540 |
| `fates_leaf_jmaxhd` | Jmax deactivation energy | J mol⁻¹ | ~152040 |
| `fates_leaf_stomatal_slope_medlyn` | Medlyn g1 | kPa^0.5 | 2.0-6.0 |
| `fates_leaf_stomatal_slope_ballberry` | Ball-Berry slope | unitless | ~9 |
| `fates_leaf_stomatal_intercept` | Minimum stomatal conductance (`g0`) | μmol H₂O m⁻² s⁻¹ | 5000-10000 |

### Hydraulics
| Parameter | Description | Units |
| --- | --- | --- |
| `fates_hydro_p50_node` | `ψ` at 50% conductivity loss | MPa |
| `fates_hydro_avuln_node` | Vulnerability curve shape | unitless |
| `fates_hydro_kmax_node` | Maximum xylem conductivity | kg m⁻¹ MPa⁻¹ s⁻¹ |
| `fates_hydro_epsil_node` | Bulk elastic modulus (TFS) | MPa |
| `fates_hydro_psi0` | Capillary reference potential (TFS) | MPa |
| `fates_hydro_psicap` | Capillary exhaustion potential (TFS) | MPa |
| `fates_hydro_solver` | Solver selector (1, 2, 3) | - |
| `fates_hydro_htftype_node` | Plant WTF selector (1=TFS, 2=VG only) | - |

### Radiation
| Parameter | Description | Units |
| --- | --- | --- |
| `fates_rad_leaf_rhovis` / `rhonir` | Leaf reflectance (vis/NIR) | fraction |
| `fates_rad_leaf_tauvis` / `taunir` | Leaf transmittance (vis/NIR) | fraction |
| `fates_rad_leaf_xl` | Leaf angle distribution | unitless |
| `fates_rad_clumping` | Foliage clumping index | unitless |

### Transpiration (BTRAN)
| Parameter | Description | Units | Default |
| --- | --- | --- | --- |
| `fates_nonhydro_smpso` | Soil potential at full stomatal opening | **mm** | -66000 |
| `fates_nonhydro_smpsc` | Soil potential at full stomatal closure | **mm** | -255000 |

## Numerical Considerations

### Photosynthesis inner loop

The coupled `ci`, `an`, `gs` system is iterated inside `LeafLayerPhotosynthesis` (`FatesPlantRespPhotosynthMod.F90`). The iteration exits when the change in leaf internal CO₂ mole fraction (not partial pressure) drops below `2 × 10⁻⁶ ppm`, or when the iteration counter `niter` reaches 5. The exact Fortran at lines 1366-1369 is:

```fortran
if ((abs(co2_inter_c-co2_inter_c_old)/can_press*1.e06_r8 <=  2.e-06_r8) &
     .or. niter == 5) then
   loop_continue = .false.
end if
```

A stale comment a few lines above still mentions "at least ten iterations", but `niter == 5` is the enforced limit.

### Hydraulic mass balance

`max_wb_step_err = 2e-6 kg` per plant per sub-step (`FatesPlantHydraulicsMod.F90:242`, with an inline comment noting the pre-existing value `1e-7` was relaxed). Three error pools in `ed_site_hydr_type` (`errh2o_hyd`, `h2oveg_growturn_err`, `h2oveg_hydro_err`) accumulate the residuals per site.

### Conservation checks in radiation

`PatchNormanRadiation` has energy-conservation checks (`EDSurfaceAlbedoMod.F90:1002-1096`) with correction logic when residuals exceed a tolerance. The patch diagnostic `radiation_error` stores the normalized residual for offline checking.

## Source References

- `biogeophys/FatesPlantRespPhotosynthMod.F90:118-155, 1366-1370, 488-490`
- `biogeophys/FatesPlantHydraulicsMod.F90:282-308, 2567-2607, 6198-6320, 240-242`
- `biogeophys/EDSurfaceAlbedoMod.F90:1, 68-173, 178-1104`
- `biogeophys/EDBtranMod.F90:88-262`
- `main/FatesHydraulicsMemMod.F90:17-19, 30-45`
- `main/EDParamsMod.F90:158-164, 218-227`
- `parameter_files/fates_params_default.cdl:437-442, 905`
- `elm/src/biogeophys/CanopyFluxesMod.F90:880, 1279`
