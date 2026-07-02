---
name: markdown-to-pdf
description: Convert a Markdown document (an ana_log, report, or note) to a shareable PDF or Word (.docx) via pandoc. Use when the user asks to "convert/render markdown to PDF/Word/docx", "render this ana_log/report to PDF", "export markdown to a document", "make a PDF of this", "turn this .md into a docx". Prose documents, not slide decks (slides go through Marp). Requires pandoc + a LaTeX engine for PDF, and python-docx for round-trip-safe .docx edits. Self-contained repo copy — depends only on tools the environment provides, not on any user-level skill or ~/.claude workflow.
---

# Markdown → PDF / DOCX

Convert a Markdown document into a shareable **PDF** or **Word `.docx`**. For A2MC this is the
"render an `ana_log` / report to PDF" step. Prose only — slide decks go through **Marp**
(markdown → PDF/PPTX), not here.

> **Self-contained by design.** This is a repo-vendored copy of a general converter, kept
> inside `.claude/skills/` so it works wherever this repo runs (local, Perlmutter, a fresh
> clone) — it must NOT depend on a user-level skill or on `~/.claude/` assets that won't exist
> elsewhere. It relies only on tools the environment provides (pandoc, a LaTeX engine,
> python-docx).

## Requirements (provided by the environment, locations vary by machine)

| Tool | Role | Find it |
|---|---|---|
| **pandoc** (v3+) | Markdown ↔ PDF / DOCX | `command -v pandoc` (macOS dev: `/opt/homebrew/bin`; Perlmutter: `module load` or conda) |
| **LaTeX engine** (`pdflatex`/`xelatex`) | PDF backend pandoc calls | macOS: BasicTeX at `/Library/TeX/texbin` (`export PATH="/Library/TeX/texbin:$PATH"`); Perlmutter: `module load texlive` |
| **python-docx** | round-trip-safe `.docx` edits | any Python with it installed (`pip install python-docx`) |

## Step 1 — pick the target

| Want | Step |
|---|---|
| PDF of a prose note/report/ana_log | **pandoc → PDF** (Step 2) |
| New `.docx` from markdown | **pandoc → DOCX** (Step 3) |
| Edit an *existing* `.docx` preserving tables / tracked changes / citation fields | **python-docx, not a round-trip** (Step 4) |

## Step 2 — Markdown → PDF

```bash
pandoc note.md -o note.pdf                       # default (pdflatex)
pandoc note.md --pdf-engine=xelatex -o note.pdf  # unicode / special fonts
```

PDF requires a LaTeX engine. pandoc renders LaTeX math natively. Missing TeX package on a
machine you control: `tlmgr install <package>` (BasicTeX) or via the cluster's texlive.

## Step 3 — Markdown → DOCX

```bash
pandoc -f markdown -t docx note.md -o note.docx
pandoc -f markdown -t docx --reference-doc=template.docx note.md -o note.docx  # match house styles
```

`--reference-doc` carries a Word template's styles (headings, fonts, margins) into the output.

## Step 4 — editing an EXISTING `.docx` (round-trip-safe)

A naive `pandoc docx→md→docx` drops tracked changes, comments, and live citation fields and can
mangle tables. Don't do it for a document that has any of those. Instead edit in place with
**python-docx** (paragraph-level, preserves styles/tables):

```bash
python3 -c "from docx import Document; d=Document('in.docx'); ...; d.save('out.docx')"
```

(Manuscript-grade section-merge tooling lives in the manuscript *workspace*, not this repo —
keep this skill's footprint to the generic pandoc + python-docx mechanics.)

## Guardrails

- **PDF needs a LaTeX engine** — if `pandoc -o x.pdf` errors "pdflatex not found", put the
  engine on PATH (`/Library/TeX/texbin` on macOS) or `module load texlive` on a cluster.
- **Back up before overwriting a `.docx`** in a non-git location: copy to
  `<name>_v<n>_YYYYMMDD.docx` first.
- **Don't round-trip a `.docx` through markdown** if it has tracked changes / comments /
  citation fields — use python-docx (Step 4).
- Prose only; **slide decks go through Marp**, not here.

## Changelog

- 2026-06-23: Repo-vendored, self-contained copy of the general `markdown-to-pdf` converter
  (the canonical cross-project version stays at user level). Adapted for this repo: stripped
  the `~/.claude/workflows/` Manuscript_DocxMerge_Workflow + user-level skill references and
  the hardcoded personal env paths, so it works wherever the repo runs (local / Perlmutter /
  fresh clone) — it depends only on environment-provided tools (pandoc, a LaTeX engine,
  python-docx). Referenced by the `scientific-analysis` skill for rendering ana_logs.
