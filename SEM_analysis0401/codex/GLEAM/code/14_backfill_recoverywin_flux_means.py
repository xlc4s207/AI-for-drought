#!/usr/bin/env python
"""Backfill recovery-window precipitation/evaporation means from existing sums."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from sem_gleam_common import finalize_feature_table


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    df = pd.read_parquet(input_path)
    out = finalize_feature_table(df)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(output_path, index=False)

    added = [
        col
        for col in (
            "recoverywin_total_precipitation_mean",
            "recoverywin_total_evaporation_mean",
        )
        if col in out.columns
    ]
    print(f"[DONE] rows={len(out):,}")
    print(f"[DONE] output={output_path}")
    print(f"[DONE] added_columns={added}")


if __name__ == "__main__":
    main()
