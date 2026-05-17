#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Dict, List

import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np
import pandas as pd
from scipy.stats import linregress


BASE_DIR = "/home/xulc/flash_drought"
YEARS = np.arange(1980, 2025, dtype=np.int32)
YEAR_MIN = int(YEARS[0])
YEAR_MAX = int(YEARS[-1])
CHUNK_SIZE = 2_000_000


@dataclass(frozen=True)
class DatasetSpec:
    key: str
    drought_type: str
    soil_layer: str
    path: str


@dataclass(frozen=True)
class TargetConfig:
    key: str
    display: str
    output_dir: str
    event_prefix: str
    abs_scale_factor: float
    abs_unit: str
    abs_rate_unit: str
    datasets: List[DatasetSpec]


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

SCENARIO_ORDER = ["flash_SMrz", "flash_SMs", "nonflash_SMrz", "nonflash_SMs"]


TARGET_CONFIGS: Dict[str, TargetConfig] = {
    "nee": TargetConfig(
        key="nee",
        display="NEE",
        output_dir=os.path.join(BASE_DIR, "process/NEE-draught-analysis/NEE_trend"),
        event_prefix="nee",
        abs_scale_factor=0.01,
        abs_unit="gC m^-2 day^-1",
        abs_rate_unit="gC m^-2 day^-2",
        datasets=[
            DatasetSpec(
                key="flash_SMrz",
                drought_type="flash",
                soil_layer="SMrz",
                path=os.path.join(
                    BASE_DIR,
                    "process/NEE-draught-analysis/code1SMrz/result/nee_response_events_global_v11_with_abs.nc",
                ),
            ),
            DatasetSpec(
                key="flash_SMs",
                drought_type="flash",
                soil_layer="SMs",
                path=os.path.join(
                    BASE_DIR,
                    "process/NEE-draught-analysis/code2SMs/result/nee_response_SMs_events_global_v11_with_abs.nc",
                ),
            ),
            DatasetSpec(
                key="nonflash_SMrz",
                drought_type="nonflash",
                soil_layer="SMrz",
                path=os.path.join(
                    BASE_DIR,
                    "process/NEE-draught-analysis/code3_nonflash_SMrz/result/nee_response_nonflash_SMrz_drought_v11_global_with_abs.nc",
                ),
            ),
            DatasetSpec(
                key="nonflash_SMs",
                drought_type="nonflash",
                soil_layer="SMs",
                path=os.path.join(
                    BASE_DIR,
                    "process/NEE-draught-analysis/code4_nonflash_SMs/result/nee_response_nonflash_SMs_drought_v11_global_with_abs.nc",
                ),
            ),
        ],
    ),
    "reco": TargetConfig(
        key="reco",
        display="RECO",
        output_dir=os.path.join(BASE_DIR, "process/RECO-draught-analysis/RECO_trend"),
        event_prefix="reco",
        abs_scale_factor=0.01,
        abs_unit="gC m^-2 day^-1",
        abs_rate_unit="gC m^-2 day^-2",
        datasets=[
            DatasetSpec(
                key="flash_SMrz",
                drought_type="flash",
                soil_layer="SMrz",
                path=os.path.join(
                    BASE_DIR,
                    "process/RECO-draught-analysis/code1/results/reco_response_events_global_v11_with_abs.nc",
                ),
            ),
            DatasetSpec(
                key="flash_SMs",
                drought_type="flash",
                soil_layer="SMs",
                path=os.path.join(
                    BASE_DIR,
                    "process/RECO-draught-analysis/code2_SMs/results/reco_response_SMs_events_global_v11_with_abs.nc",
                ),
            ),
            DatasetSpec(
                key="nonflash_SMrz",
                drought_type="nonflash",
                soil_layer="SMrz",
                path=os.path.join(
                    BASE_DIR,
                    "process/RECO-draught-analysis/code3_nonflash_SMrz/result/reco_response_nonflash_SMrz_drought_v11_global_with_abs.nc",
                ),
            ),
            DatasetSpec(
                key="nonflash_SMs",
                drought_type="nonflash",
                soil_layer="SMs",
                path=os.path.join(
                    BASE_DIR,
                    "process/RECO-draught-analysis/code4_nonflash_SMs/result/reco_response_nonflash_SMs_drought_v11_global_with_abs.nc",
                ),
            ),
        ],
    ),
}


def build_metric_var_map(prefix: str) -> Dict[str, str]:
    return {
        "t_min_mean": "t_min",
        "t_response_mean": "t_response",
        "t_impact_mean": "t_impact",
        "t_recover_mean": "t_recover",
        "amp_max_mean": "amp_max",
        "recovery_rate_mean": "recovery_rate",
        f"{prefix}_min_abs_mean": f"{prefix}_min_abs",
        f"{prefix}_drop_abs_mean": f"{prefix}_drop_abs",
        f"{prefix}_recovery_rate_abs_mean": f"{prefix}_recovery_rate_abs",
    }


