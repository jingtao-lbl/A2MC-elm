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


# =============================================================================
# Mode-aware path-prefix tagging (Phase B Chunk B.2.3 — zero-leakage)
# =============================================================================
#
# Each entry maps a wiki source path GLOB to an `applies_in:` block. The path
# is matched against `chunk['source']` (relative to the wiki tree root). On
# match, chunks under that path inherit the listed flags via
# `tools.config.build_applies_in_flags()`. On no match, chunks get
# `applies_universal: True`.
#
# Source: docs/21_Mode_Aware_RAG_Phase_B_Implementation.md §B.2.3
# Audit: memory/dev_logs/20260429b_Phase_B_Wiki_And_YAML_Audit.md

# Globs evaluated against the chunk's `source` field. First match wins
# (the table is ordered most-specific to least-specific where it matters).
_WIKI_PATH_PREFIX_TAGS = [
    # ---- Tier 2 FATES feature flags (5 dirs / 11 docs) ----
    # Fire mechanisms: only applicable when SPITFIRE is on
    ("fire/", {
        "use_fates": [True],
        "fates_spitfire_mode": [1, 2],
    }),
    # Plant hydraulics: only when use_fates_planthydro=True
    ("biophysics/hydraulics/", {
        "use_fates": [True],
        "use_fates_planthydro": [True],
    }),
    # Logging mechanisms: only when use_fates_logging=True
    ("logging/", {
        "use_fates": [True],
        "use_fates_logging": [True],
    }),
    # ---- Inverse-tagged docs (apply when the feature is OFF) ----
    # BTRAN empirical pathway applies when hydraulics is OFF
    ("biophysics/transpiration.md", {
        "use_fates": [True],
        "use_fates_planthydro": [False],
    }),
    # Regular photosynthesis runs when prescribed_phys is OFF
    ("biophysics/photosynthesis.md", {
        "use_fates": [True],
        "use_fates_ed_prescribed_phys": [False],
    }),
    # ---- Theory-doc level filtering (zero-leakage) ----
    # CNP allocation theory: only PARTEH=2 + N or NP nutrient
    ("plant-physiology/parteh/cnp_allocation.md", {
        "use_fates": [True],
        "parteh_mode": [2],
        "nutrient": ["cn", "cnp"],
    }),
    # Nutrient uptake mechanics: only PARTEH=2 + N or NP nutrient
    ("plant-physiology/parteh/soil_plant_interface.md", {
        "use_fates": [True],
        "parteh_mode": [2],
        "nutrient": ["cn", "cnp"],
    }),
    # Carbon-only allocation theory: only PARTEH=1
    ("plant-physiology/parteh/carbon_only.md", {
        "use_fates": [True],
        "parteh_mode": [1],
    }),
    # CNP calibration playbook: PARTEH=2 + N or NP
    ("advanced/cnp_calibration_guide.md", {
        "use_fates": [True],
        "parteh_mode": [2],
        "nutrient": ["cn", "cnp"],
    }),
    # ECA/RD competition theory: PARTEH=2 + N or NP
    ("advanced/nutrient_competition.md", {
        "use_fates": [True],
        "parteh_mode": [2],
        "nutrient": ["cn", "cnp"],
    }),
    # Crown damage mortality: future use_fates_tree_damage flag (out of scope);
    # tag with use_fates only so it filters out for ELM-only runs
    ("plant-physiology/crown_damage.md", {
        "use_fates": [True],
    }),
    # ---- Official-docs PARTEH theory (parteh/* directory) ----
    # The files under fates-official-docs/docs/source/{,_converted_md/}parteh/
    # describe both PARTEH=1 carbon-only and PARTEH=2 CNP allocation in detail.
    # Naming convention: h1_* = carbon-only hypothesis, h2_* = CNP flexible
    # hypothesis. Other files (hypotheses, overview_domain, turnover) describe
    # the framework that applies regardless of mode and stay universal.
    # v2.99: also matches the converted markdown at parteh/h1_*.md / h2_*.md
    # since the basename-prefix match strips the directory.
    ("parteh/h1_", {
        "use_fates": [True],
        "parteh_mode": [1],
    }),
    ("parteh/h2_", {
        "use_fates": [True],
        "parteh_mode": [2],
        "nutrient": ["cn", "cnp"],
    }),
]


