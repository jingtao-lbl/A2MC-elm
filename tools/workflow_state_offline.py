"""Offline-agent resume state (docs/31).

The autonomous agent resumes from a per-run `workflow_state_{sTAG}.json` (the WorkflowState
dataclass in orchestrator.py). The interactive (offline) agent has no run and no session_id —
it works continuously across days, keyed by calibration ROUND — so its resume brain is a
per-round singleton `use_cases/{site}/memory/workflow_state_offline_r{RR}.json`.

This is a SUBSET of WorkflowState (position/coordinate fields) + offline-only planning fields:
evidence is stored as POINTERS to topic-stems (the calibration logs hold the detail), plus
explicit open_threads / next_actions / decisions — the human-planning layer the online loop
has no place for (offline is a superset of online: it tracks everything online does, plus more).

Usage:
    from tools.workflow_state_offline import WorkflowStateOffline
    st = WorkflowStateOffline.load(calibration_round=5)      # or find_latest(site_dir)
    st.set_position(current_phase="diagnosis", experiment_count=0)
    st.add_diagnosis(stem, log_path, artifact_dir, one_line)
    st.add_thread("thread_id", summary="...", next_action="...", priority=1)
    st.save()
"""
import os
import re
import json
import glob
from collections import namedtuple
from pathlib import Path
from datetime import datetime

SCHEMA = "a2mc.offline_workflow_state.v1"

# The next workflow action a driver (the `calibration-goal` skill, docs/38 §4.3) should take,
# resolved PURELY from state. kind ∈ {"run_phase", "gate", "done"}:
#   run_phase  -> phase is the phase to run next (the driver ensures current_phase==phase, runs it)
#   gate       -> pause for a human decision (detail names the gate kind)
#   done       -> converged (Phase 7); clear the /goal
NextAction = namedtuple("NextAction", ["kind", "phase", "detail"])


