#!/usr/bin/env python3
"""
Phase Logger for A2MC Workflow

Writes detailed Markdown logs for each phase of the A2MC calibration workflow.
Logs capture full AI reasoning, analyses, and results for knowledge extraction.

Log Structure (site-specific, session-scoped when session_id set):
    use_cases/{site}/memory/logs/
    └── {session_id}/
        ├── phase0_design/
        │   └── r02_20260116_143052_Morris_Design.md
        ├── phase2_screening/
        │   └── r02_20260116_143052_Ensemble_Screening.md
        ├── phase3_diagnosis/
        │   └── r02_c01_iter03_20260116_143052_Root_Cause_Analysis.md
        └── ...

Fallback (no session_id): logs go directly under phase dirs without session subdirectory.

Filename formats (with session_id from orchestrator):
    Phase 0-2:       r{RR}_{session_id}_Title.md
    Phase 3, 4, 5, 6: r{RR}_c{EE}_iter{II}_{session_id}_Title.md

Fallback formats (standalone usage, no session_id):
    Phase 0-2:       r{RR}_{YYYYMMDDx}_Title.md
    Phase 3, 4, 5, 6: r{RR}_c{EE}_iter{II}_{YYYYMMDDx}_Title.md

    RR = calibration_round (outermost Phase 0→7 loop, e.g., round 1=138 params, round 2=162 params)
    EE = experiment_count (outer loop: full 3→4→5→6 experiment cycles)
    II = iteration within experiment cycle (Phase 3 & 4: skip_testing_count + 1;
         Phase 5 & 6: overall iteration counter within round)
    session_id = YYYYMMDD_HHMMSS timestamp matching the run log (a2mc_run_{session_id}.log)
    YYYYMMDDx = fallback: date + session letter (a, b, c for same-day logs)
    because the inner loop (Phase 3↔4) only applies there.

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
                 session_id: str = None,
                 calibration_round: int = None, iteration: int = None,
                 experiment_count: int = None, skip_testing_count: int = None):
        """
        Initialize the phase logger.

        Args:
            site_dir: Path to site use_case directory (e.g., use_cases/Kougarok)
                      If None, tries to get from A2MC_USE_CASE_DIR env var
            site_name: Site name for log headers (e.g., "Kougarok")
                       If None, tries to get from A2MC_SITE_NAME env var
            session_id: Session timestamp (YYYYMMDD_HHMMSS) from orchestrator run.
                        When set, replaces the date+letter suffix in log filenames
                        with this timestamp, making logs directly traceable to the
                        run log (a2mc_run_{session_id}.log).
                        If None, falls back to date+letter convention.
            calibration_round: Outermost loop counter (Phase 0→7 redesign cycle)
                              e.g., round 1 = 138 params, round 2 = 162 params
                              If None, tries A2MC_CALIBRATION_ROUND env var (default: 1)
            iteration: Cycle counter within a round (diagnosis/hypothesis cycles)
                       If None, tries to get from A2MC_ITERATION env var (default: 1)
            experiment_count: Outer loop counter (full 3→4→5→6 cycles)
                             If None, tries A2MC_EXPERIMENT_COUNT env var (default: 0)
            skip_testing_count: Inner loop counter (Phase 3↔4 cycles)
                               If None, tries A2MC_SKIP_TESTING_COUNT env var (default: 0)

        Environment Variables:
            A2MC_USE_CASE_DIR: Site directory path
            A2MC_SITE_NAME: Site name for log headers
            A2MC_CALIBRATION_ROUND: Calibration round (outermost loop)
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

        # Session ID from orchestrator (YYYYMMDD_HHMMSS)
        # When set, replaces date+letter in filenames AND adds session_id subdirectory
        self.session_id = session_id if session_id else None

        # Fallback: date+letter tracking (used when session_id is not set)
        self._session_letter = 'a'  # For same-day logs: a, b, c, ...
        self._last_date = None

        # Set up log directory and create phase subdirectories
        self.log_dir = self.site_dir / "memory" / "logs"
        self._ensure_directories()

        # Resolve iteration counters: explicit arg > env var > default
        if calibration_round is not None:
            self.calibration_round = calibration_round
        else:
            self.calibration_round = int(os.environ.get('A2MC_CALIBRATION_ROUND', '1'))

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

    def _ensure_directories(self):
        """Create log directories for each phase (session-scoped when session_id set)"""
        base = self.log_dir
        if self.session_id:
            base = base / self.session_id
        for phase_num, phase_name in PHASES.items():
            phase_dir = base / f"phase{phase_num}_{phase_name}"
            phase_dir.mkdir(parents=True, exist_ok=True)

    def _get_log_filename(self, phase: int, title: str) -> str:
        """
        Generate log filename with iteration context and session identifier.

        When session_id is set (orchestrator run):
            Phase 3-6:   r{RR}_c{EE}_iter{II}_{session_id}_Title.md
            Phase 0-2:   r{RR}_{session_id}_Title.md

        Fallback (no session_id, e.g., standalone usage):
            Phase 3-6:   r{RR}_c{EE}_iter{II}_{YYYYMMDDx}_Title.md
            Phase 0-2:   r{RR}_{YYYYMMDDx}_Title.md

        RR = calibration_round (outermost Phase 0→7 loop, e.g., round 1=138 params)
        EE = experiment_count (outer loop experiment cycle)
        II = iteration (Phase 3&4: skip_testing_count+1; Phase 5&6: overall iteration)
        session_id = YYYYMMDD_HHMMSS timestamp matching the run log
        """
        # Determine date portion: session_id or date+letter fallback
        if self.session_id:
            date_part = self.session_id
        else:
            today = datetime.now().strftime("%Y%m%d")
            # Reset session letter if new day
            if self._last_date != today:
                self._session_letter = 'a'
                self._last_date = today
            date_part = f"{today}{self._session_letter}"
            # Increment session letter for next log
            self._session_letter = chr(ord(self._session_letter) + 1)

        # Clean title for filename
        clean_title = title.replace(' ', '_').replace('/', '_')[:50]

        # Build prefix:
        # - Phases 3 & 4: round + cycle + iter (three loops: r, c, iter)
        #   iter = skip_testing_count + 1 (inner Phase 3↔4 loop, 1-based)
        # - Phases 5 & 6: round + cycle only (two loops: r, c)
        #   Only one Phase 5 and one Phase 6 per experiment cycle, so iter is not needed
        # - Phases 0-2: round only (iteration is always 1)
        round_prefix = f"r{self.calibration_round:02d}"
        if phase in (3, 4):
            iter_in_exp = self.skip_testing_count + 1  # 1-based inner loop counter
            iter_prefix = (f"{round_prefix}_c{self.experiment_count:02d}"
                           f"_iter{iter_in_exp:02d}")
        elif phase in (5, 6):
            iter_prefix = f"{round_prefix}_c{self.experiment_count:02d}"
        else:
            iter_prefix = round_prefix

        filename = f"{iter_prefix}_{date_part}_{clean_title}.md"

        return filename

    def _get_phase_dir(self, phase: int) -> Path:
        """Get directory for a specific phase (session-scoped when session_id set)"""
        phase_name = PHASES.get(phase, "unknown")
        base = self.log_dir
        if self.session_id:
            base = base / self.session_id
        return base / f"phase{phase}_{phase_name}"

    def set_iteration(self, iteration: int):
        """Set the current workflow iteration (backward compatible)."""
        self.current_iteration = iteration

    def set_iteration_context(self, iteration: int,
                              calibration_round: int = None,
                              experiment_count: int = None,
                              skip_testing_count: int = None):
        """
        Update all iteration counters at once.

        Call this before each phase logging call to sync with orchestrator state.

        Args:
            iteration: Cycle counter within a calibration round
            calibration_round: Outermost loop (Phase 0→7 redesign cycle, if None keeps current)
            experiment_count: Outer loop counter (if None, keeps current value)
            skip_testing_count: Inner loop counter (if None, keeps current value)
        """
        self.current_iteration = iteration
        if calibration_round is not None:
            self.calibration_round = calibration_round
        if experiment_count is not None:
            self.experiment_count = experiment_count
        if skip_testing_count is not None:
            self.skip_testing_count = skip_testing_count

    def read_phase_log(self, phase: int, session_id: str = None,
                       max_chars: int = 8000) -> Optional[str]:
        """
        Read the most recent log file for a given phase, optionally filtered
        by session_id.

        When session_id is provided, only logs from that session are considered
        (matching the YYYYMMDD_HHMMSS pattern in the filename). This ensures
        we read the log from the *current* orchestrator run, not stale logs
        from previous runs.

        When session_id is None, uses self.session_id as default filter.
        Pass session_id="" (empty string) to explicitly skip filtering and
        get the most recent log regardless of session — useful for cross-phase
        reads where the previous phase ran in a different session.

        Args:
            phase: Phase number (0-7)
            session_id: Session timestamp to match (e.g., "20260226_125323").
                        None = use self.session_id; "" = no filter (most recent).
            max_chars: Maximum characters to return (truncates from the end).

        Returns:
            Log file content as string, or None if no matching log found.
        """
        phase_dir = self._get_phase_dir(phase)
        if not phase_dir.exists():
            return None

        # None → use self.session_id; "" → no filter
        sid = self.session_id if session_id is None else session_id

        # Find matching log files
        md_files = sorted(phase_dir.glob("r*.md"), key=lambda p: p.stat().st_mtime)
        if not md_files:
            return None

        if sid:
            # Filter to logs from this session
            matching = [f for f in md_files if sid in f.name]
            if not matching:
                logger.debug(f"No phase {phase} logs matching session_id={sid}")
                return None
            # Use the most recent matching file (last by mtime)
            target = matching[-1]
        else:
            # No session filter — use most recent
            target = md_files[-1]

        try:
            content = target.read_text()
            if len(content) > max_chars:
                content = content[:max_chars] + f"\n\n... [truncated at {max_chars} chars]"
            logger.info(f"Read phase {phase} log: {target.name} ({len(content)} chars)")
            return content
        except Exception as e:
            logger.warning(f"Could not read phase log {target}: {e}")
            return None

    def _format_iteration_line(self, phase: int = None) -> str:
        """
        Format the iteration context line for log headers.

        - Phases 3 & 4: round + cycle + iteration (three loops)
        - Phases 5 & 6: round + cycle (two loops)
        - Phases 0-2: round only
        """
        if phase in (3, 4):
            iter_in_exp = self.skip_testing_count + 1  # 1-based inner loop counter
            return (f"**Round:** {self.calibration_round} | "
                    f"**Cycle:** {self.experiment_count} | "
                    f"**Iteration:** {iter_in_exp}")
        elif phase in (5, 6):
            return (f"**Round:** {self.calibration_round} | "
                    f"**Cycle:** {self.experiment_count}")
        else:
            return f"**Round:** {self.calibration_round}"

    def _format_metadata_block(self, phase: int, phase_name: str,
                               extra: Dict = None) -> str:
        """
        Generate a structured metadata JSON block for machine-readable parsing.

        Appended at the end of every log file.
        Includes experiment_count and skip_testing_count only for phases 3 & 4.
        """
        metadata = {
            "calibration_round": self.calibration_round,
            "iteration": self.current_iteration,
            "phase": phase,
            "phase_name": phase_name,
            "timestamp": datetime.now().isoformat(),
            "site": self.site_name
        }
        if self.session_id:
            metadata["session_id"] = self.session_id
        # Only include skip testing counters for phases where they matter
        if phase in (3, 4):
            metadata["experiment_count"] = self.experiment_count
            metadata["skip_testing_count"] = self.skip_testing_count
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
{self._format_iteration_line(phase=0)}
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
{self._format_iteration_line(phase=1)}
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
{self._format_iteration_line(phase=2)}
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
                      figure_paths: List[str] = None,
                      figure_analyses: List = None,
                      # Rich diagnosis fields from AI JSON
                      severity_breakdown: Dict = None,
                      root_causes: List[Dict] = None,
                      key_insights: List[str] = None,
                      comparative_analysis: Dict = None,
                      protocol_recommendations: List[Dict] = None,
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
            figure_analyses: AI visual observations for figures. List of dicts
                with 'figure' (keyword matching filename) and 'analysis' (description).
                Can also be a list of plain strings (backward compat).
            metadata: Additional metadata
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        content = f"""# {title}

**Site:** {self.site_name}
**Phase:** 3 - Diagnosis
{self._format_iteration_line(phase=3)}
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

        if severity_breakdown:
            content += """