def path_prefix_tags(source: str) -> Optional[dict]:
    """Return the applies_in: block for a wiki source path, or None on no match.

    `source` is the chunk's `source` field (relative to the wiki tree root).

    Matching rules (first match wins, table order):
      - Pattern ending with ``/`` is a directory prefix; matches anything
        whose source starts with the pattern (e.g. ``fire/`` matches
        ``fire/ignition.md``).
      - Pattern ending with a literal filename (``.md`` or ``.rst``) is an
        exact-or-suffix match (handles wiki-tree-relative paths and absolute
        paths alike).
      - Other patterns are filename-prefix matches: ``parteh/h2_`` matches
        any source containing that substring at the start of the basename
        (e.g. ``parteh/h2_callom_flexstoich.rst``). Used for tagging
        groups of related files by name.

    Returns
    -------
    Optional[dict]
        The applies_in: dict if a path-prefix entry matches, None otherwise.
        None means the chunk is universal (applies_universal: True will be set).
    """
    if not source:
        return None
    for path_glob, tags in _WIKI_PATH_PREFIX_TAGS:
        if path_glob.endswith("/"):
            # Directory prefix
            if source.startswith(path_glob):
                return tags
        elif path_glob.endswith(".md") or path_glob.endswith(".rst"):
            # Specific filename match (exact or suffix)
            if source == path_glob or source.endswith("/" + path_glob):
                return tags
        else:
            # Filename-prefix substring (e.g. 'parteh/h2_')
            if path_glob in source:
                return tags
    return None


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


def _build_chunk_mode_flags(source: str) -> dict:
    """Build the applies_in_* metadata flags for a wiki chunk by source path.

    Looks up the path against `_WIKI_PATH_PREFIX_TAGS` and returns either
    per-axis flags (for a path-prefix match) or `{'applies_universal': True}`.
    """
    # Lazy import to avoid circular dependency at module load time
    from tools.config import build_applies_in_flags
    tags = path_prefix_tags(source)
    return build_applies_in_flags(tags)


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
        kb = doc.get('kb_source', '')
        # Prefix chunk_id with kb_source to avoid collisions when multiple
        # KBs have files with identical names (e.g., FATES index.md vs ELM index.md).
        id_prefix = f"{kb}/" if kb else ""
        # Mode-aware metadata: path-prefix tags (Phase B Chunk B.2.3)
        mode_flags = _build_chunk_mode_flags(doc['source'])

        for i, chunk_text in enumerate(doc_chunks):
            if len(chunk_text) >= min_chunk_size:
                chunk = {
                    'content': chunk_text,
                    'source': doc['source'],
                    'type': doc['type'],
                    'title': doc.get('title', ''),
                    'format': doc.get('format', 'unknown'),
                    'kb_source': kb,  # propagate to chunk
                    'chunk_id': f"{id_prefix}{doc['source']}::chunk_{i}",
                }
                chunk.update(mode_flags)
                chunks.append(chunk)

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

    # Load markdown from official docs (if any). Two paths:
    # (a) `_converted_md/` — pandoc-rendered markdown from RST source (v2.99+).
    #     Preferred: math directives become LaTeX, cross-refs become links,
    #     headings become #-style. Embedding-friendly and human-readable.
    # (b) Top-level `fates-official-docs/*.md` — any hand-written markdown
    #     (rare; reserved for future use).
    # (c) Legacy fallback: raw RST files. Kept so older snapshots still load,
    #     but flagged with a warning so users know to run the converter.
    official_md_converted = (
        base / "fates-official-docs" / "docs" / "source" / "_converted_md"
    )
    official_rst_path = base / "fates-official-docs" / "docs" / "source"

    if official_md_converted.exists():
        md_docs = load_markdown_files(str(official_md_converted))
        # Tag as official-docs source so downstream metadata (kb_source,
        # path-prefix tagging, applies_in:) treats them like the original RST
        # would have been treated.
        for d in md_docs:
            d["type"] = "official-docs"
        print(
            f"Loaded {len(md_docs)} converted markdown files from official docs"
        )
        all_docs.extend(md_docs)
    elif official_rst_path.exists():
        print(
            "WARNING: _converted_md/ not found; falling back to raw RST. "
            "Run scripts/convert_official_docs.py to generate clean markdown."
        )
        rst_docs = load_rst_files(str(official_rst_path))
        print(f"Loaded {len(rst_docs)} RST files from official docs (fallback)")
        all_docs.extend(rst_docs)

    # Top-level hand-written markdown alongside the official docs (if any)
    official_md_path = base / "fates-official-docs"
    if official_md_path.exists():
        # Only top-level .md files, not the converted tree we already loaded
        official_md_docs = [
            d for d in load_markdown_files(str(official_md_path))
            if "_converted_md" not in d.get("source", "")
        ]
        if official_md_docs:
            print(
                f"Loaded {len(official_md_docs)} top-level markdown files "
                f"from official docs"
            )
            all_docs.extend(official_md_docs)

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


