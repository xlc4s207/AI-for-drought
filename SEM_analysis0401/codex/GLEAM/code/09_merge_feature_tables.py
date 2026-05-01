#!/usr/bin/env python
"""Merge master table with extracted ERA5, GLEAM-SM, and drought-event features."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from sem_gleam_common import (
    DATA_DIR,
    MASTER_VALID_PATH,
    PRE_RECOVERY_TABLE_PATH,
    RECOVERY_PHASE_TABLE_PATH,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", default=str(MASTER_VALID_PATH))
    parser.add_argument("--era5", required=True)
    parser.add_argument("--gleam-sm", required=True)
    parser.add_argument("--drought", required=True)
    parser.add_argument("--metric", default=None)
    parser.add_argument("--code-id", default=None)
    parser.add_argument("--biome", default=None)
    parser.add_argument("--drought-type", default=None)
    parser.add_argument("--soil-layer", default=None)
    parser.add_argument("--merged-output", default=None)
    parser.add_argument("--pre-output", default=str(PRE_RECOVERY_TABLE_PATH))
    parser.add_argument("--recovery-output", default=str(RECOVERY_PHASE_TABLE_PATH))
    return parser.parse_args()


def split_feature_columns(columns):
    pre_cols = []
    recovery_cols = []
    keep_cols = {"event_uid"}
    for col in columns:
        if col == "event_uid":
            continue
        if col.startswith(("pre30_", "prepeak_", "onset_", "shock_", "event_")):
            pre_cols.append(col)
        if col.startswith(("postpeak30_", "postpeak60_", "recoverywin_")):
            recovery_cols.append(col)
    return sorted(keep_cols | set(pre_cols)), sorted(keep_cols | set(recovery_cols))


def filter_analysis_subset(
    df: pd.DataFrame,
    metric: str | None = None,
    code_id: str | None = None,
    biome: str | None = None,
    drought_type: str | None = None,
    soil_layer: str | None = None,
) -> pd.DataFrame:
    out = df
    if metric:
        out = out[out["metric"].astype(str) == str(metric)]
    if code_id:
        out = out[out["code_id"].astype(str) == str(code_id)]
    if biome:
        out = out[out["biome"].astype(str) == str(biome)]
    if drought_type:
        out = out[out["drought_type"].astype(str) == str(drought_type)]
    if soil_layer:
        out = out[out["soil_layer"].astype(str) == str(soil_layer)]
    return out.reset_index(drop=True)


def build_merged_tables(
    master: pd.DataFrame,
    era5: pd.DataFrame,
    gleam_sm: pd.DataFrame,
    drought: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    merged = master.merge(era5, on="event_uid", how="left")
    merged = merged.merge(gleam_sm, on="event_uid", how="left")
    merged = merged.merge(drought, on="event_uid", how="left")

    pre_cols, recovery_cols = split_feature_columns(merged.columns)
    pre_recovery_table = merged[
        [c for c in merged.columns if c not in recovery_cols or c == "event_uid"]
    ].copy()
    recovery_phase_table = merged[
        [c for c in merged.columns if c not in pre_cols or c == "event_uid"]
    ].copy()
    return merged, pre_recovery_table, recovery_phase_table


def default_output_path(prefix: str, args: argparse.Namespace) -> Path:
    parts = [prefix]
    for value in (args.metric, args.code_id, args.biome, args.drought_type, args.soil_layer):
        if value:
            parts.append(str(value))
    return DATA_DIR / ("_".join(parts) + ".parquet")


def main() -> None:
    args = parse_args()
    master = pd.read_parquet(args.master)
    master = filter_analysis_subset(
        master,
        metric=args.metric,
        code_id=args.code_id,
        biome=args.biome,
        drought_type=args.drought_type,
        soil_layer=args.soil_layer,
    )
    era5 = pd.read_parquet(args.era5)
    gleam_sm = pd.read_parquet(args.gleam_sm)
    drought = pd.read_parquet(args.drought)

    merged, pre_recovery_table, recovery_phase_table = build_merged_tables(master, era5, gleam_sm, drought)

    pre_output = (
        Path(args.pre_output)
        if args.pre_output != str(PRE_RECOVERY_TABLE_PATH)
        else default_output_path("feature_table_pre_recovery", args)
    )
    recovery_output = (
        Path(args.recovery_output)
        if args.recovery_output != str(RECOVERY_PHASE_TABLE_PATH)
        else default_output_path("feature_table_recovery_phase", args)
    )
    merged_output = Path(args.merged_output) if args.merged_output else default_output_path("feature_table_merged", args)
    merged_output.parent.mkdir(parents=True, exist_ok=True)
    pre_output.parent.mkdir(parents=True, exist_ok=True)
    recovery_output.parent.mkdir(parents=True, exist_ok=True)

    merged.to_parquet(merged_output, index=False)
    pre_recovery_table.to_parquet(pre_output, index=False)
    recovery_phase_table.to_parquet(recovery_output, index=False)

    print(f"[DONE] merged rows: {len(merged):,}")
    print(f"[DONE] full table: {merged_output}")
    print(f"[DONE] pre table : {pre_output}")
    print(f"[DONE] rec table : {recovery_output}")


if __name__ == "__main__":
    main()
