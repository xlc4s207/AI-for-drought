#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPP Response Analysis - Non-Flash Drought (SMrz) V11 Global
=============================================================
分析根系土壤湿度 (SMrz) 非骤旱干旱事件对 GPP 的影响

与骤旱分析的核心区别：
  1. 输入事件: nonflash_drought_events_v5.nc (非骤旱干旱)
  2. 观测窗口: 可变的 — 从 drought_start 到 drought_end + 120天
     - 干旱开始点: drought_start (SM 低于 P20 的时刻)
     - 恢复观测期: 干旱结束后 120 天
     - 最大上限: MAX_WINDOW_AFTER = 600 天 (覆盖96.8%事件)
  3. 响应搜索范围: 整个观测窗口 (非骤旱干旱响应可能贯穿干旱全程)
  4. 输出增加: drought_duration, drought_end_year, drought_end_doy

关键参数:
  - WINDOW_BEFORE: 60天 (干旱前参考期, 用于z-score对比)
  - RECOVERY_WINDOW: 120天 (干旱结束后的恢复观察期)
  - MAX_WINDOW_AFTER: 600天 (观测窗口上限, 防止极端长旱越界)
  - 每个事件的实际窗口 = min(duration + 120, 600)

事件数统计:
  - 非骤旱事件总数: ~26,955,109
  - Duration 中位数: 69天, P90: 270天, P95: 366天
  - 实际总窗口: 中位 189天, P90 390天

内存优化:
  - 30 线程, 5行/块
  - 每块结果立即写磁盘
  - 及时 del + gc.collect()
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
DROUGHT_EVENTS_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMrz_5.3/nonflash_drought_events_v5.nc")
MERGED_GPP_FILE = os.path.join(BASE_DIR, "process/GPP-draught-analysis/SMrz_result/BESS_GPP_1982_2022.nc")
OUTPUT_DIR = os.path.join(BASE_DIR, "process/GPP-draught-analysis/code3_nonflash_SMrz/result")
TEMP_DIR = os.path.join(OUTPUT_DIR, "temp_chunks_nonflash_SMrz")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

START_YEAR, END_YEAR = 1982, 2022
WINDOW_BEFORE = 60           # 干旱开始前的参考期 (天)
RECOVERY_WINDOW = 120        # 干旱结束后的恢复观察期 (天)
MAX_WINDOW_AFTER = 600       # 观测窗口上限 (天), 覆盖96.8%的事件

# GPP 响应阈值 (z-score)
THRESHOLD_RESPONSE = -0.5    # 响应检测阈值
THRESHOLD_RECOVER = -0.25    # 恢复判断阈值
CONSECUTIVE_DAYS = 3         # 连续天数确认

N_WORKERS = 30
LAT_CHUNK_SIZE = 5

# 结果数据类型 — 增加了 drought_duration, drought_end_year, drought_end_doy
RESULT_DTYPE = np.dtype([
    ('lat', 'f4'), ('lon', 'f4'), ('event_id', 'i2'),
    ('drought_start_year', 'i2'), ('drought_start_doy', 'i2'),
    ('drought_end_year', 'i2'), ('drought_end_doy', 'i2'),
    ('drought_duration', 'i2'),       # 干旱持续天数 (SM < P20)
    ('actual_window_after', 'i2'),    # 实际观测窗口长度 (min(dur+120, 600))
    ('response_detected', 'i1'), ('gpp_min', 'f4'), ('gpp_mean', 'f4'),
    ('gpp_trend', 'f4'), ('t_min', 'i2'), ('t_response', 'i2'),
    ('t_impact', 'i2'), ('amp_max', 'f4'), ('t_recover', 'f4'),
    ('recovery_rate', 'f4')
])

RESULT_FIELDS = list(RESULT_DTYPE.names)

# ============================================
# 全局变量 (子进程)
# ============================================
_gpp_ds = None
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
    global _gpp_ds, _event_ds, _lon_arr, _year_offsets, _doy_idx
    _gpp_ds = nc.Dataset(MERGED_GPP_FILE, 'r')
    _event_ds = nc.Dataset(DROUGHT_EVENTS_FILE, 'r')
    _lon_arr = _gpp_ds.variables['lon'][:]
    _year_offsets = build_year_offsets()
    _doy_idx = build_doy_index()

