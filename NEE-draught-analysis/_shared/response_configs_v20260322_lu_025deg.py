#!/usr/bin/env python3
"""Configuration registry for 0.25 degree v20260322_lu compact drought-response scripts."""

import copy
import os


BASE_DIR = "/home/xulc/flash_drought"

GPP_FILE = "/data/BESS_V2/BESS_GPP_1982_2022_0.25deg.nc"
FLUXSAT_GPP_FILE = (
    "/home/xulc/flash_drought/process/fluxsat-draught-analysis/preprocess/results/"
    "FluxSat_GPP_2000_2019_0.25deg.nc"
)
FLUXSAT_GPP_FILE_FIXLON = (
    "/home/xulc/flash_drought/process/fluxsat-draught-analysis/preprocess/results/"
    "FluxSat_GPP_2000_2019_0.25deg_fixlon_v20260426.nc"
)
NEE_FILE = "/data/BESS_V2/NEE_1982-2022_0.25deg.nc"
RECO_FILE = "/data/BESS_V2/BESS_RECO_1982-2022_0.25deg.nc"

FLASH_SMRZ_FILE = os.path.join(
    BASE_DIR,
    "gleam/clip_result/SMrz_result_v5.4_0p25deg_no_ice_desert/flash_lt20_drought_events_v5.4.nc",
)
FLASH_SMS_FILE = os.path.join(
    BASE_DIR,
    "gleam/clip_result/SMs_result_v5.4_0p25deg_no_ice_desert/flash_lt20_drought_events_v5.4.nc",
)
NONFLASH_SMRZ_FILE = os.path.join(
    BASE_DIR,
    "gleam/clip_result/SMrz_result_v5.4_0p25deg_no_ice_desert/slow_gt20_drought_events_v5.4.nc",
)
NONFLASH_SMS_FILE = os.path.join(
    BASE_DIR,
    "gleam/clip_result/SMs_result_v5.4_0p25deg_no_ice_desert/slow_gt20_drought_events_v5.4.nc",
)
ERA5L_ROOT_FLASH_FILE = os.path.join(
    BASE_DIR,
    "era5/clip_result/ERA5L_root_result_v5.4_0p25deg_no_ice_desert/flash_lt20_drought_events_v5.4.nc",
)
ERA5L_SWVL1_FLASH_FILE = os.path.join(
    BASE_DIR,
    "era5/clip_result/ERA5L_swvl1_result_v5.4_0p25deg_no_ice_desert/flash_lt20_drought_events_v5.4.nc",
)
ERA5L_ROOT_NONFLASH_FILE = os.path.join(
    BASE_DIR,
    "era5/clip_result/ERA5L_root_result_v5.4_0p25deg_no_ice_desert/slow_gt20_drought_events_v5.4.nc",
)
ERA5L_SWVL1_NONFLASH_FILE = os.path.join(
    BASE_DIR,
    "era5/clip_result/ERA5L_swvl1_result_v5.4_0p25deg_no_ice_desert/slow_gt20_drought_events_v5.4.nc",
)


def _common(metric_name, data_var, data_file, direction, output_dir):
    return {
        "start_year": 1982,
        "end_year": 2022,
        "window_before": 60,
        "window_after": 180,
        "window_after_from_drought_start": 360,
        "recovery_window": 120,
        "max_window_after": 600,
        "response_search_window": 360,
        "recovery_consecutive_days": 3,
        "baseline_recovery_consecutive_days": 3,
        "anomaly_recovery_consecutive_days": 5,
        "exclude_if_onset_already_affected": False,
        "min_affected_days_for_event": 5,
        "recovery_anomaly_threshold": -0.2,
        "anomaly_source": "climatology_zscore",
        "response_logic": "legacy_relative",
        "legacy_response_threshold": -0.5,
        "legacy_recovery_threshold": -0.2,
        "legacy_consecutive_days": 5,
        "legacy_ignore_overlap_exclusion": False,
        "legacy_peak_mode": "relative_anomaly",
        "legacy_recovery_mode": "threshold_anomaly",
        "require_post_drought_decline": False,
        "post_drought_decline_search_days": 30,
        "post_drought_decline_consecutive_days": 5,
        "baseline_tolerance_multiplier": 0.5,
        "baseline_tolerance_floor_fraction": 0.02,
        "smooth_window": 5,
        "spline_agg_days": 8,
        "spline_smooth_factor_multiplier": 0.5,
        "spline_min_valid_points": 120,
        "absolute_baseline_mode": "climatology_pre_days",
        "recovery_rate_baseline_mode": "climatology_pre_days",
        "absolute_baseline_days": 10,
        "absolute_baseline_scale": 1.0,
        "data_scale": 1.0,
        "max_valid_recovery_days": None,
        "ignore_overlap_exclusion": False,
        "min_abs_at_drought_start_for_response": 20.0,
        "min_valid_values": 100,
        "metric_name": metric_name,
        "data_var": data_var,
        "data_file": data_file,
        "direction": direction,
        "output_dir": output_dir,
    }


def _gpp_output(name):
    return os.path.join(BASE_DIR, f"process/GPP-draught-analysis/{name}")


def _nee_output(name):
    return os.path.join(BASE_DIR, f"process/NEE-draught-analysis/{name}")


def _reco_output(name):
    return os.path.join(BASE_DIR, f"process/RECO-draught-analysis/{name}")


def _fluxsat_output(name):
    return os.path.join(BASE_DIR, f"process/fluxsat-draught-analysis/{name}")


