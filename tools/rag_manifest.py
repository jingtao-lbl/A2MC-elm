#!/usr/bin/env python3
"""
rag_manifest.py - Milestone registry CRUD.

Each registered RAG milestone is recorded in `rag/milestones.json` with:
    - profile_name (key, e.g., 'api-43-1')
    - description
    - fates_api_epoch (e.g., '43.1')
    - fates_tag_built (e.g., 'sci.1.91.1_api.43.1.0')
    - fates_commit_built (40-char SHA)
    - fates_param_file_format ('cdl' or 'json')
    - elm_commit_built
    - elm_wiki_subdir, fates_wiki_subdir
    - covers_sci_tags (list of FATES tags within this api epoch)
    - canonical (bool, true for the default profile)
    - legacy (bool, true for backward-compatibility profiles)
    - available_locally (bool, true if rag/chroma_db/<profile>/ exists)
    - published_at (date)

Schema documented in `docs/18_ELM_FATES_Version_Association_Plan.md` §4.3.2.

Used by:
    - scripts/build_rag_index.py to register a built profile as a milestone
    - tools/rag_selector.py to find the best milestone for a user's checkout
    - scripts/rag_list.py to display milestones
    - scripts/rag_match.py to drive the bump advisor

Author: Jing Tao with Claude
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


MANIFEST_VERSION = 1
DEFAULT_MANIFEST_PATH = "rag/milestones.json"


# =============================================================================
# Public dataclasses (typed view of the JSON)
# =============================================================================

@dataclass
class Milestone:
    """One registered milestone — typed view of an entry in rag/milestones.json."""
    profile_name: str
    description: str = ""
    fates_api_epoch: str = ""             # e.g., '43.1'
    fates_tag_built: Optional[str] = None  # e.g., 'sci.1.91.1_api.43.1.0'
    fates_commit_built: Optional[str] = None  # 40-char SHA
    fates_param_file_format: str = "cdl"  # 'cdl' or 'json'
    elm_commit_built: Optional[str] = None
    elm_wiki_subdir: Optional[str] = None
    fates_wiki_subdir: Optional[str] = None
    covers_sci_tags: List[str] = field(default_factory=list)
    canonical: bool = False
    legacy: bool = False
    available_locally: bool = False
    published_at: Optional[str] = None    # ISO date or None
    curated_yaml_path: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "fates_api_epoch": self.fates_api_epoch,
            "fates_tag_built": self.fates_tag_built,
            "fates_commit_built": self.fates_commit_built,
            "fates_param_file_format": self.fates_param_file_format,
            "elm_commit_built": self.elm_commit_built,
            "elm_wiki_subdir": self.elm_wiki_subdir,
            "fates_wiki_subdir": self.fates_wiki_subdir,
            "covers_sci_tags": list(self.covers_sci_tags),
            "canonical": self.canonical,
            "legacy": self.legacy,
            "available_locally": self.available_locally,
            "published_at": self.published_at,
            "curated_yaml_path": self.curated_yaml_path,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, profile_name: str, body: dict) -> "Milestone":
        return cls(
            profile_name=profile_name,
            description=body.get("description", ""),
            fates_api_epoch=body.get("fates_api_epoch", ""),
            fates_tag_built=body.get("fates_tag_built"),
            fates_commit_built=body.get("fates_commit_built"),
            fates_param_file_format=body.get("fates_param_file_format", "cdl"),
            elm_commit_built=body.get("elm_commit_built"),
            elm_wiki_subdir=body.get("elm_wiki_subdir"),
            fates_wiki_subdir=body.get("fates_wiki_subdir"),
            covers_sci_tags=list(body.get("covers_sci_tags", [])),
            canonical=bool(body.get("canonical", False)),
            legacy=bool(body.get("legacy", False)),
            available_locally=bool(body.get("available_locally", False)),
            published_at=body.get("published_at"),
            curated_yaml_path=body.get("curated_yaml_path"),
            notes=body.get("notes", ""),
        )


@dataclass
class Manifest:
    """In-memory mirror of `rag/milestones.json`."""
    version: int = MANIFEST_VERSION
    updated_at: str = ""
    milestones: Dict[str, Milestone] = field(default_factory=dict)
    path: Optional[Path] = None  # source file, set on load

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "updated_at": self.updated_at,
            "milestones": {n: m.to_dict() for n, m in self.milestones.items()},
        }

    def list(self) -> List[Milestone]:
        return list(self.milestones.values())

    def get(self, profile_name: str) -> Optional[Milestone]:
        return self.milestones.get(profile_name)

    def canonical_profile(self) -> Optional[Milestone]:
        for m in self.milestones.values():
            if m.canonical:
                return m
        return None


# =============================================================================
# Public API: load / save
# =============================================================================

def load_manifest(path: Path = None) -> Manifest:
    """Load `rag/milestones.json`. Returns empty Manifest if file is absent."""
    p = Path(path) if path else Path(DEFAULT_MANIFEST_PATH)
    if not p.exists():
        m = Manifest(version=MANIFEST_VERSION,
                     updated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        m.path = p
        return m
    with open(p) as f:
        data = json.load(f)
    m = Manifest(
        version=int(data.get("version", MANIFEST_VERSION)),
        updated_at=data.get("updated_at", ""),
        milestones={
            name: Milestone.from_dict(name, body)
            for name, body in data.get("milestones", {}).items()
        },
    )
    m.path = p
    return m


def save_manifest(manifest: Manifest, path: Path = None) -> None:
    """Write the manifest. Path falls back to `manifest.path` then DEFAULT_MANIFEST_PATH."""
    p = Path(path) if path else (manifest.path or Path(DEFAULT_MANIFEST_PATH))
    manifest.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(manifest.to_dict(), f, indent=2)


# =============================================================================
# Public API: CRUD
# =============================================================================

def add_milestone(manifest: Manifest, milestone: Milestone, *,
                  overwrite: bool = False) -> None:
    """Add or update a milestone entry. Raises if exists and not overwrite."""
    if milestone.profile_name in manifest.milestones and not overwrite:
        raise ValueError(
            f"Milestone '{milestone.profile_name}' already exists. "
            f"Pass overwrite=True to replace it."
        )
    manifest.milestones[milestone.profile_name] = milestone


def remove_milestone(manifest: Manifest, profile_name: str) -> bool:
    """Remove a milestone. Returns True if removed, False if not present."""
    if profile_name in manifest.milestones:
        del manifest.milestones[profile_name]
        return True
    return False


def mark_available_locally(manifest: Manifest, profile_name: str,
                           rag_dir: Path) -> bool:
    """Set `available_locally` based on whether the chroma_db dir exists."""
    m = manifest.get(profile_name)
    if m is None:
        return False
    chroma_path = Path(rag_dir) / "chroma_db" / profile_name
    m.available_locally = chroma_path.exists() and any(chroma_path.iterdir())
    return True


# =============================================================================
# Public API: FATES sci-tag enumeration for an api epoch
# =============================================================================

_SCI_TAG_RE = re.compile(r"refs/tags/(sci\.\d+\.\d+\.\d+_api\.\d+\.\d+\.\d+)")


def list_sci_tags_for_epoch(fates_repo_path: Path, api_epoch: str) -> List[str]:
    """Return all sci.X.Y.Z tags whose api.MM.NN matches `api_epoch`.

    Args:
        fates_repo_path: Path to a FATES git checkout (or any clone with the
            full tag history).
        api_epoch: 'X.Y' string, e.g., '43.1' or '31.0'.

    Returns:
        Sorted list of matching tag names (e.g., ['sci.1.91.0_api.43.1.0',
        'sci.1.91.1_api.43.1.0', ...]). Empty if git fails or no match.
    """
    fates_repo_path = Path(fates_repo_path)
    if not fates_repo_path.exists():
        return []
    try:
        out = subprocess.run(
            ["git", "ls-remote", "--tags", "."],
            cwd=str(fates_repo_path),
            capture_output=True, text=True, check=False,
        )
    except Exception:
        return []
    if out.returncode != 0:
        # Fall back to local tag enumeration
        try:
            out = subprocess.run(
                ["git", "tag", "-l"],
                cwd=str(fates_repo_path),
                capture_output=True, text=True, check=False,
            )
        except Exception:
            return []
        if out.returncode != 0:
            return []
        local_tags = [t.strip() for t in out.stdout.splitlines() if t.strip()]
        suffix = f"_api.{api_epoch}.0"
        return sorted(
            [t for t in local_tags if t.startswith("sci.") and suffix in t]
        )

    tags = []
    suffix = f"_api.{api_epoch}.0"
    for line in out.stdout.splitlines():
        m = _SCI_TAG_RE.search(line)
        if m:
            tag = m.group(1)
            if suffix in tag:
                tags.append(tag)
    return sorted(set(tags))


# =============================================================================
# CLI for ad-hoc inspection
# =============================================================================

def _main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Inspect or modify the RAG milestone registry."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="Pretty-print the manifest.")
    p_show.add_argument("--path", default=None, type=Path,
                        help=f"Manifest JSON path (default: {DEFAULT_MANIFEST_PATH})")

    p_list = sub.add_parser("list", help="List milestone names.")
    p_list.add_argument("--path", default=None, type=Path)

    p_tags = sub.add_parser(
        "list-sci-tags", help="List sci tags for a FATES api epoch."
    )
    p_tags.add_argument("--repo", required=True, type=Path,
                        help="FATES git repo path.")
    p_tags.add_argument("--epoch", required=True,
                        help="API epoch (e.g., '43.1').")

    args = parser.parse_args()

    if args.cmd == "show":
        m = load_manifest(args.path)
        print(json.dumps(m.to_dict(), indent=2))
    elif args.cmd == "list":
        m = load_manifest(args.path)
        for name, ms in m.milestones.items():
            badges = []
            if ms.canonical:
                badges.append("canonical")
            if ms.legacy:
                badges.append("legacy")
            if ms.available_locally:
                badges.append("local")
            tag = ms.fates_tag_built or ""
            print(f"  {name:15s}  {tag:30s}  [{', '.join(badges)}]")
    elif args.cmd == "list-sci-tags":
        tags = list_sci_tags_for_epoch(args.repo, args.epoch)
        for t in tags:
            print(t)


if __name__ == "__main__":
    _main()
