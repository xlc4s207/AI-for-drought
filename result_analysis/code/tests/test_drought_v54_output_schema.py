import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

import netCDF4 as nc
import numpy as np


MODULE_PATH = Path("/home/xulc/flash_drought/process/process2/drought_core_v54_threeclass.py")
MODULE_DIR = str(MODULE_PATH.parent)


def _load_module():
    if MODULE_DIR not in sys.path:
        sys.path.insert(0, MODULE_DIR)
    spec = importlib.util.spec_from_file_location("drought_core_v54_threeclass", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DroughtV54OutputSchemaTests(unittest.TestCase):
    def test_init_netcdf_files_creates_days_below_p20_variable(self):
        mod = _load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            lat = np.array([10.0, 9.75], dtype=np.float32)
            lon = np.array([100.0, 100.25, 100.5], dtype=np.float32)
            paths = mod.init_netcdf_files(tmpdir, len(lat), len(lon), lat, lon, "SMs", "test")
            with nc.Dataset(paths["rapid_1to4"], "r") as ds:
                self.assertIn("days_below_p20", ds.variables)

    def test_write_row_events_persists_days_below_p20_values(self):
        mod = _load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            lat = np.array([10.0], dtype=np.float32)
            lon = np.array([100.0, 100.25], dtype=np.float32)
            paths = mod.init_netcdf_files(tmpdir, len(lat), len(lon), lat, lon, "SMs", "test")
            handles = {k: nc.Dataset(v, "r+") for k, v in paths.items()}
            try:
                result = {}
                for event_type in mod.OUTPUT_EVENT_TYPES:
                    result[f"{event_type}_events"] = []
                result["rapid_1to4_events"] = [
                    (
                        1,
                        [
                            {
                                "onset_start_year": 2001,
                                "onset_start_doy": 120,
                                "drought_start_year": 2001,
                                "drought_start_doy": 123,
                                "drought_end_year": 2001,
                                "drought_end_doy": 150,
                                "onset_days": 3,
                                "duration": 28,
                                "days_below_p20": 19,
                                "onset_drop": 0.8,
                                "onset_rate": 0.2667,
                                "intensity": 4.5,
                            }
                        ],
                    )
                ]
                mod.write_row_events_to_nc(handles, result, global_row=0, n_lon=len(lon))
                handles["rapid_1to4"].sync()
            finally:
                for ds in handles.values():
                    ds.close()

            with nc.Dataset(paths["rapid_1to4"], "r") as ds:
                saved = ds.variables["days_below_p20"][0, 0, 1]
                self.assertEqual(int(saved), 19)

    def test_init_netcdf_files_uses_source_label_in_metadata(self):
        mod = _load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            lat = np.array([10.0], dtype=np.float32)
            lon = np.array([100.0], dtype=np.float32)
            paths = mod.init_netcdf_files(tmpdir, len(lat), len(lon), lat, lon, "swvl1", "ERA5-Land swvl1 表层土壤湿度")
            with nc.Dataset(paths["rapid_1to4"], "r") as ds:
                self.assertIn("ERA5-Land", ds.source)


if __name__ == "__main__":
    unittest.main()
