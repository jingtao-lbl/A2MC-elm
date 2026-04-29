#!/Library/Frameworks/Python.framework/Versions/3.10/bin/python3
"""
Build RAG and GraphRAG indexes for the A2MC version-association infrastructure.

Per-profile layout (Phase 4):
    rag/chroma_db/<profile>/        ChromaDB persist dir
    rag/graphs/<profile>.json       Knowledge graph (NetworkX node-link JSON)
    rag/metadata/<profile>.json     Profile metadata (per docs/18 §4.3.1)

The active profile is determined from A2MC env vars (A2MC_RAG_DIR,
A2MC_RAG_ACTIVE) and can be overridden with --profile.

Build flow:
    1. Auto-detect ELM + FATES commits from $A2MC_MODEL_PATH
       (or use --model-path override)
    2. Resolve wiki subdirs (commit-pinned) and parameter file
    3. Build vector index (ChromaDB) + knowledge graph (NetworkX)
    4. Write metadata JSON + embed `_metadata` block in graph JSON
    5. Optionally update ChromaDB collection metadata

Usage:
    # Full build, profile auto-derived from active env / FATES api epoch
    python scripts/build_rag_index.py --rebuild

    # Explicit profile + commit-pinned wiki subdirs
    python scripts/build_rag_index.py --rebuild \\
        --profile api-43-1 \\
        --fates-wiki-subdir fates-codebase-wiki-e027a40 \\
        --elm-wiki-subdir   elm-codebase-wiki-d40b843

    # Refresh metadata only (no rebuild) — used after on-disk migration
    python scripts/build_rag_index.py --record-metadata-only --profile api-43-1

    # Build subset
    python scripts/build_rag_index.py --rebuild --graph-only

Author: Jing Tao with Claude
"""

import argparse
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from rag.retriever import FATESRetriever, create_retriever
from rag.graph_builder import (
    build_fates_graph, save_graph, load_graph, load_graph_metadata,
    DEFAULT_PARAM_CDL_PATH, DEFAULT_OUTPUT_CDL_PATH,
)
from rag.hybrid_retriever import HybridRetriever
from rag.loader import load_parameter_descriptions

# tools/ modules need explicit sys.path entry
sys.path.insert(0, str(_REPO_ROOT / "tools"))
from model_version import detect_model_version, ELMFATESVersion, ModelPathError
from rag_metadata import (
    build_metadata_from_version, write_metadata, load_metadata,
    metadata_path, graph_path, chroma_dir,
)


# =============================================================================
# Path resolution
# =============================================================================

def resolve_rag_dir() -> Path:
    """Return $A2MC_RAG_DIR or default to <repo>/rag."""
    rag_dir = os.environ.get("A2MC_RAG_DIR")
    if rag_dir:
        return Path(rag_dir)
    return _REPO_ROOT / "rag"


def resolve_active_profile(args) -> str:
    """Determine the active profile name.

    Priority: --profile > $A2MC_RAG_ACTIVE > derived from FATES api epoch.
    """
    if args.profile:
        return args.profile
    env_active = os.environ.get("A2MC_RAG_ACTIVE")
    if env_active:
        return env_active
    return None  # caller will derive from version after detection


def derive_profile_from_version(version: ELMFATESVersion) -> str:
    """Map an ELMFATESVersion to a milestone name like 'api-43-1'."""
    epoch = version.fates_api_epoch
    if not epoch:
        raise RuntimeError(
            f"Cannot derive profile name: FATES api epoch not detectable from "
            f"describe='{version.fates.describe}'. Pass --profile explicitly."
        )
    return f"api-{epoch.replace('.', '-')}"


def resolve_model_path(args) -> Path:
    """Resolve --model-path arg or fall back to $A2MC_MODEL_PATH."""
    if args.model_path:
        return Path(args.model_path).resolve()
    env = os.environ.get("A2MC_MODEL_PATH")
    if not env:
        raise EnvironmentError(
            "A2MC_MODEL_PATH is required (or pass --model-path). "
            "Set it in your site config (e.g., use_cases/<site>/config/<site>_config.sh) "
            "to your E3SM checkout root."
        )
    return Path(env).resolve()