---

## Severity Breakdown

"""
            for level in ['critical', 'high', 'medium', 'low']:
                targets = severity_breakdown.get(level, [])
                if targets:
                    content += f"**{level.upper()}:** {', '.join(targets)}\n\n"

        if root_causes:
            content += """
---

## Root Causes (Ranked)

| Rank | Cause | Mechanism | Confidence | Affected Targets |
|------|-------|-----------|------------|-----------------|
"""
            for rc in root_causes:
                rank = rc.get('rank', '?')
                cause = rc.get('cause', '')
                mechanism = rc.get('mechanism', '')
                conf = rc.get('confidence', 0)
                affected = ', '.join(rc.get('affected_targets', []))
                content += f"| {rank} | {cause} | {mechanism} | {conf:.2f} | {affected} |\n"
            content += "\n"

        if key_insights:
            content += """
---

## Key Insights

"""
            for i, insight in enumerate(key_insights, 1):
                content += f"{i}. {insight}\n"
            content += "\n"

        if comparative_analysis:
            content += """
---

## Comparative Case Analysis

"""
            best_id = comparative_analysis.get('best_case_id', 'N/A')
            lc_id = comparative_analysis.get('lowest_cost_case_id', 'N/A')
            rec = comparative_analysis.get('recommended_starting_case', 'N/A')
            rationale = comparative_analysis.get('rationale', '')
            content += f"- **Best case (targets):** #{best_id}\n"
            content += f"- **Lowest cost case:** #{lc_id}\n"
            content += f"- **Recommended starting case:** #{rec}\n"
            if rationale:
                content += f"- **Rationale:** {rationale}\n"
            content += "\n"

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

        if protocol_recommendations:
            content += """
