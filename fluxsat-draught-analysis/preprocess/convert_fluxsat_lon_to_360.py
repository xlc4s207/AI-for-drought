#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
from __future__ import annotations

import argparse
import os
from pathlib import Path

import netCDF4 as nc
import numpy as np


DEFAULT_INPUT = (
    "/home/xulc/flash_drought/process/fluxsat-draught-analysis/preprocess/results/"
    "FluxSat_GPP_2000_2019_daily_005deg.nc"
)
DEFAULT_OUTPUT = (
    "/home/xulc/flash_drought/process/fluxsat-draught-analysis/preprocess/results/"
    "FluxSat_GPP_2000_2019_daily_005deg_lon360.nc"
)


def ensure_parent(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def lon_to_360(lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    lon = np.asarray(lon, dtype=np.float32)
    converted = np.where(lon < 0.0, lon + 360.0, lon)
    order = np.argsort(converted, kind="mergesort")
    return converted[order], order


def copy_attrs(src_var, dst_var, skip: set[str] | None = None) -> None:
    skip = skip or set()
    for attr in src_var.ncattrs():
        if attr in skip:
            continue
        dst_var.setncattr(attr, src_var.getncattr(attr))


def convert_file(input_path: str, output_path: str, force: bool, complevel: int) -> None:
    if os.path.exists(output_path):
        if not force:
            raise FileExistsError(f"output already exists: {output_path}")
        os.remove(output_path)
    ensure_parent(output_path)

    with nc.Dataset(input_path, "r") as src, nc.Dataset(output_path, "w", format="NETCDF4") as dst:
        for dim_name, dim in src.dimensions.items():
            dst.createDimension(dim_name, len(dim))

        lon_sorted, order = lon_to_360(src.variables["lon"][:])

        time_var = dst.createVariable("time", src.variables["time"].dtype, ("time",))
        lat_var = dst.createVariable("lat", "f4", ("lat",))
        lon_var = dst.createVariable("lon", "f4", ("lon",))
        gpp_var = dst.createVariable(
            "GPP",
            "f4",
            ("time", "lat", "lon"),
            zlib=complevel > 0,
            complevel=complevel,
            fill_value=np.float32(-9999.0),
            chunksizes=(1, min(200, len(src.dimensions["lat"])), min(200, len(src.dimensions["lon"]))),
        )
        unc_var = dst.createVariable(
            "GPP_uncertainty",
            "f4",
            ("time", "lat", "lon"),
            zlib=complevel > 0,
            complevel=complevel,
            fill_value=np.float32(-9999.0),
            chunksizes=(1, min(200, len(src.dimensions["lat"])), min(200, len(src.dimensions["lon"]))),
        )
        brdf_var = dst.createVariable(
            "BRDF_Quality",
            "i1",
            ("time", "lat", "lon"),
            zlib=complevel > 0,
            complevel=complevel,
            fill_value=np.int8(-1),
            chunksizes=(1, min(200, len(src.dimensions["lat"])), min(200, len(src.dimensions["lon"]))),
        )
        pct_var = dst.createVariable(
            "Percent_Inputs",
            "i1",
            ("time", "lat", "lon"),
            zlib=complevel > 0,
            complevel=complevel,
            fill_value=np.int8(-1),
            chunksizes=(1, min(200, len(src.dimensions["lat"])), min(200, len(src.dimensions["lon"]))),
        )

        copy_attrs(src.variables["time"], time_var)
        copy_attrs(src.variables["lat"], lat_var, skip={"_FillValue"})
        copy_attrs(src.variables["lon"], lon_var, skip={"_FillValue"})
        copy_attrs(src.variables["GPP"], gpp_var, skip={"_FillValue"})
        copy_attrs(src.variables["GPP_uncertainty"], unc_var, skip={"_FillValue"})
        copy_attrs(src.variables["BRDF_Quality"], brdf_var, skip={"_FillValue"})
        copy_attrs(src.variables["Percent_Inputs"], pct_var, skip={"_FillValue"})

        time_var[:] = src.variables["time"][:]
        lat_var[:] = src.variables["lat"][:]
        lon_var[:] = lon_sorted

        for t0 in range(0, len(src.dimensions["time"]), 8):
            t1 = min(t0 + 8, len(src.dimensions["time"]))
            gpp_var[t0:t1, :, :] = np.asarray(src.variables["GPP"][t0:t1, :, :], dtype=np.float32)[:, :, order]
            unc_var[t0:t1, :, :] = np.asarray(src.variables["GPP_uncertainty"][t0:t1, :, :], dtype=np.float32)[:, :, order]
            brdf_var[t0:t1, :, :] = np.asarray(src.variables["BRDF_Quality"][t0:t1, :, :], dtype=np.int8)[:, :, order]
            pct_var[t0:t1, :, :] = np.asarray(src.variables["Percent_Inputs"][t0:t1, :, :], dtype=np.int8)[:, :, order]

        for attr in src.ncattrs():
            dst.setncattr(attr, src.getncattr(attr))
        dst.longitude_convention = "0_to_360"
        dst.history = f"{getattr(src, 'history', '')}; reordered longitudes to 0..360"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert merged FluxSat longitude from -180..180 to 0..360.")
    parser.add_argument("--input-path", default=DEFAULT_INPUT)
    parser.add_argument("--output-path", default=DEFAULT_OUTPUT)
    parser.add_argument("--complevel", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    convert_file(args.input_path, args.output_path, args.force, max(0, min(args.complevel, 9)))


if __name__ == "__main__":
    main()
