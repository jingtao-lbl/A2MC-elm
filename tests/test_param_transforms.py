"""
Tests for the derived-parameter transform registry (tools/param_transforms.py, dev_logs/20260710a).

Locks the seed_repro_split transform: forward map, round-trip property over the whole Morris box,
default-preservation against the base-file natives, the static feasibility certificate, and the
divide-by-zero guard.
"""
import os
from pathlib import Path

import pytest

from tools.param_transforms import (
    DERIVED_TRANSFORMS,
    COORD_TO_GROUP,
    NATIVE_TO_GROUP,
    is_virtual_coord,
    native_targets,
    transform_for_coord,
    virtual_coords,
)

SEED = DERIVED_TRANSFORMS["seed_repro_split"]
SA, SAM = "fates_recruit_seed_alloc", "fates_recruit_seed_alloc_mature"
REPRO, SHARE = "seed_repro_fraction", "seed_alloc_fraction"

# api-43 base (fates_params_default.json) natives for the three Kougarok arctic PFTs.
BASE_NATIVES = {
    10: {SA: 0.07, SAM: 0.90},   # broadleaf_evergreen_arctic_shrub
    11: {SA: 0.10, SAM: 0.90},   # broadleaf_colddecid_arctic_shrub
    12: {SA: 0.00, SAM: 0.25},   # arctic_c3_grass
}


def test_registry_integrity():
    # coords and native targets are disjoint; reverse maps are consistent
    assert set(COORD_TO_GROUP) & set(NATIVE_TO_GROUP) == set()
    assert virtual_coords() == {REPRO, SHARE}
    assert native_targets() == {SA, SAM}
    assert is_virtual_coord(REPRO) and is_virtual_coord(SHARE)
    assert not is_virtual_coord(SA)                 # a native fates_ name is NOT a virtual coord
    assert transform_for_coord(REPRO) is SEED
    assert transform_for_coord("not_a_coord") is None


def test_seed_forward_map():
    out = SEED.apply({REPRO: 0.5, SHARE: 0.2})
    assert out[SA] == pytest.approx(0.10)           # 0.2 * 0.5
    assert out[SAM] == pytest.approx(0.40)          # 0.8 * 0.5
    assert out[SA] + out[SAM] == pytest.approx(0.5)  # == seed_repro_fraction


@pytest.mark.parametrize("total", [0.0, 0.1, 0.25, 0.5, 0.97, 1.0])
@pytest.mark.parametrize("share", [0.0, 0.0722, 0.1, 0.5, 1.0])
def test_roundtrip_property_over_the_box(total, share):
    """Any (total, share) in [0,1]^2 -> feasible, and the split reconstitutes the total."""
    out = SEED.apply({REPRO: total, SHARE: share})
    assert out[SA] == pytest.approx(share * total)
    assert out[SAM] == pytest.approx((1.0 - share) * total)
    assert out[SA] >= -1e-12 and out[SAM] >= -1e-12          # both non-negative
    assert out[SA] + out[SAM] <= 1.0 + 1e-9                  # sum <= 1 (never trips FATES fatal check)
    assert out[SA] + out[SAM] == pytest.approx(total)


@pytest.mark.parametrize("pft", [10, 11, 12])
def test_default_preservation(pft):
    """Coord defaults derived from base natives reproduce those natives exactly."""
    natives = BASE_NATIVES[pft]
    coords = SEED.coord_defaults(natives)
    assert set(coords) == {REPRO, SHARE}
    back = SEED.apply(coords)
    assert back[SA] == pytest.approx(natives[SA])
    assert back[SAM] == pytest.approx(natives[SAM])


def test_divide_by_zero_guard():
    """total == 0 (both natives 0) -> share defaults to 0, no ZeroDivisionError."""
    coords = SEED.coord_defaults({SA: 0.0, SAM: 0.0})
    assert coords[REPRO] == 0.0 and coords[SHARE] == 0.0
    out = SEED.apply(coords)
    assert out[SA] == 0.0 and out[SAM] == 0.0


def test_certify_bounds_accepts_in_range():
    ok, msg = SEED.certify_bounds({REPRO: 0.2, SHARE: 0.0}, {REPRO: 0.97, SHARE: 1.0})
    assert ok, msg
    assert "guaranteed" in msg


@pytest.mark.parametrize("lo,hi", [
    ({REPRO: 0.2, SHARE: 0.0}, {REPRO: 1.1, SHARE: 1.0}),   # total upper > 1
    ({REPRO: 0.2, SHARE: -0.1}, {REPRO: 0.9, SHARE: 1.0}),  # share below 0
    ({REPRO: 0.2, SHARE: 0.0}, {REPRO: 0.9, SHARE: 1.5}),   # share above 1
])
def test_certify_bounds_rejects_out_of_range(lo, hi):
    ok, _ = SEED.certify_bounds(lo, hi)
    assert not ok


def test_apply_rejects_infeasible_output():
    # total > 1 -> sum > 1 -> should raise (fail loud at generation time)
    with pytest.raises(ValueError):
        SEED.apply({REPRO: 1.2, SHARE: 0.5})


def test_apply_rejects_missing_coord():
    with pytest.raises(ValueError):
        SEED.apply({REPRO: 0.5})                             # missing seed_alloc_fraction


_BASE = os.environ.get("A2MC_BASE_PARAM_FILE", "")


@pytest.mark.skipif(not (_BASE and Path(_BASE).exists()),
                    reason="A2MC_BASE_PARAM_FILE not set / not present")
def test_default_preservation_against_live_base_file():
    """If the base param file is available, its live seed-alloc natives round-trip too."""
    import json
    P = json.load(open(_BASE))["parameters"]
    sa = P[SA]["data"]
    sam = P[SAM]["data"]
    for pft in (10, 11, 12):
        i = pft - 1
        natives = {SA: sa[i], SAM: sam[i]}
        back = SEED.apply(SEED.coord_defaults(natives))
        assert back[SA] == pytest.approx(natives[SA])
        assert back[SAM] == pytest.approx(natives[SAM])
