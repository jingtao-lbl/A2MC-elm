#!/usr/bin/env python3
"""
Phase Logger for A2MC Workflow

Writes detailed Markdown logs for each phase of the A2MC calibration workflow.
Logs capture full AI reasoning, analyses, and results for knowledge extraction.

Log Structure (site-specific):
    use_cases/{site}/memory/logs/
    ├── phase0_design/
    │   └── iter01_exp00_skip00_20260116a_Morris_Design.md
    ├── phase2_screening/
    │   └── iter01_exp00_skip00_20260116b_Ensemble_Screening.md
    ├── phase3_diagnosis/
    │   └── iter02_exp01_skip03_20260116c_Root_Cause_Analysis.md
    └── ...

Filename format: iter{II}_exp{EE}_skip{SS}_{YYYYMMDDx}_Title.md
    II = high-level iteration (display counter, zero-padded)
    EE = experiment_count (outer loop counter, zero-padded)
    SS = skip_testing_count (inner loop counter, zero-padded)
    YYYYMMDDx = date + session letter (a, b, c for same-day logs)

Note:
    - A2MC development logs go to: memory/logs/ (at framework level)
    - Phase execution logs go to: use_cases/{site}/memory/logs/ (site-specific)

Templates:
    This logger uses patterns from templates/logging/:
    - diagnostic_log_template.md: Phase 3 deep dives
    - experiment_log_template.md: Phase 4-5 experiments
    - discovery_log_template.md: Key findings (Perfect Storm, etc.)
    - analysis_log_template.md: General analysis

    Key patterns supported:
    - Named discoveries: "Perfect Storm", "Allocation Paradox", "Triple Bottleneck"
    - Mortality component analysis: Hydraulic vs C Starvation vs Fire
    - Cross-PFT comparison tables: Differential PFT responses
    - Pool tracking: P/N/C investigations
    - Phenology-nutrient uptake interaction

Usage:
    from tools.phase_logger import PhaseLogger
    from tools.config import config

    # Initialize with site-specific path and iteration context
    logger = PhaseLogger(
        site_dir=config.USE_CASE_DIR,
        site_name="Kougarok",
        iteration=2, experiment_count=1, skip_testing_count=3
    )

    # Or update iteration context later
    logger.set_iteration_context(iteration=3, experiment_count=1, skip_testing_count=0)

    # Log with full AI reasoning
    logger.log_diagnosis(
        title="PFT10 Root Cause Analysis",
        diagnosis=diagnosis_obj,
        ai_reasoning="Full AI thinking and analysis...",
        context_used={"memory": True, "rag": True}
    )

Author: Jing Tao
Created: January 2026
Updated: January 19, 2026 - Enhanced with template patterns (Perfect Storm, etc.)
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import json
import os

logger = logging.getLogger(__name__)


# Phase definitions
PHASES = {
    0: "design",
    1: "exploration",
    2: "screening",
    3: "diagnosis",
    4: "hypothesis",
    5: "testing",
    6: "refinement",
    7: "converged"
}


class PhaseLogger:
    """
    Manages detailed Markdown logging for A2MC workflow phases.

    Logs are written to site-specific directories and contain full AI reasoning,
    analyses, and results for later knowledge extraction.
    """

    def __init__(self, site_dir: str = None, site_name: str = None,
                 iteration: int = None, experiment_count: int = None,
                 skip_testing_count: int = None):
        """
        Initialize the phase logger.

        Args:
            site_dir: Path to site use_case directory (e.g., use_cases/Kougarok)
                      If None, tries to get from A2MC_USE_CASE_DIR env var
            site_name: Site name for log headers (e.g., "Kougarok")
                       If None, tries to get from A2MC_SITE_NAME env var
            iteration: Current workflow iteration number
                       If None, tries to get from A2MC_ITERATION env var (default: 1)
            experiment_count: Outer loop counter (full 3→4→5→6 cycles)
                             If None, tries A2MC_EXPERIMENT_COUNT env var (default: 0)
            skip_testing_count: Inner loop counter (Phase 3↔4 cycles)
                               If None, tries A2MC_SKIP_TESTING_COUNT env var (default: 0)

        Environment Variables:
            A2MC_USE_CASE_DIR: Site directory path
            A2MC_SITE_NAME: Site name for log headers
            A2MC_ITERATION: Current iteration number (set by orchestrator)
            A2MC_EXPERIMENT_COUNT: Outer loop counter (set by orchestrator)
            A2MC_SKIP_TESTING_COUNT: Inner loop counter (set by orchestrator)
        """
        # Resolve site directory
        if site_dir:
            self.site_dir = Path(site_dir)
        else:
            site_dir_env = os.environ.get('A2MC_USE_CASE_DIR', '')
            if site_dir_env:
                self.site_dir = Path(site_dir_env)
            else:
                # Fallback to current directory's use_cases/TEMPLATE
                self.site_dir = Path("use_cases/TEMPLATE")
                logger.warning(f"No site_dir specified, using: {self.site_dir}")

        # Resolve site name
        self.site_name = site_name or os.environ.get('A2MC_SITE_NAME', 'Unknown')

        # Set up log directory
        self.log_dir = self.site_dir / "memory" / "logs"
        self._ensure_directories()

        # Resolve iteration counters: explicit arg > env var > default
        if iteration is not None:
            self.current_iteration = iteration
        else:
            self.current_iteration = int(os.environ.get('A2MC_ITERATION', '1'))

        if experiment_count is not None:
            self.experiment_count = experiment_count
        else:
            self.experiment_count = int(os.environ.get('A2MC_EXPERIMENT_COUNT', '0'))

        if skip_testing_count is not None:
            self.skip_testing_count = skip_testing_count
        else:
            self.skip_testing_count = int(os.environ.get('A2MC_SKIP_TESTING_COUNT', '0'))

        self._session_letter = 'a'  # For same-day logs: a, b, c, ...
        self._last_date = None

    def _ensure_directories(self):
        """Create log directories for each phase"""
        for phase_num, phase_name in PHASES.items():
            phase_dir = self.log_dir / f"phase{phase_num}_{phase_name}"
            phase_dir.mkdir(parents=True, exist_ok=True)

    def _get_log_filename(self, phase: int, title: str) -> str:
        """
        Generate log filename with iteration context, date, and session letter.

        Format: iter{II}_exp{EE}_skip{SS}_{YYYYMMDDx}_Title.md

        Where:
            II = iteration (zero-padded, 2 digits)
            EE = experiment_count (zero-padded, 2 digits)
            SS = skip_testing_count (zero-padded, 2 digits)
            YYYYMMDDx = date + session letter (a, b, c for same-day logs)

        Benefits:
            - `ls` sorts by iteration → experiment → skip-testing order
            - Glob `iter01_*` finds all logs for a given iteration
            - System can find latest: `glob(f"iter{n:02d}_exp{e:02d}_skip*_*.md")`
        """
        today = datetime.now().strftime("%Y%m%d")

        # Reset session letter if new day
        if self._last_date != today:
            self._session_letter = 'a'
            self._last_date = today

        # Clean title for filename
        clean_title = title.replace(' ', '_').replace('/', '_')[:50]

        # Build iteration prefix
        iter_prefix = (f"iter{self.current_iteration:02d}"
                       f"_exp{self.experiment_count:02d}"
                       f"_skip{self.skip_testing_count:02d}")

        filename = f"{iter_prefix}_{today}{self._session_letter}_{clean_title}.md"

        # Increment session letter for next log
        self._session_letter = chr(ord(self._session_letter) + 1)

        return filename

    def _get_phase_dir(self, phase: int) -> Path:
        """Get directory for a specific phase"""
        phase_name = PHASES.get(phase, "unknown")
        return self.log_dir / f"phase{phase}_{phase_name}"

    def set_iteration(self, iteration: int):
        """Set the current workflow iteration (backward compatible)."""
        self.current_iteration = iteration

    def set_iteration_context(self, iteration: int,
                              experiment_count: int = None,
                              skip_testing_count: int = None):
        """
        Update all iteration counters at once.

        Call this before each phase logging call to sync with orchestrator state.

        Args:
            iteration: Display iteration counter
            experiment_count: Outer loop counter (if None, keeps current value)
            skip_testing_count: Inner loop counter (if None, keeps current value)
        """
        self.current_iteration = iteration
        if experiment_count is not None:
            self.experiment_count = experiment_count
        if skip_testing_count is not None:
            self.skip_testing_count = skip_testing_count

    def _format_iteration_line(self) -> str:
        """Format the iteration context line for log headers."""
        return (f"**Iteration:** {self.current_iteration} "
                f"(Experiment: {self.experiment_count}, "
                f"Skip Testing: {self.skip_testing_count})")

    def _format_metadata_block(self, phase: int, phase_name: str,
                               extra: Dict = None) -> str:
        """
        Generate a structured metadata JSON block for machine-readable parsing.

        Appended at the end of every log file.
        """
        metadata = {
            "iteration": self.current_iteration,
            "experiment_count": self.experiment_count,
            "skip_testing_count": self.skip_testing_count,
            "phase": phase,
            "phase_name": phase_name,
            "timestamp": datetime.now().isoformat(),
            "site": self.site_name
        }
        if extra:
            metadata.update(extra)
        return f"""
