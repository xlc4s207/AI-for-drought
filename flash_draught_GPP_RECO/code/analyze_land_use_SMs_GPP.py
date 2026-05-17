#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Land Use Analysis for Flash Drought GPP Response (SMs)
Based on MCD12C1 Majority Land Cover Type 1
"""

import os
import numpy as np
import pandas as pd
import netCDF4 as nc
from osgeo import gdal

# --- Configuration ---
NC_FILE = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO/SMs_GPP_results/gpp_response_SMs_events_global_v10.nc'
LC_FILE = '/home/xulc/flash_drought/land_use/MCD12C1_LC_Type1_2010_11km.tif'
OUTPUT_DIR = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO/SMs_GPP_results/land_use_analysis'

IGBP_CLASSES = {
    1: 'Evergreen Needleleaf Forest',
    2: 'Evergreen Broadleaf Forest',
    3: 'Deciduous Needleleaf Forest',
    4: 'Deciduous Broadleaf Forest',
    5: 'Mixed Forests',
    6: 'Closed Shrublands',
    7: 'Open Shrublands',
    8: 'Woody Savannas',
    9: 'Savannas',
    10: 'Grasslands',
    11: 'Permanent Wetlands',
    12: 'Croplands'
}

VARIABLES_TO_ANALYZE = [
    'gpp_min', 'gpp_mean', 'gpp_trend', 
    't_response', 't_min', 't_impact', 't_recover', 
    'amp_max', 'recovery_rate',
    'response_detected'
]

def create_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
        
def load_land_use_data():
    print("Loading Land Use data...")
    ds = gdal.Open(LC_FILE)
    band = ds.GetRasterBand(1)
    lc_data = band.ReadAsArray()
    gt = ds.GetGeoTransform()
    return lc_data, gt

def map_events_to_lc(nc_path, lc_data, gt):
    print("Mapping events to Land Use classes...")
    with nc.Dataset(nc_path, 'r') as ds:
        lats = ds.variables['lat'][:]
        lons = ds.variables['lon'][:]
        
        origin_x = gt[0]
        origin_y = gt[3]
        pixel_width = gt[1]
        pixel_height = gt[5]
        
        cols = ((lons - origin_x) / pixel_width).astype(int)
        rows = ((lats - origin_y) / pixel_height).astype(int)
        
        rows = np.clip(rows, 0, lc_data.shape[0] - 1)
        cols = np.clip(cols, 0, lc_data.shape[1] - 1)
        
        event_lc_classes = lc_data[rows, cols]
        
        return event_lc_classes, rows, cols

def analyze_and_save():
    create_output_dir()
    
    lc_data, gt = load_land_use_data()
    event_lc_classes, rows, cols = map_events_to_lc(NC_FILE, lc_data, gt)
    
    print("Reading variables from NC file...")
    data = {}
    with nc.Dataset(NC_FILE, 'r') as ds:
        for var in VARIABLES_TO_ANALYZE:
            if var in ds.variables:
                data[var] = ds.variables[var][:]
            
    df = pd.DataFrame(data)
    df['LC_Class'] = event_lc_classes
    df['row'] = rows
    df['col'] = cols
    
    grid_shape = lc_data.shape
    stats_list = []
    
    print("Analyzing each class...")
    for class_id, class_name in IGBP_CLASSES.items():
        print(f"  Processing Class {class_id}: {class_name}")
        
        class_events = df[df['LC_Class'] == class_id]
        
        if len(class_events) == 0:
            print(f"    No events found for {class_name}")
            continue
            
        stats = {'Class_ID': class_id, 'Class_Name': class_name, 'Event_Count': len(class_events)}
        
        valid_events = class_events[class_events['response_detected'] == 1]
        stats['Valid_Count'] = len(valid_events)
        stats['Valid_Ratio'] = len(valid_events) / len(class_events)
        
        for var in VARIABLES_TO_ANALYZE:
            if var == 'response_detected' or var not in data: continue
            
            valid_vals = class_events[var].dropna()
            
            stats[f'{var}_mean'] = valid_vals.mean()
            stats[f'{var}_std'] = valid_vals.std()
            stats[f'{var}_min'] = valid_vals.min()
            stats[f'{var}_max'] = valid_vals.max()
            
            if var in ['t_response', 't_impact', 't_recover', 'amp_max']:
                 valid_subset_vals = valid_events[var].dropna()
                 stats[f'{var}_valid_mean'] = valid_subset_vals.mean()

        stats_list.append(stats)
        
        # TIF Generation
        maps_dir = os.path.join(OUTPUT_DIR, 'maps')
        os.makedirs(maps_dir, exist_ok=True)
        
        map_vars = ['gpp_min', 'gpp_trend', 't_response', 't_min', 't_impact', 't_recover', 'recovery_rate']
        
        pixel_groups = class_events.groupby(['row', 'col'])
        
        for var in map_vars:
            if var not in data: continue
            pixel_means = pixel_groups[var].mean()
            
            out_grid = np.full(grid_shape, np.nan, dtype=np.float32)
            
            r_idx = pixel_means.index.get_level_values('row').values
            c_idx = pixel_means.index.get_level_values('col').values
            out_grid[r_idx, c_idx] = pixel_means.values
            
            out_name = f'Class_{class_id}_{var}_mean.tif'
            save_tif(os.path.join(maps_dir, out_name), out_grid, gt, ds_ref=gdal.Open(LC_FILE))

        pixel_counts = pixel_groups.size()
        count_grid = np.full(grid_shape, 0, dtype=np.int32)
        r_idx = pixel_counts.index.get_level_values('row').values
        c_idx = pixel_counts.index.get_level_values('col').values
        count_grid[r_idx, c_idx] = pixel_counts.values
        
        save_tif(os.path.join(maps_dir, f'Class_{class_id}_Event_Count.tif'), count_grid, gt, ds_ref=gdal.Open(LC_FILE), dtype=gdal.GDT_Int32)

    stats_df = pd.DataFrame(stats_list)
    stats_csv = os.path.join(OUTPUT_DIR, 'Land_Use_Statistics.csv')
    stats_df.to_csv(stats_csv, index=False)
    print(f"Statistics saved to {stats_csv}")

def save_tif(path, data, gt, ds_ref, dtype=gdal.GDT_Float32):
    driver = gdal.GetDriverByName('GTiff')
    rows, cols = data.shape
    out_ds = driver.Create(path, cols, rows, 1, dtype, options=['COMPRESS=LZW'])
    
    out_ds.SetGeoTransform(gt)
    out_ds.SetProjection(ds_ref.GetProjection())
    
    band = out_ds.GetRasterBand(1)
    if dtype == gdal.GDT_Float32:
        band.SetNoDataValue(np.nan)
    else:
        band.SetNoDataValue(0)
        
    band.WriteArray(data)
    band.FlushCache()
    out_ds = None 

if __name__ == '__main__':
    analyze_and_save()
