#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate drought boolean masks from GLEAM SMrz soil moisture data.

This script calculates the 10th percentile threshold for warm season 
(NH: May-Sep, SH: Nov-Mar) during 1981-2010 baseline period, then marks 
grid cells as drought when soil moisture falls below this threshold.

Usage:
    python generate_drought_bool.py --year 2020 --output_dir /path/to/output
    
Input: /data/GLEAM/SMrz_45years.nc (0.1° resolution, daily)
Output: Daily boolean NetCDF files (1 = drought, 0 = non-drought)

Author: Auto-generated
Date: 2026-01-23
"""

import numpy as np
import xarray as xr
import os
import argparse
from datetime import datetime
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')


def get_warm_season_mask(dates, lat):
    """
    Determine if each date is in warm season for a given latitude.
    
    Parameters
    ----------
    dates : array-like
        Array of datetime64 or pandas DatetimeIndex
    lat : float
        Latitude value (positive = NH, negative = SH)
    
    Returns
    -------
    mask : np.ndarray
        Boolean array, True if date is in warm season
    """
    months = dates.month if hasattr(dates, 'month') else np.array([d.month for d in dates])
    
    if lat >= 0:
        # Northern Hemisphere: May (5) - September (9)
        warm_mask = (months >= 5) & (months <= 9)
    else:
        # Southern Hemisphere: November (11) - March (3)
        warm_mask = (months >= 11) | (months <= 3)
    
    return warm_mask


def calculate_threshold_map(sm_data, time_coord, lat_coord, 
                            baseline_start=1981, baseline_end=2010,
                            percentile=10):
    """
    Calculate warm-season 10th percentile threshold for each grid cell.
    
    Parameters
    ----------
    sm_data : xr.DataArray
        Soil moisture data (time, lat, lon)
    time_coord : pd.DatetimeIndex
        Time coordinate
    lat_coord : np.ndarray
        Latitude coordinate array
    baseline_start : int
        Start year of baseline period
    baseline_end : int
        End year of baseline period
    percentile : float
        Percentile value for threshold (default 10)
    
    Returns
    -------
    threshold : np.ndarray
        2D array of threshold values (lat, lon)
    """
    print(f"Calculating {percentile}th percentile threshold for {baseline_start}-{baseline_end}...")
    
    # Get baseline period mask
    years = time_coord.year
    baseline_mask = (years >= baseline_start) & (years <= baseline_end)
    
    nlat, nlon = len(lat_coord), sm_data.shape[2]
    threshold = np.full((nlat, nlon), np.nan, dtype=np.float32)
    
    # Process each latitude band (for memory efficiency and hemisphere-specific warm season)
    for ilat, lat in enumerate(tqdm(lat_coord, desc="Computing thresholds by latitude")):
        # Get warm season mask for this latitude
        warm_mask = get_warm_season_mask(time_coord, lat)
        
        # Combine with baseline mask
        combined_mask = baseline_mask & warm_mask
        
        if combined_mask.sum() == 0:
            continue
        
        # Extract data for this latitude during baseline warm season
        lat_data = sm_data.isel(lat=ilat, time=combined_mask).values  # shape: (n_warm_days, nlon)
        
        # Calculate percentile along time axis, ignoring NaN
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            threshold[ilat, :] = np.nanpercentile(lat_data, percentile, axis=0)
    
    return threshold


def generate_drought_bool_for_year(sm_file, year, output_dir, threshold_map, 
                                   lat_coord, lon_coord, time_coord,
                                   warm_season_only=True):
    """
    Generate daily drought boolean masks for a specific year.
    
    Parameters
    ----------
    sm_file : str
        Path to soil moisture NetCDF file
    year : int
        Year to process
    output_dir : str
        Output directory for boolean NetCDF files
    threshold_map : np.ndarray
        2D threshold map (lat, lon)
    lat_coord : np.ndarray
        Latitude coordinate
    lon_coord : np.ndarray
        Longitude coordinate
    time_coord : pd.DatetimeIndex
        Full time coordinate
    warm_season_only : bool
        If True, only process warm season days
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Open dataset
    ds = xr.open_dataset(sm_file, chunks={'time': 50})
    
    # Get time indices for the target year
    years = time_coord.year
    year_mask = years == year
    year_indices = np.where(year_mask)[0]
    
    if len(year_indices) == 0:
        print(f"Warning: No data found for year {year}")
        return
    
    print(f"Processing year {year}: {len(year_indices)} days")
    
    # Create latitude-based warm season mask (2D: time x lat)
    nlat = len(lat_coord)
    
    for idx in tqdm(year_indices, desc=f"Year {year}"):
        current_date = time_coord[idx]
        day_of_year = current_date.dayofyear
        
        # Check if in warm season (need to check for each latitude)
        if warm_season_only:
            # For NH (lat >= 0): May-Sep (DOY ~121-273)
            # For SH (lat < 0): Nov-Mar (DOY ~305-365, 1-90)
            month = current_date.month
            
            # Skip if not in any warm season
            nh_warm = (month >= 5) and (month <= 9)
            sh_warm = (month >= 11) or (month <= 3)
            
            if not (nh_warm or sh_warm):
                continue
        
        # Load soil moisture for this day
        sm_day = ds['SMrz'].isel(time=idx).values  # shape: (lat, lon)
        
        # Create drought mask (1 = drought, 0 = non-drought)
        drought_bool = np.zeros_like(sm_day, dtype=np.int8)
        
        # Apply threshold
        valid_mask = ~np.isnan(sm_day) & ~np.isnan(threshold_map)
        drought_bool[valid_mask] = (sm_day[valid_mask] < threshold_map[valid_mask]).astype(np.int8)
        
        # Apply hemisphere-specific warm season filter
        for ilat, lat in enumerate(lat_coord):
            if lat >= 0:
                # NH: only mark drought in May-Sep
                if not ((month >= 5) and (month <= 9)):
                    drought_bool[ilat, :] = 0
            else:
                # SH: only mark drought in Nov-Mar
                if not ((month >= 11) or (month <= 3)):
                    drought_bool[ilat, :] = 0
        
        # Save to NetCDF
        output_file = os.path.join(output_dir, f"SMrz_bool_{day_of_year}.nc")
        
        # Create xarray DataArray
        da = xr.DataArray(
            drought_bool,
            dims=['lat', 'lon'],
            coords={'lat': lat_coord, 'lon': lon_coord},
            name='SMI',
            attrs={
                'long_name': 'Drought boolean mask (1=drought, 0=non-drought)',
                'units': '1',
                'threshold_percentile': 10,
                'baseline_period': '1981-2010',
                'source': 'GLEAM SMrz',
                'date': str(current_date.date())
            }
        )
        
        # Save
        da.to_netcdf(output_file)
    
    ds.close()
    print(f"Completed processing year {year}")


