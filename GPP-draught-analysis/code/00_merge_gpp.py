"""
合并41年GPP数据到单个NC文件
使用60核并行加速数据读取
"""
import os
import numpy as np
import netCDF4 as nc
from tqdm import tqdm
from multiprocessing import Pool, shared_memory
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

def read_year_data(year):
    """读取单年数据"""
    filepath = os.path.join(GPP_DATA_DIR, f"BESS_GPP_{year}_0.1deg.nc")
    if not os.path.exists(filepath):
        return year, None
    
    try:
        with nc.Dataset(filepath, 'r') as ds:
            gpp = ds.variables['GPP'][:].astype(np.float32)
            if hasattr(gpp, 'mask'):
                gpp = gpp.filled(np.nan)
        return year, gpp
    except Exception as e:
        print(f"Error reading {year}: {e}")
        return year, None

def main():
    print("=" * 60)
    print("合并GPP数据 (1982-2022) 为单个NC文件")
    print("=" * 60)
    
    # 获取年份信息
    years, year_info, total_days = get_year_info()
    print(f"\n年份范围: {years[0]}-{years[-1]} ({len(years)} 年)")
    print(f"总天数: {total_days}")
    
    # 读取第一个文件获取空间维度
    first_file = os.path.join(GPP_DATA_DIR, f"BESS_GPP_{years[0]}_0.1deg.nc")
    with nc.Dataset(first_file, 'r') as ds:
        lat = ds.variables['lat'][:]
        lon = ds.variables['lon'][:]
        lat_size = len(lat)
        lon_size = len(lon)
    
    print(f"空间维度: {lat_size} x {lon_size}")
    
    # 检查是否已存在
    if os.path.exists(OUTPUT_FILE):
        print(f"\n文件已存在: {OUTPUT_FILE}")
        print("跳过合并步骤")
        return
    
    # 使用60核并行读取所有年份数据
    print(f"\n[1/2] 并行读取所有年份数据 ({N_WORKERS}核)...")
    
    with Pool(processes=N_WORKERS) as pool:
        results = list(tqdm(
            pool.imap(read_year_data, years),
            total=len(years),
            desc="读取年度数据"
        ))
    
    # 整理结果
    year_data = {}
    for year, data in results:
        if data is not None:
            year_data[year] = data
            print(f"  {year}: 读取成功, shape={data.shape}")
        else:
            print(f"  {year}: 读取失败")
    
    if len(year_data) == 0:
        print("Error: 没有读取到任何数据")
        return
    
    # 创建输出文件
    print(f"\n[2/2] 写入合并文件...")
    
    with nc.Dataset(OUTPUT_FILE, 'w', format='NETCDF4') as ds_out:
        # 创建维度
        ds_out.createDimension('time', total_days)
        ds_out.createDimension('lat', lat_size)
        ds_out.createDimension('lon', lon_size)
        
        # 时间变量
        time_var = ds_out.createVariable('time', 'i4', ('time',))
        time_var.units = f'days since {START_YEAR}-01-01'
        time_var.calendar = 'standard'
        time_var[:] = np.arange(total_days)
        
        # 坐标变量
        lat_var = ds_out.createVariable('lat', 'f4', ('lat',))
        lat_var[:] = lat
        lat_var.units = 'degrees_north'
        
        lon_var = ds_out.createVariable('lon', 'f4', ('lon',))
        lon_var[:] = lon
        lon_var.units = 'degrees_east'
        
        # GPP变量 (使用chunking优化读取)
        gpp_var = ds_out.createVariable(
            'GPP', 'f4', ('time', 'lat', 'lon'),
            zlib=True, complevel=4, 
            chunksizes=(365, 100, 100),  # 按时间优化的chunk
            fill_value=np.nan
        )
        gpp_var.units = 'gC/m2/day'
        gpp_var.long_name = 'Gross Primary Production (merged 1982-2022)'
        
        # 写入数据
        for year in tqdm(years, desc="写入数据"):
            if year in year_data:
                info = year_info[year]
                start_idx = info['start_idx']
                days = info['days']
                gpp_var[start_idx:start_idx + days, :, :] = year_data[year]
        
        # 保存年份索引信息
        ds_out.year_start = START_YEAR
        ds_out.year_end = END_YEAR
        
        # 保存year_info
        import json
        ds_out.year_info = json.dumps({str(k): v for k, v in year_info.items()})
    
    print(f"\n完成! 保存至: {OUTPUT_FILE}")
    
    # 显示文件大小
    file_size = os.path.getsize(OUTPUT_FILE) / (1024**3)
    print(f"文件大小: {file_size:.2f} GB")

if __name__ == "__main__":
    main()
