#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NEE 数据重采样和年度聚合脚本
将0.05°分辨率的日尺度NEE数据重采样到0.1°并按年份聚合
"""

import os
import numpy as np
import netCDF4 as nc
from tqdm import tqdm
from multiprocessing import Pool
from scipy.ndimage import zoom

# 配置
INPUT_DIR = "/data/BESS_V2/NEE"
OUTPUT_DIR = "/data/BESS_V2/NEE_yearly_0.1"
START_YEAR = 1982
END_YEAR = 2022
NUM_WORKERS = 20  # 根据系统资源调整

def get_days_in_year(year):
    """计算某年的天数"""
    if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
        return 366
    return 365

def resample_to_01deg(data, method='mean'):
    """
    将0.05°分辨率数据重采样到0.1°分辨率
    
    参数:
        data: 输入数据 (lat, lon) 原始分辨率0.05°
        method: 重采样方法 'mean'或'sum'
    
    返回:
        重采样后的数据 (lat/2, lon/2)
    """
    # 原始维度: 3600x7200 (0.05°)
    # 目标维度: 1800x3600 (0.1°)
    # 每2x2像素聚合为1个像素
    
    if data is None:
        return None
    
    lat_size, lon_size = data.shape
    new_lat_size = lat_size // 2
    new_lon_size = lon_size // 2
    
    # 处理填充值
    fill_value = -9999
    mask = (data == fill_value)
    
    # 将填充值替换为nan以便正确计算平均值
    data_masked = np.where(mask, np.nan, data.astype(np.float32))
    
    # 重塑数据以便聚合 2x2 -> 1
    reshaped = data_masked.reshape(new_lat_size, 2, new_lon_size, 2)
    
    # 根据方法计算
    if method == 'mean':
        # 计算每2x2块的平均值（忽略nan）
        resampled = np.nanmean(reshaped, axis=(1, 3))
    elif method == 'sum':
        # 计算每2x2块的总和（忽略nan）
        resampled = np.nansum(reshaped, axis=(1, 3))
    else:
        raise ValueError(f"不支持的重采样方法: {method}")
    
    # 将nan替换回填充值
    resampled = np.where(np.isnan(resampled), fill_value, resampled)
    
    return resampled.astype(np.int16)

def read_and_resample_daily_file(filepath):
    """读取单个日文件并重采样"""
    try:
        with nc.Dataset(filepath, 'r') as ds:
            # NEE变量维度为 (lon, lat)，需要转置为 (lat, lon)
            nee_data = ds.variables['NEE'][:, :].T
            
            # 重采样到0.1°
            resampled = resample_to_01deg(nee_data, method='mean')
            
            return resampled
    except Exception as e:
        print(f"警告: 无法读取 {filepath}: {e}")
        return None

def create_resampled_coordinates():
    """创建重采样后的经纬度坐标"""
    # 原始: 0.05°分辨率, 3600x7200
    # 新的: 0.1°分辨率, 1800x3600
    
    # 纬度: -90 到 90 (从南到北)
    lat_0_1 = np.linspace(-89.95, 89.95, 1800)
    
    # 经度: -180 到 180 (从西到东)
    lon_0_1 = np.linspace(-179.95, 179.95, 3600)
    
    return lat_0_1, lon_0_1

def process_year(year):
    """处理单个年份的数据"""
    days = get_days_in_year(year)
    output_file = os.path.join(OUTPUT_DIR, f"NEE_{year}_0.1deg.nc")
    
    if os.path.exists(output_file):
        print(f"[{year}] 已存在，跳过")
        return True
    
    print(f"[{year}] 开始处理 {days} 天数据...")
    
    # 收集所有日文件
    daily_files = []
    for doy in range(1, days + 1):
        filename = f"BESS_NEE_Daily.A{year}{doy:03d}.nc"
        filepath = os.path.join(INPUT_DIR, filename)
        if os.path.exists(filepath):
            daily_files.append(filepath)
        else:
            print(f"  警告: 缺少文件 {filename}")
    
    if not daily_files:
        print(f"[{year}] 没有找到任何数据文件")
        return False
    
    # 获取重采样后的坐标
    lat_0_1, lon_0_1 = create_resampled_coordinates()
    lat_size = len(lat_0_1)
    lon_size = len(lon_0_1)
    
    # 创建输出文件
    with nc.Dataset(output_file, 'w', format='NETCDF4') as ds_out:
        # 创建维度
        ds_out.createDimension('time', None)
        ds_out.createDimension('lat', lat_size)
        ds_out.createDimension('lon', lon_size)
        
        # 创建时间变量
        time_var = ds_out.createVariable('time', 'i4', ('time',))
        time_var.units = f'days since {year}-01-01'
        time_var.calendar = 'standard'
        time_var.long_name = 'time'
        
        # 创建纬度变量
        lat_var = ds_out.createVariable('lat', 'f4', ('lat',))
        lat_var[:] = lat_0_1
        lat_var.units = 'degrees_north'
        lat_var.long_name = 'latitude'
        
        # 创建经度变量
        lon_var = ds_out.createVariable('lon', 'f4', ('lon',))
        lon_var[:] = lon_0_1
        lon_var.units = 'degrees_east'
        lon_var.long_name = 'longitude'
        
        # 创建NEE变量
        nee_var = ds_out.createVariable(
            'NEE', 'i2', ('time', 'lat', 'lon'),
            zlib=True, complevel=4, fill_value=-9999
        )
        nee_var.units = 'gC m-2 d-1'
        nee_var.long_name = 'Net Ecosystem Exchange'
        
        # 全局属性
        ds_out.title = f'BESS V2 Daily NEE {year} (0.1 degree resolution)'
        ds_out.source = 'Resampled from 0.05 degree daily files'
        ds_out.spatial_resolution = '0.1 degree'
        ds_out.temporal_resolution = 'daily'
        ds_out.original_resolution = '0.05 degree'
        
        # 逐日读取、重采样并写入
        for i, filepath in enumerate(tqdm(daily_files, desc=f"[{year}]", leave=False)):
            resampled_data = read_and_resample_daily_file(filepath)
            if resampled_data is not None:
                time_var[i] = i
                nee_var[i, :, :] = resampled_data
    
    print(f"[{year}] 完成, 保存至 {output_file}")
    return True

def main():
    """主函数"""
    # 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 60)
    print("NEE 数据重采样和年度聚合")
    print("=" * 60)
    print(f"输入目录: {INPUT_DIR}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"年份范围: {START_YEAR}-{END_YEAR}")
    print(f"并行进程数: {NUM_WORKERS}")
    print(f"重采样: 0.05° -> 0.1°")
    print("=" * 60)
    
    # 生成年份列表
    years = list(range(START_YEAR, END_YEAR + 1))
    
    # 并行处理
    with Pool(processes=NUM_WORKERS) as pool:
        results = pool.map(process_year, years)
    
    # 统计结果
    success_count = sum(results)
    print("\n" + "=" * 60)
    print(f"全部完成! 成功: {success_count}/{len(years)}")
    print("=" * 60)

if __name__ == "__main__":
    main()
