---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Conservation: Water and Energy Balance Checks

ELM enforces closure of the column and gridcell water and energy budgets every time step. This doc describes the three modules involved:

- `biogeophys/BalanceCheckMod.F90` (1140 lines at `d40b8431`, up from 1105) — per-timestep water, snow, solar, longwave, surface-energy, and soil-energy balance checks, with model abort on excessive imbalance. **Water-balance equation has six new flux terms at `d40b8431`.**
- `biogeophys/TotalWaterAndHeatMod.F90` — utility routines that compute total column water mass and heat content for land-cover change accounting and balance diagnostics. Public API unchanged.
- `biogeophys/WaterBudgetMod.F90` — gridcell/global water budget accumulator for the water budget table printed to the log. Monthly-snapshot timing reorganized.

## `BalanceCheckMod`

`biogeophys/BalanceCheckMod.F90:37-40` exports four public routines:

| Routine | Entry line | Purpose |
|---|---|---|
| `BeginColWaterBalance` | `BalanceCheckMod.F90:46-145` | Compute `begwb(c)` at the start of the time step |
| `ColWaterBalanceCheck` | `BalanceCheckMod.F90:148-779` | Close column water, snow, solar, longwave, SEB, soil balances |
| `BeginGridWaterBalance` | `BalanceCheckMod.F90:782-919` | Gridcell-level beginning state (used by `WaterBudgetMod`) |
| `GridBalanceCheck` | `BalanceCheckMod.F90:922-1138` | Gridcell-level budget closure |

### `BeginColWaterBalance`

`biogeophys/BalanceCheckMod.F90:46-145`. Sets `col_ws%begwb(c)` to the pre-timestep water mass per column. For a standard soil/crop/wetland column:

```
begwb(c) = h2ocan + h2osno + h2osfc + wa + sum_j(h2osoi_ice(j) + h2osoi_liq(j))
         + total_plant_stored_h2o(c)
```

(`BalanceCheckMod.F90:108-136`). Urban roof / sunwall / shadewall / impervious-road columns use a reduced definition `begwb = h2ocan + h2osno` because they lack soil moisture and aquifer storage. Lake columns use `begwb = h2osno` because lake water mass is held constant by design (see [lake.md](lake.md)). The `total_plant_stored_h2o` term is nonzero only when FATES hydraulics is enabled.

### `ColWaterBalanceCheck`

This is the main budget closure routine. Five independent checks in sequence.

#### 1. Column water balance — six new flux terms at d40b8431

`biogeophys/BalanceCheckMod.F90:336-341`. The residual `errh2o` is now:

```fortran
errh2o(c) = endwb(c) - begwb(c) &
        - (forc_rain_col(c) + forc_snow_col(c) + qflx_floodc(c) + qflx_from_uphill(c)        &
         + qflx_surf_irrig_col(c) + qflx_over_supply_col(c)                                  &
         - qflx_evap_tot(c) - qflx_surf(c) - qflx_h2osfc_surf(c) - qflx_to_downhill(c)       &
         - qflx_qrgwl(c) - qflx_drain(c) - qflx_drain_perched(c) - qflx_snwcp_ice(c)         &
         - qflx_ice_runoff_xs(c)                                                             &
         - qflx_lateral(c) + qflx_h2orof_drain(c) - qflx_lnd2ocn(c) + qflx_h2oocn_drain(c))  &
        * dtime
```

Source terms (positive contributions to storage):
- `forc_rain_col`, `forc_snow_col` — precipitation
- `qflx_floodc` — flood inflow from MOSART
- `qflx_surf_irrig_col`, `qflx_over_supply_col` — irrigation supply
- **`qflx_from_uphill`** *(new at d40b8431)* — IM2 hillslope inflow from upstream columns within the topounit
- **`qflx_h2orof_drain`** *(new at d40b8431)* — drainage from inundation/roof storage
- **`qflx_h2oocn_drain`** *(new at d40b8431)* — water transferred from ocean (negative `qflx_lnd2ocn` case captured here)

