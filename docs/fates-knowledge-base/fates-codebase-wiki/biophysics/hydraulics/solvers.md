---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

# Hydraulic Solvers

## Purpose and Scope

This page documents the numerical methods used to integrate the FATES plant hydraulics equations forward in time. These solvers compute the water potentials and fluxes in the compartment graph described in [Hydraulic Architecture](architecture.md), given the sub-daily transpiration demand and host-model soil moisture boundary conditions. For the overall module driver and coupling to photosynthesis, see [Plant Hydraulics](index.md).

FATES ships three solvers — a 1D Taylor solver, a 2D Picard solver, and a 2D Newton solver — all three actively implemented and dispatched at runtime.

## Solver Catalogue

Solver IDs are declared in `main/FatesHydraulicsMemMod.F90:17-19`:

```fortran
integer, parameter, public :: hydr_solver_1DTaylor = 1
integer, parameter, public :: hydr_solver_2DPicard = 2
integer, parameter, public :: hydr_solver_2DNewton = 3
```

| ID | Name | Method | Dimensionality | Implementation |
| --- | --- | --- | --- | --- |
| 1 | `hydr_solver_1DTaylor` | Implicit first-order Taylor series | 1D per rhizosphere layer, sequential | `OrderLayersForSolve1D` + `ImTaylorSolve1D` |
| 2 | `hydr_solver_2DPicard` | Picard (fixed-point) iteration | 2D: full plant-soil system | `PicardSolve2D` |
| 3 | `hydr_solver_2DNewton` | Newton-Raphson | 2D: full plant-soil system | `MatSolve2D` (`FatesPlantHydraulicsMod.F90:4689-5403`) |

Runtime selection is controlled by the global integer parameter `hydr_solver`, registered as `fates_hydro_solver` in `main/EDParamsMod.F90:218-227`. The comment at `EDParamsMod.F90:222-224` labels Newton-Raphson as "(Deprecated)", but the dispatch at `FatesPlantHydraulicsMod.F90:2567-2572` actively calls `MatSolve2D` whenever `hydr_solver == hydr_solver_2DNewton`:

```fortran
if (hydr_solver == hydr_solver_2DNewton) then
   call MatSolve2D(csite_hydr, ccohort, ccohort_hydr, &
        dtime, qflx_tran_veg_indiv, &
        sapflow, rootuptake(1:nlevrhiz), wb_err_plant, dwat_plant, &
        dth_layershell_col)
elseif (hydr_solver == hydr_solver_2DPicard) then
   call PicardSolve2D(...)
elseif (hydr_solver == hydr_solver_1DTaylor) then
   call OrderLayersForSolve1D(...)
   call ImTaylorSolve1D(...)
end if
```

So Newton is **not** deprecated in this FATES version. It is a live, user-selectable solver; choose it by setting `fates_hydro_solver = 3` in the parameter file. Any documentation suggesting otherwise should be treated as stale.

## Solver Entry Point

The hydraulics driver `hydraulics_drive` (`FatesPlantHydraulicsMod.F90:282-308`) is called every host sub-daily flux timestep from `elm/src/biogeophys/CanopyFluxesMod.F90:1279` via `alm_fates%wrap_hydraulics_drive(...)`. It performs three steps:

1. `FillDrainRhizShells` — synchronize site-level rhizosphere shells with the current host soil moisture.
2. `hydraulics_BC(nsites, sites, bc_in, bc_out, dtime)` — walk the site/patch/cohort tree, gather per-cohort transpiration demand `qflx_tran_veg_indiv`, and for each cohort dispatch to the solver chosen by `hydr_solver`.
3. Update diagnostic arrays `sapflow_scpf`, `rootuptake*_scpf`, and the site-aggregated error pools `errh2o_hyd`, `dwat_veg`, `h2oveg` with the per-cohort residuals.

Within `hydraulics_BC`, the per-cohort solver call is wrapped by `UpdatePlantPsiFTCFromTheta` (which refreshes `psi_*` and `ftc_*` from the integrated `th_*`) and an assignment of the cohort-level `btran`:

