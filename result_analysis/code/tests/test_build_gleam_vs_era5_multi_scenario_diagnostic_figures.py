import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

import netCDF4 as nc
import numpy as np


MODULE_PATH = Path(
    "/home/xulc/flash_drought/process/result_analysis/code/build_gleam_vs_era5_multi_scenario_diagnostic_figures.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "build_gleam_vs_era5_multi_scenario_diagnostic_figures",
        MODULE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class GLEAMERA5MultiScenarioDiagnosticFigureTests(unittest.TestCase):
    def test_build_scenarios_returns_four_expected_configs(self):
        mod = _load_module()
        scenarios = mod.build_scenarios()
        self.assertEqual(len(scenarios), 4)
        keys = {s.key for s in scenarios}
        self.assertEqual(keys, {"SMrz_flash", "SMs_flash", "SMrz_slow", "SMs_slow"})
        kind_map = {s.key: s.event_kind for s in scenarios}
        self.assertEqual(kind_map["SMrz_flash"], "flash")
        self.assertEqual(kind_map["SMs_flash"], "flash")
        self.assertEqual(kind_map["SMrz_slow"], "slow")
        self.assertEqual(kind_map["SMs_slow"], "slow")

    def test_scenarios_define_soil_variables_for_gleam_and_era5(self):
        mod = _load_module()
        scenarios = {s.key: s for s in mod.build_scenarios()}
        self.assertEqual(scenarios["SMrz_flash"].gleam_var, "SMrz")
        self.assertEqual(scenarios["SMrz_flash"].era5_var, "root_water")
        self.assertEqual(scenarios["SMs_flash"].gleam_var, "SMs")
        self.assertEqual(scenarios["SMs_flash"].era5_var, "swvl1")
        self.assertTrue(scenarios["SMrz_slow"].gleam_event_file.endswith("slow_gt20_drought_events_v5.4.nc"))
        self.assertTrue(scenarios["SMs_flash"].era5_event_file.endswith("flash_lt20_drought_events_v5.4.nc"))

    def test_choose_fallback_pixel_picks_largest_remaining_diff(self):
        mod = _load_module()
        gleam = np.array(
            [
                [0, 2, 1],
                [6, 3, 0],
                [2, 8, 4],
            ],
            dtype=np.int32,
        )
        era5 = np.array(
            [
                [0, 1, 1],
                [0, 1, 0],
                [1, 2, 4],
            ],
            dtype=np.int32,
        )
        used = {(1, 0)}
        picked = mod.choose_fallback_pixel(gleam, era5, used)
        self.assertEqual((picked[0], picked[1]), (2, 1))

    def test_prepare_scenario_summary_contains_required_keys(self):
        mod = _load_module()
        gleam_total = np.array([[5, 2], [0, 3]], dtype=np.int32)
        era5_total = np.array([[1, 1], [0, 1]], dtype=np.int32)
        gleam_aux = {"rapid_total": 3, "flash_total": 7}
        era5_aux = {"rapid_total": 1, "flash_total": 2}
        lat = np.array([-45.0, 35.0], dtype=np.float32)
        summary = mod.prepare_scenario_summary(
            key="SMrz_flash",
            title_cn="根系骤旱",
            gleam_total=gleam_total,
            era5_total=era5_total,
            lat=lat,
            gleam_aux=gleam_aux,
            era5_aux=era5_aux,
        )
        for name in [
            "key",
            "title_cn",
            "gleam_total_events",
            "era5_total_events",
            "gleam_active_pixels",
            "era5_active_pixels",
            "diff_breakdown",
            "lat_band_rows",
        ]:
            self.assertIn(name, summary)
        self.assertEqual(summary["gleam_total_events"], 10)
        self.assertEqual(summary["era5_total_events"], 3)
        self.assertEqual(summary["gleam_aux"]["rapid_total"], 3)

    def test_summarize_event_metrics_reads_flash_metrics_from_netcdf(self):
        mod = _load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            nc_path = Path(tmpdir) / "flash.nc"
            with nc.Dataset(nc_path, "w") as ds:
                ds.createDimension("event", 4)
                duration = ds.createVariable("duration", "i4", ("event",), fill_value=-9999)
                days_below = ds.createVariable("days_below_p20", "i4", ("event",), fill_value=-9999)
                intensity = ds.createVariable("intensity", "f4", ("event",), fill_value=np.nan)
                onset = ds.createVariable("onset_days", "i4", ("event",), fill_value=-9999)
                duration[:] = np.array([10, 15, -9999, 0], dtype=np.int32)
                days_below[:] = np.array([8, 12, -9999, 0], dtype=np.int32)
                intensity[:] = np.array([1.5, 2.5, np.nan, 0.5], dtype=np.float32)
                onset[:] = np.array([3, 8, -9999, 0], dtype=np.int32)

            summary = mod.summarize_event_metrics(str(nc_path), "flash")
            self.assertAlmostEqual(summary["duration"]["mean"], 12.5)
            self.assertAlmostEqual(summary["days_below_p20"]["median"], 10.0)
            self.assertAlmostEqual(summary["intensity"]["mean"], 1.5)
            self.assertAlmostEqual(summary["onset_days"]["median"], 5.5)


if __name__ == "__main__":
    unittest.main()
