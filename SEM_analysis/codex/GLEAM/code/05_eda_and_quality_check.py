#!/usr/bin/env python
"""EDA and quality checks for the merged SHAP+SEM feature tables."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from sem_gleam_common import DATA_DIR, MASTER_VALID_PATH, RESULTS_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", default=str(MASTER_VALID_PATH))
    parser.add_argument("--era5", default=None)
    parser.add_argument("--gleam-sm", default=None)
    parser.add_argument("--drought", default=None)
    parser.add_argument("--output", default=str(RESULTS_DIR / "eda_quality_report.md"))
    return parser.parse_args()


def maybe_read(path_str):
    return pd.read_parquet(path_str) if path_str else None


def main() -> None:
    args = parse_args()
    master = pd.read_parquet(args.master)
    parts = [master]
    for extra in (maybe_read(args.era5), maybe_read(args.gleam_sm), maybe_read(args.drought)):
        if extra is not None:
            parts.append(extra)

    merged = parts[0]
    for part in parts[1:]:
        merged = merged.merge(part, on="event_uid", how="left")

    lines = [
        "# GLEAM SHAP+SEM EDA 质控报告",
        "",
        f"- 样本量: {len(merged):,}",
        f"- biome 数: {merged['biome'].nunique()}",
        "",
        "## 样本量分布",
        "",
        merged.groupby(["metric", "code_id", "biome"]).size().rename("n").reset_index().to_markdown(index=False),
        "",
        "## 缺失率 Top 50",
        "",
        merged.isna().mean().sort_values(ascending=False).head(50).rename("missing_rate").reset_index().rename(columns={"index": "field"}).to_markdown(index=False),
    ]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"[DONE] saved to {output}")


if __name__ == "__main__":
    main()

