---
name: refine-skill
visibility: public
category: meta
description: Improve an existing A2MC skill from accumulated evidence, human-gated. Use when a skill missed a step or needs updating, when dev_logs/ana_logs/verify-pass findings in a skill's domain have piled up, or during a periodic skill review — "refine the X skill", "improve this skill", "the X skill should have caught Y", "review the skills". Gathers the signal (dev_logs, ana_logs, verify findings, explicit corrections), proposes a concrete SKILL.md diff with cited evidence, and STOPS for human approval; it never self-applies. After approval it edits, appends a ## Changelog line, runs the drift check if registries/name changed, and commits.
allowed-tools: [Read, Glob, Grep, Write, Edit, Bash]
modes:
  requires_fates: false
  nutrient_pathway: any
  scope: [meta]
  summary: "Refine an existing skill from evidence (human-gated); meta machinery, model-agnostic."
---

# refine-skill — the distill → propose → gate → apply half

Skills should get better as they're used without silently rewriting themselves and
drifting. A `SKILL.md` is the **contract** the agent obeys, so evolution is fast but
**human-gated and versioned**. The discipline is in `.claude/skills/README.md`
("Refining a skill — refine on signal, not noise"). **This skill proposes; it never
rewrites a skill on its own.**

## When to fire

- **Reactive:** a `verify`-pass finding, a dev_log/ana_log trap, an explicit user
  correction, or a repeated failure in a skill's domain suggests its `SKILL.md` is missing
  or mis-stating a step.
- **Periodic:** a "review the skills" pass.
- A human directly asks to refine/improve a skill.

## Procedure

1. **Pick the target skill** and read its current `.claude/skills/<name>/SKILL.md`.
2. **Gather the signal** (don't act on noise):
   - `grep memory/dev_logs/ memory/ana_logs/` for the skill's domain / name and for
     verify-pass findings or corrections touching its recipes.
   - Explicit user corrections in-session or in feedback memories.
   - **Threshold:** refine on a *repeated* trap (same issue ≥ ~2–3 times), an explicit human
     correction, or a clear failure pattern. A single one-off is usually not enough to change
     the contract. (Worked example of a legitimate refinement: the `/verify` pass that found
     `inject-knowledge`'s `phase=` kwarg bug and `rebuild-rag`'s stale doc-count — concrete,
     reproduced, evidence-backed.)
3. **Propose a concrete diff**, not a vague suggestion: the exact new/edited step, gotcha, or
   trigger wording, with the dev_log/ana_log/finding that justifies it cited inline.
4. **STOP at the human gate.** Present the proposed diff + evidence; wait for approval. Skill
   edits are contract changes — human-reviewed, like `curate-knowledge` / `inject-knowledge`.
5. **On approval:** apply the edit, **then re-read the ENTIRE `SKILL.md` end-to-end — not just
   your diff — to catch inconsistencies the edit introduced.** A surgical change to one step
   routinely contradicts another part of the same file: a now-stale flag or example elsewhere, a
   definition/default the edit changed, terminology drift, or an anti-pattern that no longer
   matches the revised recipe. Reconcile every conflict in the SAME pass (this is cheap now,
   expensive once the contradiction misleads a future run). Then append a dated `## Changelog`
   line stating what changed and which signal drove it; if the edit touched the `name:`, the
   README table, or the catalog, **re-run `python3 tools/check_skill_registry.py`** (must exit 0; Tier-1
   static). If the edit changed a **backing command** the skill documents, also run the **Tier-2 runtime**
   check `python3 tools/smoke_test_skills.py` — it actually executes the read-only backing commands and
   asserts exit 0, catching a broken/renamed command a static path-check can't. Then verify the branch
   (Rule #11); commit with a plain no-attribution message; write a dev_log if substantive. Do not
   public-sync (separate explicit action).

   > **Why (2026-07-09):** rapid `offline-testing-workflow` edits (per-phase builds, a debug-only
   > literal template, a new anti-pattern) left **anti-pattern #6 contradicting the revised Step 5**,
   > a **stale `--output-root`** in a code block, and a **colliding "literal template" term** — none
   > flagged by `check_skill_registry.py` (they're prose/logic, not dead paths), all caught only by a
   > full read-through. Multi-edit sessions are the highest-risk: the more steps you touch, the more
   > likely two of them now disagree.

## Guardrails

- **Never self-apply.** Propose + gate, always.
- **Surgical edits only** — add or fix a step; don't bloat or rewrite wholesale. A skill that
  keeps growing is a smell — consider splitting or pruning instead.
- **`description` (trigger) edits are the highest risk** — they change *when* the skill fires,
  so a careless edit silently mis-fires or hides the skill. Flag any trigger change
  prominently for the human and in the Changelog.
- **Evidence-cited** — every proposed change names the dev_log / ana_log / finding /
  correction that justifies it. No speculative edits.
- **Branch-scoped** — keep each branch's skills aligned to that branch's reality (a pinned
  API + manuscript flow vs generic `main`); don't import the other branch's assumptions.

## Notes

- A2MC has no scheduled skill-review routine (that would be a recurring billed agent — the
  PI's cadence call), and no run-journal of per-skill outcomes; the reactive path (grep the
  logs + verify findings) is the working signal source today.

## Changelog

- 2026-07-15: Step 5 names `tools/smoke_test_skills.py` as the **Tier-2 runtime** check when an edit changes a skill's backing command (complements Tier-1 `check_skill_registry.py`). Ported from demo `84af889`.
- 2026-07-09: **Step 5 now requires a full end-to-end `SKILL.md` re-read after applying an edit**
  (not just the diff) to catch inconsistencies the edit introduced — a stale flag/example, a
  changed default, terminology drift, or an anti-pattern that no longer matches the recipe;
  `check_skill_registry.py` can't see these (prose/logic, not dead paths), and multi-edit sessions
  are the highest-risk. Ported from demo `a2147ff` (v3.13), scrubbed of the Kougarok worked-example
  filenames.
- 2026-06-17: Initial version — A2MC counterpart to E2SA's `e2sa-refine-skill`
  (`End2EndScienceAgent/docs/design/09_skill_evolution.md`), adapted to A2MC's
  dev_logs/ana_logs signal sources and the `tools/check_skill_registry.py` gate.
