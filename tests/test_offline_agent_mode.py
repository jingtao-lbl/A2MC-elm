"""
test_offline_agent_mode.py — Phase-1 offline interactive agent mode (docs/25).

Covers the mode-aware substrate the ported agent components rely on:
  - describe_mode / config.MODE resolves and renders for representative modes
    (ELM-FATES + ECA, and ELM-only) and reflects nutrient_comp_pathway
  - every shipped SKILL.md has a valid `modes:` frontmatter block
  - the public agent surface (AGENTS.md + .claude/skills/) is leak-clean
    (no private host paths / usernames) — the same gate sync_to_public.sh enforces

Run:
    python -m unittest tests.test_offline_agent_mode -v
"""

from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

SKILLS_DIR = _REPO_ROOT / ".claude" / "skills"
LEAK_TOKENS = re.compile(r"/global/|/pscratch/|/Users/|/cfs/cdirs|jingtao|m2467|kougarok_fates_demo")


class TestDescribeMode(unittest.TestCase):
    """config.MODE resolves and the summary reflects the active configuration."""

    def _mode(self, elm_options: str):
        os.environ["A2MC_ELM_OPTIONS"] = elm_options
        # config.MODE is a property -> ConfigMode.from_env(); re-reads env each access.
        from tools.config import config
        return config.MODE

    def test_fates_eca(self):
        m = self._mode("-bgc fates -nutrient cnp -nutrient_comp_pathway eca")
        self.assertTrue(m.use_fates)
        self.assertEqual(m.nutrient_comp_pathway, "eca")
        block = m.to_prompt_block()
        self.assertIn("FATES", block)
        self.assertIn("ECA", block.upper())

    def test_elm_only(self):
        m = self._mode("-bgc sp")
        self.assertFalse(m.use_fates)
        block = m.to_prompt_block()
        self.assertIn("FATES DISABLED", block)

    def tearDown(self):
        os.environ.pop("A2MC_ELM_OPTIONS", None)


class TestSkillFrontmatter(unittest.TestCase):
    """Every shipped SKILL.md carries a valid modes: frontmatter block."""

    def _skills(self):
        return sorted(SKILLS_DIR.glob("*/SKILL.md"))

    def test_skills_present(self):
        # Subset check (not exact) so adding skills doesn't break the test; the
        # registry parity is enforced separately by tools/check_skill_registry.py.
        names = {p.parent.name for p in self._skills()}
        expected = {
            "log", "onboard-session", "curate-knowledge", "arm-hpc-monitoring",
            "restart-failed-jobs", "diagnose-forensics", "scientific-analysis",
            "build-rag-from-scratch", "rebuild-rag", "generate-codebase-wiki",
            "validate-rag-chain", "inject-knowledge", "add-skill", "refine-skill",
        }
        missing = expected - names
        self.assertEqual(missing, set(), f"expected skills missing: {missing}")

    def test_modes_frontmatter_valid(self):
        for skill in self._skills():
            text = skill.read_text()
            self.assertTrue(text.startswith("---"), f"{skill} missing frontmatter")
            fm = text.split("---", 2)[1]
            meta = yaml.safe_load(fm)
            self.assertIn("name", meta, f"{skill} missing name")
            self.assertIn("description", meta, f"{skill} missing description")
            self.assertIn("modes", meta, f"{skill} missing modes block")
            modes = meta["modes"]
            self.assertIn("requires_fates", modes, f"{skill} modes missing requires_fates")
            self.assertIsInstance(modes["requires_fates"], bool, f"{skill} requires_fates not bool")
            self.assertIn("nutrient_pathway", modes, f"{skill} modes missing nutrient_pathway")
            self.assertIn(modes["nutrient_pathway"], ("any", "eca", "rd"),
                          f"{skill} bad nutrient_pathway {modes['nutrient_pathway']!r}")

    def test_requires_fates_matches_skill_category(self):
        # The FATES Morris-ensemble analysis skills are requires_fates:true; everything
        # else is mode-agnostic (requires_fates:false).
        fates_only = {"summarize-calibration-round", "compare-calibration-rounds",
                      "offline-testing-workflow"}
        for skill in self._skills():
            meta = yaml.safe_load(skill.read_text().split("---", 2)[1])
            rf = meta["modes"]["requires_fates"]
            expected = skill.parent.name in fates_only
            self.assertEqual(rf, expected,
                             f"{skill.parent.name}: requires_fates={rf}, expected {expected}")


class TestAgentSurfaceLeakClean(unittest.TestCase):
    """AGENTS.md + .claude/skills/ contain no private host paths / usernames."""

    def test_no_leak_tokens(self):
        surface = [_REPO_ROOT / "AGENTS.md"] + list(SKILLS_DIR.rglob("*.md"))
        offenders = []
        for f in surface:
            for i, line in enumerate(f.read_text().splitlines(), 1):
                if LEAK_TOKENS.search(line):
                    offenders.append(f"{f.relative_to(_REPO_ROOT)}:{i}: {line.strip()}")
        self.assertEqual(offenders, [], "leak tokens in agent surface:\n" + "\n".join(offenders))


