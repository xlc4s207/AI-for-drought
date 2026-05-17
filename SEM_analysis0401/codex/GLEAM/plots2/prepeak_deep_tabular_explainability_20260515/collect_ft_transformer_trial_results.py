#!/usr/bin/env python3
"""Collect FT-Transformer trial outputs from run_summary.json files."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


OUT = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/plots2/prepeak_deep_tabular_explainability_20260515")


def main() -> None:
    rows = []
    for p in OUT.glob("*/*/*/run_summary.json"):
        try:
            row = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        row["run_summary_path"] = str(p)
        rows.append(row)
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["input_variant", "metric", "biome"]).reset_index(drop=True)
    out = OUT / "ft_transformer_trial_model_summary_collected.csv"
    df.to_csv(out, index=False)
    print(out)
    if not df.empty:
        print(df[["input_variant", "metric", "biome", "rows", "features", "r2_test", "rmse_test", "mae_test", "epochs_run"]].to_csv(index=False))


if __name__ == "__main__":
    main()
