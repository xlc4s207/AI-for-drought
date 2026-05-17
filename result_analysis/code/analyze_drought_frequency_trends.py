#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import csv
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import rcParams
from matplotlib.colors import SymLogNorm
import netCDF4 as nc
import numpy as np
from scipy.stats import t as t_dist


BASE_DIR = "/home/xulc/flash_drought"
PERF_DIR = os.path.join(BASE_DIR, "process/result_analysis/performance")
MAP_DIR = os.path.join(PERF_DIR, "frequency_trend_maps")
PLOT_DIR = os.path.join(PERF_DIR, "frequency_trend_plots")

DEFAULT_SOIL_DIRS = [
    "/home/xulc/flash_drought/gleam/clip_result/SMs_5.3",
    "/home/xulc/flash_drought/gleam/clip_result/SMrz_5.3",
]

DROUGHT_FILES = {
    "flash": "flash_drought_events_v5.nc",
    "nonflash": "nonflash_drought_events_v5.nc",
}

SCENARIO_CN = {
    ("SMs", "flash"): "SMs-骤旱",
    ("SMs", "nonflash"): "SMs-非骤旱",
    ("SMrz", "flash"): "SMrz-骤旱",
    ("SMrz", "nonflash"): "SMrz-非骤旱",
}


@dataclass(frozen=True)
class Scenario:
    soil_layer: str
    drought_type: str
    input_path: str
    output_path: str


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


def build_scenarios(soil_dirs: Iterable[str]) -> List[Scenario]:
    scenarios: List[Scenario] = []
    os.makedirs(MAP_DIR, exist_ok=True)
    for soil_dir in soil_dirs:
        soil_layer = os.path.basename(soil_dir).split("_")[0]
        for drought_type, filename in DROUGHT_FILES.items():
            scenarios.append(
                Scenario(
                    soil_layer=soil_layer,
                    drought_type=drought_type,
                    input_path=os.path.join(soil_dir, filename),
                    output_path=os.path.join(
                        MAP_DIR,
                        f"drought_frequency_trend_{soil_layer}_{drought_type}_1980_2024.nc",
                    ),
                )
            )
    return scenarios


def filled_float_array(var_obj, slc) -> np.ndarray:
    arr = var_obj[slc]
    if isinstance(arr, np.ma.MaskedArray):
        arr = arr.astype(np.float64).filled(np.nan)
    else:
        arr = np.asarray(arr, dtype=np.float64)
    fill = getattr(var_obj, "_FillValue", None)
    if fill is not None:
        arr[arr == fill] = np.nan
    return arr


def accumulate_annual_event_counts(drought_start_year: np.ndarray, year_min: int, year_max: int) -> np.ndarray:
    n_years = year_max - year_min + 1
    n_events, nlat, nlon = drought_start_year.shape
    flat = drought_start_year.reshape(n_events, nlat * nlon)
    counts = np.zeros((n_years, flat.shape[1]), dtype=np.int16)

    for event_idx in range(n_events):
        event_years = flat[event_idx]
        valid = np.isfinite(event_years) & (event_years >= year_min) & (event_years <= year_max)
        if not np.any(valid):
            continue
        cols = np.nonzero(valid)[0]
        year_idx = event_years[valid].astype(np.int64) - year_min
        np.add.at(counts, (year_idx, cols), 1)

    return counts.reshape(n_years, nlat, nlon)


def calc_pvalue_from_r2(slope: np.ndarray, r2: np.ndarray, n_obs: int, valid: np.ndarray) -> np.ndarray:
    pvalue = np.full(slope.shape, np.nan, dtype=np.float64)
    if n_obs <= 2:
        return pvalue
    r = np.sqrt(np.clip(r2, 0.0, 1.0))
    r = np.sign(slope) * r
    df = float(n_obs - 2)
    denom = np.maximum(1.0 - r * r, 1e-12)
    t_val = np.abs(r) * np.sqrt(df / denom)
    pvalue[valid] = 2.0 * t_dist.sf(t_val[valid], df)
    return pvalue


