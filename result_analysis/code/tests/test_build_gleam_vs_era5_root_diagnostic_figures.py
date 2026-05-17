import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np


MODULE_PATH = Path(
    "/home/xulc/flash_drought/process/result_analysis/code/build_gleam_vs_era5_root_diagnostic_figures.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "build_gleam_vs_era5_root_diagnostic_figures",
        MODULE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class GLEAMERA5RootDiagnosticFigureTests(unittest.TestCase):
    def test_compute_diff_source_breakdown_separates_zero_and_shared_cases(self):
        mod = _load_module()
        gleam = np.array([[5, 3, 1], [0, 4, 2]], dtype=np.int32)
        era5 = np.array([[0, 1, 2], [0, 4, 1]], dtype=np.int32)

        out = mod.compute_diff_source_breakdown(gleam, era5)

        self.assertEqual(out["gleam_gt0_era5_eq0_pixels"], 1)
        self.assertEqual(out["gleam_gt0_era5_eq0_diff_sum"], 5)
        self.assertEqual(out["gleam_gt_era5_and_era5_gt0_pixels"], 2)
        self.assertEqual(out["gleam_gt_era5_and_era5_gt0_diff_sum"], 3)
        self.assertEqual(out["total_positive_diff_sum"], 8)

    def test_summarize_lat_band_diff_groups_by_latitude(self):
        mod = _load_module()
        gleam = np.array(
            [
                [5, 1],
                [3, 0],
                [1, 4],
                [2, 2],
            ],
            dtype=np.int32,
        )
        era5 = np.array(
            [
                [1, 1],
                [1, 0],
                [1, 1],
                [0, 2],
            ],
            dtype=np.int32,
        )
        lat = np.array([-75.0, -15.0, 35.0, 75.0], dtype=np.float32)
        bands = [(-90, -30), (-30, 30), (30, 90)]

        rows = mod.summarize_lat_band_diff(gleam, era5, lat, bands)

        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["gleam_total"], 6)
        self.assertEqual(rows[0]["era5_total"], 2)
        self.assertEqual(rows[0]["diff_total"], 4)
        self.assertEqual(rows[1]["diff_total"], 2)
        self.assertEqual(rows[2]["diff_total"], 5)

    def test_select_typical_pixels_picks_expected_categories(self):
        mod = _load_module()
        gleam = np.zeros((6, 3), dtype=np.int32)
        era5 = np.zeros((6, 3), dtype=np.int32)
        lat = np.array([-65.0, -40.0, -5.0, 12.0, 45.0, 72.0], dtype=np.float32)
        lon = np.array([10.0, 20.0, 30.0], dtype=np.float32)

        gleam[5, 1] = 40
        gleam[4, 2] = 25
        gleam[3, 0] = 18
        gleam[2, 2] = 14

        era5[5, 1] = 0
        era5[4, 2] = 0
        era5[3, 0] = 0
        era5[2, 2] = 5

        picks = mod.select_typical_pixels(gleam, era5, lat, lon)

        self.assertEqual(picks["high_lat_hotspot"].lat_idx, 5)
        self.assertEqual(picks["high_lat_hotspot"].lon_idx, 1)
        self.assertEqual(picks["mid_lat_hotspot"].lat_idx, 4)
        self.assertEqual(picks["mid_lat_hotspot"].lon_idx, 2)
        self.assertEqual(picks["tropical_hotspot"].lat_idx, 3)
        self.assertEqual(picks["tropical_hotspot"].lon_idx, 0)
        self.assertEqual(picks["shared_nonzero"].lat_idx, 2)
        self.assertEqual(picks["shared_nonzero"].lon_idx, 2)

    def test_choose_focus_window_spans_selected_events_with_padding(self):
        mod = _load_module()
        events = [
            {"start_idx": 100, "end_idx": 150},
            {"start_idx": 420, "end_idx": 470},
        ]

        start, end = mod.choose_focus_window(events, pad_days=20, series_len=600)

        self.assertEqual(start, 80)
        self.assertEqual(end, 490)

    def test_choose_focus_window_supports_ordinal_events(self):
        mod = _load_module()
        series_start_ord = 730120
        events = [
            {"start_ord": series_start_ord + 100, "end_ord": series_start_ord + 150},
            {"start_ord": series_start_ord + 420, "end_ord": series_start_ord + 470},
        ]

        start, end = mod.choose_focus_window(
            events,
            pad_days=20,
            series_len=600,
            series_start_ord=series_start_ord,
        )

        self.assertEqual(start, 80)
        self.assertEqual(end, 490)


if __name__ == "__main__":
    unittest.main()
