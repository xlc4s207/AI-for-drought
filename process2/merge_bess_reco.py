
import os
import numpy as np
import netCDF4 as nc
from tqdm import tqdm
from multiprocessing import Pool

# 配置
INPUT_DIR = "/data/BESS_V2/RECO"
OUTPUT_DIR = "/data/BESS_V2/RECO/yearly"
START_YEAR = 1982
END_YEAR = 2022
NUM_WORKERS = 50

def get_days_in_year(year):
    if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
        return 366
    return 365

def read_daily_file(filepath):
    try:
        with nc.Dataset(filepath, 'r') as ds:
            # RECO 变量名可能是 'RECO'，维度可能是 (lon, lat)
            var_name = 'RECO' if 'RECO' in ds.variables else list(ds.variables.keys())[-1]
            data = ds.variables[var_name][:, :].T  # 转置为 (lat, lon)
            return data
    except Exception as e:
        print(f"警告: 无法读取 {filepath}: {e}")
        return None

def merge_year(year):
    days = get_days_in_year(year)
    output_file = os.path.join(OUTPUT_DIR, f"BESS_RECO_{year}.nc")
    
    if os.path.exists(output_file):
        print(f"[{year}] 已存在，跳过")
        return True
    
    print(f"[{year}] 开始合并 {days} 天数据...")
    
    daily_files = []
    for doy in range(1, days + 1):
        filename = f"BESS_RECO_Daily.A{year}{doy:03d}.nc"
        filepath = os.path.join(INPUT_DIR, filename)
        if os.path.exists(filepath):
            daily_files.append(filepath)
        else:
            print(f"  警告: 缺少文件 {filename}")
    
    if not daily_files:
        print(f"[{year}] 没有找到任何数据文件")
        return False
    
    with nc.Dataset(daily_files[0], 'r') as ds0:
        lat = ds0.variables['lat'][:]
        lon = ds0.variables['lon'][:]
        lat_size = len(lat)
        lon_size = len(lon)
    
    with nc.Dataset(output_file, 'w', format='NETCDF4') as ds_out:
        ds_out.createDimension('time', None)
        ds_out.createDimension('lat', lat_size)
        ds_out.createDimension('lon', lon_size)
        
        time_var = ds_out.createVariable('time', 'i4', ('time',))
        time_var.units = f'days since {year}-01-01'
        time_var.calendar = 'standard'
        
        lat_var = ds_out.createVariable('lat', 'f4', ('lat',))
        lat_var[:] = lat
        lat_var.units = 'degrees_north'
        
        lon_var = ds_out.createVariable('lon', 'f4', ('lon',))
        lon_var[:] = lon
        lon_var.units = 'degrees_east'
        
        reco_var = ds_out.createVariable(
            'RECO', 'i2', ('time', 'lat', 'lon'),
            zlib=True, complevel=4, fill_value=-32768
        )
        reco_var.units = 'gC/m2/day * 100'
        reco_var.long_name = 'Ecosystem Respiration'
        
        ds_out.title = f'BESS V2 Daily RECO {year}'
        ds_out.source = 'Merged from daily files'
        
        for i, filepath in enumerate(tqdm(daily_files, desc=f"[{year}]", leave=False)):
            data = read_daily_file(filepath)
            if data is not None:
                time_var[i] = i
                reco_var[i, :, :] = data
    
    print(f"[{year}] 完成, 保存至 {output_file}")
    return True

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"开始合并 BESS RECO 数据 ({START_YEAR}-{END_YEAR})...")
    print(f"输入目录: {INPUT_DIR}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"并行进程数: {NUM_WORKERS}")
    
    years = list(range(START_YEAR, END_YEAR + 1))
    
    with Pool(processes=NUM_WORKERS) as pool:
        results = pool.map(merge_year, years)
    
    success_count = sum(results)
    print(f"\n全部完成! 成功: {success_count}/{len(years)}")

if __name__ == "__main__":
    main()
