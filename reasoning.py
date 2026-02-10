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
from dataclasses import dataclass, asdict, fields
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


# =============================================================================
# DIAGNOSTIC TOOLS INVENTORY
# =============================================================================
# This inventory is included in AI prompts so Claude knows what scripts are
# available and can request specific diagnostics for deeper analysis.

DIAGNOSTIC_TOOLS_INVENTORY = """
## Available Diagnostic Tools

You can request specific diagnostic analyses by including them in your response.
The orchestrator will run these scripts and provide results in follow-up calls.

### Parameter Analysis

| Tool | Function | Use When |
|------|----------|----------|
| `check_edge_parameters` | Find parameters at Morris sampling bounds | Suspect parameter space is too narrow |
| `compare_case_parameters` | Compare parameters between good/bad cases | Want to find what makes best cases different |
| `read_case_parameters` | Get exact parameter values for a case | Need specific values for diagnosis |

### PFT Limitation Analysis

| Tool | Function | Use When |
|------|----------|----------|
| `diagnose_pft_limitations` | Full PFT diagnosis (allocation, nutrients, competition) | PFT underperforming targets |
| `analyze_allocation_dynamics` | Check L2FR and allocation responses | Suspect allocation imbalance |
| `analyze_nutrient_limitation` | Test N/P starvation hypotheses | Suspect nutrient limits growth |
| `analyze_light_competition` | Check inter-PFT shading effects | Suspect competition for light |

### Mortality & Collapse Analysis

| Tool | Function | Use When |
|------|----------|----------|
| `analyze_mortality` | Decompose mortality by cause (hydraulic, carbon starvation, fire) | Vegetation declining unexpectedly |
| `detect_collapse` | Find "Perfect Storm" patterns (rapid vegetation loss) | Suspect cascading failures |
| `detect_perfect_storm_pattern` | Check for multi-factor collapse signature | Multiple stressors combining |

### Nutrient Pool Analysis

| Tool | Function | Use When |
|------|----------|----------|
| `analyze_nutrient_pools` | P and N pool time series | Suspect nutrient depletion |
| `compare_uptake_vs_demand` | Check if uptake meets plant demand | Suspect uptake limitation |
| `extract_p_pools` / `extract_n_pools` | Get specific nutrient pool data | Need detailed nutrient dynamics |

### Nutrient Mass Balance

| Tool | Function | Use When |
|------|----------|----------|
| `extract_nutrient_budget` | Full N/P budget (all inputs, outputs, pools) | Need complete nutrient accounting |
| `calculate_budget_closure` | Check dPool/dt = Inputs - Outputs | Suspect mass imbalance or missing fluxes |
| `analyze_pft_competition` | PFT-level uptake shares and supply/demand | Suspect inter-PFT nutrient competition |
| `identify_nutrient_sinks` | Rank output pathways by magnitude | Need to find dominant nutrient loss paths |

### Target Comparison

| Tool | Function | Use When |
|------|----------|----------|
| `compare_biomass_targets` | Compare simulated vs observed values | Initial target assessment |
| `calculate_target_metrics` | Compute RE, RMSE, bias for targets | Quantify error patterns |

### Hypothesis Testing

| Tool | Function | Use When |
|------|----------|----------|
| `test_hypotheses` | Test multiple competing hypotheses with quantified metrics | Evaluating multiple explanations for a pattern |
| `test_single_hypothesis` | Test one specific hypothesis | Targeted hypothesis testing |
| `get_default_hypotheses` | Get common hypotheses for CNP allocation issues | Starting point for hypothesis testing |

### Carbon Balance Analysis

| Tool | Function | Use When |
|------|----------|----------|
| `analyze_carbon_balance` | Detect carbon deficit (cumulative GPP vs MR) | Suspecting carbon starvation or growth constraints |
| `detect_carbon_bottleneck` | Quick check for carbon bottleneck | Fast screening for C limitation |

### How to Request Diagnostics

In your JSON response, include:
```json
"requested_diagnostics": [
    {
        "tool": "check_edge_parameters",
        "reason": "Best case has extreme values, need to verify bounds",
        "priority": "high"
    },
    {
        "tool": "analyze_mortality",
        "reason": "PFT#10 biomass too low, suspect mortality issues",
        "priority": "medium",
        "args": {"pft_ids": [10]}
    }
]
```

The orchestrator will run requested diagnostics and include results in the next call.
"""

