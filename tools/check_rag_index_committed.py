#!/usr/bin/env python3
"""Assert the COMMITTED RAG index matches the COMMITTED expected_counts.

WHY THIS EXISTS
---------------
`rag/chroma_db/<profile>/chroma.sqlite3` is tracked, but ChromaDB rewrites it on every
READ, so every clone suppresses that churn with `git update-index --skip-worktree`. That
flag tells git to stop looking at the file entirely: after a rebuild, `git add` AND
`git add -A` stage **nothing** and print no error. The graph (`rag/graphs/<profile>.json`)
is plain JSON and commits normally, and `rag/milestones.json` commits normally too — so
the visible artifacts all move forward while the index silently does not.

That is not hypothetical. Between 2026-07-31 and 2026-08-07 the PFLOTRAN profile shipped
`expected_counts.documents = 1374` beside a committed index holding **1314** documents with
ZERO curated-seed chunks. Every gate was green for a week; the reasoning layer was reading a
pre-seed index.

WHAT IT CHECKS, AND WHY FROM GIT
--------------------------------
For every milestone declaring `expected_counts.documents`, compare that number against the
document count inside the **committed** `chroma.sqlite3` blob — read via `git show`, never
off disk.

Reading from disk would defeat the entire purpose: on disk the rebuild is always present,
which is exactly why this failure was invisible. The question is not "did I rebuild?" but
"did the rebuild reach the repo?", and only the blob can answer it.

Stdlib only (`sqlite3` + `subprocess`), so it runs anywhere `check_log_conformance.py` does.

Exit: 0 clean · 1 warn · 2 error.

Author: Jing Tao with Claude
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MILESTONES = ROOT / "rag" / "milestones.json"


def _git_show(rev_path: str) -> bytes | None:
    """`git show <rev>:<path>` -> bytes, or None when the path is absent at that rev."""
    p = subprocess.run(["git", "-C", str(ROOT), "show", rev_path],
                       capture_output=True)
    return p.stdout if p.returncode == 0 else None


def _counts_from_blob(blob: bytes) -> dict[str, int]:
    """{collection_name: document_count} from a committed chroma.sqlite3 blob.

    Counts through segments so a store holding more than one collection reports each
    separately — a profile carrying a foreign collection is itself a finding (the
    HybridRetriever collection-name bug manufactures an empty `fates_knowledge` inside an
    adapter's persist dir), and a blunt total would hide it.
    """
    # NamedTemporaryFile under the repo's gitignored tmp/: a hook forbids writes to /tmp
    # on this machine, and the repo dir is the documented scratch location.
    scratch = ROOT / "tmp"
    scratch.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=scratch, suffix=".sqlite3") as fh:
        fh.write(blob)
        fh.flush()
        db = sqlite3.connect(fh.name)
        try:
            # NO scope filter. The embedding rows hang off the collection's **METADATA**
            # segment, not its VECTOR one -- filtering on scope='VECTOR' returns 0 for every
            # profile, which this checker did on its first run and which testing against a
            # known-good index (1374) immediately exposed. Each embedding row references
            # exactly one segment, and each segment one collection, so joining across all of
            # a collection's segments counts every row once and cannot double-count.
            rows = db.execute(
                "SELECT c.name, COUNT(e.id) "
                "FROM collections c "
                "LEFT JOIN segments s ON s.collection = c.id "
                "LEFT JOIN embeddings e ON e.segment_id = s.id "
                "GROUP BY c.name"
            ).fetchall()
        finally:
            db.close()
    return {name: n for name, n in rows}


def check(rev: str = "HEAD") -> int:
    if not MILESTONES.exists():
        print(f"rag index check — {MILESTONES.relative_to(ROOT)} absent; nothing to check")
        return 0

    blob = _git_show(f"{rev}:rag/milestones.json")
    if blob is None:
        print(f"rag index check — rag/milestones.json not present at {rev or '<staged>'}; skipping")
        return 0
    milestones = json.loads(blob).get("milestones", {})

    errors: list[str] = []
    warns: list[str] = []
    checked = 0

    for profile, meta in sorted(milestones.items()):
        expected = ((meta.get("expected_counts") or {}).get("documents"))
        if not expected:
            continue                      # no armed count -> nothing to assert
        rel = f"rag/chroma_db/{profile}/chroma.sqlite3"
        sql = _git_show(f"{rev}:{rel}")
        if sql is None:
            warns.append(f"{profile}: expected_counts.documents={expected} but {rel} is not "
                         f"committed at {rev} — the index was never added")
            continue
        checked += 1
        try:
            per_collection = _counts_from_blob(sql)
        except sqlite3.Error as exc:                     # corrupt/unreadable blob
            errors.append(f"{profile}: committed {rel} is not a readable sqlite ({exc})")
            continue

        total = sum(per_collection.values())
        if total != expected:
            detail = ", ".join(f"{k}={v}" for k, v in sorted(per_collection.items()))
            errors.append(
                f"{profile}: milestones.json says documents={expected}, but the COMMITTED "
                f"index holds {total} ({detail}).\n"
                f"      A rebuild did not reach the repo. chroma.sqlite3 carries "
                f"--skip-worktree, so `git add` stages it silently:\n"
                f"        git update-index --no-skip-worktree {rel}\n"
                f"        <rebuild>  &&  git add {rel}  &&  git commit\n"
                f"        git update-index --skip-worktree {rel}\n"
                f"      See the `rebuild-rag` skill, Step 4.")

        empties = [k for k, v in per_collection.items() if v == 0]
        if empties and len(per_collection) > 1:
            warns.append(f"{profile}: committed index carries empty collection(s) "
                         f"{empties} beside its real one — a foreign collection was "
                         f"manufactured by opening the store under the wrong name "
                         f"(HybridRetriever collection-name bug)")

    print(f"rag index check — {checked} committed index/indices checked at {rev or '<staged>'}")
    for e in errors:
        print(f"  ERROR {e}")
    for w in warns:
        print(f"  [warn] {w}")
    if not errors and not warns:
        print("\n✔ every committed RAG index matches its committed expected_counts")
        return 0
    print(f"\n{len(errors)} error(s), {len(warns)} warning(s)")
    return 2 if errors else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rev", default="HEAD",
                    help="git revision to read the committed artifacts from (default HEAD)")
    ap.add_argument("--staged", action="store_true",
                    help="check the STAGED content (git index) instead of a commit — what a "
                         "pre-commit hook wants, since HEAD does not yet contain the change "
                         "being made and checking it would validate the PREVIOUS commit")
    args = ap.parse_args()
    # `git show :<path>` reads the index (stage 0); the empty rev is deliberate, not a bug.
    return check("" if args.staged else args.rev)


if __name__ == "__main__":
    sys.exit(main())
