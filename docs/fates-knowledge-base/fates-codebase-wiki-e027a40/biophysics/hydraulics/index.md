---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# Plant Hydraulics

## Purpose and Scope

The FATES plant hydraulics module simulates water transport through the soil-plant-atmosphere continuum using an explicit compartment model. Water moves from bulk soil through rhizosphere shells, absorbing roots, transporting roots, stems, and leaves, and finally out through stomata. The module tracks water content, water potential, and fractional conductivity (cavitation) in each compartment and uses a mechanistic limitation on stomatal conductance in place of the empirical `BTRAN` ramp.

Plant hydraulics is **enabled** at the host-land-model interface by the integer flag `hlm_use_planthydro == itrue`. Note that this flag is an integer (0/1), not a Fortran `logical`, and is compared directly against `itrue`/`ifalse` in code such as `EDBtranMod.F90:226` and `FatesPlantRespPhotosynthMod.F90:510`.

For the empirical pathway used when hydraulics is disabled, see [Transpiration and Soil Moisture Stress](../transpiration.md). For details of the data structures, see [Hydraulic Architecture](architecture.md). For numerical methods, see [Hydraulic Solvers](solvers.md).

Key reference: Christoffersen et al. (2016), *Geoscientific Model Development*, 9(11), 4227-4255, `doi:10.5194/gmd-9-4227-2016`.

## Calling Frequency and Integration Point

**Hydraulics is called sub-daily, NOT once per day.** The entry point `hydraulics_drive` is invoked from the host land model through `alm_fates%wrap_hydraulics_drive(...)`, which is called from ELM-side `components/elm/src/biogeophys/CanopyFluxesMod.F90` (line 1322 at d40b843) inside the `CanopyFluxes` routine. `CanopyFluxes` is executed every host flux timestep (typically 30 minutes in ELM/CLM). `hydraulics_drive` receives the host timestep `dtime` as an argument, and the solvers integrate over that sub-daily interval.

Within one call to `hydraulics_drive`, FATES:

1. Synchronizes rhizosphere shells with the current host soil moisture (`FillDrainRhizShells`),
2. Dispatches to the selected solver (Taylor 1D, Picard 2D, or Newton 2D) for every cohort on every patch,
3. Updates plant water potentials and the stomatal vulnerability factor `cohort_hydr%btran`, which is consumed by `FatesPlantRespPhotosynthMod` on the same sub-daily iteration. The cohort `btran` is refreshed inside `UpdatePlantPsiFTCFromTheta` at `FatesPlantHydraulicsMod.F90:711`.

Earlier versions of this wiki stated that the hydraulics module was called "once per day from the main FATES driver". That is **incorrect**. The ED daily dynamics loop (growth, allocation, mortality) is separate from the sub-daily biophysical loop that drives hydraulics and photosynthesis.

## Hydraulic Architecture Summary

Each cohort is divided into a fixed set of water-storage compartments whose counts are hard-coded in `main/FatesHydraulicsMemMod.F90:35-39`:

```fortran
integer, parameter, public :: n_hypool_leaf  = 1
integer, parameter, public :: n_hypool_stem  = 1
integer, parameter, public :: n_hypool_troot = 1  ! CANNOT BE CHANGED
integer, parameter, public :: n_hypool_aroot = 1  ! per soil layer
integer, parameter, public :: nshell         = 1
```

There is exactly one leaf node, one stem node, one transporting-root node, one absorbing-root node per rhizosphere layer, and one rhizosphere soil shell per rhizosphere layer. `nshell = 1` is a hard-coded constant, so in practice all radial soil-shell discretization collapses to a single shell; the `nshell` loops in the source retain the structure for possible future multi-shell implementations.

Plant media types (used to index water transfer functions) are declared in `FatesHydraulicsMemMod.F90:52-57`:

| Index name | Value | Usage |
| --- | --- | --- |
| `stomata_p_media` | 0 | Stomatal cavitation curve (not a storage compartment) |
| `leaf_p_media` | 1 | Leaf tissue |
| `stem_p_media` | 2 | Stem xylem and sapwood |
| `troot_p_media` | 3 | Transporting root xylem |
| `aroot_p_media` | 4 | Absorbing root tissue |
| `rhiz_p_media` | 5 | Rhizosphere soil |

