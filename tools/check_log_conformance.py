#!/usr/bin/env python3
"""check_log_conformance.py — assert a dev/ana log matches the `log` skill's contract.

WHY THIS EXISTS, AND WHY IT IS A CHECKER RATHER THAN A CHECKLIST LINE
--------------------------------------------------------------------
On 2026-08-01 a single session (on the `adapter-kit` branch, this repo's sibling) produced four
conformance failures in a row:

  * a 70-commit merge went entirely unlogged (the skill was never invoked);
  * the `log` skill CHANGED MID-SESSION — a commit added the "Skills and memory invoked" section
    and arrived inside the very merge that went unlogged — and the two logs written afterwards
    were produced from memory of the skill's earlier shape, so both were non-conformant;
  * one log was missing the REQUIRED `## Files Changed` section, a requirement that long predated
    the change and simply went unchecked;
  * one log was written without invoking the skill at all, because no subtype in its table
    matched the shape needed.

The lesson is the one in `feedback_skill_is_authoritative_over_memory`: "I read it earlier" is not
"I read the current one". A checklist item asking the author to re-read the skill is exactly the
step an author who already skipped the skill will skip again — so the check is mechanical
(`feedback_build_validators_for_all_pitfalls`).

This exact class of drift happened on THIS branch too, in miniature, during the 2026-08-14
reconciliation that produced this file: the `log` skill's own required-section order changed
mid-thread (Next moved from position 6 to last; Cross-references became required), which is
precisely the shape of change this checker exists to catch going forward.

DELIBERATELY DEPENDENCY-FREE: stdlib only, no PyYAML. The Tier-2 skill smoke harness cannot go
green on a Mac precisely because it shells a checker that needs `yaml` under a system `python3`
that lacks it; this one runs anywhere.

WHAT IT CHECKS
--------------
  L00 wrong stream   refuses a calibration log (use_cases/*/memory/logs/) rather than mis-scoring
                     it against this contract — see `wrong_stream()`; the mirror-image guard
                     lives in the sibling `tools/check_calibration_log_conformance.py`
  L1  filename       `YYYYMMDDx_Topic_In_Title_Case.md` (x = a..z, then za..zz)
  L2  header order   Title -> Date -> Author -> Type -> [Version] -> Branch
                     `Version` is REQUIRED for dev logs, FORBIDDEN for ana logs
  L3  sections       required sections present, PER SUBTYPE — Regular/Session/Audit-Review/
                     Handoff_To_Main/Reflection each have their own required set (see
                     `_REQUIRED_BY_SUBTYPE`), detected from the log's own shape via `_subtype()`.
                     Sections with a per-section "required since" date are not retroactively
                     failed on logs dated before that date.
  L5  branch match   a log under `dev_logs_<branch>/` names that branch
  L6  citations      every skill/memory NAMED in "Skills and memory invoked" actually exists

SUBTYPE-AWARE SINCE 2026-08-14. Originally L3 checked only the Regular-dev-log shape — a Session/
Audit-Review/Handoff_To_Main/Reflection log would be false-rejected for sections that subtype
never has (a Handoff_To_Main log has no Problem/Solution at all). `adapter-kit`'s own checker had
the identical limitation, first noted there 2026-08-01 and left unresolved for two weeks — until a
same-day parallel session there built subtype detection with measured evidence
(`memory/dev_logs_adapterkit/20260814e_Log_Spec_Gaps_Closed_And_Checker_Made_Subtype_Aware.md`:
flat-required-list wrongly failed 2 correctly-formed handoff logs; subtype-aware correctly failed
1 genuine violation and 0 false ones). Ported the idea here, but the mapping itself is `main`'s
own, grounded in `main`'s own logs, not copied: a real `main` Handoff_To_Main log
(`20260802g_Handoff_To_AdapterKit_Four_Generic_Fixes.md`) has no Summary/Files Changed/
Verification either, not just no Problem/Solution — broader than what adapter-kit's own base-4
assumed for their corpus. Section-heading matching also normalizes a trailing parenthetical
(`## Files Changed (net, across the session)` counts as `Files Changed` present), needed because
main's own Session-log convention appends qualifiers to headings.

Scope: pass explicit paths (what the pre-commit hook does), or a directory plus
`--since YYYYMMDD` for a sweep.

Exit: 0 clean · 1 warnings only · 2 any error.

Usage
-----
    python3 tools/check_log_conformance.py memory/dev_logs/20260814e_*.md
    python3 tools/check_log_conformance.py --dir memory/dev_logs --since 20260801
    python3 tools/check_log_conformance.py --staged        # what the hook runs

Author: Jing Tao with Claude
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Header fields in their required order. `Version` is conditional (see L2).
_DEV_HEADER = ["Date", "Author", "Type", "Version", "Branch"]
_ANA_HEADER = ["Date", "Author", "Type", "Branch"]

# Section -> the date (YYYYMMDD) it became required, or None if it has always been required.
# A log dated STRICTLY BEFORE its section's date is not retroactively failed; dated exactly ON
# the boundary day is a WARN (the rule may have landed on this repo later the same day); dated
# after is an ERROR. See `check_file()`'s L3 loop.
#
# PER SUBTYPE — see the module docstring's "SUBTYPE-AWARE" note. Each dict is a complete,
# independent required-set for that subtype, not "the base list plus exceptions": measurement
# against main's own logs (see docstring) showed Handoff_To_Main lacks even Summary/Files
# Changed/Verification, so a shared "universal base" would have been wrong for it too, not just
# for Problem/Solution/Next.
#
# Dates verified against `memory/dev_logs/CLAUDE.md` directly (not carried over from
# `adapter-kit`'s checker, which used a single 2026-08-01 date for one section only — that date is
# `adapter-kit`'s own history, not `main`'s; `main`'s "Skills and memory invoked" AND "Next" became
# required together on 2026-08-03, confirmed by re-reading the spec rather than recalling an
# earlier conversation turn, per `feedback_reread_the_decision_before_writing_its_successor`).
_REQUIRED_BY_SUBTYPE = {
    "regular": {
        "Summary": None, "Problem": None, "Solution": None, "Files Changed": None,
        "Verification": None, "Skills and memory invoked": "20260803",
        "Cross-references": "20260814", "Next": "20260803",
    },
    "audit": {
        "Summary": None, "Problem": None, "Solution": None, "Files Changed": None,
        "Verification": None, "Skills and memory invoked": "20260803",
        "Cross-references": "20260814",
    },
    "session": {
        "Summary": None, "Files Changed": None, "Verification": None,
        "Skills and memory invoked": "20260803", "Cross-references": "20260814",
    },
    "reflection": {
        "Summary": None, "Files Changed": None, "Verification": None,
        "Skills and memory invoked": "20260803", "Cross-references": "20260814",
        "Next": "20260803",
    },
    "handoff": {
        "Cross-references": "20260814",
    },
}
# ana logs stay freer-form (memory/dev_logs/CLAUDE.md never gave them a formal required-section
# list). This single entry is inherited from `adapter-kit`'s checker as-is — reconciling it was
# out of scope for the 2026-08-14 PI decision, which was about the dev-log list specifically.
_ANA_SECTIONS = {"Cross-references": None}
_CAPABILITY = "Skills and memory invoked"

_FNAME = re.compile(r"^(?P<date>\d{8})(?P<letter>z*[a-z])_(?P<topic>[A-Z][A-Za-z0-9]*"
                    r"(?:_[A-Za-z0-9.]+)*)\.md$")

# Files that LIVE in a log directory but are not logs. `memory/dev_logs/CLAUDE.md` is the
# style guide itself: staging it made the pre-commit hook check the spec as though it were an
# instance of the spec, and fail it 5 ways (2026-08-03, the same incident that made "Next" and
# "Skills and memory invoked" required — this class of self-check hazard is why the exclusion
# exists).
_NOT_LOGS = {"CLAUDE.md", "README.md", "MEMORY.md", "index.md"}


class Finding:
    __slots__ = ("path", "code", "level", "msg")

    def __init__(self, path, code, level, msg):
        self.path, self.code, self.level, self.msg = path, code, level, msg

    def __str__(self):
        tag = "ERROR" if self.level == "error" else "warn "
        return f"  {tag} [{self.code}] {self.path.name}: {self.msg}"


def _is_ana(path: Path) -> bool:
    return "ana_logs" in path.parts


def _branch_from_dir(path: Path) -> str | None:
    """`memory/dev_logs_<branchname>/` -> the branch token."""
    for part in path.parts:
        if part.startswith("dev_logs_"):
            return part[len("dev_logs_"):]
    return None


def _subtype(path: Path, present: set, text: str) -> str:
    """Best-effort subtype, from the log's own shape rather than a declared field.

    The `log` skill does not require a machine-readable subtype marker, so inferring from the
    folder and the sections a writer actually used is the only signal that cannot go stale
    relative to the content. Checked in order of reliability: Reflection lives in a dedicated
    physical subfolder (unambiguous); Handoff_To_Main and Session each have a distinctive section
    heading no other subtype uses; Audit/Review is inferred from `## Files Changed` reading "None"
    (its defining shape per the skill's own subtype table — needs the section BODY, not just
    presence, hence the regex rather than a `present` membership test); anything else defaults to
    Regular, the common case and the one every other subtype is defined as a departure from.
    """
    if "reflection" in path.parts:
        return "reflection"
    if "Why this is a handoff" in present:
        return "handoff"
    # An INBOUND handoff (written from another branch) has no "Why this is a handoff"
    # section -- that heading is main's OUTBOUND Handoff_To_Main convention -- so it
    # fell through to "regular" and was judged against a contract it can never meet
    # (it reports another session's work, so it has no Files Changed here). The
    # declared `Type:` header is the reliable signal, and it must START WITH
    # "Handoff": matching loosely would also capture "Session log / Handoff", which
    # is a session log that happens to hand off and passes its own contract today.
    # Measured against every log in this folder: exactly 3 reclassify, all genuine
    # handoffs (20260805b + the two inbound adapter-kit ones), 0 false positives.
    if re.search(r"^\*\*Type:\*\*\s*Handoff\b", text, re.M | re.I):
        return "handoff"
    if "State at session end" in present or "What was done" in present:
        return "session"
    if re.search(r"^## Files Changed\b.*$\s*\n+\s*None\b", text, re.M):
        return "audit"
    return "regular"


def wrong_stream(path: Path) -> str | None:
    """Is this path unambiguously a CALIBRATION log, which this tool does not govern?

    Fires only on a positive match (a path under `use_cases/*/memory/logs/`), never on an
    ambiguous one. Without this guard the two checkers can silently mis-serve each other: this
    tool run against a calibration log reports several "missing section" errors that read as
    "your log is broken" when the truth is "wrong tool" (measured: 9 errors on a real Kougarok
    phase log, none of them genuine — a calibration log has no Summary/Problem/Solution/Files
    Changed/Verification/Version/Branch at all). `check_calibration_log_conformance.py` carries
    the mirror-image guard against a dev/ana log; the two are only meaningful as a pair.
    """
    parts = path.parts
    if "use_cases" in parts and "logs" in parts and "memory" in parts:
        return ("a CALIBRATION log (use_cases/<site>/memory/logs/) — use "
                "`tools/check_calibration_log_conformance.py`, whose contract is different "
                "(PhaseLogger sections / free-form + Site/Phase/Round header, no Version/Branch)")
    return None


def check_file(path: Path) -> list[Finding]:
    out: list[Finding] = []
    if not path.is_file():
        return [Finding(path, "L0", "error", "file not found")]
    other = wrong_stream(path)
    if other:
        return [Finding(path, "L00", "error", f"wrong tool: this is {other}")]
    text = path.read_text(errors="replace")
    lines = text.splitlines()
    ana = _is_ana(path)

    # ---- L1 filename ----
    m = _FNAME.match(path.name)
    if not m:
        out.append(Finding(path, "L1", "error",
                           "filename is not YYYYMMDDx_Topic_In_Title_Case.md"))
        date = ""
    else:
        date = m.group("date")
        # The pattern only proves "eight digits". Check it is a REAL date.
        try:
            datetime.strptime(date, "%Y%m%d")
        except ValueError:
            out.append(Finding(path, "L1", "error",
                               f"filename date {date!r} is not a real calendar date"))
            date = ""

    # ---- L2 header order ----
    head = lines[:14]
    seen: list[str] = []
    for ln in head:
        fm = re.match(r"^\*\*(\w+):\*\*", ln)
        if fm:
            seen.append(fm.group(1))
    want = _ANA_HEADER if ana else _DEV_HEADER
    if not lines or not lines[0].startswith("# "):
        out.append(Finding(path, "L2", "error", "first line is not an `# H1` title"))
    if ana and "Version" in seen:
        out.append(Finding(path, "L2", "error",
                           "ana logs must NOT carry a Version field"))
    missing_hdr = [f for f in want if f not in seen]
    if missing_hdr:
        out.append(Finding(path, "L2", "error",
                           f"header missing {', '.join(missing_hdr)}"))
    else:
        order = [f for f in seen if f in want]
        if order != want:
            out.append(Finding(path, "L2", "warn",
                               f"header order is {order}, expected {want}"))

    # ---- L3 required sections (per-subtype, per-section since-date) ----
    # A heading may carry a trailing qualifier (`## Files Changed (net, across the session)`,
    # `## Next Action: ...`) — main's own Session-log convention does this. Both the raw heading
    # and the parenthetical/colon-stripped form go into `present`, so a qualified heading still
    # satisfies the plain section name a subtype requires.
    present: set[str] = set()
    for ln in lines:
        if ln.startswith("## "):
            h = ln[3:].strip()
            present.add(h)
            present.add(re.sub(r"\s*\(.*\)\s*$", "", h).strip())
            if ":" in h:
                present.add(h.split(":", 1)[0].strip())
    sub = "ana" if ana else _subtype(path, present, text)
    want_secs = _ANA_SECTIONS if ana else _REQUIRED_BY_SUBTYPE[sub]
    for sec, since in want_secs.items():
        if sec in present:
            continue
        if since is None:
            out.append(Finding(path, "L3", "error",
                               f"missing required section '## {sec}' (subtype: {sub})"))
            continue
        if not date:
            # Filename date unparseable (already flagged L1) -- can't date-gate, be conservative.
            out.append(Finding(path, "L3", "error",
                               f"missing required section '## {sec}' (subtype: {sub})"))
            continue
        if date < since:
            continue                          # predates the rule; not retroactively failed
        boundary = date == since
        out.append(Finding(
            path, "L3", "warn" if boundary else "error",
            f"missing required section '## {sec}' (subtype: {sub})"
            + (" — but dated on the boundary day, so it may predate the rule reaching this repo"
               if boundary
               else f" (required for logs dated on/after {since}; 'None' is a valid answer)")))

    # ---- L5 branch header matches the directory ----
    want_branch = _branch_from_dir(path)
    if want_branch:
        bm = re.search(r"^\*\*Branch:\*\*\s*(.+?)\s*$", text, re.M)
        if bm:
            squashed = bm.group(1).replace("-", "").replace("_", "").lower()
            if want_branch.lower() not in squashed:
                out.append(Finding(path, "L5", "warn",
                                   f"Branch header {bm.group(1)!r} does not match "
                                   f"directory token {want_branch!r}"))

    out.extend(_check_capability_names(path, text))
    return out


# A log stem (`20260801e`, `20260814d_Audit_...`) is a legitimate citation, not a skill name.
_STEM = re.compile(r"^\d{8}[a-z]{1,3}(_|$)")
_MEM_PREFIX = ("feedback_", "project_", "reference_", "user_")


def _check_capability_names(path: Path, text: str) -> list:
    """L6 — the skills and memories a log CLAIMS to have used must exist.

    The L3 check only asserts that the "Skills and memory invoked" section is PRESENT. A log
    could name `phase9-nonsense` or an invented memory and still pass L3 — which is worse than
    omitting the section: it asserts a provenance the reader cannot follow, and it silently
    breaks the cross-reference pass `memory-checkup` runs over exactly these names.

    Deliberately narrow: only backticked single tokens on the `**Skills:**` / `**Memory:**`
    lines of that one section are considered; anything with a path separator, a shell variable,
    whitespace, or a log-stem shape (`_STEM`) is skipped, so a log citing another log by its
    dated stem (a legitimate cross-reference, not a skill/memory claim) is not flagged.
    """
    out = []
    m = re.search(rf"^## {re.escape(_CAPABILITY)}\s*$(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not m:
        return out                                   # absence is L3's business, not L6's
    section = m.group(1)
    skills_dir, mem_dir = REPO / ".claude" / "skills", REPO / ".claude_memory"

    for label, kind in (("Skills", "skill"), ("Memory", "memory")):
        line = re.search(rf"\*\*{label}:?\*\*(.*)", section)
        if not line:
            continue
        for tok in (t.strip().strip(",.") for t in re.findall(r"`([^`\n]+)`", line.group(1))):
            if not tok or "/" in tok or "$" in tok or " " in tok or _STEM.match(tok):
                continue
            # A CLI flag is categorically not a skill or memory name -- no skill
            # directory starts with "-". Without this, a log that legitimately
            # names an interface it used (`--file`, `--dry-run`) inside the
            # Skills line is rejected for citing a skill that "does not exist".
            if tok.startswith("-"):
                continue
            if kind == "skill":
                if not (skills_dir / tok).is_dir():
                    out.append(Finding(path, "L6", "error",
                                       f"claims skill `{tok}`, which is not in .claude/skills/"))
            else:
                if not tok.startswith(_MEM_PREFIX):
                    continue                          # not a memory slug; leave it alone
                if not (mem_dir / f"{tok}.md").exists():
                    out.append(Finding(path, "L6", "error",
                                       f"claims memory `{tok}`, which is not in .claude_memory/"))
    return out


def _staged_logs() -> list[Path]:
    try:
        raw = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            text=True, cwd=REPO)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    keep = []
    for line in raw.splitlines():
        p = Path(line)
        if p.suffix != ".md":
            continue
        if p.name in _NOT_LOGS:
            continue
        # dev_logs*/ana_logs only. model_logs/ is a real 3rd stream on `main` (root CLAUDE.md
        # §8) with a genuinely different header/section shape (Model + Experiment branch, not
        # Version + Branch) -- checking it against _DEV_HEADER/_DEV_SECTIONS would be as wrong
        # as checking a phase log that way. Held by review, not by this gate, for now.
        if any(part.startswith("dev_logs") or part == "ana_logs" for part in p.parts):
            keep.append(REPO / p)
    return keep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", type=Path, help="log files to check")
    ap.add_argument("--dir", type=Path, help="check a whole log directory")
    ap.add_argument("--since", default=None,
                    help="with --dir: only logs dated YYYYMMDD or later")
    ap.add_argument("--staged", action="store_true",
                    help="check staged log files (what the pre-commit hook runs)")
    args = ap.parse_args()

    files: list[Path] = list(args.paths)
    if args.staged:
        files += _staged_logs()
    if args.dir:
        for p in sorted(args.dir.glob("*.md")):
            if p.name in _NOT_LOGS:       # the style guide is not an instance of itself
                continue
            if args.since:
                m = _FNAME.match(p.name)
                if not m or m.group("date") < args.since:
                    continue
            files.append(p)

    files = [f for f in dict.fromkeys(files)]          # de-dupe, keep order
    if not files:
        print("no log files to check")
        return 0

    findings: list[Finding] = []
    for f in files:
        findings.extend(check_file(f))

    errors = [x for x in findings if x.level == "error"]
    warns = [x for x in findings if x.level == "warn"]

    print(f"log conformance — {len(files)} file(s) checked")
    for x in findings:
        print(x)
    if not findings:
        print("\n✔ all logs conform to the `log` skill contract")
        return 0
    print(f"\n{len(errors)} error(s), {len(warns)} warning(s)")
    if errors:
        print("Fix per .claude/skills/log/SKILL.md — and RE-READ it rather than "
              "recalling it; it changes.")
    return 2 if errors else 1


if __name__ == "__main__":
    sys.exit(main())
