from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "52_plot_gpp_reco_dependence_comparison.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_gpp_reco_dependence_comparison", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TestGppRecoDependenceComparison(unittest.TestCase):
    def test_comparison_feature_list_covers_all_prepeak_inputs(self):
        self.assertEqual(len(MODULE.COMPARISON_FEATURES), 12)
        self.assertIn("prepeak_total_precipitation_mean", MODULE.COMPARISON_FEATURES)
        self.assertIn("event_intensity", MODULE.COMPARISON_FEATURES)

    def test_output_path_groups_by_biome_and_short_label(self):
        path = MODULE.comparison_output_path("Forest", "prepeak_total_precipitation_mean")

        self.assertTrue(str(path).endswith("dependence_compare_gpp_vs_reco/Forest/PRE_gpp_vs_reco.png"))

    def test_combined_output_path_groups_one_large_figure_per_biome(self):
        path = MODULE.combined_output_path("Forest")

        self.assertTrue(str(path).endswith("dependence_compare_gpp_vs_reco/combined_by_biome/Forest_all_features_gpp_vs_reco.png"))

    def test_combined_layout_has_feature_rows_and_metric_columns(self):
        nrows, ncols = MODULE.combined_layout_shape()

        self.assertEqual(nrows, len(MODULE.COMBINED_FEATURES))
        self.assertEqual(ncols, 2)

    def test_combined_feature_list_excludes_onset_and_intensity(self):
        self.assertNotIn("event_onset_days", MODULE.COMBINED_FEATURES)
        self.assertNotIn("event_intensity", MODULE.COMBINED_FEATURES)
        self.assertIn("event_duration", MODULE.COMBINED_FEATURES)
        self.assertEqual(len(MODULE.COMBINED_FEATURES), 10)

    def test_plotted_x_limits_use_color_clipped_points_with_small_padding(self):
        xlim = MODULE.plotted_x_limits(
            [
                (np.array([0.0, 1.0, 2.0, 100.0]), np.array([np.nan, 1.0, 2.0, np.nan])),
                (np.array([1.5, 2.5, 200.0]), np.array([1.5, 2.5, np.nan])),
            ]
        )

        self.assertAlmostEqual(xlim[0], 0.955)
        self.assertAlmostEqual(xlim[1], 2.545)

    def test_feature_color_values_can_keep_extremes_for_combined_plots(self):
        x = np.array([0.0, 1.0, 2.0, 100.0], dtype=float)

        color = MODULE.feature_color_values(x, clip_tails=False)

        np.testing.assert_allclose(color, x)

    def test_feature_color_values_clips_tails_by_default_for_single_feature_plots(self):
        x = np.array([0.0, 1.0, 2.0, 100.0], dtype=float)

        color = MODULE.feature_color_values(x, clip_tails=True)

        self.assertTrue(np.isnan(color[0]))
        self.assertTrue(np.isnan(color[-1]))
        self.assertTrue(np.isfinite(color[1:-1]).all())

    def test_combined_cropland_and_forest_use_clipped_tails(self):
        self.assertTrue(MODULE.combined_clip_tails_for_biome("Cropland"))
        self.assertTrue(MODULE.combined_clip_tails_for_biome("Forest"))

    def test_other_combined_biomes_keep_full_range(self):
        self.assertFalse(MODULE.combined_clip_tails_for_biome("Grassland"))
        self.assertFalse(MODULE.combined_clip_tails_for_biome("Savanna"))
        self.assertFalse(MODULE.combined_clip_tails_for_biome("Shrubland"))

    def test_combined_figures_disable_feature_color_mapping(self):
        self.assertFalse(MODULE.COMBINED_USE_COLOR_MAPPING)


if __name__ == "__main__":
    unittest.main()
