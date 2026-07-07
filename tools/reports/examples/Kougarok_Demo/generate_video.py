#!~/a2mc_env/bin/python3
"""
Kougarok Demo Presentation Video Generator
Converts PDF slides + speaker scripts into a narrated MP4 video.

Usage:
    # First generate PDF from Marp:
    npx @marp-team/marp-cli A2MC_Session_20260309_Diagnosis_Evolution.md --pdf --allow-local-files

    # Then generate video:
    export OPENAI_API_KEY="your-key"
    python generate_video.py

Requires: ffmpeg, poppler (pdftoppm), openai Python package
"""

import subprocess
import os
import re
from pathlib import Path

# Load .env from A2MC root (3 levels up)
ENV_FILE = Path(__file__).resolve().parent.parent.parent.parent / ".env"
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
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

# --- Configuration ---
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "video_output"
SLIDES_DIR = OUTPUT_DIR / "slides"
AUDIO_DIR = OUTPUT_DIR / "audio"
PDF_SLIDES_DIR = OUTPUT_DIR / "pdf_slides"
PRESENTATION_PDF = SCRIPT_DIR / "A2MC_Session_20260309_Diagnosis_Evolution.pdf"

# OpenAI TTS settings
OPENAI_VOICE = "nova"       # alloy, echo, fable, onyx, nova, shimmer
OPENAI_MODEL = "tts-1-hd"   # tts-1 (fast/cheap) or tts-1-hd (high quality)

