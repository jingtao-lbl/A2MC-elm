---
name: onboard-session
visibility: public
category: meta
description: Cold-start runbook — orient at the start of a session or after a context reset/compaction. Use when a session begins, resumes, or is compacted (especially if the SessionStart snapshot shows in-flight work or pending proposals), or when the user says "catch up", "where did we leave off", "onboard", "what's the current state". Reads the latest handoff, re-reads CLAUDE.md, checks live HPC processes + run state, and hands off to arm-hpc-monitoring / curate-knowledge as needed.
modes:
  requires_fates: false
  nutrient_pathway: any
  scope: [session]
  summary: "Cold-start session runbook; model-agnostic."
---

# Onboard a Session (cold-start runbook)

The interactive agent often starts cold — a fresh session, a resume, or after
compaction. This skill is the checklist that restores full context and catches in-flight
work before you act. It **pairs with the G2 `SessionStart` hook**
(`.claude/hooks/session-start.py`), which already surfaces a snapshot (branch,
uncommitted count, latest handoff, pending-knowledge count, live processes). The hook
gives the *data*; this skill is what you *do* with it.

> Run this whenever the snapshot shows in-flight work, after a compaction, or when the
> user asks you to catch up. Skip the HPC steps if no ensemble is active.

## Step 1 — restore context

1. **Re-read `CLAUDE.md`** (root). Required after compaction (memory:
   `re-read CLAUDE.md after compaction`) — it carries the branch banner (this branch is
   intentionally pinned to api-31-0, disconnected from `main`) and the operating rules.
   Don't reconstruct the knowledge system from `AGENTS.md`'s one-liner — `CLAUDE.md`
   §"RAG/GraphRAG System" (+ `docs/a2mc_reference/rag_reference.md`) carries the full
   hybrid vector + two-layer knowledge graph + curated YAML detail.
2. **Read the latest calibration log/report — the primary source for the application-agent (calibration)
   role, and the one that exists in ANY clone, public or private.** The SessionStart snapshot's
   `Recent calibration logs + reports` block already lists the most recently CHANGED of both across every
   case, so start from there; otherwise, newest-touched first:
   `ls -t use_cases/*/memory/logs/*.md use_cases/*/reports/*/*.md 2>/dev/null | grep -v README | head`
   — narrow to the active site. Sorting by mtime rather than by the filename date is deliberate: a file
   revised today still surfaces even when its stem is older. A round or cycle **report** is usually the
   fastest single read for where the campaign stands; the **phase logs** and their `phase_results/` stems
   carry the finer-grained trail. The `Offline state:` / `► NEXT:` line (Step 4 below) gives you a
   *pointer*; this step is where you actually read what it points into. Read for open threads + the
   `## Next` section **before** treating a `next_action` pointer as something you already understand — a
   pointer is not a substitute for having read what it points at.
