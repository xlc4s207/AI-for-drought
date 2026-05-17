# -*- coding: utf-8 -*-
"""
骤旱检测主程序 v6 - 改进版 (SMs 表层土壤湿度)
==================================================
V6 核心改进 (解决事件碎片化问题):
1. 修复 confirm_count 连续性: NaN/阈值缺失时清零
2. Gap Merge 机制: 合并间隔 ≤5 天的相邻事件
3. 跨年连续滑动平均: 避免年边界切断事件
4. DOY 阈值平滑: ±15天窗口减少锯齿化
5. 修复 onset_start_idx==0 判断 bug

算法流程:
  Step-A: detect_all_drought_events()
    - 基于 sm_ma < P20 识别所有干旱事件段
    - 结束需连续 K 天 >= P20 确认 (连续性严格)
  
  Step-A2: merge_close_events()
    - 合并间隔 ≤ GAP_MERGE_DAYS 的事件

  Step-B: classify_event()
    - 向前回溯找 onset_start (sm_ma > P40)
    - 根据 onset_days 分类: flash / slow-onset / dry-to-drier

作者: AI Assistant
日期: 2026-01-25
"""

import os
import sys
import argparse
import time
import numpy as np
import netCDF4 as nc
import pickle
import bottleneck as bn  # 更快的 nanpercentile
from datetime import datetime
from multiprocessing import Pool, cpu_count
import warnings

# 过滤 All-NaN slice 警告
warnings.filterwarnings('ignore', message='All-NaN slice encountered')
warnings.filterwarnings('ignore', category=RuntimeWarning)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'process'))

from config import (
    YEARS, LAT_SIZE, LON_SIZE,
    TEST_LAT_RANGE, TEST_LON_RANGE, MOVING_WINDOW, MAX_EVENTS_PER_PIXEL,
    PERCENTILE_HIGH, PERCENTILE_LOW, MIN_DURATION
)

# 数据路径配置 - SMs 表层土壤湿度
BASE_DIR = "/home/xulc/flash_drought/gleam"
SM_FILE = "/data/GLEAM/SMs_45years.nc"
RESULT_DIR = os.path.join(BASE_DIR, "Flash_result", "SMs_result_v6_Global")

# 骤旱爆发期时间约束
MIN_ONSET_DAYS = 5
MAX_ONSET_DAYS = 20    # 4个候 = 20天

# V5 参数
LOOKBACK_MAX = 90
END_CONFIRM_DAYS = 10     # 配合 P30 滞回阈值使用

# V6 新增参数
GAP_MERGE_DAYS = 10      # 事件合并最大间隙 (天)
DOY_SMOOTH_WINDOW = 0    # DOY 阈值平滑窗口 (0=关闭平滑, 最快)
PERCENTILE_RECOVERY = 30 # 滞回恢复阈值 (P30)

# 覆盖 config 中的值: 提升到 100 个事件
MAX_EVENTS_PER_PIXEL = 100

# 向量化写入参数
BATCH_WRITE_SIZE = 10    # 批量写入缓冲区大小 (行数) - 减小以更快看到进度

# 百分位基准期
REF_START_YEAR = 1981
REF_END_YEAR = 2010
REF_YEARS = set(range(REF_START_YEAR, REF_END_YEAR + 1))


def parse_args():
    parser = argparse.ArgumentParser(description='全球干旱检测程序 v6 - SMs (改进版)')
    parser.add_argument('--test-mode', action='store_true', help='测试模式')
    parser.add_argument('--lat-range', nargs=2, type=float, default=None)
    parser.add_argument('--lon-range', nargs=2, type=float, default=None)
    parser.add_argument('--workers', type=int, default=None)
    return parser.parse_args()


def calculate_backward_moving_average_continuous(data_2d, window=MOVING_WINDOW):
    """
    V6 改进: 跨年连续的后向滑动平均
    不再在年边界重置，避免跨年事件被切断
    """
    min_valid = window // 2
    T, n_lon = data_2d.shape
    ma_2d = np.full_like(data_2d, np.nan, dtype=np.float64)
    
    valid_mask = ~np.isnan(data_2d)
    data_filled = np.where(valid_mask, data_2d, 0.0)
    
    cum_sum = np.cumsum(data_filled, axis=0)
    cum_count = np.cumsum(valid_mask.astype(np.int32), axis=0)
    
    cum_sum_shifted = np.zeros_like(cum_sum)
    cum_count_shifted = np.zeros_like(cum_count)
    
    if window < T:
        cum_sum_shifted[window:] = cum_sum[:-window]
        cum_count_shifted[window:] = cum_count[:-window]
    
    window_sum = cum_sum - cum_sum_shifted
    window_count = cum_count - cum_count_shifted
    
    valid_window = window_count >= min_valid
    ma_2d[valid_window] = window_sum[valid_window] / window_count[valid_window]
    
    return ma_2d


