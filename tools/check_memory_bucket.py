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
import subprocess
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

# --- provenance (memory -> log) -----------------------------------------------------
# The link graph was one-directional: a log is expected to name the memories it used, but
# nothing ever asked a memory to name the log that produced it. Cause: the body template in
# `manage-auto-memory` came from the harness's generic auto-memory format, whose only link
# affordance is [[memory]] -> sideways, never back to a log.
#
# Date-scoped so pre-existing memories are not retroactively flagged. A memory file carries
# no date, but GIT DOES — the add date comes from `git log --diff-filter=A`. A file with no
# add date is new/uncommitted, i.e. being written now, so it IS in scope.
# On this branch every one of the 85 existing memories predates the cutoff (newest add is
# 2026-07-31), so adopting it grandfathers all of them and binds only new writes.
PROVENANCE_SINCE = "2026-08-03"
# NO trailing \b: a citation is usually the FULL filename (`20260803c_Log_Spec_...`), and `_`
# is a word char, so `[a-z]{1,3}\b` refuses to match there.
_LOG_STEM = re.compile(r"\b20\d{6}[a-z]{1,3}")           # a dated log stem, e.g. 20260803c
_PROVENANCE_EXEMPT = {"user"}                            # a fact about Jing has no originating log


def _added_date(path: Path) -> str:
    """YYYY-MM-DD this file was first committed; '' if untracked/new or git is unavailable."""
    try:
        out = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%ad", "--date=short", "--", str(path)],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        ).stdout.strip().splitlines()
        return out[-1] if out else ""       # last line = the ORIGINAL add, not a later re-add
    except (OSError, subprocess.SubprocessError):
        return ""


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

        if "-" in f.stem:
            # Hyphens are reserved for MODEL names (ELM-FATES, api-31-0, elm-fates in `scope:`), so a
            # hyphen anywhere in a memory identifier unambiguously separates a model name, never words.
            # Skills use hyphens (`a2mc-init`); memories do not. Adopted from adapter-kit (0 violations
            # here at adoption, so this is purely a regression guard).
            errors.append(f"{rel}: memory filenames use snake_case — no hyphens. Hyphens are "
                          f"reserved for model names (ELM-FATES); rename to `{f.stem.replace('-', '_')}.md`")

        nm = top_level(fm, "name")
        if not nm:
            errors.append(f"{rel}: missing frontmatter field `name`")
        elif nm.strip().strip("\"'") != f.stem:
            # `name:` IS the filename stem. Nothing was checking it here, so main drifted to 17
            # divergent values (prose titles and hyphenated forms) while adapter-kit, which has
            # enforced this since it landed the check, sits at 0/108.
            #
            # It is not cosmetic. The 2026-08-05 checkup traced a concrete defect chain: a divergent
            # `name:` invites an author to write `[[that-value]]`, producing a wiki-link that resolves
            # to no file. That is how `[[reference-local-repos-and-sync]]` was born dead in 949336e4 —
            # the hyphenated file never existed on any branch. No checker on either branch inspects
            # `[[ ]]` (deliberately: forward-looking links are allowed), so the resulting dead link is
            # invisible to tooling and only the memory-checkup judgment pass can find it. Enforcing
            # name == stem removes the generator instead of chasing the artifacts.
            errors.append(f"{rel}: `name: {nm}` must equal the filename stem `{f.stem}` "
                          f"(wiki-links resolve by stem, so a divergent name invites a dead link)")
        if not top_level(fm, "description"):
            errors.append(f"{rel}: missing frontmatter field `description`")

        if visibility == "public":
            hit = PERSONAL.search(text)
            if hit:
                errors.append(f"{rel}: visibility: public but contains a personal host path "
                              f"('{hit.group(0)}') — genericize or make it private")

        if f"({rel})" not in index:
            warnings.append(f"{rel}: not linked from MEMORY.md")

        # Provenance: name the log that produced this memory, so the graph is bidirectional.
        #
        # DELIBERATELY A WARNING, NOT AN ERROR (PI decision, 2026-08-05 — do not "fix" this).
        # It was proposed for promotion to an error, since date-scoping already exempts the 83
        # grandfathered memories and would have made the blast radius safe. Declined: the rule
        # should not block a commit. Compliance is behavioural, and the mechanism that makes
        # that workable is VISIBILITY — .githooks/pre-commit runs this script whenever
        # .claude_memory/ is staged and does not redirect its output, so the warning prints at
        # commit time on exactly the action that writes a memory. Keep it that way: if you ever
        # silence or capture that output, this rule stops existing in practice.

        if typ not in _PROVENANCE_EXEMPT and not _LOG_STEM.search(text):
            added = _added_date(f)
            if not added or added >= PROVENANCE_SINCE:
                when = f"added {added}" if added else "new/uncommitted"
                warnings.append(
                    f"{rel}: no log reference ({when}) — add a `**Source:**` line naming the "
                    f"dev/ana log this came from (e.g. `20260805a`), so a reader can find the "
                    f"reasoning. See the `manage-auto-memory` skill.")

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
