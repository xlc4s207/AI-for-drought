#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEE Response Analysis - Non-Flash Drought (SMrz) V11 Global
=============================================================
分析根系土壤湿度 (SMrz) 非骤旱干旱事件对 NEE 的影响

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
DROUGHT_EVENTS_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMrz_5.3/nonflash_drought_events_v5.nc")
NEE_FILE = "/data/BESS_V2/NEE_1982-2022_0.1deg.nc"
OUTPUT_DIR = os.path.join(BASE_DIR, "process/NEE-draught-analysis/code3_nonflash_SMrz/result")
TEMP_DIR = os.path.join(OUTPUT_DIR, "temp_chunks_nonflash_SMrz_nee_memopt")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

START_YEAR, END_YEAR = 1982, 2022
WINDOW_BEFORE = 60           # 干旱开始前的参考期 (天)
RECOVERY_WINDOW = 120        # 干旱结束后的恢复观察期 (天)
MAX_WINDOW_AFTER = 600       # 观测窗口上限 (天), 覆盖96.8%的事件

# NEE 响应阈值 (z-score)
THRESHOLD_RESPONSE = 0.5     # 响应检测阈值（NEE向碳源方向偏移）
THRESHOLD_RECOVER = 0.25     # 恢复判断阈值（从恶化状态回落）
CONSECUTIVE_DAYS = 3         # 连续天数确认

N_WORKERS = 8
LAT_CHUNK_SIZE = 2
LON_BATCH_SIZE = 256
OUTPUT_FILENAME = "nee_response_nonflash_SMrz_drought_v11_global_memopt.nc"

# 结果数据类型 — 增加了 drought_duration, drought_end_year, drought_end_doy
RESULT_DTYPE = np.dtype([
    ('lat', 'f4'), ('lon', 'f4'), ('event_id', 'i2'),
    ('drought_start_year', 'i2'), ('drought_start_doy', 'i2'),
    ('drought_end_year', 'i2'), ('drought_end_doy', 'i2'),
    ('drought_duration', 'i2'),       # 干旱持续天数 (SM < P20)
    ('actual_window_after', 'i2'),    # 实际观测窗口长度 (min(dur+120, 600))
    ('response_detected', 'i1'), ('nee_min', 'f4'), ('nee_mean', 'f4'),
    ('nee_trend', 'f4'), ('t_min', 'i2'), ('t_response', 'i2'),
    ('t_impact', 'i2'), ('amp_max', 'f4'), ('t_recover', 'f4'),
    ('recovery_rate', 'f4')
])

RESULT_FIELDS = list(RESULT_DTYPE.names)

