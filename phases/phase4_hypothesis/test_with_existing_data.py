#!/usr/bin/env python3
"""
Phase 4: Skip Testing - Test Hypotheses with Existing Ensemble Data

Test hypotheses using existing Morris ensemble data instead of running
new HPC experiments. This implements the Skip Testing path (inner loop)
of the three-level iteration structure.

Methods:
- comparison: Compare high vs low parameter groups
- correlation: Compute parameter-output correlations
- threshold: Filter cases meeting threshold criteria
- diagnostic: Run Phase 3 diagnostic scripts
- custom_script: Execute Claude-generated Python scripts

Author: Jing Tao with Claude
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


def _sanitize_numpy_types(obj):
    """Recursively convert numpy types to native Python types for JSON serialization."""
    import numpy as np
    if isinstance(obj, dict):
        return {k: _sanitize_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_sanitize_numpy_types(v) for v in obj]
    elif isinstance(obj, (np.bool_,)):
        return bool(obj)
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj



def test_hypothesis_with_existing_data(
    hypothesis: Dict,
    config: Any,
    screening_data: Dict,
    diagnostic_runner: Optional[Any] = None,
    round_num: Optional[int] = None,
) -> Dict:
    """
    Test a hypothesis using existing Morris ensemble data.

    Args:
        hypothesis: Hypothesis dict with 'existing_data_test' specification
        config: Orchestrator Config object
        screening_data: Screening results from Phase 2
        diagnostic_runner: Optional callable for diagnostic tests
        round_num: Active calibration round. Plumbed through to
            load_morris_ensemble_data() so skip-testing uses the correct
            round's Y matrix (with source_round fallback for subset_replay).
            If None, falls back to A2MC_CALIBRATION_ROUND env var.

    Returns:
        Dict with hypothesis_supported, confidence, test_method,
        evidence, insights, next_steps
    """
    test_spec = hypothesis.get('existing_data_test', {})
    method = test_spec.get('method', 'comparison')
    description = test_spec.get('description', 'Unknown test')

    logger.info(f"Testing hypothesis with existing data:")
    logger.info(f"  Method: {method}")
    logger.info(f"  Description: {description}")

    # Load Morris ensemble data (round-aware — resolves via calibration_rounds.yaml)
    try:
        param_matrix, y_outputs, ensemble_ranges = load_morris_ensemble_data(
            config, screening_data, round_num=round_num
        )
        logger.info(f"  Loaded {len(param_matrix)} parameter sets")
    except Exception as e:
        logger.error(f"Failed to load Morris data: {e}")
        return {
            'hypothesis_supported': False,
            'confidence': 0.0,
            'test_method': method,
            'evidence': {'error': str(e)},
            'insights': [],
            'next_steps': ['Fix data loading before retrying'],
            'untestable_params': [],
        }

    # Dispatch to appropriate test method
    param_names = get_morris_param_names(config)

    # Check which proposed params are outside ensemble range (untestable)
    untestable_params = []
    params = _get_hypothesis_params(hypothesis)
    if ensemble_ranges:
        for p in params:
            name = p.get('name', '')
            proposed = p.get('proposed', p.get('new_value'))
            if name in ensemble_ranges and proposed is not None:
                try:
                    proposed_val = float(proposed)
                except (ValueError, TypeError):
                    continue
                emin = ensemble_ranges[name]['min']
                emax = ensemble_ranges[name]['max']
                if proposed_val < emin or proposed_val > emax:
                    untestable_params.append({
                        'name': name,
                        'proposed': proposed_val,
                        'ensemble_min': emin,
                        'ensemble_max': emax,
                        'reason': f'Proposed {proposed_val} outside ensemble [{emin}, {emax}]'
                    })

        if untestable_params:
            logger.warning(f"  {len(untestable_params)}/{len(params)} params outside ensemble range — UNTESTABLE")
            for up in untestable_params:
                logger.warning(f"    {up['name']}: proposed={up['proposed']}, "
                             f"range=[{up['ensemble_min']}, {up['ensemble_max']}]")

    if method == 'comparison':
        result = test_by_case_comparison(
            hypothesis, test_spec, param_matrix, y_outputs, param_names
        )
    elif method == 'correlation':
        result = test_by_correlation(
            hypothesis, test_spec, param_matrix, y_outputs, param_names
        )
    elif method == 'threshold':
        result = test_by_threshold(
            hypothesis, test_spec, param_matrix, y_outputs, param_names, screening_data
        )
    elif method == 'diagnostic':
        result = test_by_diagnostic(
            hypothesis, test_spec, param_matrix, y_outputs,
            screening_data, diagnostic_runner
        )
    elif method == 'custom_script':
        result = test_by_custom_script(
            hypothesis, test_spec, param_matrix, y_outputs,
            screening_data, config, param_names
        )
    else:
        logger.warning(f"Unknown test method: {method}, using comparison")
        result = test_by_case_comparison(
            hypothesis, test_spec, param_matrix, y_outputs, param_names
        )

    result['test_method'] = method
    result['hypothesis_name'] = hypothesis.get('name', 'Unknown')
    result['untestable_params'] = untestable_params

    # Tag provenance so downstream iterations (and the AI prompt layer) can
    # cite the right round when they summarize this test's findings. If the
    # active round is running subset_replay and this test used source_round's
    # Y matrix, is_source_round_fallback=True tells callers to say "Morris
    # correlation from round {data_round}" instead of conflating with the
    # active round.
    active_round = y_outputs.get('_active_round')
    data_round = y_outputs.get('_data_round')
    if active_round is not None:
        result['active_round'] = active_round
    if data_round is not None:
        result['data_round'] = data_round
    if active_round is not None and data_round is not None:
        result['is_source_round_fallback'] = (active_round != data_round)

    return result


def load_morris_ensemble_data(
    config: Any,
    screening_data: Dict = None,
    round_num: Optional[int] = None,
) -> Tuple:
    """
    Load round-aware Morris parameter matrix and Y outputs for skip-testing.

    Resolves paths via ``tools.round_paths.resolve_ensemble_y_matrix_round()``
    so the right round's data is loaded even when multiple rounds' artifacts
    coexist on disk. For ``subset_replay`` rounds, the source_round's Morris
    Y matrix is loaded (with an explicit log); hypotheses built on the
    resulting correlations MUST cite the source round, not the active round.

    Historical bug this replaces: the previous implementation used a
    recursive glob ``use_case_dir.glob("**/Morris*[Bb]iomass*.txt")`` which
    would silently pick up any round's leftover Y matrix files. Session
    ``20260413_173425`` ran R4 (200 cases) but skip-testing loaded R3's
    4890-row Y matrix, producing confidently wrong hypotheses. See Bug 5
    in the session report.

    Args:
        config: Config object. Only used as a last-resort fallback for
            `use_case_dir` when env vars are not set.
        screening_data: Optional screening data to include under
            ``y_outputs['_screening']``.
        round_num: Active calibration round. If None, falls back to the
            ``A2MC_CALIBRATION_ROUND`` env var, then to 1.

    Returns:
        ``(param_matrix, y_outputs, ensemble_ranges)`` tuple.

        ``y_outputs`` additionally carries two provenance keys so downstream
        consumers (and the Phase 4 prompt) can cite the right round:
            - ``y_outputs['_active_round']``: int, the round the orchestrator
              is running.
            - ``y_outputs['_data_round']``: int, the round whose Y matrix was
              actually loaded (equals ``_active_round`` for Morris/Sobol/LHS,
              equals ``source_round`` for subset_replay).
    """
    import numpy as np
    from tools.round_paths import load_round_paths, resolve_ensemble_y_matrix_round

    # Resolve which round's Y matrix to load. Honors subset_replay
    # source_round fallback with an explicit log.
    resolved = resolve_ensemble_y_matrix_round(round_num)
    active_round = resolved['active_round']
    data_round = resolved['data_round']
    data_paths = resolved['data_round_paths']

    if resolved['is_source_round_fallback']:
        # Fetch active round's own scheme for an accurate log (data_paths
        # refers to the source round's scheme, which would be misleading).
        active_scheme = load_round_paths(active_round).get('sampling_scheme', '?')
        logger.warning(
            f"Ensemble Y matrix fallback: active round is {active_round} "
            f"(sampling_scheme={active_scheme}), but skip-testing will "
            f"load source_round={data_round}'s Morris Y matrix."
        )
        logger.warning(f"  Rationale: {resolved['reason']}")
    else:
        logger.info(
            f"Loading Y matrix for round {active_round} "
            f"(sampling_scheme={data_paths.get('sampling_scheme', '?')})"
        )

    # Parameter matrix: prefer YAML-resolved path, fall back to env var.
    param_file_str = data_paths.get('ensemble_matrix_file') or ''
    env_override = os.environ.get('A2MC_ENSEMBLE_MATRIX_FILE', '')
    if env_override and Path(env_override).exists():
        param_file = Path(env_override)
    elif param_file_str and Path(param_file_str).exists():
        param_file = Path(param_file_str)
    else:
        raise FileNotFoundError(
            f"No Morris parameter matrix file found for round {data_round}. "
            f"Set paths.ensemble_matrix_file in calibration_rounds.yaml, or "
            f"set A2MC_ENSEMBLE_MATRIX_FILE env var. "
            f"YAML-resolved path: {param_file_str or '(none)'}"
        )

    logger.info(f"  Loading parameters from: {param_file}")
    param_matrix = np.loadtxt(param_file)

    # Y output files: look ONLY in the resolved round's y_matrix_dir.
    # No more recursive glob across use_case_dir — that was Bug 5.
    y_matrix_dir = data_paths.get('y_matrix_dir') or ''
    if not y_matrix_dir or not Path(y_matrix_dir).exists():
        raise FileNotFoundError(
            f"No y_matrix_dir resolvable for round {data_round}. "
            f"Expected paths.y_matrix_dir in calibration_rounds.yaml or a "
            f"legacy directory at "
            f"use_cases/{{site}}/memory/phase_results/phase1_exploration/. "
            f"Resolved: {y_matrix_dir or '(none)'}"
        )

    y_outputs: Dict[str, Any] = {}
    y_files = sorted(Path(y_matrix_dir).glob("Morris*[Bb]iomass*.txt"))

    for y_file in y_files:
        name = y_file.stem
        if 'Leaf' in name or 'leaf' in name:
            var_name = 'leaf_biomass'
        elif 'Fineroot' in name or 'FineRoot' in name or 'fineroot' in name:
            var_name = 'froot_biomass'
        elif 'AGB' in name or 'Aboveground' in name or 'Abg' in name or 'abg' in name:
            var_name = 'agb_biomass'
        else:
            var_name = name

        if var_name in y_outputs:
            continue

        try:
            y_outputs[var_name] = np.loadtxt(y_file)
            logger.info(f"  Loaded {var_name}: shape {y_outputs[var_name].shape} from {y_file.name}")
        except Exception as e:
            logger.warning(f"  Could not load {y_file}: {e}")

    biomass_keys = [k for k in y_outputs if k in ('leaf_biomass', 'froot_biomass', 'agb_biomass')]
    if not biomass_keys:
        raise FileNotFoundError(
            f"No Morris Y output files found in {y_matrix_dir}. "
            f"Expected files matching Morris*[Bb]iomass*.txt. "
            f"Phase 1 must have run for round {data_round} first."
        )
    logger.info(f"  Y outputs loaded: {biomass_keys}")

    # Sanity check: shapes should agree between param_matrix and Y outputs.
    n_param = param_matrix.shape[0] if param_matrix.ndim >= 1 else 0
    for k in biomass_keys:
        n_y = y_outputs[k].shape[0] if y_outputs[k].ndim >= 1 else 0
        if n_y != n_param:
            logger.warning(
                f"  Row-count mismatch: param_matrix has {n_param} rows, "
                f"{k} has {n_y}. This round's Morris matrix and Y matrix "
                f"may be out of sync — skip-testing statistics may be wrong."
            )

    # Record which round this data actually represents, so downstream
    # consumers can cite provenance correctly.
    y_outputs['_active_round'] = active_round
    y_outputs['_data_round'] = data_round

    if screening_data:
        y_outputs['_screening'] = screening_data

    # Compute per-parameter ensemble ranges for out-of-range detection
    ensemble_ranges = {}
    param_names = get_morris_param_names(config)
    if param_names and len(param_matrix.shape) > 1:
        for i, name in enumerate(param_names):
            if i < param_matrix.shape[1]:
                ensemble_ranges[name] = {
                    'min': float(np.min(param_matrix[:, i])),
                    'max': float(np.max(param_matrix[:, i])),
                }

    return param_matrix, y_outputs, ensemble_ranges


def get_morris_param_names(config: Any) -> List[str]:
    """Get list of Morris parameter shorthand names from config file.

    Parses the tab-separated parameter list file and extracts the shorthand
    names (column 3, e.g., 'vmax_p_10', 'turnover_fnrt_7') that match the
    column order of the Morris X matrix.
    """
    try:
        param_list_file = getattr(config, 'param_list_file', None)
        if not param_list_file:
            param_list_file = getattr(config, 'param_bounds_file', None)
        if not param_list_file:
            try:
                from tools.config import config as a2mc_config
                param_list_file = a2mc_config.PARAM_LIST_FILE
            except (ImportError, AttributeError):
                param_list_file = os.environ.get('A2MC_PARAM_LIST_FILE', '')

        if param_list_file and Path(param_list_file).exists():
            names = []
            with open(param_list_file) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or line.startswith('='):
                        continue
                    parts = line.split('\t')
                    # Tab-separated format: No, FATES_name, Shorthand, LB, UB, Default, Description
                    if len(parts) >= 3 and parts[0].isdigit():
                        names.append(parts[2])  # Shorthand name (e.g., vmax_p_10)
                    # SALib numbered format: "  1. alpha_ptase_7"
                    elif '.' in line and line.lstrip().split('.')[0].strip().isdigit():
                        name = line.split('.', 1)[1].strip()
                        if name and (name[0].isalpha() or name[0] == '_'):
                            names.append(name)
                    # Simple one-name-per-line format
                    # Parameter names are word chars only (e.g. vmax_p_10) —
                    # reject header text that contains spaces, colons, dots, etc.
                    elif ('\t' not in line and line[0:1].isalpha()
                          and all(c.isalnum() or c == '_' for c in line)):
                        names.append(line)
            if names:
                return names
    except Exception as e:
        logger.warning(f"Could not load parameter names: {e}")
    return []


def _get_param_index(param_name: str, param_names: List[str]) -> int:
    """Get parameter index from name list, returning 0 if not found."""
    try:
        return param_names.index(param_name) if param_names else 0
    except ValueError:
        logger.warning(f"Parameter {param_name} not found in Morris list")
        return 0


def _get_hypothesis_params(hypothesis: Dict) -> list:
    """Extract parameters list from hypothesis (handles both field name conventions)."""
    return hypothesis.get('parameters', hypothesis.get('parameters_to_test', []))


def test_by_case_comparison(
    hypothesis: Dict,
    test_spec: Dict,
    param_matrix,
    y_outputs: Dict,
    param_names: List[str]
) -> Dict:
    """
    Test hypothesis by comparing cases with different parameter values.

    Splits cases into high/low groups based on parameter value median
    and compares outcome means.
    """
    import numpy as np

    params = _get_hypothesis_params(hypothesis)
    if not params:
        return {
            'hypothesis_supported': False,
            'confidence': 0.0,
            'evidence': {'error': 'No parameters specified in hypothesis'},
            'insights': [],
            'next_steps': ['Specify parameters to test']
        }

    param_name = params[0].get('name', '')
    param_idx = _get_param_index(param_name, param_names)

    # Split cases into high/low groups based on parameter value
    param_values = param_matrix[:, param_idx] if len(param_matrix.shape) > 1 else param_matrix
    threshold = np.percentile(param_values, 50)

    high_cases = np.where(param_values > threshold)[0]
    low_cases = np.where(param_values <= threshold)[0]

    logger.info(f"  Comparing {len(high_cases)} high vs {len(low_cases)} low cases")

    # Compare outcomes
    evidence = {}
    supported = False
    confidence = 0.0

    for var_name, y_data in y_outputs.items():
        if var_name.startswith('_'):
            continue

        if len(y_data.shape) == 1:
            y_array = y_data
        else:
            y_array = np.mean(y_data, axis=1) if y_data.shape[1] > 1 else y_data[:, 0]

        valid_high = high_cases[high_cases < len(y_array)]
        valid_low = low_cases[low_cases < len(y_array)]

        if len(valid_high) > 0 and len(valid_low) > 0:
            high_mean = np.mean(y_array[valid_high])
            low_mean = np.mean(y_array[valid_low])
            diff_pct = ((high_mean - low_mean) / low_mean * 100) if low_mean != 0 else 0

            evidence[var_name] = {
                'high_group_mean': float(high_mean),
                'low_group_mean': float(low_mean),
                'difference_pct': float(diff_pct)
            }

            expected_direction = params[0].get('rationale', 'increase')
            if 'increase' in expected_direction.lower() and diff_pct > 10:
                supported = True
                confidence = min(0.9, abs(diff_pct) / 100)
            elif 'decrease' in expected_direction.lower() and diff_pct < -10:
                supported = True
                confidence = min(0.9, abs(diff_pct) / 100)

    insights = []
    if supported:
        insights.append(f"Cases with higher {param_name} show expected outcome difference")
    else:
        insights.append(f"No clear relationship between {param_name} and outcomes in existing data")

    return _sanitize_numpy_types({
        'hypothesis_supported': supported,
        'confidence': confidence,
        'evidence': evidence,
        'insights': insights,
        'next_steps': [
            'Proceed with targeted experiments' if not supported else 'Consider alternative parameters'
        ]
    })


def test_by_correlation(
    hypothesis: Dict,
    test_spec: Dict,
    param_matrix,
    y_outputs: Dict,
    param_names: List[str]
) -> Dict:
    """
    Test hypothesis by computing correlation between parameter and output.
    """
    import numpy as np
    from scipy import stats

    params = _get_hypothesis_params(hypothesis)
    if not params:
        return {
            'hypothesis_supported': False,
            'confidence': 0.0,
            'evidence': {'error': 'No parameters specified'},
            'insights': [],
            'next_steps': []
        }

    param_name = params[0].get('name', '')
    param_idx = _get_param_index(param_name, param_names)
    param_values = param_matrix[:, param_idx] if len(param_matrix.shape) > 1 else param_matrix

    evidence = {}
    max_correlation = 0.0
    significant_correlations = []

    for var_name, y_data in y_outputs.items():
        if var_name.startswith('_'):
            continue

        y_array = y_data[:, 0] if len(y_data.shape) > 1 else y_data

        min_len = min(len(param_values), len(y_array))
        if min_len < 10:
            continue

        try:
            r, p_value = stats.pearsonr(param_values[:min_len], y_array[:min_len])
            evidence[var_name] = {
                'correlation': float(r),
                'p_value': float(p_value),
                'significant': p_value < 0.05
            }

            if abs(r) > abs(max_correlation):
                max_correlation = r

            if p_value < 0.05:
                significant_correlations.append((var_name, r))

        except Exception as e:
            logger.warning(f"Correlation failed for {var_name}: {e}")

    supported = abs(max_correlation) > 0.3 and len(significant_correlations) > 0
    confidence = min(0.9, abs(max_correlation))

    insights = []
    if significant_correlations:
        for var, r in significant_correlations:
            direction = "positive" if r > 0 else "negative"
            insights.append(f"{param_name} shows {direction} correlation (r={r:.3f}) with {var}")
    else:
        insights.append(f"No significant correlation found for {param_name}")

    return _sanitize_numpy_types({
        'hypothesis_supported': supported,
        'confidence': confidence,
        'evidence': evidence,
        'insights': insights,
        'next_steps': [
            'Parameter shows promise, proceed with experiments' if supported
            else 'Consider alternative mechanisms'
        ]
    })


def test_by_threshold(
    hypothesis: Dict,
    test_spec: Dict,
    param_matrix,
    y_outputs: Dict,
    param_names: List[str],
    screening_data: Dict = None
) -> Dict:
    """
    Test hypothesis by filtering cases that meet threshold criteria.

    Compares parameter values in best-performing cases vs all cases.
    """
    import numpy as np

    screening = y_outputs.get('_screening', screening_data or {})
    if not screening:
        return {
            'hypothesis_supported': False,
            'confidence': 0.0,
            'evidence': {'error': 'No screening data available'},
            'insights': [],
            'next_steps': ['Run screening first']
        }

    best_cases = screening.get('best_cases', [])
    best_case_ids = [c.get('case_id', c.get('case_num', 0)) for c in best_cases[:20]]

    params = _get_hypothesis_params(hypothesis)
    param_name = params[0].get('name', '') if params else ''
    param_idx = _get_param_index(param_name, param_names)

    param_values = param_matrix[:, param_idx] if len(param_matrix.shape) > 1 else param_matrix

    # Convert case IDs to indices (0-based)
    best_indices = []
    for cid in best_case_ids:
        try:
            idx = int(cid) - 1 if isinstance(cid, (int, str)) else 0
            if 0 <= idx < len(param_values):
                best_indices.append(idx)
        except (ValueError, TypeError):
            pass

    if not best_indices:
        return {
            'hypothesis_supported': False,
            'confidence': 0.0,
            'evidence': {'error': 'Could not map case IDs to indices'},
            'insights': [],
            'next_steps': ['Check case ID format']
        }

    best_param_mean = np.mean(param_values[best_indices])
    all_param_mean = np.mean(param_values)
    all_param_std = np.std(param_values)

    diff_zscore = (best_param_mean - all_param_mean) / all_param_std if all_param_std > 0 else 0

    evidence = {
        'best_cases_mean': float(best_param_mean),
        'all_cases_mean': float(all_param_mean),
        'z_score': float(diff_zscore),
        'n_best_cases': len(best_indices)
    }

    supported = abs(diff_zscore) > 1.0
    confidence = min(0.9, abs(diff_zscore) / 3.0)

    direction = "higher" if diff_zscore > 0 else "lower"
    insights = [
        f"Best-performing cases have {direction} {param_name} values (z={diff_zscore:.2f})"
    ]

    return _sanitize_numpy_types({
        'hypothesis_supported': supported,
        'confidence': confidence,
        'evidence': evidence,
        'insights': insights,
        'next_steps': [
            f'Prioritize {direction} values of {param_name}' if supported
            else 'Parameter does not distinguish good from bad cases'
        ]
    })


def test_by_diagnostic(
    hypothesis: Dict,
    test_spec: Dict,
    param_matrix,
    y_outputs: Dict,
    screening_data: Dict,
    diagnostic_runner: Optional[Any] = None
) -> Dict:
    """
    Test hypothesis using diagnostic analysis scripts from Phase 3.
    """
    if not screening_data:
        return {
            'hypothesis_supported': False,
            'confidence': 0.0,
            'evidence': {'error': 'No screening data'},
            'insights': [],
            'next_steps': ['Run screening first']
        }

    # Check if diagnostic tools are available
    try:
        from phases.phase3_diagnosis import run_diagnosis_for_orchestrator
        has_tools = True
    except ImportError:
        has_tools = False

    if not has_tools:
        logger.warning("Diagnostic tools not available")
        return {
            'hypothesis_supported': False,
            'confidence': 0.0,
            'evidence': {'error': 'Diagnostic tools not available'},
            'insights': ['Install diagnosis_tools from phases/phase3_diagnosis/'],
            'next_steps': ['Set up diagnostic scripts']
        }

    try:
        if diagnostic_runner:
            diagnostic_result = diagnostic_runner(screening_data)
        else:
            return {
                'hypothesis_supported': False,
                'confidence': 0.0,
                'evidence': {'error': 'No diagnostic runner provided'},
                'insights': [],
                'next_steps': ['Provide diagnostic runner callable']
            }

        if diagnostic_result:
            evidence = {
                'mortality_analysis': diagnostic_result.mortality_analysis,
                'allocation_analysis': diagnostic_result.allocation_analysis,
                'edge_parameters': diagnostic_result.edge_parameters
            }

            mechanism = hypothesis.get('mechanism', '')
            supported = False
            confidence = 0.5

            if 'allocation' in mechanism.lower():
                if diagnostic_result.allocation_analysis:
                    supported = True
                    confidence = 0.7
            elif 'mortality' in mechanism.lower():
                if diagnostic_result.mortality_analysis:
                    supported = 'failure' in str(diagnostic_result.mortality_analysis).lower()
                    confidence = 0.6

            return _sanitize_numpy_types({
                'hypothesis_supported': supported,
                'confidence': confidence,
                'evidence': evidence,
                'insights': diagnostic_result.key_insights if hasattr(diagnostic_result, 'key_insights') else [],
                'next_steps': ['Use diagnostic insights to refine hypothesis']
            })

    except Exception as e:
        logger.error(f"Diagnostic test failed: {e}")
        return {
            'hypothesis_supported': False,
            'confidence': 0.0,
            'evidence': {'error': str(e)},
            'insights': [],
            'next_steps': ['Debug diagnostic script']
        }

    return {
        'hypothesis_supported': False,
        'confidence': 0.0,
        'evidence': {},
        'insights': [],
        'next_steps': ['Run specific diagnostics for this hypothesis']
    }


def test_by_custom_script(
    hypothesis: Dict,
    test_spec: Dict,
    param_matrix,
    y_outputs: Dict,
    screening_data: Dict,
    config: Any,
    param_names: List[str]
) -> Dict:
    """
    Test hypothesis using a custom Python script generated by Claude.

    Saves the script to phases/phase3_diagnosis/generated/ for traceability,
    then executes the test_hypothesis() function safely.
    """
    import importlib.util
    from datetime import datetime

    script_code = test_spec.get('script_code', '')
    script_name = test_spec.get('script_name', 'custom_test')
    description = test_spec.get('description', 'Custom hypothesis test')

    # Check if a promoted tool with this name already exists
    a2mc_root = Path(__file__).parent.parent.parent
    promoted_path = a2mc_root / "phases" / "phase3_diagnosis" / f"{script_name}.py"

    if promoted_path.exists():
        logger.info(f"  Found promoted tool: {promoted_path.name} — using it instead of inline code")
        result = _execute_promoted_tool(
            promoted_path, script_name, description,
            param_matrix, y_outputs, screening_data, config, param_names
        )
        if result is not None:
            return result
        logger.warning(f"  Promoted tool failed, falling back to inline code")

    if not script_code:
        return {
            'hypothesis_supported': False,
            'confidence': 0.0,
            'evidence': {'error': 'No script_code provided'},
            'insights': [],
            'next_steps': ['Provide script_code in existing_data_test']
        }

    logger.info(f"Executing custom script: {script_name}")
    logger.info(f"  Description: {description}")

    # Create generated scripts directory
    a2mc_root = Path(__file__).parent.parent.parent
    generated_dir = a2mc_root / "phases" / "phase3_diagnosis" / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_filename = f"{script_name}_{timestamp}.py"
    script_path = generated_dir / script_filename

    # Prepare the full script with imports and wrapper
    full_script = f'''#!/usr/bin/env python3
"""
Auto-generated custom hypothesis test script.

