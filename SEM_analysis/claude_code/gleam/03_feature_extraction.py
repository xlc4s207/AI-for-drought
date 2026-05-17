"""03_feature_extraction.py
Stage 3: Extract ERA5 + GLEAM features for each event based on three time windows.
- W1: pre30 (onset_start - 30d ~ onset_start) - background conditions
- W2: shock (onset_start ~ peak) - impact accumulation
- W3: rec30 (peak ~ peak + 30d) - recovery phase conditions

Outputs:
  results/feature_tables/gleam_pre_recovery_feature_table.parquet
  results/feature_tables/gleam_recovery_phase_feature_table.parquet
"""
import numpy as np
import pandas as pd
import xarray as xr
from osgeo import gdal
import os, warnings
from datetime import datetime, timedelta
warnings.filterwarnings("ignore")

BASE    = "/home/xulc/flash_drought/process"
OUT_DIR = f"{BASE}/SEM_analysis/claude_code/gleam/results/feature_tables"
os.makedirs(OUT_DIR, exist_ok=True)

EVENT_TABLE = f"{BASE}/SEM_analysis/claude_code/gleam/results/event_tables/gleam_event_master_table.parquet"

# Data paths
GLEAM_SMrz = "/data/GLEAM/0p25deg_yearly/SMrz_45years_0p25deg.nc"
GLEAM_SMs  = "/data/GLEAM/0p25deg_yearly/SMs_45years_0p25deg.nc"

ERA5_VARS = {
    "tp":   "/data/era5_for_GRN/yearly/total_precipitation_0p25deg_1980_2024.nc",
    "et":   "/data/era5_for_GRN/yearly/total_evaporation_0p25deg_1980_2024.nc",
    "t2m":  "/data/era5_for_GRN/yearly/temperature_2m_0p25deg_1980_2024.nc",
    "ssrd": "/data/era5_for_GRN/yearly/ssrd_0p25deg_1980_2024.nc",
    "strd": "/data/era5_for_GRN/yearly/strd_0p25deg_1980_2024.nc",
    "sp":   "/data/era5_for_GRN/yearly/surface_pressure_0p25deg_1980_2024.nc",
    "u10":  "/data/era5_for_GRN/yearly/wind_u_10m_0p25deg_1980_2024.nc",
    "v10":  "/data/era5_for_GRN/yearly/wind_v_10m_0p25deg_1980_2024.nc",
    "lai_h": "/data/era5_for_GRN/yearly/leaf_area_index_high_vegetation_0p25deg_1980_2024.nc",
    "lai_l": "/data/era5_for_GRN/yearly/leaf_area_index_low_vegetation_0p25deg_1980_2024.nc",
    "tsoil1": "/data/era5_for_GRN/yearly/soil_temperature_level_1_0p25deg_1980_2024.nc",
    "tsoil4": "/data/era5_for_GRN/yearly/soil_temperature_level_4_0p25deg_1980_2024.nc",
}

# Helper functions
def doy_to_date(year, doy):
    """Convert year + DOY to datetime."""
    return datetime(int(year), 1, 1) + timedelta(days=int(doy) - 1)

def latlon_to_idx(lat, lon, lat_arr, lon_arr):
    """Find nearest grid indices for lat/lon arrays."""
    lat_idx = np.argmin(np.abs(lat_arr - lat))
    lon_idx = np.argmin(np.abs(lon_arr - lon))
    return lat_idx, lon_idx

def extract_window_stats(ds, var_name, lat_idx, lon_idx, time_slice, stat="mean"):
    """Extract statistics from a time window for a single variable."""
    try:
        data = ds[var_name].isel(lat=lat_idx, lon=lon_idx).sel(time=time_slice).values
        if len(data) == 0 or np.all(np.isnan(data)):
            return np.nan
        if stat == "mean":
            return np.nanmean(data)
        elif stat == "sum":
            return np.nansum(data)
        elif stat == "max":
            return np.nanmax(data)
        elif stat == "min":
            return np.nanmin(data)
    except Exception:
        return np.nan
    return np.nan

# Load event table
print("Loading event master table...")
df = pd.read_parquet(EVENT_TABLE)
print(f"  Total events: {len(df):,}")

# Filter to recovered=1 only (main analysis)
df_rec = df[df["recovered"] == 1].copy()
print(f"  Recovered events: {len(df_rec):,}")

