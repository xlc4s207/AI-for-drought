#!/usr/bin/env python
"""Plot side-by-side prepeak vs shock dependence comparisons by biome."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BIOMES = ["Forest", "Grassland", "Savanna", "Cropland", "Shrubland"]
PHASES = ("prepeak", "shock")
CORE_FEATURES = [
    "total_precipitation_mean",
    "total_evaporation_mean",
    "ssrd_mean",
    "strd_mean",
    "VPD_mean",
    "SMrz_mean",
]
FEATURE_LABELS = {
    "total_precipitation_mean": "PRE",
    "total_evaporation_mean": "EVA",
    "ssrd_mean": "SSRD",
    "strd_mean": "STRD",
    "VPD_mean": "VPD",
    "SMrz_mean": "SMrz",
}
PHASE_TITLES = {
    "prepeak": "Prepeak",
    "shock": "Shock",
}


@dataclass(frozen=True)
class PhaseColumns:
    feature_col: str
    shap_col: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepeak-root", required=True)
    parser.add_argument("--shock-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--clip-lower-quantile", type=float, default=0.01)
    parser.add_argument("--clip-upper-quantile", type=float, default=0.99)
    parser.add_argument("--point-alpha", type=float, default=0.22)
    parser.add_argument("--point-size", type=float, default=7.0)
    return parser.parse_args()


def build_phase_columns(phase: str, feature_name: str) -> PhaseColumns:
    if phase not in PHASES:
        raise ValueError(f"Unsupported phase: {phase}")
    full_name = f"{phase}_{feature_name}"
    return PhaseColumns(
        feature_col=f"feature__{full_name}",
        shap_col=f"shap__{full_name}",
    )


def load_phase_frame(root: Path, biome: str) -> pd.DataFrame:
    path = root / biome / "dependence_plot_data.parquet"
    return pd.read_parquet(path)


def compute_shared_limits(
    prepeak_df: pd.DataFrame,
    shock_df: pd.DataFrame,
    feature_name: str,
    q_low: float,
    q_high: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    pre_cols = build_phase_columns("prepeak", feature_name)
    shock_cols = build_phase_columns("shock", feature_name)

    x = pd.concat(
        [
            pd.to_numeric(prepeak_df[pre_cols.feature_col], errors="coerce"),
            pd.to_numeric(shock_df[shock_cols.feature_col], errors="coerce"),
        ],
        ignore_index=True,
    ).replace([np.inf, -np.inf], np.nan).dropna()
    y = pd.concat(
        [
            pd.to_numeric(prepeak_df[pre_cols.shap_col], errors="coerce"),
            pd.to_numeric(shock_df[shock_cols.shap_col], errors="coerce"),
        ],
        ignore_index=True,
    ).replace([np.inf, -np.inf], np.nan).dropna()

    if x.empty or y.empty:
        return (0.0, 1.0), (-1.0, 1.0)

    x_low = float(x.quantile(q_low))
    x_high = float(x.quantile(q_high))
    y_low = float(y.quantile(q_low))
    y_high = float(y.quantile(q_high))

    if not np.isfinite(x_low) or not np.isfinite(x_high) or x_low == x_high:
        x_low = float(x.min())
        x_high = float(x.max())
    if not np.isfinite(y_low) or not np.isfinite(y_high) or y_low == y_high:
        y_low = float(y.min())
        y_high = float(y.max())

    x_pad = max((x_high - x_low) * 0.06, 1e-9)
    y_pad = max((y_high - y_low) * 0.08, 1e-9)
    return (x_low - x_pad, x_high + x_pad), (y_low - y_pad, y_high + y_pad)


def add_trend(ax: plt.Axes, x: np.ndarray, y: np.ndarray) -> None:
    if len(x) < 20:
        return
    order = np.argsort(x)
    x_sorted = x[order]
    y_sorted = y[order]
    window = max(15, len(x_sorted) // 30)
    trend = pd.Series(y_sorted).rolling(window=window, center=True, min_periods=1).mean()
    ax.plot(x_sorted, trend.to_numpy(), color="#c83349", linewidth=1.8, alpha=0.95, zorder=3)


def plot_phase_panel(
    ax: plt.Axes,
    frame: pd.DataFrame,
    phase: str,
    feature_name: str,
    xlim: tuple[float, float],
    ylim: tuple[float, float],
    args: argparse.Namespace,
) -> int:
    cols = build_phase_columns(phase, feature_name)
    x = pd.to_numeric(frame[cols.feature_col], errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(frame[cols.shap_col], errors="coerce").to_numpy(dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]

    ax.scatter(
        x,
        y,
        s=args.point_size,
        alpha=args.point_alpha,
        color="#2f6b8a",
        edgecolors="none",
        zorder=2,
    )
    add_trend(ax, x, y)
    ax.axhline(0.0, color="#666666", linewidth=1.0, linestyle="--", alpha=0.85, zorder=1)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.grid(alpha=0.18, linewidth=0.6)
    ax.set_title(PHASE_TITLES[phase], fontsize=11.5)
    return int(mask.sum())


def plot_biome(
    biome: str,
    prepeak_df: pd.DataFrame,
    shock_df: pd.DataFrame,
    output_path: Path,
    args: argparse.Namespace,
) -> list[dict[str, object]]:
    fig, axes = plt.subplots(len(CORE_FEATURES), 2, figsize=(12.4, 19.0))
    summary_rows: list[dict[str, object]] = []

    for row_idx, feature_name in enumerate(CORE_FEATURES):
        label = FEATURE_LABELS[feature_name]
        xlim, ylim = compute_shared_limits(
            prepeak_df,
            shock_df,
            feature_name=feature_name,
            q_low=args.clip_lower_quantile,
            q_high=args.clip_upper_quantile,
        )
        for col_idx, phase in enumerate(PHASES):
            ax = axes[row_idx, col_idx]
            source = prepeak_df if phase == "prepeak" else shock_df
            n_points = plot_phase_panel(
                ax,
                frame=source,
                phase=phase,
                feature_name=feature_name,
                xlim=xlim,
                ylim=ylim,
                args=args,
            )
            if row_idx == len(CORE_FEATURES) - 1:
                ax.set_xlabel(label, fontsize=10.5)
            if col_idx == 0:
                ax.set_ylabel(f"SHAP for {label}", fontsize=10.5)
            summary_rows.append(
                {
                    "biome": biome,
                    "phase": phase,
                    "feature_name": feature_name,
                    "points": n_points,
                    "x_min": xlim[0],
                    "x_max": xlim[1],
                    "y_min": ylim[0],
                    "y_max": ylim[1],
                    "output_png": str(output_path),
                }
            )

    fig.suptitle(f"{biome} | Prepeak vs Shock dependence comparison", fontsize=15)
    fig.tight_layout(rect=[0, 0, 1, 0.985])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return summary_rows


def main() -> None:
    args = parse_args()
    if not 0.0 <= args.clip_lower_quantile < args.clip_upper_quantile <= 1.0:
        raise ValueError("Need 0 <= clip-lower-quantile < clip-upper-quantile <= 1.")

    prepeak_root = Path(args.prepeak_root)
    shock_root = Path(args.shock_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, object]] = []
    for biome in BIOMES:
        prepeak_df = load_phase_frame(prepeak_root, biome)
        shock_df = load_phase_frame(shock_root, biome)
        all_rows.extend(
            plot_biome(
                biome=biome,
                prepeak_df=prepeak_df,
                shock_df=shock_df,
                output_path=output_dir / f"{biome}_prepeak_vs_shock_core_dependence.png",
                args=args,
            )
        )

    pd.DataFrame(all_rows).to_csv(output_dir / "summary.csv", index=False)


if __name__ == "__main__":
    main()
