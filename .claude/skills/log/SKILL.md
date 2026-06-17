---
name: log
description: Write an A2MC development or analysis log following this repo's two-stream logging system. Use when the user asks to "write a log", "/log", "log this session", "write a dev log / ana_log", "session log", "handoff log", "document what we did", or to record a fix/feature/analysis. Picks the right stream (dev_logs vs ana_logs) and subtype (regular / session / Handoff_To_Main), applies the naming + header + required-section conventions, and runs the post-write checklist (version bump, changelog, handoff, supersede protocol).
---

# Write an A2MC Log

A2MC keeps **two parallel, tracked log streams** on this branch (plus machine-generated
phase logs you never hand-write). This skill produces a correctly-formed log in the
right stream and runs the follow-up steps that are easy to forget.

> **Step 0 — read the source of truth first.** Read `memory/dev_logs/CLAUDE.md` (the
> authoritative style guide: header order, required sections, formatting, supersede
> protocol). Do NOT scan existing logs to infer style. This skill is the *decision +
> orchestration* layer; that file is the *format* spec. If they ever disagree, the
> guide wins — update this skill.

## Step 1 — classify: which folder, then which subtype

**There are exactly two log folders. Every log goes in one of these two:**

| If the work is… | Folder |
|---|---|
| Engineering — code/infra/feature/fix/refactor/doc change | `memory/dev_logs/` |
| Scientific — results interpretation, mechanism reasoning, manuscript-supporting analysis | `memory/ana_logs/` |

**Subtypes are filename + section conventions WITHIN a folder — NOT separate folders.**
Do not create a `session_logs/` or `handoffs/` directory. Session logs and
Handoff_To_Main logs are just `dev_logs/` files with a particular shape:

| Subtype (lives in `dev_logs/` unless noted) | When | Distinctive sections |
|---|---|---|
| Regular dev log | one fix / feature / refactor | Summary · Problem · Solution · Files Changed · Verification |
| **Session log** | many threads in one session; end-of-session wrap | Summary · What was done · **State at session end** · **Open threads / Handoff to next session** · Files Changed · Cross-references |
| **Handoff_To_Main** | the change is **generic/framework** (`tools/`, `reasoning/`, `memory/`, `orchestrator.py`, generic `phases/`, README/AGENTS/sync) and also applies to `main` | Why this is a handoff · What landed here · Action items for `main` · Verify-on-main commands |

An `ana_logs/` file is freer-form: **Purpose** + scientific reasoning (cite evidence —
Step 4), no `Version` header field. A scientific handoff/summary is still just an
`ana_logs/` file with a handoff shape.

Notes:
- A generic change must **hand off to `main`** — in one of **two forms, by weight**: (a) a **separate `Handoff_To_Main` dev log** for substantial generic changes (e.g. `20260612c`, `20260612e`); or (b) a **`## Cross-branch note` section inside the dev log** for lighter or branch-flavored changes where a whole file is overkill (e.g. `20260612g`, plan doc `21`). Either way, name the generic deltas + what `main` must adapt. (Standing rule; Kougarok/api-31-0/config-only changes are exempt.)
- **Correcting an earlier understanding is itself a trigger to log.** If this work overturns or revises a conclusion in a past log, you are writing a **supersede** — still a NEW dated log (same folder as the log being corrected), never an edit to the old one. Follow the **supersede protocol** below (§"Correcting an earlier understanding").
- If the user just says "/log" with no hint, infer from the session: default to a `dev_logs/` entry for the work just done; if the session spanned several distinct threads, propose a **session log** (still in `dev_logs/`). Ask only if genuinely ambiguous.

## Step 2 — resolve the header facts

- **Filename:** `YYYYMMDDx_Topic_In_Title_Case.md`. Find the next free letter for today:
  `ls memory/dev_logs/YYYYMMDD*` (or `memory/ana_logs/`). Don't reuse a letter.