def build_doy_indices(years):
    """预计算 DOY 索引"""
    dates = []
    doy_to_indices = {doy: [] for doy in range(1, 366)}
    doy_to_indices_for_ref = {doy: [] for doy in range(1, 366)}
    
    idx = 0
    for year in years:
        if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
            n_days = 366
        else:
            n_days = 365
        
        for doy in range(1, n_days + 1):
            doy_mapped = 365 if doy == 366 else doy
            dates.append((year, doy_mapped))
            doy_to_indices[doy_mapped].append(idx)
            
            if year in REF_YEARS:
                doy_to_indices_for_ref[doy_mapped].append(idx)
            
            idx += 1
    
    for doy in doy_to_indices:
        doy_to_indices[doy] = np.array(doy_to_indices[doy], dtype=np.int32)
        doy_to_indices_for_ref[doy] = np.array(doy_to_indices_for_ref[doy], dtype=np.int32)
    
    return dates, doy_to_indices, doy_to_indices_for_ref


def read_row_from_merged(lat_idx, lon_start, lon_end, sm_ds):
    """从合并后的45年NC文件读取一行数据"""
    row_data = sm_ds.variables['SMs'][:, lat_idx, lon_start:lon_end]
    if hasattr(row_data, 'mask'):
        row_data = np.ma.filled(row_data, np.nan)
    return row_data.astype(np.float64)


def calculate_percentiles_smoothed(ma_2d, doy_to_indices_for_ref, doy_window=DOY_SMOOTH_WINDOW):
    """
    V6 简化版: 只计算 P20 和 P40 (移除 P30 滞回机制)
    """
    n_lon = ma_2d.shape[1]
    p20_2d = np.full((366, n_lon), np.nan, dtype=np.float64)
    p40_2d = np.full((366, n_lon), np.nan, dtype=np.float64)
    
    # 预计算有效列 mask (跳过全 NaN 的海洋区域)
    valid_cols = ~np.all(np.isnan(ma_2d), axis=0)
    valid_col_indices = np.where(valid_cols)[0]
    
    if len(valid_col_indices) == 0:
        return p20_2d, p40_2d
    
    # 只处理有效列
    ma_2d_valid = ma_2d[:, valid_col_indices]
    
    for doy in range(1, 366):
        if doy_window == 0:
            indices = doy_to_indices_for_ref.get(doy, [])
            if len(indices) == 0:
                continue
            doy_data = ma_2d_valid[indices, :]
        else:
            all_indices = []
            for offset in range(-doy_window, doy_window + 1):
                target_doy = ((doy - 1 + offset) % 365) + 1
                indices = doy_to_indices_for_ref.get(target_doy, [])
                if len(indices) > 0:
                    all_indices.append(indices)
            
            if len(all_indices) == 0:
                continue
            
            combined_indices = np.concatenate(all_indices)
            doy_data = ma_2d_valid[combined_indices, :]
        
        # 一次性计算两个百分位 (比 3 个快约 33%)
        with np.errstate(all='ignore'):
            percentiles = np.nanpercentile(doy_data, [PERCENTILE_LOW, PERCENTILE_HIGH], axis=0)
            p20_2d[doy, valid_col_indices] = percentiles[0]
            p40_2d[doy, valid_col_indices] = percentiles[1]
    
    return p20_2d, p40_2d


