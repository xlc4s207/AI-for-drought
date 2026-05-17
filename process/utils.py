"""
Flash Drought Detection System - Utility Functions
===================================================
IO operations, percentile calculation, and data processing utilities.
"""

import numpy as np
import xarray as xr
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS
from pathlib import Path
from typing import Tuple, List, Optional, Dict
import warnings

from config import (
    DATA_DIR, NC_FILE_PATTERN, VARIABLE_NAME, ALL_YEARS,
    N_LAT, N_LON, LAT_MIN, LAT_MAX, LON_MIN, LON_MAX,
    RESOLUTION, NODATA_VALUE, MOVING_AVG_WINDOW,
    P_HIGH, P_LOW, P_DECLINE_RATE, MAX_EVENTS_PER_PIXEL
)

warnings.filterwarnings('ignore')


# =============================================================================
# Data Loading Functions
# =============================================================================

def get_nc_filepath(year: int) -> Path:
    """Get the file path for a specific year's NC file."""
    filename = NC_FILE_PATTERN.format(year=year)
    return DATA_DIR / filename


def get_valid_pixels() -> np.ndarray:
    """
    Extract valid land pixel coordinates from the first NC file.
    Returns array of shape (N_valid, 2) with (lat_idx, lon_idx) pairs.
    """
    # Open first year's file to get land mask
    first_file = get_nc_filepath(ALL_YEARS[0])
    
    with xr.open_dataset(first_file) as ds:
        # Get first time step to check for valid data
        data = ds[VARIABLE_NAME].isel(time=0).values
        
        # Valid pixels are those that are not NaN
        valid_mask = ~np.isnan(data)
        
        # Get indices of valid pixels
        valid_indices = np.argwhere(valid_mask)
        
    print(f"Found {len(valid_indices):,} valid land pixels out of {N_LAT * N_LON:,} total pixels")
    return valid_indices


def get_lat_lon_arrays() -> Tuple[np.ndarray, np.ndarray]:
    """Get latitude and longitude coordinate arrays."""
    first_file = get_nc_filepath(ALL_YEARS[0])
    
    with xr.open_dataset(first_file) as ds:
        lats = ds['lat'].values
        lons = ds['lon'].values
        
    return lats, lons


def extract_pixel_timeseries(lat_idx: int, lon_idx: int, years: List[int] = None) -> Tuple[np.ndarray, np.ndarray]:
    """
    Extract complete time series for a single pixel across all years.
    
    Args:
        lat_idx: Latitude index in the grid
        lon_idx: Longitude index in the grid  
        years: List of years to extract (default: all years)
        
    Returns:
        Tuple of (dates array, values array)
    """
    if years is None:
        years = ALL_YEARS
        
    all_values = []
    all_dates = []
    
    for year in years:
        filepath = get_nc_filepath(year)
        
        with xr.open_dataset(filepath) as ds:
            # Extract single pixel time series for this year
            pixel_data = ds[VARIABLE_NAME][:, lat_idx, lon_idx].values
            dates = ds['time'].values
            
            all_values.append(pixel_data)
            all_dates.append(dates)
    
    # Concatenate all years
    values = np.concatenate(all_values)
    dates = np.concatenate(all_dates)
    
    return dates, values


# =============================================================================
# Statistical Functions
# =============================================================================