def compute_frequency_regression(
    year_axis: np.ndarray,
    annual_counts: np.ndarray,
    total_events: np.ndarray,
    min_total_events: int,
) -> Dict[str, np.ndarray]:
    y = np.asarray(annual_counts, dtype=np.float64)
    x = np.asarray(year_axis, dtype=np.float64)
    n_obs = x.size
    sx = float(np.sum(x))
    sxx = float(np.sum(x * x))
    denom = n_obs * sxx - sx * sx

    sy = np.sum(y, axis=0)
    syy = np.sum(y * y, axis=0)
    sxy = np.tensordot(x, y, axes=(0, 0))

    enough = np.isfinite(total_events) & (total_events >= float(min_total_events))
    slope = np.full(total_events.shape, np.nan, dtype=np.float64)
    intercept = np.full(total_events.shape, np.nan, dtype=np.float64)
    r2 = np.full(total_events.shape, np.nan, dtype=np.float64)
    mean = np.full(total_events.shape, np.nan, dtype=np.float64)

    if denom != 0.0:
        slope[enough] = (n_obs * sxy[enough] - sx * sy[enough]) / denom
        intercept[enough] = (sy[enough] - slope[enough] * sx) / float(n_obs)
        mean[enough] = sy[enough] / float(n_obs)

        r_num = n_obs * sxy - sx * sy
        r_den = denom * (n_obs * syy - sy * sy)
        good_r = enough & np.isfinite(r_den) & (r_den > 0.0)
        r = np.full(total_events.shape, np.nan, dtype=np.float64)
        r[good_r] = r_num[good_r] / np.sqrt(r_den[good_r])
        r2[good_r] = r[good_r] * r[good_r]

    pvalue = calc_pvalue_from_r2(slope=slope, r2=r2, n_obs=n_obs, valid=enough & np.isfinite(r2))
    sig_mask = enough & np.isfinite(pvalue) & (pvalue < 0.05)
    sig_slope = np.where(sig_mask, slope, np.nan)

    return {
        "slope": slope,
        "intercept": intercept,
        "r2": r2,
        "mean": mean,
        "pvalue": pvalue,
        "sig_mask": sig_mask.astype(np.int8),
        "sig_slope": sig_slope,
    }


def write_2d(var_obj, data: np.ndarray, lat_slice: slice) -> None:
    var_obj[lat_slice, :] = data.astype(var_obj.dtype, copy=False)


