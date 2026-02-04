"""
Document loader for knowledge bases.

Loads and chunks Markdown and RST files from knowledge bases
for indexing in the vector store.

Supports multiple knowledge bases:
- FATES: docs/fates-knowledge-base/
- ELM: docs/elm-knowledge-base/
"""

import re
from pathlib import Path
from typing import Optional


def load_markdown_files(base_path: str) -> list[dict]:
    """
    Load all markdown files from a directory.

    Args:
        base_path: Root directory to search for .md files

    Returns:
        List of document dictionaries with content, source, and type
    """
    docs = []
    base = Path(base_path)

    if not base.exists():
        print(f"Warning: Path does not exist: {base_path}")
        return docs

    for md_file in base.rglob("*.md"):
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Determine document type based on path
            rel_path = str(md_file.relative_to(base))
            if 'codebase-wiki' in str(md_file):
                doc_type = 'codebase-wiki'
            elif 'official-docs' in str(md_file):
                doc_type = 'official-docs'
            else:
                doc_type = 'general'

            # Extract title from first heading if present
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else md_file.stem

            docs.append({
                'content': content,
                'source': rel_path,
                'type': doc_type,
                'title': title,
                'format': 'markdown'
            })

        except Exception as e:
            print(f"Warning: Could not read {md_file}: {e}")

    return docs


def load_rst_files(base_path: str) -> list[dict]:
    """
    Load RST (reStructuredText) files from a directory.

    Args:
        base_path: Root directory to search for .rst files

    Returns:
        List of document dictionaries with content, source, and type
    """
    docs = []
    base = Path(base_path)

    if not base.exists():
        print(f"Warning: Path does not exist: {base_path}")
        return docs

    for rst_file in base.rglob("*.rst"):
        try:
            with open(rst_file, 'r', encoding='utf-8') as f:
                content = f.read()

            rel_path = str(rst_file.relative_to(base))

            # Extract title from RST (first line followed by === or ---)
            lines = content.split('\n')
            title = rst_file.stem
            if len(lines) >= 2:
                if lines[1].startswith('===') or lines[1].startswith('---'):
                    title = lines[0].strip()

            docs.append({
                'content': content,
                'source': rel_path,
                'type': 'official-docs',
                'title': title,
                'format': 'rst'
            })

        except Exception as e:
            print(f"Warning: Could not read {rst_file}: {e}")

    return docs


def clean_text(text: str) -> str:
    """
    Clean document text for better embedding quality.

    Args:
        text: Raw document text

    Returns:
        Cleaned text
    """
    # Remove excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Remove markdown image references (keep alt text)
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', text)

    # Remove SVG/image references in RST
    text = re.sub(r'\.\. image::.*?\n', '', text)
    text = re.sub(r'\.\. figure::.*?\n', '', text)

    # Remove HTML comments
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

    # Remove code block markers but keep content
    text = re.sub(r'```\w*\n', '', text)
    text = re.sub(r'```', '', text)

    return text.strip()


def chunk_documents(
    docs: list[dict],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    min_chunk_size: int = 100
) -> list[dict]:
    """
    Split documents into chunks for embedding.

    Uses semantic-aware splitting that tries to preserve
    section boundaries and code blocks.

    Args:
        docs: List of document dictionaries
        chunk_size: Target size for each chunk in characters
        chunk_overlap: Number of characters to overlap between chunks
        min_chunk_size: Minimum chunk size (smaller chunks are merged)

    Returns:
        List of chunk dictionaries with content, source, type, and chunk_id
    """
    # Define split points in order of preference
    separators = [
        "\n## ",      # H2 headers (major sections)
        "\n### ",     # H3 headers (subsections)
        "\n#### ",    # H4 headers
        "\n\n",       # Paragraphs
        "\n",         # Lines
        ". ",         # Sentences
        " ",          # Words
    ]

    chunks = []

    for doc in docs:
        content = clean_text(doc['content'])

        # Skip empty documents
        if len(content) < min_chunk_size:
            continue

        # Split using recursive character splitting
        doc_chunks = _recursive_split(content, separators, chunk_size, chunk_overlap)

        # Filter out too-small chunks and create chunk records
        for i, chunk_text in enumerate(doc_chunks):
            if len(chunk_text) >= min_chunk_size:
                chunks.append({
                    'content': chunk_text,
                    'source': doc['source'],
                    'type': doc['type'],
                    'title': doc.get('title', ''),
                    'format': doc.get('format', 'unknown'),
                    'chunk_id': f"{doc['source']}::chunk_{i}"
                })

    return chunks