```fortran
ccohort_hydr%btran = wkf_plant(stomata_p_media, ft)%p%ftc_from_psi(ccohort_hydr%psi_ag(1))
```
(`FatesPlantHydraulicsMod.F90:2651`). This `btran` is the value passed to `FatesPlantRespPhotosynthMod` in the next photosynthesis iteration.

## Governing Equations

The solvers integrate a compartment-based form of the Richards equation. For each connection between two nodes `i` and `j` the flux is

```
q_ij = -k_ij(ψ) * [(ψ_j - ψ_i) / (z_j - z_i) + ρ * g]
```

where `k_ij(ψ)` is the harmonic (or upstream-weighted) mean conductance along that edge, scaled by the fractional conductivity `ftc`. The continuity statement at each node is

```
V_i * dθ_i/dt = Σ_j q_ij - S_i
```

with `S_i` the external sink (transpiration at the leaf node, source from the host soil boundary at the outer rhizosphere shell). Closure comes from the water retention and conductivity functions (see [Hydraulic Architecture](architecture.md)):

- `θ(ψ)`, `ψ(θ)` from `wrf_*` objects.
- `dψ/dθ` from `dpsidth_from_th`, needed for both Taylor linearization and Newton Jacobian.
- `ftc(ψ)` and `d(ftc)/dψ` from `wkf_*` objects.

The non-linearity comes primarily from `ftc(ψ)`, which drops sharply through the cavitation range, and from the sigmoidal tissue capacitance curves (particularly for TFS tissue media).

## 1D Taylor Solver (`hydr_solver = 1`)

`ImTaylorSolve1D` (called after `OrderLayersForSolve1D`) walks rhizosphere layers sequentially in order of decreasing root-soil conductance. For each layer `j`, it treats the plant flow path `leaf → stem → troot → aroot(j) → shell(j)` as a small 1D Richards problem with the plant compartments included. A first-order Taylor expansion around the current `θ` and `ψ` produces a linear system small enough to factorize efficiently.

Key characteristics:

- `do_parallel_stem = .true.` (`FatesPlantHydraulicsMod.F90:161`) treats the aboveground stem + leaf column as parallel to all root layers. Without this flag the layers would have to be chained serially, tightly coupling them; the parallel treatment keeps the 1D Taylor solve cheap.
- `do_upstream_k = .true.` (`FatesPlantHydraulicsMod.F90:157`) forces the mean edge conductance to use the upstream node's `ftc`, which helps stability under sharp cavitation transitions.
- Layers are visited in order returned by `OrderLayersForSolve1D`, so the strongest sink layer is solved first. Each subsequent layer inherits updated plant states, which emergently produces hydraulic redistribution when root potentials change sign between layers.
- Allocated state uses the collapsed node count `num_nodes = n_hypool_leaf + n_hypool_stem + n_hypool_troot + n_hypool_aroot + nshell` from `InitHydrSite` (`FatesHydraulicsMemMod.F90:537-542`). Only connectivity arrays (`conn_up`, `conn_dn`, `pm_node`) are stored at site level; the solver uses local scratch arrays for the per-layer linear system.

Strengths: cheap, robust on mild gradients, emergent hydraulic redistribution.
Weaknesses: errors can accumulate across layers; very strong within-layer nonlinearity may require more Taylor iterations.

## 2D Picard Solver (`hydr_solver = 2`)

`PicardSolve2D` treats the complete plant-soil continuum as a single coupled system. At iteration `m+1`:

1. Evaluate node conductances `k^m` and capacitance terms `dψ/dθ` using the current `ψ^m`.
2. Solve the linear system arising from the continuity equation with **lagged** conductances.
3. Update `ψ^(m+1)`, `θ^(m+1)` and loop until the maximum node-update falls below tolerance.

