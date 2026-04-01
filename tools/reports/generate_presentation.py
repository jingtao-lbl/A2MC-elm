#!/usr/bin/env python3
"""
A2MC Session Presentation Generator

Complete pipeline: session logs/report → Marp slides → narration JSON → PDF → video

Stages:
  1. Collect session artifacts (report, raw logs, figures)
  2. Generate manuscript-style technical report via AI API
  3. Generate Marp slides via AI API
  4. Generate narration JSON via AI API
  5. Build PDF with marp-cli
  6. Build narrated video with generate_video.py

Usage:
    # Full pipeline (report + slides + narration + PDF + video)
    python generate_presentation.py --session-id 20260330_135435

    # On Perlmutter: generate report, slides, narration (no PDF/video)
    python generate_presentation.py --session-id 20260330_135435 --stop-after narration

    # Manuscript report only
    python generate_presentation.py --session-id 20260330_135435 --stop-after report

    # Locally: build PDF + video from existing slides + narration
    python generate_presentation.py --session-id 20260330_135435 --start-from pdf

Requires:
    - AI API key (ANTHROPIC_API_KEY, OPENAI_API_KEY, or CBORG_API_KEY)
    - marp-cli (npm install -g @marp-team/marp-cli) for PDF/PPTX
    - ffmpeg, poppler, openai Python package for video

Author: Jing Tao with Claude
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

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


# ============================================================
# AI Client Setup
# ============================================================

def create_ai_client():
    """Create AI client using A2MC's provider configuration.

    Reads A2MC_AI_PROVIDER, A2MC_AI_MODEL, and the corresponding API key
    from environment variables (set by sourcing a2mc_config.sh).

    Returns:
        (client, model, provider) tuple
    """
    provider = os.environ.get('A2MC_AI_PROVIDER', 'anthropic')
    model = os.environ.get('A2MC_AI_MODEL', '')
    base_url = os.environ.get('A2MC_AI_BASE_URL', '')

    if provider == 'anthropic':
        import anthropic
        model = model or 'claude-sonnet-4-20250514'
        kwargs = {}
        if base_url:
            kwargs['base_url'] = base_url
        client = anthropic.Anthropic(**kwargs)
        return client, model, provider

    else:
        # openai or cborg — both use the OpenAI SDK
        import openai
        if provider == 'cborg':
            model = model or 'anthropic/claude-sonnet'
            base_url = base_url or 'https://api.cborg.lbl.gov'
        else:
            model = model or 'gpt-4o'

        kwargs = {}
        if base_url:
            kwargs['base_url'] = base_url

        # Resolve API key
        key_env = os.environ.get('A2MC_AI_API_KEY_ENV', '')
        if not key_env:
            key_map = {
                'anthropic': 'ANTHROPIC_API_KEY',
                'openai': 'OPENAI_API_KEY',
                'cborg': 'CBORG_API_KEY',
            }
            key_env = key_map.get(provider, 'OPENAI_API_KEY')
        api_key = os.environ.get(key_env, '')
        if api_key:
            kwargs['api_key'] = api_key

        client = openai.OpenAI(**kwargs)
        return client, model, provider


def query_ai(client, model, provider, prompt, max_tokens=8000):
    """Send a prompt to the AI and return the response text."""
    if provider == 'anthropic':
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    else:
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content


# ============================================================
# Stage 1: Collect Artifacts
# ============================================================

def collect_artifacts(site_dir: str, session_id: str) -> dict:
    """Collect session report, raw logs, and figure paths."""
    site_path = Path(site_dir)
    logs_base = site_path / "memory" / "logs" / session_id
    results_base = site_path / "memory" / "phase_results" / session_id

    artifacts = {
        "session_report": None,
        "logs": {},
        "figures": {},
        "figure_names": {},
        "session_id": session_id,
    }

    # Session report (AI-generated narrative)
    report_file = logs_base / f"session_report_{session_id}.md"
    if report_file.exists():
        artifacts["session_report"] = report_file.read_text(encoding="utf-8")
        logger.info(f"  Session report: {report_file.name}")

    # Raw phase logs
    phase_dirs = [
        "phase1_exploration", "phase2_screening", "phase3_diagnosis",
        "phase4_hypothesis", "phase5_testing", "phase6_refinement",
    ]
    for phase_name in phase_dirs:
        log_dir = logs_base / phase_name
        if not log_dir.exists():
            continue
        log_files = sorted(log_dir.glob("*.md"))
        if log_files:
            log_contents = []
            for lf in log_files:
                try:
                    content = lf.read_text(encoding="utf-8")
                    log_contents.append({"filename": lf.name, "content": content})
                except Exception as e:
                    logger.warning(f"Could not read {lf}: {e}")
            artifacts["logs"][phase_name] = log_contents

    # Figures from phase_results (session-scoped)
    for phase_name in phase_dirs:
        fig_dir = results_base / phase_name
        if not fig_dir.exists():
            continue
        fig_files = sorted(fig_dir.glob("*.png"))
        if fig_files:
            artifacts["figures"][phase_name] = [str(f) for f in fig_files]
            artifacts["figure_names"][phase_name] = [f.name for f in fig_files]

    # Fallback: flat phase1 figures (not session-scoped)
    flat_phase1 = site_path / "memory" / "phase_results" / "phase1_exploration"
    if flat_phase1.exists() and "phase1_exploration" not in artifacts["figures"]:
        fig_files = sorted(flat_phase1.glob("*.png"))
        if fig_files:
            artifacts["figures"]["phase1_exploration"] = [str(f) for f in fig_files]
            artifacts["figure_names"]["phase1_exploration"] = [f.name for f in fig_files]

    n_logs = sum(len(v) for v in artifacts["logs"].values())
    n_figs = sum(len(v) for v in artifacts["figures"].values())
    logger.info(f"  Collected {n_logs} logs, {n_figs} figures")

    return artifacts


# ============================================================
# Stage 1.5: Generate Manuscript-Style Report
# ============================================================

MANUSCRIPT_REPORT_PROMPT = """You are writing a detailed technical report for an ELM-FATES model calibration session.
Write at the level of a top-tier journal (e.g., Journal of Advances in Modeling Earth Systems, Geoscientific Model Development). This is an internal technical report, not a submitted manuscript, but it must meet the same standards of rigor, precision, and transparency.

