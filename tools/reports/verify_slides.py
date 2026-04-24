#!/usr/bin/env python3
"""
Verify a Marp slide deck PDF for content overflow.

Marp does not auto-shrink slide content to fit the page. When a slide has
more text/code/figures than the configured layout can hold, Marp silently
clips whatever runs past the bottom edge, producing PDFs where bullets
end mid-sentence and code blocks get sliced. This script catches that
failure mode by rendering each PDF page to PNG and inspecting the bottom
margin zone for non-background pixels.

Usage:
    python tools/reports/verify_slides.py --pdf path/to/slides.pdf
    python tools/reports/verify_slides.py --pdf path/to/slides.pdf --annotate
    python tools/reports/verify_slides.py --pdf path/to/slides.pdf --output report.txt

Exit codes:
    0 = all slides fit within their content area
    1 = one or more slides have content in the bottom margin (overflow)
    2 = setup error (PDF missing, pdftoppm not installed, etc.)

Use as a pre-flight check before invoking generate_video.py — the video
build is expensive (TTS calls, several minutes of ffmpeg work), so catching
clipped slides here saves time and re-runs.

Author: Jing Tao with Claude
"""

import argparse
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("ERROR: Pillow is required. Install with `pip install Pillow` or "
          "use ~/a2mc_env/bin/python3 (which has it preinstalled).", file=sys.stderr)
    sys.exit(2)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(message)s')


# Heuristics ------------------------------------------------------------

# Fraction of slide height to inspect at the bottom (default 4% = ~30 px at 720 px).
# Marp's default `section { padding: 40px 60px }` leaves about 5-6% of vertical
# space as bottom margin. Anything in the bottom 4% indicates content has been
# pushed past where it should comfortably stop.
DEFAULT_MARGIN_FRAC = 0.04

# Pixel brightness below which a pixel counts as "content" (text/figure ink)
# rather than background. Anti-aliased glyph edges can be in the 220-250 range,
# so 250 is a permissive threshold that still excludes pure-white background.
DEFAULT_BRIGHTNESS_THRESHOLD = 250

# Fraction of margin pixels that must be dark before flagging overflow.
# Empirically, a clean blank margin reads ~0.0001-0.001. A clipped slide
# reads 0.02-0.10. The 0.005 (0.5%) threshold separates the two cleanly.
DEFAULT_OVERFLOW_FRACTION = 0.005

# Width fraction occupied by the page-number marker at the bottom-right.
# Marp paginate puts the slide number in the bottom-right corner; we mask
# it out so it doesn't trigger false positives on otherwise-clean slides.
PAGINATION_MASK_WIDTH_FRAC = 0.10
PAGINATION_MASK_HEIGHT_FRAC = 0.80  # of the inspected margin band height


