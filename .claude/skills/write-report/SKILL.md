---
name: write-report
visibility: public
category: authoring
description: Write a general, integrated, self-contained report on an arbitrary topic for a human reader (PI / collaborator / reviewer) — a crash/bug investigation synthesis, a mechanism study, a cross-cutting result write-up. Structures it for a ZERO-context reader (reader's key → executive summary → sectioned narrative → embedded figures with captions → provenance), gathers citation-backed facts first, and reconciles contradictions across source logs. Use on "write a report", "write up X for the PI/collaborator", "make an integrated report on X", "summarize this investigation into a report", "document the whole X arc". NOT the standardized single-round summary (use summarize-calibration-round) and NOT journal-register prose (use manuscript-writing-style).
allowed-tools: [Read, Glob, Grep, Write, Edit, Bash]
modes:
  requires_fates: false
  nutrient_pathway: any
  scope: [analysis]
  summary: "Integrated, self-contained report for a zero-context human reader. Model-agnostic."
---

# write-report — an integrated, self-contained report for a human reader

A report is read by someone with **zero project context** — a PI, a collaborator, a reviewer, your
future self. It must carry them from "what is this" to "what did we find and how do we know" without any
prior knowledge of the codenames, the pipeline, or the logs it's distilled from. This skill is the
structure + discipline for that; the pieces (figures, PDF) come from sibling skills.

> **Not this skill:** a **standardized single-round calibration summary** → `summarize-calibration-round`
> (fixed deliverable: combined/TRANS ensemble graphs + evaluation + Morris μ*). **Journal-register
> manuscript prose** → `manuscript-writing-style`. A short **internal log** (shorthand OK) → `log` /
> `calibration-log`. This skill is the **general, topic-agnostic integrated report**.

## The discipline (non-negotiable — `<auto-memory>/feedback_report_writing_self_contained`)

- **Zero-context reader.** Assume the reader knows nothing about A2MC internals.
- **Executive summary first** — the whole story (problem → cause → fix → outcome) in a few plain
  paragraphs, before any detail.
- **Define-or-avoid every codename/jargon** — ADSP, PFT, Morris, prescribed-P, V0, PARTEH, etc. Either
  define it on first use (a Reader's key up front for jargon-heavy topics) or don't use it.
- **Every claim is a complete finding→mechanism→evidence sentence** — the plain finding, *why* (mechanism),
  and the *evidence* (a number, a figure, a cited source). No isolated jargon ("72 PARTEH failures are
  restart-eligible" fails; a stranger can't parse it).
- **Stranger test:** could someone outside the project read a section and understand the claim + how you
  know it? If not, rewrite.
- **No em dashes (—).** Do not use the em dash character in report prose (user preference). Use a comma, a
  colon, parentheses, or split the sentence instead. En dashes in numeric ranges (2000-2004) are fine.
  Applies to the rendered PDF too, since the em dash carries through.

## Structure (the recurring skeleton, adapt, don't pad)

1. **Title + a header block** — a one-line status/scope (e.g. "Fix validated; recovery in progress"), the
   date, and an **author/provenance line**. The author line is REQUIRED and is exactly `**Author:** Jing
   Tao with A2MC` (no host / machine suffix). The report-specific author is **A2MC**, not Claude, because
   these `reports/` are public-facing A2MC deliverables and credit the framework that produced them. This
   is deliberately DISTINCT from every other artifact (dev/ana logs, scripts, commits), which keep the
   `CLAUDE.md` author-field convention (`Jing Tao with Claude` / `Jing Tao`) — see
   [[feedback_report_author_a2mc]]. The `with A2MC` form applies ONLY to `reports/` written by this skill.
   Note the companion report/log it complements so the reader knows the boundary.
2. **Reader's key / glossary** — define every term the report uses, up front. (Skip for a
   non-jargon topic; essential for a technical investigation.)
3. **Executive summary** — plain-language, the whole arc in a few paragraphs.
4. **Sectioned narrative** — background/context → the problem & why it mattered → investigation /
   diagnosis → the solution → verification → results → significance & open items. Each section ends with an
   **Evidence** pointer (the log/figure/number it rests on).
5. **Embedded figures with captions** (see FIGURES below) — placed at the section they illustrate.
6. **Provenance / artifacts** — the source logs, commit hashes, data files, and the figure-regen script,
   so every claim is traceable and the report is reproducible.
7. **Cross-references** — link companion reports/logs; **cross-ref, don't duplicate** their content.

## Recipe

### 1. Gather citation-backed facts FIRST (before writing a word)

A report is only as good as its facts. For a topic spread across many logs, **fan out a subagent** to
extract a fact-sheet with **exact numbers + `file:line`/section** and to **flag contradictions** between
logs (superseded conclusions, unit mismatches, count discrepancies):

```
Agent (Explore): "Read logs L1..Ln. Extract a citation-backed fact sheet under headings
A..H. For every number/mechanism/equation give the exact value + file:line. Flag any
contradiction between logs and name the primary source. Read-only."
```

Then **reconcile the contradictions in the report** — don't silently pick one. (Worked example — the
demo-branch R5 mass-balance report: the pass surfaced a per-patch-vs-per-m² `num_plant` unit mismatch, a
superseded dropout %, and a stale "the fix is Option A" framing — all resolved in the report.)

### 2. Draft to the skeleton, applying the discipline

Lead each section with the plain finding; support with the mechanism; cite the evidence inline. Keep
**pending results as visible placeholders** ("final recovery rate appended when the chains finish"), and
**update the report when they land** — a report is a living document until the work closes.

### 3. Figures — `figures > tables > words`

Make figures for the load-bearing claims (`<auto-memory>/feedback_figures_over_tables_over_words`); build
them with the **`plotting`** skill (readable fonts, no overlap, **verify by viewing the PNG**). Embed each
with a **caption that states its takeaway**, and add a **"how to read this"** for complex figures (multi-
series, dotted reference lines, log axes).

**ONE canonical script per figure — never two copies** (`<auto-memory>/feedback_plot_scripts_canonical_in_phase_results`).
Keeping the same `.py` in two folders is the #1 cause of script-vs-figure drift: edit one copy and the
other silently goes stale (a Phase-6 folder re-carrying a Phase-5 script; a report duplicating a
`phase_results` script). So:
- A figure that **originates in a phase log** — its script is canonical in `phase_results/{stem}/`. **Edit
  it there and regenerate in-place** (the script writes to its own folder via `HERE=Path(__file__).parent`),
  then copy only the **rendered PNG** into the report and **cross-reference** the canonical script in
  Provenance. Do NOT duplicate the `.py` into the report folder.
- A figure the **report generates fresh** (a synthesis figure not tied to one phase) — its script
  (`make_report_figures.py`) is canonical **in the report folder**.
One script, one home; everywhere else references it or copies only the PNG. (A deliberate *graduation* of a
cleared-for-public figure is the one allowed copy — a frozen snapshot, below.)

**Empty the image ALT text when you write a bold caption paragraph.** Embed as `![](figN.png)` (empty
alt) followed by a `**Figure N. <caption>**` paragraph — NOT `![Figure N](figN.png)`. Pandoc's
`implicit_figures` turns the alt text into a `<figcaption>`, so a "Figure N" alt text **plus** your bold
caption renders the label twice ("Figure 1: Figure 1"). Put the caption only in the bold paragraph; leave
the alt text empty. Enforced by `python3 tools/check_report_figures.py <report.md>` (run it before
rendering; it flags any `![Figure ...](...)` alt text).

### 4. Place it + render

```
use_cases/<site>/reports/<YYYYMMDDx>_<topic>/            # timestamp-first, same-day letter REQUIRED
  ├── <topic>_report.md          # the synthesis report  (or NOTES.md for a single graduated figure)
  ├── *.png                      # embedded figures (PNGs copied in; phase figures reference their canonical script)
  └── make_report_figures.py     # canonical ONLY for report-native (fresh) figures
```
`reports/` is the **synthesis layer** — a report here distills the **key results from the logs** for a
reader, cross-referencing (not duplicating) the `memory/*_logs/` and `phase_results/{stem}/` it rests on.

**Naming — timestamp-first `{YYYYMMDDx}_{topic}/`, the same-day letter REQUIRED.** `x` is a sequential
letter (`a`, `b`, `c`, …) for reports written the same day — use the **next free** one (check existing
`reports/{date}*`); the `topic` carries any `R<round>` tag, e.g. `20260709b_R5_massbalance_resolution`.
Past `z` (27th+ same-day), keep `z` and append a second letter: `za, zb, …, zz` — sort-stable
(`z_` < `za`); never `aa` (it sorts before `b`). Same overflow rule as logs (`CLAUDE.md` §Session Logging).
The letter is **mandatory, not optional**: several reports a day is normal (per-cycle summaries plus a
round summary), and without it `ls reports/` cannot show creation order — a bare `{date}_{topic}` sorts
only by topic string, which is not chronological. The `.gitignore` tracks **any letter-containing
`reports/*` folder** and ignores only the pure-numeric `YYYYMMDD_HHMMSS` auto session/presentation dirs +
heavy media — so a curated `{date}x_{topic}/` folder is version-controlled + **public-synced**. Render a
shareable PDF with the **`markdown-to-pdf`** skill.

**Graduating a single figure (not a full report).** `reports/` is also the home for a **graduated durable
figure** — a headline result cleared for public that doesn't need a full narrative. Drop the figure `*.png`
+ its exact producing `*.py` + a `NOTES.md` (what it shows / key finding / why durable / provenance: source
round, case set, the `phase_results/{stem}/` it came from, the calibration log + ana_log) into a
`{YYYYMMDDx}_{topic}/` folder (same-day letter required) — same tracked + public-synced layer, and copying
the producing `.py` here IS allowed (a deliberate frozen public snapshot, the one exception to "one
canonical script"). Graduate **only cleared-for-public**
artifacts (embargoed results stay in gitignored `phase_results/`).

## Footguns

- **No author line** — a report whose header omits `**Author:** Jing Tao with A2MC` reads as orphaned: the
  reader cannot tell who produced it. Every report header carries it (structure step 1). No host suffix,
  and **not** the `with Claude` form every other artifact uses.
- **Undefined shorthand** — an internal codename with no definition is the #1 report failure; a reader
  bounces off it. Define or avoid.
- **A figure-less wall of text** — if a claim is quantitative, it probably wants a figure or table. Don't
  bury the finding in prose.
- **Unverified figures** — a legend on top of the data undercuts the claim; view every PNG (`plotting`).
- **Duplicated figure caption** — `![Figure N](fig.png)` alt text + a `**Figure N.**` caption paragraph
  renders the label twice under pandoc (`implicit_figures`). Use empty alt `![](fig.png)`; run
  `tools/check_report_figures.py`.
- **Silently resolving a cross-log contradiction** — flag it and say which source you trust and why; a
  reader who later finds the other log needs to know it was superseded.
- **Stale placeholders** — a "TBD" left in after the result landed. Update the report when the run closes.
- **Duplicating a companion doc** — cross-reference `summarize-calibration-round` / an ana_log rather than
  restating it; keep each report's boundary clear.

## Cross-references

- Discipline: `<auto-memory>/feedback_report_writing_self_contained`, `feedback_figures_over_tables_over_words`,
  `feedback_logs_cite_explicit_evidence` (name the figure/table/statistic/data file behind every claim — in
  reports as in logs).
- Pieces: `plotting` (figures — the A2MC ensemble figure template), `markdown-to-pdf` (render to PDF/docx),
  `scientific-analysis` (the investigation→figure→ana_log that often feeds a report).
- Adjacent (don't overlap): `summarize-calibration-round` (standardized round summary),
  `manuscript-writing-style` (journal prose).
- Worked example (every step above): the R5 mass-balance resolution report
  (`massbalance_resolution_report.md` + `make_report_figures.py`), on the frozen manuscript
  demo branch's reports layer, not on `main`. Named by artifact, not by branch or path, so this
  public skill stays clean under the leak scan.

## Notes

- **Branch fit:** generic report-writing conventions — applies on any branch and any model configuration.

## Changelog

- 2026-08-05: **Author line now REQUIRED in the header** (structure step 1 + a footgun): every report opens with
  exactly `**Author:** Jing Tao with A2MC`, no host suffix. The `with A2MC` form is report-SPECIFIC — these are
  public-facing A2MC deliverables and credit the framework — while every other artifact keeps the CLAUDE.md
  `Jing Tao with Claude` convention. `feedback_report_author_a2mc` already carried the rule; the skill did not
  enforce it. Also added the same-day letter **overflow past `z`** (`za, zb, …`, sort-stable; never `aa`),
  matching the log convention. Adopted from adapter-kit.
- 2026-07-18: Two conventions ported from adapter-kit `67f798b` (EcoSIM R1 report set). (1) **One canonical
  script per figure** (FIGURES step 3): a phase figure's `.py` is canonical in `phase_results/{stem}/` (edit
  + regen there, copy only the PNG to the report, cross-reference the script); a report-native figure's
  script lives in the report folder; never two copies (memory `feedback_plot_scripts_canonical_in_phase_results`).
  (2) **Report folder same-day letter now REQUIRED** — `{YYYYMMDDx}_{topic}/`, not the previously-optional
  `[x]` — so `ls reports/` shows creation order when several reports land the same day.
- 2026-07-17: Added the **empty-image-alt-text** convention (FIGURES step 3 + a footgun): embed `![](fig.png)`
  + a bold `**Figure N.**` caption, never `![Figure N](...)`, else pandoc `implicit_figures` renders the label
  twice. New linter `tools/check_report_figures.py` enforces it. Ported from adapter-kit `10ca774`.
- 2026-07-16: Added the **no-em-dash rule** to the discipline (user preference): use commas / colons /
  parentheses / sentence splits instead; en dashes in numeric ranges are fine; applies to the rendered PDF too. Ported from adapter-kit `745f06c`.
- 2026-07-16: Incorporated the demo `316092b` reports-layer parts (**minus** the promote-milestone
  retirement — main never had that skill): the **timestamp-first `{YYYYMMDD[x]}_{topic}/` folder convention**,
  the **synthesis-layer framing** (a report distills key results from the logs) + an optional
  **single-figure graduation** step (figure + producing `.py` + provenance `NOTES.md`), and the matching
  `.gitignore` switch (track any letter-containing `reports/*`; ignore only pure-numeric session dirs +
  media). Re-added the `feedback_logs_cite_explicit_evidence` cross-ref (+ ported that memory to main) and
  the full-path R5 worked example.
- 2026-07-09: Ported to `main` from demo `5ef9cc7` (v3.13) — distilled from the R5 mass-balance resolution
  report (demo branch): zero-context structure, subagent fact-gather + contradiction-reconcile pass, and the
  plotting/markdown-to-pdf pieces. The topic-agnostic complement to `summarize-calibration-round`. Added
  main's `modes:` block; dropped the demo-only `feedback_logs_cite_explicit_evidence` cross-ref.
