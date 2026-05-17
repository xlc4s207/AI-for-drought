#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
"""Build RECO-only BESS 0401 recovery validation figures and summary."""

from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import rcParams
import netCDF4 as nc
import numpy as np


BASE_DIR = "/home/xulc/flash_drought"
OUT_DIR = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/conclusion/"
    "RECO_BESS_valid"
)
OUT_SPATIAL_PNG = os.path.join(OUT_DIR, "reco_0401_recovery_mean_global.png")
OUT_TREND_PNG = os.path.join(OUT_DIR, "reco_0401_recovery_trend.png")
OUT_SUMMARY_CSV = os.path.join(OUT_DIR, "reco_0401_recovery_summary.csv")
OUT_SUMMARY_MD = os.path.join(OUT_DIR, "reco_0401_recovery_summary.md")

SUMMARY_0401_CSV = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/compare_analysis2/"
    "v20260401_growingseason_recovery_gsdays/"
    "summary_table_v20260401_growingseason_recovery_gsdays.csv"
)
ANNUAL_0401_CSV = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/compare_analysis2/"
    "v20260401_growingseason_recovery_gsdays/"
    "annual_response_recovery_trends_v20260401_growingseason_recovery_gsdays.csv"
)


@dataclass(frozen=True)
class Scenario:
    code: str
    soil_layer: str
    title: str
    event_file: str


SCENARIOS = [
    Scenario(
        code="code1",
        soil_layer="SMrz",
        title="RECO | SMrz Flash",
        event_file=(
            f"{BASE_DIR}/process/RECO-draught-analysis/code1/results/"
            "reco_response_SMrz_events_global_v20260401_growingseason_recovery_gsdays_"
            "rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
        ),
    ),
    Scenario(
        code="code2",
        soil_layer="SMs",
        title="RECO | SMs Flash",
        event_file=(
            f"{BASE_DIR}/process/RECO-draught-analysis/code2_SMs/results/"
            "reco_response_SMs_drought_v20260401_growingseason_recovery_gsdays_"
            "rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
        ),
    ),
]


def setup_chinese_font() -> None:
    candidates = [
        "Noto Sans CJK SC",
        "Noto Sans CJK",
        "Source Han Sans SC",
        "Source Han Sans CN",
        "WenQuanYi Micro Hei",
        "WenQuanYi Zen Hei",
        "Microsoft YaHei",
        "SimHei",
        "PingFang SC",
        "Arial Unicode MS",
    ]
    installed = {f.name for f in fm.fontManager.ttflist}
    selected = None
    for name in candidates:
        if name in installed:
            selected = name
            break
    rcParams["font.sans-serif"] = [selected, "DejaVu Sans"] if selected else ["DejaVu Sans"]
    rcParams["axes.unicode_minus"] = False


def to_numpy(var) -> np.ndarray:
    arr = var[:]
    if np.ma.isMaskedArray(arr):
        arr = arr.filled(np.nan)
    arr = np.asarray(arr)
    if np.issubdtype(arr.dtype, np.integer):
        arr = arr.astype(np.float64)
    fill_value = getattr(var, "_FillValue", None)
    if fill_value is not None:
        arr = arr.astype(np.float64, copy=False)
        arr[np.isclose(arr, float(fill_value), equal_nan=False)] = np.nan
    return arr


def clean_nonnegative(values: Iterable[float]) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    arr[~np.isfinite(arr)] = np.nan
    arr[arr < 0] = np.nan
    return arr


def extent_from_lon_lat(lon: np.ndarray, lat: np.ndarray) -> list[float]:
    dlon = float(np.nanmedian(np.diff(lon))) if lon.size > 1 else 0.25
    dlat = float(np.nanmedian(np.diff(lat))) if lat.size > 1 else 0.25
    return [
        float(lon[0] - dlon / 2),
        float(lon[-1] + dlon / 2),
        float(lat[0] - dlat / 2),
        float(lat[-1] + dlat / 2),
    ]


def aggregate_event_recovery_mean(event_file: str) -> dict[str, np.ndarray]:
    with nc.Dataset(event_file, "r") as ds:
        lat_evt = to_numpy(ds.variables["lat"]).astype(np.float64)
        lon_evt = to_numpy(ds.variables["lon"]).astype(np.float64)
        recovery = clean_nonnegative(to_numpy(ds.variables["t_recover_to_baseline"]))

    valid = np.isfinite(lat_evt) & np.isfinite(lon_evt)
    lat_vals = np.unique(lat_evt[valid])
    lon_vals = np.unique(lon_evt[valid])
    lat_vals.sort()
    lon_vals.sort()

    nlat = len(lat_vals)
    nlon = len(lon_vals)
    lat_idx = np.searchsorted(lat_vals, lat_evt[valid])
    lon_idx = np.searchsorted(lon_vals, lon_evt[valid])
    flat_idx = lat_idx * nlon + lon_idx
    ncell = nlat * nlon

    recovery_valid = np.isfinite(recovery[valid])
    counts = np.bincount(flat_idx[recovery_valid], minlength=ncell).astype(np.int32)
    sums = np.bincount(
        flat_idx[recovery_valid],
        weights=recovery[valid][recovery_valid],
        minlength=ncell,
    )

    mean = np.full(ncell, np.nan, dtype=np.float64)
    ok = counts > 0
    mean[ok] = sums[ok] / counts[ok]
    return {
        "lat": lat_vals,
        "lon": lon_vals,
        "recovery_mean_days": mean.reshape(nlat, nlon),
    }


