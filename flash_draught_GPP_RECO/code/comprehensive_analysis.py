#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPP-RECO 骤旱响应综合分析
分析内容:
1. 有效/无效像元事件统计
2. 空间分布 (TIF)
3. 季节性无响应事件分析
4. GPP vs RECO 响应对比 (同一像元SMrz/SMs骤旱)
"""
import numpy as np
import pandas as pd
import netCDF4 as nc
from osgeo import gdal, osr
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os
from tqdm import tqdm

# ================= 配置 =================
BASE_DIR = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO'
OUTPUT_DIR = os.path.join(BASE_DIR, 'analysis_result')
TIF_DIR = os.path.join(OUTPUT_DIR, 'spatial_tif')
FIGURE_DIR = os.path.join(OUTPUT_DIR, 'figures')

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TIF_DIR, exist_ok=True)
os.makedirs(FIGURE_DIR, exist_ok=True)

NC_FILES = {
    'SMrz_GPP': os.path.join(BASE_DIR, 'SMrz_GPP_results/gpp_response_events_global_v10.nc'),
    'SMrz_RECO': os.path.join(BASE_DIR, 'SMrz_RECO_results/reco_response_events_global_v10.nc'),
    'SMs_GPP': os.path.join(BASE_DIR, 'SMs_GPP_results/gpp_response_SMs_events_global_v10.nc'),
    'SMs_RECO': os.path.join(BASE_DIR, 'SMs_RECO_results/reco_response_SMs_drought_v10_global_merged.nc'),
}

SEASONS_NORTH = {'Spring': [3,4,5], 'Summer': [6,7,8], 'Autumn': [9,10,11], 'Winter': [12,1,2]}
SEASONS_SOUTH = {'Autumn': [3,4,5], 'Winter': [6,7,8], 'Spring': [9,10,11], 'Summer': [12,1,2]}

# ================= 工具函数 =================
def doy_to_month(doy, year):
    try:
        return (datetime(int(year), 1, 1) + timedelta(days=int(doy) - 1)).month
    except:
        return 1

def get_season(month, lat):
    seasons = SEASONS_NORTH if lat >= 0 else SEASONS_SOUTH
    for season, months in seasons.items():
        if month in months:
            return season
    return 'Unknown'

def load_nc_data(filepath, var_prefix):
    """加载 NC 数据并返回 DataFrame"""
    print(f"Loading: {filepath}")
    ds = nc.Dataset(filepath, 'r')
    
    min_var = f'{var_prefix}_min'
    trend_var = f'{var_prefix}_trend'
    
    data = {
        'lat': ds.variables['lat'][:].data,
        'lon': ds.variables['lon'][:].data,
        'event_id': ds.variables['event_id'][:].data,
        'onset_year': ds.variables['onset_year'][:].data,
        'onset_doy': ds.variables['onset_doy'][:].data,
        'response_detected': ds.variables['response_detected'][:].data,
        f'{var_prefix}_min': ds.variables[min_var][:].data,
        f'{var_prefix}_trend': ds.variables[trend_var][:].data,
        't_response': ds.variables['t_response'][:].data,
        't_min': ds.variables['t_min'][:].data,
        't_impact': ds.variables['t_impact'][:].data,
        't_recover': ds.variables['t_recover'][:].data,
    }
    ds.close()
    
    df = pd.DataFrame(data)
    print(f"  Total events: {len(df)}")
    return df

def create_geotiff(lat, lon, values, output_file, resolution=0.1):
    """创建 GeoTIFF"""
    lat_min, lat_max = -60, 90
    lon_min, lon_max = -180, 180
    n_rows = int((lat_max - lat_min) / resolution)
    n_cols = int((lon_max - lon_min) / resolution)
    raster = np.full((n_rows, n_cols), np.nan, dtype=np.float32)
    
    rows = ((lat_max - lat) / resolution).astype(int)
    cols = ((lon - lon_min) / resolution).astype(int)
    valid = (rows >= 0) & (rows < n_rows) & (cols >= 0) & (cols < n_cols) & ~np.isnan(values)
    raster[rows[valid], cols[valid]] = values[valid]
    
    driver = gdal.GetDriverByName('GTiff')
    out_ds = driver.Create(output_file, n_cols, n_rows, 1, gdal.GDT_Float32, options=['COMPRESS=LZW'])
    out_ds.SetGeoTransform([lon_min, resolution, 0, lat_max, 0, -resolution])
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    out_ds.SetProjection(srs.ExportToWkt())
    out_ds.GetRasterBand(1).WriteArray(raster)
    out_ds.GetRasterBand(1).SetNoDataValue(np.nan)
    out_ds = None

# ================= 分析 1: 有效/无效事件统计 =================
def analyze_event_validity(all_data):
    print("\n=== 分析1: 有效/无效事件统计 ===")
    results = []
    
    for name, df in all_data.items():
        valid_count = (df['response_detected'] == 1).sum()
        invalid_count = (df['response_detected'] == 0).sum()
        total = len(df)
        
        result = {
            'Dataset': name,
            'Total Events': total,
            'Valid Events': valid_count,
            'Invalid Events': invalid_count,
            'Valid Ratio (%)': 100 * valid_count / total,
            'Invalid Ratio (%)': 100 * invalid_count / total,
        }
        results.append(result)
        print(f"  {name}: Valid={valid_count:,} ({result['Valid Ratio (%)']:.1f}%), Invalid={invalid_count:,}")
    
    df_results = pd.DataFrame(results)
    df_results.to_csv(os.path.join(OUTPUT_DIR, 'event_validity_stats.csv'), index=False)
    return df_results

# ================= 分析 2: 空间分布 =================
def analyze_spatial_distribution(all_data):
    print("\n=== 分析2: 空间分布 (生成TIF) ===")
    
    for name, df in all_data.items():
        # 有效事件密度
        valid_df = df[df['response_detected'] == 1]
        if len(valid_df) > 0:
            counts = valid_df.groupby(['lat', 'lon']).size().reset_index(name='count')
            output = os.path.join(TIF_DIR, f'{name}_valid_event_count.tif')
            create_geotiff(counts['lat'].values, counts['lon'].values, 
                          counts['count'].values.astype(np.float32), output)
            print(f"  Created: {name}_valid_event_count.tif")
        
        # 无效事件密度
        invalid_df = df[df['response_detected'] == 0]
        if len(invalid_df) > 0:
            counts = invalid_df.groupby(['lat', 'lon']).size().reset_index(name='count')
            output = os.path.join(TIF_DIR, f'{name}_invalid_event_count.tif')
            create_geotiff(counts['lat'].values, counts['lon'].values, 
                          counts['count'].values.astype(np.float32), output)
            print(f"  Created: {name}_invalid_event_count.tif")

# ================= 分析 3: 季节性无响应分析 =================
def analyze_seasonal_no_response(all_data):
    print("\n=== 分析3: 季节性无响应事件分析 ===")
    results = []
    
    for name, df in all_data.items():
        # 添加季节信息
        invalid_df = df[df['response_detected'] == 0].copy()
        if len(invalid_df) == 0:
            continue
            
        # 计算季节 (采样以加速)
        sample_size = min(100000, len(invalid_df))
        sample_df = invalid_df.sample(n=sample_size, random_state=42) if len(invalid_df) > sample_size else invalid_df
        
        seasons = []
        for _, row in tqdm(sample_df.iterrows(), total=len(sample_df), desc=f"  {name}"):
            month = doy_to_month(row['onset_doy'], row['onset_year'])
            seasons.append(get_season(month, row['lat']))
        sample_df = sample_df.copy()
        sample_df['season'] = seasons
        
        # 统计
        season_counts = sample_df['season'].value_counts()
        for season, count in season_counts.items():
            ratio = 100 * count / len(sample_df)
            results.append({
                'Dataset': name,
                'Season': season,
                'No-Response Count': count,
                'Ratio (%)': ratio
            })
            print(f"    {season}: {count:,} ({ratio:.1f}%)")
    
    df_results = pd.DataFrame(results)
    df_results.to_csv(os.path.join(OUTPUT_DIR, 'seasonal_no_response_stats.csv'), index=False)
    
    # 绘图
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    datasets = df_results['Dataset'].unique()
    for i, dataset in enumerate(datasets):
        ax = axes.flat[i]
        subset = df_results[df_results['Dataset'] == dataset]
        seasons_order = ['Spring', 'Summer', 'Autumn', 'Winter']
        subset = subset.set_index('Season').reindex(seasons_order).reset_index()
        ax.bar(subset['Season'], subset['Ratio (%)'], color=['green', 'red', 'orange', 'blue'])
        ax.set_title(dataset)
        ax.set_ylabel('No-Response Ratio (%)')
        ax.set_ylim(0, 50)
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURE_DIR, 'seasonal_no_response.png'), dpi=150)
    plt.close()
    print("  Saved figure: seasonal_no_response.png")
    
    return df_results

# ================= 分析 4: GPP vs RECO 对比 =================
def analyze_gpp_reco_comparison(all_data):
    print("\n=== 分析4: GPP vs RECO 响应对比 ===")
    
    for drought_type in ['SMrz', 'SMs']:
        gpp_name = f'{drought_type}_GPP'
        reco_name = f'{drought_type}_RECO'
        
        if gpp_name not in all_data or reco_name not in all_data:
            continue
        
        gpp_df = all_data[gpp_name]
        reco_df = all_data[reco_name]
        
        # 过滤有效事件
        gpp_valid = gpp_df[gpp_df['response_detected'] == 1].copy()
        reco_valid = reco_df[reco_df['response_detected'] == 1].copy()
        
        # 按像元(lat, lon)聚合平均
        print(f"  {drought_type}: Aggregating by pixel...")
        gpp_agg = gpp_valid.groupby(['lat', 'lon']).agg({
            'gpp_min': 'mean',
            'gpp_trend': 'mean',
            't_response': 'mean',
            't_impact': 'mean'
        }).reset_index()
        gpp_agg.columns = ['lat', 'lon', 'gpp_min', 'gpp_trend', 'gpp_t_response', 'gpp_t_impact']
        
        reco_agg = reco_valid.groupby(['lat', 'lon']).agg({
            'reco_min': 'mean',
            'reco_trend': 'mean',
            't_response': 'mean',
            't_impact': 'mean'
        }).reset_index()
        reco_agg.columns = ['lat', 'lon', 'reco_min', 'reco_trend', 'reco_t_response', 'reco_t_impact']
        
        # 合并 (同一像元)
        merged = pd.merge(gpp_agg, reco_agg, on=['lat', 'lon'], how='inner')
        print(f"    Common pixels: {len(merged):,}")
        
        if len(merged) == 0:
            continue
        
        # 计算对比指标
        merged['decline_diff'] = merged['gpp_min'] - merged['reco_min']  # GPP下降幅度 - RECO下降幅度
        merged['trend_diff'] = merged['gpp_trend'] - merged['reco_trend']  # GPP下降速率 - RECO下降速率
        merged['response_diff'] = merged['gpp_t_response'] - merged['reco_t_response']  # 响应时间差
        
        # 保存
        output_file = os.path.join(OUTPUT_DIR, f'{drought_type}_GPP_RECO_comparison.csv')
        merged.to_csv(output_file, index=False)
        print(f"    Saved: {drought_type}_GPP_RECO_comparison.csv")
        
        # 统计摘要
        summary = {
            'Drought Type': drought_type,
            'Common Pixels': len(merged),
            'GPP_min (mean)': merged['gpp_min'].mean(),
            'RECO_min (mean)': merged['reco_min'].mean(),
            'GPP_trend (mean)': merged['gpp_trend'].mean(),
            'RECO_trend (mean)': merged['reco_trend'].mean(),
            'GPP_t_response (mean)': merged['gpp_t_response'].mean(),
            'RECO_t_response (mean)': merged['reco_t_response'].mean(),
        }
        print(f"    GPP下降幅度: {summary['GPP_min (mean)']:.3f}, RECO下降幅度: {summary['RECO_min (mean)']:.3f}")
        print(f"    GPP下降速率: {summary['GPP_trend (mean)']:.4f}, RECO下降速率: {summary['RECO_trend (mean)']:.4f}")
        
        # 生成空间对比 TIF
        create_geotiff(merged['lat'].values, merged['lon'].values, 
                      merged['decline_diff'].values, 
                      os.path.join(TIF_DIR, f'{drought_type}_GPP_minus_RECO_decline.tif'))
        create_geotiff(merged['lat'].values, merged['lon'].values, 
                      merged['trend_diff'].values, 
                      os.path.join(TIF_DIR, f'{drought_type}_GPP_minus_RECO_trend.tif'))
        print(f"    Created spatial difference TIFs")
        
        # 绘制对比散点图
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        
        ax = axes[0]
        ax.scatter(merged['gpp_min'], merged['reco_min'], alpha=0.1, s=1)
        ax.plot([-1, 0], [-1, 0], 'r--', label='1:1 line')
        ax.set_xlabel('GPP Min (normalized)')
        ax.set_ylabel('RECO Min (normalized)')
        ax.set_title(f'{drought_type}: Decline Magnitude')
        ax.legend()
        
        ax = axes[1]
        ax.scatter(merged['gpp_trend'], merged['reco_trend'], alpha=0.1, s=1)
        ax.axhline(0, color='gray', linestyle='--', alpha=0.5)
        ax.axvline(0, color='gray', linestyle='--', alpha=0.5)
        ax.set_xlabel('GPP Trend')
        ax.set_ylabel('RECO Trend')
        ax.set_title(f'{drought_type}: Decline Rate')
        
        ax = axes[2]
        ax.scatter(merged['gpp_t_response'], merged['reco_t_response'], alpha=0.1, s=1)
        ax.plot([0, 30], [0, 30], 'r--', label='1:1 line')
        ax.set_xlabel('GPP Response Time (8d)')
        ax.set_ylabel('RECO Response Time (8d)')
        ax.set_title(f'{drought_type}: Response Time')
        ax.legend()
        
        plt.tight_layout()
        plt.savefig(os.path.join(FIGURE_DIR, f'{drought_type}_GPP_RECO_scatter.png'), dpi=150)
        plt.close()
        print(f"    Saved figure: {drought_type}_GPP_RECO_scatter.png")

# ================= 主函数 =================
def main():
    print("=" * 60)
    print("GPP-RECO 骤旱响应综合分析")
    print("=" * 60)
    
    # 加载所有数据
    all_data = {}
    for name, filepath in NC_FILES.items():
        if not os.path.exists(filepath):
            print(f"Warning: {filepath} not found, skipping.")
            continue
        var_prefix = 'gpp' if 'GPP' in name else 'reco'
        all_data[name] = load_nc_data(filepath, var_prefix)
    
    # 执行分析
    analyze_event_validity(all_data)
    analyze_spatial_distribution(all_data)
    analyze_seasonal_no_response(all_data)
    analyze_gpp_reco_comparison(all_data)
    
    print("\n" + "=" * 60)
    print(f"分析完成! 结果保存在: {OUTPUT_DIR}")
    print("=" * 60)

if __name__ == '__main__':
    main()
