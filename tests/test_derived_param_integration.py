"""
Integration tests for the derived-parameter mechanism wiring (Steps 2-3, dev_logs/20260710a):
the param_spec loader flags/validates virtual coords, and generate_parameter_files expands a
derived group into its native FATES writes. Uses synthetic CSVs (no dependence on the live list).
"""
import pytest

from tools.param_spec import load_param_spec
from phases.phase0_design.generate_parameter_files import build_modifications_list

HDR = "fates_name,pft,organ,lower,upper,default,description\n"


def _write(tmp_path, body, header=HDR):
    p = tmp_path / "list.csv"
    p.write_text(header + body)
    return str(p)


def test_loader_flags_virtual_coords(tmp_path):
    csv = _write(tmp_path,
                 "fates_cnp_vmax_nh4,10,,1,2,1.5,x\n"
                 "seed_repro_fraction,10,,0.2,0.6,0.4,mature total PFT#10\n"
                 "seed_alloc_fraction,10,,0.01,1,0.1,base share PFT#10\n")
    specs = {s.fates_name: s for s in load_param_spec(csv)}
    assert specs["fates_cnp_vmax_nh4"].is_virtual is False
    assert specs["seed_repro_fraction"].is_virtual is True
    assert specs["seed_repro_fraction"].transform_group == "seed_repro_split"
    assert specs["seed_repro_fraction"].canonical_id == "seed_repro_fraction#p10"


def test_loader_incomplete_group_raises(tmp_path):
    csv = _write(tmp_path, "seed_repro_fraction,10,,0.2,0.6,0.4,only one coord\n")
    with pytest.raises(ValueError, match="incomplete"):
        load_param_spec(csv)


def test_loader_native_conflict_raises(tmp_path):
    csv = _write(tmp_path,
                 "seed_repro_fraction,10,,0.2,0.6,0.4,x\n"
                 "seed_alloc_fraction,10,,0.01,1,0.1,x\n"
                 "fates_recruit_seed_alloc,10,,0.05,0.15,0.07,direct-row conflict\n")
    with pytest.raises(ValueError, match="direct param-list rows"):
        load_param_spec(csv)


def test_loader_virtual_coord_rejects_organ(tmp_path):
    csv = _write(tmp_path, "seed_repro_fraction,10,1,0.2,0.6,0.4,should not have organ\n")
    with pytest.raises(ValueError, match="no organ"):
        load_param_spec(csv)


def test_loader_accepts_default_api43(tmp_path):
    hdr = "fates_name,pft,organ,lower,upper,default_api43,default_api31,description\n"
    csv = _write(tmp_path, "fates_cnp_vmax_nh4,10,,1,2,1.5,1.4,x\n", header=hdr)
    (spec,) = load_param_spec(csv)
    assert spec.default == 1.5            # reads default_api43, not default_api31


def test_loader_blank_default_raises(tmp_path):
    hdr = "fates_name,pft,organ,lower,upper,default_api43,description\n"
    csv = _write(tmp_path, "fates_cnp_vmax_nh4,10,,1,2,,blank\n", header=hdr)
    with pytest.raises(ValueError, match="empty default_api43"):
        load_param_spec(csv)


def test_generate_expands_group_no_leak(tmp_path):
    csv = _write(tmp_path,
                 "fates_cnp_vmax_nh4,10,,1,2,1.5,x\n"
                 "seed_repro_fraction,10,,0.2,0.6,0.4,x\n"
                 "seed_alloc_fraction,10,,0.01,1,0.1,x\n")
    mods = build_modifications_list([1.5, 0.5, 0.2], param_list_file=csv)  # repro=0.5, share=0.2
    # no virtual coordinate leaks into the param-file modifications
    assert not any(m["param"].startswith("seed_repro") or m["param"].startswith("seed_alloc_fraction")
                   for m in mods)
    native = {m["param"]: m["value"] for m in mods if m["param"].startswith("fates_recruit_seed")}
    assert native["fates_recruit_seed_alloc"] == pytest.approx(0.1)          # 0.2 * 0.5
    assert native["fates_recruit_seed_alloc_mature"] == pytest.approx(0.4)   # 0.8 * 0.5
    # the ordinary param still passes through
    assert {"param": "fates_cnp_vmax_nh4", "pft": 10, "value": 1.5} in mods


def test_verify_new_format_virtual_natives(tmp_path, monkeypatch):
    """verify_parameter_file_new checks the NATIVE params produced by the transform, and catches drift."""
    pytest.importorskip("numpy")
    pytest.importorskip("netCDF4")
    import json
    import numpy as np
    import tools.verify_parameter_file as V
    monkeypatch.setattr(V, "PARAM_FILE_DIR", str(tmp_path))

    def pft_arr(idx, val, n=12):
        a = [0.0] * n
        a[idx] = val
        return a

    doc = {"parameters": {
        "fates_cnp_vmax_nh4": {"dims": ["fates_pft"], "data": pft_arr(9, 1.5)},
        "fates_recruit_seed_alloc": {"dims": ["fates_pft"], "data": pft_arr(9, 0.1)},          # share*total = 0.2*0.5
        "fates_recruit_seed_alloc_mature": {"dims": ["fates_pft"], "data": pft_arr(9, 0.4)},   # (1-share)*total
    }}
    pf = tmp_path / "fates_params_test_En1.json"
    pf.write_text(json.dumps(doc))
    csv = _write(tmp_path,
                 "fates_cnp_vmax_nh4,10,,1,2,1.5,x\n"
                 "seed_repro_fraction,10,,0.2,0.6,0.4,x\n"
                 "seed_alloc_fraction,10,,0.01,1,0.1,x\n")
    specs = load_param_spec(csv)
    matrix = np.array([[1.5, 0.5, 0.2]])   # vmax, repro=0.5, share=0.2

    m, mm, sk, _ = V.verify_parameter_file_new(1, matrix, specs)
    assert (m, mm, sk) == (3, 0, 0)

    doc["parameters"]["fates_recruit_seed_alloc"]["data"] = pft_arr(9, 0.99)  # corrupt a derived native
    pf.write_text(json.dumps(doc))
    m, mm, sk, mis = V.verify_parameter_file_new(1, matrix, specs)
    assert mm == 1 and "fates_recruit_seed_alloc#p10" in mis[0][1]


def test_generate_multi_pft_groups(tmp_path):
    csv = _write(tmp_path,
                 "seed_repro_fraction,10,,0.2,0.6,0.4,x\n"
                 "seed_alloc_fraction,10,,0.01,1,0.1,x\n"
                 "seed_repro_fraction,12,,0.2,0.999999,0.5,x\n"
                 "seed_alloc_fraction,12,,0.01,1,0.05,x\n")
    mods = build_modifications_list([0.5, 0.2, 0.8, 0.1], param_list_file=csv)
    by_pft = {}
    for m in mods:
        by_pft.setdefault(m["pft"], {})[m["param"]] = m["value"]
    assert by_pft[10]["fates_recruit_seed_alloc"] == pytest.approx(0.1)   # 0.2*0.5
    assert by_pft[12]["fates_recruit_seed_alloc"] == pytest.approx(0.08)  # 0.1*0.8
    assert by_pft[12]["fates_recruit_seed_alloc_mature"] == pytest.approx(0.72)  # 0.9*0.8
