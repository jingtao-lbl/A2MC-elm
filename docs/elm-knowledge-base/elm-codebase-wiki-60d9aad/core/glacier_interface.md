---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Glacier <-> Land Interface

ELM exchanges with the ice-sheet model (CISM/Glissade, referred to as GLC or `glc`)
through three files:

- `main/glc2lndMod.F90` — incoming fields from GLC: ice-sheet fractions, surface
  topography, heat flux under the ice, and coverage masks
- `main/lnd2glcMod.F90` — outgoing fields to GLC: surface temperature, topography,
  and surface mass balance (SMB = `qice`)
- `main/glcDiagnosticsMod.F90` — diagnostic-only fields (Greenland / Antarctic
  area, mask)

The exchange is keyed on the multiple-elevation-class (MEC) glacier landunit
(`istice_mec`), the columns below it (each representing one elevation class, see
`main/column_varcon.F90:76-98`), and the ice sheet coverage mask read from CISM.

## 1. Quick reference

| Direction | Module | Public entry points |
|---|---|---|
| glc → lnd | `glc2lndMod.F90` | `glc2lnd_type%Init`, `update_glc2lnd`, `glc2lnd_vars_update_glc2lnd_acc`, `Restart` |
| lnd → glc | `lnd2glcMod.F90` | `lnd2glc_type%Init`, `update_lnd2glc`, `bareland_normalization` |
| diagnostics | `glcDiagnosticsMod.F90` | `glc_diagnostics_type%Init` |

## 2. `glc2lnd_type` — what the land hears from CISM

Source: `main/glc2lndMod.F90:39-82`.

```fortran
type, public :: glc2lnd_type
   real(r8), pointer :: frac_grc    (:,:) ! fractional ice cover per elevation class [begg:endg, 0:maxpatch_glcmec]
   real(r8), pointer :: topo_grc    (:,:) ! surface elevation per elevation class
   real(r8), pointer :: hflx_grc    (:,:) ! conductive heat flux under the ice
   real(r8), pointer :: icemask_grc (:)   ! "true" ice sheet mask reported by CISM
   real(r8), pointer :: icemask_coupled_fluxes_grc (:)  ! subset of icemask where calving fluxes are actually sent
   logical , pointer :: glc_dyn_runoff_routing_grc (:)  ! pre-cached: use dynamic-glacier runoff routing here
contains
   procedure, public :: Init
   procedure, public :: Restart
   procedure, public :: update_glc2lnd
   ...
end type
```

The `maxpatch_glcmec` parameter sets the number of elevation classes; the class-0
entry in `frac_grc`, `topo_grc`, and `hflx_grc` is reserved for **bare land**
topography (used to set `col_pp%glc_topo` for non-glacier columns within the ice
sheet domain).

### 2.1 `icemask_grc` vs `icemask_coupled_fluxes_grc`

The header comment at `main/glc2lndMod.F90:46-62` is explicit that these two masks
are related but not identical:

- `icemask_grc` is the **true** ice sheet mask from CISM. It says where the coupler
  has any dynamic glacier representation at all.
- `icemask_coupled_fluxes_grc` is a **subset**: it contains only the gridcells whose
  glacier component is actually computing and returning non-zero fluxes (in
  particular, a calving flux) to the coupler.

The distinction matters for water conservation. Wherever
`icemask_coupled_fluxes_grc > 0`, ELM routes runoff using the dynamic-glacier
method; elsewhere, including the "diagnostic-only CISM" configurations where the
ice sheet is live but fluxes are zeroed out, ELM has to use the non-dynamic runoff
form to keep the water budget closed
(`main/glc2lndMod.F90:448-482`, `update_glc2lnd_dyn_runoff_routing`).

### 2.2 Cold start

`InitCold` (`main/glc2lndMod.F90:154-187`) seeds the state before any coupling
has happened. It zeros `frac_grc`, `topo_grc`, and `hflx_grc`, sets `icemask_grc`
equal to the static `ldomain%glcmask` read from the `fglcmask` file (as a rough
pre-coupling guess), and sets `icemask_coupled_fluxes_grc = 0` so that the
uncoupled runoff path is used until CISM posts real data.

### 2.3 `Restart`

Only `icemask_grc` is restartable
(`main/glc2lndMod.F90:191-218`). The other fields are either recomputed on the
first coupler call or kept synchronized via `update_glc2lnd`. `interpinic_flag` is
`skip` so this field is not regridded across resolutions at restart.

## 3. `update_glc2lnd` — the glc → lnd driver

Source: `main/glc2lndMod.F90:222-260`.

The sequence is:

