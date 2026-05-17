#!/usr/bin/env python
"""Run severity-stratified SHAP diagnostics for recovery-window precipEmean features."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

from sem_gleam_common import finalize_feature_table

try:
    import shap  # type: ignore
except Exception:  # pragma: no cover
    shap = None


TARGET = "t_recover_to_baseline_abs_peak"
FEATURES = [
    "recoverywin_total_precipitation_mean",
    "recoverywin_total_evaporation_mean",
    "recoverywin_temperature_2m_mean",
    "recoverywin_VPD_mean",
    "recoverywin_SMrz_mean",
    "recoverywin_lai_total_mean",
    "recoverywin_ssrd_mean",
    "recoverywin_strd_mean",
    "recoverywin_wind_speed_mean",
]
FOCUS_FEATURES = [
    "recoverywin_total_precipitation_mean",
    "recoverywin_ssrd_mean",
]
SEVERITY_SOURCE_MAP = {
    "intensity": "event_intensity",
    "onset_drop": "event_onset_drop",
    "days_below_p20": "event_days_below_p20",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--drought-table", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--metric", default="GPP")
    parser.add_argument("--code-id", default="code1")
    parser.add_argument("--drought-type", default="flash")
    parser.add_argument("--soil-layer", default="SMrz")
    parser.add_argument("--biomes", nargs="+", default=["Forest", "Grassland", "Cropland", "Shrubland", "Savanna"])
    parser.add_argument(
        "--severity-vars",
        nargs="+",
        default=["intensity", "onset_drop", "days_below_p20", "amp_max", "t_impact"],
    )
    parser.add_argument("--n-groups", type=int, default=3)
    parser.add_argument("--min-rows", type=int, default=2000)
    parser.add_argument("--max-rows-per-stratum", type=int, default=15000)
    parser.add_argument("--shap-sample-size", type=int, default=300)
    parser.add_argument("--n-estimators", type=int, default=60)
    parser.add_argument("--n-jobs", type=int, default=4)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def load_analysis_table(args: argparse.Namespace) -> pd.DataFrame:
    base = pd.read_parquet(args.table)
    base = finalize_feature_table(base)
    mask = (
        (base["metric"].astype(str) == str(args.metric))
        & (base["code_id"].astype(str) == str(args.code_id))
        & (base["drought_type"].astype(str) == str(args.drought_type))
        & (base["soil_layer"].astype(str) == str(args.soil_layer))
    )
    base = base.loc[mask].copy()

    drought = pd.read_parquet(args.drought_table, columns=["event_uid", *SEVERITY_SOURCE_MAP.values()])
    drought = drought.rename(columns={v: k for k, v in SEVERITY_SOURCE_MAP.items()})
    merged = base.merge(drought, on="event_uid", how="left")
    return merged


def assign_strata(series: pd.Series, n_groups: int) -> pd.Series:
    ranked = series.rank(method="first")
    labels = [f"q{i + 1}" for i in range(n_groups)]
    return pd.qcut(ranked, q=n_groups, labels=labels)


def compute_focus_direction(feature_values: np.ndarray, shap_values: np.ndarray) -> dict[str, float]:
    out: dict[str, float] = {}
    if len(feature_values) < 10:
        return {
            "feature_shap_corr": np.nan,
            "low20_mean_shap": np.nan,
            "high20_mean_shap": np.nan,
            "delta_high_low_shap": np.nan,
        }
    corr = np.corrcoef(feature_values, shap_values)[0, 1]
    q20 = np.nanquantile(feature_values, 0.2)
    q80 = np.nanquantile(feature_values, 0.8)
    low_mask = feature_values <= q20
    high_mask = feature_values >= q80
    low_mean = float(np.nanmean(shap_values[low_mask])) if np.any(low_mask) else np.nan
    high_mean = float(np.nanmean(shap_values[high_mask])) if np.any(high_mask) else np.nan
    out["feature_shap_corr"] = float(corr) if np.isfinite(corr) else np.nan
    out["low20_mean_shap"] = low_mean
    out["high20_mean_shap"] = high_mean
    out["delta_high_low_shap"] = high_mean - low_mean if np.isfinite(low_mean) and np.isfinite(high_mean) else np.nan
    return out


def fit_one_stratum(
    df: pd.DataFrame,
    max_rows: int,
    shap_sample_size: int,
    n_estimators: int,
    n_jobs: int,
    random_state: int,
) -> tuple[pd.DataFrame, dict[str, float], np.ndarray, pd.DataFrame]:
    work = df[[TARGET] + FEATURES].apply(pd.to_numeric, errors="coerce")
    work = work[work[TARGET].notna()].copy()
    work[FEATURES] = work[FEATURES].fillna(work[FEATURES].median(numeric_only=True))
    if len(work) > max_rows:
        work = work.sample(n=max_rows, random_state=random_state)
    X = work[FEATURES].astype(np.float32)
    y = work[TARGET].astype(np.float32)
    test_size = max(1, int(round(len(X) * 0.2)))
    test_size = min(test_size, len(X) - 1)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=random_state)
    model = RandomForestRegressor(
        n_estimators=n_estimators,
        random_state=random_state,
        n_jobs=n_jobs,
        min_samples_leaf=2,
    )
    model.fit(X_train, y_train)
    sample = X.sample(n=min(shap_sample_size, len(X)), random_state=random_state)
    if shap is None:
        raise ImportError("shap is required for stratified SHAP analysis.")
    explainer = shap.TreeExplainer(model)
    shap_array = np.asarray(explainer.shap_values(sample))
    importance = np.abs(shap_array).mean(axis=0)
    importance_df = pd.DataFrame({"feature": FEATURES, "importance": importance}).sort_values("importance", ascending=False)
    metrics = {
        "rows_used": int(len(X)),
        "r2_train_split": float(model.score(X_train, y_train)),
        "r2_holdout_split": float(model.score(X_test, y_test)),
        "shap_rows": int(len(sample)),
    }
    return importance_df.reset_index(drop=True), metrics, shap_array, sample


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_analysis_table(args)
    summary_rows: list[dict[str, object]] = []
    focus_rows: list[dict[str, object]] = []

    for biome in args.biomes:
        biome_df = df[df["biome"].astype(str) == str(biome)].copy()
        for severity_var in args.severity_vars:
            if severity_var not in biome_df.columns:
                continue
            sev = pd.to_numeric(biome_df[severity_var], errors="coerce")
            valid = biome_df.loc[sev.notna()].copy()
            valid[severity_var] = pd.to_numeric(valid[severity_var], errors="coerce")
            if len(valid) < args.min_rows * args.n_groups:
                continue
            try:
                valid["severity_group"] = assign_strata(valid[severity_var], args.n_groups)
            except ValueError:
                continue
            for group_label, group_df in valid.groupby("severity_group", observed=True):
                if len(group_df) < args.min_rows:
                    continue
                importance_df, metrics, shap_array, sample = fit_one_stratum(
                    group_df,
                    max_rows=args.max_rows_per_stratum,
                    shap_sample_size=args.shap_sample_size,
                    n_estimators=args.n_estimators,
                    n_jobs=args.n_jobs,
                    random_state=args.random_state,
                )
                top5 = ",".join(importance_df["feature"].head(5).astype(str).tolist())
                summary_rows.append(
                    {
                        "biome": biome,
                        "severity_var": severity_var,
                        "severity_group": str(group_label),
                        "group_rows_raw": int(len(group_df)),
                        "top5_features": top5,
                        **metrics,
                    }
                )
                for focus_feature in FOCUS_FEATURES:
                    idx = FEATURES.index(focus_feature)
                    direction = compute_focus_direction(
                        sample[focus_feature].to_numpy(dtype=float),
                        shap_array[:, idx].astype(float),
                    )
                    focus_rows.append(
                        {
                            "biome": biome,
                            "severity_var": severity_var,
                            "severity_group": str(group_label),
                            "focus_feature": focus_feature,
                            "importance_rank": int(importance_df.reset_index(drop=True).index[importance_df["feature"] == focus_feature][0] + 1),
                            "importance_value": float(importance_df.loc[importance_df["feature"] == focus_feature, "importance"].iloc[0]),
                            **direction,
                            **metrics,
                        }
                    )

    pd.DataFrame(summary_rows).to_csv(output_dir / "severity_stratified_shap_summary.csv", index=False)
    pd.DataFrame(focus_rows).to_csv(output_dir / "severity_stratified_focus_directions.csv", index=False)
    print(f"[DONE] summary={output_dir / 'severity_stratified_shap_summary.csv'}")
    print(f"[DONE] focus={output_dir / 'severity_stratified_focus_directions.csv'}")


if __name__ == "__main__":
    main()
