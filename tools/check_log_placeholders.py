#!/usr/bin/env python3
"""A rendered log must not carry a PLACEHOLDER where a finding belongs.

THE FAILURE THIS EXISTS FOR. On 2026-08-22 the R3 cycle-3 diagnosis log rendered

    ## Comparative Case Analysis
    - **Best case (targets):** #N/A
    - **Lowest cost case:** #N/A
    - **Recommended starting case:** #N/A

while the diagnosis had actually supplied two fully specified base cases. `PhaseLogger` read only
the legacy scalar keys and silently dropped `selected_base_cases`, the contract `orchestrator.py`
has treated as primary since v2.80. The PI caught it by READING the file. Nothing mechanical did:
`check_offline_log_evidence.py` exited 0, the section headings were all present, and the pre-commit
gate was clean.

That is the same shape as the false skill claim one level down. An empty section is honest and
visible. A section rendering "#N/A" **converts a missing finding into an answered one** -- it reads
as "no comparison was made" rather than "the log lost your data".

WHAT IT DOES NOT DO. It cannot tell whether prose is substantive; that is not decidable. It checks
for the specific machine-emitted stubs a renderer produces when a field it wanted was absent, which
IS decidable, and which is where the silent data loss actually happens.

    python3 tools/check_log_placeholders.py <log.md> [...]
    python3 tools/check_log_placeholders.py --staged

EXIT 0 clean / 1 a placeholder was rendered where content was expected.

Author: Jing Tao with Claude
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: Machine-emitted stubs. Each is a string a RENDERER writes when a field it wanted was missing --
#: never something a human would type into a finding. Anchored to a bullet or a whole line so a
#: log that DISCUSSES the placeholder (this file's own dev log, for instance) is not flagged.
PLACEHOLDERS = [
    (re.compile(r"^\s*-\s+\*\*[^*]+:\*\*\s*#?N/A\s*$", re.M), "a bullet whose value is N/A"),
    (re.compile(r"^\s*\*No AI reasoning recorded\*\s*$", re.M), "the empty-reasoning stub"),
    (re.compile(r"^\s*-\s+\*\*[^*]+:\*\*\s*(?:None|TBD|\{\}|\[\])\s*$", re.M),
     "a bullet whose value is None/TBD/an empty container"),
    (re.compile(r"comparative_analysis was supplied but carried no recognised key", re.M),
     "comparative_analysis supplied with no key the renderer understands"),
]

#: The ONE section where a "not provided" marker is the deliberate, honest output rather than a
#: failure: PhaseLogger's own trailing list of sections the author left empty. Excluded by slicing
#: it off before scanning, not by pattern, so a stub appearing ABOVE it is still caught.
NOT_PROVIDED_HEAD = re.compile(r"^##+\s*Sections not provided\b.*$", re.M)

#: EFFECTIVE DATE — deliberately set EARLIER on main than on the branch this came from, because
#: main's situation is different and the inherited date asserted something untrue here.
#:
#: adapter-kit grandfathered everything before 20260822: it had ~20 phase-4 hypothesis logs
#: carrying "Current: N/A / Proposed: N/A" from a renderer bug, unrepairable because the dicts that
#: produced them are gone. Flagging those forever would make the check permanently red, which is
#: how a check stops being read.
#:
#: **Main has no such backlog.** Measured 2026-08-22 with this file's own PLACEHOLDERS patterns
#: across all 18 offline calibration logs: **0 placeholders in 0 logs.** So grandfathering buys
#: nothing here and the inherited "Queued in TODO.md" line would have pointed at a backlog that
#: does not exist. The date is set before main's earliest offline log (20260713) so the rule
#: applies to the WHOLE corpus — free, since all 18 already pass, and it means a placeholder
#: introduced tomorrow is caught rather than silently exempted.
#:
#: The exempt count is still printed if it is ever non-zero, so a future backlog stays a visible
#: decision rather than a disappeared one.
PLACEHOLDER_RULE_EFFECTIVE = "20260101"
STEM_DATE = re.compile(r"(\d{8})")


#: A FENCED CODE BLOCK IS QUOTED MATERIAL, NOT RENDERED OUTPUT. Found by this check firing on the
#: very log that documents it: a log explaining the defect necessarily reproduces the stub, and a
#: dev log's worked example is the most likely place for it to appear verbatim. Blanking fences
#: (rather than deleting them) preserves line numbers, so a real hit is still reported at its true
#: line. Note this is STRICTLY WIDER than the prose case the inline-backtick anchor already handles:
#: inside a fence the stub sits at the start of a line, exactly as a renderer would emit it.
FENCE = re.compile(r"^(?P<f>`{3,}|~{3,}).*?$.*?^(?P=f)\s*$", re.M | re.S)


def _blank_fences(text: str) -> str:
    return FENCE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def scannable(text: str) -> str:
    m = NOT_PROVIDED_HEAD.search(text)
    body = text[:m.start()] if m else text
    return _blank_fences(body)


def staged_logs() -> list[Path]:
    out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
                         cwd=REPO, capture_output=True, text=True).stdout.split()
    return [REPO / r for r in out
            if r.endswith(".md") and ("/memory/logs/" in r or "memory/dev_logs" in r
                                      or "memory/model_logs/" in r or "memory/ana_logs/" in r)]


def main(argv: list[str]) -> int:
    files = staged_logs() if (argv and argv[0] == "--staged") else [Path(a) for a in argv]
    files = [f for f in files if f.is_file()]
    if not files:
        return 0

    bad: list[tuple[str, list[str]]] = []
    exempt = 0
    for f in files:
        m = STEM_DATE.match(f.name)
        if m and m.group(1) < PLACEHOLDER_RULE_EFFECTIVE:
            exempt += 1
            continue
        body = scannable(f.read_text(errors="replace"))
        hits = []
        for rx, why in PLACEHOLDERS:
            for m in rx.finditer(body):
                line = body[:m.start()].count("\n") + 1
                hits.append(f"line {line}: {why} — {m.group(0).strip()[:70]}")
        if hits:
            bad.append((f.name, hits))

    if bad:
        print(f"\n✘ check_log_placeholders: {len(bad)} log(s) render a placeholder where a "
              f"finding belongs")
        for name, hits in bad:
            print(f"  - {name}")
            for h in hits[:6]:
                print(f"      {h}")
            if len(hits) > 6:
                print(f"      ... and {len(hits) - 6} more")
        print("\n  A renderer writes these when a field it wanted was ABSENT, which usually means")
        print("  the data was passed under a key the renderer does not read. Check the key names")
        print("  against the renderer before assuming the section is genuinely empty. If it IS")
        print("  genuinely empty, omit the section rather than rendering a stub: an empty section")
        print("  is honest, a stub converts a missing finding into an answered one.")
        return 1

    if exempt:
        print(f"  [note] {exempt} log(s) predate the rule ({PLACEHOLDER_RULE_EFFECTIVE}) and are "
              f"exempt: their placeholders are unrepairable (the source dicts are gone) and the "
              f"renderer that produced them is fixed. Backlog tracked in TODO.md.")
    print(f"✔ check_log_placeholders: {len(files) - exempt} log(s) checked, "
          f"no rendered placeholders")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