`n_plant_media = 4` (leaf, stem, troot, aroot) is declared at line 34. Soil is handled separately at the site level.

For details of the `ed_cohort_hydr_type` and `ed_site_hydr_type` fields, see [Hydraulic Architecture](architecture.md).

## Water Transfer Functions (WTFs)

Plant compartments and rhizosphere shells are characterized by two functions implemented in `biogeophys/FatesHydroWTFMod.F90` (2176 lines at e027a40):

- **Water Retention Function (WRF)** — relates volumetric water content `theta` [m3 m-3] to matric potential `psi` [MPa]. Provides `th_from_psi`, `psi_from_th`, and the derivative `dpsidth_from_th`.
- **Water Conductivity Function (WKF)** — relates matric potential `psi` to the fraction of total conductivity `ftc` in `[0, 1]`, representing xylem cavitation. Provides `ftc_from_psi` and `dftcdpsi_from_psi`.

The module defines several functional forms, but **not all of them are available for plant tissues**. Verified against `InitHydroGlobals` in `FatesPlantHydraulicsMod.F90:6248-6376`.

### Plant WTFs available at runtime

Only two forms are wired into the plant WRF/WKF allocation loop (`FatesPlantHydraulicsMod.F90:6287-6326` for WRFs, `:6332-6356` for WKFs):

- `van_genuchten_type = 2` — Van Genuchten (1980) retention curve. Parameters come from the `hydr_vg_alpha_node`, `hydr_vg_n_node`, `hydr_vg_m_node`, `hydr_thetas_node`, `hydr_resid_node` PFT arrays.
- `tfs_type = 1` — Tissue Fraction Saturation model (Christoffersen/Xu TFS). Parameters come from `hydr_thetas_node`, `hydr_resid_node`, `hydr_pinot_node`, `hydr_epsil_node`, plus `rwcft`/`rwccap` derived constants for capillary/elastic regions.

Any other value of `hydr_htftype_node(pm)` — including Campbell (`campbell_type = 3`) or the smoothed Campbell variants (`smooth1_campbell_type = 31`, `smooth2_campbell_type = 32`) — falls through to the `case default` branch:

```fortran
case default
   write(fates_log(),*) 'undefined water retention type for plants, pm:',pm,'type: ',hydr_htftype_node(pm)
   call endrun(msg=errMsg(sourcefile, __LINE__))
```

(`FatesPlantHydraulicsMod.F90:6323-6325`). So **Campbell is not a valid plant WTF choice in this FATES version**, despite the source comment at `:200-206` noting that it "could technically be used".

Default `fates_params_default.json:61-67` sets `fates_hydro_htftype_node = [1, 1, 1, 1]`, so the standard configuration uses TFS for all four plant media. Note that the parameter file is now JSON (CDL format is archived).

The stomatal WKF is always the TFS/sigmoidal form with PFT parameters `hydr_p50_gs` and `hydr_avuln_gs` (`FatesPlantHydraulicsMod.F90:6371-6376`), independent of `hydr_htftype_node`.

### Soil WTF is hard-coded to Campbell

In the same module, the soil retention and conductivity types are compile-time constants (`FatesPlantHydraulicsMod.F90:214-215`):

```fortran
integer, parameter :: soil_wrf_type  = campbell_type
integer, parameter :: soil_wkf_type  = campbell_type
```

`hydr_htftype_node` therefore controls ONLY the plant media (`n_plant_media = 4`). It has no effect on the rhizosphere soil functions, which always use Campbell-Clapp-Hornberger and draw their parameters (`watsat`, `sucsat`, `bsw`) from the host land model via `bc_in`. Lines 200-206 of the same module spell this out: "Right now we just hard-code the use of campbell_type for the soil".

The stomatal vulnerability curve used by TFS is

```
ftc = max(min_ftc, 1 / (1 + (psi_eff / p50)^avuln))
```

(`FatesHydroWTFMod.F90:1885-1912`). This is the **sigmoidal Pammenter and Vanderwilligen (1998) form**, not a Weibull. Because the same functional form is used for the stomatal WKF, the cohort leaf water stress `btran` follows a symmetric S-curve around `p50`.

