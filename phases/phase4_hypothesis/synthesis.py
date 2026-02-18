#!/usr/bin/env python3
"""
Phase 4 Synthesis — Synthesize skip-testing insights into experiment designs

Extracted from orchestrator.py: _synthesize_skip_testing_insights,
_write_synthesis_summary_log.

Author: Jing Tao with Claude
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def synthesize_skip_testing_insights(
    reasoning_module,
    state_data: Dict,
    phase_logger=None,
) -> int:
    """
    Synthesize cumulative insights from skip-testing cycles into experiment designs.

    Called when exiting the skip-testing inner loop (either via exit conditions
    or via a hypothesis requiring HPC experiments). Uses the evidence ledger and
    all accumulated insights to produce consolidated experiment designs that
    the AI marks with 'synthesized': True.

    Args:
        reasoning_module: ReasoningModule instance for Claude API calls.
            If None, synthesis is skipped.
        state_data: Dict with keys:
            - cumulative_insights: list of insight dicts
            - hypotheses: list of hypothesis dicts
            - diagnoses: list of diagnosis dicts
            - exploration_data: dict with sensitivity_rankings
            - experiments: list of previous experiment dicts
            - parameter_evidence_ledger: dict of parameter evidence
            - screening_data: dict with best_case, lowest_cost_case
            - skip_testing_count: int
            - iteration: int
        phase_logger: Optional PhaseLogger for writing logs.

    Returns:
        Number of synthesized experiments appended to state_data['hypotheses'],
        or 0 if synthesis was skipped/failed.
    """
    cumulative_insights = state_data.get('cumulative_insights', [])
    if not reasoning_module or not cumulative_insights:
        return 0

    hypotheses = state_data.get('hypotheses', [])
    diagnoses = state_data.get('diagnoses', [])
    exploration_data = state_data.get('exploration_data', {})
    experiments = state_data.get('experiments', [])
    evidence_ledger = state_data.get('parameter_evidence_ledger', {})
    screening_data = state_data.get('screening_data', {})

    logger.info("Synthesizing cumulative insights into experiment designs...")
    try:
        synthesized_list = reasoning_module.synthesize_experiment_design(
            cumulative_insights=cumulative_insights,
            hypotheses=hypotheses,
            diagnoses=diagnoses,
            sensitivity_data=exploration_data.get('sensitivity_rankings', {}),
            previous_experiments=experiments,
            evidence_ledger=evidence_ledger,
        )
        if synthesized_list:
            for synth in synthesized_list:
                if synth and synth.get('parameters'):
                    hypotheses.append(synth)

            n_synth = sum(1 for s in synthesized_list if s and s.get('parameters'))
            logger.info(f"  Synthesized {n_synth} experiment designs for HPC testing")

            # Log each synthesized experiment + write synthesis summary
            if phase_logger:
                for synth in synthesized_list:
                    if not synth or not synth.get('parameters'):
                        continue
                    try:
                        phase_logger.log_hypothesis(
                            title=f"Synthesized: {synth.get('name', 'Experiment')}",
                            hypothesis_name=synth.get('name', 'Synthesized'),
                            mechanism=synth.get('mechanism', ''),
                            parameters_to_modify=synth.get('parameters', []),
                            ai_reasoning=synth.get('synthesis_summary', ''),
                            design_type=synth.get('design_type', 'cumulative'),
                            expected_outcomes=synth.get('expected_outcomes', {}),
                            confidence=synth.get('confidence', 0),
                            metadata={
                                'synthesis': True,
                                'n_cycles': len(cumulative_insights),
                                'iteration': state_data.get('iteration', 0),
                                'source_hypothesis': synth.get('source_hypothesis', ''),
                                'base_case': screening_data.get('best_case', {}),
                                'lowest_cost_case': screening_data.get('lowest_cost_case', {}),
                            }
                        )
                    except Exception as e:
                        logger.warning(f"Could not write synthesis log: {e}")

                # Write the synthesis summary with evolution tables
                try:
                    write_synthesis_summary_log(phase_logger, state_data, synthesized_list)
                except Exception as e:
                    logger.warning(f"Could not write synthesis summary log: {e}")

            return n_synth
        else:
            logger.warning("Synthesis returned no experiment designs, using last hypothesis")
            # Still write summary log with evolution tables (no synthesized experiments)
            if phase_logger:
                try:
                    write_synthesis_summary_log(phase_logger, state_data, [])
                except Exception as e:
                    logger.warning(f"Could not write synthesis summary log: {e}")
            return 0
    except Exception as e:
        logger.warning(f"Synthesis failed, using last hypothesis: {e}")
        # Still write summary log with evolution tables
        if phase_logger:
            try:
                write_synthesis_summary_log(phase_logger, state_data, [])
            except Exception as e2:
                logger.warning(f"Could not write synthesis summary log: {e2}")
        return 0


def write_synthesis_summary_log(
    phase_logger,
    state_data: Dict,
    synthesized_list: List[Dict],
):
    """
    Write a synthesis summary log with diagnosis/hypothesis evolution tables
    and synthesized experiment details. Called after synthesis completes.

    Args:
        phase_logger: PhaseLogger instance for writing logs.
        state_data: Dict with cumulative_insights, diagnoses, hypotheses,
            parameter_evidence_ledger, screening_data, etc.
        synthesized_list: List of synthesized experiment dicts.
    """
    if not phase_logger:
        return

    cumulative_insights = state_data.get('cumulative_insights', [])
    diagnoses = state_data.get('diagnoses', [])
    evidence_ledger = state_data.get('parameter_evidence_ledger', {})
    screening_data = state_data.get('screening_data', {})

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    n_cycles = len(cumulative_insights)
    n_synth = sum(1 for s in synthesized_list if s and s.get('parameters'))

    # --- Build Diagnosis Evolution table ---
    diag_rows = []
    for i, diag in enumerate(diagnoses, 1):
        confidence = diag.get('confidence', 0)
        failing = diag.get('failing_targets', [])
        n_failing = len(failing)
        causes = diag.get('likely_causes', [])
        # Build a concise summary of the diagnosis
        cause_names = []
        for c in causes[:3]:
            if isinstance(c, dict):
                cause_names.append(c.get('parameter', c.get('cause', '?')))
            elif isinstance(c, str):
                cause_names.append(c)
        cause_summary = ', '.join(cause_names)
        if len(causes) > 3:
            cause_summary += f' (+{len(causes)-3} more)'
        diag_rows.append((i, f"{confidence:.2f}", str(n_failing), cause_summary))

    diag_table = "| Iter | Confidence | # Failing | Key Causes |\n"
    diag_table += "|------|-----------|-----------|------------|\n"
    for row in diag_rows:
        diag_table += f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |\n"

    # --- Build Hypothesis Evolution table ---
    hyp_rows = []
    for i, insight in enumerate(cumulative_insights, 1):
        name = insight.get('hypothesis_name', 'Unknown')
        # Truncate long names
        if len(name) > 40:
            name = name[:37] + '...'
        n_params = len(insight.get('parameters_tested', []))
        supported = insight.get('hypothesis_supported', False)
        confidence = insight.get('confidence', 0)
        result_str = f"{'Supported' if supported else 'Not supported'} ({confidence:.2f})"
        hyp_rows.append((str(i), name, str(n_params), result_str))

    # Add synthesized experiments to table
    for synth in synthesized_list:
        if not synth or not synth.get('parameters'):
            continue
        name = synth.get('name', 'Synthesized')
        if len(name) > 40:
            name = name[:37] + '...'
        n_params = len(synth.get('parameters', []))
        confidence = synth.get('confidence', 0)
        hyp_rows.append(('Synth', name, str(n_params), f"→ HPC ({confidence:.2f})"))

    hyp_table = "| Iter | Name | # Params | Result |\n"
    hyp_table += "|------|------|----------|--------|\n"
    for row in hyp_rows:
        hyp_table += f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |\n"

    # --- Build Evidence Ledger summary ---
    ledger_section = ""
    if evidence_ledger:
        active = {k: v for k, v in evidence_ledger.items()
                  if v.get('current_status') == 'active'}
        dropped = {k: v for k, v in evidence_ledger.items()
                   if v.get('current_status') == 'dropped'}

        if active:
            ledger_section += "### Active Parameters\n\n"
            ledger_section += "| Parameter | Times Proposed | Times Supported | Status |\n"
            ledger_section += "|-----------|---------------|-----------------|--------|\n"
            for name, entry in sorted(active.items(),
                                      key=lambda x: x[1].get('times_proposed', 0),
                                      reverse=True):
                proposed = entry.get('times_proposed', 0)
                supported = entry.get('times_supported', 0)
                ledger_section += f"| {name} | {proposed} | {supported} | active |\n"
            ledger_section += "\n"

        if dropped:
            ledger_section += "### Dropped Parameters\n\n"
            ledger_section += "| Parameter | Times Proposed | Times Supported | Status |\n"
            ledger_section += "|-----------|---------------|-----------------|--------|\n"
            for name, entry in sorted(dropped.items(),
                                      key=lambda x: x[1].get('times_proposed', 0),
                                      reverse=True):
                proposed = entry.get('times_proposed', 0)
                supported = entry.get('times_supported', 0)
                ledger_section += f"| {name} | {proposed} | {supported} | dropped |\n"
            ledger_section += "\n"

    # --- Build Synthesized Experiments section ---
    synth_section = ""
    for i, synth in enumerate(synthesized_list, 1):
        if not synth or not synth.get('parameters'):
            continue
        synth_section += f"### Experiment {i}: {synth.get('name', 'Unknown')}\n\n"
        synth_section += f"- **Confidence:** {synth.get('confidence', 0):.2f}\n"
        synth_section += f"- **Design:** {synth.get('design_type', 'cumulative')}\n"
        source = synth.get('source_hypothesis', '')
        if source:
            synth_section += f"- **Source hypothesis:** {source}\n"
        synth_section += f"\n| Parameter | Current | Proposed | Rationale |\n"
        synth_section += f"|-----------|---------|----------|-----------|\n"
        params = synth.get('parameters', [])
        for p in params:
            pname = p.get('name', '?')
            cur = p.get('current', '?')
            prop = p.get('proposed', '?')
            rat = p.get('rationale', '')
            # Truncate long rationales for table readability
            if isinstance(rat, str) and len(rat) > 60:
                rat = rat[:57] + '...'
            synth_section += f"| {pname} | {cur} | {prop} | {rat} |\n"
        synth_section += "\n"

        # Add cumulative experiment breakdown for cumulative designs
        design_type = synth.get('design_type', 'cumulative')
        if design_type == 'cumulative' and len(params) > 1:
            synth_section += "#### Cumulative Experiment Breakdown\n\n"
            synth_section += "Each experiment cumulatively adds one parameter change to isolate individual effects:\n\n"
            synth_section += "| Exp | # Params | Parameters Modified | Key Change |\n"
            synth_section += "|-----|----------|---------------------|------------|\n"
            cumulative_names = []
            for j, p in enumerate(params):
                pname = p.get('name', '?')
                cur = p.get('current', '?')
                prop = p.get('proposed', '?')
                cumulative_names.append(pname)
                if j == 0:
                    params_str = pname
                else:
                    params_str = ", ".join(cumulative_names[:-1]) + f", **+{pname}**"
                synth_section += f"| exp{j+1} | {j+1} | {params_str} | {pname}: {cur} → {prop} |\n"
            synth_section += "\n"

        if synth.get('synthesis_summary'):
            synth_section += f"**Synthesis reasoning:** {synth['synthesis_summary']}\n\n"
        if synth.get('excluded_parameters_justification'):
            synth_section += "**Excluded parameters:**\n\n"
            for param, reason in synth['excluded_parameters_justification'].items():
                synth_section += f"- `{param}`: {reason}\n"
            synth_section += "\n"

    # --- Assemble full log ---
    best_case = screening_data.get('best_case', {})
    lowest_case = screening_data.get('lowest_cost_case', {})
    base_info = ""
    if best_case:
        bc_id = best_case.get('case_id', best_case.get('case_number', '?'))
        bc_rmsre = best_case.get('rmsre', best_case.get('cost', '?'))
        bc_met = best_case.get('targets_met', '?')
        base_info += f"- **Best case (targets):** #{bc_id} (RMSRE {bc_rmsre}, {bc_met} targets met)\n"
    if lowest_case:
        lc_id = lowest_case.get('case_id', lowest_case.get('case_number', '?'))
        lc_rmsre = lowest_case.get('rmsre', lowest_case.get('cost', '?'))
        lc_met = lowest_case.get('targets_met', '?')
        base_info += f"- **Lowest cost case:** #{lc_id} (RMSRE {lc_rmsre}, {lc_met} targets met)\n"

    content = f"""# Skip-Testing Synthesis Summary

**Site:** {phase_logger.site_name}
**Phase:** 4 - Hypothesis (Synthesis)
{phase_logger._format_iteration_line(phase=4)}
**Date:** {timestamp}
**Skip-testing cycles:** {n_cycles}
**Synthesized experiments:** {n_synth}

---

## Screening Baseline

{base_info if base_info else "*No baseline data available*"}

---

## Diagnosis Evolution ({n_cycles} cycles)

{diag_table}
---

## Hypothesis Evolution ({n_cycles} cycles + synthesis)

{hyp_table}
---

## Evidence Ledger

{ledger_section if ledger_section else "*No evidence ledger data*"}

---

## Synthesized Experiment Designs

{synth_section if synth_section else "*No experiments synthesized*"}

{phase_logger._format_metadata_block(4, "synthesis", {
    'n_skip_testing_cycles': n_cycles,
    'n_synthesized_experiments': n_synth,
    'n_evidence_ledger_params': len(evidence_ledger),
})}"""

    phase_logger._write_log(4, "Synthesis_Summary", content)
