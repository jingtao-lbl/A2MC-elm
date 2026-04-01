# Presentation Workflow: From A2MC Session Logs to Narrated Video

**Purpose:** Step-by-step guide for creating a narrated presentation from any A2MC calibration session.
**Author:** Jing Tao with Claude
**Last Updated:** March 11, 2026

---

## Overview

This workflow takes the raw logs from an A2MC calibration session and produces:
1. A **Marp Markdown** slide deck (`.md`)
2. A **PowerPoint** file (`.pptx`) for manual review/editing
3. A **narrated MP4 video** with TTS audio

```
Session logs ──> Marp Markdown ──> PDF ──> PPTX
  (phase3, phase4, ...)         ──> PDF ──> PNG pages ──> + TTS audio ──> MP4 video
```

---

## Prerequisites

### Tools

| Tool | Install | Purpose |
|------|---------|---------|
| Marp CLI | `npm install -g @marp-team/marp-cli` | Markdown → PDF / PPTX |
| pdftoppm | `brew install poppler` | PDF → PNG images |
| ffmpeg | `brew install ffmpeg` | Image + audio → video |
| OpenAI Python | `pip install openai` (in a2mc_env) | TTS audio generation |

### Environment

```bash
# Activate the Python environment with openai installed
source ~/a2mc_env/bin/activate

# Ensure OPENAI_API_KEY is set (loaded from A2MC/.env by generate_video.py)
# Or export manually:
export OPENAI_API_KEY="sk-..."
```

---

## Step 1: Gather Session Logs

### Identify the session

Each A2MC run produces logs tagged with a session ID (`YYYYMMDD_HHMMSS`):

```bash
# Find all logs for a session
SESSION_ID="20260309_232001"

ls use_cases/Kougarok/memory/logs/phase3_diagnosis/ | grep $SESSION_ID
ls use_cases/Kougarok/memory/logs/phase4_hypothesis/ | grep $SESSION_ID
ls use_cases/Kougarok/memory/logs/phase5_testing/ | grep $SESSION_ID
ls use_cases/Kougarok/memory/logs/phase6_refinement/ | grep $SESSION_ID
```

### Collect the log files

The key logs per iteration cycle are:

| Phase | Log Pattern | Content |
|-------|-------------|---------|
| Phase 2 | `r{RR}_{session}_Screening.md` | Ensemble screening results |
| Phase 3 | `r{RR}_c{EE}_iter{II}_{session}_Diagnosis.md` | Root cause analysis |
| Phase 4 | `r{RR}_c{EE}_iter{II}_{session}_*.md` | Hypothesis + skip-testing results |
| Phase 5 | `r{RR}_c{EE}_{session}_*.md` | Experiment design |
| Phase 6 | `r{RR}_c{EE}_{session}_*.md` | Refinement results |

### Collect diagnostic figures

Diagnostic plots are generated during Phase 3 and stored in:

```
use_cases/Kougarok/memory/phase_results/
├── phase1_exploration/     # Morris sensitivity plots
├── phase2_screening/       # Screening comparison plots
├── phase3_diagnosis/       # AI-generated diagnostic plots (P mass balance, mortality, PFT overview)
├── phase5_testing/         # Experiment parameter files and scripts
└── phase6_refinement/      # Experiment comparison plots
```

Copy relevant figures to your presentation folder:

```bash
# Create presentation directory
PRES_DIR="tools/reports/MySession"
mkdir -p $PRES_DIR/figures

# Copy relevant figures (adjust paths for your session)
cp use_cases/Kougarok/memory/phase_results/phase1_exploration/*sensitivity*.png $PRES_DIR/figures/
cp use_cases/Kougarok/memory/phase_results/phase2_screening/*top_cases*.png $PRES_DIR/figures/
cp use_cases/Kougarok/memory/phase_results/phase3_diagnosis/*.png $PRES_DIR/figures/
cp use_cases/Kougarok/memory/phase_results/phase6_refinement/*comparison*.png $PRES_DIR/figures/
```

---

## Step 2: Generate Slides and Narration with Claude

Both the Marp slide deck and the narration JSON are AI-generated. Ask Claude (via Claude Code or the API) to create them from the session logs. Example prompt:

