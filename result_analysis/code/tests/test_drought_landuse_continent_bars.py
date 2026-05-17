import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np


MODULE_PATH = Path("/home/xulc/flash_drought/process/result_analysis/code/analyze_drought_landuse_continent_bars.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("analyze_drought_landuse_continent_bars", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DroughtLanduseContinentBarTests(unittest.TestCase):
    def test_scenario_builder_returns_four_scenarios(self):
        mod = _load_module()
        scenarios = mod.build_scenarios()
        self.assertEqual(len(scenarios), 4)
        labels = {(s.soil_layer, s.drought_type) for s in scenarios}
        self.assertEqual(labels, {("SMs", "flash"), ("SMs", "nonflash"), ("SMrz", "flash"), ("SMrz", "nonflash")})

    def test_metric_specs_cover_duration_intensity_frequency(self):
        mod = _load_module()
        self.assertEqual(set(mod.METRIC_SPECS.keys()), {"duration", "intensity", "frequency"})
        self.assertEqual(mod.METRIC_SPECS["duration"].source_var, "duration_mean")
        self.assertEqual(mod.METRIC_SPECS["frequency"].source_var, "mean_annual_frequency")

    def test_landuse_group_mapping_matches_approved_scheme(self):
        mod = _load_module()
        self.assertEqual(mod.LANDUSE_GROUP_LABELS, ["森林", "灌丛", "稀树草原", "草地", "湿地", "农田"])
        classes = np.array([[1, 6, 8, 10, 11, 12, 15]], dtype=np.int16)
        grouped = mod.merge_landuse_classes(classes)
        self.assertEqual(grouped.tolist(), [[1, 2, 3, 4, 5, 6, 0]])

    def test_continent_mask_uses_six_continents(self):
        mod = _load_module()
        lat = np.array([45.0, -15.0, 50.0, 0.0, 35.0, -25.0, -75.0], dtype=np.float32)
        lon = np.array([-100.0, -60.0, 10.0, 20.0, 110.0, 135.0, 0.0], dtype=np.float32)
        code = mod.build_continent_code(lat, lon)
        self.assertEqual(code.shape, (7, 7))
        self.assertEqual(code[0, 0], 1)
        self.assertEqual(code[1, 1], 2)
        self.assertEqual(code[2, 2], 3)
        self.assertEqual(code[3, 3], 4)
        self.assertEqual(code[4, 4], 5)
        self.assertEqual(code[5, 5], 6)
        self.assertEqual(code[6, 0], 7)
        self.assertEqual(mod.PLOT_CONTINENT_CODES, [1, 2, 3, 4, 5, 6])

    def test_area_weighted_mean_uses_valid_values_only(self):
        mod = _load_module()
        data = np.array([[1.0, np.nan], [3.0, 5.0]], dtype=np.float64)
        lat_weights = np.array([[1.0, 1.0], [2.0, 2.0]], dtype=np.float64)
        mean_value, pixel_count = mod.area_weighted_mean(data, lat_weights)
        expected = (1.0 * 1.0 + 3.0 * 2.0 + 5.0 * 2.0) / (1.0 + 2.0 + 2.0)
        self.assertAlmostEqual(mean_value, expected)
        self.assertEqual(pixel_count, 3)


if __name__ == "__main__":
    unittest.main()
