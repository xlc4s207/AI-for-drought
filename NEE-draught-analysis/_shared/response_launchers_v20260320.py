#!/usr/bin/env python3
"""Launcher helpers for v20260320 GPP scripts."""

from response_configs_v20260320 import get_config
from response_standardization_v20260320 import run_relative_analysis


def run_relative_key(config_key):
    return run_relative_analysis(get_config(config_key))


def run_with_abs_key(config_key):
    return run_relative_analysis(get_config(config_key))
