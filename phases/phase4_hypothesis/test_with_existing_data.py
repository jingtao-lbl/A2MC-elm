#!/usr/bin/env python3
"""
Phase 4: Skip Testing - Test Hypotheses with Existing Ensemble Data

Test hypotheses using existing Morris ensemble data instead of running
new HPC experiments. This implements the Skip Testing path (inner loop)
of the two-level iteration structure.

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


def test_hypothesis_with_existing_data(
    hypothesis: Dict,
    config: Any,
    screening_data: Dict,
    diagnostic_runner: Optional[Any] = None
) -> Dict:
    """
    Test a hypothesis using existing Morris ensemble data.

    Args:
        hypothesis: Hypothesis dict with 'existing_data_test' specification
        config: Orchestrator Config object
        screening_data: Screening results from Phase 2
        diagnostic_runner: Optional callable for diagnostic tests

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

    # Load Morris ensemble data
    try:
        param_matrix, y_outputs = load_morris_ensemble_data(config, screening_data)
        logger.info(f"  Loaded {len(param_matrix)} parameter sets")
    except Exception as e:
        logger.error(f"Failed to load Morris data: {e}")
        return {
            'hypothesis_supported': False,
            'confidence': 0.0,
            'test_method': method,
            'evidence': {'error': str(e)},
            'insights': [],
            'next_steps': ['Fix data loading before retrying']
        }

    # Dispatch to appropriate test method
    param_names = get_morris_param_names(config)

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

    return result


def load_morris_ensemble_data(config: Any, screening_data: Dict = None) -> Tuple:
    """
    Load Morris parameter matrix and Y outputs.

    Args:
        config: Config object with use_case_dir or output_dir
        screening_data: Optional screening data to include

    Returns:
        (param_matrix, y_outputs) tuple
    """
    import numpy as np

    # Get use case directory from config or environment
    use_case_dir = getattr(config, 'use_case_dir', None)
    if not use_case_dir:
        try:
            from tools.config import config as a2mc_config
            use_case_dir = a2mc_config.USE_CASE_DIR
        except (ImportError, AttributeError):
            use_case_dir = os.environ.get('A2MC_USE_CASE_DIR', '')

    if not use_case_dir:
        raise FileNotFoundError("Cannot determine use case directory")

    # Parameter matrix file - check config/env var first, then glob
    param_file = None

    # 1. Check A2MC_ENSEMBLE_MATRIX_FILE from config or env
    ensemble_matrix = os.environ.get('A2MC_ENSEMBLE_MATRIX_FILE', '')
    if not ensemble_matrix:
        try:
            from tools.config import config as a2mc_config
            ensemble_matrix = getattr(a2mc_config, 'ENSEMBLE_MATRIX_FILE', '')
        except (ImportError, AttributeError):
            pass

    if ensemble_matrix and Path(ensemble_matrix).exists():
        param_file = Path(ensemble_matrix)
    else:
        # 2. Glob in use_case_dir/parameters/
        param_files = list(Path(use_case_dir).glob("parameters/*Morris*.txt"))
        # 3. Glob in phases/phase0_design/
        if not param_files:
            a2mc_root = Path(use_case_dir).parent.parent
            param_files = list((a2mc_root / "phases" / "phase0_design").glob("*Morris*.txt"))
        # 4. Legacy: SALib_FATES/
        if not param_files:
            param_files = list(Path(use_case_dir).parent.parent.glob("SALib_FATES/*Morris*.txt"))

        if not param_files:
            raise FileNotFoundError(
                "No Morris parameter matrix file found. "
                "Set A2MC_ENSEMBLE_MATRIX_FILE or place file in "
                "use_cases/{site}/parameters/ or phases/phase0_design/"
            )
        param_file = param_files[0]

    logger.info(f"  Loading parameters from: {param_file}")
    param_matrix = np.loadtxt(param_file)

    # Y output files
    y_outputs = {}

    y_files = list(Path(use_case_dir).glob("**/Morris*Biomass*.txt"))
    if not y_files:
        y_files = list(Path(use_case_dir).parent.glob("Morris*Biomass*.txt"))

    for y_file in y_files:
        name = y_file.stem
        if 'Leaf' in name:
            var_name = 'leaf_biomass'
        elif 'Fineroot' in name or 'FineRoot' in name:
            var_name = 'froot_biomass'
        elif 'AGB' in name or 'Aboveground' in name:
            var_name = 'agb_biomass'
        else:
            var_name = name

        try:
            y_outputs[var_name] = np.loadtxt(y_file)
            logger.info(f"  Loaded {var_name}: shape {y_outputs[var_name].shape}")
        except Exception as e:
            logger.warning(f"  Could not load {y_file}: {e}")

    # Also include screening data if available
    if screening_data:
        y_outputs['_screening'] = screening_data

    return param_matrix, y_outputs


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
                    elif '\t' not in line and line[0:1].isalpha():
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

    return {
        'hypothesis_supported': supported,
        'confidence': confidence,
        'evidence': evidence,
        'insights': insights,
        'next_steps': [
            'Proceed with targeted experiments' if not supported else 'Consider alternative parameters'
        ]
    }


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

    return {
        'hypothesis_supported': supported,
        'confidence': confidence,
        'evidence': evidence,
        'insights': insights,
        'next_steps': [
            'Parameter shows promise, proceed with experiments' if supported
            else 'Consider alternative mechanisms'
        ]
    }


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

    return {
        'hypothesis_supported': supported,
        'confidence': confidence,
        'evidence': evidence,
        'insights': insights,
        'next_steps': [
            f'Prioritize {direction} values of {param_name}' if supported
            else 'Parameter does not distinguish good from bad cases'
        ]
    }


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

            return {
                'hypothesis_supported': supported,
                'confidence': confidence,
                'evidence': evidence,
                'insights': diagnostic_result.key_insights if hasattr(diagnostic_result, 'key_insights') else [],
                'next_steps': ['Use diagnostic insights to refine hypothesis']
            }

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
