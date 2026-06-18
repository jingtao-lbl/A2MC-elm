#!/usr/bin/env python3
"""
review_pending_knowledge.py — human-in-the-loop curation of proposed Tier-3 knowledge.

The autonomous online agent (orchestrator) runs its MemoryManager in "propose" mode,
so its auto_learn writes land in `auto_discovered_pending.json` instead of the curated
KB (discoveries.json / failed_approaches.json / experiments.json). This tool lets the
interactive (human-in-the-loop) agent review those staged proposals and promote the
vetted ones into the curated KB, or discard the rest.

Why this exists: the curated KB shapes the AI's diagnoses. A misunderstood or
failed-experiment "lesson" written unattended can poison every subsequent cycle (see
memory/dev_logs/20260519a_*). Gating curated writes behind human review closes that
loop. Design + rationale: memory/dev_logs/20260612d_Memory_Write_Gate_Interactive_Only_Curated.md

Usage:
    python tools/review_pending_knowledge.py list [--memory-dir DIR] [--all]
    python tools/review_pending_knowledge.py promote (--key K | --index N | --all)
                                              [--memory-dir DIR] [--confidence C]
    python tools/review_pending_knowledge.py discard (--key K | --index N | --all)
                                              [--memory-dir DIR]

If --memory-dir is omitted it defaults to $A2MC_USE_CASE_DIR/memory/gained_knowledge.

Author: Jing Tao with Claude
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime

# Make `memory` importable when run as `python tools/review_pending_knowledge.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory.manager import MemoryManager, PENDING_FILENAME  # noqa: E402
from memory.store import load_json, save_json                # noqa: E402


def resolve_memory_dir(arg_dir):
    if arg_dir:
        return Path(arg_dir)
    use_case = os.environ.get("A2MC_USE_CASE_DIR", "")
    if use_case:
        return Path(use_case) / "memory" / "gained_knowledge"
    sys.exit("ERROR: --memory-dir not given and A2MC_USE_CASE_DIR is unset. "
             "Source the site config or pass --memory-dir.")


def load_pending(memory_dir):
    path = memory_dir / PENDING_FILENAME
    if not path.exists():
        return path, {"pending": []}
    return path, load_json(path, default={"pending": []})


def is_open(item):
    return not item.get("promoted") and not item.get("discarded")


def select_indices(items, args):
    """Return the list of pending-list indices targeted by --key/--index/--all."""
    if args.all:
        return [i for i, it in enumerate(items) if is_open(it)]
    if args.index is not None:
        if args.index < 0 or args.index >= len(items):
            sys.exit(f"ERROR: --index {args.index} out of range (0..{len(items)-1}).")
        return [args.index]
    if args.key is not None:
        hits = [i for i, it in enumerate(items)
                if it.get("key") == args.key and is_open(it)]
        if not hits:
            sys.exit(f"ERROR: no open pending entry with key={args.key!r}.")
        return hits
    sys.exit("ERROR: specify one of --key, --index, or --all.")


def cmd_list(memory_dir, args):
    _, pending = load_pending(memory_dir)
    items = pending["pending"]
    shown = 0
    print(f"Pending knowledge in {memory_dir / PENDING_FILENAME}:")
    print(f"{'idx':>3}  {'kind':<15} {'status':<9} {'staged_at':<20} key")
    print("-" * 78)
    for i, it in enumerate(items):
        if not args.all and not is_open(it):
            continue
        status = ("promoted" if it.get("promoted")
                  else "discarded" if it.get("discarded") else "open")
        print(f"{i:>3}  {it.get('kind',''):<15} {status:<9} "
              f"{it.get('staged_at','')[:19]:<20} {it.get('key','')}")
        shown += 1
    n_open = sum(1 for it in items if is_open(it))
    print("-" * 78)
    print(f"{shown} shown; {n_open} open / {len(items)} total. "
          f"Use 'promote'/'discard' with --key, --index, or --all.")


def _promote_one(mm, item, confidence):
    """Write one staged entry into the curated KB via an interactive MemoryManager."""
    kind = item.get("kind")
    entry = item.get("entry", {})
    if kind == "discovery":
        mm.add_discovery(
            name=item["key"],
            description=entry.get("description", ""),
            mechanism=entry.get("mechanism", ""),
            affects=entry.get("affects", []),
            implications=entry.get("implications", []),
            parameters_involved=entry.get("parameters_involved", []),
            do_not_repeat=entry.get("do_not_repeat", []),
            source="curated",                      # promoted => verified
            confidence=confidence if confidence is not None
            else entry.get("confidence", 0.6),
            references=entry.get("references", []),
        )
    elif kind == "failed_approach":
        mm.add_failed_approach(
            approach=entry.get("approach", item["key"]),
            experiment_id=entry.get("experiment_id", ""),
            why_failed=entry.get("why_failed", ""),
            severity=entry.get("severity", "no_effect"),
            alternatives=entry.get("alternatives", []),
        )
    elif kind == "experiment":
        mm.record_experiment(
            experiment={
                "name": entry.get("id", item["key"]),
                "base_case": entry.get("base_case"),
                "hypothesis": entry.get("hypothesis"),
                "modifications": entry.get("modifications", []),
            },
            results=entry.get("results", {}),
            outcome=entry.get("outcome", "no_effect"),
            lesson=entry.get("lesson"),
        )
    else:
        raise ValueError(f"Unknown staged kind: {kind!r}")


def cmd_promote(memory_dir, args):
    path, pending = load_pending(memory_dir)
    items = pending["pending"]
    targets = select_indices(items, args)
    # Interactive-mode manager actually writes the curated JSONs.
    mm = MemoryManager(str(memory_dir), write_mode="interactive")
    for i in targets:
        it = items[i]
        _promote_one(mm, it, args.confidence)
        it["promoted"] = True
        it["promoted_at"] = datetime.now().isoformat()
        print(f"  [promoted] {it.get('kind')} '{it.get('key')}' -> curated KB (verified)")
    save_json(path, pending)
    print(f"Promoted {len(targets)} entr{'y' if len(targets)==1 else 'ies'}.")


def cmd_discard(memory_dir, args):
    path, pending = load_pending(memory_dir)
    items = pending["pending"]
    targets = select_indices(items, args)
    for i in targets:
        items[i]["discarded"] = True
        items[i]["discarded_at"] = datetime.now().isoformat()
        print(f"  [discarded] {items[i].get('kind')} '{items[i].get('key')}'")
    save_json(path, pending)
    print(f"Discarded {len(targets)} entr{'y' if len(targets)==1 else 'ies'}.")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--memory-dir", help="gained_knowledge dir (default: "
                   "$A2MC_USE_CASE_DIR/memory/gained_knowledge)")
    sub = p.add_subparsers(dest="command")  # 'required' kwarg is 3.7+; checked below

    pl = sub.add_parser("list", help="list staged proposals")
    pl.add_argument("--all", action="store_true", help="include promoted/discarded")

    pp = sub.add_parser("promote", help="promote staged proposals into curated KB")
    g = pp.add_mutually_exclusive_group(required=True)
    g.add_argument("--key", help="promote open entries with this key")
    g.add_argument("--index", type=int, help="promote the entry at this list index")
    g.add_argument("--all", action="store_true", help="promote all open entries")
    pp.add_argument("--confidence", type=float, default=None,
                    help="override confidence for promoted discoveries")

    pd = sub.add_parser("discard", help="discard staged proposals")
    gd = pd.add_mutually_exclusive_group(required=True)
    gd.add_argument("--key", help="discard open entries with this key")
    gd.add_argument("--index", type=int, help="discard the entry at this list index")
    gd.add_argument("--all", action="store_true", help="discard all open entries")

    args = p.parse_args()
    if not args.command:
        p.print_help()
        sys.exit(1)
    memory_dir = resolve_memory_dir(args.memory_dir)

    if args.command == "list":
        cmd_list(memory_dir, args)
    elif args.command == "promote":
        cmd_promote(memory_dir, args)
    elif args.command == "discard":
        cmd_discard(memory_dir, args)


if __name__ == "__main__":
    main()
