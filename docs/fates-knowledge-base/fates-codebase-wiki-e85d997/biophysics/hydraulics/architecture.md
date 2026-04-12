---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

# Hydraulic Architecture

## Purpose and Scope

This page documents the data structures and water transfer functions that define the FATES plant hydraulics model. It covers the compartment topology, the `ed_cohort_hydr_type` and `ed_site_hydr_type` structures, the shape of the per-organ state, and the water retention (WRF) and water conductivity (WKF) function classes that translate between water content, water potential, and fractional conductivity. For numerical methods, see [Hydraulic Solvers](solvers.md). For the overall module driver and integration points, see [Plant Hydraulics](index.md).

Primary source files: `biogeophys/FatesPlantHydraulicsMod.F90`, `biogeophys/FatesHydroWTFMod.F90`, `main/FatesHydraulicsMemMod.F90`.

## Compartment Topology

Each cohort consists of a fixed set of water-storage compartments connected in a series/parallel flow network from stomata through the plant to the soil. The compartment counts are hard-coded integer parameters in `main/FatesHydraulicsMemMod.F90:33-37`:

```fortran
integer, parameter, public :: n_hypool_leaf  = 1
integer, parameter, public :: n_hypool_stem  = 1
integer, parameter, public :: n_hypool_troot = 1  ! CANNOT BE CHANGED
integer, parameter, public :: n_hypool_aroot = 1  ! per soil layer
integer, parameter, public :: nshell         = 1
```

and the derived totals

```fortran
integer, parameter, public :: n_hypool_ag   = n_hypool_leaf + n_hypool_stem  ! = 2
integer, parameter, public :: n_hypool_tot  = n_hypool_ag + n_hypool_troot + n_hypool_aroot + nshell
integer, parameter, public :: n_hypool_plant = n_hypool_tot - nshell
```

| Compartment | Index | Storage variable | Count per cohort |
| --- | --- | --- | --- |
| Leaf | `ag(1)` (with `leaf_p_media = 1`) | `th_ag(1)` | 1 |
| Stem | `ag(2)` (with `stem_p_media = 2`) | `th_ag(2)` | 1 |
| Transporting root | single node (`troot_p_media = 3`) | `th_troot` | 1 |
| Absorbing root | per rhizosphere layer (`aroot_p_media = 4`) | `th_aroot(j)` | `nlevrhiz` |
| Rhizosphere shell | per layer × shell (`rhiz_p_media = 5`) | `si_hydr%h2osoi_liqvol_shell(j,k)` | `nlevrhiz × nshell` (`nshell = 1`) |

Because `nshell = 1` is a compile-time constant, the rhizosphere radial discretization currently collapses to a single shell per layer. The `nshell` loops remain in the source so the structure can be extended in the future, but any production configuration has exactly one radial shell per rhizosphere layer.

Plant media type indices (used to select WTFs) are declared at `FatesHydraulicsMemMod.F90:50-55`:

| Index name | Value | Usage |
| --- | --- | --- |
| `stomata_p_media` | 0 | Stomatal vulnerability (WKF-only; not a storage compartment) |
| `leaf_p_media` | 1 | Leaf tissue |
| `stem_p_media` | 2 | Stem xylem and sapwood |
| `troot_p_media` | 3 | Transporting root xylem |
| `aroot_p_media` | 4 | Absorbing root tissue |
| `rhiz_p_media` | 5 | Rhizosphere soil (site level) |

`n_plant_media = 4` spans `leaf`, `stem`, `troot`, `aroot`. Stomatal and rhizosphere indices are handled separately.

## Cohort-Level Data: `ed_cohort_hydr_type`

Declared in `main/FatesHydraulicsMemMod.F90:201-321`, this type holds all per-cohort hydraulic state. One instance is attached to each cohort when hydraulics is active.

### Node heights and geometry

- `z_node_ag(1:n_hypool_ag)` — vertical position of aboveground nodes [m], positive above the soil surface.
- `z_upper_ag(1:n_hypool_ag)`, `z_lower_ag(1:n_hypool_ag)` — upper and lower bounds of each aboveground compartment [m].
- `z_node_troot` — height of the transporting-root node [m] (negative, below ground).
- Absorbing-root node heights are set equal to the midpoints of the soil layers they occupy; they are not stored as separate scalars but are recovered from `si_hydr%zi_rhiz` and `dz_rhiz` during solves.

### Maximum hydraulic conductances

