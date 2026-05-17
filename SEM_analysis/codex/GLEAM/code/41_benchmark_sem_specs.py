#!/usr/bin/env python
"""Lightweight SEM spec benchmark focused on target-equation holdout R2.

This script reuses the same dataset preparation logic as 07_sem_analysis.py,
but skips full SEM fitting so we can quickly compare alternative path specs
that preserve indirect-effect chains while changing target-equation coverage.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import pandas as pd


def load_sem_module(script_path: Path):
    spec = importlib.util.spec_from_file_location("sem_analysis_mod", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load SEM module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_spec_arg(raw: str) -> tuple[str, Path]:
    if "=" not in raw:
        raise ValueError(f"Invalid --spec value {raw!r}; expected label=/abs/path/to/spec.txt")
    label, path_str = raw.split("=", 1)
    label = label.strip()
    path = Path(path_str.strip()).expanduser().resolve()
    if not label:
        raise ValueError(f"Invalid --spec value {raw!r}; label is empty")
    if not path.exists():
        raise FileNotFoundError(f"Spec file not found: {path}")
    return label, path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sem-script", required=True)
    parser.add_argument("--table", required=True)
    parser.add_argument("--shap-root", required=True)
    parser.add_argument("--feature-scope", required=True)
    parser.add_argument("--metric", required=True)
    parser.add_argument("--code-id", required=True)
    parser.add_argument("--drought-type", default="flash")
    parser.add_argument("--soil-layer", required=True)
    parser.add_argument("--target", default="t_recover_to_baseline_abs_peak")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--max-missing-rate", type=float, default=0.3)
    parser.add_argument("--min-rows", type=int, default=200)
    parser.add_argument("--target-min-days", type=float, default=None)
    parser.add_argument("--target-max-days", type=float, default=None)
    parser.add_argument("--target-residual-offset", type=float, default=0.0)
    parser.add_argument("--biomes", nargs="+", required=True)
    parser.add_argument("--spec", dest="specs", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sem_mod = load_sem_module(Path(args.sem_script).resolve())

    df = pd.read_parquet(args.table)
    df = sem_mod.finalize_feature_table(df)

    parsed_specs = [parse_spec_arg(raw) for raw in args.specs]
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []

    for biome in args.biomes:
        biome_df = sem_mod.filter_analysis_subset(
            df,
            metric=args.metric,
            code_id=args.code_id,
            biome=biome,
            drought_type=args.drought_type,
            soil_layer=args.soil_layer,
        )
        shap_dir = Path(args.shap_root).resolve() / biome
        top_features = sem_mod.load_top_features(str(shap_dir), top_k=args.top_k)

        for spec_label, spec_path in parsed_specs:
            model_spec_text = sem_mod.read_model_spec_text(str(spec_path))
            model_spec_text = sem_mod.validate_model_spec_scope(
                model_spec_text=model_spec_text,
                feature_scope=args.feature_scope,
                target=args.target,
            )
            candidate_features = sem_mod.resolve_candidate_features_for_sem(
                top_features,
                model_spec_text=model_spec_text,
                target=args.target,
            )
            dataset = sem_mod.prepare_sem_dataset(
                biome_df,
                target=args.target,
                candidate_features=candidate_features,
                max_missing_rate=args.max_missing_rate,
                min_rows=args.min_rows,
                feature_scope=args.feature_scope,
                target_min_days=args.target_min_days,
                target_max_days=args.target_max_days,
                target_residual_offset=args.target_residual_offset,
            )
            model_spec_text = sem_mod.validate_sem_model_spec(model_spec_text, dataset.columns.tolist())
            metrics = sem_mod.compute_target_equation_r2(dataset, model_spec_text, target=args.target)
            rows.append(
                {
                    "biome": biome,
                    "spec_label": spec_label,
                    "spec_file": str(spec_path),
                    "rows": len(dataset),
                    "feature_count": max(0, len(dataset.columns) - 1),
                    **metrics,
                }
            )

    detail = pd.DataFrame(rows)
    detail = detail.sort_values(["biome", "target_equation_r2_holdout_split"], ascending=[True, False]).reset_index(
        drop=True
    )
    detail_path = output_dir / "benchmark_detail.csv"
    detail.to_csv(detail_path, index=False)

    summary = (
        detail.groupby("spec_label", as_index=False)
        .agg(
            biome_count=("biome", "nunique"),
            mean_holdout_r2=("target_equation_r2_holdout_split", "mean"),
            median_holdout_r2=("target_equation_r2_holdout_split", "median"),
            min_holdout_r2=("target_equation_r2_holdout_split", "min"),
            max_holdout_r2=("target_equation_r2_holdout_split", "max"),
            mean_train_r2=("target_equation_r2_train_split", "mean"),
            predictor_count=("target_equation_predictor_count", "median"),
        )
        .sort_values("mean_holdout_r2", ascending=False)
        .reset_index(drop=True)
    )
    summary_path = output_dir / "benchmark_summary.csv"
    summary.to_csv(summary_path, index=False)

    best_by_biome = (
        detail.sort_values(["biome", "target_equation_r2_holdout_split"], ascending=[True, False])
        .groupby("biome", as_index=False)
        .first()
    )
    best_by_biome_path = output_dir / "best_spec_by_biome.csv"
    best_by_biome.to_csv(best_by_biome_path, index=False)

    print(f"[DONE] detail={detail_path}")
    print(f"[DONE] summary={summary_path}")
    print(f"[DONE] best_by_biome={best_by_biome_path}")


if __name__ == "__main__":
    main()
