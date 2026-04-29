---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Snow Layer Model and Hydrology

ELM's snowpack is a multi-layer, mass- and energy-conserving column anchored on top of the soil column. Layer indices run from `snl(c)+1` at the **top** (most recently fallen) to `0` at the **bottom** (just above the ground interface), using the same `dz`, `z`, and `zi` arrays as the soil — snow layers simply live in the negative indices `-nlevsno+1 .. 0`. The maximum number of layers is `nlevsno = 5` by default, extended to 16 when `use_extrasnowlayers = .true.`.

**Important flag distinction at d40b8431:** `use_extrasnowlayers` and `use_firn_percolation_and_compaction` are now independent flags. `use_extrasnowlayers` only switches the maximum layer count and the `dzmax_l16`/`dzmin16` arrays consumed by `DivideExtraSnowLayers` (`SnowHydrologyMod.F90:849, 1044`). The substantive firn physics (compaction in `SnowCompaction`, capping in `SnowWater`, snow-cap aerosol scaling in `AerosolMod`, refreeze grain radius in `SnowSnicarMod`, snow-mass-balance branches in `BalanceCheckMod`, and lake-snow handling in `LakeHydrologyMod`) is now gated on `use_firn_percolation_and_compaction`. Setting only `use_extrasnowlayers = .true.` does not enable any of those firn-aware paths.

Snow physics is split across two modules:

| Module | Role |
|---|---|
| `SnowHydrologyMod` (`biogeophys/SnowHydrologyMod.F90`) | Mass (liquid + ice) movement, compaction, layer (de)combination, new-snow capping, layer initialization |
| `SnowSnicarMod` (`biogeophys/SnowSnicarMod.F90`) | Radiative transfer (SNICAR / SNICAR-AD) for snow with aerosols; effective grain radius aging (documented in [radiation.md](radiation.md)) |

`SnowHydrologyMod` is what this document describes. Cross-links to optics and aging live in [radiation.md](radiation.md).

## Public subroutines

| Subroutine | Purpose |
|---|---|
| `SnowWater(bounds, num_snowc, filter_snowc, num_nosnowc, filter_nosnowc, atm2lnd_vars, aerosol_vars)` (`biogeophys/SnowHydrologyMod.F90:116`) | Updates liquid-water percolation through the snow column, sublimation, refreezing, and the bottom-layer output onto the soil surface. Uses `use_firn_percolation_and_compaction` at lines 236, 626, 640, 650, 668, 688, 727 |
| `SnowCompaction(bounds, num_snowc, filter_snowc, top_as_inst, dtime)` (`biogeophys/SnowHydrologyMod.F90:544`) | Updates layer thickness `dz` by destructive metamorphism, overburden creep, melt-induced collapse, and (with the firn flag) wind drift |
| `CombineSnowLayers(bounds, num_snowc, filter_snowc, aerosol_vars, dtime)` (`biogeophys/SnowHydrologyMod.F90:770`) | Merges layers that fall below the minimum thickness `dzmin` into a neighbor |
| `DivideSnowLayers(bounds, num_snowc, filter_snowc, aerosol_vars, is_lake)` (`biogeophys/SnowHydrologyMod.F90:1146`) | Splits layers that exceed their maximum thickness, preserving mass and aerosol content |
| `DivideExtraSnowLayers(bounds, num_snowc, filter_snowc, aerosol_vars, is_lake)` (`biogeophys/SnowHydrologyMod.F90:1811`) | Variant for up to 16-layer mode, gated on `use_extrasnowlayers` |
| `BuildSnowFilter(bounds, num_nolakec, filter_nolakec, num_snowc, filter_snowc, num_nosnowc, filter_nosnowc)` (`biogeophys/SnowHydrologyMod.F90:2568`) | Constructs the column filter used to loop over snow-only columns (`snl(c) < 0`) |
| `InitSnowLayers(bounds, snow_depth)` (`biogeophys/SnowHydrologyMod.F90:2138`) | Cold-start partitioning of a given total depth into the appropriate number of initial layers |
| `NewSnowBulkDensity(bounds, num_c, filter_c, top_as_inst, bifall)` (`biogeophys/SnowHydrologyMod.F90:2355`) | Bulk density of freshly falling snow as a function of air temperature and wind speed |
| `SnowCapping(bounds, num_nolakec, filter_initc, num_snowc, filter_snowc, aerosol_vars)` (`biogeophys/SnowHydrologyMod.F90:2240`) | Removes mass from the bottom snow layer when the total exceeds the column's capacity |

