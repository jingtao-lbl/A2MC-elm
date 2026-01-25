#!/Library/Frameworks/Python.framework/Versions/3.10/bin/python3
"""
Build RAG and GraphRAG indexes from FATES knowledge base.

This script:
1. Loads all documents from the FATES knowledge base
2. Chunks them for optimal embedding
3. Creates a ChromaDB vector store (Phase 1: RAG)
4. Builds a knowledge graph with FATES entities (Phase 2: GraphRAG)
5. Tests the retrievers with sample queries

Usage:
    python scripts/build_rag_index.py [--rebuild] [--test] [--graph-only]

Options:
    --rebuild     Delete existing indexes and rebuild from scratch
    --test        Run test queries after building
    --graph-only  Only build/rebuild the knowledge graph
    --vector-only Only build/rebuild the vector index
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.retriever import FATESRetriever, create_retriever
from rag.graph_builder import build_fates_graph, save_graph, load_graph
from rag.hybrid_retriever import HybridRetriever, create_hybrid_retriever


def main():
    parser = argparse.ArgumentParser(description="Build FATES RAG/GraphRAG indexes")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete existing indexes and rebuild"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run test queries after building"
    )
    parser.add_argument(
        "--graph-only",
        action="store_true",
        help="Only build the knowledge graph"
    )
    parser.add_argument(
        "--vector-only",
        action="store_true",
        help="Only build the vector index"
    )
    parser.add_argument(
        "--kb-path",
        default="docs/fates-knowledge-base",
        help="Path to knowledge base (default: docs/fates-knowledge-base)"
    )
    parser.add_argument(
        "--persist-dir",
        default="rag/chroma_db",
        help="ChromaDB persistence directory (default: rag/chroma_db)"
    )
    parser.add_argument(
        "--graph-path",
        default="rag/fates_knowledge_graph.json",
        help="Knowledge graph JSON path (default: rag/fates_knowledge_graph.json)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("FATES RAG/GraphRAG Index Builder")
    print("=" * 60)
    print(f"\nKnowledge base: {args.kb_path}")
    print(f"Vector store: {args.persist_dir}")
    print(f"Knowledge graph: {args.graph_path}")
    print(f"Rebuild: {args.rebuild}")
    print()

    # Build vector index (Phase 1)
    if not args.graph_only:
        print("=" * 60)
        print("Phase 1: Building Vector Index (RAG)")
        print("=" * 60)

        if args.rebuild:
            print("Rebuilding vector index from scratch...\n")
            retriever = create_retriever(
                knowledge_base_path=args.kb_path,
                persist_dir=args.persist_dir,
                rebuild=True
            )
        else:
            retriever = FATESRetriever(
                knowledge_base_path=args.kb_path,
                persist_dir=args.persist_dir,
                auto_build=True
            )

        # Print vector stats
        print("\nVector Index Statistics:")
        stats = retriever.get_stats()
        for k, v in stats.items():
            print(f"  {k}: {v}")

    # Build knowledge graph (Phase 2)
    if not args.vector_only:
        print("\n" + "=" * 60)
        print("Phase 2: Building Knowledge Graph (GraphRAG)")
        print("=" * 60)

        graph_path = Path(args.graph_path)

        if args.rebuild or not graph_path.exists():
            print("Building knowledge graph...\n")
            kg = build_fates_graph(
                knowledge_base_path=args.kb_path,
                include_pft_specific=True
            )
            save_graph(kg, args.graph_path)
        else:
            print(f"Loading existing graph from: {args.graph_path}")
            kg = load_graph(args.graph_path)

        # Print graph stats
        print("\nKnowledge Graph Statistics:")
        stats = kg.get_stats()
        print(f"  Total nodes: {stats['total_nodes']}")
        print(f"  Total edges: {stats['total_edges']}")
        print(f"  Nodes by type: {stats['nodes_by_type']}")
        print(f"  Edges by type: {stats['edges_by_type']}")

    # Run tests if requested
    if args.test:
        run_tests(args)

    print("\n" + "=" * 60)
    print("RAG/GraphRAG indexes ready!")
    print("=" * 60)
    print("\nUsage:")
    print("  from rag import HybridRetriever")
    print("  retriever = HybridRetriever(auto_build=True)")
    print("  context = retriever.get_calibration_context(")
    print("      parameters=['fates_cnp_pid_kp'],")
    print("      outputs=['FATES_LEAFC', 'FATES_FROOTC']")
    print("  )")


def run_tests(args):
    """Run test queries to verify both indexes."""
    print("\n" + "=" * 60)
    print("Running Tests")
    print("=" * 60)

    # Create hybrid retriever for testing
    print("\nInitializing HybridRetriever...")
    retriever = HybridRetriever(
        knowledge_base_path=args.kb_path,
        vector_persist_dir=args.persist_dir,
        graph_path=args.graph_path,
        auto_build=False  # Already built
    )

    # Test 1: Vector search
    print("\n--- Test 1: Vector Search ---")
    test_queries = [
        ("PID Controller", "PID controller adaptive allocation leaf to fineroot"),
        ("Phenology", "phenology cold deciduous GDD threshold"),
        ("Nutrient Competition", "ECA nutrient competition phosphorus uptake"),
    ]

    for name, query in test_queries:
        print(f"\n  Query: {name}")
        results = retriever.vector_retriever.vector_store.query(query, n_results=2)
        for r in results[:2]:
            print(f"    - {r['source']} (relevance: {r['relevance']:.3f})")

    # Test 2: Knowledge graph queries
    print("\n--- Test 2: Knowledge Graph Queries ---")

    print("\n  Parameters affecting FATES_FROOTC:")
    params = retriever.knowledge_graph.get_related_parameters("FATES_FROOTC", depth=3)
    for p in params[:5]:
        print(f"    - {p}")

    print("\n  Parameters controlling PID_Controller:")
    pid_params = retriever.knowledge_graph.get_mechanism_parameters("PID_Controller")
    for p in pid_params[:5]:
        print(f"    - {p}")

    print("\n  PFT10 parameters:")
    pft_params = retriever.knowledge_graph.get_pft_parameters(10)
    for p in pft_params[:5]:
        print(f"    - {p}")

    # Test 3: Hybrid retrieval
    print("\n--- Test 3: Hybrid Calibration Context ---")
    print("  Parameters: ['fates_cnp_pid_kp', 'fates_alloc_storage_cushion']")
    print("  Outputs: ['FATES_LEAFC', 'FATES_FROOTC']")
    print("  Mechanisms: ['PID_Controller']")

    cal_context = retriever.get_calibration_context(
        parameters=['fates_cnp_pid_kp', 'fates_alloc_storage_cushion'],
        outputs=['FATES_LEAFC', 'FATES_FROOTC'],
        mechanisms=['PID_Controller'],
        pft=10
    )

    print("\n  Parameter info:")
    for param, info in cal_context.get('parameters', {}).items():
        effects = info.get('effects', [])
        if effects:
            print(f"    {param}: affects {[e['target'] for e in effects]}")

    print("\n  Relationships found:")
    for rel in cal_context.get('relationships', []):
        if rel['path']:
            path_str = " -> ".join([p.split(':')[-1] for p in rel['path']])
            print(f"    {rel['from']} -> {rel['to']}: {path_str}")

    # Test 4: Find parameters for output
    print("\n--- Test 4: Find Parameters for Output ---")
    print("  Finding parameters that affect FATES_L2FR:")
    l2fr_params = retriever.find_parameters_for_output("FATES_L2FR")
    for p in l2fr_params[:5]:
        print(f"    - {p['parameter']}")

    # Print combined stats
    print("\n--- Combined Statistics ---")
    stats = retriever.get_stats()
    print(f"  Vector store: {stats['vector_store']['total_documents']} documents")
    print(f"  Knowledge graph: {stats['knowledge_graph']['total_nodes']} nodes, "
          f"{stats['knowledge_graph']['total_edges']} edges")


if __name__ == "__main__":
    main()
