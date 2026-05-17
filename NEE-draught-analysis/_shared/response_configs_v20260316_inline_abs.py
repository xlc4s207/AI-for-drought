#!/usr/bin/env python3
"""Configuration registry for v20260316 inline-absolute drought-response scripts."""

import copy

from response_configs_v20260316 import CONFIGS as BASE_CONFIGS


def _upgrade_config(config):
    cfg = copy.deepcopy(config)
    cfg["title"] = cfg["title"].replace("v20260316", "v20260316_inline_abs")
    cfg["description"] = (
        cfg["description"] + " Absolute metrics are computed inline during chunk processing."
    )
    cfg["relative_output_file"] = cfg["relative_output_file"].replace("v20260316", "v20260316_inline_abs")
    cfg["with_abs_output_file"] = cfg["with_abs_output_file"].replace("v20260316", "v20260316_inline_abs")
    cfg["temp_dir"] = cfg["temp_dir"].replace("v20260316", "v20260316_inline_abs")
    return cfg


CONFIGS = {key: _upgrade_config(value) for key, value in BASE_CONFIGS.items()}

LOW_MEMORY_OVERRIDES = {
    "gpp_code1": {"n_workers": 8, "lat_chunk_size": 5},
    "gpp_code2": {"n_workers": 8, "lat_chunk_size": 5},
    "gpp_code3": {"n_workers": 8, "lat_chunk_size": 2},
    "gpp_code4": {"n_workers": 8, "lat_chunk_size": 2},
    "nee_code1": {"n_workers": 8, "lat_chunk_size": 2},
    "nee_code2": {"n_workers": 8, "lat_chunk_size": 2},
    "nee_code3": {"n_workers": 8, "lat_chunk_size": 2},
    "nee_code4": {"n_workers": 8, "lat_chunk_size": 2},
    "reco_code1": {"n_workers": 8, "lat_chunk_size": 5},
    "reco_code2": {"n_workers": 8, "lat_chunk_size": 2},
    "reco_code3": {"n_workers": 8, "lat_chunk_size": 2},
    "reco_code4": {"n_workers": 8, "lat_chunk_size": 2},
}

for key, overrides in LOW_MEMORY_OVERRIDES.items():
    CONFIGS[key].update(overrides)


def get_config(key):
    if key not in CONFIGS:
        raise KeyError(f"Unknown v20260316_inline_abs config key: {key}")
    return copy.deepcopy(CONFIGS[key])