---

## Iteration Context

```json
{json.dumps(metadata, indent=2, default=str)}
```
"""

    def _format_dict_as_markdown(self, data: Dict, indent: int = 0) -> str:
        """Format a dictionary as readable Markdown"""
        lines = []
        prefix = "  " * indent
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}- **{key}:**")
                lines.append(self._format_dict_as_markdown(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{prefix}- **{key}:**")
                for item in value:
                    if isinstance(item, dict):
                        lines.append(self._format_dict_as_markdown(item, indent + 1))
                    else:
                        lines.append(f"{prefix}  - {item}")
            else:
                lines.append(f"{prefix}- **{key}:** {value}")
        return "\n".join(lines)

    def _write_log(self, phase: int, title: str, content: str) -> Path:
        """Write a Markdown log to file"""
        phase_dir = self._get_phase_dir(phase)
        filename = self._get_log_filename(phase, title)
        filepath = phase_dir / filename

        with open(filepath, 'w') as f:
            f.write(content)

        logger.info(f"Wrote phase {phase} log: {filepath}")
        return filepath

    # =========================================================================
    # Phase-specific logging methods (Markdown format)
    # =========================================================================

    def log_design(self,
                   title: str,
                   sampling_method: str,
                   n_parameters: int,
                   n_simulations: int,
                   ai_reasoning: str = "",
                   parameter_summary: Dict = None,
                   design_decisions: List[str] = None,
                   metadata: Dict = None) -> Path:
        """
        Log Phase 0: Design with full reasoning.

        Args:
            title: Log title (e.g., "Morris Sensitivity Design")
            sampling_method: morris, lhs, sobol, custom
            n_parameters: Number of parameters
            n_simulations: Total ensemble size
            ai_reasoning: Full AI reasoning/analysis text
            parameter_summary: Summary of parameter selection
            design_decisions: Key design decisions made
            metadata: Additional metadata
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        content = f"""# {title}

**Site:** {self.site_name}
**Phase:** 0 - Design
{self._format_iteration_line()}
**Date:** {timestamp}

---

## Summary

- **Sampling Method:** {sampling_method}
- **Parameters:** {n_parameters}
- **Total Simulations:** {n_simulations}

---

## AI Reasoning and Analysis

{ai_reasoning if ai_reasoning else "*No AI reasoning recorded*"}

---

## Design Decisions

"""
        if design_decisions:
            for decision in design_decisions:
                content += f"- {decision}\n"
        else:
            content += "*No specific decisions recorded*\n"

        if parameter_summary:
            content += f"""
---

## Parameter Summary

{self._format_dict_as_markdown(parameter_summary)}
"""

        if metadata:
            content += f"""
---

## Metadata

```json
{json.dumps(metadata, indent=2, default=str)}
```
"""

        content += self._format_metadata_block(0, "design", metadata)

        return self._write_log(0, title, content)

    def log_exploration(self,
                        title: str,
                        total_cases: int,
                        completed_cases: int,
                        failed_cases: int = 0,
                        ai_reasoning: str = "",
                        issues_encountered: List[str] = None,
                        metadata: Dict = None) -> Path:
        """Log Phase 1: Exploration with status summary."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        completion_rate = (completed_cases / total_cases * 100) if total_cases > 0 else 0

        content = f"""# {title}

