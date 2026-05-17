#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List

import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np
import pandas as pd
from scipy.stats import linregress


BASE_DIR = "/home/xulc/flash_drought"
OUTPUT_DIR = os.path.join(BASE_DIR, "process/result_analysis/GPP_trend")
PLOT_DIR = os.path.join(OUTPUT_DIR, "plots")
os.makedirs(PLOT_DIR, exist_ok=True)

YEARS = np.arange(1980, 2025, dtype=np.int32)
YEAR_MIN = int(YEARS[0])
YEAR_MAX = int(YEARS[-1])
CHUNK_SIZE = 2_000_000
ABS_SCALE_FACTOR = 0.01


@dataclass(frozen=True)
class DatasetSpec:
    key: str
    drought_type: str
    soil_layer: str
    path: str


DATASETS: List[DatasetSpec] = [
    DatasetSpec(
        key="flash_SMrz",
        drought_type="flash",
        soil_layer="SMrz",
        path=os.path.join(
            BASE_DIR,
            "process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v11_with_abs.nc",
        ),
    ),
    DatasetSpec(
        key="flash_SMs",
        drought_type="flash",
        soil_layer="SMs",
        path=os.path.join(
            BASE_DIR,
            "process/GPP-draught-analysis/code2_SMs/results/gpp_response_SMs_events_global_v11_with_abs.nc",
        ),
    ),
    DatasetSpec(
        key="nonflash_SMrz",
        drought_type="nonflash",
        soil_layer="SMrz",
        path=os.path.join(
            BASE_DIR,
            "process/GPP-draught-analysis/code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v11_global_with_abs.nc",
        ),
    ),
    DatasetSpec(
        key="nonflash_SMs",
        drought_type="nonflash",
        soil_layer="SMs",
        path=os.path.join(
            BASE_DIR,
            "process/GPP-draught-analysis/code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v11_global_with_abs.nc",
        ),
    ),
]


METRIC_VAR_MAP: Dict[str, str] = {
    "t_min_mean": "t_min",
    "t_response_mean": "t_response",
    "t_impact_mean": "t_impact",
    "t_recover_mean": "t_recover",
    "amp_max_mean": "amp_max",
    "recovery_rate_mean": "recovery_rate",
    "gpp_min_abs_mean": "gpp_min_abs",
    "gpp_drop_abs_mean": "gpp_drop_abs",
    "gpp_recovery_rate_abs_mean": "gpp_recovery_rate_abs",
}

ABSOLUTE_METRICS = {"gpp_min_abs_mean", "gpp_drop_abs_mean", "gpp_recovery_rate_abs_mean"}

TREND_INDICATORS = [
    "events",
    "response_count",
    "response_ratio",
    "response_speed_proxy_mean",
    "t_min_mean",
    "t_response_mean",
    "t_impact_mean",
    "t_recover_mean",
    "amp_max_mean",
    "recovery_rate_mean",
    "gpp_min_abs_mean",
    "gpp_drop_abs_mean",
    "gpp_recovery_rate_abs_mean",
]

SCENARIO_LABELS = {
    "flash_SMrz": "Flash-SMrz",
    "flash_SMs": "Flash-SMs",
    "nonflash_SMrz": "Nonflash-SMrz",
    "nonflash_SMs": "Nonflash-SMs",
}

SCENARIO_COLORS = {
    "flash_SMrz": "#d73027",
    "flash_SMs": "#fc8d59",
    "nonflash_SMrz": "#4575b4",
    "nonflash_SMs": "#91bfdb",
}


def _to_float(arr, fill_value) -> np.ndarray:
    if isinstance(arr, np.ma.MaskedArray):
        data = arr.filled(np.nan).astype(np.float64, copy=False)
    else:
        data = np.asarray(arr, dtype=np.float64)
    if fill_value is not None:
        data[data == fill_value] = np.nan
    return data


def _read_var_chunk(var_obj, start: int, end: int) -> np.ndarray:
    fill = getattr(var_obj, "_FillValue", None)
    return _to_float(var_obj[start:end], fill)


def _year_var_name(ds: nc.Dataset) -> str:
    if "drought_start_year" in ds.variables:
        return "drought_start_year"
    if "onset_year" in ds.variables:
        return "onset_year"
    raise KeyError("Neither drought_start_year nor onset_year is available.")