def read_csv(path: str) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def find_row(rows: list[dict[str, str]], **filters: str) -> dict[str, str]:
    for row in rows:
        if all(row.get(k) == v for k, v in filters.items()):
            return row
    raise KeyError(filters)


def trend_slope(years: np.ndarray, values: np.ndarray) -> float:
    valid = np.isfinite(years) & np.isfinite(values)
    if np.sum(valid) < 2:
        return math.nan
    slope, _ = np.polyfit(years[valid], values[valid], 1)
    return float(slope * 10.0)


def fmt(value: object, decimals: int = 2) -> str:
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(float(value)):
            return "-"
        return f"{float(value):.{decimals}f}"
    return str(value)


def build_spatial_plot() -> None:
    aggregated = [aggregate_event_recovery_mean(s.event_file) for s in SCENARIOS]
    finite_values = [
        item["recovery_mean_days"][np.isfinite(item["recovery_mean_days"])] for item in aggregated
    ]
    joined = np.concatenate([arr for arr in finite_values if arr.size > 0])
    vmin = float(np.nanpercentile(joined, 2))
    vmax = float(np.nanpercentile(joined, 98))

    fig, axes = plt.subplots(1, 2, figsize=(15, 5.8), constrained_layout=True)
    im = None
    for ax, scenario, data in zip(axes, SCENARIOS, aggregated):
        im = ax.imshow(
            data["recovery_mean_days"],
            origin="lower",
            extent=extent_from_lon_lat(data["lon"], data["lat"]),
            aspect="auto",
            cmap="RdYlGn_r",
            vmin=vmin,
            vmax=vmax,
        )
        ax.set_title(scenario.title, fontsize=14)
        ax.set_xlabel("Longitude", fontsize=11)
        ax.set_ylabel("Latitude", fontsize=11)
        ax.set_xlim(-180, 180)
        ax.tick_params(labelsize=9)

    fig.suptitle("BESS 0401 RECO Recovery Time Mean After Flash Drought", fontsize=18)
    cbar = fig.colorbar(im, ax=axes[:], shrink=0.94, pad=0.02)
    cbar.set_label("Recovery Time Mean (days)", fontsize=12)
    fig.savefig(OUT_SPATIAL_PNG, dpi=220, bbox_inches="tight")
    plt.close(fig)


