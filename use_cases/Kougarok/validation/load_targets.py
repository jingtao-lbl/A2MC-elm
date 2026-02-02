#!/usr/bin/env python3
"""
Load validation targets from YAML configuration.

Usage:
    from use_cases.Kougarok.validation.load_targets import load_targets
    targets = load_targets()  # Returns Dict[str, Target]
"""

from pathlib import Path
from typing import Dict
import yaml

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tools.optimize_function import Target


def load_targets(yaml_file: Path = None) -> Dict[str, Target]:
    """
    Load validation targets from YAML file.

    Parameters
    ----------
    yaml_file : Path, optional
        Path to targets.yaml. Defaults to same directory as this script.

    Returns
    -------
    Dict[str, Target]
        Dictionary of target names to Target objects
    """
    if yaml_file is None:
        yaml_file = Path(__file__).parent / 'targets.yaml'

    with open(yaml_file, 'r') as f:
        config = yaml.safe_load(f)

    targets = {}
    for name, spec in config.get('targets', {}).items():
        targets[name] = Target(
            name=name,
            observed=spec['observed'],
            uncertainty=spec.get('uncertainty', 0.2),
            units=spec.get('units', ''),
            description=spec.get('description', '')
        )

    return targets


def get_cost_config() -> dict:
    """
    Load cost function configuration from YAML.

    Returns
    -------
    dict
        Cost function configuration
    """
    yaml_file = Path(__file__).parent / 'targets.yaml'

    with open(yaml_file, 'r') as f:
        config = yaml.safe_load(f)

    return config.get('cost_config', {
        'error_method': 'relative_error',
        'aggregation_method': 'rmsre',
        'tolerance': 0.2,
        'tolerance_type': 'relative'
    })


def get_pft_info() -> dict:
    """
    Load PFT information from YAML.

    Returns
    -------
    dict
        PFT definitions {pft_id: {name, description, ...}}
    """
    yaml_file = Path(__file__).parent / 'targets.yaml'

    with open(yaml_file, 'r') as f:
        config = yaml.safe_load(f)

    return config.get('pfts', {})


if __name__ == '__main__':
    # Test loading
    targets = load_targets()
    print(f"Loaded {len(targets)} targets:")
    for name, t in targets.items():
        print(f"  {name}: observed={t.observed:.1f} {t.units}")
