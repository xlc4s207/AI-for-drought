# -*- coding: utf-8 -*-
"""
骤旱检测主程序 - 优化版
按纬度行批量处理，大幅提升效率
"""

import os
import sys
import argparse
import time
import numpy as np
import netCDF4 as nc
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    YEARS, LAT_SIZE, LON_SIZE, RESULT_DIR, NC_DATA_DIR, NC_FILE_TEMPLATE,
    TEST_LAT_RANGE, TEST_LON_RANGE, MOVING_WINDOW, MAX_EVENTS_PER_PIXEL,
    PERCENTILE_HIGH, PERCENTILE_LOW, PERCENTILE_RATE, MIN_DURATION
)


def parse_args():
    parser = argparse.ArgumentParser(description='全球骤旱检测程序(优化版)')
    parser.add_argument('--test-mode', action='store_true', help='测试模式')
    parser.add_argument('--lat-range', nargs=2, type=float, default=None)
    parser.add_argument('--lon-range', nargs=2, type=float, default=None)
    return parser.parse_args()


def get_nc_path(year):
    return os.path.join(NC_DATA_DIR, NC_FILE_TEMPLATE.format(year=year))


def read_row_all_years(lat_idx, lon_start, lon_end):
    """
    读取一个纬度行、所有年份的数据
    返回: (n_days_total, n_lon) 的数组和日期信息
    """
    all_data = []
    all_dates = []
    
    for year in YEARS:
        with nc.Dataset(get_nc_path(year), 'r') as ds:
            # 读取该纬度行的所有经度、所有天 (n_days, n_lon)
            row_data = ds.variables['SMrz'][:, lat_idx, lon_start:lon_end]
            if hasattr(row_data, 'mask'):
                row_data = np.ma.filled(row_data, np.nan)
            all_data.append(row_data)
            
            n_days = row_data.shape[0]
            for doy in range(1, n_days + 1):
                all_dates.append((year, doy))
    
    # 拼接: (total_days, n_lon)
    combined = np.vstack(all_data)
    return combined, all_dates


def calculate_moving_average_2d(data, window=MOVING_WINDOW):
    """计算二维数组的滑动平均 (时间维度)"""
    from scipy.ndimage import uniform_filter1d
    # 沿时间轴(axis=0)应用滑动平均
    ma = uniform_filter1d(data, size=window, axis=0, mode='nearest')
    # 将NaN位置保持为NaN
    nan_mask = np.isnan(data)
    ma[nan_mask] = np.nan
    return ma


def analyze_pixel_fast(sm_data, dates):
    """
    快速分析单个像元
    sm_data: 1D时序
    dates: [(year, doy), ...]
    """
    if np.sum(~np.isnan(sm_data)) < len(sm_data) * 0.5:
        return [], 0, {}
    
    # 5日滑动平均
    from scipy.ndimage import uniform_filter1d
    sm_ma = uniform_filter1d(sm_data, size=MOVING_WINDOW, mode='nearest')
    nan_mask = np.isnan(sm_data)
    sm_ma[nan_mask] = np.nan
    
    # 按DOY分组计算百分位
    doy_values = {}
    for i, (year, doy) in enumerate(dates):
        if not np.isnan(sm_ma[i]):
            if doy not in doy_values:
                doy_values[doy] = []
            doy_values[doy].append(sm_ma[i])
    
    # 计算百分位
    percentiles = {}
    for doy in range(1, 367):
        if doy in doy_values and len(doy_values[doy]) > 0:
            vals = np.array(doy_values[doy])
            percentiles[doy] = {
                PERCENTILE_LOW: np.percentile(vals, PERCENTILE_LOW),
                PERCENTILE_HIGH: np.percentile(vals, PERCENTILE_HIGH)
            }
    
    # 计算下降速率百分位
    rates = np.diff(sm_ma, prepend=np.nan)
    doy_rates = {}
    for i, (year, doy) in enumerate(dates):
        if not np.isnan(rates[i]) and rates[i] < 0:
            if doy not in doy_rates:
                doy_rates[doy] = []
            doy_rates[doy].append(rates[i])
    
    rate_p5 = {}
    for doy in range(1, 367):
        if doy in doy_rates and len(doy_rates[doy]) > 0:
            rate_p5[doy] = np.percentile(doy_rates[doy], PERCENTILE_RATE)
    
    # 检测骤旱事件
    events = []
    n = len(sm_ma)
    in_drought = False
    above_p40 = False
    event_start = None
    crossing_start = None
    
    for i in range(n):
        if np.isnan(sm_ma[i]):
            continue
        
        year, doy = dates[i]
        if doy not in percentiles:
            continue
        
        p40 = percentiles[doy][PERCENTILE_HIGH]
        p20 = percentiles[doy][PERCENTILE_LOW]
        
        if not in_drought:
            if sm_ma[i] > p40:
                above_p40 = True
                crossing_start = i
            elif above_p40 and sm_ma[i] < p20:
                if crossing_start is not None and i > crossing_start:
                    decline_rate = (sm_ma[i] - sm_ma[crossing_start]) / (i - crossing_start)
                    rate_threshold = rate_p5.get(doy, -0.01)
                    if decline_rate <= rate_threshold:
                        in_drought = True
                        event_start = i
                above_p40 = False
        else:
            if sm_ma[i] > p20:
                event_end = i - 1
                duration = event_end - event_start + 1
                if duration >= MIN_DURATION:
                    intensity = 0.0
                    for j in range(event_start, event_end + 1):
                        _, doy_j = dates[j]
                        if doy_j in percentiles and not np.isnan(sm_ma[j]):
                            deficit = percentiles[doy_j][PERCENTILE_LOW] - sm_ma[j]
                            if deficit > 0:
                                intensity += deficit
                    
                    start_year, start_doy = dates[event_start]
                    events.append({
                        'year': start_year,
                        'start_doy': start_doy,
                        'duration': duration,
                        'intensity': intensity
                    })
                in_drought = False
                event_start = None
    
    # 统计
    yearly_counts = {year: 0 for year in YEARS}
    for event in events:
        yearly_counts[event['year']] += 1
    
    return events, len(events), yearly_counts