> Read the session logs in `use_cases/Kougarok/memory/logs/{session_id}/` and the figures in
> `use_cases/Kougarok/memory/phase_results/`. Create:
> 1. A Marp markdown slide deck summarizing the session's diagnosis evolution
> 2. A `slide_scripts.json` with narration text for each slide
>
> Use the template and example in `tools/reports/WORKFLOW.md` and
> `tools/reports/examples/Kougarok_Demo/` for reference.

Claude will generate both files. You then review and curate the output (edit text, adjust figure references, refine narration phrasing).

### Create the slide deck

Create a `.md` file with Marp front matter. Use this template as a starting point:

```markdown
---
marp: true
theme: default
paginate: true
backgroundColor: #ffffff
size: 16:9
style: |
  section { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 22px; padding: 40px 60px; }
  h1 { color: #1565C0; font-size: 1.8em; }
  h2 { color: #2196F3; font-size: 1.3em; }
  .highlight { background-color: #E3F2FD; padding: 0.5em 0.8em; border-radius: 8px; border-left: 4px solid #1565C0; }
  .red-highlight { background-color: #FFEBEE; padding: 0.5em 0.8em; border-radius: 8px; border-left: 4px solid #C62828; }
  .green-highlight { background-color: #E8F5E9; padding: 0.5em 0.8em; border-radius: 8px; border-left: 4px solid #2E7D32; }
  .orange-highlight { background-color: #FFF3E0; padding: 0.5em 0.8em; border-radius: 8px; border-left: 4px solid #E65100; }
  .columns { display: grid; grid-template-columns: 1fr 1fr; gap: 1.2em; }
  table { font-size: 0.82em; width: 100%; }
  th { background-color: #E3F2FD; }
---

# Title Slide
## Session description

---

# Slide 2 content
...
```

### Slide structure guidelines

Follow this structure for a diagnosis-evolution presentation:

| Slide Group | Slides | Content |
|-------------|--------|---------|
| **Title** | 1 | Session ID, site, round, parameter count |
| **Overview** | 1 | ASCII flow diagram of iteration cycles |
| **Phase 1-2** | 2-3 | Sensitivity results, screening table, top-cases figure |
| **Per iteration** | 2-4 each | Diagnosis findings, diagnostic evidence figures, hypothesis + skip-test result |
| **Phase 5** | 1 | Experiment design table |
| **Phase 6** | 1-2 | Experiment results (if available) |
| **Summary** | 1-2 | Evolution table, key takeaways |

### Including figures

Use Marp's background image syntax for full-slide figures:

```markdown
# Slide with side figure
![bg right:55% fit](figures/my_plot.png)

## Text content on the left
```

Or full-background:

```markdown
![bg fit](figures/full_width_plot.png)
```

### Key content to extract from logs

For each **diagnosis** log, extract:
- Failing targets
- Likely causes (ranked)
- Confidence score
- Key parameter values from comparative case analysis

For each **hypothesis** log, extract:
- Parameter changes (table format)
- Skip-testing result (supported/not supported)
- Key evidence numbers
- Learning from failure

### Example reference

See `tools/reports/examples/Kougarok_Demo/A2MC_Session_20260309_Diagnosis_Evolution.md` for a complete 21-slide example covering 4 diagnosis-hypothesis cycles.

---

## Step 3: Generate PPTX (for review)

```bash
cd $PRES_DIR

# Generate PPTX (--allow-local-files needed for local figure paths)
npx @marp-team/marp-cli MyPresentation.md --pptx --allow-local-files

# Open for review
open MyPresentation.pptx
```

**Note:** `--allow-local-files` is required for local image paths to render in the PPTX. Without it, figures will be missing.

---

## Step 4: Generate PDF (for video)

```bash
# Generate PDF (required input for video generation)
npx @marp-team/marp-cli MyPresentation.md --pdf --allow-local-files
```

Verify the PDF has the correct number of pages:

```bash
# Quick page count check
python3 -c "
import subprocess
result = subprocess.run(['pdfinfo', 'MyPresentation.pdf'], capture_output=True, text=True)
for line in result.stdout.splitlines():
    if 'Pages' in line:
        print(line)
"
```

---

## Step 5: Create the Narration Script

