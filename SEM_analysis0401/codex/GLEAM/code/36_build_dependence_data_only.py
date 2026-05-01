#!/usr/bin/env python
"""Build dependence parquet artifacts without rendering dependence PNGs."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

from sem_gleam_common import finalize_feature_table

try:
    import shap  # type: ignore
except Exception as exc:  # pragma: no cover
    raise RuntimeError("This script requires the shap package to be installed.") from exc


SHAP_ANALYSIS_PATH = Path(__file__).with_name("06_shap_analysis.py")
SHAP_ANALYSIS_SPEC = importlib.util.spec_from_file_location("shap_analysis_module", SHAP_ANALYSIS_PATH)
if SHAP_ANALYSIS_SPEC is None or SHAP_ANALYSIS_SPEC.loader is None:  # pragma: no cover
    raise RuntimeError(f"Unable to load helper module from {SHAP_ANALYSIS_PATH}")
shap_analysis_module = importlib.util.module_from_spec(SHAP_ANALYSIS_SPEC)
SHAP_ANALYSIS_SPEC.loader.exec_module(shap_analysis_module)

filter_analysis_subset = shap_analysis_module.filter_analysis_subset
fit_tree_model = shap_analysis_module.fit_tree_model
prepare_model_inputs = shap_analysis_module.prepare_model_inputs
resolve_model_backend = shap_analysis_module.resolve_model_backend
sample_for_shap = shap_analysis_module.sample_for_shap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--metric", required=True)
    parser.add_argument("--code-id", required=True)
    parser.add_argument("--drought-type", required=True)
    parser.add_argument("--soil-layer", required=True)
    parser.add_argument("--feature-scope", required=True)
    parser.add_argument("--target", default="t_recover_to_baseline_abs_peak")
    parser.add_argument("--biomes", nargs="+", required=True)
    parser.add_argument("--include-features", nargs="+", required=True)
    parser.add_argument("--exclude-features", nargs="+", default=[])
    parser.add_argument("--limit", type=int, default=50000)
    parser.add_argument("--model-backend", choices=("lightgbm", "random_forest"), default="random_forest")
    parser.add_argument("--n-estimators", type=int, default=60)
    parser.add_argument("--n-jobs", type=int, default=1)
    parser.add_argument("--shap-sample-size", type=int, default=2500)
    parser.add_argument("--max-missing-rate", type=float, default=0.3)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--event-duration-max", type=float, default=1000.0)
    parser.add_argument("--event-intensity-max", type=float, default=50.0)
    return parser.parse_args()


def filter_plotting_outliers(
    sample: pd.DataFrame,
    shap_df: pd.DataFrame,
    event_duration_max: float,
    event_intensity_max: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    mask = pd.Series(True, index=sample.index)
    if "event_duration" in sample.columns:
        duration = pd.to_numeric(sample["event_duration"], errors="coerce")
        mask &= duration.notna() & (duration <= event_duration_max)
    if "event_intensity" in sample.columns:
        intensity = pd.to_numeric(sample["event_intensity"], errors="coerce")
        mask &= intensity.notna() & (intensity <= event_intensity_max)
    kept_index = sample.index[mask]
    return sample.loc[kept_index].copy(), shap_df.loc[kept_index].copy()


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    backend = resolve_model_backend(args.model_backend)

    df = pd.read_parquet(args.table)
    df = finalize_feature_table(df)

    for biome in args.biomes:
        biome_dir = output_root / biome
        biome_dir.mkdir(parents=True, exist_ok=True)

        sub = filter_analysis_subset(
            df,
            metric=args.metric,
            code_id=args.code_id,
            biome=biome,
            drought_type=args.drought_type,
            soil_layer=args.soil_layer,
        )
        if args.limit and len(sub) > args.limit:
            sub = sub.head(args.limit).copy()

        X, y, _feature_names = prepare_model_inputs(
            sub,
            target=args.target,
            max_missing_rate=args.max_missing_rate,
            feature_scope=args.feature_scope,
            include_features=args.include_features,
            exclude_features=args.exclude_features,
        )

        model = fit_tree_model(
            X,
            y,
            backend=backend,
            random_state=args.random_state,
            n_estimators=args.n_estimators,
            n_jobs=args.n_jobs,
        )
        sample = sample_for_shap(X, sample_size=args.shap_sample_size, random_state=args.random_state)
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(sample)
        if isinstance(shap_values, list):
            shap_values = shap_values[0]
        shap_df = pd.DataFrame(np.asarray(shap_values), columns=sample.columns, index=sample.index)
        raw_sample_rows = len(sample)
        sample, shap_df = filter_plotting_outliers(
            sample,
            shap_df,
            event_duration_max=args.event_duration_max,
            event_intensity_max=args.event_intensity_max,
        )

        sample.to_parquet(biome_dir / "dependence_sample_features.parquet", index=True)
        shap_df.to_parquet(biome_dir / "dependence_sample_shap_values.parquet", index=True)
        merged = sample.add_prefix("feature__").join(shap_df.add_prefix("shap__"), how="left")
        merged.to_parquet(biome_dir / "dependence_plot_data.parquet", index=True)

        summary_lines = [
            "dependence data only",
            f"biome={biome}",
            f"filtered_rows={len(sub)}",
            f"rows_before_plot_filter={raw_sample_rows}",
            f"rows={len(sample)}",
            f"plot_filter_removed={raw_sample_rows - len(sample)}",
            f"model_backend={backend}",
            f"n_estimators={args.n_estimators}",
            f"n_jobs={args.n_jobs}",
            f"shap_sample_size={args.shap_sample_size}",
            f"sample_features_path={biome_dir / 'dependence_sample_features.parquet'}",
            f"sample_shap_path={biome_dir / 'dependence_sample_shap_values.parquet'}",
            f"plot_data_path={biome_dir / 'dependence_plot_data.parquet'}",
        ]
        (biome_dir / "dependence_plots_summary.txt").write_text("\n".join(summary_lines), encoding="utf-8")
        print(f"[DONE] dependence-data biome={biome}")


if __name__ == "__main__":
    main()
