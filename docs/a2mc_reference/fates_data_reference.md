# FATES Data Reference

**Purpose:** FATES parameter dimensions, PFT names, SZPF mapping, data utilities, and unit conventions.
**Summary:** Read this when writing code that handles FATES NetCDF data.
**Referenced from:** `CLAUDE.md` → "FATES Parameter File Dimensions" section

---

## FATES Parameter File Dimensions (api25.5.0_12pft)

From CDL reference: `Offline/fates_params_api25.5.0_12pft_c230710__parameterdef.cdl`

| Dimension | Size | Description |
|-----------|------|-------------|
| `fates_pft` | 12 | Plant functional types |
| `fates_history_size_bins` | 13 | Size classes for SZPF outputs |
| `fates_plant_organs` | 4 | Organs: leaf, fine root, sapwood, structure |
| `fates_hydr_organs` | 4 | Hydraulic organs |
| `fates_leafage_class` | 1 | Leaf age classes |
| `fates_litterclass` | 6 | Litter classes |
| `fates_NCWD` | 4 | Coarse woody debris classes |
| `fates_hlm_pftno` | 14 | Host land model PFT mapping |

---

## FATES Default PFT Names (12-PFT Configuration)

| PFT# | Array Index | Name |
|------|-------------|------|
| 1 | 0 | broadleaf_evergreen_tropical_tree |
| 2 | 1 | needleleaf_evergreen_extratrop_tree |
| 3 | 2 | needleleaf_colddecid_extratrop_tree |
| 4 | 3 | broadleaf_evergreen_extratrop_tree |
| 5 | 4 | broadleaf_hydrodecid_tropical_tree |
| 6 | 5 | broadleaf_colddecid_extratrop_tree |
| 7 | 6 | broadleaf_evergreen_extratrop_shrub |
| 8 | 7 | broadleaf_hydrodecid_extratrop_shrub |
| 9 | 8 | broadleaf_colddecid_extratrop_shrub |
| 10 | 9 | arctic_c3_grass |
| 11 | 10 | cool_c3_grass |
| 12 | 11 | c4_grass |

---

## Official Parameter Naming Convention

**IMPORTANT:** FATES parameters have official names that do NOT include PFT suffixes.

**Correct format:**
```
fates_cnp_vmax_no3       # Official parameter name
fates_alloc_storage_cushion
fates_cnp_pid_kp
```

**In NetCDF files:** Parameters have dimensions like `(fates_pft,)` with values for each PFT.

**In knowledge graph:** Node IDs use format `parameter:{name}:pft{N}`:
```
parameter:fates_cnp_vmax_no3:pft7    # PFT#7 value
parameter:fates_cnp_vmax_no3:pft9    # PFT#9 value
parameter:fates_cnp_vmax_no3:pft10   # PFT#10 value
```

---

## FATES Output Variable Dimension Levels

| Level | Dimensions | Example Variables | Description |
|-------|------------|-------------------|-------------|
| **Site-level (1D)** | `(time,)` | `FATES_GPP`, `FATES_NPP`, `FATES_LEAFC` | Gridcell-aggregated totals |
| **PFT-level (2D)** | `(fates_levpft, time)` | `FATES_GPP_PF`, `FATES_LEAFC_PF` | By PFT (fates_pft values) |
| **SZPF-level (2D)** | `(fates_levscpf, time)` | `FATES_PUPTAKE_SZPF` | Size × PFT (13 × fates_pft levels) |

---

## SZPF Index Mapping

SZPF (Size-class × PFT) dimension = `fates_history_size_bins × fates_pft` levels.

For 12-PFT configuration: 13 × 12 = 156 levels, arranged as:
```
[PFT1_size1, PFT1_size2, ..., PFT1_size13, PFT2_size1, ..., PFT12_size13]
```

**SZPF index formula:** `start = (pft_id - 1) × 13`, `end = start + 12`