def load_knowledge_base(
    knowledge_base_path: str,
    kb_name: str = None,
    wiki_subdir: str = None,
    docs_subdir: str = None,
) -> list[dict]:
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

    # Look for codebase wiki.
    # If `wiki_subdir` is supplied, use it explicitly (no probe). Required by
    # the version-association infrastructure: each milestone records which
    # commit-pinned wiki dir to load (e.g., 'fates-codebase-wiki-e027a40').
    # If unset, fall back to first-match-wins probe over canonical patterns.
    if wiki_subdir is not None:
        wiki_path = base / wiki_subdir
        if wiki_path.exists():
            wiki_docs = load_markdown_files(str(wiki_path))
            for doc in wiki_docs:
                doc['kb_source'] = kb_name
            print(f"  Loaded {len(wiki_docs)} documents from {wiki_subdir}/ (explicit wiki_subdir)")
            all_docs.extend(wiki_docs)
        else:
            print(f"  WARNING: explicit wiki_subdir '{wiki_subdir}' not found under {base}")
    else:
        wiki_patterns = [
            f"{kb_name}-codebase-wiki",
            f"{kb_name}_codebase_wiki",
            "codebase-wiki",
            "wiki",
        ]
        for pattern in wiki_patterns:
            wiki_path = base / pattern
            if wiki_path.exists():
                wiki_docs = load_markdown_files(str(wiki_path))
                for doc in wiki_docs:
                    doc['kb_source'] = kb_name
                print(f"  Loaded {len(wiki_docs)} documents from {pattern}/")
                all_docs.extend(wiki_docs)
                break

    # Look for official/technical docs. Same explicit-vs-probe pattern.
    # v2.99: when fates-official-docs/docs/source/_converted_md/ exists, the
    # markdown loader already picks up the pandoc-converted .md files (since
    # load_markdown_files recurses through .md). In that case we must NOT
    # also load the raw RST source, or we double-index the same content.
    def _has_converted_md(rst_path: Path) -> bool:
        return (rst_path / "_converted_md").exists()

    if docs_subdir is not None:
        docs_path = base / docs_subdir
        if docs_path.exists():
            md_docs = load_markdown_files(str(docs_path))
            for doc in md_docs:
                doc['kb_source'] = kb_name
            if md_docs:
                print(f"  Loaded {len(md_docs)} markdown files from {docs_subdir}/ (explicit docs_subdir)")
                all_docs.extend(md_docs)
            rst_path = docs_path / "docs" / "source"
            if rst_path.exists() and not _has_converted_md(rst_path):
                rst_docs = load_rst_files(str(rst_path))
                for doc in rst_docs:
                    doc['kb_source'] = kb_name
                if rst_docs:
                    print(f"  Loaded {len(rst_docs)} RST files from {docs_subdir}/docs/source/ (no _converted_md/ found)")
                    all_docs.extend(rst_docs)
            elif rst_path.exists():
                print(f"  Skipping RST loader for {docs_subdir}/docs/source/ (using _converted_md/ instead)")
        else:
            print(f"  WARNING: explicit docs_subdir '{docs_subdir}' not found under {base}")
    else:
        docs_patterns = [
            f"{kb_name}-official-docs",
            f"{kb_name}-technical-docs",
            "official-docs",
            "technical-docs",
            "docs",
        ]
        for pattern in docs_patterns:
            docs_path = base / pattern
            if docs_path.exists():
                md_docs = load_markdown_files(str(docs_path))
                for doc in md_docs:
                    doc['kb_source'] = kb_name
                if md_docs:
                    print(f"  Loaded {len(md_docs)} markdown files from {pattern}/")
                    all_docs.extend(md_docs)
                rst_path = docs_path / "docs" / "source"
                if rst_path.exists() and not _has_converted_md(rst_path):
                    rst_docs = load_rst_files(str(rst_path))
                    for doc in rst_docs:
                        doc['kb_source'] = kb_name
                    if rst_docs:
                        print(f"  Loaded {len(rst_docs)} RST files from {pattern}/docs/source/ (no _converted_md/ found)")
                        all_docs.extend(rst_docs)
                elif rst_path.exists():
                    print(f"  Skipping RST loader for {pattern}/docs/source/ (using _converted_md/ instead)")
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


