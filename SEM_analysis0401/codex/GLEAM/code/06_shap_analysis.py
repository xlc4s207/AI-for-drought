#!/usr/bin/env python
"""Runnable feature-importance analysis for the GLEAM recovery-time tables."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

from sem_gleam_common import RESULTS_DIR, column_allowed_by_scope, finalize_feature_table, normalize_feature_scope

try:
    import shap  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    shap = None

try:
    from lightgbm import LGBMRegressor  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    LGBMRegressor = None

META_COLUMNS = {
    "event_uid",
    "metric",
    "code_id",
    "biome",
    "soil_layer",
    "drought_type",
    "lat",
    "lon",
    "event_id",
    "onset_year",
    "onset_doy",
    "drought_start_year",
    "drought_start_doy",
    "onset_start_date",
    "drought_start_date",
}

LEAKAGE_COLUMNS = {
    "actual_window_after",
    "lu_event_valid",
    "response_detected",
    "t_response_onset_start",
    "t_response_drought_start",
    "t_peak",
    "t_peak_abs",
    "t_peak_drought_start",
    "t_peak_abs_drought_start",
    "t_impact",
    "amp_max",
    "legacy_duration",
    "t_recover_to_baseline",
    "t_recover_to_baseline_abs_peak",
    "t_recover_onset_start",
    "t_recover_drought_start",
    "t_recover_post_drought",
    "recovery_rate_to_baseline",
}

LEAKAGE_PREFIXES = (
    "flux_",
    "gpp_",
    "nee_",
    "reco_",
)

LEAKAGE_SUBSTRINGS = (
    "recover",
    "response",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--target", default="t_recover_to_baseline_abs_peak")
    parser.add_argument(
        "--feature-scope",
        choices=("predictive", "prepeak_event", "shock_event", "process", "process_recoverywin", "all"),
        default="process",
    )
    parser.add_argument("--output-dir", default=str(RESULTS_DIR / "shap"))
    parser.add_argument("--metric", default=None)
    parser.add_argument("--code-id", default=None)
    parser.add_argument("--biome", default=None)
    parser.add_argument("--drought-type", default=None)
    parser.add_argument("--soil-layer", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-missing-rate", type=float, default=0.3)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--model-backend", choices=("auto", "lightgbm", "random_forest"), default="auto")
    parser.add_argument("--shap-sample-size", nargs="+", type=int, default=[5000])
    parser.add_argument("--include-features", nargs="+", default=None)
    parser.add_argument("--exclude-features", nargs="+", default=[])
    parser.add_argument("--n-estimators", type=int, default=500)
    parser.add_argument("--n-jobs", type=int, default=-1)
    return parser.parse_args()


def filter_analysis_subset(
    df: pd.DataFrame,
    metric: str | None = None,
    code_id: str | None = None,
    biome: str | None = None,
    drought_type: str | None = None,
    soil_layer: str | None = None,
) -> pd.DataFrame:
    out = df
    if metric:
        out = out[out["metric"].astype(str) == str(metric)]
    if code_id:
        out = out[out["code_id"].astype(str) == str(code_id)]
    if biome:
        out = out[out["biome"].astype(str) == str(biome)]
    if drought_type:
        out = out[out["drought_type"].astype(str) == str(drought_type)]
    if soil_layer:
        out = out[out["soil_layer"].astype(str) == str(soil_layer)]
    return out.reset_index(drop=True)


def prepare_model_inputs(
    df: pd.DataFrame,
    target: str,
    max_missing_rate: float = 0.3,
    feature_scope: str = "all",
    include_features: Sequence[str] | None = None,
    exclude_features: Sequence[str] | None = None,
) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    work = df.copy()
    feature_scope = normalize_feature_scope(feature_scope)
    work[target] = pd.to_numeric(work[target], errors="coerce")
    work = work[work[target].notna()].reset_index(drop=True)

    feature_names: list[str] = []
    for col in work.columns:
        if col == target or col in META_COLUMNS:
            continue
        if not column_allowed_by_scope(col, feature_scope):
            continue
        if col in LEAKAGE_COLUMNS:
            continue
        if col.startswith(LEAKAGE_PREFIXES):
            continue
        # `recoverywin_` is a valid process-stage feature prefix, not a target leakage field.
        if not col.startswith("recoverywin_") and any(token in col.lower() for token in LEAKAGE_SUBSTRINGS):
            continue
        if not pd.api.types.is_numeric_dtype(work[col]):
            continue
        series = pd.to_numeric(work[col], errors="coerce")
        if series.isna().mean() > max_missing_rate:
            continue
        if series.nunique(dropna=True) <= 1:
            continue
        feature_names.append(col)

    feature_names = filter_feature_names(
        feature_names,
        include_features=include_features,
        exclude_features=exclude_features,
    )
    if not feature_names:
        raise ValueError("No usable numeric features remained after explicit feature filtering.")

    X = work[feature_names].apply(pd.to_numeric, errors="coerce")
    X = X.fillna(X.median(numeric_only=True))
    X = X.loc[:, X.nunique(dropna=True) > 1].astype(np.float32)
    feature_names = X.columns.tolist()
    y = work[target].astype(np.float32)
    return X, y, feature_names


def filter_feature_names(
    feature_names: Sequence[str],
    include_features: Sequence[str] | None = None,
    exclude_features: Sequence[str] | None = None,
) -> list[str]:
    exclude_set = {str(name) for name in (exclude_features or [])}
    if include_features:
        available = {str(name) for name in feature_names}
        filtered = [str(name) for name in include_features if str(name) in available and str(name) not in exclude_set]
        return filtered
    return [str(name) for name in feature_names if str(name) not in exclude_set]


def resolve_model_backend(requested_backend: str = "auto") -> str:
    if requested_backend == "auto":
        return "lightgbm" if LGBMRegressor is not None else "random_forest"
    if requested_backend == "lightgbm" and LGBMRegressor is None:
        raise ImportError("lightgbm is not available but --model-backend=lightgbm was requested.")
    return requested_backend


def fit_tree_model(
    X: pd.DataFrame,
    y: pd.Series,
    backend: str,
    random_state: int = 42,
    n_estimators: int = 500,
    n_jobs: int = -1,
):
    if backend == "lightgbm":
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
    elif backend == "random_forest":
        model = RandomForestRegressor(
            n_estimators=min(n_estimators, 400),
            random_state=random_state,
            n_jobs=n_jobs,
            min_samples_leaf=2,
        )
    else:  # pragma: no cover - guarded by argparse + resolve_model_backend
        raise ValueError(f"Unsupported model backend: {backend}")
    model.fit(X, y)
    return model


def compute_split_r2(
    X: pd.DataFrame,
    y: pd.Series,
    backend: str,
    random_state: int = 42,
    n_estimators: int = 500,
    n_jobs: int = -1,
) -> dict[str, float | int]:
    if len(X) < 5:
        return {
            "r2_train_split": np.nan,
            "r2_holdout_split": np.nan,
            "split_train_rows": len(X),
            "split_test_rows": 0,
        }
    test_size = max(1, int(round(len(X) * 0.2)))
    test_size = min(test_size, len(X) - 1)
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
    )
    model = fit_tree_model(
        X_train,
        y_train,
        backend=backend,
        random_state=random_state,
        n_estimators=n_estimators,
        n_jobs=n_jobs,
    )
    return {
        "r2_train_split": float(model.score(X_train, y_train)),
        "r2_holdout_split": float(model.score(X_test, y_test)),
        "split_train_rows": int(len(X_train)),
        "split_test_rows": int(len(X_test)),
    }


def sample_for_shap(
    X: pd.DataFrame,
    sample_size: int,
    random_state: int = 42,
) -> pd.DataFrame:
    if sample_size <= 0 or len(X) <= sample_size:
        return X.copy()
    return X.sample(n=sample_size, random_state=random_state).sort_index()


def compute_feature_importance(
    model,
    X: pd.DataFrame,
    backend: str,
    shap_sample_size: int = 5000,
    random_state: int = 42,
) -> tuple[pd.DataFrame, str, int, pd.DataFrame | None, np.ndarray | None]:
    sample: pd.DataFrame | None = None
    shap_array: np.ndarray | None = None
    if shap is not None:
        explainer = shap.TreeExplainer(model)
        sample = sample_for_shap(X, sample_size=shap_sample_size, random_state=random_state)
        shap_values = explainer.shap_values(sample)
        if isinstance(shap_values, list):
            shap_values = shap_values[0]
        shap_array = np.asarray(shap_values)
        importance = np.abs(shap_array).mean(axis=0)
        table = pd.DataFrame({"feature": sample.columns, "importance": importance})
        method = f"tree_shap_mean_abs:{backend}"
    else:
        raw_importance = getattr(model, "feature_importances_", None)
        if raw_importance is None:
            raise RuntimeError("SHAP is unavailable and the selected model does not expose feature_importances_.")
        table = pd.DataFrame(
            {
                "feature": X.columns,
                "importance": np.asarray(raw_importance, dtype=float),
            }
        )
        method = f"native_feature_importance:{backend}"
    table = table.sort_values("importance", ascending=False).reset_index(drop=True)
    table["rank"] = np.arange(1, len(table) + 1)
    return table, method, len(sample) if sample is not None else len(X), sample, shap_array


def save_importance_plot(importance_df: pd.DataFrame, output_path: Path, top_k: int = 20) -> None:
    top = importance_df.head(top_k).iloc[::-1]
    plt.figure(figsize=(8, max(4, len(top) * 0.35)))
    plt.barh(top["feature"], top["importance"], color="#2f6b8a")
    plt.xlabel("Importance")
    plt.ylabel("Feature")
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=200)
    plt.close()


def save_beeswarm_plot(
    shap_values: np.ndarray,
    sample: pd.DataFrame,
    output_path: Path,
    top_k: int = 20,
) -> None:
    if shap is None:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(8, max(4, min(top_k, sample.shape[1]) * 0.35)))
    shap.summary_plot(shap_values, sample, show=False, max_display=top_k)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def resolve_sample_output_dir(output_dir: Path, sample_size: int, all_sample_sizes: Sequence[int]) -> Path:
    unique_sizes = sorted({int(size) for size in all_sample_sizes})
    if len(unique_sizes) <= 1:
        return output_dir
    return output_dir / f"sample_{sample_size}"


def main() -> None:
    args = parse_args()
    df = pd.read_parquet(args.table)
    df = finalize_feature_table(df)
    df = filter_analysis_subset(
        df,
        metric=args.metric,
        code_id=args.code_id,
        biome=args.biome,
        drought_type=args.drought_type,
        soil_layer=args.soil_layer,
    )
    if args.limit:
        df = df.head(args.limit).copy()

    X, y, feature_names = prepare_model_inputs(
        df,
        target=args.target,
        max_missing_rate=args.max_missing_rate,
        feature_scope=args.feature_scope,
        include_features=args.include_features,
        exclude_features=args.exclude_features,
    )
    if X.empty or len(feature_names) == 0:
        raise ValueError("No usable numeric features were available for model fitting.")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    backend = resolve_model_backend(args.model_backend)
    split_metrics = compute_split_r2(
        X,
        y,
        backend=backend,
        random_state=args.random_state,
        n_estimators=args.n_estimators,
        n_jobs=args.n_jobs,
    )
    model = fit_tree_model(
        X,
        y,
        backend=backend,
        random_state=args.random_state,
        n_estimators=args.n_estimators,
        n_jobs=args.n_jobs,
    )
    sample_sizes = [int(size) for size in args.shap_sample_size]
    for sample_size in sample_sizes:
        current_output_dir = resolve_sample_output_dir(output_dir, sample_size, sample_sizes)
        current_output_dir.mkdir(parents=True, exist_ok=True)
        importance_df, method, shap_rows, sample, shap_values = compute_feature_importance(
            model,
            X,
            backend=backend,
            shap_sample_size=sample_size,
            random_state=args.random_state,
        )
        importance_path = current_output_dir / "feature_importance.csv"
        importance_df.to_csv(importance_path, index=False)
        plot_path = current_output_dir / "feature_importance_topk.png"
        save_importance_plot(importance_df, plot_path, top_k=args.top_k)
        beeswarm_path = current_output_dir / "feature_importance_beeswarm.png"
        if shap_values is not None and sample is not None:
            save_beeswarm_plot(shap_values, sample, beeswarm_path, top_k=args.top_k)
        summary_path = current_output_dir / "run_summary.txt"
        summary_path.write_text(
            "\n".join(
                [
                    "GLEAM feature-importance analysis",
                    f"rows={len(df)}",
                    f"model_rows={len(X)}",
                    f"target={args.target}",
                    f"feature_scope={args.feature_scope}",
                    f"feature_count={len(feature_names)}",
                    f"model_backend={backend}",
                    f"n_estimators={args.n_estimators}",
                    f"n_jobs={args.n_jobs}",
                    f"importance_method={method}",
                    f"shap_available={shap is not None}",
                    f"shap_sample_rows={shap_rows}",
                    f"shap_sample_size_arg={sample_size}",
                    f"r2_train_split={split_metrics['r2_train_split']}",
                    f"r2_holdout_split={split_metrics['r2_holdout_split']}",
                    f"split_train_rows={split_metrics['split_train_rows']}",
                    f"split_test_rows={split_metrics['split_test_rows']}",
                    f"include_features={','.join(args.include_features) if args.include_features else ''}",
                    f"exclude_features={','.join(args.exclude_features) if args.exclude_features else ''}",
                    f"beeswarm_path={beeswarm_path}",
                    f"metric={args.metric}",
                    f"code_id={args.code_id}",
                    f"biome={args.biome}",
                    f"drought_type={args.drought_type}",
                    f"soil_layer={args.soil_layer}",
                ]
            ),
            encoding="utf-8",
        )
        print(f"[DONE] summary saved to {summary_path}")


if __name__ == "__main__":
    main()
