#!/usr/bin/env python
"""Attach pre-peak precipitation mean to the latest RECO precipEmean feature table."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-table", required=True)
    parser.add_argument("--precip-features", required=True)
    parser.add_argument("--output-table", required=True)
    return parser.parse_args()


def attach_prepeak_precip_column(base_df: pd.DataFrame, precip_df: pd.DataFrame) -> pd.DataFrame:
    keep_cols = ["event_uid", "prepeak_total_precipitation_mean"]
    if "prepeak_total_precipitation_mean" not in precip_df.columns:
        raise KeyError("Missing required column: prepeak_total_precipitation_mean")

    attach = precip_df.loc[:, keep_cols].copy()
    if attach["event_uid"].duplicated().any():
        raise ValueError("Duplicate event_uid values found in precipitation feature table.")

    out = base_df.drop(columns=["prepeak_total_precipitation_mean"], errors="ignore").merge(
        attach,
        on="event_uid",
        how="left",
        validate="one_to_one",
    )
    return out


def main() -> None:
    args = parse_args()
    base_path = Path(args.base_table)
    precip_path = Path(args.precip_features)
    output_path = Path(args.output_table)

    base_df = pd.read_parquet(base_path)
    precip_df = pd.read_parquet(precip_path, columns=["event_uid", "prepeak_total_precipitation_mean"])
    out = attach_prepeak_precip_column(base_df, precip_df)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(output_path, index=False)

    matched = int(out["prepeak_total_precipitation_mean"].notna().sum())
    print(f"[DONE] rows={len(out):,}")
    print(f"[DONE] matched_prepeak_precip={matched:,}")
    print(f"[DONE] output={output_path}")


if __name__ == "__main__":
    main()
