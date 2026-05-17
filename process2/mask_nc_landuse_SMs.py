
import os
import shutil
import numpy as np
import netCDF4 as nc
from osgeo import gdal

# 配置
LC_FILE = "/home/xulc/flash_drought/land_use/MCD12C1_LC_Type1_2010_0.10deg.tif"
INPUT_NC = "/home/xulc/flash_drought/gleam/result/SMs_result/flash_drought_SMs_events_details_v2.nc"
OUTPUT_DIR = "/home/xulc/flash_drought/gleam/clip_result/SMs"
OUTPUT_NC = os.path.join(OUTPUT_DIR, os.path.basename(INPUT_NC))

MASK_VALUES = [0, 15, 16]

def mask_nc_file():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"开始处理 NetCDF 掩膜 (SMs)...")
    print(f"土地利用: {LC_FILE}")
    print(f"输入 NC: {INPUT_NC}")
    print(f"输出 NC: {OUTPUT_NC}")

    # 1. 读取掩膜数据
    ds_lc = gdal.Open(LC_FILE)
    if not ds_lc:
        print(f"无法打开 LC 文件")
        return
    lc_data = ds_lc.GetRasterBand(1).ReadAsArray()
    
    mask_2d = np.isin(lc_data, MASK_VALUES)
    masked_count = np.sum(mask_2d)
    print(f"掩膜像元数: {masked_count}")

    # 2. 复制文件
    if os.path.exists(OUTPUT_NC):
        os.remove(OUTPUT_NC)
    shutil.copy2(INPUT_NC, OUTPUT_NC)
    
    # 3. 修改文件
    with nc.Dataset(OUTPUT_NC, 'r+') as ds:
        for var_name, var in ds.variables.items():
            if var_name in ['lat', 'lon']:
                continue
                
            dims = var.dimensions
            shape = var.shape
            
            has_spatial = False
            lat_idx = -1
            lon_idx = -1
            
            if 'lat' in dims and 'lon' in dims:
                lat_idx = list(dims).index('lat')
                lon_idx = list(dims).index('lon')
                if lat_idx == len(dims) - 2 and lon_idx == len(dims) - 1:
                    has_spatial = True
            
            if has_spatial:
                print(f"  处理变量: {var_name}, 维度: {dims}")
                
                # 读取数据
                data = var[:]
                
                # 获取 fill value
                fill_value = getattr(var, '_FillValue', None)
                if fill_value is None:
                    if np.issubdtype(data.dtype, np.integer):
                        fill_value = -1
                    else:
                        fill_value = np.nan
                
                # 应用掩膜 (使用优化后的广播赋值)
                if len(shape) == 2:
                    # (lat, lon)
                    if np.ma.is_masked(data):
                        # 对于 masked array, 如果直接 slice assignment 可能需要处理 mask
                        # data[mask_2d] = fill_value 会修改 data 也会自动设 mask?
                        # 测试表明通常需要显式设 mask
                        data[mask_2d] = fill_value
                        data.mask[mask_2d] = True
                    else:
                        data[mask_2d] = fill_value
                        
                elif len(shape) == 3:
                     # (events, lat, lon)
                     if shape[-2:] == mask_2d.shape:
                         if np.ma.is_masked(data):
                             # 操作底层数据和掩膜
                             d = data.data
                             m = data.mask
                             d[:, mask_2d] = fill_value
                             m[:, mask_2d] = True
                             # 赋值回 var 会触发自动转换，应该没问题
                             var[:] = data
                         else:
                             # 纯 numpy array
                             data[:, mask_2d] = fill_value
                             var[:] = data
                
    print(f"处理完成! 已保存至 {OUTPUT_NC}")

if __name__ == "__main__":
    mask_nc_file()
