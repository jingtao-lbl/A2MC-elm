#!/usr/bin/env python3
"""
Reasoning Module Phase Methods

All phase-specific reasoning methods for ReasoningModule:
- diagnose(): Phase 3 - Root cause analysis
- generate_hypothesis(): Phase 4 - Hypothesis generation
- design_experiments(): Phase 4 - Experiment design
- interpret_results(): Phase 5/6 - Result interpretation
- extract_lesson(): Phase 6 - Lesson extraction
- analyze_screening_results(): Phase 2 - Screening analysis
- analyze_sensitivity_results(): Phase 1 - Sensitivity analysis
- check_proposed_modifications(): Safety check against memory
- generate_session_report(): End-of-session comprehensive report generation

These methods are attached to ReasoningModule in reasoning/__init__.py.

Author: Jing Tao with Claude
"""

import json
import logging
import os
from dataclasses import fields
from typing import List, Dict, Optional

from reasoning.schemas import Diagnosis, Hypothesis, Experiment
from reasoning.prompts import DIAGNOSTIC_TOOLS_INVENTORY, CUSTOM_SCRIPT_TEMPLATE

logger = logging.getLogger(__name__)


def _build_round_context_block() -> str:
    """Build a Calibration Round Context block for Phase 3/4 prompts.

    Explicitly tells the AI:
      1. Which calibration round is currently active (scheme, size, overrides)
      2. Which round's Y matrix backs any ensemble correlations cited
         (same round for morris/sobol/lhs; source_round for subset_replay)
      3. That hypotheses target the ACTIVE round's protocol + parameters,
         but ensemble correlation evidence must cite the DATA round.

    Reads active round from A2MC_CALIBRATION_ROUND env var (kept in sync by
    orchestrator.py main loop). Returns empty string if the round config
    cannot be loaded (e.g. running outside a sourced use_case), so the
    prompt still builds without round context rather than crashing.
    """
    try:
        from tools.round_paths import load_round_paths, resolve_ensemble_y_matrix_round
        resolved = resolve_ensemble_y_matrix_round(round_num=None)
    except Exception as e:
        logger.debug(f"Round context unavailable: {e}")
        return ""

    active_round = resolved['active_round']
    data_round = resolved['data_round']
    data_paths = resolved['data_round_paths']

    try:
        active_paths = load_round_paths(active_round)
    except Exception:
        active_paths = {}

    active_scheme = active_paths.get('sampling_scheme', 'unknown')
    active_overrides = active_paths.get('overrides') or {}
    source_round = active_paths.get('source_round')

    # Summarize active round overrides concisely
    overrides_line = ""
    if active_overrides:
        kvs = [f"`{k}={v}`" for k, v in active_overrides.items()]
        overrides_line = f"- **Overrides active**: {', '.join(kvs)}\n"

    # Distinct copy depending on whether data round == active round
    if data_round == active_round:
        provenance_block = (
            f"Ensemble correlations (μ*, σ, cross-case stats) in the data "
            f"below come from **round {active_round}'s own {active_scheme} "
            f"ensemble**. You can cite case numbers and ensemble statistics "
            f"directly without cross-round caveats."
        )
    else:
        # Typically subset_replay fallback to source_round
        src_scheme = data_paths.get('sampling_scheme', 'morris')
        provenance_block = (
            f"**IMPORTANT — cross-round provenance:** The active round "
            f"({active_round}) uses `sampling_scheme={active_scheme}` and "
            f"does NOT produce its own sensitivity Y matrix. Any ensemble "
            f"correlations, μ* values, case-ID references (e.g. \"Case "
            f"#4700\"), or \"across N cases\" claims in the data below "
            f"come from **round {data_round}'s {src_scheme} ensemble** "
            f"(the source round that round {active_round} was sampled "
            f"from).\n\n"
            f"When you cite such evidence in hypotheses or diagnoses, you "
            f"MUST label it as round {data_round} data (e.g. \"Morris "
            f"correlation from round {data_round} shows r=-0.26 between "
            f"l2fr_ini_9 and PFT9 leaf\"). Do NOT write \"across R"
            f"{active_round}\" or \"in the R{active_round} ensemble\" "
            f"when the underlying statistic is from round {data_round}. "
            f"Your EXPERIMENTS, however, target the ACTIVE round "
            f"({active_round})'s parameters and protocol — including any "
            f"overrides listed above."
        )

    src_line = (
        f"- **Source round**: {source_round}\n" if source_round is not None else ""
    )

    return (
        "## Calibration Round Context\n"
        f"- **Active round**: {active_round} "
        f"(sampling_scheme=`{active_scheme}`)\n"
        f"{src_line}"
        f"{overrides_line}"
        f"- **Ensemble data round**: {data_round} "
        f"(sampling_scheme=`{data_paths.get('sampling_scheme', '?')}`)\n"
        "\n"
        f"{provenance_block}\n\n"
    )


def _build_active_mode_block() -> str:
    """Build an Active Run Configuration block for Phase 3/4 prompts (Doc 20).

    Reads simulation mode from environment via `ConfigMode.from_env()` and
    renders a 3-5 line block declaring which features are ON / OFF for
    this run. The LLM uses this to self-correct on retrieved content that
    spans multiple modes.

    Returns empty string if `tools.config` is not importable (e.g. running
    outside a sourced site config), so prompts still build without the
    block rather than crashing.
    """
    try:
        from tools.config import ConfigMode
        mode = ConfigMode.from_env()
    except Exception as e:
        logger.debug(f"Mode block unavailable: {e}")
        return ""
    return mode.to_prompt_block() + "\n\n"


def _build_sensitivity_summary(sensitivity_rankings: Dict) -> str:
    """Build a concise human-readable summary of Morris sensitivity rankings.

    Handles both nested {output: {PFT: [params]}} and flat {output: [params]} formats.
    Returns a Markdown table per output variable showing top 5 params per PFT.
    """
    if not sensitivity_rankings:
        return "*No sensitivity rankings available.*"

    lines = []
    for output_var, rankings in sensitivity_rankings.items():
        lines.append(f"### {output_var}")
        if isinstance(rankings, dict):
            # Nested: {PFT: [params]}
            for pft_label, params in rankings.items():
                if not isinstance(params, list) or not params:
                    continue
                top5 = params[:5]
                header = f"**{pft_label}**: "
                entries = []
                for p in top5:
                    name = p.get('parameter', p.get('param', '?'))
                    mu_star = p.get('mu_star', 0)
                    ptype = p.get('type', '')
                    entries.append(f"`{name}` (μ*={mu_star:.3f}, {ptype})")
                lines.append(header + ", ".join(entries))
        elif isinstance(rankings, list):
            # Flat: [params]
            top5 = rankings[:5]
            entries = []
            for p in top5:
                name = p.get('parameter', p.get('param', '?'))
                mu_star = p.get('mu_star', 0)
                entries.append(f"`{name}` (μ*={mu_star:.3f})")
            lines.append(", ".join(entries))
        lines.append("")

    return "\n".join(lines)


def diagnose(self, results: Dict, targets: Dict,
             sensitivity_rankings: Dict, iteration: int,
             diagnostic_images: Optional[List[str]] = None) -> Diagnosis:
    """
    Analyze why calibration is failing.

    Args:
        results: Current simulation results by target
        targets: Validation targets with uncertainties
        sensitivity_rankings: Parameter sensitivity rankings (from Morris/Sobol/etc.)
        iteration: Current workflow iteration
        diagnostic_images: Optional list of paths to diagnostic PNG figures.
            When provided, figures are sent to Claude API as images for
            multimodal analysis (PFT overviews, mortality, P mass balance).

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

    # Get memory context if available (site-specific + generic)
    memory_context = ""
    if self.memory and failing_targets:
        memory_context = self.memory.get_relevant_context(failing_targets)
    # Also query generic (framework-level) knowledge for broader discoveries
    if self.generic_memory and failing_targets:
        generic_context = self.generic_memory.get_relevant_context(failing_targets)
        if generic_context:
            memory_context = (memory_context or "") + "\n" + generic_context
    if memory_context:
        memory_context = f"""## Adaptive Memory Context (from previous calibration work)
{memory_context}

"""

    # Get RAG context for relevant parameters and outputs
    rag_context = ""
    targeted_param_context = ""
    # Extract parameter names from sensitivity rankings
    # Rankings can be nested: {output: {PFT: [params]}} or flat: {output: [params]}
    param_names = []
    for output_rankings in sensitivity_rankings.values():
        if isinstance(output_rankings, dict):
            for pft_params in output_rankings.values():
                if isinstance(pft_params, list):
                    param_names.extend([p.get('param', p.get('parameter', ''))
                                       for p in pft_params[:5]])
        elif isinstance(output_rankings, list):
            param_names.extend([p.get('param', p.get('parameter', ''))
                               for p in output_rankings[:5]])
    param_names = list(set(p for p in param_names if p))[:15]
    # Map target names to output variables
    output_names = [f"FATES_{t.upper().replace('_', 'C_')}" for t in results.keys()]

    if self.rag_retriever:
        rag_context = self._get_rag_context(
            parameters=param_names[:10],
            outputs=output_names[:6],
            mechanisms=['PID_Controller', 'ECA_Competition', 'Storage_Allocation'],
            query="calibration diagnosis nutrient limitation biomass allocation"
        )
        # Get targeted parameter/output definitions (replaces raw CDL injection)
        targeted_param_context = self._get_targeted_param_context(
            param_names=param_names,
            output_names=output_names[:6],
            mechanisms=['PID_Controller', 'ECA_Competition', 'Storage_Allocation']
        )

    # Build concise sensitivity summary so AI focuses on high-sensitivity params
    sensitivity_summary = _build_sensitivity_summary(sensitivity_rankings)

    # Extract cross-round comparison context (subset_replay rounds) early so
    # the figures-detail block below can reference it without NameError.
    _cross_round_ctx = results.pop("cross_round_comparison", None)

    # Build diagnostic figures prompt section (outside f-string to avoid triple-quote nesting)
    if diagnostic_images:
        _figures_header = "The following diagnostic figures are attached as images. Analyze them carefully:"
        _figures_detail = (
            "\n- **PFT overview plots**: Check L2FR oscillation patterns (PID instability), biomass trends,"
            "\n  nutrient limitation timing, allocation dynamics. Oscillations with amplitude >100 indicate PID instability."
            "\n- **Mortality components**: Which mortality type dominates? When do spikes occur relative to growing season?"
            "\n- **P mass balance**: Are P pools accumulating/depleting? Is uptake matching demand?"
            "\n- **Carbon balance**: Is GPP sufficient to cover maintenance respiration? When do deficits occur?"
            "\n"
            "\nIncorporate visual observations into your diagnosis. Reference specific temporal patterns,"
            "\noscillation severity, and anomalies visible in the plots."
            "\n"
            "\n**IMPORTANT**: Populate `visual_observations` FIRST in your response (it appears"
            "\nearly in the JSON format). Provide a STRUCTURED analysis for each figure."
            "\nEach entry must have a `figure` keyword (e.g., `pft7_diagnosis`, `pft9_diagnosis`,"
            "\n`pft10_diagnosis`, `mortality_components`, `p_mass_balance`) and an `analysis` string"
            "\ndescribing what you see. For two-case comparisons, prefix with case role"
            "\n(e.g., `best_case_pft7_diagnosis`, `lowest_cost_pft10_diagnosis`)."
        )
    else:
        _figures_header = "No diagnostic figures attached for this iteration."
        _figures_detail = ""

    # Add cross-round figure descriptions if present
    if _cross_round_ctx:
        _figures_detail += (
            "\n- **Cross-round comparison plots**: Delta-biomass boxplots show R4-R3 changes per target. "
            "Cost scatter shows whether R4 improves or degrades overall. Satisfaction bars show "
            "target gains/losses. Use these to assess the P-limitation hypothesis quantitatively."
        )

    # Extract previous phase log so AI can see the full narrative from the prior phase
    _previous_phase_log = results.pop("previous_phase_log", "")

    # Extract previous phase insights from results so they appear as a dedicated
    # prompt section rather than buried in the JSON blob
    _previous_phase_insights = results.pop("previous_phase_insights", "")

    # Extract evidence ledger context (Iter 2+ hypothesis-driven diagnosis)
    _evidence_ledger_ctx = results.pop("evidence_ledger_context", "")

    # Build cross-round comparison section (extracted earlier; see _cross_round_ctx)
    _cross_round_section = ""
    if _cross_round_ctx:
        xr = _cross_round_ctx
        _cross_round_section = f"""## CROSS-ROUND COMPARISON: R{xr.get('source_round', '?')} vs R{xr.get('target_round', '?')}

