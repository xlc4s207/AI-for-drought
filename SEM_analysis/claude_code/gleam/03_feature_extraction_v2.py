"""03_feature_extraction_v2.py
Stage 3: Extract ERA5 + GLEAM features - OPTIMIZED VERSION

Strategy:
1. Process one ERA5 variable at a time (avoid opening all files simultaneously)
2. Process by metric groups to reduce memory
3. Use dask for lazy loading

Outputs:
  results/feature_tables/gleam_pre_recovery_feature_table.parquet
"""
import numpy as np
import pandas as pd
import xarray as xr
from datetime import datetime, timedelta
import os, warnings, gc
warnings.filterwarnings("ignore")

BASE    = "/home/xulc/flash_drought/process"
OUT_DIR = f"{BASE}/SEM_analysis/claude_code/gleam/results/feature_tables"
os.makedirs(OUT_DIR, exist_ok=True)

EVENT_TABLE = f"{BASE}/SEM_analysis/claude_code/gleam/results/event_tables/gleam_event_master_table.parquet"

# Data paths
GLEAM_SMrz = "/data/GLEAM/0p25deg_yearly/SMrz_45years_0p25deg.nc"
GLEAM_SMs  = "/data/GLEAM/0p25deg_yearly/SMs_45years_0p25deg.nc"

ERA5_FILES = {
    "tp":   "/data/era5_for_GRN/yearly/total_precipitation_0p25deg_1980_2024.nc",
    "t2m":  "/data/era5_for_GRN/yearly/temperature_2m_0p25deg_1980_2024.nc",
    "ssrd": "/data/era5_for_GRN/yearly/ssrd_0p25deg_1980_2024.nc",
    "et":   "/data/era5_for_GRN/yearly/total_evaporation_0p25deg_1980_2024.nc",
}

def doy_to_date(year, doy):
    return datetime(int(year), 1, 1) + timedelta(days=int(doy) - 1)

# Load events
print("Loading events...")
df = pd.read_parquet(EVENT_TABLE)
df = df[df["recovered"] == 1].reset_index(drop=True)
print(f"Events: {len(df):,}")

# Pre-compute dates and grid indices
print("Computing dates and indices...")
onset_dates = [doy_to_date(y, d) for y, d in zip(df["onset_year"], df["onset_doy"])]
peak_dates = [onset_dates[i] + timedelta(days=int(df["t_peak_abs"].iloc[i]))
              for i in range(len(df))]

# Get coordinate reference from GLEAM
ds_ref = xr.open_dataset(GLEAM_SMrz)
lat_arr = ds_ref.lat.values
lon_arr = ds_ref.lon.values
ds_ref.close()

lat_idx = np.argmin(np.abs(lat_arr[:, None] - df["lat"].values[None, :]), axis=0)
lon_idx = np.argmin(np.abs(lon_arr[:, None] - df["lon"].values[None, :]), axis=0)

# Initialize feature dataframe
features = df[["metric", "code_id", "sm_type", "drought_type", "file_tag",
               "lat", "lon", "onset_year", "onset_doy", "func_class", "func_name",
               "t_peak_abs", "change_to_peak_abs", "t_recover_to_baseline_abs_peak",
               "onset_rate", "onset_drop", "duration", "intensity",
               "days_below_p20", "drought_class"]].copy()

# Feature extraction functions
def extract_features_for_var(var_name, file_path, events_df, lat_idx, lon_idx,
                              onset_dates, peak_dates, lat_arr, lon_arr):
    """Extract features for a single variable."""
    print(f"  Processing {var_name}...")
    ds = xr.open_dataset(file_path, chunks={"time": 365})
    var = list(ds.data_vars)[0]

    n = len(events_df)
    pre_mean = np.full(n, np.nan)
    pre_sum  = np.full(n, np.nan)
    shock_mean = np.full(n, np.nan)
    shock_max = np.full(n, np.nan)
    rec_sum = np.full(n, np.nan)

    BATCH = 50000
    for batch_start in range(0, n, BATCH):
        batch_end = min(batch_start + BATCH, n)
        if batch_start % 100000 == 0:
            print(f"    Batch {batch_start//BATCH + 1}/{(n+BATCH-1)//BATCH}")

        for i in range(batch_start, batch_end):
            try:
                # W1: pre30
                w1_start = onset_dates[i] - timedelta(days=30)
                w1_end = onset_dates[i]
                data1 = ds[var].isel(lat=lat_idx[i], lon=lon_idx[i]).sel(
                    time=slice(str(w1_start.date()), str(w1_end.date()))).values
                if len(data1) > 0:
                    pre_mean[i] = np.nanmean(data1)
                    pre_sum[i] = np.nansum(data1)

                # W2: shock (onset to peak)
                w2_start = onset_dates[i]
                w2_end = peak_dates[i]
                data2 = ds[var].isel(lat=lat_idx[i], lon=lon_idx[i]).sel(
                    time=slice(str(w2_start.date()), str(w2_end.date()))).values
                if len(data2) > 0:
                    shock_mean[i] = np.nanmean(data2)
                    shock_max[i] = np.nanmax(data2)

                # W3: rec30
                w3_start = peak_dates[i]
                w3_end = peak_dates[i] + timedelta(days=30)
                data3 = ds[var].isel(lat=lat_idx[i], lon=lon_idx[i]).sel(
                    time=slice(str(w3_start.date()), str(w3_end.date()))).values
                if len(data3) > 0:
                    rec_sum[i] = np.nansum(data3)
            except:
                continue

    ds.close()
    gc.collect()

    return {
        f"pre30_{var_name}_mean": pre_mean,
        f"pre30_{var_name}_sum": pre_sum,
        f"shock_{var_name}_mean": shock_mean,
        f"shock_{var_name}_max": shock_max,
        f"rec30_{var_name}_sum": rec_sum,
    }

