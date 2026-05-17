"""
Flash Drought Detection - Optimized Version
============================================
按纬度带处理数据，大幅提升计算效率。
输出：
- 总频率 TIF
- 每年频率 TIF
- 详细事件数据 Parquet文件

Author: Auto-generated
Date: 2026-01-11
"""

import os
import sys
import numpy as np
import xarray as xr
import pandas as pd
from pathlib import Path
from datetime import datetime
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS
import warnings
import gc

warnings.filterwarnings('ignore')

# =============================================================================
# Configuration
# =============================================================================
DATA_DIR = Path(r"e:\download_data\gleam\SMrz_dd")
OUTPUT_DIR = Path(r"e:\download_data\gleam\flash_drought\result")
PROCESS_DIR = Path(r"e:\download_data\gleam\flash_drought\process")

# Climatology baseline period
BASELINE_START = 1981
BASELINE_END = 2010

# Full analysis period
ANALYSIS_START = 1980
ANALYSIS_END = 2024

# Flash drought parameters
ROLLING_WINDOW = 5
UPPER_PERCENTILE = 40
LOWER_PERCENTILE = 20
RATE_PERCENTILE = 5
MIN_DURATION = 15

# Processing parameters - 按纬度带处理
LAT_CHUNK_SIZE = 10  # 每次处理10个纬度带


