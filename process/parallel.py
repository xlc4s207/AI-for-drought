"""
Flash Drought Detection System - Parallel Processing
=====================================================
Parallel processing framework for efficient pixel-by-pixel computation.
"""

import numpy as np
from multiprocessing import Pool, cpu_count
from typing import List, Dict, Tuple
from tqdm import tqdm
import time

from config import (
    N_WORKERS, BATCH_SIZE, CHECKPOINT_INTERVAL,
    ALL_YEARS, BASELINE_PERIODS, RESULT_DIR,
    OUTPUT_ANNUAL_FREQ_DIR, OUTPUT_EVENTS_DIR,
    TOTAL_FREQ_FILENAME, ANNUAL_FREQ_PATTERN, EVENTS_PATTERN,
    N_LAT, N_LON, NODATA_VALUE, MAX_EVENTS_PER_PIXEL
)
from utils import (
    get_valid_pixels, get_lat_lon_arrays,
    save_geotiff, save_events_netcdf
)
from flash_drought import process_pixel_wrapper, FlashDroughtEvent


def initialize_result_arrays() -> Dict:
    """
    Initialize empty result arrays for storing outputs.
    
    Returns:
        Dictionary containing initialized arrays
    """
    return {
        'total_frequency': np.full((N_LAT, N_LON), NODATA_VALUE, dtype=np.float32),
        'annual_frequency': {
            year: np.full((N_LAT, N_LON), NODATA_VALUE, dtype=np.float32)
            for year in ALL_YEARS
        },
        'events': {
            year: {
                'start_doy': np.full((N_LAT, N_LON, MAX_EVENTS_PER_PIXEL), NODATA_VALUE, dtype=np.int16),
                'end_doy': np.full((N_LAT, N_LON, MAX_EVENTS_PER_PIXEL), NODATA_VALUE, dtype=np.int16),
                'duration': np.full((N_LAT, N_LON, MAX_EVENTS_PER_PIXEL), NODATA_VALUE, dtype=np.int16),
                'intensity': np.full((N_LAT, N_LON, MAX_EVENTS_PER_PIXEL), np.nan, dtype=np.float32),
            }
            for year in ALL_YEARS
        }
    }


def update_results_from_pixel(results: Dict, pixel_result: Dict) -> None:
    """
    Update result arrays with data from a single pixel.
    
    Args:
        results: Result arrays dictionary
        pixel_result: Result from process_single_pixel
    """
    lat_idx = pixel_result['lat_idx']
    lon_idx = pixel_result['lon_idx']
    
    if not pixel_result['valid']:
        return
    
    # Update total frequency
    results['total_frequency'][lat_idx, lon_idx] = pixel_result['total_count']
    
    # Update annual frequency
    for year, count in pixel_result['annual_counts'].items():
        results['annual_frequency'][year][lat_idx, lon_idx] = count
    
    # Update event details
    events_by_year = {}
    for event in pixel_result['events']:
        year = event.year
        if year not in events_by_year:
            events_by_year[year] = []
        events_by_year[year].append(event)
    
    for year, events in events_by_year.items():
        if year not in results['events']:
            continue
            
        for i, event in enumerate(events[:MAX_EVENTS_PER_PIXEL]):
            results['events'][year]['start_doy'][lat_idx, lon_idx, i] = event.start_doy
            results['events'][year]['end_doy'][lat_idx, lon_idx, i] = event.end_doy
            results['events'][year]['duration'][lat_idx, lon_idx, i] = event.duration
            results['events'][year]['intensity'][lat_idx, lon_idx, i] = event.intensity


def save_all_results(results: Dict, baseline_period: str, lats: np.ndarray, lons: np.ndarray) -> None:
    """
    Save all results to files.
    
    Args:
        results: Result arrays dictionary
        baseline_period: Baseline period key
        lats: Latitude array
        lons: Longitude array
    """
    import xarray as xr
    
    # Create output directory for this baseline
    output_dir = RESULT_DIR / f"baseline_{baseline_period}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save total frequency GeoTIFF
    save_geotiff(
        results['total_frequency'],
        output_dir / TOTAL_FREQ_FILENAME
    )
    
    # Save annual frequency GeoTIFFs
    annual_dir = output_dir / OUTPUT_ANNUAL_FREQ_DIR
    annual_dir.mkdir(parents=True, exist_ok=True)
    
    for year in ALL_YEARS:
        save_geotiff(
            results['annual_frequency'][year],
            annual_dir / ANNUAL_FREQ_PATTERN.format(year=year)
        )
    
    # Save event details to NetCDF (one file per year)
    events_dir = output_dir / OUTPUT_EVENTS_DIR
    events_dir.mkdir(parents=True, exist_ok=True)
    
    for year in ALL_YEARS:
        event_data = results['events'][year]
        
        ds = xr.Dataset(
            {
                'start_doy': (['lat', 'lon', 'event'], event_data['start_doy']),
                'end_doy': (['lat', 'lon', 'event'], event_data['end_doy']),
                'duration': (['lat', 'lon', 'event'], event_data['duration']),
                'intensity': (['lat', 'lon', 'event'], event_data['intensity']),
            },
            coords={
                'lat': lats,
                'lon': lons,
                'event': np.arange(MAX_EVENTS_PER_PIXEL)
            },
            attrs={
                'title': f'Flash Drought Events {year}',
                'description': 'Flash drought event details detected from GLEAM SMrz data',
                'source': 'GLEAM v4.2a',
                'baseline_period': baseline_period,
                'conventions': 'CF-1.8'
            }
        )
        
        save_events_netcdf(ds, events_dir / EVENTS_PATTERN.format(year=year))


