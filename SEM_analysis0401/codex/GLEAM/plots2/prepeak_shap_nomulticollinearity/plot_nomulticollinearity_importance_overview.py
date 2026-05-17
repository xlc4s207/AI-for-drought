#!/usr/bin/env python3
"""Plot 5-biome GPP/RECO importance overview for transformed SHAP runs."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/plots2/prepeak_shap_nomulticollinearity")
BIOMES = ["Forest", "Grassland", "Savanna", "Cropland", "Shrubland"]
METRICS = ["GPP", "RECO"]
METHODS = ["group_pca", "orthogonal_decomposition"]


def load_method(method: str) -> pd.DataFrame:
    rows = []
    for metric in METRICS:
        for biome in BIOMES:
            p = ROOT / method / metric / biome / "feature_importance.csv"
            df = pd.read_csv(p)
            df["method"] = method
            df["metric"] = metric
            df["biome"] = biome
            rows.append(df)
    return pd.concat(rows, ignore_index=True)


def plot_method(method: str, df: pd.DataFrame) -> None:
    labels = df["display_label"].drop_duplicates().tolist()
    n_rows = len(BIOMES)
    n_cols = len(METRICS)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(12, max(10, n_rows * 2.25)), sharex=False)
    colors = {"GPP": "#2f6b8a", "RECO": "#a23b3b"}
    for r, biome in enumerate(BIOMES):
        for c, metric in enumerate(METRICS):
            ax = axes[r, c]
            sub = df[(df["metric"] == metric) & (df["biome"] == biome)].sort_values("percent", ascending=True)
            ax.barh(sub["display_label"], sub["percent"], color=colors[metric], alpha=0.86)
            for y, val in enumerate(sub["percent"]):
                ax.text(val + 0.6, y, f"{val:.1f}%", va="center", fontsize=8)
            ax.set_xlim(0, max(5, sub["percent"].max() * 1.22))
            ax.set_title(f"{biome} | {metric}", fontsize=11)
            ax.set_xlabel("Contribution (%)")
            ax.tick_params(axis="y", labelsize=8)
            ax.tick_params(axis="x", labelsize=8)
    title = "Grouped PCA SHAP importance" if method == "group_pca" else "Orthogonal decomposition SHAP importance"
    fig.suptitle(title, fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.975))
    fig.savefig(ROOT / f"{method}_importance_percent_bars_5biomes_gpp_vs_reco.png", dpi=260)
    plt.close(fig)


def main() -> None:
    all_rows = []
    for method in METHODS:
        df = load_method(method)
        all_rows.append(df)
        plot_method(method, df)
    pd.concat(all_rows, ignore_index=True).to_csv(ROOT / "nomulticollinearity_feature_importance_all.csv", index=False)
    print(f"Wrote overview plots under {ROOT}")


if __name__ == "__main__":
    main()
