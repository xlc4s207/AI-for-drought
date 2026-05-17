#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
import argparse
import glob
import os
import re
import sys
from datetime import datetime, timedelta

import netCDF4 as nc
import numpy as np


DEFAULT_INPUT_DIR = "/data/era5_for_GRN/volunmetric_root_water"
DEFAULT_OUTPUT_DIR = "/data/era5_for_GRN/yearly"
DEFAULT_OUTPUT_NAME = "volumetric_root_soil_water_0p25deg_1980_2024.nc"
DEFAULT_GLOB = "volumetric_root_soil_water_0p25deg_*.nc"
DEFAULT_REGEX = r".*?(\d{4})\.nc$"
DEFAULT_VAR = "root_water"
DEFAULT_TITLE = "Root Zone Volumetric Soil Water 0.25 degree 1980-2024"
DEFAULT_DESCRIPTION = "Merged yearly ERA5 root-zone soil water files with unified time axis in days since 1980-01-01 00:00:00."


def log(message: str) -> None:
    print(message, flush=True)


def copy_attrs(src_var, dst_var, skip=None):
    skip = set(skip or [])
    for attr in src_var.ncattrs():
        if attr in skip:
            continue
        dst_var.setncattr(attr, src_var.getncattr(attr))


def collect_inputs(input_dir: str, glob_pattern: str, filename_regex: str):
    file_pattern = re.compile(filename_regex)
    files = []
    for path in sorted(glob.glob(os.path.join(input_dir, glob_pattern))):
        match = file_pattern.search(os.path.basename(path))
        if match:
            files.append((int(match.group(1)), path))
    if not files:
        raise FileNotFoundError(f"no yearly root-water files found in {input_dir}")
    return files


def build_time_values(year: int, length: int):
    base = datetime(1980, 1, 1)
    start = datetime(year, 1, 1)
    return np.arange((start - base).days, (start - base).days + length, dtype=np.int32)


def create_output(first_path: str, output_path: str, var_name: str, title: str, description: str):
    with nc.Dataset(first_path, "r") as src:
        dst = nc.Dataset(output_path, "w", format="NETCDF4")
        dst.createDimension("time", None)
        for dim_name in ("lat", "lon", "nbnd"):
            if dim_name in src.dimensions:
                dst.createDimension(dim_name, len(src.dimensions[dim_name]))

        lat_src = src.variables["lat"]
        lon_src = src.variables["lon"]
        time_src = src.variables["time"]
        root_src = src.variables[var_name]

        if "nbnd" in src.dimensions:
            lat_bnds_src = src.variables["lat_bnds"]
            lon_bnds_src = src.variables["lon_bnds"]
            lat_bnds_dst = dst.createVariable("lat_bnds", lat_bnds_src.dtype, lat_bnds_src.dimensions)
            lon_bnds_dst = dst.createVariable("lon_bnds", lon_bnds_src.dtype, lon_bnds_src.dimensions)
            copy_attrs(lat_bnds_src, lat_bnds_dst, skip={"_FillValue"})
            copy_attrs(lon_bnds_src, lon_bnds_dst, skip={"_FillValue"})
            lat_bnds_dst[:] = lat_bnds_src[:]
            lon_bnds_dst[:] = lon_bnds_src[:]

        if "area" in src.variables:
            area_src = src.variables["area"]
            area_dst = dst.createVariable("area", area_src.dtype, area_src.dimensions, zlib=True, complevel=1)
            copy_attrs(area_src, area_dst, skip={"_FillValue"})
            area_dst[:] = area_src[:]

        lat_dst = dst.createVariable("lat", lat_src.dtype, lat_src.dimensions)
        lon_dst = dst.createVariable("lon", lon_src.dtype, lon_src.dimensions)
        time_dst = dst.createVariable("time", np.int32, ("time",))
        root_dst = dst.createVariable(
            var_name,
            np.float32,
            ("time", "lat", "lon"),
            zlib=True,
            complevel=1,
            fill_value=np.nan,
            chunksizes=(1, len(src.dimensions["lat"]), len(src.dimensions["lon"])),
        )

        copy_attrs(lat_src, lat_dst, skip={"_FillValue"})
        copy_attrs(lon_src, lon_dst, skip={"_FillValue"})
        copy_attrs(root_src, root_dst, skip={"_FillValue"})
        copy_attrs(time_src, time_dst, skip={"units", "calendar", "long_name", "_FillValue"})

        lat_dst[:] = lat_src[:]
        lon_dst[:] = lon_src[:]
        time_dst.units = "days since 1980-01-01 00:00:00"
        time_dst.calendar = "gregorian"
        time_dst.long_name = "time"

        for attr in src.ncattrs():
            dst.setncattr(attr, src.getncattr(attr))
        dst.title = title
        dst.history = f"Created on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} with merge_era5_root_water_yearly.py"
        dst.input_file = first_path
        dst.description = description
        dst.spatial_resolution = "0.25 degree"
        return dst


def merge_files(input_dir: str, output_path: str, force: bool, glob_pattern: str, filename_regex: str, var_name: str, title: str, description: str):
    files = collect_inputs(input_dir, glob_pattern, filename_regex)
    if os.path.exists(output_path):
        if not force:
            raise FileExistsError(f"output already exists: {output_path}")
        os.remove(output_path)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    dst = create_output(files[0][1], output_path, var_name, title, description)

    offset = 0
    try:
        time_dst = dst.variables["time"]
        root_dst = dst.variables[var_name]
        for year, path in files:
            log(f"merging {year}: {path}")
            with nc.Dataset(path, "r") as src:
                root_src = src.variables[var_name]
                length = root_src.shape[0]
                time_vals = build_time_values(year, length)
                time_dst[offset : offset + length] = time_vals
                root_dst[offset : offset + length, :, :] = root_src[:, :, :]
                offset += length
        dst.sync()
    finally:
        dst.close()


def parse_args():
    parser = argparse.ArgumentParser(description="Merge yearly ERA5 root-water files into one time-concatenated NetCDF.")
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME)
    parser.add_argument("--glob-pattern", default=DEFAULT_GLOB)
    parser.add_argument("--filename-regex", default=DEFAULT_REGEX)
    parser.add_argument("--var-name", default=DEFAULT_VAR)
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--description", default=DEFAULT_DESCRIPTION)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    output_path = os.path.join(args.output_dir, args.output_name)
    merge_files(
        args.input_dir,
        output_path,
        args.force,
        args.glob_pattern,
        args.filename_regex,
        args.var_name,
        args.title,
        args.description,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        raise
