"""
Golden test for the canonical param-list loader (docs/37, Stage 0b).

Locks the new `tools/param_spec.load_param_spec()` against the legacy
`tools/modify_fates_parameters.build_param_lookup()` on the shared rows of the
migrated Kougarok CSV, so the refactor stays behavior-preserving through Stages 1–2.
"""
import re
from pathlib import Path

import pytest

from tools.count_param_list import count_params
from tests.helpers import active_param_list
from tools.param_spec import load_param_spec

REPO = Path(__file__).resolve().parents[1]
# The ACTIVE param CSV comes from the SAME authority production uses — the site
# config's A2MC_PARAM_LIST_FILE (see conftest.active_param_list). Never guess it,
# and never hardcode the size: count_params is authoritative for A2MC_N_PARAMS.
CSV = active_param_list("ELM-FATES_Kougarok")
N_PARAMS = count_params(CSV)
TXT = REPO / "use_cases/ELM-FATES_Kougarok/parameters/FATES_Parameter_List_Full_162_Finalized.txt"

RETRANS = {"fates_cnp_turnover_nitr_retrans", "fates_cnp_turnover_phos_retrans"}
# names the api-43 migration renamed/split, so they intentionally differ from the legacy list
MIGRATED = {"fates_turnover_leaf_canopy", "fates_turnover_leaf_ustory"}
# api-43 seed-allocation reparameterization (dev_logs/20260710a): the legacy `fates_recruit_seed_alloc`
# rows were replaced by the virtual coords seed_repro_fraction/seed_alloc_fraction, and the previously
# fixed `fates_recruit_seed_dbh_repro_threshold` was added as a calibrated param — all intentional.
REPARAM_NEW = {"seed_repro_fraction", "seed_alloc_fraction", "fates_recruit_seed_dbh_repro_threshold"}
REPARAM_DROPPED = {"fates_recruit_seed_alloc"}
# Dropped by the api-43 migration because the parameter is INACTIVE there: `eca_alpha_ptase` is
# hard-guarded to 0 in api-43 ECA and a nonzero value aborts init, so its 3 rows were removed
# (v2.202; memory reference_fates_eca_ptase_disabled_api43). Legacy-only by design.
API43_DROPPED = {"fates_cnp_eca_alpha_ptase"}
# Promoted from a single shared scalar to per-PFT rows by the #17 port (A2MCapi43port17):
# legacy carries one row at pft=0, para169 carries PFT#11 + PFT#12 (the cold-decid arctic PFTs).
# The identity sets therefore cannot match on either side, so it is excluded from BOTH.
SCALAR_TO_PER_PFT = {"fates_phen_gddthresh_c"}
# api-31 (12-PFT) -> api-43 (14-PFT) Kougarok PFT remap (arctic variants): evergreen 7->10, decid 9->11, graminoid 10->12
PFT_REMAP = {7: 10, 9: 11, 10: 12}


def test_csv_loads_and_counts():
    specs = load_param_spec(CSV)
    assert len(specs) == N_PARAMS
    assert len({s.canonical_id for s in specs}) == N_PARAMS  # ids unique
    # seed reparameterization landed: virtual coords present, native seed_alloc row gone
    names = {s.fates_name for s in specs}
    assert {"seed_repro_fraction", "seed_alloc_fraction"} <= names
    assert "fates_recruit_seed_alloc" not in names
    assert sum(1 for s in specs if s.is_virtual) == 6
    # stoich + retrans are organ-dimensioned; turnover_leaf is not
    organ_names = {s.fates_name for s in specs if s.is_organ}
    assert "fates_stoich_nitr" in organ_names
    assert "fates_cnp_turnover_nitr_retrans" in organ_names
    assert not any("turnover_leaf" in s.fates_name and s.is_organ for s in specs)


def test_canonical_id_scheme():
    specs = {s.canonical_id: s for s in load_param_spec(CSV)}
    # evergreen shrub is PFT#10 on api-43 (was #7)
    assert "fates_stoich_nitr#p10#o1" in specs          # leaf
    assert "fates_stoich_nitr#p10#o2" in specs          # fineroot
    assert "fates_cnp_turnover_nitr_retrans#p10#o1-2" in specs  # retrans broadcast
    assert specs["fates_cnp_turnover_nitr_retrans#p10#o1-2"].organ_slots() == [1, 2]
    # nfix1 was PFT#9 (deciduous shrub), remapped to arctic decid #11
    assert "fates_cnp_nfix1#p11" in specs
    assert specs["fates_cnp_nfix1#p11"].organ == []
    # graminoid is PFT#12 on api-43 (was #10)
    assert any(s.pft == 12 for s in specs.values())


@pytest.mark.skipif(not TXT.exists(), reason="legacy .txt not present")
def test_golden_vs_build_param_lookup():
    """The (fates_name, pft, organ) identity SET of the CSV reproduces build_param_lookup(old .txt),
    excluding the intentionally-migrated turnover_leaf names."""
    from tools.modify_fates_parameters import build_param_lookup
    lk = build_param_lookup(str(TXT))  # {shorthand: {fates_name, pft, organ}}

    def norm(fates, pft, organ):
        # retrans: legacy leaves organ implicit (None) → CSV makes it explicit [1,2]
        org = (1, 2) if fates in RETRANS else (() if organ is None else (organ,))
        return (fates, PFT_REMAP.get(pft, pft), org)   # api-31 -> api-43 PFT remap

    legacy = {norm(r["fates_name"], r["pft"], r["organ"])
              for r in lk.values()
              if r["fates_name"] != "fates_turnover_leaf"
              and r["fates_name"] not in (REPARAM_DROPPED | API43_DROPPED | SCALAR_TO_PER_PFT)}
    csv = {(s.fates_name, s.pft, tuple(s.organ))
           for s in load_param_spec(CSV)
           if s.fates_name not in (MIGRATED | REPARAM_NEW | SCALAR_TO_PER_PFT)}

    assert csv == legacy, (
        f"\n  only in CSV:    {sorted(csv - legacy)}"
        f"\n  only in legacy: {sorted(legacy - csv)}")
