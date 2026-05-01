from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "23_extract_prepeak_precip_only.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_extract_prepeak_precip_only", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TestExtractPrepeakPrecipOnly(unittest.TestCase):
    def test_patch_total_precipitation_to_prepeak_mean(self):
        class FakeModule:
            WINDOW_STATS = {
                "total_precipitation": {
                    "pre30": ("mean", "sum"),
                    "prepeak": ("mean",),
                    "recoverywin": ("sum", "mean"),
                }
            }

        MODULE.patch_total_precipitation_to_prepeak_mean(FakeModule)

        self.assertEqual(
            FakeModule.WINDOW_STATS["total_precipitation"],
            {"prepeak": ("mean",)},
        )


if __name__ == "__main__":
    unittest.main()
