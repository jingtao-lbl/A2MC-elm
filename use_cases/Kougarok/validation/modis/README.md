# MODIS LAI and GPP — Kougarok (secondary / ecosystem-function constraint)

**Added:** June 05, 2026
**Status:** Banked as a DIAGNOSTIC / cross-check only.
**Decision (2026-06-05): MODIS LAI and GPP will NOT be added as calibration
targets**, because they are ecosystem/pixel-level (a single 500 m pixel that mixes
all cover) and not PFT-resolved, whereas A2MC calibrates PFT-level biomass. An
ecosystem-level scalar cannot discriminate a per-PFT tradeoff (e.g. PFT#9 vs PFT#10),
so it cannot break the biomass equifinality at the objective level. No LAI/GPP cost
function exists in `evaluate_case.py` / `targets.yaml`, and none is planned.
**Source:** `<OFFLINE_DATAOBS>/MODIS_LAI&GPP/NGEE-Arctic/`

> `<OFFLINE_DATAOBS>` and `<OFFLINE_WORKSPACE>` are placeholders for machine-specific
> local paths (scrubbed for the public demo); real values are kept in a private dev log.

---

## Why this is here

A2MC currently calibrates against 6 leaf+fineroot biomass targets only. The
offline Round 1 work showed those 6 targets admit an **equifinality / tradeoff**:
two incompatible champion cases (#2678 vs #845) each satisfy a different subset,
and no single Morris case satisfies both PFT#9 and PFT#10 with realistic ecosystem
function (see `../../../../memory/ana_logs/offline_round1_dec2025/20251214a_Case2678vs845_ParameterTradeoff.md`).

MODIS LAI and GPP are the natural **secondary constraint** to break that tie:
ecosystem-level fluxes that the biomass-only objective cannot distinguish. In the
offline analysis the #2678 ("optimized") case over-predicted MODIS LAI/GPP by
2-3x while the #845 case matched MODIS well, i.e. an LAI/GPP term in the objective
would penalize #2678-like solutions and favor #845-like ones. However, see the
Status decision: because MODIS is a single ecosystem-level pixel (not PFT-resolved),
it cannot serve as a per-PFT discriminating target. The data is kept for diagnostic
cross-checks (does a chosen solution have a plausible total-pixel LAI/GPP magnitude
and seasonal cycle, as in the season-cycle figure), not for scoring. Breaking the
PFT#9-vs-PFT#10 equifinality must come from PFT-level information instead.

## Files

| File | Description |
|---|---|
| `Kougarok_MODISGPP_2002to2023.mat` | Original MATLAB file. Vars: `GPP_daily` (8035x4), `GPP_monthly` (264x4) |
| `Kougarok_MODISLAI_2002to2023.mat` | Original MATLAB file. Vars: `LAI_daily` (8035x4), `LAI_monthly` (264x4) |
| `Kougarok_MODISGPP_monthly_2002to2023.csv` | Portable export of `GPP_monthly` |
| `Kougarok_MODISLAI_monthly_2002to2023.csv` | Portable export of `LAI_monthly` |

The CSV exports are provided because A2MC is Python and the rest of this folder is
text-based; the `.mat` files are kept as the faithful source.

## Structure

Both monthly series: 264 rows = 22 years x 12 months (2002-2023). Four columns:

```
year, month, day_mid, value
```

`day_mid` is the mid-month day stamp from the source (16, 14.5, ...). `value` is
the monthly observation:

- **GPP:** g C m-2 day-1. Range [0, 5.49], all 264 months finite.
- **LAI:** m2 m-2 (dimensionless). Range [0, 2.39], 236 of 264 months finite
  (28 winter NaNs = no snow-season retrieval).

## Derivation (verified 2026-06-05)

Both series were produced by the MATLAB scripts in `derivation/` (copied here from
the source dir) from NASA **AppEEARS point-sample** extractions. The point sample is
a SINGLE 500 m MODIS pixel at the Kougarok site:

- Coordinate: **lat 65.1639, lon -164.8262** (AppEEARS Category "Kougarok", ID 2;
  Teller is ID 1 in the same request). MODIS tile h11v02, 500 m pixel line 1160 /
  sample 184. AppEEARS request completed 2025-03-06, date range 2000-2023.

**GPP** (`GenerateGPP_TellerKougarok.m` -> `Kougarok_MODISGPP_2002to2023.mat`):
- Product **MYD17A2HGF.061** (Aqua MODIS GPP, 8-day composite, gap-filled "HGF",
  500 m), layer `Gpp_500m`. Native units kg C m-2 (8-day)-1 (AppEEARS already
  applied the product scale factor).
- Unit conversion in the script: `factor = 1000/8.0` -> g C m-2 day-1.
- Temporal: each 8-day composite value forward-filled across its 8 days, then
  `monthlyavg` (monthly mean of the filled daily series). 2002-2023 -> 264 months.
- No QC-bit screening applied (relies on the gap-filled product; `Psn_QC` is in the
  source CSV but unused).

**LAI** (`GenerateLAI_TellerKougarok.m` -> `Kougarok_MODISLAI_2002to2023.mat`):
- Product **MCD15A3H.061** (combined Terra+Aqua LAI/FPAR, 4-day composite, 500 m),
  layer `Lai_500m`. AppEEARS applied the 0.1 scale factor, so the script uses
  `factor = 1` -> m2 m-2.
- QC: only an extreme-value filter (`Lai > 100 -> NaN`) to drop fill values. The
  per-retrieval `FparLai_QC` bits (cloud, backup-algorithm) are present in the
  source CSV but NOT used to screen, so cloud-affected / backup-algorithm
  retrievals are retained.
- Temporal: 4-day composite forward-filled across its 4 days, then `monthlyavg`.

> Caveats for use as a hard target (not blockers, just be aware):
> 1. **Single 500 m pixel**, not a site-/PFT-resolved footprint. The pixel mixes all
>    cover within that cell, while the FATES targets are PFT-partitioned.
> 2. **No QC-bit screening on LAI** (only value>100). Cloud/backup retrievals are in,
>    which can bias LAI; consider re-filtering on `FparLai_QC` if precision matters.
> 3. **GPP is Aqua-only (MYD17); LAI is Terra+Aqua (MCD15)** — different sampling.
> 4. The "daily" arrays are composite values forward-filled (step functions), not
>    true daily observations; "monthly" is the mean of that.

## Why NOT a calibration target

A2MC scores PFT-level leaf+fineroot biomass. MODIS LAI/GPP here is a single 500 m
pixel that aggregates all PFTs (and bare/other cover) in that cell, so it carries no
PFT attribution. Adding it to the objective would:

- be unable to discriminate which PFT is right/wrong (the exact gap we need to close
  for the PFT#9 vs PFT#10 tradeoff), and
- introduce a footprint/scale mismatch (pixel total vs PFT-partitioned site biomass).

So MODIS is retained only as a **diagnostic cross-check**: after a solution is chosen
on the PFT biomass targets, confirm its total-pixel LAI/GPP magnitude and seasonal
phasing are not wildly off (the role it played in the offline season-cycle figure,
where #2678 over-shot MODIS 2-3x). Breaking the equifinality itself needs PFT-level
data (e.g. PFT-partitioned biomass, cover fraction, or PFT-specific flux), not this
ecosystem-level pixel.

## Offline provenance

The offline analysis that used this data:
`<OFFLINE_WORKSPACE>/Program/OptimizationLeafRoot/compare_gpp_lai_with_modis_combined4320_topcases*.py`
(reads `GPP_monthly` / `LAI_monthly`, column 4 = value; compares ELM-FATES top-50
cases against MODIS 2002-2019).
</content>
