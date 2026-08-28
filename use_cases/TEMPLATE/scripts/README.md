# `scripts/` — the case's own long-lived scripts, and its script TEMPLATES

Two kinds of file live here, and the distinction decides where an adapted copy belongs:

1. **Case-level scripts that are run in place** — the site's auto-monitor, a multi-round bundle, a validator against an external dataset. These are long-lived, reused across rounds, and legitimately live here.
2. **Templates** — a starting point copied into a phase's own `memory/phase_results/{stem}/` and adapted there. The adapted copy is the canonical script for that figure or analysis and ships beside its caption and data.

## Skills to use when working in this folder

| doing what | skill |
|---|---|
| **before the first `savefig`** — not after | **`plotting`** (its load-bearing rule is to open the rendered PNG and look at it) |
| copying a template into a phase folder | that phase's own skill, `phase0-design` … `phase6-refinement` |
| a cross-round figure or bundle | **`compare-calibration-rounds`** |
| a one-round close-out figure set | **`summarize-calibration-round`** |
| a standalone investigation | **`scientific-analysis`** |
| the site's live auto-monitor script | **`arm-hpc-monitoring`** |
| deciding whether a script has earned promotion to here | **`calibration-discipline`** |

## The rule that keeps a figure reproducible

**A figure's canonical script lives with the figure, in `memory/phase_results/{stem}/` — not here.** When a plot needs changing, edit and regenerate it *there*; do not develop it in a scratch copy and paste the result back. A script here that produced a specific figure is a **template or a historical starting point**, never the record of how that figure was made.

Promotion runs the other way, and it is deliberate: a script proven useful across several phases can be generalized and moved up — first to here, and if it turns out to be site-agnostic, on to the repo-level `tools/`. Several of `tools/`'s plotting and extraction utilities began as case scripts and record that provenance in their headers.

## Conventions

- **Every script sources the config chain** rather than hard-coding a path — `a2mc_config.sh`, then the case config. A hard-coded output root outlives the config that was meant to own it.
- **Name a figure script for what it renders**, including the round and the case count, so two renders cannot silently overwrite each other.
- **Nothing here writes outside the repo or the configured output root.**
