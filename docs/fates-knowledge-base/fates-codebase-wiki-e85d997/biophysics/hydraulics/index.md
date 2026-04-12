---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

# Plant Hydraulics

## Purpose and Scope

The FATES plant hydraulics module simulates water transport through the soil-plant-atmosphere continuum using an explicit compartment model. Water moves from bulk soil through rhizosphere shells, absorbing roots, transporting roots, stems, and leaves, and finally out through stomata. The module tracks water content, water potential, and fractional conductivity (cavitation) in each compartment and uses a mechanistic limitation on stomatal conductance in place of the empirical `BTRAN` ramp.

Plant hydraulics is **enabled** at the host-land-model interface by the integer flag `hlm_use_planthydro == itrue`. Note that this flag is an integer (0/1), not a Fortran `logical`, and is compared directly against `itrue`/`ifalse` in code such as `EDBtranMod.F90:224,256` and `FatesPlantHydraulicsMod.F90:1309`.

For the empirical pathway used when hydraulics is disabled, see [Transpiration and Soil Moisture Stress](../transpiration.md). For details of the data structures, see [Hydraulic Architecture](architecture.md). For numerical methods, see [Hydraulic Solvers](solvers.md).

Key reference: Christoffersen et al. (2016), *Geoscientific Model Development*, 9(11), 4227-4255, `doi:10.5194/gmd-9-4227-2016`.

## Calling Frequency and Integration Point

**Hydraulics is called sub-daily, NOT once per day.** The entry point `hydraulics_drive` is invoked from the host land model through `alm_fates%wrap_hydraulics_drive(...)`, which is called from `elm/src/biogeophys/CanopyFluxesMod.F90:1279` inside the `CanopyFluxes` routine. `CanopyFluxes` is executed every host flux timestep (typically 30 minutes in ELM/CLM). `hydraulics_drive` receives the host timestep `dtime` as an argument (`FatesPlantHydraulicsMod.F90:282-290`), and the solvers integrate over that sub-daily interval.

Within one call to `hydraulics_drive`, FATES:

1. Synchronizes rhizosphere shells with the current host soil moisture (`FillDrainRhizShells`),
2. Dispatches to the selected solver (Taylor 1D, Picard 2D, or Newton 2D) for every cohort on every patch,
3. Updates plant water potentials and the stomatal vulnerability factor `cohort_hydr%btran`, which is consumed by `FatesPlantRespPhotosynthMod` on the same sub-daily iteration (`FatesPlantHydraulicsMod.F90:2649-2651`).

Earlier versions of this wiki stated that the hydraulics module was called "once per day from the main FATES driver". That is **incorrect**. The ED daily dynamics loop (growth, allocation, mortality) is separate from the sub-daily biophysical loop that drives hydraulics and photosynthesis.

## Hydraulic Architecture Summary

Each cohort is divided into a fixed set of water-storage compartments whose counts are hard-coded in `main/FatesHydraulicsMemMod.F90:33-37`:

```fortran
integer, parameter, public :: n_hypool_leaf  = 1
integer, parameter, public :: n_hypool_stem  = 1
integer, parameter, public :: n_hypool_troot = 1  ! CANNOT BE CHANGED
integer, parameter, public :: n_hypool_aroot = 1  ! per soil layer
integer, parameter, public :: nshell         = 1
```

This means there is exactly one leaf node, one stem node, one transporting-root node, one absorbing-root node per rhizosphere layer, and one rhizosphere soil shell per rhizosphere layer. `nshell = 1` is a hard-coded constant, so in practice all radial soil-shell discretization collapses to a single shell; the `nshell` loops in the source retain the structure for possible future multi-shell implementations.

Plant media types (used to index water transfer functions) are declared in `FatesHydraulicsMemMod.F90:50-55`:

| Index name | Value | Usage |
| --- | --- | --- |
| `stomata_p_media` | 0 | Stomatal cavitation curve (not a storage compartment) |
| `leaf_p_media` | 1 | Leaf tissue |
| `stem_p_media` | 2 | Stem xylem and sapwood |
| `troot_p_media` | 3 | Transporting root xylem |
| `aroot_p_media` | 4 | Absorbing root tissue |
| `rhiz_p_media` | 5 | Rhizosphere soil |

`n_plant_media = 4` (leaf, stem, troot, aroot). Soil is handled separately at the site level.

For details of the `ed_cohort_hydr_type` and `ed_site_hydr_type` fields, see [Hydraulic Architecture](architecture.md).

## Water Transfer Functions (WTFs)

Plant compartments and rhizosphere shells are characterized by two functions implemented in `biogeophys/FatesHydroWTFMod.F90`:

- **Water Retention Function (WRF)** — relates volumetric water content `θ` [m³ m⁻³] to matric potential `ψ` [MPa]. Provides `th_from_psi`, `psi_from_th`, and the derivative `dpsidth_from_th`.
- **Water Conductivity Function (WKF)** — relates matric potential `ψ` to the fraction of total conductivity `ftc ∈ [0, 1]`, representing xylem cavitation. Provides `ftc_from_psi` and `dftcdpsi_from_psi`.

The module defines several functional forms, but **not all of them are available for plant tissues**. Verified against `InitHydroGlobals` in `FatesPlantHydraulicsMod.F90:6198-6320`:

### Plant WTFs available at runtime

Only two forms are wired into the plant WRF/WKF allocation loop (`FatesPlantHydraulicsMod.F90:6236-6275`):

- `van_genuchten_type = 2` — Van Genuchten (1980) retention curve. Parameters come from the `hydr_vg_alpha_node`, `hydr_vg_n_node`, `hydr_vg_m_node`, `hydr_thetas_node`, `hydr_resid_node` PFT arrays.
- `tfs_type = 1` — Tissue Fraction Saturation model (Christoffersen/Xu TFS). Parameters come from `hydr_thetas_node`, `hydr_resid_node`, `hydr_pinot_node`, `hydr_epsil_node`, plus `rwcft`/`rwccap` derived constants for capillary/elastic regions.

Any other value of `hydr_htftype_node(pm)` — including Campbell (`campbell_type = 3`) or the smoothed Campbell variants (`smooth1_campbell_type = 31`, `smooth2_campbell_type = 32`) — falls through to the `case default` branch in `InitHydroGlobals`:

```fortran
case default
   write(fates_log(),*) 'undefined water retention type for plants, pm:',pm,'type: ',hydr_htftype_node(pm)
   call endrun(msg=errMsg(sourcefile, __LINE__))
```

So **Campbell is not a valid plant WTF choice in this FATES version**, despite the source comment at `FatesPlantHydraulicsMod.F90:200-206` noting that it "could technically be used". Earlier wiki text listing "TFS, VG, Campbell, CCH Smooth" as plant-side options should be disregarded.

Default `fates_params_default.cdl:905` sets `fates_hydro_htftype_node = 1, 1, 1, 1`, so the standard configuration uses TFS for all four plant media.

The stomatal WKF is always the TFS/sigmoidal form with PFT parameters `hydr_p50_gs` and `hydr_avuln_gs` (`FatesPlantHydraulicsMod.F90:6311-6316`).

### Soil WTF is hard-coded to Campbell

In the same module, the soil retention and conductivity types are compile-time constants (`FatesPlantHydraulicsMod.F90:214-215`):

```fortran
integer, parameter :: soil_wrf_type  = campbell_type
integer, parameter :: soil_wkf_type  = campbell_type
```

`hydr_htftype_node` therefore controls ONLY the plant media (`n_plant_media = 4`). It has no effect on the rhizosphere soil functions, which always use Campbell-Clapp-Hornberger and draw their parameters (`watsat`, `sucsat`, `bsw`) from the host land model via `bc_in`. See `RestartHydrStates` / `UpdateSizeDepRhizHydProps` for the allocation path. The Van-Genuchten-parameterized soil block is present in the code but the module comment (lines 202-206) explicitly says "Right now we just hard-code the use of `campbell_type` for the soil".

The stomatal vulnerability curve used by TFS is

```
ftc = max(min_ftc, 1 / (1 + (ψ_eff / p50)^avuln))
```

(`FatesHydroWTFMod.F90:1727-1738`). This is the **sigmoidal Pammenter and Vanderwilligen (1998) form**, not a Weibull. Because the same functional form is used for the stomatal WKF, the cohort leaf water stress `btran` follows a symmetric S-curve around `p50`.

## Numerical Solvers

FATES provides three solvers for the coupled plant-soil water-potential equations. All three are implemented and dispatched at runtime; none of them is deprecated.

### Solver Constants

Defined in `main/FatesHydraulicsMemMod.F90:17-19`:

```fortran
integer, parameter, public :: hydr_solver_1DTaylor = 1
integer, parameter, public :: hydr_solver_2DPicard = 2
integer, parameter, public :: hydr_solver_2DNewton = 3
```

Note the mapping: the integer `3` corresponds to the **Newton-Raphson 2D solver**, and `2` corresponds to **Picard**. This differs from the natural "alphabetical" ordering and must be matched exactly when writing user parameters.

### Dispatch at Runtime

