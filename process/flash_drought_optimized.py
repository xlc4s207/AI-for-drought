"""
Flash Drought Detection System - Optimized Version
===================================================
Optimized for large-scale processing with batch row-based I/O.

Key optimizations:
1. Process data row by row (all longitudes at once)
2. Load one row across all years in single pass
3. Pre-compute DOY percentiles per row
4. Parallel processing across rows instead of individual pixels
"""

import numpy as np
import xarray as xr
import pandas as pd
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass
from multiprocessing import Pool
from tqdm import tqdm
import time
import warnings
import gc

warnings.filterwarnings('ignore')

# =============================================================================
# Configuration
# =============================================================================

BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "SMrz_dd"
RESULT_DIR = BASE_DIR / "flash_drought" / "result"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

NC_FILE_PATTERN = "SMrz_{year}_GLEAM_v4.2a.nc"
VARIABLE_NAME = "SMrz"

START_YEAR = 1980
END_YEAR = 2024
ALL_YEARS = list(range(START_YEAR, END_YEAR + 1))

BASELINE_PERIODS = {
    "1980_2024": (1980, 2024),
    "1981_2010": (1981, 2010),
}

# Thresholds
P_HIGH = 40
P_LOW = 20
P_DECLINE_RATE = 5
MOVING_AVG_WINDOW = 5
MIN_EVENT_DURATION = 15
MAX_EVENTS_PER_PIXEL = 50

# Grid
N_LAT = 1800
N_LON = 3600
LAT_MIN, LAT_MAX = -89.95, 89.95
LON_MIN, LON_MAX = -179.95, 179.95
RESOLUTION = 0.1
NODATA_VALUE = -9999


@dataclass
class FlashDroughtEvent:
    """Flash drought event data."""
    year: int
    start_doy: int
    end_doy: int
    duration: int
    intensity: float


# =============================================================================
# Optimized Data Loading - Row-based
# =============================================================================

def get_nc_filepath(year: int) -> Path:
    return DATA_DIR / NC_FILE_PATTERN.format(year=year)


def get_lat_lon_arrays() -> Tuple[np.ndarray, np.ndarray]:
    """Get coordinate arrays from first NC file."""
    with xr.open_dataset(get_nc_filepath(ALL_YEARS[0])) as ds:
        return ds['lat'].values.copy(), ds['lon'].values.copy()


def get_valid_mask() -> np.ndarray:
    """Get 2D mask of valid (land) pixels."""
    with xr.open_dataset(get_nc_filepath(ALL_YEARS[0])) as ds:
        data = ds[VARIABLE_NAME].isel(time=0).values
        return ~np.isnan(data)


def extract_row_timeseries(lat_idx: int, years: List[int] = None) -> Tuple[np.ndarray, np.ndarray]:
    """
    Extract time series for an entire row (all longitudes) across all years.
    
    Returns:
        dates: 1D array of dates (n_days,)
        values: 2D array (n_days, n_lon)
    """
    if years is None:
        years = ALL_YEARS
    
    all_values = []
    all_dates = []
    
    for year in years:
        filepath = get_nc_filepath(year)
        with xr.open_dataset(filepath) as ds:
            # Extract entire row for all time steps
            row_data = ds[VARIABLE_NAME][:, lat_idx, :].values  # (time, lon)
            dates = ds['time'].values
            
            all_values.append(row_data)
            all_dates.append(dates)
    
    values = np.concatenate(all_values, axis=0)  # (total_days, n_lon)
    dates = np.concatenate(all_dates)
    
    return dates, values


# =============================================================================
# Vectorized Statistical Functions
# =============================================================================

