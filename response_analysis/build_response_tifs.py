#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import argparse
from dataclasses import dataclass
from typing import Dict, List

import netCDF4 as nc
import numpy as np
import rasterio
from rasterio.transform import from_origin

BASE_DIR = "/home/xulc/flash_drought"

FIELDS_COMMON = [
    "t_min",
    "t_response",
    "t_impact",
    "amp_max",
    "t_recover",
    "recovery_rate",
]

VARIABLE_FIELDS = {
    "GPP": ["gpp_min", "gpp_mean", "gpp_trend"],
    "NEE": ["nee_min", "nee_mean", "nee_trend"],
    "RECO": ["reco_min", "reco_mean", "reco_trend"],
}


@dataclass(frozen=True)
class Task:
    variable: str
    scenario: str
    nc_path: str
    out_dir: str


def make_dirs() -> None:
    specs = {
        "GPP": ["GPP_SMs_flash", "GPP_SMrz_flash", "GPP_SMs_nonflash", "GPP_SMrz_nonflash"],
        "NEE": ["NEE_SMs_flash", "NEE_SMrz_flash", "NEE_SMs_nonflash", "NEE_SMrz_nonflash"],
        "RECO": ["RECO_SMs_flash", "RECO_SMrz_flash", "RECO_SMs_nonflash", "RECO_SMrz_nonflash"],
    }

    for var, subdirs in specs.items():
        root = os.path.join(BASE_DIR, "process/response_analysis", var, f"{var}_total_analysis")
        for s in subdirs:
            os.makedirs(os.path.join(root, s), exist_ok=True)


def build_tasks() -> List[Task]:
    return [
        Task("GPP", "GPP_SMrz_flash",
             os.path.join(BASE_DIR, "process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v11_complete.nc"),
             os.path.join(BASE_DIR, "process/response_analysis/GPP/GPP_total_analysis/GPP_SMrz_flash")),
        Task("GPP", "GPP_SMs_flash",
             os.path.join(BASE_DIR, "process/GPP-draught-analysis/code2_SMs/results/gpp_response_SMs_events_global_v11.nc"),
             os.path.join(BASE_DIR, "process/response_analysis/GPP/GPP_total_analysis/GPP_SMs_flash")),
        Task("GPP", "GPP_SMrz_nonflash",
             os.path.join(BASE_DIR, "process/GPP-draught-analysis/code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v11_global.nc"),
             os.path.join(BASE_DIR, "process/response_analysis/GPP/GPP_total_analysis/GPP_SMrz_nonflash")),
        Task("GPP", "GPP_SMs_nonflash",
             os.path.join(BASE_DIR, "process/GPP-draught-analysis/code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v11_global.nc"),
             os.path.join(BASE_DIR, "process/response_analysis/GPP/GPP_total_analysis/GPP_SMs_nonflash")),

        Task("NEE", "NEE_SMrz_flash",
             os.path.join(BASE_DIR, "process/NEE-draught-analysis/code1SMrz/result/nee_response_events_global_v11.nc"),
             os.path.join(BASE_DIR, "process/response_analysis/NEE/NEE_total_analysis/NEE_SMrz_flash")),
        Task("NEE", "NEE_SMs_flash",
             os.path.join(BASE_DIR, "process/NEE-draught-analysis/code2SMs/result/nee_response_SMs_drought_v11_global.nc"),
             os.path.join(BASE_DIR, "process/response_analysis/NEE/NEE_total_analysis/NEE_SMs_flash")),
        Task("NEE", "NEE_SMrz_nonflash",
             os.path.join(BASE_DIR, "process/NEE-draught-analysis/code3_nonflash_SMrz/result/nee_response_nonflash_SMrz_drought_v11_global.nc"),
             os.path.join(BASE_DIR, "process/response_analysis/NEE/NEE_total_analysis/NEE_SMrz_nonflash")),
        Task("NEE", "NEE_SMs_nonflash",
             os.path.join(BASE_DIR, "process/NEE-draught-analysis/code4_nonflash_SMs/result/nee_response_nonflash_SMs_drought_v11_global.nc"),
             os.path.join(BASE_DIR, "process/response_analysis/NEE/NEE_total_analysis/NEE_SMs_nonflash")),

        Task("RECO", "RECO_SMrz_flash",
             os.path.join(BASE_DIR, "process/RECO-draught-analysis/results/reco_response_events_global_v11.nc"),
             os.path.join(BASE_DIR, "process/response_analysis/RECO/RECO_total_analysis/RECO_SMrz_flash")),
        Task("RECO", "RECO_SMs_flash",
             os.path.join(BASE_DIR, "process/RECO-draught-analysis/code2_SMs/results/reco_response_SMs_drought_v11_global.nc"),
             os.path.join(BASE_DIR, "process/response_analysis/RECO/RECO_total_analysis/RECO_SMs_flash")),
        Task("RECO", "RECO_SMrz_nonflash",
             os.path.join(BASE_DIR, "process/RECO-draught-analysis/code3_nonflash_SMrz/result/reco_response_nonflash_SMrz_drought_v11_global.nc"),
             os.path.join(BASE_DIR, "process/response_analysis/RECO/RECO_total_analysis/RECO_SMrz_nonflash")),
        Task("RECO", "RECO_SMs_nonflash",
             os.path.join(BASE_DIR, "process/RECO-draught-analysis/code4_nonflash_SMs/result/reco_response_nonflash_SMs_drought_v11_global.nc"),
             os.path.join(BASE_DIR, "process/response_analysis/RECO/RECO_total_analysis/RECO_SMs_nonflash")),
    ]