The 2D solver allocates a full site-level state using `num_nodes = n_hypool_leaf + n_hypool_stem + n_hypool_troot + (n_hypool_aroot + nshell) * nlevrhiz` (`FatesHydraulicsMemMod.F90:506-508`). Arrays allocated include `th_node(:)`, `psi_node(:)`, `ftc_node(:)`, `dftc_dpsi_node(:)`, `v_node(:)`, `z_node(:)`, `pm_node(:)`, `node_layer(:)`, `q_flux(:)`, `kmax_up(:)`, `kmax_dn(:)`, and the connectivity arrays `conn_up(:)`, `conn_dn(:)`.

Strengths: mass-conservative by construction; avoids layer-sequencing error; simpler than Newton (no Jacobian).
Weaknesses: linear convergence; can stagnate when the cavitation curve is very steep or when `dψ/dθ` is small.

## 2D Newton Solver (`hydr_solver = 3`)

`MatSolve2D` solves the same coupled system as Picard but uses a full Newton-Raphson update. At each Newton iteration:

1. Build the residual vector `residual(1:num_nodes)` from mass conservation at each node.
2. Build the banded Jacobian `ajac(num_nodes, num_nodes)` using the analytic derivatives `dpsidth_from_th` (WRFs) and `dftcdpsi_from_psi` (WKFs).
3. Factor and solve `ajac × Δθ = -residual` with LAPACK (pivots stored in `ipiv`).
4. Update `θ`, refresh `ψ` and `ftc`, recompute fluxes, and check convergence.

Arrays allocated specifically for Newton (`FatesHydraulicsMemMod.F90:509-530`) include `ajac`, `residual`, `ipiv`, and the per-step tracking arrays `th_node_init`, `th_node_prev`, `dth_node`, `h_node`.

Strengths: quadratic convergence near the solution; the most robust option for sharp gradients and severe cavitation.
Weaknesses: requires building and inverting the Jacobian each iteration; memory footprint scales as `num_nodes²`; most expensive per iteration of the three.

## Convergence and Error Handling

All three solvers check the per-plant water balance after every solve. The limit is set at `FatesPlantHydraulicsMod.F90:242`:

```fortran
real(r8), parameter :: max_wb_step_err = 2.e-6_r8   ! kg, original 1e-7 relaxed by Junyan
```

Per-cohort diagnostics recorded in `ed_cohort_hydr_type`:

| Variable | Description |
| --- | --- |
| `iterh1` | Outer iteration count for this cohort |
| `iterh2` | Inner iteration count |
| `iterlayer` | Index of the rhizosphere layer with the highest iteration count (1D Taylor only) |
| `errh2o` | Running water-balance error per unit crown area [kg m⁻²] |
| `supsub_flag` | Index of any node that hit supersaturation (+) or sub-residual (-) |

Site-level error pools (`ed_site_hydr_type`) accumulate:

- `errh2o_hyd` — total hydraulics error [mm]
- `h2oveg_growturn_err` — error from growth/turnover adjustments [kg m⁻²]
- `h2oveg_hydro_err` — error from the hydrodynamic solves [kg m⁻²]

Developer flags `trap_supersat_psi` and `trap_neg_wc` in `FatesPlantHydraulicsMod` (around line 177) can be toggled during debugging to catch unphysical states. Linear extrapolation is applied inside `psi_from_th` / `th_from_psi` beyond the normal parameter range to keep the solver stable, at the cost of physical fidelity in those edge regions.

A small buffer `thsat_buff = 0.001 m³ m⁻³` prevents numerical overshoot of saturation when purging water back to soil if `purge_supersaturation = .true.` (typically disabled).

## Water Transfer Function Interfaces

The solvers access the water transfer functions through global pointer arrays declared in `FatesPlantHydraulicsMod.F90`:

- `wrf_plant(stomata_p_media:n_plant_media, numpft)` — plant water retention functions, allocated in `InitHydroGlobals` at line 6229. Only TFS and Van Genuchten are wired up; Campbell triggers `endrun`. See [Plant Hydraulics](index.md) and [Hydraulic Architecture](architecture.md).
- `wkf_plant(stomata_p_media:n_plant_media, numpft)` — plant water conductivity functions; the stomatal index (`stomata_p_media = 0`) is always a `wkf_type_tfs` regardless of `hydr_htftype_node`.
- `si_hydr%wrf_soil(1:nlevrhiz)` — site-level soil WRFs. Soil is compile-time hard-coded to Campbell (`soil_wrf_type = campbell_type` at `FatesPlantHydraulicsMod.F90:214`), populated from host-supplied Campbell parameters `sucsat`, `watsat`, `bsw`.
- `si_hydr%wkf_soil(1:nlevrhiz)` — site-level soil WKFs, also always Campbell.

