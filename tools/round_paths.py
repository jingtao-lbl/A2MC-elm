#!/usr/bin/env python3
"""
Round-aware path resolution for A2MC calibration artifacts.

Reads `use_cases/{site}/config/calibration_rounds.yaml` and returns resolved
paths for a given calibration round, so phase scripts can avoid the fragile
filesystem-glob pattern that previously caused cross-round Y-matrix leakage
(Bug 5 in the 20260413_173425 session report: Phase 4 loaded R3's Morris Y
matrix when R4 was active).

Author: Jing Tao
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _expand_vars(s: str) -> str:
    """Expand ${VAR} references in a string using os.environ."""
    return os.path.expandvars(s) if s else s


def _resolve_yaml_path(yaml_path: Optional[str] = None) -> Path:
    """Return the path to the active use_case's calibration_rounds.yaml."""
    if yaml_path:
        p = Path(yaml_path)
        if p.exists():
            return p
        raise FileNotFoundError(f"Round config YAML not found: {p}")

    use_case_dir = os.environ.get('A2MC_USE_CASE_DIR', '')
    if not use_case_dir:
        raise FileNotFoundError(
            "A2MC_USE_CASE_DIR is not set. Source your site config first "
            "(e.g. `source use_cases/Kougarok/config/kougarok_config_r3.sh`)."
        )
    p = Path(use_case_dir) / 'config' / 'calibration_rounds.yaml'
    if not p.exists():
        raise FileNotFoundError(
            f"Round config YAML not found at expected path: {p}"
        )
    return p


