#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from collections import OrderedDict
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib import pyplot as plt
import netCDF4 as nc
import numpy as np


BASE_DIR = Path("/home/xulc/flash_drought")
OUT_DIR = BASE_DIR / "process/result_analysis/performance/diagnostic_gleam_vs_era5_multi_scenarios"

RESULT_ANALYSIS_CODE = BASE_DIR / "process/result_analysis/code"
if str(RESULT_ANALYSIS_CODE) not in sys.path:
    sys.path.insert(0, str(RESULT_ANALYSIS_CODE))

from build_gleam_vs_era5_root_diagnostic_figures import (  # noqa: E402
    DatasetContext,
    PIXEL_CN,
    PIXEL_LABELS,
    choose_focus_window,
    compute_diff_source_breakdown,
    load_pixel_series_with_thresholds,
    read_event_counts,
    read_pixel_events,
    select_focus_events,
    setup_chinese_font,
    summarize_lat_band_diff,
)


@dataclass(frozen=True)
class ScenarioConfig:
    key: str
    title_cn: str
    soil_layer: str
    event_kind: str
    gleam_event_file: str
    era5_event_file: str
    gleam_daily_file: str
    era5_daily_file: str
    gleam_var: str
    era5_var: str


def build_scenarios() -> list[ScenarioConfig]:
    era5_root_daily = "/home/xulc/flash_drought/era5/optimized_input/volumetric_root_soil_water_0p25deg_1980_2024_chunk_t365_lat1_lon1440.nc"
    era5_root_daily_fallback = "/data/era5_for_GRN/yearly/volumetric_root_soil_water_0p25deg_1980_2024.nc"
    era5_surf_daily = "/home/xulc/flash_drought/era5/optimized_input/volumetric_soil_water_layer_1_0p25deg_1980_2024_chunk_t365_lat1_lon1440.nc"
    era5_surf_daily_fallback = "/data/era5_for_GRN/yearly/volumetric_soil_water_layer_1_0p25deg_1980_2024.nc"

    root_daily = era5_root_daily if Path(era5_root_daily).exists() else era5_root_daily_fallback
    surf_daily = era5_surf_daily if Path(era5_surf_daily).exists() else era5_surf_daily_fallback

    return [
        ScenarioConfig(
            key="SMrz_flash",
            title_cn="根系土壤骤旱",
            soil_layer="SMrz",
            event_kind="flash",
            gleam_event_file=str(BASE_DIR / "gleam/clip_result/SMrz_result_v5.4_0p25deg_no_ice_desert/flash_lt20_drought_events_v5.4.nc"),
            era5_event_file=str(BASE_DIR / "era5/clip_result/ERA5L_root_result_v5.4_0p25deg_no_ice_desert/flash_lt20_drought_events_v5.4.nc"),
            gleam_daily_file="/data/GLEAM/0p25deg_yearly/SMrz_45years_0p25deg.nc",
            era5_daily_file=root_daily,
            gleam_var="SMrz",
            era5_var="root_water",
        ),
        ScenarioConfig(
            key="SMs_flash",
            title_cn="表层土壤骤旱",
            soil_layer="SMs",
            event_kind="flash",
            gleam_event_file=str(BASE_DIR / "gleam/clip_result/SMs_result_v5.4_0p25deg_no_ice_desert/flash_lt20_drought_events_v5.4.nc"),
            era5_event_file=str(BASE_DIR / "era5/clip_result/ERA5L_swvl1_result_v5.4_0p25deg_no_ice_desert/flash_lt20_drought_events_v5.4.nc"),
            gleam_daily_file="/data/GLEAM/0p25deg_yearly/SMs_45years_0p25deg.nc",
            era5_daily_file=surf_daily,
            gleam_var="SMs",
            era5_var="swvl1",
        ),
        ScenarioConfig(
            key="SMrz_slow",
            title_cn="根系土壤缓旱",
            soil_layer="SMrz",
            event_kind="slow",
            gleam_event_file=str(BASE_DIR / "gleam/clip_result/SMrz_result_v5.4_0p25deg_no_ice_desert/slow_gt20_drought_events_v5.4.nc"),
            era5_event_file=str(BASE_DIR / "era5/clip_result/ERA5L_root_result_v5.4_0p25deg_no_ice_desert/slow_gt20_drought_events_v5.4.nc"),
            gleam_daily_file="/data/GLEAM/0p25deg_yearly/SMrz_45years_0p25deg.nc",
            era5_daily_file=root_daily,
            gleam_var="SMrz",
            era5_var="root_water",
        ),
        ScenarioConfig(
            key="SMs_slow",
            title_cn="表层土壤缓旱",
            soil_layer="SMs",
            event_kind="slow",
            gleam_event_file=str(BASE_DIR / "gleam/clip_result/SMs_result_v5.4_0p25deg_no_ice_desert/slow_gt20_drought_events_v5.4.nc"),
            era5_event_file=str(BASE_DIR / "era5/clip_result/ERA5L_swvl1_result_v5.4_0p25deg_no_ice_desert/slow_gt20_drought_events_v5.4.nc"),
            gleam_daily_file="/data/GLEAM/0p25deg_yearly/SMs_45years_0p25deg.nc",
            era5_daily_file=surf_daily,
            gleam_var="SMs",
            era5_var="swvl1",
        ),
    ]


