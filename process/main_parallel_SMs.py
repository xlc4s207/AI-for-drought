# -*- coding: utf-8 -*-
"""
骤旱检测主程序 - SMs表层土壤湿度版本
使用多进程并行处理，数据源为GLEAM SMs
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
NC_DATA_DIR = os.path.join(BASE_DIR, "SMs")  # SMs数据目录
RESULT_DIR = os.path.join(BASE_DIR, "result", "SMs_result")  # SMs结果目录
NC_FILE_TEMPLATE = "SMs_{year}_GLEAM_v4.2a.nc"  # SMs文件模板
VAR_NAME = "SMs"  # 变量名

START_YEAR = 1980
END_YEAR = 2024
YEARS = list(range(START_YEAR, END_YEAR + 1))

LAT_SIZE = 1800
LON_SIZE = 3600

# 骤旱检测参数
MOVING_WINDOW = 5
PERCENTILE_HIGH = 40
PERCENTILE_LOW = 20
PERCENTILE_RATE = 5
MIN_DURATION = 15
MAX_EVENTS_PER_PIXEL = 50

# 测试区域
TEST_LAT_RANGE = (30, 40)
TEST_LON_RANGE = (100, 120)


def parse_args():
    parser = argparse.ArgumentParser(description='全球骤旱检测程序 - SMs数据')
    parser.add_argument('--test-mode', action='store_true', help='测试模式')
    parser.add_argument('--lat-range', nargs=2, type=float, default=None)
    parser.add_argument('--lon-range', nargs=2, type=float, default=None)
    parser.add_argument('--workers', type=int, default=None)
    return parser.parse_args()


def get_nc_path(year):
    return os.path.join(NC_DATA_DIR, NC_FILE_TEMPLATE.format(year=year))


def read_row_all_years(lat_idx, lon_start, lon_end):
    """读取一个纬度行、所有年份的数据"""
    all_data = []
    all_dates = []
    
    for year in YEARS:
        with nc.Dataset(get_nc_path(year), 'r') as ds:
            row_data = ds.variables[VAR_NAME][:, lat_idx, lon_start:lon_end]
            if hasattr(row_data, 'mask'):
                row_data = np.ma.filled(row_data, np.nan)
            all_data.append(row_data)
            
            n_days = row_data.shape[0]
            for doy in range(1, n_days + 1):
                all_dates.append((year, doy))
    
    combined = np.vstack(all_data)
    return combined, all_dates


def analyze_pixel_fast(sm_data, dates):
    """快速分析单个像元"""
    if np.sum(~np.isnan(sm_data)) < len(sm_data) * 0.5:
        return [], 0, {}
    
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
    
    yearly_counts = {year: 0 for year in YEARS}
    for event in events:
        yearly_counts[event['year']] += 1
    
    return events, len(events), yearly_counts


def process_single_row(args):
    """处理单行"""
    row_idx, lat_idx_global, lon_start, lon_end, n_lon = args
    
    try:
        row_data, dates = read_row_all_years(lat_idx_global, lon_start, lon_end)
        
        row_total = np.full(n_lon, np.nan, dtype=np.float32)
        row_yearly = {year: np.full(n_lon, np.nan, dtype=np.float32) for year in YEARS}
        row_events = []
        valid_count = 0
        event_count = 0
        
        for j in range(n_lon):
            pixel_data = row_data[:, j]
            
            if np.all(np.isnan(pixel_data)):
                continue
            
            events, total_count, yearly_counts = analyze_pixel_fast(pixel_data, dates)
            
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
    print("   全球骤旱(Flash Drought)检测程序 - SMs表层土壤湿度")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"数据源: {NC_DATA_DIR}")
    print(f"变量名: {VAR_NAME}")
    print(f"并行进程数: {n_workers}")
    print(f"数据年份: {YEARS[0]} - {YEARS[-1]}")
    print(f"结果目录: {RESULT_DIR}")
    
    # 创建结果目录
    os.makedirs(RESULT_DIR, exist_ok=True)
    
    # 读取坐标
    with nc.Dataset(get_nc_path(YEARS[0]), 'r') as ds:
        lat_array = ds.variables['lat'][:]
        lon_array = ds.variables['lon'][:]
    
    # 确定处理范围
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
    
    # 准备任务
    tasks = [
        (i, lat_idx_min + i, lon_idx_min, lon_idx_max + 1, n_lon)
        for i in range(n_lat)
    ]
    
    # 初始化结果数组
    total_freq = np.full((n_lat, n_lon), np.nan, dtype=np.float32)
    yearly_freq = {year: np.full((n_lat, n_lon), np.nan, dtype=np.float32) for year in YEARS}
    all_events_data = {
        'event_count': np.zeros((n_lat, n_lon), dtype=np.int16),
        'start_year': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
        'start_doy': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
        'duration': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -1, dtype=np.int16),
        'intensity': np.full((MAX_EVENTS_PER_PIXEL, n_lat, n_lon), -9999, dtype=np.float32),
    }
    
    print(f"\n[处理开始] 使用 {n_workers} 个进程并行处理...")
    print("-"*60)
    
    start_time = time.time()
    total_events = 0
    valid_pixels = 0
    completed_rows = 0
    
    with Pool(processes=n_workers) as pool:
        for result in pool.imap_unordered(process_single_row, tasks):
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
                    all_events_data['start_year'][k, row_idx, j] = evt['year']
                    all_events_data['start_doy'][k, row_idx, j] = evt['start_doy']
                    all_events_data['duration'][k, row_idx, j] = evt['duration']
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
    
    # 保存总频率
    save_tiff(total_freq, f"flash_drought_SMs_frequency_total_{YEARS[0]}_{YEARS[-1]}.tif", lat_sub, lon_sub)
    
    # 保存年度频率
    print("  保存年度频率...")
    for year in YEARS:
        save_tiff(yearly_freq[year], f"flash_drought_SMs_frequency_{year}.tif", lat_sub, lon_sub)
    
    # 保存事件详情NetCDF
    nc_path = os.path.join(RESULT_DIR, "flash_drought_SMs_events_details.nc")
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
        ec.long_name = 'Total flash drought events per pixel (1980-2024) based on SMs'
        
        sy = ds.createVariable('event_start_year', 'i2', ('max_events', 'lat', 'lon'), 
                               fill_value=-1, zlib=True)
        sy[:] = all_events_data['start_year']
        
        sd = ds.createVariable('event_start_doy', 'i2', ('max_events', 'lat', 'lon'),
                               fill_value=-1, zlib=True)
        sd[:] = all_events_data['start_doy']
        
        dur = ds.createVariable('event_duration', 'i2', ('max_events', 'lat', 'lon'),
                                fill_value=-1, zlib=True)
        dur[:] = all_events_data['duration']
        dur.long_name = 'Event duration in days'
        
        inten = ds.createVariable('event_intensity', 'f4', ('max_events', 'lat', 'lon'),
                                  fill_value=-9999, zlib=True)
        inten[:] = all_events_data['intensity']
        inten.long_name = 'Event intensity (cumulative deficit)'
        
        ds.title = 'Flash Drought Events Details (SMs - Surface Soil Moisture)'
        ds.source = f'GLEAM SMs data ({YEARS[0]}-{YEARS[-1]})'
        ds.institution = 'Flash Drought Detection System'
    
    print(f"  保存: flash_drought_SMs_events_details.nc")
    
    # 汇总
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
