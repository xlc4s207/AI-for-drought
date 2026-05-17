"""
将骤旱事件NC文件转换为空间分布TIF文件
对每个像元上的有效事件进行时间平均
优化版：使用 Pandas 向量化操作提升性能
"""
import numpy as np
import pandas as pd
import netCDF4 as nc
from osgeo import gdal, osr
from tqdm import tqdm
import os
import time


def read_nc_events(nc_file):
    """读取NC文件中的事件数据"""
    print("正在读取 NC 文件...")
    ds = nc.Dataset(nc_file, 'r')
    
    # 读取坐标和属性数据
    data = {
        'lat': ds.variables['lat'][:].data,
        'lon': ds.variables['lon'][:].data,
        'response_detected': ds.variables['response_detected'][:].data,
        'gpp_min': ds.variables['gpp_min'][:].data,
        'gpp_trend': ds.variables['gpp_trend'][:].data,
        't_min': ds.variables['t_min'][:].data,
        't_response': ds.variables['t_response'][:].data,
        't_impact': ds.variables['t_impact'][:].data,
        't_recover': ds.variables['t_recover'][:].data,
        'recovery_rate': ds.variables['recovery_rate'][:].data,
    }
    
    ds.close()
    print(f"总事件数: {len(data['lat'])}")
    
    return data


def filter_valid_events(data):
    """筛选有效事件（response_detected == 1）"""
    print("正在筛选有效事件...")
    valid_mask = data['response_detected'] == 1
    
    filtered_data = {}
    for key, values in data.items():
        filtered_data[key] = values[valid_mask]
    
    print(f"有效事件数: {np.sum(valid_mask)} / {len(valid_mask)} ({100*np.sum(valid_mask)/len(valid_mask):.2f}%)")
    
    return filtered_data


def aggregate_by_pixel(data, target_vars):
    """按像元聚合事件数据 - 使用 Pandas 向量化操作"""
    print("正在使用 Pandas 高速聚合数据...")
    start_time = time.time()
    
    # 构建 DataFrame（只包含坐标和目标变量）
    df_dict = {
        'lat': data['lat'],
        'lon': data['lon']
    }
    for var in target_vars:
        df_dict[var] = data[var]
    
    df = pd.DataFrame(df_dict)
    
    print(f"  事件总数: {len(df)}")
    
    # 使用 groupby 进行高速聚合（自动忽略 NaN）
    # 这一行替代了原来的嵌套循环，性能提升 100-1000 倍
    agg_df = df.groupby(['lat', 'lon'], as_index=False).mean()
    
    print(f"  唯一像元数: {len(agg_df)}")
    print(f"  聚合耗时: {time.time() - start_time:.2f} 秒")
    
    # 转换为字典格式
    aggregated = {col: agg_df[col].values for col in agg_df.columns}
    
    return aggregated


def create_geotiff(lat, lon, values, output_file, var_name, resolution=0.1):
    """创建 GeoTIFF 文件 - 使用向量化索引"""
    start_time = time.time()
    
    # 确定栅格范围和大小
    lat_min, lat_max = np.floor(np.nanmin(lat)), np.ceil(np.nanmax(lat))
    lon_min, lon_max = np.floor(np.nanmin(lon)), np.ceil(np.nanmax(lon))
    
    n_rows = int((lat_max - lat_min) / resolution)
    n_cols = int((lon_max - lon_min) / resolution)
    
    # 创建空白栅格
    raster = np.full((n_rows, n_cols), np.nan, dtype=np.float32)
    
    # 向量化计算所有点的行列索引
    rows = ((lat_max - lat) / resolution).astype(int)
    cols = ((lon - lon_min) / resolution).astype(int)
    
    # 过滤掉越界和 NaN 值的点
    valid_mask = (
        (rows >= 0) & (rows < n_rows) & 
        (cols >= 0) & (cols < n_cols) & 
        ~np.isnan(values)
    )
    
    # 使用 NumPy 花式索引直接填充（Pandas已经聚合过，不会有重复坐标）
    raster[rows[valid_mask], cols[valid_mask]] = values[valid_mask]
    
    # 创建 GeoTIFF
    driver = gdal.GetDriverByName('GTiff')
    out_ds = driver.Create(
        output_file,
        n_cols,
        n_rows,
        1,
        gdal.GDT_Float32,
        options=['COMPRESS=LZW']
    )
    
    # 设置地理转换参数
    geotransform = [
        lon_min,      # 左上角 X 坐标
        resolution,   # 像元宽度
        0,            # 旋转（通常为0）
        lat_max,      # 左上角 Y 坐标
        0,            # 旋转（通常为0）
        -resolution   # 像元高度（负值，因为Y轴向下）
    ]
    out_ds.SetGeoTransform(geotransform)
    
    # 设置投影（WGS84）
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    out_ds.SetProjection(srs.ExportToWkt())
    
    # 写入数据
    band = out_ds.GetRasterBand(1)
    band.WriteArray(raster)
    band.SetNoDataValue(np.nan)
    band.SetDescription(var_name)
    
    # 计算统计信息
    band.ComputeStatistics(False)
    
    # 清理
    band.FlushCache()
    out_ds.FlushCache()
    band = None
    out_ds = None
    
    print(f"  保存: {output_file}")
    print(f"  栅格大小: {n_rows} x {n_cols}")
    print(f"  有效像元数: {np.sum(~np.isnan(raster))}")
    print(f"  TIF生成耗时: {time.time() - start_time:.2f} 秒")


def main():
    # 文件路径
    nc_file = r'/home/xulc/flash_drought/process/GPP-draught-analysis/results/gpp_response_events_global_v10.nc'
    output_dir = r'/home/xulc/flash_drought/process/GPP-draught-analysis/results/tif'
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 目标变量
    target_vars = [
        'gpp_min',
        'gpp_trend',
        't_min',
        't_response',
        't_impact',
        't_recover',
        'recovery_rate'
    ]
    
    # 读取数据
    data = read_nc_events(nc_file)
    
    # 筛选有效事件
    valid_data = filter_valid_events(data)
    
    # 按像元聚合
    aggregated = aggregate_by_pixel(valid_data, target_vars)
    
    # 生成 TIF 文件
    print("\n正在生成 TIF 文件...")
    for var in target_vars:
        print(f"\n处理变量: {var}")
        output_file = os.path.join(output_dir, f'{var}_mean.tif')
        
        create_geotiff(
            aggregated['lat'],
            aggregated['lon'],
            aggregated[var],
            output_file,
            var
        )
    
    print("\n✅ 所有 TIF 文件生成完成！")


if __name__ == '__main__':
    main()
