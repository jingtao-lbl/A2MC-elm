---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Methane (CH4Mod)

This document covers ELM's methane module: production, oxidation, ebullition,
aerenchyma and diffusive transport, and atmospheric coupling. The physics
follows the CLM4Me design with vertically resolved, saturated and unsaturated
methane pools that interact with hydrology and decomposition state.

## Files

| File | Role |
|---|---|
| `biogeochem/CH4Mod.F90` | Methane driver, production, oxidation, aerenchyma transport, ebullition, tridiagonal diffusion, and annual bookkeeping. 3913 lines. |
| `biogeochem/CH4varcon.F90` | Namelist flags and switches for methane behavior (`ch4par_in` namelist). |
| `main/elm_varctl.F90` | Holds `use_lch4` (`:383`) — the top-level flag that gates the entire CH4 call path. |

## Control flag

`use_lch4` (`main/elm_varctl.F90:383`) turns the CH4 subsystem on or off at
runtime. When false, the `CH4` driver is not invoked, `forc_pch4` is never
read or written, no methane state is initialized, and all CH4 history fields
remain at `spval`. When true, `CH4Mod` runs every time step on all soil and
lake columns.

Inside `CH4varcon.F90`, finer-grained controls are read from `ch4par_in`:

| Flag | Default | Effect |
|---|---|---|
| `ch4offline` | `.true.` | If true, atmosphere receives no CH4 from land; net ecosystem methane production is not subtracted from NEE; `forc_pch4` is set to a prescribed 2009 constant. |
| `allowlakeprod` | `.false.` | Allow methane production inside lake columns. |
| `replenishlakec` | `.true.` | Keep lake soil C constant so lake production does not draw down stocks. |
| `fin_use_fsat` | `.false.` | Use ELM's `fsat` rather than Prigent-inversion for fractional inundation. |
| `usefrootc` | `.false.` | Use CLMCN fine-root C rather than Wania Arctic-sedge NPP-and-LAI for tiller C. |
| `use_aereoxid_prog` | `.true.` | If false, read `aereoxid` from parameter file (allows user override); if true, compute prognostically. |
| `usephfact` | `.false.` | Enable pH-limitation factor in methane production. |
| `anoxicmicrosites` | `.false.` | Arah and Stephen 1998 production above the water table. Hard-wired off. |
| `ch4rmcnlim` | `.false.` | Remove the N-limitation and low-moisture limitation on SOM HR when computing methanogenesis. |
| `ch4frzout` | `.false.` | "Freeze-out" pulse as in Mastepanov 2008. |
| `transpirationloss` | `.true.` | CH4 loss through transpiration. Impact < 1 Tg CH4/yr. |

`CH4varcon::CH4conrd` reads these from `ch4par_in` and MPI-broadcasts.

## Public surface

Two routines are public in `CH4Mod.F90`:

- `readCH4Params(ncid)` (`:1056-1299`) — read `CH4ParamsInst` from the
  parameter file.
- `CH4(bounds, num_soilc, filter_soilc, num_lakec, filter_lakec, num_soilp,
  filter_soilp, atm2lnd_vars, lakestate_vars, canopystate_vars,
  soilstate_vars, soilhydrology_vars, energyflux_vars, ch4_vars,
  lnd2atm_vars, elm_fates)` (`:1302-1917`) — the main driver.

The `ch4_type` object is the state and diagnostic container: production,
oxidation, ebullition, aerenchyma, and diffusion state for both saturated and
unsaturated fractions of each column, plus a lake-water pool. PFT-level tests
inside `ch4_type` methods now use `iscft`/`is_on_soil_col` helpers
(consistent with the broader `pftvarcon` refactor).

## Pool structure -- sat / unsat / lake

Every non-lake, non-urban column is treated simultaneously as a mixture of a
saturated fraction and an unsaturated fraction, with split driven by
`finundated(c)` (`ch4_vars%finundated_col`). Separate arrays track production,
oxidation, and concentration for each phase:

| Variable (column-level, vertically resolved) | Saturated | Unsaturated | Lake |
|---|---|---|---|
| CH4 production depth profile | `ch4_prod_depth_sat_col` | `ch4_prod_depth_unsat_col` | `ch4_prod_depth_lake_col` |
| CH4 oxidation depth profile | `ch4_oxid_depth_sat_col` | `ch4_oxid_depth_unsat_col` | `ch4_oxid_depth_lake_col` |
| Column CH4 conc | `conc_ch4_sat_col` | `conc_ch4_unsat_col` | `conc_ch4_lake_col` |
| Column O2 conc | `conc_o2_sat_col` | (unsat, analogous) | `conc_o2_lake_col` |
| Surface diffusive flux | `ch4_surf_diff_sat_col` | `ch4_surf_diff_unsat_col` | `ch4_surf_diff_lake_col` |
| Surface ebullition flux | `ch4_surf_ebul_sat_col` | `ch4_surf_ebul_unsat_col` | `ch4_surf_ebul_lake_col` |
| Surface aerenchyma flux | `ch4_surf_aere_sat_col` | `ch4_surf_aere_unsat_col` | -- |

