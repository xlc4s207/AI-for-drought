from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "34_build_reco_prepeak_event_source_table.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_build_reco_prepeak_event_source_table", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TestBuildRecoPrepeakEventSourceTable(unittest.TestCase):
    def test_merge_prepeak_feature_tables_keeps_required_columns(self):
        era5 = pd.DataFrame(
            {
                "event_uid": [1],
                "prepeak_total_precipitation_mean": [1.2],
                "prepeak_total_evaporation_mean": [0.8],
                "prepeak_temperature_2m_mean": [299.0],
                "prepeak_VPD_mean": [9.0],
                "prepeak_lai_total_mean": [2.1],
                "prepeak_ssrd_mean": [155.0],
                "prepeak_strd_mean": [325.0],
                "prepeak_wind_speed_mean": [3.4],
            }
        )
        sm = pd.DataFrame(
            {
                "event_uid": [1],
                "prepeak_SMrz_mean": [0.24],
                "shock_SMrz_mean": [0.15],
            }
        )

        out = MODULE.merge_prepeak_feature_tables(era5, sm)

        self.assertEqual(out.loc[0, "prepeak_SMrz_mean"], 0.24)
        self.assertIn("prepeak_total_evaporation_mean", out.columns)
        self.assertNotIn("shock_SMrz_mean", out.columns)

    def test_attach_prepeak_feature_columns_merges_required_inputs(self):
        base = pd.DataFrame(
            {
                "event_uid": [101, 102],
                "metric": ["RECO", "RECO"],
                "event_onset_days": [3.0, 5.0],
                "event_duration": [20.0, 25.0],
                "event_intensity": [0.4, 0.7],
                "t_recover_to_baseline_abs_peak": [18.0, 24.0],
            }
        )
        prepeak = pd.DataFrame(
            {
                "event_uid": [101, 102],
                "prepeak_total_precipitation_mean": [1.2, 1.5],
                "prepeak_total_evaporation_mean": [0.7, 0.8],
                "prepeak_temperature_2m_mean": [298.0, 299.0],
                "prepeak_VPD_mean": [9.1, 8.7],
                "prepeak_SMrz_mean": [0.22, 0.25],
                "prepeak_lai_total_mean": [2.0, 2.3],
                "prepeak_ssrd_mean": [150.0, 160.0],
                "prepeak_strd_mean": [320.0, 330.0],
                "prepeak_wind_speed_mean": [3.5, 3.1],
                "shock_temperature_2m_mean": [301.0, 302.0],
            }
        )

        out = MODULE.attach_prepeak_feature_columns(base, prepeak)

        self.assertEqual(out.loc[0, "prepeak_total_precipitation_mean"], 1.2)
        self.assertEqual(out.loc[1, "prepeak_wind_speed_mean"], 3.1)
        self.assertIn("event_duration", out.columns)
        self.assertIn("t_recover_to_baseline_abs_peak", out.columns)
        self.assertNotIn("shock_temperature_2m_mean", out.columns)

    def test_attach_prepeak_feature_columns_replaces_existing_prepeak_columns(self):
        base = pd.DataFrame(
            {
                "event_uid": [201],
                "prepeak_total_precipitation_mean": [-999.0],
                "t_recover_to_baseline_abs_peak": [22.0],
            }
        )
        prepeak = pd.DataFrame(
            {
                "event_uid": [201],
                "prepeak_total_precipitation_mean": [2.25],
                "prepeak_total_evaporation_mean": [0.95],
                "prepeak_temperature_2m_mean": [300.0],
                "prepeak_VPD_mean": [8.9],
                "prepeak_SMrz_mean": [0.18],
                "prepeak_lai_total_mean": [1.8],
                "prepeak_ssrd_mean": [140.0],
                "prepeak_strd_mean": [310.0],
                "prepeak_wind_speed_mean": [2.8],
            }
        )

        out = MODULE.attach_prepeak_feature_columns(base, prepeak)

        self.assertEqual(out.loc[0, "prepeak_total_precipitation_mean"], 2.25)


if __name__ == "__main__":
    unittest.main()
