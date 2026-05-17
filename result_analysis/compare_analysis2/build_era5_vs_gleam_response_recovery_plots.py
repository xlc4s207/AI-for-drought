#!/usr/bin/env python3
"""Build 12 ERA5-vs-GLEAM annual response/recovery comparison plots."""

from __future__ import annotations

import argparse
import math
import os
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np
import pandas as pd


DEFAULT_OUT_DIR = "/home/xulc/flash_drought/process/result_analysis/result_weighted/compare_analysis2/era5_vs_gleam_code1"
DEFAULT_DETAIL_CSV_NAME = "annual_response_recovery_comparison_all_codes_era5_vs_gleam.csv"
DEFAULT_SUMMARY_CSV_NAME = "trend_summary_all_codes_era5_vs_gleam.csv"

SCENARIO_LABELS = {
    "code1": "SMrz Flash",
    "code2": "SMs Flash",
    "code3": "SMrz Slow",
    "code4": "SMs Slow",
}

SOURCE_STYLES = {
    "GLEAM": {"color": "#1f77b4", "marker": "o"},
    "ERA5": {"color": "#d62728", "marker": "s"},
}


@dataclass(frozen=True)
class ComparisonItem:
    variable: str
    code: str
    gleam_path: str
    era5_path: str

    @property
    def scenario_label(self) -> str:
        return SCENARIO_LABELS[self.code]


ITEMS: List[ComparisonItem] = [
    ComparisonItem(
        "GPP",
        "code1",
        "/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
        "/home/xulc/flash_drought/process/GPP-draught-analysis/code1_ERA5_root/results/gpp_response_ERA5L_root_events_global_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
    ),
    ComparisonItem(
        "GPP",
        "code2",
        "/home/xulc/flash_drought/process/GPP-draught-analysis/code2_SMs/results/gpp_response_SMs_events_global_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
        "/home/xulc/flash_drought/process/GPP-draught-analysis/code2_ERA5_swvl1/results/gpp_response_ERA5L_swvl1_events_global_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
    ),
    ComparisonItem(
        "GPP",
        "code3",
        "/home/xulc/flash_drought/process/GPP-draught-analysis/code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
        "/home/xulc/flash_drought/process/GPP-draught-analysis/code3_ERA5_root_nonflash/result/gpp_response_nonflash_ERA5L_root_drought_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
    ),
    ComparisonItem(
        "GPP",
        "code4",
        "/home/xulc/flash_drought/process/GPP-draught-analysis/code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
        "/home/xulc/flash_drought/process/GPP-draught-analysis/code4_ERA5_swvl1_nonflash/result/gpp_response_nonflash_ERA5L_swvl1_drought_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
    ),
    ComparisonItem(
        "NEE",
        "code1",
        "/home/xulc/flash_drought/process/NEE-draught-analysis/code1SMrz/result/nee_response_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
        "/home/xulc/flash_drought/process/NEE-draught-analysis/code1_ERA5_root/result/nee_response_ERA5L_root_drought_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
    ),
    ComparisonItem(
        "NEE",
        "code2",
        "/home/xulc/flash_drought/process/NEE-draught-analysis/code2SMs/result/nee_response_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
        "/home/xulc/flash_drought/process/NEE-draught-analysis/code2_ERA5_swvl1/result/nee_response_ERA5L_swvl1_drought_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
    ),
    ComparisonItem(
        "NEE",
        "code3",
        "/home/xulc/flash_drought/process/NEE-draught-analysis/code3_nonflash_SMrz/result/nee_response_nonflash_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
        "/home/xulc/flash_drought/process/NEE-draught-analysis/code3_ERA5_root_nonflash/result/nee_response_nonflash_ERA5L_root_drought_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
    ),
    ComparisonItem(
        "NEE",
        "code4",
        "/home/xulc/flash_drought/process/NEE-draught-analysis/code4_nonflash_SMs/result/nee_response_nonflash_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
        "/home/xulc/flash_drought/process/NEE-draught-analysis/code4_ERA5_swvl1_nonflash/result/nee_response_nonflash_ERA5L_swvl1_drought_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
    ),
    ComparisonItem(
        "RECO",
        "code1",
        "/home/xulc/flash_drought/process/RECO-draught-analysis/code1/results/reco_response_SMrz_events_global_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
        "/home/xulc/flash_drought/process/RECO-draught-analysis/code1_ERA5_root/results/reco_response_ERA5L_root_events_global_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
    ),
    ComparisonItem(
        "RECO",
        "code2",
        "/home/xulc/flash_drought/process/RECO-draught-analysis/code2_SMs/results/reco_response_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
        "/home/xulc/flash_drought/process/RECO-draught-analysis/code2_ERA5_swvl1/results/reco_response_ERA5L_swvl1_drought_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
    ),
    ComparisonItem(
        "RECO",
        "code3",
        "/home/xulc/flash_drought/process/RECO-draught-analysis/code3_nonflash_SMrz/result/reco_response_nonflash_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
        "/home/xulc/flash_drought/process/RECO-draught-analysis/code3_ERA5_root_nonflash/result/reco_response_nonflash_ERA5L_root_drought_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
    ),
    ComparisonItem(
        "RECO",
        "code4",
        "/home/xulc/flash_drought/process/RECO-draught-analysis/code4_nonflash_SMs/result/reco_response_nonflash_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
        "/home/xulc/flash_drought/process/RECO-draught-analysis/code4_ERA5_swvl1_nonflash/result/reco_response_nonflash_ERA5L_swvl1_drought_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
    ),
]


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


