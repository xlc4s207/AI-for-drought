#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import datetime as dt
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib import font_manager as fm
from matplotlib import gridspec
from matplotlib import pyplot as plt
from matplotlib import rcParams
import netCDF4 as nc
import numpy as np


BASE_DIR = Path("/home/xulc/flash_drought")
OUT_DIR = BASE_DIR / "process/result_analysis/performance/diagnostic_gleam_vs_era5_root"

GLEAM_EVENT_DIR = BASE_DIR / "gleam/clip_result/SMrz_result_v5.4_0p25deg_no_ice_desert"
ERA5_EVENT_DIR = BASE_DIR / "era5/clip_result/ERA5L_root_result_v5.4_0p25deg_no_ice_desert"

GLEAM_DAILY_FILE = Path("/data/GLEAM/0p25deg_yearly/SMrz_45years_0p25deg.nc")
ERA5_DAILY_FILE_OPT = BASE_DIR / "era5/optimized_input/volumetric_root_soil_water_0p25deg_1980_2024_chunk_t365_lat1_lon1440.nc"
ERA5_DAILY_FILE_RAW = Path("/data/era5_for_GRN/yearly/volumetric_root_soil_water_0p25deg_1980_2024.nc")

EVENT_FILE_NAMES = {
    "flash_lt20": "flash_lt20_drought_events_v5.4.nc",
    "rapid_1to4": "rapid_1to4_drought_events_v5.4.nc",
    "flash_5to20": "flash_5to20_drought_events_v5.4.nc",
}

LAT_BANDS = [(-90, -60), (-60, -30), (-30, 0), (0, 30), (30, 60), (60, 90)]
PIXEL_LABELS = {
    "high_lat_hotspot": "A 高纬热点",
    "mid_lat_hotspot": "B 中纬热点",
    "tropical_hotspot": "C 热带热点",
    "shared_nonzero": "D 共享像元",
}
PIXEL_CN = {
    "high_lat_hotspot": "GLEAM高纬热点",
    "mid_lat_hotspot": "GLEAM中纬热点",
    "tropical_hotspot": "GLEAM热带热点",
    "shared_nonzero": "双方均有事件但GLEAM更多",
}


PROCESS2_DIR = BASE_DIR / "process/process2"
if str(PROCESS2_DIR) not in sys.path:
    sys.path.insert(0, str(PROCESS2_DIR))

import drought_core_v54_threeclass as core  # noqa: E402


@dataclass(frozen=True)
class DatasetContext:
    label: str
    nc_path: Path
    var_name: str
    color: str
    daily_file_label: str


@dataclass(frozen=True)
class PixelSelection:
    key: str
    lat_idx: int
    lon_idx: int
    lat: float
    lon: float
    gleam_count: int
    era5_count: int
    diff: int


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


def resolve_era5_daily_file() -> Path:
    return ERA5_DAILY_FILE_OPT if ERA5_DAILY_FILE_OPT.exists() else ERA5_DAILY_FILE_RAW


def compute_diff_source_breakdown(gleam_counts: np.ndarray, era5_counts: np.ndarray) -> dict[str, int]:
    diff = gleam_counts - era5_counts
    positive = diff > 0
    gleam_only = (gleam_counts > 0) & (era5_counts == 0)
    shared_more = (gleam_counts > era5_counts) & (era5_counts > 0)
    return {
        "gleam_gt0_era5_eq0_pixels": int(np.sum(gleam_only)),
        "gleam_gt0_era5_eq0_diff_sum": int(np.sum(diff[gleam_only])),
        "gleam_gt_era5_and_era5_gt0_pixels": int(np.sum(shared_more)),
        "gleam_gt_era5_and_era5_gt0_diff_sum": int(np.sum(diff[shared_more])),
        "total_positive_diff_sum": int(np.sum(diff[positive])),
    }


def summarize_lat_band_diff(
    gleam_counts: np.ndarray,
    era5_counts: np.ndarray,
    lat: np.ndarray,
    bands: Iterable[tuple[float, float]] = LAT_BANDS,
) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for lo, hi in bands:
        lat_mask = (lat >= lo) & (lat < hi)
        gleam_total = int(np.sum(gleam_counts[lat_mask, :]))
        era5_total = int(np.sum(era5_counts[lat_mask, :]))
        rows.append(
            {
                "lat_min": lo,
                "lat_max": hi,
                "band_label": f"{lo}~{hi}",
                "gleam_total": gleam_total,
                "era5_total": era5_total,
                "diff_total": gleam_total - era5_total,
            }
        )
    return rows