`FatesPlantHydraulicsMod.F90:2567-2607` selects the solver at every sub-daily call:

```fortran
if (hydr_solver == hydr_solver_2DNewton) then
   call MatSolve2D(...)
elseif (hydr_solver == hydr_solver_2DPicard) then
   call PicardSolve2D(...)
elseif (hydr_solver == hydr_solver_1DTaylor) then
   call OrderLayersForSolve1D(...)
   call ImTaylorSolve1D(...)
end if
```

All three code paths are live and tested:

- **2D Newton (`hydr_solver = 3`).** Full coupled system solved by Newton-Raphson using a banded Jacobian. Implementation: `MatSolve2D` at `FatesPlantHydraulicsMod.F90:4689-5403`. The comment at `EDParamsMod.F90:222-224` labels Newton-Raphson as "(Deprecated)", but that comment is inaccurate as of `e85d997`: `MatSolve2D` is actively dispatched, so calling Newton "deprecated" in documentation is misleading. Treat it as an active option.
- **2D Picard (`hydr_solver = 2`).** Fixed-point iteration over the entire plant-soil continuum with lagged conductances. Implementation: `PicardSolve2D`.
- **1D Taylor (`hydr_solver = 1`).** Sequential layer-by-layer implicit Taylor linearization. Implementation: `OrderLayersForSolve1D` followed by `ImTaylorSolve1D`. The layers are ordered by decreasing root-soil conductance so that the strongest sink is solved first; each subsequent layer inherits the already-updated plant node states.

Node counts differ between the two modes (`FatesHydraulicsMemMod.F90:500-544`):

- **2D solvers (Newton or Picard):** `num_nodes = n_hypool_leaf + n_hypool_stem + n_hypool_troot + (n_hypool_aroot + nshell) * nlevrhiz`. One Jacobian is allocated per site, sized `(num_nodes, num_nodes)`.
- **1D Taylor solver:** `num_nodes = n_hypool_leaf + n_hypool_stem + n_hypool_troot + n_hypool_aroot + nshell`, i.e. the rhizosphere-layer dimension is collapsed because each Richards solve handles one layer at a time.

### Solver comparison

| Solver ID | Name | Method | Scope | Cost | Robustness |
| --- | --- | --- | --- | --- | --- |
| 1 | `hydr_solver_1DTaylor` | Implicit first-order Taylor | Per-layer sequential | Low | Good for mild gradients |
| 2 | `hydr_solver_2DPicard` | Fixed-point with lagged k | Full plant × rhiz system | Moderate | Better for strong coupling |
| 3 | `hydr_solver_2DNewton` | Newton-Raphson on coupled system | Full plant × rhiz system | High (Jacobian, LAPACK solve) | Quadratic convergence when successful |

For solver algorithmic details, see [Hydraulic Solvers](solvers.md).

## Global Parameters

Global (non-PFT) parameters are read in `main/EDParamsMod.F90` and include:

| Parameter | Symbol | Description | Default | Units |
| --- | --- | --- | --- | --- |
| `fates_hydro_solver` | `hydr_solver` | Solver selection (1=Taylor, 2=Picard, 3=Newton) | user-specified | - |
| `fates_hydro_kmax_rsurf1` | `hydr_kmax_rsurf1` | Soil→root root-surface conductance | parameter file | kg m⁻² MPa⁻¹ s⁻¹ |
| `fates_hydro_kmax_rsurf2` | `hydr_kmax_rsurf2` | Root→soil root-surface conductance | parameter file | kg m⁻² MPa⁻¹ s⁻¹ |
| `fates_hydro_psi0` | `hydr_psi0` | Reference capillary potential (TFS) | 0.0 | MPa |
| `fates_hydro_psicap` | `hydr_psicap` | Capillary-exhaustion potential (TFS) | -0.6 | MPa |
| `fates_hydro_htftype_node` | `hydr_htftype_node(1:n_plant_media)` | Plant-tissue WRF/WKF selector (1=TFS, 2=VG only) | `1, 1, 1, 1` | - |

## PFT-Specific Parameters

Read in `main/EDPftvarcon.F90:238-270`. For each organ (leaf, stem, troot, aroot):

