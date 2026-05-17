from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "make_opgd_shap_comparison_docx.py"
SCRIPT_DIR = SCRIPT_PATH.parent
VALIDATION_DIR = SCRIPT_DIR.parent
for path in [SCRIPT_DIR, VALIDATION_DIR]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

SPEC = importlib.util.spec_from_file_location("gleam_make_opgd_shap_comparison_docx", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TestMakeOPGDSHAPComparisonDocx(unittest.TestCase):
    def test_overlap_note_classifies_partial_and_high_agreement(self):
        self.assertIn("高度一致", MODULE.overlap_note(["TMP", "SSRD"]))
        self.assertIn("部分一致", MODULE.overlap_note(["TMP"]))
        self.assertIn("差异较大", MODULE.overlap_note([]))

    def test_format_top_features_uses_q_method_and_bins_for_opgd(self):
        rows = pd.DataFrame(
            {
                "label": ["TMP", "SSRD"],
                "q": [0.1234, 0.0567],
                "method": ["quantile", "equal_interval"],
                "bins": [10, 6],
            }
        )

        text = MODULE.format_opgd_top_features(rows)

        self.assertIn("TMP (q=0.123, quantile/10)", text)
        self.assertIn("SSRD (q=0.057, equal_interval/6)", text)

    def test_reliability_counts_text_formats_grade_counts(self):
        reliability = pd.DataFrame({"reliability_grade": ["High", "Low", "Medium", "High"]})

        text = MODULE.reliability_counts_text(reliability)

        self.assertIn("High 2 个", text)
        self.assertIn("Medium 1 个", text)
        self.assertIn("Low 1 个", text)

    def test_figure_paths_returns_expected_main_and_interaction_names(self):
        paths = MODULE.figure_paths(Path("/tmp/demo"))

        self.assertEqual(paths[0].name, "shap_opgd_reliability_matrix.png")
        self.assertEqual(paths[1].name, "opgd_interaction_heatmaps.png")


if __name__ == "__main__":
    unittest.main()
