#!/usr/bin/env python3
"""Configuration registry for GPP v20260320 response scripts."""

import copy
import os


BASE_DIR = "/home/xulc/flash_drought"
GPP_FILE = os.path.join(BASE_DIR, "process/GPP-draught-analysis/SMrz_result/BESS_GPP_1982_2022.nc")

FLASH_SMRZ_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMrz_5.3/flash_drought_events_v5.nc")
FLASH_SMS_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMs_5.3/flash_drought_events_v5.nc")
NONFLASH_SMRZ_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMrz_5.3/nonflash_drought_events_v5.nc")
NONFLASH_SMS_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMs_5.3/nonflash_drought_events_v5.nc")


def _common(output_dir):
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
        "metric_name": "gpp",
        "data_var": "GPP",
        "data_file": GPP_FILE,
        "direction": "negative",
        "output_dir": output_dir,
    }


CONFIGS = {
    "gpp_code1": {
        **_common(os.path.join(BASE_DIR, "process/GPP-draught-analysis/code1/results")),
        "event_mode": "flash",
        "event_file": FLASH_SMRZ_FILE,
        "n_workers": 16,
        "lat_chunk_size": 20,
        "title": "GPP Response to SMrz Flash Drought - v20260320",
        "description": "Compact GPP response metrics using first negative anomaly and baseline recovery.",
        "relative_output_file": os.path.join(
            BASE_DIR, "process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260320.nc"
        ),
        "with_abs_output_file": os.path.join(
            BASE_DIR, "process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260320.nc"
        ),
        "temp_dir": os.path.join(BASE_DIR, "process/GPP-draught-analysis/code1/results/temp_chunks_v20260320"),
    },
    "gpp_code2": {
        **_common(os.path.join(BASE_DIR, "process/GPP-draught-analysis/code2_SMs/results")),
        "event_mode": "flash",
        "event_file": FLASH_SMS_FILE,
        "n_workers": 16,
        "lat_chunk_size": 20,
        "title": "GPP Response to SMs Flash Drought - v20260320",
        "description": "Compact GPP response metrics using first negative anomaly and baseline recovery.",
        "relative_output_file": os.path.join(
            BASE_DIR, "process/GPP-draught-analysis/code2_SMs/results/gpp_response_SMs_events_global_v20260320.nc"
        ),
        "with_abs_output_file": os.path.join(
            BASE_DIR, "process/GPP-draught-analysis/code2_SMs/results/gpp_response_SMs_events_global_v20260320.nc"
        ),
        "temp_dir": os.path.join(BASE_DIR, "process/GPP-draught-analysis/code2_SMs/results/temp_chunks_v20260320"),
    },
    "gpp_code3": {
        **_common(os.path.join(BASE_DIR, "process/GPP-draught-analysis/code3_nonflash_SMrz/result")),
        "event_mode": "nonflash",
        "event_file": NONFLASH_SMRZ_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "GPP Response to SMrz Nonflash Drought - v20260320",
        "description": "Compact nonflash GPP response metrics using first negative anomaly and baseline recovery.",
        "relative_output_file": os.path.join(
            BASE_DIR,
            "process/GPP-draught-analysis/code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v20260320.nc",
        ),
        "with_abs_output_file": os.path.join(
            BASE_DIR,
            "process/GPP-draught-analysis/code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v20260320.nc",
        ),
        "temp_dir": os.path.join(
            BASE_DIR, "process/GPP-draught-analysis/code3_nonflash_SMrz/result/temp_chunks_v20260320"
        ),
    },
    "gpp_code4": {
        **_common(os.path.join(BASE_DIR, "process/GPP-draught-analysis/code4_nonflash_SMs/result")),
        "event_mode": "nonflash",
        "event_file": NONFLASH_SMS_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "GPP Response to SMs Nonflash Drought - v20260320",
        "description": "Compact nonflash GPP response metrics using first negative anomaly and baseline recovery.",
        "relative_output_file": os.path.join(
            BASE_DIR,
            "process/GPP-draught-analysis/code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v20260320.nc",
        ),
        "with_abs_output_file": os.path.join(
            BASE_DIR,
            "process/GPP-draught-analysis/code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v20260320.nc",
        ),
        "temp_dir": os.path.join(
            BASE_DIR, "process/GPP-draught-analysis/code4_nonflash_SMs/result/temp_chunks_v20260320"
        ),
    },
}


def get_config(key):
    if key not in CONFIGS:
        raise KeyError(f"Unknown v20260320 config key: {key}")
    return copy.deepcopy(CONFIGS[key])
