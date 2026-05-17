#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
4D Drought Event Tracking for GLEAM SMrz Data.

This script tracks drought events across time by connecting 2D spatial
clusters from consecutive days based on overlap ratio. It handles event
splitting and merging scenarios.

Unlike the original cluster2.py (which connects 3D lon×lat×depth clusters 
across time), this version works with 2D lon×lat clusters from single-layer
soil moisture data.

The algorithm:
1. Load 2D drought boolean masks for each day
2. Identify 2D connected drought clusters each day
3. Track clusters across time using overlap ratio
4. Handle splitting (one event → multiple) and merging (multiple → one)
5. Output each complete event as a separate file

Usage:
    python track_4D_SMrz.py --year 2020 --start_doy 121 --end_doy 273

Author: Auto-generated  
Date: 2026-01-23
"""

import numpy as np
from scipy import ndimage
from scipy import io as sio
import os
import argparse
import xarray as xr
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
#                           CONFIGURATION
# ============================================================================

# Default paths
DEFAULT_INPUT_DIR = '/data/GLEAM/drought_3D/sm_bool'
DEFAULT_OUTPUT_DIR = '/data/GLEAM/drought_3D/events'

# Tracking parameters
OVERLAP_THRESHOLD = 0.5  # Minimum overlap ratio to consider same event
MIN_CLUSTER_SIZE = 10    # Minimum 2D cluster size to keep (grid cells)
MIN_EVENT_DURATION = 1   # Minimum event duration (days) to save

# ============================================================================
#                           HELPER FUNCTIONS
# ============================================================================

def load_daily_mask(input_dir, year, doy):
    """Load a single day's drought boolean mask."""
    filepath = os.path.join(input_dir, str(year), f'SMrz_bool_{doy}.nc')
    
    if not os.path.exists(filepath):
        return None, None, None
    
    ds = xr.open_dataset(filepath)
    mask = ds['SMI'].values  # shape: (lat, lon)
    lat_coord = ds['lat'].values
    lon_coord = ds['lon'].values
    ds.close()
    
    return mask, lat_coord, lon_coord


def identify_daily_clusters(mask, min_size=10):
    """
    Identify 2D connected drought clusters in a daily mask.
    
    Parameters
    ----------
    mask : np.ndarray
        2D boolean mask (lat, lon)
    min_size : int
        Minimum cluster size to keep
    
    Returns
    -------
    labels : np.ndarray
        2D label array
    n_clusters : int
        Number of valid clusters
    cluster_locs : list
        List of dicts with x/y locations for each cluster
    """
    # 2D connected component analysis (8-connectivity)
    structure = np.ones((3, 3), dtype=int)
    labels, n_features = ndimage.label(mask, structure=structure)
    
    cluster_locs = []
    valid_labels = []
    
    for i in range(1, n_features + 1):
        indices = np.where(labels == i)
        if len(indices[0]) >= min_size:
            cluster_locs.append({
                'yloc': indices[0].tolist(),  # lat indices
                'xloc': indices[1].tolist()   # lon indices
            })
            valid_labels.append(i)
    
    # Relabel to keep only valid clusters
    if len(valid_labels) < n_features:
        new_labels = np.zeros_like(labels)
        for new_id, old_id in enumerate(valid_labels, 1):
            new_labels[labels == old_id] = new_id
        labels = new_labels
    
    return labels, len(cluster_locs), cluster_locs


def calculate_overlap(loc1, loc2, shape):
    """
    Calculate overlap ratio between two cluster locations.
    
    Overlap = intersection / min(size1, size2)
    """
    # Create masks
    mask1 = np.zeros(shape, dtype=bool)
    mask2 = np.zeros(shape, dtype=bool)
    
    for y, x in zip(loc1['yloc'], loc1['xloc']):
        mask1[y, x] = True
    
    for y, x in zip(loc2['yloc'], loc2['xloc']):
        mask2[y, x] = True
    
    intersection = np.sum(mask1 & mask2)
    min_size = min(np.sum(mask1), np.sum(mask2))
    
    if min_size == 0:
        return 0.0
    
    return intersection / min_size


