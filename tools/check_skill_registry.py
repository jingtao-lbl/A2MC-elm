#!/usr/bin/env python3
"""Mechanical skill-registry + contract health check for A2MC (no LLM, no deps).

A2MC skills live at .claude/skills/<name>/SKILL.md and are auto-discovered by the
harness (functional registry). There are THREE human-facing registries that must stay in
sync with the disk, so the drift surface is tripled vs a single-catalog project:

  1. the "Current skills" table in  .claude/skills/README.md
  2. the per-skill entries (### `name`) in  docs/a2mc_reference/skills_catalog.md
  3. the "At a glance" capability table in  AGENTS.md  (the public, harness-neutral
     operating contract — an un-enforced registry here is exactly how AGENTS.md silently
     fell behind when 8 skills were added; see memory/dev_logs/ for the 2026-06-28 fix)

Checks:
  1. DRIFT      disk == README-table == catalog == AGENTS.md table  (4-way parity)
  2. NAME/DIR   each SKILL.md frontmatter `name:` matches its directory
  3. CHANGELOG  each SKILL.md carries a `## Changelog` section
  4. CONTRACT   (Tier-1 skill-contract validation) every backticked repo path / tool /
                script the skill cites EXISTS, and every `<name>` skill it references is a
                PROJECT skill (policy: all skills live in the repo's .claude/skills/). A ref
                that resolves only at user level → GLOBAL-SKILL-REF (move it in); an unknown
                one → DEAD-SKILL-REF. Catches skill rot (a renamed tool leaving a dead ref).

This is the STATIC (Tier-1) gate. Its runtime sibling is tools/smoke_test_skills.py
(Tier-2), which actually runs the read-only backing commands the skills document and
asserts exit 0 — catching runtime bugs a static check can't.

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
AGENTS = ROOT / "AGENTS.md"

# Files shipped to the public repo through the <!-- private --> block filter
# (filter_private in sync_to_public.sh). Unbalanced markers make the filter silently
# strip too much (or too little); a marker string appearing INLINE (not on its own line)
# is a landmine — the awk filter matches any line containing it, so it would strip
# everything after it. Both bit us (2026-07-01/02). Check mechanically.
FILTERED_FILES = [ROOT / "CLAUDE.md", ROOT / "README.md", AGENTS, README, CATALOG] \
    + sorted((ROOT / "phases").glob("**/CLAUDE.md"))
OPEN_MARK, CLOSE_MARK = "<!-- private -->", "<!-- /private -->"


def skills_on_disk():
    out = {}
    if SKILLS_DIR.is_dir():
        for d in sorted(SKILLS_DIR.iterdir()):
            sk = d / "SKILL.md"
            if d.is_dir() and sk.is_file():
                out[d.name] = sk.read_text(encoding="utf-8")
    return out


def readme_table_names():
    if not README.is_file():
        return None
    return set(re.findall(r"\[([a-z0-9-]+)\]\(\1/SKILL\.md\)", README.read_text(encoding="utf-8")))


def catalog_names():
    if not CATALOG.is_file():
        return None
    return set(re.findall(r"^###\s+`([a-z0-9-]+)`", CATALOG.read_text(encoding="utf-8"), re.M))


def agents_table_names():
    """Skill names from the 'At a glance' capability table(s) in AGENTS.md — the first
    backticked token of each table row (`| `name` | … |`). Header/separator rows have no
    backticks, so they don't match."""
    if not AGENTS.is_file():
        return None
    return set(re.findall(r"^\|\s*`([a-z0-9-]+)`", AGENTS.read_text(encoding="utf-8"), re.M))