Sink terms (negative contributions to storage):
- `qflx_evap_tot`, `qflx_surf`, `qflx_h2osfc_surf` — evapotranspiration and surface runoff
- `qflx_qrgwl`, `qflx_drain`, `qflx_drain_perched` — glacier/wetland/lake runoff and subsurface drainage
- `qflx_snwcp_ice` — snow capping
- `qflx_lateral` — column-to-column transfer
- **`qflx_to_downhill`** *(new at d40b8431)* — IM2 hillslope outflow to downstream columns
- **`qflx_ice_runoff_xs`** *(new at d40b8431)* — excess ice runoff
- **`qflx_lnd2ocn`** *(new at d40b8431)* — lateral land-to-ocean subsurface flow (from `Drainage_To_OCN`)

`dwb(c) = (endwb(c) - begwb(c)) / dtime` is the diagnostic change in water storage.

The wiki at `60d9aad` documented an equation that was missing six flux terms; using that older equation now gives a non-closing budget on any run with `use_ocn_lnd_one_way`, `use_IM2_hillslope_hydrology`, or excess-ice-related drainage activated.

#### IM2 hillslope state update

When `use_IM2_hillslope_hydrology = .true.`, the topounit-level `top_ws%from_uphill(t)` accumulator is decremented before the column residual is computed (`BalanceCheckMod.F90:316-326`):

```fortran
if (use_IM2_hillslope_hydrology) then
   top_ws%from_uphill(t) = max(0._r8, top_ws%from_uphill(t) - (col_wf%qflx_from_uphill(c) * dtime))
   if (top_ws%from_uphill(t) < 1.e-20_r8) then
      top_ws%from_uphill(t) = 0._r8   ! prevent roundoff-driven negative state
   endif
endif
```

This is the topounit-level state that closes the IM2 hillslope budget across columns.

Urban sunwall/shadewall columns zero out `forc_rain_col`/`forc_snow_col` since walls do not intercept precipitation (`BalanceCheckMod.F90:309-315`).

When `glc_dyn_runoff_routing(g)` is true (a dynamic glacier on CISM), `qflx_glcice_frz` is added back to `errh2o` as a borrowed mass and `qflx_glcice_melt` is subtracted (`BalanceCheckMod.F90:368-372`).

**Tolerance and abort:**
- Warning threshold: `abs(errh2o) > 1e-7_r8` mm (`BalanceCheckMod.F90:377`).
- Non-urban abort threshold: `abs(errh2o) > 1e-4_r8` mm after `nstep > 2` triggers `call endrun(...)` with a full diagnostic dump that now also includes `qflx_lnd2ocn`, `qflx_h2orof_drain`, `qflx_ice_runoff_xs`, `qflx_h2oocn_drain` (`BalanceCheckMod.F90:419-450`).
- Urban roof/road columns share the same abort threshold (`BalanceCheckMod.F90:391-417`).

#### 2. Snow mass balance

`biogeophys/BalanceCheckMod.F90:455-563`. Only runs when `col_pp%snl(c) < 0` (at least one explicit snow layer). Defines:

```
snow_sources = qflx_prec_grnd + qflx_dew_snow + qflx_dew_grnd
snow_sinks   = qflx_sub_snow  + qflx_evap_grnd + qflx_snow_melt
             + qflx_snwcp_ice + qflx_snwcp_liq + qflx_sl_top_soil
```

For lake (`col_pp%is_lake(c)`), soil (`col_pp%is_soil(c) .or. col_pp%is_crop(c)`), and glacier landunits the definition is refined — at `d40b8431` the routine uses these `is_*` accessors instead of the old `lun_pp%itype(l) == istdlak`/`istsoil`/`istcrop` style (`BalanceCheckMod.F90:472, 500`). Lake snow uses `frac_sno_eff` weighting and accounts for `do_capsnow`; soil columns optionally add `qflx_h2osfc_to_ice`. Firn-mode (`use_firn_percolation_and_compaction = .true.`) configurations treat capping differently — the wiki at `60d9aad` cited `use_extrasnowlayers` here, which is now stale.

