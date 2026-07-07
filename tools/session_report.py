#!/usr/bin/env python3
"""
Session Report Generator

Collects all session artifacts (logs, figures) and generates a comprehensive
Markdown report via AI API at the end of a calibration session.

The report covers:
- Screening baseline and top cases
- Diagnosis evolution with figure references and interpretations
- Hypothesis evolution and skip-testing results
- Experiment designs and outcomes
- Key discoveries and lessons learned
- Recommendations for next steps

Author: Jing Tao with Claude
"""

import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Offline (interactive-agent) topic-stem: YYYYMMDDx_phase{N}_{name}_r{RR}[...]_{descriptor}.md
# (docs/31). The phase + round are in the filename; the log is flat in logs/ (no session_id level).
OFFLINE_STEM_RE = re.compile(r"^\d{8}[a-z]_(phase\d+_[a-z]+)_r(\d+)")


def collect_offline_artifacts(site_dir: str, calibration_round: int = None) -> Dict:
    """Collect flat offline topic-stem logs + figures so they fold into synthesis (docs/31).

    The autonomous agent's logs are session-scoped (logs/{session_id}/{phase}/); the
    interactive agent's are flat topic-stems (logs/{stem}.md) with the phase in the name.
    This groups them by phase like collect_session_artifacts, so build_report_prompt picks
    them up unchanged. Optionally filter to one calibration round.

    Figure rel paths assume the report is written at logs/ root (the natural home for an
    offline round synthesis): ../phase_results/{stem}/.

    Args:
        site_dir: use_cases/{site}/ directory
        calibration_round: if set, only include logs whose stem carries _r{RR}
    Returns:
        {logs: {phase: [ {filename, content} ]}, figures: {...}, figure_rel_paths: {...}}
    """
    site_path = Path(site_dir)
    logs_dir = site_path / "memory" / "logs"
    pr_dir = site_path / "memory" / "phase_results"
    out = {"logs": {}, "figures": {}, "figure_rel_paths": {}}
    if not logs_dir.exists():
        return out

    # glob("*.md") is non-recursive → flat offline logs only, not session_id/ subdirs.
    for lf in sorted(logs_dir.glob("*.md")):
        m = OFFLINE_STEM_RE.match(lf.name)
        if not m:
            continue
        phase_name, rr = m.group(1), int(m.group(2))
        if calibration_round is not None and rr != int(calibration_round):
            continue
        try:
            content = lf.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not read offline log {lf}: {e}")
            continue
        out["logs"].setdefault(phase_name, []).append(
            {"filename": lf.name, "content": content})

        # Paired artifact folder phase_results/{stem}/ (stem = filename without .md)
        topic = pr_dir / lf.stem
        if topic.exists():
            figs = sorted(topic.glob("*.png"))
            if figs:
                out["figures"].setdefault(phase_name, []).extend(str(f) for f in figs)
                rel = f"../phase_results/{lf.stem}"
                out["figure_rel_paths"].setdefault(phase_name, []).extend(
                    f"{rel}/{f.name}" for f in figs)
    return out


def collect_session_artifacts(site_dir: str, session_id: str,
                              include_offline: bool = False,
                              calibration_round: int = None) -> Dict:
    """Collect all logs and figure paths for a session.

    Args:
        site_dir: Path to use_cases/{site}/ directory
        session_id: Session timestamp (YYYYMMDD_HHMMSS)
        include_offline: also fold in flat offline topic-stem logs (docs/31), grouped by
                         the same phase buckets so build_report_prompt picks them up.
        calibration_round: when include_offline, restrict offline logs to this round.

    Returns:
        Dict with keys: logs (Dict[phase_name, List[str]]),
                        figures (Dict[phase_name, List[str]]),
                        figure_rel_paths (Dict[phase_name, List[str]])
    """
    site_path = Path(site_dir)
    logs_base = site_path / "memory" / "logs" / session_id
    results_base = site_path / "memory" / "phase_results" / session_id

    artifacts = {
        "logs": {},
        "figures": {},
        "figure_rel_paths": {},
        "session_id": session_id,
    }

    # Collect logs (Markdown files) per phase
    phase_dirs = [
        "phase1_exploration", "phase2_screening", "phase3_diagnosis",
        "phase4_hypothesis", "phase5_testing", "phase6_refinement",
    ]

    for phase_name in phase_dirs:
        log_dir = logs_base / phase_name
        if not log_dir.exists():
            continue

        log_files = sorted(log_dir.glob("*.md"))
        if log_files:
            log_contents = []
            for lf in log_files:
                try:
                    content = lf.read_text(encoding="utf-8")
                    log_contents.append({
                        "filename": lf.name,
                        "content": content,
                    })
                except Exception as e:
                    logger.warning(f"Could not read log {lf}: {e}")
            artifacts["logs"][phase_name] = log_contents

    # Collect figure paths per phase
    for phase_name in phase_dirs:
        fig_dir = results_base / phase_name
        if not fig_dir.exists():
            continue

        fig_files = sorted(fig_dir.glob("*.png"))
        if fig_files:
            artifacts["figures"][phase_name] = [str(f) for f in fig_files]
            # Relative paths from report location (logs/{session_id}/) to
            # phase_results/{session_id}/{phase}/
            rel_dir = f"../../phase_results/{session_id}/{phase_name}"
            artifacts["figure_rel_paths"][phase_name] = [
                f"{rel_dir}/{f.name}" for f in fig_files
            ]

    # Also check for phase1 figures in flat layout (not session-scoped)
    flat_phase1 = site_path / "memory" / "phase_results" / "phase1_exploration"
    if flat_phase1.exists() and "phase1_exploration" not in artifacts["figures"]:
        fig_files = sorted(flat_phase1.glob("*.png"))
        if fig_files:
            artifacts["figures"]["phase1_exploration"] = [str(f) for f in fig_files]
            rel_dir = "../../phase_results/phase1_exploration"
            artifacts["figure_rel_paths"]["phase1_exploration"] = [
                f"{rel_dir}/{f.name}" for f in fig_files
            ]

    # Fold in flat offline topic-stem logs/figures (docs/31) so both agent modes synthesize.
    if include_offline:
        off = collect_offline_artifacts(site_dir, calibration_round)
        for key in ("logs", "figures", "figure_rel_paths"):
            for phase_name, items in off[key].items():
                artifacts[key].setdefault(phase_name, []).extend(items)

    return artifacts