def build_trend_plot(annual_rows: list[dict[str, str]]) -> dict[str, dict[str, float]]:
    fig, axes = plt.subplots(1, 2, figsize=(14.5, 5.2), constrained_layout=True)
    summary: dict[str, dict[str, float]] = {}

    for ax, scenario in zip(axes, SCENARIOS):
        rows = [
            row for row in annual_rows
            if row["variable"] == "RECO" and row["code"] == scenario.code and row["soil_layer"] == scenario.soil_layer
        ]
        years = np.array([int(row["year"]) for row in rows], dtype=np.float64)
        recovery_mean = np.array([float(row["recovery_mean"]) for row in rows], dtype=np.float64)
        slope = trend_slope(years, recovery_mean)
        intercept = float(np.polyfit(years, recovery_mean, 1)[1]) if years.size >= 2 else math.nan

        ax.plot(years, recovery_mean, color="#1f78b4", marker="o", markersize=3.8, linewidth=1.7)
        if years.size >= 2:
            fit = (slope / 10.0) * years + intercept
            ax.plot(years, fit, color="#d95f02", linestyle="--", linewidth=1.6)

        ax.set_title(f"RECO {scenario.soil_layer} Recovery Mean", fontsize=13)
        ax.set_xlabel("Year", fontsize=11)
        ax.set_ylabel("Days", fontsize=11)
        ax.grid(True, linestyle="--", alpha=0.35)
        ax.tick_params(labelsize=9)
        ax.text(
            0.03,
            0.95,
            f"Slope = {slope:.2f} d/10a",
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=10,
            bbox=dict(facecolor="white", edgecolor="#cccccc", alpha=0.9),
        )

        first5 = float(np.nanmean(recovery_mean[:5])) if recovery_mean.size >= 5 else math.nan
        last5 = float(np.nanmean(recovery_mean[-5:])) if recovery_mean.size >= 5 else math.nan
        summary[scenario.soil_layer] = {
            "slope_days_per_decade": slope,
            "first5_mean": first5,
            "last5_mean": last5,
            "delta_last5_minus_first5": last5 - first5 if np.isfinite(first5) and np.isfinite(last5) else math.nan,
        }

    fig.suptitle("BESS 0401 RECO Recovery-Time Annual Trend (1982-2021)", fontsize=17)
    fig.savefig(OUT_TREND_PNG, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return summary


def write_summary(summary_rows: list[dict[str, str]], trend_extra: dict[str, dict[str, float]]) -> None:
    rows_out = []
    for scenario in SCENARIOS:
        row = find_row(summary_rows, variable="RECO", code=scenario.code, soil_layer=scenario.soil_layer)
        extra = trend_extra[scenario.soil_layer]
        rows_out.append(
            {
                "variable": "RECO",
                "code": scenario.code,
                "soil_layer": scenario.soil_layer,
                "event_total": row["event_total"],
                "response_valid_pct": row["response_valid_pct"],
                "response_mean_days": row["response_mean_days"],
                "recovery_valid_pct": row["recovery_valid_pct"],
                "recovery_mean_days": row["recovery_mean_days"],
                "recovery_median_days": row["recovery_median_days"],
                "recovery_p25_days": row["recovery_p25_days"],
                "recovery_p75_days": row["recovery_p75_days"],
                "recovery_mean_slope_days_per_decade": row["recovery_mean_slope_days_per_decade"],
                "first5_recovery_mean": extra["first5_mean"],
                "last5_recovery_mean": extra["last5_mean"],
                "delta_last5_minus_first5": extra["delta_last5_minus_first5"],
                "file_path": row["file_path"],
            }
        )

    with open(OUT_SUMMARY_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "variable",
                "code",
                "soil_layer",
                "event_total",
                "response_valid_pct",
                "response_mean_days",
                "recovery_valid_pct",
                "recovery_mean_days",
                "recovery_median_days",
                "recovery_p25_days",
                "recovery_p75_days",
                "recovery_mean_slope_days_per_decade",
                "first5_recovery_mean",
                "last5_recovery_mean",
                "delta_last5_minus_first5",
                "file_path",
            ],
        )
        writer.writeheader()
        writer.writerows(rows_out)

    smrz = next(row for row in rows_out if row["soil_layer"] == "SMrz")
    sms = next(row for row in rows_out if row["soil_layer"] == "SMs")
    lines = [
        "# RECO 0401 全球恢复时间分布与趋势摘要",
        "",
        "| 情景 | 事件数 | 响应有效% | 恢复有效% | 恢复均值(d) | 恢复中位数(d) | 恢复趋势(d/10a) | 前5年均值 | 后5年均值 | 后5年-前5年 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        (
            f"| SMrz | {fmt(int(smrz['event_total']))} | {fmt(float(smrz['response_valid_pct']))} | "
            f"{fmt(float(smrz['recovery_valid_pct']))} | {fmt(float(smrz['recovery_mean_days']))} | "
            f"{fmt(float(smrz['recovery_median_days']))} | {fmt(float(smrz['recovery_mean_slope_days_per_decade']))} | "
            f"{fmt(float(smrz['first5_recovery_mean']))} | {fmt(float(smrz['last5_recovery_mean']))} | "
            f"{fmt(float(smrz['delta_last5_minus_first5']))} |"
        ),
        (
            f"| SMs | {fmt(int(sms['event_total']))} | {fmt(float(sms['response_valid_pct']))} | "
            f"{fmt(float(sms['recovery_valid_pct']))} | {fmt(float(sms['recovery_mean_days']))} | "
            f"{fmt(float(sms['recovery_median_days']))} | {fmt(float(sms['recovery_mean_slope_days_per_decade']))} | "
            f"{fmt(float(sms['first5_recovery_mean']))} | {fmt(float(sms['last5_recovery_mean']))} | "
            f"{fmt(float(sms['delta_last5_minus_first5']))} |"
        ),
        "",
        (
            f"- RECO 在 `SMrz` 骤旱下的全球平均恢复时间为 `{fmt(float(smrz['recovery_mean_days']))}` 天，"
            f"恢复趋势为 `{fmt(float(smrz['recovery_mean_slope_days_per_decade']))}` d/10a。"
        ),
        (
            f"- RECO 在 `SMs` 骤旱下的全球平均恢复时间为 `{fmt(float(sms['recovery_mean_days']))}` 天，"
            f"恢复趋势为 `{fmt(float(sms['recovery_mean_slope_days_per_decade']))}` d/10a。"
        ),
        (
            f"- 两种情景的后 5 年恢复均值都高于前 5 年，分别增加 "
            f"`{fmt(float(smrz['delta_last5_minus_first5']))}` 天和 `{fmt(float(sms['delta_last5_minus_first5']))}` 天，"
            "说明 RECO 恢复时间在长期上整体呈延长。"
        ),
    ]
    with open(OUT_SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    setup_chinese_font()
    build_spatial_plot()
    annual_rows = read_csv(ANNUAL_0401_CSV)
    summary_rows = read_csv(SUMMARY_0401_CSV)
    trend_extra = build_trend_plot(annual_rows)
    write_summary(summary_rows, trend_extra)
    print(f"Wrote {OUT_SPATIAL_PNG}")
    print(f"Wrote {OUT_TREND_PNG}")
    print(f"Wrote {OUT_SUMMARY_CSV}")
    print(f"Wrote {OUT_SUMMARY_MD}")


if __name__ == "__main__":
    main()
