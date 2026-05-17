# -*- coding: utf-8 -*-
"""
骤旱检测主程序 - 性能优化版 v4 (SMs 表层土壤湿度)
基于 SMrz v4 版本，主要修正 (参考 flash_drought_SMs1.md):
1. 百分位阈值使用 1981-2010 基准期
2. DOY=366 合并到 365 (减少闰日噪声)
3. 按年重置滑动平均窗口 (避免跨年污染)
4. NORMAL 状态遇 NaN 重置 wet_start_idx (防伪 onset)
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
    YEARS, LAT_SIZE, LON_SIZE, NC_FILE_TEMPLATE,
    TEST_LAT_RANGE, TEST_LON_RANGE, MOVING_WINDOW, MAX_EVENTS_PER_PIXEL,
    PERCENTILE_HIGH, PERCENTILE_LOW, MIN_DURATION
)

# 数据路径配置 - SMs 表层土壤湿度 (合并后的45年数据)
BASE_DIR = "/home/xulc/flash_drought/gleam"
SM_FILE = "/data/GLEAM/SMs_45years.nc"  # 1980-2024 合并文件
RESULT_DIR = os.path.join(BASE_DIR, "result", "SMs_result_v4")

# 骤旱爆发期时间约束
MIN_ONSET_DAYS = 5
MAX_ONSET_DAYS = 30

# ========== 百分位基准期（气候常年值）==========
REF_START_YEAR = 1981
REF_END_YEAR = 2010
REF_YEARS = set(range(REF_START_YEAR, REF_END_YEAR + 1))


def parse_args():
    parser = argparse.ArgumentParser(description='全球骤旱检测程序 - SMs v4')
    parser.add_argument('--test-mode', action='store_true', help='测试模式')
    parser.add_argument('--lat-range', nargs=2, type=float, default=None)
    parser.add_argument('--lon-range', nargs=2, type=float, default=None)
    parser.add_argument('--workers', type=int, default=None)
    return parser.parse_args()


def get_sm_file():
    return SM_FILE


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
    """预计算 DOY 索引，DOY=366 合并到 365"""
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


def analyze_pixel_optimized(sm_ma, p20_arr, p40_arr, dates):
    """骤旱分析函数 - v4 修正版"""
    valid_ratio = np.sum(~np.isnan(sm_ma)) / len(sm_ma)
    if valid_ratio < 0.5:
        return None, None, None, False
    
    events = []
    n = len(sm_ma)
    
    state = 'NORMAL'
    wet_start_idx = None
    drought_start_idx = None
    nan_count_in_drought = 0
    
    for i in range(n):
        year, doy = dates[i]
        
        if np.isnan(sm_ma[i]):
            if state == 'NORMAL':
                wet_start_idx = None
            elif state == 'DROUGHT':
                nan_count_in_drought += 1
                if nan_count_in_drought >= 3:
                    event_end = i - nan_count_in_drought
                    if event_end > drought_start_idx:
                        duration = event_end - drought_start_idx + 1
                        if duration >= MIN_DURATION:
                            onset_days = drought_start_idx - wet_start_idx
                            onset_drop = sm_ma[wet_start_idx] - sm_ma[drought_start_idx]
                            onset_rate = onset_drop / onset_days if onset_days > 0 else np.nan
                            
                            intensity = 0.0
                            for j in range(drought_start_idx, event_end + 1):
                                _, doy_j = dates[j]
                                if not np.isnan(sm_ma[j]) and not np.isnan(p20_arr[doy_j]):
                                    deficit = p20_arr[doy_j] - sm_ma[j]
                                    if deficit > 0:
                                        intensity += deficit
                            
                            onset_year, onset_doy = dates[wet_start_idx]
                            drought_year, drought_doy = dates[drought_start_idx]
                            end_year, end_doy = dates[event_end]
                            
                            events.append({
                                'onset_start_year': onset_year,
                                'onset_start_doy': onset_doy,
                                'drought_start_year': drought_year,
                                'drought_start_doy': drought_doy,
                                'drought_end_year': end_year,
                                'drought_end_doy': end_doy,
                                'onset_days': onset_days,
                                'drought_days': duration,
                                'onset_drop': onset_drop,
                                'onset_rate': onset_rate,
                                'intensity': intensity
                            })
                    
                    state = 'NORMAL'
                    wet_start_idx = None
                    drought_start_idx = None
                    nan_count_in_drought = 0
            continue
        
        nan_count_in_drought = 0
        
        p40 = p40_arr[doy]
        p20 = p20_arr[doy]
        
        if np.isnan(p40) or np.isnan(p20):
            continue
        
        current_above_p40 = sm_ma[i] > p40
        current_below_p20 = sm_ma[i] < p20
        
        if state == 'NORMAL':
            if current_above_p40:
                wet_start_idx = i
            elif wet_start_idx is not None and current_below_p20:
                onset_days = i - wet_start_idx
                if MIN_ONSET_DAYS <= onset_days <= MAX_ONSET_DAYS:
                    state = 'DROUGHT'
                    drought_start_idx = i
                else:
                    wet_start_idx = None
        
        elif state == 'DROUGHT':
            if not current_below_p20:
                event_end = i - 1
                duration = event_end - drought_start_idx + 1
                
                if duration >= MIN_DURATION:
                    onset_days = drought_start_idx - wet_start_idx
                    onset_drop = sm_ma[wet_start_idx] - sm_ma[drought_start_idx]
                    onset_rate = onset_drop / onset_days if onset_days > 0 else np.nan
                    
                    intensity = 0.0
                    for j in range(drought_start_idx, event_end + 1):
                        _, doy_j = dates[j]
                        if not np.isnan(sm_ma[j]) and not np.isnan(p20_arr[doy_j]):
                            deficit = p20_arr[doy_j] - sm_ma[j]
                            if deficit > 0:
                                intensity += deficit
                    
                    onset_year, onset_doy_val = dates[wet_start_idx]
                    drought_year, drought_doy_val = dates[drought_start_idx]
                    end_year, end_doy_val = dates[event_end]
                    
                    events.append({
                        'onset_start_year': onset_year,
                        'onset_start_doy': onset_doy_val,
                        'drought_start_year': drought_year,
                        'drought_start_doy': drought_doy_val,
                        'drought_end_year': end_year,
                        'drought_end_doy': end_doy_val,
                        'onset_days': onset_days,
                        'drought_days': duration,
                        'onset_drop': onset_drop,
                        'onset_rate': onset_rate,
                        'intensity': intensity
                    })
                
                state = 'NORMAL'
                wet_start_idx = None
                drought_start_idx = None
                
                if current_above_p40:
                    wet_start_idx = i
    
    if state == 'DROUGHT' and drought_start_idx is not None:
        event_end = n - 1
        duration = event_end - drought_start_idx + 1
        if duration >= MIN_DURATION:
            onset_days = drought_start_idx - wet_start_idx
            onset_drop = sm_ma[wet_start_idx] - sm_ma[drought_start_idx]
            onset_rate = onset_drop / onset_days if onset_days > 0 else np.nan
            
            intensity = 0.0
            for j in range(drought_start_idx, event_end + 1):
                _, doy_j = dates[j]
                if not np.isnan(sm_ma[j]) and not np.isnan(p20_arr[doy_j]):
                    deficit = p20_arr[doy_j] - sm_ma[j]
                    if deficit > 0:
                        intensity += deficit
            
            onset_year, onset_doy_val = dates[wet_start_idx]
            drought_year, drought_doy_val = dates[drought_start_idx]
            end_year, end_doy_val = dates[event_end]
            
            events.append({
                'onset_start_year': onset_year,
                'onset_start_doy': onset_doy_val,
                'drought_start_year': drought_year,
                'drought_start_doy': drought_doy_val,
                'drought_end_year': end_year,
                'drought_end_doy': end_doy_val,
                'onset_days': onset_days,
                'drought_days': duration,
                'onset_drop': onset_drop,
                'onset_rate': onset_rate,
                'intensity': intensity
            })
    
    yearly_counts = {year: 0 for year in YEARS}
    for event in events:
        yearly_counts[event['drought_start_year']] += 1
    
    return events, len(events), yearly_counts, True


_GLOBAL_DATES = None
_GLOBAL_DOY_INDICES = None
_GLOBAL_DOY_INDICES_REF = None
_GLOBAL_SM_DS = None


def init_worker(dates, doy_indices, doy_indices_ref):
    global _GLOBAL_DATES, _GLOBAL_DOY_INDICES, _GLOBAL_DOY_INDICES_REF, _GLOBAL_SM_DS
    _GLOBAL_DATES = dates
    _GLOBAL_DOY_INDICES = doy_indices
    _GLOBAL_DOY_INDICES_REF = doy_indices_ref
    _GLOBAL_SM_DS = nc.Dataset(SM_FILE, 'r')  # 每个 worker 打开合并文件


def process_single_row(args):
    row_idx, lat_idx_global, lon_start, lon_end, n_lon = args
    
    global _GLOBAL_DATES, _GLOBAL_DOY_INDICES, _GLOBAL_DOY_INDICES_REF, _GLOBAL_SM_DS
    dates = _GLOBAL_DATES
    doy_to_indices_ref = _GLOBAL_DOY_INDICES_REF
    
    try:
        row_data = read_row_from_merged(lat_idx_global, lon_start, lon_end, _GLOBAL_SM_DS)
        ma_2d = calculate_backward_moving_average_by_year(row_data, dates, MOVING_WINDOW)
        p20_2d, p40_2d = calculate_percentiles_batch(ma_2d, doy_to_indices_ref)
        
        row_total = np.full(n_lon, np.nan, dtype=np.float32)
        row_yearly = {year: np.full(n_lon, np.nan, dtype=np.float32) for year in YEARS}
        row_events = []
        valid_count = 0
        event_count = 0
        
        for j in range(n_lon):
            pixel_ma = ma_2d[:, j]
            
            if np.all(np.isnan(pixel_ma)):
                continue
            
            p20_pixel = p20_2d[:, j]
            p40_pixel = p40_2d[:, j]
            
            events, total_count, yearly_counts, is_valid = analyze_pixel_optimized(
                pixel_ma, p20_pixel, p40_pixel, dates
            )
            
            if not is_valid:
                continue
            
            row_total[j] = total_count
            for year, cnt in yearly_counts.items():
                row_yearly[year][j] = cnt
            
            row_events.append((j, events[:MAX_EVENTS_PER_PIXEL]))
            
            valid_count += 1
            event_count += total_count
        
        return {
            'row_idx': row_idx,
            'total': row_total,
            'yearly': row_yearly,
            'events': row_events,
            'valid_count': valid_count,
            'event_count': event_count
        }
    except Exception as e:
        print(f"\n[错误] 行 {row_idx}: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    args = parse_args()
    
    n_workers = args.workers if args.workers else max(1, cpu_count() - 1)
    
    print("="*60)
    print("   全球骤旱(Flash Drought)检测 - SMs 修正版 v4")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"并行进程数: {n_workers}")
    print(f"数据年份: {YEARS[0]} - {YEARS[-1]}")
    print(f"结果目录: {RESULT_DIR}")
    print()
    print("[算法参数]")
    print(f"  滑动窗口: {MOVING_WINDOW} 天 (后向)")
    print(f"  湿润阈值: P{PERCENTILE_HIGH}")
    print(f"  干旱阈值: P{PERCENTILE_LOW}")
    print(f"  爆发期约束: {MIN_ONSET_DAYS}-{MAX_ONSET_DAYS} 天")
    print(f"  最小持续: {MIN_DURATION} 天")
    print()
    print("[v4 修正内容]")
    print(f"  ✓ 百分位基准期: {REF_START_YEAR}-{REF_END_YEAR}")
    print("  ✓ DOY=366 合并到 365 (减少闰日噪声)")
    print("  ✓ 按年重置滑动平均 (避免跨年污染)")
    print("  ✓ NORMAL 状态 NaN 重置 wet_start (防伪 onset)")
    
    print("\n[预处理] 构建 DOY 索引...")
    dates, doy_to_indices, doy_to_indices_ref = build_doy_indices(YEARS)
    print(f"  时间序列长度: {len(dates)} 天")
    print(f"  基准期 (1981-2010) 天数: {sum(len(v) for v in doy_to_indices_ref.values())}")
    
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
    print(f"\n[处理范围] {n_lat} 行 x {n_lon} 列 = {n_lat * n_lon} 像元")
    
    tasks = [
        (i, lat_idx_min + i, lon_idx_min, lon_idx_max + 1, n_lon)
        for i in range(n_lat)
    ]
    
    total_freq = np.full((n_lat, n_lon), np.nan, dtype=np.float32)
    yearly_freq = {year: np.full((n_lat, n_lon), np.nan, dtype=np.float32) for year in YEARS}
    
    all_events_data = {
        'event_count': np.full((n_lat, n_lon), -1, dtype=np.int16),
        'onset_start_year': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
        'onset_start_doy': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
        'drought_start_year': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
        'drought_start_doy': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
        'drought_end_year': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
        'drought_end_doy': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
        'onset_days': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
        'drought_days': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
        'onset_drop': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -9999, dtype=np.float32),
        'onset_rate': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -9999, dtype=np.float32),
        'intensity': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -9999, dtype=np.float32),
    }
    
    print(f"\n[处理开始] 使用 {n_workers} 个进程并行处理...")
    print("-"*60)
    
    start_time = time.time()
    total_events = 0
    valid_pixels = 0
    completed_rows = 0
    
    with Pool(processes=n_workers, initializer=init_worker, 
              initargs=(dates, doy_to_indices, doy_to_indices_ref)) as pool:
        for result in pool.imap_unordered(process_single_row, tasks, chunksize=4):
            if result is None:
                completed_rows += 1
                continue
            
            row_idx = result['row_idx']
            total_freq[row_idx] = result['total']
            for year in YEARS:
                yearly_freq[year][row_idx] = result['yearly'][year]
            
            for j, events in result['events']:
                n_events = len(events)
                all_events_data['event_count'][row_idx, j] = n_events
                for k, evt in enumerate(events):
                    all_events_data['onset_start_year'][k, row_idx, j] = evt['onset_start_year']
                    all_events_data['onset_start_doy'][k, row_idx, j] = evt['onset_start_doy']
                    all_events_data['drought_start_year'][k, row_idx, j] = evt['drought_start_year']
                    all_events_data['drought_start_doy'][k, row_idx, j] = evt['drought_start_doy']
                    all_events_data['drought_end_year'][k, row_idx, j] = evt['drought_end_year']
                    all_events_data['drought_end_doy'][k, row_idx, j] = evt['drought_end_doy']
                    all_events_data['onset_days'][k, row_idx, j] = evt['onset_days']
                    all_events_data['drought_days'][k, row_idx, j] = evt['drought_days']
                    all_events_data['onset_drop'][k, row_idx, j] = evt['onset_drop']
                    all_events_data['onset_rate'][k, row_idx, j] = evt['onset_rate']
                    all_events_data['intensity'][k, row_idx, j] = evt['intensity']
            
            valid_pixels += result['valid_count']
            total_events += result['event_count']
            completed_rows += 1
            
            elapsed = time.time() - start_time
            progress = completed_rows / n_lat * 100
            speed = completed_rows / elapsed if elapsed > 0 else 0
            eta = (n_lat - completed_rows) / speed if speed > 0 else 0
            print(f"\r[进度] {completed_rows}/{n_lat} 行 ({progress:.1f}%) | "
                  f"有效: {valid_pixels} | 事件: {total_events} | "
                  f"速度: {speed:.2f}行/秒 | 剩余: {eta/60:.1f}分钟", end='', flush=True)
    
    print("\n\n" + "="*60)
    print("[保存结果]")
    print("="*60)
    
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
        data_out = np.where(np.isnan(data), -9999, data)
        band.WriteArray(data_out)
        band.FlushCache()
        out_ds = None
        print(f"  保存: {filename}")
    
    lat_sub = lat_array[lat_idx_min:lat_idx_max+1]
    lon_sub = lon_array[lon_idx_min:lon_idx_max+1]
    
    save_tiff(total_freq, f"flash_drought_SMs_frequency_total_{YEARS[0]}_{YEARS[-1]}.tif", lat_sub, lon_sub)
    
    print("  保存年度频率...")
    for year in YEARS:
        save_tiff(yearly_freq[year], f"flash_drought_SMs_frequency_{year}.tif", lat_sub, lon_sub)
    
    nc_path = os.path.join(RESULT_DIR, "flash_drought_SMs_events_details_v4.nc")
    with nc.Dataset(nc_path, 'w', format='NETCDF4') as ds:
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
        ec[:] = all_events_data['event_count']
        ec.long_name = 'Total flash drought events (-1=invalid pixel)'
        
        for key in ['onset_start_year', 'onset_start_doy', 'drought_start_year', 'drought_start_doy',
                    'drought_end_year', 'drought_end_doy', 'onset_days', 'drought_days']:
            v = ds.createVariable(key, 'i2', ('max_events', 'lat', 'lon'), fill_value=-1, zlib=True)
            v[:] = all_events_data[key]
        
        for key in ['onset_drop', 'onset_rate', 'intensity']:
            v = ds.createVariable(key, 'f4', ('max_events', 'lat', 'lon'), fill_value=-9999, zlib=True)
            v[:] = all_events_data[key]
        
        ds.title = 'Flash Drought Events Details v4 - SMs (Surface Soil Moisture)'
        ds.source = f'GLEAM SMs data ({YEARS[0]}-{YEARS[-1]})'
        ds.algorithm = 'Time Constraint Method v4'
        ds.percentile_baseline = f'{REF_START_YEAR}-{REF_END_YEAR}'
        ds.corrections = 'DOY366->365, yearly MA reset, NaN reset wet_start'
    
    print(f"  保存: flash_drought_SMs_events_details_v4.nc")
    
    elapsed = time.time() - start_time
    print("\n" + "="*60)
    print("                 处理完成")
    print("="*60)
    print(f"总耗时: {elapsed:.1f}秒 ({elapsed/60:.1f}分钟)")
    print(f"并行进程数: {n_workers}")
    print(f"有效像元: {valid_pixels}")
    print(f"骤旱事件总数: {total_events}")
    if valid_pixels > 0:
        print(f"平均频率: {total_events/valid_pixels:.2f} 次/像元")
    
    valid_freq = total_freq[~np.isnan(total_freq)]
    if len(valid_freq) > 0:
        print(f"\n[频率统计]")
        print(f"  最小: {np.min(valid_freq):.0f}")
        print(f"  最大: {np.max(valid_freq):.0f}")
        print(f"  平均: {np.mean(valid_freq):.2f}")
        print(f"  中位数: {np.median(valid_freq):.0f}")


if __name__ == '__main__':
    main()
