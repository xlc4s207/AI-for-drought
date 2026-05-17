#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
from __future__ import annotations

import argparse
import calendar
from datetime import datetime
import sys

import netCDF4 as nc
import numpy as np
import rasterio


def log(message: str) -> None:
    print(message, flush=True)


def _target_slice(year: int, month: int) -> tuple[int, int]:
    start = datetime(year, month, 1)
    base = datetime(year, 1, 1)
    start_idx = (start - base).days
    ndays = calendar.monthrange(year, month)[1]
    return start_idx, start_idx + ndays


def _maybe_reorient(data: np.ndarray, lat_vals: np.ndarray, lon_vals: np.ndarray) -> np.ndarray:
    oriented = data
    if lat_vals.size >= 2 and lat_vals[0] < lat_vals[-1]:
        oriented = oriented[:, ::-1, :]
    if lon_vals.size >= 2 and lon_vals[0] > lon_vals[-1]:
        oriented = oriented[:, :, ::-1]
    return oriented


def patch_month_from_tif(nc_path: str, tif_path: str, var_name: str, year: int, month: int) -> None:
    start_idx, end_idx = _target_slice(year, month)
    ndays = end_idx - start_idx

    with rasterio.open(tif_path) as tif_ds:
        tif_data = tif_ds.read()

    if tif_data.shape[0] != ndays:
        raise ValueError(f"TIFF band count {tif_data.shape[0]} does not match {year}-{month:02d} day count {ndays}")

    with nc.Dataset(nc_path, "r+") as ds:
        var = ds.variables[var_name]
        lat_vals = np.asarray(ds.variables["lat"][:])
        lon_vals = np.asarray(ds.variables["lon"][:])

        if var.shape[1] != tif_data.shape[1] or var.shape[2] != tif_data.shape[2]:
            raise ValueError(
                f"shape mismatch: nc spatial shape {(var.shape[1], var.shape[2])} vs tif {(tif_data.shape[1], tif_data.shape[2])}"
            )

        patched = _maybe_reorient(np.asarray(tif_data, dtype=var.dtype), lat_vals, lon_vals)
        log(f"patching {nc_path} month {year}-{month:02d} from {tif_path}")
        var[start_idx:end_idx, :, :] = patched
        ds.sync()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patch one bad ERA5 month in a yearly NetCDF using a daily multi-band TIFF.")
    parser.add_argument("--nc-path", required=True)
    parser.add_argument("--tif-path", required=True)
    parser.add_argument("--var-name", required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    patch_month_from_tif(
        nc_path=args.nc_path,
        tif_path=args.tif_path,
        var_name=args.var_name,
        year=args.year,
        month=args.month,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        raise
