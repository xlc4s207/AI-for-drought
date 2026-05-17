from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "plot_shap_opgd_comparison.py"
SCRIPT_DIR = SCRIPT_PATH.parent
VALIDATION_DIR = SCRIPT_DIR.parent
for path in [SCRIPT_DIR, VALIDATION_DIR]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

SPEC = importlib.util.spec_from_file_location("gleam_plot_shap_opgd_comparison", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TestPlotShapOPGDComparison(unittest.TestCase):
    def test_matrix_from_long_table_respects_row_and_feature_order(self):
        table = pd.DataFrame(
            {
                "metric": ["GPP", "GPP", "RECO"],
                "biome": ["Forest", "Forest", "Forest"],
                "feature": ["b", "a", "a"],
                "value": [2.0, 1.0, 3.0],
            }
        )

        matrix = MODULE.matrix_from_long_table(
            table,
            row_order=[("GPP", "Forest"), ("RECO", "Forest")],
            feature_order=["a", "b"],
            value_col="value",
        )

        np.testing.assert_allclose(matrix, [[1.0, 2.0], [3.0, np.nan]], equal_nan=True)

    def test_top3_flag_matrix_marks_both_and_either(self):
        opgd = pd.DataFrame(
            {
                "metric": ["GPP"] * 3,
                "biome": ["Forest"] * 3,
                "feature": ["a", "b", "c"],
                "q": [0.3, 0.2, 0.1],
            }
        )
        shap = pd.DataFrame(
            {
                "metric": ["GPP"] * 3,
                "biome": ["Forest"] * 3,
                "feature": ["a", "c", "d"],
                "importance": [3.0, 2.0, 1.0],
            }
        )

        flags = MODULE.top3_flag_matrix(
            opgd,
            shap,
            row_order=[("GPP", "Forest")],
            feature_order=["a", "b", "c", "d"],
        )

        self.assertEqual(flags[0, 0], MODULE.TOP3_BOTH)
        self.assertEqual(flags[0, 1], MODULE.TOP3_OPGD_ONLY)
        self.assertEqual(flags[0, 2], MODULE.TOP3_BOTH)
        self.assertEqual(flags[0, 3], MODULE.TOP3_SHAP_ONLY)

    def test_interaction_matrix_is_symmetric(self):
        rows = pd.DataFrame(
            {
                "label_1": ["A", "B"],
                "label_2": ["B", "C"],
                "q_interaction": [0.1, 0.2],
            }
        )

        matrix = MODULE.interaction_matrix(rows, ["A", "B", "C"])

        self.assertEqual(matrix[0, 1], 0.1)
        self.assertEqual(matrix[1, 0], 0.1)
        self.assertEqual(matrix[1, 2], 0.2)
        self.assertTrue(np.isnan(matrix[0, 0]))

    def test_interaction_colormap_uses_green_yellow_red_palette(self):
        cmap = MODULE.interaction_colormap()

        self.assertEqual(cmap.name, "RdYlGn_r")

    def test_continuous_heatmap_colormap_uses_green_yellow_red_palette(self):
        cmap = MODULE.continuous_heatmap_colormap()

        self.assertEqual(cmap.name, "RdYlGn_r")


if __name__ == "__main__":
    unittest.main()
