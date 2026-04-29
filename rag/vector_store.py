"""
Vector store wrapper using ChromaDB for FATES knowledge base.

Provides embedding storage and semantic search capabilities
for the RAG system.
"""

import os
from pathlib import Path
from typing import Optional


def _resolve_chroma_dir_from_env() -> str:
    """Build a per-profile ChromaDB persist dir from A2MC env vars.

    Layout: `$A2MC_RAG_DIR/chroma_db/$A2MC_RAG_ACTIVE`. `A2MC_RAG_DIR` defaults
    to `<repo>/rag` if unset. `A2MC_RAG_ACTIVE` is required (per the version-
    association infrastructure); raises EnvironmentError if missing.
    """
    rag_dir = os.environ.get("A2MC_RAG_DIR")
    if not rag_dir:
        # Fall back to repo-relative `rag/`. Resolved against repo root.
        repo_root = Path(__file__).resolve().parent.parent
        rag_dir = str(repo_root / "rag")
    active = os.environ.get("A2MC_RAG_ACTIVE")
    if not active:
        raise EnvironmentError(
            "A2MC_RAG_ACTIVE is not set and no explicit persist_dir was supplied. "
            "Set A2MC_RAG_ACTIVE to a registered milestone profile name "
            "(e.g., 'api-43-1' or 'api-31-0'), or pass `persist_dir=` explicitly."
        )
    return str(Path(rag_dir) / "chroma_db" / active)


