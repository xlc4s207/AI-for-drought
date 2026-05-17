#!/usr/bin/env python
"""Plot PRE-vs-PRE-SHAP dependence from full-sample mechanism-filtered rows."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BIOMES = ["Cropland", "Forest", "Grassland", "Savanna", "Shrubland"]
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
        raise KeyError(f"{color_col} not found and amp_max unavailable to derive it")
    out = frame.copy()
    out[color_col] = compute_gpp_drop_magnitude(out["amp_max"])
    return out


def compute_color_limits(series: pd.Series, q_low: float, q_high: float) -> tuple[float, float]:
    values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if values.empty:
        return 0.0, 1.0
    low = float(values.quantile(q_low))
    high = float(values.quantile(q_high))
    if not np.isfinite(low) or not np.isfinite(high):
        return 0.0, 1.0
    if high <= low:
        center = float(values.median())
        spread = float(values.std())
        if not np.isfinite(spread) or spread <= 0:
            spread = max(abs(center) * 0.1, 1.0)
        return center - spread, center + spread
    return low, high


def build_group_trend(frame: pd.DataFrame, pre_col: str, shap_col: str, bins: int = 18) -> pd.DataFrame:
    work = frame[[pre_col, shap_col]].copy()
    work[pre_col] = pd.to_numeric(work[pre_col], errors="coerce")
    work[shap_col] = pd.to_numeric(work[shap_col], errors="coerce")
    work = work.replace([np.inf, -np.inf], np.nan).dropna()
    if len(work) < max(60, bins * 3):
        return pd.DataFrame(columns=["pre_mid", "shap_median"])
    try:
        work["pre_bin"] = pd.qcut(work[pre_col], q=bins, duplicates="drop")
    except ValueError:
        return pd.DataFrame(columns=["pre_mid", "shap_median"])
    grouped = work.groupby("pre_bin", observed=True)
    trend = grouped.agg(
        pre_mid=(pre_col, "median"),
        shap_median=(shap_col, "median"),
    )
    return trend.reset_index(drop=True)


def summarize_biome(
    biome: str,
    full_df: pd.DataFrame,
    filtered_df: pd.DataFrame,
    pre_col: str,
    shap_col: str,
    color_col: str,
    q_low: float,
    q_high: float,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    low, high = compute_color_limits(filtered_df[color_col], q_low=q_low, q_high=q_high)
    rows.append(
        {
            "biome": biome,
            "group": "all_filtered",
            "rows": int(len(filtered_df)),
            "background_rows": int(len(full_df)),
            "pre_median": float(pd.to_numeric(filtered_df[pre_col], errors="coerce").median()),
            "pre_shap_median": float(pd.to_numeric(filtered_df[shap_col], errors="coerce").median()),
            "gpp_drop_magnitude_median": float(pd.to_numeric(filtered_df[color_col], errors="coerce").median()),
            "color_clip_low": low,
            "color_clip_high": high,
        }
    )
    for group, part in filtered_df.groupby("mechanism_group", observed=True):
        rows.append(
            {
                "biome": biome,
                "group": str(group),
                "rows": int(len(part)),
                "background_rows": int(len(full_df)),
                "pre_median": float(pd.to_numeric(part[pre_col], errors="coerce").median()),
                "pre_shap_median": float(pd.to_numeric(part[shap_col], errors="coerce").median()),
                "gpp_drop_magnitude_median": float(pd.to_numeric(part[color_col], errors="coerce").median()),
                "color_clip_low": low,
                "color_clip_high": high,
            }
        )
    return pd.DataFrame(rows)


def plot_biome(
    biome: str,
    full_df: pd.DataFrame,
    filtered_df: pd.DataFrame,
    pre_col: str,
    shap_col: str,
    color_col: str,
    low_pre_threshold: float,
    q_low: float,
    q_high: float,
    output_path: Path,
) -> pd.DataFrame:
    full_df = ensure_color_column(full_df, color_col)
    filtered_df = ensure_color_column(filtered_df, color_col)
    color_low, color_high = compute_color_limits(full_df[color_col], q_low=q_low, q_high=q_high)
    fig, ax = plt.subplots(figsize=(8.2, 6.1))

    full_x = pd.to_numeric(full_df[pre_col], errors="coerce").to_numpy(dtype=float)
    full_y = pd.to_numeric(full_df[shap_col], errors="coerce").to_numpy(dtype=float)
    full_c = pd.to_numeric(full_df[color_col], errors="coerce").to_numpy(dtype=float)
    full_mask = np.isfinite(full_x) & np.isfinite(full_y) & np.isfinite(full_c)
    clipped_c = np.clip(full_c[full_mask], color_low, color_high)
    hexbin = ax.hexbin(
        full_x[full_mask],
        full_y[full_mask],
        C=clipped_c,
        reduce_C_function=np.median,
        gridsize=75,
        mincnt=8,
        cmap=plt.get_cmap("viridis"),
        vmin=color_low,
        vmax=color_high,
        linewidths=0.0,
        alpha=0.95,
        zorder=1,
    )

    for group in ["expected_mild", "expected_severe"]:
        part = filtered_df[filtered_df["mechanism_group"] == group].copy()
        if part.empty:
            continue
        trend = build_group_trend(part, pre_col=pre_col, shap_col=shap_col)
        if not trend.empty:
            ax.plot(
                trend["pre_mid"].to_numpy(dtype=float),
                trend["shap_median"].to_numpy(dtype=float),
                color="#202124" if group == "expected_mild" else "#7f0000",
                linewidth=1.9,
                alpha=0.95,
                zorder=4,
                label=GROUP_LABELS[group],
            )

    ax.axhline(0.0, color="#616161", linewidth=1.0, linestyle="--", alpha=0.85, zorder=2)
    ax.axvline(low_pre_threshold, color="#7f5539", linewidth=1.0, linestyle=":", alpha=0.90, zorder=2)
    ax.set_title(f"{biome} | PRE vs PRE-SHAP (full sample colored)", fontsize=12.5)
    ax.set_xlabel("Recovery-window precipitation mean (m/day)", fontsize=11)
    ax.set_ylabel("SHAP value for recovery PRE", fontsize=11)
    ax.grid(alpha=0.18, linewidth=0.6)
    ax.legend(frameon=False, fontsize=9, loc="best")

    cbar = fig.colorbar(hexbin, ax=ax, pad=0.02, fraction=0.05)
    cbar.set_label("Post-drought GPP drop magnitude (-amp_max)", fontsize=10)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return summarize_biome(
        biome=biome,
        full_df=full_df,
        filtered_df=filtered_df,
        pre_col=pre_col,
        shap_col=shap_col,
        color_col=color_col,
        q_low=q_low,
        q_high=q_high,
    )


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    full_df = pd.read_parquet(args.full_table)
    filtered_df = pd.read_parquet(args.filtered_table)

    full_df = ensure_color_column(full_df, args.color_col)
    filtered_df = ensure_color_column(filtered_df, args.color_col)

    summaries: list[pd.DataFrame] = []
    for biome in BIOMES:
        full_part = full_df[full_df["biome"] == biome].copy()
        filtered_part = filtered_df[filtered_df["biome"] == biome].copy()
        if filtered_part.empty:
            continue
        summary_df = plot_biome(
            biome=biome,
            full_df=full_part,
            filtered_df=filtered_part,
            pre_col=args.pre_col,
            shap_col=args.shap_col,
            color_col=args.color_col,
            low_pre_threshold=args.low_pre_threshold,
            q_low=args.clip_q_low,
            q_high=args.clip_q_high,
            output_path=out_dir / f"{biome}_full_mechanism_filtered_pre_shap.png",
        )
        summaries.append(summary_df)

    if summaries:
        pd.concat(summaries, ignore_index=True).to_csv(out_dir / "summary.csv", index=False)


if __name__ == "__main__":
    main()
