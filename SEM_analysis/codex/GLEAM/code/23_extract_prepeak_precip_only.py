#!/usr/bin/env python
"""Wrapper around 02_extract_era5_features.py limited to prepeak precipitation mean."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("02_extract_era5_features.py")
SPEC = importlib.util.spec_from_file_location("gleam_extract_era5_features", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:  # pragma: no cover
    raise RuntimeError(f"Unable to load helper module from {SCRIPT_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def patch_total_precipitation_to_prepeak_mean(module) -> None:
    module.WINDOW_STATS["total_precipitation"] = {"prepeak": ("mean",)}


def main() -> None:
    patch_total_precipitation_to_prepeak_mean(MODULE)
    MODULE.main()


if __name__ == "__main__":
    main()
