from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "21_batch_dependence_plots_fast.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_batch_dependence_fast", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TestBatchDependencePlotsFast(unittest.TestCase):
    def test_feature_labels_cover_onsetpeak_phase_and_event_inputs(self):
        self.assertEqual(
            MODULE.FEATURE_LABELS["prepeak_total_precipitation_mean"],
            "PRE(mean, prepeak)",
        )
        self.assertEqual(
            MODULE.FEATURE_LABELS["shock_total_precipitation_mean"],
            "PRE(mean, shock)",
        )
        self.assertEqual(MODULE.FEATURE_LABELS["event_onset_days"], "Onset days")
        self.assertEqual(MODULE.FEATURE_LABELS["event_duration"], "Event duration")
        self.assertEqual(MODULE.FEATURE_LABELS["event_intensity"], "Event intensity")


if __name__ == "__main__":
    unittest.main()
