"""
脚本02: 事件提取与窗口处理 (50核并行版 - 按层处理)
- 使用合并后的GPP文件
- 50核并行处理纬度行
- 双重进度条: 层进度 + 总像元统计
"""
import os
import sys
import numpy as np
import netCDF4 as nc
from tqdm import tqdm
import pickle
from multiprocessing import Pool, Manager
from functools import partial

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import *

# 全局变量 (初始化时设置)
GPP_FILE = None
EVENTS_FILE = None

def init_worker(gpp_file, events_file):
    """初始化worker进程的全局变量"""
    global GPP_FILE, EVENTS_FILE
    GPP_FILE = gpp_file
    EVENTS_FILE = events_file

def date_to_absolute_day(year, doy, base_year=1982):
    days = 0
    for y in range(base_year, year):
        days += 366 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 365
    return days + doy - 1

def absolute_day_to_date(abs_day, base_year=1982):
    year = base_year
    while True:
        days_in_year = 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365
        if abs_day < days_in_year:
            return year, abs_day + 1
        abs_day -= days_in_year
        year += 1

def calc_pixel_climatology(ts):
    doy_values = [[] for _ in range(366)]
    idx = 0
    for year in range(START_YEAR, END_YEAR + 1):
        is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
        days = 366 if is_leap else 365
        for d in range(days):
            if idx < len(ts) and not np.isnan(ts[idx]):
                doy_idx = d if is_leap else (d if d < 59 else d + 1)
                doy_values[doy_idx].append(ts[idx])
            idx += 1
    clim_mean = np.array([np.nanmean(v) if v else np.nan for v in doy_values], dtype=np.float32)
    clim_std = np.array([np.nanstd(v) if v else np.nan for v in doy_values], dtype=np.float32)
    return clim_mean, clim_std

def extract_event_windows(events, gpp_ts, clim_mean, clim_std):
    total_days = len(gpp_ts)
    results = []
    for i, event in enumerate(events):
        onset_day = event['onset_abs_day']
        window_start = onset_day - WINDOW_BEFORE
        window_end = onset_day + WINDOW_AFTER
        if i + 1 < len(events):
            next_onset = events[i + 1]['onset_abs_day']
            if next_onset <= window_end:
                window_end = next_onset - 1
        actual_after = window_end - onset_day
        if actual_after < MIN_WINDOW_AFTER:
            continue
        if window_start < 0 or window_end >= total_days:
            continue
        gpp_window = gpp_ts[window_start:window_end + 1].copy()
        gpp_anom = np.full_like(gpp_window, np.nan)
        gpp_z = np.full_like(gpp_window, np.nan)
        for j, abs_day in enumerate(range(window_start, window_end + 1)):
            year, doy = absolute_day_to_date(abs_day)
            is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
            clim_idx = doy - 1 if is_leap else ((doy - 1) if doy <= 59 else doy)
            if clim_idx < 366 and not np.isnan(gpp_window[j]) and not np.isnan(clim_mean[clim_idx]):
                gpp_anom[j] = gpp_window[j] - clim_mean[clim_idx]
                if clim_std[clim_idx] > 0:
                    gpp_z[j] = gpp_anom[j] / clim_std[clim_idx]
        results.append({
            'event_id': event['event_id'],
            'onset_year': event['onset_year'],
            'onset_doy': event['onset_doy'],
            'window_after': actual_after,
            'duration': event['onset_days'] + event['drought_days'],
            'intensity': event['intensity'],
            'gpp_raw': gpp_window,
            'gpp_anom': gpp_anom,
            'gpp_z': gpp_z
        })
    return results