# Custom script template for hypothesis testing
CUSTOM_SCRIPT_TEMPLATE = '''
## Writing Custom Test Scripts

If NO existing diagnostic tool can test your hypothesis, you can write a custom Python script.
The script will be saved and executed by the orchestrator.

### Script Requirements

Your script must define a `test_hypothesis` function with this signature:

```python
def test_hypothesis(param_matrix, y_outputs, screening_data, config):
    """
    Test the hypothesis using existing ensemble data.

    Args:
        param_matrix: np.ndarray of shape (n_cases, n_params) - Morris parameter values
        y_outputs: dict mapping variable names to np.ndarray - Simulation outputs
            Example: {"leaf_biomass": array(...), "froot_biomass": array(...)}
        screening_data: dict with screening results
            Keys: "best_case", "best_cases", "n_cases_evaluated", etc.
        config: dict with configuration
            Keys: "param_names" (list), "pft_ids" (list), "use_case_dir" (str)

    Returns:
        dict with:
            "supported": bool - Whether hypothesis is supported
            "confidence": float - Confidence level (0-1)
            "evidence": dict - Supporting data/statistics
            "insights": list - Key findings
    """
    import numpy as np

    # Your analysis code here
    # Example: Check if high vmax_p correlates with better P uptake

    return {
        "supported": True,
        "confidence": 0.75,
        "evidence": {"correlation": 0.65, "p_value": 0.01},
        "insights": ["Found significant positive correlation"]
    }
```

### How to Specify a Custom Script

In `existing_data_test`, set method to "custom_script" and include the code:

```json
{
    "method": "custom_script",
    "description": "Test if P uptake scales with vmax_p across ensemble",
    "script_name": "test_p_uptake_scaling",
    "script_code": "def test_hypothesis(param_matrix, y_outputs, screening_data, config):\\n    import numpy as np\\n    # ... your code ..."
}
```

### Guidelines for Custom Scripts

1. **Keep it focused** - Test ONE specific aspect of the hypothesis
2. **Use numpy/scipy** - Standard scientific Python libraries are available
3. **Return structured results** - Always return the required dict format
4. **Handle edge cases** - Check for empty arrays, missing data
5. **No side effects** - Don't modify files or state outside the function
'''


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
                logger.info("RAG/GraphRAG retriever initialized successfully")
            except Exception as e:
                import traceback
                logger.warning(f"Could not initialize RAG retriever: {e}")
                logger.warning(f"RAG initialization traceback:\n{traceback.format_exc()}")
                print(f"Warning: RAG initialization failed: {e}")
                self.rag_retriever = None
        elif use_rag and HybridRetriever is None:
            logger.warning("RAG requested but HybridRetriever not available (import failed)")
            print("Warning: RAG requested but HybridRetriever import failed. Check dependencies.")

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

    def _load_template_schema(self, template_name: str) -> str:
        """Load JSON output schema from a reasoning template file.

        Reads the template and extracts the ```json ... ``` block from
        the '## JSON Output Schema' section.

        Args:
            template_name: Filename in templates/reasoning/ (e.g., 'phase3_diagnosis_template.md')

        Returns:
            JSON schema string, or empty string if not found
        """
        from pathlib import Path
        template_path = Path(__file__).parent / "templates" / "reasoning" / template_name
        if not template_path.exists():
            logger.debug(f"Template not found: {template_path}")
            return ""
        try:
            content = template_path.read_text()
            # Find the JSON Output Schema section
            schema_marker = "## JSON Output Schema"
            idx = content.find(schema_marker)
            if idx == -1:
                return ""
            # Extract the ```json ... ``` block after the marker
            section = content[idx:]
            json_start = section.find("```json")
            if json_start == -1:
                return ""
            json_start += len("```json")
            json_end = section.find("```", json_start)
            if json_end == -1:
                return ""
            return section[json_start:json_end].strip()
        except Exception as e:
            logger.warning(f"Failed to load template schema from {template_name}: {e}")
            return ""

    @staticmethod
    def _extract_json(response: str) -> dict:
        """Extract JSON from a Claude response, handling markdown wrapping."""
        json_str = response.strip()
        if json_str.startswith("```"):
            json_str = json_str.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]
        return json.loads(json_str)

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