`kmax_*` values are the per-compartment maximum conductances [kg H₂O s⁻¹ MPa⁻¹]. The actual conductance used in the solver is `kmax × ftc`, where `ftc` is the fraction of total conductivity (0-1) derived from the current water potential through the WKF.

Axial (xylem) conductances:

| Variable | Description |
| --- | --- |
| `kmax_petiole_to_leaf` | Petiole → leaf (set very high; effectively rigid) |
| `kmax_stem_upper(1)` | Upper stem boundary |
| `kmax_stem_lower(1)` | Lower stem boundary |
| `kmax_troot_upper` | Upper transporting root boundary |
| `kmax_troot_lower(j)` | Lower transporting root into rhiz layer `j` |
| `kmax_aroot_upper(j)` | Upper absorbing-root xylem in layer `j` |
| `kmax_aroot_lower(j)` | Absorbing root → transporting root |

Radial (membrane) conductances:

| Variable | Description |
| --- | --- |
| `kmax_aroot_radial_in(j)` | Root membrane, water flowing IN (soil → plant) |
| `kmax_aroot_radial_out(j)` | Root membrane, water flowing OUT (plant → soil, hydraulic redistribution) |

Having separate in/out conductances lets the model represent asymmetric membrane permeability between uptake and passive release.

### Compartment volumes and root lengths

Volumes per cohort in m³ are recalculated daily from biomass pools:

- `v_ag(1:n_hypool_ag)` / `v_ag_init(1:n_hypool_ag)` — current and previous-day volumes.
- `v_troot`, `v_troot_init` — transporting root volumes.
- `v_aroot_layer(1:nlevrhiz)`, `v_aroot_layer_init(1:nlevrhiz)` — absorbing root volumes per layer.
- `l_aroot_layer(1:nlevrhiz)` — absorbing root length per layer [m], derived from fine-root biomass and specific root length.

The `_init` arrays capture the previous state so that water-balance error from growth and turnover can be attributed separately from error in the hydraulic solve (see `h2oveg_growturn_err` below).

### State variables (prognostic)

Water content `θ` is the prognostic variable integrated by the solvers:

- `th_ag(1:n_hypool_ag)` — leaf and stem water content [m³ m⁻³].
- `th_troot` — transporting-root water content.
- `th_aroot(1:nlevrhiz)` — absorbing-root water content by layer.

### Diagnostics derived from `θ`

- `psi_ag(1:n_hypool_ag)`, `psi_troot`, `psi_aroot(1:nlevrhiz)` — water potentials [MPa], computed via `wrf_plant(pm,ft)%p%psi_from_th(th)`.
- `ftc_ag(1:n_hypool_ag)`, `ftc_troot`, `ftc_aroot(1:nlevrhiz)` — fractional conductivities [0, 1], computed via `wkf_plant(pm,ft)%p%ftc_from_psi(psi)`.
- `btran` — leaf water stress factor passed to photosynthesis, computed by `wkf_plant(stomata_p_media, ft)%p%ftc_from_psi(psi_ag(1))` at `FatesPlantHydraulicsMod.F90:2651`. The stomatal WKF is always TFS/sigmoidal.
- `qtop` — transpiration flux [kg cohort⁻¹ s⁻¹].
- `errh2o` — running water-balance error [kg m⁻² ground].
- `iterh1`, `iterh2`, `supsub_flag` — solver iteration counters and flags used for debugging supersaturation / sub-residual events.

## Site-Level Data: `ed_site_hydr_type`

Declared in `main/FatesHydraulicsMemMod.F90:68-196`. One instance per site, holding the rhizosphere shells and site-aggregated quantities that are shared across cohorts.

### Rhizosphere vertical structure

- `nlevrhiz` — number of rhizosphere layers (`≤ nlevsoi_hyd_max = 40`).
- `zi_rhiz(1:nlevrhiz)` — depth of the bottom edge of each rhizosphere layer [m].
- `dz_rhiz(1:nlevrhiz)` — thickness of each rhizosphere layer [m].
- `map_s2r(1:nlevsoil)` — maps soil layer → rhizosphere layer index.
- `map_r2s(1:nlevrhiz, 1:2)` — maps rhizosphere layer → (top, bottom) soil layer indices.

These mappings aggregate host-model soil properties (`watsat`, `sucsat`, `bsw`) onto the rhizosphere grid.

### Rhizosphere shell structure

