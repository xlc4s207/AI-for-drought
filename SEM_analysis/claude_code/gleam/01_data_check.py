"""01_data_check.py
Stage 0: Check all 12 GLEAM target files for field consistency,
event counts, recovery time distribution, and missing rates.
Output: results/data_check_report.txt
"""
import xarray as xr
import numpy as np
import os

BASE = "/home/xulc/flash_drought/process"
OUT_DIR = "/home/xulc/flash_drought/process/SEM_analysis/claude_code/gleam/results"
os.makedirs(OUT_DIR, exist_ok=True)

TARGET_FILES = [
    ("GPP", "code1", "SMrz", "flash",
     f"{BASE}/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("GPP", "code2", "SMs",  "flash",
     f"{BASE}/GPP-draught-analysis/code2_SMs/results/gpp_response_SMs_events_global_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("GPP", "code3", "SMrz", "slow",
     f"{BASE}/GPP-draught-analysis/code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("GPP", "code4", "SMs",  "slow",
     f"{BASE}/GPP-draught-analysis/code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("NEE", "code1", "SMrz", "flash",
     f"{BASE}/NEE-draught-analysis/code1SMrz/result/nee_response_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("NEE", "code2", "SMs",  "flash",
     f"{BASE}/NEE-draught-analysis/code2SMs/result/nee_response_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("NEE", "code3", "SMrz", "slow",
     f"{BASE}/NEE-draught-analysis/code3_nonflash_SMrz/result/nee_response_nonflash_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("NEE", "code4", "SMs",  "slow",
     f"{BASE}/NEE-draught-analysis/code4_nonflash_SMs/result/nee_response_nonflash_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("RECO", "code1", "SMrz", "flash",
     f"{BASE}/RECO-draught-analysis/code1/results/reco_response_SMrz_events_global_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("RECO", "code2", "SMs",  "flash",
     f"{BASE}/RECO-draught-analysis/code2_SMs/results/reco_response_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("RECO", "code3", "SMrz", "slow",
     f"{BASE}/RECO-draught-analysis/code3_nonflash_SMrz/result/reco_response_nonflash_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ("RECO", "code4", "SMs",  "slow",
     f"{BASE}/RECO-draught-analysis/code4_nonflash_SMs/result/reco_response_nonflash_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
]

# Key fields expected in every file
KEY_FIELDS = [
    "lat", "lon", "onset_year", "onset_doy",
    "drought_start_year", "drought_start_doy",
    "response_detected",
    "t_response_onset_start", "t_response_drought_start",
    "t_peak_abs",
    "t_recover_to_baseline_abs_peak",
    "t_recover_post_drought",
    "legacy_duration",
]

# Metric-specific peak field
METRIC_PEAK_FIELD = {
    "GPP":  "gpp_change_to_peak_abs",
    "NEE":  "nee_change_to_peak_abs",
    "RECO": "reco_change_to_peak_abs",
}

lines = []
lines.append("=" * 80)
lines.append("GLEAM Target File Check Report")
lines.append("=" * 80)

all_vars_seen = {}
missing_files = []

for metric, code, sm_type, drought_type, fpath in TARGET_FILES:
    tag = f"{metric}_{code}_{sm_type}_{drought_type}"
    lines.append(f"\n{'─'*70}")
    lines.append(f"[{tag}]")
    lines.append(f"  path: {fpath}")

    if not os.path.exists(fpath):
        lines.append("  STATUS: FILE NOT FOUND")
        missing_files.append(tag)
        continue

    ds = xr.open_dataset(fpath)
    n_total = ds.sizes["event"]
    avail_vars = list(ds.data_vars)
    all_vars_seen[tag] = set(avail_vars)

    # Check key fields presence
    peak_field = METRIC_PEAK_FIELD[metric]
    check_fields = KEY_FIELDS + [peak_field]
    missing_fields = [f for f in check_fields if f not in avail_vars]

    lines.append(f"  total events : {n_total:>10,}")
    lines.append(f"  variables    : {len(avail_vars)}")

    if missing_fields:
        lines.append(f"  MISSING FIELDS: {missing_fields}")
    else:
        lines.append(f"  key fields   : ALL PRESENT")

    # Response & recovery stats
    resp = ds["response_detected"].values
    n_resp = int((resp == 1).sum())
    lines.append(f"  response_detected=1 : {n_resp:>10,} ({100*n_resp/n_total:.1f}%)")

    trec = ds["t_recover_to_baseline_abs_peak"].values
    mask_main = (resp == 1) & np.isfinite(trec) & (trec >= 0)
    n_main = int(mask_main.sum())
    lines.append(f"  main analysis sample: {n_main:>10,} ({100*n_main/n_total:.1f}%)")

    if n_main > 0:
        v = trec[mask_main]
        lines.append(f"  t_recover [days] mean={v.mean():.1f}  median={np.median(v):.1f}  "
                     f"p5={np.percentile(v,5):.1f}  p95={np.percentile(v,95):.1f}  max={v.max():.1f}")

    # onset_year range
    oy = ds["onset_year"].values
    oy_valid = oy[np.isfinite(oy)]
    lines.append(f"  onset_year range: {int(oy_valid.min())}–{int(oy_valid.max())}")

    # lat/lon range (main sample)
    lats = ds["lat"].values[mask_main]
    lons = ds["lon"].values[mask_main]
    lines.append(f"  lat range (main): {lats.min():.2f} – {lats.max():.2f}")
    lines.append(f"  lon range (main): {lons.min():.2f} – {lons.max():.2f}")

    # Check t_peak_abs and t_response fields
    for fld in ["t_peak_abs", "t_response_onset_start", "legacy_duration"]:
        if fld in ds:
            arr = ds[fld].values[mask_main]
            arr_v = arr[np.isfinite(arr)]
            if len(arr_v) > 0:
                lines.append(f"  {fld}: mean={arr_v.mean():.1f}  max={arr_v.max():.1f}")

    # NaN rate of key recovery field among response=1
    resp1_mask = resp == 1
    trec_resp1 = trec[resp1_mask]
    nan_rate = np.mean(~np.isfinite(trec_resp1))
    lines.append(f"  t_recover NaN rate (among response=1): {100*nan_rate:.1f}%")

    ds.close()

# Cross-file variable consistency check
lines.append(f"\n{'='*70}")
lines.append("Variable Consistency Across Files")
lines.append(f"{'='*70}")
if all_vars_seen:
    all_vars = set.intersection(*all_vars_seen.values())
    lines.append(f"  Variables present in ALL 12 files: {len(all_vars)}")
    any_vars = set.union(*all_vars_seen.values())
    diff = any_vars - all_vars
    if diff:
        lines.append(f"  Variables NOT in all files: {sorted(diff)}")
    else:
        lines.append("  All files share identical variable sets.")

if missing_files:
    lines.append(f"\nMISSING FILES ({len(missing_files)}): {missing_files}")
else:
    lines.append("\nAll 12 files found.")

lines.append("\n" + "=" * 80)
lines.append("END OF REPORT")
lines.append("=" * 80)

report = "\n".join(lines)
print(report)

out_path = os.path.join(OUT_DIR, "data_check_report.txt")
with open(out_path, "w") as f:
    f.write(report)
print(f"\nReport saved to: {out_path}")