## Numerical Solvers

FATES provides three solvers for the coupled plant-soil water-potential equations. All three are implemented and dispatched at runtime; none of them is deprecated.

### Solver Constants

Defined in `main/FatesHydraulicsMemMod.F90:19-21`:

```fortran
integer, parameter, public :: hydr_solver_1DTaylor = 1
integer, parameter, public :: hydr_solver_2DPicard = 2
integer, parameter, public :: hydr_solver_2DNewton = 3
```

Note the mapping: the integer `3` corresponds to the **Newton-Raphson 2D solver**, and `2` corresponds to **Picard**. This differs from the natural "alphabetical" ordering and must be matched exactly when writing user namelist values.

### Solver Selection (CHANGED at e027a40)

**`fates_hydro_solver` is no longer a parameter-file entry.** Solver selection has migrated to the HLM namelist. The host passes the namelist key `hydr_solver` through the FATES interface:

- `FatesInterfaceMod.F90:2133-2137` — case branch in the integer-namelist dispatch routine sets `hlm_hydr_solver = ival`.
- `FatesInterfaceTypesMod.F90:154` — declaration `integer, public :: hlm_hydr_solver`.
- `FatesInterfaceMod.F90:1564` — initialization to `unset_int` at FATES startup.
- `FatesInterfaceMod.F90:1867-1869` — startup check that aborts with "FATES hydro solver is unset" if the HLM did not set the namelist.

Verified absent from the parameter file: `grep "fates_hydro_solver" parameter_files/fates_params_default.json` returns no matches at e027a40. Anyone following older documentation and writing `fates_hydro_solver = 2` into a JSON parameter file will get a silent ignore (the entry is not parsed) and FATES will fail at startup as above.

### Dispatch at Runtime

`FatesPlantHydraulicsMod.F90:2582-2622` selects the solver at every sub-daily call:

```fortran
if(hlm_hydr_solver == hydr_solver_2DNewton) then
   call MatSolve2D(...)
elseif(hlm_hydr_solver == hydr_solver_2DPicard) then
   call PicardSolve2D(...)
elseif(hlm_hydr_solver == hydr_solver_1DTaylor ) then
   call OrderLayersForSolve1D(...)
   call ImTaylorSolve1D(...)
end if
```

All three code paths are live and tested:

- **2D Newton (`hlm_hydr_solver = 3`).** Full coupled system solved by Newton-Raphson using a banded Jacobian. Implementation: `MatSolve2D` at `FatesPlantHydraulicsMod.F90:4740-5454`. The earlier "(Deprecated)" comment in `EDParamsMod.F90` is gone at e027a40 along with the entire `fates_hydro_solver` parameter declaration.
- **2D Picard (`hlm_hydr_solver = 2`).** Fixed-point iteration over the entire plant-soil continuum with lagged conductances. Implementation: `PicardSolve2D` at `:5510-6155`.
- **1D Taylor (`hlm_hydr_solver = 1`).** Sequential layer-by-layer implicit Taylor linearization. Implementation: `OrderLayersForSolve1D` followed by `ImTaylorSolve1D` (at `:3244-3948`). The layers are ordered by decreasing root-soil conductance so that the strongest sink is solved first.

Node counts differ between the two modes (`FatesHydraulicsMemMod.F90:505-545`):

- **2D solvers (Newton or Picard):** `num_nodes = n_hypool_leaf + n_hypool_stem + n_hypool_troot + (n_hypool_aroot + nshell) * nlevrhiz`. One Jacobian is allocated per site, sized `(num_nodes, num_nodes)`.
- **1D Taylor solver:** `num_nodes = n_hypool_leaf + n_hypool_stem + n_hypool_troot + n_hypool_aroot + nshell`, i.e. the rhizosphere-layer dimension is collapsed because each Richards solve handles one layer at a time.

### Solver comparison

| Solver ID | Name | Method | Scope | Cost | Robustness |
| --- | --- | --- | --- | --- | --- |
| 1 | `hydr_solver_1DTaylor` | Implicit first-order Taylor | Per-layer sequential | Low | Good for mild gradients |
| 2 | `hydr_solver_2DPicard` | Fixed-point with lagged k | Full plant x rhiz system | Moderate | Better for strong coupling |
| 3 | `hydr_solver_2DNewton` | Newton-Raphson on coupled system | Full plant x rhiz system | High (Jacobian, LAPACK solve) | Quadratic convergence when successful |

