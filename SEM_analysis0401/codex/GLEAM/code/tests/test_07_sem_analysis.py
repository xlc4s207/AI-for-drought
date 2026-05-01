from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "07_sem_analysis.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_sem_analysis", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TestSemAnalysis(unittest.TestCase):
    def test_filter_candidate_features_respects_include_and_exclude(self):
        features = [
            "recoverywin_temperature_2m_mean",
            "recoverywin_dewpoint_temperature_mean",
            "recoverywin_VPD_mean",
            "recoverywin_p_minus_et",
        ]
        filtered = MODULE.filter_candidate_features(
            features,
            include_features=[
                "recoverywin_temperature_2m_mean",
                "recoverywin_VPD_mean",
                "recoverywin_p_minus_et",
            ],
            exclude_features=["recoverywin_VPD_mean"],
        )
        self.assertEqual(
            filtered,
            ["recoverywin_temperature_2m_mean", "recoverywin_p_minus_et"],
        )

    def test_compute_target_equation_r2_returns_metrics(self):
        dataset = pd.DataFrame(
            {
                "target": np.linspace(0.0, 10.0, 60),
                "x1": np.linspace(1.0, 5.0, 60),
                "x2": np.linspace(-2.0, 2.0, 60),
            }
        )
        dataset["target"] = 1.5 * dataset["x1"] - 0.8 * dataset["x2"]
        metrics = MODULE.compute_target_equation_r2(dataset, "target ~ x1 + x2")
        self.assertIn("target_equation_r2_train_split", metrics)
        self.assertIn("target_equation_r2_holdout_split", metrics)
        self.assertEqual(metrics["target_equation_predictor_count"], 2)

    def test_compute_target_equation_r2_uses_named_target_equation_in_multiequation_spec(self):
        dataset = pd.DataFrame(
            {
                "mid": np.linspace(0.0, 5.0, 80),
                "x1": np.linspace(1.0, 4.0, 80),
                "x2": np.linspace(-2.0, 3.0, 80),
                "target": np.linspace(0.0, 1.0, 80),
            }
        )
        dataset["mid"] = 0.7 * dataset["x1"] - 0.2 * dataset["x2"]
        dataset["target"] = 1.3 * dataset["mid"] + 0.4 * dataset["x2"]
        metrics = MODULE.compute_target_equation_r2(
            dataset,
            "mid ~ x1 + x2\n"
            "target ~ mid + x2",
            target="target",
        )
        self.assertEqual(metrics["target_equation_lhs"], "target")
        self.assertEqual(metrics["target_equation_predictor_count"], 2)

    def test_validate_model_spec_scope_accepts_multiequation_prepeak_event_spec(self):
        spec = (
            "prepeak_SMrz_mean ~ prepeak_total_precipitation_mean + prepeak_total_evaporation_mean + prepeak_temperature_2m_mean\n"
            "prepeak_VPD_mean ~ prepeak_temperature_2m_mean + prepeak_total_evaporation_mean + prepeak_strd_mean\n"
            "prepeak_lai_total_mean ~ prepeak_SMrz_mean + prepeak_VPD_mean + prepeak_ssrd_mean + prepeak_strd_mean\n"
            "t_recover_to_baseline_abs_peak ~ prepeak_temperature_2m_mean + prepeak_total_evaporation_mean + prepeak_VPD_mean + prepeak_SMrz_mean + prepeak_lai_total_mean + event_onset_days + event_duration + event_intensity"
        )
        normalized = MODULE.validate_model_spec_scope(
            model_spec_text=spec,
            feature_scope="prepeak_event",
            target="t_recover_to_baseline_abs_peak",
        )
        self.assertIn("prepeak_SMrz_mean ~ prepeak_total_precipitation_mean", normalized)
        self.assertIn("t_recover_to_baseline_abs_peak ~ prepeak_temperature_2m_mean", normalized)


if __name__ == "__main__":
    unittest.main()