def frontmatter_name(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    nm = re.search(r"^name:\s*(.+)$", m.group(1), re.M)
    return nm.group(1).strip() if nm else None


# ---------------- Tier-1 contract validation ----------------
_BACKTICK = re.compile(r"`([^`]+)`")
_PATHISH = re.compile(r"^[A-Za-z0-9._/-]+$")
_CODE_EXT = (".py", ".sh", ".md", ".yaml", ".yml", ".json", ".txt", ".cdl", ".nc")
_REJECT = set(" <>*{}$|()=\"'\\#;,:")           # command / placeholder / glob markers
# Real repo top-level dirs: a cited path must be ANCHORED in one of these, or it's a
# basename / a path relative to another tree (wiki subdir, source tree, another repo) —
# not a repo-relative path we can validate. This is the precision anchor.
_TOP_DIRS = {p.name for p in ROOT.iterdir() if p.is_dir()}
# A skill reference: `name` directly adjacent to the word "skill".
_SKILLREF = re.compile(r"`([a-z][a-z0-9-]+)`\s+skill\b|\bskill[s]?\s+`([a-z][a-z0-9-]+)`")


def cited_paths(text):
    """Backtick-delimited spans that are unambiguously repo-relative file/dir paths.

    Pairs backticks LINE BY LINE. Inline code never spans lines, and doing so avoids a
    ``` code fence (or any backtick imbalance) desynchronizing span pairing for the rest of
    the document — which silently dropped real path citations and let dead-refs slip past
    the contract check (see memory/dev_logs_offlineagenthardening/20260702f_*)."""
    out = set()
    for line in text.splitlines():
        for span in _BACKTICK.findall(line):
            s = span.strip()
            m = re.match(r"^(.+?):\d+(?:-\d+)?$", s)    # strip trailing :NNN / :NNN-MMM
            if m:
                s = m.group(1)
            if any(c in _REJECT for c in s):
                continue
            if "/" not in s:                            # bare word / flag / param name
                continue
            if not _PATHISH.match(s):
                continue
            if s.split("/")[0] not in _TOP_DIRS:        # not anchored in a real top-level dir
                continue
            if s.startswith(("memory/dev_logs", "memory/ana_logs")):  # informal pointers (may dangle)
                continue
            if not (s.endswith("/") or s.endswith(_CODE_EXT)):        # require a file ext or a dir
                continue
            out.add(s)
    return out


def cited_skills(text):
    # Line by line, same reason as cited_paths (fence-desync robustness).
    out = set()
    for line in text.splitlines():
        for a, b in _SKILLREF.findall(line):
            out.add(a or b)
    return out


def user_skills():
    """User-level skills at ~/.claude/skills/ — used only to give a better error message
    (policy: ALL skills live in the repo; a user-level one should be moved in)."""
    d = Path.home() / ".claude" / "skills"
    return {p.name for p in d.iterdir() if (p / "SKILL.md").is_file()} if d.is_dir() else set()


def contract_check(disk):
    """Blocking problems. Every backticked repo PATH a skill cites must exist; every
    `<name>` skill it references must be a PROJECT skill (policy: all skills live in the
    repo's .claude/skills/). A ref that resolves only at user level → GLOBAL-SKILL-REF
    (move it into the repo); an unknown one → DEAD-SKILL-REF."""
    problems = []
    proj, usr = set(disk), user_skills()
    for name, text in disk.items():
        for p in sorted(cited_paths(text)):
            if not (ROOT / p.rstrip("/")).exists():
                problems.append(f"DEAD-REF: '{name}' cites `{p}` which does not exist in the repo")
        for s in sorted(cited_skills(text)):
            if s == name or s in proj:
                continue
            if s in usr:
                problems.append(f"GLOBAL-SKILL-REF: '{name}' references `{s}`, which exists only "
                                f"at user level (~/.claude/skills/) — copy it into the repo's "
                                f".claude/skills/ (all skills live in the repo)")
            else:
                problems.append(f"DEAD-SKILL-REF: '{name}' references skill `{s}` which has no dir")
    return problems


def marker_check():
    """Private-comment blocks in every filtered/shipped file must be balanced, and each
    marker must be on its own line (an inline marker is a filter landmine)."""
    problems = []
    for f in FILTERED_FILES:
        if not f.exists():
            continue
        rel = f.relative_to(ROOT)
        opens = closes = 0
        for i, line in enumerate(f.read_text().splitlines(), 1):
            s = line.strip()
            if OPEN_MARK in line:
                if s == OPEN_MARK:
                    opens += 1
                else:
                    problems.append(f"MARKER: {rel}:{i} inline '{OPEN_MARK}' (filter landmine — own line or rephrase)")
            if CLOSE_MARK in line:
                if s == CLOSE_MARK:
                    closes += 1
                else:
                    problems.append(f"MARKER: {rel}:{i} inline '{CLOSE_MARK}' (filter landmine)")
        if opens != closes:
            problems.append(f"MARKER: {rel} unbalanced private blocks ({opens} open != {closes} close)")
    return problems


def main():
    disk = skills_on_disk()
    if not disk:
        print(f"ERROR: no skills under {SKILLS_DIR}"); return 1
    readme, catalog, agents = readme_table_names(), catalog_names(), agents_table_names()
    if readme is None:
        print(f"ERROR: {README} not found"); return 1
    if catalog is None:
        print(f"ERROR: {CATALOG} not found"); return 1
    if agents is None:
        print(f"ERROR: {AGENTS} not found"); return 1

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
    for n in sorted(disk_names - agents):
        problems.append(f"DRIFT: '{n}' on disk but missing from the AGENTS.md 'At a glance' table")
    for n in sorted(agents - disk_names):
        problems.append(f"DRIFT: AGENTS.md table lists '{n}' but no skill dir exists")

    for name, text in disk.items():
        fm = frontmatter_name(text)
        if fm is None:
            problems.append(f"NAME: '{name}' SKILL.md has no `name:` in frontmatter")
        elif fm != name:
            problems.append(f"NAME: '{name}' frontmatter name is '{fm}' (must match dir)")
        if not re.search(r"^## Changelog", text, re.M):
            problems.append(f"CHANGELOG: '{name}' SKILL.md has no `## Changelog` section")

    problems += contract_check(disk)
    problems += marker_check()

    print(f"Skills on disk : {len(disk_names)}")
    print(f"README table   : {len(readme)}")
    print(f"Catalog        : {len(catalog)}")
    print(f"AGENTS.md table: {len(agents)}")
    print()
    if problems:
        print(f"✘ {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("✔ registry + contracts clean — in sync, names match, versioned, cited paths/skills exist, private markers balanced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
