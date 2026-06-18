---
name: add-skill
description: Scaffold and register a new A2MC skill so the steps are never half-done. Use when the user or agent wants to create a new capability — "add a skill", "create/scaffold a skill", "make this reusable as a skill", "distill X into a skill". Writes the SKILL.md with correct frontmatter + a ## Changelog, registers it in BOTH human-facing registries (the README 'Current skills' table AND docs/a2mc_reference/skills_catalog.md), runs the mechanical drift check, and stops for human review before commit. Human-gated.
allowed-tools: [Read, Glob, Grep, Write, Edit, Bash]
modes:
  requires_fates: false
  nutrient_pathway: any
  scope: [meta]
  summary: "Scaffold + register a new skill; meta machinery, model-agnostic."
---

# add-skill — scaffold + register a new A2MC skill

A2MC has **two** human-facing registries that must stay in sync with the skills dir (the
README "Current skills" table and `docs/a2mc_reference/skills_catalog.md`), so the
"create the SKILL.md and update the registries" step is easy to half-do. This skill does
all of it and verifies it mechanically. Conventions live in `.claude/skills/README.md`
("Adding a new skill", "Refining a skill", anti-patterns).

## When to fire

- The user asks to add/create/scaffold a skill, or to distill an existing procedure into one.
- The agent recognizes a **recurring** pattern (across ≥2 `memory/dev_logs/` or
  `memory/ana_logs/`) worth making reusable — propose it; don't self-create silently.

## Procedure

1. **Is it skill-worthy?** Per the README anti-patterns: not a one-off (wait for the pattern
   to repeat), not a paraphrase of `CLAUDE.md`. A skill encodes the easy-to-get-wrong
   conventions, not an essay.
2. **Name + scope.** Pick a kebab-case `<name>` (A2MC skills are **unprefixed** —
   `rebuild-rag`, not `a2mc-rebuild-rag`). The dir name becomes the `/<name>` invocation.
   **Branch-scoped:** skills are per-branch — a skill that only makes sense on a version-pinned
   manuscript branch doesn't belong on `main` (and vice-versa). Note the branch fit in
   the skill's Notes.
3. **Write `.claude/skills/<name>/SKILL.md`:**
   - `name:` matching the dir; `description:` = the trigger the harness matches (what it does
     + when to use + example phrasings — the highest-leverage line).
   - Body: short purpose → decision tree → numbered recipes (ready-to-run bash, use `$PY` for
     Python-3.10 RAG ops) → guardrails/footguns → cross-references.
   - End with a **`## Changelog`** seeded with a dated "Initial version — distilled from
     <source>." line.
   - **Public-sync aware:** skills ship to the public demo via `sync_to_public.sh`. No
     secrets; host-path tokens are advisory-OK on the demo leg (the leak scan), but prefer
     `$PY` / relative paths / `<placeholders>` over hardcoded personal paths.
4. **Register in BOTH registries (the manual step):**
   - add a row to the **"Current skills" table** in `.claude/skills/README.md`
     (`| [<name>](<name>/SKILL.md) | triggers when… |`);
   - add a **`### \`<name>\`` entry** to `docs/a2mc_reference/skills_catalog.md` (Purpose /
     Invoke when / Backing tools / Key discipline — match the existing entries; if it's part
     of a group like the KB-build pipeline, place it there).
5. **Verify mechanically:** run `python3 tools/check_skill_registry.py` — it must exit 0
   (confirms disk ↔ README table ↔ catalog parity, `name:`↔dir, and the `## Changelog`). A
   DRIFT failure means you missed a registry in step 4.
6. **Stop for human review.** Then, after verifying the branch (CLAUDE.md Rule #11), commit
   (`.claude/skills/<name>/` + README + catalog) with a plain no-attribution message, and
   write a brief dev_log (the `log` skill) on why it was extracted and from which logs. Do
   not commit unreviewed; do not public-sync (separate explicit action).

## Guardrails

- **Register in BOTH or it drifts** — never finish without the README-table row AND the
  catalog entry. `tools/check_skill_registry.py` (step 5) is the enforceable backstop; wire
  it into CI / pre-commit so the invariant holds even when this skill isn't used.
- **Minimal procedure** — if it's one obvious step, it may not need to be a skill.
- **Branch-scoped** — don't bake one branch's specifics (a pinned API, a manuscript flow)
  into a skill meant for another. Re-evaluate before copying across branches.
- **Human-gated** — propose + review before commit, consistent with the
  `curate-knowledge` / `inject-knowledge` write-gate stance (a skill is a contract).

## Changelog

- 2026-06-17: Initial version — A2MC counterpart to E2SA's `e2sa-add-skill`
  (`End2EndScienceAgent/docs/design/09_skill_evolution.md`), adapted for A2MC's two-registry
  setup (README table + skills_catalog.md) and the `tools/check_skill_registry.py` drift gate.