- `v_shell(j, k)` — volume of shell `k` in layer `j` [m³].
- `r_node_shell(j, k)` — nodal radius of the shell [m].
- `r_out_shell(j, k)` — outer radius [m].
- `h2osoi_liqvol_shell(j, k)` — volumetric water content in the shell [m³ m⁻³].
- `kmax_upper_shell(j, k)`, `kmax_lower_shell(j, k)` — max conductances between shells [kg s⁻¹ MPa⁻¹].

Because `nshell = 1`, the shell index `k` is always `1` in practice.

### Site-aggregated root properties

- `l_aroot_layer(1:nlevrhiz)` — total absorbing root length across all cohorts in layer `j` [m].
- `l_aroot_layer_init(1:nlevrhiz)` — previous-step value, used for water-balance adjustments.
- `rs1(1:nlevrhiz)` — mean fine root radius [m], currently a constant `fine_root_radius_const = 0.0001 m` at `FatesHydraulicsMemMod.F90:63`.

### Water balance tracking

| Variable | Description | Units |
| --- | --- | --- |
| `h2oveg` | Total water stored in vegetation | kg m⁻² |
| `h2oveg_recruit` | Water carried by new recruits | kg m⁻² |
| `h2oveg_dead` | Water in dead vegetation awaiting accounting | kg m⁻² |
| `h2oveg_growturn_err` | Error pool for growth/turnover adjustments | kg m⁻² |
| `h2oveg_hydro_err` | Error pool for the hydrodynamic solves | kg m⁻² |
| `errh2o_hyd` | Total hydraulics water balance error | mm |
| `dwat_veg` | Change in vegetation water storage | kg m⁻² |

### Diagnostic output arrays

For history output:

- `rootuptake_sl(1:nlevsoil)` — uptake per soil layer [kg m⁻² s⁻¹]
- `rootl_sl(1:nlevsoil)` — root length per soil layer [m]
- `sapflow_scpf(1:numlevsclass, 1:numpft)` — sapflow by size class × PFT [kg ha⁻¹ s⁻¹]
- `rootuptake0_scpf` … `rootuptake100_scpf` — root uptake in 0-10, 10-50, 50-100, >100 cm bins [kg ha⁻¹ m⁻¹ s⁻¹]

### Solver work arrays (2D solvers only)

`InitHydrSite` (`FatesHydraulicsMemMod.F90:447-553`) allocates different work arrays depending on the solver choice:

- When `hydr_solver` is `hydr_solver_2DNewton` (3) or `hydr_solver_2DPicard` (2):
  ```fortran
  num_nodes = n_hypool_leaf + n_hypool_stem + n_hypool_troot + (n_hypool_aroot + nshell) * nlevrhiz
  num_connections = n_hypool_leaf + n_hypool_stem + n_hypool_troot - 1 + (n_hypool_aroot + nshell) * nlevrhiz
  ```
  Arrays allocated: `ajac(num_nodes, num_nodes)`, `residual(num_nodes)`, `th_node(:)`, `psi_node(:)`, `dftc_dpsi_node(:)`, `ftc_node(:)`, `pm_node(:)`, `ipiv(:)`, `node_layer(:)`, `conn_up(:)`, `conn_dn(:)`, `kmax_up(:)`, `kmax_dn(:)`, `q_flux(:)`, `v_node(:)`, `z_node(:)`, `dth_node(:)`, `th_node_init(:)`, `th_node_prev(:)`, `h_node(:)`.
- When `hydr_solver` is `hydr_solver_1DTaylor` (1):
  ```fortran
  num_nodes = n_hypool_leaf + n_hypool_stem + n_hypool_troot + n_hypool_aroot + nshell
  num_connections = n_hypool_leaf + n_hypool_stem + n_hypool_troot + n_hypool_aroot + nshell - 1
  ```
  Only `conn_up(:)`, `conn_dn(:)`, `pm_node(:)` are allocated; the Taylor solver reuses per-layer scratch buffers rather than carrying a full site-wide state.

`SetConnections(hydr_solver_type)` (line 547) then wires `conn_up` / `conn_dn` into the appropriate flow graph for the chosen solver.

## Water Transfer Functions

All WTF classes live in `biogeophys/FatesHydroWTFMod.F90`.

### Water Retention Functions (WRF)

WRFs map between volumetric water content `θ` [m³ m⁻³] and matric potential `ψ` [MPa]. The base class `wrf_type` (lines 47-96) exposes:

