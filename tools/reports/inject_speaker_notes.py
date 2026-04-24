#!/usr/bin/env python3
"""
Inject narration JSON into Marp slide deck as speaker notes.

Marp converts HTML comments at the end of each slide section into
PowerPoint speaker notes when exporting to PPTX. This tool reads a
slide_scripts.json (the per-slide narration used for video TTS) and
appends a `<!-- Speaker notes: ... -->` block after the visible content
of each slide in the corresponding .md file.

Usage:
    python tools/reports/inject_speaker_notes.py \\
        --slides path/to/A2MC_Session_X.md \\
        --scripts path/to/slide_scripts.json

The .md file is rewritten in place. Existing speaker-note comments
(matching the `<!-- Speaker notes:` prefix) are stripped first so the
operation is idempotent.

Exit codes:
    0 = success
    1 = slide/narration count mismatch or other content error
    2 = file not found

Author: Jing Tao with Claude
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(message)s')


SPEAKER_NOTE_PATTERN = re.compile(
    r'\n*<!--\s*Speaker notes:.*?-->\n*',
    re.DOTALL,
)


def split_front_matter(md: str) -> tuple:
    """Split Marp front matter from the body.

    Returns:
        (front_matter_with_trailing_newline, body)
    """
    lines = md.splitlines(keepends=True)
    seen = 0
    for i, line in enumerate(lines):
        if line.strip() == '---':
            seen += 1
            if seen == 2:
                return ''.join(lines[:i + 1]), ''.join(lines[i + 1:])
    raise ValueError("Could not find Marp front matter (need two '---' lines)")


def split_slides(body: str) -> list:
    """Split the body into a list of (kind, text) tuples.

    kind is 'slide' for slide content and 'sep' for slide separator lines.
    """
    chunks = []
    current = []
    for line in body.splitlines(keepends=True):
        if line.strip() == '---':
            if current:
                chunks.append(('slide', ''.join(current)))
                current = []
            chunks.append(('sep', line))
        else:
            current.append(line)
    if current:
        chunks.append(('slide', ''.join(current)))
    return chunks


def strip_existing_notes(slide_text: str) -> str:
    """Remove any existing `<!-- Speaker notes: ... -->` block."""
    return SPEAKER_NOTE_PATTERN.sub('\n', slide_text).rstrip() + '\n'


def append_speaker_note(slide_text: str, narration: str) -> str:
    """Append a speaker-notes HTML comment after slide content."""
    cleaned = strip_existing_notes(slide_text).rstrip('\n')
    note_block = f"\n\n<!--\nSpeaker notes:\n{narration.strip()}\n-->\n"
    return cleaned + note_block


def inject(slides_path: Path, scripts_path: Path) -> int:
    """Inject narration into slides_path. Returns number of slides updated."""
    md = slides_path.read_text(encoding='utf-8')
    narrations = json.loads(scripts_path.read_text(encoding='utf-8'))

    front, body = split_front_matter(md)
    chunks = split_slides(body)

    # Identify the chunks that are real slides (non-empty slide chunks).
    slide_chunk_indices = [
        i for i, (kind, text) in enumerate(chunks)
        if kind == 'slide' and text.strip()
    ]

    if len(slide_chunk_indices) != len(narrations):
        raise ValueError(
            f"Slide count mismatch: deck has {len(slide_chunk_indices)} "
            f"slides but narration JSON has {len(narrations)} entries."
        )

    for slide_idx, chunk_idx in enumerate(slide_chunk_indices):
        narration = narrations[slide_idx].get('narration', '').strip()
        if not narration:
            logger.warning(
                f"  slide {slide_idx + 1}: narration is empty, skipping"
            )
            continue
        kind, text = chunks[chunk_idx]
        chunks[chunk_idx] = (kind, append_speaker_note(text, narration))

    new_body = ''.join(text for _, text in chunks)
    slides_path.write_text(front + new_body, encoding='utf-8')
    return len(slide_chunk_indices)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--slides', required=True, type=Path,
                        help='Path to the Marp slide markdown')
    parser.add_argument('--scripts', required=True, type=Path,
                        help='Path to the narration JSON')
    args = parser.parse_args()

    if not args.slides.exists():
        logger.error(f"Slides not found: {args.slides}")
        sys.exit(2)
    if not args.scripts.exists():
        logger.error(f"Scripts not found: {args.scripts}")
        sys.exit(2)

    try:
        n = inject(args.slides, args.scripts)
    except (ValueError, json.JSONDecodeError) as e:
        logger.error(f"ERROR: {e}")
        sys.exit(1)

    logger.info(f"Injected {n} speaker note blocks into {args.slides.name}")


if __name__ == "__main__":
    main()
