#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
骤旱强度和持续时间分析
分析SMrz和SMs骤旱事件的空间分布特征和土地利用类型差异
"""

import numpy as np
import pandas as pd
import netCDF4 as nc
from osgeo import gdal, osr
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# 配置
NC_FILE_SMRZ = '/home/xulc/flash_drought/gleam/clip_result/SMrz/flash_drought_events_details_v2.nc'
NC_FILE_SMS = '/home/xulc/flash_drought/gleam/clip_result/SMs/flash_drought_SMs_events_details_v2.nc'
LC_FILE = '/home/xulc/flash_drought/land_use/MCD12C1_LC_Type1_2010_11km.tif'
OUTPUT_DIR = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO/analysis_result/draught_sensity'

IGBP_CLASSES = {
    1: 'Evergreen Needleleaf Forest',
    2: 'Evergreen Broadleaf Forest',
    3: 'Deciduous Needleleaf Forest',
    4: 'Deciduous Broadleaf Forest',
    5: 'Mixed Forests',
    6: 'Closed Shrublands',
    7: 'Open Shrublands',
    8: 'Woody Savannas',
    9: 'Savannas',
    10: 'Grasslands',
    11: 'Permanent Wetlands',
    12: 'Croplands'
}

def create_output_dir():
    """创建输出目录"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"输出目录: {OUTPUT_DIR}")

def load_land_use_data():
    """加载土地利用数据"""
    print("\n加载土地利用数据...")
    ds = gdal.Open(LC_FILE)
    band = ds.GetRasterBand(1)
    lc_data = band.ReadAsArray()
    gt = ds.GetGeoTransform()
    projection = ds.GetProjection()
    ds = None
    return lc_data, gt, projection

