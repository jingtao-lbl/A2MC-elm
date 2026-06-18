#!/usr/bin/env python3
"""
validate_agent_surface.py — pre-flight validator for the interactive-agent surface.

Checks the offline (interactive) agent surface (AGENTS.md, .claude/skills/, the skills
catalog) for the pitfalls that otherwise fail silently — a leaked private path, a
malformed/incomplete skill, a skill that drifts out of the catalog, or a broken internal
link. Complements the leak-scan gate in scripts/sync_to_public.sh (this is the richer,
standalone check). See docs/25_Offline_Interactive_Agent_Mode_Plan.md.

Checks (level in [ERROR, WARN]):

  Leak
    L1  private host path / username in AGENTS.md or .claude/skills/        ERROR
  Skill frontmatter
    F1  SKILL.md frontmatter does not parse as YAML                         ERROR
    F2  frontmatter missing `name` or `description`                         ERROR
    F3  frontmatter missing `modes` block                                   ERROR
    F4  modes.requires_fates not a bool / nutrient_pathway not any|eca|rd   ERROR
    F5  frontmatter `name` != skill directory name                          ERROR
  Drift
    C1  a present skill is absent from the skills catalog                   WARN
    C2  a skill linked from catalog/README/AGENTS has no skill directory    ERROR
  Links
    D1  a relative markdown link in the agent surface resolves to nothing   ERROR

Usage:
    python tools/validate_agent_surface.py [--repo-root DIR] [--strict]

Exit code: 1 if any ERROR (or any WARN under --strict), else 0.

Author: Jing Tao with Claude
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent

LEAK_TOKENS = re.compile(r"/global/|/pscratch/|/Users/|/cfs/cdirs|jingtao|m2467|kougarok_fates_demo")
# Markdown links: [text](target). We validate repo-relative targets only.
MD_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
NON_FILE_LINK = re.compile(r"^(https?:|mailto:|#)")


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


def validate_agent_surface(repo_root: Path) -> List[Finding]:
    repo_root = Path(repo_root)
    skills_dir = repo_root / ".claude" / "skills"
    agents_md = repo_root / "AGENTS.md"
    catalog = repo_root / "docs" / "a2mc_reference" / "skills_catalog.md"
    findings: List[Finding] = []

    if not skills_dir.exists():
        findings.append(Finding("ERROR", "F0", ".claude/skills", "skills directory does not exist"))
        return findings

    skill_files = sorted(skills_dir.glob("*/SKILL.md"))
    present_skills = {p.parent.name for p in skill_files}

    # --- L1: leak scan over the agent surface ---
    surface_md = ([agents_md] if agents_md.exists() else []) + list(skills_dir.rglob("*.md"))
    for f in surface_md:
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if LEAK_TOKENS.search(line):
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
            if not isinstance(m.get("requires_fates"), bool):
                findings.append(Finding("ERROR", "F4", str(rel),
                                        f"modes.requires_fates must be a bool (got {m.get('requires_fates')!r})"))
            if m.get("nutrient_pathway", "any") not in ("any", "eca", "rd"):
                findings.append(Finding("ERROR", "F4", str(rel),
                                        f"modes.nutrient_pathway must be any|eca|rd (got {m.get('nutrient_pathway')!r})"))
        if isinstance(meta, dict) and meta.get("name") and meta["name"] != sf.parent.name:
            findings.append(Finding("ERROR", "F5", str(rel),
                                    f"frontmatter name {meta['name']!r} != directory {sf.parent.name!r}"))

    # --- C1/C2: catalog <-> skills drift ---
    catalog_text = catalog.read_text() if catalog.exists() else ""
    for name in sorted(present_skills):
        if catalog_text and name not in catalog_text:
            findings.append(Finding("WARN", "C1", str(catalog.relative_to(repo_root)),
                                    f"present skill '{name}' is not mentioned in the skills catalog"))
    # Skills referenced by a SKILL.md link path like `<name>/SKILL.md` that don't exist
    for src in ([catalog] if catalog.exists() else []) + ([skills_dir / "README.md"] if (skills_dir / "README.md").exists() else []) + ([agents_md] if agents_md.exists() else []):
        for m in MD_LINK.finditer(src.read_text()):
            mm = re.match(r"([a-z0-9-]+)/SKILL\.md$", m.group(1))
            if mm and mm.group(1) not in present_skills:
                findings.append(Finding("ERROR", "C2", str(src.relative_to(repo_root)),
                                        f"links skill '{mm.group(1)}/SKILL.md' which has no directory"))

    # --- D1: broken relative markdown links across the surface ---
    link_sources = surface_md + ([catalog] if catalog.exists() else [])
    for src in link_sources:
        base = src.parent
        for m in MD_LINK.finditer(src.read_text()):
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
