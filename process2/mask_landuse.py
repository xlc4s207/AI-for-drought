
import os
import numpy as np
from osgeo import gdal

# 配置路径
LC_FILE = "/home/xulc/flash_drought/land_use/MCD12C1_LC_Type1_2010_0.10deg.tif"
INPUT_SMRZ = "/home/xulc/flash_drought/gleam/result/SMrz_result/flash_drought_frequency_total_1980_2024.tif"
OUTPUT_DIR = "/home/xulc/flash_drought/gleam/clip_result/SMrz"

# 要掩膜掉的 IGBP 类别
# 0: Water, 15: Snow and Ice, 16: Barren or Sparsely Vegetated
MASK_VALUES = [0, 15, 16]

def mask_invalid_pixels():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = os.path.basename(INPUT_SMRZ)
    output_path = os.path.join(OUTPUT_DIR, filename)

    print(f"开始处理掩膜...")
    print(f"土地利用文件: {LC_FILE}")
    print(f"输入文件: {INPUT_SMRZ}")
    
    # 1. 读取土地利用数据
    ds_lc = gdal.Open(LC_FILE)
    if ds_lc is None:
        print(f"错误: 无法打开 {LC_FILE}")
        return
    lc_band = ds_lc.GetRasterBand(1)
    lc_data = lc_band.ReadAsArray()
    
    # 2. 读取输入数据
    ds_in = gdal.Open(INPUT_SMRZ)
    if ds_in is None:
        print(f"错误: 无法打开 {INPUT_SMRZ}")
        return
    in_band = ds_in.GetRasterBand(1)
    in_data = in_band.ReadAsArray()
    no_data_val = in_band.GetNoDataValue()
    if no_data_val is None:
        no_data_val = -9999
    
    # 检查尺寸是否一致
    if lc_data.shape != in_data.shape:
        print(f"错误: 尺寸不匹配! LC: {lc_data.shape}, Input: {in_data.shape}")
        # 这里可以添加重采样逻辑，但假设之前步骤已确保对齐
        return

    # 3. 创建掩膜
    # 找出需要在结果中设为 NaN 的位置
    # 条件: LC 值在 [0, 15, 16] 中
    mask = np.isin(lc_data, MASK_VALUES)
    
    # 统计掩膜像元数
    masked_count = np.sum(mask)
    total_valid = np.sum(in_data != no_data_val)
    print(f"将掩膜 {masked_count} 个像元 (0/15/16 类)")
    
    # 4. 应用掩膜
    # 将对应位置设为 NaN (对于浮点TIFF通常用 np.nan 或 no_data_val)
    # 这里我们使用与原文件相同的 no_data_val 还是 np.nan?
    # 为了保持一致性，如果原数据是 float，通常依然保留 no_data 标记
    # 但 numpy 数组中用 nan 更方便处理
    
    out_data = in_data.copy()
    
    # 如果原数据含 NaN，先统一处理
    if np.isnan(no_data_val):
         # 原本就是 nan
         out_data[mask] = np.nan
    else:
         # 将掩膜位置设为 no_data_val
         out_data[mask] = no_data_val

    # 5. 保存结果
    driver = gdal.GetDriverByName('GTiff')
    ds_out = driver.Create(output_path, ds_in.RasterXSize, ds_in.RasterYSize, 1, in_band.DataType)
    ds_out.SetGeoTransform(ds_in.GetGeoTransform())
    ds_out.SetProjection(ds_in.GetProjection())
    
    out_band = ds_out.GetRasterBand(1)
    out_band.SetNoDataValue(no_data_val)
    out_band.WriteArray(out_data)
    out_band.FlushCache()
    
    ds_lc = None
    ds_in = None
    ds_out = None
    
    print(f"处理完成! 结果保存在: {output_path}")

if __name__ == "__main__":
    mask_invalid_pixels()