def print_progress(msg):
    """Print with timestamp and flush."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# =============================================================================
# Data Loading Functions
# =============================================================================
def get_nc_files(data_dir, start_year, end_year):
    """Get list of NC files for specified year range."""
    files = []
    for year in range(start_year, end_year + 1):
        pattern = f"SMrz_{year}_GLEAM_v4.2a.nc"
        filepath = data_dir / pattern
        if filepath.exists():
            files.append((year, filepath))
    return files


def get_coordinates(nc_file):
    """Get lat/lon coordinates from a NC file."""
    with xr.open_dataset(nc_file) as ds:
        lats = ds['lat'].values
        lons = ds['lon'].values
    return lats, lons


def load_lat_band_data(nc_files, lat_start_idx, lat_end_idx):
    """
    Load data for a latitude band across all years.
    Returns: (dates, data_3d) where data_3d is [time, lat_band, lon]
    """
    all_dates = []
    all_data = []
    
    for year, filepath in nc_files:
        with xr.open_dataset(filepath) as ds:
            # 只读取指定纬度带
            band_data = ds['SMrz'].isel(lat=slice(lat_start_idx, lat_end_idx)).values
            dates = ds['time'].values
            all_dates.append(dates)
            all_data.append(band_data)
    
    return np.concatenate(all_dates), np.concatenate(all_data, axis=0)


# =============================================================================
# Climatology Functions
# =============================================================================
def calculate_climatology_for_band(dates, data_3d, baseline_start, baseline_end):
    """
    Calculate DOY-based percentiles for a latitude band.
    
    Args:
        dates: 1D array of dates
        data_3d: 3D array [time, lat, lon]
        
    Returns:
        p20: [366, lat, lon] - 20th percentile for each DOY
        p40: [366, lat, lon] - 40th percentile for each DOY  
        rate_p5: [366, lat, lon] - 5th percentile of decline rate
    """
    n_time, n_lat, n_lon = data_3d.shape
    
    # Convert dates to DOY and year
    dates_pd = pd.to_datetime(dates)
    doys = dates_pd.dayofyear.values
    years = dates_pd.year.values
    
    # Baseline mask
    baseline_mask = (years >= baseline_start) & (years <= baseline_end)
    
    # Apply 5-day rolling average along time axis
    # Using convolution for efficiency
    kernel = np.ones(ROLLING_WINDOW) / ROLLING_WINDOW
    data_rolling = np.apply_along_axis(
        lambda x: np.convolve(x, kernel, mode='same'), 
        0, data_3d
    )
    
    # Calculate decline rate (5-day)
    decline_rate = np.zeros_like(data_rolling)
    decline_rate[:-ROLLING_WINDOW] = (data_rolling[:-ROLLING_WINDOW] - data_rolling[ROLLING_WINDOW:]) / ROLLING_WINDOW
    
    # Initialize output arrays
    p20 = np.full((366, n_lat, n_lon), np.nan, dtype=np.float32)
    p40 = np.full((366, n_lat, n_lon), np.nan, dtype=np.float32)
    rate_p5 = np.full((366, n_lat, n_lon), np.nan, dtype=np.float32)
    
    # Calculate percentiles for each DOY
    for doy in range(1, 367):
        doy_mask = (doys == doy) & baseline_mask
        if np.sum(doy_mask) > 0:
            doy_data = data_rolling[doy_mask]  # [n_years, lat, lon]
            doy_rates = decline_rate[doy_mask]
            
            p20[doy-1] = np.nanpercentile(doy_data, LOWER_PERCENTILE, axis=0)
            p40[doy-1] = np.nanpercentile(doy_data, UPPER_PERCENTILE, axis=0)
            rate_p5[doy-1] = np.nanpercentile(doy_rates, RATE_PERCENTILE, axis=0)
    
    return p20, p40, rate_p5, data_rolling, decline_rate, doys, years


# =============================================================================
# Flash Drought Detection - Vectorized
# =============================================================================
def detect_flash_droughts_vectorized(data_rolling, decline_rate, doys, years, p20, p40, rate_p5):
    """
    Vectorized flash drought detection for a latitude band.
    
    Returns:
        events_list: List of event records
        yearly_counts: [n_years, lat, lon] - count of events per year
        total_freq: [lat, lon] - total frequency
    """
    n_time, n_lat, n_lon = data_rolling.shape
    unique_years = np.unique(years)
    n_years = len(unique_years)
    year_to_idx = {y: i for i, y in enumerate(unique_years)}
    
    # Initialize outputs
    yearly_counts = np.zeros((n_years, n_lat, n_lon), dtype=np.int16)
    yearly_duration_sum = np.zeros((n_years, n_lat, n_lon), dtype=np.float32)
    yearly_intensity_sum = np.zeros((n_years, n_lat, n_lon), dtype=np.float32)
    
    events_list = []
    
    # Process each pixel
    for lat_i in range(n_lat):
        for lon_i in range(n_lon):
            # Get pixel time series
            sm = data_rolling[:, lat_i, lon_i]
            rates = decline_rate[:, lat_i, lon_i]
            
            # Skip if all NaN
            if np.all(np.isnan(sm)):
                continue
            
            # Get thresholds for this pixel
            pixel_p20 = p20[:, lat_i, lon_i]
            pixel_p40 = p40[:, lat_i, lon_i]
            pixel_rate_p5 = rate_p5[:, lat_i, lon_i]
            
            # Detect events for this pixel
            in_event = False
            event_start_idx = None
            recently_above_40 = False
            lookback_window = 10
            
            for t in range(n_time):
                doy_idx = doys[t] - 1
                current_sm = sm[t]
                current_p20 = pixel_p20[doy_idx]
                current_p40 = pixel_p40[doy_idx]
                current_rate_threshold = pixel_rate_p5[doy_idx]
                current_rate = rates[t]
                
                if np.isnan(current_sm) or np.isnan(current_p20):
                    continue
                
                # Check above 40
                above_40 = current_sm > current_p40
                below_20 = current_sm < current_p20
                
                if above_40:
                    recently_above_40 = True
                
                # Check lookback
                if t > 0:
                    start_lb = max(0, t - lookback_window)
                    for lb_t in range(start_lb, t):
                        lb_doy_idx = doys[lb_t] - 1
                        if sm[lb_t] > pixel_p40[lb_doy_idx]:
                            recently_above_40 = True
                            break
                
                if not in_event:
                    # Check for event start
                    if below_20 and recently_above_40:
                        if not np.isnan(current_rate) and not np.isnan(current_rate_threshold):
                            if current_rate >= current_rate_threshold:  # Faster decline
                                in_event = True
                                event_start_idx = t
                else:
                    # Check for event end
                    if not below_20:
                        duration = t - event_start_idx
                        if duration >= MIN_DURATION:
                            # Valid event
                            event_year = years[event_start_idx]
                            year_idx = year_to_idx[event_year]
                            yearly_counts[year_idx, lat_i, lon_i] += 1
                            
                            # Calculate intensity
                            intensity = 0
                            for et in range(event_start_idx, t):
                                et_doy_idx = doys[et] - 1
                                if sm[et] < pixel_p20[et_doy_idx]:
                                    intensity += pixel_p20[et_doy_idx] - sm[et]
                            
                            yearly_duration_sum[year_idx, lat_i, lon_i] += duration
                            yearly_intensity_sum[year_idx, lat_i, lon_i] += intensity
                            
                            events_list.append({
                                'lat_idx': lat_i,
                                'lon_idx': lon_i,
                                'year': event_year,
                                'onset_doy': doys[event_start_idx],
                                'end_doy': doys[t-1],
                                'duration': duration,
                                'intensity': intensity
                            })
                        
                        in_event = False
                        event_start_idx = None
                        recently_above_40 = False
            
            # Handle ongoing event at end
            if in_event:
                duration = n_time - event_start_idx
                if duration >= MIN_DURATION:
                    event_year = years[event_start_idx]
                    year_idx = year_to_idx[event_year]
                    yearly_counts[year_idx, lat_i, lon_i] += 1
                    
                    intensity = 0
                    for et in range(event_start_idx, n_time):
                        et_doy_idx = doys[et] - 1
                        if sm[et] < pixel_p20[et_doy_idx]:
                            intensity += pixel_p20[et_doy_idx] - sm[et]
                    
                    yearly_duration_sum[year_idx, lat_i, lon_i] += duration
                    yearly_intensity_sum[year_idx, lat_i, lon_i] += intensity
                    
                    events_list.append({
                        'lat_idx': lat_i,
                        'lon_idx': lon_i,
                        'year': event_year,
                        'onset_doy': doys[event_start_idx],
                        'end_doy': doys[-1],
                        'duration': duration,
                        'intensity': intensity
                    })
    
    return events_list, yearly_counts, yearly_duration_sum, yearly_intensity_sum, unique_years


# =============================================================================
# Output Functions
# =============================================================================
def save_tif(data, lats, lons, output_path, nodata=-9999):
    """Save 2D array as GeoTIFF."""
    # Handle lat direction (usually north to south in GLEAM)
    if lats[0] > lats[-1]:
        # Lats are descending, data is already correct
        lat_min, lat_max = lats[-1], lats[0]
    else:
        lat_min, lat_max = lats[0], lats[-1]
        data = np.flipud(data)
    
    lon_min, lon_max = lons[0], lons[-1]
    
    # Calculate pixel size
    lat_res = abs(lats[1] - lats[0]) if len(lats) > 1 else 0.1
    lon_res = abs(lons[1] - lons[0]) if len(lons) > 1 else 0.1
    
    transform = from_bounds(
        lon_min - lon_res/2, lat_min - lat_res/2,
        lon_max + lon_res/2, lat_max + lat_res/2,
        len(lons), len(lats)
    )
    
    # Replace NaN with nodata
    data_write = np.where(np.isnan(data), nodata, data).astype(np.float32)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with rasterio.open(
        output_path, 'w',
        driver='GTiff',
        height=data_write.shape[0],
        width=data_write.shape[1],
        count=1,
        dtype=np.float32,
        crs=CRS.from_epsg(4326),
        transform=transform,
        nodata=nodata,
        compress='lzw'
    ) as dst:
        dst.write(data_write, 1)


def save_events_parquet(events_df, output_path):
    """Save events DataFrame to Parquet file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    events_df.to_parquet(output_path, compression='snappy', index=False)


