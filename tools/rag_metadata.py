#!/usr/bin/env python3
"""
rag_metadata.py - Read / write per-RAG-profile metadata.

Each registered RAG profile has three on-disk artifacts at canonical paths:
    rag/chroma_db/<profile>/      - ChromaDB persist dir
    rag/graphs/<profile>.json     - NetworkX graph JSON
    rag/metadata/<profile>.json   - this metadata file

The metadata schema is documented in
docs/18_ELM_FATES_Version_Association_Plan.md §4.3.1. Key invariants:

    - Identical metadata block is mirrored into:
        a. The standalone JSON file at rag/metadata/<profile>.json
        b. The graph JSON's top-level `_metadata` key
        c. The ChromaDB collection's `metadata` field (flattened to scalars,
           since ChromaDB collection-metadata only accepts scalar values)

    - profile_name + the four file SHAs are the load-bearing fields. Drift
      detection compares those.

    - elm_commit and fates_commit are the version identity. The selector
      uses fates_api_epoch (parsed from describe) for milestone matching.

Used by:
    - scripts/build_rag_index.py at build / record-only time
    - tools/rag_selector.py to read existing profile metadata
    - orchestrator startup hook to verify alignment

Author: Jing Tao with Claude
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Local imports — `model_version` is a sibling tool.
import sys as _sys
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in _sys.path:
    _sys.path.insert(0, str(_HERE))

from model_version import ELMFATESVersion  # noqa: E402


METADATA_VERSION = 1
A2MC_VERSION_FALLBACK = "v2.89-dev"  # used when CLAUDE.md not introspected


# =============================================================================
# Public API: SHA computation
# =============================================================================

def compute_file_sha(path: Path, *, chunk_size: int = 65536) -> str:
    """Return sha256 hex digest of a file's bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            buf = f.read(chunk_size)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


# =============================================================================
# Public API: metadata construction
# =============================================================================

