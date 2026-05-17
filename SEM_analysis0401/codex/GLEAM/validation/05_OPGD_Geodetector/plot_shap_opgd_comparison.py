#!/usr/bin/env python3
"""Plot SHAP, OPGD, reliability, and interaction comparison figures."""

from __future__ import annotations

from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_validation import FEATURES, METRICS, SHAP_ROOTS, SHORT_LABELS  # noqa: E402


WORK_DIR = Path(__file__).resolve().parent
FIG_DIR = WORK_DIR / "figures"
BIOME_ORDER = ["Cropland", "Forest", "Grassland", "Savanna", "Shrubland"]
ROW_ORDER = [(metric, biome) for metric in METRICS for biome in BIOME_ORDER]
FEATURE_ORDER = FEATURES
FEATURE_LABELS = [SHORT_LABELS.get(feature, feature) for feature in FEATURE_ORDER]

TOP3_NONE = 0
TOP3_SHAP_ONLY = 1
TOP3_OPGD_ONLY = 2
TOP3_BOTH = 3
RELIABILITY_TO_VALUE = {"Low": 0, "Medium": 1, "High": 2}


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
            "font.size": 8,
            "axes.titlesize": 10,
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def row_labels(row_order: list[tuple[str, str]]) -> list[str]:
    return [f"{metric} {biome}" for metric, biome in row_order]


def matrix_from_long_table(
    table: pd.DataFrame,
    row_order: list[tuple[str, str]],
    feature_order: list[str],
    value_col: str,
) -> np.ndarray:
    matrix = np.full((len(row_order), len(feature_order)), np.nan, dtype=float)
    lookup = {
        (row.metric, row.biome, row.feature): getattr(row, value_col)
        for row in table.itertuples(index=False)
    }
    for row_idx, (metric, biome) in enumerate(row_order):
        for col_idx, feature in enumerate(feature_order):
            value = lookup.get((metric, biome, feature), np.nan)
            matrix[row_idx, col_idx] = float(value) if pd.notna(value) else np.nan
    return matrix


def load_shap_long_table() -> pd.DataFrame:
    rows = []
    for metric, biome in ROW_ORDER:
        path = SHAP_ROOTS[metric] / biome / "feature_importance.csv"
        shap = pd.read_csv(path)
        for row in shap.itertuples(index=False):
            if row.feature in FEATURE_ORDER:
                rows.append(
                    {
                        "metric": metric,
                        "biome": biome,
                        "feature": row.feature,
                        "label": SHORT_LABELS.get(row.feature, row.feature),
                        "importance": float(row.importance),
                    }
                )
    return pd.DataFrame(rows)


def load_opgd_long_table(work_dir: Path = WORK_DIR) -> pd.DataFrame:
    return pd.read_csv(work_dir / "opgd_factor_q.csv")


def load_reliability_long_table(work_dir: Path = WORK_DIR) -> pd.DataFrame:
    return pd.read_csv(work_dir / "reliability" / "reliability_score.csv")


def top3_feature_set(group: pd.DataFrame, value_col: str) -> set[str]:
    return set(group.sort_values(value_col, ascending=False).head(3)["feature"])


def top3_flag_matrix(
    opgd: pd.DataFrame,
    shap: pd.DataFrame,
    row_order: list[tuple[str, str]],
    feature_order: list[str],
) -> np.ndarray:
    flags = np.zeros((len(row_order), len(feature_order)), dtype=int)
    for row_idx, (metric, biome) in enumerate(row_order):
        opgd_group = opgd[(opgd["metric"] == metric) & (opgd["biome"] == biome)]
        shap_group = shap[(shap["metric"] == metric) & (shap["biome"] == biome)]
        opgd_top = top3_feature_set(opgd_group, "q")
        shap_top = top3_feature_set(shap_group, "importance")
        for col_idx, feature in enumerate(feature_order):
            in_opgd = feature in opgd_top
            in_shap = feature in shap_top
            if in_opgd and in_shap:
                flags[row_idx, col_idx] = TOP3_BOTH
            elif in_shap:
                flags[row_idx, col_idx] = TOP3_SHAP_ONLY
            elif in_opgd:
                flags[row_idx, col_idx] = TOP3_OPGD_ONLY
    return flags


