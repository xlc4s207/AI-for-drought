#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import netCDF4 as nc
import numpy as np


def log(message: str) -> None:
    print(message, flush=True)


def copy_attrs(src_var, dst_var, skip: set[str] | None = None) -> None:
    skip = skip or set()
    for attr in src_var.ncattrs():
        if attr in skip:
            continue
        dst_var.setncattr(attr, src_var.getncattr(attr))


def copy_static_variables(src, dst, var_name: str, deflate: int) -> None:
    for name, src_var in src.variables.items():
        if name in {var_name, "time"}:
            continue
        kwargs = {}
        if "_FillValue" in src_var.ncattrs():
            kwargs["fill_value"] = src_var.getncattr("_FillValue")
        if src_var.ndim > 0:
            kwargs["zlib"] = True
            kwargs["complevel"] = deflate
        dst_var = dst.createVariable(name, src_var.dtype, src_var.dimensions, **kwargs)
        copy_attrs(src_var, dst_var, skip={"_FillValue"})
        dst_var[:] = src_var[:]


def collect_inputs(input_dir: str, filename_regex: str, start_year: int, end_year: int) -> list[tuple[int, str]]:
    pattern = re.compile(filename_regex)
    files: list[tuple[int, str]] = []
    for path in sorted(Path(input_dir).glob("*.nc")):
        match = pattern.search(path.name)
        if not match:
            continue
        year = int(match.group(1))
        if start_year <= year <= end_year:
            files.append((year, str(path)))
    if not files:
        raise FileNotFoundError(f"no yearly attribute files found in {input_dir} matching {filename_regex}")
    return files


def build_time_values(base_year: int, year: int, length: int) -> np.ndarray:
    base = datetime(base_year, 1, 1)
    start = datetime(year, 1, 1)
    offset = (start - base).days
    return np.arange(offset, offset + length, dtype=np.int32)


def create_output(schema_path: str, output_path: str, var_name: str, title: str | None, deflate: int, base_year: int):
    with nc.Dataset(schema_path, "r") as src:
        dst = nc.Dataset(output_path, "w", format="NETCDF4")

        for dim_name, dim in src.dimensions.items():
            dst.createDimension(dim_name, None if dim_name == "time" else len(dim))

        copy_static_variables(src, dst, var_name, deflate)

        time_src = src.variables["time"]
        data_src = src.variables[var_name]

        time_dst = dst.createVariable("time", np.int32, ("time",))
        copy_attrs(time_src, time_dst, skip={"_FillValue", "units", "calendar"})
        time_dst.units = f"days since {base_year}-01-01 00:00:00"
        time_dst.calendar = getattr(time_src, "calendar", "gregorian")

        fill_value = data_src.getncattr("_FillValue") if "_FillValue" in data_src.ncattrs() else None
        data_dims = data_src.dimensions
        chunksizes = None
        if len(data_dims) == 3 and data_dims[0] == "time":
            lat_len = len(src.dimensions[data_dims[1]])
            lon_len = len(src.dimensions[data_dims[2]])
            chunksizes = (1, lat_len, lon_len)
        data_dst = dst.createVariable(
            var_name,
            data_src.dtype,
            data_dims,
            zlib=True,
            complevel=deflate,
            fill_value=fill_value,
            chunksizes=chunksizes,
        )
        copy_attrs(data_src, data_dst, skip={"_FillValue"})

        for attr in src.ncattrs():
            dst.setncattr(attr, src.getncattr(attr))
        if title:
            dst.title = title
        dst.history = f"Created on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} with merge_era5_attribute_yearly.py"
        dst.input_file = schema_path
        dst.spatial_resolution = "0.25 degree"
        return dst


def copy_seed(seed_path: str, dst, var_name: str, time_chunk: int = 366) -> int:
    with nc.Dataset(seed_path, "r") as seed:
        time_src = seed.variables["time"]
        data_src = seed.variables[var_name]
        length = int(data_src.shape[0])
        for start in range(0, length, time_chunk):
            stop = min(start + time_chunk, length)
            dst.variables["time"][start:stop] = time_src[start:stop]
            dst.variables[var_name][start:stop, :, :] = data_src[start:stop, :, :]
        return length


def merge_files(
    input_dir: str,
    output_path: str,
    force: bool,
    filename_regex: str,
    var_name: str,
    title: str | None,
    start_year: int,
    end_year: int,
    deflate: int,
    seed_path: str | None = None,
    time_chunk: int = 366,
) -> None:
    files = collect_inputs(input_dir, filename_regex, start_year, end_year)
    if os.path.exists(output_path):
        if not force:
            raise FileExistsError(f"output already exists: {output_path}")
        os.remove(output_path)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    schema_path = seed_path or files[0][1]
    dst = create_output(schema_path, output_path, var_name, title, deflate, start_year)
    offset = 0
    try:
        time_dst = dst.variables["time"]
        data_dst = dst.variables[var_name]
        if seed_path:
            log(f"seeding from existing file: {seed_path}")
            offset = copy_seed(seed_path, dst, var_name, time_chunk=time_chunk)
        for year, path in files:
            log(f"merging {year}: {path}")
            with nc.Dataset(path, "r") as src:
                data_src = src.variables[var_name]
                length = int(data_src.shape[0])
                for start in range(0, length, time_chunk):
                    stop = min(start + time_chunk, length)
                    out_start = offset + start
                    out_stop = offset + stop
                    time_dst[out_start:out_stop] = build_time_values(start_year, year, length)[start:stop]
                    data_dst[out_start:out_stop, :, :] = data_src[start:stop, :, :]
                offset += length
        dst.sync()
    finally:
        dst.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge yearly ERA5 attribute files into one time-concatenated NetCDF.")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--filename-regex", required=True)
    parser.add_argument("--var-name", required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--deflate", type=int, default=1)
    parser.add_argument("--seed-path")
    parser.add_argument("--time-chunk", type=int, default=366)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    merge_files(
        input_dir=args.input_dir,
        output_path=args.output_path,
        force=args.force,
        filename_regex=args.filename_regex,
        var_name=args.var_name,
        title=args.title or None,
        start_year=args.start_year,
        end_year=args.end_year,
        deflate=args.deflate,
        seed_path=args.seed_path,
        time_chunk=args.time_chunk,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        raise
