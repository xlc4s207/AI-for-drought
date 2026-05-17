
import os
import glob
import numpy as np
import netCDF4 as nc
from tqdm import tqdm
from multiprocessing import Pool

# 配置
INPUT_DIR = "/data/BESS_V2/GPP_Daily"
OUTPUT_DIR = "/data/BESS_V2/GPP_Daily/yearly"
START_YEAR = 1982
END_YEAR = 2022
NUM_WORKERS = 50

def get_days_in_year(year):
    """获取指定年份的天数 (考虑闰年)"""
    if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
        return 366
    return 365

def read_daily_file(filepath):
    """读取单个每日文件的 GPP 数据"""
    try:
        with nc.Dataset(filepath, 'r') as ds:
            # 注意: BESS GPP 的维度是 (lon, lat)，需要转置为 (lat, lon)
            gpp = ds.variables['GPP'][:, :].T  # 转置为 (lat, lon)
            return gpp
    except Exception as e:
        print(f"警告: 无法读取 {filepath}: {e}")
        return None

def merge_year(year):
    """将一年的日数据合并成年度文件"""
    days = get_days_in_year(year)
    output_file = os.path.join(OUTPUT_DIR, f"BESS_GPP_{year}.nc")
    
    # 检查是否已存在
    if os.path.exists(output_file):
        print(f"[{year}] 已存在，跳过")
        return True
    
    print(f"[{year}] 开始合并 {days} 天数据...")
    
    # 收集该年所有文件
    daily_files = []
    for doy in range(1, days + 1):
        filename = f"BESS_GPP_Daily.A{year}{doy:03d}.nc"
        filepath = os.path.join(INPUT_DIR, filename)
        if os.path.exists(filepath):
            daily_files.append(filepath)
        else:
            print(f"  警告: 缺少文件 {filename}")
    
    if not daily_files:
        print(f"[{year}] 没有找到任何数据文件")
        return False
    
    # 读取第一个文件获取维度信息
    with nc.Dataset(daily_files[0], 'r') as ds0:
        lat = ds0.variables['lat'][:]
        lon = ds0.variables['lon'][:]
        lat_size = len(lat)
        lon_size = len(lon)
    
    # 创建输出文件
    with nc.Dataset(output_file, 'w', format='NETCDF4') as ds_out:
        # 创建维度
        ds_out.createDimension('time', None)  # unlimited
        ds_out.createDimension('lat', lat_size)
        ds_out.createDimension('lon', lon_size)
        
        # 创建坐标变量
        time_var = ds_out.createVariable('time', 'i4', ('time',))
        time_var.units = f'days since {year}-01-01'
        time_var.calendar = 'standard'
        
        lat_var = ds_out.createVariable('lat', 'f4', ('lat',))
        lat_var[:] = lat
        lat_var.units = 'degrees_north'
        
        lon_var = ds_out.createVariable('lon', 'f4', ('lon',))
        lon_var[:] = lon
        lon_var.units = 'degrees_east'
        
        # 创建 GPP 变量 (带压缩)
        # 原始数据是 int16，保持类型
        gpp_var = ds_out.createVariable(
            'GPP', 'i2', ('time', 'lat', 'lon'),
            zlib=True, complevel=4, fill_value=-32768
        )
        gpp_var.units = 'gC/m2/day * 100'  # 假设比例因子
        gpp_var.long_name = 'Gross Primary Production'
        
        # 全局属性
        ds_out.title = f'BESS V2 Daily GPP {year}'
        ds_out.source = 'Merged from daily files'
        
        # 逐日读取并写入
        for i, filepath in enumerate(tqdm(daily_files, desc=f"[{year}]", leave=False)):
            data = read_daily_file(filepath)
            if data is not None:
                time_var[i] = i  # DOY - 1 (0-indexed)
                gpp_var[i, :, :] = data
    
    print(f"[{year}] 完成, 保存至 {output_file}")
    return True

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"开始合并 BESS GPP 数据 ({START_YEAR}-{END_YEAR})...")
    print(f"输入目录: {INPUT_DIR}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"并行进程数: {NUM_WORKERS}")
    
    years = list(range(START_YEAR, END_YEAR + 1))
    
    # 使用 multiprocessing 并行处理各年份
    with Pool(processes=NUM_WORKERS) as pool:
        results = pool.map(merge_year, years)
    
    success_count = sum(results)
    print(f"\n全部完成! 成功: {success_count}/{len(years)}")

if __name__ == "__main__":
    main()
