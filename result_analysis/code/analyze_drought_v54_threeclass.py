#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Dict, Tuple

import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import rcParams
import netCDF4 as nc
import numpy as np
import pandas as pd


BASE_DIR = "/home/xulc/flash_drought"
PROCESS2_DIR = os.path.join(BASE_DIR, "process/process2")
if PROCESS2_DIR not in sys.path:
    sys.path.insert(0, PROCESS2_DIR)

from drought_event_v54_utils import EVENT_TYPE_LABELS_CN, EVENT_TYPE_ORDER, MAIN_EVENT_TYPES


OUT_DIR = os.path.join(BASE_DIR, "process/result_analysis/performance/v54_threeclass")
SUMMARY_CSV = os.path.join(OUT_DIR, "drought_v54_threeclass_summary.csv")
SUMMARY_MD = os.path.join(OUT_DIR, "drought_v54_threeclass_summary.md")
FIG_PNG = os.path.join(OUT_DIR, "drought_v54_threeclass_metrics.png")

LAT_CHUNK = 120
SOIL_ORDER = ["SMs", "SMrz"]
SOIL_LABELS = {"SMs": "表层土壤", "SMrz": "根系土壤"}
SOIL_COLORS = {"SMs": "#bf5b17", "SMrz": "#2166ac"}
EVENT_TYPE_SORT = {event_type: idx for idx, event_type in enumerate(EVENT_TYPE_ORDER)}


@dataclass(frozen=True)
class Scenario:
    soil_layer: str
    event_type: str
    event_path: str


def setup_chinese_font() -> str:
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
                fm.fontManager.addfont(fp)
                selected = fm.FontProperties(fname=fp).get_name()
                break
    rcParams["font.sans-serif"] = [selected, "DejaVu Sans"] if selected else ["DejaVu Sans"]
    rcParams["axes.unicode_minus"] = False
    return selected if selected else "DejaVu Sans"


def scenario_label(soil_layer: str, event_type: str) -> str:
    return f"{soil_layer}-{EVENT_TYPE_LABELS_CN[event_type]}"


def build_scenarios() -> list[Scenario]:
    scenarios: list[Scenario] = []
    for soil_layer in SOIL_ORDER:
        result_dir = os.path.join(BASE_DIR, "gleam/result", f"{soil_layer}_result_v5.4")
        if soil_layer == "SMs":
            result_dir = os.path.join(BASE_DIR, "gleam/result", "SMs_result_v5.4_0p25deg")
        elif soil_layer == "SMrz":
            result_dir = os.path.join(BASE_DIR, "gleam/result", "SMrz_result_v5.4_0p25deg")
        for event_type in EVENT_TYPE_ORDER:
            scenarios.append(
                Scenario(
                    soil_layer=soil_layer,
                    event_type=event_type,
                    event_path=os.path.join(result_dir, f"{event_type}_drought_events_v5.4.nc"),
                )
            )
    return scenarios


def aggregate_event_file(path: str) -> Dict[str, float]:
    event_count_total = 0
    duration_sum = 0.0
    intensity_sum = 0.0

    with nc.Dataset(path, "r") as ds:
        nlat = len(ds.dimensions["lat"])
        max_events = len(ds.dimensions["max_events"])
        event_idx = np.arange(max_events, dtype=np.int16)[:, None, None]
        count_var = ds.variables["event_count"]
        duration_var = ds.variables["duration"]
        intensity_var = ds.variables["intensity"]

        for lat0 in range(0, nlat, LAT_CHUNK):
            lat1 = min(lat0 + LAT_CHUNK, nlat)
            counts = count_var[lat0:lat1, :]
            if isinstance(counts, np.ma.MaskedArray):
                counts = counts.filled(0)
            counts = np.asarray(counts, dtype=np.int16)
            counts = np.where(counts < 0, 0, counts)
            if not np.any(counts > 0):
                continue

            valid_event_mask = event_idx < counts[None, :, :]

            duration = duration_var[:, lat0:lat1, :]
            if isinstance(duration, np.ma.MaskedArray):
                duration = duration.filled(-1)
            duration = np.asarray(duration, dtype=np.int16)

            intensity = intensity_var[:, lat0:lat1, :]
            if isinstance(intensity, np.ma.MaskedArray):
                intensity = intensity.filled(np.nan)
            intensity = np.asarray(intensity, dtype=np.float64)
            intensity[intensity <= -9999] = np.nan

            event_count_total += int(np.sum(counts, dtype=np.int64))

            duration_vals = duration[valid_event_mask]
            if duration_vals.size:
                duration_sum += float(np.sum(duration_vals, dtype=np.float64))

            intensity_vals = intensity[valid_event_mask]
            if intensity_vals.size:
                intensity_sum += float(np.nansum(intensity_vals))

    return {
        "count": int(event_count_total),
        "duration_sum": float(duration_sum),
        "intensity_sum": float(intensity_sum),
    }