def resolve_wiki_subdirs(args, version: ELMFATESVersion) -> tuple[str, str]:
    """Return (fates_wiki_subdir, elm_wiki_subdir).

    Priority: explicit CLI flags > commit-pinned dir matching FATES/ELM short
    SHA (e.g., 'fates-codebase-wiki-e027a40').
    """
    fates_subdir = args.fates_wiki_subdir
    if fates_subdir is None:
        candidate = f"fates-codebase-wiki-{version.fates.commit_short}"
        cand_path = _REPO_ROOT / "docs" / "fates-knowledge-base" / candidate
        if cand_path.exists():
            fates_subdir = candidate
        else:
            raise RuntimeError(
                f"Cannot resolve FATES wiki subdir. Tried '{candidate}' under "
                f"docs/fates-knowledge-base/ but it doesn't exist. Pass "
                f"--fates-wiki-subdir explicitly."
            )

    elm_subdir = args.elm_wiki_subdir
    if elm_subdir is None:
        candidate = f"elm-codebase-wiki-{version.elm.commit_short}"
        cand_path = _REPO_ROOT / "docs" / "elm-knowledge-base" / candidate
        if cand_path.exists():
            elm_subdir = candidate
        else:
            raise RuntimeError(
                f"Cannot resolve ELM wiki subdir. Tried '{candidate}' under "
                f"docs/elm-knowledge-base/ but it doesn't exist. Pass "
                f"--elm-wiki-subdir explicitly."
            )

    return fates_subdir, elm_subdir


def resolve_param_files(args, version: ELMFATESVersion) -> tuple[str, str]:
    """Return (fates_param_file, output_var_file) absolute paths.

    Priority: explicit CLI flags > commit-pinned files in
    docs/fates-knowledge-base/ (e.g., 'fates_params_info_e027a40.json').
    """
    short = version.fates.commit_short
    if args.param_cdl:
        param_file = args.param_cdl
    else:
        # Try commit-pinned JSON first (api.43+), then commit-pinned CDL
        # (api.31), then legacy unversioned CDL.
        candidates = [
            _REPO_ROOT / "docs" / "fates-knowledge-base" / f"fates_params_info_{short}.json",
            _REPO_ROOT / "docs" / "fates-knowledge-base" / f"fates_params_info_{short}.cdl",
            DEFAULT_PARAM_CDL_PATH,
        ]
        param_file = None
        for c in candidates:
            if c.exists():
                param_file = str(c)
                break
        if param_file is None:
            raise RuntimeError(
                f"Cannot resolve FATES parameter file. Tried: "
                f"{[str(c) for c in candidates]}. Pass --param-cdl explicitly."
            )

    if args.output_cdl:
        output_file = args.output_cdl
    else:
        candidates = [
            _REPO_ROOT / "docs" / "fates-knowledge-base" / f"elm_fates_output_info_{short}.cdl",
            DEFAULT_OUTPUT_CDL_PATH,
        ]
        output_file = None
        for c in candidates:
            if c.exists():
                output_file = str(c)
                break
        if output_file is None:
            raise RuntimeError(
                f"Cannot resolve FATES output CDL. Tried: "
                f"{[str(c) for c in candidates]}. Pass --output-cdl explicitly."
            )

    return param_file, output_file


def resolve_curated_yaml(args, profile: str) -> str:
    """Return the curated YAML path for this profile.

    Priority: explicit CLI flag > rag/data/curated_relationships_<profile>.yaml
    if it exists > rag/data/curated_relationships.yaml (canonical).
    """
    if args.curated_yaml:
        return args.curated_yaml
    per_profile = _REPO_ROOT / "rag" / "data" / f"curated_relationships_{profile}.yaml"
    if per_profile.exists():
        return str(per_profile)
    return str(_REPO_ROOT / "rag" / "data" / "curated_relationships.yaml")


