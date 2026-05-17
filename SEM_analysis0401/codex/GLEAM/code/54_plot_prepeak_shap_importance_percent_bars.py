#!/usr/bin/env python3
"""Plot mean absolute SHAP importance bars with percent contribution."""

from __future__ import annotations

from pathlib import Path
import importlib.util

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
PLOTS2_SCRIPT = SCRIPT_DIR / "48_redraw_prepeak_shap_plots2.py"
SPEC = importlib.util.spec_from_file_location("plots2_prepeak_redraw", PLOTS2_SCRIPT)
assert SPEC is not None
PLOTS2 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PLOTS2)

OUTPUT_PNG = PLOTS2.OUTPUT_ROOT / "shap_importance_percent_bars_5biomes_gpp_vs_reco.png"
OUTPUT_CSV = PLOTS2.OUTPUT_ROOT / "shap_importance_percent_bars_5biomes_gpp_vs_reco.csv"


def compute_importance(metric: str, biome: str) -> pd.DataFrame:
    data = PLOTS2.load_biome(metric, biome)
    features = [
        feature
        for feature in PLOTS2.FIXED_BEESWARM_FEATURES
        if feature in data.shap.columns
    ]
    rows = []
    for feature in features:
        values = pd.to_numeric(data.shap[feature], errors="coerce").to_numpy(dtype=float)
        mean_abs = float(np.nanmean(np.abs(values)))
        rows.append(
            {
                "metric": metric,
                "biome": biome,
                "feature": feature,
                "label": PLOTS2.beeswarm_label(feature),
                "mean_abs_shap": mean_abs,
            }
        )
    df = pd.DataFrame(rows)
    total = float(df["mean_abs_shap"].sum())
    df["percent"] = np.where(total > 0, df["mean_abs_shap"] / total * 100.0, np.nan)
    df = df.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)
    df["rank"] = np.arange(1, len(df) + 1)
    return df


def plot_panel(ax: plt.Axes, df: pd.DataFrame, metric: str, biome: str, max_value: float) -> None:
    work = df.sort_values("mean_abs_shap", ascending=True)
    labels = work["label"].tolist()
    values = work["mean_abs_shap"].to_numpy(dtype=float)
    percents = work["percent"].to_numpy(dtype=float)
    color = "#2b8cbe" if metric == "GPP" else "#f03b20"

    y = np.arange(len(work))
    ax.barh(y, values, color=color, alpha=0.86, height=0.72)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlim(0, max_value * 1.22)
    ax.grid(axis="x", alpha=0.18, linestyle="--", linewidth=0.6)
    ax.set_title(f"{metric} | {biome}", fontsize=10.5)
    ax.tick_params(axis="x", labelsize=8)
    ax.set_xlabel("mean(|SHAP|)", fontsize=8.5)

    for yy, value, percent in zip(y, values, percents, strict=True):
        ax.text(
            value + max_value * 0.018,
            yy,
            f"{percent:.1f}%",
            va="center",
            ha="left",
            fontsize=7.5,
            color="#333333",
        )


def main() -> None:
    all_rows = []
    panel_data: dict[tuple[str, str], pd.DataFrame] = {}
    for biome in PLOTS2.BIOMES:
        for metric in ["GPP", "RECO"]:
            df = compute_importance(metric, biome)
            panel_data[(metric, biome)] = df
            all_rows.append(df)

    importance = pd.concat(all_rows, ignore_index=True)
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    importance.to_csv(OUTPUT_CSV, index=False)

    max_value = float(importance["mean_abs_shap"].max())
    fig, axes = plt.subplots(nrows=len(PLOTS2.BIOMES), ncols=2, figsize=(16, 3.15 * len(PLOTS2.BIOMES)))
    for row, biome in enumerate(PLOTS2.BIOMES):
        for col, metric in enumerate(["GPP", "RECO"]):
            plot_panel(axes[row, col], panel_data[(metric, biome)], metric, biome, max_value)

    fig.suptitle(
        "Pre-event SHAP feature importance: mean(|SHAP|) and percent contribution",
        fontsize=15,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.982])
    fig.savefig(OUTPUT_PNG, dpi=240, bbox_inches="tight")
    plt.close(fig)
    print(OUTPUT_PNG)
    print(OUTPUT_CSV)


if __name__ == "__main__":
    main()