def _recursive_split(
    text: str,
    separators: list[str],
    chunk_size: int,
    chunk_overlap: int
) -> list[str]:
    """
    Recursively split text using a list of separators.

    Args:
        text: Text to split
        separators: List of separators in order of preference
        chunk_size: Target chunk size
        chunk_overlap: Overlap between chunks

    Returns:
        List of text chunks
    """
    if not text:
        return []

    # If text is small enough, return as-is
    if len(text) <= chunk_size:
        return [text]

    # Try each separator
    for sep in separators:
        if sep in text:
            parts = text.split(sep)

            # Reconstruct chunks with separator preserved (except for space)
            chunks = []
            current_chunk = ""

            for i, part in enumerate(parts):
                # Add separator back (except for the first part)
                if i > 0 and sep != " ":
                    part = sep + part

                # Check if adding this part would exceed chunk size
                if len(current_chunk) + len(part) <= chunk_size:
                    current_chunk += part
                else:
                    # Save current chunk if not empty
                    if current_chunk:
                        chunks.append(current_chunk)

                    # Start new chunk with overlap
                    if chunk_overlap > 0 and current_chunk:
                        # Take last chunk_overlap chars from previous chunk
                        overlap_text = current_chunk[-chunk_overlap:]
                        current_chunk = overlap_text + part
                    else:
                        current_chunk = part

                    # If part itself is too big, recursively split with next separator
                    if len(current_chunk) > chunk_size and separators.index(sep) < len(separators) - 1:
                        sub_chunks = _recursive_split(
                            current_chunk,
                            separators[separators.index(sep) + 1:],
                            chunk_size,
                            chunk_overlap
                        )
                        if sub_chunks:
                            chunks.extend(sub_chunks[:-1])
                            current_chunk = sub_chunks[-1]

            # Don't forget the last chunk
            if current_chunk:
                chunks.append(current_chunk)

            return chunks

    # No separator found - force split at chunk_size
    chunks = []
    for i in range(0, len(text), chunk_size - chunk_overlap):
        chunks.append(text[i:i + chunk_size])

    return chunks


def load_all_documents(knowledge_base_path: str) -> list[dict]:
    """
    Load all documents from the FATES knowledge base.

    Args:
        knowledge_base_path: Path to fates-knowledge-base directory

    Returns:
        List of all document dictionaries
    """
    base = Path(knowledge_base_path)
    all_docs = []

    # Load markdown from codebase wiki
    wiki_path = base / "fates-codebase-wiki"
    if wiki_path.exists():
        wiki_docs = load_markdown_files(str(wiki_path))
        print(f"Loaded {len(wiki_docs)} documents from codebase wiki")
        all_docs.extend(wiki_docs)

    # Load markdown from official docs (if any)
    official_md_path = base / "fates-official-docs"
    if official_md_path.exists():
        official_md_docs = load_markdown_files(str(official_md_path))
        print(f"Loaded {len(official_md_docs)} markdown files from official docs")
        all_docs.extend(official_md_docs)

    # Load RST from official docs
    official_rst_path = base / "fates-official-docs" / "docs" / "source"
    if official_rst_path.exists():
        rst_docs = load_rst_files(str(official_rst_path))
        print(f"Loaded {len(rst_docs)} RST files from official docs")
        all_docs.extend(rst_docs)

    # Also load index.md from knowledge base root
    index_path = base / "index.md"
    if index_path.exists():
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()
        all_docs.append({
            'content': content,
            'source': 'index.md',
            'type': 'general',
            'title': 'FATES Knowledge Base Index',
            'format': 'markdown'
        })

    print(f"Total documents loaded: {len(all_docs)}")
    return all_docs


