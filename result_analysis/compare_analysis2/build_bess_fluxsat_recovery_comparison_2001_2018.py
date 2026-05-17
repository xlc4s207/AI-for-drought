#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import rcParams
import netCDF4 as nc
import numpy as np


START_YEAR = 2001
END_YEAR = 2018
OUT_DIR = "/home/xulc/flash_drought/process/result_analysis/result_weighted/fluxsat_compare_analysis2/compare_analysis2_vs_fluxsat_v20260328_2001_2018"
SUMMARY_CSV = os.path.join(OUT_DIR, "bess_fluxsat_recovery_comparison_2001_2018.csv")
SUMMARY_MD = os.path.join(OUT_DIR, "bess_fluxsat_recovery_comparison_2001_2018.md")
ANNUAL_CSV = os.path.join(OUT_DIR, "bess_fluxsat_recovery_annual_2001_2018.csv")
FIGURE_PATH = os.path.join(OUT_DIR, "bess_fluxsat_recovery_comparison_2001_2018.png")


@dataclass(frozen=True)
class Item:
    source: str
    code: str
    soil_layer: str
    file_path: str


ITEMS: List[Item] = [
    Item(
        "BESS",
        "code1",
        "SMrz",
        "/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
    ),
    Item(
        "BESS",
        "code2",
        "SMs",
        "/home/xulc/flash_drought/process/GPP-draught-analysis/code2_SMs/results/gpp_response_SMs_events_global_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
    ),
    Item(
        "FluxSat",
        "code1",
        "SMrz",
        "/home/xulc/flash_drought/process/fluxsat-draught-analysis/code1/results/fluxsat_gpp_response_SMrz_events_global_v20260328_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100_2001_2019.nc",
    ),
    Item(
        "FluxSat",
        "code2",
        "SMs",
        "/home/xulc/flash_drought/process/fluxsat-draught-analysis/code2_SMs/results/fluxsat_gpp_response_SMs_events_global_v20260328_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100_2001_2019.nc",
    ),
]