class TestAgentSurfaceValidator(unittest.TestCase):
    """tools/validate_agent_surface.py passes on the real surface and fires on pitfalls."""

    def test_real_surface_clean(self):
        from tools.validate_agent_surface import validate_agent_surface
        errors = [f for f in validate_agent_surface(_REPO_ROOT) if f.level == "ERROR"]
        self.assertEqual(errors, [], f"agent surface should validate clean; got {errors}")

    def test_pitfalls_fire(self):
        import tempfile
        from tools.validate_agent_surface import validate_agent_surface
        d = Path(tempfile.mkdtemp())
        (d / ".claude/skills/goodskill").mkdir(parents=True)
        (d / "docs/a2mc_reference").mkdir(parents=True)
        (d / "AGENTS.md").write_text(
            "# A\nsee [cat](docs/a2mc_reference/skills_catalog.md)\n"
            "leak ~/x\n[dead](nope/missing.md)\n"
        )
        (d / ".claude/skills/goodskill/SKILL.md").write_text(
            "---\nname: wrongname\ndescription: d\n"
            "modes:\n  requires_fates: notabool\n  nutrient_pathway: banana\n---\n# body\n"
        )
        (d / "docs/a2mc_reference/skills_catalog.md").write_text("# cat\n[phantom](phantom/SKILL.md)\n")
        codes = {(f.level, f.code) for f in validate_agent_surface(d)}
        for need in [("ERROR", "L1"), ("ERROR", "F4"), ("ERROR", "F5"), ("ERROR", "D1")]:
            self.assertIn(need, codes, f"validator failed to fire {need}")
        # Registry/catalog parity (C1/C2) moved to check_skill_registry.py (D1 de-dup, v2.107):
        # validate_agent_surface no longer fires them; check_skill_registry owns that (see
        # TestRegistryAndPhaseDocGates below).
        self.assertNotIn(("ERROR", "C2"), codes)
        self.assertNotIn(("WARN", "C1"), codes)


class TestRegistryAndPhaseDocGates(unittest.TestCase):
    """The ported integrity checkers (v2.107) stay green on the real repo, and the
    registry is genuinely 4-way (disk ↔ README ↔ catalog ↔ AGENTS.md)."""

    def _run(self, script):
        import subprocess
        return subprocess.run([sys.executable, str(_REPO_ROOT / script)],
                              cwd=str(_REPO_ROOT), capture_output=True, text=True)

    def test_skill_registry_clean(self):
        r = self._run("tools/check_skill_registry.py")
        self.assertEqual(r.returncode, 0, f"registry drift:\n{r.stdout}\n{r.stderr}")

    def test_phase_script_docs_clean(self):
        r = self._run("tools/check_phase_script_docs.py")
        self.assertEqual(r.returncode, 0, f"phase script-doc drift:\n{r.stdout}\n{r.stderr}")

    def test_registry_is_four_way(self):
        # AGENTS.md 'At a glance' table is a real 4th registry: 1:1 with skills on disk.
        import importlib
        csr = importlib.import_module("tools.check_skill_registry")
        disk = set(csr.skills_on_disk())
        self.assertEqual(csr.agents_table_names(), disk,
                         "AGENTS.md 'At a glance' table is not 1:1 with skills on disk")
        self.assertEqual(csr.readme_table_names(), disk)
        self.assertEqual(csr.catalog_names(), disk)

    def test_contract_and_marker_clean(self):
        # The new contract_check (cited paths/skills exist) + marker_check (balanced
        # <!-- private --> blocks) pass on the real surface.
        import importlib
        csr = importlib.import_module("tools.check_skill_registry")
        self.assertEqual(csr.contract_check(csr.skills_on_disk()), [],
                         "a shipped skill cites a path/skill that does not exist")
        self.assertEqual(csr.marker_check(), [], "unbalanced/inline <!-- private --> markers")

    def test_cited_paths_survives_code_fence(self):
        # Regression (20260702f): a ``` code fence must NOT desync backtick pairing and
        # hide a real path citation that follows it. cited_paths pairs line-by-line.
        import importlib
        csr = importlib.import_module("tools.check_skill_registry")
        fence = "`" * 3
        text = (
            "Intro cites `tools/real_a.py`.\n"
            f"{fence}\n"
            "code with `inline` and `spans` inside a fence\n"
            f"{fence}\n"
            "After the fence, `tools/real_b.py` must still be detected.\n"
        )
        paths = csr.cited_paths(text)
        self.assertIn("tools/real_a.py", paths)
        self.assertIn("tools/real_b.py", paths,
                      "path cited after a code fence was dropped (fence-desync bug)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