def _resolve_active_round(round_num: Optional[int]) -> int:
    """Resolve the round number from explicit arg, env var, or default."""
    if round_num is not None:
        return int(round_num)
    env = os.environ.get('A2MC_CALIBRATION_ROUND', '')
    if env:
        try:
            return int(env)
        except ValueError:
            pass
    return 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_round_paths(
    round_num: Optional[int] = None,
    yaml_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Load resolved paths and metadata for one calibration round.

    Reads calibration_rounds.yaml and returns a dict with env-var-expanded
    paths. Prefer this over hand-globbing the filesystem when a phase needs
    to know "where does round N's data live."

    Args:
        round_num: Calibration round number (1, 2, 3, ...). If None, falls
            back to the `A2MC_CALIBRATION_ROUND` env var, then to 1.
        yaml_path: Optional override for the YAML path. If None, resolves to
            `${A2MC_USE_CASE_DIR}/config/calibration_rounds.yaml`.

    Returns:
        Dict with fields:
            - round: int (the round whose paths were resolved)
            - sampling_scheme: str ("morris", "sobol", "subset_replay", ...)
            - ensemble_output: str (HPC output root for this round's cases)
            - extracted_data: str (where Phase 1 writes per-case NC extracts)
            - case_name_pattern: str (e.g. "Kougarok_ELM-FATES_PtCNPEn{N}_{PHASE}")
            - param_dir: str (directory of per-case NC parameter files)
            - param_pattern: str (filename pattern with {N} placeholder)
            - ensemble_matrix_file: Optional[str] (flat-text parameter matrix,
              e.g. "FATES_CNPnPlantTraits_162param_Morris_4890sets.txt"; may
              be derived from convention if not in YAML, see below)
            - y_matrix_dir: Optional[str] (directory containing the flat-text
              Morris*Biomass*.txt Y-matrix files; may be derived if not in YAML)
            - config_file: str (site config path, e.g. kougarok_config_r3.sh)
            - overrides: Dict[str, Any] (per-round parameter overrides)
            - source_round: Optional[int] (for subset_replay rounds; the round
              whose cases were sampled to build this round)
            - _yaml_path: str (the YAML file this was loaded from, for debug)

    Raises:
        FileNotFoundError: YAML file not present
        ValueError: requested round not in YAML

    Examples:
        >>> paths = load_round_paths(3)
        >>> paths['sampling_scheme']
        'morris'
        >>> paths['extracted_data']
        '.../Kougarok_PlantTraitsCNPEnsemble162_Morris_RGSPsuplP_Extract'

        >>> paths = load_round_paths(4)
        >>> paths['sampling_scheme']
        'subset_replay'
        >>> paths['source_round']
        3
    """
    import yaml  # lazy import

    yaml_p = _resolve_yaml_path(yaml_path)
    round_num = _resolve_active_round(round_num)

    with open(yaml_p) as f:
        data = yaml.safe_load(f) or {}

    rounds = data.get('rounds', {}) or {}
    rnd = rounds.get(round_num)
    if rnd is None:
        raise ValueError(
            f"Round {round_num} not found in {yaml_p}. "
            f"Available rounds: {sorted(rounds.keys())}"
        )

    paths_block = rnd.get('paths', {}) or {}

    # Derive legacy-compatible defaults when YAML doesn't specify the flat-
    # text Y-matrix locations. This preserves behavior for pre-existing R3
    # artifacts that live under memory/phase_results/phase1_exploration/.
    use_case_dir = os.environ.get('A2MC_USE_CASE_DIR', '')
    y_matrix_dir = _expand_vars(paths_block.get('y_matrix_dir', '')) or None
    if y_matrix_dir is None and use_case_dir:
        legacy = Path(use_case_dir) / 'memory' / 'phase_results' / 'phase1_exploration'
        if legacy.exists():
            y_matrix_dir = str(legacy)

    ensemble_matrix_file = _expand_vars(paths_block.get('ensemble_matrix_file', '')) or None
    if ensemble_matrix_file is None and use_case_dir:
        params_dir = Path(use_case_dir) / 'parameters'
        if params_dir.exists():
            # Prefer a file tagged with the round's size (e.g. "4890sets")
            matches = sorted(params_dir.glob('*Morris*.txt'))
            if matches:
                ensemble_matrix_file = str(matches[0])

    return {
        'round': round_num,
        'sampling_scheme': rnd.get('sampling_scheme', ''),
        'ensemble_output': _expand_vars(paths_block.get('ensemble_output', '')),
        'extracted_data': _expand_vars(paths_block.get('extracted_data', '')),
        'case_name_pattern': paths_block.get('case_name_pattern', ''),
        'param_dir': _expand_vars(paths_block.get('param_dir', '')),
        'param_pattern': paths_block.get('param_pattern', ''),
        'ensemble_matrix_file': ensemble_matrix_file,
        'y_matrix_dir': y_matrix_dir,
        'config_file': rnd.get('config_file', ''),
        'overrides': rnd.get('overrides', {}) or {},
        'source_round': rnd.get('source_round'),
        '_yaml_path': str(yaml_p),
    }


def resolve_ensemble_y_matrix_round(round_num: Optional[int] = None) -> Dict[str, Any]:
    """Return the round whose Y matrix should be used for skip-testing.

    Handles the subset_replay semantics: a subset_replay round's cases are a
    subset of its source_round's cases, and it does not produce a Morris-style
    Y matrix of its own. For skip-testing (ensemble-wide correlations between
    parameters and outputs), the statistically valid data is the source round's
    Morris Y matrix — NOT silently, but with an explicit log so downstream
    consumers (and the AI Phase 4 prompt) can cite the provenance correctly.

    Returns a dict with:
        - active_round: int (the round the orchestrator is running)
        - data_round: int (the round whose Y matrix will be loaded)
        - data_round_paths: Dict (from load_round_paths(data_round))
        - is_source_round_fallback: bool (True if data_round != active_round)
        - reason: str (human-readable explanation, goes into logs / prompts)

    Examples:
        >>> r = resolve_ensemble_y_matrix_round(3)
        >>> r['data_round']
        3
        >>> r['is_source_round_fallback']
        False

        >>> r = resolve_ensemble_y_matrix_round(4)
        >>> r['active_round']
        4
        >>> r['data_round']
        3
        >>> r['is_source_round_fallback']
        True
    """
    active_round = _resolve_active_round(round_num)
    active_paths = load_round_paths(active_round)
    scheme = active_paths.get('sampling_scheme', '')

    # For sensitivity-style schemes, the active round is also the data round.
    if scheme in ('morris', 'sobol', 'lhs'):
        return {
            'active_round': active_round,
            'data_round': active_round,
            'data_round_paths': active_paths,
            'is_source_round_fallback': False,
            'reason': (
                f"Round {active_round} uses sampling_scheme={scheme}; "
                f"Y matrix is this round's own ensemble output."
            ),
        }

    # For subset_replay, fall back to source_round's Y matrix.
    if scheme == 'subset_replay':
        src = active_paths.get('source_round')
        if src is None:
            raise ValueError(
                f"Round {active_round} has sampling_scheme='subset_replay' "
                f"but no source_round in calibration_rounds.yaml. "
                f"Ensemble skip-testing is not possible without a source."
            )
        src_paths = load_round_paths(int(src))
        return {
            'active_round': active_round,
            'data_round': int(src),
            'data_round_paths': src_paths,
            'is_source_round_fallback': True,
            'reason': (
                f"Round {active_round} uses sampling_scheme=subset_replay; "
                f"no standalone sensitivity Y matrix exists for the "
                f"{len(read_case_list(active_paths.get('ensemble_output', '')))}-case "
                f"subset. Skip-testing uses source_round={src}'s Morris Y matrix. "
                f"Hypotheses based on ensemble correlations MUST cite round {src}, "
                f"not round {active_round}."
            ),
        }

    # Unknown scheme — be conservative and error out rather than guess.
    raise ValueError(
        f"Round {active_round} has unknown sampling_scheme='{scheme}'. "
        f"Cannot determine which round's Y matrix to use for skip-testing. "
        f"Add sampling_scheme to calibration_rounds.yaml."
    )


def read_case_list(ensemble_output: str) -> List[int]:
    """Read subset_replay_case_list.txt from an ensemble output dir, if present.

    Returns empty list if the file does not exist (e.g., non-subset_replay
    rounds, or the list hasn't been written yet).
    """
    if not ensemble_output:
        return []
    p = Path(ensemble_output) / 'subset_replay_case_list.txt'
    if not p.exists():
        return []
    cases: List[int] = []
    with open(p) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                cases.append(int(line))
            except ValueError:
                continue
    return cases


# ---------------------------------------------------------------------------
# CLI entry point (for quick manual inspection)
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Inspect resolved paths for a calibration round."
    )
    parser.add_argument(
        "round_num",
        type=int,
        nargs='?',
        default=None,
        help="Round number (defaults to $A2MC_CALIBRATION_ROUND or 1)",
    )
    parser.add_argument(
        "--yaml",
        default=None,
        help="Override path to calibration_rounds.yaml",
    )
    parser.add_argument(
        "--skip-testing-source",
        action="store_true",
        help="Show which round's Y matrix would be used for skip-testing",
    )
    args = parser.parse_args()

    if args.skip_testing_source:
        result = resolve_ensemble_y_matrix_round(args.round_num)
        print(json.dumps(result, indent=2, default=str))
    else:
        paths = load_round_paths(args.round_num, args.yaml)
        print(json.dumps(paths, indent=2, default=str))


if __name__ == "__main__":
    main()
