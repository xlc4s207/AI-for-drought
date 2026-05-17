"""
脚本01: 数据预处理
- 读取GPP和SM年度文件
- 统一时间轴 (处理闰年)
- 计算气候态和异常值
- 提取有效像元坐标
"""
import os
import numpy as np
import netCDF4 as nc
from datetime import datetime, timedelta
from tqdm import tqdm
import pickle

from config import *

def get_doy_from_date(year, month, day):
    """计算DOY"""
    return (datetime(year, month, day) - datetime(year, 1, 1)).days + 1

def is_leap_year(year):
    """判断闰年"""
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)

def load_gpp_year(year):
    """加载单年GPP数据"""
    filepath = os.path.join(GPP_DATA_DIR, f"BESS_GPP_{year}_0.1deg.nc")
    if not os.path.exists(filepath):
        print(f"Warning: GPP file not found for {year}")
        return None
    
    with nc.Dataset(filepath, 'r') as ds:
        gpp = ds.variables['GPP'][:]  # (time, lat, lon)
        lat = ds.variables['lat'][:]
        lon = ds.variables['lon'][:]
    return gpp, lat, lon

def load_sm_year(year):
    """加载单年SM数据"""
    filepath = os.path.join(SM_DATA_DIR, f"SMrz_{year}_GLEAM_v4.2a.nc")
    if not os.path.exists(filepath):
        print(f"Warning: SM file not found for {year}")
        return None
    
    with nc.Dataset(filepath, 'r') as ds:
        sm = ds.variables['SMrz'][:]  # (time, lat, lon)
    return sm

def load_valid_pixels():
    """从骤旱事件文件加载有效像元"""
    with nc.Dataset(DROUGHT_EVENTS_FILE, 'r') as ds:
        event_count = ds.variables['event_count'][:]
        lat = ds.variables['lat'][:]
        lon = ds.variables['lon'][:]
    
    # 有效像元: event_count > 0 且未被掩膜
    if hasattr(event_count, 'mask'):
        valid_mask = (event_count.data > 0) & (~event_count.mask)
    else:
        valid_mask = event_count > 0
    
    lat_idx, lon_idx = np.where(valid_mask)
    
    valid_pixels = []
    for i in range(len(lat_idx)):
        valid_pixels.append({
            'lat_idx': int(lat_idx[i]),
            'lon_idx': int(lon_idx[i]),
            'lat': float(lat[lat_idx[i]]),
            'lon': float(lon[lon_idx[i]]),
            'event_count': int(event_count[lat_idx[i], lon_idx[i]])
        })
    
    return valid_pixels, valid_mask, lat, lon

def filter_by_region(valid_pixels, region):
    """按区域筛选像元"""
    filtered = []
    for p in valid_pixels:
        if (region['lat_min'] <= p['lat'] <= region['lat_max'] and
            region['lon_min'] <= p['lon'] <= region['lon_max']):
            filtered.append(p)
    return filtered

def calc_climatology_pixel(ts_years, n_doy=366):
    """
    计算单像元的气候态
    ts_years: dict {year: array(time,)} 每年的时间序列
    返回: clim_mean[366], clim_std[366]
    """
    doy_values = [[] for _ in range(n_doy)]
    
    for year, ts in ts_years.items():
        days = len(ts)
        for d in range(days):
            # 对于非闰年,将DOY 60-365映射到60-366
            if days == 365 and d >= 59:
                doy = d + 1  # 跳过2月29日
            else:
                doy = d
            if not np.isnan(ts[d]):
                doy_values[doy].append(ts[d])
    
    clim_mean = np.zeros(n_doy)
    clim_std = np.zeros(n_doy)
    
    for doy in range(n_doy):
        if len(doy_values[doy]) > 0:
            clim_mean[doy] = np.nanmean(doy_values[doy])
            clim_std[doy] = np.nanstd(doy_values[doy])
        else:
            clim_mean[doy] = np.nan
            clim_std[doy] = np.nan
    
    return clim_mean, clim_std

def calc_anomaly(ts, doy_indices, clim_mean, clim_std):
    """
    计算异常值
    ts: 时间序列
    doy_indices: 每个时间点对应的DOY索引
    clim_mean, clim_std: 气候态
    返回: anom, z_score
    """
    anom = np.full_like(ts, np.nan, dtype=np.float32)
    z_score = np.full_like(ts, np.nan, dtype=np.float32)
    
    for i, doy in enumerate(doy_indices):
        if not np.isnan(ts[i]) and not np.isnan(clim_mean[doy]):
            anom[i] = ts[i] - clim_mean[doy]
            if clim_std[doy] > 0:
                z_score[i] = anom[i] / clim_std[doy]
    
    return anom, z_score

def main():
    print("=" * 60)
    print("Step 1: 数据预处理")
    print("=" * 60)
    
    # 1. 加载有效像元
    print("\n[1/4] 加载有效像元...")
    valid_pixels, valid_mask, lat, lon = load_valid_pixels()
    print(f"  总有效像元数: {len(valid_pixels)}")
    
    # 保存有效像元信息
    output_file = os.path.join(OUTPUT_DIR, "valid_pixels.pkl")
    with open(output_file, 'wb') as f:
        pickle.dump({
            'pixels': valid_pixels,
            'mask': valid_mask,
            'lat': lat,
            'lon': lon
        }, f)
    print(f"  保存至: {output_file}")
    
    # 2. 筛选测试区域
    print(f"\n[2/4] 筛选测试区域: {TEST_REGION['name']}")
    test_pixels = filter_by_region(valid_pixels, TEST_REGION)
    print(f"  测试区域像元数: {len(test_pixels)}")
    
    output_file = os.path.join(OUTPUT_DIR, f"valid_pixels_{TEST_REGION['name']}.pkl")
    with open(output_file, 'wb') as f:
        pickle.dump(test_pixels, f)
    print(f"  保存至: {output_file}")
    
    # 3. 创建DOY索引
    print("\n[3/4] 创建DOY索引映射...")
    doy_indices = {}
    for year in range(START_YEAR, END_YEAR + 1):
        days = 366 if is_leap_year(year) else 365
        if days == 365:
            # 非闰年: DOY 1-59 -> 0-58, DOY 60-365 -> 60-365 (跳过59)
            indices = list(range(59)) + list(range(60, 366))
        else:
            indices = list(range(366))
        doy_indices[year] = indices
    
    # 保存DOY映射
    with open(os.path.join(OUTPUT_DIR, "doy_indices.pkl"), 'wb') as f:
        pickle.dump(doy_indices, f)
    
    print("\n[4/4] 数据预处理完成!")
    print(f"  测试区域: {TEST_REGION['name']}")
    print(f"  测试像元数: {len(test_pixels)}")

if __name__ == "__main__":
    main()