def build_summary_dataframe(metrics: Dict[Tuple[str, str], Dict[str, float]]) -> pd.DataFrame:
    rows = []
    soil_layers = [soil_layer for soil_layer in SOIL_ORDER if any((soil_layer, event_type) in metrics for event_type in EVENT_TYPE_ORDER)]
    for soil_layer in soil_layers:
        total_main = sum(metrics.get((soil_layer, event_type), {}).get("count", 0) for event_type in MAIN_EVENT_TYPES)
        total_all = sum(metrics.get((soil_layer, event_type), {}).get("count", 0) for event_type in EVENT_TYPE_ORDER)
        for event_type in EVENT_TYPE_ORDER:
            values = metrics.get((soil_layer, event_type), {"count": 0, "duration_sum": 0.0, "intensity_sum": 0.0})
            count = int(values["count"])
            rows.append(
                {
                    "soil_layer": soil_layer,
                    "soil_layer_cn": SOIL_LABELS[soil_layer],
                    "event_type": event_type,
                    "event_type_cn": EVENT_TYPE_LABELS_CN[event_type],
                    "scenario_cn": scenario_label(soil_layer, event_type),
                    "event_count": count,
                    "share_of_main_classes": (count / total_main) if (event_type in MAIN_EVENT_TYPES and total_main > 0) else np.nan,
                    "share_of_all_classes": (count / total_all) if total_all > 0 else np.nan,
                    "duration_mean": (values["duration_sum"] / count) if count > 0 else np.nan,
                    "intensity_mean": (values["intensity_sum"] / count) if count > 0 else np.nan,
                    "is_main_class": event_type in MAIN_EVENT_TYPES,
                }
            )
    return pd.DataFrame(rows)


def sort_summary_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["soil_sort"] = out["soil_layer"].map({soil: idx for idx, soil in enumerate(SOIL_ORDER)})
    out["event_sort"] = out["event_type"].map(EVENT_TYPE_SORT)
    out = out.sort_values(["soil_sort", "event_sort", "scenario_cn"]).reset_index(drop=True)
    return out.drop(columns=["soil_sort", "event_sort"])


def plot_main_class_metrics(df: pd.DataFrame) -> str:
    main = df[df["is_main_class"]].copy()
    main["event_type_cn"] = pd.Categorical(
        main["event_type_cn"],
        categories=[EVENT_TYPE_LABELS_CN[event_type] for event_type in MAIN_EVENT_TYPES],
        ordered=True,
    )
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), dpi=320)
    fig.patch.set_facecolor("white")
    metric_specs = [
        ("share_of_main_classes", "全球占比", "占比"),
        ("duration_mean", "平均持续时间", "天"),
        ("intensity_mean", "平均烈度", "烈度"),
    ]
    x = np.arange(len(MAIN_EVENT_TYPES))
    width = 0.34
    for ax, (metric, title, ylabel) in zip(axes, metric_specs):
        ax.set_facecolor("#fbf8f3")
        for idx, soil_layer in enumerate(SOIL_ORDER):
            subset = main[main["soil_layer"] == soil_layer].copy()
            subset["event_sort"] = subset["event_type"].map({etype: i for i, etype in enumerate(MAIN_EVENT_TYPES)})
            subset = subset.sort_values("event_sort")
            values = subset[metric].to_numpy(dtype=np.float64)
            ax.bar(
                x + (idx - 0.5) * width,
                values,
                width=width,
                color=SOIL_COLORS[soil_layer],
                label=SOIL_LABELS[soil_layer],
                edgecolor="black",
                linewidth=0.5,
            )
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels([EVENT_TYPE_LABELS_CN[event_type] for event_type in MAIN_EVENT_TYPES], fontsize=10)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.35)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.02))
    fig.suptitle("SMs 与 SMrz 三类爆发时间干旱特征对比", fontsize=16, fontweight="bold", y=1.06)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(FIG_PNG, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return FIG_PNG


def write_summary(df: pd.DataFrame) -> None:
    lines = [
        "# v5.4 三分类干旱全球统计",
        "",
        "本统计基于 `v5.4` 事件文件，将事件划分为 `1-4天`、`5-20天`、`>20天` 三类主事件，并将 `dry_to_drier` 作为辅助类别单列。",
        "",
    ]
    for soil_layer in SOIL_ORDER:
        lines.append(f"## {SOIL_LABELS[soil_layer]}")
        subset = df[df["soil_layer"] == soil_layer]
        for event_type in EVENT_TYPE_ORDER:
            row = subset[subset["event_type"] == event_type].iloc[0]
            share_text = (
                f"{row['share_of_main_classes'] * 100:.2f}%"
                if pd.notna(row["share_of_main_classes"])
                else "不纳入三类主事件占比"
            )
            lines.append(
                f"- {row['event_type_cn']}：事件数 {int(row['event_count'])}，主事件占比 {share_text}，"
                f"平均持续时间 {row['duration_mean']:.2f} 天，平均烈度 {row['intensity_mean']:.3f}。"
            )
        lines.append("")

    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    font_name = setup_chinese_font()
    print(f"中文字体: {font_name}")

    scenarios = build_scenarios()
    metrics: Dict[Tuple[str, str], Dict[str, float]] = {}
    for scenario in scenarios:
        if not os.path.exists(scenario.event_path):
            raise FileNotFoundError(f"缺少文件: {scenario.event_path}")
        metrics[(scenario.soil_layer, scenario.event_type)] = aggregate_event_file(scenario.event_path)

    summary_df = build_summary_dataframe(metrics)
    summary_df = sort_summary_dataframe(summary_df)
    summary_df.to_csv(SUMMARY_CSV, index=False, encoding="utf-8-sig")
    plot_main_class_metrics(summary_df)
    write_summary(summary_df)

    print(f"已写出: {SUMMARY_CSV}")
    print(f"已写出: {FIG_PNG}")
    print(f"已写出: {SUMMARY_MD}")


if __name__ == "__main__":
    main()
