"""
合并SMrz数据到单个NC文件 (可配置并行版)
策略: 
- 并行进程数可配置 (默认2个)
- 每年数据按30天分块读取写入，每进程内存 < 1GB
- 总内存峰值 ≈ 进程数 × 1GB
"""
import os
import numpy as np
import netCDF4 as nc
from tqdm import tqdm
import sys
from multiprocessing import Pool, Manager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import *

# 输入/输出配置
INPUT_DIR = os.path.join(BASE_DIR, "gleam/SMrz_dd")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "SMrz_merged_1980_2024.nc")
VAR_NAME = 'SMrz'

# 时间范围
SM_START_YEAR = 1980
SM_END_YEAR = 2024

# ============================================
# 可配置参数 (修改这里调整性能)
# ============================================
# 并行进程数: 
#   - 2进程: 约2GB内存，速度2x
#   - 3进程: 约3GB内存，速度3x
#   - 4进程: 约4GB内存，速度4x
PARALLEL_WORKERS = 50  # <-- 修改这里

# 分块大小 (天数): 30天约750MB
CHUNK_DAYS = 30
# ============================================

def get_year_info():
    """获取年份信息和时间索引"""
    years = list(range(SM_START_YEAR, SM_END_YEAR + 1))
    total_days = 0
    year_info = {}
    
    for year in years:
        is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
        days = 366 if is_leap else 365
        year_info[year] = {
            'start_idx': total_days,
            'days': days,
        }
        total_days += days
    
    return years, year_info, total_days

def process_year(args):
    """
    处理单年数据 (分块读取写入)
    内存占用: 最多 CHUNK_DAYS * lat * lon * 4 bytes ≈ 750MB
    """
    year, start_idx, days, lock = args
    
    input_file = os.path.join(INPUT_DIR, f"SMrz_{year}_GLEAM_v4.2a.nc")
    if not os.path.exists(input_file):
        return year, False, "File not found"
    
    try:
        with nc.Dataset(input_file, 'r') as ds_in:
            # 分块读取和写入
            for d_start in range(0, days, CHUNK_DAYS):
                d_end = min(d_start + CHUNK_DAYS, days)
                
                # 读取小块数据 (~750MB)
                chunk_data = ds_in.variables[VAR_NAME][d_start:d_end, :, :].astype(np.float32)
                if hasattr(chunk_data, 'mask'):
                    chunk_data = chunk_data.filled(np.nan)
                
                # 加锁写入
                with lock:
                    with nc.Dataset(OUTPUT_FILE, 'a') as ds_out:
                        ds_out.variables[VAR_NAME][start_idx + d_start : start_idx + d_end, :, :] = chunk_data
                
                del chunk_data
        
        return year, True, "Success"
        
    except Exception as e:
        return year, False, str(e)

def main():
    print("=" * 60)
    print(f"合并SMrz数据 ({PARALLEL_WORKERS}进程并行, 分块读写)")
    print("=" * 60)
    
    # 1. 初始化
    years, year_info, total_days = get_year_info()
    print(f"年份范围: {years[0]}-{years[-1]} ({len(years)} 年)")
    print(f"总天数: {total_days}")
    print(f"并行进程: {PARALLEL_WORKERS}")
    print(f"分块大小: {CHUNK_DAYS} 天")
    print(f"预计内存: ≈{PARALLEL_WORKERS}GB")
    
    # 获取空间维度
    first_file = os.path.join(INPUT_DIR, f"SMrz_{years[0]}_GLEAM_v4.2a.nc")
    with nc.Dataset(first_file, 'r') as ds:
        lat = ds.variables['lat'][:]
        lon = ds.variables['lon'][:]
    
    print(f"空间维度: {len(lat)} x {len(lon)}")
    
    # 2. 准备输出文件
    if os.path.exists(OUTPUT_FILE):
        print(f"\n清理旧文件: {OUTPUT_FILE}")
        os.remove(OUTPUT_FILE)
    
    print(f"\n[1/2] 初始化空文件...")
    with nc.Dataset(OUTPUT_FILE, 'w', format='NETCDF4') as ds_out:
        ds_out.createDimension('time', total_days)
        ds_out.createDimension('lat', len(lat))
        ds_out.createDimension('lon', len(lon))
        
        time_var = ds_out.createVariable('time', 'i4', ('time',))
        time_var.units = f'days since {SM_START_YEAR}-01-01'
        time_var[:] = np.arange(total_days)
        
        ds_out.createVariable('lat', 'f4', ('lat',))[:] = lat
        ds_out.createVariable('lon', 'f4', ('lon',))[:] = lon
        
        ds_out.createVariable(
            VAR_NAME, 'f4', ('time', 'lat', 'lon'),
            zlib=True, complevel=4,
            chunksizes=(365, 100, 100),
            fill_value=np.nan
        )
    
    # 3. 多进程处理
    print(f"\n[2/2] 开始并行处理...")
    
    manager = Manager()
    lock = manager.Lock()
    
    tasks = [(year, year_info[year]['start_idx'], year_info[year]['days'], lock) for year in years]
    
    with Pool(processes=PARALLEL_WORKERS) as pool:
        results = list(tqdm(
            pool.imap_unordered(process_year, tasks),
            total=len(tasks),
            desc="合并进度"
        ))
    
    # 检查结果
    failed = [r for r in results if not r[1]]
    if failed:
        print("\nErrors:")
        for year, _, msg in failed:
            print(f"  {year}: {msg}")
    else:
        print("\n全部成功!")
        print(f"文件: {OUTPUT_FILE}")
        print(f"大小: {os.path.getsize(OUTPUT_FILE)/(1024**3):.2f} GB")

if __name__ == "__main__":
    main()
