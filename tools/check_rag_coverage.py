#!/usr/bin/env python3
"""RAG coverage self-test (docs/33 §3c, meta-validation Phase 1). Catches the "a kb_source or a
key wiki file was silently dropped from the index" bug class — the 2026-07-05/06 bug where the ELM
wiki was entirely absent from the index (the retriever returned FATES-only answers with no error).

Metadata-only: reads the active profile's Chroma collection and checks, against
`rag/canary_queries.yaml`, that each expected `kb_source` is present above a floor and that a few
canary wiki-source files appear. No embedding model needed. Degrades gracefully (exit 0 with a note)
if chromadb / pyyaml / the index are unavailable — so it never blocks an environment that can't run it.

Reading the index rewrites the tracked `chroma.sqlite3` (churn) — that file is `--skip-worktree` per
clone, so this is safe.

Usage:
    python3 tools/check_rag_coverage.py [--profile api-43-1] [--canary rag/canary_queries.yaml]
"""
import os
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _skip(msg):
    print(f"  [skip] check_rag_coverage: {msg}")
    return 0


def resolve_profile(arg, cfg):
    if arg:
        return arg
    env = os.environ.get("A2MC_RAG_ACTIVE", "")
    if env:
        return env
    # default: first configured profile that has a chroma dir on disk
    rag_dir = Path(os.environ.get("A2MC_RAG_DIR", REPO / "rag"))
    for name in cfg.get("profiles", {}):
        if (rag_dir / "chroma_db" / name).is_dir():
            return name
    return None


def main(argv):
    profile_arg = None
    canary_path = REPO / "rag" / "canary_queries.yaml"
    it = iter(argv)
    for a in it:
        if a == "--profile":
            profile_arg = next(it, None)
        elif a == "--canary":
            canary_path = Path(next(it, canary_path))
    try:
        import yaml
    except ImportError:
        return _skip("pyyaml not available")
    try:
        import chromadb
    except ImportError:
        return _skip("chromadb not available")
    if not canary_path.is_file():
        return _skip(f"no canary config at {canary_path}")

    cfg = yaml.safe_load(canary_path.read_text()) or {}
    profile = resolve_profile(profile_arg, cfg)
    if not profile:
        return _skip("no active profile (set A2MC_RAG_ACTIVE or pass --profile) and no index on disk")
    rag_dir = Path(os.environ.get("A2MC_RAG_DIR", REPO / "rag"))
    persist = rag_dir / "chroma_db" / profile
    if not persist.is_dir():
        return _skip(f"no chroma index for profile '{profile}' at {persist}")

    collection = cfg.get("collection", "fates_knowledge")
    try:
        client = chromadb.PersistentClient(path=str(persist))
        col = client.get_collection(collection)
        total = col.count()
        metas = col.get(include=["metadatas"], limit=total)["metadatas"] if total else []
    except Exception as e:  # noqa: BLE001 — a load failure IS a coverage failure signal
        print(f"✘ check_rag_coverage: could not open collection '{collection}' for '{profile}': {e}")
        return 1

    ks = Counter(m.get("kb_source", "?") for m in metas)
    sources = {str(m.get("source", "")) for m in metas}

    spec = cfg.get("profiles", {}).get(profile)
    errors = []
    if spec is None:
        print(f"  [warn] profile '{profile}' not in canary config — basic check only")
        if total <= 0:
            errors.append(f"index '{profile}' is EMPTY")
        elif len([k for k in ks if k != "?"]) < 1:
            errors.append(f"index '{profile}' has no kb_source-tagged chunks")
    else:
        if total < spec.get("min_total", 0):
            errors.append(f"total chunks {total} < floor {spec['min_total']} — index looks truncated")
        for kb, floor in (spec.get("kb_sources") or {}).items():
            if ks.get(kb, 0) < floor:
                errors.append(
                    f"kb_source '{kb}' has {ks.get(kb, 0)} chunks (floor {floor}) — a whole "
                    f"knowledge base may be missing from the index (the ELM-wiki-absent bug class)")
        for want in spec.get("must_contain_sources") or []:
            if not any(want in s for s in sources):
                errors.append(f"canary source '{want}' not found in the index — it was dropped")

    print(f"  profile '{profile}': total={total}, kb_sources={dict(ks)}")
    if errors:
        print(f"\n✘ {len(errors)} coverage problem(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"✔ RAG coverage: profile '{profile}' — kb_sources + canary sources present")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
