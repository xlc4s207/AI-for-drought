#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
处理RECO v11缺失的chunks并合并到最终结果
"""
import os
import gc
import numpy as np
import netCDF4 as nc
from datetime import datetime
import warnings
from numba import jit
from tqdm import tqdm
from multiprocessing import Pool
warnings.filterwarnings('ignore')

# ============================================
# 配置
# ============================================
BASE_DIR = "/home/xulc/flash_drought"
DROUGHT_EVENTS_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMrz_5.3/flash_drought_events_v5.nc")
MERGED_RECO_FILE = "/data/BESS_V2/BESS_RECO_1982-2022_0.1deg.nc"
TEMP_DIR = os.path.join(BASE_DIR, "process/RECO-draught-analysis/results/temp_chunks_v11")
OUTPUT_FILE = os.path.join(BASE_DIR, "process/RECO-draught-analysis/results/reco_response_events_global_v11.nc")

START_YEAR, END_YEAR = 1982, 2022
WINDOW_BEFORE = 60
WINDOW_AFTER = 180
RESPONSE_SEARCH_WINDOW = 60
THRESHOLD_RESPONSE = -0.5
THRESHOLD_RECOVER = -0.25
CONSECUTIVE_DAYS = 3
LAT_CHUNK_SIZE = 20
N_WORKERS = 6  # 降低线程数减少内存占用

MISSING_CHUNKS = [0, 1, 2, 5, 6, 7, 8, 13, 15, 17, 18, 19, 22, 25, 33, 35, 41, 42, 43, 44, 47, 48, 49, 50, 51, 53]

RESULT_DTYPE = np.dtype([
    ('lat', 'f4'), ('lon', 'f4'), ('event_id', 'i2'), 
    ('onset_year', 'i2'), ('onset_doy', 'i2'),
    ('response_detected', 'i1'), ('reco_min', 'f4'), ('reco_mean', 'f4'),
    ('reco_trend', 'f4'), ('t_min', 'i2'), ('t_response', 'i2'),
    ('t_impact', 'i2'), ('amp_max', 'f4'), ('t_recover', 'f4'),
    ('recovery_rate', 'f4')
])

RESULT_FIELDS = list(RESULT_DTYPE.names)

# ============================================
# 全局变量
# ============================================
_reco_ds = None
_event_ds = None
_lon_arr = None
_year_offsets = None
_doy_idx = None

# [辅助函数和Numba函数与v11脚本相同，省略重复代码]
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
    """初始化worker进程的全局变量"""
    global _reco_ds, _event_ds, _lon_arr, _year_offsets, _doy_idx
    _reco_ds = nc.Dataset(MERGED_RECO_FILE, 'r')
    _event_ds = nc.Dataset(DROUGHT_EVENTS_FILE, 'r')
    _lon_arr = _reco_ds.variables['lon'][:]
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
def process_single_event(reco_z, ws, we, threshold_resp, threshold_recov, n_consec, max_search):
    segment = reco_z[ws:we+1]
    if np.sum(~np.isnan(segment)) < 30:
        return (0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan)
    smoothed = smooth_causal(segment, 7)
    pre_vals = []
    for i in range(min(60, len(smoothed))):
        if not np.isnan(smoothed[i]):
            pre_vals.append(smoothed[i])
    if len(pre_vals) < 5:
        return (0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan)
    post = smoothed[60:]
    n_post = len(post)
    if n_post < 10:
        return (0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan)
    reco_min, t_min_all = 1e9, -1
    valid_sum, valid_cnt = 0.0, 0
    for i in range(n_post):
        if not np.isnan(post[i]):
            valid_sum += post[i]
            valid_cnt += 1
            if post[i] < reco_min:
                reco_min = post[i]
                t_min_all = i
    reco_mean = valid_sum / valid_cnt if valid_cnt > 0 else np.nan
    reco_trend = calc_trend(post)
    t_response = find_threshold_crossing(post, threshold_resp, n_consec, max_search)
    if t_response == -1:
        return (0, reco_min, reco_mean, reco_trend, t_min_all, -1, -1, np.nan, np.nan, np.nan)
    t_min_local, min_val = -1, 1e9
    for i in range(t_response, n_post):
        if not np.isnan(post[i]) and post[i] < min_val:
            min_val = post[i]
            t_min_local = i
    if t_min_local == -1:
        return (1, reco_min, reco_mean, reco_trend, t_min_all, t_response, -1, np.nan, np.nan, np.nan)
    t_impact = t_min_local - t_response
    t_recover_idx = find_recovery(post, t_min_local + 1, threshold_recov, n_consec)
    if t_recover_idx == -1:
        t_recover, recovery_rate = np.nan, np.nan
    else:
        t_recover = float(t_recover_idx - t_min_local)
        recovery_rate = (threshold_recov - min_val) / t_recover if t_recover > 0 else np.nan
    return (1, reco_min, reco_mean, reco_trend, t_min_all, t_response, t_impact, min_val, t_recover, recovery_rate)

def calc_climatology_zscore(reco_matrix, doy_idx):
    n_time, n_pixels = reco_matrix.shape
    clim_mean = np.full((366, n_pixels), np.nan, dtype=np.float32)
    clim_std = np.full((366, n_pixels), np.nan, dtype=np.float32)
    for d in range(366):
        mask = (doy_idx == d)
        if np.sum(mask) > 0:
            data = reco_matrix[mask, :]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                clim_mean[d, :] = np.nanmean(data, axis=0)
                clim_std[d, :] = np.nanstd(data, axis=0, ddof=0)
    clim_std[clim_std < 0.01] = np.nan
    full_mean = clim_mean[doy_idx, :]
    full_std = clim_std[doy_idx, :]
    with np.errstate(divide='ignore', invalid='ignore'):
        z_matrix = (reco_matrix - full_mean) / full_std
    return z_matrix

def process_chunk(chunk_info):
    """处理单个chunk"""
    chunk_id, lat_start, lat_end = chunk_info
    results = []
    
    try:
        lat_arr = _reco_ds.variables['lat'][lat_start:lat_end]
        n_lats = lat_end - lat_start
        
        reco_chunk = _reco_ds.variables['RECO'][:, lat_start:lat_end, :]
        if hasattr(reco_chunk, 'filled'):
            reco_chunk = reco_chunk.filled(np.nan).astype(np.float32)
        else:
            reco_chunk = reco_chunk.astype(np.float32)
        
        ec_chunk = _event_ds.variables['event_count'][lat_start:lat_end, :]
        max_ec = int(np.max(ec_chunk))
        if max_ec == 0:
            del reco_chunk, ec_chunk
            return chunk_id, np.array([], dtype=RESULT_DTYPE)
        
        oy_raw = _event_ds.variables['onset_start_year'][:max_ec, lat_start:lat_end, :]
        od_raw = _event_ds.variables['onset_start_doy'][:max_ec, lat_start:lat_end, :]
        oy_chunk = oy_raw.filled(-1) if hasattr(oy_raw, 'filled') else oy_raw
        od_chunk = od_raw.filled(-1) if hasattr(od_raw, 'filled') else od_raw
        del oy_raw, od_raw  # 及时删除原始数据
        
        for rel_lat in range(n_lats):
            lat_val = float(lat_arr[rel_lat])
            lon_with_events = np.where(ec_chunk[rel_lat, :] > 0)[0]
            if len(lon_with_events) == 0:
                continue
            reco_row = reco_chunk[:, rel_lat, lon_with_events]
            valid_count = np.sum(~np.isnan(reco_row), axis=0)
            good_mask = valid_count >= 100
            if not np.any(good_mask):
                continue
            good_lon_indices = lon_with_events[good_mask]
            reco_good = reco_row[:, good_mask]
            z_matrix = calc_climatology_zscore(reco_good, _doy_idx)
            del reco_row, reco_good  # 释放中间变量
            
            for idx, lon_idx in enumerate(good_lon_indices):
                ec = int(ec_chunk[rel_lat, lon_idx])
                reco_z = z_matrix[:, idx]
                lon_val = float(_lon_arr[lon_idx])
                for i in range(ec):
                    oy = int(oy_chunk[i, rel_lat, lon_idx])
                    od = int(od_chunk[i, rel_lat, lon_idx])
                    if oy < START_YEAR or oy > END_YEAR or od <= 0 or od > 366:
                        continue
                    onset = _year_offsets[oy] + od - 1
                    ws, we = onset - WINDOW_BEFORE, onset + WINDOW_AFTER
                    if ws < 0 or we >= len(reco_z):
                        continue
                    m = process_single_event(reco_z, ws, we, THRESHOLD_RESPONSE, THRESHOLD_RECOVER, CONSECUTIVE_DAYS, RESPONSE_SEARCH_WINDOW)
                    results.append((lat_val, lon_val, i, oy, od, int(m[0]), float(m[1]), float(m[2]), float(m[3]),
                                  int(m[4]) if m[4] >= 0 else -1, int(m[5]) if m[5] >= 0 else -1,
                                  int(m[6]) if m[6] >= 0 else -1, float(m[7]) if m[0] else float(m[1]),
                                  float(m[8]), float(m[9])))
            del z_matrix  # 释放z分数矩阵
        
        # 释放所有chunk数据
        del reco_chunk, ec_chunk, oy_chunk, od_chunk
        gc.collect()
        
    except Exception as e:
        print(f"块 {chunk_id} 错误: {e}")
        gc.collect()
        return chunk_id, np.array([], dtype=RESULT_DTYPE)
    
    if results:
        result_arr = np.array(results, dtype=RESULT_DTYPE)
        del results  # 释放results列表
    else:
        result_arr = np.array([], dtype=RESULT_DTYPE)
    
    return chunk_id, result_arr

def process_missing_chunks():
    print("="*70)
    print("处理缺失的chunks (并行)")
    print("="*70)
    
    with nc.Dataset(DROUGHT_EVENTS_FILE, 'r') as ds:
        ec_all = ds.variables['event_count'][:]
    valid_lat_indices = np.where(np.sum(ec_all, axis=1) > 0)[0]
    lat_start_idx = valid_lat_indices[0]
    lat_end_idx = valid_lat_indices[-1] + 1
    
    # 构建所有chunk范围
    all_chunks = []
    for chunk_start in range(lat_start_idx, lat_end_idx, LAT_CHUNK_SIZE):
        chunk_end = min(chunk_start + LAT_CHUNK_SIZE, lat_end_idx)
        all_chunks.append((chunk_start, chunk_end))
    
    # 构建缺失chunk的任务列表
    chunk_tasks = []
    for chunk_id in MISSING_CHUNKS:
        lat_start, lat_end = all_chunks[chunk_id]
        chunk_tasks.append((chunk_id, lat_start, lat_end))
    
    print(f"缺失chunks数量: {len(chunk_tasks)}")
    print(f"并行进程数: {N_WORKERS}")
    
    # 并行处理
    with Pool(N_WORKERS, initializer=worker_init) as pool:
        for chunk_id, result_arr in tqdm(pool.imap_unordered(process_chunk, chunk_tasks),
                                         total=len(chunk_tasks),
                                         desc="处理进度"):
            if len(result_arr) > 0:
                np.save(os.path.join(TEMP_DIR, f"chunk_{chunk_id:04d}.npy"), result_arr)
            del result_arr  # 及时释放
            gc.collect()
    
    print(f"\n✅ 缺失chunks处理完成")
    gc.collect()

def merge_all_results():
    print("\n" + "="*70)
    print("合并所有结果")
    print("="*70)
    
    temp_files = sorted([f for f in os.listdir(TEMP_DIR) if f.endswith('.npy')])
    print(f"找到 {len(temp_files)} 个临时文件")
    
    all_results = []
    for tf in tqdm(temp_files, desc="合并"):
        arr = np.load(os.path.join(TEMP_DIR, tf))
        all_results.append(arr)
        del arr  # 立即释放临时数组
    
    if all_results:
        final_results = np.concatenate(all_results)
        del all_results  # 释放列表
        gc.collect()
    else:
        final_results = np.array([], dtype=RESULT_DTYPE)
    
    print(f"合并后总事件数: {len(final_results):,}")
    n_with_response = np.sum(final_results['response_detected'] == 1)
    print(f"明显响应事件: {n_with_response:,} ({n_with_response/len(final_results)*100:.1f}%)")
    
    print(f"\n保存完整结果: {OUTPUT_FILE}")
    with nc.Dataset(OUTPUT_FILE, 'w') as ds:
        ds.createDimension('event', len(final_results))
        for field in RESULT_FIELDS:
            if field in ['lat', 'lon', 'reco_min', 'reco_mean', 'reco_trend', 'amp_max', 't_recover', 'recovery_rate']:
                var = ds.createVariable(field, 'f4', ('event',), fill_value=np.nan, zlib=True, complevel=4)
            elif field in ['event_id', 'onset_year', 'onset_doy', 't_min', 't_response', 't_impact']:
                var = ds.createVariable(field, 'i2', ('event',), zlib=True, complevel=4)
            elif field == 'response_detected':
                var = ds.createVariable(field, 'i1', ('event',), zlib=True, complevel=4)
            var[:] = final_results[field]
        ds.title = 'RECO Response to SMrz Flash Drought - Global (v11, complete)'
        ds.history = f'Created: {datetime.now()}'
    
    print(f"文件大小: {os.path.getsize(OUTPUT_FILE)/1024/1024:.1f} MB")
    print("\n✅ 完成！")

def main():
    start_time = datetime.now()
    process_missing_chunks()
    merge_all_results()
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n总耗时: {elapsed/60:.1f}分钟")

if __name__ == "__main__":
    main()
