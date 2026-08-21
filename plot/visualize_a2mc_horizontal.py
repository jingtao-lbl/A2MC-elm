#!/usr/bin/env python3
"""
A2MC - Agentic Adaptive Multi-target Calibration
Horizontal Flowchart for Presentation

Features:
- Horizontal layout (fits 16:9 PPT slides)
- Large fonts for readability
- All 7 phases including DESIGN
- Proper iteration loop with label
- Adaptive Memory System integration

Created: January 10, 2026
Author: Jing Tao with Claude
"""

import os
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

# =============================================================================
# CONFIGURATION
# =============================================================================

# Figure size optimized for 16:9 PPT slides
FIG_WIDTH = 16
FIG_HEIGHT = 9

# Font sizes (LARGE for presentation)
FONT_TITLE = 26
FONT_PHASE = 16
FONT_DESCRIPTION = 16  # Increased from 14
FONT_FEATURE = 13
FONT_ARROW_LABEL = 14

# Z-order (higher = on top)
ZORDER_LINES = 1
ZORDER_ARROWS = 2
ZORDER_BOXES = 10
ZORDER_TEXT = 15

# Colors
COLORS = {
    'design': '#E3F2FD',       # Light blue
    'exploration': '#E8F5E9',   # Light green
    'screening': '#FFF3E0',     # Light orange
    'diagnosis': '#F3E5F5',     # Light purple
    'hypothesis': '#FCE4EC',    # Light pink
    'testing': '#E0F7FA',       # Light cyan
    'refinement': '#FBE9E7',    # Light deep orange
    'converged': '#C8E6C9',     # Green
    'ai_agent': '#FFE0B2',      # Light peach
    'memory': '#E1BEE7',        # Light purple
    'iteration': '#FFCDD2',     # Light red
}

# Phase colors for labels
PHASE_COLORS = {
    'design': '#1565C0',
    'exploration': '#2E7D32',
    'screening': '#EF6C00',
    'diagnosis': '#7B1FA2',
    'hypothesis': '#C2185B',
    'testing': '#00838F',
    'refinement': '#D84315',
    'converged': '#1B5E20',
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def add_phase_box(ax, x, y, width, height, phase_num, phase_name, description,
                  color, phase_color, text_offset=0.05):
    """Add a phase box with header and description.
    
    text_offset: fraction of height to offset description text downward (default 0.05)
                 Use larger values (e.g., 0.12) for multi-line descriptions
    """
    # Main box (high z-order to be on top of lines)
    box = FancyBboxPatch(
        (x - width/2, y - height/2), width, height,
        boxstyle="round,pad=0.02,rounding_size=0.2",
        edgecolor=phase_color, facecolor=color, linewidth=3,
        zorder=ZORDER_BOXES
    )
    ax.add_patch(box)

    # Phase header
    header_height = height * 0.35
    header = FancyBboxPatch(
        (x - width/2, y + height/2 - header_height), width, header_height,
        boxstyle="round,pad=0.02,rounding_size=0.2",
        edgecolor=phase_color, facecolor=phase_color, linewidth=0,
        zorder=ZORDER_BOXES + 1
    )
    ax.add_patch(header)

    # Phase label text
    ax.text(x, y + height/2 - header_height/2, f"Phase {phase_num}: {phase_name}",
            ha='center', va='center', fontsize=FONT_PHASE, weight='bold',
            color='white', zorder=ZORDER_TEXT)

    # Description text (LARGER)
    ax.text(x, y - height*text_offset, description,
            ha='center', va='center', fontsize=FONT_DESCRIPTION,
            weight='bold', zorder=ZORDER_TEXT)

    return x, y


def add_feature_box(ax, x, y, width, height, text, color):
    """Add a feature indicator box."""
    box = FancyBboxPatch(
        (x - width/2, y - height/2), width, height,
        boxstyle="round,pad=0.05,rounding_size=0.2",
        edgecolor='black', facecolor=color, linewidth=2,
        zorder=ZORDER_BOXES
    )
    ax.add_patch(box)
    ax.text(x, y, text, ha='center', va='center',
            fontsize=FONT_FEATURE, weight='bold', zorder=ZORDER_TEXT)


def add_arrow(ax, x1, y1, x2, y2, color='black', width=2, style='-', zorder=ZORDER_ARROWS):
    """Add an arrow between two points."""
    arrow = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle='->', mutation_scale=20,
        linestyle=style, linewidth=width,
        color=color, zorder=zorder
    )
    ax.add_patch(arrow)


