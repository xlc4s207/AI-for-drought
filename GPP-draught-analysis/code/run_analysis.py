"""
骤旱对GPP影响的完整分析流水线
对应 analysis_plan.md 中的 8 个步骤

使用方法: python run_analysis.py

输出:
  - pixel_metrics_{region}.nc: 每像元聚合指标
  - event_metrics_{region}.nc: 每事件详细指标
"""
import os
import sys
import numpy as np
import netCDF4 as nc
import pandas as pd
from datetime import datetime
from tqdm import tqdm
import pickle
from multiprocessing import Pool

# ============================================
# 配置参数
# ============================================
BASE_DIR = "/home/xulc/flash_drought"
OUTPUT_DIR = os.path.join(BASE_DIR, "process/GPP-draught-analysis/SMrz_GPPresult")

# 数据文件
MERGED_GPP_FILE = os.path.join(OUTPUT_DIR, "GPP_merged_1982_2022.nc")
DROUGHT_EVENTS_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMrz/flash_drought_events_details_v2.nc")
SM_DATA_DIR = os.path.join(BASE_DIR, "gleam/SMrz_dd")

# 时间范围
START_YEAR = 1982
END_YEAR = 2022

# 事件窗口参数
WINDOW_BEFORE = 60   # 事件前天数
WINDOW_AFTER = 120   # 事件后天数
MIN_WINDOW_AFTER = 30

# 响应阈值
THETA_DECLINE = -0.5   # 下降阈值 (σ)
THETA_RECOVER = -0.25  # 恢复阈值 (σ)

# 测试区域 (美国西部)
TEST_REGION = {
    'name': 'US_West',
    'lat_min': 30, 'lat_max': 45,
    'lon_min': -125, 'lon_max': -100
}

# 并行参数
N_WORKERS = 50

# ============================================
# 工具函数
# ============================================
def date_to_absolute_day(year, doy, base_year=1982):
    """将年+DOY转换为绝对天数"""
    days = 0
    for y in range(base_year, year):
        days += 366 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 365
    return days + doy - 1

def absolute_day_to_date(abs_day, base_year=1982):
    """将绝对天数转回年+DOY"""
    year = base_year
    while True:
        days_in_year = 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365
        if abs_day < days_in_year:
            return year, abs_day + 1
        abs_day -= days_in_year
        year += 1

# ============================================
# Step 1-3: 数据准备与有效像元提取
# ============================================
def step1_extract_valid_pixels():
    """提取测试区域内有骤旱事件的像元"""
    print("\n" + "="*60)
    print("Step 1: 提取有效像元")
    print("="*60)
    
    with nc.Dataset(DROUGHT_EVENTS_FILE, 'r') as ds:
        lat = ds.variables['lat'][:]
        lon = ds.variables['lon'][:]
        event_count = ds.variables['event_count'][:]
        
        # 筛选测试区域
        lat_mask = (lat >= TEST_REGION['lat_min']) & (lat <= TEST_REGION['lat_max'])
        lon_mask = (lon >= TEST_REGION['lon_min']) & (lon <= TEST_REGION['lon_max'])
        
        valid_pixels = []
        for i, la in enumerate(lat):
            if not lat_mask[i]:
                continue
            for j, lo in enumerate(lon):
                if not lon_mask[j]:
                    continue
                if event_count[i, j] > 0:
                    valid_pixels.append({
                        'lat_idx': i, 'lon_idx': j,
                        'lat': float(la), 'lon': float(lo),
                        'event_count': int(event_count[i, j])
                    })
    
    print(f"测试区域: {TEST_REGION['name']}")
    print(f"有效像元: {len(valid_pixels)}")
    
    # 保存
    output_file = os.path.join(OUTPUT_DIR, f"valid_pixels_{TEST_REGION['name']}.pkl")
    with open(output_file, 'wb') as f:
        pickle.dump(valid_pixels, f)
    
    return valid_pixels

# ============================================
# Step 4-5: 事件提取与异常值计算
# ============================================
def calc_climatology(ts):
    """计算气候态"""
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

