#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将SMrz骤旱RECO响应NC文件转换为空间分布TIF文件
数据源: reco_response_events_global_v10.nc
"""
import numpy as np
import pandas as pd
import netCDF4 as nc
from osgeo import gdal, osr
import os

# ================= 配置 =================
NC_FILE = '/home/xulc/flash_drought/process/RECO-draught-analysis/results/reco_response_events_global_v10.nc'
OUTPUT_DIR = '/home/xulc/flash_drought/process/RECO-draught-analysis/results/spatial_tif'
TARGET_VARS = ['reco_min', 'reco_trend', 't_min', 't_response', 't_impact', 't_recover', 'recovery_rate']

os.makedirs(OUTPUT_DIR, exist_ok=True)

def read_nc_events(nc_file):
    print(f"正在读取: {nc_file}")
    ds = nc.Dataset(nc_file, 'r')
    
    data = {
        'lat': ds.variables['lat'][:].data,
        'lon': ds.variables['lon'][:].data,
        'response_detected': ds.variables['response_detected'][:].data,
    }
    for var in TARGET_VARS:
        if var in ds.variables:
            data[var] = ds.variables[var][:].data
    
    ds.close()
    print(f"总事件数: {len(data['lat'])}")
    return data

def filter_valid_events(data):
    valid_mask = data['response_detected'] == 1
    filtered = {key: values[valid_mask] for key, values in data.items()}
    print(f"有效事件数: {np.sum(valid_mask)}")
    return filtered

def aggregate_by_pixel(data, target_vars):
    print("聚合数据...")
    df_dict = {'lat': data['lat'], 'lon': data['lon']}
    for var in target_vars:
        if var in data:
            df_dict[var] = data[var]
    
    df = pd.DataFrame(df_dict)
    agg_df = df.groupby(['lat', 'lon'], as_index=False).mean()
    print(f"唯一像元数: {len(agg_df)}")
    return {col: agg_df[col].values for col in agg_df.columns}

def create_geotiff(lat, lon, values, output_file, var_name, resolution=0.1):
    lat_min, lat_max = np.floor(np.nanmin(lat)), np.ceil(np.nanmax(lat))
    lon_min, lon_max = np.floor(np.nanmin(lon)), np.ceil(np.nanmax(lon))
    
    n_rows = int((lat_max - lat_min) / resolution)
    n_cols = int((lon_max - lon_min) / resolution)
    raster = np.full((n_rows, n_cols), np.nan, dtype=np.float32)
    
    rows = ((lat_max - lat) / resolution).astype(int)
    cols = ((lon - lon_min) / resolution).astype(int)
    valid_mask = (rows >= 0) & (rows < n_rows) & (cols >= 0) & (cols < n_cols) & ~np.isnan(values)
    raster[rows[valid_mask], cols[valid_mask]] = values[valid_mask]
    
    driver = gdal.GetDriverByName('GTiff')
    out_ds = driver.Create(output_file, n_cols, n_rows, 1, gdal.GDT_Float32, options=['COMPRESS=LZW'])
    out_ds.SetGeoTransform([lon_min, resolution, 0, lat_max, 0, -resolution])
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    out_ds.SetProjection(srs.ExportToWkt())
    band = out_ds.GetRasterBand(1)
    band.WriteArray(raster)
    band.SetNoDataValue(np.nan)
    band.ComputeStatistics(False)
    band.FlushCache()
    out_ds = None
    print(f"  保存: {output_file} ({np.sum(~np.isnan(raster))} 有效像元)")

def main():
    data = read_nc_events(NC_FILE)
    valid_data = filter_valid_events(data)
    aggregated = aggregate_by_pixel(valid_data, TARGET_VARS)
    
    print("\n生成 TIF 文件...")
    for var in TARGET_VARS:
        if var in aggregated:
            output_file = os.path.join(OUTPUT_DIR, f'{var}_mean.tif')
            create_geotiff(aggregated['lat'], aggregated['lon'], aggregated[var], output_file, var)
    
    print(f"\n✅ 完成! 输出目录: {OUTPUT_DIR}")

if __name__ == '__main__':
    main()
