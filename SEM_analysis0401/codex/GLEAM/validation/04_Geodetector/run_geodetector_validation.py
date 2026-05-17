#!/usr/bin/env python3
"""Run Geodetector validation for spatial stratified heterogeneity."""

from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_validation import (  # noqa: E402
    BIOMES,
    FEATURES,
    METRICS,
    TARGET,
    VALIDATION_ROOT,
    load_metric_biome_frame,
    short_label,
    top_features,
    write_readme,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-rows", type=int, default=80000)
    parser.add_argument("--bins", type=int, default=6)
    parser.add_argument("--top-n-interactions", type=int, default=5)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def discretize(series: pd.Series, bins: int) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    try:
        return pd.qcut(values, q=bins, duplicates="drop").astype(str)
    except ValueError:
        return pd.cut(values, bins=bins, duplicates="drop").astype(str)


def q_statistic(y: pd.Series, strata: pd.Series) -> tuple[float, int]:
    df = pd.DataFrame({"y": pd.to_numeric(y, errors="coerce"), "strata": strata}).dropna()
    df = df[df["strata"] != "nan"]
    n = len(df)
    if n < 3:
        return np.nan, 0
    total_var = float(df["y"].var(ddof=0))
    if not np.isfinite(total_var) or total_var <= 0:
        return np.nan, int(df["strata"].nunique())
    within = 0.0
    for _, group in df.groupby("strata", observed=False):
        within += len(group) * float(group["y"].var(ddof=0))
    q = 1.0 - within / (n * total_var)
    return float(max(0.0, min(1.0, q))), int(df["strata"].nunique())


def risk_table(y: pd.Series, strata: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame({"y": pd.to_numeric(y, errors="coerce"), "strata": strata}).dropna()
    df = df[df["strata"] != "nan"]
    return (
        df.groupby("strata", observed=False)["y"]
        .agg(["count", "mean", "median", "std"])
        .reset_index()
        .rename(columns={"mean": "target_mean", "median": "target_median", "std": "target_std"})
    )


def main() -> None:
    args = parse_args()
    out_root = VALIDATION_ROOT / "04_Geodetector"
    q_rows = []
    interaction_rows = []
    risk_paths = []
    for metric in METRICS:
        for biome in BIOMES:
            df = load_metric_biome_frame(metric, biome)
            cols = [c for c in FEATURES if c in df.columns]
            frame = df[cols + [TARGET]].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
            frame = frame.dropna(axis=0, how="any")
            if args.max_rows > 0 and len(frame) > args.max_rows:
                frame = frame.sample(n=args.max_rows, random_state=args.random_state).sort_index()
            strata_cache = {feature: discretize(frame[feature], bins=args.bins) for feature in cols}
            sub = out_root / "results" / metric / biome
            sub.mkdir(parents=True, exist_ok=True)
            for feature in cols:
                q, strata_count = q_statistic(frame[TARGET], strata_cache[feature])
                risk = risk_table(frame[TARGET], strata_cache[feature])
                risk_path = sub / f"{short_label(feature)}_risk_detector.csv"
                risk.to_csv(risk_path, index=False)
                risk_paths.append(str(risk_path))
                q_rows.append(
                    {
                        "metric": metric,
                        "biome": biome,
                        "feature": feature,
                        "label": short_label(feature),
                        "q": q,
                        "strata_count": strata_count,
                        "rows": len(frame),
                        "risk_csv": str(risk_path),
                    }
                )
            interaction_features = [f for f in top_features(metric, biome, args.top_n_interactions) if f in cols]
            for f1, f2 in itertools.combinations(interaction_features, 2):
                s = strata_cache[f1].astype(str) + " | " + strata_cache[f2].astype(str)
                q_inter, strata_count = q_statistic(frame[TARGET], s)
                q1, _ = q_statistic(frame[TARGET], strata_cache[f1])
                q2, _ = q_statistic(frame[TARGET], strata_cache[f2])
                if q_inter > q1 + q2:
                    relation = "nonlinear_enhance"
                elif q_inter > max(q1, q2):
                    relation = "bi_factor_enhance"
                elif q_inter < min(q1, q2):
                    relation = "weaken"
                else:
                    relation = "independent_or_partial"
                interaction_rows.append(
                    {
                        "metric": metric,
                        "biome": biome,
                        "feature_1": f1,
                        "feature_2": f2,
                        "label_1": short_label(f1),
                        "label_2": short_label(f2),
                        "q_feature_1": q1,
                        "q_feature_2": q2,
                        "q_interaction": q_inter,
                        "interaction_relation": relation,
                        "strata_count": strata_count,
                        "rows": len(frame),
                    }
                )
    q_df = pd.DataFrame(q_rows).sort_values(["metric", "biome", "q"], ascending=[True, True, False])
    inter_df = pd.DataFrame(interaction_rows).sort_values(
        ["metric", "biome", "q_interaction"], ascending=[True, True, False]
    )
    q_df.to_csv(out_root / "geodetector_factor_q.csv", index=False)
    inter_df.to_csv(out_root / "geodetector_interactions.csv", index=False)
    write_readme(
        out_root / "README.md",
        [
            "# Geodetector validation",
            "Purpose: validate whether SHAP-important variables explain spatial stratified heterogeneity in recovery time.",
            "Factor detector: q statistic for each selected prepeak feature within metric-biome subsets.",
            "Interaction detector: pairwise interactions among SHAP top features.",
            "Risk detector: target means by feature strata, saved per metric/biome/feature.",
            "Outputs: geodetector_factor_q.csv, geodetector_interactions.csv, per-feature risk_detector CSV files.",
        ],
    )


if __name__ == "__main__":
    main()
