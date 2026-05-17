"""03_feature_extraction_test.py
Test version: Extract features for GPP code1 only (smaller dataset)
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

# Load only GPP code1 events
print("Loading GPP code1 events...")
df = pd.read_parquet(f"{BASE}/SEM_analysis/claude_code/gleam/results/event_tables/gleam_event_master_GPP_code1_SMrz_flash.parquet")
df = df[df["recovered"] == 1].reset_index(drop=True)
print(f"Events: {len(df):,}")

# Take a sample for testing
SAMPLE_SIZE = 10000
df = df.sample(n=min(SAMPLE_SIZE, len(df)), random_state=42).reset_index(drop=True)
print(f"Sample: {len(df):,}")

# Pre-compute dates
onset_dates = [datetime(int(y), 1, 1) + timedelta(days=int(d) - 1)
               for y, d in zip(df["onset_year"], df["onset_doy"])]
peak_dates = [onset_dates[i] + timedelta(days=int(df["t_peak_abs"].iloc[i]))
              for i in range(len(df))]

# Get grid indices
ds_ref = xr.open_dataset("/data/GLEAM/0p25deg_yearly/SMrz_45years_0p25deg.nc")
lat_arr = ds_ref.lat.values
lon_arr = ds_ref.lon.values
ds_ref.close()

lat_idx = np.argmin(np.abs(lat_arr[:, None] - df["lat"].values[None, :]), axis=0)
lon_idx = np.argmin(np.abs(lon_arr[:, None] - df["lon"].values[None, :]), axis=0)

# Initialize features
features = df[["metric", "code_id", "sm_type", "drought_type", "file_tag",
               "lat", "lon", "onset_year", "onset_doy", "func_class", "func_name",
               "t_peak_abs", "change_to_peak_abs", "t_recover_to_baseline_abs_peak",
               "onset_rate", "intensity"]].copy()

print("\nExtracting features...")

# Extract GLEAM SMrz
print("  GLEAM SMrz...")
ds = xr.open_dataset("/data/GLEAM/0p25deg_yearly/SMrz_45years_0p25deg.nc")
var = list(ds.data_vars)[0]

pre_sm = []
shock_sm = []
rec_sm = []

for i in range(len(df)):
    try:
        # W1
        w1 = ds[var].isel(lat=lat_idx[i], lon=lon_idx[i]).sel(
            time=slice(str((onset_dates[i] - timedelta(days=30)).date()),
                       str(onset_dates[i].date()))).values
        pre_sm.append(np.nanmean(w1) if len(w1) > 0 else np.nan)

        # W2
        w2 = ds[var].isel(lat=lat_idx[i], lon=lon_idx[i]).sel(
            time=slice(str(onset_dates[i].date()),
                       str(peak_dates[i].date()))).values
        shock_sm.append(np.nanmean(w2) if len(w2) > 0 else np.nan)

        # W3
        w3 = ds[var].isel(lat=lat_idx[i], lon=lon_idx[i]).sel(
            time=slice(str(peak_dates[i].date()),
                       str((peak_dates[i] + timedelta(days=30)).date()))).values
        rec_sm.append(np.nanmean(w3) if len(w3) > 0 else np.nan)
    except:
        pre_sm.append(np.nan)
        shock_sm.append(np.nan)
        rec_sm.append(np.nan)

    if (i + 1) % 1000 == 0:
        print(f"    {i+1}/{len(df)}")

ds.close()

features["pre30_SMrz_mean"] = pre_sm
features["shock_SMrz_mean"] = shock_sm
features["rec30_SMrz_mean"] = rec_sm

# Extract ERA5 t2m
print("  ERA5 t2m...")
ds = xr.open_dataset("/data/era5_for_GRN/yearly/temperature_2m_0p25deg_1980_2024.nc")
var = list(ds.data_vars)[0]

pre_t2m = []
shock_t2m = []
rec_t2m = []

for i in range(len(df)):
    try:
        w1 = ds[var].isel(lat=lat_idx[i], lon=lon_idx[i]).sel(
            time=slice(str((onset_dates[i] - timedelta(days=30)).date()),
                       str(onset_dates[i].date()))).values
        pre_t2m.append(np.nanmean(w1) if len(w1) > 0 else np.nan)

        w2 = ds[var].isel(lat=lat_idx[i], lon=lon_idx[i]).sel(
            time=slice(str(onset_dates[i].date()),
                       str(peak_dates[i].date()))).values
        shock_t2m.append(np.nanmean(w2) if len(w2) > 0 else np.nan)

        w3 = ds[var].isel(lat=lat_idx[i], lon=lon_idx[i]).sel(
            time=slice(str(peak_dates[i].date()),
                       str((peak_dates[i] + timedelta(days=30)).date()))).values
        rec_t2m.append(np.nanmean(w3) if len(w3) > 0 else np.nan)
    except:
        pre_t2m.append(np.nan)
        shock_t2m.append(np.nan)
        rec_t2m.append(np.nan)

    if (i + 1) % 1000 == 0:
        print(f"    {i+1}/{len(df)}")

ds.close()

features["pre30_t2m_mean"] = pre_t2m
features["shock_t2m_mean"] = shock_t2m
features["rec30_t2m_mean"] = rec_t2m

# Extract ERA5 tp
print("  ERA5 tp...")
ds = xr.open_dataset("/data/era5_for_GRN/yearly/total_precipitation_0p25deg_1980_2024.nc")
var = list(ds.data_vars)[0]

pre_tp = []
shock_tp = []
rec_tp = []

for i in range(len(df)):
    try:
        w1 = ds[var].isel(lat=lat_idx[i], lon=lon_idx[i]).sel(
            time=slice(str((onset_dates[i] - timedelta(days=30)).date()),
                       str(onset_dates[i].date()))).values
        pre_tp.append(np.nansum(w1) if len(w1) > 0 else np.nan)

        w2 = ds[var].isel(lat=lat_idx[i], lon=lon_idx[i]).sel(
            time=slice(str(onset_dates[i].date()),
                       str(peak_dates[i].date()))).values
        shock_tp.append(np.nansum(w2) if len(w2) > 0 else np.nan)

        w3 = ds[var].isel(lat=lat_idx[i], lon=lon_idx[i]).sel(
            time=slice(str(peak_dates[i].date()),
                       str((peak_dates[i] + timedelta(days=30)).date()))).values
        rec_tp.append(np.nansum(w3) if len(w3) > 0 else np.nan)
    except:
        pre_tp.append(np.nan)
        shock_tp.append(np.nan)
        rec_tp.append(np.nan)

    if (i + 1) % 1000 == 0:
        print(f"    {i+1}/{len(df)}")

ds.close()

features["pre30_tp_sum"] = pre_tp
features["shock_tp_sum"] = shock_tp
features["rec30_tp_sum"] = rec_tp

# Save
out_path = os.path.join(OUT_DIR, "gleam_feature_table_test.parquet")
features.to_parquet(out_path, index=False)
print(f"\nSaved: {out_path}")

# Summary
print("\n" + "="*50)
print("Test Feature Extraction Summary")
print("="*50)
print(f"Events: {len(features):,}")
print(f"Features: {len(features.columns) - 16}")
print("\nMissing rates:")
for col in ["pre30_SMrz_mean", "pre30_t2m_mean", "pre30_tp_sum"]:
    if col in features.columns:
        print(f"  {col}: {features[col].isna().mean()*100:.1f}%")

print("\nSample values:")
print(features[["pre30_SMrz_mean", "pre30_t2m_mean", "pre30_tp_sum",
                "shock_SMrz_mean", "rec30_SMrz_mean"]].head())

print("\nDone!")