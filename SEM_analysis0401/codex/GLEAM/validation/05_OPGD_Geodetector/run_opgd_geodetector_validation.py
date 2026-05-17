#!/usr/bin/env python3
"""Run OPGD-style Geodetector validation with optimized strata."""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

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


DEFAULT_METHODS = ["quantile", "equal_interval", "geometric_interval", "standard_deviation"]
DEFAULT_BIN_COUNTS = list(range(3, 11))


@dataclass
class OptimizedStrata:
    q: float
    method: str
    bins: int
    strata: pd.Series
    breaks: list[float]
    strata_count: int
    min_group_size: int
    max_group_size: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-rows", type=int, default=80000)
    parser.add_argument("--methods", default=",".join(DEFAULT_METHODS))
    parser.add_argument("--min-bins", type=int, default=3)
    parser.add_argument("--max-bins", type=int, default=10)
    parser.add_argument("--min-group-size", type=int, default=30)
    parser.add_argument("--top-n-interactions", type=int, default=5)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def empty_result(index: pd.Index | None = None) -> OptimizedStrata:
    return OptimizedStrata(
        q=np.nan,
        method="",
        bins=0,
        strata=pd.Series(index=index, dtype="object"),
        breaks=[],
        strata_count=0,
        min_group_size=0,
        max_group_size=0,
    )


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


def finite_breaks(edges: np.ndarray) -> list[float]:
    return [float(v) for v in edges if np.isfinite(v)]


def edge_strata(values: pd.Series, edges: np.ndarray) -> pd.Series | None:
    edges = np.unique(np.asarray(edges, dtype=float))
    if len(edges) < 3:
        return None
    try:
        return pd.cut(values, bins=edges, include_lowest=True, duplicates="drop").astype(str)
    except ValueError:
        return None


def quantile_strata(values: pd.Series, bins: int) -> tuple[pd.Series | None, list[float]]:
    try:
        _, edges = pd.qcut(values, q=bins, duplicates="drop", retbins=True)
    except ValueError:
        return None, []
    strata = edge_strata(values, edges)
    return strata, finite_breaks(edges)


def equal_interval_strata(values: pd.Series, bins: int) -> tuple[pd.Series | None, list[float]]:
    try:
        _, edges = pd.cut(values, bins=bins, duplicates="drop", retbins=True)
    except ValueError:
        return None, []
    strata = edge_strata(values, edges)
    return strata, finite_breaks(edges)


def geometric_interval_strata(values: pd.Series, bins: int) -> tuple[pd.Series | None, list[float]]:
    finite = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    if len(finite) < bins or np.nanmin(finite) == np.nanmax(finite):
        return None, []
    offset = 0.0
    min_value = float(np.nanmin(finite))
    if min_value <= 0:
        offset = abs(min_value) + 1e-9
    shifted = finite + offset
    positive = shifted[shifted > 0]
    if len(positive) < bins:
        return None, []
    edges = np.geomspace(float(np.nanmin(positive)), float(np.nanmax(positive)), bins + 1) - offset
    edges[0] = min_value
    edges[-1] = float(np.nanmax(finite))
    strata = edge_strata(values, edges)
    return strata, finite_breaks(edges)


def standard_deviation_strata(values: pd.Series, bins: int) -> tuple[pd.Series | None, list[float]]:
    finite = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    if len(finite) < bins or np.nanmin(finite) == np.nanmax(finite):
        return None, []
    mean = float(np.nanmean(finite))
    std = float(np.nanstd(finite))
    if not np.isfinite(std) or std <= 0:
        return None, []
    min_value = float(np.nanmin(finite))
    max_value = float(np.nanmax(finite))
    interior_count = max(1, bins - 1)
    interior = mean + std * np.linspace(-2.0, 2.0, interior_count)
    edges = np.concatenate([[min_value], interior[(interior > min_value) & (interior < max_value)], [max_value]])
    strata = edge_strata(values, edges)
    return strata, finite_breaks(edges)


def build_strata(values: pd.Series, method: str, bins: int) -> tuple[pd.Series | None, list[float]]:
    numeric = pd.to_numeric(values, errors="coerce")
    if method == "quantile":
        return quantile_strata(numeric, bins)
    if method == "equal_interval":
        return equal_interval_strata(numeric, bins)
    if method == "geometric_interval":
        return geometric_interval_strata(numeric, bins)
    if method == "standard_deviation":
        return standard_deviation_strata(numeric, bins)
    raise ValueError(f"Unknown discretization method: {method}")


def valid_group_sizes(strata: pd.Series, min_group_size: int) -> tuple[bool, int, int]:
    counts = strata.dropna()
    counts = counts[counts != "nan"].value_counts()
    if len(counts) < 2:
        return False, 0, 0
    min_size = int(counts.min())
    max_size = int(counts.max())
    return min_size >= min_group_size, min_size, max_size


def select_optimal_strata(
    x: pd.Series,
    y: pd.Series,
    methods: list[str],
    bin_counts: list[int],
    min_group_size: int,
) -> OptimizedStrata:
    best = empty_result(index=x.index)
    best_key = (-np.inf, 0, 0)
    for method in methods:
        for bins in bin_counts:
            strata, breaks = build_strata(x, method, bins)
            if strata is None:
                continue
            ok, min_size, max_size = valid_group_sizes(strata, min_group_size)
            if not ok:
                continue
            q, strata_count = q_statistic(y, strata)
            if not np.isfinite(q):
                continue
            key = (q, -abs(strata_count - bins), -bins)
            if key > best_key:
                best_key = key
                best = OptimizedStrata(
                    q=q,
                    method=method,
                    bins=bins,
                    strata=strata,
                    breaks=breaks,
                    strata_count=strata_count,
                    min_group_size=min_size,
                    max_group_size=max_size,
                )
    return best


