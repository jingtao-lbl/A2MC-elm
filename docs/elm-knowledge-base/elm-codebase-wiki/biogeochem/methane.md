---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Methane (CH4Mod)

This document covers ELM's methane module: production, oxidation, ebullition,
aerenchyma and diffusive transport, and the coupling to the atmosphere. The
physics follows the CLM4Me design with vertically resolved, saturated and
unsaturated methane pools that interact with the hydrology and decomposition
state.

## Files

| File | Role |
|---|---|
| `biogeochem/CH4Mod.F90` | Methane driver, production, oxidation, aerenchyma transport, ebullition, tridiagonal diffusion, and annual bookkeeping. ~3914 lines. |
| `biogeochem/CH4varcon.F90` | Namelist flags and switches for methane behavior (`ch4par_in` namelist) and the runtime `use_*` flags used by `CH4Mod`. |
| `main/elm_varctl.F90` | Holds `use_lch4` — the top-level flag that gates the entire CH4 call path. |

## Control flag

`use_lch4` (`main/elm_varctl.F90:349`) turns the CH4 subsystem on or off at
run time. When false, the `CH4` driver is not invoked and `forc_pch4`
(atmospheric CH4 mixing ratio) is never read or written; no methane state
is initialized, and all CH4 history fields remain at `spval`. When true,
`CH4Mod` runs every time step on all soil and lake columns.

Inside `CH4varcon.F90`, additional finer-grained controls are read from
`ch4par_in`:

| Flag | Default | Effect |
|---|---|---|
| `ch4offline` | `.true.` | If true, the atmosphere receives no CH4 from land; net ecosystem methane production is not subtracted from NEE and `forc_pch4` is set to a prescribed 2009 constant. |
| `allowlakeprod` | `.false.` | Allow methane production inside lake columns. |
| `replenishlakec` | `.true.` | Keep lake soil C constant so lake production does not draw down carbon stocks. |
| `fin_use_fsat` | `.false.` | Use ELM's `fsat` rather than the Prigent-inversion method to obtain fractional inundation. |
| `usefrootc` | `.false.` | Use CLMCN fine-root C rather than Wania Arctic-sedge NPP-and-LAI parametrization for tiller C used by aerenchyma. |
| `use_aereoxid_prog` | `.true.` | If false, read `aereoxid` from the parameter file (and allow user override); if true, compute prognostically. |
| `usephfact` | `.false.` | Enable pH-limitation factor in methane production. |
| `anoxicmicrosites` | `.false.` | Arah and Stephen 1998 production above the water table. Hard-wired off. |
| `ch4rmcnlim` | `.false.` | Remove the N-limitation and low-moisture limitation on SOM HR when computing methanogenesis. |
| `ch4frzout` | `.false.` | "Freeze-out" pulse as in Mastepanov 2008. |
| `transpirationloss` | `.true.` | CH4 loss through transpiration. Impact < 1 Tg CH4/yr. |

`CH4varcon::CH4conrd` (`biogeochem/CH4varcon.F90:93`) reads these from the
`ch4par_in` namelist group and MPI-broadcasts them to all ranks.

## Public surface

Only two routines are `public` in `CH4Mod.F90`
(`biogeochem/CH4Mod.F90:54-55`):

- `readCH4Params(ncid)` — read `CH4ParamsInst` from the parameter file.
- `CH4(bounds, num_soilc, filter_soilc, num_lakec, filter_lakec, num_soilp,
  filter_soilp, atm2lnd_vars, lakestate_vars, canopystate_vars,
  soilstate_vars, soilhydrology_vars, energyflux_vars, ch4_vars,
  lnd2atm_vars, elm_fates)` — the main driver.

The `ch4_type` object (defined earlier in the module) is the state and
diagnostic container: production, oxidation, ebullition, aerenchyma, and
diffusion state for both the saturated and unsaturated fractions of each
column, plus a lake-water pool.

## Pool structure — sat / unsat / lake

Every non-lake, non-urban column is treated simultaneously as a mixture of
a saturated fraction and an unsaturated fraction, with the fractional split
driven by `finundated(c)` (`ch4_vars%finundated_col`). Separate arrays track
production, oxidation, and concentration for each phase
(`biogeochem/CH4Mod.F90:1391-1418`):

