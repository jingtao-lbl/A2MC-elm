#!/usr/bin/env python3
"""
describe_mode.py — print the active A2MC run configuration ("mode").

A thin reuse of the existing mode-aware machinery (NOT new logic): it resolves the
current `ConfigMode` via `tools.config.config.MODE` (`ConfigMode.from_env()`, enriched by
the case dir) and prints `ConfigMode.to_prompt_block()` — the same human-readable summary
the orchestrator injects into Phase 3/4 prompts.

The interactive (offline) agent and the `.claude/skills/` call this to learn the case's
configuration before doing mode-specific work: model family (ELM with or without FATES),
PARTEH / nutrient cycling, nutrient competition pathway (ECA vs RD), FATES feature flags,
and the active RAG milestone (FATES/ELM API). See docs/25_Offline_Interactive_Agent_Mode_Plan.md.

Usage:
    python tools/describe_mode.py            # human-readable summary
    python tools/describe_mode.py --json     # structured ConfigMode fields (for guards)

Source your machine + site config first (a2mc_config.sh + use_cases/<site>/config/<site>_config.sh);
otherwise the mode cannot be resolved and a friendly hint is printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def resolve_mode():
    """Return the active ConfigMode, or None if it cannot be resolved."""
    from tools.config import config
    return config.MODE  # ConfigMode.from_env(); may raise if unconfigured


def main() -> int:
    ap = argparse.ArgumentParser(description="Print the active A2MC run configuration (mode).")
    ap.add_argument("--json", action="store_true",
                    help="Emit structured ConfigMode fields instead of the human summary.")
    args = ap.parse_args()

    try:
        mode = resolve_mode()
    except Exception as e:
        print(
            "Could not resolve the active mode. Source your config first:\n"
            "  source a2mc_config.sh\n"
            "  source use_cases/<site>/config/<site>_config.sh\n"
            f"(reason: {e})",
            file=sys.stderr,
        )
        return 2

    if args.json:
        data = asdict(mode) if is_dataclass(mode) else dict(getattr(mode, "__dict__", {}))
        data["rag_milestone"] = os.environ.get("A2MC_RAG_ACTIVE", "")
        print(json.dumps(data, indent=2, default=str))
    else:
        print(mode.to_prompt_block())
        milestone = os.environ.get("A2MC_RAG_ACTIVE", "")
        if milestone:
            print(f"- RAG milestone (model API): {milestone}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
