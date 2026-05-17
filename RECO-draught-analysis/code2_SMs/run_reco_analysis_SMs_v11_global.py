#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RECO Response Analysis - Based on SMs Flash Drought Events (V11 Global)
========================================================================
分析表层土壤湿度 (SMs) 骤旱事件对生态系统呼吸 (RECO) 的影响

基于 v10 修改：使用裁剪后的骤旱事件(排除沙漠/冰川)和0.1度RECO数据，观察期延长到180天
v11 优化：减少线程数到6，添加内存管理优化

输入:
1. SMs 骤旱事件: gleam/clip_result/SMs_5.3/flash_drought_events_v5.nc  
2. RECO 数据: BESS_RECO_1982-2022_0.1deg.nc

输出:
- RECO 响应分析结果 NetCDF 文件
"""

import os
import gc
import numpy as np
import netCDF4 as nc
from tqdm import tqdm
from multiprocessing import Pool
import warnings
from datetime import datetime
from numba import jit
import shutil
warnings.filterwarnings('ignore')

# ============================================
# 配置
# ============================================
BASE_DIR = "/home/xulc/flash_drought"
DROUGHT_EVENTS_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMs_5.3/flash_drought_events_v5.nc")
RECO_FILE = "/data/BESS_V2/BESS_RECO_1982-2022_0.1deg.nc"
OUTPUT_DIR = os.path.join(BASE_DIR, "process/RECO-draught-analysis/code2_SMs/results")
TEMP_DIR = os.path.join(OUTPUT_DIR, "temp_chunks_SMs_v11")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

START_YEAR, END_YEAR = 1982, 2022
WINDOW_BEFORE = 60      # 骤旱开始前的参考期
WINDOW_AFTER = 180      # 骤旱开始后的观察期 (v11: 从120改为180)
RESPONSE_SEARCH_WINDOW = 60  # 搜索响应的最大天数

# RECO 响应阈值 (基于 z-score)
# RECO 在干旱时可能上升或下降，这里检测负响应(下降)
THRESHOLD_RESPONSE = -0.5   # 响应检测阈值
THRESHOLD_RECOVER = -0.25   # 恢复判断阈值

CONSECUTIVE_DAYS = 3        # 连续天数确认

N_WORKERS = 6  # 降低线程数减少内存占用 (v11)
LAT_CHUNK_SIZE = 20         # 每次处理的纬度行数

# 结果数据类型
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
    global _reco_ds, _event_ds, _lon_arr, _year_offsets, _doy_idx
    _reco_ds = nc.Dataset(RECO_FILE, 'r')
    _event_ds = nc.Dataset(DROUGHT_EVENTS_FILE, 'r')
    _lon_arr = _reco_ds.variables['lon'][:]
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
    """找到首次低于阈值的位置 (连续 n_consecutive 天)"""
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
    """找到恢复位置 (连续高于阈值)"""
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
def process_single_event(reco_z, ws, we, threshold_resp, threshold_recov, n_consec, max_search):
    """
    处理单个骤旱事件，分析 RECO 响应
    
    参数:
    - reco_z: z-score 标准化后的 RECO 时间序列
    - ws, we: 分析窗口起止索引
    - threshold_resp: 响应检测阈值
    - threshold_recov: 恢复判断阈值
    - n_consec: 连续天数
    - max_search: 最大搜索范围
    
    返回:
    (response_detected, reco_min, reco_mean, reco_trend, t_min, t_response, 
     t_impact, amp_max, t_recover, recovery_rate)
    """
    segment = reco_z[ws:we+1]
    
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
    
    # 计算基本统计量
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
    
    # 检测响应开始时间
    t_response = find_threshold_crossing(post, threshold_resp, n_consec, max_search)
    
    if t_response == -1:
        return (0, reco_min, reco_mean, reco_trend, t_min_all, -1, -1, np.nan, np.nan, np.nan)
    
    # 找到响应后的最小值
    t_min_local, min_val = -1, 1e9
    for i in range(t_response, n_post):
        if not np.isnan(post[i]) and post[i] < min_val:
            min_val = post[i]
            t_min_local = i
    
    if t_min_local == -1:
        return (1, reco_min, reco_mean, reco_trend, t_min_all, t_response, -1, np.nan, np.nan, np.nan)
    
    t_impact = t_min_local - t_response
    
    # 检测恢复
    t_recover_idx = find_recovery(post, t_min_local + 1, threshold_recov, n_consec)
    if t_recover_idx == -1:
        t_recover, recovery_rate = np.nan, np.nan
    else:
        t_recover = float(t_recover_idx - t_min_local)
        recovery_rate = (threshold_recov - min_val) / t_recover if t_recover > 0 else np.nan
    
    return (1, reco_min, reco_mean, reco_trend, t_min_all, t_response, t_impact, min_val, t_recover, recovery_rate)

def calc_climatology_zscore(reco_matrix, doy_idx):
    """计算气候态 z-score 标准化"""
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
    
    # 及时释放中间变量
    del clim_mean, clim_std, full_mean, full_std
    
    return z_matrix

def process_chunk(chunk_info):
    """处理一个纬度块，优化内存使用"""
    chunk_id, lat_start, lat_end = chunk_info
    results = []
    
    try:
        lat_arr = _reco_ds.variables['lat'][lat_start:lat_end]
        n_lats = lat_end - lat_start
        
        # 读取 RECO 数据块
        reco_chunk = _reco_ds.variables['RECO'][:, lat_start:lat_end, :]
        if hasattr(reco_chunk, 'filled'):
            reco_chunk = reco_chunk.filled(np.nan).astype(np.float32)
        else:
            reco_chunk = reco_chunk.astype(np.float32)
        
        # 读取事件数据
        ec_chunk = _event_ds.variables['event_count'][lat_start:lat_end, :]
        # 处理 masked array
        if hasattr(ec_chunk, 'filled'):
            ec_chunk = ec_chunk.filled(0)
        
        max_ec = int(np.max(ec_chunk))
        if max_ec == 0:
            del reco_chunk, ec_chunk
            return chunk_id, np.array([], dtype=RESULT_DTYPE)
        
        # 读取骤旱事件信息 (使用 drought_start 而非 onset_start)
        sy_raw = _event_ds.variables['drought_start_year'][:max_ec, lat_start:lat_end, :]
        sd_raw = _event_ds.variables['drought_start_doy'][:max_ec, lat_start:lat_end, :]
        sy_chunk = sy_raw.filled(-1) if hasattr(sy_raw, 'filled') else sy_raw
        sd_chunk = sd_raw.filled(-1) if hasattr(sd_raw, 'filled') else sd_raw
        del sy_raw, sd_raw  # 及时删除原始数据
        
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
                    sy = int(sy_chunk[i, rel_lat, lon_idx])
                    sd = int(sd_chunk[i, rel_lat, lon_idx])
                    
                    if sy < START_YEAR or sy > END_YEAR or sd <= 0 or sd > 366:
                        continue
                    
                    onset = _year_offsets[sy] + sd - 1
                    ws, we = onset - WINDOW_BEFORE, onset + WINDOW_AFTER
                    
                    if ws < 0 or we >= len(reco_z):
                        continue
                    
                    m = process_single_event(
                        reco_z, ws, we,
                        THRESHOLD_RESPONSE, THRESHOLD_RECOVER,
                        CONSECUTIVE_DAYS, RESPONSE_SEARCH_WINDOW
                    )
                    
                    results.append((
                        lat_val, lon_val, i, sy, sd,
                        m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9]
                    ))
            del z_matrix  # 释放z分数矩阵
        
        # 释放所有chunk数据
        del reco_chunk, ec_chunk, sy_chunk, sd_chunk
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
    print("RECO Response Analysis - SMs Flash Drought Events (V11 Global)")
    print("=" * 70)
    print(f"开始时间: {datetime.now()}")
    print(f"骤旱事件文件: {DROUGHT_EVENTS_FILE}")
    print(f"RECO 数据文件: {RECO_FILE}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"工作进程数: {N_WORKERS}")
    print(f"纬度块大小: {LAT_CHUNK_SIZE}")
    
    # 打开文件获取维度信息
    with nc.Dataset(RECO_FILE, 'r') as ds:
        n_lat = len(ds.variables['lat'])
        n_lon = len(ds.variables['lon'])
        n_time = len(ds.variables['time'])
        lat_arr = ds.variables['lat'][:]
        lon_arr = ds.variables['lon'][:]
    
    print(f"\nRECO 数据维度: {n_time} x {n_lat} x {n_lon}")
    
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
    
    # 合并结果
    print("\n合并结果...")
    all_results = []
    temp_files = sorted([f for f in os.listdir(TEMP_DIR) if f.endswith('.npy')])
    
    for tf in tqdm(temp_files, desc="合并"):
        data = np.load(os.path.join(TEMP_DIR, tf))
        if len(data) > 0:
            all_results.append(data)
        del data  # 及时释放
    
    if len(all_results) > 0:
        merged = np.concatenate(all_results)
        del all_results
        gc.collect()
        print(f"合并后事件数: {len(merged)}")
        
        # 保存为 NetCDF
        output_file = os.path.join(OUTPUT_DIR, 'reco_response_SMs_drought_v11_global.nc')
        save_to_netcdf(merged, lat_arr, lon_arr, output_file)
    else:
        print("警告: 无有效结果!")
    
    # 清理临时文件
    print("\n清理临时文件...")
    shutil.rmtree(TEMP_DIR)
    
    print(f"\n完成时间: {datetime.now()}")

def save_to_netcdf(results, lat_arr, lon_arr, output_file):
    """保存结果到 NetCDF 文件"""
    print(f"保存到: {output_file}")
    
    with nc.Dataset(output_file, 'w', format='NETCDF4') as ds:
        # 创建维度
        ds.createDimension('event', len(results))
        ds.createDimension('lat', len(lat_arr))
        ds.createDimension('lon', len(lon_arr))
        
        # 坐标变量
        var_lat = ds.createVariable('lat_coord', 'f4', ('lat',))
        var_lat[:] = lat_arr
        var_lat.units = 'degrees_north'
        
        var_lon = ds.createVariable('lon_coord', 'f4', ('lon',))
        var_lon[:] = lon_arr
        var_lon.units = 'degrees_east'
        
        # 事件属性变量
        for field in RESULT_FIELDS:
            dtype_np = results.dtype[field]
            if 'f' in str(dtype_np):
                fill_val = np.nan
            elif 'i1' in str(dtype_np):  # int8: -128 到 127
                fill_val = -127
            elif 'i2' in str(dtype_np):  # int16: -32768 到 32767
                fill_val = -9999
            else:
                fill_val = None
            
            var = ds.createVariable(field, dtype_np, ('event',), fill_value=fill_val, 
                                   zlib=True, complevel=4)
            var[:] = results[field]
        
        # 添加属性说明
        ds.variables['response_detected'].long_name = 'RECO response detected (1=yes, 0=no)'
        ds.variables['reco_min'].long_name = 'Minimum RECO z-score during response period'
        ds.variables['reco_mean'].long_name = 'Mean RECO z-score during response period'
        ds.variables['reco_trend'].long_name = 'RECO z-score trend (slope) during response period'
        ds.variables['t_min'].long_name = 'Days to minimum RECO from drought onset'
        ds.variables['t_response'].long_name = 'Days to first response detection from drought onset'
        ds.variables['t_response'].comment = '-1 means no response detected within search window'
        ds.variables['t_impact'].long_name = 'Days from response detection to minimum'
        ds.variables['t_recover'].long_name = 'Days from minimum to recovery'
        ds.variables['recovery_rate'].long_name = 'Rate of recovery (z-score per day)'
        
        # 全局属性
        ds.title = 'RECO Response to SMs Flash Drought Events - Global Analysis (v11)'
        ds.source_drought = DROUGHT_EVENTS_FILE
        ds.source_reco = RECO_FILE
        ds.created = datetime.now().isoformat()
        ds.parameters = (f'WINDOW_BEFORE={WINDOW_BEFORE}, WINDOW_AFTER={WINDOW_AFTER}, '
                        f'THRESHOLD_RESPONSE={THRESHOLD_RESPONSE}, '
                        f'THRESHOLD_RECOVER={THRESHOLD_RECOVER}, '
                        f'CONSECUTIVE_DAYS={CONSECUTIVE_DAYS}, '
                        f'N_WORKERS={N_WORKERS}')
    
    file_size = os.path.getsize(output_file) / 1024 / 1024
    print(f"保存完成: {len(results)} 个事件, 文件大小: {file_size:.1f} MB")

if __name__ == '__main__':
    main()