1. **Sanity checks** on both masks (`check_glc2lnd_icemask`,
   `check_glc2lnd_icemask_coupled_fluxes`, `main/glc2lndMod.F90:378-446`). In
   particular, `icemask` must be a subset of `glcmask` because memory sizing is
   driven by `glcmask`, and `icemask_coupled_fluxes` must be a subset of
   `icemask`.
2. **Runoff routing mask** update via `update_glc2lnd_dyn_runoff_routing`
   (`main/glc2lndMod.F90:448-482`) — wherever the coupled-fluxes mask is non-zero,
   flag the gridcell so hydrology routes runoff in "dynamic glacier" mode, else in
   the non-dynamic mode that conserves water in the absence of a calving flux.
3. **Fraction update** via `update_glc2lnd_fracs` (only if `glc_do_dynglacier` is
   true; see `main/glc2lndMod.F90:487-580+`):
   - For each topounit on a gridcell inside the icemask, compute
     `area_ice_mec = sum(frac_grc(g, 1:maxpatch_glcmec))`
     and write it into the landunit weight via `set_landunit_weight(t, istice_mec,
     area_ice_mec)` (`main/glc2lndMod.F90:318-319, 524-525`).
   - For each column on the `istice_mec` landunit, recover the elevation class with
     `col_itype_to_icemec_class(col_pp%itype(c))`
     (`main/column_varcon.F90:101-125`) and set
     `col_pp%wtlunit(c) = frac_grc(g, icemec_class) / lun_pp%wttopounit(l_ice_mec)`.
   - Consistency check: every elevation class whose `frac_grc > 0` must be
     represented by a column; if not, `update_glc2lnd_fracs` aborts
     (`main/glc2lndMod.F90:340-355, 544+`).
4. **Topography update** via `update_glc2lnd_topo` — for every active column, set
   `col_pp%glc_topo(c) = topo_grc(g, n)`, where `n` is the icemec class for
   ice-mec columns and `0` for any other landunit type
   (`main/glc2lndMod.F90:358-374`). This `glc_topo` is exactly the elevation that
   `atm2lndMod` uses to downscale temperature, pressure, humidity, and longwave
   (see `core/atmosphere_interface.md` §2).

There is a secondary entry point `glc2lnd_vars_update_glc2lnd_acc`
(`main/glc2lndMod.F90:263-375`) that is a stand-alone GPU copy of the same logic,
marked `!$acc routine seq`. It is called from `dyn_subgrid/dynSubgridDriverMod.F90`
when OpenACC offload is enabled.

## 4. `lnd2glc_type` — what the land returns to CISM

Source: `main/lnd2glcMod.F90:38-50`.

```fortran
type, public :: lnd2glc_type
   real(r8), pointer :: tsrf_grc (:,:)  ! surface temperature per elevation class [begg:endg, 0:maxpatch_glcmec]
   real(r8), pointer :: topo_grc (:,:)  ! topographic height per elevation class
   real(r8), pointer :: qice_grc (:,:)  ! surface mass balance per elevation class (mm/s)
contains
   procedure, public :: Init
   procedure, public :: update_lnd2glc
end type
```

The class-0 slot again carries the **bare-land** value. Fields are emitted at the
gridcell, elevation-class grid because that is CISM's native binning. History
registrations attach each slot to output fields `TSRF_FORC`, `TOPO_FORC`, and
`QICE_FORC` (`main/lnd2glcMod.F90:118-139`).

## 5. `update_lnd2glc` — the lnd → glc driver

Source: `main/lnd2glcMod.F90:145-229`.

The routine accepts the "do SMB" column filter (`filter_do_smb_c`) and a logical
`init` that is true in the startup phase — when `qflx_glcice` has not yet been
computed by hydrology and must be held at the default value.

Control flow per column in the filter:

1. Look up the landunit type. If it is `istice_mec`, decode the elevation class
   with `col_itype_to_icemec_class` and set `flux_normalization = 1`. If it is
   `istsoil`, use class `n = 0` and
   `flux_normalization = bareland_normalization(c)`. All other landunit types are
   skipped (`main/lnd2glcMod.F90:181-195`).
2. Assert that this `(g, n)` slot has not already been written this step. The
   error message (`main/lnd2glcMod.F90:200-206`) specifically calls out "multiple
   columns in the istsoil landunit" as an unsupported configuration for this
   pathway.
3. Write
   `tsrf_grc(g, n) = col_es%t_soisno(c, 1)` and
   `topo_grc(g, n) = col_pp%glc_topo(c)`.
4. If we are past the init phase, write
   `qice_grc(g, n) = col_wf%qflx_glcice(c) * flux_normalization`
   and warn if `|qice| > 1.0` mm/s.

