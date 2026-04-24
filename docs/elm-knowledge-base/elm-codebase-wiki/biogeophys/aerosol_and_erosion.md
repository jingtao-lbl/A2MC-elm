---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Aerosol Deposition, Snow-on Aerosols, and Soil Erosion

This document covers two loosely coupled but physically distinct processes:

- **Aerosol deposition onto snow**: black carbon (BC), organic carbon (OC), and four dust species deposit onto the snowpack, are aged through layers, and darken the snow (SNICAR).
- **Soil erosion**: rainfall-driven and runoff-driven detachment of soil material from hillslopes, with transport-capacity-limited yield to inland waters (Tan et al. 2022).

Both paths operate on the snow/soil column but write to independent state (`aerosol_type` and `sedflux_type`).

## Scope

- `biogeophys/AerosolMod.F90` - `AerosolMasses` (column-integrated masses and per-layer concentrations) and `AerosolFluxes` (deposition from atmosphere).
- `biogeophys/AerosolType.F90` - `aerosol_type` holding per-layer snow aerosol mass and concentration plus landed deposition fluxes.
- `biogeophys/SedYieldMod.F90` - `SoilErosion` subroutine implementing a BQART-inspired rainfall and runoff erosion model.
- `biogeophys/SedFluxType.F90` - `sedflux_type` holding per-column sediment detachment and yield.

## Aerosol on snow

### Aerosol species

ELM tracks seven aerosol species in each snow layer (`aerosol_type`, `biogeophys/AerosolType.F90:21-71`):

| Category | Species | Pointer |
|---|---|---|
| Black carbon | hydrophobic BC | `mss_bcpho_col(:,:)` |
| Black carbon | hydrophilic BC | `mss_bcphi_col(:,:)` |
| Organic carbon | hydrophobic OC | `mss_ocpho_col(:,:)` |
| Organic carbon | hydrophilic OC | `mss_ocphi_col(:,:)` |
| Dust | species 1 | `mss_dst1_col(:,:)` |
| Dust | species 2 | `mss_dst2_col(:,:)` |
| Dust | species 3 | `mss_dst3_col(:,:)` |
| Dust | species 4 | `mss_dst4_col(:,:)` |

Four dust size bins cover the standard SNICAR dust optical ranges. Mass-concentration counterparts (`mss_cnc_*_col`) are `kg/kg` quantities passed directly to `SnowSnicarMod` (see below). The `flx_*_dep_*_col` arrays hold dry, wet, hydrophobic, and hydrophilic deposition fluxes per column `[kg/s]` (`biogeophys/AerosolType.F90:51-71`).

### `AerosolMasses`

`biogeophys/AerosolMod.F90:33` defines `AerosolMasses`. At the top of hydrology Phase 2 (after `BuildSnowFilter` has rebuilt the layer structure), the routine:

1. **Zeros the column-integrated totals** (`mss_bc_col`, `mss_oc_col`, `mss_dst_col`) (`biogeophys/AerosolMod.F90:100-103`).
2. **Snow capping correction**: when `do_capsnow(c)` is true and the top layer mass has been reduced by `qflx_snwcp_ice*dtime`, all aerosol masses in the top layer are scaled by `snowmass / (snowmass + qflx_snwcp_ice*dtime)` to preserve concentration (not mass) - see `biogeophys/AerosolMod.F90:110-135`. This is skipped when `use_extrasnowlayers = .true.`.
3. **Mass concentration computation**: for each snow layer, `mss_cnc_bcphi = mss_bcphi(c,j) / snowmass`, with `snowmass = h2osoi_ice + h2osoi_liq`. Hydrophobic and hydrophilic species are computed separately, as are each dust bin.
4. **Column and top-layer aggregation**: `mss_bc_col`, `mss_oc_col`, `mss_dst_col` get column sums; `mss_bc_top`, `mss_oc_top`, `mss_dst_top` get top-layer masses; `h2osno_top` tracks top-layer SWE for diagnostics.

### `AerosolFluxes`

`biogeophys/AerosolMod.F90:228-379` reads `atm2lnd_vars%forc_aer_grc(:,:)` - a 14-component array holding deposition fluxes from the atmosphere model (or prescribed file) and maps it into the `flx_*_dep_*_col` arrays. Two branches exist:

- **Bulk deposition** (default, not `MODAL_AER`): the first three indices are BC (hydrophilic dry, hydrophobic dry, wet), the next three are OC, and `forc_aer(g,7:14)` are the eight dust fluxes (wet/dry x 4 species) (`biogeophys/AerosolMod.F90:327-354`).
- **Modal deposition** (`#ifdef MODAL_AER`): "phi" BC/OC flavors represent within-hydrometeor (cloud-borne) aerosol and "pho" flavors are interstitial, consistent with the MAM modal aerosol scheme in EAM (`biogeophys/AerosolMod.F90:285-320`).

