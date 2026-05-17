#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Range:
    start: int
    end: int


def compress_indices(indices: Iterable[int]) -> list[Range]:
    values = sorted(set(int(v) for v in indices))
    if not values:
        return []
    ranges: list[Range] = []
    start = values[0]
    prev = values[0]
    for value in values[1:]:
        if value == prev + 1:
            prev = value
            continue
        ranges.append(Range(start, prev))
        start = value
        prev = value
    ranges.append(Range(start, prev))
    return ranges


def _time_labels(time_var, bad_indices: list[int]) -> dict[int, str]:
    import netCDF4 as nc

    if not bad_indices:
        return {}
    try:
        values = time_var[bad_indices]
        dates = nc.num2date(values, units=time_var.units, calendar=getattr(time_var, "calendar", "standard"))
    except Exception:
        return {}
    labels: dict[int, str] = {}
    for idx, dt in zip(bad_indices, dates):
        if hasattr(dt, "strftime"):
            labels[idx] = dt.strftime("%Y-%m-%d")
        else:
            labels[idx] = str(dt)
    return labels


def format_ranges(ranges: list[Range], labels: dict[int, str]) -> str:
    parts: list[str] = []
    for item in ranges:
        if item.start == item.end:
            if item.start in labels:
                parts.append(f"{item.start}({labels[item.start]})")
            else:
                parts.append(str(item.start))
            continue
        start_label = labels.get(item.start)
        end_label = labels.get(item.end)
        if start_label and end_label:
            parts.append(f"{item.start}-{item.end}({start_label}~{end_label})")
        else:
            parts.append(f"{item.start}-{item.end}")
    return ",".join(parts)


def find_bad_time_indices(path: str, var_name: str, block_size: int = 30) -> list[int]:
    import netCDF4 as nc
    import numpy as np

    bad: list[int] = []
    with nc.Dataset(path) as ds:
        var = ds.variables[var_name]
        time_len = int(var.shape[0])
        for start in range(0, time_len, block_size):
            end = min(start + block_size, time_len)
            try:
                _ = np.asarray(var[start:end, :, :])
            except Exception:
                for idx in range(start, end):
                    try:
                        _ = np.asarray(var[idx : idx + 1, :, :])
                    except Exception:
                        bad.append(idx)
    return bad


def main() -> None:
    import netCDF4 as nc

    parser = argparse.ArgumentParser(description="Diagnose NetCDF time slices that trigger read errors.")
    parser.add_argument("--file", required=True, help="Input NetCDF file")
    parser.add_argument("--var", required=True, help="Variable name")
    parser.add_argument("--block-size", type=int, default=30, help="Coarse probe block size along time")
    args = parser.parse_args()

    bad_indices = find_bad_time_indices(args.file, args.var, args.block_size)
    with nc.Dataset(args.file) as ds:
        labels = _time_labels(ds.variables["time"], bad_indices) if "time" in ds.variables else {}
    ranges = compress_indices(bad_indices)
    print(format_ranges(ranges, labels) if ranges else "none")


if __name__ == "__main__":
    main()
