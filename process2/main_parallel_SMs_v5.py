# -*- coding: utf-8 -*-
"""
骤旱检测主程序 v5 - 完整干旱分类版 (SMs 表层土壤湿度)
==================================================
核心改进:
1. 两步法: 先识别所有干旱事件，再分类 (flash vs non-flash)
2. 输出三类结果: Total drought / Flash drought / Non-flash drought
3. 保证 total = flash + non-flash (严格互斥)

算法流程:
  Step-A: detect_all_drought_events()
    - 基于 sm_ma < P20 识别所有干旱事件段
    - 结束需连续 K 天 >= P20 确认

  Step-B: classify_event()
    - 向前回溯找 onset_start (sm_ma > P40)
    - 根据 onset_days 分类: flash / slow-onset / dry-to-drier

作者: AI Assistant
日期: 2026-01-23
"""

import os
import sys
import argparse
import time
import numpy as np
import netCDF4 as nc
from datetime import datetime
from multiprocessing import Pool, cpu_count

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'process'))

from config import (
    YEARS, LAT_SIZE, LON_SIZE,
    TEST_LAT_RANGE, TEST_LON_RANGE, MOVING_WINDOW, MAX_EVENTS_PER_PIXEL,
    PERCENTILE_HIGH, PERCENTILE_LOW, MIN_DURATION
)

# 数据路径配置 - SMs 表层土壤湿度
BASE_DIR = "/home/xulc/flash_drought/gleam"
SM_FILE = "/data/GLEAM/SMs_45years.nc"
RESULT_DIR = os.path.join(BASE_DIR, "result", "SMs_result_v5")

# 骤旱爆发期时间约束
MIN_ONSET_DAYS = 5
MAX_ONSET_DAYS = 30

# V5 新增参数
LOOKBACK_MAX = 90
END_CONFIRM_DAYS = 3

# 百分位基准期
REF_START_YEAR = 1981
REF_END_YEAR = 2010
REF_YEARS = set(range(REF_START_YEAR, REF_END_YEAR + 1))


def parse_args():
    parser = argparse.ArgumentParser(description='全球干旱检测程序 v5 - SMs')
    parser.add_argument('--test-mode', action='store_true', help='测试模式')
    parser.add_argument('--lat-range', nargs=2, type=float, default=None)
    parser.add_argument('--lon-range', nargs=2, type=float, default=None)
    parser.add_argument('--workers', type=int, default=None)
    return parser.parse_args()


def calculate_backward_moving_average_by_year(data_2d, dates, window=MOVING_WINDOW):
    """按年重置的后向滑动平均"""
    min_valid = window // 2
    T, n_lon = data_2d.shape
    ma_2d = np.full_like(data_2d, np.nan, dtype=np.float64)
    
    year_boundaries = []
    current_year = dates[0][0]
    start_idx = 0
    
    for i, (year, doy) in enumerate(dates):
        if year != current_year:
            year_boundaries.append((start_idx, i))
            start_idx = i
            current_year = year
    year_boundaries.append((start_idx, T))
    
    for year_start, year_end in year_boundaries:
        year_len = year_end - year_start
        year_data = data_2d[year_start:year_end, :]
        
        valid_mask = ~np.isnan(year_data)
        data_filled = np.where(valid_mask, year_data, 0.0)
        
        cum_sum = np.cumsum(data_filled, axis=0)
        cum_count = np.cumsum(valid_mask.astype(np.int32), axis=0)
        
        cum_sum_shifted = np.zeros_like(cum_sum)
        cum_count_shifted = np.zeros_like(cum_count)
        
        if window < year_len:
            cum_sum_shifted[window:] = cum_sum[:-window]
            cum_count_shifted[window:] = cum_count[:-window]
        
        window_sum = cum_sum - cum_sum_shifted
        window_count = cum_count - cum_count_shifted
        
        valid_window = window_count >= min_valid
        year_ma = np.full_like(year_data, np.nan, dtype=np.float64)
        year_ma[valid_window] = window_sum[valid_window] / window_count[valid_window]
        
        ma_2d[year_start:year_end, :] = year_ma
    
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


