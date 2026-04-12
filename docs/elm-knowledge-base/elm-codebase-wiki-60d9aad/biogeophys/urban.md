---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Urban Canyon Model

ELM inherits the CLM Urban Canyon model (Oleson et al. 2010a,b; Oleson and Feddema 2020). An urban landunit is decomposed into five facets (columns):

- `icol_roof` - building roof
- `icol_sunwall` - the wall facing the sun
- `icol_shadewall` - the wall in shadow
- `icol_road_perv` - pervious road (plant-bearing)
- `icol_road_imperv` - impervious road (pavement)

Roofs, sunwalls, and shadewalls have a prognostic interior building temperature as the bottom boundary condition (see `biogeophys/soil_temperature.md`). Pervious roads behave more like bare soil with runoff and soil moisture dynamics. This doc covers the urban-specific albedo, radiation, turbulent flux, and parameter routines.

## Scope

- `biogeophys/UrbanParamsType.F90` - urban parameters (facet geometry, albedos, thermal properties, view factors, building temperature bounds) and control flags.
- `biogeophys/UrbanAlbedoMod.F90` - direct/diffuse albedo and absorbed-solar partitioning inside the canyon.
- `biogeophys/UrbanRadiationMod.F90` - longwave radiation bookkeeping inside the canyon.
- `biogeophys/UrbanFluxesMod.F90` - turbulent (sensible/latent/momentum) fluxes for each facet.

## Parameters: `UrbanParamsType`

Two derived types live in this module.

### `urbinp_type`

`biogeophys/UrbanParamsType.F90:27-56` defines `urbinp_type`, which holds the raw gridded surface-dataset inputs before they are averaged to landunit values. Arrays are `(:,:,:)` or `(:,:,:,:)` with dimensions gridcell x topounit x density-class (and radiation band for albedos). Members include `canyon_hwr` (height-to-width ratio), `wtlunit_roof` (roof fraction of the landunit), `wtroad_perv` (pervious fraction of the road), `em_{roof,improad,perroad,wall}` emissivities, direct/diffuse albedos, roof and wall heights, thermal conductivities (`tk_{wall,roof,improad}`) and volumetric heat capacities (`cv_{wall,roof,improad}`), per-layer thickness counts (`nlev_improad`), and `t_building_min` / `t_building_max`.

### `urbanparams_type`

`biogeophys/UrbanParamsType.F90:60-98` defines `urbanparams_type`, the landunit-level operational state used throughout the model:

| Member | Shape | Meaning |
|---|---|---|
| `wind_hgt_canyon` | `(:)` | Height above road at which in-canyon wind is computed (m) |
| `em_roof`, `em_improad`, `em_perroad`, `em_wall` | `(:)` | Facet emissivities |
| `alb_{roof,improad,perroad,wall}_{dir,dif}` | `(:,:)` | Direct/diffuse albedos per radiation band |
| `nlev_improad` | `(:)` | Number of impervious road layers (integer) |
| `tk_{wall,roof,improad}`, `cv_{wall,roof,improad}` | `(:,:)` | Thermal conductivity, heat capacity per layer |
| `thick_wall`, `thick_roof` | `(:)` | Total facet thicknesses (m) |
| `vf_sr`, `vf_wr`, `vf_sw`, `vf_rw`, `vf_ww` | `(:)` | View factors: sky-road, wall-road, sky-wall, road-wall, wall-wall |
| `t_building_max`, `t_building_min` | `(:)` | Internal building temperature bounds (K) |
| `eflx_traffic_factor` | `(:)` | Multiplicative factor for traffic sensible heat (unitless) |

### Control namelist values

`biogeophys/UrbanParamsType.F90:100-111` hosts the HAC (heating/air conditioning) mode string and traffic flag:

- `urban_hac` can be `urban_hac_off` (default, no HAC energy), `urban_hac_on` (HAC energy added to the atmosphere), or `urban_wasteheat_on` (HAC plus waste heat).
- `urban_traffic` (default `.false.`) enables the traffic sensible-heat flux.

`UrbanInput` and `CheckUrban` are the only public entry points of the type module (`biogeophys/UrbanParamsType.F90:23-24`); `UrbanInput` reads the `urbinp_type` from the surface dataset, `CheckUrban` validates the resulting values and aborts if inconsistencies are found.

### Building temperature bounds