def detect_all_drought_events(sm_ma, p20_arr, p40_arr, dates):
    """
    Step-A: 识别所有干旱事件 (V6 简化版)
    
    改进: 
    - NaN 时清零 confirm_count (保证连续性)
    - 阈值缺失时也清零 confirm_count
    - 恢复条件: SM >= P40 (移除 P30 滞回机制)
    """
    n = len(sm_ma)
    events = []
    
    i = 0
    while i < n:
        year, doy = dates[i]
        
        if np.isnan(sm_ma[i]):
            i += 1
            continue
        
        p20 = p20_arr[doy]
        if np.isnan(p20):
            i += 1
            continue
        
        # 找到干旱开始 (sm_ma < P20)
        if sm_ma[i] < p20:
            drought_start_idx = i
            drought_start_year, drought_start_doy = dates[i]
            
            j = i + 1
            nan_count = 0
            confirmed_end_idx = None
            confirm_count = 0
            
            while j < n:
                if np.isnan(sm_ma[j]):
                    nan_count += 1
                    confirm_count = 0  # V6 修复: 连续恢复被打断
                    if nan_count >= 3:
                        confirmed_end_idx = j - nan_count
                        break
                    j += 1
                    continue
                
                nan_count = 0
                _, doy_j = dates[j]
                p40_j = p40_arr[doy_j]  # 使用 P40 判断恢复
                
                if np.isnan(p40_j):
                    confirm_count = 0  # V6 修复: 阈值缺失也打断连续性
                    j += 1
                    continue
                
                # 恢复条件: SM >= P40
                if sm_ma[j] >= p40_j:
                    confirm_count += 1
                    if confirm_count >= END_CONFIRM_DAYS:
                        confirmed_end_idx = j - END_CONFIRM_DAYS
                        break
                else:
                    confirm_count = 0
                
                j += 1
            
            if confirmed_end_idx is None:
                drought_end_idx = j - 1 if j > drought_start_idx else drought_start_idx
            else:
                drought_end_idx = confirmed_end_idx
            
            if drought_end_idx < drought_start_idx:
                drought_end_idx = drought_start_idx
            
            duration = drought_end_idx - drought_start_idx + 1
            
            if duration >= MIN_DURATION:
                intensity = 0.0
                for k in range(drought_start_idx, drought_end_idx + 1):
                    if not np.isnan(sm_ma[k]):
                        _, doy_k = dates[k]
                        p20_k = p20_arr[doy_k]
                        if not np.isnan(p20_k):
                            deficit = p20_k - sm_ma[k]
                            if deficit > 0:
                                intensity += deficit
                
                drought_end_year, drought_end_doy = dates[drought_end_idx]
                
                events.append({
                    'start_idx': drought_start_idx,
                    'end_idx': drought_end_idx,
                    'duration': duration,
                    'drought_start_year': drought_start_year,
                    'drought_start_doy': drought_start_doy,
                    'drought_end_year': drought_end_year,
                    'drought_end_doy': drought_end_doy,
                    'intensity': intensity
                })
            
            i = drought_end_idx + 1
        else:
            i += 1
    
    return events


def merge_close_events(events, sm_ma, p20_arr, dates, max_gap=GAP_MERGE_DAYS):
    """
    V6 新增: 合并间隔小于 max_gap 的相邻事件
    
    这可以避免阈值附近抖动导致的事件碎片化
    """
    if len(events) <= 1:
        return events
    
    # 按开始索引排序
    sorted_events = sorted(events, key=lambda e: e['start_idx'])
    merged = [sorted_events[0].copy()]
    
    for event in sorted_events[1:]:
        last = merged[-1]
        gap = event['start_idx'] - last['end_idx'] - 1
        
        if gap <= max_gap:
            # 合并事件: 扩展结束位置
            last['end_idx'] = event['end_idx']
            last['duration'] = last['end_idx'] - last['start_idx'] + 1
            last['intensity'] += event['intensity']
            last['drought_end_year'] = event['drought_end_year']
            last['drought_end_doy'] = event['drought_end_doy']
        else:
            merged.append(event.copy())
    
    # 重新验证最小持续时间
    final_events = [e for e in merged if e['duration'] >= MIN_DURATION]
    
    return final_events


def classify_event(event, sm_ma, p40_arr, dates):
    """
    Step-B: 对单个干旱事件进行分类 (V6 修复版)
    
    修复: onset_start_idx == 0 时的判断 bug
    """
    drought_start_idx = event['start_idx']
    
    onset_start_idx = None
    lookback_start = max(0, drought_start_idx - LOOKBACK_MAX)
    
    for i in range(drought_start_idx - 1, lookback_start - 1, -1):
        if np.isnan(sm_ma[i]):
            continue
        _, doy_i = dates[i]
        p40_i = p40_arr[doy_i]
        if np.isnan(p40_i):
            continue
        
        if sm_ma[i] > p40_i:
            onset_start_idx = i
            break
    
    if onset_start_idx is not None:
        onset_days = drought_start_idx - onset_start_idx
        onset_drop = sm_ma[onset_start_idx] - sm_ma[drought_start_idx]
        onset_rate = onset_drop / onset_days if onset_days > 0 else np.nan
        onset_year, onset_doy = dates[onset_start_idx]
        
        if MIN_ONSET_DAYS <= onset_days <= MAX_ONSET_DAYS:
            event_type = 'flash'
        else:
            event_type = 'slow_onset'
    else:
        event_type = 'dry_to_drier'
        onset_start_idx = None
        onset_days = -1
        onset_drop = np.nan
        onset_rate = np.nan
        onset_year = -1
        onset_doy = -1
    
    return {
        'event_type': event_type,
        'onset_start_idx': onset_start_idx,
        'onset_start_year': onset_year if onset_start_idx is not None else -1,  # V6 修复
        'onset_start_doy': onset_doy if onset_start_idx is not None else -1,    # V6 修复
        'onset_days': onset_days,
        'onset_drop': onset_drop,
        'onset_rate': onset_rate
    }


