"""
Vector store wrapper using ChromaDB for FATES knowledge base.

Provides embedding storage and semantic search capabilities
for the RAG system.
"""

import os
from pathlib import Path
from typing import Optional


class FATESVectorStore:
    """
    ChromaDB-based vector store for FATES documentation.

    Uses sentence-transformers for embeddings and ChromaDB
    for persistent storage and retrieval.
    """

    def __init__(
        self,
        persist_dir: str = "rag/chroma_db",
        collection_name: str = "fates_knowledge",
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        """
        Initialize the vector store.

        Args:
            persist_dir: Directory to persist the ChromaDB database
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
            metadatas = [
                {
                    'source': c['source'],
                    'type': c['type'],
                    'title': c.get('title', ''),
                    'format': c.get('format', 'unknown'),
                    'kb_source': c.get('kb_source', '')  # Knowledge base source
                }
                for c in batch
            ]
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
