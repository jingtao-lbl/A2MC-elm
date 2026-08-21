"""
test_generic_obs_comparison.py — generic observation↔simulation comparison (docs/24).

Covers the snapshot + time-series unification and user-selectable cost functions:
  - Target observation model (scalar back-compat; snapshot/series n_points & obs_values)
  - targets.yaml parsing (snapshot synthesis, obs_months window, series, cost_method)
  - resolve_obs_index_windows (snapshot / series / legacy fallback)
  - to_cost skill-score orientation (nse/kge/correlation flipped; error metrics pass-through)
  - extract_case_series vs legacy extract_case_values consistency (synthetic NC)
  - optimize_ensemble end-to-end: snapshot AND time-series(nse) rank the exact-match case
  - generic loader: yaml-loaded Kougarok targets match the canonical .txt values

NC-backed tests are skipped when netCDF4 is unavailable (CI-friendly).

Run:
    python -m unittest tests.test_generic_obs_comparison -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from tools.optimize_function import Target, ObsPoint, optimize_ensemble, OptimizationConfig
from tools.cost_functions import to_cost, SKILL_SCORE_METHODS
from tools.evaluate_case import resolve_obs_index_windows
from tools.validate_targets_config import validate_targets_config

try:
    import netCDF4 as nc  # noqa: F401
    HAS_NETCDF = True
except ImportError:
    HAS_NETCDF = False

YEAR_START = 1901


class TestObservationModel(unittest.TestCase):
    def test_scalar_backcompat(self):
        t = Target(name="x", observed=24.6)
        self.assertEqual(t.n_points, 1)
        self.assertFalse(t.is_time_series)
        self.assertEqual(list(t.obs_values), [24.6])

    def test_series_shape(self):
        t = Target(name="g", observations=[ObsPoint(2016, 6, 1.2), ObsPoint(2016, 7, 3.4)])
        self.assertEqual(t.n_points, 2)
        self.assertTrue(t.is_time_series)
        self.assertEqual(list(t.obs_values), [1.2, 3.4])


class TestMatchResolver(unittest.TestCase):
    def test_snapshot_window(self):
        t = Target(name="x", observed=1.0, observations=[ObsPoint(2016, 7, 1.0)])
        self.assertEqual(resolve_obs_index_windows(t, YEAR_START), [[(2016 - YEAR_START) * 12 + 6]])

    def test_series_with_window(self):
        t = Target(name="g", observations=[ObsPoint(2016, 6, 1.0), ObsPoint(2016, 7, 2.0, months=[7, 8])])
        base = (2016 - YEAR_START) * 12
        self.assertEqual(resolve_obs_index_windows(t, YEAR_START), [[base + 5], [base + 6, base + 7]])

    def test_legacy_none(self):
        self.assertIsNone(resolve_obs_index_windows(Target(name="x", observed=1.0), YEAR_START))


class TestToCost(unittest.TestCase):
    def test_skill_scores_flipped(self):
        for m in SKILL_SCORE_METHODS:
            self.assertAlmostEqual(to_cost(1.0, m), 0.0)   # perfect skill -> zero cost
            self.assertAlmostEqual(to_cost(0.0, m), 1.0)

    def test_error_metrics_passthrough(self):
        self.assertEqual(to_cost(0.3, "relative_error"), 0.3)
        self.assertEqual(to_cost(1.7, "rmse"), 1.7)


class TestYamlLoaderRegression(unittest.TestCase):
    """The generic yaml loader must reproduce the canonical Kougarok target values."""

    def setUp(self):
        self.kdir = _REPO_ROOT / "use_cases" / "ELM-FATES_Kougarok"
        if not (self.kdir / "validation" / "targets.yaml").exists():
            self.skipTest("Kougarok targets.yaml not present")

    def test_yaml_matches_canonical(self):
        from tools.targets_loader import parse_targets_yaml, parse_time_anchor
        ypath = self.kdir / "validation" / "targets.yaml"
        targets = parse_targets_yaml(ypath)
        # canonical values from validation_targets_leafroot.txt (api-43 PFT ids:
        # evergreen=PFT10, deciduous=PFT11, graminoid=PFT12; were 7/9/10 on api-31)
        canonical = {
            "PFT10_leaf": 24.6, "PFT10_fineroot": 174.2,
            "PFT11_leaf": 124.7, "PFT11_fineroot": 187.3,
            "PFT12_leaf": 82.7, "PFT12_fineroot": 382.1,
        }
        self.assertEqual(set(targets), set(canonical))
        for name, obs in canonical.items():
            self.assertAlmostEqual(targets[name].observed, obs, places=6)
            self.assertEqual(targets[name].n_points, 1)  # Kougarok is snapshot
        self.assertEqual(parse_time_anchor(ypath), (2016, 7))


@unittest.skipUnless(HAS_NETCDF, "netCDF4 required")
class TestExtractionAndScreening(unittest.TestCase):
    def setUp(self):
        from tools.fates_utils import get_szpf_range
        self.d = Path(tempfile.mkdtemp())
        self.s7, self.e7 = get_szpf_range(7)
        self.nb = self.e7 - self.s7 + 1
        self.n_t = 1500
        self.jul = (2016 - YEAR_START) * 12 + 6   # 1386
        self.aug = self.jul + 1
        # 3 cases; July leaf = 20 / 24.6(exact) / 30 ; Aug = 20 / 40 / 30
        self._mk(1, 20, 20); self._mk(2, 24.6, 40); self._mk(3, 30, 30)

    def _mk(self, case, julv, augv):
        import netCDF4 as nc
        p = self.d / f"En{case}_TRANS_all_variables_monthly_1901_2019.nc"
        ds = nc.Dataset(str(p), "w")
        ds.createDimension("szpf", 156); ds.createDimension("time", self.n_t)
        v = ds.createVariable("FATES_LEAFC_SZPF", "f8", ("szpf", "time"))
        a = np.zeros((156, self.n_t))
        a[self.s7:self.e7 + 1, self.jul] = julv / 1000 / self.nb
        a[self.s7:self.e7 + 1, self.aug] = augv / 1000 / self.nb
        v[:] = a; ds.close()

    def _config(self):
        from phases.phase2_screening.screen_ensemble import ScreeningConfig
        return ScreeningConfig(case_pattern="En{N}_{PHASE}", data_dir=self.d)

    def test_scalar_wrapper_matches_series(self):
        from tools.evaluate_case import extract_case_values, extract_case_series
        ncf = self.d / "En2_TRANS_all_variables_monthly_1901_2019.nc"
        t = {"PFT7_leaf": Target("PFT7_leaf", observed=24.6)}
        scalar = extract_case_values(ncf, t, self.jul)["PFT7_leaf"]
        series = extract_case_series(ncf, t, {"PFT7_leaf": [[self.jul]]})["PFT7_leaf"]
        self.assertEqual(series.shape, (1,))
        self.assertAlmostEqual(scalar, float(series[0]))

    def test_snapshot_ranks_exact_match(self):
        from phases.phase2_screening.screen_ensemble import load_ensemble_simulated
        cfg = self._config()
        targets = {"PFT7_leaf": Target("PFT7_leaf", observed=24.6,
                                       observations=[ObsPoint(2016, 7, 24.6)])}
        sim, cn = load_ensemble_simulated(self.d, targets, cfg, verbose=False, use_cache=False)
        self.assertEqual(sim["PFT7_leaf"].shape, (3, 1))
        res = optimize_ensemble(sim, targets, OptimizationConfig(verbose=False))
        res.case_numbers = np.asarray(cn)
        self.assertEqual(res.best_set_id, 2)

    def test_timeseries_nse_ranks_exact_match(self):
        from phases.phase2_screening.screen_ensemble import load_ensemble_simulated
        cfg = self._config()
        targets = {"PFT7_leaf": Target("PFT7_leaf", cost_method="nse",
                                       observations=[ObsPoint(2016, 7, 24.6), ObsPoint(2016, 8, 40.0)])}
        sim, cn = load_ensemble_simulated(self.d, targets, cfg, verbose=False, use_cache=False)
        self.assertEqual(sim["PFT7_leaf"].shape, (3, 2))
        res = optimize_ensemble(sim, targets, OptimizationConfig(verbose=False))
        res.case_numbers = np.asarray(cn)
        self.assertEqual(res.best_set_id, 2)   # exact match -> NSE 1.0 -> cost 0


class TestTargetsValidator(unittest.TestCase):
    """Pre-flight validator catches the documented config pitfalls."""

    def _codes(self, yaml_str: str, **kw):
        d = Path(tempfile.mkdtemp())
        p = d / "targets.yaml"
        p.write_text(yaml_str)
        kw.setdefault("year_start", 1901)
        kw.setdefault("year_end", 2019)
        return {(f.level, f.code) for f in validate_targets_config(p, **kw)}

    def test_clean_kougarok(self):
        ypath = _REPO_ROOT / "use_cases" / "ELM-FATES_Kougarok" / "validation" / "targets.yaml"
        if not ypath.exists():
            self.skipTest("Kougarok targets.yaml not present")
        errs = [f for f in validate_targets_config(ypath, year_start=1901, year_end=2019)
                if f.level == "ERROR"]
        self.assertEqual(errs, [], f"Kougarok config should validate clean; got {errs}")

    def test_schema_neither(self):  # S1
        y = "time_year: 2016\ntime_month: 7\ntargets:\n  PFT7_leaf: {}\n"
        self.assertIn(("ERROR", "S1"), self._codes(y))

    def test_snapshot_no_anchor(self):  # S3
        y = "targets:\n  PFT7_leaf: {observed: 24.6}\n"
        self.assertIn(("ERROR", "S3"), self._codes(y))

    def test_both_forms(self):  # S2
        y = ("time_year: 2016\ntime_month: 7\ntargets:\n"
             "  PFT7_leaf:\n    observed: 24.6\n    observations: [{year: 2016, month: 7, value: 24.6}]\n")
        self.assertIn(("WARN", "S2"), self._codes(y))

    def test_unresolvable_name(self):  # R1
        y = "time_year: 2016\ntime_month: 7\ntargets:\n  BADNAME: {observed: 1.0}\n"
        self.assertIn(("ERROR", "R1"), self._codes(y))

    def test_skill_score_arity(self):  # A1
        y = ("time_year: 2016\ntime_month: 7\ntargets:\n"
             "  PFT7_leaf: {observed: 24.6, cost_method: nse}\n")
        self.assertIn(("ERROR", "A1"), self._codes(y))

    def test_bad_methods(self):  # C1, C2, C3
        y = ("time_year: 2016\ntime_month: 7\n"
             "cost_config: {error_method: nope, aggregation_method: nah}\ntargets:\n"
             "  PFT7_leaf: {observed: 24.6, cost_method: alsobad}\n")
        codes = self._codes(y)
        self.assertIn(("ERROR", "C1"), codes)
        self.assertIn(("ERROR", "C2"), codes)
        self.assertIn(("ERROR", "C3"), codes)

    def test_time_range(self):  # T1, T2, T3
        bad_month = ("time_year: 2016\ntime_month: 7\ntargets:\n"
                     "  PFT7_leaf: {observations: [{year: 2016, month: 13, value: 1}]}\n")
        self.assertIn(("ERROR", "T1"), self._codes(bad_month))
        before = ("time_year: 2016\ntime_month: 7\ntargets:\n"
                  "  PFT7_leaf: {observations: [{year: 1800, month: 7, value: 1}]}\n")
        self.assertIn(("ERROR", "T2"), self._codes(before))
        after = ("time_year: 2016\ntime_month: 7\ntargets:\n"
                 "  PFT7_leaf: {observations: [{year: 2030, month: 7, value: 1}]}\n")
        self.assertIn(("ERROR", "T3"), self._codes(after))

    def test_relative_nonpositive(self):  # V1
        y = "time_year: 2016\ntime_month: 7\ntargets:\n  PFT7_leaf: {observed: -5.0}\n"
        self.assertIn(("ERROR", "V1"), self._codes(y))

    def test_scale_mix(self):  # M1
        y = ("time_year: 2016\ntime_month: 7\n"
             "cost_config: {error_method: relative_error, aggregation_method: rmsre}\ntargets:\n"
             "  PFT7_leaf: {observed: 24.6}\n  PFT9_leaf: {observed: 124.7, cost_method: rmse}\n")
        self.assertIn(("WARN", "M1"), self._codes(y))


if __name__ == "__main__":
    unittest.main(verbosity=2)
