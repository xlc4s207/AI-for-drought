"""03_feature_extraction_v3.py
Vectorized feature extraction grouped by grid cell.
READ-ONLY on source data. Outputs to results/feature_tables/.
"""
import numpy as np
import pandas as pd
import xarray as xr
from datetime import datetime
import os, warnings, gc
warnings.filterwarnings("ignore")

BASE    = "/home/xulc/flash_drought/process"
OUT_DIR = f"{BASE}/SEM_analysis/claude_code/gleam/results/feature_tables"
os.makedirs(OUT_DIR, exist_ok=True)

MODE = "gpp_code1"  # set to "all" for full run

DATA_SOURCES = {
    "SMrz":  "/data/GLEAM/0p25deg_yearly/SMrz_45years_0p25deg.nc",
    "SMs":   "/data/GLEAM/0p25deg_yearly/SMs_45years_0p25deg.nc",
    "t2m":   "/data/era5_for_GRN/yearly/temperature_2m_0p25deg_1980_2024.nc",
    "tp":    "/data/era5_for_GRN/yearly/total_precipitation_0p25deg_1980_2024.nc",
    "ssrd":  "/data/era5_for_GRN/yearly/ssrd_0p25deg_1980_2024.nc",
    "et":    "/data/era5_for_GRN/yearly/total_evaporation_0p25deg_1980_2024.nc",
    "strd":  "/data/era5_for_GRN/yearly/strd_0p25deg_1980_2024.nc",
    "sp":    "/data/era5_for_GRN/yearly/surface_pressure_0p25deg_1980_2024.nc",
    "lai_h": "/data/era5_for_GRN/yearly/leaf_area_index_high_vegetation_0p25deg_1980_2024.nc",
    "lai_l": "/data/era5_for_GRN/yearly/leaf_area_index_low_vegetation_0p25deg_1980_2024.nc",
    "tsoil1":"/data/era5_for_GRN/yearly/soil_temperature_level_1_0p25deg_1980_2024.nc",
    "tsoil4":"/data/era5_for_GRN/yearly/soil_temperature_level_4_0p25deg_1980_2024.nc",
}

WINDOW_STATS = {
    ("SMrz", "pre30"):  ["mean"],
    ("SMs",  "pre30"):  ["mean"],
    ("t2m",  "pre30"):  ["mean"],
    ("tp",   "pre30"):  ["sum"],
    ("ssrd", "pre30"):  ["mean"],
    ("strd", "pre30"):  ["mean"],
    ("et",   "pre30"):  ["sum"],
    ("sp",   "pre30"):  ["mean"],
    ("lai_h","pre30"):  ["mean"],
    ("lai_l","pre30"):  ["mean"],
    ("tsoil1","pre30"): ["mean"],
    ("tsoil4","pre30"): ["mean"],
    ("SMrz", "shock"):  ["mean"],
    ("SMs",  "shock"):  ["mean"],
    ("t2m",  "shock"):  ["mean","max"],
    ("tp",   "shock"):  ["sum"],
    ("ssrd", "shock"):  ["mean"],
    ("et",   "shock"):  ["mean"],
    ("lai_h","shock"):  ["mean"],
    ("lai_l","shock"):  ["mean"],
    ("tsoil1","shock"): ["mean"],
    ("SMrz", "rec30"):  ["mean"],
    ("SMs",  "rec30"):  ["mean"],
    ("t2m",  "rec30"):  ["mean"],
    ("tp",   "rec30"):  ["sum"],
    ("ssrd", "rec30"):  ["mean"],
    ("et",   "rec30"):  ["sum"],
}

# Load events
print("Loading events...")
if MODE == "gpp_code1":
    df = pd.read_parquet(f"{BASE}/SEM_analysis/claude_code/gleam/results/event_tables/gleam_event_master_GPP_code1_SMrz_flash.parquet")
else:
    df = pd.read_parquet(f"{BASE}/SEM_analysis/claude_code/gleam/results/event_tables/gleam_event_master_table.parquet")

df = df[df["recovered"] == 1].reset_index(drop=True)
print(f"  Events: {len(df):,}")

# Compute time references as numpy.datetime64
print("Computing time references...")
onset_np = (pd.to_datetime(df["onset_year"].astype(str) + "-01-01") +
            pd.to_timedelta(df["onset_doy"] - 1, unit="D")).values.astype("datetime64[D]")
peak_np  = onset_np + df["t_peak_abs"].values.astype("timedelta64[D]")
pre30_start = onset_np - np.timedelta64(30, "D")
rec30_end   = peak_np  + np.timedelta64(30, "D")

