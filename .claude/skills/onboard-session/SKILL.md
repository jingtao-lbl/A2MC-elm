---
name: onboard-session
description: Cold-start runbook — orient at the start of a session or after a context reset/compaction. Use when a session begins, resumes, or is compacted (especially if the SessionStart snapshot shows in-flight work or pending proposals), or when the user says "catch up", "where did we leave off", "onboard", "what's the current state". Reads the latest handoff, re-reads CLAUDE.md, checks live HPC processes + run state, and hands off to arm-hpc-monitoring / curate-knowledge as needed.
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
2. **Read the latest handoff / session log** — the SessionStart snapshot names it; else
   `ls -t memory/dev_logs/*Handoff* memory/dev_logs/*Session_Log* | head`. Read it for
   open threads + "state at session end". Skim the 2–3 most recent dated dev_logs for
   anything still mid-flight.
3. **Verify branch:** `git branch --show-current` → expect `kougarok_fates_demo`.
   `git status -s` for uncommitted work the previous session left.

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

## Step 4 — summarize + propose, don't just relay

Close the onboarding with a short state summary and **proposed next actions**, not a bare
readout (memory: `react to events with proposals, not just relay`): e.g. "round R{N} has
M/4890 done, K failed → propose restart of the infra failures via `restart-failed-jobs`";
"3 pending proposals → curate"; "previous session left X uncommitted → commit or discard".

## What this skill does NOT do
- It does not replace the **G2 SessionStart hook** (that runs automatically and surfaces
  the snapshot); this skill acts on it.
- It does not arm monitors itself — it delegates to `arm-hpc-monitoring`.
- For the full monitoring reactions table, read
  `memory/dev_logs/20260514c_Monitoring_Workflow_Pattern_For_HPC_Ensembles.md`
  (required reading when an ensemble is in flight, per CLAUDE.md Rule 6).

## Changelog

- 2026-06-17: `## Changelog` convention adopted (see .claude/skills/README.md). Earlier history: git log + memory/dev_logs/.
