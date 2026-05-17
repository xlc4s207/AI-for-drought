#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch processing script to generate drought boolean masks for multiple years.

This is a memory-efficient version that processes data in chunks and 
supports parallel execution across years.

Usage:
    # Process single year
    python generate_drought_bool_batch.py --year 2020
    
    # Process year range
    python generate_drought_bool_batch.py --start_year 1981 --end_year 2024
    
    # Calculate threshold only (save for later use)
    python generate_drought_bool_batch.py --calc_threshold_only

Author: Auto-generated
Date: 2026-01-23
"""

import numpy as np
import xarray as xr
import os
import argparse
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
#                           CONFIGURATION
# ============================================================================

# Input file path
INPUT_FILE = '/data/GLEAM/SMrz_45years.nc'

# Output directories
OUTPUT_BASE = '/data/GLEAM/drought_3D'
BOOL_OUTPUT_DIR = os.path.join(OUTPUT_BASE, 'sm_bool')
THRESHOLD_DIR = os.path.join(OUTPUT_BASE, 'threshold')

# Baseline period for percentile calculation
BASELINE_START = 1981
BASELINE_END = 2010

# Drought threshold percentile (10 = D2 severe drought in USDM)
PERCENTILE = 10

# Warm season definition (months)
NH_WARM_MONTHS = [5, 6, 7, 8, 9]      # May - September
SH_WARM_MONTHS = [11, 12, 1, 2, 3]    # November - March

# ============================================================================
#                           HELPER FUNCTIONS
# ============================================================================

def get_warm_season_indices(time_coord, lat_value):
    """
    Get indices of warm season days for a given latitude.
    
    NH (lat >= 0): May-September
    SH (lat < 0): November-March
    """
    months = time_coord.month
    
    if lat_value >= 0:
        warm_mask = np.isin(months, NH_WARM_MONTHS)
    else:
        warm_mask = np.isin(months, SH_WARM_MONTHS)
    
    return warm_mask


def calculate_threshold_chunked(input_file, baseline_start, baseline_end, 
                                 percentile, chunk_size=100):
    """
    Calculate threshold map in memory-efficient chunks.
    
    Parameters
    ----------
    input_file : str
        Path to input NetCDF file
    baseline_start, baseline_end : int
        Baseline period years
    percentile : float
        Percentile for threshold
    chunk_size : int
        Number of latitudes to process at once
    
    Returns
    -------
    threshold : np.ndarray
        2D threshold map (lat, lon)
    lat_coord, lon_coord : np.ndarray
        Coordinate arrays
    """
    print(f"\n{'='*60}")
    print(f"Calculating {percentile}th percentile threshold")
    print(f"Baseline period: {baseline_start}-{baseline_end}")
    print(f"{'='*60}\n")
    
    # Open dataset
    ds = xr.open_dataset(input_file)
    
    lat_coord = ds['lat'].values
    lon_coord = ds['lon'].values
    time_coord = ds.indexes['time']
    
    # Convert time if needed
    import pandas as pd
    if not hasattr(time_coord, 'year'):
        time_coord = pd.to_datetime(time_coord)
    
    nlat, nlon = len(lat_coord), len(lon_coord)
    
    # Get baseline period time mask
    years = np.array([t.year for t in time_coord])
    baseline_time_mask = (years >= baseline_start) & (years <= baseline_end)
    baseline_indices = np.where(baseline_time_mask)[0]
    
    print(f"Data dimensions: {nlat} lat x {nlon} lon")
    print(f"Baseline days: {len(baseline_indices)}")
    
    # Initialize output
    threshold = np.full((nlat, nlon), np.nan, dtype=np.float32)
    
    # Process in latitude chunks
    n_chunks = int(np.ceil(nlat / chunk_size))
    
    for chunk_idx in range(n_chunks):
        lat_start = chunk_idx * chunk_size
        lat_end = min((chunk_idx + 1) * chunk_size, nlat)
        
        print(f"Processing latitudes {lat_start}-{lat_end} ({chunk_idx+1}/{n_chunks})...")
        
        # Load chunk of data for baseline period
        chunk_data = ds['SMrz'].isel(
            time=baseline_indices,
            lat=slice(lat_start, lat_end)
        ).values  # shape: (n_baseline_days, chunk_lats, nlon)
        
        chunk_lats = lat_coord[lat_start:lat_end]
        baseline_times = time_coord[baseline_time_mask]
        
        # Process each latitude in chunk
        for i, lat_val in enumerate(chunk_lats):
            ilat_global = lat_start + i
            
            # Get warm season mask for this latitude
            warm_mask = get_warm_season_indices(baseline_times, lat_val)
            
            if warm_mask.sum() == 0:
                continue
            
            # Extract warm season data for this latitude
            lat_warm_data = chunk_data[warm_mask, i, :]  # shape: (n_warm_days, nlon)
            
            # Calculate percentile
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                threshold[ilat_global, :] = np.nanpercentile(lat_warm_data, percentile, axis=0)
    
    ds.close()
    
    # Print statistics
    valid_count = np.sum(~np.isnan(threshold))
    print(f"\nThreshold calculation complete!")
    print(f"Valid grid cells: {valid_count:,} / {nlat * nlon:,}")
    print(f"Threshold range: {np.nanmin(threshold):.4f} - {np.nanmax(threshold):.4f}")
    
    return threshold, lat_coord, lon_coord


def save_threshold(threshold, lat_coord, lon_coord, output_dir, percentile):
    """Save threshold map to NetCDF and numpy files."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Save as numpy
    np_file = os.path.join(output_dir, f'threshold_p{int(percentile)}.npy')
    np.save(np_file, threshold)
    print(f"Saved threshold to {np_file}")
    
    # Save as NetCDF
    nc_file = os.path.join(output_dir, f'threshold_p{int(percentile)}.nc')
    da = xr.DataArray(
        threshold,
        dims=['lat', 'lon'],
        coords={'lat': lat_coord, 'lon': lon_coord},
        name='threshold',
        attrs={
            'long_name': f'{percentile}th percentile soil moisture threshold',
            'units': 'm3.m-3',
            'baseline_period': f'{BASELINE_START}-{BASELINE_END}',
            'percentile': percentile,
            'description': 'Warm season threshold (NH: May-Sep, SH: Nov-Mar)'
        }
    )
    da.to_netcdf(nc_file)
    print(f"Saved threshold to {nc_file}")
    
    return np_file, nc_file


