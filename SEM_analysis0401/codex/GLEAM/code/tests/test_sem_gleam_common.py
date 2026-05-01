import unittest

import pandas as pd

from process.SEM_analysis.codex.GLEAM.code.sem_gleam_common import (
    DERIVED_FEATURE_NAMES,
    WINDOW_STATS,
    column_allowed_by_scope,
    finalize_feature_table,
)


class SemGleamCommonTests(unittest.TestCase):
    def test_window_stats_include_recoverywin_for_requested_variables(self):
        self.assertIn("recoverywin", WINDOW_STATS["surface_pressure"])
        self.assertIn("recoverywin", WINDOW_STATS["soil_temperature_level_2"])
        self.assertIn("recoverywin", WINDOW_STATS["soil_temperature_level_3"])
        self.assertIn("recoverywin", WINDOW_STATS["soil_temperature_level_4"])
        self.assertIn("mean", WINDOW_STATS["total_precipitation"]["recoverywin"])
        self.assertIn("mean", WINDOW_STATS["total_evaporation"]["recoverywin"])

    def test_window_stats_include_onset_to_peak_mean_features(self):
        self.assertIn("prepeak", WINDOW_STATS["temperature_2m"])
        self.assertIn("mean", WINDOW_STATS["temperature_2m"]["prepeak"])
        self.assertIn("prepeak", WINDOW_STATS["total_evaporation"])
        self.assertIn("mean", WINDOW_STATS["total_evaporation"]["prepeak"])
        self.assertIn("prepeak", WINDOW_STATS["SMrz"])
        self.assertIn("mean", WINDOW_STATS["SMrz"]["prepeak"])
        self.assertIn("mean", WINDOW_STATS["total_precipitation"]["shock"])
        self.assertIn("mean", WINDOW_STATS["total_evaporation"]["shock"])

    def test_finalize_feature_table_builds_depth_weighted_recoverywin_soil_temperature_mean(self):
        df = pd.DataFrame(
            {
                "event_uid": ["a", "b"],
                "recoverywin_soil_temperature_level_1_mean": [10.0, 15.0],
                "recoverywin_soil_temperature_level_2_mean": [20.0, 25.0],
                "recoverywin_soil_temperature_level_3_mean": [30.0, 35.0],
                "recoverywin_soil_temperature_level_4_mean": [40.0, 45.0],
            }
        )

        out = finalize_feature_table(df)

        self.assertIn("recoverywin_soil_temperature_weighted_mean", out.columns)
        self.assertAlmostEqual(out.loc[0, "recoverywin_soil_temperature_weighted_mean"], 35.32871972318339)
        self.assertAlmostEqual(out.loc[1, "recoverywin_soil_temperature_weighted_mean"], 40.32871972318339)

    def test_finalize_feature_table_backfills_recoverywin_flux_means_from_sums(self):
        df = pd.DataFrame(
            {
                "event_uid": ["a", "b"],
                "t_recover_to_baseline_abs_peak": [4.0, 1.0],
                "recoverywin_total_precipitation_sum": [10.0, 6.0],
                "recoverywin_total_evaporation_sum": [5.0, -2.0],
            }
        )

        out = finalize_feature_table(df)

        self.assertIn("recoverywin_total_precipitation_mean", out.columns)
        self.assertIn("recoverywin_total_evaporation_mean", out.columns)
        self.assertAlmostEqual(out.loc[0, "recoverywin_total_precipitation_mean"], 2.0)
        self.assertAlmostEqual(out.loc[1, "recoverywin_total_precipitation_mean"], 3.0)
        self.assertAlmostEqual(out.loc[0, "recoverywin_total_evaporation_mean"], 1.0)
        self.assertAlmostEqual(out.loc[1, "recoverywin_total_evaporation_mean"], -1.0)

    def test_finalize_feature_table_builds_prepeak_derived_features(self):
        df = pd.DataFrame(
            {
                "event_uid": ["a"],
                "prepeak_wind_u_10m_mean": [3.0],
                "prepeak_wind_v_10m_mean": [4.0],
                "prepeak_leaf_area_index_high_vegetation_mean": [1.5],
                "prepeak_leaf_area_index_low_vegetation_mean": [0.5],
                "prepeak_temperature_2m_mean": [300.15],
                "prepeak_dewpoint_temperature_mean": [295.15],
            }
        )

        out = finalize_feature_table(df)

        self.assertAlmostEqual(out.loc[0, "prepeak_wind_speed_mean"], 5.0)
        self.assertAlmostEqual(out.loc[0, "prepeak_lai_total_mean"], 2.0)
        self.assertIn("prepeak_VPD_mean", out.columns)
        self.assertGreater(out.loc[0, "prepeak_VPD_mean"], 0.0)

    def test_derived_feature_names_include_recoverywin_soil_temperature_mean(self):
        self.assertIn("recoverywin_soil_temperature_weighted_mean", DERIVED_FEATURE_NAMES)

    def test_phase_specific_feature_scopes_allow_matching_columns(self):
        self.assertTrue(column_allowed_by_scope("prepeak_total_precipitation_mean", "prepeak_event"))
        self.assertTrue(column_allowed_by_scope("event_intensity", "prepeak_event"))
        self.assertFalse(column_allowed_by_scope("shock_total_precipitation_mean", "prepeak_event"))
        self.assertTrue(column_allowed_by_scope("shock_total_precipitation_mean", "shock_event"))
        self.assertFalse(column_allowed_by_scope("recoverywin_total_precipitation_mean", "shock_event"))


if __name__ == "__main__":
    unittest.main()
