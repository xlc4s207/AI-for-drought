from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "48_redraw_prepeak_shap_plots2.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_redraw_prepeak_shap_plots2", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TestRedrawPrepeakShapPlots2(unittest.TestCase):
    def test_duration_color_values_drop_high_tail_outliers(self):
        sample = pd.DataFrame({"event_duration": [20.0, 40.0, 80.0, 120.0, 1000.0]})

        values, unit = MODULE.dependence_color_values(sample, "event_duration")

        self.assertEqual(unit, "days")
        self.assertTrue(np.isnan(values[-1]))
        self.assertTrue(np.isfinite(values[:-1]).all())

    def test_evaporation_color_values_drop_two_sided_outliers(self):
        sample = pd.DataFrame(
            {"prepeak_total_evaporation_mean": [-0.0001, -0.001, -0.002, -0.003, -0.1]}
        )

        values, unit = MODULE.dependence_color_values(sample, "prepeak_total_evaporation_mean")

        self.assertEqual(unit, "mm")
        self.assertTrue(np.isnan(values[0]))
        self.assertTrue(np.isnan(values[-1]))
        self.assertTrue(np.isfinite(values[1:-1]).all())

    def test_smrz_color_values_drop_two_sided_outliers(self):
        sample = pd.DataFrame({"prepeak_SMrz_mean": [0.01, 0.08, 0.12, 0.20, 0.60]})

        values, unit = MODULE.dependence_color_values(sample, "prepeak_SMrz_mean")

        self.assertEqual(unit, "m3/m3")
        self.assertTrue(np.isnan(values[0]))
        self.assertTrue(np.isnan(values[-1]))
        self.assertTrue(np.isfinite(values[1:-1]).all())

    def test_temperature_color_values_drop_two_sided_outliers(self):
        sample = pd.DataFrame({"prepeak_temperature_2m_mean": [270.0, 285.0, 290.0, 295.0, 310.0]})

        values, unit = MODULE.dependence_color_values(sample, "prepeak_temperature_2m_mean")

        self.assertEqual(unit, "K")
        self.assertTrue(np.isnan(values[0]))
        self.assertTrue(np.isnan(values[-1]))
        self.assertTrue(np.isfinite(values[1:-1]).all())

    def test_vpd_values_convert_from_hpa_to_kpa(self):
        values, unit = MODULE.convert_feature_units(
            "prepeak_VPD_mean", np.array([6.0, 27.0, np.nan], dtype=float)
        )

        self.assertEqual(unit, "kPa")
        np.testing.assert_allclose(values[:2], [0.6, 2.7])
        self.assertTrue(np.isnan(values[2]))

    def test_eva_dependence_adds_vpd_color_mapping(self):
        specs = MODULE.color_specs_for_feature("prepeak_total_evaporation_mean")

        self.assertIn(("prepeak_VPD_mean", "VPD"), specs)

    def test_pre_dependence_adds_recovery_time_color_mapping(self):
        specs = MODULE.color_specs_for_feature("prepeak_total_precipitation_mean")

        self.assertIn((MODULE.RECOVERY_TIME_FEATURE, "Recovery"), specs)

    def test_recovery_color_values_use_tighter_two_sided_clip(self):
        values = np.array([0.0, 0.0, 1.0, 10.0, 20.0, 100.0], dtype=float)

        clipped = MODULE.clip_two_sided_color_tail(values, low_q=0.10, high_q=0.90)

        self.assertTrue(np.isnan(clipped[0]))
        self.assertTrue(np.isnan(clipped[1]))
        self.assertTrue(np.isnan(clipped[-1]))
        self.assertTrue(np.isfinite(clipped[2:-1]).all())

    def test_prepare_beeswarm_inputs_uses_fixed_gpp_reco_feature_order(self):
        fixed_features = [
            "prepeak_ssrd_mean",
            "prepeak_total_evaporation_mean",
            "prepeak_temperature_2m_mean",
            "prepeak_strd_mean",
            "prepeak_SMrz_mean",
            "prepeak_wind_speed_mean",
            "prepeak_VPD_mean",
            "event_duration",
            "prepeak_total_precipitation_mean",
            "event_intensity",
        ]
        sample = pd.DataFrame(
            {
                feature: [float(i + 1), float(i + 2)]
                for i, feature in enumerate(fixed_features + ["event_onset_days", "prepeak_lai_total_mean"])
            }
        )
        shap_df = pd.DataFrame(
            {
                feature: [float(i), float(-i)]
                for i, feature in enumerate(fixed_features + ["event_onset_days", "prepeak_lai_total_mean"])
            }
        )
        importance_df = pd.DataFrame(
            {
                "feature": [
                    "event_onset_days",
                    "prepeak_lai_total_mean",
                    "prepeak_VPD_mean",
                    "prepeak_total_precipitation_mean",
                    "prepeak_wind_speed_mean",
                    "prepeak_ssrd_mean",
                    "prepeak_temperature_2m_mean",
                    "event_duration",
                    "event_intensity",
                    "prepeak_SMrz_mean",
                    "prepeak_strd_mean",
                    "prepeak_total_evaporation_mean",
                ],
                "importance": np.arange(12, dtype=float),
            }
        )

        feature_frame, shap_matrix, feature_names = MODULE.prepare_beeswarm_inputs(
            sample, shap_df, importance_df, top_n=10
        )

        self.assertEqual(
            feature_names,
            ["SSRD", "|EVA|", "TMP", "STRD", "SMrz", "Wind", "VPD", "Duration", "Pre", "Intensity"],
        )
        self.assertEqual(feature_frame.columns.tolist(), feature_names)
        self.assertEqual(shap_matrix.shape, (2, 10))

    def test_plot_single_beeswarm_enables_shap_internal_sorting(self):
        fixed_features = MODULE.FIXED_BEESWARM_FEATURES
        sample = pd.DataFrame(
            {
                feature: [float(i + 1), float(i + 2), float(i + 3)]
                for i, feature in enumerate(fixed_features)
            }
        )
        shap_df = pd.DataFrame(
            {
                feature: [float(i), float(-i), float(i + 0.5)]
                for i, feature in enumerate(fixed_features)
            }
        )
        importance_df = pd.DataFrame({"feature": fixed_features, "importance": np.arange(len(fixed_features))})
        calls = []
        original_summary_plot = MODULE.shap.summary_plot

        def fake_summary_plot(**kwargs):
            calls.append(kwargs)

        MODULE.shap.summary_plot = fake_summary_plot
        try:
            with tempfile.TemporaryDirectory() as tmp:
                MODULE.plot_single_beeswarm(
                    sample,
                    shap_df,
                    importance_df,
                    "test",
                    Path(tmp) / "beeswarm.png",
                    top_n=10,
                )
        finally:
            MODULE.shap.summary_plot = original_summary_plot

        self.assertEqual(calls[0]["feature_names"], ["SSRD", "|EVA|", "TMP", "STRD", "SMrz", "Wind", "VPD", "Duration", "Pre", "Intensity"])
        self.assertIs(calls[0]["sort"], True)


if __name__ == "__main__":
    unittest.main()
