from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "run_opgd_geodetector_validation.py"
SCRIPT_DIR = SCRIPT_PATH.parent
VALIDATION_DIR = SCRIPT_DIR.parent
for path in [SCRIPT_DIR, VALIDATION_DIR]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

SPEC = importlib.util.spec_from_file_location("gleam_opgd_geodetector_validation", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TestOPGDGeodetectorValidation(unittest.TestCase):
    def test_select_optimal_strata_keeps_best_candidate_metadata(self):
        x = pd.Series([1, 2, 3, 4, 10, 11, 12, 13], dtype=float)
        y = pd.Series([1, 1, 1, 1, 9, 9, 9, 9], dtype=float)

        result = MODULE.select_optimal_strata(
            x,
            y,
            methods=["equal_interval", "quantile"],
            bin_counts=[2, 4],
            min_group_size=2,
        )

        self.assertEqual(result.method, "equal_interval")
        self.assertEqual(result.bins, 2)
        self.assertGreater(result.q, 0.95)
        self.assertEqual(result.strata_count, 2)
        self.assertEqual(result.min_group_size, 4)
        self.assertEqual(len(result.strata), len(x))
        self.assertTrue(np.isfinite(result.breaks).all())

    def test_select_optimal_strata_rejects_tiny_groups(self):
        x = pd.Series([1, 2, 3, 4, 100], dtype=float)
        y = pd.Series([1, 1, 1, 1, 9], dtype=float)

        result = MODULE.select_optimal_strata(
            x,
            y,
            methods=["equal_interval"],
            bin_counts=[2],
            min_group_size=3,
        )

        self.assertTrue(np.isnan(result.q))
        self.assertEqual(result.method, "")
        self.assertEqual(result.bins, 0)
        self.assertEqual(result.strata_count, 0)

    def test_interaction_uses_optimized_single_factor_strata(self):
        frame = pd.DataFrame(
            {
                "target": [1, 1, 1, 1, 9, 9, 9, 9],
                "a": [1, 2, 3, 4, 10, 11, 12, 13],
                "b": [10, 11, 12, 13, 1, 2, 3, 4],
            }
        )
        optimized = {
            feature: MODULE.select_optimal_strata(
                frame[feature],
                frame["target"],
                methods=["equal_interval", "quantile"],
                bin_counts=[2],
                min_group_size=2,
            )
            for feature in ["a", "b"]
        }

        row = MODULE.build_interaction_row(
            metric="GPP",
            biome="Demo",
            frame=frame,
            target="target",
            feature_1="a",
            feature_2="b",
            optimized=optimized,
            labeler=lambda value: value.upper(),
        )

        self.assertEqual(row["feature_1"], "a")
        self.assertEqual(row["label_1"], "A")
        self.assertGreater(row["q_interaction"], 0.95)
        self.assertEqual(row["method_1"], optimized["a"].method)
        self.assertEqual(row["bins_1"], optimized["a"].bins)
        self.assertEqual(row["interaction_relation"], "bi_factor_enhance")


if __name__ == "__main__":
    unittest.main()
