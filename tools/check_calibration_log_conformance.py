#!/usr/bin/env python3
"""check_calibration_log_conformance.py — assert a CALIBRATION log matches the `calibration-log`
skill's contract.

The sibling `check_log_conformance.py` governs the DEVELOPMENT streams (`memory/dev_logs*/`,
`memory/ana_logs/`) and its contract does not fit here: a calibration log has no
`Version`/`Branch` header and no `Summary`/`Files Changed`/`Verification` sections. Pointing the
dev checker at a calibration log fails it for sections it was never meant to have; pointing THIS
tool at a dev log is worse — it returns a near-clean pass against the wrong contract (see
`wrong_stream()` below), which nobody re-examines. Neither tool refuses the other's stream on its
own, so both carry an explicit guard.

The `calibration-log` skill defines TWO types and this tool checks both:

  TYPE A — PHASE LOG (`PhaseLogger`-generated; stem carries `_phase{N}_`)
      Each phase has its own purpose in reaching the calibration goal, so each has its OWN
      required sections. Those live in `PhaseLogger._EXPECTED_SECTIONS` and are READ FROM THERE
      (via `ast`, below) rather than copied — a second copy of a contract is exactly how
      `check_log_conformance.py`'s own required-section list and the `log` skill's spec drifted
      from each other before the 2026-08-14 reconciliation (`memory/dev_logs/20260814e_*`).

  TYPE B — FREE-FORM SESSION LOG (exploratory work that does not map to a phase)
      Lighter: header + the shared "record what you CONSULTED" block + cross-references.

WHAT THIS DOES NOT DO. `check_offline_log_evidence.py` already covers the EVIDENCE dimension for
analysis phases (first-hand artifact vs restatement, confidence-without-a-test, orphan numbers,
a figure missing its caption/script). This tool is STRUCTURE only; the two are complementary and
neither subsumes the other. Run both.

Non-retroactive by construction, like its sibling: a rule is applied only to logs dated on or
after the day it entered the skill, and the boundary day is a WARNING (a date cannot express when
a rule reached this branch).

Exit: 0 clean · 1 warnings only · 2 any error.

Usage:
    python3 tools/check_calibration_log_conformance.py <log.md | logs_dir | --site use_cases/<site>>

Author: Jing Tao with Claude.
"""
import ast
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# The day the `calibration-log` skill added "Skills and memory invoked" to BOTH log types
# (its changelog: "2026-08-01: Added 'Skills and memory invoked' (both log types)").
CAPABILITY_SECTION_SINCE = "20260801"

# The day `PhaseLogger._EXPECTED_SECTIONS` entered the generator (v2.215, "offline phase logs
# carry the reasoning chain", `26a51f91`). Logs written before it had no per-phase section
# contract to meet. Measured before setting this — see the module's own dev log for the number.
PHASE_SECTIONS_SINCE = "20260801"

# TYPE A ---------------------------------------------------------------------------------------
# `PhaseLogger` offline stem: YYYYMMDDx_phase{N}_{name}_r{RR}[_c{EE}[_iter{II}]]_{descriptor}
_PHASE_STEM = re.compile(
    r"^(?P<date>\d{8})(?P<letter>z*[a-z])_phase(?P<phase>[0-7])_(?P<name>[a-z0-9]+)"
    r"_r(?P<round>\d{2})(?:_c(?P<cycle>\d{2}))?(?:_iter(?P<iter>\d{2}))?_(?P<desc>.+)\.md$")
# Header fields PhaseLogger always emits.
_PHASE_HEADER = ["Site", "Phase", "Round", "Date"]
_PHASE_ALWAYS = ["Iteration Context"]
# The offline trailer's placeholder for an unfilled handshake field.
_HANDSHAKE_MISS = "_(not provided"

# TYPE B ---------------------------------------------------------------------------------------
_FREE_STEM = re.compile(r"^(?P<date>\d{8})(?P<letter>z*[a-z])_(?P<topic>.+)\.md$")
_FREE_HEADER_REQUIRED = ["Date", "Author"]
_FREE_HEADER_EXPECTED = ["Site", "Type"]
_FREE_SECTIONS = ["Cross-references"]

_NOT_LOGS = {"CLAUDE.md", "README.md", "MEMORY.md", "index.md"}


