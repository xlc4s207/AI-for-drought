#!/usr/bin/env python
"""Plot biome-wise recovery PRE dependence colored by recovery and impact duration."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import Normalize


BIOMES = ["Cropland", "Forest", "Grassland", "Savanna", "Shrubland"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--pre-col", default="recoverywin_total_precipitation_mean")
    parser.add_argument("--shap-col", default="recoverywin_total_precipitation_mean__shap")
    parser.add_argument("--recover-col", default="t_recover_to_baseline_abs_peak")
    parser.add_argument("--impact-col", default="t_impact")
    parser.add_argument("--clip-lower-quantile", type=float, default=0.02)
    parser.add_argument("--clip-upper-quantile", type=float, default=0.98)
    return parser.parse_args()


def add_trend(ax: plt.Axes, x: np.ndarray, y: np.ndarray) -> None:
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 20:
        return
    x2 = x[mask]
    y2 = y[mask]
    order = np.argsort(x2)
    x2 = x2[order]
    y2 = y2[order]
    trend = pd.Series(y2).rolling(window=max(31, len(y2) // 40), center=True, min_periods=1).mean()
    ax.plot(x2, trend.to_numpy(), color="#c83349", linewidth=2.1, alpha=0.95, zorder=3)


def build_panels(t_recover: np.ndarray, t_impact_pos: np.ndarray) -> list[tuple[np.ndarray, str, str, bool]]:
    return [
        (t_recover, "t_recover", "viridis", False),
        (t_impact_pos, "|t_impact|", "viridis", True),
    ]


def plot_one_biome(df: pd.DataFrame, biome: str, args: argparse.Namespace, output_path: Path) -> None:
    work = df[df["biome"] == biome].copy()
    if work.empty:
        return

    x = pd.to_numeric(work[args.pre_col], errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(work[args.shap_col], errors="coerce").to_numpy(dtype=float)
    t_recover = pd.to_numeric(work[args.recover_col], errors="coerce").to_numpy(dtype=float)
    t_impact_pos = np.abs(pd.to_numeric(work[args.impact_col], errors="coerce").to_numpy(dtype=float))

    fig, axes = plt.subplots(1, 2, figsize=(13.8, 5.6), sharex=True, sharey=True)
    panels = build_panels(t_recover, t_impact_pos)
    for ax, (cvals, clabel, cmap, use_robust_clip) in zip(axes, panels):
        mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(cvals)
        norm = None
        if use_robust_clip and int(mask.sum()) >= 20:
            clipped = cvals[mask]
            q_low = float(np.nanquantile(clipped, args.clip_lower_quantile))
            q_high = float(np.nanquantile(clipped, args.clip_upper_quantile))
            if np.isfinite(q_low) and np.isfinite(q_high) and q_high > q_low:
                norm = Normalize(vmin=q_low, vmax=q_high, clip=True)
        sc = ax.scatter(
            x[mask],
            y[mask],
            c=cvals[mask],
            cmap=cmap,
            norm=norm,
            s=14,
            alpha=0.58,
            edgecolors="none",
            zorder=2,
        )
        add_trend(ax, x[mask], y[mask])
        ax.axhline(0.0, color="#6e6e6e", linewidth=1.0, linestyle="--", alpha=0.8, zorder=1)
        ax.set_title(f"{biome} | color={clabel}", fontsize=12)
        ax.set_xlabel("Recovery-window precipitation mean (m/day)", fontsize=11)
        ax.grid(alpha=0.18, linewidth=0.6)
        cbar = fig.colorbar(sc, ax=ax, fraction=0.045, pad=0.02)
        cbar.set_label(clabel, fontsize=10)
        cbar.ax.tick_params(labelsize=9)
    axes[0].set_ylabel("SHAP value for recovery PRE", fontsize=11)
    fig.suptitle(f"{biome} recovery PRE dependence", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    df = pd.read_parquet(args.samples)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, object]] = []
    for biome in BIOMES:
        out_png = out_dir / f"{biome}_recovery_pre_shap_colored.png"
        plot_one_biome(df, biome, args, out_png)
        biome_df = df[df["biome"] == biome].copy()
        summary_rows.append(
            {
                "biome": biome,
                "rows": int(len(biome_df)),
                "negative_t_impact_count": int((pd.to_numeric(biome_df[args.impact_col], errors="coerce") < 0).sum()),
                "zero_t_impact_count": int((pd.to_numeric(biome_df[args.impact_col], errors="coerce") == 0).sum()),
                "min_t_impact_raw": float(pd.to_numeric(biome_df[args.impact_col], errors="coerce").min()),
                "max_t_impact_raw": float(pd.to_numeric(biome_df[args.impact_col], errors="coerce").max()),
                "note": "Plot uses abs(t_impact) for color mapping.",
                "output_png": str(out_png),
            }
        )
    pd.DataFrame(summary_rows).to_csv(out_dir / "summary.csv", index=False)


if __name__ == "__main__":
    main()
