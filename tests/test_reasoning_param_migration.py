"""
docs/37 Stage 1 — reasoning/ layer onto the canonical loader.

Locks the dual-path behavior of the migrated readers: the new explicit-column CSV keys by
canonical_id (via load_param_spec); the legacy shorthand .txt keeps its shorthand keys.
"""
from pathlib import Path

import pytest

from tools.count_param_list import count_params
from tests.helpers import active_param_list

REPO = Path(__file__).resolve().parents[1]
# The ACTIVE param CSV comes from the SAME authority production uses — the site
# config's A2MC_PARAM_LIST_FILE (see conftest.active_param_list). Never guess it,
# and never hardcode the size: count_params is authoritative for A2MC_N_PARAMS.
CSV = active_param_list("ELM-FATES_Kougarok")
N_PARAMS = count_params(CSV)
TXT = REPO / "use_cases/ELM-FATES_Kougarok/parameters/FATES_Parameter_List_Full_162_Finalized.txt"


# --- reasoning/validation.py: load_parameter_bounds + find_bounds_entry --------------------

def test_bounds_new_format_keyed_by_canonical_id():
    from reasoning.validation import load_parameter_bounds
    b = load_parameter_bounds(str(CSV))
    assert len(b) == N_PARAMS
    # canonical-id keys, including a virtual coord
    assert "fates_stoich_nitr#p10#o1" in b
    assert "seed_repro_fraction#p10" in b
    # organ collapses to the legacy single-int form (matches the old shorthand parser)
    assert b["fates_stoich_nitr#p10#o1"]["organ"] == 1          # leaf
    assert b["fates_stoich_nitr#p10#o2"]["organ"] == 2          # fineroot
    assert b["fates_cnp_turnover_nitr_retrans#p10#o1-2"]["organ"] is None  # retrans → None
    # global params carry pft None (not 0)
    assert b["fates_maintresp_nonleaf_baserate"]["pft"] is None
    # entry shape preserved
    e = b["fates_stoich_nitr#p10#o1"]
    assert e["fates_name"] == "fates_stoich_nitr" and e["pft"] == 10
    assert e["lower_bound"] < e["upper_bound"]


def test_find_bounds_entry_by_fates_name_pft_organ():
    from reasoning.validation import load_parameter_bounds, find_bounds_entry
    b = load_parameter_bounds(str(CSV))
    # the AI proposes (fates_name, pft, organ); the reverse lookup must find the row
    leaf = find_bounds_entry("fates_stoich_nitr", 10, 1, b)
    froot = find_bounds_entry("fates_stoich_nitr", 10, 2, b)
    assert leaf and froot and leaf["upper_bound"] != froot["upper_bound"]   # distinct organ rows
    # retrans: entry organ is None → matches any requested organ (legacy behavior)
    rt = find_bounds_entry("fates_cnp_turnover_nitr_retrans", 10, 1, b)
    assert rt and (rt["lower_bound"], rt["upper_bound"]) == (0.4, 0.7)
    # a non-existent combo returns None
    assert find_bounds_entry("fates_not_a_param", 10, 1, b) is None


@pytest.mark.skipif(not TXT.exists(), reason="legacy .txt not present")
def test_bounds_legacy_format_keyed_by_shorthand():
    from reasoning.validation import load_parameter_bounds
    b = load_parameter_bounds(str(TXT))
    assert b, "legacy bounds should load"
    # legacy keys are shorthands (no '#' canonical markers, no fates_ prefix on the key)
    assert not any("#" in k for k in b)
    sample = next(iter(b.values()))
    assert {"lower_bound", "upper_bound", "pft", "organ", "fates_name"} <= set(sample)


# --- reasoning/base.py: the 4 readers (via staticmethod-preserving stub) ---------------------

def _base_stub():
    """A minimal object carrying just what the migrated base.py readers touch."""
    from reasoning.base import ReasoningModule
    class Stub:
        _is_new_param_list = staticmethod(ReasoningModule._is_new_param_list)
        _shorthand_to_official = None
    return ReasoningModule, Stub()


def test_base_build_param_name_mapping_new_format(monkeypatch):
    monkeypatch.setenv("A2MC_PARAM_LIST_FILE", str(CSV))
    RM, s = _base_stub()
    m = RM._build_param_name_mapping(s)
    assert m["fates_stoich_nitr#p10#o1"] == ("fates_stoich_nitr", 10)   # canonical_id → (fates_name, pft)
    assert m["seed_repro_fraction#p10"] == ("seed_repro_fraction", 10)  # virtual coord too
    assert m["fates_stoich_nitr"] == ("fates_stoich_nitr", None)        # base node


def test_base_resolve_param_names_to_graph_nodes(monkeypatch):
    monkeypatch.setenv("A2MC_PARAM_LIST_FILE", str(CSV))
    RM, s = _base_stub()
    s._shorthand_to_official = RM._build_param_name_mapping(s)
    assert RM._resolve_param_names(s, ["fates_stoich_nitr#p10#o1", "seed_repro_fraction#p10"]) == \
        ["fates_stoich_nitr:pft10", "seed_repro_fraction:pft10"]


