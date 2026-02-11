"""
Phase 4: Hypothesis Generation

Generate testable hypotheses based on diagnosis.
Design experiments to test each hypothesis.
Test hypotheses with existing ensemble data (Skip Testing path).
"""

from phases.phase4_hypothesis.generate_hypothesis import (
    run_hypothesis_generation,
    generate_hypothesis_with_claude,
    generate_hypothesis_rule_based,
)
from phases.phase4_hypothesis.test_with_existing_data import (
    test_hypothesis_with_existing_data,
    load_morris_ensemble_data,
    get_morris_param_names,
    test_by_case_comparison,
    test_by_correlation,
    test_by_threshold,
    test_by_diagnostic,
    test_by_custom_script,
)

__all__ = [
    'run_hypothesis_generation',
    'generate_hypothesis_with_claude',
    'generate_hypothesis_rule_based',
    'test_hypothesis_with_existing_data',
    'load_morris_ensemble_data',
    'get_morris_param_names',
    'test_by_case_comparison',
    'test_by_correlation',
    'test_by_threshold',
    'test_by_diagnostic',
    'test_by_custom_script',
]
