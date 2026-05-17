#!/usr/bin/env python
"""Plot trend-first PRE-SHAP figures with zoomed low-PRE panels."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BIOMES = ["Cropland", "Forest", "Grassland", "Savanna", "Shrubland"]
GROUP_COLORS = {
    "expected_mild": "#355c7d",
    "expected_severe": "#b22222",
}
GROUP_LABELS = {
    "expected_mild": "expected mild",
    "expected_severe": "expected severe",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-table", required=True)
    parser.add_argument("--filtered-table", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--pre-col", default="recoverywin_total_precipitation_mean")
    parser.add_argument("--shap-col", default="pre_shap")
    parser.add_argument("--color-col", default="gpp_drop_magnitude")
    parser.add_argument("--low-pre-threshold", type=float, default=0.004)
    parser.add_argument("--zoom-max", type=float, default=0.008)
    parser.add_argument("--context-quantile", type=float, default=0.99)
    parser.add_argument("--all-bins", type=int, default=18)
    parser.add_argument("--group-bins", type=int, default=8)
    parser.add_argument("--min-bin-count", type=int, default=40)
    parser.add_argument("--clip-q-low", type=float, default=0.05)
    parser.add_argument("--clip-q-high", type=float, default=0.95)
    return parser.parse_args()


def compute_gpp_drop_magnitude(values: pd.Series) -> pd.Series:
    out = -pd.to_numeric(values, errors="coerce")
    return out.clip(lower=0)


def ensure_color_column(frame: pd.DataFrame, color_col: str) -> pd.DataFrame:
    if color_col in frame.columns:
        return frame
    if "amp_max" not in frame.columns:
        raise KeyError(f"{color_col} not found and amp_max unavailable")
    out = frame.copy()
    out[color_col] = compute_gpp_drop_magnitude(out["amp_max"])
    return out


def subset_x_range(frame: pd.DataFrame, x_col: str, x_min: float | None, x_max: float | None) -> pd.DataFrame:
    work = frame.copy()
    x = pd.to_numeric(work[x_col], errors="coerce")
    mask = np.isfinite(x)
    if x_min is not None:
        mask &= x >= x_min
    if x_max is not None:
        mask &= x <= x_max
    return work.loc[mask].copy()


def build_binned_summary(
    frame: pd.DataFrame,
    x_col: str,
    y_col: str,
    color_col: str,
    n_bins: int = 18,
    min_count: int = 40,
    x_min: float | None = None,
    x_max: float | None = None,
) -> pd.DataFrame:
    work = subset_x_range(frame, x_col=x_col, x_min=x_min, x_max=x_max)
    work = work[[x_col, y_col, color_col]].copy()
    work[x_col] = pd.to_numeric(work[x_col], errors="coerce")
    work[y_col] = pd.to_numeric(work[y_col], errors="coerce")
    work[color_col] = pd.to_numeric(work[color_col], errors="coerce")
    work = work.replace([np.inf, -np.inf], np.nan).dropna()
    if work.empty:
        return pd.DataFrame(columns=["bin_id", "count", "x_mid", "y_mid", "y_q25", "y_q75", "color_median"])

    unique_x = work[x_col].nunique(dropna=True)
    bins = max(2, min(int(n_bins), int(unique_x)))
    if bins < 2:
        return pd.DataFrame(columns=["bin_id", "count", "x_mid", "y_mid", "y_q25", "y_q75", "color_median"])
    try:
        work["bin_id"] = pd.qcut(work[x_col], q=bins, labels=False, duplicates="drop")
    except ValueError:
        return pd.DataFrame(columns=["bin_id", "count", "x_mid", "y_mid", "y_q25", "y_q75", "color_median"])
    out = (
        work.groupby("bin_id", observed=True)
        .agg(
            count=(x_col, "size"),
            x_mid=(x_col, "median"),
            y_mid=(y_col, "median"),
            y_q25=(y_col, lambda s: float(s.quantile(0.25))),
            y_q75=(y_col, lambda s: float(s.quantile(0.75))),
            color_median=(color_col, "median"),
        )
        .reset_index()
    )
    out = out[out["count"] >= int(min_count)].copy()
    return out.sort_values("x_mid").reset_index(drop=True)


def build_group_curves(
    frame: pd.DataFrame,
    x_col: str,
    y_col: str,
    group_col: str,
    n_bins: int = 8,
    min_count: int = 20,
    x_min: float | None = None,
    x_max: float | None = None,
) -> pd.DataFrame:
    work = subset_x_range(frame, x_col=x_col, x_min=x_min, x_max=x_max)
    work = work[[x_col, y_col, group_col]].copy()
    work[x_col] = pd.to_numeric(work[x_col], errors="coerce")
    work[y_col] = pd.to_numeric(work[y_col], errors="coerce")
    work = work.replace([np.inf, -np.inf], np.nan).dropna()
    rows: list[pd.DataFrame] = []
    for group, part in work.groupby(group_col, observed=True):
        unique_x = part[x_col].nunique(dropna=True)
        bins = max(2, min(int(n_bins), int(unique_x)))
        if bins < 2:
            continue
        try:
            part = part.copy()
            part["bin_id"] = pd.qcut(part[x_col], q=bins, labels=False, duplicates="drop")
        except ValueError:
            continue
        curve = (
            part.groupby("bin_id", observed=True)
            .agg(
                count=(x_col, "size"),
                x_mid=(x_col, "median"),
                y_mid=(y_col, "median"),
            )
            .reset_index(drop=True)
        )
        curve = curve[curve["count"] >= int(min_count)].copy()
        if curve.empty:
            continue
        curve[group_col] = group
        rows.append(curve)
    if not rows:
        return pd.DataFrame(columns=[group_col, "count", "x_mid", "y_mid"])
    return pd.concat(rows, ignore_index=True).sort_values([group_col, "x_mid"]).reset_index(drop=True)


def compute_color_limits(series: pd.Series, q_low: float, q_high: float) -> tuple[float, float]:
    values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if values.empty:
        return 0.0, 1.0
    low = float(values.quantile(q_low))
    high = float(values.quantile(q_high))
    if not np.isfinite(low) or not np.isfinite(high):
        return 0.0, 1.0
    if high <= low:
        high = low + 1.0
    return low, high


def plot_panel(
    ax: plt.Axes,
    full_df: pd.DataFrame,
    filtered_df: pd.DataFrame,
    pre_col: str,
    shap_col: str,
    color_col: str,
    color_limits: tuple[float, float],
    x_min: float | None,
    x_max: float | None,
    title: str,
    low_pre_threshold: float,
    all_bins: int,
    group_bins: int,
    min_bin_count: int,
):
    summary = build_binned_summary(
        full_df,
        x_col=pre_col,
        y_col=shap_col,
        color_col=color_col,
        n_bins=all_bins,
        min_count=min_bin_count,
        x_min=x_min,
        x_max=x_max,
    )
    if not summary.empty:
        ax.fill_between(
            summary["x_mid"].to_numpy(dtype=float),
            summary["y_q25"].to_numpy(dtype=float),
            summary["y_q75"].to_numpy(dtype=float),
            color="#bdbdbd",
            alpha=0.40,
            zorder=1,
            label="all IQR",
        )
        ax.plot(
            summary["x_mid"].to_numpy(dtype=float),
            summary["y_mid"].to_numpy(dtype=float),
            color="#202124",
            linewidth=2.2,
            zorder=3,
            label="all median",
        )
        scatter = ax.scatter(
            summary["x_mid"].to_numpy(dtype=float),
            summary["y_mid"].to_numpy(dtype=float),
            c=np.clip(summary["color_median"].to_numpy(dtype=float), color_limits[0], color_limits[1]),
            cmap="viridis",
            vmin=color_limits[0],
            vmax=color_limits[1],
            s=np.clip(np.sqrt(summary["count"].to_numpy(dtype=float)) * 7.0, 28, 120),
            edgecolors="#202124",
            linewidths=0.25,
            zorder=4,
        )
    else:
        scatter = None

    curves = build_group_curves(
        filtered_df,
        x_col=pre_col,
        y_col=shap_col,
        group_col="mechanism_group",
        n_bins=group_bins,
        min_count=max(8, min_bin_count // 2),
        x_min=x_min,
        x_max=x_max,
    )
    for group in ["expected_mild", "expected_severe"]:
        part = curves[curves["mechanism_group"] == group]
        if part.empty:
            continue
        ax.plot(
            part["x_mid"].to_numpy(dtype=float),
            part["y_mid"].to_numpy(dtype=float),
            color=GROUP_COLORS[group],
            linewidth=2.2,
            alpha=0.95,
            zorder=5,
            label=GROUP_LABELS[group],
        )

    ax.axhline(0.0, color="#616161", linewidth=1.0, linestyle="--", alpha=0.85, zorder=2)
    if x_min is None or (low_pre_threshold >= (x_min or 0.0) and (x_max is None or low_pre_threshold <= x_max)):
        ax.axvline(low_pre_threshold, color="#7f5539", linewidth=1.0, linestyle=":", alpha=0.95, zorder=2)
    ax.set_title(title, fontsize=11.5)
    ax.grid(alpha=0.16, linewidth=0.55)
    return scatter, summary


def summarize_biome(
    biome: str,
    full_df: pd.DataFrame,
    filtered_df: pd.DataFrame,
    pre_col: str,
    shap_col: str,
    color_col: str,
    zoom_max: float,
    context_quantile: float,
) -> pd.DataFrame:
    context_xmax = float(pd.to_numeric(full_df[pre_col], errors="coerce").quantile(context_quantile))
    rows = [
        {
            "biome": biome,
            "full_rows": int(len(full_df)),
            "filtered_rows": int(len(filtered_df)),
            "pre_median": float(pd.to_numeric(full_df[pre_col], errors="coerce").median()),
            "pre_shap_median": float(pd.to_numeric(full_df[shap_col], errors="coerce").median()),
            "gpp_drop_magnitude_median": float(pd.to_numeric(full_df[color_col], errors="coerce").median()),
            "zoom_max": zoom_max,
            "context_xmax": context_xmax,
        }
    ]
    return pd.DataFrame(rows)


def plot_biome(
    biome: str,
    full_df: pd.DataFrame,
    filtered_df: pd.DataFrame,
    args: argparse.Namespace,
    output_path: Path,
) -> pd.DataFrame:
    full_df = ensure_color_column(full_df, args.color_col)
    filtered_df = ensure_color_column(filtered_df, args.color_col)
    color_limits = compute_color_limits(full_df[args.color_col], q_low=args.clip_q_low, q_high=args.clip_q_high)
    context_xmax = float(pd.to_numeric(full_df[args.pre_col], errors="coerce").quantile(args.context_quantile))
    context_xmax = max(context_xmax, args.zoom_max * 1.25)

    fig, axes = plt.subplots(1, 2, figsize=(13.8, 5.8), sharey=True, constrained_layout=True)
    scatter_left, _ = plot_panel(
        axes[0],
        full_df=full_df,
        filtered_df=filtered_df,
        pre_col=args.pre_col,
        shap_col=args.shap_col,
        color_col=args.color_col,
        color_limits=color_limits,
        x_min=0.0,
        x_max=args.zoom_max,
        title=f"{biome} | zoomed trend (0–{args.zoom_max:.3f})",
        low_pre_threshold=args.low_pre_threshold,
        all_bins=args.all_bins,
        group_bins=args.group_bins,
        min_bin_count=args.min_bin_count,
    )
    scatter_right, _ = plot_panel(
        axes[1],
        full_df=full_df,
        filtered_df=filtered_df,
        pre_col=args.pre_col,
        shap_col=args.shap_col,
        color_col=args.color_col,
        color_limits=color_limits,
        x_min=0.0,
        x_max=context_xmax,
        title=f"{biome} | full context (≤ p{int(args.context_quantile * 100)})",
        low_pre_threshold=args.low_pre_threshold,
        all_bins=args.all_bins,
        group_bins=args.group_bins,
        min_bin_count=args.min_bin_count,
    )
    axes[0].set_ylabel("SHAP value for recovery PRE", fontsize=11)
    for ax in axes:
        ax.set_xlabel("Recovery-window precipitation mean (m/day)", fontsize=11)
    handles, labels = axes[1].get_legend_handles_labels()
    uniq: dict[str, object] = {}
    for handle, label in zip(handles, labels, strict=False):
        if label not in uniq:
            uniq[label] = handle
    axes[1].legend(uniq.values(), uniq.keys(), frameon=False, fontsize=9, loc="best")

    mappable = scatter_right if scatter_right is not None else scatter_left
    if mappable is not None:
        cbar = fig.colorbar(mappable, ax=axes.ravel().tolist(), pad=0.02, fraction=0.03)
        cbar.set_label("Median GPP drop magnitude by PRE bin", fontsize=10)

    fig.suptitle(f"{biome} | PRE-SHAP trend-first view", fontsize=13.5)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=240, bbox_inches="tight")
    plt.close(fig)

    return summarize_biome(
        biome=biome,
        full_df=full_df,
        filtered_df=filtered_df,
        pre_col=args.pre_col,
        shap_col=args.shap_col,
        color_col=args.color_col,
        zoom_max=args.zoom_max,
        context_quantile=args.context_quantile,
    )


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    full_df = pd.read_parquet(args.full_table)
    filtered_df = pd.read_parquet(args.filtered_table)

    summaries: list[pd.DataFrame] = []
    for biome in BIOMES:
        full_part = full_df[full_df["biome"] == biome].copy()
        filtered_part = filtered_df[filtered_df["biome"] == biome].copy()
        if full_part.empty:
            continue
        summaries.append(
            plot_biome(
                biome=biome,
                full_df=full_part,
                filtered_df=filtered_part,
                args=args,
                output_path=out_dir / f"{biome}_pre_shap_trend_focus.png",
            )
        )

    if summaries:
        pd.concat(summaries, ignore_index=True).to_csv(out_dir / "summary.csv", index=False)


if __name__ == "__main__":
    main()