# ============================================
# Numba 加速函数
# ============================================
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
def process_single_event(gpp_z, ws, we, window_before,
                         threshold_resp, threshold_recov, n_consec, max_search):
    """
    处理单个非骤旱干旱事件，分析 GPP 响应
    
    参数:
    - gpp_z: z-score 标准化后的 GPP 时间序列 (全时段)
    - ws, we: 分析窗口起止索引 (ws = drought_start - WINDOW_BEFORE)
    - window_before: 干旱前参考期天数 (默认60)
    - threshold_resp: 响应检测阈值 (-0.5)
    - threshold_recov: 恢复判断阈值 (-0.25)
    - n_consec: 连续天数
    - max_search: 响应搜索最大天数 (= 实际观测窗口长度)
    
    返回:
    (response_detected, gpp_min, gpp_mean, gpp_trend, t_min, t_response, 
     t_impact, amp_max, t_recover, recovery_rate)
    """
    segment = gpp_z[ws:we+1]
    
    if np.sum(~np.isnan(segment)) < 30:
        return (0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan)
    
    smoothed = smooth_causal(segment, 7)
    
    # 干旱前参考期 (前 window_before 天)
    pre_vals = []
    for i in range(min(window_before, len(smoothed))):
        if not np.isnan(smoothed[i]):
            pre_vals.append(smoothed[i])
    
    if len(pre_vals) < 5:
        return (0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan)
    
    # 干旱后的观察期 (从 drought_start 开始)
    post = smoothed[window_before:]
    n_post = len(post)
    
    if n_post < 10:
        return (0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan)
    
    # 计算基本统计量
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
    
    # 检测响应 — 搜索整个观测窗口 (非骤旱响应可出现在干旱全程+恢复期)
    actual_search = min(max_search, n_post)
    t_response = find_threshold_crossing(post, threshold_resp, n_consec, actual_search)
    
    if t_response == -1:
        return (0, gpp_min, gpp_mean, gpp_trend, t_min_all, -1, -1, np.nan, np.nan, np.nan)
    
    # 找到响应后的最小值
    t_min_local, min_val = -1, 1e9
    for i in range(t_response, n_post):
        if not np.isnan(post[i]) and post[i] < min_val:
            min_val = post[i]
            t_min_local = i
    
    if t_min_local == -1:
        return (1, gpp_min, gpp_mean, gpp_trend, t_min_all, t_response, -1, np.nan, np.nan, np.nan)
    
    t_impact = t_min_local - t_response
    
    # 检测恢复
    t_recover_idx = find_recovery(post, t_min_local + 1, threshold_recov, n_consec)
    if t_recover_idx == -1:
        t_recover, recovery_rate = np.nan, np.nan
    else:
        t_recover = float(t_recover_idx - t_min_local)
        recovery_rate = (threshold_recov - min_val) / t_recover if t_recover > 0 else np.nan
    
    return (1, gpp_min, gpp_mean, gpp_trend, t_min_all, t_response,
            t_impact, min_val, t_recover, recovery_rate)

# ============================================
# Z-score 标准化
# ============================================
def calc_climatology_zscore(gpp_matrix, doy_idx):
    """计算气候态 z-score 标准化"""
    n_time, n_pixels = gpp_matrix.shape
    clim_mean = np.full((366, n_pixels), np.nan, dtype=np.float32)
    clim_std = np.full((366, n_pixels), np.nan, dtype=np.float32)
    
    for d in range(366):
        mask = (doy_idx == d)
        if np.sum(mask) > 0:
            data = gpp_matrix[mask, :]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                clim_mean[d, :] = np.nanmean(data, axis=0)
                clim_std[d, :] = np.nanstd(data, axis=0, ddof=0)
    
    clim_std[clim_std < 0.01] = np.nan
    full_mean = clim_mean[doy_idx, :]
    full_std = clim_std[doy_idx, :]
    
    with np.errstate(divide='ignore', invalid='ignore'):
        z_matrix = (gpp_matrix - full_mean) / full_std
    
    del clim_mean, clim_std, full_mean, full_std
    return z_matrix

