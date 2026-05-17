from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "33_plot_prepeak_vs_recoverywin_comparison.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_prepeak_vs_recoverywin_comparison", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TestPrepeakVsRecoverywinComparison(unittest.TestCase):
    def test_resolve_biomes_uses_explicit_argument_when_provided(self):
        biomes = MODULE.resolve_biomes(["Forest", "Wetland"])
        self.assertEqual(biomes, ["Forest", "Wetland"])

    def test_resolve_biomes_falls_back_to_default(self):
        biomes = MODULE.resolve_biomes(None)
        self.assertEqual(biomes, MODULE.DEFAULT_BIOMES)

    def test_normalize_biome_root_prefers_shap_by_biome_subdir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            nested = root / "shap_by_biome"
            nested.mkdir()

            resolved = MODULE.normalize_biome_root(root)

        self.assertEqual(resolved, nested)

    def test_resolve_biomes_uses_shared_directory_names_when_roots_provided(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            prepeak_root = tmp_path / "prepeak"
            recoverywin_root = tmp_path / "recoverywin"
            for biome in ["Forest", "Wetland", "Savanna"]:
                (prepeak_root / biome).mkdir(parents=True, exist_ok=True)
            for biome in ["Forest", "Grassland", "Wetland"]:
                (recoverywin_root / biome).mkdir(parents=True, exist_ok=True)

            biomes = MODULE.resolve_biomes(
                None,
                prepeak_root=prepeak_root,
                recoverywin_root=recoverywin_root,
            )

        self.assertEqual(biomes, ["Forest", "Wetland"])

    def test_format_beeswarm_feature_name_uses_short_labels(self):
        self.assertEqual(MODULE.format_beeswarm_feature_name("prepeak_total_evaporation_mean"), "EVA (mm)")
        self.assertEqual(MODULE.format_beeswarm_feature_name("recoverywin_total_precipitation_mean"), "PRE (mm)")
        self.assertEqual(MODULE.format_beeswarm_feature_name("prepeak_temperature_2m_mean"), "TMP (K)")
        self.assertEqual(MODULE.format_beeswarm_feature_name("event_onset_days"), "Onset day")
        self.assertEqual(MODULE.format_beeswarm_feature_name("event_duration"), "Duration")
        self.assertEqual(MODULE.format_beeswarm_feature_name("event_intensity"), "Intensity")

    def test_build_scheme_columns_resolves_prefixed_feature_and_shap_names(self):
        cols = MODULE.build_scheme_columns("prepeak", "ssrd_mean")
        self.assertEqual(cols.feature_col, "feature__prepeak_ssrd_mean")
        self.assertEqual(cols.shap_col, "shap__prepeak_ssrd_mean")

        cols = MODULE.build_scheme_columns("recoverywin", "wind_speed_mean")
        self.assertEqual(cols.feature_col, "feature__recoverywin_wind_speed_mean")
        self.assertEqual(cols.shap_col, "shap__recoverywin_wind_speed_mean")

    def test_build_sample_columns_resolves_raw_sample_column_names(self):
        cols = MODULE.build_sample_columns("prepeak", "total_precipitation_mean")
        self.assertEqual(cols.feature_col, "prepeak_total_precipitation_mean")
        self.assertEqual(cols.shap_col, "prepeak_total_precipitation_mean")

        cols = MODULE.build_sample_columns("recoverywin", "wind_speed_mean")
        self.assertEqual(cols.feature_col, "recoverywin_wind_speed_mean")
        self.assertEqual(cols.shap_col, "recoverywin_wind_speed_mean")

    def test_shared_feature_names_exclude_event_features(self):
        self.assertEqual(
            MODULE.SHARED_FEATURES,
            [
                "total_precipitation_mean",
                "total_evaporation_mean",
                "temperature_2m_mean",
                "VPD_mean",
                "SMrz_mean",
                "ssrd_mean",
                "strd_mean",
                "wind_speed_mean",
            ],
        )

    def test_read_importance_order_keeps_only_shared_features(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "feature_importance.csv"
            pd.DataFrame(
                {
                    "feature": [
                        "prepeak_total_evaporation_mean",
                        "event_duration",
                        "prepeak_ssrd_mean",
                        "prepeak_wind_speed_mean",
                        "event_intensity",
                        "prepeak_total_precipitation_mean",
                    ],
                    "importance": [4.0, 3.0, 2.0, 1.5, 1.0, 0.8],
                    "rank": [1, 2, 3, 4, 5, 6],
                }
            ).to_csv(csv_path, index=False)

            ordered = MODULE.read_importance_order(csv_path, "prepeak")

        self.assertEqual(
            ordered,
            [
                "total_evaporation_mean",
                "ssrd_mean",
                "wind_speed_mean",
                "total_precipitation_mean",
            ],
        )

    def test_compute_beeswarm_offsets_stacks_nearby_points(self):
        x = pd.Series([0.0, 0.0, 0.0, 0.1, 0.1, 2.0], dtype=float).to_numpy()

        offsets = MODULE.compute_beeswarm_offsets(x, max_swarm=0.28)

        self.assertEqual(len(offsets), len(x))
        self.assertTrue((abs(offsets) <= 0.28 + 1e-9).all())
        self.assertGreater(len(set(offsets[:3])), 1)
        self.assertGreater(len(set(offsets[3:5])), 1)
        self.assertEqual(offsets[-1], 0.0)

    def test_prepare_standard_beeswarm_inputs_returns_prefixed_feature_frame_and_shap_matrix(self):
        sample_df = pd.DataFrame(
            {
                "prepeak_total_precipitation_mean": [0.1, 0.2, 0.3],
                "prepeak_total_evaporation_mean": [1.0, 1.1, 1.2],
                "recoverywin_total_precipitation_mean": [0.1, 0.2, 0.3],
            }
        )
        shap_df = pd.DataFrame(
            {
                "prepeak_total_precipitation_mean": [-2.0, 0.5, 1.0],
                "prepeak_total_evaporation_mean": [0.2, -0.1, 0.4],
                "recoverywin_total_precipitation_mean": [-1.5, 0.25, 2.5],
            }
        )

        feature_frame, shap_matrix, feature_names = MODULE.prepare_standard_beeswarm_inputs(
            sample_df=sample_df,
            shap_df=shap_df,
            scheme="prepeak",
            feature_order=["total_precipitation_mean", "total_evaporation_mean"],
            max_points=10,
        )

        self.assertEqual(
            list(feature_frame.columns),
            ["prepeak_total_precipitation_mean", "prepeak_total_evaporation_mean"],
        )
        self.assertEqual(feature_names, list(feature_frame.columns))
        self.assertEqual(shap_matrix.shape, (3, 2))
        self.assertAlmostEqual(float(shap_matrix[0, 0]), -2.0, places=6)
        self.assertAlmostEqual(float(shap_matrix[2, 1]), 0.4, places=6)

    def test_plot_standard_beeswarm_panel_calls_shap_summary_plot(self):
        sample_df = pd.DataFrame(
            {
                "prepeak_total_precipitation_mean": [0.1, 0.2, 0.3],
                "prepeak_total_evaporation_mean": [1.0, 1.1, 1.2],
            }
        )
        shap_df = pd.DataFrame(
            {
                "prepeak_total_precipitation_mean": [-2.0, 0.5, 1.0],
                "prepeak_total_evaporation_mean": [0.2, -0.1, 0.4],
            }
        )
        calls: list[dict[str, object]] = []

        class FakeShapModule:
            @staticmethod
            def summary_plot(shap_values, features=None, feature_names=None, **kwargs):
                calls.append(
                    {
                        "shape": shap_values.shape,
                        "feature_shape": features.shape,
                        "feature_names": list(feature_names),
                        "kwargs": kwargs,
                    }
                )

        with mock.patch.object(MODULE, "shap", FakeShapModule()):
            fig, ax = MODULE.plt.subplots(figsize=(4, 3))
            try:
                MODULE.plot_standard_beeswarm_panel(
                    ax=ax,
                    sample_df=sample_df,
                    shap_df=shap_df,
                    scheme="prepeak",
                    feature_order=["total_precipitation_mean", "total_evaporation_mean"],
                    max_points=10,
                )
            finally:
                MODULE.plt.close(fig)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["shape"], (3, 2))
        self.assertEqual(calls[0]["feature_shape"], (3, 2))
        self.assertEqual(calls[0]["kwargs"]["max_display"], 2)
        self.assertFalse(calls[0]["kwargs"]["show"])
        self.assertFalse(calls[0]["kwargs"]["color_bar"])
        self.assertEqual(
            calls[0]["feature_names"],
            ["PRE (mm)", "EVA (mm)"],
        )


if __name__ == "__main__":
    unittest.main()
