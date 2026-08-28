#!/usr/bin/env python3
"""PreToolUse hook: fire when a Bash command is about to hand-roll a run restart.

Why this exists
---------------
Restarting a timed-out case kept starting from `xmlquery CONTINUE_RUN` and a
hand-composed plan, across sessions. The 2026-08-20 reflection
(`memory/dev_logs/reflection/20260820a_*`) found the cause was ROUTING, not
comprehension:

  - No memory carried the mechanism (`git grep` over `.claude_memory/` for
    restart_experiment_case / CONTINUE_RUN / finidat returned nothing, x3).
  - `restart-failed-jobs`' frontmatter description -- the part read before any
    skill is opened -- named only the two ENSEMBLE pathways, and mentioned
    `restart_experiment_case.py` only inside a changelog entry, never as a
    routing step. A single suffixed offline-testing case is exactly what the
    ensemble machinery cannot address, so the skill most likely to be consulted
    pointed away from the one correct tool.

Those two gaps are now closed in the memory + skill. This hook closes the third:
both fixes are things that must be READ, and the wrong instinct arrives before
anything gets opened. This observes the moment the wrong path is taken.

It is advisory and NEVER blocks. Two of its trigger shapes have a legitimate
form (see below), so denying would be wrong; the message says plainly which
case is which and costs one line when it is the legitimate one.

Contract
--------
Fires on a Bash command that BOTH invokes CIME (`xmlquery`/`xmlchange`) AND
either mentions `CONTINUE_RUN`, or hand-edits the RUN_STARTDATE+finidat pair
inline. Requiring an xmlquery/xmlchange invocation is what keeps a plain
`git grep CONTINUE_RUN` (reading docs ABOUT the rule) from firing.

Deliberately NOT matched:
  - `tools/model_evolution/build_v0_case_via_*.sh` and anything under
    `model_evolution/` -- these are the CORRECT tool for a V0 build, so the
    restart reminder would be wrong there. (Until 2026-08-26 they also took a
    `--continue-run` flag; it was REMOVED, so CONTINUE_RUN is now an
    unambiguous wrong-answer marker everywhere -- no legitimate
    segment. That is a real, recurring workflow and must stay silent.
  - `restart_experiment_case.py` -- the correct tool.
  - `bash restart_*.sh` -- a generated restart script doing the finidat/
    RUN_STARTDATE/STOP_N edits is the CORRECT mechanism being replayed.
  - `--dry-run`, and this file itself.

Author: Jing Tao with Claude
"""
import json
import re
import sys

CIME_RE = re.compile(r"\bxml(?:query|change)\b", re.I)
CONTINUE_RE = re.compile(r"\bCONTINUE_RUN\b")
# Hand-composing the restart inline rather than letting the tool generate it.
HANDROLL_RE = re.compile(r"\bRUN_STARTDATE\b", re.I)
FINIDAT_RE = re.compile(r"\bfinidat\b", re.I)

QUIET_RE = re.compile(
    r"model_evolution"                 # V0 builders are the correct tool for their job
    r"|build_v0_case_via"
    r"|restart_experiment_case\.py"    # the correct tool
    r"|restart_[A-Za-z0-9_]*\.sh"      # replaying a generated restart script
    r"|--dry-run\b"
    r"|remind-restart-mechanism",
    re.I,
)

MESSAGE = (
    "RESTART MECHANISM -> if you are restarting/resuming a run, STOP and use the tool:\n"
    "    python tools/restart_experiment_case.py --case-dir <case>          # preview\n"
    "    python tools/restart_experiment_case.py --case-dir <case> --execute\n"
    "It derives resume year, STOP_N, forcing-cycle snap-back and the finidat path from the\n"
    "case's OWN files, and --execute re-chains the ENTIRE downstream chain (an un-rechained\n"
    "downstream strands on DependencyNeverSatisfied).\n"
    "  * This project resumes via finidat + RUN_STARTDATE + STOP_N -- NOT CONTINUE_RUN.\n"
    "    Cases run with CONTINUE_RUN=FALSE, so a plain resubmit silently re-runs from the\n"
    "    ORIGINAL RUN_STARTDATE and times out again.\n"
    "  * Cycle-snap-back of the resume year is ADSP/RGSP ONLY, NEVER TRANS (TRANS writes a\n"
    "    restart every year, so there is no partial forcing cycle to snap back from).\n"
    "  * Check use_cases/<site>/memory/phase_results/{stem}/restart_*.sh -- prior restarts of\n"
    "    the SAME experiment are the authoritative precedent.\n"
    "See `restart-failed-jobs` Step 1 (ad-hoc fork) and the memory\n"
    "feedback_restart_via_finidat_not_continue_run.\n"
    "This covers model-evolution V0 checks too: as of 2026-08-26 they use the SAME finidat\n"
    "mechanism (build_v0_case_via_clone.sh no longer takes --continue-run), so CONTINUE_RUN\n"
    "is not used anywhere in A2MC."
)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)                                   # unparseable -> stay silent

    if payload.get("tool_name") != "Bash":
        sys.exit(0)
    cmd = (payload.get("tool_input") or {}).get("command", "") or ""
    if not cmd or QUIET_RE.search(cmd):
        sys.exit(0)
    # Requiring a real CIME invocation keeps `git grep CONTINUE_RUN` (reading the
    # docs ABOUT this rule) from firing -- a read is not an act.
    if not CIME_RE.search(cmd):
        sys.exit(0)
    if not (CONTINUE_RE.search(cmd)
            or (HANDROLL_RE.search(cmd) and FINIDAT_RE.search(cmd))):
        sys.exit(0)

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": MESSAGE}}))
    sys.exit(0)


if __name__ == "__main__":
    main()