### 5.1 `bareland_normalization`

Source: `main/lnd2glcMod.F90:231-295`.

CISM sees the gridcell as two classes: glacier and bare. ELM subdivides the
non-glacier part into multiple landunits (natural veg, crop, lake, wetland, urban,
…). Currently only the natural veg landunit carries a nonzero SMB flux, so when
ELM sends up the vegetated-landunit value it must scale it by the fraction of the
"bare land" area that the natural veg landunit occupies — otherwise CISM would
apply the same SMB to the lake portion and water conservation would break.

The formula is:

```
area_glacier = get_landunit_weight(t, istice_mec)
if (area_glacier ≈ 1.0) then
   bareland_normalization = 1.0
else
   bareland_normalization = col_pp%wttopounit(c) / (1.0 - area_glacier)
end if
```

The worked example in the header comment
(`main/lnd2glcMod.F90:247-258`) walks through a 60% `istice_mec` / 30% `istsoil` /
10% `istdlak` gridcell: a 1 m vegetated SMB is rescaled to
`1 * (0.3 / 0.4) = 0.75 m` so that when CISM spreads it uniformly across the 40%
"bare land" area, the total ice grown matches the 0.3 m³/m² per gridcell the land
model originally computed.

The comments at `main/lnd2glcMod.F90:262-264` flag that this code would need
rework if the vegetated landunit ever had multiple columns.

## 6. `glcDiagnosticsMod` — time-invariant GIS/AIS masks

Source: `main/glcDiagnosticsMod.F90`.

A single derived type `glc_diagnostics_type` holds four gridcell arrays:
`gris_mask_grc`, `gris_area_grc`, `aais_mask_grc`, `aais_area_grc`
(`main/glcDiagnosticsMod.F90:17-34`). The history fields are only registered when
`create_glacier_mec_landunit` is true (`main/glcDiagnosticsMod.F90:100-122`).

`calc_timeconst_diagnostics` (`main/glcDiagnosticsMod.F90:127-181`) is called once
at initialization. It uses hard-coded latitude / longitude boxes to tag a gridcell
as Greenland (multiple latitude bands between 58°N and 85°N with longitude wraps
around 285°–355°) or Antarctic (latitude < −60°). Area variables are allocated but
left at their initial value of zero in this module; other diagnostics fill them at
runtime.

## 7. Plugging glacier exchange into the main loop

The coupling routines appear in two places in `dyn_subgrid/dynSubgridDriverMod.F90`:

1. **Inside `dynSubgrid_driver`**, when `create_glacier_mec_landunit` is true, the
   driver calls `glc2lnd_vars%update_glc2lnd(bounds_clump)`
   (`dyn_subgrid/dynSubgridDriverMod.F90:259-261`). This is what pushes updated
   elevation-class fractions into `lun_pp%wttopounit` and
   `col_pp%wtlunit` before the rest of `dyn_subgrid` runs its two-pass update.
2. `icemask_grc` flows from `glc2lnd_vars` into `dynSubgrid_wrapup_weight_changes`
   (`dyn_subgrid/dynSubgridDriverMod.F90:322-357`), where it is forwarded to
   `reweight_wrapup` and ultimately used by `is_active_l` /
   `is_active_c` to keep the glacier-mec landunits alive inside the icemask even
   when they temporarily have zero weight (see
   `main/subgridWeightsMod.F90:355-385` and
   `core/subgrid_utilities.md` §3).

On the reverse direction, `update_lnd2glc` is called once per time step from the
coupling layer with `filter_do_smb_c` giving the set of columns that produce SMB
fluxes in this time step.

## 8. Design rules

- **Do not copy ice-sheet fractions directly into `col_pp%wtlunit` from outside
  `update_glc2lnd_fracs`**. Use `set_landunit_weight` for the landunit level and
  let `update_glc2lnd_fracs` handle the per-column normalization; this keeps the
  invariants in `check_weights` satisfied.
- **Always pass fluxes through `bareland_normalization`** when sending an
  istsoil-landunit flux to the class-0 slot. Without this, CISM will over-count the
  flux whenever non-glacier landunits other than natural veg (lake, wetland, urban)
  exist on the gridcell.
- **Treat `col_pp%glc_topo` as authoritative** for elevation in any downstream
  code (notably `atm2lndMod`'s downscaling). `glc_topo` is the value CISM
  acknowledged, while `ldomain%topo` is the static surface dataset elevation.
- **Conservation is asymmetric across the interface.** The glc → lnd path updates
  weights via `set_landunit_weight` and relies on `reweight_wrapup` to run
  immediately afterwards. The lnd → glc path does not touch weights — it only
  reads column state and rescales bare-land fluxes.