This round is a **controlled experiment**: the same {xr.get('n_cases_paired', '?')} parameter sets
were run in both R{xr.get('source_round', '?')} and R{xr.get('target_round', '?')}, differing ONLY in:
**{xr.get('override_description', 'one parameter override')}**.

### Per-Target Biomass Changes (R{xr.get('target_round', '?')} minus R{xr.get('source_round', '?')})
{xr.get('per_target_summary', '(not available)')}

### Target Satisfaction Changes
{xr.get('satisfaction_summary', '(not available)')}

### Rank Correlation
Spearman rho between R{xr.get('source_round', '?')} and R{xr.get('target_round', '?')} composite cost: {xr.get('rank_correlation', '?')}

### Cases Missing (R{xr.get('target_round', '?')} crashed)
{xr.get('n_cases_tgt_missing', 0)} out of {xr.get('n_cases_total', '?')} R{xr.get('target_round', '?')} cases crashed (likely P mass balance abort).

### Interpretation Questions
1. Does removing P limitation rescue PFT10 biomass?
2. Which PFTs benefit vs degrade when P is no longer limiting?
3. Do the crashed R{xr.get('target_round', '?')} cases share parameter characteristics?
4. Is the rank ordering preserved (high rho) or reshuffled (low rho)?
5. What does this imply about the dominant nutrient limitation bottleneck?

**IMPORTANT**: This is the strongest evidence for or against the P-limitation hypothesis.
Integrate these quantitative results into your root cause analysis.
"""

    # Extract diagnostic data summary for prominent placement
    # (prevents AI from hallucinating numbers that contradict diagnostic tool output)
    _diag_summary = ""
    diag_ctx = results.get("diagnostic_context", {})
    if diag_ctx:
        edge_sum = diag_ctx.get("edge_summary", "")
        redesign = diag_ctx.get("redesign_candidates", [])
        _diag_summary = f"""## Diagnostic Tool Results (VERIFIED -- cite these, do NOT fabricate numbers)

{edge_sum if edge_sum else "No edge parameters detected."}

Redesign candidates: {len(redesign)}
{chr(10).join(f'- {r}' for r in redesign[:10]) if redesign else '(none)'}

CRITICAL: The above edge parameter counts come from actual diagnostic scripts.
When you reference "parameters at bounds" in your diagnosis, use ONLY the counts above.
DO NOT fabricate numbers. If the tool reports 0 edge parameters, do not claim otherwise.
"""

    _round_ctx = _build_round_context_block()
    _mode_ctx = _build_active_mode_block()

    prompt = f"""Analyze these ELM-FATES calibration results and diagnose why targets are not being met.

{_round_ctx}{_mode_ctx}{rag_context}{memory_context}{targeted_param_context}

{self._param_list_context}

{_previous_phase_log}

{_previous_phase_insights}

{_evidence_ledger_ctx}

{_diag_summary}

{_cross_round_section}

## Current Results (simulated values in g C/m²)
{json.dumps(results, indent=2)}

## Validation Targets (observed values with ±20% uncertainty)
{json.dumps(targets, indent=2)}

## Sensitivity Rankings (top parameters by importance)

**IMPORTANT: Focus your hypotheses on parameters with HIGH Morris sensitivity (μ*).
Parameters with low μ* are unlikely to be primary drivers of model-data mismatch.**

{sensitivity_summary}

<details>
<summary>Full sensitivity rankings (JSON)</summary>

{json.dumps(sensitivity_rankings, indent=2)}
</details>

{DIAGNOSTIC_TOOLS_INVENTORY}

## Diagnostic Figures

{_figures_header}
{_figures_detail}

## Comparative Case Analysis

Reference cases are provided in the results:
- **best_case**: Case with most targets satisfied within top 10 by cost (tiebreak: lowest cost)
- **lowest_cost_case**: Case with minimum composite RMSRE
- **high_satisfaction_cases** (if present): Other top-10 cases that satisfy the SAME number of
  targets as best_case. These are alternative starting points — they may satisfy DIFFERENT
  targets, offering complementary strengths.

Analyze ALL reference cases (not just best_case):
1. Which targets does each case satisfy under ±20% tolerance?
2. Which targets does each case satisfy under std-range tolerance (obs ± obs_std)?
3. Do the high-satisfaction alternatives satisfy different targets than best_case?
   If so, identify which case provides the best foundation for the failing targets.
4. What parameter differences might explain their complementary strengths?
5. **Select 1-2 base cases** for experiment design. Output them in `comparative_analysis.selected_base_cases`.
   For each, specify the case_id, rationale, targets it already satisfies, and targets to fix.
   If only best_case is needed, include just that one. If an alternative has complementary
   strengths (satisfies different targets), include it as a second base case.

IMPORTANT: Always state the base case number (e.g., "Case #86") when discussing results.
Your diagnosis and parameter recommendations should be grounded in a specific base case.

If results include `std_range_evaluation`, use it to assess whether the "lowest cost" case
might actually be closer to a globally acceptable solution despite failing some ±20% checks.

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

2. **Mechanism Inventory (REQUIRED):** Before deep analysis, enumerate ALL plausible
   mechanisms that could explain the failures. For each mechanism, rate likelihood
   (high/medium/low) and note what evidence would confirm/refute it. Format as a table:

   | # | Mechanism | Likelihood | Confirming Evidence | Refuting Evidence |
   |---|-----------|------------|--------------------|--------------------|

   Consider at least these mechanism categories:
   - Nutrient limitation (P starvation, N competition, soil chemistry)
   - Carbon balance (GPP vs respiration, storage depletion)
   - Allocation dynamics (PID controller, L2FR, storage priorities)
   - Competition (light, nutrient, PFT interactions)
   - Mortality (C starvation, hydraulic, background)
   - Phenology (timing, growing season length)
   - Simulation protocol (spinup strategy, nutrient supplementation during spinup)

   **Beyond parameter changes:** If the root cause is systemic (e.g., chronic P limitation
   across ALL PFTs), consider whether a simulation protocol change might be needed.
   Available protocol settings (in a2mc_config.sh) and their CURRENT values:
   - A2MC_ADSP_SUPLPHOS={os.environ.get('A2MC_ADSP_SUPLPHOS', '?')} / A2MC_RGSP_SUPLPHOS={os.environ.get('A2MC_RGSP_SUPLPHOS', '?')} / A2MC_TRANS_SUPLPHOS={os.environ.get('A2MC_TRANS_SUPLPHOS', '?')}: nutrient supplementation per phase ('ALL' or 'NONE')
   - A2MC_ADSP_SUPLNITRO={os.environ.get('A2MC_ADSP_SUPLNITRO', '?')} / A2MC_RGSP_SUPLNITRO={os.environ.get('A2MC_RGSP_SUPLNITRO', '?')} / A2MC_TRANS_SUPLNITRO={os.environ.get('A2MC_TRANS_SUPLNITRO', '?')}: same for nitrogen
   - A2MC_ADSP_NYEARS_AD_CARBON_ONLY={os.environ.get('A2MC_ADSP_NYEARS_AD_CARBON_ONLY', '?')}: carbon-only years before nutrient cycling in AD spinup
   **IMPORTANT constraints on protocol changes:**
   - Nutrient supplementation (SUPLPHOS/SUPLNITRO) is ONLY valid during SPINUP phases (ADSP, RGSP)
     to help vegetation establish. It must be OFF during TRANSIENT (TRANS) because transient runs
     represent real ecosystem conditions. Enabling supplementation during TRANS is equivalent to
     a fertilization experiment, which is not what we are calibrating for.
   - If the AI diagnoses a nutrient supply structural failure, the fix should be in SPINUP protocol
     (ADSP/RGSP supplementation or longer spinup), parameter tuning (uptake kinetics, stoichiometry),
     or soil initial conditions — NOT transient-phase supplementation.
   Protocol changes require a full re-spinup (Phase 0 redesign). Use "protocol_recommendations" in the response.

3. **For each mechanism in the inventory, present evidence FOR and AGAINST** using
   quantitative data from the results and sensitivity rankings.

4. **Rank root causes** by confidence and evidence strength.

5. **Provide a conceptual model** (ASCII diagram) showing the causal chain from root cause to failing targets.

6. Consider cross-PFT conflicts and shared parameter effects.

7. **Identify which mechanisms are independent vs interacting.** Some mechanisms may
   form a causal chain (e.g., soil P bottleneck → P starvation → PID reallocation →
   biomass collapse). Note these chains — they require coordinated, not isolated, fixes.

IMPORTANT: If the knowledge base shows failed approaches, DO NOT recommend those approaches.

