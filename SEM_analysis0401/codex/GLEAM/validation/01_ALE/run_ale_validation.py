#!/usr/bin/env python3
"""Run ALE validation for SHAP dependence directions and thresholds."""

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
    save_curve_plot,
    short_label,
    top_features,
    write_readme,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-rows", type=int, default=50000)
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--bins", type=int, default=20)
    parser.add_argument("--n-estimators", type=int, default=260)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def compute_ale(model, X: pd.DataFrame, feature: str, bins: int) -> pd.DataFrame:
    values = X[feature].to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    edges = np.unique(np.nanquantile(finite, np.linspace(0.0, 1.0, bins + 1)))
    if len(edges) < 3:
        return pd.DataFrame()
    effects = []
    centers = []
    counts = []
    for left, right in zip(edges[:-1], edges[1:]):
        if right <= left:
            continue
        if right == edges[-1]:
            mask = (values >= left) & (values <= right)
        else:
            mask = (values >= left) & (values < right)
        if not np.any(mask):
            continue
        X_bin = X.loc[mask].copy()
        X_low = X_bin.copy()
        X_high = X_bin.copy()
        X_low[feature] = left
        X_high[feature] = right
        diff = model.predict(X_high) - model.predict(X_low)
        effects.append(float(np.nanmean(diff)))
        centers.append(float((left + right) / 2.0))
        counts.append(int(mask.sum()))
    if not effects:
        return pd.DataFrame()
    ale = np.cumsum(np.asarray(effects))
    ale = ale - np.average(ale, weights=np.asarray(counts))
    return pd.DataFrame(
        {
            "feature_value": centers,
            "ale": ale,
            "local_effect": effects,
            "bin_count": counts,
        }
    )


def main() -> None:
    args = parse_args()
    out_root = VALIDATION_ROOT / "01_ALE"
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
                ale_df = compute_ale(bundle.model, bundle.X_test, feature, bins=args.bins)
                if ale_df.empty:
                    continue
                sub = out_root / "results" / metric / biome
                csv_path = sub / f"{short_label(feature)}_ale_curve.csv"
                png_path = sub / f"{short_label(feature)}_ale_curve.png"
                csv_path.parent.mkdir(parents=True, exist_ok=True)
                ale_df.to_csv(csv_path, index=False)
                save_curve_plot(
                    png_path,
                    ale_df["feature_value"].to_numpy(dtype=float),
                    ale_df["ale"].to_numpy(dtype=float),
                    feature,
                    f"{metric} | {biome} | {short_label(feature)} ALE",
                    "ALE effect on recovery time",
                )
                rows.append(
                    {
                        "metric": metric,
                        "biome": biome,
                        "feature": feature,
                        "label": short_label(feature),
                        "csv": str(csv_path),
                        "png": str(png_path),
                        "ale_min": float(ale_df["ale"].min()),
                        "ale_max": float(ale_df["ale"].max()),
                        "bins": len(ale_df),
                    }
                )
    pd.DataFrame(rows).to_csv(out_root / "ale_validation_index.csv", index=False)
    pd.DataFrame(model_rows).to_csv(out_root / "model_fit_summary.csv", index=False)
    write_readme(
        out_root / "README.md",
        [
            "# ALE validation",
            "Purpose: validate SHAP dependence directions and thresholds using accumulated local effects.",
            "Default scope: GPP/RECO x five biomes x SHAP top-5 features.",
            "Model: LightGBM regressor retrained from the prepeak feature table for each metric-biome subset.",
            "Outputs: per-feature CSV curves, PNG plots, model_fit_summary.csv, ale_validation_index.csv.",
        ],
    )


if __name__ == "__main__":
    main()
