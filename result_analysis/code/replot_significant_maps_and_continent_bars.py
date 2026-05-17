#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Replot significance maps with better contrast and coastlines,
and create grouped bar charts by 6 continents (4 scenarios per metric).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Tuple

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import rcParams
from matplotlib.colors import SymLogNorm
import netCDF4 as nc
import numpy as np
import pandas as pd


BASE_DIR = "/home/xulc/flash_drought"
PERF_DIR = os.path.join(BASE_DIR, "process/result_analysis/performance")
MAP_DIR = os.path.join(PERF_DIR, "significant_trend_maps")
os.makedirs(MAP_DIR, exist_ok=True)

METRICS = ["duration", "intensity", "onset_rate", "onset_drop"]
METRIC_CN = {
    "duration": "干旱持续时间",
    "intensity": "干旱烈度",
    "onset_rate": "骤旱发展速率",
    "onset_drop": "骤旱下降幅度",
}
SCENARIO_CN = {
    ("SMs", "flash"): "SMs-骤旱",
    ("SMs", "nonflash"): "SMs-非骤旱",
    ("SMrz", "flash"): "SMrz-骤旱",
    ("SMrz", "nonflash"): "SMrz-非骤旱",
}
SCENARIO_ORDER = [("SMs", "flash"), ("SMs", "nonflash"), ("SMrz", "flash"), ("SMrz", "nonflash")]

CONTINENT_ORDER = ["北美洲", "南美洲", "欧洲", "非洲", "亚洲", "大洋洲"]
SCENARIO_COLORS = {
    "SMs-骤旱": "#1f77b4",
    "SMs-非骤旱": "#ff7f0e",
    "SMrz-骤旱": "#2ca02c",
    "SMrz-非骤旱": "#d62728",
}
MAP_STRIDE = 3  # plotting-only downsampling for speed


@dataclass(frozen=True)
class Scenario:
    soil_layer: str
    drought_type: str
    sig_path: str
    plot_dir: str


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
    return selected if selected is not None else "DejaVu Sans"


def build_scenarios() -> list[Scenario]:
    specs = [
        ("SMs", "flash", os.path.join(BASE_DIR, "gleam/clip_result/SMs_5.3/trend_analysis/flash")),
        ("SMs", "nonflash", os.path.join(BASE_DIR, "gleam/clip_result/SMs_5.3/trend_analysis/nonflash")),
        ("SMrz", "flash", os.path.join(BASE_DIR, "gleam/clip_result/SMrz_5.3/trend_analysis/flash")),
        ("SMrz", "nonflash", os.path.join(BASE_DIR, "gleam/clip_result/SMrz_5.3/trend_analysis/nonflash")),
    ]
    scenarios = []
    for soil, dtype, folder in specs:
        scenarios.append(
            Scenario(
                soil_layer=soil,
                drought_type=dtype,
                sig_path=os.path.join(folder, "pixel_trend_significance_v1.nc"),
                plot_dir=os.path.join(folder, "plots"),
            )
        )
    return scenarios


def _to_float(a) -> np.ndarray:
    if hasattr(a, "filled"):
        a = a.filled(np.nan)
    return np.asarray(a, dtype=np.float64)


def _robust_vmax(arrays: list[np.ndarray], q: float = 92.0) -> float:
    vals = []
    for a in arrays:
        v = np.abs(a[np.isfinite(a)])
        if v.size > 0:
            vals.append(v)
    if not vals:
        return 1.0
    allv = np.concatenate(vals)
    vmax = float(np.nanpercentile(allv, q))
    return vmax if np.isfinite(vmax) and vmax > 0 else 1.0


