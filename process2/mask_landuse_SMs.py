
import os
import numpy as np
from osgeo import gdal

# 配置路径
# 土地利用数据 (已重采样到 0.1 度)
LC_FILE = "/home/xulc/flash_drought/land_use/MCD12C1_LC_Type1_2010_0.10deg.tif"

# 输入数据 (SMs 结果)
INPUT_FILE = "/home/xulc/flash_drought/gleam/result/SMs_result/flash_drought_SMs_frequency_total_1980_2024.tif"

# 输出目录
OUTPUT_DIR = "/home/xulc/flash_drought/gleam/clip_result/SMs"

# 要掩膜掉的 IGBP 类别
# 0: Water, 15: Snow and Ice, 16: Barren or Sparsely Vegetated
MASK_VALUES = [0, 15, 16]

def mask_invalid_pixels():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = os.path.basename(INPUT_FILE)
    output_path = os.path.join(OUTPUT_DIR, filename)

    print(f"开始处理掩膜 (SMs)...")
    print(f"土地利用文件: {LC_FILE}")
    print(f"输入文件: {INPUT_FILE}")
    
    # 1. 读取土地利用数据
    ds_lc = gdal.Open(LC_FILE)
    if ds_lc is None:
        print(f"错误: 无法打开 {LC_FILE}")
        return
    lc_band = ds_lc.GetRasterBand(1)
    lc_data = lc_band.ReadAsArray()
    
    # 2. 读取输入数据
    ds_in = gdal.Open(INPUT_FILE)
    if ds_in is None:
        print(f"错误: 无法打开 {INPUT_FILE}")
        return
    in_band = ds_in.GetRasterBand(1)
    in_data = in_band.ReadAsArray()
    no_data_val = in_band.GetNoDataValue()
    if no_data_val is None:
        no_data_val = -9999
    
    # 检查尺寸是否一致
    if lc_data.shape != in_data.shape:
        print(f"错误: 尺寸不匹配! LC: {lc_data.shape}, Input: {in_data.shape}")
        return

    # 3. 创建掩膜
    mask = np.isin(lc_data, MASK_VALUES)
    
    masked_count = np.sum(mask)
    print(f"将掩膜 {masked_count} 个像元 (0/15/16 类)")
    
    # 4. 应用掩膜
    out_data = in_data.copy()
    
    if np.isnan(no_data_val):
         out_data[mask] = np.nan
    else:
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