# Open datasets (keep open for efficiency)
print("\nOpening datasets...")
ds_smrz = xr.open_dataset(GLEAM_SMrz)
ds_sms  = xr.open_dataset(GLEAM_SMs)
print("  GLEAM SM loaded")

# Open ERA5 datasets
era5_ds = {}
for vname, fpath in ERA5_VARS.items():
    try:
        era5_ds[vname] = xr.open_dataset(fpath)
        print(f"  ERA5 {vname} loaded")
    except Exception as e:
        print(f"  WARNING: Failed to load {vname}: {e}")

# Get coordinate arrays
lat_arr = ds_smrz.lat.values
lon_arr = ds_smrz.lon.values
time_arr = ds_smrz.time.values

# Pre-compute lat/lon indices for all events
print("\nPre-computing grid indices...")
lat_indices = np.argmin(np.abs(lat_arr[:, None] - df_rec["lat"].values[None, :]), axis=0)
lon_indices = np.argmin(np.abs(lon_arr[:, None] - df_rec["lon"].values[None, :]), axis=0)

# Build time references
print("Building time references...")
onset_dates = [doy_to_date(y, d) for y, d in zip(df_rec["onset_year"], df_rec["onset_doy"])]
peak_dates  = [onset_dates[i] + timedelta(days=int(df_rec["t_peak_abs"].iloc[i]))
               for i in range(len(df_rec))]

# Initialize feature arrays
n_events = len(df_rec)
features_pre = {}
features_shock = {}
features_rec = {}

# Define features to extract
PRE_FEATURES = [
    ("SMrz", "mean"), ("SMs", "mean"),
    ("tp", "sum"), ("et", "sum"), ("t2m", "mean"),
    ("ssrd", "mean"), ("strd", "mean"), ("sp", "mean"),
    ("lai_h", "mean"), ("lai_l", "mean"),
]

SHOCK_FEATURES = [
    ("SMrz", "mean"), ("SMs", "mean"),
    ("tp", "sum"), ("et", "mean"), ("t2m", "mean"), ("t2m", "max"),
    ("ssrd", "mean"), ("strd", "mean"),
    ("lai_h", "mean"), ("lai_l", "mean"),
]

REC_FEATURES = [
    ("SMrz", "mean"), ("SMs", "mean"),
    ("tp", "sum"), ("et", "sum"), ("t2m", "mean"),
    ("ssrd", "mean"), ("strd", "mean"),
]

# Process in batches
BATCH_SIZE = 100000
n_batches = (n_events + BATCH_SIZE - 1) // BATCH_SIZE

print(f"\nExtracting features in {n_batches} batches...")

