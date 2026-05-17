"""
Simple test script for flash drought detection.
Tests single pixel processing without parallel overhead.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
import numpy as np

print("=" * 60)
print("Flash Drought Detection - Simple Test")
print("=" * 60)

# Test 1: Import modules
print("\n[1/4] Testing imports...")
try:
    from config import DATA_DIR, ALL_YEARS, RESULT_DIR
    from utils import get_valid_pixels, get_lat_lon_arrays, extract_pixel_timeseries
    from utils import compute_5day_moving_average, compute_doy_percentiles
    from flash_drought import detect_flash_drought_events, process_single_pixel
    print("    ✓ All modules imported successfully")
except Exception as e:
    print(f"    ✗ Import error: {e}")
    sys.exit(1)

# Test 2: Check data files
print("\n[2/4] Checking data files...")
print(f"    Data directory: {DATA_DIR}")
nc_files = list(DATA_DIR.glob("*.nc"))
print(f"    Found {len(nc_files)} NC files")
print(f"    Year range: {ALL_YEARS[0]} - {ALL_YEARS[-1]}")

# Test 3: Get valid pixels
print("\n[3/4] Loading valid pixel mask...")
start = time.time()
valid_pixels = get_valid_pixels()
print(f"    Time: {time.time() - start:.2f}s")
print(f"    Valid pixels: {len(valid_pixels):,}")

# Test 4: Process a test pixel
print("\n[4/4] Processing test pixel (35°N, 115°E)...")
lats, lons = get_lat_lon_arrays()

# Find index for test location
test_lat, test_lon = 35.0, 115.0
lat_idx = np.argmin(np.abs(lats - test_lat))
lon_idx = np.argmin(np.abs(lons - test_lon))
print(f"    Grid indices: ({lat_idx}, {lon_idx})")
print(f"    Actual coords: ({lats[lat_idx]:.2f}°N, {lons[lon_idx]:.2f}°E)")

start = time.time()
result = process_single_pixel(lat_idx, lon_idx, "1980_2024")
elapsed = time.time() - start

print(f"    Processing time: {elapsed:.2f}s")
print(f"    Valid data: {result['valid']}")
print(f"    Total events: {result['total_count']}")

if result['events']:
    print("\n    Event Summary:")
    print("    " + "-" * 50)
    for i, event in enumerate(result['events'][:5], 1):
        print(f"    {i}. Year {event.year}: DOY {event.start_doy}-{event.end_doy}, "
              f"{event.duration}d, intensity={event.intensity:.3f}")
    if len(result['events']) > 5:
        print(f"    ... and {len(result['events']) - 5} more events")

# Summary
print("\n" + "=" * 60)
print("Test Complete!")
print(f"Result directory: {RESULT_DIR}")
print("=" * 60)
