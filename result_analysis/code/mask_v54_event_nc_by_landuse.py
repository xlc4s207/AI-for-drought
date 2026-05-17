#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from pathlib import Path

import netCDF4 as nc
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject


LANDUSE_PATH = Path("/home/xulc/flash_drought/land_use/MCD12C1_LC_Type1_2010_11km.tif")
landuse_path_global = LANDUSE_PATH
DEFAULT_SOURCE_DIRS = [
    Path("/home/xulc/flash_drought/gleam/result/SMs_result_v5.4_0p25deg"),
    Path("/home/xulc/flash_drought/gleam/result/SMrz_result_v5.4_0p25deg"),
]
DEFAULT_OUT_BASE = Path("/home/xulc/flash_drought/gleam/clip_result")
OUT_SUFFIX = "_no_ice_desert"

TARGET_FILES = [
    "rapid_1to4_drought_events_v5.4.nc",
    "flash_5to20_drought_events_v5.4.nc",
    "flash_lt20_drought_events_v5.4.nc",
    "slow_gt20_drought_events_v5.4.nc",
]

INVALID_LANDUSE_CLASSES = (15, 16)
SHORT_FILL = np.int16(-1)
FLOAT_FILL = np.float32(-9999.0)


def parse_args():
    parser = argparse.ArgumentParser(description="按土地利用掩膜 v5.4 干旱事件 NetCDF（去除冰原与荒漠）")
    parser.add_argument(
        "--source-dir",
        action="append",
        dest="source_dirs",
        default=None,
        help="待处理结果目录，可重复指定；默认处理 GLEAM 两个 v5.4 目录",
    )
    parser.add_argument(
        "--out-base",
        type=str,
        default=str(DEFAULT_OUT_BASE),
        help="输出根目录，默认写入 /home/xulc/flash_drought/gleam/clip_result",
    )
    parser.add_argument(
        "--landuse",
        type=str,
        default=str(LANDUSE_PATH),
        help="土地利用栅格路径",
    )
    return parser.parse_args()


def build_invalid_landuse_mask(landuse: np.ndarray) -> np.ndarray:
    return np.isin(landuse, INVALID_LANDUSE_CLASSES)


def apply_spatial_mask_to_arrays(
    spatial_mask: np.ndarray,
    event_count: np.ndarray,
    short_data: dict[str, np.ndarray],
    float_data: dict[str, np.ndarray],
) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, np.ndarray]]:
    masked_count = np.array(event_count, copy=True)
    masked_count[spatial_mask] = SHORT_FILL

    masked_short = {}
    for name, arr in short_data.items():
        out = np.array(arr, copy=True)
        out[:, spatial_mask] = SHORT_FILL
        masked_short[name] = out

    masked_float = {}
    for name, arr in float_data.items():
        out = np.array(arr, copy=True)
        out[:, spatial_mask] = FLOAT_FILL
        masked_float[name] = out

    return masked_count, masked_short, masked_float


def compute_target_transform(lon: np.ndarray, lat: np.ndarray):
    dx = float(np.median(np.diff(lon)))
    dy = float(np.median(np.diff(lat)))
    west = float(lon.min() - dx / 2.0)
    east = float(lon.max() + dx / 2.0)
    south = float(lat.min() - abs(dy) / 2.0)
    north = float(lat.max() + abs(dy) / 2.0)
    return from_bounds(west, south, east, north, len(lon), len(lat))


def align_mask_to_latitude_order(mask_arr: np.ndarray, lat: np.ndarray) -> np.ndarray:
    lat = np.asarray(lat, dtype=np.float32)
    if lat.ndim != 1 or lat.size < 2:
        return mask_arr
    if float(lat[1]) > float(lat[0]):
        return np.flipud(mask_arr)
    return mask_arr