## Scientific Writing Rules

**Tone and Style:**
- Professional, neutral, precise. No filler, no vague or promotional language.
- Avoid vague terms such as "significant" unless quantitatively defined.
- Avoid buzzwords unless precisely defined. Define key terms on first use.
- Do NOT use em dashes. Use commas, periods, parentheses, or separate sentences.

**Rigor:**
- Every major claim must be supported by empirical evidence, established theory, or clear logical inference.
- If a claim lacks supporting data, explicitly state this as a limitation or hypothesis.
- Quantify uncertainty wherever possible. Present model predictions as model-based inference, not direct observation.
- Clearly separate data, model inference, and interpretation.

**Transparency:**
- Explicitly state what the ensemble can and cannot represent.
- Discuss limitations, transferability, and uncertainty honestly.
- Present failed hypotheses and negative results with the same rigor as successes.

**Failure Modes to Avoid:**
- Hallucinated citations or datasets
- Overstating spatial or temporal generality
- Treating model predictions as direct measurements
- Blurring distinctions between related but different concepts

## Session Context

{session_context}

## Session Report (if available)

{session_report}

## Raw Phase Logs

{raw_logs}

## Available Diagnostic Figures

{figure_list}

## Report Structure

Write a complete technical report with the following sections. Use Markdown formatting.
Embed ALL relevant diagnostic figures using `![description](figures/FILENAME)`.

### 1. Summary
2-3 paragraphs. State the objective, methods, key findings, and outcome. A reader should understand the entire session from this section alone.

### 2. Introduction and Objectives
- Site description and ecological context
- Calibration targets (PFTs, biomass pools, observed values with uncertainties)
- Parameter space (number of parameters, sampling design, ensemble size)
- Specific objectives of this calibration session

### 3. Methods
- Sensitivity analysis methodology (Morris/Sobol, trajectories, levels)
- Screening methodology (cost function, target weighting, ranking criteria)
- AI-driven diagnosis approach (how root causes were identified)
- Skip-testing methodology (how hypotheses were tested against existing ensemble data)
- Experiment design strategy (cumulative vs factorial, parameter selection rationale)

