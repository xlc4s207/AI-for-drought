#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import rcParams
import netCDF4 as nc
import numpy as np


BASE_DIR = Path("/home/xulc/flash_drought/era5/result")
OUT_DIR = Path("/home/xulc/flash_drought/gleam/result/tmp_plot")

SOIL_ORDER = ["ERA5L_swvl1", "ERA5L_root"]
SOIL_CN = {"ERA5L_swvl1": "ERA5表层土壤", "ERA5L_root": "ERA5根系土壤"}

EVENT_SPECS = [
    ("rapid_1to4", "1-4天", "YlOrRd"),
    ("flash_5to20", "5-20天", "OrRd"),
    ("flash_lt20", "<20天", "Reds"),
    ("slow_gt20", ">20天", "PuBuGn"),
]


@dataclass(frozen=True)
class ScenarioSpec:
    soil: str
    event_key: str
    event_cn: str
    cmap: str
    nc_path: Path


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
            if Path(fp).exists():
                fm.fontManager.addfont(fp)
                selected = fm.FontProperties(fname=fp).get_name()
                break
    rcParams["font.sans-serif"] = [selected, "DejaVu Sans"] if selected else ["DejaVu Sans"]
    rcParams["axes.unicode_minus"] = False
    return selected if selected else "DejaVu Sans"


def build_specs() -> list[ScenarioSpec]:
    specs: list[ScenarioSpec] = []
    for soil in SOIL_ORDER:
        d = BASE_DIR / f"{soil}_result_v5.4_0p25deg"
        for event_key, event_cn, cmap in EVENT_SPECS:
            specs.append(
                ScenarioSpec(
                    soil=soil,
                    event_key=event_key,
                    event_cn=event_cn,
                    cmap=cmap,
                    nc_path=d / f"{event_key}_drought_events_v5.4.nc",
                )
            )
    return specs


def event_count_to_plot_array(event_count: np.ndarray) -> np.ndarray:
    arr = np.asarray(event_count, dtype=np.float32)
    arr = np.where(arr <= 0, np.nan, arr)
    return arr


def read_event_count_map(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with nc.Dataset(path, "r") as ds:
        lat = np.asarray(ds.variables["lat"][:], dtype=np.float32)
        lon = np.asarray(ds.variables["lon"][:], dtype=np.float32)
        count = ds.variables["event_count"][:]
        if hasattr(count, "filled"):
            count = count.filled(-1)
        count = event_count_to_plot_array(count)
    return lon, lat, count


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


def choose_imshow_origin(lat: np.ndarray) -> str:
    lat = np.asarray(lat, dtype=np.float32)
    if lat.ndim != 1 or lat.size < 2:
        return "upper"
    return "lower" if float(lat[1]) > float(lat[0]) else "upper"


def plot_maps(lon: np.ndarray, lat: np.ndarray, arrays: dict[tuple[str, str], np.ndarray]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(21, 8.8), dpi=320)
    gs = fig.add_gridspec(3, 4, height_ratios=[1, 1, 0.08], hspace=0.08, wspace=0.04)

    per_event_limits = {}
    for event_key, _, _ in EVENT_SPECS:
        mats = [arrays[(soil, event_key)] for soil in SOIL_ORDER]
        per_event_limits[event_key] = robust_limits(mats)

    lon_min, lon_max = float(np.min(lon)), float(np.max(lon))
    lat_min, lat_max = float(np.min(lat)), float(np.max(lat))
    origin = choose_imshow_origin(lat)

    for row, soil in enumerate(SOIL_ORDER):
        for col, (event_key, event_cn, cmap_name) in enumerate(EVENT_SPECS):
            ax = fig.add_subplot(gs[row, col], projection=ccrs.PlateCarree())
            arr = arrays[(soil, event_key)]
            vmin, vmax = per_event_limits[event_key]
            cmap = plt.get_cmap(cmap_name).copy()
            cmap.set_bad((1, 1, 1, 0))

            im = ax.imshow(
                arr,
                extent=[lon_min, lon_max, lat_min, lat_max],
                origin=origin,
                transform=ccrs.PlateCarree(),
                cmap=cmap,
                vmin=vmin,
                vmax=vmax,
                interpolation="nearest",
                zorder=1,
            )
            iy, ix = np.where(np.isfinite(arr))
            if 0 < iy.size <= 5000:
                im = ax.scatter(
                    lon[ix],
                    lat[iy],
                    c=arr[iy, ix],
                    s=8,
                    marker="s",
                    cmap=cmap,
                    vmin=vmin,
                    vmax=vmax,
                    linewidths=0.0,
                    transform=ccrs.PlateCarree(),
                    zorder=2,
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

    fig.suptitle("ERA5原始结果 v5.4 干旱频次分布图（未掩膜）", fontsize=18, y=0.98)
    out_path = OUT_DIR / "era5_v54_raw_frequency_maps_2x4.png"
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def main() -> None:
    font_name = setup_chinese_font()
    print(f"中文字体: {font_name}")
    specs = build_specs()
    arrays: dict[tuple[str, str], np.ndarray] = {}
    lon = None
    lat = None

    for spec in specs:
        if not spec.nc_path.exists():
            raise FileNotFoundError(f"缺少文件: {spec.nc_path}")
        lon, lat, arr = read_event_count_map(spec.nc_path)
        arrays[(spec.soil, spec.event_key)] = arr

    assert lon is not None and lat is not None
    out_path = plot_maps(lon, lat, arrays)
    print(f"已写出: {out_path}")


if __name__ == "__main__":
    main()

