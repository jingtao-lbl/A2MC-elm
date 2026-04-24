---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Conservation: Water and Energy Balance Checks

ELM enforces closure of the column and gridcell water and energy budgets every time step. This doc describes the three modules involved:

- `biogeophys/BalanceCheckMod.F90` - per-timestep water, snow, solar, longwave, surface-energy, and soil-energy balance checks, with model abort on excessive imbalance.
- `biogeophys/TotalWaterAndHeatMod.F90` - utility routines that compute total column water mass and heat content for land-cover change accounting and balance diagnostics.
- `biogeophys/WaterBudgetMod.F90` - gridcell/global water budget accumulator for the water budget table printed to the log.

## `BalanceCheckMod`

`biogeophys/BalanceCheckMod.F90:37-40` exports four public routines:

| Routine | Purpose |
|---|---|
| `BeginColWaterBalance` | Compute `begwb(c)` at the start of the time step |
| `ColWaterBalanceCheck` | Close column water, snow, solar, longwave, SEB, soil balances |
| `BeginGridWaterBalance` | Gridcell-level beginning state (used by `WaterBudgetMod`) |
| `GridBalanceCheck` | Gridcell-level budget closure |

### `BeginColWaterBalance`

`biogeophys/BalanceCheckMod.F90:46-145`. Sets `col_ws%begwb(c)` to the pre-timestep water mass per column. For a standard soil/crop/wetland column:

```
begwb(c) = h2ocan + h2osno + h2osfc + wa + sum_j(h2osoi_ice(j) + h2osoi_liq(j))
         + total_plant_stored_h2o(c)
```
(`biogeophys/BalanceCheckMod.F90:108-136`). Urban roof / sunwall / shadewall / impervious-road columns use a reduced definition `begwb = h2ocan + h2osno` because they lack soil moisture and aquifer storage (`biogeophys/BalanceCheckMod.F90:106-108`). Lake columns use `begwb = h2osno` (`biogeophys/BalanceCheckMod.F90:138-141`) because the lake water mass is held constant by design (`biogeophys/lake.md`). The `total_plant_stored_h2o` term is nonzero only when FATES hydraulics is enabled.

### `ColWaterBalanceCheck`

This is the main budget closure routine. It performs five independent checks in sequence.

#### 1. Column water balance

`biogeophys/BalanceCheckMod.F90:313-429`. The residual `errh2o` is computed as:

```
errh2o(c) = endwb(c) - begwb(c)
          - dtime * ( forc_rain_col  + forc_snow_col
                    + qflx_floodc + qflx_surf_irrig_col + qflx_over_supply_col
                    - qflx_evap_tot - qflx_surf  - qflx_h2osfc_surf
                    - qflx_qrgwl    - qflx_drain - qflx_drain_perched
                    - qflx_snwcp_ice - qflx_lateral + qflx_h2orof_drain )
```
(`biogeophys/BalanceCheckMod.F90:319-323`). Sources are precipitation, flood, irrigation; sinks are evapotranspiration, surface runoff, glacier/wetland/lake runoff, subsurface drainage, snow capping, and lateral columns-to-column flow.

Urban sunwall/shadewall columns zero out `forc_rain_col`/`forc_snow_col` since walls do not intercept precipitation (`biogeophys/BalanceCheckMod.F90:304-306`).

`dwb(c) = (endwb(c) - begwb(c)) / dtime` is the diagnostic change in water storage.

When `glc_dyn_runoff_routing(g)` is true (a dynamic glacier on CISM), `qflx_glcice_frz` is added back to `errh2o` as a borrowed mass (new ice ownership transferred to CISM) and `qflx_glcice_melt` is subtracted because meltwater is in `qflx_qrgwl` but the source mass was borrowed from beneath the column (`biogeophys/BalanceCheckMod.F90:336-353`).

**Tolerance and abort:**
- Warning threshold: `abs(errh2o) > 1e-7_r8` mm (`biogeophys/BalanceCheckMod.F90:358`).
- Non-urban abort threshold: `abs(errh2o) > 1e-4_r8` mm after `nstep > 2` triggers `call endrun(...)` with a full diagnostic dump (`biogeophys/BalanceCheckMod.F90:397-425`).
- Urban roof/road columns have the same abort threshold (`biogeophys/BalanceCheckMod.F90:372-395`).

#### 2. Snow mass balance

`biogeophys/BalanceCheckMod.F90:430-563`. Only runs when `col_pp%snl(c) < 0` (at least one explicit snow layer). Defines:

```
snow_sources = qflx_prec_grnd + qflx_dew_snow + qflx_dew_grnd
snow_sinks   = qflx_sub_snow  + qflx_evap_grnd + qflx_snow_melt
             + qflx_snwcp_ice + qflx_snwcp_liq + qflx_sl_top_soil
```
(`biogeophys/BalanceCheckMod.F90:443-445`). For lake (`istdlak`), soil (`istsoil`/`istcrop`/`istwet`), and glacier landunits the definition is refined - lake snow uses `frac_sno_eff` weighting and accounts for `do_capsnow`; soil columns optionally add `qflx_h2osfc_to_ice`; firn-model (`use_extrasnowlayers`) configurations treat capping differently. See `biogeophys/BalanceCheckMod.F90:447-507`.

