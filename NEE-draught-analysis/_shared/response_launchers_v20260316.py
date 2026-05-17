#!/usr/bin/env python3
"""Launcher helpers for v20260316 wrapper scripts."""

from add_absolute_metrics_v20260316 import augment_absolute_metrics
from response_configs_v20260316 import get_config
from response_standardization_v20260316 import run_relative_analysis


def run_relative_key(config_key):
    return run_relative_analysis(get_config(config_key))


def run_with_abs_key(config_key):
    config = get_config(config_key)
    relative_output = run_relative_analysis(config)
    augment_absolute_metrics(
        input_file=relative_output,
        data_file=config["data_file"],
        var_name=config["data_var"],
        output_file=config["with_abs_output_file"],
        direction=config["direction"],
        baseline_tolerance_multiplier=config["baseline_tolerance_multiplier"],
        baseline_tolerance_floor_fraction=config["baseline_tolerance_floor_fraction"],
        baseline_recovery_consecutive_days=config["baseline_recovery_consecutive_days"],
    )
    return config["with_abs_output_file"]


def run_add_absolute_key(config_key):
    config = get_config(config_key)
    augment_absolute_metrics(
        input_file=config["relative_output_file"],
        data_file=config["data_file"],
        var_name=config["data_var"],
        output_file=config["with_abs_output_file"],
        direction=config["direction"],
        baseline_tolerance_multiplier=config["baseline_tolerance_multiplier"],
        baseline_tolerance_floor_fraction=config["baseline_tolerance_floor_fraction"],
        baseline_recovery_consecutive_days=config["baseline_recovery_consecutive_days"],
    )
    return config["with_abs_output_file"]
