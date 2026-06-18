#!/usr/bin/env python3
"""Mechanical skill-registry health check for A2MC (no LLM, no deps).

A2MC skills live at .claude/skills/<name>/SKILL.md and are auto-discovered by the
harness (functional registry). There are TWO human-facing registries that must stay in
sync with the disk, so the drift surface is doubled vs a single-catalog project:

  1. the "Current skills" table in  .claude/skills/README.md
  2. the per-skill entries (### `name`) in  docs/a2mc_reference/skills_catalog.md

Adding/removing a skill without updating BOTH is silent drift. `add-skill` registers in
both by construction; this check makes the invariant enforceable (CI / pre-commit / a hard
step in add-skill) instead of relying on the meta-skill being used.

Checks:
  1. DRIFT      disk == README-table == catalog  (3-way parity)
  2. NAME/DIR   each SKILL.md frontmatter `name:` matches its directory
  3. CHANGELOG  each SKILL.md carries a `## Changelog` section

Exit 0 = clean, 1 = any problem. Run from the repo root:
    python3 tools/check_skill_registry.py

Author: Jing Tao with Claude
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / ".claude" / "skills"
README = SKILLS_DIR / "README.md"
CATALOG = ROOT / "docs" / "a2mc_reference" / "skills_catalog.md"


def skills_on_disk():
    out = {}
    if SKILLS_DIR.is_dir():
        for d in sorted(SKILLS_DIR.iterdir()):
            sk = d / "SKILL.md"
            if d.is_dir() and sk.is_file():
                out[d.name] = sk.read_text(encoding="utf-8")
    return out


def readme_table_names():
    """Names linked in the README 'Current skills' table: [name](name/SKILL.md)."""
    if not README.is_file():
        return None
    return set(re.findall(r"\[([a-z0-9-]+)\]\(\1/SKILL\.md\)", README.read_text(encoding="utf-8")))


def catalog_names():
    """Per-skill headers in the catalog: ### `name`."""
    if not CATALOG.is_file():
        return None
    return set(re.findall(r"^###\s+`([a-z0-9-]+)`", CATALOG.read_text(encoding="utf-8"), re.M))


def frontmatter_name(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    nm = re.search(r"^name:\s*(.+)$", m.group(1), re.M)
    return nm.group(1).strip() if nm else None


def main():
    disk = skills_on_disk()
    if not disk:
        print(f"ERROR: no skills under {SKILLS_DIR}")
        return 1
    readme = readme_table_names()
    catalog = catalog_names()
    if readme is None:
        print(f"ERROR: {README} not found"); return 1
    if catalog is None:
        print(f"ERROR: {CATALOG} not found"); return 1

    disk_names = set(disk)
    problems = []
    for n in sorted(disk_names - readme):
        problems.append(f"DRIFT: '{n}' on disk but missing from the README 'Current skills' table")
    for n in sorted(readme - disk_names):
        problems.append(f"DRIFT: README table lists '{n}' but no skill dir exists")
    for n in sorted(disk_names - catalog):
        problems.append(f"DRIFT: '{n}' on disk but missing from docs/a2mc_reference/skills_catalog.md")
    for n in sorted(catalog - disk_names):
        problems.append(f"DRIFT: catalog lists '{n}' but no skill dir exists")

    for name, text in disk.items():
        fm = frontmatter_name(text)
        if fm is None:
            problems.append(f"NAME: '{name}' SKILL.md has no `name:` in frontmatter")
        elif fm != name:
            problems.append(f"NAME: '{name}' frontmatter name is '{fm}' (must match dir)")
        if not re.search(r"^## Changelog", text, re.M):
            problems.append(f"CHANGELOG: '{name}' SKILL.md has no `## Changelog` section")

    print(f"Skills on disk : {len(disk_names)}")
    print(f"README table   : {len(readme)}")
    print(f"Catalog        : {len(catalog)}")
    print()
    if problems:
        print(f"✘ {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("✔ registry clean — disk ↔ README table ↔ catalog in sync, names match, all versioned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