- **Author line — by environment** (infer from the working directory / where you're running):
  | Where | Author line |
  |---|---|
  | Perlmutter (the HPC clone) | `Jing Tao with Claude on Perlmutter` |
  | Local Mac (the dev-source clone) | `Jing Tao with Claude` |
  | Jing alone, no Claude | `Jing Tao` |
- **Type:** `Enhancement` | `Bug fix` | `Refactoring` | `Research` | `Documentation` (combine with ` / ` as needed).
- **Branch:** the current branch (`git branch --show-current`).
- **Version:** dev logs include `**Version:** v2.XX`; **ana logs omit Version** (not version-tied). Use the current `CLAUDE.md` version, bumped if this change bumps it (Step 4).

Header order (dev log): Title → Date → Author → Type → Version → Branch → `---`.
ana log drops the Version line. Match `memory/dev_logs/CLAUDE.md` exactly.

## Step 3 — draft

Use the required sections for the chosen subtype (Step 1 table); pull the exact
templates from `memory/dev_logs/CLAUDE.md`. **For multi-thread sessions, keep a running
log** and update it as you go rather than reconstructing at the end.

### What to capture (content checklist — the substance, not just the shape)

A well-formed-but-hollow log is a failure. Capture each of these that applies, and put
it in the mapped section:

| Capture | Where it goes | Notes |
|---|---|---|
| **What you did** — the change/work in plain terms | Summary / What was done | one honest paragraph; lead with the outcome |
| **The problem / goal** — what was broken, missing, or the question | Problem / Purpose | why this was worth doing |
| **How you solved it** — approach + key implementation details | Solution | enough that someone could redo it |
| **Scripts/tools you RAN** — existing tools invoked, with the **actual command** | Solution / Verification | paste the command, not a paraphrase (reproducible) |
| **Scripts/functions you WROTE or changed** — path + purpose | Files Changed (table) | new vs modified; one line each |
| **Artifacts GENERATED** — graphs (PNG), data (NC/txt/csv), reports | Solution + cite inline (Step 4) | **name the file + its directory**; figures are usually gitignored so the filename is the only pointer |
| **Results / outcome** — the numbers, verdict, what passed/failed | Verification / Results | quote the statistic; if it failed, say so with the output |
| **Decisions & alternatives** — non-obvious choices and why | Design Decisions (optional section) | what you rejected and the reason |
| **State & what's left** — committed vs not, open threads, follow-ups | State at session end / Open threads (session logs) | so the next session can resume |

Be concrete: **Files Changed** is a markdown table; **Verification** is the actual
commands + their results (say so if something failed or was skipped). Prefer pasting a
real command/figure-path over describing it.

## Step 4 — cite explicit evidence (load-bearing, esp. ana logs)

Every quantitative or scientific claim must name its **figure / table / statistic /
data file inline** (gitignored figures: the filename is the only pointer). When a
section leans on several artifacts, add an **"Artifacts this section is based on"**
table. A claim with no cited source is a red flag — find the source or soften the claim.

## Step 5 — post-write checklist

Run the ones that apply:

1. **Code change → bump version + changelog.** Bump the version in `CLAUDE.md`'s header
   and add an entry at the top of `## Version History` in `memory/a2mc_development_history.md`
   (`- **vX.XX** (YYYY-MM-DD): title` + bullets + `Details:` pointer). Docs-only/no-code
   logs (like this one's MCP-fix example) may skip the bump — say so in the log.
2. **Generic/framework change → hand off to `main`.** Choose the form by weight — a
   separate `Handoff_To_Main` log (substantial changes) **or** a `## Cross-branch note`
   section inside the dev log (lighter / branch-flavored); see the Step 1 notes. Verify
   the target state with `git show main:<path>` / `git ls-tree origin/main …`.
3. **Correcting an earlier understanding → supersede, don't edit.** Follow the full
   protocol in §"Correcting an earlier understanding" below. Never rewrite an old log's
   conclusion in place.
4. **Link related logs** by filename in a Cross-references section.
5. **Do NOT commit** unless the user asks. When you do: verify branch first
   (`git branch --show-current`), and **never** add AI attribution to the commit message.

## Correcting an earlier understanding (supersede protocol)

When new work overturns or revises a conclusion in a past log (dev OR ana), **never
edit the old log's body to change its conclusion in place.** A silently-corrected old
log is invisible to date-ordered search and ends up self-contradicting; a reader who
lands on the old log by date trusts the stale conclusion. (This burned us 2026-06-07:
ground truth had been changed in place inside an older log, so a latest-date search
missed it.) Make the correction **bidirectional and dated** — both entry points must
lead to the truth:

1. **New log = forward pointer (the canonical record going forward).** Write a NEW
   dated log carrying the *full* corrected understanding, in the same folder as the log
   it corrects. **Name the old log(s) it revises.** Add a reciprocal banner right after
   its header:
   ```markdown
   > **Supersedes [IN PART]** [[YYYYMMDDx_Old_Log]] (YYYY-MM-DD): <one-line what changed>.
   ```
2. **Old log = back pointer.** Add a banner immediately **after the old log's header**
   (leave its body untouched as the historical reasoning trail):
   ```markdown
   > ## ⚠️ SUPERSEDED [IN PART] (YYYY-MM-DD)
   > <what is wrong> is corrected by [[YYYYMMDDx_New_Log]]. <one-line corrected conclusion.>
   > <which sections still stand, if partial.>
   > *Original body left intact below as the historical reasoning trail (do not edit in place).*
   ```
3. **Mark "IN PART" vs full.** If only one section/claim is wrong, write "IN PART" and
   name which sections still stand; drop "IN PART" only if the whole log is superseded.
4. **Leave the original analysis untouched** — it's the record of what we believed and why.
5. **Short operational claim in a recent log?** A clearly-marked inline blockquote right
   after the wrong line is enough (still don't delete the original line):
   ```markdown
   > **CORRECTION (YYYY-MM-DD):** … see [[YYYYMMDDx_New_Log]].
   ```

Canonical spec + worked example (`20260514a` banner ↔ `20260608a` new analysis):
`memory/dev_logs/CLAUDE.md` §"Correcting or Superseding an Earlier Log". Applies to
`ana_logs/` too.

## Quick reference — `/log` argument forms

| Invocation | Action |
|---|---|
| `/log` | infer from session: dev log for the work just done, or propose a session log if multi-thread |
| `/log <topic>` | regular dev log on `<topic>` |
| `/log session` | session log wrapping the whole session + open threads |
| `/log ana <topic>` | analysis log in `memory/ana_logs/` (cite evidence) |
| `/log handoff <topic>` | `Handoff_To_Main` for a generic change |
| `/log supersede <old-log> <topic>` | new corrected-understanding log + bidirectional supersede banners (§"Correcting an earlier understanding") |

## What this skill does NOT cover

- **Phase execution logs** under `use_cases/{site}/memory/logs/{session_id}/` are
  machine-generated by the orchestrator — never hand-write these.
- **Auto-memory** (`MEMORY.md` + `feedback_*`/`project_*` files) is a separate system
  from these episodic logs; don't conflate them.
- On a **feature branch**, logs go to `memory/dev_logs_<branchname>/`, not `dev_logs/`.