def plot_metric_panel_with_coast(
    metric: str,
    lon: np.ndarray,
    lat: np.ndarray,
    sig_by_scenario: Dict[Tuple[str, str], np.ndarray],
) -> str:
    out_png = os.path.join(MAP_DIR, f"{metric}_significant_trend_p005_2x2.png")
    vmax = _robust_vmax([sig_by_scenario[k] for k in SCENARIO_ORDER], q=90.0)
    linthresh = max(vmax * 0.08, 1e-8)
    norm = SymLogNorm(linthresh=linthresh, linscale=0.9, vmin=-vmax, vmax=vmax, base=10)

    fig = plt.figure(figsize=(16, 8), dpi=260)
    gs = fig.add_gridspec(2, 3, width_ratios=[1, 1, 0.045], wspace=0.03, hspace=0.08)
    lon_plot = lon[::MAP_STRIDE]
    lat_plot = lat[::MAP_STRIDE]

    im = None
    for i, key in enumerate(SCENARIO_ORDER):
        r, c = divmod(i, 2)
        ax = fig.add_subplot(gs[r, c], projection=ccrs.PlateCarree())
        arr = sig_by_scenario[key][::MAP_STRIDE, ::MAP_STRIDE]
        im = ax.pcolormesh(
            lon_plot,
            lat_plot,
            arr,
            transform=ccrs.PlateCarree(),
            shading="auto",
            cmap="RdBu_r",
            norm=norm,
            rasterized=True,
        )
        ax.add_feature(cfeature.COASTLINE.with_scale("110m"), linewidth=0.5, edgecolor="black")
        ax.set_extent([-180, 180, -60, 85], crs=ccrs.PlateCarree())
        gl = ax.gridlines(
            crs=ccrs.PlateCarree(),
            draw_labels=True,
            linewidth=0.3,
            color="gray",
            alpha=0.35,
            linestyle="--",
        )
        gl.top_labels = False
        gl.right_labels = False
        gl.left_labels = c == 0
        gl.bottom_labels = r == 1
        gl.xlabel_style = {"size": 8}
        gl.ylabel_style = {"size": 8}
        ax.set_title(SCENARIO_CN[key], fontsize=12, pad=4)

    cax = fig.add_subplot(gs[:, 2])
    assert im is not None
    cb = fig.colorbar(im, cax=cax, orientation="vertical")
    cb.set_label("趋势斜率（单位/年，p<0.05）", fontsize=10)
    cb.ax.tick_params(labelsize=8)

    fig.suptitle(f"{METRIC_CN[metric]} 显著趋势图（p<0.05）", fontsize=16, y=0.98)
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)
    return out_png