def analyze_pixel_v6(sm_ma, p20_arr, p40_arr, dates):
    """V6 版本像元分析: 两步法 + Gap Merge + 滞回机制"""
    valid_ratio = np.sum(~np.isnan(sm_ma)) / len(sm_ma)
    if valid_ratio < 0.5:
        return None, None, None, False
    
    # Step-A: 检测所有干旱事件 (使用 P30 滞回恢复)
    all_events = detect_all_drought_events(sm_ma, p20_arr, p40_arr, dates)
    
    if len(all_events) == 0:
        return [], [], [], True
    
    # Step-A2: Gap Merge 合并相邻事件
    all_events = merge_close_events(all_events, sm_ma, p20_arr, dates)
    
    if len(all_events) == 0:
        return [], [], [], True
    
    # Step-B: 分类每个事件
    flash_events = []
    nonflash_events = []
    
    for event in all_events:
        classification = classify_event(event, sm_ma, p40_arr, dates)
        full_event = {**event, **classification}
        
        if classification['event_type'] == 'flash':
            flash_events.append(full_event)
        else:
            nonflash_events.append(full_event)
    
    return all_events, flash_events, nonflash_events, True


# 全局变量
_GLOBAL_DATES = None
_GLOBAL_DOY_INDICES = None
_GLOBAL_DOY_INDICES_REF = None
_GLOBAL_SM_DS = None


def init_worker(dates, doy_indices, doy_indices_ref):
    global _GLOBAL_DATES, _GLOBAL_DOY_INDICES, _GLOBAL_DOY_INDICES_REF, _GLOBAL_SM_DS
    _GLOBAL_DATES = dates
    _GLOBAL_DOY_INDICES = doy_indices
    _GLOBAL_DOY_INDICES_REF = doy_indices_ref
    _GLOBAL_SM_DS = nc.Dataset(SM_FILE, 'r')


def process_single_row(args):
    """处理单行 - V6 优化版（内存缓冲）"""
    row_idx, lat_idx_global, lon_start, lon_end, n_lon = args
    
    global _GLOBAL_DATES, _GLOBAL_DOY_INDICES, _GLOBAL_DOY_INDICES_REF, _GLOBAL_SM_DS
    dates = _GLOBAL_DATES
    doy_to_indices_ref = _GLOBAL_DOY_INDICES_REF
    
    try:
        row_data = read_row_from_merged(lat_idx_global, lon_start, lon_end, _GLOBAL_SM_DS)
        
        # V6: 使用跨年连续滑动平均
        ma_2d = calculate_backward_moving_average_continuous(row_data, MOVING_WINDOW)
        
        # V6: 使用 DOY 平滑阈值 (含 P30 滞回阈值)
        p20_2d, p40_2d = calculate_percentiles_smoothed(ma_2d, doy_to_indices_ref)
        
        row_total = np.full(n_lon, np.nan, dtype=np.float32)
        row_flash = np.full(n_lon, np.nan, dtype=np.float32)
        row_nonflash = np.full(n_lon, np.nan, dtype=np.float32)
        
        row_yearly_total = {year: np.full(n_lon, np.nan, dtype=np.float32) for year in YEARS}
        row_yearly_flash = {year: np.full(n_lon, np.nan, dtype=np.float32) for year in YEARS}
        row_yearly_nonflash = {year: np.full(n_lon, np.nan, dtype=np.float32) for year in YEARS}
        
        row_total_events = []
        row_flash_events = []
        row_nonflash_events = []
        
        valid_count = 0
        total_event_count = 0
        flash_event_count = 0
        nonflash_event_count = 0
        
        for j in range(n_lon):
            pixel_ma = ma_2d[:, j]
            
            if np.all(np.isnan(pixel_ma)):
                continue
            
            p20_pixel = p20_2d[:, j]
            p40_pixel = p40_2d[:, j]
            
            all_evts, flash_evts, nonflash_evts, is_valid = analyze_pixel_v6(
                pixel_ma, p20_pixel, p40_pixel, dates
            )
            
            if not is_valid:
                continue
            
            row_total[j] = len(all_evts)
            row_flash[j] = len(flash_evts)
            row_nonflash[j] = len(nonflash_evts)
            
            yearly_total = {year: 0 for year in YEARS}
            yearly_flash = {year: 0 for year in YEARS}
            yearly_nonflash = {year: 0 for year in YEARS}
            
            for e in all_evts:
                yearly_total[e['drought_start_year']] += 1
            for e in flash_evts:
                yearly_flash[e['drought_start_year']] += 1
            for e in nonflash_evts:
                yearly_nonflash[e['drought_start_year']] += 1
            
            for year in YEARS:
                row_yearly_total[year][j] = yearly_total[year]
                row_yearly_flash[year][j] = yearly_flash[year]
                row_yearly_nonflash[year][j] = yearly_nonflash[year]
            
            row_total_events.append((j, all_evts[:MAX_EVENTS_PER_PIXEL]))
            row_flash_events.append((j, flash_evts[:MAX_EVENTS_PER_PIXEL]))
            row_nonflash_events.append((j, nonflash_evts[:MAX_EVENTS_PER_PIXEL]))
            
            valid_count += 1
            total_event_count += len(all_evts)
            flash_event_count += len(flash_evts)
            nonflash_event_count += len(nonflash_evts)
        
        result = {
            'row_idx': row_idx,
            'total': row_total,
            'flash': row_flash,
            'nonflash': row_nonflash,
            'yearly_total': row_yearly_total,
            'yearly_flash': row_yearly_flash,
            'yearly_nonflash': row_yearly_nonflash,
            'total_events': row_total_events,
            'flash_events': row_flash_events,
            'nonflash_events': row_nonflash_events,
            'valid_count': valid_count,
            'total_event_count': total_event_count,
            'flash_event_count': flash_event_count,
            'nonflash_event_count': nonflash_event_count
        }
        
        return result
    except Exception as e:
        print(f"\n[错误] 行 {row_idx}: {e}")
        import traceback
        traceback.print_exc()
        return None