## Response Format
Return a JSON object with this structure. IMPORTANT: Required fields appear FIRST.
Write them before the verbose optional sections to avoid truncation.
```json
{{
    "iteration": {iteration},
    "confidence": 0.85,
    "reasoning": "Summary of diagnosis logic including conceptual model",
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
            "priority": 1,
            "caution": "potential side effects"
        }}
    ],
    "protocol_recommendations": [
        {{
            "setting": "A2MC config variable name (e.g., A2MC_RGSP_SUPLPHOS)",
            "current_value": "current value",
            "proposed_value": "proposed value",
            "rationale": "why this protocol change is needed",
            "requires_respin": true,
            "priority": 1
        }}
    ],
    "cross_pft_conflicts": [
        "Description of any shared parameter conflicts"
    ],
    "key_insights": [
        "Named insight (e.g., Triple Bottleneck Pattern)"
    ],
    "severity_breakdown": {{
        "critical": ["targets with >50% error"],
        "high": ["targets with 30-50% error"],
        "medium": ["targets with 20-30% error"],
        "low": ["targets with <20% error"]
    }},
    "root_causes": [
        {{
            "rank": 1,
            "cause": "Root cause description",
            "mechanism": "FATES_Mechanism_Name",
            "confidence": 0.85,
            "affected_targets": ["target1", "target2"]
        }}
    ],
    "comparative_analysis": {{
        "best_case_id": null,
        "lowest_cost_case_id": null,
        "recommended_starting_case": null,
        "rationale": "Why this case is the better starting point",
        "selected_base_cases": [
            {{
                "case_id": 86,
                "rationale": "Why this case was selected as a base for experiments",
                "targets_satisfied": ["targets this case already meets"],
                "targets_to_fix": ["targets to improve from this starting point"]
            }}
        ]
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
    "visual_observations": [
        {{
            "figure": "pft7_diagnosis",
            "analysis": "Description of key patterns observed in this PFT7 figure"
        }}
    ],
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

**IMPORTANT**: All quantitative claims must be supported by the data provided.
If the Diagnostic Tool Results show 0 edge parameters, do NOT claim "X parameters at bounds."
When referencing specific parameter values or edge cases, always cite the case ID
(e.g., "Case #322 has vmax_ptase at lower bound"). Generic claims like "parameters
are at bounds" without case attribution are not acceptable.

Respond ONLY with the JSON object, no additional text."""

    # Use multimodal query if diagnostic images are provided
    # Multimodal diagnosis needs extra output tokens: 10 images + figure analysis
    # + full diagnosis JSON. 12288 tokens avoids truncation that drops fields
    # near the end of the response (e.g., visual_observations, requested_diagnostics).
    # Diagnosis JSON is large: severity, root_causes, hypotheses with evidence,
    # reasoning, comparative_analysis, visual_observations, requested_diagnostics.
    # Configurable via A2MC_AI_DIAG_MAX_TOKENS (default 16384).
    _diag_tokens = int(os.environ.get("A2MC_AI_DIAG_MAX_TOKENS", "16384"))
    if diagnostic_images:
        response = self.query_with_images(prompt, diagnostic_images, max_tokens=_diag_tokens)
    else:
        response = self.query(prompt, max_tokens=_diag_tokens)

    # Parse response — filter to Diagnosis dataclass fields
    try:
        data = self._extract_json(response)
        known = {f.name for f in fields(Diagnosis)}
        filtered = {k: v for k, v in data.items() if k in known}

        # Sanitize None values in list/dict fields. Truncated JSON repair
        # can leave fields as explicit None (e.g., "failing_targets": null),
        # which passes the "key in filtered" check but breaks downstream code
        # that expects iterable types.
        _list_fields = ('failing_targets', 'likely_causes', 'parameter_recommendations',
                        'cross_pft_conflicts', 'requested_diagnostics',
                        'visual_observations', 'protocol_recommendations')
        _dict_fields = ('comparative_analysis',)
        for fname in _list_fields:
            if fname in filtered and filtered[fname] is None:
                filtered[fname] = []
        for fname in _dict_fields:
            if fname in filtered and filtered[fname] is None:
                filtered[fname] = {}

        # Fill in required fields if missing (truncation recovery)
        _required_defaults = {
            'iteration': iteration,
            'failing_targets': [],
            'likely_causes': [],
            'parameter_recommendations': [],
            'cross_pft_conflicts': [],
            'confidence': 0.5,
            'reasoning': '',
        }
        for key, default in _required_defaults.items():
            if key not in filtered:
                logger.warning(f"Diagnosis response missing '{key}' — filling default "
                               f"(likely max_tokens truncation)")
                filtered[key] = default
        return Diagnosis(**filtered)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse diagnosis response: {e}")
        logger.error(f"Response was: {response}")
        raise


def _build_alt_case_params_context(self, screening_data: Dict,
                                   best_case_params: Dict[str, float],
                                   include_set: set,
                                   best_case_id) -> str:
    """Build parameter context for high-satisfaction alternative cases.

    For each alternative, shows only parameters that DIFFER from best_case
    and which targets each case satisfies vs fails. This keeps the prompt
    concise while giving the AI the data to design per-base-case experiments.

    Args:
        screening_data: Full screening data (has comparative_analysis from orchestrator)
        best_case_params: Parameter values for best_case (shorthand → value)
        include_set: Set of shorthand param names to include
        best_case_id: Best case ID for labeling

    Returns:
        Prompt context string (may be empty if no alternatives exist)
    """
    # Get comparative analysis with high_satisfaction_cases and param diffs
    # This is passed through diagnosis_input → screening_results in the orchestrator
    comp = screening_data.get('_comparative_analysis', {})
    if not comp:
        # Also check if it was stored at top level (different code paths)
        comp = {}

    # Build candidate list (union of three sources, in priority order):
    #   1. high_satisfaction_cases — top-10 cases tying best_case on n_satisfied
    #   2. lowest_cost_case — case with minimum composite RMSRE in ensemble
    #   3. _selected_base_cases — cases the diagnosis AI explicitly selected
    #      (may be outside both above sets if they have unique strengths,
    #       e.g., highest PFT10 leaf despite lower overall n_satisfied)
    high_sat = comp.get('high_satisfaction_cases', [])
    lowest_cost = comp.get('lowest_cost_case', {})
    selected_diag = screening_data.get('_selected_base_cases', [])

    seen_ids = {best_case_id}
    candidates = []  # list of (case_id, comparative_eval_or_none)

    # 1. high_satisfaction_cases (have full per_target evaluation)
    for alt in high_sat:
        alt_id = alt.get('case_id')
        if alt_id and alt_id not in seen_ids:
            candidates.append((alt_id, alt))
            seen_ids.add(alt_id)

    # 2. lowest_cost_case (also has full per_target evaluation)
    lc_id = lowest_cost.get('case_id')
    if lc_id and lc_id not in seen_ids:
        # Tag it so the prompt can label it appropriately
        lc_with_tag = dict(lowest_cost)
        lc_with_tag['_is_lowest_cost'] = True
        candidates.append((lc_id, lc_with_tag))
        seen_ids.add(lc_id)

    # 3. Diagnosis-selected cases not already in above sets
    for sel in selected_diag:
        sel_id = sel.get('case_id')
        if sel_id and sel_id not in seen_ids:
            # No comparative eval for this case (it's outside top-by-n_satisfied
            # and not the lowest cost), but the AI selected it for a reason.
            candidates.append((sel_id, {'_diagnosis_rationale': sel.get('rationale', ''),
                                        '_targets_to_fix': sel.get('targets_to_fix', []),
                                        '_targets_satisfied': sel.get('targets_satisfied', [])}))
            seen_ids.add(sel_id)

    if not candidates:
        return ""

    sections = []
    for alt_id, alt in candidates:
        # Load this case's full parameter values
        alt_params = self._load_base_case_parameters(int(alt_id))
        if not alt_params:
            continue

        # Which targets each case satisfies
        alt_targets_met = []
        alt_targets_failed = []
        best_targets_met = []
        best_targets_failed = []

        best_eval = comp.get('best_case', {}).get('per_target', {})
        alt_eval = alt.get('per_target', {})

        if alt_eval:
            # high_satisfaction_cases path: full per_target evaluation
            for tname in alt_eval:
                if alt_eval[tname].get('within_20pct'):
                    alt_targets_met.append(tname)
                else:
                    alt_targets_failed.append(tname)
        else:
            # diagnosis-selected path: use AI's targets_satisfied/targets_to_fix
            alt_targets_met = alt.get('_targets_satisfied', [])
            alt_targets_failed = alt.get('_targets_to_fix', [])

        for tname in best_eval:
            if best_eval[tname].get('within_20pct'):
                best_targets_met.append(tname)
            else:
                best_targets_failed.append(tname)

        # Build diff lines — only include params in include_set that differ
        diff_lines = []
        for pname in sorted(include_set):
            if pname in alt_params and pname in best_case_params:
                bval = best_case_params[pname]
                aval = alt_params[pname]
                if bval != aval:
                    diff_lines.append(f"  {pname}: {aval}  (vs {bval} in #{best_case_id})")

        if not diff_lines:
            continue

        target_summary = ""
        if alt_targets_met or best_targets_met:
            target_summary = (
                f"\nCase #{alt_id} satisfies: {', '.join(alt_targets_met) or 'none'}"
                f"\nCase #{alt_id} fails: {', '.join(alt_targets_failed) or 'none'}"
                f"\nCase #{best_case_id} satisfies: {', '.join(best_targets_met) or 'none'}"
                f"\nCase #{best_case_id} fails: {', '.join(best_targets_failed) or 'none'}"
            )

        alt_rmsre = alt.get('rmsre', '?')
        alt_met = alt.get('targets_met_20pct', '?')
        diag_rationale = alt.get('_diagnosis_rationale', '')
        is_lowest_cost = alt.get('_is_lowest_cost', False)

        if is_lowest_cost:
            header_meta = f"LOWEST COST in ensemble — RMSRE: {alt_rmsre}, targets_met: {alt_met}"
        elif alt_eval:
            header_meta = f"high-satisfaction tie — RMSRE: {alt_rmsre}, targets_met: {alt_met}"
        else:
            header_meta = f"diagnosis-selected (outside top n_satisfied)"

        rationale_block = ""
        if diag_rationale:
            rationale_block = f"\n**Diagnosis rationale:** {diag_rationale}\n"

        sections.append(
            f"## Alternative Case #{alt_id} — Parameter Differences vs #{best_case_id}"
            f" ({header_meta})"
            f"{rationale_block}"
            f"{target_summary}\n\n"
            f"Parameters that differ (diagnosis-relevant + top sensitive):\n"
            f"{chr(10).join(diff_lines)}\n\n"
            f"You may design a SEPARATE experiment group from Case #{alt_id} if it provides\n"
            f"a better starting point for certain targets. Specify `\"base_case\": {alt_id}` in the\n"
            f"hypothesis JSON to use this case instead of #{best_case_id}."
        )
        logger.info(f"Added {len(diff_lines)} parameter diffs for alternative case #{alt_id}")

    # If diagnosis already selected base cases, highlight them
    selected = screening_data.get('_selected_base_cases', [])
    if selected:
        sel_lines = ["## Diagnosis-Selected Base Cases (from Phase 3)"]
        sel_lines.append("")
        sel_lines.append("The diagnosis phase has already recommended these base cases for experiments.")
        sel_lines.append("Use these unless you have strong reason to deviate.")
        sel_lines.append("")
        for s in selected:
            sid = s.get('case_id', '?')
            rat = s.get('rationale', '')
            t_sat = ', '.join(s.get('targets_satisfied', []))
            t_fix = ', '.join(s.get('targets_to_fix', []))
            sel_lines.append(f"- **Case #{sid}**: {rat}")
            if t_sat:
                sel_lines.append(f"  - Already satisfies: {t_sat}")
            if t_fix:
                sel_lines.append(f"  - Targets to fix: {t_fix}")
        sections.append("\n".join(sel_lines))

    return "\n\n".join(sections)