# =============================================================================
# MAIN FIGURE
# =============================================================================

fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
ax.set_xlim(0, 16)
ax.set_ylim(0, 9)
ax.axis('off')

# Title
ax.text(8, 8.5, 'Agentic Adaptive Multi-target Calibration (A2MC)',
        ha='center', va='center', fontsize=FONT_TITLE, weight='bold',
        zorder=ZORDER_TEXT)

# =============================================================================
# LAYOUT PARAMETERS
# =============================================================================
row1_y = 6.0
row2_y = 2.8
box_width = 3.2
box_height = 2.0
gap = 0.6

# Calculate x positions (x0 controls left margin for entire flowchart)
x0 = 2.5
x1 = x0 + box_width + gap
x2 = x1 + box_width + gap
x3 = x2 + box_width + gap

# =============================================================================
# INNER ITERATION LOOP: Phase 6 (REFINEMENT) → Phase 3 (DIAGNOSIS)
# =============================================================================
# With new layout: REFINEMENT is at x1, DIAGNOSIS is at x3
# Route: From REFINEMENT top → through gap → RIGHT to DIAGNOSIS

inner_loop_color = '#1976D2'  # Blue for inner loop
inner_loop_width = 2.5

# Inner loop coordinates (stays in the gap between rows)
inner_mid_y = (row1_y + row2_y) / 2  # Middle of gap between rows
inner_start_x = x1  # REFINEMENT is now at x1
inner_end_x = x3 - 0.4  # Shifted LEFT to avoid overlap with black arrow

# Segment 1: From REFINEMENT top, go UP to gap level (lowered for longer arrow)
inner_line_y = inner_mid_y - 0.2  # Lower position to allow longer arrow
ax.plot([inner_start_x, inner_start_x], [row2_y + box_height/2, inner_line_y],
        color=inner_loop_color, linewidth=inner_loop_width, linestyle='--', zorder=ZORDER_LINES)

# Segment 2: Go RIGHT toward DIAGNOSIS (but shifted left)
ax.plot([inner_start_x, inner_end_x], [inner_line_y, inner_line_y],
        color=inner_loop_color, linewidth=inner_loop_width, linestyle='--', zorder=ZORDER_LINES)

# Segment 3: Solid arrow pointing UP to DIAGNOSIS (LONGER arrow from lower position)
add_arrow(ax, inner_end_x, inner_line_y, inner_end_x, row1_y - box_height/2 - 0.15,
          color=inner_loop_color, width=inner_loop_width, style='-', zorder=ZORDER_ARROWS)

# Inner loop label (BELOW the dashed line)
ax.text((inner_start_x + inner_end_x) / 2, inner_mid_y + 0.06,
        'Refine: Rethink and adjust hypothesis',
        ha='center', va='top', fontsize=FONT_ARROW_LABEL - 1, weight='bold',
        color=inner_loop_color, zorder=ZORDER_TEXT,
        bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                  edgecolor=inner_loop_color, linewidth=1.5, alpha=0.95))

# =============================================================================
# OUTER ITERATION LOOP: Phase 6 (REFINEMENT) → Phase 0 (DESIGN)
# =============================================================================
# Start from middle of arrow between Phase 6 and Phase 7
# Route: Middle of 6→7 arrow → Down → Left (around CONVERGED) → Up on left side → Down to DESIGN

outer_loop_color = '#D32F2F'  # Red for outer loop
outer_loop_width = 2.5

# Outer loop coordinates
outer_start_x = (x0 + x1) / 2  # Middle of arrow between Phase 6 (x1) and Phase 7 (x0)
outer_bottom_y = row2_y - box_height/2 - 0.4  # Below row 2
outer_left_x = x0 - box_width/2 - 0.4  # Left of CONVERGED (now at x0)
outer_top_y = row1_y + box_height/2 + 0.5  # Above row 1

# Segment 1: From middle of 6→7 arrow, go DOWN (start slightly below to avoid overlap)
ax.plot([outer_start_x, outer_start_x], [row2_y - 0.3, outer_bottom_y],
        color=outer_loop_color, linewidth=outer_loop_width, linestyle='--', zorder=ZORDER_LINES)

# Segment 2: Go LEFT (around CONVERGED which is now at x0)
ax.plot([outer_start_x, outer_left_x], [outer_bottom_y, outer_bottom_y],
        color=outer_loop_color, linewidth=outer_loop_width, linestyle='--', zorder=ZORDER_LINES)