- `th_from_psi(psi)` — water content for a given potential.
- `psi_from_th(th)` — potential for a given water content.
- `dpsidth_from_th(th)` — derivative `dψ/dθ` [MPa m³ m⁻³], needed for Jacobian and Taylor linearization.

Extended types:

- `wrf_type_vg` — Van Genuchten (1980). Parameters `alpha`, `n_vg`, `m_vg`, `th_sat`, `th_res`. `θ = θ_res + (θ_sat - θ_res) / [1 + (α |ψ|)^n]^m`.
- `wrf_type_cch` — Campbell-Clapp-Hornberger. Parameters `th_sat`, `ψ_sat`, `β`. `θ/θ_sat = (ψ/ψ_sat)^(-1/β)`. Used only for soil in the current FATES build.
- `wrf_type_smooth_cch` — smoothed Campbell with a quadratic near-saturation cap.
- `wrf_type_tfs` — Tissue Fraction Saturation (three-region: capillary, elastic, cavitation). Parameters include `θ_sat`, `θ_res`, `pinot` (osmotic potential at full turgor), `epsil` (bulk elastic modulus), `rwc_ft`, and capillary region slopes computed from `hydr_psi0` and `hydr_psicap`. TFS blends a pressure-volume curve with a cavitation vulnerability.

### Water Conductivity Functions (WKF)

WKFs map potential `ψ` to the fraction of maximum conductivity `ftc ∈ [0, 1]`:

- `ftc_from_psi(psi)` — fractional conductivity.
- `dftcdpsi_from_psi(psi)` — derivative `d(ftc)/dψ`.

Extended types:

- `wkf_type_vg` — Van Genuchten relative permeability combined with a plant tortuosity factor `tort`.
- `wkf_type_cch` — Campbell-Clapp-Hornberger relative permeability (soil only).
- `wkf_type_smooth_cch` — smoothed variant of the above.
- `wkf_type_tfs` — sigmoidal vulnerability curve

  ```
  ftc = max(min_ftc, 1 / (1 + (ψ_eff / p50)^avuln))
  ```

  (implemented in `ftc_from_psi_tfs` at `FatesHydroWTFMod.F90:1727-1738`). Parameters: `p50` and `avuln` from the PFT `hydr_p50_node(ft, pm)` and `hydr_avuln_node(ft, pm)` tables. This is the **Pammenter and Vanderwilligen (1998) sigmoidal form**, often abbreviated PV98 or Hill-type; it is **not** a Weibull. A Weibull curve would be `ftc = exp(-(ψ/b)^c)`, with fundamentally different shape parameters.

### Which WTFs are actually available for plants

`InitHydroGlobals` (`FatesPlantHydraulicsMod.F90:6198-6320`) is the sole dispatcher that wires `hydr_htftype_node(pm)` into the plant `wrf_plant` / `wkf_plant` pointer arrays. Only two branches are implemented:

```fortran
do pm = 1, n_plant_media
   select case(hydr_htftype_node(pm))
   case(van_genuchten_type)
      ! allocate wrf_type_vg / wkf_type_vg
   case(tfs_type)
      ! allocate wrf_type_tfs / wkf_type_tfs
   case default
      call endrun(msg="undefined water retention type for plants ...")
   end select
end do
```

- `tfs_type = 1` and `van_genuchten_type = 2` are valid plant WTF choices.
- `campbell_type = 3`, `smooth1_campbell_type = 31`, `smooth2_campbell_type = 32` trigger `endrun` if selected for plants.

The default parameter file sets `fates_hydro_htftype_node = 1, 1, 1, 1` (`fates_params_default.cdl:905`), so production runs use TFS for all four plant media unless a user modifies the parameter file.

The stomatal WKF (`wkf_plant(stomata_p_media, ft)`) is always allocated as a `wkf_type_tfs` at `FatesPlantHydraulicsMod.F90:6311-6316`, independently of `hydr_htftype_node`. Its `p50` and `avuln` are read from the PFT parameters `hydr_p50_gs` and `hydr_avuln_gs`.

### Soil WTFs are hard-coded to Campbell

`FatesPlantHydraulicsMod.F90:214-215` defines the site-level soil WRF and WKF as compile-time constants:

```fortran
integer, parameter :: soil_wrf_type  = campbell_type
integer, parameter :: soil_wkf_type  = campbell_type
```