def process_lat_row(args):
    """处理单个纬度行"""
    lat_idx, lat_val, valid_lon_indices = args
    
    results = []
    
    # 读取GPP数据
    with nc.Dataset(MERGED_GPP_FILE, 'r') as ds_gpp:
        gpp_row = ds_gpp.variables['GPP'][:, lat_idx, :]
        if hasattr(gpp_row, 'mask'):
            gpp_row = gpp_row.filled(np.nan)
    
    # 读取事件
    with nc.Dataset(DROUGHT_EVENTS_FILE, 'r') as ds_events:
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
            lon_val = float(ds_events.variables['lon'][lon_idx])
            gpp_ts = gpp_row[:, lon_idx].astype(np.float32)
            
            if np.all(np.isnan(gpp_ts)):
                continue
            
            clim_mean, clim_std = calc_climatology(gpp_ts)
            
            # 提取事件窗口
            total_days = len(gpp_ts)
            windows = []
            
            for idx, event in enumerate(events):
                onset_day = event['onset_abs_day']
                window_start = onset_day - WINDOW_BEFORE
                window_end = onset_day + WINDOW_AFTER
                
                if idx + 1 < len(events):
                    next_onset = events[idx + 1]['onset_abs_day']
                    if next_onset <= window_end:
                        window_end = next_onset - 1
                
                actual_after = window_end - onset_day
                if actual_after < MIN_WINDOW_AFTER:
                    continue
                if window_start < 0 or window_end >= total_days:
                    continue
                
                gpp_window = gpp_ts[window_start:window_end + 1].copy()
                
                # 计算z-score
                gpp_z = np.full_like(gpp_window, np.nan)
                for j, abs_day in enumerate(range(window_start, window_end + 1)):
                    year, doy = absolute_day_to_date(abs_day)
                    is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
                    clim_idx = doy - 1 if is_leap else ((doy - 1) if doy <= 59 else doy)
                    if clim_idx < 366 and not np.isnan(gpp_window[j]) and not np.isnan(clim_mean[clim_idx]):
                        if clim_std[clim_idx] > 0:
                            gpp_z[j] = (gpp_window[j] - clim_mean[clim_idx]) / clim_std[clim_idx]
                
                windows.append({
                    **event,
                    'window_after': actual_after,
                    'gpp_z': gpp_z
                })
            
            if windows:
                results.append({
                    'lat_idx': lat_idx, 'lon_idx': lon_idx,
                    'lat': lat_val, 'lon': lon_val,
                    'windows': windows
                })
    
    return results

def step2_extract_events(valid_pixels):
    """提取事件窗口 (50核并行)"""
    print("\n" + "="*60)
    print("Step 2: 提取事件窗口 (50核并行)")
    print("="*60)
    
    # 按纬度分组
    lat_groups = {}
    for p in valid_pixels:
        lat_idx = p['lat_idx']
        if lat_idx not in lat_groups:
            lat_groups[lat_idx] = {'lat': p['lat'], 'lon_indices': []}
        lat_groups[lat_idx]['lon_indices'].append(p['lon_idx'])
    
    tasks = [(lat_idx, lat_groups[lat_idx]['lat'], lat_groups[lat_idx]['lon_indices']) 
             for lat_idx in sorted(lat_groups.keys())]
    
    print(f"纬度行数: {len(tasks)}")
    
    all_results = []
    with Pool(processes=N_WORKERS) as pool:
        for results in tqdm(pool.imap_unordered(process_lat_row, tasks), 
                           total=len(tasks), desc="处理纬度行"):
            all_results.extend(results)
    
    print(f"有效像元: {len(all_results)}")
    total_events = sum(len(r['windows']) for r in all_results)
    print(f"有效事件: {total_events}")
    
    return all_results

