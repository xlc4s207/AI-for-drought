#!/usr/bin/env python
"""Plot severity-stratified SHAP direction contrasts for PRE and SSRD."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


FEATURE_LABELS = {
    "recoverywin_total_precipitation_mean": "PRE",
    "recoverywin_ssrd_mean": "SSRD",
}

SEVERITY_LABELS = {
    "intensity": "intensity",
    "onset_drop": "onset_drop",
    "days_below_p20": "days_below_p20",
    "amp_max": "amp_max",
    "t_impact": "t_impact",
}

GROUP_ORDER = ["q1", "q2", "q3"]
BIOME_ORDER = ["Forest", "Grassland", "Cropland", "Shrubland", "Savanna"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def prepare_matrix(
    df: pd.DataFrame,
    feature_name: str,
    severity_var: str,
) -> tuple[np.ndarray, list[str]]:
    subset = df[
        (df["focus_feature"].astype(str) == feature_name)
        & (df["severity_var"].astype(str) == severity_var)
    ].copy()
    subset["delta_high_low_shap"] = pd.to_numeric(subset["delta_high_low_shap"], errors="coerce")

    row_labels: list[str] = []
    values: list[list[float]] = []
    for biome in BIOME_ORDER:
        biome_df = subset[subset["biome"].astype(str) == biome]
        if biome_df.empty:
            continue
        row_labels.append(biome)
        row_values: list[float] = []
        for group in GROUP_ORDER:
            value = biome_df.loc[
                biome_df["severity_group"].astype(str) == group, "delta_high_low_shap"
            ]
            row_values.append(float(value.iloc[0]) if not value.empty else np.nan)
        values.append(row_values)
    return np.asarray(values, dtype=float), row_labels


def draw_panel(
    ax: plt.Axes,
    values: np.ndarray,
    row_labels: list[str],
    title: str,
    vmax: float,
) -> None:
    if values.size == 0:
        ax.axis("off")
        ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=12)
        return

    im = ax.imshow(values, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_title(title, fontsize=13, pad=8)
    ax.set_xticks(np.arange(len(GROUP_ORDER)))
    ax.set_xticklabels(GROUP_ORDER, fontsize=10)
    ax.set_yticks(np.arange(len(row_labels)))
    ax.set_yticklabels(row_labels, fontsize=10)
    ax.set_xlabel("Severity group", fontsize=10)

    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            value = values[i, j]
            if np.isnan(value):
                text = "NA"
                color = "#555555"
            else:
                text = f"{value:+.1f}"
                color = "black" if abs(value) < vmax * 0.55 else "white"
            ax.text(j, i, text, ha="center", va="center", fontsize=9.5, color=color)

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks(np.arange(-0.5, len(GROUP_ORDER), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(row_labels), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.5)
    ax.tick_params(which="minor", bottom=False, left=False)
    return im


def save_severity_figure(
    df: pd.DataFrame,
    severity_var: str,
    output_path: Path,
) -> None:
    pre_values, row_labels = prepare_matrix(
        df, "recoverywin_total_precipitation_mean", severity_var
    )
    ssrd_values, _ = prepare_matrix(df, "recoverywin_ssrd_mean", severity_var)

    combined = np.concatenate(
        [arr[np.isfinite(arr)] for arr in (pre_values, ssrd_values) if arr.size],
        axis=0,
    )
    vmax = max(1.0, float(np.nanmax(np.abs(combined)))) if combined.size else 1.0

    fig, axes = plt.subplots(1, 2, figsize=(10.8, max(4.8, 0.75 * max(1, len(row_labels)) + 2.2)))
    im = draw_panel(axes[0], pre_values, row_labels, "PRE", vmax)
    draw_panel(axes[1], ssrd_values, row_labels, "SSRD", vmax)
    axes[1].set_yticklabels([])

    cbar = fig.colorbar(im, ax=axes, shrink=0.92, pad=0.02)
    cbar.set_label("delta_high_low_shap", fontsize=10)
    cbar.ax.tick_params(labelsize=9)

    fig.suptitle(
        f"Severity-stratified SHAP direction contrast: {SEVERITY_LABELS.get(severity_var, severity_var)}",
        fontsize=15,
        y=0.98,
    )
    fig.text(
        0.5,
        0.02,
        "Negative: higher values tend to shorten recovery; Positive: higher values tend to prolong recovery",
        ha="center",
        fontsize=10,
    )
    fig.tight_layout(rect=(0.02, 0.05, 0.98, 0.95))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_overview_markdown(output_dir: Path, severity_vars: list[str]) -> None:
    lines = [
        "# Severity-stratified PRE vs SSRD direction figures",
        "",
        "## Reading guide",
        "",
        "- Color and number both represent `delta_high_low_shap`.",
        "- Negative values: larger feature values tend to shorten recovery time.",
        "- Positive values: larger feature values tend to prolong recovery time.",
        "- PRE is shown as a reference panel; SSRD is the main conditional-effect panel.",
        "",
        "## Figures",
        "",
    ]
    for severity_var in severity_vars:
        lines.append(
            f"- `{severity_var}`: `{output_dir / f'severity_{severity_var}_pre_vs_ssrd.png'}`"
        )
    (output_dir / "severity_pre_vs_ssrd_figure_guide.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    input_csv = Path(args.input_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_csv)
    severity_vars = [
        var
        for var in ["intensity", "onset_drop", "days_below_p20", "amp_max", "t_impact"]
        if var in set(df["severity_var"].astype(str))
    ]
    for severity_var in severity_vars:
        save_severity_figure(
            df,
            severity_var,
            output_dir / f"severity_{severity_var}_pre_vs_ssrd.png",
        )
    save_overview_markdown(output_dir, severity_vars)
    print(f"[DONE] figures saved to {output_dir}")


if __name__ == "__main__":
    main()
