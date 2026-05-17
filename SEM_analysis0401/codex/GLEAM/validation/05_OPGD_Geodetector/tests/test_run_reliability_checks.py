from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "run_reliability_checks.py"
SCRIPT_DIR = SCRIPT_PATH.parent
VALIDATION_DIR = SCRIPT_DIR.parent
for path in [SCRIPT_DIR, VALIDATION_DIR]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

SPEC = importlib.util.spec_from_file_location("gleam_opgd_reliability_checks", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TestOPGDReliabilityChecks(unittest.TestCase):
    def test_spearman_rank_correlation_detects_same_and_reverse_order(self):
        same = MODULE.spearman_rank_correlation(
            {"a": 1, "b": 2, "c": 3},
            {"a": 1, "b": 2, "c": 3},
        )
        reverse = MODULE.spearman_rank_correlation(
            {"a": 1, "b": 2, "c": 3},
            {"a": 3, "b": 2, "c": 1},
        )

        self.assertAlmostEqual(same, 1.0)
        self.assertAlmostEqual(reverse, -1.0)

    def test_build_shap_opgd_consistency_row_reports_overlap_and_correlation(self):
        opgd_group = pd.DataFrame(
            {
                "metric": ["GPP"] * 3,
                "biome": ["Demo"] * 3,
                "feature": ["a", "b", "c"],
                "label": ["A", "B", "C"],
                "q": [0.3, 0.2, 0.1],
            }
        )
        shap_group = pd.DataFrame(
            {
                "feature": ["a", "c", "b"],
                "importance": [10.0, 8.0, 2.0],
            }
        )

        row = MODULE.build_shap_opgd_consistency_row(opgd_group, shap_group, top_n=2)

        self.assertEqual(row["metric"], "GPP")
        self.assertEqual(row["biome"], "Demo")
        self.assertEqual(row["top3_overlap_count"], 1)
        self.assertEqual(row["top3_overlap_labels"], "A")
        self.assertLess(row["spearman_rank_correlation"], 1.0)

    def test_assign_reliability_grade_uses_q_stability_shap_and_group_size(self):
        self.assertEqual(
            MODULE.assign_reliability_grade(
                q=0.16,
                q_cv=0.08,
                top3_frequency=0.85,
                in_shap_top3=True,
                min_group_share=0.08,
            ),
            "High",
        )
        self.assertEqual(
            MODULE.assign_reliability_grade(
                q=0.08,
                q_cv=0.20,
                top3_frequency=0.50,
                in_shap_top3=True,
                min_group_share=0.02,
            ),
            "Medium",
        )
        self.assertEqual(
            MODULE.assign_reliability_grade(
                q=0.03,
                q_cv=0.70,
                top3_frequency=0.10,
                in_shap_top3=False,
                min_group_share=0.001,
            ),
            "Low",
        )

    def test_assign_reliability_grade_caps_tiny_strata_as_not_high_reliability(self):
        self.assertEqual(
            MODULE.assign_reliability_grade(
                q=0.16,
                q_cv=0.08,
                top3_frequency=0.95,
                in_shap_top3=True,
                min_group_share=0.003,
            ),
            "Medium",
        )
        self.assertEqual(
            MODULE.assign_reliability_grade(
                q=0.16,
                q_cv=0.08,
                top3_frequency=0.95,
                in_shap_top3=True,
                min_group_share=0.0008,
            ),
            "Low",
        )


if __name__ == "__main__":
    unittest.main()
