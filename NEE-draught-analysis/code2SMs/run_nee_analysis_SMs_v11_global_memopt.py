#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEE Response Analysis - Based on SMs Flash Drought Events (V11 Global)
========================================================================
分析表层土壤湿度 (SMs) 骤旱事件对净生态系统交换 (NEE) 的影响

基于 RECO v11 修改为 NEE 分析：
- 输入NEE文件：0.1°分辨率NEE数据
- 块大小：5行/块（从20行减少）
- 并行进程：30个（从6个增加）
- 观察期：180天
- 添加内存管理优化

输入:
1. SMs 骤旱事件: gleam/clip_result/SMs_5.3/flash_drought_events_v5.nc  
2. NEE 数据: NEE_1982-2022_0.1deg.nc

输出:
- NEE 响应分析结果 NetCDF 文件
"""

import os
import gc
import sys
import numpy as np
import netCDF4 as nc
from tqdm import tqdm
from multiprocessing import Pool
import warnings
from datetime import datetime
from numba import jit
import shutil
warnings.filterwarnings('ignore')

SHARED_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "_shared")
if SHARED_DIR not in sys.path:
    sys.path.append(SHARED_DIR)

from memopt_utils import StreamingEventNetCDFWriter

# ============================================
# 配置
# ============================================
BASE_DIR = "/home/xulc/flash_drought"
DROUGHT_EVENTS_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMs_5.3/flash_drought_events_v5.nc")
NEE_FILE = "/data/BESS_V2/NEE_1982-2022_0.1deg.nc"
OUTPUT_DIR = "/home/xulc/flash_drought/process/NEE-draught-analysis/code2SMs/result"
TEMP_DIR = os.path.join(OUTPUT_DIR, "temp_chunks_SMs_v11_memopt")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

START_YEAR, END_YEAR = 1982, 2022
WINDOW_BEFORE = 60      # 骤旱开始前的参考期
WINDOW_AFTER = 180      # 骤旱开始后的观察期 (v11: 180天)
RESPONSE_SEARCH_WINDOW = 60  # 搜索响应的最大天数

# NEE 响应阈值 (基于 z-score)
THRESHOLD_RESPONSE = 0.5    # 响应检测阈值（NEE向碳源方向偏移）
THRESHOLD_RECOVER = 0.25    # 恢复判断阈值（从恶化状态回落）

CONSECUTIVE_DAYS = 3        # 连续天数确认

N_WORKERS = 8
LAT_CHUNK_SIZE = 2
LON_BATCH_SIZE = 256
OUTPUT_FILENAME = 'nee_response_SMs_drought_v11_global_memopt.nc'

# 结果数据类型
RESULT_DTYPE = np.dtype([
    ('lat', 'f4'), ('lon', 'f4'), ('event_id', 'i2'), 
    ('onset_year', 'i2'), ('onset_doy', 'i2'),
    ('response_detected', 'i1'), ('nee_min', 'f4'), ('nee_mean', 'f4'),
    ('nee_trend', 'f4'), ('t_min', 'i2'), ('t_response', 'i2'),
    ('t_impact', 'i2'), ('amp_max', 'f4'), ('t_recover', 'f4'),
    ('recovery_rate', 'f4')
])

RESULT_FIELDS = list(RESULT_DTYPE.names)

# ============================================
# 全局变量
# ============================================
_nee_ds = None
_event_ds = None
_lon_arr = None
_year_offsets = None
_doy_idx = None

def build_year_offsets():
    """构建年份到时间索引的偏移量映射"""
    offsets = {}
    cumsum = 0
    for year in range(START_YEAR, END_YEAR + 1):
        offsets[year] = cumsum
        is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
        cumsum += 366 if is_leap else 365
    return offsets

def build_doy_index():
    """构建每个时间步对应的 DOY 索引"""
    idx_arr = []
    for year in range(START_YEAR, END_YEAR + 1):
        is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
        for d in range(366 if is_leap else 365):
            doy_idx = d if is_leap else (d if d < 59 else d + 1)
            idx_arr.append(doy_idx)
    return np.array(idx_arr, dtype=np.int16)

def worker_init():
    """初始化工作进程"""
    global _nee_ds, _event_ds, _lon_arr, _year_offsets, _doy_idx
    _nee_ds = nc.Dataset(NEE_FILE, 'r')
    _event_ds = nc.Dataset(DROUGHT_EVENTS_FILE, 'r')
    _lon_arr = _nee_ds.variables['lon'][:]
    _year_offsets = build_year_offsets()
    _doy_idx = build_doy_index()

@jit(nopython=True)
def smooth_causal(x, window=7):
    """因果平滑 (只使用过去数据)"""
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
    """找到首次高于阈值的位置 (连续 n_consecutive 天)"""
    n = min(len(x), max_search)
    for i in range(n - n_consecutive + 1):
        all_above = True
        for j in range(i, i + n_consecutive):
            if np.isnan(x[j]) or x[j] < threshold:
                all_above = False
                break
        if all_above:
            return i
    return -1

@jit(nopython=True)
def find_recovery(x, start_idx, threshold, n_consecutive):
    """找到恢复位置 (连续低于阈值)"""
    n = len(x)
    for i in range(start_idx, n - n_consecutive + 1):
        all_below = True
        for j in range(i, i + n_consecutive):
            if np.isnan(x[j]) or x[j] >= threshold:
                all_below = False
                break
        if all_below:
            return i
    return -1

@jit(nopython=True)
def calc_trend(y):
    """计算线性趋势斜率"""
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
def process_single_event(nee_z, ws, we, threshold_resp, threshold_recov, n_consec, max_search):
    """
    处理单个骤旱事件，分析 NEE 响应
    
    参数:
    - nee_z: z-score 标准化后的 NEE 时间序列
    - ws, we: 分析窗口起止索引
    - threshold_resp: 响应检测阈值
    - threshold_recov: 恢复判断阈值
    - n_consec: 连续天数
    - max_search: 最大搜索范围
    
    返回:
    (response_detected, nee_min, nee_mean, nee_trend, t_min, t_response, 
     t_impact, amp_max, t_recover, recovery_rate)
    """
    segment = nee_z[ws:we+1]
    
    if np.sum(~np.isnan(segment)) < 30:
        return (0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan)
    
    smoothed = smooth_causal(segment, 7)
    
    # 骤旱前的参考期 (前 WINDOW_BEFORE 天)
    pre_vals = []
    for i in range(min(60, len(smoothed))):
        if not np.isnan(smoothed[i]):
            pre_vals.append(smoothed[i])
    
    if len(pre_vals) < 5:
        return (0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan)
    
    # 骤旱后的观察期 (第 60 天开始)
    post = smoothed[60:]
    n_post = len(post)
    
    if n_post < 10:
        return (0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan)
    
    # 计算基本统计量（冲击峰值使用最大值，表示向碳源方向恶化）
    nee_min, t_min_all = 1e9, -1
    valid_sum, valid_cnt = 0.0, 0
    for i in range(n_post):
        if not np.isnan(post[i]):
            valid_sum += post[i]
            valid_cnt += 1
            if post[i] < nee_min:
                nee_min = post[i]
                t_min_all = i
    
    nee_mean = valid_sum / valid_cnt if valid_cnt > 0 else np.nan
    nee_trend = calc_trend(post)
    
    # 检测响应开始时间
    t_response = find_threshold_crossing(post, threshold_resp, n_consec, max_search)
    
    if t_response == -1:
        return (0, nee_min, nee_mean, nee_trend, t_min_all, -1, -1, np.nan, np.nan, np.nan)
    
    # 找到响应后的峰值（最大正异常）
    t_min_local, min_val = -1, -1e9
    for i in range(t_response, n_post):
        if not np.isnan(post[i]) and post[i] > min_val:
            min_val = post[i]
            t_min_local = i
    
    if t_min_local == -1:
        return (1, nee_min, nee_mean, nee_trend, t_min_all, t_response, -1, np.nan, np.nan, np.nan)
    
    t_impact = t_min_local - t_response
    
    # 检测恢复
    t_recover_idx = find_recovery(post, t_min_local + 1, threshold_recov, n_consec)
    if t_recover_idx == -1:
        t_recover, recovery_rate = np.nan, np.nan
    else:
        t_recover = float(t_recover_idx - t_min_local)
        recovery_rate = (min_val - threshold_recov) / t_recover if t_recover > 0 else np.nan
    
    return (1, nee_min, nee_mean, nee_trend, t_min_all, t_response, t_impact, min_val, t_recover, recovery_rate)

def calc_climatology_zscore(nee_matrix, doy_idx):
    """计算气候态 z-score 标准化"""
    n_time, n_pixels = nee_matrix.shape
    clim_mean = np.full((366, n_pixels), np.nan, dtype=np.float32)
    clim_std = np.full((366, n_pixels), np.nan, dtype=np.float32)
    
    for d in range(366):
        mask = (doy_idx == d)
        if np.sum(mask) > 0:
            data = nee_matrix[mask, :]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                clim_mean[d, :] = np.nanmean(data, axis=0)
                clim_std[d, :] = np.nanstd(data, axis=0, ddof=0)
    
    clim_std[clim_std < 0.01] = np.nan
    full_mean = clim_mean[doy_idx, :]
    full_std = clim_std[doy_idx, :]
    
    with np.errstate(divide='ignore', invalid='ignore'):
        z_matrix = (nee_matrix - full_mean) / full_std
    
    # 及时释放中间变量
    del clim_mean, clim_std, full_mean, full_std
    
    return z_matrix


def to_float32_with_nan(data):
    if hasattr(data, 'mask'):
        data = data.astype(np.float32)
        return np.ma.filled(data, np.nan)
    return np.asarray(data, dtype=np.float32)


def to_int_array(data, fill_value):
    if hasattr(data, 'filled'):
        return data.filled(fill_value)
    return np.asarray(data)

def process_chunk(chunk_info):
    """处理一个纬度块，按单纬线读取以降低峰值内存。"""
    chunk_id, lat_start, lat_end = chunk_info
    results = []
    
    try:
        for lat_idx in range(lat_start, lat_end):
            lat_val = float(_nee_ds.variables['lat'][lat_idx])

            ec_row = to_int_array(_event_ds.variables['event_count'][lat_idx, :], 0)
            lon_with_events = np.where(ec_row > 0)[0]
            if len(lon_with_events) == 0:
                continue

            nee_row = to_float32_with_nan(_nee_ds.variables['NEE'][:, lat_idx, lon_with_events])
            valid_count = np.sum(~np.isnan(nee_row), axis=0)
            good_rel_idx = np.where(valid_count >= 100)[0]

            if len(good_rel_idx) == 0:
                del nee_row, ec_row
                continue

            max_ec = int(np.max(ec_row[lon_with_events]))
            sy_row = to_int_array(_event_ds.variables['drought_start_year'][:max_ec, lat_idx, lon_with_events], -1)
            sd_row = to_int_array(_event_ds.variables['drought_start_doy'][:max_ec, lat_idx, lon_with_events], -1)

            for batch_start in range(0, len(good_rel_idx), LON_BATCH_SIZE):
                batch_rel = good_rel_idx[batch_start:batch_start + LON_BATCH_SIZE]
                batch_lon_indices = lon_with_events[batch_rel]
                nee_good = nee_row[:, batch_rel]
                z_matrix = calc_climatology_zscore(nee_good, _doy_idx)

                for idx, rel_idx in enumerate(batch_rel):
                    lon_idx = int(lon_with_events[rel_idx])
                    ec = int(ec_row[lon_idx])
                    nee_z = z_matrix[:, idx]
                    lon_val = float(_lon_arr[lon_idx])

                    for event_idx in range(ec):
                        sy = int(sy_row[event_idx, rel_idx])
                        sd = int(sd_row[event_idx, rel_idx])

                        if sy < START_YEAR or sy > END_YEAR or sd <= 0 or sd > 366:
                            continue

                        onset = _year_offsets[sy] + sd - 1
                        ws, we = onset - WINDOW_BEFORE, onset + WINDOW_AFTER
                        if ws < 0 or we >= len(nee_z):
                            continue

                        m = process_single_event(
                            nee_z, ws, we,
                            THRESHOLD_RESPONSE, THRESHOLD_RECOVER,
                            CONSECUTIVE_DAYS, RESPONSE_SEARCH_WINDOW
                        )

                        results.append((
                            lat_val, lon_val, event_idx, sy, sd,
                            m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9]
                        ))

                del z_matrix, nee_good

            del nee_row, ec_row, sy_row, sd_row
            gc.collect()

        gc.collect()
        
        if results:
            result_arr = np.array(results, dtype=RESULT_DTYPE)
            del results
        else:
            result_arr = np.array([], dtype=RESULT_DTYPE)
        
        return chunk_id, result_arr
    
    except Exception as e:
        print(f"Chunk {chunk_id} 处理错误: {e}")
        import traceback
        traceback.print_exc()
        gc.collect()
        return chunk_id, np.array([], dtype=RESULT_DTYPE)

def main():
    print("=" * 70)
    print("NEE Response Analysis - SMs Flash Drought Events (V11 Global, MemOpt)")
    print("=" * 70)
    print(f"开始时间: {datetime.now()}")
    print(f"骤旱事件文件: {DROUGHT_EVENTS_FILE}")
    print(f"NEE 数据文件: {NEE_FILE}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"工作进程数: {N_WORKERS}")
    print(f"纬度块大小: {LAT_CHUNK_SIZE}")
    print(f"经度批大小: {LON_BATCH_SIZE}")
    
    # 打开文件获取维度信息
    with nc.Dataset(NEE_FILE, 'r') as ds:
        n_lat = len(ds.variables['lat'])
        n_lon = len(ds.variables['lon'])
        n_time = len(ds.variables['time'])
        lat_arr = ds.variables['lat'][:]
        lon_arr = ds.variables['lon'][:]
    
    print(f"\nNEE 数据维度: {n_time} x {n_lat} x {n_lon}")
    
    # 创建处理任务
    chunks = []
    for i, lat_start in enumerate(range(0, n_lat, LAT_CHUNK_SIZE)):
        lat_end = min(lat_start + LAT_CHUNK_SIZE, n_lat)
        chunks.append((i, lat_start, lat_end))
    
    print(f"分块数: {len(chunks)}")
    
    # 清理临时目录
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    # 并行处理
    print(f"\n开始并行处理...")
    total_events = 0
    
    with Pool(N_WORKERS, initializer=worker_init) as pool:
        for chunk_id, result in tqdm(pool.imap_unordered(process_chunk, chunks),
                                     total=len(chunks), desc="处理进度"):
            if len(result) > 0:
                # 保存到临时文件
                temp_file = os.path.join(TEMP_DIR, f"chunk_{chunk_id:04d}.npy")
                np.save(temp_file, result)
                total_events += len(result)
            del result  # 及时释放
            gc.collect()
    
    print(f"\n处理完成! 总事件数: {total_events}")

    # 流式写出结果，避免最终全量合并带来的内存峰值
    print("\n流式写出结果...")
    temp_files = sorted([f for f in os.listdir(TEMP_DIR) if f.endswith('.npy')])
    if not temp_files:
        print("警告: 无有效结果!")
    else:
        output_file = os.path.join(OUTPUT_DIR, OUTPUT_FILENAME)
        save_chunks_to_netcdf(temp_files, lat_arr, lon_arr, output_file)
    
    # 清理临时文件
    print("\n清理临时文件...")
    shutil.rmtree(TEMP_DIR)
    
    print(f"\n完成时间: {datetime.now()}")

def build_var_attrs():
    return {
        'response_detected': {'long_name': 'NEE deterioration detected (1=yes, 0=no)'},
        'nee_min': {'long_name': 'Minimum NEE z-score during observation period'},
        'nee_mean': {'long_name': 'Mean NEE z-score during response period'},
        'nee_trend': {'long_name': 'NEE z-score trend (slope) during response period'},
        't_min': {'long_name': 'Days to peak deterioration (max NEE z-score) from drought onset'},
        't_response': {
            'long_name': 'Days to first deterioration detection from drought onset',
            'comment': '-1 means no deterioration detected within search window',
        },
        't_impact': {'long_name': 'Days from deterioration detection to peak deterioration'},
        'amp_max': {'long_name': 'Peak deterioration amplitude (max NEE z-score after response)'},
        't_recover': {'long_name': 'Days from peak deterioration to recovery'},
        'recovery_rate': {'long_name': 'Rate of recovery from peak deterioration (z-score per day)'},
    }


def save_chunks_to_netcdf(temp_files, lat_arr, lon_arr, output_file):
    """将临时块结果流式写入 NetCDF 文件。"""
    print(f"保存到: {output_file}")

    coord_vars = [
        {'name': 'lat_coord', 'dtype': 'f4', 'dim_name': 'lat', 'dims': ('lat',), 'data': lat_arr, 'attrs': {'units': 'degrees_north'}},
        {'name': 'lon_coord', 'dtype': 'f4', 'dim_name': 'lon', 'dims': ('lon',), 'data': lon_arr, 'attrs': {'units': 'degrees_east'}},
    ]
    global_attrs = {
        'title': 'NEE Response to SMs Flash Drought Events - Global Analysis (v11, memopt)',
        'description': 'Memory-optimized run with single-latitude reads, longitude batching, and streaming output.',
        'source_drought': DROUGHT_EVENTS_FILE,
        'source_nee': NEE_FILE,
        'created': datetime.now().isoformat(),
        'parameters': (f'WINDOW_BEFORE={WINDOW_BEFORE}, WINDOW_AFTER={WINDOW_AFTER}, '
                       f'THRESHOLD_RESPONSE={THRESHOLD_RESPONSE}, '
                       f'THRESHOLD_RECOVER={THRESHOLD_RECOVER}, '
                       f'CONSECUTIVE_DAYS={CONSECUTIVE_DAYS}, '
                       f'N_WORKERS={N_WORKERS}, LAT_CHUNK_SIZE={LAT_CHUNK_SIZE}, '
                       f'LON_BATCH_SIZE={LON_BATCH_SIZE}')
    }
    writer = StreamingEventNetCDFWriter(
        output_file,
        RESULT_DTYPE,
        RESULT_FIELDS,
        var_attrs=build_var_attrs(),
        global_attrs=global_attrs,
        coord_vars=coord_vars,
    )
    total_written = 0
    for tf in tqdm(temp_files, desc='写出'):
        arr = np.load(os.path.join(TEMP_DIR, tf))
        writer.append(arr)
        total_written += len(arr)
        del arr
    writer.close()

    file_size = os.path.getsize(output_file) / 1024 / 1024
    print(f"保存完成: {total_written} 个事件, 文件大小: {file_size:.1f} MB")

if __name__ == '__main__':
    main()