# ------------------------------------------------------------------------------------------
# Read the per-phase contract from phase_logger.py WITHOUT importing it.
# ------------------------------------------------------------------------------------------
def _str_const(node):
    """A string literal, across AST vintages. Python 3.8 replaced `ast.Str` with `ast.Constant`;
    the pre-commit hook falls back to bare python3, which may be pre-3.8 on some machines, so
    supporting only `Constant` would make the parser return {} there — and a silently-empty
    contract means the per-phase check quietly does nothing on exactly the interpreter the hook
    may pick."""
    if isinstance(node, getattr(ast, "Constant", ())) and isinstance(node.value, str):
        return node.value
    if isinstance(node, getattr(ast, "Str", ())):          # <3.8
        return node.s
    raise ValueError("not a string literal")


def _int_const(node):
    if isinstance(node, getattr(ast, "Constant", ())) and isinstance(node.value, int):
        return node.value
    if isinstance(node, getattr(ast, "Num", ())):          # <3.8
        return node.n
    raise ValueError("not an int literal")


def load_expected_sections():
    """Parse `PhaseLogger._EXPECTED_SECTIONS` out of the source.

    Deliberately `ast`, not `import`: this checker must stay stdlib-only and runnable under the
    pre-commit hook's interpreter, and `tools/phase_logger.py` needs `dataclasses` and other
    imports that may not resolve under a bare system `python3`. Parsing keeps ONE source of truth
    for the per-phase contract while adding no runtime dependency — the alternative, a second
    hardcoded copy, is exactly the drift class `check_log_conformance.py` was bitten by.

    Returns {phase:int -> [section, ...]}, or {} if the constant cannot be found (in which case
    the per-phase check is skipped rather than silently passing everything — see C4).
    """
    src = (REPO / "tools" / "phase_logger.py")
    if not src.is_file():
        return {}
    try:
        tree = ast.parse(src.read_text(errors="replace"))
    except SyntaxError:
        return {}

    consts = {}

    def value(node):
        """Evaluate list literals, names bound to lists, and `+` between them."""
        if isinstance(node, ast.List):
            out = []
            for e in node.elts:
                out.append(_str_const(e))
            return out
        if isinstance(node, ast.Name):
            return list(consts[node.id])
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return value(node.left) + value(node.right)
        raise ValueError("unsupported node")

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        tgt = node.targets[0]
        if not isinstance(tgt, ast.Name):
            continue
        if tgt.id == "_RUN_SPINE":
            try:
                consts["_RUN_SPINE"] = value(node.value)
            except Exception:
                pass
        elif tgt.id == "_EXPECTED_SECTIONS" and isinstance(node.value, ast.Dict):
            out = {}
            for k, v in zip(node.value.keys, node.value.values):
                try:
                    out[_int_const(k)] = value(v)
                except Exception:
                    return {}
            return out
    return {}


class Finding:
    __slots__ = ("path", "code", "level", "msg")

    def __init__(self, path, code, level, msg):
        self.path, self.code, self.level, self.msg = path, code, level, msg

    def __str__(self):
        tag = "ERROR" if self.level == "error" else "warn "
        return "  %s [%s] %s: %s" % (tag, self.code, self.path.name, self.msg)


def _headers(text):
    return set(re.findall(r"^\*\*([A-Za-z ]+):\*\*", text, re.M))


def _sections(text):
    """`## Foo` headings. PhaseLogger appends free text to some headings ('## Next Action: ...'),
    so the leading token before ':' is kept as well — otherwise every such section reads absent."""
    out = set()
    for ln in text.splitlines():
        if ln.startswith("## "):
            h = ln[3:].strip()
            out.add(h)
            if ":" in h:
                out.add(h.split(":", 1)[0].strip())
    return out


def wrong_stream(path):
    """Is this path unambiguously in a stream this tool does NOT govern?

    Fires only on a POSITIVE match for another stream, never on an ambiguous path, so a log in a
    scratch/tmp directory (tests, a draft) is still checkable. Without this guard the two
    checkers can silently mis-serve each other: pointing THIS tool at a dev log returns a
    near-clean pass ("0 errors, 1 warning") against the wrong contract — more dangerous than a
    false failure, since nobody re-examines a pass.
    """
    parts = path.parts
    if any(p.startswith("dev_logs") or p == "ana_logs" for p in parts):
        return ("a DEVELOPMENT log (memory/dev_logs*/ or memory/ana_logs/) — use "
                "`tools/check_log_conformance.py`, whose contract is different "
                "(Summary/Problem/Solution/Files Changed/Verification + Version/Branch header)")
    if "model_logs" in parts:
        return ("a MODEL-DEV log (memory/model_logs/) — that stream has its own header shape and "
                "is held by review, not by a checker (see memory/model_logs/CLAUDE.md)")
    return None


