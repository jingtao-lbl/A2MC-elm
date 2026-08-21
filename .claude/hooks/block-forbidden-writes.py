#!/usr/bin/env python3
"""PreToolUse(Bash) hook — enforce the NERSC "no writes outside home" hard rule.

Denies a Bash command only when it appears to WRITE to a system temp/scratch path
(/tmp, /scratch, /dev/shm, $SCRATCH, $TMPDIR) or uses bare `mktemp`. READS from those
paths are allowed, and the project's own repo-internal `tmp/` dir (e.g.
.../A2MC/tmp, ./tmp) is NOT flagged — only absolute system paths at a token boundary.

Limit: cannot see writes made *inside* a program (e.g. `python foo.py` that writes to
/tmp). Catches direct shell writes/redirects/file-ops, which is the common case.

Schema: reads the tool-call JSON on stdin; denies via
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", ...}}.
See feedback_no_writes_outside_home / CLAUDE.md.
"""
import sys, json, re

# Absolute system temp/scratch path at a token boundary — excludes .../A2MC/tmp, ./tmp
ABS_RE = re.compile(r"""(?:^|[\s"'=(:|&;])(?:/tmp|/scratch|/dev/shm)(?:$|[/\s"'):|&;])""")
VAR_RE = re.compile(r"""\$\{?(?:SCRATCH|TMPDIR)\}?""")
REDIR_RE = re.compile(r""">>?\s*["']?(?:/tmp|/scratch|/dev/shm|\$\{?(?:SCRATCH|TMPDIR)\}?)""")
FILEOP_RE = re.compile(r"""\b(?:cp|mv|rsync|tee|install|touch|mkdir|dd|ln)\b""")
MKTEMP_RE = re.compile(r"""\bmktemp\b""")
MKTEMP_SAFE_RE = re.compile(r"""\bmktemp\b[^\n]*\s-(?:p|-tmpdir)\b""")


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason}}))
    sys.exit(0)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)                      # unparseable → don't block
    if data.get("tool_name") != "Bash":
        sys.exit(0)
    cmd = (data.get("tool_input") or {}).get("command", "") or ""

    # bare mktemp defaults to /tmp (a write outside home)
    if MKTEMP_RE.search(cmd) and not MKTEMP_SAFE_RE.search(cmd):
        deny("`mktemp` defaults to /tmp (write outside home). Use a repo-internal temp, "
             "e.g. `mktemp -p ./tmp`, or write under the project dir.")

    if not (ABS_RE.search(cmd) or VAR_RE.search(cmd)):
        sys.exit(0)                      # no system temp/scratch path referenced

    if REDIR_RE.search(cmd) or FILEOP_RE.search(cmd):
        deny("Command appears to WRITE to a forbidden system path "
             "(/tmp, /scratch, /dev/shm, $SCRATCH, $TMPDIR). NERSC HARD RULE: no writes "
             "outside home. Reads are fine — write to a repo-internal dir (e.g. ./tmp) "
             "instead. If this is read-only, rephrase to avoid the write-like token.")
    sys.exit(0)


if __name__ == "__main__":
    # Guard added 2026-08-19: without it, importing this module RUNS the hook,
    # so it cannot be unit-tested in process. Enforced by
    # tests/test_hook_matcher_coverage.py::test_hooks_are_importable_without_running.
    main()