def compute_5day_moving_average_2d(values: np.ndarray) -> np.ndarray:
    """Compute 5-day moving average for 2D array (time x lon)."""
    window = MOVING_AVG_WINDOW
    kernel = np.ones(window) / window
    
    result = np.zeros_like(values)
    for lon_idx in range(values.shape[1]):
        col = values[:, lon_idx]
        if not np.all(np.isnan(col)):
            padded = np.pad(col, (window//2, window//2), mode='edge')
            result[:, lon_idx] = np.convolve(padded, kernel, mode='valid')
        else:
            result[:, lon_idx] = np.nan
    
    return result


def compute_doy_percentiles_vectorized(
    values: np.ndarray,
    dates: np.ndarray,
    baseline_years: Tuple[int, int]
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute DOY percentiles for all pixels in a row.
    
    Args:
        values: 2D array (time, lon)
        dates: 1D array of dates
        baseline_years: tuple of (start, end) baseline years
        
    Returns:
        p40: 2D array (367, n_lon)
        p20: 2D array (367, n_lon)
        decline_p5: 2D array (367, n_lon)
    """
    n_lon = values.shape[1]
    
    dates_pd = pd.to_datetime(dates)
    years = dates_pd.year.values
    doy = dates_pd.dayofyear.values
    
    baseline_mask = (years >= baseline_years[0]) & (years <= baseline_years[1])
    
    p40 = np.full((367, n_lon), np.nan)
    p20 = np.full((367, n_lon), np.nan)
    decline_p5 = np.full((367, n_lon), np.nan)
    
    # Calculate decline rates
    decline_rates = np.diff(values, axis=0, prepend=values[:1, :])
    
    for d in range(1, 367):
        doy_mask = (doy == d) & baseline_mask
        if np.sum(doy_mask) > 0:
            doy_values = values[doy_mask, :]  # (n_matches, n_lon)
            
            # Compute percentiles ignoring NaN
            with np.errstate(all='ignore'):
                p40[d, :] = np.nanpercentile(doy_values, P_HIGH, axis=0)
                p20[d, :] = np.nanpercentile(doy_values, P_LOW, axis=0)
            
            doy_decline = decline_rates[doy_mask, :]
            with np.errstate(all='ignore'):
                decline_p5[d, :] = np.nanpercentile(doy_decline, P_DECLINE_RATE, axis=0)
    
    return p40, p20, decline_p5


# =============================================================================
# Flash Drought Detection
# =============================================================================

def detect_flash_drought_single_pixel(
    values: np.ndarray,
    doy: np.ndarray,
    years: np.ndarray,
    p40: np.ndarray,
    p20: np.ndarray,
    decline_p5: np.ndarray
) -> List[FlashDroughtEvent]:
    """Detect flash drought events for a single pixel time series."""
    events = []
    n = len(values)
    
    if n == 0 or np.all(np.isnan(values)):
        return events
    
    # Build daily thresholds
    p40_daily = np.array([p40[d] if d < 367 else np.nan for d in doy])
    p20_daily = np.array([p20[d] if d < 367 else np.nan for d in doy])
    decline_p5_daily = np.array([decline_p5[d] if d < 367 else np.nan for d in doy])
    
    in_event = False
    event_start_idx = None
    was_above_p40 = False
    
    i = 0
    while i < n:
        val = values[i]
        th_p40 = p40_daily[i]
        th_p20 = p20_daily[i]
        
        if np.isnan(val) or np.isnan(th_p40) or np.isnan(th_p20):
            i += 1
            continue
        
        if not in_event:
            if val >= th_p40:
                was_above_p40 = True
            
            if was_above_p40 and val < th_p20:
                lookback = min(5, i)
                if lookback > 0:
                    window_decline = values[i] - values[i - lookback]
                    avg_decline = window_decline / lookback
                    th_decline = decline_p5_daily[i]
                    
                    if not np.isnan(th_decline) and avg_decline <= th_decline:
                        in_event = True
                        event_start_idx = i
        else:
            if val >= th_p20:
                event_end_idx = i - 1
                duration = event_end_idx - event_start_idx + 1
                
                if duration >= MIN_EVENT_DURATION:
                    deficit = np.maximum(p20_daily[event_start_idx:event_end_idx+1] - 
                                        values[event_start_idx:event_end_idx+1], 0)
                    intensity = float(np.nansum(deficit))
                    
                    events.append(FlashDroughtEvent(
                        year=int(years[event_start_idx]),
                        start_doy=int(doy[event_start_idx]),
                        end_doy=int(doy[event_end_idx]),
                        duration=int(duration),
                        intensity=intensity
                    ))
                
                in_event = False
                event_start_idx = None
                was_above_p40 = False
        
        i += 1
    
    # Handle trailing event
    if in_event and event_start_idx is not None:
        event_end_idx = n - 1
        duration = event_end_idx - event_start_idx + 1
        if duration >= MIN_EVENT_DURATION:
            deficit = np.maximum(p20_daily[event_start_idx:event_end_idx+1] - 
                                values[event_start_idx:event_end_idx+1], 0)
            intensity = float(np.nansum(deficit))
            events.append(FlashDroughtEvent(
                year=int(years[event_start_idx]),
                start_doy=int(doy[event_start_idx]),
                end_doy=int(doy[event_end_idx]),
                duration=int(duration),
                intensity=intensity
            ))
    
    return events


def process_row(lat_idx: int, baseline_period: str = "1980_2024") -> Dict:
    """
    Process an entire row (all longitudes) at once.
    
    This is the key optimization - loading one row across all years
    is much faster than loading individual pixels.
    """
    result = {
        'lat_idx': lat_idx,
        'pixel_results': [],
        'total_events': 0
    }
    
    try:
        # Load entire row time series
        dates, values = extract_row_timeseries(lat_idx)
        
        # Check if row has any valid data
        valid_cols = ~np.all(np.isnan(values), axis=0)
        if not np.any(valid_cols):
            return result
        
        # Compute 5-day moving average
        values_ma = compute_5day_moving_average_2d(values)
        
        # Compute DOY percentiles for the row
        baseline_years = BASELINE_PERIODS[baseline_period]
        p40, p20, decline_p5 = compute_doy_percentiles_vectorized(
            values_ma, dates, baseline_years
        )
        
        # Prepare date info
        dates_pd = pd.to_datetime(dates)
        doy = dates_pd.dayofyear.values
        years_arr = dates_pd.year.values
        
        # Process each valid pixel in the row
        for lon_idx in range(N_LON):
            if not valid_cols[lon_idx]:
                continue
            
            pixel_values = values_ma[:, lon_idx]
            pixel_p40 = p40[:, lon_idx]
            pixel_p20 = p20[:, lon_idx]
            pixel_decline = decline_p5[:, lon_idx]
            
            events = detect_flash_drought_single_pixel(
                pixel_values, doy, years_arr, pixel_p40, pixel_p20, pixel_decline
            )
            
            if events:
                result['pixel_results'].append({
                    'lon_idx': lon_idx,
                    'events': events,
                    'count': len(events)
                })
                result['total_events'] += len(events)
        
        # Free memory
        del values, values_ma, p40, p20, decline_p5
        gc.collect()
        
    except Exception as e:
        print(f"Error processing row {lat_idx}: {e}")
    
    return result


def process_row_wrapper(args):
    """Wrapper for parallel processing."""
    lat_idx, baseline_period = args
    return process_row(lat_idx, baseline_period)


# =============================================================================
# Output Functions
# =============================================================================

def save_geotiff(data: np.ndarray, output_path: Path, nodata: float = NODATA_VALUE):
    """Save 2D array as GeoTIFF."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    transform = from_bounds(
        LON_MIN - RESOLUTION/2, LAT_MIN - RESOLUTION/2,
        LON_MAX + RESOLUTION/2, LAT_MAX + RESOLUTION/2,
        N_LON, N_LAT
    )
    
    with rasterio.open(
        output_path, 'w', driver='GTiff',
        height=N_LAT, width=N_LON, count=1,
        dtype=data.dtype, crs=CRS.from_epsg(4326),
        transform=transform, nodata=nodata, compress='lzw'
    ) as dst:
        dst.write(data, 1)
    
    print(f"Saved: {output_path}")


def save_events_netcdf(events_data: Dict, lats: np.ndarray, lons: np.ndarray, 
                       year: int, output_path: Path, baseline: str):
    """Save events for a year to NetCDF."""
    ds = xr.Dataset(
        {
            'start_doy': (['lat', 'lon', 'event'], events_data['start_doy']),
            'end_doy': (['lat', 'lon', 'event'], events_data['end_doy']),
            'duration': (['lat', 'lon', 'event'], events_data['duration']),
            'intensity': (['lat', 'lon', 'event'], events_data['intensity']),
        },
        coords={
            'lat': lats,
            'lon': lons,
            'event': np.arange(MAX_EVENTS_PER_PIXEL)
        },
        attrs={
            'title': f'Flash Drought Events {year}',
            'baseline_period': baseline
        }
    )
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(output_path, encoding={
        k: {'dtype': 'float32', 'zlib': True, 'complevel': 4}
        for k in ds.data_vars
    })
    print(f"Saved: {output_path}")


# =============================================================================
# Main Processing
# =============================================================================

def run_flash_drought_detection(
    baseline_period: str = "1980_2024",
    n_workers: int = 4,
    test_rows: List[int] = None
):
    """
    Run flash drought detection using row-based processing.
    
    Args:
        baseline_period: Baseline for percentile calculation
        n_workers: Number of parallel workers
        test_rows: If provided, only process these rows (for testing)
    """
    print("\n" + "=" * 70)
    print("  FLASH DROUGHT DETECTION - OPTIMIZED ROW-BASED PROCESSING")
    print("=" * 70)
    
    # Get coordinates
    lats, lons = get_lat_lon_arrays()
    
    # Get valid mask
    print("\nLoading valid pixel mask...")
    valid_mask = get_valid_mask()
    
    # Find rows with valid data
    valid_rows = np.where(np.any(valid_mask, axis=1))[0]
    
    if test_rows is not None:
        valid_rows = np.array([r for r in test_rows if r in valid_rows])
    
    print(f"Rows to process: {len(valid_rows)}")
    print(f"Baseline period: {baseline_period}")
    print(f"Workers: {n_workers}")
    
    # Initialize result arrays
    total_freq = np.full((N_LAT, N_LON), NODATA_VALUE, dtype=np.float32)
    annual_freq = {year: np.full((N_LAT, N_LON), NODATA_VALUE, dtype=np.float32) 
                   for year in ALL_YEARS}
    
    # Events storage per year
    events_by_year = {
        year: {
            'start_doy': np.full((N_LAT, N_LON, MAX_EVENTS_PER_PIXEL), NODATA_VALUE, dtype=np.float32),
            'end_doy': np.full((N_LAT, N_LON, MAX_EVENTS_PER_PIXEL), NODATA_VALUE, dtype=np.float32),
            'duration': np.full((N_LAT, N_LON, MAX_EVENTS_PER_PIXEL), NODATA_VALUE, dtype=np.float32),
            'intensity': np.full((N_LAT, N_LON, MAX_EVENTS_PER_PIXEL), np.nan, dtype=np.float32),
        }
        for year in ALL_YEARS
    }
    
    # Prepare arguments
    args_list = [(int(lat_idx), baseline_period) for lat_idx in valid_rows]
    
    start_time = time.time()
    total_events = 0
    
    print("\nProcessing rows...")
    
    # Sequential processing for reliability (can switch to parallel if needed)
    if n_workers == 1:
        # Sequential
        for args in tqdm(args_list, desc="Rows"):
            row_result = process_row_wrapper(args)
            lat_idx = row_result['lat_idx']
            
            for pixel in row_result['pixel_results']:
                lon_idx = pixel['lon_idx']
                total_freq[lat_idx, lon_idx] = pixel['count']
                
                # Count per year and store events
                year_counts = {y: 0 for y in ALL_YEARS}
                event_idx_by_year = {y: 0 for y in ALL_YEARS}
                
                for event in pixel['events']:
                    year = event.year
                    if year in year_counts:
                        year_counts[year] += 1
                        
                        idx = event_idx_by_year[year]
                        if idx < MAX_EVENTS_PER_PIXEL:
                            events_by_year[year]['start_doy'][lat_idx, lon_idx, idx] = event.start_doy
                            events_by_year[year]['end_doy'][lat_idx, lon_idx, idx] = event.end_doy
                            events_by_year[year]['duration'][lat_idx, lon_idx, idx] = event.duration
                            events_by_year[year]['intensity'][lat_idx, lon_idx, idx] = event.intensity
                            event_idx_by_year[year] += 1
                
                for year, count in year_counts.items():
                    annual_freq[year][lat_idx, lon_idx] = count
            
            total_events += row_result['total_events']
    else:
        # Parallel
        with Pool(n_workers) as pool:
            for row_result in tqdm(pool.imap(process_row_wrapper, args_list), 
                                   total=len(args_list), desc="Rows"):
                lat_idx = row_result['lat_idx']
                
                for pixel in row_result['pixel_results']:
                    lon_idx = pixel['lon_idx']
                    total_freq[lat_idx, lon_idx] = pixel['count']
                    
                    year_counts = {y: 0 for y in ALL_YEARS}
                    event_idx_by_year = {y: 0 for y in ALL_YEARS}
                    
                    for event in pixel['events']:
                        year = event.year
                        if year in year_counts:
                            year_counts[year] += 1
                            
                            idx = event_idx_by_year[year]
                            if idx < MAX_EVENTS_PER_PIXEL:
                                events_by_year[year]['start_doy'][lat_idx, lon_idx, idx] = event.start_doy
                                events_by_year[year]['end_doy'][lat_idx, lon_idx, idx] = event.end_doy
                                events_by_year[year]['duration'][lat_idx, lon_idx, idx] = event.duration
                                events_by_year[year]['intensity'][lat_idx, lon_idx, idx] = event.intensity
                                event_idx_by_year[year] += 1
                    
                    for year, count in year_counts.items():
                        annual_freq[year][lat_idx, lon_idx] = count
                
                total_events += row_result['total_events']
    
    elapsed = time.time() - start_time
    
    print(f"\n{'=' * 70}")
    print(f"Processing complete!")
    print(f"Time: {elapsed/60:.1f} minutes")
    print(f"Rows processed: {len(valid_rows)}")
    print(f"Total events: {total_events:,}")
    print(f"{'=' * 70}")
    
    # Save results
    output_dir = RESULT_DIR / f"baseline_{baseline_period}"
    
    print("\nSaving total frequency...")
    save_geotiff(total_freq, output_dir / "total_frequency.tif")
    
    print("\nSaving annual frequency...")
    annual_dir = output_dir / "annual_frequency"
    for year in ALL_YEARS:
        save_geotiff(annual_freq[year], annual_dir / f"frequency_{year}.tif")
    
    print("\nSaving event details...")
    events_dir = output_dir / "events"
    for year in ALL_YEARS:
        save_events_netcdf(events_by_year[year], lats, lons, year,
                          events_dir / f"events_{year}.nc", baseline_period)
    
    print(f"\nAll results saved to: {output_dir}")
    
    return total_freq, annual_freq


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Flash Drought Detection (Optimized)')
    parser.add_argument('--baseline', default='1980_2024', 
                       choices=['1980_2024', '1981_2010'])
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--test', action='store_true', help='Test mode - process 10 rows')
    
    args = parser.parse_args()
    
    if args.test:
        # Test with a few rows near the equator (more likely to have data)
        test_rows = [900, 901, 902, 903, 904, 549, 550, 551, 552, 553]
        run_flash_drought_detection(args.baseline, args.workers, test_rows)
    else:
        run_flash_drought_detection(args.baseline, args.workers)
