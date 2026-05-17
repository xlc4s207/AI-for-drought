#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
from dataclasses import dataclass
from glob import glob
from pathlib import Path

import netCDF4 as nc
import numpy as np


FILE_RE = re.compile(r"FluxSat_GPP_(\d{4})(\d{2})_0\.25deg\.nc$")
DEFAULT_INPUT_DIR = (
    "/home/xulc/flash_drought/process/fluxsat-draught-analysis/preprocess/results/monthly_025deg"
)
DEFAULT_OUTPUT = (
    "/home/xulc/flash_drought/process/fluxsat-draught-analysis/preprocess/results/"
    "FluxSat_GPP_2000_2019_0.25deg.nc"
)
DEFAULT_REPORT = (
    "/home/xulc/flash_drought/process/fluxsat-draught-analysis/analysis/"
    "fluxsat_monthly_inventory_2000_2019.md"
)


@dataclass(frozen=True)
class MonthlyFile:
    year: int
    month: int
    path: str


def ensure_parent(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def discover_monthly_files(input_dir: str, start_year: int, end_year: int) -> list[MonthlyFile]:
    items: list[MonthlyFile] = []
    for path in sorted(glob(os.path.join(input_dir, "FluxSat_GPP_*_0.25deg.nc"))):
        m = FILE_RE.search(os.path.basename(path))
        if not m:
            continue
        year = int(m.group(1))
        month = int(m.group(2))
        if start_year <= year <= end_year:
            items.append(MonthlyFile(year=year, month=month, path=path))
    if not items:
        raise FileNotFoundError(f"no resampled FluxSat monthly files found in {input_dir}")
    return items


def write_inventory_report(report_path: str, items: list[MonthlyFile], observed_days: dict[tuple[int, int], int]) -> None:
    ensure_parent(report_path)
    lines = [
        "# FluxSat 2000-2019 月文件盘点（0.25deg）",
        "",
        f"- 月文件数: {len(items)}",
        f"- 首文件: `{os.path.basename(items[0].path)}`",
        f"- 末文件: `{os.path.basename(items[-1].path)}`",
        "",
        "| 年 | 月 | 实际天数 | 文件 |",
        "| --- | ---: | ---: | --- |",
    ]
    for item in items:
        lines.append(
            f"| {item.year} | {item.month:02d} | {observed_days[(item.year, item.month)]} | `{os.path.basename(item.path)}` |"
        )
    Path(report_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def copy_attrs(src_var, dst_var, skip: set[str] | None = None) -> None:
    skip = skip or set()
    for attr in src_var.ncattrs():
        if attr in skip:
            continue
        dst_var.setncattr(attr, src_var.getncattr(attr))


def create_output_dataset(template_path: str, output_path: str, total_days: int, complevel: int) -> nc.Dataset:
    ensure_parent(output_path)
    with nc.Dataset(template_path, "r") as src:
        lat = np.asarray(src.variables["lat"][:], dtype=np.float32)
        lon = np.asarray(src.variables["lon"][:], dtype=np.float32)

    dst = nc.Dataset(output_path, "w", format="NETCDF4")
    dst.createDimension("time", total_days)
    dst.createDimension("lat", lat.size)
    dst.createDimension("lon", lon.size)

    time_var = dst.createVariable("time", "f8", ("time",))
    lat_var = dst.createVariable("lat", "f4", ("lat",))
    lon_var = dst.createVariable("lon", "f4", ("lon",))
    gpp_var = dst.createVariable(
        "GPP",
        "f4",
        ("time", "lat", "lon"),
        zlib=complevel > 0,
        complevel=complevel,
        fill_value=np.float32(np.nan),
        chunksizes=(1, min(200, lat.size), min(200, lon.size)),
    )
    unc_var = dst.createVariable(
        "GPP_uncertainty",
        "f4",
        ("time", "lat", "lon"),
        zlib=complevel > 0,
        complevel=complevel,
        fill_value=np.float32(np.nan),
        chunksizes=(1, min(200, lat.size), min(200, lon.size)),
    )
    brdf_var = dst.createVariable(
        "BRDF_Quality",
        "f4",
        ("time", "lat", "lon"),
        zlib=complevel > 0,
        complevel=complevel,
        fill_value=np.float32(np.nan),
        chunksizes=(1, min(200, lat.size), min(200, lon.size)),
    )
    pct_var = dst.createVariable(
        "Percent_Inputs",
        "f4",
        ("time", "lat", "lon"),
        zlib=complevel > 0,
        complevel=complevel,
        fill_value=np.float32(np.nan),
        chunksizes=(1, min(200, lat.size), min(200, lon.size)),
    )
    lat_var[:] = lat
    lon_var[:] = lon
    time_var.units = "days since 2000-01-01 00:00:00"
    time_var.calendar = "standard"
    lat_var.units = "degrees_north"
    lon_var.units = "degrees_east"
    gpp_var.units = "g m-2 d-1"
    unc_var.units = "g m-2 d-1"
    dst.title = "FluxSat GPP 2000-2019 merged daily 0.25 degree file"
    dst.source = "Merged from monthly 0.25 degree FluxSat files"
    return dst


def total_days_for_year_range(start_year: int, end_year: int) -> int:
    start = dt.date(start_year, 1, 1)
    end = dt.date(end_year, 12, 31)
    return (end - start).days + 1


def expected_time_axis(start_year: int, end_year: int) -> np.ndarray:
    return np.arange(total_days_for_year_range(start_year, end_year), dtype=np.float64)


def merge_files(
    items: list[MonthlyFile],
    output_path: str,
    report_path: str,
    start_year: int,
    end_year: int,
    force: bool,
    complevel: int,
) -> None:
    if os.path.exists(output_path):
        if not force:
            raise FileExistsError(f"output already exists: {output_path}")
        os.remove(output_path)

    observed_days: dict[tuple[int, int], int] = {}
    total_days = total_days_for_year_range(start_year, end_year)
    for item in items:
        with nc.Dataset(item.path, "r") as ds:
            n_days = int(ds.dimensions["time"].size)
            observed_days[(item.year, item.month)] = n_days

    dst = create_output_dataset(items[0].path, output_path, total_days, complevel)
    try:
        dst.variables["time"][:] = expected_time_axis(start_year, end_year)
        for item in items:
            print(f"[merge] {item.year}-{item.month:02d} <- {item.path}", flush=True)
            with nc.Dataset(item.path, "r") as src:
                src_time = np.asarray(src.variables["time"][:], dtype=np.float64)
                if src_time.size == 0:
                    continue
                time_index = np.floor(src_time).astype(np.int64)
                if np.any(time_index < 0) or np.any(time_index >= total_days):
                    raise ValueError(
                        f"monthly file has time values outside target year range: {item.path}"
                    )
                if np.unique(time_index).size != time_index.size:
                    raise ValueError(f"monthly file has duplicate time values: {item.path}")
                for name in ["GPP", "GPP_uncertainty", "BRDF_Quality", "Percent_Inputs"]:
                    dst.variables[name][time_index, ...] = src.variables[name][:]
        dst.sync()
    finally:
        dst.close()

    write_inventory_report(report_path, items, observed_days)
    print(f"[done] merged {len(items)} files -> {output_path}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge monthly 0.25deg FluxSat files into a continuous daily file.")
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR)
    parser.add_argument("--start-year", type=int, default=2000)
    parser.add_argument("--end-year", type=int, default=2019)
    parser.add_argument("--output-path", default=DEFAULT_OUTPUT)
    parser.add_argument("--report-path", default=DEFAULT_REPORT)
    parser.add_argument("--complevel", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    items = discover_monthly_files(args.input_dir, args.start_year, args.end_year)
    merge_files(
        items,
        args.output_path,
        args.report_path,
        args.start_year,
        args.end_year,
        args.force,
        max(0, min(args.complevel, 9)),
    )


if __name__ == "__main__":
    main()
