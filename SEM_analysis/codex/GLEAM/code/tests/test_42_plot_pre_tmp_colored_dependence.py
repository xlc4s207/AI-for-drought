from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "42_plot_pre_tmp_colored_dependence.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("plot_pre_tmp_colored_dependence", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TestPlotPreTmpColoredDependence(unittest.TestCase):
    def test_build_scheme_feature_name(self):
        self.assertEqual(MODULE.build_scheme_feature_name("prepeak", "total_precipitation_mean"), "prepeak_total_precipitation_mean")
        self.assertEqual(MODULE.build_scheme_feature_name("recoverywin", "temperature_2m_mean"), "recoverywin_temperature_2m_mean")

    def test_compute_color_norm_uses_quantiles(self):
        series = pd.Series(np.linspace(280.0, 310.0, 100))
        norm = MODULE.compute_color_norm(series, 0.05, 0.95)
        self.assertIsNotNone(norm)
        assert norm is not None
        self.assertAlmostEqual(float(norm.vmin), float(series.quantile(0.05)), places=6)
        self.assertAlmostEqual(float(norm.vmax), float(series.quantile(0.95)), places=6)

    def test_build_filtered_frame_keeps_pre_tmp_columns(self):
        sample_df = pd.DataFrame(
            {
                "prepeak_total_precipitation_mean": [0.1, 0.2, 0.3],
                "prepeak_temperature_2m_mean": [295.0, 296.0, 297.0],
            }
        )
        shap_df = pd.DataFrame(
            {
                "prepeak_total_precipitation_mean": [-1.0, 0.5, 0.8],
            }
        )
        frame = MODULE.build_filtered_frame(sample_df, shap_df, "prepeak", "temperature_2m_mean")
        self.assertEqual(list(frame.columns), ["x", "y", "color"])
        self.assertEqual(len(frame), 3)

    def test_build_filtered_frame_supports_alternative_color_feature(self):
        sample_df = pd.DataFrame(
            {
                "prepeak_total_precipitation_mean": [0.1, 0.2, 0.3],
                "prepeak_total_evaporation_mean": [0.001, 0.0011, 0.0012],
            }
        )
        shap_df = pd.DataFrame(
            {
                "prepeak_total_precipitation_mean": [-1.0, 0.5, 0.8],
            }
        )
        frame = MODULE.build_filtered_frame(sample_df, shap_df, "prepeak", "total_evaporation_mean")
        self.assertEqual(list(frame.columns), ["x", "y", "color"])
        self.assertEqual(len(frame), 3)
        self.assertAlmostEqual(float(frame.loc[0, "color"]), 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