`errh2osno(c) = (h2osno - h2osno_old) - (snow_sources - snow_sinks) * dtime` (`biogeophys/BalanceCheckMod.F90:509`). Warning threshold: `1e-7`. Abort threshold: `1e-4` mm (`biogeophys/BalanceCheckMod.F90:522-562`).

#### 3. Solar radiation balance

`biogeophys/BalanceCheckMod.F90:565-654`. Closure check:
```
errsol(p) = fsa(p) + fsr(p)
          - (forc_solad(t,1) + forc_solad(t,2) + forc_solai(t,1) + forc_solai(t,2))
```
(`biogeophys/BalanceCheckMod.F90:578-583`). Urban patches skip this check since the urban module does its own internal solar balance. The tolerance is loosened for FATES-active patches to `5e-7` W m^-2 (vs. `1e-7` for non-FATES) (`biogeophys/BalanceCheckMod.F90:620-626`) due to higher numerical roundoff in the FATES radiative transfer path. Abort threshold is `1e-5` W m^-2 (`biogeophys/BalanceCheckMod.F90:640`).

#### 4. Longwave radiation balance

`biogeophys/BalanceCheckMod.F90:656-677`. For non-urban patches:
```
errlon(p) = eflx_lwrad_out(p) - eflx_lwrad_net(p) - forc_lwrad(t)
```
(`biogeophys/BalanceCheckMod.F90:589-593`). Warning `1e-7`, abort `1e-5` W m^-2.

#### 5. Surface energy balance

`biogeophys/BalanceCheckMod.F90:679-720`. For non-urban patches:
```
errseb(p) = sabv + sabg_chk + forc_lwrad - eflx_lwrad_out
          - eflx_sh_tot - eflx_lh_tot - eflx_soil_grnd
```
(`biogeophys/BalanceCheckMod.F90:601-603`). For urban patches, the formulation adds back the wasteheat, AC, and traffic terms:
```
errseb(p) = sabv + sabg - eflx_lwrad_net - eflx_sh_tot - eflx_lh_tot - eflx_soil_grnd
          + eflx_wasteheat + eflx_heat_from_ac + eflx_traffic
```
(`biogeophys/BalanceCheckMod.F90:604-608`). Abort threshold `1e-5` W m^-2.

Note `sabg_chk = (1-frac_sno)*sabg_soil + frac_sno*sabg_snow` - this is the **current-timestep** partitioning used in the balance check, which differs from `sabg` used elsewhere because `frac_sno` can change within a timestep.

#### 6. Soil / lake energy balance

`biogeophys/BalanceCheckMod.F90:722-742`. The residual `errsoi_col(c)` is written by `SoilTemperature` and `LakeTemperature` after their internal energy conservation bookkeeping. Warning `1e-5`, abort `1e-4` W m^-2.

### Gridcell balance

`BeginGridWaterBalance` and `GridBalanceCheck` (`biogeophys/BalanceCheckMod.F90:749`, `889`) aggregate column-level states to the gridcell using `subgridAveMod::c2g` and apply the same residual check at the gridcell level, accounting for dynamic land-cover terms `qflx_liq_dynbal` and `qflx_ice_dynbal`.

## `TotalWaterAndHeatMod`

`biogeophys/TotalWaterAndHeatMod.F90` provides utility routines used primarily by the dynamic landunit area-adjustment machinery (so that water and heat are conserved when weights shift between landunits). Public routines (`biogeophys/TotalWaterAndHeatMod.F90:39-46`):

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

### Water mass accounting

`ComputeLiqIceMassNonLake` (`biogeophys/TotalWaterAndHeatMod.F90:164-299`) accumulates:

- Snow layers (`h2osoi_liq(c,j)`, `h2osoi_ice(c,j)` for `j = snl(c)+1, 0`).
- Soil layers (`j = 1, nlevgrnd`), skipped for urban impervious columns (`has_h2o = .false.`).
- Aquifer water `wa(c)` for soil/crop/wet/ice and pervious urban road columns.
- Canopy water `h2ocan_patch * wtcol(p)` summed over active patches (soil/crop landunits only).

Note that `h2osfc`, `snocan` and `total_plant_stored_h2o` are currently commented out of the water-mass sum (`biogeophys/TotalWaterAndHeatMod.F90:287-295`) - they are intentionally excluded from the water-mass calculation used by dynamic-landunit accounting but are still tracked separately by `BalanceCheckMod`.

### Heat content accounting

`ComputeHeatNonLake` uses the base temperature `heat_base_temp = tfrz` (`biogeophys/TotalWaterAndHeatMod.F90:66`). The comment block at `biogeophys/TotalWaterAndHeatMod.F90:51-66` explains why this must equal `tfrz`:

- Liquid pools without an explicit temperature are assumed to be at `heat_base_temp`; this is reasonable only for `tfrz`.
- `AdjustDeltaHeatForDeltaLiq` does not account for ice enthalpy changes separately, implicitly assuming runoff ice leaves at `heat_base_temp` - again consistent only with `tfrz`.