def clean_time(values: Iterable[float]) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
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


def finite_mean(values: Iterable[float]) -> float:
    arr = np.asarray(values, dtype=np.float64)
    valid = np.isfinite(arr)
    if not np.any(valid):
        return math.nan
    return float(np.nanmean(arr[valid]))


def fit_trend(years: np.ndarray, values: np.ndarray) -> Dict[str, float]:
    valid = np.isfinite(years) & np.isfinite(values)
    years = years[valid].astype(np.float64, copy=False)
    values = values[valid].astype(np.float64, copy=False)
    if years.size < 2:
        return {
            "slope_days_per_decade": math.nan,
            "intercept": math.nan,
            "first_year": math.nan,
            "last_year": math.nan,
            "years_used": int(years.size),
        }
    slope, intercept = np.polyfit(years, values, 1)
    return {
        "slope_days_per_decade": float(slope * 10.0),
        "intercept": float(intercept),
        "first_year": int(years.min()),
        "last_year": int(years.max()),
        "years_used": int(years.size),
    }


def build_annual_df(
    path: str,
    source: str,
    variable: str,
    code: str,
    mean_func: Callable[[Iterable[float], Iterable[float]], float],
) -> pd.DataFrame:
    with nc.Dataset(path, "r") as ds:
        years = to_numpy(ds.variables["onset_year"])
        lat = to_numpy(ds.variables["lat"])
        response = clean_time(to_numpy(ds.variables["t_response_onset_start"]))
        recovery = clean_time(to_numpy(ds.variables["t_recover_to_baseline"]))
        response_detected = to_numpy(ds.variables["response_detected"]) == 1

    response_mask = response_detected & np.isfinite(years) & np.isfinite(response) & np.isfinite(lat)
    recovery_mask = np.isfinite(years) & np.isfinite(recovery) & np.isfinite(lat)

    response_df = pd.DataFrame(
        {
            "year": years[response_mask].astype(int),
            "response_days": response[response_mask],
            "lat": lat[response_mask],
        }
    )
    recovery_df = pd.DataFrame(
        {
            "year": years[recovery_mask].astype(int),
            "recovery_days": recovery[recovery_mask],
            "lat": lat[recovery_mask],
        }
    )

    annual_response = response_df.groupby("year").apply(
        lambda g: pd.Series(
            {
                "response_mean": mean_func(g["response_days"].to_numpy(), g["lat"].to_numpy()),
                "response_median": float(np.nanmedian(g["response_days"].to_numpy())),
                "response_count": int(g["response_days"].shape[0]),
            }
        )
    )
    annual_recovery = recovery_df.groupby("year").apply(
        lambda g: pd.Series(
            {
                "recovery_mean": mean_func(g["recovery_days"].to_numpy(), g["lat"].to_numpy()),
                "recovery_median": float(np.nanmedian(g["recovery_days"].to_numpy())),
                "recovery_count": int(g["recovery_days"].shape[0]),
            }
        )
    )

    annual = annual_response.join(annual_recovery, how="outer").reset_index()
    annual.insert(0, "source", source)
    annual.insert(0, "code", code)
    annual.insert(0, "variable", variable)
    return annual.sort_values("year").reset_index(drop=True)


def add_trend_line(ax: plt.Axes, years: np.ndarray, values: np.ndarray, color: str) -> Dict[str, float]:
    trend = fit_trend(years, values)
    if math.isfinite(trend["slope_days_per_decade"]):
        x = np.asarray(years, dtype=float)
        y = trend["intercept"] + (trend["slope_days_per_decade"] / 10.0) * x
        ax.plot(x, y, linestyle="--", linewidth=1.6, color=color, alpha=0.9)
    return trend


