#!/usr/bin/env python
"""Compare background conditions for low-PRE samples split by PRE-SHAP sign."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BIOMES = ["Cropland", "Forest", "Grassland", "Savanna", "Shrubland"]
BACKGROUND_FEATURES = [
    "feature__recoverywin_SMrz_mean",
    "feature__recoverywin_VPD_mean",
    "feature__recoverywin_lai_total_mean",
    "feature__recoverywin_temperature_2m_mean",
    "feature__recoverywin_total_evaporation_mean",
]
LABELS = {
    "feature__recoverywin_SMrz_mean": "SMrz",
    "feature__recoverywin_VPD_mean": "VPD",
    "feature__recoverywin_lai_total_mean": "LAI",
    "feature__recoverywin_temperature_2m_mean": "TMP",
    "feature__recoverywin_total_evaporation_mean": "EVA",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-root", required=True)
    parser.add_argument("--pre-feature", default="feature__prepeak_total_precipitation_mean")
    parser.add_argument("--pre-shap", default="shap__prepeak_total_precipitation_mean")
    parser.add_argument("--low-quantile", type=float, default=0.2)
    parser.add_argument("--output-name", default="low_pre_shap_sign_background")
    return parser.parse_args()


def build_group_frame(
    biome_dir: Path,
    pre_feature: str,
    pre_shap: str,
    low_quantile: float,
) -> pd.DataFrame:
    df = pd.read_parquet(biome_dir / "dependence_plot_data.parquet")
    keep_cols = [pre_feature, pre_shap, *BACKGROUND_FEATURES]
    work = df[keep_cols].apply(pd.to_numeric, errors="coerce")
    threshold = work[pre_feature].quantile(low_quantile)
    work = work[work[pre_feature] <= threshold].copy()
    work["group"] = np.where(work[pre_shap] < 0, "low PRE & SHAP<0", "low PRE & SHAP>=0")
    work["biome"] = biome_dir.name
    return work


def summarize_groups(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for biome, biome_df in df.groupby("biome", observed=True):
        for group, group_df in biome_df.groupby("group", observed=True):
            row: dict[str, object] = {"biome": biome, "group": group, "n": len(group_df)}
            for col in BACKGROUND_FEATURES:
                row[f"{col}__mean"] = float(group_df[col].mean())
                row[f"{col}__median"] = float(group_df[col].median())
            rows.append(row)
    return pd.DataFrame(rows)


def add_delta_summary(summary: pd.DataFrame) -> pd.DataFrame:
    out_rows: list[dict[str, object]] = []
    for biome, biome_df in summary.groupby("biome", observed=True):
        neg = biome_df[biome_df["group"] == "low PRE & SHAP<0"]
        pos = biome_df[biome_df["group"] == "low PRE & SHAP>=0"]
        if neg.empty or pos.empty:
            continue
        row: dict[str, object] = {"biome": biome}
        row["n_neg"] = int(neg["n"].iloc[0])
        row["n_pos"] = int(pos["n"].iloc[0])
        row["neg_frac"] = float(row["n_neg"] / (row["n_neg"] + row["n_pos"]))
        for col in BACKGROUND_FEATURES:
            row[f"{LABELS[col]}_mean_neg"] = float(neg[f"{col}__mean"].iloc[0])
            row[f"{LABELS[col]}_mean_pos"] = float(pos[f"{col}__mean"].iloc[0])
            row[f"{LABELS[col]}_delta_neg_minus_pos"] = float(
                neg[f"{col}__mean"].iloc[0] - pos[f"{col}__mean"].iloc[0]
            )
        out_rows.append(row)
    return pd.DataFrame(out_rows)


def plot_background_panels(df: pd.DataFrame, output_path: Path) -> None:
    fig, axes = plt.subplots(
        nrows=len(BIOMES),
        ncols=len(BACKGROUND_FEATURES),
        figsize=(15.5, 13.5),
        sharex=False,
    )
    colors = {"low PRE & SHAP<0": "#1f77b4", "low PRE & SHAP>=0": "#d62728"}
    for i, biome in enumerate(BIOMES):
        biome_df = df[df["biome"] == biome].copy()
        for j, col in enumerate(BACKGROUND_FEATURES):
            ax = axes[i, j]
            groups = []
            labels = []
            box_colors = []
            for group in ["low PRE & SHAP<0", "low PRE & SHAP>=0"]:
                vals = biome_df.loc[biome_df["group"] == group, col].dropna().to_numpy(dtype=float)
                if len(vals) == 0:
                    continue
                groups.append(vals)
                labels.append(group.replace("low PRE & ", ""))
                box_colors.append(colors[group])
            if groups:
                bp = ax.boxplot(
                    groups,
                    labels=labels,
                    patch_artist=True,
                    widths=0.6,
                    showfliers=False,
                    medianprops={"color": "black", "linewidth": 1.2},
                    whiskerprops={"linewidth": 1.0},
                    capprops={"linewidth": 1.0},
                )
                for patch, color in zip(bp["boxes"], box_colors):
                    patch.set_facecolor(color)
                    patch.set_alpha(0.75)
            ax.set_title(f"{biome} | {LABELS[col]}", fontsize=10)
            ax.tick_params(axis="x", labelrotation=18, labelsize=8)
            ax.tick_params(axis="y", labelsize=8)
            ax.grid(alpha=0.18, linewidth=0.6)
    fig.suptitle("Low PRE samples: background contrast between PRE-SHAP<0 and PRE-SHAP>=0", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    root = Path(args.result_root)
    frames = [
        build_group_frame(root / biome, args.pre_feature, args.pre_shap, args.low_quantile)
        for biome in BIOMES
    ]
    merged = pd.concat(frames, ignore_index=True)
    out_dir = root / "diagnostics_low_pre_shap_groups"
    out_dir.mkdir(parents=True, exist_ok=True)

    merged.to_parquet(out_dir / f"{args.output_name}_samples.parquet", index=False)
    summary = summarize_groups(merged)
    summary.to_csv(out_dir / f"{args.output_name}_summary.csv", index=False)
    delta = add_delta_summary(summary)
    delta.to_csv(out_dir / f"{args.output_name}_delta.csv", index=False)
    plot_background_panels(merged, out_dir / f"{args.output_name}_boxplots.png")


if __name__ == "__main__":
    main()