def load_threshold(threshold_dir, percentile):
    """Load pre-computed threshold map."""
    np_file = os.path.join(threshold_dir, f'threshold_p{int(percentile)}.npy')
    if os.path.exists(np_file):
        print(f"Loading threshold from {np_file}")
        return np.load(np_file)
    else:
        raise FileNotFoundError(f"Threshold file not found: {np_file}")


def generate_bool_for_year(input_file, year, threshold, output_dir,
                            lat_coord, lon_coord):
    """
    Generate drought boolean masks for one year.
    
    Output: One NetCDF per day, containing boolean mask (1=drought, 0=non-drought)
    """
    import pandas as pd
    
    year_output_dir = os.path.join(output_dir, str(year))
    os.makedirs(year_output_dir, exist_ok=True)
    
    print(f"\nProcessing year {year}...")
    
    # Open dataset
    ds = xr.open_dataset(input_file)
    time_coord = ds.indexes['time']
    if not hasattr(time_coord, 'year'):
        time_coord = pd.to_datetime(time_coord)
    
    # Get indices for this year
    years = np.array([t.year for t in time_coord])
    year_mask = years == year
    year_indices = np.where(year_mask)[0]
    
    if len(year_indices) == 0:
        print(f"No data for year {year}")
        ds.close()
        return
    
    print(f"Found {len(year_indices)} days for year {year}")
    
    nlat, nlon = len(lat_coord), len(lon_coord)
    days_processed = 0
    
    for idx in year_indices:
        current_time = time_coord[idx]
        month = current_time.month
        day_of_year = current_time.dayofyear
        
        # Load soil moisture for this day
        sm_day = ds['SMrz'].isel(time=idx).values
        
        # Create drought mask
        drought_bool = np.zeros((nlat, nlon), dtype=np.int8)
        
        # Apply threshold where valid
        valid = ~np.isnan(sm_day) & ~np.isnan(threshold)
        drought_bool[valid] = (sm_day[valid] < threshold[valid]).astype(np.int8)
        
        # Apply hemisphere-specific warm season mask
        for ilat, lat_val in enumerate(lat_coord):
            if lat_val >= 0:
                # NH: only May-September
                if month not in NH_WARM_MONTHS:
                    drought_bool[ilat, :] = 0
            else:
                # SH: only November-March
                if month not in SH_WARM_MONTHS:
                    drought_bool[ilat, :] = 0
        
        # Save output
        output_file = os.path.join(year_output_dir, f'SMrz_bool_{day_of_year}.nc')
        
        da = xr.DataArray(
            drought_bool,
            dims=['lat', 'lon'],
            coords={'lat': lat_coord, 'lon': lon_coord},
            name='SMI',
            attrs={
                'long_name': 'Drought boolean mask',
                'units': '1',
                'date': str(current_time.date()),
                'day_of_year': int(day_of_year)
            }
        )
        da.to_netcdf(output_file)
        days_processed += 1
    
    ds.close()
    print(f"Year {year}: saved {days_processed} daily files to {year_output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description='Generate drought boolean masks from GLEAM SMrz'
    )
    parser.add_argument('--input', type=str, default=INPUT_FILE,
                        help='Input soil moisture file')
    parser.add_argument('--output_dir', type=str, default=BOOL_OUTPUT_DIR,
                        help='Output directory for boolean masks')
    parser.add_argument('--threshold_dir', type=str, default=THRESHOLD_DIR,
                        help='Directory for threshold files')
    parser.add_argument('--year', type=int, default=None,
                        help='Single year to process')
    parser.add_argument('--start_year', type=int, default=None,
                        help='Start year for range processing')
    parser.add_argument('--end_year', type=int, default=None,
                        help='End year for range processing')
    parser.add_argument('--calc_threshold_only', action='store_true',
                        help='Only calculate and save threshold')
    parser.add_argument('--recalc_threshold', action='store_true',
                        help='Recalculate threshold even if exists')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Drought Boolean Mask Generator (Batch)")
    print("=" * 60)
    print(f"Input file: {args.input}")
    print(f"Output directory: {args.output_dir}")
    print(f"Threshold directory: {args.threshold_dir}")
    print("=" * 60)
    
    # Create directories
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.threshold_dir, exist_ok=True)
    
    # Calculate or load threshold
    threshold_file = os.path.join(args.threshold_dir, f'threshold_p{PERCENTILE}.npy')
    
    if os.path.exists(threshold_file) and not args.recalc_threshold:
        threshold = load_threshold(args.threshold_dir, PERCENTILE)
        # Load coordinates
        ds = xr.open_dataset(args.input)
        lat_coord = ds['lat'].values
        lon_coord = ds['lon'].values
        ds.close()
    else:
        threshold, lat_coord, lon_coord = calculate_threshold_chunked(
            args.input, BASELINE_START, BASELINE_END, PERCENTILE
        )
        save_threshold(threshold, lat_coord, lon_coord, args.threshold_dir, PERCENTILE)
    
    if args.calc_threshold_only:
        print("\nThreshold calculation complete. Exiting.")
        return
    
    # Determine years to process
    if args.year:
        years_to_process = [args.year]
    elif args.start_year and args.end_year:
        years_to_process = list(range(args.start_year, args.end_year + 1))
    else:
        print("Error: Specify --year or --start_year/--end_year")
        return
    
    print(f"\nYears to process: {years_to_process}")
    
    # Process each year
    for year in years_to_process:
        generate_bool_for_year(
            args.input, year, threshold, args.output_dir,
            lat_coord, lon_coord
        )
    
    print("\n" + "=" * 60)
    print("All processing complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
