"""
Convert CCM NetCDF Results to GeoTIFF (SMs)
===========================================
将稀疏存储的 CCM 结果 (v4 SMs) 转换为标准的全球 0.1° GeoTIFF 文件。

输入: ccm_lag_results_v4_SMs.nc
输出: 
  - ccm_SMs_lag_star.tif
  - ccm_SMs_rho_max.tif
  - ccm_SMs_rho_zero.tif
  - ccm_SMs_valid.tif

作者: AI Assistant
日期: 2026-01-25
"""

import os
import numpy as np
import netCDF4 as nc
import rasterio
from rasterio.transform import from_origin
import warnings

warnings.filterwarnings('ignore')

# ================= 配置 =================
BASE_DIR = "/home/xulc/flash_drought"
INPUT_FILE = os.path.join(BASE_DIR, "process/GPP-draught-analysis/CCM_code/results_v4_SMs/ccm_lag_results_v4_SMs.nc")
OUTPUT_DIR = os.path.dirname(INPUT_FILE)

# 全球 0.1 度网格参数
LON_MIN, LON_MAX = -180.0, 180.0
LAT_MIN, LAT_MAX = -90.0, 90.0
RES = 0.1
COLS = int((LON_MAX - LON_MIN) / RES) # 3600
ROWS = int((LAT_MAX - LAT_MIN) / RES) # 1800

# GeoTIFF 变换参数 (左上角坐标，分辨率)
TRANSFORM = from_origin(LON_MIN, LAT_MAX, RES, RES)
CRS = 'EPSG:4326'

def latlon_to_idx(lat, lon):
    """将经纬度转换为网格行列号"""
    # row 0 is at +90 lat
    row = int((90.0 - lat) / RES)
    # col 0 is at -180 lon
    col = int((lon - (-180.0)) / RES)
    return row, col

def save_tif(data, filename, dtype, nodata_val):
    """保存为 GeoTIFF"""
    out_path = os.path.join(OUTPUT_DIR, filename)
    print(f"Saving {out_path}...")
    
    with rasterio.open(
        out_path,
        'w',
        driver='GTiff',
        height=ROWS,
        width=COLS,
        count=1,
        dtype=dtype,
        crs=CRS,
        transform=TRANSFORM,
        nodata=nodata_val,
        compress='lzw'
    ) as dst:
        dst.write(data, 1)

def main():
    print(f"Processing: {INPUT_FILE}")
    
    if not os.path.exists(INPUT_FILE):
        print("Error: Input file not found!")
        return

    with nc.Dataset(INPUT_FILE, 'r') as ds:
        # 读取数据
        print("Reading nc data...")
        lats = ds.variables['lat'][:]
        lons = ds.variables['lon'][:]
        lag_star = ds.variables['lag_star'][:]
        rho_max = ds.variables['rho_max'][:]
        rho_zero = ds.variables['rho_zero'][:]
        valid = ds.variables['valid'][:]
        n_points = len(lats)
        print(f"Total points: {n_points}")

    # ===== 1. 处理 lag_star =====
    print("\nProcessing lag_star...")
    grid_lag = np.full((ROWS, COLS), np.nan, dtype=np.float32)
    
    # 批量计算索引 (向量化以加速)
    # 注意: 数据中的经纬度对应网格中心，需转换为左上角索引
    # 此处假设 grid 对齐良好。直接计算：
    r_idx = ((90.0 - lats) / RES).astype(int)
    c_idx = ((lons - (-180.0)) / RES).astype(int)
    
    # 边界检查
    mask = (r_idx >= 0) & (r_idx < ROWS) & (c_idx >= 0) & (c_idx < COLS)
    
    # 进一步过滤: 只保留 valid == 1 的点
    # 注意: mask 是针对全部点的 boolean array
    is_valid_point = (valid == 1)
    final_mask = mask & is_valid_point
    
    r_idx_valid = r_idx[final_mask]
    c_idx_valid = c_idx[final_mask]
    
    # 填充网格 (只填充有效点，其他保持 NaN)
    grid_lag[r_idx_valid, c_idx_valid] = lag_star[final_mask]
    save_tif(grid_lag, "ccm_SMs_lag_star.tif", rasterio.float32, np.nan)

    # ===== 2. 处理 rho_max =====
    print("\nProcessing rho_max...")
    grid_rho = np.full((ROWS, COLS), np.nan, dtype=np.float32)
    grid_rho[r_idx, c_idx] = rho_max[mask]
    save_tif(grid_rho, "ccm_SMs_rho_max.tif", rasterio.float32, np.nan)

    # ===== 3. 处理 rho_zero =====
    print("\nProcessing rho_zero...")
    grid_rho_zero = np.full((ROWS, COLS), np.nan, dtype=np.float32)
    grid_rho_zero[r_idx, c_idx] = rho_zero[mask]
    save_tif(grid_rho_zero, "ccm_SMs_rho_zero.tif", rasterio.float32, np.nan)

    # ===== 4. 处理 valid =====
    print("\nProcessing valid...")
    grid_valid = np.full((ROWS, COLS), 0, dtype=np.int8)
    grid_valid[r_idx, c_idx] = valid[mask]
    save_tif(grid_valid, "ccm_SMs_valid.tif", rasterio.int8, 0)
    
    print("\nConversion completed successfully!")

if __name__ == "__main__":
    main()
