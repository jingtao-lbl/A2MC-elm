#!/usr/bin/env python3
"""
validate_agent_surface.py — pre-flight validator for the interactive-agent surface.

Checks the offline (interactive) agent surface (AGENTS.md, .claude/skills/, the skills
catalog) for the pitfalls that otherwise fail silently — a leaked private path, a
malformed/incomplete skill, or a broken internal link. (Registry/catalog parity — a skill
missing from a registry, or a registry entry with no skill dir — is owned by
tools/check_skill_registry.py, the 4-way coherence gate.) Complements the leak-scan gate in
scripts/sync_to_public.sh (this is the richer, standalone check).
See docs/25_Offline_Interactive_Agent_Mode_Plan.md.

Checks (level in [ERROR, WARN]):

  Leak
    L1  private host path / username in AGENTS.md or .claude/skills/        ERROR
  Skill frontmatter
    F1  SKILL.md frontmatter does not parse as YAML                         ERROR
    F2  frontmatter missing `name` or `description`                         ERROR
    F3  frontmatter missing `modes` block                                   ERROR
    F4  modes.requires_fates not a bool / nutrient_pathway not any|eca|rd   ERROR
    F5  frontmatter `name` != skill directory name                          ERROR
  Links
    D1  a relative markdown link in the agent surface resolves to nothing   ERROR
  Enumeration
    G1  git could not enumerate the surface; fell back to a filesystem walk WARN

  (Registry/catalog parity — C1/C2 in earlier versions — moved to
  tools/check_skill_registry.py, the 4-way coherence gate. This validator is the
  publish/quality gate: leak + frontmatter schema + link integrity.)

Usage:
    python tools/validate_agent_surface.py [--repo-root DIR] [--strict]

Exit code: 1 if any ERROR (or any WARN under --strict), else 0.

Author: Jing Tao with Claude
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# LEAK TOKENS -- IDENTITY ONLY, NOT PATH SHAPE.
# ---------------------------------------------------------------------------
# Public-facing text SHOULD carry a real path SHAPE with the identifying segments
# templated -- "shared NERSC scratch (such as /global/cfs/cdirs/<project>/<user>/...)",
# never a bare "some shared filesystem". The shape is public knowledge (documented NERSC
# mount points) and is the only thing that makes the text usable: a reader substitutes
# their own values. So the structural tokens (`/global/`, `/pscratch/`, `/Users/`,
# `/cfs/cdirs`) are NOT leaks on their own and are deliberately absent below -- keeping
# them condemned the useful half of every scrubbed example (feedback_scrub_paths_keep_the_example).
#
# What remains is IDENTITY: the username and the NERSC project codes this repo actually
# uses (m2467 = model checkouts, m4218 = scratch; see reference_main_tmp_cfs_scratch_path).
# These are not secrets (allocation codes appear in published acknowledgements; the
# username is inferable from the already-public contact address) -- they stay tokens
# because a real personal path necessarily contains one, so catching the identity segment
# still catches the whole path: `~/...` trips both `m2467`
# and `jingtao` even though neither `/global/` nor `/cfs/cdirs` does anymore.
#
# PARSED BY scripts/sync_to_public.sh. This assignment and PUBLIC_CONTACT below are the
# single source of truth for the sync leg's agent-surface leak gate, which reads them with
# sed rather than keeping its own copy (the copy it used to keep drifted for two months).
# Keep both on ONE line in the exact form `NAME = re.compile(r"...")` — the sync script
# fails closed if it cannot parse them, so a reformat breaks the sync loudly, not silently.
LEAK_TOKENS = re.compile(r"jingtao|m2467|m4218|kougarok_fates_demo")
# The bare token `jingtao` above exists to catch HOST PATHS (~,
# ~). The maintainer's CONTACT ADDRESS is a different thing and is already
# published — it is in the shipped (filtered) CLAUDE.md and in README.md — so a skill that
# tells a reader how to reach them is not a leak. Stripped before the scan so the path
# tokens stay strict. (2026-08-02: this fired on .claude/skills/README.md's note about
# requesting the maintainer-side private skills.)
PUBLIC_CONTACT = re.compile(r"jingtao@lbl\.gov")
# Markdown links: [text](target). We validate repo-relative targets only.
MD_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
NON_FILE_LINK = re.compile(r"^(https?:|mailto:|#)")
# Fenced blocks and inline code spans, stripped before link-scanning: a skill that
# DOCUMENTS markdown syntax (e.g. write-report teaching `![](fig.png)`) is showing an
# example, not linking a file. Parsing those as live links is a false positive.
CODE_SPAN = re.compile(r"```.*?```|`[^`\n]*`", re.S)


@dataclass
class Finding:
    level: str   # "ERROR" | "WARN"
    code: str
    where: str
    message: str


def _frontmatter(text: str):
    """Return the YAML frontmatter dict for a SKILL.md, or raise."""
    if not text.startswith("---"):
        raise ValueError("no frontmatter")
    return yaml.safe_load(text.split("---", 2)[1])


def _on_surface(p: Path, skills_dir: Path) -> bool:
    """False for a path inside a dot-directory (`.ipynb_checkpoints/`, ...).

    Filesystem-walk fallback predicate only (see `_enumerate_skills_md`). `parts[:-1]`
    excludes the filename, so only DIRECTORY components are tested.
    """
    return not any(part.startswith(".") for part in p.relative_to(skills_dir).parts[:-1])


def _enumerate_skills_md(repo_root: Path, skills_dir: Path) -> Tuple[List[Path], bool]:
    """Markdown under .claude/skills/ that could reach a published copy. (files, used_git).

    Enumerated with `git ls-files`, not a filesystem walk (feedback_a_gate_must_measure_the_branch_not_the_disk):
    a gate must measure what is COMMITTED, not what happens to be on disk. A gitignored
    Jupyter checkpoint (`.ipynb_checkpoints/SKILL-checkpoint.md`) is a stale copy of a
    skill that can never be published, so scanning it fails this gate for something no
    commit can fix — and fails on whichever clone happens to have opened the file in
    Jupyter while passing on every other one. A gate whose verdict depends on the machine
    is not a gate.

    `--cached --others --exclude-standard` = tracked PLUS untracked-but-not-ignored, so a
    brand-new skill that has not been `git add`ed yet is still validated (narrowing to
    `--cached` only would trade a false positive for a false negative, the worse trade on
    a leak gate).

    Falls back to the dot-directory-filtered filesystem walk (`_on_surface`) when git is
    unavailable (an extracted copy, a non-git tmpdir in a unit test) — degradation is
    reported to the caller as a WARN (G1), never silently assumed away.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "-z",
             "--cached", "--others", "--exclude-standard", "--", ".claude/skills"],
            capture_output=True, check=True, text=True, timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ([p for p in sorted(skills_dir.rglob("*.md")) if _on_surface(p, skills_dir)], False)
    return (sorted({repo_root / rel for rel in out.split("\0") if rel.endswith(".md")}), True)


