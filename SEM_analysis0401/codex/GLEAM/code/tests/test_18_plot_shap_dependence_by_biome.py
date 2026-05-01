from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "18_plot_shap_dependence_by_biome.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_dependence_by_biome", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TestDependencePlotByBiome(unittest.TestCase):
    def test_sample_for_shap_uses_requested_limit(self):
        X = MODULE.pd.DataFrame({"x": np.arange(10000, dtype=float)})
        sampled = MODULE.sample_for_shap(X, sample_size=5000, random_state=42)
        self.assertEqual(len(sampled), 5000)

    def test_build_dependence_points_frame_keeps_only_finite_points(self):
        frame = MODULE.build_dependence_points_frame(
            "recoverywin_total_precipitation_mean",
            np.array([1.0, np.nan, 3.0, 4.0]),
            np.array([0.2, 0.1, np.nan, -0.4]),
        )
        self.assertEqual(frame["label"].iloc[0], "PRE")
        self.assertEqual(len(frame), 2)
        self.assertListEqual(frame["point_index"].tolist(), [0, 1])
        self.assertListEqual(frame["feature_value"].round(6).tolist(), [1.0, 4.0])
        self.assertListEqual(frame["shap_value"].round(6).tolist(), [0.2, -0.4])


if __name__ == "__main__":
    unittest.main()
