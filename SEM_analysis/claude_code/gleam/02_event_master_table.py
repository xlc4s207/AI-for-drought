"""02_event_master_table.py
Stage 1-2: Build event master table for all 12 GLEAM target files.
Outputs:
  results/event_tables/gleam_event_master_{tag}.parquet
  results/event_tables/gleam_event_master_table.parquet
"""
import numpy as np
import pandas as pd
import xarray as xr
from osgeo import gdal
import os, warnings
warnings.filterwarnings("ignore")

BASE    = "/home/xulc/flash_drought/process"
OUT_DIR = f"{BASE}/SEM_analysis/claude_code/gleam/results/event_tables"
os.makedirs(OUT_DIR, exist_ok=True)

LU_FILE   = "/home/xulc/flash_drought/land_use/functional_class_025deg.tif"
IGBP_FILE = "/home/xulc/flash_drought/land_use/MCD12C1_LC_Type1_2010_025deg.tif"

DROUGHT_DIRS = {
    "SMrz": "/home/xulc/flash_drought/gleam/clip_result/SMrz_result_v5.4_0p25deg_no_ice_desert",
    "SMs":  "/home/xulc/flash_drought/gleam/clip_result/SMs_result_v5.4_0p25deg_no_ice_desert",
}
DROUGHT_FILES = {
    "flash_lt20":  "flash_lt20_drought_events_v5.4.nc",
    "flash_5to20": "flash_5to20_drought_events_v5.4.nc",
    "rapid_1to4":  "rapid_1to4_drought_events_v5.4.nc",
    "slow_gt20":   "slow_gt20_drought_events_v5.4.nc",
}
FUNC_NAMES = {0:"Excluded",1:"Forest",2:"Shrubland",
              3:"Savanna_Grassland",4:"Wetland",5:"Cropland"}