Private helpers: `WindDriftCompaction` (`biogeophys/SnowHydrologyMod.F90:2421`), `Combo` (`SnowHydrologyMod.F90:2491` — mass/energy merge of two layers).

## Snow column geometry

| Field | Meaning | Indexing |
|---|---|---|
| `snl(c)` | Negative number of active snow layers; 0 means no snow | Scalar per column |
| `dz(c,j)` | Layer thickness [m]; snow layers live at `j = snl(c)+1 .. 0` | `-nlevsno+1 : nlevgrnd` |
| `z(c,j)` | Node depth of layer midpoint [m], measured downward from the ground surface | same |
| `zi(c,j)` | Interface depth [m]; `zi(c,0)` = ground surface | `-nlevsno : nlevgrnd` |
| `h2osoi_liq(c,j)` | Liquid water in the layer [kg m<sup>-2</sup>] | same as `dz` |
| `h2osoi_ice(c,j)` | Ice mass in the layer [kg m<sup>-2</sup>] | same |
| `t_soisno(c,j)` | Layer temperature [K] | same |
| `snw_rds(c,j)` | Effective grain radius [μm] (written by `SnowAge_grain`; read by `SNICAR_RT`) | snow layers only |
| `frac_sno`, `frac_sno_eff` | Fraction of ground covered by snow (depth-dependent) | `col_ws` |
| `h2osno(c)` | Total column snow water (= Σ `h2osoi_liq + h2osoi_ice`) [mm H<sub>2</sub>O] | `col_ws` |
| `int_snow(c)` | Integrated snowfall for the current snow season [mm] | `col_ws` |
| `snow_depth(c)` | Total snow depth [m] | `col_ws` |

The default size bounds for the five-layer model are encoded in module-scope data (`biogeophys/SnowHydrologyMod.F90:806`):

```
data dzmin /0.010, 0.015, 0.025, 0.055, 0.115/     ! [m] minimum thickness by layer index
```

with corresponding `dzmax_u` and `dzmax_l` arrays used by `DivideSnowLayers` and `InitSnowLayers`. The 16-layer variant uses `dzmin16` and `dzmax_u16`/`dzmax_l16` with finer layering near the surface.

## New snow density — `NewSnowBulkDensity`

`NewSnowBulkDensity` (`biogeophys/SnowHydrologyMod.F90:2355`) computes the bulk density `bifall` (kg m<sup>-3</sup>) of any newly-fallen snow. It uses the CLMv5 temperature-dependent formulation with a wind-speed correction from Slater (2016, based on Liston et al. 2007):

```
if (forc_t > tfrz + 2)         bifall = 50 + 1.7 * 17^1.5                         ! ~= 169
else if (forc_t > tfrz - 15)   bifall = 50 + 1.7 * (forc_t - tfrz + 15)^1.5
else                            bifall = -(50/15 + 0.0333*15) * td - 0.0333 * td^2   ! td in deg C, floored at -57.55

! Wind correction (applied always when forc_wind > 0.1 m/s):
bifall += 266.861 * ((1 + tanh(forc_wind/5)) / 2)^8.8
```

Warmer, wetter snow falls denser; Arctic-cold snow falls less dense until below −57.55 C, where the function is clamped to avoid nonphysical behavior. Wind drift adds up to ~ 267 kg m<sup>-3</sup> for very high wind speeds.

