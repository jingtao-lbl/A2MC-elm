#!/usr/bin/env python3
"""
Generic validation-target loader (framework-level, site-agnostic).

Loads calibration targets + cost configuration + snapshot time anchor from a case's
``targets.yaml``. This is the single source of parsing logic; the per-site loaders
(e.g. ``use_cases/<site>/validation/load_targets.py``) delegate here.

Observation forms per target (see docs/24_Generic_Obs_Comparison_Plan.md):

- **Snapshot**: scalar ``observed`` matched to a single timestep. Time anchor from the
  top-level ``time_year`` / ``time_month``; optional per-target ``obs_months`` averages
  those months (e.g. ``[7, 8]`` for end-of-month sampling vs monthly output).
- **Time series**: an ``observations`` list of ``{year, month, value, [uncertainty], [months]}``.

Either form yields a self-contained Target carrying ``observations`` (length-1 for a
snapshot). Optional per-target ``cost_method`` overrides the global
``cost_config.error_method``.

Author: Jing Tao with Claude
"""

import os
from pathlib import Path
from typing import Dict, Optional, Tuple

import yaml

try:
    from .optimize_function import Target, ObsPoint
except ImportError:
    from tools.optimize_function import Target, ObsPoint

DEFAULT_COST_CONFIG = {
    'error_method': 'relative_error',
    'aggregation_method': 'rmsre',
    'tolerance': 0.2,
    'tolerance_type': 'relative',
}


def resolve_targets_yaml(use_case_dir: Optional[str] = None) -> Optional[Path]:
    """
    Resolve the path to a case's targets.yaml.

    Priority: explicit ``$A2MC_VALIDATION_TARGETS`` env var, else
    ``<use_case_dir>/validation/targets.yaml`` (use_case_dir defaults to
    ``$A2MC_USE_CASE_DIR``). Returns None if nothing exists.
    """
    env_path = os.environ.get('A2MC_VALIDATION_TARGETS', '')
    if env_path:
        p = Path(env_path)
        return p if p.exists() else None
    ucd = use_case_dir or os.environ.get('A2MC_USE_CASE_DIR', '')
    if ucd:
        p = Path(ucd) / 'validation' / 'targets.yaml'
        if p.exists():
            return p
    return None


def parse_targets_yaml(yaml_file) -> Dict[str, Target]:
    """Parse a targets.yaml into ``{name: Target}`` (snapshot or time series)."""
    yaml_file = Path(yaml_file)
    with open(yaml_file, 'r') as f:
        config = yaml.safe_load(f)

    anchor_year = config.get('time_year')
    anchor_month = config.get('time_month')

    targets: Dict[str, Target] = {}
    for name, spec in config.get('targets', {}).items():
        unc = spec.get('uncertainty', 0.2)
        observed = spec.get('observed')
        observations = None

        if 'observations' in spec:
            observations = [
                ObsPoint(
                    year=int(p['year']),
                    month=int(p['month']),
                    value=float(p['value']),
                    months=p.get('months'),
                    uncertainty=p.get('uncertainty'),
                )
                for p in spec['observations']
            ]
            if observed is None:
                observed = observations[0].value
        elif observed is not None and anchor_year is not None and anchor_month is not None:
            observations = [
                ObsPoint(
                    year=int(anchor_year),
                    month=int(anchor_month),
                    value=float(observed),
                    months=spec.get('obs_months'),
                    uncertainty=unc,
                )
            ]

        targets[name] = Target(
            name=name,
            observed=observed,
            uncertainty=unc,
            units=spec.get('units', ''),
            description=spec.get('description', ''),
            obs_std=spec.get('original_std'),
            observations=observations,
            cost_method=spec.get('cost_method'),
        )

    return targets


def parse_cost_config(yaml_file) -> dict:
    """Read the ``cost_config`` block (with defaults) from a targets.yaml."""
    with open(Path(yaml_file), 'r') as f:
        config = yaml.safe_load(f)
    cc = dict(DEFAULT_COST_CONFIG)
    cc.update(config.get('cost_config', {}) or {})
    return cc


def parse_time_anchor(yaml_file) -> Tuple[Optional[int], Optional[int]]:
    """Read the snapshot time anchor (time_year, time_month) from a targets.yaml."""
    with open(Path(yaml_file), 'r') as f:
        config = yaml.safe_load(f)
    return config.get('time_year'), config.get('time_month')


def load_case_targets(use_case_dir: Optional[str] = None):
    """
    Resolve and load a case's targets, cost config, and snapshot time anchor.

    Returns ``(targets, cost_config, (anchor_year, anchor_month))``. If no targets.yaml
    is found, returns ``(None, None, (None, None))`` so callers can fall back to a
    site-specific loader. This is the generic entry point used by the screening helper
    and the orchestrator to avoid hardcoding any site's target list.
    """
    path = resolve_targets_yaml(use_case_dir)
    if path is None:
        return None, None, (None, None)
    return parse_targets_yaml(path), parse_cost_config(path), parse_time_anchor(path)