For solver algorithmic details, see [Hydraulic Solvers](solvers.md).

## Global Parameters

Global (non-PFT) parameters in the parameter file:

| Parameter | Symbol | Description | Default | Units | Source |
| --- | --- | --- | --- | --- | --- |
| `fates_hydro_kmax_rsurf1` | `hydr_kmax_rsurf1` | Soil to root root-surface conductance | 20.0 | kg m-2 MPa-1 s-1 | `fates_params_default.json:1832-1837` |
| `fates_hydro_kmax_rsurf2` | `hydr_kmax_rsurf2` | Root to soil root-surface conductance | 0.0001 | kg m-2 MPa-1 s-1 | `:1839-1844` |
| `fates_hydro_psi0` | `hydr_psi0` | Sapwood water potential at saturation (TFS reference) | 0.0 | MPa | `:1846-1851` |
| `fates_hydro_psicap` | `hydr_psicap` | Capillary-exhaustion potential (TFS) | -0.6 | MPa | `:1853-1858` |
| `fates_hydro_htftype_node` | `hydr_htftype_node(1:n_plant_media)` | Plant-tissue WRF/WKF selector (1=TFS, 2=VG only) | `[1, 1, 1, 1]` | unitless | `:61-67` |

`fates_hydro_solver` is **not** in the parameter file at e027a40. Set the HLM namelist `hydr_solver` instead.

## PFT-Specific Parameters

Read in `main/EDPftvarcon.F90:776-808`. For each organ (leaf, stem, troot, aroot):

- `fates_hydro_p50_node` — `psi` at 50% conductivity loss [MPa] (`EDPftvarcon.F90:780`; default -2.25 all entries, `fates_params_default.json:712-717`)
- `fates_hydro_avuln_node` — Vulnerability curve shape [-] (`EDPftvarcon.F90:776`; default 2.0 all entries, JSON `:670-675`)
- `fates_hydro_kmax_node` — Maximum xylem conductivity per unit area [kg m-1 MPa-1 s-1] (`EDPftvarcon.F90:808`; default `[-999, 3.0, -999, -999]` per organ, JSON `:698-703`)
- `fates_hydro_epsil_node` — Bulk elastic modulus [MPa] (TFS only) (`EDPftvarcon.F90:788`; defaults 12/10/10/8 per organ, JSON `:677-682`)
- `fates_hydro_pitlp_node` — Turgor loss point [MPa] (TFS only) (defaults -1.67/-1.4/-1.4/-1.2, JSON `:733-738`)
- `fates_hydro_pinot_node` — Osmotic potential at full turgor [MPa] (TFS only) (`EDPftvarcon.F90:804`; JSON `:726-731`)
- `fates_hydro_thetas_node` — Saturated water content [cm3 cm-3] (JSON `:768`)
- `fates_hydro_resid_node` — Residual water content [cm3 cm-3] (defaults 0.16/0.21/0.21/0.11 per organ, JSON `:740-745`)
- `fates_hydro_fcap_node` — Capillary-reserve fraction of non-residual water [-] (TFS only) (defaults 0/0.08/0.08/0 per organ, JSON `:684-689`)

Van Genuchten organs additionally use `fates_hydro_vg_alpha_node`, `fates_hydro_vg_n_node`, `fates_hydro_vg_m_node` (see the `case(van_genuchten_type)` branch in `InitHydroGlobals`).

Whole-plant parameters: `fates_hydro_p_taper` (xylem taper exponent, default 0.333 all PFTs, JSON `:719-724`), `fates_hydro_rfrac_stem` (stem fraction of troot-to-canopy resistance, default 0.625, JSON `:747-752`), `fates_hydro_rs2` (absorbing root radius, default 0.0001 m, JSON `:754-759`), `fates_hydro_srl` (specific root length, default 25.0 m g-1, JSON `:761-766`).