**Site:** {self.site_name}
**Phase:** 1 - Exploration
{self._format_iteration_line()}
**Date:** {timestamp}

---

## Ensemble Status

| Metric | Value |
|--------|-------|
| Total Cases | {total_cases} |
| Completed | {completed_cases} |
| Failed | {failed_cases} |
| Incomplete | {total_cases - completed_cases - failed_cases} |
| Completion Rate | {completion_rate:.1f}% |

---

## AI Reasoning and Analysis

{ai_reasoning if ai_reasoning else "*No AI reasoning recorded*"}

---

## Issues Encountered

"""
        if issues_encountered:
            for issue in issues_encountered:
                content += f"- {issue}\n"
        else:
            content += "*No issues recorded*\n"

        if metadata:
            content += f"""
---

## Metadata

```json
{json.dumps(metadata, indent=2, default=str)}
```
"""

        content += self._format_metadata_block(1, "exploration", metadata)

        return self._write_log(1, title, content)

    def log_screening(self,
                      title: str,
                      n_sets_evaluated: int,
                      best_cost: float,
                      top_sets: List[int],
                      ai_reasoning: str = "",
                      ai_analysis: Dict = None,
                      target_performance: Dict = None,
                      key_findings: List[str] = None,
                      metadata: Dict = None) -> Path:
        """
        Log Phase 2: Screening with full analysis.

        Args:
            title: Log title
            n_sets_evaluated: Number of parameter sets evaluated
            best_cost: Best composite cost achieved
            top_sets: List of top parameter set IDs
            ai_reasoning: Full AI reasoning text
            ai_analysis: Structured AI analysis results
            target_performance: Performance by target
            key_findings: Key findings from screening
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        content = f"""# {title}

**Site:** {self.site_name}
**Phase:** 2 - Screening
{self._format_iteration_line()}
**Date:** {timestamp}

---

## Summary

- **Sets Evaluated:** {n_sets_evaluated}
- **Best Composite Cost:** {best_cost:.6f}
- **Top Sets:** {top_sets[:10]}

---

## AI Reasoning and Analysis

{ai_reasoning if ai_reasoning else "*No AI reasoning recorded*"}

"""
        if ai_analysis:
            content += f"""
---

## Structured AI Analysis

{self._format_dict_as_markdown(ai_analysis)}
"""

        if target_performance:
            content += f"""
---

## Target Performance

{self._format_dict_as_markdown(target_performance)}
"""

        content += """
---

## Key Findings

"""
        if key_findings:
            for finding in key_findings:
                content += f"- {finding}\n"
        else:
            content += "*No key findings recorded*\n"

        if metadata:
            content += f"""
---

## Metadata

```json
{json.dumps(metadata, indent=2, default=str)}
```
"""

        content += self._format_metadata_block(2, "screening", metadata)

        return self._write_log(2, title, content)

    def log_diagnosis(self,
                      title: str,
                      failing_targets: List[str],
                      likely_causes: List[str],
                      ai_reasoning: str = "",
                      parameter_recommendations: List[Dict] = None,
                      cross_pft_conflicts: List[str] = None,
                      confidence: float = 0.0,
                      context_used: Dict = None,
                      # New template-based sections
                      hypotheses: List[Dict] = None,
                      conceptual_model: str = None,
                      mortality_analysis: Dict = None,
                      pool_tracking: Dict = None,
                      named_discoveries: List[Dict] = None,
                      questions_for_discussion: List[str] = None,
                      metadata: Dict = None) -> Path:
        """
        Log Phase 3: Diagnosis with full AI reasoning.

        This is where the detailed AI thinking about root causes goes.

        Args:
            title: Log title
            failing_targets: List of targets not meeting criteria
            likely_causes: List of identified causes
            ai_reasoning: Full AI reasoning text
            parameter_recommendations: List of parameter change suggestions
            cross_pft_conflicts: List of PFT conflicts identified
            confidence: Overall confidence (0-1)
            context_used: Dict indicating what context was used
            hypotheses: List of hypotheses tested (template pattern)
            conceptual_model: ASCII diagram of causal chain (template pattern)
            mortality_analysis: Mortality component breakdown (template pattern)
            pool_tracking: P/N/C pool tracking data (template pattern)
            named_discoveries: Named patterns found (e.g., "Perfect Storm")
            questions_for_discussion: Open questions for next steps
            metadata: Additional metadata
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        content = f"""# {title}

