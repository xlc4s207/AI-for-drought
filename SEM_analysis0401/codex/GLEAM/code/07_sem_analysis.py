#!/usr/bin/env python
"""Biome-specific SEM preparation and fallback path analysis."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split

from sem_gleam_common import RESULTS_DIR, column_allowed_by_scope, finalize_feature_table, normalize_feature_scope

try:
    from semopy import Model  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Model = None

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
    parser.add_argument("--shap-results", required=True)
    parser.add_argument("--model-spec-file", default=None)
    parser.add_argument("--target", default="t_recover_to_baseline_abs_peak")
    parser.add_argument(
        "--feature-scope",
        choices=("predictive", "prepeak_event", "shock_event", "process", "process_recoverywin", "all"),
        default="process",
    )
    parser.add_argument("--metric", default=None)
    parser.add_argument("--code-id", default=None)
    parser.add_argument("--biome", required=True)
    parser.add_argument("--drought-type", default="flash")
    parser.add_argument("--soil-layer", default=None)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--include-features", nargs="+", default=None)
    parser.add_argument("--exclude-features", nargs="+", default=[])
    parser.add_argument("--max-missing-rate", type=float, default=0.3)
    parser.add_argument("--min-rows", type=int, default=200)
    parser.add_argument("--target-min-days", type=float, default=None)
    parser.add_argument("--target-max-days", type=float, default=None)
    parser.add_argument("--target-residual-offset", type=float, default=0.0)
    parser.add_argument("--output-dir", default=str(RESULTS_DIR / "sem" / "by_biome"))
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
    if biome and biome != "None":
        out = out[out["biome"].astype(str) == str(biome)]
    if drought_type:
        out = out[out["drought_type"].astype(str) == str(drought_type)]
    if soil_layer:
        out = out[out["soil_layer"].astype(str) == str(soil_layer)]
    return out.reset_index(drop=True)


def load_top_features(shap_results: str, top_k: int = 8) -> list[str]:
    path = Path(shap_results)
    if path.is_dir():
        path = path / "feature_importance.csv"
    table = pd.read_csv(path)
    if "feature" not in table.columns:
        raise ValueError("SHAP/importance result file must contain a 'feature' column.")
    return table["feature"].dropna().astype(str).head(top_k).tolist()


def read_model_spec_text(model_spec_file: str | None) -> str | None:
    if not model_spec_file:
        return None
    return Path(model_spec_file).read_text(encoding="utf-8")


def normalize_model_spec_text(model_spec_text: str) -> str:
    lines: list[str] = []
    for raw_line in str(model_spec_text).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    if not lines:
        raise ValueError("SEM model spec is empty after removing comments and blank lines.")
    return "\n".join(lines)


def parse_sem_equations(model_spec_text: str) -> list[tuple[str, list[str]]]:
    equations: list[tuple[str, list[str]]] = []
    normalized = normalize_model_spec_text(model_spec_text)
    for line in normalized.splitlines():
        if "=~" in line or "~~" in line:
            raise ValueError(
                "Current codex SEM mechanism workflow supports observed-variable structural equations only; "
                "measurement or covariance operators are not supported here."
            )
        if "~" not in line:
            raise ValueError(f"Invalid SEM equation without '~': {line}")
        lhs, rhs = line.split("~", 1)
        lhs = lhs.strip()
        rhs_terms: list[str] = []
        for raw_term in rhs.split("+"):
            term = raw_term.strip()
            if not term:
                continue
            if "*" in term:
                term = term.split("*")[-1].strip()
            rhs_terms.append(term)
        if not lhs or not rhs_terms:
            raise ValueError(f"Invalid SEM equation: {line}")
        equations.append((lhs, rhs_terms))
    return equations


def extract_sem_variables(model_spec_text: str) -> list[str]:
    variables: list[str] = []
    for lhs, rhs_terms in parse_sem_equations(model_spec_text):
        if lhs not in variables:
            variables.append(lhs)
        for term in rhs_terms:
            if term not in variables:
                variables.append(term)
    return variables


def validate_model_spec_scope(
    model_spec_text: str,
    feature_scope: str,
    target: str,
) -> str:
    normalized = normalize_model_spec_text(model_spec_text)
    scope = normalize_feature_scope(feature_scope)
    invalid: list[str] = []
    for variable in extract_sem_variables(normalized):
        if variable == target:
            continue
        if not column_allowed_by_scope(variable, scope):
            invalid.append(variable)
    if invalid:
        raise ValueError(
            "SEM model spec contains variables outside the requested feature scope "
            f"{scope!r}: {sorted(invalid)}"
        )
    return normalized


def resolve_candidate_features_for_sem(
    top_features: list[str],
    model_spec_text: str | None,
    target: str,
) -> list[str]:
    candidate_features: list[str] = []
    for feature in top_features:
        if feature == target or feature in candidate_features:
            continue
        candidate_features.append(feature)
    if model_spec_text:
        for feature in extract_sem_variables(model_spec_text):
            if feature == target or feature in candidate_features:
                continue
            candidate_features.append(feature)
    return candidate_features


def filter_candidate_features(
    candidate_features: list[str],
    include_features: list[str] | None = None,
    exclude_features: list[str] | None = None,
) -> list[str]:
    exclude_set = {str(name) for name in (exclude_features or [])}
    if include_features:
        available = {str(name) for name in candidate_features}
        return [str(name) for name in include_features if str(name) in available and str(name) not in exclude_set]
    return [str(name) for name in candidate_features if str(name) not in exclude_set]


def prepare_sem_dataset(
    df: pd.DataFrame,
    target: str,
    candidate_features: list[str],
    max_missing_rate: float = 0.3,
    min_rows: int = 200,
    feature_scope: str = "all",
    target_min_days: float | None = None,
    target_max_days: float | None = None,
    target_residual_offset: float = 0.0,
) -> pd.DataFrame:
    work = df.copy()
    feature_scope = normalize_feature_scope(feature_scope)
    work[target] = pd.to_numeric(work[target], errors="coerce")
    work = work[work[target].notna()].reset_index(drop=True)
    work = apply_target_window(
        work,
        target=target,
        target_min_days=target_min_days,
        target_max_days=target_max_days,
        target_residual_offset=target_residual_offset,
    )

    keep_features: list[str] = []
    for col in candidate_features:
        if col not in work.columns or col in META_COLUMNS or col == target:
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
        keep_features.append(col)

    if not keep_features:
        raise ValueError("No SEM candidate features remained after filtering.")

    dataset = work[[target] + keep_features].apply(pd.to_numeric, errors="coerce")
    dataset[keep_features] = dataset[keep_features].fillna(dataset[keep_features].median(numeric_only=True))
    dataset = dataset.dropna(subset=[target]).reset_index(drop=True)
    if len(dataset) < min_rows:
        raise ValueError(f"SEM dataset rows={len(dataset)} is smaller than min_rows={min_rows}.")

    std = dataset.std(ddof=0).replace(0, np.nan)
    dataset = (dataset - dataset.mean()) / std
    dataset = dataset.dropna(axis=1, how="any")
    return dataset


def apply_target_window(
    df: pd.DataFrame,
    target: str,
    target_min_days: float | None = None,
    target_max_days: float | None = None,
    target_residual_offset: float = 0.0,
) -> pd.DataFrame:
    work = df.copy()
    work[target] = pd.to_numeric(work[target], errors="coerce")
    work = work[work[target].notna()].reset_index(drop=True)
    if target_min_days is not None:
        work = work[work[target] > float(target_min_days)].reset_index(drop=True)
    if target_max_days is not None:
        work = work[work[target] <= float(target_max_days)].reset_index(drop=True)
    if target_residual_offset:
        work[target] = work[target] - float(target_residual_offset)
        work = work[work[target].notna() & (work[target] > 0)].reset_index(drop=True)
    return work


def build_sem_model_spec(target: str, features: list[str], model_spec_text: str | None = None) -> str:
    if model_spec_text is not None:
        return normalize_model_spec_text(model_spec_text)
    rhs = " + ".join(features)
    return f"{target} ~ {rhs}"


def validate_sem_model_spec(model_spec_text: str, available_columns: list[str]) -> str:
    available = {str(column) for column in available_columns}
    missing = [feature for feature in extract_sem_variables(model_spec_text) if feature not in available]
    if missing:
        raise ValueError(f"SEM model spec references columns not present in dataset: {missing}")
    return model_spec_text


def fit_sem_or_fallback(
    dataset: pd.DataFrame,
    target: str,
    model_spec: str | None = None,
) -> tuple[pd.DataFrame, str, str]:
    features = [c for c in dataset.columns if c != target]
    spec = build_sem_model_spec(target, features, model_spec_text=model_spec)
    spec = validate_sem_model_spec(spec, dataset.columns.tolist())
    if Model is not None:
        model = Model(spec)
        model.fit(dataset)
        estimates = model.inspect()
        return estimates, "semopy", spec

    rows: list[dict[str, object]] = []
    for lhs, rhs_terms in parse_sem_equations(spec):
        X = dataset[rhs_terms].to_numpy()
        y = dataset[lhs].to_numpy()
        reg = LinearRegression()
        reg.fit(X, y)
        equation_text = f"{lhs} ~ {' + '.join(rhs_terms)}"
        for rhs, coef in zip(rhs_terms, reg.coef_):
            rows.append(
                {
                    "lhs": lhs,
                    "rhs": rhs,
                    "Estimate": float(coef),
                    "abs_estimate": float(abs(coef)),
                    "equation": equation_text,
                }
            )
    coef_df = pd.DataFrame(rows).sort_values(["lhs", "abs_estimate"], ascending=[True, False]).reset_index(drop=True)
    return coef_df, "linear_regression_fallback", spec


def compute_target_equation_r2(
    dataset: pd.DataFrame,
    model_spec: str,
    target: str = "t_recover_to_baseline_abs_peak",
    random_state: int = 42,
) -> dict[str, float | int | str]:
    equations = parse_sem_equations(model_spec)
    lhs, rhs_terms = equations[0]
    for eq_lhs, eq_rhs_terms in equations:
        if eq_lhs == target:
            lhs, rhs_terms = eq_lhs, eq_rhs_terms
            break
    if len(dataset) < 5:
        return {
            "target_equation_lhs": lhs,
            "target_equation_r2_train_split": np.nan,
            "target_equation_r2_holdout_split": np.nan,
            "target_equation_predictor_count": len(rhs_terms),
            "target_equation_train_rows": len(dataset),
            "target_equation_test_rows": 0,
        }
    test_size = max(1, int(round(len(dataset) * 0.2)))
    test_size = min(test_size, len(dataset) - 1)
    X = dataset[rhs_terms]
    y = dataset[lhs]
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
    )
    reg = LinearRegression()
    reg.fit(X_train, y_train)
    return {
        "target_equation_lhs": lhs,
        "target_equation_r2_train_split": float(reg.score(X_train, y_train)),
        "target_equation_r2_holdout_split": float(reg.score(X_test, y_test)),
        "target_equation_predictor_count": len(rhs_terms),
        "target_equation_train_rows": int(len(X_train)),
        "target_equation_test_rows": int(len(X_test)),
    }


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
    model_spec_text = read_model_spec_text(args.model_spec_file)
    if model_spec_text is not None:
        model_spec_text = validate_model_spec_scope(
            model_spec_text=model_spec_text,
            feature_scope=args.feature_scope,
            target=args.target,
        )
    top_features = load_top_features(args.shap_results, top_k=args.top_k)
    candidate_features = resolve_candidate_features_for_sem(
        top_features,
        model_spec_text=model_spec_text,
        target=args.target,
    )
    candidate_features = filter_candidate_features(
        candidate_features,
        include_features=args.include_features,
        exclude_features=args.exclude_features,
    )
    dataset = prepare_sem_dataset(
        df,
        target=args.target,
        candidate_features=candidate_features,
        max_missing_rate=args.max_missing_rate,
        min_rows=args.min_rows,
        feature_scope=args.feature_scope,
        target_min_days=args.target_min_days,
        target_max_days=args.target_max_days,
        target_residual_offset=args.target_residual_offset,
    )
    estimates, backend, spec = fit_sem_or_fallback(dataset, args.target, model_spec=model_spec_text)
    target_r2_metrics = compute_target_equation_r2(dataset, spec, target=args.target)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tag_parts = [p for p in (args.metric, args.code_id, args.biome, args.drought_type, args.soil_layer) if p]
    tag = "_".join(str(p) for p in tag_parts)

    dataset_path = output_dir / f"{tag}_sem_dataset.parquet"
    features_path = output_dir / f"{tag}_selected_features.csv"
    estimates_path = output_dir / f"{tag}_estimates.csv"
    spec_path = output_dir / f"{tag}_model_spec.txt"
    note = output_dir / f"{tag}_sem_summary.txt"

    dataset.to_parquet(dataset_path, index=False)
    pd.DataFrame({"feature": [c for c in dataset.columns if c != args.target]}).to_csv(features_path, index=False)
    estimates.to_csv(estimates_path, index=False)
    spec_path.write_text(spec, encoding="utf-8")
    note.write_text(
        "\n".join(
            [
                f"biome={args.biome}",
                f"table={args.table}",
                f"target={args.target}",
                f"feature_scope={args.feature_scope}",
                f"rows={len(dataset)}",
                f"feature_count={len(dataset.columns) - 1}",
                f"target_min_days={args.target_min_days}",
                f"target_max_days={args.target_max_days}",
                f"target_residual_offset={args.target_residual_offset}",
                f"backend={backend}",
                f"target_equation_lhs={target_r2_metrics['target_equation_lhs']}",
                f"target_equation_r2_train_split={target_r2_metrics['target_equation_r2_train_split']}",
                f"target_equation_r2_holdout_split={target_r2_metrics['target_equation_r2_holdout_split']}",
                f"target_equation_predictor_count={target_r2_metrics['target_equation_predictor_count']}",
                f"target_equation_train_rows={target_r2_metrics['target_equation_train_rows']}",
                f"target_equation_test_rows={target_r2_metrics['target_equation_test_rows']}",
                f"include_features={','.join(args.include_features) if args.include_features else ''}",
                f"exclude_features={','.join(args.exclude_features) if args.exclude_features else ''}",
                f"shap_results={args.shap_results}",
                f"model_spec_file={args.model_spec_file}",
            ]
        ),
        encoding="utf-8",
    )
    print(f"[DONE] note saved to {note}")


if __name__ == "__main__":
    main()