def plot_continent_grouped_bars(df: pd.DataFrame) -> tuple[str, str]:
    # figure 1: significant mean slope
    out1 = os.path.join(MAP_DIR, "continent_grouped_bars_sig_mean_slope_2x2.png")
    fig1, axes1 = plt.subplots(2, 2, figsize=(18, 10), dpi=300)
    width = 0.18
    x = np.arange(len(CONTINENT_ORDER))

    scale = {"duration": 1.0, "intensity": 1.0, "onset_rate": 1e4, "onset_drop": 1e4}
    unit = {"duration": "单位/年", "intensity": "单位/年", "onset_rate": "×1e-4 /年", "onset_drop": "×1e-4 /年"}

    for ax, metric in zip(axes1.flat, METRICS):
        sub = df[(df["metric"] == metric) & (df["continent_cn"].isin(CONTINENT_ORDER))].copy()
        for j, key in enumerate(SCENARIO_ORDER):
            scen = SCENARIO_CN[key]
            vals = []
            for cont in CONTINENT_ORDER:
                m = sub[(sub["scenario_cn"] == scen) & (sub["continent_cn"] == cont)]
                v = float(m["sig_mean_slope"].iloc[0]) if len(m) > 0 else np.nan
                vals.append(v * scale[metric] if np.isfinite(v) else np.nan)
            ax.bar(x + (j - 1.5) * width, vals, width=width, label=scen, color=SCENARIO_COLORS[scen], alpha=0.9)

        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(CONTINENT_ORDER, fontsize=9)
        ax.set_title(f"{METRIC_CN[metric]}（显著像元平均趋势）", fontsize=11)
        ax.set_ylabel(f"斜率 ({unit[metric]})", fontsize=9)
        ax.grid(axis="y", linestyle="--", alpha=0.3)

    handles, labels = axes1[0, 0].get_legend_handles_labels()
    fig1.legend(handles, labels, loc="upper center", ncol=4, frameon=False, fontsize=10, bbox_to_anchor=(0.5, 0.98))
    fig1.suptitle("六大洲分组柱状图：显著趋势均值（每指标 × 四情景）", fontsize=16, y=0.995)
    fig1.tight_layout(rect=[0.02, 0.03, 0.98, 0.94])
    fig1.savefig(out1, bbox_inches="tight")
    plt.close(fig1)

    # figure 2: significant pixel ratio in valid pixels
    out2 = os.path.join(MAP_DIR, "continent_grouped_bars_sig_ratio_2x2.png")
    fig2, axes2 = plt.subplots(2, 2, figsize=(18, 10), dpi=300)
    for ax, metric in zip(axes2.flat, METRICS):
        sub = df[(df["metric"] == metric) & (df["continent_cn"].isin(CONTINENT_ORDER))].copy()
        for j, key in enumerate(SCENARIO_ORDER):
            scen = SCENARIO_CN[key]
            vals = []
            for cont in CONTINENT_ORDER:
                m = sub[(sub["scenario_cn"] == scen) & (sub["continent_cn"] == cont)]
                v = float(m["sig_ratio_in_valid"].iloc[0]) if len(m) > 0 else np.nan
                vals.append(v * 100.0 if np.isfinite(v) else np.nan)
            ax.bar(x + (j - 1.5) * width, vals, width=width, label=scen, color=SCENARIO_COLORS[scen], alpha=0.9)

        ax.set_xticks(x)
        ax.set_xticklabels(CONTINENT_ORDER, fontsize=9)
        ax.set_title(f"{METRIC_CN[metric]}（显著像元占比）", fontsize=11)
        ax.set_ylabel("占比 (%)", fontsize=9)
        ax.grid(axis="y", linestyle="--", alpha=0.3)

    handles2, labels2 = axes2[0, 0].get_legend_handles_labels()
    fig2.legend(handles2, labels2, loc="upper center", ncol=4, frameon=False, fontsize=10, bbox_to_anchor=(0.5, 0.98))
    fig2.suptitle("六大洲分组柱状图：显著像元占比（每指标 × 四情景）", fontsize=16, y=0.995)
    fig2.tight_layout(rect=[0.02, 0.03, 0.98, 0.94])
    fig2.savefig(out2, bbox_inches="tight")
    plt.close(fig2)

    return out1, out2


def main() -> None:
    font_name = setup_chinese_font()
    print("中文字体:", font_name)

    scenarios = build_scenarios()
    sig_by_metric: Dict[str, Dict[Tuple[str, str], np.ndarray]] = {m: {} for m in METRICS}
    lon = None
    lat = None

    for s in scenarios:
        if not os.path.exists(s.sig_path):
            raise FileNotFoundError(f"缺少显著性文件: {s.sig_path}")
        with nc.Dataset(s.sig_path, "r") as ds:
            if lon is None:
                lon = _to_float(ds.variables["lon"][:]).astype(np.float32)
                lat = _to_float(ds.variables["lat"][:]).astype(np.float32)
            for metric in METRICS:
                arr = _to_float(ds.variables[f"{metric}_sig_slope_p005"][:]).astype(np.float32)
                sig_by_metric[metric][(s.soil_layer, s.drought_type)] = arr

    assert lon is not None and lat is not None
    for metric in METRICS:
        out = plot_metric_panel_with_coast(
            metric=metric,
            lon=lon,
            lat=lat,
            sig_by_scenario=sig_by_metric[metric],
        )
        print("已写出:", out)

    csv_path = os.path.join(PERF_DIR, "continent_significant_trend_stats.csv")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"缺少统计表: {csv_path}")
    df = pd.read_csv(csv_path)
    out1, out2 = plot_continent_grouped_bars(df)
    print("已写出:", out1)
    print("已写出:", out2)


if __name__ == "__main__":
    main()