After building the column deposition fluxes, the routine deposits into the top snow layer:
```
mss_bcphi(c, snl(c)+1) += flx_bc_dep_phi(c) * dtime
mss_bcpho(c, snl(c)+1) += flx_bc_dep_pho(c) * dtime
mss_ocphi(c, snl(c)+1) += flx_oc_dep_phi(c) * dtime
mss_ocpho(c, snl(c)+1) += flx_oc_dep_pho(c) * dtime
mss_dst{1..4}(c, snl(c)+1) += (dry + wet)*dtime
```
(`biogeophys/AerosolMod.F90:364-375`). The comment at `biogeophys/AerosolMod.F90:357-362` notes that the deposition step comes *after* the per-layer aerosol advection in `SnowHydrologyMod` so that newly deposited aerosols appear in the top layer before the next radiative call.

### Aging and advection

Aerosol masses are advected between snow layers by `SnowHydrologyMod::SnowWater` as part of the liquid water fluxes, with species-specific effective solubilities. Hydrophilic flavors are largely washed out with percolating water; hydrophobic flavors age to hydrophilic over a prescribed timescale. ELM inherits the CLM4/SNICAR aging formulation documented in Flanner et al. 2007.

### Coupling to SNICAR and snow albedo

`SnowSnicarMod` reads `mss_cnc_*` arrays each timestep to compute snow-layer-resolved specific absorption that darkens the visible albedo. The resulting `albgrd`, `albgri` are used by `SurfaceAlbedoMod` and `UrbanAlbedoMod`. Dust optics uses the four prescribed size bins consistent with the Fialho et al. 2006 / Balkanski et al. 2007 optical properties.

`snw_rds_min = 54.526_r8` (`biogeophys/AerosolMod.F90:27`) is the minimum allowed snow effective radius (also the "fresh snow" value) used by the grain-growth solver in `SnowSnicarMod`.

## Soil erosion: `SedYieldMod`

`biogeophys/SedYieldMod.F90` implements the Tan et al. 2022 erosion model cited in the module header (`biogeophys/SedYieldMod.F90:5-7`). The single public routine is `SoilErosion` (`biogeophys/SedYieldMod.F90:53`):

```
subroutine SoilErosion(bounds, num_soilc, filter_soilc,
     canopystate_vars, cnstate_vars, soilstate_vars, sedflux_vars)
```

### Inputs

From `soilstate_vars` (tuning and soil properties):
- `bd_col` - bulk density (kg/m^3)
- `cellsand_col`, `cellclay_col`, `cellgrvl_col` - soil texture and gravel percentage (by mass)
- `tillage_col` - conserved tillage fraction
- `litho_col` - lithology erodibility index

From `col_pp`:
- `hslp_p10(c,:)` - hillslope gradient percentiles (`nlevslp` bins)

From the topounit / gridcell atmospheric state (`top_as`, `top_af`):
- `forc_rain(t)` - rain rate (mm/s)
- `forc_t(t)` - atmospheric temperature (K), used to gate rainfall erosion (must be > 273.15 K)

From water fluxes (`col_wf`, `veg_wf`):
- `qflx_surf(c)` - surface runoff (mm/s)
- `qflx_qrgwl(c)` - glacier runoff (mm/s)
- `qflx_dirct_rain(p)`, `qflx_leafdrip(p)`, `qflx_real_irrig_patch(p)` - throughfall, leaf drip, irrigation

From canopy state (`canopystate_vars`):
- `tlai_patch` - total LAI
- `htop_patch`, `hbot_patch` - canopy top/bottom height

From the soil BGC cascade (`decomp_cpools_vr`):
- Litter C in the top soil layer, used to compute residue cover (`Brsd`).

### Mechanics

The detachment model has two independent components:

1. **Rainfall-driven detachment** (`Es_P`, `biogeophys/SedYieldMod.F90:200-234`):
   - Throughfall kinetic energy: `KE_DT = Ptot * fungrvl * max(8.95 + 8.44*log10(Ie), 0)`, with `Ie = 3.6e3 * (rain + irrigation)` the precipitation intensity (mm/hr), `Ptot` the throughfall amount (mm), and `fungrvl = 1 - 0.01*fgrvl` the gravel cover fraction. See `biogeophys/SedYieldMod.F90:208-209`.
   - Leaf-drip kinetic energy: `KE_LD = max(15.8*sqrt(cheight) - 5.87, 0) * fungrvl * Dl`, with `Dl` the leaf drip amount (mm) and `cheight` the canopy centroid height (`biogeophys/SedYieldMod.F90:213`).
   - Ground cover attenuation: `fgndcov = exp(-gcbc_p(pft) * PCT_gnd - gcbr_p(pft) * Broot)`, where `PCT_gnd = 100 * max(residue_cover, 1 - exp(-LAI))` and `Broot` is the top-layer root biomass density (`biogeophys/SedYieldMod.F90:219-220`).
   - Assembly: `Es_P += pfactor(c) * ftillage * flitho * fgndcov * wtcol(p) * K * (KE_DT + KE_LD)`.
   - `K` is soil detachability (`SoilDetachability(stxt)`) and `ftillage = 2.7 - 1.7*tillage`.
   - Snow cover scales the final result by `(1 - frac_sno(c))` (`biogeophys/SedYieldMod.F90:234`).

