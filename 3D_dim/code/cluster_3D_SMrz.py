#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
3D (lon, lat, time) drought clustering for single-layer soil moisture data.

This script performs spatial-temporal connected component analysis on 
drought boolean masks from GLEAM SMrz data. Unlike the original cluster1.py
which handles 3D spatial (lon, lat, depth), this script treats time as the
third dimension for 2D spatial data.

The algorithm:
1. Load consecutive days of drought boolean masks
2. Stack them into a 3D array (lon, lat, time)
3. Use connected component analysis to identify drought events

Usage:
    mpirun -np 4 python cluster_3D_SMrz.py --year 2020 --start_doy 121 --end_doy 273

Author: Auto-generated
Date: 2026-01-23
"""

import numpy as np
import scipy.io as scio
import cc3d
import os
import argparse
from netCDF4 import Dataset
import xarray as xr
from mpi4py import MPI
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
#                           CONFIGURATION
# ============================================================================

# Default paths
DEFAULT_INPUT_DIR = '/data/GLEAM/drought_3D/sm_bool'
DEFAULT_OUTPUT_DIR = '/data/GLEAM/drought_3D/cluster1'

# Connectivity criterion for 3D clustering
# 6: face-connected (strict)
# 18: face + edge connected
# 26: face + edge + corner connected (most permissive)
CONNECTIVITY = 26

# Minimum cluster size (filter out small noise)
MIN_CLUSTER_SIZE = 10

# Time window size for each chunk (days)
TIME_WINDOW = 30

# ============================================================================
#                           MAIN FUNCTIONS
# ============================================================================

def load_daily_masks(input_dir, year, doy_list):
    """
    Load daily drought boolean masks and stack into 3D array.
    
    Parameters
    ----------
    input_dir : str
        Directory containing year subdirectories with daily NetCDF files
    year : int
        Year to process
    doy_list : list
        List of day-of-year values to load
    
    Returns
    -------
    data_3d : np.ndarray
        3D boolean array (lon, lat, time)
    lat_coord : np.ndarray
        Latitude coordinate
    lon_coord : np.ndarray
        Longitude coordinate
    valid_doys : list
        List of DOYs that were successfully loaded
    """
    year_dir = os.path.join(input_dir, str(year))
    
    data_list = []
    valid_doys = []
    lat_coord = None
    lon_coord = None
    
    for doy in doy_list:
        filepath = os.path.join(year_dir, f'SMrz_bool_{doy}.nc')
        
        if not os.path.exists(filepath):
            continue
        
        try:
            ds = xr.open_dataset(filepath)
            mask = ds['SMI'].values  # shape: (lat, lon)
            
            if lat_coord is None:
                lat_coord = ds['lat'].values
                lon_coord = ds['lon'].values
            
            ds.close()
            
            # Transpose to (lon, lat) and add to list
            data_list.append(mask.T)
            valid_doys.append(doy)
            
        except Exception as e:
            print(f"Warning: Could not load {filepath}: {e}")
            continue
    
    if len(data_list) == 0:
        return None, None, None, []
    
    # Stack into 3D array (lon, lat, time)
    data_3d = np.stack(data_list, axis=2)
    
    return data_3d, lat_coord, lon_coord, valid_doys


def cluster_3d_drought(data_3d, connectivity=26, min_size=10):
    """
    Perform 3D connected component analysis on drought data.
    
    Parameters
    ----------
    data_3d : np.ndarray
        3D boolean array (lon, lat, time)
    connectivity : int
        Connectivity criterion (6, 18, or 26)
    min_size : int
        Minimum cluster size to keep
    
    Returns
    -------
    labels : np.ndarray
        3D label array (same shape as input)
    n_clusters : int
        Number of clusters found
    cluster_sizes : list
        Size of each cluster
    """
    # Ensure binary input
    binary_data = (data_3d > 0).astype(np.uint8)
    
    # Perform connected component analysis
    labels, n_clusters = cc3d.connected_components(
        binary_data, 
        connectivity=connectivity, 
        return_N=True
    )
    
    # Calculate cluster sizes
    cluster_sizes = []
    for i in range(1, n_clusters + 1):
        size = np.sum(labels == i)
        cluster_sizes.append(size)
    
    # Filter small clusters
    if min_size > 0:
        for i, size in enumerate(cluster_sizes):
            if size < min_size:
                labels[labels == (i + 1)] = 0
    
    return labels, n_clusters, cluster_sizes


def process_time_chunk(input_dir, output_dir, year, start_doy, end_doy,
                       connectivity=26, min_size=10):
    """
    Process a chunk of days for a given year.
    
    Parameters
    ----------
    input_dir : str
        Input directory with boolean masks
    output_dir : str
        Output directory for cluster results
    year : int
        Year to process
    start_doy : int
        Start day of year
    end_doy : int
        End day of year
    connectivity : int
        Connectivity for cc3d
    min_size : int
        Minimum cluster size
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Create list of days to process
    doy_list = list(range(start_doy, end_doy + 1))
    
    print(f"Loading data for year {year}, DOY {start_doy}-{end_doy}...")
    
    # Load data
    data_3d, lat_coord, lon_coord, valid_doys = load_daily_masks(
        input_dir, year, doy_list
    )
    
    if data_3d is None:
        print(f"No data found for year {year}, DOY {start_doy}-{end_doy}")
        return
    
    print(f"Loaded {len(valid_doys)} days, data shape: {data_3d.shape}")
    
    # Perform clustering
    print("Performing 3D connected component analysis...")
    labels, n_clusters, sizes = cluster_3d_drought(
        data_3d, connectivity=connectivity, min_size=min_size
    )
    
    print(f"Found {n_clusters} clusters")
    
    # Save results
    output_file = os.path.join(
        output_dir, 
        f'cluster3D_{year}_{start_doy:03d}_{end_doy:03d}.mat'
    )
    
    scio.savemat(output_file, {
        'cluster': labels,
        'N': n_clusters,
        'L': sizes,
        'doy_list': valid_doys,
        'year': year
    })
    
    print(f"Saved to {output_file}")
    
    return labels, n_clusters, sizes