---

## Protocol Recommendations

"""
            for rec in protocol_recommendations:
                setting = rec.get('setting', 'Unknown')
                current = rec.get('current_value', '?')
                proposed = rec.get('proposed_value', '?')
                rationale = rec.get('rationale', '')
                respin = rec.get('requires_respin', True)
                priority = rec.get('priority', 0)
                content += f"### {setting} (Priority: {priority})\n"
                content += f"- **Current:** `{current}` → **Proposed:** `{proposed}`\n"
                content += f"- **Rationale:** {rationale}\n"
                content += f"- **Requires re-spinup:** {'Yes' if respin else 'No'}\n\n"

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

        if figure_paths:
            content += """
---

## Diagnostic Figures

"""
            # Build lookup from figure_analyses for matching descriptions to figures
            # Supports both structured dicts ({"figure": "keyword", "analysis": "..."})
            # and plain strings (backward compat, rendered as unmatched observations)
            analyses_lookup = {}  # keyword -> analysis text
            unmatched_analyses = []
            if figure_analyses:
                for entry in figure_analyses:
                    if isinstance(entry, dict) and entry.get('figure'):
                        analyses_lookup[entry['figure'].lower()] = entry.get('analysis', '')
                    elif isinstance(entry, str):
                        unmatched_analyses.append(entry)

            _session_id = os.environ.get('A2MC_SESSION_ID', '')
            if _session_id:
                _fig_rel_dir = f"../../phase_results/{_session_id}/phase3_diagnosis"
            else:
                _fig_rel_dir = "../../phase_results/phase3_diagnosis"
            for fig_path in figure_paths:
                fig_name = Path(fig_path).name
                content += f"![{fig_name}]({_fig_rel_dir}/{fig_name})\n\n"

                # Find matching analysis by checking if any keyword is in the filename
                fig_lower = fig_name.lower()
                for keyword, analysis in analyses_lookup.items():
                    if keyword in fig_lower and analysis:
                        content += f"> **AI Analysis:** {analysis}\n\n"
                        break

            # Render any unmatched plain-string observations at the end
            if unmatched_analyses:
                content += "### Additional Visual Observations\n\n"
                for obs in unmatched_analyses:
                    content += f"- {obs}\n"
                content += "\n"

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
                       figure_paths: List[str] = None,
                       metadata: Dict = None) -> Path:
        """Log Phase 4: Hypothesis with experimental design."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        content = f"""# {title}

