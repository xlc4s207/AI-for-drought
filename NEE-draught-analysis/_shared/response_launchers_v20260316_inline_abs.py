#!/usr/bin/env python3
"""Launcher helpers for v20260316_inline_abs wrapper scripts."""

from response_configs_v20260316_inline_abs import get_config
from response_standardization_v20260316_inline_abs import run_relative_analysis


def run_relative_key(config_key):
    return run_relative_analysis(get_config(config_key))


def run_with_abs_key(config_key):
    config = get_config(config_key)
    config["relative_output_file"] = config["with_abs_output_file"]
    return run_relative_analysis(config)


def run_add_absolute_key(config_key):
    return run_with_abs_key(config_key)