# =============================================================================
# Main Processing
# =============================================================================
def process_global():
    """Process all global data by latitude bands."""
    print_progress("=" * 60)
    print_progress("Flash Drought Detection - Optimized Global Processing")
    print_progress("=" * 60)
    
    # Create directories
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Get files and coordinates
    nc_files = get_nc_files(DATA_DIR, ANALYSIS_START, ANALYSIS_END)
    print_progress(f"Found {len(nc_files)} NC files ({ANALYSIS_START}-{ANALYSIS_END})")
    
    lats, lons = get_coordinates(nc_files[0][1])
    n_lats, n_lons = len(lats), len(lons)
    print_progress(f"Grid size: {n_lats} lat x {n_lons} lon")
    
    # Initialize global results
    years_list = list(range(ANALYSIS_START, ANALYSIS_END + 1))
    n_years = len(years_list)
    
    total_frequency = np.full((n_lats, n_lons), np.nan, dtype=np.float32)
    yearly_frequency = np.full((n_years, n_lats, n_lons), np.nan, dtype=np.float32)
    yearly_mean_duration = np.full((n_years, n_lats, n_lons), np.nan, dtype=np.float32)
    yearly_mean_intensity = np.full((n_years, n_lats, n_lons), np.nan, dtype=np.float32)
    
    all_events = []
    
    # Process by latitude bands
    n_chunks = (n_lats + LAT_CHUNK_SIZE - 1) // LAT_CHUNK_SIZE
    print_progress(f"Processing {n_chunks} latitude bands (size={LAT_CHUNK_SIZE})")
    
    for chunk_idx in range(n_chunks):
        lat_start = chunk_idx * LAT_CHUNK_SIZE
        lat_end = min((chunk_idx + 1) * LAT_CHUNK_SIZE, n_lats)
        
        print_progress(f"Processing band {chunk_idx+1}/{n_chunks}: lat indices [{lat_start}:{lat_end}]")
        
        # Load data for this band
        print_progress(f"  Loading data...")
        dates, data_3d = load_lat_band_data(nc_files, lat_start, lat_end)
        print_progress(f"  Data shape: {data_3d.shape}")
        
        # Calculate climatology
        print_progress(f"  Calculating climatology...")
        p20, p40, rate_p5, data_rolling, decline_rate, doys, data_years = \
            calculate_climatology_for_band(dates, data_3d, BASELINE_START, BASELINE_END)
        
        # Detect flash droughts
        print_progress(f"  Detecting flash droughts...")
        events, yearly_counts, yearly_dur_sum, yearly_int_sum, unique_years = \
            detect_flash_droughts_vectorized(data_rolling, decline_rate, doys, data_years, p20, p40, rate_p5)
        
        print_progress(f"  Found {len(events)} events in this band")
        
        # Store results
        band_n_lat = lat_end - lat_start
        
        # Map unique years to our year indices
        year_to_global_idx = {y: y - ANALYSIS_START for y in unique_years}
        
        for i, y in enumerate(unique_years):
            global_year_idx = year_to_global_idx[y]
            yearly_frequency[global_year_idx, lat_start:lat_end, :] = yearly_counts[i]
            
            # Mean duration and intensity
            with np.errstate(invalid='ignore', divide='ignore'):
                yearly_mean_duration[global_year_idx, lat_start:lat_end, :] = \
                    np.where(yearly_counts[i] > 0, yearly_dur_sum[i] / yearly_counts[i], np.nan)
                yearly_mean_intensity[global_year_idx, lat_start:lat_end, :] = \
                    np.where(yearly_counts[i] > 0, yearly_int_sum[i] / yearly_counts[i], np.nan)
        
        # Adjust lat indices in events and add coordinates
        for evt in events:
            evt['lat_idx'] += lat_start
            evt['lat'] = lats[evt['lat_idx']]
            evt['lon'] = lons[evt['lon_idx']]
            all_events.append(evt)
        
        # Free memory
        del data_3d, data_rolling, decline_rate, p20, p40, rate_p5
        gc.collect()
    
    # Calculate total frequency
    print_progress("Calculating total frequency...")
    total_counts = np.nansum(yearly_frequency, axis=0)
    total_frequency = total_counts / n_years
    
    # Save results
    print_progress("Saving results...")
    
    # 1. Total frequency TIF
    save_tif(total_frequency, lats, lons, OUTPUT_DIR / "flash_drought_frequency_total.tif")
    print_progress(f"  Saved: flash_drought_frequency_total.tif")
    
    # 2. Yearly frequency TIFs
    for i, year in enumerate(years_list):
        save_tif(yearly_frequency[i], lats, lons, OUTPUT_DIR / f"flash_drought_frequency_{year}.tif")
    print_progress(f"  Saved: yearly frequency TIFs ({ANALYSIS_START}-{ANALYSIS_END})")
    
    # 3. Yearly mean duration TIFs
    for i, year in enumerate(years_list):
        save_tif(yearly_mean_duration[i], lats, lons, OUTPUT_DIR / f"flash_drought_duration_{year}.tif")
    print_progress(f"  Saved: yearly duration TIFs")
    
    # 4. Yearly mean intensity TIFs
    for i, year in enumerate(years_list):
        save_tif(yearly_mean_intensity[i], lats, lons, OUTPUT_DIR / f"flash_drought_intensity_{year}.tif")
    print_progress(f"  Saved: yearly intensity TIFs")
    
    # 5. Detailed events Parquet
    if all_events:
        events_df = pd.DataFrame(all_events)
        events_df = events_df[['year', 'lat', 'lon', 'lat_idx', 'lon_idx', 
                               'onset_doy', 'end_doy', 'duration', 'intensity']]
        save_events_parquet(events_df, OUTPUT_DIR / "flash_drought_events_detail.parquet")
        print_progress(f"  Saved: flash_drought_events_detail.parquet ({len(all_events)} events)")
    
    print_progress("=" * 60)
    print_progress("Processing complete!")
    print_progress(f"Total events detected: {len(all_events)}")
    print_progress(f"Results saved to: {OUTPUT_DIR}")
    

