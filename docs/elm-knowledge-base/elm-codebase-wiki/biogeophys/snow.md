---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Snow Layer Model and Hydrology

ELM's snowpack is a multi-layer, mass- and energy-conserving column anchored on top of the soil column. Layer indices run from `snl(c)+1` at the **top** (most recently fallen) to `0` at the **bottom** (just above the ground interface), using the same `dz`, `z`, and `zi` arrays as the soil — snow layers simply live in the negative indices `-nlevsno+1 .. 0`. The maximum number of layers is `nlevsno = 5` by default, extended to 16 when `use_extrasnowlayers = .true.`.

Snow physics is split across two modules:

| Module | Role |
|---|---|
| `SnowHydrologyMod` (`biogeophys/SnowHydrologyMod.F90`) | Mass (liquid + ice) movement, compaction, layer (de)combination, new-snow capping, layer initialization |
| `SnowSnicarMod` (`biogeophys/SnowSnicarMod.F90`) | Radiative transfer (SNICAR / SNICAR-AD) for snow with aerosols; effective grain radius aging (documented in [radiation.md](radiation.md)) |

`SnowHydrologyMod` is what this document describes. Cross-links to optics and aging live in [radiation.md](radiation.md).

## Public subroutines

| Subroutine | Purpose |
|---|---|
| `SnowWater(bounds, num_snowc, filter_snowc, num_nosnowc, filter_nosnowc, atm2lnd_vars, aerosol_vars)` (`biogeophys/SnowHydrologyMod.F90:116`) | Updates liquid-water percolation through the snow column, sublimation, refreezing, and the bottom-layer output onto the soil surface |
| `SnowCompaction(bounds, num_snowc, filter_snowc, top_as_inst, dtime)` (`biogeophys/SnowHydrologyMod.F90:544`) | Updates layer thickness `dz` by destructive metamorphism, overburden creep, melt-induced collapse, and (with `use_extrasnowlayers`) wind drift |
| `CombineSnowLayers(bounds, num_snowc, filter_snowc, aerosol_vars, dtime)` (`biogeophys/SnowHydrologyMod.F90:770`) | Merges layers that fall below the minimum thickness `dzmin` into a neighbor |
| `DivideSnowLayers(bounds, num_snowc, filter_snowc, aerosol_vars, is_lake)` (`biogeophys/SnowHydrologyMod.F90:1146`) | Splits layers that exceed their maximum thickness, preserving mass and aerosol content |
| `DivideExtraSnowLayers(bounds, num_snowc, filter_snowc, aerosol_vars, is_lake)` (`biogeophys/SnowHydrologyMod.F90:1811`) | Variant for up to 16-layer mode |
| `BuildSnowFilter(bounds, num_nolakec, filter_nolakec, num_snowc, filter_snowc, num_nosnowc, filter_nosnowc)` (`biogeophys/SnowHydrologyMod.F90:2566`) | Constructs the column filter used to loop over snow-only columns (`snl(c) < 0`) |
| `InitSnowLayers(bounds, snow_depth)` (`biogeophys/SnowHydrologyMod.F90:2138`) | Cold-start partitioning of a given total depth into the appropriate number of initial layers |
| `NewSnowBulkDensity(bounds, num_c, filter_c, top_as_inst, bifall)` (`biogeophys/SnowHydrologyMod.F90:2353`) | Bulk density of freshly falling snow as a function of air temperature and wind speed |
| `SnowCapping(bounds, num_nolakec, filter_initc, num_snowc, filter_snowc, aerosol_vars)` (`biogeophys/SnowHydrologyMod.F90:2240`) | Removes mass from the bottom snow layer when the total exceeds the column's capacity |

Private helpers: `WindDriftCompaction` (`biogeophys/SnowHydrologyMod.F90:2419`), `Combo` (`SnowHydrologyMod.F90:2489` — mass/energy merge of two layers).

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

`NewSnowBulkDensity` (`biogeophys/SnowHydrologyMod.F90:2353`) computes the bulk density `bifall` (kg m<sup>-3</sup>) of any newly-fallen snow. It uses the CLMv5 temperature-dependent formulation with a wind-speed correction from Slater (2016, based on Liston et al. 2007):

