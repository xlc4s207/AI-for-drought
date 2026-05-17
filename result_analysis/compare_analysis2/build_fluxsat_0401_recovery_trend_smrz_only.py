#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
"""Plot SMrz-only recovery time trend analysis for BESS vs FluxSat."""

from __future__ import annotations

import csv
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


BASE_DIR = "/home/xulc/flash_drought"
ANNUAL_CSV = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/fluxsat_compare_analysis2/"
    "fluxsat_0401_sensitivity_compare/fluxsat_0401_sensitivity_annual.csv"
)
OUT_COMPARE_PNG = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/fluxsat_compare_analysis2/"
    "fluxsat_0401_sensitivity_compare/fluxsat_0401_sensitivity_recovery_trend_smrz_only.png"
)
OUT_CONCLUSION_PNG = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/conclusion/BESS_Fluxsat_valid/"
    "fluxsat_0401_sensitivity_recovery_trend_smrz_only.png"
)


def read_rows(path: str) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def add_trend_line(ax: plt.Axes, years: np.ndarray, values: np.ndarray, color: str) -> None:
    valid = np.isfinite(years) & np.isfinite(values)
    if np.sum(valid) < 2:
        return
    slope, intercept = np.polyfit(years[valid], values[valid], 1)
    ax.plot(
        years[valid],
        intercept + slope * years[valid],
        linestyle="--",
        linewidth=1.6,
        color=color,
        alpha=0.75,
    )


def main() -> None:
    rows = read_rows(ANNUAL_CSV)
    selected = [
        row
        for row in rows
        if row["code"] == "code1"
        and row["soil_layer"] == "SMrz"
        and row["dataset"] in {"BESS 0401", "FluxSat 0401 rec100cap"}
    ]

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in selected:
        grouped.setdefault(row["dataset"], []).append(row)

    fig, ax = plt.subplots(figsize=(11, 6.6), constrained_layout=True)
    styles = {
        "BESS 0401": {"color": "#CC6677", "marker": "o", "label": "BESS"},
        "FluxSat 0401 rec100cap": {"color": "#0072B2", "marker": "s", "label": "FluxSat"},
    }

    for dataset in ["BESS 0401", "FluxSat 0401 rec100cap"]:
        dataset_rows = sorted(grouped.get(dataset, []), key=lambda r: int(r["year"]))
        if not dataset_rows:
            continue
        years = np.array([int(r["year"]) for r in dataset_rows], dtype=np.float64)
        values = np.array([float(r["recovery_mean"]) for r in dataset_rows], dtype=np.float64)
        if dataset.startswith("FluxSat"):
            keep = years != 2000
            years = years[keep]
            values = values[keep]
        style = styles[dataset]
        ax.plot(
            years,
            values,
            color=style["color"],
            marker=style["marker"],
            markersize=7,
            linewidth=2.8,
            label=style["label"],
        )
        add_trend_line(ax, years, values, style["color"])

    ax.set_title("SMrz Recovery Time Trend Following Flash Drought", fontsize=24)
    ax.set_xlabel("Year", fontsize=18)
    ax.set_ylabel("Recovery Time Mean (days)", fontsize=18)
    ax.set_xlim(1981.5, 2021.5)
    ax.set_ylim(25.0, 50.0)
    ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.35)
    ax.legend(frameon=False, fontsize=16, ncol=2, loc="best")
    ax.tick_params(axis="both", labelsize=15)
    for out_png in (OUT_COMPARE_PNG, OUT_CONCLUSION_PNG):
        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        fig.savefig(out_png, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {OUT_COMPARE_PNG}")
    print(f"Wrote {OUT_CONCLUSION_PNG}")


if __name__ == "__main__":
    main()
