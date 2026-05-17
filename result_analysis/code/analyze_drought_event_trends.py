#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Analyze per-pixel drought-event trend metrics for four scenarios:
1) SMs + flash
2) SMs + nonflash
3) SMrz + flash
4) SMrz + nonflash

Input files are expected at:
- <soil_dir>/flash_drought_events_v5.nc
- <soil_dir>/nonflash_drought_events_v5.nc

Outputs are written to:
- <soil_dir>/trend_analysis/<drought_type>/pixel_trend_metrics_v1.nc
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

import netCDF4 as nc
import numpy as np


DEFAULT_SOIL_DIRS = [
    "/home/xulc/flash_drought/gleam/clip_result/SMs_5.3",
    "/home/xulc/flash_drought/gleam/clip_result/SMrz_5.3",
]

DROUGHT_FILES = {
    "flash": "flash_drought_events_v5.nc",
    "nonflash": "nonflash_drought_events_v5.nc",
}

METRICS = ("duration", "intensity", "onset_rate", "onset_drop")


@dataclass(frozen=True)
class Scenario:
    soil_dir: str
    drought_type: str
    input_path: str
    output_dir: str
    output_path: str


def build_scenarios(soil_dirs: Iterable[str]) -> list[Scenario]:
    scenarios: list[Scenario] = []
    for soil_dir in soil_dirs:
        for drought_type, filename in DROUGHT_FILES.items():
            input_path = os.path.join(soil_dir, filename)
            output_dir = os.path.join(soil_dir, "trend_analysis", drought_type)
            output_path = os.path.join(output_dir, "pixel_trend_metrics_v1.nc")
            scenarios.append(
                Scenario(
                    soil_dir=soil_dir,
                    drought_type=drought_type,
                    input_path=input_path,
                    output_dir=output_dir,
                    output_path=output_path,
                )
            )
    return scenarios


def _filled_float_array(var_obj, slc: Tuple[slice, slice, slice]) -> np.ndarray:
    arr = var_obj[slc]
    if isinstance(arr, np.ma.MaskedArray):
        arr = arr.astype(np.float64).filled(np.nan)
    else:
        arr = np.asarray(arr, dtype=np.float64)
    fill = getattr(var_obj, "_FillValue", None)
    if fill is not None:
        arr[arr == fill] = np.nan
    return arr


def _write_2d(var_obj, data: np.ndarray, lat_slice: slice) -> None:
    var_obj[lat_slice, :] = data.astype(np.float32, copy=False)


def _compute_regression(
    years: np.ndarray,
    values: np.ndarray,
    min_events: int,
) -> Dict[str, np.ndarray]:
    valid = np.isfinite(years) & np.isfinite(values)

    x = np.where(valid, years, 0.0)
    y = np.where(valid, values, 0.0)

    n = valid.sum(axis=0).astype(np.float64)
    sx = x.sum(axis=0)
    sy = y.sum(axis=0)
    sxx = (x * x).sum(axis=0)
    syy = (y * y).sum(axis=0)
    sxy = (x * y).sum(axis=0)

    denom = n * sxx - sx * sx
    slope = np.full_like(denom, np.nan, dtype=np.float64)
    intercept = np.full_like(denom, np.nan, dtype=np.float64)
    r2 = np.full_like(denom, np.nan, dtype=np.float64)
    mean_value = np.full_like(denom, np.nan, dtype=np.float64)

    enough = n >= float(min_events)
    valid_denom = enough & np.isfinite(denom) & (np.abs(denom) > 0.0)

    slope[valid_denom] = (n[valid_denom] * sxy[valid_denom] - sx[valid_denom] * sy[valid_denom]) / denom[valid_denom]
    intercept[valid_denom] = (sy[valid_denom] - slope[valid_denom] * sx[valid_denom]) / n[valid_denom]
    mean_value[enough] = sy[enough] / n[enough]

    r_num = n * sxy - sx * sy
    r_den = (n * sxx - sx * sx) * (n * syy - sy * sy)
    good_r = valid_denom & np.isfinite(r_den) & (r_den > 0.0)
    r = np.full_like(denom, np.nan, dtype=np.float64)
    r[good_r] = r_num[good_r] / np.sqrt(r_den[good_r])
    r2[good_r] = r[good_r] * r[good_r]

    return {
        "slope": slope,
        "intercept": intercept,
        "r2": r2,
        "n_events_used": n,
        "mean": mean_value,
    }


