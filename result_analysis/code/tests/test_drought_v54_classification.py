import importlib.util
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path("/home/xulc/flash_drought/process/process2/drought_event_v54_utils.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("drought_event_v54_utils", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DroughtV54ClassificationTests(unittest.TestCase):
    def test_onset_days_1_to_4_are_rapid(self):
        mod = _load_module()
        for onset_days in (1, 2, 3, 4):
            self.assertEqual(mod.classify_onset_days_v54(onset_days, has_onset_start=True), "rapid_1to4")

    def test_onset_days_5_to_20_are_flash(self):
        mod = _load_module()
        for onset_days in (5, 10, 20):
            self.assertEqual(mod.classify_onset_days_v54(onset_days, has_onset_start=True), "flash_5to20")

    def test_onset_days_above_20_are_slow(self):
        mod = _load_module()
        for onset_days in (21, 35, 90):
            self.assertEqual(mod.classify_onset_days_v54(onset_days, has_onset_start=True), "slow_gt20")

    def test_missing_onset_start_is_dry_to_drier(self):
        mod = _load_module()
        self.assertEqual(mod.classify_onset_days_v54(-1, has_onset_start=False), "dry_to_drier")

    def test_category_order_keeps_paper_plot_sequence(self):
        mod = _load_module()
        self.assertEqual(
            mod.EVENT_TYPE_ORDER,
            ["rapid_1to4", "flash_5to20", "slow_gt20", "dry_to_drier"],
        )


if __name__ == "__main__":
    unittest.main()
