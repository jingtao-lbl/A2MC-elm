#!/usr/bin/env python
"""Validate the `affects` variable names in curated knowledge against the MODEL's own registry.

Every discovery in `gained_knowledge/discoveries.json` carries an `affects` list, and
`MemoryManager._find_relevant_discoveries()` matches a phase's failing targets against it. A name
that no longer exists -- or never did -- cannot match, so the entry is silently invisible to
retrieval. Nothing failed, nothing warned; the knowledge was simply never surfaced. That is the
defect this checker exists to make loud.

WHAT COUNTS AS VALID -- and why the obvious check is the wrong one
------------------------------------------------------------------
The tempting reference set is "the variables in one of our history files". It is WRONG, and it
produces false alarms at scale: measured 2026-08-25, checking against a single `h0` reported 11
broken entries when exactly ONE was genuinely invalid. Two reasons:

  1. A name can be a real model variable that is simply `use_default='inactive'` -- absent from our
     output but perfectly valid to name, and it would match the moment the variable is enabled.
  2. Retrieval matches STRINGS, not the contents of any particular NetCDF file. What the model can
     emit is the contract; what one run happened to write is not.

So validity is judged against what the model REGISTERS:

  * FATES  -- `vname='X'` in `main/FatesHistoryInterfaceMod.F90`.
  * ELM    -- `fname='X'` in any `hist_addfld*` call under `components/elm/src`.

Two traps in gathering those, both hit while writing this:

  * FATES is a **git submodule**, so a plain `git grep` from the E3SM root silently returns ZERO
    matches rather than erroring. `--recurse-submodules` is required
    (see auto-memory `feedback_nersc_no_recursive_traversal`).
  * Vertically-resolved names are built at runtime as `fname='SOLUTIONP'//trim(vr_suffix)`, so
    `SOLUTIONP_vr` never appears as a literal. Every ELM base name therefore also admits its
    `_vr` form.

Usage
-----
    python tools/validate_knowledge_affects.py                    # site + generic KB
    python tools/validate_knowledge_affects.py --kb <file.json>   # one file
    python tools/validate_knowledge_affects.py --list-valid       # dump the accepted name set

    python tools/validate_knowledge_affects.py --staged        # pre-commit gate

Exit: 0 clean, 1 invalid names found, 2 setup error (model path unreadable) -- the gate
SKIPS on 2 rather than blocking a commit over an unsourced config.

Author: Jing Tao with Claude on Perlmutter
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

FATES_HIST = "*FatesHistoryInterfaceMod.F90"
ELM_SRC = "components/elm/src"
_META = {"version", "site", "description", "_affects_convention", "discoveries"}


def _git_grep(repo: Path, pattern: str, pathspec: str, recurse: bool) -> set[str]:
    """Names captured by `pattern` via git grep. Index-based, never a filesystem walk."""
    cmd = ["git", "grep", "-ohE"]
    if recurse:
        cmd.append("--recurse-submodules")
    cmd += [pattern, "--", pathspec]
    try:
        out = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"git grep failed in {repo}: {exc}") from exc
    if out.returncode not in (0, 1):          # 1 = no matches, which is a real answer
        raise RuntimeError(f"git grep returned {out.returncode} in {repo}: {out.stderr[:200]}")
    return {m.group(1) for m in re.finditer(r"'([A-Za-z0-9_]+)'", out.stdout)}


def registered_names(model_root: Path) -> tuple[set[str], dict[str, int]]:
    """The set of history-variable names this model can emit, plus per-source counts."""
    fates = _git_grep(model_root, r"vname='[A-Za-z0-9_]+'", FATES_HIST, recurse=True)
    elm = _git_grep(model_root, r"fname='[A-Za-z0-9_]+'", f"{ELM_SRC}/**/*.F90", recurse=False)
    # `fname='X'//trim(vr_suffix)` is assembled at runtime -- admit the _vr form of every ELM name.
    elm_vr = {f"{n}_vr" for n in elm}
    if not fates:
        # A silent empty FATES set is the submodule trap, not a model without history variables.
        raise RuntimeError(
            "no FATES vnames found -- FATES is a submodule and git grep needs --recurse-submodules; "
            "an empty set here would pass every entry vacuously, so this is fatal rather than a warning")
    return fates | elm | elm_vr, {"fates": len(fates), "elm": len(elm), "elm_vr": len(elm_vr)}


def resolve_model_path() -> "Path | None":
    """A2MC_MODEL_PATH from the environment, else by SOURCING a2mc_config.sh in a subshell.

    The env var is only set once someone has sourced the config, which a bare `git commit` has
    not. Relying on it alone made the pre-commit gate skip silently in the ordinary case -- a
    check that cannot fail. Sourcing the repo's own config is what a human would do, and it keeps
    one source of truth rather than re-deriving the path with a regex.
    """
    env = os.environ.get("A2MC_MODEL_PATH")
    if env:
        return Path(env)
    root = Path(__file__).resolve().parent.parent
    cfg = root / "a2mc_config.sh"
    if not cfg.is_file():
        return None
    out = subprocess.run(
        ["bash", "-c", f'set -a; source "{cfg}" >/dev/null 2>&1; printf "%s" "${{A2MC_MODEL_PATH:-}}"'],
        capture_output=True, text=True, cwd=root, timeout=60)
    val = out.stdout.strip()
    return Path(val) if val else None


def staged_kbs() -> "list[Path]":
    """Staged discoveries.json paths, or [] if none. Used by the pre-commit gate."""
    out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
                         capture_output=True, text=True)
    return [Path(p) for p in out.stdout.split()
            if p.endswith("gained_knowledge/discoveries.json")]


def _staged_blob(path: Path) -> str:
    """The STAGED content of `path` -- what is actually being committed, which is not necessarily
    what is in the working tree. Validating the file on disk would let a broken staged version
    through in exactly the case a gate is for."""
    out = subprocess.run(["git", "show", f":{path}"], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"cannot read staged blob for {path}")
    return out.stdout


def kb_entries_from(payload: str):
    """(key, affects) for every discovery entry, tolerating both container shapes."""
    data = json.loads(payload)
    if isinstance(data, dict):
        listed = data.get("discoveries")
        if isinstance(listed, list) and listed:
            for e in listed:
                if isinstance(e, dict) and "affects" in e:
                    yield e.get("name", "<unnamed>"), e["affects"]
        for k, v in data.items():
            if k not in _META and isinstance(v, dict) and "affects" in v:
                yield k, v["affects"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kb", action="append", type=Path, help="KB json (repeatable; default: site + generic)")
    ap.add_argument("--model-path", type=Path, default=None)
    ap.add_argument("--list-valid", action="store_true", help="print the accepted name set and exit")
    ap.add_argument("--staged", action="store_true",
                    help="validate the STAGED content of any staged discoveries.json; exit 0 if none")
    args = ap.parse_args()

    if args.staged and not staged_kbs():
        return 0                                   # nothing to gate

    model_root = args.model_path or resolve_model_path()
    if not model_root:
        # Genuinely unresolvable. Exit 2 is a SETUP error, distinct from exit 1 (a real finding);
        # the pre-commit gate skips on 2 rather than blocking a commit on a setup condition.
        print("ERROR: could not resolve A2MC_MODEL_PATH — not in the environment and not obtainable "
              "by sourcing a2mc_config.sh", file=sys.stderr)
        return 2
    if not (model_root / ".git").exists():
        print(f"ERROR: {model_root} is not a git checkout", file=sys.stderr)
        return 2
    try:
        valid, counts = registered_names(model_root)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.list_valid:
        for n in sorted(valid):
            print(n)
        return 0

    if args.staged:
        kbs = staged_kbs()
    else:
        kbs = args.kb
        if not kbs:
            ucd = os.environ.get("A2MC_USE_CASE_DIR", "")
            kbs = [p for p in (Path(ucd) / "memory/gained_knowledge/discoveries.json" if ucd else None,
                               Path("memory/gained_knowledge/discoveries.json")) if p and p.is_file()]
        if not kbs:
            print("ERROR: no knowledge base found (set A2MC_USE_CASE_DIR or pass --kb)", file=sys.stderr)
            return 2

    print(f"knowledge `affects` validation ({'staged' if args.staged else 'working tree'}) — model registers "
          f"{counts['fates']} FATES + {counts['elm']} ELM names ({len(valid)} accepted incl. _vr forms)")
    bad, checked = [], 0
    for kb in kbs:
        try:
            payload = _staged_blob(kb) if args.staged else kb.read_text()
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        for key, affects in kb_entries_from(payload):
            checked += 1
            missing = [a for a in affects if a not in valid]
            if missing:
                bad.append((kb, key, missing))
    for kb, key, missing in bad:
        print(f"  ✘ {kb.name}: {key}")
        print(f"      not registered by the model: {', '.join(missing)}")
        print(f"      -> this entry can never match a target; retrieval passes it over silently")
    if bad:
        print(f"\n✘ {len(bad)} of {checked} entries name a variable the model does not register.")
        print("  Fix the name (see the KB's own `_affects_convention`) — do NOT delete the entry.")
        return 1
    print(f"\n✔ all {checked} entries' affects resolve against the model's history registry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
