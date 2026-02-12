"""
FATES Output Variable Registry - Single Source of Truth

Centralized registry for FATES output variable metadata:
- Variable families (site, PFT, SZPF levels for each quantity)
- Target name aliases (e.g., 'fineroot' -> 'froot')
- Unit conversion factors for validation
- Lookup functions for consumers

All scripts that need to map target names to NetCDF variables,
compute SZPF aggregation, or apply unit factors should import
from this module instead of defining local mappings.

Author: Jing Tao with Claude
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


# =============================================================================
# Data Structures
# =============================================================================

class DimensionLevel(Enum):
    """FATES output variable dimension levels."""
    SITE = 'site'               # (time, lndgrid)
    PFT = 'pft'                 # (time, fates_levpft, lndgrid) - 12 levels
    SZPF = 'szpf'               # (time, fates_levscpf, lndgrid) - 156 levels
    SIZE = 'size'               # (time, fates_levscls, lndgrid) - 13 levels
    SOIL = 'soil'               # (time, levsoi, lndgrid) - 10 levels
    AGE = 'age'                 # (time, fates_levage, lndgrid) - 7 levels
    ELEMENT = 'element'         # (time, fates_levelem, lndgrid) - 3 levels
    ELEMENT_PFT = 'element_pft' # (time, fates_levelpft, lndgrid) - 36 levels
    CANOPY = 'canopy'           # (time, fates_levcan, lndgrid) - 2 levels


@dataclass(frozen=True)
class VariableFamily:
    """A group of related FATES variables at different dimension levels.

    Each family represents a single physical quantity (e.g., leaf carbon)
    available at multiple aggregation levels in the FATES output.
    """
    canonical_name: str         # e.g., 'leaf', 'froot', 'gpp'
    long_name: str              # e.g., 'Leaf carbon biomass'
    category: str               # 'biomass', 'flux', 'allocation', 'nutrient'
    units: str                  # NetCDF units, e.g., 'kg m-2'
    site_var: Optional[str]     # e.g., 'FATES_LEAFC'
    pft_var: Optional[str]      # e.g., 'FATES_LEAFC_PF'
    szpf_var: Optional[str]     # e.g., 'FATES_LEAFC_SZPF'
    validation_factor: float = 1.0  # multiply NetCDF value to match target units


# =============================================================================
# Registry
# =============================================================================

VARIABLE_FAMILIES: Dict[str, VariableFamily] = {
    'leaf': VariableFamily(
        canonical_name='leaf',
        long_name='Leaf carbon biomass',
        category='biomass',
        units='kg C m-2',
        site_var='FATES_LEAFC',
        pft_var='FATES_LEAFC_PF',
        szpf_var='FATES_LEAFC_SZPF',
        validation_factor=1000,  # kg -> g
    ),
    'froot': VariableFamily(
        canonical_name='froot',
        long_name='Fine root carbon biomass',
        category='biomass',
        units='kg C m-2',
        site_var='FATES_FROOTC',
        pft_var=None,
        szpf_var='FATES_FROOTC_SZPF',
        validation_factor=1000,
    ),
    'abg': VariableFamily(
        canonical_name='abg',
        long_name='Aboveground vegetation carbon',
        category='biomass',
        units='kg C m-2',
        site_var='FATES_VEGC_ABOVEGROUND',
        pft_var=None,
        szpf_var='FATES_VEGC_ABOVEGROUND_SZPF',
        validation_factor=1000,
    ),
    'vegc': VariableFamily(
        canonical_name='vegc',
        long_name='Total vegetation carbon',
        category='biomass',
        units='kg C m-2',
        site_var='FATES_VEGC',
        pft_var='FATES_VEGC_PF',
        szpf_var='FATES_VEGC_SZPF',
        validation_factor=1000,
    ),
    'gpp': VariableFamily(
        canonical_name='gpp',
        long_name='Gross primary production',
        category='flux',
        units='kg C m-2 s-1',
        site_var='FATES_GPP',
        pft_var='FATES_GPP_PF',
        szpf_var=None,
        validation_factor=1.0,
    ),
    'npp': VariableFamily(
        canonical_name='npp',
        long_name='Net primary production',
        category='flux',
        units='kg C m-2 s-1',
        site_var='FATES_NPP',
        pft_var='FATES_NPP_PF',
        szpf_var='FATES_NPP_SZPF',
        validation_factor=1.0,
    ),
    'lai': VariableFamily(
        canonical_name='lai',
        long_name='Leaf area index',
        category='biomass',
        units='m2 m-2',
        site_var='FATES_LAI',
        pft_var=None,
        szpf_var=None,
        validation_factor=1.0,
    ),
    'storec': VariableFamily(
        canonical_name='storec',
        long_name='Storage carbon',
        category='biomass',
        units='kg C m-2',
        site_var='FATES_STOREC',
        pft_var='FATES_STOREC_PF',
        szpf_var=None,
        validation_factor=1000,
    ),
    'puptake': VariableFamily(
        canonical_name='puptake',
        long_name='Phosphorus uptake',
        category='nutrient',
        units='kg P m-2 s-1',
        site_var='FATES_PUPTAKE',
        pft_var=None,
        szpf_var='FATES_PUPTAKE_SZPF',
        validation_factor=1.0,
    ),
    'nh4uptake': VariableFamily(
        canonical_name='nh4uptake',
        long_name='NH4 uptake',
        category='nutrient',
        units='kg N m-2 s-1',
        site_var='FATES_NH4UPTAKE',
        pft_var=None,
        szpf_var='FATES_NH4UPTAKE_SZPF',
        validation_factor=1.0,
    ),
    'no3uptake': VariableFamily(
        canonical_name='no3uptake',
        long_name='NO3 uptake',
        category='nutrient',
        units='kg N m-2 s-1',
        site_var='FATES_NO3UPTAKE',
        pft_var=None,
        szpf_var='FATES_NO3UPTAKE_SZPF',
        validation_factor=1.0,
    ),
    'autoresp': VariableFamily(
        canonical_name='autoresp',
        long_name='Autotrophic respiration',
        category='flux',
        units='kg C m-2 s-1',
        site_var='FATES_AUTORESP',
        pft_var=None,
        szpf_var=None,
        validation_factor=1.0,
    ),
}


# Aliases: common alternate names -> canonical name
TARGET_ALIASES: Dict[str, str] = {
    'fineroot': 'froot',
    'fine_root': 'froot',
    'leaf_biomass': 'leaf',
    'fineroot_biomass': 'froot',
    'froot_biomass': 'froot',
    'abg_biomass': 'abg',
    'total_vegc': 'vegc',
}


# =============================================================================
# Public Functions
# =============================================================================

def resolve_target_name(name: str) -> str:
    """Resolve a target name to its canonical form.

    Examples:
        >>> resolve_target_name('fineroot')
        'froot'
        >>> resolve_target_name('leaf')
        'leaf'
        >>> resolve_target_name('LEAF')
        'leaf'
    """
    lower = name.lower()
    resolved = TARGET_ALIASES.get(lower, lower)
    return resolved


def get_variable_family(target_name: str) -> VariableFamily:
    """Get the variable family for a target name.

    Args:
        target_name: Target name (canonical or alias)

    Returns:
        VariableFamily for the resolved target

    Raises:
        KeyError: If target name not found in registry
    """
    canonical = resolve_target_name(target_name)
    if canonical not in VARIABLE_FAMILIES:
        raise KeyError(
            f"Unknown target '{target_name}' (resolved to '{canonical}'). "
            f"Available: {list(VARIABLE_FAMILIES.keys())}"
        )
    return VARIABLE_FAMILIES[canonical]


def get_fates_variable(target_name: str, level: str = 'szpf') -> Optional[str]:
    """Get the FATES NetCDF variable name for a target at a given level.

    Args:
        target_name: Target name (canonical or alias)
        level: Dimension level ('site', 'pft', 'szpf')

    Returns:
        Variable name string, or None if not available at that level
    """
    family = get_variable_family(target_name)
    level_map = {
        'site': family.site_var,
        'pft': family.pft_var,
        'szpf': family.szpf_var,
    }
    return level_map.get(level)


def get_validation_factor(target_name: str) -> float:
    """Get the unit conversion factor for validation comparison.

    Args:
        target_name: Target name (canonical or alias)

    Returns:
        Multiplication factor (e.g., 1000 for kg->g)
    """
    return get_variable_family(target_name).validation_factor


def get_preferred_level(target_name: str) -> str:
    """Get the most detailed available dimension level for a target.

    Preference order: szpf > pft > site

    Args:
        target_name: Target name (canonical or alias)

    Returns:
        Level string: 'szpf', 'pft', or 'site'
    """
    family = get_variable_family(target_name)
    if family.szpf_var:
        return 'szpf'
    if family.pft_var:
        return 'pft'
    return 'site'


def list_families() -> List[str]:
    """List all canonical family names in the registry."""
    return list(VARIABLE_FAMILIES.keys())


# =============================================================================
# Backward-Compatible Constants (auto-generated from registry)
# =============================================================================

# Maps target name -> best available variable (szpf > pft > site)
TARGET_VAR_MAPPING: Dict[str, str] = {}
for _name, _fam in VARIABLE_FAMILIES.items():
    _var = _fam.szpf_var or _fam.pft_var or _fam.site_var
    if _var:
        TARGET_VAR_MAPPING[_name] = _var

# Also add aliases to TARGET_VAR_MAPPING for direct lookup
for _alias, _canonical in TARGET_ALIASES.items():
    if _canonical in TARGET_VAR_MAPPING:
        TARGET_VAR_MAPPING[_alias] = TARGET_VAR_MAPPING[_canonical]

# Full variable info dict (matches extract_sensitivity_outputs.py format)
OUTPUT_VARIABLES: Dict[str, dict] = {}
for _name, _fam in VARIABLE_FAMILIES.items():
    OUTPUT_VARIABLES[_name] = {
        'site_var': _fam.site_var,
        'pft_var': _fam.pft_var,
        'szpf_var': _fam.szpf_var,
        'units': _fam.units,
        'description': _fam.long_name,
    }

# Also add alias keys that extract_sensitivity_outputs.py uses
OUTPUT_VARIABLES['leaf_biomass'] = OUTPUT_VARIABLES['leaf']
OUTPUT_VARIABLES['fineroot_biomass'] = OUTPUT_VARIABLES['froot']
OUTPUT_VARIABLES['abg_biomass'] = OUTPUT_VARIABLES['abg']
OUTPUT_VARIABLES['total_vegc'] = OUTPUT_VARIABLES['vegc']

# Maps SZPF variable name -> validation factor
VAR_FACTORS: Dict[str, float] = {}
for _fam in VARIABLE_FAMILIES.values():
    if _fam.szpf_var:
        VAR_FACTORS[_fam.szpf_var] = _fam.validation_factor
    if _fam.pft_var:
        VAR_FACTORS[_fam.pft_var] = _fam.validation_factor
    if _fam.site_var:
        VAR_FACTORS[_fam.site_var] = _fam.validation_factor
