---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# Parameter Management Tools

## Purpose and Scope

This page documents the Python tools shipped with FATES for modifying parameter files at api.43. These tools are used for calibration, sensitivity studies, and model configuration. For the parameter file structure and how parameters are loaded into FATES, see [Parameter System](parameter_system.md).

**Major change at api.43:** the parameter toolset operates on **JSON** files (not NetCDF/CDL). The CLI flags, file formats, and orchestration patterns all changed. Workflows built against the old toolset (`--var/--val/--pft`, `ncgen`/`ncdump`, XML-driven `BatchPatchParams.py`) will not work without modification.

The api.43 toolset supports:

- Modifying individual parameter values (by integer index or PFT name)
- Cloning and reordering PFTs
- Sorting parameter file variables into a standard order
- JSON-driven batch modifications
- One-way migration from CDL to XML+JSON

All tools live in `tools/` and import the shared helper `write_json.py`.

| Tool | Purpose | Source | Lines |
|------|---------|--------|-------|
| `modify_fates_paramfile.py` | Modify or query individual parameter values | `tools/modify_fates_paramfile.py` | 374 |
| `pft_index_swapper.py` | Clone, reorder, or subset PFTs | `tools/pft_index_swapper.py` | 102 |
| `sort_parameters.py` | Sort variables into standard order | `tools/sort_parameters.py` | 157 |
| `batch_patch_params.py` | JSON-driven batch modifications | `tools/batch_patch_params.py` | 83 |
| `cdl_to_xml.py` | Convert legacy CDL to XML+JSON pair | `tools/cdl_to_xml.py` | 483 |
| `write_json.py` | Shared JSON pretty-writer (helper, no CLI) | `tools/write_json.py` | 71 |
| `FindInactive.py` | Inspect history-variable activation flags | `tools/FindInactive.py` | 90 |

Renames vs. earlier API generations:

| Pre-api.43 name | api.43 name |
|------------------|-------------|
| `FatesPFTIndexSwapper.py` | `pft_index_swapper.py` |
| `ncvarsort.py` | `sort_parameters.py` |
| `BatchPatchParams.py` | `batch_patch_params.py` |
| `UpdateParamAPI.py` | (removed) |

The `ncdiff` and `pftdiff` directories are still present but are no longer the primary workflow.

## Workflow Overview

There are two common paths at api.43:

1. **Direct.** Edit `fates_params_default.json` (or a copy) by repeated calls to `modify_fates_paramfile.py`, optionally followed by `sort_parameters.py`.
2. **Batch.** Write a JSON control file describing all desired modifications and invoke `batch_patch_params.py`. Internally it calls `pft_index_swapper.py` and then patches values in place.

Migration from a legacy CDL workflow uses `cdl_to_xml.py` once to produce an XML+JSON pair, after which the api.43 tools take over.

## Tool 1: `modify_fates_paramfile.py`

### Purpose

Primary tool for modifying or querying individual parameter values in a FATES JSON parameter file. Header comment notes "Refactored for json: R. Knox 2025" (`tools/modify_fates_paramfile.py:5`).

### Command-Line Interface

Sourced from `tools/modify_fates_paramfile.py:60-82`:

| Argument | Required | Description |
|----------|----------|-------------|
| `--fin`, `--input` | Yes | Input JSON filename |
| `--fout`, `--output` | Conditionally | Output JSON filename (required unless `--overwrite`) |
| `--param` | Yes (unless `--listparams`) | Name of the parameter to modify or query |
| `--q`, `--queryparam` | No | Report parameter info only, then exit |
| `--indices` | No | Space- or comma-separated list of 1-based indices to change. Special value `all` targets every index. For 2D arrays the array is flattened with PFT as the inner dimension. |
| `--pft-names` | No | Space- or comma-separated list of PFT names (must match entries in `fates_pftname`) |
| `--values` | Yes (unless `--queryparam`/`--listparams`) | List of values to write, one per index |
| `--overwrite` | No | Edit `--fin` in place (cannot be combined with `--fout`) |
| `--silent` | No | Suppress output messages |
| `--listparams` | No | List all parameter names in `--fin` and exit |

