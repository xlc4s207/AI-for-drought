#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass
from typing import Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import rcParams
import netCDF4 as nc
import numpy as np


BASE_DIR = "/home/xulc/flash_drought"
START_YEAR = 2000
END_YEAR = 2019
OUT_DIR = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/fluxsat_compare_analysis2/"
    "bess0328_vs_fluxsat0401_rec120cap_2000_2019"
)
SUMMARY_CSV = os.path.join(OUT_DIR, "bess0328_vs_fluxsat0401_rec120cap_summary.csv")
SUMMARY_MD = os.path.join(OUT_DIR, "bess0328_vs_fluxsat0401_rec120cap_summary.md")
ANNUAL_CSV = os.path.join(OUT_DIR, "bess0328_vs_fluxsat0401_rec120cap_annual.csv")
FIGURE_PATH = os.path.join(OUT_DIR, "bess0328_vs_fluxsat0401_rec120cap_response_recovery.png")


@dataclass(frozen=True)
class Item:
    source: str
    code: str
    soil_layer: str
    file_path: str


ITEMS: List[Item] = [
    Item(
        "BESS 0328",
        "code1",
        "SMrz",
        f"{BASE_DIR}/process/GPP-draught-analysis/code1/results/"
        "gpp_response_SMrz_events_global_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
    ),
    Item(
        "FluxSat 0401 rec120cap",
        "code1",
        "SMrz",
        f"{BASE_DIR}/process/fluxsat-draught-analysis/code1/results/"
        "fluxsat_gpp_response_SMrz_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec120cap.nc",
    ),
    Item(
        "BESS 0328",
        "code2",
        "SMs",
        f"{BASE_DIR}/process/GPP-draught-analysis/code2_SMs/results/"
        "gpp_response_SMs_events_global_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
    ),
    Item(
        "FluxSat 0401 rec120cap",
        "code2",
        "SMs",
        f"{BASE_DIR}/process/fluxsat-draught-analysis/code2_SMs/results/"
        "fluxsat_gpp_response_SMs_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec120cap.nc",
    ),
]

STYLES = {
    ("BESS 0328", "code1"): {"color": "#1f78b4", "marker": "o", "linestyle": "-"},
    ("FluxSat 0401 rec120cap", "code1"): {"color": "#e31a1c", "marker": "o", "linestyle": "--"},
    ("BESS 0328", "code2"): {"color": "#33a02c", "marker": "s", "linestyle": "-"},
    ("FluxSat 0401 rec120cap", "code2"): {"color": "#ff7f00", "marker": "s", "linestyle": "--"},
}


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


def latitude_area_weights(latitudes: Iterable[float]) -> np.ndarray:
    lat = np.asarray(latitudes, dtype=np.float64)
    weights = np.cos(np.deg2rad(lat))
    weights[~np.isfinite(weights)] = np.nan
    weights[weights < 0] = np.nan
    return weights


def finite_weighted_mean(values: Iterable[float], latitudes: Iterable[float]) -> float:
    arr = np.asarray(values, dtype=np.float64)
    weights = latitude_area_weights(latitudes)
    valid = np.isfinite(arr) & np.isfinite(weights) & (weights > 0)
    if not np.any(valid):
        return math.nan
    return float(np.average(arr[valid], weights=weights[valid]))


def trend_slope(years: np.ndarray, values: np.ndarray) -> float:
    valid = np.isfinite(years) & np.isfinite(values)
    if np.sum(valid) < 2:
        return math.nan
    slope, _ = np.polyfit(years[valid], values[valid], 1)
    return float(slope * 10.0)


def fmt(value: object, decimals: int = 2) -> str:
    if value is None:
        return "-"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(float(value)):
            return "-"
        return f"{float(value):,.{decimals}f}"
    return str(value)


