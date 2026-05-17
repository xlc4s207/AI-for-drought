#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPP Response Analysis - Non-Flash Drought (SMrz) V11 Global With Absolute Metrics
===============================================================================
在非骤旱分析中同步输出相对值与原始 GPP 绝对值指标。
"""

import os
import gc
import shutil
from datetime import datetime

import netCDF4 as nc
import numpy as np
from multiprocessing import Pool
from numba import jit
from tqdm import tqdm
import warnings

warnings.filterwarnings('ignore')

BASE_DIR = "/home/xulc/flash_drought"
DROUGHT_EVENTS_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMrz_5.3/nonflash_drought_events_v5.nc")
MERGED_GPP_FILE = os.path.join(BASE_DIR, "process/GPP-draught-analysis/SMrz_result/BESS_GPP_1982_2022.nc")
OUTPUT_DIR = os.path.join(BASE_DIR, "process/GPP-draught-analysis/code3_nonflash_SMrz/result")
TEMP_DIR = os.path.join(OUTPUT_DIR, "temp_chunks_nonflash_SMrz_with_abs")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

START_YEAR, END_YEAR = 1982, 2022
WINDOW_BEFORE = 60
RECOVERY_WINDOW = 120
MAX_WINDOW_AFTER = 600
THRESHOLD_RESPONSE = -0.5
THRESHOLD_RECOVER = -0.25
CONSECUTIVE_DAYS = 3

N_WORKERS = 24
LAT_CHUNK_SIZE = 9

RESULT_DTYPE = np.dtype([
    ('lat', 'f4'), ('lon', 'f4'), ('event_id', 'i2'),
    ('drought_start_year', 'i2'), ('drought_start_doy', 'i2'),
    ('drought_end_year', 'i2'), ('drought_end_doy', 'i2'),
    ('drought_duration', 'i2'), ('actual_window_after', 'i2'),
    ('response_detected', 'i1'), ('gpp_min', 'f4'), ('gpp_mean', 'f4'),
    ('gpp_trend', 'f4'), ('t_min', 'i2'), ('t_response', 'i2'),
    ('t_impact', 'i2'), ('amp_max', 'f4'), ('t_recover', 'f4'),
    ('recovery_rate', 'f4'),
    ('gpp_baseline_abs', 'f4'), ('gpp_min_abs', 'f4'), ('gpp_max_abs', 'f4'),
    ('gpp_mean_abs', 'f4'), ('gpp_trend_abs', 'f4'), ('gpp_drop_abs', 'f4'),
    ('gpp_rise_abs', 'f4'), ('gpp_change_to_peak_abs', 'f4'),
    ('gpp_recovery_rate_abs', 'f4'),
])

RESULT_FIELDS = list(RESULT_DTYPE.names)

_gpp_ds = None
_event_ds = None
_lon_arr = None
_year_offsets = None
_doy_idx = None


def build_year_offsets():
    offsets = {}
    cumsum = 0
    for year in range(START_YEAR, END_YEAR + 1):
        offsets[year] = cumsum
        is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
        cumsum += 366 if is_leap else 365
    return offsets


def build_doy_index():
    idx_arr = []
    for year in range(START_YEAR, END_YEAR + 1):
        is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
        for d in range(366 if is_leap else 365):
            doy_idx = d if is_leap else (d if d < 59 else d + 1)
            idx_arr.append(doy_idx)
    return np.array(idx_arr, dtype=np.int16)


def worker_init():
    global _gpp_ds, _event_ds, _lon_arr, _year_offsets, _doy_idx
    _gpp_ds = nc.Dataset(MERGED_GPP_FILE, 'r')
    _event_ds = nc.Dataset(DROUGHT_EVENTS_FILE, 'r')
    _lon_arr = _gpp_ds.variables['lon'][:]
    _year_offsets = build_year_offsets()
    _doy_idx = build_doy_index()


@jit(nopython=True)
def smooth_causal(x, window=7):
    n = len(x)
    result = np.full(n, np.nan)
    for i in range(n):
        start = max(0, i - window + 1)
        vals = []
        for j in range(start, i + 1):
            if not np.isnan(x[j]):
                vals.append(x[j])
        if len(vals) >= 3:
            result[i] = np.mean(np.array(vals))
    return result


@jit(nopython=True)
def find_threshold_crossing(x, threshold, n_consecutive, max_search):
    n = min(len(x), max_search)
    for i in range(n - n_consecutive + 1):
        all_below = True
        for j in range(i, i + n_consecutive):
            if np.isnan(x[j]) or x[j] > threshold:
                all_below = False
                break
        if all_below:
            return i
    return -1


@jit(nopython=True)
def find_recovery(x, start_idx, threshold, n_consecutive):
    n = len(x)
    for i in range(start_idx, n - n_consecutive + 1):
        all_above = True
        for j in range(i, i + n_consecutive):
            if np.isnan(x[j]) or x[j] <= threshold:
                all_above = False
                break
        if all_above:
            return i
    return -1


@jit(nopython=True)
def calc_trend(y):
    valid_x, valid_y = [], []
    for i in range(len(y)):
        if not np.isnan(y[i]):
            valid_x.append(float(i))
            valid_y.append(y[i])
    if len(valid_x) < 10:
        return np.nan
    x_arr = np.array(valid_x)
    y_arr = np.array(valid_y)
    x_mean, y_mean = np.mean(x_arr), np.mean(y_arr)
    num, den = 0.0, 0.0
    for i in range(len(x_arr)):
        num += (x_arr[i] - x_mean) * (y_arr[i] - y_mean)
        den += (x_arr[i] - x_mean) ** 2
    return num / den if den > 0 else np.nan


@jit(nopython=True)
def process_single_event_relative(gpp_z, ws, we, window_before, threshold_resp, threshold_recov, n_consec, max_search):
    segment = gpp_z[ws:we + 1]
    if np.sum(~np.isnan(segment)) < 30:
        return (0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan)
    smoothed = smooth_causal(segment, 7)
    pre_vals = []
    for i in range(min(window_before, len(smoothed))):
        if not np.isnan(smoothed[i]):
            pre_vals.append(smoothed[i])
    if len(pre_vals) < 5:
        return (0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan)
    post = smoothed[window_before:]
    n_post = len(post)
    if n_post < 10:
        return (0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan)
    gpp_min, t_min_all = 1e9, -1
    valid_sum, valid_cnt = 0.0, 0
    for i in range(n_post):
        if not np.isnan(post[i]):
            valid_sum += post[i]
            valid_cnt += 1
            if post[i] < gpp_min:
                gpp_min = post[i]
                t_min_all = i
    gpp_mean = valid_sum / valid_cnt if valid_cnt > 0 else np.nan
    gpp_trend = calc_trend(post)
    actual_search = min(max_search, n_post)
    t_response = find_threshold_crossing(post, threshold_resp, n_consec, actual_search)
    if t_response == -1:
        return (0, gpp_min, gpp_mean, gpp_trend, t_min_all, -1, -1, np.nan, np.nan, np.nan)
    t_min_local, min_val = -1, 1e9
    for i in range(t_response, n_post):
        if not np.isnan(post[i]) and post[i] < min_val:
            min_val = post[i]
            t_min_local = i
    if t_min_local == -1:
        return (1, gpp_min, gpp_mean, gpp_trend, t_min_all, t_response, -1, np.nan, np.nan, np.nan)
    t_impact = t_min_local - t_response
    t_recover_idx = find_recovery(post, t_min_local + 1, threshold_recov, n_consec)
    if t_recover_idx == -1:
        t_recover, recovery_rate = np.nan, np.nan
    else:
        t_recover = float(t_recover_idx - t_min_local)
        recovery_rate = (threshold_recov - min_val) / t_recover if t_recover > 0 else np.nan
    return (1, gpp_min, gpp_mean, gpp_trend, t_min_all, t_response, t_impact, min_val, t_recover, recovery_rate)


def calc_absolute_metrics(gpp_abs, ws, we, window_before, t_min, t_recover):
    segment = gpp_abs[ws:we + 1]
    if len(segment) <= window_before:
        return (np.nan,) * 9
    pre = segment[:window_before]
    post = segment[window_before:]
    if np.sum(np.isfinite(pre)) < 5 or np.sum(np.isfinite(post)) < 10:
        return (np.nan,) * 9
    baseline = float(np.nanmean(pre))
    post_min = float(np.nanmin(post))
    post_max = float(np.nanmax(post))
    post_mean = float(np.nanmean(post))
    post_trend = float(calc_trend(post))
    drop_abs = baseline - post_min
    rise_abs = post_max - baseline
    change_to_peak = np.nan
    recovery_rate_abs = np.nan
    if t_min >= 0 and t_min < len(post) and np.isfinite(post[t_min]):
        peak_val = float(post[t_min])
        change_to_peak = peak_val - baseline
        if np.isfinite(t_recover) and t_recover > 0:
            rec_idx = t_min + int(round(t_recover))
            if 0 <= rec_idx < len(post) and np.isfinite(post[rec_idx]):
                recovery_rate_abs = (float(post[rec_idx]) - peak_val) / float(t_recover)
    return (baseline, post_min, post_max, post_mean, post_trend, drop_abs, rise_abs, change_to_peak, recovery_rate_abs)


def calc_climatology_zscore(gpp_matrix, doy_idx):
    n_time, n_pixels = gpp_matrix.shape
    clim_mean = np.full((366, n_pixels), np.nan, dtype=np.float32)
    clim_std = np.full((366, n_pixels), np.nan, dtype=np.float32)
    for d in range(366):
        mask = (doy_idx == d)
        if np.sum(mask) > 0:
            data = gpp_matrix[mask, :]
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                clim_mean[d, :] = np.nanmean(data, axis=0)
                clim_std[d, :] = np.nanstd(data, axis=0, ddof=0)
    clim_std[clim_std < 0.01] = np.nan
    full_mean = clim_mean[doy_idx, :]
    full_std = clim_std[doy_idx, :]
    with np.errstate(divide='ignore', invalid='ignore'):
        z_matrix = (gpp_matrix - full_mean) / full_std
    del clim_mean, clim_std, full_mean, full_std
    return z_matrix


def process_chunk(chunk_info):
    chunk_id, lat_start, lat_end = chunk_info
    results = []
    try:
        lat_arr = _gpp_ds.variables['lat'][lat_start:lat_end]
        n_lats = lat_end - lat_start
        n_time = len(_doy_idx)
        gpp_chunk = _gpp_ds.variables['GPP'][:, lat_start:lat_end, :]
        gpp_chunk = gpp_chunk.filled(np.nan).astype(np.float32) if hasattr(gpp_chunk, 'filled') else gpp_chunk.astype(np.float32)
        ec_chunk = _event_ds.variables['event_count'][lat_start:lat_end, :]
        if hasattr(ec_chunk, 'filled'):
            ec_chunk = ec_chunk.filled(0)
        max_ec = int(np.max(ec_chunk))
        if max_ec == 0:
            del gpp_chunk, ec_chunk
            return chunk_id, np.array([], dtype=RESULT_DTYPE)
        sy_raw = _event_ds.variables['drought_start_year'][:max_ec, lat_start:lat_end, :]
        sd_raw = _event_ds.variables['drought_start_doy'][:max_ec, lat_start:lat_end, :]
        ey_raw = _event_ds.variables['drought_end_year'][:max_ec, lat_start:lat_end, :]
        ed_raw = _event_ds.variables['drought_end_doy'][:max_ec, lat_start:lat_end, :]
        dur_raw = _event_ds.variables['duration'][:max_ec, lat_start:lat_end, :]
        sy_chunk = sy_raw.filled(-1) if hasattr(sy_raw, 'filled') else np.array(sy_raw)
        sd_chunk = sd_raw.filled(-1) if hasattr(sd_raw, 'filled') else np.array(sd_raw)
        ey_chunk = ey_raw.filled(-1) if hasattr(ey_raw, 'filled') else np.array(ey_raw)
        ed_chunk = ed_raw.filled(-1) if hasattr(ed_raw, 'filled') else np.array(ed_raw)
        dur_chunk = dur_raw.filled(-1) if hasattr(dur_raw, 'filled') else np.array(dur_raw)

        for rel_lat in range(n_lats):
            lat_val = float(lat_arr[rel_lat])
            lon_with_events = np.where(ec_chunk[rel_lat, :] > 0)[0]
            if len(lon_with_events) == 0:
                continue
            gpp_row = gpp_chunk[:, rel_lat, lon_with_events]
            valid_count = np.sum(~np.isnan(gpp_row), axis=0)
            good_mask = valid_count >= 100
            if not np.any(good_mask):
                del gpp_row
                continue
            good_lon_indices = lon_with_events[good_mask]
            gpp_good = gpp_row[:, good_mask]
            z_matrix = calc_climatology_zscore(gpp_good, _doy_idx)
            del gpp_row
            for idx, lon_idx in enumerate(good_lon_indices):
                ec = int(ec_chunk[rel_lat, lon_idx])
                gpp_z = z_matrix[:, idx]
                gpp_abs = gpp_good[:, idx]
                lon_val = float(_lon_arr[lon_idx])
                for event_id in range(ec):
                    sy = int(sy_chunk[event_id, rel_lat, lon_idx])
                    sd = int(sd_chunk[event_id, rel_lat, lon_idx])
                    ey = int(ey_chunk[event_id, rel_lat, lon_idx])
                    ed = int(ed_chunk[event_id, rel_lat, lon_idx])
                    dur = int(dur_chunk[event_id, rel_lat, lon_idx])
                    if sy < START_YEAR or sy > END_YEAR or sd <= 0 or sd > 366 or dur <= 0:
                        continue
                    actual_window = min(dur + RECOVERY_WINDOW, MAX_WINDOW_AFTER)
                    drought_start_idx = _year_offsets[sy] + sd - 1
                    ws = drought_start_idx - WINDOW_BEFORE
                    we = drought_start_idx + actual_window
                    if ws < 0 or we >= n_time:
                        continue
                    rel_metrics = process_single_event_relative(gpp_z, ws, we, WINDOW_BEFORE, THRESHOLD_RESPONSE, THRESHOLD_RECOVER, CONSECUTIVE_DAYS, actual_window)
                    abs_metrics = calc_absolute_metrics(gpp_abs, ws, we, WINDOW_BEFORE, int(rel_metrics[4]) if rel_metrics[4] >= 0 else -1, float(rel_metrics[8]))
                    results.append((
                        lat_val, lon_val, event_id, sy, sd, ey, ed, min(dur, 32767), min(actual_window, 32767),
                        int(rel_metrics[0]), float(rel_metrics[1]), float(rel_metrics[2]), float(rel_metrics[3]),
                        int(rel_metrics[4]) if rel_metrics[4] >= 0 else -1,
                        int(rel_metrics[5]) if rel_metrics[5] >= 0 else -1,
                        int(rel_metrics[6]) if rel_metrics[6] >= 0 else -1,
                        float(rel_metrics[7]) if rel_metrics[0] else float(rel_metrics[1]),
                        float(rel_metrics[8]), float(rel_metrics[9]),
                        float(abs_metrics[0]), float(abs_metrics[1]), float(abs_metrics[2]), float(abs_metrics[3]), float(abs_metrics[4]),
                        float(abs_metrics[5]), float(abs_metrics[6]), float(abs_metrics[7]), float(abs_metrics[8]),
                    ))
            del z_matrix, gpp_good
        del gpp_chunk, ec_chunk, sy_chunk, sd_chunk, ey_chunk, ed_chunk, dur_chunk
        gc.collect()
    except Exception as exc:
        print(f"Chunk {chunk_id} 处理错误: {exc}")
        import traceback
        traceback.print_exc()
        gc.collect()
        return chunk_id, np.array([], dtype=RESULT_DTYPE)
    return chunk_id, np.array(results, dtype=RESULT_DTYPE) if results else np.array([], dtype=RESULT_DTYPE)


def save_to_netcdf(final_results, out_file):
    with nc.Dataset(out_file, 'w', format='NETCDF4') as ds:
        ds.createDimension('event', len(final_results))
        float_fields = {
            'lat', 'lon', 'gpp_min', 'gpp_mean', 'gpp_trend', 'amp_max', 't_recover', 'recovery_rate',
            'gpp_baseline_abs', 'gpp_min_abs', 'gpp_max_abs', 'gpp_mean_abs', 'gpp_trend_abs',
            'gpp_drop_abs', 'gpp_rise_abs', 'gpp_change_to_peak_abs', 'gpp_recovery_rate_abs',
        }
        int16_fields = {
            'event_id', 'drought_start_year', 'drought_start_doy', 'drought_end_year', 'drought_end_doy',
            'drought_duration', 'actual_window_after', 't_min', 't_response', 't_impact',
        }
        for field in RESULT_FIELDS:
            if field in float_fields:
                var = ds.createVariable(field, 'f4', ('event',), fill_value=np.nan, zlib=True, complevel=4)
            elif field in int16_fields:
                var = ds.createVariable(field, 'i2', ('event',), zlib=True, complevel=4)
            elif field == 'response_detected':
                var = ds.createVariable(field, 'i1', ('event',), zlib=True, complevel=4)
            else:
                raise ValueError(f"未处理字段类型: {field}")
            var[:] = final_results[field]
        ds.title = 'GPP Response to Non-Flash SMrz Drought - Global Analysis (v11, relative + absolute metrics)'
        ds.history = f'Created: {datetime.now()}'
        ds.source_gpp = MERGED_GPP_FILE
        ds.source_events = DROUGHT_EVENTS_FILE


def main():
    print('=' * 70)
    print('GPP Response to Non-Flash Drought (SMrz) - V11 Global (relative + absolute metrics)')
    print('=' * 70)
    print(f'开始时间: {datetime.now()}')
    print(f'\n数据源:')
    print(f'  GPP: {MERGED_GPP_FILE}')
    print(f'  非骤旱事件: {DROUGHT_EVENTS_FILE}')
    print(f'\n观测窗口设计:')
    print(f'  参考期: drought_start 前 {WINDOW_BEFORE} 天')
    print(f'  观测期: drought_start → drought_end + {RECOVERY_WINDOW} 天')
    print(f'  观测期上限: {MAX_WINDOW_AFTER} 天')
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR)
    start_time = datetime.now()
    with nc.Dataset(DROUGHT_EVENTS_FILE, 'r') as ds:
        ec_all = ds.variables['event_count'][:]
        if hasattr(ec_all, 'filled'):
            ec_all = ec_all.filled(0)
        lat_has_events = np.any(ec_all > 0, axis=1)
        valid_lat_indices = np.where(lat_has_events)[0]
        if len(valid_lat_indices) == 0:
            print('无有效事件!')
            return
        lat_start_idx = int(valid_lat_indices[0])
        lat_end_idx = int(valid_lat_indices[-1] + 1)
    chunks = []
    chunk_id = 0
    for chunk_start in range(lat_start_idx, lat_end_idx, LAT_CHUNK_SIZE):
        chunk_end = min(chunk_start + LAT_CHUNK_SIZE, lat_end_idx)
        chunks.append((chunk_id, chunk_start, chunk_end))
        chunk_id += 1
    total_saved = 0
    completed = 0
    with Pool(N_WORKERS, initializer=worker_init) as pool:
        for cid, result_arr in tqdm(pool.imap_unordered(process_chunk, chunks), total=len(chunks), desc='处理进度'):
            if len(result_arr) > 0:
                np.save(os.path.join(TEMP_DIR, f'chunk_{cid:04d}.npy'), result_arr)
                total_saved += len(result_arr)
            completed += 1
            del result_arr
            gc.collect()
    print(f'\n已完成 {completed}/{len(chunks)} 个chunk')
    print(f'已保存 {total_saved:,} 个事件到临时文件')
    print(f'处理耗时: {(datetime.now() - start_time).total_seconds()/60:.1f} 分钟')
    temp_files = sorted([f for f in os.listdir(TEMP_DIR) if f.endswith('.npy')])
    all_results = []
    for tf in tqdm(temp_files, desc='合并'):
        arr = np.load(os.path.join(TEMP_DIR, tf))
        if len(arr) > 0:
            all_results.append(arr)
    final_results = np.concatenate(all_results) if all_results else np.array([], dtype=RESULT_DTYPE)
    out_file = os.path.join(OUTPUT_DIR, 'gpp_response_nonflash_SMrz_drought_v11_global_with_abs.nc')
    save_to_netcdf(final_results, out_file)
    print(f'输出: {out_file}')
    print(f'文件大小: {os.path.getsize(out_file)/1024/1024:.1f} MB')
    shutil.rmtree(TEMP_DIR)


if __name__ == '__main__':
    main()
