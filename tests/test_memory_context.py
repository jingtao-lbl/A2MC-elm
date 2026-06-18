"""Tests for the read-side gate: MemoryManager.get_relevant_context(verified_only=...)
(G6). With verified_only=True, only verified discoveries reach the formatted context —
the read-side complement to the write gate. See memory/dev_logs/20260617b_* and Q4 in
20260519f."""
from memory.manager import MemoryManager


def test_get_relevant_context_verified_only_filters_discoveries(tmp_path):
    m = MemoryManager(str(tmp_path), write_mode="interactive")
    # curated -> verified True; auto_discovered -> verified False
    m.add_discovery("curated_one", "desc", "mech", ["leaf_pft7"], source="curated")
    m.add_discovery("auto_one", "desc", "mech", ["leaf_pft7"], source="auto_discovered")

    both = m.get_relevant_context(targets=["leaf_pft7"], verified_only=False)
    only = m.get_relevant_context(targets=["leaf_pft7"], verified_only=True)

    # default: both surface
    assert "curated_one" in both
    assert "auto_one" in both
    # verified_only: only the verified discovery survives
    assert "curated_one" in only
    assert "auto_one" not in only


def test_get_relevant_context_default_is_unfiltered(tmp_path):
    m = MemoryManager(str(tmp_path), write_mode="interactive")
    m.add_discovery("auto_one", "desc", "mech", ["leaf_pft7"], source="auto_discovered")
    # default call (no verified_only) keeps the unverified discovery — backward compatible
    assert "auto_one" in m.get_relevant_context(targets=["leaf_pft7"])