CONFIGS = {
    "gpp_code1": {
        **_common("gpp", "GPP", GPP_FILE, "negative", _gpp_output("code1/results")),
        "event_mode": "flash",
        "event_file": FLASH_SMRZ_FILE,
        "n_workers": 16,
        "lat_chunk_size": 20,
        "title": "GPP Response to SMrz Flash Drought - v20260322_lu_025deg",
        "description": "Compact GPP response metrics for v5.4 SMrz flash drought events at 0.25 degree.",
        "relative_output_file": _gpp_output("code1/results/gpp_response_SMrz_events_global_v20260322_lu_025deg.nc"),
        "with_abs_output_file": _gpp_output("code1/results/gpp_response_SMrz_events_global_v20260322_lu_025deg.nc"),
        "temp_dir": _gpp_output("code1/results/temp_chunks_v20260322_lu_025deg"),
    },
    "gpp_code1_rel_m02": {
        **_common("gpp", "GPP", GPP_FILE, "negative", _gpp_output("code1/results")),
        "event_mode": "flash",
        "event_file": FLASH_SMRZ_FILE,
        "n_workers": 16,
        "lat_chunk_size": 20,
        "title": "GPP Response to SMrz Flash Drought - v20260323_rel_m02",
        "description": (
            "Legacy relative z-score response logic with recovery threshold at -0.2 "
            "for v5.4 SMrz flash drought events at 0.25 degree."
        ),
        "response_logic": "legacy_relative",
        "legacy_response_threshold": -0.5,
        "legacy_recovery_threshold": -0.2,
        "legacy_consecutive_days": 5,
        "legacy_ignore_overlap_exclusion": True,
        "exclude_if_onset_already_affected": False,
        "min_affected_days_for_event": 1,
        "relative_output_file": _gpp_output("code1/results/gpp_response_SMrz_events_global_v20260323_rel_m02.nc"),
        "with_abs_output_file": _gpp_output("code1/results/gpp_response_SMrz_events_global_v20260323_rel_m02.nc"),
        "temp_dir": _gpp_output("code1/results/temp_chunks_v20260323_rel_m02"),
    },
    "gpp_code2": {
        **_common("gpp", "GPP", GPP_FILE, "negative", _gpp_output("code2_SMs/results")),
        "event_mode": "flash",
        "event_file": FLASH_SMS_FILE,
        "n_workers": 16,
        "lat_chunk_size": 20,
        "title": "GPP Response to SMs Flash Drought - v20260322_lu_025deg",
        "description": "Compact GPP response metrics for v5.4 SMs flash drought events at 0.25 degree.",
        "relative_output_file": _gpp_output("code2_SMs/results/gpp_response_SMs_events_global_v20260322_lu_025deg.nc"),
        "with_abs_output_file": _gpp_output("code2_SMs/results/gpp_response_SMs_events_global_v20260322_lu_025deg.nc"),
        "temp_dir": _gpp_output("code2_SMs/results/temp_chunks_v20260322_lu_025deg"),
    },
    "gpp_code3": {
        **_common("gpp", "GPP", GPP_FILE, "negative", _gpp_output("code3_nonflash_SMrz/result")),
        "event_mode": "nonflash",
        "event_file": NONFLASH_SMRZ_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "GPP Response to SMrz Slow Drought - v20260322_lu_025deg",
        "description": "Compact GPP response metrics for v5.4 SMrz slow drought events at 0.25 degree.",
        "relative_output_file": _gpp_output(
            "code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v20260322_lu_025deg.nc"
        ),
        "with_abs_output_file": _gpp_output(
            "code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v20260322_lu_025deg.nc"
        ),
        "temp_dir": _gpp_output("code3_nonflash_SMrz/result/temp_chunks_v20260322_lu_025deg"),
    },
    "gpp_code4": {
        **_common("gpp", "GPP", GPP_FILE, "negative", _gpp_output("code4_nonflash_SMs/result")),
        "event_mode": "nonflash",
        "event_file": NONFLASH_SMS_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "GPP Response to SMs Slow Drought - v20260322_lu_025deg",
        "description": "Compact GPP response metrics for v5.4 SMs slow drought events at 0.25 degree.",
        "relative_output_file": _gpp_output(
            "code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v20260322_lu_025deg.nc"
        ),
        "with_abs_output_file": _gpp_output(
            "code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v20260322_lu_025deg.nc"
        ),
        "temp_dir": _gpp_output("code4_nonflash_SMs/result/temp_chunks_v20260322_lu_025deg"),
    },
    "nee_code1": {
        **_common("nee", "NEE", NEE_FILE, "positive", _nee_output("code1SMrz/result")),
        "event_mode": "flash",
        "event_file": FLASH_SMRZ_FILE,
        "n_workers": 16,
        "lat_chunk_size": 20,
        "title": "NEE Response to SMrz Flash Drought - v20260322_lu_025deg",
        "description": "Compact NEE response metrics for v5.4 SMrz flash drought events at 0.25 degree.",
        "relative_output_file": _nee_output("code1SMrz/result/nee_response_SMrz_drought_v20260322_lu_025deg.nc"),
        "with_abs_output_file": _nee_output(
            "code1SMrz/result/nee_response_SMrz_drought_v20260322_lu_025deg.nc"
        ),
        "temp_dir": _nee_output("code1SMrz/result/temp_chunks_v20260322_lu_025deg"),
    },
    "nee_code2": {
        **_common("nee", "NEE", NEE_FILE, "positive", _nee_output("code2SMs/result")),
        "event_mode": "flash",
        "event_file": FLASH_SMS_FILE,
        "n_workers": 16,
        "lat_chunk_size": 20,
        "title": "NEE Response to SMs Flash Drought - v20260322_lu_025deg",
        "description": "Compact NEE response metrics for v5.4 SMs flash drought events at 0.25 degree.",
        "relative_output_file": _nee_output("code2SMs/result/nee_response_SMs_drought_v20260322_lu_025deg.nc"),
        "with_abs_output_file": _nee_output("code2SMs/result/nee_response_SMs_drought_v20260322_lu_025deg.nc"),
        "temp_dir": _nee_output("code2SMs/result/temp_chunks_v20260322_lu_025deg"),
    },
    "nee_code3": {
        **_common("nee", "NEE", NEE_FILE, "positive", _nee_output("code3_nonflash_SMrz/result")),
        "event_mode": "nonflash",
        "event_file": NONFLASH_SMRZ_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "NEE Response to SMrz Slow Drought - v20260322_lu_025deg",
        "description": "Compact NEE response metrics for v5.4 SMrz slow drought events at 0.25 degree.",
        "relative_output_file": _nee_output(
            "code3_nonflash_SMrz/result/nee_response_nonflash_SMrz_drought_v20260322_lu_025deg.nc"
        ),
        "with_abs_output_file": _nee_output(
            "code3_nonflash_SMrz/result/nee_response_nonflash_SMrz_drought_v20260322_lu_025deg.nc"
        ),
        "temp_dir": _nee_output("code3_nonflash_SMrz/result/temp_chunks_v20260322_lu_025deg"),
    },
    "nee_code4": {
        **_common("nee", "NEE", NEE_FILE, "positive", _nee_output("code4_nonflash_SMs/result")),
        "event_mode": "nonflash",
        "event_file": NONFLASH_SMS_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "NEE Response to SMs Slow Drought - v20260322_lu_025deg",
        "description": "Compact NEE response metrics for v5.4 SMs slow drought events at 0.25 degree.",
        "relative_output_file": _nee_output(
            "code4_nonflash_SMs/result/nee_response_nonflash_SMs_drought_v20260322_lu_025deg.nc"
        ),
        "with_abs_output_file": _nee_output(
            "code4_nonflash_SMs/result/nee_response_nonflash_SMs_drought_v20260322_lu_025deg.nc"
        ),
        "temp_dir": _nee_output("code4_nonflash_SMs/result/temp_chunks_v20260322_lu_025deg"),
    },
    "reco_code1": {
        **_common("reco", "RECO", RECO_FILE, "negative", _reco_output("code1/results")),
        "event_mode": "flash",
        "event_file": FLASH_SMRZ_FILE,
        "n_workers": 16,
        "lat_chunk_size": 20,
        "title": "RECO Response to SMrz Flash Drought - v20260322_lu_025deg",
        "description": "Compact RECO response metrics for v5.4 SMrz flash drought events at 0.25 degree.",
        "relative_output_file": _reco_output("code1/results/reco_response_SMrz_events_global_v20260322_lu_025deg.nc"),
        "with_abs_output_file": _reco_output(
            "code1/results/reco_response_SMrz_events_global_v20260322_lu_025deg.nc"
        ),
        "temp_dir": _reco_output("code1/results/temp_chunks_v20260322_lu_025deg"),
    },
    "reco_code2": {
        **_common("reco", "RECO", RECO_FILE, "negative", _reco_output("code2_SMs/results")),
        "event_mode": "flash",
        "event_file": FLASH_SMS_FILE,
        "n_workers": 16,
        "lat_chunk_size": 20,
        "title": "RECO Response to SMs Flash Drought - v20260322_lu_025deg",
        "description": "Compact RECO response metrics for v5.4 SMs flash drought events at 0.25 degree.",
        "relative_output_file": _reco_output("code2_SMs/results/reco_response_SMs_drought_v20260322_lu_025deg.nc"),
        "with_abs_output_file": _reco_output(
            "code2_SMs/results/reco_response_SMs_drought_v20260322_lu_025deg.nc"
        ),
        "temp_dir": _reco_output("code2_SMs/results/temp_chunks_v20260322_lu_025deg"),
    },
    "reco_code3": {
        **_common("reco", "RECO", RECO_FILE, "negative", _reco_output("code3_nonflash_SMrz/result")),
        "event_mode": "nonflash",
        "event_file": NONFLASH_SMRZ_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "RECO Response to SMrz Slow Drought - v20260322_lu_025deg",
        "description": "Compact RECO response metrics for v5.4 SMrz slow drought events at 0.25 degree.",
        "relative_output_file": _reco_output(
            "code3_nonflash_SMrz/result/reco_response_nonflash_SMrz_drought_v20260322_lu_025deg.nc"
        ),
        "with_abs_output_file": _reco_output(
            "code3_nonflash_SMrz/result/reco_response_nonflash_SMrz_drought_v20260322_lu_025deg.nc"
        ),
        "temp_dir": _reco_output("code3_nonflash_SMrz/result/temp_chunks_v20260322_lu_025deg"),
    },
    "reco_code4": {
        **_common("reco", "RECO", RECO_FILE, "negative", _reco_output("code4_nonflash_SMs/result")),
        "event_mode": "nonflash",
        "event_file": NONFLASH_SMS_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "RECO Response to SMs Slow Drought - v20260322_lu_025deg",
        "description": "Compact RECO response metrics for v5.4 SMs slow drought events at 0.25 degree.",
        "relative_output_file": _reco_output(
            "code4_nonflash_SMs/result/reco_response_nonflash_SMs_drought_v20260322_lu_025deg.nc"
        ),
        "with_abs_output_file": _reco_output(
            "code4_nonflash_SMs/result/reco_response_nonflash_SMs_drought_v20260322_lu_025deg.nc"
        ),
        "temp_dir": _reco_output("code4_nonflash_SMs/result/temp_chunks_v20260322_lu_025deg"),
    },
}

# Lat-alignment hotfix variants:
# keep legacy v20260322 outputs untouched and write repaired runs to v20260323_latfix files.
_LATFIX_BASE_KEYS = [
    "gpp_code1",
    "gpp_code2",
    "gpp_code3",
    "gpp_code4",
    "nee_code1",
    "nee_code2",
    "nee_code3",
    "nee_code4",
    "reco_code1",
    "reco_code2",
    "reco_code3",
    "reco_code4",
]

for _base_key in _LATFIX_BASE_KEYS:
    _cfg = copy.deepcopy(CONFIGS[_base_key])
    _cfg["title"] = _cfg["title"].replace("v20260322_lu_025deg", "v20260323_latfix")
    _cfg["description"] = (
        _cfg["description"]
        + " Lat-alignment hotfix enabled (auto event-data axis mapping)."
    )
    _cfg["relative_output_file"] = _cfg["relative_output_file"].replace(
        "v20260322_lu_025deg", "v20260323_latfix"
    )
    _cfg["with_abs_output_file"] = _cfg["with_abs_output_file"].replace(
        "v20260322_lu_025deg", "v20260323_latfix"
    )
    _cfg["temp_dir"] = _cfg["temp_dir"].replace("v20260322_lu_025deg", "v20260323_latfix")
    CONFIGS[f"{_base_key}_latfix"] = _cfg

# GPP SMrz flash: keep latfix, but relax anomaly recovery threshold to z > -0.2.
CONFIGS["gpp_code1_latfix_rec_m02"] = copy.deepcopy(CONFIGS["gpp_code1_latfix"])
CONFIGS["gpp_code1_latfix_rec_m02"]["title"] = (
    "GPP Response to SMrz Flash Drought - v20260323_latfix_rec_m02"
)
CONFIGS["gpp_code1_latfix_rec_m02"]["description"] = (
    "Latfix run with anomaly-recovery threshold at z > -0.2 (relative metric)."
)
CONFIGS["gpp_code1_latfix_rec_m02"]["recovery_anomaly_threshold"] = -0.2
CONFIGS["gpp_code1_latfix_rec_m02"]["relative_output_file"] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260323_latfix_rec_m02.nc"
)
CONFIGS["gpp_code1_latfix_rec_m02"]["with_abs_output_file"] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260323_latfix_rec_m02.nc"
)
CONFIGS["gpp_code1_latfix_rec_m02"]["temp_dir"] = _gpp_output(
    "code1/results/temp_chunks_v20260323_latfix_rec_m02"
)