for batch_idx in range(n_batches):
    start_idx = batch_idx * BATCH_SIZE
    end_idx = min((batch_idx + 1) * BATCH_SIZE, n_events)

    if batch_idx % 10 == 0:
        print(f"  Processing batch {batch_idx+1}/{n_batches} (events {start_idx:,} - {end_idx:,})...")

    batch_features_pre = {f"pre30_{v}_{s}": np.full(end_idx - start_idx, np.nan)
                          for v, s in PRE_FEATURES}
    batch_features_shock = {f"shock_{v}_{s}": np.full(end_idx - start_idx, np.nan)
                            for v, s in SHOCK_FEATURES}
    batch_features_rec = {f"rec30_{v}_{s}": np.full(end_idx - start_idx, np.nan)
                          for v, s in REC_FEATURES}

    for i in range(start_idx, end_idx):
        local_i = i - start_idx
        lat_i = lat_indices[i]
        lon_i = lon_indices[i]
        onset_d = onset_dates[i]
        peak_d = peak_dates[i]

        # W1: pre30 window
        w1_start = onset_d - timedelta(days=30)
        w1_end = onset_d
        w1_slice = slice(str(w1_start.date()), str(w1_end.date()))

        # W2: shock window (onset to peak)
        w2_start = onset_d
        w2_end = peak_d
        w2_slice = slice(str(w2_start.date()), str(w2_end.date()))

        # W3: rec30 window (peak to peak+30)
        w3_start = peak_d
        w3_end = peak_d + timedelta(days=30)
        w3_slice = slice(str(w3_start.date()), str(w3_end.date()))

        # Extract GLEAM SM
        try:
            smrz_pre = ds_smrz["SMrz"].isel(lat=lat_i, lon=lon_i).sel(time=w1_slice).values
            batch_features_pre["pre30_SMrz_mean"][local_i] = np.nanmean(smrz_pre)
        except: pass

        try:
            sms_pre = ds_sms["SMs"].isel(lat=lat_i, lon=lon_i).sel(time=w1_slice).values
            batch_features_pre["pre30_SMs_mean"][local_i] = np.nanmean(sms_pre)
        except: pass

        # Extract ERA5 variables
        for vname, ds_obj in era5_ds.items():
            varname = list(ds_obj.data_vars)[0]  # get actual variable name

            # W1
            for stat in ["mean", "sum"]:
                if (vname, stat) in PRE_FEATURES:
                    try:
                        val = extract_window_stats(ds_obj, varname, lat_i, lon_i, w1_slice, stat)
                        batch_features_pre[f"pre30_{vname}_{stat}"][local_i] = val
                    except: pass

            # W2
            for stat in ["mean", "sum", "max"]:
                if (vname, stat) in SHOCK_FEATURES:
                    try:
                        val = extract_window_stats(ds_obj, varname, lat_i, lon_i, w2_slice, stat)
                        batch_features_shock[f"shock_{vname}_{stat}"][local_i] = val
                    except: pass

            # W3
            for stat in ["mean", "sum"]:
                if (vname, stat) in REC_FEATURES:
                    try:
                        val = extract_window_stats(ds_obj, varname, lat_i, lon_i, w3_slice, stat)
                        batch_features_rec[f"rec30_{vname}_{stat}"][local_i] = val
                    except: pass

    # Append to main feature dicts
    for k, v in batch_features_pre.items():
        if k not in features_pre:
            features_pre[k] = []
        features_pre[k].extend(v)

    for k, v in batch_features_shock.items():
        if k not in features_shock:
            features_shock[k] = []
        features_shock[k].extend(v)

    for k, v in batch_features_rec.items():
        if k not in features_rec:
            features_rec[k] = []
        features_rec[k].extend(v)

print("\nBuilding feature dataframes...")

# Combine features with event metadata
df_pre = df_rec[["metric", "code_id", "sm_type", "drought_type", "file_tag",
                 "lat", "lon", "onset_year", "onset_doy",
                 "func_class", "func_name",
                 "t_peak_abs", "change_to_peak_abs",
                 "t_recover_to_baseline_abs_peak",
                 "onset_rate", "onset_drop", "duration", "intensity",
                 "days_below_p20", "drought_class"]].copy()

for k, v in features_pre.items():
    df_pre[k] = v

for k, v in features_shock.items():
    df_pre[k] = v

# Add derived features
df_pre["pre30_LAI_total_mean"] = df_pre["pre30_lai_h_mean"] + df_pre["pre30_lai_l_mean"]
df_pre["pre30_P_ET_sum"] = df_pre["pre30_tp_sum"] - df_pre["pre30_et_sum"]

# Recovery phase table (includes W3)
df_rec_phase = df_pre.copy()
for k, v in features_rec.items():
    df_rec_phase[k] = v

df_rec_phase["rec30_LAI_total_mean"] = df_rec_phase["rec30_lai_h_mean"] + df_rec_phase["rec30_lai_l_mean"]

# Save
print("Saving feature tables...")
pre_out = os.path.join(OUT_DIR, "gleam_pre_recovery_feature_table.parquet")
rec_out = os.path.join(OUT_DIR, "gleam_recovery_phase_feature_table.parquet")

df_pre.to_parquet(pre_out, index=False)
print(f"  Saved: {pre_out} ({len(df_pre):,} rows)")

df_rec_phase.to_parquet(rec_out, index=False)
print(f"  Saved: {rec_out} ({len(df_rec_phase):,} rows)")

# Summary statistics
print("\n" + "="*70)
print("Feature Extraction Summary")
print("="*70)
print(f"Total events processed: {n_events:,}")
print(f"Features extracted: {len(df_pre.columns) - 20}")  # minus metadata columns

# Check missing rates
print("\nMissing rate for key features (pre_recovery table):")
for col in ["pre30_SMrz_mean", "pre30_SMs_mean", "pre30_tp_sum", "pre30_t2m_mean",
            "shock_SMrz_mean", "shock_t2m_mean", "shock_tp_sum"]:
    if col in df_pre.columns:
        miss_rate = df_pre[col].isna().mean() * 100
        print(f"  {col}: {miss_rate:.1f}%")

print("\nDone!")