class FATESVectorStore:
    """
    ChromaDB-based vector store for FATES documentation.

    Uses sentence-transformers for embeddings and ChromaDB
    for persistent storage and retrieval.
    """

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        collection_name: str = "fates_knowledge",
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        """
        Initialize the vector store.

        Args:
            persist_dir: Directory to persist the ChromaDB database. If None,
                derives from `$A2MC_RAG_DIR/chroma_db/$A2MC_RAG_ACTIVE`. The
                env vars must be set when `persist_dir` is unset (per the
                version-association infrastructure; see CLAUDE.md).
            collection_name: Name of the collection in ChromaDB
            embedding_model: Sentence-transformer model for embeddings
        """
        try:
            import chromadb
            from chromadb.utils import embedding_functions
        except ImportError:
            raise ImportError(
                "chromadb is required. Install with: pip install chromadb sentence-transformers"
            )

        if persist_dir is None:
            persist_dir = _resolve_chroma_dir_from_env()

        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.embedding_model = embedding_model

        # Ensure persist directory exists
        Path(persist_dir).mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client with persistence
        self.client = chromadb.PersistentClient(path=persist_dir)

        # Initialize embedding function
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn,
            metadata={
                "description": "FATES knowledge base for A2MC calibration",
                "embedding_model": embedding_model
            }
        )

        print(f"Vector store initialized at: {persist_dir}")
        print(f"Collection: {collection_name} ({self.collection.count()} documents)")

    def add_documents(self, chunks: list[dict], batch_size: int = 100) -> int:
        """
        Add document chunks to the vector store.

        Args:
            chunks: List of chunk dictionaries with content, source, type, chunk_id
            batch_size: Number of documents to add in each batch

        Returns:
            Number of documents added
        """
        if not chunks:
            print("No chunks to add")
            return 0

        # Process in batches to avoid memory issues
        total_added = 0

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]

            documents = [c['content'] for c in batch]
            metadatas = []
            for c in batch:
                meta = {
                    'source': c['source'],
                    'type': c['type'],
                    'title': c.get('title', ''),
                    'format': c.get('format', 'unknown'),
                    'kb_source': c.get('kb_source', ''),
                }
                # Pass through CDL definition metadata for filtered queries
                for extra_key in ('entity_type', 'param_category', 'is_pft_specific',
                                  'dimension_level', 'output_category'):
                    if extra_key in c:
                        meta[extra_key] = c[extra_key]
                metadatas.append(meta)
            ids = [c['chunk_id'] for c in batch]

            # Check for existing IDs and skip them
            existing = set()
            try:
                existing_docs = self.collection.get(ids=ids)
                existing = set(existing_docs['ids'])
            except Exception:
                pass

            # Filter out existing documents
            new_docs = []
            new_metas = []
            new_ids = []

            for doc, meta, id_ in zip(documents, metadatas, ids):
                if id_ not in existing:
                    new_docs.append(doc)
                    new_metas.append(meta)
                    new_ids.append(id_)

            if new_docs:
                self.collection.add(
                    documents=new_docs,
                    metadatas=new_metas,
                    ids=new_ids
                )
                total_added += len(new_docs)

            print(f"  Processed batch {i // batch_size + 1}: "
                  f"added {len(new_docs)}, skipped {len(batch) - len(new_docs)}")

        print(f"Total documents added: {total_added}")
        print(f"Collection now contains: {self.collection.count()} documents")

        return total_added

    def query(
        self,
        query: str,
        n_results: int = 5,
        filter_type: Optional[str] = None,
        filter_source: Optional[str] = None
    ) -> list[dict]:
        """
        Query the vector store for relevant documents.

        Args:
            query: Search query string
            n_results: Maximum number of results to return
            filter_type: Filter by document type (e.g., 'codebase-wiki', 'official-docs')
            filter_source: Filter by source path (substring match)

        Returns:
            List of result dictionaries with content, source, type, distance
        """
        # Build where clause for filtering
        where = None
        if filter_type:
            where = {"type": filter_type}

        # Query the collection
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"]
        )

        # Format results
        formatted = []
        if results['documents'] and results['documents'][0]:
            for doc, meta, dist in zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            ):
                # Apply source filter if specified
                if filter_source and filter_source not in meta.get('source', ''):
                    continue

                formatted.append({
                    'content': doc,
                    'source': meta.get('source', ''),
                    'type': meta.get('type', ''),
                    'title': meta.get('title', ''),
                    'kb_source': meta.get('kb_source', ''),  # Knowledge base source
                    'distance': dist,
                    'relevance': 1 - dist  # Convert distance to relevance score
                })

        return formatted

    def query_parameters(
        self,
        query: str,
        n_results: int = 10,
        category: Optional[str] = None
    ) -> list[dict]:
        """Query for parameter definitions only.

        Args:
            query: Search query
            n_results: Max results
            category: Filter by parameter category (e.g., 'cnp', 'alloc')

        Returns:
            List of result dicts filtered to parameter definitions
        """
        where = {"entity_type": "parameter"}
        if category:
            where = {"$and": [
                {"entity_type": "parameter"},
                {"param_category": category}
            ]}

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"]
            )
        except Exception:
            # Fallback: entity_type metadata may not exist in older indexes
            return self.query(query, n_results=n_results)

        formatted = []
        if results['documents'] and results['documents'][0]:
            for doc, meta, dist in zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            ):
                formatted.append({
                    'content': doc,
                    'source': meta.get('source', ''),
                    'type': meta.get('type', ''),
                    'title': meta.get('title', ''),
                    'distance': dist,
                    'relevance': 1 - dist
                })

        return formatted

    def query_outputs(
        self,
        query: str,
        n_results: int = 10,
        dimension_level: Optional[str] = None
    ) -> list[dict]:
        """Query for output variable definitions only.

        Args:
            query: Search query
            n_results: Max results
            dimension_level: Filter by dimension level (e.g., 'site', 'pft', 'szpf')

        Returns:
            List of result dicts filtered to output definitions
        """
        where = {"entity_type": "output"}
        if dimension_level:
            where = {"$and": [
                {"entity_type": "output"},
                {"dimension_level": dimension_level}
            ]}

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"]
            )
        except Exception:
            return self.query(query, n_results=n_results)

        formatted = []
        if results['documents'] and results['documents'][0]:
            for doc, meta, dist in zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            ):
                formatted.append({
                    'content': doc,
                    'source': meta.get('source', ''),
                    'type': meta.get('type', ''),
                    'title': meta.get('title', ''),
                    'distance': dist,
                    'relevance': 1 - dist
                })

        return formatted

    def query_multiple(
        self,
        queries: list[str],
        n_results_per_query: int = 3,
        deduplicate: bool = True
    ) -> list[dict]:
        """
        Query with multiple queries and combine results.

        Args:
            queries: List of query strings
            n_results_per_query: Number of results per query
            deduplicate: Whether to remove duplicate results

        Returns:
            Combined list of results
        """
        all_results = []
        seen_sources = set()

        for query in queries:
            results = self.query(query, n_results=n_results_per_query)

            for r in results:
                if deduplicate:
                    if r['source'] not in seen_sources:
                        seen_sources.add(r['source'])
                        all_results.append(r)
                else:
                    all_results.append(r)

        # Sort by relevance
        all_results.sort(key=lambda x: x['relevance'], reverse=True)

        return all_results

    def delete_collection(self):
        """Delete the entire collection (use with caution)."""
        self.client.delete_collection(self.collection_name)
        print(f"Deleted collection: {self.collection_name}")

    def get_stats(self) -> dict:
        """Get statistics about the vector store."""
        count = self.collection.count()

        # Get sample of metadata to analyze types
        sample = self.collection.peek(limit=min(100, count))

        type_counts = {}
        if sample['metadatas']:
            for meta in sample['metadatas']:
                doc_type = meta.get('type', 'unknown')
                type_counts[doc_type] = type_counts.get(doc_type, 0) + 1

        return {
            'total_documents': count,
            'persist_dir': self.persist_dir,
            'collection_name': self.collection_name,
            'embedding_model': self.embedding_model,
            'type_distribution_sample': type_counts
        }


if __name__ == "__main__":
    # Test the vector store
    store = FATESVectorStore()

    print("\nVector store stats:")
    stats = store.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")

    if store.collection.count() > 0:
        print("\nTesting query...")
        results = store.query("PID controller allocation", n_results=3)
        for r in results:
            print(f"\n  Source: {r['source']}")
            print(f"  Relevance: {r['relevance']:.3f}")
            print(f"  Preview: {r['content'][:150]}...")
