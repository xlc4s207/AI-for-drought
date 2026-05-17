#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Tuple

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import rcParams
import netCDF4 as nc
import numpy as np


BASE_DIR = "/home/xulc/flash_drought"
PERF_DIR = os.path.join(BASE_DIR, "process/result_analysis/performance")
OUT_DIR = os.path.join(PERF_DIR, "distribution_maps")

SCENARIO_CN = {
    ("SMs", "flash"): "SMs-骤旱",
    ("SMs", "nonflash"): "SMs-非骤旱",
    ("SMrz", "flash"): "SMrz-骤旱",
    ("SMrz", "nonflash"): "SMrz-非骤旱",
}
SCENARIO_ORDER = [("SMs", "flash"), ("SMs", "nonflash"), ("SMrz", "flash"), ("SMrz", "nonflash")]
MAP_STRIDE = 3


@dataclass(frozen=True)
class MetricSpec:
    source_kind: str
    source_var: str
    title_cn: str
    colorbar_cn: str
    cmap: str
    out_name: str


METRIC_SPECS: Dict[str, MetricSpec] = {
    "duration": MetricSpec("event_trend", "duration_mean", "干旱持续时间空间分布", "持续时间", "YlOrRd", "duration_distribution_2x2.png"),
    "intensity": MetricSpec("event_trend", "intensity_mean", "干旱烈度空间分布", "烈度", "OrRd", "intensity_distribution_2x2.png"),
    "onset_rate": MetricSpec("event_trend", "onset_rate_mean", "干旱发生速率空间分布", "发生速率", "YlGnBu", "onset_rate_distribution_2x2.png"),
    "frequency": MetricSpec("frequency_trend", "mean_annual_frequency", "干旱发生频次空间分布", "平均年发生频次", "PuBuGn", "frequency_distribution_2x2.png"),
}


@dataclass(frozen=True)
class Scenario:
    soil_layer: str
    drought_type: str
    event_trend_path: str
    frequency_trend_path: str


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

    rcParams["font.sans-serif"] = [selected, "DejaVu Sans"] if selected else ["DejaVu Sans"]
    rcParams["axes.unicode_minus"] = False
    return selected if selected else "DejaVu Sans"


def build_scenarios() -> list[Scenario]:
    return [
        Scenario(
            soil_layer="SMs",
            drought_type="flash",
            event_trend_path=os.path.join(BASE_DIR, "gleam/clip_result/SMs_5.3/trend_analysis/flash/pixel_trend_metrics_v1.nc"),
            frequency_trend_path=os.path.join(PERF_DIR, "frequency_trend_maps/drought_frequency_trend_SMs_flash_1980_2024.nc"),
        ),
        Scenario(
            soil_layer="SMs",
            drought_type="nonflash",
            event_trend_path=os.path.join(BASE_DIR, "gleam/clip_result/SMs_5.3/trend_analysis/nonflash/pixel_trend_metrics_v1.nc"),
            frequency_trend_path=os.path.join(PERF_DIR, "frequency_trend_maps/drought_frequency_trend_SMs_nonflash_1980_2024.nc"),
        ),
        Scenario(
            soil_layer="SMrz",
            drought_type="flash",
            event_trend_path=os.path.join(BASE_DIR, "gleam/clip_result/SMrz_5.3/trend_analysis/flash/pixel_trend_metrics_v1.nc"),
            frequency_trend_path=os.path.join(PERF_DIR, "frequency_trend_maps/drought_frequency_trend_SMrz_flash_1980_2024.nc"),
        ),
        Scenario(
            soil_layer="SMrz",
            drought_type="nonflash",
            event_trend_path=os.path.join(BASE_DIR, "gleam/clip_result/SMrz_5.3/trend_analysis/nonflash/pixel_trend_metrics_v1.nc"),
            frequency_trend_path=os.path.join(PERF_DIR, "frequency_trend_maps/drought_frequency_trend_SMrz_nonflash_1980_2024.nc"),
        ),
    ]


