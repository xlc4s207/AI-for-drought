#!/usr/bin/env python3
"""Build FluxSat GPP summary table and trend figure for v20260401 outputs."""

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


OUT_DIR = "/home/xulc/flash_drought/process/result_analysis/result_weighted/fluxsat_compare_analysis2/v20260328_rec100_2001_2019"
SUMMARY_CSV = os.path.join(OUT_DIR, "summary_table_fluxsat_v20260328_rec100_2001_2019.csv")
SUMMARY_MD = os.path.join(OUT_DIR, "summary_table_fluxsat_v20260328_rec100_2001_2019.md")
ANNUAL_CSV = os.path.join(OUT_DIR, "annual_response_recovery_trends_fluxsat_v20260328_rec100_2001_2019.csv")
FIGURE_PATH = os.path.join(OUT_DIR, "fluxsat_gpp_response_recovery_trend_v20260328_rec100_2001_2019.png")


@dataclass(frozen=True)
class Item:
    variable: str
    code: str
    soil_layer: str
    data_source: str
    file_path: str

    @property
    def scenario_label(self) -> str:
        return f"{self.data_source} {self.code} ({self.soil_layer})"


ITEMS: List[Item] = [
    Item(
        "GPP",
        "code1",
        "SMrz",
        "FluxSat",
        "/home/xulc/flash_drought/process/fluxsat-draught-analysis/code1/results/fluxsat_gpp_response_SMrz_events_global_v20260328_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100_2001_2019.nc",
    ),
    Item(
        "GPP",
        "code2",
        "SMs",
        "FluxSat",
        "/home/xulc/flash_drought/process/fluxsat-draught-analysis/code2_SMs/results/fluxsat_gpp_response_SMs_events_global_v20260328_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100_2001_2019.nc",
    ),
]

