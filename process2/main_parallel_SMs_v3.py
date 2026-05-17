# -*- coding: utf-8 -*-
"""
骤旱检测主程序 - SMs表层土壤湿度 性能优化版 v3
基于 v2 版本，主要优化：
1. 向量化滑动平均计算 (O(T) 复杂度)
2. 批量计算 P20/P40 阈值 (按行处理)
3. 预计算 DOY 索引
4. event_count 初始化为 -1 区分无效像元
"""

import os
import sys
import argparse
import time
import numpy as np
import netCDF4 as nc
from datetime import datetime
from multiprocessing import Pool, cpu_count

# ==================== 配置参数 ====================
BASE_DIR = "/home/xulc/flash_drought/gleam"
NC_DATA_DIR = os.path.join(BASE_DIR, "SMs")
RESULT_DIR = os.path.join(BASE_DIR, "result", "SMs_result_v3")
NC_FILE_TEMPLATE = "SMs_{year}_GLEAM_v4.2a.nc"
VAR_NAME = "SMs"

START_YEAR = 1980
END_YEAR = 2024
YEARS = list(range(START_YEAR, END_YEAR + 1))

LAT_SIZE = 1800
LON_SIZE = 3600

# 骤旱检测参数
MOVING_WINDOW = 5
PERCENTILE_HIGH = 40
PERCENTILE_LOW = 20
MIN_DURATION = 15
MAX_EVENTS_PER_PIXEL = 50

# 骤旱爆发期时间约束
MIN_ONSET_DAYS = 5
MAX_ONSET_DAYS = 30

# 测试区域
TEST_LAT_RANGE = (30, 40)
TEST_LON_RANGE = (100, 120)


def parse_args():
    parser = argparse.ArgumentParser(description='全球骤旱检测 - SMs 优化版v3')
    parser.add_argument('--test-mode', action='store_true', help='测试模式')
    parser.add_argument('--lat-range', nargs=2, type=float, default=None)
    parser.add_argument('--lon-range', nargs=2, type=float, default=None)
    parser.add_argument('--workers', type=int, default=None)
    return parser.parse_args()


def get_nc_path(year):
    return os.path.join(NC_DATA_DIR, NC_FILE_TEMPLATE.format(year=year))


def calculate_backward_moving_average_vectorized(data_2d, window=MOVING_WINDOW):
    """
    向量化后向滑动平均，支持 2D 数组 (time, lon)
    使用 cumsum 实现 O(T) 复杂度
    """
    min_valid = window // 2
    T, n_lon = data_2d.shape
    
    # 将 NaN 替换为 0 用于累加
    valid_mask = ~np.isnan(data_2d)
    data_filled = np.where(valid_mask, data_2d, 0.0)
    
    # 计算累积和
    cum_sum = np.cumsum(data_filled, axis=0)
    cum_count = np.cumsum(valid_mask.astype(np.int32), axis=0)
    
    # 构建偏移数组
    cum_sum_shifted = np.zeros_like(cum_sum)
    cum_count_shifted = np.zeros_like(cum_count)
    
    if window < T:
        cum_sum_shifted[window:] = cum_sum[:-window]
        cum_count_shifted[window:] = cum_count[:-window]
    
    # 窗口内的和与计数
    window_sum = cum_sum - cum_sum_shifted
    window_count = cum_count - cum_count_shifted
    
    # 计算平均值
    ma_2d = np.full_like(data_2d, np.nan, dtype=np.float64)
    valid_window = window_count >= min_valid
    ma_2d[valid_window] = window_sum[valid_window] / window_count[valid_window]
    
    return ma_2d


def build_doy_indices(years):
    """
    预计算每年每天对应的 DOY 和全局索引
    """
    dates = []
    doy_to_indices = {doy: [] for doy in range(1, 367)}
    
    idx = 0
    for year in years:
        if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
            n_days = 366
        else:
            n_days = 365
        
        for doy in range(1, n_days + 1):
            dates.append((year, doy))
            doy_to_indices[doy].append(idx)
            idx += 1
    
    for doy in doy_to_indices:
        doy_to_indices[doy] = np.array(doy_to_indices[doy], dtype=np.int32)
    
    return dates, doy_to_indices


def read_row_all_years(lat_idx, lon_start, lon_end):
    """读取一个纬度行、所有年份的数据"""
    all_data = []
    
    for year in YEARS:
        with nc.Dataset(get_nc_path(year), 'r') as ds:
            row_data = ds.variables[VAR_NAME][:, lat_idx, lon_start:lon_end]
            if hasattr(row_data, 'mask'):
                row_data = np.ma.filled(row_data, np.nan)
            all_data.append(row_data)
    
    combined = np.vstack(all_data)
    return combined