| PFT# | SZPF Indices |
|------|--------------|
| 1 | 0-12 |
| 2 | 13-25 |
| ... | ... |
| 7 | 78-90 |
| 9 | 104-116 |
| 10 | 117-129 |
| 12 | 143-155 |

---

## FATES Data Utilities (`tools/fates_utils.py`)

### Import Functions
```python
from tools import (
    # Index mapping
    get_szpf_range,          # Get SZPF index range for a PFT
    get_pft_index,           # Convert PFT ID to 0-based index
    get_n_szpf_levels,       # Calculate total SZPF levels

    # Data aggregation
    aggregate_szpf_by_pft,   # Sum SZPF data across size classes
    extract_pft_data,        # Extract data for specific PFT

    # File reading
    get_pft_names_from_file, # Read PFT names from .nc or .json

    # NetCDF helpers
    get_variable_info,       # Get variable metadata
    identify_dimension_level,# Identify site/pft/szpf level
    convert_flux_to_annual,  # Unit conversion
)
```

### Usage Examples
```python
from tools import aggregate_szpf_by_pft, get_szpf_range, get_pft_names_from_file

# Get SZPF index range for PFT#10 (works with any fates_pft count)
start, end = get_szpf_range(10, fates_pft=12)  # Returns (117, 129)

# Aggregate SZPF data to PFT level
pft10_puptake = aggregate_szpf_by_pft(szpf_data, pft_id=10, fates_pft=12)

# Read PFT names from parameter file
pft_names = get_pft_names_from_file('fates_params.nc')
# Returns: {1: 'broadleaf_evergreen_tropical_tree', 2: '...', ...}
```

---

## A2MC Internal Naming Conventions

A2MC uses several naming conventions across subsystems. All must align for discovery matching, skip-testing, and cross-phase data flow to work correctly.

### Validation Target Names (Canonical)

Format: `PFT{N}_{variable}` — 1-indexed PFT number, canonical variable name.

```
PFT7_fineroot    PFT7_leaf
PFT9_fineroot    PFT9_leaf
PFT10_fineroot   PFT10_leaf
```

Defined in `use_cases/{site}/validation/` files. Parsed by `tools/evaluate_case.py:_parse_target_specs()` using regex `PFT(\d+)_(\w+)`. The variable part is resolved through `tools/fates_output_variables.py:resolve_target_name()` (e.g., `fineroot` → `froot`).

### Morris Ensemble Parameter Shorthand

Format: `{param_name}_{pft}` — PFT suffix is A2MC shorthand, NOT the official FATES name.

```
vmax_p_10           → fates_cnp_vmax_p (PFT#10)
alloc_storage_cushion_10 → fates_alloc_storage_cushion (PFT#10)
pid_kp              → fates_cnp_pid_kp (all PFTs)
```

Defined in `use_cases/{site}/parameters/FATES_Parameter_List_*.txt`.

### Discovery `affects` Field (Adaptive Memory)

**Canonical format — use official FATES/ELM output variable names:**

| Scope | Format | Examples |
|-------|--------|----------|
| FATES outputs | Official variable name (any dimension level) | `FATES_FROOTC`, `FATES_LEAFC_PF`, `FATES_GPP` |
| FATES SZPF outputs | SZPF-level variable name | `FATES_PUPTAKE_SZPF`, `FATES_FROOTC_SZPF` |
| ELM soil variables | ELM variable name | `LABILEP_vr`, `SECONDP_vr`, `TOTLITP` |
| FATES diagnostics | Diagnostic variable name | `FATES_L2FR`, `FATES_NEFFLUX`, `FATES_NEP` |

**Rules for `affects`:**
1. Use official FATES/ELM variable names — the AI knows each variable's dimensions (site/PFT/SZPF) from the variable registry
2. Do NOT embed PFT IDs into variable names — `FATES_FROOTC` covers all PFTs; use `affects_pfts` to specify which PFTs
3. Any dimension level is acceptable: site-level (`FATES_FROOTC`), PFT-level (`FATES_FROOTC_PF`), or SZPF-level (`FATES_FROOTC_SZPF`)
4. The matching code in `memory/manager.py:_find_relevant_discoveries()` maps validation targets (e.g., `PFT10_fineroot`) to FATES variable names via `tools/fates_output_variables.py`, then does case-insensitive substring matching against `affects`

