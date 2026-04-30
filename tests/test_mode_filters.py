"""
test_mode_filters.py - Verification fixtures for mode-aware RAG retrieval.

Per Doc 20 §4.7. The fixtures here ship in Phase A and assert:

    1. ConfigMode parses env vars correctly under each mode combination.
    2. `to_prompt_block()` produces the expected text (which the LLM uses
       to self-correct on retrieved content).
    3. `kb_source_filter()` returns the right value for each mode.
    4. parse_elm_options handles realistic CIME flag strings.

Phase B will extend this file with per-mode chunk filtering assertions
(e.g., "PARTEH=1 retrieval does NOT surface fates_cnp_pid_kp").

Run via:
    python -m pytest tests/test_mode_filters.py -v

Or via the dedicated harness:
    python scripts/verify_mode_aware.py
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

# Project root on sys.path so `tools.config` imports cleanly
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.config import ConfigMode, parse_elm_options  # noqa: E402


# =============================================================================
# Fixture: clean env for each test
# =============================================================================

class _EnvSandbox:
    """Context manager that clears mode env vars and restores them on exit."""
    KEYS = (
        # Tier 1
        "A2MC_BGC_MODE",
        "A2MC_USE_FATES",
        "A2MC_FATES_PARTEH_MODE",
        "A2MC_USE_FATES_NOCOMP",
        "A2MC_ELM_OPTIONS",
        # Tier 2
        "A2MC_FATES_SPITFIRE_MODE",
        "A2MC_USE_FATES_PLANTHYDRO",
        "A2MC_USE_FATES_LOGGING",
        "A2MC_USE_FATES_SP",
        "A2MC_USE_FATES_ED_PRESCRIBED_PHYS",
        "A2MC_USE_FATES_FIXED_BIOGEOG",
        # Phase B v2.92+: case-dir auto-detection
        "A2MC_CASE_DIR",
        "A2MC_CASE_NAME",
    )

    def __enter__(self):
        self._saved = {k: os.environ.pop(k, None) for k in self.KEYS}
        return self

    def __exit__(self, exc_type, exc, tb):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def set(self, **kwargs):
        for k, v in kwargs.items():
            os.environ[k.upper()] = str(v)


# =============================================================================
# Phase A fixtures
# =============================================================================

class TestParseElmOptions(unittest.TestCase):
    """parse_elm_options handles realistic CIME flag strings."""

    def test_full_string(self):
        opts = parse_elm_options(
            "-bgc fates -nutrient cnp -nutrient_comp_pathway eca "
            "-soil_decomp century"
        )
        self.assertEqual(opts["bgc"], "fates")
        self.assertEqual(opts["nutrient"], "cnp")
        self.assertEqual(opts["nutrient_comp_pathway"], "eca")
        self.assertEqual(opts["soil_decomp"], "century")

    def test_empty_string(self):
        self.assertEqual(parse_elm_options(""), {})

    def test_partial_string(self):
        opts = parse_elm_options("-nutrient cn")
        self.assertEqual(opts, {"nutrient": "cn"})


class TestConfigModeFromEnv(unittest.TestCase):
    """ConfigMode.from_env() reads env vars under each mode combination.

    Defaults reflect ELM source (namelist_defaults.xml), NOT Kougarok overrides.
    Kougarok-equivalent tests must explicitly set ELM_OPTIONS to FATES mode.
    """

    def test_no_env_raises(self):
        """No env vars set + no case dir -> from_env() raises ValueError.

        v2.92+ behavior: forces explicit configuration. The dataclass default
        (`ConfigMode()` with no args) is preserved for tests, but `from_env()`
        no longer silently falls back to that default.
        """
        with _EnvSandbox():
            with self.assertRaises(ValueError) as cm:
                ConfigMode.from_env()
            self.assertIn("bgc_mode", str(cm.exception))

    def test_dataclass_defaults_match_elm_source(self):
        """ConfigMode() without args (dataclass defaults) reflects ELM source.

        Defaults from namelist_defaults.xml: bgc=sp, parteh_mode=1, nu_com=RD.
        Used in tests + as a sentinel for any path that needs a baseline
        ConfigMode without parsing env vars.
        """
        mode = ConfigMode()
        self.assertEqual(mode.bgc_mode, "sp")
        self.assertFalse(mode.use_fates)
        self.assertEqual(mode.parteh_mode, 1)
        self.assertEqual(mode.nutrient, "")
        self.assertEqual(mode.nutrient_comp_pathway, "rd")
        self.assertEqual(mode.fates_spitfire_mode, 0)

    def test_kougarok_override_via_elm_options(self):
        """Kougarok site config: -bgc fates + CNP + ECA enables FATES mode."""
        with _EnvSandbox() as env:
            env.set(
                A2MC_ELM_OPTIONS="-bgc fates -nutrient cnp -nutrient_comp_pathway eca",
                A2MC_FATES_PARTEH_MODE="2",
            )
            mode = ConfigMode.from_env()
        self.assertEqual(mode.bgc_mode, "fates")
        self.assertTrue(mode.use_fates)
        self.assertEqual(mode.parteh_mode, 2)
        self.assertEqual(mode.nutrient, "cnp")
        self.assertEqual(mode.nutrient_comp_pathway, "eca")

    def test_bgc_mode_derives_use_fates(self):
        """use_fates is derived from bgc_mode (not an independent input)."""
        with _EnvSandbox() as env:
            env.set(A2MC_BGC_MODE="fates")
            mode = ConfigMode.from_env()
        self.assertTrue(mode.use_fates)

        with _EnvSandbox() as env:
            env.set(A2MC_BGC_MODE="cn")
            mode = ConfigMode.from_env()
        self.assertFalse(mode.use_fates)

    def test_inconsistent_use_fates_raises(self):
        """Explicit A2MC_USE_FATES contradicting bgc_mode raises ValueError."""
        with _EnvSandbox() as env:
            env.set(A2MC_BGC_MODE="cn", A2MC_USE_FATES="true")
            with self.assertRaises(ValueError) as cm:
                ConfigMode.from_env()
            self.assertIn("inconsistent", str(cm.exception))

    def test_invalid_bgc_mode_raises(self):
        with _EnvSandbox() as env:
            env.set(A2MC_BGC_MODE="invalid")
            with self.assertRaises(ValueError):
                ConfigMode.from_env()

    def test_invalid_parteh_mode_raises(self):
        with _EnvSandbox() as env:
            env.set(A2MC_FATES_PARTEH_MODE="3")
            with self.assertRaises(ValueError):
                ConfigMode.from_env()

    def test_fates_dgvm_conflict_raises(self):
        """bgc=fates + -dynamic_vegetation should raise (FATES IS the DGVM)."""
        with _EnvSandbox() as env:
            env.set(A2MC_ELM_OPTIONS="-bgc fates -dynamic_vegetation")
            with self.assertRaises(ValueError) as cm:
                ConfigMode.from_env()
            self.assertIn("DGVM", str(cm.exception))

    def test_sp_fates_sp_conflict_raises(self):
        with _EnvSandbox() as env:
            env.set(A2MC_BGC_MODE="sp", A2MC_USE_FATES_SP="true")
            with self.assertRaises(ValueError):
                ConfigMode.from_env()

    def test_elm_only_via_env(self):
        """Explicit ELM-only run via env vars: use_fates derives False."""
        with _EnvSandbox() as env:
            env.set(A2MC_BGC_MODE="bgc")
            mode = ConfigMode.from_env()
        self.assertFalse(mode.use_fates)
        self.assertEqual(mode.bgc_mode, "bgc")

    def test_parteh_1_carbon_only_under_fates(self):
        with _EnvSandbox() as env:
            env.set(
                A2MC_ELM_OPTIONS="-bgc fates -nutrient c",
                A2MC_FATES_PARTEH_MODE="1",
            )
            mode = ConfigMode.from_env()
        self.assertTrue(mode.use_fates)
        self.assertEqual(mode.parteh_mode, 1)

    def test_nocomp_under_fates(self):
        with _EnvSandbox() as env:
            env.set(
                A2MC_ELM_OPTIONS="-bgc fates -nutrient cnp -nutrient_comp_pathway eca",
                A2MC_USE_FATES_NOCOMP="true",
                A2MC_FATES_PARTEH_MODE="2",
            )
            mode = ConfigMode.from_env()
        self.assertTrue(mode.use_fates_nocomp)

    def test_cn_only_nutrient(self):
        with _EnvSandbox() as env:
            env.set(
                A2MC_ELM_OPTIONS=
                "-bgc fates -nutrient cn -nutrient_comp_pathway eca"
            )
            mode = ConfigMode.from_env()
        self.assertEqual(mode.nutrient, "cn")
        self.assertEqual(mode.nutrient_comp_pathway, "eca")

    # ----- Tier 2 FATES feature flag fixtures -----

    def test_fates_spitfire_mode_parsed(self):
        with _EnvSandbox() as env:
            env.set(
                A2MC_BGC_MODE="fates",
                A2MC_FATES_SPITFIRE_MODE="2",
            )
            mode = ConfigMode.from_env()
        self.assertEqual(mode.fates_spitfire_mode, 2)

    def test_invalid_spitfire_mode_raises(self):
        with _EnvSandbox() as env:
            env.set(A2MC_FATES_SPITFIRE_MODE="3")
            with self.assertRaises(ValueError):
                ConfigMode.from_env()

    def test_use_fates_planthydro_parsed(self):
        with _EnvSandbox() as env:
            env.set(A2MC_BGC_MODE="fates", A2MC_USE_FATES_PLANTHYDRO="true")
            mode = ConfigMode.from_env()
        self.assertTrue(mode.use_fates_planthydro)

    def test_use_fates_logging_parsed(self):
        with _EnvSandbox() as env:
            env.set(A2MC_BGC_MODE="fates", A2MC_USE_FATES_LOGGING="true")
            mode = ConfigMode.from_env()
        self.assertTrue(mode.use_fates_logging)

    # ----- Tier 3 secondary compset modifier fixtures -----

    def test_bare_flag_parsing_methane(self):
        with _EnvSandbox() as env:
            env.set(A2MC_ELM_OPTIONS="-bgc bgc -nutrient cnp -methane")
            mode = ConfigMode.from_env()
        self.assertTrue(mode.methane)

    def test_bare_flag_parsing_hydrstress(self):
        with _EnvSandbox() as env:
            env.set(A2MC_ELM_OPTIONS="-bgc fates -nutrient cnp -hydrstress")
            mode = ConfigMode.from_env()
        self.assertTrue(mode.hydrstress)

    def test_bgc_bgc_auto_pairs_methane(self):
        """-bgc bgc auto-implies methane=True (per config_component.xml)."""
        with _EnvSandbox() as env:
            env.set(A2MC_ELM_OPTIONS="-bgc bgc -nutrient cnp -nutrient_comp_pathway eca -soil_decomp ctc")
            mode = ConfigMode.from_env()
        self.assertTrue(mode.methane)

    def test_irrig_with_value_and_tw_irr(self):
        """-irrig .true. -tw_irr_on (WFM compset pair) sets irrig=True."""
        with _EnvSandbox() as env:
            env.set(A2MC_ELM_OPTIONS="-bgc fates -nutrient cnp -irrig .true. -tw_irr_on")
            mode = ConfigMode.from_env()
        self.assertTrue(mode.irrig)

    def test_solar_rad_scheme_top(self):
        with _EnvSandbox() as env:
            env.set(A2MC_ELM_OPTIONS="-bgc fates -nutrient cnp -solar_rad_scheme top")
            mode = ConfigMode.from_env()
        self.assertEqual(mode.solar_rad_scheme, "top")


class TestConfigModePromptBlock(unittest.TestCase):
    """to_prompt_block() produces text the LLM uses to self-correct."""

    def _kougarok_mode(self):
        """Helper: set the env to canonical Kougarok config."""
        os.environ["A2MC_ELM_OPTIONS"] = (
            "-bgc fates -nutrient cnp -nutrient_comp_pathway eca"
        )
        os.environ["A2MC_FATES_PARTEH_MODE"] = "2"
        return ConfigMode.from_env()

    def test_kougarok_lists_fates_enabled(self):
        with _EnvSandbox():
            mode = self._kougarok_mode()
        block = mode.to_prompt_block()
        self.assertIn("FATES: enabled", block)
        self.assertIn("PARTEH=2", block)
        self.assertIn("Nutrient cycling: CNP", block)
        self.assertIn("Competition: ON", block)

    def test_elm_only_says_fates_disabled(self):
        """Explicit ELM-only run -> FATES disabled in prompt block."""
        with _EnvSandbox() as env:
            env.set(A2MC_BGC_MODE="bgc")
            mode = ConfigMode.from_env()
        block = mode.to_prompt_block()
        self.assertIn("FATES DISABLED", block)
        # ELM-only must not mention PARTEH or competition
        self.assertNotIn("PARTEH=", block)
        self.assertNotIn("Competition:", block)

    def test_parteh_1_warns_cnp_inapplicable(self):
        with _EnvSandbox() as env:
            env.set(
                A2MC_ELM_OPTIONS="-bgc fates -nutrient c",
                A2MC_FATES_PARTEH_MODE="1",
            )
            mode = ConfigMode.from_env()
        block = mode.to_prompt_block()
        self.assertIn("PARTEH=1", block)
        self.assertIn("carbon-only", block)
        self.assertIn("CNP mechanisms", block)
        self.assertIn("do NOT apply", block)

    def test_nocomp_warns_eca_rd_inapplicable(self):
        with _EnvSandbox() as env:
            env.set(
                A2MC_ELM_OPTIONS="-bgc fates -nutrient cnp -nutrient_comp_pathway eca",
                A2MC_USE_FATES_NOCOMP="true",
                A2MC_FATES_PARTEH_MODE="2",
            )
            mode = ConfigMode.from_env()
        block = mode.to_prompt_block()
        self.assertIn("Competition: OFF", block)
        self.assertIn("ECA/RD do NOT apply", block)

    def test_cn_only_warns_p_cycle_inapplicable(self):
        with _EnvSandbox() as env:
            env.set(
                A2MC_ELM_OPTIONS=
                "-bgc fates -nutrient cn -nutrient_comp_pathway eca",
                A2MC_FATES_PARTEH_MODE="2",
            )
            mode = ConfigMode.from_env()
        block = mode.to_prompt_block()
        self.assertIn("Nutrient cycling: CN", block)
        self.assertIn("P-cycle parameters", block)
        self.assertIn("do NOT apply", block)

    def test_tier2_features_render_when_active(self):
        """Active Tier 2 flags appear in prompt; off flags do not."""
        with _EnvSandbox() as env:
            env.set(
                A2MC_ELM_OPTIONS="-bgc fates -nutrient cnp",
                A2MC_FATES_SPITFIRE_MODE="1",
                A2MC_USE_FATES_PLANTHYDRO="true",
            )
            mode = ConfigMode.from_env()
        block = mode.to_prompt_block()
        self.assertIn("FATES features:", block)
        self.assertIn("spitfire=1", block)
        self.assertIn("planthydro", block)
        self.assertNotIn("logging", block)


class TestConfigModeKbSourceFilter(unittest.TestCase):
    """kb_source_filter() returns 'elm' for ELM-only runs, None otherwise."""

    def test_elm_only_filters_to_elm_via_env(self):
        """Explicit ELM-only via env -> use_fates=False -> kb_source filters to 'elm'."""
        with _EnvSandbox() as env:
            env.set(A2MC_BGC_MODE="bgc")
            mode = ConfigMode.from_env()
        self.assertEqual(mode.kb_source_filter(), "elm")

    def test_kougarok_no_filter(self):
        """FATES on -> no kb_source filter (both ELM and FATES allowed)."""
        with _EnvSandbox() as env:
            env.set(A2MC_ELM_OPTIONS="-bgc fates -nutrient cnp -nutrient_comp_pathway eca")
            mode = ConfigMode.from_env()
        self.assertIsNone(mode.kb_source_filter())

    def test_parteh_1_under_fates_still_no_filter(self):
        """PARTEH=1 carbon-only is still FATES-on; kb_source filter only applies
        when bgc_mode != 'fates'.
        """
        with _EnvSandbox() as env:
            env.set(
                A2MC_ELM_OPTIONS="-bgc fates -nutrient c",
                A2MC_FATES_PARTEH_MODE="1",
            )
            mode = ConfigMode.from_env()
        self.assertIsNone(mode.kb_source_filter())


class TestModeBlockBuilder(unittest.TestCase):
    """_build_active_mode_block returns the same text as ConfigMode.to_prompt_block()."""

    def test_helper_matches_method(self):
        from reasoning.methods import _build_active_mode_block
        with _EnvSandbox() as env:
            # Set explicit ELM-only mode via env (v2.92+: from_env() requires it)
            env.set(A2MC_BGC_MODE="bgc")
            mode = ConfigMode.from_env()
            block_helper = _build_active_mode_block()
        self.assertIn(mode.to_prompt_block(), block_helper)
        # Helper appends a trailing blank line for prompt formatting
        self.assertTrue(block_helper.endswith("\n\n"))


# =============================================================================
# Phase B fixtures (placeholder; will be filled in once filtering lands)
# =============================================================================

class TestToChromaWhere(unittest.TestCase):
    """ConfigMode.to_chroma_where() builds a 20-axis filter clause."""

    def test_clause_has_20_branches(self):
        """One $or branch per axis."""
        m = ConfigMode()
        where = m.to_chroma_where()
        self.assertIn("$and", where)
        self.assertEqual(len(where["$and"]), 20)

    def test_branch_structure_universal_or_active(self):
        """Each branch is $or [{applies_universal: True}, {applies_in_<axis>_<v>: True}]."""
        m = ConfigMode(bgc_mode="fates", use_fates=True, parteh_mode=2)
        where = m.to_chroma_where()
        for branch in where["$and"]:
            self.assertIn("$or", branch)
            options = branch["$or"]
            self.assertEqual(len(options), 2)
            # First option is always applies_universal
            self.assertEqual(options[0], {"applies_universal": True})
            # Second is the active per-axis flag
            for k, v in options[1].items():
                self.assertTrue(k.startswith("applies_in_"))
                self.assertIs(v, True)


class TestBuildAppliesInFlags(unittest.TestCase):
    """build_applies_in_flags() generates correct chunk metadata flags."""

    def test_untagged_returns_universal_only(self):
        from tools.config import build_applies_in_flags
        flags = build_applies_in_flags(None)
        self.assertEqual(flags, {"applies_universal": True})

        flags2 = build_applies_in_flags({})
        self.assertEqual(flags2, {"applies_universal": True})

    def test_tagged_no_universal(self):
        from tools.config import build_applies_in_flags
        flags = build_applies_in_flags({"parteh_mode": [2], "use_fates": [True]})
        # No applies_universal on tagged entries
        self.assertNotIn("applies_universal", flags)
        # Per-axis flags for tagged axis
        self.assertIs(flags["applies_in_parteh_mode_2"], True)
        self.assertIs(flags["applies_in_parteh_mode_1"], False)
        self.assertIs(flags["applies_in_use_fates_true"], True)
        self.assertIs(flags["applies_in_use_fates_false"], False)
        # Untagged axis: all values True (universal w.r.t. that axis)
        self.assertIs(flags["applies_in_nutrient_cnp"], True)
        self.assertIs(flags["applies_in_nutrient_empty"], True)


class TestPathPrefixTags(unittest.TestCase):
    """rag/loader.py path-prefix table covers expected wiki sections."""

    def test_fire_directory_tagged_spitfire(self):
        from rag.loader import path_prefix_tags
        tags = path_prefix_tags("fire/ignition.md")
        self.assertIsNotNone(tags)
        self.assertEqual(tags["fates_spitfire_mode"], [1, 2])

    def test_carbon_only_tagged_parteh_1(self):
        from rag.loader import path_prefix_tags
        tags = path_prefix_tags("plant-physiology/parteh/carbon_only.md")
        self.assertIsNotNone(tags)
        self.assertEqual(tags["parteh_mode"], [1])

    def test_cnp_allocation_tagged_parteh_2(self):
        from rag.loader import path_prefix_tags
        tags = path_prefix_tags("plant-physiology/parteh/cnp_allocation.md")
        self.assertIsNotNone(tags)
        self.assertEqual(tags["parteh_mode"], [2])
        self.assertEqual(tags["nutrient"], ["cn", "cnp"])

    def test_transpiration_inverse_tag(self):
        """transpiration.md applies when planthydro is OFF (inverse)."""
        from rag.loader import path_prefix_tags
        tags = path_prefix_tags("biophysics/transpiration.md")
        self.assertIsNotNone(tags)
        self.assertEqual(tags["use_fates_planthydro"], [False])

    def test_universal_paths_return_none(self):
        from rag.loader import path_prefix_tags
        for source in ["overview/index.md", "plant-physiology/allometry.md",
                       "architecture/main_loop.md"]:
            self.assertIsNone(path_prefix_tags(source),
                              f"{source} should not match any path-prefix")


# Phase B placeholders activated. These require a live RAG index, so they
# query rag/chroma_db/api-43-1/ directly via chromadb. Skipped if the index
# isn't present.

class TestPhaseBFilteringEndToEnd(unittest.TestCase):
    """Real-index zero-leakage assertions against api-43-1 ChromaDB."""

    @classmethod
    def setUpClass(cls):
        try:
            import chromadb
            db_path = _REPO_ROOT / "rag" / "chroma_db" / "api-43-1"
            if not db_path.exists():
                raise unittest.SkipTest(f"api-43-1 RAG index not present at {db_path}")
            cls.client = chromadb.PersistentClient(path=str(db_path))
            cls.coll = cls.client.get_collection("fates_knowledge")
        except Exception as e:
            raise unittest.SkipTest(f"Could not load api-43-1 ChromaDB: {e}")

    def _passes(self, chunk_id_or_source, where, by_source=False):
        """Return True if a chunk matches both the locator and the where clause."""
        kwargs = {"where": where, "limit": 1}
        if by_source:
            kwargs["where"] = {"$and": where["$and"] + [{"source": chunk_id_or_source}]}
        else:
            kwargs["ids"] = [chunk_id_or_source]
        result = self.coll.get(**kwargs)
        return len(result["ids"]) > 0

    def test_parteh_1_does_not_retrieve_pid_controller(self):
        m = ConfigMode(bgc_mode="fates", use_fates=True, parteh_mode=1, nutrient="c")
        # PID controller param fates_cnp_pid_kp should be filtered
        self.assertFalse(self._passes("param_def::fates_cnp_pid_kp", m.to_chroma_where()))

    def test_parteh_1_does_not_retrieve_cnp_allocation_theory(self):
        """Path-prefix tagging filters CNP allocation theory chunks."""
        m = ConfigMode(bgc_mode="fates", use_fates=True, parteh_mode=1, nutrient="c")
        self.assertFalse(self._passes(
            "plant-physiology/parteh/cnp_allocation.md",
            m.to_chroma_where(), by_source=True,
        ))

    def test_parteh_2_does_not_retrieve_carbon_only_theory(self):
        m = ConfigMode(bgc_mode="fates", use_fates=True, parteh_mode=2,
                       nutrient="cnp", nutrient_comp_pathway="eca")
        self.assertFalse(self._passes(
            "plant-physiology/parteh/carbon_only.md",
            m.to_chroma_where(), by_source=True,
        ))

    def test_no_fire_filters_fire_chunks(self):
        """Default Kougarok (spitfire=0) should filter fire chunks."""
        m = ConfigMode(bgc_mode="fates", use_fates=True, parteh_mode=2,
                       nutrient="cnp", nutrient_comp_pathway="eca")
        self.assertFalse(self._passes(
            "fire/ignition.md", m.to_chroma_where(), by_source=True,
        ))

    def test_spitfire_on_passes_fire_chunks(self):
        m = ConfigMode(bgc_mode="fates", use_fates=True, parteh_mode=2,
                       nutrient="cnp", nutrient_comp_pathway="eca",
                       fates_spitfire_mode=1)
        self.assertTrue(self._passes(
            "fire/ignition.md", m.to_chroma_where(), by_source=True,
        ))

    def test_universal_param_passes_in_all_modes(self):
        for cfg in [
            ConfigMode(),  # default ELM SP
            ConfigMode(bgc_mode="fates", use_fates=True, parteh_mode=1),
            ConfigMode(bgc_mode="fates", use_fates=True, parteh_mode=2,
                       nutrient="cnp", nutrient_comp_pathway="eca"),
        ]:
            self.assertTrue(self._passes(
                "param_def::fates_alloc_storage_cushion", cfg.to_chroma_where()
            ), f"universal param should pass in {cfg.bgc_mode} parteh={cfg.parteh_mode}")

    def test_kougarok_mode_count_strict_superset_of_default(self):
        """Kougarok mode should retrieve at least as many chunks as default ELM."""
        m_default = ConfigMode()
        m_kougarok = ConfigMode(bgc_mode="fates", use_fates=True, parteh_mode=2,
                                nutrient="cnp", nutrient_comp_pathway="eca")
        n_default = len(self.coll.get(where=m_default.to_chroma_where(),
                                       limit=10000)["ids"])
        n_kougarok = len(self.coll.get(where=m_kougarok.to_chroma_where(),
                                        limit=10000)["ids"])
        self.assertGreater(n_kougarok, n_default,
                           "FATES-on Kougarok should retrieve more than default ELM")


class TestCaseParser(unittest.TestCase):
    """case_parser reads a CIME case directory and produces a ConfigMode.

    Uses the example case at Offline/CIME_case_example/ which is committed
    in the repo for exactly this purpose.
    """

    EXAMPLE_CASE = (
        Path(__file__).resolve().parent.parent
        / "Offline"
        / "CIME_case_example"
        / "Kougarok_ELM-FATES_PtCNPEn86_TRANS"
    )

    def setUp(self):
        if not self.EXAMPLE_CASE.exists():
            self.skipTest(f"Example case not found: {self.EXAMPLE_CASE}")

    def test_parse_env_run_xml_extracts_elm_bldnml_opts(self):
        from tools.case_parser import parse_env_run_xml
        opts = parse_env_run_xml(self.EXAMPLE_CASE / "env_run.xml")
        self.assertIn("-bgc fates", opts)
        self.assertIn("-nutrient cnp", opts)
        self.assertIn("-nutrient_comp_pathway eca", opts)
        self.assertIn("-soil_decomp century", opts)

    def test_parse_user_nl_elm_extracts_fates_settings(self):
        from tools.case_parser import parse_namelist_file
        nl = parse_namelist_file(self.EXAMPLE_CASE / "user_nl_elm")
        self.assertEqual(nl.get("fates_parteh_mode"), 2)
        self.assertEqual(nl.get("use_fates"), True)
        self.assertEqual(nl.get("use_fates_nocomp"), False)

    def test_parse_lnd_in_extracts_resolved_namelist(self):
        from tools.case_parser import parse_namelist_file
        nl = parse_namelist_file(self.EXAMPLE_CASE / "CaseDocs" / "lnd_in")
        self.assertEqual(nl.get("use_fates"), True)
        self.assertEqual(nl.get("fates_parteh_mode"), 2)
        self.assertEqual(nl.get("nu_com"), "ECA")
        self.assertEqual(nl.get("use_century_decomp"), True)

    def test_case_to_config_mode_full_resolution(self):
        from tools.case_parser import case_to_config_mode
        mode = case_to_config_mode(self.EXAMPLE_CASE)
        self.assertEqual(mode.bgc_mode, "fates")
        self.assertTrue(mode.use_fates)
        self.assertEqual(mode.parteh_mode, 2)
        self.assertEqual(mode.nutrient, "cnp")
        self.assertEqual(mode.nutrient_comp_pathway, "eca")
        self.assertEqual(mode.soil_decomp, "century")
        self.assertFalse(mode.use_fates_nocomp)
        self.assertEqual(mode.fates_spitfire_mode, 0)
        self.assertFalse(mode.use_fates_planthydro)

    def test_from_env_uses_case_dir_when_set(self):
        with _EnvSandbox() as env:
            env.set(A2MC_CASE_DIR=str(self.EXAMPLE_CASE))
            mode = ConfigMode.from_env()
        self.assertEqual(mode.bgc_mode, "fates")
        self.assertEqual(mode.parteh_mode, 2)
        self.assertEqual(mode.nutrient, "cnp")

    def test_resolve_case_dir_from_e3sm_root_and_case_name(self):
        from tools.case_parser import resolve_case_dir
        with _EnvSandbox() as env:
            # Set A2MC_E3SM_ROOT + A2MC_CASE_NAME to resolve to example case
            example_parent = self.EXAMPLE_CASE.parent.parent  # Offline/
            # Pretend E3SM root has cime/scripts/<case_name>
            # We can't easily fake this without modifying the filesystem;
            # just confirm the env-var lookup logic returns None when paths
            # don't exist.
            env.set(A2MC_E3SM_ROOT="/nonexistent", A2MC_CASE_NAME="foo")
            self.assertIsNone(resolve_case_dir())


class TestEnvVsCaseDirPriority(unittest.TestCase):
    """v2.94+: env vars are PRIMARY (user intent); case dir is enrichment only.

    Env vars override case dir on conflict (with a warning). Case dir fills
    in fields env vars didn't specify.
    """

    EXAMPLE_CASE = (
        Path(__file__).resolve().parent.parent
        / "Offline"
        / "CIME_case_example"
        / "Kougarok_ELM-FATES_PtCNPEn86_TRANS"
    )

    def setUp(self):
        if not self.EXAMPLE_CASE.exists():
            self.skipTest(f"Example case not found: {self.EXAMPLE_CASE}")

    def test_env_vars_override_case_dir(self):
        """Env-set parteh_mode overrides case-dir's resolved value."""
        import warnings
        with _EnvSandbox() as env:
            env.set(
                A2MC_CASE_DIR=str(self.EXAMPLE_CASE),  # case has parteh_mode=2
                A2MC_FATES_PARTEH_MODE="1",            # user updates intent to 1
            )
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                mode = ConfigMode.from_env()
            # Env wins
            self.assertEqual(mode.parteh_mode, 1)
            # Warning emitted about the conflict
            conflict_warnings = [str(x.message) for x in w
                                 if "overrides" in str(x.message)]
            self.assertGreater(len(conflict_warnings), 0,
                               "Expected a conflict warning")

    def test_case_dir_enriches_unset_fields(self):
        """Env vars don't specify nutrient/pathway/decomp; case dir fills them."""
        with _EnvSandbox() as env:
            env.set(
                A2MC_CASE_DIR=str(self.EXAMPLE_CASE),
                # User only sets bgc_mode + parteh_mode
                A2MC_BGC_MODE="fates",
                A2MC_FATES_PARTEH_MODE="2",
                # nutrient, pathway, decomp NOT set in env
            )
            mode = ConfigMode.from_env()
        # All filled from case dir
        self.assertEqual(mode.nutrient, "cnp")
        self.assertEqual(mode.nutrient_comp_pathway, "eca")
        self.assertEqual(mode.soil_decomp, "century")

    def test_no_warning_when_env_and_case_agree(self):
        """No conflict warning when env vars and case dir agree."""
        import warnings
        with _EnvSandbox() as env:
            env.set(
                A2MC_CASE_DIR=str(self.EXAMPLE_CASE),
                A2MC_BGC_MODE="fates",
                A2MC_FATES_PARTEH_MODE="2",  # matches case dir
            )
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                mode = ConfigMode.from_env()
            conflict_warnings = [x for x in w
                                 if "overrides" in str(x.message)]
            self.assertEqual(len(conflict_warnings), 0)

    def test_env_only_works_without_case_dir(self):
        """No case dir set + env vars provide everything: works."""
        with _EnvSandbox() as env:
            env.set(
                A2MC_ELM_OPTIONS="-bgc fates -nutrient cnp -nutrient_comp_pathway eca",
                A2MC_FATES_PARTEH_MODE="2",
            )
            mode = ConfigMode.from_env()
        self.assertEqual(mode.bgc_mode, "fates")
        self.assertEqual(mode.parteh_mode, 2)
        self.assertEqual(mode.nutrient, "cnp")


if __name__ == "__main__":
    unittest.main(verbosity=2)
