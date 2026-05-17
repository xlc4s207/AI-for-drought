#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import argparse
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import rasterio

BASE_DIR = "/home/xulc/flash_drought/process/response_analysis"
OUT_DIR = "/home/xulc/flash_drought/process/response_analysis/plot_analysis/total"
os.makedirs(OUT_DIR, exist_ok=True)

ROWS_4x3 = ["SMs_flash", "SMrz_flash", "SMs_nonflash", "SMrz_nonflash"]
COLS_4x3 = ["GPP", "RECO", "NEE"]

ROWS_3x4 = ["GPP", "RECO", "NEE"]
COLS_3x4 = ["SMs_flash", "SMrz_flash", "SMs_nonflash", "SMrz_nonflash"]

METRICS = [
    "min",
    "mean",
    "trend",
    "t_min",
    "t_response",
    "t_impact",
    "amp_max",
    "t_recover",
    "recovery_rate",
]

SCENARIO_LABELS = {
    "SMs_flash": "SMs-flash",
    "SMrz_flash": "SMrz-flash",
    "SMs_nonflash": "SMs-nonflash",
    "SMrz_nonflash": "SMrz-nonflash",
}

VARIABLE_LABELS = {
    "GPP": "GPP",
    "RECO": "RECO",
    "NEE": "NEE",
}


def metric_to_filename(variable: str, metric: str) -> str:
    v = variable.lower()
    if metric in ["min", "mean", "trend"]:
        return f"{v}_{metric}.tif"
    return f"{metric}.tif"


def tif_path(variable: str, scenario: str, metric: str) -> str:
    folder = f"{variable}_{scenario}"
    filename = metric_to_filename(variable, metric)
    return os.path.join(
        BASE_DIR,
        variable,
        f"{variable}_total_analysis",
        folder,
        filename,
    )


def load_raster(path: str) -> Tuple[np.ndarray, Tuple[float, float, float, float]]:
    with rasterio.open(path) as src:
        data = src.read(1).astype(np.float32)
        data = np.where(np.isfinite(data), data, np.nan)
        extent = (src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top)
    return data, extent


def robust_minmax(arrays: List[np.ndarray], metric: str) -> Tuple[float, float]:
    vals = np.concatenate([a[np.isfinite(a)] for a in arrays if np.isfinite(a).any()])
    if vals.size == 0:
        return -1.0, 1.0

    if metric in ["trend"]:
        p = np.nanpercentile(np.abs(vals), 98)
        p = max(p, 1e-6)
        return -p, p

    vmin = np.nanpercentile(vals, 2)
    vmax = np.nanpercentile(vals, 98)
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
        m = float(np.nanmean(vals))
        s = float(np.nanstd(vals))
        if not np.isfinite(s) or s == 0:
            s = 1.0
        vmin, vmax = m - 2 * s, m + 2 * s
    return float(vmin), float(vmax)


def cmap_for_metric(metric: str) -> str:
    if metric in ["trend"]:
        return "RdBu_r"
    if metric in ["amp_max"]:
        return "coolwarm"
    return "viridis"


def plot_metric(metric: str, layout: str = "4x3", dpi: int = 600) -> None:
    if layout == "4x3":
        rows = ROWS_4x3
        cols = COLS_4x3
    else:
        rows = ROWS_3x4
        cols = COLS_3x4

    rasters: Dict[Tuple[str, str], Tuple[np.ndarray, Tuple[float, float, float, float]]] = {}
    arrays = []

    for r in rows:
        for c in cols:
            p = tif_path(c, r, metric) if layout == "4x3" else tif_path(r, c, metric)
            if not os.path.exists(p):
                raise FileNotFoundError(f"缺少文件: {p}")
            arr, ext = load_raster(p)
            rasters[(r, c)] = (arr, ext)
            arrays.append(arr)

    vmin, vmax = robust_minmax(arrays, metric)
    cmap = cmap_for_metric(metric)

    if layout == "4x3":
        fig, axes = plt.subplots(4, 3, figsize=(15, 16), dpi=dpi)
        plt.subplots_adjust(wspace=0.05, hspace=0.08, right=0.90)
    else:
        fig, axes = plt.subplots(3, 4, figsize=(20, 12), dpi=dpi)
        plt.subplots_adjust(wspace=0.06, hspace=0.12, right=0.90)

    last_im = None
    for i, r in enumerate(rows):
        for j, c in enumerate(cols):
            ax = axes[i, j]
            arr, ext = rasters[(r, c)]
            last_im = ax.imshow(
                arr,
                extent=ext,
                origin="upper",
                cmap=cmap,
                vmin=vmin,
                vmax=vmax,
                interpolation="nearest",
            )
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_aspect("auto")

            if i == 0:
                if layout == "4x3":
                    ax.set_title(VARIABLE_LABELS[c], fontsize=12, pad=8)
                else:
                    ax.set_title(SCENARIO_LABELS[c], fontsize=12, pad=8)
            if j == 0:
                if layout == "4x3":
                    ax.set_ylabel(SCENARIO_LABELS[r], fontsize=12)
                else:
                    ax.set_ylabel(VARIABLE_LABELS[r], fontsize=12)

    cax = fig.add_axes([0.92, 0.15, 0.015, 0.7])
    cb = fig.colorbar(last_im, cax=cax)
    cb.ax.tick_params(labelsize=9)

    title = "4 Scenarios × 3 Variables" if layout == "4x3" else "3 Variables × 4 Scenarios"
    fig.suptitle(f"{metric} | {title}", fontsize=15, y=0.995)

    out_png = os.path.join(OUT_DIR, f"total_{metric}_{layout}.png")
    fig.savefig(out_png, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {out_png}")


def main() -> None:
    parser = argparse.ArgumentParser(description="绘制12子图总览")
    parser.add_argument("--layout", choices=["4x3", "3x4", "both"], default="4x3")
    parser.add_argument("--dpi", type=int, default=600)
    args = parser.parse_args()

    layouts = ["4x3", "3x4"] if args.layout == "both" else [args.layout]

    for m in METRICS:
        for layout in layouts:
            plot_metric(m, layout=layout, dpi=args.dpi)
    print(f"\n全部完成，布局={layouts}，DPI={args.dpi}。")


if __name__ == "__main__":
    main()
