#!/usr/bin/env python3
"""Build annual trend figures for 12 rec100 result files."""

from __future__ import annotations

import os
import sys
from typing import Dict, Iterable, List

import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import rcParams
import netCDF4 as nc
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from build_compare_analysis2_rec100 import (
    ITEMS,
    Item,
    finite_weighted_mean,
    pick_metric_fields,
    to_numpy,
)


OUT_DIR = "/home/xulc/flash_drought/process/result_analysis/result_weighted/compare_analysis2/trend_figure"
YEAR_START = 1982
YEAR_END = 2021
YEARS = np.arange(YEAR_START, YEAR_END + 1, dtype=np.int32)
VARIABLE_ORDER = ["GPP", "NEE", "RECO"]
SCENARIO_ORDER = [
    ("flash", "SMrz"),
    ("flash", "SMs"),
    ("slow", "SMrz"),
    ("slow", "SMs"),
]
SCENARIO_LABELS = {
    ("flash", "SMrz"): "SMrz_flash",
    ("flash", "SMs"): "SMs_flash",
    ("slow", "SMrz"): "SMrz_slow",
    ("slow", "SMs"): "SMs_slow",
}
SCENARIO_COLORS = {
    ("flash", "SMrz"): "#b22222",
    ("flash", "SMs"): "#ff8c00",
    ("slow", "SMrz"): "#1f78b4",
    ("slow", "SMs"): "#33a02c",
}

METRICS = {
    "change_value": {
        "field_getter": lambda item: pick_metric_fields(item.variable)["change_to_peak_abs"],
        "title_cn": "变化值",
        "ylabel": "变化值",
        "clean_kind": "change_value",
    },
    "response_time": {
        "field_getter": lambda item: "t_response_onset_start",
        "title_cn": "响应时间",
        "ylabel": "天",
        "clean_kind": "time",
    },
    "impact_time": {
        "field_getter": lambda item: "t_impact",
        "title_cn": "影响时间",
        "ylabel": "天",
        "clean_kind": "time",
    },
    "recovery_time": {
        "field_getter": lambda item: "t_recover_to_baseline",
        "title_cn": "恢复时间",
        "ylabel": "天",
        "clean_kind": "time",
    },
}

STAT_ORDER = [("mean", "平均值"), ("median", "中位数")]


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
        common_font_files = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJKSC-Regular.otf",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        ]
        for fp in common_font_files:
            if os.path.exists(fp):
                try:
                    fm.fontManager.addfont(fp)
                    selected = fm.FontProperties(fname=fp).get_name()
                    break
                except Exception:
                    continue
    if selected is not None:
        rcParams["font.sans-serif"] = [selected, "DejaVu Sans"]
    else:
        rcParams["font.sans-serif"] = ["DejaVu Sans"]
    rcParams["axes.unicode_minus"] = False


def clean_metric_values(metric_kind: str, values: Iterable[float]) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    if metric_kind == "time":
        arr[arr < 0] = np.nan
    return arr


def aggregate_annual_stat_series(years: np.ndarray, values: np.ndarray, latitudes: np.ndarray) -> Dict[str, np.ndarray]:
    years = np.asarray(years, dtype=np.int32)
    values = np.asarray(values, dtype=np.float64)
    latitudes = np.asarray(latitudes, dtype=np.float64)
    mean_out = np.full(YEARS.shape, np.nan, dtype=np.float64)
    median_out = np.full(YEARS.shape, np.nan, dtype=np.float64)
    for idx, year in enumerate(YEARS):
        mask = (years == year) & np.isfinite(values)
        if not np.any(mask):
            continue
        vals = values[mask]
        mean_out[idx] = finite_weighted_mean(vals, latitudes[mask])
        median_out[idx] = float(np.nanmedian(vals))
    return {"mean": mean_out, "median": median_out}


def build_dataset_series(item: Item, metric_key: str) -> Dict[str, np.ndarray]:
    metric_info = METRICS[metric_key]
    field_name = metric_info["field_getter"](item)
    with nc.Dataset(item.file_path, "r") as ds:
        years = to_numpy(ds.variables["onset_year"]).astype(np.int32, copy=False)
        lat = to_numpy(ds.variables["lat"])
        values = to_numpy(ds.variables[field_name])
    values = clean_metric_values(metric_info["clean_kind"], values)
    return aggregate_annual_stat_series(years, values, lat)


def plot_metric_stat(metric_key: str, stat_key: str, stat_cn: str) -> str:
    metric_info = METRICS[metric_key]
    fig, axes = plt.subplots(1, 3, figsize=(18, 5), sharex=True)
    for ax, variable in zip(axes, VARIABLE_ORDER):
        subset = [item for item in ITEMS if item.variable == variable]
        for drought_type, soil_layer in SCENARIO_ORDER:
            item = next(
                (
                    x for x in subset
                    if x.drought_type == drought_type and x.soil_layer == soil_layer
                ),
                None,
            )
            if item is None:
                continue
            annual = build_dataset_series(item, metric_key)
            ax.plot(
                YEARS,
                annual[stat_key],
                label=SCENARIO_LABELS[(drought_type, soil_layer)],
                color=SCENARIO_COLORS[(drought_type, soil_layer)],
                linewidth=1.7,
            )
        ax.set_title(variable)
        ax.set_xlabel("Year")
        ax.grid(alpha=0.25, linewidth=0.5)
        ax.set_xlim(YEAR_START, YEAR_END)
    axes[0].set_ylabel(metric_info["ylabel"])
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.04), frameon=False)
    fig.suptitle(f"1982-2021 年{metric_info['title_cn']}{stat_cn}趋势", y=1.08, fontsize=14)
    fig.tight_layout()
    out_name = f"annual_{metric_key}_{stat_key}_trend_1982_2021.png"
    out_path = os.path.join(OUT_DIR, out_name)
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out_path


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    setup_chinese_font()
    outputs: List[str] = []
    for metric_key in METRICS:
        for stat_key, stat_cn in STAT_ORDER:
            outputs.append(plot_metric_stat(metric_key, stat_key, stat_cn))
    for out in outputs:
        print(f"Wrote {out}")


if __name__ == "__main__":
    main()