```
if (forc_t > tfrz + 2)         bifall = 50 + 1.7 * 17^1.5                         ! ~= 169
else if (forc_t > tfrz - 15)   bifall = 50 + 1.7 * (forc_t - tfrz + 15)^1.5
else                            bifall = -(50/15 + 0.0333*15) * td - 0.0333 * td^2   ! td in deg C, floored at -57.55

! Wind correction (applied always when forc_wind > 0.1 m/s):
bifall += 266.861 * ((1 + tanh(forc_wind/5)) / 2)^8.8
```

(`biogeophys/SnowHydrologyMod.F90:2386-2410`). Warmer, wetter snow falls denser; Arctic-cold snow falls less dense until below −57.55 C, where the function is clamped to avoid nonphysical behavior. Wind drift adds up to ~ 267 kg m<sup>-3</sup> for very high wind speeds.

The resulting `bifall` is used inside `CanopyHydrology` (not `SnowHydrology` directly) to convert `qflx_prec_grnd_snow` from kg m<sup>-2</sup> s<sup>-1</sup> to a depth increment `dz_snowf` and then either (a) add to the existing top snow layer, or (b) create a new first layer if the current `snl(c) == 0`. The 10-mm threshold for creating the first layer is referenced in [canopy_hydrology.md](canopy_hydrology.md).

## Snow water movement — `SnowWater`

`SnowWater` (`biogeophys/SnowHydrologyMod.F90:116`) is an **explicit, non-Richards** water percolation scheme. Its in-source description (`biogeophys/SnowHydrologyMod.F90:121-128`) states:

> Evaluate the change of snow mass and the snow water onto soil. Water flow within snow is computed by an explicit and non-physical based scheme, which permits a part of liquid water over the holding capacity (a tentative value is used, i.e. equal to 0.033*porosity) to percolate into the underlying layer. [...] The water flow out of the bottom of the snow pack will participate as the input of the soil water and runoff.

Per-layer operations (top to bottom):

1. **Sublimation deposit/loss** — subtracted from ice content of the top layer using `qflx_sub_snow`.
2. **Effective porosity** is computed as `eff_porosity = 1 - vol_ice`.
3. **Irreducible liquid fraction** = `ssi` (= 0.033, a module-scope parameter).
4. **Percolation capacity** — water that exceeds `ssi * eff_porosity * dz` flows into the next layer down, carrying aerosols (BC, OC, dust) with it via `qin_*`/`qout_*` flux accumulators.
5. **Bottom layer** — excess water becomes `qflx_snomelt` + `qflx_snow2topsoi`, feeding the column water budget at the top of the soil.

Aerosol transport (BC/OC hydrophobic and hydrophilic, four dust bins) is tracked as integrated mass through `aerosol_vars`: `mss_bcphi_col`, `mss_bcpho_col`, `mss_ocphi_col`, `mss_ocpho_col`, `mss_dst1_col..mss_dst4_col`. These masses are the inputs to `SNICAR_RT` for computing snow albedo perturbation from aerosol darkening (see [radiation.md](radiation.md)).

After `SnowWater`, `AerosolFluxes` (called inside `SnowWater` at `biogeophys/SnowHydrologyMod.F90:136`) deposits fresh atmospheric aerosol flux onto the top layer.

## Snow compaction — `SnowCompaction`

`SnowCompaction` (`biogeophys/SnowHydrologyMod.F90:544`) reduces `dz(c,j)` based on three (standard) or four (`use_extrasnowlayers`) mechanisms. In-source description at `biogeophys/SnowHydrologyMod.F90:547-554`:

> Three metamorphisms of changing snow characteristics are implemented, i.e., destructive, overburden, and melt. The treatments of the former two are from SNTHERM.89 and SNTHERM.99 (1991, 1999). The contribution due to melt metamorphism is simply taken as a ratio of snow ice fraction after the melting versus before the melting.

Module-scope parameters (`biogeophys/SnowHydrologyMod.F90:572-581`):

```
c2  = 23.e-3 [m^3/kg]                ! density scaling
c3  = 2.777e-6 [1/s]                 ! destructive metamorphism rate
c4  = 0.04 [1/K]                     ! temperature scaling
c5  = 2.0                            ! wet-snow accelerator
dm  = 100 kg/m^3                     ! destructive metamorphism density threshold
eta0 = 9e5 kg-s/m^2                  ! viscosity coefficient
```

### Destructive metamorphism

At each layer (`biogeophys/SnowHydrologyMod.F90:662-681`):

