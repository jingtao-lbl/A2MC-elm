#!/usr/bin/env python3
"""Invariant checker for the offline resume state (`workflow_state_offline_r{RR}.json`).

The state analog of `tools/check_skill_registry.py`. The offline convergence loop is *state on
disk + resolve_next_action() + the phase skills* (see `calibration-goal`), so a corrupt or stale
state file silently misdrives the whole workflow. This validates the file the driver trusts:

  ERRORS (exit 1 — the state would misdrive the loop):
    - wrong `schema`; `current_phase` not a real phase; counters out of range / wrong type;
      `converged` not a bool; an `open_thread` with no `id`; a `phase6_decision` that fails
      `validate_phase6_decision()` (e.g. a premature stop_model_dev/redesign while cycles remain).
  WARNINGS (exit 0 — worth a look, not a corruption):
    - an evidence pointer whose `log_path` no longer resolves on disk (logs get relocated/gitignored);
      an `open_thread` with no `next_action`; `current_phase == refinement` with no decision yet
      (a valid *pending-gate* state); `skip_testing_count` over the usual cap.

Stdlib-only (runs under system python3 + the SessionStart hook). Run from the repo root:
    python3 tools/check_workflow_state_offline.py            # all use_cases/*/…_r*.json
    python3 tools/check_workflow_state_offline.py --file <path>
    python3 tools/check_workflow_state_offline.py --quiet    # one line per file (for the hook)

Author: Jing Tao with Claude
"""
import argparse
import glob
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Load workflow_state_offline DIRECTLY by file (not `from tools.…`) so we bypass tools/__init__.py,
# which pulls in 3.7+ deps (dataclasses) — this keeps the checker runnable under system python 3.6
# (the SessionStart hook + the Tier-1 smoke context, same as check_skill_registry).
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "_wso_direct", str(Path(__file__).resolve().parent / "workflow_state_offline.py"))
_wso = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_wso)
WorkflowStateOffline, SCHEMA = _wso.WorkflowStateOffline, _wso.SCHEMA

VALID_PHASES = set(WorkflowStateOffline.RUNNABLE_PHASES) | {"refinement"}
SKIP_TESTING_CAP = 10  # --max-skip-testing default; not stored in state, so a soft cap


def check_one(path):
    """Return (errors, warnings) for one state file."""
    errors, warnings = [], []
    try:
        d = json.loads(Path(path).read_text())
    except Exception as e:
        return [f"unreadable / invalid JSON: {e}"], []

    if d.get("schema") != SCHEMA:
        errors.append(f"schema '{d.get('schema')}' != expected '{SCHEMA}'")

    cp = d.get("current_phase")
    if cp not in VALID_PHASES:
        errors.append(f"current_phase '{cp}' not in {sorted(VALID_PHASES)}")

    cr = d.get("calibration_round")
    if not isinstance(cr, int) or cr < 1:
        errors.append(f"calibration_round '{cr}' must be an int >= 1")

    mx = (d.get("phase6_decision") or {}).get("max_experiments", 10)
    ec = d.get("experiment_count", 0)
    if not isinstance(ec, int) or ec < 0:
        errors.append(f"experiment_count '{ec}' must be an int >= 0")
    elif ec > mx:
        errors.append(f"experiment_count ({ec}) exceeds max_experiments ({mx}) — middle loop overran")

    stc = d.get("skip_testing_count", 0)
    if not isinstance(stc, int) or stc < 0:
        errors.append(f"skip_testing_count '{stc}' must be an int >= 0")
    elif stc > SKIP_TESTING_CAP:
        warnings.append(f"skip_testing_count ({stc}) over the usual cap ({SKIP_TESTING_CAP})")

    if not isinstance(d.get("converged"), bool):
        errors.append(f"converged '{d.get('converged')}' must be a bool")

    for i, t in enumerate(d.get("open_threads", [])):
        if not (t.get("id") or "").strip():
            errors.append(f"open_threads[{i}] has no 'id'")
        if not (t.get("next_action") or "").strip():
            warnings.append(f"open_thread '{t.get('id', i)}' has no next_action")

    ev = d.get("evidence", {})
    for cat in ("diagnoses", "hypotheses", "experiments"):
        for e in ev.get(cat, []):
            lp = e.get("log_path")
            if lp and not (ROOT / lp).exists() and not Path(lp).exists():
                warnings.append(f"evidence {cat} '{e.get('stem', '?')}': log_path not on disk ({lp})")

    dec = d.get("phase6_decision")
    if dec:
        viol = WorkflowStateOffline(data=d).validate_phase6_decision()
        for v in viol:
            errors.append(f"phase6_decision: {v}")
        if cp != "refinement":
            warnings.append(f"phase6_decision set but current_phase is '{cp}', not 'refinement'")
    elif cp == "refinement":
        warnings.append("current_phase=refinement with no phase6_decision — pending the convergence gate")

    warnings.extend(_check_decisions_current(path, d))

    errors_, warnings_ = _check_phase_logged(path, d)
    errors.extend(errors_)
    warnings.extend(warnings_)

    return errors, warnings


