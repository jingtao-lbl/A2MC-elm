#!/usr/bin/env python3
"""PostToolUse hook: a memory file was just written, and it may not be what the skill would produce.

Why this exists
---------------
`manage-auto-memory` owns the `.claude_memory/` bucket: the rich frontmatter schema, the naming rule,
the `**Source:**` back-link, and the `MEMORY.md` index line. Writing a memory WITHOUT it is a
conditional failure whose condition becomes true mid-session, which is the shape the other
`remind-*` hooks exist for -- the moment it becomes true goes unobserved.

CHECK THE ARTIFACT, NOT THE CEREMONY
------------------------------------
A hook cannot reliably know whether a skill was invoked, and keying on that would be a check that
mostly guesses. It CAN know whether the file has the properties the skill guarantees, which is the
same split `check_calibration_log_conformance` C11 draws against `check_skill_claims`: one asks
whether a claim is TRUE, the other whether it is THERE. This asks whether the OUTCOME is right, so
it fires on a bad file written by a careful agent and stays silent on a good one written by a lucky
one -- and the second case is not a failure worth interrupting.

THE TRAP IT WAS BUILT FOR (2026-08-23)
--------------------------------------
The harness reads memory from `~/.claude/projects/<key>/memory/`, which on a wired clone is a
SYMLINK to `<repo>/.claude_memory/`. Writing through that path lands the file in the right directory
AND lets the harness normalize the frontmatter into its own simpler global schema on the way --
moving `machine`, `visibility` and `scope` down inside `metadata:` and adding session fields. The
file then looks saved, sits in git, and fails `check_memory_bucket.py` with all three fields
"missing". A wired symlink makes the write land in the right DIRECTORY; it does not make it produce
the right FILE. That is the single most useful thing this hook can say, so it says it by name.

NOISE IS THE FAILURE MODE. Silent when the memory is well-formed. Silent on `MEMORY.md` and
`CLAUDE.md`, which are not memories. Never blocks. Never raises.

Author: Jing Tao with Claude
"""
import json
import os
import re
import subprocess
import sys

WRITE_TOOLS = {"Write", "Edit", "NotebookEdit", "MultiEdit"}
BUCKET = ".claude_memory"
NOT_MEMORIES = {"MEMORY.md", "CLAUDE.md", "README.md"}
REQUIRED_TOP = ("machine", "visibility", "scope", "name")
# Memories added on/after this date owe a Source line (check_memory_bucket.py date-scopes the same way).
SOURCE_SINCE = "2026-08-03"


def _frontmatter(text):
    """-> (raw_block, dict_of_TOP_LEVEL_keys). Deliberately shallow: nesting is what we detect."""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None, {}
    block = m.group(1)
    top = {}
    for line in block.split("\n"):
        if line[:1] in (" ", "\t", "#") or ":" not in line:
            continue
        k, _, v = line.partition(":")
        top[k.strip()] = v.strip()
    return block, top