# --- Slide Scripts ---
# Each entry: (slide_number, title, script_text, pdf_page)
SLIDE_SCRIPTS = [
    (1, "Title Slide",
     "Hello. I'm Jing Tao from Lawrence Berkeley National Laboratory. "
     "Today I'll show you how A2MC's AI reasoning deepens its understanding "
     "through iterative calibration cycles. "
     "This presentation follows a single A2MC session at the Kougarok, Alaska site, "
     "where the AI completed four diagnosis-hypothesis cycles "
     "before submitting experiments to the supercomputer.",
     1),

    (2, "Session Overview",
     "This session ran four complete diagnosis-hypothesis iterations "
     "using A2MC's skip-testing feature. "
     "After Phase 2 screening, the AI enters a loop: "
     "it diagnoses why the best ensemble cases fail to match observations, "
     "proposes a hypothesis with specific parameter changes, "
     "and tests that hypothesis against the existing 4,890 simulations. "
     "When a hypothesis is not supported, the AI learns from the failure "
     "and returns to diagnosis with new insights. "
     "Only after four cycles of deepening understanding "
     "did the AI design seven experiments and submit them to Perlmutter. "
     "All of this skip-testing happened in about 30 minutes "
     "with no new HPC simulations.",
     2),

    (3, "Phase 1: Morris Sensitivity",
     "Phase 1 runs a Morris sensitivity analysis of 162 parameters "
     "across 4,890 simulations. "
     "This figure shows the sensitivity ranking for leaf biomass by PFT. "
     "Each PFT has different dominant controls. "
     "PFT7, the evergreen shrub, is most sensitive to the phenology GDD threshold "
     "and leaf turnover. "
     "PFT9, the deciduous shrub, shows strong sensitivity to the leaf-to-fineroot ratio. "
     "PFT10, the Arctic graminoid, is controlled by nitrogen store ratio "
     "and, interestingly, a cross-PFT ammonium uptake parameter. "
     "These rankings guide the AI's search for root causes, "
     "but sensitivity alone cannot explain multi-factor interactions.",
     3),

    (4, "Phase 2: Screening Text",
     "Phase 2 screens the full ensemble against six validation targets: "
     "leaf and fineroot biomass for each of the three PFTs. "
     "The results are sobering. "
     "Out of 4,890 simulations, zero meet more than three of the six targets. "
     "86.6 percent of cases meet zero targets. "
     "Only four cases meet three targets, and none meet four or more. "
     "The best case, number 322, meets three targets with an RMSRE of 0.614. "
     "Interestingly, the lowest overall error case, number 1386, "
     "meets zero targets despite having a lower RMSRE of 0.586. "
     "This shows that discrete target satisfaction and continuous error metrics "
     "can disagree, making this a hard combinatorial optimization problem.",
     4),

    (5, "Phase 2: Top 100 Cases",
     "This figure shows the top 100 ensemble cases as light blue lines "
     "for all six biomass targets. "
     "The black diamond marks the observation with its 20 percent uncertainty range. "
     "The best case 322 is shown in blue, and the lowest RMSRE case 1386 in red. "
     "You can see that no single case reaches all targets simultaneously. "
     "Some cases do well for PFT7 but poorly for PFT10, and vice versa. "
     "This is why AI-driven multi-target calibration is essential.",
     5),

    (6, "Iteration 1: Diagnosis",
     "In the first diagnosis, the AI sees a monolithic picture: "
     "systemic phosphorus starvation across all PFTs. "
     "The numbers are extreme: total P demand is 358,000 grams per square meter per year, "
     "while total P supply is only 0.67 grams. "
     "That's a demand-to-supply ratio of over 500,000 to 1. "
     "PFT7 captures 73 percent of the tiny P supply, "
     "PFT9 gets 25 percent, "
     "and PFT10, the Arctic graminoid, gets only 2 percent. "
     "The AI's initial causal model is straightforward: "
     "extreme P demand leads to ECA competition where PFT7 dominates, "
     "PFT10 gets essentially zero phosphorus, "
     "the PID controller diverts carbon to roots, "
     "and leaf biomass collapses. "
     "The proposed fix is PFT10-centric: boost vmax_p_10 by 100x.",
     6),

    (7, "P Mass Balance Evidence",
     "This diagnostic plot, generated by the AI's analysis scripts, "
     "shows the phosphorus mass balance for Case 322. "
     "Panel C reveals that litter P pools accumulate massively, "
     "meaning phosphorus is trapped in decomposing litter. "
     "Panel E shows that P uptake flux is near zero for vegetation. "
     "Panel F shows the total ecosystem P budget: "
     "about 1,243 grams of P per square meter total, "
     "but almost none available to plants. "
     "98.9 percent of soil P is locked in mineral pools. "
     "The tiny available fraction is fought over by three PFTs "
     "with astronomically inflated demand.",
     7),

    (8, "PFT10 Overview Evidence",
     "This six-panel diagnostic overview of PFT10 in Case 322 "
     "shows the Arctic graminoid in total collapse. "
     "Panel A shows fineroot biomass far below the 382 gram target. "
     "Panel B shows leaf biomass near zero versus the 82.7 target. "
     "Panel C reveals the P uptake-to-demand ratio is essentially zero. "
     "Panel D shows that GPP is dominated by PFT7 and PFT9, "
     "while PFT10 contributes negligibly. "
     "Panel E shows L2FR spikes indicating unstable allocation. "
     "And Panel F shows near-zero allocation to both leaf and root. "
     "This is complete vegetation collapse.",
     8),

    (9, "Iteration 1: Hypothesis Result",
     "The first hypothesis proposed boosting PFT10's competitive ability "
     "by increasing vmax_p_10 by 100 times, "
     "reducing P stoichiometry, and adjusting the leaf-to-fineroot ratio. "
     "But skip-testing against the existing ensemble rejected this hypothesis. "
     "When comparing cases with high versus low vmax_p_10, "
     "PFT10 leaf biomass was 0.006 versus 0.003 grams per square meter. "
     "Both are essentially zero. "
     "The entire ensemble operates within a regime of total P-starvation collapse. "
     "Improving PFT10's competitive position within a collapsed system has no effect. "
     "The key learning: you cannot fix a PFT within a system that is universally collapsed. "
     "The problem is bigger than PFT10.",
     9),

    (10, "Iteration 2: Diagnosis",
     "After the first failure, the AI's diagnosis becomes more nuanced. "
     "Instead of one monolithic problem, it now recognizes three distinct failure modes. "
     "PFT9 has l2fr_ini at 18.31, at the upper bound, "
     "which routes over 95 percent of carbon to fine roots, starving leaves. "
     "PFT9 leaf is only 26.6 versus the target of 124.7. "
     "PFT7 has the opposite problem: l2fr_ini at 0.85 is too leaf-biased, "
     "giving insufficient root allocation. "
     "And PFT10 faces structural collapse with three allometric parameters "
     "all at their lower bounds. "
     "A critical realization: PFT10's absolute P demand is only 15.5 grams per year, "
     "which is 10,000 times smaller than PFT7 and PFT9. "
     "This pivots the thinking: PFT10's collapse is more about structural failures "
     "than P competition.",
     10),

    (11, "PFT9 Diagnostic Evidence",
     "This diagnostic plot for PFT9 in Case 322 reveals the deciduous shrub's leaf starvation. "
     "Panel A shows fineroot biomass overshooting, heavily root-biased. "
     "Panel B shows leaf biomass at only 26.6, far below the target of 124.7. "
     "Panel E shows the L2FR ratio driven by the extreme l2fr_ini value of 18.31. "
     "Panel F confirms root allocation dominates while leaf allocation is starved. "
     "The AI identified that PFT9's leaf deficit is caused by allocation imbalance, "
     "not P starvation. This is a distinct mechanism from PFT10's failure.",
     11),

    (12, "Iteration 2: Hypothesis Result",
     "The second hypothesis proposed dual l2fr corrections: "
     "reducing PFT9's l2fr from 18.3 to 4.5 and increasing PFT7's from 0.85 to 1.8, "
     "plus allometric rescue for PFT10. "
     "But skip-testing found this was also not supported. "
     "Case 3972, with l2fr_ini_9 at 5.24, appeared to show PFT9 leaf at 85.2 grams "
     "from the Y-matrix. But the diagnostic script found PFT9 leaf at only 0.037 grams "
     "at the actual observation timestep of July 2016. "
     "This is because the Y-matrix stores multi-year means for sensitivity analysis, "
     "while diagnostics evaluate at a specific point in time. "
     "For collapsing vegetation, annual means can be non-zero "
     "while the observation-timestep value is near zero. "
     "The AI caught this discrepancy and self-corrected. "
     "The l2fr correction alone cannot overcome systemic P starvation.",
     12),

    (13, "Iteration 3: Diagnosis",
     "In the third iteration, the AI discovers a completely new failure mode: "
     "hydraulic mortality is killing PFT10. "
     "Diagnostic scripts revealed that 92 percent of PFT10 deaths "
     "are from hydraulic failure, with only 5 percent from carbon starvation. "
     "The root cause: mort_hf_sm_threshold_10 is at 1 times 10 to the minus 8, "
     "the absolute lower bound. "
     "This means any soil moisture level triggers hydraulic death for PFT10. "
     "Plants are killed before they can grow. "
     "The AI now identifies three distinct failure regimes: "
     "systemic P starvation affecting all PFTs, "
     "hydraulic mortality specifically killing PFT10, "
     "and structural or allometric collapse also in PFT10. "
     "GPP equals zero and maintenance respiration equals zero for best cases. "
     "The system is in total collapse.",
     13),

    (14, "Mortality Components Evidence",
     "This mortality decomposition plot, generated by the AI's diagnostic scripts, "
     "shows three panels for each PFT. "
     "PFT7 at the top shows mortality dominated by hydraulic failure in red, "
     "with periodic carbon starvation in orange. "
     "PFT9 in the middle shows episodic mortality spikes "
     "with a mix of hydraulic and carbon starvation. "
     "PFT10 at the bottom shows the critical finding: "
     "92 percent hydraulic failure, persistent death at nearly every timestep. "
     "This plot revealed a mechanism that was invisible "
     "in the sensitivity analysis and screening phases.",
     14),

    (15, "Iteration 3: Hypothesis Result",
     "The third hypothesis proposed fixing the hydraulic mortality threshold "
     "plus P demand relief and PID stabilization. "
     "But skip-testing again did not support this. "
     "Cases with high mortality thresholds showed only 1.09 times more PFT10 biomass "
     "than cases with low thresholds. The expected ratio was at least 2x. "
     "More importantly, Case 4007 achieves PFT10 fineroot biomass of 0.297 grams "
     "even with the mortality threshold at its lower bound. "
     "If hydraulic mortality were the primary cause, "
     "cases at the lower bound should have zero biomass. They don't. "
     "Conclusion: hydraulic mortality is a secondary symptom, not the root cause.",
     15),

    (16, "Iteration 4: The Breakthrough",
     "In the fourth and final diagnosis, the AI makes a breakthrough. "
     "It asks: what actually drives the 534,000-to-1 demand-to-supply ratio? "
     "The answer: vmax_nh4_7 and vmax_no3_9 are both at their upper bounds. "
     "ECA demand equals vmax times fine root carbon. "
     "With extreme vmax values, PFT7 and PFT9 each generate "
     "over 160,000 grams per square meter per year of P demand. "
     "PFT10 could have any vmax value and it wouldn't matter, "
     "because PFT7 plus PFT9 demand completely dwarfs the supply. "
     "Crucially, the ensemble contains existence proofs: "
     "Case 648 achieves PFT10 leaf at 79.6, within 3.6 percent of the 82.7 target. "
     "Case 3972 has vmax_nh4_7 seven times lower and shows better PFT7 fineroot. "
     "The targets are reachable. The problem is Case 322's extreme vmax values.",
     16),

    (17, "The Conceptual Shift",
     "This slide captures the key conceptual shift across the four iterations. "
     "In iterations 1 through 3, the AI was PFT10-centric: "
     "boost PFT10 vmax, fix PFT10 allometry, fix PFT10 mortality. "
     "All failed because PFT10 can't compete in a collapsed system. "
     "In iteration 4, the AI shifts to system-level thinking. "
     "Instead of helping the victim, fix the system. "
     "Reduce PFT7 and PFT9 vmax by 100x to bring total demand "
     "from 358,000 down to about 3,500 grams per year. "
     "At that level, ECA can distribute phosphorus meaningfully to all PFTs. "
     "This is the first time the AI proposes reducing PFT7 and PFT9 parameters. "
     "All prior cycles left the primary vmax bottleneck untouched.",
     17),

    (18, "Iteration 4: Hypothesis",
     "The synthesized hypothesis has seven parameter changes across three pathways. "
     "Pathway 1 is the demand reset: "
     "reduce vmax_nh4_7, vmax_no3_9, and vmax_nh4_9 each by 100x, "
     "bringing total demand from 358,000 to about 3,500. "
     "Pathway 2 is the allocation fix: "
     "reduce l2fr_ini_9 from 18.3 to 5.2 and increase l2fr_ini_7 from 0.85 to 1.8, "
     "correcting the dual-direction allocation problem. "
     "Pathway 3 is stabilization: "
     "increase pid_kd_10 and pid_kd_9 to prevent allocation oscillation "
     "after the system rebalances. "
     "The AI's self-review flagged 8 warnings: "
     "100x changes are aggressive, and 7 simultaneous modifications "
     "prevent causal attribution. "
     "The response: design 7 cumulative experiments to isolate each effect.",
     18),

    (19, "Phase 5: Experiment Design",
     "Phase 5 designs seven cumulative experiments, "
     "each adding one parameter change on top of the previous. "
     "Experiment 1 reduces only vmax_nh4_7 by 100x. "
     "Experiment 2 adds vmax_no3_9 reduction. "
     "Experiment 3 completes the full demand reset with vmax_nh4_9. "
     "Experiment 4 adds the l2fr_ini_9 allocation correction. "
     "Experiment 5 adds l2fr_ini_7 correction. "
     "Experiments 6 and 7 add PID stabilization parameters. "
     "This cumulative design means we can attribute improvement "
     "to each individual change. "
     "All seven experiments were submitted to NERSC Perlmutter, "
     "with results expected in about two days of simulation time.",
     19),

    (20, "Evolution Summary",
     "Let me summarize how the AI's understanding deepened across four iterations. "
     "Iteration 1 saw monolithic P starvation and tried to boost PFT10 vmax. "
     "It failed, teaching us you can't fix a PFT in a collapsed system. "
     "Iteration 2 identified three separate PFT-specific failures "
     "and tried dual l2fr corrections plus allometry. "
     "It failed, revealing the Y-matrix versus observation timestep discrepancy "
     "and that l2fr alone is insufficient. "
     "Iteration 3 discovered hydraulic mortality killing PFT10 "
     "and tried fixing the mortality threshold. "
     "It was refuted: mortality is a symptom, not the cause. "
     "Iteration 4 found the real root cause: systemic vmax inflation in PFT7 and PFT9. "
     "The progression from 'fix the victim' to 'fix the system' "
     "required evidence from three failed hypotheses.",
     20),

    (21, "Key Takeaways",
     "Let me close with the key takeaways from this session. "
     "First, iterative deepening: each failed hypothesis is not wasted. "
     "It eliminates mechanisms and reveals new ones. "
     "Second, self-correction: the AI caught its own data discrepancy "
     "between Y-matrix multi-year means and observation-timestep values. "
     "Third, mechanism-first reasoning: the AI isn't curve-fitting parameters. "
     "It's understanding why the model fails. "
     "Fourth, AI-generated diagnostics: P mass balance, mortality decomposition, "
     "and PFT overview plots were all created by the AI to support its reasoning. "
     "Fifth, skip testing: four complete cycles in about 30 minutes "
     "using existing ensemble data, with no new HPC simulations. "
     "Sixth, cumulative experiment design: seven experiments that isolate individual effects. "
     "And finally, the conceptual shift from fixing the victim to fixing the system "
     "required evidence from three failed hypotheses. "
     "Thank you for your attention. "
     "The code is available at github.com slash jingtao-lbl slash A2MC-elm.",
     21),
]


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


