#!/usr/bin/env python3
"""
Reasoning Module for Agentic Calibration

This module interfaces with the Claude API to perform:
1. Diagnosis - Analyze why calibration is failing
2. Hypothesis generation - Create testable hypotheses
3. Experiment design - Design specific experiments
4. Result interpretation - Analyze simulation outcomes
5. Discovery extraction - Learn from experiment results

Uses structured prompts and JSON responses for reliable parsing.
Integrates with MemoryManager for adaptive learning.
"""

import os
import json
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from memory import MemoryManager

try:
    import anthropic
except ImportError:
    anthropic = None
    print("Warning: anthropic package not installed. Run: pip install anthropic")

# Configuration
try:
    from tools.config import config as a2mc_config
except ImportError:
    a2mc_config = None

# RAG/GraphRAG integration
try:
    from rag import HybridRetriever
except ImportError as e:
    HybridRetriever = None
    print(f"Warning: RAG module not available ({e}). RAG context will be disabled.")
    print("  To enable RAG, install: pip install networkx chromadb sentence-transformers pyyaml")
    print("  Or use Python 3.10: /Library/Frameworks/Python.framework/Versions/3.10/bin/python3")

logger = logging.getLogger(__name__)


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


class ReasoningModule:
    """
    Claude API interface for agentic reasoning.

    This module uses carefully crafted prompts to elicit structured,
    actionable outputs from Claude for each reasoning task.
    """

    # System prompt establishing the agent's expertise
    SYSTEM_PROMPT = """You are an expert in ELM-FATES (E3SM Land Model - Functionally Assembled Terrestrial Ecosystem Simulator) calibration, specializing in:

1. Arctic tundra ecosystems and plant functional types (PFTs)
2. Carbon-Nitrogen-Phosphorus (CNP) cycling and nutrient limitation
3. Sensitivity analysis interpretation (Morris, Sobol, etc.)
4. Multi-objective optimization for ecosystem models
5. Mechanistic hypothesis generation for model calibration

Your role is to act as an autonomous calibration agent that:
- Analyzes simulation results objectively
- Identifies mechanistic causes of model-observation mismatch
- Generates testable hypotheses with specific parameter modifications
- Designs efficient experiments (cumulative or factorial)
- Interprets results and recommends next steps
- Learns from experiments and records discoveries for future reference

IMPORTANT: You have access to a MEMORY SYSTEM containing:
- Verified DISCOVERIES from previous calibration work
- FAILED EXPERIMENTS that should NOT be repeated
- PARAMETER RELATIONSHIPS and known interactions

When the memory context mentions "DO NOT REPEAT", you MUST NOT propose that approach
unless you have strong justification for why it would work differently this time.

Always respond with structured JSON that can be parsed programmatically.
Be specific about parameter names, values, and expected quantitative outcomes.
Express uncertainty when appropriate using confidence scores (0-1)."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 memory: Optional['MemoryManager'] = None,
                 use_rag: bool = True):
        """
        Initialize the reasoning module.

        Args:
            api_key: AI API key. Resolution order:
                     1. Explicit argument
                     2. A2MC_AI_API_KEY_ENV config (default: AI_API_KEY)
            model: Claude model to use. Resolution order:
                   1. Explicit argument
                   2. A2MC_AI_MODEL env var
                   3. Default: claude-sonnet-4-20250514
            memory: Optional MemoryManager for adaptive learning
            use_rag: Whether to use RAG/GraphRAG for context retrieval

        Environment Variables (set in a2mc_config.sh):
            A2MC_AI_MODEL: Model name (e.g., claude-sonnet-4-20250514)
            A2MC_AI_MAX_TOKENS: Max tokens for responses (default: 4096)
            AI_API_KEY: API key (or use A2MC_AI_API_KEY_ENV to specify different var)
        """
        # Resolve API key
        if api_key:
            self.api_key = api_key
        elif a2mc_config:
            self.api_key = a2mc_config.get_ai_api_key()
        else:
            self.api_key = os.environ.get("AI_API_KEY")

        # Resolve model
        if model:
            self.model = model
        elif a2mc_config:
            self.model = a2mc_config.AI_MODEL
        else:
            self.model = os.environ.get("A2MC_AI_MODEL", "claude-sonnet-4-20250514")

        self.memory = memory
        self.use_rag = use_rag

        if anthropic is None:
            raise ImportError("anthropic package required. Install with: pip install anthropic")

        if not self.api_key:
            raise ValueError("AI_API_KEY not found in environment. Set it with: export AI_API_KEY='your-key'")

        self.client = anthropic.Anthropic(api_key=self.api_key)

        # Initialize RAG retriever if enabled
        self.rag_retriever = None
        if use_rag and HybridRetriever is not None:
            try:
                self.rag_retriever = HybridRetriever(auto_build=False)
                logger.info("RAG/GraphRAG retriever initialized")
            except Exception as e:
                logger.warning(f"Could not initialize RAG retriever: {e}")
                self.rag_retriever = None

        memory_status = "with memory" if memory else "without memory"
        rag_status = "with RAG" if self.rag_retriever else "without RAG"
        logger.info(f"Reasoning module initialized {memory_status}, {rag_status}, model: {self.model}")

    def query(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Send a query to Claude and return the response.

        Args:
            prompt: The prompt to send
            max_tokens: Max tokens for response. If None, uses A2MC_AI_MAX_TOKENS config.
        """
        if max_tokens is None:
            if a2mc_config:
                max_tokens = a2mc_config.AI_MAX_TOKENS
            else:
                max_tokens = int(os.environ.get("A2MC_AI_MAX_TOKENS", "4096"))
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise

    def _get_rag_context(self,
                         parameters: List[str] = None,
                         outputs: List[str] = None,
                         mechanisms: List[str] = None,
                         pft: int = None,
                         query: str = None) -> str:
        """
        Get relevant context from RAG/GraphRAG for reasoning.

        Args:
            parameters: List of parameter names being considered
            outputs: List of output variables being analyzed
            mechanisms: List of FATES mechanisms relevant to the task
            pft: Specific PFT number if applicable
            query: Optional natural language query for additional context

        Returns:
            Formatted context string to include in prompts
        """
        if not self.rag_retriever:
            return ""

        try:
            context_parts = []

            # Get calibration context if we have structured entities
            if parameters or outputs or mechanisms:
                cal_context = self.rag_retriever.get_calibration_context(
                    parameters=parameters,
                    outputs=outputs,
                    mechanisms=mechanisms,
                    pft=pft,
                    n_vector_results=3,
                    graph_depth=2
                )
                if cal_context.get('combined'):
                    context_parts.append(cal_context['combined'])

            # Get additional context from natural language query
            if query:
                query_context = self.rag_retriever.get_context(
                    query=query,
                    n_vector_results=3,
                    graph_depth=2,
                    include_graph=True
                )
                if query_context.get('combined'):
                    context_parts.append(query_context['combined'])

            if context_parts:
                return "## FATES Knowledge Base Context (RAG/GraphRAG)\n" + "\n\n".join(context_parts) + "\n\n"

        except Exception as e:
            logger.warning(f"RAG context retrieval failed: {e}")

        return ""

    def diagnose(self, results: Dict, targets: Dict,
                 sensitivity_rankings: Dict, iteration: int) -> Diagnosis:
        """
        Analyze why calibration is failing.

        Args:
            results: Current simulation results by target
            targets: Validation targets with uncertainties
            sensitivity_rankings: Parameter sensitivity rankings (from Morris/Sobol/etc.)
            iteration: Current workflow iteration

        Returns:
            Structured Diagnosis object
        """
        # Identify failing targets for memory query
        failing_targets = []
        for target, value in results.items():
            if target in targets:
                target_mean = targets[target].get("mean", targets[target])
                if isinstance(target_mean, dict):
                    target_mean = target_mean.get("mean", 0)
                if value < target_mean * 0.8 or value > target_mean * 1.2:
                    failing_targets.append(target)

        # Get memory context if available
        memory_context = ""
        if self.memory and failing_targets:
            memory_context = self.memory.get_relevant_context(failing_targets)
            if memory_context:
                memory_context = f"""## Adaptive Memory Context (from previous calibration work)
{memory_context}

"""

        # Get RAG context for relevant parameters and outputs
        rag_context = ""
        if self.rag_retriever:
            # Extract parameter names from sensitivity rankings
            param_names = []
            for target_params in sensitivity_rankings.values():
                if isinstance(target_params, list):
                    param_names.extend([p.get('param', p.get('parameter', ''))
                                       for p in target_params[:5]])
            # Map target names to output variables
            output_names = [f"FATES_{t.upper().replace('_', 'C_')}" for t in results.keys()]

            rag_context = self._get_rag_context(
                parameters=list(set(param_names))[:10],
                outputs=output_names[:6],
                mechanisms=['PID_Controller', 'ECA_Competition', 'Storage_Allocation'],
                query="calibration diagnosis nutrient limitation biomass allocation"
            )

        prompt = f"""Analyze these ELM-FATES calibration results and diagnose why targets are not being met.

{rag_context}{memory_context}## Current Results (simulated values in g C/m²)
{json.dumps(results, indent=2)}

## Validation Targets (observed values with ±20% uncertainty)
{json.dumps(targets, indent=2)}

## Sensitivity Rankings (top parameters by importance)
{json.dumps(sensitivity_rankings, indent=2)}

## Task
Diagnose why calibration is failing. Consider:
1. Which specific targets are failing and by what magnitude?
2. What are the mechanistic causes based on FATES model structure?
3. Which parameters from sensitivity rankings should be prioritized?
4. Are there cross-PFT conflicts (shared parameters affecting multiple PFTs differently)?
5. What insights from the knowledge base context (if provided) are relevant?

IMPORTANT: If the knowledge base shows failed approaches, DO NOT recommend those approaches.

## Response Format
Return a JSON object with this structure:
```json
{{
    "iteration": {iteration},
    "failing_targets": ["target1", "target2"],
    "likely_causes": [
        "Mechanistic explanation 1",
        "Mechanistic explanation 2"
    ],
    "parameter_recommendations": [
        {{
            "parameter": "param_name",
            "current_issue": "why this is a problem",
            "suggested_direction": "increase/decrease",
            "priority": 1
        }}
    ],
    "cross_pft_conflicts": [
        "Description of any shared parameter conflicts"
    ],
    "confidence": 0.85,
    "reasoning": "Brief explanation of the diagnosis logic"
}}
```

Respond ONLY with the JSON object, no additional text."""

        response = self.query(prompt)

        # Parse response
        try:
            # Extract JSON from response (handle potential markdown wrapping)
            json_str = response.strip()
            if json_str.startswith("```"):
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
            data = json.loads(json_str)
            return Diagnosis(**data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse diagnosis response: {e}")
            logger.error(f"Response was: {response}")
            raise

    def generate_hypothesis(self, diagnosis: Diagnosis,
                           sensitivity_data: Dict,
                           previous_experiments: List[Dict]) -> Hypothesis:
        """
        Generate a testable hypothesis from diagnosis.

        Args:
            diagnosis: Diagnosis object from previous phase
            sensitivity_data: Full sensitivity analysis data
            previous_experiments: List of experiments already tried

        Returns:
            Structured Hypothesis object
        """
        # Get failed approaches from memory
        failed_approaches_context = ""
        if self.memory:
            failed_approaches = self.memory.failed_approaches.get("failed_approaches", [])
            if failed_approaches:
                failed_approaches_context = "\n## FAILED APPROACHES - DO NOT PROPOSE THESE\n"
                for fa in failed_approaches[:10]:
                    failed_approaches_context += f"- **{fa.get('approach', '?')}**: {fa.get('why_failed', 'Failed')}\n"
                    if fa.get("alternatives"):
                        failed_approaches_context += f"  Alternatives: {', '.join(fa['alternatives'][:2])}\n"
                failed_approaches_context += "\n"

        # Get RAG context for parameters mentioned in diagnosis
        rag_context = ""
        if self.rag_retriever:
            # Extract parameters from diagnosis recommendations
            param_names = [rec.get('parameter', '') for rec in diagnosis.parameter_recommendations]
            # Infer mechanisms from likely causes
            mechanisms = []
            causes_text = " ".join(diagnosis.likely_causes).lower()
            if 'pid' in causes_text or 'allocation' in causes_text:
                mechanisms.append('PID_Controller')
            if 'nutrient' in causes_text or 'phosphorus' in causes_text or 'nitrogen' in causes_text:
                mechanisms.append('ECA_Competition')
            if 'storage' in causes_text:
                mechanisms.append('Storage_Allocation')
            if 'mortality' in causes_text or 'starvation' in causes_text:
                mechanisms.append('Carbon_Starvation')

            rag_context = self._get_rag_context(
                parameters=param_names[:10],
                mechanisms=mechanisms if mechanisms else ['PID_Controller'],
                query=f"hypothesis testing {' '.join(diagnosis.likely_causes[:2])}"
            )

        prompt = f"""Based on this diagnosis, generate a testable hypothesis for ELM-FATES calibration.
{rag_context}{failed_approaches_context}
## Diagnosis
{diagnosis.to_json()}

## Sensitivity Analysis Data (top 20 parameters per output)
{json.dumps(sensitivity_data, indent=2)}

## Previous Experiments (avoid repeating these)
{json.dumps(previous_experiments, indent=2)}

## Task
Generate a specific, testable hypothesis with:
1. A clear mechanistic name (e.g., "PFT9 Mortality Trap", "Nutrient Limitation Bottleneck")
2. A mechanistic explanation of why this would improve calibration
3. Specific parameters to modify with current and proposed values
4. Recommended experimental design (cumulative for sequential mechanisms, factorial for interacting parameters)
5. Quantitative expected outcomes for each target

## Design Guidelines
- Use CUMULATIVE design when mechanisms are sequential (A → B → C)
- Use FACTORIAL design when parameters may interact (P × N synergy)
- Only modify PFT-specific parameters to avoid cross-PFT conflicts
- Propose values within physically realistic bounds

## Response Format
Return a JSON object with this structure:
```json
{{
    "name": "Hypothesis Name",
    "mechanism": "Detailed mechanistic explanation",
    "parameters": [
        {{
            "name": "fates_param_name",
            "pft": 9,
            "current": 0.787,
            "proposed": 0.30,
            "rationale": "Why this change should help"
        }}
    ],
    "design_type": "cumulative",
    "expected_outcomes": {{
        "leaf_pft9": 120.0,
        "froot_pft9": 65.0
    }},
    "success_criteria": {{
        "leaf_pft9_within_20pct": true,
        "no_degradation_other_pfts": true
    }},
    "confidence": 0.75
}}
```

Respond ONLY with the JSON object."""

        response = self.query(prompt)

        try:
            json_str = response.strip()
            if json_str.startswith("```"):
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
            data = json.loads(json_str)
            return Hypothesis(**data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse hypothesis response: {e}")
            raise

    def design_experiments(self, hypothesis: Hypothesis,
                          base_case: Dict) -> List[Experiment]:
        """
        Design specific experiments from hypothesis.

        Args:
            hypothesis: Hypothesis to test
            base_case: Best current case to modify

        Returns:
            List of Experiment objects
        """
        prompt = f"""Design specific experiments to test this hypothesis.

## Hypothesis
{hypothesis.to_json()}

## Base Case (starting point)
{json.dumps(base_case, indent=2)}

## Task
Design a sequence of experiments following the {hypothesis.design_type} approach.

For CUMULATIVE design:
- Exp1: Modify first parameter only
- Exp2: Exp1 + second parameter
- Exp3: Exp2 + third parameter
- etc.

For FACTORIAL design:
- Test all combinations of parameters
- Include individual effects AND interactions

## Response Format
Return a JSON array of experiments:
```json
[
    {{
        "name": "Exp1",
        "base_case": "case_2678",
        "modifications": [
            {{
                "parameter": "param_name",
                "old_value": 0.787,
                "new_value": 0.30
            }}
        ],
        "expected_results": {{
            "leaf_pft9": 80.0,
            "improvement_pct": 50
        }},
        "success_threshold": 0.20
    }}
]
```

Respond ONLY with the JSON array."""

        response = self.query(prompt)

        try:
            json_str = response.strip()
            if json_str.startswith("```"):
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
            data = json.loads(json_str)
            return [Experiment(**exp) for exp in data]
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse experiments response: {e}")
            raise

    def interpret_results(self, experiment: Experiment,
                         actual_results: Dict,
                         targets: Dict) -> Dict:
        """
        Interpret experiment results and recommend next steps.

        Args:
            experiment: The experiment that was run
            actual_results: Actual simulation results
            targets: Validation targets

        Returns:
            Interpretation with recommendations
        """
        # Get RAG context for parameters modified in experiment
        rag_context = ""
        if self.rag_retriever:
            param_names = [mod.get('parameter', '') for mod in experiment.modifications]
            output_names = list(actual_results.keys())

            rag_context = self._get_rag_context(
                parameters=param_names,
                outputs=[f"FATES_{o.upper()}" for o in output_names[:6]],
                query="experiment results interpretation parameter effects"
            )

        prompt = f"""Interpret these ELM-FATES experiment results.

{rag_context}

## Experiment
{experiment.to_json()}

## Actual Results
{json.dumps(actual_results, indent=2)}

## Targets
{json.dumps(targets, indent=2)}

## Task
Analyze the results and provide:
1. Which targets improved, stayed same, or degraded?
2. Was the hypothesis confirmed, partially confirmed, or rejected?
3. What mechanistic insights can we draw?
4. What should be the next step?

## Response Format
```json
{{
    "targets_improved": ["target1"],
    "targets_degraded": [],
    "hypothesis_status": "partially_confirmed",
    "insights": [
        "Mechanistic insight 1",
        "Mechanistic insight 2"
    ],
    "recommendation": {{
        "action": "continue_testing|iterate|converge",
        "next_hypothesis": "Description if iterating",
        "parameters_to_adjust": []
    }},
    "confidence": 0.80
}}
```

Respond ONLY with the JSON object."""

        response = self.query(prompt)

        try:
            json_str = response.strip()
            if json_str.startswith("```"):
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse interpretation response: {e}")
            raise

    def extract_lesson(self, experiment: Dict, results: Dict,
                      outcome: str) -> Dict:
        """
        Extract lessons and potential discoveries from experiment results.

        This method is called after failed or interesting experiments to
        extract mechanistic insights that should be recorded in memory.

        Args:
            experiment: Experiment specification that was run
            results: Actual results from simulation
            outcome: Outcome category (success, FAILED, catastrophic_collapse, etc.)

        Returns:
            Dict with:
            - lesson: String describing what was learned
            - is_discovery: Boolean if this reveals a new mechanistic insight
            - discovery: Dict with discovery details if is_discovery is True
            - should_add_to_failed_approaches: Boolean
            - failed_approach: Dict with failed approach details if applicable
        """
        # Get RAG context for parameters modified in experiment
        rag_context = ""
        if self.rag_retriever:
            modifications = experiment.get('modifications', [])
            param_names = [mod.get('parameter', '') for mod in modifications]
            output_names = list(results.keys()) if results else []

            rag_context = self._get_rag_context(
                parameters=param_names,
                outputs=[f"FATES_{o.upper()}" for o in output_names[:6]],
                query=f"lesson extraction {outcome} experiment mechanistic insight"
            )

        prompt = f"""Analyze this ELM-FATES experiment to extract lessons for future calibration.

{rag_context}

## Experiment
Name: {experiment.get('name', 'Unknown')}
Base case: {experiment.get('base_case', 'Unknown')}
Modifications: {json.dumps(experiment.get('modifications', []), indent=2)}

## Results
{json.dumps(results, indent=2)}

## Outcome
{outcome}

## Task
Extract lessons from this experiment. Consider:
1. What mechanistic insight does this reveal about FATES behavior?
2. Is this a significant discovery that should be recorded for future reference?
3. If the experiment failed, should this approach be added to a "do not repeat" list?

A DISCOVERY should be recorded if:
- The result reveals a non-obvious mechanism (e.g., feedback loops, parameter interactions)
- The result contradicts expectations in an informative way
- The insight would help prevent future mistakes

## Response Format
```json
{{
    "lesson": "One-line summary of what was learned",
    "detailed_mechanism": "Detailed explanation of the mechanism if discovered",
    "is_discovery": true,
    "discovery": {{
        "name": "short_identifier",
        "description": "One-line description",
        "mechanism": "Detailed mechanistic explanation",
        "affects": ["output1", "output2"],
        "parameters_involved": ["param1", "param2"],
        "implications": ["Implication 1", "Implication 2"],
        "do_not_repeat": ["Approach to avoid"]
    }},
    "should_add_to_failed_approaches": true,
    "failed_approach": {{
        "approach": "Description of the approach",
        "why_failed": "Explanation",
        "severity": "catastrophic|degradation|no_effect",
        "alternatives": ["Alternative 1", "Alternative 2"]
    }},
    "confidence": 0.75
}}
```

If is_discovery is false, omit the discovery field.
If should_add_to_failed_approaches is false, omit the failed_approach field.

Respond ONLY with the JSON object."""

        response = self.query(prompt)

        try:
            json_str = response.strip()
            if json_str.startswith("```"):
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
            result = json.loads(json_str)

            # Auto-record to memory if available
            if self.memory:
                # Record discovery if significant
                if result.get("is_discovery") and result.get("discovery"):
                    disc = result["discovery"]
                    self.memory.add_discovery(
                        name=disc.get("name", f"discovery_{experiment.get('name', 'unknown')}"),
                        description=disc.get("description", ""),
                        mechanism=disc.get("mechanism", ""),
                        affects=disc.get("affects", []),
                        implications=disc.get("implications", []),
                        parameters_involved=disc.get("parameters_involved", []),
                        do_not_repeat=disc.get("do_not_repeat", []),
                        source="auto_discovered",
                        confidence=result.get("confidence", 0.6)
                    )
                    logger.info(f"Auto-recorded discovery: {disc.get('name')}")

                # Record failed approach if applicable
                if result.get("should_add_to_failed_approaches") and result.get("failed_approach"):
                    fa = result["failed_approach"]
                    self.memory.add_failed_approach(
                        approach=fa.get("approach", ""),
                        experiment_id=experiment.get("name", "unknown"),
                        why_failed=fa.get("why_failed", ""),
                        severity=fa.get("severity", "unknown"),
                        alternatives=fa.get("alternatives", [])
                    )
                    logger.info(f"Auto-recorded failed approach: {fa.get('approach')}")

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse lesson extraction response: {e}")
            # Return minimal result on parse failure
            return {
                "lesson": f"Experiment {outcome}. Unable to extract detailed lesson.",
                "is_discovery": False,
                "should_add_to_failed_approaches": outcome in ["FAILED", "catastrophic_collapse"],
                "confidence": 0.3
            }

    def analyze_screening_results(self, screening_results: Dict,
                                    targets: Dict,
                                    parameter_sets: Dict,
                                    sensitivity_rankings: Optional[Dict] = None) -> Dict:
        """
        AI analysis of screening results BEFORE diagnosis.

        This method analyzes the distribution of errors, identifies patterns
        in successful cases, detects edge cases, and prepares context for diagnosis.

        Args:
            screening_results: Results from cost function screening
                - ranked_indices: Best to worst indices
                - composite_cost: Cost per parameter set
                - individual_errors: {target: errors_array}
                - n_satisfied: Targets satisfied per set
            targets: Validation targets with observed values
            parameter_sets: Parameter values for all sets (n_sets × n_params)
            sensitivity_rankings: Optional sensitivity rankings (from Morris/Sobol/etc.)

        Returns:
            Dict with:
            - error_patterns: Which targets fail most often and why
            - edge_cases: Parameters at bounds in top cases
            - success_patterns: Common features of top cases
            - pft_tradeoffs: Conflicts between PFTs
            - recommendations: What to focus on in diagnosis
            - knowledge_entries: New knowledge to add to memory
        """
        # Prepare summary statistics
        n_sets = len(screening_results.get("composite_cost", []))
        top_indices = screening_results.get("ranked_indices", [])[:50]
        top_costs = [screening_results["composite_cost"][i] for i in top_indices[:10]]

        # Identify failing targets
        individual_errors = screening_results.get("individual_errors", {})
        target_failure_rates = {}
        for target, errors in individual_errors.items():
            # Count how often this target fails (error > 0.2 = outside ±20%)
            failure_rate = sum(1 for e in errors if e > 0.2) / len(errors)
            target_failure_rates[target] = failure_rate

        # Get memory context
        memory_context = ""
        if self.memory:
            # Get relevant discoveries and parameter knowledge
            failing_targets = [t for t, r in target_failure_rates.items() if r > 0.5]
            if failing_targets:
                memory_context = self.memory.get_relevant_context(failing_targets)
                if memory_context:
                    memory_context = f"""## Adaptive Memory Context
{memory_context}

"""

        # Get RAG context for targets being analyzed
        rag_context = ""
        if self.rag_retriever:
            # Map target names to output variables
            output_names = [f"FATES_{t.upper().replace('LEAF', 'LEAFC').replace('FROOT', 'FROOTC')}"
                           for t in target_failure_rates.keys()]
            # Get relevant mechanisms for screening analysis
            rag_context = self._get_rag_context(
                outputs=output_names[:6],
                mechanisms=['PID_Controller', 'ECA_Competition', 'Storage_Allocation'],
                query="screening analysis multi-target calibration parameter sensitivity"
            )

        prompt = f"""Analyze these ELM-FATES screening results to prepare for diagnosis.

{rag_context}{memory_context}## Screening Summary
- Total parameter sets evaluated: {n_sets}
- Best composite cost: {top_costs[0]:.4f}
- Top 10 costs: {[f"{c:.4f}" for c in top_costs]}

## Target Failure Rates (fraction of sets where target is outside ±20%)
{json.dumps(target_failure_rates, indent=2)}

## Validation Targets
{json.dumps(targets, indent=2)}

## Individual Errors for Top 10 Cases
{json.dumps({t: [individual_errors[t][i] for i in top_indices[:10]] for t in individual_errors}, indent=2)}

{f"## Sensitivity Rankings{chr(10)}{json.dumps(sensitivity_rankings, indent=2)}" if sensitivity_rankings else ""}

## Task
Analyze the screening results to identify:

1. **Error Patterns**: Which targets fail most often? Are failures correlated?
2. **Success Patterns**: What do the top 10 cases have in common?
3. **PFT Trade-offs**: Do improvements in one PFT come at the cost of another?
4. **Priority Targets**: Which targets should diagnosis focus on?
5. **Potential Mechanisms**: What FATES mechanisms might explain the patterns?

## Response Format
```json
{{
    "error_patterns": [
        {{
            "target": "target_name",
            "failure_rate": 0.85,
            "typical_direction": "underestimated|overestimated",
            "likely_mechanism": "Mechanism explanation"
        }}
    ],
    "success_patterns": [
        "Pattern observed in top cases"
    ],
    "pft_tradeoffs": [
        {{
            "pft_improved": "PFT9",
            "pft_degraded": "PFT10",
            "shared_parameter": "param_name",
            "explanation": "Why this trade-off occurs"
        }}
    ],
    "priority_targets": ["target1", "target2"],
    "potential_mechanisms": [
        {{
            "mechanism": "Mechanism name",
            "affects": ["target1", "target2"],
            "confidence": 0.7,
            "evidence": "What in the data suggests this"
        }}
    ],
    "recommendations_for_diagnosis": [
        "Focus on X because Y"
    ],
    "knowledge_entries": [
        {{
            "type": "parameter_pattern|discovery|caution",
            "content": "Description of the knowledge",
            "confidence": 0.8
        }}
    ]
}}
```

Respond ONLY with the JSON object."""

        response = self.query(prompt)

        try:
            json_str = response.strip()
            if json_str.startswith("```"):
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
            result = json.loads(json_str)

            # Auto-record knowledge entries to memory if available
            if self.memory and result.get("knowledge_entries"):
                for entry in result["knowledge_entries"]:
                    if entry.get("type") == "discovery":
                        self.memory.add_discovery(
                            name=f"screening_insight_{len(self.memory.discoveries.get('discoveries', []))}",
                            description=entry.get("content", ""),
                            mechanism="Identified from screening analysis",
                            affects=result.get("priority_targets", []),
                            confidence=entry.get("confidence", 0.6)
                        )
                        logger.info(f"Auto-recorded screening insight to memory")

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse screening analysis response: {e}")
            logger.error(f"Response was: {response}")
            # Return minimal result
            return {
                "error_patterns": [],
                "success_patterns": [],
                "pft_tradeoffs": [],
                "priority_targets": list(target_failure_rates.keys())[:3],
                "potential_mechanisms": [],
                "recommendations_for_diagnosis": ["Unable to parse AI analysis"],
                "knowledge_entries": []
            }

    def analyze_sensitivity_results(self, morris_rankings: Dict,
                                       pfts: List[str],
                                       output_var: str,
                                       problem: Optional[Dict] = None) -> Dict:
        """
        AI analysis of Morris sensitivity analysis results for Phase 1.

        Analyzes parameter rankings (μ*, σ) to identify:
        - Key parameters driving model behavior
        - Parameter interactions (high σ/μ* ratio)
        - Cross-PFT patterns (generic vs PFT-specific importance)
        - Knowledge to add to the knowledge base

        Args:
            morris_rankings: Dict with PFT keys, each containing list of dicts:
                [{parameter, mu, mu_star, sigma, mu_star_conf, rank}, ...]
            pfts: List of PFT identifiers (e.g., ['PFT7', 'PFT9', 'PFT10'])
            output_var: Output variable analyzed (e.g., 'leaf_biomass')
            problem: Optional SALib problem definition with parameter bounds

        Returns:
            Dict with:
            - key_parameters: Top parameters with interpretations
            - interactions: Parameters with high σ indicating non-linear effects
            - cross_pft_patterns: Parameters important across all vs specific PFTs
            - edge_effects: Parameters that may need expanded sampling ranges
            - knowledge_entries: Discoveries to add to knowledge base
            - recommendations: For next phases (diagnosis, hypothesis)
        """
        # Prepare summary of top parameters per PFT
        top_params_summary = {}
        for pft in pfts:
            if pft in morris_rankings:
                # Get top 10 parameters by mu_star
                rankings = morris_rankings[pft]
                if isinstance(rankings, list):
                    sorted_rankings = sorted(rankings,
                                            key=lambda x: abs(x.get('mu_star', 0)),
                                            reverse=True)
                    top_params_summary[pft] = sorted_rankings[:10]

        # Identify parameters with high interaction (σ/μ* > 0.5)
        high_interaction_params = {}
        for pft in pfts:
            if pft in morris_rankings:
                rankings = morris_rankings[pft]
                if isinstance(rankings, list):
                    interactions = []
                    for r in rankings:
                        mu_star = abs(r.get('mu_star', 0))
                        sigma = abs(r.get('sigma', 0))
                        if mu_star > 0.01:  # Avoid division by zero
                            ratio = sigma / mu_star
                            if ratio > 0.5:  # High interaction threshold
                                interactions.append({
                                    'parameter': r.get('parameter'),
                                    'mu_star': mu_star,
                                    'sigma': sigma,
                                    'ratio': ratio
                                })
                    high_interaction_params[pft] = sorted(
                        interactions, key=lambda x: x['ratio'], reverse=True
                    )[:5]

        # Find cross-PFT patterns (parameters in top 20 for all PFTs)
        all_pft_top20 = {}
        for pft in pfts:
            if pft in morris_rankings:
                rankings = morris_rankings[pft]
                if isinstance(rankings, list):
                    sorted_rankings = sorted(rankings,
                                            key=lambda x: abs(x.get('mu_star', 0)),
                                            reverse=True)
                    # Extract base parameter names (remove PFT suffix if present)
                    top20_params = set()
                    for r in sorted_rankings[:20]:
                        param = r.get('parameter', '')
                        # Remove PFT suffix like _7, _9, _10
                        base_param = param
                        for suffix in ['_7', '_9', '_10', '_11', '_12']:
                            if param.endswith(suffix):
                                base_param = param[:-len(suffix)]
                                break
                        top20_params.add(base_param)
                    all_pft_top20[pft] = top20_params

        # Find intersection (parameters important for ALL PFTs)
        if all_pft_top20:
            common_params = set.intersection(*all_pft_top20.values())
        else:
            common_params = set()

        # Get memory context for relevant parameters
        memory_context = ""
        if self.memory:
            param_names = []
            for pft_params in top_params_summary.values():
                param_names.extend([p.get('parameter', '') for p in pft_params[:5]])
            if param_names:
                memory_context = self.memory.get_relevant_context(
                    targets=[output_var],
                    parameters=param_names[:10]
                )
                if memory_context:
                    memory_context = f"""## Adaptive Memory Context
{memory_context}

"""

        # Get RAG context for top parameters
        rag_context = ""
        if self.rag_retriever:
            # Extract unique parameter names from top rankings
            param_names = []
            for pft_params in top_params_summary.values():
                param_names.extend([p.get('parameter', '') for p in pft_params[:5]])
            param_names = list(set(param_names))[:15]

            # Map output var to FATES variable name
            output_mapping = {
                'leaf_biomass': 'FATES_LEAFC',
                'fineroot_biomass': 'FATES_FROOTC',
                'abg_biomass': 'FATES_VEGC_ABOVEGROUND',
                'total_vegc': 'FATES_VEGC',
                'gpp': 'FATES_GPP',
                'npp': 'FATES_NPP',
                'lai': 'FATES_LAI'
            }
            output_name = output_mapping.get(output_var, f'FATES_{output_var.upper()}')

            rag_context = self._get_rag_context(
                parameters=param_names,
                outputs=[output_name],
                mechanisms=['PID_Controller', 'ECA_Competition', 'Storage_Allocation'],
                query=f"Morris sensitivity analysis {output_var} parameter importance"
            )

        prompt = f"""Analyze these Morris sensitivity analysis results for ELM-FATES calibration.

{rag_context}{memory_context}## Output Variable Analyzed
{output_var}

## PFTs Analyzed
{', '.join(pfts)}

## Top 10 Parameters by μ* (each PFT)
{json.dumps(top_params_summary, indent=2)}

## Parameters with High Interaction (σ/μ* > 0.5)
{json.dumps(high_interaction_params, indent=2)}

## Parameters Important for ALL PFTs (in top 20 for each)
{list(common_params)}

{f"## Parameter Bounds (from SALib problem){chr(10)}{json.dumps(problem, indent=2)}" if problem else ""}

## Task
Analyze the Morris sensitivity results to extract actionable insights:

1. **Key Parameters**: Which parameters have the strongest influence? What mechanisms do they control?

2. **Parameter Interactions**: High σ/μ* ratio indicates non-linear effects or interactions.
   - Which parameters interact?
   - What does this mean for calibration strategy?

3. **Cross-PFT Patterns**:
   - Parameters important for ALL PFTs → Generic importance, adjust carefully
   - Parameters important for ONE PFT → PFT-specific tuning possible

4. **Edge Effects**: Parameters with high μ* near sampling bounds may need:
   - Expanded ranges in next iteration
   - Caution about extrapolation

5. **Knowledge Base Entries**: What should be recorded for future reference?
   - Generic FATES mechanisms (for all use cases)
   - Site-specific patterns (for this use case only)

## Response Format
```json
{{
    "key_parameters": [
        {{
            "parameter": "param_name",
            "mu_star": 0.45,
            "mechanism": "What this parameter controls",
            "pfts_affected": ["PFT7", "PFT9"],
            "calibration_priority": "high|medium|low",
            "notes": "Additional insights"
        }}
    ],
    "interactions": [
        {{
            "parameter": "param_name",
            "interacts_with": ["other_param1", "other_param2"],
            "interaction_type": "synergistic|antagonistic|threshold",
            "implication": "What this means for calibration"
        }}
    ],
    "cross_pft_patterns": {{
        "generic_parameters": [
            {{
                "parameter": "param_name",
                "reason": "Why important for all PFTs",
                "calibration_advice": "Adjust carefully, affects all PFTs"
            }}
        ],
        "pft_specific_parameters": [
            {{
                "parameter": "param_name",
                "pft": "PFT9",
                "reason": "Why only important for this PFT"
            }}
        ]
    }},
    "edge_effects": [
        {{
            "parameter": "param_name",
            "current_bounds": [0.0, 1.0],
            "recommendation": "Expand upper bound to 1.5",
            "reason": "High sensitivity near upper bound"
        }}
    ],
    "knowledge_entries": [
        {{
            "type": "generic_discovery|site_specific|parameter_insight",
            "name": "short_identifier",
            "description": "What was learned",
            "confidence": 0.8,
            "scope": "generic|site_specific"
        }}
    ],
    "recommendations": [
        "Recommendation for diagnosis/hypothesis phases"
    ],
    "summary": "One-paragraph summary of key findings"
}}
```

Respond ONLY with the JSON object."""

        response = self.query(prompt)

        try:
            json_str = response.strip()
            if json_str.startswith("```"):
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
            result = json.loads(json_str)

            # Auto-record knowledge entries to memory if available
            if self.memory and result.get("knowledge_entries"):
                for entry in result["knowledge_entries"]:
                    entry_type = entry.get("type", "")
                    if entry_type in ["generic_discovery", "site_specific"]:
                        self.memory.add_discovery(
                            name=entry.get("name", f"sensitivity_insight_{output_var}"),
                            description=entry.get("description", ""),
                            mechanism=f"Identified from Morris sensitivity analysis of {output_var}",
                            affects=[output_var],
                            confidence=entry.get("confidence", 0.7),
                            source="morris_sensitivity_analysis"
                        )
                        logger.info(f"Auto-recorded sensitivity discovery: {entry.get('name')}")
                    elif entry_type == "parameter_insight":
                        # Add to parameter knowledge
                        param_name = entry.get("name", "unknown")
                        self.memory.add_parameter_knowledge(
                            parameter=param_name,
                            knowledge_type="sensitivity",
                            content=entry.get("description", ""),
                            confidence=entry.get("confidence", 0.7)
                        )
                        logger.info(f"Auto-recorded parameter insight: {param_name}")

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse sensitivity analysis response: {e}")
            logger.error(f"Response was: {response}")
            # Return minimal result
            return {
                "key_parameters": [],
                "interactions": [],
                "cross_pft_patterns": {"generic_parameters": [], "pft_specific_parameters": []},
                "edge_effects": [],
                "knowledge_entries": [],
                "recommendations": ["Unable to parse AI analysis"],
                "summary": "Analysis failed - check logs for details"
            }

    def check_proposed_modifications(self, modifications: List[Dict]) -> Dict:
        """
        Check proposed modifications against memory for potential issues.

        Args:
            modifications: List of proposed parameter modifications

        Returns:
            Dict with warnings and recommendations
        """
        if not self.memory:
            return {"warnings": [], "recommendations": [], "safe_to_proceed": True}

        warnings = []
        recommendations = []

        # Check against failed approaches
        do_not_repeat = self.memory.check_do_not_repeat(modifications)
        for match in do_not_repeat:
            warnings.append({
                "type": "DO_NOT_REPEAT",
                "modification": match["modification"],
                "matched_approach": match["matched_approach"]["approach"],
                "reason": match["warning"]
            })

        # Check parameter cautions
        param_names = [m.get("parameter", "") for m in modifications]
        cautions = self.memory.get_parameter_cautions(param_names)
        for param, param_cautions in cautions.items():
            for caution in param_cautions:
                warnings.append({
                    "type": "CAUTION",
                    "parameter": param,
                    "message": caution
                })

        # Check failed experiments with these parameters
        failed_exps = self.memory.get_failed_experiments(param_names)
        for exp in failed_exps[:3]:  # Limit to 3 most relevant
            recommendations.append({
                "type": "LEARN_FROM_FAILURE",
                "experiment": exp.get("id"),
                "lesson": exp.get("lesson", "No lesson recorded")
            })

        safe_to_proceed = not any(w["type"] == "DO_NOT_REPEAT" for w in warnings)

        return {
            "warnings": warnings,
            "recommendations": recommendations,
            "safe_to_proceed": safe_to_proceed
        }


# Example usage
if __name__ == "__main__":
    # Test the module
    logging.basicConfig(level=logging.INFO)

    # Check if API key is set
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY environment variable to test")
        exit(1)

    reasoning = ReasoningModule()

    # Test diagnosis
    test_results = {
        "leaf_pft7": 28.5,
        "leaf_pft9": 45.2,  # Should be ~125
        "leaf_pft10": 78.3,
        "froot_pft7": 165.4,
        "froot_pft9": 42.1,  # Should be ~187
        "froot_pft10": 295.6
    }

    test_targets = {
        "leaf_pft7": {"mean": 24.6, "uncertainty": 0.20},
        "leaf_pft9": {"mean": 124.7, "uncertainty": 0.20},
        "leaf_pft10": {"mean": 82.7, "uncertainty": 0.20},
        "froot_pft7": {"mean": 174.2, "uncertainty": 0.20},
        "froot_pft9": {"mean": 187.3, "uncertainty": 0.20},
        "froot_pft10": {"mean": 382.1, "uncertainty": 0.20}
    }

    test_sensitivity = {
        "leaf_pft9": [
            {"param": "mort_scalar_cstarvation_9", "mu_star": 0.45},
            {"param": "alloc_storage_cushion_9", "mu_star": 0.38}
        ]
    }

    print("Testing diagnosis...")
    diagnosis = reasoning.diagnose(test_results, test_targets, test_sensitivity, iteration=1)
    print(diagnosis.to_json())
