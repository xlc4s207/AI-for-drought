#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import rcParams
import numpy as np
import rasterio


BASE_DIR = Path("/home/xulc/flash_drought/gleam/result")
OUT_DIR = BASE_DIR / "tmp_plot"

SOIL_ORDER = ["SMs", "SMrz"]
SOIL_CN = {"SMs": "表层土壤", "SMrz": "根系土壤"}

EVENT_SPECS = [
    ("rapid_1to4", "1-4天", "YlOrRd"),
    ("flash_5to20", "5-20天", "OrRd"),
    ("slow_gt20", ">20天", "PuBuGn"),
]


@dataclass(frozen=True)
class RasterSpec:
    soil: str
    event_key: str
    event_cn: str
    cmap: str
    tif_path: Path


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
        for fp in [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJKSC-Regular.otf",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        ]:
            if os.path.exists(fp):
                fm.fontManager.addfont(fp)
                selected = fm.FontProperties(fname=fp).get_name()
                break

    rcParams["font.sans-serif"] = [selected, "DejaVu Sans"] if selected else ["DejaVu Sans"]
    rcParams["axes.unicode_minus"] = False
    return selected if selected else "DejaVu Sans"


def build_specs() -> list[RasterSpec]:
    specs: list[RasterSpec] = []
    for soil in SOIL_ORDER:
        result_dir = BASE_DIR / f"{soil}_result_v5.4_0p25deg"
        for event_key, event_cn, cmap in EVENT_SPECS:
            specs.append(
                RasterSpec(
                    soil=soil,
                    event_key=event_key,
                    event_cn=event_cn,
                    cmap=cmap,
                    tif_path=result_dir / f"{event_key}_drought_frequency_1980_2024_v5.4.tif",
                )
            )
    return specs


def read_tif(path: Path) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    with rasterio.open(path) as src:
        arr = src.read(1).astype(np.float32)
        nodata = src.nodata
        if nodata is not None:
            arr = np.where(arr == nodata, np.nan, arr)
        arr = np.where(arr <= 0, np.nan, arr)
        bounds = src.bounds
    return arr, (bounds.left, bounds.right, bounds.bottom, bounds.top)


def robust_limits(arrays: list[np.ndarray]) -> tuple[float, float]:
    valid = [a[np.isfinite(a)] for a in arrays if np.any(np.isfinite(a))]
    if not valid:
        return 0.0, 1.0
    vals = np.concatenate(valid)
    vmin = float(np.nanpercentile(vals, 2))
    vmax = float(np.nanpercentile(vals, 98))
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin >= vmax:
        vmin = float(np.nanmin(vals))
        vmax = float(np.nanmax(vals))
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin >= vmax:
        return 0.0, 1.0
    return vmin, vmax


def plot_single(spec: RasterSpec, arr: np.ndarray, extent: tuple[float, float, float, float], vmin: float, vmax: float) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(11, 5.4), dpi=300)
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
    ax.set_facecolor("#f7f4ef")
    cmap = plt.get_cmap(spec.cmap).copy()
    cmap.set_bad((1, 1, 1, 0))
    im = ax.imshow(
        arr,
        extent=extent,
        origin="upper",
        transform=ccrs.PlateCarree(),
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        interpolation="nearest",
        zorder=1,
    )
    ax.add_feature(cfeature.LAND.with_scale("110m"), facecolor="#f6f1e8", edgecolor="none", zorder=-2)
    ax.add_feature(cfeature.OCEAN.with_scale("110m"), facecolor="#f2f6fb", edgecolor="none", zorder=-3)
    ax.add_feature(cfeature.COASTLINE.with_scale("110m"), linewidth=0.55, edgecolor="black", zorder=3)
    ax.set_extent([-180, 180, -60, 85], crs=ccrs.PlateCarree())
    gl = ax.gridlines(draw_labels=True, linewidth=0.3, color="gray", alpha=0.3, linestyle="--")
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {"size": 8}
    gl.ylabel_style = {"size": 8}
    ax.set_title(f"{SOIL_CN[spec.soil]} {spec.event_cn}干旱频次（1980-2024）", fontsize=14, pad=10)
    cb = fig.colorbar(im, ax=ax, orientation="horizontal", pad=0.06, fraction=0.05)
    cb.set_label("1980-2024累计发生频次", fontsize=10)
    cb.ax.tick_params(labelsize=8)
    out_path = OUT_DIR / f"{spec.soil}_{spec.event_key}_frequency_map.png"
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def plot_overview(specs: list[RasterSpec], arrays: dict[tuple[str, str], np.ndarray], extents: dict[tuple[str, str], tuple[float, float, float, float]]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(17, 8.6), dpi=320)
    gs = fig.add_gridspec(3, 3, height_ratios=[1, 1, 0.07], hspace=0.08, wspace=0.04)

    per_event_limits = {}
    for event_key, _, _ in EVENT_SPECS:
        mats = [arrays[(soil, event_key)] for soil in SOIL_ORDER]
        per_event_limits[event_key] = robust_limits(mats)

    for row, soil in enumerate(SOIL_ORDER):
        for col, (event_key, event_cn, cmap) in enumerate(EVENT_SPECS):
            ax = fig.add_subplot(gs[row, col], projection=ccrs.PlateCarree())
            arr = arrays[(soil, event_key)]
            extent = extents[(soil, event_key)]
            vmin, vmax = per_event_limits[event_key]
            cmap_obj = plt.get_cmap(cmap).copy()
            cmap_obj.set_bad((1, 1, 1, 0))
            im = ax.imshow(
                arr,
                extent=extent,
                origin="upper",
                transform=ccrs.PlateCarree(),
                cmap=cmap_obj,
                vmin=vmin,
                vmax=vmax,
                interpolation="nearest",
                zorder=1,
            )
            ax.set_facecolor("#f7f4ef")
            ax.add_feature(cfeature.LAND.with_scale("110m"), facecolor="#f6f1e8", edgecolor="none", zorder=-2)
            ax.add_feature(cfeature.OCEAN.with_scale("110m"), facecolor="#f2f6fb", edgecolor="none", zorder=-3)
            ax.add_feature(cfeature.COASTLINE.with_scale("110m"), linewidth=0.5, edgecolor="black", zorder=3)
            ax.set_extent([-180, 180, -60, 85], crs=ccrs.PlateCarree())
            gl = ax.gridlines(draw_labels=True, linewidth=0.25, color="gray", alpha=0.3, linestyle="--")
            gl.top_labels = False
            gl.right_labels = False
            gl.left_labels = col == 0
            gl.bottom_labels = row == 1
            gl.xlabel_style = {"size": 8}
            gl.ylabel_style = {"size": 8}
            ax.set_title(f"{SOIL_CN[soil]} {event_cn}", fontsize=12, pad=5)

            if row == 1:
                cax = fig.add_subplot(gs[2, col])
                cb = fig.colorbar(im, cax=cax, orientation="horizontal")
                cb.set_label(f"{event_cn}干旱累计频次", fontsize=9)
                cb.ax.tick_params(labelsize=8)

    fig.suptitle("0.25°土壤层不同起始时间类别干旱频次分布图", fontsize=18, y=0.98)
    out_path = OUT_DIR / "v54_frequency_maps_2x3.png"
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def main() -> None:
    font_name = setup_chinese_font()
    print(f"中文字体: {font_name}")
    specs = build_specs()
    arrays: dict[tuple[str, str], np.ndarray] = {}
    extents: dict[tuple[str, str], tuple[float, float, float, float]] = {}

    for spec in specs:
        if not spec.tif_path.exists():
            raise FileNotFoundError(f"缺少文件: {spec.tif_path}")
        arr, extent = read_tif(spec.tif_path)
        arrays[(spec.soil, spec.event_key)] = arr
        extents[(spec.soil, spec.event_key)] = extent

    for event_key, _, _ in EVENT_SPECS:
        mats = [arrays[(soil, event_key)] for soil in SOIL_ORDER]
        vmin, vmax = robust_limits(mats)
        for soil in SOIL_ORDER:
            spec = next(s for s in specs if s.soil == soil and s.event_key == event_key)
            out = plot_single(spec, arrays[(soil, event_key)], extents[(soil, event_key)], vmin, vmax)
            print(f"已写出: {out}")

    overview = plot_overview(specs, arrays, extents)
    print(f"已写出: {overview}")


if __name__ == "__main__":
    main()
