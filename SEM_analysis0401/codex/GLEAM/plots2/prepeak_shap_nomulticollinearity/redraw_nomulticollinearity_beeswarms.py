#!/usr/bin/env python3
"""Redraw beeswarm plots with feature and SHAP columns aligned."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT = Path(__file__).with_name("run_prepeak_nomulticollinearity_shap.py")
SPEC = importlib.util.spec_from_file_location("nomulticollinearity_shap", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to import {SCRIPT}")
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)

ROOT = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/plots2/prepeak_shap_nomulticollinearity")


def redraw_one(folder: Path) -> None:
    importance = pd.read_csv(folder / "feature_importance.csv")
    sample = pd.read_parquet(folder / "dependence_sample_features.parquet")
    shap_df = pd.read_parquet(folder / "dependence_sample_shap_values.parquet")
    feature_order = importance.sort_values("rank")["feature"].tolist()
    mod.save_beeswarm(
        shap_df.to_numpy(dtype=float),
        sample,
        feature_order,
        folder / "feature_importance_beeswarm.png",
    )


def main() -> None:
    count = 0
    for folder in sorted(ROOT.glob("*/*/*")):
        if not folder.is_dir():
            continue
        required = [
            folder / "feature_importance.csv",
            folder / "dependence_sample_features.parquet",
            folder / "dependence_sample_shap_values.parquet",
        ]
        if all(path.exists() for path in required):
            redraw_one(folder)
            count += 1
    print(f"Redrew {count} beeswarm plots")


if __name__ == "__main__":
    main()
