---
name: port-param-file
description: >
  Port a calibrated/site-tuned parameter file across model versions — e.g. a FATES api-31 12-PFT
  NetCDF onto the api-43 14-PFT JSON, or any future version bump. Fires on "convert/port/migrate a
  param file to api-XX", "map parameters to the new version", "build the new-API base file from the
  tuned prior one". The MECHANICS layer; the doctrine (why + which values) lives in the memory it cites.
visibility: public
category: calibration
modes:
  requires_fates: false
  nutrient_pathway: any
  scope: [calibration]
  summary: "Migrate a tuned parameter file across model/API versions — remap PFT identity by functional type, transfer overlapping tuned values. Format-agnostic (.nc/.json)."
---

# port-param-file — migrate a tuned parameter file across model/API versions

The model evolves (FATES api-31 → api-43 → …); each bump changes the parameter **set**, the **format**
(NetCDF/CDL ≤ api-31 → JSON ≥ api-43), and the **PFT roster** (count, order, identity). Carrying a
site's calibration forward is a real migration, not a copy — and it has a silent footgun (PFT identity).

> **Read the doctrine first — do NOT restate it here.** *Why* you port tuned values (not the generic
> upstream default), and the sharp edge (NON-calibrated params used as-is), are in
> [[feedback_port_tuned_base_param_file_across_versions]]. *That PFT ids are not stable across versions
> and must be mapped by functional type* is in [[feedback_verify_pft_identity_across_versions]]. This
> skill is only the mechanical recipe + the tool that executes it.

## When to fire

- Adopting a new model/API version and you need the site's **base parameter file** in the new
  version's format+structure carrying the prior tuned values.
- Any "convert / port / migrate this `.nc` to the api-XX `.json`" / "map these parameters to the new
  version" request.
- NOT for editing single parameters in one file (that's `tools/modify_fates_parameters.py`), and NOT
  for adding a brand-new knob to the model (that's `add-fates-parameter`).

## The recipe (`tools/port_param_file.py` — 3 subcommands)

Backing tool: `tools/port_param_file.py`. Version/format/param-list agnostic — formats auto-detected;
the entity dim (`--pft-dim`, default `fates_pft`) and identity var (`--id-var`, default `fates_pftname`)
are flags, so it retargets to future versions (or another model) without edits. Run under a2mc_env
(`$PY`); for a `.cdl` source, `ncgen -o x.nc x.cdl` first.

**1. Identity FIRST — eyeball the map before porting (the load-bearing step).**
```bash
$PY tools/port_param_file.py identity --source OLD.nc --target NEW_default.json
```
The tool auto-matches PFT slots by `fates_pftname`. **Inspect the report**: any row flagged
`NAME MISMATCH` is a slot that must be resolved by **functional intent**, not name. The canonical trap:
api-31 *repurposed* generic `extratrop_shrub` slots (PFT7/9) for arctic shrubs, but api-43 has
*dedicated* arctic-shrub PFTs (10/11) — so name-matching is wrong and you MUST override:
```bash
--map 7:10,9:11,10:12       # 1-based src:tgt, comma-separated; override wins over name-match
```

**2. Port** (writes NEW-format file: target's structure/defaults + source's tuned values):
```bash
$PY tools/port_param_file.py port --source OLD.nc --target NEW_default.json \
    --out BASE_ported.json --map 7:10,9:11,10:12
# read the report: N scalar + M per-PFT transferred; K target-only KEPT at default; J source-only DROPPED
```
Optional `--params-file names.txt` restricts the transfer to a named set (e.g. only calibrated params);
default transfers **every** overlapping numeric param (the fuller, more faithful base-file port).

**3. Verify** the remapped entity slots equal the source:
```bash
$PY tools/port_param_file.py verify --source OLD.nc --ported BASE_ported.json --map 7:10,9:11,10:12
```

## Footguns (mechanical — the doctrine ones are in the cited memories)

- **Map by functional type, never by index or name.** The `identity` step + explicit `--map` exist
  precisely because name-matching silently lands calibrated arctic-shrub values in the wrong (extratrop)
  slots. Always read the identity report before porting.
- **Param-set drift → runtime abort.** The target build reads its OWN registered param set. A param the
  target expects but the source lacks stays at the **target default** (the tool reports these as
  "target-only KEPT") — fine. But if you hand-build a file missing a param the target registered, the run
  aborts at param read (`check_var … not on dataset` → `ENDRUN`, past the compile gate). Porting *onto the
  target template* (what this tool does) avoids that by construction — don't strip the template down.
- **`entity-dim only on one side` = handle it explicitly.** If a param is scalar in the old version but
  per-PFT in the new (e.g. a knob that was promoted per-PFT — see `add-fates-parameter`/`model-evolution`),
  the tool SKIPS it rather than force a scalar into a per-PFT array. Set it deliberately afterward.
- **Version-INACTIVATED params must be zeroed AFTER porting.** A faithful port transfers the source's
  *active* value for a knob the target version has since **disabled / hard-guarded to 0**, and the new
  build then **aborts at init** on the nonzero value (a runtime abort past the compile gate, like a
  `FatesCheckParams`/`ENDRUN`). Worked case: `fates_cnp_eca_alpha_ptase`/`_lambda_ptase` were active in
  api-31 (0.45/0.95, 1.0) but api-43 ECA guards them to 0 (`EDPftvarcon.F90` `FatesCheckParams`) — the
  #2939 port carried the api-31 values into the arctic PFTs and crashed the ADSP at 56 s until zeroed. After
  porting, **zero every param the target version inactivated** (see [[reference_fates_eca_ptase_disabled_api43]]).
- **Non-calibrated params are the real risk** — this is doctrine; see
  [[feedback_port_tuned_base_param_file_across_versions]] (the arctic graminoid `dbh_repro_threshold`
  0.35-vs-3.0 behavior flip). Diff the ported base vs the generic new default and decide each drift.

## Cross-references

- **Doctrine (why/which values):** [[feedback_port_tuned_base_param_file_across_versions]],
  [[feedback_verify_pft_identity_across_versions]]; `docs/37` §9 (api-43 migration).
- **Backing tool:** `tools/port_param_file.py`; identity report also via `tools/validate_param_list.py`.
- **Adjacent skills:** `add-fates-parameter` (add a new knob — the source of scalar→per-PFT promotions),
  `model-evolution` (source changes), `phase0-design` (uses the ported base file as `A2MC_BASE_PARAM_FILE`).

## Changelog

- 2026-07-14: Added the **version-INACTIVATED-params footgun** — a faithful port carries a source's
  active value for a knob the target has since disabled/guarded-to-0, and the new build aborts at init on
  the nonzero value; zero those after porting. Evidence: the #2939 port's api-31 `eca_alpha/lambda_ptase`
  crashed the api-43 ADSP at 56 s (`EDPftvarcon.F90` `FatesCheckParams`) until zeroed.
- 2026-07-14: Initial version — distilled from the demo R3 En2939 api-31→api-43 migration (session
  `memory/dev_logs/20260714*`), generalizing the one-off `migrate_2939_nc_to_api43_json.py` into the
  version/format-agnostic `tools/port_param_file.py`. Thin by design: defers doctrine to the two cited
  memories, carries only the mechanical recipe + footguns.
