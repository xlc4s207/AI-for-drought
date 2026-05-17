#!/usr/bin/env python3
"""Run PDP validation for average model-response trends."""

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
    parser.add_argument("--eval-rows", type=int, default=5000)
    parser.add_argument("--n-estimators", type=int, default=260)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def compute_pdp(model, X: pd.DataFrame, feature: str, grid_size: int, eval_rows: int, random_state: int) -> pd.DataFrame:
    grid = quantile_grid(X[feature], grid_size=grid_size)
    if len(grid) < 2:
        return pd.DataFrame()
    eval_X = X.sample(n=min(eval_rows, len(X)), random_state=random_state).copy()
    baseline = float(np.nanmean(model.predict(eval_X)))
    rows = []
    for value in grid:
        X_mod = eval_X.copy()
        X_mod[feature] = value
        preds = model.predict(X_mod)
        rows.append(
            {
                "feature_value": float(value),
                "prediction_mean": float(np.nanmean(preds)),
                "prediction_std": float(np.nanstd(preds)),
                "centered_effect": float(np.nanmean(preds) - baseline),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    out_root = VALIDATION_ROOT / "03_PDP"
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
                pdp_df = compute_pdp(
                    bundle.model,
                    bundle.X_test,
                    feature,
                    grid_size=args.grid_size,
                    eval_rows=args.eval_rows,
                    random_state=args.random_state,
                )
                if pdp_df.empty:
                    continue
                sub = out_root / "results" / metric / biome
                csv_path = sub / f"{short_label(feature)}_pdp_curve.csv"
                png_path = sub / f"{short_label(feature)}_pdp_curve.png"
                csv_path.parent.mkdir(parents=True, exist_ok=True)
                pdp_df.to_csv(csv_path, index=False)
                save_curve_plot(
                    png_path,
                    pdp_df["feature_value"].to_numpy(dtype=float),
                    pdp_df["centered_effect"].to_numpy(dtype=float),
                    feature,
                    f"{metric} | {biome} | {short_label(feature)} PDP",
                    "Centered mean prediction",
                )
                rows.append(
                    {
                        "metric": metric,
                        "biome": biome,
                        "feature": feature,
                        "label": short_label(feature),
                        "csv": str(csv_path),
                        "png": str(png_path),
                        "pdp_min": float(pdp_df["centered_effect"].min()),
                        "pdp_max": float(pdp_df["centered_effect"].max()),
                        "grid_points": len(pdp_df),
                    }
                )
    pd.DataFrame(rows).to_csv(out_root / "pdp_validation_index.csv", index=False)
    pd.DataFrame(model_rows).to_csv(out_root / "model_fit_summary.csv", index=False)
    write_readme(
        out_root / "README.md",
        [
            "# PDP validation",
            "Purpose: provide average model-response trends as an intuitive supplement to ALE and SHAP.",
            "Default scope: GPP/RECO x five biomes x SHAP top-5 features.",
            "PDP is reported as centered mean prediction relative to the evaluation-sample baseline.",
            "Outputs: per-feature PDP CSV, PNG plots, model_fit_summary.csv, pdp_validation_index.csv.",
        ],
    )


if __name__ == "__main__":
    main()
