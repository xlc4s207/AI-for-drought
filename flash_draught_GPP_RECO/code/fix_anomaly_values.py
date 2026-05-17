#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理土地利用分析地图中的异常值
将绝对值大于阈值的异常值替换为NaN
"""

import numpy as np
from osgeo import gdal, osr
import os
import glob
import shutil

# 配置
MAPS_DIR_SMRZ = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO/SMrz_GPP_results/land_use_analysis/maps'
MAPS_DIR_SMS = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO/SMs_GPP_results/land_use_analysis/maps'
BACKUP_SUFFIX = '.backup'
ANOMALY_THRESHOLD = 1e6  # 绝对值大于此值的视为异常

def backup_file(filepath):
    """备份原文件"""
    backup_path = filepath + BACKUP_SUFFIX
    if not os.path.exists(backup_path):
        shutil.copy2(filepath, backup_path)
        print(f"  已备份: {os.path.basename(backup_path)}")
    return backup_path

def fix_anomaly_in_tif(tif_path, threshold=ANOMALY_THRESHOLD):
    """
    修复TIF文件中的异常值
    
    Parameters:
    -----------
    tif_path : str
        TIF文件路径
    threshold : float
        异常值阈值（绝对值）
    
    Returns:
    --------
    dict : 修复统计信息
    """
    filename = os.path.basename(tif_path)
    
    # 读取数据
    ds = gdal.Open(tif_path, gdal.GA_ReadOnly)
    if ds is None:
        return {'error': 'Failed to open file'}
    
    band = ds.GetRasterBand(1)
    data = band.ReadAsArray()
    nodata = band.GetNoDataValue()
    
    # 获取地理信息
    geo_transform = ds.GetGeoTransform()
    projection = ds.GetProjection()
    
    ds = None  # 关闭文件
    
    # 统计异常值
    valid_mask = ~np.isnan(data)
    if nodata is not None:
        valid_mask &= (data != nodata)
    
    valid_data = data[valid_mask]
    
    if len(valid_data) == 0:
        return {'filename': filename, 'status': 'no_data', 'anomalies': 0}
    
    anomaly_mask = valid_mask & (np.abs(data) > threshold)
    anomaly_count = np.sum(anomaly_mask)
    
    if anomaly_count == 0:
        return {'filename': filename, 'status': 'clean', 'anomalies': 0}
    
    # 备份原文件
    backup_file(tif_path)
    
    # 替换异常值为NaN
    data_fixed = data.copy()
    data_fixed[anomaly_mask] = np.nan
    
    # 统计修复后的数据范围
    valid_fixed = data_fixed[~np.isnan(data_fixed)]
    if nodata is not None:
        valid_fixed = valid_fixed[valid_fixed != nodata]
    
    new_min = np.min(valid_fixed) if len(valid_fixed) > 0 else np.nan
    new_max = np.max(valid_fixed) if len(valid_fixed) > 0 else np.nan
    
    # 保存修复后的文件
    driver = gdal.GetDriverByName('GTiff')
    rows, cols = data.shape
    out_ds = driver.Create(tif_path, cols, rows, 1, gdal.GDT_Float32, 
                           options=['COMPRESS=LZW'])
    
    out_ds.SetGeoTransform(geo_transform)
    out_ds.SetProjection(projection)
    
    out_band = out_ds.GetRasterBand(1)
    out_band.SetNoDataValue(np.nan)
    out_band.WriteArray(data_fixed)
    out_band.FlushCache()
    
    out_ds = None
    
    return {
        'filename': filename,
        'status': 'fixed',
        'anomalies': anomaly_count,
        'total_valid': len(valid_data),
        'ratio': anomaly_count / len(valid_data) * 100,
        'new_min': new_min,
        'new_max': new_max
    }

def process_directory(maps_dir, pattern='*gpp_min_mean.tif'):
    """
    处理目录中的所有匹配文件
    
    Parameters:
    -----------
    maps_dir : str
        地图文件目录
    pattern : str
        文件匹配模式
    """
    print(f"\n{'='*80}")
    print(f"处理目录: {maps_dir}")
    print(f"匹配模式: {pattern}")
    print(f"{'='*80}\n")
    
    tif_files = sorted(glob.glob(os.path.join(maps_dir, pattern)))
    
    if len(tif_files) == 0:
        print("未找到匹配的文件")
        return
    
    print(f"找到 {len(tif_files)} 个文件\n")
    
    results = []
    
    for tif_file in tif_files:
        print(f"处理: {os.path.basename(tif_file)}")
        result = fix_anomaly_in_tif(tif_file)
        results.append(result)
        
        if result.get('status') == 'fixed':
            print(f"  ✓ 已修复 {result['anomalies']} 个异常值 "
                  f"({result['ratio']:.2f}%)")
            print(f"  新范围: [{result['new_min']:.2e}, {result['new_max']:.2e}]")
        elif result.get('status') == 'clean':
            print(f"  ✓ 无异常值，跳过")
        else:
            print(f"  ✗ 状态: {result.get('status', 'unknown')}")
        print()
    
    # 汇总统计
    print(f"\n{'='*80}")
    print("处理汇总:")
    print(f"{'='*80}")
    
    fixed_count = sum(1 for r in results if r.get('status') == 'fixed')
    clean_count = sum(1 for r in results if r.get('status') == 'clean')
    total_anomalies = sum(r.get('anomalies', 0) for r in results)
    
    print(f"总文件数: {len(results)}")
    print(f"  修复的文件: {fixed_count}")
    print(f"  干净的文件: {clean_count}")
    print(f"  总异常值数: {total_anomalies}")
    print()

def main():
    print("\n" + "="*80)
    print("土地利用分析地图 - 异常值清理工具")
    print("="*80)
    
    # 处理 SMrz_GPP 结果
    if os.path.exists(MAPS_DIR_SMRZ):
        process_directory(MAPS_DIR_SMRZ, '*gpp_min_mean.tif')
    
    # 处理 SMs_GPP 结果
    if os.path.exists(MAPS_DIR_SMS):
        process_directory(MAPS_DIR_SMS, '*gpp_min_mean.tif')
    
    print("\n" + "="*80)
    print("清理完成！")
    print("="*80)
    print("\n提示: 原文件已备份为 .backup 后缀")
    print("如需恢复，可使用以下命令:")
    print("  cd <maps目录>")
    print("  for f in *.backup; do mv \"$f\" \"${f%.backup}\"; done")
    print()

if __name__ == '__main__':
    main()
