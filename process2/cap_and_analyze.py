
import os
import numpy as np
from osgeo import gdal, osr

# 配置路径
SMRZ_FILE = "/home/xulc/flash_drought/gleam/clip_result/SMrz/flash_drought_frequency_total_1980_2024.tif"
SMS_FILE = "/home/xulc/flash_drought/gleam/clip_result/SMs/flash_drought_SMs_frequency_total_1980_2024.tif"
OUTPUT_DIR = "/home/xulc/flash_drought/gleam/analysis/west_us"

# 美国西部范围 (粗略定义)
# Lat: 30N ~ 49N
# Lon: -125W ~ -100W
REGION_LAT = (30, 49)
REGION_LON = (-125, -100)

MAX_VAL = 50

def cap_values_inplace(filepath):
    print(f"\n[处理] 正在截断文件值 (>{MAX_VAL} -> {MAX_VAL}): {filepath}")
    ds = gdal.Open(filepath, gdal.GA_Update)  # Update模式
    if not ds:
        print("无法打开文件")
        return False
    
    band = ds.GetRasterBand(1)
    data = band.ReadAsArray()
    no_data = band.GetNoDataValue()
    
    # 执行截断
    mask = (data > MAX_VAL)
    if no_data is not None:
        mask = mask & (data != no_data)
    
    count = np.sum(mask)
    if count > 0:
        data[mask] = MAX_VAL
        band.WriteArray(data)
        band.FlushCache()
        print(f"  已修正 {count} 个像元")
    else:
        print("  不需要修正")
    
    ds = None
    return True

def analyze_west_us():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"\n[分析] 美国西部 ({REGION_LAT}, {REGION_LON})")
    
    # 读取数据
    ds_smrz = gdal.Open(SMRZ_FILE)
    ds_sms = gdal.Open(SMS_FILE)
    
    gt = ds_smrz.GetGeoTransform()
    # gt: (top_left_x, x_res, rot, top_left_y, rot, y_res)
    
    # 提取区域
    # 假设两张图完全对齐
    rows = ds_smrz.RasterYSize
    cols = ds_smrz.RasterXSize
    
    # 计算行列范围
    # lon = gt[0] + x * gt[1]
    # lat = gt[3] + y * gt[5]
    
    x_min = int((REGION_LON[0] - gt[0]) / gt[1])
    x_max = int((REGION_LON[1] - gt[0]) / gt[1])
    y_min = int((REGION_LAT[1] - gt[3]) / gt[5])
    y_max = int((REGION_LAT[0] - gt[3]) / gt[5])
    
    # 确保坐标正确 (y_res通常是负的)
    if y_min > y_max: y_min, y_max = y_max, y_min
    
    # 边界检查
    x_min = max(0, x_min); x_max = min(cols, x_max)
    y_min = max(0, y_min); y_max = min(rows, y_max)
    
    print(f"  提取窗口: x[{x_min}:{x_max}], y[{y_min}:{y_max}]")
    
    data_smrz = ds_smrz.GetRasterBand(1).ReadAsArray(x_min, y_min, x_max - x_min, y_max - y_min)
    data_sms = ds_sms.GetRasterBand(1).ReadAsArray(x_min, y_min, x_max - x_min, y_max - y_min)
    
    nodata = ds_smrz.GetRasterBand(1).GetNoDataValue()
    
    # 转换为 float 并处理 NaN
    data_smrz = data_smrz.astype(np.float32)
    data_sms = data_sms.astype(np.float32)
    
    if nodata is not None:
        data_smrz[data_smrz == nodata] = np.nan
        data_sms[data_sms == nodata] = np.nan
    
    # 统计
    valid_mask = ~np.isnan(data_smrz) & ~np.isnan(data_sms)
    valid_smrz = data_smrz[valid_mask]
    valid_sms = data_sms[valid_mask]
    
    print(f"\n  有效像元数: {np.sum(valid_mask)}")
    print(f"  SMrz (根系) 平均频率: {np.mean(valid_smrz):.2f}")
    print(f"  SMs (表层) 平均频率: {np.mean(valid_sms):.2f}")
    
    diff = valid_smrz - valid_sms
    print(f"  平均差异 (SMrz - SMs): {np.mean(diff):.2f}")
    
    # 保存差异图
    diff_map = data_smrz - data_sms
    out_file = os.path.join(OUTPUT_DIR, "diff_SMrz_minus_SMs_WestUS.tif")
    
    out_driver = gdal.GetDriverByName('GTiff')
    out_ds = out_driver.Create(out_file, x_max-x_min, y_max-y_min, 1, gdal.GDT_Float32)
    
    # 新的 GeoTransform
    new_gt = list(gt)
    new_gt[0] = gt[0] + x_min * gt[1]
    new_gt[3] = gt[3] + y_min * gt[5]
    out_ds.SetGeoTransform(new_gt)
    out_ds.SetProjection(ds_smrz.GetProjection())
    
    out_band = out_ds.GetRasterBand(1)
    out_band.SetNoDataValue(-9999)
    out_band.WriteArray(diff_map)
    out_band.FlushCache()
    out_ds = None
    
    print(f"  差异图已保存: {out_file}")

if __name__ == "__main__":
    # 1. 截断处理
    cap_values_inplace(SMRZ_FILE)
    cap_values_inplace(SMS_FILE)
    
    # 2. 区域分析
    analyze_west_us()
