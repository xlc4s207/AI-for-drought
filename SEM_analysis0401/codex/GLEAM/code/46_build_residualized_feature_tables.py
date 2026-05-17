#!/usr/bin/env python3
"""Build residualized 0401 feature tables for SHAP sensitivity runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


DATA_DIR = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/data")
OUT_DIR = DATA_DIR / "residualized_shap_inputs_20260502"


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
        output_path=OUT_DIR / "feature_table_prepeak_event_GPP_code1_flash_SMrz_0401_residR1_tmp_ssrd.parquet",
        residual_specs=(
            ResidualSpec(
                target="prepeak_VPD_mean",
                parents=("prepeak_temperature_2m_mean", "prepeak_wind_speed_mean"),
                output="prepeak_VPD_resid",
            ),
            ResidualSpec(
                target="prepeak_total_evaporation_mean",
                parents=("prepeak_total_precipitation_mean", "prepeak_VPD_mean"),
                output="prepeak_total_evaporation_resid",
            ),
        ),
    ),
    "gpp_recovery": ScenarioConfig(
        input_path=DATA_DIR / "feature_table_recovery_phase_GPP_code1_flash_SMrz_0401.parquet",
        output_path=OUT_DIR / "feature_table_recovery_phase_GPP_code1_flash_SMrz_0401_residR1_tmp_ssrd.parquet",
        residual_specs=(
            ResidualSpec(
                target="recoverywin_VPD_mean",
                parents=("recoverywin_temperature_2m_mean", "recoverywin_wind_speed_mean"),
                output="recoverywin_VPD_resid",
            ),
            ResidualSpec(
                target="recoverywin_total_evaporation_mean",
                parents=("recoverywin_total_precipitation_mean", "recoverywin_VPD_mean"),
                output="recoverywin_total_evaporation_resid",
            ),
        ),
    ),
    "reco_prepeak": ScenarioConfig(
        input_path=DATA_DIR / "feature_table_prepeak_event_RECO_code1_flash_SMrz_0401_mswepE.parquet",
        output_path=OUT_DIR / "feature_table_prepeak_event_RECO_code1_flash_SMrz_0401_mswepE_residR1_tmp_ssrd.parquet",
        residual_specs=(
            ResidualSpec(
                target="prepeak_VPD_mean",
                parents=("prepeak_temperature_2m_mean", "prepeak_wind_speed_mean"),
                output="prepeak_VPD_resid",
            ),
            ResidualSpec(
                target="prepeak_total_evaporation_mean",
                parents=("prepeak_total_precipitation_mean", "prepeak_VPD_mean"),
                output="prepeak_total_evaporation_resid",
            ),
        ),
    ),
    "reco_recovery": ScenarioConfig(
        input_path=DATA_DIR / "feature_table_recovery_phase_RECO_code1_flash_SMrz_0401_mswepE.parquet",
        output_path=OUT_DIR / "feature_table_recovery_phase_RECO_code1_flash_SMrz_0401_mswepE_residR1_tmp_ssrd.parquet",
        residual_specs=(
            ResidualSpec(
                target="recoverywin_VPD_mean",
                parents=("recoverywin_temperature_2m_mean", "recoverywin_wind_speed_mean"),
                output="recoverywin_VPD_resid",
            ),
            ResidualSpec(
                target="recoverywin_total_evaporation_mean",
                parents=("recoverywin_total_precipitation_mean", "recoverywin_VPD_mean"),
                output="recoverywin_total_evaporation_resid",
            ),
        ),
    ),
}


def fit_residual(values: pd.DataFrame, target: str, parents: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray]:
    cols = [target, *parents]
    subset = values.loc[:, cols].apply(pd.to_numeric, errors="coerce")
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
    model_rows: list[dict[str, object]] = []

    for spec in cfg.residual_specs:
        df[spec.output] = np.nan
        for biome, biome_index in df.groupby("biome", sort=True).groups.items():
            biome_df = df.loc[biome_index]
            residuals, coefs = fit_residual(biome_df, spec.target, spec.parents)
            df.loc[biome_index, spec.output] = residuals
            model_rows.append(
                {
                    "scenario": name,
                    "biome": biome,
                    "target": spec.target,
                    "residual_column": spec.output,
                    "parents": ",".join(spec.parents),
                    "n_rows": int(len(biome_df)),
                    "n_valid_rows": int(np.isfinite(residuals).sum()),
                    "intercept": float(coefs[0]) if np.isfinite(coefs[0]) else np.nan,
                    **{
                        f"coef_{parent}": float(coefs[i + 1]) if i + 1 < len(coefs) else np.nan
                        for i, parent in enumerate(spec.parents)
                    },
                }
            )

    return df, pd.DataFrame(model_rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_rows: list[pd.DataFrame] = []
    for name, cfg in SCENARIOS.items():
        out_df, meta_df = process_scenario(name, cfg)
        out_df.to_parquet(cfg.output_path, index=False)
        meta_path = cfg.output_path.with_suffix(".residual_models.csv")
        meta_df.to_csv(meta_path, index=False)
        all_rows.append(meta_df)
        print(f"[DONE] {name} -> {cfg.output_path}")
    pd.concat(all_rows, ignore_index=True).to_csv(OUT_DIR / "residual_model_summary_20260502.csv", index=False)


if __name__ == "__main__":
    main()
