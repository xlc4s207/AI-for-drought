from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "35_backfill_dependence_artifacts.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_backfill_dependence_artifacts", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TestBackfillDependenceArtifacts(unittest.TestCase):
    def test_build_read_columns_keeps_filters_target_and_unique_features(self):
        columns = MODULE.build_read_columns(
            target="t_recover_to_baseline_abs_peak",
            include_features=[
                "recoverywin_total_precipitation_mean",
                "recoverywin_total_precipitation_mean",
                "recoverywin_VPD_mean",
            ],
            extra_columns=["event_duration", "event_duration"],
        )

        self.assertEqual(
            columns,
            [
                "metric",
                "code_id",
                "biome",
                "drought_type",
                "soil_layer",
                "t_recover_to_baseline_abs_peak",
                "recoverywin_total_precipitation_mean",
                "recoverywin_VPD_mean",
                "event_duration",
            ],
        )

    def test_prepare_model_frame_filters_rows_and_fills_missing_values(self):
        df = pd.DataFrame(
            {
                "metric": ["RECO", "RECO", "GPP"],
                "code_id": ["code1", "code1", "code1"],
                "biome": ["Forest", "Forest", "Forest"],
                "drought_type": ["flash", "flash", "flash"],
                "soil_layer": ["SMrz", "SMrz", "SMrz"],
                "t_recover_to_baseline_abs_peak": [10.0, 12.0, 15.0],
                "recoverywin_total_precipitation_mean": [1.0, None, 3.0],
                "recoverywin_VPD_mean": [0.2, 0.4, 0.6],
            }
        )

        features, target = MODULE.prepare_model_frame(
            df=df,
            biome="Forest",
            metric="RECO",
            code_id="code1",
            drought_type="flash",
            soil_layer="SMrz",
            target="t_recover_to_baseline_abs_peak",
            include_features=["recoverywin_total_precipitation_mean", "recoverywin_VPD_mean"],
            limit=None,
        )

        self.assertEqual(features.columns.tolist(), ["recoverywin_VPD_mean"])
        self.assertEqual(len(features), 2)
        self.assertEqual(len(target), 2)
        self.assertFalse(features.isna().any().any())
        self.assertAlmostEqual(float(features.iloc[1, 0]), 0.4, places=6)

    def test_write_dependence_artifacts_saves_three_parquet_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "Forest"
            sample = pd.DataFrame(
                {
                    "recoverywin_total_precipitation_mean": [1.0, 2.0],
                    "recoverywin_VPD_mean": [0.2, 0.4],
                },
                index=[5, 6],
            )
            shap_df = pd.DataFrame(
                {
                    "recoverywin_total_precipitation_mean": [-0.5, 0.8],
                    "recoverywin_VPD_mean": [0.1, -0.2],
                },
                index=[5, 6],
            )

            MODULE.write_dependence_artifacts(output_dir, sample, shap_df)

            sample_path = output_dir / "dependence_sample_features.parquet"
            shap_path = output_dir / "dependence_sample_shap_values.parquet"
            merged_path = output_dir / "dependence_plot_data.parquet"
            self.assertTrue(sample_path.exists())
            self.assertTrue(shap_path.exists())
            self.assertTrue(merged_path.exists())

            merged = pd.read_parquet(merged_path)
            self.assertEqual(
                merged.columns.tolist(),
                [
                    "feature__recoverywin_total_precipitation_mean",
                    "feature__recoverywin_VPD_mean",
                    "shap__recoverywin_total_precipitation_mean",
                    "shap__recoverywin_VPD_mean",
                ],
            )


if __name__ == "__main__":
    unittest.main()
