import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd


MODULE_PATH = Path("/home/xulc/flash_drought/process/result_analysis/code/analyze_drought_v54_threeclass.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("analyze_drought_v54_threeclass", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DroughtV54ThreeclassAnalysisTests(unittest.TestCase):
    def test_build_summary_rows_computes_share_and_means(self):
        mod = _load_module()
        metrics = {
            ("SMs", "rapid_1to4"): {"count": 20, "duration_sum": 200.0, "intensity_sum": 50.0},
            ("SMs", "flash_5to20"): {"count": 30, "duration_sum": 450.0, "intensity_sum": 120.0},
            ("SMs", "slow_gt20"): {"count": 50, "duration_sum": 1000.0, "intensity_sum": 300.0},
            ("SMs", "dry_to_drier"): {"count": 10, "duration_sum": 300.0, "intensity_sum": 40.0},
        }
        df = mod.build_summary_dataframe(metrics)
        main = df[df["event_type"].isin(["rapid_1to4", "flash_5to20", "slow_gt20"])].copy()
        main = main.sort_values("event_type")

        self.assertEqual(main["event_count"].tolist(), [30, 20, 50])
        self.assertTrue(np.allclose(main["share_of_main_classes"].to_numpy(), np.array([0.3, 0.2, 0.5])))
        self.assertTrue(np.allclose(main["duration_mean"].to_numpy(), np.array([15.0, 10.0, 20.0])))
        self.assertTrue(np.allclose(main["intensity_mean"].to_numpy(), np.array([4.0, 2.5, 6.0])))

    def test_plot_dataframe_order_matches_soil_then_category(self):
        mod = _load_module()
        df = pd.DataFrame(
            {
                "soil_layer": ["SMrz", "SMs", "SMrz", "SMs"],
                "event_type": ["slow_gt20", "flash_5to20", "rapid_1to4", "slow_gt20"],
                "scenario_cn": ["SMrz->20天", "SMs-5-20天", "SMrz-1-4天", "SMs->20天"],
                "event_count": [5, 6, 7, 8],
                "share_of_main_classes": [0.2, 0.3, 0.4, 0.5],
                "duration_mean": [10.0, 11.0, 12.0, 13.0],
                "intensity_mean": [1.0, 2.0, 3.0, 4.0],
            }
        )
        ordered = mod.sort_summary_dataframe(df)
        self.assertEqual(
            ordered["scenario_cn"].tolist(),
            ["SMs-5-20天", "SMs->20天", "SMrz-1-4天", "SMrz->20天"],
        )


if __name__ == "__main__":
    unittest.main()