**Site:** {self.site_name}
**Phase:** 3 - Diagnosis
{self._format_iteration_line()}
**Date:** {timestamp}
**Confidence:** {confidence:.2f}

---

## Failing Targets

"""
        for target in failing_targets:
            content += f"- {target}\n"

        content += f"""
---

## Likely Causes

"""
        for i, cause in enumerate(likely_causes, 1):
            content += f"{i}. {cause}\n"

        content += f"""
---

## AI Reasoning and Deep Analysis

{ai_reasoning if ai_reasoning else "*No AI reasoning recorded*"}

---

## Parameter Recommendations

"""
        if parameter_recommendations:
            for rec in parameter_recommendations:
                param = rec.get('parameter', 'Unknown')
                direction = rec.get('suggested_direction', 'Unknown')
                issue = rec.get('current_issue', '')
                priority = rec.get('priority', 0)
                content += f"### {param} (Priority: {priority})\n"
                content += f"- **Direction:** {direction}\n"
                content += f"- **Issue:** {issue}\n\n"
        else:
            content += "*No recommendations recorded*\n"

        if cross_pft_conflicts:
            content += """
---

## Cross-PFT Conflicts

"""
            for conflict in cross_pft_conflicts:
                content += f"- {conflict}\n"

        # New template-based sections

        if hypotheses:
            content += """
---

## Hypotheses Tested

"""
            for h in hypotheses:
                h_id = h.get('id', 'H?')
                statement = h.get('statement', '')
                mechanism = h.get('mechanism', '')
                status = h.get('status', 'untested')
                content += f"### {h_id}: {statement}\n"
                content += f"- **Mechanism:** {mechanism}\n"
                content += f"- **Status:** {status}\n"
                if h.get('evidence_for'):
                    content += "- **Evidence FOR:**\n"
                    for ev in h['evidence_for']:
                        content += f"  - {ev}\n"
                if h.get('evidence_against'):
                    content += "- **Evidence AGAINST:**\n"
                    for ev in h['evidence_against']:
                        content += f"  - {ev}\n"
                content += "\n"

        if conceptual_model:
            content += f"""
---

## Conceptual Model

```
{conceptual_model}
```
"""

        if mortality_analysis:
            content += """
---