def generate_audio_openai(text, output_path, voice=OPENAI_VOICE, model=OPENAI_MODEL):
    """Generate speech audio using OpenAI TTS API."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    client = OpenAI()
    clean_text = re.sub(r'\s+', ' ', text).strip()
    response = client.audio.speech.create(
        model=model,
        voice=voice,
        input=clean_text,
        speed=1.0
    )
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


# ============================================================
# Main Pipeline
# ============================================================

def main():
    print("=" * 60)
    print("Kougarok Demo - Diagnosis Evolution Video Generator")
    print("=" * 60)

    # Check prerequisites
    if not PRESENTATION_PDF.exists():
        print(f"ERROR: PDF not found: {PRESENTATION_PDF}")
        print("Generate it first:")
        print("  npx @marp-team/marp-cli A2MC_Session_20260309_Diagnosis_Evolution.md "
              "--pdf --allow-local-files")
        return

    # Create output directories
    for d in [OUTPUT_DIR, SLIDES_DIR, AUDIO_DIR, PDF_SLIDES_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    # Step 1: Extract PDF pages
    print("\n[Step 1/5] Extracting PDF slides...")
    pdf_pages = extract_pdf_slides(PRESENTATION_PDF, PDF_SLIDES_DIR)

    # Step 2: Scale slides to 1920x1080
    print("\n[Step 2/5] Scaling slides to 1920x1080...")
    for slide_num, title, script, pdf_page in SLIDE_SCRIPTS:
        page_pattern = f"page-{pdf_page:02d}.png"
        source = PDF_SLIDES_DIR / page_pattern
        if not source.exists():
            page_pattern = f"page-{pdf_page}.png"
            source = PDF_SLIDES_DIR / page_pattern
        if not source.exists():
            print(f"  WARNING: Page image not found for slide {slide_num} (page {pdf_page})")
            continue
        output = SLIDES_DIR / f"slide_{slide_num:02d}.png"
        generate_slide_image(source, output)
        print(f"  Slide {slide_num}: {title}")

    # Step 3: Generate audio
    print(f"\n[Step 3/5] Generating audio ({'OpenAI TTS' if USE_OPENAI_TTS else 'macOS say'})...")
    for slide_num, title, script, pdf_page in SLIDE_SCRIPTS:
        audio_path = AUDIO_DIR / f"slide_{slide_num:02d}.mp3"
        if USE_OPENAI_TTS:
            generate_audio_openai(script, audio_path)
            print(f"  Slide {slide_num}: {title} (OpenAI)")
        else:
            generate_audio_macos(script, audio_path)
            print(f"  Slide {slide_num}: {title} (macOS)")

    # Step 4: Create individual slide videos
    print("\n[Step 4/5] Creating slide videos...")
    video_files = []
    total_duration = 0
    for slide_num, title, script, pdf_page in SLIDE_SCRIPTS:
        image_path = SLIDES_DIR / f"slide_{slide_num:02d}.png"
        audio_path = AUDIO_DIR / f"slide_{slide_num:02d}.mp3"
        video_path = OUTPUT_DIR / f"slide_{slide_num:02d}.mp4"

        if not image_path.exists() or not audio_path.exists():
            print(f"  SKIP slide {slide_num}: missing image or audio")
            continue

        duration = create_slide_video(image_path, audio_path, video_path)
        video_files.append(video_path)
        total_duration += duration
        print(f"  Slide {slide_num}: {title} ({duration:.1f}s)")

    # Step 5: Concatenate into final video
    print("\n[Step 5/5] Concatenating final video...")
    final_output = OUTPUT_DIR / "A2MC_Diagnosis_Evolution.mp4"
    concatenate_videos(video_files, final_output)

    print("\n" + "=" * 60)
    print(f"DONE! Total duration: {total_duration:.0f}s ({total_duration/60:.1f} min)")
    print(f"Final video: {final_output}")
    print(f"\nPlay with: open {final_output}")
    print("=" * 60)


if __name__ == "__main__":
    main()
