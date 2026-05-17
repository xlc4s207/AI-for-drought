# -*- coding: utf-8 -*-
"""
数据读取模块
逐像元读取并拼接45年时序数据
"""

import os
import numpy as np
import netCDF4 as nc
from config import NC_DATA_DIR, NC_FILE_TEMPLATE, YEARS


def get_nc_file_path(year):
    """获取指定年份的NC文件路径"""
    filename = NC_FILE_TEMPLATE.format(year=year)
    return os.path.join(NC_DATA_DIR, filename)


def get_coordinate_arrays():
    """获取坐标数组(lat, lon)，从第一个NC文件读取"""
    first_file = get_nc_file_path(YEARS[0])
    with nc.Dataset(first_file, 'r') as ds:
        lat = ds.variables['lat'][:]
        lon = ds.variables['lon'][:]
    return lat, lon


def lat_lon_to_index(lat_value, lon_value, lat_array, lon_array):
    """将经纬度值转换为数组索引"""
    lat_idx = np.argmin(np.abs(lat_array - lat_value))
    lon_idx = np.argmin(np.abs(lon_array - lon_value))
    return lat_idx, lon_idx


def index_to_lat_lon(lat_idx, lon_idx, lat_array, lon_array):
    """将数组索引转换为经纬度值"""
    return lat_array[lat_idx], lon_array[lon_idx]


def read_pixel_timeseries(lat_idx, lon_idx, years=None):
    """
    读取单个像元所有年份的时序数据
    
    Parameters:
    -----------
    lat_idx : int
        纬度索引
    lon_idx : int
        经度索引
    years : list, optional
        年份列表，默认为所有年份
        
    Returns:
    --------
    data : numpy.ndarray
        时序数据数组
    dates : list
        日期信息列表 [(year, doy), ...]
    is_valid : bool
        是否为有效像元(非全masked)
    """
    if years is None:
        years = YEARS
    
    all_data = []
    all_dates = []
    
    for year in years:
        nc_path = get_nc_file_path(year)
        
        with nc.Dataset(nc_path, 'r') as ds:
            # 读取该像元该年所有天的数据
            pixel_data = ds.variables['SMrz'][:, lat_idx, lon_idx]
            
            # 转换为numpy数组
            if hasattr(pixel_data, 'mask'):
                # masked array
                data = np.ma.filled(pixel_data, np.nan)
            else:
                data = np.array(pixel_data)
            
            all_data.extend(data)
            
            # 记录日期信息
            n_days = len(data)
            for doy in range(1, n_days + 1):
                all_dates.append((year, doy))
    
    data_array = np.array(all_data)
    
    # 检查是否为有效像元
    is_valid = not np.all(np.isnan(data_array))
    
    return data_array, all_dates, is_valid


def check_pixel_validity(lat_idx, lon_idx):
    """
    快速检查像元是否有效(只读取第一年第一天)
    
    Returns:
    --------
    bool : 是否有效
    """
    nc_path = get_nc_file_path(YEARS[0])
    
    with nc.Dataset(nc_path, 'r') as ds:
        value = ds.variables['SMrz'][0, lat_idx, lon_idx]
        if hasattr(value, 'mask') and value.mask:
            return False
        if np.isnan(value):
            return False
    return True


def get_index_ranges_for_region(lat_range, lon_range):
    """
    获取指定区域的索引范围
    
    Parameters:
    -----------
    lat_range : tuple
        (lat_min, lat_max)
    lon_range : tuple
        (lon_min, lon_max)
        
    Returns:
    --------
    lat_indices : range
        纬度索引范围
    lon_indices : range
        经度索引范围
    """
    lat_array, lon_array = get_coordinate_arrays()
    
    lat_min_idx, _ = lat_lon_to_index(lat_range[0], lon_range[0], lat_array, lon_array)
    lat_max_idx, _ = lat_lon_to_index(lat_range[1], lon_range[1], lat_array, lon_array)
    _, lon_min_idx = lat_lon_to_index(lat_range[0], lon_range[0], lat_array, lon_array)
    _, lon_max_idx = lat_lon_to_index(lat_range[0], lon_range[1], lat_array, lon_array)
    
    # 确保顺序正确
    if lat_min_idx > lat_max_idx:
        lat_min_idx, lat_max_idx = lat_max_idx, lat_min_idx
    if lon_min_idx > lon_max_idx:
        lon_min_idx, lon_max_idx = lon_max_idx, lon_min_idx
    
    return range(lat_min_idx, lat_max_idx + 1), range(lon_min_idx, lon_max_idx + 1)