{DIAGNOSTIC_TOOLS_INVENTORY}

## Previous Hypothesis Tests (if any)

If the results include `hypothesis_test_results`, these are from previous iterations where
hypotheses were tested using existing ensemble data (Skip Testing path). Use these insights:

1. **If hypothesis was SUPPORTED**: The mechanism is likely correct; refine parameter recommendations
2. **If hypothesis was NOT SUPPORTED**: Rule out that mechanism; consider alternatives
3. **Check the evidence**: Use quantitative findings to inform current diagnosis
4. **Build on insights**: Don't repeat failed hypotheses; incorporate lessons learned

## Diagnostic Process (follow these steps)
1. **Classify severity** for each failing target:
   - CRITICAL: >50% error, blocks progress
   - HIGH: 30-50% error, significant impact
   - MEDIUM: 20-30% error, needs attention
   - LOW: <20% error, within acceptable range

2. **Form 4-6 hypotheses BEFORE deep analysis.** Each hypothesis should:
   - State a specific FATES mechanism (PID_Controller, ECA_Competition, Storage_Allocation, etc.)
   - Predict which targets it affects
   - Be testable with parameter modifications

3. **For each hypothesis, present evidence FOR and AGAINST** using quantitative data from the results and sensitivity rankings.

4. **Rank root causes** by confidence and evidence strength.

5. **Provide a conceptual model** (ASCII diagram) showing the causal chain from root cause to failing targets.

6. Consider cross-PFT conflicts and shared parameter effects.

IMPORTANT: If the knowledge base shows failed approaches, DO NOT recommend those approaches.

## Response Format
Return a JSON object with this structure:
```json
{{
    "iteration": {iteration},
    "failing_targets": ["target1", "target2"],
    "severity_breakdown": {{
        "critical": ["targets with >50% error"],
        "high": ["targets with 30-50% error"],
        "medium": ["targets with 20-30% error"],
        "low": ["targets with <20% error"]
    }},
    "hypotheses": [
        {{
            "id": "H1",
            "statement": "Specific mechanism hypothesis",
            "mechanism": "FATES_Mechanism_Name",
            "evidence_for": ["Quantitative evidence supporting this"],
            "evidence_against": ["Evidence contradicting this"],
            "confidence": 0.8
        }}
    ],
    "root_causes": [
        {{
            "rank": 1,
            "cause": "Root cause description",
            "mechanism": "FATES_Mechanism_Name",
            "confidence": 0.85,
            "affected_targets": ["target1", "target2"]
        }}
    ],
    "likely_causes": [
        "Mechanistic explanation 1",
        "Mechanistic explanation 2"
    ],
    "parameter_recommendations": [
        {{
            "parameter": "param_name",
            "current_issue": "why this is a problem",
            "suggested_direction": "increase/decrease",
            "priority": 1,
            "caution": "potential side effects"
        }}
    ],
    "key_insights": [
        "Named insight (e.g., Triple Bottleneck Pattern)"
    ],
    "cross_pft_conflicts": [
        "Description of any shared parameter conflicts"
    ],
    "confidence": 0.85,
    "reasoning": "Summary of diagnosis logic including conceptual model",
    "requested_diagnostics": [
        {{
            "tool": "tool_name_from_inventory",
            "reason": "Why this diagnostic would help",
            "priority": "high/medium/low",
            "args": {{"optional": "arguments"}}
        }}
    ]
}}
```

