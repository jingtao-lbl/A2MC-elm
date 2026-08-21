"""Every hook must be reachable by the matcher it is registered under.

The failure this prevents, reported from the `adapter-kit` branch
(`memory/dev_logs/20260819f_Handoff_From_AdapterKit_*`): a `PostToolUse` entry
carried `"matcher": "Bash"`, and a new hook that inspected `Write`/`Edit`
payloads was appended to that same entry. The hook installed, smoke-tested
fine on its Bash triggers, and was **deaf to more than half of what it
watched** — silently, because a matcher that never fires looks identical to a
hook with nothing to say.

The check is structural, not behavioural: read which tool names each hook
inspects, read the matcher it sits under, and assert the matcher admits them.
"""
import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SETTINGS = REPO / ".claude" / "settings.json"
HOOKS_DIR = REPO / ".claude" / "hooks"

# Tool names a hook may gate on. A hook that names none is matcher-agnostic.
_KNOWN_TOOLS = ("Bash", "Write", "Edit", "MultiEdit", "NotebookEdit", "Read", "Glob", "Grep")

# `payload.get("tool_name") != "Bash"` / `tool_name not in ("Write", "Edit")` / etc.
_TOOL_GATE = re.compile(r'tool_name["\']?\s*(?:!=|==|not in|in)\s*[\(\[]?([^)\]\n:]+)')


def _tools_inspected(src: str) -> set:
    """Tool names the hook's own code gates on."""
    found = set()
    for m in _TOOL_GATE.finditer(src):
        for t in _KNOWN_TOOLS:
            if f'"{t}"' in m.group(1) or f"'{t}'" in m.group(1):
                found.add(t)
    return found


def _matcher_admits(matcher: str, tool: str) -> bool:
    """Claude Code matches the tool name against the matcher as a regex."""
    if not matcher:          # absent matcher = fires for everything
        return True
    return re.fullmatch(matcher, tool) is not None


class TestHookMatcherCoverage(unittest.TestCase):
    def test_every_hook_is_reachable_by_its_matcher(self):
        settings = json.loads(SETTINGS.read_text())
        problems = []

        for event, entries in settings.get("hooks", {}).items():
            for entry in entries:
                matcher = entry.get("matcher", "")
                for h in entry.get("hooks", []):
                    cmd = h.get("command", "")
                    m = re.search(r'hooks/([A-Za-z0-9_\-]+\.py)', cmd)
                    if not m:
                        continue
                    script = HOOKS_DIR / m.group(1)
                    if not script.is_file():
                        problems.append(f"{event}: registered hook {m.group(1)} does not exist")
                        continue
                    inspects = _tools_inspected(script.read_text())
                    unreachable = {t for t in inspects if not _matcher_admits(matcher, t)}
                    if unreachable:
                        problems.append(
                            f"{event} matcher={matcher!r}: {m.group(1)} inspects "
                            f"{sorted(inspects)} but {sorted(unreachable)} can never reach it — "
                            f"widen the matcher (e.g. 'Bash|Write|Edit') or give this hook its "
                            f"own entry")

        self.assertEqual(problems, [], "hook matcher does not cover the hook's own triggers:\n  "
                                       + "\n  ".join(problems))

    def test_every_registered_hook_script_exists(self):
        settings = json.loads(SETTINGS.read_text())
        missing = []
        for event, entries in settings.get("hooks", {}).items():
            for entry in entries:
                for h in entry.get("hooks", []):
                    m = re.search(r'hooks/([A-Za-z0-9_\-]+\.py)', h.get("command", ""))
                    if m and not (HOOKS_DIR / m.group(1)).is_file():
                        missing.append(f"{event}: {m.group(1)}")
        self.assertEqual(missing, [], f"registered but absent: {missing}")

    def test_hooks_are_importable_without_running(self):
        """A hook must guard `main()`, or importing it in a test executes it.

        `session-start.py` lacked this until 2026-08-19 and emitted a full
        snapshot on import, which is why `adapter-kit` had to test it out of
        process. `remind-arm-monitoring.py` had the guard all along.
        """
        offenders = []
        for f in sorted(HOOKS_DIR.glob("*.py")):
            src = f.read_text()
            if "def main(" not in src:
                continue
            if '__name__' not in src:
                offenders.append(f.name)
        self.assertEqual(offenders, [],
                         f"hooks call main() at import (add an `if __name__ == \"__main__\":` "
                         f"guard): {offenders}")


if __name__ == "__main__":
    unittest.main()