def summarize_item(item: Item) -> Tuple[dict, List[dict]]:
    with nc.Dataset(item.file_path, "r") as ds:
        onset_year = to_numpy(ds.variables["onset_year"])
        lat = to_numpy(ds.variables["lat"])
        t_response = clean_nonnegative(to_numpy(ds.variables["t_response_drought_start"]))
        t_recover = clean_nonnegative(to_numpy(ds.variables["t_recover_to_baseline"]))

    year_mask = np.isfinite(onset_year) & (onset_year >= START_YEAR) & (onset_year <= END_YEAR)
    onset_year = onset_year[year_mask]
    lat = lat[year_mask]
    t_response = t_response[year_mask]
    t_recover = t_recover[year_mask]
    event_total = int(onset_year.size)

    annual_rows: List[dict] = []
    annual_response_means: List[float] = []
    annual_recovery_means: List[float] = []
    annual_years: List[float] = []
    for year in range(START_YEAR, END_YEAR + 1):
        mask = onset_year == year
        resp_vals = t_response[mask]
        rec_vals = t_recover[mask]
        lat_vals = lat[mask]
        annual_rows.append(
            {
                "source": item.source,
                "code": item.code,
                "soil_layer": item.soil_layer,
                "year": year,
                "response_count": int(np.sum(np.isfinite(resp_vals))),
                "response_mean": finite_weighted_mean(resp_vals, lat_vals),
                "recovery_count": int(np.sum(np.isfinite(rec_vals))),
                "recovery_mean": finite_weighted_mean(rec_vals, lat_vals),
            }
        )
        annual_years.append(float(year))
        annual_response_means.append(annual_rows[-1]["response_mean"])
        annual_recovery_means.append(annual_rows[-1]["recovery_mean"])

    response_valid = np.isfinite(t_response)
    recovery_valid = np.isfinite(t_recover)
    summary = {
        "source": item.source,
        "code": item.code,
        "soil_layer": item.soil_layer,
        "window_start": START_YEAR,
        "window_end": END_YEAR,
        "event_total_window": event_total,
        "response_count": int(np.sum(response_valid)),
        "response_valid_pct": float(np.sum(response_valid)) * 100.0 / event_total if event_total else math.nan,
        "response_mean_days": finite_weighted_mean(t_response[response_valid], lat[response_valid]),
        "response_mean_slope_days_per_decade": trend_slope(np.asarray(annual_years), np.asarray(annual_response_means)),
        "recovery_count": int(np.sum(recovery_valid)),
        "recovery_valid_pct": float(np.sum(recovery_valid)) * 100.0 / event_total if event_total else math.nan,
        "recovery_mean_days": finite_weighted_mean(t_recover[recovery_valid], lat[recovery_valid]),
        "recovery_mean_slope_days_per_decade": trend_slope(np.asarray(annual_years), np.asarray(annual_recovery_means)),
        "first5_recovery_mean": float(np.nanmean(np.asarray(annual_recovery_means[:5], dtype=np.float64))),
        "last5_recovery_mean": float(np.nanmean(np.asarray(annual_recovery_means[-5:], dtype=np.float64))),
        "file_path": item.file_path,
    }
    return summary, annual_rows


def write_csv(path: str, rows: List[dict], fieldnames: List[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_md(rows: List[dict]) -> None:
    lines = [
        "# BESS 0328 与 FluxSat 0401 rec120cap 对比（2000-2019）",
        "",
        "> 说明：BESS 使用 0328 rec100 版本，FluxSat 使用 0401 rec120cap 版本，统一截取 2000-2019 年。",
        "",
        "| 数据源 | 情景 | 窗口事件数 | 响应有效% | 响应均值(d) | 响应趋势(d/10a) | 恢复有效% | 恢复均值(d) | 恢复趋势(d/10a) | 前5年恢复均值 | 后5年恢复均值 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["source"],
                    f'{row["code"]} ({row["soil_layer"]})',
                    fmt(row["event_total_window"], 0),
                    fmt(row["response_valid_pct"]),
                    fmt(row["response_mean_days"]),
                    fmt(row["response_mean_slope_days_per_decade"]),
                    fmt(row["recovery_valid_pct"]),
                    fmt(row["recovery_mean_days"]),
                    fmt(row["recovery_mean_slope_days_per_decade"]),
                    fmt(row["first5_recovery_mean"]),
                    fmt(row["last5_recovery_mean"]),
                ]
            )
            + " |"
        )
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def add_trend_line(ax: plt.Axes, years: np.ndarray, values: np.ndarray, color: str) -> None:
    valid = np.isfinite(years) & np.isfinite(values)
    if np.sum(valid) < 2:
        return
    slope, intercept = np.polyfit(years[valid], values[valid], 1)
    ax.plot(years[valid], intercept + slope * years[valid], linestyle=":", linewidth=1.2, color=color, alpha=0.85)