def parallel_process_pixels(
    valid_pixels: np.ndarray,
    baseline_period: str = "1980_2024",
    n_workers: int = None,
    test_mode: bool = False,
    test_pixels: int = 100
) -> Dict:
    """
    Process all valid pixels in parallel.
    
    Args:
        valid_pixels: Array of valid pixel indices (N, 2)
        baseline_period: Baseline period key
        n_workers: Number of parallel workers (None = use config default)
        test_mode: If True, only process a subset of pixels
        test_pixels: Number of pixels to process in test mode
        
    Returns:
        Result arrays dictionary
    """
    if n_workers is None:
        n_workers = N_WORKERS
    
    # In test mode, only process a subset
    if test_mode:
        np.random.seed(42)
        indices = np.random.choice(len(valid_pixels), min(test_pixels, len(valid_pixels)), replace=False)
        valid_pixels = valid_pixels[indices]
    
    total_pixels = len(valid_pixels)
    print(f"\n{'='*60}")
    print(f"Flash Drought Detection - Parallel Processing")
    print(f"{'='*60}")
    print(f"Total pixels to process: {total_pixels:,}")
    print(f"Baseline period: {baseline_period}")
    print(f"Number of workers: {n_workers}")
    print(f"{'='*60}\n")
    
    # Prepare arguments for parallel processing
    args_list = [
        (int(lat_idx), int(lon_idx), baseline_period)
        for lat_idx, lon_idx in valid_pixels
    ]
    
    # Initialize result arrays
    results = initialize_result_arrays()
    
    # Get lat/lon arrays for output
    lats, lons = get_lat_lon_arrays()
    
    start_time = time.time()
    processed = 0
    events_found = 0
    
    # Process in parallel with progress bar
    print("Processing pixels...")
    
    with Pool(processes=n_workers) as pool:
        # Use imap for memory-efficient processing with progress updates
        with tqdm(total=total_pixels, desc="Processing", unit="pixels") as pbar:
            for pixel_result in pool.imap(process_pixel_wrapper, args_list, chunksize=BATCH_SIZE):
                update_results_from_pixel(results, pixel_result)
                processed += 1
                events_found += pixel_result['total_count']
                pbar.update(1)
                
                # Print periodic updates
                if processed % CHECKPOINT_INTERVAL == 0:
                    elapsed = time.time() - start_time
                    rate = processed / elapsed
                    remaining = (total_pixels - processed) / rate if rate > 0 else 0
                    print(f"\n  Checkpoint: {processed:,} pixels processed, "
                          f"{events_found:,} events found, "
                          f"ETA: {remaining/60:.1f} min")
    
    elapsed_time = time.time() - start_time
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Processing Complete!")
    print(f"{'='*60}")
    print(f"Total time: {elapsed_time/60:.1f} minutes")
    print(f"Pixels processed: {processed:,}")
    print(f"Total events found: {events_found:,}")
    print(f"Average events per pixel: {events_found/processed:.2f}" if processed > 0 else "N/A")
    print(f"{'='*60}\n")
    
    # Save results
    print("Saving results...")
    save_all_results(results, baseline_period, lats, lons)
    
    return results


def run_single_pixel_test(lat: float, lon: float, baseline_period: str = "1980_2024") -> Dict:
    """
    Run flash drought detection on a single pixel for testing.
    
    Args:
        lat: Latitude coordinate
        lon: Longitude coordinate
        baseline_period: Baseline period key
        
    Returns:
        Detailed results for the pixel
    """
    from utils import latlon_to_idx
    from flash_drought import process_single_pixel
    
    lats, lons = get_lat_lon_arrays()
    lat_idx, lon_idx = latlon_to_idx(lat, lon, lats, lons)
    
    print(f"\n{'='*60}")
    print(f"Single Pixel Test")
    print(f"{'='*60}")
    print(f"Location: ({lat:.2f}°N, {lon:.2f}°E)")
    print(f"Grid indices: (lat_idx={lat_idx}, lon_idx={lon_idx})")
    print(f"Baseline period: {baseline_period}")
    print(f"{'='*60}\n")
    
    start_time = time.time()
    result = process_single_pixel(lat_idx, lon_idx, baseline_period)
    elapsed = time.time() - start_time
    
    print(f"Processing time: {elapsed:.2f} seconds")
    print(f"Valid pixel: {result['valid']}")
    print(f"Total events: {result['total_count']}")
    
    if result['events']:
        print(f"\nEvent Details:")
        print("-" * 50)
        for i, event in enumerate(result['events'], 1):
            print(f"  Event {i}:")
            print(f"    Year: {event.year}")
            print(f"    Start DOY: {event.start_doy}")
            print(f"    End DOY: {event.end_doy}")
            print(f"    Duration: {event.duration} days")
            print(f"    Intensity: {event.intensity:.4f}")
    
    print(f"\nAnnual Event Counts:")
    print("-" * 50)
    for year, count in result['annual_counts'].items():
        if count > 0:
            print(f"  {year}: {count} event(s)")
    
    return result
