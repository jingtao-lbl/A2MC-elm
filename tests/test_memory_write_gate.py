"""Tests for the Tier-3 memory write gate (memory/manager.py, v2.90).

propose mode (the autonomous online agent) stages curated writes to
auto_discovered_pending.json; interactive mode (the human-in-the-loop agent) writes the
curated JSONs. See memory/dev_logs/20260612d_*. tmp_path stays under the repo tmp/ via
pytest.ini --basetemp."""
import json

from memory.manager import MemoryManager, PENDING_FILENAME


def _curated_exist(d):
    return [(d / f).exists() for f in
            ("discoveries.json", "experiments.json", "failed_approaches.json")]


def test_propose_mode_stages_not_curated(tmp_path):
    m = MemoryManager(str(tmp_path), write_mode="propose")
    m.add_discovery("x", "desc", "mech", ["leaf_pft7"], confidence=0.7)
    m.add_failed_approach("an approach", "exp1", "why", "catastrophic", [])
    m.record_experiment({"name": "exp1", "modifications": []},
                        {"targets_met": 0, "metrics": {}}, "FAILED")
    # nothing reached the curated KB
    assert _curated_exist(tmp_path) == [False, False, False]
    # all three proposals are staged
    pend = json.loads((tmp_path / PENDING_FILENAME).read_text())
    assert len(pend["pending"]) == 3
    assert {p["kind"] for p in pend["pending"]} == {"discovery", "failed_approach", "experiment"}


def test_interactive_mode_writes_curated(tmp_path):
    m = MemoryManager(str(tmp_path), write_mode="interactive")
    m.add_discovery("real", "desc", "mech", ["leaf_pft7"])
    assert (tmp_path / "discoveries.json").exists()
    assert not (tmp_path / PENDING_FILENAME).exists()
    data = json.loads((tmp_path / "discoveries.json").read_text())
    # default source is auto_discovered -> verified False; promotion (source=curated) sets it True
    assert "real" in data
    assert data["real"]["verified"] is False


def test_interactive_promote_marks_verified(tmp_path):
    m = MemoryManager(str(tmp_path), write_mode="interactive")
    m.add_discovery("curated_one", "d", "m", ["x"], source="curated")
    data = json.loads((tmp_path / "discoveries.json").read_text())
    assert data["curated_one"]["verified"] is True


def test_default_mode_is_interactive(tmp_path):
    assert MemoryManager(str(tmp_path)).write_mode == "interactive"


def test_env_overrides_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("A2MC_MEMORY_WRITE_MODE", "propose")
    assert MemoryManager(str(tmp_path)).write_mode == "propose"


def test_unknown_mode_falls_back_to_interactive(tmp_path):
    assert MemoryManager(str(tmp_path), write_mode="bogus").write_mode == "interactive"
