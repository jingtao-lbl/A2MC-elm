"""
test_modify_fates_parameters_json.py — Round-trip tests for v2.100 Chunk 7
JSON modification path.

Validates _create_modified_json() and _modify_json_param() against the
live api-43-1 fates_params_default.json template. Five test cases mirror
the four NC access patterns plus a multi-modification chain to catch
state-management bugs.

Skipped when A2MC_MODEL_PATH is not set (CI-friendly).

Run via:
    python -m unittest tests.test_modify_fates_parameters_json -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# tools.modify_fates_parameters imports netCDF4 at module level; skip cleanly under
# an interpreter without it (e.g. ~/a2mc_env) so `pytest` collection doesn't halt.
import pytest  # noqa: E402
pytest.importorskip("netCDF4")

from tools.modify_fates_parameters import (  # noqa: E402
    create_modified_parameter_file,
    detect_format,
    _create_modified_json,
    _modify_json_param,
)


def _api43_template() -> Path | None:
    """Locate the api-43-1 fates_params_default.json template."""
    model_path = os.environ.get("A2MC_MODEL_PATH")
    if not model_path:
        return None
    p = (Path(model_path) / "components" / "elm" / "src" /
         "external_models" / "fates" / "parameter_files" /
         "fates_params_default.json")
    return p if p.exists() else None


@unittest.skipUnless(_api43_template(),
                     "api-43-1 fates_params_default.json not found "
                     "(A2MC_MODEL_PATH unset or template missing)")
class TestJsonRoundTripAgainstApi43(unittest.TestCase):
    """End-to-end: read template, modify, write, reload, verify."""

    @classmethod
    def setUpClass(cls):
        cls.template = _api43_template()
        with open(cls.template) as f:
            cls.template_doc = json.load(f)

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="json_mod_test_"))
        self.out = self.tmpdir / "case_001" / "fates_params.json"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _reload(self) -> dict:
        with open(self.out) as f:
            return json.load(f)

    def _orig(self, name: str, pft: int = None, organ: int = None) -> float:
        """Read the un-modified value from the template doc."""
        var = self.template_doc["parameters"][name]
        dims = var.get("dims", [])
        data = var["data"]
        if not dims:
            return float(data[0] if isinstance(data, list) else data)
        if dims == ["fates_pft"]:
            return float(data[pft - 1])
        if "fates_plant_organs" in dims and "fates_pft" in dims:
            return float(data[organ - 1][pft - 1])
        raise ValueError(f"don't know how to read {name} with dims={dims}")

    def test_format_detection(self):
        """detect_format on real api-43-1 template -> 'json'."""
        self.assertEqual(detect_format(self.template), "json")

    def test_1d_pft_param_per_pft_modification(self):
        """1D fates_pft param: modify PFT#9 only, confirm other PFTs unchanged."""
        # fates_cnp_eca_km_p is 1D per-PFT in api-43-1
        original_pft9 = self._orig("fates_cnp_eca_km_p", pft=9)
        original_pft7 = self._orig("fates_cnp_eca_km_p", pft=7)
        original_pft10 = self._orig("fates_cnp_eca_km_p", pft=10)

        new_value = original_pft9 * 5  # 5x the default
        _create_modified_json(
            self.template, self.out,
            modifications=[
                {'param': 'fates_cnp_eca_km_p', 'pft': 9, 'value': new_value}
            ],
            verbose=False
        )
        doc = self._reload()
        d = doc["parameters"]["fates_cnp_eca_km_p"]["data"]
        self.assertAlmostEqual(d[8], new_value, places=6)
        self.assertAlmostEqual(d[6], original_pft7, places=6)
        self.assertAlmostEqual(d[9], original_pft10, places=6)

    def test_2d_organ_pft_param(self):
        """2D organ × PFT: modify (organ=1, pft=9), confirm targeted cell + others unchanged."""
        # fates_cnp_turnover_phos_retrans is (fates_plant_organs, fates_pft)
        original = self._orig("fates_cnp_turnover_phos_retrans", pft=9, organ=1)
        new_value = 0.42

        _create_modified_json(
            self.template, self.out,
            modifications=[
                {'param': 'fates_cnp_turnover_phos_retrans',
                 'pft': 9, 'organ': 1, 'value': new_value}
            ],
            verbose=False
        )
        doc = self._reload()
        d = doc["parameters"]["fates_cnp_turnover_phos_retrans"]["data"]
        # Target cell modified
        self.assertAlmostEqual(d[0][8], new_value, places=6)
        # Other organs for PFT#9 unchanged
        self.assertAlmostEqual(d[1][8], self._orig("fates_cnp_turnover_phos_retrans", pft=9, organ=2), places=6)
        # Other PFTs for organ=1 unchanged
        self.assertAlmostEqual(d[0][6], self._orig("fates_cnp_turnover_phos_retrans", pft=7, organ=1), places=6)

    def test_percent_change(self):
        """+50% change applied correctly."""
        original = self._orig("fates_cnp_eca_km_p", pft=10)
        _create_modified_json(
            self.template, self.out,
            modifications=[
                {'param': 'fates_cnp_eca_km_p', 'pft': 10, 'percent': 50.0}
            ],
            verbose=False
        )
        doc = self._reload()
        new_val = doc["parameters"]["fates_cnp_eca_km_p"]["data"][9]
        self.assertAlmostEqual(new_val, original * 1.5, places=6)

    def test_multi_modification_chain(self):
        """Three modifications across different access patterns; all land correctly."""
        mods = [
            {'param': 'fates_cnp_eca_km_p',         'pft': 7,  'value': 0.05},
            {'param': 'fates_cnp_eca_km_p',         'pft': 9,  'value': 0.10},
            {'param': 'fates_cnp_turnover_phos_retrans',
                                                   'pft': 10, 'organ': 1, 'value': 0.30},
        ]
        results = _create_modified_json(
            self.template, self.out, modifications=mods, verbose=False
        )
        self.assertEqual(len(results), 3)
        doc = self._reload()
        d = doc["parameters"]["fates_cnp_eca_km_p"]["data"]
        self.assertAlmostEqual(d[6], 0.05, places=6)
        self.assertAlmostEqual(d[8], 0.10, places=6)
        d2 = doc["parameters"]["fates_cnp_turnover_phos_retrans"]["data"]
        self.assertAlmostEqual(d2[0][9], 0.30, places=6)

    def test_public_dispatcher_routes_json(self):
        """create_modified_parameter_file (public API) auto-routes to JSON path."""
        original = self._orig("fates_cnp_eca_km_p", pft=9)
        # Call PUBLIC api; no format flag — detect_format does the routing
        results = create_modified_parameter_file(
            self.template, self.out,
            modifications=[
                {'param': 'fates_cnp_eca_km_p', 'pft': 9, 'percent': 100.0}
            ],
            verbose=False
        )
        self.assertEqual(len(results), 1)
        doc = self._reload()
        self.assertAlmostEqual(
            doc["parameters"]["fates_cnp_eca_km_p"]["data"][8],
            original * 2.0,
            places=6,
        )
        # Output is JSON
        self.assertEqual(detect_format(self.out), "json")

    def test_unmodified_params_byte_equal(self):
        """Sanity check: params we didn't touch must be byte-equal to the template."""
        _create_modified_json(
            self.template, self.out,
            modifications=[
                {'param': 'fates_cnp_eca_km_p', 'pft': 9, 'value': 99.0}
            ],
            verbose=False
        )
        doc = self._reload()
        params = doc["parameters"]
        # Sample 5 non-touched params; their data must match template
        non_touched = [k for k in params if k != "fates_cnp_eca_km_p"][:5]
        for name in non_touched:
            self.assertEqual(
                params[name]["data"],
                self.template_doc["parameters"][name]["data"],
                f"Non-modified param {name} changed unexpectedly"
            )


class TestErrorPaths(unittest.TestCase):
    """Edge cases that don't require api-43-1 template."""

    def test_unknown_param_raises(self):
        doc = {"parameters": {}}
        with self.assertRaises(ValueError) as ctx:
            _modify_json_param(doc, "fates_nonexistent", pft_index=9,
                               new_value=1.0, verbose=False)
        self.assertIn("not found", str(ctx.exception))

    def test_2d_param_missing_organ_raises(self):
        doc = {"parameters": {"foo": {
            "dims": ["fates_plant_organs", "fates_pft"],
            "data": [[0.0] * 14] * 4,
        }}}
        with self.assertRaises(ValueError) as ctx:
            _modify_json_param(doc, "foo", pft_index=9,  # no organ
                               new_value=1.0, verbose=False)
        self.assertIn("organ", str(ctx.exception))

    def test_missing_value_and_percent_raises(self):
        doc = {"parameters": {"foo": {
            "dims": ["fates_pft"], "data": [0.0] * 14,
        }}}
        with self.assertRaises(ValueError) as ctx:
            _modify_json_param(doc, "foo", pft_index=9, verbose=False)
        self.assertIn("new_value or percent_change", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
