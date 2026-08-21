#!/usr/bin/env python3
"""Guard the A2MC version number against collision and drift.

Catches the failure of 2026-07-30: two branches independently bumped to the SAME version
(v2.209). Each branch was internally consistent, so nothing complained — and because both
edited `CLAUDE.md` to the identical string, `git merge-tree` reported the merge CLEAN. The
collision only becomes visible in the merged changelog, which is exactly where this looks.

Checks (ERROR, exit 1):
  1. the version in CLAUDE.md's `**Status:** Implementation Complete (vX.YZ)` header appears
     EXACTLY ONCE as a `- **vX.YZ**` entry in memory/a2mc_development_history.md
  2. no LIVE duplicate — two changelog entries on the CURRENT header version

A duplicate on a HISTORICAL version only warns: the changelog is a record of what happened
(v2.80 legitimately has 3 entries from April 2026), not something to rewrite.

Stdlib-only, so it runs under any interpreter the pre-commit hook picks.

Author: Jing Tao with Claude
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD = ROOT / "CLAUDE.md"
CHANGELOG = ROOT / "memory" / "a2mc_development_history.md"


def main():
    if not CLAUDE_MD.exists() or not CHANGELOG.exists():
        print("check_version_consistency: files absent (skip)")
        return 0

    m = re.search(r"\*\*Status:\*\*.*?\((v[\d.]+)\)", CLAUDE_MD.read_text(encoding="utf-8"))
    if not m:
        print("check_version_consistency: no version header in CLAUDE.md (skip)")
        return 0
    header = m.group(1)

    entries = re.findall(r"^- \*\*(v[\d.]+)\*\*", CHANGELOG.read_text(encoding="utf-8"), re.M)
    errors = []
    warnings = []

    for v in sorted({v for v in entries if entries.count(v) > 1}):
        msg = ("%s has %d changelog entries — two changes claimed the same version "
               "(the cross-branch collision signature)" % (v, entries.count(v)))
        if v == header:
            errors.append(msg + ". Renumber the later one BEFORE committing.")
        else:
            warnings.append(msg + " (historical; left as-is)")

    if header not in entries:
        errors.append(
            "CLAUDE.md header says %s but no `- **%s**` entry exists in "
            "memory/a2mc_development_history.md — add the changelog entry or fix the header."
            % (header, header))

    for w in warnings:
        print("  [warn] %s" % w)
    if errors:
        print("✘ %d version problem(s):" % len(errors))
        for e in errors:
            print("  - %s" % e)
        return 1
    print("✔ version consistent: CLAUDE.md %s has exactly one changelog entry "
          "(%d versions logged)" % (header, len(entries)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