The resulting `bifall` is used inside `CanopyHydrology` (not `SnowHydrology` directly) to convert `qflx_prec_grnd_snow` from kg m<sup>-2</sup> s<sup>-1</sup> to a depth increment `dz_snowf` and then either (a) add to the existing top snow layer, or (b) create a new first layer if the current `snl(c) == 0`. The 10-mm threshold for creating the first layer is referenced in [canopy_hydrology.md](canopy_hydrology.md).

## Snow water movement — `SnowWater`

`SnowWater` (`biogeophys/SnowHydrologyMod.F90:116`) is an **explicit, non-Richards** water percolation scheme. It permits a part of liquid water over the holding capacity (a tentative value, `ssi = 0.033 * porosity`) to percolate into the underlying layer. Water flow out of the bottom of the snowpack feeds the column water budget at the top of the soil.

Per-layer operations (top to bottom):

1. **Sublimation deposit/loss** — subtracted from ice content of the top layer using `qflx_sub_snow`. The capping branch at `SnowHydrologyMod.F90:236` is gated on `do_capsnow(c) .and. .not. use_firn_percolation_and_compaction` (i.e. the standard branch is skipped when firn mode is on, which has its own treatment).
2. **Effective porosity** is computed as `eff_porosity = 1 - vol_ice`.
3. **Irreducible liquid fraction** = `ssi` (= 0.033, a module-scope parameter).
4. **Percolation capacity** — water that exceeds `ssi * eff_porosity * dz` flows into the next layer down, carrying aerosols (BC, OC, dust) with it via `qin_*`/`qout_*` flux accumulators.
5. **Bottom layer** — excess water becomes `qflx_snomelt` + `qflx_snow2topsoi`, feeding the column water budget at the top of the soil.

Aerosol transport (BC/OC hydrophobic and hydrophilic, four dust bins) is tracked as integrated mass through `aerosol_vars`: `mss_bcphi_col`, `mss_bcpho_col`, `mss_ocphi_col`, `mss_ocpho_col`, `mss_dst1_col..mss_dst4_col`. These masses are the inputs to `SNICAR_RT` for computing snow albedo perturbation from aerosol darkening (see [radiation.md](radiation.md)).

After `SnowWater`, `AerosolFluxes` (called inside `SnowWater`) deposits fresh atmospheric aerosol flux onto the top layer.

## Snow compaction — `SnowCompaction`

`SnowCompaction` (`biogeophys/SnowHydrologyMod.F90:544`) reduces `dz(c,j)` based on **three** mechanisms in default mode (destructive metamorphism, overburden creep, melt) or **four** when `use_firn_percolation_and_compaction = .true.` (adds wind drift via `WindDriftCompaction`). Both branches share the same outer loop; the firn flag selects between the standard CLM4/SNTHERM formulation and a new, grain-size-aware physics with overburden via the Glen flow law and pseudo-pressure for wind drift.

### Module-scope constants

`biogeophys/SnowHydrologyMod.F90:572-581`:

```
c2  = 23.e-3 [m^3/kg]                 ! density scaling (overburden, default)
c3  = 2.777e-6 [1/s]                  ! destructive metamorphism rate (default)
c3_ams = 0.83e-6 [1/s]                ! Schneider et al. (2021), Table 2 (firn mode)
c4  = 0.04 [1/K]                      ! temperature scaling
c5  = 2.0                             ! wet-snow accelerator
dm  = 100 kg/m^3                      ! destructive metamorphism density threshold (default)
rho_dm = 150 kg/m^3                   ! destructive-metamorphism density threshold (firn mode; Anderson 1976; Schneider 2021)
eta0 = 9e5 kg-s/m^2                   ! viscosity coefficient (default overburden)
k_creep_snow = 9.2e-9 [m^3-s/kg]      ! creep coefficient for snow, bi <= 550 kg/m^3 (firn mode)
k_creep_firn = 3.7e-9 [m^3-s/kg]      ! creep coefficient for firn, bi > 550 kg/m^3 (firn mode)
```

