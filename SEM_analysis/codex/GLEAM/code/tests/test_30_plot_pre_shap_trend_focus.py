from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "30_plot_pre_shap_trend_focus.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_pre_shap_trend_focus", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TestPreShapTrendFocus(unittest.TestCase):
    def test_build_binned_summary_returns_ordered_bins(self):
        frame = pd.DataFrame(
            {
                "pre": [0.001, 0.0015, 0.002, 0.003, 0.004, 0.006, 0.008, 0.010],
                "pre_shap": [-5.0, -4.0, -2.0, 1.0, 3.0, 2.0, 0.5, -1.0],
                "gpp_drop_magnitude": [0.3, 0.4, 0.5, 1.0, 1.5, 1.3, 1.1, 0.8],
            }
        )

        result = MODULE.build_binned_summary(
            frame,
            x_col="pre",
            y_col="pre_shap",
            color_col="gpp_drop_magnitude",
            n_bins=4,
            min_count=1,
        )

        self.assertFalse(result.empty)
        self.assertTrue(result["x_mid"].is_monotonic_increasing)
        self.assertIn("y_q25", result.columns)
        self.assertIn("color_median", result.columns)

    def test_build_group_curves_keeps_groups_separate(self):
        frame = pd.DataFrame(
            {
                "pre": [0.001, 0.0015, 0.002, 0.004, 0.005, 0.006],
                "pre_shap": [-6.0, -4.0, -2.0, 1.0, 2.0, 3.0],
                "mechanism_group": [
                    "expected_mild",
                    "expected_mild",
                    "expected_mild",
                    "expected_severe",
                    "expected_severe",
                    "expected_severe",
                ],
            }
        )

        result = MODULE.build_group_curves(
            frame,
            x_col="pre",
            y_col="pre_shap",
            group_col="mechanism_group",
            n_bins=2,
            min_count=1,
        )

        self.assertIn("expected_mild", set(result["mechanism_group"]))
        self.assertIn("expected_severe", set(result["mechanism_group"]))


if __name__ == "__main__":
    unittest.main()