def check_file(path, expected_sections=None):
    out = []
    if not path.is_file():
        return [Finding(path, "C0", "error", "file not found")]
    if path.name in _NOT_LOGS:
        return []
    other = wrong_stream(path)
    if other:
        return [Finding(path, "C00", "error", "wrong tool: this is %s" % other)]
    text = path.read_text(errors="replace")
    secs, hdrs = _sections(text), _headers(text)
    is_phase = "_phase" in path.name and _PHASE_STEM.match(path.name)

    if is_phase:
        out += _check_phase(path, text, secs, hdrs, expected_sections)
    else:
        out += _check_free(path, text, secs, hdrs)

    # Shared: the "record what you CONSULTED" block, both types, non-retroactive.
    m = _PHASE_STEM.match(path.name) or _FREE_STEM.match(path.name)
    date = m.group("date") if m else None
    if date and date >= CAPABILITY_SECTION_SINCE and "Skills and memory invoked" not in secs:
        boundary = date == CAPABILITY_SECTION_SINCE
        out.append(Finding(
            path, "C8", "warn" if boundary else "error",
            "missing '## Skills and memory invoked' — required for BOTH log types since "
            "%s ('None' is a valid answer)" % CAPABILITY_SECTION_SINCE
            + (" (boundary day, so it may predate the rule reaching this branch)"
               if boundary else "")))
    return out


def _check_phase(path, text, secs, hdrs, expected_sections):
    out = []
    m = _PHASE_STEM.match(path.name)

    for f in _PHASE_HEADER:
        if f not in hdrs:
            out.append(Finding(path, "C2", "error", "header missing '**%s:**'" % f))

    # The filename's phase number must agree with the header — a mismatch means the log was
    # written by one phase method and renamed, or hand-edited, and every downstream tool that
    # keys off the stem (workflow_state, the reasoning chain) will disagree with the body.
    hm = re.search(r"^\*\*Phase:\*\*\s*(\d)", text, re.M)
    if hm and hm.group(1) != m.group("phase"):
        out.append(Finding(path, "C3", "error",
                           "filename says phase %s but header says phase %s"
                           % (m.group("phase"), hm.group(1))))

    for s in _PHASE_ALWAYS:
        if s not in secs:
            out.append(Finding(path, "C5", "error", "missing '## %s'" % s))

    # C4 — the phase's OWN required sections. Each phase exists to move the calibration toward
    # the goal in a specific way, so its section list is its contract, not decoration.
    phase = int(m.group("phase"))
    if expected_sections is None:
        expected_sections = load_expected_sections()
    date = m.group("date")
    if not expected_sections:
        out.append(Finding(path, "C4", "warn",
                           "could not read PhaseLogger._EXPECTED_SECTIONS — per-phase section "
                           "check SKIPPED (fix the parser rather than trusting this pass)"))
    elif date >= PHASE_SECTIONS_SINCE:
        # Sections the GENERATOR already named as absent are C7's business, not C4's. Reporting
        # both would double-count the same gap and bury the ones nobody has acknowledged.
        declared = set()
        blk = re.search(r"^## Sections not provided\s*$(.*?)(?=^## |\Z)", text, re.S | re.M)
        if blk:
            declared = {ln[2:].split("—")[0].split(" - ")[0].strip()
                        for ln in blk.group(1).splitlines() if ln.startswith("- ")}
        boundary = date == PHASE_SECTIONS_SINCE
        for s in expected_sections.get(phase, []):
            if s in secs or s in declared:
                continue
            out.append(Finding(
                path, "C4", "warn" if boundary else "error",
                "phase %d log missing '## %s' — this phase's own contract "
                "(PhaseLogger._EXPECTED_SECTIONS); required for logs dated after %s"
                % (phase, s, PHASE_SECTIONS_SINCE)))

    # C6 — the offline handshake must be FILLED, not left as the generated placeholder. An
    # unfilled field is worse than an absent one: it looks like a chain and resolves to nothing.
    if "Phase Handshake" in secs:
        blk = re.search(r"^## Phase Handshake\s*$(.*?)(?=^## |\Z)", text, re.S | re.M)
        if blk:
            for label in ("Inherited from the previous phase", "Handed to the next phase",
                          "Next action"):
                fm = re.search(r"\*\*%s:\*\*\s*(.*)" % re.escape(label), blk.group(1))
                if fm and _HANDSHAKE_MISS in fm.group(1):
                    out.append(Finding(path, "C6", "error",
                                       "Phase Handshake '%s' left as the generated placeholder"
                                       % label))

    # C7 — PhaseLogger names the sections it emitted empty. That list is a to-do the writer left
    # behind, not a state to ship: it is the generator telling you the log is incomplete.
    if "Sections not provided" in secs:
        blk = re.search(r"^## Sections not provided\s*$(.*?)(?=^## |\Z)", text, re.S | re.M)
        n = len(re.findall(r"^- ", blk.group(1), re.M)) if blk else 0
        out.append(Finding(path, "C7", "warn",
                           "PhaseLogger flagged %d section(s) as not provided — fill them or "
                           "state why they do not apply" % n))
    return out


