#!/usr/bin/env python
"""Attach RECO prepeak predictor features to the pre-recovery event table."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


PREPEAK_FEATURE_COLUMNS = [
    "prepeak_total_precipitation_mean",
    "prepeak_total_evaporation_mean",
    "prepeak_temperature_2m_mean",
    "prepeak_VPD_mean",
    "prepeak_SMrz_mean",
    "prepeak_lai_total_mean",
    "prepeak_ssrd_mean",
    "prepeak_strd_mean",
    "prepeak_wind_speed_mean",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-table", required=True)
    parser.add_argument("--prepeak-features", required=True)
    parser.add_argument("--sm-features", default=None)
    parser.add_argument("--output-table", required=True)
    return parser.parse_args()


def merge_prepeak_feature_tables(era5_df: pd.DataFrame, sm_df: pd.DataFrame) -> pd.DataFrame:
    keep_cols = ["event_uid", "prepeak_SMrz_mean"]
    missing = [col for col in keep_cols if col not in sm_df.columns]
    if missing:
        raise KeyError(f"Missing required SM feature columns: {missing}")
    sm_keep = sm_df.loc[:, keep_cols].copy()
    if sm_keep["event_uid"].duplicated().any():
        raise ValueError("Duplicate event_uid values found in SM feature table.")
    return era5_df.merge(sm_keep, on="event_uid", how="left", validate="one_to_one")


def attach_prepeak_feature_columns(base_df: pd.DataFrame, prepeak_df: pd.DataFrame) -> pd.DataFrame:
    missing = [col for col in PREPEAK_FEATURE_COLUMNS if col not in prepeak_df.columns]
    if missing:
        raise KeyError(f"Missing required prepeak feature columns: {missing}")

    keep_cols = ["event_uid", *PREPEAK_FEATURE_COLUMNS]
    attach = prepeak_df.loc[:, keep_cols].copy()
    if attach["event_uid"].duplicated().any():
        raise ValueError("Duplicate event_uid values found in prepeak feature table.")

    out = base_df.drop(columns=PREPEAK_FEATURE_COLUMNS, errors="ignore").merge(
        attach,
        on="event_uid",
        how="left",
        validate="one_to_one",
    )
    return out


def main() -> None:
    args = parse_args()
    base_path = Path(args.base_table)
    prepeak_path = Path(args.prepeak_features)
    output_path = Path(args.output_table)

    base_df = pd.read_parquet(base_path)
    prepeak_df = pd.read_parquet(prepeak_path)
    if args.sm_features:
        sm_df = pd.read_parquet(Path(args.sm_features), columns=["event_uid", "prepeak_SMrz_mean"])
        prepeak_df = merge_prepeak_feature_tables(prepeak_df, sm_df)
    out = attach_prepeak_feature_columns(base_df, prepeak_df)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(output_path, index=False)

    matched = int(out["prepeak_total_precipitation_mean"].notna().sum())
    print(f"[DONE] rows={len(out):,}")
    print(f"[DONE] matched_prepeak_rows={matched:,}")
    print(f"[DONE] output={output_path}")


if __name__ == "__main__":
    main()