def aggregate_dataset(spec: DatasetSpec) -> pd.DataFrame:
    if not os.path.exists(spec.path):
        raise FileNotFoundError(spec.path)

    n_year = len(YEARS)
    events = np.zeros(n_year, dtype=np.float64)
    response_count = np.zeros(n_year, dtype=np.float64)
    metric_sums = {k: np.zeros(n_year, dtype=np.float64) for k in METRIC_VAR_MAP}
    metric_counts = {k: np.zeros(n_year, dtype=np.float64) for k in METRIC_VAR_MAP}
    speed_sums = np.zeros(n_year, dtype=np.float64)
    speed_counts = np.zeros(n_year, dtype=np.float64)

    with nc.Dataset(spec.path, "r") as ds:
        n_events = len(ds.dimensions["event"])
        year_name = _year_var_name(ds)
        print(f"[{spec.key}] events={n_events} year_var={year_name}")

        response_var = ds.variables["response_detected"]
        metric_vars = {k: ds.variables[v] for k, v in METRIC_VAR_MAP.items()}
        year_var = ds.variables[year_name]

        for start in range(0, n_events, CHUNK_SIZE):
            end = min(start + CHUNK_SIZE, n_events)
            years_raw = _read_var_chunk(year_var, start, end)
            response_raw = _read_var_chunk(response_var, start, end)

            finite_year = np.isfinite(years_raw)
            if not np.any(finite_year):
                continue

            years_int = years_raw.astype(np.int32, copy=False)
            in_range = finite_year & (years_int >= YEAR_MIN) & (years_int <= YEAR_MAX)
            if not np.any(in_range):
                continue

            year_idx_all = years_int[in_range] - YEAR_MIN
            events += np.bincount(year_idx_all, minlength=n_year)

            responded = in_range & np.isfinite(response_raw) & (response_raw > 0)
            if np.any(responded):
                year_idx_resp = years_int[responded] - YEAR_MIN
                response_count += np.bincount(year_idx_resp, minlength=n_year)

            for metric_name, var_obj in metric_vars.items():
                values = _read_var_chunk(var_obj, start, end)
                if metric_name in ABSOLUTE_METRICS:
                    values = values * ABS_SCALE_FACTOR
                valid = responded & np.isfinite(values)
                if not np.any(valid):
                    continue
                year_idx_metric = years_int[valid] - YEAR_MIN
                metric_sums[metric_name] += np.bincount(
                    year_idx_metric, weights=values[valid], minlength=n_year
                )
                metric_counts[metric_name] += np.bincount(year_idx_metric, minlength=n_year)

            t_response_vals = _read_var_chunk(metric_vars["t_response_mean"], start, end)
            valid_speed = responded & np.isfinite(t_response_vals) & (t_response_vals > 0)
            if np.any(valid_speed):
                year_idx_speed = years_int[valid_speed] - YEAR_MIN
                speed_vals = 1.0 / t_response_vals[valid_speed]
                speed_sums += np.bincount(year_idx_speed, weights=speed_vals, minlength=n_year)
                speed_counts += np.bincount(year_idx_speed, minlength=n_year)

    out = pd.DataFrame(
        {
            "year": YEARS,
            "scenario": spec.key,
            "drought_type": spec.drought_type,
            "soil_layer": spec.soil_layer,
            "events": events,
            "response_count": response_count,
        }
    )

    ratio_arr = np.full(n_year, np.nan, dtype=np.float64)
    np.divide(response_count, events, out=ratio_arr, where=events > 0)
    out["response_ratio"] = ratio_arr

    for metric_name in METRIC_VAR_MAP:
        mean_arr = np.full(n_year, np.nan, dtype=np.float64)
        np.divide(
            metric_sums[metric_name],
            metric_counts[metric_name],
            out=mean_arr,
            where=metric_counts[metric_name] > 0,
        )
        out[metric_name] = mean_arr

    speed_arr = np.full(n_year, np.nan, dtype=np.float64)
    np.divide(speed_sums, speed_counts, out=speed_arr, where=speed_counts > 0)
    out["response_speed_proxy_mean"] = speed_arr

    return out