3. **If this clone also carries framework-development history** — i.e. `memory/dev_logs*/` exists (true on
   the private A2MC-dev repo; absent on a fresh public clone, since it's excluded from the public sync) —
   also read the latest handoff/session log there:
   `ls -t memory/dev_logs*/*Handoff* memory/dev_logs*/*Session_Log* 2>/dev/null | head`. **Glob
   `dev_logs*`, not `dev_logs`** — every feature branch keeps its own stream (`memory/dev_logs_<branch>/`)
   and writes only there, so the bare directory reports `main`'s newest file and silently misses the
   branch's own; the snapshot names the stream alongside the filename for the same reason. Skim the 2–3
   most recent dated dev_logs (and `memory/ana_logs/` if present) for anything still mid-flight. This step
   covers the **developing-agent** role (framework code, RAG, skills) — skip it entirely if the directory
   doesn't exist; don't treat its absence as an error.
4. **Verify branch:** `git branch --show-current` → confirm it matches your intended working branch (`main` or your feature branch).
   `git status -s` for uncommitted work the previous session left.
5. **Read the master state, then the round detail** — two files, and knowing which answers what
   saves you from acting on a stale one.

   **`tools/agent_state.py` — the clone-level master.** `python3 tools/agent_state.py` prints the
   setup stage, EVERY case with its current phase/round/cycle, and each case's approved-plan task
   list with what is done and what is next. The position half is **DERIVED on read** from the newest
   log stem, so it cannot be stale; the task/decision/thread half is stored. This is the line to
   trust for *where the work is*. Validate the stored half with `--check` (it rejects any attempt to
   store a derived field). If a case shows plan tasks, **the next `todo` is your default next action.**

   **`workflow_state_offline_r{RR}.json` — the per-round detail.** Still the place for open threads
   with their `next_action`, the `phase6_decision` binding target, and the per-round evidence
   pointers. If a round is mid-refinement, note the **binding target + next targeted experiment** —
   that is the objective to drive toward (`feedback_performance_experiment_is_the_objective`), not the
   loudest crash thread. **Validate it:** the SessionStart hook flags a corrupt state
   (`⚠ Offline state INVALID …`); if it does, run `python3 tools/check_workflow_state_offline.py` and fix
   the invariants before driving.

   > **Weigh the round detail by its age.** The snapshot prints `recorded <date>` beside it because
   > its stored position fields drift — measured 2026-08-21 at ten days and five phases behind the
   > logs, with a `next_action` naming jobs long finished. If `recorded` lags the master's `as of`
   > date, treat its `next_action` as a *lead to verify*, not an instruction to execute.
6. **Recall the operating discipline.** Skim `AGENTS.md` §"Offline-Agent Operating Discipline" — the four
   recurring failure modes (verify before claiming · track the objective · drive, don't wait · trust the
   skill) and the gate enforcing each. Lead memory: `feedback_offline_agent_operating_discipline`.

## Step 2 — check for in-flight HPC work

```bash
ps -ef | grep "$USER" | grep -E 'monitor|submit|extract' | grep -v grep
```
- **If an auto-monitor / submitter / extractor is running** → an ensemble is in flight.
  Invoke the **`arm-hpc-monitoring`** skill (CLAUDE.md Rule 6) to arm `Monitor` on the
  live logs with the event + error filters. Read the active handoff log for the
  round-scoped event names/filenames.
- **Check run state** if a round is active: `squeue -u "$USER"` (or the round's job
  prefix) and, for completion, `tools/diagnose_ensemble_status.py`. Re-derive counts from
  live `squeue` + disk NC counts + the most recent dated log (memory:
  `verify run-state before quoting`) — don't trust stale numbers in an old log.

## Step 3 — check pending knowledge

If the snapshot reports pending proposals (or
`use_cases/*/memory/gained_knowledge/auto_discovered_pending.json` has open items),
invoke the **`curate-knowledge`** skill to review + promote/discard them. Online runs
stage proposals here; they only enter the curated KB when a human-in-the-loop session
curates them.

## Step 4 — drive the next action, don't wait (docs/35)

Close the onboarding by **advancing the workflow**, not with a bare readout. When the offline resume
brain (`workflow_state_offline`) holds an active goal + a `next_action` (the SessionStart `► NEXT:`
line), **execute it** — you are the superset of the autonomous orchestrator, which drives itself with no
per-phase prompt ([[feedback_offline_agent_drives_the_workflow]]). Lead with: *"Round R{N}, phase X;
next action = `<...>`. Proceeding with it — will pause only at a fork or hard stop."* Then do it.

> **To drive the *whole* calibration to the goal (not just this one action), hand off to `calibration-goal`** — the run-to-convergence driver that loops this drive-the-next-action over the full 7-phase workflow (via `resolve_next_action`) until Phase-7 CONVERGED or a loop limit, pausing only at the gates. `onboard-session` orients + resumes; `calibration-goal` drives.

**DRIVE (just do it — surface results, not permission requests):**
- arm/re-arm monitors; extract completed data; run a **planned** experiment; skip-test on existing data;
  advance to the next phase per the 7-phase workflow + iteration rules; regenerate a plot; commit routine work.

**PAUSE for the human (a genuine fork or hard stop):**
- a **Phase-6** converge / redesign / **stop→model-dev** decision (the `docs/34` objective gate — a hard pause);
- a **curated-KB write** (`inject-knowledge` / `curate-knowledge` promote — Tier-3, human-gated);
- an **expensive / irreversible** action (a full-ensemble redesign, a large HPC spend, anything hard to undo);
- the standing hard stops: destructive / outside-repo actions, a claim about the user, an ambiguous instruction.

Everything not in the PAUSE list, you drive. Surface **proposals + results**, not "shall I…?" for mechanical steps.

## What this skill does NOT do
- It does not replace the **G2 SessionStart hook** (that runs automatically and surfaces
  the snapshot); this skill acts on it.
- It does not arm monitors itself — it delegates to `arm-hpc-monitoring`.
- For the full monitoring reactions, invoke the `arm-hpc-monitoring` skill
  (required when an ensemble is in flight, per CLAUDE.md Rule 6).

## Changelog

- 2026-08-09: Step 1 point 2 redirected from `memory/dev_logs/` (framework-dev-only, excluded from the
  public sync) to `use_cases/{site}/reports/`, `use_cases/{site}/memory/logs/`, and
  `use_cases/{site}/memory/phase_results/` — the application-agent's actual calibration record, present
  in any clone. The dev_logs read moved to a new
  point 3, gated on `memory/dev_logs/` existing (private repo only), so the skill degrades cleanly on a
  public clone instead of pointing at a directory that was never shipped. Signal: PI observed I had a
  `next_action` pointer from the resume-state JSON but had not actually read the reports/logs it pointed
  into — the skill told me to read dev_logs, not the calibration record. `SKILL.md` bodies ship unfiltered
  (no `<!-- private -->` mechanism exists for them, unlike CLAUDE.md/AGENTS.md/README), so this is a
  mode-aware single skill rather than a private/public content split.
- 2026-07-15: Step 1 point 4 now validates the offline state (`tools/check_workflow_state_offline.py`); the SessionStart hook flags a corrupt state loudly. Ported from demo `d3cbbf5` (offline-workflow enforcement sweep).
- 2026-07-06: Point Step 1 at `AGENTS.md` §"Offline-Agent Operating Discipline" — the consolidated
  4-failure-mode stance (docs/36, reinforcement #4); lead memory `feedback_offline_agent_operating_discipline`.
- 2026-07-06: Cold-start **driving** reinforcement (docs/35, FM-3): Step 1 reads the offline resume brain
  (`workflow_state_offline` + `phase6_decision`); Step 4 reframed from "summarize + propose" to "**drive the
  next action, don't wait**" with an explicit DRIVE-vs-PAUSE list. Pairs with the SessionStart `► NEXT:` line
  + AGENTS.md core rule 10. See `feedback_offline_agent_drives_the_workflow`.
- 2026-06-17: `## Changelog` convention adopted (see .claude/skills/README.md). Earlier history: git log + memory/dev_logs/.