TARGET_FILES = [
    ("GPP",  "code1", "SMrz", "flash", f"{BASE}/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("GPP",  "code2", "SMs",  "flash", f"{BASE}/GPP-draught-analysis/code2_SMs/results/gpp_response_SMs_events_global_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("GPP",  "code3", "SMrz", "slow",  f"{BASE}/GPP-draught-analysis/code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("GPP",  "code4", "SMs",  "slow",  f"{BASE}/GPP-draught-analysis/code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("NEE",  "code1", "SMrz", "flash", f"{BASE}/NEE-draught-analysis/code1SMrz/result/nee_response_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("NEE",  "code2", "SMs",  "flash", f"{BASE}/NEE-draught-analysis/code2SMs/result/nee_response_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("NEE",  "code3", "SMrz", "slow",  f"{BASE}/NEE-draught-analysis/code3_nonflash_SMrz/result/nee_response_nonflash_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("NEE",  "code4", "SMs",  "slow",  f"{BASE}/NEE-draught-analysis/code4_nonflash_SMs/result/nee_response_nonflash_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("RECO", "code1", "SMrz", "flash", f"{BASE}/RECO-draught-analysis/code1/results/reco_response_SMrz_events_global_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("RECO", "code2", "SMs",  "flash", f"{BASE}/RECO-draught-analysis/code2_SMs/results/reco_response_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("RECO", "code3", "SMrz", "slow",  f"{BASE}/RECO-draught-analysis/code3_nonflash_SMrz/result/reco_response_nonflash_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("RECO", "code4", "SMs",  "slow",  f"{BASE}/RECO-draught-analysis/code4_nonflash_SMs/result/reco_response_nonflash_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
]

# load land cover
print("Loading land cover...")
lu_ds    = gdal.Open(LU_FILE)
func_arr = lu_ds.GetRasterBand(1).ReadAsArray().astype(np.int8)
lu_gt    = lu_ds.GetGeoTransform()
lu_ds    = None
igbp_ds  = gdal.Open(IGBP_FILE)
igbp_arr = igbp_ds.GetRasterBand(1).ReadAsArray().astype(np.int8)
igbp_ds  = None

def latlon_to_lu_rowcol(lat, lon):
    col = np.floor((lon - lu_gt[0]) / lu_gt[1]).astype(int)
    row = np.floor((lat - lu_gt[3]) / lu_gt[5]).astype(int)
    return np.clip(row, 0, 719), np.clip(col, 0, 1439)

# build drought lookup
def build_drought_lookup(sm_type):
    lookup = {}
    ddir = DROUGHT_DIRS[sm_type]
    for dclass, fname in DROUGHT_FILES.items():
        fpath = os.path.join(ddir, fname)
        if not os.path.exists(fpath):
            print(f"  WARNING: {fpath} not found")
            continue
        ds = xr.open_dataset(fpath)
        lats_g   = ds.lat.values
        lons_g   = ds.lon.values
        ec_arr   = ds["event_count"].values
        onset_sy = ds["onset_start_year"].values
        onset_sd = ds["onset_start_doy"].values
        o_days   = ds["onset_days"].values
        dur      = ds["duration"].values
        dp20     = ds["days_below_p20"].values
        o_drop   = ds["onset_drop"].values
        o_rate   = ds["onset_rate"].values
        intens   = ds["intensity"].values
        n_ev     = ds.sizes["max_events"]
        ds.close()
        # dims are (max_events, lat, lon)
        ec_arr_t = ec_arr  # (lat, lon) — event_count has no event dim
        for ri, ci in zip(*np.where(np.nan_to_num(ec_arr_t) > 0)):
            key = (round(float(lats_g[ri]), 4), round(float(lons_g[ci]), 4))
            if key not in lookup:
                lookup[key] = []
            n_this = int(np.nan_to_num(ec_arr_t[ri, ci]))
            for ei in range(min(n_this, n_ev)):
                sy = onset_sy[ei, ri, ci]
                sd = onset_sd[ei, ri, ci]
                if not (np.isfinite(sy) and np.isfinite(sd)):
                    continue
                lookup[key].append({
                    "drought_class":    dclass,
                    "onset_start_year": int(sy),
                    "onset_start_doy":  int(sd),
                    "onset_days":       float(o_days[ei, ri, ci]),
                    "duration":         float(dur[ei, ri, ci]),
                    "days_below_p20":   float(dp20[ei, ri, ci]),
                    "onset_drop":       float(o_drop[ei, ri, ci]),
                    "onset_rate":       float(o_rate[ei, ri, ci]),
                    "intensity":        float(intens[ei, ri, ci]),
                })
        print(f"    {sm_type}/{dclass}: done")
    return lookup

lookup_cache = {}

def get_lookup(sm_type):
    if sm_type not in lookup_cache:
        print(f"  Building drought lookup for {sm_type}...")
        lookup_cache[sm_type] = build_drought_lookup(sm_type)
        total = sum(len(v) for v in lookup_cache[sm_type].values())
        print(f"  Total grid cells with events: {total:,}")
    return lookup_cache[sm_type]


def vectorized_match(lats, lons, onset_years, onset_doys, sm_type, tol=1):
    """Vectorized drought morphology matching via pandas merge."""
    lookup = get_lookup(sm_type)
    rows = []
    for (lat_k, lon_k), evs in lookup.items():
        for ev in evs:
            rows.append({
                "lat_k": lat_k,
                "lon_k": lon_k,
                "oy_k":  ev["onset_start_year"],
                "od_k":  ev["onset_start_doy"],
                "drought_class":  ev["drought_class"],
                "onset_days":     ev["onset_days"],
                "duration":       ev["duration"],
                "days_below_p20": ev["days_below_p20"],
                "onset_drop":     ev["onset_drop"],
                "onset_rate":     ev["onset_rate"],
                "intensity":      ev["intensity"],
            })
    if not rows:
        return None
    lkup_df = pd.DataFrame(rows)

    query_df = pd.DataFrame({
        "row_idx": np.arange(len(lats)),
        "lat_k":   np.round(lats, 4),
        "lon_k":   np.round(lons, 4),
        "oy_k":    onset_years.astype(int),
        "od_k":    onset_doys.astype(int),
    })

    merged = query_df.merge(lkup_df, on=["lat_k", "lon_k", "oy_k"],
                            how="left", suffixes=("", "_ev"))
    merged = merged[np.abs(merged["od_k"] - merged["od_k_ev"].fillna(-9999)) <= tol]
    merged = merged.drop_duplicates(subset="row_idx", keep="first")
    return merged.set_index("row_idx")


# process each file
all_dfs = []
morph_cols = ["drought_class","onset_days","duration",
              "days_below_p20","onset_drop","onset_rate","intensity"]

for metric, code_id, sm_type, drought_type, fpath in TARGET_FILES:
    tag = f"{metric}_{code_id}_{sm_type}_{drought_type}"
    print(f"\n{'='*60}\nProcessing {tag}...")

    ds = xr.open_dataset(fpath)
    peak_field = f"{metric.lower()}_change_to_peak_abs"

    resp  = ds["response_detected"].values
    trec  = ds["t_recover_to_baseline_abs_peak"].values
    lat_v = ds["lat"].values
    lon_v = ds["lon"].values
    oy_v  = ds["onset_year"].values
    od_v  = ds["onset_doy"].values

    resp_mask = ((resp == 1) & np.isfinite(lat_v) & np.isfinite(lon_v)
                 & np.isfinite(oy_v) & np.isfinite(od_v))
    idx = np.where(resp_mask)[0]
    print(f"  response=1: {len(idx):,}")

    lats_sel = lat_v[idx]
    lons_sel = lon_v[idx]
    rows_lu, cols_lu = latlon_to_lu_rowcol(lats_sel, lons_sel)
    func_cls = func_arr[rows_lu, cols_lu].astype(int)
    igbp_cls = igbp_arr[rows_lu, cols_lu].astype(int)
    veg_mask = func_cls > 0
    idx      = idx[veg_mask]
    lats_sel = lats_sel[veg_mask]
    lons_sel = lons_sel[veg_mask]
    func_cls = func_cls[veg_mask]
    igbp_cls = igbp_cls[veg_mask]
    print(f"  after veg filter: {len(idx):,}")

    if len(idx) == 0:
        ds.close()
        continue

    trec_sel  = trec[idx]
    recovered = (np.isfinite(trec_sel) & (trec_sel >= 0)).astype(np.int8)

    df = pd.DataFrame({
        "metric":       metric,
        "code_id":      code_id,
        "sm_type":      sm_type,
        "drought_type": drought_type,
        "file_tag":     tag,
        "lat":  lats_sel,
        "lon":  lons_sel,
        "onset_year": oy_v[idx].astype(int),
        "onset_doy":  od_v[idx].astype(int),
        "drought_start_year": ds["drought_start_year"].values[idx],
        "drought_start_doy":  ds["drought_start_doy"].values[idx],
        "igbp_class": igbp_cls,
        "func_class": func_cls,
        "func_name":  [FUNC_NAMES[c] for c in func_cls],
        "t_response_onset_start":   ds["t_response_onset_start"].values[idx],
        "t_response_drought_start": ds["t_response_drought_start"].values[idx],
        "t_peak_abs":               ds["t_peak_abs"].values[idx],
        "change_to_peak_abs": (ds[peak_field].values[idx]
                               if peak_field in ds.data_vars else np.nan),
        "t_recover_to_baseline_abs_peak": trec_sel,
        "t_recover_post_drought": ds["t_recover_post_drought"].values[idx],
        "legacy_duration":        ds["legacy_duration"].values[idx],
        "recovered": recovered,
    })
    ds.close()

    # vectorized morphology matching
    print(f"  Matching drought morphology ({sm_type})...")
    for c in morph_cols:
        df[c] = "" if c == "drought_class" else np.nan

    match_result = vectorized_match(
        df["lat"].values, df["lon"].values,
        df["onset_year"].values, df["onset_doy"].values, sm_type)

    n_matched = 0
    if match_result is not None:
        for c in morph_cols:
            if c in match_result.columns:
                df.loc[match_result.index, c] = match_result[c].values
        n_matched = len(match_result)

    print(f"  Morphology match: {n_matched:,}/{len(df):,} "
          f"({100*n_matched/max(len(df),1):.1f}%)")

    out_f = os.path.join(OUT_DIR, f"gleam_event_master_{tag}.parquet")
    df.to_parquet(out_f, index=False)
    print(f"  Saved: {out_f}")
    all_dfs.append(df)

# combine
print("\nCombining all files...")
df_all = pd.concat(all_dfs, ignore_index=True)
print(f"\nCombined: {len(df_all):,} events (response=1, veg only)")
print(f"  recovered=1: {df_all.recovered.sum():,}")
print(f"  recovered=0: {(df_all.recovered==0).sum():,}")
print("  By metric (recovered=1):")
for m, g in df_all[df_all.recovered==1].groupby("metric"):
    print(f"    {m}: {len(g):,}")
print("  By func_name (recovered=1):")
for fn, g in df_all[df_all.recovered==1].groupby("func_name"):
    print(f"    {fn}: {len(g):,}")
matched_ok = df_all["drought_class"].apply(lambda x: isinstance(x, str) and x != "")
print(f"  Overall morphology match rate: {matched_ok.mean()*100:.1f}%")

out_all = os.path.join(OUT_DIR, "gleam_event_master_table.parquet")
df_all.to_parquet(out_all, index=False)
print(f"\nSaved combined: {out_all}")
