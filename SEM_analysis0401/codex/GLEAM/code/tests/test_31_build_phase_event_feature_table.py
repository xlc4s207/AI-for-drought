from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "31_build_phase_event_feature_table.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_build_phase_event_feature_table", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TestBuildPhaseEventFeatureTable(unittest.TestCase):
    def test_select_phase_feature_table_keeps_prepeak_and_event_inputs(self):
        source = pd.DataFrame(
            {
                "event_uid": [1],
                "metric": ["GPP"],
                "code_id": ["code1"],
                "biome": ["Forest"],
                "soil_layer": ["SMrz"],
                "drought_type": ["flash"],
                "lat": [10.0],
                "lon": [100.0],
                "t_recover_to_baseline_abs_peak": [12.0],
                "event_onset_days": [5.0],
                "event_duration": [18.0],
                "event_intensity": [2.5],
                "prepeak_total_precipitation_mean": [1.2],
                "prepeak_total_evaporation_mean": [0.8],
                "prepeak_temperature_2m_mean": [299.0],
                "prepeak_VPD_mean": [6.0],
                "prepeak_SMrz_mean": [0.21],
                "prepeak_lai_total_mean": [1.9],
                "prepeak_ssrd_mean": [120.0],
                "prepeak_strd_mean": [340.0],
                "prepeak_wind_speed_mean": [3.4],
                "shock_total_precipitation_mean": [0.4],
            }
        )

        out = MODULE.select_phase_feature_table(source, phase="prepeak")

        self.assertIn("prepeak_total_precipitation_mean", out.columns)
        self.assertIn("event_intensity", out.columns)
        self.assertNotIn("shock_total_precipitation_mean", out.columns)

    def test_select_phase_feature_table_keeps_shock_and_event_inputs(self):
        source = pd.DataFrame(
            {
                "event_uid": [1],
                "t_recover_to_baseline_abs_peak": [12.0],
                "event_onset_days": [5.0],
                "event_duration": [18.0],
                "event_intensity": [2.5],
                "shock_total_precipitation_mean": [0.5],
                "shock_total_evaporation_mean": [0.2],
                "shock_temperature_2m_mean": [301.0],
                "shock_VPD_mean": [9.0],
                "shock_SMrz_mean": [0.15],
                "shock_lai_total_mean": [1.1],
                "shock_ssrd_mean": [150.0],
                "shock_strd_mean": [355.0],
                "shock_wind_speed_mean": [4.2],
            }
        )

        out = MODULE.select_phase_feature_table(source, phase="shock")

        self.assertIn("shock_total_evaporation_mean", out.columns)
        self.assertIn("event_duration", out.columns)
        self.assertNotIn("prepeak_total_precipitation_mean", out.columns)

    def test_select_phase_feature_table_raises_for_missing_required_features(self):
        source = pd.DataFrame(
            {
                "event_uid": [1],
                "t_recover_to_baseline_abs_peak": [12.0],
                "event_onset_days": [5.0],
                "event_duration": [18.0],
                "event_intensity": [2.5],
                "prepeak_total_precipitation_mean": [1.2],
            }
        )

        with self.assertRaises(KeyError):
            MODULE.select_phase_feature_table(source, phase="prepeak")


if __name__ == "__main__":
    unittest.main()