def _event_counts_to_active_values(arr: np.ndarray) -> np.ndarray:
    vals = np.asarray(arr, dtype=np.int32)
    return vals[vals > 0]


def _valid_metric_values(arr: np.ndarray, kind: str) -> np.ndarray:
    data = np.asarray(arr, dtype=np.float64).ravel()
    data = data[np.isfinite(data)]
    if kind in {"duration", "days_below_p20", "onset_days"}:
        data = data[data > 0]
    return data


def summarize_event_metrics(nc_path: str, event_kind: str) -> dict:
    with nc.Dataset(nc_path) as ds:
        summary = {}
        for name in ["duration", "days_below_p20", "intensity"]:
            arr = ds.variables[name][:]
            if hasattr(arr, "filled"):
                fill = -9999 if name != "intensity" else np.nan
                arr = arr.filled(fill)
            vals = _valid_metric_values(arr, name)
            summary[name] = {
                "mean": float(np.mean(vals)) if vals.size else np.nan,
                "median": float(np.median(vals)) if vals.size else np.nan,
            }
        if event_kind == "flash":
            arr = ds.variables["onset_days"][:]
            if hasattr(arr, "filled"):
                arr = arr.filled(-9999)
            vals = _valid_metric_values(arr, "onset_days")
            summary["onset_days"] = {
                "mean": float(np.mean(vals)) if vals.size else np.nan,
                "median": float(np.median(vals)) if vals.size else np.nan,
            }
        return summary


def choose_fallback_pixel(
    gleam_counts: np.ndarray,
    era5_counts: np.ndarray,
    used_indices: set[tuple[int, int]],
) -> tuple[int, int]:
    diff = gleam_counts - era5_counts
    valid = diff > 0
    if used_indices:
        for i, j in used_indices:
            valid[i, j] = False
    if not np.any(valid):
        idx = int(np.argmax(diff))
        return tuple(np.unravel_index(idx, diff.shape))
    masked = np.where(valid, diff, -10**9)
    idx = int(np.argmax(masked))
    return tuple(np.unravel_index(idx, diff.shape))


