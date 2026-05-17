# -*- coding: utf-8 -*-
"""
融合 Copernicus C3S Soil Moisture 逐日 NC 文件
将 1980-2024 年的数据融合到两个大 NC 文件中:
  1. RZSM_C3S_1980_2024_daily.nc4  (根系层: rzsm_1, rzsm_2, rzsm_3, rzsm_1m)
  2. SSMV_C3S_1980_2024_daily.nc4  (表层: sm)

内存优化: 逐文件读取写入, 不在内存中累积全部数据

用法:
  python merge_c3s_sm.py
"""

import os
import glob
import re
import numpy as np
import netCDF4 as nc
from datetime import datetime
import time
import gc

# ==================== 配置 ====================
DATA_DIR = "/data/Copernicus C3S Soil Moisture"
OUT_DIR = os.path.join(DATA_DIR, "total")
START_YEAR = 1980
END_YEAR = 2024

# RZSM 文件名模式
RZSM_PATTERN = "C3S-RZSM-L3S-RZSMV-DAILY-*-v202505.0.0.nc"
# SSMV 文件名模式
SSMV_PATTERN = "C3S-SOILMOISTURE-L3S-SSMV-COMBINED-DAILY-*-v202505.0.0.nc"


def extract_date_from_filename(filename):
    """从文件名提取日期字符串, 返回 (year, month, day) 或 None"""
    # 匹配 14 位日期时间戳: YYYYMMDDHHMMSS
    m = re.search(r'DAILY-(\d{4})(\d{2})(\d{2})\d{6}', filename)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None


def filter_and_sort_files(file_list, start_year, end_year):
    """过滤指定年份范围的文件并按日期排序, 去除同一天的重复文件 (保留 TCDR)"""
    dated_files = []
    for f in file_list:
        date_info = extract_date_from_filename(os.path.basename(f))
        if date_info is None:
            continue
        year, month, day = date_info
        if start_year <= year <= end_year:
            dated_files.append((year, month, day, f))

    # 按日期排序
    dated_files.sort(key=lambda x: (x[0], x[1], x[2]))

    # 去重: 同一天可能有 TCDR 和 ICDR, 优先保留 TCDR
    unique = {}
    for year, month, day, f in dated_files:
        key = (year, month, day)
        if key not in unique:
            unique[key] = f
        else:
            # 优先 TCDR
            if 'TCDR' in f:
                unique[key] = f

    result = [(k[0], k[1], k[2], v) for k, v in sorted(unique.items())]
    return result