Description: {description}
Hypothesis: {hypothesis.get('name', 'Unknown')}
Generated: {datetime.now().isoformat()}

This script was generated by Claude AI to test a specific hypothesis
using existing Morris ensemble data.
"""

import numpy as np
try:
    from scipy import stats
except ImportError:
    stats = None

# Custom test function from Claude
{script_code}
'''

    try:
        # Save the script
        with open(script_path, 'w') as f:
            f.write(full_script)
        logger.info(f"  Saved script to: {script_path}")

        # Load the module dynamically
        spec = importlib.util.spec_from_file_location(script_name, script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Check for test_hypothesis function
        if not hasattr(module, 'test_hypothesis'):
            return {
                'hypothesis_supported': False,
                'confidence': 0.0,
                'evidence': {'error': 'Script missing test_hypothesis() function'},
                'insights': [],
                'next_steps': ['Ensure script defines test_hypothesis(param_matrix, y_outputs, screening_data, config)']
            }

        # Prepare config dict for the script
        use_case_dir = getattr(config, 'use_case_dir', None)
        if not use_case_dir:
            try:
                from tools.config import config as a2mc_config
                use_case_dir = a2mc_config.USE_CASE_DIR
            except (ImportError, AttributeError):
                use_case_dir = os.environ.get('A2MC_USE_CASE_DIR', '')

        script_config = {
            'param_names': param_names,
            'pft_ids': [int(p.strip()) for p in os.environ.get('A2MC_PFTS', '7,9,10').split(',')],
            'use_case_dir': str(use_case_dir) if use_case_dir else ''
        }

        # Execute the test function
        logger.info("  Executing test_hypothesis()...")
        result = module.test_hypothesis(
            param_matrix=param_matrix,
            y_outputs=y_outputs,
            screening_data=screening_data,
            config=script_config
        )

        # Validate result format
        if not isinstance(result, dict):
            return {
                'hypothesis_supported': False,
                'confidence': 0.0,
                'evidence': {'error': f'Script returned {type(result)}, expected dict'},
                'insights': [],
                'next_steps': ['Ensure test_hypothesis returns a dict']
            }

        # Sanitize numpy types to native Python for JSON serialization
        result = _sanitize_numpy_types(result)

        # Ensure required fields
        result.setdefault('hypothesis_supported', False)
        result.setdefault('confidence', 0.0)
        result.setdefault('evidence', {})
        result.setdefault('insights', [])
        result.setdefault('next_steps', [])

        # Add script metadata
        result['script_path'] = str(script_path)
        result['script_name'] = script_name

        logger.info(f"  Result: {'SUPPORTED' if result['hypothesis_supported'] else 'NOT SUPPORTED'}")
        logger.info(f"  Confidence: {result['confidence']:.2f}")

        return result

    except SyntaxError as e:
        logger.error(f"Syntax error in custom script: {e}")
        return {
            'hypothesis_supported': False,
            'confidence': 0.0,
            'evidence': {'error': f'Syntax error: {e}', 'line': e.lineno},
            'insights': ['Fix syntax error in script_code'],
            'next_steps': ['Review and correct the script code']
        }

    except Exception as e:
        logger.error(f"Custom script execution failed: {e}")
        import traceback
        return {
            'hypothesis_supported': False,
            'confidence': 0.0,
            'evidence': {'error': str(e), 'traceback': traceback.format_exc()},
            'insights': [],
            'next_steps': ['Debug the custom script', f'Check {script_path}']
        }


def _execute_promoted_tool(
    promoted_path: Path,
    script_name: str,
    description: str,
    param_matrix,
    y_outputs: Dict,
    screening_data: Dict,
    config: Any,
    param_names: List[str]
) -> Optional[Dict]:
    """
    Execute a promoted diagnostic tool instead of AI-generated inline code.

    Returns result dict on success, or None on failure (caller falls back to inline).
    """
    import importlib.util

    try:
        spec = importlib.util.spec_from_file_location(script_name, promoted_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if not hasattr(module, 'test_hypothesis'):
            logger.warning(f"  Promoted tool {promoted_path.name} has no test_hypothesis() — skipping")
            return None

        # Build script_config (same as test_by_custom_script)
        use_case_dir = getattr(config, 'use_case_dir', None)
        if not use_case_dir:
            try:
                from tools.config import config as a2mc_config
                use_case_dir = a2mc_config.USE_CASE_DIR
            except (ImportError, AttributeError):
                use_case_dir = os.environ.get('A2MC_USE_CASE_DIR', '')

        script_config = {
            'param_names': param_names,
            'pft_ids': [int(p.strip()) for p in os.environ.get('A2MC_PFTS', '7,9,10').split(',')],
            'use_case_dir': str(use_case_dir) if use_case_dir else ''
        }

        logger.info(f"  Executing promoted tool test_hypothesis()...")
        result = module.test_hypothesis(
            param_matrix=param_matrix,
            y_outputs=y_outputs,
            screening_data=screening_data,
            config=script_config
        )

        if not isinstance(result, dict):
            logger.warning(f"  Promoted tool returned {type(result)}, expected dict")
            return None

        # Sanitize numpy types to native Python for JSON serialization
        result = _sanitize_numpy_types(result)

        result.setdefault('hypothesis_supported', False)
        result.setdefault('confidence', 0.0)
        result.setdefault('evidence', {})
        result.setdefault('insights', [])
        result.setdefault('next_steps', [])

        result['script_path'] = str(promoted_path)
        result['script_name'] = script_name
        result['promoted_tool'] = True

        logger.info(f"  Result: {'SUPPORTED' if result['hypothesis_supported'] else 'NOT SUPPORTED'}")
        logger.info(f"  Confidence: {result['confidence']:.2f}")

        return result

    except Exception as e:
        logger.error(f"  Promoted tool execution failed: {e}")
        return None