def risk_table(y: pd.Series, strata: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame({"y": pd.to_numeric(y, errors="coerce"), "strata": strata}).dropna()
    df = df[df["strata"] != "nan"]
    return (
        df.groupby("strata", observed=False)["y"]
        .agg(["count", "mean", "median", "std"])
        .reset_index()
        .rename(columns={"mean": "target_mean", "median": "target_median", "std": "target_std"})
    )


def interaction_relation(q_inter: float, q1: float, q2: float) -> str:
    tol = 1e-12
    if q_inter > q1 + q2 + tol:
        return "nonlinear_enhance"
    if q_inter + tol >= max(q1, q2):
        return "bi_factor_enhance"
    if q_inter < min(q1, q2) - tol:
        return "weaken"
    return "independent_or_partial"


def build_interaction_row(
    metric: str,
    biome: str,
    frame: pd.DataFrame,
    target: str,
    feature_1: str,
    feature_2: str,
    optimized: dict[str, OptimizedStrata],
    labeler: Callable[[str], str],
) -> dict[str, object]:
    opt1 = optimized[feature_1]
    opt2 = optimized[feature_2]
    combined = opt1.strata.astype(str) + " | " + opt2.strata.astype(str)
    q_inter, strata_count = q_statistic(frame[target], combined)
    return {
        "metric": metric,
        "biome": biome,
        "feature_1": feature_1,
        "feature_2": feature_2,
        "label_1": labeler(feature_1),
        "label_2": labeler(feature_2),
        "q_feature_1": opt1.q,
        "q_feature_2": opt2.q,
        "q_interaction": q_inter,
        "interaction_relation": interaction_relation(q_inter, opt1.q, opt2.q),
        "method_1": opt1.method,
        "method_2": opt2.method,
        "bins_1": opt1.bins,
        "bins_2": opt2.bins,
        "strata_count": strata_count,
        "rows": len(frame),
    }


def main() -> None:
    args = parse_args()
    out_root = VALIDATION_ROOT / "05_OPGD_Geodetector"
    methods = [item.strip() for item in args.methods.split(",") if item.strip()]
    bin_counts = list(range(args.min_bins, args.max_bins + 1))
    q_rows = []
    interaction_rows = []
    for metric in METRICS:
        for biome in BIOMES:
            df = load_metric_biome_frame(metric, biome)
            cols = [c for c in FEATURES if c in df.columns]
            frame = df[cols + [TARGET]].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
            frame = frame.dropna(axis=0, how="any")
            if args.max_rows > 0 and len(frame) > args.max_rows:
                frame = frame.sample(n=args.max_rows, random_state=args.random_state).sort_index()
            sub = out_root / "results" / metric / biome
            sub.mkdir(parents=True, exist_ok=True)
            optimized: dict[str, OptimizedStrata] = {}
            for feature in cols:
                opt = select_optimal_strata(
                    frame[feature],
                    frame[TARGET],
                    methods=methods,
                    bin_counts=bin_counts,
                    min_group_size=args.min_group_size,
                )
                optimized[feature] = opt
                risk = risk_table(frame[TARGET], opt.strata)
                risk_path = sub / f"{short_label(feature)}_opgd_risk_detector.csv"
                risk.to_csv(risk_path, index=False)
                q_rows.append(
                    {
                        "metric": metric,
                        "biome": biome,
                        "feature": feature,
                        "label": short_label(feature),
                        "q": opt.q,
                        "method": opt.method,
                        "bins": opt.bins,
                        "strata_count": opt.strata_count,
                        "min_group_size": opt.min_group_size,
                        "max_group_size": opt.max_group_size,
                        "breaks_json": json.dumps(opt.breaks, ensure_ascii=False),
                        "rows": len(frame),
                        "risk_csv": str(risk_path),
                    }
                )
            interaction_features = [f for f in top_features(metric, biome, args.top_n_interactions) if f in optimized]
            for f1, f2 in itertools.combinations(interaction_features, 2):
                if not np.isfinite(optimized[f1].q) or not np.isfinite(optimized[f2].q):
                    continue
                interaction_rows.append(
                    build_interaction_row(
                        metric=metric,
                        biome=biome,
                        frame=frame,
                        target=TARGET,
                        feature_1=f1,
                        feature_2=f2,
                        optimized=optimized,
                        labeler=short_label,
                    )
                )
    q_df = pd.DataFrame(q_rows).sort_values(["metric", "biome", "q"], ascending=[True, True, False])
    inter_df = pd.DataFrame(interaction_rows).sort_values(
        ["metric", "biome", "q_interaction"], ascending=[True, True, False]
    )
    q_df.to_csv(out_root / "opgd_factor_q.csv", index=False)
    inter_df.to_csv(out_root / "opgd_interactions.csv", index=False)
    write_readme(
        out_root / "README.md",
        [
            "# OPGD Geodetector validation",
            "Purpose: improve the fixed-bin Geodetector by optimizing continuous-variable strata.",
            f"Methods: {', '.join(methods)}.",
            f"Bin search: {args.min_bins}-{args.max_bins}; min group size: {args.min_group_size}.",
            "Factor detector: selects the method/bin count with the highest valid q for each metric-biome-feature.",
            "Interaction detector: reuses the optimized single-factor strata for SHAP top-feature pairs.",
            "Outputs: opgd_factor_q.csv, opgd_interactions.csv, and per-feature OPGD risk detector CSV files.",
        ],
    )


if __name__ == "__main__":
    main()