def _added_since(path, iso_date):
    """True if git has no add-date for `path` (untracked, i.e. brand new) or it was added on/after
    `iso_date`. Errs toward True only for a genuinely new file, never for repo history it cannot read."""
    try:
        out = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%as", "--", path],
            cwd=os.path.dirname(path) or ".", capture_output=True, text=True, timeout=5)
    except Exception:
        return False                      # cannot tell -> stay quiet rather than nag
    if out.returncode != 0:
        return False
    dates = [d for d in out.stdout.split() if d]
    if not dates:
        return True                       # untracked: this write is the memory's creation
    return dates[-1] >= iso_date


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if payload.get("tool_name") not in WRITE_TOOLS:
        return
    ti = payload.get("tool_input") or {}
    path = ti.get("file_path") or ti.get("notebook_path") or ""
    if not path.endswith(".md"):
        return

    real = os.path.realpath(path)
    if f"{os.sep}{BUCKET}{os.sep}" not in real + os.sep:
        return
    base = os.path.basename(real)
    if base in NOT_MEMORIES:
        return

    try:
        with open(real, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return

    block, top = _frontmatter(text)
    problems, notes, nested = [], [], []
    reported_nesting = False    # dedup below keys on this, NOT on `nested`: if the trap
                                # branch is ever edited away, the fields must reappear in the
                                # generic missing-field check rather than vanish from both.

    # 1. THE TRAP: rich fields nested under metadata: instead of top level.
    if block is not None:
        nested = [k for k in ("machine", "visibility", "scope")
                  if k not in top and re.search(rf"^\s+{k}\s*:", block, re.M)]
        if nested:
            reported_nesting = True
            problems.append(
                f"`{', '.join(nested)}` sit INSIDE `metadata:` instead of at top level. That is the "
                f"harness's own auto-memory schema, not this repo's -- it normalizes on write through "
                f"`~/.claude/projects/.../memory/`, even on a wired clone where that path is a symlink "
                f"into the bucket. `check_memory_bucket.py` reads them as MISSING. Move them to top level.")

    if block is None:
        problems.append("no YAML frontmatter at all -- this repo's bucket requires the rich schema.")
    else:
        # Do not double-report: a field the harness NESTED is already named by the trap message.
        skip = nested if reported_nesting else []
        missing = [k for k in REQUIRED_TOP if k not in top and k not in skip]
        if missing:
            problems.append(f"missing top-level frontmatter: {', '.join(missing)}")
        if "name" in top and top["name"] != base[:-3]:
            problems.append(f"`name:` is `{top['name']}` but the filename stem is `{base[:-3]}` -- "
                            f"they must be identical, or a `[[link]]` resolves to nothing.")
        if "-" in base[:-3]:
            problems.append(f"`{base[:-3]}` contains a HYPHEN. Memory identifiers are snake_case; "
                            f"hyphens are reserved for model names.")

    # 2. The back-link, which only the skill's template carries.
    #    NON-RETROACTIVE, the same way check_memory_bucket.py scopes it: a memory carries no date but
    #    git does, so ask git when the file was ADDED. Without this the hook fires on every edit to
    #    every pre-rule memory in the bucket -- measured on a real one -- and a reminder that fires on
    #    correct work is the noise this hook's own docstring calls the failure mode.
    #    MAIN'S CONTRACT, not the source branch's. adapter-kit requires the literal `**Source:**`
    #    marker "by PATH, not bare stem" — a tightening it made separately after a bare stem
    #    resolved to the wrong log twice. **main has NOT adopted that tightening**:
    #    `check_memory_bucket.py` accepts a dated log stem anywhere in the text (`_LOG_STEM`).
    #    Enforcing the stricter rule here would fire on 94 of main's 106 memories — measured —
    #    which is exactly the noise this hook's docstring calls its failure mode, and it would
    #    contradict the checker that actually gates the commit. Mirror the checker; the tightening
    #    is queued in TODO.md as its own decision, with its migration cost stated.
    _LOG_STEM = re.compile(r"\b20\d{6}[a-z]{1,3}")
    is_user_memory = re.search(r"^\s*type:\s*user\s*$", block or "", re.M)
    if (not _LOG_STEM.search(text) and not is_user_memory
            and _added_since(real, SOURCE_SINCE)):
        problems.append(f"no log reference — add a `**Source:**` line naming the dev/ana log this "
                        f"came from (e.g. `20260805a`), so a reader can find the reasoning. "
                        f"Scoped to memories added on/after {SOURCE_SINCE}, matching "
                        f"`check_memory_bucket.py`.")

    # 3. Invisible to recall.
    idx = os.path.join(os.path.dirname(real), "MEMORY.md")
    try:
        if base not in open(idx, encoding="utf-8").read():
            notes.append(f"no `MEMORY.md` pointer yet -- a memory with no index line is invisible to recall.")
    except OSError:
        pass

    if not problems and not notes:
        return

    lines = [f"MEMORY BUCKET -- `{base}` was written directly; `manage-auto-memory` owns this file's shape.", ""]
    for p in problems:
        lines.append(f"  ✗ {p}")
    for n in notes:
        lines.append(f"  · {n}")
    lines += ["", "  Fix, then `python3 tools/check_memory_bucket.py` (exit 0). Full contract + the "
                  "retire-a-memory path: the `manage-auto-memory` skill."]
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse", "additionalContext": "\n".join(lines)}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass          # a reminder must never break the tool call it follows
