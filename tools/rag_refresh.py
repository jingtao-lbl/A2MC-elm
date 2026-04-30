#!/usr/bin/env python3
"""
rag_refresh.py - Pure-Python T1 metadata refresh for a registered RAG profile.

The orchestrator alignment hook (docs/22 §3.1, Chunk D) calls
`refresh_metadata()` directly when it detects a T1 condition (same epoch,
all SHAs match): we re-stamp `built_at`, recompute file SHAs, and mirror
the metadata into the three on-disk locations:

    - rag/metadata/<profile>.json       (standalone)
    - rag/graphs/<profile>.json         (`_metadata` key)
    - ChromaDB collection.metadata      (flattened scalar form)

What this file deliberately does NOT do:
    - Touch chunk content or chunk-level metadata. Mode-aware tagging
      (applies_in:, kb_source, path-prefix) lives on individual chunks /
      graph nodes and is preserved by leaving them alone.
    - Rebuild the graph or vector store. T2 / T3 do that via
      `build_rag_index.py`; T1 is intentionally a pure-metadata operation.
    - Modify the curated YAML or its frozen snapshot.

Used by:
    - orchestrator.py `_check_rag_alignment()` for in-process T1 refresh.
    - `scripts/build_rag_index.py --record-metadata-only` re-uses the
      same builder via `tools.rag_metadata.build_metadata_from_version`,
      so behavior stays consistent with the CLI path.

Author: Jing Tao with Claude
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from model_version import detect_model_version, ELMFATESVersion  # noqa: E402
from rag_manifest import load_manifest, Milestone  # noqa: E402
from rag_metadata import (  # noqa: E402
    build_metadata_from_version,
    metadata_path,
    graph_path,
    chroma_dir,
    write_metadata,
)


_REPO_ROOT = _HERE.parent


# =============================================================================
# Errors
# =============================================================================

class RefreshError(RuntimeError):
    """Raised when metadata refresh cannot complete (missing milestone,
    unreadable model path, etc.). Caller should surface to the user."""


# =============================================================================
# Public API
# =============================================================================

def refresh_metadata(
    profile_name: str,
    model_path: Path,
    *,
    rag_dir: Optional[Path] = None,
    repo_root: Optional[Path] = None,
) -> dict:
    """Refresh metadata for an existing RAG profile (T1 path).

    Args:
        profile_name: Milestone name registered in `rag/milestones.json`
            (e.g. ``"api-43-1"``).
        model_path: User's E3SM / ELM-FATES checkout root. Used to detect
            FATES + ELM commits + parameter file location.
        rag_dir: Optional override for the RAG storage root (defaults to
            ``$A2MC_RAG_DIR`` or ``<repo>/rag``).
        repo_root: Optional override for the A2MC repo root, used to
            resolve doc paths (defaults to ``<this file>/../..``).

    Returns:
        The metadata dict that was written.

    Raises:
        RefreshError: profile not registered, model path unreadable, or
            metadata file IO fails.
    """
    repo_root = Path(repo_root) if repo_root else _REPO_ROOT
    rag_dir = Path(rag_dir) if rag_dir else _resolve_rag_dir(repo_root)
    model_path = Path(model_path)

    manifest_path = rag_dir / "milestones.json"
    if not manifest_path.exists():
        raise RefreshError(
            f"Milestone manifest not found at {manifest_path}. "
            "Phase 4 version-association migration must complete before "
            "metadata refresh can run."
        )

    manifest = load_manifest(manifest_path)
    milestone = manifest.milestones.get(profile_name)
    if milestone is None:
        raise RefreshError(
            f"Profile {profile_name!r} not registered in {manifest_path}. "
            f"Known profiles: {sorted(manifest.milestones)}."
        )

    try:
        version = detect_model_version(model_path)
    except Exception as e:
        raise RefreshError(
            f"Cannot detect model version from {model_path}: {e}"
        ) from e

    # Resolve path inputs the metadata builder needs. `build_metadata_from_version`
    # computes SHAs internally; we just supply absolute file paths.
    fates_param_file = _resolve_fates_param_file(model_path, milestone)
    output_var_file = _resolve_output_cdl(repo_root, milestone, kind="fates")
    elm_output_var_file = _resolve_output_cdl(repo_root, milestone, kind="elm")
    curated_yaml_path = _resolve_curated_yaml(repo_root, milestone, profile_name)

    # Stats: read whatever already exists on disk. We don't rebuild.
    stats = _read_existing_stats(rag_dir, profile_name)

    md = build_metadata_from_version(
        version,
        profile_name=profile_name,
        elm_wiki_root=str(repo_root / "docs" / "elm-knowledge-base"),
        elm_wiki_subdir=milestone.elm_wiki_subdir or "",
        fates_wiki_root=str(repo_root / "docs" / "fates-knowledge-base"),
        fates_wiki_subdir=milestone.fates_wiki_subdir or "",
        fates_param_file=fates_param_file,
        fates_param_file_format=milestone.fates_param_file_format or "json",
        output_var_file=output_var_file,
        elm_output_var_file=elm_output_var_file,
        curated_yaml_path=curated_yaml_path,
        stats=stats,
    )

    md_path = metadata_path(rag_dir, profile_name)
    g_path = graph_path(rag_dir, profile_name)
    chroma_collection = _load_chroma_collection_or_none(rag_dir, profile_name)

    write_metadata(
        md_path,
        md,
        chroma_collection=chroma_collection,
        graph_json_path=g_path,
    )

    return md


# =============================================================================
# Path helpers (lightweight; full resolution lives in build_rag_index.py)
# =============================================================================

def _resolve_rag_dir(repo_root: Path) -> Path:
    env = os.environ.get("A2MC_RAG_DIR")
    if env:
        return Path(env)
    return repo_root / "rag"


def _resolve_fates_param_file(model_path: Path, milestone: Milestone) -> str:
    """User's actual FATES parameter file — derived from the checkout, not
    the milestone (we want the SHA the user is running with, which may
    drift even within an epoch; that's exactly the signal T1/T2 split on)."""
    fates_root = (
        model_path / "components" / "elm" / "src" / "external_models" / "fates"
    )
    fmt = milestone.fates_param_file_format or "json"
    candidate = fates_root / "parameter_files" / f"fates_params_default.{fmt}"
    return str(candidate)


def _resolve_output_cdl(repo_root: Path, milestone: Milestone,
                       *, kind: str) -> Optional[str]:
    """Resolve FATES or ELM output CDL filename from milestone, return
    None if the milestone doesn't register one (e.g. legacy api-31-0 has
    no separate ELM CDL)."""
    if kind == "fates":
        fname = milestone.fates_output_cdl
    elif kind == "elm":
        fname = milestone.elm_output_cdl
    else:
        raise ValueError(f"kind must be 'fates' or 'elm', got {kind!r}")
    if not fname:
        return None
    return str(repo_root / "docs" / "fates-knowledge-base" / fname)


def _resolve_curated_yaml(repo_root: Path, milestone: Milestone,
                         profile_name: str) -> str:
    """Resolve the per-milestone curated YAML snapshot."""
    if milestone.curated_yaml_path:
        return str(repo_root / milestone.curated_yaml_path)
    # Fallback: conventional path used when the milestone doesn't pin one.
    return str(
        repo_root / "rag" / "data" / f"curated_relationships_{profile_name}.yaml"
    )


# =============================================================================
# Stats + chroma collection lookup (best-effort; refresh works without them)
# =============================================================================

def _read_existing_stats(rag_dir: Path, profile_name: str) -> dict:
    """Read chunk count + graph node/edge counts from existing artifacts.

    Returns whatever can be read; missing artifacts produce zero counts
    rather than errors. T1 by definition runs against an existing profile,
    so all three artifacts should be present, but we are defensive.
    """
    stats: dict = {"chunk_count": 0, "graph_nodes": 0, "graph_edges": 0}

    g = graph_path(rag_dir, profile_name)
    if g.exists():
        try:
            with open(g) as f:
                graph = json.load(f)
            stats["graph_nodes"] = len(graph.get("nodes", []))
            stats["graph_edges"] = len(graph.get("links", graph.get("edges", [])))
        except Exception:
            pass

    cd = chroma_dir(rag_dir, profile_name)
    if cd.exists():
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(cd))
            for coll in client.list_collections():
                stats["chunk_count"] += coll.count()
        except Exception:
            pass

    return stats


def _load_chroma_collection_or_none(rag_dir: Path, profile_name: str):
    """Return the primary ChromaDB collection so write_metadata() can
    mirror the flattened metadata into it. None if unavailable."""
    cd = chroma_dir(rag_dir, profile_name)
    if not cd.exists():
        return None
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(cd))
        colls = client.list_collections()
        if not colls:
            return None
        return colls[0]
    except Exception:
        return None
