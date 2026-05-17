"""
脚本03: 计算GPP响应指标 (NC输出版)
- 抵抗力指标: 变化速率(rate), 变化幅度(amplitude)
- 恢复力指标: 恢复时间(recovery time)
- 输出: NetCDF格式 (带坐标信息)
"""
import os
import sys
import numpy as np
import pandas as pd
import netCDF4 as nc
from tqdm import tqdm
import pickle

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import *

def calc_response_metrics(window_data):
    """计算单个事件的响应指标"""
    gpp_z = window_data['gpp_z']
    window_before = 60  # 固定值
    window_after = window_data['window_after']
    
    pre_event = gpp_z[:window_before]
    post_event = gpp_z[window_before:]
    
    valid_pre = np.sum(~np.isnan(pre_event))
    valid_post = np.sum(~np.isnan(post_event))
    
    if valid_pre < 10 or valid_post < 10:
        return None
    
    baseline_mean = np.nanmean(pre_event)
    
    # 响应时间
    t_onset = None
    for i, val in enumerate(post_event):
        if not np.isnan(val) and val < THETA_DECLINE:
            t_onset = i
            break
    
    if np.all(np.isnan(post_event)):
        t_min, gpp_min = None, None
    else:
        t_min = int(np.nanargmin(post_event))
        gpp_min = float(np.nanmin(post_event))
    
    # 抵抗力
    if t_min is not None and t_min > 0:
        decline_rate = (gpp_min - baseline_mean) / (t_min + 1)
    else:
        decline_rate = None
    
    amp_max = gpp_min
    
    negative_vals = np.where(post_event < 0, post_event, 0)
    impact_area = float(np.nansum(negative_vals))
    
    # 恢复力
    t_recover = None
    if t_min is not None:
        for i in range(t_min + 1, len(post_event)):
            if not np.isnan(post_event[i]) and post_event[i] > THETA_RECOVER:
                t_recover = i - t_min
                break
    
    if t_min is not None and t_recover is not None and t_recover > 0 and gpp_min is not None:
        recovery_rate = (THETA_RECOVER - gpp_min) / t_recover
    else:
        recovery_rate = None
    
    return {
        'event_id': window_data['event_id'],
        'onset_year': window_data['onset_year'],
        'onset_doy': window_data['onset_doy'],
        'duration': window_data['duration'],
        'intensity': window_data['intensity'],
        't_onset': t_onset,
        't_min': t_min,
        'decline_rate': decline_rate,
        'amp_max': amp_max,
        'impact_area': impact_area,
        't_recover': t_recover,
        'recovery_rate': recovery_rate
    }

def save_pixel_metrics_nc(pixel_metrics, output_file, lat_arr, lon_arr):
    """保存像元级指标为NetCDF格式"""
    
    # 创建2D网格
    nlat, nlon = len(lat_arr), len(lon_arr)
    
    # 初始化指标数组
    metrics_names = ['n_events', 't_min_mean', 't_min_std', 'amp_max_mean', 'amp_max_std',
                     'decline_rate_mean', 'impact_area_mean', 't_recover_mean', 't_recover_std',
                     'recovery_rate_mean']
    
    data = {m: np.full((nlat, nlon), np.nan, dtype=np.float32) for m in metrics_names}
    
    # 填充数据
    for p in pixel_metrics:
        lat_idx = p['lat_idx']
        lon_idx = p['lon_idx']
        for m in metrics_names:
            if m in p and p[m] is not None:
                data[m][lat_idx, lon_idx] = p[m]
    
    # 写入NetCDF
    with nc.Dataset(output_file, 'w', format='NETCDF4') as ds:
        ds.createDimension('lat', nlat)
        ds.createDimension('lon', nlon)
        
        lat_var = ds.createVariable('lat', 'f4', ('lat',))
        lat_var[:] = lat_arr
        lat_var.units = 'degrees_north'
        
        lon_var = ds.createVariable('lon', 'f4', ('lon',))
        lon_var[:] = lon_arr
        lon_var.units = 'degrees_east'
        
        for m in metrics_names:
            var = ds.createVariable(m, 'f4', ('lat', 'lon'), zlib=True, fill_value=np.nan)
            var[:] = data[m]
            if 't_' in m:
                var.units = 'days'
            elif 'rate' in m:
                var.units = 'sigma/day'
            elif 'amp' in m:
                var.units = 'sigma'
        
        ds.title = f'GPP Response Metrics - {TEST_REGION["name"]}'
        ds.source = 'Flash Drought GPP Analysis'
    
    print(f"像元指标已保存: {output_file}")

def save_event_metrics_nc(event_metrics, output_file):
    """保存事件级指标为NetCDF格式"""
    
    n_events = len(event_metrics)
    
    with nc.Dataset(output_file, 'w', format='NETCDF4') as ds:
        ds.createDimension('event', n_events)
        
        # 坐标变量
        lat_var = ds.createVariable('lat', 'f4', ('event',))
        lon_var = ds.createVariable('lon', 'f4', ('event',))
        lat_var[:] = [e['lat'] for e in event_metrics]
        lon_var[:] = [e['lon'] for e in event_metrics]
        
        # 事件信息
        for field in ['event_id', 'onset_year', 'onset_doy', 'duration']:
            var = ds.createVariable(field, 'i4', ('event',), zlib=True)
            var[:] = [e.get(field, -1) for e in event_metrics]
        
        # 浮点指标
        for field in ['intensity', 't_onset', 't_min', 'decline_rate', 'amp_max', 
                      'impact_area', 't_recover', 'recovery_rate']:
            var = ds.createVariable(field, 'f4', ('event',), zlib=True, fill_value=np.nan)
            vals = []
            for e in event_metrics:
                v = e.get(field)
                vals.append(np.nan if v is None else float(v))
            var[:] = vals
        
        ds.title = f'GPP Event Metrics - {TEST_REGION["name"]}'
    
    print(f"事件指标已保存: {output_file}")

