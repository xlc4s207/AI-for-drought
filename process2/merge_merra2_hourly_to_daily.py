#!/usr/bin/env python3
import argparse
import os
from typing import Iterable

import numpy as np
from netCDF4 import Dataset


def _copy_variable_attrs(src_var, dst_var) -> None:
    for attr in src_var.ncattrs():
        if attr == "_FillValue":
            continue
        dst_var.setncattr(attr, src_var.getncattr(attr))


def _copy_global_attrs(src_ds: Dataset, dst_ds: Dataset) -> None:
    for attr in src_ds.ncattrs():
        if attr.lower() in {"history", "nco"}:
            continue
        dst_ds.setncattr(attr, src_ds.getncattr(attr))


def convert_hourly_to_daily(src_path: str, dst_path: str, var_name: str) -> None:
    with Dataset(src_path, "r") as src:
        time_src = src.variables["time"]
        lat_src = src.variables["lat"]
        lon_src = src.variables["lon"]
        data_src = src.variables[var_name]

        time_vals = np.asarray(time_src[:], dtype=np.int64)
        order = np.argsort(time_vals)
        sorted_time = time_vals[order]
        day_ids = np.floor_divide(sorted_time, 1440)

        unique_days, start_idx, counts = np.unique(
            day_ids, return_index=True, return_counts=True
        )
        day_mid_minutes = unique_days * 1440 + 720

        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        with Dataset(dst_path, "w", format="NETCDF4") as dst:
            dst.createDimension("time", len(unique_days))
            dst.createDimension("lat", len(lat_src))
            dst.createDimension("lon", len(lon_src))

            time_dst = dst.createVariable("time", "i4", ("time",), zlib=True, complevel=4)
            lat_dst = dst.createVariable("lat", lat_src.dtype, ("lat",), zlib=True, complevel=4)
            lon_dst = dst.createVariable("lon", lon_src.dtype, ("lon",), zlib=True, complevel=4)

            fill_value = getattr(data_src, "_FillValue", np.float32(1e15))
            data_dst = dst.createVariable(
                var_name,
                "f4",
                ("time", "lat", "lon"),
                zlib=True,
                complevel=4,
                fill_value=fill_value,
                chunksizes=(1, len(lat_src), len(lon_src)),
            )

            _copy_variable_attrs(time_src, time_dst)
            _copy_variable_attrs(lat_src, lat_dst)
            _copy_variable_attrs(lon_src, lon_dst)
            _copy_variable_attrs(data_src, data_dst)
            _copy_global_attrs(src, dst)

            time_dst[:] = day_mid_minutes.astype(np.int32)
            lat_dst[:] = lat_src[:]
            lon_dst[:] = lon_src[:]

            if "time_increment" in time_dst.ncattrs():
                time_dst.setncattr("time_increment", 240000)
            if "RangeBeginningDate" in dst.ncattrs() and len(unique_days) > 0:
                dst.setncattr("RangeBeginningDate", str(int(unique_days[0])))

            for day_pos, (start, count) in enumerate(zip(start_idx, counts, strict=False)):
                idx = order[start : start + count]
                day_block = np.asarray(data_src[idx, :, :], dtype=np.float32)

                if np.isfinite(fill_value):
                    mask = day_block == np.float32(fill_value)
                else:
                    mask = np.zeros(day_block.shape, dtype=bool)

                day_block = np.where(mask, np.nan, day_block)
                with np.errstate(invalid="ignore"):
                    day_mean = np.nanmean(day_block, axis=0)
                day_mean = np.where(np.isnan(day_mean), np.float32(fill_value), day_mean).astype(np.float32)

                data_dst[day_pos, :, :] = day_mean


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert hourly MERRA2 SM files to daily mean NetCDF.")
    parser.add_argument("--smrz-in", required=True, help="Input SMrz hourly file")
    parser.add_argument("--sms-in", required=True, help="Input SMs hourly file")
    parser.add_argument("--out-dir", required=True, help="Output directory")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    smrz_out = os.path.join(args.out_dir, "SMrz_MERRA2_1980_2024_daily_mean.nc4")
    sms_out = os.path.join(args.out_dir, "SMs_MERRA2_1980_2024_daily_mean.nc4")

    convert_hourly_to_daily(args.smrz_in, smrz_out, "RZMC")
    convert_hourly_to_daily(args.sms_in, sms_out, "SFMC")

    print("Created:")
    print(smrz_out)
    print(sms_out)


if __name__ == "__main__":
    main()