| Variable (column-level, vertically resolved) | Saturated | Unsaturated | Lake |
|---|---|---|---|
| CH4 production depth profile | `ch4_prod_depth_sat_col` | `ch4_prod_depth_unsat_col` | `ch4_prod_depth_lake_col` |
| CH4 oxidation depth profile | `ch4_oxid_depth_sat_col` | `ch4_oxid_depth_unsat_col` | `ch4_oxid_depth_lake_col` |
| Column CH4 conc | `conc_ch4_sat_col` | `conc_ch4_unsat_col` | `conc_ch4_lake_col` |
| Column O2 conc | `conc_o2_sat_col` | (unsat, analogous) | `conc_o2_lake_col` |
| Surface diffusive flux | `ch4_surf_diff_sat_col` | `ch4_surf_diff_unsat_col` | `ch4_surf_diff_lake_col` |
| Surface ebullition flux | `ch4_surf_ebul_sat_col` | `ch4_surf_ebul_unsat_col` | `ch4_surf_ebul_lake_col` |
| Surface aerenchyma flux | `ch4_surf_aere_sat_col` | `ch4_surf_aere_unsat_col` | — |

At each time step the driver runs production, oxidation, aerenchyma, and
ebullition twice (once with `sat = 1`, once with `sat = 0`) and then
solves the transport equation. Lake columns go through a third call with
`lake = .true.`.

## Driver: `CH4`

Entry: `CH4` (`biogeochem/CH4Mod.F90:1302`). Flow:

1. **Atmospheric CH4.** If `ch4offline = .true.`, the first topounit on
   each gridcell has its `forc_pch4` set to `atmch4 * forc_pbot`; otherwise
   the coupler-supplied value is used and an error is raised if zero
   (`biogeochem/CH4Mod.F90:1465-1484`). `c_atm(g,1..3)` stores the top-of-
   atmosphere CH4, O2, and CO2 mixing ratios in mol/m³ for use downstream.
2. **Column pre-step.** Save `totcolch4_bef` for the mass-balance check,
   update lagged surface runoff `qflx_surf_lag` with a latitude-dependent
   time scale (30 d below 45° and 60 d above), and refresh `finundated`
   via either `fsat` or a decay-lag inversion of the Prigent observations
   (`biogeochem/CH4Mod.F90:1485-1500`).
3. **Root fraction.** Build per-patch `rootfraction(p, 1:nlevgrnd)` used
   by production (via root respiration) and aerenchyma (via tiller porosity).
4. **Unsaturated pass.** Call `ch4_prod(..., sat=0)`, `ch4_oxid(..., sat=0)`,
   `ch4_aere(..., sat=0)`, `ch4_ebul(..., sat=0)`, `ch4_tran(..., sat=0)`.
5. **Saturated pass.** Same sequence with `sat = 1`.
6. **Lake pass.** Same sequence with `lake = .true.` and the lake column
   filter `filter_lakec`, gated on `allowlakeprod`.
7. **Gridcell aggregation.** Weighted by `finundated` plus the dry
   fraction. The column net adjustment `nem_col` is accumulated into the
   gridcell `nem_grc` (the CO2-equivalent correction subtracted from NEE
   if methane is not passed to the atmosphere directly) and
   `ch4_surf_flux_tot_col` is the column total CH4 flux to the atmosphere.
8. **Mass balance check.** `totcolch4 - totcolch4_bef - production +
   oxidation + surface fluxes` should be zero to within tolerance.
9. **Annual update.** `ch4_annualupdate` resets annual accumulators.

## Production — `ch4_prod`

`ch4_prod` (`biogeochem/CH4Mod.F90:1920`) computes production per soil
layer below the water table, reusing the CN heterotrophic respiration as
the base rate. The key idea is that methanogenesis is a fixed fraction
`f_ch4` of the CO2 that *would* be produced aerobically, adjusted for a
separate Q10, pH, root litter fraction, and a lagged inundation factor.

Parameters (`biogeochem/CH4Mod.F90:66-110`, loaded from the parameter file):

| Parameter | Meaning |
|---|---|
| `q10ch4` | Additional Q10 applied ABOVE the soil decomposition temperature relationship. |
| `q10ch4base` | Base temperature at which the effective `f_ch4` equals the constant `f_ch4`. |
| `f_ch4` | Fraction of total C mineralization going to CH4 at `q10ch4base`. |
| `rootlitfrac` | Fraction of soil organic matter associated with roots. |
| `cnscalefactor` | Scale factor on CN decomposition for assigning methane flux. |
| `redoxlag` | Time lag (days) for `finundated_lag` used in production. |
| `redoxlag_vertical` | Time lag (days) for per-layer saturation flag `layer_sat_lag`. |
| `lake_decomp_fact` | Base decomposition rate (1/s) at 25°C for lake soils. |
| `pHmax`, `pHmin` | pH bounds for the optional pH factor (enabled by `usephfact`). |
| `oxinhib` | O2 inhibition coefficient (m³/mol), inhibits methanogenesis at high O2. |