`RestartHydrStates` / `UpdateSizeDepRhizHydProps` allocate `wrf_soil(j)` and `wkf_soil(j)` using these constants, drawing Campbell parameters from `bc_in(s)%sucsat_sisl`, `watsat_sisl`, and `bsw_sisl` aggregated via `AggBCToRhiz`. `hydr_htftype_node` does **not** control the soil WTFs; the soil is always Campbell. Lines 202-206 of the same module spell this out in a comment: "Right now we just hard-code the use of campbell_type for the soil".

### Global WRF / WKF pointer arrays

- `wrf_plant(0:n_plant_media, 1:numpft)` — plant WRFs, indexed by media type and PFT (index 0 is stomatal, which for WRF is unused but reserved). See allocation at `FatesPlantHydraulicsMod.F90:6229`.
- `wkf_plant(0:n_plant_media, 1:numpft)` — plant WKFs, index 0 holds the stomatal vulnerability curve.
- `si_hydr%wrf_soil(1:nlevrhiz)` — one WRF per rhizosphere layer (site level), always Campbell.
- `si_hydr%wkf_soil(1:nlevrhiz)` — one WKF per rhizosphere layer, always Campbell.

These are polymorphic pointers: the dispatcher allocates the concrete type (`wrf_type_vg`, `wrf_type_tfs`, `wrf_type_cch`, …) and assigns the base-class pointer via the `wrf_arr_type` / `wkf_arr_type` holder.

## Size-Dependent Updates

Whenever a cohort grows, fuses, or recruits, hydraulic state depends on the updated biomass and height. The update sequence is:

| Function | File / lines | Purpose |
| --- | --- | --- |
| `UpdatePlantHydrNodes(cohort, ft, height, si_hydr)` | `FatesPlantHydraulicsMod.F90` ~`1581-1662` | Recomputes node heights from updated plant height |
| `UpdatePlantHydrLenVol(cohort, csite_hydr)` | ~`1668-1796` | Recomputes compartment volumes from biomass pools |
| `UpdatePlantKmax(cohort_hydr, cohort, csite_hydr)` | ~`1836-2274` | Recomputes axial/radial conductances, applies xylem taper |
| `UpdateSizeDepRhizVolLenCon(site, bc_in)` | ~`2369-2641` | Recomputes rhizosphere shell geometry and conductances |
| `UpdateSizeDepPlantHydProps` / `UpdateSizeDepPlantHydStates` | high-level wrappers | Call the above in the correct order |
| `SavePreviousCompartmentVolumes` / `SavePreviousRhizVolumes` | state bookkeeping | Store `v_ag_init`, `v_troot_init`, etc. for water balance diagnostics |

Compartment volumes are derived from allometric biomass pools using per-organ saturated water content `thetas_*` and a carbon-to-biomass factor `c2b`:

- `v_ag(leaf)   = bleaf_allom / (c2b × thetas_leaf × denh2o)`
- `v_ag(stem)   = bsap_allom × agb_frac / (c2b × thetas_stem × denh2o)`
- `v_troot      = bsap_allom × (1 - agb_frac) / (c2b × thetas_troot × denh2o)`
- `v_aroot(j)   = bfineroot × layer_fraction(j) / (c2b × thetas_aroot × denh2o)`

Axial conductances use `kmax_node × A_cond / L_path × ftc`, where `A_cond` is derived from sapwood area and plant geometry, and the xylem taper `A_cond(z) = A_cond(base) × (z/h)^p_taper` is applied in the stem when `fates_hydro_p_taper` differs from 1. Root surface conductances use `(kmax_rsurf1 or kmax_rsurf2) × A_root`.

## Key Parameters (summary)