def merge_rzsm(data_dir, out_dir, start_year, end_year):
    """融合 RZSM 数据"""
    print("=" * 70)
    print("  融合 RZSM (根系层土壤湿度) 数据")
    print("=" * 70)

    # 查找文件
    pattern = os.path.join(data_dir, RZSM_PATTERN)
    file_list = glob.glob(pattern)
    print(f"找到 {len(file_list)} 个 RZSM 文件")

    # 过滤和排序
    dated_files = filter_and_sort_files(file_list, start_year, end_year)
    n_times = len(dated_files)
    print(f"筛选 {start_year}-{end_year} 年: {n_times} 个文件")

    if n_times == 0:
        print("错误: 无文件可处理")
        return

    # 读取第一个文件获取空间维度
    first_file = dated_files[0][3]
    with nc.Dataset(first_file, 'r') as ds0:
        lat = ds0.variables['lat'][:]
        lon = ds0.variables['lon'][:]
        n_lat = len(lat)
        n_lon = len(lon)

    print(f"空间维度: {n_lat} x {n_lon} (0.25°)")
    print(f"时间步数: {n_times}")
    print(f"日期范围: {dated_files[0][0]}/{dated_files[0][1]:02d}/{dated_files[0][2]:02d} -> "
          f"{dated_files[-1][0]}/{dated_files[-1][1]:02d}/{dated_files[-1][2]:02d}")

    # 创建输出文件
    out_path = os.path.join(out_dir, f"RZSM_C3S_{start_year}_{end_year}_daily.nc4")
    print(f"\n创建输出文件: {out_path}")

    os.makedirs(out_dir, exist_ok=True)

    ds_out = nc.Dataset(out_path, 'w', format='NETCDF4')

    # 维度
    ds_out.createDimension('time', None)  # unlimited
    ds_out.createDimension('lat', n_lat)
    ds_out.createDimension('lon', n_lon)

    # 坐标变量
    time_var = ds_out.createVariable('time', 'f8', ('time',), zlib=True)
    time_var.units = 'days since 1970-01-01T00:00:00+00:00'
    time_var.calendar = 'standard'
    time_var.long_name = 'time'

    lat_var = ds_out.createVariable('lat', 'f4', ('lat',))
    lat_var[:] = lat
    lat_var.units = 'degrees_north'
    lat_var.long_name = 'latitude'

    lon_var = ds_out.createVariable('lon', 'f4', ('lon',))
    lon_var[:] = lon
    lon_var.units = 'degrees_east'
    lon_var.long_name = 'longitude'

    # 数据变量 - 使用 chunking 和压缩
    chunk_t = 1  # 每次写入1个时间步, 匹配逐日写入模式
    rzsm_vars = {}
    var_info = {
        'rzsm_1': 'Root Zone Soil Moisture at 0-10 cm',
        'rzsm_2': 'Root Zone Soil Moisture at 10-40 cm',
        'rzsm_3': 'Root Zone Soil Moisture at 40-100 cm',
        'rzsm_1m': 'Root Zone Soil Moisture at 0-1 m',
    }
    for vname, long_name in var_info.items():
        v = ds_out.createVariable(vname, 'f4', ('time', 'lat', 'lon'),
                                  fill_value=-9999.0, zlib=True, complevel=4,
                                  chunksizes=(chunk_t, n_lat, n_lon))
        v.units = 'm3 m-3'
        v.long_name = long_name
        rzsm_vars[vname] = v

    # 全局属性
    ds_out.title = f'C3S Root Zone Soil Moisture (RZSM) Daily {start_year}-{end_year}'
    ds_out.source = 'Copernicus Climate Change Service (C3S) Soil Moisture'
    ds_out.resolution = '0.25 degrees'
    ds_out.created = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 逐文件读取写入
    print(f"\n开始逐文件写入...")
    t_start = time.time()

    for i, (year, month, day, fpath) in enumerate(dated_files):
        try:
            with nc.Dataset(fpath, 'r') as ds_in:
                # 写入时间
                time_val = ds_in.variables['time'][0]
                time_var[i] = float(time_val)

                # 写入数据变量
                for vname in var_info:
                    if vname in ds_in.variables:
                        data = ds_in.variables[vname][0, :, :]
                        if hasattr(data, 'mask'):
                            data = np.ma.filled(data, -9999.0)
                        rzsm_vars[vname][i, :, :] = data
                    else:
                        rzsm_vars[vname][i, :, :] = -9999.0

        except Exception as e:
            print(f"\n  [警告] 跳过文件 {os.path.basename(fpath)}: {e}")
            for vname in var_info:
                rzsm_vars[vname][i, :, :] = -9999.0
            continue

        # 进度
        if (i + 1) % 500 == 0 or i == n_times - 1:
            elapsed = time.time() - t_start
            speed = (i + 1) / elapsed
            eta = (n_times - i - 1) / speed
            print(f"\r  [{i+1}/{n_times}] {year}/{month:02d}/{day:02d} | "
                  f"{speed:.1f} 文件/s | ETA: {eta/60:.1f}m", end='', flush=True)

        # 定期刷新和 GC
        if (i + 1) % 2000 == 0:
            ds_out.sync()
            gc.collect()

    ds_out.close()
    elapsed = time.time() - t_start
    fsize = os.path.getsize(out_path) / (1024**3)
    print(f"\n\n✓ RZSM 融合完成! 耗时: {elapsed/60:.1f}分钟, 文件大小: {fsize:.2f} GB")