def analyze_scenario(
    scenario: Scenario,
    year_min: int,
    year_max: int,
    min_total_events: int,
    lat_chunk: int,
    overwrite: bool,
    lat_start: int,
    lat_stop: int | None,
) -> Dict[str, np.ndarray]:
    if not os.path.exists(scenario.input_path):
        raise FileNotFoundError(f"Missing input: {scenario.input_path}")
    if os.path.exists(scenario.output_path) and not overwrite:
        raise FileExistsError(f"Output exists: {scenario.output_path}")
    if os.path.exists(scenario.output_path):
        os.remove(scenario.output_path)

    year_axis = np.arange(year_min, year_max + 1, dtype=np.float64)
    annual_global_events = np.zeros(year_axis.size, dtype=np.float64)
    total_valid_pixels = 0

    with nc.Dataset(scenario.input_path, "r") as src, nc.Dataset(scenario.output_path, "w", format="NETCDF4") as dst:
        nlat = len(src.dimensions["lat"])
        nlon = len(src.dimensions["lon"])

        dst.createDimension("lat", nlat)
        dst.createDimension("lon", nlon)
        lat_var = dst.createVariable("lat", "f4", ("lat",))
        lon_var = dst.createVariable("lon", "f4", ("lon",))
        lat_var[:] = src.variables["lat"][:]
        lon_var[:] = src.variables["lon"][:]
        lat_var.units = getattr(src.variables["lat"], "units", "degrees_north")
        lon_var.units = getattr(src.variables["lon"], "units", "degrees_east")

        out_vars = {
            "frequency_slope": dst.createVariable("frequency_slope", "f4", ("lat", "lon"), zlib=True, complevel=4, fill_value=np.float32(np.nan)),
            "frequency_intercept": dst.createVariable("frequency_intercept", "f4", ("lat", "lon"), zlib=True, complevel=4, fill_value=np.float32(np.nan)),
            "frequency_r2": dst.createVariable("frequency_r2", "f4", ("lat", "lon"), zlib=True, complevel=4, fill_value=np.float32(np.nan)),
            "frequency_pvalue": dst.createVariable("frequency_pvalue", "f4", ("lat", "lon"), zlib=True, complevel=4, fill_value=np.float32(np.nan)),
            "frequency_sig_mask_p005": dst.createVariable("frequency_sig_mask_p005", "i1", ("lat", "lon"), zlib=True, complevel=4, fill_value=np.int8(-1)),
            "frequency_sig_slope_p005": dst.createVariable("frequency_sig_slope_p005", "f4", ("lat", "lon"), zlib=True, complevel=4, fill_value=np.float32(np.nan)),
            "mean_annual_frequency": dst.createVariable("mean_annual_frequency", "f4", ("lat", "lon"), zlib=True, complevel=4, fill_value=np.float32(np.nan)),
            "total_events": dst.createVariable("total_events", "f4", ("lat", "lon"), zlib=True, complevel=4, fill_value=np.float32(np.nan)),
        }

        out_vars["frequency_slope"].units = "annual event count change per year"
        out_vars["frequency_intercept"].units = "annual event count"
        out_vars["frequency_r2"].units = "1"
        out_vars["frequency_pvalue"].units = "1"
        out_vars["frequency_sig_mask_p005"].long_name = "1 significant, 0 not significant, -1 invalid"
        out_vars["frequency_sig_slope_p005"].units = "annual event count change per year"
        out_vars["mean_annual_frequency"].units = "events per year"
        out_vars["total_events"].units = "count"

        dst.title = "Per-pixel drought annual frequency trend"
        dst.source = getattr(src, "source", "")
        dst.algorithm = getattr(src, "algorithm", "")
        dst.period = f"{year_min}-{year_max}"
        dst.min_total_events = min_total_events
        dst.drought_type = scenario.drought_type
        dst.soil_layer = scenario.soil_layer

        start_idx = max(0, lat_start)
        stop_idx = nlat if lat_stop is None else min(nlat, lat_stop)

        for lat0 in range(start_idx, stop_idx, lat_chunk):
            lat1 = min(lat0 + lat_chunk, stop_idx)
            lat_slc = slice(lat0, lat1)

            years = filled_float_array(src.variables["drought_start_year"], (slice(None), lat_slc, slice(None)))
            total_events = filled_float_array(src.variables["event_count"], (lat_slc, slice(None)))
            annual_counts = accumulate_annual_event_counts(years, year_min=year_min, year_max=year_max)
            stat = compute_frequency_regression(
                year_axis=year_axis,
                annual_counts=annual_counts,
                total_events=total_events,
                min_total_events=min_total_events,
            )

            valid_pixels = np.isfinite(total_events) & (total_events >= float(min_total_events))
            total_valid_pixels += int(np.sum(valid_pixels))
            annual_global_events += annual_counts[:, valid_pixels].sum(axis=1)

            write_2d(out_vars["frequency_slope"], stat["slope"], lat_slc)
            write_2d(out_vars["frequency_intercept"], stat["intercept"], lat_slc)
            write_2d(out_vars["frequency_r2"], stat["r2"], lat_slc)
            write_2d(out_vars["frequency_pvalue"], stat["pvalue"], lat_slc)
            mask_out = np.full(valid_pixels.shape, -1, dtype=np.int8)
            mask_out[valid_pixels] = 0
            mask_out[stat["sig_mask"] > 0] = 1
            write_2d(out_vars["frequency_sig_mask_p005"], mask_out, lat_slc)
            write_2d(out_vars["frequency_sig_slope_p005"], stat["sig_slope"], lat_slc)
            write_2d(out_vars["mean_annual_frequency"], stat["mean"], lat_slc)
            write_2d(out_vars["total_events"], total_events, lat_slc)
            print(f"[{scenario.soil_layer}-{scenario.drought_type}] processed lat rows {lat0}:{lat1}")

    mean_annual_frequency = (
        annual_global_events / float(total_valid_pixels)
        if total_valid_pixels > 0
        else np.full(year_axis.size, np.nan, dtype=np.float64)
    )
    return {
        "year": year_axis,
        "annual_global_events": annual_global_events,
        "mean_annual_frequency": mean_annual_frequency,
        "valid_pixels": np.array([total_valid_pixels], dtype=np.int64),
    }


