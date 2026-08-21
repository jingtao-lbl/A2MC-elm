#!/usr/bin/env python3
"""RAG golden-query test (meta-validation, content layer).

Runs a curated set of realistic queries (rag/golden_queries.yaml) against a BUILT RAG
profile and asserts the retrieved CONTENT is correct — the class of regression that the
metadata-only coverage check (tools/check_rag_coverage.py) cannot see: a wrong SZPF
ordering formula, a mislabeled PFT identity, a dropped mechanism (see dev_logs 20260710r/t).

Unlike the coverage canary, this loads the embedding model + the graph and queries the
index the way the reasoning agent does (HybridRetriever.get_context) plus a direct graph
PFT-identity check.

Usage:
    python3 tools/check_rag_queries.py [--profile api-43-1] [--queries rag/golden_queries.yaml]

Exit codes: 0 = pass (or gracefully skipped if RAG deps unavailable), 1 = a query/identity
assertion failed. Degrades gracefully (exit 0 + note) only on missing deps, never on a real
assertion failure.
"""
import os
import sys
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))   # so `import rag` works when run as a script file


def _skip(msg: str) -> int:
    print(f"  [skip] RAG golden-query test: {msg}")
    return 0


def _flatten(obj) -> str:
    """Flatten a get_context dict (or any structure) to one searchable string."""
    return json.dumps(obj, default=str)


def main() -> int:
    profile = os.environ.get("A2MC_RAG_ACTIVE", "api-43-1")
    queries_path = REPO / "rag" / "golden_queries.yaml"
    it = iter(sys.argv[1:])
    for a in it:
        if a == "--profile":
            profile = next(it, profile)
        elif a in ("--queries", "--golden"):
            queries_path = Path(next(it, queries_path))
        elif a in ("-h", "--help"):
            print(__doc__)
            return 0

    try:
        import yaml
    except Exception as e:
        return _skip(f"PyYAML unavailable ({e})")
    if not queries_path.is_file():
        return _skip(f"no golden-query config at {queries_path}")

    cfg = yaml.safe_load(queries_path.read_text()) or {}
    spec = (cfg.get("profiles") or {}).get(profile)
    if not spec:
        print(f"  [warn] profile '{profile}' not in {queries_path.name} — nothing to test")
        return 0

    # Make sure the retriever loads THIS profile.
    os.environ["A2MC_RAG_ACTIVE"] = profile
    try:
        from rag import HybridRetriever
        retr = HybridRetriever(auto_build=False)
    except Exception as e:
        return _skip(f"could not load RAG retriever / embedding model ({e})")

    errors = []
    n_checks = 0

    # --- 1. Retrieval/content queries ---
    for q in spec.get("queries") or []:
        name = q.get("name", q.get("query", "?"))
        try:
            ctx = _flatten(retr.get_context(q["query"], n_vector_results=6))
        except Exception as e:
            errors.append(f"query '{name}': retrieval failed ({e})")
            continue
        low = ctx.lower()
        for sub in q.get("must_contain") or []:
            n_checks += 1
            if sub.lower() not in low:
                errors.append(f"query '{name}': MISSING required text {sub!r}")
        for sub in q.get("must_not_contain") or []:
            n_checks += 1
            if sub.lower() in low:
                errors.append(f"query '{name}': found FORBIDDEN text {sub!r} (stale/wrong content)")
        any_list = q.get("must_contain_any") or []
        if any_list:
            n_checks += 1
            if not any(s.lower() in low for s in any_list):
                errors.append(f"query '{name}': none of {any_list} present in retrieved context")

    # --- 2. Graph PFT-identity check ---
    pft_expect = spec.get("pft_identity") or {}
    if pft_expect:
        try:
            G = retr.knowledge_graph.graph
            got = {
                d.get("index"): str(d.get("name", ""))
                for _, d in G.nodes(data=True)
                if str(d.get("node_type", "")).upper() == "PFT"
            }
        except Exception as e:
            errors.append(f"PFT-identity: could not read graph PFT nodes ({e})")
            got = {}
        for pid, want in pft_expect.items():
            n_checks += 1
            pid = int(pid)
            name = got.get(pid)
            if name is None:
                errors.append(f"PFT-identity: PFT{pid} node missing from graph")
            elif want.lower() not in name.lower():
                errors.append(
                    f"PFT-identity: PFT{pid} name {name!r} does not contain {want!r} "
                    f"(wrong/stale identity)"
                )

    print(f"  profile '{profile}': ran {n_checks} content assertions "
          f"({len(spec.get('queries') or [])} queries + {len(pft_expect)} PFT identities)")
    if errors:
        print(f"\n✘ RAG golden-query test FAILED for '{profile}':", file=sys.stderr)
        for e in errors:
            print(f"    - {e}", file=sys.stderr)
        return 1
    print(f"✔ RAG golden-query test: profile '{profile}' — content + PFT identities correct")
    return 0


if __name__ == "__main__":
    sys.exit(main())
