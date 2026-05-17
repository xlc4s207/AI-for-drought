#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
01_build_event_master_table.py
==============================
Stage 1: Read 12 GLEAM carbon-flux event NC files, assign IGBP land-use class
and biome label from MCD12C1, filter valid events, output unified parquet.

Usage:
    /home/xulc/.local/share/mamba/envs/Flash_dra/bin/python 01_build_event_master_table.py
"""

import os
import sys
import time
import numpy as np
import pandas as pd
import xarray as xr
import rasterio
from rasterio.transform import rowcol

# ============================================================
# Configuration
# ============================================================
PYTHON_BIN = "/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
BASE_PROCESS = "/home/xulc/flash_drought/process"
OUTPUT_DIR = "/home/xulc/flash_drought/process/SEM_analysis/anti/GLEAM/data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

LAND_USE_TIF = "/home/xulc/flash_drought/land_use/MCD12C1_LC_Type1_2010_11km.tif"

# IGBP class -> biome mapping
IGBP_TO_BIOME = {
    1: "Forest", 2: "Forest", 3: "Forest", 4: "Forest", 5: "Forest",
    6: "Shrubland", 7: "Shrubland",
    8: "Savanna", 9: "Savanna",
    10: "Grassland",
    11: "Wetland",
    12: "Cropland", 14: "Cropland",
}
# Classes to exclude (water, urban, snow/ice, barren)
EXCLUDE_IGBP = {0, 13, 15, 16, 255}

# 12 GLEAM target files
EVENT_FILES = {
    # (metric, code_id, drought_type, soil_layer): path
    ("GPP", "code1", "flash", "SMrz"): os.path.join(
        BASE_PROCESS, "GPP-draught-analysis/code1/results/"
        "gpp_response_SMrz_events_global_v20260328_latfix_"
        "rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("GPP", "code2", "flash", "SMs"): os.path.join(
        BASE_PROCESS, "GPP-draught-analysis/code2_SMs/results/"
        "gpp_response_SMs_events_global_v20260328_latfix_"
        "rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("GPP", "code3", "nonflash", "SMrz"): os.path.join(
        BASE_PROCESS, "GPP-draught-analysis/code3_nonflash_SMrz/result/"
        "gpp_response_nonflash_SMrz_drought_v20260328_latfix_"
        "rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("GPP", "code4", "nonflash", "SMs"): os.path.join(
        BASE_PROCESS, "GPP-draught-analysis/code4_nonflash_SMs/result/"
        "gpp_response_nonflash_SMs_drought_v20260328_latfix_"
        "rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("NEE", "code1", "flash", "SMrz"): os.path.join(
        BASE_PROCESS, "NEE-draught-analysis/code1SMrz/result/"
        "nee_response_SMrz_drought_v20260328_latfix_"
        "rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("NEE", "code2", "flash", "SMs"): os.path.join(
        BASE_PROCESS, "NEE-draught-analysis/code2SMs/result/"
        "nee_response_SMs_drought_v20260328_latfix_"
        "rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("NEE", "code3", "nonflash", "SMrz"): os.path.join(
        BASE_PROCESS, "NEE-draught-analysis/code3_nonflash_SMrz/result/"
        "nee_response_nonflash_SMrz_drought_v20260328_latfix_"
        "rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("NEE", "code4", "nonflash", "SMs"): os.path.join(
        BASE_PROCESS, "NEE-draught-analysis/code4_nonflash_SMs/result/"
        "nee_response_nonflash_SMs_drought_v20260328_latfix_"
        "rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("RECO", "code1", "flash", "SMrz"): os.path.join(
        BASE_PROCESS, "RECO-draught-analysis/code1/results/"
        "reco_response_SMrz_events_global_v20260328_latfix_"
        "rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("RECO", "code2", "flash", "SMs"): os.path.join(
        BASE_PROCESS, "RECO-draught-analysis/code2_SMs/results/"
        "reco_response_SMs_drought_v20260328_latfix_"
        "rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("RECO", "code3", "nonflash", "SMrz"): os.path.join(
        BASE_PROCESS, "RECO-draught-analysis/code3_nonflash_SMrz/result/"
        "reco_response_nonflash_SMrz_drought_v20260328_latfix_"
        "rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("RECO", "code4", "nonflash", "SMs"): os.path.join(
        BASE_PROCESS, "RECO-draught-analysis/code4_nonflash_SMs/result/"
        "reco_response_nonflash_SMs_drought_v20260328_latfix_"
        "rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
}

# Fields to extract from each event NC (common across GPP/NEE/RECO)
COMMON_FIELDS = [
    "lat", "lon", "event_id",
    "onset_year", "onset_doy",
    "drought_start_year", "drought_start_doy",
    "actual_window_after",
    "lu_event_valid",
    "response_detected",
    "t_response_onset_start", "t_response_drought_start",
    "t_peak", "t_peak_abs",
    "t_peak_drought_start", "t_peak_abs_drought_start",
    "t_impact", "amp_max",
    "legacy_duration",
    "t_recover_to_baseline", "t_recover_to_baseline_abs_peak",
    "t_recover_onset_start", "t_recover_drought_start",
    "t_recover_post_drought",
    "recovery_rate_to_baseline",
]

# Metric-specific fields (baselines, losses, etc.)
METRIC_FIELDS = {
    "GPP": [
        "gpp_baseline_abs", "gpp_baseline_std_abs",
        "gpp_min_abs", "gpp_change_to_peak_abs",
        "gpp_loss_total_abs", "gpp_loss_drought_phase_abs",
        "gpp_loss_post_drought_phase_abs", "gpp_peak_deficit_abs",
    ],
    "NEE": [
        "nee_baseline_abs", "nee_baseline_std_abs",
        "nee_min_abs", "nee_change_to_peak_abs",
        "nee_loss_total_abs", "nee_loss_drought_phase_abs",
        "nee_loss_post_drought_phase_abs", "nee_peak_deficit_abs",
    ],
    "RECO": [
        "reco_baseline_abs", "reco_baseline_std_abs",
        "reco_min_abs", "reco_change_to_peak_abs",
        "reco_loss_total_abs", "reco_loss_drought_phase_abs",
        "reco_loss_post_drought_phase_abs", "reco_peak_deficit_abs",
    ],
}

# Unified column names for metric-specific fields
UNIFIED_METRIC_COLS = [
    "flux_baseline_abs", "flux_baseline_std_abs",
    "flux_min_abs", "flux_change_to_peak_abs",
    "flux_loss_total_abs", "flux_loss_drought_phase_abs",
    "flux_loss_post_drought_phase_abs", "flux_peak_deficit_abs",
]


def load_landuse_raster(tif_path):
    """Load MCD12C1 land-use TIF and return (data_array, transform)."""
    print(f"  Loading land-use TIF: {tif_path}")
    with rasterio.open(tif_path) as src:
        data = src.read(1)
        transform = src.transform
        nodata = src.nodata
        print(f"    Shape: {data.shape}, nodata: {nodata}")
    return data, transform, nodata


def assign_igbp_class(lats, lons, lu_data, lu_transform, lu_nodata):
    """
    Assign IGBP class to each event based on (lat, lon).
    Uses rasterio rowcol to map geographic coords to pixel indices.
    """
    n = len(lats)
    igbp_classes = np.full(n, 255, dtype=np.uint8)  # default: unclassified

    # Convert to arrays
    lats_arr = np.asarray(lats, dtype=np.float64)
    lons_arr = np.asarray(lons, dtype=np.float64)

    # Mask invalid coords
    valid = np.isfinite(lats_arr) & np.isfinite(lons_arr)

    # Batch convert geographic coords to pixel indices
    rows, cols = rowcol(lu_transform, lons_arr[valid], lats_arr[valid])
    rows = np.asarray(rows)
    cols = np.asarray(cols)

    # Clip to valid range
    h, w = lu_data.shape
    in_bounds = (rows >= 0) & (rows < h) & (cols >= 0) & (cols < w)

    # Extract values
    valid_idx = np.where(valid)[0]
    for i, (r, c, ib) in enumerate(zip(rows, cols, in_bounds)):
        if ib:
            val = lu_data[r, c]
            if lu_nodata is not None and val == lu_nodata:
                continue
            igbp_classes[valid_idx[i]] = val

    return igbp_classes


def read_event_file(filepath, metric, code_id, drought_type, soil_layer):
    """Read one event NC file and return a DataFrame."""
    print(f"  Reading: {os.path.basename(filepath)}")
    ds = xr.open_dataset(filepath)

    # Determine which fields exist in this file
    available_common = [f for f in COMMON_FIELDS if f in ds]
    missing_common = [f for f in COMMON_FIELDS if f not in ds]
    if missing_common:
        print(f"    Missing common fields: {missing_common}")

    # Read common fields
    data = {}
    for f in available_common:
        data[f] = ds[f].values

    # Read metric-specific fields and rename to unified names
    metric_fields = METRIC_FIELDS.get(metric, [])
    available_metric = [f for f in metric_fields if f in ds]
    missing_metric = [f for f in metric_fields if f not in ds]
    if missing_metric:
        print(f"    Missing metric fields: {missing_metric}")

    for orig, unified in zip(metric_fields, UNIFIED_METRIC_COLS):
        if orig in ds:
            data[unified] = ds[orig].values
        else:
            data[unified] = np.full(len(ds.event), np.nan, dtype=np.float32)

    ds.close()

    df = pd.DataFrame(data)
    n_total = len(df)

    # Add metadata columns
    df["metric"] = metric
    df["code_id"] = code_id
    df["drought_type"] = drought_type
    df["soil_layer"] = soil_layer

    print(f"    Total events: {n_total:,}")
    return df


def main():
    t0 = time.time()
    print("=" * 70)
    print("Stage 1: Build Event Master Table")
    print("=" * 70)

    # 1. Load land-use raster
    lu_data, lu_transform, lu_nodata = load_landuse_raster(LAND_USE_TIF)

    # 2. Read all 12 event files
    all_dfs = []
    for (metric, code_id, dtype, slayer), fpath in EVENT_FILES.items():
        if not os.path.exists(fpath):
            print(f"  WARNING: File not found: {fpath}")
            continue
        df = read_event_file(fpath, metric, code_id, dtype, slayer)
        all_dfs.append(df)

    # 3. Concatenate
    print("\nConcatenating all files...")
    master = pd.concat(all_dfs, ignore_index=True)
    print(f"  Total events across all files: {len(master):,}")

    # 4. Assign IGBP land-use class
    print("\nAssigning IGBP land-use class from MCD12C1...")
    master["igbp_class"] = assign_igbp_class(
        master["lat"].values, master["lon"].values,
        lu_data, lu_transform, lu_nodata
    )

    # Map to biome
    master["biome"] = master["igbp_class"].map(IGBP_TO_BIOME).fillna("Other")

    # 5. Filtering
    print("\nFiltering events...")
    n_raw = len(master)

    # 5a. Valid land use
    mask_lu = master["lu_event_valid"] == 1
    print(f"  lu_event_valid == 1: {mask_lu.sum():,} / {n_raw:,}")

    # 5b. IGBP not excluded
    mask_igbp = ~master["igbp_class"].isin(EXCLUDE_IGBP)
    print(f"  IGBP not excluded: {mask_igbp.sum():,} / {n_raw:,}")

    # 5c. Response detected
    mask_resp = master["response_detected"] == 1
    print(f"  response_detected == 1: {mask_resp.sum():,} / {n_raw:,}")

    # 5d. Recovery time valid (finite and >= 0)
    mask_rec = (
        np.isfinite(master["t_recover_to_baseline_abs_peak"])
        & (master["t_recover_to_baseline_abs_peak"] >= 0)
    )
    print(f"  t_recover valid (finite, >=0): {mask_rec.sum():,} / {n_raw:,}")

    # 5e. Coordinates valid
    mask_coord = np.isfinite(master["lat"]) & np.isfinite(master["lon"])
    print(f"  coords valid: {mask_coord.sum():,} / {n_raw:,}")

    # Combined mask
    mask_all = mask_lu & mask_igbp & mask_resp & mask_rec & mask_coord
    master_valid = master[mask_all].copy().reset_index(drop=True)
    print(f"\n  Final valid events: {len(master_valid):,} / {n_raw:,} "
          f"({len(master_valid)/n_raw*100:.1f}%)")

    # 6. Sample count summary
    print("\n" + "=" * 70)
    print("Sample Count by Biome x Metric x Code")
    print("=" * 70)

    summary = (
        master_valid
        .groupby(["biome", "metric", "code_id"])
        .size()
        .reset_index(name="n_events")
    )
    # Pivot for display
    pivot = summary.pivot_table(
        index=["biome"], columns=["metric", "code_id"],
        values="n_events", fill_value=0
    )
    print(pivot.to_string())

    # Biome totals
    print("\nBiome Totals:")
    biome_totals = master_valid.groupby("biome").size()
    for biome, cnt in biome_totals.items():
        flag = "OK" if cnt >= 1000 else "LOW"
        print(f"  {biome:15s}: {cnt:>10,}  [{flag}]")

    # 7. Save
    out_all = os.path.join(OUTPUT_DIR, "event_master_table_all.parquet")
    out_valid = os.path.join(OUTPUT_DIR, "event_master_table_valid.parquet")

    master.to_parquet(out_all, index=False, engine="pyarrow")
    master_valid.to_parquet(out_valid, index=False, engine="pyarrow")

    print(f"\nSaved:")
    print(f"  All events   : {out_all} ({len(master):,} rows)")
    print(f"  Valid events  : {out_valid} ({len(master_valid):,} rows)")

    # Also save summary CSV
    out_summary = os.path.join(OUTPUT_DIR, "event_count_summary.csv")
    summary_full = (
        master_valid
        .groupby(["biome", "metric", "code_id", "drought_type", "soil_layer"])
        .agg(
            n_events=("lat", "size"),
            mean_recovery_time=("t_recover_to_baseline_abs_peak", "mean"),
            median_recovery_time=("t_recover_to_baseline_abs_peak", "median"),
            std_recovery_time=("t_recover_to_baseline_abs_peak", "std"),
        )
        .reset_index()
    )
    summary_full.to_csv(out_summary, index=False)
    print(f"  Summary CSV   : {out_summary}")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
