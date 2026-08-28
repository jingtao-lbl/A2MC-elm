"""block-recursive-traversal.py must match command names in COMMAND POSITION.

Adopted from adapter-kit `1bd690ab` + `7e53e3ba` (re-authored, per adopt-from-adapter-kit).

Two classes of false positive this pins:

1. **Prose-as-code.** A bare `\\s` prefix matched the word anywhere, so the English word "tree"
   inside an `echo` string denied the command. Main hit this class four times on 2026-08-22.
2. **Flag stolen from a neighbour.** Searching the whole line for `-r` associated it with a command
   it did not belong to: `... | grep -E "..." ; rm -rf ./tmp/x` read as a recursive grep.

**Why the fixtures live in this file and not in a shell command:** the hook inspects the Bash
command string, so writing these cases inline in a shell invocation makes the hook deny the *test*.
That is the same "a check whose input contains test fixtures" trap the check-(8) port had to handle.

**The verdict is on STDOUT, not the exit code.** This hook always exits 0 and signals via
`{"hookSpecificOutput": {"permissionDecision": "deny"}}`. Reading the exit code makes every case
look allowed, so a test written that way cannot fail. Learned the hard way while porting this.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / ".claude" / "hooks" / "block-recursive-traversal.py"


def decide(cmd: str) -> str:
    """-> 'deny' or 'allow', read from the hook's stdout decision."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
    env = dict(os.environ, A2MC_TRAVERSAL_GUARD="on")   # deterministic off-HPC too
    p = subprocess.run([sys.executable, str(HOOK)], input=payload,
                       capture_output=True, text=True, env=env)
    try:
        out = json.loads(p.stdout or "{}")
    except json.JSONDecodeError:
        return "allow"
    return out.get("hookSpecificOutput", {}).get("permissionDecision", "allow")


# --------------------------------------------------------------- must still DENY

MUST_DENY = [
    "grep -r 'foo' /global/cfs/cdirs/m2467",
    "grep -rn 'foo' ~",
    "find ~ -name '*.F90'",
    "ls -R /global/cfs/cdirs",
]


@pytest.mark.parametrize("cmd", MUST_DENY)
def test_real_traversals_are_still_denied(cmd):
    """The whole point of the hook. If these regress, the fixes went too far."""
    assert decide(cmd) == "deny", cmd


# --------------------------------------------------------------- must ALLOW

MUST_ALLOW = [
    # prose-as-code: the English word "tree" is not the tree(1) command
    'echo "=== main working tree on those paths ==="',
    # a flag belonging to a DIFFERENT command on the same line
    'python plot.py --tape /global/cfs/x | grep -E "abc" ; rm -rf ./tmp/x',
    # index reads are never traversals
    'git grep -n "pattern" -- tools/',
    "git ls-files use_cases/",
    # single-file greps in a compound, the shape that bit main repeatedly on 2026-08-22
    'python tools/check_log_conformance.py memory/dev_logs/x.md | tail -3\ngrep -n "^## " memory/dev_logs/x.md',
    "git status --short | grep -v watch_",
    # bounded find is the documented remedy; it must not be denied
    "find tools/ -maxdepth 2 -name '*.py'",
]


@pytest.mark.parametrize("cmd", MUST_ALLOW)
def test_non_traversals_are_allowed(cmd):
    assert decide(cmd) == "allow", cmd


# --------------------------------------------------- the real denials this port fixed
# Both were measured DENY before the port and ALLOW after (tmp replay, 2026-08-22). Kept
# verbatim in shape so a future change to the matchers cannot silently reintroduce them.

REAL_DENIALS_FIXED = [
    # An in-memory dict walk is not a filesystem walk. The `walk()` name plus two shared
    # absolute paths elsewhere in the command was enough to deny it.
    '''cd ~/A2MC-main && ~/a2mc_env/bin/python - <<'PY'
import json
d = json.load(open("use_cases/x/fates_params.json"))
def find(sub):
    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, path + "/" + k)
    walk(d)
PY''',
    # A git compound whose last stage is `git status | awk`. Index reads throughout.
    '''cd ~/A2MC-main
git branch --show-current
git config user.email
git fetch origin --quiet
git log --oneline origin/main..HEAD
git status --short | awk '!/watch_/' ''',
]


@pytest.mark.parametrize("cmd", REAL_DENIALS_FIXED)
def test_real_denials_from_20260822_stay_fixed(cmd):
    assert decide(cmd) == "allow", cmd


# --------------------------------------------------------------- the guard main added

def test_hook_is_importable_without_running():
    """main() must stay behind `if __name__ == '__main__'`.

    adapter-kit REMOVED this guard on its copy. Taking that file wholesale would undo main's
    2026-08-19 fix (fb94d66e) and break tests/test_hook_matcher_coverage.py. Pinned here so the
    next adoption cannot quietly drop it.
    """
    src = HOOK.read_text()
    assert 'if __name__ == "__main__":' in src, (
        "the __main__ guard was removed -- importing this module would RUN the hook")
