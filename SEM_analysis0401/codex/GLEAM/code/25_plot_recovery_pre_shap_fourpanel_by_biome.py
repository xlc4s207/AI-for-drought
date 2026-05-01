#!/usr/bin/env python
"""Plot biome-wise recovery PRE dependence colored by recovery and event-severity metrics."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LogNorm, Normalize

from sem_gleam_common import finalize_feature_table


SHAP_ANALYSIS_PATH = Path(__file__).with_name("06_shap_analysis.py")
SHAP_ANALYSIS_SPEC = importlib.util.spec_from_file_location("shap_analysis_module", SHAP_ANALYSIS_PATH)
if SHAP_ANALYSIS_SPEC is None or SHAP_ANALYSIS_SPEC.loader is None:  # pragma: no cover
    raise RuntimeError(f"Unable to load helper module from {SHAP_ANALYSIS_PATH}")
shap_analysis_module = importlib.util.module_from_spec(SHAP_ANALYSIS_SPEC)
SHAP_ANALYSIS_SPEC.loader.exec_module(shap_analysis_module)

filter_analysis_subset = shap_analysis_module.filter_analysis_subset
prepare_model_inputs = shap_analysis_module.prepare_model_inputs


BIOMES = ["Cropland", "Forest", "Grassland", "Savanna", "Shrubland"]
MODEL_FEATURES = [
    "prepeak_total_precipitation_mean",
    "recoverywin_total_precipitation_mean",
    "recoverywin_total_evaporation_mean",
    "recoverywin_SMrz_mean",
    "recoverywin_temperature_2m_mean",
    "recoverywin_VPD_mean",
    "recoverywin_wind_speed_mean",
    "recoverywin_lai_total_mean",
    "recoverywin_ssrd_mean",
    "recoverywin_strd_mean",
]
EXCLUDE_FEATURES = [
    "recoverywin_p_minus_et",
    "recoverywin_total_precipitation_sum",
    "recoverywin_total_evaporation_sum",
    "recoverywin_SMrz_delta",
]
PANEL_SPECS = [
    ("t_recover_to_baseline_abs_peak", "t_recover", "viridis", False, "linear"),
    ("event_intensity", "intensity", "viridis", True, "log"),
    ("event_onset_drop", "onset_drop", "viridis", True, "linear"),
    ("amp_max", "GPP drop (amp_max)", "viridis", True, "linear"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--drought-table", required=True)
    parser.add_argument("--shap-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--metric", default="GPP")
    parser.add_argument("--code-id", default="code1")
    parser.add_argument("--drought-type", default="flash")
    parser.add_argument("--soil-layer", default="SMrz")
    parser.add_argument("--feature-scope", default="all")
    parser.add_argument("--limit", type=int, default=50000)
    parser.add_argument("--pre-col", default="recoverywin_total_precipitation_mean")
    parser.add_argument("--shap-col", default="recoverywin_total_precipitation_mean")
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
    trend = pd.Series(y2).rolling(window=max(31, len(y2) // 35), center=True, min_periods=1).mean()
    ax.plot(x2, trend.to_numpy(), color="#c83349", linewidth=2.0, alpha=0.95, zorder=3)


def build_biome_frame(
    base_df: pd.DataFrame,
    drought_df: pd.DataFrame,
    shap_root: Path,
    biome: str,
    args: argparse.Namespace,
) -> pd.DataFrame:
    sub = filter_analysis_subset(
        base_df,
        metric=args.metric,
        code_id=args.code_id,
        biome=biome,
        drought_type=args.drought_type,
        soil_layer=args.soil_layer,
    )
    if args.limit and len(sub) > args.limit:
        sub = sub.head(args.limit).copy()

    X, _, _ = prepare_model_inputs(
        sub,
        target="t_recover_to_baseline_abs_peak",
        max_missing_rate=0.3,
        feature_scope=args.feature_scope,
        include_features=MODEL_FEATURES,
        exclude_features=EXCLUDE_FEATURES,
    )

    biome_dir = shap_root / biome
    sample = pd.read_parquet(biome_dir / "dependence_sample_features.parquet")
    shap_values = pd.read_parquet(biome_dir / "dependence_sample_shap_values.parquet")

    missing_idx = sample.index.difference(X.index)
    if len(missing_idx) > 0:
        raise KeyError(f"Sample indices not found in model inputs for biome={biome}: {len(missing_idx)}")

    meta_cols = ["event_uid", "t_recover_to_baseline_abs_peak", "amp_max"]
    meta = sub.loc[sample.index, meta_cols].copy()
    sample = sample.add_suffix("__feature")
    shap_values = shap_values.add_suffix("__shap")
    merged = sample.join(shap_values).join(meta)
    merged = merged.merge(drought_df[["event_uid", "event_intensity", "event_onset_drop"]], on="event_uid", how="left")
    merged["biome"] = biome
    return merged


def plot_biome(
    df: pd.DataFrame,
    biome: str,
    output_path: Path,
    pre_col: str,
    shap_col: str,
    args: argparse.Namespace,
) -> dict[str, object]:
    x = pd.to_numeric(df[f"{pre_col}__feature"], errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(df[f"{shap_col}__shap"], errors="coerce").to_numpy(dtype=float)

    fig, axes = plt.subplots(2, 2, figsize=(14, 11), sharex=True, sharey=True)
    axes = axes.flatten()
    summary: dict[str, object] = {"biome": biome, "rows": int(len(df)), "output_png": str(output_path)}
    for ax, (col, label, cmap, use_robust_color, color_scale) in zip(axes, PANEL_SPECS):
        cvals = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
        mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(cvals)
        cvals_plot = cvals[mask]
        color_norm = None
        if cvals_plot.size > 0:
            raw_min = float(np.nanmin(cvals_plot))
            raw_max = float(np.nanmax(cvals_plot))
            if use_robust_color and cvals_plot.size >= 20:
                q_low = float(np.nanquantile(cvals_plot, args.clip_lower_quantile))
                q_high = float(np.nanquantile(cvals_plot, args.clip_upper_quantile))
                if np.isfinite(q_low) and np.isfinite(q_high) and q_high > q_low:
                    if color_scale == "log" and q_low > 0:
                        color_norm = LogNorm(vmin=q_low, vmax=q_high, clip=True)
                    else:
                        color_norm = Normalize(vmin=q_low, vmax=q_high, clip=True)
                    summary[f"{col}_raw_min"] = raw_min
                    summary[f"{col}_raw_max"] = raw_max
                    summary[f"{col}_clip_min"] = q_low
                    summary[f"{col}_clip_max"] = q_high
                else:
                    summary[f"{col}_raw_min"] = raw_min
                    summary[f"{col}_raw_max"] = raw_max
            else:
                summary[f"{col}_raw_min"] = raw_min
                summary[f"{col}_raw_max"] = raw_max
        sc = ax.scatter(
            x[mask],
            y[mask],
            c=cvals_plot,
            cmap=cmap,
            norm=color_norm,
            s=15,
            alpha=0.58,
            edgecolors="none",
            zorder=2,
        )
        add_trend(ax, x[mask], y[mask])
        ax.axhline(0.0, color="#6e6e6e", linewidth=1.0, linestyle="--", alpha=0.8, zorder=1)
        ax.set_title(f"{biome} | color={label}", fontsize=11.5)
        ax.grid(alpha=0.18, linewidth=0.6)
        cbar = fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.02)
        cbar.set_label(label, fontsize=10)
        cbar.ax.tick_params(labelsize=9)
        summary[f"non_null_{col}"] = int(mask.sum())
        summary[f"{col}_robust_color"] = bool(use_robust_color)
        summary[f"{col}_color_scale"] = color_scale
    for ax in axes[2:]:
        ax.set_xlabel("Recovery-window precipitation mean (m/day)", fontsize=10.5)
    axes[0].set_ylabel("SHAP value for recovery PRE", fontsize=10.5)
    axes[2].set_ylabel("SHAP value for recovery PRE", fontsize=10.5)
    fig.suptitle(f"{biome} | PRE-SHAP dependence colored by severity metrics", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return summary


def main() -> None:
    args = parse_args()
    if not 0.0 <= args.clip_lower_quantile < args.clip_upper_quantile <= 1.0:
        raise ValueError("Color clipping quantiles must satisfy 0 <= lower < upper <= 1.")
    base_df = finalize_feature_table(pd.read_parquet(args.table))
    drought_df = pd.read_parquet(args.drought_table)
    shap_root = Path(args.shap_root)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, object]] = []
    for biome in BIOMES:
        biome_frame = build_biome_frame(base_df, drought_df, shap_root, biome, args)
        out_png = out_dir / f"{biome}_recovery_pre_shap_fourpanel.png"
        summary_rows.append(
            plot_biome(
                biome_frame,
                biome=biome,
                output_path=out_png,
                pre_col=args.pre_col,
                shap_col=args.shap_col,
                args=args,
            )
        )
    pd.DataFrame(summary_rows).to_csv(out_dir / "summary.csv", index=False)


if __name__ == "__main__":
    main()