def calc_trend(years: np.ndarray, values: np.ndarray) -> Dict[str, float]:
    mask = np.isfinite(values)
    if int(mask.sum()) < 3:
        return {
            "slope": np.nan,
            "intercept": np.nan,
            "r2": np.nan,
            "pvalue": np.nan,
            "n_years": int(mask.sum()),
        }
    res = linregress(years[mask], values[mask])
    return {
        "slope": float(res.slope),
        "intercept": float(res.intercept),
        "r2": float(res.rvalue * res.rvalue),
        "pvalue": float(res.pvalue),
        "n_years": int(mask.sum()),
    }


def build_trend_table(df: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict] = []
    for scenario, grp in df.groupby("scenario"):
        grp = grp.sort_values("year")
        years = grp["year"].to_numpy(dtype=np.float64)
        drought_type = grp["drought_type"].iloc[0]
        soil_layer = grp["soil_layer"].iloc[0]
        for ind in TREND_INDICATORS:
            vals = grp[ind].to_numpy(dtype=np.float64)
            stat = calc_trend(years, vals)
            first_val = vals[0] if np.isfinite(vals[0]) else np.nan
            last_val = vals[-1] if np.isfinite(vals[-1]) else np.nan
            rows.append(
                {
                    "scenario": scenario,
                    "label": SCENARIO_LABELS.get(scenario, scenario),
                    "drought_type": drought_type,
                    "soil_layer": soil_layer,
                    "indicator": ind,
                    "slope_per_year": stat["slope"],
                    "intercept": stat["intercept"],
                    "r2": stat["r2"],
                    "pvalue": stat["pvalue"],
                    "n_years_used": stat["n_years"],
                    "start_year_value": first_val,
                    "end_year_value": last_val,
                    "change_1980_2024": (last_val - first_val)
                    if (np.isfinite(first_val) and np.isfinite(last_val))
                    else np.nan,
                }
            )
    return pd.DataFrame(rows)


def plot_indicator(df: pd.DataFrame, indicator: str, ylabel: str, out_png: str) -> None:
    fig, ax = plt.subplots(figsize=(10, 5), dpi=180)
    order = ["flash_SMrz", "flash_SMs", "nonflash_SMrz", "nonflash_SMs"]
    for sc in order:
        grp = df[df["scenario"] == sc].sort_values("year")
        if grp.empty:
            continue
        x = grp["year"].to_numpy(dtype=np.float64)
        y = grp[indicator].to_numpy(dtype=np.float64)
        color = SCENARIO_COLORS.get(sc, None)
        label = SCENARIO_LABELS.get(sc, sc)
        ax.plot(x, y, color=color, linewidth=1.6, alpha=0.9, label=label)

        mask = np.isfinite(y)
        if int(mask.sum()) >= 3:
            lr = linregress(x[mask], y[mask])
            yfit = lr.intercept + lr.slope * x
            ax.plot(x, yfit, color=color, linestyle="--", linewidth=1.1, alpha=0.9)

    ax.set_xlabel("Year")
    ax.set_ylabel(ylabel)
    ax.set_title(f"GPP {indicator} trend (1980-2024)")
    ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.4)
    ax.legend(loc="best", fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def plot_panel(df: pd.DataFrame, out_png: str) -> None:
    indicators = [
        ("response_ratio", "Response ratio"),
        ("response_speed_proxy_mean", "Response speed proxy mean (1/day)"),
        ("gpp_drop_abs_mean", "Mean GPP drop abs (gC m^-2 day^-1)"),
        ("gpp_recovery_rate_abs_mean", "Mean GPP recovery rate abs (gC m^-2 day^-2)"),
    ]
    order = ["flash_SMrz", "flash_SMs", "nonflash_SMrz", "nonflash_SMs"]

    fig, axes = plt.subplots(2, 2, figsize=(13, 8), dpi=200, sharex=True)
    axes = axes.ravel()
    for i, (ind, ylabel) in enumerate(indicators):
        ax = axes[i]
        for sc in order:
            grp = df[df["scenario"] == sc].sort_values("year")
            if grp.empty:
                continue
            x = grp["year"].to_numpy(dtype=np.float64)
            y = grp[ind].to_numpy(dtype=np.float64)
            color = SCENARIO_COLORS.get(sc, None)
            label = SCENARIO_LABELS.get(sc, sc)
            ax.plot(x, y, color=color, linewidth=1.4, alpha=0.9, label=label)

            mask = np.isfinite(y)
            if int(mask.sum()) >= 3:
                lr = linregress(x[mask], y[mask])
                yfit = lr.intercept + lr.slope * x
                ax.plot(x, yfit, color=color, linestyle="--", linewidth=1.0, alpha=0.8)

        ax.set_ylabel(ylabel)
        ax.grid(True, linestyle="--", linewidth=0.35, alpha=0.35)
        ax.set_title(ind)

    axes[2].set_xlabel("Year")
    axes[3].set_xlabel("Year")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.01))
    fig.suptitle("Global GPP response trends to flash/nonflash drought (1980-2024)", y=1.04)
    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)

