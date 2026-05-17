from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "32_plot_onsetpeak_dependence_comparison.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_onsetpeak_dependence_comparison", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TestOnsetpeakDependenceComparison(unittest.TestCase):
    def test_build_phase_columns_resolves_prefixed_feature_and_shap_names(self):
        cols = MODULE.build_phase_columns("prepeak", "total_precipitation_mean")
        self.assertEqual(cols.feature_col, "feature__prepeak_total_precipitation_mean")
        self.assertEqual(cols.shap_col, "shap__prepeak_total_precipitation_mean")

        cols = MODULE.build_phase_columns("shock", "SMrz_mean")
        self.assertEqual(cols.feature_col, "feature__shock_SMrz_mean")
        self.assertEqual(cols.shap_col, "shap__shock_SMrz_mean")

    def test_build_phase_columns_rejects_unknown_phase(self):
        with self.assertRaises(ValueError):
            MODULE.build_phase_columns("recoverywin", "ssrd_mean")


if __name__ == "__main__":
    unittest.main()
