#!/usr/bin/env python
"""Backfill SHAP dependence parquet artifacts with projected-column reads."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import shap  # type: ignore
except Exception as exc:  # pragma: no cover
    raise RuntimeError("This script requires the shap package to be installed.") from exc

try:
    from lightgbm import LGBMRegressor  # type: ignore
except Exception:  # pragma: no cover
    LGBMRegressor = None

from sklearn.ensemble import RandomForestRegressor


DEFAULT_FILTER_COLUMNS = ["metric", "code_id", "biome", "drought_type", "soil_layer"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--metric", required=True)
    parser.add_argument("--code-id", required=True)
    parser.add_argument("--drought-type", required=True)
    parser.add_argument("--soil-layer", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--biomes", nargs="+", required=True)
    parser.add_argument("--include-features", nargs="+", required=True)
    parser.add_argument("--extra-columns", nargs="+", default=[])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--shap-sample-size", type=int, default=2500)
    parser.add_argument("--model-backend", choices=("lightgbm", "random_forest"), default="lightgbm")
    parser.add_argument("--n-estimators", type=int, default=120)
    parser.add_argument("--n-jobs", type=int, default=-1)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def build_read_columns(
    target: str,
    include_features: list[str],
    extra_columns: list[str] | None = None,
) -> list[str]:
    ordered: list[str] = []
    for name in [*DEFAULT_FILTER_COLUMNS, target, *(include_features or []), *((extra_columns or []))]:
        if name not in ordered:
            ordered.append(name)
    return ordered


def prepare_model_frame(
    df: pd.DataFrame,
    biome: str,
    metric: str,
    code_id: str,
    drought_type: str,
    soil_layer: str,
    target: str,
    include_features: list[str],
    limit: int | None,
) -> tuple[pd.DataFrame, pd.Series]:
    sub = df[
        (df["metric"].astype(str) == str(metric))
        & (df["code_id"].astype(str) == str(code_id))
        & (df["biome"].astype(str) == str(biome))
        & (df["drought_type"].astype(str) == str(drought_type))
        & (df["soil_layer"].astype(str) == str(soil_layer))
    ].copy()
    if limit and len(sub) > limit:
        sub = sub.head(limit).copy()

    sub[target] = pd.to_numeric(sub[target], errors="coerce")
    sub = sub[sub[target].notna()].copy()
    if sub.empty:
        raise ValueError(f"No usable rows remain for biome={biome}")

    features = sub[include_features].apply(pd.to_numeric, errors="coerce")
    features = features.loc[:, features.notna().sum(axis=0) > 0].copy()
    if features.empty:
        raise ValueError(f"No usable feature columns remain for biome={biome}")

    for col in features.columns:
        features[col] = features[col].fillna(features[col].median())
    features = features.loc[:, features.nunique(dropna=True) > 1].astype(np.float32)
    if features.empty:
        raise ValueError(f"All feature columns became constant for biome={biome}")

    target_series = sub.loc[features.index, target].astype(np.float32)
    return features, target_series


def fit_model(
    features: pd.DataFrame,
    target: pd.Series,
    backend: str,
    n_estimators: int,
    n_jobs: int,
    random_state: int,
):
    if backend == "lightgbm":
        if LGBMRegressor is None:
            raise ImportError("lightgbm is not available but was requested.")
        model = LGBMRegressor(
            objective="regression",
            n_estimators=n_estimators,
            learning_rate=0.05,
            num_leaves=31,
            min_child_samples=20,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=random_state,
            n_jobs=n_jobs,
            verbosity=-1,
        )
    else:
        model = RandomForestRegressor(
            n_estimators=min(n_estimators, 400),
            random_state=random_state,
            n_jobs=n_jobs,
            min_samples_leaf=2,
        )
    model.fit(features, target)
    return model


def write_dependence_artifacts(output_dir: Path, sample: pd.DataFrame, shap_df: pd.DataFrame) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    sample.to_parquet(output_dir / "dependence_sample_features.parquet", index=True)
    shap_df.to_parquet(output_dir / "dependence_sample_shap_values.parquet", index=True)
    merged = sample.add_prefix("feature__").join(shap_df.add_prefix("shap__"), how="left")
    merged.to_parquet(output_dir / "dependence_plot_data.parquet", index=True)


def main() -> None:
    args = parse_args()
    include_features = [str(name) for name in args.include_features]
    read_columns = build_read_columns(
        target=args.target,
        include_features=include_features,
        extra_columns=[str(name) for name in args.extra_columns],
    )
    df = pd.read_parquet(args.table, columns=read_columns)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, object]] = []
    for biome in args.biomes:
        features, target = prepare_model_frame(
            df=df,
            biome=str(biome),
            metric=args.metric,
            code_id=args.code_id,
            drought_type=args.drought_type,
            soil_layer=args.soil_layer,
            target=args.target,
            include_features=include_features,
            limit=args.limit,
        )
        model = fit_model(
            features=features,
            target=target,
            backend=args.model_backend,
            n_estimators=args.n_estimators,
            n_jobs=args.n_jobs,
            random_state=args.random_state,
        )
        sample_size = min(len(features), int(args.shap_sample_size))
        sample = features.sample(n=sample_size, random_state=args.random_state).copy()
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(sample)
        if isinstance(shap_values, list):
            shap_values = shap_values[0]
        shap_df = pd.DataFrame(np.asarray(shap_values), columns=sample.columns, index=sample.index)
        write_dependence_artifacts(output_root / str(biome), sample, shap_df)
        summary_rows.append(
            {
                "biome": str(biome),
                "rows": int(len(features)),
                "sample_rows": int(len(sample)),
                "feature_count": int(len(sample.columns)),
                "features": ",".join(sample.columns.tolist()),
            }
        )

    pd.DataFrame(summary_rows).to_csv(output_root / "dependence_artifact_backfill_summary.csv", index=False)


if __name__ == "__main__":
    main()