### 4. Results

#### 4.1 Sensitivity Analysis
- Key sensitive parameters per PFT and output variable
- Cross-PFT sensitivity patterns
- Embed sensitivity ranking figures

#### 4.2 Ensemble Screening
- Distribution of target satisfaction across ensemble
- Best cases and their characteristics
- Embed screening/top-cases figures

#### 4.3 Iterative Diagnosis and Hypothesis Testing
For EACH diagnosis-hypothesis cycle, report:
- Failing targets with quantitative error metrics
- Root cause analysis with confidence scores
- Diagnostic evidence (embed all relevant figures with detailed captions)
- Hypothesis formulation (specific parameter changes with mechanistic rationale)
- Skip-testing result (supported/not supported, quantitative evidence)
- What was learned and how it informed the next cycle

Present this as a scientific narrative showing how understanding evolved, not as a log dump.

#### 4.4 Experiment Design
- Final parameter modifications (table format: parameter, PFT, current, proposed, rationale)
- Cumulative experiment structure and why this design was chosen
- Expected outcomes with quantitative predictions

#### 4.5 Experiment Results (if available)
- Comparison of predicted vs actual outcomes
- Target improvement metrics
- Remaining gaps

### 5. Discussion
- Mechanistic insights discovered (name each discovery explicitly)
- Why certain hypotheses failed and what that reveals about model behavior
- Implications for ELM-FATES calibration methodology
- Limitations of the current approach
- Comparison with manual calibration approaches (if applicable)

### 6. Conclusions and Recommendations
- Summary of key findings (numbered list)
- Recommended parameter modifications for the next calibration round
- Suggested parameter space adjustments (bounds to expand, new parameters to include)
- Open questions requiring further investigation

### 7. Appendix: Parameter Tables
- Full table of modified parameters with values
- Edge parameters flagged for bound expansion

## Output Rules
- Output ONLY the Markdown report. No code fences around the entire output.
- Use proper scientific notation for small numbers (e.g., 1.03 x 10^-3).
- Include quantitative values whenever available (biomass in gC/m2, RMSRE values, confidence scores).
- Reference specific case numbers (e.g., "Case #86") when discussing results.
- The report should be thorough: 1500-3000 lines of Markdown.
"""


def generate_manuscript_report(client, model, provider, artifacts, author, output_path):
    """Generate a manuscript-style technical report via AI API."""
    session_context = (
        f"Session: {artifacts['session_id']}\n"
        f"Author: {author}"
    )

    session_report = artifacts.get("session_report") or "*No session report available*"
    if len(session_report) > 30000:
        session_report = session_report[:30000] + "\n\n[... truncated ...]"

    # Build raw logs (truncated per phase)
    raw_logs_parts = []
    for phase_name, logs in artifacts.get("logs", {}).items():
        raw_logs_parts.append(f"\n### {phase_name}")
        for log_entry in logs:
            content = log_entry["content"]
            if len(content) > 8000:
                content = content[:8000] + "\n[... truncated ...]"
            raw_logs_parts.append(f"\n#### {log_entry['filename']}\n{content}")
    raw_logs = "\n".join(raw_logs_parts) if raw_logs_parts else "*No raw logs available*"

    # Build figure list
    fig_parts = []
    for phase_name, names in artifacts.get("figure_names", {}).items():
        for name in names:
            fig_parts.append(f"- `figures/{name}` ({phase_name})")
    figure_list = "\n".join(fig_parts) if fig_parts else "*No figures available*"

    prompt = MANUSCRIPT_REPORT_PROMPT.format(
        session_context=session_context,
        session_report=session_report,
        raw_logs=raw_logs,
        figure_list=figure_list,
    )

    logger.info("Generating manuscript-style report via AI API...")
    response = query_ai(client, model, provider, prompt, max_tokens=16000)

    # Clean up code fences
    if response.startswith("```"):
        lines = response.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        response = "\n".join(lines)

    output_path.write_text(response, encoding="utf-8")
    n_lines = response.count("\n") + 1
    logger.info(f"  Report written: {output_path} ({n_lines} lines)")
    return output_path


# ============================================================
# Stage 2: Generate Marp Slides
# ============================================================

SLIDE_GENERATION_PROMPT = """You are generating a Marp presentation slide deck from an A2MC calibration session.