2. **Runoff-driven detachment** (`Es_Q`, `biogeophys/SedYieldMod.F90:236-291`):
   - Runoff power: `Qss = (1 - 0.7846 * frac_sno) * Qs`, `Qs = 8.64e4 * qflx_surf` (mm/day).
   - Slope factor: average `sin(atan(hslp_p10))` over hillslope percentile bins (`biogeophys/SedYieldMod.F90:245-252`).
   - Cohesion via `COH = SoilCohesion(stxt)`.
   - Manning roughness: `nh = 0.03 + 0.05 * max(Crsd, Clai)`, and `fsr = wtcol * (0.03/nh)^0.6`.
   - Assembly: `Es_Q += 19.1 * qfactor(c) * 2/COH * flitho * fslp * ftillage * fgndcov * Qss^1.5 * wtcol(p)` (for non-C4-grass, grass has a glacier factor applied instead).

3. **Transport capacity**: `Tc = 19.1 * tfactor(c) * fslp_tc * fsr * ftillage_tc * flitho * fglacier * Qs^2` (`biogeophys/SedYieldMod.F90:286-288`). The yield to inland waters is capped by transport capacity:
   ```
   flx_sed_yld(c) = min(Es_P + Es_Q, Tc)
   ```
   (`biogeophys/SedYieldMod.F90:298`).

### Glacier scaling

If there is an active `istice` landunit in the same topounit and its meltwater runoff is finite, `fglacier = 1 + 9 * lun_pp%wttopounit(lt)`, implementing a runoff-power amplification for glacier-fed streams (`biogeophys/SedYieldMod.F90:164-180`).

### Output: `sedflux_type`

Defined in `biogeophys/SedFluxType.F90:21-43`:

| Member | Meaning |
|---|---|
| `pfactor_col` | Rainfall-driven erosion scaling factor (tunable, column-constant) |
| `qfactor_col` | Runoff-driven erosion scaling factor |
| `tfactor_col` | Transport capacity scaling factor |
| `sed_p_ero_col` | Sediment detachment driven by rainfall (kg/m2/s) |
| `sed_q_ero_col` | Sediment detachment driven by runoff (kg/m2/s) |
| `sed_ero_col` | Total detachment (kg/m2/s) |
| `sed_crop_ero_col` | Cropland-only detachment (kg/m2/s) |
| `sed_yld_col` | Sediment yield to inland waters (kg/m2/s), capped by `Tc` |

The first three scaling factors are read at initialization (via `InitCold`) from the surface dataset or a runtime parameter file and held fixed thereafter.

## Interfaces with other subsystems

- **SNICAR (snow albedo)** - `mss_cnc_*_col` arrays are the primary coupling point; SNICAR reads them and produces a multi-layer snow albedo that enters `SurfaceAlbedoType` and thus `CanopyFluxesMod` and `BareGroundFluxesMod`. See `biogeophys/canopy_fluxes.md` for how the surface albedo feeds back into vegetation energy balance.
- **Snow hydrology** - `SnowWater`, `SnowCompaction`, `CombineSnowLayers`, and `DivideSnowLayers` advect aerosol mass alongside layer water. `AerosolMasses` must run after these layer-manipulation routines.
- **Soil biogeochemistry** - `SedYieldMod` uses `decomp_cpools_vr` (litter C in the top soil layer) to compute residue cover, and the sediment yield is consumed by the river routing subsystem (MOSART) and the land-ocean sediment-POC/PON/POP flux accounting (not covered in the biogeophys docs).
- **Atmospheric coupling** - `atm2lnd_vars%forc_aer_grc` delivers the 14 aerosol fluxes (or MAM modal fluxes under `#ifdef MODAL_AER`).
- **FAN ammonia volatilization** - `SnowHydrologyMod` also moves FAN chemicals; the aerosol path is independent but shares the layer-advection infrastructure.

## Notes

- `forc_aer_grc(g,1:14)` is the contract between ELM and the atmospheric model/forcing files; its index layout depends on `MODAL_AER`. Users switching between bulk and modal forcing must verify the forcing dataset matches the compiled mode.
- `snw_rds_min = 54.526` microns is the SNICAR "fresh snow" effective radius; it is also used as a clipping value in the snow grain growth solver.
- The erosion model assumes `forc_t(t) > T0 = SHR_CONST_TKFRZ` before any rainfall detachment (`biogeophys/SedYieldMod.F90:202`) - i.e., rainfall detachment is suppressed when the surface is frozen.
- `SoilDetachability` and `SoilCohesion` are texture-based lookup functions (sand/silt/clay/gravel proportions) defined further down in `SedYieldMod.F90` - they are private helpers.
- The sediment model treats glacier columns only via the topounit scaling `fglacier`; glaciers themselves are not eroded.