def test_base_case_params_new_format_canonical_keyed(tmp_path, monkeypatch):
    import numpy as np
    from tools.param_spec import load_param_spec
    specs = load_param_spec(str(CSV))
    mat = tmp_path / "mat.txt"
    np.savetxt(mat, np.vstack([np.arange(len(specs)), np.arange(len(specs)) + 1000.0]))
    monkeypatch.setenv("A2MC_PARAM_LIST_FILE", str(CSV))
    monkeypatch.setenv("A2MC_ENSEMBLE_MATRIX_FILE", str(mat))
    RM, s = _base_stub()
    bc = RM._load_base_case_parameters(s, 2)          # case 2 → row idx 1 = arange+1000
    assert len(bc) == N_PARAMS
    tgt = next(x.row_index for x in specs if x.canonical_id == "fates_stoich_nitr#p10#o1")
    assert bc["fates_stoich_nitr#p10#o1"] == pytest.approx(tgt + 1000.0)


def test_base_ensemble_listing_uses_canonical_ids(monkeypatch):
    monkeypatch.setenv("A2MC_PARAM_LIST_FILE", str(CSV))
    RM, s = _base_stub()
    txt = RM._load_ensemble_parameter_list(s)
    assert "fates_stoich_nitr#p10#o1" in txt and "canonical id" in txt


# --- tools/modify_fates_parameters.resolve_parameter_name (spec-based, new format) ----------

def _specs():
    from tools.param_spec import load_param_spec
    return load_param_spec(str(CSV))


def test_resolve_retrans_broadcasts_organ_list():
    from tools.modify_fates_parameters import resolve_parameter_name as R
    # retrans without organ → [1,2] so design_experiments writes both slots
    assert R("fates_cnp_turnover_nitr_retrans", pft=10, organ=None, specs=_specs()) == \
        ("fates_cnp_turnover_nitr_retrans", 10, [1, 2])


def test_resolve_stoich_canonical_and_explicit():
    from tools.modify_fates_parameters import resolve_parameter_name as R
    specs = _specs()
    assert R("fates_stoich_nitr#p10#o1", specs=specs) == ("fates_stoich_nitr", 10, 1)
    assert R("fates_stoich_nitr#p10#o2", specs=specs) == ("fates_stoich_nitr", 10, 2)
    assert R("fates_stoich_nitr", pft=10, organ=1, specs=specs) == ("fates_stoich_nitr", 10, 1)


def test_resolve_nonorgan_and_ambiguity():
    from tools.modify_fates_parameters import resolve_parameter_name as R
    specs = _specs()
    assert R("fates_cnp_vmax_nh4", pft=10, specs=specs) == ("fates_cnp_vmax_nh4", 10, None)
    assert R("seed_repro_fraction#p10", specs=specs) == ("seed_repro_fraction", 10, None)
    with pytest.raises(ValueError, match="organ-dependent"):
        R("fates_stoich_nitr", pft=10, organ=None, specs=specs)


# --- phases/phase3_diagnosis readers -------------------------------------------------------

def test_phase3_load_param_names_canonical():
    from phases.phase3_diagnosis.read_case_parameters import load_param_names
    names = load_param_names(str(CSV))
    assert len(names) == N_PARAMS
    assert "fates_stoich_nitr#p10#o1" in names and "seed_repro_fraction#p10" in names


def test_phase3_load_param_bounds_column_order():
    from phases.phase3_diagnosis.read_case_parameters import load_param_names, load_param_bounds
    from tools.param_spec import load_param_spec
    names, bounds = load_param_names(str(CSV)), load_param_bounds(str(CSV))
    specs = load_param_spec(str(CSV))
    assert len(bounds) == len(names) == N_PARAMS
    # bounds are in canonical column order
    assert bounds[0] == (specs[0].lower, specs[0].upper)


def test_phase3_categorize_canonical_ids():
    from phases.phase3_diagnosis.check_edge_parameters import categorize_edge_parameters
    er = {"at_lower": [{"name": "fates_stoich_nitr#p10#o1"},
                       {"name": "fates_cnp_eca_vmax_nh4#p10"}],
          "at_upper": [{"name": "seed_repro_fraction#p12"},
                       {"name": "fates_recruit_seed_dbh_repro_threshold#p12"}]}
    cats = categorize_edge_parameters(er)
    assert len(cats["Stoichiometry_N"]["at_lower"]) == 1
    assert len(cats["CNP_vmax"]["at_lower"]) == 1
    assert len(cats["Recruitment"]["at_upper"]) == 2   # seed_repro_fraction + dbh_repro threshold
    # nothing fell through to 'Other' (empty categories are dropped from the result)
    assert not cats.get("Other", {}).get("at_lower") and not cats.get("Other", {}).get("at_upper")