`--indices` and `--pft-names` are mutually exclusive (`tools/modify_fates_paramfile.py:149-152`).

### Variable Dimensionality Handling

The script reads `data['parameters'][name]['dims']` to determine shape (`tools/modify_fates_paramfile.py:112-122`):

- **Scalars** (`"dims": ["scalar"]`) accept a single value at index 1.
- **1D arrays** (`["fates_pft"]`, `["fates_NCWD"]`, etc.) are addressed by 1-based indices.
- **2D arrays** (e.g. `["fates_plant_organs", "fates_pft"]`) flatten with the second JSON dim as the inner index. `--indices=all` writes one value to every cell. `--queryparam` prints the index pattern so users can read it off (`tools/modify_fates_paramfile.py:139-146`).

### Type Coercion

`dtype` is read from the parameter object and must be `float`, `integer`, or `string` (`tools/modify_fates_paramfile.py:168-179`). Values are coerced into the correct Python type with `float()`, `int()`, or `str()`. A coercion failure prints "incompatible value" and exits 2.

### History Tracking

The tool appends a record of each modification to `data['attributes']['history']` (`tools/modify_fates_paramfile.py:159-162`). The record contains the timestamp and the full command line.

### Example Usage

```bash
# List every parameter in the file
./modify_fates_paramfile.py --fin fates_params_default.json --listparams

# Query a parameter (print dims, sizes, current values, index pattern)
./modify_fates_paramfile.py --fin fates_params_default.json \
    --param fates_leaf_vcmax25top --queryparam

# Change a PFT-specific parameter for PFT index 7
./modify_fates_paramfile.py --fin fates_params_default.json \
    --fout fates_params_new.json --param fates_mort_bmort \
    --indices 7 --values 0.02

# Same edit, addressed by PFT name instead of index
./modify_fates_paramfile.py --fin fates_params_default.json \
    --fout fates_params_new.json --param fates_mort_bmort \
    --pft-names broadleaf_evergreen_extratrop_shrub --values 0.02

# Modify a global (scalar) parameter
./modify_fates_paramfile.py --fin fates_params_default.json \
    --fout fates_params_new.json --param fates_mort_disturb_frac \
    --indices 1 --values 0.9

# Apply a single value to all PFTs
./modify_fates_paramfile.py --fin fates_params_default.json \
    --fout fates_params_new.json --param fates_leaf_slatop \
    --indices all --values 0.02

# Write distinct values to all 4 organ rows of a PFT-organ array (PFT 1)
# Order: plant_organs={leaf, fineroot, sapwood, structure}
./modify_fates_paramfile.py --fin fates_params_default.json \
    --fout fates_params_new.json --param fates_stoich_nitr \
    --indices 1,15,29,43 --values 0.0335,0.024,1e-08,0.0047
```

(With 14 PFTs, the second-organ row begins at flat index 15, the third at 29, the fourth at 43; verify with `--queryparam`.)

### CLI Flags Removed at api.43

The pre-api.43 flags `--var`/`--variable`, `--val`/`--value`, `--pft`/`--PFT`, `--pftname`/`--PFTname`, `--allPFTs`/`--allpfts`, `--all`, `--changeshape`, `--nohist` are **no longer accepted**. `--indices all` replaces `--all` and `--allPFTs`. There is no per-call switch to suppress history; the history attribute is always updated.

## Tool 2: `pft_index_swapper.py`

### Purpose

Creates a new JSON file by cloning and reordering PFTs from an input file. Used for:

- Reducing the number of PFTs for simplified simulations
- Duplicating PFTs for sensitivity studies
- Reordering PFTs to match a different indexing scheme

### Command-Line Interface

Sourced from `tools/pft_index_swapper.py:37-43`:

| Argument | Required | Description |
|----------|----------|-------------|
| `--fin`, `--input` | Yes | Input JSON filename |
| `--fout`, `--output` | Conditionally | Output JSON filename (required unless `--overwrite`) |
| `--pft-indices` | Yes | Space- or comma-separated 1-based PFT indices to retain (in output order) |
| `--overwrite` | No | Edit `--fin` in place |
| `--silent` | No | Suppress output messages |