### Discovery `affects_pfts` Field (Adaptive Memory)

**Optional field** — list of 1-indexed PFT numbers specifying which PFTs are impacted.

```json
"affects_pfts": [10]          // Only PFT#10
"affects_pfts": [7, 9, 10]   // All three Kougarok PFTs
"affects_pfts": []            // All PFTs (same as omitting the field)
```

**Rules for `affects_pfts`:**
1. Uses 1-indexed PFT numbers (matching validation target convention: PFT#7, PFT#9, PFT#10)
2. If absent or empty, the discovery applies to all PFTs
3. Only meaningful for FATES PFT-dimensioned variables — for ELM soil variables like `LABILEP_vr`, `affects_pfts` specifies which PFT targets are ultimately affected by the soil-level mechanism
4. Both the matching code and the AI see this field — `get_relevant_context()` formats it as "**Affected PFTs:** PFT#7, PFT#10" in the AI prompt

**Example entries:**
```json
{
    "affects": ["FATES_FROOTC", "FATES_LEAFC", "FATES_GPP"],
    "affects_pfts": [10],
    "description": "PFT#10 fine root underestimation caused by three bottlenecks..."
}

{
    "affects": ["LABILEP_vr", "SECONDP_vr", "FATES_PUPTAKE_SZPF", "FATES_FROOTC_PF"],
    "affects_pfts": [7, 9, 10],
    "description": "Soil P chemistry bottleneck affecting all PFTs..."
}
```

**Common mistakes to avoid:**
```python
# WRONG — ad-hoc names with PFT# and _biomass suffix
"PFT#10_fineroot_biomass"   # Use: "FATES_FROOTC"

# WRONG — generic concepts that don't match any variable
"drought_response"          # Use: "FATES_MORTALITY_HYDRAULIC_SZPF" or specific variables
"vegetation_mortality"      # Use: "FATES_MORTALITY_CSTARV_SZPF", "FATES_MORTALITY_HYDRAULIC_SZPF"
"L2FR_target"               # Use: "FATES_L2FR"

# CORRECT — official variable names
"FATES_FROOTC"              # Fine root carbon (all PFTs, site-level)
"FATES_LEAFC_PF"            # Leaf carbon (PFT-level)
"LABILEP_vr"                # Labile P (ELM soil variable)
["LABILEP_vr", "SECONDP_vr", "FATES_PUPTAKE_SZPF", "FATES_FROOTC_PF"]  # cross-domain
```

### Parameter Knowledge Keys (Adaptive Memory — `parameters.json`)

**Canonical format — use official FATES parameter names as JSON keys:**

```json
"fates_cnp_pid_kp": {
  "parameter_pft": [10],
  "affects_pfts": [7, 9, 10],
  "insights": ["For PFT#10, low value outperformed high value due to..."],
  "bounds": {"min": 5e-06, "max": 0.001},
  "interactions": ["fates_cnp_vmax_p", "fates_alloc_storage_cushion"],
  "source": "log_file.md"
}
```

**Rules for parameter keys:**
1. Use official FATES parameter names — `fates_cnp_pid_kp`, NOT `pid_kp_10` or `fates_cnp_pid_kp_10`
2. Do NOT embed PFT IDs into key names — PFT specificity belongs in `parameter_pft` and `affects_pfts` fields (same principle as discovery `affects_pfts`)
3. One entry per official parameter name — merge PFT-specific insights into a single entry with natural PFT context in insight text (e.g., "For PFT#10: ...")
4. Non-FATES parameters (`q10_mr`, `r_desorp`, etc.) keep their existing names

**`parameter_pft` field** — list of PFT IDs whose knob was turned in Morris (or `null` for shared parameters):
```json
"parameter_pft": [10]        // PFT#10 was varied
"parameter_pft": [9, 10]     // Both PFT#9 and PFT#10 were varied (merged insights)
"parameter_pft": null         // Shared parameter (e.g., phenology, PID gains)
```

**`affects_pfts` field** — list of PFT IDs that respond to changes (may differ from `parameter_pft` due to cross-PFT competition):
```json
"affects_pfts": [10]          // Only PFT#10 responds
"affects_pfts": [7, 9, 10]    // All three Kougarok PFTs respond
"affects_pfts": [9, 10]       // PFT#9 crown area affects PFT#10 via competition
```

**`bounds` field** — Morris sampling ranges ONLY (not recommendations, case values, or notes):
```python
# CORRECT — Morris sampling range
"bounds": {"min": 5e-06, "max": 0.001}

# WRONG — recommendation (move to insights)
"bounds": {"recommended_reduction": 0.8}

# WRONG — case-specific values (move to insights)
"bounds": {"current": 0.00853, "optimal": 0.02604}
```

**Matching:** `memory/manager.py:get_relevant_context()` strips trailing PFT suffixes (`_7`, `_9`, `_10`) from query names before matching, so Morris shorthand queries like `pid_kp_10` resolve to stored key `fates_cnp_pid_kp`.

**Common mistakes to avoid:**
```python
# WRONG — PFT suffix in key (breaks v2.52 convention)
"fates_cnp_pid_kp__pft10"     # Use: "fates_cnp_pid_kp" with parameter_pft: [10]
"fates_cnp_pid_kp_10"         # Use: "fates_cnp_pid_kp" with parameter_pft: [10]

# WRONG — Morris shorthand as key
"pid_kp_10"                   # Use: "fates_cnp_pid_kp"
"microb_bio_7"                # Use: "fates_cnp_eca_decompmicc"
"alloc_storage_cushion_10"    # Use: "fates_alloc_storage_cushion"

# WRONG — conceptual/abbreviated names
"vmax_p_10"                   # Use: "fates_cnp_vmax_p"
"l2fr_ini_10"                 # Use: "fates_allom_l2fr"

# CORRECT — official names with PFT fields
"fates_cnp_pid_kp":       {"parameter_pft": [10], ...}
"fates_cnp_eca_decompmicc": {"parameter_pft": [7, 9, 10], ...}
"fates_alloc_storage_cushion": {"parameter_pft": [9, 10], ...}
```

### Knowledge Graph Node IDs

Format: `parameter:{name}:pft{N}` or `output:{name}:pft{N}`.

```
parameter:fates_cnp_vmax_no3:pft7
output:FATES_LEAFC_SZPF:pft10
```

Used by `rag/knowledge_graph.py`. Not used in discovery matching.

---

## Unit Conventions

**IMPORTANT:** Always check NetCDF variable metadata for units:
```python
import netCDF4 as nc
ds = nc.Dataset('output.nc')
print(ds.variables['FATES_PUPTAKE_SZPF'].units)      # e.g., "kg m-2 s-1"
print(ds.variables['FATES_PUPTAKE_SZPF'].long_name)  # Variable description
```

**Standard unit format (NOT slashes):**
- `kg m-2 s-1` (kilograms per square meter per second)
- `g C m-2` (grams carbon per square meter)
- `mol m-2 s-1` (moles per square meter per second)

**ELM No-Leap-Year Calendar:**

ELM uses a no-leap-year calendar where every year has exactly 365 days. Each month has fixed day counts:

| Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec | Total |
|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-------|
| 31  | 28  | 31  | 30  | 31  | 30  | 31  | 31  | 30  | 31  | 30  | 31  | 365   |

- **Seconds per year:** `365 * 86400 = 31,536,000` (NOT `365.25 * 86400 = 31,557,600`)
- **Annual flux conversion:** `kg m-2 s-1 → g m-2 yr-1`: multiply by `1000 * 365 * 86400`
- **Monthly flux conversion:** Use per-month day counts, NOT a uniform average (`365/12 ≈ 30.42`)
  ```python
  DAYS_PER_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  ```
