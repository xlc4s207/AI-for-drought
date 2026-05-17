
import os
import shutil
import numpy as np
import netCDF4 as nc
from osgeo import gdal

# 配置
LC_FILE = "/home/xulc/flash_drought/land_use/MCD12C1_LC_Type1_2010_0.10deg.tif"
INPUT_NC = "/home/xulc/flash_drought/gleam/result/SMrz_result/flash_drought_events_details_v2.nc"
OUTPUT_DIR = "/home/xulc/flash_drought/gleam/clip_result/SMrz"
OUTPUT_NC = os.path.join(OUTPUT_DIR, os.path.basename(INPUT_NC))

MASK_VALUES = [0, 15, 16]

def mask_nc_file():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"开始处理 NetCDF 掩膜...")
    print(f"土地利用: {LC_FILE}")
    print(f"输入 NC: {INPUT_NC}")
    print(f"输出 NC: {OUTPUT_NC}")

    # 1. 读取掩膜数据
    ds_lc = gdal.Open(LC_FILE)
    if not ds_lc:
        print(f"无法打开 LC 文件")
        return
    lc_data = ds_lc.GetRasterBand(1).ReadAsArray()
    
    # 生成布尔掩膜 (True 为需要掩膜的区域)
    mask_2d = np.isin(lc_data, MASK_VALUES)
    masked_count = np.sum(mask_2d)
    print(f"掩膜像元数: {masked_count}")

    # 2. 复制文件 (作为基础修改)
    # 因为 NetCDF 结构复杂，先复制再修改通常更稳妥，或者新建并复制属性
    # 这里使用 shutil.copy 先复制，然后以 r+ 模式修改
    if os.path.exists(OUTPUT_NC):
        os.remove(OUTPUT_NC)
    shutil.copy2(INPUT_NC, OUTPUT_NC)
    
    # 3. 打开输出文件进行修改
    with nc.Dataset(OUTPUT_NC, 'r+') as ds:
        # 遍历所有变量
        for var_name, var in ds.variables.items():
            if var_name in ['lat', 'lon']:
                continue
                
            dims = var.dimensions
            shape = var.shape
            
            # 检查是否包含 lat, lon 维度
            # 假设 lat, lon 分别是最后两个维度 或者 只有 lat, lon
            # 我们的文件结构通常是 (max_events, lat, lon) 或 (lat, lon)
            
            has_spatial = False
            lat_idx = -1
            lon_idx = -1
            
            if 'lat' in dims and 'lon' in dims:
                lat_idx = list(dims).index('lat')
                lon_idx = list(dims).index('lon')
                # 确保是最后两维，或者处理广播
                if lat_idx == len(dims) - 2 and lon_idx == len(dims) - 1:
                    has_spatial = True
            
            if has_spatial:
                print(f"  处理变量: {var_name}, 维度: {dims}")
                
                # 读取数据 (如果是 masked array)
                data = var[:]
                
                # 获取 fill value
                fill_value = getattr(var, '_FillValue', None)
                if fill_value is None:
                    # 如果没有 fill value，根据类型设定一个
                    if np.issubdtype(data.dtype, np.integer):
                        fill_value = -1
                    else:
                        fill_value = np.nan
                
                # 应用掩膜
                # data 的形状可能是 (lat, lon) 或 (events, lat, lon)
                # mask_2d 的形状是 (lat, lon)
                
                if len(shape) == 2:
                    # (lat, lon)
                    if np.ma.is_masked(data):
                        data[mask_2d] = fill_value
                        data.mask[mask_2d] = True
                    else:
                        data[mask_2d] = fill_value
                        
                elif len(shape) == 3:
                     # (events, lat, lon)
                     if shape[-2:] == mask_2d.shape:
                         # 使用 numpy 广播赋值 (极快)
                         # data[:, mask] 会选择所有符合 mask 的列，赋值回原数组的相应位置
                         # 注意: fill_value 必须与 data 类型兼容
                         
                         if np.ma.is_masked(data):
                             # data[..., mask_2d] = fill_value
                             # 对于 masked array, ... 索引可能有些 trick，但通常可行
                             # data[:, mask_2d] = fill_value
                             # 还需要设置 mask
                             
                             # 由于 MaskedArray 的切片赋值比较复杂且慢
                             # 我们直接操作底层 data 和 mask
                             
                             d = data.data
                             m = data.mask
                             
                             # 广播赋值
                             d[:, mask_2d] = fill_value
                             m[:, mask_2d] = True
                             
                             # 重新封装 (其实直接修改引用的 d, m 即可生效?)
                             # data.mask = m
                             # 只要 d 和 m 是视图或引用即可。
                             # 但为了保险:
                             var[:] = data
                             
                         else:
                             # 纯 numpy array
                             data[:, mask_2d] = fill_value

                        
                # 写回数据
                var[:] = data
                
    print(f"处理完成! 已保存至 {OUTPUT_NC}")

if __name__ == "__main__":
    mask_nc_file()