# Extract GLEAM SM first
print("\nExtracting GLEAM soil moisture...")

for sm_var, sm_file, sm_name in [("SMrz", GLEAM_SMrz, "SMrz"),
                                   ("SMs", GLEAM_SMs, "SMs")]:
    print(f"  Processing {sm_name}...")
    ds = xr.open_dataset(sm_file, chunks={"time": 365})
    var = list(ds.data_vars)[0]

    n = len(df)
    pre_sm = np.full(n, np.nan)
    shock_sm = np.full(n, np.nan)
    rec_sm = np.full(n, np.nan)

    BATCH = 50000
    for batch_start in range(0, n, BATCH):
        batch_end = min(batch_start + BATCH, n)
        if batch_start % 100000 == 0:
            print(f"    Batch {batch_start//BATCH + 1}/{(n+BATCH-1)//BATCH}")

        for i in range(batch_start, batch_end):
            try:
                # W1
                w1_start = onset_dates[i] - timedelta(days=30)
                w1_end = onset_dates[i]
                data1 = ds[var].isel(lat=lat_idx[i], lon=lon_idx[i]).sel(
                    time=slice(str(w1_start.date()), str(w1_end.date()))).values
                if len(data1) > 0:
                    pre_sm[i] = np.nanmean(data1)

                # W2
                w2_start = onset_dates[i]
                w2_end = peak_dates[i]
                data2 = ds[var].isel(lat=lat_idx[i], lon=lon_idx[i]).sel(
                    time=slice(str(w2_start.date()), str(w2_end.date()))).values
                if len(data2) > 0:
                    shock_sm[i] = np.nanmean(data2)

                # W3
                w3_start = peak_dates[i]
                w3_end = peak_dates[i] + timedelta(days=30)
                data3 = ds[var].isel(lat=lat_idx[i], lon=lon_idx[i]).sel(
                    time=slice(str(w3_start.date()), str(w3_end.date()))).values
                if len(data3) > 0:
                    rec_sm[i] = np.nanmean(data3)
            except:
                continue

    ds.close()
    features[f"pre30_{sm_name}_mean"] = pre_sm
    features[f"shock_{sm_name}_mean"] = shock_sm
    features[f"rec30_{sm_name}_mean"] = rec_sm
    gc.collect()

print("  GLEAM SM done")

# Extract ERA5 variables one by one
print("\nExtracting ERA5 variables...")
for var_name, file_path in ERA5_FILES.items():
    feats = extract_features_for_var(var_name, file_path, df, lat_idx, lon_idx,
                                      onset_dates, peak_dates, lat_arr, lon_arr)
    for k, v in feats.items():
        features[k] = v
    gc.collect()

# Derived features
print("\nComputing derived features...")
features["pre30_P_ET_sum"] = features.get("pre30_tp_sum", 0) - features.get("pre30_et_sum", 0)
features["shock_P_ET_sum"] = features.get("shock_tp_sum", 0) - features.get("shock_et_sum", 0)

# Save
print("\nSaving feature table...")
out_path = os.path.join(OUT_DIR, "gleam_feature_table.parquet")
features.to_parquet(out_path, index=False)
print(f"Saved: {out_path}")

# Summary
print("\n" + "="*60)
print("Feature Extraction Summary")
print("="*60)
print(f"Total events: {len(features):,}")
print(f"Features: {len(features.columns) - 20}")
print("\nMissing rates:")
for col in ["pre30_SMrz_mean", "pre30_SMs_mean", "pre30_tp_sum", "pre30_t2m_mean"]:
    if col in features.columns:
        print(f"  {col}: {features[col].isna().mean()*100:.1f}%")

print("\nDone!")