def _select_one(
    key: str,
    mask: np.ndarray,
    diff: np.ndarray,
    gleam_counts: np.ndarray,
    era5_counts: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
) -> PixelSelection | None:
    valid = mask & (diff > 0)
    if not np.any(valid):
        return None
    masked_diff = np.where(valid, diff, -10**9)
    idx = int(np.argmax(masked_diff))
    i, j = np.unravel_index(idx, diff.shape)
    return PixelSelection(
        key=key,
        lat_idx=int(i),
        lon_idx=int(j),
        lat=float(lat[i]),
        lon=float(lon[j]),
        gleam_count=int(gleam_counts[i, j]),
        era5_count=int(era5_counts[i, j]),
        diff=int(diff[i, j]),
    )


def select_typical_pixels(
    gleam_counts: np.ndarray,
    era5_counts: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
) -> dict[str, PixelSelection]:
    diff = gleam_counts - era5_counts
    lat2d = np.repeat(lat[:, None], lon.size, axis=1)
    selections: dict[str, PixelSelection] = {}

    rules = {
        "high_lat_hotspot": (np.abs(lat2d) >= 60) & (era5_counts == 0),
        "mid_lat_hotspot": (np.abs(lat2d) >= 30) & (np.abs(lat2d) < 60) & (era5_counts == 0),
        "tropical_hotspot": (np.abs(lat2d) < 23.5) & (era5_counts == 0),
        "shared_nonzero": (era5_counts > 0) & (gleam_counts > era5_counts),
    }

    for key, mask in rules.items():
        picked = _select_one(key, mask, diff, gleam_counts, era5_counts, lat, lon)
        if picked is not None:
            selections[key] = picked
    return selections


def choose_focus_window(
    events: list[dict],
    pad_days: int,
    series_len: int,
    series_start_ord: int | None = None,
) -> tuple[int, int]:
    if not events:
        return 0, min(series_len - 1, 729)
    if all("start_idx" in e and "end_idx" in e for e in events):
        start_idx = max(0, min(int(e["start_idx"]) for e in events) - pad_days)
        end_idx = min(series_len - 1, max(int(e["end_idx"]) for e in events) + pad_days)
        return start_idx, end_idx
    if series_start_ord is None:
        raise KeyError("choose_focus_window 需要 start_idx/end_idx，或提供 series_start_ord 用于 start_ord/end_ord 转换")
    start_idx = max(0, min(int(e["start_ord"]) - series_start_ord for e in events) - pad_days)
    end_idx = min(series_len - 1, max(int(e["end_ord"]) - series_start_ord for e in events) + pad_days)
    return start_idx, end_idx


def ordinal_from_year_doy(year: int, doy: int) -> int:
    if year <= 0 or doy <= 0:
        return -1
    return (dt.date(year, 1, 1) + dt.timedelta(days=doy - 1)).toordinal()


