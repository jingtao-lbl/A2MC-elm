#!/Library/Frameworks/Python.framework/Versions/3.10/bin/python3
"""
rag_match.py - Match a user's E3SM checkout to a milestone, with bump advisor.

Runs the selector against the user's checkout, walks `git log` between the
matched milestone's commit and the user's commit (forward or backward), and
shows a parameter-file delta. Output is a recommendation: use as-is, refresh
metadata, partial rebuild (T2), or full new-epoch bump (T3).

This is the diagnostic surface that the user inspects BEFORE deciding to run
`scripts/rag_bump.py`.

Usage:
    python scripts/rag_match.py
    python scripts/rag_match.py --model-path /path/to/E3SM
    python scripts/rag_match.py --json

Author: Jing Tao with Claude
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "tools"))

from model_version import detect_model_version, ModelPathError  # noqa: E402
from rag_manifest import load_manifest  # noqa: E402
from rag_metadata import compute_file_sha  # noqa: E402
from rag_selector import (  # noqa: E402
    select_rag, classify_bump_tier, get_milestone_param_sha,
)


# =============================================================================
# Helpers
# =============================================================================

def _git_log(repo_path: Path, commit_a: str, commit_b: str,
             max_commits: int = 50) -> list[str]:
    """Return `git log --oneline a..b` lines (capped at max_commits)."""
    try:
        out = subprocess.run(
            ["git", "log", "--oneline", f"-{max_commits}", f"{commit_a}..{commit_b}"],
            cwd=str(repo_path), capture_output=True, text=True, check=False,
        )
        if out.returncode != 0:
            return []
        return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
    except Exception:
        return []


def _git_diff_files(repo_path: Path, commit_a: str, commit_b: str,
                    suffix: str = ".F90") -> list[str]:
    """Return list of files matching `suffix` that changed between a and b."""
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", f"{commit_a}..{commit_b}"],
            cwd=str(repo_path), capture_output=True, text=True, check=False,
        )
        if out.returncode != 0:
            return []
        return [
            ln.strip() for ln in out.stdout.splitlines()
            if ln.strip().endswith(suffix)
        ]
    except Exception:
        return []


def _resolve_user_param_file(model_path: Path, fates_param_file_format: str) -> Path:
    """Return the path to the FATES parameter file inside the user's checkout."""
    fates_root = model_path / "components" / "elm" / "src" / "external_models" / "fates"
    if fates_param_file_format == "json":
        candidate = fates_root / "parameter_files" / "fates_params_default.json"
    else:
        candidate = fates_root / "parameter_files" / "fates_params_default.cdl"
    return candidate


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Match a user's E3SM checkout to a registered milestone."
    )
    parser.add_argument("--model-path", type=Path, default=None,
                        help="E3SM checkout root. Defaults to $A2MC_MODEL_PATH.")
    parser.add_argument("--manifest", type=Path,
                        default=_REPO_ROOT / "rag" / "milestones.json",
                        help="Manifest JSON path")
    parser.add_argument("--rag-dir", type=Path,
                        default=os.environ.get("A2MC_RAG_DIR") or str(_REPO_ROOT / "rag"),
                        help="RAG storage root")
    parser.add_argument("--max-commits", type=int, default=20,
                        help="Cap git-log output (default: 20)")
    parser.add_argument("--json", action="store_true",
                        help="Emit machine-readable JSON instead of summary.")
    args = parser.parse_args()

    # 1. Detect user's version
    model_path = args.model_path
    if model_path is None:
        env = os.environ.get("A2MC_MODEL_PATH")
        if not env:
            print("ERROR: A2MC_MODEL_PATH not set and --model-path not given.",
                  file=sys.stderr)
            sys.exit(2)
        model_path = Path(env)
    model_path = model_path.resolve()

    try:
        version = detect_model_version(model_path)
    except ModelPathError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Run selector
    manifest = load_manifest(args.manifest)
    sel = select_rag(version, manifest)

    # 3. Param-file sha drift check.
    #
    # The metadata records the sha of the docs/-staged FATES parameter file
    # used at index-build time. The user's source-tree file lives at a
    # different path inside their E3SM checkout. These two are different
    # artifacts even when content is identical (the staged copy may have
    # NetCDF metadata header differences from extraction). For T1/T2
    # tier classification we therefore default to "matches" when the user
    # is at the exact milestone commit. A future enhancement: also record
    # the source-tree sha at build time and compare against that.
    user_param_sha = None
    user_param_file = None
    user_param_sha_matches = True  # default optimistic; only flip on real drift signal
    if sel.milestone:
        user_param_file = _resolve_user_param_file(
            model_path, sel.milestone.fates_param_file_format
        )
        if user_param_file.exists():
            user_param_sha = compute_file_sha(user_param_file)
        # Real drift signal: user is at a DIFFERENT FATES commit than the
        # milestone was built against. Same commit -> param file content is
        # identical to what the milestone was built from, regardless of the
        # path we hashed.
        if version.fates.commit_sha != sel.milestone.fates_commit_built:
            user_param_sha_matches = False
            sel.param_file_changed = True
            if sel.mode in ("exact_epoch", "close_enough"):
                sel.rebuild_required = True

    tier = classify_bump_tier(sel, user_param_sha_matches)

    # 4. Walk git history between user and milestone commit (FATES only — ELM
    #    moves much faster and the diff is rarely informative).
    fates_repo = model_path / "components" / "elm" / "src" / "external_models" / "fates"
    fates_log_forward = []
    fates_log_backward = []
    fates_changed_F90 = []
    if sel.milestone and sel.milestone.fates_commit_built:
        ms_commit = sel.milestone.fates_commit_built
        user_commit = version.fates.commit_sha
        if ms_commit != user_commit:
            # forward = milestone..user (commits user has past milestone)
            fates_log_forward = _git_log(
                fates_repo, ms_commit, user_commit, max_commits=args.max_commits
            )
            # backward = user..milestone (commits milestone has past user)
            fates_log_backward = _git_log(
                fates_repo, user_commit, ms_commit, max_commits=args.max_commits
            )
            fates_changed_F90 = _git_diff_files(
                fates_repo, ms_commit, user_commit, suffix=".F90"
            )

    # 5. Build recommendation
    if tier == "T1":
        recommendation = (
            f"T1 (metadata refresh only). Use milestone '{sel.profile_name}' "
            f"as-is. If you want to update its metadata to record this run, "
            f"run:\n"
            f"  python scripts/build_rag_index.py --record-metadata-only "
            f"--profile {sel.profile_name}"
        )
    elif tier == "T2":
        recommendation = (
            f"T2 (param-only delta). Same epoch as milestone '{sel.profile_name}', "
            f"but the FATES parameter file sha differs. Recommend partial "
            f"rebuild:\n"
            f"  python scripts/rag_bump.py --target-milestone {sel.profile_name} "
            f"--mode prompt-pack    # or --mode api / --mode auto"
        )
    else:  # T3
        target = (sel.milestone.profile_name + "-???") if sel.milestone else "<new>"
        proposed = f"api-{version.fates_api_epoch.replace('.', '-')}"
        recommendation = (
            f"T3 (new api epoch). User's FATES (epoch {version.fates_api_epoch}) "
            f"differs from nearest milestone '{sel.profile_name}' (epoch "
            f"{sel.milestone_api_epoch}). A full wiki regen + rebuild is needed.\n"
            f"  python scripts/rag_bump.py --target-milestone {proposed} "
            f"--mode prompt-pack --basis {sel.profile_name}\n"
            f"(Use --mode api or --mode auto if you have AI credentials.)"
        )

    # 6. Output
    result = {
        "user": {
            "model_path": str(model_path),
            "fates_commit": version.fates.commit_sha,
            "fates_commit_short": version.fates.commit_short,
            "fates_describe": version.fates.describe,
            "fates_api_epoch": version.fates_api_epoch,
            "elm_commit_short": version.elm.commit_short,
            "elm_describe": version.elm.describe,
        },
        "selection": sel.to_dict(),
        "param_file": {
            "user_path": str(user_param_file) if user_param_file else None,
            "user_sha": user_param_sha,
            "milestone_sha": (
                get_milestone_param_sha(args.rag_dir, sel.profile_name)
                if sel.profile_name else None
            ),
            "matches": user_param_sha_matches,
        },
        "fates_history": {
            "milestone_commit": (
                sel.milestone.fates_commit_built if sel.milestone else None
            ),
            "user_commit": version.fates.commit_sha,
            "forward_log": fates_log_forward,
            "backward_log": fates_log_backward,
            "changed_F90_files": fates_changed_F90,
        },
        "tier": tier,
        "recommendation": recommendation,
    }

    if args.json:
        print(json.dumps(result, indent=2))
        return

    # Human-readable
    print(f"User checkout:      {model_path}")
    print(f"  FATES:            {version.fates.commit_short}  ({version.fates.describe})")
    print(f"  ELM:              {version.elm.commit_short}  ({version.elm.describe or 'no describe'})")
    print(f"  api epoch:        {version.fates_api_epoch}")
    print()
    print(f"Selection:          {sel.profile_name or '(none)'}")
    print(f"  mode:             {sel.mode}")
    print(f"  direction:        {sel.direction}")
    print(f"  epoch distance:   {sel.epoch_distance}")
    print(f"  param-file match: {user_param_sha_matches}")
    print(f"  bump tier:        {tier}")
    print()
    if fates_log_forward:
        print(f"FATES commits user has past milestone (forward, {len(fates_log_forward)} shown):")
        for ln in fates_log_forward[:10]:
            print(f"  {ln}")
        if len(fates_log_forward) > 10:
            print(f"  ... ({len(fates_log_forward) - 10} more)")
        print()
    if fates_log_backward:
        print(f"FATES commits milestone has past user (backward, {len(fates_log_backward)} shown):")
        for ln in fates_log_backward[:10]:
            print(f"  {ln}")
        if len(fates_log_backward) > 10:
            print(f"  ... ({len(fates_log_backward) - 10} more)")
        print()
    if fates_changed_F90:
        print(f"FATES .F90 files changed between milestone and user: {len(fates_changed_F90)}")
        for f in fates_changed_F90[:10]:
            print(f"  {f}")
        if len(fates_changed_F90) > 10:
            print(f"  ... ({len(fates_changed_F90) - 10} more)")
        print()
    print("--- Recommendation ---")
    print(recommendation)


if __name__ == "__main__":
    main()
