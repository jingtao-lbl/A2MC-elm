#!/usr/bin/env python3
"""
check_phase_script_docs.py — verify each phases/phaseN_*/CLAUDE.md "Scripts in This
Folder" table matches the actual *.py scripts on disk.

Scripts are the source of truth; the CLAUDE.md tables are the stale side. This catches
the drift class where a script is renamed / added / extracted-from-orchestrator but its
phase CLAUDE.md table is not updated in lockstep (e.g. run_screening.py ->
screen_ensemble.py). It is the phase-doc analog of tools/check_skill_registry.py.

Two checks per phase:
  1. UNDOCUMENTED — a local *.py present on disk but absent from the Scripts table.
  2. STALE        — a *.py named in the Scripts table that is neither a local file
                    nor a tools/ script (a dead reference).

Tolerant by design (avoids the false positives that would make it noise):
  - __init__.py ignored everywhere.
  - Per-phase IGNORE globs (phase3 auto-discovers test_*.py — see root CLAUDE.md
    §"Diagnostic tools"); applied to BOTH the disk scan and the table refs.
  - tools/ and root-level references (e.g. orchestrator.py) in the table are allowed
    (cross-folder reuse), not flagged stale.
  - Only TABLE ROWS within the "## Scripts in This Folder" section are parsed, so prose
    inside that section (e.g. a "generate_morris_ensemble.py (deleted in P1 ...)"
    historical note) and the separate "Shared Tools Used (in tools/)" section do not
    trigger false positives.

Exit 0 = clean; exit 1 = drift. stdlib-only → safe to run in the pre-commit hook.

Author: Jing Tao with Claude
"""
import re
import sys
import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PHASES = ROOT / "phases"
TOOLS = ROOT / "tools"

GLOBAL_IGNORE = ["__init__.py"]
# Per-phase ignore globs beyond the global list (matched against bare filenames).
IGNORE = {
    "phase3_diagnosis": ["test_*.py"],  # auto-discovered hypothesis tests (root CLAUDE.md)
}


def _ignored(name, phase_name):
    globs = GLOBAL_IGNORE + IGNORE.get(phase_name, [])
    return any(fnmatch.fnmatch(name, g) for g in globs)


def scripts_table_refs(text):
    """Backticked *.py names in the TABLE ROWS of the '## Scripts in This Folder' section.

    Captures from that H2 heading up to the next H2 (### subsections are kept, so
    phase3's High-Level / Low-Level tables are both included), then looks only at table
    rows (lines starting with '|') so prose inside the section is ignored.
    """
    m = re.search(
        r"^##\s+Scripts in This Folder\s*$(.*?)(?=^##\s)",
        text, re.MULTILINE | re.DOTALL,
    )
    section = m.group(1) if m else ""
    rows = [ln for ln in section.splitlines() if ln.lstrip().startswith("|")]
    return set(re.findall(r"`([A-Za-z0-9_]+\.py)`", "\n".join(rows)))


def local_scripts(phase_dir, phase_name):
    return {p.name for p in phase_dir.glob("*.py") if not _ignored(p.name, phase_name)}


def main():
    # Scripts that may legitimately be referenced from a phase table but live elsewhere.
    allowed_external = {p.name for p in TOOLS.glob("*.py")} | {p.name for p in ROOT.glob("*.py")}
    phase_dirs = sorted(
        d for d in PHASES.iterdir()
        if d.is_dir() and re.match(r"phase\d", d.name)
    )
    any_drift = False
    for d in phase_dirs:
        claude = d / "CLAUDE.md"
        if not claude.exists():
            print(f"  ✗ {d.name}: no CLAUDE.md")
            any_drift = True
            continue
        text = claude.read_text()
        table = {n for n in scripts_table_refs(text) if not _ignored(n, d.name)}
        local = local_scripts(d, d.name)
        undocumented = sorted(local - table)
        stale = sorted(n for n in table if n not in local and n not in allowed_external)
        if undocumented or stale:
            any_drift = True
            print(f"  ✗ {d.name}:")
            for n in undocumented:
                print(f"      UNDOCUMENTED  {n}  (on disk, not in Scripts table)")
            for n in stale:
                print(f"      STALE         {n}  (in Scripts table, no such script)")
        else:
            print(f"  ✓ {d.name}: {len(local)} scripts, table in sync")
    print()
    if any_drift:
        print("✗ phase script-doc drift — scripts are truth; update the phase "
              "CLAUDE.md 'Scripts in This Folder' table to match disk")
        return 1
    print("✔ all phase CLAUDE.md Scripts tables match disk")
    return 0


if __name__ == "__main__":
    sys.exit(main())