## Mortality Component Analysis

| Year | Total Mort | Hydraulic | C Starvation | Fire | Dominant |
|------|------------|-----------|--------------|------|----------|
"""
            for year, data in mortality_analysis.items():
                total = data.get('total', 0)
                hydraulic = data.get('hydraulic', 0)
                c_starv = data.get('c_starvation', 0)
                fire = data.get('fire', 0)
                dominant = data.get('dominant', '-')
                content += f"| {year} | {total} | {hydraulic} | {c_starv} | {fire} | {dominant} |\n"

            content += """
**Key insight: Phenology-Nutrient Uptake Interaction**
- **Evergreen PFTs**: Persistent but LOW nutrient uptake rates → vulnerable to chronic stress
- **Deciduous PFTs & Graminoids**: HIGH uptake during spring flushing → more resilient
"""

        if pool_tracking:
            content += """
---

## Pool Tracking Analysis

| Pool | Initial | Final | Δ Total |
|------|---------|-------|---------|
"""
            for pool, data in pool_tracking.items():
                initial = data.get('initial', 'N/A')
                final = data.get('final', 'N/A')
                delta = data.get('delta', 'N/A')
                content += f"| {pool} | {initial} | {final} | {delta} |\n"

        if named_discoveries:
            content += """
---

## Named Discoveries

"""
            for disc in named_discoveries:
                name = disc.get('name', 'Unknown')
                description = disc.get('description', '')
                mechanism = disc.get('mechanism', '')
                content += f"### \"{name}\"\n\n"
                content += f"**Description:** {description}\n\n"
                if mechanism:
                    content += f"**Mechanism:**\n```\n{mechanism}\n```\n\n"

        if questions_for_discussion:
            content += """
---

## Questions for Discussion

"""
            for i, q in enumerate(questions_for_discussion, 1):
                content += f"{i}. {q}\n"

        if context_used:
            content += f"""
---

## Context Sources Used

- **Memory (Adaptive):** {context_used.get('memory', False)}
- **RAG (Knowledge Base):** {context_used.get('rag', False)}
- **Previous Experiments:** {context_used.get('experiments', False)}
"""

        if metadata:
            content += f"""
---

## Metadata

```json
{json.dumps(metadata, indent=2, default=str)}
```
"""

        content += self._format_metadata_block(3, "diagnosis", metadata)

        return self._write_log(3, title, content)

    def log_hypothesis(self,
                       title: str,
                       hypothesis_name: str,
                       mechanism: str,
                       parameters_to_modify: List[Dict],
                       ai_reasoning: str = "",
                       design_type: str = "cumulative",
                       expected_outcomes: Dict = None,
                       experiments_planned: List[Dict] = None,
                       confidence: float = 0.0,
                       metadata: Dict = None) -> Path:
        """Log Phase 4: Hypothesis with experimental design."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        content = f"""# {title}

**Site:** {self.site_name}
**Phase:** 4 - Hypothesis
{self._format_iteration_line()}
**Date:** {timestamp}
**Confidence:** {confidence:.2f}

---

## Hypothesis: {hypothesis_name}

### Mechanism

{mechanism}

### Design Type

{design_type}

---

## AI Reasoning and Analysis

{ai_reasoning if ai_reasoning else "*No AI reasoning recorded*"}

---

## Parameters to Modify

"""
        for param in parameters_to_modify:
            name = param.get('name', 'Unknown')
            current = param.get('current', 'N/A')
            proposed = param.get('proposed', 'N/A')
            rationale = param.get('rationale', '')
            content += f"### {name}\n"
            content += f"- **Current:** {current}\n"
            content += f"- **Proposed:** {proposed}\n"
            content += f"- **Rationale:** {rationale}\n\n"

        if expected_outcomes:
            content += f"""
---

## Expected Outcomes

{self._format_dict_as_markdown(expected_outcomes)}
"""

        if experiments_planned:
            content += """
---

## Experiments Planned

"""
            for i, exp in enumerate(experiments_planned, 1):
                content += f"### Experiment {i}: {exp.get('name', 'Unknown')}\n"
                content += f"{self._format_dict_as_markdown(exp)}\n\n"

        if metadata:
            content += f"""
---

## Metadata

```json
{json.dumps(metadata, indent=2, default=str)}
```
"""

        content += self._format_metadata_block(4, "hypothesis", metadata)

        return self._write_log(4, title, content)

    def log_testing(self,
                    title: str,
                    experiments_run: List[str],
                    results_summary: Dict,
                    ai_reasoning: str = "",
                    best_experiment: str = "",
                    improvement_details: Dict = None,
                    metadata: Dict = None) -> Path:
        """Log Phase 5: Testing results."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        content = f"""# {title}

**Site:** {self.site_name}
**Phase:** 5 - Testing
{self._format_iteration_line()}
**Date:** {timestamp}

