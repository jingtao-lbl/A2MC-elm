---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Lake Column Model (S-LAKE / CLM4-LISSS)

ELM's lake model is the CLM4-LISSS formulation described in Subin et al. 2012 (JAMES). It is implemented over a `istdlak` landunit with one `istdlak` column per lake gridcell and a single patch per column. This doc covers lake surface fluxes, lake temperature solver, lake hydrology, and the supporting types and constants.

The lake module is essentially unchanged at `d40b8431`. The only material updates are: (a) substituting `use_firn_percolation_and_compaction` for `use_extrasnowlayers` at most use sites in `LakeHydrologyMod`, (b) replacing `lun_pp%itype(l) == istdlak` with `col_pp%is_lake(c)` accessors at several call sites, and (c) the addition of a per-layer snow-melt diagnostic `qflx_snomelt_lyr` in `LakeTemperatureMod`. Algorithmic physics is preserved.

## Scope

- `biogeophys/LakeCon.F90` — tuneable constants and namelist parameters. Unchanged at `d40b8431`.
- `biogeophys/LakeFluxesMod.F90` — surface fluxes (sensible, latent, longwave, friction velocity) over lakes. 18 diff lines (comment text "Monin-Obukhov" → "Obukhov length scale" plus the firn-flag substitution).
- `biogeophys/LakeTemperatureMod.F90` — lake water / snow / soil thermal solver. 15 diff lines, mainly the `qflx_snomelt_lyr` per-layer diagnostic.
- `biogeophys/LakeHydrologyMod.F90` — snow mass balance over lakes, water budget closure. 40 diff lines, mostly `use_firn_percolation_and_compaction` substitutions and `qflx_lnd2ocn` initialization.
- `biogeophys/LakeStateType.F90` — lake state derived type. Unchanged.

## Architecture

A lake column holds, from the top down, a (possibly empty) snowpack, a stack of liquid/ice lake layers (`nlevlak`, typically 10 but lake-depth-dependent), and a sub-lake soil column (`nlevgrnd` layers). The full thermal column is `-nlevsno+1 : nlevlak + nlevgrnd`. Solar radiation penetrates into the lake with a depth-dependent extinction coefficient. Convective mixing, eddy diffusion, and (optionally) enhanced deep-lake mixing are applied after the diffusive step. The lake water mass is kept constant — any water budget imbalance is dumped into `qflx_qrgwl` (see [conservation.md](conservation.md)).

## Constants: `LakeCon`

`biogeophys/LakeCon.F90` hosts all tuneable lake constants, most of which are module variables that may be set in `LakeConInit`. Highlights:

| Name | Value | Meaning |
|---|---|---|
| `tdmax` | `277._r8` | Temperature of maximum water density (K) |
| `emg_lake` | `0.97` | Lake emissivity, frozen and unfrozen |
| `betavis` | `0.0` | Visible-band fraction absorbed in the surface layer |
| `z0frzlake` | `0.001` m | Roughness length over snow-free frozen lakes |
| `za_lake` | `0.6` m | Depth of the surface-light-absorption layer |
| `cur0`, `cus`, `curm` | `0.01`, `0.1`, `0.1` | Charnock-parameter bounds |
| `fcrit` | 22 or 100 | Critical dimensionless fetch (namelist choice) |
| `minz0lake` | 1e-5 or 1e-10 | Minimum roughness length |
| `n2min` | `7.5e-5` s^-2 | Minimum N^2 for enhanced diffusivity |
| `lsadz` | `0.03` m | Extra thickness added to snow layer min/max for lakes |
| `deepmixing_depthcrit` | `25._r8` m | Depth above which to invoke deep-lake extra mixing |
| `deepmixing_mixfact` | `10._r8` | Factor to increase deep-lake mixing by |
| `lakepuddling` | `.false.` | Sensitivity switch; suppress convection over ice |

The `lake_use_old_fcrit_minz0` flag (default `.false.`) switches between the Subin et al. 2011 formulation (`fcrit=22`, `minz0lake=1e-5`) and the Vickers and Mahrt 1997 formulation (`fcrit=100`, `minz0lake=1e-10`).

## Surface fluxes: `LakeFluxesMod`

`biogeophys/LakeFluxesMod.F90:39` defines `LakeFluxes`, the only public entry point. It computes:

- Roughness lengths `z0mg`, `z0hg`, `z0qg` using either a prognostic Charnock formulation over open water (bounds controlled by `cur0`, `cus`, `curm`, `fcrit`) or the fixed `z0frzlake` when the lake is frozen.
- Iteration on Obukhov length scale for stability (loops of up to `itmax_impl = 30` iterations, `LakeFluxesMod.F90:82`) using `FrictionVelocity` / `MoninObukIni` from `FrictionVelocityMod`.
- Sensible and latent heat fluxes via the atmospheric boundary-layer resistances `ram`, `rah`, `raw`.
- Ground heat flux `eflx_soil_grnd` into the water/ice, which becomes the upper boundary condition for `LakeTemperature`.
- Saturation humidity `qsatg`, `qsatgdT` at the ground temperature (`QSat`).
- `emg_lake` is the emissivity used for longwave up.

