#!/usr/bin/env python3
"""SessionStart hook — surface a brief operating snapshot into context at session start
(also runs on resume / after compaction). Best-effort and read-only; never blocks.

Shows: current branch, uncommitted-file count, the latest Handoff/Session dev_log,
the count of pending knowledge proposals awaiting curation, and any live long-running
A2MC processes. Helps the cold-start runbook (CLAUDE.md Rule 6) fire reliably.
"""
import sys, os, json, glob, subprocess


def sh(args):
    try:
        return subprocess.check_output(args, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""


def main():
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    lines = []

    branch = sh(["git", "-C", root, "branch", "--show-current"])
    if branch:
        lines.append("Branch: %s" % branch)

    dirty = sh(["git", "-C", root, "status", "--porcelain"])
    n_dirty = len([l for l in dirty.splitlines() if l.strip()])
    lines.append("Uncommitted files: %d" % n_dirty)

    logs = (glob.glob(os.path.join(root, "memory", "dev_logs", "*Handoff*")) +
            glob.glob(os.path.join(root, "memory", "dev_logs", "*Session_Log*")))
    if logs:
        lines.append("Latest handoff/session log: %s" % os.path.basename(sorted(logs)[-1]))

    open_props = 0
    for p in glob.glob(os.path.join(root, "use_cases", "*", "memory",
                                    "gained_knowledge", "auto_discovered_pending.json")):
        try:
            with open(p) as f:
                d = json.load(f)
            open_props += sum(1 for it in d.get("pending", [])
                              if not it.get("promoted") and not it.get("discarded"))
        except Exception:
            pass
    if open_props:
        lines.append("Pending knowledge proposals to curate: %d "
                     "(run the curate-knowledge skill)" % open_props)

    ps = sh(["bash", "-lc",
             "ps -ef | grep \"$USER\" | grep -E 'monitor|submit|extract' "
             "| grep -v grep | head -5"])
    if ps:
        lines.append("Live A2MC processes:\n" + ps)

    ctx = "A2MC session snapshot —\n" + "\n".join(lines)
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": ctx}}))


main()
