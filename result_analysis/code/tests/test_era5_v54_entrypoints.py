import importlib.util
from pathlib import Path
import sys
import unittest


def _load_module(path_str: str, module_name: str):
    path = Path(path_str)
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class Era5V54EntrypointsTests(unittest.TestCase):
    def test_surface_entrypoint_uses_expected_era5_file_and_var(self):
        mod = _load_module(
            "/home/xulc/flash_drought/process/process2/main_parallel_ERA5_swvl1_v5.4.py",
            "main_parallel_ERA5_swvl1_v54",
        )
        self.assertEqual(
            mod.SM_FILE,
            "/data/era5_for_GRN/yearly/volumetric_soil_water_layer_1_0p25deg_1980_2024.nc",
        )
        self.assertEqual(mod.SM_VAR, "swvl1")
        self.assertIn("ERA5L_swvl1_result_v5.4_0p25deg", mod.RESULT_DIR)

    def test_root_entrypoint_uses_expected_era5_file_and_var(self):
        mod = _load_module(
            "/home/xulc/flash_drought/process/process2/main_parallel_ERA5_root_v5.4.py",
            "main_parallel_ERA5_root_v54",
        )
        self.assertEqual(
            mod.SM_FILE,
            "/data/era5_for_GRN/yearly/volumetric_root_soil_water_0p25deg_1980_2024.nc",
        )
        self.assertEqual(mod.SM_VAR, "root_water")
        self.assertIn("ERA5L_root_result_v5.4_0p25deg", mod.RESULT_DIR)


if __name__ == "__main__":
    unittest.main()
