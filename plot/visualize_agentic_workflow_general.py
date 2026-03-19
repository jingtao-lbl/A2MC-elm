#!/usr/bin/env python3
"""
AI-Enabled Agentic Workflow for Multi-Target Calibration - GENERAL FLOWCHART

This is the general conceptual flowchart showing the high-level phases and connections.

Created: December 15, 2025
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

# Figure setup - optimized for clarity (reduced width, legend inside boxes)
fig, ax = plt.subplots(1, 1, figsize=(12, 28))
ax.set_xlim(0, 11)
ax.set_ylim(-9, 30)
ax.axis('off')

# Color scheme
COLOR_EXPLORATION = '#E8F4F8'      # Light blue
COLOR_SCREENING = '#FFF4E6'        # Light orange
COLOR_DIAGNOSIS = '#F0E6FF'        # Light purple
COLOR_HYPOTHESIS = '#FFE6E6'       # Light pink
COLOR_TESTING = '#E6FFE6'          # Light green
COLOR_REFINEMENT = '#FFE6F0'       # Light rose
COLOR_DECISION = '#FFFFCC'         # Light yellow
COLOR_AI = '#FFE6CC'               # Light peach
COLOR_SUCCESS = '#CCFFCC'          # Light green

# Helper functions
def add_box(x, y, width, height, text, color, fontsize=14, bold=False, style='round'):
    """Add a box with text"""
    if style == 'round':
        box = FancyBboxPatch((x, y), width, height,
                            boxstyle="round,pad=0.15",
                            edgecolor='black', facecolor=color,
                            linewidth=3)
    elif style == 'diamond':
        points = np.array([
            [x + width/2, y + height],
            [x + width, y + height/2],
            [x + width/2, y],
            [x, y + height/2],
        ])
        box = mpatches.Polygon(points, closed=True,
                              edgecolor='black', facecolor=color,
                              linewidth=3)
    else:  # rectangle
        box = FancyBboxPatch((x, y), width, height,
                            boxstyle="square,pad=0.1",
                            edgecolor='black', facecolor=color,
                            linewidth=3)

    ax.add_patch(box)

    weight = 'bold' if bold else 'normal'
    ax.text(x + width/2, y + height/2, text,
           ha='center', va='center',
           fontsize=fontsize, weight=weight,
           wrap=True)

    return box

def add_arrow(x1, y1, x2, y2, label='', style='solid', color='black', width=3):
    """Add an arrow between boxes"""
    gap = 0.2

    dx = x2 - x1
    dy = y2 - y1
    length = np.sqrt(dx**2 + dy**2)

    if length > 0:
        ux, uy = dx/length, dy/length
        x1_adj = x1 + ux * gap
        y1_adj = y1 + uy * gap
        x2_adj = x2 - ux * gap
        y2_adj = y2 - uy * gap
    else:
        x1_adj, y1_adj, x2_adj, y2_adj = x1, y1, x2, y2

    arrow = FancyArrowPatch((x1_adj, y1_adj), (x2_adj, y2_adj),
                           arrowstyle='->', mutation_scale=30,
                           linestyle=style, linewidth=width,
                           color=color, zorder=1)
    ax.add_patch(arrow)

    if label:
        mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mid_x + 0.5, mid_y, label,
               ha='center', va='center',
               fontsize=16, weight='bold',
               bbox=dict(boxstyle='round,pad=0.5',
                        facecolor='white', edgecolor=color, alpha=0.95, linewidth=2))

def add_phase_label(x, y, text, color, fontsize=18):
    """Add a phase label"""
    ax.text(x, y, text,
           ha='center', va='center',
           fontsize=fontsize, weight='bold',
           color='white',
           bbox=dict(boxstyle='round,pad=0.8',
                    facecolor=color, edgecolor='black', linewidth=3))

# =============================================================================
# TITLE
# =============================================================================
ax.text(5, 29.5, 'Agentic Adaptive Multi-target Calibration (A2MC)',
       ha='center', va='top', fontsize=28, weight='bold')
ax.text(5, 28.6, 'Workflow for ELM-FATES',
       ha='center', va='top', fontsize=28, style='italic')

# =============================================================================
# PHASE 1: EXPLORATION
# =============================================================================
y1 = 27
add_phase_label(5, y1, 'PHASE 1: EXPLORATION', '#0066CC')

add_box(1.5, y1 - 2, 7, 1.5,
       'Global Sensitivity Analysis\nIdentify influential parameters',
       COLOR_EXPLORATION, fontsize=18, bold=True)

add_box(1.5, y1 - 4, 7, 0.8,
       '[AI Agent] Rank parameters by importance',
       COLOR_AI, fontsize=16)

add_arrow(5, y1 - 2, 5, y1 - 3.2)

# =============================================================================
# PHASE 2: SCREENING
# =============================================================================
y2 = y1 - 5
add_phase_label(5, y2, 'PHASE 2: SCREENING', '#FF8800')

add_box(1.5, y2 - 2, 7, 1.5,
       'Multi-Objective Validation\nCalculate performance metrics',
       COLOR_SCREENING, fontsize=18, bold=True)

add_box(1.5, y2 - 4, 7, 0.8,
       '[AI Agent] Identify best-performing cases',
       COLOR_AI, fontsize=16)

add_arrow(5, y1 - 4, 5, y2 - 0.5)
add_arrow(5, y2 - 2, 5, y2 - 3.2)

# =============================================================================
# PHASE 3: DIAGNOSIS
# =============================================================================
y3 = y2 - 5
add_phase_label(5, y3, 'PHASE 3: DIAGNOSIS', '#9900CC')

add_box(1.5, y3 - 2, 7, 1.5,
       'Multi-Level Analysis\nEdge Analysis | Case Compare | Calibration',
       COLOR_DIAGNOSIS, fontsize=18, bold=True)

add_box(1.5, y3 - 4, 7, 0.8,
       '[AI Agent] Generate mechanistic hypotheses',
       COLOR_AI, fontsize=16)

add_arrow(5, y2 - 4, 5, y3 - 0.5)
add_arrow(5, y3 - 2, 5, y3 - 3.2)

# =============================================================================
# PHASE 4: HYPOTHESIS
# =============================================================================
y4 = y3 - 5
add_phase_label(5, y4, 'PHASE 4: HYPOTHESIS', '#CC0066')

add_box(1.5, y4 - 2, 7, 1.5,
       'Hypothesis Generation\nMechanistic understanding of failures',
       COLOR_HYPOTHESIS, fontsize=18, bold=True)

add_box(1.5, y4 - 4, 7, 0.8,
       '[AI Agent] Design experiments to test hypotheses',
       COLOR_AI, fontsize=16)

add_arrow(5, y3 - 4, 5, y4 - 0.5)
add_arrow(5, y4 - 2, 5, y4 - 3.2)

# =============================================================================
# PHASE 5: TESTING
# =============================================================================
y5 = y4 - 5
add_phase_label(5, y5, 'PHASE 5: TESTING', '#00AA00')

add_box(1.5, y5 - 2, 7, 1.5,
       'Iterative Experimentation\nFull Factorial Parameter Modifications',
       COLOR_TESTING, fontsize=18, bold=True)

add_arrow(5, y4 - 4, 5, y5 - 0.5)

# Decision node 1 - Performance Satisfactory?
decision1_y = y5 - 5.0
add_box(3.5, decision1_y, 3, 1.5,
       'Performance\nSatisfactory?',
       COLOR_DECISION, fontsize=14, bold=True, style='diamond')

add_arrow(5, y5 - 2, 5, decision1_y + 1.5)

# NO branch - iterate back to diagnosis (from decision 1)
ax.text(2.8, decision1_y + 0.75, 'NO',
       ha='center', va='center', fontsize=16, weight='bold',
       bbox=dict(boxstyle='round,pad=0.4', facecolor='white', edgecolor='red', linewidth=2))
add_arrow(3.5, decision1_y + 0.75, 0.8, decision1_y + 0.75, style='dashed', color='red', width=3)
add_arrow(0.8, decision1_y + 0.75, 0.8, y3 - 1.25, color='red', width=3)

add_arrow(0.05, y3 - 1.25, 1.5, y3 - 1.25, color='red', width=3)

# =============================================================================
# PHASE 6: REFINEMENT
# =============================================================================
y6 = decision1_y - 1.8
add_phase_label(5, y6, 'PHASE 6: REFINEMENT', '#CC3366')

# YES arrow from decision 1 to Phase 6
ax.text(6.0, decision1_y - 0.6, 'YES',
       ha='center', va='center', fontsize=16, weight='bold',
       bbox=dict(boxstyle='round,pad=0.4', facecolor='white', edgecolor='green', linewidth=2))
add_arrow(5, decision1_y, 5, y6 + 0.5, color='green', width=3)

add_box(1.5, y6 - 2, 7, 1.5,
       'Hypothesis Refinement\nIterative improvement',
       COLOR_REFINEMENT, fontsize=18, bold=True)

add_arrow(5, y6 - 0.5, 5, y6 - 0.5)

# Decision node 2 - Targets Achieved?
decision2_y = y6 - 4.5
add_box(3.5, decision2_y, 3, 1.5,
       'Targets\nAchieved?',
       COLOR_DECISION, fontsize=14, bold=True, style='diamond')

add_arrow(5, y6 - 2, 5, decision2_y + 1.5)

# NO branch from decision 2 - back to diagnosis
ax.text(2.8, decision2_y + 0.75, 'NO',
       ha='center', va='center', fontsize=16, weight='bold',
       bbox=dict(boxstyle='round,pad=0.4', facecolor='white', edgecolor='red', linewidth=2))
add_arrow(3.5, decision2_y + 0.75, 0.3, decision2_y + 0.75, style='dashed', color='red', width=3)
add_arrow(0.3, decision2_y + 0.75, 0.3, y3 - 1.25, color='red', width=3)

# =============================================================================
# CONVERGENCE
# =============================================================================
y7 = decision2_y - 1.8
add_phase_label(5, y7, 'CONVERGENCE', '#006600')

# YES arrow from decision 2 to Convergence
ax.text(6.0, decision2_y - 0.6, 'YES',
       ha='center', va='center', fontsize=16, weight='bold',
       bbox=dict(boxstyle='round,pad=0.4', facecolor='white', edgecolor='green', linewidth=2))
add_arrow(5, decision2_y, 5, y7 + 0.5, color='green', width=4)

add_box(1.5, y7 - 1.8, 7, 1.5,
       'OPTIMAL CONFIGURATION\nAll targets achieved',
       COLOR_SUCCESS, fontsize=20, bold=True)

# =============================================================================
# KEY FEATURES (Right side - text inside boxes)
# =============================================================================
feature_x = 9.0
box_width = 1.5
box_height = 1.2

# Box 1: AI Agent Role
add_box(feature_x, 25, box_width, box_height, 'AI Agent\nDecisions', COLOR_AI, fontsize=16, bold=False, style='rectangle')

# Box 2: Iteration
add_box(feature_x, 23.5, box_width, box_height, 'Iterative\nRefinement', '#FFE6E6', fontsize=16, bold=False, style='rectangle')

# Box 3: Multi-objective
add_box(feature_x, 22, box_width, box_height, 'Multi-\nObjective', COLOR_SCREENING, fontsize=16, bold=False, style='rectangle')

# Box 4: Mechanistic
add_box(feature_x, 20.5, box_width, box_height, 'Mechanistic\nConstraints', COLOR_DIAGNOSIS, fontsize=16, bold=False, style='rectangle')

# Tight layout
plt.tight_layout()

# Save
output_file = './AI_Agentic_Workflow_GENERAL.png'
plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
print(f"\n[OK] General workflow diagram saved: {output_file}")

# Don't show - just save
# plt.show()