These are calibration-relevant for permafrost / cold-snow simulations. The `c3_ams`, `k_creep_snow`, `k_creep_firn`, and `rho_dm` constants are new at `d40b8431` and only matter when the firn flag is on.

### Destructive metamorphism

For each layer (`SnowHydrologyMod.F90:660-686`):

```
bi     = h2osoi_ice / (frac_sno * dz)    ! partial ice density
td     = tfrz - t_soisno                 ! depression below 0 C
dexpf  = exp(-c4 * td)                   ! temperature factor

if (.not. use_firn_percolation_and_compaction) then
   ddz1 = -c3 * dexpf
   if (bi > dm) ddz1 *= exp(-46e-3 * (bi - dm))
else
   ! Firn mode: a "fresh-snow" pseudo-pressure term plus the SSA-aware destructive term
   ddz1_fresh = (-grav * (burden + wx/2)) / &
                (0.007 * min(max(bi,dm),denice)**(4.75 + min(td,0)/40))
   snw_ssa = 3.e6 / (denice * snw_rds(c,j))
   if (snw_ssa < 50) ddz1_fresh *= exp(-46.e-2 * (50 - snw_ssa))
   ddz1 = -c3_ams * dexpf
   if (bi > rho_dm) ddz1 *= exp(-46.0e-3 * (bi - rho_dm))
   ddz1 += ddz1_fresh
endif

if (h2osoi_liq > 0.01*dz*frac_sno)  ddz1 *= c5    ! wet-snow acceleration
```

### Overburden compaction

Load from all layers above is `burden(c)` (accumulated top-down). Then (`SnowHydrologyMod.F90:687-703`):

```
if (.not. use_firn_percolation_and_compaction) then
   ddz2 = -(burden + wx/2) * exp(-0.08*td - c2*bi) / eta0
else
   ! Glen flow-law form
   p_gls = max(denice/bi, 1) * grav * (burden + wx/2)
   if (bi <= 550) then    ! snow regime
      ddz2 = (-k_creep_snow * (max(denice/bi, 1) - 1) * &
              exp(-60.e6/(rgas*t_soisno)) * p_gls) / &
             (snw_rds(c,j)*1e-6)^2 - 1.0e-10
   else                   ! firn regime
      ddz2 = (-k_creep_firn * (max(denice/bi, 1) - 1) * &
              exp(-60.e6/(rgas*t_soisno)) * p_gls) / &
             (snw_rds(c,j)*1e-6)^2 - 1.0e-10
   endif
endif
```

The firn-mode form includes the `60e6 J/mol` activation energy for ice creep and a `1/grain^2` dependence.

### Melt compaction

When `imelt(c,j) == 1`, melt compaction is estimated (`SnowHydrologyMod.F90:707-725`):

```
ddz3 = -(1/dtime) * max(0, (frac_iceold(c,j) - fi) / frac_iceold(c,j))
```

For `subgridflag == 1` soil/crop columns there is a more sophisticated treatment that accounts for the change in snow-cover fraction `fsno_melt` using the `n_melt` SCA shape parameter. The branch uses `col_pp%is_soil(c) .or. col_pp%is_crop(c)` (the new accessor pattern, replacing the old landunit-type check).

### Wind drift (firn mode only)

`WindDriftCompaction` (`SnowHydrologyMod.F90:2421`) updates `ddz4` based on the Liston et al. (2007) wind-drift parameterization. Layer mobility is tracked via `mobile(c)`; once the top layer becomes immobile (ice crust), no underlying layer can wind-compact. Called only when `use_firn_percolation_and_compaction = .true.`.

### Time integration

Layer thickness is then updated:

```
pdzdtc   = ddz1 + ddz2 + ddz3 + ddz4
dz(c,j)  *= (1 + pdzdtc * dtime)
burden(c) += wx                    ! accumulate load for next layer down
```

## Layer management

Because new snow accumulates at the top and compacts / melts over time, the number of layers grows and shrinks. `CombineSnowLayers` and `DivideSnowLayers` enforce the mixing rules:

