#!/usr/bin/env python3
"""
A2MC Session Report Video Generator

Converts a Marp PDF slide deck + a JSON narration script into a narrated MP4 video.

Usage:
    # 1. Generate PDF from Marp markdown:
    npx @marp-team/marp-cli session_slides.md --pdf --allow-local-files

    # 2. Create narration script (slide_scripts.json):
    [
        {"slide": 1, "title": "Title Slide", "narration": "Welcome to...", "page": 1},
        {"slide": 2, "title": "Overview", "narration": "This session...", "page": 2},
        ...
    ]

    # 3. Generate video:
    python generate_video.py --pdf session_slides.pdf --scripts slide_scripts.json

    # Or with explicit output name:
    python generate_video.py --pdf session_slides.pdf --scripts slide_scripts.json \
        --output session_video.mp4

Requires: ffmpeg, poppler (pdftoppm), openai Python package (optional, falls back to macOS say)

Author: Jing Tao with Claude
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Load .env from A2MC root if available
_root = Path(__file__).resolve().parent.parent.parent
_env_file = _root / ".env"
if _env_file.exists():
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, val = line.partition('=')
                val = val.strip()
                if val.startswith('$'):
                    val = os.environ.get(val[1:], val)
                os.environ.setdefault(key.strip(), val)

# Try to import OpenAI
try:
    from openai import OpenAI
    USE_OPENAI_TTS = True
except ImportError:
    print("Warning: openai package not installed. Falling back to macOS 'say' command.")
    USE_OPENAI_TTS = False

# Default TTS settings
DEFAULT_VOICE = "nova"       # alloy, echo, fable, onyx, nova, shimmer
DEFAULT_MODEL = "tts-1-hd"   # tts-1 (fast/cheap) or tts-1-hd (high quality)


# ============================================================
# Pipeline Functions
# ============================================================

def extract_pdf_slides(pdf_path, output_dir):
    """Extract PDF pages to PNG images using pdftoppm."""
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / "page"
    cmd = ['pdftoppm', '-png', '-r', '150', str(pdf_path), str(prefix)]
    print(f"  Extracting PDF slides: {pdf_path}")
    subprocess.run(cmd, check=True)
    pages = sorted(output_dir.glob("page-*.png"))
    print(f"  Extracted {len(pages)} pages")
    return pages


def generate_slide_image(source_image, output_path):
    """Scale and pad image to 1920x1080."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        'ffmpeg', '-y', '-i', str(source_image),
        '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,'
               'pad=1920:1080:(ow-iw)/2:(oh-ih)/2:white',
        '-frames:v', '1',
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def generate_audio_openai(text, output_path, voice=DEFAULT_VOICE, model=DEFAULT_MODEL):
    """Generate speech audio using OpenAI TTS API."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    client = OpenAI()
    clean_text = re.sub(r'\s+', ' ', text).strip()
    with client.audio.speech.with_streaming_response.create(
        model=model,
        voice=voice,
        input=clean_text,
        speed=1.0
    ) as response:
        response.stream_to_file(str(output_path))


def generate_audio_macos(text, output_path):
    """Fallback: Generate speech using macOS 'say' command."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    aiff_path = output_path.with_suffix('.aiff')
    clean_text = re.sub(r'\s+', ' ', text).strip()
    subprocess.run(['say', '-o', str(aiff_path), clean_text], check=True)
    subprocess.run([
        'ffmpeg', '-y', '-i', str(aiff_path),
        '-c:a', 'libmp3lame', '-b:a', '192k',
        str(output_path)
    ], check=True, capture_output=True)
    aiff_path.unlink(missing_ok=True)


def get_audio_duration(audio_path):
    """Get duration of audio file in seconds."""
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', str(audio_path)],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


