#!/usr/bin/env python3
"""Build residualized 0401 feature tables keeping TMP plus radiation residual terms."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


DATA_DIR = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/data")
OUT_DIR = DATA_DIR / "residualized_shap_inputs_20260502_tmp_rad"


@dataclass(frozen=True)
class ResidualSpec:
    target: str
    parents: tuple[str, ...]
    output: str


@dataclass(frozen=True)
class ScenarioConfig:
    input_path: Path
    output_path: Path
    residual_specs: tuple[ResidualSpec, ...]


SCENARIOS: dict[str, ScenarioConfig] = {
    "gpp_prepeak": ScenarioConfig(
        input_path=DATA_DIR / "feature_table_prepeak_event_GPP_code1_flash_SMrz_0401.parquet",
        output_path=OUT_DIR / "feature_table_prepeak_event_GPP_code1_flash_SMrz_0401_residRtmpRad.parquet",
        residual_specs=(
            ResidualSpec("prepeak_VPD_mean", ("prepeak_temperature_2m_mean", "prepeak_wind_speed_mean"), "prepeak_VPD_resid"),
            ResidualSpec("prepeak_total_evaporation_mean", ("prepeak_total_precipitation_mean", "prepeak_VPD_mean"), "prepeak_total_evaporation_resid"),
            ResidualSpec("prepeak_ssrd_mean", ("prepeak_temperature_2m_mean",), "prepeak_ssrd_resid_tmp"),
            ResidualSpec("prepeak_strd_mean", ("prepeak_temperature_2m_mean",), "prepeak_strd_resid_tmp"),
        ),
    ),
    "gpp_recovery": ScenarioConfig(
        input_path=DATA_DIR / "feature_table_recovery_phase_GPP_code1_flash_SMrz_0401.parquet",
        output_path=OUT_DIR / "feature_table_recovery_phase_GPP_code1_flash_SMrz_0401_residRtmpRad.parquet",
        residual_specs=(
            ResidualSpec("recoverywin_VPD_mean", ("recoverywin_temperature_2m_mean", "recoverywin_wind_speed_mean"), "recoverywin_VPD_resid"),
            ResidualSpec("recoverywin_total_evaporation_mean", ("recoverywin_total_precipitation_mean", "recoverywin_VPD_mean"), "recoverywin_total_evaporation_resid"),
            ResidualSpec("recoverywin_ssrd_mean", ("recoverywin_temperature_2m_mean",), "recoverywin_ssrd_resid_tmp"),
            ResidualSpec("recoverywin_strd_mean", ("recoverywin_temperature_2m_mean",), "recoverywin_strd_resid_tmp"),
        ),
    ),
    "reco_prepeak": ScenarioConfig(
        input_path=DATA_DIR / "feature_table_prepeak_event_RECO_code1_flash_SMrz_0401_mswepE.parquet",
        output_path=OUT_DIR / "feature_table_prepeak_event_RECO_code1_flash_SMrz_0401_mswepE_residRtmpRad.parquet",
        residual_specs=(
            ResidualSpec("prepeak_VPD_mean", ("prepeak_temperature_2m_mean", "prepeak_wind_speed_mean"), "prepeak_VPD_resid"),
            ResidualSpec("prepeak_total_evaporation_mean", ("prepeak_total_precipitation_mean", "prepeak_VPD_mean"), "prepeak_total_evaporation_resid"),
            ResidualSpec("prepeak_ssrd_mean", ("prepeak_temperature_2m_mean",), "prepeak_ssrd_resid_tmp"),
            ResidualSpec("prepeak_strd_mean", ("prepeak_temperature_2m_mean",), "prepeak_strd_resid_tmp"),
        ),
    ),
    "reco_recovery": ScenarioConfig(
        input_path=DATA_DIR / "feature_table_recovery_phase_RECO_code1_flash_SMrz_0401_mswepE.parquet",
        output_path=OUT_DIR / "feature_table_recovery_phase_RECO_code1_flash_SMrz_0401_mswepE_residRtmpRad.parquet",
        residual_specs=(
            ResidualSpec("recoverywin_VPD_mean", ("recoverywin_temperature_2m_mean", "recoverywin_wind_speed_mean"), "recoverywin_VPD_resid"),
            ResidualSpec("recoverywin_total_evaporation_mean", ("recoverywin_total_precipitation_mean", "recoverywin_VPD_mean"), "recoverywin_total_evaporation_resid"),
            ResidualSpec("recoverywin_ssrd_mean", ("recoverywin_temperature_2m_mean",), "recoverywin_ssrd_resid_tmp"),
            ResidualSpec("recoverywin_strd_mean", ("recoverywin_temperature_2m_mean",), "recoverywin_strd_resid_tmp"),
        ),
    ),
}


def fit_residual(df: pd.DataFrame, target: str, parents: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray]:
    cols = [target, *parents]
    subset = df.loc[:, cols].apply(pd.to_numeric, errors="coerce")
    valid = np.all(np.isfinite(subset.to_numpy(dtype=float)), axis=1)
    residuals = np.full(len(subset), np.nan, dtype=np.float32)
    coefs = np.full(len(parents) + 1, np.nan, dtype=np.float64)
    if valid.sum() < len(parents) + 5:
        return residuals, coefs
    y = subset.loc[valid, target].to_numpy(dtype=float)
    X = subset.loc[valid, list(parents)].to_numpy(dtype=float)
    X_design = np.column_stack([np.ones(len(X)), X])
    coefs, *_ = np.linalg.lstsq(X_design, y, rcond=None)
    pred = X_design @ coefs
    residuals[np.where(valid)[0]] = (y - pred).astype(np.float32)
    return residuals, coefs


def process_scenario(name: str, cfg: ScenarioConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_parquet(cfg.input_path).copy()
    rows: list[dict[str, object]] = []
    for spec in cfg.residual_specs:
        df[spec.output] = np.nan
        for biome, idx in df.groupby("biome", sort=True).groups.items():
            part = df.loc[idx]
            residuals, coefs = fit_residual(part, spec.target, spec.parents)
            df.loc[idx, spec.output] = residuals
            row = {
                "scenario": name,
                "biome": biome,
                "target": spec.target,
                "residual_column": spec.output,
                "parents": ",".join(spec.parents),
                "n_rows": int(len(part)),
                "n_valid_rows": int(np.isfinite(residuals).sum()),
                "intercept": float(coefs[0]) if np.isfinite(coefs[0]) else np.nan,
            }
            for i, parent in enumerate(spec.parents):
                row[f"coef_{parent}"] = float(coefs[i + 1]) if i + 1 < len(coefs) else np.nan
            rows.append(row)
    return df, pd.DataFrame(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_meta = []
    for name, cfg in SCENARIOS.items():
        out_df, meta = process_scenario(name, cfg)
        out_df.to_parquet(cfg.output_path, index=False)
        meta.to_csv(cfg.output_path.with_suffix(".residual_models.csv"), index=False)
        all_meta.append(meta)
        print(f"[DONE] {name} -> {cfg.output_path}")
    pd.concat(all_meta, ignore_index=True).to_csv(OUT_DIR / "residual_model_summary_tmp_rad_20260502.csv", index=False)


if __name__ == "__main__":
    main()