def select_typical_pixels_with_fallback(
    gleam_counts: np.ndarray,
    era5_counts: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
) -> OrderedDict[str, dict]:
    diff = gleam_counts - era5_counts
    lat2d = np.repeat(lat[:, None], len(lon), axis=1)
    categories = OrderedDict(
        [
            ("high_lat_hotspot", (np.abs(lat2d) >= 60) & (era5_counts == 0) & (diff > 0)),
            ("mid_lat_hotspot", (np.abs(lat2d) >= 30) & (np.abs(lat2d) < 60) & (era5_counts == 0) & (diff > 0)),
            ("tropical_hotspot", (np.abs(lat2d) < 23.5) & (era5_counts == 0) & (diff > 0)),
            ("shared_nonzero", (era5_counts > 0) & (gleam_counts > era5_counts)),
        ]
    )
    used: set[tuple[int, int]] = set()
    picks: OrderedDict[str, dict] = OrderedDict()
    for key, mask in categories.items():
        if np.any(mask):
            masked = np.where(mask, diff, -10**9)
            idx = int(np.argmax(masked))
            i, j = np.unravel_index(idx, diff.shape)
        else:
            i, j = choose_fallback_pixel(gleam_counts, era5_counts, used)
        used.add((int(i), int(j)))
        picks[key] = {
            "key": key,
            "lat_idx": int(i),
            "lon_idx": int(j),
            "lat": float(lat[i]),
            "lon": float(lon[j]),
            "gleam_count": int(gleam_counts[i, j]),
            "era5_count": int(era5_counts[i, j]),
            "diff": int(diff[i, j]),
        }
    return picks


def prepare_scenario_summary(
    key: str,
    title_cn: str,
    gleam_total: np.ndarray,
    era5_total: np.ndarray,
    lat: np.ndarray,
    gleam_aux: dict | None = None,
    era5_aux: dict | None = None,
) -> dict:
    gleam_aux = gleam_aux or {}
    era5_aux = era5_aux or {}
    gleam_active = gleam_total > 0
    era5_active = era5_total > 0
    gleam_active_vals = gleam_total[gleam_active]
    era5_active_vals = era5_total[era5_active]
    return {
        "key": key,
        "title_cn": title_cn,
        "gleam_total_events": int(np.sum(gleam_total)),
        "era5_total_events": int(np.sum(era5_total)),
        "gleam_active_pixels": int(np.sum(gleam_active)),
        "era5_active_pixels": int(np.sum(era5_active)),
        "gleam_mean_events_per_active_pixel": float(np.mean(gleam_active_vals)) if gleam_active_vals.size else np.nan,
        "era5_mean_events_per_active_pixel": float(np.mean(era5_active_vals)) if era5_active_vals.size else np.nan,
        "gleam_median_events_per_active_pixel": float(np.median(gleam_active_vals)) if gleam_active_vals.size else np.nan,
        "era5_median_events_per_active_pixel": float(np.median(era5_active_vals)) if era5_active_vals.size else np.nan,
        "diff_breakdown": compute_diff_source_breakdown(gleam_total, era5_total),
        "lat_band_rows": summarize_lat_band_diff(gleam_total, era5_total, lat),
        "gleam_aux": gleam_aux,
        "era5_aux": era5_aux,
    }


def build_scenario_diagnostics(scenario: ScenarioConfig) -> dict:
    lat, lon, gleam_total = read_event_counts(Path(scenario.gleam_event_file))
    _, _, era5_total = read_event_counts(Path(scenario.era5_event_file))
    if gleam_total.shape != era5_total.shape:
        raise ValueError(f"{scenario.key} 事件数组形状不一致")

    gleam_aux = summarize_event_metrics(scenario.gleam_event_file, scenario.event_kind)
    era5_aux = summarize_event_metrics(scenario.era5_event_file, scenario.event_kind)
    if scenario.event_kind == "flash":
        _, _, g_rapid = read_event_counts(Path(scenario.gleam_event_file.replace("flash_lt20", "rapid_1to4")))
        _, _, e_rapid = read_event_counts(Path(scenario.era5_event_file.replace("flash_lt20", "rapid_1to4")))
        _, _, g_flash = read_event_counts(Path(scenario.gleam_event_file.replace("flash_lt20", "flash_5to20")))
        _, _, e_flash = read_event_counts(Path(scenario.era5_event_file.replace("flash_lt20", "flash_5to20")))
        gleam_aux["rapid_total"] = int(np.sum(g_rapid))
        gleam_aux["flash_total"] = int(np.sum(g_flash))
        era5_aux["rapid_total"] = int(np.sum(e_rapid))
        era5_aux["flash_total"] = int(np.sum(e_flash))

    summary = prepare_scenario_summary(
        key=scenario.key,
        title_cn=scenario.title_cn,
        gleam_total=gleam_total,
        era5_total=era5_total,
        lat=lat,
        gleam_aux=gleam_aux,
        era5_aux=era5_aux,
    )
    summary["lat"] = lat
    summary["lon"] = lon
    summary["gleam_total_grid"] = gleam_total
    summary["era5_total_grid"] = era5_total
    summary["typical_pixels"] = select_typical_pixels_with_fallback(gleam_total, era5_total, lat, lon)
    summary["scenario"] = scenario
    return summary


