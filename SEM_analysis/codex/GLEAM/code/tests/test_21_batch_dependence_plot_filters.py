from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "21_batch_dependence_plots_fast.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_batch_dependence_fast_filters", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TestBatchDependencePlotFilters(unittest.TestCase):
    def test_filter_plotting_outliers_removes_duration_and_intensity_extremes(self):
        sample = pd.DataFrame(
            {
                "event_duration": [200.0, 1500.0, 300.0, 20.0],
                "event_intensity": [4.0, 3.0, 60.0, 10.0],
                "prepeak_ssrd_mean": [1.0, 2.0, 3.0, 4.0],
            },
            index=[10, 11, 12, 13],
        )
        shap_df = pd.DataFrame(
            {
                "event_duration": [0.1, 0.2, 0.3, 0.4],
                "event_intensity": [0.1, 0.2, 0.3, 0.4],
                "prepeak_ssrd_mean": [0.4, 0.3, 0.2, 0.1],
            },
            index=[10, 11, 12, 13],
        )

        filtered_sample, filtered_shap = MODULE.filter_plotting_outliers(
            sample,
            shap_df,
            event_duration_max=1000.0,
            event_intensity_max=50.0,
        )

        self.assertListEqual(filtered_sample.index.tolist(), [10, 13])
        self.assertListEqual(filtered_shap.index.tolist(), [10, 13])

    def test_filter_local_vertical_shap_outliers_removes_deep_negative_tail_at_repeated_value(self):
        values = [1.0] * 80 + [1.0] * 6 + [0.8 + i * 0.01 for i in range(40)] + [1.2 + i * 0.01 for i in range(40)]
        shap_values = [0.8] * 80 + [-6.0, -5.8, -5.5, -5.1, -4.9, -4.7] + [0.5] * 40 + [1.0] * 40

        filtered_x, filtered_y, removed = MODULE.filter_local_vertical_shap_outliers(
            MODULE.np.asarray(values, dtype=float),
            MODULE.np.asarray(shap_values, dtype=float),
        )

        self.assertGreaterEqual(removed, 6)
        self.assertEqual(len(filtered_x), len(values) - removed)
        self.assertGreater(filtered_y.min(), -4.0)

    def test_filter_local_vertical_shap_outliers_keeps_regular_monotonic_pattern(self):
        values = MODULE.np.linspace(0.0, 10.0, 200)
        shap_values = 0.4 * values - 2.0

        filtered_x, filtered_y, removed = MODULE.filter_local_vertical_shap_outliers(
            values,
            shap_values,
        )

        self.assertEqual(removed, 0)
        self.assertEqual(len(filtered_x), len(values))
        self.assertEqual(len(filtered_y), len(shap_values))

    def test_filter_local_vertical_shap_outliers_removes_dense_group_shifted_below_neighbors(self):
        values = (
            [0.96] * 20
            + [0.98] * 20
            + [1.00] * 60
            + [1.02] * 20
            + [1.04] * 20
        )
        shap_values = (
            [0.2] * 20
            + [0.1] * 20
            + [-8.0, -7.8, -7.5, -7.1, -6.9, -6.5, -6.2, -5.9, -5.6, -5.2] * 6
            + [0.0] * 20
            + [0.3] * 20
        )

        filtered_x, filtered_y, removed = MODULE.filter_local_vertical_shap_outliers(
            MODULE.np.asarray(values, dtype=float),
            MODULE.np.asarray(shap_values, dtype=float),
        )

        self.assertGreaterEqual(removed, 50)
        self.assertEqual(len(filtered_x), len(values) - removed)
        self.assertGreater(filtered_y.min(), -2.0)

    def test_filter_local_vertical_shap_outliers_removes_dense_group_shifted_above_neighbors(self):
        values = (
            [0.96] * 20
            + [0.98] * 20
            + [1.00] * 60
            + [1.02] * 20
            + [1.04] * 20
        )
        shap_values = (
            [-0.2] * 20
            + [0.0] * 20
            + [5.2, 5.6, 5.9, 6.2, 6.5, 6.9, 7.1, 7.5, 7.8, 8.0] * 6
            + [0.1] * 20
            + [0.3] * 20
        )

        filtered_x, filtered_y, removed = MODULE.filter_local_vertical_shap_outliers(
            MODULE.np.asarray(values, dtype=float),
            MODULE.np.asarray(shap_values, dtype=float),
        )

        self.assertGreaterEqual(removed, 50)
        self.assertEqual(len(filtered_x), len(values) - removed)
        self.assertLess(filtered_y.max(), 2.0)


if __name__ == "__main__":
    unittest.main()