def main():
    args = parse_args()
    
    print("="*60)
    print("     全球骤旱(Flash Drought)检测程序 - 优化版")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"数据年份: {YEARS[0]} - {YEARS[-1]}")
    print(f"结果目录: {RESULT_DIR}")
    
    # 读取坐标
    with nc.Dataset(get_nc_path(YEARS[0]), 'r') as ds:
        lat_array = ds.variables['lat'][:]
        lon_array = ds.variables['lon'][:]
    
    # 确定处理范围
    if args.test_mode:
        lat_range = args.lat_range if args.lat_range else TEST_LAT_RANGE
        lon_range = args.lon_range if args.lon_range else TEST_LON_RANGE
        print(f"\n[测试模式] 纬度: {lat_range}, 经度: {lon_range}")
        
        lat_idx_min = np.argmin(np.abs(lat_array - lat_range[1]))  # 注意:lat从90到-90
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
    
    # 初始化结果数组
    total_freq = np.full((n_lat, n_lon), np.nan, dtype=np.float32)
    yearly_freq = {year: np.full((n_lat, n_lon), np.nan, dtype=np.float32) for year in YEARS}
    
    # 事件详情存储
    all_events_data = {
        'event_count': np.zeros((n_lat, n_lon), dtype=np.int16),
        'start_year': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
        'start_doy': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
        'duration': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
        'intensity': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -9999, dtype=np.float32),
    }
    
    print("\n[处理开始]")
    print("-"*60)
    
    start_time = time.time()
    total_events = 0
    valid_pixels = 0
    
    for i, lat_idx in enumerate(range(lat_idx_min, lat_idx_max + 1)):
        # 读取该纬度行所有年份数据
        row_data, dates = read_row_all_years(lat_idx, lon_idx_min, lon_idx_max + 1)
        
        # 逐经度处理
        for j in range(n_lon):
            pixel_data = row_data[:, j]
            
            # 检查有效性
            if np.all(np.isnan(pixel_data)):
                continue
            
            # 分析
            events, total_count, yearly_counts = analyze_pixel_fast(pixel_data, dates)
            
            # 存储结果
            total_freq[i, j] = total_count
            for year, cnt in yearly_counts.items():
                yearly_freq[year][i, j] = cnt
            
            # 事件详情
            n_events = min(len(events), MAX_EVENTS_PER_PIXEL)
            all_events_data['event_count'][i, j] = n_events
            for k, evt in enumerate(events[:n_events]):
                all_events_data['start_year'][k, i, j] = evt['year']
                all_events_data['start_doy'][k, i, j] = evt['start_doy']
                all_events_data['duration'][k, i, j] = evt['duration']
                all_events_data['intensity'][k, i, j] = evt['intensity']
            
            total_events += total_count
            valid_pixels += 1
        
        # 进度显示
        elapsed = time.time() - start_time
        progress = (i + 1) / n_lat * 100
        speed = (i + 1) / elapsed if elapsed > 0 else 0
        eta = (n_lat - i - 1) / speed if speed > 0 else 0
        print(f"\r[进度] {i+1}/{n_lat} 行 ({progress:.1f}%) | "
              f"有效像元: {valid_pixels} | 事件: {total_events} | "
              f"速度: {speed:.1f}行/秒 | 剩余: {eta:.0f}秒", end='', flush=True)
    
    print("\n\n" + "="*60)
    print("[保存结果]")
    print("="*60)
    
    # 保存GeoTIFF
    from osgeo import gdal, osr
    os.makedirs(RESULT_DIR, exist_ok=True)
    
    def save_tiff(data, filename, lat_sub, lon_sub):
        filepath = os.path.join(RESULT_DIR, filename)
        rows, cols = data.shape
        driver = gdal.GetDriverByName('GTiff')
        out_ds = driver.Create(filepath, cols, rows, 1, gdal.GDT_Float32)
        
        # 地理变换
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
    
    # 保存总频率
    save_tiff(total_freq, f"flash_drought_frequency_total_{YEARS[0]}_{YEARS[-1]}.tif", lat_sub, lon_sub)
    
    # 保存年度频率
    print("  保存年度频率...")
    for year in YEARS:
        save_tiff(yearly_freq[year], f"flash_drought_frequency_{year}.tif", lat_sub, lon_sub)
    
    # 保存事件详情NetCDF
    nc_path = os.path.join(RESULT_DIR, "flash_drought_events_details.nc")
    with nc.Dataset(nc_path, 'w', format='NETCDF4') as ds:
        ds.createDimension('lat', n_lat)
        ds.createDimension('lon', n_lon)
        ds.createDimension('max_events', MAX_EVENTS_PER_PIXEL)
        
        lat_var = ds.createVariable('lat', 'f4', ('lat',))
        lat_var[:] = lat_sub
        lon_var = ds.createVariable('lon', 'f4', ('lon',))
        lon_var[:] = lon_sub
        
        ec = ds.createVariable('event_count', 'i2', ('lat', 'lon'), fill_value=-1, zlib=True)
        ec[:] = all_events_data['event_count']
        
        sy = ds.createVariable('event_start_year', 'i2', ('max_events', 'lat', 'lon'), 
                               fill_value=-1, zlib=True)
        sy[:] = all_events_data['start_year']
        
        sd = ds.createVariable('event_start_doy', 'i2', ('max_events', 'lat', 'lon'),
                               fill_value=-1, zlib=True)
        sd[:] = all_events_data['start_doy']
        
        dur = ds.createVariable('event_duration', 'i2', ('max_events', 'lat', 'lon'),
                                fill_value=-1, zlib=True)
        dur[:] = all_events_data['duration']
        
        inten = ds.createVariable('event_intensity', 'f4', ('max_events', 'lat', 'lon'),
                                  fill_value=-9999, zlib=True)
        inten[:] = all_events_data['intensity']
        
        ds.title = 'Flash Drought Events Details'
        ds.source = f'GLEAM SMrz data ({YEARS[0]}-{YEARS[-1]})'
    
    print(f"  保存: flash_drought_events_details.nc")
    
    # 汇总
    elapsed = time.time() - start_time
    print("\n" + "="*60)
    print("                 处理完成")
    print("="*60)
    print(f"总耗时: {elapsed:.1f}秒 ({elapsed/60:.1f}分钟)")
    print(f"有效像元: {valid_pixels}")
    print(f"骤旱事件总数: {total_events}")
    print(f"平均频率: {total_events/valid_pixels:.2f} 次/像元" if valid_pixels > 0 else "")
    
    # 显示统计
    valid_freq = total_freq[~np.isnan(total_freq)]
    if len(valid_freq) > 0:
        print(f"\n[频率统计]")
        print(f"  最小: {np.min(valid_freq):.0f}")
        print(f"  最大: {np.max(valid_freq):.0f}")
        print(f"  平均: {np.mean(valid_freq):.2f}")
        print(f"  中位数: {np.median(valid_freq):.0f}")


if __name__ == '__main__':
    main()