`errh2osno(c) = (h2osno - h2osno_old) - (snow_sources - snow_sinks) * dtime`. Warning threshold: `1e-7`. Abort threshold: `1e-4` mm.

#### 3. Solar radiation balance

`biogeophys/BalanceCheckMod.F90:565-688`. Closure check:
```
errsol(p) = fsa(p) + fsr(p) - (forc_solad(t,1) + forc_solad(t,2) + forc_solai(t,1) + forc_solai(t,2))
```
Urban patches skip this check since the urban module does its own internal solar balance. The tolerance is loosened for FATES-active patches (`BalanceCheckMod.F90:654-658`):

```fortran
if (use_fates) then
   sol_err_th = 5.e-7_r8
else
   sol_err_th = 1.e-7_r8
endif
```

Abort threshold is `1e-5` W m^-2 (`BalanceCheckMod.F90:673`).

#### 4. Longwave radiation balance

`biogeophys/BalanceCheckMod.F90:690-712`. For non-urban patches:
```
errlon(p) = eflx_lwrad_out(p) - eflx_lwrad_net(p) - forc_lwrad(t)
```
Warning `1e-7`, abort `1e-5` W m^-2.

#### 5. Surface energy balance

`biogeophys/BalanceCheckMod.F90:714-739`. For non-urban patches:
```
errseb(p) = sabv + sabg_chk + forc_lwrad - eflx_lwrad_out
          - eflx_sh_tot - eflx_lh_tot - eflx_soil_grnd
```
For urban patches, the formulation adds back the wasteheat, AC, and traffic terms:
```
errseb(p) = sabv + sabg - eflx_lwrad_net - eflx_sh_tot - eflx_lh_tot - eflx_soil_grnd
          + eflx_wasteheat + eflx_heat_from_ac + eflx_traffic
```
Abort threshold `1e-5` W m^-2 (`BalanceCheckMod.F90:730`).

Note `sabg_chk = (1-frac_sno)*sabg_soil + frac_sno*sabg_snow` — this is the **current-timestep** partitioning used in the balance check, which differs from `sabg` used elsewhere because `frac_sno` can change within a timestep.

#### 6. Soil / lake energy balance

`biogeophys/BalanceCheckMod.F90:741-779`. The residual `errsoi_col(c)` is written by `SoilTemperature` and `LakeTemperature` after their internal energy conservation bookkeeping. Warning `1e-5`, abort `1e-4` W m^-2.

### Gridcell balance

`BeginGridWaterBalance` and `GridBalanceCheck` (`BalanceCheckMod.F90:782, 922`) aggregate column-level states to the gridcell using `subgridAveMod::c2g` and apply the same residual check at the gridcell level, accounting for dynamic land-cover terms `qflx_liq_dynbal` and `qflx_ice_dynbal`.

## `TotalWaterAndHeatMod`

`biogeophys/TotalWaterAndHeatMod.F90` provides utility routines used primarily by the dynamic landunit area-adjustment machinery (so that water and heat are conserved when weights shift between landunits). Public routines:

| Routine | Purpose |
|---|---|
| `ComputeWaterMassNonLake` | Total water mass (liquid + ice) for non-lake columns |
| `ComputeWaterMassLake` | Total water mass for lake columns |
| `ComputeLiqIceMassNonLake` | Same, separated into liquid and ice |
| `ComputeLiqIceMassLake` | Same, lake |
| `ComputeHeatNonLake` | Total heat content for non-lake columns |
| `ComputeHeatLake` | Total heat content for lake columns |
| `AdjustDeltaHeatForDeltaLiq` | Correct gridcell heat change for implicit liquid runoff enthalpy |
| `LiquidWaterHeat` | Heat content of a given liquid water mass at a given temperature |

