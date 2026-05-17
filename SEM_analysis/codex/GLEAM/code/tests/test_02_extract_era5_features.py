from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path
import unittest
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "02_extract_era5_features.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_extract_era5_features", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TestExtractEra5Features(unittest.TestCase):
    def test_resolve_era5_variable_specs_prefers_rechunked_root_when_available(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            yearly = root / "yearly"
            rechunked = root / "rechunked_spatial_20260402"
            yearly.mkdir()
            rechunked.mkdir()

            original_specs = {
                "temperature_2m": yearly / "temperature_2m_0p25deg_1980_2024.nc",
                "total_precipitation": yearly / "total_precipitation_0p25deg_1980_2024.nc",
            }
            for path in original_specs.values():
                path.write_text("")
            (rechunked / "temperature_2m_0p25deg_1980_2024_spatialchunks_py.nc").write_text("")
            (rechunked / "total_precipitation_0p25deg_1980_2024_spatialchunks_py.nc").write_text("")

            with mock.patch.object(MODULE, "ERA5_VARIABLE_SPECS", original_specs):
                resolved = MODULE.resolve_era5_variable_specs(
                    era5_root_dir=None,
                    era5_file_suffix="_spatialchunks_py.nc",
                )

            self.assertEqual(
                resolved["temperature_2m"],
                rechunked / "temperature_2m_0p25deg_1980_2024_spatialchunks_py.nc",
            )
            self.assertEqual(
                resolved["total_precipitation"],
                rechunked / "total_precipitation_0p25deg_1980_2024_spatialchunks_py.nc",
            )


if __name__ == "__main__":
    unittest.main()