### `AdjustDeltaHeatForDeltaLiq` and liquid enthalpy

This routine corrects gridcell heat change for the enthalpy carried by liquid that flows between landunits during land-cover change. It uses `LiquidWaterHeat` (`biogeophys/TotalWaterAndHeatMod.F90:46`) and clips the water temperature to `[DeltaLiqMinTemp, DeltaLiqMaxTemp] = [tfrz, tfrz + 35]` (`biogeophys/TotalWaterAndHeatMod.F90:73-74`) to keep the adjustment physically reasonable.

Private helpers `AccumulateLiquidWaterHeat` and `TempToHeat` (`biogeophys/TotalWaterAndHeatMod.F90:77-79`) convert temperature differences to enthalpy changes using `cpliq`, `cpice`, and `hfus`.

## `WaterBudgetMod`

`biogeophys/WaterBudgetMod.F90` aggregates gridcell water fluxes and states into globally summed budgets that are printed to the log at various reporting periods. It is the ELM equivalent of the CLM water-balance diagnostic output.

### Flux and state indices

Six global fluxes (`biogeophys/WaterBudgetMod.F90:32-49`):

| Index | Name | Quantity |
|---|---|---|
| `f_rain` | `rain` | Rain forcing from atmosphere |
| `f_snow` | `snow` | Snow forcing from atmosphere |
| `f_evap` | `evap` | Total evapotranspiration sink |
| `f_roff` | `runoff` | Total liquid runoff (surf + surfp + sub + subp + gwl) |
| `f_ioff` | `frzrof` | Ice runoff |
| `f_irri` | `irrig` | Irrigation supply |

Fifteen global states (`biogeophys/WaterBudgetMod.F90:52-88`), split into `_beg` and `_end` pairs for total water, canopy water, snow, surface water, soil liquid, soil ice, aquifer water, plus a final `w_errh2o` accumulator.

### Reporting periods

`biogeophys/WaterBudgetMod.F90:89-100` defines five period slots: `p_inst` (instantaneous), `p_day`, `p_mon`, `p_ann`, `p_inf` (all-time since start of run). Each has its own flux and state accumulator (`budg_fluxG`, `budg_stateG`).

### Driver routines

- `WaterBudget_Reset(mode)` - zero out specified period accumulators.
- `WaterBudget_Run(bounds, atm2lnd_vars, lnd2atm_vars, soilhydrology_vars)` - compute the per-gridcell contributions weighted by area `af = area(g)/re^2 * frac(g)` (`biogeophys/WaterBudgetMod.F90:326-356`) and add to `budg_fluxL`, `budg_stateL`.
- `WaterBudget_Accum` - call `WaterBudget_Run` and advance period counters.
- `WaterBudget_Sum0` - MPI reduce `L` to global `G` sums and reset local buffers (`biogeophys/WaterBudgetMod.F90:363`).
- `WaterBudget_Print(budg_print_inst, budg_print_daily, ...)` - emit the formatted budget table.
- `WaterBudget_SetBeginningMonthlyStates`, `WaterBudget_SetEndingMonthlyStates` - snapshot states for monthly summaries.
- `WaterBudget_Restart` - read/write budget state from/to restart files.

### Connection to `BalanceCheck`

The `errh2o(c)` residuals computed in `ColWaterBalanceCheck` are aggregated to `errh2o_grc` and accumulated into `budg_stateL(s_w_errh2o, :)`, providing the "error h2o" line in the printed budget table. A non-trivial residual here indicates either a bug or a tolerance breach - the abort paths in `BalanceCheckMod` catch the latter first.

## Interfaces with other subsystems

- **Canopy fluxes** - `qflx_evap_tot`, `eflx_sh_tot`, `eflx_lh_tot`, and `eflx_soil_grnd` from `CanopyFluxesMod` / `BareGroundFluxesMod` feed directly into the surface energy balance check. See `biogeophys/canopy_fluxes.md`.
- **Soil temperature / lake temperature** - both write `errsoi` per column, which is picked up by `ColWaterBalanceCheck` stage 6. See `biogeophys/soil_temperature.md` and `biogeophys/lake.md`.
- **Soil hydrology** - `qflx_surf`, `qflx_drain`, `qflx_drain_perched`, `qflx_qrgwl` come from `HydrologyDrainageMod` and `HydrologyNoDrainageMod`. `wa(c)` is read from `soilhydrology_vars` for the water-mass sum. See `biogeophys/soil_hydrology.md`.
- **Dynamic landunits** - `TotalWaterAndHeatMod` is called by `dyn_subgrid` routines to conserve mass and heat across shifting landunit weights; `AdjustDeltaHeatForDeltaLiq` is the link point.
- **Glacier coupling** - `glc_dyn_runoff_routing` branches in the water balance adjust `errh2o` to account for mass transfers between ELM and CISM.
- **Urban** - urban columns have reduced `begwb` definitions, skip the per-column solar and longwave balance checks (those are done separately inside the urban radiation module), and use a distinct SEB closure that credits wasteheat, AC heat, and traffic. See `biogeophys/urban.md`.

## Tolerance table summary

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
