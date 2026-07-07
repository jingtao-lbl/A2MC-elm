#!/usr/bin/env python3
"""Validate the git-synced Claude memory bucket (.claude_memory/).

Enforces the frontmatter schema from docs/29_Claude_Memory_Bucket_Adoption_Plan.md +
CLAUDE.md branch rule (every .claude_memory memory sets machine/visibility/scope/type).
No-ops if .claude_memory/ is absent (e.g. the public clone), so it is safe to ship in tools/.

ERRORS (exit 1): a memory file missing a required frontmatter field, an invalid enum
value, a `visibility: public` file that contains a personal host path, or a DEAD LINK in
MEMORY.md (an index line pointing to a deleted/renamed memory — the removal backstop).
WARNINGS (exit 0): a memory not linked from MEMORY.md.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUCKET = ROOT / ".claude_memory"

MACHINE = {"shared", "mac", "perlmutter"}
VISIBILITY = {"private", "public"}
SCOPE = {"fates", "elm", "elm-fates", "modeling", "hpc", "a2mc", "process"}
TYPE = {"user", "feedback", "project", "reference"}
# Personal host paths that must never appear in a visibility: public memory.
PERSONAL = re.compile(r"~|/global/homes/|/global/cfs/cdirs/|/pscratch/|/dvs_ro/cfs/")

SKIP = {"MEMORY.md", "CLAUDE.md"}


def frontmatter(text):
    """Return the frontmatter block (between the first two --- lines) or None."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    return None if end is None else "\n".join(lines[1:end])


def top_level(fm, key):
    """Value of a top-level `key: value` line in the frontmatter, or None."""
    m = re.search(rf"^{key}:\s*(.+?)\s*$", fm, re.M)
    return m.group(1).strip() if m else None


def main():
    if not BUCKET.is_dir():
        print("check_memory_bucket: no .claude_memory/ (skip)")
        return 0

    files = sorted(f for f in BUCKET.glob("*.md") if f.name not in SKIP)
    index = (BUCKET / "MEMORY.md").read_text(encoding="utf-8") if (BUCKET / "MEMORY.md").exists() else ""

    errors, warnings = [], []
    for f in files:
        rel = f.name
        text = f.read_text(encoding="utf-8")
        fm = frontmatter(text)
        if fm is None:
            errors.append(f"{rel}: no YAML frontmatter block")
            continue

        machine = top_level(fm, "machine")
        visibility = top_level(fm, "visibility")
        scope = top_level(fm, "scope")
        # `type` may be top-level or nested under a `metadata:` block — accept either.
        tmatch = re.search(r"^\s*type:\s*(.+?)\s*$", fm, re.M)
        typ = tmatch.group(1).strip() if tmatch else None

        for name, val, allowed in (
            ("machine", machine, MACHINE),
            ("visibility", visibility, VISIBILITY),
            ("scope", scope, SCOPE),
            ("type", typ, TYPE),
        ):
            if val is None:
                errors.append(f"{rel}: missing frontmatter field `{name}`")
            elif val not in allowed:
                errors.append(f"{rel}: invalid `{name}: {val}` (allowed: {', '.join(sorted(allowed))})")

        if not top_level(fm, "name"):
            errors.append(f"{rel}: missing frontmatter field `name`")
        if not top_level(fm, "description"):
            errors.append(f"{rel}: missing frontmatter field `description`")

        if visibility == "public":
            hit = PERSONAL.search(text)
            if hit:
                errors.append(f"{rel}: visibility: public but contains a personal host path "
                              f"('{hit.group(0)}') — genericize or make it private")

        if f"({rel})" not in index:
            warnings.append(f"{rel}: not linked from MEMORY.md")

    # Removal backstop: every bare (<slug>.md) link in MEMORY.md must resolve to a real
    # memory file. A dead link means a memory was deleted without pruning its index line
    # — the symmetric-removal gap (mirrors check_skill_registry.py's DRIFT check for skills).
    existing = {f.name for f in files}
    for target in re.findall(r"\(([A-Za-z0-9_][A-Za-z0-9_.-]*\.md)\)", index):
        if target in SKIP or target in existing:
            continue
        errors.append(f"MEMORY.md: dead link to `{target}` — file does not exist; prune the "
                      f"index line (or restore the memory)")

    for w in warnings:
        print(f"  [warn] {w}")
    if errors:
        print(f"\n✘ {len(errors)} problem(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"✔ .claude_memory/: {len(files)} memories, frontmatter valid"
          + (f" ({len(warnings)} unindexed — warn)" if warnings else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
