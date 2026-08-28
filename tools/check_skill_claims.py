#!/usr/bin/env python3
"""Verify a log's "Skills and memory invoked" claim against what was ACTUALLY invoked.

THE FAILURE THIS EXISTS FOR. On 2026-08-22 the R3 Phase 1/2/3/4 calibration logs each listed
their `phaseN` skill under "**Skills:**" without the skill having been invoked. The phases were
worked from recollection of the conventions and the claim was written as though the skill had
been consulted. The PI caught it; nothing mechanical did. Invoking `phase3-diagnosis` afterwards
immediately surfaced a requirement it would have enforced -- a sim-vs-obs time series per scored
target, absent from two phases -- so the false claim had a real cost, not just a cosmetic one.

That section exists precisely to expose analysis done without checking the source of truth. An
untrue entry there is worse than an empty one: it converts a missing check into a passed one.

WHY THIS CAN BE CHECKED AT ALL. The coding-agent transcript records each Skill invocation as a
`tool_use` block, so "which skills were actually invoked" is ground truth on disk rather than a
matter of recollection. This reads the project's transcripts and compares.

    python3 tools/check_skill_claims.py <log.md> [more.md ...]
    python3 tools/check_skill_claims.py --staged

EXIT 0 clean · 1 WARN (cannot verify) · 2 ERROR (a claimed skill was never invoked)

DEGRADES LOUDLY, NEVER SILENTLY. With no transcripts available -- a different harness, a pruned
directory -- this reports "cannot verify" and exits 1. It must never print a clean result it did
not earn; that would be the same defect it is built to catch, one level up.

Author: Jing Tao with Claude
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO / ".claude" / "skills"

#: EFFECTIVE DATE. Verification is against the CURRENT session's transcript, which can say nothing
#: about a log written in an earlier session -- so every historical log would be flagged as unverified
#: and the check would be permanently red, which is how a check stops being read (same reasoning as
#: the embed rule, v2.273). Measured: without this, 15 logs from 2026-08-10/11 were flagged.
#: Logs stamped before this date are exempt, and the exempt COUNT is printed so the backlog is a
#: visible decision rather than a disappeared one.
CLAIMS_RULE_EFFECTIVE = "20260822"

#: Transcript roots, most specific first. The dir name is the project path with separators
#: replaced by '-', which is how the harness names it.
def transcript_dirs() -> list[Path]:
    base = Path.home() / ".claude" / "projects"
    if not base.is_dir():
        return []
    slug = str(REPO).replace("/", "-")
    cands = [base / slug]
    # A clone reached by another path (symlink, $HOME vs /global/u1) gets a different slug, so
    # fall back to any project dir whose name ends with the repo's basename.
    cands += [d for d in base.iterdir()
              if d.is_dir() and d.name.endswith("-" + REPO.name) and d not in cands]
    return [d for d in cands if d.is_dir()]


def known_skills() -> set[str]:
    if not SKILLS_DIR.is_dir():
        return set()
    return {d.name for d in SKILLS_DIR.iterdir() if (d / "SKILL.md").is_file()}


def invoked_skills() -> tuple[dict, int]:
    """-> ({skill: latest YYYYMMDD it was invoked}, n transcripts read).

    SCOPE IS THE SESSION, not the calendar day, and both alternatives were tried and rejected:

      * ALL transcripts -- too loose. A skill invoked weeks ago in an unrelated context validates
        today's log. Measured: this passed `phase1-exploration` while catching its two siblings.
      * the log's DATE -- too strict. A session runs for days across compaction, and a skill
        invoked on its first day is still loaded and governing on its third. Measured: this
        flagged `calibration-log`, `plotting` and `calibration-discipline` as stale when they had
        genuinely been invoked in the same continuous session.

    So: the CURRENT session (newest transcript). That is the session staging the commit, and a
    skill invoked anywhere in it was actually read.
    """
    files = sorted((f for d in transcript_dirs() for f in d.glob("*.jsonl")),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    found, n = {}, 0
    for f in files[:1]:            # the current session only
            n += 1
            try:
                with open(f, errors="ignore") as fh:
                    for line in fh:
                        # Cheap prefilter: parsing 50 MB of JSON per file is not free.
                        if '"Skill"' not in line:
                            continue
                        try:
                            rec = json.loads(line)
                        except Exception:
                            continue
                        content = (rec.get("message") or {}).get("content") or []
                        if not isinstance(content, list):
                            continue
                        for blk in content:
                            if (isinstance(blk, dict) and blk.get("type") == "tool_use"
                                    and blk.get("name") == "Skill"):
                                s = (blk.get("input") or {}).get("skill")
                                if not s:
                                    continue
                                s = s.strip().lstrip("/")
                                day = (rec.get("timestamp") or "")[:10].replace("-", "")
                                if day and (s not in found or day > found[s]):
                                    found[s] = day
            except OSError:
                continue
    return found, n


#: The MEMORY claim bullet. Memories are surfaced by the harness rather than invoked as a tool,
#: so "did you read it" is NOT verifiable the way a Skill call is. What IS verifiable is whether
#: the memory EXISTS -- an invented or misremembered name is a real and common error, and it makes
#: the citation unresolvable for the next reader.
MEMCLAIM = re.compile(r"^[ \t]*[-*][ \t]*\*\*Memory:?\*\*(.*?)(?=\n[ \t]*[-*][ \t]*\*\*|\n[ \t]*\n|\Z)",
                      re.M | re.S)
MEMNAME = re.compile(r"(?:`|\[\[)((?:feedback|reference|project)_[a-z0-9_]+)(?:`|\]\])")


def claimed_memories(text: str) -> set[str]:
    out = set()
    for m in MEMCLAIM.finditer(text):
        out.update(MEMNAME.findall(m.group(1)))
    return out


def known_memories() -> set[str]:
    d = REPO / ".claude_memory"
    return {f.stem for f in d.glob("*.md")} if d.is_dir() else set()


#: The claim BULLET, including its wrapped continuation lines. Capturing only the first line is
#: silent UNDER-detection -- the worst failure mode for a check, because it reports clean. Measured:
#: the R3 Phase 1 log claims `phase1-exploration` on the SECOND line of the bullet, and a
#: first-line-only pattern passed it while catching its two siblings. The bullet runs until a blank
#: line or the next top-level bullet.
CLAIM = re.compile(r"^[ \t]*[-*][ \t]*\*\*Skills?:?\*\*(.*?)(?=\n[ \t]*[-*][ \t]*\*\*|\n[ \t]*\n|\Z)",
                   re.M | re.S)
BACKTICKED = re.compile(r"`([A-Za-z0-9][A-Za-z0-9._-]*)`")


def claimed_skills(text: str, universe: set[str]) -> set[str]:
    """Backticked tokens on the Skills line that are REAL skill names.

    Restricting to the known-skill universe is what keeps prose out: a line reading
    "`log` (the skill amended)" yields `log`, while "`PhaseLogger`" yields nothing.
    """
    out = set()
    for m in CLAIM.finditer(text):
        for tok in BACKTICKED.findall(m.group(1)):
            if tok in universe:
                out.add(tok)
    return out


# NOTE: git yields paths WITHOUT a leading slash ('memory/dev_logs_adapterkit/x.md'), so a
# test for '/memory/dev_logs' silently matches nothing. That made this check skip every dev
# log while reporting clean -- caught 2026-08-22 by a test that staged a real modified log.
def staged_logs() -> list[Path]:
    out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
                         cwd=REPO, capture_output=True, text=True).stdout.split()
    keep = []
    for rel in out:
        if not rel.endswith(".md"):
            continue
        if ("/memory/logs/" in rel or "memory/dev_logs" in rel
                or "memory/model_logs/" in rel or "memory/ana_logs/" in rel):
            keep.append(REPO / rel)
    return keep


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__.strip().split("\n\n")[0])
        return 0
    files = staged_logs() if argv[0] == "--staged" else [Path(a) for a in argv]
    files = [f for f in files if f.is_file()]
    if not files:
        print("check_skill_claims: no log files to check")
        return 0

    universe = known_skills()
    invoked, ntr = invoked_skills()

    STEM_DATE = re.compile(r"(\d{8})")

    if ntr == 0:
        print("  [warn] check_skill_claims: NO transcript found — cannot verify skill claims.")
        print("         This is not a pass. Skill claims in these logs are unverified:")
        for f in files:
            c = claimed_skills(f.read_text(errors="replace"), universe)
            if c:
                print(f"           {f.name}: claims {sorted(c)}")
        return 1

    errors, checked, exempt = [], 0, 0
    for f in files:
        m = STEM_DATE.match(f.name)
        if m and m.group(1) < CLAIMS_RULE_EFFECTIVE:
            exempt += 1
            continue
        text = f.read_text(errors="replace")
        c = claimed_skills(text, universe)
        if not c:
            continue
        checked += 1
        missing, stale, ok = [], [], []
        for s in sorted(c):
            (ok if s in invoked else missing).append(s)
        # Memory names: existence only. Unresolvable citations are a separate, checkable error.
        mem_universe = known_memories()
        if mem_universe:
            ghosts = sorted(m for m in claimed_memories(text) if m not in mem_universe)
            if ghosts:
                stale.extend(f"MEMORY does not exist: {g}" for g in ghosts)
        if missing or stale:
            errors.append((f.name, missing, stale, ok))

    if errors:
        print(f"\n✘ check_skill_claims: {len(errors)} log(s) claim a skill not invoked for that log")
        for name, missing, stale, ok in errors:
            print(f"  - {name}")
            if missing:
                print(f"      claimed but NEVER invoked : {', '.join(missing)}")
            if stale:
                for s in stale:
                    print(f"      {s}")
            if ok:
                print(f"      genuinely invoked         : {', '.join(ok)}")
        print("\n  Either invoke the skill and redo the step it governs, or remove it from the")
        print("  claim. 'Skills and memory invoked' exists to expose work done without checking")
        print("  the source of truth — a false entry turns a missing check into a passed one.")
        print(f"  (checked against the CURRENT session's transcript; "
              f"{len(invoked)} distinct skill(s) invoked in it: {', '.join(sorted(invoked))})")
        return 2

    if exempt:
        print(f"  [note] {exempt} log(s) predate the rule ({CLAIMS_RULE_EFFECTIVE}) and are exempt: "
              f"they were written in earlier sessions, which the current transcript cannot speak to.")
    print(f"✔ check_skill_claims: {checked} log(s) with skill claims, all verified against "
          f"{ntr} transcript(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