def analyze_scenario(
    scenario: Scenario,
    min_events: int,
    lat_chunk: int,
    year_min: int,
    year_max: int,
    overwrite: bool,
    lat_start: int,
    lat_stop: int | None,
) -> None:
    if not os.path.exists(scenario.input_path):
        raise FileNotFoundError(f"Input file not found: {scenario.input_path}")

    os.makedirs(scenario.output_dir, exist_ok=True)
    if os.path.exists(scenario.output_path) and not overwrite:
        raise FileExistsError(
            f"Output exists: {scenario.output_path}. Use --overwrite to replace."
        )

    if os.path.exists(scenario.output_path):
        os.remove(scenario.output_path)

    print(f"[START] {scenario.drought_type} @ {scenario.soil_dir}")
    with nc.Dataset(scenario.input_path, "r") as src, nc.Dataset(scenario.output_path, "w", format="NETCDF4") as dst:
        nlat = len(src.dimensions["lat"])
        nlon = len(src.dimensions["lon"])

        dst.createDimension("lat", nlat)
        dst.createDimension("lon", nlon)

        lat_var = dst.createVariable("lat", "f4", ("lat",))
        lon_var = dst.createVariable("lon", "f4", ("lon",))
        lat_var[:] = src.variables["lat"][:]
        lon_var[:] = src.variables["lon"][:]
        lat_var.units = getattr(src.variables["lat"], "units", "degrees_north")
        lon_var.units = getattr(src.variables["lon"], "units", "degrees_east")

        out_vars: Dict[str, nc.Variable] = {}
        for metric in METRICS:
            out_vars[f"{metric}_slope"] = dst.createVariable(f"{metric}_slope", "f4", ("lat", "lon"), zlib=True, complevel=4, fill_value=np.float32(np.nan))
            out_vars[f"{metric}_intercept"] = dst.createVariable(f"{metric}_intercept", "f4", ("lat", "lon"), zlib=True, complevel=4, fill_value=np.float32(np.nan))
            out_vars[f"{metric}_r2"] = dst.createVariable(f"{metric}_r2", "f4", ("lat", "lon"), zlib=True, complevel=4, fill_value=np.float32(np.nan))
            out_vars[f"{metric}_n_events"] = dst.createVariable(f"{metric}_n_events", "f4", ("lat", "lon"), zlib=True, complevel=4, fill_value=np.float32(np.nan))
            out_vars[f"{metric}_mean"] = dst.createVariable(f"{metric}_mean", "f4", ("lat", "lon"), zlib=True, complevel=4, fill_value=np.float32(np.nan))

            out_vars[f"{metric}_slope"].units = f"{metric} units per year"
            out_vars[f"{metric}_intercept"].units = f"{metric} units"
            out_vars[f"{metric}_r2"].units = "1"
            out_vars[f"{metric}_n_events"].units = "count"
            out_vars[f"{metric}_mean"].units = f"{metric} units"

        dst.title = "Per-pixel drought event trend metrics"
        dst.source = getattr(src, "source", "")
        dst.algorithm = getattr(src, "algorithm", "")
        dst.period = f"{year_min}-{year_max}"
        dst.drought_type = scenario.drought_type
        dst.min_events = min_events
        dst.notes = "OLS trend on event-level values against drought_start_year."

        start_idx = max(0, lat_start)
        stop_idx = nlat if lat_stop is None else min(nlat, lat_stop)
        if start_idx >= stop_idx:
            raise ValueError(f"Invalid lat range: start={start_idx}, stop={stop_idx}, nlat={nlat}")

        for lat0 in range(start_idx, stop_idx, lat_chunk):
            lat1 = min(lat0 + lat_chunk, stop_idx)
            lat_slc = slice(lat0, lat1)

            years = _filled_float_array(src.variables["drought_start_year"], (slice(None), lat_slc, slice(None)))
            years[(years < year_min) | (years > year_max)] = np.nan

            for metric in METRICS:
                values = _filled_float_array(src.variables[metric], (slice(None), lat_slc, slice(None)))
                stat = _compute_regression(years=years, values=values, min_events=min_events)

                _write_2d(out_vars[f"{metric}_slope"], stat["slope"], lat_slc)
                _write_2d(out_vars[f"{metric}_intercept"], stat["intercept"], lat_slc)
                _write_2d(out_vars[f"{metric}_r2"], stat["r2"], lat_slc)
                _write_2d(out_vars[f"{metric}_n_events"], stat["n_events_used"], lat_slc)
                _write_2d(out_vars[f"{metric}_mean"], stat["mean"], lat_slc)

            print(f"  processed lat rows [{lat0}:{lat1}]")

    print(f"[DONE] {scenario.output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze per-pixel trends of drought event metrics.")
    parser.add_argument(
        "--soil-dirs",
        nargs="+",
        default=DEFAULT_SOIL_DIRS,
        help="Soil-layer result directories (default: SMs_5.3 and SMrz_5.3).",
    )
    parser.add_argument("--year-min", type=int, default=1980, help="Minimum year to include.")
    parser.add_argument("--year-max", type=int, default=2024, help="Maximum year to include.")
    parser.add_argument("--min-events", type=int, default=5, help="Minimum valid events per pixel.")
    parser.add_argument("--lat-chunk", type=int, default=50, help="Latitude chunk size.")
    parser.add_argument("--lat-start", type=int, default=0, help="Latitude start index (inclusive).")
    parser.add_argument("--lat-stop", type=int, default=None, help="Latitude stop index (exclusive).")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing outputs.")
    parser.add_argument("--dry-run", action="store_true", help="Only print scenarios without running.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scenarios = build_scenarios(args.soil_dirs)

    print("Scenarios:")
    for s in scenarios:
        print(f"  - {s.drought_type:8s} | {s.soil_dir} -> {s.output_path}")

    if args.dry_run:
        return

    for scenario in scenarios:
        analyze_scenario(
            scenario=scenario,
            min_events=args.min_events,
            lat_chunk=args.lat_chunk,
            year_min=args.year_min,
            year_max=args.year_max,
            overwrite=args.overwrite,
            lat_start=args.lat_start,
            lat_stop=args.lat_stop,
        )


if __name__ == "__main__":
    main()
