#!/usr/bin/env python3
"""PreToolUse(Bash) hook — block git commits whose message carries AI attribution.

Matches only the literal attribution-trailer signatures (Co-Authored-By, the
"Generated with [Claude Code]" line, 🤖 Generated with) — NOT bare "Claude"/"Anthropic",
which would false-positive on legitimate messages mentioning CLAUDE.md or .claude/.
Covers `-m`/`-F`-style commits seen in the command string; editor-based commits are
caught by the repo-local .git/hooks/commit-msg fallback. CLAUDE.md critical rule #1.
"""
import sys, json, re

# Literal AI-attribution trailer signatures (case-insensitive)
PATTERNS = [
    r"co-authored-by",
    r"\U0001f916\s*generated with",     # 🤖 Generated with
    r"generated with \[?claude code",
]


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
        sys.exit(0)
    if data.get("tool_name") != "Bash":
        sys.exit(0)
    cmd = (data.get("tool_input") or {}).get("command", "") or ""
    # Require the `commit` subcommand adjacent to `git ` (whitespace) — so this does
    # NOT match `.git/hooks/commit-msg`, `git log`, or `echo commit`. We always use
    # `git commit -m`; `git -C x commit` (rare here) is caught by the commit-msg fallback.
    if not re.search(r"\bgit\s+commit\b", cmd):
        sys.exit(0)
    low = cmd.lower()
    for p in PATTERNS:
        if re.search(p, low):
            deny("Commit message contains AI attribution (matched /%s/). CLAUDE.md "
                 "rule #1 forbids Co-Authored-By / 'Generated with Claude' trailers. "
                 "Remove the attribution and retry." % p)
    sys.exit(0)


main()