# ============================================
# 块处理函数
# ============================================
def process_chunk(chunk_info):
    """处理一个纬度块"""
    chunk_id, lat_start, lat_end = chunk_info
    results = []
    
    try:
        lat_arr = _gpp_ds.variables['lat'][lat_start:lat_end]
        n_lats = lat_end - lat_start
        n_time = len(_doy_idx)
        
        # 读取 GPP 数据块
        gpp_chunk = _gpp_ds.variables['GPP'][:, lat_start:lat_end, :]
        if hasattr(gpp_chunk, 'filled'):
            gpp_chunk = gpp_chunk.filled(np.nan).astype(np.float32)
        else:
            gpp_chunk = gpp_chunk.astype(np.float32)
        
        # 读取事件计数
        ec_chunk = _event_ds.variables['event_count'][lat_start:lat_end, :]
        if hasattr(ec_chunk, 'filled'):
            ec_chunk = ec_chunk.filled(0)
        
        max_ec = int(np.max(ec_chunk))
        if max_ec == 0:
            del gpp_chunk, ec_chunk
            return chunk_id, np.array([], dtype=RESULT_DTYPE)
        
        # 读取干旱事件信息 (使用 drought_start/end)
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
        del sy_raw, sd_raw, ey_raw, ed_raw, dur_raw
        
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
            del gpp_row, gpp_good
            
            for idx, lon_idx in enumerate(good_lon_indices):
                ec = int(ec_chunk[rel_lat, lon_idx])
                gpp_z = z_matrix[:, idx]
                lon_val = float(_lon_arr[lon_idx])
                
                for i in range(ec):
                    sy = int(sy_chunk[i, rel_lat, lon_idx])
                    sd = int(sd_chunk[i, rel_lat, lon_idx])
                    ey = int(ey_chunk[i, rel_lat, lon_idx])
                    ed = int(ed_chunk[i, rel_lat, lon_idx])
                    dur = int(dur_chunk[i, rel_lat, lon_idx])
                    
                    # 跳过无效事件
                    if sy < START_YEAR or sy > END_YEAR or sd <= 0 or sd > 366:
                        continue
                    if dur <= 0:
                        continue
                    
                    # 计算可变观测窗口: min(duration + 120, 600)
                    actual_window = min(dur + RECOVERY_WINDOW, MAX_WINDOW_AFTER)
                    
                    drought_start_idx = _year_offsets[sy] + sd - 1
                    ws = drought_start_idx - WINDOW_BEFORE
                    we = drought_start_idx + actual_window
                    
                    if ws < 0 or we >= n_time:
                        continue
                    
                    # 响应搜索范围 = 整个观测窗口
                    m = process_single_event(
                        gpp_z, ws, we,
                        WINDOW_BEFORE,
                        THRESHOLD_RESPONSE, THRESHOLD_RECOVER,
                        CONSECUTIVE_DAYS, actual_window
                    )
                    
                    results.append((
                        lat_val, lon_val, i,
                        sy, sd, ey, ed,
                        min(dur, 32767),       # drought_duration (i2 safe)
                        min(actual_window, 32767),  # actual_window_after
                        int(m[0]), float(m[1]), float(m[2]), float(m[3]),
                        int(m[4]) if m[4] >= 0 else -1,
                        int(m[5]) if m[5] >= 0 else -1,
                        int(m[6]) if m[6] >= 0 else -1,
                        float(m[7]) if m[0] else float(m[1]),
                        float(m[8]), float(m[9])
                    ))
            
            del z_matrix
        
        del gpp_chunk, ec_chunk, sy_chunk, sd_chunk, ey_chunk, ed_chunk, dur_chunk
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

