from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "22_build_reco_prepeak_precip_table.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_reco_prepeak_table", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TestBuildRecoPrepeakPrecipTable(unittest.TestCase):
    def test_attach_prepeak_precip_column_by_event_uid(self):
        base = pd.DataFrame(
            {
                "event_uid": [11, 12],
                "metric": ["RECO", "RECO"],
                "recoverywin_total_precipitation_mean": [1.2, 2.3],
            }
        )
        precip = pd.DataFrame(
            {
                "event_uid": [11, 12],
                "prepeak_total_precipitation_mean": [5.5, 6.5],
                "prepeak_total_precipitation_sum": [55.0, 65.0],
            }
        )

        out = MODULE.attach_prepeak_precip_column(base, precip)

        self.assertListEqual(
            out["prepeak_total_precipitation_mean"].tolist(),
            [5.5, 6.5],
        )
        self.assertListEqual(
            out["recoverywin_total_precipitation_mean"].tolist(),
            [1.2, 2.3],
        )

    def test_attach_prepeak_precip_column_replaces_existing_column(self):
        base = pd.DataFrame(
            {
                "event_uid": [21],
                "prepeak_total_precipitation_mean": [-999.0],
            }
        )
        precip = pd.DataFrame(
            {
                "event_uid": [21],
                "prepeak_total_precipitation_mean": [3.25],
            }
        )

        out = MODULE.attach_prepeak_precip_column(base, precip)

        self.assertEqual(out.loc[0, "prepeak_total_precipitation_mean"], 3.25)


if __name__ == "__main__":
    unittest.main()