`LakeFluxes` uses per-iteration implicit stress updates (`shr_flux_update_stress`) when the `implicit_stress` option is enabled. It writes `eflx_soil_grnd`, `eflx_sh_tot`, `eflx_lh_tot`, and the Obukhov length `obu` to `energyflux_vars` / `frictionvel_vars`, and reads atmospheric state from `top_as` / `top_af`.

## Lake thermal solver: `LakeTemperatureMod`

The public entry point is `LakeTemperature` (`biogeophys/LakeTemperatureMod.F90:42-1051`). The header comment describes a 25-45 layer column consisting of up to 5 snow layers, `nlevlak` lake layers, and `nlevgrnd` soil layers, solved as a single tridiagonal system using Crank-Nicholson time stepping.

### Key features

1. Lake water layers can freeze by any fraction and release latent heat; thermal and mechanical properties are adjusted for ice fraction.
2. Convective mixing (though not eddy diffusion) still occurs for frozen lakes.
3. No sunlight is absorbed in the lake if there are snow layers (except through SNICAR to the top soil layer).
4. Light is allowed to reach the top soil layer where it is assumed to be fully absorbed.
5. Lake depth is variable, read from surface data in `initLakeMod`.
6. The extinction coefficient varies with depth.
7. The fraction of shortwave absorbed at the surface is the NIR fraction.
8. Enhanced background diffusion and a deep-lake mixing option are available (Subin 2011).

### Outline

The 11 internal stages:

```
1   Initialization
2   Lake density
3   Diffusivity
4   Heat source term from solar radiation penetrating lake
5   Set thermal props and find initial energy content
6   Set up vectors for tridiagonal matrix solution
7   Solve tridiagonal and back-substitute
8   (Optional) First energy check using temperature change at constant Cv
9   Phase change
9.5 (Optional) Second energy check with latent heat
10  Convective mixing
11  Final energy check; dump imbalance into sensible heat or abort
```

### Constants set at the top

```
cwat      = cpliq * denh2o          ! water heat capacity per unit volume
cice_eff  = cpice * denh2o          ! effective ice heat capacity (use water density)
cfus      = hfus  * denh2o          ! latent heat per unit volume
tkice_eff = tkice * (denice/denh2o) ! effective conductivity
km        = tkwat / cwat            ! molecular diffusivity
```

The `*_eff` quantities preserve consistency because lake layer depth `dz_lake(c,j)` is held constant through freeze/thaw rather than expanding.

### Diffusivity, mixing, solar penetration

The eddy diffusivity `kme(c,j)` combines molecular diffusivity `km`, an eddy term `ke` driven by surface friction velocity `ws_col`, an optional Fang and Stefan 1996 correction (`fangkm`, when `lake_no_ed = .false.`), and a deep-lake multiplier by `mixfact` if the column is deeper than `depthcrit`. The Brunt-Vaisala frequency `n2` is clipped at `n2min`.

Absorbed solar radiation `phi(c,j) = eta * exp(-eta*zin) - eta * exp(-eta*zout)` multiplied by the fraction that reaches depth. The extinction coefficient `eta` is either `etal_col` (from lake surface data) or a depth-dependent formulation. `betavis` (default 0) and the diagnosed NIR fraction determine how much is absorbed in the surface layer `za_lake = 0.6` m. The `phi_soil` term (light through the entire lake into the top soil layer) is added to the soil surface flux.

### Tridiagonal system

The combined column uses arrays `a(-nlevsno+1:nlevlak+nlevgrnd)`, `b`, `c1`, `r`, and is solved with `TridiagonalMod::Tridiagonal`. Interface conductivity `tkix` is computed analogously to `SoilTemperatureMod` (harmonic mean via flux matching). The soil sub-layer uses `SoilThermProp_Lake` (`biogeophys/LakeTemperatureMod.F90:1054-1227`), which parallels `SoilThermProp` but assumes the soil is fully saturated.

### Phase change and convective mixing

`PhaseChange_Lake` (`biogeophys/LakeTemperatureMod.F90:1230-1454`) adjusts `lake_icefrac_col(c,j)`, `h2osoi_liq/ice` (for soil sub-layers), and `lhabs` (total latent heat absorbed per m^2). At `d40b8431`, this routine writes a per-layer snow-melt diagnostic `col_wf%qflx_snomelt_lyr(c,j)` (`LakeTemperatureMod.F90:1294, 1311, 1404`):

```fortran
qflx_snomelt_lyr => col_wf%qflx_snomelt_lyr  ! Output: [real(r8) (:,:)] snow melt per layer (mm H2O /s)
...
qflx_snomelt_lyr(c,:) = 0._r8
...
qflx_snomelt_lyr(c,j) = melt/dtime
```

Convective mixing (stage 10) runs over any unstable layers (`rhow(c,j) > rhow(c,j+1)` when unfrozen, using a density-temperature relation where `rhow` peaks at `tdmax = 277 K`). The column is homogenized over the convectively mixed region using mass-weighted averaging, subject to the `lakepuddling` option that suppresses convection when sufficient ice is present.

