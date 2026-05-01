from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "24_plot_recovery_pre_shap_colored_by_duration.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_pre_shap_colored_by_duration", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TestRecoveryPreShapColoredByDuration(unittest.TestCase):
    def test_build_panels_uses_same_viridis_colormap_for_both_panels(self):
        panels = MODULE.build_panels(np.array([1.0]), np.array([2.0]))

        self.assertEqual(len(panels), 2)
        self.assertEqual(panels[0][2], "viridis")
        self.assertEqual(panels[1][2], "viridis")
        self.assertEqual(panels[1][1], "|t_impact|")
        self.assertFalse(panels[0][3])
        self.assertTrue(panels[1][3])


if __name__ == "__main__":
    unittest.main()