def filled(arr) -> np.ndarray:
    if hasattr(arr, "filled"):
        return np.asarray(arr.filled(np.nan))
    return np.asarray(arr)


def build_grid(lat: np.ndarray, lon: np.ndarray):
    lat_unique = np.unique(lat)
    lon_unique = np.unique(lon)

    lat_desc = np.sort(lat_unique)[::-1]
    lon_asc = np.sort(lon_unique)

    lat_map: Dict[float, int] = {v: i for i, v in enumerate(lat_desc.tolist())}
    lon_map: Dict[float, int] = {v: i for i, v in enumerate(lon_asc.tolist())}

    # 用字典映射（事件坐标来自同一网格，精确匹配）
    row_idx = np.fromiter((lat_map[v] for v in lat.tolist()), dtype=np.int32, count=lat.size)
    col_idx = np.fromiter((lon_map[v] for v in lon.tolist()), dtype=np.int32, count=lon.size)

    nrows, ncols = lat_desc.size, lon_asc.size
    cell_idx = (row_idx.astype(np.int64) * ncols + col_idx.astype(np.int64)).astype(np.int64)

    if ncols > 1:
        xres = float(np.median(np.diff(lon_asc)))
    else:
        xres = 0.1
    if nrows > 1:
        yres = float(np.median(np.abs(np.diff(lat_desc))))
    else:
        yres = 0.1

    west = float(lon_asc.min() - xres / 2.0)
    north = float(lat_desc.max() + yres / 2.0)
    transform = from_origin(west, north, xres, yres)

    return cell_idx, nrows, ncols, transform


def aggregate_mean_to_grid(values: np.ndarray, cell_idx: np.ndarray, nrows: int, ncols: int) -> np.ndarray:
    vals = values.astype(np.float64, copy=False)
    valid = np.isfinite(vals)

    sums = np.bincount(cell_idx[valid], weights=vals[valid], minlength=nrows * ncols)
    counts = np.bincount(cell_idx[valid], minlength=nrows * ncols)

    out = np.full(nrows * ncols, np.nan, dtype=np.float32)
    nonzero = counts > 0
    out[nonzero] = (sums[nonzero] / counts[nonzero]).astype(np.float32)
    return out.reshape((nrows, ncols))


def write_tif(path: str, data: np.ndarray, transform) -> None:
    profile = {
        "driver": "GTiff",
        "height": data.shape[0],
        "width": data.shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": transform,
        "compress": "LZW",
        "nodata": np.nan,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data.astype(np.float32), 1)


def process_task(task: Task) -> None:
    fields = VARIABLE_FIELDS[task.variable] + FIELDS_COMMON

    with nc.Dataset(task.nc_path, "r") as ds:
        lat = filled(ds.variables["lat"][:]).astype(np.float64, copy=False)
        lon = filled(ds.variables["lon"][:]).astype(np.float64, copy=False)

        if task.variable == "NEE":
            lat = -lat
            print(f"[INFO] {task.scenario} 应用纬度方向修正: lat -> -lat")

        cell_idx, nrows, ncols, transform = build_grid(lat, lon)

        for field in fields:
            if field not in ds.variables:
                print(f"[WARN] {task.scenario} 缺失字段 {field}，跳过")
                continue

            arr = filled(ds.variables[field][:])
            grid = aggregate_mean_to_grid(arr, cell_idx, nrows, ncols)
            out_tif = os.path.join(task.out_dir, f"{field}.tif")
            write_tif(out_tif, grid, transform)
            print(f"[OK] {task.scenario} -> {out_tif}")


def main() -> None:
    parser = argparse.ArgumentParser(description="将响应事件NC聚合为栅格均值TIF")
    parser.add_argument(
        "--variable",
        choices=["GPP", "NEE", "RECO", "ALL"],
        default="ALL",
        help="只处理指定变量（默认ALL）",
    )
    args = parser.parse_args()

    make_dirs()
    tasks = build_tasks()

    if args.variable != "ALL":
        tasks = [t for t in tasks if t.variable == args.variable]

    print(f"总任务数: {len(tasks)}")
    for i, task in enumerate(tasks, start=1):
        print(f"\n[{i}/{len(tasks)}] 处理 {task.scenario}")
        process_task(task)

    print("\n全部完成。")


if __name__ == "__main__":
    main()