def merge_ssmv(data_dir, out_dir, start_year, end_year):
    """融合 SSMV 数据"""
    print("\n" + "=" * 70)
    print("  融合 SSMV (表层土壤湿度) 数据")
    print("=" * 70)

    # 查找文件
    pattern = os.path.join(data_dir, SSMV_PATTERN)
    file_list = glob.glob(pattern)
    print(f"找到 {len(file_list)} 个 SSMV 文件")

    # 过滤和排序
    dated_files = filter_and_sort_files(file_list, start_year, end_year)
    n_times = len(dated_files)
    print(f"筛选 {start_year}-{end_year} 年: {n_times} 个文件")

    if n_times == 0:
        print("错误: 无文件可处理")
        return

    # 读取第一个文件获取空间维度
    first_file = dated_files[0][3]
    with nc.Dataset(first_file, 'r') as ds0:
        lat = ds0.variables['lat'][:]
        lon = ds0.variables['lon'][:]
        n_lat = len(lat)
        n_lon = len(lon)

    print(f"空间维度: {n_lat} x {n_lon} (0.25°)")
    print(f"时间步数: {n_times}")
    print(f"日期范围: {dated_files[0][0]}/{dated_files[0][1]:02d}/{dated_files[0][2]:02d} -> "
          f"{dated_files[-1][0]}/{dated_files[-1][1]:02d}/{dated_files[-1][2]:02d}")

    # 创建输出文件
    out_path = os.path.join(out_dir, f"SSMV_C3S_{start_year}_{end_year}_daily.nc4")
    print(f"\n创建输出文件: {out_path}")

    os.makedirs(out_dir, exist_ok=True)

    ds_out = nc.Dataset(out_path, 'w', format='NETCDF4')

    # 维度
    ds_out.createDimension('time', None)
    ds_out.createDimension('lat', n_lat)
    ds_out.createDimension('lon', n_lon)

    # 坐标变量
    time_var = ds_out.createVariable('time', 'f8', ('time',), zlib=True)
    time_var.units = 'days since 1970-01-01 00:00:00 UTC'
    time_var.calendar = 'standard'
    time_var.long_name = 'time'

    lat_var = ds_out.createVariable('lat', 'f4', ('lat',))
    lat_var[:] = lat
    lat_var.units = 'degrees_north'
    lat_var.long_name = 'latitude'

    lon_var = ds_out.createVariable('lon', 'f4', ('lon',))
    lon_var[:] = lon
    lon_var.units = 'degrees_east'
    lon_var.long_name = 'longitude'

    # 数据变量
    chunk_t = 1  # 每次写入1个时间步, 匹配逐日写入模式
    sm_var = ds_out.createVariable('sm', 'f4', ('time', 'lat', 'lon'),
                                   fill_value=-9999.0, zlib=True, complevel=4,
                                   chunksizes=(chunk_t, n_lat, n_lon))
    sm_var.units = 'm3 m-3'
    sm_var.long_name = 'Volumetric Soil Moisture'

    # 全局属性
    ds_out.title = f'C3S Surface Soil Moisture (SSM) Daily {start_year}-{end_year}'
    ds_out.source = 'Copernicus Climate Change Service (C3S) Soil Moisture'
    ds_out.resolution = '0.25 degrees'
    ds_out.created = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 逐文件读取写入
    print(f"\n开始逐文件写入...")
    t_start = time.time()

    for i, (year, month, day, fpath) in enumerate(dated_files):
        try:
            with nc.Dataset(fpath, 'r') as ds_in:
                time_val = ds_in.variables['time'][0]
                time_var[i] = float(time_val)

                data = ds_in.variables['sm'][0, :, :]
                if hasattr(data, 'mask'):
                    data = np.ma.filled(data, -9999.0)
                sm_var[i, :, :] = data

        except Exception as e:
            print(f"\n  [警告] 跳过文件 {os.path.basename(fpath)}: {e}")
            sm_var[i, :, :] = -9999.0
            continue

        if (i + 1) % 500 == 0 or i == n_times - 1:
            elapsed = time.time() - t_start
            speed = (i + 1) / elapsed
            eta = (n_times - i - 1) / speed
            print(f"\r  [{i+1}/{n_times}] {year}/{month:02d}/{day:02d} | "
                  f"{speed:.1f} 文件/s | ETA: {eta/60:.1f}m", end='', flush=True)

        if (i + 1) % 2000 == 0:
            ds_out.sync()
            gc.collect()

    ds_out.close()
    elapsed = time.time() - t_start
    fsize = os.path.getsize(out_path) / (1024**3)
    print(f"\n\n✓ SSMV 融合完成! 耗时: {elapsed/60:.1f}分钟, 文件大小: {fsize:.2f} GB")


if __name__ == '__main__':
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"数据目录: {DATA_DIR}")
    print(f"输出目录: {OUT_DIR}")
    print(f"年份范围: {START_YEAR}-{END_YEAR}")

    merge_rzsm(DATA_DIR, OUT_DIR, START_YEAR, END_YEAR)
    merge_ssmv(DATA_DIR, OUT_DIR, START_YEAR, END_YEAR)

    print(f"\n全部完成! 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