# ============================================
# Step 6: 计算响应指标
# ============================================
def calc_metrics(window):
    """计算单事件响应指标"""
    gpp_z = window['gpp_z']
    
    pre_event = gpp_z[:WINDOW_BEFORE]
    post_event = gpp_z[WINDOW_BEFORE:]
    
    if np.sum(~np.isnan(pre_event)) < 10 or np.sum(~np.isnan(post_event)) < 10:
        return None
    
    baseline = np.nanmean(pre_event)
    
    # t_onset
    t_onset = None
    for i, val in enumerate(post_event):
        if not np.isnan(val) and val < THETA_DECLINE:
            t_onset = i
            break
    
    # t_min, amp_max
    if np.all(np.isnan(post_event)):
        return None
    t_min = int(np.nanargmin(post_event))
    amp_max = float(np.nanmin(post_event))
    
    # decline_rate
    decline_rate = (amp_max - baseline) / (t_min + 1) if t_min > 0 else None
    
    # impact_area
    impact_area = float(np.nansum(np.where(post_event < 0, post_event, 0)))
    
    # t_recover
    t_recover = None
    for i in range(t_min + 1, len(post_event)):
        if not np.isnan(post_event[i]) and post_event[i] > THETA_RECOVER:
            t_recover = i - t_min
            break
    
    # recovery_rate
    if t_recover and t_recover > 0:
        recovery_rate = (THETA_RECOVER - amp_max) / t_recover
    else:
        recovery_rate = None
    
    return {
        'event_id': window['event_id'],
        'onset_year': window['onset_year'],
        'onset_doy': window['onset_doy'],
        'duration': window['onset_days'] + window['drought_days'],
        'intensity': window['intensity'],
        't_onset': t_onset,
        't_min': t_min,
        'amp_max': amp_max,
        'decline_rate': decline_rate,
        'impact_area': impact_area,
        't_recover': t_recover,
        'recovery_rate': recovery_rate
    }

def step3_calc_metrics(pixel_results):
    """计算响应指标"""
    print("\n" + "="*60)
    print("Step 3: 计算响应指标")
    print("="*60)
    
    all_events = []
    all_pixels = []
    
    for pixel in tqdm(pixel_results, desc="计算指标"):
        event_list = []
        for w in pixel['windows']:
            m = calc_metrics(w)
            if m:
                m['lat'] = pixel['lat']
                m['lon'] = pixel['lon']
                m['lat_idx'] = pixel['lat_idx']
                m['lon_idx'] = pixel['lon_idx']
                event_list.append(m)
        
        if event_list:
            all_events.extend(event_list)
            
            # 像元聚合
            df = pd.DataFrame(event_list)
            all_pixels.append({
                'lat_idx': pixel['lat_idx'],
                'lon_idx': pixel['lon_idx'],
                'lat': pixel['lat'],
                'lon': pixel['lon'],
                'n_events': len(df),
                't_min_mean': df['t_min'].mean(),
                'amp_max_mean': df['amp_max'].mean(),
                't_recover_mean': df['t_recover'].mean(),
                'decline_rate_mean': df['decline_rate'].mean(),
                'recovery_rate_mean': df['recovery_rate'].mean(),
                'impact_area_mean': df['impact_area'].mean()
            })
    
    print(f"有效事件: {len(all_events)}")
    print(f"有效像元: {len(all_pixels)}")
    
    return all_events, all_pixels

