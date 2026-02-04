"""
RAG (Retrieval-Augmented Generation) system for FATES knowledge base.

This module provides semantic search and knowledge graph capabilities
for AI-assisted calibration of ELM-FATES.

Phase 1 Components (Vector RAG):
- loader: Document loading and chunking
- vector_store: ChromaDB vector store wrapper
- retriever: RAG retriever for context retrieval

Phase 2 Components (GraphRAG):
- knowledge_graph: Graph schema and operations
- graph_builder: Build graph from FATES entities
- hybrid_retriever: Combined vector + graph retrieval

Phase 3 Components (Version-Flexible GraphRAG):
- parameter_parser: Parse parameters from CDL/JSON/NC files

Usage:
    # Basic RAG
    from rag import FATESRetriever
    retriever = FATESRetriever(auto_build=True)
    context = retriever.get_calibration_context(
        parameters=['fates_cnp_pid_kp'],
        outputs=['FATES_LEAFC']
    )

    # GraphRAG (hybrid)
    from rag import HybridRetriever
    retriever = HybridRetriever(auto_build=True)
    context = retriever.get_calibration_context(
        parameters=['fates_cnp_pid_kp'],
        outputs=['FATES_LEAFC'],
        mechanisms=['PID_Controller']
    )

    # Parameter parsing (any FATES version)
    from rag import FATESParameterParser
    parser = FATESParameterParser('fates_params.nc')
    params = parser.parse()
    pft_names = parser.get_pft_names()
"""

# Phase 1: Vector RAG
from .loader import (
    load_markdown_files,
    load_rst_files,
    chunk_documents,
    load_all_documents,
    load_knowledge_base,
    load_multiple_knowledge_bases,
    DEFAULT_KNOWLEDGE_BASES
)
from .vector_store import FATESVectorStore
from .retriever import FATESRetriever, create_retriever

# Phase 2: GraphRAG
from .knowledge_graph import FATESKnowledgeGraph
from .graph_builder import build_fates_graph, save_graph, load_graph
from .hybrid_retriever import HybridRetriever, create_hybrid_retriever

# Phase 3: Version-Flexible GraphRAG
from .parameter_parser import (
    FATESParameterParser,
    FATESParameter,
    compare_parameter_files,
    get_calibratable_parameters,
    CATEGORIES as PARAM_CATEGORIES,
)

__all__ = [
    # Phase 1
    'load_markdown_files',
    'load_rst_files',
    'chunk_documents',
    'load_all_documents',
    'load_knowledge_base',
    'load_multiple_knowledge_bases',
    'DEFAULT_KNOWLEDGE_BASES',
    'FATESVectorStore',
    'FATESRetriever',
    'create_retriever',
    # Phase 2
    'FATESKnowledgeGraph',
    'build_fates_graph',
    'save_graph',
    'load_graph',
    'HybridRetriever',
    'create_hybrid_retriever',
    # Phase 3
    'FATESParameterParser',
    'FATESParameter',
    'compare_parameter_files',
    'get_calibratable_parameters',
    'PARAM_CATEGORIES',
]
