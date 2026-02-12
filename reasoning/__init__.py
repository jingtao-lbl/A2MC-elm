"""
Reasoning Module for Agentic Calibration

This package interfaces with the Claude API to perform:
1. Diagnosis - Analyze why calibration is failing
2. Hypothesis generation - Create testable hypotheses
3. Experiment design - Design specific experiments
4. Result interpretation - Analyze simulation outcomes
5. Discovery extraction - Learn from experiment results

Uses structured prompts and JSON responses for reliable parsing.
Integrates with MemoryManager for adaptive learning.

Author: Jing Tao with Claude
"""

# Schemas (dataclasses)
from reasoning.schemas import Diagnosis, Hypothesis, Experiment

# Prompt constants
from reasoning.prompts import DIAGNOSTIC_TOOLS_INVENTORY, CUSTOM_SCRIPT_TEMPLATE, get_diagnostic_tools_inventory

# Core class
from reasoning.base import ReasoningModule

# Attach phase methods to ReasoningModule
from reasoning import methods as _methods

ReasoningModule.diagnose = _methods.diagnose
ReasoningModule.generate_hypothesis = _methods.generate_hypothesis
ReasoningModule.synthesize_experiment_design = _methods.synthesize_experiment_design
ReasoningModule.design_experiments = _methods.design_experiments
ReasoningModule.interpret_results = _methods.interpret_results
ReasoningModule.extract_lesson = _methods.extract_lesson
ReasoningModule.analyze_screening_results = _methods.analyze_screening_results
ReasoningModule.analyze_sensitivity_results = _methods.analyze_sensitivity_results
ReasoningModule.check_proposed_modifications = _methods.check_proposed_modifications

__all__ = [
    'ReasoningModule',
    'Diagnosis',
    'Hypothesis',
    'Experiment',
    'DIAGNOSTIC_TOOLS_INVENTORY',
    'CUSTOM_SCRIPT_TEMPLATE',
    'get_diagnostic_tools_inventory',
]
