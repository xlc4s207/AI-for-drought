#!/usr/bin/env python
"""Replace selected feature columns in a base table with columns from an override table."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-table", required=True)
    parser.add_argument("--override-table", required=True)
    parser.add_argument("--output-table", required=True)
    parser.add_argument("--match-column", default="event_uid")
    parser.add_argument("--column-substring", default=None)
    parser.add_argument("--columns", nargs="+", default=None)
    return parser.parse_args()


def resolve_override_columns(
    override_df: pd.DataFrame,
    match_column: str,
    columns: list[str] | None = None,
    column_substring: str | None = None,
) -> list[str]:
    selected: list[str] = []
    for col in override_df.columns:
        if col == match_column:
            continue
        if columns and col in columns:
            selected.append(col)
            continue
        if column_substring and column_substring in col:
            selected.append(col)
    if columns:
        missing = [col for col in columns if col not in override_df.columns]
        if missing:
            raise KeyError(f"Override table missing requested columns: {missing}")
    if not selected:
        raise ValueError("No override feature columns were selected.")
    return selected


def main() -> None:
    args = parse_args()
    base_df = pd.read_parquet(Path(args.base_table))
    override_df = pd.read_parquet(Path(args.override_table))

    if args.match_column not in base_df.columns:
        raise KeyError(f"Base table missing match column: {args.match_column}")
    if args.match_column not in override_df.columns:
        raise KeyError(f"Override table missing match column: {args.match_column}")
    if base_df[args.match_column].duplicated().any():
        raise ValueError("Base table contains duplicate match keys.")
    if override_df[args.match_column].duplicated().any():
        raise ValueError("Override table contains duplicate match keys.")

    replace_columns = resolve_override_columns(
        override_df,
        match_column=args.match_column,
        columns=[str(col) for col in args.columns] if args.columns else None,
        column_substring=args.column_substring,
    )
    override_keep = override_df[[args.match_column, *replace_columns]].copy()
    out = base_df.drop(columns=replace_columns, errors="ignore").merge(
        override_keep,
        on=args.match_column,
        how="left",
        validate="one_to_one",
    )

    output_path = Path(args.output_table)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(output_path, index=False)

    print(f"[DONE] rows={len(out):,}")
    print(f"[DONE] replaced_columns={','.join(replace_columns)}")
    print(f"[DONE] output={output_path}")


if __name__ == "__main__":
    main()