def analyze_drought_events(nc_path, dataset_name):
    """
    分析骤旱事件的强度和持续时间
    
    Returns:
    --------
    dict: 包含各种统计指标的字典
    """
    print(f"\n{'='*80}")
    print(f"分析数据集: {dataset_name}")
    print(f"文件: {os.path.basename(nc_path)}")
    print(f"{'='*80}\n")
    
    with nc.Dataset(nc_path, 'r') as ds:
        # 读取坐标
        lats = ds.variables['lat'][:]
        lons = ds.variables['lon'][:]
        
        # 读取事件数量
        event_count = ds.variables['event_count'][:]
        
        # 读取持续时间和强度
        drought_days = ds.variables['drought_days'][:]  # (max_events, lat, lon)
        intensity = ds.variables['intensity'][:]
        onset_days = ds.variables['onset_days'][:]
        onset_rate = ds.variables['onset_rate'][:]
        
        # 获取填充值
        fill_value_days = ds.variables['drought_days']._FillValue
        fill_value_intensity = ds.variables['intensity']._FillValue
    
    print(f"数据维度: {drought_days.shape}")
    print(f"纬度范围: {lats.min():.2f} 到 {lats.max():.2f}")
    print(f"经度范围: {lons.min():.2f} 到 {lons.max():.2f}")
    
    # 统计总事件数
    total_events = np.sum(event_count[event_count != -1])
    pixels_with_events = np.sum(event_count > 0)
    
    print(f"\n基本统计:")
    print(f"  总事件数: {total_events:,}")
    print(f"  有事件的像元数: {pixels_with_events:,}")
    print(f"  平均每个像元事件数: {total_events/pixels_with_events:.2f}")
    
    # 创建掩膜
    valid_mask_days = (drought_days != fill_value_days) & (drought_days > 0)
    valid_mask_intensity = (intensity != fill_value_intensity) & (~np.isnan(intensity))
    valid_mask_onset = (onset_days != fill_value_days) & (onset_days > 0)
    valid_mask_rate = (onset_rate != fill_value_intensity) & (~np.isnan(onset_rate))
    
    # 计算平均持续时间（每个像元的平均）
    # 对于每个像元，计算其所有事件的平均值
    mean_drought_days = np.full((len(lats), len(lons)), np.nan, dtype=np.float32)
    mean_intensity = np.full((len(lats), len(lons)), np.nan, dtype=np.float32)
    mean_onset_days = np.full((len(lats), len(lons)), np.nan, dtype=np.float32)
    mean_onset_rate = np.full((len(lats), len(lons)), np.nan, dtype=np.float32)
    
    print("\n计算像元平均值...")
    for i in range(len(lats)):
        if i % 200 == 0:
            print(f"  处理进度: {i}/{len(lats)} ({i/len(lats)*100:.1f}%)")
        
        for j in range(len(lons)):
            if event_count[i, j] > 0:
                # 持续时间
                valid_days = drought_days[:, i, j][valid_mask_days[:, i, j]]
                if len(valid_days) > 0:
                    mean_drought_days[i, j] = np.mean(valid_days)
                
                # 强度
                valid_int = intensity[:, i, j][valid_mask_intensity[:, i, j]]
                if len(valid_int) > 0:
                    mean_intensity[i, j] = np.mean(valid_int)
                
                # 发生期持续时间
                valid_onset = onset_days[:, i, j][valid_mask_onset[:, i, j]]
                if len(valid_onset) > 0:
                    mean_onset_days[i, j] = np.mean(valid_onset)
                
                # 发生速率
                valid_rate = onset_rate[:, i, j][valid_mask_rate[:, i, j]]
                if len(valid_rate) > 0:
                    mean_onset_rate[i, j] = np.mean(valid_rate)
    
    # 全局统计
    valid_duration = mean_drought_days[~np.isnan(mean_drought_days)]
    valid_intensity_vals = mean_intensity[~np.isnan(mean_intensity)]
    valid_onset = mean_onset_days[~np.isnan(mean_onset_days)]
    valid_rate = mean_onset_rate[~np.isnan(mean_onset_rate)]
    
    print(f"\n全局平均统计:")
    print(f"  平均持续时间: {np.mean(valid_duration):.2f} ± {np.std(valid_duration):.2f} 天")
    print(f"  持续时间范围: {np.min(valid_duration):.2f} - {np.max(valid_duration):.2f} 天")
    print(f"  平均强度: {np.mean(valid_intensity_vals):.4f} ± {np.std(valid_intensity_vals):.4f}")
    print(f"  强度范围: {np.min(valid_intensity_vals):.4f} - {np.max(valid_intensity_vals):.4f}")
    print(f"  平均发生期: {np.mean(valid_onset):.2f} ± {np.std(valid_onset):.2f} 天")
    print(f"  平均发生速率: {np.mean(valid_rate):.6f} ± {np.std(valid_rate):.6f}")
    
    return {
        'lats': lats,
        'lons': lons,
        'event_count': event_count,
        'mean_drought_days': mean_drought_days,
        'mean_intensity': mean_intensity,
        'mean_onset_days': mean_onset_days,
        'mean_onset_rate': mean_onset_rate,
        'total_events': total_events,
        'pixels_with_events': pixels_with_events,
        'stats': {
            'duration_mean': np.mean(valid_duration),
            'duration_std': np.std(valid_duration),
            'duration_min': np.min(valid_duration),
            'duration_max': np.max(valid_duration),
            'intensity_mean': np.mean(valid_intensity_vals),
            'intensity_std': np.std(valid_intensity_vals),
            'intensity_min': np.min(valid_intensity_vals),
            'intensity_max': np.max(valid_intensity_vals),
            'onset_days_mean': np.mean(valid_onset),
            'onset_days_std': np.std(valid_onset),
            'onset_rate_mean': np.mean(valid_rate),
            'onset_rate_std': np.std(valid_rate)
        }
    }