The public API is unchanged at `d40b8431`. The only internal change is that the soil-layer geometry initialization now reads `ZSOI` directly from the input file when available, otherwise falling back to the default ELM `scalez`/`zecoeff` layers. This is in init code, not the public routines.

### Water mass accounting

`ComputeLiqIceMassNonLake` accumulates:

- Snow layers (`h2osoi_liq(c,j)`, `h2osoi_ice(c,j)` for `j = snl(c)+1, 0`).
- Soil layers (`j = 1, nlevgrnd`), skipped for urban impervious columns.
- Aquifer water `wa(c)` for soil/crop/wet/ice and pervious urban road columns.
- Canopy water `h2ocan_patch * wtcol(p)` summed over active patches (soil/crop landunits only).

Note that `h2osfc`, `snocan` and `total_plant_stored_h2o` are intentionally excluded from the water-mass calculation used by dynamic-landunit accounting but are still tracked separately by `BalanceCheckMod`.

### Heat content accounting

`ComputeHeatNonLake` uses the base temperature `heat_base_temp = tfrz`. The base must equal `tfrz` because:

- Liquid pools without an explicit temperature are assumed to be at `heat_base_temp`; this is reasonable only for `tfrz`.
- `AdjustDeltaHeatForDeltaLiq` does not account for ice enthalpy changes separately, implicitly assuming runoff ice leaves at `heat_base_temp` — again consistent only with `tfrz`.

### `AdjustDeltaHeatForDeltaLiq` and liquid enthalpy

This routine corrects gridcell heat change for the enthalpy carried by liquid that flows between landunits during land-cover change. It uses `LiquidWaterHeat` and clips the water temperature to `[DeltaLiqMinTemp, DeltaLiqMaxTemp] = [tfrz, tfrz + 35]` to keep the adjustment physically reasonable.

Private helpers `AccumulateLiquidWaterHeat` and `TempToHeat` convert temperature differences to enthalpy changes using `cpliq`, `cpice`, and `hfus`.

## `WaterBudgetMod`

`biogeophys/WaterBudgetMod.F90` aggregates gridcell water fluxes and states into globally summed budgets that are printed to the log at various reporting periods.

### Flux and state indices

Six global fluxes:

| Index | Name | Quantity |
|---|---|---|
| `f_rain` | `rain` | Rain forcing from atmosphere |
| `f_snow` | `snow` | Snow forcing from atmosphere |
| `f_evap` | `evap` | Total evapotranspiration sink |
| `f_roff` | `runoff` | Total liquid runoff (surf + surfp + sub + subp + gwl) |
| `f_ioff` | `frzrof` | Ice runoff |
| `f_irri` | `irrig` | Irrigation supply |

Fifteen global states, split into `_beg` and `_end` pairs for total water, canopy water, snow, surface water, soil liquid, soil ice, aquifer water, plus a final `w_errh2o` accumulator.

### Reporting periods

Five period slots: `p_inst`, `p_day`, `p_mon`, `p_ann`, `p_inf`. Each has its own flux and state accumulator (`budg_fluxG`, `budg_stateG`).

### Driver routines

- `WaterBudget_Reset(mode)` — zero out specified period accumulators.
- `WaterBudget_Run(bounds, atm2lnd_vars, lnd2atm_vars, soilhydrology_vars)` — compute the per-gridcell contributions weighted by area and add to `budg_fluxL`, `budg_stateL`.
- `WaterBudget_Accum` — call `WaterBudget_Run` and advance period counters.
- `WaterBudget_Sum0` — MPI reduce `L` to global `G` sums and reset local buffers.
- `WaterBudget_Print(...)` — emit the formatted budget table.
- `WaterBudget_SetBeginningMonthlyStates`, `WaterBudget_SetEndingMonthlyStates` — snapshot states for monthly summaries.
- `WaterBudget_Restart` — read/write budget state from/to restart files.

### Monthly snapshot timing reorganized

At `d40b8431`, the timing for the begin-of-month TWS snapshot uses `get_prev_date` and a `get_nstep() <= 1` guard (`WaterBudgetMod.F90:704-713`):