**`hydr_htftype_node` therefore affects only the plant media (leaf, stem, troot, aroot)** and cannot be used to switch the soil between Campbell and Van Genuchten. If a user sets a plant organ to `campbell_type = 3`, FATES aborts at initialization with "undefined water retention type for plants". An earlier statement in the original wiki suggesting that `hydr_htftype_node` "allows mixing, for example, TFS functions for plant tissues with Campbell functions for soil" is misleading: soil Campbell is hard-coded, and the plant choice is restricted to TFS or VG.

## Solver Configuration Summary

| Parameter | Description | Default |
| --- | --- | --- |
| `fates_hydro_solver` (`hydr_solver`) | Solver selector: 1=Taylor, 2=Picard, 3=Newton | user-specified |
| `fates_hydro_htftype_node` (`hydr_htftype_node(1:4)`) | Plant WTF selector, per-organ. Valid values: 1 (TFS), 2 (VG). | `1, 1, 1, 1` (all TFS) |
| `fates_hydro_kmax_rsurf1` | Soil→root surface conductance | parameter file |
| `fates_hydro_kmax_rsurf2` | Root→soil surface conductance | parameter file |
| `fates_hydro_psi0` | Reference potential (TFS capillary region) | 0.0 MPa |
| `fates_hydro_psicap` | Capillary exhaustion potential (TFS) | -0.6 MPa |
| `do_parallel_stem` (`FatesPlantHydraulicsMod.F90:161`) | Treat stem+leaf as parallel to root layers (1D Taylor only) | `.true.` |
| `do_upstream_k` (`FatesPlantHydraulicsMod.F90:157`) | Use upstream `ftc` for edge conductance | `.true.` |

## Unit Testing

A Python unit test driver lives in `functional_unit_testing/hydro/HydroUTestDriver.py`. It exercises the WRF and WKF classes directly rather than running the full plant solver, verifying that analytic derivatives (`dpsidth_from_th`, `dftcdpsi_from_psi`) match numerical differentiation. This ensures that the Jacobian used by the Newton solver stays consistent with the primitive `ftc` and `ψ` evaluations, and gives a convenient regression harness for new functional forms.

## Source References

- `biogeophys/FatesPlantHydraulicsMod.F90:282-308` — `hydraulics_drive` entry point
- `biogeophys/FatesPlantHydraulicsMod.F90:2567-2607` — solver dispatch
- `biogeophys/FatesPlantHydraulicsMod.F90:4689-5403` — `MatSolve2D` (Newton implementation)
- `biogeophys/FatesPlantHydraulicsMod.F90:242` — `max_wb_step_err`
- `biogeophys/FatesPlantHydraulicsMod.F90:157-167` — `do_upstream_k`, `do_parallel_stem`
- `biogeophys/FatesPlantHydraulicsMod.F90:200-215` — WTF constants, soil hard-coded Campbell
- `biogeophys/FatesPlantHydraulicsMod.F90:6198-6320` — `InitHydroGlobals` plant WTF allocation
- `biogeophys/FatesPlantHydraulicsMod.F90:2649-2651` — update of cohort `btran`
- `main/FatesHydraulicsMemMod.F90:17-19` — solver ID constants
- `main/FatesHydraulicsMemMod.F90:447-553` — `InitHydrSite` (node allocation differs by solver)
- `main/EDParamsMod.F90:218-227` — `hydr_solver` parameter and stale "Deprecated" comment on Newton
- `elm/src/biogeophys/CanopyFluxesMod.F90:1279` — sub-daily call to `wrap_hydraulics_drive`
- `functional_unit_testing/hydro/HydroUTestDriver.py` — WRF/WKF unit tests