def save_geotiff(data, output_path, lons, lats, projection, nodata_value=np.nan):
    """保存为GeoTIFF格式"""
    driver = gdal.GetDriverByName('GTiff')
    rows, cols = data.shape
    
    # 创建地理变换
    lon_res = (lons[-1] - lons[0]) / (len(lons) - 1)
    lat_res = (lats[-1] - lats[0]) / (len(lats) - 1)
    geo_transform = (lons[0] - lon_res/2, lon_res, 0,
                     lats[0] - lat_res/2, 0, lat_res)
    
    # 创建输出数据集
    out_ds = driver.Create(output_path, cols, rows, 1, gdal.GDT_Float32,
                           options=['COMPRESS=LZW'])
    out_ds.SetGeoTransform(geo_transform)
    out_ds.SetProjection(projection)
    
    band = out_ds.GetRasterBand(1)
    band.SetNoDataValue(nodata_value if not np.isnan(nodata_value) else -9999)
    
    # 替换NaN为nodata
    data_copy = data.copy()
    if np.isnan(nodata_value):
        data_copy[np.isnan(data_copy)] = -9999
        band.SetNoDataValue(-9999)
    
    band.WriteArray(data_copy)
    band.FlushCache()
    
    out_ds = None
    print(f"  已保存: {os.path.basename(output_path)}")

def analyze_by_land_use(result, lc_data, lc_gt, dataset_name):
    """按土地利用类型分析"""
    print(f"\n按土地利用类型分析 ({dataset_name})...")
    
    lats = result['lats']
    lons = result['lons']
    
    # 创建经纬度网格
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    
    # 映射到土地利用数据
    origin_x = lc_gt[0]
    origin_y = lc_gt[3]
    pixel_width = lc_gt[1]
    pixel_height = lc_gt[5]
    
    cols = ((lon_grid - origin_x) / pixel_width).astype(int)
    rows = ((lat_grid - origin_y) / pixel_height).astype(int)
    
    rows = np.clip(rows, 0, lc_data.shape[0] - 1)
    cols = np.clip(cols, 0, lc_data.shape[1] - 1)
    
    lc_classes = lc_data[rows, cols]
    
    # 按类型统计
    lc_stats = []
    
    for class_id in range(1, 13):
        class_name = IGBP_CLASSES[class_id]
        class_mask = (lc_classes == class_id)
        
        # 提取该类型的数据
        duration_vals = result['mean_drought_days'][class_mask]
        intensity_vals = result['mean_intensity'][class_mask]
        onset_vals = result['mean_onset_days'][class_mask]
        rate_vals = result['mean_onset_rate'][class_mask]
        event_count_vals = result['event_count'][class_mask]
        
        # 移除NaN
        duration_valid = duration_vals[~np.isnan(duration_vals)]
        intensity_valid = intensity_vals[~np.isnan(intensity_vals)]
        onset_valid = onset_vals[~np.isnan(onset_vals)]
        rate_valid = rate_vals[~np.isnan(rate_vals)]
        event_count_valid = event_count_vals[event_count_vals > 0]
        
        if len(duration_valid) == 0:
            print(f"  Class {class_id:2d} ({class_name}): 无有效数据")
            continue
        
        print(f"  Class {class_id:2d} ({class_name}): "
              f"像元数={len(duration_valid):,}, "
              f"平均持续={np.mean(duration_valid):.2f}天, "
              f"平均强度={np.mean(intensity_valid):.4f}")
        
        stats = {
            'Dataset': dataset_name,
            'Class_ID': class_id,
            'Class_Name': class_name,
            'Pixel_Count': len(duration_valid),
            'Total_Events': np.sum(event_count_valid),
            'Avg_Events_Per_Pixel': np.mean(event_count_valid),
            'Duration_Mean': np.mean(duration_valid),
            'Duration_Std': np.std(duration_valid),
            'Duration_Min': np.min(duration_valid),
            'Duration_Max': np.max(duration_valid),
            'Intensity_Mean': np.mean(intensity_valid),
            'Intensity_Std': np.std(intensity_valid),
            'Intensity_Min': np.min(intensity_valid),
            'Intensity_Max': np.max(intensity_valid),
            'Onset_Days_Mean': np.mean(onset_valid) if len(onset_valid) > 0 else np.nan,
            'Onset_Days_Std': np.std(onset_valid) if len(onset_valid) > 0 else np.nan,
            'Onset_Rate_Mean': np.mean(rate_valid) if len(rate_valid) > 0 else np.nan,
            'Onset_Rate_Std': np.std(rate_valid) if len(rate_valid) > 0 else np.nan
        }
        
        lc_stats.append(stats)
    
    return pd.DataFrame(lc_stats), lc_classes