def validate_agent_surface(repo_root: Path) -> List[Finding]:
    repo_root = Path(repo_root)
    skills_dir = repo_root / ".claude" / "skills"
    agents_md = repo_root / "AGENTS.md"
    catalog = repo_root / "docs" / "a2mc_reference" / "skills_catalog.md"
    findings: List[Finding] = []

    if not skills_dir.exists():
        findings.append(Finding("ERROR", "F0", ".claude/skills", "skills directory does not exist"))
        return findings

    skills_md, used_git = _enumerate_skills_md(repo_root, skills_dir)
    if not used_git:
        findings.append(Finding("WARN", "G1", ".claude/skills",
                                "git could not enumerate the surface; walked the filesystem "
                                "instead (ignored files other than checkpoints may be scanned)"))
    skill_files = sorted(p for p in skills_md
                         if p.name == "SKILL.md" and p.parent.parent == skills_dir)

    # --- L1: leak scan over the agent surface ---
    surface_md = ([agents_md] if agents_md.exists() else []) + skills_md
    for f in surface_md:
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if LEAK_TOKENS.search(PUBLIC_CONTACT.sub("", line)):
                findings.append(Finding("ERROR", "L1", f"{f.relative_to(repo_root)}:{i}",
                                        f"private path/username token: {line.strip()[:80]}"))

    # --- F*: skill frontmatter ---
    for sf in skill_files:
        rel = sf.relative_to(repo_root)
        try:
            meta = _frontmatter(sf.read_text())
        except Exception as e:
            findings.append(Finding("ERROR", "F1", str(rel), f"frontmatter does not parse: {e}"))
            continue
        if not isinstance(meta, dict):
            findings.append(Finding("ERROR", "F1", str(rel), "frontmatter is not a mapping"))
            continue
        if "name" not in meta or "description" not in meta:
            findings.append(Finding("ERROR", "F2", str(rel), "missing name/description"))
        if "modes" not in meta:
            findings.append(Finding("ERROR", "F3", str(rel), "missing modes: block"))
        else:
            m = meta["modes"] or {}
            # A scalar `modes: any` (instead of the mapping) used to crash here with
            # AttributeError on .get — report it as a finding instead of dying.
            if not isinstance(m, dict):
                findings.append(Finding("ERROR", "F4", str(rel),
                                        f"modes: must be a mapping (requires_fates/nutrient_pathway/...), got scalar {m!r}"))
                continue
            if not isinstance(m.get("requires_fates"), bool):
                findings.append(Finding("ERROR", "F4", str(rel),
                                        f"modes.requires_fates must be a bool (got {m.get('requires_fates')!r})"))
            if m.get("nutrient_pathway", "any") not in ("any", "eca", "rd"):
                findings.append(Finding("ERROR", "F4", str(rel),
                                        f"modes.nutrient_pathway must be any|eca|rd (got {m.get('nutrient_pathway')!r})"))
        if isinstance(meta, dict) and meta.get("name") and meta["name"] != sf.parent.name:
            findings.append(Finding("ERROR", "F5", str(rel),
                                    f"frontmatter name {meta['name']!r} != directory {sf.parent.name!r}"))

    # --- D1: broken relative markdown links across the surface ---
    link_sources = surface_md + ([catalog] if catalog.exists() else [])
    for src in link_sources:
        base = src.parent
        for m in MD_LINK.finditer(CODE_SPAN.sub("", src.read_text())):
            target = m.group(1).split("#", 1)[0].strip()
            if not target or NON_FILE_LINK.match(target):
                continue
            if "<" in target or ">" in target:
                continue  # template placeholder (e.g. <name>/SKILL.md), not a real link
            resolved = (base / target).resolve()
            if not resolved.exists():
                findings.append(Finding("ERROR", "D1", str(src.relative_to(repo_root)),
                                        f"broken relative link: {m.group(1)}"))

    return findings


def _print(findings: List[Finding]) -> None:
    print("\nValidating interactive-agent surface (AGENTS.md + .claude/skills/ + catalog)")
    print("-" * 78)
    if not findings:
        print("  ✓ No issues found.")
    else:
        for f in sorted(findings, key=lambda x: (x.level != "ERROR", x.code)):
            mark = "✗" if f.level == "ERROR" else "!"
            print(f"  {mark} [{f.level:<5} {f.code}] {f.where}: {f.message}")
    n_err = sum(1 for f in findings if f.level == "ERROR")
    n_warn = sum(1 for f in findings if f.level == "WARN")
    print("-" * 78)
    print(f"  {n_err} error(s), {n_warn} warning(s)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate the interactive-agent surface.")
    ap.add_argument("--repo-root", default=str(_REPO_ROOT))
    ap.add_argument("--strict", action="store_true", help="Treat warnings as failures (exit 1)")
    args = ap.parse_args()
    findings = validate_agent_surface(Path(args.repo_root))
    _print(findings)
    n_err = sum(1 for f in findings if f.level == "ERROR")
    n_warn = sum(1 for f in findings if f.level == "WARN")
    return 1 if (n_err or (args.strict and n_warn)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