def build_plot_labels(cfg: TargetConfig) -> Dict[str, str]:
    return {
        f"{cfg.event_prefix}_min_abs_mean": f"Mean {cfg.display} min abs ({cfg.abs_unit})",
        f"{cfg.event_prefix}_drop_abs_mean": f"Mean {cfg.display} drop abs ({cfg.abs_unit})",
        f"{cfg.event_prefix}_recovery_rate_abs_mean": f"Mean {cfg.display} recovery rate abs ({cfg.abs_rate_unit})",
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


def aggregate_dataset(spec: DatasetSpec, cfg: TargetConfig, metric_var_map: Dict[str, str]) -> pd.DataFrame:
    if not os.path.exists(spec.path):
        raise FileNotFoundError(spec.path)

    abs_metrics = {
        f"{cfg.event_prefix}_min_abs_mean",
        f"{cfg.event_prefix}_drop_abs_mean",
        f"{cfg.event_prefix}_recovery_rate_abs_mean",
    }

    n_year = len(YEARS)
    events = np.zeros(n_year, dtype=np.float64)
    response_count = np.zeros(n_year, dtype=np.float64)
    metric_sums = {k: np.zeros(n_year, dtype=np.float64) for k in metric_var_map}
    metric_counts = {k: np.zeros(n_year, dtype=np.float64) for k in metric_var_map}
    speed_sums = np.zeros(n_year, dtype=np.float64)
    speed_counts = np.zeros(n_year, dtype=np.float64)

    with nc.Dataset(spec.path, "r") as ds:
        n_events = len(ds.dimensions["event"])
        year_name = _year_var_name(ds)
        print(f"[{cfg.key}:{spec.key}] events={n_events} year_var={year_name}")

        response_var = ds.variables["response_detected"]
        metric_vars = {k: ds.variables[v] for k, v in metric_var_map.items()}
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
                if metric_name in abs_metrics:
                    values = values * cfg.abs_scale_factor
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
    out["response_ratio"] = np.divide(
        response_count,
        events,
        out=np.full(n_year, np.nan, dtype=np.float64),
        where=events > 0,
    )

    for metric_name in metric_var_map:
        out[metric_name] = np.divide(
            metric_sums[metric_name],
            metric_counts[metric_name],
            out=np.full(n_year, np.nan, dtype=np.float64),
            where=metric_counts[metric_name] > 0,
        )

    out["response_speed_proxy_mean"] = np.divide(
        speed_sums,
        speed_counts,
        out=np.full(n_year, np.nan, dtype=np.float64),
        where=speed_counts > 0,
    )
    return out


def calc_trend(years: np.ndarray, values: np.ndarray) -> Dict[str, float]:
    mask = np.isfinite(values)
    if int(mask.sum()) < 3:
        return {"slope": np.nan, "intercept": np.nan, "r2": np.nan, "pvalue": np.nan, "n_years": int(mask.sum())}
    res = linregress(years[mask], values[mask])
    return {
        "slope": float(res.slope),
        "intercept": float(res.intercept),
        "r2": float(res.rvalue * res.rvalue),
        "pvalue": float(res.pvalue),
        "n_years": int(mask.sum()),
    }


def build_trend_table(df: pd.DataFrame, indicators: List[str]) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    for scenario, grp in df.groupby("scenario"):
        grp = grp.sort_values("year")
        years = grp["year"].to_numpy(dtype=np.float64)
        for ind in indicators:
            vals = grp[ind].to_numpy(dtype=np.float64)
            stat = calc_trend(years, vals)
            first_val = vals[0] if np.isfinite(vals[0]) else np.nan
            last_val = vals[-1] if np.isfinite(vals[-1]) else np.nan
            rows.append(
                {
                    "scenario": scenario,
                    "label": SCENARIO_LABELS.get(scenario, scenario),
                    "drought_type": grp["drought_type"].iloc[0],
                    "soil_layer": grp["soil_layer"].iloc[0],
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


def plot_indicator(df: pd.DataFrame, indicator: str, ylabel: str, out_png: str, title_prefix: str) -> None:
    fig, ax = plt.subplots(figsize=(10, 5), dpi=180)
    for sc in SCENARIO_ORDER:
        grp = df[df["scenario"] == sc].sort_values("year")
        if grp.empty:
            continue
        x = grp["year"].to_numpy(dtype=np.float64)
        y = grp[indicator].to_numpy(dtype=np.float64)
        color = SCENARIO_COLORS.get(sc)
        label = SCENARIO_LABELS.get(sc, sc)
        ax.plot(x, y, color=color, linewidth=1.6, alpha=0.9, label=label)
        mask = np.isfinite(y)
        if int(mask.sum()) >= 3:
            lr = linregress(x[mask], y[mask])
            ax.plot(x, lr.intercept + lr.slope * x, color=color, linestyle="--", linewidth=1.1, alpha=0.9)
    ax.set_xlabel("Year")
    ax.set_ylabel(ylabel)
    ax.set_title(f"{title_prefix} {indicator} trend (1980-2024)")
    ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.4)
    ax.legend(loc="best", fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def plot_panel(df: pd.DataFrame, indicators: List[tuple[str, str]], out_png: str, title: str) -> None:
    n = len(indicators)
    ncols = 2
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(13, 4 * nrows), dpi=200, sharex=True)
    axes = np.atleast_1d(axes).ravel()

    for idx, (ind, ylabel) in enumerate(indicators):
        ax = axes[idx]
        for sc in SCENARIO_ORDER:
            grp = df[df["scenario"] == sc].sort_values("year")
            if grp.empty:
                continue
            x = grp["year"].to_numpy(dtype=np.float64)
            y = grp[ind].to_numpy(dtype=np.float64)
            color = SCENARIO_COLORS.get(sc)
            label = SCENARIO_LABELS.get(sc, sc)
            ax.plot(x, y, color=color, linewidth=1.4, alpha=0.9, label=label)
            mask = np.isfinite(y)
            if int(mask.sum()) >= 3:
                lr = linregress(x[mask], y[mask])
                ax.plot(x, lr.intercept + lr.slope * x, color=color, linestyle="--", linewidth=1.0, alpha=0.8)
        ax.set_ylabel(ylabel)
        ax.set_title(ind)
        ax.grid(True, linestyle="--", linewidth=0.35, alpha=0.35)

    for ax in axes[n:]:
        ax.axis("off")
    for idx in range(max(0, n - ncols), n):
        axes[idx].set_xlabel("Year")

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.01))
    fig.suptitle(title, y=1.03)
    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def write_summary_md(cfg: TargetConfig, trend_df: pd.DataFrame, out_md: str, generated_files: List[str]) -> None:
    lines = [
        f"# {cfg.display} Response Trend Analysis (1980-2024)",
        "",
        "## Definitions",
        "- `response_ratio` = response_count / events",
        "- `response_speed_proxy_mean` = mean(1 / t_response), only valid responded events",
        f"- absolute {cfg.display} metrics are scaled by factor `{cfg.abs_scale_factor}`",
        "",
        "## Input Files",
    ]
    for spec in cfg.datasets:
        lines.append(f"- `{spec.key}`: `{spec.path}`")
    lines.extend(["", "## Significant Trends (p < 0.05)"])
    sig = trend_df[np.isfinite(trend_df["pvalue"]) & (trend_df["pvalue"] < 0.05)].copy()
    if sig.empty:
        lines.append("- No significant trend found under p < 0.05.")
    else:
        for _, row in sig.sort_values(["indicator", "pvalue"]).iterrows():
            lines.append(
                "- {label} | {indicator}: slope={slope:.6f}/yr, p={p:.3g}, R2={r2:.3f}".format(
                    label=row["label"], indicator=row["indicator"], slope=row["slope_per_year"], p=row["pvalue"], r2=row["r2"]
                )
            )
    lines.extend(["", "## Files Generated"])
    lines.extend([f"- `{name}`" for name in generated_files])
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze yearly response trends for NEE or RECO.")
    parser.add_argument("--target", choices=sorted(TARGET_CONFIGS), required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = TARGET_CONFIGS[args.target]
    metric_var_map = build_metric_var_map(cfg.event_prefix)
    trend_indicators = [
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
        f"{cfg.event_prefix}_min_abs_mean",
        f"{cfg.event_prefix}_drop_abs_mean",
        f"{cfg.event_prefix}_recovery_rate_abs_mean",
    ]
    label_map = build_plot_labels(cfg)

    output_dir = cfg.output_dir
    plot_dir = os.path.join(output_dir, "plots")
    os.makedirs(plot_dir, exist_ok=True)

    yearly_frames = [aggregate_dataset(spec, cfg, metric_var_map) for spec in cfg.datasets]
    yearly_df = pd.concat(yearly_frames, ignore_index=True).sort_values(["scenario", "year"]).reset_index(drop=True)

    yearly_csv = os.path.join(output_dir, f"{cfg.key}_yearly_response_timeseries_1980_2024.csv")
    yearly_df.to_csv(yearly_csv, index=False, encoding="utf-8")

    trend_df = build_trend_table(yearly_df, trend_indicators).sort_values(["indicator", "scenario"]).reset_index(drop=True)
    trend_csv = os.path.join(output_dir, f"{cfg.key}_response_trend_summary_1980_2024.csv")
    trend_df.to_csv(trend_csv, index=False, encoding="utf-8")

    main_panel = [
        ("response_ratio", "Response ratio"),
        ("response_speed_proxy_mean", "Response speed proxy mean (1/day)"),
        (f"{cfg.event_prefix}_drop_abs_mean", label_map[f"{cfg.event_prefix}_drop_abs_mean"]),
        (f"{cfg.event_prefix}_recovery_rate_abs_mean", label_map[f"{cfg.event_prefix}_recovery_rate_abs_mean"]),
    ]
    additional_panel = [
        (f"{cfg.event_prefix}_min_abs_mean", label_map[f"{cfg.event_prefix}_min_abs_mean"]),
        ("t_min_mean", "Mean t_min (days)"),
        ("t_response_mean", "Mean t_response (days)"),
        ("t_impact_mean", "Mean t_impact (days)"),
        ("t_recover_mean", "Mean t_recover (days)"),
    ]

    plot_panel(
        yearly_df,
        main_panel,
        os.path.join(plot_dir, f"{cfg.key}_trend_panel_2x2.png"),
        f"Global {cfg.display} response trends to flash/nonflash drought (1980-2024)",
    )
    plot_panel(
        yearly_df,
        additional_panel,
        os.path.join(plot_dir, f"{cfg.key}_trend_additional_panel.png"),
        f"Additional global {cfg.display} response trends (1980-2024)",
    )

    plot_indicator(yearly_df, "response_ratio", "Response ratio", os.path.join(plot_dir, f"{cfg.key}_response_ratio_trend.png"), cfg.display)
    plot_indicator(
        yearly_df,
        "response_speed_proxy_mean",
        "Response speed proxy mean (1/day)",
        os.path.join(plot_dir, f"{cfg.key}_response_speed_proxy_trend.png"),
        cfg.display,
    )
    plot_indicator(
        yearly_df,
        f"{cfg.event_prefix}_min_abs_mean",
        label_map[f"{cfg.event_prefix}_min_abs_mean"],
        os.path.join(plot_dir, f"{cfg.key}_min_abs_trend.png"),
        cfg.display,
    )
    plot_indicator(yearly_df, "t_min_mean", "Mean t_min (days)", os.path.join(plot_dir, f"{cfg.key}_t_min_trend.png"), cfg.display)
    plot_indicator(
        yearly_df,
        "t_response_mean",
        "Mean t_response (days)",
        os.path.join(plot_dir, f"{cfg.key}_t_response_trend.png"),
        cfg.display,
    )
    plot_indicator(yearly_df, "t_impact_mean", "Mean t_impact (days)", os.path.join(plot_dir, f"{cfg.key}_t_impact_trend.png"), cfg.display)
    plot_indicator(
        yearly_df,
        "t_recover_mean",
        "Mean t_recover (days)",
        os.path.join(plot_dir, f"{cfg.key}_t_recover_trend.png"),
        cfg.display,
    )
    plot_indicator(
        yearly_df,
        f"{cfg.event_prefix}_drop_abs_mean",
        label_map[f"{cfg.event_prefix}_drop_abs_mean"],
        os.path.join(plot_dir, f"{cfg.key}_drop_abs_trend.png"),
        cfg.display,
    )
    plot_indicator(
        yearly_df,
        f"{cfg.event_prefix}_recovery_rate_abs_mean",
        label_map[f"{cfg.event_prefix}_recovery_rate_abs_mean"],
        os.path.join(plot_dir, f"{cfg.key}_recovery_abs_trend.png"),
        cfg.display,
    )

    summary_md = os.path.join(output_dir, f"{cfg.key}_response_trend_summary_1980_2024.md")
    write_summary_md(
        cfg,
        trend_df,
        summary_md,
        [
            os.path.basename(yearly_csv),
            os.path.basename(trend_csv),
            f"plots/{cfg.key}_trend_panel_2x2.png",
            f"plots/{cfg.key}_trend_additional_panel.png",
            f"plots/{cfg.key}_response_ratio_trend.png",
            f"plots/{cfg.key}_response_speed_proxy_trend.png",
            f"plots/{cfg.key}_min_abs_trend.png",
            f"plots/{cfg.key}_t_min_trend.png",
            f"plots/{cfg.key}_t_response_trend.png",
            f"plots/{cfg.key}_t_impact_trend.png",
            f"plots/{cfg.key}_t_recover_trend.png",
            f"plots/{cfg.key}_drop_abs_trend.png",
            f"plots/{cfg.key}_recovery_abs_trend.png",
        ],
    )

    print("[DONE] output_dir =", output_dir)
    print("[DONE] yearly_csv =", yearly_csv)
    print("[DONE] trend_csv =", trend_csv)
    print("[DONE] summary_md =", summary_md)


if __name__ == "__main__":
    main()
