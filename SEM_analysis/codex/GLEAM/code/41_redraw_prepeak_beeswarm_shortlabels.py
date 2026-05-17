#!/usr/bin/env python
"""Redraw prepeak beeswarm plots with simplified feature labels."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    import shap  # type: ignore
except ImportError:  # pragma: no cover
    shap = None


SCRIPT_33_PATH = Path(__file__).with_name("33_plot_prepeak_vs_recoverywin_comparison.py")
SCRIPT_33_SPEC = importlib.util.spec_from_file_location("plot_prepeak_vs_recoverywin_comparison", SCRIPT_33_PATH)
if SCRIPT_33_SPEC is None or SCRIPT_33_SPEC.loader is None:
    raise RuntimeError(f"Unable to load helper module from {SCRIPT_33_PATH}")
plot_prepeak_vs_recoverywin_comparison = importlib.util.module_from_spec(SCRIPT_33_SPEC)
sys.modules[SCRIPT_33_SPEC.name] = plot_prepeak_vs_recoverywin_comparison
SCRIPT_33_SPEC.loader.exec_module(plot_prepeak_vs_recoverywin_comparison)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--biomes", nargs="+", default=None)
    parser.add_argument("--max-points", type=int, default=2500)
    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument("--title-prefix", default="Prepeak")
    parser.add_argument("--output-suffix", default="prepeak")
    return parser.parse_args()


def resolve_feature_order(csv_path: Path) -> list[str]:
    df = pd.read_csv(csv_path)
    ordered: list[str] = []
    for feature in df.sort_values("rank")["feature"].tolist():
        if isinstance(feature, str) and feature not in ordered:
            ordered.append(feature)
    return ordered


def select_valid_columns(
    sample_df: pd.DataFrame,
    shap_df: pd.DataFrame,
    feature_order: list[str],
) -> list[str]:
    return [name for name in feature_order if name in sample_df.columns and name in shap_df.columns]


def prepare_beeswarm_inputs(
    sample_df: pd.DataFrame,
    shap_df: pd.DataFrame,
    feature_order: list[str],
    max_points: int,
) -> tuple[pd.DataFrame, np.ndarray, list[str]]:
    selected_cols = select_valid_columns(sample_df, shap_df, feature_order)
    if not selected_cols:
        return pd.DataFrame(), np.empty((0, 0), dtype=float), []

    feature_frame = sample_df[selected_cols].apply(pd.to_numeric, errors="coerce")
    shap_frame = shap_df[selected_cols].apply(pd.to_numeric, errors="coerce")
    valid_mask = feature_frame.notna().all(axis=1) & shap_frame.notna().all(axis=1)
    feature_frame = feature_frame.loc[valid_mask].reset_index(drop=True)
    shap_frame = shap_frame.loc[valid_mask].reset_index(drop=True)
    if feature_frame.empty:
        return pd.DataFrame(columns=selected_cols), np.empty((0, len(selected_cols)), dtype=float), selected_cols
    if len(feature_frame) > max_points:
        sampled_idx = feature_frame.sample(n=max_points, random_state=42).index
        feature_frame = feature_frame.loc[sampled_idx].reset_index(drop=True)
        shap_frame = shap_frame.loc[sampled_idx].reset_index(drop=True)
    return feature_frame, shap_frame.to_numpy(dtype=float), selected_cols


def plot_single_beeswarm(
    sample_df: pd.DataFrame,
    shap_df: pd.DataFrame,
    feature_order: list[str],
    title: str,
    output_path: Path,
    max_points: int,
    dpi: int,
) -> dict[str, object]:
    feature_frame, shap_matrix, feature_names = prepare_beeswarm_inputs(
        sample_df=sample_df,
        shap_df=shap_df,
        feature_order=feature_order,
        max_points=max_points,
    )
    display_feature_names = [
        plot_prepeak_vs_recoverywin_comparison.format_beeswarm_feature_name(name)
        for name in feature_names
    ]

    fig, ax = plt.subplots(figsize=(8.6, max(4.8, len(feature_names) * 0.38)))
    if shap is None or feature_frame.empty or shap_matrix.size == 0:
        ax.text(0.5, 0.5, "No SHAP data", ha="center", va="center", fontsize=10)
        ax.set_axis_off()
    else:
        plt.sca(ax)
        shap.summary_plot(
            shap_matrix,
            feature_frame,
            feature_names=display_feature_names,
            show=False,
            max_display=len(feature_names),
            plot_size=None,
        )
        ax.tick_params(axis="y", labelsize=10)
        ax.tick_params(axis="x", labelsize=9)
    ax.set_title(title, fontsize=12)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return {
        "output_path": str(output_path),
        "points": int(len(feature_frame)),
        "feature_count": int(len(feature_names)),
        "features_used": ",".join(feature_names),
        "labels_used": ",".join(display_feature_names),
    }


def main() -> None:
    args = parse_args()
    input_root = plot_prepeak_vs_recoverywin_comparison.normalize_biome_root(Path(args.input_root))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    biomes = plot_prepeak_vs_recoverywin_comparison.resolve_biomes(args.biomes, prepeak_root=input_root, recoverywin_root=input_root)

    rows: list[dict[str, object]] = []
    for biome in biomes:
        biome_dir = input_root / biome
        sample_df = pd.read_parquet(biome_dir / "dependence_sample_features.parquet")
        shap_df = pd.read_parquet(biome_dir / "dependence_sample_shap_values.parquet")
        feature_order = resolve_feature_order(biome_dir / "feature_importance.csv")
        row = plot_single_beeswarm(
            sample_df=sample_df,
            shap_df=shap_df,
            feature_order=feature_order,
            title=f"{biome} | {args.title_prefix} SHAP beeswarm",
            output_path=output_dir / f"{biome}_{args.output_suffix}_beeswarm_shortlabels.png",
            max_points=args.max_points,
            dpi=args.dpi,
        )
        row["biome"] = biome
        rows.append(row)

    pd.DataFrame(rows).to_csv(output_dir / "summary.csv", index=False)


if __name__ == "__main__":
    main()
