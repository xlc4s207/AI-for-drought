#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为事件级干旱响应结果补充绝对值指标（GPP/RECO/NEE通用）

用途：
- 输入：已有的相对指标结果 nc（含 event 维）
- 读取：原始变量数据（GPP/RECO/NEE）
- 输出：在原字段基础上新增绝对值字段的 nc

新增字段（单位与原变量一致）：
- value_baseline_abs: 干旱前基准期均值（前60天）
- value_min_abs: 干旱后观测期最小值
- value_max_abs: 干旱后观测期最大值
- value_mean_abs: 干旱后观测期平均值
- value_trend_abs: 干旱后观测期线性趋势（斜率/天）
- value_drop_abs: 基准到最小值的下降量（baseline - min）
- value_rise_abs: 基准到最大值的上升量（max - baseline）
- value_change_to_peak_abs: 基准到峰值(由 t_min 指定)变化量
- value_recovery_rate_abs: 峰值到恢复点的绝对恢复速率
"""

import os
import argparse
from functools import lru_cache
import numpy as np
import netCDF4 as nc

BASE_DIR = "/home/xulc/flash_drought"
START_YEAR = 1982
END_YEAR = 2022
WINDOW_BEFORE = 60
WINDOW_AFTER_FLASH = 180

DEFAULT_DATA_FILES = {
    "gpp": os.path.join(BASE_DIR, "process/GPP-draught-analysis/SMrz_result/BESS_GPP_1982_2022.nc"),
    "reco": "/data/BESS_V2/BESS_RECO_1982-2022_0.1deg.nc",
    "nee": "/data/BESS_V2/NEE_1982-2022_0.1deg.nc",
}


def build_year_offsets(start_year=START_YEAR, end_year=END_YEAR):
    offsets = {}
    cumsum = 0
    for year in range(start_year, end_year + 1):
        offsets[year] = cumsum
        leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
        cumsum += 366 if leap else 365
    return offsets


def calc_trend(y):
    mask = np.isfinite(y)
    if np.sum(mask) < 10:
        return np.nan
    x = np.arange(len(y), dtype=np.float64)[mask]
    v = y[mask].astype(np.float64)
    xm = x.mean()
    vm = v.mean()
    den = np.sum((x - xm) ** 2)
    if den <= 0:
        return np.nan
    return np.sum((x - xm) * (v - vm)) / den


def infer_metric_type(input_file):
    name = os.path.basename(input_file).lower()
    if "gpp" in name:
        return "gpp", "GPP"
    if "reco" in name:
        return "reco", "RECO"
    if "nee" in name:
        return "nee", "NEE"
    raise ValueError(f"无法从文件名识别变量类型（gpp/reco/nee）: {input_file}")


def infer_default_input(cwd):
    cands = [f for f in os.listdir(cwd) if f.endswith(".nc") and "_with_abs" not in f]
    if not cands:
        return None
    cands.sort()
    return os.path.join(cwd, cands[0])


def get_onset_fields(result_ds):
    if "onset_year" in result_ds.variables and "onset_doy" in result_ds.variables:
        return "onset_year", "onset_doy"
    if "drought_start_year" in result_ds.variables and "drought_start_doy" in result_ds.variables:
        return "drought_start_year", "drought_start_doy"
    raise ValueError("结果文件缺少 onset_year/onset_doy 或 drought_start_year/drought_start_doy 字段")


def main():
    parser = argparse.ArgumentParser(description="为干旱响应事件结果补充绝对值指标")
    parser.add_argument("--input", default=None, help="输入结果nc路径；默认取当前目录第一个nc")
    parser.add_argument("--data", default=None, help="原始变量nc路径；默认按文件名自动推断")
    parser.add_argument("--var", default=None, help="变量名（GPP/RECO/NEE）；默认自动推断")
    parser.add_argument("--output", default=None, help="输出nc路径，默认在输入名后加 _with_abs")
    parser.add_argument("--window-before", type=int, default=WINDOW_BEFORE)
    parser.add_argument("--window-after-flash", type=int, default=WINDOW_AFTER_FLASH)
    args = parser.parse_args()

    cwd = os.getcwd()
    input_file = args.input or infer_default_input(cwd)
    if input_file is None:
        raise FileNotFoundError("当前目录未找到可用 .nc 输入文件，请使用 --input 指定")
    if not os.path.isabs(input_file):
        input_file = os.path.abspath(input_file)

    metric_type, inferred_var = infer_metric_type(input_file)
    data_file = args.data or DEFAULT_DATA_FILES[metric_type]
    var_name = args.var or inferred_var

    if not os.path.exists(input_file):
        raise FileNotFoundError(f"输入结果文件不存在: {input_file}")
    if not os.path.exists(data_file):
        raise FileNotFoundError(f"原始变量文件不存在: {data_file}")

    output_file = args.output
    if output_file is None:
        root, ext = os.path.splitext(input_file)
        output_file = root + "_with_abs" + ext
    elif not os.path.isabs(output_file):
        output_file = os.path.abspath(output_file)

    print("=" * 70)
    print("Absolute Metrics Augmentation")
    print("=" * 70)
    print(f"Input : {input_file}")
    print(f"Data  : {data_file}")
    print(f"Var   : {var_name}")
    print(f"Output: {output_file}")

    year_offsets = build_year_offsets()

    with nc.Dataset(input_file, "r") as res_ds, nc.Dataset(data_file, "r") as data_ds:
        onset_year_key, onset_doy_key = get_onset_fields(res_ds)

        event_dim = "event"
        if event_dim not in res_ds.dimensions:
            raise ValueError("输入结果文件缺少 event 维度")
        n_event = len(res_ds.dimensions[event_dim])

        lat_arr = data_ds.variables["lat"][:].astype(np.float32)
        lon_arr = data_ds.variables["lon"][:].astype(np.float32)
        data_var = data_ds.variables[var_name]
        data_time = len(data_ds.dimensions["time"])

        event_lat = res_ds.variables["lat"][:]
        event_lon = res_ds.variables["lon"][:]
        event_year = res_ds.variables[onset_year_key][:]
        event_doy = res_ds.variables[onset_doy_key][:]

        t_min = res_ds.variables["t_min"][:] if "t_min" in res_ds.variables else np.full(n_event, -1, dtype=np.int16)
        t_recover = res_ds.variables["t_recover"][:] if "t_recover" in res_ds.variables else np.full(n_event, np.nan, dtype=np.float32)

        if "actual_window_after" in res_ds.variables:
            event_win_after = res_ds.variables["actual_window_after"][:]
        else:
            event_win_after = np.full(n_event, args.window_after_flash, dtype=np.int16)

        lat_idx = np.array([int(np.argmin(np.abs(lat_arr - v))) for v in event_lat], dtype=np.int32)
        lon_idx = np.array([int(np.argmin(np.abs(lon_arr - v))) for v in event_lon], dtype=np.int32)

        @lru_cache(maxsize=1024)
        def get_pixel_series(i_lat, i_lon):
            raw = data_var[:, int(i_lat), int(i_lon)]
            arr = raw.astype(np.float32)
            if np.ma.isMaskedArray(arr):
                arr = np.ma.filled(arr, np.nan).astype(np.float32)
            return arr

        value_baseline_abs = np.full(n_event, np.nan, dtype=np.float32)
        value_min_abs = np.full(n_event, np.nan, dtype=np.float32)
        value_max_abs = np.full(n_event, np.nan, dtype=np.float32)
        value_mean_abs = np.full(n_event, np.nan, dtype=np.float32)
        value_trend_abs = np.full(n_event, np.nan, dtype=np.float32)
        value_drop_abs = np.full(n_event, np.nan, dtype=np.float32)
        value_rise_abs = np.full(n_event, np.nan, dtype=np.float32)
        value_change_to_peak_abs = np.full(n_event, np.nan, dtype=np.float32)
        value_recovery_rate_abs = np.full(n_event, np.nan, dtype=np.float32)

        for i in range(n_event):
            year = int(event_year[i])
            doy = int(event_doy[i])
            if year not in year_offsets or doy < 1 or doy > 366:
                continue

            onset = year_offsets[year] + doy - 1
            win_after = int(event_win_after[i]) if np.isfinite(event_win_after[i]) else args.window_after_flash
            if win_after <= 0:
                win_after = args.window_after_flash

            ws = onset - args.window_before
            we = onset + win_after
            if ws < 0 or we >= data_time:
                continue

            s = get_pixel_series(int(lat_idx[i]), int(lon_idx[i]))
            seg = s[ws:we + 1]
            if seg.size <= args.window_before:
                continue

            pre = seg[:args.window_before]
            post = seg[args.window_before:]
            pre_valid = np.isfinite(pre)
            post_valid = np.isfinite(post)
            if np.sum(pre_valid) < 5 or np.sum(post_valid) < 10:
                continue

            baseline = float(np.nanmean(pre))
            post_min = float(np.nanmin(post))
            post_max = float(np.nanmax(post))
            post_mean = float(np.nanmean(post))
            post_trend = float(calc_trend(post))

            value_baseline_abs[i] = baseline
            value_min_abs[i] = post_min
            value_max_abs[i] = post_max
            value_mean_abs[i] = post_mean
            value_trend_abs[i] = post_trend
            value_drop_abs[i] = baseline - post_min
            value_rise_abs[i] = post_max - baseline

            if i < len(t_min) and int(t_min[i]) >= 0 and int(t_min[i]) < len(post):
                peak_idx = int(t_min[i])
                if np.isfinite(post[peak_idx]):
                    peak_val = float(post[peak_idx])
                    value_change_to_peak_abs[i] = peak_val - baseline

                    tr = float(t_recover[i]) if i < len(t_recover) else np.nan
                    if np.isfinite(tr) and tr > 0:
                        rec_idx = peak_idx + int(round(tr))
                        if 0 <= rec_idx < len(post) and np.isfinite(post[rec_idx]):
                            value_recovery_rate_abs[i] = (float(post[rec_idx]) - peak_val) / tr

    with nc.Dataset(input_file, "r") as src, nc.Dataset(output_file, "w", format="NETCDF4") as dst:
        for dim_name, dim in src.dimensions.items():
            dst.createDimension(dim_name, None if dim.isunlimited() else len(dim))

        for var_name_src, var in src.variables.items():
            fill_value = getattr(var, "_FillValue", None)
            if fill_value is not None:
                out_var = dst.createVariable(var_name_src, var.datatype, var.dimensions,
                                             zlib=True, complevel=4, fill_value=fill_value)
            else:
                out_var = dst.createVariable(var_name_src, var.datatype, var.dimensions,
                                             zlib=True, complevel=4)
            out_var[:] = var[:]
            for attr in var.ncattrs():
                if attr == "_FillValue":
                    continue
                out_var.setncattr(attr, var.getncattr(attr))

        def add_float_var(name, data, long_name, units="same as source variable"):
            var = dst.createVariable(name, "f4", ("event",), zlib=True, complevel=4, fill_value=np.nan)
            var[:] = data
            var.long_name = long_name
            var.units = units

        add_float_var("value_baseline_abs", value_baseline_abs, "Absolute baseline mean before drought (window_before)")
        add_float_var("value_min_abs", value_min_abs, "Absolute minimum value during post-drought observation window")
        add_float_var("value_max_abs", value_max_abs, "Absolute maximum value during post-drought observation window")
        add_float_var("value_mean_abs", value_mean_abs, "Absolute mean value during post-drought observation window")
        add_float_var("value_trend_abs", value_trend_abs, "Absolute linear trend slope during post-drought observation window", units="source-unit per day")
        add_float_var("value_drop_abs", value_drop_abs, "Absolute drop from baseline to post-window minimum (baseline - min)")
        add_float_var("value_rise_abs", value_rise_abs, "Absolute rise from baseline to post-window maximum (max - baseline)")
        add_float_var("value_change_to_peak_abs", value_change_to_peak_abs, "Absolute change from baseline to t_min point (value_at_t_min - baseline)")
        add_float_var("value_recovery_rate_abs", value_recovery_rate_abs, "Absolute recovery rate from t_min to recovery point", units="source-unit per day")

        for attr in src.ncattrs():
            dst.setncattr(attr, src.getncattr(attr))

        dst.setncattr("abs_metrics_added", "true")
        dst.setncattr("abs_metrics_source_file", os.path.abspath(input_file))
        dst.setncattr("abs_metrics_data_file", os.path.abspath(data_file))
        dst.setncattr("abs_metrics_variable", inferred_var)
        dst.setncattr("abs_metrics_window_before", args.window_before)
        dst.setncattr("abs_metrics_window_after_flash", args.window_after_flash)

    print(f"完成，输出文件: {output_file}")


if __name__ == "__main__":
    main()
