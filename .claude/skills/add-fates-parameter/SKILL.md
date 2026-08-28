---
name: add-fates-parameter
visibility: public
category: model-dev
description: Add a new FATES model parameter (a parameter-file entry read via EDParamsMod) to the ELM-FATES source — wire it through EDParamsMod, `use` it in the consuming module, and add it to the parameter file(s). Use for a model-dev change that needs a new tunable/switchable knob — "add a FATES parameter", "make X an EDParamsMod parameter", "promote this hardcoded constant to a FATES parameter", "switch-gate this model change with a namelist/param knob". This is model-dev on the pinned checkout, so it pairs with the reproducibility contract (experiment branch, default-off, V0-at-equality).
allowed-tools: [Read, Glob, Grep, Write, Edit, Bash]
modes:
  requires_fates: true       # a FATES source change; only meaningful with FATES
  nutrient_pathway: any
  scope: [model-dev]
  summary: "Wire a new FATES EDParamsMod parameter + param-file entry; model-dev on the pinned checkout."
---

# add-fates-parameter — wire a new FATES parameter into EDParamsMod + the parameter file

Model-dev on the model checkout often needs a new tunable/switchable knob (a density cap, a
per-PFT threshold, a mode flag). This is the `EDParamsMod` scalar wiring **plus** the parameter-file step,
with the footguns. It is model-dev, so read the **reproducibility contract first** (the model checkout's
`CLAUDE.md` §1): experiment branch off the pinned
checkout, **push only to your own fork** (never upstream), switch-gated **default-off**, V0-at-equality
before trusting.

## When NOT to use
- A suitable parameter already exists — **verify from source/RAG first** (never assume from the name);
  don't add a duplicate.
- The change is purely structural and never tuned — it can be hardcoded. But any *behavioral* change on
  the pinned checkout should be a **switch-gated param** so a switch-off build reproduces the baseline.

## The two pieces (both required)
A FATES parameter needs **(A)** the `EDParamsMod` code wiring (declare / register / retrieve) **and**
**(B)** the value in the parameter **file**. Missing (B) → the reader **aborts at runtime** (a *registered*
param must be present in every parameter file the run reads). Missing (A) → the value is ignored.

## (A) Recipe — a SCALAR real parameter (template: `ED_val_understorey_death`)

Follow an existing scalar end-to-end; `ED_val_understorey_death` is the clean template. In
`main/EDParamsMod.F90`, `grep -n ED_val_understorey_death EDParamsMod.F90` to find ALL five spots, and add
yours beside each:

1. **Declaration** (real-scalar block):
   `real(r8),protected, public :: ED_val_<name>    ! <what it is, units>`
2. **Parameter-file name string:**
   `character(len=param_string_length),parameter,public :: ED_name_<name> = "fates_<name>"`
3. **Default in `FatesParamsInit`** — a `nan` **sentinel** (catches "missing from file"; NOT the
   operational default): `ED_val_<name> = nan`
4. **Register in `FatesRegisterParams`:**
   ```fortran
   call fates_params%RegisterParameter(name=ED_name_<name>, dimension_shape=dimension_shape_scalar, &
        dimension_names=dim_names_scalar)
   ```
5. **Retrieve in `FatesReceiveParams`:**
   `call fates_params%RetrieveParameter(name=ED_name_<name>, data=ED_val_<name>)`
   (**Integer** param: read into a scratch `tmpreal` then `nint()` — see `max_cohort_per_patch`.)
6. **(Optional) report log** in the report routine: `write(fates_log(),fmt0) 'ED_val_<name> = ',ED_val_<name>`

**Use it** in the consuming module (e.g. `EDPhysiologyMod`, which already imports EDParamsMod):
`use EDParamsMod, only : ED_val_<name>`

Annotate every edit with a `!Jing Tao:` comment ([[feedback_model_code_comment_jing_tao]]).

## (B) Recipe — add the parameter to the FILE (the step that's easy to forget)

The registered param must be a variable in **every** parameter file the run reads. **api-43 (this main
checkout) uses JSON** — `parameter_files/fates_params_default.json`; api-31-0 (the demo branch) used
**NetCDF** (`.nc` / `.cdl`). Check the model version first; the mechanism differs.