### `CombineSnowLayers`

`CombineSnowLayers` (`biogeophys/SnowHydrologyMod.F90:770`) merges layers whose `dz` or ice mass falls below `dzmin`. For each layer `j`, starting from the top:

1. If `dz(c,j) < dzmin(|j-snl(c)|)` **or** `h2osoi_ice(c,j) + h2osoi_liq(c,j)` is negligible, mark for merging.
2. Pick the neighbor `neibor` (prefer below; if at the bottom, merge with the layer above).
3. Call `Combo` (`biogeophys/SnowHydrologyMod.F90:2491`) to mass- and energy-conservatively merge the two: `dz_new = dz1 + dz2`, `wice_new = wice1 + wice2`, `wliq_new = wliq1 + wliq2`, `t_new` from enthalpy conservation, `snw_rds_new` mass-weighted.
4. Transfer aerosol masses (BC, OC, dust) by straight sum into the merged layer.
5. Renumber: bump `snl(c)` closer to 0 and shift layers upward.

If the merge results in `snl(c) == 0` and there is still some mass left, it is transferred to `int_snow` / `h2osno` and delivered to the top soil layer as `mflx_snowlyr_col`.

### `DivideSnowLayers`

`DivideSnowLayers` (`biogeophys/SnowHydrologyMod.F90:1146`) is the inverse operation. For each layer whose `dz` exceeds the maximum for its position, it splits into two, preserving ice mass, liquid mass, temperature, aerosol mass, and grain radius. The split ratio depends on whether the layer is the topmost (half-and-half) or not (top-biased to keep finer resolution near the fresh-snow source). Bookkeeping is done in local arrays then copied back into `col_pp%dz`, `col_ws%h2osoi_ice`, etc. After division a consistency check verifies mass conservation.

### `DivideExtraSnowLayers`

`DivideExtraSnowLayers` (`biogeophys/SnowHydrologyMod.F90:1811`) is the 16-layer variant, activated when `use_extrasnowlayers = .true.`. It uses `dzmax_u16` and `dzmax_l16`, which subdivide the near-surface more finely to better resolve the absorbed-radiation gradient from `SNICAR_RT`. Note that this routine reads `use_extrasnowlayers` (the layer-count switch), **not** `use_firn_percolation_and_compaction`.

## Initialization — `InitSnowLayers`

`InitSnowLayers` (`biogeophys/SnowHydrologyMod.F90:2138`) partitions a given `snow_depth` into the appropriate number of layers at cold start. Logic:

- If `snow_depth < dzmin16(1)`: no snow layers, `snl = 0`.
- If `snow_depth` fits within `[dzmin16(1), dzmax_l(1)]`: single layer `dz(c,0) = snow_depth`.
- Otherwise: increase `|snl|` until the total depth fits within the cumulative upper bounds `sum(dzmax_u(1..|snl|))`, set intermediate layers to `dzmax_u(j)`, split the two bottom layers into equal-size if possible (else fill the second-to-bottom at `dzmax_u(-snl-1)` and put the remainder in the bottom).
- Set node depth `z(c,j) = zi(c,j) - 0.5*dz(c,j)` and interface depth `zi(c,j-1) = zi(c,j) - dz(c,j)`, walking upward from `zi(c,0) = 0`.

Lake columns are special-cased to `snl = 0`, `dz = z = zi = 0`; their snow physics runs separately through `LakeHydrologyMod` (see [lake.md](lake.md)).

## Snow capping — `SnowCapping`