# ============================================
# 主函数
# ============================================
def main():
    print("=" * 70)
    print("GPP Response to Non-Flash Drought (SMrz) - V11 Global")
    print("=" * 70)
    print(f"开始时间: {datetime.now()}")
    print(f"\n数据源:")
    print(f"  GPP: {MERGED_GPP_FILE}")
    print(f"  非骤旱事件: {DROUGHT_EVENTS_FILE}")
    print(f"\n观测窗口设计:")
    print(f"  参考期: drought_start 前 {WINDOW_BEFORE} 天")
    print(f"  观测期: drought_start → drought_end + {RECOVERY_WINDOW} 天")
    print(f"  观测期上限: {MAX_WINDOW_AFTER} 天")
    print(f"  响应搜索: 整个观测窗口 (可变长度)")
    print(f"\n并行配置:")
    print(f"  工作进程: {N_WORKERS}")
    print(f"  纬度块大小: {LAT_CHUNK_SIZE}")
    
    # 清理临时目录
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR)
    
    start_time = datetime.now()
    
    # 获取有效纬度范围
    with nc.Dataset(DROUGHT_EVENTS_FILE, 'r') as ds:
        ec_all = ds.variables['event_count'][:]
        if hasattr(ec_all, 'filled'):
            ec_all = ec_all.filled(0)
        
        lat_has_events = np.any(ec_all > 0, axis=1)
        valid_lat_indices = np.where(lat_has_events)[0]
        
        if len(valid_lat_indices) == 0:
            print("无有效事件!")
            return
        
        lat_start_idx = int(valid_lat_indices[0])
        lat_end_idx = int(valid_lat_indices[-1] + 1)
        total_events = int(np.sum(ec_all))
        del ec_all
    
    print(f"\n有效纬度范围: [{lat_start_idx}, {lat_end_idx}) ({lat_end_idx - lat_start_idx} 行)")
    print(f"总事件数: {total_events:,}")
    
    # 创建处理任务
    chunks = []
    chunk_id = 0
    for chunk_start in range(lat_start_idx, lat_end_idx, LAT_CHUNK_SIZE):
        chunk_end = min(chunk_start + LAT_CHUNK_SIZE, lat_end_idx)
        chunks.append((chunk_id, chunk_start, chunk_end))
        chunk_id += 1
    
    print(f"分块数: {len(chunks)}")
    print(f"\n开始并行处理...")
    
    # 并行处理
    total_saved = 0
    completed = 0
    
    with Pool(N_WORKERS, initializer=worker_init) as pool:
        try:
            for cid, result_arr in tqdm(pool.imap_unordered(process_chunk, chunks),
                                        total=len(chunks), desc="处理进度"):
                if len(result_arr) > 0:
                    temp_file = os.path.join(TEMP_DIR, f"chunk_{cid:04d}.npy")
                    np.save(temp_file, result_arr)
                    total_saved += len(result_arr)
                completed += 1
                del result_arr
                gc.collect()
        except KeyboardInterrupt:
            print("\n用户中断!")
            pool.terminate()
            pool.join()
        except Exception as e:
            print(f"\n处理出错: {e}")
            pool.terminate()
            pool.join()
    
    mid_time = datetime.now()
    print(f"\n已完成 {completed}/{len(chunks)} 个chunk")
    print(f"已保存 {total_saved:,} 个事件到临时文件")
    print(f"处理耗时: {(mid_time - start_time).total_seconds()/60:.1f} 分钟")
    
    # 合并结果
    print("\n合并临时文件...")
    temp_files = sorted([f for f in os.listdir(TEMP_DIR) if f.endswith('.npy')])
    
    all_results = []
    for tf in tqdm(temp_files, desc="合并"):
        arr = np.load(os.path.join(TEMP_DIR, tf))
        if len(arr) > 0:
            all_results.append(arr)
        del arr
    
    if not all_results:
        print("警告: 无有效结果!")
        return
    
    final_results = np.concatenate(all_results)
    del all_results
    gc.collect()
    
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()
    
    print(f"\n总耗时: {elapsed/60:.1f} 分钟 ({elapsed/3600:.2f} 小时)")
    print(f"事件结果数: {len(final_results):,}")
    print(f"事件保留率: {len(final_results)/total_events*100:.1f}%")
    
    n_with_response = np.sum(final_results['response_detected'] == 1)
    print(f"显著响应事件: {n_with_response:,} ({n_with_response/len(final_results)*100:.1f}%)")
    
    # 按干旱持续时间分组统计
    dur_arr = final_results['drought_duration']
    print(f"\n=== 按干旱持续时间分组统计 ===")
    bins = [(0, 30, "短旱(≤30天)"), (30, 90, "中旱(30-90天)"),
            (90, 180, "中长旱(90-180天)"), (180, 365, "长旱(180-365天)"),
            (365, 99999, "极长旱(>365天)")]
    for lo, hi, label in bins:
        mask = (dur_arr > lo) & (dur_arr <= hi)
        n = np.sum(mask)
        if n > 0:
            n_resp = np.sum(final_results['response_detected'][mask] == 1)
            print(f"  {label}: {n:,} 事件, 响应率 {n_resp/n*100:.1f}%")
    
    # 保存 NetCDF
    print("\n保存最终结果...")
    out_file = os.path.join(OUTPUT_DIR, "gpp_response_nonflash_SMrz_drought_v11_global.nc")
    save_to_netcdf(final_results, out_file)
    
    # 清理临时文件
    print("清理临时文件...")
    shutil.rmtree(TEMP_DIR)
    
    print(f"\n完成时间: {datetime.now()}")
    print("✅ 非骤旱干旱 GPP 响应分析完成！")