Stomatal control: `fates_hydro_p50_gs` (-1.5 MPa all PFTs, JSON `:705-710`), `fates_hydro_avuln_gs` (2.5, JSON `:663-668`), and `fates_hydro_k_lwp` (inner-leaf-humidity scaling, default 0.0, JSON `:691-696`). The stomatal vulnerability is always TFS/sigmoidal, independent of `hydr_htftype_node`.

All PFT-dimensioned arrays now have length 14 (was 12 at e85d997).

## Coupling to Photosynthesis

After each hydraulic solve, the cohort leaf water stress is updated inside `UpdatePlantPsiFTCFromTheta` at `FatesPlantHydraulicsMod.F90:684-729`:

```fortran
ccohort_hydr%btran = wkf_plant(stomata_p_media, ft)%p%ftc_from_psi(ccohort_hydr%psi_ag(1))
```

(line 711). `ccohort_hydr%btran` replaces the empirical `cpatch%btran_ft(ft)` when `hlm_use_planthydro == itrue`; `FatesPlantRespPhotosynthMod` reads it at `:512` and feeds it into the leaf solve, where the per-PFT btran-application switches `fates_leaf_stomatal_btran_model` and `fates_leaf_agross_btran_model` decide where it actually multiplies (gs0, gs1, vcmax, jmax). See [Photosynthesis and Respiration](../photosynthesis.md) for the switch semantics. A companion routine `BTranForHLMDiagnosticsFromCohortHydr` fills `bc_out%btran_pa` from the same cohort-level `btran` so the host land model always sees a patch-level scalar wetness diagnostic.

## Mass Balance and Error Tracking

Per-plant, per-step water balance errors are checked against a compile-time threshold (`FatesPlantHydraulicsMod.F90:240-242`):

```fortran
real(r8), parameter :: max_wb_step_err = 2.e-6_r8   ! original is 1.e-7_r8, Junyan changed to 2.e-6_r8
```

Three running error pools in `ed_site_hydr_type` accumulate the residuals:

- `errh2o_hyd` — total hydraulics water balance error [mm]
- `h2oveg_growturn_err` — error from growth/turnover adjustments [kg m-2]
- `h2oveg_hydro_err` — error from the hydrodynamic solves [kg m-2]

Each hydraulic solve, growth event, turnover event, recruitment, and mortality event updates these pools. `iterh1`, `iterh2`, and `supsub_flag` per cohort record solver iteration counts and any supersaturation/sub-residual events for diagnostics. See the "Numerical Considerations" section of [Hydraulic Solvers](solvers.md).

## Source References

- `biogeophys/FatesPlantHydraulicsMod.F90:200-215` — WTF type constants and `soil_wrf_type`/`soil_wkf_type` hard-coding
- `biogeophys/FatesPlantHydraulicsMod.F90:240-242` — `max_wb_step_err`
- `biogeophys/FatesPlantHydraulicsMod.F90:684-729` — `UpdatePlantPsiFTCFromTheta` (cohort `btran` update)
- `biogeophys/FatesPlantHydraulicsMod.F90:2582-2622` — solver dispatch
- `biogeophys/FatesPlantHydraulicsMod.F90:6248-6376` — `InitHydroGlobals` (plant WTF allocation)
- `biogeophys/FatesHydroWTFMod.F90:1885-1912` — sigmoidal `ftc_from_psi_tfs`
- `main/FatesHydraulicsMemMod.F90:19-21` — solver constants
- `main/FatesHydraulicsMemMod.F90:35-39, 52-57` — compartment counts (`nshell=1`) and plant-media indices
- `main/FatesHydraulicsMemMod.F90:452-553` — `InitHydrSite` (node-count dispatch)
- `main/FatesInterfaceTypesMod.F90:154` — `hlm_hydr_solver`
- `main/FatesInterfaceMod.F90:1867-1869, 2133-2137` — namelist dispatch and unset-check
- `main/EDPftvarcon.F90:94-96, 389-395, 776-808` — PFT hydraulics parameter declarations
- ELM-side `components/elm/src/biogeophys/CanopyFluxesMod.F90` (line 1322 at d40b843) — sub-daily call to the ELM-side wrap_hydraulics_drive routine (declared in `components/elm/src/main/elmfates_interfaceMod.F90`)
- `parameter_files/fates_params_default.json:61-67` — default `hydr_htftype_node = [1,1,1,1]` (TFS)