## Session Context

{session_context}

## Session Report (AI-generated narrative summary)

{session_report}

## Raw Phase Logs

{raw_logs}

## Available Figures

{figure_list}

## Instructions

Generate a complete Marp Markdown slide deck following this structure:

1. **Title slide** — Session ID, site, round, parameter count. Include:
   "A2MC Reporting Agent"
   "Curated by {author}"

2. **Session Overview** — ASCII flow diagram showing iteration cycles (diagnosis → hypothesis → skip-testing loops → experiments)

3. **Phase 1-2** (2-3 slides) — Sensitivity results, screening table, top-cases figure

4. **Per iteration cycle** (2-4 slides each) — Diagnosis findings with evidence figures, hypothesis with skip-test results, what was learned from each failure

5. **Experiment Design** (1 slide) — If experiments were designed, show the parameter changes table

6. **Experiment Results** (1-2 slides) — If Phase 6 data available

7. **Summary** (1-2 slides) — Evolution table showing how understanding deepened, key takeaways

### Marp formatting rules

- Use `---` to separate slides
- Include figures with `![bg right:55% fit](figures/FILENAME)` or `![bg fit](figures/FILENAME)`
- Use `<div class="highlight">` for key findings (blue), `<div class="red-highlight">` for critical issues, `<div class="green-highlight">` for successes, `<div class="orange-highlight">` for warnings
- Use `<div class="columns"><div>` for two-column layouts
- Tables with `font-size: 0.82em` are already styled
- First slide should have `<!-- _paginate: false -->`

### Required Marp front matter (include exactly):

```
---
marp: true
theme: default
paginate: true
backgroundColor: #ffffff
size: 16:9
style: |
  section {{ font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 22px; padding: 40px 60px; }}
  h1 {{ color: #1565C0; font-size: 1.8em; margin-bottom: 0.3em; }}
  h2 {{ color: #2196F3; font-size: 1.3em; margin-bottom: 0.3em; }}
  h3 {{ color: #1976D2; font-size: 1.1em; margin-bottom: 0.2em; }}
  .columns {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.2em; }}
  .highlight {{ background-color: #E3F2FD; padding: 0.5em 0.8em; border-radius: 8px; border-left: 4px solid #1565C0; }}
  .orange-highlight {{ background-color: #FFF3E0; padding: 0.5em 0.8em; border-radius: 8px; border-left: 4px solid #E65100; }}
  .green-highlight {{ background-color: #E8F5E9; padding: 0.5em 0.8em; border-radius: 8px; border-left: 4px solid #2E7D32; }}
  .red-highlight {{ background-color: #FFEBEE; padding: 0.5em 0.8em; border-radius: 8px; border-left: 4px solid #C62828; }}
  table {{ font-size: 0.82em; width: 100%; }}
  th {{ background-color: #E3F2FD; }}
  strong {{ color: #1565C0; }}
  footer {{ font-size: 0.6em; color: #999; }}
---
```

Output ONLY the complete Marp Markdown (starting with the --- front matter). No code fences around the output.
"""


def generate_slides(client, model, provider, artifacts, author, output_path):
    """Generate Marp slides via AI API."""
    # Build context
    session_context = f"Session: {artifacts['session_id']}"

    session_report = artifacts.get("session_report") or "*No session report available*"
    if len(session_report) > 30000:
        session_report = session_report[:30000] + "\n\n[... truncated ...]"

    # Build raw logs (truncated per phase)
    raw_logs_parts = []
    for phase_name, logs in artifacts.get("logs", {}).items():
        raw_logs_parts.append(f"\n### {phase_name}")
        for log_entry in logs:
            content = log_entry["content"]
            if len(content) > 8000:
                content = content[:8000] + "\n[... truncated ...]"
            raw_logs_parts.append(f"\n#### {log_entry['filename']}\n{content}")
    raw_logs = "\n".join(raw_logs_parts) if raw_logs_parts else "*No raw logs available*"

    # Build figure list
    fig_parts = []
    for phase_name, names in artifacts.get("figure_names", {}).items():
        for name in names:
            fig_parts.append(f"- `figures/{name}` ({phase_name})")
    figure_list = "\n".join(fig_parts) if fig_parts else "*No figures available*"

    prompt = SLIDE_GENERATION_PROMPT.format(
        session_context=session_context,
        session_report=session_report,
        raw_logs=raw_logs,
        figure_list=figure_list,
        author=author,
    )

    logger.info("Generating slides via AI API...")
    response = query_ai(client, model, provider, prompt, max_tokens=16000)

    # Clean up: remove code fences if AI wrapped the output
    if response.startswith("```"):
        lines = response.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        response = "\n".join(lines)

    output_path.write_text(response, encoding="utf-8")
    logger.info(f"  Slides written: {output_path}")

    # Count slides
    n_slides = response.count("\n---") + 1
    logger.info(f"  Generated {n_slides} slides")
    return n_slides


# ============================================================
# Stage 3: Generate Narration JSON
# ============================================================

NARRATION_GENERATION_PROMPT = """You are generating a narration script for a presentation video.
The narration will be converted to speech using text-to-speech (OpenAI TTS).

