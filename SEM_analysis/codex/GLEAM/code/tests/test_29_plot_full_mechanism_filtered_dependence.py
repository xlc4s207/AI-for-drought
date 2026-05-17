from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "29_plot_full_mechanism_filtered_dependence.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_full_mechanism_plot", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TestFullMechanismFilteredDependencePlot(unittest.TestCase):
    def test_ensure_color_column_can_derive_from_ampmax(self):
        frame = pd.DataFrame({"amp_max": [-2.0, -0.5, 1.0]})

        result = MODULE.ensure_color_column(frame, "gpp_drop_magnitude")

        self.assertIn("gpp_drop_magnitude", result.columns)
        self.assertListEqual(result["gpp_drop_magnitude"].round(6).tolist(), [2.0, 0.5, 0.0])

    def test_compute_color_limits_uses_quantiles(self):
        series = pd.Series([1, 2, 3, 4, 100])

        low, high = MODULE.compute_color_limits(series, q_low=0.05, q_high=0.95)

        self.assertGreaterEqual(low, 1.0)
        self.assertLess(high, 100.0)
        self.assertGreater(high, low)

    def test_summarize_biome_returns_group_rows(self):
        full_df = pd.DataFrame(
            {
                "recoverywin_total_precipitation_mean": [0.001, 0.002, 0.005, 0.006],
                "pre_shap": [-2.0, -1.0, 1.5, 2.5],
                "gpp_drop_magnitude": [0.2, 0.4, 1.8, 2.2],
                "mechanism_group": ["background", "background", "background", "background"],
            }
        )
        filtered_df = pd.DataFrame(
            {
                "recoverywin_total_precipitation_mean": [0.001, 0.005, 0.006],
                "pre_shap": [-2.0, 1.5, 2.5],
                "gpp_drop_magnitude": [0.2, 1.8, 2.2],
                "mechanism_group": ["expected_mild", "expected_severe", "expected_severe"],
            }
        )

        summary = MODULE.summarize_biome(
            biome="Cropland",
            full_df=full_df,
            filtered_df=filtered_df,
            pre_col="recoverywin_total_precipitation_mean",
            shap_col="pre_shap",
            color_col="gpp_drop_magnitude",
            q_low=0.05,
            q_high=0.95,
        )

        self.assertIn("all_filtered", set(summary["group"]))
        self.assertIn("expected_mild", set(summary["group"]))
        self.assertIn("expected_severe", set(summary["group"]))


if __name__ == "__main__":
    unittest.main()