The building-temperature bounds `t_building_min`, `t_building_max` define the prescribed internal temperature used as the bottom boundary by the urban soil-temperature solver (`biogeophys/soil_temperature.md` section on `ComputeHeatDiffFluxAndFactor`). Inside `SoilTemperature`, `t_building` is clipped at each step and `cool_on` / `heat_on` flags are set (`biogeophys/SoilTemperatureMod.F90:303-318`). Any heat that the building system removes (cooling) or adds (heating) goes to `eflx_urban_ac`, `eflx_urban_heat`, and `eflx_building_heat`.

## Canyon view factors

The five view factors define how much of each facet's upward-emitted longwave and reflected shortwave reaches the other facets or the sky. Their relationships inside the canyon obey closure identities (see Oleson et al. 2008 CLM-Urban technical note):

```
vf_sr + 2 * vf_wr = 1     (road sees sky and two walls)
vf_sw +   vf_rw + vf_ww = 1 (wall sees sky, road, and opposing wall)
```

The values are allocated in `UrbanParamsType::Init` and then computed from `canyon_hwr` during initialization elsewhere in the model driver.

## Albedo: `UrbanAlbedoMod`

`biogeophys/UrbanAlbedoMod.F90:44` defines `UrbanAlbedo`, the public entry point. The routine is called with the **inactive_and_active** version of the landunit filters so that inactive urban landunits remaining for possible future landuse change are kept up to date (`biogeophys/UrbanAlbedoMod.F90:51-55`).

Private helpers (`biogeophys/UrbanAlbedoMod.F90:34-38`):

- `SnowAlbedo` - snow albedo for roof and both road types.
- `incident_direct` - direct beam solar incident on walls and road in the canyon.
- `incident_diffuse` - diffuse solar incident on walls and road in the canyon.
- `net_solar` - solar radiation absorbed by road and both walls (after multiple reflections).

### Flow

1. Compute cosine of solar zenith angle `coszen` and zenith angle `zen` from `surfalb_vars%coszen_col` (`biogeophys/UrbanAlbedoMod.F90:163-168`).
2. Initialize albedos and fluxes to zero (`biogeophys/UrbanAlbedoMod.F90:170-178`).
3. For each of the two radiation bands (`numrad = 2`: visible and NIR):
   - Compute snow-adjusted facet albedos for roof, impervious road, and pervious road using the standard two-stream snow albedo from `SurfaceAlbedoMod`.
   - Call `incident_direct` and `incident_diffuse` to compute how much of `sdir`, `sdif` reaches each facet after geometry-based canyon-trapping.
   - Call `net_solar` to compute reflected and absorbed fluxes per facet, applying the geometric series of reflections using the view factors.
4. Write `sabs_roof_{dir,dif}_lun`, `sabs_sunwall_{dir,dif}_lun`, `sabs_shadewall_{dir,dif}_lun`, `sabs_improad_{dir,dif}_lun`, `sabs_perroad_{dir,dif}_lun` to `solarabs_vars` for use by `SolarAbsorbedType`.
5. Compute the landunit composite albedos `albgrd`, `albgri`, `albd`, `albi` weighted by the facet area fractions (`wtlunit_roof`, `wtroad_perv`).

The output feeds both the atmosphere (via `SurfaceAlbedoType::albgrd`, `albgri`) and the column thermal solver (via `SolarAbsorbedType::sabs_*_lun`).

## Longwave radiation: `UrbanRadiationMod`

`biogeophys/UrbanRadiationMod.F90:45` defines `UrbanRadiation`. It handles the incoming longwave radiation `forc_lwrad` and the canyon's own longwave exchange. The private helper is `net_longwave` (`biogeophys/UrbanRadiationMod.F90:319`), which computes the net longwave for road and both walls taking into account:

- Multiple reflections inside the canyon (view-factor weighted).
- Emissivities `em_{roof,improad,perroad,wall}`.
- Facet temperatures `t_soisno(c,1)` (skin temperatures) via Stefan-Boltzmann `sb * T^4` (where `sb` comes from `elm_varcon`).
- Sky radiation penetrating through the canyon opening according to `vf_sr`, `vf_sw`.

Outputs include `eflx_lwrad_net_patch` / `eflx_lwrad_out_patch` on `energyflux_vars` and the longwave absorbed per facet.

## Turbulent fluxes: `UrbanFluxesMod`

`biogeophys/UrbanFluxesMod.F90:49` defines `UrbanFluxes`. The header (`biogeophys/UrbanFluxesMod.F90:54-57`) states: "Turbulent and momentum fluxes from urban canyon (consisting of roof, sunwall, shadewall, pervious and impervious road)."

### Strategy