Process (simplified):

1. Compute `hr_vr` vertically (from the CN heterotrophic respiration
   profile) and `rr_vr` (root respiration) for each soil layer below the
   water table, weighted by rootfraction.
2. Apply the extra temperature response: `t_fact_ch4` uses `q10ch4`
   relative to `q10ch4base`, independently of the CN temperature response
   already baked into `hr_vr`.
3. `f_ch4_adj = f_ch4 * t_fact_ch4 * (optional pH factor) * seasonalfin`,
   where `seasonalfin = max(0, finundated - annavg_finrw)` captures the
   excess of current inundation over the respiration-weighted annual mean.
   This represents the "methane production is higher during wet pulses"
   behavior.
4. Per layer: `ch4_prod_depth(c, j) = (hr_vr + rootlitfrac*rr_vr) * f_ch4_adj
   * layer_sat_lag(c, j) / molC`, where `layer_sat_lag` is an exponential
   moving average of saturation status gated by `redoxlag_vertical`.
5. O2 and CO2 decomposition-depth diagnostics are computed on the same
   loop for downstream use by `ch4_tran`.

When `ch4rmcnlim = .true.`, the code removes the `fphr` (fraction of
potential HR, which bundles moisture and N limitations) so that
methanogenesis can run at the unlimited rate; this option has not been
extensively tested (`biogeochem/CH4varcon.F90:60-63`).

## Oxidation — `ch4_oxid`

`ch4_oxid` (`biogeochem/CH4Mod.F90:2267`) uses double Michaelis-Menten
kinetics on CH4 and O2, with a separate set of parameters for the
saturated (`vmax_ch4_oxid`, `k_m`, `k_m_o2`) and unsaturated
(`vmax_oxid_unsat`, `k_m_unsat`) cases:

```
oxid_a = vmax_eff * (conc_ch4_rel / (k_m_eff + conc_ch4_rel))
              * (conc_o2_rel   / (k_m_o2  + conc_o2_rel))
              * q10_ch4oxid^((T - T0)/10)
```

where `vmax_eff` and `k_m_eff` are the sat- or unsat-specific values, and
`conc_ch4_rel`, `conc_o2_rel` are concentrations relative to soil water
volume, not bulk volume (because only the aqueous fraction is oxidized).
A soil-moisture factor `smp_fact` (derived from `smp_crit`) reduces the
rate when moisture falls below a threshold. The final flux is
`ch4_oxid_depth(c, j) = oxid_a * dz(c, j)`. Actual O2 and CH4 consumption
in `ch4_tran` is further capped by available O2 so that oxidation never
exceeds supply.

## Aerenchyma transport — `ch4_aere`

`ch4_aere` (`biogeochem/CH4Mod.F90:2413`) handles vascular plant-mediated
gas transport: CH4 out of the soil through roots and stems, O2 into the
soil the same way, and the minor CH4 transpiration-loss pathway (for
`transpirationloss = .true.`). The formulation distinguishes grasses
from non-grasses via `nongrassporosratio`
(`biogeochem/CH4Mod.F90:92-96`) and switches inundated vegetation to a
higher porosity than upland vegetation (`unsat_aere_ratio`). Arctic C3
grass (`nc3_arctic_grass`) and any vegetation in inundated areas are
assumed to have tiller porosity even outside the listed wetland PFTs —
this is the module's main Arctic-wetland heuristic.

Pre-computed tiller carbon for porosity:
- If `usefrootc = .true.`, tiller C is taken from fine-root C.
- If `usefrootc = .false.` (default), it is derived from annual NPP and
  LAI using the Wania Arctic-sedge parametrization.

The fraction of the aerenchyma flux that is reoxidized before reaching
the atmosphere is controlled by `aereoxid`. If `use_aereoxid_prog = .true.`
this is computed from the local O2 profile; otherwise it is read from the
parameter file (and defaults to zero, i.e. complete venting to the
atmosphere) (`biogeochem/CH4varcon.F90:16-18`). The residual flux is
added to `ch4_surf_aere_sat` or `ch4_surf_aere_unsat`.

`SiteOxAere` (`biogeochem/CH4Mod.F90:2631`) is a per-column, per-layer
helper that computes the aerenchyma oxidation fraction.

## Ebullition — `ch4_ebul`