# Phase name -> the phase NUMBER that appears in an offline log stem
# (stem = YYYYMMDDx_phase{N}_{name}_r{RR}[_c{EE}[_iter{II}]]_{descriptor}).
#: How many commits touching a case since its newest decision before the record looks stale.
DECISION_STALE_COMMITS = 8


def _check_decisions_current(path, d):
    """WARN when the case has moved but the state has recorded no findings.

    Adopted from adapter-kit (re-authored). The state is not only a program counter: `PhaseLogger`
    rebuilds its "Reasoning chain" block from `decisions` on every log write, so a finding that
    never reaches the state is invisible to the next phase — which is the re-derivation the loop
    exists to prevent.

    Main's own instance, 2026-08-21/22: `workflow_state_offline_r01.json` sat at `updated_at`
    2026-08-11, `phase: design`, `cycle 0` — ten days and an entire suplphos dose experiment behind
    — so the ADRGnoneC0 collapse had to be RE-DERIVED after a context loss rather than recalled.
    Nothing mechanical flagged it; the PI asked.

    The signal is ACTIVITY vs RECORD: commits touching this case since the newest decision's date.
    It cannot judge whether a finding was worth recording and deliberately does not try — it asks
    the weaker, decidable question "has this case moved a lot with nothing written down", which is
    the shape the failure actually takes.

    WHAT WOULD MAKE THIS FAIL (named first, per `feedback_a_check_that_cannot_fail`):
      1. many commits touching the case, newest decision older than all of them -> WARN
      2. no decisions at all on an active round                                 -> WARN
      3. git unavailable, or the case path unknown                              -> SILENT. An
         unreadable history is not evidence of a missing finding.
    """
    import subprocess

    warnings = []
    decs = d.get("decisions") or []
    if not isinstance(decs, list):
        return warnings
    if d.get("converged"):
        return warnings                  # a closed round is not expected to keep recording

    # Only the ACTIVE (highest-numbered) round. A superseded round's decisions are finished by
    # definition, and warning about them forever is how a nudge becomes noise and gets tuned out —
    # which would leave the round actually being worked unwatched.
    here = Path(path).resolve()
    siblings = sorted(here.parent.glob("workflow_state_offline_r*.json"))
    if siblings and here != siblings[-1]:
        return warnings

    newest = max((x.get("date", "") for x in decs), default="")
    case_dir = here.parent.parent        # <case>/memory/<state>.json -> <case>
    try:
        out = subprocess.run(
            ["git", "log", "--since", newest or "30 days ago", "--format=%h", "--", str(case_dir)],
            capture_output=True, text=True, timeout=30, cwd=str(ROOT))
        if out.returncode != 0:
            return warnings
        n = len([x for x in out.stdout.split() if x])
    except Exception:
        return warnings                  # (3) silent

    if not decs:
        warnings.append(
            f"no decisions recorded on an active round ({n} commit(s) touching this case) — "
            f"findings belong in the state as they are established, not only at Phase 6")
    elif n >= DECISION_STALE_COMMITS:
        warnings.append(
            f"{n} commit(s) touching this case since the newest decision ({newest}) — "
            f"record findings with add_decision(finding, rationale) as they are established; "
            f"next_action is the program counter, not the record")
    return warnings


