#!/usr/bin/env python3
"""
Reasoning Module Data Schemas

Dataclasses for structured AI reasoning outputs:
- Diagnosis: Structured diagnosis of calibration failures
- Hypothesis: Structured hypothesis for testing
- Experiment: Structured experiment design

Author: Jing Tao with Claude
"""

import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional


@dataclass
class Diagnosis:
    """Structured diagnosis of calibration failures."""
    iteration: int
    failing_targets: List[str]
    likely_causes: List[str]
    parameter_recommendations: List[Dict]
    cross_pft_conflicts: List[str]
    confidence: float  # 0-1
    reasoning: str
    # Requested diagnostics: scripts to run for deeper analysis
    requested_diagnostics: Optional[List[Dict]] = None  # [{tool, reason, priority, args}]
    # Comparative case analysis (best_case vs lowest_cost_case)
    comparative_analysis: Optional[Dict] = None
    # Visual observations from diagnostic figures (multimodal analysis)
    visual_observations: Optional[List[Dict]] = None
    # Protocol recommendations: simulation protocol changes (e.g., suplphos, spinup strategy)
    protocol_recommendations: Optional[List[Dict]] = None  # [{setting, current_value, proposed_value, rationale, requires_respin}]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'Diagnosis':
        data = json.loads(json_str)
        return cls(**data)


@dataclass
class Hypothesis:
    """Structured hypothesis for testing."""
    name: str
    mechanism: str
    parameters: List[Dict]  # [{name, current, proposed, rationale}]
    design_type: str  # "cumulative" or "factorial"
    expected_outcomes: Dict[str, float]
    success_criteria: Dict[str, float]
    confidence: float
    # Skip Testing path: test hypothesis with existing ensemble data
    test_with_existing: bool = False  # If True, can be tested without new HPC runs
    existing_data_test: Optional[Dict] = None  # Test spec: {method, description, cases_to_compare, success_criterion}

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'Hypothesis':
        data = json.loads(json_str)
        return cls(**data)


@dataclass
class Experiment:
    """Structured experiment design."""
    name: str
    base_case: str
    modifications: List[Dict]
    expected_results: Dict[str, float]
    success_threshold: float

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)