def reliability_matrix(reliability: pd.DataFrame, row_order: list[tuple[str, str]], feature_order: list[str]) -> np.ndarray:
    encoded = reliability.copy()
    encoded["grade_value"] = encoded["reliability_grade"].map(RELIABILITY_TO_VALUE)
    return matrix_from_long_table(encoded, row_order, feature_order, "grade_value")


def setup_heatmap_axis(ax, title: str, show_y: bool) -> None:
    ax.set_title(title, fontweight="bold", pad=8)
    ax.set_xticks(np.arange(len(FEATURE_LABELS)))
    ax.set_xticklabels(FEATURE_LABELS, rotation=45, ha="right")
    ax.set_yticks(np.arange(len(ROW_ORDER)))
    ax.set_yticklabels(row_labels(ROW_ORDER) if show_y else [])
    ax.tick_params(length=0)
    ax.set_xticks(np.arange(-0.5, len(FEATURE_LABELS), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(ROW_ORDER), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.8)
    for spine in ax.spines.values():
        spine.set_visible(False)


def overlay_top3_markers(ax, flags: np.ndarray) -> None:
    for row_idx in range(flags.shape[0]):
        for col_idx in range(flags.shape[1]):
            flag = flags[row_idx, col_idx]
            if flag == TOP3_BOTH:
                ax.scatter(col_idx, row_idx, s=32, marker="o", facecolor="black", edgecolor="black", linewidth=0.7)
            elif flag == TOP3_SHAP_ONLY:
                ax.scatter(col_idx, row_idx, s=34, marker="o", facecolor="white", edgecolor="#0072B2", linewidth=1.1)
            elif flag == TOP3_OPGD_ONLY:
                ax.scatter(col_idx, row_idx, s=34, marker="s", facecolor="white", edgecolor="#D55E00", linewidth=1.1)


def continuous_heatmap_colormap():
    return plt.get_cmap("RdYlGn_r").copy()


def save_figure(fig, stem: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / f"{stem}.png", dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(FIG_DIR / f"{stem}.pdf", bbox_inches="tight", facecolor="white")


def plot_main_matrix() -> None:
    configure_style()
    shap = load_shap_long_table()
    opgd = load_opgd_long_table()
    reliability = load_reliability_long_table()

    shap_matrix = matrix_from_long_table(shap, ROW_ORDER, FEATURE_ORDER, "importance")
    opgd_matrix = matrix_from_long_table(opgd, ROW_ORDER, FEATURE_ORDER, "q")
    rel_matrix = reliability_matrix(reliability, ROW_ORDER, FEATURE_ORDER)
    flags = top3_flag_matrix(opgd, shap, ROW_ORDER, FEATURE_ORDER)

    fig, axes = plt.subplots(
        1,
        3,
        figsize=(14.6, 5.8),
        gridspec_kw={"width_ratios": [1.0, 1.0, 1.03], "wspace": 0.16},
    )

    im_shap = axes[0].imshow(shap_matrix, aspect="auto", cmap=continuous_heatmap_colormap())
    setup_heatmap_axis(axes[0], "A  SHAP mean |value|", show_y=True)
    cbar = fig.colorbar(im_shap, ax=axes[0], fraction=0.046, pad=0.02)
    cbar.set_label("mean |SHAP|")

    im_q = axes[1].imshow(opgd_matrix, aspect="auto", cmap=continuous_heatmap_colormap(), vmin=0, vmax=np.nanmax(opgd_matrix))
    setup_heatmap_axis(axes[1], "B  OPGD q statistic", show_y=False)
    cbar = fig.colorbar(im_q, ax=axes[1], fraction=0.046, pad=0.02)
    cbar.set_label("q")

    rel_cmap = ListedColormap(["#E5E5E5", "#9ECAE1", "#08519C"])
    rel_norm = BoundaryNorm([-0.5, 0.5, 1.5, 2.5], rel_cmap.N)
    im_rel = axes[2].imshow(rel_matrix, aspect="auto", cmap=rel_cmap, norm=rel_norm)
    setup_heatmap_axis(axes[2], "C  Reliability and Top3 overlap", show_y=False)
    overlay_top3_markers(axes[2], flags)
    cbar = fig.colorbar(im_rel, ax=axes[2], fraction=0.046, pad=0.02, ticks=[0, 1, 2])
    cbar.ax.set_yticklabels(["Low", "Medium", "High"])
    cbar.set_label("reliability")

    legend_handles = [
        Line2D([0], [0], marker="o", color="black", markerfacecolor="black", linestyle="None", markersize=5, label="SHAP Top3 + OPGD Top3"),
        Line2D([0], [0], marker="o", color="#0072B2", markerfacecolor="white", linestyle="None", markersize=5, label="SHAP Top3 only"),
        Line2D([0], [0], marker="s", color="#D55E00", markerfacecolor="white", linestyle="None", markersize=5, label="OPGD Top3 only"),
    ]
    fig.legend(handles=legend_handles, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.55, -0.02))
    fig.suptitle("SHAP prediction contribution vs. OPGD spatial stratified heterogeneity", y=1.02, fontweight="bold")
    save_figure(fig, "shap_opgd_reliability_matrix")
    plt.close(fig)


def interaction_matrix(rows: pd.DataFrame, labels: list[str]) -> np.ndarray:
    matrix = np.full((len(labels), len(labels)), np.nan, dtype=float)
    label_to_idx = {label: idx for idx, label in enumerate(labels)}
    for row in rows.itertuples(index=False):
        if row.label_1 not in label_to_idx or row.label_2 not in label_to_idx:
            continue
        i = label_to_idx[row.label_1]
        j = label_to_idx[row.label_2]
        matrix[i, j] = float(row.q_interaction)
        matrix[j, i] = float(row.q_interaction)
    return matrix


def interaction_colormap():
    return plt.get_cmap("RdYlGn_r").copy()


def plot_interaction_heatmaps() -> None:
    configure_style()
    interactions = pd.read_csv(WORK_DIR / "opgd_interactions.csv")
    fig, axes = plt.subplots(2, 5, figsize=(13.5, 6.6), constrained_layout=True)
    vmax = float(np.nanmax(interactions["q_interaction"]))
    for idx, (metric, biome) in enumerate(ROW_ORDER):
        ax = axes.flat[idx]
        sub = interactions[(interactions["metric"] == metric) & (interactions["biome"] == biome)].copy()
        labels = sorted(set(sub["label_1"]) | set(sub["label_2"]), key=lambda label: FEATURE_LABELS.index(label) if label in FEATURE_LABELS else 999)
        matrix = interaction_matrix(sub, labels)
        im = ax.imshow(matrix, aspect="equal", cmap=interaction_colormap(), vmin=0, vmax=vmax)
        ax.set_title(f"{metric} {biome}", fontsize=8, fontweight="bold")
        ax.set_xticks(np.arange(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=6)
        ax.set_yticks(np.arange(len(labels)))
        ax.set_yticklabels(labels, fontsize=6)
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
        top = sub.sort_values("q_interaction", ascending=False).head(1)
        if not top.empty:
            row = top.iloc[0]
            ax.text(
                0.5,
                -0.28,
                f"top: {row['label_1']}+{row['label_2']} q={row['q_interaction']:.3f}",
                transform=ax.transAxes,
                ha="center",
                va="top",
                fontsize=6,
            )
    cbar = fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.72, pad=0.01)
    cbar.set_label("interaction q")
    fig.suptitle("OPGD interaction detector: pairwise q among SHAP top features", fontweight="bold")
    save_figure(fig, "opgd_interaction_heatmaps")
    plt.close(fig)


def main() -> None:
    plot_main_matrix()
    plot_interaction_heatmaps()
    print(FIG_DIR / "shap_opgd_reliability_matrix.png")
    print(FIG_DIR / "opgd_interaction_heatmaps.png")


if __name__ == "__main__":
    main()
