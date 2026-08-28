#!/usr/bin/env python3
"""Has this been investigated before? Search a case's logs and REPORT THEIR CORRECTION STATUS.

THE FAILURE THIS EXISTS FOR. On 2026-08-22 I twice recorded a finding as new or a premise as
unverified, and both had been settled in the case's own logs. Neither failure was a missing search:

  * For the NPP-scope question my grep DID surface `20260807b` and I read it -- but its answer lived
    three logs downstream through a banner chain (asked 08-07, answered wrongly 08-08, retracted
    08-09, re-established from the source document 08-09b). A plain grep shows the first log and
    says nothing about the chain.
  * For the target-inconsistency finding the relevant log was titled with the conclusion and a plain
    keyword search on my terms did not rank it.

So a bare `git grep` is not the tool. What is needed is a search that tells you, for each hit,
whether that log has been CORRECTED, RETRACTED or SUPERSEDED, and by what -- because in this
project's logging convention the answer is very often not in the log you find first.

    python3 tools/prior_art.py <keyword> [keyword ...] [--site EcoSIM_BioCON] [--all-streams]

Ranks by hit count, prints each log's title and any correction banner it carries, and lists the
logs that cite it. EXIT 0 always: this is a research aid, not a gate.

Author: Jing Tao with Claude
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import subprocess

REPO = pathlib.Path(__file__).resolve().parent.parent

#: How this project marks a log whose conclusion has moved. Matched case-insensitively at line start
#: or after a blockquote marker, because they are written as banners near the top.
BANNER = re.compile(
    r"^\s*>?\s*#{0,4}\s*[⚠⛔★]*\s*\**\s*"
    r"(RETRACTED|PARTLY RETRACTED|CORRECTED|PARTLY CORRECTED|SUPERSEDED|WITHDRAWN|"
    r"REVISED|OBSOLETE|CENTRAL FINDING RETRACTED)\b.*$",
    re.M | re.I)

STREAMS_CASE = "use_cases/{site}/memory/logs"
STREAMS_ALL = ["memory/dev_logs*", "memory/model_logs", "memory/ana_logs"]


def enumerate_logs(site: str | None, all_streams: bool) -> list[str]:
    """git ls-files, index-based, never a filesystem walk. Includes untracked-but-present logs."""
    specs = []
    if site:
        specs.append(f"use_cases/{site}/memory/logs/*.md")
        specs.append(f"use_cases/{site}/reports/*/*.md")
    if all_streams or not site:
        specs += ["memory/*logs*/*.md"]
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", *specs],
                         cwd=REPO, capture_output=True, text=True)
    return [f for f in out.stdout.split() if f.endswith(".md")]


def title_of(text: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else fallback


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("keywords", nargs="+")
    ap.add_argument("--site", default=os.environ.get("A2MC_SITE_NAME"))
    ap.add_argument("--all-streams", action="store_true",
                    help="also search dev/model/ana logs, not just the case's phase logs")
    ap.add_argument("--top", type=int, default=8)
    a = ap.parse_args()

    files = enumerate_logs(a.site, a.all_streams)
    if not files:
        print("  no logs found. Pass --site or run from the repo root.")
        return 0
    pats = [re.compile(re.escape(k), re.I) for k in a.keywords]

    hits = []
    for rel in files:
        try:
            text = (REPO / rel).read_text(errors="replace")
        except OSError:
            continue
        n = sum(len(p.findall(text)) for p in pats)
        matched = sum(1 for p in pats if p.search(text))
        if not n:
            continue
        banners = [m.group(0).strip()[:150] for m in BANNER.finditer(text)][:3]
        hits.append((matched, n, rel, title_of(text, pathlib.Path(rel).stem), banners))

    hits.sort(key=lambda h: (-h[0], -h[1]))
    print(f"  searched {len(files)} log(s) for {a.keywords}; {len(hits)} carry at least one\n")
    for matched, n, rel, title, banners in hits[:a.top]:
        print(f"  [{matched}/{len(a.keywords)} terms, {n} hits] {pathlib.Path(rel).name}")
        print(f"      {title[:104]}")
        for b in banners:
            print(f"      ** {b}")
        if not banners:
            print(f"      (no correction banner)")
        print()

    if any(h[4] for h in hits[:a.top]):
        print("  ** AT LEAST ONE HIT CARRIES A CORRECTION BANNER. In this project's convention the")
        print("     answer is often NOT in the log you find first: follow the chain to the log that")
        print("     supersedes it before concluding anything is new, open, or unverified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
