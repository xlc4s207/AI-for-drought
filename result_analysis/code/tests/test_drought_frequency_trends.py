import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np


MODULE_PATH = Path("/home/xulc/flash_drought/process/result_analysis/code/analyze_drought_frequency_trends.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("analyze_drought_frequency_trends", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DroughtFrequencyTrendTests(unittest.TestCase):
    def test_accumulate_annual_event_counts_counts_events_per_pixel_year(self):
        mod = _load_module()

        years = np.array(
            [
                [[1980, 1981]],
                [[1980, 1982]],
                [[np.nan, 1981]],
            ],
            dtype=np.float64,
        )

        counts = mod.accumulate_annual_event_counts(years, 1980, 1982)

        expected = np.array(
            [
                [[2, 0]],
                [[0, 2]],
                [[0, 1]],
            ],
            dtype=np.int16,
        )
        np.testing.assert_array_equal(counts, expected)

    def test_compute_frequency_regression_uses_zero_years_and_threshold(self):
        mod = _load_module()

        year_axis = np.arange(1980, 1984, dtype=np.float64)
        annual_counts = np.array(
            [
                [[0, 2]],
                [[1, 2]],
                [[2, 2]],
                [[3, 2]],
            ],
            dtype=np.float64,
        )
        total_events = np.array([[6, 2]], dtype=np.float64)

        stat = mod.compute_frequency_regression(
            year_axis=year_axis,
            annual_counts=annual_counts,
            total_events=total_events,
            min_total_events=3,
        )

        np.testing.assert_allclose(stat["slope"][0, 0], 1.0, atol=1e-6)
        np.testing.assert_allclose(stat["mean"][0, 0], 1.5, atol=1e-6)
        self.assertTrue(np.isnan(stat["slope"][0, 1]))


if __name__ == "__main__":
    unittest.main()