def generate_hypothesis(self, diagnosis: Diagnosis,
                       sensitivity_data: Dict,
                       previous_experiments: List[Dict],
                       screening_data: Dict = None) -> Hypothesis:
    """
    Generate a testable hypothesis from diagnosis.

    Args:
        diagnosis: Diagnosis object from previous phase
        sensitivity_data: Full sensitivity analysis data
        previous_experiments: List of experiments already tried
        screening_data: Screening results with case IDs for context

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

    # Get discovery context from memory (mechanistic insights from past calibration)
    discovery_context = ""
    if self.memory:
        # Extract target names from diagnosis
        target_names = [t if isinstance(t, str) else t.get('name', '') for t in diagnosis.failing_targets] if diagnosis.failing_targets else []
        # Also extract parameter names from recommendations
        rec_params = [rec.get('parameter', '') for rec in diagnosis.parameter_recommendations]
        rec_params = [p for p in rec_params if p]
        disc_text = self.memory.get_relevant_context(
            targets=target_names,
            parameters=rec_params,
            max_chars=4000
        )
        if disc_text.strip():
            discovery_context = f"\n## DISCOVERIES FROM PREVIOUS CALIBRATION\n\n{disc_text}\n\n**Use these discoveries to inform your hypothesis.** If a discovery describes a mechanism\nthat explains the current diagnosis, incorporate it. If a discovery warns about a specific\napproach, avoid it.\n\n"

    # Get RAG context for parameters mentioned in diagnosis AND sensitivity
    rag_context = ""
    targeted_param_context = ""
    # Extract parameters from diagnosis recommendations
    param_names = [rec.get('parameter', '') for rec in diagnosis.parameter_recommendations]
    param_names = [p for p in param_names if p]
    # Also extract top sensitive params (handles nested {output: {PFT: [params]}})
    for output_rankings in sensitivity_data.values():
        if isinstance(output_rankings, dict):
            for pft_params in output_rankings.values():
                if isinstance(pft_params, list):
                    param_names.extend([p.get('param', p.get('parameter', ''))
                                       for p in pft_params[:3]])
        elif isinstance(output_rankings, list):
            param_names.extend([p.get('param', p.get('parameter', ''))
                               for p in output_rankings[:3]])
    param_names = list(set(p for p in param_names if p))[:20]
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

    if self.rag_retriever:
        rag_context = self._get_rag_context(
            parameters=param_names[:10],
            mechanisms=mechanisms if mechanisms else ['PID_Controller'],
            query=f"hypothesis testing {' '.join(diagnosis.likely_causes[:2])}"
        )
        # Get targeted parameter/output definitions
        targeted_param_context = self._get_targeted_param_context(
            param_names=param_names[:15],
            mechanisms=mechanisms if mechanisms else ['PID_Controller']
        )

    # Build concise sensitivity summary
    sensitivity_summary = _build_sensitivity_summary(sensitivity_data)

    # Build reference case context from screening data
    _case_context = ""
    _base_case_params_context = ""
    if screening_data:
        bc = screening_data.get('best_case', {})
        lc = screening_data.get('lowest_cost_case', {})
        bc_id = bc.get('case_id', 'N/A')
        lc_id = lc.get('case_id', 'N/A')
        bc_rmsre = bc.get('composite_rmsre', bc.get('cost', 'N/A'))
        lc_rmsre = lc.get('composite_rmsre', lc.get('cost', 'N/A'))
        bc_met = bc.get('targets_met', 'N/A')
        lc_met = lc.get('targets_met', 'N/A')
        _case_context = f"""## Reference Cases
- **Best case:** #{bc_id} (composite_rmsre: {bc_rmsre}, targets_met: {bc_met})
- **Lowest cost case:** #{lc_id} (composite_rmsre: {lc_rmsre}, targets_met: {lc_met})

When discussing parameter values, edge cases, or diagnostic findings, ALWAYS reference
the specific case ID (e.g., "Case #{bc_id}'s phosphatase parameters are at lower bounds").
Do NOT make generic statements without case attribution.
"""
        # Read base case parameter values — only pass diagnosis-relevant +
        # top 10 sensitive per target to keep the prompt concise.
        if bc_id != 'N/A':
            base_case_params = self._load_base_case_parameters(int(bc_id))
            if base_case_params:
                # Build set of params to include:
                # 1) Diagnosis-recommended (already in param_names)
                include_set = set(p for p in param_names if p)
                # 2) Top 10 sensitive params per PFT per output variable
                for output_rankings in sensitivity_data.values():
                    if isinstance(output_rankings, dict):
                        for pft_params in output_rankings.values():
                            if isinstance(pft_params, list):
                                include_set.update(
                                    p.get('parameter', p.get('param', ''))
                                    for p in pft_params[:10]
                                )
                    elif isinstance(output_rankings, list):
                        include_set.update(
                            p.get('parameter', p.get('param', ''))
                            for p in output_rankings[:10]
                        )
                include_set.discard('')

                # include_set may contain FATES names (from diagnosis, e.g.
                # 'fates_cnp_vmax_p') or shorthands (from sensitivity, e.g.
                # 'vmax_p_10'). base_case_params keys are shorthands. Use
                # build_param_lookup() reverse mapping to expand FATES names
                # to their matching shorthands.
                try:
                    from tools.modify_fates_parameters import build_param_lookup
                    _plf = os.environ.get('A2MC_PARAM_LIST_FILE', '')
                    param_lookup = build_param_lookup(_plf)
                    # Reverse: fates_name → set of shorthands
                    fates_to_shorthands = {}
                    for shorthand, entry in param_lookup.items():
                        fates_to_shorthands.setdefault(entry['fates_name'], set()).add(shorthand)
                    # Expand any FATES names in include_set to their shorthands
                    expanded = set()
                    for p in include_set:
                        if p in fates_to_shorthands:
                            expanded.update(fates_to_shorthands[p])
                        else:
                            expanded.add(p)
                    include_set = expanded
                except Exception as e:
                    logger.debug(f"FATES→shorthand expansion failed: {e}")

                included_lines = []
                for pname, pval in sorted(base_case_params.items()):
                    if pname in include_set:
                        included_lines.append(f"  {pname}: {pval}")

                # Fallback: if filtering produced 0 matches (e.g., no sensitivity
                # data and FATES→shorthand expansion failed), include ALL params
                # so the AI at least has current values to work with.
                if not included_lines:
                    logger.warning(f"No params matched include_set ({len(include_set)} entries). "
                                   f"Including all {len(base_case_params)} base case params as fallback.")
                    for pname, pval in sorted(base_case_params.items()):
                        included_lines.append(f"  {pname}: {pval}")

                _base_case_params_context = f"""## Base Case #{bc_id} — Actual Parameter Values ({len(included_lines)} params)

**CRITICAL: Use these ACTUAL values as the "current" field when recommending parameter changes.**
**Do NOT guess or infer current values from bounds or defaults — use the values below.**

{chr(10).join(included_lines)}
"""
                logger.info(f"Added {len(included_lines)}/{len(base_case_params)} base case parameter values "
                            f"to hypothesis prompt (diagnosis-relevant + top sensitive)")

                # Load alternative high-satisfaction case parameters (show diffs only)
                _base_case_params_context += self._build_alt_case_params_context(
                    screening_data, base_case_params, include_set, bc_id
                )

    _round_ctx = _build_round_context_block()
    _mode_ctx = _build_active_mode_block()

    prompt = f"""Based on this diagnosis, generate a testable hypothesis for ELM-FATES calibration.

{_round_ctx}{_mode_ctx}{rag_context}{discovery_context}{failed_approaches_context}{targeted_param_context}

{self._param_list_context}

{_case_context}
{_base_case_params_context}

## Diagnosis
{diagnosis.to_json()}

## Sensitivity Analysis Data (top parameters per output)

**IMPORTANT: Hypotheses MUST target parameters with high Morris sensitivity (μ*).
Proposing changes to low-sensitivity parameters wastes HPC compute.**

{sensitivity_summary}

<details>
<summary>Full sensitivity data (JSON)</summary>

{json.dumps(sensitivity_data, indent=2)}
</details>

## Previous Experiments (avoid repeating these)
{json.dumps(previous_experiments, indent=2)}

## Hypothesis Generation Process (follow these steps)

1. **Consider at least 3 possible hypotheses** before selecting the best one for testing.
   For each, briefly note the mechanism, expected effect, and risk level.
   **DIVERSITY REQUIREMENT:** Your hypothesis MUST target a DIFFERENT mechanism than
   previous experiments listed above. If all major mechanisms have been explored, you may
   refine the highest-confidence one with new evidence.

2. **Select the BEST hypothesis** based on:
   - Highest expected impact on failing targets
   - Strongest mechanistic evidence from diagnosis
   - Lowest risk of cross-PFT degradation
   - Not previously failed (check failed approaches above)
   - Targets a DIFFERENT mechanism from previous experiments

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
- Morris sampling bounds are NOT physical limits. You MAY propose values outside
  the current Morris range if scientifically justified (e.g., literature values,
  mechanistic reasoning). Flag these as "out of Morris bounds — recommend bound
  expansion in Phase 0 redesign." Do NOT submit no-op parameters (proposed == current)
  just because the current value is at a bound — either propose a value beyond
  the bound or omit the parameter entirely.
- Include parameter bounds (min/max) and sensitivity rank where known

## CRITICAL: Organ-Dependent Parameters
Some FATES parameters have an organ dimension (fates_plant_organs × fates_pft).
For these parameters you MUST include the `"organ"` field:
- `"organ": 1` = leaf
- `"organ": 2` = fineroot
- `"organ": 3` = sapwood
- `"organ": 4` = storage

**Two categories of organ-dependent parameters:**

**Category A — Different values per organ** (stoichiometry, allocation priority):
`fates_stoich_phos`, `fates_stoich_nitr`, `fates_alloc_organ_priority`
These have DIFFERENT values for leaf vs fineroot. Specify each organ separately:
```json
{{"name": "fates_stoich_phos", "pft": 10, "organ": 1, "current": 0.003, "proposed": 0.0015, "rationale": "reduce leaf P demand"}}
{{"name": "fates_stoich_phos", "pft": 10, "organ": 2, "current": 0.0009, "proposed": 0.0007, "rationale": "reduce fineroot P demand"}}
```

**Category B — Same value for leaf + fineroot** (retranslocation):
`fates_cnp_turnover_nitr_retrans`, `fates_cnp_turnover_phos_retrans`
Retranslocation only applies to senescing tissues (leaf and fineroot), NOT sapwood or storage.
You MUST provide TWO entries with the SAME proposed value — one for organ=1 (leaf), one for organ=2 (fineroot):
```json
{{"name": "fates_cnp_turnover_phos_retrans", "pft": 10, "organ": 1, "current": 0.7, "proposed": 0.89, "rationale": "increase P recycling in leaves"}}
{{"name": "fates_cnp_turnover_phos_retrans", "pft": 10, "organ": 2, "current": 0.7, "proposed": 0.89, "rationale": "increase P recycling in fineroots"}}
```

