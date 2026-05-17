#!/usr/bin/env python3
"""Configuration registry for v20260316 standardized drought-response scripts."""

import copy
import os


BASE_DIR = "/home/xulc/flash_drought"

GPP_FILE = os.path.join(BASE_DIR, "process/GPP-draught-analysis/SMrz_result/BESS_GPP_1982_2022.nc")
RECO_FILE = "/data/BESS_V2/BESS_RECO_1982-2022_0.1deg.nc"
NEE_FILE = "/data/BESS_V2/NEE_1982-2022_0.1deg.nc"

FLASH_SMRZ_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMrz_5.3/flash_drought_events_v5.nc")
FLASH_SMS_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMs_5.3/flash_drought_events_v5.nc")
NONFLASH_SMRZ_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMrz_5.3/nonflash_drought_events_v5.nc")
NONFLASH_SMS_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMs_5.3/nonflash_drought_events_v5.nc")


def _common(metric_name, data_var, data_file, direction, output_dir):
    return {
        "start_year": 1982,
        "end_year": 2022,
        "window_before": 60,
        "window_after": 180,
        "recovery_window": 120,
        "max_window_after": 600,
        "response_search_window": 60,
        "response_threshold": 0.5 if direction == "positive" else -0.5,
        "recover_threshold": 0.25 if direction == "positive" else -0.25,
        "consecutive_days": 3,
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


CONFIGS = {
    "gpp_code1": {
        **_common("gpp", "GPP", GPP_FILE, "negative", os.path.join(BASE_DIR, "process/GPP-draught-analysis/code1/results")),
        "event_mode": "flash",
        "event_file": FLASH_SMRZ_FILE,
        "n_workers": 16,
        "lat_chunk_size": 20,
        "title": "GPP Response to SMrz Flash Drought - v20260316",
        "description": "Standardized flash-drought GPP response using onset_start and drought_start anchors.",
        "relative_output_file": os.path.join(BASE_DIR, "process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260316.nc"),
        "with_abs_output_file": os.path.join(BASE_DIR, "process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260316_with_abs.nc"),
        "temp_dir": os.path.join(BASE_DIR, "process/GPP-draught-analysis/code1/results/temp_chunks_v20260316"),
    },
    "gpp_code2": {
        **_common("gpp", "GPP", GPP_FILE, "negative", os.path.join(BASE_DIR, "process/GPP-draught-analysis/code2_SMs/results")),
        "event_mode": "flash",
        "event_file": FLASH_SMS_FILE,
        "n_workers": 16,
        "lat_chunk_size": 20,
        "title": "GPP Response to SMs Flash Drought - v20260316",
        "description": "Standardized flash-drought GPP response using onset_start and drought_start anchors.",
        "relative_output_file": os.path.join(BASE_DIR, "process/GPP-draught-analysis/code2_SMs/results/gpp_response_SMs_events_global_v20260316.nc"),
        "with_abs_output_file": os.path.join(BASE_DIR, "process/GPP-draught-analysis/code2_SMs/results/gpp_response_SMs_events_global_v20260316_with_abs.nc"),
        "temp_dir": os.path.join(BASE_DIR, "process/GPP-draught-analysis/code2_SMs/results/temp_chunks_v20260316"),
    },
    "gpp_code3": {
        **_common("gpp", "GPP", GPP_FILE, "negative", os.path.join(BASE_DIR, "process/GPP-draught-analysis/code3_nonflash_SMrz/result")),
        "event_mode": "nonflash",
        "event_file": NONFLASH_SMRZ_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "GPP Response to SMrz Nonflash Drought - v20260316",
        "description": "Standardized nonflash-drought GPP response using onset_start as the primary anchor.",
        "relative_output_file": os.path.join(BASE_DIR, "process/GPP-draught-analysis/code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v20260316.nc"),
        "with_abs_output_file": os.path.join(BASE_DIR, "process/GPP-draught-analysis/code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v20260316_with_abs.nc"),
        "temp_dir": os.path.join(BASE_DIR, "process/GPP-draught-analysis/code3_nonflash_SMrz/result/temp_chunks_v20260316"),
    },
    "gpp_code4": {
        **_common("gpp", "GPP", GPP_FILE, "negative", os.path.join(BASE_DIR, "process/GPP-draught-analysis/code4_nonflash_SMs/result")),
        "event_mode": "nonflash",
        "event_file": NONFLASH_SMS_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "GPP Response to SMs Nonflash Drought - v20260316",
        "description": "Standardized nonflash-drought GPP response using onset_start as the primary anchor.",
        "relative_output_file": os.path.join(BASE_DIR, "process/GPP-draught-analysis/code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v20260316.nc"),
        "with_abs_output_file": os.path.join(BASE_DIR, "process/GPP-draught-analysis/code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v20260316_with_abs.nc"),
        "temp_dir": os.path.join(BASE_DIR, "process/GPP-draught-analysis/code4_nonflash_SMs/result/temp_chunks_v20260316"),
    },
    "reco_code1": {
        **_common("reco", "RECO", RECO_FILE, "negative", os.path.join(BASE_DIR, "process/RECO-draught-analysis/code1/results")),
        "event_mode": "flash",
        "event_file": FLASH_SMRZ_FILE,
        "n_workers": 16,
        "lat_chunk_size": 20,
        "title": "RECO Response to SMrz Flash Drought - v20260316",
        "description": "Standardized flash-drought RECO response using onset_start and drought_start anchors.",
        "relative_output_file": os.path.join(BASE_DIR, "process/RECO-draught-analysis/code1/results/reco_response_SMrz_events_global_v20260316.nc"),
        "with_abs_output_file": os.path.join(BASE_DIR, "process/RECO-draught-analysis/code1/results/reco_response_SMrz_events_global_v20260316_with_abs.nc"),
        "temp_dir": os.path.join(BASE_DIR, "process/RECO-draught-analysis/code1/results/temp_chunks_v20260316"),
    },
    "reco_code2": {
        **_common("reco", "RECO", RECO_FILE, "negative", os.path.join(BASE_DIR, "process/RECO-draught-analysis/code2_SMs/results")),
        "event_mode": "flash",
        "event_file": FLASH_SMS_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "RECO Response to SMs Flash Drought - v20260316",
        "description": "Standardized flash-drought RECO response using onset_start and drought_start anchors.",
        "relative_output_file": os.path.join(BASE_DIR, "process/RECO-draught-analysis/code2_SMs/results/reco_response_SMs_drought_v20260316.nc"),
        "with_abs_output_file": os.path.join(BASE_DIR, "process/RECO-draught-analysis/code2_SMs/results/reco_response_SMs_drought_v20260316_with_abs.nc"),
        "temp_dir": os.path.join(BASE_DIR, "process/RECO-draught-analysis/code2_SMs/results/temp_chunks_v20260316"),
    },
    "reco_code3": {
        **_common("reco", "RECO", RECO_FILE, "negative", os.path.join(BASE_DIR, "process/RECO-draught-analysis/code3_nonflash_SMrz/result")),
        "event_mode": "nonflash",
        "event_file": NONFLASH_SMRZ_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "RECO Response to SMrz Nonflash Drought - v20260316",
        "description": "Standardized nonflash-drought RECO response using onset_start as the primary anchor.",
        "relative_output_file": os.path.join(BASE_DIR, "process/RECO-draught-analysis/code3_nonflash_SMrz/result/reco_response_nonflash_SMrz_drought_v20260316.nc"),
        "with_abs_output_file": os.path.join(BASE_DIR, "process/RECO-draught-analysis/code3_nonflash_SMrz/result/reco_response_nonflash_SMrz_drought_v20260316_with_abs.nc"),
        "temp_dir": os.path.join(BASE_DIR, "process/RECO-draught-analysis/code3_nonflash_SMrz/result/temp_chunks_v20260316"),
    },
    "reco_code4": {
        **_common("reco", "RECO", RECO_FILE, "negative", os.path.join(BASE_DIR, "process/RECO-draught-analysis/code4_nonflash_SMs/result")),
        "event_mode": "nonflash",
        "event_file": NONFLASH_SMS_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "RECO Response to SMs Nonflash Drought - v20260316",
        "description": "Standardized nonflash-drought RECO response using onset_start as the primary anchor.",
        "relative_output_file": os.path.join(BASE_DIR, "process/RECO-draught-analysis/code4_nonflash_SMs/result/reco_response_nonflash_SMs_drought_v20260316.nc"),
        "with_abs_output_file": os.path.join(BASE_DIR, "process/RECO-draught-analysis/code4_nonflash_SMs/result/reco_response_nonflash_SMs_drought_v20260316_with_abs.nc"),
        "temp_dir": os.path.join(BASE_DIR, "process/RECO-draught-analysis/code4_nonflash_SMs/result/temp_chunks_v20260316"),
    },
    "nee_code1": {
        **_common("nee", "NEE", NEE_FILE, "positive", os.path.join(BASE_DIR, "process/NEE-draught-analysis/code1SMrz/result")),
        "event_mode": "flash",
        "event_file": FLASH_SMRZ_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "NEE Response to SMrz Flash Drought - v20260316",
        "description": "Standardized flash-drought NEE response using onset_start and drought_start anchors.",
        "relative_output_file": os.path.join(BASE_DIR, "process/NEE-draught-analysis/code1SMrz/result/nee_response_SMrz_drought_v20260316.nc"),
        "with_abs_output_file": os.path.join(BASE_DIR, "process/NEE-draught-analysis/code1SMrz/result/nee_response_SMrz_drought_v20260316_with_abs.nc"),
        "temp_dir": os.path.join(BASE_DIR, "process/NEE-draught-analysis/code1SMrz/result/temp_chunks_v20260316"),
    },
    "nee_code2": {
        **_common("nee", "NEE", NEE_FILE, "positive", os.path.join(BASE_DIR, "process/NEE-draught-analysis/code2SMs/result")),
        "event_mode": "flash",
        "event_file": FLASH_SMS_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "NEE Response to SMs Flash Drought - v20260316",
        "description": "Standardized flash-drought NEE response using onset_start and drought_start anchors.",
        "relative_output_file": os.path.join(BASE_DIR, "process/NEE-draught-analysis/code2SMs/result/nee_response_SMs_drought_v20260316.nc"),
        "with_abs_output_file": os.path.join(BASE_DIR, "process/NEE-draught-analysis/code2SMs/result/nee_response_SMs_drought_v20260316_with_abs.nc"),
        "temp_dir": os.path.join(BASE_DIR, "process/NEE-draught-analysis/code2SMs/result/temp_chunks_v20260316"),
    },
    "nee_code3": {
        **_common("nee", "NEE", NEE_FILE, "positive", os.path.join(BASE_DIR, "process/NEE-draught-analysis/code3_nonflash_SMrz/result")),
        "event_mode": "nonflash",
        "event_file": NONFLASH_SMRZ_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "NEE Response to SMrz Nonflash Drought - v20260316",
        "description": "Standardized nonflash-drought NEE response using onset_start as the primary anchor.",
        "relative_output_file": os.path.join(BASE_DIR, "process/NEE-draught-analysis/code3_nonflash_SMrz/result/nee_response_nonflash_SMrz_drought_v20260316.nc"),
        "with_abs_output_file": os.path.join(BASE_DIR, "process/NEE-draught-analysis/code3_nonflash_SMrz/result/nee_response_nonflash_SMrz_drought_v20260316_with_abs.nc"),
        "temp_dir": os.path.join(BASE_DIR, "process/NEE-draught-analysis/code3_nonflash_SMrz/result/temp_chunks_v20260316"),
    },
    "nee_code4": {
        **_common("nee", "NEE", NEE_FILE, "positive", os.path.join(BASE_DIR, "process/NEE-draught-analysis/code4_nonflash_SMs/result")),
        "event_mode": "nonflash",
        "event_file": NONFLASH_SMS_FILE,
        "n_workers": 30,
        "lat_chunk_size": 5,
        "title": "NEE Response to SMs Nonflash Drought - v20260316",
        "description": "Standardized nonflash-drought NEE response using onset_start as the primary anchor.",
        "relative_output_file": os.path.join(BASE_DIR, "process/NEE-draught-analysis/code4_nonflash_SMs/result/nee_response_nonflash_SMs_drought_v20260316.nc"),
        "with_abs_output_file": os.path.join(BASE_DIR, "process/NEE-draught-analysis/code4_nonflash_SMs/result/nee_response_nonflash_SMs_drought_v20260316_with_abs.nc"),
        "temp_dir": os.path.join(BASE_DIR, "process/NEE-draught-analysis/code4_nonflash_SMs/result/temp_chunks_v20260316"),
    },
}


def get_config(key):
    if key not in CONFIGS:
        raise KeyError(f"Unknown v20260316 config key: {key}")
    return copy.deepcopy(CONFIGS[key])