At each time step the driver runs production, oxidation, aerenchyma, and
ebullition twice (once with `sat = 1`, once with `sat = 0`) and then solves
the transport equation. Lake columns go through a third call with
`lake = .true.`.

## Driver: `CH4` (`:1302`)

Flow:

1. **Atmospheric CH4.** If `ch4offline = .true.`, the first topounit on each
   gridcell has its `forc_pch4` set to `atmch4 * forc_pbot`; otherwise the
   coupler-supplied value is used and an error raised if zero. `c_atm(g,1..3)`
   stores top-of-atmosphere CH4, O2, CO2 mixing ratios in mol/m^3.
2. **Column pre-step.** Save `totcolch4_bef` for the mass-balance check, update
   lagged surface runoff `qflx_surf_lag` with a latitude-dependent time scale
   (30 d below 45 deg, 60 d above), refresh `finundated` via either `fsat` or
   the Prigent-inversion method.
3. **Root fraction.** Build per-patch `rootfraction(p, 1:nlevgrnd)` used by
   production (root respiration) and aerenchyma (tiller porosity).
4. **Unsaturated pass.** `ch4_prod(..., sat=0)`, `ch4_oxid(..., sat=0)`,
   `ch4_aere(..., sat=0)`, `ch4_ebul(..., sat=0)`, `ch4_tran(..., sat=0)`.
5. **Saturated pass.** Same with `sat = 1`.
6. **Lake pass.** Same with `lake = .true.`, gated on `allowlakeprod`.
7. **Gridcell aggregation.** Weighted by `finundated` plus dry fraction.
   `nem_col` accumulates into `nem_grc` (CO2-equivalent correction subtracted
   from NEE if methane is not passed to the atmosphere directly).
8. **Mass balance check.** `totcolch4 - totcolch4_bef - production + oxidation
   + surface fluxes` should be zero within tolerance.
9. **Annual update.** `ch4_annualupdate` (`:3782-3911`) resets annual
   accumulators.

## Production -- `ch4_prod` (`:1920`)

Computes production per soil layer below the water table, reusing CN
heterotrophic respiration as the base rate. Methanogenesis is a fixed fraction
`f_ch4` of CO2 that would be produced aerobically, adjusted for separate Q10,
pH, root litter fraction, and lagged inundation factor.

Parameters loaded from the parameter file:

| Parameter | Meaning |
|---|---|
| `q10ch4` | Additional Q10 applied above the soil decomposition temperature relationship. |
| `q10ch4base` | Base temperature at which the effective `f_ch4` equals the constant `f_ch4`. |
| `f_ch4` | Fraction of total C mineralization going to CH4 at `q10ch4base`. |
| `rootlitfrac` | Fraction of soil organic matter associated with roots. |
| `cnscalefactor` | Scale factor on CN decomposition for assigning methane flux. |
| `redoxlag` | Time lag (days) for `finundated_lag`. |
| `redoxlag_vertical` | Time lag (days) for per-layer saturation flag `layer_sat_lag`. |
| `lake_decomp_fact` | Base decomposition rate (1/s) at 25 deg C for lake soils. |
| `pHmax`, `pHmin` | pH bounds (enabled by `usephfact`). |
| `oxinhib` | O2 inhibition coefficient (m^3/mol). |

Process:

1. `hr_vr` from CN HR profile, `rr_vr` from root respiration weighted by
   rootfraction.
2. Extra temperature response `t_fact_ch4` using `q10ch4` relative to
   `q10ch4base`.
3. `f_ch4_adj = f_ch4 * t_fact_ch4 * (optional pH factor) * seasonalfin`,
   where `seasonalfin = max(0, finundated - annavg_finrw)`.
4. Per layer: `ch4_prod_depth(c, j) = (hr_vr + rootlitfrac*rr_vr) * f_ch4_adj
   * layer_sat_lag(c, j) / molC`.
5. O2 and CO2 decomposition-depth diagnostics computed alongside.

When `ch4rmcnlim = .true.`, removes `fphr` (fraction of potential HR, which
bundles moisture and N limitations).

## Oxidation -- `ch4_oxid` (`:2267`)

Double Michaelis-Menten kinetics on CH4 and O2, with separate parameters for
saturated (`vmax_ch4_oxid`, `k_m`, `k_m_o2`) and unsaturated (`vmax_oxid_unsat`,
`k_m_unsat`):

