#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPP响应与未响应骤旱事件对比分析
分析有GPP响应和无GPP响应的骤旱事件在强度和持续时间上的差异
"""

import numpy as np
import pandas as pd
import netCDF4 as nc
from osgeo import gdal, osr
import os
from datetime import datetime
import warnings
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from functools import partial
import multiprocessing as mp
warnings.filterwarnings('ignore')

# 设置线程数（使用CPU核心数的一半以避免过载）
N_WORKERS = max(1, mp.cpu_count() // 2)

# 配置
GPP_RESPONSE_FILE = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO/SMrz_GPP_results/gpp_response_events_global_v10.nc'
DROUGHT_DETAILS_FILE = '/home/xulc/flash_drought/gleam/clip_result/SMrz/flash_drought_events_details_v2.nc'
LC_FILE = '/home/xulc/flash_drought/land_use/MCD12C1_LC_Type1_2010_11km.tif'
OUTPUT_DIR = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO/analysis_result/non_response_analysis'

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
    print(f"输出目录: {OUTPUT_DIR}\n")

def load_gpp_response_data():
    """加载GPP响应数据"""
    print("="*80)
    print("加载GPP响应数据")
    print("="*80 + "\n")
    
    with nc.Dataset(GPP_RESPONSE_FILE, 'r') as ds:
        lats = ds.variables['lat'][:]
        lons = ds.variables['lon'][:]
        event_ids = ds.variables['event_id'][:]
        onset_years = ds.variables['onset_year'][:]
        onset_doys = ds.variables['onset_doy'][:]
        response_detected = ds.variables['response_detected'][:]
        gpp_min = ds.variables['gpp_min'][:]
        
    print(f"总事件数: {len(lats):,}")
    print(f"有GPP响应事件数: {np.sum(response_detected == 1):,}")
    print(f"无GPP响应事件数: {np.sum(response_detected == 0):,}")
    print(f"响应率: {np.sum(response_detected == 1) / len(lats) * 100:.2f}%\n")
    
    return {
        'lats': lats,
        'lons': lons,
        'event_ids': event_ids,
        'onset_years': onset_years,
        'onset_doys': onset_doys,
        'response_detected': response_detected,
        'gpp_min': gpp_min
    }

def load_drought_details():
    """加载骤旱事件详细信息（不立即读取大数组，保持文件句柄）"""
    print("="*80)
    print("加载骤旱事件详细信息")
    print("="*80 + "\n")
    
    ds = nc.Dataset(DROUGHT_DETAILS_FILE, 'r')
    
    detail_lats = ds.variables['lat'][:]
    detail_lons = ds.variables['lon'][:]
    event_count = ds.variables['event_count'][:]
    
    # 保存变量引用而不是立即读取所有数据
    drought_days_var = ds.variables['drought_days']
    intensity_var = ds.variables['intensity']
    onset_days_var = ds.variables['onset_days']
    onset_drop_var = ds.variables['onset_drop']
    onset_rate_var = ds.variables['onset_rate']
    
    fill_value_days = drought_days_var._FillValue
    fill_value_intensity = intensity_var._FillValue
    
    print(f"数据维度: {drought_days_var.shape}")
    print(f"网格尺寸: {len(detail_lats)} × {len(detail_lons)}")
    print(f"最大事件数/像元: {drought_days_var.shape[0]}\n")
    
    return {
        'dataset': ds,  # 保持文件打开
        'lats': detail_lats,
        'lons': detail_lons,
        'event_count': event_count,
        'drought_days': drought_days_var,
        'intensity': intensity_var,
        'onset_days': onset_days_var,
        'onset_drop': onset_drop_var,
        'onset_rate': onset_rate_var,
        'fill_value_days': fill_value_days,
        'fill_value_intensity': fill_value_intensity
    }

def match_events_to_drought_details(gpp_data, drought_data):
    """
    将GPP响应事件匹配到骤旱详情数据（向量化版本）
    返回每个事件的强度和持续时间
    """
    print("="*80)
    print("匹配事件到骤旱详情数据（向量化处理）")
    print("="*80 + "\n")
    
    lats_gpp = gpp_data['lats']
    lons_gpp = gpp_data['lons']
    event_ids_gpp = gpp_data['event_ids']
    
    detail_lats = drought_data['lats']
    detail_lons = drought_data['lons']
    drought_days = drought_data['drought_days']
    intensity = drought_data['intensity']
    onset_days = drought_data['onset_days']
    onset_drop = drought_data['onset_drop']
    onset_rate = drought_data['onset_rate']
    
    print("构建索引...")
    # 四舍五入到网格点
    lats_rounded = np.round(lats_gpp * 10) / 10
    lons_rounded = np.round(lons_gpp * 10) / 10
    
    # 计算索引（向量化）
    # 纬度范围从89.95到-89.95，步长-0.1
    lat_indices = ((89.95 - lats_rounded) / 0.1).astype(int)
    # 经度范围从-179.95到179.95，步长0.1
    lon_indices = ((lons_rounded + 179.95) / 0.1).astype(int)
    
    # 确保索引在有效范围内
    valid_mask = (~np.isnan(lats_gpp) & ~np.isnan(lons_gpp) &
                  (lat_indices >= 0) & (lat_indices < len(detail_lats)) &
                  (lon_indices >= 0) & (lon_indices < len(detail_lons)) &
                  (event_ids_gpp >= 0) & (event_ids_gpp < drought_days.shape[0]))
    
    print(f"有效事件数: {np.sum(valid_mask):,} / {len(lats_gpp):,}")
    
    # 准备输出数组
    n_events = len(lats_gpp)
    matched_duration = np.full(n_events, np.nan, dtype=np.float32)
    matched_intensity = np.full(n_events, np.nan, dtype=np.float32)
    matched_onset_days = np.full(n_events, np.nan, dtype=np.float32)
    matched_onset_drop = np.full(n_events, np.nan, dtype=np.float32)
    matched_onset_rate = np.full(n_events, np.nan, dtype=np.float32)
    
    # 准备索引数组
    valid_indices = np.where(valid_mask)[0]
    event_indices = event_ids_gpp[valid_indices].astype(int)
    lat_idx = lat_indices[valid_indices]
    lon_idx = lon_indices[valid_indices]
    
    print("提取数据（分批处理）...")
    # 分批处理避免内存溢出
    batch_size = 1000000
    n_batches = (len(valid_indices) + batch_size - 1) // batch_size
    
    for batch_idx in range(n_batches):
        start_idx = batch_idx * batch_size
        end_idx = min((batch_idx + 1) * batch_size, len(valid_indices))
        
        print(f"  批次 {batch_idx+1}/{n_batches}: 处理 {start_idx:,} - {end_idx:,}")
        
        batch_valid_indices = valid_indices[start_idx:end_idx]
        batch_event_indices = event_indices[start_idx:end_idx]
        batch_lat_idx = lat_idx[start_idx:end_idx]
        batch_lon_idx = lon_idx[start_idx:end_idx]
        
        # 逐个读取数据（避免使用高级索引导致内存问题）
        batch_duration = np.empty(len(batch_event_indices), dtype=np.float32)
        batch_intensity = np.empty(len(batch_event_indices), dtype=np.float32)
        batch_onset_days = np.empty(len(batch_event_indices), dtype=np.float32)
        batch_onset_drop = np.empty(len(batch_event_indices), dtype=np.float32)
        batch_onset_rate = np.empty(len(batch_event_indices), dtype=np.float32)
        
        for i in range(len(batch_event_indices)):
            if i % 100000 == 0 and i > 0:
                print(f"    进度: {i}/{len(batch_event_indices)}")
            
            e_idx = batch_event_indices[i]
            li = batch_lat_idx[i]
            lo = batch_lon_idx[i]
            
            batch_duration[i] = drought_days[e_idx, li, lo]
            batch_intensity[i] = intensity[e_idx, li, lo]
            batch_onset_days[i] = onset_days[e_idx, li, lo]
            batch_onset_drop[i] = onset_drop[e_idx, li, lo]
            batch_onset_rate[i] = onset_rate[e_idx, li, lo]
        
        # 创建有效数据掩膜
        valid_data_mask = ((batch_duration != drought_data['fill_value_days']) & 
                           (batch_duration > 0) &
                           (batch_intensity != drought_data['fill_value_intensity']) & 
                           (~np.isnan(batch_intensity)))
        
        # 赋值有效数据
        matched_duration[batch_valid_indices[valid_data_mask]] = batch_duration[valid_data_mask]
        matched_intensity[batch_valid_indices[valid_data_mask]] = batch_intensity[valid_data_mask]
        
        # 处理发生期数据
        onset_days_valid_mask = ((batch_onset_days != drought_data['fill_value_days']) & 
                                (batch_onset_days > 0))
        matched_onset_days[batch_valid_indices[onset_days_valid_mask]] = batch_onset_days[onset_days_valid_mask]
        
        onset_drop_valid_mask = ((batch_onset_drop != drought_data['fill_value_intensity']) & 
                                (~np.isnan(batch_onset_drop)))
        matched_onset_drop[batch_valid_indices[onset_drop_valid_mask]] = batch_onset_drop[onset_drop_valid_mask]
        
        onset_rate_valid_mask = ((batch_onset_rate != drought_data['fill_value_intensity']) & 
                                (~np.isnan(batch_onset_rate)))
        matched_onset_rate[batch_valid_indices[onset_rate_valid_mask]] = batch_onset_rate[onset_rate_valid_mask]
    
    matched_count = np.sum(~np.isnan(matched_duration))
    unmatched_count = n_events - matched_count
    
    print(f"\n匹配完成:")
    print(f"  成功匹配: {matched_count:,} ({matched_count/n_events*100:.2f}%)")
    print(f"  未匹配: {unmatched_count:,} ({unmatched_count/n_events*100:.2f}%)\n")
    
    return {
        'duration': matched_duration,
        'intensity': matched_intensity,
        'onset_days': matched_onset_days,
        'onset_drop': matched_onset_drop,
        'onset_rate': matched_onset_rate
    }

def compare_response_vs_non_response(gpp_data, matched_data):
    """对比有响应和无响应事件的差异"""
    print("="*80)
    print("对比分析：GPP响应 vs 未响应")
    print("="*80 + "\n")
    
    response_mask = gpp_data['response_detected'] == 1
    non_response_mask = gpp_data['response_detected'] == 0
    
    # 提取有效数据
    # 有响应的事件
    resp_duration = matched_data['duration'][response_mask]
    resp_intensity = matched_data['intensity'][response_mask]
    resp_onset_days = matched_data['onset_days'][response_mask]
    resp_onset_drop = matched_data['onset_drop'][response_mask]
    resp_onset_rate = matched_data['onset_rate'][response_mask]
    
    # 移除NaN
    resp_duration_valid = resp_duration[~np.isnan(resp_duration)]
    resp_intensity_valid = resp_intensity[~np.isnan(resp_intensity)]
    resp_onset_days_valid = resp_onset_days[~np.isnan(resp_onset_days)]
    resp_onset_drop_valid = resp_onset_drop[~np.isnan(resp_onset_drop)]
    resp_onset_rate_valid = resp_onset_rate[~np.isnan(resp_onset_rate)]
    
    # 无响应的事件
    non_resp_duration = matched_data['duration'][non_response_mask]
    non_resp_intensity = matched_data['intensity'][non_response_mask]
    non_resp_onset_days = matched_data['onset_days'][non_response_mask]
    non_resp_onset_drop = matched_data['onset_drop'][non_response_mask]
    non_resp_onset_rate = matched_data['onset_rate'][non_response_mask]
    
    # 移除NaN
    non_resp_duration_valid = non_resp_duration[~np.isnan(non_resp_duration)]
    non_resp_intensity_valid = non_resp_intensity[~np.isnan(non_resp_intensity)]
    non_resp_onset_days_valid = non_resp_onset_days[~np.isnan(non_resp_onset_days)]
    non_resp_onset_drop_valid = non_resp_onset_drop[~np.isnan(non_resp_onset_drop)]
    non_resp_onset_rate_valid = non_resp_onset_rate[~np.isnan(non_resp_onset_rate)]
    
    # 检查是否有有效数据
    if len(resp_duration_valid) == 0 or len(non_resp_duration_valid) == 0:
        print("错误：没有足够的有效数据进行对比分析")
        print(f"  有响应事件: {len(resp_duration_valid):,}")
        print(f"  无响应事件: {len(non_resp_duration_valid):,}")
        return None
    
    print("有GPP响应的骤旱事件:")
    print(f"  有效事件数: {len(resp_duration_valid):,}")
    print(f"  平均持续时间: {np.mean(resp_duration_valid):.2f} ± {np.std(resp_duration_valid):.2f} 天")
    print(f"  持续时间范围: {np.min(resp_duration_valid):.2f} - {np.max(resp_duration_valid):.2f} 天")
    print(f"  中位数持续时间: {np.median(resp_duration_valid):.2f} 天")
    print(f"  平均强度: {np.mean(resp_intensity_valid):.4f} ± {np.std(resp_intensity_valid):.4f}")
    print(f"  强度范围: {np.min(resp_intensity_valid):.4f} - {np.max(resp_intensity_valid):.4f}")
    print(f"  中位数强度: {np.median(resp_intensity_valid):.4f}")
    print(f"  平均发生期: {np.mean(resp_onset_days_valid):.2f} ± {np.std(resp_onset_days_valid):.2f} 天")
    print(f"  平均发生降幅: {np.mean(resp_onset_drop_valid):.4f} ± {np.std(resp_onset_drop_valid):.4f}")
    print(f"  平均发生速率: {np.mean(resp_onset_rate_valid):.6f} ± {np.std(resp_onset_rate_valid):.6f}")
    
    print("\n无GPP响应的骤旱事件:")
    print(f"  有效事件数: {len(non_resp_duration_valid):,}")
    print(f"  平均持续时间: {np.mean(non_resp_duration_valid):.2f} ± {np.std(non_resp_duration_valid):.2f} 天")
    print(f"  持续时间范围: {np.min(non_resp_duration_valid):.2f} - {np.max(non_resp_duration_valid):.2f} 天")
    print(f"  中位数持续时间: {np.median(non_resp_duration_valid):.2f} 天")
    print(f"  平均强度: {np.mean(non_resp_intensity_valid):.4f} ± {np.std(non_resp_intensity_valid):.4f}")
    print(f"  强度范围: {np.min(non_resp_intensity_valid):.4f} - {np.max(non_resp_intensity_valid):.4f}")
    print(f"  中位数强度: {np.median(non_resp_intensity_valid):.4f}")
    print(f"  平均发生期: {np.mean(non_resp_onset_days_valid):.2f} ± {np.std(non_resp_onset_days_valid):.2f} 天")
    print(f"  平均发生降幅: {np.mean(non_resp_onset_drop_valid):.4f} ± {np.std(non_resp_onset_drop_valid):.4f}")
    print(f"  平均发生速率: {np.mean(non_resp_onset_rate_valid):.6f} ± {np.std(non_resp_onset_rate_valid):.6f}")
    
    # 计算差异
    print("\n差异分析:")
    duration_diff = np.mean(resp_duration_valid) - np.mean(non_resp_duration_valid)
    duration_diff_pct = duration_diff / np.mean(non_resp_duration_valid) * 100
    print(f"  持续时间差异: {duration_diff:+.2f} 天 ({duration_diff_pct:+.1f}%)")
    
    intensity_diff = np.mean(resp_intensity_valid) - np.mean(non_resp_intensity_valid)
    intensity_diff_pct = intensity_diff / np.mean(non_resp_intensity_valid) * 100
    print(f"  强度差异: {intensity_diff:+.4f} ({intensity_diff_pct:+.1f}%)")
    
    onset_days_diff = np.mean(resp_onset_days_valid) - np.mean(non_resp_onset_days_valid)
    onset_days_diff_pct = onset_days_diff / np.mean(non_resp_onset_days_valid) * 100
    print(f"  发生期差异: {onset_days_diff:+.2f} 天 ({onset_days_diff_pct:+.1f}%)")
    
    onset_drop_diff = np.mean(resp_onset_drop_valid) - np.mean(non_resp_onset_drop_valid)
    onset_drop_diff_pct = onset_drop_diff / np.mean(non_resp_onset_drop_valid) * 100
    print(f"  发生降幅差异: {onset_drop_diff:+.4f} ({onset_drop_diff_pct:+.1f}%)")
    
    onset_rate_diff = np.mean(resp_onset_rate_valid) - np.mean(non_resp_onset_rate_valid)
    onset_rate_diff_pct = onset_rate_diff / np.mean(non_resp_onset_rate_valid) * 100
    print(f"  发生速率差异: {onset_rate_diff:+.6f} ({onset_rate_diff_pct:+.1f}%)")
    
    return {
        'response': {
            'count': len(resp_duration_valid),
            'duration_mean': np.mean(resp_duration_valid),
            'duration_std': np.std(resp_duration_valid),
            'duration_median': np.median(resp_duration_valid),
            'duration_min': np.min(resp_duration_valid),
            'duration_max': np.max(resp_duration_valid),
            'intensity_mean': np.mean(resp_intensity_valid),
            'intensity_std': np.std(resp_intensity_valid),
            'intensity_median': np.median(resp_intensity_valid),
            'intensity_min': np.min(resp_intensity_valid),
            'intensity_max': np.max(resp_intensity_valid),
            'onset_days_mean': np.mean(resp_onset_days_valid),
            'onset_days_std': np.std(resp_onset_days_valid),
            'onset_drop_mean': np.mean(resp_onset_drop_valid),
            'onset_drop_std': np.std(resp_onset_drop_valid),
            'onset_rate_mean': np.mean(resp_onset_rate_valid),
            'onset_rate_std': np.std(resp_onset_rate_valid),
        },
        'non_response': {
            'count': len(non_resp_duration_valid),
            'duration_mean': np.mean(non_resp_duration_valid),
            'duration_std': np.std(non_resp_duration_valid),
            'duration_median': np.median(non_resp_duration_valid),
            'duration_min': np.min(non_resp_duration_valid),
            'duration_max': np.max(non_resp_duration_valid),
            'intensity_mean': np.mean(non_resp_intensity_valid),
            'intensity_std': np.std(non_resp_intensity_valid),
            'intensity_median': np.median(non_resp_intensity_valid),
            'intensity_min': np.min(non_resp_intensity_valid),
            'intensity_max': np.max(non_resp_intensity_valid),
            'onset_days_mean': np.mean(non_resp_onset_days_valid),
            'onset_days_std': np.std(non_resp_onset_days_valid),
            'onset_drop_mean': np.mean(non_resp_onset_drop_valid),
            'onset_drop_std': np.std(non_resp_onset_drop_valid),
            'onset_rate_mean': np.mean(non_resp_onset_rate_valid),
            'onset_rate_std': np.std(non_resp_onset_rate_valid),
        },
        'difference': {
            'duration_abs': duration_diff,
            'duration_pct': duration_diff_pct,
            'intensity_abs': intensity_diff,
            'intensity_pct': intensity_diff_pct,
            'onset_days_abs': onset_days_diff,
            'onset_days_pct': onset_days_diff_pct,
            'onset_drop_abs': onset_drop_diff,
            'onset_drop_pct': onset_drop_diff_pct,
            'onset_rate_abs': onset_rate_diff,
            'onset_rate_pct': onset_rate_diff_pct,
        }
    }

def load_land_use_data():
    """加载土地利用数据"""
    print("\n" + "="*80)
    print("加载土地利用数据")
    print("="*80 + "\n")
    
    ds = gdal.Open(LC_FILE)
    band = ds.GetRasterBand(1)
    lc_data = band.ReadAsArray()
    gt = ds.GetGeoTransform()
    projection = ds.GetProjection()
    ds = None
    
    print(f"土地利用数据维度: {lc_data.shape}")
    return lc_data, gt, projection

def analyze_by_land_use(gpp_data, matched_data, lc_data, lc_gt):
    """按土地利用类型分析响应与未响应的差异"""
    print("\n" + "="*80)
    print("按土地利用类型分析")
    print("="*80 + "\n")
    
    lats = gpp_data['lats']
    lons = gpp_data['lons']
    response_detected = gpp_data['response_detected']
    
    # 映射到土地利用数据
    origin_x = lc_gt[0]
    origin_y = lc_gt[3]
    pixel_width = lc_gt[1]
    pixel_height = lc_gt[5]
    
    cols = ((lons - origin_x) / pixel_width).astype(int)
    rows = ((lats - origin_y) / pixel_height).astype(int)
    
    rows = np.clip(rows, 0, lc_data.shape[0] - 1)
    cols = np.clip(cols, 0, lc_data.shape[1] - 1)
    
    # 获取土地类型
    valid_coords = ~np.isnan(lats) & ~np.isnan(lons)
    lc_classes = np.full(len(lats), -1, dtype=np.int16)
    lc_classes[valid_coords] = lc_data[rows[valid_coords], cols[valid_coords]]
    
    # 按类型统计
    lc_stats = []
    
    for class_id in range(1, 13):
        class_name = IGBP_CLASSES[class_id]
        class_mask = (lc_classes == class_id)
        
        # 有响应的
        resp_mask = class_mask & (response_detected == 1)
        resp_duration = matched_data['duration'][resp_mask]
        resp_intensity = matched_data['intensity'][resp_mask]
        
        resp_duration_valid = resp_duration[~np.isnan(resp_duration)]
        resp_intensity_valid = resp_intensity[~np.isnan(resp_intensity)]
        
        # 无响应的
        non_resp_mask = class_mask & (response_detected == 0)
        non_resp_duration = matched_data['duration'][non_resp_mask]
        non_resp_intensity = matched_data['intensity'][non_resp_mask]
        
        non_resp_duration_valid = non_resp_duration[~np.isnan(non_resp_duration)]
        non_resp_intensity_valid = non_resp_intensity[~np.isnan(non_resp_intensity)]
        
        if len(resp_duration_valid) == 0 and len(non_resp_duration_valid) == 0:
            print(f"  Class {class_id:2d} ({class_name}): 无有效数据")
            continue
        
        # 计算响应率
        total_class_events = len(resp_duration_valid) + len(non_resp_duration_valid)
        response_rate = len(resp_duration_valid) / total_class_events * 100 if total_class_events > 0 else 0
        
        print(f"  Class {class_id:2d} ({class_name}):")
        print(f"    响应率: {response_rate:.1f}% ({len(resp_duration_valid):,}/{total_class_events:,})")
        
        if len(resp_duration_valid) > 0:
            print(f"    有响应 - 持续: {np.mean(resp_duration_valid):.2f}天, 强度: {np.mean(resp_intensity_valid):.4f}")
        if len(non_resp_duration_valid) > 0:
            print(f"    无响应 - 持续: {np.mean(non_resp_duration_valid):.2f}天, 强度: {np.mean(non_resp_intensity_valid):.4f}")
        
        stats = {
            'Class_ID': class_id,
            'Class_Name': class_name,
            'Total_Events': total_class_events,
            'Response_Events': len(resp_duration_valid),
            'Non_Response_Events': len(non_resp_duration_valid),
            'Response_Rate': response_rate,
            'Response_Duration_Mean': np.mean(resp_duration_valid) if len(resp_duration_valid) > 0 else np.nan,
            'Response_Duration_Std': np.std(resp_duration_valid) if len(resp_duration_valid) > 0 else np.nan,
            'Response_Intensity_Mean': np.mean(resp_intensity_valid) if len(resp_intensity_valid) > 0 else np.nan,
            'Response_Intensity_Std': np.std(resp_intensity_valid) if len(resp_intensity_valid) > 0 else np.nan,
            'NonResponse_Duration_Mean': np.mean(non_resp_duration_valid) if len(non_resp_duration_valid) > 0 else np.nan,
            'NonResponse_Duration_Std': np.std(non_resp_duration_valid) if len(non_resp_duration_valid) > 0 else np.nan,
            'NonResponse_Intensity_Mean': np.mean(non_resp_intensity_valid) if len(non_resp_intensity_valid) > 0 else np.nan,
            'NonResponse_Intensity_Std': np.std(non_resp_intensity_valid) if len(non_resp_intensity_valid) > 0 else np.nan,
        }
        
        # 计算差异
        if len(resp_duration_valid) > 0 and len(non_resp_duration_valid) > 0:
            stats['Duration_Difference'] = np.mean(resp_duration_valid) - np.mean(non_resp_duration_valid)
            stats['Duration_Difference_Pct'] = stats['Duration_Difference'] / np.mean(non_resp_duration_valid) * 100
            stats['Intensity_Difference'] = np.mean(resp_intensity_valid) - np.mean(non_resp_intensity_valid)
            stats['Intensity_Difference_Pct'] = stats['Intensity_Difference'] / np.mean(non_resp_intensity_valid) * 100
        else:
            stats['Duration_Difference'] = np.nan
            stats['Duration_Difference_Pct'] = np.nan
            stats['Intensity_Difference'] = np.nan
            stats['Intensity_Difference_Pct'] = np.nan
        
        lc_stats.append(stats)
    
    return pd.DataFrame(lc_stats)

def create_spatial_maps(gpp_data, matched_data, drought_data, projection):
    """创建空间分布地图"""
    print("\n" + "="*80)
    print("创建空间分布地图")
    print("="*80 + "\n")
    
    detail_lats = drought_data['lats']
    detail_lons = drought_data['lons']
    
    # 创建网格
    n_lat = len(detail_lats)
    n_lon = len(detail_lons)
    
    # 初始化数组
    resp_duration_grid = np.full((n_lat, n_lon), np.nan, dtype=np.float32)
    resp_intensity_grid = np.full((n_lat, n_lon), np.nan, dtype=np.float32)
    non_resp_duration_grid = np.full((n_lat, n_lon), np.nan, dtype=np.float32)
    non_resp_intensity_grid = np.full((n_lat, n_lon), np.nan, dtype=np.float32)
    response_rate_grid = np.full((n_lat, n_lon), np.nan, dtype=np.float32)
    
    # 创建经纬度到索引的映射
    lat_to_idx = {lat: i for i, lat in enumerate(detail_lats)}
    lon_to_idx = {lon: j for j, lon in enumerate(detail_lons)}
    
    print("按像元聚合数据...")
    
    # 遍历每个像元
    for i, lat in enumerate(detail_lats):
        if i % 200 == 0:
            print(f"  进度: {i}/{n_lat} ({i/n_lat*100:.1f}%)")
        
        for j, lon in enumerate(detail_lons):
            # 找到该像元的所有事件
            pixel_mask = (np.abs(gpp_data['lats'] - lat) < 0.05) & (np.abs(gpp_data['lons'] - lon) < 0.05)
            
            if not np.any(pixel_mask):
                continue
            
            # 有响应的事件
            resp_mask = pixel_mask & (gpp_data['response_detected'] == 1)
            resp_dur = matched_data['duration'][resp_mask]
            resp_int = matched_data['intensity'][resp_mask]
            
            resp_dur_valid = resp_dur[~np.isnan(resp_dur)]
            resp_int_valid = resp_int[~np.isnan(resp_int)]
            
            if len(resp_dur_valid) > 0:
                resp_duration_grid[i, j] = np.mean(resp_dur_valid)
                resp_intensity_grid[i, j] = np.mean(resp_int_valid)
            
            # 无响应的事件
            non_resp_mask = pixel_mask & (gpp_data['response_detected'] == 0)
            non_resp_dur = matched_data['duration'][non_resp_mask]
            non_resp_int = matched_data['intensity'][non_resp_mask]
            
            non_resp_dur_valid = non_resp_dur[~np.isnan(non_resp_dur)]
            non_resp_int_valid = non_resp_int[~np.isnan(non_resp_int)]
            
            if len(non_resp_dur_valid) > 0:
                non_resp_duration_grid[i, j] = np.mean(non_resp_dur_valid)
                non_resp_intensity_grid[i, j] = np.mean(non_resp_int_valid)
            
            # 响应率
            total_events = len(resp_dur_valid) + len(non_resp_dur_valid)
            if total_events > 0:
                response_rate_grid[i, j] = len(resp_dur_valid) / total_events * 100
    
    # 保存为GeoTIFF
    def save_tif(data, filename):
        driver = gdal.GetDriverByName('GTiff')
        rows, cols = data.shape
        
        lon_res = (detail_lons[-1] - detail_lons[0]) / (len(detail_lons) - 1)
        lat_res = (detail_lats[-1] - detail_lats[0]) / (len(detail_lats) - 1)
        geo_transform = (detail_lons[0] - lon_res/2, lon_res, 0,
                        detail_lats[0] - lat_res/2, 0, lat_res)
        
        output_path = os.path.join(OUTPUT_DIR, filename)
        out_ds = driver.Create(output_path, cols, rows, 1, gdal.GDT_Float32,
                              options=['COMPRESS=LZW'])
        out_ds.SetGeoTransform(geo_transform)
        out_ds.SetProjection(projection)
        
        band = out_ds.GetRasterBand(1)
        band.SetNoDataValue(-9999)
        
        data_copy = data.copy()
        data_copy[np.isnan(data_copy)] = -9999
        
        band.WriteArray(data_copy)
        band.FlushCache()
        out_ds = None
        
        print(f"  已保存: {filename}")
    
    save_tif(resp_duration_grid, 'response_mean_duration.tif')
    save_tif(resp_intensity_grid, 'response_mean_intensity.tif')
    save_tif(non_resp_duration_grid, 'non_response_mean_duration.tif')
    save_tif(non_resp_intensity_grid, 'non_response_mean_intensity.tif')
    save_tif(response_rate_grid, 'response_rate_spatial.tif')

def create_markdown_report(comparison_stats, lc_stats):
    """创建Markdown分析报告"""
    output_path = os.path.join(OUTPUT_DIR, 'gpp_response_comparison_report.md')
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# GPP响应与未响应骤旱事件对比分析报告\n\n")
        f.write(f"**分析日期**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        
        # 总体统计
        f.write("## 1. 总体统计对比\n\n")
        
        f.write("### 1.1 事件数量\n\n")
        f.write("| 类别 | 事件数 |\n")
        f.write("|------|-------|\n")
        f.write(f"| 有GPP响应 | {comparison_stats['response']['count']:,} |\n")
        f.write(f"| 无GPP响应 | {comparison_stats['non_response']['count']:,} |\n")
        f.write(f"| 总计 | {comparison_stats['response']['count'] + comparison_stats['non_response']['count']:,} |\n")
        f.write(f"| 响应率 | {comparison_stats['response']['count'] / (comparison_stats['response']['count'] + comparison_stats['non_response']['count']) * 100:.2f}% |\n\n")
        
        f.write("### 1.2 持续时间对比\n\n")
        f.write("| 指标 | 有响应 | 无响应 | 差异 |\n")
        f.write("|------|--------|--------|------|\n")
        f.write(f"| 平均值 (天) | {comparison_stats['response']['duration_mean']:.2f} ± {comparison_stats['response']['duration_std']:.2f} | "
                f"{comparison_stats['non_response']['duration_mean']:.2f} ± {comparison_stats['non_response']['duration_std']:.2f} | "
                f"{comparison_stats['difference']['duration_abs']:+.2f} ({comparison_stats['difference']['duration_pct']:+.1f}%) |\n")
        f.write(f"| 中位数 (天) | {comparison_stats['response']['duration_median']:.2f} | "
                f"{comparison_stats['non_response']['duration_median']:.2f} | "
                f"{comparison_stats['response']['duration_median'] - comparison_stats['non_response']['duration_median']:+.2f} |\n")
        f.write(f"| 范围 (天) | {comparison_stats['response']['duration_min']:.0f} - {comparison_stats['response']['duration_max']:.0f} | "
                f"{comparison_stats['non_response']['duration_min']:.0f} - {comparison_stats['non_response']['duration_max']:.0f} | - |\n\n")
        
        f.write("### 1.3 强度对比\n\n")
        f.write("| 指标 | 有响应 | 无响应 | 差异 |\n")
        f.write("|------|--------|--------|------|\n")
        f.write(f"| 平均值 | {comparison_stats['response']['intensity_mean']:.4f} ± {comparison_stats['response']['intensity_std']:.4f} | "
                f"{comparison_stats['non_response']['intensity_mean']:.4f} ± {comparison_stats['non_response']['intensity_std']:.4f} | "
                f"{comparison_stats['difference']['intensity_abs']:+.4f} ({comparison_stats['difference']['intensity_pct']:+.1f}%) |\n")
        f.write(f"| 中位数 | {comparison_stats['response']['intensity_median']:.4f} | "
                f"{comparison_stats['non_response']['intensity_median']:.4f} | "
                f"{comparison_stats['response']['intensity_median'] - comparison_stats['non_response']['intensity_median']:+.4f} |\n")
        f.write(f"| 范围 | {comparison_stats['response']['intensity_min']:.4f} - {comparison_stats['response']['intensity_max']:.4f} | "
                f"{comparison_stats['non_response']['intensity_min']:.4f} - {comparison_stats['non_response']['intensity_max']:.4f} | - |\n\n")
        
        f.write("### 1.4 发生期特征对比\n\n")
        f.write("| 指标 | 有响应 | 无响应 | 差异 |\n")
        f.write("|------|--------|--------|------|\n")
        f.write(f"| 平均发生期 (天) | {comparison_stats['response']['onset_days_mean']:.2f} ± {comparison_stats['response']['onset_days_std']:.2f} | "
                f"{comparison_stats['non_response']['onset_days_mean']:.2f} ± {comparison_stats['non_response']['onset_days_std']:.2f} | "
                f"{comparison_stats['difference']['onset_days_abs']:+.2f} ({comparison_stats['difference']['onset_days_pct']:+.1f}%) |\n")
        f.write(f"| 平均发生降幅 | {comparison_stats['response']['onset_drop_mean']:.4f} ± {comparison_stats['response']['onset_drop_std']:.4f} | "
                f"{comparison_stats['non_response']['onset_drop_mean']:.4f} ± {comparison_stats['non_response']['onset_drop_std']:.4f} | "
                f"{comparison_stats['difference']['onset_drop_abs']:+.4f} ({comparison_stats['difference']['onset_drop_pct']:+.1f}%) |\n")
        f.write(f"| 平均发生速率 | {comparison_stats['response']['onset_rate_mean']:.6f} ± {comparison_stats['response']['onset_rate_std']:.6f} | "
                f"{comparison_stats['non_response']['onset_rate_mean']:.6f} ± {comparison_stats['non_response']['onset_rate_std']:.6f} | "
                f"{comparison_stats['difference']['onset_rate_abs']:+.6f} ({comparison_stats['difference']['onset_rate_pct']:+.1f}%) |\n\n")
        
        # 土地利用类型分析
        f.write("---\n\n")
        f.write("## 2. 不同土地利用类型的响应差异\n\n")
        
        f.write("### 2.1 响应率排序\n\n")
        lc_sorted_by_rate = lc_stats.sort_values('Response_Rate', ascending=False)
        f.write("| 排名 | 土地类型 | 响应率 | 有响应事件数 | 无响应事件数 |\n")
        f.write("|------|---------|--------|-------------|-------------|\n")
        for idx, (_, row) in enumerate(lc_sorted_by_rate.iterrows(), 1):
            f.write(f"| {idx} | {row['Class_Name']} | {row['Response_Rate']:.1f}% | "
                   f"{row['Response_Events']:,} | {row['Non_Response_Events']:,} |\n")
        
        f.write("\n### 2.2 持续时间差异\n\n")
        f.write("| 土地类型 | 有响应持续时间 | 无响应持续时间 | 差异 |\n")
        f.write("|---------|----------------|---------------|------|\n")
        for _, row in lc_stats.iterrows():
            if not np.isnan(row['Response_Duration_Mean']) and not np.isnan(row['NonResponse_Duration_Mean']):
                f.write(f"| {row['Class_Name']} | {row['Response_Duration_Mean']:.2f} ± {row['Response_Duration_Std']:.2f} | "
                       f"{row['NonResponse_Duration_Mean']:.2f} ± {row['NonResponse_Duration_Std']:.2f} | "
                       f"{row['Duration_Difference']:+.2f} ({row['Duration_Difference_Pct']:+.1f}%) |\n")
        
        f.write("\n### 2.3 强度差异\n\n")
        f.write("| 土地类型 | 有响应强度 | 无响应强度 | 差异 |\n")
        f.write("|---------|-----------|-----------|------|\n")
        for _, row in lc_stats.iterrows():
            if not np.isnan(row['Response_Intensity_Mean']) and not np.isnan(row['NonResponse_Intensity_Mean']):
                f.write(f"| {row['Class_Name']} | {row['Response_Intensity_Mean']:.4f} ± {row['Response_Intensity_Std']:.4f} | "
                       f"{row['NonResponse_Intensity_Mean']:.4f} ± {row['NonResponse_Intensity_Std']:.4f} | "
                       f"{row['Intensity_Difference']:+.4f} ({row['Intensity_Difference_Pct']:+.1f}%) |\n")
        
        # 关键发现
        f.write("\n---\n\n")
        f.write("## 3. 关键发现\n\n")
        
        f.write("### 3.1 总体趋势\n\n")
        
        if comparison_stats['difference']['duration_pct'] > 0:
            f.write(f"- **有GPP响应的骤旱事件持续时间更长**：平均长 {comparison_stats['difference']['duration_abs']:.2f} 天 ({comparison_stats['difference']['duration_pct']:.1f}%)\n")
        else:
            f.write(f"- **无GPP响应的骤旱事件持续时间更长**：平均短 {-comparison_stats['difference']['duration_abs']:.2f} 天 ({-comparison_stats['difference']['duration_pct']:.1f}%)\n")
        
        if comparison_stats['difference']['intensity_pct'] > 0:
            f.write(f"- **有GPP响应的骤旱事件强度更大**：平均高 {comparison_stats['difference']['intensity_abs']:.4f} ({comparison_stats['difference']['intensity_pct']:.1f}%)\n")
        else:
            f.write(f"- **无GPP响应的骤旱事件强度更大**：平均低 {-comparison_stats['difference']['intensity_abs']:.4f} ({-comparison_stats['difference']['intensity_pct']:.1f}%)\n")
        
        if comparison_stats['difference']['onset_days_pct'] > 0:
            f.write(f"- **有GPP响应的事件发生期更长**：平均长 {comparison_stats['difference']['onset_days_abs']:.2f} 天 ({comparison_stats['difference']['onset_days_pct']:.1f}%)\n")
        else:
            f.write(f"- **无GPP响应的事件发生期更长**：平均短 {-comparison_stats['difference']['onset_days_abs']:.2f} 天 ({-comparison_stats['difference']['onset_days_pct']:.1f}%)\n")
        
        f.write("\n### 3.2 土地类型特征\n\n")
        
        top3_response = lc_sorted_by_rate.head(3)
        f.write("**响应率最高的土地类型**：\n\n")
        for _, row in top3_response.iterrows():
            f.write(f"- {row['Class_Name']}: {row['Response_Rate']:.1f}%\n")
        
        bottom3_response = lc_sorted_by_rate.tail(3)
        f.write("\n**响应率最低的土地类型**：\n\n")
        for _, row in bottom3_response.iterrows():
            f.write(f"- {row['Class_Name']}: {row['Response_Rate']:.1f}%\n")
        
        # 输出文件
        f.write("\n---\n\n")
        f.write("## 4. 输出文件\n\n")
        f.write("- `response_mean_duration.tif`: 有响应事件的平均持续时间空间分布\n")
        f.write("- `response_mean_intensity.tif`: 有响应事件的平均强度空间分布\n")
        f.write("- `non_response_mean_duration.tif`: 无响应事件的平均持续时间空间分布\n")
        f.write("- `non_response_mean_intensity.tif`: 无响应事件的平均强度空间分布\n")
        f.write("- `response_rate_spatial.tif`: 响应率空间分布\n")
        f.write("- `comparison_statistics.csv`: 总体统计对比\n")
        f.write("- `landuse_comparison_stats.csv`: 土地利用类型对比统计\n\n")
        
        f.write("---\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print(f"\n✓ 报告已保存: {output_path}")

def main():
    print("\n" + "="*80)
    print("GPP响应与未响应骤旱事件对比分析")
    print("="*80 + "\n")
    
    # 创建输出目录
    create_output_dir()
    
    # 加载数据
    gpp_data = load_gpp_response_data()
    drought_data = load_drought_details()
    
    # 匹配事件到骤旱详情
    matched_data = match_events_to_drought_details(gpp_data, drought_data)
    
    # 对比分析
    comparison_stats = compare_response_vs_non_response(gpp_data, matched_data)
    
    if comparison_stats is None:
        print("\n分析失败：无法获得有效的对比数据")
        return
    
    # 加载土地利用数据
    lc_data, lc_gt, projection = load_land_use_data()
    
    # 按土地利用类型分析
    lc_stats = analyze_by_land_use(gpp_data, matched_data, lc_data, lc_gt)
    
    # 创建空间地图
    create_spatial_maps(gpp_data, matched_data, drought_data, projection)
    
    # 保存统计结果
    print("\n" + "="*80)
    print("保存统计结果")
    print("="*80 + "\n")
    
    # 总体统计
    comparison_df = pd.DataFrame([
        {
            'Category': 'Response',
            **{f'{k}': v for k, v in comparison_stats['response'].items()}
        },
        {
            'Category': 'Non_Response',
            **{f'{k}': v for k, v in comparison_stats['non_response'].items()}
        },
        {
            'Category': 'Difference',
            **{f'{k}': v for k, v in comparison_stats['difference'].items()}
        }
    ])
    
    comparison_csv = os.path.join(OUTPUT_DIR, 'comparison_statistics.csv')
    comparison_df.to_csv(comparison_csv, index=False, encoding='utf-8-sig')
    print(f"✓ 已保存: {comparison_csv}")
    
    # 土地利用类型统计
    lc_csv = os.path.join(OUTPUT_DIR, 'landuse_comparison_stats.csv')
    lc_stats.to_csv(lc_csv, index=False, encoding='utf-8-sig')
    print(f"✓ 已保存: {lc_csv}")
    
    # 创建Markdown报告
    create_markdown_report(comparison_stats, lc_stats)
    
    print("\n" + "="*80)
    print("分析完成！")
    print("="*80)
    print(f"\n所有结果已保存到: {OUTPUT_DIR}")
    print("\n生成的文件:")
    print("  - 5个空间分布TIF文件")
    print("  - 2个统计CSV文件")
    print("  - 1个Markdown分析报告")
    print()
    
    # 关闭文件
    if 'dataset' in drought_data:
        drought_data['dataset'].close()

if __name__ == '__main__':
    main()
