#!/usr/bin/env python3
"""Configuration registry for v20260316_3 hybrid drought-response scripts."""

import copy
import os

from response_configs_v20260316 import CONFIGS as BASE_CONFIGS


BASE_DIR = "/home/xulc/flash_drought"
GPP_FILE = os.path.join(BASE_DIR, "process/GPP-draught-analysis/SMrz_result/BESS_GPP_1982_2022.nc")


def _upgrade_config(config):
    cfg = copy.deepcopy(config)
    cfg["title"] = cfg["title"].replace("v20260316", "v20260316_3")
    cfg["description"] = (
        cfg["description"] + " Includes GPP-climatology timing stratification with legacy bulk-read processing."
    )
    cfg["relative_output_file"] = cfg["relative_output_file"].replace("v20260316", "v20260316_3")
    cfg["with_abs_output_file"] = cfg["with_abs_output_file"].replace("v20260316", "v20260316_3")
    cfg["temp_dir"] = cfg["temp_dir"].replace("v20260316", "v20260316_3")
    cfg["timing_reference_file"] = GPP_FILE
    cfg["timing_reference_var"] = "GPP"
    return cfg


CONFIGS = {key: _upgrade_config(value) for key, value in BASE_CONFIGS.items()}
CONFIGS["gpp_code1"]["lat_chunk_size"] = 5


def get_config(key):
    if key not in CONFIGS:
        raise KeyError(f"Unknown v20260316_3 config key: {key}")
    return copy.deepcopy(CONFIGS[key])