```
oxid_a = vmax_eff * (conc_ch4_rel / (k_m_eff + conc_ch4_rel))
              * (conc_o2_rel   / (k_m_o2  + conc_o2_rel))
              * q10_ch4oxid^((T - T0)/10)
```

A soil-moisture factor `smp_fact` (derived from `smp_crit`) reduces the rate
when moisture falls below threshold. Final flux:
`ch4_oxid_depth(c, j) = oxid_a * dz(c, j)`. Actual O2 and CH4 consumption in
`ch4_tran` is capped by available O2.

## Aerenchyma transport -- `ch4_aere` (`:2413`)

Vascular plant-mediated gas transport: CH4 out of soil through roots and
stems, O2 in, plus minor CH4 transpiration loss (`transpirationloss`). The
formulation distinguishes grasses from non-grasses via `nongrassporosratio`
and switches inundated vegetation to higher porosity (`unsat_aere_ratio`).
Arctic C3 grass and inundated vegetation are assumed to have tiller porosity.

Pre-computed tiller carbon for porosity:
- If `usefrootc = .true.`, tiller C from fine-root C.
- If `usefrootc = .false.`, derived from annual NPP and LAI (Wania
  Arctic-sedge parametrization).

Aerenchyma reoxidation fraction controlled by `aereoxid`. If
`use_aereoxid_prog = .true.`, computed from local O2 profile; otherwise read
from the parameter file (defaults to zero, i.e. complete venting).

`SiteOxAere` (`:2630-2792`) is a per-column, per-layer helper computing the
aerenchyma oxidation fraction.

## Ebullition -- `ch4_ebul` (`:2796`)

Bubble release when aqueous CH4 concentration exceeds Henry's-law solubility
by factor `vgc_max` (Wania et al.). Solubility `k_h_cc` depends on temperature
and pressure. Bubbles assigned a fixed CH4 fraction (Kellner et al. 2006) and
released at the water-table depth; they then travel to the atmosphere inside
`ch4_tran` without re-oxidation.

## Transport -- `ch4_tran` (`:2930`)

Reaction-diffusion equation for both CH4 and O2 with a Crank-Nicolson
tridiagonal scheme on the soil-layer grid:

1. **Competition.** Layer oxidation, plant respiration, and root-uptake O2
   demand capped at available O2 supply.
2. **Gas-phase partitioning.** Concentrations split into dissolved and
   gas-phase fractions using `k_h_cc`. In unsaturated soils only the gas
   fraction is diffusible; in saturated soils only the dissolved fraction.
3. **Diffusivity.** From soil texture, porosity, organic matter fraction, and
   liquid-water content. Constants `d_con_w`, `d_con_g`, `s_con` from
   `elm_varcon`.
4. **Boundary conditions.** Top of soil exchanges with atmosphere via
   `grnd_ch4_cond`. Snow and lake water added as bulk resistance. If
   `ch4frzout = .true.`, CH4 excluded from frozen pore-water fraction.
5. **Solve.** Tridiagonal solve per column, possibly sub-stepped if CFL
   condition requires `dtime_ch4 < dtime`.
6. **Surface flux.** `ch4_surf_diff_*` from top-of-soil gradient;
   `ch4_surf_ebul_*` queued by `ch4_ebul`; total surface CH4 flux is the sum
   plus aerenchyma.

## Atmospheric coupling

If `ch4offline = .true.`, computed `ch4_surf_flux_tot_col` is recorded for
diagnostics but not sent to the atmosphere. Instead, `nem_col` is the amount
by which land CO2 flux must be corrected to account for methane production
and oxidation. `nem_grc` accumulates into the gridcell correction to
`lnd2atm_vars%nem_grc`.

If `ch4offline = .false.`, `forc_pch4` is the actual atmospheric CH4
concentration from the coupler, and the land-to-atmosphere CH4 flux is a
proper coupler variable.

## Initialization and history

`Init` sets up the `ch4_type` via `InitAllocate`, `InitHistory`, and
`InitCold`. `InitHistory` registers methane-related history fields
(`CH4_SURF_FLUX`, `CH4_PROD_TOT`, `CH4_OXID_TOT`, `FINUNDATED`,
`CONC_CH4_SAT`, `CONC_CH4_UNSAT`, ebullition / aerenchyma flux diagnostics).
`Restart` handles read/write for model restarts.

## What CH4Mod does not do

- Does not run without `use_lch4 = .true.`.
- Does not compute `finundated` from scratch; `fsat` comes from soil
  hydrology, Prigent inversion is post-processing of water-table depth and
  surface runoff.
- Does not decompose soil carbon. It consumes CN decomposition (`hr_vr`,
  `somhr`, `lithr`) to set production rates.
- Does not handle lake water CH4 emissions via boiling ice-out at thaw.
  `ch4frzout` approximates the freeze-out pulse in frozen soils, but lake
  ebullition is through `ch4_ebul` like everywhere else.