### Behavior

The tool walks every parameter in `data['parameters']` and, for any whose `dims` list contains `fates_pft`, repacks the data slice along the PFT axis (`tools/pft_index_swapper.py:65-78`). For 2D parameters PFT is always the second JSON dimension. The dimension `data['dimensions']['fates_pft']` is updated to `len(pft_indices)` (`tools/pft_index_swapper.py:78`).

Other dimensions (`fates_plant_organs`, `fates_hydr_organs`, `fates_litterclass`, `fates_landuseclass`, `fates_NCWD`, `fates_history_*`) are passed through unchanged.

### Example Usage

```bash
# Create a 3-PFT file from PFT 1 cloned three times
./pft_index_swapper.py --fin fates_params_default.json \
    --fout fates_3pft.json --pft-indices 1,1,1

# Reorder PFTs (swap 1 and 2 in the canonical 14-PFT list)
./pft_index_swapper.py --fin fates_params_default.json \
    --fout fates_swapped.json --pft-indices 2,1,3,4,5,6,7,8,9,10,11,12,13,14

# Extract the three Arctic PFTs (e027a40 indices)
./pft_index_swapper.py --fin fates_params_default.json \
    --fout fates_arctic.json --pft-indices 10,11,12
```

(At e027a40, PFT 10 = `broadleaf_evergreen_arctic_shrub`, PFT 11 = `broadleaf_colddecid_arctic_shrub`, PFT 12 = `arctic_c3_grass`.)

## Tool 3: `sort_parameters.py`

### Purpose

Reorganizes parameters in a JSON file into a standard order based on dimensionality. Improves readability and ensures consistent diffs across modifications.

### Command-Line Interface

Sourced from `tools/sort_parameters.py:30-36`:

| Argument | Required | Description |
|----------|----------|-------------|
| `--fin`, `--input` | Yes | Input filename |
| `--fout`, `--output` | Yes | Output filename |
| `--O`, `--overwrite` | No | Automatically overwrite the output file |
| `--debug` | No | Print sort order |
| `--silent` | No | Suppress messages |

### Sort Order

Parameters are grouped by `dims` and emitted in the order defined by `sortorder_list` at `tools/sort_parameters.py:47-72`. The order is: history bin axes, organ-axis arrays, then string-typed name arrays, then PFT-axis arrays (1D and 2D), then litter and landuse arrays, then scalars. Any parameter whose `dims` does not match an entry in `sortorder_list` triggers an error message identifying the unrecognized dim tuple.

## Tool 4: `batch_patch_params.py`

### Purpose

Orchestrates multiple parameter modifications using a **JSON** control file (the XML control file used in earlier API generations is no longer supported). Header notes "Parser code was based off of modify_fates_paramfile.py" (`tools/batch_patch_params.py:5`).

### Command-Line Interface

Sourced from `tools/batch_patch_params.py:32-37`:

| Argument | Required | Description |
|----------|----------|-------------|
| `--fin`, `--input` | Yes | JSON control file path |
| `--silent` | No | Suppress output messages |

### Control File Structure

A worked example ships at `parameter_files/patch_default_bciopt224.json`. The top-level keys are (`tools/batch_patch_params.py:45-76`):

| Key | Required | Description |
|-----|----------|-------------|
| `notes` | No | Free-text description (any string or list-of-strings) |
| `usage` | No | Free-text instructions |
| `base_file` | Yes | Path to the base JSON parameter file |
| `new_file` | Yes | Path to the output JSON file |
| `pft_trim_list` | Yes | List of integer 1-based PFT indices to retain |
| `parameters.pft_parameters` | No | Dict keyed by comma-separated PFT-id strings; values are dicts of `{param_name: [data...]}` |
| `parameters.non_pft_parameters` | No | Dict of `{param_name: [data...]}` for scalars and non-PFT-dimensioned parameters |

### Processing Steps

