#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
"""Compare FluxSat 0401 sensitivity variants against BESS 0401 trends."""

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


BASE_DIR = "/home/xulc/flash_drought"
OUT_DIR = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/"
    "fluxsat_compare_analysis2/fluxsat_0401_sensitivity_compare"
)
SUMMARY_CSV = os.path.join(OUT_DIR, "fluxsat_0401_sensitivity_summary.csv")
ANNUAL_CSV = os.path.join(OUT_DIR, "fluxsat_0401_sensitivity_annual.csv")
SUMMARY_MD = os.path.join(OUT_DIR, "fluxsat_0401_sensitivity_summary.md")
RECOVERY_FIG = os.path.join(OUT_DIR, "fluxsat_0401_sensitivity_recovery_trend.png")
RESPONSE_FIG = os.path.join(OUT_DIR, "fluxsat_0401_sensitivity_response_trend.png")

BESS_ANNUAL_CSV = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/compare_analysis2/"
    "v20260401_growingseason_recovery_gsdays/"
    "annual_response_recovery_trends_v20260401_growingseason_recovery_gsdays.csv"
)
BESS_SUMMARY_CSV = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/compare_analysis2/"
    "v20260401_growingseason_recovery_gsdays/"
    "summary_table_v20260401_growingseason_recovery_gsdays.csv"
)


@dataclass(frozen=True)
class FluxSatItem:
    label: str
    code: str
    soil_layer: str
    file_path: str


FLUXSAT_ITEMS: List[FluxSatItem] = [
    FluxSatItem(
        "FluxSat 0401 norecmax",
        "code1",
        "SMrz",
        f"{BASE_DIR}/process/fluxsat-draught-analysis/code1/results/"
        "fluxsat_gpp_response_SMrz_events_global_"
        "v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc",
    ),
    FluxSatItem(
        "FluxSat 0401 rec100cap",
        "code1",
        "SMrz",
        f"{BASE_DIR}/process/fluxsat-draught-analysis/code1/results/"
        "fluxsat_gpp_response_SMrz_events_global_"
        "v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_fixlon_v20260426.nc",
    ),
    FluxSatItem(
        "FluxSat 0401 rec120cap",
        "code1",
        "SMrz",
        f"{BASE_DIR}/process/fluxsat-draught-analysis/code1/results/"
        "fluxsat_gpp_response_SMrz_events_global_"
        "v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec120cap.nc",
    ),
    FluxSatItem(
        "FluxSat 0401 rec100cap gs0.7",
        "code1",
        "SMrz",
        f"{BASE_DIR}/process/fluxsat-draught-analysis/code1/results/"
        "fluxsat_gpp_response_SMrz_events_global_"
        "v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_gsfrac07.nc",
    ),
    FluxSatItem(
        "FluxSat 0401 norecmax",
        "code2",
        "SMs",
        f"{BASE_DIR}/process/fluxsat-draught-analysis/code2_SMs/results/"
        "fluxsat_gpp_response_SMs_events_global_"
        "v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc",
    ),
    FluxSatItem(
        "FluxSat 0401 rec100cap",
        "code2",
        "SMs",
        f"{BASE_DIR}/process/fluxsat-draught-analysis/code2_SMs/results/"
        "fluxsat_gpp_response_SMs_events_global_"
        "v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_fixlon_v20260426.nc",
    ),
    FluxSatItem(
        "FluxSat 0401 rec120cap",
        "code2",
        "SMs",
        f"{BASE_DIR}/process/fluxsat-draught-analysis/code2_SMs/results/"
        "fluxsat_gpp_response_SMs_events_global_"
        "v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec120cap.nc",
    ),
    FluxSatItem(
        "FluxSat 0401 rec100cap gs0.7",
        "code2",
        "SMs",
        f"{BASE_DIR}/process/fluxsat-draught-analysis/code2_SMs/results/"
        "fluxsat_gpp_response_SMs_events_global_"
        "v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_gsfrac07.nc",
    ),
]