def plot_figure(rows: List[dict]) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.5), sharex=True, constrained_layout=True)
    for col, code in enumerate(("code1", "code2")):
        soil_layer = "SMrz" if code == "code1" else "SMs"
        for source in ("BESS 0328", "FluxSat 0401 rec120cap"):
            subset = [row for row in rows if row["code"] == code and row["source"] == source]
            subset.sort(key=lambda r: r["year"])
            years = np.array([row["year"] for row in subset], dtype=np.float64)
            response = np.array([row["response_mean"] for row in subset], dtype=np.float64)
            recovery = np.array([row["recovery_mean"] for row in subset], dtype=np.float64)
            style = STYLES[(source, code)]
            axes[0, col].plot(years, response, color=style["color"], linestyle=style["linestyle"], marker=style["marker"], markersize=4, linewidth=1.8, label=source)
            axes[1, col].plot(years, recovery, color=style["color"], linestyle=style["linestyle"], marker=style["marker"], markersize=4, linewidth=1.8, label=source)
            add_trend_line(axes[0, col], years, response, style["color"])
            add_trend_line(axes[1, col], years, recovery, style["color"])
        axes[0, col].set_title(f"{code} ({soil_layer}) 响应时间")
        axes[1, col].set_title(f"{code} ({soil_layer}) 恢复时间")
        axes[0, col].set_ylabel("响应均值 (天)")
        axes[1, col].set_ylabel("恢复均值 (天)")
        axes[1, col].set_xlabel("Year")
        axes[0, col].grid(True, linestyle="--", linewidth=0.6, alpha=0.35)
        axes[1, col].grid(True, linestyle="--", linewidth=0.6, alpha=0.35)
        axes[0, col].legend(frameon=False, loc="best")
        axes[1, col].legend(frameon=False, loc="best")
    fig.savefig(FIGURE_PATH, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    setup_chinese_font()
    summary_rows: List[dict] = []
    annual_rows: List[dict] = []
    for item in ITEMS:
        summary, annual = summarize_item(item)
        summary_rows.append(summary)
        annual_rows.extend(annual)

    summary_rows.sort(key=lambda row: (row["code"], row["source"]))
    annual_rows.sort(key=lambda row: (row["code"], row["source"], row["year"]))

    write_csv(
        SUMMARY_CSV,
        summary_rows,
        [
            "source",
            "code",
            "soil_layer",
            "window_start",
            "window_end",
            "event_total_window",
            "response_count",
            "response_valid_pct",
            "response_mean_days",
            "response_mean_slope_days_per_decade",
            "recovery_count",
            "recovery_valid_pct",
            "recovery_mean_days",
            "recovery_mean_slope_days_per_decade",
            "first5_recovery_mean",
            "last5_recovery_mean",
            "file_path",
        ],
    )
    write_csv(
        ANNUAL_CSV,
        annual_rows,
        [
            "source",
            "code",
            "soil_layer",
            "year",
            "response_count",
            "response_mean",
            "recovery_count",
            "recovery_mean",
        ],
    )
    write_md(summary_rows)
    plot_figure(annual_rows)
    print(f"Wrote {SUMMARY_CSV}")
    print(f"Wrote {SUMMARY_MD}")
    print(f"Wrote {ANNUAL_CSV}")
    print(f"Wrote {FIGURE_PATH}")


if __name__ == "__main__":
    main()
