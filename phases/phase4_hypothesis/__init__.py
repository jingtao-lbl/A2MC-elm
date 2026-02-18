"""
Phase 4: Hypothesis Generation

Generate testable hypotheses based on diagnosis.
Design experiments to test each hypothesis.
Test hypotheses with existing ensemble data (Skip Testing path).
Synthesize skip-testing insights into experiment designs.
"""

from phases.phase4_hypothesis.generate_hypothesis import (
    run_hypothesis_generation,
    generate_hypothesis_with_claude,
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
from phases.phase4_hypothesis.synthesis import (
    synthesize_skip_testing_insights,
    write_synthesis_summary_log,
)

__all__ = [
    'run_hypothesis_generation',
    'generate_hypothesis_with_claude',
    'test_hypothesis_with_existing_data',
    'load_morris_ensemble_data',
    'get_morris_param_names',
    'test_by_case_comparison',
    'test_by_correlation',
    'test_by_threshold',
    'test_by_diagnostic',
    'test_by_custom_script',
    'synthesize_skip_testing_insights',
    'write_synthesis_summary_log',
]