**IMPORTANT**: If you need more data to form a confident diagnosis, use `requested_diagnostics`
to request specific diagnostic analyses. The orchestrator will run them and provide results.

Respond ONLY with the JSON object, no additional text."""

        response = self.query(prompt)

        # Parse response — filter to Diagnosis dataclass fields
        try:
            data = self._extract_json(response)
            known = {f.name for f in fields(Diagnosis)}
            return Diagnosis(**{k: v for k, v in data.items() if k in known})
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

## Hypothesis Generation Process (follow these steps)

1. **Consider at least 3 possible hypotheses** before selecting the best one for testing.
   For each, briefly note the mechanism, expected effect, and risk level.

2. **Select the BEST hypothesis** based on:
   - Highest expected impact on failing targets
   - Strongest mechanistic evidence from diagnosis
   - Lowest risk of cross-PFT degradation
   - Not previously failed (check failed approaches above)

3. **Assess risk** for the selected hypothesis:
   - LOW: PFT-specific parameter, well-understood mechanism
   - MEDIUM: Shared parameter or partial evidence
   - HIGH: Novel mechanism, potential for cascading effects

4. **Include what WON'T work** based on memory and reasoning.

5. **Name potential discoveries** to watch for during testing:
   - Allocation Paradox: uptake increase causes PID reallocation that reduces total growth
   - Mortality Trap: parameter change triggers carbon starvation mortality
   - Compensation Effect: one PFT gains at another's expense

## Design Guidelines
- Use CUMULATIVE design when mechanisms are sequential (A → B → C)
- Use FACTORIAL design when parameters may interact (P × N synergy)
- Only modify PFT-specific parameters to avoid cross-PFT conflicts
- Propose values within physically realistic bounds
- Include parameter bounds (min/max) and sensitivity rank where known

## Skip Testing: Test with Existing Data (IMPORTANT)

Before proposing new HPC experiments, consider if this hypothesis can be tested
using EXISTING Morris ensemble data. Set `test_with_existing: true` if ANY of these apply:

1. **Correlation check**: Can verify by comparing cases with different parameter values
   - Example: "Cases with high vmax_p should have higher P uptake"
2. **Threshold analysis**: Can filter existing screening results
   - Example: "Cases with l2fr > 2.0 should have better froot biomass"
3. **Edge parameter impact**: Already computed by diagnostic scripts
   - Example: "Parameters at upper bounds correlate with target failures"
4. **Mass balance analysis**: Can analyze existing simulation outputs
   - Example: "P uptake exceeds demand in failing cases"
5. **Custom analysis**: Write a Python script for novel analysis not covered above
   - Example: "Analyze P cycling dynamics across PFTs"

If `test_with_existing: true`, provide `existing_data_test` with:
- `method`: "correlation" | "threshold" | "comparison" | "diagnostic" | "custom_script"
- `description`: What to check
- `cases_to_compare`: Case IDs or selection criteria (for non-custom methods)
- `success_criterion`: What result confirms/refutes the hypothesis

**For custom_script method**, also provide:
- `script_name`: Short name for the script (e.g., "test_p_cycling")
- `script_code`: Python function code (see format below)

{CUSTOM_SCRIPT_TEMPLATE}

This saves HPC compute time by using data we already have!

## Response Format
Return a JSON object with this structure:
```json
{{
    "name": "Hypothesis Name (memorable, mechanistic)",
    "mechanism": "Detailed mechanistic explanation",
    "parameters": [
        {{
            "name": "fates_param_name",
            "pft": 9,
            "current": 0.787,
            "proposed": 0.30,
            "rationale": "Why this change should help",
            "bounds": [0.1, 1.0],
            "sensitivity_rank": 3
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
    "confidence": 0.75,
    "risk_level": "low",
    "potential_discoveries": [
        {{
            "name": "Discovery Name",
            "signature": "What to look for in results",
            "action_if_observed": "What to do if discovered"
        }}
    ],
    "wont_work": [
        {{
            "approach": "Approach that won't work",
            "why_fails": "Mechanistic reason",
            "alternative": "Better approach"
        }}
    ],
    "test_with_existing": false,
    "existing_data_test": null
}}
```

If hypothesis CAN be tested with existing data, set:
```json
{{
    "test_with_existing": true,
    "existing_data_test": {{
        "method": "comparison",
        "description": "Compare cases with high vs low vmax_p values",
        "cases_to_compare": {{"high_vmax_p": "top 10%", "low_vmax_p": "bottom 10%"}},
        "success_criterion": "High vmax_p cases have >20% higher P uptake"
    }}
}}
```

If you need a CUSTOM SCRIPT for novel analysis:
```json
{{
    "test_with_existing": true,
    "existing_data_test": {{
        "method": "custom_script",
        "description": "Analyze P cycling efficiency across PFTs",
        "script_name": "test_p_cycling_efficiency",
        "script_code": "def test_hypothesis(param_matrix, y_outputs, screening_data, config):\\n    import numpy as np\\n    # Get P uptake and demand data\\n    # Calculate cycling efficiency\\n    # Compare across PFTs\\n    return {{\\n        \\"supported\\": True,\\n        \\"confidence\\": 0.8,\\n        \\"evidence\\": {{\\"efficiency_ratio\\": 0.75}},\\n        \\"insights\\": [\\"PFT10 has lowest P cycling efficiency\\"]\\n    }}",
        "success_criterion": "P cycling efficiency < 0.5 indicates limitation"
    }}
}}
```

Respond ONLY with the JSON object."""

        response = self.query(prompt)

        # Parse response — filter to Hypothesis dataclass fields
        try:
            data = self._extract_json(response)
            known = {f.name for f in fields(Hypothesis)}
            return Hypothesis(**{k: v for k, v in data.items() if k in known})
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
            data = self._extract_json(response)
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

