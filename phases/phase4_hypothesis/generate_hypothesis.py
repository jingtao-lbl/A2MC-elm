#!/usr/bin/env python3
"""
Phase 4: Hypothesis Generation

Generate testable hypotheses from diagnosis results using Claude API
or rule-based fallback. This module was extracted from orchestrator.py
to keep phase-specific logic in the phase folder.

Author: Jing Tao with Claude
"""

import logging
from dataclasses import asdict
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


def generate_hypothesis_with_claude(
    diagnosis: Dict,
    reasoning_module: Any,
    exploration_data: Dict,
    previous_experiments: list,
    screening_data: Dict = None
) -> Dict:
    """
    Use Claude API to generate hypothesis from diagnosis.

    Args:
        diagnosis: Diagnosis dict from Phase 3
        reasoning_module: Initialized ReasoningModule instance
        exploration_data: Sensitivity analysis data from Phase 1
        previous_experiments: List of previous experiment dicts
        screening_data: Screening results with case IDs for context

    Returns:
        Hypothesis dict
    """
    from reasoning import Diagnosis
    diagnosis_obj = Diagnosis(**diagnosis)

    hypothesis = reasoning_module.generate_hypothesis(
        diagnosis=diagnosis_obj,
        sensitivity_data=exploration_data.get('sensitivity_rankings', {}),
        previous_experiments=previous_experiments,
        screening_data=screening_data
    )
    return asdict(hypothesis) if hasattr(hypothesis, '__dict__') else hypothesis


def run_hypothesis_generation(
    diagnosis: Dict,
    reasoning_module: Optional[Any],
    exploration_data: Dict,
    previous_experiments: list,
    iteration: int,
    existing_hypotheses: list = None,
    existing_diagnoses: list = None,
    screening_data: Dict = None
) -> Dict:
    """
    High-level API for hypothesis generation.

    Checks for existing hypothesis (resume case), then generates
    using Claude or rule-based fallback.

    Args:
        diagnosis: Latest diagnosis dict
        reasoning_module: ReasoningModule instance (or None)
        exploration_data: Sensitivity analysis data
        previous_experiments: Previous experiment list
        iteration: Current iteration number
        existing_hypotheses: List of existing hypotheses (for resume check)
        existing_diagnoses: List of existing diagnoses (for resume check)
        screening_data: Screening results with case IDs for context

    Returns:
        Hypothesis dict (new or existing)
    """
    # Check if hypothesis already exists for this iteration (resuming after checkpoint)
    if existing_hypotheses:
        last_hyp = existing_hypotheses[-1]
        if last_hyp.get('iteration', None) == iteration or (
            existing_diagnoses and len(existing_hypotheses) >= len(existing_diagnoses)
        ):
            logger.info("Hypothesis already generated for this iteration (resuming from checkpoint)")
            return last_hyp

    logger.info("Generating hypotheses...")

    if not reasoning_module:
        raise RuntimeError("No reasoning module available — Claude API is required for hypothesis generation")

    logger.info("Using Claude API for hypothesis generation...")
    hypothesis = generate_hypothesis_with_claude(
        diagnosis, reasoning_module, exploration_data, previous_experiments,
        screening_data=screening_data
    )

    return hypothesis
