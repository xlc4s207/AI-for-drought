from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "03_extract_gleam_sm_features.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_extract_gleam_sm_features", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TestExtractGleamSmFeatures(unittest.TestCase):
    def test_build_phase_windows_includes_prepeak(self):
        onset_dates = np.array(["2001-06-01"], dtype="datetime64[D]")
        drought_dates = np.array(["2001-06-06"], dtype="datetime64[D]")
        peak_offsets = np.array([4], dtype=np.int32)
        recovery_offsets = np.array([10], dtype=np.int32)

        windows = MODULE.build_phase_windows(
            onset_dates,
            drought_dates,
            peak_offsets,
            recovery_offsets,
        )

        self.assertIn("prepeak", windows)
        prepeak_start, prepeak_end = windows["prepeak"]
        self.assertEqual(prepeak_start[0], np.datetime64("2001-06-01"))
        self.assertEqual(prepeak_end[0], np.datetime64("2001-06-10"))


if __name__ == "__main__":
    unittest.main()