`ch4_ebul` (`biogeochem/CH4Mod.F90:2797`) implements bubble release when
the aqueous CH4 concentration exceeds the saturation (Henry's law)
solubility by a factor `vgc_max` (Wania et al.). The solubility `k_h_cc`
depends on temperature and hydrostatic+atmospheric pressure. Bubbles are
assigned a fixed CH4 fraction (Kellner et al. 2006) and are released to
the water-table depth; they then travel to the atmosphere inside
`ch4_tran` without being re-oxidized along the way.

## Transport — `ch4_tran`

`ch4_tran` (`biogeochem/CH4Mod.F90:2931`) solves the reaction-diffusion
equation for both CH4 and O2 with a Crank-Nicolson tridiagonal scheme on
the soil-layer grid. The steps are:

1. **Competition.** Any one layer's oxidation, plant respiration, and
   root-uptake O2 demand is capped at the available O2 supply, so all
   processes are mutually consistent. The same cap applies to CH4 demand.
2. **Gas-phase partitioning.** Concentrations are split into dissolved
   and gas-phase fractions using `k_h_cc`. In unsaturated soils, only the
   gas fraction is diffusible; in saturated soils, only the dissolved
   fraction (with much lower molecular diffusivity) is diffusible.
3. **Diffusivity.** Set based on soil texture, porosity, organic matter
   fraction, and liquid-water content. `d_con_w` / `d_con_g` / `s_con`
   constants come from `elm_varcon`.
4. **Boundary conditions.** Top of soil exchanges with the atmosphere
   via `grnd_ch4_cond` (aerodynamic conductance, computed elsewhere).
   Snow and lake water are added as a bulk resistance; concentrations are
   not tracked inside snow, and oxidation is not allowed there either.
   If `ch4frzout = .true.`, CH4 is excluded from the frozen pore-water
   fraction to simulate the spring freeze-out pulse.
5. **Solve.** Tridiagonal solve per column, possibly sub-stepped if the
   CFL condition requires `dtime_ch4 < dtime`. Multiple `iter` iterations
   per physics step.
6. **Surface flux.** `ch4_surf_diff_*` is obtained from the top-of-soil
   gradient; `ch4_surf_ebul_*` is the ebullition flux queued by
   `ch4_ebul`; total surface CH4 flux is their sum plus aerenchyma.

## Atmospheric coupling

If `ch4offline = .true.`, the computed `ch4_surf_flux_tot_col` is recorded
for diagnostics but is not sent back to the atmosphere; instead, the
column-level net adjustment `nem_col` is the amount by which the land
CO2 flux to the atmosphere must be corrected to account for methane
production and oxidation (because methane production consumes C that
would otherwise have become CO2, and methane oxidation releases CO2 that
is not double-counted by the CN HR sink). `nem_grc` accumulates this
into the gridcell correction passed to `lnd2atm_vars%nem_grc`.

If `ch4offline = .false.`, `forc_pch4` is the actual atmospheric CH4
concentration coming from the coupler, and the land-to-atmosphere CH4
flux is a proper coupler variable. In this mode the land model
contributes directly to `CH4` concentrations in the atmosphere.

## Initialization and history

`Init` (`biogeochem/CH4Mod.F90:205`) sets up the `ch4_type` object via
`InitAllocate` (`:220`), `InitHistory` (`:317`), and `InitCold` (`:661`).
`InitHistory` registers the methane-related history fields
(`CH4_SURF_FLUX`, `CH4_PROD_TOT`, `CH4_OXID_TOT`, `FINUNDATED`,
`CONC_CH4_SAT`, `CONC_CH4_UNSAT`, and the ebullition / aerenchyma flux
diagnostics). `Restart` (`:942`) handles read/write of the methane state
for model restarts. `readCH4Params` (`:1056`) populates the
`CH4ParamsInst` type from the parameter file.

## What CH4Mod does not do

- It does not run without `use_lch4 = .true.`. No methane fields are
  initialized otherwise.
- It does not compute finundated from scratch. `fsat` comes from the
  soil-hydrology module, and the Prigent-inversion method is a
  physically-based post-processing of the water-table depth and surface
  runoff — the actual algorithm lives in `get_jwt` and the
  `finundated` initialization block in the driver.
- It does not decompose soil carbon. It consumes CN decomposition
  (`hr_vr`, `somhr`, `lithr`) to set production rates, but lets the CN
  subsystem own the carbon pools and their turnover.
- It does not handle lake water CH4 emissions via boiling ice-out at
  thaw; `ch4frzout` approximates the freeze-out pulse in frozen soils,
  but lake ebullition is through `ch4_ebul` like everywhere else.
