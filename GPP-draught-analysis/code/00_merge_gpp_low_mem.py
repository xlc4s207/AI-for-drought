"""
合并41年GPP数据到单个NC文件 (低内存优化版)
策略: 初始化空的大文件，然后逐年读取并写入，避免一次性加载过多数据
"""
import os
import numpy as np
import netCDF4 as nc
from tqdm import tqdm
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import *

# 输出文件
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "GPP_merged_1982_2022.nc")

def get_year_info():
    """获取年份信息和时间索引"""
    years = list(range(START_YEAR, END_YEAR + 1))
    total_days = 0
    year_info = {}
    
    for year in years:
        is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
        days = 366 if is_leap else 365
        year_info[year] = {
            'start_idx': total_days,
            'days': days,
            'is_leap': is_leap
        }
        total_days += days
    
    return years, year_info, total_days

def main():
    print("=" * 60)
    print("合并GPP数据 (低内存模式)")
    print("=" * 60)
    
    # 1. 获取基础信息
    years, year_info, total_days = get_year_info()
    print(f"年份范围: {years[0]}-{years[-1]} ({len(years)} 年)")
    print(f"总天数: {total_days}")
    
    # 获取空间维度
    first_file = os.path.join(GPP_DATA_DIR, f"BESS_GPP_{years[0]}_0.1deg.nc")
    with nc.Dataset(first_file, 'r') as ds:
        lat = ds.variables['lat'][:]
        lon = ds.variables['lon'][:]
        lat_size = len(lat)
        lon_size = len(lon)
    print(f"空间维度: {lat_size} x {lon_size}")
    
    # 2. 初始化输出文件 (如果不存在)
    if os.path.exists(OUTPUT_FILE):
        print(f"\n文件已存在: {OUTPUT_FILE}")
        msg = input("是否覆盖? (y/n): ")
        if msg.lower() != 'y':
            print("取消操作")
            return
        os.remove(OUTPUT_FILE)
    
    print(f"\n[1/2] 初始化输出文件...")
    with nc.Dataset(OUTPUT_FILE, 'w', format='NETCDF4') as ds_out:
        # 定义维度
        ds_out.createDimension('time', total_days)
        ds_out.createDimension('lat', lat_size)
        ds_out.createDimension('lon', lon_size)
        
        # 定义变量
        time_var = ds_out.createVariable('time', 'i4', ('time',))
        time_var.units = f'days since {START_YEAR}-01-01'
        time_var[:] = np.arange(total_days)
        
        lat_var = ds_out.createVariable('lat', 'f4', ('lat',))
        lat_var[:] = lat
        
        lon_var = ds_out.createVariable('lon', 'f4', ('lon',))
        lon_var[:] = lon
        
        # 定义GPP变量 (启用压缩)
        # 注意: 不预填充数据，保持文件稀疏，直到写入
        gpp_var = ds_out.createVariable(
            'GPP', 'f4', ('time', 'lat', 'lon'),
            zlib=True, complevel=4,
            chunksizes=(365, 100, 100),  # 按年分块，空间也分块
            fill_value=np.nan
        )
        gpp_var.units = 'gC/m2/day'
    
    # 3. 逐年读取并写入 (低内存关键)
    print(f"\n[2/2] 逐年合并数据...")
    
    # 使用追加模式打开
    with nc.Dataset(OUTPUT_FILE, 'a') as ds_out:
        gpp_var = ds_out.variables['GPP']
        
        for year in tqdm(years, desc="处理年份"):
            input_file = os.path.join(GPP_DATA_DIR, f"BESS_GPP_{year}_0.1deg.nc")
            
            if not os.path.exists(input_file):
                print(f"Warning: {year} 文件不存在")
                continue
            
            # 读取单年数据
            # 内存消耗: 366 * 1800 * 3600 * 4 bytes ≈ 9 GB
            # 如果9GB仍然太大，可以进一步按时间片读取
            try:
                with nc.Dataset(input_file, 'r') as ds_in:
                    # 获取该年在总时间轴的位置
                    info = year_info[year]
                    start = info['start_idx']
                    end = start + info['days']
                    
                    # 为了进一步降低内存，我们按月(或30天)分块读取写入
                    # 这样内存峰值可以控制在 1GB 以内
                    days = info['days']
                    chunk_size = 30
                    
                    for d_start in range(0, days, chunk_size):
                        d_end = min(d_start + chunk_size, days)
                        
                        # 读取小块数据
                        chunk_data = ds_in.variables['GPP'][d_start:d_end, :, :].astype(np.float32)
                        
                        # 处理掩膜
                        if isinstance(chunk_data, np.ma.MaskedArray):
                            chunk_data = chunk_data.filled(np.nan)
                        
                        # 写入目标文件
                        gpp_var[start+d_start : start+d_end, :, :] = chunk_data
                        
                        # 显式清理
                        del chunk_data
                        
            except Exception as e:
                print(f"Error processing {year}: {e}")
                
    print(f"\n合并完成! 文件: {OUTPUT_FILE}")
    print(f"大小: {os.path.getsize(OUTPUT_FILE)/(1024**3):.2f} GB")

if __name__ == "__main__":
    main()
