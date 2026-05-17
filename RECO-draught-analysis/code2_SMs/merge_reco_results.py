#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RECO Analysis - Merger Script
=============================
手动合并 RECO 分析的临时分块结果。
用于在主程序被终止后，挽救已经生成的中间结果。
"""

import os
import numpy as np
import netCDF4 as nc
from datetime import datetime
from tqdm import tqdm
import shutil

# ================= 配置 =================
BASE_DIR = "/home/xulc/flash_drought"
OUTPUT_DIR = os.path.join(BASE_DIR, "process/RECO-draught-analysis/code2_SMs/results")
TEMP_DIR = os.path.join(OUTPUT_DIR, "temp_chunks_SMs")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'reco_response_SMs_drought_v10_global_merged.nc')

# 源文件路径（用于读取属性）
DROUGHT_EVENTS_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMs/flash_drought_SMs_events_details_v2.nc")
RECO_FILE = "/data/BESS_V2/RECO/BESS_RECO_1982_2022.nc"

# 结果字段定义 (必须与生成脚本一致)
RESULT_DTYPE = np.dtype([
    ('lat', 'f4'), ('lon', 'f4'), ('event_id', 'i2'), 
    ('onset_year', 'i2'), ('onset_doy', 'i2'),
    ('response_detected', 'i1'), ('reco_min', 'f4'), ('reco_mean', 'f4'),
    ('reco_trend', 'f4'), ('t_min', 'i2'), ('t_response', 'i2'),
    ('t_impact', 'i2'), ('amp_max', 'f4'), ('t_recover', 'f4'),
    ('recovery_rate', 'f4')
])

RESULT_FIELDS = list(RESULT_DTYPE.names)

def main():
    print("=" * 60)
    print("RECO Analysis Merger Script")
    print("=" * 60)
    print(f"临时目录: {TEMP_DIR}")
    
    if not os.path.exists(TEMP_DIR):
        print("错误: 临时目录不存在!")
        return

    # 1. 扫描文件
    temp_files = sorted([f for f in os.listdir(TEMP_DIR) if f.endswith('.npy')])
    print(f"发现 {len(temp_files)} 个分块文件")
    
    if len(temp_files) == 0:
        print("无文件可合并。")
        return
        
    # 2. 合并结果
    all_results = []
    total_events = 0
    
    print("正在加载临时文件...")
    for tf in tqdm(temp_files):
        try:
            data = np.load(os.path.join(TEMP_DIR, tf))
            if len(data) > 0:
                all_results.append(data)
                total_events += len(data)
        except Exception as e:
            print(f"加载 {tf} 失败: {e}")
            
    print(f"总加载事件数: {total_events}")
    
    if total_events == 0:
        print("无有效数据。")
        return
        
    merged = np.concatenate(all_results)
    print(f"合并后数组大小: {len(merged)}")
    
    # 3. 获取坐标信息 (用于 NetCDF)
    print("读取坐标信息...")
    with nc.Dataset(RECO_FILE, 'r') as ds:
        lat_arr = ds.variables['lat'][:]
        lon_arr = ds.variables['lon'][:]
        
    # 4. 保存结果
    print(f"保存结果至: {OUTPUT_FILE}")
    save_to_netcdf(merged, lat_arr, lon_arr, OUTPUT_FILE)
    
    print("\n合并成功完成!")
    # 注意：不自动删除临时文件，以防万一
    print(f"提示: 确认结果无误后，您可以手动删除目录: {TEMP_DIR}")

def save_to_netcdf(results, lat_arr, lon_arr, output_file):
    """保存结果到 NetCDF 文件"""
    
    with nc.Dataset(output_file, 'w', format='NETCDF4') as ds:
        # 创建维度
        ds.createDimension('event', len(results))
        ds.createDimension('lat', len(lat_arr))
        ds.createDimension('lon', len(lon_arr))
        
        # 坐标变量
        var_lat = ds.createVariable('lat_coord', 'f4', ('lat',))
        var_lat[:] = lat_arr
        var_lat.units = 'degrees_north'
        
        var_lon = ds.createVariable('lon_coord', 'f4', ('lon',))
        var_lon[:] = lon_arr
        var_lon.units = 'degrees_east'
        
        # 事件属性变量
        for field in RESULT_FIELDS:
            # 确定填充值
            dtype_np = results.dtype[field]
            if 'f' in str(dtype_np):
                fill_val = np.nan
            else:
                fill_val = -1 if 'i' in str(dtype_np) else None
            
            var = ds.createVariable(field, dtype_np, ('event',), fill_value=fill_val)
            var[:] = results[field]
        
        # 添加属性说明
        ds.variables['response_detected'].long_name = 'RECO response detected (1=yes, 0=no)'
        ds.variables['reco_min'].long_name = 'Minimum RECO z-score during response period'
        ds.variables['reco_mean'].long_name = 'Mean RECO z-score during response period'
        ds.variables['reco_trend'].long_name = 'RECO z-score trend (slope) during response period'
        ds.variables['t_min'].long_name = 'Days to minimum RECO from drought onset'
        ds.variables['t_response'].long_name = 'Days to first response detection from drought onset'
        ds.variables['t_response'].comment = '-1 means no response detected within search window'
        ds.variables['t_impact'].long_name = 'Days from response detection to minimum'
        ds.variables['t_recover'].long_name = 'Days from minimum to recovery'
        ds.variables['recovery_rate'].long_name = 'Rate of recovery (z-score per day)'
        
        # 全局属性
        ds.title = 'RECO Response to SMs Flash Drought Events - Global Analysis (Merged Partial)'
        ds.source_drought = DROUGHT_EVENTS_FILE
        ds.source_reco = RECO_FILE
        ds.created = datetime.now().isoformat()
        ds.comment = 'Merged from partial run (missing last chunk)'

if __name__ == '__main__':
    main()