def test_small_region():
    """Test on a small region."""
    print_progress("Testing on small region...")
    
    nc_files = get_nc_files(DATA_DIR, ANALYSIS_START, ANALYSIS_END)
    lats, lons = get_coordinates(nc_files[0][1])
    
    # Test on 5 latitude bands
    lat_start, lat_end = 545, 555  # Around 35°N
    
    print_progress(f"Loading test data (lat indices {lat_start}:{lat_end})...")
    dates, data_3d = load_lat_band_data(nc_files, lat_start, lat_end)
    print_progress(f"Data shape: {data_3d.shape}")
    
    print_progress("Calculating climatology...")
    p20, p40, rate_p5, data_rolling, decline_rate, doys, data_years = \
        calculate_climatology_for_band(dates, data_3d, BASELINE_START, BASELINE_END)
    
    print_progress("Detecting flash droughts...")
    events, yearly_counts, yearly_dur_sum, yearly_int_sum, unique_years = \
        detect_flash_droughts_vectorized(data_rolling, decline_rate, doys, data_years, p20, p40, rate_p5)
    
    print_progress(f"Found {len(events)} events")
    
    if events:
        print_progress("\nSample events:")
        for evt in events[:5]:
            print_progress(f"  Year {evt['year']}, DOY {evt['onset_doy']}-{evt['end_doy']}, "
                          f"Duration {evt['duration']} days, Intensity {evt['intensity']:.2f}")
    
    return events


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_small_region()
    else:
        process_global()