# GPP SMrz flash custom definition requested by user:
# 1) response: z <= -0.5 for 5 consecutive days after drought_start
# 2) recovery: z > -0.2 for 5 consecutive days
# 3) window: drought_start + 360 days
# 4) absolute metrics/recovery rate baselines: climatology-based pre-10-day reference
CONFIGS["gpp_code1_latfix_relm05_rec_m02_c10_w360"] = copy.deepcopy(CONFIGS["gpp_code1_latfix"])
CONFIGS["gpp_code1_latfix_relm05_rec_m02_c10_w360"]["title"] = (
    "GPP Response to SMrz Flash Drought - v20260323_latfix_relm05_rec_m02_c10_w360"
)
CONFIGS["gpp_code1_latfix_relm05_rec_m02_c10_w360"]["description"] = (
    "User custom: legacy relative thresholds (-0.5/-0.2, 5-day), "
    "window = drought_start + 360d, climatology pre-10d baseline for absolute change and recovery rate."
)
CONFIGS["gpp_code1_latfix_relm05_rec_m02_c10_w360"]["response_logic"] = "legacy_relative"
CONFIGS["gpp_code1_latfix_relm05_rec_m02_c10_w360"]["legacy_response_threshold"] = -0.5
CONFIGS["gpp_code1_latfix_relm05_rec_m02_c10_w360"]["legacy_recovery_threshold"] = -0.2
CONFIGS["gpp_code1_latfix_relm05_rec_m02_c10_w360"]["legacy_consecutive_days"] = 5
CONFIGS["gpp_code1_latfix_relm05_rec_m02_c10_w360"]["legacy_ignore_overlap_exclusion"] = True
CONFIGS["gpp_code1_latfix_relm05_rec_m02_c10_w360"]["response_search_window"] = 360
CONFIGS["gpp_code1_latfix_relm05_rec_m02_c10_w360"]["window_after_from_drought_start"] = 360
CONFIGS["gpp_code1_latfix_relm05_rec_m02_c10_w360"]["smooth_window"] = 5
CONFIGS["gpp_code1_latfix_relm05_rec_m02_c10_w360"]["absolute_baseline_mode"] = "climatology_pre_days"
CONFIGS["gpp_code1_latfix_relm05_rec_m02_c10_w360"]["recovery_rate_baseline_mode"] = "climatology_pre_days"
CONFIGS["gpp_code1_latfix_relm05_rec_m02_c10_w360"]["absolute_baseline_days"] = 10
CONFIGS["gpp_code1_latfix_relm05_rec_m02_c10_w360"]["relative_output_file"] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260323_latfix_relm05_rec_m02_c10_w360.nc"
)
CONFIGS["gpp_code1_latfix_relm05_rec_m02_c10_w360"]["with_abs_output_file"] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260323_latfix_relm05_rec_m02_c10_w360.nc"
)
CONFIGS["gpp_code1_latfix_relm05_rec_m02_c10_w360"]["temp_dir"] = _gpp_output(
    "code1/results/temp_chunks_v20260323_latfix_relm05_rec_m02_c10_w360"
)

# GPP SMrz flash custom definition requested on 2026-03-24:
# 1) response: z <= -0.3 for 5 consecutive days
# 2) peak: minimum of 5-day smoothed absolute GPP between drought_start and sustained recovery
# 3) recovery: 5-day smoothed absolute GPP >= pre-drought-10-day baseline for 5 consecutive days
# 4) window: drought_start + 360 days
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w360"] = copy.deepcopy(CONFIGS["gpp_code1"])
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w360"]["title"] = (
    "GPP Response to SMrz Flash Drought - v20260324_latfix_relm03_abspeak_absrec_c10_w360"
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w360"]["description"] = (
    "User custom: response uses relative z <= -0.3 for 5 days; "
    "peak uses 5-day smoothed absolute GPP minimum; "
    "recovery uses pre-drought 10-day baseline on 5-day smoothed absolute GPP for 5 days; "
    "window = drought_start + 360d."
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w360"]["response_logic"] = "legacy_relative"
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w360"]["legacy_response_threshold"] = -0.3
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w360"]["legacy_recovery_threshold"] = -0.2
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w360"]["legacy_consecutive_days"] = 5
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w360"]["legacy_ignore_overlap_exclusion"] = True
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w360"]["legacy_peak_mode"] = "smoothed_absolute_min"
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w360"]["legacy_recovery_mode"] = (
    "absolute_baseline"
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w360"]["response_search_window"] = 360
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w360"]["window_after_from_drought_start"] = 360
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w360"]["smooth_window"] = 5
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w360"]["absolute_baseline_mode"] = "pre_days_raw"
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w360"]["recovery_rate_baseline_mode"] = (
    "pre_days_raw"
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w360"]["absolute_baseline_days"] = 10
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w360"]["relative_output_file"] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260324_latfix_relm03_abspeak_absrec_c10_w360.nc"
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w360"]["with_abs_output_file"] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260324_latfix_relm03_abspeak_absrec_c10_w360.nc"
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w360"]["temp_dir"] = _gpp_output(
    "code1/results/temp_chunks_v20260324_latfix_relm03_abspeak_absrec_c10_w360"
)

CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w420"] = copy.deepcopy(
    CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w360"]
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w420"]["title"] = (
    "GPP Response to SMrz Flash Drought - v20260324_latfix_relm03_abspeak_absrec_c10_w420"
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w420"]["description"] = (
    "User custom: response uses relative z <= -0.3 for 5 days; "
    "peak uses 5-day smoothed absolute GPP minimum; "
    "recovery uses pre-drought 10-day baseline on 5-day smoothed absolute GPP for 5 days; "
    "window = drought_start + 420d."
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w420"]["response_search_window"] = 420
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w420"]["window_after_from_drought_start"] = 420
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w420"]["relative_output_file"] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260324_latfix_relm03_abspeak_absrec_c10_w420.nc"
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w420"]["with_abs_output_file"] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260324_latfix_relm03_abspeak_absrec_c10_w420.nc"
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w420"]["temp_dir"] = _gpp_output(
    "code1/results/temp_chunks_v20260324_latfix_relm03_abspeak_absrec_c10_w420"
)

CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30_w420_decline30_d5"] = copy.deepcopy(
    CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c10_w420"]
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30_w420_decline30_d5"]["title"] = (
    "GPP Response to SMrz Flash Drought - v20260324_latfix_relm03_abspeak_absrec_c30_w420_decline30_d5"
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30_w420_decline30_d5"]["description"] = (
    "User custom: response uses relative z <= -0.3 for 5 days, but only for events with a sustained "
    "5-day decline within 30 days after drought start; peak uses 5-day smoothed absolute GPP minimum; "
    "recovery uses pre-drought 30-day baseline on 5-day smoothed absolute GPP for 5 days; "
    "window = drought_start + 420d."
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30_w420_decline30_d5"]["absolute_baseline_days"] = 30
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30_w420_decline30_d5"][
    "require_post_drought_decline"
] = True
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30_w420_decline30_d5"][
    "post_drought_decline_search_days"
] = 30
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30_w420_decline30_d5"][
    "post_drought_decline_consecutive_days"
] = 5
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30_w420_decline30_d5"]["relative_output_file"] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260324_latfix_relm03_abspeak_absrec_c30_w420_decline30_d5.nc"
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30_w420_decline30_d5"]["with_abs_output_file"] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260324_latfix_relm03_abspeak_absrec_c30_w420_decline30_d5.nc"
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30_w420_decline30_d5"]["temp_dir"] = _gpp_output(
    "code1/results/temp_chunks_v20260324_latfix_relm03_abspeak_absrec_c30_w420_decline30_d5"
)

CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec120"] = copy.deepcopy(
    CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30_w420_decline30_d5"]
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec120"]["title"] = (
    "GPP Response to SMrz Flash Drought - v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec120"
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec120"]["description"] = (
    "User custom: response uses relative z <= -0.3 for 5 days, but only for events with a sustained "
    "5-day decline within 30 days after drought start; recovery baseline uses 0.95 x pre-drought "
    "30-day mean on 5-day smoothed absolute GPP; recovery longer than 120 days is treated as seasonal "
    "variation and not counted as valid recovery; window = drought_start + 420d."
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec120"][
    "absolute_baseline_scale"
] = 0.95
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec120"][
    "max_valid_recovery_days"
] = 120
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec120"][
    "relative_output_file"
] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec120.nc"
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec120"][
    "with_abs_output_file"
] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec120.nc"
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec120"]["temp_dir"] = (
    _gpp_output("code1/results/temp_chunks_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec120")
)

CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"] = copy.deepcopy(
    CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec120"]
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"]["title"] = (
    "GPP Response to SMrz Flash Drought - v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"]["description"] = (
    "User custom: response uses relative z <= -0.3 for 5 days, but only for events with a sustained "
    "5-day decline within 30 days after drought start; recovery baseline uses 0.95 x pre-drought "
    "30-day mean on 5-day smoothed absolute GPP; recovery longer than 100 days is treated as seasonal "
    "variation and not counted as valid recovery; window = drought_start + 420d."
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][
    "max_valid_recovery_days"
] = 100
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][
    "relative_output_file"
] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][
    "with_abs_output_file"
] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"
)
CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"]["temp_dir"] = (
    _gpp_output("code1/results/temp_chunks_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100")
)

CONFIGS["gpp_code1_v20260325_zhao_spline_control"] = copy.deepcopy(
    CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"]
)
CONFIGS["gpp_code1_v20260325_zhao_spline_control"]["title"] = (
    "GPP Response to SMrz Flash Drought - v20260325_zhao_spline_control"
)
CONFIGS["gpp_code1_v20260325_zhao_spline_control"]["description"] = (
    "Paper-reference Zhao-style control for SMrz flash droughts: daily BESS GPP is aggregated internally to "
    "8-day means, a cubic smoothing spline baseline is fitted and interpolated back to daily scale, anomaly is "
    "defined as GPP minus spline baseline, response uses sustained negative anomalies, recovery uses sustained "
    "non-negative anomalies, and cumulative GPP loss is integrated from response onset to recovery. This 8-day "
    "configuration is retained for literature comparison and is not the regular production version."
)
for _cfg_key, _cfg_value in {
    "anomaly_source": "spline_residual",
    "response_logic": "zhao_spline_negative",
    "n_workers": 8,
    "lat_chunk_size": 10,
    "legacy_consecutive_days": 5,
    "anomaly_recovery_consecutive_days": 5,
    "recovery_anomaly_threshold": 0.0,
    "exclude_if_onset_already_affected": True,
    "min_affected_days_for_event": 5,
    "smooth_window": 5,
    "spline_agg_days": 8,
    "spline_smooth_factor_multiplier": 0.5,
    "spline_min_valid_points": 120,
    "require_post_drought_decline": False,
    "absolute_baseline_mode": "pre_days_raw",
    "recovery_rate_baseline_mode": "pre_days_raw",
    "absolute_baseline_days": 30,
    "absolute_baseline_scale": 0.95,
    "max_valid_recovery_days": 100,
}.items():
    CONFIGS["gpp_code1_v20260325_zhao_spline_control"][_cfg_key] = _cfg_value