# Segment 3: Go UP (left side of diagram)
ax.plot([outer_left_x, outer_left_x], [outer_bottom_y, outer_top_y],
        color=outer_loop_color, linewidth=outer_loop_width, linestyle='--', zorder=ZORDER_LINES)

# Segment 4: Go RIGHT (above row 1, to DESIGN at x0)
ax.plot([outer_left_x, x0], [outer_top_y, outer_top_y],
        color=outer_loop_color, linewidth=outer_loop_width, linestyle='--', zorder=ZORDER_LINES)

# Segment 5: Solid arrow pointing down to DESIGN
add_arrow(ax, x0, outer_top_y, x0, row1_y + box_height/2 + 0.1,
          color=outer_loop_color, width=outer_loop_width, style='-', zorder=ZORDER_ARROWS)

# Outer loop label (VERTICAL, on left side of the red dashed line)
ax.text(outer_left_x - 0.3, (outer_bottom_y + outer_top_y) / 2,
        'Redesign: Expand parameter space if refinement fails',
        ha='center', va='center', fontsize=FONT_ARROW_LABEL, weight='bold',
        color=outer_loop_color, zorder=ZORDER_TEXT, rotation=90,
        bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                  edgecolor=outer_loop_color, linewidth=2, alpha=0.95))

# =============================================================================
# ROW 1: Phases 0-3 (Design → Exploration → Screening → Diagnosis)
# =============================================================================

# Phase 0: DESIGN (3+ lines, use larger text_offset)
add_phase_box(ax, x0, row1_y, box_width, box_height,
              "0", "DESIGN", "Initial Parameter List;\nMorris/Sobol\nSampling Design;\nSimulation Execution",
              COLORS['design'], PHASE_COLORS['design'], text_offset=0.13)

# Phase 1: EXPLORATION (3 lines, use larger text_offset)
add_phase_box(ax, x1, row1_y, box_width, box_height,
              "1", "EXPLORATION", "Global Sensitivity\nAnalysis; Rank\nParameter Importance",
              COLORS['exploration'], PHASE_COLORS['exploration'], text_offset=0.12)

# Phase 2: SCREENING
add_phase_box(ax, x2, row1_y, box_width, box_height,
              "2", "SCREENING", "Multi-Objective\nValidation",
              COLORS['screening'], PHASE_COLORS['screening'])

# Phase 3: DIAGNOSIS
add_phase_box(ax, x3, row1_y, box_width, box_height,
              "3", "DIAGNOSIS", "Edge Case Detection;\n Case Comparison",
              COLORS['diagnosis'], PHASE_COLORS['diagnosis'])

# Arrows Row 1 (between boxes, not through them)
arrow_y1 = row1_y
add_arrow(ax, x0 + box_width/2 + 0.1, arrow_y1, x1 - box_width/2 - 0.1, arrow_y1)
add_arrow(ax, x1 + box_width/2 + 0.1, arrow_y1, x2 - box_width/2 - 0.1, arrow_y1)
add_arrow(ax, x2 + box_width/2 + 0.1, arrow_y1, x3 - box_width/2 - 0.1, arrow_y1)

# =============================================================================
# ROW 2: Phases 4-7 (FLIPPED: right to left for snake pattern)
# Phase 4 below Phase 3, then 5, 6, 7 going left
# =============================================================================

# Phase 4: HYPOTHESIS (at x3, below DIAGNOSIS)
add_phase_box(ax, x3, row2_y, box_width, box_height,
              "4", "HYPOTHESIS", "Generate Hypotheses;\nExperimental Design;",
              COLORS['hypothesis'], PHASE_COLORS['hypothesis'])

# Phase 5: TESTING (at x2)
add_phase_box(ax, x2, row2_y, box_width, box_height,
              "5", "TESTING", "Parameter File Creation;\nCreate New Case Scripts;\nSimulation Execution",
              COLORS['testing'], PHASE_COLORS['testing'])

# Phase 6: REFINEMENT (at x1) - Purple to match Adaptive Memory
add_phase_box(ax, x1, row2_y, box_width, box_height,
              "6", "REFINEMENT", "Evaluate Results;\nExtract Lessons",
              COLORS['memory'], PHASE_COLORS['diagnosis'])  # Purple theme for memory learning