CODE_STYLES = {
    "code1": {"color": "#1f78b4", "marker": "o"},
    "code2": {"color": "#d95f02", "marker": "s"},
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
    if selected is None:
        for fp in [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJKSC-Regular.otf",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        ]:
            if os.path.exists(fp):
                try:
                    fm.fontManager.addfont(fp)
                    selected = fm.FontProperties(fname=fp).get_name()
                    break
                except Exception:
                    continue
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


def finite_stats(values: np.ndarray, latitudes: np.ndarray) -> Dict[str, float]:
    arr = np.asarray(values, dtype=np.float64)
    latitudes = np.asarray(latitudes, dtype=np.float64)
    valid = np.isfinite(arr) & np.isfinite(latitudes)
    arr = arr[valid]
    latitudes = latitudes[valid]
    if arr.size == 0:
        return {
            "count": 0,
            "mean": math.nan,
            "median": math.nan,
            "p25": math.nan,
            "p75": math.nan,
        }
    q25, q50, q75 = np.percentile(arr, [25, 50, 75])
    return {
        "count": int(arr.size),
        "mean": finite_weighted_mean(arr, latitudes),
        "median": float(q50),
        "p25": float(q25),
        "p75": float(q75),
    }


def annual_series(years: np.ndarray, values: np.ndarray, latitudes: np.ndarray) -> List[Dict[str, object]]:
    years = np.asarray(years, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    latitudes = np.asarray(latitudes, dtype=np.float64)
    valid = np.isfinite(years) & np.isfinite(values) & np.isfinite(latitudes)
    years = years[valid].astype(np.int32, copy=False)
    values = values[valid]
    latitudes = latitudes[valid]
    out: List[Dict[str, object]] = []
    for year in np.unique(years):
        year_mask = years == year
        vals = values[year_mask]
        if vals.size == 0:
            continue
        out.append(
            {
                "year": int(year),
                "count": int(vals.size),
                "mean": finite_weighted_mean(vals, latitudes[year_mask]),
                "median": float(np.nanmedian(vals)),
            }
        )
    return out


def trend_slope(years: np.ndarray, values: np.ndarray) -> float:
    years = np.asarray(years, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    valid = np.isfinite(years) & np.isfinite(values)
    years = years[valid]
    values = values[valid]
    if years.size < 2:
        return math.nan
    return float(np.polyfit(years, values, 1)[0] * 10.0)


def summarize_item(item: Item) -> Tuple[Dict[str, object], List[Dict[str, object]]]:
    with nc.Dataset(item.file_path, "r") as ds:
        onset_year = to_numpy(ds.variables["onset_year"])
        lat = to_numpy(ds.variables["lat"])
        t_response = clean_nonnegative(to_numpy(ds.variables["t_response_drought_start"]))
        t_recover = clean_nonnegative(to_numpy(ds.variables["t_recover_to_baseline"]))
        event_total = len(ds.dimensions["event"])

    response_stats = finite_stats(t_response, lat)
    recovery_stats = finite_stats(t_recover, lat)
    annual_response = annual_series(onset_year, t_response, lat)
    annual_recovery = annual_series(onset_year, t_recover, lat)

    annual_rows: List[Dict[str, object]] = []
    response_by_year = {row["year"]: row for row in annual_response}
    recovery_by_year = {row["year"]: row for row in annual_recovery}
    for year in sorted(set(response_by_year) | set(recovery_by_year)):
        annual_rows.append(
            {
                "variable": item.variable,
                "data_source": item.data_source,
                "code": item.code,
                "soil_layer": item.soil_layer,
                "year": year,
                "response_count": response_by_year.get(year, {}).get("count", 0),
                "response_mean": response_by_year.get(year, {}).get("mean", math.nan),
                "response_median": response_by_year.get(year, {}).get("median", math.nan),
                "recovery_count": recovery_by_year.get(year, {}).get("count", 0),
                "recovery_mean": recovery_by_year.get(year, {}).get("mean", math.nan),
                "recovery_median": recovery_by_year.get(year, {}).get("median", math.nan),
            }
        )

    resp_slope = trend_slope(
        np.array([row["year"] for row in annual_response], dtype=np.float64),
        np.array([row["mean"] for row in annual_response], dtype=np.float64),
    )
    rec_slope = trend_slope(
        np.array([row["year"] for row in annual_recovery], dtype=np.float64),
        np.array([row["mean"] for row in annual_recovery], dtype=np.float64),
    )

    summary_row = {
        "variable": item.variable,
        "data_source": item.data_source,
        "code": item.code,
        "soil_layer": item.soil_layer,
        "event_total": event_total,
        "response_valid_count": response_stats["count"],
        "response_valid_pct": response_stats["count"] * 100.0 / event_total if event_total else math.nan,
        "response_mean_days": response_stats["mean"],
        "response_median_days": response_stats["median"],
        "response_p25_days": response_stats["p25"],
        "response_p75_days": response_stats["p75"],
        "response_mean_slope_days_per_decade": resp_slope,
        "recovery_valid_count": recovery_stats["count"],
        "recovery_valid_pct": recovery_stats["count"] * 100.0 / event_total if event_total else math.nan,
        "recovery_mean_days": recovery_stats["mean"],
        "recovery_median_days": recovery_stats["median"],
        "recovery_p25_days": recovery_stats["p25"],
        "recovery_p75_days": recovery_stats["p75"],
        "recovery_mean_slope_days_per_decade": rec_slope,
        "file_path": item.file_path,
    }
    return summary_row, annual_rows


def write_summary_csv(rows: List[Dict[str, object]]) -> None:
    fieldnames = [
        "variable",
        "data_source",
        "code",
        "soil_layer",
        "event_total",
        "response_valid_count",
        "response_valid_pct",
        "response_mean_days",
        "response_median_days",
        "response_p25_days",
        "response_p75_days",
        "response_mean_slope_days_per_decade",
        "recovery_valid_count",
        "recovery_valid_pct",
        "recovery_mean_days",
        "recovery_median_days",
        "recovery_p25_days",
        "recovery_p75_days",
        "recovery_mean_slope_days_per_decade",
        "file_path",
    ]
    with open(SUMMARY_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_annual_csv(rows: List[Dict[str, object]]) -> None:
    fieldnames = [
        "variable",
        "data_source",
        "code",
        "soil_layer",
        "year",
        "response_count",
        "response_mean",
        "response_median",
        "recovery_count",
        "recovery_mean",
        "recovery_median",
    ]
    with open(ANNUAL_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary_md(rows: List[Dict[str, object]]) -> None:
    headers = [
        "变量",
        "数据源",
        "情景",
        "事件数",
        "响应有效%",
        "响应均值(d)",
        "响应中位数(d)",
        "恢复有效%",
        "恢复均值(d)",
        "恢复中位数(d)",
        "响应趋势(d/10a)",
        "恢复趋势(d/10a)",
    ]
    lines = [
        "# FluxSat v20260328 rec100 版本汇总表",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["variable"],
                    row["data_source"],
                    f'{row["code"]} ({row["soil_layer"]})',
                    fmt(row["event_total"], 0),
                    fmt(row["response_valid_pct"]),
                    fmt(row["response_mean_days"]),
                    fmt(row["response_median_days"]),
                    fmt(row["recovery_valid_pct"]),
                    fmt(row["recovery_mean_days"]),
                    fmt(row["recovery_median_days"]),
                    fmt(row["response_mean_slope_days_per_decade"]),
                    fmt(row["recovery_mean_slope_days_per_decade"]),
                ]
            )
            + " |"
        )
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def add_trend_line(ax: plt.Axes, years: np.ndarray, values: np.ndarray, color: str) -> None:
    years = np.asarray(years, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    valid = np.isfinite(years) & np.isfinite(values)
    years = years[valid]
    values = values[valid]
    if years.size < 2:
        return
    slope, intercept = np.polyfit(years, values, 1)
    ax.plot(years, intercept + slope * years, linestyle="--", linewidth=1.5, color=color, alpha=0.9)


def plot_fluxsat_gpp(annual_rows: List[Dict[str, object]]) -> str:
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True, constrained_layout=True)
    for code in ["code1", "code2"]:
        rows = sorted((row for row in annual_rows if row["code"] == code), key=lambda x: x["year"])
        if not rows:
            continue
        years = np.array([row["year"] for row in rows], dtype=np.float64)
        response = np.array([row["response_mean"] for row in rows], dtype=np.float64)
        recovery = np.array([row["recovery_mean"] for row in rows], dtype=np.float64)
        style = CODE_STYLES[code]
        label = f"FluxSat {code} ({rows[0]['soil_layer']})"

        axes[0].plot(years, response, color=style["color"], marker=style["marker"], markersize=4.2, linewidth=2.0, label=label)
        axes[1].plot(years, recovery, color=style["color"], marker=style["marker"], markersize=4.2, linewidth=2.0, label=label)
        add_trend_line(axes[0], years, response, style["color"])
        add_trend_line(axes[1], years, recovery, style["color"])

    axes[0].set_title("FluxSat GPP 响应时间变化趋势（v20260328 rec100）")
    axes[0].set_ylabel("响应时间均值 (天)")
    axes[1].set_title("FluxSat GPP 恢复时间变化趋势（v20260328 rec100）")
    axes[1].set_ylabel("恢复时间均值 (天)")
    axes[1].set_xlabel("Year")

    for ax in axes:
        ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.35)
        ax.legend(frameon=False, loc="best")

    fig.savefig(FIGURE_PATH, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return FIGURE_PATH


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    setup_chinese_font()

    summary_rows: List[Dict[str, object]] = []
    annual_rows: List[Dict[str, object]] = []
    for item in ITEMS:
        summary_row, item_annual_rows = summarize_item(item)
        summary_rows.append(summary_row)
        annual_rows.extend(item_annual_rows)

    summary_rows.sort(key=lambda row: row["code"])
    annual_rows.sort(key=lambda row: (row["code"], row["year"]))

    write_summary_csv(summary_rows)
    write_summary_md(summary_rows)
    write_annual_csv(annual_rows)
    figure_path = plot_fluxsat_gpp(annual_rows)

    print(f"Wrote {SUMMARY_CSV}")
    print(f"Wrote {SUMMARY_MD}")
    print(f"Wrote {ANNUAL_CSV}")
    print(f"Wrote {figure_path}")


if __name__ == "__main__":
    main()