CONFIGS["gpp_code1_v20260325_zhao_spline_control"]["relative_output_file"] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260325_zhao_spline_control.nc"
)
CONFIGS["gpp_code1_v20260325_zhao_spline_control"]["with_abs_output_file"] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260325_zhao_spline_control.nc"
)
CONFIGS["gpp_code1_v20260325_zhao_spline_control"]["temp_dir"] = _gpp_output(
    "code1/results/temp_chunks_v20260325_zhao_spline_control"
)

CONFIGS["gpp_code1_v20260326_zhao_spline_control_overlapopen"] = copy.deepcopy(
    CONFIGS["gpp_code1_v20260325_zhao_spline_control"]
)
CONFIGS["gpp_code1_v20260326_zhao_spline_control_overlapopen"]["title"] = (
    "GPP Response to SMrz Flash Drought - v20260326_zhao_spline_control_overlapopen"
)
CONFIGS["gpp_code1_v20260326_zhao_spline_control_overlapopen"]["description"] = (
    "Paper-reference Zhao-style spline control with overlap exclusion disabled for recovery detection; "
    "daily BESS GPP is aggregated internally to 8-day means, anomaly is defined as GPP minus spline baseline, "
    "and both post-drought recovery duration and cumulative losses are reported. This 8-day configuration is "
    "retained only for literature comparison and is not the regular production version."
)
CONFIGS["gpp_code1_v20260326_zhao_spline_control_overlapopen"]["ignore_overlap_exclusion"] = True
CONFIGS["gpp_code1_v20260326_zhao_spline_control_overlapopen"]["relative_output_file"] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260326_zhao_spline_control_overlapopen.nc"
)
CONFIGS["gpp_code1_v20260326_zhao_spline_control_overlapopen"]["with_abs_output_file"] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260326_zhao_spline_control_overlapopen.nc"
)
CONFIGS["gpp_code1_v20260326_zhao_spline_control_overlapopen"]["temp_dir"] = _gpp_output(
    "code1/results/temp_chunks_v20260326_zhao_spline_control_overlapopen"
)

CONFIGS["gpp_code1_v20260326_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought"] = (
    copy.deepcopy(CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"])
)
CONFIGS["gpp_code1_v20260326_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought"][
    "title"
] = (
    "GPP Response to SMrz Flash Drought - v20260326_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought"
)
CONFIGS["gpp_code1_v20260326_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought"][
    "description"
] = (
    "rec100 logic with added post-drought recovery duration field t_recover_post_drought, "
    "defined as recovery timing measured from drought end; all other rec100 response and recovery rules are unchanged."
)
CONFIGS["gpp_code1_v20260326_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought"][
    "relative_output_file"
] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260326_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought.nc"
)
CONFIGS["gpp_code1_v20260326_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought"][
    "with_abs_output_file"
] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260326_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought.nc"
)
CONFIGS["gpp_code1_v20260326_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought"][
    "temp_dir"
] = _gpp_output(
    "code1/results/temp_chunks_v20260326_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought"
)

CONFIGS["gpp_code1_v20260327_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought_spline5resp"] = (
    copy.deepcopy(CONFIGS["gpp_code1_v20260326_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought"])
)
CONFIGS["gpp_code1_v20260327_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought_spline5resp"][
    "title"
] = (
    "GPP Response to SMrz Flash Drought - v20260327_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought_spline5resp"
)
CONFIGS["gpp_code1_v20260327_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought_spline5resp"][
    "description"
] = (
    "Regular production version: rec100 main logic with t_recover_post_drought retained, plus an auxiliary "
    "spline5 response-only field group. The auxiliary group uses daily GPP cubic-spline residual anomalies built "
    "from 5-day aggregation, followed by 5-day smoothing and sustained negative-anomaly response detection. "
    "These spline5 fields are used only for response timing and peak diagnostics, not for recovery-time "
    "calculation."
)
CONFIGS["gpp_code1_v20260327_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought_spline5resp"][
    "aux_response_config"
] = {
    "prefix": "spline5",
    "anomaly_source": "spline_residual",
    "response_logic": "zhao_spline_negative",
    "direction": "negative",
    "smooth_window": 5,
    "spline_agg_days": 5,
    "spline_smooth_factor_multiplier": 0.5,
    "spline_min_valid_points": 120,
    "legacy_consecutive_days": 5,
    "min_affected_days_for_event": 5,
    "exclude_if_onset_already_affected": True,
    "response_search_window": 420,
}
CONFIGS["gpp_code1_v20260327_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought_spline5resp"][
    "relative_output_file"
] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260327_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought_spline5resp.nc"
)
CONFIGS["gpp_code1_v20260327_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought_spline5resp"][
    "with_abs_output_file"
] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260327_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought_spline5resp.nc"
)
CONFIGS["gpp_code1_v20260327_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought_spline5resp"][
    "temp_dir"
] = _gpp_output(
    "code1/results/temp_chunks_v20260327_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100_postdrought_spline5resp"
)

CONFIGS["gpp_code1_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"] = copy.deepcopy(
    CONFIGS["gpp_code1_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"]
)
CONFIGS["gpp_code1_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][
    "title"
] = (
    "GPP Response to SMrz Flash Drought - v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"
)
CONFIGS["gpp_code1_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][
    "description"
] = (
    "Control version against rec100: only the relative-response threshold is relaxed from z <= -0.3 "
    "to z <= 0 for 5 days; all other response, peak, recovery, baseline, and screening rules remain "
    "identical to the v20260324 rec100 configuration."
)
CONFIGS["gpp_code1_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][
    "legacy_response_threshold"
] = 0.0
CONFIGS["gpp_code1_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][
    "relative_output_file"
] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"
)
CONFIGS["gpp_code1_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][
    "with_abs_output_file"
] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"
)
CONFIGS["gpp_code1_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][
    "temp_dir"
] = _gpp_output(
    "code1/results/temp_chunks_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"
)

