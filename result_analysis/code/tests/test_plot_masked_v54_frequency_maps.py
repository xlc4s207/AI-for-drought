import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np


MODULE_PATH = Path("/home/xulc/flash_drought/process/result_analysis/code/plot_masked_v54_frequency_maps.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("plot_masked_v54_frequency_maps", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PlotMaskedV54FrequencyMapsTests(unittest.TestCase):
    def test_event_count_to_plot_array_masks_nonpositive_values(self):
        mod = _load_module()
        arr = np.array([[5, 0, -1], [2, 3, -1]], dtype=np.int16)
        out = mod.event_count_to_plot_array(arr)
        self.assertTrue(np.isfinite(out[0, 0]))
        self.assertTrue(np.isnan(out[0, 1]))
        self.assertTrue(np.isnan(out[0, 2]))
        self.assertEqual(float(out[1, 1]), 3.0)

    def test_choose_imshow_origin_uses_lower_for_ascending_latitudes(self):
        mod = _load_module()
        lat = np.array([-89.875, -89.625, -89.375, -89.125], dtype=np.float32)
        self.assertEqual(mod.choose_imshow_origin(lat), "lower")

    def test_choose_imshow_origin_uses_upper_for_descending_latitudes(self):
        mod = _load_module()
        lat = np.array([89.875, 89.625, 89.375, 89.125], dtype=np.float32)
        self.assertEqual(mod.choose_imshow_origin(lat), "upper")


if __name__ == "__main__":
    unittest.main()