def save_to_netcdf(results, output_file):
    """保存结果到 NetCDF 文件"""
    print(f"保存到: {output_file}")
    
    with nc.Dataset(output_file, 'w', format='NETCDF4') as ds:
        ds.createDimension('event', len(results))
        
        for field in RESULT_FIELDS:
            dtype_np = results.dtype[field]
            if 'f' in str(dtype_np):
                fill_val = np.nan
            elif 'i1' in str(dtype_np):
                fill_val = -127
            elif 'i2' in str(dtype_np):
                fill_val = -9999
            else:
                fill_val = None
            
            var = ds.createVariable(field, dtype_np, ('event',),
                                   fill_value=fill_val, zlib=True, complevel=4)
            var[:] = results[field]
        
        # 变量属性
        ds.variables['drought_start_year'].long_name = 'Year when SM drops below P20'
        ds.variables['drought_start_doy'].long_name = 'DOY when SM drops below P20'
        ds.variables['drought_end_year'].long_name = 'Year when SM recovers above P20'
        ds.variables['drought_end_doy'].long_name = 'DOY when SM recovers above P20'
        ds.variables['drought_duration'].long_name = 'Drought duration in days (SM < P20)'
        ds.variables['drought_duration'].units = 'days'
        ds.variables['actual_window_after'].long_name = 'Actual observation window (min(duration+120, 600))'
        ds.variables['actual_window_after'].units = 'days'
        ds.variables['response_detected'].long_name = 'GPP response detected (1=yes, 0=no)'
        ds.variables['gpp_min'].long_name = 'Minimum GPP z-score during observation period'
        ds.variables['gpp_mean'].long_name = 'Mean GPP z-score during observation period'
        ds.variables['gpp_trend'].long_name = 'GPP z-score trend (slope)'
        ds.variables['t_min'].long_name = 'Days to minimum GPP from drought_start'
        ds.variables['t_response'].long_name = 'Days to first response from drought_start'
        ds.variables['t_response'].comment = '-1 means no response detected within observation window'
        ds.variables['t_impact'].long_name = 'Days from response detection to minimum'
        ds.variables['t_recover'].long_name = 'Days from minimum to recovery'
        ds.variables['recovery_rate'].long_name = 'Rate of recovery (z-score per day)'
        
        # 全局属性
        ds.title = 'GPP Response to Non-Flash SMrz Drought - Global Analysis (v11)'
        ds.description = ('Non-flash drought GPP response analysis with variable observation window. '
                          'Window = min(drought_duration + 120, 600) days from drought_start.')
        ds.source_drought = DROUGHT_EVENTS_FILE
        ds.source_gpp = MERGED_GPP_FILE
        ds.created = datetime.now().isoformat()
        ds.parameters = (f'WINDOW_BEFORE={WINDOW_BEFORE}, '
                        f'RECOVERY_WINDOW={RECOVERY_WINDOW}, '
                        f'MAX_WINDOW_AFTER={MAX_WINDOW_AFTER}, '
                        f'THRESHOLD_RESPONSE={THRESHOLD_RESPONSE}, '
                        f'THRESHOLD_RECOVER={THRESHOLD_RECOVER}, '
                        f'CONSECUTIVE_DAYS={CONSECUTIVE_DAYS}, '
                        f'N_WORKERS={N_WORKERS}, LAT_CHUNK_SIZE={LAT_CHUNK_SIZE}')
    
    file_size = os.path.getsize(output_file) / 1024 / 1024
    print(f"保存完成: {len(results):,} 个事件, 文件大小: {file_size:.1f} MB")

if __name__ == '__main__':
    main()