def calculate_percentiles_batch(ma_2d, doy_to_indices_for_ref):
    """使用基准期 1981-2010 计算 P20/P40"""
    n_lon = ma_2d.shape[1]
    p20_2d = np.full((366, n_lon), np.nan, dtype=np.float64)
    p40_2d = np.full((366, n_lon), np.nan, dtype=np.float64)
    
    for doy in range(1, 366):
        indices = doy_to_indices_for_ref.get(doy)
        if indices is None or len(indices) == 0:
            continue
        
        doy_data = ma_2d[indices, :]
        
        with np.errstate(all='ignore'):
            p20_2d[doy, :] = np.nanpercentile(doy_data, PERCENTILE_LOW, axis=0)
            p40_2d[doy, :] = np.nanpercentile(doy_data, PERCENTILE_HIGH, axis=0)
    
    return p20_2d, p40_2d


def detect_all_drought_events(sm_ma, p20_arr, dates):
    """Step-A: 识别所有干旱事件"""
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
                    if nan_count >= 3:
                        confirmed_end_idx = j - nan_count
                        break
                    j += 1
                    continue
                
                nan_count = 0
                _, doy_j = dates[j]
                p20_j = p20_arr[doy_j]
                
                if np.isnan(p20_j):
                    j += 1
                    continue
                
                if sm_ma[j] >= p20_j:
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


def classify_event(event, sm_ma, p40_arr, dates):
    """Step-B: 对单个干旱事件进行分类"""
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
        'onset_start_year': onset_year if onset_start_idx else -1,
        'onset_start_doy': onset_doy if onset_start_idx else -1,
        'onset_days': onset_days,
        'onset_drop': onset_drop,
        'onset_rate': onset_rate
    }


