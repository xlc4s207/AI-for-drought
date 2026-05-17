#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generate significance-filtered trend maps (p < 0.05) and continent statistics.

Inputs:
  - Existing trend products:
    <soil_dir>/trend_analysis/<drought_type>/pixel_trend_metrics_v1.nc

Outputs:
  - Per scenario:
    <soil_dir>/trend_analysis/<drought_type>/pixel_trend_significance_v1.nc
    <soil_dir>/trend_analysis/<drought_type>/plots/*_sig_trend_p005.png
  - Global summary:
    /home/xulc/flash_drought/process/result_analysis/performance/significant_trend_maps/*
    /home/xulc/flash_drought/process/result_analysis/performance/continent_significant_trend_stats.csv
    /home/xulc/flash_drought/process/result_analysis/performance/continent_significant_trend_stats.md
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import rcParams
import netCDF4 as nc
import numpy as np
import pandas as pd
from scipy.stats import t as t_dist


BASE_DIR = "/home/xulc/flash_drought"
PERF_DIR = os.path.join(BASE_DIR, "process/result_analysis/performance")
MAP_DIR = os.path.join(PERF_DIR, "significant_trend_maps")
os.makedirs(PERF_DIR, exist_ok=True)
os.makedirs(MAP_DIR, exist_ok=True)

P_THRESHOLD = 0.05
MIN_EVENTS = 5

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

CONTINENT_CODES = {
    1: "北美洲",
    2: "南美洲",
    3: "欧洲",
    4: "非洲",
    5: "亚洲",
    6: "大洋洲",
    7: "南极洲",
}


@dataclass(frozen=True)
class Scenario:
    soil_layer: str
    drought_type: str
    trend_path: str
    output_nc: str
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


def build_scenarios() -> List[Scenario]:
    specs = [
        ("SMs", "flash", os.path.join(BASE_DIR, "gleam/clip_result/SMs_5.3/trend_analysis/flash")),
        ("SMs", "nonflash", os.path.join(BASE_DIR, "gleam/clip_result/SMs_5.3/trend_analysis/nonflash")),
        ("SMrz", "flash", os.path.join(BASE_DIR, "gleam/clip_result/SMrz_5.3/trend_analysis/flash")),
        ("SMrz", "nonflash", os.path.join(BASE_DIR, "gleam/clip_result/SMrz_5.3/trend_analysis/nonflash")),
    ]
    scenarios: List[Scenario] = []
    for soil, dtype, folder in specs:
        scenarios.append(
            Scenario(
                soil_layer=soil,
                drought_type=dtype,
                trend_path=os.path.join(folder, "pixel_trend_metrics_v1.nc"),
                output_nc=os.path.join(folder, "pixel_trend_significance_v1.nc"),
                plot_dir=os.path.join(folder, "plots"),
            )
        )
    return scenarios


def _to_float(a) -> np.ndarray:
    if hasattr(a, "filled"):
        a = a.filled(np.nan)
    return np.asarray(a, dtype=np.float64)


def calc_pvalue_from_r2(slope: np.ndarray, r2: np.ndarray, n_events: np.ndarray) -> np.ndarray:
    pvalue = np.full(slope.shape, np.nan, dtype=np.float64)

    valid = (
        np.isfinite(slope)
        & np.isfinite(r2)
        & np.isfinite(n_events)
        & (n_events > 2.0)
        & (r2 >= 0.0)
        & (r2 <= 1.0)
    )
    if not np.any(valid):
        return pvalue

    r = np.sqrt(np.clip(r2, 0.0, 1.0))
    r = np.sign(slope) * r
    df = n_events - 2.0
    denom = np.maximum(1.0 - r * r, 1e-12)
    tval = np.abs(r) * np.sqrt(df / denom)
    pvalue[valid] = 2.0 * t_dist.sf(tval[valid], df[valid])
    return pvalue


def _normalize_lon(lon_1d: np.ndarray) -> np.ndarray:
    lon = lon_1d.copy()
    lon = ((lon + 180.0) % 360.0) - 180.0
    return lon


def build_continent_code(lat_1d: np.ndarray, lon_1d: np.ndarray) -> np.ndarray:
    lat2d, lon2d = np.meshgrid(lat_1d, _normalize_lon(lon_1d), indexing="ij")
    code = np.zeros(lat2d.shape, dtype=np.int8)
    unassigned = np.ones(lat2d.shape, dtype=bool)

    def assign(mask: np.ndarray, cid: int) -> None:
        nonlocal unassigned
        m = mask & unassigned
        code[m] = cid
        unassigned[m] = False

    antarctica = lat2d < -60.0
    north_america = (lon2d >= -170.0) & (lon2d <= -50.0) & (lat2d >= 7.0) & (lat2d <= 84.0)
    south_america = (lon2d >= -92.0) & (lon2d <= -30.0) & (lat2d >= -60.0) & (lat2d < 15.0)
    europe = (lon2d >= -25.0) & (lon2d <= 60.0) & (lat2d >= 35.0) & (lat2d <= 72.0)
    africa = (lon2d >= -20.0) & (lon2d <= 55.0) & (lat2d >= -35.0) & (lat2d < 38.0)
    asia = (
        ((lon2d >= 25.0) & (lon2d <= 180.0) & (lat2d >= 5.0) & (lat2d <= 82.0))
        | ((lon2d >= 60.0) & (lon2d <= 150.0) & (lat2d >= -10.0) & (lat2d < 5.0))
        | ((lon2d <= -170.0) & (lat2d >= 50.0) & (lat2d <= 72.0))
    )
    oceania = (lon2d >= 110.0) & (lon2d <= 180.0) & (lat2d >= -50.0) & (lat2d < 10.0)

    assign(north_america, 1)
    assign(south_america, 2)
    assign(europe, 3)
    assign(africa, 4)
    assign(asia, 5)
    assign(oceania, 6)
    assign(antarctica, 7)
    return code


def _finite_percentile_abs(a: np.ndarray, q: float = 98.0) -> float:
    v = np.abs(a[np.isfinite(a)])
    if v.size == 0:
        return 1.0
    p = float(np.nanpercentile(v, q))
    return p if np.isfinite(p) and p > 0 else 1.0


def save_single_map(
    lon: np.ndarray,
    lat: np.ndarray,
    sig_slope: np.ndarray,
    title: str,
    out_png: str,
    vmax: float | None = None,
) -> None:
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    vmax_local = _finite_percentile_abs(sig_slope) if vmax is None else vmax

    fig, ax = plt.subplots(figsize=(12, 5), dpi=300)
    im = ax.pcolormesh(
        lon,
        lat,
        sig_slope,
        shading="auto",
        cmap="RdBu_r",
        vmin=-vmax_local,
        vmax=vmax_local,
    )
    ax.set_xlim(-180, 180)
    ax.set_ylim(-60, 90)
    ax.set_xlabel("经度")
    ax.set_ylabel("纬度")
    ax.set_title(title)
    ax.grid(linestyle="--", linewidth=0.4, alpha=0.35)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label("趋势斜率（单位/年，p<0.05）")
    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def save_metric_panel(
    lon: np.ndarray,
    lat: np.ndarray,
    metric: str,
    sig_by_scenario: Dict[Tuple[str, str], np.ndarray],
) -> str:
    out_png = os.path.join(MAP_DIR, f"{metric}_significant_trend_p005_2x2.png")

    all_vals = np.concatenate(
        [v[np.isfinite(v)] for v in sig_by_scenario.values() if np.any(np.isfinite(v))]
    ) if any(np.any(np.isfinite(v)) for v in sig_by_scenario.values()) else np.array([0.0])
    vmax = _finite_percentile_abs(all_vals, q=98.0)

    order = [("SMs", "flash"), ("SMs", "nonflash"), ("SMrz", "flash"), ("SMrz", "nonflash")]
    fig, axes = plt.subplots(2, 2, figsize=(16, 8), dpi=300, sharex=True, sharey=True)

    for ax, key in zip(axes.flat, order):
        arr = sig_by_scenario[key]
        im = ax.pcolormesh(
            lon,
            lat,
            arr,
            shading="auto",
            cmap="RdBu_r",
            vmin=-vmax,
            vmax=vmax,
        )
        ax.set_xlim(-180, 180)
        ax.set_ylim(-60, 90)
        ax.set_title(SCENARIO_CN[key], fontsize=11)
        ax.grid(linestyle="--", linewidth=0.35, alpha=0.3)

    for ax in axes[1, :]:
        ax.set_xlabel("经度")
    for ax in axes[:, 0]:
        ax.set_ylabel("纬度")

    cb = fig.colorbar(im, ax=axes.ravel().tolist(), fraction=0.018, pad=0.015)
    cb.set_label("趋势斜率（单位/年，p<0.05）")
    fig.suptitle(f"{METRIC_CN[metric]} 显著趋势图（p<0.05）", fontsize=15, y=0.98)
    fig.tight_layout(rect=[0.02, 0.02, 0.98, 0.95])
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)
    return out_png


def analyze() -> None:
    font_name = setup_chinese_font()
    print(f"中文字体: {font_name}")

    scenarios = build_scenarios()
    for s in scenarios:
        if not os.path.exists(s.trend_path):
            raise FileNotFoundError(f"Missing trend file: {s.trend_path}")

    sig_data_for_panel: Dict[str, Dict[Tuple[str, str], np.ndarray]] = {
        m: {} for m in METRICS
    }
    continent_rows: List[Dict] = []

    lat_cache: np.ndarray | None = None
    lon_cache: np.ndarray | None = None
    continent_code_cache: np.ndarray | None = None

    for s in scenarios:
        os.makedirs(s.plot_dir, exist_ok=True)
        if os.path.exists(s.output_nc):
            os.remove(s.output_nc)

        with nc.Dataset(s.trend_path, "r") as src, nc.Dataset(s.output_nc, "w", format="NETCDF4") as dst:
            lat = _to_float(src.variables["lat"][:]).astype(np.float32)
            lon = _to_float(src.variables["lon"][:]).astype(np.float32)

            if lat_cache is None:
                lat_cache = lat.copy()
                lon_cache = lon.copy()
                continent_code_cache = build_continent_code(lat_cache, lon_cache)

            dst.createDimension("lat", lat.size)
            dst.createDimension("lon", lon.size)
            lat_var = dst.createVariable("lat", "f4", ("lat",))
            lon_var = dst.createVariable("lon", "f4", ("lon",))
            lat_var[:] = lat
            lon_var[:] = lon
            lat_var.units = "degrees_north"
            lon_var.units = "degrees_east"

            dst.title = "Per-pixel trend significance derived from pixel_trend_metrics_v1"
            dst.source_trend_file = s.trend_path
            dst.p_threshold = P_THRESHOLD
            dst.min_events_rule = MIN_EVENTS
            dst.notes = "p-value is computed from slope sign + R2 + n_events using two-sided t test."

            for metric in METRICS:
                slope = _to_float(src.variables[f"{metric}_slope"][:])
                r2 = _to_float(src.variables[f"{metric}_r2"][:])
                n_events = _to_float(src.variables[f"{metric}_n_events"][:])

                pvalue = calc_pvalue_from_r2(slope=slope, r2=r2, n_events=n_events)
                valid = np.isfinite(slope) & np.isfinite(n_events) & (n_events >= MIN_EVENTS)
                sig_mask = valid & np.isfinite(pvalue) & (pvalue < P_THRESHOLD)
                sig_slope = np.where(sig_mask, slope, np.nan)

                p_var = dst.createVariable(
                    f"{metric}_pvalue", "f4", ("lat", "lon"), zlib=True, complevel=4, fill_value=np.float32(np.nan)
                )
                m_var = dst.createVariable(
                    f"{metric}_sig_mask_p005", "i1", ("lat", "lon"), zlib=True, complevel=4, fill_value=np.int8(-1)
                )
                s_var = dst.createVariable(
                    f"{metric}_sig_slope_p005", "f4", ("lat", "lon"), zlib=True, complevel=4, fill_value=np.float32(np.nan)
                )
                p_var.units = "1"
                s_var.units = "units per year"
                m_var.long_name = "1: significant (p<0.05), 0: not significant, -1: invalid"

                p_var[:, :] = pvalue.astype(np.float32)
                mask_out = np.full(sig_mask.shape, -1, dtype=np.int8)
                mask_out[valid] = 0
                mask_out[sig_mask] = 1
                m_var[:, :] = mask_out
                s_var[:, :] = sig_slope.astype(np.float32)

                scenario_key = (s.soil_layer, s.drought_type)
                sig_data_for_panel[metric][scenario_key] = sig_slope

                save_single_map(
                    lon=lon,
                    lat=lat,
                    sig_slope=sig_slope,
                    title=f"{SCENARIO_CN[scenario_key]} | {METRIC_CN[metric]} 显著趋势（p<0.05）",
                    out_png=os.path.join(s.plot_dir, f"{metric}_sig_trend_p005.png"),
                )

                assert continent_code_cache is not None
                for cid, cname in CONTINENT_CODES.items():
                    c_mask = continent_code_cache == cid
                    c_valid = valid & c_mask
                    c_sig = sig_mask & c_mask
                    vals = slope[c_sig]
                    vals = vals[np.isfinite(vals)]

                    n_valid = int(np.sum(c_valid))
                    n_sig = int(np.sum(c_sig))
                    continent_rows.append(
                        {
                            "soil_layer": s.soil_layer,
                            "drought_type": s.drought_type,
                            "scenario_cn": SCENARIO_CN[scenario_key],
                            "metric": metric,
                            "metric_cn": METRIC_CN[metric],
                            "continent_code": cid,
                            "continent_cn": cname,
                            "n_valid_pixels": n_valid,
                            "n_sig_pixels": n_sig,
                            "sig_ratio_in_valid": (n_sig / n_valid) if n_valid > 0 else np.nan,
                            "sig_mean_slope": float(np.nanmean(vals)) if vals.size > 0 else np.nan,
                            "sig_median_slope": float(np.nanmedian(vals)) if vals.size > 0 else np.nan,
                            "sig_positive_ratio": float(np.mean(vals > 0)) if vals.size > 0 else np.nan,
                            "sig_negative_ratio": float(np.mean(vals < 0)) if vals.size > 0 else np.nan,
                        }
                    )

        print(f"已写出: {s.output_nc}")

    panel_outputs = []
    assert lon_cache is not None and lat_cache is not None
    for metric in METRICS:
        out_png = save_metric_panel(
            lon=lon_cache,
            lat=lat_cache,
            metric=metric,
            sig_by_scenario=sig_data_for_panel[metric],
        )
        panel_outputs.append(out_png)
        print(f"已写出: {out_png}")

    df = pd.DataFrame(continent_rows)
    csv_path = os.path.join(PERF_DIR, "continent_significant_trend_stats.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    md_path = os.path.join(PERF_DIR, "continent_significant_trend_stats.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 各大洲显著趋势统计（p<0.05）\n\n")
        f.write(f"- 显著性阈值: p < {P_THRESHOLD}\n")
        f.write(f"- 有效像元阈值: n_events >= {MIN_EVENTS}\n")
        f.write("- 大洲掩膜: 离线经纬度分区规则（见脚本）\n\n")

        for metric in METRICS:
            f.write(f"## {METRIC_CN[metric]}\n\n")
            sub = df[df["metric"] == metric].copy()
            if sub.empty:
                f.write("无数据\n\n")
                continue
            sub = sub.sort_values(["scenario_cn", "continent_code"])

            show_cols = [
                "scenario_cn",
                "continent_cn",
                "n_valid_pixels",
                "n_sig_pixels",
                "sig_ratio_in_valid",
                "sig_mean_slope",
                "sig_median_slope",
                "sig_positive_ratio",
                "sig_negative_ratio",
            ]
            f.write("| " + " | ".join(show_cols) + " |\n")
            f.write("|" + "|".join(["---"] * len(show_cols)) + "|\n")
            for _, row in sub[show_cols].iterrows():
                vals = []
                for c in show_cols:
                    v = row[c]
                    if isinstance(v, (float, np.floating)):
                        vals.append("" if not np.isfinite(v) else f"{float(v):.6g}")
                    else:
                        vals.append(str(v))
                f.write("| " + " | ".join(vals) + " |\n")
            f.write("\n\n")

    print(f"已写出: {csv_path}")
    print(f"已写出: {md_path}")


if __name__ == "__main__":
    analyze()