The narration JSON is generated alongside the slides in Step 2. If you need to create or edit it separately:

### JSON narration format

Each `slide_scripts.json` file has one entry per slide:

```json
[
    {"slide": 1, "title": "Title Slide", "narration": "Welcome to...", "page": 1},
    {"slide": 2, "title": "Overview", "narration": "This session ran...", "page": 2}
]
```

- `slide`: Sequential slide number (1, 2, 3, ...)
- `title`: For progress display only
- `narration`: TTS narration text — natural speech, no markdown or special characters
- `page`: Which PDF page corresponds to this slide (usually same as slide number)

### Narration writing tips

- **Spell out abbreviations** on first use: "PFT, or Plant Functional Type"
- **Avoid special characters**: Write "10 to the minus 8" not "10⁻⁸"
- **Use natural pauses**: Break long sentences into shorter ones
- **Describe figures**: "This figure shows..." when the slide has a plot
- **Keep it concise**: 15-30 seconds per slide is typical (50-100 words)

---

## Step 6: Generate the Video

```bash
# Activate environment with openai
source ~/a2mc_env/bin/activate

# Run the generic video generator
python tools/reports/generate_video.py \
    --pdf use_cases/Kougarok/reports/MyPresentation.pdf \
    --scripts $PRES_DIR/slide_scripts.json \
    --output-dir use_cases/Kougarok/reports/video_output
```

### Pipeline stages

The script runs 5 stages:

1. **Extract PDF slides** — `pdftoppm` converts PDF pages to PNG
2. **Scale slides** — `ffmpeg` pads/scales each to 1920x1080
3. **Generate audio** — OpenAI TTS (`tts-1-hd`, voice `nova`) or macOS `say` fallback
4. **Create slide videos** — `ffmpeg` combines each slide image + audio into MP4 segment
5. **Concatenate** — `ffmpeg` joins all segments into final video

### Output structure

```
video_output/
├── pdf_slides/          # Raw PNG pages from PDF
│   ├── page-01.png
│   └── ...
├── slides/              # Scaled 1920x1080 PNGs
│   ├── slide_01.png
│   └── ...
├── audio/               # TTS audio files
│   ├── slide_01.mp3
│   └── ...
├── slide_01.mp4         # Individual slide videos
├── slide_02.mp4
├── ...
├── video_list.txt       # ffmpeg concat list
└── MyPresentation.mp4   # Final video
```

### TTS options

| Setting | Options | Default |
|---------|---------|---------|
| Voice | alloy, echo, fable, onyx, **nova**, shimmer | nova |
| Model | tts-1 (fast), **tts-1-hd** (high quality) | tts-1-hd |
| Fallback | macOS `say` command (free, lower quality) | auto if no openai |

To change voice/model, use command-line arguments:

```bash
python tools/reports/generate_video.py --pdf ... --scripts ... --voice shimmer --model tts-1
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| `openai not installed` | Use `~/a2mc_env/bin/python3 generate_video.py` |
| `PDF not found` | Run Step 4 first to generate the PDF |
| Figures missing in PDF | Add `--allow-local-files` to marp-cli |
| Audio sounds robotic | Switch to `tts-1-hd` model |
| Video too long | Shorten narration scripts |
| `pdftoppm not found` | `brew install poppler` |

---

## Quick Reference: Full Pipeline

```bash
# 0. Set up
SESSION_ID="20260309_232001"
PRES_DIR="tools/reports/MySession"
REPORTS_DIR="use_cases/Kougarok/reports"
mkdir -p $PRES_DIR/figures $REPORTS_DIR
source ~/a2mc_env/bin/activate