For non-organ parameters, set `"organ": null` or omit it.

## Skip Testing: Test with Existing Data (MANDATORY FIRST STEP)

**You MUST set `test_with_existing: true` unless the hypothesis fundamentally CANNOT be
evaluated with existing ensemble data.** HPC experiments are expensive (hours of compute),
so ALWAYS prefer testing with existing Morris data first. Only set `test_with_existing: false`
if you need parameter values OUTSIDE the Morris ensemble ranges.

Set `test_with_existing: true` if ANY of these apply (most hypotheses qualify):

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
Return a JSON object with this structure. If using an alternative base case (from the
Alternative Case sections above), specify its case ID in the `base_case` field.
Otherwise omit `base_case` to use the best case.
```json
{{
    "name": "Hypothesis Name (memorable, mechanistic)",
    "base_case": null,
    "mechanism": "Detailed mechanistic explanation",
    "parameters": [
        {{
            "name": "fates_param_name",
            "pft": 9,
            "organ": null,
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

    # Hypothesis JSON includes embedded test scripts, so use 8192 tokens.
    response = self.query(prompt, max_tokens=8192)

    # Parse response — filter to Hypothesis dataclass fields
    try:
        data = self._extract_json(response)

        # --- Layer 1 validation: auto-fix + error detection ---
        from reasoning.validation import (
            validate_hypothesis_parameters, load_parameter_bounds,
            build_reprompt_context,
        )
        # Load base case params (may already exist from prompt building above)
        _val_base_params = {}
        if screening_data:
            _val_bc_id = screening_data.get('best_case', {}).get('case_id', 'N/A')
            if _val_bc_id != 'N/A':
                _val_base_params = self._load_base_case_parameters(int(_val_bc_id))
        _val_bounds = load_parameter_bounds()

        _val_result = None
        if _val_base_params or _val_bounds:
            _val_result = validate_hypothesis_parameters(data, _val_base_params, _val_bounds)

            # If errors remain after auto-fix, re-prompt once
            if _val_result.has_errors:
                for issue in _val_result.issues:
                    if issue.severity == "error":
                        logger.warning(f"  Validation error: {issue.parameter} ({issue.check}): {issue.detail}")
                reprompt_ctx = build_reprompt_context(
                    _val_result, data, _val_base_params, _val_bounds)
                logger.warning(f"Hypothesis validation found {_val_result.n_errors} error(s), re-prompting once")
                retry_response = self.query(prompt + reprompt_ctx, max_tokens=8192)
                data = self._extract_json(retry_response)
                # Re-validate the retry (auto-fix only, no further re-prompt)
                _val_result = validate_hypothesis_parameters(data, _val_base_params, _val_bounds)
                if _val_result.has_errors:
                    logger.warning(f"Retry still has {_val_result.n_errors} error(s): {_val_result.summary()}")
                    for issue in _val_result.issues:
                        if issue.severity == "error":
                            logger.warning(f"  Unresolved: {issue.parameter} ({issue.check}): {issue.detail}")
                    # Strip parameters with unresolved errors to prevent downstream crashes
                    error_params = {issue.parameter for issue in _val_result.issues if issue.severity == "error"}
                    if error_params and 'parameters' in data:
                        before_count = len(data['parameters'])
                        data['parameters'] = [
                            p for p in data['parameters']
                            if p.get('name', p.get('parameter', '')) not in error_params
                        ]
                        stripped = before_count - len(data['parameters'])
                        if stripped:
                            logger.warning(f"  Stripped {stripped} parameter(s) with unresolved errors: {error_params}")

        known = {f.name for f in fields(Hypothesis)}
        hyp = Hypothesis(**{k: v for k, v in data.items() if k in known})
        # Attach validation result as non-dataclass attribute for caller access
        hyp._validation = _val_result
        return hyp
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse hypothesis response: {e}")
        raise


def synthesize_experiment_design(
    self,
    cumulative_insights: List[Dict],
    hypotheses: List[Dict],
    diagnoses: List[Dict] = None,
    sensitivity_data: Dict = None,
    previous_experiments: List = None,
    # Backward compat: accept old 'diagnosis' kwarg
    diagnosis: Dict = None,
    evidence_ledger: Dict = None,
    screening_data: Dict = None,
) -> List[Dict]:
    """
    Synthesize cumulative skip-testing insights into multiple experiment designs.

    Called when the skip-testing inner loop exits (confidence >= threshold or
    max cycles reached).  Each supported hypothesis becomes a separate
    experiment design so they can be tested independently on HPC.  The AI
    refines each hypothesis using evidence gathered across all cycles
    (including refuted insights and parameter interactions).

    Args:
        cumulative_insights: List of insight dicts from skip-testing cycles,
            each with: cycle, hypothesis_name, hypothesis_supported, confidence,
            test_method, key_insights, evidence_summary, parameters_tested
        hypotheses: All hypotheses generated during skip-testing
        diagnoses: All diagnosis dicts from skip-testing cycles.
            The full list lets the AI see how understanding evolved across cycles.
        sensitivity_data: Morris/Sobol sensitivity rankings
        previous_experiments: Previous HPC experiments (to avoid repeating)
        diagnosis: Deprecated — single diagnosis dict for backward compatibility.
            Use 'diagnoses' instead.

    Returns:
        List of hypothesis dicts, each with: name, mechanism, parameters,
        design_type, expected_outcomes, success_criteria, confidence.
        One per distinct experiment to run on HPC.
    """
    # Backward compat: if caller passed 'diagnosis' (singular), wrap it
    if diagnoses is None and diagnosis is not None:
        diagnoses = [diagnosis]
    elif diagnoses is None:
        diagnoses = []
    if not cumulative_insights:
        # Nothing to synthesize - return last hypothesis as-is
        if hypotheses:
            last = hypotheses[-1]
            h = last if isinstance(last, dict) else last.__dict__ if hasattr(last, '__dict__') else {}
            return [h] if h else []
        return []

    # Build summary of supported vs refuted hypotheses
    supported = [i for i in cumulative_insights if i.get('hypothesis_supported')]
    refuted = [i for i in cumulative_insights if not i.get('hypothesis_supported')]

    if not supported:
        # No supported hypotheses - return best-effort hypothesis with most parameters
        if hypotheses:
            # Find the hypothesis with the most parameters (prefer recent ones)
            best_hyp = None
            best_n_params = 0
            for hyp in reversed(hypotheses):
                h = hyp if isinstance(hyp, dict) else (hyp.__dict__ if hasattr(hyp, '__dict__') else {})
                params = h.get('parameters', h.get('parameters_to_test', []))
                if len(params) > best_n_params:
                    best_n_params = len(params)
                    best_hyp = h
                # Take the first (most recent) one with parameters if none has many
                if best_hyp is None and params:
                    best_hyp = h
                    best_n_params = len(params)
            if best_hyp is None:
                # All hypotheses have 0 params — fall back to last one
                last = hypotheses[-1]
                best_hyp = last if isinstance(last, dict) else (last.__dict__ if hasattr(last, '__dict__') else {})
            best_hyp['synthesis_note'] = 'No hypotheses were supported during skip testing; testing best-effort hypothesis with most parameters'
            return [best_hyp] if best_hyp else []
        return []

    # Get failed approaches from memory
    failed_approaches_context = ""
    if self.memory:
        failed_approaches = self.memory.failed_approaches.get("failed_approaches", [])
        if failed_approaches:
            failed_approaches_context = "\n## FAILED APPROACHES - DO NOT PROPOSE THESE\n"
            for fa in failed_approaches[:10]:
                failed_approaches_context += f"- **{fa.get('approach', '?')}**: {fa.get('why_failed', 'Failed')}\n"
            failed_approaches_context += "\n"

    # Get discovery context from memory for synthesis
    discovery_context = ""
    if self.memory:
        # Extract target names from diagnoses and parameter names from insights
        synth_targets = []
        synth_params = []
        for diag in diagnoses:
            for t in diag.get('failing_targets', []):
                if isinstance(t, dict):
                    synth_targets.append(t.get('name', ''))
                elif isinstance(t, str):
                    synth_targets.append(t)
        for insight in cumulative_insights:
            synth_params.extend(insight.get('parameters_tested', []))
        synth_targets = [t for t in synth_targets if t]
        synth_params = list(set(p for p in synth_params if p))[:15]
        disc_text = self.memory.get_relevant_context(
            targets=synth_targets,
            parameters=synth_params,
            max_chars=3000
        )
        if disc_text.strip():
            discovery_context = f"\n{disc_text}\n\n"

    # Get RAG context for parameters mentioned across all insights
    rag_context = ""
    all_params = []
    for insight in cumulative_insights:
        all_params.extend(insight.get('parameters_tested', []))
    all_params = list(set(p for p in all_params if p))[:20]

    if self.rag_retriever and all_params:
        rag_context = self._get_rag_context(
            parameters=all_params[:10],
            query="experiment design synthesis parameter calibration"
        )

    # Build sensitivity summary if available
    sensitivity_summary = ""
    if sensitivity_data:
        sensitivity_summary = f"\n## Sensitivity Rankings\n{_build_sensitivity_summary(sensitivity_data)}\n"

    # Build previous experiments summary
    prev_exp_summary = ""
    if previous_experiments:
        prev_exp_summary = f"\n## Previous HPC Experiments (avoid repeating)\n{json.dumps(previous_experiments, indent=2, default=str)}\n"

    # Build diagnosis evolution summary (all cycles, not just latest)
    if len(diagnoses) > 1:
        diagnosis_context = "## Diagnosis Evolution (all skip-testing cycles)\n\n"
        for i, diag in enumerate(diagnoses):
            cycle_num = i + 1
            causes = diag.get('likely_causes', [])
            confidence = diag.get('confidence', 0)
            recs = diag.get('parameter_recommendations', [])
            rec_names = [r.get('parameter', '?') for r in recs[:5]]
            diagnosis_context += f"### Cycle {cycle_num} (confidence: {confidence:.2f})\n"
            diagnosis_context += f"**Root causes:** {'; '.join(causes[:3]) if causes else 'N/A'}\n"
            diagnosis_context += f"**Key parameters:** {', '.join(rec_names) if rec_names else 'N/A'}\n\n"
        diagnosis_context += f"### Latest Diagnosis (Cycle {len(diagnoses)}) — Full Detail\n"
        diagnosis_context += json.dumps(diagnoses[-1], indent=2, default=str)
    elif diagnoses:
        diagnosis_context = f"## Diagnosis Context\n{json.dumps(diagnoses[-1], indent=2, default=str)}"
    else:
        diagnosis_context = "## Diagnosis Context\n*No diagnosis available*"

    # Build evidence ledger section (replaces raw hypothesis_param_groups dump)
    evidence_ledger_section = ""
    if evidence_ledger:
        evidence_ledger_section = format_evidence_ledger_for_prompt(evidence_ledger)
    else:
        # Fallback: collect param groups from hypotheses (no ledger available)
        hypothesis_param_groups = []
        for hyp in hypotheses:
            h = hyp if isinstance(hyp, dict) else (hyp.__dict__ if hasattr(hyp, '__dict__') else {})
            params = h.get('parameters', h.get('parameters_to_test', []))
            if params:
                hypothesis_param_groups.append({
                    'hypothesis_name': h.get('name', 'unknown'),
                    'mechanism': h.get('mechanism', ''),
                    'parameters': params,
                    'was_supported': any(
                        i.get('hypothesis_supported') and i.get('hypothesis_name') == h.get('name')
                        for i in cumulative_insights
                    )
                })
        evidence_ledger_section = (
            f"## Hypotheses and Their Parameters\n"
            f"{json.dumps(hypothesis_param_groups, indent=2, default=str)}"
        )

    # Read base case parameter values — only include params mentioned in
    # hypotheses (not all 162) since synthesis works with Phase 4 outputs.
    _synth_base_params = ""
    if screening_data:
        bc_id = screening_data.get('best_case', {}).get('case_id', 'N/A')
        if bc_id != 'N/A':
            base_case_params = self._load_base_case_parameters(int(bc_id))
            if base_case_params:
                # Collect param names from all hypotheses
                synth_include = set()
                for hyp in hypotheses:
                    h = hyp if isinstance(hyp, dict) else (hyp.__dict__ if hasattr(hyp, '__dict__') else {})
                    for p in h.get('parameters', h.get('parameters_to_test', [])):
                        pname = p.get('name', p.get('parameter', ''))
                        if pname:
                            synth_include.add(pname)
                synth_include.discard('')

                param_lines = [f"  {pname}: {pval}"
                               for pname, pval in sorted(base_case_params.items())
                               if pname in synth_include]
                _synth_base_params = f"""## Base Case #{bc_id} — Actual Parameter Values ({len(param_lines)} params from hypotheses)

**CRITICAL: Use these ACTUAL values as the "current" field for each parameter.**
**Do NOT guess or infer current values from bounds or defaults.**

{chr(10).join(param_lines) if param_lines else '  (no matching parameters found)'}
"""
                logger.info(f"Added {len(param_lines)}/{len(base_case_params)} base case parameter values "
                            f"to synthesis prompt (hypothesis-relevant only)")

                # Add alternative case parameter diffs for synthesis
                _synth_base_params += self._build_alt_case_params_context(
                    screening_data, base_case_params, synth_include, bc_id
                )

    _round_ctx = _build_round_context_block()
    _mode_ctx = _build_active_mode_block()

    prompt = f"""You are synthesizing {len(cumulative_insights)} skip-testing cycles into MULTIPLE experiment designs for HPC testing.

Each supported hypothesis should become its OWN experiment — do NOT merge them into one.
This allows independent testing of different mechanistic ideas in parallel on HPC.

{_round_ctx}{_mode_ctx}{rag_context}{discovery_context}{failed_approaches_context}
{_synth_base_params}

## Cumulative Skip-Testing Insights

### Supported Hypotheses ({len(supported)})
{json.dumps(supported, indent=2, default=str)}

### Refuted Hypotheses ({len(refuted)})
{json.dumps(refuted, indent=2, default=str)}

{diagnosis_context}

{evidence_ledger_section}
{sensitivity_summary}{prev_exp_summary}

## Composite Mechanistic Picture (REQUIRED before designing experiments)

Before designing experiments, synthesize ALL skip-testing insights into a unified
mechanistic model. Address these questions:
- Which mechanisms are independent vs interacting?
- Which must be addressed first (prerequisite) vs can be tested in parallel?
- Do any discoveries from previous calibration work explain patterns seen in skip-testing?

This composite picture should inform your experiment design — some experiments may need
to address MULTIPLE interacting mechanisms if they form a causal chain.

## Synthesis Task

Create a SEPARATE experiment design for each distinct supported hypothesis.
Use the evidence ledger to decide which parameters to include.

### Rules:
1. **One experiment per supported hypothesis** — keep them independent so we can identify which mechanism matters
2. **Multi-cycle parameters (3+ cycles) are STRONG candidates** — include unless you have explicit counter-evidence (cite the cycle and evidence)
3. **Dropped parameters (active in 2+ previous cycles but missing in latest)** require EXPLICIT justification for exclusion
4. **Single-cycle parameters are WEAK** — include only with strong mechanistic rationale
5. **Refine values** using all evidence gathered across cycles (adjust based on what was learned)
6. **EXCLUDE refuted parameters** unless strong counter-evidence exists
7. **Prioritize** high-sensitivity parameters (from Morris rankings)
8. **Use cumulative design** within each experiment (safest for multi-parameter changes)
9. **For each parameter you INCLUDE**: cite which cycles support it and the evidence
10. **For each parameter you EXCLUDE from the active set**: provide a specific reason
11. **Organ-dependent parameters** MUST include `"organ"` field:
    - `fates_stoich_phos`, `fates_stoich_nitr`, `fates_alloc_organ_priority`: specify organ per entry (1=leaf, 2=fineroot, 3=sapwood, 4=storage)
    - `fates_cnp_turnover_nitr_retrans`, `fates_cnp_turnover_phos_retrans`: retranslocation only applies to senescing tissues — provide TWO entries with the SAME value, one for organ=1 (leaf) and one for organ=2 (fineroot)

## Multi-Base-Case Experiment Groups

If alternative high-satisfaction cases are provided above, you may design SEPARATE experiment
groups from different base cases. Each group is an independent cumulative sequence targeting
that base case's weaknesses:

- Each group must specify `"base_case"` with the case ID number
- Each group uses cumulative design (each experiment adds one parameter change)
- Focus each group on that base case's WEAKEST targets (the targets it fails)
- Use the "current" values from the CORRECT base case for each group
- If multiple alternatives exist, select the 1-2 most promising based on complementary target
  coverage (which targets each satisfies that the other does not). Do NOT use all alternatives.
- Explain in `synthesis_summary` WHY each base case was selected

If no alternatives are provided, use the best case as the sole base case (omit `"base_case"`).

## Response Format
Return a JSON array of experiment designs (one per supported hypothesis, optionally from different base cases):
```json
[
    {{
        "name": "Descriptive experiment name",
        "base_case": 86,
        "mechanism": "Mechanistic explanation for this specific hypothesis",
        "parameters": [
            {{
                "name": "fates_param_name",
                "pft": 9,
                "organ": null,
                "current": 0.787,
                "proposed": 0.30,
                "rationale": "Why this change (citing evidence from skip testing cycles X, Y, Z)",
                "bounds": [0.1, 1.0],
                "sensitivity_rank": 3
            }}
        ],
        "design_type": "cumulative",
        "expected_outcomes": {{
            "target_name": "expected_value_or_direction"
        }},
        "success_criteria": {{
            "criterion_name": true
        }},
        "confidence": 0.85,
        "source_hypothesis": "Original hypothesis name this refines",
        "synthesis_summary": "What evidence supports this experiment and why this base case",
        "excluded_parameters_justification": {{
            "param_name": "Reason for exclusion despite evidence"
        }}
    }}
]
```

Respond ONLY with the JSON array."""

    try:
        # Synthesis produces multi-experiment JSON arrays; use 8192 tokens.
        response = self.query(prompt, max_tokens=8192)
        result = self._extract_json(response)

        # Handle both list and single-dict responses
        if isinstance(result, dict):
            result = [result]

        if not isinstance(result, list):
            raise ValueError(f"Expected list, got {type(result)}")

        # Ensure required fields on each experiment
        for i, exp in enumerate(result):
            exp.setdefault('name', f"Experiment {i+1} from skip-testing synthesis")
            exp.setdefault('mechanism', 'From skip-testing analysis')
            exp.setdefault('parameters', [])
            exp.setdefault('design_type', 'cumulative')
            exp.setdefault('expected_outcomes', {})
            exp.setdefault('success_criteria', {})
            exp.setdefault('confidence', max((s.get('confidence', 0) for s in supported), default=0.5))
            exp.setdefault('test_with_existing', False)
            exp['synthesized'] = True

        # Filter out experiments with no parameters
        result = [exp for exp in result if exp.get('parameters')]

        # --- Layer 1 validation: auto-fix synthesized experiments ---
        from reasoning.validation import (
            validate_experiment_designs, load_parameter_bounds,
        )
        _synth_base_params = {}
        if screening_data:
            _synth_bc_id = screening_data.get('best_case', {}).get('case_id', 'N/A')
            if _synth_bc_id != 'N/A':
                _synth_base_params = self._load_base_case_parameters(int(_synth_bc_id))
        _synth_bounds = load_parameter_bounds()

        if (_synth_base_params or _synth_bounds) and result:
            from reasoning.validation import build_reprompt_context
            val_results = validate_experiment_designs(result, _synth_base_params, _synth_bounds)
            has_errors = False
            for exp, vr in zip(result, val_results):
                if not vr.is_clean:
                    exp['_validation'] = vr
                    logger.info(f"  Synthesis validation '{exp.get('name', '?')}': {vr.summary()}")
                    if vr.has_errors:
                        has_errors = True

            # Re-prompt once if any experiment has validation errors
            if has_errors:
                error_lines = ["\n## VALIDATION ERRORS in synthesized experiments — Please fix and re-generate\n"]
                for exp, vr in zip(result, val_results):
                    if vr.has_errors:
                        error_lines.append(f"### Experiment: {exp.get('name', '?')}")
                        for issue in vr.issues:
                            if issue.severity == "error":
                                error_lines.append(f"- **{issue.parameter}** ({issue.check}): {issue.detail}")
                error_lines.append("\nPlease regenerate the complete JSON array with these corrections.")
                error_lines.append("Respond ONLY with the corrected JSON array.")
                reprompt_ctx = "\n".join(error_lines)

                logger.warning(f"Synthesis validation found errors, re-prompting once")
                retry_response = self.query(prompt + reprompt_ctx, max_tokens=8192)
                result = self._extract_json(retry_response)
                if isinstance(result, dict):
                    result = [result]
                result = [exp for exp in result if exp.get('parameters')]
                # Re-validate (auto-fix only, no further re-prompt)
                val_results = validate_experiment_designs(result, _synth_base_params, _synth_bounds)
                for exp, vr in zip(result, val_results):
                    if not vr.is_clean:
                        logger.info(f"  Retry validation '{exp.get('name', '?')}': {vr.summary()}")
                    if vr.has_errors:
                        # Strip parameters with unresolved errors
                        error_params = {i.parameter for i in vr.issues if i.severity == "error"}
                        before = len(exp.get('parameters', []))
                        exp['parameters'] = [
                            p for p in exp.get('parameters', [])
                            if p.get('parameter', p.get('name', '')) not in error_params
                        ]
                        stripped = before - len(exp['parameters'])
                        if stripped:
                            logger.warning(f"  Stripped {stripped} param(s) from '{exp.get('name', '?')}': {error_params}")

        logger.info(f"Synthesized {len(result)} experiment designs from {len(cumulative_insights)} skip-testing cycles")
        for exp in result:
            logger.info(f"  - {exp.get('name')}: {len(exp.get('parameters', []))} params, "
                        f"confidence={exp.get('confidence', 0):.2f}")

        return result

    except Exception as e:
        logger.error(f"Synthesis failed, falling back to per-hypothesis extraction: {e}")

        # Fallback: create one experiment per supported hypothesis
        experiments = []
        for insight in supported:
            hyp_name = insight.get('hypothesis_name', '')
            for hyp in hypotheses:
                h = hyp if isinstance(hyp, dict) else (hyp.__dict__ if hasattr(hyp, '__dict__') else {})
                if h.get('name') == hyp_name:
                    params = h.get('parameters', h.get('parameters_to_test', []))
                    if params:
                        experiments.append({
                            'name': f"Test: {hyp_name}",
                            'mechanism': h.get('mechanism', ''),
                            'parameters': params,
                            'design_type': h.get('design_type', 'cumulative'),
                            'expected_outcomes': h.get('expected_outcomes', {}),
                            'success_criteria': h.get('success_criteria', {}),
                            'confidence': insight.get('confidence', 0.5),
                            'source_hypothesis': hyp_name,
                            'test_with_existing': False,
                            'synthesized': True,
                        })
                    break  # found matching hypothesis

        if not experiments and hypotheses:
            # Last resort: use last hypothesis
            last = hypotheses[-1]
            h = last if isinstance(last, dict) else (last.__dict__ if hasattr(last, '__dict__') else {})
            h['synthesized'] = True
            experiments = [h]

        return experiments


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

{f"## Sensitivity Rankings{chr(10)}{chr(10)}{_build_sensitivity_summary(sensitivity_rankings)}{chr(10)}{chr(10)}<details>{chr(10)}<summary>Full sensitivity rankings (JSON)</summary>{chr(10)}{chr(10)}{json.dumps(sensitivity_rankings, indent=2)}{chr(10)}</details>" if sensitivity_rankings else ""}

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

    Analyzes parameter rankings (mu*, sigma) to identify:
    - Key parameters driving model behavior
    - Parameter interactions (high sigma/mu* ratio)
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
        - interactions: Parameters with high sigma indicating non-linear effects
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

    # Identify parameters with high interaction (sigma/mu* > 0.5)
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

## Top 10 Parameters by mu* (each PFT)
{json.dumps(top_params_summary, indent=2)}

## Parameters with High Interaction (sigma/mu* > 0.5)
{json.dumps(high_interaction_params, indent=2)}

## Parameters Important for ALL PFTs (in top 20 for each)
{list(common_params)}

{f"## Parameter Bounds (from SALib problem){chr(10)}{json.dumps(problem, indent=2)}" if problem else ""}

## Sensitivity Analysis Process (follow these steps)

1. **Key Parameters**: Which parameters have the strongest influence? What mechanisms do they control?
   For each top parameter, note the FATES mechanism (PID_Controller, ECA_Competition, etc.).

2. **Parameter Interactions**: High sigma/mu* ratio indicates non-linear effects or interactions.
   - Which parameters interact?
   - What does this mean for calibration strategy?
   - Are interactions synergistic (combined effect > sum) or antagonistic?

3. **Cross-PFT Comparison**: Create a comparison table showing:
   - Which parameters are in the top 10 for ALL PFTs (generic importance)
   - Which parameters are in the top 10 for only ONE PFT (PFT-specific)
   - Are the same mechanisms dominant across PFTs or do different PFTs have different bottlenecks?

4. **Edge Effects**: Parameters with high mu* near sampling bounds may need:
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


# =========================================================================
# Evidence Ledger Functions (standalone, not ReasoningModule methods)
# =========================================================================

def update_evidence_ledger(
    ledger: Dict,
    hypothesis: Dict,
    cycle_num: int,
    test_result: Optional[Dict] = None,
    untestable_params: Optional[list] = None,
) -> None:
    """
    Update the parameter evidence ledger after a skip-testing cycle.

    Tracks which parameters have been proposed across cycles, how many times
    each was supported, and creates an evidence trail so the AI can see
    parameter-level history across the skip-testing inner loop.

    Args:
        ledger: The parameter_evidence_ledger dict (mutated in place).
        hypothesis: Hypothesis dict with 'parameters' (or 'parameters_to_test').
        cycle_num: Current skip-testing cycle number (1-based).
        test_result: Optional test result dict with 'hypothesis_supported', 'confidence'.
        untestable_params: Optional list of params outside ensemble range.
            These are marked 'untestable' instead of supported/refuted.
    """
    # Build set of untestable parameter names for quick lookup
    untestable_names = set()
    if untestable_params:
        untestable_names = {p['name'] for p in untestable_params if 'name' in p}
    params = hypothesis.get('parameters', hypothesis.get('parameters_to_test', []))
    current_param_names = set()

    for p in params:
        name = p.get('name', '')
        if not name:
            continue
        current_param_names.add(name)

        if name not in ledger:
            # New parameter — first time proposed
            ledger[name] = {
                'fates_name': p.get('fates_name', ''),
                'pft': p.get('pft', None),
                'first_proposed_cycle': cycle_num,
                'last_proposed_cycle': cycle_num,
                'times_proposed': 1,
                'times_supported': 0,
                'proposed_values': [p.get('proposed', p.get('new_value'))],
                'current_status': 'active',
                'drop_reason': None,
                'evidence_trail': [
                    {'cycle': cycle_num, 'action': 'proposed',
                     'value': p.get('proposed', p.get('new_value')),
                     'source': 'hypothesis'}
                ],
            }
        else:
            entry = ledger[name]
            entry['last_proposed_cycle'] = cycle_num
            entry['times_proposed'] += 1
            entry['proposed_values'].append(p.get('proposed', p.get('new_value')))
            entry['current_status'] = 'active'
            entry['drop_reason'] = None

            # Determine if value changed
            prev_value = entry['proposed_values'][-2] if len(entry['proposed_values']) >= 2 else None
            new_value = p.get('proposed', p.get('new_value'))
            action = 'refined' if prev_value != new_value else 'kept'
            trail_entry = {
                'cycle': cycle_num, 'action': action,
                'value': new_value, 'source': 'hypothesis',
            }
            if action == 'refined' and p.get('rationale'):
                trail_entry['reason'] = p['rationale']
            entry['evidence_trail'].append(trail_entry)

            # Cap evidence trail at 20 entries
            if len(entry['evidence_trail']) > 20:
                entry['evidence_trail'] = entry['evidence_trail'][-20:]

    # Mark dropped parameters (were active but not in current hypothesis)
    for name, entry in ledger.items():
        if name not in current_param_names and entry.get('current_status') == 'active':
            entry['current_status'] = 'dropped'
            entry['drop_reason'] = f'Not included in cycle {cycle_num} hypothesis'
            entry['evidence_trail'].append({
                'cycle': cycle_num, 'action': 'dropped',
                'reason': entry['drop_reason'],
            })
            if len(entry['evidence_trail']) > 20:
                entry['evidence_trail'] = entry['evidence_trail'][-20:]

    # Update support counts from test result
    if test_result:
        for name in current_param_names:
            if name not in ledger:
                continue
            if name in untestable_names:
                # Param was outside ensemble range — mark as untestable, not refuted
                ledger[name]['evidence_trail'].append({
                    'cycle': cycle_num, 'action': 'untestable',
                    'reason': 'Proposed value outside Morris ensemble range',
                    'value': ledger[name]['proposed_values'][-1] if ledger[name]['proposed_values'] else None,
                })
                if len(ledger[name]['evidence_trail']) > 20:
                    ledger[name]['evidence_trail'] = ledger[name]['evidence_trail'][-20:]
            elif test_result.get('hypothesis_supported'):
                ledger[name]['times_supported'] += 1


def check_hypothesis_regression(
    current_hypothesis: Dict,
    previous_hypothesis: Dict,
    ledger: Dict,
) -> Optional[Dict]:
    """
    Detect if current hypothesis unjustifiably drops multi-cycle parameters.

    Returns a warning dict if regression detected, None otherwise.
    This is a warning, not a blocker — the AI may have valid reasons.

    Args:
        current_hypothesis: Current hypothesis dict.
        previous_hypothesis: Previous hypothesis dict.
        ledger: Parameter evidence ledger.

    Returns:
        Dict with 'dropped_params' and 'warning' if regression detected, else None.
    """
    prev_params = {
        p.get('name', '') for p in
        previous_hypothesis.get('parameters', previous_hypothesis.get('parameters_to_test', []))
    }
    curr_params = {
        p.get('name', '') for p in
        current_hypothesis.get('parameters', current_hypothesis.get('parameters_to_test', []))
    }

    dropped = prev_params - curr_params
    if not dropped:
        return None

    # Check if dropped params were multi-cycle active
    unjustified_drops = []
    for param in dropped:
        entry = ledger.get(param, {})
        if entry.get('times_proposed', 0) >= 2:
            unjustified_drops.append(param)

    if unjustified_drops:
        return {
            'dropped_params': list(unjustified_drops),
            'warning': (
                f"Hypothesis dropped {len(unjustified_drops)} multi-cycle parameter(s) "
                f"without justification: {', '.join(unjustified_drops)}"
            ),
        }
    return None


def format_evidence_ledger_for_prompt(
    ledger: Dict,
    max_params: int = 20,
) -> str:
    """
    Render the evidence ledger as Markdown tables for AI prompt context.

    Produces three sections: Active params, Dropped params, Single-Cycle params.
    Caps output at top max_params by times_proposed.

    Args:
        ledger: The parameter_evidence_ledger dict.
        max_params: Maximum number of parameters to include.

    Returns:
        Markdown string with evidence tables and selection rules.
    """
    if not ledger:
        return "*No parameter evidence ledger available.*"

    # Categorize
    active = []
    dropped = []
    single_cycle = []

    for name, entry in ledger.items():
        status = entry.get('current_status', 'active')
        times = entry.get('times_proposed', 0)
        if status == 'active' and times >= 2:
            active.append((name, entry))
        elif status == 'dropped' and times >= 2:
            dropped.append((name, entry))
        else:
            single_cycle.append((name, entry))

    # Sort by times_proposed descending
    active.sort(key=lambda x: x[1].get('times_proposed', 0), reverse=True)
    dropped.sort(key=lambda x: x[1].get('times_proposed', 0), reverse=True)
    single_cycle.sort(key=lambda x: x[1].get('times_proposed', 0), reverse=True)

    # Cap total
    total = len(active) + len(dropped) + len(single_cycle)
    if total > max_params:
        # Prioritize active, then dropped, then single-cycle
        remaining = max_params
        active = active[:remaining]
        remaining -= len(active)
        dropped = dropped[:remaining]
        remaining -= len(dropped)
        single_cycle = single_cycle[:remaining]

    lines = [f"## Parameter Evidence Ledger ({sum(1 for _, e in ledger.items() if e.get('current_status') == 'active')} active, "
             f"{sum(1 for _, e in ledger.items() if e.get('current_status') == 'dropped')} dropped)\n"]

    # Active parameters
    if active:
        lines.append("### Active Parameters (recommended in 2+ cycles)")
        lines.append("| Parameter | PFT | Times Proposed | Times Supported | Latest Value | First→Last Cycle |")
        lines.append("|-----------|-----|---------------|-----------------|-------------|-----------------|")
        for name, entry in active:
            pft = entry.get('pft', '?')
            tp = entry.get('times_proposed', 0)
            ts = entry.get('times_supported', 0)
            vals = entry.get('proposed_values', [])
            latest = vals[-1] if vals else '?'
            if isinstance(latest, float):
                latest = f"{latest:.4g}"
            fc = entry.get('first_proposed_cycle', '?')
            lc = entry.get('last_proposed_cycle', '?')
            lines.append(f"| {name} | {pft} | {tp} | {ts} | {latest} | {fc}→{lc} |")
        lines.append("")

    # Dropped parameters
    if dropped:
        lines.append("### Dropped Parameters (previously active, not in latest cycle)")
        lines.append("| Parameter | PFT | Drop Reason | Was Active Cycles |")
        lines.append("|-----------|-----|-------------|-------------------|")
        for name, entry in dropped:
            pft = entry.get('pft', '?')
            reason = entry.get('drop_reason', 'Unknown')
            fc = entry.get('first_proposed_cycle', '?')
            lc = entry.get('last_proposed_cycle', '?')
            tp = entry.get('times_proposed', 0)
            lines.append(f"| {name} | {pft} | {reason} | {fc}→{lc} ({tp} cycles) |")
        lines.append("")

    # Single-cycle parameters
    if single_cycle:
        lines.append("### Single-Cycle Parameters (proposed once only)")
        lines.append("| Parameter | PFT | Cycle | Supported? |")
        lines.append("|-----------|-----|-------|-----------|")
        for name, entry in single_cycle:
            pft = entry.get('pft', '?')
            fc = entry.get('first_proposed_cycle', '?')
            ts = entry.get('times_supported', 0)
            supported_str = 'Yes' if ts > 0 else 'No'
            lines.append(f"| {name} | {pft} | {fc} | {supported_str} |")
        lines.append("")

    # Selection rules
    lines.append("### Rules for Parameter Selection")
    lines.append("1. Parameters active in 3+ cycles are **STRONG** candidates — include unless you have explicit counter-evidence (cite the cycle and evidence)")
    lines.append("2. Parameters dropped from the latest cycle but active in 2+ previous cycles require **EXPLICIT justification** for exclusion")
    lines.append("3. Single-cycle parameters are **WEAK** candidates — include only with strong mechanistic rationale")
    lines.append("4. For each parameter you INCLUDE: cite which cycles support it and the evidence")
    lines.append("5. For each parameter you EXCLUDE from the active set: provide a specific reason")

    return "\n".join(lines)


# =========================================================================
# CALIBRATION ROUND SUMMARY
# =========================================================================

def summarize_calibration_round(self, round_number: int,
                                 previous_rounds: List[Dict],
                                 phase_history: List[Dict],
                                 experiments: List[Dict],
                                 diagnoses: List[Dict],
                                 best_experiment: Optional[Dict],
                                 config_snapshot: Dict,
                                 exit_reason: str) -> Dict:
    """
    Generate a structured summary of a completed calibration round.

    Called at the end of Phase 6 (redesign) or Phase 7 (convergence) to
    document what happened during this round and why it ended.

    Args:
        round_number: Current calibration round number
        previous_rounds: List of previous round summaries from calibration_rounds.yaml
        phase_history: Phase transition log from workflow state
        experiments: All experiments run during this round
        diagnoses: All diagnoses generated during this round
        best_experiment: Best experiment result (if any)
        config_snapshot: Current config values (params, ensembles, protocol, etc.)
        exit_reason: Why the round ended ("converged", "max_experiments", "redesign")

    Returns:
        Dict with YAML-ready round summary fields:
        - parameters, ensembles, trajectories, protocol
        - changes_from_previous, rationale, outcome, status
    """
    # Build context from previous rounds
    prev_summary = ""
    if previous_rounds:
        for r in previous_rounds:
            r_num = r.get("round_number", "?")
            prev_summary += f"\n### Round {r_num}\n"
            prev_summary += f"- Parameters: {r.get('parameters', '?')}, Ensembles: {r.get('ensembles', '?')}\n"
            prev_summary += f"- Protocol suplphos: {json.dumps(r.get('protocol', {}).get('suplphos', {}))}\n"
            if r.get("changes_from_previous"):
                prev_summary += f"- Changes: {r['changes_from_previous']}\n"
            prev_summary += f"- Rationale: {r.get('rationale', 'N/A')}\n"
            prev_summary += f"- Outcome: {r.get('outcome', 'N/A')}\n"

    # Build experiment summary
    exp_summary = ""
    if experiments:
        exp_summary = f"Total experiments: {len(experiments)}\n"
        for exp in experiments[-5:]:  # Last 5 experiments
            name = exp.get("name", "?")
            targets_met = exp.get("results", {}).get("targets_met", "?")
            exp_summary += f"  - {name}: {targets_met} targets met\n"

    # Build diagnosis summary
    diag_summary = ""
    if diagnoses:
        diag_summary = f"Total diagnoses: {len(diagnoses)}\n"
        for diag in diagnoses[-3:]:  # Last 3 diagnoses
            if isinstance(diag, dict):
                root_causes = diag.get("root_causes", [])
                if root_causes:
                    diag_summary += f"  - Root causes: {', '.join(str(rc) for rc in root_causes[:3])}\n"

    # Best result
    best_summary = "No experiments completed."
    if best_experiment:
        best_summary = (
            f"Best: {best_experiment.get('name', '?')} — "
            f"{best_experiment.get('results', {}).get('targets_met', '?')} targets met"
        )

    prompt = f"""Summarize this completed calibration round for the calibration_rounds.yaml history file.

## Current Round: {round_number}
Exit reason: {exit_reason}

## Configuration
- Parameters: {config_snapshot.get('n_params', '?')}
- Ensembles: {config_snapshot.get('n_ensembles', '?')}
- Trajectories: {config_snapshot.get('n_trajectories', '?')}
- Protocol suplphos: ADSP={config_snapshot.get('suplphos_adsp', '?')}, RGSP={config_snapshot.get('suplphos_rgsp', '?')}, TRANS={config_snapshot.get('suplphos_trans', '?')}

## Previous Rounds
{prev_summary if prev_summary else "This is the first round."}

## Phase History (this round)
{json.dumps(phase_history[-20:], indent=2) if phase_history else "N/A"}

## Experiments (this round)
{exp_summary if exp_summary else "No experiments."}

## Diagnoses (this round)
{diag_summary if diag_summary else "No diagnoses."}

## Best Result
{best_summary}

## Instructions
Write a concise summary of this calibration round. Return a JSON object with:

```json
{{{{
    "changes_from_previous": ["List of changes from the previous round, or null if first round"],
    "rationale": "Why this round was run (1-3 sentences)",
    "outcome": "What was achieved or learned (2-4 sentences)",
    "status": "completed"
}}}}
```

Guidelines:
- Be specific about mechanistic findings, not just statistics
- Reference specific discoveries, parameter names, or PFTs when relevant
- For "outcome", focus on the KEY insight or result, not a laundry list
- Keep each field concise but informative for future AI reasoning

Respond ONLY with the JSON object."""

    response = self.query(prompt)

    try:
        result = self._extract_json(response)
        # Merge with config data to create the full round entry
        round_entry = {
            "parameters": config_snapshot.get("n_params"),
            "ensembles": config_snapshot.get("n_ensembles"),
            "trajectories": config_snapshot.get("n_trajectories"),
            "targets": config_snapshot.get("targets"),
            "protocol": {
                "suplphos": {
                    "ADSP": config_snapshot.get("suplphos_adsp", "?"),
                    "RGSP": config_snapshot.get("suplphos_rgsp", "?"),
                    "TRANS": config_snapshot.get("suplphos_trans", "?"),
                }
            },
            "changes_from_previous": result.get("changes_from_previous"),
            "rationale": result.get("rationale", ""),
            "outcome": result.get("outcome", ""),
            "status": result.get("status", "completed"),
        }
        return round_entry

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse round summary response: {e}")
        return {
            "parameters": config_snapshot.get("n_params"),
            "ensembles": config_snapshot.get("n_ensembles"),
            "trajectories": config_snapshot.get("n_trajectories"),
            "protocol": {
                "suplphos": {
                    "ADSP": config_snapshot.get("suplphos_adsp", "?"),
                    "RGSP": config_snapshot.get("suplphos_rgsp", "?"),
                    "TRANS": config_snapshot.get("suplphos_trans", "?"),
                }
            },
            "changes_from_previous": None,
            "rationale": f"Round {round_number} (auto-summary failed)",
            "outcome": f"Exit reason: {exit_reason}. Best: {best_summary}",
            "status": "completed",
        }


def generate_session_report(self, artifacts: Dict, state_summary: Dict) -> str:
    """Generate a comprehensive session report via AI.

    Collects all phase logs, figure references, and state data, then
    calls the AI to produce a cohesive Markdown narrative report.

    Called at the end of Phase 6 (before convergence/loop decision).

    Args:
        artifacts: Output from tools.session_report.collect_session_artifacts()
        state_summary: Dict with calibration state info (site, round, targets, etc.)

    Returns:
        Markdown report string
    """
    from tools.session_report import build_report_prompt

    prompt = build_report_prompt(artifacts, state_summary)

    # Use diag max tokens since the report is long
    max_tokens = int(os.environ.get('A2MC_AI_DIAG_MAX_TOKENS', '16384'))

    logger.info("Generating session report via AI...")
    report = self.query(prompt, max_tokens=max_tokens)

    if not report or len(report.strip()) < 100:
        logger.warning("AI returned empty or very short session report")
        return _fallback_session_report(artifacts, state_summary)

    return report


def _fallback_session_report(artifacts: Dict, state_summary: Dict) -> str:
    """Generate a minimal report without AI when the API call fails."""
    lines = [
        f"# Session Report: {state_summary.get('session_id', 'Unknown')}",
        "",
        f"**Site:** {state_summary.get('site_name', '?')}",
        f"**Round:** {state_summary.get('calibration_round', '?')}",
        f"**Outcome:** {'CONVERGED' if state_summary.get('converged') else state_summary.get('exit_reason', '?')}",
        "",
        "---",
        "",
        "*AI report generation failed. Raw logs are available in the session directory.*",
        "",
    ]

    # List available logs
    for phase_name, log_list in artifacts.get("logs", {}).items():
        lines.append(f"## {phase_name}")
        for log_entry in log_list:
            lines.append(f"- {log_entry['filename']}")
        lines.append("")

    # List available figures
    for phase_name, paths in artifacts.get("figure_rel_paths", {}).items():
        lines.append(f"## Figures: {phase_name}")
        for p in paths:
            fig_name = os.path.splitext(os.path.basename(p))[0]
            lines.append(f"![{fig_name}]({p})")
        lines.append("")

    return "\n".join(lines)
