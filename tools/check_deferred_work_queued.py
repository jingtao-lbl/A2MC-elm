#!/usr/bin/env python3
"""A log that DEFERS work must route that work into TODO.md, the queue that is actually read.

THE FAILURE THIS EXISTS FOR. On 2026-08-22 the PI asked why a known gap had not been fixed. It had
been *documented*: the log that introduced `check_skill_claims.py` carried a section headed "What
this does NOT fix" naming precisely the hole the PI then had to point out. I had identified it,
written it down, and stopped -- treating documentation as discharge.

That is structural, not a lapse of attention. A dev log is APPEND-ONLY and nobody re-reads it;
`TODO.md` is the forward-looking checklist the root CLAUDE.md says to read at session start and
update at every step transition. Nothing routed between them. Measured at the time this check was
written: TODO.md was 318 lines with **zero** references to any log from 2026-08-21 or 2026-08-22,
the two days that produced the most deferred items.

So: if a log's `## Next` section names real work, TODO.md must reference that log. The link is
decidable -- a stem is a string -- which is what makes this a check rather than a good intention.

    python3 tools/check_deferred_work_queued.py <log.md> [...]
    python3 tools/check_deferred_work_queued.py --staged

EXIT 0 clean / 1 WARN. Deliberately a WARN: whether a deferred item is worth queueing is a
judgement, and gating a commit on a judgement is how gates get bypassed wholesale. What it removes
is the ability to defer SILENTLY.

Author: Jing Tao with Claude
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TODO = REPO / "TODO.md"

#: Sections where deferred work hides. "Next" is the conventional one; the others appear whenever a
#: log is honest about its own limits, which is exactly when the item is most likely to be lost.
DEFER_HEADS = re.compile(
    r"^##+\s*(Next|What (?:this|it) does NOT fix|What is (?:still )?NOT fixed|"
    r"Not fixed|Deferred|Open questions?|Still open)\b.*$",
    re.M | re.I)

#: Phrases that mean "there is nothing to queue". A log allowed to say this honestly is what keeps
#: the check from manufacturing busywork on every commit.
NOTHING = re.compile(
    r"nothing outstanding|nothing to queue|no follow[- ]up|nothing deferred|"
    r"nothing further|none outstanding|nothing here", re.I)

STEM = re.compile(r"^(\d{8}[a-z]+_[A-Za-z0-9_]+)")



def _short_is_unambiguous(short: str) -> bool:
    """True when this date+letter prefix identifies exactly ONE log across every stream.

    Enumerated with `git ls-files` (index-based, never a filesystem walk -- a hard requirement on a
    shared filesystem). Falls back to ambiguous-if-unknown: if the enumeration fails we cannot prove
    uniqueness, and a check that cannot prove its premise must not pass on it.
    """
    # --cached --others --exclude-standard: a log written THIS session is not yet tracked, and a
    # tracked-only enumeration reported it as the unique holder of its prefix -- a false clean, in
    # the check written to prevent false cleans. [[feedback_a_gate_must_measure_the_branch_not_the_disk]]
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard",
                          "--", "memory/*logs*/*.md"],
                         cwd=REPO, capture_output=True, text=True)
    if out.returncode != 0:
        return False
    hits = {pathlib.Path(f).name for f in out.stdout.split()
            if pathlib.Path(f).name.startswith(short + "_")}
    return len(hits) == 1


def section_bodies(text: str) -> list[tuple[str, str]]:
    """-> [(heading, body)] for each deferral-ish section, body running to the next heading."""
    out, ms = [], list(DEFER_HEADS.finditer(text))
    for i, m in enumerate(ms):
        start = m.end()
        nxt = re.search(r"^##+\s", text[start:], re.M)
        end = start + (nxt.start() if nxt else len(text) - start)
        out.append((m.group(0).strip(), text[start:end].strip()))
    return out


def has_real_work(body: str) -> bool:
    """A body is 'real work' if it says something and does not say 'nothing outstanding'."""
    if not body or NOTHING.search(body):
        return False
    # Prose alone can be a closing remark; a numbered/bulleted item is a task.
    return bool(re.search(r"^\s*(?:[-*]|\d+\.)\s+\S", body, re.M))


def todo_text() -> str:
    return TODO.read_text(errors="replace") if TODO.is_file() else ""


# NOTE: git yields paths WITHOUT a leading slash ('memory/dev_logs_adapterkit/x.md'), so a
# test for '/memory/dev_logs' silently matches nothing. That made this check skip every dev
# log while reporting clean -- caught 2026-08-22 by a test that staged a real modified log.
def staged_logs() -> list[Path]:
    out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
                         cwd=REPO, capture_output=True, text=True).stdout.split()
    return [REPO / r for r in out
            if r.endswith(".md") and ("memory/dev_logs" in r or "memory/model_logs/" in r)]


def main(argv: list[str]) -> int:
    files = staged_logs() if (argv and argv[0] == "--staged") else [Path(a) for a in argv]
    files = [f for f in files if f.is_file()]
    if not files:
        return 0
    todo = todo_text()
    if not todo:
        print("  [warn] check_deferred_work_queued: TODO.md not found — cannot verify routing")
        return 1

    unrouted = []
    for f in files:
        m = STEM.match(f.name)
        stem = m.group(1) if m else f.stem
        text = f.read_text(errors="replace")
        deferring = [(h, b) for h, b in section_bodies(text) if has_real_work(b)]
        if not deferring:
            continue
        # The link: TODO.md names the log. The FULL stem always counts. The date+letter short form
        # counts too, because a TODO line often cites it -- but ONLY when it is unambiguous.
        #
        # THE FALSE CLEAN THIS FIXES. `memory/dev_logs_<branch>/` and `memory/model_logs/` keep
        # INDEPENDENT same-day letter sequences, so `20260822c` names a dev log AND a model log.
        # On 2026-08-22 a model log deferring three real items passed this check because TODO.md
        # happened to cite the dev log of the same letter. A checker reporting clean on work nobody
        # queued is the exact defect it was written to prevent, one level up.
        short = stem.split("_")[0]
        if stem in todo:
            continue
        if short in todo and _short_is_unambiguous(short):
            continue
        unrouted.append((f.name, [h for h, _ in deferring]))

    if unrouted:
        print("\n  [warn] check_deferred_work_queued: log(s) defer work that TODO.md does not carry")
        for name, heads in unrouted:
            print(f"    {name}")
            for h in heads:
                print(f"        {h}")
        print("\n    A dev log is APPEND-ONLY and nobody re-reads it; TODO.md is the queue read at")
        print("    session start. An item that lives only in a log's 'Next' or 'does NOT fix'")
        print("    section is parked, not scheduled — which is how a gap documented on 2026-08-22")
        print("    survived until the PI asked why it was still open.")
        print("    Add a TODO.md line citing the log stem, or say 'Nothing outstanding' and mean it.")
        return 1

    print("✔ check_deferred_work_queued: every deferring log is referenced from TODO.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
