#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
from __future__ import annotations

import csv
import importlib.util
import math
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


BASE_DIR = "/home/xulc/flash_drought"
SOURCE_SCRIPT = (
    f"{BASE_DIR}/process/fluxsat-draught-analysis/analysis/run_fluxsat_lu2025_like_recovery.py"
)
OUT_DIR = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/fluxsat_lu2025_like_recovery_trend"
)
ANNUAL_CSV = os.path.join(OUT_DIR, "fluxsat_lu2025_like_recovery_annual_trend.csv")
SUMMARY_MD = os.path.join(OUT_DIR, "fluxsat_lu2025_like_recovery_trend_summary.md")
FIGURE_PATH = os.path.join(OUT_DIR, "fluxsat_lu2025_like_recovery_trend.png")


def load_source_module():
    spec = importlib.util.spec_from_file_location("fluxsat_lu2025_like_recovery", SOURCE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def finite_slope(years, values):
    years = np.asarray(years, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    valid = np.isfinite(years) & np.isfinite(values)
    years = years[valid]
    values = values[valid]
    if years.size < 2:
        return math.nan
    return float(np.polyfit(years, values, 1)[0] * 10.0)


def fmt(value, decimals=2):
    if value is None:
        return "-"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(float(value)):
            return "-"
        return f"{float(value):,.{decimals}f}"
    return str(value)


def main() -> None:
    Path(OUT_DIR).mkdir(parents=True, exist_ok=True)
    mod = load_source_module()
    mod.setup_chinese_font()

    _, selected_idx, slots, _ = mod.load_time_and_slots(mod.FLUXSAT_FILE)
    results = [
        mod.process_scenario("SMrz", mod.FLUXSAT_FILE, mod.EVENT_FILES["SMrz"], selected_idx, slots),
        mod.process_scenario("SMs", mod.FLUXSAT_FILE, mod.EVENT_FILES["SMs"], selected_idx, slots),
    ]

    annual_rows = []
    summary_rows = []
    for result in results:
        annual_rows.extend(result.annual_rows)
        years = np.asarray([row["year"] for row in result.annual_rows], dtype=np.float64)
        event_mean = np.asarray([row["event_mean_days"] for row in result.annual_rows], dtype=np.float64)
        pixel_mean = np.asarray([row["pixel_mean_days"] for row in result.annual_rows], dtype=np.float64)
        summary_rows.append(
            {
                "scenario": result.scenario,
                "event_mean_all": result.summary["recovery_stats_days_event_level"]["mean"],
                "event_median_all": result.summary["recovery_stats_days_event_level"]["median"],
                "pixel_mean_all": result.summary["recovery_stats_days_pixel_level"]["mean"],
                "pixel_median_all": result.summary["recovery_stats_days_pixel_level"]["median"],
                "event_trend_days_per_decade": finite_slope(years, event_mean),
                "pixel_trend_days_per_decade": finite_slope(years, pixel_mean),
            }
        )

    annual_rows.sort(key=lambda row: (row["scenario"], row["year"]))
    with open(ANNUAL_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scenario",
                "year",
                "event_count",
                "event_mean_days",
                "event_median_days",
                "pixel_count",
                "pixel_mean_days",
                "pixel_median_days",
            ],
        )
        writer.writeheader()
        writer.writerows(annual_rows)

    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True, constrained_layout=True)
    styles = {"SMrz": {"color": "#1f78b4", "marker": "o"}, "SMs": {"color": "#d95f02", "marker": "s"}}
    for result in results:
        rows = sorted(result.annual_rows, key=lambda row: row["year"])
        years = np.asarray([row["year"] for row in rows], dtype=np.float64)
        event_mean = np.asarray([row["event_mean_days"] for row in rows], dtype=np.float64)
        pixel_mean = np.asarray([row["pixel_mean_days"] for row in rows], dtype=np.float64)
        style = styles[result.scenario]
        axes[0].plot(years, event_mean, color=style["color"], marker=style["marker"], linewidth=2.0, markersize=4.0, label=result.scenario)
        axes[1].plot(years, pixel_mean, color=style["color"], marker=style["marker"], linewidth=2.0, markersize=4.0, label=result.scenario)

        valid = np.isfinite(years) & np.isfinite(event_mean)
        if np.count_nonzero(valid) >= 2:
            slope, intercept = np.polyfit(years[valid], event_mean[valid], 1)
            axes[0].plot(years[valid], intercept + slope * years[valid], linestyle="--", color=style["color"], linewidth=1.4, alpha=0.9)
        valid = np.isfinite(years) & np.isfinite(pixel_mean)
        if np.count_nonzero(valid) >= 2:
            slope, intercept = np.polyfit(years[valid], pixel_mean[valid], 1)
            axes[1].plot(years[valid], intercept + slope * years[valid], linestyle="--", color=style["color"], linewidth=1.4, alpha=0.9)

    axes[0].set_title("FluxSat Lu 等 2025 类口径恢复时间趋势（事件平均）")
    axes[0].set_ylabel("恢复时间均值 (天)")
    axes[1].set_title("FluxSat Lu 等 2025 类口径恢复时间趋势（像元平均）")
    axes[1].set_ylabel("恢复时间均值 (天)")
    axes[1].set_xlabel("Year")
    for ax in axes:
        ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.35)
        ax.legend(frameon=False, loc="best")
    fig.savefig(FIGURE_PATH, dpi=220, bbox_inches="tight")
    plt.close(fig)

    lines = [
        "# FluxSat Lu 等 2025 类口径恢复时间趋势汇总",
        "",
        f"- 年际统计：`{ANNUAL_CSV}`",
        f"- 趋势图：`{FIGURE_PATH}`",
        "",
        "| 情景 | 总体事件均值(d) | 总体像元均值(d) | 事件趋势(d/10a) | 像元趋势(d/10a) |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["scenario"],
                    fmt(row["event_mean_all"]),
                    fmt(row["pixel_mean_all"]),
                    fmt(row["event_trend_days_per_decade"]),
                    fmt(row["pixel_trend_days_per_decade"]),
                ]
            )
            + " |"
        )
    Path(SUMMARY_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {ANNUAL_CSV}")
    print(f"Wrote {FIGURE_PATH}")
    print(f"Wrote {SUMMARY_MD}")


if __name__ == "__main__":
    main()
