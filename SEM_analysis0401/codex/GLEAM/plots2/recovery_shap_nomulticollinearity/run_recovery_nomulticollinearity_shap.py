#!/usr/bin/env python3
"""Run recovery-window SHAP with grouped PCA and orthogonalized inputs.

This reuses the prepeak no-multicollinearity workflow, but replaces the
prepeak meteorological predictors with recovery-window predictors.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
import sys

import pandas as pd


ROOT = Path("/home/xulc/flash_drought")
GLEAM = ROOT / "process/SEM_analysis0401/codex/GLEAM"
PREPEAK_SCRIPT = GLEAM / "plots2/prepeak_shap_nomulticollinearity/run_prepeak_nomulticollinearity_shap.py"
OUT = GLEAM / "plots2/recovery_shap_nomulticollinearity"


spec = importlib.util.spec_from_file_location("prepeak_nomulticollinearity", PREPEAK_SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to import {PREPEAK_SCRIPT}")
pre = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pre
spec.loader.exec_module(pre)


@dataclass(frozen=True)
class MetricConfig:
    metric: str
    table: Path


pre.OUT = OUT
pre.METRICS = (
    MetricConfig("GPP", GLEAM / "data/feature_table_merged_GPP_code1_flash_SMrz_0401.parquet"),
    MetricConfig("RECO", GLEAM / "data/feature_table_merged_RECO_code1_flash_SMrz_0401_mswepE.parquet"),
)

pre.RAW_FEATURES = {
    "SSRD": "recoverywin_ssrd_mean",
    "EVA": "recoverywin_total_evaporation_mean",
    "TMP": "recoverywin_temperature_2m_mean",
    "STRD": "recoverywin_strd_mean",
    "SMrz": "recoverywin_SMrz_mean",
    "Wind": "recoverywin_wind_speed_mean",
    "VPD": "recoverywin_VPD_mean",
    "Duration": "event_duration",
    "Pre": "recoverywin_total_precipitation_mean",
    "Intensity": "event_intensity",
}


def write_readme(summaries: pd.DataFrame) -> None:
    lines = [
        "# Recovery-window SHAP without explicit multicollinearity",
        "",
        "This workflow mirrors `prepeak_shap_nomulticollinearity`, but uses recovery-window predictors to explain `t_recover_to_baseline_abs_peak`.",
        "",
        "Source predictors are restricted to the same ten conceptual variables:",
        "SSRD, EVA, TMP, STRD, SMrz, Wind, VPD, Duration, Pre, Intensity.",
        "",
        "Meteorological and water variables are mapped to `recoverywin_*` fields:",
        "- SSRD: `recoverywin_ssrd_mean`",
        "- EVA: `recoverywin_total_evaporation_mean`",
        "- TMP: `recoverywin_temperature_2m_mean`",
        "- STRD: `recoverywin_strd_mean`",
        "- SMrz: `recoverywin_SMrz_mean`",
        "- Wind: `recoverywin_wind_speed_mean`",
        "- VPD: `recoverywin_VPD_mean`",
        "- Pre: `recoverywin_total_precipitation_mean`",
        "",
        "Two transformed-input versions are provided:",
        "",
        "- `group_pca`: PCA within mechanism groups: Energy(SSRD/STRD/TMP), Water(Pre/EVA/SMrz), AtmosDemand(VPD/Wind), Event(Duration/Intensity). Only PC1 is retained for each group.",
        "- `orthogonal_decomposition`: sequential residualization using the same physical ordering as the prepeak workflow.",
        "",
        "Each metric/biome folder contains `feature_importance.csv`, `feature_importance_beeswarm.png`, `feature_importance_bar.png`, `dependence_plots/`, `vif_after_transform.csv`, and `run_summary.txt`.",
        "",
        "## Model summary",
        "",
        "```csv",
        summaries.to_csv(index=False).strip(),
        "```",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


pre.write_readme = write_readme


if __name__ == "__main__":
    pre.main()