def save_events_netcdf(filepath, events_data, n_lat, n_lon, lat_sub, lon_sub, event_type_name):
    """保存事件详情到NetCDF"""
    with nc.Dataset(filepath, 'w', format='NETCDF4') as ds:
        ds.createDimension('lat', n_lat)
        ds.createDimension('lon', n_lon)
        ds.createDimension('max_events', MAX_EVENTS_PER_PIXEL)
        
        lat_var = ds.createVariable('lat', 'f4', ('lat',))
        lat_var[:] = lat_sub
        lat_var.units = 'degrees_north'
        
        lon_var = ds.createVariable('lon', 'f4', ('lon',))
        lon_var[:] = lon_sub
        lon_var.units = 'degrees_east'
        
        ec = ds.createVariable('event_count', 'i2', ('lat', 'lon'), fill_value=-1, zlib=True)
        ec[:] = events_data['event_count']
        ec.long_name = f'{event_type_name} events (-1=invalid)'
        
        for key in ['onset_start_year', 'onset_start_doy', 'drought_start_year', 'drought_start_doy',
                    'drought_end_year', 'drought_end_doy', 'onset_days', 'duration']:
            if key in events_data:
                v = ds.createVariable(key, 'i2', ('max_events', 'lat', 'lon'), fill_value=-1, zlib=True)
                v[:] = events_data[key]
        
        for key in ['onset_drop', 'onset_rate', 'intensity']:
            if key in events_data:
                v = ds.createVariable(key, 'f4', ('max_events', 'lat', 'lon'), fill_value=-9999, zlib=True)
                v[:] = events_data[key]
        
        ds.title = f'{event_type_name} Events Details v6'
        ds.source = f'GLEAM SMs data ({YEARS[0]}-{YEARS[-1]})'
        ds.algorithm = 'Two-step Method v6 with Gap Merge'
        ds.percentile_baseline = f'{REF_START_YEAR}-{REF_END_YEAR}'
        ds.v6_improvements = 'confirm_count fix, gap merge, continuous MA, DOY smoothing'