The routine maintains a **canyon air temperature `taf`** and canyon specific humidity `qaf` as landunit-level unknowns. Each facet transfers heat and moisture to the canyon air through a facet-specific conductance `wtus_{roof,road_perv,road_imperv,sunwall,shadewall}` and `wtuq_{...}`; the canyon air transfers to the overlying atmosphere through conductances `wtas`, `wtaq` (`biogeophys/UrbanFluxesMod.F90:126-147`). Closure of the canyon energy balance yields:

```
taf = (wtas*thm + sum_i wtus_i * t_facet_i) / wts_sum
qaf = (wtaq*qm  + sum_i wtuq_i * q_facet_i) / wtq_sum
```

where `wts_sum = wtas + sum_i wtus_i` and `wtq_sum = wtaq + sum_i wtuq_i`. These appear as `taf_numer/denom`, `qaf_numer/denom` in the code (`biogeophys/UrbanFluxesMod.F90:122-125`).

### Monin-Obukhov iteration

The routine iterates on the overlying-canyon resistance `ramu`, `rahu`, `rawu` using `FrictionVelocity` / `MoninObukIni` (`biogeophys/UrbanFluxesMod.F90:67-68`). `implicit_stress` updates are applied via `shr_flux_update_stress` when the corresponding option is enabled.

### In-canyon wind

`canyontop_wind`, `canyon_u_wind`, `canyon_wind` (`biogeophys/UrbanFluxesMod.F90:101-103`) use an exponential decay from roof level to `wind_hgt_canyon`, following the standard canyon-resistance model. The in-canyon resistance `canyon_resistance` converts facet temperature differences into sensible heat fluxes.

### Water budget for pervious road

Pervious roads have a surface water budget similar to soil columns (`pondmx_urban` caps standing water on roofs and impervious roads, defined in `elm_varcon`). Excess water becomes runoff and is added to `qflx_qrgwl` for closure.

### HAC and waste heat

If `urban_hac == urban_hac_on`, the HAC energy required to keep building interior temperature within `[t_building_min, t_building_max]` is added directly to the atmosphere as `eflx_urban_ac` and `eflx_urban_heat`. If `urban_hac == urban_wasteheat_on`, a factor-based waste heat (`ht_wasteheat_factor`, `ac_wasteheat_factor`, capped by `wasteheat_limit`) is added on top (`biogeophys/UrbanFluxesMod.F90:62-63` - imports these constants from `elm_varcon`).

### Traffic

If `urban_traffic == .true.`, `eflx_traffic_factor` multiplies a base traffic sensible heat flux; the result is added to the landunit sensible heat.

## Interfaces with other subsystems

- **Soil temperature** - urban facets use `SoilTemperature` for the thermal column with a fixed `t_building` bottom boundary condition; see `biogeophys/soil_temperature.md` and the dedicated `SetMatrix_SoilUrban*`, `SetRHSVec_SoilUrban*` routines in `SoilTemperatureMod`.
- **Canopy fluxes** - pervious roads optionally invoke the vegetation flux path for the pervious-road grass; see `biogeophys/canopy_fluxes.md` for the non-urban vegetated analog.
- **Surface albedo** - `UrbanAlbedo` is called in place of `SurfaceAlbedo` for urban landunits; the two paths write to the same `SurfaceAlbedoType` fields.
- **SNICAR** - snow on roofs and roads is still aged and its albedo is still adjusted by SNICAR as on non-urban columns; `UrbanAlbedo::SnowAlbedo` reuses the base snow albedo machinery.
- **Balance check** - urban columns have reduced water budget (only `h2ocan + h2osno + ponded water + sub-layer soil water`); `BalanceCheckMod::BeginColWaterBalance` has explicit branches for urban columns (`biogeophys/BalanceCheckMod.F90:106-111`).

## Numerical notes

- Urban landunits have `nlevurb` soil/wall layers (separate parameter from `nlevgrnd`); the wall, roof, and impervious-road columns solve only `1:nlevurb`. See the branches in `SoilThermProp` and `ComputeHeatDiffFluxAndFactor` for urban vs. non-urban.
- `urbanparams_vars` is declared `public, target` in `UrbanParamsType` and exists as a single global instance (`biogeophys/UrbanParamsType.F90:117`). All urban modules import this instance.
- The urban radiation path requires `coszen > 0` to do any work - otherwise it skips to zeroed outputs.
- `urban_hac_off` results in no HAC energy flux but `t_building` is still clipped at `[t_building_min, t_building_max]` - meaning the building acts as an infinite heat reservoir without atmospheric feedback.