def resample_invalid_mask_to_nc_grid(landuse_path: Path, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    with rasterio.open(landuse_path) as src:
        src_arr = src.read(1)
        dst_arr = np.zeros((len(lat), len(lon)), dtype=np.int16)
        dst_transform = compute_target_transform(lon, lat)
        reproject(
            source=src_arr,
            destination=dst_arr,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=dst_transform,
            dst_crs=src.crs,
            resampling=Resampling.mode,
        )
    dst_arr = align_mask_to_latitude_order(dst_arr, lat)
    return build_invalid_landuse_mask(dst_arr)


def copy_dimensions(src: nc.Dataset, dst: nc.Dataset) -> None:
    for name, dim in src.dimensions.items():
        dst.createDimension(name, None if dim.isunlimited() else len(dim))


def create_output_variable(dst: nc.Dataset, src_var: nc.Variable):
    fill_value = getattr(src_var, "_FillValue", None)
    filters = src_var.filters() if hasattr(src_var, "filters") else {}
    kwargs = {}
    if fill_value is not None:
        kwargs["fill_value"] = fill_value
    if isinstance(filters, dict):
        if filters.get("zlib"):
            kwargs["zlib"] = True
            kwargs["complevel"] = filters.get("complevel", 4)
            if filters.get("shuffle") is not None:
                kwargs["shuffle"] = filters.get("shuffle")
    chunking = src_var.chunking() if hasattr(src_var, "chunking") else None
    if isinstance(chunking, tuple):
        kwargs["chunksizes"] = chunking

    dst_var = dst.createVariable(src_var.name, src_var.datatype, src_var.dimensions, **kwargs)
    attrs = {attr: src_var.getncattr(attr) for attr in src_var.ncattrs() if attr != "_FillValue"}
    dst_var.setncatts(attrs)
    return dst_var


def mask_variable_data(name: str, dims: tuple[str, ...], data, spatial_mask: np.ndarray):
    if name in {"lat", "lon"}:
        return data

    if hasattr(data, "filled"):
        fill = SHORT_FILL if np.issubdtype(np.asarray(data).dtype, np.integer) else FLOAT_FILL
        data = data.filled(fill)

    arr = np.asarray(data)

    if dims == ("lat", "lon"):
        out = np.array(arr, copy=True)
        if np.issubdtype(out.dtype, np.integer):
            out[spatial_mask] = SHORT_FILL
        else:
            out[spatial_mask] = FLOAT_FILL
        return out

    if dims[-2:] == ("lat", "lon"):
        out = np.array(arr, copy=True)
        if np.issubdtype(out.dtype, np.integer):
            out[:, spatial_mask] = SHORT_FILL
        else:
            out[:, spatial_mask] = FLOAT_FILL
        return out

    return arr


def mask_one_netcdf(in_path: Path, out_path: Path, spatial_mask: np.ndarray) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    with nc.Dataset(in_path, "r") as src, nc.Dataset(out_path, "w", format="NETCDF4") as dst:
        copy_dimensions(src, dst)
        dst.setncatts({attr: src.getncattr(attr) for attr in src.ncattrs()})
        dst.landuse_mask_source = str(landuse_path_global)
        dst.landuse_mask_classes_removed = "15=snow_ice,16=barren_or_sparsely_vegetated"
        dst.landuse_mask_note = "Pixels over ice/snow and desert/barren were masked to fill values."

        for name, src_var in src.variables.items():
            dst_var = create_output_variable(dst, src_var)
            data = src_var[:]
            dst_var[:] = mask_variable_data(name, src_var.dimensions, data, spatial_mask)


def output_dir_for_source(source_dir: Path, out_base: Path) -> Path:
    return out_base / f"{source_dir.name}{OUT_SUFFIX}"


def build_mask_from_example_nc(example_nc: Path, landuse_path: Path) -> np.ndarray:
    with nc.Dataset(example_nc, "r") as ds:
        lat = np.asarray(ds.variables["lat"][:], dtype=np.float32)
        lon = np.asarray(ds.variables["lon"][:], dtype=np.float32)
    return resample_invalid_mask_to_nc_grid(landuse_path, lon, lat)


def main() -> None:
    global landuse_path_global
    args = parse_args()
    source_dirs = [Path(p) for p in args.source_dirs] if args.source_dirs else list(DEFAULT_SOURCE_DIRS)
    out_base = Path(args.out_base)
    landuse_path_global = Path(args.landuse)

    print("开始按土地利用掩膜 v5.4 事件文件（去除冰原与荒漠）...")
    for source_dir in source_dirs:
        out_dir = output_dir_for_source(source_dir, out_base)
        example_nc = source_dir / TARGET_FILES[0]
        spatial_mask = build_mask_from_example_nc(example_nc, landuse_path_global)
        masked_pixels = int(np.sum(spatial_mask))
        total_pixels = int(spatial_mask.size)

        print(f"\n源目录: {source_dir}")
        print(f"输出目录: {out_dir}")
        print(f"掩膜像元: {masked_pixels}/{total_pixels} ({masked_pixels / total_pixels:.2%})")

        for filename in TARGET_FILES:
            in_path = source_dir / filename
            out_path = out_dir / filename
            if not in_path.exists():
                raise FileNotFoundError(f"缺少文件: {in_path}")
            mask_one_netcdf(in_path, out_path, spatial_mask)
            print(f"  已写出: {out_path}")


if __name__ == "__main__":
    main()