def summarize_scenario(scenario: Scenario) -> Dict[str, float]:
    with nc.Dataset(scenario.output_path, "r") as ds:
        slope = filled_float_array(ds.variables["frequency_slope"], (slice(None), slice(None)))
        pvalue = filled_float_array(ds.variables["frequency_pvalue"], (slice(None), slice(None)))
        total_events = filled_float_array(ds.variables["total_events"], (slice(None), slice(None)))
        mean_annual_frequency = filled_float_array(ds.variables["mean_annual_frequency"], (slice(None), slice(None)))

    valid = np.isfinite(slope) & np.isfinite(total_events)
    sig = valid & np.isfinite(pvalue) & (pvalue < 0.05)
    s = slope[valid]
    sig_s = slope[sig]
    mean_freq = mean_annual_frequency[valid]

    return {
        "soil_layer": scenario.soil_layer,
        "drought_type": scenario.drought_type,
        "scenario_cn": SCENARIO_CN[(scenario.soil_layer, scenario.drought_type)],
        "valid_pixels": int(np.sum(valid)),
        "valid_ratio": float(np.mean(valid)),
        "mean_slope": float(np.nanmean(s)) if s.size else np.nan,
        "median_slope": float(np.nanmedian(s)) if s.size else np.nan,
        "positive_ratio": float(np.mean(s > 0)) if s.size else np.nan,
        "negative_ratio": float(np.mean(s < 0)) if s.size else np.nan,
        "sig_pixels": int(np.sum(sig)),
        "sig_ratio_in_valid": float(np.sum(sig) / np.sum(valid)) if np.sum(valid) > 0 else np.nan,
        "sig_mean_slope": float(np.nanmean(sig_s)) if sig_s.size else np.nan,
        "sig_positive_ratio": float(np.mean(sig_s > 0)) if sig_s.size else np.nan,
        "sig_negative_ratio": float(np.mean(sig_s < 0)) if sig_s.size else np.nan,
        "mean_annual_frequency": float(np.nanmean(mean_freq)) if mean_freq.size else np.nan,
    }