### Energy conservation

Three energy-balance checks bracket the solver: at the end of `fin` flux accumulation, after the tridiagonal solve, and after phase change + convection. The final check writes `errsoi(c)` to `col_ef%errsoi` and passes it to `BalanceCheckMod` (see [conservation.md](conservation.md)).

## Lake hydrology: `LakeHydrologyMod`

`LakeHydrology` (`biogeophys/LakeHydrologyMod.F90:49-772`) handles the water mass balance for lake columns. The header comment states the defining constraint: **lake water mass is kept constant**. Any imbalance is closed through `qflx_qrgwl`. The routine:

- Does `SnowWater`, `SnowCompaction`, `CombineSnowLayers`, `DivideSnowLayers` (or `DivideExtraSnowLayers` when `use_extrasnowlayers = .true.`) on any snow overlying the lake.
- Fills the sub-lake soil with water if phase-change has opened pore space; spills excess water back out if the soil exceeds pore capacity.
- Special handling when snow layers are present over an unfrozen lake top: if the top lake layer holds enough latent heat to melt all the snow ice without going sub-freezing, the snow is removed, its water becomes runoff, and the latent heat is subtracted from the lake.
- Adjusts snow-layer minimum and maximum thicknesses by `lsadz = 0.03` m to avoid 1800 s timestep instabilities.

### Firn-flag and ocean-flux substitutions at d40b8431

At `d40b8431`, the lake snow-handling branches at `LakeHydrologyMod.F90:259, 291, 403, 425, 440, 488, 716, 722, 735` use `use_firn_percolation_and_compaction` (instead of `use_extrasnowlayers`). The routine also initializes `qflx_lnd2ocn` to zero for lake columns (`LakeHydrologyMod.F90`, alongside the standard hydrology budget closure).

## Lake state: `lakestate_type`

`biogeophys/LakeStateType.F90:22-`. Members:

| Member | Grain | Meaning |
|---|---|---|
| `lakefetch_col` | column | Lake fetch from surface data (m) |
| `etal_col` | column | Light extinction coefficient (1/m) from surface data |
| `lake_raw_col` | column | Aerodynamic resistance for moisture (s/m) |
| `ks_col` | column | Eddy-diffusivity decay coefficient |
| `ws_col` | column | Surface friction velocity (m/s) |
| `ust_lake_col` | column | Friction velocity carried between timesteps |
| `betaprime_col` | column | Effective beta: `sabg_lyr(p,jtop)` under snow or `beta` otherwise |
| `savedtke1_col` | column | Top-level eddy conductivity from the previous step (W/mK) |
| `lake_icefrac_col` | column x nlevlak | Mass fraction of each lake layer that is frozen |
| `lake_icethick_col` | column | Integrated ice thickness (m) |
| `lakeresist_col` | column | Resistance for CH4 conductance calculation |
| `ram1_lake_patch` | patch | Aerodynamical resistance (s/m) |

## Interfaces with other subsystems

- **Surface albedo** — `lake_icefrac_col` and `lake_icethick_col` are read by `SurfaceAlbedoMod` to determine icy-versus-open-water albedo, and by `SnowSnicarMod` through the shared snow overlay.
- **Canopy / bare ground** — lake columns do not invoke `CanopyFluxesMod` or `BareGroundFluxesMod`; the lake surface flux pathway is independent (see `biogeophys/canopy_fluxes.md` for the non-lake analog).
- **CH4 (`CH4Mod`)** — `LakeTemperature` writes `grnd_ch4_cond_col` and `lakeresist_col` for use by the CH4 diffusion path. The lake sub-soil hosts the CH4 production and oxidation.
- **Snow hydrology** — shared `SnowHydrologyMod` routines are reused (`SnowWater`, `SnowCompaction`, etc.), but snow layer thickness bounds are increased by `lsadz`. Firn-mode physics (when `use_firn_percolation_and_compaction = .true.`) propagates into lake-snow handling.
- **Balance check** — `errsoi` from `LakeTemperature` and the water budget residual from `LakeHydrology` feed `BalanceCheckMod::ColWaterBalanceCheck`. The lake snow-mass-balance branches at `BalanceCheckMod.F90:472-500` use the `col_pp%is_lake(c)` accessor (instead of `lun_pp%itype(l) == istdlak`).

## Numerical notes

- `nlevlak` is model-wide (parameter `elm_varpar`) but lake depth `lakedepth` is variable per column; layer thicknesses `dz_lake(c,:)` / `z_lake(c,:)` are derived in `initLakeMod`.
- The 0.6 m surface-absorption layer (`za_lake`) partly decouples near-surface thermal response from the diffusive solver; `lsadz` prevents top-layer CFL issues at 1800 s.
- `lakepuddling` and `lake_no_ed` are hard-coded off and have not been extensively tested.
- One lake column = one patch is hard-coded (all lake-specific subroutines assert this).
