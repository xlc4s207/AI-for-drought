"""
合并41年GPP数据到单个NC文件 (并行且内存安全版)
策略: 
- 限制并发进程数为5 (每个进程占用约9GB内存，总计 < 50GB，符合 < 64GB 要求)
- 并行读取源文件 (IO/解压加速)
- 加锁串行写入目标文件 (防止竞争)
"""
import os
import numpy as np
import netCDF4 as nc
from tqdm import tqdm
import sys
from multiprocessing import Pool, Manager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import *

# 输出文件
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "GPP_merged_1982_2022.nc")

# 并行配置 (根据 64GB 内存限制计算)
# 单年数据: 366 * 1800 * 3600 * 4 bytes ≈ 9.5 GB
# N_WORKERS = 5 -> CPU内存峰值约 47.5 GB < 64 GB
# 预留 buffer 给操作系统
PARALLEL_WORKERS = 5

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

def process_year(args):
    """
    处理单年数据: 读取 -> 等待锁 -> 写入
    args: (year, start_idx, days, lock)
    """
    year, start_idx, days, lock = args
    
    input_file = os.path.join(GPP_DATA_DIR, f"BESS_GPP_{year}_0.1deg.nc")
    if not os.path.exists(input_file):
        return year, False, "File not found"
    
    try:
        # 1. 独立读取 (并行执行)
        # print(f"[{year}] Reading...")
        with nc.Dataset(input_file, 'r') as ds_in:
            # 读取全部数据到内存
            data = ds_in.variables['GPP'][:].astype(np.float32)
            if hasattr(data, 'mask'):
                data = data.filled(np.nan)
        
        # 2. 写入目标文件 (串行执行)
        # print(f"[{year}] Waiting for lock to write...")
        with lock:
            # print(f"[{year}] Writing...")
            # 注意: 每次写入都需要重新打开文件，因为Dataset对象不能跨进程共享
            # 虽然有开销，但比序列化传输 9GB 数据要快得多
            with nc.Dataset(OUTPUT_FILE, 'a') as ds_out:
                gpp_var = ds_out.variables['GPP']
                gpp_var[start_idx : start_idx + days, :, :] = data
        
        # 释放内存
        del data
        return year, True, "Success"
        
    except Exception as e:
        return year, False, str(e)

def main():
    print("=" * 60)
    print(f"合并GPP数据 (并行内存安全版, {PARALLEL_WORKERS} 进程)")
    print("=" * 60)
    
    # 1. 初始化
    years, year_info, total_days = get_year_info()
    print(f"年份范围: {years[0]}-{years[-1]} ({len(years)} 年)")
    print(f"总天数: {total_days}")
    
    # 获取空间维度
    first_file = os.path.join(GPP_DATA_DIR, f"BESS_GPP_{years[0]}_0.1deg.nc")
    with nc.Dataset(first_file, 'r') as ds:
        lat = ds.variables['lat'][:]
        lon = ds.variables['lon'][:]
    
    # 2. 准备输出文件
    if os.path.exists(OUTPUT_FILE):
        print(f"\n清理旧文件: {OUTPUT_FILE}")
        os.remove(OUTPUT_FILE)
    
    print(f"\n[1/2] 初始化空文件...")
    with nc.Dataset(OUTPUT_FILE, 'w', format='NETCDF4') as ds_out:
        # 定义维度
        ds_out.createDimension('time', total_days)
        ds_out.createDimension('lat', len(lat))
        ds_out.createDimension('lon', len(lon))
        
        # 定义变量
        time_var = ds_out.createVariable('time', 'i4', ('time',))
        time_var.units = f'days since {START_YEAR}-01-01'
        time_var[:] = np.arange(total_days)
        
        ds_out.createVariable('lat', 'f4', ('lat',))[:] = lat
        ds_out.createVariable('lon', 'f4', ('lon',))[:] = lon
        
        # 定义GPP变量 (启用压缩)
        ds_out.createVariable(
            'GPP', 'f4', ('time', 'lat', 'lon'),
            zlib=True, complevel=4,
            chunksizes=(365, 100, 100),
            fill_value=np.nan
        )
    
    # 3. 多进程处理
    print(f"\n[2/2] 开始并行处理...")
    
    manager = Manager()
    lock = manager.Lock()
    
    # 准备任务参数
    tasks = []
    for year in years:
        info = year_info[year]
        tasks.append((year, info['start_idx'], info['days'], lock))
    
    # 启动进程池
    with Pool(processes=PARALLEL_WORKERS) as pool:
        # 使用 imap_unordered 处理结果，显示进度条
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
        print(f"文件大小: {os.path.getsize(OUTPUT_FILE)/(1024**3):.2f} GB")

if __name__ == "__main__":
    main()