def render_pdf_to_pngs(pdf_path: Path, output_dir: Path, dpi: int = 150) -> list:
    """Convert PDF pages to PNG files using pdftoppm.

    Returns:
        Sorted list of PNG paths, one per page.
    """
    pdftoppm = shutil.which('pdftoppm')
    if not pdftoppm:
        raise RuntimeError(
            "pdftoppm not found in PATH. Install with `brew install poppler` "
            "(macOS) or `apt-get install poppler-utils` (Linux)."
        )

    output_prefix = output_dir / "page"
    result = subprocess.run(
        [pdftoppm, '-r', str(dpi), '-png', str(pdf_path), str(output_prefix)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"pdftoppm failed with exit code {result.returncode}:\n{result.stderr}"
        )

    pngs = sorted(output_dir.glob("page-*.png"))
    if not pngs:
        raise RuntimeError(f"pdftoppm produced no PNG files in {output_dir}")
    return pngs


def detect_overflow(
    png_path: Path,
    margin_frac: float = DEFAULT_MARGIN_FRAC,
    brightness_threshold: int = DEFAULT_BRIGHTNESS_THRESHOLD,
    overflow_fraction: float = DEFAULT_OVERFLOW_FRACTION,
) -> dict:
    """Inspect the bottom margin of a slide image for clipped text content.

    A clean slide has a near-white margin band at the bottom. A clipped slide
    has text or code-block edges intruding into that band — but a slide with
    a `bg right:55% fit` figure ALSO has dark pixels in the bottom margin
    band, because the figure extends to the page edge by design.

    The heuristic distinguishes the two:

      1. Clean slide: no dark pixels anywhere in the margin band.

      2. Normal-padding slide: dark pixels exist in the upper part of the
         margin (last_dark_row_from_bottom > 5) but the literal bottom
         edge is clear. This is natural — the section padding leaves ~5-10
         px of true blank space below the lowest content line.

      3. Bg figure: dark pixels distributed UNIFORMLY across nearly all
         rows of the margin band (a figure that fills its container fills
         the whole band, top to bottom). Content is concentrated on the
         RIGHT side of the slide. The LEFT half of the band is clean.

      4. Clipped text: dark pixels CONCENTRATED in the bottommost few rows
         (the last visible line of text that didn't fit). Often left-aligned
         or distributed across the full slide width. The LEFT half of the
         band has measurable dark fraction.

      5. Text clipped ON TOP OF a bg figure: figure-like uniform pattern on
         the right + extra dark pixels on the left half near the bottom.

    The verifier flags cases 4 and 5 as overflow.

    Args:
        png_path: PNG of one rendered slide page.
        margin_frac: Fraction of slide height to inspect at the bottom.
        brightness_threshold: 0-255 brightness below which a pixel is "dark".
        overflow_fraction: Fraction of dark pixels above which the slide is
            flagged as overflowing.

    Returns:
        Dict with:
            'overflow':           bool
            'reason':             str — one of
                                    'clean',
                                    'normal_padding',
                                    'bg_figure',
                                    'clipped_text',
                                    'text_clipped_on_figure'
            'fraction_dark':      float — overall dark fraction in margin
            'left_half_fraction': float — dark fraction in left half (after
                                          masking pag corner)
            'last_dark_row':      int — pixel rows from bottom edge
            'rows_with_content':  int — # margin rows containing any dark
            'margin_height_px':   int
    """
    img = Image.open(png_path).convert('L')  # grayscale
    width, height = img.size

    margin_height = max(int(height * margin_frac), 12)
    bottom = img.crop((0, height - margin_height, width, height))

    # Mask the pagination marker (bottom-right corner)
    bottom_for_analysis = bottom.copy()
    draw = ImageDraw.Draw(bottom_for_analysis)
    pag_w = int(width * PAGINATION_MASK_WIDTH_FRAC)
    pag_h = int(margin_height * PAGINATION_MASK_HEIGHT_FRAC)
    draw.rectangle(
        (width - pag_w, margin_height - pag_h, width, margin_height),
        fill=255,
    )

    # Per-row dark pixel counts (full margin width minus the pag mask)
    rows_dark = []
    for row_idx in range(margin_height):
        row_strip = bottom_for_analysis.crop((0, row_idx, width, row_idx + 1))
        dark = sum(1 for p in row_strip.getdata() if p < brightness_threshold)
        rows_dark.append(dark)

    total_dark = sum(rows_dark)
    n_pixels = margin_height * width
    fraction_dark = total_dark / n_pixels

    # Bottommost row with dark content
    last_dark_row_from_bottom = 0
    for row_idx in range(margin_height - 1, -1, -1):
        if rows_dark[row_idx] > 0:
            last_dark_row_from_bottom = margin_height - row_idx
            break

    # Rows with at least one dark pixel
    rows_with_content = sum(1 for c in rows_dark if c > 0)

    # Left-half-only dark fraction (after pag mask). Used to detect text
    # clipping that sits on top of a bg right:55% figure.
    half_w = width // 2
    left_half = bottom_for_analysis.crop((0, 0, half_w, margin_height))
    left_pixels = list(left_half.getdata())
    left_dark = sum(1 for p in left_pixels if p < brightness_threshold)
    left_half_fraction = left_dark / len(left_pixels)

    common = {
        'fraction_dark': fraction_dark,
        'left_half_fraction': left_half_fraction,
        'last_dark_row': last_dark_row_from_bottom,
        'rows_with_content': rows_with_content,
        'margin_height_px': margin_height,
    }

    # Decision tree

    # Case 1: clean — nothing in margin
    if total_dark == 0:
        return {'overflow': False, 'reason': 'clean', **common}

    # Case 2: normal padding — content sits well above the literal bottom
    # edge (last dark row > 5 px from bottom). This is what a clean Marp
    # slide looks like when the lowest line of text happens to be near the
    # bottom of the content area.
    if last_dark_row_from_bottom > 5 and fraction_dark < 0.05:
        return {'overflow': False, 'reason': 'normal_padding', **common}

    # Content is at or near the literal bottom edge. Decide whether it's
    # a figure (uniformly distributed across margin rows) or clipped text
    # (concentrated near the bottom).
    figure_like = rows_with_content >= margin_height * 0.85

    # Case 3: bg figure — content fills almost all rows of the margin band
    # uniformly, AND the left half is clean. The figure is intentionally
    # extending to the page edge.
    if figure_like and left_half_fraction < overflow_fraction:
        return {'overflow': False, 'reason': 'bg_figure', **common}

    # Case 5: text on figure — figure-like distribution on the right but
    # the left half has measurable dark content (clipped text).
    if figure_like and left_half_fraction >= overflow_fraction:
        return {'overflow': True, 'reason': 'text_clipped_on_figure', **common}

    # Case 4: clipped text — content concentrated in a few bottom rows.
    return {'overflow': True, 'reason': 'clipped_text', **common}


def annotate_overflow(
    png_path: Path,
    output_path: Path,
    margin_frac: float = DEFAULT_MARGIN_FRAC,
    overflow: bool = False,
) -> None:
    """Save a copy of the PNG with the analyzed bottom strip outlined.

    Color-codes the overflow band: red if overflow detected, green if clean.
    Useful for visually verifying false positives/negatives during calibration.
    """
    img = Image.open(png_path).convert('RGB')
    width, height = img.size
    margin_height = max(int(height * margin_frac), 12)

    color = (220, 30, 30) if overflow else (40, 180, 40)
    draw = ImageDraw.Draw(img)
    draw.rectangle(
        (0, height - margin_height, width - 1, height - 1),
        outline=color,
        width=4,
    )
    img.save(output_path)


def verify_pdf(
    pdf_path: Path,
    dpi: int = 150,
    margin_frac: float = DEFAULT_MARGIN_FRAC,
    brightness_threshold: int = DEFAULT_BRIGHTNESS_THRESHOLD,
    overflow_fraction: float = DEFAULT_OVERFLOW_FRACTION,
    annotate: bool = False,
) -> dict:
    """Run overflow verification on a PDF.

    Returns:
        Dict with 'results' (list of per-slide dicts) and 'n_overflow' (int).
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        logger.info(f"Rendering {pdf_path.name} at {dpi} DPI...")
        pngs = render_pdf_to_pngs(pdf_path, tmp_dir, dpi=dpi)
        logger.info(f"  {len(pngs)} pages")

        if annotate:
            ann_dir = pdf_path.parent / f"{pdf_path.stem}_overflow_annotations"
            ann_dir.mkdir(exist_ok=True)
            logger.info(f"  Annotated PNGs will be saved to: {ann_dir}")

        results = []
        for i, png in enumerate(pngs, start=1):
            r = detect_overflow(
                png,
                margin_frac=margin_frac,
                brightness_threshold=brightness_threshold,
                overflow_fraction=overflow_fraction,
            )
            r['slide'] = i
            results.append(r)

            if annotate:
                annotate_overflow(
                    png,
                    ann_dir / f"slide_{i:02d}.png",
                    margin_frac=margin_frac,
                    overflow=r['overflow'],
                )

        n_overflow = sum(1 for r in results if r['overflow'])
        return {'results': results, 'n_overflow': n_overflow, 'n_total': len(results)}


def format_report(pdf_path: Path, verification: dict) -> str:
    """Format verification results as a human-readable text report."""
    results = verification['results']
    n_overflow = verification['n_overflow']
    n_total = verification['n_total']

    lines = []
    lines.append("")
    lines.append(f"Slide overflow report: {pdf_path.name}")
    lines.append("=" * 64)
    lines.append(f"  Pages:             {n_total}")
    lines.append(f"  Overflow detected: {n_overflow}/{n_total}")
    lines.append("")
    lines.append(f"  {'Slide':>6}  {'Status':<10}  {'Reason':<24}  {'%Dark':>7}  {'%Left':>7}  {'LastRow':>8}")
    lines.append(f"  {'-'*6}  {'-'*10}  {'-'*24}  {'-'*7}  {'-'*7}  {'-'*8}")
    for r in results:
        status = "OVERFLOW" if r['overflow'] else "ok"
        lines.append(
            f"  {r['slide']:>6}  {status:<10}  {r['reason']:<24}  "
            f"{r['fraction_dark']*100:>6.2f}%  "
            f"{r['left_half_fraction']*100:>6.2f}%  "
            f"{r['last_dark_row']:>8}"
        )
    lines.append("")
    if n_overflow:
        bad_slides = [str(r['slide']) for r in results if r['overflow']]
        lines.append(f"FAIL: {n_overflow} slide(s) have content in the bottom margin.")
        lines.append(f"      Affected slides: {', '.join(bad_slides)}")
        lines.append("")
        lines.append("Likely causes:")
        lines.append("  - Too many bullet points or table rows for the slide height")
        lines.append("  - Tall code blocks that don't fit at the configured font size")
        lines.append("  - Two-column layouts where one column overflows")
        lines.append("  - Section padding too tight for the chosen content density")
        lines.append("")
        lines.append("Fixes:")
        lines.append("  - Split the overflowing slide into two")
        lines.append("  - Reduce bullet count or shorten bullet text")
        lines.append("  - Use <style scoped> to override font-size/padding for that slide only")
        lines.append("  - For figures, use `![bg fit](figures/x.png)` so Marp scales to fit")
    else:
        lines.append("PASS: all slides fit within their content area.")
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Verify Marp slide PDF for content overflow.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('--pdf', required=True, type=Path,
                        help='Path to the slide deck PDF to verify')
    parser.add_argument('--dpi', type=int, default=150,
                        help='Render DPI (default: 150)')
    parser.add_argument('--margin-frac', type=float, default=DEFAULT_MARGIN_FRAC,
                        help=f'Bottom margin fraction to inspect '
                             f'(default: {DEFAULT_MARGIN_FRAC})')
    parser.add_argument('--brightness-threshold', type=int, default=DEFAULT_BRIGHTNESS_THRESHOLD,
                        help=f'Pixel brightness below which a pixel is "dark" '
                             f'(default: {DEFAULT_BRIGHTNESS_THRESHOLD})')
    parser.add_argument('--overflow-fraction', type=float, default=DEFAULT_OVERFLOW_FRACTION,
                        help=f'Fraction of dark pixels above which the slide '
                             f'is flagged (default: {DEFAULT_OVERFLOW_FRACTION})')
    parser.add_argument('--annotate', action='store_true',
                        help='Save PNGs with the bottom margin band outlined '
                             '(red = overflow, green = ok)')
    parser.add_argument('--output', type=Path, default=None,
                        help='Write report to this file (default: stdout)')

    args = parser.parse_args()

    try:
        verification = verify_pdf(
            args.pdf,
            dpi=args.dpi,
            margin_frac=args.margin_frac,
            brightness_threshold=args.brightness_threshold,
            overflow_fraction=args.overflow_fraction,
            annotate=args.annotate,
        )
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(2)
    except RuntimeError as e:
        logger.error(str(e))
        sys.exit(2)

    report = format_report(args.pdf, verification)
    if args.output:
        args.output.write_text(report)
        logger.info(f"Report written: {args.output}")
        print(report)
    else:
        print(report)

    sys.exit(1 if verification['n_overflow'] else 0)


if __name__ == "__main__":
    main()
