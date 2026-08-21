#!/usr/bin/env python3
"""PostToolUse hook: phase work landed — did the offline state follow?

`calibration-discipline` item 5: update AND validate the offline state after
every phase. Like every conditional instruction, it is read once and then has to
be remembered at a moment nobody observes.

★ THE DESIGN POINT: a hook keyed on state WRITES is blind to an agent that
forgets to write one. So this watches the WORK and asks whether the bookkeeping
followed. Two triggers:

  A  a write to workflow_state_offline_r*.json  -> state written but INVALID
  B  a write to a phase log / phase_results artifact -> state never written AT ALL

Ported from `adapter-kit` (handoff 20260819g). Three properties preserved
verbatim, each earned there rather than reasoned out:

  1. COMPARE TIMESTAMPS, NOT PHASE NUMBERS. "log says phase6, state says design,
     therefore stale" is WRONG: a Phase-6 -> Phase-0 redesign moves the phase
     BACKWARDS, so that combination is a correct state. Kougarok will hit this
     the first time it redesigns.
  2. A CRASHED VALIDATOR IS NOT A FAILING CHECK. Reporting "state invalid" over
     a Python traceback cries wolf about the user's data because our tool broke.
     Safe to treat a traceback as "stay silent" because
     check_workflow_state_offline.py handles genuinely corrupt JSON CLEANLY --
     verified on this branch: `--file <bad json>` exits 1 with no traceback.
  3. FIRE ONLY ON A REAL VIOLATION. Calibration is the main working loop, not a
     one-off setup arc, so a per-transition checklist reminder is noise and noise
     gets muted. Silent when the state kept up; silent when the case runs no
     offline loop at all (some legitimately do not -- treating absence as a
     violation would fire on every one of them).
"""
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

STAMP = ".claude/.calibration_discipline_stamp"
_STATE_RE = re.compile(r"workflow_state_offline_r\d+\.json$")
# A phase log (use_cases/<case>/memory/logs/YYYYMMDDx_phaseN_...) or a phase_results artifact.
_WORK_RE = re.compile(r"use_cases/[^/]+/memory/(logs/\d{8}[a-z]{1,3}_phase\d|phase_results/)")
_STEM_DATE = re.compile(r"(\d{8})[a-z]{1,3}_")


def _root():
    return os.environ.get("CLAUDE_PROJECT_DIR") or str(Path(__file__).resolve().parents[2])


def _emit(body):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse", "systemMessage": body}}))


def _state_for(path: Path):
    """The offline state governing this artifact, or None if the case runs no loop."""
    parts = path.parts
    if "use_cases" not in parts:
        return None
    i = parts.index("use_cases")
    if len(parts) <= i + 1:
        return None
    mem = Path(*parts[: i + 2]) / "memory"
    states = sorted(mem.glob("workflow_state_offline_r*.json"))
    return states[-1] if states else None      # highest round


def _already_said(root, key):
    stamp = Path(root) / STAMP
    try:
        if stamp.read_text().strip() == key:
            return True
    except OSError:
        pass
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(key)
    except OSError:
        pass
    return False


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    if payload.get("tool_response", {}).get("success") is False:
        return
    if payload.get("tool_name") not in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        return

    path_s = str((payload.get("tool_input") or {}).get("file_path", ""))
    if not path_s:
        return
    root = _root()
    path = Path(path_s)

    # ---- Trigger A: a state was written — is it VALID? ----
    if _STATE_RE.search(path_s):
        checker = Path(root) / "tools" / "check_workflow_state_offline.py"
        if not checker.is_file():
            return
        r = subprocess.run([sys.executable, str(checker), "--file", str(path)],
                           capture_output=True, text=True)
        if "Traceback (most recent call last)" in (r.stderr or ""):
            return                                   # OUR tool broke; say nothing
        if r.returncode == 0:
            return                                   # valid
        if _already_said(root, f"invalid:{path.name}"):
            return
        _emit("OFFLINE STATE INVALID — `calibration-discipline` item 5.\n"
              f"  {path.name}\n"
              f"  {(r.stdout or r.stderr).strip().splitlines()[-1][:160] if (r.stdout or r.stderr).strip() else ''}\n"
              f"  Fix: python3 tools/check_workflow_state_offline.py --file {path}")
        return

    # ---- Trigger B: phase work landed — did the state follow? ----
    if not _WORK_RE.search(path_s.replace(os.sep, "/")):
        return
    state = _state_for(path)
    if state is None or not state.is_file():
        return                                       # no offline loop here: not a violation

    m = _STEM_DATE.search(path.name)
    if not m:
        return
    try:
        art = date(int(m.group(1)[:4]), int(m.group(1)[4:6]), int(m.group(1)[6:8]))
        upd = json.loads(state.read_text()).get("updated_at", "")
        su = date(int(upd[:4]), int(upd[5:7]), int(upd[8:10]))
    except Exception:
        return                                       # unreadable either side: silent

    if art <= su:
        return                                       # bookkeeping kept up
    if _already_said(root, f"stale:{state.name}:{art}:{su}"):
        return

    _emit("PHASE WORK LANDED, STATE NOT UPDATED — `calibration-discipline` item 5.\n"
          f"  newest phase artifact: {art:%Y%m%d}   state `updated_at`: {su} ({state.name})\n"
          "  The offline state is the resume brain: a cold session reads it to learn where the\n"
          "  loop is, so work it does not record is work the next session cannot see.")


if __name__ == "__main__":
    main()
