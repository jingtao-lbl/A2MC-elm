"""
RAG Retriever for FATES knowledge base.

Provides high-level interface for retrieving relevant context
from the FATES documentation during AI-assisted calibration.
"""

from pathlib import Path
from typing import Optional

from .loader import load_all_documents, chunk_documents
from .vector_store import FATESVectorStore


class FATESRetriever:
    """
    RAG retriever for FATES documentation.

    Combines document loading, chunking, and vector search
    to provide relevant context for calibration tasks.
    """

    def __init__(
        self,
        knowledge_base_path: str = "docs/fates-knowledge-base",
        persist_dir: str = "rag/chroma_db",
        auto_build: bool = False
    ):
        """
        Initialize the retriever.

        Args:
            knowledge_base_path: Path to the FATES knowledge base directory
            persist_dir: Directory for ChromaDB persistence
            auto_build: If True, automatically build index if empty
        """
        self.kb_path = knowledge_base_path
        self.persist_dir = persist_dir
        self.vector_store = FATESVectorStore(persist_dir=persist_dir)
        self._indexed = self.vector_store.collection.count() > 0

        if auto_build and not self._indexed:
            print("Index is empty. Building automatically...")
            self.build_index()

    def build_index(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        Build the vector index from the knowledge base.

        Args:
            chunk_size: Target size for document chunks
            chunk_overlap: Overlap between chunks
        """
        print(f"Building index from: {self.kb_path}")

        # Load all documents
        docs = load_all_documents(self.kb_path)

        if not docs:
            print("Warning: No documents found!")
            return

        # Chunk documents
        print(f"\nChunking {len(docs)} documents...")
        chunks = chunk_documents(docs, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        print(f"Created {len(chunks)} chunks")

        # Add to vector store
        print("\nAdding to vector store...")
        self.vector_store.add_documents(chunks)

        self._indexed = True
        print("\nIndex built successfully!")

    def get_context(
        self,
        query: str,
        n_results: int = 5,
        filter_type: Optional[str] = None
    ) -> str:
        """
        Get relevant context for a query.

        Args:
            query: Search query
            n_results: Number of results to return
            filter_type: Filter by document type

        Returns:
            Formatted context string
        """
        if not self._indexed:
            raise ValueError("Index not built. Call build_index() first or set auto_build=True")

        results = self.vector_store.query(
            query,
            n_results=n_results,
            filter_type=filter_type
        )

        if not results:
            return "No relevant documentation found."

        # Format context
        context_parts = []
        for i, r in enumerate(results, 1):
            source_info = f"[{i}] Source: {r['source']}"
            if r.get('title'):
                source_info += f" ({r['title']})"

            context_parts.append(f"{source_info}\n{r['content']}")

        return "\n\n---\n\n".join(context_parts)

    def get_calibration_context(
        self,
        parameters: list[str] = None,
        outputs: list[str] = None,
        mechanisms: list[str] = None,
        n_results_per_query: int = 2,
        max_total_results: int = 10
    ) -> str:
        """
        Get context relevant to specific calibration targets.

        Generates targeted queries for parameters, outputs, and mechanisms
        and combines the results.

        Args:
            parameters: List of parameter names (e.g., ['fates_cnp_pid_kp', 'fates_alloc_storage_cushion'])
            outputs: List of output variables (e.g., ['leaf_biomass', 'fineroot'])
            mechanisms: List of mechanisms (e.g., ['PID controller', 'ECA competition'])
            n_results_per_query: Results per individual query
            max_total_results: Maximum total results to return

        Returns:
            Formatted context string
        """
        if not self._indexed:
            raise ValueError("Index not built. Call build_index() first or set auto_build=True")

        queries = []

        # Generate queries for parameters
        if parameters:
            for param in parameters:
                # Clean parameter name for querying
                clean_param = param.replace('fates_', '').replace('_', ' ')
                queries.append(f"FATES parameter {clean_param} controls behavior effect")
                queries.append(f"{param} sensitivity calibration")

        # Generate queries for outputs
        if outputs:
            for output in outputs:
                queries.append(f"FATES {output} biomass allocation mechanism")
                queries.append(f"{output} sensitivity parameters")

        # Generate queries for mechanisms
        if mechanisms:
            for mech in mechanisms:
                queries.append(f"FATES {mech} mechanism implementation")
                queries.append(f"{mech} parameters controls")

        if not queries:
            return "No queries specified. Provide parameters, outputs, or mechanisms."

        # Query with all queries
        results = self.vector_store.query_multiple(
            queries,
            n_results_per_query=n_results_per_query,
            deduplicate=True
        )

        # Limit total results
        results = results[:max_total_results]

        if not results:
            return "No relevant documentation found."

        # Format context
        context_parts = []
        for i, r in enumerate(results, 1):
            source_info = f"[{i}] Source: {r['source']} (relevance: {r['relevance']:.2f})"
            context_parts.append(f"{source_info}\n{r['content']}")

        return "\n\n---\n\n".join(context_parts)

    def search(
        self,
        query: str,
        n_results: int = 5,
        return_raw: bool = False
    ) -> list[dict] | str:
        """
        Search the knowledge base.

        Args:
            query: Search query
            n_results: Number of results
            return_raw: If True, return raw result dictionaries

        Returns:
            Either formatted string or list of result dicts
        """
        if not self._indexed:
            raise ValueError("Index not built. Call build_index() first or set auto_build=True")

        results = self.vector_store.query(query, n_results=n_results)

        if return_raw:
            return results

        return self.get_context(query, n_results=n_results)

    def get_parameter_documentation(self, param_name: str) -> str:
        """
        Get documentation for a specific parameter.

        Args:
            param_name: FATES parameter name

        Returns:
            Relevant documentation context
        """
        queries = [
            f"parameter {param_name} description",
            f"{param_name} controls affects",
            f"{param_name} calibration sensitivity"
        ]

        results = self.vector_store.query_multiple(
            queries,
            n_results_per_query=2,
            deduplicate=True
        )[:5]

        if not results:
            return f"No documentation found for parameter: {param_name}"

        context_parts = []
        for r in results:
            context_parts.append(f"[{r['source']}]\n{r['content']}")

        return "\n\n---\n\n".join(context_parts)

    def get_mechanism_documentation(self, mechanism: str) -> str:
        """
        Get documentation for a specific mechanism.

        Args:
            mechanism: Mechanism name (e.g., 'PID controller', 'phenology')

        Returns:
            Relevant documentation context
        """
        queries = [
            f"FATES {mechanism} mechanism",
            f"{mechanism} implementation code",
            f"{mechanism} parameters controls"
        ]

        results = self.vector_store.query_multiple(
            queries,
            n_results_per_query=3,
            deduplicate=True
        )[:8]

        if not results:
            return f"No documentation found for mechanism: {mechanism}"

        context_parts = []
        for r in results:
            context_parts.append(f"[{r['source']}]\n{r['content']}")

        return "\n\n---\n\n".join(context_parts)

    def get_stats(self) -> dict:
        """Get retriever statistics."""
        store_stats = self.vector_store.get_stats()
        return {
            **store_stats,
            'knowledge_base_path': self.kb_path,
            'indexed': self._indexed
        }


def create_retriever(
    knowledge_base_path: str = "docs/fates-knowledge-base",
    persist_dir: str = "rag/chroma_db",
    rebuild: bool = False
) -> FATESRetriever:
    """
    Factory function to create a retriever with optional rebuild.

    Args:
        knowledge_base_path: Path to knowledge base
        persist_dir: ChromaDB persistence directory
        rebuild: If True, delete existing index and rebuild

    Returns:
        Configured FATESRetriever instance
    """
    if rebuild:
        import shutil
        persist_path = Path(persist_dir)
        if persist_path.exists():
            print(f"Removing existing index at: {persist_dir}")
            shutil.rmtree(persist_dir)

    retriever = FATESRetriever(
        knowledge_base_path=knowledge_base_path,
        persist_dir=persist_dir,
        auto_build=True
    )

    return retriever


if __name__ == "__main__":
    import sys

    kb_path = sys.argv[1] if len(sys.argv) > 1 else "docs/fates-knowledge-base"

    print("Creating FATES retriever...")
    retriever = FATESRetriever(knowledge_base_path=kb_path, auto_build=True)

    print("\n" + "=" * 50)
    print("Testing retriever")
    print("=" * 50)

    # Test basic search
    print("\n1. Basic search: 'PID controller allocation'")
    context = retriever.get_context("PID controller allocation", n_results=3)
    print(context[:500] + "..." if len(context) > 500 else context)

    # Test calibration context
    print("\n2. Calibration context for PFT#10 optimization")
    cal_context = retriever.get_calibration_context(
        parameters=['fates_cnp_pid_kp', 'fates_alloc_storage_cushion'],
        outputs=['leaf_biomass', 'fineroot_biomass'],
        mechanisms=['PID controller', 'nutrient competition']
    )
    print(cal_context[:500] + "..." if len(cal_context) > 500 else cal_context)

    # Test parameter documentation
    print("\n3. Parameter documentation: fates_cnp_pid_kp")
    param_doc = retriever.get_parameter_documentation('fates_cnp_pid_kp')
    print(param_doc[:500] + "..." if len(param_doc) > 500 else param_doc)

    print("\n" + "=" * 50)
    print("Retriever stats:")
    stats = retriever.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