def write_csv(path: str, rows: List[Dict[str, float]], headers: List[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def save_map_figure(scenarios: List[Scenario]) -> str:
    os.makedirs(PLOT_DIR, exist_ok=True)
    font_name = setup_chinese_font()
    print(f"中文字体: {font_name}")

    arrays = []
    lon = None
    lat = None
    for scenario in scenarios:
        with nc.Dataset(scenario.output_path, "r") as ds:
            if lon is None:
                lon = filled_float_array(ds.variables["lon"], slice(None))
                lat = filled_float_array(ds.variables["lat"], slice(None))
            arrays.append(filled_float_array(ds.variables["frequency_sig_slope_p005"], (slice(None), slice(None))))

    assert lon is not None and lat is not None
    finite_arrays = [a[np.isfinite(a)] for a in arrays if np.any(np.isfinite(a))]
    if finite_arrays:
        vmax = np.nanpercentile(np.abs(np.concatenate(finite_arrays)), 90)
    else:
        vmax = np.nan
    if not np.isfinite(vmax) or vmax <= 0:
        vmax = 1.0
    norm = SymLogNorm(linthresh=max(vmax * 0.08, 1e-8), linscale=0.9, vmin=-vmax, vmax=vmax, base=10)

    fig = plt.figure(figsize=(16, 8), dpi=260)
    gs = fig.add_gridspec(2, 3, width_ratios=[1, 1, 0.045], wspace=0.03, hspace=0.08)
    stride = 3
    lon_plot = lon[::stride]
    lat_plot = lat[::stride]
    im = None

    for idx, scenario in enumerate(scenarios):
        row, col = divmod(idx, 2)
        ax = fig.add_subplot(gs[row, col], projection=ccrs.PlateCarree())
        arr = arrays[idx][::stride, ::stride]
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
        gl = ax.gridlines(draw_labels=True, linewidth=0.3, color="gray", alpha=0.35, linestyle="--")
        gl.top_labels = False
        gl.right_labels = False
        gl.left_labels = col == 0
        gl.bottom_labels = row == 1
        gl.xlabel_style = {"size": 8}
        gl.ylabel_style = {"size": 8}
        ax.set_title(SCENARIO_CN[(scenario.soil_layer, scenario.drought_type)], fontsize=12, pad=4)

    for idx in range(len(scenarios), 4):
        row, col = divmod(idx, 2)
        ax = fig.add_subplot(gs[row, col])
        ax.axis("off")

    cax = fig.add_subplot(gs[:, 2])
    assert im is not None
    cb = fig.colorbar(im, cax=cax, orientation="vertical")
    cb.set_label("频率趋势斜率（事件数/年/年，p<0.05）", fontsize=10)
    cb.ax.tick_params(labelsize=8)
    fig.suptitle("四种情景干旱发生频率显著趋势图（1980-2024，p<0.05）", fontsize=16, y=0.98)

    out_png = os.path.join(PLOT_DIR, "drought_frequency_slope_significant_p005_2x2.png")
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)
    return out_png


def save_timeseries_plot(rows: List[Dict[str, float]]) -> str:
    os.makedirs(PLOT_DIR, exist_ok=True)
    setup_chinese_font()
    fig, ax = plt.subplots(figsize=(10, 5), dpi=220)
    for scenario_cn, group in _group_timeseries(rows).items():
        years = [r["year"] for r in group]
        means = [r["mean_annual_frequency"] for r in group]
        ax.plot(years, means, linewidth=1.8, label=scenario_cn)

    ax.set_xlabel("年份")
    ax.set_ylabel("平均年发生频率（事件数/年）")
    ax.set_title("四种情景全球平均年发生频率时间序列")
    ax.grid(linestyle="--", alpha=0.3)
    ax.legend(frameon=False)
    out_png = os.path.join(PLOT_DIR, "drought_frequency_global_mean_timeseries.png")
    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)
    return out_png


def _group_timeseries(rows: List[Dict[str, float]]) -> Dict[str, List[Dict[str, float]]]:
    grouped: Dict[str, List[Dict[str, float]]] = {}
    for row in rows:
        grouped.setdefault(row["scenario_cn"], []).append(row)
    for key in grouped:
        grouped[key] = sorted(grouped[key], key=lambda x: x["year"])
    return grouped


