#!/usr/bin/env python3
"""Run reliability checks for OPGD Geodetector results."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATION_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(VALIDATION_DIR))

from common_validation import (  # noqa: E402
    FEATURES,
    SHAP_ROOTS,
    TARGET,
    load_metric_biome_frame,
    short_label,
    write_readme,
)
from run_opgd_geodetector_validation import (  # noqa: E402
    DEFAULT_BIN_COUNTS,
    DEFAULT_METHODS,
    edge_strata,
    q_statistic,
    select_optimal_strata,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstraps", type=int, default=100)
    parser.add_argument("--max-rows", type=int, default=80000)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--min-group-share", type=float, default=0.01)
    parser.add_argument("--top-n", type=int, default=3)
    parser.add_argument("--reuse-existing", action="store_true")
    return parser.parse_args()


def spearman_rank_correlation(left: dict[str, int], right: dict[str, int]) -> float:
    features = sorted(set(left) & set(right))
    if len(features) < 2:
        return np.nan
    x = np.asarray([left[feature] for feature in features], dtype=float)
    y = np.asarray([right[feature] for feature in features], dtype=float)
    if np.nanstd(x) <= 0 or np.nanstd(y) <= 0:
        return np.nan
    return float(np.corrcoef(x, y)[0, 1])


def feature_ranks(features: list[str]) -> dict[str, int]:
    return {feature: rank + 1 for rank, feature in enumerate(features)}


def build_shap_opgd_consistency_row(opgd_group: pd.DataFrame, shap_group: pd.DataFrame, top_n: int = 3) -> dict[str, object]:
    opgd_sorted = opgd_group.sort_values("q", ascending=False).reset_index(drop=True)
    shap_sorted = shap_group[shap_group["feature"].isin(set(opgd_sorted["feature"]))].copy()
    shap_sorted = shap_sorted.sort_values("importance", ascending=False).reset_index(drop=True)

    opgd_top = opgd_sorted.head(top_n)
    shap_top = shap_sorted.head(top_n)
    opgd_top_features = opgd_top["feature"].tolist()
    shap_top_features = shap_top["feature"].tolist()
    overlap_features = [feature for feature in opgd_top_features if feature in set(shap_top_features)]
    label_map = dict(zip(opgd_sorted["feature"], opgd_sorted["label"]))
    overlap_labels = [label_map.get(feature, short_label(feature)) for feature in overlap_features]

    opgd_ranks = feature_ranks(opgd_sorted["feature"].tolist())
    shap_ranks = feature_ranks(shap_sorted["feature"].tolist())
    corr = spearman_rank_correlation(opgd_ranks, shap_ranks)
    return {
        "metric": opgd_sorted["metric"].iloc[0],
        "biome": opgd_sorted["biome"].iloc[0],
        "top3_overlap_count": len(overlap_features),
        "top3_overlap_labels": ", ".join(overlap_labels) if overlap_labels else "",
        "spearman_rank_correlation": corr,
    }


def build_strata_from_opgd_row(values: pd.Series, row: pd.Series) -> pd.Series:
    breaks = json.loads(row["breaks_json"])
    strata = edge_strata(values, np.asarray(breaks, dtype=float))
    if strata is None:
        return pd.Series(index=values.index, dtype="object")
    return strata


def bootstrap_q_stability(
    frame: pd.DataFrame,
    opgd_group: pd.DataFrame,
    bootstraps: int,
    random_state: int,
    top_n: int,
) -> pd.DataFrame:
    y = frame[TARGET]
    strata_map = {
        row.feature: build_strata_from_opgd_row(frame[row.feature], pd.Series(row._asdict()))
        for row in opgd_group.itertuples(index=False)
    }
    q_values: dict[str, list[float]] = {feature: [] for feature in strata_map}
    top_counts: dict[str, int] = {feature: 0 for feature in strata_map}
    rng = np.random.default_rng(random_state)
    n = len(frame)
    for _ in range(bootstraps):
        idx = rng.integers(0, n, size=n)
        q_for_bootstrap = {}
        for feature, strata in strata_map.items():
            q, _ = q_statistic(y.iloc[idx], strata.iloc[idx])
            q_values[feature].append(q)
            q_for_bootstrap[feature] = q
        top_features = [
            feature
            for feature, _ in sorted(q_for_bootstrap.items(), key=lambda item: item[1], reverse=True)[:top_n]
            if np.isfinite(q_for_bootstrap[feature])
        ]
        for feature in top_features:
            top_counts[feature] += 1
    rows = []
    for row in opgd_group.itertuples(index=False):
        values = np.asarray(q_values[row.feature], dtype=float)
        finite = values[np.isfinite(values)]
        q_mean = float(np.nanmean(finite)) if len(finite) else np.nan
        q_sd = float(np.nanstd(finite, ddof=1)) if len(finite) > 1 else np.nan
        rows.append(
            {
                "metric": row.metric,
                "biome": row.biome,
                "feature": row.feature,
                "label": row.label,
                "q_opgd": row.q,
                "bootstrap_q_mean": q_mean,
                "bootstrap_q_sd": q_sd,
                "bootstrap_q_cv": float(q_sd / q_mean) if np.isfinite(q_mean) and q_mean > 0 and np.isfinite(q_sd) else np.nan,
                "bootstrap_q_ci_low": float(np.nanquantile(finite, 0.025)) if len(finite) else np.nan,
                "bootstrap_q_ci_high": float(np.nanquantile(finite, 0.975)) if len(finite) else np.nan,
                "top3_frequency": top_counts[row.feature] / bootstraps if bootstraps > 0 else np.nan,
                "bootstraps": bootstraps,
            }
        )
    return pd.DataFrame(rows)


def conservative_opgd_rows(frame: pd.DataFrame, opgd_group: pd.DataFrame, min_group_share: float) -> pd.DataFrame:
    min_group_size = max(30, int(np.ceil(len(frame) * min_group_share)))
    rows = []
    for row in opgd_group.itertuples(index=False):
        opt = select_optimal_strata(
            frame[row.feature],
            frame[TARGET],
            methods=DEFAULT_METHODS,
            bin_counts=DEFAULT_BIN_COUNTS,
            min_group_size=min_group_size,
        )
        rows.append(
            {
                "metric": row.metric,
                "biome": row.biome,
                "feature": row.feature,
                "label": row.label,
                "q_conservative": opt.q,
                "conservative_method": opt.method,
                "conservative_bins": opt.bins,
                "conservative_min_group_size": opt.min_group_size,
                "conservative_min_group_share": opt.min_group_size / len(frame) if len(frame) else np.nan,
                "required_min_group_size": min_group_size,
            }
        )
    return pd.DataFrame(rows)


def strata_sensitivity_rows(
    opgd_group: pd.DataFrame,
    fixed_group: pd.DataFrame,
    conservative_group: pd.DataFrame,
) -> pd.DataFrame:
    fixed = fixed_group[["feature", "q"]].rename(columns={"q": "q_fixed6"})
    conservative = conservative_group[
        [
            "feature",
            "q_conservative",
            "conservative_method",
            "conservative_bins",
            "conservative_min_group_size",
            "conservative_min_group_share",
            "required_min_group_size",
        ]
    ]
    merged = opgd_group.merge(fixed, on="feature", how="left").merge(conservative, on="feature", how="left")
    merged["q_gain_vs_fixed6"] = merged["q"] - merged["q_fixed6"]
    merged["q_gain_vs_conservative"] = merged["q"] - merged["q_conservative"]
    merged["opgd_min_group_share"] = merged["min_group_size"] / merged["rows"]
    return merged[
        [
            "metric",
            "biome",
            "feature",
            "label",
            "q_fixed6",
            "q",
            "q_conservative",
            "q_gain_vs_fixed6",
            "q_gain_vs_conservative",
            "method",
            "bins",
            "min_group_size",
            "opgd_min_group_share",
            "conservative_method",
            "conservative_bins",
            "conservative_min_group_size",
            "conservative_min_group_share",
            "required_min_group_size",
            "rows",
        ]
    ].rename(columns={"q": "q_opgd", "method": "opgd_method", "bins": "opgd_bins"})


def assign_reliability_grade(
    q: float,
    q_cv: float,
    top3_frequency: float,
    in_shap_top3: bool,
    min_group_share: float,
) -> str:
    if np.isfinite(min_group_share) and min_group_share < 0.001:
        return "Low"
    score = 0
    if np.isfinite(q) and q >= 0.10:
        score += 2
    elif np.isfinite(q) and q >= 0.05:
        score += 1
    if np.isfinite(q_cv) and q_cv <= 0.15:
        score += 2
    elif np.isfinite(q_cv) and q_cv <= 0.35:
        score += 1
    if np.isfinite(top3_frequency) and top3_frequency >= 0.70:
        score += 2
    elif np.isfinite(top3_frequency) and top3_frequency >= 0.40:
        score += 1
    if in_shap_top3:
        score += 1
    if np.isfinite(min_group_share) and min_group_share >= 0.01:
        score += 1
    if score >= 7:
        if np.isfinite(min_group_share) and min_group_share < 0.005:
            return "Medium"
        return "High"
    if score >= 4:
        return "Medium"
    return "Low"


def reliability_score_rows(
    opgd_group: pd.DataFrame,
    bootstrap_group: pd.DataFrame,
    sensitivity_group: pd.DataFrame,
    shap_group: pd.DataFrame,
    top_n: int,
) -> pd.DataFrame:
    shap_top = set(shap_group.sort_values("importance", ascending=False).head(top_n)["feature"])
    merged = (
        opgd_group.merge(
            bootstrap_group[["feature", "bootstrap_q_mean", "bootstrap_q_sd", "bootstrap_q_cv", "top3_frequency"]],
            on="feature",
            how="left",
        )
        .merge(
            sensitivity_group[
                [
                    "feature",
                    "q_fixed6",
                    "q_conservative",
                    "opgd_min_group_share",
                    "conservative_min_group_share",
                    "q_gain_vs_fixed6",
                    "q_gain_vs_conservative",
                ]
            ],
            on="feature",
            how="left",
        )
    )
    merged["in_shap_top3"] = merged["feature"].isin(shap_top)
    merged["reliability_grade"] = [
        assign_reliability_grade(
            q=row.q,
            q_cv=row.bootstrap_q_cv,
            top3_frequency=row.top3_frequency,
            in_shap_top3=row.in_shap_top3,
            min_group_share=row.opgd_min_group_share,
        )
        for row in merged.itertuples(index=False)
    ]
    return merged[
        [
            "metric",
            "biome",
            "feature",
            "label",
            "q",
            "bootstrap_q_mean",
            "bootstrap_q_sd",
            "bootstrap_q_cv",
            "top3_frequency",
            "q_fixed6",
            "q_conservative",
            "q_gain_vs_fixed6",
            "q_gain_vs_conservative",
            "method",
            "bins",
            "min_group_size",
            "opgd_min_group_share",
            "in_shap_top3",
            "reliability_grade",
            "rows",
        ]
    ].rename(columns={"q": "q_opgd", "method": "opgd_method", "bins": "opgd_bins"})


def prepare_frame(metric: str, biome: str, max_rows: int, random_state: int) -> pd.DataFrame:
    df = load_metric_biome_frame(metric, biome)
    cols = [c for c in FEATURES if c in df.columns]
    frame = df[cols + [TARGET]].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    frame = frame.dropna(axis=0, how="any")
    if max_rows > 0 and len(frame) > max_rows:
        frame = frame.sample(n=max_rows, random_state=random_state).sort_index()
    return frame


def main() -> None:
    args = parse_args()
    work_dir = SCRIPT_DIR
    out_dir = work_dir / "reliability"
    out_dir.mkdir(parents=True, exist_ok=True)
    opgd = pd.read_csv(work_dir / "opgd_factor_q.csv")
    fixed = pd.read_csv(VALIDATION_DIR / "04_Geodetector" / "geodetector_factor_q.csv")

    bootstrap_parts = []
    conservative_parts = []
    sensitivity_parts = []
    consistency_rows = []
    reliability_parts = []
    if args.reuse_existing:
        existing_bootstrap = pd.read_csv(out_dir / "bootstrap_q_stability.csv")
        existing_sensitivity = pd.read_csv(out_dir / "strata_sensitivity.csv")
    else:
        existing_bootstrap = pd.DataFrame()
        existing_sensitivity = pd.DataFrame()
    for (metric, biome), opgd_group in opgd.groupby(["metric", "biome"], sort=False):
        shap_group = pd.read_csv(SHAP_ROOTS[metric] / biome / "feature_importance.csv")
        if args.reuse_existing:
            bootstrap_group = existing_bootstrap[
                (existing_bootstrap["metric"] == metric) & (existing_bootstrap["biome"] == biome)
            ].copy()
            sensitivity_group = existing_sensitivity[
                (existing_sensitivity["metric"] == metric) & (existing_sensitivity["biome"] == biome)
            ].copy()
            conservative_group = pd.DataFrame()
        else:
            frame = prepare_frame(metric, biome, max_rows=args.max_rows, random_state=args.random_state)
            fixed_group = fixed[(fixed["metric"] == metric) & (fixed["biome"] == biome)].copy()
            bootstrap_group = bootstrap_q_stability(
                frame,
                opgd_group,
                bootstraps=args.bootstraps,
                random_state=args.random_state + len(bootstrap_parts) * 1009,
                top_n=args.top_n,
            )
            conservative_group = conservative_opgd_rows(frame, opgd_group, min_group_share=args.min_group_share)
            sensitivity_group = strata_sensitivity_rows(opgd_group, fixed_group, conservative_group)

        consistency_rows.append(build_shap_opgd_consistency_row(opgd_group, shap_group, top_n=args.top_n))
        if not args.reuse_existing:
            bootstrap_parts.append(bootstrap_group)
            conservative_parts.append(conservative_group)
            sensitivity_parts.append(sensitivity_group)
        reliability_parts.append(
            reliability_score_rows(
                opgd_group,
                bootstrap_group,
                sensitivity_group,
                shap_group,
                top_n=args.top_n,
            )
        )

    bootstrap_df = existing_bootstrap if args.reuse_existing else pd.concat(bootstrap_parts, ignore_index=True)
    sensitivity_df = existing_sensitivity if args.reuse_existing else pd.concat(sensitivity_parts, ignore_index=True)
    consistency_df = pd.DataFrame(consistency_rows)
    reliability_df = pd.concat(reliability_parts, ignore_index=True)

    bootstrap_df.to_csv(out_dir / "bootstrap_q_stability.csv", index=False)
    sensitivity_df.to_csv(out_dir / "strata_sensitivity.csv", index=False)
    consistency_df.to_csv(out_dir / "shap_opgd_consistency.csv", index=False)
    reliability_df.to_csv(out_dir / "reliability_score.csv", index=False)
    write_readme(
        out_dir / "README.md",
        [
            "# OPGD reliability checks",
            f"Bootstraps: {args.bootstraps}",
            f"Max rows per metric-biome subset: {args.max_rows}",
            f"Conservative min group share: {args.min_group_share}",
            "Outputs:",
            "- bootstrap_q_stability.csv",
            "- strata_sensitivity.csv",
            "- shap_opgd_consistency.csv",
            "- reliability_score.csv",
        ],
    )


if __name__ == "__main__":
    main()
