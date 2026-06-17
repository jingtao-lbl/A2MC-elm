---
name: refine-skill
description: Improve an existing A2MC skill from accumulated evidence, human-gated. Use when a skill missed a step or needs updating, when dev_logs/ana_logs/verify-pass findings in a skill's domain have piled up, or during a periodic skill review — "refine the X skill", "improve this skill", "the X skill should have caught Y", "review the skills". Gathers the signal (dev_logs, ana_logs, verify findings, explicit corrections), proposes a concrete SKILL.md diff with cited evidence, and STOPS for human approval; it never self-applies. After approval it edits, appends a ## Changelog line, runs the drift check if registries/name changed, and commits.
allowed-tools: [Read, Glob, Grep, Write, Edit, Bash]
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
5. **On approval:** apply the edit; append a dated `## Changelog` line stating what changed
   and which signal drove it; if the edit touched the `name:`, the README table, or the
   catalog, **re-run `python3 tools/check_skill_registry.py`** (must exit 0); verify the
   branch (Rule #11); commit with a plain no-attribution message; write a dev_log if
   substantive. Do not public-sync (separate explicit action).

## Guardrails

- **Never self-apply.** Propose + gate, always.
- **Surgical edits only** — add or fix a step; don't bloat or rewrite wholesale. A skill that
  keeps growing is a smell — consider splitting or pruning instead.
- **`description` (trigger) edits are the highest risk** — they change *when* the skill fires,
  so a careless edit silently mis-fires or hides the skill. Flag any trigger change
  prominently for the human and in the Changelog.
- **Evidence-cited** — every proposed change names the dev_log / ana_log / finding /
  correction that justifies it. No speculative edits.
- **Branch-scoped** — keep `kougarok_fates_demo` skills aligned to api-31-0 / the manuscript
  flow; don't import `main`/adapter-kit assumptions.

## Notes

- A2MC has no scheduled skill-review routine (that would be a recurring billed agent — the
  PI's cadence call), and no run-journal of per-skill outcomes; the reactive path (grep the
  logs + verify findings) is the working signal source today.

## Changelog

- 2026-06-17: Initial version — A2MC counterpart to E2SA's `e2sa-refine-skill`
  (`End2EndScienceAgent/docs/design/09_skill_evolution.md`), adapted to A2MC's
  dev_logs/ana_logs signal sources and the `tools/check_skill_registry.py` gate.