1. Convert PFT trim list to a comma-separated string and invoke `../tools/pft_index_swapper.py --pft-indices=<list> --fin=<base_file> --fout=<new_file>` (`tools/batch_patch_params.py:49-52`).
2. Load the resulting `<new_file>` and walk `parameters.pft_parameters`. For each comma-separated PFT-id key, write the supplied values into the parameter array at the corresponding (1-based → 0-based) PFT positions. Both 1D and 2D parameters are supported; 2D parameters expect a list-of-lists with the outer index being the non-PFT dim (`tools/batch_patch_params.py:57-72`).
3. Walk `parameters.non_pft_parameters` and overwrite the entire `data` field for each named parameter (`tools/batch_patch_params.py:74-76`).
4. Re-emit the JSON via `write_json.traverse_data` (`tools/batch_patch_params.py:78-79`).

`batch_patch_params.py` does **not** internally sort the output. Run `sort_parameters.py` afterwards if a canonical ordering is desired.

### Example Control-File Excerpt

From `parameter_files/patch_default_bciopt224.json`:

```json
{
    "notes": "...",
    "base_file": "fates_params_default.json",
    "new_file":  "fates_params_opt224.json",
    "pft_trim_list": [1],
    "parameters": {
        "pft_parameters": {
            "1": {
                "fates_pftname": ["generic_tropical_broadleaf_evergreen"],
                "fates_cnp_prescribed_nuptake": [ 0 ],
                "fates_cnp_prescribed_puptake": [ 0 ],
                "fates_stoich_nitr": [ 0.03347526, 0.024, 1e-08, 0.0047 ],
                "fates_stoich_phos": [ 0.002675,   0.0005, 0.00015, 0.00015 ],
                "fates_cnp_turnover_nitr_retrans": [ 0.45, 0.25, 0, 0 ],
                "fates_cnp_turnover_phos_retrans": [ 0.65, 0.25, 0, 0 ],
                ...
            }
        }
    }
}
```

The 4-element lists for `fates_stoich_nitr` etc. correspond to the four `fates_plant_organs` (`leaf, fine root, sapwood, structure`).

### Invocation

From the `parameter_files/` directory (per the `usage` field of the example):

```bash
cd parameter_files
python ../tools/batch_patch_params.py --fin patch_default_bciopt224.json
```

## Tool 5: `cdl_to_xml.py`

### Purpose

Converts a legacy CDL parameter file into an XML metadata file plus a JSON data file. Used once when migrating an old workflow into the api.43 toolset.

### Command-Line Interface

Sourced from `tools/cdl_to_xml.py:121-127`:

| Argument | Required | Description |
|----------|----------|-------------|
| `--cdlfile` | Yes | CDL file path (input) |
| `--outfile` | Yes | Output base name; the script appends `.xml` and `.json` |
| `--verbose` | No | Increase logging |

The XML output captures dimensions and per-parameter metadata (`units`, `long_name`, `dtype`, `dim_names`); the JSON output captures the data arrays. The intent is to ease comparison across API generations and to seed the JSON inputs to the other tools.

## Tool 6: `FindInactive.py`

### Purpose

Inspects `main/FatesHistoryInterfaceMod.F90` to list history variables that are inactive under the requested feature flags (hydraulics, nitrogen, phosphorus, etc.). Not used during parameter editing; included here because it lives in `tools/`.

### Command-Line Interface

Sourced from `tools/FindInactive.py:21-30`:

```bash
./FindInactive.py --f main/FatesHistoryInterfaceMod.F90 \
                  -hydro-active -nitr-active -phos-active
```

## File Format Details

### JSON Parameter File

The canonical schema is documented in [Parameter System](parameter_system.md). Each parameter is a JSON object with `dtype`, `dims`, `long_name`, `units`, `data`. The top-level file has `attributes`, `dimensions`, and `parameters`. A `dims` value of `["scalar"]` indicates a scalar parameter. The pretty-printer `write_json.traverse_data()` (`tools/write_json.py:13`) keeps innermost lists on a single line; this preserves human-readable diffs for typical PFT-axis edits.

### CDL Format (Legacy)