| Parameter | Symbol | Scope | Description | Units |
| --- | --- | --- | --- | --- |
| `fates_hydro_p50_node` | `hydr_p50_node(ft, pm)` | PFT × organ | `ψ` at 50% conductivity loss | MPa |
| `fates_hydro_avuln_node` | `hydr_avuln_node(ft, pm)` | PFT × organ | Vulnerability shape (sigmoidal exponent) | - |
| `fates_hydro_kmax_node` | `hydr_kmax_node(ft, pm)` | PFT × organ | Maximum xylem conductivity per unit area | kg m⁻¹ MPa⁻¹ s⁻¹ |
| `fates_hydro_epsil_node` | `hydr_epsil_node(ft, pm)` | PFT × organ (TFS) | Bulk elastic modulus | MPa |
| `fates_hydro_pinot_node` | `hydr_pinot_node(ft, pm)` | PFT × organ (TFS) | Osmotic potential at full turgor | MPa |
| `fates_hydro_thetas_node` | `hydr_thetas_node(ft, pm)` | PFT × organ | Saturated water content | m³ m⁻³ |
| `fates_hydro_resid_node` | `hydr_resid_node(ft, pm)` | PFT × organ | Residual water content | m³ m⁻³ |
| `fates_hydro_vg_alpha_node` | `hydr_vg_alpha_node(ft, pm)` | PFT × organ (VG) | Capillary length | MPa⁻¹ |
| `fates_hydro_vg_n_node` / `vg_m_node` | same | PFT × organ (VG) | Pore size distribution | - |
| `fates_hydro_p_taper` | `hydr_p_taper(ft)` | PFT | Xylem taper exponent | - |
| `fates_hydro_rfrac_stem` | `hydr_rfrac_stem(ft)` | PFT | Stem fraction of troot→canopy resistance | - |
| `fates_hydro_rs2` | `hydr_rs2(ft)` | PFT | Absorbing root radius | m |
| `fates_hydro_srl` | `hydr_srl(ft)` | PFT | Specific root length | m g⁻¹ |
| `fates_hydro_p50_gs` | `hydr_p50_gs(ft)` | PFT | Leaf potential at 50% stomatal closure | MPa |
| `fates_hydro_avuln_gs` | `hydr_avuln_gs(ft)` | PFT | Sigmoidal exponent for stomatal vulnerability | - |
| `fates_hydro_kmax_rsurf1` / `rsurf2` | `hydr_kmax_rsurf1/2` | Global | Soil↔root surface conductance | kg m⁻² MPa⁻¹ s⁻¹ |
| `fates_hydro_psi0` | `hydr_psi0` | Global (TFS) | Reference capillary potential | MPa |
| `fates_hydro_psicap` | `hydr_psicap` | Global (TFS) | Capillary exhaustion potential | MPa |
| `fates_hydro_htftype_node` | `hydr_htftype_node(1:4)` | Global | Plant WTF selector (1=TFS, 2=VG only) | - |
| `fates_hydro_solver` | `hydr_solver` | Global | 1=Taylor, 2=Picard, 3=Newton | - |

## Summary

The FATES plant hydraulic architecture represents each cohort as a fixed topology of leaf, stem, transporting-root, and per-rhizosphere-layer absorbing-root nodes, plus site-level rhizosphere shells. State is carried in `ed_cohort_hydr_type` (water content, potential, fractional conductivity, node geometry, per-compartment `kmax`) and `ed_site_hydr_type` (rhizosphere shells, layer mapping, site aggregates, error pools). Water retention and water conductivity functions live in `FatesHydroWTFMod` as polymorphic classes, but for plant tissues only TFS and Van Genuchten are wired up in `InitHydroGlobals`; Campbell is available only for soil, where it is hard-coded. Size-dependent helpers recompute volumes, lengths, and conductances whenever a cohort grows or recruits.

For the numerical methods that integrate this architecture forward in time, see [Hydraulic Solvers](solvers.md).

## Source References

- `main/FatesHydraulicsMemMod.F90:17-19` — solver ID parameters
- `main/FatesHydraulicsMemMod.F90:30-45` — compartment counts, `nshell`, media indices
- `main/FatesHydraulicsMemMod.F90:68-196` — `ed_site_hydr_type`
- `main/FatesHydraulicsMemMod.F90:201-321` — `ed_cohort_hydr_type`
- `main/FatesHydraulicsMemMod.F90:447-553` — `InitHydrSite` allocation and `SetConnections`
- `biogeophys/FatesPlantHydraulicsMod.F90:200-215` — WTF constants and soil hard-coding
- `biogeophys/FatesPlantHydraulicsMod.F90:218-242` — global pointer arrays and `max_wb_step_err`
- `biogeophys/FatesPlantHydraulicsMod.F90:6198-6320` — `InitHydroGlobals` plant WTF allocation
- `biogeophys/FatesHydroWTFMod.F90:47-242` — base and extended WRF/WKF classes
- `biogeophys/FatesHydroWTFMod.F90:1727-1738` — sigmoidal `ftc_from_psi_tfs`
- `parameter_files/fates_params_default.cdl:905` — default `fates_hydro_htftype_node = 1,1,1,1`
