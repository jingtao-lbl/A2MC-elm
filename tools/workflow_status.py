#!/usr/bin/env python3
"""
Master Workflow Status Tracker for A2MC

Maintains a master log of workflow progress, making it easy to:
1. See current workflow status at a glance
2. Know which phase is running and where to check logs
3. Track phase completion history
4. Identify where the workflow got stuck

Master log location: memory/workflow_log.json

Usage:
    # Check status from command line
    python tools/workflow_status.py

    # Check status from Python
    from tools.workflow_status import WorkflowStatus, show_status
    status = WorkflowStatus()
    status.show()

    # In orchestrator - update status at phase transitions
    status = WorkflowStatus()
    status.start_phase(3, "diagnosis", iteration=2)
    status.complete_phase(3, "diagnosis", log_file="20260115_140000_diagnosis.json")

Author: Jing Tao
Created: January 2026
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict


# Phase definitions (matching orchestrator.py)
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

# Status values
STATUS_RUNNING = "running"
STATUS_PAUSED = "paused"
STATUS_FAILED = "failed"
STATUS_CONVERGED = "converged"
STATUS_NOT_STARTED = "not_started"

# Phase status values
PHASE_PENDING = "pending"
PHASE_IN_PROGRESS = "in_progress"
PHASE_COMPLETED = "completed"
PHASE_FAILED = "failed"
PHASE_SKIPPED = "skipped"


@dataclass
class PhaseStatus:
    """Status of a single phase."""
    phase: int
    phase_name: str
    status: str = PHASE_PENDING  # pending, in_progress, completed, failed, skipped
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    log_file: Optional[str] = None
    error: Optional[str] = None
    iteration: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'PhaseStatus':
        return cls(**data)


@dataclass
class WorkflowLog:
    """Master workflow log structure."""
    # Workflow identification
    workflow_id: str = ""
    use_case: str = ""  # e.g., "Kougarok"

    # Current status
    status: str = STATUS_NOT_STARTED  # running, paused, failed, converged, not_started
    current_phase: int = 0
    current_phase_name: str = "design"
    iteration: int = 0

    # Timestamps
    created_at: str = ""
    started_at: Optional[str] = None
    updated_at: str = ""

    # Phase tracking
    phase_status: Dict[str, Dict] = field(default_factory=dict)

    # Error tracking
    last_error: Optional[str] = None
    error_phase: Optional[int] = None
    error_timestamp: Optional[str] = None

    # Quick reference
    check_logs_at: str = ""

    # History
    events: List[Dict] = field(default_factory=list)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.workflow_id:
            self.workflow_id = f"a2mc_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        # Initialize phase status for all phases
        if not self.phase_status:
            for phase_num, phase_name in PHASES.items():
                key = f"phase{phase_num}_{phase_name}"
                self.phase_status[key] = PhaseStatus(
                    phase=phase_num,
                    phase_name=phase_name
                ).to_dict()

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'WorkflowLog':
        return cls(**data)


class WorkflowStatus:
    """
    Master workflow status tracker.

    Maintains a persistent log of workflow progress at:
        memory/workflow_log.json
    """

    def __init__(self, log_dir: str = "memory", auto_load: bool = True):
        """
        Initialize workflow status tracker.

        Args:
            log_dir: Directory containing workflow_log.json
            auto_load: If True, load existing log if present
        """
        self.log_dir = Path(log_dir)
        self.log_file = self.log_dir / "workflow_log.json"
        self.phase_results_dir = self.log_dir / "phase_results"

        # Initialize or load log
        if auto_load and self.log_file.exists():
            self.log = self._load()
        else:
            self.log = WorkflowLog()
            self._save()

    def _load(self) -> WorkflowLog:
        """Load workflow log from file."""
        with open(self.log_file, 'r') as f:
            data = json.load(f)
        return WorkflowLog.from_dict(data)

    def _save(self):
        """Save workflow log to file."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log.updated_at = datetime.now().isoformat()
        with open(self.log_file, 'w') as f:
            json.dump(self.log.to_dict(), f, indent=2)

    def _add_event(self, event_type: str, details: Dict):
        """Add event to history."""
        self.log.events.append({
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "phase": self.log.current_phase,
            "iteration": self.log.iteration,
            **details
        })
        # Keep last 100 events
        if len(self.log.events) > 100:
            self.log.events = self.log.events[-100:]

    def _get_phase_key(self, phase: int) -> str:
        """Get phase key for phase_status dict."""
        phase_name = PHASES.get(phase, f"unknown")
        return f"phase{phase}_{phase_name}"

    def _update_check_logs_at(self):
        """Update the check_logs_at path based on current phase."""
        phase_name = PHASES.get(self.log.current_phase, "unknown")
        self.log.check_logs_at = f"memory/phase_results/phase{self.log.current_phase}_{phase_name}/"

    # =========================================================================
    # Workflow-level operations
    # =========================================================================

    def start_workflow(self, use_case: str = "", workflow_id: str = ""):
        """Mark workflow as started."""
        if workflow_id:
            self.log.workflow_id = workflow_id
        if use_case:
            self.log.use_case = use_case

        self.log.status = STATUS_RUNNING
        self.log.started_at = datetime.now().isoformat()
        self.log.current_phase = 0
        self.log.current_phase_name = "design"
        self.log.iteration = 0
        self._update_check_logs_at()

        self._add_event("workflow_started", {"use_case": use_case})
        self._save()

    def pause_workflow(self, reason: str = ""):
        """Mark workflow as paused."""
        self.log.status = STATUS_PAUSED
        self._add_event("workflow_paused", {"reason": reason})
        self._save()

    def resume_workflow(self):
        """Resume paused workflow."""
        self.log.status = STATUS_RUNNING
        self._add_event("workflow_resumed", {})
        self._save()

    def fail_workflow(self, error: str, phase: Optional[int] = None):
        """Mark workflow as failed."""
        self.log.status = STATUS_FAILED
        self.log.last_error = error
        self.log.error_phase = phase if phase is not None else self.log.current_phase
        self.log.error_timestamp = datetime.now().isoformat()

        self._add_event("workflow_failed", {"error": error})
        self._save()

    def complete_workflow(self):
        """Mark workflow as converged/completed."""
        self.log.status = STATUS_CONVERGED
        self.log.current_phase = 7
        self.log.current_phase_name = "converged"

        self._add_event("workflow_converged", {
            "total_iterations": self.log.iteration
        })
        self._save()

    # =========================================================================
    # Phase-level operations
    # =========================================================================

    def start_phase(self, phase: int, phase_name: str = None, iteration: int = None):
        """Mark a phase as started."""
        if phase_name is None:
            phase_name = PHASES.get(phase, "unknown")
        if iteration is not None:
            self.log.iteration = iteration

        self.log.current_phase = phase
        self.log.current_phase_name = phase_name
        self.log.status = STATUS_RUNNING
        self._update_check_logs_at()

        # Update phase status
        key = self._get_phase_key(phase)
        if key in self.log.phase_status:
            self.log.phase_status[key]["status"] = PHASE_IN_PROGRESS
            self.log.phase_status[key]["started_at"] = datetime.now().isoformat()
            self.log.phase_status[key]["iteration"] = self.log.iteration
            self.log.phase_status[key]["error"] = None

        self._add_event("phase_started", {"phase": phase, "phase_name": phase_name})
        self._save()

    def complete_phase(self, phase: int, phase_name: str = None,
                       log_file: str = None, next_phase: int = None):
        """Mark a phase as completed."""
        if phase_name is None:
            phase_name = PHASES.get(phase, "unknown")

        key = self._get_phase_key(phase)
        now = datetime.now().isoformat()

        if key in self.log.phase_status:
            phase_data = self.log.phase_status[key]
            phase_data["status"] = PHASE_COMPLETED
            phase_data["completed_at"] = now
            phase_data["log_file"] = log_file

            # Calculate duration
            if phase_data.get("started_at"):
                started = datetime.fromisoformat(phase_data["started_at"])
                completed = datetime.fromisoformat(now)
                phase_data["duration_seconds"] = (completed - started).total_seconds()

        self._add_event("phase_completed", {
            "phase": phase,
            "phase_name": phase_name,
            "log_file": log_file
        })

        # Advance to next phase if specified
        if next_phase is not None:
            self.start_phase(next_phase)

        self._save()

    def fail_phase(self, phase: int, error: str, phase_name: str = None):
        """Mark a phase as failed."""
        if phase_name is None:
            phase_name = PHASES.get(phase, "unknown")

        key = self._get_phase_key(phase)
        if key in self.log.phase_status:
            self.log.phase_status[key]["status"] = PHASE_FAILED
            self.log.phase_status[key]["error"] = error
            self.log.phase_status[key]["completed_at"] = datetime.now().isoformat()

        self.log.last_error = error
        self.log.error_phase = phase
        self.log.error_timestamp = datetime.now().isoformat()

        self._add_event("phase_failed", {
            "phase": phase,
            "phase_name": phase_name,
            "error": error
        })
        self._save()

    def set_iteration(self, iteration: int):
        """Update the current iteration number."""
        self.log.iteration = iteration
        self._add_event("iteration_changed", {"iteration": iteration})
        self._save()

    # =========================================================================
    # Status display
    # =========================================================================

    def get_status_dict(self) -> Dict:
        """Get current status as dictionary."""
        return self.log.to_dict()

    def get_summary(self) -> Dict:
        """Get a brief status summary."""
        # Calculate phases completed
        phases_completed = sum(
            1 for ps in self.log.phase_status.values()
            if ps.get("status") == PHASE_COMPLETED
        )

        return {
            "workflow_id": self.log.workflow_id,
            "status": self.log.status,
            "current_phase": self.log.current_phase,
            "current_phase_name": self.log.current_phase_name,
            "iteration": self.log.iteration,
            "phases_completed": phases_completed,
            "total_phases": len(PHASES) - 1,  # Exclude "converged"
            "check_logs_at": self.log.check_logs_at,
            "last_error": self.log.last_error
        }

    def show(self, detailed: bool = False):
        """Print formatted status to console."""
        print("\n" + "=" * 50)
        print("A2MC Workflow Status")
        print("=" * 50)

        # Basic info
        status_emoji = {
            STATUS_RUNNING: "▶",
            STATUS_PAUSED: "⏸",
            STATUS_FAILED: "✗",
            STATUS_CONVERGED: "✓",
            STATUS_NOT_STARTED: "○"
        }

        emoji = status_emoji.get(self.log.status, "?")
        print(f"Status:     {emoji} {self.log.status.upper()}")
        print(f"Workflow:   {self.log.workflow_id}")
        if self.log.use_case:
            print(f"Use Case:   {self.log.use_case}")
        print(f"Phase:      {self.log.current_phase} - {self.log.current_phase_name.upper()}")
        print(f"Iteration:  {self.log.iteration}")

        # Time info
        if self.log.started_at:
            started = datetime.fromisoformat(self.log.started_at)
            elapsed = datetime.now() - started
            hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            print(f"Running:    {hours}h {minutes}m {seconds}s")

        print(f"Updated:    {self.log.updated_at[:19] if self.log.updated_at else 'N/A'}")

        # Phase history
        print("\nPhase History:")
        for phase_num in range(8):
            key = self._get_phase_key(phase_num)
            if key not in self.log.phase_status:
                continue

            ps = self.log.phase_status[key]
            phase_name = ps.get("phase_name", PHASES.get(phase_num, "unknown"))
            status = ps.get("status", PHASE_PENDING)

            # Status indicator
            if status == PHASE_COMPLETED:
                indicator = "✓"
            elif status == PHASE_IN_PROGRESS:
                indicator = "→"
            elif status == PHASE_FAILED:
                indicator = "✗"
            else:
                indicator = "○"

            # Duration
            duration_str = ""
            if ps.get("duration_seconds"):
                dur = ps["duration_seconds"]
                if dur >= 3600:
                    duration_str = f" ({dur/3600:.1f}h)"
                elif dur >= 60:
                    duration_str = f" ({dur/60:.1f}m)"
                else:
                    duration_str = f" ({dur:.0f}s)"
            elif status == PHASE_IN_PROGRESS and ps.get("started_at"):
                started = datetime.fromisoformat(ps["started_at"])
                elapsed = (datetime.now() - started).total_seconds()
                if elapsed >= 60:
                    duration_str = f" ({elapsed/60:.0f}m in progress)"
                else:
                    duration_str = f" ({elapsed:.0f}s in progress)"

            # Iteration info
            iter_str = ""
            if ps.get("iteration", 0) > 0:
                iter_str = f" [iter {ps['iteration']}]"

            print(f"  {indicator} Phase {phase_num} ({phase_name}){duration_str}{iter_str}")

            if detailed and ps.get("log_file"):
                print(f"      Log: {ps['log_file']}")

        # Error info
        if self.log.last_error:
            print(f"\nLast Error (Phase {self.log.error_phase}):")
            print(f"  {self.log.last_error[:100]}...")

        # Where to check logs
        if self.log.check_logs_at:
            print(f"\nCheck logs: {self.log.check_logs_at}")

        print("=" * 50 + "\n")

    def show_json(self):
        """Print status as JSON."""
        print(json.dumps(self.log.to_dict(), indent=2))


def show_status(log_dir: str = "memory", detailed: bool = False):
    """Convenience function to show workflow status."""
    status = WorkflowStatus(log_dir)
    status.show(detailed)


def get_status(log_dir: str = "memory") -> Dict:
    """Convenience function to get workflow status as dict."""
    status = WorkflowStatus(log_dir)
    return status.get_summary()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="A2MC Workflow Status")
    parser.add_argument("--detailed", "-d", action="store_true",
                       help="Show detailed status including log files")
    parser.add_argument("--json", "-j", action="store_true",
                       help="Output as JSON")
    parser.add_argument("--log-dir", default="memory",
                       help="Directory containing workflow_log.json")

    args = parser.parse_args()

    status = WorkflowStatus(args.log_dir)

    if args.json:
        status.show_json()
    else:
        status.show(detailed=args.detailed)