def _check_free(path, text, secs, hdrs):
    out = []
    if not _FREE_STEM.match(path.name):
        out.append(Finding(path, "C1", "error",
                           "filename is not YYYYMMDDx_Topic.md (x = same-day letter; past z use "
                           "za, zb — never aa, it sorts before b)"))
    for f in _FREE_HEADER_REQUIRED:
        if f not in hdrs:
            out.append(Finding(path, "C2", "error", "header missing '**%s:**'" % f))
    for f in _FREE_HEADER_EXPECTED:
        if f not in hdrs:
            out.append(Finding(path, "C2", "warn",
                               "header missing '**%s:**' (expected for a calibration session log; "
                               "omit only if genuinely not applicable)" % f))
    for s in _FREE_SECTIONS:
        if s not in secs:
            out.append(Finding(path, "C9", "error", "missing '## %s'" % s))
    if "Next" not in secs:
        out.append(Finding(path, "C10", "warn",
                           "no '## Next' — say what this leaves open, even if 'nothing'"))
    return out


def _staged():
    """Calibration logs staged in THIS commit.

    Staged-only on purpose, mirroring the sibling: the gate covers what you are writing now and
    never blocks a commit over pre-existing drift in logs you did not touch.
    """
    import subprocess
    try:
        out = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            cwd=str(REPO)).decode("utf-8", "replace")
    except Exception:
        return []
    keep = []
    for line in out.splitlines():
        p = Path(line.strip())
        if not line.strip() or p.suffix != ".md":
            continue
        parts = p.parts
        if "use_cases" in parts and "logs" in parts and "memory" in parts:
            keep.append(REPO / p)
    return [p for p in keep if p.is_file()]


def _collect(args):
    if args == ["--staged"]:
        return _staged()
    paths = []
    it = iter(args)
    for a in it:
        if a == "--site":
            site = Path(next(it, ""))
            d = site / "memory" / "logs"
            paths += sorted(p for p in d.glob("*.md")) if d.is_dir() else []
        else:
            p = Path(a)
            paths += sorted(p.glob("*.md")) if p.is_dir() else [p]
    return [p for p in paths if p.name not in _NOT_LOGS]


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__.strip().splitlines()[-3])
        return 2
    paths = _collect(args)
    if not paths:
        print("no calibration logs found in: %s" % " ".join(args))
        return 0

    expected = load_expected_sections()
    findings = []
    for p in paths:
        findings += check_file(p, expected)

    print("calibration-log conformance — %d file(s) checked" % len(paths))
    if not findings:
        print("\n\u2714 all logs conform to the `calibration-log` skill contract")
        return 0
    errs = [f for f in findings if f.level == "error"]
    for f in findings:
        print(f)
    print("\n%d error(s), %d warning(s)" % (len(errs), len(findings) - len(errs)))
    print("Fix per .claude/skills/calibration-log/SKILL.md — and RE-READ it rather than "
          "recalling it; it changes.")
    return 2 if errs else 1


if __name__ == "__main__":
    sys.exit(main())