def _to_float(a) -> np.ndarray:
    if hasattr(a, "filled"):
        a = a.filled(np.nan)
    return np.asarray(a, dtype=np.float64)


def _robust_range(arrays: list[np.ndarray], q_low: float = 2.0, q_high: float = 98.0) -> Tuple[float, float]:
    vals = [a[np.isfinite(a)] for a in arrays if np.any(np.isfinite(a))]
    if not vals:
        return 0.0, 1.0
    allv = np.concatenate(vals)
    vmin = float(np.nanpercentile(allv, q_low))
    vmax = float(np.nanpercentile(allv, q_high))
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
        vmin = float(np.nanmin(allv))
        vmax = float(np.nanmax(allv))
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
        return 0.0, 1.0
    return vmin, vmax


def _read_metric_array(scenario: Scenario, metric_name: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    spec = METRIC_SPECS[metric_name]
    path = scenario.event_trend_path if spec.source_kind == "event_trend" else scenario.frequency_trend_path
    with nc.Dataset(path, "r") as ds:
        lon = _to_float(ds.variables["lon"][:]).astype(np.float32)
        lat = _to_float(ds.variables["lat"][:]).astype(np.float32)
        arr = _to_float(ds.variables[spec.source_var][:]).astype(np.float32)
    return lon, lat, arr


def plot_metric_distribution(metric_name: str, scenarios: list[Scenario]) -> str:
    spec = METRIC_SPECS[metric_name]
    os.makedirs(OUT_DIR, exist_ok=True)

    arrays = []
    lon = None
    lat = None
    for scenario in scenarios:
        lon, lat, arr = _read_metric_array(scenario, metric_name)
        arrays.append(arr)

    assert lon is not None and lat is not None
    vmin, vmax = _robust_range(arrays)

    fig = plt.figure(figsize=(16, 8), dpi=260)
    gs = fig.add_gridspec(2, 3, width_ratios=[1, 1, 0.045], wspace=0.03, hspace=0.08)
    lon_plot = lon[::MAP_STRIDE]
    lat_plot = lat[::MAP_STRIDE]

    im = None
    for i, scenario in enumerate(scenarios):
        r, c = divmod(i, 2)
        ax = fig.add_subplot(gs[r, c], projection=ccrs.PlateCarree())
        arr = arrays[i][::MAP_STRIDE, ::MAP_STRIDE]
        im = ax.pcolormesh(
            lon_plot,
            lat_plot,
            arr,
            transform=ccrs.PlateCarree(),
            shading="auto",
            cmap=spec.cmap,
            vmin=vmin,
            vmax=vmax,
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
        ax.set_title(SCENARIO_CN[(scenario.soil_layer, scenario.drought_type)], fontsize=12, pad=4)

    cax = fig.add_subplot(gs[:, 2])
    assert im is not None
    cb = fig.colorbar(im, cax=cax, orientation="vertical")
    cb.set_label(spec.colorbar_cn, fontsize=10)
    cb.ax.tick_params(labelsize=8)

    fig.suptitle(f"{spec.title_cn}（1980-2024 平均）", fontsize=16, y=0.98)
    out_png = os.path.join(OUT_DIR, spec.out_name)
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)
    return out_png


def main() -> None:
    font_name = setup_chinese_font()
    print(f"中文字体: {font_name}")
    scenarios = build_scenarios()
    for scenario in scenarios:
        if not os.path.exists(scenario.event_trend_path):
            raise FileNotFoundError(f"缺少文件: {scenario.event_trend_path}")
        if not os.path.exists(scenario.frequency_trend_path):
            raise FileNotFoundError(f"缺少文件: {scenario.frequency_trend_path}")

    for metric_name in METRIC_SPECS:
        out = plot_metric_distribution(metric_name, scenarios)
        print(f"已写出: {out}")


if __name__ == "__main__":
    main()
