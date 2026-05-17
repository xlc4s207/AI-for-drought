import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np


MODULE_PATH = Path("/home/xulc/flash_drought/process/result_analysis/code/mask_v54_event_nc_by_landuse.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("mask_v54_event_nc_by_landuse", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class MaskV54EventNcByLanduseTests(unittest.TestCase):
    def test_build_invalid_landuse_mask_marks_ice_and_barren(self):
        mod = _load_module()
        landuse = np.array(
            [
                [1, 15, 16],
                [12, 0, 5],
            ],
            dtype=np.int16,
        )
        mask = mod.build_invalid_landuse_mask(landuse)
        expected = np.array(
            [
                [False, True, True],
                [False, False, False],
            ],
            dtype=bool,
        )
        self.assertTrue(np.array_equal(mask, expected))

    def test_apply_spatial_mask_sets_fill_values_for_masked_pixels(self):
        mod = _load_module()
        spatial_mask = np.array(
            [
                [False, True, False],
                [True, False, True],
            ],
            dtype=bool,
        )
        count_arr = np.array(
            [
                [3, 4, 5],
                [6, 7, 8],
            ],
            dtype=np.int16,
        )
        short_cube = np.arange(12, dtype=np.int16).reshape(2, 2, 3)
        float_cube = np.arange(12, dtype=np.float32).reshape(2, 2, 3) / 10.0

        masked_count, masked_short, masked_float = mod.apply_spatial_mask_to_arrays(
            spatial_mask=spatial_mask,
            event_count=count_arr,
            short_data={"duration": short_cube.copy()},
            float_data={"intensity": float_cube.copy()},
        )

        self.assertEqual(int(masked_count[0, 1]), -1)
        self.assertEqual(int(masked_count[1, 0]), -1)
        self.assertEqual(int(masked_count[1, 2]), -1)
        self.assertEqual(int(masked_short["duration"][0, 0, 1]), -1)
        self.assertEqual(int(masked_short["duration"][1, 1, 0]), -1)
        self.assertAlmostEqual(float(masked_float["intensity"][0, 1, 2]), -9999.0)
        self.assertEqual(int(masked_count[0, 0]), 3)
        self.assertEqual(int(masked_short["duration"][0, 0, 0]), 0)
        self.assertAlmostEqual(float(masked_float["intensity"][1, 0, 0]), 0.6)

    def test_align_mask_to_latitude_order_flips_for_ascending_latitudes(self):
        mod = _load_module()
        lat = np.array([-10.0, 0.0, 10.0], dtype=np.float32)
        north_up_mask = np.array(
            [
                [15, 15],
                [0, 0],
                [16, 16],
            ],
            dtype=np.int16,
        )
        aligned = mod.align_mask_to_latitude_order(north_up_mask, lat)
        expected = np.array(
            [
                [16, 16],
                [0, 0],
                [15, 15],
            ],
            dtype=np.int16,
        )
        self.assertTrue(np.array_equal(aligned, expected))

    def test_align_mask_to_latitude_order_keeps_descending_latitudes(self):
        mod = _load_module()
        lat = np.array([10.0, 0.0, -10.0], dtype=np.float32)
        north_up_mask = np.array(
            [
                [15, 15],
                [0, 0],
                [16, 16],
            ],
            dtype=np.int16,
        )
        aligned = mod.align_mask_to_latitude_order(north_up_mask, lat)
        self.assertTrue(np.array_equal(aligned, north_up_mask))


if __name__ == "__main__":
    unittest.main()