```
bi     = h2osoi_ice / (frac_sno * dz)    ! partial ice density
td     = tfrz - t_soisno                 ! depression below 0 C
dexpf  = exp(-c4 * td)                   ! temperature factor
ddz1   = -c3 * dexpf
if (bi > dm)  ddz1 *= exp(-46e-3 * (bi - dm))    ! slowdown above 100 kg/m3
if (h2osoi_liq > 0.01*dz*frac_sno)  ddz1 *= c5   ! wet-snow acceleration
```

### Overburden compaction

Load from all layers above is `burden(c)` (accumulated top-down). Then (`biogeophys/SnowHydrologyMod.F90:687-689`):

```
ddz2 = -(burden + wx/2) * exp(-0.08*td - c2*bi) / eta0
```

In extra-layer mode, this is replaced by a grain-size-aware creep form with `k_creep_snow = 1.4e-9` and `k_creep_firn = 1.2e-9`, including the Arrhenius activation-energy factor `exp(-60e6 / (R*T))` and a `1/grain^2` dependence (`biogeophys/SnowHydrologyMod.F90:691-702`).

### Melt compaction

When `imelt(c,j) == 1`, melt compaction is estimated as (`biogeophys/SnowHydrologyMod.F90:707-725`):

```
ddz3 = -(1/dtime) * max(0, (frac_iceold(c,j) - fi) / frac_iceold(c,j))
```

For `subgridflag == 1` soil/crop columns there is a more sophisticated treatment that also accounts for the change in snow-cover fraction `fsno_melt` using the `n_melt` SCA shape parameter.

### Wind drift (extra-layers only)

`WindDriftCompaction` (`biogeophys/SnowHydrologyMod.F90:2419`) updates `ddz4` based on the Liston et al. (2007) wind-drift parameterization. Layer mobility is tracked via `mobile(c)`; once the top layer becomes immobile (ice crust), no underlying layer can wind-compact.

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
3. Call `Combo` (`biogeophys/SnowHydrologyMod.F90:2489`) to mass- and energy-conservatively merge the two: `dz_new = dz1 + dz2`, `wice_new = wice1 + wice2`, `wliq_new = wliq1 + wliq2`, `t_new` from enthalpy conservation, `snw_rds_new` mass-weighted.
4. Transfer aerosol masses (BC, OC, dust) by straight sum into the merged layer.
5. Renumber: bump `snl(c)` closer to 0 and shift layers upward.

If the merge results in `snl(c) == 0` and there is still some mass left, it is transferred to `int_snow` / `h2osno` and delivered to the top soil layer as `mflx_snowlyr_col`.

### `DivideSnowLayers`

`DivideSnowLayers` (`biogeophys/SnowHydrologyMod.F90:1146`) is the inverse operation. For each layer whose `dz` exceeds the maximum for its position, it splits into two, preserving ice mass, liquid mass, temperature, aerosol mass, and grain radius. The split ratio depends on whether the layer is the topmost (half-and-half) or not (top-biased to keep finer resolution near the fresh-snow source). Bookkeeping is done in local arrays `dzsno`, `swice`, `swliq`, `tsno`, `mbc_phi/pho`, `moc_phi/pho`, `mdst1..4`, `rds` and then copied back into `col_pp%dz`, `col_ws%h2osoi_ice`, etc. After division a consistency check (`dztot`, `snwicetot`, `snwliqtot`) verifies mass conservation.

### `DivideExtraSnowLayers`

`DivideExtraSnowLayers` (`biogeophys/SnowHydrologyMod.F90:1811`) is the 16-layer variant, activated when `use_extrasnowlayers = .true.`. It uses `dzmax_u16` and `dzmax_l16`, which subdivide the near-surface more finely to better resolve the absorbed-radiation gradient from `SNICAR_RT`.

## Initialization — `InitSnowLayers`

`InitSnowLayers` (`biogeophys/SnowHydrologyMod.F90:2138`) partitions a given `snow_depth` into the appropriate number of layers at cold start. The logic (`biogeophys/SnowHydrologyMod.F90:2182-2232`):

- If `snow_depth < dzmin16(1)`: no snow layers, `snl = 0`.
- If `snow_depth` fits within `[dzmin16(1), dzmax_l(1)]`: single layer `dz(c,0) = snow_depth`.
- Otherwise: increase `|snl|` until the total depth fits within the cumulative upper bounds `sum(dzmax_u(1..|snl|))`, set intermediate layers to `dzmax_u(j)`, split the two bottom layers into equal-size if possible (else fill the second-to-bottom at `dzmax_u(-snl-1)` and put the remainder in the bottom).
- Set node depth `z(c,j) = zi(c,j) - 0.5*dz(c,j)` and interface depth `zi(c,j-1) = zi(c,j) - dz(c,j)`, walking upward from `zi(c,0) = 0`.