def track_events(input_dir, year, doy_list, overlap_threshold=0.5, 
                 min_cluster_size=10, min_duration=1):
    """
    Track drought events across multiple days.
    
    Parameters
    ----------
    input_dir : str
        Directory with boolean mask files
    year : int
        Year to process
    doy_list : list
        List of day-of-year values to process
    overlap_threshold : float
        Minimum overlap ratio to link clusters
    min_cluster_size : int
        Minimum 2D cluster size
    min_duration : int
        Minimum event duration (days)
    
    Returns
    -------
    tracks : list
        List of completed event tracks
    """
    # Initialize tracking structures
    search = []  # Active event pool
    tracks = []  # Completed events
    
    shape = None  # Will be set on first data load
    
    for i, doy in enumerate(tqdm(doy_list, desc="Tracking events")):
        # Load daily mask
        mask, lat_coord, lon_coord = load_daily_mask(input_dir, year, doy)
        
        if mask is None:
            continue
        
        if shape is None:
            shape = mask.shape
        
        # Identify clusters for this day
        labels, n_clusters, cluster_locs = identify_daily_clusters(
            mask, min_size=min_cluster_size
        )
        
        if i == 0:
            # First day: initialize all clusters as new events
            for loc in cluster_locs:
                event = {
                    'day': [doy],
                    'xloc': [loc['xloc']],
                    'yloc': [loc['yloc']]
                }
                search.append(event)
        else:
            # Subsequent days: try to link with previous events
            count = np.zeros(len(cluster_locs))  # Track which clusters are linked
            
            for event_idx, event in enumerate(search):
                # Only check events that were active on previous day
                if event['day'][-1] != doy_list[i-1]:
                    continue
                
                # Get previous location
                prev_loc = {
                    'xloc': event['xloc'][-1],
                    'yloc': event['yloc'][-1]
                }
                
                # Calculate overlap with all current clusters
                overlaps = []
                for loc in cluster_locs:
                    overlap = calculate_overlap(prev_loc, loc, shape)
                    overlaps.append(overlap)
                
                overlaps = np.array(overlaps)
                matching_indices = np.where(overlaps >= overlap_threshold)[0]
                
                if len(matching_indices) > 0:
                    # Link to matching cluster(s)
                    merged_xloc = []
                    merged_yloc = []
                    
                    for idx in matching_indices:
                        merged_xloc.extend(cluster_locs[idx]['xloc'])
                        merged_yloc.extend(cluster_locs[idx]['yloc'])
                        count[idx] += 1
                    
                    event['day'].append(doy)
                    event['xloc'].append(merged_xloc)
                    event['yloc'].append(merged_yloc)
            
            # Create new events for unlinked clusters
            for idx, loc in enumerate(cluster_locs):
                if count[idx] == 0:
                    event = {
                        'day': [doy],
                        'xloc': [loc['xloc']],
                        'yloc': [loc['yloc']]
                    }
                    search.append(event)
            
            # Move inactive events to completed tracks
            inactive_mask = []
            for event in search:
                is_inactive = event['day'][-1] < doy
                inactive_mask.append(is_inactive)
                if is_inactive:
                    tracks.append(event)
            
            search = [e for e, inactive in zip(search, inactive_mask) if not inactive]
    
    # Add remaining active events to tracks
    tracks.extend(search)
    
    # Filter by minimum duration
    tracks = [t for t in tracks if len(t['day']) >= min_duration]
    
    print(f"Found {len(tracks)} events with duration >= {min_duration} days")
    
    return tracks, lat_coord, lon_coord


def save_events(tracks, output_dir, year, lat_coord, lon_coord):
    """
    Save event tracks to individual text files.
    
    Each file contains: day, x_idx, y_idx (one row per grid cell)
    """
    year_output_dir = os.path.join(output_dir, str(year))
    os.makedirs(year_output_dir, exist_ok=True)
    
    for i, event in enumerate(tracks):
        # Flatten event data
        all_days = []
        all_x = []
        all_y = []
        
        for j, day in enumerate(event['day']):
            n_cells = len(event['xloc'][j])
            all_days.extend([day] * n_cells)
            all_x.extend(event['xloc'][j])
            all_y.extend(event['yloc'][j])
        
        # Stack into matrix
        matrix = np.column_stack([all_days, all_x, all_y])
        
        # Save
        output_file = os.path.join(year_output_dir, f'{i+1}.txt')
        np.savetxt(output_file, matrix, fmt='%d')
    
    # Also save summary
    summary_file = os.path.join(year_output_dir, 'summary.txt')
    with open(summary_file, 'w') as f:
        f.write(f"Year: {year}\n")
        f.write(f"Total events: {len(tracks)}\n")
        f.write(f"Lat range: {lat_coord.min():.2f} to {lat_coord.max():.2f}\n")
        f.write(f"Lon range: {lon_coord.min():.2f} to {lon_coord.max():.2f}\n")
        f.write("\n")
        f.write("Event_ID\tStart_DOY\tEnd_DOY\tDuration\tMax_Size\n")
        for i, event in enumerate(tracks):
            duration = len(event['day'])
            max_size = max(len(x) for x in event['xloc'])
            f.write(f"{i+1}\t{event['day'][0]}\t{event['day'][-1]}\t{duration}\t{max_size}\n")
    
    print(f"Saved {len(tracks)} events to {year_output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description='4D Drought Event Tracking for GLEAM SMrz'
    )
    parser.add_argument('--input_dir', type=str, default=DEFAULT_INPUT_DIR,
                        help='Input directory with boolean masks')
    parser.add_argument('--output_dir', type=str, default=DEFAULT_OUTPUT_DIR,
                        help='Output directory for event files')
    parser.add_argument('--year', type=int, required=True,
                        help='Year to process')
    parser.add_argument('--start_doy', type=int, default=1,
                        help='Start day of year')
    parser.add_argument('--end_doy', type=int, default=365,
                        help='End day of year')
    parser.add_argument('--overlap', type=float, default=OVERLAP_THRESHOLD,
                        help='Overlap threshold for event linking')
    parser.add_argument('--min_size', type=int, default=MIN_CLUSTER_SIZE,
                        help='Minimum cluster size (grid cells)')
    parser.add_argument('--min_duration', type=int, default=MIN_EVENT_DURATION,
                        help='Minimum event duration (days)')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("4D Drought Event Tracking for GLEAM SMrz")
    print("=" * 60)
    print(f"Input: {args.input_dir}")
    print(f"Output: {args.output_dir}")
    print(f"Year: {args.year}")
    print(f"DOY range: {args.start_doy} - {args.end_doy}")
    print(f"Overlap threshold: {args.overlap}")
    print(f"Min cluster size: {args.min_size}")
    print(f"Min event duration: {args.min_duration}")
    print("=" * 60)
    
    # Create DOY list
    doy_list = list(range(args.start_doy, args.end_doy + 1))
    
    # Track events
    tracks, lat_coord, lon_coord = track_events(
        args.input_dir, args.year, doy_list,
        overlap_threshold=args.overlap,
        min_cluster_size=args.min_size,
        min_duration=args.min_duration
    )
    
    # Save results
    if len(tracks) > 0:
        save_events(tracks, args.output_dir, args.year, lat_coord, lon_coord)
    else:
        print("No events found.")
    
    print("\nProcessing complete!")


if __name__ == '__main__':
    main()
