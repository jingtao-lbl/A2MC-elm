#!/usr/bin/env python
"""Who SETS and who READS an A2MC_* configuration variable — the repo's own config graph.

A2MC has a GraphRAG over the MODEL's source (FATES + ELM, `rag/graphs/api-*.json`) and nothing at
all over its own configuration surface. So A2MC can traverse FATES's call graph to tell you what
`fates_allom_l2fr` touches, but has no way to answer "who sets `A2MC_N_SAMPLES`, and who reads it?"

That asymmetry cost real time on main on 2026-08-22, adopting adapter-kit's v2.269. The sobol
ensemble size was hardcoded as `N(2P+2)` in `a2mc_config.sh` AND in `tools/config.py`, while
`create_parameter_sample.py` honoured a `--no-second-order` flag that no config anywhere set — so
a first-order design would be sized ~2x too large by two surfaces and correctly by a third, with
nothing to signal the disagreement. Finding the second surface took a hand grep that this tool
answers in one query.

The failure mode it targets is specific. A variable's MEANING lives in its READERS, not in its
declaration or its name — `A2MC_N_SAMPLES` reads as "the number of samples", the machine config
declares it with a default of 1000, and neither tells you it feeds sobol AND lhs while morris
ignores it entirely. Searching where a symptom appears (a config file) answers a different question
from the one that matters (what consumes this, and how).

    python tools/config_graph.py --var A2MC_N_SAMPLES     # one variable, fully
    python tools/config_graph.py --orphans                # read but never set, and vice versa
    python tools/config_graph.py --like N_SAMPLES         # candidate duplicate names

KNOWN LIMIT — stated so this is not over-trusted as a completeness check. It stops at the
environment-variable boundary. It will show three READS of `A2MC_SOBOL_SECOND_ORDER` (shell,
`tools/config.py`, the sampler) but NOT that those three must agree on a *formula*; and it shows
`tools/config.py` reading a variable, not that `Config.N_SAMPLES` then flows on to `orchestrator.py`
and the samplers. It finds orphans and duplicate names; it does not verify consistency.

Enumeration is `git ls-files` (index-based), never a filesystem walk — a hard requirement on this
machine's shared filesystems.

Author: Jing Tao with Claude
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

VAR = re.compile(r"\bA2MC_[A-Z0-9_]+\b")

#: A write. `export FOO=`, `FOO=`, or a shell default `FOO=${FOO:-x}`.
SET_SH = re.compile(r"^\s*(?:export\s+)?(A2MC_[A-Z0-9_]+)\s*=")
#: A read in shell: $FOO or ${FOO...}
READ_SH = re.compile(r"\$\{?(A2MC_[A-Z0-9_]+)")
#: A read in Python: os.environ.get("FOO"...) / os.environ["FOO"] / getenv("FOO"), and the repo's
#: OWN wrapper helpers — `_env("FOO", ...)` and `_required_env("FOO", ...)`.
#:
#: THE UNDER-DETECTION THIS FIXES. Without the wrapper alternatives this tool reports every variable
#: read only through one of them as "SET but never READ — dead, or read by something outside the
#: repo". **Under-detection is the worst failure mode for a config graph**, because the whole point
#: is to answer "what consumes this"; a confident "nothing" is worse than no answer, since it
#: invites deleting a live variable.
#:
#: main has three such wrappers — `tools/config.py::_required_env`,
#: `tools/check_calibration_rounds.py::_env`, `tools/generate_calibration_rounds.py::_env` — so the
#: first `--orphans` run here (15 set-but-never-read) was over-reporting.
#: (Adopted from adapter-kit afabce8d, widened for main's `_required_env`.)
READ_PY = re.compile(
    r"""(?:environ(?:\.get)?\s*[\(\[]|getenv\s*\(|\b_env\s*\(|\b_required_env\s*\()"""
    r"""\s*["'](A2MC_[A-Z0-9_]+)["']""")
#: A write in Python: os.environ["FOO"] = / os.environ.setdefault("FOO"
SET_PY = re.compile(r"""environ(?:\[["'](A2MC_[A-Z0-9_]+)["']\]\s*=|\.setdefault\(\s*["'](A2MC_[A-Z0-9_]+)["'])""")

#: Files that RECORD rather than DEFINE. A dev log quoting a variable is not a consumer, and
#: counting it as one is how a grep-based answer drowns in its own history. Kept separate rather
#: than dropped: on main a well-travelled variable has more mentions under memory/ than in code.
RECORD_PREFIXES = ("memory/", "docs/", ".claude_memory/", "use_cases/")
RECORD_SUFFIXES = (".md", ".json", ".txt", ".yaml", ".yml", ".csv")


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, timeout=60)
    return [f for f in out.stdout.splitlines() if f]


def is_record(path: str) -> bool:
    """Documentation/state, not code.

    The `/config/` carve-out matters on main: `use_cases/{site}/config/{site}_config.sh` is a real
    setter (the site config layer), while a `.sh` elsewhere under use_cases/ is a per-experiment
    script that merely consumes.
    """
    if path.endswith((".py", ".sh")):
        return path.startswith("use_cases/") and "/config/" not in path
    return path.endswith(RECORD_SUFFIXES) or path.startswith(RECORD_PREFIXES)


def scan(files: list[str]):
    """-> {var: {"set": [(path,line,text)], "read": [...], "record": [...]}}"""
    g: dict[str, dict[str, list]] = defaultdict(lambda: {"set": [], "read": [], "record": []})
    for rel in files:
        p = REPO / rel
        try:
            text = p.read_text(errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue
        if "A2MC_" not in text:
            continue
        record = is_record(rel)
        py = rel.endswith(".py")
        for i, line in enumerate(text.splitlines(), 1):
            if "A2MC_" not in line:
                continue
            hit = (line.strip()[:150])
            if record:
                for v in set(VAR.findall(line)):
                    g[v]["record"].append((rel, i, hit))
                continue
            sets = set()
            if py:
                for m in SET_PY.finditer(line):
                    sets.add(m.group(1) or m.group(2))
                reads = set(READ_PY.findall(line))
            else:
                m = SET_SH.match(line)
                if m:
                    sets.add(m.group(1))
                reads = set(READ_SH.findall(line))
            for v in sets:
                g[v]["set"].append((rel, i, hit))
            # A shell default `FOO=${FOO:-x}` both sets and reads FOO; the set is what matters.
            for v in reads - sets:
                g[v]["read"].append((rel, i, hit))
    return g


def show_var(g, var: str, quiet: bool = False) -> int:
    e = g.get(var)
    if not e:
        print(f"✘ {var}: no occurrence anywhere in tracked files", file=sys.stderr)
        return 1
    print(f"=== {var}")
    for kind, label in (("set", "SET BY"), ("read", "READ BY")):
        rows = e[kind]
        print(f"  {label} ({len(rows)}):" if rows else f"  {label}: (none)")
        for rel, i, hit in rows:
            print(f"    {rel}:{i}")
            if not quiet:
                print(f"        {hit}")
    if e["record"] and not quiet:
        print(f"  mentioned in {len(e['record'])} record file(s) (logs/docs/state) — not consumers")
    # The two shapes worth flagging without being asked.
    if e["read"] and not e["set"]:
        print("  ⚠ READ but never SET in tracked files — relies on a default or the environment")
    if e["set"] and not e["read"]:
        print("  ⚠ SET but never READ — dead, or read by something outside the repo")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--var", help="show setters and readers for one variable")
    ap.add_argument("--like", help="variables whose name contains this substring (duplicate hunt)")
    ap.add_argument("--orphans", action="store_true",
                    help="variables read-but-never-set or set-but-never-read")
    ap.add_argument("--quiet", action="store_true", help="paths only, no source lines")
    a = ap.parse_args()

    g = scan(tracked_files())

    if a.var:
        return show_var(g, a.var, a.quiet)

    if a.like:
        names = sorted(v for v in g if a.like.upper() in v)
        if not names:
            print(f"no variable name contains {a.like!r}", file=sys.stderr)
            return 1
        print(f"=== {len(names)} variable(s) whose name contains {a.like!r}")
        print("    (two names for ONE quantity is the shape to look for: a lopsided cluster)")
        for v in names:
            print(f"  {v:34s} set:{len(g[v]['set']):2d}  read:{len(g[v]['read']):2d}")
        return 0

    if a.orphans:
        unset = sorted(v for v, e in g.items() if e["read"] and not e["set"])
        unread = sorted(v for v, e in g.items() if e["set"] and not e["read"])
        print(f"=== READ but never SET ({len(unset)}) — each relies on a default")
        for v in unset:
            print(f"  {v:34s} read in {len(g[v]['read'])} place(s)")
        print(f"\n=== SET but never READ ({len(unread)}) — dead, or consumed outside the repo")
        for v in unread:
            print(f"  {v:34s} set in {len(g[v]['set'])} place(s)")
        return 0

    print(f"{len(g)} A2MC_* variables in tracked files. Use --var / --like / --orphans.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
