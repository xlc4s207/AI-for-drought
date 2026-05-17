#!/usr/bin/env python3
"""Summarize annual latitude-area-weighted GPP recovery time for the all-season SMrz run."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Iterable

import netCDF4 as nc
import numpy as np


BASE = Path("/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results")
INPUT = BASE / "gpp_response_SMrz_events_global_v20260514_allseason_recovery_elapsed_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
OUTPUT_CSV = BASE / "gpp_allseason_recovery_weighted_annual_summary_20260514.csv"
OUTPUT_MD = BASE / "gpp_allseason_recovery_weighted_annual_summary_20260514.md"


def to_numpy(var):
    arr = var[:]
    if np.ma.isMaskedArray(arr):
        arr = arr.filled(np.nan)
    arr = np.asarray(arr)
    fill_value = getattr(var, "_FillValue", None)
    if fill_value is not None and np.issubdtype(arr.dtype, np.floating):
        arr[np.isclose(arr, float(fill_value), equal_nan=False)] = np.nan
    if np.issubdtype(arr.dtype, np.integer):
        arr = arr.astype(np.float64)
    return arr


def clean_nonnegative(values):
    arr = np.asarray(values, dtype=np.float64)
    arr[arr < 0] = np.nan
    return arr


def latitude_area_weights(latitudes: Iterable[float]) -> np.ndarray:
    lat = np.asarray(latitudes, dtype=np.float64)
    weights = np.cos(np.deg2rad(lat))
    weights[~np.isfinite(weights)] = np.nan
    weights[weights < 0] = np.nan
    return weights


def weighted_mean(values: Iterable[float], latitudes: Iterable[float]) -> float:
    arr = np.asarray(values, dtype=np.float64)
    weights = latitude_area_weights(latitudes)
    valid = np.isfinite(arr) & np.isfinite(weights) & (weights > 0)
    if not np.any(valid):
        return math.nan
    return float(np.average(arr[valid], weights=weights[valid]))


def main() -> None:
    if not INPUT.exists():
        raise FileNotFoundError(INPUT)

    with nc.Dataset(INPUT, "r") as ds:
        onset_year = to_numpy(ds.variables["onset_year"])
        lat = to_numpy(ds.variables["lat"])
        rec_peak = clean_nonnegative(to_numpy(ds.variables["t_recover_to_baseline_abs_peak"]))
        rec_total = clean_nonnegative(to_numpy(ds.variables["t_recover_to_baseline"]))
        response = to_numpy(ds.variables["response_detected"]) == 1

    valid_rec = np.isfinite(rec_peak)
    years = np.unique(onset_year[np.isfinite(onset_year)])
    rows = []
    for year in years.astype(int):
        year_mask = np.isfinite(onset_year) & (onset_year == year)
        year_lat = lat[year_mask]
        peak_vals = rec_peak[year_mask]
        total_vals = rec_total[year_mask]
        resp_vals = response[year_mask]
        valid_mask = np.isfinite(peak_vals)
        rows.append(
            {
                "year": int(year),
                "event_count": int(year_mask.sum()),
                "response_count": int(np.sum(resp_vals)),
                "recovery_count": int(np.sum(valid_mask)),
                "recovery_ratio": float(np.sum(valid_mask) / year_mask.sum()) if year_mask.sum() else math.nan,
                "weighted_mean_recovery_peak_days": weighted_mean(peak_vals, year_lat),
                "median_recovery_peak_days": float(np.nanmedian(peak_vals)) if np.any(valid_mask) else math.nan,
                "weighted_mean_recovery_total_days": weighted_mean(total_vals, year_lat),
                "median_recovery_total_days": float(np.nanmedian(total_vals)) if np.any(np.isfinite(total_vals)) else math.nan,
            }
        )

    rows.sort(key=lambda r: r["year"])

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# GPP 全年骤旱恢复时间逐年面积加权汇总",
        "",
        f"- 输入文件: `{INPUT}`",
        "- 权重: `cos(lat)` 纬度面积权重",
        "- 主指标: `t_recover_to_baseline_abs_peak`",
        "- 口径: 全年事件，无生长季筛选，恢复时间按实际经过天数计",
        "",
        "| 年份 | 事件数 | 响应数 | 恢复数 | 恢复率 | 面积加权均值(峰值到恢复) | 中位数(峰值到恢复) | 面积加权均值(总恢复) | 中位数(总恢复) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['year']} | {row['event_count']:,} | {row['response_count']:,} | {row['recovery_count']:,} | "
            f"{row['recovery_ratio']:.4f} | {row['weighted_mean_recovery_peak_days']:.3f} | "
            f"{row['median_recovery_peak_days']:.3f} | {row['weighted_mean_recovery_total_days']:.3f} | "
            f"{row['median_recovery_total_days']:.3f} |"
        )
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(OUTPUT_CSV)
    print(OUTPUT_MD)


if __name__ == "__main__":
    main()