def load_multiple_knowledge_bases(
    knowledge_base_paths: list[str],
    wiki_subdirs: list[str] = None,
    docs_subdirs: list[str] = None,
) -> list[dict]:
    """
    Load documents from multiple knowledge bases.

    Args:
        knowledge_base_paths: List of paths to knowledge base directories.
        wiki_subdirs: Optional list of explicit wiki subdir names, parallel to
            `knowledge_base_paths`. Use `None` for an entry to fall back to
            probe-based discovery for that KB. Length must match `knowledge_base_paths`
            if supplied.
        docs_subdirs: Same shape as `wiki_subdirs`, for official/technical docs.

    Returns:
        Combined list of document dictionaries from all knowledge bases.
    """
    all_docs = []
    n = len(knowledge_base_paths)

    if wiki_subdirs is not None and len(wiki_subdirs) != n:
        raise ValueError(
            f"wiki_subdirs length ({len(wiki_subdirs)}) must match "
            f"knowledge_base_paths length ({n})"
        )
    if docs_subdirs is not None and len(docs_subdirs) != n:
        raise ValueError(
            f"docs_subdirs length ({len(docs_subdirs)}) must match "
            f"knowledge_base_paths length ({n})"
        )

    for i, kb_path in enumerate(knowledge_base_paths):
        wiki_sd = wiki_subdirs[i] if wiki_subdirs is not None else None
        docs_sd = docs_subdirs[i] if docs_subdirs is not None else None
        docs = load_knowledge_base(
            kb_path, wiki_subdir=wiki_sd, docs_subdir=docs_sd
        )
        all_docs.extend(docs)

    print(f"\n=== Total documents from all knowledge bases: {len(all_docs)} ===")
    return all_docs


# Default knowledge bases for A2MC
DEFAULT_KNOWLEDGE_BASES = [
    "docs/fates-knowledge-base",
    "docs/elm-knowledge-base",
]


