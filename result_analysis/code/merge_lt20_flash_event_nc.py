#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path

import netCDF4 as nc
import numpy as np


BASE_DIR = Path("/home/xulc/flash_drought/gleam/result")
TARGETS = [
    BASE_DIR / "SMs_result_v5.4_0p25deg",
    BASE_DIR / "SMrz_result_v5.4_0p25deg",
]

RAPID_NAME = "rapid_1to4_drought_events_v5.4.nc"
FLASH_NAME = "flash_5to20_drought_events_v5.4.nc"
OUT_NAME = "flash_lt20_drought_events_v5.4.nc"

SHORT_FILL = np.int16(-1)
FLOAT_FILL = np.float32(-9999.0)

SHORT_VARS = [
    "onset_start_year",
    "onset_start_doy",
    "drought_start_year",
    "drought_start_doy",
    "drought_end_year",
    "drought_end_doy",
    "onset_days",
    "duration",
    "days_below_p20",
]
FLOAT_VARS = [
    "onset_drop",
    "onset_rate",
    "intensity",
]


def _read_counts(ds: nc.Dataset) -> np.ndarray:
    counts = ds.variables["event_count"][:]
    if isinstance(counts, np.ma.MaskedArray):
        counts = counts.filled(0)
    counts = np.asarray(counts, dtype=np.int16)
    return np.where(counts < 0, 0, counts)


def _read_var(ds: nc.Dataset, name: str, fill_value):
    arr = ds.variables[name][:]
    if isinstance(arr, np.ma.MaskedArray):
        arr = arr.filled(fill_value)
    return np.asarray(arr)


def _sort_key(event: dict[str, float | int]) -> tuple[int, int, int, int]:
    return (
        int(event["drought_start_year"]),
        int(event["drought_start_doy"]),
        int(event["onset_days"]),
        int(event["duration"]),
    )


def merge_one_directory(result_dir: Path) -> tuple[Path, int, int]:
    rapid_path = result_dir / RAPID_NAME
    flash_path = result_dir / FLASH_NAME
    out_path = result_dir / OUT_NAME

    if not rapid_path.exists():
        raise FileNotFoundError(f"缺少文件: {rapid_path}")
    if not flash_path.exists():
        raise FileNotFoundError(f"缺少文件: {flash_path}")

    with nc.Dataset(rapid_path, "r") as rapid_ds, nc.Dataset(flash_path, "r") as flash_ds:
        lat = np.asarray(rapid_ds.variables["lat"][:], dtype=np.float32)
        lon = np.asarray(rapid_ds.variables["lon"][:], dtype=np.float32)

        rapid_counts = _read_counts(rapid_ds)
        flash_counts = _read_counts(flash_ds)
        combined_counts = rapid_counts.astype(np.int32) + flash_counts.astype(np.int32)
        max_combined_events = int(np.max(combined_counts))

        rapid_data = {}
        flash_data = {}
        for name in SHORT_VARS:
            rapid_data[name] = _read_var(rapid_ds, name, SHORT_FILL).astype(np.int16)
            flash_data[name] = _read_var(flash_ds, name, SHORT_FILL).astype(np.int16)
        for name in FLOAT_VARS:
            rapid_data[name] = _read_var(rapid_ds, name, FLOAT_FILL).astype(np.float32)
            flash_data[name] = _read_var(flash_ds, name, FLOAT_FILL).astype(np.float32)

        ny, nx = rapid_counts.shape
        merged_short = {
            name: np.full((max_combined_events, ny, nx), SHORT_FILL, dtype=np.int16)
            for name in SHORT_VARS
        }
        merged_float = {
            name: np.full((max_combined_events, ny, nx), FLOAT_FILL, dtype=np.float32)
            for name in FLOAT_VARS
        }

        total_events = 0
        for iy in range(ny):
            for ix in range(nx):
                nr = int(rapid_counts[iy, ix])
                nf = int(flash_counts[iy, ix])
                total = nr + nf
                if total == 0:
                    continue

                events: list[dict[str, float | int]] = []
                for src_data, n_src in ((rapid_data, nr), (flash_data, nf)):
                    for iev in range(n_src):
                        event = {name: src_data[name][iev, iy, ix] for name in SHORT_VARS}
                        event.update({name: src_data[name][iev, iy, ix] for name in FLOAT_VARS})
                        events.append(event)

                events.sort(key=_sort_key)
                total_events += total

                for iev, event in enumerate(events):
                    for name in SHORT_VARS:
                        merged_short[name][iev, iy, ix] = np.int16(event[name])
                    for name in FLOAT_VARS:
                        merged_float[name][iev, iy, ix] = np.float32(event[name])

    if out_path.exists():
        out_path.unlink()

    with nc.Dataset(out_path, "w", format="NETCDF4") as out_ds:
        out_ds.createDimension("lat", len(lat))
        out_ds.createDimension("lon", len(lon))
        out_ds.createDimension("max_events", max_combined_events)

        lat_var = out_ds.createVariable("lat", "f4", ("lat",))
        lon_var = out_ds.createVariable("lon", "f4", ("lon",))
        lat_var.units = "degrees_north"
        lon_var.units = "degrees_east"
        lat_var[:] = lat
        lon_var[:] = lon

        count_var = out_ds.createVariable(
            "event_count",
            "i2",
            ("lat", "lon"),
            zlib=True,
            complevel=4,
            fill_value=SHORT_FILL,
        )
        count_var[:] = combined_counts.astype(np.int16)

        for name in SHORT_VARS:
            var = out_ds.createVariable(
                name,
                "i2",
                ("max_events", "lat", "lon"),
                zlib=True,
                complevel=4,
                fill_value=SHORT_FILL,
            )
            var[:] = merged_short[name]

        for name in FLOAT_VARS:
            var = out_ds.createVariable(
                name,
                "f4",
                ("max_events", "lat", "lon"),
                zlib=True,
                complevel=4,
                fill_value=FLOAT_FILL,
            )
            var[:] = merged_float[name]

        with nc.Dataset(rapid_path, "r") as rapid_ds:
            out_ds.title = "flash_lt20 Drought Events Details v5.4"
            out_ds.source = getattr(rapid_ds, "source", "")
            out_ds.algorithm = "Two-step Method v5.4 (<20-day onset merged from rapid_1to4 + flash_5to20)"
            out_ds.percentile_baseline = getattr(rapid_ds, "percentile_baseline", "1981-2010")
            out_ds.percentile_window = getattr(rapid_ds, "percentile_window", "5 days (±2)")
            out_ds.onset_definition = "Flash drought defined as onset_days < 20 days"
            out_ds.merge_components = "rapid_1to4 + flash_5to20"

    return out_path, int(np.sum(combined_counts, dtype=np.int64)), max_combined_events


def main() -> None:
    print("开始合并 <20天骤旱 事件文件...")
    for result_dir in TARGETS:
        out_path, total_events, max_events = merge_one_directory(result_dir)
        print(f"[完成] {out_path}")
        print(f"  总事件数: {total_events}")
        print(f"  输出 max_events: {max_events}")


if __name__ == "__main__":
    main()
