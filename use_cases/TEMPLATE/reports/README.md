# `reports/` — the project team-facing synthesis

**A report is written for the project team**, and for a reader with no prior context. It carries the scientific reasoning and analysis for the calibration work, with verified artifacts and source links tracing back to `../memory/logs/` and `../memory/phase_results/`.

## Skills to use when working in this folder

| doing what | skill |
|---|---|
| **writing any report here** | **`write-report`** |
| every figure in it | **`plotting`** |
| a single round's close-out | **`summarize-calibration-round`** |
| comparing rounds R1…RN | **`compare-calibration-rounds`** |
| an investigation that is not a round close | **`scientific-analysis`**, or **`diagnose-forensics`** for an anomaly |
| sending it outside the repo | **`markdown-to-pdf`** |

## What belongs here, and what does not

| | goes to |
|---|---|
| a **cycle** report, a **round summary**, a cross-round synthesis, a standalone investigation | **here** |
| the per-phase reasoning chain | `memory/logs/` |
| figures, data, generating scripts | `memory/phase_results/{stem}/` |
| model source changes, and which round ran which binary | the repo-level `memory/model_logs/` (see `model-evolution`) |

A report **cites** `phase_results/` and copies in only the rendered PNG. The canonical script stays with its figure in the phase folder; regenerate it there, never here.

## The conventions that make a report readable cold

- **Executive summary first**, then finding → mechanism → evidence. Define jargon on first use; the test is whether a stranger to the project can follow it.
- **Figures over tables over words.** Every figure gets a caption and a bold `**Figure N.**` heading; alt text stays **empty** (`![](fig.png)`) because pandoc's `implicit_figures` turns alt text into a `<figcaption>`, so a labelled alt renders the label twice. `python tools/check_report_figures.py` rejects one.
- **Every quantitative claim names its source** — the figure, the statistic, or the data file.
- **Equations in LaTeX** (`$…$` / `$$…$$`), never ASCII art, so the report typesets when converted.
- **No em dashes** in report prose specifically (user preference; it carries through to the rendered PDF). Logs use them freely.
- **Prose is not hard-wrapped.** One paragraph, one long line.
- **Author line:** `**Author:** Jing Tao with A2MC` — no host or machine suffix. The `with A2MC` form is report-specific; every other artifact keeps `with Claude`.

## Naming

`YYYYMMDDx_Topic/`, one folder per report, each self-contained: the `.md`, its figures, their captions, and the data. `YYYYMMDDx_R*_c*/` closes an experiment cycle; `YYYYMMDDx_*_ROUND_SUMMARY/` closes a round and carries the next-round work plan.