def load_knowledge_base(knowledge_base_path: str, kb_name: str = None) -> list[dict]:
    """
    Load documents from a knowledge base with flexible structure.

    Supports knowledge bases with structures like:
    - {kb_name}-codebase-wiki/  (markdown files)
    - {kb_name}-official-docs/ or {kb_name}-technical-docs/ (markdown/rst files)

    Args:
        knowledge_base_path: Path to knowledge base directory
        kb_name: Name of knowledge base (e.g., 'fates', 'elm').
                 If None, inferred from directory name.

    Returns:
        List of document dictionaries
    """
    base = Path(knowledge_base_path)
    all_docs = []

    if not base.exists():
        print(f"Warning: Knowledge base path does not exist: {knowledge_base_path}")
        return all_docs

    # Infer kb_name from directory if not provided
    if kb_name is None:
        dir_name = base.name.lower()
        if '-knowledge-base' in dir_name:
            kb_name = dir_name.replace('-knowledge-base', '')
        else:
            kb_name = dir_name

    print(f"\nLoading {kb_name.upper()} knowledge base from: {knowledge_base_path}")

    # Look for codebase wiki (various naming conventions)
    wiki_patterns = [
        f"{kb_name}-codebase-wiki",
        f"{kb_name}_codebase_wiki",
        "codebase-wiki",
        "wiki"
    ]
    for pattern in wiki_patterns:
        wiki_path = base / pattern
        if wiki_path.exists():
            wiki_docs = load_markdown_files(str(wiki_path))
            # Tag documents with knowledge base source
            for doc in wiki_docs:
                doc['kb_source'] = kb_name
            print(f"  Loaded {len(wiki_docs)} documents from {pattern}/")
            all_docs.extend(wiki_docs)
            break

    # Look for official/technical docs (various naming conventions)
    docs_patterns = [
        f"{kb_name}-official-docs",
        f"{kb_name}-technical-docs",
        "official-docs",
        "technical-docs",
        "docs"
    ]
    for pattern in docs_patterns:
        docs_path = base / pattern
        if docs_path.exists():
            # Load markdown files
            md_docs = load_markdown_files(str(docs_path))
            for doc in md_docs:
                doc['kb_source'] = kb_name
            if md_docs:
                print(f"  Loaded {len(md_docs)} markdown files from {pattern}/")
                all_docs.extend(md_docs)

            # Load RST files (check for docs/source subdirectory)
            rst_path = docs_path / "docs" / "source"
            if rst_path.exists():
                rst_docs = load_rst_files(str(rst_path))
                for doc in rst_docs:
                    doc['kb_source'] = kb_name
                if rst_docs:
                    print(f"  Loaded {len(rst_docs)} RST files from {pattern}/docs/source/")
                    all_docs.extend(rst_docs)
            break

    # Load index.md from root if exists
    index_path = base / "index.md"
    if index_path.exists():
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()
        all_docs.append({
            'content': content,
            'source': 'index.md',
            'type': 'general',
            'title': f'{kb_name.upper()} Knowledge Base Index',
            'format': 'markdown',
            'kb_source': kb_name
        })

    print(f"  Total from {kb_name.upper()}: {len(all_docs)} documents")
    return all_docs


def load_multiple_knowledge_bases(knowledge_base_paths: list[str]) -> list[dict]:
    """
    Load documents from multiple knowledge bases.

    Args:
        knowledge_base_paths: List of paths to knowledge base directories

    Returns:
        Combined list of document dictionaries from all knowledge bases
    """
    all_docs = []

    for kb_path in knowledge_base_paths:
        docs = load_knowledge_base(kb_path)
        all_docs.extend(docs)

    print(f"\n=== Total documents from all knowledge bases: {len(all_docs)} ===")
    return all_docs


# Default knowledge bases for A2MC
DEFAULT_KNOWLEDGE_BASES = [
    "docs/fates-knowledge-base",
    "docs/elm-knowledge-base",
]


if __name__ == "__main__":
    # Test the loader
    import sys

    kb_path = sys.argv[1] if len(sys.argv) > 1 else "docs/fates-knowledge-base"

    print(f"Loading documents from: {kb_path}")
    docs = load_all_documents(kb_path)

    print(f"\nChunking {len(docs)} documents...")
    chunks = chunk_documents(docs)

    print(f"Created {len(chunks)} chunks")
    print(f"\nSample chunk:")
    if chunks:
        sample = chunks[0]
        print(f"  Source: {sample['source']}")
        print(f"  Type: {sample['type']}")
        print(f"  Content preview: {sample['content'][:200]}...")