**Site:** {self.site_name}
**Phase:** 4 - Hypothesis
{self._format_iteration_line(phase=4)}
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
            pft = param.get('pft')
            organ = param.get('organ')
            # Include PFT and organ in heading to disambiguate duplicate param names
            heading = name
            if pft is not None:
                heading += f" (PFT#{pft})"
            if organ is not None:
                organ_names = {1: 'leaf', 2: 'fineroot', 3: 'sapwood', 4: 'storage'}
                heading += f" [{organ_names.get(organ, f'organ={organ}')}]"
            content += f"### {heading}\n"
            content += f"- **Current:** {current}\n"
            content += f"- **Proposed:** {proposed}\n"
            content += f"- **Rationale:** {rationale}\n\n"

        # Render validation report if available in metadata
        if metadata and metadata.get('validation'):
            from reasoning.validation import format_validation_for_log, format_ai_review_for_log
            val = metadata['validation']
            # Accept both ValidationResult objects and dicts
            if hasattr(val, 'issues'):
                val_section = format_validation_for_log(val)
            else:
                val_section = ""
            if val_section:
                content += f"\n---\n\n{val_section}\n"

        # Render AI self-review if available in metadata
        if metadata and metadata.get('ai_review'):
            from reasoning.validation import format_ai_review_for_log
            review_section = format_ai_review_for_log(metadata['ai_review'])
            if review_section:
                content += f"\n---\n\n{review_section}\n"

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

        if figure_paths:
            content += """
---

## Diagnostic Figures

"""
            _session_id = os.environ.get('A2MC_SESSION_ID', '')
            if _session_id:
                _fig_rel_dir = f"../../phase_results/{_session_id}/phase3_diagnosis"
            else:
                _fig_rel_dir = "../../phase_results/phase3_diagnosis"
            for fig_path in figure_paths:
                fig_name = Path(fig_path).name
                content += f"![{fig_name}]({_fig_rel_dir}/{fig_name})\n\n"

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

    def log_experiment_design(self,
                             title: str,
                             hypothesis_name: str,
                             mechanism: str,
                             design_type: str,
                             base_case: str,
                             experiments: list,
                             metadata: Dict = None) -> Path:
        """Log Phase 5: Experiment design summary (before submission).

        Called after experiments are designed and parameter files are created,
        but before HPC submission.  Produces a Markdown table showing per-
        experiment parameter modifications.

        Args:
            title: Log title
            hypothesis_name: Name of the hypothesis being tested
            mechanism: Mechanistic explanation
            design_type: cumulative / factorial / single
            base_case: Base case ID
            experiments: List of experiment dicts from design_experiment_sequence,
                each with 'name', 'modifications' (list of {parameter, old_value,
                new_value, pft?}), and optionally 'param_file'.
            metadata: Additional metadata dict
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        content = f"""# {title}