def plot_item(item: ComparisonItem, combined: pd.DataFrame, out_dir: str) -> List[Dict[str, object]]:
    subset = combined[(combined["variable"] == item.variable) & (combined["code"] == item.code)].copy()
    fig, axes = plt.subplots(2, 1, figsize=(11.5, 8.5), sharex=True, constrained_layout=True)
    summary_rows: List[Dict[str, object]] = []

    for metric, ax, ylabel in [
        ("response_mean", axes[0], "Response time (days)"),
        ("recovery_mean", axes[1], "Recovery time (days)"),
    ]:
        for source in ["GLEAM", "ERA5"]:
            src = subset[subset["source"] == source].sort_values("year")
            years = src["year"].to_numpy(dtype=float)
            values = src[metric].to_numpy(dtype=float)
            style = SOURCE_STYLES[source]
            ax.plot(
                years,
                values,
                label=f"{source} annual mean",
                color=style["color"],
                marker=style["marker"],
                markersize=4.2,
                linewidth=2.1,
            )
            trend = add_trend_line(ax, years, values, style["color"])
            summary_rows.append(
                {
                    "variable": item.variable,
                    "code": item.code,
                    "scenario": item.scenario_label,
                    "metric": metric,
                    "source": source,
                    **trend,
                    "mean_value": float(np.nanmean(values)) if np.isfinite(values).any() else math.nan,
                }
            )

        ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.35)
        ax.set_ylabel(ylabel)
        ax.legend(loc="best", frameon=False, ncol=2)

    trend_text_lines = []
    summary_df = pd.DataFrame(summary_rows)
    for metric_name, short_label in [("response_mean", "Resp"), ("recovery_mean", "Rec")]:
        for source in ["GLEAM", "ERA5"]:
            row = summary_df[(summary_df["metric"] == metric_name) & (summary_df["source"] == source)].iloc[0]
            slope = row["slope_days_per_decade"]
            if math.isfinite(float(slope)):
                trend_text_lines.append(f"{short_label} {source}: {slope:+.2f} d/dec")
            else:
                trend_text_lines.append(f"{short_label} {source}: NA")

    axes[0].set_title(f"{item.variable} {item.code} ({item.scenario_label})")
    axes[0].text(
        0.01,
        1.14,
        " | ".join(trend_text_lines),
        transform=axes[0].transAxes,
        fontsize=10,
        color="#333333",
    )
    axes[1].set_xlabel("Year")

    png_path = os.path.join(out_dir, f"{item.variable.lower()}_{item.code}_era5_vs_gleam_response_recovery.png")
    fig.savefig(png_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return summary_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUT_DIR,
        help="Directory for CSV and PNG outputs.",
    )
    parser.add_argument(
        "--mean-mode",
        choices=["weighted", "no_weight"],
        default="weighted",
        help="Use latitude-area-weighted means or plain unweighted pixel means.",
    )
    return parser.parse_args()


def resolve_mean_func(mean_mode: str) -> Callable[[Iterable[float], Iterable[float]], float]:
    if mean_mode == "weighted":
        return finite_weighted_mean
    if mean_mode == "no_weight":
        return lambda values, _latitudes: finite_mean(values)
    raise ValueError(f"Unsupported mean mode: {mean_mode}")


def main() -> None:
    args = parse_args()
    out_dir = os.path.abspath(args.out_dir)
    detail_csv = os.path.join(out_dir, DEFAULT_DETAIL_CSV_NAME)
    summary_csv = os.path.join(out_dir, DEFAULT_SUMMARY_CSV_NAME)
    mean_func = resolve_mean_func(args.mean_mode)

    os.makedirs(out_dir, exist_ok=True)
    annual_frames = []
    all_summary_rows: List[Dict[str, object]] = []

    for item in ITEMS:
        annual_frames.append(build_annual_df(item.gleam_path, "GLEAM", item.variable, item.code, mean_func))
        annual_frames.append(build_annual_df(item.era5_path, "ERA5", item.variable, item.code, mean_func))

    combined = pd.concat(annual_frames, ignore_index=True)
    combined["scenario"] = combined["code"].map(SCENARIO_LABELS)
    combined = combined.sort_values(["variable", "code", "source", "year"]).reset_index(drop=True)
    combined.to_csv(detail_csv, index=False)

    for item in ITEMS:
        all_summary_rows.extend(plot_item(item, combined, out_dir))

    summary = pd.DataFrame(all_summary_rows).sort_values(["variable", "code", "metric", "source"]).reset_index(drop=True)
    summary.to_csv(summary_csv, index=False)
    print(f"Mean mode: {args.mean_mode}")
    print(f"Wrote annual table: {detail_csv}")
    print(f"Wrote trend summary: {summary_csv}")
    print(f"Wrote {len(ITEMS)} figures to: {out_dir}")


if __name__ == "__main__":
    main()
