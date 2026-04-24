---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

# Parameter Management Tools

## Purpose and Scope

This page documents the Python tools shipped with FATES for modifying parameter files. These tools are used for calibration, sensitivity studies, and model configuration. For the parameter file structure and how parameters are loaded into FATES, see [Parameter System](parameter_system.md).

The parameter tools operate on NetCDF parameter files (or their human-readable CDL counterparts) and support:

- Modifying individual parameter values
- Cloning and reordering PFTs
- Batch modifications driven by XML control files
- Sorting parameter file variables into a standard order

All tools live in the FATES source tree under `tools/`. The primary four are:

| Tool | Purpose | Source | Lines |
|------|---------|--------|-------|
| `modify_fates_paramfile.py` | Modify individual parameter values | `tools/modify_fates_paramfile.py` | ~347 |
| `FatesPFTIndexSwapper.py` | Clone / reorder PFTs | `tools/FatesPFTIndexSwapper.py` | ~278 |
| `ncvarsort.py` | Sort variables into standard order | `tools/ncvarsort.py` | ~137 |
| `BatchPatchParams.py` | XML-driven batch modifications | `tools/BatchPatchParams.py` | ~197 |

Additional tools present in `tools/` but not documented here: `FindInactive.py`, `UpdateParamAPI.py`, `ncdiff`, `pftdiff`, `landusedata/`, `luh2/`.

## Workflow Overview

There are two common paths:

1. Direct — build your NetCDF parameter file by making individual calls to `modify_fates_paramfile.py`, optionally sorting with `ncvarsort.py`.
2. Batch — write an XML file describing all desired modifications and invoke `BatchPatchParams.py`, which internally orchestrates `FatesPFTIndexSwapper.py`, `modify_fates_paramfile.py`, and `ncvarsort.py`.

## Tool 1: `modify_fates_paramfile.py`

### Purpose

Primary tool for modifying individual parameter values in a FATES parameter file. Can modify scalars, PFT-specific parameters, and multi-dimensional arrays.

### Command-Line Interface

Sourced from `tools/modify_fates_paramfile.py:36-52`:

| Argument | Required | Description |
|----------|----------|-------------|
| `--var`, `--variable` | Yes | Name of the variable to modify |
| `--val`, `--value` | Yes | New value(s) as a real number or comma-separated list |
| `--fin`, `--input` | Yes | Input NetCDF filename |
| `--fout`, `--output` | Yes | Output NetCDF filename |
| `--pft`, `--PFT` | No | PFT index to modify (1-based) |
| `--pftname`, `--PFTname` | No | PFT name to modify (alternative to `--pft`) |
| `--allPFTs`, `--allpfts` | No | Apply to all PFT indices |
| `--all` | No | Replace all values for the parameter; supersedes other flags |
| `--O`, `--overwrite` | No | Automatically overwrite output file |
| `--silent`, `--s` | No | Suppress output messages |
| `--nohist` | No | Do not record edit in NetCDF `history` attribute |
| `--changeshape` | No | Allow changing variable dimensions (plastic dimensions only) |

### Variable Dimensionality Handling

The script detects variable dimensionality at runtime:

- Scalar variables are replaced directly.
- 1D PFT-indexed arrays update only the specified PFT position (or all positions with `--allPFTs`).
- Multi-dimensional arrays (e.g. `fates_hydro_p50_node(fates_hydr_organs, fates_pft)`) accept comma-separated lists matching the full slice length.

### Example Usage

```bash
# Modify a PFT-specific parameter for PFT index 7
./modify_fates_paramfile.py --fin fates_params_default.nc --fout fates_params_new.nc \
    --var fates_mort_bmort --pft 7 --val 0.02 --O

# Modify a global (non-PFT) parameter
./modify_fates_paramfile.py --fin fates_params_default.nc --fout fates_params_new.nc \
    --var fates_mort_disturb_frac --val 0.9 --O

# Apply a new value to all PFTs
./modify_fates_paramfile.py --fin fates_params_default.nc --fout fates_params_new.nc \
    --var fates_leaf_slatop --allPFTs --val 0.02 --O

# Replace every value of a multi-dimensional array
./modify_fates_paramfile.py --fin fates_params_default.nc --fout fates_params_new.nc \
    --var fates_hydro_p50_node --all --val -2.0,-2.5,-2.5,-3.0 --O
```

### History Tracking

By default, the tool appends a record of each modification to the NetCDF `history` attribute `(tools/modify_fates_paramfile.py:307-315)`. Pass `--nohist` to suppress this.

### Dimension Reshaping

With `--changeshape`, the tool can modify the size of a "plastic" dimension. Increasing the size pads with zeros; decreasing truncates. Only the following dimensions can be safely reshaped without breaking model functionality:

- `fates_history_age_bins`
- `fates_history_size_bins`
- `fates_history_coage_bins`
- `fates_history_height_bins`
- `fates_leafage_class`

All variables sharing the affected dimension are reshaped together `(tools/modify_fates_paramfile.py:156-240)`.

## Tool 2: `FatesPFTIndexSwapper.py`

### Purpose

Creates a new parameter file by cloning and reordering PFTs from an input file. Used for:

- Reducing the number of PFTs for simplified simulations
- Duplicating PFTs for sensitivity studies
- Reordering PFTs to match a different indexing scheme

### Command-Line Interface

Sourced from `tools/FatesPFTIndexSwapper.py:79-133`:

| Argument | Required | Description |
|----------|----------|-------------|
| `--fin` | Yes | Input NetCDF filename |
| `--fout` | Yes | Output NetCDF filename |
| `--pft-indices` | Yes | Comma-delimited list of PFT indices to include (1-based) |
| `--nohist` | No | Do not record operation in file history |
| `-h`, `--help` | No | Print help message |

### Handled Dimensions

Recognized dimensions `(tools/FatesPFTIndexSwapper.py:26-30)`:

| Dimension | Description |
|-----------|-------------|
| `fates_pft` | PFT dimension — resized by the tool |
| `fates_plant_organs` | Allocation organs (4: leaf, fineroot, sapwood, store) |
| `fates_hydr_organs` | Hydraulic organs (4: leaf, stem, transporting root, absorbing root) |
| `fates_litterclass` | Litter class dimension |
| `fates_string_length` | Character string length |

Any variable that has `fates_pft` among its dimensions is repacked to the new order. Other dimensions are copied unchanged.

### Example Usage

```bash
# Create a 3-PFT file from the first PFT of the base file, cloned 3 times
./FatesPFTIndexSwapper.py --fin fates_params_default.nc --fout fates_3pft.nc \
    --pft-indices=1,1,1

# Reorder PFTs (swap PFT 1 and PFT 2)
./FatesPFTIndexSwapper.py --fin fates_params_default.nc --fout fates_swapped.nc \
    --pft-indices=2,1,3,4,5,6,7,8,9,10,11,12

# Extract a subset of PFTs
./FatesPFTIndexSwapper.py --fin fates_params_default.nc --fout fates_arctic.nc \
    --pft-indices=7,9,10
```

### Output Dimensions

The output file preserves all input dimensions except that `fates_pft` is resized to `len(pft-indices)`. All other dimensions remain unchanged.

## Tool 3: `ncvarsort.py`

### Purpose

Reorganizes variables in a NetCDF file into a standardized order. Improves readability and ensures consistency across parameter files, particularly after multiple modifications.

### Command-Line Interface

Sourced from `tools/ncvarsort.py:16-25`:

| Argument | Required | Description |
|----------|----------|-------------|
| `--fin`, `--input` | Yes | Input filename |
| `--fout`, `--output` | Yes | Output filename |
| `--O`, `--overwrite` | No | Automatically overwrite output file |
| `--debug` | No | Print sort order |
| `--silent` | No | Suppress messages |

### Sorting Strategy

Variables are grouped by dimensionality and then sorted alphabetically within each group `(tools/ncvarsort.py:37-71)`. The sort order uses a dictionary `dimtype_sortorder_dict` keyed on the variable's dimensions tuple, with groups for history-bin variables, organ-dimensioned variables, name arrays, PFT-dimensioned variables, litter-class variables, CWD variables, and scalars. Sort keys are lowercased for a case-insensitive sort with case as a tiebreaker.

The tool copies all dimensions, variables, attributes, and global metadata to the output, writing the variables in the computed sort order.

## Tool 4: `BatchPatchParams.py`

### Purpose

Orchestrates multiple parameter modifications using an XML control file. Ideal for:

- Site-specific calibrations
- Creating specialized parameter sets for experiments
- Documenting systematic parameter modifications

Internally, `BatchPatchParams.py` calls `FatesPFTIndexSwapper.py`, `modify_fates_paramfile.py`, and `ncvarsort.py` as building blocks.

### Command-Line Interface

Sourced from `tools/BatchPatchParams.py:88-91`:

| Argument | Required | Description |
|----------|----------|-------------|
| `--f` | Yes | XML control file path |

### XML Control File Structure

The XML file has the following elements `(tools/BatchPatchParams.py:98-172)`:

| Element | Required | Description |
|---------|----------|-------------|
| `<base_file>` | Yes | Path to the base CDL parameter file |
| `<new_file>` | Yes | Path to the output CDL file |
| `<pft_trim_list>` | Yes | Comma-separated PFT indices to retain |
| `<notes>` | No | Free-text description of the parameter set |
| `<parameters>` | Yes | Container for parameter groups |
| `<non_pft_group>` | No | Global (non-PFT-specific) parameters |
| `<pft_group ids="...">` | No | PFT-specific parameters; `ids` attribute lists target PFT indices |