**Site:** {self.site_name}
**Phase:** 5 - Testing (Experiment Design)
{self._format_iteration_line(phase=5)}
**Date:** {timestamp}

---

## Hypothesis

**Name:** {hypothesis_name}
**Mechanism:** {mechanism}
**Design:** {design_type}
**Base Case:** {base_case}

---

## Experiment Summary

| Exp | Parameters Modified | Changes |
|-----|-------------------|---------|
"""
        for exp in experiments:
            name = exp.get('name', '?')
            mods = exp.get('modifications', [])
            # Build parameter names column
            param_names = []
            changes = []
            for m in mods:
                pname = m.get('parameter', '?')
                pft = m.get('pft', '')
                if pft:
                    param_names.append(f"`{pname}` PFT{pft}")
                else:
                    param_names.append(f"`{pname}`")
                old = m.get('old_value', '?')
                new = m.get('new_value', '?')
                # Compute percent change
                try:
                    old_f = float(old)
                    new_f = float(new)
                    if old_f != 0:
                        pct = (new_f - old_f) / old_f * 100
                        changes.append(f"{old} → {new} ({pct:+.1f}%)")
                    else:
                        changes.append(f"{old} → {new}")
                except (ValueError, TypeError):
                    changes.append(f"{old} → {new}")

            params_str = ", ".join(param_names)
            changes_str = "; ".join(changes)
            content += f"| {name} | {params_str} | {changes_str} |\n"

        # Detailed per-experiment breakdown
        content += """