Lake columns are special-cased to `snl = 0`, `dz = z = zi = 0` (`biogeophys/SnowHydrologyMod.F90:2170-2176`); their snow physics runs separately through `LakeHydrologyMod` (see [lake.md](lake.md)).

## Snow capping — `SnowCapping`

`SnowCapping` (`biogeophys/SnowHydrologyMod.F90:2240`) enforces a maximum snow water equivalent per column (set by the column's `capsnow` or glacier-capping rule). When exceeded, mass is removed from the bottom snow layer at constant density and temperature, producing `qflx_snwcp_ice_col` and `qflx_snwcp_liq_col` outputs that enter the column water budget. Density adjustment is acknowledged in-source as imperfect (`SnowHydrologyMod.F90:2248`: "Density and temperature of the layer are conserved (density needs some work, temperature is a state variable)").

This routine is called twice per step: once for non-lake columns, once for lake columns. A separate initialization filter `filter_initc` ensures that the snow-capping flux fields are zeroed only once per group, avoiding double-counting.

## `BuildSnowFilter`

`BuildSnowFilter` (`biogeophys/SnowHydrologyMod.F90:2566`) is a trivial but hot-path utility: it walks the non-lake column filter and splits it into columns with `snl(c) < 0` (have snow) and `snl(c) == 0` (no snow). All downstream snow routines then operate only on the `filter_snowc` slice, avoiding wasted work on snow-free columns.

## Cross-links with SNICAR

`SnowHydrologyMod` and `SnowSnicarMod` share the snow column state but keep their concerns separate:

- `h2osoi_liq`, `h2osoi_ice`, `snw_rds`, aerosol masses (`mss_bcphi_col`, etc.) are written by `SnowHydrology` (water movement, layer management) and by `SnowAge_grain` (grain size only).
- `SNICAR_RT` / `SNICAR_AD_RT` read those fields and write snow albedo `albsnd`/`albsni` and per-layer absorption fractions into `surfalb_type`.
- The per-layer absorbed shortwave (`sabg_lyr` computed in `SurfaceRadiation`, see [radiation.md](radiation.md)) then becomes the snowpack heat-source term in `SoilTemperature`, closing the radiation-to-snow-heating loop.

## Cross-links with the rest of biogeophys

- **Precipitation input**: `qflx_prec_grnd_snow` from [canopy_hydrology.md](canopy_hydrology.md) is the driver of new snow accumulation.
- **Sublimation / dew**: `qflx_sub_snow_patch`, `qflx_dew_snow_patch` from `CanopyFluxes` / `BareGroundFluxes` / `LakeFluxes` modify the top layer's `h2osoi_ice` before `SnowWater`.
- **Temperature coupling**: `SoilTemperature` (see `soil_temperature.md`) solves the coupled heat diffusion through the snow + soil column; phase changes update `h2osoi_liq`, `h2osoi_ice`, `imelt`, which in turn drive `SnowCompaction`'s melt metamorphism.
- **Albedo feedback**: `SnowAge_grain` uses `h2osoi_liq`, `h2osoi_ice`, `t_soisno`, and the temperature gradient `dT/dz` between adjacent layers to update `snw_rds`, which feeds the next step's `SNICAR_RT` — closing the grain-aging / albedo feedback loop.
- **Runoff**: The liquid flux exiting the bottom layer becomes an input to `SoilHydrologyMod` as ponding / infiltration.

Call order within one ELM time step (simplified):

```
BuildSnowFilter
CanopyHydrology                 -> qflx_prec_grnd_snow, NewSnowBulkDensity, first-layer creation
CanopyFluxes/BareGround/Urban   -> set qflx_sub_snow / qflx_dew_snow
SoilFluxes                       -> finalize top-layer heat flux
SoilTemperature                  -> update t_soisno, imelt, h2osoi_liq/ice via phase change
SnowWater                        -> percolate liquid, update aerosols
SnowCompaction                   -> update dz
SnowCapping                      -> enforce capacity
CombineSnowLayers                -> merge thin layers
DivideSnowLayers (or extra)     -> split thick layers
SnowAge_grain                    -> grain radius update (in SnowSnicarMod)
SurfaceAlbedo (next step)        -> SNICAR_RT / SNICAR_AD_RT using updated snw_rds and aerosols
```