def main():
    parser = argparse.ArgumentParser(
        description='3D drought clustering for GLEAM SMrz'
    )
    parser.add_argument('--input_dir', type=str, default=DEFAULT_INPUT_DIR,
                        help='Input directory with boolean masks')
    parser.add_argument('--output_dir', type=str, default=DEFAULT_OUTPUT_DIR,
                        help='Output directory for cluster results')
    parser.add_argument('--year', type=int, required=True,
                        help='Year to process')
    parser.add_argument('--start_doy', type=int, default=1,
                        help='Start day of year')
    parser.add_argument('--end_doy', type=int, default=365,
                        help='End day of year')
    parser.add_argument('--connectivity', type=int, default=CONNECTIVITY,
                        choices=[6, 18, 26],
                        help='3D connectivity criterion')
    parser.add_argument('--min_size', type=int, default=MIN_CLUSTER_SIZE,
                        help='Minimum cluster size to keep')
    parser.add_argument('--window', type=int, default=TIME_WINDOW,
                        help='Time window size for chunked processing')
    parser.add_argument('--no_mpi', action='store_true',
                        help='Disable MPI parallelization')
    
    args = parser.parse_args()
    
    # MPI setup
    if not args.no_mpi:
        comm = MPI.COMM_WORLD
        rank = comm.rank
        size = comm.size
    else:
        rank = 0
        size = 1
    
    if rank == 0:
        print("=" * 60)
        print("3D Drought Clustering for GLEAM SMrz")
        print("=" * 60)
        print(f"Input: {args.input_dir}")
        print(f"Output: {args.output_dir}")
        print(f"Year: {args.year}")
        print(f"DOY range: {args.start_doy} - {args.end_doy}")
        print(f"Connectivity: {args.connectivity}")
        print(f"Min cluster size: {args.min_size}")
        print(f"MPI processes: {size}")
        print("=" * 60)
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Divide work among MPI ranks
    total_days = args.end_doy - args.start_doy + 1
    n_windows = int(np.ceil(total_days / args.window))
    
    # Create list of (start_doy, end_doy) chunks
    chunks = []
    for i in range(n_windows):
        chunk_start = args.start_doy + i * args.window
        chunk_end = min(chunk_start + args.window - 1, args.end_doy)
        chunks.append((chunk_start, chunk_end))
    
    # Distribute chunks across MPI ranks
    my_chunks = [chunks[i] for i in range(len(chunks)) if i % size == rank]
    
    if rank == 0:
        print(f"Total chunks: {len(chunks)}, this rank processes: {len(my_chunks)}")
    
    # Process assigned chunks
    for start_doy, end_doy in my_chunks:
        print(f"Rank {rank}: Processing DOY {start_doy}-{end_doy}")
        
        process_time_chunk(
            args.input_dir, args.output_dir, args.year,
            start_doy, end_doy,
            connectivity=args.connectivity,
            min_size=args.min_size
        )
    
    if not args.no_mpi:
        comm.Barrier()
    
    if rank == 0:
        print("\nAll processing complete!")


if __name__ == '__main__':
    main()