# Load coordinate reference
ds0 = xr.open_dataset(list(DATA_SOURCES.values())[0])
lat_arr  = ds0.lat.values
lon_arr  = ds0.lon.values
time_arr = ds0.time.values.astype("datetime64[D]")
ds0.close()

lat_idx  = np.argmin(np.abs(lat_arr[:, None]  - df["lat"].values[None, :]),  axis=0)
lon_idx  = np.argmin(np.abs(lon_arr[:, None]  - df["lon"].values[None, :]),  axis=0)
grid_key = lat_idx * len(lon_arr) + lon_idx

# Initialize feature arrays
feature_names = []
for (var, win), stats in WINDOW_STATS.items():
    for s in stats:
        feature_names.append(f"{win}_{var}_{s}")

feat = {name: np.full(len(df), np.nan, dtype=np.float32) for name in feature_names}

# Vectorized extraction: group by grid cell
def extract_var(var_name, fpath):
    needed_wins = list(set(win for (v, win) in WINDOW_STATS if v == var_name))
    if not needed_wins:
        return
    print(f"  {var_name}...", flush=True)

    ds = xr.open_dataset(fpath)
    varkey = list(ds.data_vars)[0]
    arr = ds[varkey].values   # load into memory
    dims = list(ds[varkey].dims)
    ds.close()

    # Ensure shape is (time, lat, lon)
    if dims.index("time") != 0:
        arr = np.moveaxis(arr, dims.index("time"), 0)

    unique_cells, cell_counts = np.unique(grid_key, return_counts=True)
    for ci, cell in enumerate(unique_cells):
        if ci % 20000 == 0:
            print(f"    {ci:,}/{len(unique_cells):,}", flush=True)
        li  = lat_idx[np.where(grid_key == cell)[0][0]]
        loi = lon_idx[np.where(grid_key == cell)[0][0]]
        ts  = arr[:, li, loi].astype(np.float32)
        ev_idx = np.where(grid_key == cell)[0]

        for ei in ev_idx:
            for win in needed_wins:
                if win == "pre30":
                    t0 = int(np.searchsorted(time_arr, pre30_start[ei]))
                    t1 = int(np.searchsorted(time_arr, onset_np[ei]))
                elif win == "shock":
                    t0 = int(np.searchsorted(time_arr, onset_np[ei]))
                    t1 = int(np.searchsorted(time_arr, peak_np[ei]))
                elif win == "rec30":
                    t0 = int(np.searchsorted(time_arr, peak_np[ei]))
                    t1 = int(np.searchsorted(time_arr, rec30_end[ei]))
                else:
                    continue
                if t1 <= t0 or t0 >= len(ts):
                    continue
                t1  = min(t1, len(ts))
                seg = ts[t0:t1]
                seg = seg[np.isfinite(seg)]
                if len(seg) == 0:
                    continue
                for s in WINDOW_STATS.get((var_name, win), []):
                    key = f"{win}_{var_name}_{s}"
                    if s == "mean":
                        feat[key][ei] = float(np.mean(seg))
                    elif s == "sum":
                        feat[key][ei] = float(np.sum(seg))
                    elif s == "max":
                        feat[key][ei] = float(np.max(seg))

for var_name, fpath in DATA_SOURCES.items():
    if any(v == var_name for (v, w) in WINDOW_STATS):
        extract_var(var_name, fpath)
        gc.collect()

# Build output
print("\nBuilding output...")
meta = ["metric","code_id","sm_type","drought_type","file_tag",
        "lat","lon","onset_year","onset_doy","func_class","func_name",
        "t_peak_abs","change_to_peak_abs","t_recover_to_baseline_abs_peak",
        "onset_rate","onset_drop","duration","intensity","days_below_p20","drought_class"]
out = df[meta].copy()
for name in feature_names:
    out[name] = feat[name]

if "pre30_lai_h_mean" in out.columns and "pre30_lai_l_mean" in out.columns:
    out["pre30_LAI_total_mean"] = out["pre30_lai_h_mean"] + out["pre30_lai_l_mean"]
if "pre30_tp_sum" in out.columns and "pre30_et_sum" in out.columns:
    out["pre30_P_ET_sum"] = out["pre30_tp_sum"] + out["pre30_et_sum"]

out_path = os.path.join(OUT_DIR, f"gleam_feature_table_{MODE}.parquet")
out.to_parquet(out_path, index=False)
print(f"Saved: {out_path}  ({len(out):,} rows, {len(out.columns)} cols)")

print("\nMissing rates (key features):")
for col in ["pre30_SMrz_mean","pre30_SMs_mean","pre30_t2m_mean",
            "pre30_tp_sum","shock_t2m_mean","rec30_SMrz_mean"]:
    if col in out.columns:
        print(f"  {col}: {out[col].isna().mean()*100:.1f}%")

print("\nDone!")