# 1. Copy figures
cp use_cases/Kougarok/memory/phase_results/phase3_diagnosis/*.png $PRES_DIR/figures/

# 2. Create Marp markdown + narration JSON (AI-generated, human-curated)
#    → $PRES_DIR/MyPresentation.md
#    → $PRES_DIR/slide_scripts.json

# 3. Generate PPTX (review)
npx @marp-team/marp-cli $PRES_DIR/MyPresentation.md --pptx --allow-local-files \
    -o $REPORTS_DIR/MyPresentation.pptx

# 4. Generate PDF (for video)
npx @marp-team/marp-cli $PRES_DIR/MyPresentation.md --pdf --allow-local-files \
    -o $REPORTS_DIR/MyPresentation.pdf

# 5. Generate video
python tools/reports/generate_video.py \
    --pdf $REPORTS_DIR/MyPresentation.pdf \
    --scripts $PRES_DIR/slide_scripts.json \
    --output-dir $REPORTS_DIR/video_output

# 6. Play result
open $REPORTS_DIR/video_output/MyPresentation.mp4
```

---

## Automated Pipeline (Recommended)

`generate_presentation.py` automates the entire pipeline from session logs to narrated video with a single command:

```bash
# Source config for AI provider settings
source a2mc_config.sh
source use_cases/Kougarok/config/kougarok_config.sh

# Full pipeline: collect artifacts → AI slides → AI narration → PDF → video
python tools/reports/generate_presentation.py --session-id 20260330_135435

# With custom author name
python tools/reports/generate_presentation.py --session-id 20260330_135435 \
    --author "Dr. Jing Tao (Lawrence Berkeley National Laboratory)"

# Generate slides + narration only (review before building video)
python tools/reports/generate_presentation.py --session-id 20260330_135435 \
    --stop-after narration

# Resume from PDF stage (after reviewing/editing slides and narration)
python tools/reports/generate_presentation.py --session-id 20260330_135435 \
    --start-from pdf
```

### Pipeline Stages

| Stage | What it does | AI? |
|-------|-------------|-----|
| 1. collect | Gather session report, raw logs, figures | No |
| 2. slides | Generate Marp slide deck from logs + report | **Yes** |
| 3. narration | Generate TTS narration script for each slide | **Yes** |
| 4. pdf | Build PDF and PPTX with marp-cli | No |
| 5. video | Build narrated MP4 with TTS audio | No (TTS API) |

The AI uses both the session report (high-level narrative) and raw phase logs (detailed data) as input, since the report alone may not capture everything.

### Output Structure

```
use_cases/{site}/reports/{session_id}/
├── A2MC_Session_{session_id}.md     # Marp slides (AI-generated, human-curated)
├── slide_scripts.json               # Narration JSON (AI-generated, human-curated)
├── A2MC_Session_{session_id}.pdf    # PDF for video pipeline
├── A2MC_Session_{session_id}.pptx   # PPTX for manual review
├── figures/                         # Copied diagnostic figures
└── video_output/                    # Narrated video
    ├── slides/, audio/              # Intermediate files
    └── A2MC_Session_{session_id}.mp4
```

### Recommended Workflow

1. Run with `--stop-after narration` to generate slides and narration
2. **Review and edit** the slides (`.md`) and narration (`slide_scripts.json`)
3. Resume with `--start-from pdf` to build PDF and video from the curated files

---

## Directory Structure

```
tools/reports/                     # Reusable tooling (tracked in git)
├── WORKFLOW.md                    # This file
├── generate_presentation.py      # Full pipeline: logs → slides → narration → PDF → video
├── generate_video.py             # Video-only generator (PDF + narration → MP4)
└── examples/                     # Session-specific examples
    └── Kougarok_Demo/            # Example: Session 20260309
        ├── A2MC_Session_20260309_Diagnosis_Evolution.md  # Marp slides
        ├── slide_scripts.json    # Narration JSON
        ├── generate_video.py     # Session-specific video script (legacy)
        └── figures/

use_cases/{site}/reports/{session_id}/  # Generated outputs (gitignored)
├── *.md, *.pdf, *.pptx               # Slides in various formats
├── slide_scripts.json                 # Narration script
├── figures/                           # Diagnostic figures
└── video_output/                      # Narrated video
```

---

## Manual Workflow (Step-by-Step)

The steps below describe the manual process. Use `generate_presentation.py` above to automate steps 1-6.

1. **Gather logs** from `use_cases/{site}/memory/logs/{session_id}/`
2. **Copy figures** from `phase_results/{session_id}/` directories
3. **Create Marp markdown and narration JSON** — both are typically AI-generated by Claude and curated by the user
4. **Generate PDF/PPTX** with marp-cli
5. **Generate video** with `python tools/reports/generate_video.py --pdf ... --scripts ...`

The slide content and narration scripts are AI-generated and human-curated. Everything else is automated.