def compute_5day_moving_average(values: np.ndarray) -> np.ndarray:
    """
    Compute 5-day moving average of the time series.
    Uses centered moving average with edge handling.
    """
    window = MOVING_AVG_WINDOW
    
    # Use convolution for efficient moving average
    kernel = np.ones(window) / window
    
    # Pad edges to maintain array length
    padded = np.pad(values, (window//2, window//2), mode='edge')
    moving_avg = np.convolve(padded, kernel, mode='valid')
    
    return moving_avg


def get_day_of_year(dates: np.ndarray) -> np.ndarray:
    """Extract day of year (1-366) from datetime array."""
    # Convert to pandas datetime for easy DOY extraction
    import pandas as pd
    dates_pd = pd.to_datetime(dates)
    return dates_pd.dayofyear.values


def compute_doy_percentiles(
    values: np.ndarray,
    dates: np.ndarray,
    baseline_years: Tuple[int, int]
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute DOY-based percentile thresholds for flash drought detection.
    
    Args:
        values: Full time series of 5-day moving average SM values
        dates: Corresponding dates
        baseline_years: (start_year, end_year) for baseline period
        
    Returns:
        Tuple of (p40_thresholds, p20_thresholds, decline_rate_p5) for DOY 1-366
    """
    import pandas as pd
    
    # Convert to pandas for easier date handling
    dates_pd = pd.to_datetime(dates)
    years = dates_pd.year.values
    doy = dates_pd.dayofyear.values
    
    # Filter to baseline period
    baseline_mask = (years >= baseline_years[0]) & (years <= baseline_years[1])
    baseline_values = values[baseline_mask]
    baseline_doy = doy[baseline_mask]
    
    # Initialize arrays for 366 possible DOYs
    p40_thresholds = np.full(367, np.nan)  # Index 0 unused, 1-366 for DOYs
    p20_thresholds = np.full(367, np.nan)
    decline_rate_p5 = np.full(367, np.nan)
    
    # Compute decline rates
    decline_rates = np.diff(baseline_values, prepend=baseline_values[0])
    baseline_decline = decline_rates[baseline_mask[:-1] if len(baseline_mask) > len(decline_rates) else baseline_mask[:len(decline_rates)]]
    
    # Recalculate for correct length
    decline_rates_full = np.diff(values, prepend=values[0])
    baseline_decline_rates = decline_rates_full[baseline_mask]
    baseline_doy_for_decline = doy[baseline_mask]
    
    for d in range(1, 367):
        # Get values for this DOY across all baseline years
        doy_mask = baseline_doy == d
        doy_values = baseline_values[doy_mask]
        
        if len(doy_values) > 0:
            p40_thresholds[d] = np.nanpercentile(doy_values, P_HIGH)
            p20_thresholds[d] = np.nanpercentile(doy_values, P_LOW)
        
        # Get decline rates for this DOY
        doy_decline_mask = baseline_doy_for_decline == d
        doy_decline_values = baseline_decline_rates[doy_decline_mask]
        
        if len(doy_decline_values) > 0:
            # P5 of decline rates (negative values = decrease)
            decline_rate_p5[d] = np.nanpercentile(doy_decline_values, P_DECLINE_RATE)
    
    return p40_thresholds, p20_thresholds, decline_rate_p5


# =============================================================================
# Output Functions
# =============================================================================

def save_geotiff(
    data: np.ndarray,
    output_path: Path,
    nodata: float = NODATA_VALUE
) -> None:
    """
    Save 2D array as GeoTIFF with proper georeferencing.
    
    Args:
        data: 2D array of shape (N_LAT, N_LON)
        output_path: Path to save the GeoTIFF
        nodata: NoData value
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create transform (affine transformation)
    transform = from_bounds(
        LON_MIN - RESOLUTION/2, LAT_MIN - RESOLUTION/2,
        LON_MAX + RESOLUTION/2, LAT_MAX + RESOLUTION/2,
        N_LON, N_LAT
    )
    
    # Flip data vertically (GeoTIFF uses top-left origin)
    # data_flipped = np.flipud(data)
    
    with rasterio.open(
        output_path,
        'w',
        driver='GTiff',
        height=N_LAT,
        width=N_LON,
        count=1,
        dtype=data.dtype,
        crs=CRS.from_epsg(4326),
        transform=transform,
        nodata=nodata,
        compress='lzw'
    ) as dst:
        dst.write(data, 1)
    
    print(f"Saved GeoTIFF: {output_path}")


def create_events_netcdf(
    output_path: Path,
    lats: np.ndarray,
    lons: np.ndarray
) -> xr.Dataset:
    """
    Create an empty NetCDF structure for storing event details.
    
    Args:
        output_path: Path to save the NetCDF file
        lats: Latitude array
        lons: Longitude array
        
    Returns:
        Empty xarray Dataset with proper structure
    """
    # Create coordinate arrays
    event_ids = np.arange(MAX_EVENTS_PER_PIXEL)
    
    # Create empty data arrays filled with NaN/NoData
    start_doy = np.full((len(lats), len(lons), MAX_EVENTS_PER_PIXEL), NODATA_VALUE, dtype=np.int16)
    end_doy = np.full((len(lats), len(lons), MAX_EVENTS_PER_PIXEL), NODATA_VALUE, dtype=np.int16)
    duration = np.full((len(lats), len(lons), MAX_EVENTS_PER_PIXEL), NODATA_VALUE, dtype=np.int16)
    intensity = np.full((len(lats), len(lons), MAX_EVENTS_PER_PIXEL), np.nan, dtype=np.float32)
    
    ds = xr.Dataset(
        {
            'start_doy': (['lat', 'lon', 'event'], start_doy),
            'end_doy': (['lat', 'lon', 'event'], end_doy),
            'duration': (['lat', 'lon', 'event'], duration),
            'intensity': (['lat', 'lon', 'event'], intensity),
        },
        coords={
            'lat': lats,
            'lon': lons,
            'event': event_ids
        },
        attrs={
            'title': 'Flash Drought Events',
            'description': 'Flash drought event details detected from GLEAM SMrz data',
            'source': 'GLEAM v4.2a',
            'conventions': 'CF-1.8'
        }
    )
    
    return ds


def save_events_netcdf(
    ds: xr.Dataset,
    output_path: Path
) -> None:
    """Save events dataset to NetCDF file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    encoding = {
        'start_doy': {'dtype': 'int16', 'zlib': True, 'complevel': 4},
        'end_doy': {'dtype': 'int16', 'zlib': True, 'complevel': 4},
        'duration': {'dtype': 'int16', 'zlib': True, 'complevel': 4},
        'intensity': {'dtype': 'float32', 'zlib': True, 'complevel': 4},
    }
    
    ds.to_netcdf(output_path, encoding=encoding)
    print(f"Saved NetCDF: {output_path}")


# =============================================================================
# Helper Functions
# =============================================================================

def idx_to_latlon(lat_idx: int, lon_idx: int, lats: np.ndarray, lons: np.ndarray) -> Tuple[float, float]:
    """Convert grid indices to lat/lon coordinates."""
    return lats[lat_idx], lons[lon_idx]


def latlon_to_idx(lat: float, lon: float, lats: np.ndarray, lons: np.ndarray) -> Tuple[int, int]:
    """Convert lat/lon coordinates to grid indices."""
    lat_idx = np.argmin(np.abs(lats - lat))
    lon_idx = np.argmin(np.abs(lons - lon))
    return lat_idx, lon_idx


def print_progress(current: int, total: int, prefix: str = "Progress"):
    """Print progress bar to terminal."""
    percent = current / total * 100
    bar_length = 50
    filled = int(bar_length * current / total)
    bar = '=' * filled + '-' * (bar_length - filled)
    print(f"\r{prefix}: [{bar}] {percent:.1f}% ({current:,}/{total:,})", end='', flush=True)
    if current == total:
        print()  # New line at completion