def process_lat_row(args):
    """处理单个纬度行的所有像元 (worker函数)"""
    lat_idx, lat_val, valid_lon_indices = args
    
    results = []
    n_pixels_processed = 0
    
    try:
        # 打开GPP文件读取该行数据
        with nc.Dataset(GPP_FILE, 'r') as ds_gpp:
            gpp_row = ds_gpp.variables['GPP'][:, lat_idx, :]
            if hasattr(gpp_row, 'mask'):
                gpp_row = gpp_row.filled(np.nan)
        
        # 打开事件文件
        with nc.Dataset(EVENTS_FILE, 'r') as ds_events:
            for lon_idx in valid_lon_indices:
                event_count = int(ds_events.variables['event_count'][lat_idx, lon_idx])
                if event_count <= 0:
                    continue
                
                # 加载事件
                events = []
                for i in range(event_count):
                    onset_year = int(ds_events.variables['onset_start_year'][i, lat_idx, lon_idx])
                    onset_doy = int(ds_events.variables['onset_start_doy'][i, lat_idx, lon_idx])
                    if onset_year < START_YEAR or onset_year > END_YEAR:
                        continue
                    if onset_doy <= 0 or onset_doy > 366:
                        continue
                    events.append({
                        'event_id': i,
                        'onset_year': onset_year,
                        'onset_doy': onset_doy,
                        'onset_abs_day': date_to_absolute_day(onset_year, onset_doy),
                        'onset_days': int(ds_events.variables['onset_days'][i, lat_idx, lon_idx]),
                        'drought_days': int(ds_events.variables['drought_days'][i, lat_idx, lon_idx]),
                        'intensity': float(ds_events.variables['intensity'][i, lat_idx, lon_idx]),
                    })
                
                if not events:
                    continue
                events.sort(key=lambda x: x['onset_abs_day'])
                
                # 处理GPP
                gpp_ts = gpp_row[:, lon_idx].astype(np.float32)
                if np.all(np.isnan(gpp_ts)):
                    continue
                
                clim_mean, clim_std = calc_pixel_climatology(gpp_ts)
                windows = extract_event_windows(events, gpp_ts, clim_mean, clim_std)
                
                if windows:
                    results.append({
                        'lat_idx': lat_idx,
                        'lon_idx': lon_idx,
                        'lat': lat_val,
                        'n_events': len(events),
                        'n_valid_windows': len(windows),
                        'windows': windows
                    })
                    n_pixels_processed += 1
        
        return lat_idx, results, n_pixels_processed, None
    
    except Exception as e:
        return lat_idx, [], 0, str(e)

def main():
    print("=" * 60)
    print("Step 2: 事件提取与窗口处理 (50核并行)")
    print("=" * 60)
    
    if not os.path.exists(MERGED_GPP_FILE):
        print(f"Error: 未找到合并后的GPP文件: {MERGED_GPP_FILE}")
        return
    
    print(f"\n使用合并GPP文件: {MERGED_GPP_FILE}")
    
    test_pixels_file = os.path.join(OUTPUT_DIR, f"valid_pixels_{TEST_REGION['name']}.pkl")
    if not os.path.exists(test_pixels_file):
        print("Error: 请先运行 01_prepare_data.py")
        return
    
    with open(test_pixels_file, 'rb') as f:
        test_pixels = pickle.load(f)
    
    print(f"测试区域: {TEST_REGION['name']}")
    print(f"总像元数: {len(test_pixels)}")
    
    # 按纬度行分组
    lat_groups = {}
    for p in test_pixels:
        lat_idx = p['lat_idx']
        if lat_idx not in lat_groups:
            lat_groups[lat_idx] = {'lat': p['lat'], 'lon_indices': []}
        lat_groups[lat_idx]['lon_indices'].append(p['lon_idx'])
    
    lat_indices = sorted(lat_groups.keys())
    print(f"纬度行数: {len(lat_indices)}")
    print(f"并行进程: 50\n")
    
    # 准备任务
    tasks = [(lat_idx, lat_groups[lat_idx]['lat'], lat_groups[lat_idx]['lon_indices']) 
             for lat_idx in lat_indices]
    
    # 并行处理
    all_results = []
    total_pixels = 0
    errors = []
    
    with Pool(processes=50, initializer=init_worker, 
              initargs=(MERGED_GPP_FILE, DROUGHT_EVENTS_FILE)) as pool:
        for lat_idx, results, n_pixels, error in tqdm(
            pool.imap_unordered(process_lat_row, tasks),
            total=len(tasks),
            desc="处理纬度行"
        ):
            all_results.extend(results)
            total_pixels += n_pixels
            if error:
                errors.append((lat_idx, error))
    
    print(f"\n处理完成!")
    print(f"有效结果: {len(all_results)} 像元")
    print(f"总事件窗口: {sum(r['n_valid_windows'] for r in all_results)}")
    
    if errors:
        print(f"\n错误 ({len(errors)}):")
        for lat_idx, err in errors[:5]:
            print(f"  层{lat_idx}: {err}")
    
    # 保存结果
    output_file = os.path.join(OUTPUT_DIR, f"event_windows_{TEST_REGION['name']}.pkl")
    with open(output_file, 'wb') as f:
        pickle.dump(all_results, f)
    print(f"\n保存至: {output_file}")

if __name__ == "__main__":
    main()
