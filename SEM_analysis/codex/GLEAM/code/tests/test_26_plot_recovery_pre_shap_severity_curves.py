from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "26_plot_recovery_pre_shap_severity_curves.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_pre_shap_severity_curves", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TestRecoveryPreShapSeverityCurves(unittest.TestCase):
    def test_compute_percentile_composite_increases_with_severity(self):
        frame = pd.DataFrame(
            {
                "event_intensity": [0.1, 1.0, 10.0],
                "event_onset_drop": [0.01, 0.03, 0.08],
                "amp_max": [-0.2, -1.0, -3.0],
            }
        )

        score = MODULE.compute_percentile_composite(frame)

        self.assertEqual(len(score), 3)
        self.assertTrue(np.isfinite(score).all())
        self.assertLess(score.iloc[0], score.iloc[1])
        self.assertLess(score.iloc[1], score.iloc[2])

    def test_assign_severity_groups_returns_low_mid_high(self):
        values = pd.Series(np.arange(9, dtype=float))

        groups = MODULE.assign_severity_groups(values, n_groups=3)

        self.assertListEqual(sorted(groups.astype(str).unique().tolist()), ["High", "Low", "Mid"])
        self.assertEqual((groups.astype(str) == "Low").sum(), 3)
        self.assertEqual((groups.astype(str) == "Mid").sum(), 3)
        self.assertEqual((groups.astype(str) == "High").sum(), 3)

    def test_build_group_curve_summary_keeps_all_groups(self):
        frame = pd.DataFrame(
            {
                "pre": np.tile(np.linspace(0.0, 0.012, 12), 3),
                "shap": np.concatenate(
                    [
                        np.linspace(-2.0, 0.0, 12),
                        np.linspace(-1.0, 1.0, 12),
                        np.linspace(0.0, 2.0, 12),
                    ]
                ),
                "severity_group": ["Low"] * 12 + ["Mid"] * 12 + ["High"] * 12,
            }
        )

        summary = MODULE.build_group_curve_summary(
            frame,
            x_col="pre",
            y_col="shap",
            group_col="severity_group",
            n_bins=6,
            min_bin_count=2,
        )

        self.assertGreaterEqual(len(summary), 12)
        self.assertSetEqual(set(summary["severity_group"].unique().tolist()), {"Low", "Mid", "High"})
        self.assertTrue((summary["point_count"] >= 2).all())


if __name__ == "__main__":
    unittest.main()