CONFIGS[
    "gpp_code1_v20260331_growingseason_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
] = copy.deepcopy(CONFIGS["gpp_code1_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"])
CONFIGS[
    "gpp_code1_v20260331_growingseason_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["title"] = (
    "GPP Response to SMrz Growing-Season Flash Drought - "
    "v20260331_growingseason_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
)
CONFIGS[
    "gpp_code1_v20260331_growingseason_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["description"] = (
    "Growing-season GPP response version derived from the v20260328 rel0 control: "
    "events are retained only when more than half of the drought duration falls within "
    "the annual growing season defined from ERA5 2 m temperature using sustained >5 C "
    "start and sustained <5 C end criteria; the maximum valid recovery-day cap is removed."
)
CONFIGS[
    "gpp_code1_v20260331_growingseason_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["growing_season_enabled"] = True
CONFIGS[
    "gpp_code1_v20260331_growingseason_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["growing_season_temp_file"] = "/data/era5_for_GRN/yearly/temperature_2m_0p25deg_1980_2024.nc"
CONFIGS[
    "gpp_code1_v20260331_growingseason_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["growing_season_temp_var"] = "temperature_2m"
CONFIGS[
    "gpp_code1_v20260331_growingseason_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["growing_season_temp_threshold_k"] = 278.15
CONFIGS[
    "gpp_code1_v20260331_growingseason_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["growing_season_min_consecutive_days"] = 5
CONFIGS[
    "gpp_code1_v20260331_growingseason_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["growing_season_min_fraction"] = 0.5
CONFIGS[
    "gpp_code1_v20260331_growingseason_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["max_valid_recovery_days"] = None
CONFIGS[
    "gpp_code1_v20260331_growingseason_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["relative_output_file"] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260331_growingseason_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
)
CONFIGS[
    "gpp_code1_v20260331_growingseason_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["with_abs_output_file"] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260331_growingseason_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
)
CONFIGS[
    "gpp_code1_v20260331_growingseason_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["temp_dir"] = _gpp_output(
    "code1/results/temp_chunks_v20260331_growingseason_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
)

CONFIGS[
    "gpp_code1_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
] = copy.deepcopy(
    CONFIGS["gpp_code1_v20260331_growingseason_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"]
)
CONFIGS[
    "gpp_code1_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["title"] = (
    "GPP Response to SMrz Growing-Season Flash Drought - "
    "v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
)
CONFIGS[
    "gpp_code1_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["description"] = (
    "Growing-season GPP response version derived from the 2026-03-31 growing-season control: "
    "events are still filtered by drought-season overlap, recovery can cross seasons, but "
    "recovery durations are counted using growing-season-effective days only."
)
CONFIGS[
    "gpp_code1_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["recovery_day_count_mode"] = "growing_season_only"
CONFIGS[
    "gpp_code1_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["relative_output_file"] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
)
CONFIGS[
    "gpp_code1_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["with_abs_output_file"] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
)
CONFIGS[
    "gpp_code1_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["temp_dir"] = _gpp_output(
    "code1/results/temp_chunks_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
)

CONFIGS[
    "gpp_code1_v20260514_allseason_recovery_elapsed_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
] = copy.deepcopy(
    CONFIGS["gpp_code1_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"]
)
CONFIGS[
    "gpp_code1_v20260514_allseason_recovery_elapsed_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["title"] = (
    "GPP Response to SMrz All-Season Flash Drought - "
    "v20260514_allseason_recovery_elapsed_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
)
CONFIGS[
    "gpp_code1_v20260514_allseason_recovery_elapsed_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["description"] = (
    "All-season GPP response version derived from the 2026-04-01 growing-season recovery control: "
    "the drought-event growing-season overlap filter is disabled, recovery duration is counted as "
    "elapsed calendar days from peak impact to baseline recovery, and max_valid_recovery_days remains None."
)
CONFIGS[
    "gpp_code1_v20260514_allseason_recovery_elapsed_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["growing_season_enabled"] = False
CONFIGS[
    "gpp_code1_v20260514_allseason_recovery_elapsed_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["recovery_day_count_mode"] = "elapsed_days"
CONFIGS[
    "gpp_code1_v20260514_allseason_recovery_elapsed_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["max_valid_recovery_days"] = None
CONFIGS[
    "gpp_code1_v20260514_allseason_recovery_elapsed_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["relative_output_file"] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260514_allseason_recovery_elapsed_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
)
CONFIGS[
    "gpp_code1_v20260514_allseason_recovery_elapsed_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["with_abs_output_file"] = _gpp_output(
    "code1/results/gpp_response_SMrz_events_global_v20260514_allseason_recovery_elapsed_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
)
CONFIGS[
    "gpp_code1_v20260514_allseason_recovery_elapsed_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
]["temp_dir"] = _gpp_output(
    "code1/results/temp_chunks_v20260514_allseason_recovery_elapsed_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
)

CONFIGS["gpp_code1_era5_root_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"] = copy.deepcopy(
    CONFIGS["gpp_code1_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"]
)
CONFIGS["gpp_code1_era5_root_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][
    "event_file"
] = ERA5L_ROOT_FLASH_FILE
CONFIGS["gpp_code1_era5_root_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][
    "title"
] = (
    "GPP Response to ERA5L Root Flash Drought - "
    "v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"
)
CONFIGS["gpp_code1_era5_root_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][
    "description"
] = (
    "ERA5L root-zone flash-drought version cloned from the GLEAM v20260328 rel0 control: "
    "same response, peak, recovery, baseline, and screening rules, but replacing the event "
    "catalog with ERA5L root flash events and writing outputs into an isolated ERA5 directory."
)
CONFIGS["gpp_code1_era5_root_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][
    "relative_output_file"
] = _gpp_output(
    "code1_ERA5_root/results/gpp_response_ERA5L_root_events_global_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"
)
CONFIGS["gpp_code1_era5_root_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][
    "with_abs_output_file"
] = _gpp_output(
    "code1_ERA5_root/results/gpp_response_ERA5L_root_events_global_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"
)
CONFIGS["gpp_code1_era5_root_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][
    "temp_dir"
] = _gpp_output(
    "code1_ERA5_root/results/temp_chunks_v20260330_era5_root_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"
)

CONFIGS["gpp_code2_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"] = copy.deepcopy(
    CONFIGS["gpp_code2_latfix"]
)
CONFIGS["gpp_code2_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"]["title"] = (
    "GPP Response to SMs Flash Drought - v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"
)
CONFIGS["gpp_code2_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"]["description"] = (
    "SMs flash version aligned to code1 rec100 logic: response uses relative z <= -0.3 for 5 days, "
    "requires a sustained 5-day decline within 30 days after drought start; recovery baseline uses "
    "0.95 x pre-drought 30-day mean on 5-day smoothed absolute GPP; recovery longer than 100 days is "
    "treated as seasonal variation; window = drought_start + 420d."
)
for _key, _value in {
    "response_logic": "legacy_relative",
    "legacy_response_threshold": -0.3,
    "legacy_recovery_threshold": -0.2,
    "legacy_consecutive_days": 5,
    "legacy_ignore_overlap_exclusion": True,
    "legacy_peak_mode": "smoothed_absolute_min",
    "legacy_recovery_mode": "absolute_baseline",
    "response_search_window": 420,
    "window_after_from_drought_start": 420,
    "smooth_window": 5,
    "absolute_baseline_mode": "pre_days_raw",
    "recovery_rate_baseline_mode": "pre_days_raw",
    "absolute_baseline_days": 30,
    "absolute_baseline_scale": 0.95,
    "require_post_drought_decline": True,
    "post_drought_decline_search_days": 30,
    "post_drought_decline_consecutive_days": 5,
    "max_valid_recovery_days": 100,
}.items():
    CONFIGS["gpp_code2_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][_key] = _value
CONFIGS["gpp_code2_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][
    "relative_output_file"
] = _gpp_output(
    "code2_SMs/results/gpp_response_SMs_events_global_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"
)
CONFIGS["gpp_code2_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][
    "with_abs_output_file"
] = _gpp_output(
    "code2_SMs/results/gpp_response_SMs_events_global_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"
)
CONFIGS["gpp_code2_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"]["temp_dir"] = (
    _gpp_output("code2_SMs/results/temp_chunks_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100")
)

CONFIGS["gpp_code3_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"] = copy.deepcopy(
    CONFIGS["gpp_code3_latfix"]
)
CONFIGS["gpp_code3_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"]["title"] = (
    "GPP Response to SMrz Slow Drought - v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"
)
CONFIGS["gpp_code3_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"]["description"] = (
    "SMrz slow-drought version aligned to code1 rec100 logic: response uses relative z <= -0.3 for 5 "
    "days, requires a sustained 5-day decline within 30 days after drought start; recovery baseline "
    "uses 0.95 x pre-drought 30-day mean on 5-day smoothed absolute GPP; recovery longer than 100 "
    "days is treated as seasonal variation; window = drought_start + 420d."
)
for _key, _value in {
    "response_logic": "legacy_relative",
    "legacy_response_threshold": -0.3,
    "legacy_recovery_threshold": -0.2,
    "legacy_consecutive_days": 5,
    "legacy_ignore_overlap_exclusion": True,
    "legacy_peak_mode": "smoothed_absolute_min",
    "legacy_recovery_mode": "absolute_baseline",
    "response_search_window": 420,
    "window_after_from_drought_start": 420,
    "smooth_window": 5,
    "absolute_baseline_mode": "pre_days_raw",
    "recovery_rate_baseline_mode": "pre_days_raw",
    "absolute_baseline_days": 30,
    "absolute_baseline_scale": 0.95,
    "require_post_drought_decline": True,
    "post_drought_decline_search_days": 30,
    "post_drought_decline_consecutive_days": 5,
    "max_valid_recovery_days": 100,
}.items():
    CONFIGS["gpp_code3_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][_key] = _value
CONFIGS["gpp_code3_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][
    "relative_output_file"
] = _gpp_output(
    "code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"
)
CONFIGS["gpp_code3_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][
    "with_abs_output_file"
] = _gpp_output(
    "code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"
)
CONFIGS["gpp_code3_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"]["temp_dir"] = (
    _gpp_output("code3_nonflash_SMrz/result/temp_chunks_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100")
)

CONFIGS["gpp_code4_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"] = copy.deepcopy(
    CONFIGS["gpp_code4_latfix"]
)
CONFIGS["gpp_code4_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"]["title"] = (
    "GPP Response to SMs Slow Drought - v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"
)
CONFIGS["gpp_code4_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"]["description"] = (
    "SMs slow-drought version aligned to code1 rec100 logic: response uses relative z <= -0.3 for 5 "
    "days, requires a sustained 5-day decline within 30 days after drought start; recovery baseline "
    "uses 0.95 x pre-drought 30-day mean on 5-day smoothed absolute GPP; recovery longer than 100 "
    "days is treated as seasonal variation; window = drought_start + 420d."
)
for _key, _value in {
    "response_logic": "legacy_relative",
    "legacy_response_threshold": -0.3,
    "legacy_recovery_threshold": -0.2,
    "legacy_consecutive_days": 5,
    "legacy_ignore_overlap_exclusion": True,
    "legacy_peak_mode": "smoothed_absolute_min",
    "legacy_recovery_mode": "absolute_baseline",
    "response_search_window": 420,
    "window_after_from_drought_start": 420,
    "smooth_window": 5,
    "absolute_baseline_mode": "pre_days_raw",
    "recovery_rate_baseline_mode": "pre_days_raw",
    "absolute_baseline_days": 30,
    "absolute_baseline_scale": 0.95,
    "require_post_drought_decline": True,
    "post_drought_decline_search_days": 30,
    "post_drought_decline_consecutive_days": 5,
    "max_valid_recovery_days": 100,
}.items():
    CONFIGS["gpp_code4_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][_key] = _value
CONFIGS["gpp_code4_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][
    "relative_output_file"
] = _gpp_output(
    "code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"
)
CONFIGS["gpp_code4_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"][
    "with_abs_output_file"
] = _gpp_output(
    "code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"
)
CONFIGS["gpp_code4_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"]["temp_dir"] = (
    _gpp_output("code4_nonflash_SMs/result/temp_chunks_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100")
)

for _code_idx, _title_suffix, _output_path, _temp_dir in [
    (
        2,
        "GPP Response to SMs Flash Drought - v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        _gpp_output("code2_SMs/results/gpp_response_SMs_events_global_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        _gpp_output("code2_SMs/results/temp_chunks_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"),
    ),
    (
        3,
        "GPP Response to SMrz Slow Drought - v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        _gpp_output("code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        _gpp_output("code3_nonflash_SMrz/result/temp_chunks_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"),
    ),
    (
        4,
        "GPP Response to SMs Slow Drought - v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        _gpp_output("code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        _gpp_output("code4_nonflash_SMs/result/temp_chunks_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"),
    ),
]:
    _new_key = f"gpp_code{_code_idx}_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"
    _base_key = f"gpp_code{_code_idx}_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"
    CONFIGS[_new_key] = copy.deepcopy(CONFIGS[_base_key])
    CONFIGS[_new_key]["title"] = _title_suffix
    CONFIGS[_new_key]["description"] = (
        "GPP rel0 control version aligned to rec100: only the relative-response threshold is relaxed "
        "from z <= -0.3 to z <= 0 for 5 days; all other response, peak, recovery, baseline, and "
        "screening rules remain identical to the rec100 configuration."
    )
    CONFIGS[_new_key]["legacy_response_threshold"] = 0.0
    CONFIGS[_new_key]["relative_output_file"] = _output_path
    CONFIGS[_new_key]["with_abs_output_file"] = _output_path
    CONFIGS[_new_key]["temp_dir"] = _temp_dir


for _code_idx, _base_key, _title_suffix, _output_path in [
    (
        1,
        "nee_code1_latfix",
        "NEE Response to SMrz Flash Drought - v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        _nee_output("code1SMrz/result/nee_response_SMrz_drought_v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ),
    (
        2,
        "nee_code2_latfix",
        "NEE Response to SMs Flash Drought - v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        _nee_output("code2SMs/result/nee_response_SMs_drought_v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ),
    (
        3,
        "nee_code3_latfix",
        "NEE Response to SMrz Slow Drought - v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        _nee_output("code3_nonflash_SMrz/result/nee_response_nonflash_SMrz_drought_v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ),
    (
        4,
        "nee_code4_latfix",
        "NEE Response to SMs Slow Drought - v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        _nee_output("code4_nonflash_SMs/result/nee_response_nonflash_SMs_drought_v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ),
]:
    _new_key = f"nee_code{_code_idx}_v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"
    CONFIGS[_new_key] = copy.deepcopy(CONFIGS[_base_key])
    CONFIGS[_new_key]["title"] = _title_suffix
    CONFIGS[_new_key]["description"] = (
        "NEE rec100 logic aligned to the approved carbon-flux rule: response uses relative z >= +0.3 for 5 "
        "days; requires a sustained 5-day increase within 30 days after drought start; peak uses 5-day "
        "smoothed absolute NEE maximum; recovery baseline uses 0.95 x pre-drought 30-day mean on 5-day "
        "smoothed absolute NEE; recovery longer than 100 days is treated as seasonal variation; "
        "window = drought_start + 420d."
    )
    for _cfg_key, _cfg_value in {
        "response_logic": "legacy_relative",
        "legacy_response_threshold": 0.3,
        "legacy_recovery_threshold": 0.2,
        "legacy_consecutive_days": 5,
        "legacy_ignore_overlap_exclusion": True,
        "legacy_peak_mode": "smoothed_absolute_max",
        "legacy_recovery_mode": "absolute_baseline",
        "response_search_window": 420,
        "window_after_from_drought_start": 420,
        "smooth_window": 5,
        "absolute_baseline_mode": "pre_days_raw",
        "recovery_rate_baseline_mode": "pre_days_raw",
        "absolute_baseline_days": 30,
        "absolute_baseline_scale": 0.95,
        "require_post_drought_decline": True,
        "post_drought_decline_search_days": 30,
        "post_drought_decline_consecutive_days": 5,
        "max_valid_recovery_days": 100,
    }.items():
        CONFIGS[_new_key][_cfg_key] = _cfg_value
    CONFIGS[_new_key]["relative_output_file"] = _output_path
    CONFIGS[_new_key]["with_abs_output_file"] = _output_path
    CONFIGS[_new_key]["temp_dir"] = _output_path.replace(".nc", "").replace(
        "/nee_response_", "/temp_chunks_"
    )


for _code_idx, _title_suffix, _output_path in [
    (
        1,
        "NEE Response to SMrz Flash Drought - v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        _nee_output("code1SMrz/result/nee_response_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ),
    (
        2,
        "NEE Response to SMs Flash Drought - v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        _nee_output("code2SMs/result/nee_response_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ),
    (
        3,
        "NEE Response to SMrz Slow Drought - v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        _nee_output("code3_nonflash_SMrz/result/nee_response_nonflash_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ),
    (
        4,
        "NEE Response to SMs Slow Drought - v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        _nee_output("code4_nonflash_SMs/result/nee_response_nonflash_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ),
]:
    _new_key = f"nee_code{_code_idx}_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"
    _base_key = f"nee_code{_code_idx}_v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"
    CONFIGS[_new_key] = copy.deepcopy(CONFIGS[_base_key])
    CONFIGS[_new_key]["title"] = _title_suffix
    CONFIGS[_new_key]["description"] = (
        "NEE rel0 control version aligned to rec100: only the relative-response threshold is relaxed "
        "from z >= +0.3 to z >= 0 for 5 days; all other response, peak, recovery, baseline, and "
        "screening rules remain identical to the rec100 configuration."
    )
    CONFIGS[_new_key]["legacy_response_threshold"] = 0.0
    CONFIGS[_new_key]["relative_output_file"] = _output_path
    CONFIGS[_new_key]["with_abs_output_file"] = _output_path
    CONFIGS[_new_key]["temp_dir"] = _output_path.replace(".nc", "").replace(
        "/nee_response_", "/temp_chunks_"
    )


for _code_idx, _base_key, _title_suffix, _output_path in [
    (
        1,
        "reco_code1_latfix",
        "RECO Response to SMrz Flash Drought - v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        _reco_output("code1/results/reco_response_SMrz_events_global_v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ),
    (
        2,
        "reco_code2_latfix",
        "RECO Response to SMs Flash Drought - v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        _reco_output("code2_SMs/results/reco_response_SMs_drought_v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ),
    (
        3,
        "reco_code3_latfix",
        "RECO Response to SMrz Slow Drought - v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        _reco_output("code3_nonflash_SMrz/result/reco_response_nonflash_SMrz_drought_v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ),
    (
        4,
        "reco_code4_latfix",
        "RECO Response to SMs Slow Drought - v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        _reco_output("code4_nonflash_SMs/result/reco_response_nonflash_SMs_drought_v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ),
]:
    _new_key = f"reco_code{_code_idx}_v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"
    CONFIGS[_new_key] = copy.deepcopy(CONFIGS[_base_key])
    CONFIGS[_new_key]["title"] = _title_suffix
    CONFIGS[_new_key]["description"] = (
        "RECO rec100 logic aligned to the GPP-style rule: response uses relative z <= -0.3 for 5 days, "
        "requires a sustained 5-day decline within 30 days after drought start; peak uses 5-day smoothed "
        "absolute RECO minimum; recovery baseline uses 0.95 x pre-drought 30-day mean on 5-day smoothed "
        "absolute RECO; recovery longer than 100 days is treated as seasonal variation; "
        "window = drought_start + 420d."
    )
    for _cfg_key, _cfg_value in {
        "response_logic": "legacy_relative",
        "legacy_response_threshold": -0.3,
        "legacy_recovery_threshold": -0.2,
        "legacy_consecutive_days": 5,
        "legacy_ignore_overlap_exclusion": True,
        "legacy_peak_mode": "smoothed_absolute_min",
        "legacy_recovery_mode": "absolute_baseline",
        "response_search_window": 420,
        "window_after_from_drought_start": 420,
        "smooth_window": 5,
        "absolute_baseline_mode": "pre_days_raw",
        "recovery_rate_baseline_mode": "pre_days_raw",
        "absolute_baseline_days": 30,
        "absolute_baseline_scale": 0.95,
        "require_post_drought_decline": True,
        "post_drought_decline_search_days": 30,
        "post_drought_decline_consecutive_days": 5,
        "max_valid_recovery_days": 100,
    }.items():
        CONFIGS[_new_key][_cfg_key] = _cfg_value
    CONFIGS[_new_key]["relative_output_file"] = _output_path
    CONFIGS[_new_key]["with_abs_output_file"] = _output_path
    CONFIGS[_new_key]["temp_dir"] = _output_path.replace(".nc", "").replace(
        "/reco_response_", "/temp_chunks_"
    )


for _code_idx, _title_suffix, _output_path in [
    (
        1,
        "RECO Response to SMrz Flash Drought - v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        _reco_output("code1/results/reco_response_SMrz_events_global_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ),
    (
        2,
        "RECO Response to SMs Flash Drought - v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        _reco_output("code2_SMs/results/reco_response_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ),
    (
        3,
        "RECO Response to SMrz Slow Drought - v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        _reco_output("code3_nonflash_SMrz/result/reco_response_nonflash_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ),
    (
        4,
        "RECO Response to SMs Slow Drought - v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        _reco_output("code4_nonflash_SMs/result/reco_response_nonflash_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ),
]:
    _new_key = f"reco_code{_code_idx}_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"
    _base_key = f"reco_code{_code_idx}_v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100"
    CONFIGS[_new_key] = copy.deepcopy(CONFIGS[_base_key])
    CONFIGS[_new_key]["title"] = _title_suffix
    CONFIGS[_new_key]["description"] = (
        "RECO rel0 control version aligned to rec100: only the relative-response threshold is relaxed "
        "from z <= -0.3 to z <= 0 for 5 days; all other response, peak, recovery, baseline, and "
        "screening rules remain identical to the rec100 configuration."
    )
    CONFIGS[_new_key]["legacy_response_threshold"] = 0.0
    CONFIGS[_new_key]["relative_output_file"] = _output_path
    CONFIGS[_new_key]["with_abs_output_file"] = _output_path
    CONFIGS[_new_key]["temp_dir"] = _output_path.replace(".nc", "").replace(
        "/reco_response_", "/temp_chunks_"
    )


for _new_key, _base_key, _title, _description, _output_path, _temp_dir in [
    (
        "gpp_code2_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        "gpp_code2_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "GPP Response to SMs Growing-Season Flash Drought - "
        "v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        "Growing-season GPP response version for GLEAM surface-soil flash drought derived from the "
        "v20260328 rel0 control: events are retained only when more than half of drought duration "
        "falls within the annual growing season, recovery can cross seasons, but recovery durations "
        "are counted using growing-season-effective days only.",
        _gpp_output(
            "code2_SMs/results/gpp_response_SMs_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
        ),
        _gpp_output(
            "code2_SMs/results/temp_chunks_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
        ),
    ),
    (
        "nee_code1_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        "nee_code1_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "NEE Response to SMrz Growing-Season Flash Drought - "
        "v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        "Growing-season NEE response version for GLEAM root-zone flash drought derived from the "
        "v20260328 rel0 control: events are retained only when more than half of drought duration "
        "falls within the annual growing season, recovery can cross seasons, but recovery durations "
        "are counted using growing-season-effective days only.",
        _nee_output(
            "code1SMrz/result/nee_response_SMrz_drought_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
        ),
        _nee_output(
            "code1SMrz/result/temp_chunks_SMrz_drought_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
        ),
    ),
    (
        "nee_code2_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        "nee_code2_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "NEE Response to SMs Growing-Season Flash Drought - "
        "v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        "Growing-season NEE response version for GLEAM surface-soil flash drought derived from the "
        "v20260328 rel0 control: events are retained only when more than half of drought duration "
        "falls within the annual growing season, recovery can cross seasons, but recovery durations "
        "are counted using growing-season-effective days only.",
        _nee_output(
            "code2SMs/result/nee_response_SMs_drought_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
        ),
        _nee_output(
            "code2SMs/result/temp_chunks_SMs_drought_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
        ),
    ),
    (
        "reco_code1_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        "reco_code1_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "RECO Response to SMrz Growing-Season Flash Drought - "
        "v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        "Growing-season RECO response version for GLEAM root-zone flash drought derived from the "
        "v20260328 rel0 control: events are retained only when more than half of drought duration "
        "falls within the annual growing season, recovery can cross seasons, but recovery durations "
        "are counted using growing-season-effective days only.",
        _reco_output(
            "code1/results/reco_response_SMrz_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
        ),
        _reco_output(
            "code1/results/temp_chunks_SMrz_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
        ),
    ),
    (
        "reco_code2_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        "reco_code2_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "RECO Response to SMs Growing-Season Flash Drought - "
        "v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        "Growing-season RECO response version for GLEAM surface-soil flash drought derived from the "
        "v20260328 rel0 control: events are retained only when more than half of drought duration "
        "falls within the annual growing season, recovery can cross seasons, but recovery durations "
        "are counted using growing-season-effective days only.",
        _reco_output(
            "code2_SMs/results/reco_response_SMs_drought_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
        ),
        _reco_output(
            "code2_SMs/results/temp_chunks_SMs_drought_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
        ),
    ),
]:
    CONFIGS[_new_key] = copy.deepcopy(CONFIGS[_base_key])
    CONFIGS[_new_key]["title"] = _title
    CONFIGS[_new_key]["description"] = _description
    CONFIGS[_new_key]["growing_season_enabled"] = True
    CONFIGS[_new_key]["growing_season_temp_file"] = "/data/era5_for_GRN/yearly/temperature_2m_0p25deg_1980_2024.nc"
    CONFIGS[_new_key]["growing_season_temp_var"] = "temperature_2m"
    CONFIGS[_new_key]["growing_season_temp_threshold_k"] = 278.15
    CONFIGS[_new_key]["growing_season_min_consecutive_days"] = 5
    CONFIGS[_new_key]["growing_season_min_fraction"] = 0.5
    CONFIGS[_new_key]["max_valid_recovery_days"] = None
    CONFIGS[_new_key]["recovery_day_count_mode"] = "growing_season_only"
    CONFIGS[_new_key]["relative_output_file"] = _output_path
    CONFIGS[_new_key]["with_abs_output_file"] = _output_path
    CONFIGS[_new_key]["temp_dir"] = _temp_dir


for _new_key, _base_key, _event_file, _title, _description, _output_path, _temp_dir in [
    (
        "fluxsat_code1_v20260328_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100_2001_2019",
        "gpp_code1_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        FLASH_SMRZ_FILE,
        "FluxSat GPP Response to SMrz Flash Drought - "
        "v20260328_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100_2001_2019",
        "FluxSat GPP flash-drought version aligned to the GPP 0328 rec100 method: "
        "GLEAM SMrz flash events are analyzed over the 2001-2019 overlap period using the "
        "same rel0 response rule and rec100 absolute-baseline recovery definition as v20260328.",
        _fluxsat_output(
            "code1/results/fluxsat_gpp_response_SMrz_events_global_v20260328_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100_2001_2019.nc"
        ),
        _fluxsat_output(
            "code1/results/temp_chunks_fluxsat_gpp_SMrz_events_global_v20260328_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100_2001_2019"
        ),
    ),
    (
        "fluxsat_code2_v20260328_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100_2001_2019",
        "gpp_code2_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        FLASH_SMS_FILE,
        "FluxSat GPP Response to SMs Flash Drought - "
        "v20260328_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100_2001_2019",
        "FluxSat GPP flash-drought version aligned to the GPP 0328 rec100 method: "
        "GLEAM SMs flash events are analyzed over the 2001-2019 overlap period using the "
        "same rel0 response rule and rec100 absolute-baseline recovery definition as v20260328.",
        _fluxsat_output(
            "code2_SMs/results/fluxsat_gpp_response_SMs_events_global_v20260328_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100_2001_2019.nc"
        ),
        _fluxsat_output(
            "code2_SMs/results/temp_chunks_fluxsat_gpp_SMs_events_global_v20260328_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100_2001_2019"
        ),
    ),
    (
        "fluxsat_code1_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        "gpp_code1_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        FLASH_SMRZ_FILE,
        "FluxSat GPP Response to SMrz Growing-Season Flash Drought - "
        "v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        "FluxSat GPP growing-season flash-drought version aligned to the GPP 0401 method: "
        "GLEAM SMrz flash events are filtered by growing-season overlap and recovery durations "
        "are counted using growing-season-effective days only over the 2000-2019 overlap period.",
        _fluxsat_output(
            "code1/results/fluxsat_gpp_response_SMrz_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
        ),
        _fluxsat_output(
            "code1/results/temp_chunks_fluxsat_gpp_SMrz_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
        ),
    ),
    (
        "fluxsat_code2_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        "gpp_code2_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        FLASH_SMS_FILE,
        "FluxSat GPP Response to SMs Growing-Season Flash Drought - "
        "v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        "FluxSat GPP growing-season flash-drought version aligned to the GPP 0401 method: "
        "GLEAM SMs flash events are filtered by growing-season overlap and recovery durations "
        "are counted using growing-season-effective days only over the 2000-2019 overlap period.",
        _fluxsat_output(
            "code2_SMs/results/fluxsat_gpp_response_SMs_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
        ),
        _fluxsat_output(
            "code2_SMs/results/temp_chunks_fluxsat_gpp_SMs_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax"
        ),
    ),
]:
    CONFIGS[_new_key] = copy.deepcopy(CONFIGS[_base_key])
    CONFIGS[_new_key]["data_file"] = FLUXSAT_GPP_FILE
    if "v20260328" in _new_key:
        CONFIGS[_new_key]["start_year"] = 2001
    else:
        CONFIGS[_new_key]["start_year"] = 2000
    CONFIGS[_new_key]["end_year"] = 2019
    CONFIGS[_new_key]["event_file"] = _event_file
    CONFIGS[_new_key]["title"] = _title
    CONFIGS[_new_key]["description"] = _description
    CONFIGS[_new_key]["relative_output_file"] = _output_path
    CONFIGS[_new_key]["with_abs_output_file"] = _output_path
    CONFIGS[_new_key]["temp_dir"] = _temp_dir
    CONFIGS[_new_key]["output_dir"] = os.path.dirname(_output_path)
    CONFIGS[_new_key]["data_scale"] = 100.0


for _new_key, _base_key, _event_file, _title, _description, _output_path, _temp_dir, _max_valid_days, _gs_fraction in [
    (
        "fluxsat_code1_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap",
        "fluxsat_code1_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        FLASH_SMRZ_FILE,
        "FluxSat GPP Response to SMrz Growing-Season Flash Drought - v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap",
        "FluxSat 0401 sensitivity run: keep growing-season event filter and growing-season-only recovery counting, but restore the 100-day valid-recovery cap.",
        _fluxsat_output(
            "code1/results/fluxsat_gpp_response_SMrz_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap.nc"
        ),
        _fluxsat_output(
            "code1/results/temp_chunks_fluxsat_gpp_SMrz_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap"
        ),
        100,
        0.5,
    ),
    (
        "fluxsat_code2_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap",
        "fluxsat_code2_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        FLASH_SMS_FILE,
        "FluxSat GPP Response to SMs Growing-Season Flash Drought - v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap",
        "FluxSat 0401 sensitivity run: keep growing-season event filter and growing-season-only recovery counting, but restore the 100-day valid-recovery cap.",
        _fluxsat_output(
            "code2_SMs/results/fluxsat_gpp_response_SMs_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap.nc"
        ),
        _fluxsat_output(
            "code2_SMs/results/temp_chunks_fluxsat_gpp_SMs_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap"
        ),
        100,
        0.5,
    ),
    (
        "fluxsat_code1_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec120cap",
        "fluxsat_code1_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        FLASH_SMRZ_FILE,
        "FluxSat GPP Response to SMrz Growing-Season Flash Drought - v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec120cap",
        "FluxSat 0401 sensitivity run: keep growing-season event filter and growing-season-only recovery counting, but apply a 120-day valid-recovery cap.",
        _fluxsat_output(
            "code1/results/fluxsat_gpp_response_SMrz_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec120cap.nc"
        ),
        _fluxsat_output(
            "code1/results/temp_chunks_fluxsat_gpp_SMrz_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec120cap"
        ),
        120,
        0.5,
    ),
    (
        "fluxsat_code2_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec120cap",
        "fluxsat_code2_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        FLASH_SMS_FILE,
        "FluxSat GPP Response to SMs Growing-Season Flash Drought - v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec120cap",
        "FluxSat 0401 sensitivity run: keep growing-season event filter and growing-season-only recovery counting, but apply a 120-day valid-recovery cap.",
        _fluxsat_output(
            "code2_SMs/results/fluxsat_gpp_response_SMs_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec120cap.nc"
        ),
        _fluxsat_output(
            "code2_SMs/results/temp_chunks_fluxsat_gpp_SMs_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec120cap"
        ),
        120,
        0.5,
    ),
    (
        "fluxsat_code1_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_gsfrac07",
        "fluxsat_code1_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        FLASH_SMRZ_FILE,
        "FluxSat GPP Response to SMrz Growing-Season Flash Drought - v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_gsfrac07",
        "FluxSat 0401 sensitivity run: restore the 100-day valid-recovery cap and tighten the growing-season overlap fraction to 0.7.",
        _fluxsat_output(
            "code1/results/fluxsat_gpp_response_SMrz_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_gsfrac07.nc"
        ),
        _fluxsat_output(
            "code1/results/temp_chunks_fluxsat_gpp_SMrz_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_gsfrac07"
        ),
        100,
        0.7,
    ),
    (
        "fluxsat_code2_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_gsfrac07",
        "fluxsat_code2_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax",
        FLASH_SMS_FILE,
        "FluxSat GPP Response to SMs Growing-Season Flash Drought - v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_gsfrac07",
        "FluxSat 0401 sensitivity run: restore the 100-day valid-recovery cap and tighten the growing-season overlap fraction to 0.7.",
        _fluxsat_output(
            "code2_SMs/results/fluxsat_gpp_response_SMs_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_gsfrac07.nc"
        ),
        _fluxsat_output(
            "code2_SMs/results/temp_chunks_fluxsat_gpp_SMs_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_gsfrac07"
        ),
        100,
        0.7,
    ),
]:
    CONFIGS[_new_key] = copy.deepcopy(CONFIGS[_base_key])
    CONFIGS[_new_key]["event_file"] = _event_file
    CONFIGS[_new_key]["title"] = _title
    CONFIGS[_new_key]["description"] = _description
    CONFIGS[_new_key]["relative_output_file"] = _output_path
    CONFIGS[_new_key]["with_abs_output_file"] = _output_path
    CONFIGS[_new_key]["temp_dir"] = _temp_dir
    CONFIGS[_new_key]["output_dir"] = os.path.dirname(_output_path)
    CONFIGS[_new_key]["max_valid_recovery_days"] = _max_valid_days
    CONFIGS[_new_key]["growing_season_min_fraction"] = _gs_fraction
    CONFIGS[_new_key]["n_workers"] = 6


for _new_key, _base_key, _event_file, _title, _description, _output_path, _temp_dir, _max_valid_days, _gs_fraction in [
    (
        "fluxsat_code1_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_fixlon_v20260426",
        "fluxsat_code1_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap",
        FLASH_SMRZ_FILE,
        "FluxSat GPP Response to SMrz Growing-Season Flash Drought - v20260401_rec100cap_fixlon_v20260426",
        "FluxSat 0401 rec100cap rerun using the 2026-04-26 fixed-longitude preprocessing output.",
        _fluxsat_output(
            "code1/results/fluxsat_gpp_response_SMrz_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_fixlon_v20260426.nc"
        ),
        _fluxsat_output(
            "code1/results/temp_chunks_fluxsat_gpp_SMrz_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_fixlon_v20260426"
        ),
        100,
        0.5,
    ),
    (
        "fluxsat_code2_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_fixlon_v20260426",
        "fluxsat_code2_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap",
        FLASH_SMS_FILE,
        "FluxSat GPP Response to SMs Growing-Season Flash Drought - v20260401_rec100cap_fixlon_v20260426",
        "FluxSat 0401 rec100cap rerun using the 2026-04-26 fixed-longitude preprocessing output.",
        _fluxsat_output(
            "code2_SMs/results/fluxsat_gpp_response_SMs_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_fixlon_v20260426.nc"
        ),
        _fluxsat_output(
            "code2_SMs/results/temp_chunks_fluxsat_gpp_SMs_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_fixlon_v20260426"
        ),
        100,
        0.5,
    ),
]:
    CONFIGS[_new_key] = copy.deepcopy(CONFIGS[_base_key])
    CONFIGS[_new_key]["data_file"] = FLUXSAT_GPP_FILE_FIXLON
    CONFIGS[_new_key]["event_file"] = _event_file
    CONFIGS[_new_key]["title"] = _title
    CONFIGS[_new_key]["description"] = _description
    CONFIGS[_new_key]["relative_output_file"] = _output_path
    CONFIGS[_new_key]["with_abs_output_file"] = _output_path
    CONFIGS[_new_key]["temp_dir"] = _temp_dir
    CONFIGS[_new_key]["output_dir"] = os.path.dirname(_output_path)
    CONFIGS[_new_key]["max_valid_recovery_days"] = _max_valid_days
    CONFIGS[_new_key]["growing_season_min_fraction"] = _gs_fraction
    CONFIGS[_new_key]["n_workers"] = 4


for _new_key, _base_key, _event_file, _title_suffix, _description, _output_path, _temp_dir in [
    (
        "gpp_code2_era5_swvl1_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "gpp_code2_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        ERA5L_SWVL1_FLASH_FILE,
        "GPP Response to ERA5L Surface Flash Drought - v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "ERA5L surface-soil flash-drought version cloned from the GLEAM SMs rel0 control with identical response, peak, recovery, baseline, and screening rules.",
        _gpp_output("code2_ERA5_swvl1/results/gpp_response_ERA5L_swvl1_events_global_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        _gpp_output("code2_ERA5_swvl1/results/temp_chunks_v20260330_era5_swvl1_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"),
    ),
    (
        "gpp_code3_era5_root_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "gpp_code3_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        ERA5L_ROOT_NONFLASH_FILE,
        "GPP Response to ERA5L Root Slow Drought - v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "ERA5L root-zone slow-drought version cloned from the GLEAM SMrz slow rel0 control with identical response, peak, recovery, baseline, and screening rules.",
        _gpp_output("code3_ERA5_root_nonflash/result/gpp_response_nonflash_ERA5L_root_drought_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        _gpp_output("code3_ERA5_root_nonflash/result/temp_chunks_v20260330_era5_root_nonflash_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"),
    ),
    (
        "gpp_code4_era5_swvl1_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "gpp_code4_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        ERA5L_SWVL1_NONFLASH_FILE,
        "GPP Response to ERA5L Surface Slow Drought - v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "ERA5L surface-soil slow-drought version cloned from the GLEAM SMs slow rel0 control with identical response, peak, recovery, baseline, and screening rules.",
        _gpp_output("code4_ERA5_swvl1_nonflash/result/gpp_response_nonflash_ERA5L_swvl1_drought_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        _gpp_output("code4_ERA5_swvl1_nonflash/result/temp_chunks_v20260330_era5_swvl1_nonflash_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"),
    ),
    (
        "nee_code1_era5_root_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "nee_code1_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        ERA5L_ROOT_FLASH_FILE,
        "NEE Response to ERA5L Root Flash Drought - v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "ERA5L root-zone flash-drought version cloned from the GLEAM SMrz rel0 control with identical response, peak, recovery, baseline, and screening rules.",
        _nee_output("code1_ERA5_root/result/nee_response_ERA5L_root_drought_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        _nee_output("code1_ERA5_root/result/temp_chunks_v20260330_era5_root_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"),
    ),
    (
        "nee_code2_era5_swvl1_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "nee_code2_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        ERA5L_SWVL1_FLASH_FILE,
        "NEE Response to ERA5L Surface Flash Drought - v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "ERA5L surface-soil flash-drought version cloned from the GLEAM SMs rel0 control with identical response, peak, recovery, baseline, and screening rules.",
        _nee_output("code2_ERA5_swvl1/result/nee_response_ERA5L_swvl1_drought_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        _nee_output("code2_ERA5_swvl1/result/temp_chunks_v20260330_era5_swvl1_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"),
    ),
    (
        "nee_code3_era5_root_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "nee_code3_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        ERA5L_ROOT_NONFLASH_FILE,
        "NEE Response to ERA5L Root Slow Drought - v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "ERA5L root-zone slow-drought version cloned from the GLEAM SMrz slow rel0 control with identical response, peak, recovery, baseline, and screening rules.",
        _nee_output("code3_ERA5_root_nonflash/result/nee_response_nonflash_ERA5L_root_drought_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        _nee_output("code3_ERA5_root_nonflash/result/temp_chunks_v20260330_era5_root_nonflash_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"),
    ),
    (
        "nee_code4_era5_swvl1_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "nee_code4_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        ERA5L_SWVL1_NONFLASH_FILE,
        "NEE Response to ERA5L Surface Slow Drought - v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "ERA5L surface-soil slow-drought version cloned from the GLEAM SMs slow rel0 control with identical response, peak, recovery, baseline, and screening rules.",
        _nee_output("code4_ERA5_swvl1_nonflash/result/nee_response_nonflash_ERA5L_swvl1_drought_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        _nee_output("code4_ERA5_swvl1_nonflash/result/temp_chunks_v20260330_era5_swvl1_nonflash_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"),
    ),
    (
        "reco_code1_era5_root_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "reco_code1_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        ERA5L_ROOT_FLASH_FILE,
        "RECO Response to ERA5L Root Flash Drought - v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "ERA5L root-zone flash-drought version cloned from the GLEAM SMrz rel0 control with identical response, peak, recovery, baseline, and screening rules.",
        _reco_output("code1_ERA5_root/results/reco_response_ERA5L_root_events_global_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        _reco_output("code1_ERA5_root/results/temp_chunks_v20260330_era5_root_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"),
    ),
    (
        "reco_code2_era5_swvl1_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "reco_code2_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        ERA5L_SWVL1_FLASH_FILE,
        "RECO Response to ERA5L Surface Flash Drought - v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "ERA5L surface-soil flash-drought version cloned from the GLEAM SMs rel0 control with identical response, peak, recovery, baseline, and screening rules.",
        _reco_output("code2_ERA5_swvl1/results/reco_response_ERA5L_swvl1_drought_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        _reco_output("code2_ERA5_swvl1/results/temp_chunks_v20260330_era5_swvl1_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"),
    ),
    (
        "reco_code3_era5_root_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "reco_code3_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        ERA5L_ROOT_NONFLASH_FILE,
        "RECO Response to ERA5L Root Slow Drought - v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "ERA5L root-zone slow-drought version cloned from the GLEAM SMrz slow rel0 control with identical response, peak, recovery, baseline, and screening rules.",
        _reco_output("code3_ERA5_root_nonflash/result/reco_response_nonflash_ERA5L_root_drought_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        _reco_output("code3_ERA5_root_nonflash/result/temp_chunks_v20260330_era5_root_nonflash_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"),
    ),
    (
        "reco_code4_era5_swvl1_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "reco_code4_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        ERA5L_SWVL1_NONFLASH_FILE,
        "RECO Response to ERA5L Surface Slow Drought - v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100",
        "ERA5L surface-soil slow-drought version cloned from the GLEAM SMs slow rel0 control with identical response, peak, recovery, baseline, and screening rules.",
        _reco_output("code4_ERA5_swvl1_nonflash/result/reco_response_nonflash_ERA5L_swvl1_drought_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        _reco_output("code4_ERA5_swvl1_nonflash/result/temp_chunks_v20260330_era5_swvl1_nonflash_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100"),
    ),
]:
    CONFIGS[_new_key] = copy.deepcopy(CONFIGS[_base_key])
    CONFIGS[_new_key]["event_file"] = _event_file
    CONFIGS[_new_key]["title"] = _title_suffix
    CONFIGS[_new_key]["description"] = _description
    CONFIGS[_new_key]["relative_output_file"] = _output_path
    CONFIGS[_new_key]["with_abs_output_file"] = _output_path
    CONFIGS[_new_key]["temp_dir"] = _temp_dir


def get_config(key):
    if key not in CONFIGS:
        raise KeyError(f"Unknown v20260322_lu_025deg config key: {key}")
    return copy.deepcopy(CONFIGS[key])