def read_event_counts(nc_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with nc.Dataset(nc_path) as ds:
        lat = np.asarray(ds.variables["lat"][:], dtype=np.float32)
        lon = np.asarray(ds.variables["lon"][:], dtype=np.float32)
        count = ds.variables["event_count"][:]
        if hasattr(count, "filled"):
            count = count.filled(0)
        count = np.asarray(count, dtype=np.int32)
        count = np.where(count < 0, 0, count)
    return lat, lon, count


def read_pixel_events(nc_path: Path, lat_idx: int, lon_idx: int) -> list[dict]:
    with nc.Dataset(nc_path) as ds:
        event_count = int(np.ma.filled(ds.variables["event_count"][lat_idx, lon_idx], 0))
        if event_count <= 0:
            return []
        keys = [
            "onset_start_year",
            "onset_start_doy",
            "drought_start_year",
            "drought_start_doy",
            "drought_end_year",
            "drought_end_doy",
            "onset_days",
            "duration",
            "days_below_p20",
        ]
        arrs = {}
        for key in keys:
            arr = ds.variables[key][:event_count, lat_idx, lon_idx]
            arrs[key] = np.ma.filled(arr, -1).astype(np.int32)

    events = []
    for idx in range(event_count):
        start_year = int(arrs["drought_start_year"][idx])
        start_doy = int(arrs["drought_start_doy"][idx])
        end_year = int(arrs["drought_end_year"][idx])
        end_doy = int(arrs["drought_end_doy"][idx])
        if start_year <= 0 or start_doy <= 0 or end_year <= 0 or end_doy <= 0:
            continue
        events.append(
            {
                "onset_start_year": int(arrs["onset_start_year"][idx]),
                "onset_start_doy": int(arrs["onset_start_doy"][idx]),
                "drought_start_year": start_year,
                "drought_start_doy": start_doy,
                "drought_end_year": end_year,
                "drought_end_doy": end_doy,
                "onset_days": int(arrs["onset_days"][idx]),
                "duration": int(arrs["duration"][idx]),
                "days_below_p20": int(arrs["days_below_p20"][idx]),
                "start_ord": ordinal_from_year_doy(start_year, start_doy),
                "end_ord": ordinal_from_year_doy(end_year, end_doy),
            }
        )
    events.sort(key=lambda x: x["start_ord"])
    return events


def _representative_year(events: list[dict]) -> int | None:
    if not events:
        return None
    years = [int(e["drought_start_year"]) for e in events if int(e["drought_start_year"]) > 0]
    if not years:
        return None
    values, counts = np.unique(np.asarray(years, dtype=np.int32), return_counts=True)
    return int(values[np.argmax(counts)])


def select_focus_events(gleam_events: list[dict], era5_events: list[dict]) -> list[dict]:
    combined = gleam_events + era5_events
    if not combined:
        return []
    year = _representative_year(combined)
    if year is None:
        return combined
    focus = [
        e
        for e in combined
        if int(e["drought_start_year"]) == year
        or int(e["drought_end_year"]) == year
    ]
    return focus if focus else combined


def load_pixel_series_with_thresholds(context: DatasetContext, lat_idx: int, lon_idx: int) -> dict:
    valid_years = set(range(1980, 2025))
    ref_years = set(range(1981, 2011))
    with nc.Dataset(context.nc_path) as ds:
        dates, _, doy_to_indices_for_ref, _, is_daily, daily_time_indices, time_slice = core.build_daily_indices_from_time(
            ds.variables["time"], valid_years, ref_years
        )
        prebuilt = core.build_prebuilt_window_indices(doy_to_indices_for_ref)
        if time_slice is not None:
            t0, t1 = time_slice
            x = ds.variables[context.var_name][t0:t1, lat_idx, lon_idx]
        else:
            x = ds.variables[context.var_name][daily_time_indices, lat_idx, lon_idx]
        if hasattr(x, "mask"):
            x = np.ma.filled(x, np.nan)
        raw = np.asarray(x, dtype=np.float64)
        ma = core.calculate_backward_moving_average_by_year(raw.reshape(-1, 1), dates, core.MOVING_WINDOW)[:, 0]
        p20, p40 = core.calculate_percentiles_batch(ma.reshape(-1, 1), prebuilt)
        p20 = p20[:, 0]
        p40 = p40[:, 0]
        datetimes = [dt.date(y, 1, 1) + dt.timedelta(days=doy - 1) for y, doy in dates]
    return {
        "dates": datetimes,
        "smoothed": ma,
        "p20": np.array([p20[doy] if doy < len(p20) else np.nan for _, doy in dates], dtype=np.float64),
        "p40": np.array([p40[doy] if doy < len(p40) else np.nan for _, doy in dates], dtype=np.float64),
    }


def build_diagnostics() -> dict:
    gleam_lat, gleam_lon, gleam_total = read_event_counts(GLEAM_EVENT_DIR / EVENT_FILE_NAMES["flash_lt20"])
    era5_lat, era5_lon, era5_total = read_event_counts(ERA5_EVENT_DIR / EVENT_FILE_NAMES["flash_lt20"])
    if gleam_total.shape != era5_total.shape:
        raise ValueError("GLEAM 与 ERA5 事件频次数组形状不一致")

    _, _, gleam_rapid = read_event_counts(GLEAM_EVENT_DIR / EVENT_FILE_NAMES["rapid_1to4"])
    _, _, era5_rapid = read_event_counts(ERA5_EVENT_DIR / EVENT_FILE_NAMES["rapid_1to4"])
    _, _, gleam_flash = read_event_counts(GLEAM_EVENT_DIR / EVENT_FILE_NAMES["flash_5to20"])
    _, _, era5_flash = read_event_counts(ERA5_EVENT_DIR / EVENT_FILE_NAMES["flash_5to20"])

    lat_band_rows = summarize_lat_band_diff(gleam_total, era5_total, gleam_lat, LAT_BANDS)
    diff_breakdown = compute_diff_source_breakdown(gleam_total, era5_total)
    pixel_selections = select_typical_pixels(gleam_total, era5_total, gleam_lat, gleam_lon)

    return {
        "lat": gleam_lat,
        "lon": gleam_lon,
        "gleam_total": gleam_total,
        "era5_total": era5_total,
        "gleam_rapid": gleam_rapid,
        "era5_rapid": era5_rapid,
        "gleam_flash": gleam_flash,
        "era5_flash": era5_flash,
        "lat_band_rows": lat_band_rows,
        "diff_breakdown": diff_breakdown,
        "pixel_selections": pixel_selections,
    }


def plot_overview(diagnostics: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(18, 11), dpi=320)
    gs = gridspec.GridSpec(2, 3, figure=fig, wspace=0.25, hspace=0.28)

    gleam_total = diagnostics["gleam_total"]
    era5_total = diagnostics["era5_total"]
    gleam_rapid = diagnostics["gleam_rapid"]
    era5_rapid = diagnostics["era5_rapid"]
    gleam_flash = diagnostics["gleam_flash"]
    era5_flash = diagnostics["era5_flash"]
    lat = diagnostics["lat"]
    lon = diagnostics["lon"]
    diff = gleam_total - era5_total
    selections: dict[str, PixelSelection] = diagnostics["pixel_selections"]

    # Panel A: composition bars
    ax = fig.add_subplot(gs[0, 0])
    labels = ["GLEAM", "ERA5"]
    rapid_vals = [int(np.sum(gleam_rapid)), int(np.sum(era5_rapid))]
    flash_vals = [int(np.sum(gleam_flash)), int(np.sum(era5_flash))]
    ax.bar(labels, rapid_vals, color="#d94841", label="1-4天")
    ax.bar(labels, flash_vals, bottom=rapid_vals, color="#fdae6b", label="5-20天")
    for i, total in enumerate(np.array(rapid_vals) + np.array(flash_vals)):
        ax.text(i, total * 1.01, f"{total:,}", ha="center", va="bottom", fontsize=10)
    ax.set_title("骤旱组成对比", fontsize=14)
    ax.set_ylabel("事件数")
    ax.legend(frameon=False, fontsize=10)

    # Panel B: latitude-band diff
    ax = fig.add_subplot(gs[0, 1])
    rows = diagnostics["lat_band_rows"]
    band_labels = [r["band_label"] for r in rows]
    band_diff = [r["diff_total"] for r in rows]
    colors = ["#2b8cbe" if x >= 0 else "#969696" for x in band_diff]
    ax.bar(band_labels, band_diff, color=colors)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("纬度带差异贡献", fontsize=14)
    ax.set_ylabel("GLEAM - ERA5 事件数")
    ax.tick_params(axis="x", rotation=20)

    # Panel C: diff source
    ax = fig.add_subplot(gs[0, 2])
    breakdown = diagnostics["diff_breakdown"]
    source_labels = ["ERA5=0", "两边都有事件\n但GLEAM更多"]
    source_vals = [
        breakdown["gleam_gt0_era5_eq0_diff_sum"],
        breakdown["gleam_gt_era5_and_era5_gt0_diff_sum"],
    ]
    ax.bar(source_labels, source_vals, color=["#756bb1", "#31a354"])
    ax.set_title("差异来源分解", fontsize=14)
    ax.set_ylabel("正差值事件数")
    total_pos = max(breakdown["total_positive_diff_sum"], 1)
    for i, value in enumerate(source_vals):
        ax.text(i, value * 1.01, f"{value/total_pos:.1%}", ha="center", va="bottom", fontsize=10)

    # Panel D: active pixel distribution
    ax = fig.add_subplot(gs[1, 0])
    gleam_active = gleam_total[gleam_total > 0]
    era5_active = era5_total[era5_total > 0]
    bins = np.linspace(0, float(np.nanpercentile(gleam_active, 98)), 35)
    ax.hist(gleam_active, bins=bins, alpha=0.55, color="#3182bd", density=True, label="GLEAM")
    ax.hist(era5_active, bins=bins, alpha=0.55, color="#ef6548", density=True, label="ERA5")
    ax.set_title("活跃像元事件次数分布", fontsize=14)
    ax.set_xlabel("每像元事件数")
    ax.set_ylabel("概率密度")
    ax.legend(frameon=False, fontsize=10)

    # Panel E: difference map
    ax = fig.add_subplot(gs[1, 1:], projection=ccrs.PlateCarree())
    arr = np.where(diff == 0, np.nan, diff).astype(np.float32)
    vmax = float(np.nanpercentile(np.abs(arr[np.isfinite(arr)]), 98)) if np.any(np.isfinite(arr)) else 1.0
    im = ax.imshow(
        arr,
        extent=[float(lon.min()), float(lon.max()), float(lat.min()), float(lat.max())],
        origin="lower" if lat[1] > lat[0] else "upper",
        transform=ccrs.PlateCarree(),
        cmap="RdBu_r",
        vmin=-vmax,
        vmax=vmax,
        interpolation="nearest",
        zorder=1,
    )
    ax.add_feature(cfeature.LAND.with_scale("110m"), facecolor="#f6f1e8", edgecolor="none", zorder=-2)
    ax.add_feature(cfeature.OCEAN.with_scale("110m"), facecolor="#f2f6fb", edgecolor="none", zorder=-3)
    ax.add_feature(cfeature.COASTLINE.with_scale("110m"), linewidth=0.55, edgecolor="black", zorder=3)
    ax.set_extent([-180, 180, -60, 85], crs=ccrs.PlateCarree())
    gl = ax.gridlines(draw_labels=True, linewidth=0.25, color="gray", alpha=0.3, linestyle="--")
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {"size": 8}
    gl.ylabel_style = {"size": 8}
    ax.set_title("每像元骤旱事件差值（GLEAM - ERA5）", fontsize=14)
    for key, picked in selections.items():
        ax.scatter(
            picked.lon,
            picked.lat,
            s=36,
            c="#111111",
            edgecolors="white",
            linewidths=0.7,
            transform=ccrs.PlateCarree(),
            zorder=4,
        )
        ax.text(
            picked.lon + 2.5,
            picked.lat + 1.5,
            PIXEL_LABELS.get(key, key),
            fontsize=10,
            weight="bold",
            color="#111111",
            transform=ccrs.PlateCarree(),
            zorder=5,
        )
    cb = fig.colorbar(im, ax=ax, orientation="horizontal", pad=0.05, fraction=0.05)
    cb.set_label("GLEAM - ERA5 事件数", fontsize=10)
    cb.ax.tick_params(labelsize=9)

    fig.suptitle("GLEAM 与 ERA5 根区骤旱差异诊断图", fontsize=18, y=0.98)
    out_path = OUT_DIR / "gleam_vs_era5_root_flash_diagnostic_overview.png"
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def plot_typical_pixels(diagnostics: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    contexts = {
        "GLEAM": DatasetContext("GLEAM", GLEAM_DAILY_FILE, "SMrz", "#2b8cbe", "GLEAM SMrz"),
        "ERA5": DatasetContext("ERA5", resolve_era5_daily_file(), "root_water", "#ef6548", "ERA5 root"),
    }
    event_dirs = {
        "GLEAM": GLEAM_EVENT_DIR / EVENT_FILE_NAMES["flash_lt20"],
        "ERA5": ERA5_EVENT_DIR / EVENT_FILE_NAMES["flash_lt20"],
    }

    fig, axes = plt.subplots(4, 1, figsize=(18, 14), dpi=320, sharex=False)
    selections: dict[str, PixelSelection] = diagnostics["pixel_selections"]

    for ax, key in zip(axes, [k for k in PIXEL_LABELS if k in selections]):
        picked = selections[key]
        gleam_events = read_pixel_events(event_dirs["GLEAM"], picked.lat_idx, picked.lon_idx)
        era5_events = read_pixel_events(event_dirs["ERA5"], picked.lat_idx, picked.lon_idx)
        focus_events = select_focus_events(gleam_events, era5_events)

        gleam_series = load_pixel_series_with_thresholds(contexts["GLEAM"], picked.lat_idx, picked.lon_idx)
        era5_series = load_pixel_series_with_thresholds(contexts["ERA5"], picked.lat_idx, picked.lon_idx)
        start_idx, end_idx = choose_focus_window(
            focus_events,
            pad_days=50,
            series_len=len(gleam_series["dates"]),
            series_start_ord=gleam_series["dates"][0].toordinal(),
        )

        # Fallback for empty or invalid window
        if end_idx <= start_idx:
            start_idx, end_idx = 0, min(len(gleam_series["dates"]) - 1, 729)
        xs = np.arange(start_idx, end_idx + 1)
        dates = gleam_series["dates"][start_idx : end_idx + 1]

        # Draw event windows first
        for event in gleam_events:
            if event["end_ord"] < gleam_series["dates"][start_idx].toordinal() or event["start_ord"] > gleam_series["dates"][end_idx].toordinal():
                continue
            s = max(start_idx, event["start_ord"] - gleam_series["dates"][0].toordinal())
            e = min(end_idx, event["end_ord"] - gleam_series["dates"][0].toordinal())
            ax.axvspan(s, e, color="#2b8cbe", alpha=0.10)
        for event in era5_events:
            if event["end_ord"] < gleam_series["dates"][start_idx].toordinal() or event["start_ord"] > gleam_series["dates"][end_idx].toordinal():
                continue
            s = max(start_idx, event["start_ord"] - gleam_series["dates"][0].toordinal())
            e = min(end_idx, event["end_ord"] - gleam_series["dates"][0].toordinal())
            ax.axvspan(s, e, color="#ef6548", alpha=0.08)

        ax.plot(xs, gleam_series["smoothed"][start_idx : end_idx + 1], color="#2b8cbe", linewidth=1.4, label="GLEAM 5日平滑")
        ax.plot(xs, gleam_series["p20"][start_idx : end_idx + 1], color="#2b8cbe", linewidth=0.9, linestyle="--", alpha=0.8, label="GLEAM P20")
        ax.plot(xs, gleam_series["p40"][start_idx : end_idx + 1], color="#2b8cbe", linewidth=0.9, linestyle=":", alpha=0.8, label="GLEAM P40")

        ax.plot(xs, era5_series["smoothed"][start_idx : end_idx + 1], color="#ef6548", linewidth=1.4, label="ERA5 5日平滑")
        ax.plot(xs, era5_series["p20"][start_idx : end_idx + 1], color="#ef6548", linewidth=0.9, linestyle="--", alpha=0.8, label="ERA5 P20")
        ax.plot(xs, era5_series["p40"][start_idx : end_idx + 1], color="#ef6548", linewidth=0.9, linestyle=":", alpha=0.8, label="ERA5 P40")

        tick_idx = np.linspace(start_idx, end_idx, 6, dtype=int)
        tick_idx = np.unique(tick_idx)
        ax.set_xticks(tick_idx)
        ax.set_xticklabels([gleam_series["dates"][idx].strftime("%Y-%m") for idx in tick_idx], rotation=20)
        ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.35)
        ax.set_ylabel("土壤湿度")
        ax.set_title(
            f"{PIXEL_LABELS[key]} | {PIXEL_CN[key]} | ({picked.lat:.3f}, {picked.lon:.3f}) | "
            f"GLEAM={picked.gleam_count} ERA5={picked.era5_count}",
            fontsize=12,
            pad=6,
        )

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles[:6], labels[:6], loc="upper center", ncol=6, frameon=False, fontsize=10)
    fig.suptitle("典型像元根区土壤湿度与阈值诊断图", fontsize=18, y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.975])
    out_path = OUT_DIR / "gleam_vs_era5_root_flash_typical_pixels.png"
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def main() -> None:
    font_name = setup_chinese_font()
    print(f"中文字体: {font_name}")
    diagnostics = build_diagnostics()
    overview = plot_overview(diagnostics)
    print(f"已写出: {overview}")
    typical = plot_typical_pixels(diagnostics)
    print(f"已写出: {typical}")


if __name__ == "__main__":
    main()