## Slide Deck

{slide_content}

## Narration Style Guide

The narrator is an A2MC reporting agent. Follow these rules:

1. **Opening slide:** Start with "Hello. I'm an A2MC reporting agent, curated by {author}. Today I'll..."
2. **Spell out abbreviations** on first use: "PFT, or Plant Functional Type"
3. **Avoid special characters** — write "10 to the minus 8" not "10^-8", write "grams per square meter" not "g/m2"
4. **Use natural pauses** — break long sentences into shorter ones
5. **Describe figures explicitly** — "This figure shows..." when the slide has a plot
6. **Be specific** — mention case numbers, parameter values, confidence scores
7. **Target 50-100 words per slide** (15-30 seconds of speech)
8. **Keep it scientific but accessible** — explain mechanisms clearly
9. **For table-heavy slides** — narrate the key takeaway, don't read every cell
10. **For figure slides** — describe what the figure shows and what insight it provides

## Output Format

Return a JSON array. Each entry has:
- "slide": sequential number (1, 2, 3, ...)
- "title": short title for progress display
- "narration": the TTS text (natural speech, no markdown)
- "page": which PDF page this corresponds to (usually same as slide number)

Output ONLY the JSON array. No code fences, no explanation.
"""


def generate_narration(client, model, provider, slides_path, author, output_path):
    """Generate narration JSON via AI API."""
    slide_content = slides_path.read_text(encoding="utf-8")

    prompt = NARRATION_GENERATION_PROMPT.format(
        slide_content=slide_content,
        author=author,
    )

    logger.info("Generating narration via AI API...")
    response = query_ai(client, model, provider, prompt, max_tokens=16000)

    # Clean up: extract JSON from response
    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    # Validate JSON
    scripts = json.loads(text)
    assert isinstance(scripts, list), "Expected JSON array"
    for entry in scripts:
        for key in ("slide", "title", "narration", "page"):
            assert key in entry, f"Missing '{key}' in entry: {entry}"

    output_path.write_text(json.dumps(scripts, indent=2, ensure_ascii=False),
                           encoding="utf-8")
    logger.info(f"  Narration written: {output_path} ({len(scripts)} slides)")
    return scripts


# ============================================================
# Stage 4: Build PDF
# ============================================================

def build_pdf(slides_path, output_dir):
    """Build PDF from Marp slides using marp-cli."""
    pdf_path = output_dir / f"{slides_path.stem}.pdf"
    cmd = [
        "npx", "@marp-team/marp-cli",
        str(slides_path), "--pdf", "--allow-local-files",
        "-o", str(pdf_path),
    ]
    logger.info(f"Building PDF: {pdf_path.name}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"marp-cli failed: {result.stderr}")
        raise RuntimeError(f"PDF generation failed: {result.stderr}")
    logger.info(f"  PDF: {pdf_path}")

    # Also generate PPTX for review
    pptx_path = output_dir / f"{slides_path.stem}.pptx"
    cmd_pptx = [
        "npx", "@marp-team/marp-cli",
        str(slides_path), "--pptx", "--allow-local-files",
        "-o", str(pptx_path),
    ]
    subprocess.run(cmd_pptx, capture_output=True, text=True)
    if pptx_path.exists():
        logger.info(f"  PPTX: {pptx_path}")

    return pdf_path


# ============================================================
# Stage 5: Build Video
# ============================================================

def build_video(pdf_path, scripts_path, output_dir, voice="nova", tts_model="tts-1-hd"):
    """Build narrated video using generate_video.py."""
    video_script = Path(__file__).parent / "generate_video.py"
    cmd = [
        sys.executable, str(video_script),
        "--pdf", str(pdf_path),
        "--scripts", str(scripts_path),
        "--output-dir", str(output_dir / "video_output"),
        "--voice", voice,
        "--model", tts_model,
    ]
    logger.info("Building video...")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError("Video generation failed")

    # Find the output video
    video_files = list((output_dir / "video_output").glob("*.mp4"))
    # Return the concatenated one (largest)
    if video_files:
        final = max(video_files, key=lambda f: f.stat().st_size)
        logger.info(f"  Video: {final}")
        return final
    return None


# ============================================================
# Main Pipeline
# ============================================================

STAGES = ["collect", "report", "slides", "narration", "pdf", "video"]


def main():
    parser = argparse.ArgumentParser(
        description="Generate presentation and narrated video from A2MC session"
    )
    parser.add_argument("--session-id", required=True,
                        help="Session ID (YYYYMMDD_HHMMSS)")
    parser.add_argument("--site-dir", default=None,
                        help="Path to use_cases/{site}/ (default: from A2MC_USE_CASE_DIR)")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: use_cases/{site}/reports/{session_id}/)")
    parser.add_argument("--author", default=None,
                        help="Author name for narration intro (default: from A2MC_AUTHOR or 'the A2MC team')")
    parser.add_argument("--start-from", choices=STAGES, default="collect",
                        help="Start from this stage (skip earlier stages)")
    parser.add_argument("--stop-after", choices=STAGES, default="video",
                        help="Stop after this stage")
    parser.add_argument("--voice", default="nova",
                        help="TTS voice (default: nova)")
    parser.add_argument("--tts-model", default="tts-1-hd",
                        help="TTS model (default: tts-1-hd)")

    args = parser.parse_args()

    # Resolve site directory
    site_dir = args.site_dir or os.environ.get('A2MC_USE_CASE_DIR', '')
    if not site_dir:
        logger.error("No site directory. Set A2MC_USE_CASE_DIR or pass --site-dir")
        sys.exit(1)

    # Resolve output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(site_dir) / "reports" / args.session_id
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(exist_ok=True)

    # Resolve author
    author = args.author or os.environ.get('A2MC_AUTHOR', 'the A2MC team')

    session_id = args.session_id
    start_idx = STAGES.index(args.start_from)
    stop_idx = STAGES.index(args.stop_after)

    slides_path = output_dir / f"A2MC_Session_{session_id}.md"
    scripts_path = output_dir / "slide_scripts.json"
    report_path = output_dir / f"A2MC_Session_{session_id}_Technical_Report.md"

    n_stages = stop_idx - start_idx + 1
    print("=" * 60)
    print("A2MC Session Presentation Generator")
    print("=" * 60)
    print(f"  Session:  {session_id}")
    print(f"  Site dir: {site_dir}")
    print(f"  Output:   {output_dir}")
    print(f"  Author:   {author}")
    print(f"  Stages:   {' → '.join(STAGES[start_idx:stop_idx+1])}")
    print()

    # Helper: ensure artifacts are collected
    def ensure_artifacts():
        nonlocal artifacts
        if artifacts is None:
            print("[Stage 1/6] Collecting session artifacts...")
            artifacts = collect_artifacts(site_dir, session_id)
        return artifacts

    # Helper: ensure AI client is created
    ai_client = [None, None, None]  # [client, model, provider]
    def ensure_ai_client():
        if ai_client[0] is None:
            ai_client[:] = list(create_ai_client())
            logger.info(f"  AI provider: {ai_client[2]}, model: {ai_client[1]}")
        return ai_client

    # --- Stage 1: Collect ---
    # STAGES index: 0=collect, 1=report, 2=slides, 3=narration, 4=pdf, 5=video
    artifacts = None
    if start_idx <= 0:
        print("[Stage 1/6] Collecting session artifacts...")
        artifacts = collect_artifacts(site_dir, session_id)

        if not artifacts["logs"] and not artifacts["session_report"]:
            logger.error(f"No logs or session report found for session {session_id}")
            sys.exit(1)

        # Copy figures to output directory
        n_copied = 0
        for phase_name, fig_paths in artifacts.get("figures", {}).items():
            for fp in fig_paths:
                src = Path(fp)
                dst = figures_dir / src.name
                if not dst.exists():
                    import shutil
                    shutil.copy2(src, dst)
                    n_copied += 1
        if n_copied:
            logger.info(f"  Copied {n_copied} figures to {figures_dir}")

    if stop_idx <= 0:
        print("\nDone (stopped after collect).")
        return

    # --- Stage 2: Manuscript-Style Report ---
    if start_idx <= 1:
        ensure_artifacts()
        print("\n[Stage 2/6] Generating manuscript-style technical report via AI...")
        client, model, provider = ensure_ai_client()
        generate_manuscript_report(client, model, provider, artifacts, author,
                                   report_path)

    if stop_idx <= 1:
        print(f"\nDone (stopped after report). Review: {report_path}")
        return

    # --- Stage 3: Generate Slides ---
    if start_idx <= 2:
        ensure_artifacts()
        print("\n[Stage 3/6] Generating slides via AI...")
        client, model, provider = ensure_ai_client()
        generate_slides(client, model, provider, artifacts, author, slides_path)

    if stop_idx <= 2:
        print(f"\nDone (stopped after slides). Review: {slides_path}")
        return

    # --- Stage 4: Generate Narration ---
    if start_idx <= 3:
        if not slides_path.exists():
            logger.error(f"Slides not found: {slides_path}")
            sys.exit(1)
        print("\n[Stage 4/6] Generating narration via AI...")
        client, model, provider = ensure_ai_client()
        generate_narration(client, model, provider, slides_path, author, scripts_path)

    if stop_idx <= 3:
        print(f"\nDone (stopped after narration). Review:")
        print(f"  Report:    {report_path}")
        print(f"  Slides:    {slides_path}")
        print(f"  Narration: {scripts_path}")
        return

    # --- Stage 5: Build PDF ---
    pdf_path = None
    if start_idx <= 4:
        if not slides_path.exists():
            logger.error(f"Slides not found: {slides_path}")
            sys.exit(1)
        print("\n[Stage 5/6] Building PDF and PPTX...")
        pdf_path = build_pdf(slides_path, output_dir)

    if stop_idx <= 4:
        print(f"\nDone (stopped after PDF). Review:")
        print(f"  PDF:  {pdf_path}")
        return

    # --- Stage 6: Build Video ---
    if start_idx <= 5:
        if pdf_path is None:
            pdf_path = output_dir / f"A2MC_Session_{session_id}.pdf"
        if not pdf_path.exists():
            logger.error(f"PDF not found: {pdf_path}")
            sys.exit(1)
        if not scripts_path.exists():
            logger.error(f"Narration not found: {scripts_path}")
            sys.exit(1)
        print("\n[Stage 6/6] Building narrated video...")
        video_path = build_video(pdf_path, scripts_path, output_dir,
                                 voice=args.voice, tts_model=args.tts_model)

        if video_path:
            print(f"\nDone! Video: {video_path}")
            print(f"Play with: open {video_path}")

    print()
    print("=" * 60)
    print("Output files:")
    if report_path.exists():
        print(f"  Report:    {report_path}")
    print(f"  Slides:    {slides_path}")
    print(f"  Narration: {scripts_path}")
    if pdf_path and pdf_path.exists():
        print(f"  PDF:       {pdf_path}")
    pptx = output_dir / f"A2MC_Session_{session_id}.pptx"
    if pptx.exists():
        print(f"  PPTX:      {pptx}")
    video_out = output_dir / "video_output"
    if video_out.exists():
        videos = list(video_out.glob("*.mp4"))
        if videos:
            final = max(videos, key=lambda f: f.stat().st_size)
            print(f"  Video:     {final}")
    print("=" * 60)


if __name__ == "__main__":
    main()
