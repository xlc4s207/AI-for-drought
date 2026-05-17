import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd


MODULE_PATH = Path("/home/xulc/flash_drought/process/result_analysis/code/plot_drought_annual_lineplots.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("plot_drought_annual_lineplots", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DroughtAnnualLineplotTests(unittest.TestCase):
    def test_scenario_builder_returns_four_scenarios(self):
        mod = _load_module()
        scenarios = mod.build_scenarios()
        self.assertEqual(len(scenarios), 4)
        labels = {(s.soil_layer, s.drought_type) for s in scenarios}
        self.assertEqual(labels, {("SMs", "flash"), ("SMs", "nonflash"), ("SMrz", "flash"), ("SMrz", "nonflash")})

    def test_metric_specs_cover_four_requested_metrics(self):
        mod = _load_module()
        self.assertEqual(set(mod.METRIC_SPECS.keys()), {"frequency", "duration", "intensity", "onset_days"})
        self.assertEqual(mod.METRIC_SPECS["frequency"].source_var, "mean_annual_frequency")
        self.assertEqual(mod.METRIC_SPECS["duration"].source_var, "duration")

    def test_annual_mean_aggregator_groups_values_by_year(self):
        mod = _load_module()
        years = np.array([1980, 1980, 1981, 1981, 1981, 1982, -1], dtype=np.int16)
        values = np.array([1.0, 3.0, 2.0, np.nan, 4.0, 5.0, 6.0], dtype=np.float64)
        out = mod.aggregate_event_metric_by_year(years, values, 1980, 1982)
        expected = {1980: 2.0, 1981: 3.0, 1982: 5.0}
        self.assertEqual(out, expected)

    def test_merge_helper_preserves_expected_columns(self):
        mod = _load_module()
        df = mod.build_metric_dataframe(
            scenario_cn="SMs-骤旱",
            soil_layer="SMs",
            drought_type="flash",
            metric_name="duration",
            metric_cn="持续时间",
            annual_values={1980: 10.0, 1981: 12.0},
        )
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(
            list(df.columns),
            ["soil_layer", "drought_type", "scenario_cn", "metric", "metric_cn", "year", "value"],
        )
        self.assertEqual(df["scenario_cn"].nunique(), 1)
        self.assertEqual(df["metric"].iloc[0], "duration")

    def test_filter_years_excludes_1980_and_2024(self):
        mod = _load_module()
        df = pd.DataFrame(
            {
                "soil_layer": ["SMs"] * 4,
                "drought_type": ["flash"] * 4,
                "scenario_cn": ["SMs-骤旱"] * 4,
                "metric": ["frequency"] * 4,
                "metric_cn": ["频率"] * 4,
                "year": [1980, 1981, 2023, 2024],
                "value": [1.0, 2.0, 3.0, 4.0],
            }
        )
        filtered = mod.filter_plot_years(df)
        self.assertEqual(filtered["year"].tolist(), [1981, 2023])

    def test_centered_smooth5_computes_rolling_mean(self):
        mod = _load_module()
        df = pd.DataFrame(
            {
                "soil_layer": ["SMs"] * 6,
                "drought_type": ["flash"] * 6,
                "scenario_cn": ["SMs-骤旱"] * 6,
                "metric": ["duration"] * 6,
                "metric_cn": ["持续时间"] * 6,
                "year": [1980, 1982, 1983, 1984, 1985, 1986],
                "value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            }
        )
        smoothed = mod.add_centered_rolling_mean(df, window=5)
        self.assertIn("smoothed_5yr", smoothed.columns)
        expected = [2.0, 2.5, 3.0, 4.0, 4.5, 5.0]
        self.assertTrue(np.allclose(smoothed["smoothed_5yr"].to_numpy(), np.array(expected), equal_nan=True))

    def test_nonflash_mask_keeps_only_slow_onset_events(self):
        mod = _load_module()
        years = np.array([1981, 1981, 1982, 1983, 1984, 1979, 2025], dtype=np.int16)
        onset_days = np.array([25.0, -1.0, 18.0, 40.0, np.nan, 30.0, 35.0], dtype=np.float64)
        scenario = mod.Scenario("SMs", "nonflash", "/tmp/nonflash.nc")

        mask = mod.build_event_mask(years, onset_days, scenario, 1980, 2024)

        self.assertTrue(np.array_equal(mask, np.array([True, False, False, True, False, False, False])))

    def test_flash_mask_keeps_only_valid_flash_onset_window(self):
        mod = _load_module()
        years = np.array([1981, 1981, 1982, 1983, 1984], dtype=np.int16)
        onset_days = np.array([5.0, 12.0, 20.0, 21.0, -1.0], dtype=np.float64)
        scenario = mod.Scenario("SMrz", "flash", "/tmp/flash.nc")

        mask = mod.build_event_mask(years, onset_days, scenario, 1980, 2024)

        self.assertTrue(np.array_equal(mask, np.array([True, True, True, False, False])))


if __name__ == "__main__":
    unittest.main()