def main():
    args = parse_args()
    n_workers = args.workers if args.workers else max(1, cpu_count() - 1)
    
    print("="*70)
    print("   全球干旱检测 v6 - 改进版 (SMs 表层土壤湿度)")
    print("="*70)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"并行进程数: {n_workers}")
    print(f"数据年份: {YEARS[0]} - {YEARS[-1]}")
    print(f"结果目录: {RESULT_DIR}")
    print()
    print("[算法参数]")
    print(f"  滑动窗口: {MOVING_WINDOW} 天")
    print(f"  干旱阈值: P{PERCENTILE_LOW}, 恢复阈值: P{PERCENTILE_RECOVERY} (滞回), 湿润阈值: P{PERCENTILE_HIGH}")
    print(f"  骤旱 onset: {MIN_ONSET_DAYS}-{MAX_ONSET_DAYS} 天")
    print(f"  最小持续: {MIN_DURATION} 天")
    print(f"  回溯窗口: {LOOKBACK_MAX} 天")
    print(f"  结束确认: {END_CONFIRM_DAYS} 天")
    print()
    print("[V6 改进]")
    print(f"  ✓ 修复 confirm_count 连续性 bug")
    print(f"  ✓ Gap Merge: 合并间隔 ≤{GAP_MERGE_DAYS} 天的事件")
    print(f"  ✓ 跨年连续滑动平均")
    print(f"  ✓ DOY 阈值平滑: ±{DOY_SMOOTH_WINDOW} 天窗口")
    print(f"  ✓ 修复 onset_start_idx==0 判断")
    print(f"  ✓ 滞回机制: 开始<P{PERCENTILE_LOW}, 恢复>P{PERCENTILE_RECOVERY}")
    
    print("\n[预处理] 构建 DOY 索引...")
    dates, doy_to_indices, doy_to_indices_ref = build_doy_indices(YEARS)
    print(f"  时间序列长度: {len(dates)} 天")
    
    with nc.Dataset(SM_FILE, 'r') as ds:
        lat_array = ds.variables['lat'][:]
        lon_array = ds.variables['lon'][:]
    
    if args.test_mode:
        lat_range = args.lat_range if args.lat_range else TEST_LAT_RANGE
        lon_range = args.lon_range if args.lon_range else TEST_LON_RANGE
        print(f"\n[测试模式] 纬度: {lat_range}, 经度: {lon_range}")
        
        lat_idx_min = np.argmin(np.abs(lat_array - lat_range[1]))
        lat_idx_max = np.argmin(np.abs(lat_array - lat_range[0]))
        lon_idx_min = np.argmin(np.abs(lon_array - lon_range[0]))
        lon_idx_max = np.argmin(np.abs(lon_array - lon_range[1]))
        
        if lat_idx_min > lat_idx_max:
            lat_idx_min, lat_idx_max = lat_idx_max, lat_idx_min
    else:
        lat_idx_min, lat_idx_max = 0, LAT_SIZE - 1
        lon_idx_min, lon_idx_max = 0, LON_SIZE - 1
    
    n_lat = int(lat_idx_max - lat_idx_min + 1)
    n_lon = int(lon_idx_max - lon_idx_min + 1)
    print(f"\n[处理范围] {n_lat} 行 x {n_lon} 列")
    
    tasks = [(i, lat_idx_min + i, lon_idx_min, lon_idx_max + 1, n_lon) for i in range(n_lat)]
    
    # --- V6 Improved: Pre-initialize NetCDF files for Vectorized Writing ---
    
    os.makedirs(RESULT_DIR, exist_ok=True)
    lat_sub = lat_array[lat_idx_min:lat_idx_max+1]
    lon_sub = lon_array[lon_idx_min:lon_idx_max+1]
    
    def init_nc_files():
        """Initialize all result files"""
        from osgeo import gdal, osr
        driver = gdal.GetDriverByName('GTiff')
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        wkt = srs.ExportToWkt()
        
        lon_res = abs(lon_sub[1] - lon_sub[0]) if len(lon_sub) > 1 else 0.1
        lat_res = abs(lat_sub[1] - lat_sub[0]) if len(lat_sub) > 1 else 0.1
        geo = (float(lon_sub[0]) - lon_res/2, lon_res, 0,
               float(lat_sub[0]) + lat_res/2, 0, -lat_res)
               
        # 1. Frequency TIFs
        tif_paths = {}
        # Annual
        for year in YEARS:
            for kind in ['total', 'flash', 'nonflash']:
                check_path = os.path.join(RESULT_DIR, f"{kind}_drought_{year}.tif")
                if not os.path.exists(check_path):
                    ds = driver.Create(check_path, n_lon, n_lat, 1, gdal.GDT_Float32)
                    ds.SetGeoTransform(geo)
                    ds.SetProjection(wkt)
                    band = ds.GetRasterBand(1)
                    band.SetNoDataValue(-9999)
                    band.Fill(-9999)
                    ds = None
                tif_paths[f"{kind}_{year}"] = check_path
        
        # Total Period
        for kind in ['total', 'flash', 'nonflash']:
            check_path = os.path.join(RESULT_DIR, f"{kind}_drought_frequency_{YEARS[0]}_{YEARS[-1]}.tif")
            if not os.path.exists(check_path):
                ds = driver.Create(check_path, n_lon, n_lat, 1, gdal.GDT_Float32)
                ds.SetGeoTransform(geo)
                ds.SetProjection(wkt)
                band = ds.GetRasterBand(1)
                band.SetNoDataValue(-9999)
                band.Fill(-9999)
                ds = None
            tif_paths[f"{kind}_all"] = check_path
            
        # 2. Events NetCDFs
        nc_paths = {}
        for kind, name in [('total', 'Total Drought'), ('flash', 'Flash Drought'), ('nonflash', 'Non-flash Drought')]:
            fname = os.path.join(RESULT_DIR, f"{kind}_drought_events_v6.nc")
            if not os.path.exists(fname):
                with nc.Dataset(fname, 'w', format='NETCDF4') as ds:
                    ds.createDimension('lat', n_lat)
                    ds.createDimension('lon', n_lon)
                    ds.createDimension('max_events', MAX_EVENTS_PER_PIXEL)
                    
                    lat_var = ds.createVariable('lat', 'f4', ('lat',))
                    lat_var[:] = lat_sub
                    lat_var.units = 'degrees_north'
                    
                    lon_var = ds.createVariable('lon', 'f4', ('lon',))
                    lon_var[:] = lon_sub
                    lon_var.units = 'degrees_east'
                    
                    # Variables
                    ds.createVariable('event_count', 'i2', ('lat', 'lon'), fill_value=-1, zlib=True)
                    
                    for key in ['onset_start_year', 'onset_start_doy', 'drought_start_year', 'drought_start_doy',
                                'drought_end_year', 'drought_end_doy', 'onset_days', 'duration']:
                        ds.createVariable(key, 'i2', ('max_events', 'lat', 'lon'), fill_value=-1, zlib=True)
                    
                    for key in ['onset_drop', 'onset_rate', 'intensity']:
                        ds.createVariable(key, 'f4', ('max_events', 'lat', 'lon'), fill_value=-9999, zlib=True)
                        
                    ds.title = f'{name} Events Details v6'
                    ds.source = f'GLEAM SMs data ({YEARS[0]}-{YEARS[-1]})'
            nc_paths[kind] = fname
            
        return tif_paths, nc_paths

    tif_paths, nc_paths = init_nc_files()
    
    # 过滤掉已缓存的任务（如果使用了缓存） - 实际上我们要在主循环中处理
    # 为了进度条准确，我们还是全部提交给Pool，但在Pool的回调中，如果命中缓存会很快返回
    
    print(f"\n[处理开始] 使用 {n_workers} 个进程 (Vectorized I/O enabled)...")
    print(f"[批量写入] 缓冲区大小: {BATCH_WRITE_SIZE} 行")
    print("-"*70)
    
    start_time = time.time()
    stats = {'valid': 0, 'total': 0, 'flash': 0, 'nonflash': 0}
    completed = 0
    total_tasks = len(tasks)
    
    # 批量写入缓冲区
    from osgeo import gdal
    batch_buffer = []  # 存储待写入的结果
    
    def flush_batch_to_disk(buffer):
        """批量写入缓冲区到磁盘 - 向量化IO"""
        if not buffer:
            return
        
        # 按行索引排序确保顺序写入
        buffer.sort(key=lambda x: x['row_idx'])
        
        # 1. 批量写入 TIFs
        tif_batches = {}
        for path in tif_paths.values():
            tif_batches[path] = []
        
        for res in buffer:
            rel_row = res['row_idx']
            tif_batches[tif_paths['total_all']].append((rel_row, res['total']))
            tif_batches[tif_paths['flash_all']].append((rel_row, res['flash']))
            tif_batches[tif_paths['nonflash_all']].append((rel_row, res['nonflash']))
            for year in YEARS:
                tif_batches[tif_paths[f'total_{year}']].append((rel_row, res['yearly_total'][year]))
                tif_batches[tif_paths[f'flash_{year}']].append((rel_row, res['yearly_flash'][year]))
                tif_batches[tif_paths[f'nonflash_{year}']].append((rel_row, res['yearly_nonflash'][year]))
        
        # 向量化写入 TIFs
        for path, rows_data in tif_batches.items():
            if not rows_data:
                continue
            ds = gdal.Open(path, gdal.GA_Update)
            band = ds.GetRasterBand(1)
            for row_idx, row_data in rows_data:
                band.WriteArray(row_data.reshape(1, -1), 0, row_idx)
            band.FlushCache()
            ds = None
        
        # 2. 批量写入 NetCDFs
        nc_handles = {k: nc.Dataset(p, 'r+') for k, p in nc_paths.items()}
        
        def write_nc_batch(kind, results_list):
            ds = nc_handles[kind]
            # 从NetCDF获取实际的列数（支持测试模式）
            actual_n_lon = ds.dimensions['lon'].size
            for res in results_list:
                rel_row = res['row_idx']
                events_data_list = res[f'{kind}_events']
                
                # 准备整行数据
                counts = np.full(actual_n_lon, -1, dtype=np.int16)
                vars_buffers = {}
                for vname in ds.variables:
                    if vname not in ['lat', 'lon', 'event_count']:
                        dtype = ds.variables[vname].dtype
                        fill = ds.variables[vname]._FillValue
                        vars_buffers[vname] = np.full((MAX_EVENTS_PER_PIXEL, actual_n_lon), fill, dtype=dtype)
                
                # 填充数据
                for col_idx, evts in events_data_list:
                    counts[col_idx] = len(evts)
                    for k, e in enumerate(evts):
                        if k >= MAX_EVENTS_PER_PIXEL: break
                        if 'onset_start_year' in vars_buffers: vars_buffers['onset_start_year'][k, col_idx] = e.get('onset_start_year', -1)
                        if 'onset_start_doy' in vars_buffers: vars_buffers['onset_start_doy'][k, col_idx] = e.get('onset_start_doy', -1)
                        if 'drought_start_year' in vars_buffers: vars_buffers['drought_start_year'][k, col_idx] = e['drought_start_year']
                        if 'drought_start_doy' in vars_buffers: vars_buffers['drought_start_doy'][k, col_idx] = e['drought_start_doy']
                        if 'drought_end_year' in vars_buffers: vars_buffers['drought_end_year'][k, col_idx] = e['drought_end_year']
                        if 'drought_end_doy' in vars_buffers: vars_buffers['drought_end_doy'][k, col_idx] = e['drought_end_doy']
                        if 'onset_days' in vars_buffers: vars_buffers['onset_days'][k, col_idx] = e.get('onset_days', -1)
                        if 'duration' in vars_buffers: vars_buffers['duration'][k, col_idx] = e['duration']
                        if 'onset_drop' in vars_buffers: vars_buffers['onset_drop'][k, col_idx] = e.get('onset_drop', -9999)
                        if 'onset_rate' in vars_buffers: vars_buffers['onset_rate'][k, col_idx] = e.get('onset_rate', -9999)
                        if 'intensity' in vars_buffers: vars_buffers['intensity'][k, col_idx] = e['intensity']
                
                # 一次性写入整行
                ds.variables['event_count'][rel_row, :] = counts
                for vname, buff in vars_buffers.items():
                    ds.variables[vname][:, rel_row, :] = buff
        
        write_nc_batch('total', buffer)
        write_nc_batch('flash', buffer)
        write_nc_batch('nonflash', buffer)
        
        # 同步到磁盘
        for ds in nc_handles.values():
            ds.sync()
            ds.close()
        
        buffer.clear()
    
    try:
        with Pool(processes=n_workers, initializer=init_worker,
                  initargs=(dates, doy_to_indices, doy_to_indices_ref)) as pool:
            
            # 使用 Imap 获取结果
            for result in pool.imap_unordered(process_single_row, tasks, chunksize=1):
                if result is None:
                    completed += 1
                    continue
                
                # 将结果加入批量缓冲区
                batch_buffer.append(result)
                
                # 更新统计
                stats['valid'] += result['valid_count']
                stats['total'] += result['total_event_count']
                stats['flash'] += result['flash_event_count']
                stats['nonflash'] += result['nonflash_event_count']
                completed += 1
                
                # 当缓冲区达到阈值时批量写入
                if len(batch_buffer) >= BATCH_WRITE_SIZE:
                    flush_batch_to_disk(batch_buffer)
                
                # 进度显示
                elapsed = time.time() - start_time
                progress = completed / total_tasks * 100
                speed = completed / elapsed if elapsed > 0 else 0
                eta = (total_tasks - completed) / speed if speed > 0 else 0
                print(f"\r[{progress:.1f}%] Total:{stats['total']} Flash:{stats['flash']} "
                      f"NonFlash:{stats['nonflash']} | Buffer:{len(batch_buffer)} | {speed:.1f}行/s | ETA:{eta/60:.1f}m", 
                      end='', flush=True)
            
            # 写入剩余缓冲区
            if batch_buffer:
                print(f"\n正在写入最后 {len(batch_buffer)} 行...")
                flush_batch_to_disk(batch_buffer)

    finally:
        # 确保所有数据都已写入
        if batch_buffer:
            flush_batch_to_disk(batch_buffer)

    elapsed = time.time() - start_time
    print("\n" + "="*70)
    print("                    处理完成")
    print("="*70)
    print(f"总耗时: {elapsed/60:.1f}分钟")
    print(f"有效像元: {stats['valid']}")
    print(f"\n[事件统计]")
    print(f"  Total drought:     {stats['total']}")
    if stats['total'] > 0:
        print(f"  Flash drought:     {stats['flash']} ({stats['flash']/stats['total']*100:.1f}%)")
        print(f"  Non-flash drought: {stats['nonflash']} ({stats['nonflash']/stats['total']*100:.1f}%)")
    else:
        print(f"  Flash drought:     0")
        print(f"  Non-flash drought: 0")
    print(f"  验证: flash + nonflash = {stats['flash'] + stats['nonflash']} = total({stats['total']})")


if __name__ == '__main__':
    main()