_PHASE_NUM = {"design": 0, "exploration": 1, "screening": 2, "diagnosis": 3,
              "hypothesis": 4, "testing": 5, "refinement": 6, "converged": 7}


def _check_phase_logged(path, d):
    """WARN when the state says a phase is current but no offline log exists for it.

    `calibration-discipline` already requires 'each phase logged with its phaseN skill +
    calibration-log'. That was a checklist item — a habit — and habits decay silently across
    a multi-week round. This makes it observable, and it belongs HERE because the same
    checklist already says the state is validated after EVERY phase, so the existing habit
    gains the check without a new command to remember.

    It is a filesystem question, not a judgement about prose: a log stem encodes its phase
    and round, so 'was this phase logged?' is decidable — the same category as the evidence
    gate (an artifact exists) rather than 'is the section any good'.

    WARNING, never ERROR: an error would block the state write a phase transition depends on,
    i.e. gate the loop on a bookkeeping artifact, and that is how gates get bypassed.

    But the window in which it fires innocently is SHORT, and the message says so. A phase log
    is a LIVING record, not an end-of-phase write-up: a phase-0 log should exist from the
    moment cases are submitted, and then accumulate the job/array IDs, the monitoring armed,
    the cases that failed when the scheduler hiccupped, what was restarted, and the early plots
    that checked the run looks right — each paired with an artifact in `phase_results/{stem}/`.
    Create it early and enrich it; do not defer it to the end, or the operational detail that
    makes it useful is gone by the time you write it.
    """
    cp, rnd = d.get("current_phase"), d.get("calibration_round")
    n = _PHASE_NUM.get(cp)
    if n is None or rnd is None:
        return [], []                       # already reported by the checks above
    logs_dir = Path(path).parent / "logs"
    if not logs_dir.is_dir():
        return [], [f"no {logs_dir} — phase '{cp}' cannot have been logged"]

    want = f"_phase{n}_{cp}_r{int(rnd):02d}"
    if not any(want in p.name for p in logs_dir.glob("*.md")):
        return [], [f"no offline log found for phase {n} ({cp}) of round {int(rnd):02d} "
                    f"— expected a stem containing '{want}' in {logs_dir.name}/. "
                    f"START it now and enrich as you go (`calibration-log`): a phase log is a "
                    f"LIVING record — submission, job IDs, monitoring, failures/restarts, early "
                    f"verification plots — not an end-of-phase write-up. Only expected to be "
                    f"absent in the first moments of a phase."]
    return [], []


def main():
    ap = argparse.ArgumentParser(description="Validate offline workflow_state_offline_r*.json invariants")
    ap.add_argument("--file", help="check one state file (default: all use_cases/*/memory/…_r*.json)")
    ap.add_argument("--quiet", action="store_true", help="one line per file (for the SessionStart hook)")
    args = ap.parse_args()

    if args.file:
        paths = [args.file]
    else:
        # canonical per-round singletons only (…_r{RR}.json) — NOT archived/superseded copies
        # with extra suffixes, matching WorkflowStateOffline.find_latest()'s r(\d+)\.json regex.
        import re as _re
        paths = sorted(p for p in glob.glob(
            str(ROOT / "use_cases" / "*" / "memory" / "workflow_state_offline_r*.json"))
            if _re.search(r"workflow_state_offline_r\d+\.json$", p))

    if not paths:
        print("· no workflow_state_offline_r*.json found (no active offline round)")
        return 0

    total_err = 0
    for p in paths:
        errs, warns = check_one(p)
        total_err += len(errs)
        rel = os.path.relpath(p, ROOT)
        if args.quiet:
            mark = "✘" if errs else ("·" if warns else "✔")
            print(f"  {mark} {rel}: {len(errs)} error(s), {len(warns)} warning(s)")
            continue
        mark = "✘" if errs else "✔"
        print(f"{mark} {rel}")
        for e in errs:
            print(f"    ERROR   {e}")
        for w in warns:
            print(f"    warn    {w}")

    if total_err:
        print(f"\n✘ {total_err} invariant error(s) — the offline state would misdrive the loop; fix before driving.")
        return 1
    print("\n✔ offline state invariants clean — schema, phase, counters, threads, phase6 gate all valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
