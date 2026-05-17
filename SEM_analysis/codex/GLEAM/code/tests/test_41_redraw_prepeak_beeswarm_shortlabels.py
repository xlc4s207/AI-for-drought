from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "41_redraw_prepeak_beeswarm_shortlabels.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("redraw_prepeak_beeswarm_shortlabels", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TestRedrawPrepeakBeeswarmShortlabels(unittest.TestCase):
    def test_resolve_feature_order_uses_rank_order(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "feature_importance.csv"
            pd.DataFrame(
                {
                    "feature": ["prepeak_ssrd_mean", "event_duration", "prepeak_total_evaporation_mean"],
                    "importance": [3.0, 2.0, 1.0],
                    "rank": [2, 3, 1],
                }
            ).to_csv(csv_path, index=False)

            ordered = MODULE.resolve_feature_order(csv_path)

        self.assertEqual(
            ordered,
            ["prepeak_total_evaporation_mean", "prepeak_ssrd_mean", "event_duration"],
        )

    def test_prepare_beeswarm_inputs_keeps_event_and_prepeak_columns(self):
        sample_df = pd.DataFrame(
            {
                "prepeak_total_precipitation_mean": [0.1, 0.2, 0.3],
                "event_duration": [5, 7, 9],
                "missing_feature": [1, 2, 3],
            }
        )
        shap_df = pd.DataFrame(
            {
                "prepeak_total_precipitation_mean": [-1.0, 0.2, 0.5],
                "event_duration": [0.1, -0.3, 0.8],
            }
        )

        feature_frame, shap_matrix, feature_names = MODULE.prepare_beeswarm_inputs(
            sample_df=sample_df,
            shap_df=shap_df,
            feature_order=["prepeak_total_precipitation_mean", "event_duration", "missing_feature"],
            max_points=10,
        )

        self.assertEqual(feature_names, ["prepeak_total_precipitation_mean", "event_duration"])
        self.assertEqual(list(feature_frame.columns), feature_names)
        self.assertEqual(shap_matrix.shape, (3, 2))


if __name__ == "__main__":
    unittest.main()