def build_report_prompt(artifacts: Dict, state_summary: Dict) -> str:
    """Build the AI prompt from collected artifacts and orchestrator state.

    Args:
        artifacts: Output from collect_session_artifacts()
        state_summary: Dict with calibration state info:
            - site_name, calibration_round, session_id
            - n_params, n_ensembles, sampling_scheme
            - targets (list of target names)
            - best_experiment (dict or None)
            - converged (bool)
            - iteration, experiment_count
            - exit_reason (str)

    Returns:
        Prompt string for the AI
    """
    sections = []

    # Header context
    exp_cycle_num = state_summary.get('experiment_cycle_number',
                                      state_summary.get('experiment_count', 0) + 1)
    skip_testing_count = state_summary.get('skip_testing_count', '?')

    sections.append(f"""You are generating a comprehensive session report for an A2MC calibration session.

**Session:** {state_summary.get('session_id', '?')}
**Site:** {state_summary.get('site_name', '?')}
**Calibration Round:** {state_summary.get('calibration_round', '?')}
**Parameters:** {state_summary.get('n_params', '?')} ({state_summary.get('sampling_scheme', '?')} sampling)
**Ensemble Size:** {state_summary.get('n_ensembles', '?')}
**Targets:** {', '.join(state_summary.get('targets', []))}
**Outcome:** {'CONVERGED' if state_summary.get('converged') else state_summary.get('exit_reason', 'in progress')}
**Current Experiment Cycle:** {exp_cycle_num} (Phase 3→4→5→6 cycle, matches `cEE` in phase log filenames)
**Skip-Testing Iterations in This Cycle:** {skip_testing_count} (Phase 3↔4 inner-loop iterations, matches `iterII`)

## CRITICAL: A2MC Three-Level Iteration Terminology

A2MC has THREE distinct iteration levels. DO NOT CONFUSE THEM in the report:

1. **Calibration Round** (outermost): A full Phase 0→7 cycle with a specific parameter set.
   - Example: Round 3 = 162 parameters, 4890 Morris simulations.
   - Incremented only when the parameter space is redesigned (Phase 6 → Phase 0).

2. **Experiment Cycle** (middle loop): One full Phase 3→4→5→6 cycle that runs NEW HPC experiments.
   - Labelled `c00`, `c01`, `c02`, ... in phase log filenames.
   - Incremented when Phase 6 returns to Phase 3 after HPC results disprove a hypothesis.
   - **This session is in Experiment Cycle {exp_cycle_num}.**

3. **Skip-Testing Iteration** (innermost loop): One Phase 3↔4 cycle that tests a hypothesis
   WITHOUT running new HPC simulations (uses existing Morris ensemble data).
   - Labelled `iter01`, `iter02`, ... in Phase 3/4 log filenames.
   - This cycle had **{skip_testing_count}** skip-testing iterations before going to HPC.

**When writing the report:**
- Use "Experiment Cycle N" ONLY for the Phase 3→4→5→6 outer cycle.
- Use "Iteration N" or "Skip-Testing Iteration N" for the Phase 3↔4 inner-loop iterations.
- DO NOT call skip-testing iterations "Cycle 1", "Cycle 2", etc. — that's reserved for experiment cycles.
- If you're describing the 10 diagnosis→hypothesis attempts before HPC, those are skip-testing iterations, NOT cycles.
""")

    # Add all phase logs
    for phase_name in [
        "phase1_exploration", "phase2_screening", "phase3_diagnosis",
        "phase4_hypothesis", "phase5_testing", "phase6_refinement",
    ]:
        logs = artifacts.get("logs", {}).get(phase_name, [])
        if not logs:
            continue

        sections.append(f"\n{'='*60}\n## {phase_name.upper()} LOGS\n{'='*60}")
        for log_entry in logs:
            sections.append(f"\n### File: {log_entry['filename']}\n")
            # Truncate very long logs to avoid exceeding context
            content = log_entry["content"]
            if len(content) > 15000:
                content = content[:15000] + "\n\n[... truncated for length ...]"
            sections.append(content)

    # Add figure inventory
    fig_rel = artifacts.get("figure_rel_paths", {})
    if fig_rel:
        sections.append(f"\n{'='*60}\n## AVAILABLE FIGURES\n{'='*60}")
        sections.append(
            "These figures are available for embedding in the report. "
            "Use the exact relative paths provided as Markdown image references."
        )
        for phase_name, paths in fig_rel.items():
            sections.append(f"\n### {phase_name}")
            for p in paths:
                fig_name = Path(p).stem
                sections.append(f"- `{p}` — {fig_name}")

    # Best experiment summary
    best = state_summary.get("best_experiment")
    if best:
        sections.append(f"\n{'='*60}\n## BEST EXPERIMENT RESULT\n{'='*60}")
        sections.append(f"Name: {best.get('name', 'N/A')}")
        results = best.get("results", {})
        sections.append(f"Targets met: {results.get('targets_met', '?')}/{state_summary.get('n_targets', '?')}")
        mods = best.get("modifications", [])
        if mods:
            sections.append("Parameter modifications:")
            for m in mods:
                sections.append(f"  - {m.get('parameter', '?')}: {m.get('old_value', '?')} → {m.get('new_value', '?')}")

    # Instructions
    sections.append(f"""

{'='*60}
## INSTRUCTIONS
{'='*60}

Generate a comprehensive Markdown session report. The report should be a
**self-contained narrative** that a scientist can read to understand what
happened in this calibration session.

Structure the report with these sections:

1. **Header** — Title, session metadata (site, round, date, parameters, targets)

2. **Executive Summary** — 3-5 sentence overview of the session: what was attempted,
   what was discovered, what the outcome was.

3. **Screening Baseline** — Top candidate cases, target satisfaction, cost metrics.
   Include the screening figure if available.

4. **Diagnosis Evolution** — For EACH skip-testing iteration (NOT cycle):
   - What targets were failing and why
   - The root cause analysis with confidence scores
   - **Embed ALL relevant diagnostic figures** using the markdown paths provided above
   - Describe what each figure shows (the log content has figure interpretations)
   - How understanding evolved from one iteration to the next
   - Label headings as "Iteration 1", "Iteration 2", ... NOT "Cycle 1", "Cycle 2"

5. **Hypothesis Evolution** — For EACH hypothesis (one per skip-testing iteration):
   - What was proposed and why
   - Skip-testing result (supported/not supported, confidence)
   - What was learned from the test
   - Label as "Iteration N Hypothesis" NOT "Cycle N Hypothesis"

6. **Experiment Design** — If experiments were synthesized:
   - Cumulative experiment structure
   - Parameter changes and rationale

7. **Experiment Results** — If Phase 5/6 data is available:
   - Which experiments improved targets
   - How results compared to predictions

8. **Key Discoveries** — Named mechanistic insights discovered during the session
   (e.g., "P Starvation Cascade", "ECA Competition Asymmetry")

9. **Recommendations** — Next steps based on session findings

IMPORTANT FORMATTING RULES:
- Embed figures using: ![description](relative_path)
- Place figures RIGHT AFTER the text that discusses them
- Use tables for parameter comparisons and target summaries
- Keep the narrative flowing — this is a REPORT, not a log dump
- Be specific with numbers: correlation coefficients, confidence scores, biomass values
- Reference specific case numbers when discussing results
- The report should be 800-1500 lines of Markdown

Output ONLY the Markdown report content (no JSON wrapper, no code fences around the entire output).
""")

    return "\n".join(sections)


def write_session_report(site_dir: str, session_id: str,
                         report_content: str,
                         calibration_round: int = None,
                         experiment_count: int = None) -> Path:
    """Write the session report to the logs directory.

    Filename includes round and experiment cycle counters when available
    so multiple session reports from the same session can coexist:
        session_report_r{RR}_c{EE}_{session_id}.md
    Falls back to session_report_{session_id}.md if counters not provided.

    Args:
        site_dir: Path to use_cases/{site}/
        session_id: Session timestamp
        report_content: Generated Markdown report
        calibration_round: Calibration round number (e.g., 3)
        experiment_count: Experiment cycle counter (0-indexed, e.g., 0 for first cycle)

    Returns:
        Path to the written report file
    """
    report_dir = Path(site_dir) / "memory" / "logs" / session_id
    report_dir.mkdir(parents=True, exist_ok=True)

    if calibration_round is not None and experiment_count is not None:
        prefix = f"r{calibration_round:02d}_c{experiment_count:02d}_"
    else:
        prefix = ""

    report_path = report_dir / f"session_report_{prefix}{session_id}.md"
    report_path.write_text(report_content, encoding="utf-8")

    logger.info(f"Session report written: {report_path}")
    return report_path
