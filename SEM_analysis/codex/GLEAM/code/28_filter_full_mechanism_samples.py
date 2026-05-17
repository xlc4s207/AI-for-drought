#!/usr/bin/env python
"""Filter mechanism-consistent samples from the full GPP recovery table."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

from sem_gleam_common import finalize_feature_table


SHAP_ANALYSIS_PATH = Path(__file__).with_name("06_shap_analysis.py")
SHAP_ANALYSIS_SPEC = importlib.util.spec_from_file_location("shap_analysis_module", SHAP_ANALYSIS_PATH)
if SHAP_ANALYSIS_SPEC is None or SHAP_ANALYSIS_SPEC.loader is None:  # pragma: no cover
    raise RuntimeError(f"Unable to load helper module from {SHAP_ANALYSIS_PATH}")
shap_analysis_module = importlib.util.module_from_spec(SHAP_ANALYSIS_SPEC)
SHAP_ANALYSIS_SPEC.loader.exec_module(shap_analysis_module)

filter_analysis_subset = shap_analysis_module.filter_analysis_subset
prepare_model_inputs = shap_analysis_module.prepare_model_inputs
fit_tree_model = shap_analysis_module.fit_tree_model


BIOMES = ["Cropland", "Forest", "Grassland", "Savanna", "Shrubland"]
MODEL_FEATURES = [
    "prepeak_total_precipitation_mean",
    "recoverywin_total_precipitation_mean",
    "recoverywin_total_evaporation_mean",
    "recoverywin_SMrz_mean",
    "recoverywin_temperature_2m_mean",
    "recoverywin_VPD_mean",
    "recoverywin_wind_speed_mean",
    "recoverywin_lai_total_mean",
    "recoverywin_ssrd_mean",
    "recoverywin_strd_mean",
]
EXCLUDE_FEATURES = [
    "recoverywin_p_minus_et",
    "recoverywin_total_precipitation_sum",
    "recoverywin_total_evaporation_sum",
    "recoverywin_SMrz_delta",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--metric", default="GPP")
    parser.add_argument("--code-id", default="code1")
    parser.add_argument("--drought-type", default="flash")
    parser.add_argument("--soil-layer", default="SMrz")
    parser.add_argument("--feature-scope", default="all")
    parser.add_argument("--target", default="t_recover_to_baseline_abs_peak")
    parser.add_argument("--pre-col", default="recoverywin_total_precipitation_mean")
    parser.add_argument("--amp-col", default="amp_max")
    parser.add_argument("--model-backend", default="lightgbm")
    parser.add_argument("--n-estimators", type=int, default=120)
    parser.add_argument("--n-jobs", type=int, default=12)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--low-pre-threshold", type=float, default=0.004)
    parser.add_argument("--severe-pre-threshold", type=float, default=0.004)
    return parser.parse_args()


def compute_gpp_drop_magnitude(values: pd.Series) -> pd.Series:
    out = -pd.to_numeric(values, errors="coerce")
    return out.clip(lower=0)


def classify_mechanism_groups(
    frame: pd.DataFrame,
    pre_col: str,
    shap_col: str,
    amp_col: str,
    low_pre_threshold: float = 0.004,
    severe_pre_threshold: float = 0.004,
) -> pd.Series:
    pre = pd.to_numeric(frame[pre_col], errors="coerce")
    shap = pd.to_numeric(frame[shap_col], errors="coerce")
    gpp_drop = compute_gpp_drop_magnitude(frame[amp_col])
    low_cut = float(gpp_drop.quantile(1 / 3))
    high_cut = float(gpp_drop.quantile(2 / 3))

    groups = pd.Series("background", index=frame.index, dtype="object")
    mild_mask = (pre < low_pre_threshold) & (shap < 0) & (gpp_drop <= low_cut)
    severe_mask = (pre >= severe_pre_threshold) & (shap > 0) & (gpp_drop >= high_cut)
    groups.loc[mild_mask] = "expected_mild"
    groups.loc[severe_mask] = "expected_severe"
    return groups


def compute_feature_shap_values(model, X: pd.DataFrame, feature_names: list[str], feature_name: str) -> np.ndarray:
    if feature_name not in feature_names:
        raise KeyError(f"{feature_name} not found in feature list")
    contrib = model.predict(X, pred_contrib=True)
    contrib = np.asarray(contrib)
    if contrib.ndim != 2 or contrib.shape[1] < len(feature_names):
        raise ValueError("Unexpected LightGBM contribution output shape")
    feat_idx = feature_names.index(feature_name)
    return contrib[:, feat_idx].astype(float)


def process_biome(base_df: pd.DataFrame, biome: str, args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    sub = filter_analysis_subset(
        base_df,
        metric=args.metric,
        code_id=args.code_id,
        biome=biome,
        drought_type=args.drought_type,
        soil_layer=args.soil_layer,
    ).copy()
    X, y, feature_names = prepare_model_inputs(
        sub,
        target=args.target,
        max_missing_rate=0.3,
        feature_scope=args.feature_scope,
        include_features=MODEL_FEATURES,
        exclude_features=EXCLUDE_FEATURES,
    )
    model = fit_tree_model(
        X,
        y,
        backend=args.model_backend,
        random_state=args.random_state,
        n_estimators=args.n_estimators,
        n_jobs=args.n_jobs,
    )
    pre_shap = compute_feature_shap_values(model, X, feature_names, args.pre_col)
    work = sub.loc[X.index, ["event_uid", "biome", args.pre_col, args.amp_col, args.target, "flux_change_to_peak_abs"]].copy()
    work["pre_shap"] = pre_shap
    work["gpp_drop_magnitude"] = compute_gpp_drop_magnitude(work[args.amp_col])
    work["mechanism_group"] = classify_mechanism_groups(
        work,
        pre_col=args.pre_col,
        shap_col="pre_shap",
        amp_col=args.amp_col,
        low_pre_threshold=args.low_pre_threshold,
        severe_pre_threshold=args.severe_pre_threshold,
    )
    summary = []
    for group, grp in work.groupby("mechanism_group", observed=True):
        summary.append(
            {
                "biome": biome,
                "group": str(group),
                "rows": int(len(grp)),
                "pre_median": float(pd.to_numeric(grp[args.pre_col], errors="coerce").median()),
                "pre_shap_median": float(pd.to_numeric(grp["pre_shap"], errors="coerce").median()),
                "amp_max_median": float(pd.to_numeric(grp[args.amp_col], errors="coerce").median()),
                "gpp_drop_magnitude_median": float(pd.to_numeric(grp["gpp_drop_magnitude"], errors="coerce").median()),
            }
        )
    return work, pd.DataFrame(summary)


def main() -> None:
    args = parse_args()
    base_df = finalize_feature_table(pd.read_parquet(args.table))
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[pd.DataFrame] = []
    summaries: list[pd.DataFrame] = []
    filtered_rows: list[pd.DataFrame] = []
    for biome in BIOMES:
        full_df, summary_df = process_biome(base_df, biome, args)
        all_rows.append(full_df)
        summaries.append(summary_df)
        filtered_rows.append(full_df[full_df["mechanism_group"] != "background"].copy())

    all_full = pd.concat(all_rows, ignore_index=True)
    all_filtered = pd.concat(filtered_rows, ignore_index=True)
    all_summary = pd.concat(summaries, ignore_index=True)

    all_full.to_parquet(out_dir / "full_rows_with_pre_shap.parquet", index=False)
    all_filtered.to_parquet(out_dir / "filtered_mechanism_rows.parquet", index=False)
    all_summary.to_csv(out_dir / "summary.csv", index=False)


if __name__ == "__main__":
    main()
