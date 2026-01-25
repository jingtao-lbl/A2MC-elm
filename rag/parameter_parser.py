"""
FATES Parameter Parser for A2MC

This module provides utilities for parsing FATES parameters from various file formats:
- CDL (.cdl) - Human-readable NetCDF definition files
- JSON (.json) - New FATES default parameter format
- NetCDF (.nc) - Binary parameter files

The parser extracts parameter metadata (name, dimensions, units, description) and
optionally default values, supporting version-flexible GraphRAG construction.

Author: A2MC Framework
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np


# =============================================================================
# Parameter Categories (extracted from name prefix)
# =============================================================================

CATEGORIES = {
    'alloc': 'Allocation',
    'allom': 'Allometry',
    'cnp': 'Carbon-Nitrogen-Phosphorus',
    'damage': 'Damage',
    'dev': 'Development',
    'fire': 'Fire',
    'frag': 'Fragmentation',
    'history': 'History Output',
    'hydro': 'Hydraulics',
    'landuse': 'Land Use',
    'leaf': 'Leaf Physiology',
    'leafn': 'Leaf Nitrogen',
    'litter': 'Litter',
    'maintresp': 'Maintenance Respiration',
    'max': 'Maximum Values',
    'mort': 'Mortality',
    'patch': 'Patch Dynamics',
    'phen': 'Phenology',
    'prt': 'PARTEH',
    'q10': 'Temperature Sensitivity',
    'rad': 'Radiation',
    'recruit': 'Recruitment',
    'regeneration': 'Regeneration',
    'rxfire': 'Prescribed Fire',
    'seed': 'Seed Dynamics',
    'soil': 'Soil',
    'stoich': 'Stoichiometry',
    'trs': 'Tree Recruitment Seedling',
    'turnover': 'Turnover',
    'vai': 'Vegetation Area Index',
}


@dataclass
class FATESParameter:
    """
    Represents a single FATES parameter with its metadata.

    Attributes
    ----------
    name : str
        Official FATES parameter name (e.g., 'fates_alloc_storage_cushion')
    dimensions : List[str]
        List of dimension names (e.g., ['fates_pft'])
    units : str
        Parameter units (e.g., 'unitless', 'kg C m-2')
    long_name : str
        Human-readable description
    data_type : str
        Data type ('double', 'integer', 'string')
    default_values : Optional[np.ndarray]
        Default values if available from file
    """
    name: str
    dimensions: List[str] = field(default_factory=list)
    units: str = 'unknown'
    long_name: str = ''
    data_type: str = 'double'
    default_values: Optional[Any] = None

    @property
    def category(self) -> str:
        """Extract category from parameter name prefix."""
        # fates_xxx_yyy -> xxx
        parts = self.name.split('_')
        if len(parts) >= 2:
            prefix = parts[1]
            return CATEGORIES.get(prefix, prefix)
        return 'other'

    @property
    def category_key(self) -> str:
        """Get the raw category key (for grouping)."""
        parts = self.name.split('_')
        if len(parts) >= 2:
            return parts[1]
        return 'other'

    @property
    def is_pft_specific(self) -> bool:
        """Check if parameter has PFT dimension."""
        return 'fates_pft' in self.dimensions

    @property
    def is_scalar(self) -> bool:
        """Check if parameter is scalar (no dimensions)."""
        return len(self.dimensions) == 0

    @property
    def is_string(self) -> bool:
        """Check if parameter is string type."""
        return self.data_type in ('string', 'char')

    def __repr__(self) -> str:
        dims = f"({', '.join(self.dimensions)})" if self.dimensions else "(scalar)"
        return f"FATESParameter({self.name}{dims})"


class FATESParameterParser:
    """
    Parse FATES parameters from CDL, JSON, or NetCDF files.

    This parser extracts all parameter metadata from FATES parameter files,
    supporting multiple file formats for version flexibility.

    Parameters
    ----------
    file_path : str
        Path to FATES parameter file (.cdl, .json, or .nc)

    Examples
    --------
    >>> parser = FATESParameterParser('fates_params_api25.5.0_12pft.cdl')
    >>> params = parser.parse()
    >>> print(len(params))
    286
    >>> print(params['fates_alloc_storage_cushion'])
    FATESParameter(fates_alloc_storage_cushion(fates_pft))
    """

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"Parameter file not found: {file_path}")
        self.format = self._detect_format()
        self._parameters: Optional[Dict[str, FATESParameter]] = None
        self._dimensions: Optional[Dict[str, int]] = None

    def _detect_format(self) -> str:
        """Detect file format from extension."""
        suffix = self.file_path.suffix.lower()
        if suffix == '.cdl':
            return 'cdl'
        elif suffix == '.json':
            return 'json'
        elif suffix == '.nc':
            return 'nc'
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

    def parse(self) -> Dict[str, FATESParameter]:
        """
        Parse all parameters from the file.

        Returns
        -------
        Dict[str, FATESParameter]
            Dictionary mapping parameter names to FATESParameter objects
        """
        if self._parameters is not None:
            return self._parameters

        if self.format == 'cdl':
            self._parameters, self._dimensions = self._parse_cdl()
        elif self.format == 'json':
            self._parameters, self._dimensions = self._parse_json()
        elif self.format == 'nc':
            self._parameters, self._dimensions = self._parse_nc()

        return self._parameters

    def get_dimensions(self) -> Dict[str, int]:
        """
        Get dimension names and sizes.

        Returns
        -------
        Dict[str, int]
            Dictionary mapping dimension names to sizes
            e.g., {'fates_pft': 12, 'fates_plant_organs': 4}
        """
        if self._dimensions is None:
            self.parse()
        return self._dimensions

    def get_pft_count(self) -> int:
        """Get number of PFTs in this parameter file."""
        dims = self.get_dimensions()
        return dims.get('fates_pft', 12)

    def get_pft_names(self) -> Dict[int, str]:
        """
        Get PFT names from parameter file.

        Returns
        -------
        Dict[int, str]
            Dictionary mapping PFT ID (1-based) to PFT name
        """
        params = self.parse()
        if 'fates_pftname' in params:
            param = params['fates_pftname']
            if param.default_values is not None:
                names = param.default_values
                return {i + 1: name for i, name in enumerate(names)}
        return {}

    def get_parameters_by_category(self) -> Dict[str, List[FATESParameter]]:
        """
        Group parameters by category.

        Returns
        -------
        Dict[str, List[FATESParameter]]
            Dictionary mapping category keys to lists of parameters
        """
        params = self.parse()
        by_category = {}
        for param in params.values():
            cat = param.category_key
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(param)
        return by_category

    def get_pft_parameters(self) -> List[FATESParameter]:
        """Get all PFT-specific parameters."""
        params = self.parse()
        return [p for p in params.values() if p.is_pft_specific]

    def get_scalar_parameters(self) -> List[FATESParameter]:
        """Get all scalar (shared) parameters."""
        params = self.parse()
        return [p for p in params.values() if p.is_scalar]

    # =========================================================================
    # CDL Parser
    # =========================================================================

    def _parse_cdl(self) -> Tuple[Dict[str, FATESParameter], Dict[str, int]]:
        """Parse parameters from CDL file."""
        with open(self.file_path, 'r') as f:
            content = f.read()

        # Parse dimensions
        dimensions = self._parse_cdl_dimensions(content)

        # Parse variables (parameters)
        parameters = {}

        # Match variable declarations: type name(dims); or type name;
        # Handles double, int, char types
        var_pattern = r'^\s+(double|int|char)\s+(fates_\w+)(?:\(([^)]+)\))?\s*;'

        for match in re.finditer(var_pattern, content, re.MULTILINE):
            data_type = match.group(1)
            name = match.group(2)
            dims_str = match.group(3)

            # Parse dimensions
            if dims_str:
                # Extract dimension names (before =)
                dims = [d.split('=')[0].strip() for d in dims_str.split(',')]
            else:
                dims = []

            # Map char to string for consistency
            if data_type == 'char':
                data_type = 'string'
                # Remove string_length dimension for string types
                dims = [d for d in dims if 'string' not in d.lower()]

            parameters[name] = FATESParameter(
                name=name,
                dimensions=dims,
                data_type=data_type,
            )

        # Parse attributes (units, long_name)
        self._parse_cdl_attributes(content, parameters)

        return parameters, dimensions

    def _parse_cdl_dimensions(self, content: str) -> Dict[str, int]:
        """Parse dimension declarations from CDL content."""
        dimensions = {}

        # Find dimensions section
        dim_section = re.search(r'dimensions:\s*\n(.*?)(?=variables:|data:|$)',
                                content, re.DOTALL)
        if dim_section:
            dim_text = dim_section.group(1)
            # Match: dimension_name = size ;
            for match in re.finditer(r'(\w+)\s*=\s*(\d+)\s*;', dim_text):
                dim_name = match.group(1)
                dim_size = int(match.group(2))
                dimensions[dim_name] = dim_size

        return dimensions

    def _parse_cdl_attributes(self, content: str, parameters: Dict[str, FATESParameter]):
        """Parse variable attributes (units, long_name) from CDL content."""
        # Match: variable_name:attribute = "value" ;
        attr_pattern = r'(fates_\w+):(\w+)\s*=\s*"([^"]*)"'

        for match in re.finditer(attr_pattern, content):
            var_name = match.group(1)
            attr_name = match.group(2)
            attr_value = match.group(3)

            if var_name in parameters:
                if attr_name == 'units':
                    parameters[var_name].units = attr_value
                elif attr_name == 'long_name':
                    parameters[var_name].long_name = attr_value

    # =========================================================================
    # JSON Parser
    # =========================================================================

    def _parse_json(self) -> Tuple[Dict[str, FATESParameter], Dict[str, int]]:
        """Parse parameters from JSON file."""
        with open(self.file_path, 'r') as f:
            data = json.load(f)

        # Parse dimensions
        dimensions = data.get('dimensions', {})

        # Parse parameters
        parameters = {}
        params_data = data.get('parameters', {})

        for name, info in params_data.items():
            # Get dimensions (normalize 'scalar' to empty list)
            dims = info.get('dims', [])
            if dims == ['scalar']:
                dims = []

            # Get data type
            dtype = info.get('dtype', 'float')
            if dtype == 'float':
                dtype = 'double'
            elif dtype == 'integer':
                dtype = 'int'

            # Get default values
            default_values = info.get('data', None)

            parameters[name] = FATESParameter(
                name=name,
                dimensions=dims,
                units=info.get('units', 'unknown'),
                long_name=info.get('long_name', ''),
                data_type=dtype,
                default_values=default_values,
            )

        return parameters, dimensions

    # =========================================================================
    # NetCDF Parser
    # =========================================================================

    def _parse_nc(self) -> Tuple[Dict[str, FATESParameter], Dict[str, int]]:
        """Parse parameters from NetCDF file."""
        try:
            import netCDF4 as nc
        except ImportError:
            raise ImportError("netCDF4 package required for parsing .nc files")

        ds = nc.Dataset(self.file_path, 'r')

        # Parse dimensions
        dimensions = {name: len(dim) for name, dim in ds.dimensions.items()}

        # Parse parameters
        parameters = {}

        for var_name, var in ds.variables.items():
            if not var_name.startswith('fates_'):
                continue

            # Get dimensions
            dims = list(var.dimensions)
            # Remove string length dimension for char arrays
            dims = [d for d in dims if 'string' not in d.lower()]

            # Determine data type
            dtype_str = str(var.dtype)
            if 'float' in dtype_str or dtype_str == 'float64':
                data_type = 'double'
            elif 'int' in dtype_str:
                data_type = 'int'
            elif dtype_str.startswith('|S') or dtype_str == 'object':
                data_type = 'string'
            else:
                data_type = 'double'

            # Get default values
            try:
                if data_type == 'string':
                    # Handle character arrays (NetCDF stores as bytes)
                    raw_data = var[:]
                    default_values = []
                    for row in raw_data:
                        try:
                            # Join bytes and decode
                            if hasattr(row, '__iter__'):
                                name = b''.join(row).decode('utf-8').strip()
                            else:
                                name = str(row).strip()
                            default_values.append(name)
                        except Exception:
                            default_values.append('')
                else:
                    default_values = var[:].data
            except Exception:
                default_values = None

            parameters[var_name] = FATESParameter(
                name=var_name,
                dimensions=dims,
                units=getattr(var, 'units', 'unknown'),
                long_name=getattr(var, 'long_name', ''),
                data_type=data_type,
                default_values=default_values,
            )

        ds.close()
        return parameters, dimensions


# =============================================================================
# Utility Functions
# =============================================================================

def compare_parameter_files(
    file1: str,
    file2: str
) -> Dict[str, Any]:
    """
    Compare parameters between two FATES parameter files.

    Parameters
    ----------
    file1 : str
        Path to first parameter file
    file2 : str
        Path to second parameter file

    Returns
    -------
    Dict with keys:
        'common': List of common parameter names
        'only_in_file1': List of parameters only in file1
        'only_in_file2': List of parameters only in file2
        'dimension_changes': List of (name, old_dims, new_dims) tuples
    """
    parser1 = FATESParameterParser(file1)
    parser2 = FATESParameterParser(file2)

    params1 = parser1.parse()
    params2 = parser2.parse()

    names1 = set(params1.keys())
    names2 = set(params2.keys())

    common = names1 & names2
    only1 = names1 - names2
    only2 = names2 - names1

    # Find dimension changes
    dim_changes = []
    for name in common:
        dims1 = tuple(params1[name].dimensions)
        dims2 = tuple(params2[name].dimensions)
        if dims1 != dims2:
            dim_changes.append((name, dims1, dims2))

    return {
        'common': sorted(common),
        'only_in_file1': sorted(only1),
        'only_in_file2': sorted(only2),
        'dimension_changes': dim_changes,
        'file1_count': len(params1),
        'file2_count': len(params2),
    }


def get_calibratable_parameters(
    file_path: str,
    exclude_string: bool = True,
    exclude_history: bool = True,
) -> List[FATESParameter]:
    """
    Get list of parameters suitable for calibration.

    Filters out string parameters and history output parameters by default.

    Parameters
    ----------
    file_path : str
        Path to FATES parameter file
    exclude_string : bool
        Exclude string-type parameters (default: True)
    exclude_history : bool
        Exclude history bin edge parameters (default: True)

    Returns
    -------
    List[FATESParameter]
        List of calibratable parameters
    """
    parser = FATESParameterParser(file_path)
    params = parser.parse()

    calibratable = []
    for param in params.values():
        # Skip string parameters
        if exclude_string and param.is_string:
            continue
        # Skip history bin parameters
        if exclude_history and 'history' in param.name:
            continue
        # Skip name parameters
        if param.name.endswith('_name'):
            continue
        calibratable.append(param)

    return calibratable


# =============================================================================
# Main (for testing)
# =============================================================================

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python parameter_parser.py <param_file>")
        sys.exit(1)

    file_path = sys.argv[1]
    parser = FATESParameterParser(file_path)
    params = parser.parse()
    dims = parser.get_dimensions()

    print(f"\nParsed {len(params)} parameters from {file_path}")
    print(f"\nDimensions:")
    for name, size in sorted(dims.items()):
        print(f"  {name}: {size}")

    print(f"\nParameters by category:")
    by_cat = parser.get_parameters_by_category()
    for cat, cat_params in sorted(by_cat.items()):
        print(f"  {cat}: {len(cat_params)} parameters")

    print(f"\nPFT-specific parameters: {len(parser.get_pft_parameters())}")
    print(f"Scalar parameters: {len(parser.get_scalar_parameters())}")

    # Show first few parameters
    print(f"\nFirst 10 parameters:")
    for i, (name, param) in enumerate(sorted(params.items())[:10]):
        print(f"  {param}")