## Interpretation Process (follow these steps)

1. **Expected vs Actual comparison**: For each target, classify as:
   - CONFIRMED: result matches expected outcome (within 20%)
   - PARTIAL: result moves in right direction but less than expected
   - REJECTED: result moves in wrong direction or no change

2. **Cross-PFT impact analysis**: Did modifications for one PFT affect others?
   Create a mental table: PFT x Target showing improvement/degradation.

3. **Named discovery detection**: Watch for these known patterns:
   - Allocation Paradox: uptake increase causes PID to reallocate away from roots
   - Mortality Trap: parameter change triggers carbon starvation cascade
   - Compensation Effect: gains in one PFT come at another's expense
   - Storage Depletion: short-term improvement followed by long-term decline

4. **Next step recommendation**: Based on hypothesis status, recommend:
   - CONFIRMED → continue to convergence or test next hypothesis
   - PARTIAL → refine hypothesis with adjusted parameters
   - REJECTED → return to diagnosis with new insights

## Response Format
```json
{{
    "targets_improved": ["target1"],
    "targets_degraded": [],
    "hypothesis_status": "confirmed|partial|rejected",
    "expected_vs_actual": [
        {{
            "target": "target_name",
            "expected": 80.0,
            "actual": 68.0,
            "status": "PARTIAL",
            "improvement_pct": 52
        }}
    ],
    "cross_pft_impact": {{
        "affected_pfts": ["PFT10"],
        "degraded": false,
        "notes": "No cross-PFT degradation observed"
    }},
    "discoveries": [
        {{
            "name": "Discovery Name",
            "description": "What was discovered",
            "confidence": 0.9
        }}
    ],
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
            return self._extract_json(response)
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

## Lesson Extraction Process (follow these steps)

1. **Parameter category analysis**: Classify each modified parameter:
   - Allocation (PID, storage cushion, leaf-to-froot ratio)
   - Nutrient uptake (vmax_p, vmax_nh4, vmax_no3, ECA parameters)
   - Storage (store_ratio, storage_cushion)
   - Mortality (cstarvation scalar, hydraulic parameters)
   - Phenology (GDD threshold, chilling)

2. **Identify fundamental constraints**: What does this experiment reveal about
   the model's structural limitations? E.g., "Cannot increase vmax_p > 2x
   without storage buffer" or "PID Kp must be < 0.4 for stressed PFTs"

3. **Mechanism synthesis (before/after understanding)**:
   - Before this experiment, we thought: ...
   - After this experiment, we now understand: ...

4. **Is this a significant discovery?** A DISCOVERY should be recorded if:
   - The result reveals a non-obvious mechanism (feedback loops, parameter interactions)
   - The result contradicts expectations in an informative way
   - The insight would help prevent future mistakes

5. **If failed, should this approach be added to "do not repeat" list?**

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
            result = self._extract_json(response)

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

## Screening Analysis Process (follow these steps)

1. **PFT-by-PFT performance summary**: For each PFT, report:
   - Number of cases within observational uncertainty
   - Median error direction (overestimated vs underestimated)
   - Quality assessment (GOOD / MODERATE / POOR / CRITICAL)

2. **Target bias pattern analysis**: For each target, classify:
   - Bias direction: UNDEREST (model too low) / OVEREST (model too high) / near_target
   - Bias consistency: how consistent is the direction across all parameter sets?

3. **Edge parameter identification**: Flag parameters at sampling bounds
   in top cases. These suggest the model "wants" values outside the tested range.

4. **Error Patterns**: Which targets fail most often? Are failures correlated?
5. **Success Patterns**: What do the top 10 cases have in common?
6. **PFT Trade-offs**: Do improvements in one PFT come at the cost of another?
7. **Priority Targets**: Which targets should diagnosis focus on?
8. **Potential Mechanisms**: What FATES mechanisms might explain the patterns?

## Response Format
```json
{{
    "pft_performance": {{
        "PFT_ID": {{
            "name": "PFT name",
            "cases_within_uncertainty": 123,
            "median_error": -0.45,
            "quality": "POOR|MODERATE|GOOD|CRITICAL"
        }}
    }},
    "target_bias": {{
        "target_name": {{
            "bias": -0.46,
            "type": "UNDEREST|OVEREST|near_target",
            "consistency": 0.92
        }}
    }},
    "edge_parameters": [
        {{
            "parameter": "param_name",
            "pft": 10,
            "at_bound": "upper|lower",
            "implication": "Model wants higher/lower values"
        }}
    ],
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
            result = self._extract_json(response)

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

## Sensitivity Analysis Process (follow these steps)

1. **Key Parameters**: Which parameters have the strongest influence? What mechanisms do they control?
   For each top parameter, note the FATES mechanism (PID_Controller, ECA_Competition, etc.).

2. **Parameter Interactions**: High σ/μ* ratio indicates non-linear effects or interactions.
   - Which parameters interact?
   - What does this mean for calibration strategy?
   - Are interactions synergistic (combined effect > sum) or antagonistic?

3. **Cross-PFT Comparison**: Create a comparison table showing:
   - Which parameters are in the top 10 for ALL PFTs (generic importance)
   - Which parameters are in the top 10 for only ONE PFT (PFT-specific)
   - Are the same mechanisms dominant across PFTs or do different PFTs have different bottlenecks?

4. **Edge Effects**: Parameters with high μ* near sampling bounds may need:
   - Expanded ranges in next iteration
   - Caution about extrapolation

5. **Calibration Strategy Implications**:
   - Which parameters should be tuned PFT-by-PFT vs globally?
   - What order should parameters be tuned in (based on interactions)?

6. **Knowledge Base Entries**: What should be recorded for future reference?
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
            result = self._extract_json(response)

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