class WorkflowStateOffline:
    """Per-round offline resume state (load / mutate / save)."""

    def __init__(self, site_dir=None, calibration_round=None, data=None):
        self.site_dir = Path(site_dir or os.environ.get("A2MC_USE_CASE_DIR")
                             or "use_cases/TEMPLATE")
        self.calibration_round = int(calibration_round
                                     or os.environ.get("A2MC_CALIBRATION_ROUND", "1"))
        self.site_name = os.environ.get("A2MC_SITE_NAME", self.site_dir.name)
        self.data = data if data is not None else self._blank()

    # ---- paths ----
    @property
    def path(self) -> Path:
        return (self.site_dir / "memory"
                / f"workflow_state_offline_r{self.calibration_round:02d}.json")

    def _blank(self) -> dict:
        today = datetime.now().strftime("%Y-%m-%d")
        return {
            "schema": SCHEMA,
            "note": ("Offline (interactive) agent resume brain — subset of WorkflowState + "
                     "offline planning fields; evidence is pointers to topic-stems, not blobs. "
                     "Per-round singleton (docs/31)."),
            "site": self.site_name,
            "calibration_round": self.calibration_round,
            "current_phase": "design",
            "experiment_count": 0,
            "skip_testing_count": 0,
            "converged": False,
            "started_at": today,
            "updated_at": today,
            "round_summary": "",
            "evidence": {"diagnoses": [], "hypotheses": [], "experiments": []},
            "open_threads": [],
            "next_actions": [],
            "decisions": [],
            # Phase-6 objective gate (docs/34). Filled before a converge/redesign/stop decision;
            # validate_phase6_decision() blocks a premature escalation. None until Phase 6.
            "phase6_decision": None,
            "provenance": {"authored_by": "offline (interactive) agent",
                           "spec": "docs/31_Offline_Agent_Logging_And_Artifact_Layout_Plan.md"},
        }

    # ---- load / save ----
    @classmethod
    def load(cls, calibration_round=None, site_dir=None):
        """Load the round's state file, or return a blank one if it doesn't exist yet."""
        inst = cls(site_dir=site_dir, calibration_round=calibration_round)
        if inst.path.exists():
            inst.data = json.loads(inst.path.read_text())
            inst.calibration_round = inst.data.get("calibration_round", inst.calibration_round)
        return inst

    @classmethod
    def find_latest(cls, site_dir=None):
        """Return the highest-round state instance on disk, or None if none exist."""
        base = Path(site_dir or os.environ.get("A2MC_USE_CASE_DIR") or "use_cases/TEMPLATE")
        best = None
        for p in glob.glob(str(base / "memory" / "workflow_state_offline_r*.json")):
            m = re.search(r"workflow_state_offline_r(\d+)\.json$", p)
            if m and (best is None or int(m.group(1)) > best):
                best = int(m.group(1))
        if best is None:
            return None
        return cls.load(calibration_round=best, site_dir=site_dir)

    def save(self) -> Path:
        self.data["updated_at"] = datetime.now().strftime("%Y-%m-%d")
        self.data["calibration_round"] = self.calibration_round
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2) + "\n")
        return self.path

    # ---- mutators ----
    def set_position(self, current_phase=None, experiment_count=None,
                     skip_testing_count=None, converged=None):
        for k, v in (("current_phase", current_phase),
                     ("experiment_count", experiment_count),
                     ("skip_testing_count", skip_testing_count),
                     ("converged", converged)):
            if v is not None:
                self.data[k] = v
        return self

    def add_evidence(self, kind, stem, log_path, artifact_dir="", one_line=""):
        """kind in {'diagnoses','hypotheses','experiments'}. Idempotent on stem."""
        bucket = self.data["evidence"].setdefault(kind, [])
        entry = {"stem": stem, "log_path": str(log_path),
                 "artifact_dir": str(artifact_dir), "one_line": one_line}
        bucket[:] = [e for e in bucket if e.get("stem") != stem] + [entry]
        return self

    def add_diagnosis(self, stem, log_path, artifact_dir="", one_line=""):
        return self.add_evidence("diagnoses", stem, log_path, artifact_dir, one_line)

    def add_thread(self, thread_id, summary, next_action="", priority=None, refs=None):
        """Add or replace an open thread (idempotent on thread_id)."""
        t = {"id": thread_id, "summary": summary, "next_action": next_action}
        if priority is not None:
            t["priority"] = priority
        if refs:
            t["refs"] = list(refs)
        threads = self.data["open_threads"]
        threads[:] = [x for x in threads if x.get("id") != thread_id] + [t]
        threads.sort(key=lambda x: x.get("priority", 99))
        return self

    def close_thread(self, thread_id):
        self.data["open_threads"] = [x for x in self.data["open_threads"]
                                     if x.get("id") != thread_id]
        return self

    def add_decision(self, decision, rationale="", date=None):
        self.data["decisions"].append({
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "decision": decision, "rationale": rationale})
        return self

    def set_next_actions(self, actions):
        self.data["next_actions"] = list(actions)
        return self

    # ---- Phase-6 objective gate (docs/34) ----

    #: allowed Phase-6 routing decisions (mirror the orchestrator state machine)
    PHASE6_DECISIONS = ("converge", "rethink_6to3", "redesign_6to0", "stop_model_dev")

    def set_phase6_decision(self, decision, binding_target="", next_targeted_experiment="NONE",
                            exhaustion_justification="", objective="", best_so_far="",
                            max_experiments=10):
        """Record a Phase-6 routing decision + the objective restatement it requires (docs/34).

        `next_targeted_experiment`: a named, in-range, target-aimed experiment aimed at
        `binding_target`, or the literal "NONE" if genuinely none remains.
        Call validate_phase6_decision() before acting on the result.
        """
        self.data["phase6_decision"] = {
            "objective": objective,
            "best_so_far": best_so_far,
            "binding_target": binding_target,
            "next_targeted_experiment": next_targeted_experiment,
            "exhaustion_justification": exhaustion_justification,
            "decision": decision,
            "experiment_count": self.data.get("experiment_count", 0),
            "max_experiments": max_experiments,
        }
        return self

    def validate_phase6_decision(self):
        """Return a list of gate violations for the current phase6_decision ([] = valid).

        The gate (docs/34) makes the offline agent restate the objective before it can escalate,
        so "stop → improve the model" cannot be the path of least resistance:
          - decision must be one of PHASE6_DECISIONS;
          - any non-converge decision needs a non-empty binding_target;
          - stop_model_dev / redesign_6to0 are INVALID while experiment_count < max_experiments
            AND a named next_targeted_experiment remains (that is a rethink_6to3);
          - stop_model_dev additionally REQUIRES next_targeted_experiment == "NONE" AND a non-empty
            exhaustion_justification (you may not stop with a lever on the table).
        """
        d = self.data.get("phase6_decision")
        errs = []
        if not d:
            return ["phase6_decision not set — fill it before a Phase-6 routing decision (docs/34)"]
        dec = d.get("decision")
        if dec not in self.PHASE6_DECISIONS:
            return [f"decision '{dec}' not in {self.PHASE6_DECISIONS}"]
        ec = d.get("experiment_count", 0)
        mx = d.get("max_experiments", 10)
        nxt = (d.get("next_targeted_experiment") or "").strip()
        has_named = bool(nxt) and nxt.upper() != "NONE"
        if dec != "converge" and not (d.get("binding_target") or "").strip():
            errs.append("binding_target is required for a non-converge decision — name the "
                        "specific failing target (feedback_performance_experiment_is_the_objective)")
        if dec in ("stop_model_dev", "redesign_6to0") and ec < mx and has_named:
            errs.append(
                f"decision '{dec}' is invalid while experiment_count ({ec}) < max_experiments "
                f"({mx}) and a named in-range experiment remains ('{nxt}') — that is a rethink_6to3; "
                f"run it first (feedback_performance_experiment_is_the_objective).")
        if dec == "stop_model_dev":
            if has_named:
                errs.append("stop_model_dev requires next_targeted_experiment == NONE — you may not "
                            "stop with a named parameter experiment still on the table.")
            if not (d.get("exhaustion_justification") or "").strip():
                errs.append("stop_model_dev requires a non-empty exhaustion_justification "
                            "(why no in-range target-aimed experiment remains).")
            # A self-authored exhaustion_justification is NOT sufficient BELOW the loop limit:
            # declaring "next_targeted_experiment == NONE" at a low experiment_count is exactly
            # the documented premature-stop failure (2026-07-21: stop_model_dev asserted at
            # experiment_count 0/10 while an untested, source-verified residence lever remained
            # — found in the very next cycle). The middle loop exists to TEST the "it's futile"
            # conviction, not to trust it. An early stop needs explicit HUMAN sign-off.
            if ec < mx and not bool(d.get("human_confirmed_exhaustion")):
                errs.append(
                    f"stop_model_dev at experiment_count ({ec}) < max_experiments ({mx}) requires "
                    f"human_confirmed_exhaustion=true. A self-declared next_targeted_experiment==NONE "
                    f"is not sufficient below the loop limit (feedback_never_self_declare_exhaustion): "
                    f"either drive the remaining cycles (rethink_6to3) or get explicit human sign-off.")
        return errs

    # Phases 0-5 are executed directly; phase 6 (refinement) is the convergence fork.
    RUNNABLE_PHASES = ("design", "exploration", "screening", "diagnosis", "hypothesis", "testing")

    def resolve_next_action(self) -> "NextAction":
        """Deterministic, PURE-state resolver for the offline convergence driver (docs/38 §4.3).

        Maps this state -> the next workflow action, encoding the phase graph + the Phase-6 fork:
          - converged                       -> done (Phase 7)
          - current_phase in 0..5           -> run_phase(current_phase)
          - current_phase == refinement:
              no phase6_decision            -> gate (make the converge/rethink/redesign/stop call)
              converge                      -> done
              rethink_6to3                  -> run_phase(diagnosis)   (driver: experiment_count++,
                                                                       set current_phase, clear decision)
              redesign_6to0                 -> run_phase(design)      (driver: calibration_round++, …)
              stop_model_dev                -> gate (human; earned only if validate_phase6_decision passes)

        NOTE: WAIT_HPC (an ensemble in flight) and the curated-KB-write / expensive-action gates are
        RUNTIME concerns the driver overlays (they depend on squeue/monitors, not on state), so they
        are deliberately NOT resolved here — this keeps the resolver pure + unit-testable.
        """
        d = self.data
        if d.get("converged"):
            return NextAction("done", "converged", "all targets met — Phase 7 CONVERGED")
        phase = d.get("current_phase", "design")
        if phase in self.RUNNABLE_PHASES:
            return NextAction("run_phase", phase, f"execute the {phase} phase skill")
        if phase == "refinement":
            dec = (d.get("phase6_decision") or {}).get("decision")
            if not dec:
                return NextAction("gate", "refinement",
                                  "Phase-6 converge/rethink/redesign/stop decision needed "
                                  "(fill phase6_decision, then validate_phase6_decision)")
            if dec == "converge":
                return NextAction("done", "converged", "Phase-6 decided converge — Phase 7 CONVERGED")
            if dec == "rethink_6to3":
                return NextAction("run_phase", "diagnosis",
                                  "Phase-6 rethink — next experiment cycle, back to diagnosis")
            if dec == "redesign_6to0":
                return NextAction("run_phase", "design",
                                  "Phase-6 redesign — widen the space, next calibration round")
            if dec == "stop_model_dev":
                return NextAction("gate", "refinement",
                                  "Phase-6 stop -> model-dev — HUMAN gate (must pass validate_phase6_decision)")
            return NextAction("gate", "refinement", f"unknown phase6 decision '{dec}'")
        return NextAction("gate", phase, f"unknown current_phase '{phase}' — resolve manually")

    # ---- read helpers (for the SessionStart hook) ----
    def summary_line(self) -> str:
        """One-line snapshot for cold start, e.g. the SessionStart hook."""
        d = self.data
        nt = len(d.get("open_threads", []))
        nxt = ""
        if d.get("open_threads"):
            nxt = " (→ next: %s)" % (d["open_threads"][0].get("next_action", "")[:80])
        return "R%s · %s · cycle %s · %d open thread%s%s" % (
            d.get("calibration_round"), d.get("current_phase"),
            d.get("experiment_count"), nt, "" if nt == 1 else "s", nxt)


if __name__ == "__main__":
    # tiny self-check (no file writes): build a blank, mutate, print
    st = WorkflowStateOffline(site_dir="use_cases/TEMPLATE", calibration_round=5)
    st.set_position(current_phase="diagnosis", experiment_count=0)
    st.add_diagnosis("20260704a_phase3_diagnosis_r05_c00_iter01_demo",
                     "logs/demo.md", "phase_results/demo/", "demo one-liner")
    st.add_thread("demo_thread", summary="do the thing", next_action="cap the bound", priority=1)
    print("path:", st.path)
    print("summary:", st.summary_line())
    print("evidence diagnoses:", len(st.data["evidence"]["diagnoses"]))