def create_slide_video(image_path, audio_path, output_path):
    """Combine a slide image + audio into a video segment."""
    duration = get_audio_duration(audio_path)
    total_duration = duration + 1.0  # 1 second padding
    cmd = [
        'ffmpeg', '-y',
        '-loop', '1', '-i', str(image_path),
        '-i', str(audio_path),
        '-c:v', 'libx264', '-tune', 'stillimage',
        '-c:a', 'aac', '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        '-t', str(total_duration),
        '-shortest',
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return duration


def concatenate_videos(video_files, output_path):
    """Concatenate video segments into final video."""
    list_file = output_path.parent / "video_list.txt"
    with open(list_file, 'w') as f:
        for video in video_files:
            f.write(f"file '{video.name}'\n")

    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat', '-safe', '0',
        '-i', str(list_file),
        '-c', 'copy',
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def load_slide_scripts(scripts_path):
    """Load slide scripts from JSON file.

    Expected format:
    [
        {"slide": 1, "title": "Title", "narration": "Text...", "page": 1},
        ...
    ]
    """
    with open(scripts_path) as f:
        scripts = json.load(f)

    # Validate
    for entry in scripts:
        for key in ("slide", "title", "narration", "page"):
            if key not in entry:
                raise ValueError(f"Missing '{key}' in slide script entry: {entry}")

    return scripts


# ============================================================
# Main Pipeline
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate narrated video from Marp PDF slides + JSON narration script"
    )
    parser.add_argument("--pdf", required=True, help="Path to PDF slide deck")
    parser.add_argument("--scripts", required=True, help="Path to JSON narration script file")
    parser.add_argument("--output", default=None,
                        help="Output video filename (default: derived from PDF name)")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: video_output/ next to PDF)")
    parser.add_argument("--voice", default=DEFAULT_VOICE,
                        help=f"OpenAI TTS voice (default: {DEFAULT_VOICE})")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"OpenAI TTS model (default: {DEFAULT_MODEL})")

    args = parser.parse_args()

    pdf_path = Path(args.pdf).resolve()
    scripts_path = Path(args.scripts).resolve()

    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        sys.exit(1)

    if not scripts_path.exists():
        print(f"ERROR: Scripts file not found: {scripts_path}")
        sys.exit(1)

    # Set output directory
    if args.output_dir:
        output_dir = Path(args.output_dir).resolve()
    else:
        output_dir = pdf_path.parent / "video_output"

    slides_dir = output_dir / "slides"
    audio_dir = output_dir / "audio"
    pdf_slides_dir = output_dir / "pdf_slides"

    # Determine output filename
    if args.output:
        final_output = output_dir / args.output
    else:
        final_output = output_dir / f"{pdf_path.stem}.mp4"

    # Load scripts
    slide_scripts = load_slide_scripts(scripts_path)

    print("=" * 60)
    print("A2MC Session Report Video Generator")
    print("=" * 60)
    print(f"  PDF:     {pdf_path}")
    print(f"  Scripts: {scripts_path}")
    print(f"  Output:  {final_output}")
    print(f"  Slides:  {len(slide_scripts)}")
    print(f"  TTS:     {'OpenAI' if USE_OPENAI_TTS else 'macOS say'}")

    # Create output directories
    for d in [output_dir, slides_dir, audio_dir, pdf_slides_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Step 1: Extract PDF pages
    print("\n[Step 1/5] Extracting PDF slides...")
    extract_pdf_slides(pdf_path, pdf_slides_dir)

    # Step 2: Scale slides to 1920x1080
    print("\n[Step 2/5] Scaling slides to 1920x1080...")
    for entry in slide_scripts:
        slide_num = entry["slide"]
        title = entry["title"]
        pdf_page = entry["page"]

        page_pattern = f"page-{pdf_page:02d}.png"
        source = pdf_slides_dir / page_pattern
        if not source.exists():
            page_pattern = f"page-{pdf_page}.png"
            source = pdf_slides_dir / page_pattern
        if not source.exists():
            print(f"  WARNING: Page image not found for slide {slide_num} (page {pdf_page})")
            continue
        output = slides_dir / f"slide_{slide_num:02d}.png"
        generate_slide_image(source, output)
        print(f"  Slide {slide_num}: {title}")

    # Step 3: Generate audio
    tts_label = 'OpenAI TTS' if USE_OPENAI_TTS else 'macOS say'
    print(f"\n[Step 3/5] Generating audio ({tts_label})...")
    for entry in slide_scripts:
        slide_num = entry["slide"]
        title = entry["title"]
        narration = entry["narration"]

        audio_path = audio_dir / f"slide_{slide_num:02d}.mp3"
        if USE_OPENAI_TTS:
            generate_audio_openai(narration, audio_path, voice=args.voice, model=args.model)
        else:
            generate_audio_macos(narration, audio_path)
        print(f"  Slide {slide_num}: {title}")

    # Step 4: Create individual slide videos
    print("\n[Step 4/5] Creating slide videos...")
    video_files = []
    total_duration = 0
    for entry in slide_scripts:
        slide_num = entry["slide"]
        title = entry["title"]

        image_path = slides_dir / f"slide_{slide_num:02d}.png"
        audio_path = audio_dir / f"slide_{slide_num:02d}.mp3"
        video_path = output_dir / f"slide_{slide_num:02d}.mp4"

        if not image_path.exists() or not audio_path.exists():
            print(f"  SKIP slide {slide_num}: missing image or audio")
            continue

        duration = create_slide_video(image_path, audio_path, video_path)
        video_files.append(video_path)
        total_duration += duration
        print(f"  Slide {slide_num}: {title} ({duration:.1f}s)")

    # Step 5: Concatenate into final video
    print("\n[Step 5/5] Concatenating final video...")
    concatenate_videos(video_files, final_output)

    print("\n" + "=" * 60)
    print(f"DONE! Total duration: {total_duration:.0f}s ({total_duration/60:.1f} min)")
    print(f"Final video: {final_output}")
    print(f"\nPlay with: open {final_output}")
    print("=" * 60)


if __name__ == "__main__":
    main()
