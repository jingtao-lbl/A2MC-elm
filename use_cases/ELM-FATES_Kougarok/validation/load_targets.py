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
from tools.targets_loader import parse_targets_yaml, parse_cost_config


def load_targets(yaml_file: Path = None) -> Dict[str, Target]:
    """
    Load Kougarok validation targets from YAML.

    Thin wrapper over the framework-level parser ``tools.targets_loader.parse_targets_yaml``
    (site-agnostic; supports snapshot and time-series targets — see
    docs/24_Generic_Obs_Comparison_Plan.md). Defaults to this directory's targets.yaml.
    """
    if yaml_file is None:
        yaml_file = Path(__file__).parent / 'targets.yaml'
    return parse_targets_yaml(yaml_file)


def get_cost_config() -> dict:
    """Load the cost-function config block from this case's targets.yaml."""
    return parse_cost_config(Path(__file__).parent / 'targets.yaml')


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