LABEL_STYLES = {
    "BESS 0401": {"color": "#CC6677", "linestyle": "-", "marker": "o"},
    "FluxSat 0401 norecmax": {"color": "#1f78b4", "linestyle": "-", "marker": "o"},
    "FluxSat 0401 rec100cap": {"color": "#0072B2", "linestyle": "-", "marker": "s"},
    "FluxSat 0401 rec120cap": {"color": "#ff7f00", "linestyle": "-", "marker": "^"},
    "FluxSat 0401 rec100cap gs0.7": {"color": "#e31a1c", "linestyle": "-", "marker": "D"},
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


def annual_series(years: np.ndarray, values: np.ndarray, latitudes: np.ndarray) -> List[Dict[str, object]]:
    valid = np.isfinite(years) & np.isfinite(values) & np.isfinite(latitudes)
    years = years[valid].astype(np.int32, copy=False)
    values = values[valid]
    latitudes = latitudes[valid]
    out: List[Dict[str, object]] = []
    for year in np.unique(years):
        mask = years == year
        vals = values[mask]
        out.append(
            {
                "year": int(year),
                "count": int(vals.size),
                "mean": finite_weighted_mean(vals, latitudes[mask]),
                "median": float(np.nanmedian(vals)),
            }
        )
    return out


def summarize_fluxsat(item: FluxSatItem) -> Tuple[Dict[str, object], List[Dict[str, object]]]:
    with nc.Dataset(item.file_path, "r") as ds:
        onset_year = to_numpy(ds.variables["onset_year"])
        lat = to_numpy(ds.variables["lat"])
        t_response = clean_nonnegative(to_numpy(ds.variables["t_response_drought_start"]))
        t_recover = clean_nonnegative(to_numpy(ds.variables["t_recover_to_baseline"]))
        event_total = len(ds.dimensions["event"])

    response_valid = np.isfinite(t_response)
    recovery_valid = np.isfinite(t_recover)

    annual_resp = annual_series(onset_year, t_response, lat)
    annual_rec = annual_series(onset_year, t_recover, lat)
    resp_by_year = {row["year"]: row for row in annual_resp}
    rec_by_year = {row["year"]: row for row in annual_rec}
    annual_rows: List[Dict[str, object]] = []
    for year in sorted(set(resp_by_year) | set(rec_by_year)):
        annual_rows.append(
            {
                "dataset": item.label,
                "code": item.code,
                "soil_layer": item.soil_layer,
                "year": year,
                "response_count": resp_by_year.get(year, {}).get("count", 0),
                "response_mean": resp_by_year.get(year, {}).get("mean", math.nan),
                "recovery_count": rec_by_year.get(year, {}).get("count", 0),
                "recovery_mean": rec_by_year.get(year, {}).get("mean", math.nan),
            }
        )

    resp_years = np.array([row["year"] for row in annual_resp], dtype=np.float64)
    resp_means = np.array([row["mean"] for row in annual_resp], dtype=np.float64)
    rec_years = np.array([row["year"] for row in annual_rec], dtype=np.float64)
    rec_means = np.array([row["mean"] for row in annual_rec], dtype=np.float64)

    summary = {
        "dataset": item.label,
        "code": item.code,
        "soil_layer": item.soil_layer,
        "event_total": event_total,
        "response_valid_count": int(np.sum(response_valid)),
        "response_valid_pct": float(np.sum(response_valid)) * 100.0 / event_total if event_total else math.nan,
        "response_mean_days": finite_weighted_mean(t_response[response_valid], lat[response_valid]),
        "response_mean_slope_days_per_decade": trend_slope(resp_years, resp_means),
        "recovery_valid_count": int(np.sum(recovery_valid)),
        "recovery_valid_pct": float(np.sum(recovery_valid)) * 100.0 / event_total if event_total else math.nan,
        "recovery_mean_days": finite_weighted_mean(t_recover[recovery_valid], lat[recovery_valid]),
        "recovery_mean_slope_days_per_decade": trend_slope(rec_years, rec_means),
        "first5_recovery_mean": float(np.nanmean(rec_means[:5])) if rec_means.size >= 5 else math.nan,
        "last5_recovery_mean": float(np.nanmean(rec_means[-5:])) if rec_means.size >= 5 else math.nan,
        "file_path": item.file_path,
    }
    return summary, annual_rows


def load_bess_rows() -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    summary_rows: List[Dict[str, object]] = []
    with open(BESS_SUMMARY_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["variable"] != "GPP" or row["code"] not in {"code1", "code2"}:
                continue
            summary_rows.append(
                {
                    "dataset": "BESS 0401",
                    "code": row["code"],
                    "soil_layer": row["soil_layer"],
                    "event_total": int(float(row["event_total"])),
                    "response_valid_count": int(float(row["response_valid_count"])),
                    "response_valid_pct": float(row["response_valid_pct"]),
                    "response_mean_days": float(row["response_mean_days"]),
                    "response_mean_slope_days_per_decade": float(row["response_mean_slope_days_per_decade"]),
                    "recovery_valid_count": int(float(row["recovery_valid_count"])),
                    "recovery_valid_pct": float(row["recovery_valid_pct"]),
                    "recovery_mean_days": float(row["recovery_mean_days"]),
                    "recovery_mean_slope_days_per_decade": float(row["recovery_mean_slope_days_per_decade"]),
                    "first5_recovery_mean": math.nan,
                    "last5_recovery_mean": math.nan,
                    "file_path": row["file_path"],
                }
            )

    annual_rows: List[Dict[str, object]] = []
    yearly_means: Dict[Tuple[str, str], List[float]] = {}
    with open(BESS_ANNUAL_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["variable"] != "GPP" or row["code"] not in {"code1", "code2"}:
                continue
            annual_rows.append(
                {
                    "dataset": "BESS 0401",
                    "code": row["code"],
                    "soil_layer": row["soil_layer"],
                    "year": int(float(row["year"])),
                    "response_count": int(float(row["response_count"])),
                    "response_mean": float(row["response_mean"]),
                    "recovery_count": int(float(row["recovery_count"])),
                    "recovery_mean": float(row["recovery_mean"]),
                }
            )
            yearly_means.setdefault(("BESS 0401", row["code"]), []).append(float(row["recovery_mean"]))

    for summary in summary_rows:
        means = yearly_means.get((summary["dataset"], summary["code"]), [])
        arr = np.asarray(means, dtype=np.float64)
        if arr.size >= 5:
            summary["first5_recovery_mean"] = float(np.nanmean(arr[:5]))
            summary["last5_recovery_mean"] = float(np.nanmean(arr[-5:]))
    return summary_rows, annual_rows


def write_csv(path: str, rows: List[Dict[str, object]], fieldnames: List[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def add_trend_line(ax: plt.Axes, years: np.ndarray, values: np.ndarray, color: str) -> None:
    valid = np.isfinite(years) & np.isfinite(values)
    if np.sum(valid) < 2:
        return
    slope, intercept = np.polyfit(years[valid], values[valid], 1)
    ax.plot(years[valid], intercept + slope * years[valid], linestyle="--", linewidth=1.2, color=color, alpha=0.7)


def plot_metric(
    annual_rows: List[Dict[str, object]],
    metric: str,
    ylabel: str,
    out_path: str,
    datasets: List[str] | None = None,
    y_limits: tuple[float, float] | None = None,
) -> None:
    if datasets is None:
        datasets = [
            "BESS 0401",
            "FluxSat 0401 norecmax",
            "FluxSat 0401 rec100cap",
            "FluxSat 0401 rec120cap",
            "FluxSat 0401 rec100cap gs0.7",
        ]
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True, constrained_layout=True)
    display_labels = {
        "BESS 0401": "BESS",
        "FluxSat 0401 rec100cap": "FluxSat",
    }
    for ax, code in zip(axes, ("code1", "code2")):
        rows_by_dataset = {}
        soil_layer = "SMrz" if code == "code1" else "SMs"
        for row in annual_rows:
            if row["code"] != code:
                continue
            rows_by_dataset.setdefault(row["dataset"], []).append(row)
        for dataset in datasets:
            rows = sorted(rows_by_dataset.get(dataset, []), key=lambda r: r["year"])
            if not rows:
                continue
            years = np.array([row["year"] for row in rows], dtype=np.float64)
            values = np.array([row[metric] for row in rows], dtype=np.float64)
            if dataset.startswith("FluxSat"):
                keep = years != 2000
                years = years[keep]
                values = values[keep]
            if years.size == 0:
                continue
            style = LABEL_STYLES[dataset]
            ax.plot(
                years,
                values,
                color=style["color"],
                linestyle=style["linestyle"],
                marker=style["marker"],
                markersize=6,
                linewidth=2.4,
                label=display_labels.get(dataset, dataset),
            )
            add_trend_line(ax, years, values, style["color"])
        ax.set_title(f"{soil_layer}", fontsize=22)
        ax.set_ylabel(ylabel, fontsize=18)
        if y_limits is not None:
            ax.set_ylim(*y_limits)
        ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.35)
        ax.legend(frameon=False, fontsize=16, ncol=2, loc="best")
        ax.tick_params(axis="both", labelsize=15)
    axes[-1].set_xlabel("Year", fontsize=18)
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def write_summary_md(rows: List[Dict[str, object]]) -> None:
    lines = [
        "# FluxSat 0401 敏感性方案与 BESS 0401 对比",
        "",
        "| 数据集 | 情景 | 事件数 | 响应有效% | 响应均值(d) | 响应趋势(d/10a) | 恢复有效% | 恢复均值(d) | 恢复趋势(d/10a) | 前5年恢复均值 | 后5年恢复均值 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["dataset"],
                    f'{row["code"]} ({row["soil_layer"]})',
                    fmt(row["event_total"], 0),
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

    for code in ("code1", "code2"):
        bess = next(row for row in rows if row["dataset"] == "BESS 0401" and row["code"] == code)
        fluxsat_rows = [row for row in rows if row["dataset"] != "BESS 0401" and row["code"] == code]
        best = min(
            fluxsat_rows,
            key=lambda row: abs(row["recovery_mean_slope_days_per_decade"] - bess["recovery_mean_slope_days_per_decade"]),
        )
        lines.append("")
        lines.append(
            f"- {code} 最接近 BESS 0401 恢复趋势的 FluxSat 方案是 `{best['dataset']}`，"
            f"其恢复斜率为 `{fmt(best['recovery_mean_slope_days_per_decade'])} d/10a`，"
            f"BESS 为 `{fmt(bess['recovery_mean_slope_days_per_decade'])} d/10a`。"
        )
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    setup_chinese_font()

    summary_rows, annual_rows = load_bess_rows()
    for item in FLUXSAT_ITEMS:
        summary_row, item_annual = summarize_fluxsat(item)
        summary_rows.append(summary_row)
        annual_rows.extend(item_annual)

    summary_rows.sort(key=lambda row: (row["code"], row["dataset"]))
    annual_rows.sort(key=lambda row: (row["code"], row["dataset"], row["year"]))

    write_csv(
        SUMMARY_CSV,
        summary_rows,
        [
            "dataset",
            "code",
            "soil_layer",
            "event_total",
            "response_valid_count",
            "response_valid_pct",
            "response_mean_days",
            "response_mean_slope_days_per_decade",
            "recovery_valid_count",
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
            "dataset",
            "code",
            "soil_layer",
            "year",
            "response_count",
            "response_mean",
            "recovery_count",
            "recovery_mean",
        ],
    )
    write_summary_md(summary_rows)
    plot_metric(
        annual_rows,
        "recovery_mean",
        "Recovery Time Mean (days)",
        RECOVERY_FIG,
        datasets=["BESS 0401", "FluxSat 0401 rec100cap"],
        y_limits=(25.0, 50.0),
    )
    plot_metric(annual_rows, "response_mean", "响应时间均值 (天)", RESPONSE_FIG)
    print(f"Wrote {SUMMARY_CSV}")
    print(f"Wrote {ANNUAL_CSV}")
    print(f"Wrote {SUMMARY_MD}")
    print(f"Wrote {RECOVERY_FIG}")
    print(f"Wrote {RESPONSE_FIG}")


if __name__ == "__main__":
    main()