---

## Experiment Details

"""
        for exp in experiments:
            name = exp.get('name', '?')
            mods = exp.get('modifications', [])
            param_file = exp.get('param_file', '')
            content += f"### {name}\n\n"
            if param_file:
                content += f"**Parameter file:** `{Path(param_file).name}`\n\n"
            content += "| Parameter | PFT | Old Value | New Value | Change |\n"
            content += "|-----------|-----|-----------|-----------|--------|\n"
            for m in mods:
                pname = m.get('parameter', '?')
                pft = m.get('pft', '')
                old = m.get('old_value', '?')
                new = m.get('new_value', '?')
                try:
                    old_f = float(old)
                    new_f = float(new)
                    if old_f != 0:
                        pct = (new_f - old_f) / old_f * 100
                        change = f"{pct:+.1f}%"
                    else:
                        change = "N/A"
                except (ValueError, TypeError):
                    change = ""
                content += f"| `{pname}` | {pft} | {old} | {new} | {change} |\n"
            content += "\n"

        if metadata:
            content += f"""---

## Metadata

```json
{json.dumps(metadata, indent=2, default=str)}
```
"""

        content += self._format_metadata_block(5, "testing_design", metadata)

        return self._write_log(5, title, content)

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
{self._format_iteration_line(phase=5)}
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
{self._format_iteration_line(phase=6)}
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
                               calibration_round: int = None,
                               iteration: int = None,
                               experiment_count: int = None,
                               skip_testing_count: int = None) -> List[Path]:
        """
        Find logs matching specific iteration context.

        Args:
            phase: Phase number or name
            calibration_round: Filter by calibration round (None = any)
            iteration: Filter by iteration within experiment cycle (1-based, None = any)
                       For Phase 3&4: inner loop counter (= skip_testing_count + 1)
                       For Phase 5&6: overall iteration within round
            experiment_count: Filter by experiment count (None = any, Phase 3&4 only)
            skip_testing_count: Deprecated alias for iteration (kept for backward compat).
                               If provided and iteration is None, converts to iteration.

        Returns:
            List of matching log paths, sorted by name

        Examples:
            # All logs for round 2
            find_logs_by_iteration(3, calibration_round=2)

            # All logs for experiment 0, iteration 1
            find_logs_by_iteration(3, experiment_count=0, iteration=1)

            # All logs for experiment 1
            find_logs_by_iteration(3, experiment_count=1)
        """
        # Backward compat: convert skip_testing_count to iteration
        if skip_testing_count is not None and iteration is None:
            iteration = skip_testing_count + 1

        if isinstance(phase, str):
            for num, name in PHASES.items():
                if name == phase.lower():
                    phase = num
                    break
            else:
                return []

        phase_dir = self._get_phase_dir(phase)

        # Build glob pattern
        round_part = f"r{calibration_round:02d}" if calibration_round is not None else "r*"

        if phase in (3, 4, 5, 6):
            exp_part = f"_c{experiment_count:02d}" if experiment_count is not None else "_c*"
            iter_part = f"_iter{iteration:02d}" if iteration is not None else "_iter*"
            pattern = f"{round_part}{exp_part}{iter_part}_*.md"
        else:
            pattern = f"{round_part}_*.md"

        return sorted(phase_dir.glob(pattern))


def create_logger(site_dir: str = None) -> PhaseLogger:
    """Create a PhaseLogger instance for a site."""
    return PhaseLogger(site_dir=site_dir)


if __name__ == "__main__":
    # Test the logger
    # With session_id and experiment_count=1, skip_testing_count=3, filename will be:
    #   r02_exp01_iter04_20260212_143052_Title.md  (iter = skip + 1 = 4)
    logger = PhaseLogger(site_dir="use_cases/Kougarok", site_name="Kougarok",
                         session_id="20260212_143052",
                         calibration_round=2, iteration=2,
                         experiment_count=1, skip_testing_count=3)

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