```fortran
call get_prev_date(year_prev, month_prev, day_prev, sec_prev)

! At the beginning of a simulation, save grid-level TWS based on
! 'begwb' from the current time step
if (day_prev == 1 .and. sec_prev == 0 .and. get_nstep() <= 1) then
   call c2g(bounds, begwb, tws_month_beg_grc, ...)
endif
```

The end-of-month snapshot uses `get_curr_date` and a `get_nstep() >= 1` guard (`WaterBudgetMod.F90:743-749`). The wiki at `60d9aad` cited `day_curr == 1`; the `prev_date`-based logic is more robust to the start-of-run transient. Reporting periods and index list are unchanged.

### Connection to `BalanceCheck`

The `errh2o(c)` residuals computed in `ColWaterBalanceCheck` are aggregated to `errh2o_grc` and accumulated into `budg_stateL(s_w_errh2o, :)`, providing the "error h2o" line in the printed budget table. A non-trivial residual here indicates either a bug or a tolerance breach — the abort paths in `BalanceCheckMod` catch the latter first.

## Interfaces with other subsystems

- **Canopy fluxes** — `qflx_evap_tot`, `eflx_sh_tot`, `eflx_lh_tot`, and `eflx_soil_grnd` from `CanopyFluxesMod` / `BareGroundFluxesMod` feed directly into the surface energy balance check. See [canopy_fluxes.md](canopy_fluxes.md).
- **Soil temperature / lake temperature** — both write `errsoi` per column, which is picked up by `ColWaterBalanceCheck` stage 6. See [soil_temperature.md](soil_temperature.md) and [lake.md](lake.md).
- **Soil hydrology** — `qflx_surf`, `qflx_drain`, `qflx_drain_perched`, `qflx_qrgwl` come from `HydrologyDrainageMod` and `HydrologyNoDrainageMod`. **`qflx_lnd2ocn`, `qflx_h2oocn_drain`, `qflx_ice_runoff_xs` are produced by `Drainage_To_OCN` and consumed by the new water-balance equation** (see [soil_hydrology.md](soil_hydrology.md)).
- **IM2 hillslope hydrology** — `qflx_from_uphill` (source) and `qflx_to_downhill` (sink) from `SurfaceRunoff` and `HydrologyDrainage` enter the water-balance equation; `top_ws%from_uphill(t)` is updated in `BalanceCheckMod` itself.
- **Dynamic landunits** — `TotalWaterAndHeatMod` is called by `dyn_subgrid` routines to conserve mass and heat across shifting landunit weights; `AdjustDeltaHeatForDeltaLiq` is the link point.
- **Glacier coupling** — `glc_dyn_runoff_routing` branches in the water balance adjust `errh2o` to account for mass transfers between ELM and CISM.
- **Urban** — urban columns have reduced `begwb` definitions, skip the per-column solar and longwave balance checks (those are done separately inside the urban radiation module), and use a distinct SEB closure that credits wasteheat, AC heat, and traffic. See [urban.md](urban.md).

## Tolerance table summary

(Unchanged at `d40b8431`; the equation it defends has changed.)

| Check | Warning | Abort |
|---|---|---|
| Column water `errh2o` | `1e-7` mm | `1e-4` mm |
| Snow water `errh2osno` | `1e-7` mm | `1e-4` mm |
| Solar `errsol` (non-FATES) | `1e-7` W m^-2 | `1e-5` W m^-2 |
| Solar `errsol` (FATES active) | `5e-7` W m^-2 | `1e-5` W m^-2 |
| Longwave `errlon` | `1e-7` W m^-2 | `1e-5` W m^-2 |
| Surface energy `errseb` | `1e-7` W m^-2 | `1e-5` W m^-2 |
| Soil / lake energy `errsoi_col` | `1e-5` W m^-2 | `1e-4` W m^-2 |

The first-two-timestep exemption (`nstep > 2`) is applied to every abort path to allow initialization transients to settle.
