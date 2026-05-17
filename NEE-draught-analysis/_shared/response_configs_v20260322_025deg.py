#!/usr/bin/env python3
"""Configuration registry for 0.25 degree v20260322 compact drought-response scripts."""

import copy
import os


BASE_DIR = "/home/xulc/flash_drought"

GPP_FILE = "/data/BESS_V2/BESS_GPP_1982_2022_0.25deg.nc"
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


def _common(metric_name, data_var, data_file, direction, output_dir):
    return {
        "start_year": 1982,
        "end_year": 2022,
        "window_before": 60,
        "window_after": 180,
        "recovery_window": 120,
        "max_window_after": 600,
        "response_search_window": 60,
        "recovery_consecutive_days": 3,
        "baseline_recovery_consecutive_days": 3,
        "baseline_tolerance_multiplier": 0.5,
        "baseline_tolerance_floor_fraction": 0.02,
        "smooth_window": 7,
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


CONFIGS = {
    "gpp_code1": {
        **_common("gpp", "GPP", GPP_FILE, "negative", _gpp_output("code1/results")),
        "event_mode": "flash",
        "event_file": FLASH_SMRZ_FILE,
        "n_workers": 16,
        "lat_chunk_size": 20,
        "title": "GPP Response to SMrz Flash Drought - v20260322_025deg",
        "description": "Compact GPP response metrics for v5.4 SMrz flash drought events at 0.25 degree.",
        "relative_output_file": _gpp_output("code1/results/gpp_response_SMrz_events_global_v20260322_025deg.nc"),
        "with_abs_output_file": _gpp_output("code1/results/gpp_response_SMrz_events_global_v20260322_025deg.nc"),
        "temp_dir": _gpp_output("code1/results/temp_chunks_v20260322_025deg"),
    },
    "gpp_code2": {
        **_common("gpp", "GPP", GPP_FILE, "negative", _gpp_output("code2_SMs/results")),
        "event_mode": "flash",
        "event_file": FLASH_SMS_FILE,
        "n_workers": 16,
        "lat_chunk_size": 20,
        "title": "GPP Response to SMs Flash Drought - v20260322_025deg",
        "description": "Compact GPP response metrics for v5.4 SMs flash drought events at 0.25 degree.",
        "relative_output_file": _gpp_output("code2_SMs/results/gpp_response_SMs_events_global_v20260322_025deg.nc"),
        "with_abs_output_file": _gpp_output("code2_SMs/results/gpp_response_SMs_events_global_v20260322_025deg.nc"),
        "temp_dir": _gpp_output("code2_SMs/results/temp_chunks_v20260322_025deg"),
    },
    "gpp_code3": {
        **_common("gpp", "GPP", GPP_FILE, "negative", _gpp_output("code3_nonflash_SMrz/result")),
        "event_mode": "nonflash",
        "event_file": NONFLASH_SMRZ_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "GPP Response to SMrz Slow Drought - v20260322_025deg",
        "description": "Compact GPP response metrics for v5.4 SMrz slow drought events at 0.25 degree.",
        "relative_output_file": _gpp_output(
            "code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v20260322_025deg.nc"
        ),
        "with_abs_output_file": _gpp_output(
            "code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v20260322_025deg.nc"
        ),
        "temp_dir": _gpp_output("code3_nonflash_SMrz/result/temp_chunks_v20260322_025deg"),
    },
    "gpp_code4": {
        **_common("gpp", "GPP", GPP_FILE, "negative", _gpp_output("code4_nonflash_SMs/result")),
        "event_mode": "nonflash",
        "event_file": NONFLASH_SMS_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "GPP Response to SMs Slow Drought - v20260322_025deg",
        "description": "Compact GPP response metrics for v5.4 SMs slow drought events at 0.25 degree.",
        "relative_output_file": _gpp_output(
            "code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v20260322_025deg.nc"
        ),
        "with_abs_output_file": _gpp_output(
            "code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v20260322_025deg.nc"
        ),
        "temp_dir": _gpp_output("code4_nonflash_SMs/result/temp_chunks_v20260322_025deg"),
    },
    "nee_code1": {
        **_common("nee", "NEE", NEE_FILE, "positive", _nee_output("code1SMrz/result")),
        "event_mode": "flash",
        "event_file": FLASH_SMRZ_FILE,
        "n_workers": 16,
        "lat_chunk_size": 20,
        "title": "NEE Response to SMrz Flash Drought - v20260322_025deg",
        "description": "Compact NEE response metrics for v5.4 SMrz flash drought events at 0.25 degree.",
        "relative_output_file": _nee_output("code1SMrz/result/nee_response_SMrz_drought_v20260322_025deg.nc"),
        "with_abs_output_file": _nee_output(
            "code1SMrz/result/nee_response_SMrz_drought_v20260322_025deg.nc"
        ),
        "temp_dir": _nee_output("code1SMrz/result/temp_chunks_v20260322_025deg"),
    },
    "nee_code2": {
        **_common("nee", "NEE", NEE_FILE, "positive", _nee_output("code2SMs/result")),
        "event_mode": "flash",
        "event_file": FLASH_SMS_FILE,
        "n_workers": 16,
        "lat_chunk_size": 20,
        "title": "NEE Response to SMs Flash Drought - v20260322_025deg",
        "description": "Compact NEE response metrics for v5.4 SMs flash drought events at 0.25 degree.",
        "relative_output_file": _nee_output("code2SMs/result/nee_response_SMs_drought_v20260322_025deg.nc"),
        "with_abs_output_file": _nee_output("code2SMs/result/nee_response_SMs_drought_v20260322_025deg.nc"),
        "temp_dir": _nee_output("code2SMs/result/temp_chunks_v20260322_025deg"),
    },
    "nee_code3": {
        **_common("nee", "NEE", NEE_FILE, "positive", _nee_output("code3_nonflash_SMrz/result")),
        "event_mode": "nonflash",
        "event_file": NONFLASH_SMRZ_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "NEE Response to SMrz Slow Drought - v20260322_025deg",
        "description": "Compact NEE response metrics for v5.4 SMrz slow drought events at 0.25 degree.",
        "relative_output_file": _nee_output(
            "code3_nonflash_SMrz/result/nee_response_nonflash_SMrz_drought_v20260322_025deg.nc"
        ),
        "with_abs_output_file": _nee_output(
            "code3_nonflash_SMrz/result/nee_response_nonflash_SMrz_drought_v20260322_025deg.nc"
        ),
        "temp_dir": _nee_output("code3_nonflash_SMrz/result/temp_chunks_v20260322_025deg"),
    },
    "nee_code4": {
        **_common("nee", "NEE", NEE_FILE, "positive", _nee_output("code4_nonflash_SMs/result")),
        "event_mode": "nonflash",
        "event_file": NONFLASH_SMS_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "NEE Response to SMs Slow Drought - v20260322_025deg",
        "description": "Compact NEE response metrics for v5.4 SMs slow drought events at 0.25 degree.",
        "relative_output_file": _nee_output(
            "code4_nonflash_SMs/result/nee_response_nonflash_SMs_drought_v20260322_025deg.nc"
        ),
        "with_abs_output_file": _nee_output(
            "code4_nonflash_SMs/result/nee_response_nonflash_SMs_drought_v20260322_025deg.nc"
        ),
        "temp_dir": _nee_output("code4_nonflash_SMs/result/temp_chunks_v20260322_025deg"),
    },
    "reco_code1": {
        **_common("reco", "RECO", RECO_FILE, "negative", _reco_output("code1/results")),
        "event_mode": "flash",
        "event_file": FLASH_SMRZ_FILE,
        "n_workers": 16,
        "lat_chunk_size": 20,
        "title": "RECO Response to SMrz Flash Drought - v20260322_025deg",
        "description": "Compact RECO response metrics for v5.4 SMrz flash drought events at 0.25 degree.",
        "relative_output_file": _reco_output("code1/results/reco_response_SMrz_events_global_v20260322_025deg.nc"),
        "with_abs_output_file": _reco_output(
            "code1/results/reco_response_SMrz_events_global_v20260322_025deg.nc"
        ),
        "temp_dir": _reco_output("code1/results/temp_chunks_v20260322_025deg"),
    },
    "reco_code2": {
        **_common("reco", "RECO", RECO_FILE, "negative", _reco_output("code2_SMs/results")),
        "event_mode": "flash",
        "event_file": FLASH_SMS_FILE,
        "n_workers": 16,
        "lat_chunk_size": 20,
        "title": "RECO Response to SMs Flash Drought - v20260322_025deg",
        "description": "Compact RECO response metrics for v5.4 SMs flash drought events at 0.25 degree.",
        "relative_output_file": _reco_output("code2_SMs/results/reco_response_SMs_drought_v20260322_025deg.nc"),
        "with_abs_output_file": _reco_output(
            "code2_SMs/results/reco_response_SMs_drought_v20260322_025deg.nc"
        ),
        "temp_dir": _reco_output("code2_SMs/results/temp_chunks_v20260322_025deg"),
    },
    "reco_code3": {
        **_common("reco", "RECO", RECO_FILE, "negative", _reco_output("code3_nonflash_SMrz/result")),
        "event_mode": "nonflash",
        "event_file": NONFLASH_SMRZ_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "RECO Response to SMrz Slow Drought - v20260322_025deg",
        "description": "Compact RECO response metrics for v5.4 SMrz slow drought events at 0.25 degree.",
        "relative_output_file": _reco_output(
            "code3_nonflash_SMrz/result/reco_response_nonflash_SMrz_drought_v20260322_025deg.nc"
        ),
        "with_abs_output_file": _reco_output(
            "code3_nonflash_SMrz/result/reco_response_nonflash_SMrz_drought_v20260322_025deg.nc"
        ),
        "temp_dir": _reco_output("code3_nonflash_SMrz/result/temp_chunks_v20260322_025deg"),
    },
    "reco_code4": {
        **_common("reco", "RECO", RECO_FILE, "negative", _reco_output("code4_nonflash_SMs/result")),
        "event_mode": "nonflash",
        "event_file": NONFLASH_SMS_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "RECO Response to SMs Slow Drought - v20260322_025deg",
        "description": "Compact RECO response metrics for v5.4 SMs slow drought events at 0.25 degree.",
        "relative_output_file": _reco_output(
            "code4_nonflash_SMs/result/reco_response_nonflash_SMs_drought_v20260322_025deg.nc"
        ),
        "with_abs_output_file": _reco_output(
            "code4_nonflash_SMs/result/reco_response_nonflash_SMs_drought_v20260322_025deg.nc"
        ),
        "temp_dir": _reco_output("code4_nonflash_SMs/result/temp_chunks_v20260322_025deg"),
    },
}


def get_config(key):
    if key not in CONFIGS:
        raise KeyError(f"Unknown v20260322_025deg config key: {key}")
    return copy.deepcopy(CONFIGS[key])