def calculate_percentiles_batch(ma_2d, doy_to_indices):
    """批量计算每个 DOY 的 P20/P40 阈值"""
    n_lon = ma_2d.shape[1]
    p20_2d = np.full((367, n_lon), np.nan, dtype=np.float64)
    p40_2d = np.full((367, n_lon), np.nan, dtype=np.float64)
    
    for doy in range(1, 367):
        indices = doy_to_indices.get(doy)
        if indices is None or len(indices) == 0:
            continue
        
        doy_data = ma_2d[indices, :]
        
        with np.errstate(all='ignore'):
            p20_2d[doy, :] = np.nanpercentile(doy_data, PERCENTILE_LOW, axis=0)
            p40_2d[doy, :] = np.nanpercentile(doy_data, PERCENTILE_HIGH, axis=0)
    
    return p20_2d, p40_2d


def analyze_pixel_optimized(sm_ma, p20_arr, p40_arr, dates):
    """优化版骤旱分析函数"""
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
            if state == 'DROUGHT':
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


# 全局变量
_GLOBAL_DATES = None
_GLOBAL_DOY_INDICES = None


def init_worker(dates, doy_indices):
    """初始化 worker 进程的全局变量"""
    global _GLOBAL_DATES, _GLOBAL_DOY_INDICES
    _GLOBAL_DATES = dates
    _GLOBAL_DOY_INDICES = doy_indices


def process_single_row(args):
    """处理单行 - 优化版"""
    row_idx, lat_idx_global, lon_start, lon_end, n_lon = args
    
    global _GLOBAL_DATES, _GLOBAL_DOY_INDICES
    dates = _GLOBAL_DATES
    doy_to_indices = _GLOBAL_DOY_INDICES
    
    try:
        row_data = read_row_all_years(lat_idx_global, lon_start, lon_end)
        
        # 向量化计算
        ma_2d = calculate_backward_moving_average_vectorized(row_data, MOVING_WINDOW)
        p20_2d, p40_2d = calculate_percentiles_batch(ma_2d, doy_to_indices)
        
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
        return None


def main():
    args = parse_args()
    
    n_workers = args.workers if args.workers else max(1, cpu_count() - 1)
    
    print("="*60)
    print("   全球骤旱检测 - SMs表层 优化版 v3")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"数据源: {NC_DATA_DIR}")
    print(f"变量名: {VAR_NAME}")
    print(f"并行进程数: {n_workers}")
    print(f"数据年份: {YEARS[0]} - {YEARS[-1]}")
    print(f"结果目录: {RESULT_DIR}")
    
    os.makedirs(RESULT_DIR, exist_ok=True)
    
    print("\n[预处理] 构建 DOY 索引...")
    dates, doy_to_indices = build_doy_indices(YEARS)
    
    with nc.Dataset(get_nc_path(YEARS[0]), 'r') as ds:
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
              initargs=(dates, doy_to_indices)) as pool:
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
    
    nc_path = os.path.join(RESULT_DIR, "flash_drought_SMs_events_details_v3.nc")
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
        ec.long_name = 'Total flash drought events (-1=invalid)'
        
        v = ds.createVariable('onset_start_year', 'i2', ('max_events', 'lat', 'lon'), fill_value=-1, zlib=True)
        v[:] = all_events_data['onset_start_year']
        
        v = ds.createVariable('onset_start_doy', 'i2', ('max_events', 'lat', 'lon'), fill_value=-1, zlib=True)
        v[:] = all_events_data['onset_start_doy']
        
        v = ds.createVariable('drought_start_year', 'i2', ('max_events', 'lat', 'lon'), fill_value=-1, zlib=True)
        v[:] = all_events_data['drought_start_year']
        
        v = ds.createVariable('drought_start_doy', 'i2', ('max_events', 'lat', 'lon'), fill_value=-1, zlib=True)
        v[:] = all_events_data['drought_start_doy']
        
        v = ds.createVariable('drought_end_year', 'i2', ('max_events', 'lat', 'lon'), fill_value=-1, zlib=True)
        v[:] = all_events_data['drought_end_year']
        
        v = ds.createVariable('drought_end_doy', 'i2', ('max_events', 'lat', 'lon'), fill_value=-1, zlib=True)
        v[:] = all_events_data['drought_end_doy']
        
        v = ds.createVariable('onset_days', 'i2', ('max_events', 'lat', 'lon'), fill_value=-1, zlib=True)
        v[:] = all_events_data['onset_days']
        
        v = ds.createVariable('drought_days', 'i2', ('max_events', 'lat', 'lon'), fill_value=-1, zlib=True)
        v[:] = all_events_data['drought_days']
        
        v = ds.createVariable('onset_drop', 'f4', ('max_events', 'lat', 'lon'), fill_value=-9999, zlib=True)
        v[:] = all_events_data['onset_drop']
        
        v = ds.createVariable('onset_rate', 'f4', ('max_events', 'lat', 'lon'), fill_value=-9999, zlib=True)
        v[:] = all_events_data['onset_rate']
        
        v = ds.createVariable('intensity', 'f4', ('max_events', 'lat', 'lon'), fill_value=-9999, zlib=True)
        v[:] = all_events_data['intensity']
        
        ds.title = 'Flash Drought Events Details v3 SMs (Optimized)'
        ds.source = f'GLEAM SMs data ({YEARS[0]}-{YEARS[-1]})'
    
    print(f"  保存: flash_drought_SMs_events_details_v3.nc")
    
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