# ============================================
# 全局变量 (子进程)
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
def process_single_event(nee_z, ws, we, window_before,
                         threshold_resp, threshold_recov, n_consec, max_search):
    """
    处理单个非骤旱干旱事件，分析 NEE 响应
    
    参数:
    - nee_z: z-score 标准化后的 NEE 时间序列 (全时段)
    - ws, we: 分析窗口起止索引 (ws = drought_start - WINDOW_BEFORE)
    - window_before: 干旱前参考期天数 (默认60)
    - threshold_resp: 响应检测阈值 (-0.5)
    - threshold_recov: 恢复判断阈值 (-0.25)
    - n_consec: 连续天数
    - max_search: 响应搜索最大天数 (= 实际观测窗口长度)
    
    返回:
    (response_detected, nee_min, nee_mean, nee_trend, t_min, t_response, 
     t_impact, amp_max, t_recover, recovery_rate)
    """
    segment = nee_z[ws:we+1]
    
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
    
    # 检测响应 — 搜索整个观测窗口 (非骤旱响应可出现在干旱全程+恢复期)
    actual_search = min(max_search, n_post)
    t_response = find_threshold_crossing(post, threshold_resp, n_consec, actual_search)
    
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
    
    return (1, nee_min, nee_mean, nee_trend, t_min_all, t_response,
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


def to_float32_with_nan(data):
    if hasattr(data, 'mask'):
        data = data.astype(np.float32)
        return np.ma.filled(data, np.nan)
    return np.asarray(data, dtype=np.float32)


def to_int_array(data, fill_value):
    if hasattr(data, 'filled'):
        return data.filled(fill_value)
    return np.asarray(data)

# ============================================
# 块处理函数
# ============================================
def process_chunk(chunk_info):
    """处理一个纬度块，按单纬线与经度批次降低内存峰值。"""
    chunk_id, lat_start, lat_end = chunk_info
    results = []
    
    try:
        n_time = len(_doy_idx)

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
                del nee_row
                continue

            max_ec = int(np.max(ec_row[lon_with_events]))
            sy_row = to_int_array(_event_ds.variables['drought_start_year'][:max_ec, lat_idx, lon_with_events], -1)
            sd_row = to_int_array(_event_ds.variables['drought_start_doy'][:max_ec, lat_idx, lon_with_events], -1)
            ey_row = to_int_array(_event_ds.variables['drought_end_year'][:max_ec, lat_idx, lon_with_events], -1)
            ed_row = to_int_array(_event_ds.variables['drought_end_doy'][:max_ec, lat_idx, lon_with_events], -1)
            dur_row = to_int_array(_event_ds.variables['duration'][:max_ec, lat_idx, lon_with_events], -1)

            for batch_start in range(0, len(good_rel_idx), LON_BATCH_SIZE):
                batch_rel = good_rel_idx[batch_start:batch_start + LON_BATCH_SIZE]
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
                        ey = int(ey_row[event_idx, rel_idx])
                        ed = int(ed_row[event_idx, rel_idx])
                        dur = int(dur_row[event_idx, rel_idx])

                        if sy < START_YEAR or sy > END_YEAR or sd <= 0 or sd > 366:
                            continue
                        if dur <= 0:
                            continue

                        actual_window = min(dur + RECOVERY_WINDOW, MAX_WINDOW_AFTER)
                        drought_start_idx = _year_offsets[sy] + sd - 1
                        ws = drought_start_idx - WINDOW_BEFORE
                        we = drought_start_idx + actual_window

                        if ws < 0 or we >= n_time:
                            continue

                        m = process_single_event(
                            nee_z, ws, we,
                            WINDOW_BEFORE,
                            THRESHOLD_RESPONSE, THRESHOLD_RECOVER,
                            CONSECUTIVE_DAYS, actual_window
                        )

                        results.append((
                            lat_val, lon_val, event_idx,
                            sy, sd, ey, ed,
                            min(dur, 32767),
                            min(actual_window, 32767),
                            int(m[0]), float(m[1]), float(m[2]), float(m[3]),
                            int(m[4]) if m[4] >= 0 else -1,
                            int(m[5]) if m[5] >= 0 else -1,
                            int(m[6]) if m[6] >= 0 else -1,
                            float(m[7]) if m[0] else float(m[1]),
                            float(m[8]), float(m[9])
                        ))

                del z_matrix, nee_good

            del nee_row, ec_row, sy_row, sd_row, ey_row, ed_row, dur_row
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

# ============================================
# 主函数
# ============================================
def main():
    print("=" * 70)
    print("NEE Response to Non-Flash Drought (SMrz) - V11 Global (MemOpt)")
    print("=" * 70)
    print(f"开始时间: {datetime.now()}")
    print(f"\n数据源:")
    print(f"  NEE: {NEE_FILE}")
    print(f"  非骤旱事件: {DROUGHT_EVENTS_FILE}")
    print(f"\n观测窗口设计:")
    print(f"  参考期: drought_start 前 {WINDOW_BEFORE} 天")
    print(f"  观测期: drought_start → drought_end + {RECOVERY_WINDOW} 天")
    print(f"  观测期上限: {MAX_WINDOW_AFTER} 天")
    print(f"  响应搜索: 整个观测窗口 (可变长度)")
    print(f"\n并行配置:")
    print(f"  工作进程: {N_WORKERS}")
    print(f"  纬度块大小: {LAT_CHUNK_SIZE}")
    print(f"  经度批大小: {LON_BATCH_SIZE}")
    
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
    
    # 流式写出结果
    print("\n流式写出结果...")
    temp_files = sorted([f for f in os.listdir(TEMP_DIR) if f.endswith('.npy')])

    if not temp_files:
        print("警告: 无有效结果!")
        return
    event_count = 0
    for tf in temp_files:
        arr = np.load(os.path.join(TEMP_DIR, tf))
        event_count += len(arr)
        del arr
    
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()
    
    print(f"\n总耗时: {elapsed/60:.1f} 分钟 ({elapsed/3600:.2f} 小时)")
    print(f"事件结果数: {event_count:,}")
    print(f"事件保留率: {event_count/total_events*100:.1f}%")

    print("\n保存最终结果...")
    out_file = os.path.join(OUTPUT_DIR, OUTPUT_FILENAME)
    save_chunks_to_netcdf(temp_files, out_file)
    
    # 清理临时文件
    print("清理临时文件...")
    shutil.rmtree(TEMP_DIR)
    
    print(f"\n完成时间: {datetime.now()}")
    print("✅ 非骤旱干旱 NEE 响应分析完成！")

def build_var_attrs():
    return {
        'drought_start_year': {'long_name': 'Year when SM drops below P20'},
        'drought_start_doy': {'long_name': 'DOY when SM drops below P20'},
        'drought_end_year': {'long_name': 'Year when SM recovers above P20'},
        'drought_end_doy': {'long_name': 'DOY when SM recovers above P20'},
        'drought_duration': {'long_name': 'Drought duration in days (SM < P20)', 'units': 'days'},
        'actual_window_after': {'long_name': 'Actual observation window (min(duration+120, 600))', 'units': 'days'},
        'response_detected': {'long_name': 'NEE deterioration detected (1=yes, 0=no)'},
        'nee_min': {'long_name': 'Minimum NEE z-score during observation period'},
        'nee_mean': {'long_name': 'Mean NEE z-score during observation period'},
        'nee_trend': {'long_name': 'NEE z-score trend (slope)'},
        't_min': {'long_name': 'Days to peak deterioration (max NEE z-score) from drought_start'},
        't_response': {
            'long_name': 'Days to first deterioration from drought_start',
            'comment': '-1 means no deterioration detected within observation window',
        },
        't_impact': {'long_name': 'Days from deterioration detection to peak deterioration'},
        'amp_max': {'long_name': 'Peak deterioration amplitude (max NEE z-score after response)'},
        't_recover': {'long_name': 'Days from peak deterioration to recovery'},
        'recovery_rate': {'long_name': 'Rate of recovery from peak deterioration (z-score per day)'},
    }


def save_chunks_to_netcdf(temp_files, output_file):
    """将临时块结果流式写入 NetCDF。"""
    print(f"保存到: {output_file}")

    global_attrs = {
        'title': 'NEE Response to Non-Flash SMrz Drought - Global Analysis (v11, memopt)',
        'description': 'Memory-optimized non-flash SMrz NEE response analysis with single-latitude reads, longitude batching, and streaming output.',
        'source_drought': DROUGHT_EVENTS_FILE,
        'source_nee': NEE_FILE,
        'created': datetime.now().isoformat(),
        'parameters': (f'WINDOW_BEFORE={WINDOW_BEFORE}, '
                       f'RECOVERY_WINDOW={RECOVERY_WINDOW}, '
                       f'MAX_WINDOW_AFTER={MAX_WINDOW_AFTER}, '
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
    )
    total_written = 0
    for tf in tqdm(temp_files, desc='写出'):
        arr = np.load(os.path.join(TEMP_DIR, tf))
        writer.append(arr)
        total_written += len(arr)
        del arr
    writer.close()

    file_size = os.path.getsize(output_file) / 1024 / 1024
    print(f"保存完成: {total_written:,} 个事件, 文件大小: {file_size:.1f} MB")

if __name__ == '__main__':
    main()