---

## Experiments Run

"""
        for exp in experiments_run:
            content += f"- {exp}\n"

        content += f"""
---

## Results Summary

{self._format_dict_as_markdown(results_summary)}

---

## AI Reasoning and Analysis

{ai_reasoning if ai_reasoning else "*No AI reasoning recorded*"}

"""
        if best_experiment:
            content += f"""
---

## Best Experiment

**{best_experiment}**

"""
            if improvement_details:
                content += f"{self._format_dict_as_markdown(improvement_details)}\n"

        if metadata:
            content += f"""
---

## Metadata

```json
{json.dumps(metadata, indent=2, default=str)}
```
"""

        content += self._format_metadata_block(5, "testing", metadata)

        return self._write_log(5, title, content)

    def log_refinement(self,
                       title: str,
                       hypothesis_status: str,
                       targets_improved: List[str],
                       targets_degraded: List[str],
                       ai_reasoning: str = "",
                       lessons_learned: List[str] = None,
                       discoveries: List[Dict] = None,
                       failed_approaches: List[Dict] = None,
                       next_action: str = "iterate",
                       generalizability_assessment: Dict = None,
                       # New template-based sections
                       experiment_results: List[Dict] = None,
                       multi_phase_analysis: Dict = None,
                       cross_pft_comparison: Dict = None,
                       parameter_category_analysis: Dict = None,
                       mechanism_synthesis: Dict = None,
                       fundamental_constraints: List[str] = None,
                       convergence_assessment: Dict = None,
                       next_iteration_strategy: Dict = None,
                       metadata: Dict = None) -> Path:
        """
        Log Phase 6: Refinement with lessons and knowledge extraction.

        This phase is critical for knowledge extraction - the AI reasoning
        here will be processed to update gained_knowledge stores.

        Args:
            title: Log title
            hypothesis_status: CONFIRMED / PARTIAL / REJECTED
            targets_improved: List of improved targets
            targets_degraded: List of degraded targets
            ai_reasoning: Full AI reasoning text
            lessons_learned: List of lessons
            discoveries: Named discoveries (e.g., "Allocation Paradox")
            failed_approaches: Approaches that failed
            next_action: iterate / converge / abort
            generalizability_assessment: Whether to promote to generic knowledge
            experiment_results: Detailed experiment outcomes (template pattern)
            multi_phase_analysis: ADSP→RGSP→TRANS tracking (template pattern)
            cross_pft_comparison: Differential PFT responses (template pattern)
            parameter_category_analysis: By-category analysis (template pattern)
            mechanism_synthesis: Before/after understanding (template pattern)
            fundamental_constraints: Hard constraints discovered (template pattern)
            convergence_assessment: Progress toward convergence (template pattern)
            next_iteration_strategy: Strategy for next round (template pattern)
            metadata: Additional metadata
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        content = f"""# {title}

**Site:** {self.site_name}
**Phase:** 6 - Refinement
{self._format_iteration_line()}
**Date:** {timestamp}

---

## Hypothesis Status: {hypothesis_status}

---

## Target Changes

### Improved
"""
        for target in targets_improved:
            content += f"- {target}\n"
        if not targets_improved:
            content += "- *None*\n"

        content += """
### Degraded
"""
        for target in targets_degraded:
            content += f"- {target}\n"
        if not targets_degraded:
            content += "- *None*\n"

        content += f"""
---

## AI Reasoning and Deep Analysis

{ai_reasoning if ai_reasoning else "*No AI reasoning recorded*"}

---

## Lessons Learned

"""
        if lessons_learned:
            for lesson in lessons_learned:
                content += f"- {lesson}\n"
        else:
            content += "*No lessons recorded*\n"

        if discoveries:
            content += """
---

## Discoveries (for gained_knowledge)

"""
            for disc in discoveries:
                name = disc.get('name', 'Unknown')
                content += f"### {name}\n"
                content += f"{self._format_dict_as_markdown(disc)}\n\n"

        if failed_approaches:
            content += """
---

## Failed Approaches (DO NOT REPEAT)

"""
            for fa in failed_approaches:
                approach = fa.get('approach', 'Unknown')
                why = fa.get('why_failed', '')
                content += f"### {approach}\n"
                content += f"- **Why Failed:** {why}\n"
                if fa.get('alternatives'):
                    content += f"- **Alternatives:** {', '.join(fa['alternatives'])}\n"
                content += "\n"

        # New template-based sections

        if experiment_results:
            content += """
---

## Experiment Results Summary

| Exp ID | Hypothesis | Expected | Actual | Status | Key Finding |
|--------|------------|----------|--------|--------|-------------|
"""
            for exp in experiment_results:
                exp_id = exp.get('id', 'EXP_?')
                hypothesis = exp.get('hypothesis', '-')
                expected = exp.get('expected', '-')
                actual = exp.get('actual', '-')
                status = exp.get('status', '-')
                finding = exp.get('key_finding', '-')
                content += f"| {exp_id} | {hypothesis} | {expected} | {actual} | {status} | {finding} |\n"

        if multi_phase_analysis:
            content += """
---

## Multi-Phase Time Series Analysis

| Phase | Years | Key Metric | Value | Key Event |
|-------|-------|------------|-------|-----------|
"""
            for phase, data in multi_phase_analysis.items():
                years = data.get('years', '-')
                metric = data.get('metric', '-')
                value = data.get('value', '-')
                event = data.get('event', '-')
                content += f"| {phase} | {years} | {metric} | {value} | {event} |\n"

        if cross_pft_comparison:
            content += """
---

## Cross-PFT Comparison During Events

| PFT | Pre-Event | During Event | Post-Event | Outcome |
|-----|-----------|--------------|------------|---------|
"""
            for pft, data in cross_pft_comparison.items():
                pre = data.get('pre_event', '-')
                during = data.get('during_event', '-')
                post = data.get('post_event', '-')
                outcome = data.get('outcome', '-')
                content += f"| {pft} | {pre} | {during} | {post} | {outcome} |\n"

            content += """
**Key insight: Phenology-Nutrient Uptake Interaction**
- **Evergreen PFTs**: Persistent but LOW nutrient uptake rates → vulnerable to chronic stress
- **Deciduous PFTs & Graminoids**: HIGH uptake during spring flushing → more resilient
"""

        if parameter_category_analysis:
            content += """
---

## Parameter Category Analysis

"""
            for category, params in parameter_category_analysis.items():
                content += f"### {category}\n\n"
                content += "| Parameter | Direction | Outcome | Generalizable? |\n"
                content += "|-----------|-----------|---------|----------------|\n"
                for p in params:
                    name = p.get('name', '-')
                    direction = p.get('direction', '-')
                    outcome = p.get('outcome', '-')
                    generalizable = p.get('generalizable', '-')
                    content += f"| {name} | {direction} | {outcome} | {generalizable} |\n"
                content += "\n"

        if mechanism_synthesis:
            content += """
---

## Mechanism-Based Synthesis

"""
            for mechanism, data in mechanism_synthesis.items():
                content += f"### What We Learned About {mechanism}\n\n"
                if data.get('before'):
                    content += f"**BEFORE this iteration:**\n{data['before']}\n\n"
                if data.get('after'):
                    content += f"**AFTER this iteration:**\n{data['after']}\n\n"
                if data.get('recommendation'):
                    content += f"**RECOMMENDATION:**\n{data['recommendation']}\n\n"

        if fundamental_constraints:
            content += """
---

## Fundamental Constraints Identified

```
┌─────────────────────────────────────────────────────────┐
│           FUNDAMENTAL CONSTRAINTS                        │
├─────────────────────────────────────────────────────────┤
"""
            for i, constraint in enumerate(fundamental_constraints, 1):
                content += f"│  {i}. {constraint:<53}│\n"
            content += """└─────────────────────────────────────────────────────────┘
```
"""

        if convergence_assessment:
            content += """
---

## Convergence Assessment

"""
            status = convergence_assessment.get('status', 'unknown')
            content += f"**Current Status:** {status}\n\n"
            if convergence_assessment.get('progress'):
                content += f"**Progress:**\n{convergence_assessment['progress']}\n\n"
            if convergence_assessment.get('criteria'):
                content += "| Criterion | Target | Current | Met |\n"
                content += "|-----------|--------|---------|-----|\n"
                for criterion, data in convergence_assessment['criteria'].items():
                    target = data.get('target', '-')
                    current = data.get('current', '-')
                    met = '✓' if data.get('met', False) else '✗'
                    content += f"| {criterion} | {target} | {current} | {met} |\n"
            if convergence_assessment.get('recommendation'):
                content += f"\n**RECOMMENDATION:** {convergence_assessment['recommendation']}\n"

        if next_iteration_strategy:
            content += """
---

## Next Iteration Strategy

"""
            if next_iteration_strategy.get('focus'):
                content += f"**Focus:** {next_iteration_strategy['focus']}\n\n"
            if next_iteration_strategy.get('priority_experiments'):
                content += "**Priority Experiments:**\n"
                for exp in next_iteration_strategy['priority_experiments']:
                    content += f"- {exp}\n"
                content += "\n"
            if next_iteration_strategy.get('parameters_to_hold'):
                content += "**Parameters to Hold Fixed:**\n"
                for p in next_iteration_strategy['parameters_to_hold']:
                    content += f"- {p}\n"
                content += "\n"
            if next_iteration_strategy.get('new_hypotheses'):
                content += "**New Hypotheses to Explore:**\n"
                for h in next_iteration_strategy['new_hypotheses']:
                    content += f"- {h}\n"

        if generalizability_assessment:
            content += f"""
---

## Generalizability Assessment

*Should these lessons be promoted to generic knowledge?*

{self._format_dict_as_markdown(generalizability_assessment)}
"""

        content += f"""
---

## Next Action: {next_action}

"""

        if metadata:
            content += f"""
---

## Metadata

```json
{json.dumps(metadata, indent=2, default=str)}
```
"""

        content += self._format_metadata_block(6, "refinement", metadata)

        return self._write_log(6, title, content)

    # =========================================================================
    # Log retrieval methods
    # =========================================================================

    def get_latest_log(self, phase: int | str) -> Optional[Path]:
        """Get path to the most recent log for a phase."""
        if isinstance(phase, str):
            for num, name in PHASES.items():
                if name == phase.lower():
                    phase = num
                    break
            else:
                return None

        phase_dir = self._get_phase_dir(phase)
        logs = sorted(phase_dir.glob("*.md"), reverse=True)
        return logs[0] if logs else None

    def get_all_logs(self, phase: int | str) -> List[Path]:
        """Get all log paths for a phase, sorted by date (newest first)."""
        if isinstance(phase, str):
            for num, name in PHASES.items():
                if name == phase.lower():
                    phase = num
                    break
            else:
                return []

        phase_dir = self._get_phase_dir(phase)
        return sorted(phase_dir.glob("*.md"), reverse=True)

    def find_logs_by_iteration(self, phase: int | str,
                               iteration: int = None,
                               experiment_count: int = None,
                               skip_testing_count: int = None) -> List[Path]:
        """
        Find logs matching specific iteration context.

        Args:
            phase: Phase number or name
            iteration: Filter by display iteration (None = any)
            experiment_count: Filter by experiment count (None = any)
            skip_testing_count: Filter by skip testing count (None = any)

        Returns:
            List of matching log paths, sorted by name

        Examples:
            # All logs for iteration 2
            find_logs_by_iteration(3, iteration=2)

            # All skip-testing cycle 3 logs in experiment 1
            find_logs_by_iteration(3, experiment_count=1, skip_testing_count=3)
        """
        if isinstance(phase, str):
            for num, name in PHASES.items():
                if name == phase.lower():
                    phase = num
                    break
            else:
                return []

        phase_dir = self._get_phase_dir(phase)

        # Build glob pattern
        iter_part = f"iter{iteration:02d}" if iteration is not None else "iter*"
        exp_part = f"_exp{experiment_count:02d}" if experiment_count is not None else "_exp*"
        skip_part = f"_skip{skip_testing_count:02d}" if skip_testing_count is not None else "_skip*"

        pattern = f"{iter_part}{exp_part}{skip_part}_*.md"
        return sorted(phase_dir.glob(pattern))