def main():
    parser = argparse.ArgumentParser(
        description='Generate drought boolean masks from GLEAM SMrz data'
    )
    parser.add_argument('--input', type=str, 
                        default='/data/GLEAM/SMrz_45years.nc',
                        help='Input soil moisture NetCDF file')
    parser.add_argument('--year', type=int, required=True,
                        help='Year to process')
    parser.add_argument('--output_dir', type=str, 
                        default='/data/GLEAM/sm_bool',
                        help='Output directory for boolean masks')
    parser.add_argument('--threshold_file', type=str, default=None,
                        help='Pre-computed threshold file (optional)')
    parser.add_argument('--save_threshold', action='store_true',
                        help='Save computed threshold to file')
    parser.add_argument('--baseline_start', type=int, default=1981,
                        help='Baseline period start year')
    parser.add_argument('--baseline_end', type=int, default=2010,
                        help='Baseline period end year')
    parser.add_argument('--percentile', type=float, default=10,
                        help='Percentile for drought threshold')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Drought Boolean Mask Generator")
    print("=" * 60)
    print(f"Input file: {args.input}")
    print(f"Year to process: {args.year}")
    print(f"Output directory: {args.output_dir}")
    print(f"Baseline period: {args.baseline_start}-{args.baseline_end}")
    print(f"Threshold percentile: {args.percentile}")
    print("=" * 60)
    
    # Load dataset metadata
    print("Loading dataset metadata...")
    ds = xr.open_dataset(args.input)
    
    # Get coordinates
    lat_coord = ds['lat'].values
    lon_coord = ds['lon'].values
    
    # Convert time to datetime
    time_coord = ds.indexes['time']
    if not hasattr(time_coord, 'year'):
        # Convert to pandas DatetimeIndex if needed
        import pandas as pd
        time_coord = pd.to_datetime(time_coord)
    
    print(f"Data shape: {ds['SMrz'].shape}")
    print(f"Lat range: {lat_coord.min():.2f} to {lat_coord.max():.2f}")
    print(f"Lon range: {lon_coord.min():.2f} to {lon_coord.max():.2f}")
    print(f"Time range: {time_coord[0]} to {time_coord[-1]}")
    
    # Load or calculate threshold
    threshold_dir = os.path.dirname(args.output_dir)
    threshold_file = args.threshold_file or os.path.join(
        threshold_dir, f'drought_threshold_p{int(args.percentile)}.npy'
    )
    
    if os.path.exists(threshold_file) and args.threshold_file:
        print(f"Loading pre-computed threshold from {threshold_file}")
        threshold_map = np.load(threshold_file)
    else:
        # Calculate threshold
        threshold_map = calculate_threshold_map(
            ds['SMrz'], time_coord, lat_coord,
            baseline_start=args.baseline_start,
            baseline_end=args.baseline_end,
            percentile=args.percentile
        )
        
        if args.save_threshold:
            os.makedirs(os.path.dirname(threshold_file), exist_ok=True)
            np.save(threshold_file, threshold_map)
            print(f"Saved threshold to {threshold_file}")
    
    ds.close()
    
    # Generate boolean masks for the specified year
    generate_drought_bool_for_year(
        args.input, args.year, args.output_dir,
        threshold_map, lat_coord, lon_coord, time_coord,
        warm_season_only=True
    )
    
    print("\nDone!")


if __name__ == '__main__':
    main()
