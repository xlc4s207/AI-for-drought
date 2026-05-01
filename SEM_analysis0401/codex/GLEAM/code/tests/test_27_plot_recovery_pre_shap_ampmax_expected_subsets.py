from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "27_plot_recovery_pre_shap_ampmax_expected_subsets.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_ampmax_expected_subsets", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TestAmpmaxExpectedSubsets(unittest.TestCase):
    def test_compute_gpp_drop_magnitude_maps_negative_ampmax_to_positive_drop(self):
        values = pd.Series([-2.0, -0.5, 0.0, 1.0])

        result = MODULE.compute_gpp_drop_magnitude(values)

        self.assertListEqual(result.round(6).tolist(), [2.0, 0.5, 0.0, 0.0])

    def test_classify_expected_groups_marks_mild_and_severe_samples(self):
        frame = pd.DataFrame(
            {
                "pre": [0.001, 0.002, 0.003, 0.005, 0.006, 0.007],
                "shap": [-3.0, -1.5, -0.2, 0.5, 2.0, 3.0],
                "amp_max": [-0.1, -0.2, -0.3, -1.5, -2.5, -3.0],
            }
        )

        groups = MODULE.classify_expected_groups(
            frame,
            pre_col="pre",
            shap_col="shap",
            amp_col="amp_max",
            low_pre_threshold=0.004,
            severe_pre_threshold=0.001,
        )

        self.assertEqual(groups.iloc[0], "expected_mild")
        self.assertEqual(groups.iloc[5], "expected_severe")
        self.assertIn("background", set(groups.astype(str)))


if __name__ == "__main__":
    unittest.main()