def create_land_use_maps(result, lc_classes, lc_gt, projection, dataset_name):
    """创建各土地利用类型的专题地图"""
    print(f"\n创建土地利用类型专题地图 ({dataset_name})...")
    
    lats = result['lats']
    lons = result['lons']
    
    maps_dir = os.path.join(OUTPUT_DIR, 'maps', dataset_name.lower())
    os.makedirs(maps_dir, exist_ok=True)
    
    for class_id in range(1, 13):
        class_name = IGBP_CLASSES[class_id].replace(' ', '_')
        
        # 创建掩膜
        class_mask = (lc_classes == class_id)
        
        # 持续时间地图
        duration_map = result['mean_drought_days'].copy()
        duration_map[~class_mask] = np.nan
        
        if np.sum(~np.isnan(duration_map)) > 0:
            output_path = os.path.join(maps_dir, f'Class_{class_id:02d}_{class_name}_duration.tif')
            save_geotiff(duration_map, output_path, lons, lats, projection)
        
        # 强度地图
        intensity_map = result['mean_intensity'].copy()
        intensity_map[~class_mask] = np.nan
        
        if np.sum(~np.isnan(intensity_map)) > 0:
            output_path = os.path.join(maps_dir, f'Class_{class_id:02d}_{class_name}_intensity.tif')
            save_geotiff(intensity_map, output_path, lons, lats, projection)

