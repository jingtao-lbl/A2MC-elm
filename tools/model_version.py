#!/usr/bin/env python3
"""
model_version.py - Detect ELM + FATES git state from an E3SM checkout.

Reads commit SHAs and `git describe --tags` output for the two components
A2MC's RAG infrastructure cares about: ELM (`components/elm/`) and FATES
(`components/elm/src/external_models/fates/`, nested under ELM).

Used by:
    - tools/rag_selector.py to match user's checkout to a registered milestone
    - scripts/build_rag_index.py to write metadata at build time
    - orchestrator startup hook to verify alignment with active RAG profile

The FATES commit pinned in E3SM is often older than `NGEET/fates:main`. Always
read the pinned commit; never assume E3SM is at the latest FATES.

Author: Jing Tao with Claude
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# =============================================================================
# Public dataclasses
# =============================================================================

@dataclass
class ComponentVersion:
    """Git state for one source-tree component (ELM or FATES)."""
    commit_sha: str                          # full 40-char SHA
    commit_short: str                        # 7-char short SHA
    describe: Optional[str] = None           # `git describe --tags --long` output
    nearest_tag: Optional[str] = None        # tag part of describe (e.g., 'sci.1.91.1_api.43.1.0')
    commits_past_tag: Optional[int] = None   # commits past nearest tag

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ELMFATESVersion:
    """Combined ELM + FATES git state at a moment in time."""
    elm: ComponentVersion
    fates: ComponentVersion
    model_path: str                          # absolute path used for detection
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "elm": self.elm.to_dict(),
            "fates": self.fates.to_dict(),
            "model_path": self.model_path,
            "detected_at": self.detected_at.isoformat(timespec="seconds"),
        }

    @property
    def fates_api_epoch(self) -> Optional[str]:
        """Return the FATES api.X.Y epoch (e.g., '43.1') or None.

        Parses the FATES `describe` field looking for `api.X.Y`. Returns the
        'X.Y' string. Used by the milestone selector for epoch matching.
        """
        return parse_api_epoch(self.fates.describe or self.fates.nearest_tag or "")

    @property
    def fates_sci_tag(self) -> Optional[str]:
        """Return the full FATES sci.X.Y.Z tag (e.g., 'sci.1.91.1_api.43.1.0')."""
        return self.fates.nearest_tag


# =============================================================================
# Exceptions
# =============================================================================

class ModelPathError(RuntimeError):
    """Raised when A2MC_MODEL_PATH is invalid or not an E3SM checkout."""
    pass


# =============================================================================
# Helpers
# =============================================================================

# Match 'api.NN.M' anywhere in the describe / tag string.
# Examples that should match:
#   sci.1.91.1_api.43.1.0
#   sci.1.91.1_api.43.1.0-0-ge027a403
#   sci.1.68.2_api.31.0.0-3-ge85d9977
_API_EPOCH_RE = re.compile(r"api\.(\d+)\.(\d+)")


def parse_api_epoch(text: str) -> Optional[str]:
    """Extract 'X.Y' from a FATES describe / tag string. Returns None on miss."""
    if not text:
        return None
    m = _API_EPOCH_RE.search(text)
    if not m:
        return None
    return f"{m.group(1)}.{m.group(2)}"


def parse_describe(describe: str) -> tuple[Optional[str], Optional[int]]:
    """Parse `git describe --tags --long` output.

    Format: `<tag>-<commits_past>-g<short_sha>` (e.g., 'sci.1.68.2_api.31.0.0-3-ge85d9977').
    Returns (nearest_tag, commits_past_tag), or (None, None) if not parseable.
    """
    if not describe:
        return None, None
    # Last two `-` delimited fields are `<commits>-g<sha>`. Everything before
    # is the tag (which itself contains dots/dashes).
    m = re.match(r"^(.+)-(\d+)-g[0-9a-f]{4,}$", describe.strip())
    if not m:
        # Some describes have no `-N-gSHA` suffix when at exact tag with --long off.
        # With --long it should always be present, but handle defensively.
        return describe.strip() or None, None
    return m.group(1), int(m.group(2))


def _git(args: list[str], cwd: Path) -> str:
    """Run a git command in `cwd`; return stripped stdout. Raise on failure."""
    result = subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed in {cwd}: "
            f"exit={result.returncode}, stderr={result.stderr.strip()}"
        )
    return result.stdout.strip()


def _git_optional(args: list[str], cwd: Path) -> Optional[str]:
    """Like `_git` but returns None on failure instead of raising."""
    try:
        return _git(args, cwd)
    except RuntimeError:
        return None


# =============================================================================
# Component detection
# =============================================================================

def _detect_component(component_path: Path, label: str) -> ComponentVersion:
    """Read commit + describe for one component directory.

    Works for both ELM (a subdirectory of the E3SM repo, no own `.git/`) and
    FATES (a submodule with its own `.git` file). `git rev-parse HEAD` walks
    upward automatically to find the nearest repo, so we don't pre-check for
    `.git/`.

    Raises ModelPathError if the directory exists but `git rev-parse HEAD`
    fails (most often: FATES submodule registered but not initialized).
    """
    if not component_path.exists():
        raise ModelPathError(
            f"{label} directory missing: {component_path}"
        )

    try:
        sha = _git(["rev-parse", "HEAD"], component_path)
    except RuntimeError as e:
        raise ModelPathError(
            f"{label} `git rev-parse HEAD` failed at {component_path}: {e}. "
            f"If this is a FATES submodule, run `git submodule update --init` "
            f"in the E3SM checkout."
        ) from e

    # `git describe` is best-effort; some checkouts have no reachable tag.
    describe = _git_optional(
        ["describe", "--tags", "--long", sha],
        component_path,
    )
    nearest_tag, commits_past = parse_describe(describe) if describe else (None, None)

    return ComponentVersion(
        commit_sha=sha,
        commit_short=sha[:7],
        describe=describe,
        nearest_tag=nearest_tag,
        commits_past_tag=commits_past,
    )


# =============================================================================
# Public API
# =============================================================================

def detect_model_version(model_path: Path) -> ELMFATESVersion:
    """Read ELM + FATES git state from an E3SM checkout.

    Parameters
    ----------
    model_path : Path
        Absolute path to the E3SM repo root. Must contain `components/elm/`
        and `components/elm/src/external_models/fates/`.

    Returns
    -------
    ELMFATESVersion

    Raises
    ------
    ModelPathError
        - model_path doesn't exist
        - not an E3SM checkout (no `components/elm/`)
        - FATES submodule not initialized
        - either component fails `git rev-parse HEAD`

    Notes
    -----
    Both ELM and FATES commits are required for a valid version. FATES is
    nested under ELM at `components/elm/src/external_models/fates/`, NOT at
    the top-level `components/fates/`.

    `git describe` failures degrade gracefully: the component's `describe`,
    `nearest_tag`, and `commits_past_tag` fields become None. The commit SHA
    is the load-bearing identifier; describe is for human-readable reporting.
    """
    model_path = Path(model_path).resolve()

    if not model_path.exists():
        raise ModelPathError(
            f"A2MC_MODEL_PATH does not exist: {model_path}"
        )

    elm_path = model_path / "components" / "elm"
    if not elm_path.exists():
        raise ModelPathError(
            f"Not an E3SM checkout (components/elm/ not found): {model_path}"
        )

    fates_path = elm_path / "src" / "external_models" / "fates"
    # An empty FATES dir means the submodule is registered but not init'd.
    fates_initialized = fates_path.exists() and any(fates_path.iterdir())
    if not fates_initialized:
        raise ModelPathError(
            f"FATES submodule not initialized at {fates_path}. "
            f"Run `git submodule update --init` in the E3SM checkout."
        )

    elm = _detect_component(elm_path, "ELM")
    fates = _detect_component(fates_path, "FATES")

    return ELMFATESVersion(
        elm=elm,
        fates=fates,
        model_path=str(model_path),
    )


# =============================================================================
# CLI for ad-hoc inspection
# =============================================================================

def _main():
    import argparse
    import json
    import os
    import sys

    parser = argparse.ArgumentParser(
        description="Detect ELM + FATES git state from an E3SM checkout."
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=None,
        help="Path to E3SM repo root. Defaults to $A2MC_MODEL_PATH.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable summary.",
    )
    args = parser.parse_args()

    model_path = args.model_path
    if model_path is None:
        env = os.environ.get("A2MC_MODEL_PATH")
        if not env:
            print(
                "ERROR: A2MC_MODEL_PATH not set and --model-path not given.",
                file=sys.stderr,
            )
            sys.exit(2)
        model_path = Path(env)

    try:
        version = detect_model_version(model_path)
    except ModelPathError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(version.to_dict(), indent=2))
    else:
        print(f"Model path:   {version.model_path}")
        print(f"Detected at:  {version.detected_at.isoformat(timespec='seconds')}")
        print()
        print(f"ELM:")
        print(f"  commit:     {version.elm.commit_sha}")
        print(f"  describe:   {version.elm.describe or '(none)'}")
        print(f"  short:      {version.elm.commit_short}")
        print()
        print(f"FATES:")
        print(f"  commit:     {version.fates.commit_sha}")
        print(f"  describe:   {version.fates.describe or '(none)'}")
        print(f"  short:      {version.fates.commit_short}")
        print(f"  nearest tag:{version.fates.nearest_tag or '(none)'}")
        print(f"  api epoch:  {version.fates_api_epoch or '(none)'}")
        print(f"  past tag:   {version.fates.commits_past_tag if version.fates.commits_past_tag is not None else '(none)'}")


if __name__ == "__main__":
    _main()
