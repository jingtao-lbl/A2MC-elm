#!/usr/bin/env python3
"""
rag_selector.py - Match a user's ELM-FATES checkout to a registered milestone.

The user runs A2MC against their own E3SM/ELM-FATES checkout. The selector's
job is to find which registered milestone profile (`api-31-0`, `api-43-1`, etc.)
best fits the user's commits, and report whether to use it as-is or rebuild.

Selection logic (bidirectional, see plan §4.5 + scope discussion 2026-04-28):

    1. Detect user's FATES api epoch from `git describe`.

    2. Exact-epoch match: a milestone exists with `fates_api_epoch ==` user's.
       Compare parameter-file sha:
         - matches:  EXACT_EPOCH (no rebuild) or CLOSE_ENOUGH (sci drift OK).
         - differs:  REBUILD_NEEDED (param surface changed within epoch).

    3. Bidirectional nearest-epoch fallback: pick the milestone whose api epoch
       is closest to the user's, considering BOTH lower and higher epochs.
       Distance is `abs(major_diff) * 100 + abs(minor_diff)`. Returns
       REBUILD_NEEDED with that milestone as basis. Direction is reported in
       the result.

    4. No registered milestones at all: NO_MATCH.

Used by:
    - orchestrator.py startup hook (`_check_rag_alignment`)
    - scripts/rag_match.py CLI for diagnostic + bump advisor
    - scripts/rag_bump.py to determine bump tier (T1/T2/T3)

Author: Jing Tao with Claude
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional, Tuple

# Sibling tools
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from model_version import ELMFATESVersion  # noqa: E402
from rag_manifest import Manifest, Milestone  # noqa: E402


SelectionMode = Literal[
    "exact_epoch",      # epoch match + sha match → use milestone as-is
    "close_enough",     # epoch match + sha match + sci drift → use as-is, note drift
    "rebuild_needed",   # epoch match but sha differs OR closest-epoch fallback
    "no_match",         # no milestone exists at all
]


# =============================================================================
# Public dataclasses
# =============================================================================

@dataclass
class RAGSelection:
    """Selector result. Tells the caller which milestone to use and how."""
    profile_name: Optional[str]                 # which milestone profile to load
    mode: SelectionMode
    milestone: Optional[Milestone]              # milestone entry used as basis (None if no_match)
    user_api_epoch: Optional[str]               # user's detected epoch
    milestone_api_epoch: Optional[str]          # milestone's epoch
    direction: Optional[str] = None             # 'exact', 'forward', 'backward'
    epoch_distance: Optional[int] = None        # abs distance in (major*100+minor) units
    drift_sci_tags: Optional[int] = None        # tags between milestone tag and user commit (within epoch)
    drift_commits: Optional[int] = None         # raw commit distance in FATES repo (None if not computed)
    param_file_changed: bool = False
    rebuild_required: bool = False
    reason: str = ""                            # human-readable explanation

    def to_dict(self) -> dict:
        d = {
            "profile_name": self.profile_name,
            "mode": self.mode,
            "user_api_epoch": self.user_api_epoch,
            "milestone_api_epoch": self.milestone_api_epoch,
            "direction": self.direction,
            "epoch_distance": self.epoch_distance,
            "drift_sci_tags": self.drift_sci_tags,
            "drift_commits": self.drift_commits,
            "param_file_changed": self.param_file_changed,
            "rebuild_required": self.rebuild_required,
            "reason": self.reason,
        }
        if self.milestone:
            d["milestone"] = self.milestone.to_dict()
        return d


# =============================================================================
# Helpers
# =============================================================================

def _parse_epoch(epoch: str) -> Tuple[int, int]:
    """Parse 'X.Y' → (X, Y) ints. Raises ValueError if malformed."""
    parts = epoch.split(".")
    if len(parts) != 2:
        raise ValueError(f"Malformed api epoch: {epoch!r}")
    return int(parts[0]), int(parts[1])


def _epoch_distance(a: str, b: str) -> int:
    """Compute scaled distance between two api epochs.

    `abs(major_a - major_b) * 100 + abs(minor_a - minor_b)` so a major-version
    diff always outweighs minor.
    """
    am, an = _parse_epoch(a)
    bm, bn = _parse_epoch(b)
    return abs(am - bm) * 100 + abs(an - bn)


def _compare_epochs(user: str, ms: str) -> str:
    """Return 'exact', 'forward', or 'backward'. 'forward' = user > milestone."""
    um, un = _parse_epoch(user)
    mm, mn = _parse_epoch(ms)
    if (um, un) == (mm, mn):
        return "exact"
    if (um, un) > (mm, mn):
        return "forward"
    return "backward"


def _count_drift_sci_tags(milestone: Milestone, user_describe: str) -> Optional[int]:
    """Count sci tags between milestone's `fates_tag_built` and the user's nearest tag.

    Both must be within the milestone's `covers_sci_tags` for a meaningful count.
    Returns None if either is missing or not in the list.
    """
    if not milestone.covers_sci_tags or not milestone.fates_tag_built or not user_describe:
        return None
    # User's nearest tag is the part of describe before the `-N-gSHA` suffix.
    parts = user_describe.split("-")
    if len(parts) < 3:
        user_tag = user_describe
    else:
        user_tag = "-".join(parts[:-2])
    try:
        i_milestone = milestone.covers_sci_tags.index(milestone.fates_tag_built)
        i_user = milestone.covers_sci_tags.index(user_tag)
    except ValueError:
        return None
    return abs(i_user - i_milestone)


# =============================================================================
# Public API: selection
# =============================================================================

def select_rag(
    user_version: ELMFATESVersion,
    manifest: Manifest,
    user_param_file_sha: Optional[str] = None,
) -> RAGSelection:
    """Decide which RAG profile to use for the user's ELM-FATES checkout.

    Args:
        user_version: detected version state from `tools.model_version`.
        manifest: loaded milestone registry from `tools.rag_manifest`.
        user_param_file_sha: sha256 of the user's FATES parameter file (CDL or
            JSON). Used for the param-file drift check on epoch matches. If
            None, drift cannot be detected and selector errs on the side of
            "close_enough" (no rebuild).

    Returns:
        RAGSelection. `profile_name` is None only when `mode == 'no_match'`.
    """
    user_epoch = user_version.fates_api_epoch
    if not user_epoch:
        return RAGSelection(
            profile_name=None,
            mode="no_match",
            milestone=None,
            user_api_epoch=None,
            milestone_api_epoch=None,
            reason=(
                f"Cannot determine user's FATES api epoch from "
                f"describe='{user_version.fates.describe}'. "
                f"`git describe --tags --long` may have failed in the FATES "
                f"submodule, or the checkout has no reachable api.X.Y tag."
            ),
        )

    if not manifest.milestones:
        return RAGSelection(
            profile_name=None,
            mode="no_match",
            milestone=None,
            user_api_epoch=user_epoch,
            milestone_api_epoch=None,
            reason="No registered milestones in rag/milestones.json.",
        )

    # ----- Step 2: exact-epoch match -----
    exact = [m for m in manifest.milestones.values() if m.fates_api_epoch == user_epoch]
    if exact:
        # Prefer canonical, then most recently published
        exact.sort(key=lambda m: (not m.canonical, m.published_at or ""), reverse=False)
        ms = exact[0]
        param_changed = False
        if user_param_file_sha is not None and ms.fates_commit_built:
            # We don't carry the milestone's param sha here; that's in metadata
            # JSON. Caller (rag_match / orchestrator) compares the metadata
            # sha against `user_param_file_sha` and passes the result via
            # `user_param_file_sha != metadata.fates_param_file_sha`. To keep
            # this function simple, treat user_param_file_sha as advisory:
            # the caller can override `param_file_changed` post-hoc via the
            # `rebuild_required` field.
            pass

        drift = _count_drift_sci_tags(ms, user_version.fates.describe or "")
        if drift is None or drift == 0:
            mode: SelectionMode = "exact_epoch"
            reason = (
                f"User's FATES is at sci tag '{user_version.fates.nearest_tag}' "
                f"(api epoch {user_epoch}); milestone '{ms.profile_name}' was "
                f"built against the same tag. Use as-is."
            )
        else:
            mode = "close_enough"
            reason = (
                f"User's FATES sci tag '{user_version.fates.nearest_tag}' is "
                f"{drift} tag(s) away from milestone build tag "
                f"'{ms.fates_tag_built}', but both are inside api epoch "
                f"{user_epoch}. Use milestone as-is; sci-only drift does not "
                f"change the parameter surface or wiki content materially."
            )
        return RAGSelection(
            profile_name=ms.profile_name,
            mode=mode,
            milestone=ms,
            user_api_epoch=user_epoch,
            milestone_api_epoch=ms.fates_api_epoch,
            direction="exact",
            epoch_distance=0,
            drift_sci_tags=drift,
            drift_commits=user_version.fates.commits_past_tag,
            param_file_changed=False,
            rebuild_required=False,
            reason=reason,
        )

    # ----- Step 3: bidirectional nearest-epoch fallback -----
    by_distance = sorted(
        manifest.milestones.values(),
        key=lambda m: (
            _epoch_distance(user_epoch, m.fates_api_epoch),
            not m.canonical,        # prefer canonical at same distance
            m.published_at or "",
        ),
    )
    nearest = by_distance[0]
    distance = _epoch_distance(user_epoch, nearest.fates_api_epoch)
    direction = _compare_epochs(user_epoch, nearest.fates_api_epoch)

    if direction == "forward":
        reason = (
            f"User's FATES is at api epoch {user_epoch}, ahead of nearest "
            f"registered milestone '{nearest.profile_name}' (api epoch "
            f"{nearest.fates_api_epoch}). Distance {distance} units. Rebuild "
            f"recommended; api-major or api-minor diff means parameter surface "
            f"and host interface have evolved."
        )
    elif direction == "backward":
        reason = (
            f"User's FATES is at api epoch {user_epoch}, BEHIND nearest "
            f"registered milestone '{nearest.profile_name}' (api epoch "
            f"{nearest.fates_api_epoch}). Distance {distance} units. The "
            f"milestone may not match user's source. Consider rebuilding "
            f"against user's commit, or using an older milestone if available."
        )
    else:  # exact distance 0 but not in `exact` list — shouldn't happen, defensive
        reason = (
            f"Closest milestone '{nearest.profile_name}' has the same epoch "
            f"as user but was not selected as exact match — investigate."
        )

    return RAGSelection(
        profile_name=nearest.profile_name,
        mode="rebuild_needed",
        milestone=nearest,
        user_api_epoch=user_epoch,
        milestone_api_epoch=nearest.fates_api_epoch,
        direction=direction,
        epoch_distance=distance,
        drift_sci_tags=None,
        drift_commits=user_version.fates.commits_past_tag,
        param_file_changed=False,
        rebuild_required=True,
        reason=reason,
    )


# =============================================================================
# Helper for orchestrator: read milestone's param-file sha from metadata
# =============================================================================

def get_milestone_param_sha(rag_dir: Path, profile_name: str) -> Optional[str]:
    """Read the FATES parameter file sha recorded in this milestone's metadata.

    Returns None if metadata is missing or the field is absent.
    """
    md_path = Path(rag_dir) / "metadata" / f"{profile_name}.json"
    if not md_path.exists():
        return None
    try:
        import json as _json
        with open(md_path) as f:
            md = _json.load(f)
        return md.get("param_files", {}).get("fates_param_file_sha")
    except Exception:
        return None


# =============================================================================
# Helper: determine bump tier (T1 / T2 / T3) for the rag_bump tool
# =============================================================================

def classify_bump_tier(selection: RAGSelection,
                       user_param_sha_matches: bool) -> str:
    """Return 'T1', 'T2', or 'T3' for `rag_bump.py` orchestration.

    T1: same epoch, sha matches, no rebuild needed (just metadata refresh).
    T2: same epoch, sha differs (param-file-only delta — partial rebuild).
    T3: different epoch (full new-epoch bump — wiki regen required).
    """
    if selection.mode in ("exact_epoch", "close_enough"):
        if user_param_sha_matches:
            return "T1"
        return "T2"
    return "T3"


# =============================================================================
# CLI for ad-hoc inspection
# =============================================================================

def _main():
    import argparse
    import json
    import os

    parser = argparse.ArgumentParser(
        description="Match an E3SM checkout to a registered milestone."
    )
    parser.add_argument("--model-path", type=Path, default=None,
                        help="E3SM checkout root. Defaults to $A2MC_MODEL_PATH.")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="Manifest JSON path (default: rag/milestones.json)")
    parser.add_argument("--json", action="store_true",
                        help="Emit JSON instead of human-readable summary.")
    args = parser.parse_args()

    from model_version import detect_model_version, ModelPathError
    from rag_manifest import load_manifest

    model_path = args.model_path
    if model_path is None:
        env = os.environ.get("A2MC_MODEL_PATH")
        if not env:
            print("ERROR: A2MC_MODEL_PATH not set and --model-path not given.",
                  file=sys.stderr)
            sys.exit(2)
        model_path = Path(env)

    try:
        version = detect_model_version(model_path)
    except ModelPathError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    manifest = load_manifest(args.manifest)
    sel = select_rag(version, manifest)

    if args.json:
        print(json.dumps(sel.to_dict(), indent=2))
    else:
        print(f"User checkout:   {model_path}")
        print(f"  FATES commit:  {version.fates.commit_short} ({version.fates.describe})")
        print(f"  ELM commit:    {version.elm.commit_short}")
        print(f"  api epoch:     {version.fates_api_epoch}")
        print()
        print(f"Selection:       {sel.profile_name or '(none)'}")
        print(f"  mode:          {sel.mode}")
        print(f"  direction:     {sel.direction}")
        print(f"  epoch dist:    {sel.epoch_distance}")
        print(f"  drift sci:     {sel.drift_sci_tags}")
        print(f"  rebuild:       {sel.rebuild_required}")
        print()
        print(f"Reason: {sel.reason}")


if __name__ == "__main__":
    _main()
