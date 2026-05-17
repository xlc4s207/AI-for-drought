#!/usr/bin/env python
"""Build a phase-specific onset-to-peak feature table for SHAP and SEM."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


META_COLUMNS = [
    "event_uid",
    "metric",
    "code_id",
    "biome",
    "soil_layer",
    "drought_type",
    "lat",
    "lon",
    "event_id",
    "onset_year",
    "onset_doy",
    "drought_start_year",
    "drought_start_doy",
    "onset_start_date",
    "drought_start_date",
]

TARGET_COLUMN = "t_recover_to_baseline_abs_peak"
EVENT_INPUT_COLUMNS = [
    "event_onset_days",
    "event_duration",
    "event_intensity",
]
PHASE_FEATURE_SUFFIXES = [
    "total_precipitation_mean",
    "total_evaporation_mean",
    "temperature_2m_mean",
    "VPD_mean",
    "SMrz_mean",
    "lai_total_mean",
    "ssrd_mean",
    "strd_mean",
    "wind_speed_mean",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-table", required=True)
    parser.add_argument("--phase", choices=("prepeak", "shock"), required=True)
    parser.add_argument("--output-table", required=True)
    return parser.parse_args()


def required_phase_columns(phase: str) -> list[str]:
    return [f"{phase}_{suffix}" for suffix in PHASE_FEATURE_SUFFIXES]


def select_phase_feature_table(df: pd.DataFrame, phase: str) -> pd.DataFrame:
    required_columns = [TARGET_COLUMN, *EVENT_INPUT_COLUMNS, *required_phase_columns(phase)]
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns for phase={phase}: {missing}")

    keep_columns = [col for col in META_COLUMNS if col in df.columns]
    for col in [TARGET_COLUMN, *EVENT_INPUT_COLUMNS, *required_phase_columns(phase)]:
        if col not in keep_columns:
            keep_columns.append(col)
    return df.loc[:, keep_columns].copy()


def main() -> None:
    args = parse_args()
    source_path = Path(args.source_table)
    output_path = Path(args.output_table)

    df = pd.read_parquet(source_path)
    out = select_phase_feature_table(df, phase=args.phase)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(output_path, index=False)

    print(f"[DONE] phase={args.phase}")
    print(f"[DONE] rows={len(out):,}")
    print(f"[DONE] output={output_path}")


if __name__ == "__main__":
    main()