def create_logger(site_dir: str = None) -> PhaseLogger:
    """Create a PhaseLogger instance for a site."""
    return PhaseLogger(site_dir=site_dir)


if __name__ == "__main__":
    # Test the logger
    logger = PhaseLogger(site_dir="use_cases/Kougarok", site_name="Kougarok",
                         iteration=2, experiment_count=1, skip_testing_count=3)

    # Test diagnosis log
    filepath = logger.log_diagnosis(
        title="PFT10_P_Limitation_Analysis",
        failing_targets=["froot_pft10", "leaf_pft10"],
        likely_causes=[
            "PFT#10 shows severe P-limitation due to low Vmax_P",
            "Storage cushion too low causing carbon starvation"
        ],
        ai_reasoning="""
## Deep Analysis

Looking at the screening results, PFT#10 consistently underperforms across all
top parameter sets. The pattern suggests a fundamental limitation in phosphorus
uptake rather than allocation parameters.

### Evidence

1. **Correlation with P-uptake parameters:** Sets with higher `vmax_p` show
   better PFT#10 performance (r=0.67)

2. **Storage dynamics:** Even with adequate carbon, PFT#10 fails to allocate
   to fine roots, suggesting nutrient-driven allocation feedback

3. **Cross-PFT comparison:** PFT#7 and PFT#9 don't show this pattern,
   indicating PFT#10-specific limitation

### Hypothesis

The PID controller may be responding to P-limitation by reducing growth
allocation, but the reduction is too aggressive for arctic graminoids
which have different P-requirements than shrubs.
""",
        parameter_recommendations=[
            {"parameter": "fates_cnp_vmax_p", "suggested_direction": "increase",
             "current_issue": "Too low for P-limited conditions", "priority": 1},
            {"parameter": "fates_alloc_storage_cushion", "suggested_direction": "increase",
             "current_issue": "Triggers starvation too early", "priority": 2}
        ],
        confidence=0.78,
        context_used={"memory": True, "rag": True, "experiments": False}
    )

    print(f"Wrote test log to: {filepath}")
