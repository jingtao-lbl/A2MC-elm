#!/usr/bin/env python3
"""
convert_official_docs.py - Convert FATES tech-doc RST source to Markdown.

Reads every *.rst under docs/fates-knowledge-base/fates-official-docs/docs/source/,
runs pandoc with markdown_strict+pipe_tables+raw_tex output format, and writes
to a parallel _converted_md/ tree at the same level. Preserves the RST in place
as the upstream artifact (we don't re-render from upstream — we render OUR
local snapshot for reproducibility).

Run once when the upstream tech doc is refreshed (rare; the upstream doc has
no version selector and is essentially single-track per
memory/dev_logs/20260505a_FATES_Official_Docs_RST_To_Markdown_Conversion_Plan.md).

Why pandoc not Sphinx-build: pandoc handles RST directives directly without
needing a working Sphinx environment + intersphinx_mapping resolution. The
output isn't pixel-perfect rendering, but it's clean enough for embedding
and human reading. RST :math: directives become LaTeX `$...$` (embedding-
friendly), :ref: becomes plain markdown links, section underlines become
`#`-style headings.

Author: Jing Tao with Claude
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = (
    REPO_ROOT
    / "docs"
    / "fates-knowledge-base"
    / "fates-official-docs"
    / "docs"
    / "source"
)
OUT_DIR_NAME = "_converted_md"
OUT_ROOT = SRC_ROOT / OUT_DIR_NAME

# markdown_strict avoids GitHub-specific extensions (portable);
# +pipe_tables lets RST grid tables survive as | tables;
# +raw_tex lets math survive as $...$ / $$...$$ (embedding-friendly).
PANDOC_FMT = "markdown_strict+pipe_tables+raw_tex"


def find_rst_files() -> list[Path]:
    """All *.rst under SRC_ROOT, excluding anything inside _converted_md/."""
    files: list[Path] = []
    for p in sorted(SRC_ROOT.rglob("*.rst")):
        if OUT_DIR_NAME in p.parts:
            continue
        files.append(p)
    return files


def convert_one(rst_path: Path) -> Path:
    """Convert one .rst to .md at the mirrored _converted_md/ location."""
    rel = rst_path.relative_to(SRC_ROOT)
    out_path = (OUT_ROOT / rel).with_suffix(".md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # --resource-path: lets pandoc find files referenced by directives like
    # `.. csv-table:: ... :file: images/trs_params.csv`. Without this, pandoc
    # aborts with "File images/trs_params.csv not found in resource path."
    # Pass both SRC_ROOT (for ../images/...) and the file's parent dir
    # (for sibling references).
    cmd = [
        "pandoc",
        "-f",
        "rst",
        "-t",
        PANDOC_FMT,
        f"--resource-path={SRC_ROOT}:{rst_path.parent}",
        "-o",
        str(out_path),
        str(rst_path),
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"pandoc failed on {rst_path.relative_to(SRC_ROOT)}: "
            f"exit={result.returncode}\nstderr={result.stderr.strip()}"
        )
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert FATES tech-doc RST source to Markdown via pandoc."
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove existing _converted_md/ tree before converting",
    )
    args = parser.parse_args(argv)

    if not SRC_ROOT.exists():
        print(f"ERROR: source tree missing at {SRC_ROOT}", file=sys.stderr)
        return 2

    if args.clean and OUT_ROOT.exists():
        print(f"Removing existing {OUT_ROOT.relative_to(REPO_ROOT)}...")
        shutil.rmtree(OUT_ROOT)

    OUT_ROOT.mkdir(exist_ok=True)

    rst_files = find_rst_files()
    print(f"Converting {len(rst_files)} RST files via pandoc {PANDOC_FMT}...")

    for rst in rst_files:
        out = convert_one(rst)
        rel_in = rst.relative_to(SRC_ROOT)
        rel_out = out.relative_to(SRC_ROOT)
        print(f"  {rel_in} -> {rel_out}")

    print(f"\nDone. Converted markdown lives at:")
    print(f"  {OUT_ROOT}")
    print(f"\nNext: rebuild the api-43-1 RAG to ingest the converted markdown:")
    print(f"  python scripts/build_rag_index.py --rebuild --profile api-43-1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