- `fates_hydro_p50_node` — `ψ` at 50% conductivity loss [MPa]
- `fates_hydro_avuln_node` — Vulnerability curve shape [-]
- `fates_hydro_kmax_node` — Maximum xylem conductivity per unit area [kg m⁻¹ MPa⁻¹ s⁻¹]
- `fates_hydro_epsil_node` — Bulk elastic modulus [MPa] (TFS only)
- `fates_hydro_pitlp_node` — Turgor loss point [MPa] (TFS only)
- `fates_hydro_pinot_node` — Osmotic potential at full turgor [MPa] (TFS only)
- `fates_hydro_thetas_node` — Saturated water content [cm³ cm⁻³]
- `fates_hydro_resid_node` — Residual water content [cm³ cm⁻³]
- `fates_hydro_fcap_node` — Capillary-reserve fraction of non-residual water [-] (TFS only)

Van Genuchten organs additionally use `fates_hydro_vg_alpha_node`, `fates_hydro_vg_n_node`, `fates_hydro_vg_m_node` (see the `case(van_genuchten_type)` branch in `InitHydroGlobals`).

Whole-plant parameters: `fates_hydro_p_taper` (xylem taper exponent), `fates_hydro_rfrac_stem` (stem fraction of troot-to-canopy resistance), `fates_hydro_rs2` (absorbing root radius), `fates_hydro_srl` (specific root length).

Stomatal control: `fates_hydro_p50_gs`, `fates_hydro_avuln_gs`, and `fates_hydro_k_lwp`. The stomatal vulnerability is always TFS/sigmoidal, independent of `hydr_htftype_node`.

## Coupling to Photosynthesis

After each hydraulic solve, the cohort leaf water stress is updated (`FatesPlantHydraulicsMod.F90:2649-2651`):

```fortran
call UpdatePlantPsiFTCFromTheta(ccohort, csite_hydr)
ccohort_hydr%btran = wkf_plant(stomata_p_media, ft)%p%ftc_from_psi(ccohort_hydr%psi_ag(1))
```

`ccohort_hydr%btran` replaces the empirical `cpatch%btran_ft(ft)` when `hlm_use_planthydro == itrue`; `FatesPlantRespPhotosynthMod` multiplies it into the stomatal intercept exactly as in the non-hydraulic pathway. See [Photosynthesis and Respiration](../photosynthesis.md) for how this factor is consumed. A companion routine `BTranForHLMDiagnosticsFromCohortHydr` fills `bc_out%btran_pa` from the same cohort-level `btran` so the host land model always sees a patch-level scalar wetness diagnostic.

## Mass Balance and Error Tracking

Per-plant, per-step water balance errors are checked against a compile-time threshold (`FatesPlantHydraulicsMod.F90:240-242`):

```fortran
real(r8), parameter :: max_wb_step_err = 2.e-6_r8   ! kg
```

Three running error pools in `ed_site_hydr_type` accumulate the residuals:

- `errh2o_hyd` — total hydraulics water balance error [mm]
- `h2oveg_growturn_err` — error from growth/turnover adjustments [kg m⁻²]
- `h2oveg_hydro_err` — error from the hydrodynamic solves [kg m⁻²]

Each hydraulic solve, growth event, turnover event, recruitment, and mortality event updates these pools. `iterh1`, `iterh2`, and `supsub_flag` per cohort record solver iteration counts and any supersaturation/sub-residual events for diagnostics. See the "Numerical Considerations" section of [Hydraulic Solvers](solvers.md).

## Source References

- `biogeophys/FatesPlantHydraulicsMod.F90:282-308` — `hydraulics_drive` entry point
- `biogeophys/FatesPlantHydraulicsMod.F90:2567-2607` — solver dispatch
- `biogeophys/FatesPlantHydraulicsMod.F90:6198-6320` — `InitHydroGlobals` (plant WTF allocation)
- `biogeophys/FatesPlantHydraulicsMod.F90:208-215` — WTF type constants and `soil_wrf_type`/`soil_wkf_type` hard-coding
- `biogeophys/FatesPlantHydraulicsMod.F90:240-242` — `max_wb_step_err`
- `biogeophys/FatesPlantHydraulicsMod.F90:2649-2651` — update of cohort `btran`
- `main/FatesHydraulicsMemMod.F90:17-19` — solver constants
- `main/FatesHydraulicsMemMod.F90:30-45` — plant-media and compartment counts (`nshell=1`)
- `main/FatesHydraulicsMemMod.F90:447-553` — `InitHydrSite` and node-count dispatch
- `main/EDParamsMod.F90:158, 164` — `hydr_htftype_node` parameter registration
- `main/EDParamsMod.F90:218-227` — `hydr_solver` parameter and (outdated) "Deprecated" comment on Newton
- `elm/src/biogeophys/CanopyFluxesMod.F90:1279` — sub-daily call to `wrap_hydraulics_drive`
- `parameter_files/fates_params_default.cdl:905` — default `hydr_htftype_node = 1, 1, 1, 1` (TFS)