`SnowCapping` (`biogeophys/SnowHydrologyMod.F90:2240`) enforces a maximum snow water equivalent per column (set by the column's `capsnow` or glacier-capping rule). When exceeded, mass is removed from the bottom snow layer at constant density and temperature, producing `qflx_snwcp_ice_col` and `qflx_snwcp_liq_col` outputs that enter the column water budget. Density adjustment is acknowledged in-source as imperfect.

This routine is called twice per step: once for non-lake columns, once for lake columns. A separate initialization filter `filter_initc` ensures that the snow-capping flux fields are zeroed only once per group, avoiding double-counting.

## `BuildSnowFilter`

`BuildSnowFilter` (`biogeophys/SnowHydrologyMod.F90:2568`) is a trivial but hot-path utility: it walks the non-lake column filter and splits it into columns with `snl(c) < 0` (have snow) and `snl(c) == 0` (no snow). All downstream snow routines then operate only on the `filter_snowc` slice, avoiding wasted work on snow-free columns.

## Cross-links with SNICAR

`SnowHydrologyMod` and `SnowSnicarMod` share the snow column state but keep their concerns separate:

- `h2osoi_liq`, `h2osoi_ice`, `snw_rds`, aerosol masses (`mss_bcphi_col`, etc.) are written by `SnowHydrology` (water movement, layer management) and by `SnowAge_grain` (grain size only).
- `SNICAR_RT` / `SNICAR_AD_RT` read those fields and write snow albedo `albsnd`/`albsni` and per-layer absorption fractions into `surfalb_type`. Slope-corrected SWE is used when `use_finetop_rad = .true.` (see [radiation.md](radiation.md)).
- The per-layer absorbed shortwave (`sabg_lyr` computed in `SurfaceRadiation`, see [radiation.md](radiation.md)) then becomes the snowpack heat-source term in `SoilTemperature`, closing the radiation-to-snow-heating loop.

## Cross-links with the rest of biogeophys

- **Precipitation input**: `qflx_prec_grnd_snow` from [canopy_hydrology.md](canopy_hydrology.md) is the driver of new snow accumulation.
- **Sublimation / dew**: `qflx_sub_snow_patch`, `qflx_dew_snow_patch` from `CanopyFluxes` / `BareGroundFluxes` / `LakeFluxes` modify the top layer's `h2osoi_ice` before `SnowWater`.
- **Temperature coupling**: `SoilTemperature` (see `soil_temperature.md`) solves the coupled heat diffusion through the snow + soil column; phase changes update `h2osoi_liq`, `h2osoi_ice`, `imelt`, which in turn drive `SnowCompaction`'s melt metamorphism. When `use_T_rho_dependent_snowthk = .true.`, snow thermal conductivity uses a T- and density-dependent five-anchor formulation rather than Jordan (1991) — see `soil_temperature.md`.
- **Albedo feedback**: `SnowAge_grain` uses `h2osoi_liq`, `h2osoi_ice`, `t_soisno`, and the temperature gradient `dT/dz` between adjacent layers to update `snw_rds`. The refreeze radius `snw_rds_refrz` is now a **variable** that is reset to 1500 µm when `use_firn_percolation_and_compaction = .true.` and 1000 µm otherwise (see [aerosol_and_erosion.md](aerosol_and_erosion.md) and [radiation.md](radiation.md)).
- **Runoff**: The liquid flux exiting the bottom layer becomes an input to `SoilHydrologyMod` as ponding / infiltration.

Call order within one ELM time step (simplified):

```
BuildSnowFilter
CanopyHydrology                 -> qflx_prec_grnd_snow, NewSnowBulkDensity, first-layer creation
CanopyFluxes/BareGround/Urban   -> set qflx_sub_snow / qflx_dew_snow
SoilFluxes                       -> finalize top-layer heat flux
SoilTemperature                  -> update t_soisno, imelt, h2osoi_liq/ice via phase change
SnowWater                        -> percolate liquid, update aerosols
SnowCompaction                   -> update dz (3 or 4 mechanisms depending on firn flag)
SnowCapping                      -> enforce capacity
CombineSnowLayers                -> merge thin layers
DivideSnowLayers (or extra)     -> split thick layers
SnowAge_grain                    -> grain radius update (in SnowSnicarMod; firn-flag-dependent snw_rds_refrz)
SurfaceAlbedo (next step)        -> SNICAR_RT / SNICAR_AD_RT using updated snw_rds and aerosols
```
