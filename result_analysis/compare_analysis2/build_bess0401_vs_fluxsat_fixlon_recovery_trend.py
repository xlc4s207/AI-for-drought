#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
"""Plot BESS 0401 vs FluxSat fixlon recovery trends for SMrz and SMs."""

from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import rcParams
import numpy as np


BASE_DIR = "/home/xulc/flash_drought"
OUT_DIR = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/"
    "fluxsat_compare_analysis2/bess0401_vs_fluxsat_fixlon_spatial_compare"
)
BESS_ANNUAL = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/compare_analysis2/"
    "v20260401_growingseason_recovery_gsdays/"
    "annual_response_recovery_trends_v20260401_growingseason_recovery_gsdays.csv"
)
FLUXSAT_ANNUAL = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/fluxsat_compare_analysis2/"
    "fluxsat_0401_sensitivity_compare/fluxsat_0401_sensitivity_annual.csv"
)


@dataclass(frozen=True)
class Scenario:
    code: str
    soil_layer: str
    title: str
    out_png: str


SCENARIOS = [
    Scenario(
        code="code1",
        soil_layer="SMrz",
        title="SMrz Recovery Trend: BESS 0401 vs FluxSat fixlon",
        out_png=os.path.join(OUT_DIR, "smrz_recovery_trend_bess0401_vs_fluxsat_fixlon.png"),
    ),
    Scenario(
        code="code2",
        soil_layer="SMs",
        title="SMs Recovery Trend: BESS 0401 vs FluxSat fixlon",
        out_png=os.path.join(OUT_DIR, "sms_recovery_trend_bess0401_vs_fluxsat_fixlon.png"),
    ),
]


def setup_font() -> None:
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


def read_csv_rows(path: str) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def trend_slope(years: np.ndarray, values: np.ndarray) -> float:
    valid = np.isfinite(years) & np.isfinite(values)
    if np.sum(valid) < 2:
        return math.nan
    slope, _ = np.polyfit(years[valid], values[valid], 1)
    return float(slope * 10.0)


def extract_bess_series(rows: list[dict[str, str]], scenario: Scenario) -> tuple[np.ndarray, np.ndarray]:
    years = []
    values = []
    for row in rows:
        if row["variable"] != "GPP":
            continue
        if row["code"] != scenario.code or row["soil_layer"] != scenario.soil_layer:
            continue
        year = int(row["year"])
        if 2000 <= year <= 2019:
            years.append(year)
            values.append(float(row["recovery_mean"]))
    return np.asarray(years, dtype=np.float64), np.asarray(values, dtype=np.float64)


def extract_fluxsat_series(rows: list[dict[str, str]], scenario: Scenario) -> tuple[np.ndarray, np.ndarray]:
    years = []
    values = []
    for row in rows:
        if row["dataset"] != "FluxSat 0401 rec100cap":
            continue
        if row["code"] != scenario.code or row["soil_layer"] != scenario.soil_layer:
            continue
        year = int(row["year"])
        values.append(float(row["recovery_mean"]))
        years.append(year)
    return np.asarray(years, dtype=np.float64), np.asarray(values, dtype=np.float64)


def plot_one(scenario: Scenario, bess_rows: list[dict[str, str]], fluxsat_rows: list[dict[str, str]]) -> None:
    by, bv = extract_bess_series(bess_rows, scenario)
    fy, fv = extract_fluxsat_series(fluxsat_rows, scenario)

    bs = trend_slope(by, bv)
    fs = trend_slope(fy, fv)

    fig, ax = plt.subplots(figsize=(9.5, 5.6), constrained_layout=True)
    ax.plot(by, bv, color="#111111", marker="o", linewidth=2.0, label=f"BESS 0401 ({bs:.2f} d/10a)")
    ax.plot(fy, fv, color="#33a02c", marker="s", linewidth=2.0, label=f"FluxSat fixlon ({fs:.2f} d/10a)")
    ax.set_title(scenario.title)
    ax.set_xlabel("Year")
    ax.set_ylabel("Recovery mean (days)")
    ax.grid(True, alpha=0.25, linewidth=0.6)
    ax.legend(frameon=False)
    ax.set_xlim(1999.5, 2019.5)
    fig.savefig(scenario.out_png, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    setup_font()
    bess_rows = read_csv_rows(BESS_ANNUAL)
    fluxsat_rows = read_csv_rows(FLUXSAT_ANNUAL)
    for scenario in SCENARIOS:
        plot_one(scenario, bess_rows, fluxsat_rows)
        print(f"Wrote {scenario.out_png}")


if __name__ == "__main__":
    main()