def create_markdown_report(smrz_result, sms_result, smrz_lc_stats, sms_lc_stats):
    """创建Markdown分析报告"""
    output_path = os.path.join(OUTPUT_DIR, 'drought_severity_analysis_report.md')
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# 骤旱强度和持续时间分析报告\n\n")
        f.write(f"**分析日期**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        
        # 数据来源
        f.write("## 1. 数据来源\n\n")
        f.write("- **SMrz数据**: `flash_drought_events_details_v2.nc` (根区土壤湿度)\n")
        f.write("- **SMs数据**: `flash_drought_SMs_events_details_v2.nc` (表层土壤湿度)\n")
        f.write("- **时间范围**: 1980-2024 (45年)\n")
        f.write("- **空间分辨率**: 0.1° × 0.1°\n\n")
        
        # 总体统计
        f.write("---\n\n")
        f.write("## 2. 全球骤旱事件统计\n\n")
        
        f.write("### 2.1 事件数量\n\n")
        f.write("| 指标 | SMrz (根区) | SMs (表层) |\n")
        f.write("|------|------------|----------|\n")
        f.write(f"| 总事件数 | {smrz_result['total_events']:,} | {sms_result['total_events']:,} |\n")
        f.write(f"| 有事件的像元数 | {smrz_result['pixels_with_events']:,} | {sms_result['pixels_with_events']:,} |\n")
        f.write(f"| 平均每像元事件数 | {smrz_result['total_events']/smrz_result['pixels_with_events']:.2f} | {sms_result['total_events']/sms_result['pixels_with_events']:.2f} |\n\n")
        
        f.write("### 2.2 持续时间统计\n\n")
        f.write("| 指标 | SMrz (根区) | SMs (表层) |\n")
        f.write("|------|------------|----------|\n")
        f.write(f"| 平均持续时间 (天) | {smrz_result['stats']['duration_mean']:.2f} ± {smrz_result['stats']['duration_std']:.2f} | {sms_result['stats']['duration_mean']:.2f} ± {sms_result['stats']['duration_std']:.2f} |\n")
        f.write(f"| 最短持续时间 (天) | {smrz_result['stats']['duration_min']:.2f} | {sms_result['stats']['duration_min']:.2f} |\n")
        f.write(f"| 最长持续时间 (天) | {smrz_result['stats']['duration_max']:.2f} | {sms_result['stats']['duration_max']:.2f} |\n\n")
        
        f.write("### 2.3 强度统计\n\n")
        f.write("| 指标 | SMrz (根区) | SMs (表层) |\n")
        f.write("|------|------------|----------|\n")
        f.write(f"| 平均强度 | {smrz_result['stats']['intensity_mean']:.4f} ± {smrz_result['stats']['intensity_std']:.4f} | {sms_result['stats']['intensity_mean']:.4f} ± {sms_result['stats']['intensity_std']:.4f} |\n")
        f.write(f"| 最小强度 | {smrz_result['stats']['intensity_min']:.4f} | {sms_result['stats']['intensity_min']:.4f} |\n")
        f.write(f"| 最大强度 | {smrz_result['stats']['intensity_max']:.4f} | {sms_result['stats']['intensity_max']:.4f} |\n\n")
        
        f.write("### 2.4 发生期特征\n\n")
        f.write("| 指标 | SMrz (根区) | SMs (表层) |\n")
        f.write("|------|------------|----------|\n")
        f.write(f"| 平均发生期 (天) | {smrz_result['stats']['onset_days_mean']:.2f} ± {smrz_result['stats']['onset_days_std']:.2f} | {sms_result['stats']['onset_days_mean']:.2f} ± {sms_result['stats']['onset_days_std']:.2f} |\n")
        f.write(f"| 平均发生速率 | {smrz_result['stats']['onset_rate_mean']:.6f} ± {smrz_result['stats']['onset_rate_std']:.6f} | {sms_result['stats']['onset_rate_mean']:.6f} ± {sms_result['stats']['onset_rate_std']:.6f} |\n\n")
        
        # 土地利用类型分析
        f.write("---\n\n")
        f.write("## 3. 不同土地利用类型的骤旱特征\n\n")
        
        f.write("### 3.1 持续时间对比\n\n")
        f.write("| 土地类型 | SMrz持续时间(天) | SMs持续时间(天) | 差异 |\n")
        f.write("|---------|----------------|---------------|-----|\n")
        
        for class_id in range(1, 13):
            smrz_row = smrz_lc_stats[smrz_lc_stats['Class_ID'] == class_id]
            sms_row = sms_lc_stats[sms_lc_stats['Class_ID'] == class_id]
            
            if len(smrz_row) > 0 and len(sms_row) > 0:
                class_name = smrz_row.iloc[0]['Class_Name']
                smrz_dur = smrz_row.iloc[0]['Duration_Mean']
                sms_dur = sms_row.iloc[0]['Duration_Mean']
                diff = smrz_dur - sms_dur
                
                f.write(f"| {class_name} | {smrz_dur:.2f} ± {smrz_row.iloc[0]['Duration_Std']:.2f} | "
                       f"{sms_dur:.2f} ± {sms_row.iloc[0]['Duration_Std']:.2f} | {diff:+.2f} |\n")
        
        f.write("\n### 3.2 强度对比\n\n")
        f.write("| 土地类型 | SMrz强度 | SMs强度 | 差异 |\n")
        f.write("|---------|---------|--------|-----|\n")
        
        for class_id in range(1, 13):
            smrz_row = smrz_lc_stats[smrz_lc_stats['Class_ID'] == class_id]
            sms_row = sms_lc_stats[sms_lc_stats['Class_ID'] == class_id]
            
            if len(smrz_row) > 0 and len(sms_row) > 0:
                class_name = smrz_row.iloc[0]['Class_Name']
                smrz_int = smrz_row.iloc[0]['Intensity_Mean']
                sms_int = sms_row.iloc[0]['Intensity_Mean']
                diff = smrz_int - sms_int
                
                f.write(f"| {class_name} | {smrz_int:.4f} ± {smrz_row.iloc[0]['Intensity_Std']:.4f} | "
                       f"{sms_int:.4f} ± {sms_row.iloc[0]['Intensity_Std']:.4f} | {diff:+.4f} |\n")
        
        # 关键发现
        f.write("\n---\n\n")
        f.write("## 4. 关键发现\n\n")
        
        # 持续时间最长的类型
        f.write("### 4.1 持续时间特征\n\n")
        
        smrz_longest = smrz_lc_stats.nlargest(3, 'Duration_Mean')[['Class_Name', 'Duration_Mean']]
        sms_longest = sms_lc_stats.nlargest(3, 'Duration_Mean')[['Class_Name', 'Duration_Mean']]
        
        f.write("**持续时间最长的土地类型 (SMrz):**\n\n")
        for idx, row in smrz_longest.iterrows():
            f.write(f"- {row['Class_Name']}: {row['Duration_Mean']:.2f} 天\n")
        
        f.write("\n**持续时间最长的土地类型 (SMs):**\n\n")
        for idx, row in sms_longest.iterrows():
            f.write(f"- {row['Class_Name']}: {row['Duration_Mean']:.2f} 天\n")
        
        # 强度最大的类型
        f.write("\n### 4.2 强度特征\n\n")
        
        smrz_intense = smrz_lc_stats.nlargest(3, 'Intensity_Mean')[['Class_Name', 'Intensity_Mean']]
        sms_intense = sms_lc_stats.nlargest(3, 'Intensity_Mean')[['Class_Name', 'Intensity_Mean']]
        
        f.write("**强度最大的土地类型 (SMrz):**\n\n")
        for idx, row in smrz_intense.iterrows():
            f.write(f"- {row['Class_Name']}: {row['Intensity_Mean']:.4f}\n")
        
        f.write("\n**强度最大的土地类型 (SMs):**\n\n")
        for idx, row in sms_intense.iterrows():
            f.write(f"- {row['Class_Name']}: {row['Intensity_Mean']:.4f}\n")
        
        # 输出文件说明
        f.write("\n---\n\n")
        f.write("## 5. 输出文件\n\n")
        f.write("### 5.1 空间分布地图\n\n")
        f.write("- `smrz_mean_duration.tif`: SMrz平均持续时间空间分布\n")
        f.write("- `smrz_mean_intensity.tif`: SMrz平均强度空间分布\n")
        f.write("- `sms_mean_duration.tif`: SMs平均持续时间空间分布\n")
        f.write("- `sms_mean_intensity.tif`: SMs平均强度空间分布\n\n")
        
        f.write("### 5.2 土地利用类型地图\n\n")
        f.write("位于 `maps/smrz/` 和 `maps/sms/` 目录下\n\n")
        f.write("- `Class_XX_<类型名>_duration.tif`: 各土地类型的持续时间分布\n")
        f.write("- `Class_XX_<类型名>_intensity.tif`: 各土地类型的强度分布\n\n")
        
        f.write("### 5.3 统计数据\n\n")
        f.write("- `drought_severity_statistics.csv`: 总体统计汇总\n")
        f.write("- `smrz_landuse_severity_stats.csv`: SMrz土地利用类型统计\n")
        f.write("- `sms_landuse_severity_stats.csv`: SMs土地利用类型统计\n\n")
        
        f.write("---\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print(f"\n✓ 报告已保存: {output_path}")

def main():
    print("\n" + "="*80)
    print("骤旱强度和持续时间分析")
    print("="*80)
    
    # 创建输出目录
    create_output_dir()
    
    # 加载土地利用数据
    lc_data, lc_gt, projection = load_land_use_data()
    
    # 分析SMrz数据
    smrz_result = analyze_drought_events(NC_FILE_SMRZ, 'SMrz')
    
    # 分析SMs数据
    sms_result = analyze_drought_events(NC_FILE_SMS, 'SMs')
    
    # 保存全局空间分布地图
    print("\n" + "="*80)
    print("保存全局空间分布地图")
    print("="*80 + "\n")
    
    save_geotiff(smrz_result['mean_drought_days'], 
                os.path.join(OUTPUT_DIR, 'smrz_mean_duration.tif'),
                smrz_result['lons'], smrz_result['lats'], projection)
    
    save_geotiff(smrz_result['mean_intensity'],
                os.path.join(OUTPUT_DIR, 'smrz_mean_intensity.tif'),
                smrz_result['lons'], smrz_result['lats'], projection)
    
    save_geotiff(smrz_result['mean_onset_days'],
                os.path.join(OUTPUT_DIR, 'smrz_mean_onset_days.tif'),
                smrz_result['lons'], smrz_result['lats'], projection)
    
    save_geotiff(sms_result['mean_drought_days'],
                os.path.join(OUTPUT_DIR, 'sms_mean_duration.tif'),
                sms_result['lons'], sms_result['lats'], projection)
    
    save_geotiff(sms_result['mean_intensity'],
                os.path.join(OUTPUT_DIR, 'sms_mean_intensity.tif'),
                sms_result['lons'], sms_result['lats'], projection)
    
    save_geotiff(sms_result['mean_onset_days'],
                os.path.join(OUTPUT_DIR, 'sms_mean_onset_days.tif'),
                sms_result['lons'], sms_result['lats'], projection)
    
    # 按土地利用类型分析
    print("\n" + "="*80)
    print("按土地利用类型分析")
    print("="*80)
    
    smrz_lc_stats, smrz_lc_classes = analyze_by_land_use(smrz_result, lc_data, lc_gt, 'SMrz')
    sms_lc_stats, sms_lc_classes = analyze_by_land_use(sms_result, lc_data, lc_gt, 'SMs')
    
    # 创建土地利用类型专题地图
    create_land_use_maps(smrz_result, smrz_lc_classes, lc_gt, projection, 'SMrz')
    create_land_use_maps(sms_result, sms_lc_classes, lc_gt, projection, 'SMs')
    
    # 保存统计结果
    print("\n" + "="*80)
    print("保存统计结果")
    print("="*80 + "\n")
    
    # 总体统计
    overall_stats = pd.DataFrame([
        {
            'Dataset': 'SMrz',
            'Total_Events': smrz_result['total_events'],
            'Pixels_With_Events': smrz_result['pixels_with_events'],
            **{f'Duration_{k}': v for k, v in smrz_result['stats'].items() if 'duration' in k.lower()},
            **{f'Intensity_{k}': v for k, v in smrz_result['stats'].items() if 'intensity' in k.lower()},
            **{f'Onset_{k}': v for k, v in smrz_result['stats'].items() if 'onset' in k.lower()}
        },
        {
            'Dataset': 'SMs',
            'Total_Events': sms_result['total_events'],
            'Pixels_With_Events': sms_result['pixels_with_events'],
            **{f'Duration_{k}': v for k, v in sms_result['stats'].items() if 'duration' in k.lower()},
            **{f'Intensity_{k}': v for k, v in sms_result['stats'].items() if 'intensity' in k.lower()},
            **{f'Onset_{k}': v for k, v in sms_result['stats'].items() if 'onset' in k.lower()}
        }
    ])
    
    overall_csv = os.path.join(OUTPUT_DIR, 'drought_severity_statistics.csv')
    overall_stats.to_csv(overall_csv, index=False, encoding='utf-8-sig')
    print(f"✓ 已保存: {overall_csv}")
    
    # 土地利用类型统计
    smrz_lc_csv = os.path.join(OUTPUT_DIR, 'smrz_landuse_severity_stats.csv')
    sms_lc_csv = os.path.join(OUTPUT_DIR, 'sms_landuse_severity_stats.csv')
    
    smrz_lc_stats.to_csv(smrz_lc_csv, index=False, encoding='utf-8-sig')
    sms_lc_stats.to_csv(sms_lc_csv, index=False, encoding='utf-8-sig')
    
    print(f"✓ 已保存: {smrz_lc_csv}")
    print(f"✓ 已保存: {sms_lc_csv}")
    
    # 创建Markdown报告
    create_markdown_report(smrz_result, sms_result, smrz_lc_stats, sms_lc_stats)
    
    print("\n" + "="*80)
    print("分析完成！")
    print("="*80)
    print(f"\n所有结果已保存到: {OUTPUT_DIR}")
    print("\n生成的文件:")
    print("  - 6个全局空间分布TIF文件")
    print("  - 48个土地利用类型专题TIF文件 (12类 × 2变量 × 2数据集)")
    print("  - 3个统计CSV文件")
    print("  - 1个Markdown分析报告")
    print()

if __name__ == '__main__':
    main()
