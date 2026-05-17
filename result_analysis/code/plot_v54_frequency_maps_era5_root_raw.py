#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import rcParams
import netCDF4 as nc
import numpy as np

BASE_DIR = Path('/home/xulc/flash_drought/era5/result/ERA5L_root_result_v5.4_0p25deg')
OUT_PATH = Path('/home/xulc/flash_drought/gleam/result/tmp_plot/era5_root_v54_raw_frequency_maps_1x4.png')

EVENT_SPECS = [
    ('rapid_1to4', '1-4天', 'YlOrRd'),
    ('flash_5to20', '5-20天', 'OrRd'),
    ('flash_lt20', '<20天', 'Reds'),
    ('slow_gt20', '>20天', 'PuBuGn'),
]


def setup_chinese_font() -> str:
    candidates = [
        'Noto Sans CJK SC', 'Noto Sans CJK', 'Source Han Sans SC', 'Source Han Sans CN',
        'WenQuanYi Micro Hei', 'WenQuanYi Zen Hei', 'Microsoft YaHei', 'SimHei',
        'PingFang SC', 'Arial Unicode MS',
    ]
    installed = {f.name for f in fm.fontManager.ttflist}
    selected = None
    for name in candidates:
        if name in installed:
            selected = name
            break
    if selected is None:
        for fp in [
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/opentype/noto/NotoSansCJKSC-Regular.otf',
            '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
            '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
        ]:
            if Path(fp).exists():
                fm.fontManager.addfont(fp)
                selected = fm.FontProperties(fname=fp).get_name()
                break

    rcParams['font.sans-serif'] = [selected, 'DejaVu Sans'] if selected else ['DejaVu Sans']
    rcParams['axes.unicode_minus'] = False
    return selected if selected else 'DejaVu Sans'


def read_count(path: Path):
    with nc.Dataset(path, 'r') as ds:
        lat = np.asarray(ds.variables['lat'][:], dtype=np.float32)
        lon = np.asarray(ds.variables['lon'][:], dtype=np.float32)
        arr = ds.variables['event_count'][:]
        if hasattr(arr, 'filled'):
            arr = arr.filled(-1)
        arr = np.asarray(arr, dtype=np.float32)
    arr = np.where(arr <= 0, np.nan, arr)
    return lon, lat, arr


def robust_limits(arr: np.ndarray):
    v = arr[np.isfinite(arr)]
    if v.size == 0:
        return 0.0, 1.0
    vmin = float(np.nanpercentile(v, 2))
    vmax = float(np.nanpercentile(v, 98))
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin >= vmax:
        vmin = float(np.nanmin(v))
        vmax = float(np.nanmax(v))
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin >= vmax:
        return 0.0, 1.0
    return vmin, vmax


def choose_origin(lat: np.ndarray) -> str:
    if lat.ndim != 1 or lat.size < 2:
        return 'upper'
    return 'lower' if float(lat[1]) > float(lat[0]) else 'upper'


def main():
    font_name = setup_chinese_font()
    print(f'中文字体: {font_name}')

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    arrays = {}
    lon = lat = None
    for key, _, _ in EVENT_SPECS:
        p = BASE_DIR / f'{key}_drought_events_v5.4.nc'
        if not p.exists():
            raise FileNotFoundError(f'缺少文件: {p}')
        lon, lat, arr = read_count(p)
        arrays[key] = arr

    assert lon is not None and lat is not None

    fig = plt.figure(figsize=(20, 5.6), dpi=320)
    gs = fig.add_gridspec(2, 4, height_ratios=[1, 0.08], hspace=0.08, wspace=0.04)

    lon_min, lon_max = float(np.min(lon)), float(np.max(lon))
    lat_min, lat_max = float(np.min(lat)), float(np.max(lat))
    origin = choose_origin(lat)

    for col, (key, label_cn, cmap_name) in enumerate(EVENT_SPECS):
        ax = fig.add_subplot(gs[0, col], projection=ccrs.PlateCarree())
        arr = arrays[key]
        vmin, vmax = robust_limits(arr)
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
            interpolation='nearest',
            zorder=1,
        )

        ax.set_facecolor('#f7f4ef')
        ax.add_feature(cfeature.LAND.with_scale('110m'), facecolor='#f6f1e8', edgecolor='none', zorder=-2)
        ax.add_feature(cfeature.OCEAN.with_scale('110m'), facecolor='#f2f6fb', edgecolor='none', zorder=-3)
        ax.add_feature(cfeature.COASTLINE.with_scale('110m'), linewidth=0.5, edgecolor='black', zorder=3)
        ax.set_extent([-180, 180, -60, 85], crs=ccrs.PlateCarree())

        gl = ax.gridlines(draw_labels=True, linewidth=0.25, color='gray', alpha=0.3, linestyle='--')
        gl.top_labels = False
        gl.right_labels = False
        gl.left_labels = col == 0
        gl.bottom_labels = True
        gl.xlabel_style = {'size': 8}
        gl.ylabel_style = {'size': 8}

        ax.set_title(f'ERA5根系土壤 {label_cn}', fontsize=13, pad=5)

        cax = fig.add_subplot(gs[1, col])
        cb = fig.colorbar(im, cax=cax, orientation='horizontal')
        cb.set_label(f'{label_cn}干旱累计频次', fontsize=9)
        cb.ax.tick_params(labelsize=8)

    fig.suptitle('ERA5根系土壤 v5.4 干旱频次分布图（未掩膜）', fontsize=18, y=0.98)
    fig.savefig(OUT_PATH, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f'已写出: {OUT_PATH}')


if __name__ == '__main__':
    main()
