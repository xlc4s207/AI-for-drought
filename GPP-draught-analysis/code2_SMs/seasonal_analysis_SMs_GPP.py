#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
骤旱GPP响应的季节性分析 (SMs 表层土壤湿度版)
Input: gpp_response_SMs_events_global_v10.nc
"""
import numpy as np
import pandas as pd
import netCDF4 as nc
from osgeo import gdal, osr
import os
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from tqdm import tqdm

# ================= 配置 =================
BASE_DIR = "/home/xulc/flash_drought"
NC_FILE = os.path.join(BASE_DIR, 'process/GPP-draught-analysis/code2_SMs/results/gpp_response_SMs_events_global_v10.nc')
OUTPUT_DIR = os.path.join(BASE_DIR, 'process/GPP-draught-analysis/code2_SMs/results/seasonal_analysis')
TIF_DIR = os.path.join(OUTPUT_DIR, 'tif')
FIGURE_DIR = os.path.join(OUTPUT_DIR, 'figures')

TARGET_VAR = 'gpp_min'  # 分析的目标变量
TARGET_NAME = 'GPP'     # 显示名称

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TIF_DIR, exist_ok=True)
os.makedirs(FIGURE_DIR, exist_ok=True)

# 季节定义
SEASONS_NORTH = {
    'Spring': {'months': [3, 4, 5], 'name_zh': '春季'},
    'Summer': {'months': [6, 7, 8], 'name_zh': '夏季'},
    'Autumn': {'months': [9, 10, 11], 'name_zh': '秋季'},
    'Winter': {'months': [12, 1, 2], 'name_zh': '冬季'}
}
SEASONS_SOUTH = {
    'Autumn': {'months': [3, 4, 5], 'name_zh': '秋季'},
    'Winter': {'months': [6, 7, 8], 'name_zh': '冬季'},
    'Spring': {'months': [9, 10, 11], 'name_zh': '春季'},
    'Summer': {'months': [12, 1, 2], 'name_zh': '夏季'}
}

def doy_to_month(doy, year):
    date = datetime(year, 1, 1) + timedelta(days=int(doy) - 1)
    return date.month

def get_season_from_month(month, hemisphere):
    seasons = SEASONS_NORTH if hemisphere == 'north' else SEASONS_SOUTH
    for season, info in seasons.items():
        if month in info['months']:
            return season
    return None

def calculate_drought_season_vectorized(onset_years, onset_doys, durations, lats):
    n = len(onset_years)
    seasons = np.empty(n, dtype=object)
    
    for i in tqdm(range(n), desc="计算季节", unit="事件"):
        onset_year = int(onset_years[i])
        onset_doy = int(onset_doys[i])
        duration = durations[i]
        lat = lats[i]
        
        hemisphere = 'north' if lat >= 0 else 'south'
        
        # 简单逻辑：以开始时间所在季节为主 (如果持续时间短)
        # 或者计算覆盖天数最多的季节
        month = doy_to_month(onset_doy, onset_year)
        seasons[i] = get_season_from_month(month, hemisphere)
        
    return seasons

def read_and_classify_events():
    print(f"正在读取: {NC_FILE}")
    ds = nc.Dataset(NC_FILE, 'r')
    
    # 获取变量
    try:
        data = {
            'lat': ds.variables['lat'][:].data,
            'lon': ds.variables['lon'][:].data,
            'event_id': ds.variables['event_id'][:].data,
            'onset_year': ds.variables['onset_year'][:].data,
            'onset_doy': ds.variables['onset_doy'][:].data,
            'response_detected': ds.variables['response_detected'][:].data,
            't_response': ds.variables['t_response'][:].data,
            't_min': ds.variables['t_min'][:].data,
            't_impact': ds.variables['t_impact'][:].data,
            't_recover': ds.variables['t_recover'][:].data,
            'recovery_rate': ds.variables['recovery_rate'][:].data,
            'target_min': ds.variables[TARGET_VAR][:].data,  # 动态读取
        }
    except KeyError as e:
        print(f"Error reading variables: {e}")
        # 兼容不同文件结构
        if 'lat_coord' in ds.variables:
             # 如果是合并后的文件，可能lat是坐标变量，需要另外处理？
             # 不，合并脚本保存时 'lat' 是 (event,) 变量
             pass
        raise
        
    ds.close()
    
    # 过滤无效响应
    valid_mask = data['response_detected'] == 1
    print(f"有效事件数: {np.sum(valid_mask)}")
    
    df = pd.DataFrame({key: data[key][valid_mask] for key in data.keys()})
    df['duration'] = df['t_min'] # 近似
    
    print("计算季节...")
    df['season'] = calculate_drought_season_vectorized(
        df['onset_year'].values,
        df['onset_doy'].values,
        df['duration'].values,
        df['lat'].values
    )
    
    return df

def analyze_seasonal_response(df):
    results = {}
    seasons = ['Spring', 'Summer', 'Autumn', 'Winter']
    
    for season in seasons:
        season_data = df[df['season'] == season]
        if len(season_data) == 0: continue
        
        stats = {
            'event_count': len(season_data),
            't_response_mean': season_data['t_response'].mean(),
            't_response_std': season_data['t_response'].std(),
            't_impact_mean': season_data['t_impact'].mean(),
            't_recover_mean': season_data['t_recover'].replace(-9999, np.nan).mean(), # 处理缺失
            'recovery_rate': 100 * (season_data['t_recover'] > 0).sum() / len(season_data),
            'target_min_mean': season_data['target_min'].mean(),
        }
        results[season] = stats
        
        print(f"\n[{season}]")
        print(f"  Count: {stats['event_count']}")
        print(f"  Response Time: {stats['t_response_mean']:.1f}")
        print(f"  {TARGET_NAME} Min: {stats['target_min_mean']:.2f}")

    return results

def create_seasonal_spatial_maps(df):
    print("生成 TIF...")
    resolution = 0.1
    lat_min, lat_max = -60, 90
    lon_min, lon_max = -180, 180
    n_rows = int((lat_max - lat_min) / resolution)
    n_cols = int((lon_max - lon_min) / resolution)
    
    for season in ['Spring', 'Summer', 'Autumn', 'Winter']:
        season_data = df[df['season'] == season].copy()
        if len(season_data) == 0: continue
        
        # 优化: 向量化替换无效值
        if 't_recover' in season_data.columns:
            season_data['t_recover'] = season_data['t_recover'].replace(-9999, np.nan)
        
        # 聚合 - 包括所有需要的变量
        pixel_stats = season_data.groupby(['lat', 'lon']).agg({
            't_response': 'mean',
            'target_min': 'mean',
            't_min': 'mean',
            't_impact': 'mean',
            't_recover': 'mean', 
            'event_id': 'count'
        }).reset_index()
        
        # 变量映射 (文件名 -> DataFrame列名)
        metrics = {
            'event_count': 'event_id',
            f'{TARGET_VAR}': 'target_min', # gpp_min 或 reco_min
            't_response': 't_response',
            't_min': 't_min',
            't_impact': 't_impact',
            't_recover': 't_recover'
        }
        
        for file_suffix, col_name in metrics.items():
            raster = np.full((n_rows, n_cols), np.nan, dtype=np.float32)
            lats = pixel_stats['lat'].values
            lons = pixel_stats['lon'].values
            
            # 检查列是否存在
            if col_name in pixel_stats:
                values = pixel_stats[col_name].values
                
                rows = ((lat_max - lats) / resolution).astype(int)
                cols = ((lons - lon_min) / resolution).astype(int)
                
                # Bounds check
                valid = (rows >= 0) & (rows < n_rows) & (cols >= 0) & (cols < n_cols)
                raster[rows[valid], cols[valid]] = values[valid]
            
            # 文件名格式: Season_variable.tif
            output_file = os.path.join(TIF_DIR, f'{season}_{file_suffix}.tif')
            save_geotiff(raster, output_file, lon_min, lat_max, resolution, file_suffix)

def save_geotiff(raster, output_file, lon_min, lat_max, resolution, description):
    driver = gdal.GetDriverByName('GTiff')
    n_rows, n_cols = raster.shape
    out_ds = driver.Create(output_file, n_cols, n_rows, 1, gdal.GDT_Float32, options=['COMPRESS=LZW'])
    out_ds.SetGeoTransform([lon_min, resolution, 0, lat_max, 0, -resolution])
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    out_ds.SetProjection(srs.ExportToWkt())
    band = out_ds.GetRasterBand(1)
    band.WriteArray(raster)
    band.SetNoDataValue(np.nan)
    band.FlushCache()
    out_ds = None

def create_comparison_figures(df, stats):
    print("生成图表...")
    # 简化的绘图逻辑
    seasons = ['Spring', 'Summer', 'Autumn', 'Winter']
    
    fig, ax = plt.subplots(figsize=(10, 6))
    counts = [stats.get(s, {}).get('event_count', 0) for s in seasons]
    ax.bar(seasons, counts, color='skyblue', edgecolor='black')
    ax.set_title(f'Seasonal {TARGET_NAME} Response Event Counts')
    plt.savefig(os.path.join(FIGURE_DIR, 'seasonal_counts.png'))
    plt.close()
    
    fig, ax = plt.subplots(figsize=(10, 6))
    resp = [stats.get(s, {}).get('t_response_mean', 0) for s in seasons]
    ax.bar(seasons, resp, color='lightgreen', edgecolor='black')
    ax.set_title(f'Seasonal Mean Response Time')
    plt.savefig(os.path.join(FIGURE_DIR, 'seasonal_response_time.png'))
    plt.close()

def main():
    df = read_and_classify_events()
    stats = analyze_seasonal_response(df)
    create_seasonal_spatial_maps(df)
    create_comparison_figures(df, stats)
    
    # 保存统计CSV
    pd.DataFrame(stats).T.to_csv(os.path.join(OUTPUT_DIR, 'seasonal_stats.csv'))
    print(f"完成! 结果保存在: {OUTPUT_DIR}")

if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
