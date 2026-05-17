#!/usr/bin/env python3
"""Run ICE validation for within-biome response heterogeneity."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_validation import (  # noqa: E402
    BIOMES,
    METRICS,
    VALIDATION_ROOT,
    fit_model,
    quantile_grid,
    save_curve_plot,
    short_label,
    top_features,
    write_readme,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-rows", type=int, default=50000)
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--grid-size", type=int, default=25)
    parser.add_argument("--ice-samples", type=int, default=80)
    parser.add_argument("--n-estimators", type=int, default=260)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def compute_ice(model, X: pd.DataFrame, feature: str, grid_size: int, n_samples: int, random_state: int) -> pd.DataFrame:
    grid = quantile_grid(X[feature], grid_size=grid_size)
    if len(grid) < 2:
        return pd.DataFrame()
    sample = X.sample(n=min(n_samples, len(X)), random_state=random_state).copy()
    base = model.predict(sample)
    rows = []
    for sample_pos, (idx, row) in enumerate(sample.iterrows()):
        repeated = pd.DataFrame([row.to_dict()] * len(grid), columns=X.columns)
        repeated[feature] = grid
        preds = model.predict(repeated)
        centered = preds - base[sample_pos]
        for value, pred, effect in zip(grid, preds, centered):
            rows.append(
                {
                    "sample_index": idx,
                    "feature_value": float(value),
                    "prediction": float(pred),
                    "centered_effect": float(effect),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    out_root = VALIDATION_ROOT / "02_ICE"
    rows = []
    model_rows = []
    for metric in METRICS:
        for biome in BIOMES:
            bundle = fit_model(
                metric,
                biome,
                max_rows=args.max_rows,
                random_state=args.random_state,
                n_estimators=args.n_estimators,
            )
            model_rows.append(
                {
                    "metric": metric,
                    "biome": biome,
                    "train_rows": len(bundle.X_train),
                    "test_rows": len(bundle.X_test),
                    "r2_train": bundle.r2_train,
                    "r2_test": bundle.r2_test,
                }
            )
            for feature in top_features(metric, biome, args.top_n):
                ice_df = compute_ice(
                    bundle.model,
                    bundle.X_test,
                    feature,
                    grid_size=args.grid_size,
                    n_samples=args.ice_samples,
                    random_state=args.random_state,
                )
                if ice_df.empty:
                    continue
                sub = out_root / "results" / metric / biome
                csv_path = sub / f"{short_label(feature)}_ice_curves.csv"
                png_path = sub / f"{short_label(feature)}_ice_curves.png"
                csv_path.parent.mkdir(parents=True, exist_ok=True)
                ice_df.to_csv(csv_path, index=False)
                mean_df = ice_df.groupby("feature_value", as_index=False)["centered_effect"].mean()
                lines = [
                    (
                        g["feature_value"].to_numpy(dtype=float),
                        g["centered_effect"].to_numpy(dtype=float),
                    )
                    for _, g in ice_df.groupby("sample_index")
                ]
                save_curve_plot(
                    png_path,
                    mean_df["feature_value"].to_numpy(dtype=float),
                    mean_df["centered_effect"].to_numpy(dtype=float),
                    feature,
                    f"{metric} | {biome} | {short_label(feature)} ICE",
                    "Centered prediction effect",
                    extra_lines=lines,
                )
                final_effects = ice_df.sort_values("feature_value").groupby("sample_index")["centered_effect"].last()
                rows.append(
                    {
                        "metric": metric,
                        "biome": biome,
                        "feature": feature,
                        "label": short_label(feature),
                        "csv": str(csv_path),
                        "png": str(png_path),
                        "ice_samples": int(ice_df["sample_index"].nunique()),
                        "effect_iqr": float(final_effects.quantile(0.75) - final_effects.quantile(0.25)),
                        "effect_std": float(final_effects.std()),
                    }
                )
    pd.DataFrame(rows).to_csv(out_root / "ice_validation_index.csv", index=False)
    pd.DataFrame(model_rows).to_csv(out_root / "model_fit_summary.csv", index=False)
    write_readme(
        out_root / "README.md",
        [
            "# ICE validation",
            "Purpose: check within-biome heterogeneity behind mean SHAP/PDP/ALE responses.",
            "Default scope: GPP/RECO x five biomes x SHAP top-5 features.",
            "Each PNG shows individual centered ICE curves plus the red mean curve.",
            "Outputs: per-feature ICE CSV, PNG plots, model_fit_summary.csv, ice_validation_index.csv.",
        ],
    )


if __name__ == "__main__":
    main()