# Phase 7: CONVERGED (at x0)
add_phase_box(ax, x0, row2_y, box_width, box_height,
              "7", "CONVERGED", "Optimal\nConfiguration",
              COLORS['converged'], PHASE_COLORS['converged'])

# Arrows Row 2 (RIGHT to LEFT: Phase 4 → 5 → 6 → 7)
arrow_y2 = row2_y
add_arrow(ax, x3 - box_width/2 - 0.1, arrow_y2, x2 + box_width/2 + 0.1, arrow_y2)  # 4 → 5
add_arrow(ax, x2 - box_width/2 - 0.1, arrow_y2, x1 + box_width/2 + 0.1, arrow_y2)  # 5 → 6
add_arrow(ax, x1 - box_width/2 - 0.1, arrow_y2, x0 + box_width/2 + 0.1, arrow_y2)  # 6 → 7

# =============================================================================
# AI BADGES: Mark AI-driven phases (2, 3, 4, 6)
# =============================================================================
ai_badge_color = COLORS['ai_agent']  # Same as "AI Agent" feature box (#FFE0B2)

def add_ai_badge(ax, x, y, box_w, box_h):
    """Add an 'AI' badge to the bottom-right corner of a phase box."""
    badge_x = x + box_w/2 - 0.35
    badge_y = y - box_h/2 + 0.35
    # Draw circular badge
    circle = plt.Circle((badge_x, badge_y), 0.25,
                        facecolor=ai_badge_color, edgecolor='black',
                        linewidth=1.5, zorder=ZORDER_BOXES + 5)
    ax.add_patch(circle)
    ax.text(badge_x, badge_y, 'AI', ha='center', va='center',
            fontsize=10, weight='bold', color='black', zorder=ZORDER_TEXT + 5)

# Add AI badges to phases 2, 3, 4, 6
add_ai_badge(ax, x2, row1_y, box_width, box_height)  # Phase 2: SCREENING
add_ai_badge(ax, x3, row1_y, box_width, box_height)  # Phase 3: DIAGNOSIS
add_ai_badge(ax, x3, row2_y, box_width, box_height)  # Phase 4: HYPOTHESIS
add_ai_badge(ax, x1, row2_y, box_width, box_height)  # Phase 6: REFINEMENT

# =============================================================================
# CONNECTING ARROW: DIAGNOSIS → HYPOTHESIS (simple vertical drop)
# =============================================================================
# Both are now at x3 (Phase 3 above, Phase 4 below)
# Simple vertical arrow

add_arrow(ax, x3, row1_y - box_height/2 - 0.1, x3, row2_y + box_height/2 + 0.1,
          color='black', width=2, zorder=ZORDER_ARROWS)

# =============================================================================
# KEY FEATURES (Bottom row)
# =============================================================================
feature_y = 0.55
feature_box_width = 3.0
feature_box_height = 0.7

# Feature 1: AI Agent
add_feature_box(ax, 2.0, feature_y, feature_box_width, feature_box_height,
                'AI Agent\nAutonomous Reasoning', COLORS['ai_agent'])

# Feature 2: Adaptive Memory
add_feature_box(ax, 5.6, feature_y, feature_box_width, feature_box_height,
                'Adaptive Memory\nLearning from Experiments', COLORS['memory'])

# Feature 3: Multi-Target
add_feature_box(ax, 9.2, feature_y, feature_box_width, feature_box_height,
                'Multi-Target Optimization\n6 Biomass + 2 Ecosystem', COLORS['screening'])

# Feature 4: Iterative
add_feature_box(ax, 12.8, feature_y, feature_box_width, feature_box_height,
                'Iterative Refinement\nHypothesis-Driven', COLORS['iteration'])

# =============================================================================
# SAVE
# =============================================================================
plt.tight_layout()

# In-repo, next to this script: the figure is a repo artifact, and the old
# absolute path only existed on one machine.
output_file = str(Path(__file__).resolve().parent / 'A2MC_Workflow_Horizontal.png')
plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
print(f"\n[OK] Horizontal A2MC workflow saved: {output_file}")

# Optional second copy, opt-in via env var (was a hardcoded personal directory
# that exists on no other machine, so the save always failed elsewhere).
_extra = os.environ.get('A2MC_WORKFLOW_FIGURE_COPY')
if _extra:
    output_file2 = str(Path(_extra) / 'A2MC_Workflow_Horizontal.png')
    plt.savefig(output_file2, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"[OK] Also saved to: {output_file2}")

plt.close()