The tool converts the base CDL to a NetCDF binary via `ncgen`, runs `FatesPFTIndexSwapper.py` to prune/reorder PFTs according to `pft_trim_list`, then loops through each `<non_pft_group>` and `<pft_group>` calling `modify_fates_paramfile.py` for each parameter, finally sorting with `ncvarsort.py` and dumping back to CDL.

### Parameter Group Processing

**Non-PFT group**: parameters without a PFT dimension. The tool calls `modify_fates_paramfile.py` with `--all` for each parameter.

**PFT group**: parameters with a PFT dimension. The `ids` attribute specifies target PFT indices. Values can be:

- A single value applied to all specified PFTs
- A comma-separated list matching the number of PFTs
- Multi-valued per PFT for multi-organ parameters such as `fates_stoich_nitr` (4 organ values per PFT). The list length must be evenly divisible by the number of target PFT ids `(tools/BatchPatchParams.py:152-167)`.

### Example XML Files

Two reference XML files ship with FATES at `parameter_files/`:

- `patch_default_e3smtest.xml` — simple parameter patch
- `patch_default_bciopt224.xml` — complex calibration (single PFT extraction, multi-organ stoichiometry, non-PFT parameters, extensive `<notes>`)

## File Format Details

### CDL Format

CDL is the human-readable text representation of NetCDF files. Structure:

- `dimensions:` — define array dimensions
- `variables:` — declare variables with type, dimensions, and attributes
- `data:` — actual parameter values

Conversion:

```bash
ncgen -o fates_params.nc fates_params_default.cdl   # CDL → NetCDF
ncdump fates_params.nc > fates_params.cdl           # NetCDF → CDL
```

### XML Patch Format

XML patch files structure parameter modifications hierarchically (see `parameter_files/patch_default_bciopt224.xml` for a worked example).

## Integration With the FATES Parameter System

Parameter files produced by these tools are loaded through the FATES parameter interface `(main/EDPftvarcon.F90:315-346, main/EDParamsMod.F90)`. The same variables declared in the CDL file are:

1. Registered during `FatesRegisterParams`, `PRTRegisterParams`, etc.
2. Read by the HLM's parameter reader (`param_reader%Read(fates_params)`)
3. Pulled into module storage during `FatesReceiveParams`, `PRTReceiveParams`, etc.

If a tool writes a parameter name that is not declared in the register routines, FATES will abort at read time with a missing-parameter error.

## Best Practices

**Version control.** Track parameter files as CDL, not NetCDF, for human-readable diffs, merge conflict resolution, and clear documentation. Convert to NetCDF with `ncgen` before running simulations.

**History preservation.** Leave the `history` attribute enabled (do not pass `--nohist`) so each modification is recorded in the file itself.

**Constraint checking.** The tools do not enforce model constraints. FATES performs these checks during initialization:

- Allometry mode indices must match available functions
- Stoichiometry ratios must be positive
- Mortality rates must be between 0 and 1 (per year)
- PFT-dimensioned arrays must match the number of PFTs

## Technical Implementation Details

### Data Type Handling

`modify_fates_paramfile.py` handles three input forms `(tools/modify_fates_paramfile.py:66-82)`:

| Input | Interpretation | Example |
|-------|----------------|---------|
| Single number | Float | `50.0` |
| Comma-separated | Array of floats | `1.0,2.0,3.0` |
| String (for `fates_pftname` only) | Character array | `"tropical_broadleaf"` |

### Dimension Metadata Preservation

All tools preserve:

- Variable `units` attribute
- Variable `long_name` attribute
- Global `history` attribute (unless `--nohist`)
- Dimension sizes and names

### Temporary File Management

`BatchPatchParams.py` uses `mktemp` to create temporary files `(tools/BatchPatchParams.py:105-110)`, so the original input file remains intact even if the process fails.

## Summary

| Tool | Primary Use Case | Key Features |
|------|------------------|--------------|
| `modify_fates_paramfile.py` | Single parameter edits | PFT-specific, array support, history tracking |
| `FatesPFTIndexSwapper.py` | PFT cloning/reordering | Preserves multi-dimensional structure |
| `ncvarsort.py` | Variable organization | Standardized sorting order |
| `BatchPatchParams.py` | Complex modifications | XML-driven, orchestrates the other three tools |

All four tools operate on NetCDF files and preserve metadata. For parameter meanings and scientific context, see [Parameter System](parameter_system.md). For initialization and how parameters enter FATES, see [Initialization Modes](initialization.md).