def write_markdown_summary(path: str, summary_rows: List[Dict[str, float]], map_path: str, ts_path: str) -> None:
    idx = {(r["soil_layer"], r["drought_type"]): r for r in summary_rows}
    with open(path, "w", encoding="utf-8") as f:
        f.write("# 干旱发生频率变化趋势报告（1980-2024）\n\n")
        f.write("## 分析口径\n")
        f.write("- 频率定义：每个像元每年的事件数。\n")
        f.write("- 趋势方法：对 1980-2024 的逐年事件数做 OLS 线性趋势。\n")
        f.write("- 有效像元阈值：总事件数 >= 5。\n")
        f.write("- 显著性阈值：p < 0.05。\n\n")

        f.write("## 全球总体结论\n")
        for row in summary_rows:
            direction = "增加" if row["mean_slope"] > 0 else "减少"
            f.write(
                f"- {row['scenario_cn']}：平均斜率 {row['mean_slope']:.6g}，"
                f"中位数 {row['median_slope']:.6g}，"
                f"正趋势像元占比 {row['positive_ratio'] * 100:.1f}%，"
                f"显著像元占有效像元 {row['sig_ratio_in_valid'] * 100:.1f}%，"
                f"整体以频率{direction}为主。\n"
            )
        f.write("\n")

        f.write("## 情景对比\n")
        for soil in ["SMs", "SMrz"]:
            if (soil, "flash") not in idx or (soil, "nonflash") not in idx:
                continue
            flash = idx[(soil, "flash")]
            nonflash = idx[(soil, "nonflash")]
            f.write(
                f"- {soil}：非骤旱平均斜率 {nonflash['mean_slope']:.6g}，骤旱平均斜率 {flash['mean_slope']:.6g}；"
                f"非骤旱显著像元占比 {nonflash['sig_ratio_in_valid'] * 100:.1f}%，骤旱 {flash['sig_ratio_in_valid'] * 100:.1f}%。\n"
            )
        f.write("\n")

        f.write("## 输出文件\n")
        f.write(f"- 显著趋势图：`{map_path}`\n")
        f.write(f"- 全球时间序列图：`{ts_path}`\n")
        f.write("- 单情景频率趋势 NetCDF：`process/result_analysis/performance/frequency_trend_maps/`\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze drought-event annual frequency trends.")
    parser.add_argument("--soil-dirs", nargs="+", default=DEFAULT_SOIL_DIRS)
    parser.add_argument("--year-min", type=int, default=1980)
    parser.add_argument("--year-max", type=int, default=2024)
    parser.add_argument("--min-total-events", type=int, default=5)
    parser.add_argument("--lat-chunk", type=int, default=50)
    parser.add_argument("--lat-start", type=int, default=0)
    parser.add_argument("--lat-stop", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scenarios = build_scenarios(args.soil_dirs)
    os.makedirs(PERF_DIR, exist_ok=True)
    os.makedirs(MAP_DIR, exist_ok=True)
    os.makedirs(PLOT_DIR, exist_ok=True)

    print("Scenarios:")
    for scenario in scenarios:
        print(f"  - {scenario.soil_layer}-{scenario.drought_type}: {scenario.input_path} -> {scenario.output_path}")
    if args.dry_run:
        return

    timeseries_rows: List[Dict[str, float]] = []
    for scenario in scenarios:
        result = analyze_scenario(
            scenario=scenario,
            year_min=args.year_min,
            year_max=args.year_max,
            min_total_events=args.min_total_events,
            lat_chunk=args.lat_chunk,
            overwrite=args.overwrite,
            lat_start=args.lat_start,
            lat_stop=args.lat_stop,
        )
        for year, total_events, mean_freq in zip(result["year"], result["annual_global_events"], result["mean_annual_frequency"]):
            timeseries_rows.append(
                {
                    "soil_layer": scenario.soil_layer,
                    "drought_type": scenario.drought_type,
                    "scenario_cn": SCENARIO_CN[(scenario.soil_layer, scenario.drought_type)],
                    "year": int(year),
                    "global_event_count": float(total_events),
                    "mean_annual_frequency": float(mean_freq),
                }
            )

    summary_rows = [summarize_scenario(s) for s in scenarios]
    summary_csv = os.path.join(PERF_DIR, "drought_frequency_trend_summary_1980_2024.csv")
    timeseries_csv = os.path.join(PERF_DIR, "drought_frequency_timeseries_1980_2024.csv")
    summary_md = os.path.join(PERF_DIR, "drought_frequency_trend_summary_1980_2024.md")

    write_csv(
        summary_csv,
        summary_rows,
        [
            "soil_layer",
            "drought_type",
            "scenario_cn",
            "valid_pixels",
            "valid_ratio",
            "mean_slope",
            "median_slope",
            "positive_ratio",
            "negative_ratio",
            "sig_pixels",
            "sig_ratio_in_valid",
            "sig_mean_slope",
            "sig_positive_ratio",
            "sig_negative_ratio",
            "mean_annual_frequency",
        ],
    )
    write_csv(
        timeseries_csv,
        timeseries_rows,
        ["soil_layer", "drought_type", "scenario_cn", "year", "global_event_count", "mean_annual_frequency"],
    )

    map_path = save_map_figure(scenarios)
    ts_path = save_timeseries_plot(timeseries_rows)
    write_markdown_summary(summary_md, summary_rows, map_path, ts_path)

    print(f"Wrote: {summary_csv}")
    print(f"Wrote: {timeseries_csv}")
    print(f"Wrote: {summary_md}")
    print(f"Wrote: {map_path}")
    print(f"Wrote: {ts_path}")


if __name__ == "__main__":
    main()
