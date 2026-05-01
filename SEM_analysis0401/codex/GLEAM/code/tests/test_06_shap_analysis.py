from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path
import unittest
from unittest import mock

import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "06_shap_analysis.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_shap_analysis", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TestShapAnalysis(unittest.TestCase):
    def test_filter_feature_names_respects_include_and_exclude(self):
        feature_names = [
            "recoverywin_temperature_2m_mean",
            "recoverywin_dewpoint_temperature_mean",
            "recoverywin_VPD_mean",
            "recoverywin_p_minus_et",
        ]
        resolved = MODULE.filter_feature_names(
            feature_names,
            include_features=[
                "recoverywin_temperature_2m_mean",
                "recoverywin_VPD_mean",
                "recoverywin_p_minus_et",
            ],
            exclude_features=["recoverywin_VPD_mean"],
        )
        self.assertEqual(
            resolved,
            [
                "recoverywin_temperature_2m_mean",
                "recoverywin_p_minus_et",
            ],
        )

    def test_compute_split_r2_returns_holdout_metrics(self):
        X = MODULE.pd.DataFrame(
            {
                "x1": np.arange(50, dtype=float),
                "x2": np.arange(50, dtype=float) * 0.5,
            }
        )
        y = (2.0 * X["x1"] - 0.3 * X["x2"]).astype(np.float32)
        metrics = MODULE.compute_split_r2(
            X,
            y,
            backend="random_forest",
            random_state=42,
            n_estimators=50,
            n_jobs=1,
        )
        self.assertIn("r2_train_split", metrics)
        self.assertIn("r2_holdout_split", metrics)
        self.assertGreaterEqual(metrics["split_train_rows"], 1)
        self.assertGreaterEqual(metrics["split_test_rows"], 1)

    def test_resolve_sample_output_dir_keeps_legacy_single_sample_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "shap"
            resolved = MODULE.resolve_sample_output_dir(output_dir, 5000, [5000])
            self.assertEqual(resolved, output_dir)

    def test_resolve_sample_output_dir_nests_multi_sample_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "shap"
            resolved = MODULE.resolve_sample_output_dir(output_dir, 10000, [5000, 10000, 20000])
            self.assertEqual(resolved, output_dir / "sample_10000")

    def test_save_beeswarm_plot_writes_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            calls: list[tuple[np.ndarray, tuple[int, int]]] = []

            class FakeShapModule:
                @staticmethod
                def summary_plot(values, features, show=False, plot_type=None, max_display=None):
                    calls.append((np.asarray(values), features.shape))

            sample = MODULE.pd.DataFrame(
                {
                    "a": [1.0, 2.0, 3.0],
                    "b": [4.0, 5.0, 6.0],
                }
            )
            shap_values = np.array(
                [
                    [0.1, -0.2],
                    [0.3, 0.4],
                    [-0.5, 0.6],
                ],
                dtype=float,
            )
            output_path = tmp_path / "beeswarm.png"

            with mock.patch.object(MODULE, "shap", FakeShapModule()):
                MODULE.save_beeswarm_plot(shap_values, sample, output_path, top_k=10)

            self.assertTrue(output_path.exists())
            self.assertGreater(output_path.stat().st_size, 0)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][1], sample.shape)


if __name__ == "__main__":
    unittest.main()
