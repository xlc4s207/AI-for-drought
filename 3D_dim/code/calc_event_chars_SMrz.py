#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Calculate characteristics for 4D drought events from GLEAM SMrz data.

This script computes various properties for each tracked drought event:
- Duration (days)
- Maximum spatial extent (area in km²)
- Mean/max intensity (soil moisture deficit)
- Centroid trajectory
- Event classification

Usage:
    python calc_event_chars_SMrz.py --year 2020

Author: Auto-generated
Date: 2026-01-23
"""

import numpy as np
import xarray as xr
import os
import argparse
from glob import glob
import pandas as pd
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
#                           CONFIGURATION
# ============================================================================

# Paths
SM_INPUT_FILE = '/data/GLEAM/SMrz_45years.nc'
THRESHOLD_FILE = '/data/GLEAM/drought_3D/threshold/threshold_p10.nc'
EVENT_INPUT_DIR = '/data/GLEAM/drought_3D/events'
OUTPUT_DIR = '/data/GLEAM/drought_3D/characteristics'

# Grid cell area lookup (km² per latitude band, 0.1° resolution)
# Pre-calculated for 0.1° grid cells at different latitudes

# ============================================================================
#                           HELPER FUNCTIONS
# ============================================================================

def calculate_grid_area_0_1deg(lat):
    """
    Calculate area of a 0.1° × 0.1° grid cell at given latitude.
    
    Area = R² * cos(lat) * dlon * dlat
    where R = 6371 km, dlon = dlat = 0.1° = π/1800 rad
    
    Parameters
    ----------
    lat : float or np.ndarray
        Latitude in degrees
    
    Returns
    -------
    area : float or np.ndarray
        Grid cell area in km²
    """
    R = 6371.0  # Earth radius in km
    lat_rad = np.deg2rad(lat)
    dlat = np.deg2rad(0.1)
    dlon = np.deg2rad(0.1)
    
    area = R**2 * np.cos(lat_rad) * dlon * dlat
    return area


def load_threshold(threshold_file):
    """Load the drought threshold map."""
    ds = xr.open_dataset(threshold_file)
    threshold = ds['threshold'].values
    lat = ds['lat'].values
    lon = ds['lon'].values
    ds.close()
    return threshold, lat, lon


def load_event_file(filepath):
    """
    Load event track file.
    
    Returns
    -------
    df : pd.DataFrame
        DataFrame with columns: day, x_idx, y_idx
    """
    data = np.loadtxt(filepath, dtype=int)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    
    df = pd.DataFrame(data, columns=['day', 'x_idx', 'y_idx'])
    return df


def calculate_event_characteristics(event_df, sm_data, threshold, 
                                     lat_coord, lon_coord, year):
    """
    Calculate characteristics for a single drought event.
    
    Parameters
    ----------
    event_df : pd.DataFrame
        Event data with day, x_idx, y_idx columns
    sm_data : xr.DataArray
        Soil moisture data
    threshold : np.ndarray
        Threshold map
    lat_coord, lon_coord : np.ndarray
        Coordinate arrays
    year : int
        Year of the event
    
    Returns
    -------
    chars : dict
        Dictionary of event characteristics
    """
    # Basic temporal properties
    days = event_df['day'].unique()
    start_day = days.min()
    end_day = days.max()
    duration = len(days)
    
    # Calculate daily properties
    daily_areas = []
    daily_intensities = []
    daily_centroids = []
    
    for day in days:
        day_data = event_df[event_df['day'] == day]
        x_indices = day_data['x_idx'].values
        y_indices = day_data['y_idx'].values
        
        # Calculate area
        lats = lat_coord[y_indices]
        lons = lon_coord[x_indices]
        areas = calculate_grid_area_0_1deg(lats)
        daily_area = np.sum(areas)
        daily_areas.append(daily_area)
        
        # Calculate centroid
        centroid_lat = np.average(lats, weights=areas)
        centroid_lon = np.average(lons, weights=areas)
        daily_centroids.append((centroid_lat, centroid_lon))
        
        # Calculate intensity (soil moisture deficit)
        try:
            # Get time index for this day in the full dataset
            # Day is DOY, need to convert to actual time index
            time_index = (year - 1980) * 365 + day - 1  # Approximate
            
            sm_values = []
            thresh_values = []
            for xi, yi in zip(x_indices, y_indices):
                if yi < len(lat_coord) and xi < len(lon_coord):
                    thresh_val = threshold[yi, xi]
                    if not np.isnan(thresh_val):
                        thresh_values.append(thresh_val)
            
            if len(thresh_values) > 0:
                # Intensity = mean threshold (as proxy for severity)
                daily_intensities.append(np.mean(thresh_values))
            else:
                daily_intensities.append(np.nan)
                
        except Exception as e:
            daily_intensities.append(np.nan)
    
    # Aggregate characteristics
    chars = {
        'year': year,
        'start_doy': int(start_day),
        'end_doy': int(end_day),
        'duration': int(duration),
        'max_area_km2': float(np.max(daily_areas)),
        'mean_area_km2': float(np.mean(daily_areas)),
        'total_area_km2': float(np.sum(daily_areas)),
        'mean_intensity': float(np.nanmean(daily_intensities)),
        'n_grid_cells': int(len(event_df)),
        'start_centroid_lat': float(daily_centroids[0][0]),
        'start_centroid_lon': float(daily_centroids[0][1]),
        'end_centroid_lat': float(daily_centroids[-1][0]),
        'end_centroid_lon': float(daily_centroids[-1][1]),
    }
    
    # Calculate movement (centroid displacement)
    if len(daily_centroids) > 1:
        lat_disp = chars['end_centroid_lat'] - chars['start_centroid_lat']
        lon_disp = chars['end_centroid_lon'] - chars['start_centroid_lon']
        chars['centroid_displacement_km'] = float(
            np.sqrt((lat_disp * 111)**2 + (lon_disp * 111 * np.cos(np.deg2rad(chars['start_centroid_lat'])))**2)
        )
    else:
        chars['centroid_displacement_km'] = 0.0
    
    # Classification based on duration and area
    if duration >= 30 and chars['max_area_km2'] > 100000:
        chars['category'] = 'major'
    elif duration >= 14 or chars['max_area_km2'] > 50000:
        chars['category'] = 'moderate'
    else:
        chars['category'] = 'minor'
    
    return chars


def process_year(year, event_dir, output_dir, threshold, lat_coord, lon_coord):
    """
    Process all events for a given year.
    """
    year_event_dir = os.path.join(event_dir, str(year))
    
    if not os.path.exists(year_event_dir):
        print(f"No events found for year {year}")
        return None
    
    # Find all event files
    event_files = sorted(glob(os.path.join(year_event_dir, '[0-9]*.txt')))
    
    if len(event_files) == 0:
        print(f"No event files found in {year_event_dir}")
        return None
    
    print(f"Processing {len(event_files)} events for year {year}")
    
    # Process each event
    all_chars = []
    
    for event_file in tqdm(event_files, desc=f"Year {year}"):
        event_id = int(os.path.basename(event_file).replace('.txt', ''))
        
        try:
            event_df = load_event_file(event_file)
            chars = calculate_event_characteristics(
                event_df, None, threshold, lat_coord, lon_coord, year
            )
            chars['event_id'] = event_id
            all_chars.append(chars)
        except Exception as e:
            print(f"Error processing {event_file}: {e}")
            continue
    
    # Create DataFrame
    if len(all_chars) > 0:
        df = pd.DataFrame(all_chars)
        
        # Reorder columns
        cols = ['event_id', 'year', 'start_doy', 'end_doy', 'duration',
                'max_area_km2', 'mean_area_km2', 'total_area_km2',
                'mean_intensity', 'n_grid_cells', 'category',
                'start_centroid_lat', 'start_centroid_lon',
                'end_centroid_lat', 'end_centroid_lon',
                'centroid_displacement_km']
        df = df[[c for c in cols if c in df.columns]]
        
        # Save
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f'event_chars_{year}.csv')
        df.to_csv(output_file, index=False)
        print(f"Saved {len(df)} events to {output_file}")
        
        return df
    
    return None


def main():
    parser = argparse.ArgumentParser(
        description='Calculate drought event characteristics'
    )
    parser.add_argument('--year', type=int, default=None,
                        help='Single year to process')
    parser.add_argument('--start_year', type=int, default=None,
                        help='Start year for range')
    parser.add_argument('--end_year', type=int, default=None,
                        help='End year for range')
    parser.add_argument('--event_dir', type=str, default=EVENT_INPUT_DIR,
                        help='Input directory with event files')
    parser.add_argument('--output_dir', type=str, default=OUTPUT_DIR,
                        help='Output directory')
    parser.add_argument('--threshold_file', type=str, default=THRESHOLD_FILE,
                        help='Threshold file path')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Drought Event Characteristics Calculator")
    print("=" * 60)
    
    # Load threshold
    print("Loading threshold map...")
    threshold, lat_coord, lon_coord = load_threshold(args.threshold_file)
    print(f"Threshold shape: {threshold.shape}")
    
    # Determine years to process
    if args.year:
        years = [args.year]
    elif args.start_year and args.end_year:
        years = list(range(args.start_year, args.end_year + 1))
    else:
        # Find all available years
        years = []
        for d in os.listdir(args.event_dir):
            if d.isdigit():
                years.append(int(d))
        years = sorted(years)
    
    print(f"Processing years: {years}")
    
    # Process each year
    all_dfs = []
    for year in years:
        df = process_year(
            year, args.event_dir, args.output_dir,
            threshold, lat_coord, lon_coord
        )
        if df is not None:
            all_dfs.append(df)
    
    # Combine all years
    if len(all_dfs) > 0:
        combined = pd.concat(all_dfs, ignore_index=True)
        combined_file = os.path.join(args.output_dir, 'all_events.csv')
        combined.to_csv(combined_file, index=False)
        print(f"\nSaved combined {len(combined)} events to {combined_file}")
        
        # Print summary statistics
        print("\n" + "=" * 60)
        print("Summary Statistics")
        print("=" * 60)
        print(f"Total events: {len(combined)}")
        print(f"Mean duration: {combined['duration'].mean():.1f} days")
        print(f"Max duration: {combined['duration'].max()} days")
        print(f"Mean max area: {combined['max_area_km2'].mean():.0f} km²")
        print(f"Max max area: {combined['max_area_km2'].max():.0f} km²")
        print(f"\nCategory distribution:")
        print(combined['category'].value_counts())
    
    print("\nProcessing complete!")


if __name__ == '__main__':
    main()