Historical CDL files are preserved under `parameter_files/archive/` (api24 through api41). At api.43 the canonical workflow no longer uses CDL or NetCDF directly; `ncgen` and `ncdump` are not part of the api.43 toolchain.

## Integration With the FATES Parameter System

Parameter files produced by these tools are loaded through the api.43 JSON loader. The flow is one-shot (`main/FatesInterfaceMod.F90:792-893`):

1. `JSONRead(paramfile, pstruct)` parses the entire JSON file into the module-level `pstruct` (`main/JSONParameterUtilsMod.F90:189`).
2. `FatesTransferParameters()` distributes `pstruct` into module storage in five passes (`main/FatesInterfaceMod.F90:2675-2694`): generic, SPITFIRE, PRT, leaf-biophysics, PFT.
3. Each `TransferParams*` routine queries `pstruct%GetParamFromName("fates_<name>")`. If a parameter name is missing or has no data, FATES aborts at read time.

The two-phase Register/Receive flow used in earlier API generations no longer exists; there is no opportunity for a tool to write a parameter that is "registered but not received."

## Best Practices

**Version control.** Track JSON parameter files directly in git. The pretty-printer keeps innermost lists on a single line, so per-PFT edits produce small, reviewable diffs.

**History preservation.** `modify_fates_paramfile.py` always appends to `attributes.history`. Do not edit the `history` field manually unless cleaning up a development branch.

**Constraint checking.** The Python tools do **not** enforce model constraints. FATES performs these checks during initialization (`FatesCheckParameters()` at `main/FatesInterfaceMod.F90:2697`):

- Allometry mode indices must match available functions
- Stoichiometry ratios must be positive
- Mortality rates must be in [0,1] (per year)
- PFT-dimensioned arrays must match the loaded `numpft`
- The carbon-starvation mortality model selector and other namelist-driven options must be in their valid range

**Use `--queryparam` first.** For 2D parameters, the index-pattern output from `modify_fates_paramfile.py --queryparam` is the easiest way to confirm which flat index corresponds to which (organ, PFT) cell before issuing a write.

## Technical Implementation Details

### Type Inference

`modify_fates_paramfile.py` uses the `dtype` field of the parameter object to coerce input strings via `float()`, `int()`, or `str()` (`tools/modify_fates_paramfile.py:168-179`). String parameters are stored verbatim (no quoting transform).

### History Attribute

The `history` attribute on the JSON root (under `attributes`) is appended in place. The string form is `'<timestamp>: modify_fates_paramfile_json.py <argv>'.` (`tools/modify_fates_paramfile.py:57-58`, `:159-162`).

### Output Pretty-Printing

All tools that write JSON use `write_json.traverse_data()` (`tools/write_json.py:13`). This keeps lists on one line (so a 14-element PFT vector renders as `[v1, v2, ..., v14]`), which produces compact, diff-friendly output.

### No Temporary Files for Batch Mode

`batch_patch_params.py` writes directly to `new_file` after invoking `pft_index_swapper.py` to populate it. There is no `mktemp`-based scratch path; the original `base_file` is read once at line 51 and never modified.

## Summary

| Tool | Primary Use Case | Key Features |
|------|------------------|--------------|
| `modify_fates_paramfile.py` | Single-parameter edits and queries | `--indices` or `--pft-names`, scalar/1D/2D support, automatic history |
| `pft_index_swapper.py` | PFT cloning, reordering, subsetting | Repacks every PFT-dimensioned parameter |
| `sort_parameters.py` | Variable organisation | Standardised sort order keyed on `dims` |
| `batch_patch_params.py` | Coordinated multi-parameter edits | JSON-driven, internally invokes `pft_index_swapper.py` |
| `cdl_to_xml.py` | One-time legacy migration | CDL → XML metadata + JSON data |
| `FindInactive.py` | History-variable inspection | Reports inactive vars by feature flag |

All editing tools operate on JSON files, preserve metadata (`units`, `long_name`, `dtype`, dimensions), and update the `history` attribute. For parameter meanings and scientific context, see [Parameter System](parameter_system.md). For initialization and how parameters enter FATES, see [Initialization Modes](initialization.md).