STYLES = {
    ("BESS", "code1"): {"color": "#1f78b4", "marker": "o", "linestyle": "-"},
    ("FluxSat", "code1"): {"color": "#1f78b4", "marker": "o", "linestyle": "--"},
    ("BESS", "code2"): {"color": "#d95f02", "marker": "s", "linestyle": "-"},
    ("FluxSat", "code2"): {"color": "#d95f02", "marker": "s", "linestyle": "--"},
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


def summarize_item(item: Item) -> Tuple[Dict[str, object], List[Dict[str, object]]]:
    with nc.Dataset(item.file_path, "r") as ds:
        onset_year = to_numpy(ds.variables["onset_year"])
        lat = to_numpy(ds.variables["lat"])
        t_recover_peak = clean_nonnegative(to_numpy(ds.variables["t_recover_to_baseline"]))
        event_total = len(ds.dimensions["event"])

    year_mask = np.isfinite(onset_year) & (onset_year >= START_YEAR) & (onset_year <= END_YEAR)
    onset_year = onset_year[year_mask]
    lat = lat[year_mask]
    t_recover_peak = t_recover_peak[year_mask]

    recovery_valid = np.isfinite(t_recover_peak)
    recovery_count = int(np.sum(recovery_valid))
    recovery_mean = finite_weighted_mean(t_recover_peak[recovery_valid], lat[recovery_valid])
    recovery_median = float(np.nanmedian(t_recover_peak[recovery_valid])) if recovery_count else math.nan

    annual_rows: List[Dict[str, object]] = []
    annual_years: List[float] = []
    annual_means: List[float] = []
    for year in range(START_YEAR, END_YEAR + 1):
        mask = onset_year == year
        yr_count = int(np.sum(np.isfinite(t_recover_peak[mask])))
        yr_mean = finite_weighted_mean(t_recover_peak[mask], lat[mask])
        yr_median = float(np.nanmedian(t_recover_peak[mask])) if yr_count else math.nan
        annual_rows.append(
            {
                "source": item.source,
                "code": item.code,
                "soil_layer": item.soil_layer,
                "year": year,
                "recovery_count": yr_count,
                "recovery_mean": yr_mean,
                "recovery_median": yr_median,
            }
        )
        annual_years.append(float(year))
        annual_means.append(yr_mean)

    summary = {
        "source": item.source,
        "code": item.code,
        "soil_layer": item.soil_layer,
        "window_start": START_YEAR,
        "window_end": END_YEAR,
        "event_total_window": int(len(onset_year)),
        "recovery_count": recovery_count,
        "recovery_valid_pct": recovery_count * 100.0 / len(onset_year) if len(onset_year) else math.nan,
        "recovery_mean_days": recovery_mean,
        "recovery_median_days": recovery_median,
        "recovery_mean_slope_days_per_decade": trend_slope(np.asarray(annual_years), np.asarray(annual_means)),
        "first_period_mean": float(np.nanmean(np.asarray(annual_means[:5], dtype=np.float64))),
        "last_period_mean": float(np.nanmean(np.asarray(annual_means[-5:], dtype=np.float64))),
        "file_path": item.file_path,
    }
    return summary, annual_rows


def write_csv(path: str, rows: List[Dict[str, object]], fieldnames: List[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_md(rows: List[Dict[str, object]]) -> None:
    lines = [
        "# BESS 与 FluxSat 恢复时间对比（2001-2018）",
        "",
        "> 说明：BESS 取 compare_analysis2 对应的 rec100 GPP 结果，并截取 2001-2018；FluxSat 取 v20260328 rec100 输出。",
        "",
        "| 数据源 | 情景 | 窗口事件数 | 恢复有效数 | 恢复有效% | 恢复均值(d) | 恢复中位数(d) | 恢复趋势(d/10a) | 前5年均值 | 后5年均值 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["source"],
                    f'{row["code"]} ({row["soil_layer"]})',
                    fmt(row["event_total_window"], 0),
                    fmt(row["recovery_count"], 0),
                    fmt(row["recovery_valid_pct"]),
                    fmt(row["recovery_mean_days"]),
                    fmt(row["recovery_median_days"]),
                    fmt(row["recovery_mean_slope_days_per_decade"]),
                    fmt(row["first_period_mean"]),
                    fmt(row["last_period_mean"]),
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


def plot_figure(rows: List[Dict[str, object]]) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True, constrained_layout=True)
    for code, ax in zip(("code1", "code2"), axes):
        for source in ("BESS", "FluxSat"):
            sub = [r for r in rows if r["code"] == code and r["source"] == source]
            years = np.array([r["year"] for r in sub], dtype=np.float64)
            means = np.array([r["recovery_mean"] for r in sub], dtype=np.float64)
            style = STYLES[(source, code)]
            label = f"{source} {code} ({sub[0]['soil_layer']})"
            ax.plot(years, means, color=style["color"], marker=style["marker"], linestyle=style["linestyle"], linewidth=2.0, markersize=4.0, label=label)
            add_trend_line(ax, years, means, style["color"])
        ax.set_title(f"GPP 恢复时间对比：{sub[0]['soil_layer']}")
        ax.set_ylabel("恢复时间均值 (天)")
        ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.35)
        ax.legend(frameon=False, loc="best")
    axes[-1].set_xlabel("Year")
    fig.savefig(FIGURE_PATH, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    setup_chinese_font()

    summary_rows: List[Dict[str, object]] = []
    annual_rows: List[Dict[str, object]] = []
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
            "recovery_count",
            "recovery_valid_pct",
            "recovery_mean_days",
            "recovery_median_days",
            "recovery_mean_slope_days_per_decade",
            "first_period_mean",
            "last_period_mean",
            "file_path",
        ],
    )
    write_csv(
        ANNUAL_CSV,
        annual_rows,
        ["source", "code", "soil_layer", "year", "recovery_count", "recovery_mean", "recovery_median"],
    )
    write_md(summary_rows)
    plot_figure(annual_rows)
    print(f"Wrote {SUMMARY_CSV}")
    print(f"Wrote {SUMMARY_MD}")
    print(f"Wrote {ANNUAL_CSV}")
    print(f"Wrote {FIGURE_PATH}")


if __name__ == "__main__":
    main()