# ============================================
# Step 7: 保存结果为NC格式
# ============================================
def step4_save_results(all_events, all_pixels):
    """保存结果为NetCDF格式"""
    print("\n" + "="*60)
    print("Step 4: 保存结果 (NetCDF格式)")
    print("="*60)
    
    # === 事件级结果 ===
    event_file = os.path.join(OUTPUT_DIR, f"event_metrics_{TEST_REGION['name']}.nc")
    n = len(all_events)
    
    with nc.Dataset(event_file, 'w', format='NETCDF4') as ds:
        ds.createDimension('event', n)
        
        # 坐标
        ds.createVariable('lat', 'f4', ('event',))[:] = [e['lat'] for e in all_events]
        ds.createVariable('lon', 'f4', ('event',))[:] = [e['lon'] for e in all_events]
        
        # 整型字段
        for f in ['event_id', 'onset_year', 'onset_doy', 'duration']:
            ds.createVariable(f, 'i4', ('event',))[:] = [e.get(f, -1) for e in all_events]
        
        # 浮点字段
        for f in ['intensity', 't_onset', 't_min', 'amp_max', 'decline_rate', 
                  'impact_area', 't_recover', 'recovery_rate']:
            var = ds.createVariable(f, 'f4', ('event',), fill_value=np.nan)
            var[:] = [e.get(f) if e.get(f) is not None else np.nan for e in all_events]
        
        ds.title = f'Event Metrics - {TEST_REGION["name"]}'
    
    print(f"事件结果: {event_file}")
    
    # === 像元级结果 ===
    pixel_file = os.path.join(OUTPUT_DIR, f"pixel_metrics_{TEST_REGION['name']}.nc")
    
    # 获取坐标范围
    lat_indices = sorted(set(p['lat_idx'] for p in all_pixels))
    lon_indices = sorted(set(p['lon_idx'] for p in all_pixels))
    
    with nc.Dataset(DROUGHT_EVENTS_FILE, 'r') as ds_ref:
        lat_arr = ds_ref.variables['lat'][min(lat_indices):max(lat_indices)+1]
        lon_arr = ds_ref.variables['lon'][min(lon_indices):max(lon_indices)+1]
    
    lat_offset = min(lat_indices)
    lon_offset = min(lon_indices)
    nlat, nlon = len(lat_arr), len(lon_arr)
    
    metrics = ['n_events', 't_min_mean', 'amp_max_mean', 't_recover_mean', 
               'decline_rate_mean', 'recovery_rate_mean', 'impact_area_mean']
    
    with nc.Dataset(pixel_file, 'w', format='NETCDF4') as ds:
        ds.createDimension('lat', nlat)
        ds.createDimension('lon', nlon)
        
        ds.createVariable('lat', 'f4', ('lat',))[:] = lat_arr
        ds.createVariable('lon', 'f4', ('lon',))[:] = lon_arr
        ds.variables['lat'].units = 'degrees_north'
        ds.variables['lon'].units = 'degrees_east'
        
        # 初始化数据
        data = {m: np.full((nlat, nlon), np.nan, dtype=np.float32) for m in metrics}
        
        for p in all_pixels:
            i = p['lat_idx'] - lat_offset
            j = p['lon_idx'] - lon_offset
            for m in metrics:
                if p.get(m) is not None:
                    data[m][i, j] = p[m]
        
        for m in metrics:
            var = ds.createVariable(m, 'f4', ('lat', 'lon'), zlib=True, fill_value=np.nan)
            var[:] = data[m]
        
        ds.title = f'Pixel Metrics - {TEST_REGION["name"]}'
    
    print(f"像元结果: {pixel_file}")

# ============================================
# 主程序
# ============================================
def main():
    print("="*60)
    print("骤旱对GPP影响分析 - 完整流水线")
    print("="*60)
    print(f"测试区域: {TEST_REGION['name']}")
    print(f"GPP数据: {MERGED_GPP_FILE}")
    print(f"时间范围: {START_YEAR}-{END_YEAR}")
    
    # Step 1: 提取有效像元
    valid_pixels = step1_extract_valid_pixels()
    
    # Step 2: 提取事件窗口
    pixel_results = step2_extract_events(valid_pixels)
    
    # Step 3: 计算响应指标
    all_events, all_pixels = step3_calc_metrics(pixel_results)
    
    # Step 4: 保存结果
    step4_save_results(all_events, all_pixels)
    
    # 打印摘要
    print("\n" + "="*60)
    print("分析完成 - 结果摘要")
    print("="*60)
    df = pd.DataFrame(all_events)
    print(f"响应时间 (t_min): 均值={df['t_min'].mean():.1f}天")
    print(f"抵抗力 (amp_max): 均值={df['amp_max'].mean():.2f}σ")
    print(f"恢复力 (t_recover): 均值={df['t_recover'].mean():.1f}天")

if __name__ == "__main__":
    main()