def load_parameter_descriptions(
    param_cdl_path: str,
    output_cdl_path: str = None,
    curated_yaml_data: Optional[dict] = None,
    elm_output_cdl_path: str = None,
) -> list[dict]:
    """Generate document chunks from CDL metadata for vector indexing.

    Each parameter generates a chunk like:
        "FATES Parameter: fates_alloc_storage_cushion
        Dimensions: fates_pft (PFT-specific)
        Units: unitless
        Description: Ratio of storage carbon to leaf carbon that plants target.
        Category: Allocation"

    Each output generates a chunk like:
        "FATES Output Variable: FATES_LEAFC
        Dimensions: time, lndgrid (site-level)
        Units: kg C m-2
        Description: Leaf carbon pool.
        Category: Biomass"

    Args:
        param_cdl_path: Path to FATES parameter CDL file
        output_cdl_path: Path to ELM-FATES output CDL file (optional)

    Returns:
        List of chunk dictionaries ready for add_documents()
    """
    chunks = []

    # Lazy import for mode-aware tagging
    from tools.config import build_applies_in_flags

    # Pre-build a name → applies_in lookup from curated YAML (B.2.2)
    yaml_params = (curated_yaml_data or {}).get('parameters') or {}
    yaml_outputs = (curated_yaml_data or {}).get('outputs') or {}

    # --- Parameter definitions ---
    if param_cdl_path:
        from .parameter_parser import FATESParameterParser, CATEGORIES
        try:
            parser = FATESParameterParser(param_cdl_path)
            params = parser.parse()

            for name, param in params.items():
                if param.is_string or name.endswith('_name'):
                    continue

                dims_str = ', '.join(param.dimensions) if param.dimensions else 'scalar'
                pft_note = ' (PFT-specific)' if param.is_pft_specific else ''
                cat_name = CATEGORIES.get(param.category_key, param.category_key)

                content = (
                    f"FATES Parameter: {name}\n"
                    f"Dimensions: {dims_str}{pft_note}\n"
                    f"Units: {param.units}\n"
                    f"Description: {param.long_name}\n"
                    f"Category: {cat_name}"
                )

                # Mode-aware metadata: inherit applies_in: from YAML entity
                # of the same name. Untagged parameters are universal.
                yaml_entry = yaml_params.get(name) or {}
                applies_in = yaml_entry.get('applies_in')
                inactive = bool(yaml_entry.get('inactive', False))
                mode_flags = build_applies_in_flags(applies_in)

                chunk = {
                    'content': content,
                    'source': f'fates_params_info.cdl::{name}',
                    'type': 'parameter_definition',
                    'title': f'Parameter: {name}',
                    'format': 'cdl',
                    'kb_source': 'fates',  # FATES parameter file
                    'chunk_id': f'param_def::{name}',
                    'entity_type': 'parameter',
                    'param_category': param.category_key,
                    'is_pft_specific': str(param.is_pft_specific),
                }
                chunk.update(mode_flags)
                if inactive:
                    chunk['inactive'] = True
                chunks.append(chunk)

            print(f"  Generated {len(chunks)} parameter definition chunks")
        except Exception as e:
            print(f"  Warning: Could not load parameter definitions: {e}")

    # --- Output variable definitions ---
    # Two-CDL setup (v2.96+): FATES core registry + ELM core registry.
    # Each is parsed independently and merged into all_vars. ELM vars override
    # only on duplicate name (rare), with the FATES CDL source winning.
    if output_cdl_path or elm_output_cdl_path:
        from .output_parser import FATESOutputParser
        try:
            all_vars = {}
            sources = {}  # name -> source CDL filename for the chunk's `source` field

            # FATES outputs first (existing path)
            if output_cdl_path:
                fates_parser = FATESOutputParser(output_cdl_path)
                fates_vars = fates_parser.get_fates_variables()
                key_elm = fates_parser.get_key_elm_variables()
                fates_basename = Path(output_cdl_path).name
                for name, var in {**fates_vars, **key_elm}.items():
                    all_vars[name] = var
                    sources[name] = fates_basename

            # ELM-side outputs (Phase B follow-up; v2.96+).
            # Skip names already in all_vars (FATES CDL takes precedence on dupe).
            if elm_output_cdl_path:
                elm_parser = FATESOutputParser(elm_output_cdl_path)
                # The ELM CDL has the SAME structure (parser doesn't care that
                # the file represents ELM core variables — variable shapes
                # and CDL syntax are identical). Both methods retrieve
                # variables; for the ELM-only CDL we use parse() directly
                # to get all variables without the FATES_ filter.
                elm_all = elm_parser.parse()
                elm_basename = Path(elm_output_cdl_path).name
                added_elm = 0
                for name, var in elm_all.items():
                    if name in all_vars:
                        continue
                    all_vars[name] = var
                    sources[name] = elm_basename
                    added_elm += 1

            out_count = 0
            for name, var in all_vars.items():
                dims_str = ', '.join(var.dimensions) if var.dimensions else 'scalar'
                level_note = f' ({var.dimension_level}-level)' if var.dimension_level != 'other' else ''

                content = (
                    f"{'FATES' if var.is_fates else 'ELM'} Output Variable: {name}\n"
                    f"Dimensions: {dims_str}{level_note}\n"
                    f"Units: {var.units}\n"
                    f"Description: {var.long_name}\n"
                    f"Category: {var.category}"
                )

                # Mode-aware metadata: inherit applies_in: from YAML output
                # entity of the same name; universal otherwise.
                yaml_entry = yaml_outputs.get(name) or {}
                applies_in = yaml_entry.get('applies_in')
                mode_flags = build_applies_in_flags(applies_in)

                chunk = {
                    'content': content,
                    'source': f'{sources.get(name, "output.cdl")}::{name}',
                    'type': 'output_definition',
                    'title': f'Output: {name}',
                    'format': 'cdl',
                    # is_fates is set per output variable in FATESOutputParser:
                    # output CDL contains both FATES_* (FATES) and ELM bare-name vars (ELM)
                    'kb_source': 'fates' if var.is_fates else 'elm',
                    'chunk_id': f'output_def::{name}',
                    'entity_type': 'output',
                    'dimension_level': var.dimension_level,
                    'output_category': var.category,
                }
                chunk.update(mode_flags)
                chunks.append(chunk)
                out_count += 1

            print(f"  Generated {out_count} output definition chunks")
        except Exception as e:
            print(f"  Warning: Could not load output definitions: {e}")

    return chunks


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