# =============================================================================
# Main build flow
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Build A2MC RAG/GraphRAG indexes (profile-aware)."
    )
    # Profile and operation mode
    parser.add_argument(
        "--profile",
        default=None,
        help="Active profile name (e.g., 'api-43-1'). Defaults to "
             "$A2MC_RAG_ACTIVE or derived from FATES api epoch.",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete existing indexes and rebuild from scratch.",
    )
    parser.add_argument(
        "--record-metadata-only",
        action="store_true",
        help="Skip the actual rebuild; only compute and write the metadata "
             "JSON + embed _metadata in existing graph + update ChromaDB "
             "collection metadata. Used after on-disk migration to align "
             "metadata with already-built artifacts.",
    )
    parser.add_argument(
        "--graph-only", action="store_true",
        help="Only build the knowledge graph (skip vector index).",
    )
    parser.add_argument(
        "--vector-only", action="store_true",
        help="Only build the vector index (skip knowledge graph).",
    )
    parser.add_argument(
        "--no-definitions", action="store_true",
        help="Skip indexing CDL parameter/output definitions in ChromaDB.",
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Run test queries after building.",
    )

    # Inputs
    parser.add_argument(
        "--model-path", default=None,
        help="E3SM checkout root. Defaults to $A2MC_MODEL_PATH.",
    )
    parser.add_argument(
        "--kb-paths",
        nargs="+",
        default=["docs/fates-knowledge-base", "docs/elm-knowledge-base"],
        help="Knowledge base roots (one or more). FATES first, then ELM.",
    )
    parser.add_argument(
        "--fates-wiki-subdir", default=None,
        help="FATES wiki subdir name. Default: 'fates-codebase-wiki-<short_sha>'.",
    )
    parser.add_argument(
        "--elm-wiki-subdir", default=None,
        help="ELM wiki subdir name. Default: 'elm-codebase-wiki-<short_sha>'.",
    )
    parser.add_argument(
        "--param-cdl", default=None,
        help="FATES parameter file (.cdl or .json). Auto-detected from FATES "
             "commit short SHA if not given.",
    )
    parser.add_argument(
        "--output-cdl", default=None,
        help="FATES output CDL. Auto-detected from FATES commit short SHA if not given.",
    )
    parser.add_argument(
        "--curated-yaml", default=None,
        help="Curated relationships YAML. Auto-detected: per-profile snapshot "
             "(rag/data/curated_relationships_<profile>.yaml) if it exists, "
             "else canonical rag/data/curated_relationships.yaml.",
    )

    args = parser.parse_args()

    # 1. Detect model version
    try:
        model_path = resolve_model_path(args)
    except EnvironmentError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Model path: {model_path}")
    try:
        version = detect_model_version(model_path)
    except ModelPathError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Resolve profile name
    profile = resolve_active_profile(args)
    if profile is None:
        profile = derive_profile_from_version(version)
    print(f"Active profile: {profile}")

    # 3. Resolve all paths
    rag_dir = resolve_rag_dir()
    fates_wiki_subdir, elm_wiki_subdir = resolve_wiki_subdirs(args, version)
    fates_param_file, output_var_file = resolve_param_files(args, version)
    curated_yaml = resolve_curated_yaml(args, profile)

    # FATES first by convention; --kb-paths order matters for wiki_subdirs alignment.
    kb_paths = [str((_REPO_ROOT / p).resolve()) if not Path(p).is_absolute() else p
                for p in args.kb_paths]
    wiki_subdirs = [fates_wiki_subdir, elm_wiki_subdir]
    if len(kb_paths) != len(wiki_subdirs):
        print(
            f"ERROR: --kb-paths has {len(kb_paths)} entries but expected 2 "
            f"(FATES + ELM).",
            file=sys.stderr,
        )
        sys.exit(2)

    persist_dir = chroma_dir(rag_dir, profile)
    g_path = graph_path(rag_dir, profile)
    md_path = metadata_path(rag_dir, profile)

    print()
    print("=" * 60)
    print(f"  FATES commit:   {version.fates.commit_short}  ({version.fates.describe})")
    print(f"  ELM commit:     {version.elm.commit_short}  ({version.elm.describe or 'no describe'})")
    print(f"  api epoch:      {version.fates_api_epoch}")
    print()
    print(f"  KB paths:       {kb_paths}")
    print(f"  FATES wiki:     {fates_wiki_subdir}")
    print(f"  ELM wiki:       {elm_wiki_subdir}")
    print(f"  Param file:     {fates_param_file}")
    print(f"  Output CDL:     {output_var_file}")
    print(f"  Curated YAML:   {curated_yaml}")
    print()
    print(f"  ChromaDB dir:   {persist_dir}")
    print(f"  Graph file:     {g_path}")
    print(f"  Metadata file:  {md_path}")
    print("=" * 60)
    print()

    # Set env vars so downstream rag/* modules see them
    os.environ["A2MC_RAG_DIR"] = str(rag_dir)
    os.environ["A2MC_RAG_ACTIVE"] = profile

    fates_param_format = (
        "json" if Path(fates_param_file).suffix.lower() == ".json" else "cdl"
    )

    # 4. record-metadata-only: skip build, just write metadata
    if args.record_metadata_only:
        print("--record-metadata-only: skipping build, writing metadata only.")
        graph_stats = {}
        if Path(g_path).exists():
            kg = load_graph(str(g_path))
            graph_stats = kg.get_stats()
        chunk_count = 0
        if Path(persist_dir).exists():
            try:
                retr = FATESRetriever(
                    knowledge_base_path=kb_paths, persist_dir=str(persist_dir)
                )
                chunk_count = retr.vector_store.collection.count()
            except Exception as e:
                print(f"  (could not read ChromaDB collection count: {e})")

        md = build_metadata_from_version(
            version,
            profile_name=profile,
            elm_wiki_root="docs/elm-knowledge-base",
            elm_wiki_subdir=elm_wiki_subdir,
            fates_wiki_root="docs/fates-knowledge-base",
            fates_wiki_subdir=fates_wiki_subdir,
            fates_param_file=fates_param_file,
            fates_param_file_format=fates_param_format,
            output_var_file=output_var_file,
            curated_yaml_path=curated_yaml,
            stats={
                "chunk_count": chunk_count,
                "graph_nodes": graph_stats.get("total_nodes", 0),
                "graph_edges": graph_stats.get("total_edges", 0),
            },
        )
        write_metadata(md_path, md, graph_json_path=g_path)
        print(f"\nMetadata written: {md_path}")
        return

    # 5. Build vector index (Phase 1)
    if not args.graph_only:
        print("=" * 60)
        print("Phase 1: Building Vector Index (RAG)")
        print("=" * 60)
        if args.rebuild:
            print("Rebuilding vector index from scratch...\n")
            retriever = create_retriever(
                knowledge_base_path=kb_paths,
                persist_dir=str(persist_dir),
                rebuild=True,
            )
        else:
            retriever = FATESRetriever(
                knowledge_base_path=kb_paths,
                persist_dir=str(persist_dir),
                auto_build=True,
            )
        if not args.no_definitions:
            print("\n" + "-" * 40)
            print("Indexing parameter/output definitions...")
            definition_chunks = load_parameter_descriptions(
                param_cdl_path=fates_param_file,
                output_cdl_path=output_var_file,
            )
            if definition_chunks:
                print(f"Adding {len(definition_chunks)} definition chunks...")
                retriever.vector_store.add_documents(definition_chunks)
                print(f"Total documents now: {retriever.vector_store.collection.count()}")
        chunk_count = retriever.vector_store.collection.count()
        print(f"\nVector store: {chunk_count} documents")
    else:
        chunk_count = 0

    # 6. Build knowledge graph (Phase 2)
    if not args.vector_only:
        print("\n" + "=" * 60)
        print("Phase 2: Building Knowledge Graph (GraphRAG)")
        print("=" * 60)
        # Use FATES wiki path (first KB)
        fates_kb_path = kb_paths[0]
        if args.rebuild or not Path(g_path).exists():
            print("Building knowledge graph (two-layer construction)...\n")
            kg = build_fates_graph(
                knowledge_base_path=fates_kb_path,
                include_pft_specific=True,
                param_cdl_path=fates_param_file,
                output_cdl_path=output_var_file,
            )
        else:
            print(f"Loading existing graph from: {g_path}")
            kg = load_graph(str(g_path))

        graph_stats = kg.get_stats()
        print(f"\nGraph: {graph_stats['total_nodes']} nodes, "
              f"{graph_stats['total_edges']} edges")
    else:
        graph_stats = {}

    # 7. Write metadata + embed in graph
    md = build_metadata_from_version(
        version,
        profile_name=profile,
        elm_wiki_root="docs/elm-knowledge-base",
        elm_wiki_subdir=elm_wiki_subdir,
        fates_wiki_root="docs/fates-knowledge-base",
        fates_wiki_subdir=fates_wiki_subdir,
        fates_param_file=fates_param_file,
        fates_param_file_format=fates_param_format,
        output_var_file=output_var_file,
        curated_yaml_path=curated_yaml,
        stats={
            "chunk_count": chunk_count,
            "graph_nodes": graph_stats.get("total_nodes", 0),
            "graph_edges": graph_stats.get("total_edges", 0),
        },
    )

    # Save graph with metadata embedded
    if not args.vector_only:
        save_graph(kg, str(g_path), metadata=md)

    # Write standalone metadata JSON
    write_metadata(md_path, md, graph_json_path=None)
    print(f"\nMetadata written: {md_path}")

    if args.test:
        run_tests(args, kb_paths, str(persist_dir), str(g_path))

    print("\n" + "=" * 60)
    print(f"RAG/GraphRAG indexes ready for profile '{profile}'!")
    print("=" * 60)


def run_tests(args, kb_paths, persist_dir, graph_p):
    """Run test queries to verify both indexes."""
    print("\n" + "=" * 60)
    print("Running Tests")
    print("=" * 60)

    retriever = HybridRetriever(
        knowledge_base_path=kb_paths,
        vector_persist_dir=persist_dir,
        graph_path=graph_p,
        auto_build=False,
    )
    print("\n--- Vector Search ---")
    for name, query in [
        ("PID Controller", "PID controller adaptive allocation"),
        ("Phenology", "phenology cold deciduous GDD threshold"),
        ("ECA Competition", "ECA nutrient competition phosphorus uptake"),
    ]:
        print(f"\n  {name}: {query}")
        results = retriever.vector_retriever.vector_store.query(query, n_results=2)
        for r in results[:2]:
            print(f"    - {r['source']} (relevance: {r['relevance']:.3f})")

    print("\n--- Knowledge Graph ---")
    print("\n  Parameters affecting FATES_FROOTC:")
    for p in retriever.knowledge_graph.get_related_parameters("FATES_FROOTC", depth=3)[:5]:
        print(f"    - {p}")


if __name__ == "__main__":
    main()
