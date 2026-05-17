from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "28_filter_full_mechanism_samples.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_full_mechanism_filter", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TestFullMechanismFiltering(unittest.TestCase):
    def test_compute_gpp_drop_magnitude_converts_negative_ampmax(self):
        values = pd.Series([-2.5, -0.4, 0.0, 1.2])

        result = MODULE.compute_gpp_drop_magnitude(values)

        self.assertListEqual(result.round(6).tolist(), [2.5, 0.4, 0.0, 0.0])

    def test_classify_mechanism_groups_uses_expected_rules(self):
        frame = pd.DataFrame(
            {
                "pre": [0.001, 0.002, 0.0045, 0.006, 0.007],
                "pre_shap": [-2.0, -0.5, 0.1, 2.0, 3.5],
                "amp_max": [-0.1, -0.5, -1.0, -2.0, -3.0],
            }
        )

        groups = MODULE.classify_mechanism_groups(
            frame,
            pre_col="pre",
            shap_col="pre_shap",
            amp_col="amp_max",
            low_pre_threshold=0.004,
            severe_pre_threshold=0.004,
        )

        self.assertEqual(groups.iloc[0], "expected_mild")
        self.assertEqual(groups.iloc[4], "expected_severe")
        self.assertIn("background", set(groups.astype(str)))


if __name__ == "__main__":
    unittest.main()