def build_all_diagnostics() -> list[dict]:
    return [build_scenario_diagnostics(s) for s in build_scenarios()]


def _scenario_labels(diag: dict) -> tuple[list[str], list[float], list[float]]:
    labels = ["总事件数", "活跃像元数", "活跃像元均值"]
    gleam_vals = [
        diag["gleam_total_events"] / 1e6,
        diag["gleam_active_pixels"] / 1e3,
        diag["gleam_mean_events_per_active_pixel"],
    ]
    era5_vals = [
        diag["era5_total_events"] / 1e6,
        diag["era5_active_pixels"] / 1e3,
        diag["era5_mean_events_per_active_pixel"],
    ]
    return labels, gleam_vals, era5_vals


def plot_summary_overview(diagnostics: list[dict]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(4, 3, figsize=(16, 16), dpi=320)
    colors = {"GLEAM": "#2b8cbe", "ERA5": "#ef6548"}
    for row, diag in enumerate(diagnostics):
        labels, gleam_vals, era5_vals = _scenario_labels(diag)
        for col, (label, gv, ev) in enumerate(zip(labels, gleam_vals, era5_vals)):
            ax = axes[row, col]
            ax.bar(["GLEAM", "ERA5"], [gv, ev], color=[colors["GLEAM"], colors["ERA5"]], width=0.62)
            ax.set_title(f"{diag['title_cn']} | {label}", fontsize=11)
            ax.grid(True, axis="y", linestyle="--", alpha=0.25)
            if col == 0:
                ax.set_ylabel("百万" if label == "总事件数" else ("千像元" if label == "活跃像元数" else "事件/像元"))
            ymax = max(gv, ev) if np.isfinite([gv, ev]).all() else 0
            if ymax > 0:
                ax.text(0, gv * 1.02, f"{gv:.2f}", ha="center", va="bottom", fontsize=9)
                ax.text(1, ev * 1.02, f"{ev:.2f}", ha="center", va="bottom", fontsize=9)
    fig.suptitle("GLEAM 与 ERA5 四情景事件规模总览", fontsize=18, y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.985])
    out_path = OUT_DIR / "multi_scenario_event_scale_overview.png"
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def plot_structural_comparison(diagnostics: list[dict]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), dpi=320)
    axes = axes.ravel()
    for ax, diag in zip(axes, diagnostics):
        if diag["scenario"].event_kind == "flash":
            g_vals = [diag["gleam_aux"].get("rapid_total", 0), diag["gleam_aux"].get("flash_total", 0)]
            e_vals = [diag["era5_aux"].get("rapid_total", 0), diag["era5_aux"].get("flash_total", 0)]
            x = np.arange(2)
            w = 0.34
            ax.bar(x - w / 2, g_vals, width=w, color="#2b8cbe", label="GLEAM")
            ax.bar(x + w / 2, e_vals, width=w, color="#ef6548", label="ERA5")
            ax.set_xticks(x)
            ax.set_xticklabels(["1-4天", "5-20天"])
            ax.set_ylabel("事件数")
        else:
            metrics = ["duration", "days_below_p20", "intensity"]
            g_vals = [diag["gleam_aux"][m]["median"] for m in metrics]
            e_vals = [diag["era5_aux"][m]["median"] for m in metrics]
            x = np.arange(len(metrics))
            w = 0.34
            ax.bar(x - w / 2, g_vals, width=w, color="#2b8cbe", label="GLEAM")
            ax.bar(x + w / 2, e_vals, width=w, color="#ef6548", label="ERA5")
            ax.set_xticks(x)
            ax.set_xticklabels(["持续时间", "低于P20", "烈度"])
            ax.set_ylabel("中位数")
        ax.set_title(diag["title_cn"], fontsize=12)
        ax.grid(True, axis="y", linestyle="--", alpha=0.25)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False, fontsize=10)
    fig.suptitle("GLEAM 与 ERA5 四情景结构差异", fontsize=18, y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.955])
    out_path = OUT_DIR / "multi_scenario_structural_comparison.png"
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def plot_difference_maps(diagnostics: list[dict]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(16, 9.5), dpi=320, subplot_kw={"projection": ccrs.PlateCarree()})
    axes = axes.ravel()
    all_abs = []
    for diag in diagnostics:
        diff = diag["gleam_total_grid"] - diag["era5_total_grid"]
        valid = diff[np.isfinite(diff)]
        if valid.size:
            all_abs.append(np.abs(valid))
    vmax = float(np.nanpercentile(np.concatenate(all_abs), 98)) if all_abs else 1.0
    for ax, diag in zip(axes, diagnostics):
        diff = (diag["gleam_total_grid"] - diag["era5_total_grid"]).astype(np.float32)
        diff = np.where(diff == 0, np.nan, diff)
        lat = diag["lat"]
        lon = diag["lon"]
        im = ax.imshow(
            diff,
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
        ax.add_feature(cfeature.COASTLINE.with_scale("110m"), linewidth=0.5, edgecolor="black", zorder=3)
        ax.set_extent([-180, 180, -60, 85], crs=ccrs.PlateCarree())
        gl = ax.gridlines(draw_labels=True, linewidth=0.25, color="gray", alpha=0.3, linestyle="--")
        gl.top_labels = False
        gl.right_labels = False
        gl.left_labels = True
        gl.bottom_labels = True
        gl.xlabel_style = {"size": 7}
        gl.ylabel_style = {"size": 7}
        ax.set_title(diag["title_cn"], fontsize=12)
        for key, picked in diag["typical_pixels"].items():
            ax.scatter(picked["lon"], picked["lat"], s=24, c="#111111", edgecolors="white", linewidths=0.6, transform=ccrs.PlateCarree(), zorder=4)
        cb = fig.colorbar(im, ax=ax, orientation="horizontal", pad=0.04, fraction=0.05)
        cb.ax.tick_params(labelsize=8)
    fig.suptitle("四情景每像元事件差值分布图（GLEAM - ERA5）", fontsize=18, y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.965])
    out_path = OUT_DIR / "multi_scenario_difference_maps.png"
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def plot_typical_pixels_for_scenario(diag: dict) -> Path:
    scenario: ScenarioConfig = diag["scenario"]
    contexts = {
        "GLEAM": DatasetContext("GLEAM", Path(scenario.gleam_daily_file), scenario.gleam_var, "#2b8cbe", f"GLEAM {scenario.soil_layer}"),
        "ERA5": DatasetContext("ERA5", Path(scenario.era5_daily_file), scenario.era5_var, "#ef6548", f"ERA5 {scenario.soil_layer}"),
    }
    fig, axes = plt.subplots(4, 1, figsize=(18, 14), dpi=300, sharex=False)
    for ax, (key, picked) in zip(axes, diag["typical_pixels"].items()):
        gleam_events = read_pixel_events(Path(scenario.gleam_event_file), picked["lat_idx"], picked["lon_idx"])
        era5_events = read_pixel_events(Path(scenario.era5_event_file), picked["lat_idx"], picked["lon_idx"])
        focus_events = select_focus_events(gleam_events, era5_events)
        gleam_series = load_pixel_series_with_thresholds(contexts["GLEAM"], picked["lat_idx"], picked["lon_idx"])
        era5_series = load_pixel_series_with_thresholds(contexts["ERA5"], picked["lat_idx"], picked["lon_idx"])
        start_idx, end_idx = choose_focus_window(
            focus_events,
            pad_days=50,
            series_len=len(gleam_series["dates"]),
            series_start_ord=gleam_series["dates"][0].toordinal(),
        )
        if end_idx <= start_idx:
            start_idx, end_idx = 0, min(len(gleam_series["dates"]) - 1, 729)
        xs = np.arange(start_idx, end_idx + 1)
        for event in gleam_events:
            start = event["start_ord"] - gleam_series["dates"][0].toordinal()
            end = event["end_ord"] - gleam_series["dates"][0].toordinal()
            if end < start_idx or start > end_idx:
                continue
            ax.axvspan(max(start_idx, start), min(end_idx, end), color="#2b8cbe", alpha=0.10)
        for event in era5_events:
            start = event["start_ord"] - era5_series["dates"][0].toordinal()
            end = event["end_ord"] - era5_series["dates"][0].toordinal()
            if end < start_idx or start > end_idx:
                continue
            ax.axvspan(max(start_idx, start), min(end_idx, end), color="#ef6548", alpha=0.08)
        ax.plot(xs, gleam_series["smoothed"][start_idx : end_idx + 1], color="#2b8cbe", linewidth=1.3, label="GLEAM 5日平滑")
        ax.plot(xs, gleam_series["p20"][start_idx : end_idx + 1], color="#2b8cbe", linewidth=0.9, linestyle="--", alpha=0.85, label="GLEAM P20")
        ax.plot(xs, gleam_series["p40"][start_idx : end_idx + 1], color="#2b8cbe", linewidth=0.9, linestyle=":", alpha=0.85, label="GLEAM P40")
        ax.plot(xs, era5_series["smoothed"][start_idx : end_idx + 1], color="#ef6548", linewidth=1.3, label="ERA5 5日平滑")
        ax.plot(xs, era5_series["p20"][start_idx : end_idx + 1], color="#ef6548", linewidth=0.9, linestyle="--", alpha=0.85, label="ERA5 P20")
        ax.plot(xs, era5_series["p40"][start_idx : end_idx + 1], color="#ef6548", linewidth=0.9, linestyle=":", alpha=0.85, label="ERA5 P40")
        tick_idx = np.linspace(start_idx, end_idx, 6, dtype=int)
        tick_idx = np.unique(tick_idx)
        ax.set_xticks(tick_idx)
        ax.set_xticklabels([gleam_series["dates"][idx].strftime("%Y-%m") for idx in tick_idx], rotation=20)
        ax.grid(True, linestyle="--", linewidth=0.35, alpha=0.3)
        ax.set_ylabel("土壤湿度")
        ax.set_title(
            f"{PIXEL_LABELS.get(key, key)} | {PIXEL_CN.get(key, key)} | "
            f"({picked['lat']:.3f}, {picked['lon']:.3f}) | GLEAM={picked['gleam_count']} ERA5={picked['era5_count']}",
            fontsize=11,
        )
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles[:6], labels[:6], loc="upper center", ncol=6, frameon=False, fontsize=9)
    fig.suptitle(f"{scenario.title_cn} 典型像元阈值诊断图", fontsize=17, y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    out_path = OUT_DIR / f"{scenario.key}_typical_pixels.png"
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def main() -> None:
    font_name = setup_chinese_font()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"中文字体: {font_name}")
    diagnostics = build_all_diagnostics()
    out1 = plot_summary_overview(diagnostics)
    print(f"已写出: {out1}")
    out2 = plot_structural_comparison(diagnostics)
    print(f"已写出: {out2}")
    out3 = plot_difference_maps(diagnostics)
    print(f"已写出: {out3}")
    for diag in diagnostics:
        out = plot_typical_pixels_for_scenario(diag)
        print(f"已写出: {out}")


if __name__ == "__main__":
    main()
