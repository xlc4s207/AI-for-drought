#!/usr/bin/env python3
import argparse
import calendar
import os
import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta

import netCDF4 as nc
import numpy as np
import rasterio


FILE_RE = re.compile(r".*_(\d{4})_(\d{2})\.tif$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge monthly ERA5L dewpoint GeoTIFF files into yearly NetCDF files.",
    )
    parser.add_argument(
        "--input-dir",
        default="/data/era5_for_GRN/era5_dewpoint_2mtem",
        help="Directory containing monthly tif files.",
    )
    parser.add_argument(
        "--output-dir",
        default="/data/era5_for_GRN/total_dewpoint_tem_nc",
        help="Directory where yearly netCDF files are written.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output files.",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=None,
        help="Optional start year filter.",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=None,
        help="Optional end year filter.",
    )
    parser.add_argument(
        "--complevel",
        type=int,
        default=1,
        help="NetCDF compression level 0-9 (0 disables compression).",
    )
    return parser.parse_args()


def build_year_month_map(input_dir: str) -> dict[int, dict[int, str]]:
    year_month_map: dict[int, dict[int, str]] = defaultdict(dict)
    for name in sorted(os.listdir(input_dir)):
        if not name.endswith(".tif"):
            continue
        match = FILE_RE.match(name)
        if not match:
            continue
        year = int(match.group(1))
        month = int(match.group(2))
        year_month_map[year][month] = os.path.join(input_dir, name)
    return dict(year_month_map)


def make_lon_lat(transform: rasterio.Affine, width: int, height: int) -> tuple[np.ndarray, np.ndarray]:
    lon = transform.c + (np.arange(width) + 0.5) * transform.a
    lat = transform.f + (np.arange(height) + 0.5) * transform.e
    return lon.astype(np.float32), lat.astype(np.float32)


def write_year_nc(year: int, month_files: dict[int, str], output_path: str, complevel: int) -> None:
    with rasterio.open(month_files[min(month_files.keys())]) as ref:
        width = ref.width
        height = ref.height
        transform = ref.transform
        crs = ref.crs.to_string() if ref.crs is not None else ""

    lon, lat = make_lon_lat(transform, width, height)

    ds = nc.Dataset(output_path, "w", format="NETCDF4")
    try:
        ds.createDimension("time", None)
        ds.createDimension("lat", height)
        ds.createDimension("lon", width)

        time_var = ds.createVariable("time", "i4", ("time",))
        lat_var = ds.createVariable("lat", "f4", ("lat",))
        lon_var = ds.createVariable("lon", "f4", ("lon",))

        data_var = ds.createVariable(
            "dewpoint_temperature",
            "f4",
            ("time", "lat", "lon"),
            zlib=complevel > 0,
            complevel=complevel,
            chunksizes=(1, min(180, height), min(360, width)),
            fill_value=np.float32(np.nan),
        )

        time_var.units = "days since 1900-01-01 00:00:00"
        time_var.calendar = "gregorian"
        time_var.long_name = "time"

        lat_var.standard_name = "latitude"
        lat_var.units = "degrees_north"
        lon_var.standard_name = "longitude"
        lon_var.units = "degrees_east"

        data_var.long_name = "2m dewpoint temperature"
        data_var.units = "unknown"
        data_var.coordinates = "time lat lon"

        ds.title = f"ERA5L 2m dewpoint temperature daily data for {year}"
        ds.source = "Merged from monthly GeoTIFF files"
        ds.history = f"Created on {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} UTC"
        if crs:
            ds.crs = crs

        lat_var[:] = lat
        lon_var[:] = lon

        time_index = 0

        for month in sorted(month_files.keys()):
            tif_path = month_files[month]
            with rasterio.open(tif_path) as src:
                if src.width != width or src.height != height:
                    raise ValueError(f"Dimension mismatch in {tif_path}")

                expected_days = calendar.monthrange(year, month)[1]
                if src.count != expected_days:
                    print(
                        f"[WARN] {os.path.basename(tif_path)} has {src.count} bands, "
                        f"expected {expected_days} for {year}-{month:02d}."
                    )

                month_start = datetime(year, month, 1)
                for band in range(1, src.count + 1):
                    current_date = month_start + timedelta(days=band - 1)
                    time_var[time_index] = nc.date2num(
                        current_date,
                        units=time_var.units,
                        calendar=time_var.calendar,
                    )
                    data_var[time_index, :, :] = src.read(band, out_dtype=np.float32)
                    time_index += 1

        print(f"[OK] {year}: wrote {time_index} daily slices -> {output_path}")
    finally:
        ds.close()


def main() -> None:
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    year_month_map = build_year_month_map(args.input_dir)
    years = sorted(year_month_map.keys())

    if args.start_year is not None:
        years = [y for y in years if y >= args.start_year]
    if args.end_year is not None:
        years = [y for y in years if y <= args.end_year]

    if not years:
        print("[INFO] No files matched the provided filters.")
        return

    print(f"[INFO] Years found: {years[0]}-{years[-1]} (count={len(years)})")
    for year in years:
        month_files = year_month_map[year]
        missing = [m for m in range(1, 13) if m not in month_files]
        if missing:
            print(f"[WARN] {year}: missing months {missing}, skip")
            continue

        output_path = os.path.join(args.output_dir, f"dewpoint_temperature_{year}.nc")
        if os.path.exists(output_path) and not args.force:
            print(f"[SKIP] {year}: {output_path} exists (use --force to overwrite)")
            continue

        if os.path.exists(output_path):
            os.remove(output_path)

        write_year_nc(year, month_files, output_path, max(0, min(args.complevel, 9)))


if __name__ == "__main__":
    main()