**JSON (api-43, primary here).** A scalar is a top-level entry. Edit the JSON with a small Python script
(don't hand-edit — preserve ordering/formatting):
```python
import json
with open(param_file) as f: d = json.load(f)
# follow an existing scalar's shape (e.g. fates_maxcohort) — dimensions, units, long_name, values
d["fates_<name>"] = {"dimensions": ["scalar"], "values": <value>,
                     "units": "<units>", "long_name": "<description>"}
with open(param_file, "w") as f: json.dump(d, f, indent=<match existing>)
```
Verify against an existing scalar's exact schema in `fates_params_default.json` before writing — the JSON
key/shape conventions are the source of truth, not this snippet.

**NetCDF (api-31 / demo legacy).** A scalar is a **0-d `double`** (like `fates_maxcohort`):
```python
import netCDF4 as nc
d = nc.Dataset(param_file, 'a')
if 'fates_<name>' not in d.variables:
    v = d.createVariable('fates_<name>', 'f8')          # 0-d scalar (no dimensions)
    v.units = "<units>"; v.long_name = "<description>"
d.variables['fates_<name>'].assignValue(<value>)         # scalar assignment
d.close()
```

Add it to **all** param files the experiment/production uses (base + per-case). `tools/modify_fates_parameters.py`
*modifies existing* params; a **new** variable needs the `createVariable` / JSON-insert above.

## Default-off / switch-gating (the reproducibility gate)
For a behavioral change on the pinned checkout, set the parameter's **default** (in the base param file) to
a value that makes the change a **no-op** — e.g. a very large value for a cap so `min()` is inert. Then a
switch-off build reproduces the frozen baseline **bit-for-bit** (the V0-at-equality test). Turn it on by
setting a finite value in the experiment param file — **runtime-tunable, no rebuild** to sweep it.

## Gotchas
- **Registered ⇒ must be in every param file** — the #1 footgun (runtime abort at param read:
  `check_var: <name> is not on dataset` → `ENDRUN`, NOT a build error, so the compile gate won't catch it).
  This bites **verification/test param files too**: a V0-off or experiment file built from the *pristine*
  ensemble/default param file silently drops the new param. And when experiment branches **stack**, the
  build needs the *union* of every lineage's registered params — build test files from a **post-change**
  param file (the immediately-prior experiment's), not the pristine one. Worked example: the demo #17
  phen-split V0 run aborted on the missing #16 `fates_max_plant_density` (demo `model_logs/20260710a`).
- **api-43 = JSON**, not `.nc` — the param-file step differs; verify the model version first.
- **A PER-PFT param does NOT go in `EDParamsMod`** — it belongs in **`EDPftvarcon`** (the idiomatic per-PFT
  container). `EDParamsMod` has **no clean array-retrieve** (verified 2026-07-09, the #17 `phen_gddthresh_c`
  read), so a PFT-dimensioned knob wired through `EDParamsMod` is the wrong home. This whole recipe (A) is for
  a **scalar/global** knob; for a per-PFT one, follow the same declare/register/retrieve pattern but in
  `EDPftvarcon` (and in the param file it's a PFT-dimensioned var, `dimension_shape_1d` + a PFT dimension name).
- **Integer vs real** retrieve — real reads `data=` directly; integer reads a `tmpreal` + `nint`.
- **`nan` init is a sentinel**, not the operational default — the operational default lives in the file.
- **Model-dev discipline** — experiment branch off the pinned checkout, **push only to your own fork
  (never upstream)**, `!Jing Tao:` comment on every edit, V0-at-equality before trusting results
  (the model checkout's `CLAUDE.md` §1).

## Cross-references
- **Umbrella workflow:** `model-evolution` — this skill is its "add a tunable/switchable knob" sub-recipe;
  `model-evolution` covers the full source-change discipline (mechanism-gate, scope-from-source, paired verify).
- **Worked example (demo branch / api-31-0):** `fates_max_plant_density` (the Option-C mass-balance recruit
  cap) — FATES commit `408a31ee` on the fork branch `exp/cohort-n-ceiling`; demo `memory/model_logs/20260707c`.
  The EDParamsMod recipe is model-version-general; only the param-file step (JSON vs `.nc`) differs on api-43.
- Reproducibility contract + fork-push rule + model map: the model checkout's `CLAUDE.md` §1 (path recorded in [[feedback_model_source_push_fork_only]]).
- Model-dev logging: the model-evolution folder under the case itself — contract in `use_cases/TEMPLATE/memory/model_evolution/README.md` (moved under the case 2026-08-26; `memory/model_logs/CLAUDE.md` documents the frozen pre-move archive). Source-comment rule: [[feedback_model_code_comment_jing_tao]].

## Changelog

- 2026-07-10: Ported demo `5d587ce` — extended the "registered ⇒ must be in every param file" gotcha with the
  **verification / stacked-branch corollary**: a V0/test param file built from the *pristine* ensemble file
  drops params added by prior changes; stacked experiment branches need the *union* of every lineage's
  registered params; the failure is a runtime `ENDRUN` at param read, not a build error. Driven by the demo
  #17 V0 run aborting on the missing #16 `fates_max_plant_density`.
- 2026-07-09: Gotcha sharpened — a **per-PFT** param goes in **`EDPftvarcon`**, not `EDParamsMod` (no clean
  array-retrieve; verified via the demo #17 `phen_gddthresh_c` read). Cross-linked the `model-evolution`
  umbrella. Ported from demo `7c08096`.
- 2026-07-09: Ported to `main` from demo `a44717d`/`8a8f031` (v3.13), adapted to **api-43**: JSON param
  file is now the primary (B) path (`.nc` demoted to api-31/demo legacy), model-tree paths point at
  `E3SM_FATES_api43`, and the fork-push rule + `!Jing Tao:` comment rule are cross-linked. Worked example
  (`fates_max_plant_density`) kept but labeled as the demo/api-31 origin.
