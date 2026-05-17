#!/usr/bin/env python3
"""Plot 5-biome GPP/RECO importance overview for recovery-window SHAP runs."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


GLEAM = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM")
SOURCE = GLEAM / "plots2/prepeak_shap_nomulticollinearity/plot_nomulticollinearity_importance_overview.py"
ROOT = GLEAM / "plots2/recovery_shap_nomulticollinearity"

spec = importlib.util.spec_from_file_location("prepeak_importance_overview", SOURCE)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to import {SOURCE}")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
mod.ROOT = ROOT


if __name__ == "__main__":
    mod.main()