def plot_additional_panel(df: pd.DataFrame, out_png: str) -> None:
    indicators = [
        ("gpp_min_abs_mean", "Mean GPP min abs (gC m^-2 day^-1)"),
        ("t_min_mean", "Mean t_min (days)"),
        ("t_response_mean", "Mean t_response (days)"),
        ("t_impact_mean", "Mean t_impact (days)"),
        ("t_recover_mean", "Mean t_recover (days)"),
    ]
    order = ["flash_SMrz", "flash_SMs", "nonflash_SMrz", "nonflash_SMs"]

    fig, axes = plt.subplots(3, 2, figsize=(13, 11), dpi=200, sharex=True)
    axes = axes.ravel()
    for i, (ind, ylabel) in enumerate(indicators):
        ax = axes[i]
        for sc in order:
            grp = df[df["scenario"] == sc].sort_values("year")
            if grp.empty:
                continue
            x = grp["year"].to_numpy(dtype=np.float64)
            y = grp[ind].to_numpy(dtype=np.float64)
            color = SCENARIO_COLORS.get(sc, None)
            label = SCENARIO_LABELS.get(sc, sc)
            ax.plot(x, y, color=color, linewidth=1.4, alpha=0.9, label=label)

            mask = np.isfinite(y)
            if int(mask.sum()) >= 3:
                lr = linregress(x[mask], y[mask])
                yfit = lr.intercept + lr.slope * x
                ax.plot(x, yfit, color=color, linestyle="--", linewidth=1.0, alpha=0.8)

        ax.set_ylabel(ylabel)
        ax.grid(True, linestyle="--", linewidth=0.35, alpha=0.35)
        ax.set_title(ind)

    for idx in [4, 5]:
        axes[idx].set_xlabel("Year")
    # Hide the unused 6th subplot.
    if len(indicators) < len(axes):
        axes[-1].axis("off")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.01))
    fig.suptitle("Additional global GPP response trends (1980-2024)", y=1.04)
    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def write_summary_md(trend_df: pd.DataFrame, out_md: str) -> None:
    lines: List[str] = []
    lines.append("# GPP Response Trend Analysis (1980-2024)")
    lines.append("")
    lines.append("## Definitions")
    lines.append("- `response_ratio` = response_count / events")
    lines.append("- `response_speed_proxy_mean` = mean(1 / t_response), only valid responded events")
    lines.append(f"- absolute GPP metrics are scaled by factor `{ABS_SCALE_FACTOR}` (DN -> flux)")
    lines.append("")
    lines.append("## Input Files")
    for spec in DATASETS:
        lines.append(f"- `{spec.key}`: `{spec.path}`")
    lines.append("")

    lines.append("## Significant Trends (p < 0.05)")
    sig = trend_df[np.isfinite(trend_df["pvalue"]) & (trend_df["pvalue"] < 0.05)].copy()
    if sig.empty:
        lines.append("- No significant trend found under p < 0.05.")
    else:
        for _, row in sig.sort_values(["indicator", "pvalue"]).iterrows():
            lines.append(
                "- {label} | {indicator}: slope={slope:.6f}/yr, p={p:.3g}, R2={r2:.3f}".format(
                    label=row["label"],
                    indicator=row["indicator"],
                    slope=row["slope_per_year"],
                    p=row["pvalue"],
                    r2=row["r2"],
                )
            )
    lines.append("")

    lines.append("## Files Generated")
    lines.append("- `gpp_yearly_response_timeseries_1980_2024.csv`")
    lines.append("- `gpp_response_trend_summary_1980_2024.csv`")
    lines.append("- `plots/gpp_trend_panel_2x2.png`")
    lines.append("- `plots/gpp_response_ratio_trend.png`")
    lines.append("- `plots/gpp_response_speed_proxy_trend.png`")
    lines.append("- `plots/gpp_min_abs_trend.png`")
    lines.append("- `plots/t_min_trend.png`")
    lines.append("- `plots/t_response_trend.png`")
    lines.append("- `plots/t_impact_trend.png`")
    lines.append("- `plots/t_recover_trend.png`")
    lines.append("- `plots/gpp_drop_abs_trend.png`")
    lines.append("- `plots/gpp_recovery_abs_trend.png`")
    lines.append("- `plots/gpp_trend_additional_panel_2x2.png`")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(PLOT_DIR, exist_ok=True)

    yearly_frames = [aggregate_dataset(spec) for spec in DATASETS]
    yearly_df = pd.concat(yearly_frames, ignore_index=True)
    yearly_df = yearly_df.sort_values(["scenario", "year"]).reset_index(drop=True)

    yearly_csv = os.path.join(OUTPUT_DIR, "gpp_yearly_response_timeseries_1980_2024.csv")
    yearly_df.to_csv(yearly_csv, index=False, encoding="utf-8")

    trend_df = build_trend_table(yearly_df)
    trend_df = trend_df.sort_values(["indicator", "scenario"]).reset_index(drop=True)
    trend_csv = os.path.join(OUTPUT_DIR, "gpp_response_trend_summary_1980_2024.csv")
    trend_df.to_csv(trend_csv, index=False, encoding="utf-8")

    plot_panel(yearly_df, os.path.join(PLOT_DIR, "gpp_trend_panel_2x2.png"))
    plot_additional_panel(yearly_df, os.path.join(PLOT_DIR, "gpp_trend_additional_panel_2x2.png"))
    plot_indicator(
        yearly_df,
        indicator="response_ratio",
        ylabel="Response ratio",
        out_png=os.path.join(PLOT_DIR, "gpp_response_ratio_trend.png"),
    )
    plot_indicator(
        yearly_df,
        indicator="response_speed_proxy_mean",
        ylabel="Response speed proxy mean (1/day)",
        out_png=os.path.join(PLOT_DIR, "gpp_response_speed_proxy_trend.png"),
    )
    plot_indicator(
        yearly_df,
        indicator="gpp_min_abs_mean",
        ylabel="Mean GPP min abs (gC m^-2 day^-1)",
        out_png=os.path.join(PLOT_DIR, "gpp_min_abs_trend.png"),
    )
    plot_indicator(
        yearly_df,
        indicator="t_min_mean",
        ylabel="Mean t_min (days)",
        out_png=os.path.join(PLOT_DIR, "t_min_trend.png"),
    )
    plot_indicator(
        yearly_df,
        indicator="t_response_mean",
        ylabel="Mean t_response (days)",
        out_png=os.path.join(PLOT_DIR, "t_response_trend.png"),
    )
    plot_indicator(
        yearly_df,
        indicator="t_impact_mean",
        ylabel="Mean t_impact (days)",
        out_png=os.path.join(PLOT_DIR, "t_impact_trend.png"),
    )
    plot_indicator(
        yearly_df,
        indicator="t_recover_mean",
        ylabel="Mean t_recover (days)",
        out_png=os.path.join(PLOT_DIR, "t_recover_trend.png"),
    )
    plot_indicator(
        yearly_df,
        indicator="gpp_drop_abs_mean",
        ylabel="Mean GPP drop abs (gC m^-2 day^-1)",
        out_png=os.path.join(PLOT_DIR, "gpp_drop_abs_trend.png"),
    )
    plot_indicator(
        yearly_df,
        indicator="gpp_recovery_rate_abs_mean",
        ylabel="Mean GPP recovery rate abs (gC m^-2 day^-2)",
        out_png=os.path.join(PLOT_DIR, "gpp_recovery_abs_trend.png"),
    )

    summary_md = os.path.join(OUTPUT_DIR, "gpp_response_trend_summary_1980_2024.md")
    write_summary_md(trend_df, summary_md)

    print("[DONE] output_dir =", OUTPUT_DIR)
    print("[DONE] yearly_csv =", yearly_csv)
    print("[DONE] trend_csv =", trend_csv)
    print("[DONE] summary_md =", summary_md)


if __name__ == "__main__":
    main()