def process_pixel_results(pixel_data):
    """处理单像元的所有事件"""
    windows = pixel_data['windows']
    
    event_metrics = []
    for window in windows:
        metrics = calc_response_metrics(window)
        if metrics is not None:
            metrics['lat_idx'] = pixel_data['lat_idx']
            metrics['lon_idx'] = pixel_data['lon_idx']
            metrics['lat'] = pixel_data['lat']
            metrics['lon'] = pixel_data.get('lon', 0)
            event_metrics.append(metrics)
    
    if len(event_metrics) == 0:
        return None, None
    
    # 聚合像元级别指标
    df = pd.DataFrame(event_metrics)
    pixel_agg = {
        'lat_idx': pixel_data['lat_idx'],
        'lon_idx': pixel_data['lon_idx'],
        'lat': pixel_data['lat'],
        'lon': pixel_data.get('lon', 0),
        'n_events': len(df),
        't_min_mean': df['t_min'].mean(),
        't_min_std': df['t_min'].std(),
        'amp_max_mean': df['amp_max'].mean(),
        'amp_max_std': df['amp_max'].std(),
        'decline_rate_mean': df['decline_rate'].mean(),
        'impact_area_mean': df['impact_area'].mean(),
        't_recover_mean': df['t_recover'].mean(),
        't_recover_std': df['t_recover'].std(),
        'recovery_rate_mean': df['recovery_rate'].mean()
    }
    
    return event_metrics, pixel_agg

def main():
    print("=" * 60)
    print("Step 3: 计算GPP响应指标 (NC输出)")
    print("=" * 60)
    
    # 加载事件窗口数据
    input_file = os.path.join(OUTPUT_DIR, f"event_windows_{TEST_REGION['name']}.pkl")
    if not os.path.exists(input_file):
        print("Error: 请先运行 02_extract_events.py")
        return
    
    with open(input_file, 'rb') as f:
        pixel_results = pickle.load(f)
    
    print(f"\n加载像元数: {len(pixel_results)}")
    
    # 获取坐标范围
    lat_indices = sorted(set(p['lat_idx'] for p in pixel_results))
    lon_indices = sorted(set(p['lon_idx'] for p in pixel_results))
    
    # 从骤旱事件文件获取实际坐标
    with nc.Dataset(DROUGHT_EVENTS_FILE, 'r') as ds:
        lat_arr = ds.variables['lat'][min(lat_indices):max(lat_indices)+1]
        lon_arr = ds.variables['lon'][min(lon_indices):max(lon_indices)+1]
    
    # 调整索引为局部索引
    lat_offset = min(lat_indices)
    lon_offset = min(lon_indices)
    
    # 计算指标
    all_event_metrics = []
    all_pixel_agg = []
    
    for pixel_data in tqdm(pixel_results, desc="计算指标"):
        # 调整为局部索引
        pixel_data_copy = pixel_data.copy()
        pixel_data_copy['lat_idx'] = pixel_data['lat_idx'] - lat_offset
        pixel_data_copy['lon_idx'] = pixel_data['lon_idx'] - lon_offset
        
        # 添加lon信息 (如果缺失)
        if 'lon' not in pixel_data_copy:
            with nc.Dataset(DROUGHT_EVENTS_FILE, 'r') as ds:
                pixel_data_copy['lon'] = float(ds.variables['lon'][pixel_data['lon_idx']])
        
        event_metrics, pixel_agg = process_pixel_results(pixel_data_copy)
        if event_metrics is not None:
            all_event_metrics.extend(event_metrics)
            all_pixel_agg.append(pixel_agg)
    
    print(f"\n有效事件数: {len(all_event_metrics)}")
    print(f"有效像元数: {len(all_pixel_agg)}")
    
    # 保存为NetCDF
    output_pixels = os.path.join(OUTPUT_DIR, f"pixel_metrics_{TEST_REGION['name']}.nc")
    output_events = os.path.join(OUTPUT_DIR, f"event_metrics_{TEST_REGION['name']}.nc")
    
    save_pixel_metrics_nc(all_pixel_agg, output_pixels, lat_arr, lon_arr)
    save_event_metrics_nc(all_event_metrics, output_events)
    
    # 打印统计摘要
    df = pd.DataFrame(all_event_metrics)
    print("\n" + "=" * 40)
    print("结果摘要")
    print("=" * 40)
    print(f"响应时间 (t_min): 均值={df['t_min'].mean():.1f}天, 标准差={df['t_min'].std():.1f}天")
    print(f"抵抗力 (amp_max): 均值={df['amp_max'].mean():.2f}σ, 标准差={df['amp_max'].std():.2f}σ")
    print(f"恢复力 (t_recover): 均值={df['t_recover'].mean():.1f}天, 标准差={df['t_recover'].std():.1f}天")

if __name__ == "__main__":
    main()