def build_metadata_from_version(
    version: ELMFATESVersion,
    *,
    profile_name: str,
    a2mc_version: str = A2MC_VERSION_FALLBACK,
    elm_wiki_root: str,
    elm_wiki_subdir: str,
    fates_wiki_root: str,
    fates_wiki_subdir: str,
    fates_param_file: str,
    fates_param_file_format: str,
    output_var_file: str,
    curated_yaml_path: str,
    stats: Optional[Dict[str, int]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> dict:
    """Construct a metadata dict from a detected ELMFATESVersion plus paths.

    All file path arguments are stored as strings (rel-to-repo-root preferred,
    but absolute is also OK). SHAs of `fates_param_file`, `output_var_file`,
    and `curated_yaml_path` are computed automatically.

    Schema follows docs/18 §4.3.1.
    """
    fates_param_sha = _safe_sha(fates_param_file)
    output_var_sha = _safe_sha(output_var_file)
    curated_yaml_sha = _safe_sha(curated_yaml_path)

    md = {
        "metadata_schema_version": METADATA_VERSION,
        "profile_name": profile_name,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "a2mc_version": a2mc_version,
        "model_path": version.model_path,
        "elm": {
            "commit_sha": version.elm.commit_sha,
            "commit_short": version.elm.commit_short,
            "describe": version.elm.describe,
            "wiki_subdir": elm_wiki_subdir,
            "wiki_root": elm_wiki_root,
        },
        "fates": {
            "commit_sha": version.fates.commit_sha,
            "commit_short": version.fates.commit_short,
            "describe": version.fates.describe,
            "nearest_tag": version.fates.nearest_tag,
            "commits_past_tag": version.fates.commits_past_tag,
            "api_epoch": version.fates_api_epoch,
            "wiki_subdir": fates_wiki_subdir,
            "wiki_root": fates_wiki_root,
        },
        "param_files": {
            "fates_param_file": fates_param_file,
            "fates_param_file_format": fates_param_file_format,
            "fates_param_file_sha": fates_param_sha,
            "output_var_file": output_var_file,
            "output_var_file_sha": output_var_sha,
        },
        "curated_yaml": {
            "path": curated_yaml_path,
            "sha": curated_yaml_sha,
        },
        "stats": dict(stats) if stats else {},
    }
    if extra:
        md.update(extra)
    return md


def _safe_sha(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    return compute_file_sha(p)


# =============================================================================
# Public API: read / write
# =============================================================================

def metadata_path(rag_dir: Path, profile_name: str) -> Path:
    """Canonical metadata file path for a profile."""
    return Path(rag_dir) / "metadata" / f"{profile_name}.json"


def graph_path(rag_dir: Path, profile_name: str) -> Path:
    """Canonical graph JSON path for a profile."""
    return Path(rag_dir) / "graphs" / f"{profile_name}.json"


def chroma_dir(rag_dir: Path, profile_name: str) -> Path:
    """Canonical ChromaDB persist dir for a profile."""
    return Path(rag_dir) / "chroma_db" / profile_name


def load_metadata(path: Path) -> dict:
    """Load a metadata JSON. Raises FileNotFoundError if missing."""
    p = Path(path)
    with open(p) as f:
        return json.load(f)


def write_metadata(
    path: Path,
    metadata: dict,
    *,
    chroma_collection: Any = None,
    graph_json_path: Optional[Path] = None,
) -> None:
    """Write the metadata JSON, mirror to graph JSON and ChromaDB collection.

    Parameters
    ----------
    path : Path
        Destination for the standalone metadata JSON.
    metadata : dict
        Metadata block (typically from `build_metadata_from_version`).
    chroma_collection : Any, optional
        A ChromaDB Collection object. If supplied, its metadata is updated
        with the flattened scalar form of `metadata`.
    graph_json_path : Path, optional
        If supplied, the graph JSON is loaded, its top-level `_metadata` key
        is replaced with `metadata`, and the file is rewritten.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(metadata, f, indent=2, default=_json_default)

    if graph_json_path is not None:
        gp = Path(graph_json_path)
        if gp.exists():
            with open(gp) as f:
                graph = json.load(f)
            graph["_metadata"] = metadata
            with open(gp, "w") as f:
                json.dump(graph, f, indent=2, default=_json_default)
        else:
            # Build will write a graph later; nothing to mirror yet.
            pass

    if chroma_collection is not None:
        flat = flatten_metadata_for_chroma(metadata)
        # ChromaDB collection objects expose `modify(metadata=...)` to
        # update collection-level metadata. Best-effort.
        try:
            chroma_collection.modify(metadata=flat)
        except Exception:
            # Older ChromaDB versions may use `update_collection` on the
            # client; the caller can handle that path explicitly.
            pass


def _json_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat(timespec="seconds")
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Not JSON serializable: {type(obj).__name__}")


# =============================================================================
# Public API: ChromaDB metadata flattening
# =============================================================================

def flatten_metadata_for_chroma(metadata: dict) -> Dict[str, Any]:
    """Flatten nested metadata dict into scalar-only key/value pairs.

    ChromaDB collection metadata accepts only `str | int | float | bool` values.
    Nested dicts are joined with `.` separators; lists are joined with `,`.

    Example:
        {"fates": {"commit_short": "e027a40"}, "stats": {"chunk_count": 2707}}
        -> {"fates.commit_short": "e027a40", "stats.chunk_count": 2707}
    """
    flat: Dict[str, Any] = {}
    _flatten_into(flat, "", metadata)
    return flat


def _flatten_into(out: Dict[str, Any], prefix: str, value: Any) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            new_prefix = f"{prefix}.{k}" if prefix else str(k)
            _flatten_into(out, new_prefix, v)
    elif isinstance(value, (list, tuple)):
        # Coerce to comma-separated string of repr-stringified scalars.
        out[prefix] = ",".join(str(x) for x in value)
    elif value is None:
        # Omit None values rather than store as 'None' string. ChromaDB also
        # rejects None.
        return
    elif isinstance(value, (str, int, float, bool)):
        out[prefix] = value
    elif isinstance(value, datetime):
        out[prefix] = value.isoformat(timespec="seconds")
    else:
        out[prefix] = str(value)


# =============================================================================
# CLI for ad-hoc inspection
# =============================================================================

def _main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Inspect or compute SHA for a RAG metadata file."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="Pretty-print a metadata JSON.")
    p_show.add_argument("metadata_path", type=Path)

    p_sha = sub.add_parser("sha", help="Compute sha256 of a file.")
    p_sha.add_argument("file_path", type=Path)

    p_flatten = sub.add_parser(
        "flatten", help="Flatten a metadata JSON for ChromaDB-style storage."
    )
    p_flatten.add_argument("metadata_path", type=Path)

    args = parser.parse_args()

    if args.cmd == "show":
        md = load_metadata(args.metadata_path)
        print(json.dumps(md, indent=2, default=_json_default))
    elif args.cmd == "sha":
        print(compute_file_sha(args.file_path))
    elif args.cmd == "flatten":
        md = load_metadata(args.metadata_path)
        flat = flatten_metadata_for_chroma(md)
        print(json.dumps(flat, indent=2, default=_json_default))


if __name__ == "__main__":
    _main()