def analyze_pixel_v5(sm_ma, p20_arr, p40_arr, dates):
    """V5 版本像元分析"""
    valid_ratio = np.sum(~np.isnan(sm_ma)) / len(sm_ma)
    if valid_ratio < 0.5:
        return None, None, None, False
    
    all_events = detect_all_drought_events(sm_ma, p20_arr, dates)
    
    if len(all_events) == 0:
        return [], [], [], True
    
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
    """处理单行 - V5 版本"""
    row_idx, lat_idx_global, lon_start, lon_end, n_lon = args
    
    global _GLOBAL_DATES, _GLOBAL_DOY_INDICES, _GLOBAL_DOY_INDICES_REF, _GLOBAL_SM_DS
    dates = _GLOBAL_DATES
    doy_to_indices_ref = _GLOBAL_DOY_INDICES_REF
    
    try:
        row_data = read_row_from_merged(lat_idx_global, lon_start, lon_end, _GLOBAL_SM_DS)
        ma_2d = calculate_backward_moving_average_by_year(row_data, dates, MOVING_WINDOW)
        p20_2d, p40_2d = calculate_percentiles_batch(ma_2d, doy_to_indices_ref)
        
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
            
            all_evts, flash_evts, nonflash_evts, is_valid = analyze_pixel_v5(
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
        
        return {
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
        
        ds.title = f'{event_type_name} Events Details v5'
        ds.source = f'GLEAM SMs data ({YEARS[0]}-{YEARS[-1]})'
        ds.algorithm = 'Two-step Method v5'
        ds.percentile_baseline = f'{REF_START_YEAR}-{REF_END_YEAR}'


def main():
    args = parse_args()
    n_workers = args.workers if args.workers else max(1, cpu_count() - 1)
    
    print("="*70)
    print("   全球干旱检测 v5 - 完整分类版 (SMs 表层土壤湿度)")
    print("="*70)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"并行进程数: {n_workers}")
    print(f"数据年份: {YEARS[0]} - {YEARS[-1]}")
    print(f"结果目录: {RESULT_DIR}")
    print()
    print("[算法参数]")
    print(f"  滑动窗口: {MOVING_WINDOW} 天")
    print(f"  干旱阈值: P{PERCENTILE_LOW}, 湿润阈值: P{PERCENTILE_HIGH}")
    print(f"  骤旱 onset: {MIN_ONSET_DAYS}-{MAX_ONSET_DAYS} 天")
    print(f"  最小持续: {MIN_DURATION} 天")
    print(f"  回溯窗口: {LOOKBACK_MAX} 天")
    print(f"  结束确认: {END_CONFIRM_DAYS} 天")
    print()
    print("[V5 特性]")
    print("  ✓ 两步法: 先检测全部干旱，再分类")
    print("  ✓ 三类输出: Total / Flash / Non-flash")
    print("  ✓ 保证 Total = Flash + Non-flash")
    
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
    
    n_lat = lat_idx_max - lat_idx_min + 1
    n_lon = lon_idx_max - lon_idx_min + 1
    print(f"\n[处理范围] {n_lat} 行 x {n_lon} 列")
    
    tasks = [(i, lat_idx_min + i, lon_idx_min, lon_idx_max + 1, n_lon) for i in range(n_lat)]
    
    freq_total = np.full((n_lat, n_lon), np.nan, dtype=np.float32)
    freq_flash = np.full((n_lat, n_lon), np.nan, dtype=np.float32)
    freq_nonflash = np.full((n_lat, n_lon), np.nan, dtype=np.float32)
    
    yearly_total = {year: np.full((n_lat, n_lon), np.nan, dtype=np.float32) for year in YEARS}
    yearly_flash = {year: np.full((n_lat, n_lon), np.nan, dtype=np.float32) for year in YEARS}
    yearly_nonflash = {year: np.full((n_lat, n_lon), np.nan, dtype=np.float32) for year in YEARS}
    
    def init_events_data():
        return {
            'event_count': np.full((n_lat, n_lon), -1, dtype=np.int16),
            'onset_start_year': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
            'onset_start_doy': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
            'drought_start_year': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
            'drought_start_doy': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
            'drought_end_year': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
            'drought_end_doy': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
            'onset_days': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
            'duration': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
            'onset_drop': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -9999, dtype=np.float32),
            'onset_rate': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -9999, dtype=np.float32),
            'intensity': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -9999, dtype=np.float32),
        }
    
    total_events_data = init_events_data()
    flash_events_data = init_events_data()
    nonflash_events_data = init_events_data()
    
    print(f"\n[处理开始] 使用 {n_workers} 个进程...")
    print("-"*70)
    
    start_time = time.time()
    stats = {'valid': 0, 'total': 0, 'flash': 0, 'nonflash': 0}
    completed = 0
    
    with Pool(processes=n_workers, initializer=init_worker,
              initargs=(dates, doy_to_indices, doy_to_indices_ref)) as pool:
        for result in pool.imap_unordered(process_single_row, tasks, chunksize=4):
            if result is None:
                completed += 1
                continue
            
            row_idx = result['row_idx']
            freq_total[row_idx] = result['total']
            freq_flash[row_idx] = result['flash']
            freq_nonflash[row_idx] = result['nonflash']
            
            for year in YEARS:
                yearly_total[year][row_idx] = result['yearly_total'][year]
                yearly_flash[year][row_idx] = result['yearly_flash'][year]
                yearly_nonflash[year][row_idx] = result['yearly_nonflash'][year]
            
            def save_row_events(events_list, events_data):
                for j, evts in events_list:
                    events_data['event_count'][row_idx, j] = len(evts)
                    for k, e in enumerate(evts):
                        events_data['onset_start_year'][k, row_idx, j] = e.get('onset_start_year', -1)
                        events_data['onset_start_doy'][k, row_idx, j] = e.get('onset_start_doy', -1)
                        events_data['drought_start_year'][k, row_idx, j] = e['drought_start_year']
                        events_data['drought_start_doy'][k, row_idx, j] = e['drought_start_doy']
                        events_data['drought_end_year'][k, row_idx, j] = e['drought_end_year']
                        events_data['drought_end_doy'][k, row_idx, j] = e['drought_end_doy']
                        events_data['onset_days'][k, row_idx, j] = e.get('onset_days', -1)
                        events_data['duration'][k, row_idx, j] = e['duration']
                        events_data['onset_drop'][k, row_idx, j] = e.get('onset_drop', -9999)
                        events_data['onset_rate'][k, row_idx, j] = e.get('onset_rate', -9999)
                        events_data['intensity'][k, row_idx, j] = e['intensity']
            
            save_row_events(result['total_events'], total_events_data)
            save_row_events(result['flash_events'], flash_events_data)
            save_row_events(result['nonflash_events'], nonflash_events_data)
            
            stats['valid'] += result['valid_count']
            stats['total'] += result['total_event_count']
            stats['flash'] += result['flash_event_count']
            stats['nonflash'] += result['nonflash_event_count']
            completed += 1
            
            elapsed = time.time() - start_time
            progress = completed / n_lat * 100
            speed = completed / elapsed if elapsed > 0 else 0
            eta = (n_lat - completed) / speed if speed > 0 else 0
            print(f"\r[{progress:.1f}%] Total:{stats['total']} Flash:{stats['flash']} "
                  f"NonFlash:{stats['nonflash']} | {speed:.1f}行/s | ETA:{eta/60:.1f}m", 
                  end='', flush=True)
    
    print("\n\n" + "="*70)
    print("[保存结果]")
    print("="*70)
    
    from osgeo import gdal, osr
    os.makedirs(RESULT_DIR, exist_ok=True)
    
    def save_tiff(data, filename, lat_sub, lon_sub):
        filepath = os.path.join(RESULT_DIR, filename)
        rows, cols = data.shape
        driver = gdal.GetDriverByName('GTiff')
        out_ds = driver.Create(filepath, cols, rows, 1, gdal.GDT_Float32)
        
        lon_res = abs(lon_sub[1] - lon_sub[0]) if len(lon_sub) > 1 else 0.1
        lat_res = abs(lat_sub[1] - lat_sub[0]) if len(lat_sub) > 1 else 0.1
        geotransform = (float(lon_sub[0]) - lon_res/2, lon_res, 0,
                        float(lat_sub[0]) + lat_res/2, 0, -lat_res)
        out_ds.SetGeoTransform(geotransform)
        
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        out_ds.SetProjection(srs.ExportToWkt())
        
        band = out_ds.GetRasterBand(1)
        band.SetNoDataValue(-9999)
        band.WriteArray(np.where(np.isnan(data), -9999, data))
        band.FlushCache()
        out_ds = None
    
    lat_sub = lat_array[lat_idx_min:lat_idx_max+1]
    lon_sub = lon_array[lon_idx_min:lon_idx_max+1]
    
    print("  保存总频率...")
    save_tiff(freq_total, f"total_drought_SMs_frequency_{YEARS[0]}_{YEARS[-1]}.tif", lat_sub, lon_sub)
    save_tiff(freq_flash, f"flash_drought_SMs_frequency_{YEARS[0]}_{YEARS[-1]}.tif", lat_sub, lon_sub)
    save_tiff(freq_nonflash, f"nonflash_drought_SMs_frequency_{YEARS[0]}_{YEARS[-1]}.tif", lat_sub, lon_sub)
    
    print("  保存年度频率...")
    for year in YEARS:
        save_tiff(yearly_total[year], f"total_drought_SMs_{year}.tif", lat_sub, lon_sub)
        save_tiff(yearly_flash[year], f"flash_drought_SMs_{year}.tif", lat_sub, lon_sub)
        save_tiff(yearly_nonflash[year], f"nonflash_drought_SMs_{year}.tif", lat_sub, lon_sub)
    
    print("  保存事件详情 NetCDF...")
    save_events_netcdf(os.path.join(RESULT_DIR, "total_drought_SMs_events_v5.nc"),
                       total_events_data, n_lat, n_lon, lat_sub, lon_sub, "Total Drought SMs")
    save_events_netcdf(os.path.join(RESULT_DIR, "flash_drought_SMs_events_v5.nc"),
                       flash_events_data, n_lat, n_lon, lat_sub, lon_sub, "Flash Drought SMs")
    save_events_netcdf(os.path.join(RESULT_DIR, "nonflash_drought_SMs_events_v5.nc"),
                       nonflash_events_data, n_lat, n_lon, lat_sub, lon_sub, "Non-flash Drought SMs")
    
    elapsed = time.time() - start_time
    print("\n" + "="*70)
    print("                    处理完成")
    print("="*70)
    print(f"总耗时: {elapsed/60:.1f}分钟")
    print(f"有效像元: {stats['valid']}")
    print(f"\n[事件统计]")
    print(f"  Total drought:     {stats['total']}")
    print(f"  Flash drought:     {stats['flash']} ({stats['flash']/stats['total']*100:.1f}%)" if stats['total'] > 0 else "  Flash drought:     0")
    print(f"  Non-flash drought: {stats['nonflash']} ({stats['nonflash']/stats['total']*100:.1f}%)" if stats['total'] > 0 else "  Non-flash drought: 0")
    print(f"  验证: flash + nonflash = {stats['flash'] + stats['nonflash']} = total({stats['total']})")


if __name__ == '__main__':
    main()
